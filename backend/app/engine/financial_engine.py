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
from .benchmark_registry import BenchmarkView, evidence_analysis, resolve, policy, dilution_defaults

import json
import math
import os
from datetime import date

from .models import (
    AccretionDilutionBridge,
    BalanceSheetAtClose,
    ContributionAnalysis,
    ContributionRow,
    CreditMetrics,
    DealInput,
    DealOutput,
    DealVerdict,
    DefensePositioning,
    HealthStatus,
    ImpliedValuation,
    IncomeStatementYear,
    Industry,
    ScorecardMetric,
    SourcesAndUses,
    SourcesAndUsesItem,
    SynergyItem,
)
from .circularity_solver import build_debt_schedule, DebtTranche
from .ma_context import comparison, downside
from .purchase_price import compute_ppa, get_transaction_costs
from .returns import compute_returns
from .risk_analyzer import analyze_risks
from .sensitivity import generate_all_sensitivity_matrices


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_benchmarks():
    return BenchmarkView("ma")


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


def _cta_year_value(items: list[SynergyItem], year: int) -> float:
    """
    Cost-to-achieve expensed in a given year (audit fix F-12).

    Each synergy's one-time cost_to_achieve is expensed straight-line over its
    phase-in period (years 1..phase_in_years).
    """
    total = 0.0
    for item in items:
        if item.cost_to_achieve <= 0:
            continue
        n = max(1, item.phase_in_years)
        if year <= n:
            total += item.cost_to_achieve / n
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


def _safe_float(value: float, default: float = 0.0) -> float:
    """Replace NaN, Infinity, or None with a safe default."""
    if value is None or math.isnan(value) or math.isinf(value):
        return default
    return value


def _format_currency(value: float) -> str:
    """Format a dollar value for display.

    Per project convention, all monetary values are already in millions USD.
    E.g. value=50.0 means $50M.
    """
    abs_val = abs(value)
    sign = "-" if value < 0 else ""
    if abs_val >= 1000:
        return f"{sign}${abs_val/1000:.1f}B"
    if abs_val >= 1:
        return f"{sign}${abs_val:.1f}M"
    if abs_val >= 0.001:
        return f"{sign}${abs_val*1000:.0f}K"
    return f"{sign}$0"


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
        parts.append(f"Combined backlog of ${combined_backlog:.0f}M provides {revenue_visibility_years:.1f} years of revenue visibility")

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

@evidence_analysis
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

    # Unit-convention guard (audit fix F-8): all monetary inputs are expected in
    # MILLIONS USD (e.g. 50.0 = $50M). Inputs above $1 trillion-in-millions almost
    # certainly indicate raw-dollar inputs — warn but never raise.
    if (
        deal.acquirer.revenue > 1e6
        or deal.target.revenue > 1e6
        or deal.target.acquisition_price > 1e6
    ):
        notes.append(
            "Warning: inputs appear to be in raw dollars, but the engine convention "
            "is millions USD (e.g. 50.0 = $50M). Size-based defaults (fee tiers, "
            "interest rates) and formatted outputs will be misscaled."
        )

    # Fiscal year base: Year 1 = current calendar year
    fiscal_year_start = date.today().year

    # Use explicit debt tranches if provided, else build synthetic
    tranches = deal.structure.debt_tranches if deal.structure.debt_tranches else _build_synthetic_tranches(deal)
    acq_debt_total = sum(t.amount for t in tranches)

    n_years = deal.projection_years
    acq = deal.acquirer
    tgt = deal.target

    # Warn if any synergy phase-in exceeds projection horizon
    all_synergies = deal.synergies.cost_synergies + deal.synergies.revenue_synergies
    for syn in all_synergies:
        if syn.phase_in_years > n_years:
            notes.append(
                f"Synergy '{syn.category}' has a {syn.phase_in_years}-year phase-in "
                f"but projections only run {n_years} years — full run-rate is never reached."
            )
            break  # One warning is enough

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

    # acquisition_price is ENTERPRISE VALUE by convention (audit fix F-10).
    # The equity consideration (what is paid for the target's shares) backs out
    # target net debt: EV - debt + cash.
    enterprise_value = deal.target.acquisition_price
    equity_consideration = ppa.equity_consideration

    # Consideration split (cash/stock/debt percentages apply to EV — the total
    # transaction funding, since target debt is refinanced with new financing)
    cash_used = enterprise_value * deal.structure.cash_percentage

    # New shares issued (for stock consideration)
    new_shares_issued = 0.0
    if deal.structure.stock_percentage > 0 and acq.share_price > 0:
        stock_consideration = enterprise_value * deal.structure.stock_percentage
        new_shares_issued = stock_consideration / acq.share_price

    total_shares_pro_forma = acq.shares_outstanding + new_shares_issued

    # Foregone interest on cash consideration (audit fix F-3): cash paid out at
    # close no longer earns the short-term yield. Deducted pre-tax every year.
    cash_yield = deal.structure.cash_yield
    foregone_interest_annual = cash_used * cash_yield

    # Implied pre-existing below-EBIT items (mostly existing interest expense),
    # backed out so pro forma NI anchors to actual reported net income instead of
    # an EBITDA-margin rebuild that deleted them (audit fix F-2):
    #   existing items₀ = EBIT₀ - EBT₀ = (EBITDA - D&A) - NI / (1 - tax)
    # These are grown at each company's growth rate so the anchored EBT identity
    # holds exactly: EBT_yr = EBT₀ × (1+g)^yr + deal adjustments.
    acq_ebt0 = acq.net_income / (1 - acq.tax_rate) if acq.tax_rate < 1 else acq.net_income
    tgt_ebt0 = tgt.net_income / (1 - tgt.tax_rate) if tgt.tax_rate < 1 else tgt.net_income
    acq_existing_items0 = (acq.ebitda - acq.depreciation) - acq_ebt0
    tgt_existing_items0 = (tgt.ebitda - tgt.depreciation) - tgt_ebt0

    # Pre-compute yearly operating streams (also feeds the circularity solver
    # with consistent, synergy-inclusive, grown inputs — audit fix F-11)
    yr_acq_rev: list[float] = []
    yr_tgt_rev: list[float] = []
    yr_rev_syn: list[float] = []
    yr_cost_syn: list[float] = []
    yr_cta: list[float] = []
    yr_ebitda: list[float] = []
    yr_da: list[float] = []
    yr_capex: list[float] = []
    yr_existing_interest: list[float] = []
    solver_ebitda_by_year: list[float] = []

    for yr in range(1, n_years + 1):
        acq_g = (1 + acquirer_revenue_growth) ** yr
        tgt_g = (1 + target_growth) ** yr
        acq_rev_yr = acq.revenue * acq_g
        tgt_rev_yr = tgt.revenue * tgt_g
        # Revenue synergies contribute at the target's EBITDA margin, not at
        # 100% margin (audit fix F-13)
        rev_syn_yr = _synergy_year_value(deal.synergies.revenue_synergies, yr)
        cost_syn_yr = _synergy_year_value(deal.synergies.cost_synergies, yr)
        cta_yr = _cta_year_value(all_synergies, yr)

        ebitda_yr = (
            acq_rev_yr * acq_ebitda_margin
            + tgt_rev_yr * tgt_ebitda_margin
            + rev_syn_yr * tgt_ebitda_margin
            + cost_syn_yr
            - cta_yr
        )
        da_yr = (
            acq.depreciation * acq_g
            + tgt.depreciation * tgt_g
            + ppa.total_incremental_annual
        )
        capex_yr = acq.capex * acq_g + tgt.capex * tgt_g
        existing_int_yr = acq_existing_items0 * acq_g + tgt_existing_items0 * tgt_g

        yr_acq_rev.append(acq_rev_yr)
        yr_tgt_rev.append(tgt_rev_yr)
        yr_rev_syn.append(rev_syn_yr)
        yr_cost_syn.append(cost_syn_yr)
        yr_cta.append(cta_yr)
        yr_ebitda.append(ebitda_yr)
        yr_da.append(da_yr)
        yr_capex.append(capex_yr)
        yr_existing_interest.append(existing_int_yr)

        # The solver treats its "ebitda" input as pre-acquisition-interest,
        # pre-tax earnings + D&A. Net out other fixed charges (existing interest,
        # foregone cash yield, Year-1 fees) so solver FCF matches engine FCF.
        solver_ebitda_by_year.append(
            ebitda_yr
            - existing_int_yr
            - foregone_interest_annual
            - (transaction_costs if yr == 1 else 0.0)
        )

    # Solve circularity across all years
    debt_schedules, any_non_convergence = build_debt_schedule(
        tranches=tranches,
        projection_years=n_years,
        ebitda_by_year=solver_ebitda_by_year,
        da_by_year=yr_da,
        capex_by_year=yr_capex,
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
    # Deal-attributable (target + synergy) streams for the returns module (F-1)
    deal_ebitda_by_year: list[float] = []
    deal_fcf_by_year: list[float] = []

    for yr in range(1, n_years + 1):
        ds = debt_schedules[yr - 1]
        acq_g = (1 + acquirer_revenue_growth) ** yr
        tgt_g = (1 + target_growth) ** yr

        acq_rev_yr = yr_acq_rev[yr - 1]
        tgt_rev_yr = yr_tgt_rev[yr - 1]
        rev_syn_yr = yr_rev_syn[yr - 1]
        cost_syn_yr = yr_cost_syn[yr - 1]
        cta_yr = yr_cta[yr - 1]

        total_rev = acq_rev_yr + tgt_rev_yr + rev_syn_yr

        # COGS: synergy revenue carries target COGS (revenue synergies flow
        # through at the target's margins, not 100% — audit fix F-13)
        combined_cogs = (
            acq_rev_yr * (1 - acq_gross_margin_base)
            + (tgt_rev_yr + rev_syn_yr) * (1 - tgt_gross_margin_base)
        )
        gross_profit = total_rev - combined_cogs

        # SG&A: margin-gap based; cost synergies reduce it, synergy revenue adds
        # its share, and cost-to-achieve is expensed as an operating cost (F-12)
        acq_sga = acq_rev_yr * (acq_gross_margin_base - acq_ebitda_margin)
        tgt_sga = (tgt_rev_yr + rev_syn_yr) * (tgt_gross_margin_base - tgt_ebitda_margin)
        combined_sga = acq_sga + tgt_sga - cost_syn_yr + cta_yr

        ebitda = gross_profit - combined_sga  # == yr_ebitda[yr-1]

        # D&A: acquirer + target (grown) + PPA incremental
        da_total = yr_da[yr - 1]

        ebit = ebitda - da_total

        # Interest expense (audit fixes F-2 / F-3):
        #   acquisition interest (converged debt schedule)
        # + implied existing below-EBIT items for both companies (grown)
        # + foregone yield on cash consideration
        acquisition_interest_only = ds.total_interest_expense
        existing_int_yr = yr_existing_interest[yr - 1]
        interest_exp = acquisition_interest_only + existing_int_yr + foregone_interest_annual

        ebt = ebit - interest_exp

        # Transaction costs expensed in Year 1 (ASC 805)
        if yr == 1:
            ebt -= transaction_costs
            notes.append(f"Year 1 includes ${transaction_costs:.1f}M in transaction fees (one-time, per ASC 805).")

        taxes = max(0.0, ebt * acq.tax_rate)
        net_income = ebt - taxes

        pro_forma_eps = _safe_float(net_income / total_shares_pro_forma if total_shares_pro_forma > 0 else 0.0)

        # Acquirer standalone EPS (grows at 3% per year for simplicity)
        standalone_eps_yr = _safe_float(acq_standalone_eps * (1.03 ** yr))
        # Audit fix F-4: divide by |standalone EPS| so the sign of the accretion %
        # always matches the direction of the EPS change (an improvement from a
        # negative base is positive, a deterioration from a positive base is
        # negative). When standalone EPS <= 0 the percentage is Not Meaningful —
        # flagged via accretion_is_nm; judge the deal on the EPS delta.
        accretion_is_nm = standalone_eps_yr <= 0
        accretion_dilution_pct = _safe_float(
            (pro_forma_eps - standalone_eps_yr) / abs(standalone_eps_yr) * 100
            if standalone_eps_yr != 0 else 0.0
        )

        # Combined FCF: NI + D&A - capex - ALL debt paydown (mandatory + optional).
        # Audit fix F-5: mandatory principal is cash out the door too — subtracting
        # only the optional sweep double-counted those dollars in exit equity.
        capex_yr = yr_capex[yr - 1]
        fcf_yr = net_income + da_total - capex_yr - ds.total_debt_paydown

        # Deal-attributable earnings & FCF (target + synergies + deal effects) —
        # the stream the returns module values (audit fix F-1)
        syn_eff_yr = cost_syn_yr + rev_syn_yr * tgt_ebitda_margin
        deal_ebt_yr = (
            tgt_ebt0 * tgt_g
            + syn_eff_yr
            - cta_yr
            - ppa.total_incremental_annual
            - acquisition_interest_only
            - foregone_interest_annual
            - (transaction_costs if yr == 1 else 0.0)
        )
        deal_ni_yr = deal_ebt_yr * (1 - acq.tax_rate)
        deal_ebitda_yr = (
            tgt_rev_yr * tgt_ebitda_margin + syn_eff_yr - cta_yr
        )
        deal_fcf_yr = (
            deal_ni_yr
            + tgt.depreciation * tgt_g
            + ppa.total_incremental_annual
            - tgt.capex * tgt_g
            - ds.total_debt_paydown
        )

        ebitda_by_year.append(ebitda)
        net_income_by_year.append(net_income)
        ending_debt_by_year.append(ds.ending_debt_balance)
        fcf_by_year.append(fcf_yr)
        deal_ebitda_by_year.append(deal_ebitda_yr)
        deal_fcf_by_year.append(deal_fcf_yr)

        income_statement.append(IncomeStatementYear(
            year=yr,
            fiscal_year_label=f"FY{fiscal_year_start + yr - 1}E",
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
            accretion_is_nm=accretion_is_nm,
            # Pro forma adjustment detail
            acquirer_revenue=acq_rev_yr,
            target_revenue=tgt_rev_yr,
            synergy_revenue=rev_syn_yr,
            acquirer_ebitda=acq_rev_yr * acq_ebitda_margin,
            target_ebitda=tgt_rev_yr * tgt_ebitda_margin,
            synergy_cost=cost_syn_yr,
            incremental_da=ppa.total_incremental_annual,
            acquisition_interest=acquisition_interest_only,
            existing_interest=existing_int_yr,
            foregone_cash_interest=foregone_interest_annual,
            integration_costs=cta_yr,
            transaction_costs=transaction_costs if yr == 1 else 0.0,
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
        # Interest drag = NEW acquisition debt only (existing interest is part of
        # each company's standalone earnings, already in the anchored baseline)
        interest_drag = -(acquisition_interest_only * (1 - acq.tax_rate)) / total_shares_pro_forma if total_shares_pro_forma > 0 else 0.0
        # Foregone yield on cash consideration (audit fix F-3)
        foregone_drag = -(foregone_interest_annual * (1 - acq.tax_rate)) / total_shares_pro_forma if total_shares_pro_forma > 0 else 0.0
        da_adj = -(ppa.total_incremental_annual * (1 - acq.tax_rate)) / total_shares_pro_forma if total_shares_pro_forma > 0 else 0.0
        # Synergies net of cost-to-achieve; revenue synergies at target margin (F-12/F-13)
        syn_benefit = ((syn_eff_yr - cta_yr) * (1 - acq.tax_rate)) / total_shares_pro_forma if total_shares_pro_forma > 0 else 0.0
        share_dilution = (
            # EPS is diluted because the same standalone NI is spread over more shares
            -((acq_standalone_ni_yr / total_shares_pro_forma) - standalone_eps_yr)
            if new_shares_issued > 0 and total_shares_pro_forma > 0 else 0.0
        )

        # Sum of explicit components
        components_sum = (
            target_earnings_contribution
            + interest_drag
            + foregone_drag
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
            foregone_interest_drag=foregone_drag,
            tax_impact=tax_impact,
            total_accretion_dilution=total_bridge,
            total_accretion_dilution_pct=accretion_dilution_pct,
        ))

    # -----------------------------------------------------------------------
    # Balance Sheet at Close (simplified opening BS with balancing plug — F-22)
    # -----------------------------------------------------------------------
    # Assets: acquirer book assets (proxied) + target intangibles + goodwill + PP&E writeup
    acq_combined_assets = (acq.revenue * 1.2) + ppa.goodwill + ppa.identifiable_intangibles + ppa.asset_writeup
    assets_before_plug = acq_combined_assets + tgt.revenue * 0.8

    # Liabilities: acquirer existing debt + new acquisition debt + DTL on step-ups
    combined_total_liabilities = (
        acq.total_debt
        + acq_debt_total
        + ppa.deferred_tax_liability  # DTL from PP&E and intangible step-ups (ASC 805)
    )
    # Equity: acquirer market cap + new shares at issue price
    combined_equity = acq.market_cap + new_shares_issued * acq.share_price

    # Balancing plug (audit fix F-22): the asset side is a revenue-based proxy,
    # so it will not tie to L+E exactly. Plug the difference into assets so the
    # statement balances, and disclose it.
    balancing_plug = (combined_total_liabilities + combined_equity) - assets_before_plug
    combined_total_assets = assets_before_plug + balancing_plug
    if abs(balancing_plug) > 0.5:  # > $0.5M
        notes.append(
            f"Opening balance sheet is simplified (revenue-based asset proxies); "
            f"a balancing plug of {_format_currency(balancing_plug)} was applied to "
            f"total assets so that Assets = Liabilities + Equity."
        )

    balance_sheet = BalanceSheetAtClose(
        goodwill=ppa.goodwill,
        identifiable_intangibles=ppa.identifiable_intangibles,
        ppe_writeup=ppa.asset_writeup,
        new_acquisition_debt=acq_debt_total,
        cash_used=cash_used,
        shares_issued=new_shares_issued,
        target_equity_eliminated=max(0.0, tgt.working_capital + tgt.cash_on_hand - tgt.total_debt),
        combined_total_assets=combined_total_assets,
        combined_total_liabilities=combined_total_liabilities,
        combined_equity=combined_equity,
        balancing_plug=balancing_plug,
    )

    # -----------------------------------------------------------------------
    # Returns Analysis — on the deal-attributable (target + synergy) stream (F-1)
    # -----------------------------------------------------------------------
    returns = compute_returns(
        deal,
        deal_ebitda_by_year=deal_ebitda_by_year,
        ending_debt_by_year=ending_debt_by_year,
        deal_fcf_by_year=deal_fcf_by_year,
        transaction_costs=transaction_costs,
    )
    notes.extend(returns.notes)

    # -----------------------------------------------------------------------
    # Sensitivity Matrices
    # -----------------------------------------------------------------------
    if include_sensitivity:
        def _accretion_fn(modified_deal: DealInput) -> float | None:
            """Quick re-run for sensitivity — returns Year 1 accretion as decimal.
            Calls run_deal with include_sensitivity=False to prevent recursive re-entry.
            Returns None when the scenario fails to compute (audit fix F-21) —
            never silently 0.0, which would render as a plausible "flat" cell.
            """
            try:
                out = run_deal(modified_deal, include_sensitivity=False)
                if out.pro_forma_income_statement:
                    return out.pro_forma_income_statement[0].accretion_dilution_pct / 100
                return None
            except Exception:
                return None

        sensitivity_matrices = generate_all_sensitivity_matrices(deal, _accretion_fn)
        for m in sensitivity_matrices:
            if m.note and "failed" in m.note:
                notes.append(f"Sensitivity matrix '{m.title}': {m.note}")
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
    risks, ai_benchmark_context = analyze_risks(deal, stub_output, benchmarks)

    # -----------------------------------------------------------------------
    # Defense Positioning (only for Defense & National Security deals)
    # -----------------------------------------------------------------------
    defense_positioning = _compute_defense_positioning(deal, benchmarks)

    # -----------------------------------------------------------------------
    # Sources & Uses of Funds (audit fixes F-9 / F-10)
    # Uses = equity purchase (EV - debt + cash) + target debt refinance + fees.
    # Sources = consideration funding + target cash acquired; any remaining gap
    # (typically the fees and refinance) is funded from acquirer balance-sheet
    # cash so the table always balances.
    # -----------------------------------------------------------------------
    stock_issued_value = new_shares_issued * acq.share_price

    uses: list[SourcesAndUsesItem] = [
        SourcesAndUsesItem(label="Purchase of Target Equity", amount=equity_consideration),
    ]
    if tgt.total_debt > 0:
        uses.append(SourcesAndUsesItem(label="Refinance Target Debt", amount=tgt.total_debt))
    if transaction_costs > 0:
        uses.append(SourcesAndUsesItem(label="Transaction Fees & Expenses", amount=transaction_costs))

    sources: list[SourcesAndUsesItem] = []
    if cash_used > 0:
        sources.append(SourcesAndUsesItem(label="Cash from Acquirer", amount=cash_used))
    if acq_debt_total > 0:
        sources.append(SourcesAndUsesItem(label="New Debt Financing", amount=acq_debt_total))
    if stock_issued_value > 0:
        sources.append(SourcesAndUsesItem(label="Stock Issuance", amount=stock_issued_value))
    if tgt.cash_on_hand > 0:
        sources.append(SourcesAndUsesItem(label="Target Cash Acquired", amount=tgt.cash_on_hand))

    funding_gap = sum(u.amount for u in uses) - sum(s.amount for s in sources)
    additional_acquirer_cash = 0.0
    if funding_gap > 0.005:
        additional_acquirer_cash = funding_gap
        sources.append(SourcesAndUsesItem(
            label="Additional Cash from Acquirer (fees / refinancing)",
            amount=additional_acquirer_cash,
        ))
    elif funding_gap < -0.005:
        # Sources exceed uses (e.g. oversized debt tranches) — excess goes to the
        # combined balance sheet as cash.
        uses.append(SourcesAndUsesItem(
            label="Cash to Combined Balance Sheet",
            amount=-funding_gap,
        ))

    total_sources = sum(s.amount for s in sources)
    total_uses = sum(u.amount for u in uses)

    sources_and_uses = SourcesAndUses(
        sources=sources,
        uses=uses,
        total_sources=total_sources,
        total_uses=total_uses,
        balanced=abs(total_sources - total_uses) < max(0.01, 0.001 * max(total_sources, 1.0)),
    )

    # Cash sufficiency validation (audit fixes F-3 / F-9): warn — never raise —
    # when the acquirer's balance-sheet cash cannot cover its cash obligations.
    total_acquirer_cash_needed = cash_used + additional_acquirer_cash
    if total_acquirer_cash_needed > acq.cash_on_hand + 0.005:
        notes.append(
            f"Warning: acquirer cash required at close "
            f"({_format_currency(total_acquirer_cash_needed)} including fees/refinancing) "
            f"exceeds cash on hand ({_format_currency(acq.cash_on_hand)}). "
            f"The deal is underfunded as structured — increase debt or stock consideration."
        )

    # -----------------------------------------------------------------------
    # Contribution Analysis
    # -----------------------------------------------------------------------
    def _pct(a: float, b: float) -> tuple[float, float]:
        total = a + b
        if total == 0:
            return 0.0, 0.0
        return a / total, b / total

    contrib_rows: list[ContributionRow] = []
    for metric_name, acq_val, tgt_val in [
        ("Revenue", acq.revenue, tgt.revenue),
        ("EBITDA", acq.ebitda, tgt.ebitda),
        ("Net Income", acq.net_income, tgt.net_income),
    ]:
        a_pct, t_pct = _pct(acq_val, tgt_val)
        contrib_rows.append(ContributionRow(
            metric=metric_name,
            acquirer_value=acq_val,
            target_value=tgt_val,
            acquirer_pct=a_pct,
            target_pct=t_pct,
        ))

    # Implied ownership from stock consideration
    implied_own_target = new_shares_issued / total_shares_pro_forma if total_shares_pro_forma > 0 else 0.0
    implied_own_acquirer = 1.0 - implied_own_target

    contribution_analysis = ContributionAnalysis(
        rows=contrib_rows,
        implied_ownership_acquirer=implied_own_acquirer,
        implied_ownership_target=implied_own_target,
    )

    # -----------------------------------------------------------------------
    # Credit Metrics (Post-Close)
    # -----------------------------------------------------------------------
    combined_ebitda_close = acq.ebitda + tgt.ebitda
    total_post_close_debt = acq_debt_total + acq.total_debt
    # Net debt (audit fix F-18): net BOTH the acquirer's remaining cash (after
    # cash consideration, fees, and any refinancing gap funded from cash) AND
    # the target cash acquired in the transaction.
    acq_remaining_cash = max(0.0, acq.cash_on_hand - total_acquirer_cash_needed)
    net_debt_close = total_post_close_debt - acq_remaining_cash - tgt.cash_on_hand
    y1_interest = income_statement[0].interest_expense if income_statement else 0.0
    y1_capex = acq.capex + tgt.capex
    # Mandatory amortization from year 1 debt schedule
    y1_mandatory_amort = 0.0
    if debt_schedules:
        y1_mandatory_amort = debt_schedules[0].total_debt_paydown - debt_schedules[0].optional_cash_sweep

    credit_metrics = CreditMetrics(
        total_debt_to_ebitda=_safe_float(total_post_close_debt / combined_ebitda_close if combined_ebitda_close > 0 else 0.0),
        net_debt_to_ebitda=_safe_float(net_debt_close / combined_ebitda_close if combined_ebitda_close > 0 else 0.0),
        interest_coverage=_safe_float(combined_ebitda_close / y1_interest if y1_interest > 0 else 99.9),
        fixed_charge_coverage=_safe_float(
            (combined_ebitda_close - y1_capex) / (y1_interest + y1_mandatory_amort)
            if (y1_interest + y1_mandatory_amort) > 0 else 99.9
        ),
        debt_to_total_cap=_safe_float(
            total_post_close_debt / (total_post_close_debt + combined_equity)
            if (total_post_close_debt + combined_equity) > 0 else 0.0
        ),
    )

    # -----------------------------------------------------------------------
    # Implied Valuation Metrics (audit fix F-10)
    # acquisition_price IS the enterprise value; equity value backs out net debt.
    # EV multiples use EV; P/E uses the equity consideration.
    # -----------------------------------------------------------------------
    ev = enterprise_value
    # NTM EBITDA for the EV multiple must be target-side (EV was paid for the
    # target, not the combined company): target Year 1 EBITDA.
    ntm_target_ebitda = (
        tgt.revenue * (1 + target_growth) * tgt_ebitda_margin if tgt.revenue > 0 else tgt.ebitda
    )

    implied_valuation = ImpliedValuation(
        enterprise_value=ev,
        equity_value=equity_consideration,
        ev_revenue_ltm=_safe_float(ev / tgt.revenue if tgt.revenue > 0 else 0.0),
        ev_ebitda_ltm=_safe_float(ev / tgt.ebitda if tgt.ebitda > 0 else 0.0),
        ev_ebitda_ntm=_safe_float(ev / ntm_target_ebitda if ntm_target_ebitda > 0 else 0.0),
        price_to_earnings=_safe_float(equity_consideration / tgt.net_income if tgt.net_income > 0 else 0.0),
    )

    # -----------------------------------------------------------------------
    # Deal Scorecard
    # -----------------------------------------------------------------------
    y1 = income_statement[0]
    entry_multiple = _safe_float(returns.entry_multiple)
    post_close_leverage = _safe_float(
        (acq_debt_total + acq.total_debt) / (acq.ebitda + tgt.ebitda) if (acq.ebitda + tgt.ebitda) > 0 else 0
    )

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

    # Breakeven synergy (audit fix F-14): closed-form Year-1 EPS-neutral synergy.
    # Year-1 NI is linear in pre-tax synergies S (in the taxable region):
    #   NI(S) = NI_actual + (S - S_actual) × (1 - tax)
    # EPS-neutral requires NI(S) = standalone_EPS₁ × pro forma shares, so:
    #   S* = S_actual + (required_NI - NI_actual) / (1 - tax)
    y1_is = income_statement[0]
    required_ni_y1 = y1_is.acquirer_standalone_eps * total_shares_pro_forma
    syn_y1_effective = (
        _synergy_year_value(deal.synergies.cost_synergies, 1)
        + _synergy_year_value(deal.synergies.revenue_synergies, 1) * tgt_ebitda_margin
    )
    tax_factor = (1 - acq.tax_rate) if y1_is.ebt > 0 else 1.0  # NI = EBT when EBT <= 0
    breakeven_synergy = max(
        0.0,
        syn_y1_effective + (required_ni_y1 - y1_is.net_income) / tax_factor
        if tax_factor > 0 else 0.0,
    )

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
            formatted_value=_format_multiple(entry_multiple) if tgt.ebitda > 0 else "N/M",
            benchmark_low=ev_range["low"],
            benchmark_median=ev_range["median"],
            benchmark_high=ev_range["high"],
            health_status=_health(entry_multiple, ev_range["low"], ev_range["median"], ev_range["high"], higher_is_better=False) if tgt.ebitda > 0 else HealthStatus.FAIR,
            description=f"You're paying {entry_multiple:.1f}× EBITDA. Assumed sector range for {ind_key}: {ev_range['low']}–{ev_range['high']}×",
        ),
        ScorecardMetric(
            name="Year 1 Accretion / Dilution",
            value=y1.accretion_dilution_pct,
            formatted_value="NM" if y1.accretion_is_nm else _format_pct(y1.accretion_dilution_pct),
            benchmark_low=-5.0,
            benchmark_median=0.0,
            benchmark_high=10.0,
            health_status=HealthStatus.GOOD if y1.accretion_dilution_pct > 2 else (HealthStatus.FAIR if y1.accretion_dilution_pct > 0 else HealthStatus.POOR),
            description=(
                "Change in earnings per share vs acquirer standalone in Year 1"
                + (" (% is Not Meaningful — standalone EPS is negative; judge the EPS delta)" if y1.accretion_is_nm else "")
            ),
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
                description="Software embedded in DoD programs of record — program association; future funding is not guaranteed",
            ))

    # -----------------------------------------------------------------------
    # Verdict
    # -----------------------------------------------------------------------
    # Audit fix F-4: with the abs(standalone) convention, the sign of the
    # accretion % always matches the direction of the Year-1 EPS delta, so the
    # thresholds below remain valid even for a loss-making acquirer. When
    # standalone EPS <= 0 the % magnitude is Not Meaningful — the verdict is
    # effectively driven by the EPS delta and the copy references the delta.
    y1_ad = y1.accretion_dilution_pct
    y1_eps_delta = y1.pro_forma_eps - y1.acquirer_standalone_eps
    y1_is_nm = y1.accretion_is_nm

    def _ad_text() -> str:
        """Human-readable Year-1 impact — % when meaningful, $ delta when NM."""
        if y1_is_nm:
            return f"${y1_eps_delta:+.2f} EPS vs a negative standalone base"
        return f"{y1_ad:+.1f}%"

    is_defense_deal = defense_positioning is not None

    if y1_ad > 2.0:
        verdict = DealVerdict.GREEN
        headline = (
            f"This deal improves Year 1 EPS by {_ad_text()}" if y1_is_nm
            else f"This deal is accretive to earnings by {y1_ad:+.1f}% in Year 1"
        )
        subtext = (
            f"The combined company would earn ${y1.pro_forma_eps:.2f} per share vs "
            f"${y1.acquirer_standalone_eps:.2f} standalone — a "
            f"${y1_eps_delta:.2f} improvement "
            f"driven primarily by {'cost savings' if sum(s.annual_amount for s in deal.synergies.cost_synergies) > 0 else 'target earnings contribution'}."
        )
        if y1_is_nm:
            subtext += (
                " Standalone EPS is negative, so the accretion percentage is not "
                "meaningful — the verdict is based on the dollar EPS improvement."
            )
        if is_defense_deal:
            subtext += (
                f" Illustrative defense assumptions show {defense_positioning.total_defense_premium_pct:.0%} "
                f"certification/clearance adjustment with {defense_positioning.backlog_coverage_ratio:.1f}× backlog coverage."
            )
    elif y1_ad >= -2.0:
        verdict = DealVerdict.YELLOW
        headline = f"This deal is marginally neutral ({_ad_text()} in Year 1)"
        subtext = (
            "At this price, the deal has minimal EPS impact in Year 1. "
            "It becomes more meaningful as synergies phase in and debt is repaid."
        )
        if y1_is_nm:
            subtext += (
                " Standalone EPS is negative, so percentage accretion is not "
                "meaningful — judge the dollar EPS delta."
            )
        if is_defense_deal:
            subtext += (
                f" Defense backlog of ${defense_positioning.combined_backlog:.0f}M "
                f"provides additional revenue visibility not captured in EPS."
            )
    else:
        verdict = DealVerdict.RED
        # Pre-tax annual synergies needed to close the Year-1 EPS gap
        min_syn = abs(y1_eps_delta) * total_shares_pro_forma / max(1e-9, (1 - acq.tax_rate))
        headline = (
            f"At this price, the deal worsens Year 1 EPS by ${abs(y1_eps_delta):.2f}" if y1_is_nm
            else f"At this price, the deal destroys near-term earnings by {y1_ad:.1f}%"
        )
        subtext = (
            f"The deal requires synergies exceeding approximately "
            f"{_format_currency(min_syn)}/year to break even. "
            "Consider renegotiating price or increasing synergy capture."
        )


    return DealOutput(
        valuation_comparison=comparison(deal),
        downside_scenarios=downside(deal) if include_sensitivity else [],
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
        sources_and_uses=sources_and_uses,
        contribution_analysis=contribution_analysis,
        credit_metrics=credit_metrics,
        implied_valuation=implied_valuation,
        fiscal_year_start=fiscal_year_start,
        defense_positioning=defense_positioning,
        ai_modifier_applied=deal.target.is_ai_native and ai_benchmark_context is not None and "fallback" not in ai_benchmark_context,
        ai_benchmark_context=ai_benchmark_context,
        convergence_warning=any_non_convergence,
        computation_notes=notes,
    )
