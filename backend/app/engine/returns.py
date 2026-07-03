# Licensed under the Business Source License 1.1 — see LICENSE file for details
"""
IRR and MOIC return calculations for the acquirer's equity investment in the DEAL.

CONVENTION (audit fix F-1): the return is computed on the TARGET-SIDE economics —
the exit value is (target + synergy) EBITDA × exit multiple, i.e. the stream of
earnings the acquirer bought — NOT the whole combined company. Valuing the
combined acquirer+target against a target-only equity check wildly overstates
IRR/MOIC (the acquirer's own pre-existing earnings are not a return on the deal).

Equity invested (audit fix F-19): cash consideration + stock consideration +
transaction fees, with NO artificial floor. When the equity check is ~zero
(e.g. ~100% debt-financed), IRR/MOIC are not meaningful and a note is returned
instead of a fabricated number.

Exit equity:
  Exit EV       = deal EBITDA at exit × exit multiple
  Exit equity   = max(0, Exit EV - net acquisition debt at exit)
  Net debt      = ending acquisition debt - cumulative deal-attributable FCF

Deal-attributable FCF already subtracts ALL debt paydown (mandatory + optional,
audit fix F-5), so debt repaid out of cash flow is not double counted: the
paydown reduces cumulative cash by exactly the amount it reduces ending debt.
Cumulative cash is allowed to go negative (paydowns funded beyond deal FCF
increase effective net debt attributable to the deal).

IRR is computed with Newton-Raphson and a bisection fallback (audit fix F-20);
the solver never raises and guards against rates <= -100%.

All monetary values are in millions USD.
"""
from __future__ import annotations

import math

from .models import DealInput, ReturnsAnalysis, ReturnScenario


MAX_IRR_ITERATIONS = 200
IRR_TOLERANCE = 1e-8
_MIN_RATE = -0.9999   # Never evaluate NPV at rate <= -1
_MAX_RATE = 100.0     # 10,000% — beyond any sane M&A outcome


def _npv(rate: float, cash_flows: list[float]) -> float:
    """
    Net Present Value of a series of cash flows at a given discount rate.
    cash_flows[0] is t=0 (initial investment, typically negative).
    """
    return sum(cf / (1 + rate) ** t for t, cf in enumerate(cash_flows))


def _irr_bisection(cash_flows: list[float]) -> float:
    """Robust bisection fallback for IRR on [-99.99%, +10,000%]."""
    lo, hi = _MIN_RATE, _MAX_RATE
    f_lo = _npv(lo, cash_flows)
    f_hi = _npv(hi, cash_flows)
    if f_lo * f_hi > 0:
        # No sign change in bracket — no IRR in a meaningful range.
        # Return the boundary closer to zero NPV.
        return lo if abs(f_lo) < abs(f_hi) else hi
    for _ in range(200):
        mid = (lo + hi) / 2.0
        f_mid = _npv(mid, cash_flows)
        if abs(f_mid) < IRR_TOLERANCE or (hi - lo) < IRR_TOLERANCE:
            return mid
        if f_lo * f_mid <= 0:
            hi, f_hi = mid, f_mid
        else:
            lo, f_lo = mid, f_mid
    return (lo + hi) / 2.0


def _irr(cash_flows: list[float]) -> float:
    """
    Compute IRR using Newton-Raphson with a bisection fallback.

    Args:
        cash_flows: List where [0] is investment (negative) and subsequent
                    entries are cash inflows.

    Returns:
        IRR as a decimal (e.g., 0.20 for 20%). Never raises; returns -1.0
        when no IRR exists (no sign change in cash flows).
    """
    # Validate that there's a sign change (necessary for IRR to exist)
    has_negative = any(cf < 0 for cf in cash_flows)
    has_positive = any(cf > 0 for cf in cash_flows)
    if not (has_negative and has_positive):
        return -1.0

    # Initial guess: 15% — reasonable for M&A transactions
    rate = 0.15

    for _ in range(MAX_IRR_ITERATIONS):
        try:
            npv = _npv(rate, cash_flows)
            # Derivative of NPV with respect to rate
            dnpv = sum(
                -t * cf / (1 + rate) ** (t + 1)
                for t, cf in enumerate(cash_flows)
            )
        except (OverflowError, ZeroDivisionError):
            return _irr_bisection(cash_flows)
        if dnpv == 0:
            return _irr_bisection(cash_flows)
        new_rate = rate - npv / dnpv
        # Guard: Newton stepped out of the valid domain — fall back to bisection
        if new_rate <= _MIN_RATE or new_rate > _MAX_RATE or math.isnan(new_rate):
            return _irr_bisection(cash_flows)
        if abs(new_rate - rate) < IRR_TOLERANCE:
            return new_rate
        rate = new_rate

    # Did not converge — use the robust fallback
    return _irr_bisection(cash_flows)


def compute_returns(
    deal: DealInput,
    deal_ebitda_by_year: list[float],
    ending_debt_by_year: list[float],
    deal_fcf_by_year: list[float],
    transaction_costs: float = 0.0,
) -> ReturnsAnalysis:
    """
    Compute IRR and MOIC across exit years and exit multiples on the
    deal-attributable (target + synergy) earnings stream.

    Args:
        deal: Full deal input (acquisition_price is ENTERPRISE VALUE).
        deal_ebitda_by_year: Target + synergy EBITDA (net of integration costs)
            for years 1-N — the stream the exit multiple is applied to.
        ending_debt_by_year: Ending acquisition-debt balance for years 1-N
            (post mandatory amortization and optional sweep).
        deal_fcf_by_year: Deal-attributable free cash flow per year, AFTER all
            debt paydown (mandatory + optional).
        transaction_costs: One-time fees paid at close (part of the equity check).

    Returns:
        ReturnsAnalysis with scenarios across exit years and multiples.
    """
    acquisition_price = deal.target.acquisition_price  # EV by convention
    struct = deal.structure

    # Equity invested = cash + stock consideration + transaction fees.
    # No artificial floor (audit fix F-19) — a ~100% debt deal has ~zero equity
    # and its IRR/MOIC are flagged as not meaningful instead.
    equity_invested = (
        acquisition_price * (struct.cash_percentage + struct.stock_percentage)
        + max(0.0, transaction_costs)
    )

    notes: list[str] = []
    min_meaningful_equity = max(0.01 * acquisition_price, 1e-9)
    equity_is_meaningful = equity_invested > min_meaningful_equity
    if not equity_is_meaningful:
        notes.append(
            "Equity check is near zero (deal is ~100% debt financed) — "
            "IRR and MOIC are not meaningful and are reported as 0."
        )

    # Entry multiple for reference: EV / target LTM EBITDA
    target_ebitda = deal.target.ebitda
    entry_multiple = (acquisition_price / target_ebitda) if target_ebitda > 0 else 0.0

    # Exit multiple range: entry ± 2x in 0.5x steps
    exit_multiples = [
        round(entry_multiple + delta, 1)
        for delta in [-2.0, -1.5, -1.0, -0.5, 0.0, 0.5, 1.0, 1.5, 2.0]
        if (entry_multiple + delta) > 1.0  # Multiples must be positive
    ]

    exit_years = [y for y in [3, 5, 7] if y <= len(deal_ebitda_by_year)]

    # Cumulative deal-attributable cash. deal_fcf_by_year already subtracts
    # all debt paydown, so this may go negative when paydowns exceed deal FCF —
    # that shortfall correctly increases net debt attributable to the deal.
    cumulative_cash_by_year: list[float] = []
    running_cash = 0.0
    for yr_fcf in deal_fcf_by_year:
        running_cash += yr_fcf
        cumulative_cash_by_year.append(running_cash)

    scenarios: list[ReturnScenario] = []

    for exit_year in exit_years:
        exit_ebitda = deal_ebitda_by_year[exit_year - 1]
        ending_debt = ending_debt_by_year[exit_year - 1] if exit_year <= len(ending_debt_by_year) else 0.0
        cash_at_exit = cumulative_cash_by_year[exit_year - 1] if exit_year <= len(cumulative_cash_by_year) else 0.0

        net_debt_at_exit = ending_debt - cash_at_exit

        for exit_mult in exit_multiples:
            exit_ev = exit_ebitda * exit_mult
            exit_equity = max(0.0, exit_ev - net_debt_at_exit)

            if equity_is_meaningful:
                # Cash flows: [Year 0: -equity_invested, Year exit: +exit_equity]
                cash_flows = [-equity_invested] + [0.0] * (exit_year - 1) + [exit_equity]
                irr = _irr(cash_flows)
                moic = exit_equity / equity_invested
            else:
                irr = 0.0
                moic = 0.0

            scenarios.append(ReturnScenario(
                exit_year=exit_year,
                exit_multiple=exit_mult,
                exit_enterprise_value=exit_ev,
                irr=max(-1.0, irr),  # Cap at -100%
                moic=moic,
            ))

    return ReturnsAnalysis(
        entry_multiple=entry_multiple,
        equity_invested=equity_invested,
        scenarios=scenarios,
        annual_fcf_to_equity=list(deal_fcf_by_year),
        notes=notes,
    )
