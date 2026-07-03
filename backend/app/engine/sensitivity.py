# Licensed under the Business Source License 1.1 — see LICENSE file for details
"""
Sensitivity matrix generator.

Produces 2D sensitivity tables showing how accretion/dilution changes
across combinations of key deal variables. Used to build the interactive
heatmaps in the frontend.

Guarantees (audit fixes F-6 / F-7 / F-21):
  - The base-case cell always reproduces the headline base-run Year-1
    accretion — no synthetic assumptions are injected at the base point.
  - For zero-synergy deals the synergy axis switches to clearly-labeled
    ABSOLUTE dollar amounts (base = $0) instead of silently injecting a
    2%-of-revenue synergy into every column.
  - The leverage axis is sized off TARGET (acquisition) economics —
    turns × target EBITDA — and explicit debt tranches are rescaled
    proportionally. "(Base)" highlights are suppressed when no modeled
    point matches the actual deal.
  - Failed cells are returned as None / "n/a" with a note — never a
    silent 0.0.
"""
from __future__ import annotations

from typing import Callable, Optional

from .models import DealInput, SensitivityMatrix


def _format_cell(value: float) -> str:
    """Format a cell value as a percentage string."""
    return f"{value:+.1f}%"


def _format_currency_compact(value: float) -> str:
    """Format a dollar value compactly for axis labels.

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


def build_sensitivity_matrix(
    title: str,
    row_label: str,
    col_label: str,
    row_values: list[float],
    col_values: list[float],
    compute_fn: Callable[[float, float], Optional[float]],
    base_row_idx: int = -1,
    base_col_idx: int = -1,
    row_display_labels: list[str] | None = None,
    col_display_labels: list[str] | None = None,
    note: str | None = None,
) -> SensitivityMatrix:
    """
    Build a 2D sensitivity matrix by calling compute_fn(row_val, col_val)
    for each combination of row and column values.

    Failed cells (compute_fn returns None or raises) are stored as None with
    an "n/a" label and surfaced via the matrix note — never silently rendered
    as 0.0 (audit fix F-21).

    Args:
        title: Human-readable title for the matrix.
        row_label: Label for the row axis.
        col_label: Label for the column axis.
        row_values: List of values for the row dimension.
        col_values: List of values for the column dimension.
        compute_fn: Function(row_val, col_val) → accretion/dilution decimal,
            or None when the scenario cannot be computed.
        base_row_idx: Index of the base case row (-1 = none).
        base_col_idx: Index of the base case column (-1 = none).
        row_display_labels: Optional display labels with absolute values.
        col_display_labels: Optional display labels with absolute values.
        note: Optional assumption note attached to the matrix.

    Returns:
        SensitivityMatrix ready for serialization.
    """
    data: list[list[Optional[float]]] = []
    data_labels: list[list[str]] = []
    failed_cells = 0

    for row_val in row_values:
        row_data: list[Optional[float]] = []
        row_labels: list[str] = []
        for col_val in col_values:
            try:
                result = compute_fn(row_val, col_val)
            except Exception:
                result = None
            if result is None:
                failed_cells += 1
                row_data.append(None)
                row_labels.append("n/a")
            else:
                row_data.append(round(result, 4))
                row_labels.append(_format_cell(result * 100))
        data.append(row_data)
        data_labels.append(row_labels)

    if failed_cells > 0:
        failure_note = f"{failed_cells} cell(s) failed to compute and are shown as n/a."
        note = f"{note} {failure_note}" if note else failure_note

    return SensitivityMatrix(
        title=title,
        row_label=row_label,
        col_label=col_label,
        row_values=row_values,
        col_values=col_values,
        data=data,
        data_labels=data_labels,
        base_row_idx=base_row_idx,
        base_col_idx=base_col_idx,
        row_display_labels=row_display_labels or [],
        col_display_labels=col_display_labels or [],
        note=note,
    )


def generate_all_sensitivity_matrices(
    deal: DealInput,
    engine_fn: Callable[[DealInput], Optional[float]],
) -> list[SensitivityMatrix]:
    """
    Generate the standard suite of sensitivity matrices for a deal.

    Matrices generated:
    1. Purchase Price vs Total Synergies (rows = price premium%, cols = synergy)
    2. Purchase Price vs Cash/Stock Mix (rows = price premium%, cols = cash%)
    3. Interest Rate vs Leverage Multiple (rows = interest rate, cols = debt/target EBITDA)

    Args:
        deal: The baseline deal inputs.
        engine_fn: Function(deal) → Year 1 accretion/dilution decimal, or None
            when the scenario fails to compute.

    Returns:
        List of SensitivityMatrix objects.
    """
    matrices: list[SensitivityMatrix] = []

    # ------------------------------------------------------------------
    # 1. Purchase Price Premium vs Total Annual Synergies
    # ------------------------------------------------------------------
    base_price = deal.target.acquisition_price
    base_synergies = sum(
        s.annual_amount
        for s in deal.synergies.cost_synergies + deal.synergies.revenue_synergies
    )

    price_premiums = [-0.20, -0.10, 0.0, 0.10, 0.20, 0.30, 0.40]  # % change vs base
    price_base_idx = 2  # 0.0 premium

    # Build display labels with absolute values
    price_row_labels = []
    for p in price_premiums:
        abs_price = base_price * (1 + p)
        if p == 0:
            price_row_labels.append(f"{_format_currency_compact(abs_price)} (Base)")
        else:
            price_row_labels.append(f"{_format_currency_compact(abs_price)} ({p:+.0%})")

    syn_note: str | None = None
    if base_synergies > 0:
        # Deal has synergies: columns are achievement multipliers of the plan.
        # Multiplier 1.0 leaves the deal untouched, so the base cell always
        # equals the headline base-run accretion (audit fix F-6).
        synergy_multipliers = [0.0, 0.25, 0.50, 0.75, 1.0, 1.25, 1.50]
        syn_base_idx = 4    # 1.0 multiplier (100%)
        syn_col_values = [s * 100 for s in synergy_multipliers]

        syn_col_labels = []
        for s in synergy_multipliers:
            abs_syn = base_synergies * s
            if s == 1.0:
                syn_col_labels.append(f"{_format_currency_compact(abs_syn)} (Base)")
            else:
                syn_col_labels.append(f"{_format_currency_compact(abs_syn)}")

        def price_vs_synergy(price_prem: float, syn_mult_pct: float) -> Optional[float]:
            modified = _deep_copy_deal(deal)
            modified.target.acquisition_price = base_price * (1 + price_prem / 100.0)
            _scale_synergies(modified, syn_mult_pct / 100.0)
            return engine_fn(modified)

        matrices.append(build_sensitivity_matrix(
            title="Purchase Price vs Synergies",
            row_label="Purchase Price",
            col_label="Synergy Achievement",
            row_values=[p * 100 for p in price_premiums],
            col_values=syn_col_values,
            compute_fn=price_vs_synergy,
            base_row_idx=price_base_idx,
            base_col_idx=syn_base_idx,
            row_display_labels=price_row_labels,
            col_display_labels=syn_col_labels,
        ))
    else:
        # Zero-synergy deal (audit fix F-6): DO NOT inject a hidden synthetic
        # synergy — the base column is $0 (identical to the headline run), and
        # the other columns are clearly-labeled hypothetical ABSOLUTE cost
        # synergies expressed as % of target revenue.
        rev_fractions = [0.0, 0.005, 0.01, 0.015, 0.02, 0.025, 0.03]
        syn_dollars = [deal.target.revenue * f for f in rev_fractions]
        syn_base_idx = 0
        syn_col_values = syn_dollars  # absolute $M
        syn_note = (
            "Deal has no modeled synergies. Columns show hypothetical annual "
            "cost synergies (0–3% of target revenue, 3-year phase-in); the "
            "$0 column is the actual base case."
        )

        syn_col_labels = []
        for f, amt in zip(rev_fractions, syn_dollars):
            if amt <= 0:
                syn_col_labels.append("$0 (Base)")
            else:
                syn_col_labels.append(
                    f"{_format_currency_compact(amt)} ({f:.1%} of tgt rev)"
                )

        def price_vs_synergy_abs(price_prem: float, syn_amount: float) -> Optional[float]:
            modified = _deep_copy_deal(deal)
            modified.target.acquisition_price = base_price * (1 + price_prem / 100.0)
            if syn_amount > 0:
                from .models import SynergyItem
                modified.synergies.cost_synergies = [SynergyItem(
                    category="Hypothetical cost synergies",
                    annual_amount=syn_amount,
                    phase_in_years=3,
                    cost_to_achieve=0.0,
                )]
            return engine_fn(modified)

        matrices.append(build_sensitivity_matrix(
            title="Purchase Price vs Synergies",
            row_label="Purchase Price",
            col_label="Hypothetical Annual Synergies",
            row_values=[p * 100 for p in price_premiums],
            col_values=syn_col_values,
            compute_fn=price_vs_synergy_abs,
            base_row_idx=price_base_idx,
            base_col_idx=syn_base_idx,
            row_display_labels=price_row_labels,
            col_display_labels=syn_col_labels,
            note=syn_note,
        ))

    # ------------------------------------------------------------------
    # 2. Purchase Price Premium vs Cash/Stock Mix
    # ------------------------------------------------------------------
    cash_percentages = [0.0, 0.20, 0.40, 0.60, 0.80, 1.0]  # cash% (rest in stock)

    # Find base case for cash mix — highlight only if a modeled point actually
    # matches the deal's cash percentage
    actual_cash_pct = deal.structure.cash_percentage
    cash_base_idx = min(range(len(cash_percentages)), key=lambda i: abs(cash_percentages[i] - actual_cash_pct))
    if abs(cash_percentages[cash_base_idx] - actual_cash_pct) > 0.01:
        cash_base_idx = -1

    cash_col_labels = []
    for c in cash_percentages:
        label = f"{c:.0%} Cash"
        if abs(c - actual_cash_pct) < 0.01:
            label += " (Base)"
        cash_col_labels.append(label)

    def price_vs_cash_mix(price_prem: float, cash_pct: float) -> Optional[float]:
        modified = _deep_copy_deal(deal)
        modified.target.acquisition_price = base_price * (1 + price_prem / 100.0)
        # Normalize so cash + stock + debt = 1 (debt held constant)
        debt = modified.structure.debt_percentage
        remaining = 1.0 - debt
        if remaining <= 0:
            cash_frac = 0.0
            stock_frac = 0.0
        else:
            cash_frac = min(cash_pct / 100.0, remaining)
            stock_frac = remaining - cash_frac
        modified.structure.cash_percentage = cash_frac
        modified.structure.stock_percentage = stock_frac
        return engine_fn(modified)

    matrices.append(build_sensitivity_matrix(
        title="Purchase Price vs Cash/Stock Mix",
        row_label="Purchase Price",
        col_label="Cash % of Deal",
        row_values=[p * 100 for p in price_premiums],
        col_values=[c * 100 for c in cash_percentages],
        compute_fn=price_vs_cash_mix,
        base_row_idx=price_base_idx,
        base_col_idx=cash_base_idx,
        row_display_labels=price_row_labels,
        col_display_labels=cash_col_labels,
    ))

    # ------------------------------------------------------------------
    # 3. Interest Rate vs Leverage (Acquisition Debt / TARGET EBITDA)
    # ------------------------------------------------------------------
    # Audit fix F-7: leverage is sized off the TARGET / acquisition economics
    # (turns × target EBITDA vs purchase price), not combined EBITDA — sizing
    # off combined EBITDA pegged every column at the 95% cap whenever the
    # acquirer was larger than the target, making the axis dead.
    target_ebitda = deal.target.ebitda

    # Actual acquisition debt: explicit tranches when present, else debt% × price
    orig_tranche_total = sum(t.amount for t in deal.structure.debt_tranches)
    actual_acq_debt = (
        orig_tranche_total if deal.structure.debt_tranches
        else base_price * deal.structure.debt_percentage
    )

    interest_rates = [0.05, 0.06, 0.07, 0.08, 0.09, 0.10, 0.11]
    leverage_turns = [2.0, 3.0, 4.0, 5.0, 6.0, 7.0]  # Acquisition Debt / Target EBITDA

    # Find closest base case for interest rate and leverage
    actual_leverage = actual_acq_debt / target_ebitda if target_ebitda > 0 else 0.0
    actual_rate = 0.08  # default
    if deal.structure.debt_tranches and orig_tranche_total > 0:
        actual_rate = sum(t.amount * t.interest_rate for t in deal.structure.debt_tranches) / orig_tranche_total

    # Suppress "(Base)" highlight when no modeled point matches the actual deal
    rate_base_idx = min(range(len(interest_rates)), key=lambda i: abs(interest_rates[i] - actual_rate))
    if abs(interest_rates[rate_base_idx] - actual_rate) > 0.005:
        rate_base_idx = -1
    lev_base_idx = min(range(len(leverage_turns)), key=lambda i: abs(leverage_turns[i] - actual_leverage))
    if abs(leverage_turns[lev_base_idx] - actual_leverage) > 0.5:
        lev_base_idx = -1

    rate_row_labels = []
    for r in interest_rates:
        label = f"{r:.1%}"
        if abs(r - actual_rate) <= 0.005:
            label += " (Base)"
        rate_row_labels.append(label)

    lev_col_labels = []
    for lv in leverage_turns:
        label = f"{lv:.1f}×"
        if abs(lv - actual_leverage) <= 0.5:
            label += " (Base)"
        lev_col_labels.append(label)

    lev_note = None
    if lev_base_idx == -1:
        lev_note = (
            f"Actual deal leverage is {actual_leverage:.1f}× target EBITDA — "
            "outside the modeled 2–7× grid, so no column is highlighted as base."
        )

    def interest_vs_leverage(rate_pct: float, turns: float) -> Optional[float]:
        modified = _deep_copy_deal(deal)
        rate = rate_pct / 100.0
        # Size acquisition debt off target EBITDA; cap at 95% of purchase price
        new_debt = min(turns * target_ebitda, 0.95 * base_price)
        debt_pct = new_debt / base_price if base_price > 0 else 0.0
        remaining = 1.0 - debt_pct
        # Split remaining between cash and stock proportionally to the original mix
        orig_non_debt = (deal.structure.cash_percentage + deal.structure.stock_percentage)
        if orig_non_debt > 0:
            cash_frac = (deal.structure.cash_percentage / orig_non_debt) * remaining
            stock_frac = remaining - cash_frac
        else:
            cash_frac = remaining
            stock_frac = 0.0
        modified.structure.debt_percentage = debt_pct
        modified.structure.cash_percentage = cash_frac
        modified.structure.stock_percentage = stock_frac
        if modified.structure.debt_tranches and orig_tranche_total > 0:
            # Rescale explicit tranche amounts proportionally to the new total
            # debt (audit fix F-7 — amounts were previously never rescaled),
            # and apply the scenario interest rate to every tranche.
            scale = new_debt / orig_tranche_total
            for tranche in modified.structure.debt_tranches:
                tranche.amount = max(1e-9, tranche.amount * scale)
                tranche.interest_rate = rate
        else:
            # No tranches — model the scenario with a single synthetic tranche
            from .models import DebtTranche, AmortizationType
            if new_debt > 0:
                modified.structure.debt_tranches = [DebtTranche(
                    name="Term Loan",
                    amount=new_debt,
                    interest_rate=rate,
                    term_years=7,
                    amortization_type=AmortizationType.STRAIGHT_LINE,
                )]
            else:
                modified.structure.debt_tranches = []
        return engine_fn(modified)

    matrices.append(build_sensitivity_matrix(
        title="Interest Rate vs Leverage",
        row_label="Debt Interest Rate",
        col_label="Acquisition Debt / Target EBITDA",
        row_values=[r * 100 for r in interest_rates],
        col_values=leverage_turns,
        compute_fn=interest_vs_leverage,
        base_row_idx=rate_base_idx,
        base_col_idx=lev_base_idx,
        row_display_labels=rate_row_labels,
        col_display_labels=lev_col_labels,
        note=lev_note,
    ))

    return matrices


def _deep_copy_deal(deal: DealInput) -> DealInput:
    """Create a deep copy of a DealInput for sensitivity analysis."""
    return deal.model_copy(deep=True)


def _scale_synergies(deal: DealInput, multiplier: float) -> None:
    """Scale all synergy amounts by an achievement multiplier.

    Audit fix F-6: never injects synthetic synergies — a multiplier of 1.0 is
    a strict no-op, and zero-synergy deals use the absolute-dollar axis in
    generate_all_sensitivity_matrices instead of this helper.
    """
    if multiplier == 1.0:
        return
    kept_cost = []
    for s in deal.synergies.cost_synergies:
        s.annual_amount = s.annual_amount * multiplier
        if s.annual_amount > 0:
            kept_cost.append(s)
    kept_rev = []
    for s in deal.synergies.revenue_synergies:
        s.annual_amount = s.annual_amount * multiplier
        if s.annual_amount > 0:
            kept_rev.append(s)
    # SynergyItem.annual_amount must be > 0 per the model; drop zeroed items
    deal.synergies.cost_synergies = kept_cost
    deal.synergies.revenue_synergies = kept_rev
