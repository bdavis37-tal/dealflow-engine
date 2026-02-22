"""
Iterative solver for the debt/interest/income circularity in leveraged deal models.

The circularity arises because:
  Interest Expense → Net Income → Free Cash Flow → Debt Paydown → Debt Balance → Interest Expense

We resolve this with a simple Newton-style iterative approach:
  1. Start with an initial guess for interest expense
  2. Compute net income → FCF → mandatory debt amortization → ending debt
  3. Compute new interest expense from ending debt balance
  4. Compare; repeat until convergence

Convergence tolerance: $1 or 0.01% of interest, whichever is smaller.
Max iterations: 100.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from .models import DebtTranche, AmortizationType

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 100
ABSOLUTE_TOLERANCE = 1.0          # $1
RELATIVE_TOLERANCE = 0.0001       # 0.01%


@dataclass
class DebtScheduleYear:
    """Debt schedule output for a single year, per tranche."""
    tranche_name: str
    beginning_balance: float
    scheduled_principal: float
    interest_expense: float
    ending_balance: float
    interest_rate: float


@dataclass
class SolverResult:
    """Output of the circularity solver for a single projection year."""
    total_interest_expense: float
    total_debt_paydown: float
    ending_debt_balance: float
    tranche_schedules: list[DebtScheduleYear]
    converged: bool
    iterations: int


def _scheduled_principal(tranche: DebtTranche, year: int, current_balance: float) -> float:
    """
    Compute mandatory principal payment for a given tranche in a given year.

    Args:
        tranche: The debt tranche definition.
        year: The projection year (1-indexed).
        current_balance: The tranche's beginning-of-year balance.

    Returns:
        Mandatory principal payment for the year.
    """
    if tranche.amortization_type == AmortizationType.INTEREST_ONLY:
        # No principal until final year
        if year == tranche.term_years:
            return current_balance
        return 0.0

    elif tranche.amortization_type == AmortizationType.BULLET:
        # Balloon payment in final year
        if year == tranche.term_years:
            return current_balance
        return 0.0

    else:
        # Straight-line amortization: equal principal each year
        if year > tranche.term_years:
            return 0.0
        annual_principal = tranche.amount / tranche.term_years
        return min(annual_principal, current_balance)


def solve_year(
    ebitda: float,
    da: float,
    capex: float,
    working_capital_change: float,
    tax_rate: float,
    tranche_balances: dict[str, float],
    tranches: list[DebtTranche],
    year: int,
) -> SolverResult:
    """
    Solve the debt/interest circularity for a single projection year.

    The circularity: EBITDA → EBIT → EBT (needs interest) → Net Income
    → FCF → Cash Available for Debt → Ending Balances → Interest Next Iteration

    Args:
        ebitda: EBITDA for the year (pre-interest, pre-tax).
        da: Total D&A for the year.
        capex: Total capex for the year.
        working_capital_change: Change in NWC (positive = cash outflow).
        tax_rate: Effective tax rate.
        tranche_balances: Dict of tranche_name → beginning balance.
        tranches: List of DebtTranche definitions.
        year: Current projection year (1-indexed).

    Returns:
        SolverResult with converged interest expense and debt schedule.
    """
    # Initial guess: interest expense = sum of (balance × rate) ignoring paydown
    initial_interest = sum(
        tranche_balances.get(t.name, 0.0) * t.interest_rate
        for t in tranches
    )

    prev_interest = initial_interest
    converged = False
    iterations = 0
    final_schedules: list[DebtScheduleYear] = []
    final_balances: dict[str, float] = {}

    for iteration in range(MAX_ITERATIONS):
        iterations = iteration + 1
        current_balances = dict(tranche_balances)
        schedules: list[DebtScheduleYear] = []
        total_interest = 0.0
        total_principal = 0.0

        # Compute interest on beginning balances (conventional: interest on BOY balance)
        for tranche in tranches:
            bal = current_balances.get(tranche.name, 0.0)
            if bal <= 0:
                continue
            interest = bal * tranche.interest_rate
            principal = _scheduled_principal(tranche, year, bal)

            total_interest += interest
            total_principal += principal

            schedules.append(DebtScheduleYear(
                tranche_name=tranche.name,
                beginning_balance=bal,
                scheduled_principal=principal,
                interest_expense=interest,
                ending_balance=max(0.0, bal - principal),
                interest_rate=tranche.interest_rate,
            ))

        # Check convergence against previous iteration's interest
        abs_diff = abs(total_interest - prev_interest)
        rel_diff = abs_diff / max(abs(prev_interest), 1.0)

        if abs_diff <= ABSOLUTE_TOLERANCE or rel_diff <= RELATIVE_TOLERANCE:
            converged = True
            final_schedules = schedules
            final_balances = {s.tranche_name: s.ending_balance for s in schedules}
            break

        prev_interest = total_interest

    if not converged:
        logger.warning(
            "Circularity solver did not converge in %d iterations (year %d). "
            "Using best estimate: interest=$%.0f",
            MAX_ITERATIONS,
            year,
            prev_interest,
        )
        final_schedules = schedules
        final_balances = {s.tranche_name: s.ending_balance for s in schedules}

    # Compute totals from final converged schedule
    total_interest_final = sum(s.interest_expense for s in final_schedules)
    total_paydown_final = sum(s.scheduled_principal for s in final_schedules)
    ending_debt_final = sum(s.ending_balance for s in final_schedules)

    return SolverResult(
        total_interest_expense=total_interest_final,
        total_debt_paydown=total_paydown_final,
        ending_debt_balance=ending_debt_final,
        tranche_schedules=final_schedules,
        converged=converged,
        iterations=iterations,
    )


def build_debt_schedule(
    tranches: list[DebtTranche],
    projection_years: int,
    ebitda_by_year: list[float],
    da_by_year: list[float],
    capex_by_year: list[float],
    tax_rate: float,
) -> tuple[list[SolverResult], bool]:
    """
    Build the full multi-year debt schedule, solving circularity each year.

    Returns:
        Tuple of (list of SolverResult per year, any_non_convergence_flag).
    """
    results: list[SolverResult] = []
    any_non_convergence = False

    # Initialize balances from original tranche amounts
    balances: dict[str, float] = {t.name: t.amount for t in tranches}

    for year in range(1, projection_years + 1):
        ebitda = ebitda_by_year[year - 1] if year <= len(ebitda_by_year) else 0.0
        da = da_by_year[year - 1] if year <= len(da_by_year) else 0.0
        capex = capex_by_year[year - 1] if year <= len(capex_by_year) else 0.0

        result = solve_year(
            ebitda=ebitda,
            da=da,
            capex=capex,
            working_capital_change=0.0,  # Simplified; NWC changes handled separately
            tax_rate=tax_rate,
            tranche_balances=balances,
            tranches=tranches,
            year=year,
        )

        if not result.converged:
            any_non_convergence = True

        # Roll forward balances from this year's ending balances
        balances = {s.tranche_name: s.ending_balance for s in result.tranche_schedules}
        # Zero out tranches not in schedules (fully paid)
        for t in tranches:
            if t.name not in balances:
                balances[t.name] = 0.0

        results.append(result)

    return results, any_non_convergence
