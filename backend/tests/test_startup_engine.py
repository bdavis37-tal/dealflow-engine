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

    def test_arr_weighting_ramps_with_revenue(self, seed_b2b_saas):
        """When ARR exists, the ARR multiple weight ramps with ARR magnitude (S-1)."""
        output = run_startup_valuation(seed_b2b_saas)
        notes_text = " ".join(output.computation_notes)
        # $600K ARR against a $1M ramp threshold → 0.65 × 0.6 = 39% weight
        assert "ARR multiple weighted 39%" in notes_text

    def test_arr_weight_full_65_pct_at_threshold(self, seed_b2b_saas):
        """At/above the ARR ramp threshold, the full 65% weight applies."""
        data = seed_b2b_saas.model_dump()
        data["traction"]["annual_recurring_revenue"] = 2.0
        data["traction"]["monthly_recurring_revenue"] = 2.0 / 12
        output = run_startup_valuation(StartupInput(**data))
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
        assert "per_dimension_cap" in result.inputs_used
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

    def test_existing_safe_stack_converts_at_next_priced_round(self, seed_b2b_saas):
        """
        With a SAFE current round, the existing SAFE stack converts at the
        projected next PRICED round — not at the current unpriced round (S-10).
        """
        output = run_startup_valuation(seed_b2b_saas)
        first = output.dilution_scenarios[0]
        # SAFE round: no conversion yet — founder still at 100% pre-round
        assert first.founder_ownership_pct_before == pytest.approx(1.0)

        # Compare against a no-stack run: at the projected Series A the stack
        # must produce extra founder dilution.
        data = seed_b2b_saas.model_dump()
        data["fundraise"]["existing_safe_stack"] = 0.0
        no_stack = run_startup_valuation(StartupInput(**data))
        with_stack_a = next(s for s in output.dilution_scenarios if "Series A" in s.round_label)
        no_stack_a = next(s for s in no_stack.dilution_scenarios if "Series A" in s.round_label)
        assert with_stack_a.founder_ownership_pct_after < no_stack_a.founder_ownership_pct_after

    def test_existing_safe_stack_converts_now_when_round_is_priced(self, seed_b2b_saas):
        """A priced current round converts the existing SAFE stack immediately."""
        data = seed_b2b_saas.model_dump()
        data["fundraise"]["instrument"] = "priced_equity"
        output = run_startup_valuation(StartupInput(**data))
        first = output.dilution_scenarios[0]
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
        # Defense tech seed P50 = $24M (PitchBook 2025), higher than B2B SaaS $16M
        assert output.benchmark_p50 >= 20.0


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


# ---------------------------------------------------------------------------
# Regression tests for audited defects (S-1 .. S-18)
# ---------------------------------------------------------------------------

def _make_input(**overrides) -> StartupInput:
    """Baseline seed B2B SaaS input for regression scenarios."""
    base = dict(
        company_name="Regression",
        team=TeamProfile(domain_experts=True, technical_cofounder=True),
        traction=TractionMetrics(
            has_revenue=False,
            mom_growth_rate=0.0,
            net_revenue_retention=1.10,
            gross_margin=0.75,
            monthly_burn_rate=0.1,
            cash_on_hand=2.0,
        ),
        product=ProductProfile(stage=ProductStage.BETA),
        market=MarketProfile(tam_usd_billions=10.0, sam_usd_millions=500.0),
        fundraise=FundraisingProfile(
            stage=StartupStage.SEED,
            vertical=StartupVertical.B2B_SAAS,
            raise_amount=3.0,
            instrument=InstrumentType.SAFE,
        ),
    )
    data = StartupInput(**base).model_dump()
    for dotted, value in overrides.items():
        node = data
        parts = dotted.split(".")
        for p in parts[:-1]:
            node = node[p]
        node[parts[-1]] = value
    return StartupInput(**data)


class TestS1RevenueCliff:
    """S-1: ARR weight must ramp with ARR magnitude — no valuation cliff."""

    def test_blended_monotonic_in_arr(self):
        """Blended valuation must be non-decreasing across ARR ∈ {0, 0.05, 0.5, 2.0}."""
        blended_by_arr = []
        for arr in [0.0, 0.05, 0.5, 2.0]:
            inp = _make_input(**{
                "traction.has_revenue": True,  # hold constant so only ARR varies
                "traction.annual_recurring_revenue": arr,
                "traction.mom_growth_rate": 0.10,
            })
            out = run_startup_valuation(inp)
            blended_by_arr.append((arr, out.blended_valuation))
        for (arr_prev, v_prev), (arr_next, v_next) in zip(blended_by_arr, blended_by_arr[1:]):
            assert v_next >= v_prev - 1e-9, (
                f"Valuation dropped from ${v_prev}M at ARR={arr_prev} to ${v_next}M at ARR={arr_next}"
            )

    def test_small_arr_does_not_flip_verdict_negative(self):
        """$50K ARR must not turn a fair/strong pre-revenue verdict into at_risk."""
        pre_rev = run_startup_valuation(_make_input(**{"traction.has_revenue": True}))
        small_arr = run_startup_valuation(_make_input(**{
            "traction.has_revenue": True,
            "traction.annual_recurring_revenue": 0.05,
            "traction.mom_growth_rate": 0.10,
        }))
        assert small_arr.blended_valuation >= pre_rev.blended_valuation - 1e-9
        order = [ValuationVerdict.AT_RISK, ValuationVerdict.FAIR, ValuationVerdict.STRONG, ValuationVerdict.STRETCHED]
        assert order.index(small_arr.verdict) >= order.index(pre_rev.verdict)


class TestS2SAFEConversion:
    """S-2/S-9: post-money SAFE mechanics, discount usage, no fabricated price."""

    def test_post_money_ownership_is_raise_over_cap(self):
        inp = _make_input(**{"fundraise.pre_money_valuation_ask": 15.0})
        out = run_startup_valuation(inp)
        conv = out.safe_conversion
        assert conv.safe_type == "post_money"
        assert conv.implied_ownership_pct == pytest.approx(3.0 / 15.0, abs=1e-4)

    def test_pre_money_ownership_is_raise_over_cap_plus_raise(self):
        inp = _make_input(**{
            "fundraise.pre_money_valuation_ask": 15.0,
            "fundraise.safe_type": "pre_money",
        })
        out = run_startup_valuation(inp)
        conv = out.safe_conversion
        assert conv.safe_type == "pre_money"
        assert conv.implied_ownership_pct == pytest.approx(3.0 / 18.0, abs=1e-4)

    def test_conversion_price_at_cap_is_none(self):
        """No share count is modeled — the per-share price must not be fabricated."""
        out = run_startup_valuation(_make_input())
        assert out.safe_conversion.conversion_price_at_cap is None

    def test_discount_governs_when_deeper_than_cap(self):
        """A low next-round pre-money with a big discount should beat a high cap."""
        inp = _make_input(**{
            "fundraise.pre_money_valuation_ask": 200.0,  # cap far above next round
            "fundraise.safe_discount": 0.25,
        })
        out = run_startup_valuation(inp)
        conv = out.safe_conversion
        assert conv.governing_term == "discount"
        assert conv.conversion_valuation == pytest.approx(conv.next_round_pre_money * 0.75, abs=0.1)
        assert "discount" in conv.note.lower()

    def test_cap_governs_when_below_discounted_round(self):
        inp = _make_input(**{
            "fundraise.pre_money_valuation_ask": 10.0,
            "fundraise.safe_discount": 0.10,
        })
        out = run_startup_valuation(inp)
        conv = out.safe_conversion
        assert conv.governing_term == "cap"
        assert conv.conversion_valuation == pytest.approx(10.0)
        # post-money cap conversion: ownership = raise / cap
        assert conv.conversion_ownership_pct == pytest.approx(3.0 / 10.0, abs=1e-4)

    def test_capless_note_when_no_explicit_ask(self):
        out = run_startup_valuation(_make_input())
        assert "proxy cap" in out.safe_conversion.note


class TestDealMechanicsBasis:
    """Deal mechanics price at the preparer's ask when provided; the model
    midpoint is only the fallback. The blend/range never depend on the ask."""

    def test_no_ask_uses_model_midpoint(self):
        out = run_startup_valuation(_make_input())
        assert out.dilution_basis == "model_midpoint"
        assert out.dilution_basis_pre_money == pytest.approx(out.blended_valuation, abs=0.01)
        assert out.dilution_scenarios[0].pre_money == pytest.approx(out.blended_valuation, abs=0.01)

    def test_ask_prices_current_round_and_implied_dilution(self):
        out = run_startup_valuation(_make_input(**{"fundraise.pre_money_valuation_ask": 15.0}))
        assert out.dilution_basis == "preparer_ask"
        assert out.dilution_basis_pre_money == pytest.approx(15.0)
        current = out.dilution_scenarios[0]
        assert current.pre_money == pytest.approx(15.0)
        assert out.implied_dilution == pytest.approx(3.0 / 18.0, abs=1e-4)

    def test_blend_and_range_are_invariant_to_ask(self):
        base = run_startup_valuation(_make_input())
        asked = run_startup_valuation(_make_input(**{"fundraise.pre_money_valuation_ask": 40.0}))
        assert asked.blended_valuation == pytest.approx(base.blended_valuation)
        assert asked.valuation_range_low == pytest.approx(base.valuation_range_low)
        assert asked.valuation_range_high == pytest.approx(base.valuation_range_high)

    def test_projected_rounds_stay_market_anchored(self):
        """Future rounds are market projections — an aggressive ask must not
        drag the projected next round up with it."""
        base = run_startup_valuation(_make_input())
        asked = run_startup_valuation(_make_input(**{"fundraise.pre_money_valuation_ask": 200.0}))
        base_next = next(s for s in base.dilution_scenarios if "projected" in s.round_label)
        asked_next = next(s for s in asked.dilution_scenarios if "projected" in s.round_label)
        assert asked_next.pre_money == pytest.approx(base_next.pre_money, abs=0.01)

    def test_above_market_ask_flags_down_round(self):
        out = run_startup_valuation(_make_input(**{"fundraise.pre_money_valuation_ask": 200.0}))
        assert any("down round" in w.lower() for w in out.warnings)

    def test_basis_documented_in_computation_notes(self):
        out = run_startup_valuation(_make_input(**{"fundraise.pre_money_valuation_ask": 15.0}))
        assert any("preparer's ask" in n for n in out.computation_notes)


class TestS3AIPremium:
    """S-3 (emergent model): defense_tech frozen; premium emerges from
    parameter-level calibration; range brackets blended."""

    def test_defense_tech_gets_no_ai_premium(self):
        inp = _make_input(**{
            "fundraise.vertical": "defense_tech",
            "fundraise.is_ai_native": True,
            "fundraise.ai_native_score": 1.0,
            "fundraise.raise_amount": 6.0,
        })
        out = run_startup_valuation(inp)
        assert out.ai_modifier_applied is False
        assert out.ai_premium_multiplier is None
        assert out.blended_before_ai is None

    def test_healthtech_emergent_premium(self):
        """Healthtech (1.0 vertical premium) at score 1.0 with meaningful ARR:
        the premium is EMERGENT from parameter calibration, not a post-blend
        scalar — bounded by the AI-enabled SaaS multiple cap."""
        overrides = {
            "fundraise.vertical": "healthtech",
            "traction.has_revenue": True,
            "traction.annual_recurring_revenue": 1.0,
            "traction.mom_growth_rate": 0.10,
        }
        out = run_startup_valuation(_make_input(**{
            **overrides,
            "fundraise.is_ai_native": True,
            "fundraise.ai_native_score": 1.0,
        }))
        baseline = run_startup_valuation(_make_input(**overrides))
        assert out.ai_modifier_applied is True
        assert out.blended_before_ai == pytest.approx(baseline.blended_valuation, rel=1e-6)
        assert 0.0 < out.ai_premium_multiplier <= 0.60
        assert out.blended_valuation == pytest.approx(
            out.blended_before_ai * (1 + out.ai_premium_multiplier), rel=1e-3
        )

    def test_blended_within_range_with_ai_premium(self):
        """Range must be scaled with the premium so blended stays inside it."""
        for vertical, score in [("healthtech", 1.0), ("b2b_saas", 0.8), ("defense_tech", 1.0)]:
            inp = _make_input(**{
                "fundraise.vertical": vertical,
                "fundraise.is_ai_native": True,
                "fundraise.ai_native_score": score,
            })
            out = run_startup_valuation(inp)
            assert out.valuation_range_low <= out.blended_valuation <= out.valuation_range_high, (
                f"{vertical}: blended {out.blended_valuation} outside "
                f"[{out.valuation_range_low}, {out.valuation_range_high}]"
            )


class TestS4OverrideValidation:
    """S-4: partial/out-of-range user overrides must be filled, clamped, warned."""

    def test_partial_scorecard_override_fills_neutral(self):
        """{'management_team': 1.5} alone must RAISE the valuation, not lower it."""
        base = run_startup_valuation(_make_input())
        boosted = run_startup_valuation(_make_input(scorecard_scores={"management_team": 1.5}))
        assert boosted.blended_valuation > base.blended_valuation

    def test_scorecard_values_clamped(self):
        wild = run_startup_valuation(_make_input(scorecard_scores={"management_team": 99.0}))
        capped = run_startup_valuation(_make_input(scorecard_scores={"management_team": 1.5}))
        assert wild.blended_valuation == pytest.approx(capped.blended_valuation, rel=1e-6)
        assert any("clamped" in w for w in wild.warnings)

    def test_scorecard_unknown_key_warns(self):
        out = run_startup_valuation(_make_input(scorecard_scores={"management_team": 1.2, "vibes": 1.5}))
        assert any("Unknown scorecard factor" in w for w in out.warnings)

    def test_rfs_scores_clamped_to_max_steps(self):
        """{'Management': 100} must behave exactly like {'Management': 2}."""
        wild = run_startup_valuation(_make_input(risk_factor_scores={"Management": 100}))
        capped = run_startup_valuation(_make_input(risk_factor_scores={"Management": 2}))
        assert wild.blended_valuation == pytest.approx(capped.blended_valuation, rel=1e-6)
        assert any("clamped" in w for w in wild.warnings)

    def test_rfs_unknown_category_ignored_with_warning(self):
        out = run_startup_valuation(_make_input(risk_factor_scores={"Management": 1, "Moon Phase": 2}))
        rfs_method = next(m for m in out.method_results if m.method_name == "risk_factor_summation")
        assert "Moon Phase" not in rfs_method.inputs_used["scores"]
        assert any("Unknown risk factor" in w for w in out.warnings)


class TestS5ARRRangeBracket:
    """S-5: ARR-method indicated value must sit inside its own low/high range."""

    @pytest.mark.parametrize("nrr,mom,gm", [
        (1.45, 0.25, 0.85),   # elite everything — max positive adjustment
        (0.75, 0.01, 0.30),   # terrible everything — max negative adjustment
        (1.10, 0.10, 0.75),   # median
    ])
    def test_indicated_within_bounds(self, nrr, mom, gm):
        inp = _make_input(**{
            "traction.has_revenue": True,
            "traction.annual_recurring_revenue": 1.0,
            "traction.net_revenue_retention": nrr,
            "traction.mom_growth_rate": mom,
            "traction.gross_margin": gm,
        })
        vdata = _get_vertical_data(inp.fundraise.vertical, inp.fundraise.stage)
        result = _run_arr_multiple(inp, vdata)
        assert result.value_low <= result.indicated_value <= result.value_high


class TestS6BerkusCeiling:
    """S-6: Berkus must respect the ~$3.5M ceiling, scaled by regional premium only."""

    def test_max_berkus_is_3_5m_times_regional_premium(self):
        inp = _make_input(
            **{"fundraise.stage": "pre_seed", "fundraise.geography": "other_us"},
            berkus_scores={"idea": 1.0, "management": 1.0, "prototype": 1.0, "relationships": 1.0, "rollout": 1.0},
        )
        vdata = _get_vertical_data(inp.fundraise.vertical, inp.fundraise.stage)
        result = _run_berkus(inp, vdata)
        # other_us premium is < 1.0, so indicated must be <= 3.5
        assert result.indicated_value <= 3.5

    def test_berkus_independent_of_vertical_benchmarks(self):
        """Same scores in defense_tech vs consumer must give the same Berkus value."""
        scores = {"idea": 0.8, "management": 0.8, "prototype": 0.6, "relationships": 0.5, "rollout": 0.3}
        results = []
        for vertical in ["defense_tech", "consumer"]:
            inp = _make_input(
                **{"fundraise.stage": "pre_seed", "fundraise.vertical": vertical},
                berkus_scores=scores,
            )
            vdata = _get_vertical_data(inp.fundraise.vertical, inp.fundraise.stage)
            results.append(_run_berkus(inp, vdata).indicated_value)
        assert results[0] == pytest.approx(results[1])

    def test_regional_premium_scales_the_cap(self):
        scores = {"idea": 1.0, "management": 1.0, "prototype": 1.0, "relationships": 1.0, "rollout": 1.0}
        vals = {}
        for geo in ["bay_area", "other_us"]:
            inp = _make_input(
                **{"fundraise.stage": "pre_seed", "fundraise.geography": geo},
                berkus_scores=scores,
            )
            vdata = _get_vertical_data(inp.fundraise.vertical, inp.fundraise.stage)
            result = _run_berkus(inp, vdata)
            vals[geo] = result.indicated_value
            assert result.indicated_value == pytest.approx(
                3.5 * result.inputs_used["regional_premium"], abs=0.05
            )
        assert vals["bay_area"] > vals["other_us"]


class TestS7VerdictSemantics:
    """S-7: percentile labels must match the actual thresholds."""

    def test_p25_p50_label_not_bottom_quartile(self, seed_b2b_saas):
        from app.engine.startup_engine import _build_scorecard
        vdata = _get_vertical_data(StartupVertical.B2B_SAAS, StartupStage.SEED)
        # blended between P25 (9.0) and P50 (16.0)
        flags = _build_scorecard(seed_b2b_saas, 12.0, vdata)
        vs_flag = next(f for f in flags if f.metric == "Valuation vs. Benchmark")
        assert "Bottom quartile" not in vs_flag.benchmark
        assert "Below median" in vs_flag.benchmark


class TestS8RuleOf40:
    """S-8: Rule of 40 uses compounded growth + burn-based margin, graded by bands."""

    def test_compound_growth_and_burn_margin(self):
        inp = _make_input(**{
            "traction.has_revenue": True,
            "traction.annual_recurring_revenue": 1.2,
            "traction.mom_growth_rate": 0.05,
            "traction.monthly_burn_rate": 0.1,
        })
        vdata = _get_vertical_data(inp.fundraise.vertical, inp.fundraise.stage)
        result = _run_arr_multiple(inp, vdata)
        expected_growth = ((1.05 ** 12) - 1) * 100      # ≈ 79.6%
        expected_margin = -(0.1 * 12) / 1.2 * 100        # = -100%
        assert result.inputs_used["rule_of_40_approx"] == pytest.approx(
            expected_growth + expected_margin, abs=0.5
        )
        assert result.inputs_used["rule_of_40_band"]  # graded against JSON bands

    def test_zero_burn_margin_is_breakeven(self):
        inp = _make_input(**{
            "traction.has_revenue": True,
            "traction.annual_recurring_revenue": 1.0,
            "traction.mom_growth_rate": 0.10,
            "traction.monthly_burn_rate": 0.0,
        })
        vdata = _get_vertical_data(inp.fundraise.vertical, inp.fundraise.stage)
        result = _run_arr_multiple(inp, vdata)
        expected_growth = ((1.10 ** 12) - 1) * 100
        assert result.inputs_used["rule_of_40_approx"] == pytest.approx(expected_growth, abs=0.5)


class TestS10VerticalDilutionPath:
    """S-10: projected rounds use the vertical's round sizes, not hardcoded $3M/$10M."""

    def test_defense_tech_series_a_uses_vertical_round_size(self):
        inp = _make_input(**{
            "fundraise.vertical": "defense_tech",
            "fundraise.raise_amount": 6.0,
        })
        out = run_startup_valuation(inp)
        series_a = next(s for s in out.dilution_scenarios if "Series A" in s.round_label)
        # defense_tech series_a round_size_median = 25.0 (not the old hardcoded 10.0)
        assert series_a.raise_amount == pytest.approx(25.0)

    def test_ai_infra_pre_seed_projects_vertical_seed_round(self):
        inp = _make_input(**{
            "fundraise.stage": "pre_seed",
            "fundraise.vertical": "ai_ml_infrastructure",
            "fundraise.raise_amount": 0.75,
        })
        out = run_startup_valuation(inp)
        seed = next(s for s in out.dilution_scenarios if "Seed" in s.round_label and "projected" in s.round_label)
        # ai_ml_infrastructure seed round_size_median = 5.0 (not hardcoded 3.0)
        assert seed.raise_amount == pytest.approx(5.0)


class TestS11BenchmarkConsumption:
    """S-11: series_a P95 read; SAFE cap anchored to vertical safe_cap_median."""

    def test_series_a_benchmark_p95_populated(self):
        inp = _make_input(**{
            "fundraise.stage": "series_a",
            "traction.has_revenue": True,
            "traction.annual_recurring_revenue": 3.0,
            "traction.mom_growth_rate": 0.12,
            "fundraise.raise_amount": 10.0,
        })
        out = run_startup_valuation(inp)
        assert out.benchmark_p95 > 0

    def test_pre_seed_safe_cap_anchored_to_vertical_median(self):
        inp = _make_input(**{
            "fundraise.stage": "pre_seed",
            "fundraise.raise_amount": 0.6,
        })
        out = run_startup_valuation(inp)
        vdata = _get_vertical_data(inp.fundraise.vertical, inp.fundraise.stage)
        cap_median = vdata["safe_cap_median"]
        assert out.recommended_safe_cap >= cap_median
        assert out.recommended_safe_cap == pytest.approx(
            max(cap_median, out.blended_valuation), abs=0.1
        )


class TestS12UnknownRunwayNeutral:
    """S-12: burn==0 AND cash==0 is unknown data → neutral scores + warning."""

    def test_zero_burn_zero_cash_warns_and_scores_neutral(self):
        inp = _make_input(**{"traction.monthly_burn_rate": 0.0, "traction.cash_on_hand": 0.0})
        out = run_startup_valuation(inp)
        assert any("runway" in w.lower() or "burn" in w.lower() for w in out.warnings)
        scorecard = next(m for m in out.method_results if m.method_name == "scorecard")
        assert scorecard.inputs_used["scores"]["additional_financing_needed"] == pytest.approx(1.0)
        rfs = next(m for m in out.method_results if m.method_name == "risk_factor_summation")
        assert rfs.inputs_used["scores"]["Funding / Capital Raising"] == 0

    def test_zero_burn_with_cash_still_scores_healthy(self):
        inp = _make_input(**{"traction.monthly_burn_rate": 0.0, "traction.cash_on_hand": 2.0})
        out = run_startup_valuation(inp)
        scorecard = next(m for m in out.method_results if m.method_name == "scorecard")
        assert scorecard.inputs_used["scores"]["additional_financing_needed"] == pytest.approx(1.2)

    def test_no_geography_double_count_in_other_factors(self):
        bay = _make_input(**{"fundraise.geography": "bay_area"})
        other = _make_input(**{"fundraise.geography": "other_us"})
        vdata = _get_vertical_data(StartupVertical.B2B_SAAS, StartupStage.SEED)
        bay_result = _run_scorecard(bay, vdata)
        other_result = _run_scorecard(other, vdata)
        assert bay_result.inputs_used["scores"]["other_factors"] == other_result.inputs_used["scores"]["other_factors"]


class TestS16DownRoundWarningStage:
    """S-16: down-round warning notes the proxy when no stage-specific rate exists."""

    def test_pre_seed_down_round_warning_notes_proxy(self):
        # Build a pre-seed valuation forced above P75 via a strong profile
        inp = _make_input(
            **{
                "fundraise.stage": "pre_seed",
                "fundraise.geography": "bay_area",
                "fundraise.raise_amount": 0.75,
                "team.prior_exits": 2,
                "team.repeat_founder": True,
                "team.tier1_background": True,
                "market.tam_usd_billions": 60.0,
                "market.competitive_moat": "high",
            },
            scorecard_scores={k: 1.5 for k in [
                "management_team", "market_size", "product_technology",
                "competitive_environment", "marketing_sales_channels",
                "additional_financing_needed", "other_factors",
            ]},
        )
        out = run_startup_valuation(inp)
        down_warnings = [w for w in out.warnings if "down round" in w.lower()]
        if out.blended_valuation > out.benchmark_p75:
            assert down_warnings
            # pre_seed has no down_round_pct in market_wide_medians → proxy note
            assert any("proxy" in w for w in down_warnings)

    def test_seed_down_round_warning_has_no_proxy_note(self):
        inp = _make_input(
            **{"fundraise.geography": "bay_area"},
            scorecard_scores={k: 1.5 for k in [
                "management_team", "market_size", "product_technology",
                "competitive_environment", "marketing_sales_channels",
                "additional_financing_needed", "other_factors",
            ]},
        )
        out = run_startup_valuation(inp)
        down_warnings = [w for w in out.warnings if "down round" in w.lower()]
        if out.blended_valuation > out.benchmark_p75:
            assert down_warnings
            assert all("proxy" not in w for w in down_warnings)
            assert any("12%" in w for w in down_warnings)  # seed down_round_pct = 0.12


class TestS17CompetitiveMoatCoercion:
    """S-17: competitive_moat coerces bad values instead of raising."""

    def test_uppercase_coerced(self):
        m = MarketProfile(tam_usd_billions=5.0, sam_usd_millions=200.0, competitive_moat="HIGH")
        assert m.competitive_moat == "high"

    def test_unknown_value_defaults_to_medium(self):
        m = MarketProfile(tam_usd_billions=5.0, sam_usd_millions=200.0, competitive_moat="galactic")
        assert m.competitive_moat == "medium"

    def test_non_string_defaults_to_medium(self):
        m = MarketProfile(tam_usd_billions=5.0, sam_usd_millions=200.0, competitive_moat=3)
        assert m.competitive_moat == "medium"


class TestS18RevenueConsistency:
    """S-18: has_revenue gates the ARR method; MRR/ARR conflicts warn."""

    def test_arr_without_has_revenue_flag_gates_method(self):
        inp = _make_input(**{
            "traction.has_revenue": False,
            "traction.annual_recurring_revenue": 1.0,
        })
        out = run_startup_valuation(inp)
        arr_method = next(m for m in out.method_results if m.method_name == "arr_multiple")
        assert arr_method.applicable is False
        assert any("has_revenue" in w for w in out.warnings)

    def test_mrr_arr_conflict_warns(self):
        inp = _make_input(**{
            "traction.has_revenue": True,
            "traction.monthly_recurring_revenue": 0.1,   # implies $1.2M ARR
            "traction.annual_recurring_revenue": 0.5,    # conflicts by >20%
            "traction.mom_growth_rate": 0.10,
        })
        out = run_startup_valuation(inp)
        assert any("MRR" in w and "ARR" in w for w in out.warnings)

    def test_consistent_mrr_arr_no_warning(self):
        inp = _make_input(**{
            "traction.has_revenue": True,
            "traction.monthly_recurring_revenue": 0.1,
            "traction.annual_recurring_revenue": 1.2,
            "traction.mom_growth_rate": 0.10,
        })
        out = run_startup_valuation(inp)
        assert not any("differs from reported ARR" in w for w in out.warnings)


class TestRangeInvariant:
    """Global invariant: valuation_range_low <= blended <= valuation_range_high."""

    @pytest.mark.parametrize("stage", ["pre_seed", "seed", "series_a"])
    @pytest.mark.parametrize("arr", [0.0, 0.05, 1.0, 5.0])
    def test_blended_always_within_range(self, stage, arr):
        inp = _make_input(**{
            "fundraise.stage": stage,
            "traction.has_revenue": arr > 0,
            "traction.annual_recurring_revenue": arr,
            "traction.mom_growth_rate": 0.10 if arr > 0 else 0.0,
        })
        out = run_startup_valuation(inp)
        assert out.valuation_range_low <= out.blended_valuation <= out.valuation_range_high
