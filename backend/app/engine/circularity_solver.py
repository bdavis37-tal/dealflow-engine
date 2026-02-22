"""
Iterative solver for the debt/interest/income circularity in leveraged deal models.

The circularity arises because:
  Interest Expense → Net Income → Free Cash Flow → Debt Paydown → Debt Balance → Interest Expense

We resolve this with an iterative approach using average-balance interest:
  1. Guess interest expense (BOY balance × rate as starting estimate).
  2. Compute EBIT, EBT, NI, FCF from operating inputs.
  3. Apply mandatory scheduled amortization per tranche.
  4. Apply optional cash sweep (excess FCF) in waterfall order (highest rate first).
  5. Compute ending balances.
  6. Recompute interest on average balance ((BOY + EOY) / 2).
  7. Compare to previous iteration; apply damping.
  8. Repeat until convergence or max iterations.

NOTE: Prior convention used beginning-of-year (BOY) balances for interest, which
removed the intra-year circular dependency but also prevented FCF-driven paydown
from affecting interest within the year. This implementation switches to average-
balance interest to model the full circularity accurately. The change is documented
here per CLAUDE.md convention.

Convergence tolerance: $1 or 0.01% of interest, whichever is smaller.
Max iterations: 100. Damping factor: 0.5 (prevents oscillation).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from .models import DebtTranche, AmortizationType

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 100
ABSOLUTE_TOLERANCE = 1.0          # $1
RELATIVE_TOLERANCE = 0.0001       # 0.01%
DAMPING = 0.5                     # Blend old/new estimate to prevent oscillation


@dataclass
class DebtScheduleYear:
    """Debt schedule output for a single year, per tranche."""
    tranche_name: str
    beginning_balance: float
    scheduled_principal: float
    optional_paydown: float
    interest_expense: float
    ending_balance: float
    interest_rate: float


@dataclass
class SolverResult:
    """Output of the circularity solver for a single projection year."""
    total_interest_expense: float
    total_debt_paydown: float
    optional_cash_sweep: float
    ending_debt_balance: float
    tranche_schedules: list[DebtScheduleYear]
    converged: bool
    iterations: int
    net_income: float
    free_cash_flow: float


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

    The circular dependency:
      EBITDA - DA - Interest = EBT → NI → FCF → Optional Debt Paydown
      → Ending Balance → Average Balance → Interest  (circular)

    Interest is computed on the average of beginning and ending balances
    to capture the FCF → paydown → interest feedback loop within the year.

    Args:
        ebitda: EBITDA for the year (pre-interest, pre-tax).
        da: Total D&A for the year.
        capex: Total capex for the year.
        working_capital_change: Change in NWC (positive = cash outflow).
        tax_rate: Effective tax rate.
        tranche_balances: Dict of tranche_name → beginning-of-year balance.
        tranches: List of DebtTranche definitions.
        year: Current projection year (1-indexed).

    Returns:
        SolverResult with converged interest expense, debt schedule, and FCF.
    """
    if not tranches:
        return SolverResult(
            total_interest_expense=0.0,
            total_debt_paydown=0.0,
            optional_cash_sweep=0.0,
            ending_debt_balance=0.0,
            tranche_schedules=[],
            converged=True,
            iterations=0,
            net_income=max(0.0, (ebitda - da) * (1 - tax_rate)),
            free_cash_flow=max(0.0, (ebitda - da) * (1 - tax_rate)) + da - capex - working_capital_change,
        )

    # Mandatory principal per tranche (fixed, independent of interest)
    tranche_mandatory: dict[str, float] = {}
    total_mandatory = 0.0
    for tranche in tranches:
        bal = tranche_balances.get(tranche.name, 0.0)
        if bal <= 0:
            tranche_mandatory[tranche.name] = 0.0
            continue
        principal = _scheduled_principal(tranche, year, bal)
        tranche_mandatory[tranche.name] = principal
        total_mandatory += principal

    # Initial interest guess: BOY balances × rate (no paydown yet)
    prev_interest = sum(
        tranche_balances.get(t.name, 0.0) * t.interest_rate
        for t in tranches
        if tranche_balances.get(t.name, 0.0) > 0
    )

    converged = False
    iterations = 0
    final_schedules: list[DebtScheduleYear] = []
    final_ni = 0.0
    final_fcf = 0.0

    # Waterfall order: highest interest rate first for optional paydown
    sorted_tranches = sorted(tranches, key=lambda t: t.interest_rate, reverse=True)

    for iteration in range(MAX_ITERATIONS):
        iterations = iteration + 1

        # Step 1: compute NI and FCF with current interest estimate
        ebit = ebitda - da
        ebt = ebit - prev_interest
        taxes = max(0.0, ebt * tax_rate)
        net_income = ebt - taxes
        fcf = net_income + da - capex - working_capital_change

        # Step 2: optional cash sweep — excess FCF after mandatory amortization
        optional_available = max(0.0, fcf - total_mandatory)
        tranche_optional: dict[str, float] = {t.name: 0.0 for t in tranches}
        remaining = optional_available
        for tranche in sorted_tranches:
            if remaining <= 0:
                break
            boy_bal = tranche_balances.get(tranche.name, 0.0)
            after_mandatory = boy_bal - tranche_mandatory.get(tranche.name, 0.0)
            if after_mandatory <= 0:
                continue
            sweep = min(remaining, after_mandatory)
            tranche_optional[tranche.name] = sweep
            remaining -= sweep

        # Step 3: compute ending balances and average-balance interest
        total_new_interest = 0.0
        schedules: list[DebtScheduleYear] = []

        for tranche in tranches:
            boy_bal = tranche_balances.get(tranche.name, 0.0)
            if boy_bal <= 0:
                continue
            mandatory = tranche_mandatory.get(tranche.name, 0.0)
            optional_sweep = tranche_optional.get(tranche.name, 0.0)
            ending_bal = max(0.0, boy_bal - mandatory - optional_sweep)

            # Average balance captures the timing of paydown within the year
            avg_balance = (boy_bal + ending_bal) / 2.0
            interest = avg_balance * tranche.interest_rate
            total_new_interest += interest

            schedules.append(DebtScheduleYear(
                tranche_name=tranche.name,
                beginning_balance=boy_bal,
                scheduled_principal=mandatory,
                optional_paydown=optional_sweep,
                interest_expense=interest,
                ending_balance=ending_bal,
                interest_rate=tranche.interest_rate,
            ))

        # Step 4: check convergence
        abs_diff = abs(total_new_interest - prev_interest)
        rel_diff = abs_diff / max(abs(prev_interest), 1.0)

        final_schedules = schedules
        final_ni = net_income
        final_fcf = fcf

        if abs_diff <= ABSOLUTE_TOLERANCE or rel_diff <= RELATIVE_TOLERANCE:
            converged = True
            break

        # Apply damping: blend old and new to prevent oscillation
        prev_interest = DAMPING * prev_interest + (1.0 - DAMPING) * total_new_interest

    if not converged:
        logger.warning(
            "Circularity solver did not converge in %d iterations (year %d). "
            "Using best estimate: interest=$%.0f",
            MAX_ITERATIONS,
            year,
            prev_interest,
        )

    # Compute totals from final converged schedule
    total_interest_final = sum(s.interest_expense for s in final_schedules)
    total_mandatory_final = sum(s.scheduled_principal for s in final_schedules)
    total_optional_final = sum(s.optional_paydown for s in final_schedules)
    ending_debt_final = sum(s.ending_balance for s in final_schedules)

    return SolverResult(
        total_interest_expense=total_interest_final,
        total_debt_paydown=total_mandatory_final + total_optional_final,
        optional_cash_sweep=total_optional_final,
        ending_debt_balance=ending_debt_final,
        tranche_schedules=final_schedules,
        converged=converged,
        iterations=iterations,
        net_income=final_ni,
        free_cash_flow=final_fcf,
    )


def build_debt_schedule(
    tranches: list[DebtTranche],
    projection_years: int,
    ebitda_by_year: list[float],
    da_by_year: list[float],
    capex_by_year: list[float],
    tax_rate: float,
    wc_change_by_year: list[float] | None = None,
) -> tuple[list[SolverResult], bool]:
    """
    Build the full multi-year debt schedule, solving circularity each year.

    Args:
        tranches: Debt tranche definitions.
        projection_years: Number of years to project.
        ebitda_by_year: Pre-interest, pre-tax EBITDA for each year.
        da_by_year: Total D&A for each year.
        capex_by_year: Total capital expenditures for each year.
        tax_rate: Effective tax rate (used for FCF computation).
        wc_change_by_year: Working capital change per year (positive = outflow).
            Defaults to zero each year if not provided.

    Returns:
        Tuple of (list of SolverResult per year, any_non_convergence_flag).
    """
    results: list[SolverResult] = []
    any_non_convergence = False

    if wc_change_by_year is None:
        wc_change_by_year = [0.0] * projection_years

    # Initialize balances from original tranche amounts
    balances: dict[str, float] = {t.name: t.amount for t in tranches}

    for year in range(1, projection_years + 1):
        ebitda = ebitda_by_year[year - 1] if year <= len(ebitda_by_year) else 0.0
        da = da_by_year[year - 1] if year <= len(da_by_year) else 0.0
        capex = capex_by_year[year - 1] if year <= len(capex_by_year) else 0.0
        wc_change = wc_change_by_year[year - 1] if year <= len(wc_change_by_year) else 0.0

        result = solve_year(
            ebitda=ebitda,
            da=da,
            capex=capex,
            working_capital_change=wc_change,
            tax_rate=tax_rate,
            tranche_balances=balances,
            tranches=tranches,
            year=year,
        )

        if not result.converged:
            any_non_convergence = True

        # Roll forward balances from this year's ending balances
        balances = {s.tranche_name: s.ending_balance for s in result.tranche_schedules}
        # Zero out tranches not in schedules (fully paid or had zero balance)
        for t in tranches:
            if t.name not in balances:
                balances[t.name] = 0.0

        results.append(result)

    return results, any_non_convergence
