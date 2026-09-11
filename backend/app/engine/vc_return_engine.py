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
from .benchmark_registry import BenchmarkView, evidence_analysis, policy

import logging
import math
import os
from typing import Optional

from .vc_scenarios import build_path, effective_deal, path_ownership

from .vc_fund_models import (
    AntiDilutionInput, AntiDilutionOutput, AntiDilutionType,
    BridgeRoundInput, BridgeRoundOutput,
    CarryStructure,
    DealComparisonEntry, DealComparisonOutput,
    DilutionAssumptions,
    FundCashflow,
    FundIRRInput, FundIRROutput,
    FundProfile,
    GPCarryInput, GPCarryOutput,
    ICMemoFinancials,
    OwnershipMath,
    PortfolioConstructionStats, PortfolioInput, PortfolioOutput, PortfolioPosition,
    PreferenceType,
    ProRataAnalysis,
    QSBSInput, QSBSOutput,
    QuickScreenResult,
    SAFEConversionInput, SAFEConversionOutput, SAFEConversionResult,
    VCDealInput, VCDealOutput,
    VCScenario,
    VCStage,
    WaterfallDistribution,
)

logger = logging.getLogger(__name__)

_DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "vc_benchmarks.json")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BENCHMARKS_CACHE: Optional[dict] = None


def _load_benchmarks():
    return BenchmarkView("vc")


def _irr(investment: float, proceeds: float, years: float) -> float:
    """Compute IRR for a single cash-in / cash-out scenario."""
    if investment <= 0 or proceeds <= 0 or years <= 0:
        return 0.0
    return (proceeds / investment) ** (1.0 / years) - 1.0


def _npv(rate: float, cashflows: list[tuple[float, float]]) -> float:
    """Compute NPV. cashflows = [(year, amount), ...]"""
    return sum(cf / (1 + rate) ** yr for yr, cf in cashflows)


def _xirr(investment: float, proceeds: float, years: float) -> float:
    """Alias of :func:`_irr` kept for API compatibility.

    Despite the name, this is NOT an irregular-cashflow XIRR — it handles the
    single cash-in / single cash-out case only (closed form, no search).
    For true multi-cashflow IRR see ``run_fund_irr_analysis``.
    """
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
    future_rounds: Optional[list[str]] = None,
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

    future_rounds = stage_sequence.get(stage, []) if future_rounds is None else future_rounds
    for rnd in future_rounds:
        d = dilution_map.get(rnd, 0.0)
        # also include option pool expansion
        effective_dilution = 1 - (1 - d) * (1 - dilution.option_pool_expansion)
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

    # Fund returner thresholds — GROSS: the exit EV at which this position's
    # gross proceeds equal target_x × fund size (before fees and carry).
    def fund_returner_exit(target_x: float) -> float:
        target_proceeds = fund_profile.fund_size * target_x
        if exit_pct <= 0:
            return float("inf")
        return target_proceeds / exit_pct

    # NET variant: exit EV at which LPs receive target_x × fund size AFTER
    # carry. Required gross distribution D solves:
    #   D − carry × max(0, D − check) = target_x × fund_size
    #   → D = (target_x × fund_size − carry × check) / (1 − carry)
    # Management fees are implicitly covered because the target is stated on
    # committed capital (which is what funds the fees); no separate fee term
    # is added on top.
    def fund_returner_exit_net(target_x: float) -> float:
        if exit_pct <= 0:
            return float("inf")
        target_net = fund_profile.fund_size * target_x
        c = fund_profile.carry_pct
        if c < 1.0 and target_net > check_size:
            gross_needed = (target_net - c * check_size) / (1.0 - c)
        else:
            gross_needed = target_net
        return gross_needed / exit_pct

    fr_1x = fund_returner_exit(1.0)
    fr_3x = fund_returner_exit(3.0)
    fr_5x = fund_returner_exit(5.0)
    fr_1x_net = fund_returner_exit_net(1.0)
    fr_3x_net = fund_returner_exit_net(3.0)
    fr_5x_net = fund_returner_exit_net(5.0)

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
        fund_returner_1x_exit_net=fr_1x_net,
        fund_returner_3x_exit_net=fr_3x_net,
        fund_returner_5x_exit_net=fr_5x_net,
        exit_values_tested=[float(e) for e in test_exits],
        gross_proceeds_at_exits=gross_at_exits,
        fund_contribution_at_exits=contribution_at_exits,
        required_arr_multiple_for_1x_fund=arr_multiple_1x,
        required_arr_multiple_for_3x_fund=arr_multiple_3x,
    )


# ---------------------------------------------------------------------------
# 2. Scenario Engine
# ---------------------------------------------------------------------------

GROWTH_DECAY_FACTOR = 0.70   # each year, growth rate decays to 70% of prior year
TERMINAL_GROWTH_FLOOR = 0.15  # growth never decays below 15% (healthy SaaS terminal pace)
ARR_PROJECTION_CAP_X = 100.0  # hard guardrail: projected ARR ≤ 100x current ARR


def _project_arr(current_arr: float, initial_growth: float, years: int) -> float:
    """Project ARR forward with annual growth-rate decay.

    Startups do not compound a constant hypergrowth rate for 7+ years; growth
    fades as base revenue scales. We decay the growth rate geometrically each
    year (g_{t+1} = g_t × GROWTH_DECAY_FACTOR) toward a terminal floor of
    TERMINAL_GROWTH_FLOOR. The result is capped at ARR_PROJECTION_CAP_X ×
    current ARR — an aggressive but bounded guardrail for long horizons.
    """
    arr = current_arr
    g = max(-1.0, initial_growth)
    for _ in range(max(0, years)):
        arr *= (1.0 + g)
        g = g * policy('growth_decay') if g < 0 else max(TERMINAL_GROWTH_FLOOR, g * policy('growth_decay'))
    return min(arr, current_arr * ARR_PROJECTION_CAP_X)


def _stage_scenario_weights(stage: VCStage, benchmarks: dict) -> tuple[float, float, float]:
    """Derive (bear, base, bull) probabilities for the entry stage.

    Bear is the FAILURE branch (write-off / near-total loss). Its probability
    is seeded from stage_transition_probabilities in vc_benchmarks.json:
      - seed:      seed_to_failure directly (Carta/Correlation Ventures ~0.62)
      - pre-seed:  fail the pre-seed→seed graduation OR fail later as a seed
                   company: 1 − P(graduate) × (1 − P(seed failure))
      - later stages: heuristic loss rates anchored on Correlation Ventures
        loss-rate curves (loss rates fall as companies mature).
    Bull is the power-law tail: 25% of the survival mass, capped at 15%.
    Base absorbs the remainder.
    """
    p_fail = policy('failure_rates', stage.value)

    p_fail = min(0.85, max(0.05, p_fail))
    p_bull = min(policy('bull_probability_cap'), policy('bull_survival_share') * (1.0 - p_fail))
    p_base = max(0.0, 1.0 - p_fail - p_bull)
    return p_fail, p_base, p_bull


def compute_scenarios(
    deal: VCDealInput,
    fund: FundProfile,
    exit_ownership_pct: float,
    benchmarks: dict,
) -> tuple[VCScenario, VCScenario, VCScenario]:
    """
    Build bear/base/bull scenarios using vertical benchmarks or overrides.

    Exit multiples are ARR multiples (or revenue multiples for non-SaaS).

    Scenario weights are derived per entry stage from the benchmark stage
    transition/failure probabilities (see _stage_scenario_weights):
      - Bear = failure mass (write-off / near-total loss)
      - Bull = power-law tail of the survival mass
      - Base = the remainder
    """
    deal = effective_deal(deal)
    multiples = benchmarks.get('verticals', {}).get(deal.vertical.value, {}).get('exit_multiples', {})
    weights = _stage_scenario_weights(deal.stage, benchmarks)
    result = []
    for label, weight, default in zip(['Bear', 'Base', 'Bull'], weights, [0.0, 5.0, 12.0]):
        override = getattr(deal, label.lower() + '_exit_multiple_arr')
        multiple = override if override is not None else (0.0 if label == 'Bear' else multiples.get(label.lower(), default))
        result.append(build_path(label, weight, multiple, deal, fund))
    return tuple(result)


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
    """Single-screen pass/look-deeper/strong-interest recommendation.

    Anchored on (a) the bull case's fund contribution — can this deal move the
    needle for the fund if it works — and (b) the probability-weighted expected
    MOIC across the corrected distribution (which includes the failure mass in
    the bear branch).
    """
    # Structured flags: (code, message). Codes drive the recommendation logic;
    # messages are surfaced to the UI. Avoids brittle substring matching.
    structured_flags: list[tuple[str, str]] = []
    entry_pct = ownership.entry_ownership_pct
    exit_pct = ownership.exit_ownership_pct

    # Ownership check
    adequacy = _ownership_adequacy(entry_pct, fund.target_ownership_pct)
    if adequacy == "thin":
        structured_flags.append((
            "thin_ownership",
            f"Ownership thin: {entry_pct:.1%} entry vs {fund.target_ownership_pct:.1%} target",
        ))

    # Check size vs target
    target_check = fund.target_initial_check_size
    if target_check > 0 and deal.check_size > target_check * 1.5:
        structured_flags.append((
            "oversized_check",
            f"Check size ${deal.check_size:.1f}M exceeds target ${target_check:.1f}M by >50%",
        ))

    # Valuation vs benchmark
    vdata = benchmarks.get("verticals", {}).get(deal.vertical.value, {})
    stage_data = vdata.get(deal.stage.value, {})
    median_post = stage_data.get("median_post_money_usd_m", None)
    if median_post and deal.post_money_valuation > median_post * 1.5:
        structured_flags.append((
            "rich_valuation",
            f"Valuation ${deal.post_money_valuation:.0f}M is >1.5x median ${median_post:.0f}M for "
            f"{deal.stage.value} {deal.vertical.value}",
        ))

    # Fund returner check (base surviving case vs gross 1x-fund threshold)
    fr_threshold = ownership.fund_returner_1x_exit
    if base.exit_enterprise_value < fr_threshold:
        structured_flags.append((
            "below_fund_returner",
            f"Base case exit (${base.exit_enterprise_value:.0f}M) below fund-returner "
            f"threshold (${fr_threshold:.0f}M)",
        ))

    # Runway
    if deal.burn_rate_monthly > 0 and deal.cash_on_hand > 0:
        runway = _runway_months(deal.cash_on_hand, deal.burn_rate_monthly)
        if runway and runway < 12:
            structured_flags.append(("short_runway", f"Short runway: {runway:.0f} months"))

    # ARR multiple at entry
    if deal.arr > 0:
        arr_multiple = deal.post_money_valuation / deal.arr
        benchmark_arr_mult = stage_data.get("median_arr_multiple", None)
        if benchmark_arr_mult and arr_multiple > benchmark_arr_mult * 1.5:
            structured_flags.append((
                "rich_arr_multiple",
                f"Entry ARR multiple {arr_multiple:.0f}x vs benchmark {benchmark_arr_mult:.0f}x "
                f"(paying {arr_multiple/benchmark_arr_mult:.1f}x median)",
            ))

    flags = [msg for _, msg in structured_flags]

    # Recommendation — probability-weighted expected MOIC (includes failure mass)
    # plus bull-case fund contribution.
    expected_moic = (
        bear.probability * bear.gross_moic
        + base.probability * base.gross_moic
        + bull.probability * bull.gross_moic
    )
    bull_fund_contribution = bull.fund_contribution_x

    serious_codes = {"thin_ownership", "below_fund_returner", "short_runway"}
    serious_flags = len([c for c, _ in structured_flags if c in serious_codes])

    if (
        bull_fund_contribution >= 1.0
        and expected_moic >= 3.0
        and adequacy in ("strong", "acceptable")
        and serious_flags == 0
    ):
        rec = "strong_interest"
        rec_rationale = (
            f"Bull case returns {bull_fund_contribution:.1f}x the fund, probability-weighted "
            f"expected MOIC {expected_moic:.1f}x (after {bear.probability:.0%} failure mass), "
            f"ownership adequate at {entry_pct:.1%} entry, no blocking flags. Merits serious diligence."
        )
    elif (bull_fund_contribution >= 0.5 or expected_moic >= 2.0) and serious_flags <= 1:
        rec = "look_deeper"
        rec_rationale = (
            f"Bull case contributes {bull_fund_contribution:.1f}x of the fund; probability-weighted "
            f"expected MOIC {expected_moic:.1f}x. "
            f"{'Address flags before proceeding.' if flags else 'Conduct standard diligence.'}"
        )
    else:
        rec = "pass"
        rec_rationale = (
            f"Even in the bull case this deal contributes only {bull_fund_contribution:.1f}x of the "
            f"fund, and probability-weighted expected MOIC is {expected_moic:.1f}x after the "
            f"{bear.probability:.0%} failure probability — insufficient given fund math"
            f"{f', with {serious_flags} blocking flag(s)' if serious_flags else ''}. "
            "Pass or revisit at better terms."
        )

    if not all(s.available for s in (bear, base, bull)):
        rec = 'insufficient_inputs'
        rec_rationale = 'Return-based screening is unavailable. Supply explicit exit assumptions and any missing cap-table ownership.'
        flags = list(dict.fromkeys(n for scenario in (bear, base, bull) if not scenario.available for n in scenario.notes))
    elif any(s.illustrative for s in (bear, base, bull)):
        rec_rationale = 'Illustrative scenarios supplied by the user. ' + rec_rationale
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

    Mechanics:
    - Preferences are paid senior → junior; a class that converts to common
      forfeits its preference (which returns to the residual pool).
    - The residual is shared pro-rata (on as-converted ownership) among common,
      converted classes, and participating classes.
    - Convert/stay decisions are re-solved to a fixed point: each class's
      decision is evaluated against the distribution implied by everyone
      else's current decision (senior → junior), iterating until stable.
    - Capped participating classes hold the conversion option too:
      gets = max(min(pref + participation, cap), as-converted value).
    - As-converted ownership uses LiquidationPreference.ownership_pct when
      provided; otherwise falls back to dollar-proportional estimation
      (invested / total invested, scaled by 1 − common%) with a note.
    """
    stack = sorted(deal.liquidation_stack, key=lambda x: x.seniority)
    n = len(stack)
    notes: list[str] = []
    common_fraction = deal.common_shares_pct

    if n == 0:
        return WaterfallDistribution(
            exit_ev=exit_ev, share_classes=[], common_gets=max(0.0, exit_ev),
            total_distributed=max(0.0, exit_ev), investor_total=0.0,
            investor_moic=0.0, conversion_was_optimal=False, notes=notes,
        )

    total_invested = sum(p.invested_amount for p in stack) or 1.0
    fracs: list[float] = []
    used_fallback = False
    for p in stack:
        if p.ownership_pct is not None:
            fracs.append(p.ownership_pct)
        else:
            fracs.append((p.invested_amount / total_invested) * (1 - common_fraction))
            used_fallback = True
    if used_fallback:
        notes.append(
            "As-converted ownership for one or more classes was estimated dollar-proportionally "
            "from invested amounts (ownership_pct not provided). This overweights late, expensive "
            "money — provide ownership_pct per share class for exact conversion math."
        )

    def _distribute(convert: list[bool]) -> tuple[list[float], list[float], float]:
        """Given convert decisions, return (pref_paid, gets, common_gets)."""
        remaining = exit_ev
        pref_paid = [0.0] * n
        for seniority in sorted({p.seniority for p in stack}):
            peers = [i for i, p in enumerate(stack) if p.seniority == seniority and not convert[i]]
            claims = sum(stack[i].invested_amount * stack[i].preference_multiple for i in peers)
            available = min(remaining, claims)
            for i in peers:
                pref_paid[i] = available * stack[i].invested_amount * stack[i].preference_multiple / claims
            remaining -= available
        residual = max(0.0, remaining)

        # Residual pool participants: common + converted classes + participating classes
        weights = [0.0] * n
        for i, p in enumerate(stack):
            if convert[i]:
                weights[i] = fracs[i]
            elif p.preference_type in (PreferenceType.PARTICIPATING,
                                       PreferenceType.PARTICIPATING_CAPPED):
                weights[i] = fracs[i]
        # Allocate residual across all eligible holders, repeatedly redistributing
        # capped participation to the remaining holders (including preferred).
        gets = pref_paid.copy()
        caps = [float('inf')] * n
        for i, p in enumerate(stack):
            if not convert[i] and p.preference_type == PreferenceType.PARTICIPATING_CAPPED:
                caps[i] = p.invested_amount * (p.participation_cap if p.participation_cap is not None else 3.0)
        common_gets = 0.0
        active = {i for i, w in enumerate(weights) if w > 0 and gets[i] < caps[i]}
        while residual > 1e-12:
            denominator = common_fraction + sum(weights[i] for i in active)
            if denominator <= 0:
                common_gets += residual
                break
            clipped = {i for i in active if residual * weights[i] / denominator > caps[i] - gets[i] + 1e-12}
            if clipped:
                for i in clipped:
                    payment = max(0.0, caps[i] - gets[i])
                    gets[i] += payment
                    residual -= payment
                active -= clipped
            else:
                for i in active:
                    gets[i] += residual * weights[i] / denominator
                common_gets += residual * common_fraction / denominator
                break
        return pref_paid, gets, common_gets

    # Fixed-point convert/stay solve (senior → junior each sweep).
    # Uncapped participating never converts (pref + participation dominates).
    convert = [False] * n
    for _ in range(2 * n + 4):
        changed = False
        for i, p in enumerate(stack):
            if p.preference_type == PreferenceType.PARTICIPATING:
                continue
            _, gets_cur, _ = _distribute(convert)
            alt = convert.copy()
            alt[i] = not alt[i]
            _, gets_alt, _ = _distribute(alt)
            if gets_alt[i] > gets_cur[i] + 1e-9:
                convert = alt
                changed = True
        if not changed:
            break

    pref_paid, gets, common_gets = _distribute(convert)

    distributions: list[dict] = []
    for i, p in enumerate(stack):
        # Hypothetical as-converted value under the final decision set
        if convert[i]:
            conversion_value = gets[i]
        else:
            alt = convert.copy()
            alt[i] = True
            _, gets_alt, _ = _distribute(alt)
            conversion_value = gets_alt[i]
        distributions.append({
            "share_class": p.share_class,
            "type": p.preference_type.value,
            "invested_amount": p.invested_amount,
            "preference_amount": p.invested_amount * p.preference_multiple,
            "preference_multiple": p.preference_multiple,
            "liquidation_payout": pref_paid[i],
            "conversion_value": conversion_value,
            "gets": gets[i],
            "converted": convert[i],
        })

    total_distributed = sum(gets) + common_gets

    # Find "our" position (first preferred, or most junior)
    investor_index = next((i for i, p in enumerate(stack) if p.share_class == deal.investor_share_class), 0)
    if not deal.investor_share_class:
        notes.append('Standalone waterfall displays the first preferred class; select investor_share_class for scenario reconciliation.')
    investor_total = distributions[investor_index]["gets"]
    investor_moic = investor_total / stack[investor_index].invested_amount if stack[investor_index].invested_amount > 0 else 0.0

    return WaterfallDistribution(
        exit_ev=exit_ev,
        share_classes=distributions,
        common_gets=common_gets,
        total_distributed=total_distributed,
        investor_total=investor_total,
        investor_moic=investor_moic,
        conversion_was_optimal=distributions[investor_index]["converted"],
        notes=notes,
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
    Should you exercise your pro-rata right at the next round?

    Legs:
    - PASS: keep the current diluted trajectory. Exit ownership is
      ownership.exit_ownership_pct, which ALREADY includes all future round
      dilution — no additional dilution is applied.
    - EXERCISE: buying pro-rata at the next round offsets that round's
      new-money dilution (the option-pool refresh still dilutes everyone),
      so maintained exit % = exit % with the next round's new-money dilution
      backed out.

    Exit EVs and probabilities reuse the main scenario engine (bear = failure
    mass, base/bull = growth-decayed projections) rather than ad-hoc multiples.

    Decision rule: exercise if the expected incremental proceeds exceed the
    pro-rata check; partial if positive but below the check; else pass.
    """
    if next_round_valuation <= 0 or pro_rata_check <= 0:
        raise ValueError('Positive next-round post-money valuation and follow-on check are required')
    if deal.liquidation_stack or any(v.exit_cap_table for v in deal.scenario_assumptions.values()):
        raise ValueError('Pro-rata preference analysis requires separately projected capitalization for each leg; use explicit deal scenarios')
    if not ownership.dilution_stack:
        raise ValueError('Select a future financing round before analyzing pro-rata')
    if any(v.future_rounds is not None and v.future_rounds != deal.future_rounds for v in deal.scenario_assumptions.values()):
        raise ValueError('Pro-rata requires a common financing path across scenarios')
    exit_pct_pass = ownership.exit_ownership_pct

    # Maintain leg: back out the NEXT round's new-money dilution (pro-rata does
    # not offset the option-pool refresh, which dilutes all shareholders).
    if ownership.dilution_stack:
        next_round = ownership.dilution_stack[0]
        pool = deal.dilution.option_pool_expansion
        round_only_dilution = 1 - (1 - next_round["dilution_pct"]) / (1 - pool)
    else:
        round_only_dilution = 0.0
    later_dilution = 1.0
    for item in ownership.dilution_stack[1:]:
        later_dilution *= 1 - item['dilution_pct']
    maintained_pct = exit_pct_pass + (pro_rata_check / next_round_valuation) * later_dilution
    if maintained_pct > 1:
        raise ValueError('Follow-on check implies more than 100% ownership')

    reserve_after_pct = (
        (fund.reserve_pool - pro_rata_check) / fund.reserve_pool
        if fund.reserve_pool > 0
        else 0.0
    )

    # Reuse the scenario engine for exit EVs and probabilities
    bear0, base0, bull0 = compute_scenarios(deal, fund, exit_pct_pass, benchmarks)

    if not all(s.available for s in (bear0, base0, bull0)):
        raise ValueError('Explicit exit assumptions are required before pro-rata return analysis')
    exercise_scenarios: list[VCScenario] = []
    pass_scenarios: list[VCScenario] = []
    exit_yr = deal.expected_exit_years

    for sc in (bear0, base0, bull0):
        exit_ev = sc.exit_enterprise_value
        exit_yr = sc.exit_year

        # With exercise (maintain ownership through the next round)
        cost_exercise = deal.check_size + pro_rata_check
        proceeds_exercise = sc.exit_equity_value * maintained_pct
        net_exercise = _carry_adj_proceeds(proceeds_exercise, cost_exercise,
                                           fund.carry_pct, fund.hurdle_rate, exit_yr)
        exercise_scenarios.append(VCScenario(
            label=f"{sc.label} (exercise)",
            probability=sc.probability,
            exit_year=exit_yr,
            exit_multiple_arr=sc.exit_multiple_arr,
            exit_enterprise_value=exit_ev,
            gross_proceeds_to_fund=proceeds_exercise,
            net_proceeds_to_fund=net_exercise,
            gross_moic=proceeds_exercise / cost_exercise if cost_exercise > 0 else 0.0,
            net_moic=net_exercise / cost_exercise if cost_exercise > 0 else 0.0,
            gross_irr=_irr(cost_exercise, proceeds_exercise, exit_yr) if proceeds_exercise > 0 else -1.0,
            net_irr=_irr(cost_exercise, net_exercise, exit_yr) if net_exercise > 0 else -1.0,
            fund_contribution_x=proceeds_exercise / fund.fund_size,
            outcome_description=f"Pro-rata exercised at ${next_round_valuation:.0f}M valuation",
        ))

        # Without exercise (already-diluted exit trajectory as-is)
        proceeds_pass = sc.exit_equity_value * exit_pct_pass
        net_pass = _carry_adj_proceeds(proceeds_pass, deal.check_size,
                                       fund.carry_pct, fund.hurdle_rate, exit_yr)
        pass_scenarios.append(VCScenario(
            label=f"{sc.label} (pass)",
            probability=sc.probability,
            exit_year=exit_yr,
            exit_multiple_arr=sc.exit_multiple_arr,
            exit_enterprise_value=exit_ev,
            gross_proceeds_to_fund=proceeds_pass,
            net_proceeds_to_fund=net_pass,
            gross_moic=proceeds_pass / deal.check_size if deal.check_size > 0 else 0.0,
            net_moic=net_pass / deal.check_size if deal.check_size > 0 else 0.0,
            gross_irr=_irr(deal.check_size, proceeds_pass, exit_yr) if proceeds_pass > 0 else -1.0,
            net_irr=_irr(deal.check_size, net_pass, exit_yr) if net_pass > 0 else -1.0,
            fund_contribution_x=proceeds_pass / fund.fund_size,
            outcome_description=f"Diluted trajectory: {exit_pct_pass:.1%} ownership at exit",
        ))

    ev_exercise = sum(s.gross_proceeds_to_fund * s.probability for s in exercise_scenarios)
    ev_pass = sum(s.gross_proceeds_to_fund * s.probability for s in pass_scenarios)
    incremental_value = ev_exercise - ev_pass

    # Sanity-check the pro-rata check size: it should approximate
    # current ownership % × next-round new money (new money ≈ post-money ×
    # round dilution fraction).
    size_warning = " Follow-on ownership is check / next-round post-money, diluted only by later rounds. IRRs conservatively place both checks at time zero."
    if round_only_dilution > 0 and next_round_valuation > 0 and pro_rata_check > 0:
        implied_round_size = next_round_valuation * round_only_dilution
        expected_check = ownership.entry_ownership_pct * implied_round_size
        if expected_check > 0 and abs(pro_rata_check - expected_check) / expected_check > 0.5:
            size_warning += (
                f" Note: pro-rata check ${pro_rata_check:.2f}M deviates >50% from the implied "
                f"pro-rata amount ${expected_check:.2f}M "
                f"(≈{ownership.entry_ownership_pct:.1%} of an implied ${implied_round_size:.1f}M round)."
            )

    if incremental_value > pro_rata_check:
        rec = "exercise"
        rec_rationale = (
            f"Expected incremental proceeds from maintaining ownership "
            f"(${incremental_value:.1f}M) exceed the ${pro_rata_check:.1f}M pro-rata check. "
            f"Exercise if reserve available.{size_warning}"
        )
    elif incremental_value > 0:
        rec = "partial"
        rec_rationale = (
            f"Expected incremental proceeds (${incremental_value:.1f}M) are positive but below "
            f"the ${pro_rata_check:.1f}M check. Consider partial exercise to conserve "
            f"reserves.{size_warning}"
        )
    else:
        rec = "pass"
        rec_rationale = (
            f"Expected incremental proceeds (${incremental_value:.1f}M) do not justify "
            f"${pro_rata_check:.1f}M of reserve deployment.{size_warning}"
        )

    return ProRataAnalysis(
        company_name=deal.company_name,
        next_round_valuation=next_round_valuation,
        pro_rata_amount=pro_rata_check,
        maintained_ownership_pct=maintained_pct,
        diluted_ownership_if_pass=exit_pct_pass,
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

    # Residual fair value: only positions still held. A fair_value of 0.0 is a
    # real mark (written off), so use `is not None`, never `or cost_basis`.
    # Exited / written-off positions carry no residual value — exit proceeds
    # belong in DPI, not RVPI.
    residual_positions = [p for p in positions if p.status in ("active", "partially_exited")]
    total_fv = sum(
        (p.fair_value if p.fair_value is not None else p.cost_basis)
        for p in residual_positions
    )
    total_realized = sum(p.realized_proceeds for p in positions)

    # TVPI/DPI/RVPI are NET-style multiples on called capital INCLUDING the
    # management-fee load (consistent with run_fund_irr_analysis, which counts
    # fee calls in total_called). unrealized_tvpi below remains the GROSS
    # fair-value-on-cost multiple.
    called_capital = total_deployed + fund.total_management_fees
    dpi = total_realized / called_capital if called_capital > 0 else 0.0
    rvpi = total_fv / called_capital if called_capital > 0 else 0.0
    tvpi = dpi + rvpi

    # Reserve adequacy: comparing follow-on capital ALLOCATED vs the reserve
    # pool. Allocations above 110% of the pool mean the fund has promised more
    # follow-on than it holds — over-committed (not "over-reserved").
    total_reserve_alloc = sum(p.reserve_allocated for p in positions)
    if total_reserve_alloc <= fund.reserve_pool * 0.90:
        reserve_adequacy = "adequate"
    elif total_reserve_alloc <= fund.reserve_pool * 1.10:
        reserve_adequacy = "tight"
    else:
        reserve_adequacy = "over-committed"

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
        unrealized_tvpi=(total_fv / total_cost if total_cost > 0 else 0.0),
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

    if stats.reserve_adequacy == "over-committed":
        alerts.append("Follow-on allocations exceed the reserve pool — fund is over-committed")
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

    OBBBA (July 4, 2025) changes for stock issued after that date:
      - Per-taxpayer exclusion cap raised to $15M (from $10M)
      - Gross-asset test threshold raised to $75M (from $50M)
      - Tiered exclusion by holding period: 50% at 3 years, 75% at 4 years,
        100% at 5 years (pre-July-2025 stock remains 5yr / 100%-or-nothing,
        assuming post-Sept-2010 acquisition).

    Exclusion cap per §1202(b)(1) is the GREATER of the per-taxpayer dollar
    cap and 10× the taxpayer's basis in the stock.

    LP-level benefit: each LP is a separate taxpayer with an allocable share
    of the fund's gain and basis. We allocate gain and basis pro-rata across
    lp_count, apply the per-taxpayer caps at the LP level, then aggregate.

    Tax rate assumption: the benefit of exclusion is measured against the
    federal LTCG rate of 23.8% (20% LTCG + 3.8% NIIT) — the tax an LP would
    otherwise pay on the gain. (The 28% §1202 collectibles-style rate + NIIT
    applies only to the NON-excluded portion of §1202 stock gain, so it does
    not apply to the excluded amount modeled here.)
    """
    post_obbba = inp.issuance_date_post_july_2025
    asset_threshold = 75.0 if post_obbba else 50.0
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
            "name": f"Assets ≤ ${asset_threshold:.0f}M at Issuance",
            "passed": inp.assets_at_issuance_under_50m,
            "note": (
                f"Aggregate gross assets must be ≤${asset_threshold:.0f}M at the time of stock issuance "
                f"({'OBBBA post-July-2025 threshold' if post_obbba else 'pre-OBBBA threshold'})."
            ),
        },
        {
            "name": "Original Issuance",
            "passed": inp.original_issuance,
            "note": "Shares must be acquired directly from the corporation (not secondary market).",
        },
    ]

    is_eligible = all(c["passed"] for c in checks)

    # Holding-period tiering
    h = inp.holding_period_years
    if post_obbba:
        if h >= 5.0:
            exclusion_pct = 1.0
        elif h >= 4.0:
            exclusion_pct = 0.75
        elif h >= 3.0:
            exclusion_pct = 0.50
        else:
            exclusion_pct = 0.0
    else:
        exclusion_pct = 1.0 if h >= 5.0 else 0.0

    holding_satisfied = exclusion_pct > 0.0
    # Years remaining to reach the FULL 100% exclusion
    years_remaining = max(0.0, 5.0 - h) if is_eligible else None

    # Per-taxpayer dollar cap: $15M post-OBBBA, $10M before.
    # §1202(b)(1): exclusion cap = GREATER of dollar cap and 10× basis.
    per_taxpayer_dollar_cap = 15.0 if post_obbba else 10.0
    exclusion_cap = max(per_taxpayer_dollar_cap, inp.investment_amount * 10.0)

    # Rough gain estimate (assume 10x MOIC on the position)
    estimated_gain = inp.investment_amount * 10.0

    # Per-LP allocation: each LP is a separate taxpayer.
    lp_count = max(1, inp.lp_count)
    lp_allocable_gain = estimated_gain / lp_count
    lp_allocable_basis = inp.investment_amount / lp_count
    lp_cap = max(per_taxpayer_dollar_cap, lp_allocable_basis * 10.0)
    lp_excluded_gain = (
        min(lp_cap, lp_allocable_gain) * exclusion_pct
        if (is_eligible and holding_satisfied)
        else 0.0
    )
    excluded_gain = lp_excluded_gain * lp_count  # aggregate across LPs
    tax_saved_per_lp = lp_excluded_gain * inp.lp_marginal_tax_rate
    total_lp_benefit = tax_saved_per_lp * lp_count

    notes = []
    if not is_eligible:
        notes.append("Company does not qualify for QSBS treatment based on provided criteria.")
    if not holding_satisfied:
        min_holding = 3.0 if post_obbba else 5.0
        notes.append(
            f"Minimum holding period not yet met ({h:.1f} years held; "
            f"{min_holding:.0f} years required for {'partial' if post_obbba else 'any'} exclusion). "
            f"{years_remaining:.1f} years remaining to the full 100% exclusion."
            if years_remaining is not None else
            f"Minimum holding period not yet met ({h:.1f} years held)."
        )
    elif exclusion_pct < 1.0:
        notes.append(
            f"OBBBA tiered exclusion: {exclusion_pct:.0%} of the capped gain is excludable at "
            f"{h:.1f} years held (75% at 4 years, 100% at 5 years)."
        )
    if post_obbba:
        notes.append(
            "OBBBA (post-July 4, 2025 issuance): $15M per-taxpayer cap, $75M gross-asset "
            "threshold, and 50/75/100% tiered exclusion at 3/4/5-year holding periods."
        )
    else:
        notes.append(
            "Pre-OBBBA stock: $10M per-taxpayer cap (or 10× basis if greater), $50M gross-asset "
            "threshold, and 100% exclusion only after a full 5-year holding period."
        )
    notes.append(
        "Tax saved is measured against the 23.8% federal LTCG rate (20% + 3.8% NIIT) an LP would "
        "otherwise owe on the excluded gain; the 28%+NIIT §1202 rate applies only to any "
        "non-excluded portion. State conformity varies."
    )
    notes.append(
        "QSBS benefits flow through to LPs individually. Each LP applies their own per-taxpayer "
        "cap to their allocable share of gain and basis. Consult tax counsel for fund-specific "
        "structuring (e.g., SMLLCs, SPVs)."
    )

    return QSBSOutput(
        company_name=inp.company_name,
        is_eligible=is_eligible,
        eligibility_checks=checks,
        holding_period_satisfied=holding_satisfied,
        years_remaining_to_qualify=years_remaining,
        exclusion_cap_per_taxpayer=exclusion_cap,
        exclusion_pct_applicable=exclusion_pct,
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
        company_name=inp.company_name,
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
    """Model a bridge / extension round from investor perspective.

    Dilution mechanics:
    - Equity bridge: dilutes immediately at the pre-bridge valuation.
    - SAFE / convertible bridge: dilutes at CONVERSION into the next round at
      the discounted price. The converting amount includes accrued interest
      for convertible notes. Dilution = conversion_amount /
      (effective_conversion_valuation + conversion_amount).

    Runway: bridge_amount / monthly_burn when the company's burn is provided;
    None otherwise (never fabricated).

    Recommendation compares the economics of participating (buying at an
    effective discount to the expected next round, plus avoided dilution on
    the existing stake) against the incremental check required.
    """
    effective_conversion_price = inp.expected_next_round_valuation * (1 - inp.discount_rate)
    implied_discount = (
        1.0 - (effective_conversion_price / inp.expected_next_round_valuation)
        if inp.expected_next_round_valuation > 0 else 0.0
    )

    # Accrued interest converts alongside principal for convertible notes
    accrued_interest = 0.0
    if inp.instrument == "convertible_note" and inp.interest_rate > 0:
        accrued_interest = inp.bridge_amount * inp.interest_rate * (inp.maturity_months / 12.0)
    conversion_amount = inp.bridge_amount + accrued_interest

    if inp.instrument == "equity":
        dilution_from_bridge = (
            inp.bridge_amount / (inp.pre_bridge_valuation + inp.bridge_amount)
            if inp.pre_bridge_valuation > 0
            else 0.0
        )
    else:
        # SAFE / convertible: converts into the next round at the discounted
        # valuation; bridge holders take conversion_amount / effective post.
        denom = effective_conversion_price + conversion_amount
        dilution_from_bridge = conversion_amount / denom if denom > 0 else 0.0

    post_bridge_ownership = inp.current_ownership_pct * (1 - dilution_from_bridge)

    # Real runway from the company's actual burn — None when unknown
    additional_runway = (
        inp.bridge_amount / inp.monthly_burn
        if (inp.monthly_burn is not None and inp.monthly_burn > 0)
        else None
    )

    notes = [
        f"Bridge converts at {implied_discount:.0%} discount to next round: "
        f"${effective_conversion_price:.0f}M effective valuation at conversion."
    ]
    if accrued_interest > 0:
        notes.append(
            f"Interest accrues at {inp.interest_rate:.0%}/yr. At maturity ({inp.maturity_months}mo), "
            f"${conversion_amount:.2f}M (principal + ${accrued_interest:.2f}M accrued interest) "
            "converts at the discounted price."
        )
    if additional_runway is None:
        notes.append("Monthly burn not provided — runway extension cannot be estimated.")

    # Participate / pass / monitor decision
    participation_check = (
        inp.pro_rata_amount if inp.pro_rata_amount > 0
        else inp.current_ownership_pct * inp.bridge_amount
    )
    # Buying at a discount to the expected next round → immediate mark-up
    markup_gain = (
        participation_check * (inp.expected_next_round_valuation / effective_conversion_price - 1.0)
        if effective_conversion_price > 0 else 0.0
    )
    # Value of the ownership lost if we sit out (marked at next-round valuation)
    dilution_cost_if_pass = (
        inp.current_ownership_pct * dilution_from_bridge * inp.expected_next_round_valuation
    )
    benefit = markup_gain + dilution_cost_if_pass

    if not inp.fund_is_participating:
        rec = "monitor"
        notes.append(
            "Fund is not participating in the bridge — monitor the round and the company's "
            "runway to the next milestone."
        )
    elif participation_check > 0 and benefit > 0.25 * participation_check:
        rec = "participate"
        notes.append(
            f"Participate: discount economics (${markup_gain:.2f}M mark-up on a "
            f"${participation_check:.2f}M check) plus avoided dilution "
            f"(${dilution_cost_if_pass:.2f}M) exceed 25% of the incremental check."
        )
    elif participation_check > 0 and benefit > 0.10 * participation_check:
        rec = "monitor"
        notes.append(
            f"Marginal economics (benefit ${benefit:.2f}M on a ${participation_check:.2f}M check) — "
            "monitor: revisit once bridge terms or next-round signal firm up."
        )
    else:
        rec = "pass"
        notes.append(
            f"Pass: expected benefit (${benefit:.2f}M) is below 10% of the "
            f"${participation_check:.2f}M incremental check; dilution from sitting out is "
            f"limited to {dilution_from_bridge:.1%}."
        )

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

@evidence_analysis
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
    deal = effective_deal(deal)
    path_ownership(deal, deal.future_rounds)  # Validate the explicit path.
    benchmarks = _load_benchmarks()

    # 1. Ownership math
    ownership = compute_ownership_math(
        check_size=deal.check_size,
        post_money=deal.post_money_valuation,
        stage=deal.stage,
        dilution=deal.dilution,
        fund_profile=fund,
        arr=deal.arr,
        future_rounds=deal.future_rounds,
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

    computation_notes: list[str] = [
        # M8: expected_irr semantics
        "expected_irr is the IRR of the probability-weighted expected proceeds "
        "at their specified exit dates, NOT the probability-weighted average of "
        "per-scenario IRRs.",
    ]

    # The displayed waterfall uses exactly the base scenario's distributable
    # equity and exit capitalization, so its investor proceeds reconcile.
    waterfall = None
    base_override = deal.scenario_assumptions.get('Base')
    base_stack = (base_override.exit_cap_table if base_override and
                  base_override.exit_cap_table is not None else deal.liquidation_stack)
    if base.available and base_stack:
        common = (base_override.exit_common_pct if base_override and
                  base_override.exit_common_pct is not None else deal.common_shares_pct)
        projected = deal.model_copy(update={'liquidation_stack': base_stack, 'common_shares_pct': common})
        waterfall = compute_waterfall(projected, base.exit_equity_value)
        waterfall.investor_total = base.gross_proceeds_to_fund
        waterfall.investor_moic = base.gross_moic
        waterfall.notes.append('Scenario investor proceeds are the check-size fraction of the selected share class; class payouts remain shown separately.')
        computation_notes.append('Base scenario proceeds reconcile to the displayed exit-cap-table waterfall.')

    # 6. IC Memo
    ic = build_ic_memo(deal, fund, ownership, bear, base, bull, ev, benchmarks)

    # 7. Ownership adequacy
    adequacy = _ownership_adequacy(ownership.entry_ownership_pct, fund.target_ownership_pct)

    # 8. Power law context
    # With the stage-derived failure mass in the bear branch, the base case is
    # the median *surviving* outcome — the note frames how many of those a
    # fund needs to return 3x gross.
    base_x_fund = base.fund_contribution_x
    fund_returners_needed = (
        3.0 / base_x_fund if base_x_fund > 0 else float("inf")
    )
    power_law_note = (
        f"Your fund needs ~{fund_returners_needed:.0f} 'base-case' outcomes "
        f"(${base.exit_enterprise_value:.0f}M exits each returning {base_x_fund:.1f}x the fund) "
        f"to return 3x gross. With a {fund.target_initial_check_count}-company portfolio, "
        f"that's {fund_returners_needed/fund.target_initial_check_count:.0%} of deals needing to hit base. "
        f"Portfolio concentration remains an assumption; these scenarios do not forecast its distribution."
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
        warnings.append("No current revenue. Returns require explicit exit assumptions; no revenue placeholder is used.")

    available = all(s.available for s in (bear, base, bull))
    if not available:
        ic.expected_value = None
        ic.financial_summary_text = 'Insufficient inputs for return analysis. ' + quick.recommendation_rationale
        power_law_note = 'Return-based portfolio context unavailable until exit assumptions are supplied.'
    # Dated expected proceeds: solve one NPV across the specified scenario dates.
    if available and len({s.exit_year for s in (bear, base, bull)}) > 1:
        lo, hi = -.999999, 1000.0
        for _ in range(160):
            mid = (lo + hi) / 2
            npv = sum(s.probability*s.gross_proceeds_to_fund/(1+mid)**s.exit_year for s in (bear,base,bull)) - deal.check_size
            if npv > 0: lo = mid
            else: hi = mid
        expected_irr = (lo + hi) / 2
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
        expected_value=ev if available else None,
        expected_moic=expected_moic if available else None,
        expected_irr=expected_irr if available else None,
        quick_screen=quick,
        waterfall=waterfall,
        ic_memo=ic,
        power_law_note=power_law_note,
        ownership_adequacy=adequacy,
        vertical_benchmarks_used=benchmarks.get("verticals", {}).get(deal.vertical.value, {}),
        flags=flags,
        warnings=warnings,
        computation_notes=computation_notes,
    )


# ---------------------------------------------------------------------------
# 11. GP Carry Economics
# ---------------------------------------------------------------------------

def run_gp_carry_analysis(inp: GPCarryInput) -> GPCarryOutput:
    """
    Model GP carry economics through a standard VC fund waterfall.

    Whole-fund (European) waterfall:
      1. Return of capital — LPs get back 1x committed capital
      2. Preferred return — LPs earn hurdle rate (compounded annually) on called capital
      3. GP catch-up — GP receives catch_up_pct of distributions until GP has
         received catch_up_target share of total profits
      4. Carried interest — remaining profits split carry_pct to GP, rest to LPs

    Deal-by-deal (American) waterfall:
      Same structure but applied per realized investment. More GP-friendly
      (carry paid earlier) but creates clawback exposure.

    Called-capital timing: the preferred return is NOT compounded on the full
    commitment from day 0. We approximate real call timing by assuming capital
    is called evenly over the deployment period, each annual tranche (called
    mid-year) compounding at the hurdle rate until the end of the fund life.

    Catch-up mechanics: after LPs receive capital + preferred, the GP receives
    catch_up_pct of each subsequent dollar until the GP holds catch_up_target
    of the profits distributed so far (preferred + catch-up pool). For a 100%
    catch-up at a 20% target this equals carry/(1−carry) × preferred. Once
    fully caught up, total GP take equals carry% × total profits; with a zero
    hurdle there is no preferred and hence no catch-up.
    """
    fund = inp.fund_profile
    total_dist = inp.total_distributions

    # Step 1: Return of capital
    return_of_capital = min(total_dist, fund.fund_size)
    remaining = max(0.0, total_dist - return_of_capital)

    # Step 2: Preferred return on called capital (timing-approximated).
    # Capital is assumed called in equal annual tranches over the deployment
    # period, each tranche mid-year, compounding at the hurdle to end of life.
    deploy_years = max(1, fund.deployment_period_years)
    tranche = fund.fund_size / deploy_years
    hurdle_compounded = sum(
        tranche * ((1 + fund.hurdle_rate) ** max(0.0, inp.fund_life_years - (y + 0.5)) - 1)
        for y in range(deploy_years)
    )
    preferred_return = min(remaining, hurdle_compounded)
    remaining -= preferred_return

    total_profit = max(0.0, total_dist - fund.fund_size)

    # Step 3: GP catch-up.
    # Full catch-up is reached when GP has catch_up_target of the profit
    # distributed so far: catch_up_pct × pool = catch_up_target × (preferred + pool)
    #   → pool = catch_up_target × preferred / (catch_up_pct − catch_up_target)
    if (
        inp.catch_up_pct > 0
        and preferred_return > 0
        and fund.hurdle_rate > 0
    ):
        if inp.catch_up_pct > inp.catch_up_target:
            full_catch_up_pool = (
                inp.catch_up_target * preferred_return
                / (inp.catch_up_pct - inp.catch_up_target)
            )
        else:
            # Catch-up rate at or below the target share: GP can never fully
            # catch up — the catch-up tier absorbs all remaining profit.
            full_catch_up_pool = float("inf")
        catch_up_pool = min(remaining, full_catch_up_pool)
        catch_up_to_gp = catch_up_pool * inp.catch_up_pct
    else:
        # No hurdle → no preferred → nothing to catch up on.
        catch_up_pool = 0.0
        catch_up_to_gp = 0.0
    remaining -= catch_up_pool

    # Step 4: Remaining split at carry rate
    gp_carry_from_remaining = remaining * fund.carry_pct

    total_gp_carry = catch_up_to_gp + gp_carry_from_remaining

    # GP commitment economics
    gp_commit = fund.fund_size * inp.gp_commit_pct
    gp_return_of_commit = min(gp_commit, return_of_capital * inp.gp_commit_pct)

    # Per-GP
    carry_per_gp = total_gp_carry / inp.num_gps if inp.num_gps > 0 else total_gp_carry
    total_salary = inp.gp_salary_annual * inp.fund_life_years
    salary_per_gp = total_salary / inp.num_gps if inp.num_gps > 0 else total_salary
    total_comp_per_gp = carry_per_gp + gp_return_of_commit / max(inp.num_gps, 1) + salary_per_gp

    # None (not inf) when there is no salary — inf is not JSON-serializable
    carry_vs_salary = (carry_per_gp / salary_per_gp) if salary_per_gp > 0 else None

    # Management fees
    total_mgmt_fees = fund.total_management_fees
    mgmt_per_gp_annual = (
        (total_mgmt_fees / fund.management_fee_years) / inp.num_gps
        if inp.num_gps > 0 and fund.management_fee_years > 0
        else 0.0
    )

    # Clawback exposure
    clawback_escrow = total_gp_carry * inp.clawback_escrow_pct
    # Max clawback = total carry paid (in deal-by-deal, GP may have been overpaid)
    clawback_exposure = total_gp_carry if inp.carry_structure == CarryStructure.DEAL_BY_DEAL else 0.0

    # LP economics: everything the GP doesn't take goes to LPs
    lp_total = total_dist - total_gp_carry
    lp_paid_in = fund.fund_size * (1 - inp.gp_commit_pct)
    lp_net_mult = lp_total / lp_paid_in if lp_paid_in > 0 else 0.0
    lp_net_irr_val = _irr(lp_paid_in, lp_total, inp.fund_life_years) if lp_paid_in > 0 else None

    gross_mult = total_dist / fund.fund_size if fund.fund_size > 0 else 0.0

    notes = []
    if inp.carry_structure == CarryStructure.DEAL_BY_DEAL:
        notes.append(
            "Deal-by-deal (American) waterfall: carry is paid on each realized exit. "
            "This means the GP receives carry earlier but faces clawback risk if later "
            "exits underperform."
        )
    else:
        notes.append(
            "Whole-fund (European) waterfall: carry is only paid after all capital is "
            "returned to LPs plus the hurdle rate. More LP-friendly; no clawback risk."
        )

    notes.append(
        f"Preferred return approximates call timing: capital called evenly over "
        f"{max(1, fund.deployment_period_years)} deployment years (mid-year tranches), each "
        f"compounding at the {fund.hurdle_rate:.0%} hurdle to the end of the "
        f"{inp.fund_life_years}-year fund life (${hurdle_compounded:.1f}M preferred at full run)."
    )

    if gross_mult < 1.0:
        notes.append(f"Fund is returning {gross_mult:.2f}x — below cost basis. No carry is earned.")
    elif total_gp_carry > 0:
        notes.append(
            f"GP earns ${total_gp_carry:.1f}M in carry on ${total_profit:.1f}M of profits. "
            f"Effective GP take: {total_gp_carry / total_profit:.1%} of profits."
        )

    return GPCarryOutput(
        fund_size=fund.fund_size,
        total_distributions=total_dist,
        gross_multiple=gross_mult,
        return_of_capital=return_of_capital,
        preferred_return_amount=preferred_return,
        catch_up_amount=catch_up_to_gp,
        remaining_after_catch_up=remaining,
        gp_carry_from_remaining=gp_carry_from_remaining,
        total_gp_carry=total_gp_carry,
        gp_commit_amount=gp_commit,
        gp_return_of_commit=gp_return_of_commit,
        gp_carry_per_gp=carry_per_gp,
        gp_total_comp_per_gp=total_comp_per_gp,
        carry_as_multiple_of_salary=carry_vs_salary,
        total_management_fees=total_mgmt_fees,
        management_fee_per_gp_annual=mgmt_per_gp_annual,
        clawback_escrow=clawback_escrow,
        clawback_exposure=clawback_exposure,
        lp_total_distributions=lp_total,
        lp_net_multiple=lp_net_mult,
        lp_net_irr=lp_net_irr_val,
        carry_structure=inp.carry_structure,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# 12. Fund-Level IRR & J-Curve
# ---------------------------------------------------------------------------

@evidence_analysis
def run_fund_irr_analysis(inp: FundIRRInput) -> FundIRROutput:
    """
    Compute fund-level IRR and model the J-curve.

    The J-curve reflects the typical VC fund lifecycle:
    - Years 0-3: capital calls exceed distributions (negative cumulative CF)
    - Years 3-5: first exits begin, curve flattens
    - Years 5-10: distributions accelerate, curve rises above zero

    If no explicit cashflows are provided, we synthesize a typical deployment
    schedule based on the fund profile and current positions.
    """
    fund = inp.fund_profile

    # Build cashflow timeline
    if inp.cashflows:
        cfs = sorted(inp.cashflows, key=lambda c: c.year)
    else:
        # Synthesize from positions — capital calls are negative, distributions positive
        cfs = []
        for pos in inp.positions:
            # Initial investment as capital call
            call_year = max(0.0, pos.vintage_year - fund.vintage_year)
            cfs.append(FundCashflow(
                year=call_year,
                amount=-pos.check_size,
                description=f"Initial: {pos.company_name}",
            ))
            if pos.reserve_deployed > 0:
                cfs.append(FundCashflow(
                    year=call_year + 1.5,
                    amount=-pos.reserve_deployed,
                    description=f"Follow-on: {pos.company_name}",
                ))
            if pos.realized_proceeds > 0:
                cfs.append(FundCashflow(
                    year=call_year + 5.0,
                    amount=pos.realized_proceeds,
                    description=f"Exit: {pos.company_name}",
                ))

        # Add management fee calls (annual)
        annual_fee = fund.fund_size * fund.management_fee_pct
        for yr in range(fund.management_fee_years):
            cfs.append(FundCashflow(
                year=float(yr),
                amount=-annual_fee,
                description=f"Management fee Y{yr+1}",
            ))

        cfs = sorted(cfs, key=lambda c: c.year)

    # Compute aggregates
    total_called = sum(-c.amount for c in cfs if c.amount < 0)
    total_distributed = sum(c.amount for c in cfs if c.amount > 0)

    # Current NAV
    if inp.current_nav is not None:
        nav = inp.current_nav
    else:
        nav = sum(
            (p.fair_value if p.fair_value is not None else p.cost_basis)
            for p in inp.positions
            if p.status in ("active", "partially_exited")
        )

    # TVPI / DPI / RVPI
    dpi = total_distributed / total_called if total_called > 0 else 0.0
    rvpi = nav / total_called if total_called > 0 else 0.0
    gross_tvpi = dpi + rvpi

    # Net TVPI (after carry on total gains — realized distributions AND
    # unrealized NAV, not just NAV). Carry is only earned when total value
    # clears the hurdle-compounded called capital (European-style, 100%
    # catch-up assumed, so above the hurdle carry applies to the full gain).
    total_value = total_distributed + nav
    gain = max(0.0, total_value - total_called)
    hurdle_basis = total_called * ((1 + fund.hurdle_rate) ** inp.fund_age_years)
    carry_on_gain = gain * fund.carry_pct if total_value >= hurdle_basis else 0.0
    net_tvpi = (total_value - carry_on_gain) / total_called if total_called > 0 else 0.0

    # IRR via Newton's method on cashflows + terminal NAV
    def _compute_irr_from_cfs(cashflows: list[FundCashflow], terminal_nav: float,
                               terminal_year: float) -> Optional[float]:
        """Newton-Raphson IRR solver for irregular cashflows."""
        all_cfs = [(c.year, c.amount) for c in cashflows]
        all_cfs.append((terminal_year, terminal_nav))

        # Initial guess
        r = 0.10
        for _ in range(200):
            npv_val = sum(cf / (1 + r) ** t if (1 + r) > 0 else 0.0 for t, cf in all_cfs)
            dnpv = sum(-t * cf / (1 + r) ** (t + 1) if (1 + r) > 0 else 0.0 for t, cf in all_cfs)
            if abs(dnpv) < 1e-12:
                break
            r_new = r - npv_val / dnpv
            # Clamp to reasonable range
            r_new = max(-0.99, min(10.0, r_new))
            if abs(r_new - r) < 1e-8:
                r = r_new
                break
            r = r_new

        # Validate
        if math.isnan(r) or math.isinf(r) or r < -0.99 or r > 10.0:
            return None
        return r

    gross_irr = _compute_irr_from_cfs(cfs, nav, inp.fund_age_years) if cfs else None

    # Net IRR: haircut BOTH realized distributions and terminal NAV by the
    # carry load (scaled pro-rata across all value), not just the NAV.
    if cfs:
        net_scale = (total_value - carry_on_gain) / total_value if total_value > 0 else 1.0
        net_cfs = [
            FundCashflow(
                year=c.year,
                amount=c.amount * net_scale if c.amount > 0 else c.amount,
                description=c.description,
            )
            for c in cfs
        ]
        net_irr = _compute_irr_from_cfs(net_cfs, nav * net_scale, inp.fund_age_years)
    else:
        net_irr = None

    # J-curve construction
    j_points = []
    cumulative = 0.0
    trough_year = None
    trough_val = 0.0

    # Build yearly snapshots
    max_year = max((c.year for c in cfs), default=inp.fund_age_years)
    for yr in range(int(max_year) + 1):
        year_cfs = sum(c.amount for c in cfs if int(c.year) == yr)
        cumulative += year_cfs
        # Estimate NAV at this point (linear interpolation to current NAV)
        if inp.fund_age_years > 0:
            nav_at_yr = nav * min(1.0, yr / inp.fund_age_years)
        else:
            nav_at_yr = nav
        tvpi_at_yr = (cumulative + nav_at_yr) / total_called if total_called > 0 else 0.0

        j_points.append({
            "year": yr,
            "cumulative_cf": cumulative,
            "nav_estimate": nav_at_yr,
            "tvpi": tvpi_at_yr,
        })

        if cumulative < trough_val:
            trough_val = cumulative
            trough_year = float(yr)

    quartile = 'unavailable'
    vintage_context = (
        f'Fund {fund.fund_name} (vintage {fund.vintage_year}) is {inp.fund_age_years:.0f} years old. '
        'No matching vintage, age, size and net-metric benchmark is available; no quartile assigned.'
    )

    notes = []
    if dpi < 0.5 and inp.fund_age_years > 5:
        notes.append(
            f"DPI of {dpi:.2f}x at year {inp.fund_age_years:.0f} is below typical pace. "
            "Consider accelerating exits or secondaries."
        )
    if not cfs:
        notes.append("No cashflows provided — using position data to estimate fund performance.")

    return FundIRROutput(
        fund_size=fund.fund_size,
        fund_age_years=inp.fund_age_years,
        total_called=total_called,
        total_distributed=total_distributed,
        current_nav=nav,
        gross_tvpi=gross_tvpi,
        net_tvpi=net_tvpi,
        gross_irr=gross_irr,
        net_irr=net_irr,
        dpi=dpi,
        rvpi=rvpi,
        j_curve_points=j_points,
        j_curve_trough_year=trough_year,
        j_curve_trough_value=trough_val,
        quartile_estimate=quartile,
        vintage_context=vintage_context,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# 13. SAFE Conversion Modeling
# ---------------------------------------------------------------------------

def run_safe_conversion(inp: SAFEConversionInput) -> SAFEConversionOutput:
    """
    Model a stack of SAFEs converting at a priced equity round.

    Handles:
    - Valuation cap conversion
    - Discount rate conversion
    - MFN (Most Favored Nation) clause
    - Post-money vs pre-money SAFE mechanics
    - Option pool shuffle

    The conversion logic follows YC post-money SAFE conventions:
    - Post-money SAFE: the cap is measured on the post-SAFE capitalization,
      i.e. the SAFE holder owns safe_amount / valuation_cap of the company
      capitalization INCLUDING all SAFE conversion shares. Because every
      post-money SAFE's share count depends on the total SAFE shares, we solve
      the stack to a fixed point.
    - Pre-money SAFE: cap is on pre-money valuation (more founder-friendly)

    MFN: a SAFE with an MFN clause inherits the best cap/discount among SAFEs
    issued AFTER it. Issuance order is taken to be the order of safe_stack.

    Option pool: option_pool_pct is a percentage of the POST-money fully
    diluted capitalization (per the field's documentation); the pool size is
    solved jointly with the SAFE conversion (outer fixed-point iteration).
    """
    # Work on copies — never mutate caller's SAFE terms (MFN adjustments below)
    safes = [s.model_copy() for s in inp.safe_stack]
    pre_money = inp.priced_round_pre_money
    new_money = inp.priced_round_amount
    post_money = pre_money + new_money

    # Step 0: MFN — each MFN SAFE inherits the best cap/discount among SAFEs
    # issued AFTER it (stack order = issuance order).
    mfn_applied: list[bool] = [False] * len(safes)
    for idx, s in enumerate(safes):
        if not s.has_mfn:
            continue
        later = safes[idx + 1:]
        later_caps = [t.valuation_cap for t in later if t.valuation_cap is not None]
        best_cap = min(later_caps) if later_caps else None
        best_discount = max((t.discount_rate for t in later), default=0.0)
        if best_cap is not None and (s.valuation_cap is None or best_cap < s.valuation_cap):
            s.valuation_cap = best_cap
            mfn_applied[idx] = True
        if best_discount > s.discount_rate:
            s.discount_rate = best_discount
            mfn_applied[idx] = True

    founder_shares = inp.pre_safe_shares_outstanding

    # Jointly solve option pool (as % of post-money) and SAFE conversion.
    # Outer loop: pool sizing; inner loop: post-money SAFE fixed point.
    pool_pct = min(inp.option_pool_pct, 0.99)
    option_pool_shares = founder_shares * pool_pct / (1 - pool_pct)  # initial guess
    total_safe_shares = 0.0
    pre_round_shares = founder_shares + option_pool_shares
    priced_round_pps = pre_money / pre_round_shares if pre_round_shares > 0 else 0.0
    new_investor_shares = new_money / priced_round_pps if priced_round_pps > 0 else 0.0
    per_safe: list[tuple[float, float, str]] = []  # (pps, shares, discount_applied)

    for _outer in range(100):
        pre_round_shares = founder_shares + option_pool_shares
        priced_round_pps = pre_money / pre_round_shares if pre_round_shares > 0 else 0.0

        # Inner fixed point: post-money SAFE caps are measured on the
        # post-SAFE capitalization (pre-round shares + ALL SAFE shares).
        for _inner in range(100):
            post_safe_cap_shares = pre_round_shares + total_safe_shares
            new_per_safe = []
            new_total = 0.0
            for safe in safes:
                if safe.valuation_cap is not None and pre_round_shares > 0:
                    if safe.is_post_money:
                        cap_pps = safe.valuation_cap / post_safe_cap_shares
                    else:
                        cap_pps = safe.valuation_cap / pre_round_shares
                else:
                    cap_pps = float("inf")

                if safe.discount_rate > 0:
                    discount_pps = priced_round_pps * (1 - safe.discount_rate)
                else:
                    discount_pps = float("inf")

                if cap_pps <= discount_pps and cap_pps < float("inf"):
                    conversion_pps = cap_pps
                    discount_applied = "cap" if discount_pps == float("inf") else "cap (lower)"
                elif discount_pps < float("inf"):
                    conversion_pps = discount_pps
                    discount_applied = "discount" if cap_pps == float("inf") else "discount (lower)"
                else:
                    conversion_pps = priced_round_pps
                    discount_applied = "none (at round price)"

                shares = safe.safe_amount / conversion_pps if conversion_pps > 0 else 0.0
                new_per_safe.append((conversion_pps, shares, discount_applied))
                new_total += shares
            converged = abs(new_total - total_safe_shares) <= max(1e-9, 1e-9 * new_total)
            total_safe_shares = new_total
            per_safe = new_per_safe
            if converged:
                break

        new_investor_shares = new_money / priced_round_pps if priced_round_pps > 0 else 0.0

        # Pool sized off post-money fully diluted shares: pool = pct × total
        total_ex_pool = founder_shares + total_safe_shares + new_investor_shares
        pool_target = total_ex_pool * pool_pct / (1 - pool_pct) if pool_pct < 1.0 else 0.0
        if abs(pool_target - option_pool_shares) <= max(1e-9, 1e-9 * max(pool_target, 1.0)):
            option_pool_shares = pool_target
            break
        option_pool_shares = pool_target

    # Build per-SAFE conversion results
    conversions: list[SAFEConversionResult] = []
    for (safe, (conversion_pps, shares, discount_applied), was_mfn) in zip(safes, per_safe, mfn_applied):
        conversions.append(SAFEConversionResult(
            investor_name=safe.investor_name,
            safe_amount=safe.safe_amount,
            conversion_price=conversion_pps,
            shares_issued=shares,
            ownership_pct=0.0,  # filled after total computed
            effective_valuation=conversion_pps * pre_round_shares,
            discount_applied=discount_applied,
            mfn_adjusted=was_mfn,
        ))

    # Step 4: Total cap table (recompute with the converged pool)
    pre_round_shares = founder_shares + option_pool_shares
    total_shares = pre_round_shares + total_safe_shares + new_investor_shares

    # Compute ownership percentages
    for conv in conversions:
        conv.ownership_pct = conv.shares_issued / total_shares if total_shares > 0 else 0.0

    founder_pct = founder_shares / total_shares if total_shares > 0 else 0.0
    option_pct = option_pool_shares / total_shares if total_shares > 0 else 0.0
    safe_total_pct = total_safe_shares / total_shares if total_shares > 0 else 0.0
    new_investor_pct = new_investor_shares / total_shares if total_shares > 0 else 0.0

    total_post_money_actual = total_shares * priced_round_pps

    # Dilution analysis
    # Without SAFEs, founders would own: founder_shares / (founder_shares + option_pool + new_investor)
    no_safe_total = founder_shares + option_pool_shares + new_investor_shares
    founder_pct_without_safes = founder_shares / no_safe_total if no_safe_total > 0 else 0.0
    dilution_from_safes = founder_pct_without_safes - founder_pct

    # Total dilution from pre-funding
    original_founder_pct = 1.0  # founders owned 100% before any dilution
    total_dilution = original_founder_pct - founder_pct

    effective_pre_to_founders = founder_pct * post_money

    notes = [
        f"Option pool sized to {inp.option_pool_pct:.0%} of the post-money fully diluted "
        "capitalization (solved jointly with SAFE conversion).",
    ]
    if total_safe_shares > 0 and priced_round_pps > 0:
        avg_safe_pps = sum(s.safe_amount for s in safes) / total_safe_shares
        notes.append(
            f"SAFEs convert at an average price of ${avg_safe_pps:.4f}/share "
            f"vs. priced round at ${priced_round_pps:.4f}/share "
            f"({(1 - avg_safe_pps / priced_round_pps):.1%} average discount)."
        )

    if dilution_from_safes > 0.10:
        notes.append(
            f"SAFE stack causes {dilution_from_safes:.1%} additional founder dilution "
            f"beyond the priced round. Consider the cumulative impact on founder incentives."
        )

    if any(mfn_applied):
        notes.append(
            "MFN clause triggered: SAFE holders with MFN inherited the best terms among "
            "SAFEs issued after them (stack order = issuance order)."
        )

    return SAFEConversionOutput(
        company_name=inp.company_name,
        priced_round_pre_money=pre_money,
        priced_round_amount=new_money,
        priced_round_price_per_share=priced_round_pps,
        conversions=conversions,
        founder_shares=founder_shares,
        founder_ownership_pct=founder_pct,
        option_pool_shares=option_pool_shares,
        option_pool_pct=option_pct,
        safe_shares_total=total_safe_shares,
        safe_ownership_total_pct=safe_total_pct,
        new_investor_shares=new_investor_shares,
        new_investor_ownership_pct=new_investor_pct,
        total_shares=total_shares,
        total_post_money=total_post_money_actual,
        founder_dilution_from_safes=dilution_from_safes,
        founder_dilution_total=total_dilution,
        effective_pre_money_to_founders=effective_pre_to_founders,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# 14. Deal Comparison
# ---------------------------------------------------------------------------

def run_deal_comparison(
    deals: list[tuple[VCDealInput, FundProfile]],
) -> DealComparisonOutput:
    """
    Side-by-side comparison of multiple VC deals for IC discussion.

    Evaluates each deal independently, then ranks them on key metrics
    to help VCs prioritize which deals to pursue.
    """
    entries: list[DealComparisonEntry] = []
    for deal, fund in deals:
        evaluated = run_vc_deal_evaluation(deal, fund)
        ownership = evaluated.ownership
        base = evaluated.base_scenario
        expected_moic = evaluated.expected_moic
        expected_irr = evaluated.expected_irr
        quick = evaluated.quick_screen
        runway = _runway_months(deal.cash_on_hand, deal.burn_rate_monthly)

        entries.append(DealComparisonEntry(
            company_name=deal.company_name,
            vertical=deal.vertical,
            stage=deal.stage,
            post_money=deal.post_money_valuation,
            check_size=deal.check_size,
            arr=deal.arr,
            revenue_growth_rate=deal.revenue_growth_rate,
            gross_margin=deal.gross_margin,
            burn_rate_monthly=deal.burn_rate_monthly,
            runway_months=runway,
            entry_ownership_pct=ownership.entry_ownership_pct,
            exit_ownership_pct=ownership.exit_ownership_pct,
            expected_moic=expected_moic,
            expected_irr=expected_irr,
            base_case_ev=base.exit_enterprise_value,
            fund_returner_threshold=ownership.fund_returner_1x_exit,
            recommendation=quick.recommendation,
        ))

    # Rank on key metrics (1 = best)
    if entries:
        by_moic = sorted((i for i, e in enumerate(entries) if e.expected_moic is not None), key=lambda i: entries[i].expected_moic, reverse=True)
        by_irr = sorted((i for i, e in enumerate(entries) if e.expected_irr is not None), key=lambda i: entries[i].expected_irr, reverse=True)
        by_ownership = sorted(range(len(entries)), key=lambda i: entries[i].exit_ownership_pct, reverse=True)

        for rank, idx in enumerate(by_moic):
            entries[idx].rank_moic = rank + 1
        for rank, idx in enumerate(by_irr):
            entries[idx].rank_irr = rank + 1
        for rank, idx in enumerate(by_ownership):
            entries[idx].rank_ownership = rank + 1

    comparable = [e for e in entries if e.expected_moic is not None]
    best_ev = max(comparable, key=lambda e: e.expected_moic).company_name if comparable else None
    best_own = max(entries, key=lambda e: e.exit_ownership_pct).company_name if entries else None

    # Best fund fit: strong_interest > look_deeper > pass, then by MOIC
    rec_order = {"strong_interest": 3, "look_deeper": 2, "pass": 1}
    best_fit = max(
        comparable,
        key=lambda e: (rec_order.get(e.recommendation, 0), e.expected_moic)
    ).company_name if comparable else None

    comp_notes = []
    if len(comparable) < len(entries):
        comp_notes.append('Deals with insufficient inputs are excluded from return rankings.')
    if len(comparable) >= 2:
        moic_spread = max(e.expected_moic for e in comparable) - min(e.expected_moic for e in comparable)
        comp_notes.append(
            f"MOIC spread across {len(comparable)} comparable deals: {moic_spread:.1f}x "
            f"({min(e.expected_moic for e in comparable):.1f}x to {max(e.expected_moic for e in comparable):.1f}x)"
        )
        strong = [e for e in entries if e.recommendation == "strong_interest"]
        if strong:
            comp_notes.append(f"{len(strong)} deal(s) rated 'strong interest': {', '.join(e.company_name for e in strong)}")

    return DealComparisonOutput(
        deals=entries,
        best_risk_adjusted=best_ev,
        best_ownership=best_own,
        best_fund_fit=best_fit,
        comparison_notes=comp_notes,
    )
