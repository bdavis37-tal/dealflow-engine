"""
Test suite for the Defense AI valuation vertical.

Tests defense-specific valuation logic including:
  - Defense positioning computation (clearance, certifications, backlog)
  - Defense-specific scorecard metrics (EV/Revenue, backlog coverage, premiums)
  - Defense-specific risk checks (concentration, recompete, clearance, IP, CR)
  - Verdict adjustment for defense backlog
"""
import json
import pytest
from pathlib import Path

from app.engine.models import DealInput, Industry, ClearanceLevel
from app.engine.financial_engine import run_deal, _compute_defense_positioning


FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(filename: str) -> dict:
    with open(FIXTURES_DIR / filename) as f:
        return json.load(f)


def deal_from_fixture(filename: str) -> tuple[DealInput, dict]:
    fixture = load_fixture(filename)
    deal = DealInput(**fixture["input"])
    return deal, fixture["expected"]


class TestDefenseAIAcquisition:
    """
    Fixture: $1.8B acquisition of AI-native defense startup by defense prime.
    Target has TS/SCI clearance, $500M backlog, 2 programs of record,
    FedRAMP High + IL5 + CMMC Level 3 certifications.
    """

    def setup_method(self):
        self.deal, self.expected = deal_from_fixture("defense_ai_acquisition.json")
        self.output = run_deal(self.deal, include_sensitivity=False)

    def test_output_is_produced(self):
        assert self.output is not None
        assert len(self.output.pro_forma_income_statement) == 5

    def test_defense_positioning_present(self):
        """Defense deals should produce a defense_positioning output."""
        assert self.output.defense_positioning is not None

    def test_defense_positioning_clearance(self):
        dp = self.output.defense_positioning
        assert dp.clearance_level == "Top Secret/SCI"

    def test_defense_positioning_backlog(self):
        dp = self.output.defense_positioning
        assert dp.combined_backlog == 500_000_000
        # backlog / revenue = 500M / 120M ≈ 4.17
        assert abs(dp.backlog_coverage_ratio - 4.17) < 0.1

    def test_defense_positioning_revenue_visibility(self):
        dp = self.output.defense_positioning
        # funded backlog / revenue = 200M / 120M ≈ 1.67
        assert abs(dp.revenue_visibility_years - 1.67) < 0.1

    def test_defense_positioning_ev_revenue(self):
        dp = self.output.defense_positioning
        # 1.8B / 120M = 15.0
        assert abs(dp.ev_revenue_multiple - 15.0) < 0.1

    def test_defense_positioning_is_ai_native(self):
        dp = self.output.defense_positioning
        assert dp.is_ai_native is True

    def test_clearance_premium_applied(self):
        dp = self.output.defense_positioning
        # TS/SCI should have 20% clearance premium
        assert dp.clearance_premium_applied == 0.20

    def test_certification_premium_applied(self):
        dp = self.output.defense_positioning
        # FedRAMP High (8%) + IL5 (10%) + CMMC Level 3 (5%) = 23%
        assert abs(dp.certification_premium_applied - 0.23) < 0.01

    def test_program_of_record_premium_applied(self):
        dp = self.output.defense_positioning
        # 2 programs of record → 15% POR premium
        assert dp.program_of_record_premium_applied == 0.15

    def test_total_defense_premium(self):
        dp = self.output.defense_positioning
        # 20% + 23% + 15% = 58%
        expected_total = 0.20 + 0.23 + 0.15
        assert abs(dp.total_defense_premium_pct - expected_total) < 0.01

    def test_defense_positioning_summary(self):
        dp = self.output.defense_positioning
        assert "Top Secret/SCI" in dp.positioning_summary
        assert "contract vehicle" in dp.positioning_summary
        assert "program" in dp.positioning_summary.lower()

    def test_contract_vehicles_count(self):
        dp = self.output.defense_positioning
        assert dp.active_contract_vehicles == 4

    def test_programs_of_record_count(self):
        dp = self.output.defense_positioning
        assert dp.programs_of_record == 2


class TestDefenseScorecardMetrics:
    """Test that defense deals include defense-specific scorecard metrics."""

    def setup_method(self):
        self.deal, _ = deal_from_fixture("defense_ai_acquisition.json")
        self.output = run_deal(self.deal, include_sensitivity=False)

    def test_ev_revenue_metric_present(self):
        names = [m.name for m in self.output.deal_scorecard]
        assert "Implied EV/Revenue" in names

    def test_backlog_coverage_metric_present(self):
        names = [m.name for m in self.output.deal_scorecard]
        assert "Backlog Coverage Ratio" in names

    def test_defense_premium_metric_present(self):
        names = [m.name for m in self.output.deal_scorecard]
        assert "Defense Premium Applied" in names

    def test_programs_of_record_metric_present(self):
        names = [m.name for m in self.output.deal_scorecard]
        assert "Programs of Record" in names

    def test_standard_metrics_still_present(self):
        """Defense deals should still have standard M&A metrics."""
        names = [m.name for m in self.output.deal_scorecard]
        assert any("EBITDA" in n or "Multiple" in n for n in names)
        assert any("Accretion" in n or "Dilution" in n for n in names)


class TestDefenseRiskChecks:
    """Test defense-specific risk detection."""

    def setup_method(self):
        self.deal, _ = deal_from_fixture("defense_ai_acquisition.json")
        self.output = run_deal(self.deal, include_sensitivity=False)

    def test_risk_assessment_includes_defense_risks(self):
        """At 85% DoD concentration, should flag customer concentration."""
        risk_names = [r.metric_name for r in self.output.risk_assessment]
        assert "DoD Revenue Concentration" in risk_names

    def test_no_recompete_risk_with_4_vehicles(self):
        """4 contract vehicles is above the threshold, shouldn't flag."""
        risk_names = [r.metric_name for r in self.output.risk_assessment]
        assert "Contract Vehicle Count" not in risk_names

    def test_no_ip_risk_for_company_owned(self):
        """Company-owned IP shouldn't trigger IP risk."""
        risk_names = [r.metric_name for r in self.output.risk_assessment]
        assert "IP Ownership Risk" not in risk_names

    def test_clearance_without_por_flagged(self):
        """Modify fixture to have high clearance but no POR — should flag."""
        fixture = load_fixture("defense_ai_acquisition.json")
        fixture["input"]["target"]["defense_profile"]["programs_of_record"] = 0
        deal = DealInput(**fixture["input"])
        output = run_deal(deal, include_sensitivity=False)
        risk_names = [r.metric_name for r in output.risk_assessment]
        assert "Clearance Utilization" in risk_names

    def test_ip_unlimited_rights_flagged(self):
        """Government unlimited rights should flag IP risk."""
        fixture = load_fixture("defense_ai_acquisition.json")
        fixture["input"]["target"]["defense_profile"]["ip_ownership"] = "unlimited_rights"
        deal = DealInput(**fixture["input"])
        output = run_deal(deal, include_sensitivity=False)
        risk_names = [r.metric_name for r in output.risk_assessment]
        assert "IP Ownership Risk" in risk_names

    def test_low_vehicle_count_flagged(self):
        """1 contract vehicle should flag recompete risk."""
        fixture = load_fixture("defense_ai_acquisition.json")
        fixture["input"]["target"]["defense_profile"]["contract_vehicles"] = ["Prime Contract"]
        deal = DealInput(**fixture["input"])
        output = run_deal(deal, include_sensitivity=False)
        risk_names = [r.metric_name for r in output.risk_assessment]
        assert "Contract Vehicle Count" in risk_names


class TestDefenseVerdictAdjustment:
    """Test that the verdict accounts for defense backlog context."""

    def test_verdict_mentions_defense_context(self):
        """Verdict subtext should reference defense positioning for defense deals."""
        deal, _ = deal_from_fixture("defense_ai_acquisition.json")
        output = run_deal(deal, include_sensitivity=False)
        # The deal is likely dilutive on pure EPS (high price, low EBITDA target)
        # but should mention backlog/premiums in subtext
        subtext = output.deal_verdict_subtext.lower()
        assert "backlog" in subtext or "defense" in subtext or "premium" in subtext


class TestNonDefenseDealUnchanged:
    """Ensure non-defense deals are not affected by defense additions."""

    def setup_method(self):
        self.deal, self.expected = deal_from_fixture("simple_cash_deal.json")
        self.output = run_deal(self.deal, include_sensitivity=False)

    def test_no_defense_positioning(self):
        assert self.output.defense_positioning is None

    def test_standard_scorecard_only(self):
        names = [m.name for m in self.output.deal_scorecard]
        assert "Implied EV/Revenue" not in names
        assert "Backlog Coverage Ratio" not in names
        assert "Defense Premium Applied" not in names

    def test_no_defense_risks(self):
        risk_names = [r.metric_name for r in self.output.risk_assessment]
        assert "DoD Revenue Concentration" not in risk_names
        assert "Contract Vehicle Count" not in risk_names
        assert "Clearance Utilization" not in risk_names
        assert "IP Ownership Risk" not in risk_names
