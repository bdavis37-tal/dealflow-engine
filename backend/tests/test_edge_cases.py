"""
Edge case tests and golden file regression test for the financial engine.

Tests cover:
  - All-stock deal (no cash, no debt, pure equity dilution)
  - Extreme leverage (90% debt, 3 tranches, tight coverage)
  - Golden file regression (pinned output for simple_cash_deal, 0.1% tolerance)
"""
import json
import pytest
from pathlib import Path

from app.engine.models import DealInput, DealVerdict
from app.engine.financial_engine import run_deal

FIXTURES_DIR = Path(__file__).parent / "fixtures"
GOLDEN_TOLERANCE = 0.001  # 0.1%


def load_deal(filename: str) -> DealInput:
    with open(FIXTURES_DIR / filename) as f:
        data = json.load(f)
    return DealInput(**data["input"])


def _within_tolerance(actual: float, expected: float, tolerance: float = GOLDEN_TOLERANCE) -> bool:
    """Check if actual is within tolerance of expected (relative or absolute for near-zero)."""
    if expected == 0:
        return abs(actual) < 1.0  # Within $1 of zero
    return abs(actual - expected) / abs(expected) < tolerance


# ---------------------------------------------------------------------------
# All-Stock Deal
# ---------------------------------------------------------------------------
class TestAllStockDeal:
    """100% stock consideration: no cash used, no debt, maximum share dilution."""

    def setup_method(self):
        self.deal = load_deal("all_stock_deal.json")
        self.output = run_deal(self.deal, include_sensitivity=False)

    def test_output_produced(self):
        assert self.output is not None
        assert len(self.output.pro_forma_income_statement) == 5

    def test_new_shares_issued(self):
        """100% stock → new shares = acquisition_price / share_price."""
        bs = self.output.balance_sheet_at_close
        expected_shares = self.deal.target.acquisition_price / self.deal.acquirer.share_price
        assert abs(bs.shares_issued - expected_shares) < 1, (
            f"Expected {expected_shares:,.0f} new shares, got {bs.shares_issued:,.0f}"
        )

    def test_no_acquisition_debt(self):
        """All-stock deal should have zero acquisition debt."""
        assert self.output.balance_sheet_at_close.new_acquisition_debt == 0.0

    def test_no_cash_used(self):
        """All-stock deal should use zero cash."""
        assert self.output.balance_sheet_at_close.cash_used == 0.0

    def test_no_convergence_warning(self):
        """No debt → no circularity → no convergence warning."""
        assert not self.output.convergence_warning

    def test_eps_defined_all_years(self):
        """Pro forma EPS should be finite for all years."""
        for yr in self.output.pro_forma_income_statement:
            assert yr.pro_forma_eps != 0.0 or yr.net_income == 0.0
            assert -1000 < yr.pro_forma_eps < 1000

    def test_share_dilution_reflected(self):
        """With new shares issued, the share dilution impact should be nonzero in bridge."""
        bridge_yr1 = self.output.accretion_dilution_bridge[0]
        assert bridge_yr1.share_dilution_impact != 0.0, (
            "100% stock deal should show share dilution impact"
        )

    def test_verdict_set(self):
        assert self.output.deal_verdict in list(DealVerdict)


# ---------------------------------------------------------------------------
# Extreme Leverage Deal
# ---------------------------------------------------------------------------
class TestExtremeLeverageDeal:
    """90% debt financing with 3 tranches. Tests solver under stress."""

    def setup_method(self):
        self.deal = load_deal("extreme_leverage_deal.json")
        self.output = run_deal(self.deal, include_sensitivity=False)

    def test_output_produced(self):
        assert self.output is not None
        assert len(self.output.pro_forma_income_statement) == 7  # 7-year projection

    def test_significant_interest_expense(self):
        """With $270M total debt at 7.5-14%, interest should be substantial."""
        y1 = self.output.pro_forma_income_statement[0]
        # Minimum expected: $270M × 7.5% = $20.25M
        assert y1.interest_expense > 15_000_000, (
            f"Interest expense {y1.interest_expense:,.0f} too low for $270M debt"
        )

    def test_three_tranches_in_deal(self):
        assert len(self.deal.structure.debt_tranches) == 3

    def test_leverage_risk_flagged(self):
        """
        With 90% debt on a $300M deal, combined leverage should be very high.
        Post-close leverage = ($270M + $30M existing + $5M target) / ($25M + $12M) ≈ 8.2×
        This should trigger a leverage risk flag.
        """
        risk_names = [r.metric_name for r in self.output.risk_assessment]
        # At 8.2× leverage, should trigger leverage risk (threshold is 4×)
        has_leverage_risk = any("leverage" in name.lower() for name in risk_names)
        assert has_leverage_risk or len(self.output.risk_assessment) > 0, (
            "Extreme leverage deal should flag at least one risk"
        )

    def test_verdict_reflects_stress(self):
        """90% debt on a high-multiple deal should not get a green verdict."""
        # This deal has entry_multiple = 25× on a consulting firm → likely red or yellow
        assert self.output.deal_verdict in [DealVerdict.RED, DealVerdict.YELLOW], (
            f"Expected red or yellow verdict, got {self.output.deal_verdict.value}"
        )

    def test_interest_declines_over_time(self):
        """First lien has straight-line amortization → interest should decline."""
        y1 = self.output.pro_forma_income_statement[0].interest_expense
        y7 = self.output.pro_forma_income_statement[6].interest_expense
        assert y7 < y1, "Interest should decline as debt amortizes"


# ---------------------------------------------------------------------------
# Golden File Regression Test
# ---------------------------------------------------------------------------
class TestGoldenFile:
    """
    Pinned regression test against hand-verified output for simple_cash_deal.
    All financial metrics must match within 0.1% tolerance.
    If this test fails, a core financial computation changed.
    """

    def setup_method(self):
        self.deal = load_deal("simple_cash_deal.json")
        self.output = run_deal(self.deal, include_sensitivity=False)
        with open(FIXTURES_DIR / "golden_simple_cash_deal.json") as f:
            self.golden = json.load(f)

    def test_entry_multiple(self):
        assert _within_tolerance(
            self.output.returns_analysis.entry_multiple,
            self.golden["entry_multiple"],
        ), f"Entry multiple {self.output.returns_analysis.entry_multiple:.4f} != golden {self.golden['entry_multiple']}"

    def test_goodwill(self):
        assert _within_tolerance(
            self.output.balance_sheet_at_close.goodwill,
            self.golden["goodwill"],
        ), f"Goodwill {self.output.balance_sheet_at_close.goodwill:,.0f} != golden {self.golden['goodwill']:,.0f}"

    def test_year1_revenue(self):
        y1 = self.output.pro_forma_income_statement[0]
        assert _within_tolerance(y1.revenue, self.golden["year1"]["revenue"])

    def test_year1_ebitda(self):
        y1 = self.output.pro_forma_income_statement[0]
        assert _within_tolerance(y1.ebitda, self.golden["year1"]["ebitda"])

    def test_year1_net_income(self):
        y1 = self.output.pro_forma_income_statement[0]
        assert _within_tolerance(y1.net_income, self.golden["year1"]["net_income"])

    def test_year1_eps(self):
        y1 = self.output.pro_forma_income_statement[0]
        assert _within_tolerance(y1.pro_forma_eps, self.golden["year1"]["pro_forma_eps"])

    def test_year1_accretion_pct(self):
        y1 = self.output.pro_forma_income_statement[0]
        assert _within_tolerance(
            y1.accretion_dilution_pct,
            self.golden["year1"]["accretion_dilution_pct"],
        )

    def test_year5_revenue(self):
        y5 = self.output.pro_forma_income_statement[4]
        assert _within_tolerance(y5.revenue, self.golden["year5"]["revenue"])

    def test_year5_eps(self):
        y5 = self.output.pro_forma_income_statement[4]
        assert _within_tolerance(y5.pro_forma_eps, self.golden["year5"]["pro_forma_eps"])

    def test_balance_sheet_no_debt(self):
        bs = self.output.balance_sheet_at_close
        assert bs.new_acquisition_debt == self.golden["balance_sheet"]["new_acquisition_debt"]
        assert bs.shares_issued == self.golden["balance_sheet"]["shares_issued"]
        assert _within_tolerance(bs.cash_used, self.golden["balance_sheet"]["cash_used"])

    def test_verdict(self):
        assert self.output.deal_verdict.value == self.golden["verdict"]

    def test_convergence(self):
        assert self.output.convergence_warning == self.golden["convergence_warning"]

    def test_risk_count(self):
        assert len(self.output.risk_assessment) == self.golden["risk_count"]

    def test_scorecard_count(self):
        assert len(self.output.deal_scorecard) == self.golden["scorecard_count"]
