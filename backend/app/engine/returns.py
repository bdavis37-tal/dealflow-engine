"""
IRR and MOIC return calculations for the acquirer's equity investment.

We compute returns at exit years 3, 5, 7 across a range of exit EV/EBITDA multiples
(entry multiple ± 2x in 0.5x steps).

IRR is computed using Newton-Raphson on the NPV function.

Cash balance at exit is modeled as cumulative free cash flow (NI + D&A - capex - WC)
minus mandatory and optional debt paydowns already captured in the debt schedule.
This replaces the prior heuristic of 50% of cumulative net income.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from .models import DealInput, ReturnsAnalysis, ReturnScenario


MAX_IRR_ITERATIONS = 200
IRR_TOLERANCE = 1e-8


def _npv(rate: float, cash_flows: list[float]) -> float:
    """
    Net Present Value of a series of cash flows at a given discount rate.
    cash_flows[0] is t=0 (initial investment, typically negative).
    """
    return sum(cf / (1 + rate) ** t for t, cf in enumerate(cash_flows))


def _irr(cash_flows: list[float]) -> float:
    """
    Compute IRR using Newton-Raphson iteration.

    Args:
        cash_flows: List where [0] is investment (negative) and subsequent
                    entries are cash inflows.

    Returns:
        IRR as a decimal (e.g., 0.20 for 20%). Returns -1.0 if not convergent.
    """
    # Validate that there's a sign change (necessary for IRR to exist)
    has_negative = any(cf < 0 for cf in cash_flows)
    has_positive = any(cf > 0 for cf in cash_flows)
    if not (has_negative and has_positive):
        return -1.0

    # Initial guess: 15% — reasonable for M&A transactions
    rate = 0.15

    for _ in range(MAX_IRR_ITERATIONS):
        npv = _npv(rate, cash_flows)
        # Derivative of NPV with respect to rate
        dnpv = sum(
            -t * cf / (1 + rate) ** (t + 1)
            for t, cf in enumerate(cash_flows)
        )
        if dnpv == 0:
            break
        new_rate = rate - npv / dnpv
        if abs(new_rate - rate) < IRR_TOLERANCE:
            return new_rate
        rate = new_rate

    return rate  # Best estimate even if not fully converged


def compute_returns(
    deal: DealInput,
    ebitda_by_year: list[float],
    net_income_by_year: list[float],
    ending_debt_by_year: list[float],
    fcf_by_year: list[float] | None = None,
) -> ReturnsAnalysis:
    """
    Compute IRR and MOIC across exit years and exit multiples.

    Equity value at exit:
      Exit EV = Exit EBITDA × Exit Multiple
      Exit Equity = Exit EV - Net Debt at Exit
      Net Debt at Exit = Ending Debt - Cumulative FCF retained as cash

    Cash at exit is derived from the cumulative FCF roll-forward. FCF that was
    used for optional debt paydown is already removed from ending_debt_by_year
    (the solver applies optional sweeps), so we track only remaining FCF as cash.

    Initial equity investment:
      = Cash used from acquirer's balance sheet + new stock issued
      (Debt financing is separate — equity return is on equity capital)

    Args:
        deal: Full deal input.
        ebitda_by_year: Pro forma EBITDA for years 1-N.
        net_income_by_year: Pro forma net income for years 1-N.
        ending_debt_by_year: Ending debt balance for years 1-N (post optional sweep).
        fcf_by_year: Free cash flow per year (NI + DA - capex - WC change).
            If not provided, approximated from net_income with 70% NI→FCF conversion.

    Returns:
        ReturnsAnalysis with scenarios across exit years and multiples.
    """
    acquisition_price = deal.target.acquisition_price
    struct = deal.structure

    # Equity invested = cash portion + fair value of stock issued
    # (Debt portion is financed — not the equity check)
    equity_invested = acquisition_price * (struct.cash_percentage + struct.stock_percentage)
    equity_invested = max(equity_invested, acquisition_price * 0.10)  # Floor at 10%

    # Entry multiple for reference
    target_ebitda = deal.target.ebitda
    entry_multiple = (acquisition_price / target_ebitda) if target_ebitda > 0 else 0.0

    # Exit multiple range: entry ± 2x in 0.5x steps
    exit_multiples = [
        round(entry_multiple + delta, 1)
        for delta in [-2.0, -1.5, -1.0, -0.5, 0.0, 0.5, 1.0, 1.5, 2.0]
        if (entry_multiple + delta) > 1.0  # Multiples must be positive
    ]

    exit_years = [y for y in [3, 5, 7] if y <= len(ebitda_by_year)]

    # Build cumulative cash balance roll-forward from FCF.
    # FCF used for optional debt paydown is already captured in ending_debt_by_year
    # (the circularity solver sweeps excess FCF to reduce debt). The remaining FCF
    # — beyond mandatory amortization and optional sweep — is retained as cash.
    # If fcf_by_year is not provided, use a conservative 70% NI→FCF conversion.
    if fcf_by_year is None:
        fcf_by_year = [ni * 0.70 for ni in net_income_by_year]

    # Cumulative cash = sum of annual FCF; negative FCF years draw down cash
    cumulative_cash_by_year: list[float] = []
    running_cash = 0.0
    for yr_fcf in fcf_by_year:
        running_cash = max(0.0, running_cash + yr_fcf)
        cumulative_cash_by_year.append(running_cash)

    scenarios: list[ReturnScenario] = []

    for exit_year in exit_years:
        exit_ebitda = ebitda_by_year[exit_year - 1] if exit_year <= len(ebitda_by_year) else ebitda_by_year[-1]
        ending_debt = ending_debt_by_year[exit_year - 1] if exit_year <= len(ending_debt_by_year) else 0.0
        cash_at_exit = cumulative_cash_by_year[exit_year - 1] if exit_year <= len(cumulative_cash_by_year) else 0.0

        net_debt_at_exit = max(0.0, ending_debt - cash_at_exit)

        for exit_mult in exit_multiples:
            exit_ev = exit_ebitda * exit_mult
            exit_equity = max(0.0, exit_ev - net_debt_at_exit)

            # Cash flows: [Year 0: -equity_invested, Year exit: +exit_equity]
            cash_flows = [-equity_invested] + [0.0] * (exit_year - 1) + [exit_equity]

            irr = _irr(cash_flows)
            moic = exit_equity / equity_invested if equity_invested > 0 else 0.0

            scenarios.append(ReturnScenario(
                exit_year=exit_year,
                exit_multiple=exit_mult,
                exit_enterprise_value=exit_ev,
                irr=max(-1.0, irr),  # Cap at -100%
                moic=moic,
            ))

    return ReturnsAnalysis(
        entry_multiple=entry_multiple,
        scenarios=scenarios,
    )
