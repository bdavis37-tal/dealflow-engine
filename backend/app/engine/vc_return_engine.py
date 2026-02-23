"""
VC Fund-Seat Return Engine

Core computations for seed/early-stage VC deal analysis from the investor's perspective.
Implements:
  1. Ownership math  — entry %, dilution stack, exit %
  2. Fund returner   — exit threshold to matter to the fund
  3. 3-scenario model (First Chicago from LP seat)
  4. Waterfall       — liquidation preference + conversion analysis
  5. Pro-rata        — option value of exercising follow-on rights
  6. Portfolio       — deployment tracking, concentration, TVPI/DPI/RVPI
  7. IC memo         — auto-populated financial section text
  8. QSBS            — eligibility + tax benefit
  9. Anti-dilution   — full ratchet vs. broad-based weighted average
  10. Bridge round   — ownership impact + IRR analysis

All monetary values: USD millions.
All rates/percentages: decimals (0.20 = 20%).
"""
from __future__ import annotations

import json
import logging
import math
import os
from typing import Optional

from .vc_fund_models import (
    AntiDilutionInput, AntiDilutionOutput, AntiDilutionType,
    BridgeRoundInput, BridgeRoundOutput,
    DilutionAssumptions,
    FundProfile,
    ICMemoFinancials,
    LPReportInput, LPReportOutput,
    OwnershipMath,
    PortfolioConstructionStats, PortfolioInput, PortfolioOutput, PortfolioPosition,
    PreferenceType,
    ProRataAnalysis,
    QSBSInput, QSBSOutput,
    QuickScreenResult,
    VCDealInput, VCDealOutput,
    VCScenario,
    VCStage, VCVertical,
    WaterfallDistribution,
)

logger = logging.getLogger(__name__)

_DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "vc_benchmarks.json")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_benchmarks() -> dict:
    try:
        with open(_DATA_PATH, "r") as f:
            return json.load(f)
    except Exception:
        logger.warning("Could not load vc_benchmarks.json — using hardcoded defaults")
        return {}


def _irr(investment: float, proceeds: float, years: float) -> float:
    """Compute IRR for a single cash-in / cash-out scenario."""
    if investment <= 0 or proceeds <= 0 or years <= 0:
        return 0.0
    return (proceeds / investment) ** (1.0 / years) - 1.0


def _npv(rate: float, cashflows: list[tuple[float, float]]) -> float:
    """Compute NPV. cashflows = [(year, amount), ...]"""
    return sum(cf / (1 + rate) ** yr for yr, cf in cashflows)


def _xirr(investment: float, proceeds: float, years: float) -> float:
    """Binary-search IRR (same as _irr for single cashflow)."""
    return _irr(investment, proceeds, years)


def _carry_adj_proceeds(gross: float, cost_basis: float, carry_pct: float, hurdle: float,
                         years: float) -> float:
    """
    Net proceeds after carry. Simplified: carry only charged on gains above
    hurdle-rate-compounded return. No catch-up modeled for simplicity.
    """
    hurdle_basis = cost_basis * (1 + hurdle) ** years
    gain_above_hurdle = max(0.0, gross - hurdle_basis)
    carry = gain_above_hurdle * carry_pct
    return gross - carry


def _runway_months(cash: float, burn: float) -> Optional[float]:
    if burn <= 0:
        return None
    return cash / burn


# ---------------------------------------------------------------------------
# 1. Ownership Math
# ---------------------------------------------------------------------------

def compute_ownership_math(
    check_size: float,
    post_money: float,
    stage: VCStage,
    dilution: DilutionAssumptions,
    fund_profile: FundProfile,
    arr: float,
) -> OwnershipMath:
    """
    Core ownership calculations. All the math a VC does on a napkin, automated.

    Dilution stack applied from current stage forward to assumed exit.
    We assume exits happen after C/D round (Series C+ through IPO).
    """
    entry_pct = check_size / post_money

    # Build dilution stack based on entry stage
    stack: list[dict] = []
    current_pct = entry_pct

    stage_sequence = {
        VCStage.PRE_SEED: ["seed", "series_a", "series_b", "series_c", "ipo"],
        VCStage.SEED:     ["series_a", "series_b", "series_c", "ipo"],
        VCStage.SERIES_A: ["series_b", "series_c", "ipo"],
        VCStage.SERIES_B: ["series_c", "ipo"],
        VCStage.SERIES_C: ["ipo"],
        VCStage.GROWTH:   [],
    }

    dilution_map = {
        "seed":     dilution.pre_seed_to_seed,
        "series_a": dilution.seed_to_a,
        "series_b": dilution.a_to_b,
        "series_c": dilution.b_to_c,
        "ipo":      dilution.c_to_ipo,
    }

    future_rounds = stage_sequence.get(stage, [])
    for rnd in future_rounds:
        d = dilution_map.get(rnd, 0.0)
        # also include option pool expansion
        effective_dilution = d + dilution.option_pool_expansion
        pre_round = current_pct
        current_pct = current_pct * (1 - effective_dilution)
        stack.append({
            "round": rnd.replace("_", " ").title(),
            "dilution_pct": effective_dilution,
            "ownership_before": pre_round,
            "ownership_after": current_pct,
        })

    exit_pct = current_pct
    total_dilution = 1.0 - (exit_pct / entry_pct) if entry_pct > 0 else 0.0

    # Fund returner thresholds
    def fund_returner_exit(target_x: float) -> float:
        target_proceeds = fund_profile.fund_size * target_x
        if exit_pct <= 0:
            return float("inf")
        return target_proceeds / exit_pct

    fr_1x = fund_returner_exit(1.0)
    fr_3x = fund_returner_exit(3.0)
    fr_5x = fund_returner_exit(5.0)

    # Test exits at round numbers
    test_exits = [50, 100, 250, 500, 1000, 2000, 5000, 10000]
    gross_at_exits = [e * exit_pct for e in test_exits]
    contribution_at_exits = [g / fund_profile.fund_size for g in gross_at_exits]

    # ARR multiples needed for fund returner thresholds
    arr_multiple_1x = (fr_1x / arr) if arr > 0 else None
    arr_multiple_3x = (fr_3x / arr) if arr > 0 else None

    return OwnershipMath(
        entry_ownership_pct=entry_pct,
        exit_ownership_pct=exit_pct,
        dilution_stack=stack,
        total_dilution_pct=total_dilution,
        fund_returner_1x_exit=fr_1x,
        fund_returner_3x_exit=fr_3x,
        fund_returner_5x_exit=fr_5x,
        exit_values_tested=[float(e) for e in test_exits],
        gross_proceeds_at_exits=gross_at_exits,
        fund_contribution_at_exits=contribution_at_exits,
        required_arr_multiple_for_1x_fund=arr_multiple_1x,
        required_arr_multiple_for_3x_fund=arr_multiple_3x,
    )


# ---------------------------------------------------------------------------
# 2. Scenario Engine
# ---------------------------------------------------------------------------

def _build_scenario(
    label: str,
    probability: float,
    exit_multiple_arr: float,
    arr: float,
    revenue_ttm: float,
    exit_year: int,
    exit_ownership_pct: float,
    check_size: float,
    fund_size: float,
    carry_pct: float,
    hurdle: float,
    outcome_description: str,
    revenue_growth_rate: float = 1.5,
) -> VCScenario:
    """Build a single scenario.

    Exit EV = exit_multiple × projected_ARR_at_exit_year.
    ARR is projected forward using the deal's revenue growth rate, which
    itself is scenario-adjusted (bear: 0.5x, base: 1.0x, bull: 1.3x of stated rate).
    If no ARR/revenue data, uses a $10M ARR placeholder.
    """
    # Use ARR if available, fall back to revenue
    current_revenue = arr if arr > 0 else (revenue_ttm if revenue_ttm > 0 else None)

    if current_revenue and current_revenue > 0:
        # Scenario-specific growth rate modifier
        growth_mods = {"Bear": 0.5, "Base": 1.0, "Bull": 1.3}
        mod = growth_mods.get(label, 1.0)
        effective_growth = max(0.0, revenue_growth_rate * mod)
        # Project ARR to exit year (capped at 10x current to avoid unrealistic projections)
        projected_arr = current_revenue * ((1 + effective_growth) ** exit_year)
        projected_arr = min(projected_arr, current_revenue * 100)  # cap at 100x current
        exit_ev = exit_multiple_arr * projected_arr
    else:
        # No revenue data — use a conservative placeholder
        exit_ev = exit_multiple_arr * 10.0  # $10M ARR placeholder

    gross_proceeds = exit_ev * exit_ownership_pct
    net_proceeds = _carry_adj_proceeds(gross_proceeds, check_size, carry_pct, hurdle, exit_year)

    gross_moic = gross_proceeds / check_size if check_size > 0 else 0.0
    net_moic = net_proceeds / check_size if check_size > 0 else 0.0

    gross_irr = _irr(check_size, gross_proceeds, exit_year)
    net_irr = _irr(check_size, net_proceeds, exit_year)

    fund_contrib = gross_proceeds / fund_size

    return VCScenario(
        label=label,
        probability=probability,
        exit_year=exit_year,
        exit_multiple_arr=exit_multiple_arr,
        exit_enterprise_value=exit_ev,
        gross_proceeds_to_fund=gross_proceeds,
        net_proceeds_to_fund=net_proceeds,
        gross_moic=gross_moic,
        net_moic=net_moic,
        gross_irr=gross_irr,
        net_irr=net_irr,
        fund_contribution_x=fund_contrib,
        outcome_description=outcome_description,
    )


def compute_scenarios(
    deal: VCDealInput,
    fund: FundProfile,
    exit_ownership_pct: float,
    benchmarks: dict,
) -> tuple[VCScenario, VCScenario, VCScenario]:
    """
    Build bear/base/bull scenarios using vertical benchmarks or overrides.

    Exit multiples are ARR multiples (or revenue multiples for non-SaaS).
    Probabilities follow typical VC power-law distribution:
      - Bear:  40% probability (includes 0x write-off scenarios)
      - Base:  40% probability
      - Bull:  20% probability
    """
    vertical_data = benchmarks.get("verticals", {}).get(deal.vertical.value, {})
    exit_multiples = vertical_data.get("exit_multiples", {})

    bear_mult = deal.bear_exit_multiple_arr or exit_multiples.get("bear", 2.0)
    base_mult = deal.base_exit_multiple_arr or exit_multiples.get("base", 5.0)
    bull_mult = deal.bull_exit_multiple_arr or exit_multiples.get("bull", 12.0)

    exit_yr = deal.expected_exit_years

    bear = _build_scenario(
        label="Bear",
        probability=0.40,
        exit_multiple_arr=bear_mult,
        arr=deal.arr,
        revenue_ttm=deal.revenue_ttm,
        exit_year=exit_yr,
        exit_ownership_pct=exit_ownership_pct,
        check_size=deal.check_size,
        fund_size=fund.fund_size,
        carry_pct=fund.carry_pct,
        hurdle=fund.hurdle_rate,
        revenue_growth_rate=deal.revenue_growth_rate,
        outcome_description=(
            f"Modest outcome: {bear_mult:.0f}x ARR at exit. "
            "Company reaches product-market fit but faces execution challenges, "
            "competitive pressure, or unfavorable exit environment."
        ),
    )

    base = _build_scenario(
        label="Base",
        probability=0.40,
        exit_multiple_arr=base_mult,
        arr=deal.arr,
        revenue_ttm=deal.revenue_ttm,
        exit_year=exit_yr,
        exit_ownership_pct=exit_ownership_pct,
        check_size=deal.check_size,
        fund_size=fund.fund_size,
        carry_pct=fund.carry_pct,
        hurdle=fund.hurdle_rate,
        revenue_growth_rate=deal.revenue_growth_rate,
        outcome_description=(
            f"Expected case: {base_mult:.0f}x ARR at exit. "
            "Company executes on plan, reaches growth milestones, "
            "and achieves a strategic M&A exit or IPO at median valuations."
        ),
    )

    bull = _build_scenario(
        label="Bull",
        probability=0.20,
        exit_multiple_arr=bull_mult,
        arr=deal.arr,
        revenue_ttm=deal.revenue_ttm,
        exit_year=exit_yr,
        exit_ownership_pct=exit_ownership_pct,
        check_size=deal.check_size,
        fund_size=fund.fund_size,
        carry_pct=fund.carry_pct,
        hurdle=fund.hurdle_rate,
        revenue_growth_rate=deal.revenue_growth_rate,
        outcome_description=(
            f"Power-law outcome: {bull_mult:.0f}x ARR at exit. "
            "Category-defining company, dominant market position, "
            "IPO or acquisition at premium valuation. Top-decile result."
        ),
    )

    return bear, base, bull


# ---------------------------------------------------------------------------
# 3. Quick Screen
# ---------------------------------------------------------------------------

def _ownership_adequacy(entry_pct: float, target_pct: float) -> str:
    ratio = entry_pct / target_pct if target_pct > 0 else 0.0
    if ratio >= 0.90:
        return "strong"
    if ratio >= 0.70:
        return "acceptable"
    return "thin"


def compute_quick_screen(
    deal: VCDealInput,
    fund: FundProfile,
    ownership: OwnershipMath,
    bear: VCScenario,
    base: VCScenario,
    bull: VCScenario,
    benchmarks: dict,
) -> QuickScreenResult:
    """Single-screen pass/look-deeper/strong-interest recommendation."""
    flags: list[str] = []
    entry_pct = ownership.entry_ownership_pct
    exit_pct = ownership.exit_ownership_pct

    # Ownership check
    adequacy = _ownership_adequacy(entry_pct, fund.target_ownership_pct)
    if adequacy == "thin":
        flags.append(f"Ownership thin: {entry_pct:.1%} entry vs {fund.target_ownership_pct:.1%} target")

    # Check size vs target
    target_check = fund.target_initial_check_size
    if target_check > 0 and deal.check_size > target_check * 1.5:
        flags.append(f"Check size ${deal.check_size:.1f}M exceeds target ${target_check:.1f}M by >50%")

    # Valuation vs benchmark
    vdata = benchmarks.get("verticals", {}).get(deal.vertical.value, {})
    stage_data = vdata.get(deal.stage.value, {})
    median_post = stage_data.get("median_post_money_usd_m", None)
    if median_post and deal.post_money_valuation > median_post * 1.5:
        flags.append(
            f"Valuation ${deal.post_money_valuation:.0f}M is >1.5x median ${median_post:.0f}M for "
            f"{deal.stage.value} {deal.vertical.value}"
        )

    # Fund returner check
    fr_threshold = ownership.fund_returner_1x_exit
    if base.exit_enterprise_value < fr_threshold:
        flags.append(
            f"Base case exit (${base.exit_enterprise_value:.0f}M) below fund-returner "
            f"threshold (${fr_threshold:.0f}M)"
        )

    # Runway
    if deal.burn_rate_monthly > 0 and deal.cash_on_hand > 0:
        runway = _runway_months(deal.cash_on_hand, deal.burn_rate_monthly)
        if runway and runway < 12:
            flags.append(f"Short runway: {runway:.0f} months")

    # ARR multiple at entry
    if deal.arr > 0:
        arr_multiple = deal.post_money_valuation / deal.arr
        benchmark_arr_mult = stage_data.get("median_arr_multiple", None)
        if benchmark_arr_mult and arr_multiple > benchmark_arr_mult * 1.5:
            flags.append(
                f"Entry ARR multiple {arr_multiple:.0f}x vs benchmark {benchmark_arr_mult:.0f}x "
                f"(paying {arr_multiple/benchmark_arr_mult:.1f}x median)"
            )

    # Recommendation
    serious_flags = len([f for f in flags if "thin" in f or "below fund-returner" in f or "Short runway" in f])
    if base.gross_moic >= 10 and adequacy in ("strong", "acceptable") and serious_flags == 0:
        rec = "strong_interest"
        rec_rationale = (
            f"Base case {base.gross_moic:.1f}x MOIC, ownership adequate at {entry_pct:.1%} entry, "
            "no blocking flags. Merits serious diligence."
        )
    elif base.gross_moic >= 5 and serious_flags <= 1:
        rec = "look_deeper"
        rec_rationale = (
            f"Base case {base.gross_moic:.1f}x MOIC is attractive. "
            f"{'Address flags before proceeding.' if flags else 'Conduct standard diligence.'}"
        )
    else:
        rec = "pass"
        rec_rationale = (
            f"Base case {base.gross_moic:.1f}x MOIC insufficient given fund math, "
            f"or {len(flags)} blocking flag(s). Pass or revisit at better terms."
        )

    arr_multiple_entry = (deal.post_money_valuation / deal.arr) if deal.arr > 0 else None
    fr_arr = ownership.required_arr_multiple_for_1x_fund

    return QuickScreenResult(
        company_name=deal.company_name,
        stage=deal.stage,
        vertical=deal.vertical,
        post_money=deal.post_money_valuation,
        check_size=deal.check_size,
        entry_ownership_pct=entry_pct,
        exit_ownership_pct=exit_pct,
        fund_returner_threshold=fr_threshold,
        fund_returner_arr_multiple=fr_arr,
        bear_ev=bear.exit_enterprise_value,
        base_ev=base.exit_enterprise_value,
        bull_ev=bull.exit_enterprise_value,
        bear_moic=bear.gross_moic,
        base_moic=base.gross_moic,
        bull_moic=bull.gross_moic,
        recommendation=rec,
        recommendation_rationale=rec_rationale,
        flags=flags,
    )


# ---------------------------------------------------------------------------
# 4. Waterfall Analysis
# ---------------------------------------------------------------------------

def compute_waterfall(deal: VCDealInput, exit_ev: float) -> WaterfallDistribution:
    """
    Distribute exit proceeds through the liquidation preference stack.
    Handles non-participating, participating, and capped participating preferred.
    """
    stack = sorted(deal.liquidation_stack, key=lambda x: x.seniority)
    remaining = exit_ev
    distributions: list[dict] = []

    # Step 1: Pay liquidation preferences in seniority order
    for pref in stack:
        pref_amount = pref.invested_amount * pref.preference_multiple
        paid = min(remaining, pref_amount)
        remaining -= paid
        distributions.append({
            "share_class": pref.share_class,
            "type": pref.preference_type.value,
            "preference_amount": pref.invested_amount,
            "preference_multiple": pref.preference_multiple,
            "liquidation_payout": paid,
            "conversion_value": 0.0,  # filled later
            "gets": paid,
            "converted": False,
        })

    # Step 2: Distribute remainder to common (and participating preferred if applicable)
    # Estimate total shares to allocate remainder proportionally
    total_preferred_invested = sum(p.invested_amount for p in stack) if stack else 1.0
    common_fraction = deal.common_shares_pct

    for i, (d, pref) in enumerate(zip(distributions, stack)):
        if pref.preference_type == PreferenceType.NON_PARTICIPATING:
            # Check if conversion is better
            preferred_fraction = (pref.invested_amount / total_preferred_invested) * (1 - common_fraction)
            conversion_value = exit_ev * preferred_fraction
            if conversion_value > d["liquidation_payout"]:
                d["gets"] = conversion_value
                d["converted"] = True
                d["conversion_value"] = conversion_value

        elif pref.preference_type == PreferenceType.PARTICIPATING:
            # Gets liquidation preference + pro-rata on remainder
            preferred_fraction = (pref.invested_amount / total_preferred_invested) * (1 - common_fraction)
            participation = remaining * preferred_fraction
            d["gets"] = d["liquidation_payout"] + participation
            d["conversion_value"] = d["gets"]

        elif pref.preference_type == PreferenceType.PARTICIPATING_CAPPED:
            preferred_fraction = (pref.invested_amount / total_preferred_invested) * (1 - common_fraction)
            participation = remaining * preferred_fraction
            cap_value = pref.invested_amount * (pref.participation_cap or 3.0)
            d["gets"] = min(d["liquidation_payout"] + participation, cap_value)
            d["conversion_value"] = d["gets"]

    # Common gets remainder after preferences
    total_preferred_gets = sum(d["gets"] for d in distributions)
    common_gets = max(0.0, exit_ev - total_preferred_gets)

    # Find "our" position (first preferred, or most junior)
    investor_total = distributions[0]["gets"] if distributions else 0.0
    investor_moic = investor_total / stack[0].invested_amount if (stack and stack[0].invested_amount > 0) else 0.0

    return WaterfallDistribution(
        exit_ev=exit_ev,
        share_classes=distributions,
        common_gets=common_gets,
        total_distributed=exit_ev,
        investor_total=investor_total,
        investor_moic=investor_moic,
        conversion_was_optimal=distributions[0]["converted"] if distributions else False,
    )


# ---------------------------------------------------------------------------
# 5. Pro-Rata Analysis
# ---------------------------------------------------------------------------

def compute_pro_rata(
    deal: VCDealInput,
    fund: FundProfile,
    ownership: OwnershipMath,
    next_round_valuation: float,
    pro_rata_check: float,
    benchmarks: dict,
) -> ProRataAnalysis:
    """
    Should you exercise your pro-rata right?

    Builds two scenario sets (exercise vs. pass) and computes expected value of each.
    """
    # Dilution from here (partial stack)
    # Simplified: assume 2 more rounds of dilution remain
    maintained_pct = ownership.exit_ownership_pct  # If we exercise
    diluted_pct = maintained_pct * (1 - deal.dilution.a_to_b)  # If we pass

    reserve_after_pct = (
        (fund.reserve_pool - pro_rata_check) / fund.reserve_pool
        if fund.reserve_pool > 0
        else 0.0
    )

    # Build simplified scenarios for both choices
    exercise_scenarios = []
    pass_scenarios = []

    for sc_label, sc_prob, sc_mult in [("Bear", 0.40, 2.0), ("Base", 0.40, 7.0), ("Bull", 0.20, 15.0)]:
        exit_ev = sc_mult * (deal.arr if deal.arr > 0 else deal.revenue_ttm or 10.0)

        # With exercise (maintain ownership)
        proceeds_exercise = exit_ev * maintained_pct
        moic_exercise = proceeds_exercise / (deal.check_size + pro_rata_check)
        irr_exercise = _irr(deal.check_size + pro_rata_check, proceeds_exercise, deal.expected_exit_years)
        exercise_scenarios.append(VCScenario(
            label=f"{sc_label} (exercise)",
            probability=sc_prob,
            exit_year=deal.expected_exit_years,
            exit_multiple_arr=sc_mult,
            exit_enterprise_value=exit_ev,
            gross_proceeds_to_fund=proceeds_exercise,
            net_proceeds_to_fund=_carry_adj_proceeds(proceeds_exercise, deal.check_size + pro_rata_check,
                                                     fund.carry_pct, fund.hurdle_rate, deal.expected_exit_years),
            gross_moic=moic_exercise,
            net_moic=moic_exercise * (1 - fund.carry_pct),
            gross_irr=irr_exercise,
            net_irr=irr_exercise * 0.85,
            fund_contribution_x=proceeds_exercise / fund.fund_size,
            outcome_description=f"Pro-rata exercised at ${next_round_valuation:.0f}M valuation",
        ))

        # Without exercise (diluted)
        proceeds_pass = exit_ev * diluted_pct
        moic_pass = proceeds_pass / deal.check_size
        irr_pass = _irr(deal.check_size, proceeds_pass, deal.expected_exit_years)
        pass_scenarios.append(VCScenario(
            label=f"{sc_label} (pass)",
            probability=sc_prob,
            exit_year=deal.expected_exit_years,
            exit_multiple_arr=sc_mult,
            exit_enterprise_value=exit_ev,
            gross_proceeds_to_fund=proceeds_pass,
            net_proceeds_to_fund=_carry_adj_proceeds(proceeds_pass, deal.check_size,
                                                     fund.carry_pct, fund.hurdle_rate, deal.expected_exit_years),
            gross_moic=moic_pass,
            net_moic=moic_pass * (1 - fund.carry_pct),
            gross_irr=irr_pass,
            net_irr=irr_pass * 0.85,
            fund_contribution_x=proceeds_pass / fund.fund_size,
            outcome_description=f"Diluted to {diluted_pct:.1%} ownership",
        ))

    ev_exercise = sum(s.gross_proceeds_to_fund * s.probability for s in exercise_scenarios)
    ev_pass = sum(s.gross_proceeds_to_fund * s.probability for s in pass_scenarios)

    incremental_value = ev_exercise - ev_pass
    if pro_rata_check <= 0 or incremental_value > pro_rata_check * 2:
        rec = "exercise"
        rec_rationale = (
            f"Expected value of maintaining ownership (${ev_exercise:.1f}M) outweighs "
            f"cost of pro-rata (${pro_rata_check:.1f}M). Exercise if reserve available."
        )
    elif incremental_value > 0:
        rec = "partial"
        rec_rationale = (
            f"Marginal incremental value (${incremental_value:.1f}M) from exercise. "
            "Consider partial exercise to conserve reserves."
        )
    else:
        rec = "pass"
        rec_rationale = (
            f"Expected dilution impact (${ev_pass - ev_exercise:.1f}M) insufficient to justify "
            f"${pro_rata_check:.1f}M reserve deployment."
        )

    return ProRataAnalysis(
        company_name=deal.company_name,
        next_round_valuation=next_round_valuation,
        pro_rata_amount=pro_rata_check,
        maintained_ownership_pct=maintained_pct,
        diluted_ownership_if_pass=diluted_pct,
        reserve_impact=pro_rata_check,
        reserve_pct_remaining_after=max(0.0, reserve_after_pct),
        exercise_scenarios=exercise_scenarios,
        pass_scenarios=pass_scenarios,
        expected_value_exercise=ev_exercise,
        expected_value_pass=ev_pass,
        recommendation=rec,
        recommendation_rationale=rec_rationale,
    )


# ---------------------------------------------------------------------------
# 6. Portfolio Construction
# ---------------------------------------------------------------------------

def compute_portfolio_stats(
    fund: FundProfile,
    positions: list[PortfolioPosition],
) -> PortfolioConstructionStats:
    """Compute fund-level portfolio construction metrics."""
    active = [p for p in positions if p.status == "active"]
    exited = [p for p in positions if p.status == "exited"]
    written_off = [p for p in positions if p.status == "written_off"]

    total_initial = sum(p.check_size for p in positions)
    total_reserve = sum(p.reserve_deployed for p in positions)
    total_deployed = total_initial + total_reserve

    initial_remaining = max(0.0, fund.initial_check_pool - total_initial)
    reserve_remaining = max(0.0, fund.reserve_pool - total_reserve)

    pct_deployed = total_deployed / fund.investable_capital if fund.investable_capital > 0 else 0.0

    # Stage breakdown
    stage_breakdown: dict[str, float] = {}
    vertical_breakdown: dict[str, float] = {}
    for p in positions:
        stage_breakdown[p.stage_at_entry.value] = (
            stage_breakdown.get(p.stage_at_entry.value, 0.0) + p.cost_basis
        )
        vertical_breakdown[p.vertical.value] = (
            vertical_breakdown.get(p.vertical.value, 0.0) + p.cost_basis
        )

    total_cost = sum(p.cost_basis for p in positions)
    largest_pct = max((p.cost_basis / total_cost for p in positions), default=0.0) if total_cost > 0 else 0.0

    total_fv = sum(p.fair_value or p.cost_basis for p in positions)
    total_realized = sum(p.realized_proceeds for p in positions)

    dpi = total_realized / total_cost if total_cost > 0 else 0.0
    rvpi = total_fv / total_cost if total_cost > 0 else 0.0
    tvpi = dpi + rvpi

    # Reserve adequacy
    total_reserve_alloc = sum(p.reserve_allocated for p in positions)
    if total_reserve_alloc <= fund.reserve_pool * 0.90:
        reserve_adequacy = "adequate"
    elif total_reserve_alloc <= fund.reserve_pool * 1.10:
        reserve_adequacy = "tight"
    else:
        reserve_adequacy = "over-reserved"

    avg_followon = (
        (total_reserve / total_initial) if total_initial > 0 else 0.0
    )

    return PortfolioConstructionStats(
        fund_size=fund.fund_size,
        investable_capital=fund.investable_capital,
        initial_check_pool=fund.initial_check_pool,
        reserve_pool=fund.reserve_pool,
        total_initial_deployed=total_initial,
        total_reserve_deployed=total_reserve,
        total_deployed=total_deployed,
        pct_deployed=pct_deployed,
        initial_remaining=initial_remaining,
        reserve_remaining=reserve_remaining,
        total_remaining=max(0.0, fund.investable_capital - total_deployed),
        company_count=len(positions),
        stage_breakdown=stage_breakdown,
        vertical_breakdown=vertical_breakdown,
        largest_position_pct=largest_pct,
        total_cost_basis=total_cost,
        total_fair_value=total_fv,
        unrealized_tvpi=rvpi,
        realized_proceeds=total_realized,
        dpi=dpi,
        rvpi=rvpi,
        tvpi=tvpi,
        reserve_adequacy=reserve_adequacy,
        average_follow_on_multiple=avg_followon,
    )


def run_portfolio_analysis(inp: PortfolioInput) -> PortfolioOutput:
    """Full portfolio construction analysis."""
    stats = compute_portfolio_stats(inp.fund_profile, inp.positions)
    alerts: list[str] = []
    recs: list[str] = []

    # Concentration alerts
    for vertical, amt in stats.vertical_breakdown.items():
        pct = amt / stats.total_cost_basis if stats.total_cost_basis > 0 else 0.0
        if pct > 0.35:
            alerts.append(f"High concentration: {pct:.0%} of portfolio in {vertical.replace('_', ' ').title()}")

    if stats.largest_position_pct > 0.20:
        alerts.append(f"Single position represents {stats.largest_position_pct:.0%} of cost basis")

    if stats.reserve_adequacy == "over-reserved":
        alerts.append("Reserve pool over-allocated — review reserve assignments")
        recs.append("Consider reducing reserves on early-stage positions with uncertain follow-on opportunity")

    if stats.reserve_adequacy == "tight":
        alerts.append("Reserve pool approaching capacity — deploy initial checks cautiously")

    if stats.pct_deployed > 0.80:
        recs.append("Fund >80% deployed — reserve allocation is critical, prioritize follow-ons carefully")

    if stats.tvpi < 1.0:
        alerts.append(f"TVPI below 1.0x ({stats.tvpi:.2f}x) — portfolio underwater on marks")

    return PortfolioOutput(
        stats=stats,
        positions=inp.positions,
        alerts=alerts,
        recommendations=recs,
    )


# ---------------------------------------------------------------------------
# 7. IC Memo Generation
# ---------------------------------------------------------------------------

def build_ic_memo(
    deal: VCDealInput,
    fund: FundProfile,
    ownership: OwnershipMath,
    bear: VCScenario,
    base: VCScenario,
    bull: VCScenario,
    expected_value: float,
    benchmarks: dict,
) -> ICMemoFinancials:
    """Auto-generate the financial section of an IC memo."""
    runway = _runway_months(deal.cash_on_hand, deal.burn_rate_monthly)

    vdata = benchmarks.get("verticals", {}).get(deal.vertical.value, {})
    stage_data = vdata.get(deal.stage.value, {})
    median_arr_mult = stage_data.get("median_arr_multiple", None)

    arr_multiple_at_entry = (deal.post_money_valuation / deal.arr) if deal.arr > 0 else None

    if arr_multiple_at_entry and median_arr_mult:
        ratio = arr_multiple_at_entry / median_arr_mult
        if ratio > 1.3:
            valuation_vs_benchmark = "above market"
        elif ratio < 0.8:
            valuation_vs_benchmark = "below market"
        else:
            valuation_vs_benchmark = "at market"
    else:
        valuation_vs_benchmark = "insufficient data for comparison"

    # Financial summary text
    arr_str = f"${deal.arr:.1f}M ARR" if deal.arr > 0 else "pre-revenue"
    growth_str = f"{deal.revenue_growth_rate:.0%} YoY growth" if deal.revenue_growth_rate > 0 else "growth not provided"

    summary = (
        f"We are proposing a ${deal.check_size:.1f}M investment at a ${deal.post_money_valuation:.0f}M "
        f"post-money valuation ({deal.stage.value.replace('_',' ').title()} round). "
        f"The company has {arr_str} with {growth_str} and a {deal.gross_margin:.0%} gross margin. "
        f"Our initial ownership is {ownership.entry_ownership_pct:.1%}, expected to dilute to "
        f"{ownership.exit_ownership_pct:.1%} at exit after {ownership.total_dilution_pct:.0%} dilution. "
        f"In our base case, the company exits at ${base.exit_enterprise_value:.0f}M "
        f"({base.gross_moic:.1f}x MOIC, {base.gross_irr:.0%} IRR). "
        f"To return 1x the fund, we need a ${ownership.fund_returner_1x_exit:.0f}M exit. "
        f"{'This is achievable in the base case.' if base.exit_enterprise_value > ownership.fund_returner_1x_exit else 'The base case does not return the fund — outperformance required.'} "
        f"Probability-weighted expected proceeds: ${expected_value:.1f}M "
        f"({expected_value / fund.fund_size:.1f}x of fund)."
    )

    thesis_prompt = (
        f"[Analyst: complete the following]\n\n"
        f"We are investing ${deal.check_size:.1f}M in {deal.company_name} because:\n\n"
        f"1. MARKET THESIS: [Why is {deal.vertical.value.replace('_',' ')} a compelling category now?]\n"
        f"2. COMPANY DIFFERENTIATION: [What is {deal.company_name}'s specific edge?]\n"
        f"3. TEAM: [Why is this team uniquely positioned to win?]\n"
        f"4. RISK FACTORS: [What are the 3 key risks and how do we mitigate them?]\n"
        f"5. EXIT PATH: [Who are the likely acquirers? What is the IPO path?]"
    )

    return ICMemoFinancials(
        company_name=deal.company_name,
        stage=deal.stage,
        vertical=deal.vertical,
        check_size=deal.check_size,
        post_money=deal.post_money_valuation,
        entry_ownership_pct=ownership.entry_ownership_pct,
        instrument="SAFE" if deal.stage in (VCStage.PRE_SEED, VCStage.SEED) else "Priced Equity",
        board_seat=deal.board_seat,
        pro_rata_rights=deal.pro_rata_rights,
        arr=deal.arr,
        revenue_growth_rate=deal.revenue_growth_rate,
        gross_margin=deal.gross_margin,
        burn_rate_monthly=deal.burn_rate_monthly,
        runway_months=runway,
        ownership_at_exit=ownership.exit_ownership_pct,
        total_dilution_pct=ownership.total_dilution_pct,
        scenarios=[bear, base, bull],
        expected_value=expected_value,
        fund_returner_threshold=ownership.fund_returner_1x_exit,
        fund_contribution_base=base.fund_contribution_x,
        arr_multiple_at_entry=arr_multiple_at_entry,
        stage_median_arr_multiple=median_arr_mult,
        valuation_vs_benchmark=valuation_vs_benchmark,
        investment_thesis_prompt=thesis_prompt,
        financial_summary_text=summary,
    )


# ---------------------------------------------------------------------------
# 8. QSBS Analysis
# ---------------------------------------------------------------------------

def run_qsbs_analysis(inp: QSBSInput) -> QSBSOutput:
    """
    IRC § 1202 QSBS eligibility analysis.
    Post-July 4, 2025: new $15M exclusion cap per taxpayer (up from $10M).
    """
    checks = [
        {
            "name": "C-Corporation",
            "passed": inp.incorporated_in_c_corp,
            "note": "Must be incorporated as a domestic C-Corp.",
        },
        {
            "name": "Domestic US Corporation",
            "passed": inp.domestic_us_corp,
            "note": "Must be organized under US state law.",
        },
        {
            "name": "Active Trade or Business",
            "passed": inp.active_business,
            "note": "Cannot be a professional services firm, finance/insurance company, or holding company.",
        },
        {
            "name": "Assets ≤ $50M at Issuance",
            "passed": inp.assets_at_issuance_under_50m,
            "note": "Aggregate gross assets must be ≤$50M at the time of stock issuance.",
        },
        {
            "name": "Original Issuance",
            "passed": inp.original_issuance,
            "note": "Shares must be acquired directly from the corporation (not secondary market).",
        },
    ]

    is_eligible = all(c["passed"] for c in checks)
    holding_satisfied = inp.holding_period_years >= 5.0
    years_remaining = max(0.0, 5.0 - inp.holding_period_years) if is_eligible else None

    # New cap: $15M if issued after July 4, 2025; else $10M
    per_taxpayer_cap = 15.0 if inp.issuance_date_post_july_2025 else 10.0
    basis_10x_cap = inp.investment_amount * 10.0
    exclusion_cap = min(per_taxpayer_cap, basis_10x_cap)

    # Rough gain estimate (assume 10x MOIC)
    estimated_gain = inp.investment_amount * 10.0
    excluded_gain = min(exclusion_cap, estimated_gain) if is_eligible and holding_satisfied else 0.0
    tax_saved_per_lp = excluded_gain * inp.lp_marginal_tax_rate
    total_lp_benefit = tax_saved_per_lp * inp.lp_count  # Note: each LP gets own exclusion

    notes = []
    if not is_eligible:
        notes.append("Company does not qualify for QSBS treatment based on provided criteria.")
    if not holding_satisfied:
        notes.append(
            f"5-year holding period not yet met ({inp.holding_period_years:.1f} years held). "
            f"{years_remaining:.1f} years remaining."
        )
    if inp.issuance_date_post_july_2025:
        notes.append("New $15M exclusion cap applies (post July 4, 2025 issuance).")
    else:
        notes.append("$10M exclusion cap applies. Check if TCJA 2025 provisions apply to this investment.")
    notes.append(
        "QSBS benefits flow through to LPs individually. Each LP can exclude up to the cap amount. "
        "Consult tax counsel for fund-specific structuring (e.g., SMLLCs, SPVs)."
    )

    return QSBSOutput(
        company_name=inp.company_name,
        is_eligible=is_eligible,
        eligibility_checks=checks,
        holding_period_satisfied=holding_satisfied,
        years_remaining_to_qualify=years_remaining,
        exclusion_cap_per_taxpayer=exclusion_cap,
        estimated_gain_excluded=excluded_gain,
        estimated_federal_tax_saved_per_lp=tax_saved_per_lp,
        estimated_total_lp_benefit=total_lp_benefit,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# 9. Anti-Dilution Analysis
# ---------------------------------------------------------------------------

def run_anti_dilution(inp: AntiDilutionInput) -> AntiDilutionOutput:
    """Compute anti-dilution adjustment: full ratchet vs. broad-based WA."""
    original_total_shares = inp.original_shares  # fully diluted

    if inp.anti_dilution_type == AntiDilutionType.NONE:
        adjusted_price = inp.original_price_per_share
        additional_shares = 0.0
        notes = "No anti-dilution protection — investor bears full dilution impact."

    elif inp.anti_dilution_type == AntiDilutionType.FULL_RATCHET:
        # Full ratchet: price resets to new round price
        adjusted_price = inp.down_round_price_per_share
        additional_shares = (
            inp.investor_preferred_shares * inp.original_price_per_share / inp.down_round_price_per_share
            - inp.investor_preferred_shares
        )
        notes = (
            "Full ratchet: conversion price resets to down-round price. "
            "Most punitive for founders and other shareholders."
        )

    else:  # BROAD_BASED_WA
        # Broad-based weighted average formula:
        # NCP = OCP × (A + B) / (A + C)
        # A = total shares outstanding before new round
        # B = shares that would have been issued at OCP
        # C = actual new shares issued at new price
        A = original_total_shares
        B = (inp.down_round_new_shares_issued * inp.down_round_price_per_share) / inp.original_price_per_share
        C = inp.down_round_new_shares_issued
        adjusted_price = inp.original_price_per_share * (A + B) / (A + C)
        additional_shares = (
            inp.investor_preferred_shares * inp.original_price_per_share / adjusted_price
            - inp.investor_preferred_shares
        )
        notes = (
            "Broad-based weighted average: conversion price adjusted proportionally to dilution. "
            "Standard in most term sheets; more founder-friendly than full ratchet."
        )

    # Economic impact (value transferred to anti-dilution beneficiary)
    value_transferred = additional_shares * inp.down_round_price_per_share

    new_total_shares = original_total_shares + inp.down_round_new_shares_issued + additional_shares
    effective_ownership = (inp.investor_preferred_shares + additional_shares) / new_total_shares

    return AntiDilutionOutput(
        company_name=inp.company_name if hasattr(inp, "company_name") else "Company",
        anti_dilution_type=inp.anti_dilution_type,
        original_price=inp.original_price_per_share,
        down_round_price=inp.down_round_price_per_share,
        adjusted_conversion_price=adjusted_price,
        additional_shares_issued=additional_shares,
        economic_impact=value_transferred,
        effective_ownership_pct_after=effective_ownership,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# 10. Bridge Round Analysis
# ---------------------------------------------------------------------------

def run_bridge_analysis(inp: BridgeRoundInput) -> BridgeRoundOutput:
    """Model a bridge / extension round from investor perspective."""
    dilution_from_bridge = (
        inp.bridge_amount / (inp.pre_bridge_valuation + inp.bridge_amount)
        if inp.pre_bridge_valuation > 0
        else 0.0
    )

    post_bridge_ownership = inp.current_ownership_pct * (1 - dilution_from_bridge)

    effective_conversion_price = inp.expected_next_round_valuation * (1 - inp.discount_rate)
    implied_discount = 1.0 - (effective_conversion_price / inp.expected_next_round_valuation)

    additional_runway = _runway_months(inp.bridge_amount, inp.bridge_amount / 18.0)  # rough

    notes = [
        f"Bridge converts at {imp_d:.0%} discount to Series A: ${effective_conversion_price:.0f}M valuation cap implied.".replace("imp_d", str(implied_discount)),
    ]
    notes[0] = (
        f"Bridge converts at {implied_discount:.0%} discount to next round: "
        f"${effective_conversion_price:.0f}M effective valuation at conversion."
    )

    if inp.interest_rate > 0:
        accrued_interest = inp.bridge_amount * inp.interest_rate * (inp.maturity_months / 12.0)
        notes.append(
            f"Interest accrues at {inp.interest_rate:.0%}/yr. "
            f"At maturity ({inp.maturity_months}mo), total obligation: "
            f"${inp.bridge_amount + accrued_interest:.2f}M."
        )

    rec = "participate" if inp.fund_is_participating else "monitor"
    if post_bridge_ownership > inp.current_ownership_pct * 0.95:
        rec = "participate — minimal ownership dilution from bridge"
    else:
        rec = f"participate — dilution limited to {dilution_from_bridge:.1%}; preserves relationship"

    return BridgeRoundOutput(
        company_name=inp.company_name,
        bridge_amount=inp.bridge_amount,
        instrument=inp.instrument,
        pre_bridge_ownership=inp.current_ownership_pct,
        post_bridge_ownership_if_convert=post_bridge_ownership,
        dilution_from_bridge=dilution_from_bridge,
        effective_conversion_price=effective_conversion_price,
        implied_discount_to_next_round=implied_discount,
        additional_runway_months=additional_runway,
        irr_if_participate=None,
        irr_if_pass=None,
        recommendation=rec,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Main Orchestrator
# ---------------------------------------------------------------------------

def run_vc_deal_evaluation(deal: VCDealInput, fund: FundProfile) -> VCDealOutput:
    """
    Full VC deal evaluation — the main entry point.

    Runs all Phase 1 computations:
    1. Ownership math
    2. 3-scenario return model
    3. Quick screen
    4. Waterfall (if cap table provided)
    5. IC memo
    6. Power law context
    """
    benchmarks = _load_benchmarks()

    # 1. Ownership math
    ownership = compute_ownership_math(
        check_size=deal.check_size,
        post_money=deal.post_money_valuation,
        stage=deal.stage,
        dilution=deal.dilution,
        fund_profile=fund,
        arr=deal.arr,
    )

    # 2. Scenarios
    bear, base, bull = compute_scenarios(deal, fund, ownership.exit_ownership_pct, benchmarks)

    # 3. Expected value
    ev = bear.gross_proceeds_to_fund * bear.probability + \
         base.gross_proceeds_to_fund * base.probability + \
         bull.gross_proceeds_to_fund * bull.probability

    expected_moic = ev / deal.check_size if deal.check_size > 0 else 0.0
    expected_irr = _irr(deal.check_size, ev, deal.expected_exit_years)

    # 4. Quick screen
    quick = compute_quick_screen(deal, fund, ownership, bear, base, bull, benchmarks)

    # 5. Waterfall (optional)
    waterfall = None
    if deal.liquidation_stack:
        waterfall = compute_waterfall(deal, base.exit_enterprise_value)

    # 6. IC Memo
    ic = build_ic_memo(deal, fund, ownership, bear, base, bull, ev, benchmarks)

    # 7. Ownership adequacy
    adequacy = _ownership_adequacy(ownership.entry_ownership_pct, fund.target_ownership_pct)

    # 8. Power law context
    # At 40% bear probability, a fund needs ~3 fund-returners out of 25 deals to 3x the fund
    base_x_fund = base.fund_contribution_x
    fund_returners_needed = (
        3.0 / base_x_fund if base_x_fund > 0 else float("inf")
    )
    power_law_note = (
        f"Your fund needs ~{fund_returners_needed:.0f} 'base-case' outcomes "
        f"(${base.exit_enterprise_value:.0f}M exits each returning {base_x_fund:.1f}x the fund) "
        f"to return 3x gross. With a {fund.target_initial_check_count}-company portfolio, "
        f"that's {fund_returners_needed/fund.target_initial_check_count:.0%} of deals needing to hit base. "
        f"Power law: the top 2-3 positions will likely generate 80%+ of returns."
    )

    # Flags and warnings
    flags = quick.flags[:]
    warnings: list[str] = []

    if deal.check_size < fund.target_initial_check_size * 0.5:
        warnings.append(
            f"Check size ${deal.check_size:.1f}M is well below fund average "
            f"${fund.target_initial_check_size:.1f}M — even outperformance won't move the needle."
        )

    if deal.arr == 0 and deal.revenue_ttm == 0:
        warnings.append("No revenue data provided — exit multiple analysis uses $10M revenue placeholder.")

    return VCDealOutput(
        company_name=deal.company_name,
        stage=deal.stage,
        vertical=deal.vertical,
        fund_size=fund.fund_size,
        check_size=deal.check_size,
        post_money=deal.post_money_valuation,
        ownership=ownership,
        bear_scenario=bear,
        base_scenario=base,
        bull_scenario=bull,
        expected_value=ev,
        expected_moic=expected_moic,
        expected_irr=expected_irr,
        quick_screen=quick,
        waterfall=waterfall,
        ic_memo=ic,
        power_law_note=power_law_note,
        ownership_adequacy=adequacy,
        vertical_benchmarks_used=benchmarks.get("verticals", {}).get(deal.vertical.value, {}),
        flags=flags,
        warnings=warnings,
        computation_notes=[],
    )
