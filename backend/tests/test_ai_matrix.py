"""
Tests for the inputs-up AI-native parameter calibration matrix.

The AI-native toggle no longer applies a post-blend scalar premium. Instead
it shifts the PARAMETERS of the individual valuation methods (scorecard
weights, Berkus per-dimension caps, RFS step values, ARR multiple uplift)
BEFORE blending. Any premium is emergent.

All monetary values in USD millions; percentages as decimals.
"""
import json
import os

import pytest

from app.engine.ai_modifier import AIParameterSet, get_ai_parameters
from app.engine.startup_engine import (
    run_startup_valuation,
    _get_vertical_data,
)
from app.engine.startup_models import (
    StartupInput,
    StartupStage,
    StartupVertical,
    InstrumentType,
    ProductStage,
    TeamProfile,
    TractionMetrics,
    ProductProfile,
    MarketProfile,
    FundraisingProfile,
)

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "app", "data")
_TOGGLE_PATH = os.path.join(_DATA_DIR, "ai_toggle_config.json")
_BENCHMARKS_PATH = os.path.join(_DATA_DIR, "startup_valuation_benchmarks.json")

FROZEN_ON = ["ai_ml_infrastructure", "ai_enabled_saas", "defense_tech"]


def _mk(
    vertical: str = "b2b_saas",
    stage: str = "seed",
    score: float = 0.0,
    is_ai_native: bool = False,
    arr: float = 1.0,
) -> StartupInput:
    """Reference company: seed SaaS with meaningful ARR and moderate signals."""
    has_revenue = arr > 0
    return StartupInput(
        company_name="MatrixRef",
        team=TeamProfile(domain_experts=True, technical_cofounder=True),
        traction=TractionMetrics(
            has_revenue=has_revenue,
            annual_recurring_revenue=arr,
            monthly_recurring_revenue=arr / 12.0 if arr > 0 else 0.0,
            mom_growth_rate=0.10 if has_revenue else 0.0,
            net_revenue_retention=1.10,
            gross_margin=0.75,
            monthly_burn_rate=0.1,
            cash_on_hand=2.0,
            paying_customer_count=10 if has_revenue else 0,
        ),
        product=ProductProfile(stage=ProductStage.PAYING_CUSTOMERS if has_revenue else ProductStage.BETA),
        market=MarketProfile(tam_usd_billions=10.0, sam_usd_millions=500.0),
        fundraise=FundraisingProfile(
            stage=StartupStage(stage),
            vertical=StartupVertical(vertical),
            raise_amount=3.0,
            instrument=InstrumentType.SAFE,
            is_ai_native=is_ai_native,
            ai_native_score=score,
        ),
    )


# ---------------------------------------------------------------------------
# Data integrity
# ---------------------------------------------------------------------------

class TestParameterMatrixData:
    """The calibration matrix must not embed a hidden premium."""

    @pytest.fixture(scope="class")
    def config(self) -> dict:
        with open(_TOGGLE_PATH) as f:
            return json.load(f)

    def test_config_loads_with_parameter_matrix(self, config):
        assert "parameter_matrix" in config
        assert "standard" in config["parameter_matrix"]
        assert "ai_native" in config["parameter_matrix"]

    def test_ai_native_scorecard_weights_sum_to_one(self, config):
        weights = config["parameter_matrix"]["ai_native"]["scorecard_weights"]
        assert sum(weights.values()) == pytest.approx(1.0, abs=1e-9)
        assert len(weights) == 7

    def test_berkus_apportionment_totals_3_5(self, config):
        caps = config["parameter_matrix"]["ai_native"]["berkus_cap_apportionment"]
        assert sum(caps.values()) == pytest.approx(3.5, abs=1e-9)
        assert len(caps) == 5

    def test_rfs_overrides_double_three_volatility_categories(self, config):
        overrides = config["parameter_matrix"]["ai_native"]["rfs_step_value_overrides"]
        assert set(overrides) == {"Technology", "Competition", "Litigation"}
        assert all(v == pytest.approx(0.50) for v in overrides.values())

    def test_standard_section_is_neutral(self, config):
        std = config["parameter_matrix"]["standard"]
        assert std["scorecard_weights"] is None
        assert std["berkus_cap_apportionment"] is None
        assert std["rfs_step_value_overrides"] == {}
        assert std["arr_multiple_uplift"] == 0.0

    def test_frozen_on_verticals_listed(self, config):
        assert set(FROZEN_ON) <= set(config["frozen_on"])


# ---------------------------------------------------------------------------
# get_ai_parameters unit behavior
# ---------------------------------------------------------------------------

class TestGetAIParameters:
    def test_toggle_off_returns_standard(self):
        p = get_ai_parameters(False, 1.0, "b2b_saas")
        assert p.applied is False
        assert p.scorecard_weights is None
        assert p.berkus_caps is None
        assert p.rfs_step_values == {}
        assert p.arr_multiple_uplift == 0.0

    def test_zero_score_returns_standard(self):
        p = get_ai_parameters(True, 0.0, "b2b_saas")
        assert p.applied is False
        assert p.arr_multiple_uplift == 0.0

    def test_frozen_on_returns_standard_with_context(self):
        for v in FROZEN_ON:
            p = get_ai_parameters(True, 1.0, v)
            assert p.applied is False
            assert "already reflected in benchmarks" in p.context

    def test_score_one_matches_matrix_endpoints(self):
        p = get_ai_parameters(True, 1.0, "b2b_saas")
        assert p.applied is True
        assert p.scorecard_weights["product_technology"] == pytest.approx(0.25)
        assert p.scorecard_weights["management_team"] == pytest.approx(0.25)
        assert sum(p.scorecard_weights.values()) == pytest.approx(1.0, abs=1e-9)
        assert p.berkus_caps["prototype"] == pytest.approx(1.05)
        assert p.berkus_caps["idea"] == pytest.approx(0.55)
        assert sum(p.berkus_caps.values()) == pytest.approx(3.5, abs=1e-9)
        assert p.rfs_step_values["Technology"] == pytest.approx(0.50)
        # b2b_saas vertical premium is 0.8 → uplift 0.8 at score 1.0
        assert p.arr_multiple_uplift == pytest.approx(0.8)

    def test_half_score_blends_linearly(self):
        p = get_ai_parameters(True, 0.5, "b2b_saas")
        # weights: w = std + (ai − std) × 0.5, re-normalized (sum already 1.0)
        assert p.scorecard_weights["product_technology"] == pytest.approx((0.15 + 0.25) / 2)
        assert sum(p.scorecard_weights.values()) == pytest.approx(1.0, abs=1e-9)
        assert p.berkus_caps["prototype"] == pytest.approx((0.7 + 1.05) / 2)
        assert sum(p.berkus_caps.values()) == pytest.approx(3.5, abs=1e-9)
        # RFS step: 0.25 + (0.50 − 0.25) × 0.5 = 0.375
        assert p.rfs_step_values["Litigation"] == pytest.approx(0.375)
        assert p.arr_multiple_uplift == pytest.approx(0.4)

    def test_never_raises_on_garbage(self):
        p = get_ai_parameters(True, 1.0, "not_a_vertical")
        assert isinstance(p, AIParameterSet)
        assert p.arr_multiple_uplift == 0.0  # unknown vertical → no uplift


# ---------------------------------------------------------------------------
# Emergent premium — identical inputs, toggle flipped
# ---------------------------------------------------------------------------

class TestEmergentPremium:
    @pytest.mark.parametrize("vertical", ["b2b_saas", "healthtech"])
    def test_score_one_premium_within_bounds(self, vertical):
        """At score 1.0 with meaningful ARR the emergent premium is (0%, 60%]."""
        base = run_startup_valuation(_mk(vertical=vertical))
        ai = run_startup_valuation(_mk(vertical=vertical, is_ai_native=True, score=1.0))
        assert ai.ai_modifier_applied is True
        assert ai.blended_before_ai == pytest.approx(base.blended_valuation, rel=1e-6)
        premium = ai.ai_premium_multiplier
        assert premium is not None
        assert 0.0 < premium <= 0.60
        assert ai.blended_valuation == pytest.approx(
            ai.blended_before_ai * (1 + premium), rel=1e-3
        )

    @pytest.mark.parametrize("vertical", ["b2b_saas", "healthtech"])
    def test_half_score_premium_strictly_between(self, vertical):
        full = run_startup_valuation(_mk(vertical=vertical, is_ai_native=True, score=1.0))
        half = run_startup_valuation(_mk(vertical=vertical, is_ai_native=True, score=0.5))
        assert 0.0 < half.ai_premium_multiplier < full.ai_premium_multiplier

    def test_premium_monotonic_in_score(self):
        prev = None
        for score in [0.0, 0.25, 0.5, 0.75, 1.0]:
            out = run_startup_valuation(
                _mk(is_ai_native=score > 0, score=score)
            )
            if prev is not None:
                assert out.blended_valuation > prev, (
                    f"Blended not strictly increasing at score {score}"
                )
            prev = out.blended_valuation

    def test_context_describes_parameter_calibration(self):
        out = run_startup_valuation(_mk(is_ai_native=True, score=1.0))
        assert out.ai_premium_context is not None
        assert "parameter-level calibration" in out.ai_premium_context


# ---------------------------------------------------------------------------
# Frozen verticals — toggle changes nothing
# ---------------------------------------------------------------------------

class TestFrozenVerticals:
    @pytest.mark.parametrize("vertical", FROZEN_ON)
    def test_toggle_changes_nothing(self, vertical):
        off = run_startup_valuation(_mk(vertical=vertical))
        on = run_startup_valuation(_mk(vertical=vertical, is_ai_native=True, score=1.0))
        assert on.blended_valuation == pytest.approx(off.blended_valuation, abs=1e-6)
        assert on.valuation_range_low == pytest.approx(off.valuation_range_low, abs=1e-6)
        assert on.valuation_range_high == pytest.approx(off.valuation_range_high, abs=1e-6)
        assert on.ai_modifier_applied is False
        assert on.ai_premium_multiplier is None
        assert on.blended_before_ai is None

    @pytest.mark.parametrize("vertical", FROZEN_ON)
    def test_context_says_benchmarks_already_price_ai(self, vertical):
        on = run_startup_valuation(_mk(vertical=vertical, is_ai_native=True, score=1.0))
        assert "already reflected in benchmarks" in (on.ai_premium_context or "")


# ---------------------------------------------------------------------------
# No post-blend scalar — blended is exactly the weighted method average
# ---------------------------------------------------------------------------

def _expected_blend(out, inp: StartupInput) -> float:
    """Recompute the weighted method average independently of the engine."""
    by_name = {m.method_name: m for m in out.method_results}
    applicable = [m for m in out.method_results if m.applicable and m.indicated_value is not None]
    assert applicable, "test requires at least one applicable method"
    arr = inp.traction.annual_recurring_revenue or (inp.traction.monthly_recurring_revenue * 12)
    arr_m = by_name["arr_multiple"]
    pre_values = [
        by_name[n].indicated_value
        for n in ("berkus", "scorecard", "risk_factor_summation")
        if by_name[n].applicable and by_name[n].indicated_value is not None
    ]
    if arr > 0 and arr_m.applicable and pre_values:
        vdata = _get_vertical_data(inp.fundraise.vertical, inp.fundraise.stage)
        ramp_denominator = max(float(vdata.get("arr_required_min") or 1.0), 1.0)
        ramp = min(1.0, arr / ramp_denominator)
        arr_weight = 0.65 * ramp
        pre_avg = sum(pre_values) / len(pre_values)
        blended = arr_m.indicated_value * arr_weight + pre_avg * (1 - arr_weight)
        if ramp < 1.0 and blended < pre_avg:
            blended = pre_avg
        return blended
    if arr > 0 and arr_m.applicable:
        return arr_m.indicated_value
    return sum(pre_values) / len(pre_values)


class TestNoPostBlendScalar:
    @pytest.mark.parametrize("is_ai_native,score", [(False, 0.0), (True, 1.0)])
    def test_arr_case_blended_is_weighted_average(self, is_ai_native, score):
        inp = _mk(is_ai_native=is_ai_native, score=score)
        out = run_startup_valuation(inp)
        assert out.blended_valuation == pytest.approx(_expected_blend(out, inp), abs=0.02)

    @pytest.mark.parametrize("is_ai_native,score", [(False, 0.0), (True, 1.0)])
    def test_pre_revenue_blended_is_simple_average(self, is_ai_native, score):
        inp = _mk(is_ai_native=is_ai_native, score=score, arr=0.0)
        out = run_startup_valuation(inp)
        assert out.blended_valuation == pytest.approx(_expected_blend(out, inp), abs=0.02)

    @pytest.mark.parametrize("is_ai_native,score", [(False, 0.0), (True, 1.0)])
    def test_blended_within_method_hull(self, is_ai_native, score):
        """A weighted average can never leave [min, max] of the method values."""
        out = run_startup_valuation(_mk(is_ai_native=is_ai_native, score=score))
        values = [m.indicated_value for m in out.method_results
                  if m.applicable and m.indicated_value is not None]
        assert min(values) - 0.02 <= out.blended_valuation <= max(values) + 0.02


# ---------------------------------------------------------------------------
# ARR multiple uplift cap
# ---------------------------------------------------------------------------

class TestARRMultipleCap:
    def _ai_enabled_saas_p50(self, stage: str) -> float:
        with open(_BENCHMARKS_PATH) as f:
            benchmarks = json.load(f)
        return benchmarks["verticals"]["ai_enabled_saas"][stage]["arr_multiple_p50"]

    def test_b2b_saas_never_exceeds_ai_enabled_saas_p50(self):
        cap = self._ai_enabled_saas_p50("seed")
        out = run_startup_valuation(_mk(vertical="b2b_saas", is_ai_native=True, score=1.0))
        arr_m = next(m for m in out.method_results if m.method_name == "arr_multiple")
        assert arr_m.inputs_used["effective_base_multiple"] <= cap + 1e-9

    def test_cap_binds_for_developer_tools_with_note(self):
        """developer_tools seed P50 (14x) × 1.5 uplift = 21x > ai_enabled_saas 18x."""
        cap = self._ai_enabled_saas_p50("seed")
        out = run_startup_valuation(_mk(vertical="developer_tools", is_ai_native=True, score=1.0))
        arr_m = next(m for m in out.method_results if m.method_name == "arr_multiple")
        assert arr_m.inputs_used["uplift_cap_bound"] is True
        assert arr_m.inputs_used["effective_base_multiple"] == pytest.approx(cap)
        assert any("capped" in n for n in out.computation_notes)

    def test_uplift_scales_p25_p75_bounds_consistently(self):
        """Range bounds scale with the same effective factor (S-5 bracket fix)."""
        base = run_startup_valuation(_mk(vertical="b2b_saas"))
        ai = run_startup_valuation(_mk(vertical="b2b_saas", is_ai_native=True, score=1.0))
        base_m = next(m for m in base.method_results if m.method_name == "arr_multiple")
        ai_m = next(m for m in ai.method_results if m.method_name == "arr_multiple")
        factor = ai_m.inputs_used["uplift_factor"]
        assert factor > 1.0
        assert ai_m.value_low == pytest.approx(base_m.value_low * factor, rel=1e-2)
        assert ai_m.value_high == pytest.approx(base_m.value_high * factor, rel=1e-2)
        # Indicated value stays inside its own bounds
        assert ai_m.value_low <= ai_m.indicated_value <= ai_m.value_high


# ---------------------------------------------------------------------------
# Berkus re-apportionment preserves the total cap
# ---------------------------------------------------------------------------

class TestBerkusReapportionment:
    def test_total_cap_preserved_at_full_score(self):
        inp = _mk(vertical="b2b_saas", stage="pre_seed", is_ai_native=True, score=1.0, arr=0.0)
        out = run_startup_valuation(inp)
        berkus = next(m for m in out.method_results if m.method_name == "berkus")
        caps = berkus.inputs_used["per_dimension_caps"]
        regional = berkus.inputs_used["regional_premium"]
        assert berkus.inputs_used["ai_reapportioned"] is True
        assert sum(caps.values()) == pytest.approx(3.5 * regional, abs=0.05)
        # Re-apportioned toward prototype/relationships, away from idea/rollout
        assert caps["prototype"] > caps["idea"]
        assert caps["relationships"] > caps["rollout"]


# ---------------------------------------------------------------------------
# Range invariant
# ---------------------------------------------------------------------------

class TestRangeInvariant:
    @pytest.mark.parametrize("vertical", ["b2b_saas", "healthtech", "developer_tools", "defense_tech"])
    @pytest.mark.parametrize("is_ai_native,score", [(False, 0.0), (True, 0.5), (True, 1.0)])
    def test_blended_within_range(self, vertical, is_ai_native, score):
        out = run_startup_valuation(_mk(vertical=vertical, is_ai_native=is_ai_native, score=score))
        assert out.valuation_range_low <= out.blended_valuation <= out.valuation_range_high
