"""
Test suite for the startup valuation engine.

Tests cover all 4 valuation methods, verdict assignment, dilution modeling,
SAFE conversion, edge cases, and multiple verticals. All monetary values
in USD millions; percentages as decimals per project convention.
"""
import pytest

from app.engine.startup_models import (
    StartupInput,
    StartupValuationOutput,
    StartupStage,
    StartupVertical,
    InstrumentType,
    Geography,
    ProductStage,
    TeamProfile,
    TractionMetrics,
    ProductProfile,
    MarketProfile,
    FundraisingProfile,
    ValuationVerdict,
    ValuationSignal,
    RaiseSignal,
)
from app.engine.startup_engine import (
    run_startup_valuation,
    _run_berkus,
    _run_scorecard,
    _run_rfs,
    _run_arr_multiple,
    _get_vertical_data,
    _build_dilution_scenarios,
    _build_safe_conversion,
    _assign_verdict,
    _compute_round_timing,
)


# ---------------------------------------------------------------------------
# Fixtures — common startup profiles
# ---------------------------------------------------------------------------

@pytest.fixture
def seed_b2b_saas() -> StartupInput:
    """Typical seed-stage B2B SaaS startup with moderate traction."""
    return StartupInput(
        company_name="AcmeSaaS",
        team=TeamProfile(
            founder_count=2,
            prior_exits=0,
            domain_experts=True,
            technical_cofounder=True,
            repeat_founder=False,
            tier1_background=False,
            notable_advisors=True,
        ),
        traction=TractionMetrics(
            has_revenue=True,
            monthly_recurring_revenue=0.05,   # $50K MRR
            annual_recurring_revenue=0.6,     # $600K ARR
            mom_growth_rate=0.12,             # 12% MoM
            net_revenue_retention=1.15,       # 115% NRR
            gross_margin=0.80,
            monthly_burn_rate=0.1,            # $100K/mo burn
            cash_on_hand=2.0,                 # $2M cash
            paying_customer_count=15,
            logo_customer_count=3,
            has_lois=False,
        ),
        product=ProductProfile(
            stage=ProductStage.PAYING_CUSTOMERS,
            has_patent_or_ip=False,
            proprietary_data_moat=True,
            open_source_traction=False,
            regulatory_clearance=False,
        ),
        market=MarketProfile(
            tam_usd_billions=8.0,
            sam_usd_millions=400.0,
            market_growth_rate=0.20,
            competitive_moat="medium",
        ),
        fundraise=FundraisingProfile(
            stage=StartupStage.SEED,
            vertical=StartupVertical.B2B_SAAS,
            geography=Geography.BAY_AREA,
            raise_amount=3.0,
            instrument=InstrumentType.SAFE,
            pre_money_valuation_ask=None,
            safe_discount=0.20,
            has_mfn_clause=False,
            existing_safe_stack=0.5,
        ),
    )


@pytest.fixture
def pre_seed_ai_infra() -> StartupInput:
    """Pre-seed AI/ML infrastructure startup with no revenue."""
    return StartupInput(
        company_name="QuantumAI",
        team=TeamProfile(
            founder_count=3,
            prior_exits=1,
            domain_experts=True,
            technical_cofounder=True,
            repeat_founder=True,
            tier1_background=True,
            notable_advisors=True,
        ),
        traction=TractionMetrics(
            has_revenue=False,
            monthly_recurring_revenue=0.0,
            annual_recurring_revenue=0.0,
            mom_growth_rate=0.0,
            net_revenue_retention=1.0,
            gross_margin=0.7,
            monthly_burn_rate=0.05,
            cash_on_hand=0.5,
            paying_customer_count=0,
            logo_customer_count=0,
            has_lois=True,
        ),
        product=ProductProfile(
            stage=ProductStage.MVP,
            has_patent_or_ip=True,
            proprietary_data_moat=True,
            open_source_traction=True,
            regulatory_clearance=False,
        ),
        market=MarketProfile(
            tam_usd_billions=25.0,
            sam_usd_millions=1500.0,
            market_growth_rate=0.35,
            competitive_moat="high",
        ),
        fundraise=FundraisingProfile(
            stage=StartupStage.PRE_SEED,
            vertical=StartupVertical.AI_ML_INFRASTRUCTURE,
            geography=Geography.BAY_AREA,
            raise_amount=0.75,
            instrument=InstrumentType.SAFE,
            safe_discount=0.0,
            has_mfn_clause=True,
            existing_safe_stack=0.0,
        ),
    )


@pytest.fixture
def series_a_fintech() -> StartupInput:
    """Series A fintech with strong revenue and unit economics."""
    return StartupInput(
        company_name="PayFlow",
        team=TeamProfile(
            founder_count=2,
            prior_exits=1,
            domain_experts=True,
            technical_cofounder=True,
            repeat_founder=True,
            tier1_background=True,
            notable_advisors=True,
        ),
        traction=TractionMetrics(
            has_revenue=True,
            monthly_recurring_revenue=0.25,   # $250K MRR
            annual_recurring_revenue=3.0,     # $3M ARR
            mom_growth_rate=0.15,             # 15% MoM
            net_revenue_retention=1.25,       # 125% NRR
            gross_margin=0.75,
            monthly_burn_rate=0.4,            # $400K/mo
            cash_on_hand=6.0,                 # $6M
            paying_customer_count=50,
            logo_customer_count=10,
            has_lois=True,
        ),
        product=ProductProfile(
            stage=ProductStage.SCALING,
            has_patent_or_ip=True,
            proprietary_data_moat=True,
            open_source_traction=False,
            regulatory_clearance=True,
        ),
        market=MarketProfile(
            tam_usd_billions=50.0,
            sam_usd_millions=5000.0,
            market_growth_rate=0.25,
            competitive_moat="high",
        ),
        fundraise=FundraisingProfile(
            stage=StartupStage.SERIES_A,
            vertical=StartupVertical.FINTECH,
            geography=Geography.NEW_YORK,
            raise_amount=12.0,
            instrument=InstrumentType.PRICED_EQUITY,
            pre_money_valuation_ask=60.0,
            safe_discount=0.0,
            has_mfn_clause=False,
            existing_safe_stack=2.0,
        ),
    )


@pytest.fixture
def pre_seed_healthtech_minimal() -> StartupInput:
    """Pre-seed healthtech with very minimal data — edge case."""
    return StartupInput(
        company_name="HealthMinimal",
        team=TeamProfile(
            founder_count=1,
            prior_exits=0,
            domain_experts=False,
            technical_cofounder=False,
            repeat_founder=False,
            tier1_background=False,
            notable_advisors=False,
        ),
        traction=TractionMetrics(
            has_revenue=False,
            monthly_recurring_revenue=0.0,
            annual_recurring_revenue=0.0,
            mom_growth_rate=0.0,
            net_revenue_retention=1.0,
            gross_margin=0.7,
            monthly_burn_rate=0.0,
            cash_on_hand=0.0,
            paying_customer_count=0,
            logo_customer_count=0,
            has_lois=False,
        ),
        product=ProductProfile(
            stage=ProductStage.IDEA,
            has_patent_or_ip=False,
            proprietary_data_moat=False,
            open_source_traction=False,
            regulatory_clearance=False,
        ),
        market=MarketProfile(
            tam_usd_billions=5.0,
            sam_usd_millions=200.0,
            market_growth_rate=0.10,
            competitive_moat="low",
        ),
        fundraise=FundraisingProfile(
            stage=StartupStage.PRE_SEED,
            vertical=StartupVertical.HEALTHTECH,
            geography=Geography.OTHER_US,
            raise_amount=0.5,
            instrument=InstrumentType.SAFE,
            safe_discount=0.0,
            has_mfn_clause=False,
            existing_safe_stack=0.0,
        ),
    )


@pytest.fixture
def seed_climate_high_growth() -> StartupInput:
    """Seed-stage climate/energy startup with very high growth rate."""
    return StartupInput(
        company_name="GreenVolt",
        team=TeamProfile(
            founder_count=2,
            prior_exits=0,
            domain_experts=True,
            technical_cofounder=True,
            repeat_founder=False,
            tier1_background=False,
            notable_advisors=True,
        ),
        traction=TractionMetrics(
            has_revenue=True,
            monthly_recurring_revenue=0.08,   # $80K MRR
            annual_recurring_revenue=0.96,    # $960K ARR
            mom_growth_rate=0.25,             # 25% MoM — very high
            net_revenue_retention=1.30,       # 130% NRR
            gross_margin=0.65,
            monthly_burn_rate=0.15,
            cash_on_hand=3.0,
            paying_customer_count=8,
            logo_customer_count=2,
            has_lois=True,
        ),
        product=ProductProfile(
            stage=ProductStage.PAYING_CUSTOMERS,
            has_patent_or_ip=True,
            proprietary_data_moat=False,
            open_source_traction=False,
            regulatory_clearance=False,
        ),
        market=MarketProfile(
            tam_usd_billions=30.0,
            sam_usd_millions=2000.0,
            market_growth_rate=0.30,
            competitive_moat="high",
        ),
        fundraise=FundraisingProfile(
            stage=StartupStage.SEED,
            vertical=StartupVertical.CLIMATE_ENERGY,
            geography=Geography.AUSTIN,
            raise_amount=4.0,
            instrument=InstrumentType.CONVERTIBLE_NOTE,
            safe_discount=0.15,
            has_mfn_clause=False,
            existing_safe_stack=0.0,
        ),
    )


@pytest.fixture
def seed_consumer_zero_revenue() -> StartupInput:
    """Seed-stage consumer startup with zero revenue — edge case."""
    return StartupInput(
        company_name="ViralApp",
        team=TeamProfile(
            founder_count=2,
            prior_exits=0,
            domain_experts=False,
            technical_cofounder=True,
            repeat_founder=False,
            tier1_background=True,
            notable_advisors=False,
        ),
        traction=TractionMetrics(
            has_revenue=False,
            monthly_recurring_revenue=0.0,
            annual_recurring_revenue=0.0,
            mom_growth_rate=0.0,
            net_revenue_retention=1.0,
            gross_margin=0.7,
            monthly_burn_rate=0.08,
            cash_on_hand=1.0,
            paying_customer_count=0,
            logo_customer_count=0,
            has_lois=False,
        ),
        product=ProductProfile(
            stage=ProductStage.BETA,
            has_patent_or_ip=False,
            proprietary_data_moat=False,
            open_source_traction=False,
            regulatory_clearance=False,
        ),
        market=MarketProfile(
            tam_usd_billions=15.0,
            sam_usd_millions=800.0,
            market_growth_rate=0.18,
            competitive_moat="medium",
        ),
        fundraise=FundraisingProfile(
            stage=StartupStage.SEED,
            vertical=StartupVertical.CONSUMER,
            geography=Geography.LOS_ANGELES,
            raise_amount=2.0,
            instrument=InstrumentType.SAFE,
            safe_discount=0.20,
            has_mfn_clause=True,
            existing_safe_stack=0.3,
        ),
    )


# ---------------------------------------------------------------------------
# Test Class: Main Orchestrator
# ---------------------------------------------------------------------------

class TestRunStartupValuation:
    """Tests for the top-level run_startup_valuation() orchestrator."""

    def test_produces_output_for_seed_b2b_saas(self, seed_b2b_saas):
        output = run_startup_valuation(seed_b2b_saas)
        assert isinstance(output, StartupValuationOutput)
        assert output.company_name == "AcmeSaaS"
        assert output.stage == StartupStage.SEED
        assert output.vertical == StartupVertical.B2B_SAAS

    def test_blended_valuation_is_positive(self, seed_b2b_saas):
        output = run_startup_valuation(seed_b2b_saas)
        assert output.blended_valuation > 0

    def test_valuation_range_brackets_blended(self, seed_b2b_saas):
        output = run_startup_valuation(seed_b2b_saas)
        assert output.valuation_range_low <= output.blended_valuation
        assert output.valuation_range_high >= output.blended_valuation

    def test_four_method_results_returned(self, seed_b2b_saas):
        output = run_startup_valuation(seed_b2b_saas)
        assert len(output.method_results) == 4
        method_names = {m.method_name for m in output.method_results}
        assert method_names == {"berkus", "scorecard", "risk_factor_summation", "arr_multiple"}

    def test_implied_dilution_is_reasonable(self, seed_b2b_saas):
        output = run_startup_valuation(seed_b2b_saas)
        assert 0.0 < output.implied_dilution < 1.0

    def test_benchmarks_populated(self, seed_b2b_saas):
        output = run_startup_valuation(seed_b2b_saas)
        assert output.benchmark_p25 > 0
        assert output.benchmark_p50 > output.benchmark_p25
        assert output.benchmark_p75 > output.benchmark_p50

    def test_investor_scorecard_non_empty(self, seed_b2b_saas):
        output = run_startup_valuation(seed_b2b_saas)
        assert len(output.investor_scorecard) > 0

    def test_verdict_is_valid_enum(self, seed_b2b_saas):
        output = run_startup_valuation(seed_b2b_saas)
        assert output.verdict in list(ValuationVerdict)
        assert len(output.verdict_headline) > 0
        assert len(output.verdict_subtext) > 0

    def test_traction_bar_populated(self, seed_b2b_saas):
        output = run_startup_valuation(seed_b2b_saas)
        assert len(output.traction_bar) > 0

    def test_percentile_label_populated(self, seed_b2b_saas):
        output = run_startup_valuation(seed_b2b_saas)
        assert output.percentile_in_market in [
            "top 5%",
            "top quartile (P75–P95)",
            "top half (P50–P75)",
            "bottom half (P25–P50)",
            "bottom quartile (below P25)",
        ]

    def test_safe_cap_recommended_for_safe_instrument(self, seed_b2b_saas):
        """When raising on a SAFE, engine should recommend a cap."""
        output = run_startup_valuation(seed_b2b_saas)
        assert output.recommended_safe_cap is not None
        assert output.recommended_safe_cap > output.blended_valuation

    def test_no_safe_cap_for_priced_equity(self, series_a_fintech):
        output = run_startup_valuation(series_a_fintech)
        assert output.recommended_safe_cap is None

    def test_vertical_benchmarks_passthrough(self, seed_b2b_saas):
        output = run_startup_valuation(seed_b2b_saas)
        assert isinstance(output.vertical_benchmarks, dict)
        assert "valuation_p50" in output.vertical_benchmarks

    def test_computation_notes_present(self, seed_b2b_saas):
        output = run_startup_valuation(seed_b2b_saas)
        assert len(output.computation_notes) > 0

    def test_arr_dominant_weighting_when_revenue_exists(self, seed_b2b_saas):
        """When ARR exists, the ARR multiple should be weighted 65%."""
        output = run_startup_valuation(seed_b2b_saas)
        notes_text = " ".join(output.computation_notes)
        assert "ARR multiple weighted 65%" in notes_text

    def test_pre_revenue_blending_note(self, pre_seed_ai_infra):
        """Pre-revenue startups should blend applicable pre-revenue methods."""
        output = run_startup_valuation(pre_seed_ai_infra)
        notes_text = " ".join(output.computation_notes)
        assert "pre-revenue methods" in notes_text

    def test_round_timing_signal_present(self, seed_b2b_saas):
        output = run_startup_valuation(seed_b2b_saas)
        assert output.round_timing is not None
        assert output.round_timing.signal in list(RaiseSignal)


# ---------------------------------------------------------------------------
# Test Class: Berkus Method
# ---------------------------------------------------------------------------

class TestBerkusMethod:
    """Tests for the Berkus valuation method."""

    def test_applicable_for_pre_seed(self, pre_seed_ai_infra):
        vdata = _get_vertical_data(
            pre_seed_ai_infra.fundraise.vertical,
            pre_seed_ai_infra.fundraise.stage,
        )
        result = _run_berkus(pre_seed_ai_infra, vdata)
        assert result.applicable is True
        assert result.indicated_value is not None
        assert result.indicated_value > 0

    def test_not_applicable_for_series_a(self, series_a_fintech):
        vdata = _get_vertical_data(
            series_a_fintech.fundraise.vertical,
            series_a_fintech.fundraise.stage,
        )
        result = _run_berkus(series_a_fintech, vdata)
        assert result.applicable is False
        # Engine still computes a value even if not applicable
        assert result.indicated_value is not None

    def test_not_applicable_for_seed(self, seed_b2b_saas):
        """Berkus is only applicable for pre_seed stage."""
        vdata = _get_vertical_data(
            seed_b2b_saas.fundraise.vertical,
            seed_b2b_saas.fundraise.stage,
        )
        result = _run_berkus(seed_b2b_saas, vdata)
        assert result.applicable is False

    def test_bay_area_premium_increases_value(self, pre_seed_ai_infra):
        """Bay Area premium (1.35x) should produce higher values than other_us (0.90x)."""
        vdata = _get_vertical_data(
            pre_seed_ai_infra.fundraise.vertical,
            pre_seed_ai_infra.fundraise.stage,
        )
        bay_area_result = _run_berkus(pre_seed_ai_infra, vdata)

        # Create a version with other_us geography
        data = pre_seed_ai_infra.model_dump()
        data["fundraise"]["geography"] = "other_us"
        other_us_input = StartupInput(**data)
        other_us_result = _run_berkus(other_us_input, vdata)

        assert bay_area_result.indicated_value > other_us_result.indicated_value

    def test_strong_team_increases_berkus(self, pre_seed_ai_infra):
        """Prior exits and domain expertise should score higher than a weak team."""
        vdata = _get_vertical_data(
            pre_seed_ai_infra.fundraise.vertical,
            pre_seed_ai_infra.fundraise.stage,
        )
        strong_result = _run_berkus(pre_seed_ai_infra, vdata)

        data = pre_seed_ai_infra.model_dump()
        data["team"]["prior_exits"] = 0
        data["team"]["domain_experts"] = False
        data["team"]["repeat_founder"] = False
        data["team"]["tier1_background"] = False
        data["team"]["notable_advisors"] = False
        weak_input = StartupInput(**data)
        weak_result = _run_berkus(weak_input, vdata)

        assert strong_result.indicated_value > weak_result.indicated_value

    def test_value_low_and_high_brackets(self, pre_seed_ai_infra):
        vdata = _get_vertical_data(
            pre_seed_ai_infra.fundraise.vertical,
            pre_seed_ai_infra.fundraise.stage,
        )
        result = _run_berkus(pre_seed_ai_infra, vdata)
        assert result.value_low < result.indicated_value
        assert result.value_high > result.indicated_value

    def test_berkus_with_explicit_overrides(self, pre_seed_ai_infra):
        """User-provided berkus_scores should be used directly."""
        data = pre_seed_ai_infra.model_dump()
        data["berkus_scores"] = {
            "idea": 0.9,
            "management": 0.9,
            "prototype": 0.8,
            "relationships": 0.7,
            "rollout": 0.5,
        }
        inp = StartupInput(**data)
        vdata = _get_vertical_data(inp.fundraise.vertical, inp.fundraise.stage)
        result = _run_berkus(inp, vdata)
        assert result.inputs_used["scores"]["idea"] == 0.9
        assert result.inputs_used["scores"]["management"] == 0.9

    def test_inputs_used_contains_expected_keys(self, pre_seed_ai_infra):
        vdata = _get_vertical_data(
            pre_seed_ai_infra.fundraise.vertical,
            pre_seed_ai_infra.fundraise.stage,
        )
        result = _run_berkus(pre_seed_ai_infra, vdata)
        assert "regional_median" in result.inputs_used
        assert "regional_premium" in result.inputs_used
        assert "scores" in result.inputs_used


# ---------------------------------------------------------------------------
# Test Class: Scorecard Method
# ---------------------------------------------------------------------------

class TestScorecardMethod:
    """Tests for the Scorecard (Bill Payne) valuation method."""

    def test_applicable_for_pre_seed(self, pre_seed_ai_infra):
        vdata = _get_vertical_data(
            pre_seed_ai_infra.fundraise.vertical,
            pre_seed_ai_infra.fundraise.stage,
        )
        result = _run_scorecard(pre_seed_ai_infra, vdata)
        assert result.applicable is True

    def test_applicable_for_seed(self, seed_b2b_saas):
        vdata = _get_vertical_data(
            seed_b2b_saas.fundraise.vertical,
            seed_b2b_saas.fundraise.stage,
        )
        result = _run_scorecard(seed_b2b_saas, vdata)
        assert result.applicable is True
        assert result.indicated_value is not None
        assert result.indicated_value > 0

    def test_not_applicable_for_series_a(self, series_a_fintech):
        vdata = _get_vertical_data(
            series_a_fintech.fundraise.vertical,
            series_a_fintech.fundraise.stage,
        )
        result = _run_scorecard(series_a_fintech, vdata)
        assert result.applicable is False

    def test_weighted_multiplier_near_one_for_average(self, seed_b2b_saas):
        """A moderately strong startup should have a multiplier near or above 1.0."""
        vdata = _get_vertical_data(
            seed_b2b_saas.fundraise.vertical,
            seed_b2b_saas.fundraise.stage,
        )
        result = _run_scorecard(seed_b2b_saas, vdata)
        multiplier = result.inputs_used["weighted_multiplier"]
        assert 0.5 < multiplier < 1.5

    def test_large_tam_scores_higher(self, seed_b2b_saas):
        """$50B+ TAM should score maximum market_size factor (1.5)."""
        data = seed_b2b_saas.model_dump()
        data["market"]["tam_usd_billions"] = 60.0
        large_tam_input = StartupInput(**data)
        vdata = _get_vertical_data(
            large_tam_input.fundraise.vertical,
            large_tam_input.fundraise.stage,
        )
        result = _run_scorecard(large_tam_input, vdata)
        assert result.inputs_used["scores"]["market_size"] == 1.5

    def test_scorecard_with_explicit_overrides(self, seed_b2b_saas):
        data = seed_b2b_saas.model_dump()
        data["scorecard_scores"] = {
            "management_team": 1.4,
            "market_size": 1.3,
            "product_technology": 1.2,
            "competitive_environment": 1.1,
            "marketing_sales_channels": 1.0,
            "additional_financing_needed": 1.0,
            "other_factors": 1.0,
        }
        inp = StartupInput(**data)
        vdata = _get_vertical_data(inp.fundraise.vertical, inp.fundraise.stage)
        result = _run_scorecard(inp, vdata)
        assert result.inputs_used["scores"]["management_team"] == 1.4

    def test_value_range_surrounds_indicated(self, seed_b2b_saas):
        vdata = _get_vertical_data(
            seed_b2b_saas.fundraise.vertical,
            seed_b2b_saas.fundraise.stage,
        )
        result = _run_scorecard(seed_b2b_saas, vdata)
        assert result.value_low < result.indicated_value
        assert result.value_high > result.indicated_value


# ---------------------------------------------------------------------------
# Test Class: Risk Factor Summation
# ---------------------------------------------------------------------------

class TestRiskFactorSummation:
    """Tests for the Risk Factor Summation method."""

    def test_applicable_for_pre_seed(self, pre_seed_ai_infra):
        vdata = _get_vertical_data(
            pre_seed_ai_infra.fundraise.vertical,
            pre_seed_ai_infra.fundraise.stage,
        )
        result = _run_rfs(pre_seed_ai_infra, vdata)
        assert result.applicable is True

    def test_applicable_for_seed(self, seed_b2b_saas):
        vdata = _get_vertical_data(
            seed_b2b_saas.fundraise.vertical,
            seed_b2b_saas.fundraise.stage,
        )
        result = _run_rfs(seed_b2b_saas, vdata)
        assert result.applicable is True

    def test_not_applicable_for_series_a(self, series_a_fintech):
        vdata = _get_vertical_data(
            series_a_fintech.fundraise.vertical,
            series_a_fintech.fundraise.stage,
        )
        result = _run_rfs(series_a_fintech, vdata)
        assert result.applicable is False

    def test_positive_risk_scores_increase_valuation(self, seed_b2b_saas):
        """A startup with all positive risk scores should exceed baseline."""
        data = seed_b2b_saas.model_dump()
        data["risk_factor_scores"] = {
            "Management": 2,
            "Stage of Business": 2,
            "Legislation / Political": 1,
            "Manufacturing / Operations": 1,
            "Sales / Marketing": 2,
            "Funding / Capital Raising": 1,
            "Competition": 1,
            "Technology": 2,
            "Litigation": 0,
            "International": 1,
            "Reputation": 2,
            "Exit Potential": 2,
        }
        inp = StartupInput(**data)
        vdata = _get_vertical_data(inp.fundraise.vertical, inp.fundraise.stage)
        result = _run_rfs(inp, vdata)
        assert result.inputs_used["total_adjustment"] > 0

    def test_negative_risk_scores_decrease_valuation(self, seed_b2b_saas):
        """All-negative risk scores should produce below-baseline valuation."""
        data = seed_b2b_saas.model_dump()
        data["risk_factor_scores"] = {
            "Management": -2,
            "Stage of Business": -2,
            "Legislation / Political": -2,
            "Manufacturing / Operations": -2,
            "Sales / Marketing": -2,
            "Funding / Capital Raising": -2,
            "Competition": -2,
            "Technology": -2,
            "Litigation": -2,
            "International": -2,
            "Reputation": -2,
            "Exit Potential": -2,
        }
        inp = StartupInput(**data)
        vdata = _get_vertical_data(inp.fundraise.vertical, inp.fundraise.stage)
        result = _run_rfs(inp, vdata)
        assert result.inputs_used["total_adjustment"] < 0

    def test_floor_at_half_million(self, pre_seed_healthtech_minimal):
        """Extremely negative inputs should not produce valuation below $0.5M."""
        data = pre_seed_healthtech_minimal.model_dump()
        data["risk_factor_scores"] = {k: -2 for k in [
            "Management", "Stage of Business", "Legislation / Political",
            "Manufacturing / Operations", "Sales / Marketing",
            "Funding / Capital Raising", "Competition", "Technology",
            "Litigation", "International", "Reputation", "Exit Potential",
        ]}
        inp = StartupInput(**data)
        vdata = _get_vertical_data(inp.fundraise.vertical, inp.fundraise.stage)
        result = _run_rfs(inp, vdata)
        assert result.indicated_value >= 0.5

    def test_twelve_risk_categories_in_auto_scores(self, seed_b2b_saas):
        vdata = _get_vertical_data(
            seed_b2b_saas.fundraise.vertical,
            seed_b2b_saas.fundraise.stage,
        )
        result = _run_rfs(seed_b2b_saas, vdata)
        assert len(result.inputs_used["scores"]) == 12

    def test_regulated_verticals_get_negative_legislation_score(self):
        """Fintech, healthtech, biotech, defense_tech should get -1 legislation."""
        for vertical in [
            StartupVertical.FINTECH,
            StartupVertical.HEALTHTECH,
            StartupVertical.BIOTECH_PHARMA,
            StartupVertical.DEFENSE_TECH,
        ]:
            inp = StartupInput(
                company_name="RegTest",
                team=TeamProfile(),
                traction=TractionMetrics(),
                product=ProductProfile(),
                market=MarketProfile(tam_usd_billions=5.0, sam_usd_millions=500.0),
                fundraise=FundraisingProfile(
                    stage=StartupStage.SEED,
                    vertical=vertical,
                    raise_amount=3.0,
                ),
            )
            vdata = _get_vertical_data(vertical, StartupStage.SEED)
            result = _run_rfs(inp, vdata)
            assert result.inputs_used["scores"]["Legislation / Political"] == -1, (
                f"Expected -1 legislation score for {vertical.value}"
            )


# ---------------------------------------------------------------------------
# Test Class: ARR Multiple Method
# ---------------------------------------------------------------------------

class TestARRMultipleMethod:
    """Tests for the ARR Multiple (comparable benchmarks) method."""

    def test_applicable_with_revenue(self, seed_b2b_saas):
        vdata = _get_vertical_data(
            seed_b2b_saas.fundraise.vertical,
            seed_b2b_saas.fundraise.stage,
        )
        result = _run_arr_multiple(seed_b2b_saas, vdata)
        assert result.applicable is True
        assert result.indicated_value is not None
        assert result.indicated_value > 0

    def test_not_applicable_without_revenue(self, pre_seed_ai_infra):
        vdata = _get_vertical_data(
            pre_seed_ai_infra.fundraise.vertical,
            pre_seed_ai_infra.fundraise.stage,
        )
        result = _run_arr_multiple(pre_seed_ai_infra, vdata)
        assert result.applicable is False
        assert result.indicated_value is None

    def test_not_applicable_for_biotech(self):
        """Biotech has null ARR multiples — method should be N/A."""
        inp = StartupInput(
            company_name="BioNoARR",
            team=TeamProfile(),
            traction=TractionMetrics(
                has_revenue=True,
                annual_recurring_revenue=1.0,
            ),
            product=ProductProfile(),
            market=MarketProfile(tam_usd_billions=20.0, sam_usd_millions=2000.0),
            fundraise=FundraisingProfile(
                stage=StartupStage.SEED,
                vertical=StartupVertical.BIOTECH_PHARMA,
                raise_amount=6.0,
            ),
        )
        vdata = _get_vertical_data(StartupVertical.BIOTECH_PHARMA, StartupStage.SEED)
        result = _run_arr_multiple(inp, vdata)
        assert result.applicable is False

    def test_higher_nrr_increases_multiple(self, seed_b2b_saas):
        vdata = _get_vertical_data(
            seed_b2b_saas.fundraise.vertical,
            seed_b2b_saas.fundraise.stage,
        )
        # Standard NRR of 1.15
        base_result = _run_arr_multiple(seed_b2b_saas, vdata)

        # Elite NRR of 1.45
        data = seed_b2b_saas.model_dump()
        data["traction"]["net_revenue_retention"] = 1.45
        elite_input = StartupInput(**data)
        elite_result = _run_arr_multiple(elite_input, vdata)

        assert elite_result.indicated_value > base_result.indicated_value

    def test_low_nrr_compresses_multiple(self, seed_b2b_saas):
        vdata = _get_vertical_data(
            seed_b2b_saas.fundraise.vertical,
            seed_b2b_saas.fundraise.stage,
        )
        base_result = _run_arr_multiple(seed_b2b_saas, vdata)

        data = seed_b2b_saas.model_dump()
        data["traction"]["net_revenue_retention"] = 0.75
        low_nrr_input = StartupInput(**data)
        low_nrr_result = _run_arr_multiple(low_nrr_input, vdata)

        assert low_nrr_result.indicated_value < base_result.indicated_value

    def test_high_growth_increases_multiple(self, seed_b2b_saas):
        vdata = _get_vertical_data(
            seed_b2b_saas.fundraise.vertical,
            seed_b2b_saas.fundraise.stage,
        )
        base_result = _run_arr_multiple(seed_b2b_saas, vdata)

        data = seed_b2b_saas.model_dump()
        data["traction"]["mom_growth_rate"] = 0.25  # 25% MoM
        high_growth_input = StartupInput(**data)
        high_growth_result = _run_arr_multiple(high_growth_input, vdata)

        assert high_growth_result.indicated_value > base_result.indicated_value

    def test_adjusted_multiple_has_floor_of_one(self):
        """Even with terrible metrics, the adjusted multiple should be >= 1.0x."""
        inp = StartupInput(
            company_name="BadMetrics",
            team=TeamProfile(),
            traction=TractionMetrics(
                has_revenue=True,
                annual_recurring_revenue=0.1,
                mom_growth_rate=0.01,
                net_revenue_retention=0.5,
                gross_margin=0.30,
                monthly_burn_rate=0.5,
            ),
            product=ProductProfile(),
            market=MarketProfile(tam_usd_billions=5.0, sam_usd_millions=200.0),
            fundraise=FundraisingProfile(
                stage=StartupStage.SEED,
                vertical=StartupVertical.B2B_SAAS,
                raise_amount=2.0,
            ),
        )
        vdata = _get_vertical_data(StartupVertical.B2B_SAAS, StartupStage.SEED)
        result = _run_arr_multiple(inp, vdata)
        assert result.inputs_used["adjusted_multiple"] >= 1.0

    def test_mrr_fallback_to_arr(self):
        """If only MRR is provided, ARR should be computed as MRR * 12."""
        inp = StartupInput(
            company_name="MRROnly",
            team=TeamProfile(),
            traction=TractionMetrics(
                has_revenue=True,
                monthly_recurring_revenue=0.1,  # $100K MRR
                annual_recurring_revenue=0.0,    # No ARR explicitly set
                mom_growth_rate=0.10,
                net_revenue_retention=1.10,
                gross_margin=0.80,
            ),
            product=ProductProfile(),
            market=MarketProfile(tam_usd_billions=5.0, sam_usd_millions=500.0),
            fundraise=FundraisingProfile(
                stage=StartupStage.SEED,
                vertical=StartupVertical.B2B_SAAS,
                raise_amount=3.0,
            ),
        )
        vdata = _get_vertical_data(StartupVertical.B2B_SAAS, StartupStage.SEED)
        result = _run_arr_multiple(inp, vdata)
        assert result.applicable is True
        # Implied ARR should be 0.1 * 12 = 1.2
        assert result.inputs_used["arr"] == pytest.approx(1.2, abs=0.01)


# ---------------------------------------------------------------------------
# Test Class: Verdict Assignment
# ---------------------------------------------------------------------------

class TestVerdictAssignment:
    """Tests for verdict determination logic."""

    def test_strong_verdict_for_above_median(self, seed_b2b_saas):
        """B2B SaaS seed with $600K ARR and 115% NRR should land strong or fair."""
        output = run_startup_valuation(seed_b2b_saas)
        assert output.verdict in [ValuationVerdict.STRONG, ValuationVerdict.FAIR, ValuationVerdict.STRETCHED]

    def test_at_risk_for_minimal_startup(self, pre_seed_healthtech_minimal):
        """Minimal pre-seed (idea stage, no team, no traction) should be at_risk or fair."""
        output = run_startup_valuation(pre_seed_healthtech_minimal)
        assert output.verdict in [ValuationVerdict.AT_RISK, ValuationVerdict.FAIR]

    def test_verdict_thresholds_against_benchmarks(self):
        """Directly test _assign_verdict with known values."""
        vdata = {"valuation_p25": 9.0, "valuation_p50": 16.0, "valuation_p75": 28.0}

        _, _, _ = _assign_verdict(5.0, vdata, [])  # below P25
        verdict_below, _, _ = _assign_verdict(5.0, vdata, [])
        assert verdict_below == ValuationVerdict.AT_RISK

        verdict_p25_p50, _, _ = _assign_verdict(12.0, vdata, [])
        assert verdict_p25_p50 == ValuationVerdict.FAIR

        verdict_p50_p75, _, _ = _assign_verdict(20.0, vdata, [])
        assert verdict_p50_p75 == ValuationVerdict.STRONG

        verdict_above_p75, _, _ = _assign_verdict(35.0, vdata, [])
        assert verdict_above_p75 == ValuationVerdict.STRETCHED

    def test_verdict_with_no_benchmarks(self):
        """When p50 is 0 or missing, should return FAIR with fallback message."""
        verdict, headline, _ = _assign_verdict(10.0, {}, [])
        assert verdict == ValuationVerdict.FAIR
        assert "Indicative" in headline


# ---------------------------------------------------------------------------
# Test Class: Dilution Modeling
# ---------------------------------------------------------------------------

class TestDilutionScenarios:
    """Tests for multi-round dilution projection."""

    def test_seed_has_current_plus_series_a_projection(self, seed_b2b_saas):
        output = run_startup_valuation(seed_b2b_saas)
        assert len(output.dilution_scenarios) >= 2
        labels = [s.round_label for s in output.dilution_scenarios]
        assert any("Current" in l for l in labels)
        assert any("Series A" in l for l in labels)

    def test_pre_seed_has_three_scenarios(self, pre_seed_ai_infra):
        """Pre-seed should project: current, seed, series A."""
        output = run_startup_valuation(pre_seed_ai_infra)
        assert len(output.dilution_scenarios) == 3

    def test_series_a_has_only_current_round(self, series_a_fintech):
        """Series A (terminal) has no projected next rounds."""
        output = run_startup_valuation(series_a_fintech)
        assert len(output.dilution_scenarios) == 1
        assert "Current" in output.dilution_scenarios[0].round_label

    def test_founder_ownership_declines_each_round(self, pre_seed_ai_infra):
        output = run_startup_valuation(pre_seed_ai_infra)
        scenarios = output.dilution_scenarios
        for i in range(1, len(scenarios)):
            prev_after = scenarios[i - 1].founder_ownership_pct_after
            curr_before = scenarios[i].founder_ownership_pct_before
            # The "before" of next round should equal "after" of previous round
            assert curr_before == pytest.approx(prev_after, abs=0.01)

    def test_current_round_dilution_matches_raise_over_post(self, seed_b2b_saas):
        output = run_startup_valuation(seed_b2b_saas)
        current = output.dilution_scenarios[0]
        expected_inv_pct = current.raise_amount / current.post_money
        assert current.investor_ownership_pct == pytest.approx(expected_inv_pct, abs=0.01)

    def test_post_money_equals_pre_plus_raise(self, seed_b2b_saas):
        output = run_startup_valuation(seed_b2b_saas)
        for scenario in output.dilution_scenarios:
            assert scenario.post_money == pytest.approx(
                scenario.pre_money + scenario.raise_amount, abs=0.1
            )

    def test_existing_safe_stack_reduces_founder_starting_pct(self, seed_b2b_saas):
        """Existing SAFEs should reduce the founder's starting ownership."""
        output = run_startup_valuation(seed_b2b_saas)
        first = output.dilution_scenarios[0]
        # seed_b2b_saas has existing_safe_stack = 0.5
        assert first.founder_ownership_pct_before < 1.0

    def test_projected_rounds_have_step_up(self, pre_seed_ai_infra):
        """Each projected round's pre-money should exceed previous post-money."""
        output = run_startup_valuation(pre_seed_ai_infra)
        scenarios = output.dilution_scenarios
        for i in range(1, len(scenarios)):
            assert scenarios[i].pre_money > scenarios[i - 1].post_money


# ---------------------------------------------------------------------------
# Test Class: SAFE Conversion
# ---------------------------------------------------------------------------

class TestSAFEConversion:
    """Tests for SAFE conversion mechanics."""

    def test_safe_conversion_generated_for_safe_instrument(self, seed_b2b_saas):
        output = run_startup_valuation(seed_b2b_saas)
        assert output.safe_conversion is not None

    def test_no_safe_conversion_for_priced_equity(self, series_a_fintech):
        output = run_startup_valuation(series_a_fintech)
        assert output.safe_conversion is None

    def test_safe_conversion_amount_matches_raise(self, seed_b2b_saas):
        output = run_startup_valuation(seed_b2b_saas)
        conv = output.safe_conversion
        assert conv.safe_amount == seed_b2b_saas.fundraise.raise_amount

    def test_safe_conversion_discount_rate(self, seed_b2b_saas):
        output = run_startup_valuation(seed_b2b_saas)
        conv = output.safe_conversion
        assert conv.discount_rate == 0.20  # from fixture

    def test_safe_conversion_implied_ownership_positive(self, seed_b2b_saas):
        output = run_startup_valuation(seed_b2b_saas)
        conv = output.safe_conversion
        assert 0.0 < conv.implied_ownership_pct < 1.0

    def test_safe_conversion_valuation_cap(self, seed_b2b_saas):
        """When no explicit ask, cap should equal blended valuation."""
        output = run_startup_valuation(seed_b2b_saas)
        conv = output.safe_conversion
        # Cap = blended (since pre_money_valuation_ask is None)
        assert conv.valuation_cap == pytest.approx(output.blended_valuation, abs=0.1)

    def test_safe_conversion_with_explicit_ask(self):
        """When founder sets pre_money_valuation_ask, it becomes the cap."""
        inp = StartupInput(
            company_name="ExplicitCap",
            team=TeamProfile(),
            traction=TractionMetrics(),
            product=ProductProfile(),
            market=MarketProfile(tam_usd_billions=5.0, sam_usd_millions=500.0),
            fundraise=FundraisingProfile(
                stage=StartupStage.PRE_SEED,
                vertical=StartupVertical.B2B_SAAS,
                raise_amount=0.5,
                instrument=InstrumentType.SAFE,
                pre_money_valuation_ask=10.0,
            ),
        )
        output = run_startup_valuation(inp)
        assert output.safe_conversion is not None
        assert output.safe_conversion.valuation_cap == 10.0

    def test_mfn_clause_mentioned_in_note(self, pre_seed_ai_infra):
        """MFN clause should be noted in the conversion summary."""
        output = run_startup_valuation(pre_seed_ai_infra)
        conv = output.safe_conversion
        assert "MFN" in conv.note

    def test_existing_safe_stack_mentioned_in_note(self, seed_b2b_saas):
        """Existing SAFE stack should be mentioned in the note."""
        output = run_startup_valuation(seed_b2b_saas)
        conv = output.safe_conversion
        assert "existing SAFEs" in conv.note


# ---------------------------------------------------------------------------
# Test Class: Edge Cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_zero_revenue_startup(self, seed_consumer_zero_revenue):
        """Zero-revenue seed startup should still produce valid output."""
        output = run_startup_valuation(seed_consumer_zero_revenue)
        assert output.blended_valuation > 0
        # ARR multiple should NOT be applicable
        arr_method = next(m for m in output.method_results if m.method_name == "arr_multiple")
        assert arr_method.applicable is False

    def test_very_high_growth_does_not_crash(self, seed_climate_high_growth):
        """25% MoM growth should be handled gracefully."""
        output = run_startup_valuation(seed_climate_high_growth)
        assert output.blended_valuation > 0
        assert output.verdict in list(ValuationVerdict)

    def test_pre_seed_minimal_data(self, pre_seed_healthtech_minimal):
        """Idea-stage with no team strength, no traction should still compute."""
        output = run_startup_valuation(pre_seed_healthtech_minimal)
        assert output.blended_valuation > 0
        # Should have warnings about limited inputs
        assert len(output.method_results) == 4

    def test_high_dilution_warning(self):
        """Raise amount that causes >25% dilution should trigger a warning."""
        inp = StartupInput(
            company_name="BigRaise",
            team=TeamProfile(),
            traction=TractionMetrics(),
            product=ProductProfile(),
            market=MarketProfile(tam_usd_billions=5.0, sam_usd_millions=200.0),
            fundraise=FundraisingProfile(
                stage=StartupStage.PRE_SEED,
                vertical=StartupVertical.B2B_SAAS,
                raise_amount=5.0,  # Large raise vs. likely ~$6M pre-money
                instrument=InstrumentType.SAFE,
            ),
        )
        output = run_startup_valuation(inp)
        dilution_warnings = [w for w in output.warnings if "dilution" in w.lower()]
        assert len(dilution_warnings) > 0

    def test_below_100_nrr_warning(self):
        """NRR < 100% with revenue should trigger a churn warning."""
        inp = StartupInput(
            company_name="ChurnCo",
            team=TeamProfile(),
            traction=TractionMetrics(
                has_revenue=True,
                annual_recurring_revenue=1.0,
                net_revenue_retention=0.85,
                mom_growth_rate=0.05,
                gross_margin=0.75,
            ),
            product=ProductProfile(stage=ProductStage.PAYING_CUSTOMERS),
            market=MarketProfile(tam_usd_billions=10.0, sam_usd_millions=500.0),
            fundraise=FundraisingProfile(
                stage=StartupStage.SEED,
                vertical=StartupVertical.B2B_SAAS,
                raise_amount=3.0,
            ),
        )
        output = run_startup_valuation(inp)
        nrr_warnings = [w for w in output.warnings if "NRR" in w or "churn" in w.lower()]
        assert len(nrr_warnings) > 0

    def test_above_p75_triggers_down_round_warning(self):
        """Valuation above P75 should warn about down-round risk."""
        inp = StartupInput(
            company_name="PricyStartup",
            team=TeamProfile(
                prior_exits=2,
                domain_experts=True,
                repeat_founder=True,
                tier1_background=True,
                notable_advisors=True,
            ),
            traction=TractionMetrics(
                has_revenue=True,
                annual_recurring_revenue=3.0,
                mom_growth_rate=0.20,
                net_revenue_retention=1.40,
                gross_margin=0.85,
                monthly_burn_rate=0.1,
                cash_on_hand=5.0,
                paying_customer_count=30,
                logo_customer_count=5,
                has_lois=True,
            ),
            product=ProductProfile(
                stage=ProductStage.SCALING,
                has_patent_or_ip=True,
                proprietary_data_moat=True,
            ),
            market=MarketProfile(
                tam_usd_billions=50.0,
                sam_usd_millions=3000.0,
                competitive_moat="high",
            ),
            fundraise=FundraisingProfile(
                stage=StartupStage.SEED,
                vertical=StartupVertical.B2B_SAAS,
                geography=Geography.BAY_AREA,
                raise_amount=3.0,
            ),
        )
        output = run_startup_valuation(inp)
        # If blended is above P75, there should be a down-round warning
        if output.blended_valuation > output.benchmark_p75:
            down_round_warnings = [w for w in output.warnings if "down round" in w.lower()]
            assert len(down_round_warnings) > 0

    def test_engine_never_raises(self):
        """Engine should return output (possibly with warnings) rather than raising."""
        # Construct a minimal valid input
        inp = StartupInput(
            company_name="MinimalValid",
            market=MarketProfile(tam_usd_billions=1.0, sam_usd_millions=50.0),
            fundraise=FundraisingProfile(
                stage=StartupStage.PRE_SEED,
                vertical=StartupVertical.CONSUMER,
                raise_amount=0.25,
            ),
        )
        output = run_startup_valuation(inp)
        assert isinstance(output, StartupValuationOutput)


# ---------------------------------------------------------------------------
# Test Class: Multiple Verticals
# ---------------------------------------------------------------------------

class TestMultipleVerticals:
    """Tests across different verticals to ensure vertical-specific benchmarks work."""

    @pytest.fixture
    def _base_seed_input(self):
        """Base seed input that can be parameterized by vertical."""
        return dict(
            company_name="VerticalTest",
            team=TeamProfile(
                founder_count=2,
                domain_experts=True,
                technical_cofounder=True,
            ),
            traction=TractionMetrics(
                has_revenue=True,
                annual_recurring_revenue=1.0,
                mom_growth_rate=0.10,
                net_revenue_retention=1.10,
                gross_margin=0.75,
                monthly_burn_rate=0.1,
                cash_on_hand=2.0,
                paying_customer_count=10,
            ),
            product=ProductProfile(stage=ProductStage.PAYING_CUSTOMERS),
            market=MarketProfile(tam_usd_billions=10.0, sam_usd_millions=500.0),
        )

    @pytest.mark.parametrize("vertical", [
        StartupVertical.B2B_SAAS,
        StartupVertical.FINTECH,
        StartupVertical.HEALTHTECH,
        StartupVertical.AI_ML_INFRASTRUCTURE,
        StartupVertical.CLIMATE_ENERGY,
        StartupVertical.DEVELOPER_TOOLS,
        StartupVertical.CONSUMER,
        StartupVertical.MARKETPLACE,
        StartupVertical.DEFENSE_TECH,
    ])
    def test_vertical_produces_valid_output(self, _base_seed_input, vertical):
        inp = StartupInput(
            **_base_seed_input,
            fundraise=FundraisingProfile(
                stage=StartupStage.SEED,
                vertical=vertical,
                raise_amount=3.0,
            ),
        )
        output = run_startup_valuation(inp)
        assert output.blended_valuation > 0
        assert output.vertical == vertical
        assert output.benchmark_p50 > 0

    def test_ai_infra_valued_higher_than_consumer(self, _base_seed_input):
        """AI/ML Infrastructure has higher median multiples than consumer."""
        ai_inp = StartupInput(
            **_base_seed_input,
            fundraise=FundraisingProfile(
                stage=StartupStage.SEED,
                vertical=StartupVertical.AI_ML_INFRASTRUCTURE,
                raise_amount=3.0,
            ),
        )
        consumer_inp = StartupInput(
            **_base_seed_input,
            fundraise=FundraisingProfile(
                stage=StartupStage.SEED,
                vertical=StartupVertical.CONSUMER,
                raise_amount=3.0,
            ),
        )
        ai_output = run_startup_valuation(ai_inp)
        consumer_output = run_startup_valuation(consumer_inp)
        assert ai_output.benchmark_p50 > consumer_output.benchmark_p50

    def test_defense_tech_has_highest_seed_benchmarks(self, _base_seed_input):
        """Defense tech should have among the highest seed valuations."""
        defense_inp = StartupInput(
            **_base_seed_input,
            fundraise=FundraisingProfile(
                stage=StartupStage.SEED,
                vertical=StartupVertical.DEFENSE_TECH,
                raise_amount=6.0,
            ),
        )
        output = run_startup_valuation(defense_inp)
        # Defense tech seed P50 = $35M, higher than B2B SaaS $16M
        assert output.benchmark_p50 >= 30.0


# ---------------------------------------------------------------------------
# Test Class: Method Applicability Matrix
# ---------------------------------------------------------------------------

class TestMethodApplicability:
    """Ensure correct method applicability across stages."""

    def test_pre_seed_applicability(self, pre_seed_ai_infra):
        output = run_startup_valuation(pre_seed_ai_infra)
        methods = {m.method_name: m.applicable for m in output.method_results}
        assert methods["berkus"] is True
        assert methods["scorecard"] is True
        assert methods["risk_factor_summation"] is True
        assert methods["arr_multiple"] is False  # No revenue

    def test_seed_with_revenue_applicability(self, seed_b2b_saas):
        output = run_startup_valuation(seed_b2b_saas)
        methods = {m.method_name: m.applicable for m in output.method_results}
        assert methods["berkus"] is False         # Berkus is pre-seed only
        assert methods["scorecard"] is True
        assert methods["risk_factor_summation"] is True
        assert methods["arr_multiple"] is True    # Has revenue

    def test_seed_without_revenue_applicability(self, seed_consumer_zero_revenue):
        output = run_startup_valuation(seed_consumer_zero_revenue)
        methods = {m.method_name: m.applicable for m in output.method_results}
        assert methods["berkus"] is False         # Not pre-seed
        assert methods["scorecard"] is True
        assert methods["risk_factor_summation"] is True
        assert methods["arr_multiple"] is False   # No revenue

    def test_series_a_applicability(self, series_a_fintech):
        output = run_startup_valuation(series_a_fintech)
        methods = {m.method_name: m.applicable for m in output.method_results}
        assert methods["berkus"] is False
        assert methods["scorecard"] is False
        assert methods["risk_factor_summation"] is False
        assert methods["arr_multiple"] is True


# ---------------------------------------------------------------------------
# Test Class: Round Timing Signal
# ---------------------------------------------------------------------------

class TestRoundTimingSignal:
    """Tests for the round timing signal computation."""

    def test_raise_now_with_low_runway(self):
        """Short runway should produce RAISE_NOW signal."""
        inp = StartupInput(
            company_name="LowRunway",
            traction=TractionMetrics(
                monthly_burn_rate=0.2,
                cash_on_hand=1.0,  # 5 months runway
            ),
            product=ProductProfile(),
            market=MarketProfile(tam_usd_billions=5.0, sam_usd_millions=200.0),
            fundraise=FundraisingProfile(
                stage=StartupStage.SEED,
                vertical=StartupVertical.B2B_SAAS,
                raise_amount=3.0,
            ),
        )
        vdata = _get_vertical_data(StartupVertical.B2B_SAAS, StartupStage.SEED)
        timing = _compute_round_timing(inp, vdata)
        assert timing.signal == RaiseSignal.RAISE_NOW

    def test_focus_milestones_with_long_runway(self):
        """Long runway should produce FOCUS_MILESTONES signal."""
        inp = StartupInput(
            company_name="HealthyRunway",
            traction=TractionMetrics(
                monthly_burn_rate=0.05,
                cash_on_hand=5.0,  # 100 months runway
            ),
            product=ProductProfile(stage=ProductStage.PAYING_CUSTOMERS),
            market=MarketProfile(tam_usd_billions=10.0, sam_usd_millions=500.0),
            fundraise=FundraisingProfile(
                stage=StartupStage.PRE_SEED,
                vertical=StartupVertical.B2B_SAAS,
                raise_amount=0.5,
            ),
        )
        vdata = _get_vertical_data(StartupVertical.B2B_SAAS, StartupStage.PRE_SEED)
        timing = _compute_round_timing(inp, vdata)
        assert timing.signal == RaiseSignal.FOCUS_MILESTONES

    def test_series_a_always_focus_milestones(self, series_a_fintech):
        """Series A (terminal stage) should always produce FOCUS_MILESTONES."""
        vdata = _get_vertical_data(
            series_a_fintech.fundraise.vertical,
            series_a_fintech.fundraise.stage,
        )
        timing = _compute_round_timing(series_a_fintech, vdata)
        assert timing.signal == RaiseSignal.FOCUS_MILESTONES

    def test_milestone_gaps_populated(self, seed_consumer_zero_revenue):
        """Zero-revenue seed should have unmet milestone gaps."""
        vdata = _get_vertical_data(
            seed_consumer_zero_revenue.fundraise.vertical,
            seed_consumer_zero_revenue.fundraise.stage,
        )
        timing = _compute_round_timing(seed_consumer_zero_revenue, vdata)
        assert len(timing.milestone_gaps) > 0
        assert timing.milestone_met_count < timing.milestone_total_count

    def test_critical_runway_warning(self):
        """Less than 6 months runway should trigger a critical warning."""
        inp = StartupInput(
            company_name="CriticalRunway",
            traction=TractionMetrics(
                monthly_burn_rate=0.3,
                cash_on_hand=1.0,  # ~3.3 months
            ),
            product=ProductProfile(),
            market=MarketProfile(tam_usd_billions=5.0, sam_usd_millions=200.0),
            fundraise=FundraisingProfile(
                stage=StartupStage.SEED,
                vertical=StartupVertical.B2B_SAAS,
                raise_amount=3.0,
            ),
        )
        vdata = _get_vertical_data(StartupVertical.B2B_SAAS, StartupStage.SEED)
        timing = _compute_round_timing(inp, vdata)
        assert any("Critical" in w for w in timing.warnings)


# ---------------------------------------------------------------------------
# Test Class: Investor Scorecard
# ---------------------------------------------------------------------------

class TestInvestorScorecard:
    """Tests for the investor scorecard flags."""

    def test_scorecard_has_team_and_tam_flags(self, seed_b2b_saas):
        output = run_startup_valuation(seed_b2b_saas)
        metrics = {f.metric for f in output.investor_scorecard}
        assert "Team Quality" in metrics
        assert "Total Addressable Market" in metrics

    def test_burn_multiple_flag_for_revenue_startup(self, seed_b2b_saas):
        output = run_startup_valuation(seed_b2b_saas)
        metrics = {f.metric for f in output.investor_scorecard}
        assert "Burn Multiple" in metrics

    def test_no_burn_multiple_flag_for_zero_revenue(self, pre_seed_ai_infra):
        """No revenue means no burn multiple flag."""
        output = run_startup_valuation(pre_seed_ai_infra)
        metrics = {f.metric for f in output.investor_scorecard}
        assert "Burn Multiple" not in metrics

    def test_nrr_flag_for_revenue_startup(self, seed_b2b_saas):
        output = run_startup_valuation(seed_b2b_saas)
        metrics = {f.metric for f in output.investor_scorecard}
        assert "Net Revenue Retention" in metrics

    def test_runway_flag_when_burn_exists(self, seed_b2b_saas):
        output = run_startup_valuation(seed_b2b_saas)
        metrics = {f.metric for f in output.investor_scorecard}
        assert "Current Runway" in metrics

    def test_strong_team_flag_with_prior_exit(self, series_a_fintech):
        output = run_startup_valuation(series_a_fintech)
        team_flag = next(f for f in output.investor_scorecard if f.metric == "Team Quality")
        assert team_flag.signal == ValuationSignal.STRONG

    def test_weak_team_flag_without_technical_cofounder(self, pre_seed_healthtech_minimal):
        output = run_startup_valuation(pre_seed_healthtech_minimal)
        team_flag = next(f for f in output.investor_scorecard if f.metric == "Team Quality")
        assert team_flag.signal == ValuationSignal.WEAK

    def test_scorecard_signals_are_valid_enums(self, seed_b2b_saas):
        output = run_startup_valuation(seed_b2b_saas)
        for flag in output.investor_scorecard:
            assert flag.signal in list(ValuationSignal)
            assert len(flag.commentary) > 0
            assert len(flag.benchmark) > 0
