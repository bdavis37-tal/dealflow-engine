# Licensed under the Business Source License 1.1 — see LICENSE file for details
"""
Risk identification and plain-English risk communication.

Evaluates a completed deal and generates actionable risk callouts with
tolerance bands — telling the user exactly how much headroom they have.
"""
from __future__ import annotations

from .models import (
    DealInput,
    DealOutput,
    RiskItem,
    RiskSeverity,
)


def _leverage_risk(
    deal: DealInput,
    output: DealOutput,
) -> RiskItem | None:
    """
    Leverage risk: high debt/EBITDA increases bankruptcy risk and limits flexibility.

    Thresholds (based on credit market norms):
      < 4.0x: Normal
      4.0x–6.0x: Elevated (Medium/High)
      > 6.0x: Critical
    """
    # Post-close net debt = acquisition debt + existing acquirer debt - combined cash
    acq_debt = deal.target.acquisition_price * deal.structure.debt_percentage
    total_debt = acq_debt + deal.acquirer.total_debt
    combined_ebitda = deal.acquirer.ebitda + deal.target.ebitda
    if combined_ebitda <= 0:
        return None

    leverage = total_debt / combined_ebitda
    threshold_medium = 4.0
    threshold_critical = 6.0

    if leverage < threshold_medium:
        return None  # No flag needed

    if leverage >= threshold_critical:
        severity = RiskSeverity.CRITICAL
        description = (
            f"Debt load is extremely high at {leverage:.1f}x EBITDA. "
            "This level of leverage significantly elevates default risk and will "
            "severely restrict the company's financial flexibility."
        )
    else:
        severity = RiskSeverity.HIGH if leverage > 5.0 else RiskSeverity.MEDIUM
        description = (
            f"Post-close leverage of {leverage:.1f}x EBITDA is above typical comfort "
            "levels for most lenders. The business has limited cushion if EBITDA "
            "underperforms projections."
        )

    # Tolerance band: max EBITDA decline before breach of 6x covenant
    ebitda_buffer = max(0.0, total_debt / threshold_critical - combined_ebitda)
    safe_ebitda = total_debt / threshold_critical
    decline_pct = (combined_ebitda - safe_ebitda) / combined_ebitda * 100

    return RiskItem(
        description=description,
        severity=severity,
        metric_name="Post-Close Debt / EBITDA",
        current_value=leverage,
        threshold_value=threshold_critical,
        tolerance_band=(
            f"Deal hits critical leverage threshold if EBITDA falls by more than "
            f"{decline_pct:.0f}% (to ${safe_ebitda/1e6:.1f}M)."
        ),
        plain_english=(
            f"For every $1 of annual profit, the combined company owes ${leverage:.1f} "
            "in debt. Most lenders get nervous above $4."
        ),
    )


def _synergy_execution_risk(
    deal: DealInput,
    output: DealOutput,
) -> RiskItem | None:
    """
    Synergy execution risk: are the assumed synergies realistic?

    Benchmark: synergies above 10% of target revenue are rarely achieved in full.
    Above 15% is considered aggressive; above 20% is a red flag.
    """
    target_revenue = deal.target.revenue
    if target_revenue <= 0:
        return None

    total_synergies = sum(
        s.annual_amount
        for s in deal.synergies.cost_synergies + deal.synergies.revenue_synergies
    )
    if total_synergies <= 0:
        return None

    synergy_pct = total_synergies / target_revenue

    threshold_medium = 0.08   # 8% of target revenue
    threshold_high = 0.15     # 15% of target revenue

    if synergy_pct < threshold_medium:
        return None

    severity = RiskSeverity.HIGH if synergy_pct >= threshold_high else RiskSeverity.MEDIUM
    description = (
        f"Assumed synergies of ${total_synergies/1e6:.1f}M represent "
        f"{synergy_pct:.0%} of target revenue. "
        + ("This is an aggressive assumption that is rarely fully achieved." if synergy_pct >= threshold_high
           else "This is above the typical range for comparable transactions.")
    )

    return RiskItem(
        description=description,
        severity=severity,
        metric_name="Synergies as % of Target Revenue",
        current_value=synergy_pct * 100,
        threshold_value=threshold_high * 100,
        tolerance_band=(
            f"Synergies must exceed ${target_revenue * 0.03 / 1e6:.1f}M/year "
            f"(3% of target revenue) for the deal to generate meaningful value."
        ),
        plain_english=(
            f"You're counting on saving ${total_synergies/1e6:.1f}M per year from combining "
            "these companies. Deals that assume large savings often end up capturing "
            "only 50-70% of what was projected."
        ),
    )


def _interest_rate_sensitivity_risk(
    deal: DealInput,
    output: DealOutput,
    base_accretion_pct: float,
) -> RiskItem | None:
    """
    Interest rate risk: how many basis points of rate increase would flip to dilution?

    Threshold: if < 200bp of headroom, flag.
    """
    acq_debt = deal.target.acquisition_price * deal.structure.debt_percentage
    if acq_debt <= 0:
        return None

    # Find the blended rate from tranches or default
    if deal.structure.debt_tranches:
        total_debt_amt = sum(t.amount for t in deal.structure.debt_tranches)
        if total_debt_amt > 0:
            blended_rate = sum(t.amount * t.interest_rate for t in deal.structure.debt_tranches) / total_debt_amt
        else:
            blended_rate = 0.08
    else:
        blended_rate = 0.08

    # Estimate: each 100bp increase adds ~(acq_debt * 0.01 * (1-tax)) to annual interest drag
    tax_rate = deal.acquirer.tax_rate
    shares = deal.acquirer.shares_outstanding
    if shares <= 0:
        return None

    # EPS impact per 100bp rate increase
    eps_drag_per_100bp = (acq_debt * 0.01 * (1 - tax_rate)) / shares

    # Current EPS accretion from output (Year 1)
    if output.pro_forma_income_statement:
        y1 = output.pro_forma_income_statement[0]
        current_eps_accretion = y1.pro_forma_eps - y1.acquirer_standalone_eps
    else:
        return None

    if current_eps_accretion <= 0:
        return None  # Already dilutive — other risks cover this

    # How many 100bp increments until dilutive?
    if eps_drag_per_100bp <= 0:
        return None

    breakeven_100bp = current_eps_accretion / eps_drag_per_100bp
    breakeven_bp = breakeven_100bp * 100
    breakeven_rate = blended_rate + (breakeven_bp / 10000)

    if breakeven_bp >= 200:
        return None  # Sufficient headroom

    severity = RiskSeverity.HIGH if breakeven_bp < 100 else RiskSeverity.MEDIUM
    description = (
        f"The deal is sensitive to interest rate changes. A rate increase of just "
        f"{breakeven_bp:.0f} basis points ({breakeven_bp/100:.2f}%) would eliminate "
        "all earnings benefit from the acquisition."
    )

    return RiskItem(
        description=description,
        severity=severity,
        metric_name="Rate Increase to Dilution (bp)",
        current_value=breakeven_bp,
        threshold_value=200.0,
        tolerance_band=(
            f"Deal remains accretive as long as borrowing rates stay below "
            f"{breakeven_rate:.2%}."
        ),
        plain_english=(
            f"If interest rates rise by more than {breakeven_bp:.0f} basis points "
            f"({breakeven_bp/100:.2f}%), this deal stops adding value. "
            "Current rates leave limited room for error."
        ),
    )


def _purchase_price_risk(
    deal: DealInput,
    benchmarks: dict,
) -> RiskItem | None:
    """
    Purchase price risk: implied entry multiple vs industry benchmarks.

    Flag if entry multiple > 1.5× the industry median EV/EBITDA.
    """
    target_ebitda = deal.target.ebitda
    if target_ebitda <= 0:
        return None

    entry_multiple = deal.target.acquisition_price / target_ebitda
    industry_key = deal.target.industry.value
    ind = benchmarks.get(industry_key, {})
    ev_range = ind.get("ev_ebitda_multiple_range", {})
    median_multiple = ev_range.get("median", 9.0)
    high_multiple = ev_range.get("high", 13.0)

    overpay_threshold = median_multiple * 1.5

    if entry_multiple < high_multiple:
        return None  # Within normal range

    severity = RiskSeverity.HIGH if entry_multiple > overpay_threshold else RiskSeverity.MEDIUM
    pct_above_median = (entry_multiple - median_multiple) / median_multiple * 100

    return RiskItem(
        description=(
            f"You're paying {entry_multiple:.1f}× EBITDA for the target, which is "
            f"{pct_above_median:.0f}% above the typical {median_multiple:.1f}× for "
            f"{deal.target.industry.value} companies. High entry prices require "
            "exceptional execution to generate returns."
        ),
        severity=severity,
        metric_name="Entry EV/EBITDA Multiple",
        current_value=entry_multiple,
        threshold_value=overpay_threshold,
        tolerance_band=(
            f"At the current price, EBITDA must grow to ${deal.target.acquisition_price / median_multiple / 1e6:.1f}M "
            f"to reach a fair {median_multiple:.1f}× multiple."
        ),
        plain_english=(
            f"You're paying a premium price — {entry_multiple:.1f}× annual earnings, "
            f"vs the typical {median_multiple:.1f}× for this type of business. "
            "You're betting on above-average performance to earn this back."
        ),
    )


def _integration_cost_risk(deal: DealInput) -> RiskItem | None:
    """
    Integration cost risk: if cost-to-achieve > Year 1 synergy value, flag.
    """
    year1_synergies = 0.0
    total_cost_to_achieve = 0.0

    for s in deal.synergies.cost_synergies + deal.synergies.revenue_synergies:
        # Year 1 synergy value based on phase-in
        year1_pct = 1.0 / s.phase_in_years
        year1_synergies += s.annual_amount * year1_pct
        total_cost_to_achieve += s.cost_to_achieve

    if year1_synergies <= 0 or total_cost_to_achieve <= 0:
        return None

    ratio = total_cost_to_achieve / year1_synergies

    if ratio <= 1.0:
        return None  # Costs < Year 1 synergies: acceptable

    severity = RiskSeverity.HIGH if ratio > 2.0 else RiskSeverity.MEDIUM

    return RiskItem(
        description=(
            f"One-time integration costs of ${total_cost_to_achieve/1e6:.1f}M exceed "
            f"Year 1 synergy benefits of ${year1_synergies/1e6:.1f}M by {ratio:.1f}×. "
            "The deal will be cash flow negative in the near term."
        ),
        severity=severity,
        metric_name="Integration Costs / Year 1 Synergies",
        current_value=ratio,
        threshold_value=1.0,
        tolerance_band=(
            f"Breakeven on integration investment occurs when cumulative synergies "
            f"reach ${total_cost_to_achieve/1e6:.1f}M — "
            f"approximately {ratio:.1f} years at current phase-in."
        ),
        plain_english=(
            f"The costs of combining these companies (${total_cost_to_achieve/1e6:.1f}M) "
            "outweigh what you'll save in the first year. You're investing upfront "
            "for future payoff."
        ),
    )


def _revenue_synergy_concentration_risk(deal: DealInput) -> RiskItem | None:
    """
    Revenue synergy concentration risk.

    Revenue synergies are notoriously harder to achieve than cost synergies.
    Flag if revenue synergies > 50% of total synergy value.
    """
    total_cost = sum(s.annual_amount for s in deal.synergies.cost_synergies)
    total_revenue = sum(s.annual_amount for s in deal.synergies.revenue_synergies)
    total = total_cost + total_revenue

    if total <= 0 or total_revenue <= 0:
        return None

    rev_pct = total_revenue / total

    if rev_pct < 0.50:
        return None

    severity = RiskSeverity.HIGH if rev_pct > 0.70 else RiskSeverity.MEDIUM

    return RiskItem(
        description=(
            f"{rev_pct:.0%} of your projected synergies come from revenue growth — "
            "selling more by combining the companies. Revenue synergies are significantly "
            "harder to achieve than cost synergies and often take longer to materialize."
        ),
        severity=severity,
        metric_name="Revenue Synergy % of Total",
        current_value=rev_pct * 100,
        threshold_value=50.0,
        tolerance_band=(
            f"Deal economics hold even if revenue synergies are zero, "
            f"as long as cost synergies of ${total_cost/1e6:.1f}M are achieved."
        ),
        plain_english=(
            "You're counting on growing revenue by combining these companies. "
            "That's harder than cutting costs — customers don't always respond "
            "the way you expect when companies merge."
        ),
    )


def analyze_risks(
    deal: DealInput,
    output: DealOutput,
    benchmarks: dict,
) -> list[RiskItem]:
    """
    Run all risk analyzers and return flagged risks sorted by severity.

    Args:
        deal: Deal inputs.
        output: Computed deal outputs.
        benchmarks: Industry benchmark data dict.

    Returns:
        List of RiskItems, sorted critical → high → medium → low.
    """
    base_accretion = 0.0
    if output.pro_forma_income_statement:
        base_accretion = output.pro_forma_income_statement[0].accretion_dilution_pct

    risk_functions = [
        lambda: _leverage_risk(deal, output),
        lambda: _synergy_execution_risk(deal, output),
        lambda: _interest_rate_sensitivity_risk(deal, output, base_accretion),
        lambda: _purchase_price_risk(deal, benchmarks),
        lambda: _integration_cost_risk(deal),
        lambda: _revenue_synergy_concentration_risk(deal),
    ]

    severity_order = {
        RiskSeverity.CRITICAL: 0,
        RiskSeverity.HIGH: 1,
        RiskSeverity.MEDIUM: 2,
        RiskSeverity.LOW: 3,
    }

    risks: list[RiskItem] = []
    for fn in risk_functions:
        try:
            risk = fn()
            if risk is not None:
                risks.append(risk)
        except Exception:
            pass  # Never let a risk analyzer crash the deal analysis

    risks.sort(key=lambda r: severity_order.get(r.severity, 4))
    return risks
