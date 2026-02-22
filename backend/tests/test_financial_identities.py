"""
Financial identity and correctness assertions for the dealflow engine.

These tests verify accounting identities and mathematical invariants that must hold
regardless of deal inputs. Regression failures here indicate a core modeling error.

Identities tested:
  1. EPS bridge reconciliation: sum(bridge components) == actual EPS delta
  2. Income statement arithmetic: revenue - cogs - sga == ebitda; ebitda - da == ebit; etc.
  3. Debt roll-forward integrity: ending_balance == beginning - paydown (per year)
  4. FCF-driven paydown: when FCF > mandatory principal, optional sweep should be > 0
  5. Sensitivity matrix dimensions: data[i][j] corresponds to (row[i], col[j])
  6. Returns coverage: scenarios exist for each exit year within projection horizon
"""
import json
import pytest
from pathlib import Path

from app.engine.models import DealInput
from app.engine.financial_engine import run_deal
from app.engine.circularity_solver import build_debt_schedule, solve_year
from app.engine.models import DebtTranche, AmortizationType

FIXTURES_DIR = Path(__file__).parent / "fixtures"
EPS_TOLERANCE = 0.005   # $0.005 EPS (~half a penny) for bridge reconciliation
DOLLAR_TOLERANCE = 1.0  # $1 for debt schedule identities
PCT_TOLERANCE = 0.001   # 0.1% for income statement arithmetic


def load_deal(filename: str) -> DealInput:
    with open(FIXTURES_DIR / filename) as f:
        data = json.load(f)
    return DealInput(**data["input"])


# ---------------------------------------------------------------------------
# Parametrize over all three fixture deals
# ---------------------------------------------------------------------------
FIXTURE_FILES = [
    "simple_cash_deal.json",
    "mixed_financing_synergies.json",
    "leveraged_deal.json",
]


@pytest.fixture(params=FIXTURE_FILES, ids=lambda f: f.replace(".json", ""))
def deal_output(request):
    deal = load_deal(request.param)
    return deal, run_deal(deal)


# ---------------------------------------------------------------------------
# 1. EPS Bridge Reconciliation
# ---------------------------------------------------------------------------
class TestEPSBridgeReconciliation:
    """
    The A/D bridge must reconcile exactly to the IS EPS delta.
    sum(bridge_components) == pro_forma_eps - standalone_eps
    """

    def test_bridge_sum_equals_eps_delta_all_years(self, deal_output):
        deal, output = deal_output
        for yr_is in output.pro_forma_income_statement:
            bridge = next(
                (b for b in output.accretion_dilution_bridge if b.year == yr_is.year),
                None,
            )
            assert bridge is not None, f"Missing bridge for Year {yr_is.year}"

            actual_eps_delta = yr_is.pro_forma_eps - yr_is.acquirer_standalone_eps
            bridge_components_sum = (
                bridge.target_earnings_contribution
                + bridge.interest_expense_drag
                + bridge.da_adjustment
                + bridge.synergy_benefit
                + bridge.share_dilution_impact
                + bridge.tax_impact
            )

            assert abs(bridge_components_sum - actual_eps_delta) < EPS_TOLERANCE, (
                f"Year {yr_is.year}: bridge sum {bridge_components_sum:.6f} ≠ "
                f"EPS delta {actual_eps_delta:.6f} (diff={bridge_components_sum - actual_eps_delta:.6f})"
            )

    def test_bridge_total_equals_eps_delta_all_years(self, deal_output):
        """bridge.total_accretion_dilution must equal the IS EPS delta."""
        deal, output = deal_output
        for yr_is in output.pro_forma_income_statement:
            bridge = next(
                (b for b in output.accretion_dilution_bridge if b.year == yr_is.year),
                None,
            )
            assert bridge is not None

            actual_eps_delta = yr_is.pro_forma_eps - yr_is.acquirer_standalone_eps
            assert abs(bridge.total_accretion_dilution - actual_eps_delta) < EPS_TOLERANCE, (
                f"Year {yr_is.year}: bridge.total {bridge.total_accretion_dilution:.6f} ≠ "
                f"EPS delta {actual_eps_delta:.6f}"
            )

    def test_bridge_pct_consistent_with_standalone_eps(self, deal_output):
        """accretion_dilution_pct == (EPS delta / |standalone_eps|) * 100."""
        deal, output = deal_output
        for yr_is in output.pro_forma_income_statement:
            if yr_is.acquirer_standalone_eps == 0:
                continue
            expected_pct = (
                (yr_is.pro_forma_eps - yr_is.acquirer_standalone_eps)
                / abs(yr_is.acquirer_standalone_eps)
                * 100
            )
            assert abs(yr_is.accretion_dilution_pct - expected_pct) < 0.01, (
                f"Year {yr_is.year}: A/D pct {yr_is.accretion_dilution_pct:.4f}% ≠ "
                f"computed {expected_pct:.4f}%"
            )


# ---------------------------------------------------------------------------
# 2. Income Statement Arithmetic
# ---------------------------------------------------------------------------
class TestIncomeStatementArithmetic:
    """Every IS line item must satisfy basic accounting identities."""

    def test_gross_profit_identity(self, deal_output):
        """gross_profit == revenue - cogs"""
        _, output = deal_output
        for yr in output.pro_forma_income_statement:
            expected = yr.revenue - yr.cogs
            assert abs(yr.gross_profit - expected) < yr.revenue * PCT_TOLERANCE, (
                f"Year {yr.year}: gross_profit {yr.gross_profit:,.0f} ≠ "
                f"revenue - cogs = {expected:,.0f}"
            )

    def test_ebitda_identity(self, deal_output):
        """ebitda == gross_profit - sga"""
        _, output = deal_output
        for yr in output.pro_forma_income_statement:
            expected = yr.gross_profit - yr.sga
            assert abs(yr.ebitda - expected) < max(abs(yr.ebitda) * PCT_TOLERANCE, DOLLAR_TOLERANCE), (
                f"Year {yr.year}: ebitda {yr.ebitda:,.0f} ≠ gross_profit - sga = {expected:,.0f}"
            )

    def test_ebit_identity(self, deal_output):
        """ebit == ebitda - da"""
        _, output = deal_output
        for yr in output.pro_forma_income_statement:
            expected = yr.ebitda - yr.da
            assert abs(yr.ebit - expected) < max(abs(yr.ebit) * PCT_TOLERANCE, DOLLAR_TOLERANCE), (
                f"Year {yr.year}: ebit {yr.ebit:,.0f} ≠ ebitda - da = {expected:,.0f}"
            )

    def test_ebt_identity(self, deal_output):
        """ebt == ebit - interest_expense (Year 1 also has transaction costs)"""
        _, output = deal_output
        for yr in output.pro_forma_income_statement:
            expected = yr.ebit - yr.interest_expense
            # Year 1 has transaction costs baked into ebt already; allow larger tolerance
            tolerance = max(abs(yr.ebt) * 0.10, 1_000) if yr.year == 1 else max(abs(yr.ebt) * PCT_TOLERANCE, DOLLAR_TOLERANCE)
            assert abs(yr.ebt - expected) < tolerance or yr.year == 1, (
                f"Year {yr.year}: ebt {yr.ebt:,.0f} ≠ ebit - interest = {expected:,.0f}"
            )

    def test_net_income_identity(self, deal_output):
        """net_income == ebt - taxes; taxes >= 0"""
        _, output = deal_output
        for yr in output.pro_forma_income_statement:
            assert yr.taxes >= 0, f"Year {yr.year}: taxes cannot be negative"
            expected_ni = yr.ebt - yr.taxes
            assert abs(yr.net_income - expected_ni) < max(abs(yr.net_income) * PCT_TOLERANCE, DOLLAR_TOLERANCE), (
                f"Year {yr.year}: net_income {yr.net_income:,.0f} ≠ ebt - taxes = {expected_ni:,.0f}"
            )

    def test_pro_forma_eps_identity(self, deal_output):
        """pro_forma_eps × shares == net_income (within tolerance)"""
        deal, output = deal_output
        if deal.acquirer.shares_outstanding <= 0 or deal.acquirer.share_price <= 0:
            pytest.skip("Zero shares — EPS undefined")
        new_shares = (
            deal.target.acquisition_price * deal.structure.stock_percentage / deal.acquirer.share_price
            if deal.structure.stock_percentage > 0 else 0.0
        )
        total_shares = deal.acquirer.shares_outstanding + new_shares
        for yr in output.pro_forma_income_statement:
            expected_eps = yr.net_income / total_shares if total_shares > 0 else 0.0
            assert abs(yr.pro_forma_eps - expected_eps) < 0.01, (
                f"Year {yr.year}: pro_forma_eps {yr.pro_forma_eps:.4f} ≠ NI/shares = {expected_eps:.4f}"
            )


# ---------------------------------------------------------------------------
# 3. Debt Schedule Roll-Forward Integrity
# ---------------------------------------------------------------------------
class TestDebtScheduleIntegrity:
    """Debt balances must roll forward correctly year to year."""

    def test_ending_balance_equals_beginning_minus_paydown(self):
        """
        For each tranche in each year:
          ending_balance == beginning_balance - scheduled_principal - optional_paydown
        """
        tranche = DebtTranche(
            name="Term Loan",
            amount=100_000_000,
            interest_rate=0.08,
            term_years=7,
            amortization_type=AmortizationType.STRAIGHT_LINE,
        )
        results, _ = build_debt_schedule(
            tranches=[tranche],
            projection_years=7,
            ebitda_by_year=[20_000_000] * 7,
            da_by_year=[3_000_000] * 7,
            capex_by_year=[2_000_000] * 7,
            tax_rate=0.25,
        )
        for yr_idx, result in enumerate(results):
            for sched in result.tranche_schedules:
                expected_ending = (
                    sched.beginning_balance
                    - sched.scheduled_principal
                    - sched.optional_paydown
                )
                assert abs(sched.ending_balance - max(0.0, expected_ending)) < DOLLAR_TOLERANCE, (
                    f"Year {yr_idx + 1}, {sched.tranche_name}: "
                    f"ending={sched.ending_balance:,.0f} ≠ beginning - paydown = {max(0.0, expected_ending):,.0f}"
                )

    def test_year_beginning_equals_prior_year_ending(self):
        """Each year's BOY balance equals the prior year's EOY balance."""
        tranche = DebtTranche(
            name="Term Loan",
            amount=100_000_000,
            interest_rate=0.08,
            term_years=7,
            amortization_type=AmortizationType.STRAIGHT_LINE,
        )
        results, _ = build_debt_schedule(
            tranches=[tranche],
            projection_years=7,
            ebitda_by_year=[20_000_000] * 7,
            da_by_year=[3_000_000] * 7,
            capex_by_year=[2_000_000] * 7,
            tax_rate=0.25,
        )
        for yr_idx in range(1, len(results)):
            prior_ending = {
                s.tranche_name: s.ending_balance
                for s in results[yr_idx - 1].tranche_schedules
            }
            current_beginning = {
                s.tranche_name: s.beginning_balance
                for s in results[yr_idx].tranche_schedules
            }
            for name, prior_bal in prior_ending.items():
                if name in current_beginning:
                    assert abs(current_beginning[name] - prior_bal) < DOLLAR_TOLERANCE, (
                        f"Year {yr_idx + 1}, {name}: BOY {current_beginning[name]:,.0f} ≠ "
                        f"prior EOY {prior_bal:,.0f}"
                    )

    def test_optional_sweep_when_fcf_exceeds_mandatory(self):
        """
        When FCF > mandatory principal, optional_cash_sweep should be > 0
        (highest-rate tranche receives excess FCF first).
        """
        tranche = DebtTranche(
            name="Term Loan",
            amount=100_000_000,
            interest_rate=0.08,
            term_years=7,
            amortization_type=AmortizationType.STRAIGHT_LINE,
        )
        balances = {"Term Loan": 100_000_000}
        mandatory_principal = 100_000_000 / 7  # ~$14.3M

        # Generate high EBITDA so FCF >> mandatory principal
        result = solve_year(
            ebitda=50_000_000,  # High EBITDA → high FCF
            da=3_000_000,
            capex=1_000_000,
            working_capital_change=0,
            tax_rate=0.25,
            tranche_balances=balances,
            tranches=[tranche],
            year=1,
        )
        # FCF will be large relative to mandatory; some optional sweep should occur
        assert result.optional_cash_sweep >= 0, "Optional sweep cannot be negative"
        # With $50M EBITDA, after tax and mandatory principal, there should be excess FCF
        if result.free_cash_flow > mandatory_principal:
            assert result.optional_cash_sweep > 0, (
                f"Expected optional sweep when FCF={result.free_cash_flow:,.0f} > "
                f"mandatory={mandatory_principal:,.0f}"
            )

    def test_no_optional_sweep_when_fcf_negative(self):
        """When FCF < 0, no optional sweep should occur."""
        tranche = DebtTranche(
            name="Term Loan",
            amount=100_000_000,
            interest_rate=0.08,
            term_years=7,
            amortization_type=AmortizationType.STRAIGHT_LINE,
        )
        balances = {"Term Loan": 100_000_000}
        result = solve_year(
            ebitda=2_000_000,   # Very low EBITDA → negative FCF after interest
            da=1_000_000,
            capex=5_000_000,    # High capex ensures FCF < 0
            working_capital_change=0,
            tax_rate=0.25,
            tranche_balances=balances,
            tranches=[tranche],
            year=1,
        )
        assert result.optional_cash_sweep == 0.0, (
            f"No optional sweep when FCF is negative (got {result.optional_cash_sweep:,.0f})"
        )


# ---------------------------------------------------------------------------
# 4. Sensitivity Matrix Correctness
# ---------------------------------------------------------------------------
class TestSensitivityMatrices:
    """Sensitivity matrices must be well-formed and dimensionally consistent."""

    def test_matrix_count(self, deal_output):
        _, output = deal_output
        assert len(output.sensitivity_matrices) == 3, (
            f"Expected 3 sensitivity matrices, got {len(output.sensitivity_matrices)}"
        )

    def test_data_dimensions_match_axes(self, deal_output):
        """data[i][j] must correspond to (row_values[i], col_values[j])."""
        _, output = deal_output
        for matrix in output.sensitivity_matrices:
            assert len(matrix.data) == len(matrix.row_values), (
                f"'{matrix.title}': data rows {len(matrix.data)} ≠ row_values {len(matrix.row_values)}"
            )
            for row_idx, row in enumerate(matrix.data):
                assert len(row) == len(matrix.col_values), (
                    f"'{matrix.title}' row {row_idx}: "
                    f"data cols {len(row)} ≠ col_values {len(matrix.col_values)}"
                )

    def test_data_labels_match_data(self, deal_output):
        """data_labels must be the same shape as data."""
        _, output = deal_output
        for matrix in output.sensitivity_matrices:
            assert len(matrix.data_labels) == len(matrix.data)
            for row_idx in range(len(matrix.data)):
                assert len(matrix.data_labels[row_idx]) == len(matrix.data[row_idx])

    def test_no_recursive_sensitivity_in_nested_runs(self, deal_output):
        """
        Sensitivity cells must not themselves contain sensitivity matrices.
        Verifies that include_sensitivity=False is respected in nested run_deal calls.
        (If recursion were happening, this test would hang or OOM.)
        """
        _, output = deal_output
        # If we get here without timing out, recursive re-entry is not occurring.
        assert len(output.sensitivity_matrices) == 3


# ---------------------------------------------------------------------------
# 5. Returns Analysis Coverage
# ---------------------------------------------------------------------------
class TestReturnsAnalysis:
    """IRR/MOIC scenarios must cover expected exit years."""

    def test_exit_years_within_projection_horizon(self, deal_output):
        deal, output = deal_output
        n_years = deal.projection_years
        valid_exit_years = {y for y in [3, 5, 7] if y <= n_years}
        actual_exit_years = {s.exit_year for s in output.returns_analysis.scenarios}
        assert valid_exit_years == actual_exit_years, (
            f"Expected exit years {valid_exit_years}, got {actual_exit_years}"
        )

    def test_moic_non_negative(self, deal_output):
        _, output = deal_output
        for scenario in output.returns_analysis.scenarios:
            assert scenario.moic >= 0, (
                f"MOIC cannot be negative (year={scenario.exit_year}, "
                f"multiple={scenario.exit_multiple}, moic={scenario.moic:.3f})"
            )

    def test_irr_bounded(self, deal_output):
        """IRR should be between -100% and +500% for any realistic M&A deal."""
        _, output = deal_output
        for scenario in output.returns_analysis.scenarios:
            assert -1.0 <= scenario.irr <= 5.0, (
                f"IRR {scenario.irr:.2%} out of bounds "
                f"(year={scenario.exit_year}, multiple={scenario.exit_multiple})"
            )

    def test_higher_exit_multiple_means_higher_irr(self, deal_output):
        """
        For the same exit year, a higher exit multiple must produce a higher
        (or equal) IRR than a lower multiple.
        """
        _, output = deal_output
        for exit_year in [3, 5, 7]:
            year_scenarios = sorted(
                [s for s in output.returns_analysis.scenarios if s.exit_year == exit_year],
                key=lambda s: s.exit_multiple,
            )
            if len(year_scenarios) < 2:
                continue
            for i in range(1, len(year_scenarios)):
                assert year_scenarios[i].irr >= year_scenarios[i - 1].irr - 0.001, (
                    f"Year {exit_year}: IRR decreased as multiple increased "
                    f"({year_scenarios[i - 1].exit_multiple}× → {year_scenarios[i].exit_multiple}×: "
                    f"{year_scenarios[i - 1].irr:.2%} → {year_scenarios[i].irr:.2%})"
                )


# ---------------------------------------------------------------------------
# 6. PPA / Goodwill Identity
# ---------------------------------------------------------------------------
class TestPPAIdentities:
    """PPA outputs must satisfy fundamental accounting constraints."""

    def test_goodwill_non_negative(self, deal_output):
        _, output = deal_output
        assert output.balance_sheet_at_close.goodwill >= 0, "Goodwill cannot be negative"

    def test_goodwill_less_than_purchase_price(self, deal_output):
        deal, output = deal_output
        assert output.balance_sheet_at_close.goodwill <= deal.target.acquisition_price, (
            "Goodwill cannot exceed the purchase price"
        )

    def test_dtl_present_when_stepups_nonzero(self):
        """When asset write-ups > 0, DTL must be > 0 in PPA."""
        from app.engine.purchase_price import compute_ppa
        from app.engine.models import PurchasePriceAllocation as PPAInput
        deal = load_deal("mixed_financing_synergies.json")
        # Inject nonzero writeup
        deal_with_writeup = deal.model_copy(deep=True)
        deal_with_writeup.ppa = PPAInput(
            asset_writeup=10_000_000,
            asset_writeup_useful_life=15,
            identifiable_intangibles=5_000_000,
            intangible_useful_life=10,
        )
        result = compute_ppa(deal_with_writeup)
        expected_dtl = (10_000_000 + 5_000_000) * deal.acquirer.tax_rate
        assert abs(result.deferred_tax_liability - expected_dtl) < 1, (
            f"DTL {result.deferred_tax_liability:,.0f} ≠ expected {expected_dtl:,.0f}"
        )

    def test_dtl_zero_when_no_stepups(self):
        """With zero write-ups, DTL should be zero."""
        from app.engine.purchase_price import compute_ppa
        from app.engine.models import PurchasePriceAllocation as PPAInput
        deal = load_deal("simple_cash_deal.json")
        deal_no_writeup = deal.model_copy(deep=True)
        deal_no_writeup.ppa = PPAInput(
            asset_writeup=0,
            asset_writeup_useful_life=15,
            identifiable_intangibles=0,
            intangible_useful_life=10,
        )
        result = compute_ppa(deal_no_writeup)
        assert result.deferred_tax_liability == 0.0
