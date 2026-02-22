"""
Sensitivity matrix generator.

Produces 2D sensitivity tables showing how accretion/dilution changes
across combinations of key deal variables. Used to build the interactive
heatmaps in the frontend.
"""
from __future__ import annotations

import copy
from typing import Callable

from .models import DealInput, SensitivityMatrix


def _format_cell(value: float) -> str:
    """Format a cell value as a percentage string."""
    return f"{value:+.1f}%"


def build_sensitivity_matrix(
    title: str,
    row_label: str,
    col_label: str,
    row_values: list[float],
    col_values: list[float],
    compute_fn: Callable[[float, float], float],
) -> SensitivityMatrix:
    """
    Build a 2D sensitivity matrix by calling compute_fn(row_val, col_val)
    for each combination of row and column values.

    Args:
        title: Human-readable title for the matrix.
        row_label: Label for the row axis.
        col_label: Label for the column axis.
        row_values: List of values for the row dimension.
        col_values: List of values for the column dimension.
        compute_fn: Function(row_val, col_val) → accretion/dilution %.

    Returns:
        SensitivityMatrix ready for serialization.
    """
    data: list[list[float]] = []
    data_labels: list[list[str]] = []

    for row_val in row_values:
        row_data: list[float] = []
        row_labels: list[str] = []
        for col_val in col_values:
            result = compute_fn(row_val, col_val)
            row_data.append(round(result, 4))
            row_labels.append(_format_cell(result * 100))
        data.append(row_data)
        data_labels.append(row_labels)

    return SensitivityMatrix(
        title=title,
        row_label=row_label,
        col_label=col_label,
        row_values=row_values,
        col_values=col_values,
        data=data,
        data_labels=data_labels,
    )


def generate_all_sensitivity_matrices(
    deal: DealInput,
    engine_fn: Callable[[DealInput], float],
) -> list[SensitivityMatrix]:
    """
    Generate the standard suite of sensitivity matrices for a deal.

    Matrices generated:
    1. Purchase Price vs Total Synergies (rows = price premium%, cols = synergy$)
    2. Purchase Price vs Cash/Stock Mix (rows = price premium%, cols = cash%)
    3. Interest Rate vs Leverage Multiple (rows = interest rate, cols = debt/EBITDA)

    Args:
        deal: The baseline deal inputs.
        engine_fn: Function(deal) → Year 1 accretion/dilution % (decimal).

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
    synergy_multipliers = [0.0, 0.25, 0.50, 0.75, 1.0, 1.25, 1.50]

    def price_vs_synergy(price_prem: float, syn_mult: float) -> float:
        modified = _deep_copy_deal(deal)
        modified.target.acquisition_price = base_price * (1 + price_prem)
        _scale_synergies(modified, syn_mult, base_synergies)
        return engine_fn(modified)

    matrices.append(build_sensitivity_matrix(
        title="Purchase Price vs Synergies",
        row_label="Price Premium vs Base",
        col_label="Synergy Achievement (%)",
        row_values=[p * 100 for p in price_premiums],
        col_values=[s * 100 for s in synergy_multipliers],
        compute_fn=price_vs_synergy,
    ))

    # ------------------------------------------------------------------
    # 2. Purchase Price Premium vs Cash/Stock Mix
    # ------------------------------------------------------------------
    cash_percentages = [0.0, 0.20, 0.40, 0.60, 0.80, 1.0]  # cash% (rest in stock)

    def price_vs_cash_mix(price_prem: float, cash_pct: float) -> float:
        modified = _deep_copy_deal(deal)
        modified.target.acquisition_price = base_price * (1 + price_prem)
        stock_pct = 1.0 - (cash_pct / 100.0) - modified.structure.debt_percentage
        cash_frac = cash_pct / 100.0
        # Normalize so cash + stock + debt = 1
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
        row_label="Price Premium vs Base",
        col_label="Cash % of Deal",
        row_values=[p * 100 for p in price_premiums],
        col_values=[c * 100 for c in [0.0, 0.20, 0.40, 0.60, 0.80, 1.0]],
        compute_fn=price_vs_cash_mix,
    ))

    # ------------------------------------------------------------------
    # 3. Interest Rate vs Leverage (Debt/EBITDA at Close)
    # ------------------------------------------------------------------
    target_ebitda = deal.target.ebitda
    combined_ebitda = deal.acquirer.ebitda + target_ebitda
    base_debt = base_price * deal.structure.debt_percentage

    interest_rates = [0.05, 0.06, 0.07, 0.08, 0.09, 0.10, 0.11]
    leverage_turns = [2.0, 3.0, 4.0, 5.0, 6.0, 7.0]  # Debt / Combined EBITDA

    def interest_vs_leverage(rate_pct: float, turns: float) -> float:
        modified = _deep_copy_deal(deal)
        rate = rate_pct / 100.0
        total_debt_implied = combined_ebitda * turns
        debt_pct = min(total_debt_implied / base_price, 0.95)
        remaining = 1.0 - debt_pct
        # Split remaining between cash and stock proportionally
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
        # Adjust all tranche interest rates
        for tranche in modified.structure.debt_tranches:
            tranche.interest_rate = rate
        # If no tranches, the engine uses blended rate — set via a synthetic tranche
        if not modified.structure.debt_tranches:
            from .models import DebtTranche, AmortizationType
            modified.structure.debt_tranches = [DebtTranche(
                name="Term Loan",
                amount=base_price * debt_pct,
                interest_rate=rate,
                term_years=7,
                amortization_type=AmortizationType.STRAIGHT_LINE,
            )]
        return engine_fn(modified)

    matrices.append(build_sensitivity_matrix(
        title="Interest Rate vs Leverage",
        row_label="Debt Interest Rate (%)",
        col_label="Total Debt / EBITDA (×)",
        row_values=[r * 100 for r in interest_rates],
        col_values=leverage_turns,
        compute_fn=interest_vs_leverage,
    ))

    return matrices


def _deep_copy_deal(deal: DealInput) -> DealInput:
    """Create a deep copy of a DealInput for sensitivity analysis."""
    return deal.model_copy(deep=True)


def _scale_synergies(deal: DealInput, multiplier: float, base_total: float) -> None:
    """Scale synergy amounts by a multiplier relative to base total."""
    if base_total <= 0:
        # Add a minimal cost synergy if none exist
        if multiplier > 0:
            from .models import SynergyItem
            deal.synergies.cost_synergies = [SynergyItem(
                category="Combined savings",
                annual_amount=deal.target.revenue * 0.02 * multiplier,
                phase_in_years=3,
                cost_to_achieve=0.0,
            )]
        return

    for s in deal.synergies.cost_synergies + deal.synergies.revenue_synergies:
        s.annual_amount = s.annual_amount * multiplier
