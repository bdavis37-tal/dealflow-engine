"""
Tests for the round timing signal computation.

Covers:
- Unit tests for _compute_round_timing across key scenarios
- Property-based tests using hypothesis for invariant verification
"""
from __future__ import annotations

import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from app.engine.startup_engine import _compute_round_timing, _next_stage_for, run_startup_valuation
from app.engine.startup_models import (
    StartupInput,
    StartupStage,
    StartupVertical,
    FundraisingProfile,
    TractionMetrics,
    TeamProfile,
    ProductProfile,
    MarketProfile,
    RaiseSignal,
    InstrumentType,
    Geography,
    ProductStage,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_input(
    stage: StartupStage = StartupStage.SEED,
    vertical: StartupVertical = StartupVertical.B2B_SAAS,
    cash_on_hand: float = 0.5,
    monthly_burn_rate: float = 0.05,
    arr: float = 0.0,
    mrr: float = 0.0,
    mom_growth: float = 0.0,
    nrr: float = 1.0,
    gross_margin: float = 0.70,
    paying_customers: int = 0,
    has_lois: bool = False,
    logo_customers: int = 0,
    product_stage: ProductStage = ProductStage.MVP,
    technical_cofounder: bool = True,
    tam: float = 5.0,
) -> StartupInput:
    return StartupInput(
        company_name="TestCo",
        team=TeamProfile(technical_cofounder=technical_cofounder),
        traction=TractionMetrics(
            has_revenue=arr > 0 or mrr > 0,
            annual_recurring_revenue=arr,
            monthly_recurring_revenue=mrr,
            mom_growth_rate=mom_growth,
            net_revenue_retention=nrr,
            gross_margin=gross_margin,
            monthly_burn_rate=monthly_burn_rate,
            cash_on_hand=cash_on_hand,
            paying_customer_count=paying_customers,
            logo_customer_count=logo_customers,
            has_lois=has_lois,
        ),
        product=ProductProfile(stage=product_stage),
        market=MarketProfile(
            tam_usd_billions=tam,
            sam_usd_millions=tam * 100,
        ),
        fundraise=FundraisingProfile(
            stage=stage,
            vertical=vertical,
            raise_amount=1.0,
            instrument=InstrumentType.SAFE,
        ),
    )


# ---------------------------------------------------------------------------
# Unit tests: _next_stage_for
# ---------------------------------------------------------------------------

class TestNextStageFor:
    def test_pre_seed_to_seed(self):
        assert _next_stage_for(StartupStage.PRE_SEED) == StartupStage.SEED

    def test_seed_to_series_a(self):
        assert _next_stage_for(StartupStage.SEED) == StartupStage.SERIES_A

    def test_series_a_is_terminal(self):
        assert _next_stage_for(StartupStage.SERIES_A) is None


# ---------------------------------------------------------------------------
# Unit tests: _compute_round_timing
# ---------------------------------------------------------------------------

class TestComputeRoundTiming:

    def test_zero_burn_rate(self):
        """Zero burn → runway_months=0 in output, no crash, signal is valid."""
        inp = make_input(cash_on_hand=0.0, monthly_burn_rate=0.0)
        result = _compute_round_timing(inp, {})
        assert result.runway_months == 0.0
        assert result.signal in (RaiseSignal.RAISE_NOW, RaiseSignal.RAISE_IN_MONTHS, RaiseSignal.FOCUS_MILESTONES)
        # No data warning should be present
        assert any("burn" in w.lower() or "runway" in w.lower() for w in result.warnings)

    def test_series_a_terminal_stage(self):
        """Series A → always focus_milestones (no next stage modeled)."""
        inp = make_input(stage=StartupStage.SERIES_A, cash_on_hand=2.0, monthly_burn_rate=0.1)
        result = _compute_round_timing(inp, {})
        assert result.signal == RaiseSignal.FOCUS_MILESTONES
        assert result.months_to_next_round == 0.0

    def test_seed_14_months_runway_raise_now(self):
        """
        Seed stage: months_to_next=24, fundraise_process=6 → window opens at 18 months.
        14 months runway < 18 months window → raise_now.
        """
        inp = make_input(
            stage=StartupStage.SEED,
            cash_on_hand=0.7,   # 0.7 / 0.05 = 14 months
            monthly_burn_rate=0.05,
        )
        result = _compute_round_timing(inp, {})
        assert result.runway_months == pytest.approx(14.0, abs=0.1)
        assert result.signal == RaiseSignal.RAISE_NOW

    def test_seed_30_months_runway_raise_in_months(self):
        """
        Seed stage: window opens at 18 months.
        30 months runway → 30 - 18 = 12 months until window → raise_in_months.
        """
        inp = make_input(
            stage=StartupStage.SEED,
            cash_on_hand=1.5,   # 1.5 / 0.05 = 30 months
            monthly_burn_rate=0.05,
        )
        result = _compute_round_timing(inp, {})
        assert result.runway_months == pytest.approx(30.0, abs=0.1)
        assert result.signal == RaiseSignal.RAISE_IN_MONTHS
        assert result.raise_in_months is not None
        assert result.raise_in_months == pytest.approx(12.0, abs=0.5)

    def test_seed_40_months_runway_focus_milestones(self):
        """
        Seed stage: window opens at 18 months.
        40 months runway → 40 - 18 = 22 months > 12 → focus_milestones.
        """
        inp = make_input(
            stage=StartupStage.SEED,
            cash_on_hand=2.0,   # 2.0 / 0.05 = 40 months
            monthly_burn_rate=0.05,
        )
        result = _compute_round_timing(inp, {})
        assert result.runway_months == pytest.approx(40.0, abs=0.1)
        assert result.signal == RaiseSignal.FOCUS_MILESTONES
        assert result.raise_in_months is None

    def test_pre_seed_24_months_runway(self):
        """
        Pre-seed: months_to_next=18, window opens at 12 months.
        24 months runway → 24 - 12 = 12 months → boundary of raise_in_months.
        """
        inp = make_input(
            stage=StartupStage.PRE_SEED,
            cash_on_hand=1.2,   # 1.2 / 0.05 = 24 months
            monthly_burn_rate=0.05,
        )
        result = _compute_round_timing(inp, {})
        assert result.runway_months == pytest.approx(24.0, abs=0.1)
        # 24 - 12 = 12 months → exactly at boundary; raise_in_months (< 12 is focus)
        assert result.signal in (RaiseSignal.RAISE_IN_MONTHS, RaiseSignal.FOCUS_MILESTONES)

    def test_biotech_no_arr_fields(self):
        """Biotech with zero ARR fields should not raise exceptions."""
        inp = make_input(
            stage=StartupStage.SEED,
            vertical=StartupVertical.BIOTECH_PHARMA,
            arr=0.0,
            mrr=0.0,
            cash_on_hand=1.0,
            monthly_burn_rate=0.1,
        )
        result = _compute_round_timing(inp, {})
        assert result is not None
        assert result.signal in (RaiseSignal.RAISE_NOW, RaiseSignal.RAISE_IN_MONTHS, RaiseSignal.FOCUS_MILESTONES)

    def test_critical_runway_warning(self):
        """< 6 months runway should produce a critical warning."""
        inp = make_input(
            stage=StartupStage.SEED,
            cash_on_hand=0.2,   # 0.2 / 0.05 = 4 months
            monthly_burn_rate=0.05,
        )
        result = _compute_round_timing(inp, {})
        assert result.signal == RaiseSignal.RAISE_NOW
        assert any("critical" in w.lower() for w in result.warnings)

    def test_milestone_gaps_are_strings(self):
        """milestone_gaps must always be a list of strings."""
        inp = make_input(stage=StartupStage.SEED)
        result = _compute_round_timing(inp, {})
        assert isinstance(result.milestone_gaps, list)
        for gap in result.milestone_gaps:
            assert isinstance(gap, str)

    def test_milestone_counts_consistent(self):
        """met_count + len(gaps) == total_count."""
        inp = make_input(stage=StartupStage.SEED)
        result = _compute_round_timing(inp, {})
        assert result.milestone_met_count + len(result.milestone_gaps) == result.milestone_total_count

    def test_all_milestones_met_no_gaps(self):
        """A well-funded seed startup meeting all milestones should have no gaps."""
        inp = make_input(
            stage=StartupStage.SEED,
            arr=0.2,
            mom_growth=0.15,
            nrr=1.05,
            paying_customers=5,
            gross_margin=0.75,
            cash_on_hand=2.0,
            monthly_burn_rate=0.05,
        )
        result = _compute_round_timing(inp, {})
        assert result.milestone_gaps == []
        assert result.milestone_met_count == result.milestone_total_count


# ---------------------------------------------------------------------------
# All 13 verticals × 3 stages — no exceptions
# ---------------------------------------------------------------------------

ALL_VERTICALS = list(StartupVertical)
ALL_STAGES = list(StartupStage)


@pytest.mark.parametrize("vertical", ALL_VERTICALS)
@pytest.mark.parametrize("stage", ALL_STAGES)
def test_no_exception_all_verticals_stages(vertical: StartupVertical, stage: StartupStage):
    """_compute_round_timing must not raise for any valid vertical × stage combination."""
    inp = make_input(stage=stage, vertical=vertical, cash_on_hand=1.0, monthly_burn_rate=0.05)
    result = _compute_round_timing(inp, {})
    assert result is not None
    assert result.signal in (RaiseSignal.RAISE_NOW, RaiseSignal.RAISE_IN_MONTHS, RaiseSignal.FOCUS_MILESTONES)


# ---------------------------------------------------------------------------
# Property-based tests
# ---------------------------------------------------------------------------

# Strategy for valid StartupInput
_stage_st = st.sampled_from(list(StartupStage))
_vertical_st = st.sampled_from(list(StartupVertical))
_burn_st = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
_cash_st = st.floats(min_value=0.0, max_value=10.0, allow_nan=False, allow_infinity=False)
_arr_st = st.floats(min_value=0.0, max_value=5.0, allow_nan=False, allow_infinity=False)
_growth_st = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
_nrr_st = st.floats(min_value=0.5, max_value=2.0, allow_nan=False, allow_infinity=False)
_gm_st = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
_customers_st = st.integers(min_value=0, max_value=100)
_tam_st = st.floats(min_value=0.01, max_value=1000.0, allow_nan=False, allow_infinity=False)


@given(
    stage=_stage_st,
    vertical=_vertical_st,
    cash=_cash_st,
    burn=_burn_st,
    arr=_arr_st,
    growth=_growth_st,
    nrr=_nrr_st,
    gm=_gm_st,
    customers=_customers_st,
    tam=_tam_st,
)
@settings(max_examples=200, suppress_health_checks=[HealthCheck.too_slow])
def test_pbt_no_exceptions(
    stage, vertical, cash, burn, arr, growth, nrr, gm, customers, tam
):
    """No valid input combination should raise an exception."""
    inp = make_input(
        stage=stage, vertical=vertical,
        cash_on_hand=cash, monthly_burn_rate=burn,
        arr=arr, mom_growth=growth, nrr=nrr,
        gross_margin=gm, paying_customers=customers, tam=tam,
    )
    result = _compute_round_timing(inp, {})
    assert result is not None


@given(
    cash=st.floats(min_value=0.01, max_value=10.0, allow_nan=False, allow_infinity=False),
    burn=st.floats(min_value=0.001, max_value=1.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=200)
def test_pbt_runway_formula(cash: float, burn: float):
    """When burn > 0, runway_months == cash / burn (within float tolerance)."""
    inp = make_input(cash_on_hand=cash, monthly_burn_rate=burn)
    result = _compute_round_timing(inp, {})
    expected_runway = cash / burn
    assert result.runway_months == pytest.approx(expected_runway, rel=1e-4)


@given(
    stage=_stage_st,
    vertical=_vertical_st,
    cash=_cash_st,
    burn=_burn_st,
)
@settings(max_examples=200, suppress_health_checks=[HealthCheck.too_slow])
def test_pbt_signal_always_valid(stage, vertical, cash, burn):
    """Signal is always one of the three valid enum values."""
    inp = make_input(stage=stage, vertical=vertical, cash_on_hand=cash, monthly_burn_rate=burn)
    result = _compute_round_timing(inp, {})
    assert result.signal in (RaiseSignal.RAISE_NOW, RaiseSignal.RAISE_IN_MONTHS, RaiseSignal.FOCUS_MILESTONES)


@given(
    stage=_stage_st,
    vertical=_vertical_st,
    cash=_cash_st,
    burn=_burn_st,
)
@settings(max_examples=200, suppress_health_checks=[HealthCheck.too_slow])
def test_pbt_milestone_gaps_always_strings(stage, vertical, cash, burn):
    """milestone_gaps is always a list of strings."""
    inp = make_input(stage=stage, vertical=vertical, cash_on_hand=cash, monthly_burn_rate=burn)
    result = _compute_round_timing(inp, {})
    assert isinstance(result.milestone_gaps, list)
    for gap in result.milestone_gaps:
        assert isinstance(gap, str)


@given(
    stage=_stage_st,
    vertical=_vertical_st,
    cash=_cash_st,
    burn=_burn_st,
    arr=_arr_st,
    tam=_tam_st,
)
@settings(max_examples=100, suppress_health_checks=[HealthCheck.too_slow])
def test_pbt_round_timing_always_present_on_full_output(
    stage, vertical, cash, burn, arr, tam
):
    """run_startup_valuation always returns a round_timing field."""
    inp = make_input(
        stage=stage, vertical=vertical,
        cash_on_hand=cash, monthly_burn_rate=burn,
        arr=arr, tam=tam,
    )
    output = run_startup_valuation(inp)
    assert output.round_timing is not None
    assert output.round_timing.signal in (
        RaiseSignal.RAISE_NOW, RaiseSignal.RAISE_IN_MONTHS, RaiseSignal.FOCUS_MILESTONES
    )
