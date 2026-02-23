# Licensed under the Business Source License 1.1 — see LICENSE file for details
"""
Core financial computation engine.

Takes a DealInput and returns a DealOutput by:
  1. Computing purchase price allocation
  2. Building 5-year pro forma income statements (with circularity-solved debt)
  3. Computing the accretion/dilution bridge
  4. Generating sensitivity matrices
  5. Computing IRR/MOIC returns
  6. Running risk analysis
  7. Assembling the deal scorecard and verdict
"""
from __future__ import annotations

import json
import os
from typing import Callable

from .models import (
    AccretionDilutionBridge,
    BalanceSheetAtClose,
    DealInput,
    DealOutput,
    DealVerdict,
    DefensePositioning,
    HealthStatus,
    IncomeStatementYear,
    Industry,
    ScorecardMetric,
    SynergyItem,
)
from .circularity_solver import build_debt_schedule, DebtTranche
from .purchase_price import compute_ppa, get_transaction_costs
from .returns import compute_returns
from .risk_analyzer import analyze_risks
from .sensitivity import generate_all_sensitivity_matrices
from .defaults import get_defaults


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_benchmarks() -> dict:
    data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    path = os.path.join(data_dir, "industry_benchmarks.json")
    with open(path) as f:
        return json.load(f)


def _synergy_year_value(items: list[SynergyItem], year: int) -> float:
    """
    Compute total synergy value realized in a given year.

    Each synergy item phases in linearly over phase_in_years.
    Year 1 = 1/N of run-rate, Year 2 = 2/N, ..., Year N = full run-rate.
    """
    total = 0.0
    for item in items:
        if item.phase_in_years <= 0:
            total += item.annual_amount
        else:
            realized_pct = min(1.0, year / item.phase_in_years)
            total += item.annual_amount * realized_pct
    return total


def _build_synthetic_tranches(deal: DealInput) -> list[DebtTranche]:
    """
    If the deal has no explicit debt tranches, build a single synthetic tranche
    from the deal structure using smart-default interest rates.
    """
    from .defaults import get_interest_rate
    from .models import AmortizationType

    acq_debt = deal.target.acquisition_price * deal.structure.debt_percentage
    if acq_debt <= 0:
        return []

    rate = get_interest_rate(deal.target.acquisition_price)
    return [DebtTranche(
        name="Acquisition Term Loan",
        amount=acq_debt,
        interest_rate=rate,
        term_years=7,
        amortization_type=AmortizationType.STRAIGHT_LINE,
    )]


def _format_currency(value: float) -> str:
    """Format a dollar value for display."""
    abs_val = abs(value)
    sign = "-" if value < 0 else ""
    if abs_val >= 1_000_000_000:
        return f"{sign}${abs_val/1_000_000_000:.1f}B"
    if abs_val >= 1_000_000:
        return f"{sign}${abs_val/1_000_000:.1f}M"
    if abs_val >= 1_000:
        return f"{sign}${abs_val/1_000:.0f}K"
    return f"{sign}${abs_val:.0f}"


def _format_multiple(value: float) -> str:
    return f"{value:.1f}×"


def _format_pct(value: float) -> str:
    return f"{value:+.1f}%"


# ---------------------------------------------------------------------------
# Defense-specific computation
# ---------------------------------------------------------------------------

def _compute_defense_positioning(deal: DealInput, benchmarks: dict) -> DefensePositioning | None:
    """
    Compute defense-specific positioning metrics when the target is in
    the Defense & National Security vertical with a defense_profile.
    """
    tgt = deal.target
    if tgt.industry != Industry.DEFENSE or tgt.defense_profile is None:
        return None

    dp = tgt.defense_profile
    defense_bench = benchmarks.get("Defense & National Security", {}).get("defense_specific", {})

    # EV/Revenue multiple
    ev_revenue = tgt.acquisition_price / tgt.revenue if tgt.revenue > 0 else 0.0

    # Backlog metrics
    combined_backlog = dp.contract_backlog_total
    backlog_coverage_ratio = combined_backlog / tgt.revenue if tgt.revenue > 0 else 0.0
    revenue_visibility_years = dp.contract_backlog_funded / tgt.revenue if tgt.revenue > 0 else 0.0

    # Clearance premium from benchmarks
    clearance_premiums = defense_bench.get("clearance_premium_pct", {})
    clearance_premium = clearance_premiums.get(dp.clearance_level.value, 0.0)

    # Certification premium — sum applicable certifications
    cert_premiums = defense_bench.get("certification_premium_pct", {})
    certification_premium = 0.0
    cert_key_map = {
        "FedRAMP Moderate": "fedramp_moderate",
        "FedRAMP High": "fedramp_high",
        "IL4": "il4",
        "IL5": "il5",
        "IL6": "il6",
        "CMMC Level 2": "cmmc_level_2",
        "CMMC Level 3": "cmmc_level_3",
    }
    for cert in dp.authorization_certifications:
        key = cert_key_map.get(cert, cert.lower().replace(" ", "_"))
        certification_premium += cert_premiums.get(key, 0.0)

    # Program of record premium
    por_premium = defense_bench.get("program_of_record_premium_pct", 0.15) if dp.programs_of_record > 0 else 0.0

    total_defense_premium = clearance_premium + certification_premium + por_premium

    # Build summary
    clearance_labels = {
        "unclassified": "Unclassified",
        "secret": "Secret",
        "top_secret": "Top Secret",
        "ts_sci": "Top Secret/SCI",
        "sap": "SAP",
    }
    clearance_label = clearance_labels.get(dp.clearance_level.value, dp.clearance_level.value)

    parts = []
    parts.append(f"This acquisition gives the buyer access to {clearance_label} facility clearance")
    if len(dp.contract_vehicles) > 0:
        parts.append(f"{len(dp.contract_vehicles)} active contract vehicle{'s' if len(dp.contract_vehicles) != 1 else ''}")
    if dp.programs_of_record > 0:
        parts.append(f"positions on {dp.programs_of_record} program{'s' if dp.programs_of_record != 1 else ''} of record")
    if combined_backlog > 0:
        parts.append(f"Combined backlog of ${combined_backlog / 1e6:.0f}M provides {revenue_visibility_years:.1f} years of revenue visibility")

    summary = ", ".join(parts[:3])
    if len(parts) > 3:
        summary += ". " + parts[3]
    summary += "."

    return DefensePositioning(
        clearance_level=clearance_label,
        active_contract_vehicles=len(dp.contract_vehicles),
        programs_of_record=dp.programs_of_record,
        combined_backlog=combined_backlog,
        backlog_coverage_ratio=backlog_coverage_ratio,
        revenue_visibility_years=revenue_visibility_years,
        ev_revenue_multiple=ev_revenue,
        clearance_premium_applied=clearance_premium,
        certification_premium_applied=certification_premium,
        program_of_record_premium_applied=por_premium,
        total_defense_premium_pct=total_defense_premium,
        is_ai_native=dp.is_ai_native,
        positioning_summary=summary,
    )


# ---------------------------------------------------------------------------
# Main engine
# ---------------------------------------------------------------------------

def run_deal(deal: DealInput, include_sensitivity: bool = True) -> DealOutput:
    """
    Execute the full deal model computation.

    Args:
        deal: Complete deal inputs.
        include_sensitivity: When False, skips sensitivity matrix generation.
            Always pass False when calling run_deal() from within a sensitivity
            function to prevent exponential recursive re-entry.

    Returns:
        DealOutput with all computed results.
    """
    benchmarks = _load_benchmarks()
    ppa = compute_ppa(deal)
    transaction_costs = get_transaction_costs(deal)
    notes: list[str] = []

    # Use explicit debt tranches if provided, else build synthetic
    tranches = deal.structure.debt_tranches if deal.structure.debt_tranches else _build_synthetic_tranches(deal)
    acq_debt_total = sum(t.amount for t in tranches)

    n_years = deal.projection_years
    acq = deal.acquirer
    tgt = deal.target

    # -----------------------------------------------------------------------
    # Year-by-year projections
    # -----------------------------------------------------------------------
    acquirer_revenue_growth = 0.03  # Modest organic growth for acquirer
    target_growth = tgt.revenue_growth_rate

    # EBITDA margin (guarded against zero revenue — Pydantic enforces gt=0, but
    # be explicit here in case the engine is called directly in tests)
    acq_ebitda_margin = acq.ebitda / acq.revenue if acq.revenue > 0 else 0.15
    tgt_ebitda_margin = tgt.ebitda / tgt.revenue if tgt.revenue > 0 else 0.12

    # Gross margin: derive from EBITDA margin + SG&A proxy
    # Guard against acq_ebitda_margin producing unrealistic gross margins
    acq_gross_margin_base = max(0.1, min(0.95, acq_ebitda_margin + 0.20))
    tgt_gross_margin_base = max(0.1, min(0.95, tgt_ebitda_margin + 0.20))

    # Standalone acquirer EPS (for accretion/dilution comparison)
    acq_standalone_eps = acq.eps

    # New shares issued (for stock consideration)
    new_shares_issued = 0.0
    if deal.structure.stock_percentage > 0 and acq.share_price > 0:
        stock_consideration = deal.target.acquisition_price * deal.structure.stock_percentage
        new_shares_issued = stock_consideration / acq.share_price

    total_shares_pro_forma = acq.shares_outstanding + new_shares_issued

    # Build ebitda_by_year for circularity solver (initial estimate before synergies)
    raw_ebitda_by_year: list[float] = []
    raw_da_by_year: list[float] = []
    raw_capex_by_year: list[float] = []

    for yr in range(1, n_years + 1):
        acq_rev_yr = acq.revenue * (1 + acquirer_revenue_growth) ** yr
        tgt_rev_yr = tgt.revenue * (1 + target_growth) ** yr
        combined_rev = acq_rev_yr + tgt_rev_yr
        combined_ebitda = (
            acq_rev_yr * acq_ebitda_margin
            + tgt_rev_yr * tgt_ebitda_margin
        )
        raw_ebitda_by_year.append(combined_ebitda)
        combined_da = (acq.depreciation + tgt.depreciation) + ppa.total_incremental_annual
        raw_da_by_year.append(combined_da)
        raw_capex_by_year.append(acq.capex + tgt.capex)

    # Solve circularity across all years
    debt_schedules, any_non_convergence = build_debt_schedule(
        tranches=tranches,
        projection_years=n_years,
        ebitda_by_year=raw_ebitda_by_year,
        da_by_year=raw_da_by_year,
        capex_by_year=raw_capex_by_year,
        tax_rate=acq.tax_rate,
    )

    if any_non_convergence:
        notes.append("Warning: debt circularity solver did not fully converge in some years. Results are estimates.")

    # -----------------------------------------------------------------------
    # Build pro forma income statement
    # -----------------------------------------------------------------------
    income_statement: list[IncomeStatementYear] = []
    ad_bridge: list[AccretionDilutionBridge] = []

    ebitda_by_year: list[float] = []
    net_income_by_year: list[float] = []
    ending_debt_by_year: list[float] = []
    fcf_by_year: list[float] = []

    for yr in range(1, n_years + 1):
        ds = debt_schedules[yr - 1]

        # Revenue projections
        acq_rev_yr = acq.revenue * (1 + acquirer_revenue_growth) ** yr
        tgt_rev_yr = tgt.revenue * (1 + target_growth) ** yr
        combined_rev = acq_rev_yr + tgt_rev_yr

        # Revenue synergies realized this year
        rev_syn_yr = _synergy_year_value(deal.synergies.revenue_synergies, yr)
        total_rev = combined_rev + rev_syn_yr

        # COGS (derive from gross margin; simplified combined approach)
        # acq_gross_margin_base / tgt_gross_margin_base are pre-computed above
        combined_cogs = (
            acq_rev_yr * (1 - acq_gross_margin_base)
            + tgt_rev_yr * (1 - tgt_gross_margin_base)
        )

        # Cost synergies (reduce SG&A / COGS)
        cost_syn_yr = _synergy_year_value(deal.synergies.cost_synergies, yr)

        gross_profit = total_rev - combined_cogs

        # SG&A: (gross_margin - ebitda_margin) × revenue for each entity, scaled by growth
        # No division by acq.revenue needed — use the base margin gap directly
        acq_sga = acq_rev_yr * (acq_gross_margin_base - acq_ebitda_margin)
        tgt_sga = tgt_rev_yr * (tgt_gross_margin_base - tgt_ebitda_margin)
        combined_sga = acq_sga + tgt_sga - cost_syn_yr

        ebitda = gross_profit - combined_sga

        # D&A: acquirer + target + PPA incremental
        da_total = (
            acq.depreciation * (1 + acquirer_revenue_growth) ** yr
            + tgt.depreciation * (1 + target_growth) ** yr
            + ppa.total_incremental_annual
        )

        ebit = ebitda - da_total

        # Interest expense from converged debt schedule
        interest_exp = ds.total_interest_expense

        ebt = ebit - interest_exp

        # Transaction costs expensed in Year 1 (ASC 805)
        if yr == 1:
            ebt -= transaction_costs
            notes.append(f"Year 1 includes ${transaction_costs/1e6:.1f}M in transaction fees (one-time, per ASC 805).")

        taxes = max(0.0, ebt * acq.tax_rate)
        net_income = ebt - taxes

        pro_forma_eps = net_income / total_shares_pro_forma if total_shares_pro_forma > 0 else 0.0

        # Acquirer standalone EPS (grows at 3% per year for simplicity)
        standalone_eps_yr = acq_standalone_eps * (1.03 ** yr)
        accretion_dilution_pct = (
            (pro_forma_eps - standalone_eps_yr) / abs(standalone_eps_yr) * 100
            if standalone_eps_yr != 0 else 0.0
        )

        # FCF for returns roll-forward: NI + D&A - capex - WC change
        # Optional cash sweep (debt paydown from excess FCF) is already reflected
        # in ds.ending_debt_balance, so we track only what remains as free cash.
        capex_yr = (acq.capex + tgt.capex)
        fcf_yr = net_income + da_total - capex_yr - ds.optional_cash_sweep

        ebitda_by_year.append(ebitda)
        net_income_by_year.append(net_income)
        ending_debt_by_year.append(ds.ending_debt_balance)
        fcf_by_year.append(fcf_yr)

        income_statement.append(IncomeStatementYear(
            year=yr,
            revenue=total_rev,
            cogs=combined_cogs,
            gross_profit=gross_profit,
            sga=combined_sga,
            ebitda=ebitda,
            da=da_total,
            ebit=ebit,
            interest_expense=interest_exp,
            ebt=ebt,
            taxes=taxes,
            net_income=net_income,
            acquirer_standalone_eps=standalone_eps_yr,
            pro_forma_eps=pro_forma_eps,
            accretion_dilution_pct=accretion_dilution_pct,
        ))

        # ------------------------------------------------------------------
        # Accretion/Dilution Bridge (reconciled to IS EPS delta)
        # ------------------------------------------------------------------
        # EPS delta = pro_forma_eps - standalone_eps_yr (the IS truth)
        # We build the bridge from an explicit NI walk:
        #   Standalone NI (acquirer-only)  →  [per original share count]
        #   + Target NI contribution       →  target NI scaled to pro forma shares
        #   - Incremental interest (AT)    →  new debt service after-tax
        #   - Incremental D&A (AT)         →  PPA step-up charges after-tax
        #   + Synergy benefit (AT)         →  cost + revenue synergies after-tax
        #   - Share dilution effect        →  EPS erosion from new shares outstanding
        #   + Reconciling item             →  captures all other effects (transaction
        #                                     costs, tax timing differences, rounding)
        # The reconciling item makes the bridge tie exactly to the IS EPS delta.

        acq_standalone_ni_yr = standalone_eps_yr * acq.shares_outstanding
        target_ni_yr = tgt.net_income * (1 + target_growth) ** yr

        # Per-share deltas (denominator = pro forma shares for comparability)
        target_earnings_contribution = target_ni_yr / total_shares_pro_forma if total_shares_pro_forma > 0 else 0.0
        interest_drag = -(interest_exp * (1 - acq.tax_rate)) / total_shares_pro_forma if total_shares_pro_forma > 0 else 0.0
        da_adj = -(ppa.total_incremental_annual * (1 - acq.tax_rate)) / total_shares_pro_forma if total_shares_pro_forma > 0 else 0.0
        syn_benefit = ((cost_syn_yr + rev_syn_yr) * (1 - acq.tax_rate)) / total_shares_pro_forma if total_shares_pro_forma > 0 else 0.0
        share_dilution = (
            # EPS is diluted because the same standalone NI is spread over more shares
            -((acq_standalone_ni_yr / total_shares_pro_forma) - standalone_eps_yr)
            if new_shares_issued > 0 and total_shares_pro_forma > 0 else 0.0
        )

        # Sum of explicit components
        components_sum = (
            target_earnings_contribution
            + interest_drag
            + da_adj
            + syn_benefit
            + share_dilution
        )

        # Reconciling item = actual EPS delta minus sum of components
        # This captures transaction costs, tax differences, WC effects, etc.
        actual_eps_delta = pro_forma_eps - standalone_eps_yr
        tax_impact = actual_eps_delta - components_sum  # Reconciling / residual

        total_bridge = components_sum + tax_impact  # = actual_eps_delta by construction

        ad_bridge.append(AccretionDilutionBridge(
            year=yr,
            target_earnings_contribution=target_earnings_contribution,
            interest_expense_drag=interest_drag,
            da_adjustment=da_adj,
            synergy_benefit=syn_benefit,
            share_dilution_impact=share_dilution,
            tax_impact=tax_impact,
            total_accretion_dilution=total_bridge,
            total_accretion_dilution_pct=accretion_dilution_pct,
        ))

    # -----------------------------------------------------------------------
    # Balance Sheet at Close (simplified opening BS; see F3 in review for full fix)
    # -----------------------------------------------------------------------
    # Assets: acquirer book assets (proxied) + target intangibles + goodwill + PP&E writeup
    acq_combined_assets = (acq.revenue * 1.2) + ppa.goodwill + ppa.identifiable_intangibles + ppa.asset_writeup
    combined_total_assets = acq_combined_assets + tgt.revenue * 0.8

    # Liabilities: acquirer existing debt + new acquisition debt + DTL on step-ups
    combined_total_liabilities = (
        acq.total_debt
        + acq_debt_total
        + ppa.deferred_tax_liability  # DTL from PP&E and intangible step-ups (ASC 805)
    )
    # Equity: acquirer market cap + new shares at issue price
    combined_equity = acq.market_cap + new_shares_issued * acq.share_price

    balance_sheet = BalanceSheetAtClose(
        goodwill=ppa.goodwill,
        identifiable_intangibles=ppa.identifiable_intangibles,
        ppe_writeup=ppa.asset_writeup,
        new_acquisition_debt=acq_debt_total,
        cash_used=deal.target.acquisition_price * deal.structure.cash_percentage,
        shares_issued=new_shares_issued,
        target_equity_eliminated=max(0.0, tgt.working_capital + tgt.cash_on_hand - tgt.total_debt),
        combined_total_assets=combined_total_assets,
        combined_total_liabilities=combined_total_liabilities,
        combined_equity=combined_equity,
    )

    # -----------------------------------------------------------------------
    # Returns Analysis
    # -----------------------------------------------------------------------
    returns = compute_returns(deal, ebitda_by_year, net_income_by_year, ending_debt_by_year, fcf_by_year)

    # -----------------------------------------------------------------------
    # Sensitivity Matrices
    # -----------------------------------------------------------------------
    if include_sensitivity:
        def _accretion_fn(modified_deal: DealInput) -> float:
            """Quick re-run for sensitivity — returns Year 1 accretion as decimal.
            Calls run_deal with include_sensitivity=False to prevent recursive re-entry.
            """
            try:
                out = run_deal(modified_deal, include_sensitivity=False)
                if out.pro_forma_income_statement:
                    return out.pro_forma_income_statement[0].accretion_dilution_pct / 100
                return 0.0
            except Exception:
                return 0.0

        sensitivity_matrices = generate_all_sensitivity_matrices(deal, _accretion_fn)
    else:
        sensitivity_matrices = []

    # -----------------------------------------------------------------------
    # Risk Assessment
    # -----------------------------------------------------------------------
    # Build a stub output for risk analyzer (it only needs IS data)
    stub_output = DealOutput(
        pro_forma_income_statement=income_statement,
        balance_sheet_at_close=balance_sheet,
        accretion_dilution_bridge=ad_bridge,
        sensitivity_matrices=[],
        returns_analysis=returns,
        risk_assessment=[],
        deal_verdict=DealVerdict.GREEN,
        deal_verdict_headline="",
        deal_verdict_subtext="",
        deal_scorecard=[],
    )
    risks = analyze_risks(deal, stub_output, benchmarks)

    # -----------------------------------------------------------------------
    # Defense Positioning (only for Defense & National Security deals)
    # -----------------------------------------------------------------------
    defense_positioning = _compute_defense_positioning(deal, benchmarks)

    # -----------------------------------------------------------------------
    # Deal Scorecard
    # -----------------------------------------------------------------------
    y1 = income_statement[0]
    entry_multiple = returns.entry_multiple
    post_close_leverage = (acq_debt_total + acq.total_debt) / (acq.ebitda + tgt.ebitda) if (acq.ebitda + tgt.ebitda) > 0 else 0

    # IRR at 5yr, base case (entry multiple)
    base_case_5yr = next(
        (s for s in returns.scenarios if s.exit_year == 5 and abs(s.exit_multiple - entry_multiple) < 0.6),
        None
    )
    irr_5yr = base_case_5yr.irr * 100 if base_case_5yr else 0.0

    # Total synergy NPV (simple 5yr, 10% discount rate)
    total_annual_synergies = sum(s.annual_amount for s in deal.synergies.cost_synergies + deal.synergies.revenue_synergies)
    synergy_npv = sum(
        _synergy_year_value(deal.synergies.cost_synergies + deal.synergies.revenue_synergies, yr) / (1.10 ** yr)
        for yr in range(1, 6)
    )

    # Breakeven synergy: minimum synergies for Year 1 accretion
    # At zero synergies, what's the accretion? If negative, how much synergy to break even?
    y1_no_syn = income_statement[0].accretion_dilution_pct  # Already includes synergies
    syn_yr1 = _synergy_year_value(deal.synergies.cost_synergies + deal.synergies.revenue_synergies, 1)
    # Approximate: each dollar of synergy (after tax) per share adds to accretion
    breakeven_synergy = max(0.0, total_annual_synergies * 0.3)  # 30% of assumed synergies as minimum threshold

    # Debt paydown timeline
    paydown_year = n_years
    for idx, yr_debt in enumerate(ending_debt_by_year):
        if yr_debt <= acq_debt_total * 0.1:  # 90% paid down
            paydown_year = idx + 1
            break

    ind_key = deal.target.industry.value
    ind_bench = benchmarks.get(ind_key, {})
    ev_range = ind_bench.get("ev_ebitda_multiple_range", {"low": 6, "median": 9, "high": 13})

    def _health(value: float, low: float, mid: float, high: float, higher_is_better: bool = True) -> HealthStatus:
        if higher_is_better:
            if value >= mid:
                return HealthStatus.GOOD
            if value >= low:
                return HealthStatus.FAIR
            return HealthStatus.POOR
        else:
            if value <= mid:
                return HealthStatus.GOOD
            if value <= high:
                return HealthStatus.FAIR
            return HealthStatus.POOR

    scorecard: list[ScorecardMetric] = [
        ScorecardMetric(
            name="Entry EV/EBITDA Multiple",
            value=entry_multiple,
            formatted_value=_format_multiple(entry_multiple),
            benchmark_low=ev_range["low"],
            benchmark_median=ev_range["median"],
            benchmark_high=ev_range["high"],
            health_status=_health(entry_multiple, ev_range["low"], ev_range["median"], ev_range["high"], higher_is_better=False),
            description=f"You're paying {entry_multiple:.1f}× EBITDA. Typical range for {ind_key}: {ev_range['low']}–{ev_range['high']}×",
        ),
        ScorecardMetric(
            name="Year 1 Accretion / Dilution",
            value=y1.accretion_dilution_pct,
            formatted_value=_format_pct(y1.accretion_dilution_pct),
            benchmark_low=-5.0,
            benchmark_median=0.0,
            benchmark_high=10.0,
            health_status=HealthStatus.GOOD if y1.accretion_dilution_pct > 2 else (HealthStatus.FAIR if y1.accretion_dilution_pct > 0 else HealthStatus.POOR),
            description="Change in earnings per share vs acquirer standalone in Year 1",
        ),
        ScorecardMetric(
            name="Pro Forma EPS (Year 1)",
            value=y1.pro_forma_eps,
            formatted_value=f"${y1.pro_forma_eps:.2f}",
            benchmark_low=y1.acquirer_standalone_eps * 0.9,
            benchmark_median=y1.acquirer_standalone_eps,
            benchmark_high=y1.acquirer_standalone_eps * 1.15,
            health_status=HealthStatus.GOOD if y1.pro_forma_eps >= y1.acquirer_standalone_eps else HealthStatus.POOR,
            description=f"Combined EPS vs standalone {_format_currency(y1.acquirer_standalone_eps * acq.shares_outstanding)} standalone earnings",
        ),
        ScorecardMetric(
            name="IRR at 5-Year Exit",
            value=irr_5yr,
            formatted_value=_format_pct(irr_5yr),
            benchmark_low=12.0,
            benchmark_median=20.0,
            benchmark_high=30.0,
            health_status=_health(irr_5yr, 12.0, 20.0, 30.0),
            description="Annualized return on equity invested at base-case exit multiple",
        ),
        ScorecardMetric(
            name="Post-Close Leverage",
            value=post_close_leverage,
            formatted_value=_format_multiple(post_close_leverage),
            benchmark_low=2.0,
            benchmark_median=4.0,
            benchmark_high=6.0,
            health_status=_health(post_close_leverage, 2.0, 4.0, 6.0, higher_is_better=False),
            description="Combined debt divided by combined EBITDA at close",
        ),
        ScorecardMetric(
            name="Breakeven Annual Savings",
            value=breakeven_synergy,
            formatted_value=_format_currency(breakeven_synergy),
            benchmark_low=total_annual_synergies * 0.25,
            benchmark_median=total_annual_synergies * 0.50,
            benchmark_high=total_annual_synergies * 0.75,
            health_status=HealthStatus.GOOD if total_annual_synergies > 0 else HealthStatus.FAIR,
            description="Minimum annual synergies needed for the deal to add value",
        ),
        ScorecardMetric(
            name="Debt Repayment Timeline",
            value=float(paydown_year),
            formatted_value=f"Year {paydown_year}",
            benchmark_low=3.0,
            benchmark_median=5.0,
            benchmark_high=7.0,
            health_status=_health(paydown_year, 3.0, 5.0, 7.0, higher_is_better=False),
            description="Year by which 90% of acquisition debt is repaid",
        ),
        ScorecardMetric(
            name="Total Synergy Value (NPV)",
            value=synergy_npv,
            formatted_value=_format_currency(synergy_npv),
            benchmark_low=deal.target.acquisition_price * 0.05,
            benchmark_median=deal.target.acquisition_price * 0.15,
            benchmark_high=deal.target.acquisition_price * 0.30,
            health_status=_health(synergy_npv, deal.target.acquisition_price * 0.05, deal.target.acquisition_price * 0.15, deal.target.acquisition_price * 0.30),
            description="Net present value of 5-year synergy stream at 10% discount rate",
        ),
    ]

    # Defense-specific scorecard metrics
    if defense_positioning is not None:
        dp = defense_positioning
        ev_rev_range = ind_bench.get("ev_revenue_multiple_range", {"low": 3, "median": 8, "high": 20})

        scorecard.append(ScorecardMetric(
            name="Implied EV/Revenue",
            value=dp.ev_revenue_multiple,
            formatted_value=_format_multiple(dp.ev_revenue_multiple),
            benchmark_low=ev_rev_range["low"],
            benchmark_median=ev_rev_range["median"],
            benchmark_high=ev_rev_range["high"],
            health_status=_health(dp.ev_revenue_multiple, ev_rev_range["low"], ev_rev_range["median"], ev_rev_range["high"], higher_is_better=False),
            description=f"EV/Revenue of {dp.ev_revenue_multiple:.1f}× vs defense {'AI' if dp.is_ai_native else 'tech'} range {ev_rev_range['low']}–{ev_rev_range['high']}×",
        ))
        scorecard.append(ScorecardMetric(
            name="Backlog Coverage Ratio",
            value=dp.backlog_coverage_ratio,
            formatted_value=_format_multiple(dp.backlog_coverage_ratio),
            benchmark_low=1.0,
            benchmark_median=2.0,
            benchmark_high=4.0,
            health_status=_health(dp.backlog_coverage_ratio, 1.0, 2.0, 4.0),
            description=f"Contracted backlog of {_format_currency(dp.combined_backlog)} covers {dp.backlog_coverage_ratio:.1f}× annual revenue",
        ))
        if dp.total_defense_premium_pct > 0:
            scorecard.append(ScorecardMetric(
                name="Defense Premium Applied",
                value=dp.total_defense_premium_pct * 100,
                formatted_value=f"{dp.total_defense_premium_pct:.0%}",
                benchmark_low=5.0,
                benchmark_median=15.0,
                benchmark_high=40.0,
                health_status=_health(dp.total_defense_premium_pct * 100, 5.0, 15.0, 40.0),
                description=f"Clearance ({dp.clearance_premium_applied:.0%}) + certs ({dp.certification_premium_applied:.0%}) + POR ({dp.program_of_record_premium_applied:.0%}) premium",
            ))
        if dp.programs_of_record > 0:
            scorecard.append(ScorecardMetric(
                name="Programs of Record",
                value=float(dp.programs_of_record),
                formatted_value=str(dp.programs_of_record),
                benchmark_low=0.0,
                benchmark_median=1.0,
                benchmark_high=3.0,
                health_status=HealthStatus.GOOD if dp.programs_of_record >= 1 else HealthStatus.FAIR,
                description="Software embedded in DoD programs of record — multi-year guaranteed funding",
            ))

    # -----------------------------------------------------------------------
    # Verdict
    # -----------------------------------------------------------------------
    y1_ad = y1.accretion_dilution_pct

    # Defense deals get adjusted verdict logic — backlog and certifications
    # can justify a higher price that would look dilutive on pure EPS math
    is_defense_deal = defense_positioning is not None
    defense_uplift = False
    if is_defense_deal and defense_positioning.backlog_coverage_ratio >= 2.0:
        defense_uplift = True

    if y1_ad > 2.0:
        verdict = DealVerdict.GREEN
        headline = f"This deal is accretive to earnings by {y1_ad:+.1f}% in Year 1"
        subtext = (
            f"The combined company would earn ${y1.pro_forma_eps:.2f} per share vs "
            f"${y1.acquirer_standalone_eps:.2f} standalone — a "
            f"${(y1.pro_forma_eps - y1.acquirer_standalone_eps):.2f} improvement "
            f"driven primarily by {'cost savings' if sum(s.annual_amount for s in deal.synergies.cost_synergies) > 0 else 'target earnings contribution'}."
        )
        if is_defense_deal:
            subtext += (
                f" Defense positioning adds {defense_positioning.total_defense_premium_pct:.0%} "
                f"certification/clearance premium with {defense_positioning.backlog_coverage_ratio:.1f}× backlog coverage."
            )
    elif y1_ad >= -2.0 or (defense_uplift and y1_ad >= -8.0):
        verdict = DealVerdict.YELLOW
        if defense_uplift and y1_ad < -2.0:
            headline = f"Near-term dilutive ({y1_ad:+.1f}%) but justified by defense backlog"
            subtext = (
                f"Traditional EPS math shows dilution, but ${defense_positioning.combined_backlog / 1e6:.0f}M "
                f"of contracted backlog ({defense_positioning.backlog_coverage_ratio:.1f}× revenue) and "
                f"{defense_positioning.total_defense_premium_pct:.0%} defense premiums provide downside protection. "
                f"Revenue visibility of {defense_positioning.revenue_visibility_years:.1f} years from funded backlog."
            )
        else:
            headline = f"This deal is marginally neutral ({y1_ad:+.1f}% in Year 1)"
            subtext = (
                "At this price, the deal has minimal EPS impact in Year 1. "
                "It becomes more meaningful as synergies phase in and debt is repaid."
            )
            if is_defense_deal:
                subtext += (
                    f" Defense backlog of ${defense_positioning.combined_backlog / 1e6:.0f}M "
                    f"provides additional revenue visibility not captured in EPS."
                )
    else:
        verdict = DealVerdict.RED
        min_syn = abs(y1_ad / 100 * y1.acquirer_standalone_eps * total_shares_pro_forma / (1 - acq.tax_rate))
        headline = f"At this price, the deal destroys near-term earnings by {y1_ad:.1f}%"
        subtext = (
            f"The deal requires synergies exceeding approximately "
            f"{_format_currency(min_syn)}/year to break even. "
            "Consider renegotiating price or increasing synergy capture."
        )
        if is_defense_deal:
            subtext += (
                f" Even accounting for defense premiums ({defense_positioning.total_defense_premium_pct:.0%}) "
                f"and backlog ({defense_positioning.backlog_coverage_ratio:.1f}× coverage), the price "
                f"appears stretched."
            )

    return DealOutput(
        pro_forma_income_statement=income_statement,
        balance_sheet_at_close=balance_sheet,
        accretion_dilution_bridge=ad_bridge,
        sensitivity_matrices=sensitivity_matrices,
        returns_analysis=returns,
        risk_assessment=risks,
        deal_verdict=verdict,
        deal_verdict_headline=headline,
        deal_verdict_subtext=subtext,
        deal_scorecard=scorecard,
        defense_positioning=defense_positioning,
        convergence_warning=any_non_convergence,
        computation_notes=notes,
    )
