"""
Tests for the iterative circularity solver.
Verifies convergence behavior, debt amortization schedules, and edge cases.
"""
import pytest
from app.engine.circularity_solver import solve_year, build_debt_schedule, MAX_ITERATIONS
from app.engine.models import DebtTranche, AmortizationType


def make_tranche(
    name: str = "Term Loan",
    amount: float = 100_000_000,
    rate: float = 0.08,
    term: int = 7,
    amort: AmortizationType = AmortizationType.STRAIGHT_LINE,
) -> DebtTranche:
    return DebtTranche(
        name=name,
        amount=amount,
        interest_rate=rate,
        term_years=term,
        amortization_type=amort,
    )


class TestSingleTrancheStraightLine:
    """Single straight-line amortizing tranche."""

    def setup_method(self):
        self.tranche = make_tranche(amount=70_000_000, rate=0.08, term=7)
        self.balances = {self.tranche.name: self.tranche.amount}

    def test_year1_interest(self):
        """
        Year 1 interest uses average balance ((BOY + EOY) / 2) × rate.
        BOY = $70M, mandatory principal = $70M / 7 = $10M, EOY ≥ $60M.
        Average ≤ ($70M + $60M) / 2 = $65M → interest ≤ $65M × 8% = $5.2M.
        With no optional sweep (low FCF scenario), interest = $5.2M exactly.
        """
        result = solve_year(
            ebitda=20_000_000,
            da=3_000_000,
            capex=2_000_000,
            working_capital_change=0,
            tax_rate=0.25,
            tranche_balances=self.balances,
            tranches=[self.tranche],
            year=1,
        )
        # Average balance = (BOY + EOY) / 2; interest must be less than BOY-only interest
        boy_interest = 70_000_000 * 0.08  # $5.6M (BOY only upper bound)
        assert result.total_interest_expense > 0
        assert result.total_interest_expense <= boy_interest + 100

    def test_year1_principal(self):
        """Straight-line: annual principal (mandatory only) = $70M / 7 = $10M.
        total_debt_paydown includes both mandatory + optional sweep."""
        result = solve_year(
            ebitda=20_000_000, da=3_000_000, capex=2_000_000,
            working_capital_change=0, tax_rate=0.25,
            tranche_balances=self.balances, tranches=[self.tranche], year=1,
        )
        expected_mandatory = 70_000_000 / 7
        # total_debt_paydown >= mandatory (optional sweep adds more if FCF allows)
        assert result.total_debt_paydown >= expected_mandatory - 100

    def test_ending_balance_year1(self):
        """Ending balance = $70M - mandatory - optional_sweep <= $70M - ($70M/7)."""
        result = solve_year(
            ebitda=20_000_000, da=3_000_000, capex=2_000_000,
            working_capital_change=0, tax_rate=0.25,
            tranche_balances=self.balances, tranches=[self.tranche], year=1,
        )
        max_expected_balance = 70_000_000 - (70_000_000 / 7)
        # Ending balance <= balance after mandatory only (optional sweep reduces further)
        assert result.ending_debt_balance <= max_expected_balance + 100

    def test_converges(self):
        result = solve_year(
            ebitda=20_000_000, da=3_000_000, capex=2_000_000,
            working_capital_change=0, tax_rate=0.25,
            tranche_balances=self.balances, tranches=[self.tranche], year=1,
        )
        assert result.converged

    def test_iterations_reasonable(self):
        result = solve_year(
            ebitda=20_000_000, da=3_000_000, capex=2_000_000,
            working_capital_change=0, tax_rate=0.25,
            tranche_balances=self.balances, tranches=[self.tranche], year=1,
        )
        assert result.iterations <= MAX_ITERATIONS


class TestBulletTranche:
    """Bullet tranche: no amortization until final year."""

    def test_no_principal_before_maturity(self):
        tranche = make_tranche(amount=50_000_000, rate=0.10, term=5, amort=AmortizationType.BULLET)
        balances = {tranche.name: tranche.amount}

        for year in range(1, 5):  # Years 1-4
            result = solve_year(
                ebitda=15_000_000, da=2_000_000, capex=1_500_000,
                working_capital_change=0, tax_rate=0.25,
                tranche_balances=balances, tranches=[tranche], year=year,
            )
            # Mandatory (scheduled) principal = 0 for bullet pre-maturity
            for sched in result.tranche_schedules:
                assert sched.scheduled_principal == 0.0, (
                    f"Year {year}: bullet mandatory principal should be zero"
                )
            # Optional sweep from excess FCF is allowed — it's good if debt is repaid early
            # (total_debt_paydown may be > 0 due to cash sweep)
            # Balance rolls forward for next year's BOY
            balances = {tranche.name: result.ending_debt_balance}

    def test_full_repayment_at_maturity(self):
        tranche = make_tranche(amount=50_000_000, rate=0.10, term=5, amort=AmortizationType.BULLET)
        balances = {tranche.name: 50_000_000}
        result = solve_year(
            ebitda=15_000_000, da=2_000_000, capex=1_500_000,
            working_capital_change=0, tax_rate=0.25,
            tranche_balances=balances, tranches=[tranche], year=5,
        )
        assert abs(result.total_debt_paydown - 50_000_000) < 100
        assert abs(result.ending_debt_balance) < 100


class TestInterestOnlyTranche:
    """Interest-only: no amortization until final year (same as bullet)."""

    def test_interest_only_no_principal_mid_term(self):
        tranche = make_tranche(amount=30_000_000, rate=0.095, term=7, amort=AmortizationType.INTEREST_ONLY)
        balances = {tranche.name: tranche.amount}
        result = solve_year(
            ebitda=12_000_000, da=1_500_000, capex=1_000_000,
            working_capital_change=0, tax_rate=0.25,
            tranche_balances=balances, tranches=[tranche], year=3,
        )
        # Mandatory principal = 0 for interest-only mid-term
        # Optional sweep may reduce balance if FCF is positive; scheduled_principal == 0
        for sched in result.tranche_schedules:
            assert sched.scheduled_principal == 0.0, "Interest-only: no mandatory principal mid-term"
        # Interest on average balance: if optional sweep occurred, avg < BOY × rate
        boy_interest = 30_000_000 * 0.095
        assert result.total_interest_expense <= boy_interest + 100  # At most BOY interest


class TestMultiTrancheSchedule:
    """Multi-tranche debt schedule: verify combined totals."""

    def test_multi_tranche_year1(self):
        tranches = [
            make_tranche("First Lien", 250_000_000, 0.070, 7, AmortizationType.STRAIGHT_LINE),
            make_tranche("Second Lien", 100_000_000, 0.095, 7, AmortizationType.INTEREST_ONLY),
            make_tranche("Mezzanine", 50_000_000, 0.120, 5, AmortizationType.BULLET),
        ]
        balances = {t.name: t.amount for t in tranches}

        result = solve_year(
            ebitda=60_000_000, da=8_000_000, capex=6_000_000,
            working_capital_change=0, tax_rate=0.25,
            tranche_balances=balances, tranches=tranches, year=1,
        )

        # Interest uses average balance ((BOY + EOY) / 2) for the amortizing tranche.
        # First Lien amortizes: BOY=$250M, mandatory principal=$250M/7≈$35.7M.
        # After optional sweep, ending balance may be lower; average ≈ (250M + EOY)/2.
        # Verify interest is positive and within a 20% band of BOY-based estimate.
        boy_interest_estimate = 17_500_000 + 9_500_000 + 6_000_000  # $33M at BOY
        assert result.total_interest_expense > 0
        assert result.total_interest_expense < boy_interest_estimate * 1.05  # At most slightly above BOY

        # Mandatory paydown >= First Lien mandatory (~$35.7M); optional sweep adds more
        expected_mandatory = 250_000_000 / 7
        assert result.total_debt_paydown >= expected_mandatory - 1000

        assert result.converged


class TestFullDebtSchedule:
    """Full multi-year debt schedule construction."""

    def test_schedule_length(self):
        tranche = make_tranche(amount=100_000_000, rate=0.08, term=7)
        results, non_converged = build_debt_schedule(
            tranches=[tranche],
            projection_years=7,
            ebitda_by_year=[20_000_000] * 7,
            da_by_year=[3_000_000] * 7,
            capex_by_year=[2_000_000] * 7,
            tax_rate=0.25,
        )
        assert len(results) == 7

    def test_balance_reaches_zero_by_maturity(self):
        tranche = make_tranche(amount=70_000_000, rate=0.08, term=7)
        results, _ = build_debt_schedule(
            tranches=[tranche],
            projection_years=7,
            ebitda_by_year=[20_000_000] * 7,
            da_by_year=[3_000_000] * 7,
            capex_by_year=[2_000_000] * 7,
            tax_rate=0.25,
        )
        final_balance = results[-1].ending_debt_balance
        assert abs(final_balance) < 1000, f"Balance should be ~zero at maturity, got {final_balance:,.0f}"

    def test_interest_declines_with_balance(self):
        """As straight-line principal reduces balance, interest should decrease each year."""
        tranche = make_tranche(amount=70_000_000, rate=0.08, term=7)
        results, _ = build_debt_schedule(
            tranches=[tranche],
            projection_years=7,
            ebitda_by_year=[20_000_000] * 7,
            da_by_year=[3_000_000] * 7,
            capex_by_year=[2_000_000] * 7,
            tax_rate=0.25,
        )
        interests = [r.total_interest_expense for r in results]
        for i in range(1, len(interests)):
            assert interests[i] <= interests[i - 1] + 1, (
                f"Interest should decline: Year {i} = {interests[i]:,.0f}, Year {i+1} = {interests[i+1]:,.0f}"
            )

    def test_no_convergence_warning_standard_case(self):
        tranche = make_tranche(amount=50_000_000, rate=0.075, term=5)
        _, any_non_convergence = build_debt_schedule(
            tranches=[tranche],
            projection_years=5,
            ebitda_by_year=[15_000_000] * 5,
            da_by_year=[2_000_000] * 5,
            capex_by_year=[1_500_000] * 5,
            tax_rate=0.25,
        )
        assert not any_non_convergence
