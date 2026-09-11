"""
Startup Valuation Engine

Implements four valuation methods, weighted by applicability:
  1. Berkus Method          — pre-revenue / concept stage
  2. Scorecard Method       — pre-revenue / angel stage (vs. regional comparable)
  3. Risk Factor Summation  — cross-check on Scorecard; 12 risk categories
  4. ARR Multiple           — post-revenue; primary method once ARR exists

The blended output represents a weighted average of applicable methods with
explicit low/high ranges tied to market benchmarks (Carta, PitchBook, Equidam Q3 2025).
"""
from __future__ import annotations
from .benchmark_registry import BenchmarkView, evidence_analysis, resolve, policy

import logging
import os
from typing import Optional

from .ai_modifier import AIParameterSet, get_ai_parameters
from .startup_models import (
    StartupInput,
    StartupValuationOutput,
    StartupStage,
    StartupVertical,
    ValuationMethodResult,
    DilutionScenario,
    SAFEConversionSummary,
    ScorecardFlag,
    ValuationVerdict,
    ValuationSignal,
    InstrumentType,
    ProductStage,
    RaiseSignal,
    RoundTimingSignal,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Load benchmark data once at module level
# ---------------------------------------------------------------------------

_DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "startup_valuation_benchmarks.json")

def _load_benchmarks():
    return BenchmarkView("startup")


_BENCHMARKS = _load_benchmarks()


def _get_vertical_data(vertical: StartupVertical, stage: StartupStage) -> dict:
    """Return the benchmark block for a given vertical × stage."""
    vdata = _BENCHMARKS["verticals"].get(vertical.value, {})
    return vdata.get(stage.value, {})


def _get_regional_premium(geography: str) -> float:
    """Regional adjustment multiplier for the Berkus baseline."""
    return _BENCHMARKS.get("berkus_regional_premiums", {}).get(geography, 1.0)


def _get_vertical_baseline(vdata: dict, stage: StartupStage) -> float:
    """
    Return the vertical-specific valuation baseline for pre-revenue methods.
    Uses the vertical assumption when available, then a same-stage market assumption.
    This ensures defense tech, AI infra, etc. are anchored to their own comps
    rather than the generic $7.7M market median.
    """
    vertical_p50 = vdata.get('valuation_p50')
    if vertical_p50 and vertical_p50 > 0:
        return float(vertical_p50)
    market = _BENCHMARKS['market_wide_medians'].get(stage.value, {})
    median = market.get('valuation_median') or market.get('valuation_pre_money_median')
    if median is None:
        raise ValueError('No compatible stage baseline is configured')
    return float(median)


# ---------------------------------------------------------------------------
# Method 1: Berkus Method
# ---------------------------------------------------------------------------

# 2025-era Berkus ceiling: up to $0.7M per dimension, $3.5M total pre-money.
# Berkus is deliberately NOT benchmark-anchored — it provides an independent
# qualitative signal uncorrelated with the comparable-based methods.
_BERKUS_DIMENSION_CAP = 0.7  # USD millions per dimension
_BERKUS_TOTAL_CAP = _BERKUS_DIMENSION_CAP * 5  # $3.5M


def _run_berkus(
    inp: StartupInput,
    vdata: dict,
    berkus_caps: Optional[dict[str, float]] = None,
) -> ValuationMethodResult:
    """
    Berkus Method: 5 factors × up to $0.7M each = $3.5M max (2025-era Berkus
    ceiling). The regional premium scales the CAP — not a vertical median —
    so the method keeps its accepted ~$3–3.5M ceiling and stays independent
    of the comparable benchmarks used by the other methods.

    `berkus_caps` (AI parameter matrix) re-apportions the $3.5M total across
    the 5 dimensions (keys: idea, management, prototype, relationships,
    rollout) without changing the total — no hidden premium. The regional
    premium still scales each cap.
    """
    regional_premium = _get_regional_premium(inp.fundraise.geography.value)
    # Effective per-dimension caps (pre-regional). Standard = uniform $0.7M.
    caps = {
        d: (berkus_caps or {}).get(d, _BERKUS_DIMENSION_CAP)
        for d in ("idea", "management", "prototype", "relationships", "rollout")
    }
    reapportioned = berkus_caps is not None
    factor_max = _BERKUS_DIMENSION_CAP * regional_premium  # standard max per dimension

    # Dimension scoring (0–1 each; max contribution = 20% × regional_median each)
    if inp.berkus_scores:
        # User provided explicit overrides
        scores = inp.berkus_scores
        s_idea = max(0.0, min(1.0, scores.get("idea", 0.7)))
        s_management = max(0.0, min(1.0, scores.get("management", 0.7)))
        s_prototype = max(0.0, min(1.0, scores.get("prototype", 0.7)))
        s_relationships = max(0.0, min(1.0, scores.get("relationships", 0.5)))
        s_rollout = max(0.0, min(1.0, scores.get("rollout", 0.3)))
    else:
        # Auto-score from input signals
        t = inp.traction
        team = inp.team
        prod = inp.product

        # Dimension 1: Sound Idea (market + uniqueness)
        market_size_score = min(1.0, inp.market.tam_usd_billions / 10.0)
        moat_score = {"low": 0.4, "medium": 0.7, "high": 1.0}.get(inp.market.competitive_moat, 0.7)
        s_idea = (market_size_score * 0.5 + moat_score * 0.5)

        # Dimension 2: Quality of Management
        mgmt_base = 0.5
        if team.prior_exits >= 1: mgmt_base += 0.2
        if team.domain_experts: mgmt_base += 0.1
        if team.repeat_founder: mgmt_base += 0.1
        if team.tier1_background: mgmt_base += 0.05
        if team.notable_advisors: mgmt_base += 0.05
        s_management = min(1.0, mgmt_base)

        # Dimension 3: Prototype / Product
        stage_map = {
            ProductStage.IDEA: 0.2,
            ProductStage.MVP: 0.5,
            ProductStage.BETA: 0.7,
            ProductStage.PAYING_CUSTOMERS: 0.9,
            ProductStage.SCALING: 1.0,
        }
        s_prototype = stage_map.get(prod.stage, 0.5)
        if prod.has_patent_or_ip: s_prototype = min(1.0, s_prototype + 0.05)
        if prod.proprietary_data_moat: s_prototype = min(1.0, s_prototype + 0.05)

        # Dimension 4: Strategic Relationships
        s_relationships = 0.3
        if t.has_lois: s_relationships += 0.25
        if t.logo_customer_count >= 1: s_relationships += 0.2
        if team.notable_advisors: s_relationships += 0.15
        if t.paying_customer_count >= 5: s_relationships += 0.1
        s_relationships = min(1.0, s_relationships)

        # Dimension 5: Product Rollout / Sales
        s_rollout = 0.1
        if t.has_revenue and t.monthly_recurring_revenue > 0:
            arr = t.annual_recurring_revenue or t.monthly_recurring_revenue * 12
            s_rollout = min(1.0, 0.3 + arr / 1.0)  # Full score at $1M ARR
        elif t.paying_customer_count >= 1:
            s_rollout = 0.5
        elif t.has_lois:
            s_rollout = 0.35
        elif prod.stage in [ProductStage.BETA, ProductStage.PAYING_CUSTOMERS]:
            s_rollout = 0.4

    # Calculate indicated value: per-dimension score × per-dimension cap × regional premium
    indicated = (
        s_idea * caps["idea"]
        + s_management * caps["management"]
        + s_prototype * caps["prototype"]
        + s_relationships * caps["relationships"]
        + s_rollout * caps["rollout"]
    ) * regional_premium
    value_low = indicated * 0.7
    value_high = indicated * 1.4

    if reapportioned:
        cap_desc = (
            f"AI-native calibration re-apportions the ${_BERKUS_TOTAL_CAP:.1f}M Berkus ceiling "
            f"toward prototype/IP (caps: "
            + ", ".join(f"{d} ${c * regional_premium:.2f}M" for d, c in caps.items())
            + f"; total unchanged) × "
            f"{inp.fundraise.geography.value.replace('_', ' ').title()} premium {regional_premium:.2f}x. "
        )
    else:
        cap_desc = (
            f"5 dimensions × up to ${factor_max:.2f}M each "
            f"(${_BERKUS_TOTAL_CAP:.1f}M Berkus ceiling × "
            f"{inp.fundraise.geography.value.replace('_', ' ').title()} premium {regional_premium:.2f}x). "
        )

    return ValuationMethodResult(
        method_name="berkus",
        method_label="Berkus Method",
        indicated_value=round(indicated, 2),
        value_low=round(value_low, 2),
        value_high=round(value_high, 2),
        applicable=inp.fundraise.stage == StartupStage.PRE_SEED,
        rationale=(
            cap_desc
            + f"Scores: Idea {s_idea:.0%}, Team {s_management:.0%}, Product {s_prototype:.0%}, "
            f"Relationships {s_relationships:.0%}, Sales {s_rollout:.0%}."
        ),
        inputs_used={
            "per_dimension_cap": round(factor_max, 3),
            "per_dimension_caps": {d: round(c * regional_premium, 3) for d, c in caps.items()},
            "ai_reapportioned": reapportioned,
            "total_cap": round(_BERKUS_TOTAL_CAP * regional_premium, 3),
            "regional_premium": regional_premium,
            "scores": {
                "idea": round(s_idea, 2),
                "management": round(s_management, 2),
                "prototype": round(s_prototype, 2),
                "relationships": round(s_relationships, 2),
                "rollout": round(s_rollout, 2),
            },
        },
    )


# ---------------------------------------------------------------------------
# Method 2: Scorecard Method
# ---------------------------------------------------------------------------

def _run_scorecard(
    inp: StartupInput,
    vdata: dict,
    warnings: Optional[list[str]] = None,
    weights_override: Optional[dict[str, float]] = None,
) -> ValuationMethodResult:
    """
    Scorecard Method: 7 weighted factors vs. regional comparable.
    Weighted sum (50–150% range) × regional median.

    `weights_override` (AI parameter matrix) replaces the benchmark weights
    with the score-blended AI-native weights; both always sum to 1.0, so the
    shift re-weights factors (toward product/IP) without a hidden premium.

    User-provided scorecard_scores are validated: missing factors are filled
    with the neutral 1.0, values are clamped to [0.5, 1.5], and unknown keys
    are ignored with a warning (appended to `warnings` when provided).
    """
    regional_premium = _get_regional_premium(inp.fundraise.geography.value)
    vertical_baseline = _get_vertical_baseline(vdata, inp.fundraise.stage)
    regional_median = vertical_baseline * regional_premium

    weights = weights_override or _BENCHMARKS["scorecard_weights"]

    if inp.scorecard_scores:
        provided = inp.scorecard_scores
        unknown_keys = sorted(k for k in provided if k not in weights)
        if unknown_keys and warnings is not None:
            warnings.append(
                f"Unknown scorecard factor(s) ignored: {', '.join(unknown_keys)}. "
                f"Valid factors: {', '.join(weights)}."
            )
        scores = {}
        for factor in weights:
            raw = provided.get(factor, 1.0)  # missing factor = peer average, not zero
            clamped = max(0.5, min(1.5, float(raw)))
            if clamped != raw and warnings is not None:
                warnings.append(
                    f"Scorecard factor '{factor}' value {raw} clamped to {clamped} "
                    "(valid range 0.5–1.5)."
                )
            scores[factor] = clamped
    else:
        t = inp.traction
        team = inp.team
        prod = inp.product
        market = inp.market

        # Management team (0.5–1.5)
        mgmt = 0.85
        if team.prior_exits >= 1: mgmt += 0.25
        if team.domain_experts: mgmt += 0.1
        if team.repeat_founder: mgmt += 0.1
        if team.technical_cofounder: mgmt += 0.05
        if team.tier1_background: mgmt += 0.05
        mgmt = max(0.5, min(1.5, mgmt))

        # Market size (0.5–1.5)
        tam = market.tam_usd_billions
        if tam >= 50: market_score = 1.5
        elif tam >= 10: market_score = 1.2
        elif tam >= 1: market_score = 1.0
        else: market_score = 0.7

        # Product / technology (0.5–1.5)
        product_score = 0.75
        stage_add = {
            ProductStage.IDEA: 0.0,
            ProductStage.MVP: 0.15,
            ProductStage.BETA: 0.3,
            ProductStage.PAYING_CUSTOMERS: 0.4,
            ProductStage.SCALING: 0.5,
        }.get(prod.stage, 0.15)
        product_score += stage_add
        if prod.has_patent_or_ip: product_score += 0.1
        if prod.proprietary_data_moat: product_score += 0.1
        if prod.open_source_traction: product_score += 0.05
        product_score = max(0.5, min(1.5, product_score))

        # Competitive environment (0.5–1.5)
        comp_score = {"low": 0.7, "medium": 1.0, "high": 1.35}.get(market.competitive_moat, 1.0)

        # Marketing / sales (0.5–1.5)
        sales_score = 0.7
        if t.has_revenue: sales_score += 0.2
        if t.has_lois: sales_score += 0.15
        if t.paying_customer_count >= 10: sales_score += 0.2
        elif t.paying_customer_count >= 3: sales_score += 0.1
        sales_score = max(0.5, min(1.5, sales_score))

        # Additional financing needed (0.5–1.5; less = better)
        # burn==0 AND cash==0 means the data is unknown — score neutral, not best-case.
        if t.monthly_burn_rate > 0:
            runway: Optional[float] = t.cash_on_hand / t.monthly_burn_rate
        elif t.cash_on_hand == 0:
            runway = None  # unknown
        else:
            runway = 24.0  # cash with no burn: genuinely long runway
        if runway is None: financing_score = 1.0
        elif runway >= 18: financing_score = 1.2
        elif runway >= 12: financing_score = 1.0
        elif runway >= 6: financing_score = 0.8
        else: financing_score = 0.6

        # Other factors (geography is already priced via the regional premium
        # multiplier — do not double-count it here)
        other_score = 1.0
        if prod.regulatory_clearance: other_score = 1.2

        scores = {
            "management_team": mgmt,
            "market_size": market_score,
            "product_technology": product_score,
            "competitive_environment": comp_score,
            "marketing_sales_channels": sales_score,
            "additional_financing_needed": financing_score,
            "other_factors": other_score,
        }

    # Weighted sum
    weighted_sum = sum(weights.get(k, 0) * v for k, v in scores.items())
    indicated = weighted_sum * regional_median
    value_low = indicated * 0.8
    value_high = indicated * 1.25

    return ValuationMethodResult(
        method_name="scorecard",
        method_label="Scorecard (Bill Payne) Method",
        indicated_value=round(indicated, 2),
        value_low=round(value_low, 2),
        value_high=round(value_high, 2),
        applicable=inp.fundraise.stage in [StartupStage.PRE_SEED, StartupStage.SEED],
        rationale=(
            f"Weighted scoring vs. regional median of ${regional_median:.1f}M. "
            f"Overall multiplier: {weighted_sum:.2f}x (1.0 = peer average). "
            f"Key drivers: team {scores.get('management_team', 1.0):.2f}x, "
            f"market {scores.get('market_size', 1.0):.2f}x, "
            f"product {scores.get('product_technology', 1.0):.2f}x."
        ),
        inputs_used={
            "regional_median": regional_median,
            "weighted_multiplier": round(weighted_sum, 3),
            "weights": {k: round(v, 4) for k, v in weights.items()},
            "ai_weights_applied": weights_override is not None,
            "scores": {k: round(v, 2) for k, v in scores.items()},
        },
    )


# ---------------------------------------------------------------------------
# Method 3: Risk Factor Summation
# ---------------------------------------------------------------------------

def _run_rfs(
    inp: StartupInput,
    vdata: dict,
    warnings: Optional[list[str]] = None,
    step_overrides: Optional[dict[str, float]] = None,
) -> ValuationMethodResult:
    """
    Risk Factor Summation: 12 categories, each -max_steps to +max_steps
    (max_steps from the risk_factor_summation benchmark block, currently ±2).
    Each step = ±$250K (±$0.25M) scaled to the vertical baseline.

    `step_overrides` (AI parameter matrix) widens the raw per-step value for
    specific volatility categories (Technology, Competition, Litigation).
    The widening is symmetric — negative scores in those categories subtract
    more, positive scores add more.

    User-provided risk_factor_scores are clamped to ±max_steps; unknown
    categories are ignored with a warning (appended to `warnings` when provided).
    """
    regional_premium = _get_regional_premium(inp.fundraise.geography.value)
    vertical_baseline = _get_vertical_baseline(vdata, inp.fundraise.stage)
    base = vertical_baseline * regional_premium
    # Scale adjustment per step proportionally to vertical baseline.
    # The benchmark $0.25M/step was calibrated for the ~$7.7M market median.
    # For defense tech ($10M+) or AI infra ($10M+), flat $0.25M is negligible;
    # scaling keeps each step at ~3.2% of baseline regardless of vertical.
    market_median = _BENCHMARKS["market_wide_medians"]["pre_seed"]["valuation_median"]
    rfs_config = _BENCHMARKS["risk_factor_summation"]
    raw_adj = rfs_config["adjustment_per_step_usd_millions"]
    max_steps = int(rfs_config.get("max_steps", 2))
    valid_categories = rfs_config.get("categories", [])
    baseline_scale = (base / market_median) if market_median > 0 else 1.0
    adj_per_step = raw_adj * baseline_scale

    def _step_for(category: str) -> float:
        """Per-category step value: overridden raw step × baseline scaling."""
        raw = (step_overrides or {}).get(category, raw_adj)
        return raw * baseline_scale

    if inp.risk_factor_scores:
        provided = inp.risk_factor_scores
        unknown_keys = sorted(
            k for k in provided if valid_categories and k not in valid_categories
        )
        if unknown_keys and warnings is not None:
            warnings.append(
                f"Unknown risk factor categor{'ies' if len(unknown_keys) > 1 else 'y'} ignored: "
                f"{', '.join(unknown_keys)}. Valid categories: {', '.join(valid_categories)}."
            )
        rfs = {}
        for category, raw in provided.items():
            if valid_categories and category not in valid_categories:
                continue
            clamped = max(-max_steps, min(max_steps, int(raw)))
            if clamped != raw and warnings is not None:
                warnings.append(
                    f"Risk factor '{category}' score {raw} clamped to {clamped} "
                    f"(valid range -{max_steps} to +{max_steps})."
                )
            rfs[category] = clamped
    else:
        t = inp.traction
        team = inp.team
        prod = inp.product

        rfs = {}

        # Management
        mgmt_score = 0
        if team.prior_exits >= 1: mgmt_score += 2
        elif team.domain_experts: mgmt_score += 1
        elif not team.technical_cofounder and inp.fundraise.vertical in [
            StartupVertical.AI_ML_INFRASTRUCTURE, StartupVertical.DEVELOPER_TOOLS
        ]: mgmt_score -= 1
        rfs["Management"] = max(-2, min(2, mgmt_score))

        # Stage of Business
        stage_map = {
            ProductStage.IDEA: -2,
            ProductStage.MVP: -1,
            ProductStage.BETA: 0,
            ProductStage.PAYING_CUSTOMERS: 1,
            ProductStage.SCALING: 2,
        }
        rfs["Stage of Business"] = stage_map.get(prod.stage, 0)

        # Legislation / Political
        # Defense tech faces ITAR, CMMC, clearance requirements — high regulatory burden
        high_reg = [
            StartupVertical.FINTECH, StartupVertical.HEALTHTECH,
            StartupVertical.BIOTECH_PHARMA, StartupVertical.DEFENSE_TECH,
        ]
        rfs["Legislation / Political"] = -1 if inp.fundraise.vertical in high_reg else 1 if prod.regulatory_clearance else 0

        # Manufacturing / Operations
        hard_hw = [StartupVertical.DEEP_TECH_HARDWARE, StartupVertical.CLIMATE_ENERGY, StartupVertical.BIOTECH_PHARMA]
        rfs["Manufacturing / Operations"] = -1 if inp.fundraise.vertical in hard_hw else 0

        # Sales / Marketing
        sales_score = -1
        if t.paying_customer_count >= 10: sales_score = 2
        elif t.paying_customer_count >= 3: sales_score = 1
        elif t.has_lois or t.paying_customer_count >= 1: sales_score = 0
        rfs["Sales / Marketing"] = sales_score

        # Funding / Capital Raising
        # burn==0 AND cash==0 means runway is unknown — neutral, not best-case.
        if t.monthly_burn_rate > 0:
            runway: Optional[float] = t.cash_on_hand / t.monthly_burn_rate
        elif t.cash_on_hand == 0:
            runway = None  # unknown
        else:
            runway = 18.0  # cash with no burn: healthy
        if runway is None:
            rfs["Funding / Capital Raising"] = 0
        else:
            rfs["Funding / Capital Raising"] = 1 if runway >= 18 else 0 if runway >= 12 else -1

        # Competition
        comp_map = {"low": -2, "medium": 0, "high": 1}
        rfs["Competition"] = comp_map.get(inp.market.competitive_moat, 0)

        # Technology
        tech_score = 0
        if prod.has_patent_or_ip: tech_score += 1
        if prod.proprietary_data_moat: tech_score += 1
        rfs["Technology"] = max(-2, min(2, tech_score))

        # Litigation
        rfs["Litigation"] = 0  # No information

        # International
        rfs["International"] = 1 if inp.market.tam_usd_billions >= 5 else 0

        # Reputation
        rep_score = 0
        if team.tier1_background: rep_score += 1
        if team.prior_exits >= 1: rep_score += 1
        rfs["Reputation"] = max(-2, min(2, rep_score))

        # Exit Potential
        exit_score = 0
        if inp.market.tam_usd_billions >= 10: exit_score += 1
        # Defense tech exit comps (Palantir, Anduril, Shield AI) justify premium
        if inp.fundraise.vertical in [
            StartupVertical.AI_ML_INFRASTRUCTURE,
            StartupVertical.AI_ENABLED_SAAS,
            StartupVertical.DEFENSE_TECH,
        ]: exit_score += 1
        rfs["Exit Potential"] = max(-2, min(2, exit_score))

    total_adjustment = sum(score * _step_for(category) for category, score in rfs.items())
    indicated = base + total_adjustment
    indicated = max(0.5, indicated)  # floor at $500K

    step_note = ""
    if step_overrides:
        step_note = (
            " AI-native calibration widens the per-step value for "
            + ", ".join(sorted(step_overrides))
            + " (symmetric — cuts both ways)."
        )

    return ValuationMethodResult(
        method_name="risk_factor_summation",
        method_label="Risk Factor Summation",
        indicated_value=round(indicated, 2),
        value_low=round(max(0.5, indicated * 0.80), 2),
        value_high=round(indicated * 1.25, 2),
        applicable=inp.fundraise.stage in [StartupStage.PRE_SEED, StartupStage.SEED],
        rationale=(
            f"Base ${base:.1f}M + total adjustment ${total_adjustment:+.2f}M "
            f"from {sum(rfs.values())} net score across 12 risk categories "
            f"(${adj_per_step:.2f}M per step)." + step_note
        ),
        inputs_used={
            "base": base,
            "adjustment_per_step": adj_per_step,
            "step_overrides": {
                k: round(v * baseline_scale, 4) for k, v in (step_overrides or {}).items()
            },
            "scores": rfs,
            "total_adjustment": round(total_adjustment, 2),
        },
    )


# ---------------------------------------------------------------------------
# Method 4: ARR Multiple
# ---------------------------------------------------------------------------

def _run_arr_multiple(
    inp: StartupInput,
    vdata: dict,
    arr_uplift: float = 0.0,
    notes: Optional[list[str]] = None,
) -> ValuationMethodResult:
    """
    ARR Multiple method. Uses NRR and growth rate to select the appropriate multiple band.
    Only applicable when has_revenue is set AND ARR > 0 (consistent with the
    NRR scorecard flag, which also gates on has_revenue).

    `arr_uplift` (AI parameter matrix) lifts the vertical P50 multiple by
    (1 + uplift), CAPPED at the same-stage ai_enabled_saas arr_multiple_p50 —
    an AI toggle can lift a traditional company's multiple toward, but never
    beyond, what a true AI-enabled SaaS company commands. The P25/P75 bounds
    are scaled by the same effective factor so the indicated value can never
    invert out of its own range.
    """
    t = inp.traction
    arr = t.annual_recurring_revenue or (t.monthly_recurring_revenue * 12)

    business = inp.fundraise.business_model
    nonsoftware = business in {'hardware', 'services', 'biotech', 'mixed'} or (business == 'auto' and inp.fundraise.vertical.value in {'deep_tech_hardware', 'biotech_pharma', 'climate_energy', 'consumer', 'marketplace'})
    if nonsoftware:
        return ValuationMethodResult(method_name='arr_multiple', method_label='ARR Multiple',
            applicable=False, indicated_value=None, value_low=None, value_high=None, inputs_used={},
            rationale='Recurring-software method excluded for this business model. Use milestone evidence and specialist valuation inputs.')
    if arr <= 0 or not t.has_revenue:
        if arr > 0 and not t.has_revenue:
            rationale = (
                "Recurring revenue was provided but has_revenue is false — "
                "ARR multiple method gated off. Set has_revenue=true to include it."
            )
        else:
            rationale = "No ARR reported — ARR multiple method not applicable."
        return ValuationMethodResult(
            method_name="arr_multiple",
            method_label="ARR Multiple",
            indicated_value=None,
            value_low=None,
            value_high=None,
            applicable=False,
            rationale=rationale,
            inputs_used={"arr": arr},
        )

    # Determine base multiple from vertical benchmarks
    p50_multiple = vdata.get("arr_multiple_p50")
    p25_multiple = vdata.get("arr_multiple_p25")
    p75_multiple = vdata.get("arr_multiple_p75")

    if p50_multiple is None:
        # Biotech / milestone-based — use revenue multiple if applicable, else N/A
        return ValuationMethodResult(
            method_name="arr_multiple",
            method_label="ARR Multiple",
            indicated_value=None,
            value_low=None,
            value_high=None,
            applicable=False,
            rationale="ARR multiples are not the primary method for this vertical (milestone/asset-based).",
            inputs_used={"arr": arr},
        )

    # --- AI-native ARR multiple uplift (parameter matrix) ---
    # effective_p50 = vertical_p50 × (1 + uplift), capped at the same-stage
    # ai_enabled_saas p50. P25/P75 scale by the same effective factor.
    uplift_factor = 1.0
    uplift_cap = None
    cap_bound = False
    if arr_uplift > 0:
        uplift_cap = (
            _BENCHMARKS["verticals"]
            .get(StartupVertical.AI_ENABLED_SAAS.value, {})
            .get(inp.fundraise.stage.value, {})
            .get("arr_multiple_p50")
        )
        target_multiple = p50_multiple * (1 + arr_uplift)
        if uplift_cap is not None and target_multiple > uplift_cap:
            # Never lift a traditional company beyond what a true AI-enabled
            # SaaS company commands (never below the vertical's own P50).
            target_multiple = max(p50_multiple, float(uplift_cap))
            cap_bound = True
            if notes is not None:
                notes.append(
                    f"AI-native ARR multiple uplift capped at the {inp.fundraise.stage.value.replace('_', ' ')} "
                    f"AI-enabled SaaS median of {uplift_cap:.1f}x — the uplift lifts a multiple toward, "
                    "but never beyond, what a true AI-enabled SaaS company commands."
                )
        uplift_factor = target_multiple / p50_multiple if p50_multiple > 0 else 1.0

    base_multiple = p50_multiple * uplift_factor

    # NRR adjustment
    nrr = t.net_revenue_retention
    nrr_adj = 0.0
    if nrr >= 1.40: nrr_adj = 0.30   # elite; can double the multiple
    elif nrr >= 1.20: nrr_adj = 0.15
    elif nrr >= 1.10: nrr_adj = 0.05
    elif nrr < 1.00: nrr_adj = -0.20

    # MoM growth adjustment
    mom = t.mom_growth_rate
    if mom >= 0.20: growth_adj = 0.15
    elif mom >= 0.10: growth_adj = 0.05
    elif mom >= 0.05: growth_adj = 0.0
    else: growth_adj = -0.10

    # Gross margin adjustment
    gm = t.gross_margin
    if gm >= 0.80: gm_adj = 0.05
    elif gm >= 0.60: gm_adj = 0.0
    elif gm < 0.40: gm_adj = -0.15
    else: gm_adj = -0.07

    # Burn multiple adjustment
    if inp.traction.monthly_burn_rate > 0 and arr > 0:
        burn_mult = (inp.traction.monthly_burn_rate * 12) / arr
        if burn_mult <= 1.0: burn_adj = 0.10
        elif burn_mult <= 1.5: burn_adj = 0.05
        elif burn_mult > 2.5: burn_adj = -0.10
        else: burn_adj = 0.0
    else:
        burn_adj = 0.0

    adjustment_factor = 1 + nrr_adj + growth_adj + gm_adj + burn_adj
    adjusted_multiple = max(1.0, base_multiple * adjustment_factor)

    # Apply the same AI uplift factor and adjustment factor to the P25/P75
    # bounds so the indicated value (adjusted P50) can never invert out of
    # its own range (S-5 bracket fix preserved).
    low_multiple = (
        p25_multiple * uplift_factor if p25_multiple is not None else base_multiple * 0.7
    ) * adjustment_factor
    high_multiple = (
        p75_multiple * uplift_factor if p75_multiple is not None else base_multiple * 1.4
    ) * adjustment_factor

    indicated = arr * adjusted_multiple
    value_low = min(arr * low_multiple, indicated)
    value_high = max(arr * high_multiple, indicated)

    # Rule of 40: compounded annual growth + burn-based operating margin proxy.
    # MoM growth compounds — (1+mom)^12 − 1 — it does not simply multiply by 12.
    yoy_growth_pct = ((1 + mom) ** 12 - 1) * 100 if mom > 0 else 0.0
    # Margin proxy from burn: ≈ −(annualized burn) / ARR. Zero burn ≈ breakeven.
    margin_pct = -((t.monthly_burn_rate * 12) / arr) * 100 if t.monthly_burn_rate > 0 else 0.0
    rule_of_40 = yoy_growth_pct + margin_pct

    # Grade against the benchmark rule_of_40_bands
    ro40_bands = _BENCHMARKS.get("rule_of_40_bands", {})
    rule_of_40_band = None
    for band_name in ["elite", "excellent", "strong", "average", "below_bar"]:
        band = ro40_bands.get(band_name)
        if band and rule_of_40 >= band.get("min", 0):
            rule_of_40_band = band.get("label", band_name)
            break
    if rule_of_40_band is None:
        rule_of_40_band = ro40_bands.get("below_bar", {}).get("label", "below bar")

    return ValuationMethodResult(
        method_name="arr_multiple",
        method_label="ARR Multiple",
        indicated_value=round(indicated, 2),
        value_low=round(value_low, 2),
        value_high=round(value_high, 2),
        applicable=True,
        rationale=(
            f"ARR ${arr:.2f}M × {adjusted_multiple:.1f}x adjusted multiple "
            f"(base {base_multiple:.1f}x"
            + (
                f" incl. AI-native uplift ×{uplift_factor:.2f}"
                + (" — capped at AI-enabled SaaS median" if cap_bound else "")
                if uplift_factor > 1.0
                else ""
            )
            + f", NRR {nrr:.0%} adj {nrr_adj:+.0%}, "
            f"growth adj {growth_adj:+.0%}, GM adj {gm_adj:+.0%})."
        ),
        inputs_used={
            "arr": arr,
            "base_multiple_p50": p50_multiple,
            "effective_base_multiple": round(base_multiple, 2),
            "arr_multiple_uplift": round(arr_uplift, 4),
            "uplift_factor": round(uplift_factor, 4),
            "uplift_cap_multiple": uplift_cap,
            "uplift_cap_bound": cap_bound,
            "adjusted_multiple": round(adjusted_multiple, 2),
            "adjustment_factor": round(adjustment_factor, 3),
            "nrr": nrr,
            "mom_growth": mom,
            "gross_margin": gm,
            "rule_of_40_approx": round(rule_of_40, 1),
            "rule_of_40_band": rule_of_40_band,
        },
    )


# ---------------------------------------------------------------------------
# Round timing signal
# ---------------------------------------------------------------------------

# Typical months between stages based on Carta / PitchBook median data (2023–2025).
# These represent the median time from close of current round to start of next raise process.
_STAGE_MONTHS_TO_NEXT: dict[str, float] = {
    "pre_seed": 18.0,   # Pre-seed → Seed: ~18 months median
    "seed": 24.0,       # Seed → Series A: ~24 months median
    "series_a": 0.0,    # Terminal — no next stage modeled
}

# Milestone checklist per stage. Each entry is (description, bool_check_fn).
# The check_fn receives (inp: StartupInput) and returns True if milestone is MET.
_STAGE_MILESTONES: dict[str, list[tuple[str, object]]] = {
    "pre_seed": [
        ("Working prototype or MVP", lambda inp: inp.product.stage.value in ("mvp", "beta", "paying_customers", "scaling")),
        ("At least 1 paying customer or signed LOI", lambda inp: inp.traction.paying_customer_count >= 1 or inp.traction.has_lois),
        ("Technical co-founder on team", lambda inp: inp.team.technical_cofounder),
        ("TAM ≥ $1B", lambda inp: inp.market.tam_usd_billions >= 1.0),
    ],
    "seed": [
        ("$100K+ ARR or strong pilot pipeline", lambda inp: (inp.traction.annual_recurring_revenue or inp.traction.monthly_recurring_revenue * 12) >= 0.1 or inp.traction.logo_customer_count >= 2),
        ("MoM growth ≥ 10%", lambda inp: inp.traction.mom_growth_rate >= 0.10),
        ("NRR ≥ 100%", lambda inp: inp.traction.net_revenue_retention >= 1.0),
        ("≥ 3 paying customers", lambda inp: inp.traction.paying_customer_count >= 3),
        ("Gross margin ≥ 60%", lambda inp: inp.traction.gross_margin >= 0.60),
    ],
    "series_a": [
        ("$1M+ ARR", lambda inp: (inp.traction.annual_recurring_revenue or inp.traction.monthly_recurring_revenue * 12) >= 1.0),
        ("MoM growth ≥ 15%", lambda inp: inp.traction.mom_growth_rate >= 0.15),
        ("NRR ≥ 110%", lambda inp: inp.traction.net_revenue_retention >= 1.10),
        ("≥ 10 paying customers", lambda inp: inp.traction.paying_customer_count >= 10),
        ("Gross margin ≥ 70%", lambda inp: inp.traction.gross_margin >= 0.70),
    ],
}


def _next_stage_for(stage: StartupStage) -> Optional[StartupStage]:
    """Return the next fundraising stage, or None if Series A (terminal)."""
    _next: dict[StartupStage, Optional[StartupStage]] = {
        StartupStage.PRE_SEED: StartupStage.SEED,
        StartupStage.SEED: StartupStage.SERIES_A,
        StartupStage.SERIES_A: None,
    }
    return _next[stage]


def _compute_round_timing(inp: StartupInput, vdata: dict) -> RoundTimingSignal:
    """
    Compute the round timing signal for the current startup.

    Signal logic:
    - raise_now:         runway < (months_to_next_round - fundraise_process_months)
                         i.e. already in or past the raise window
    - raise_in_months:   runway is sufficient but raise window opens within 12 months
    - focus_milestones:  runway is healthy AND raise window is > 12 months away
                         OR Series A terminal stage

    Milestone gaps are computed regardless of signal to surface actionable gaps.
    """
    t = inp.traction
    stage = inp.fundraise.stage
    FUNDRAISE_PROCESS_MONTHS = 6.0

    # --- Runway ---
    if t.monthly_burn_rate > 0:
        runway_months = t.cash_on_hand / t.monthly_burn_rate
    else:
        # Zero burn: effectively infinite runway — use a large sentinel
        runway_months = 999.0

    # --- Stage timeline ---
    months_to_next = _STAGE_MONTHS_TO_NEXT.get(stage.value, 0.0)
    months_until_window = months_to_next - FUNDRAISE_PROCESS_MONTHS

    # --- Series A terminal case ---
    next_stage = _next_stage_for(stage)
    if next_stage is None:
        # Series A: no next round modeled — focus on milestones / growth
        signal = RaiseSignal.FOCUS_MILESTONES
        signal_label = "Focus on Growth"
        signal_detail = (
            "You're at Series A — the next raise (Series B) depends on hitting $5–10M ARR "
            "and demonstrable unit economics. Focus on growth and efficiency metrics."
        )
    else:
        # --- Signal resolution ---
        if runway_months < months_until_window:
            # Runway won't last to the raise window — start now
            signal = RaiseSignal.RAISE_NOW
            signal_label = "Raise Now"
            signal_detail = (
                f"With {runway_months:.0f} months of runway and a typical "
                f"{months_to_next:.0f}-month path to your next round, you need to begin "
                f"fundraising immediately. Allow {FUNDRAISE_PROCESS_MONTHS:.0f} months for the process."
            )
        elif runway_months < months_until_window + 12:
            # Raise window opens within 12 months
            months_left = runway_months - months_until_window
            signal = RaiseSignal.RAISE_IN_MONTHS
            signal_label = f"Raise in ~{max(1, round(months_left)):.0f} Months"
            signal_detail = (
                f"Your runway supports waiting, but the raise window opens in roughly "
                f"{max(1, round(months_left)):.0f} months. Use this time to hit key milestones "
                f"and warm up investor relationships."
            )
        else:
            # Healthy runway — focus on milestones
            signal = RaiseSignal.FOCUS_MILESTONES
            signal_label = "Focus on Milestones"
            signal_detail = (
                f"You have {runway_months:.0f} months of runway — well ahead of the raise window. "
                f"Prioritize hitting the milestones below to maximize your valuation at the next round."
            )

    # --- Milestone gap analysis ---
    milestone_defs = _STAGE_MILESTONES.get(stage.value, [])
    milestone_gaps: list[str] = []
    met_count = 0
    for description, check_fn in milestone_defs:
        try:
            met = bool(check_fn(inp))  # type: ignore[operator]
        except Exception:
            met = False
        if met:
            met_count += 1
        else:
            milestone_gaps.append(description)

    total_count = len(milestone_defs)

    # --- Warnings ---
    timing_warnings: list[str] = []
    if t.monthly_burn_rate > 0 and runway_months < 6:
        timing_warnings.append(
            f"Critical: only {runway_months:.0f} months of runway remaining. "
            "Fundraising at this stage severely limits negotiating leverage."
        )
    if t.monthly_burn_rate == 0 and t.cash_on_hand == 0:
        timing_warnings.append(
            "No burn rate or cash data provided — runway estimate is unavailable. "
            "Add cash on hand and monthly burn for an accurate timing signal."
        )

    if t.monthly_burn_rate <= 0:
        signal_label = 'Runway Not Quantified'
        signal_detail = 'No positive monthly cash burn was supplied. A dated fundraising recommendation requires cash and burn inputs; milestone guidance remains illustrative.'

    # Populate raise_in_months field for the raise_in_months signal
    raise_in_months_val: Optional[float] = None
    if signal == RaiseSignal.RAISE_IN_MONTHS:
        raise_in_months_val = max(1.0, runway_months - months_until_window)

    return RoundTimingSignal(
        runway_months=round(runway_months if runway_months < 999 else 0.0, 1),
        months_to_next_round=months_to_next,
        fundraise_process_months=FUNDRAISE_PROCESS_MONTHS,
        months_until_raise_window=months_until_window,
        signal=signal,
        signal_label=signal_label,
        signal_detail=signal_detail,
        milestone_gaps=milestone_gaps,
        milestone_met_count=met_count,
        milestone_total_count=total_count,
        raise_in_months=raise_in_months_val,
        warnings=timing_warnings,
    )


# ---------------------------------------------------------------------------
# Dilution modeling
# ---------------------------------------------------------------------------

def _projected_round(
    vertical: StartupVertical,
    next_stage: StartupStage,
    floor_pre: float,
) -> tuple[float, float]:
    """
    Project (pre_money, raise_amount) for the next round from the vertical's
    next-stage benchmark block, falling back to market-wide medians.
    floor_pre enforces a step-up over the prior round's post-money.
    """
    ndata = _get_vertical_data(vertical, next_stage)
    market = _BENCHMARKS["market_wide_medians"].get(next_stage.value, {})
    market_pre = market.get("valuation_pre_money_median") or market.get("valuation_median") or 0.0
    pre = max(ndata.get("valuation_p50") or market_pre, floor_pre)
    raise_amount = (
        ndata.get("round_size_median")
        or market.get("round_size_median")
        or (3.0 if next_stage == StartupStage.SEED else 10.0)
    )
    return float(pre), float(raise_amount)


def _build_dilution_scenarios(
    inp: StartupInput,
    basis_pre_money: float,
    model_pre_money: float,
) -> list[DilutionScenario]:
    """
    Project dilution across the current round and the next typical rounds,
    using the vertical's per-stage round sizes and valuation medians.

    The CURRENT round is priced at `basis_pre_money` — the preparer's ask when
    one was provided, otherwise the model midpoint. Dilution describes the
    actual deal on the table, so it flows off the price actually being asked,
    not the model's blend.

    Projected FUTURE rounds stay anchored to `model_pre_money` (the model
    midpoint): they are market projections, and the model does not assume the
    market validates the preparer's ask. When the ask is above market, a
    projected round can therefore price below the current post-money — that is
    the down-round risk, surfaced as a warning by the orchestrator.

    Existing SAFEs convert at the next PRICED round: if the current round is
    priced equity they convert now; otherwise conversion is deferred to the
    first projected priced round.
    """
    raise_amount = inp.fundraise.raise_amount
    stage = inp.fundraise.stage
    vertical = inp.fundraise.vertical
    scenarios: list[DilutionScenario] = []

    # Existing SAFE stack: converts at the next priced round.
    existing_safe_pct = 0.0
    pending_safe_stack = 0.0
    if inp.fundraise.existing_safe_stack > 0:
        if inp.fundraise.instrument == InstrumentType.PRICED_EQUITY and basis_pre_money > 0:
            # Current round is priced — SAFEs convert into it now.
            existing_safe_pct = min(0.30, inp.fundraise.existing_safe_stack / basis_pre_money)
        else:
            # Current round is a SAFE/note — conversion deferred to the
            # projected next priced round below.
            pending_safe_stack = inp.fundraise.existing_safe_stack

    founder_pct = 1.0 - existing_safe_pct

    # Current round
    post_money = basis_pre_money + raise_amount
    inv_pct = raise_amount / post_money
    new_founder_pct = founder_pct * (1 - inv_pct)

    scenarios.append(DilutionScenario(
        round_label=f"Current ({stage.value.replace('_', ' ').title()})",
        pre_money=round(basis_pre_money, 2),
        raise_amount=round(raise_amount, 2),
        post_money=round(post_money, 2),
        investor_ownership_pct=round(inv_pct, 4),
        founder_ownership_pct_before=round(founder_pct, 4),
        founder_ownership_pct_after=round(new_founder_pct, 4),
        dilution_this_round=round(inv_pct, 4),
    ))

    founder_pct = new_founder_pct

    # Next round projections from the vertical's per-stage benchmark blocks.
    # Step-up floors anchor to the MODEL-midpoint post-money, not the ask —
    # future rounds are market projections (see docstring).
    model_post = model_pre_money + raise_amount
    next_rounds: list[tuple[str, float, float, float]] = []  # (label, pre_money, raise, option_pool)
    if stage == StartupStage.PRE_SEED:
        # Projected Seed pre-money must exceed model post-money (step-up floor: 1.5x post-money)
        seed_pre, seed_raise = _projected_round(vertical, StartupStage.SEED, model_post * 1.5)
        seed_post = seed_pre + seed_raise
        # Projected Series A pre-money must exceed projected Seed post-money (floor: 2x seed post)
        series_a_pre, series_a_raise = _projected_round(vertical, StartupStage.SERIES_A, seed_post * 2.0)
        next_rounds = [
            ("Seed (projected)", seed_pre, seed_raise, 0.10),
            ("Series A (projected)", series_a_pre, series_a_raise, 0.10),
        ]
    elif stage == StartupStage.SEED:
        # Projected Series A pre-money must exceed model post-money (floor: 2x post-money)
        series_a_pre, series_a_raise = _projected_round(vertical, StartupStage.SERIES_A, model_post * 2.0)
        next_rounds = [
            ("Series A (projected)", series_a_pre, series_a_raise, 0.10),
        ]

    for label, next_pre, next_raise, option_pool in next_rounds:
        # Option pool shuffle: pool comes out of pre-money
        pool_dilution = option_pool  # applied to existing shareholders
        post = next_pre + next_raise
        inv_pct = next_raise / post
        # Deferred SAFE stack converts at the first projected priced round
        safe_conversion_pct = 0.0
        if pending_safe_stack > 0 and next_pre > 0:
            safe_conversion_pct = min(0.30, pending_safe_stack / next_pre)
            pending_safe_stack = 0.0
        # Founder diluted by SAFE conversion and option pool first, then investor
        founder_after_pool = founder_pct * (1 - safe_conversion_pct) * (1 - pool_dilution)
        founder_after_inv = founder_after_pool * (1 - inv_pct)

        scenarios.append(DilutionScenario(
            round_label=label,
            pre_money=round(next_pre, 2),
            raise_amount=round(next_raise, 2),
            post_money=round(post, 2),
            investor_ownership_pct=round(inv_pct, 4),
            founder_ownership_pct_before=round(founder_pct, 4),
            founder_ownership_pct_after=round(founder_after_inv, 4),
            dilution_this_round=round(founder_pct - founder_after_inv, 4),
        ))
        founder_pct = founder_after_inv

    return scenarios


def _build_safe_conversion(
    inp: StartupInput,
    basis_pre_money: float,
    model_pre_money: float,
) -> Optional[SAFEConversionSummary]:
    """
    Model how the current SAFE converts at the projected next priced round.

    `basis_pre_money` (preparer's ask when provided, else the model midpoint)
    anchors the capless-SAFE proxy cap. The projected next priced round stays
    anchored to `model_pre_money` — it is a market projection, so an
    above-market cap can convert at the discount instead of the cap. This is
    the same projection convention as the dilution model.

    Mechanics depend on safe_type:
      - post_money (YC 2018+ standard, ~87% of market): ownership at cap = raise / cap
      - pre_money (legacy):                             ownership at cap = raise / (cap + raise)

    Conversion at the projected next priced round happens at the LOWER of the
    cap and next_round_pre × (1 − discount); the governing term is reported.
    conversion_price_at_cap is None — a per-share price requires a share
    count, which the engine does not model.
    """
    if inp.fundraise.instrument != InstrumentType.SAFE:
        return None

    f = inp.fundraise
    if f.safe_valuation_cap is None:
        return None
    capless = False
    cap = f.safe_valuation_cap
    discount = f.safe_discount
    raise_amount = f.raise_amount
    safe_type = f.safe_type

    # Ownership implied by the cap alone
    if safe_type == "post_money":
        implied_ownership = raise_amount / cap if cap > 0 else 0.0
    else:
        implied_ownership = raise_amount / (cap + raise_amount) if (cap + raise_amount) > 0 else 0.0

    # Projected next priced round (same market-anchored projection as the
    # dilution model — floors off the model midpoint, not the ask)
    current_post = model_pre_money + raise_amount
    next_round_pre: Optional[float] = None
    next_round_label = ""
    if f.stage == StartupStage.PRE_SEED:
        next_round_pre, _ = _projected_round(f.vertical, StartupStage.SEED, current_post * 1.5)
        next_round_label = "Seed"
    elif f.stage == StartupStage.SEED:
        next_round_pre, _ = _projected_round(f.vertical, StartupStage.SERIES_A, current_post * 2.0)
        next_round_label = "Series A"

    governing_term: Optional[str] = None
    conversion_valuation: Optional[float] = None
    conversion_ownership: Optional[float] = None
    if next_round_pre is not None and cap > 0:
        discounted_valuation = next_round_pre * (1 - discount)
        cap_equivalent_pre = cap - raise_amount if safe_type == "post_money" else cap
        if discounted_valuation < cap_equivalent_pre:
            governing_term = "discount" if discount > 0 else "round_price"
            conversion_valuation = discounted_valuation
            # Discount conversion prices off the round itself (pre-money mechanics)
            conversion_ownership = raise_amount / (conversion_valuation + raise_amount)
        else:
            governing_term = "cap"
            conversion_valuation = cap
            if safe_type == "post_money":
                conversion_ownership = raise_amount / cap
            else:
                conversion_ownership = raise_amount / (cap + raise_amount)

    type_label = "post-money" if safe_type == "post_money" else "pre-money"
    note_parts = [
        f"{type_label.capitalize()} SAFE of ${raise_amount:.2f}M with a ${cap:.1f}M valuation cap "
        f"(implied ownership at cap: {implied_ownership:.1%})."
    ]
    if capless:
        note_parts.append(
            "No explicit cap was provided — the engine's blended valuation is used as a proxy cap."
        )
    if next_round_pre is not None and governing_term is not None:
        note_parts.append(
            f"At the projected {next_round_label} round (~${next_round_pre:.1f}M pre-money), "
            f"the {dict(discount='discount', round_price='round price', cap='valuation cap')[governing_term]} governs in this simplified illustration: "
            f"conversion at ${conversion_valuation:.1f}M for ~{conversion_ownership:.1%} ownership."
        )
    elif next_round_pre is None:
        note_parts.append(
            "No next priced round is modeled at Series A — conversion shown at the cap only."
        )
    if discount > 0:
        note_parts.append(f"Includes {discount:.0%} discount on conversion price.")
    if f.has_mfn_clause:
        note_parts.append("MFN clause present — monitor any subsequent SAFE issuances.")
    if f.existing_safe_stack > 0:
        note_parts.append(
            f"${f.existing_safe_stack:.1f}M in existing SAFEs not yet converted — "
            "cumulative dilution at next priced round will be higher than this single instrument."
        )
    note_parts.append(
        "Exact conversion requires fully diluted share counts, option pool and other converting securities; the illustration is not a final cap table."
    )

    return SAFEConversionSummary(
        safe_amount=raise_amount,
        valuation_cap=cap,
        discount_rate=discount,
        safe_type=safe_type,
        conversion_price_at_cap=None,  # requires shares outstanding (not modeled)
        implied_ownership_pct=round(implied_ownership, 4),
        next_round_pre_money=round(next_round_pre, 2) if next_round_pre is not None else None,
        conversion_valuation=round(conversion_valuation, 2) if conversion_valuation is not None else None,
        conversion_ownership_pct=round(conversion_ownership, 4) if conversion_ownership is not None else None,
        governing_term=governing_term,
        note=" ".join(note_parts),
    )


# ---------------------------------------------------------------------------
# Investor Scorecard
# ---------------------------------------------------------------------------

def _build_scorecard(inp: StartupInput, blended: float, vdata: dict) -> list[ScorecardFlag]:
    """Generate investor-grade scorecard flags."""
    flags: list[ScorecardFlag] = []
    t = inp.traction
    team = inp.team
    stage = inp.fundraise.stage

    # --- Burn Multiple ---
    if t.monthly_burn_rate > 0 and (t.monthly_recurring_revenue > 0 or t.annual_recurring_revenue > 0):
        arr = t.annual_recurring_revenue or t.monthly_recurring_revenue * 12
        burn_mult = (t.monthly_burn_rate * 12) / arr if arr > 0 else 99
        bands = _BENCHMARKS["burn_multiple_bands"]
        if burn_mult <= 1.0:
            signal = ValuationSignal.STRONG
            bm_label = bands["exceptional"]["label"]
        elif burn_mult <= 1.5:
            signal = ValuationSignal.FAIR
            bm_label = bands["great"]["label"]
        elif burn_mult <= 2.5:
            signal = ValuationSignal.WEAK
            bm_label = bands["average"]["label"]
        else:
            signal = ValuationSignal.WARNING
            bm_label = bands["red_flag"]["label"]

        flags.append(ScorecardFlag(
            metric="Burn / Current ARR (proxy)",
            value=f"{burn_mult:.1f}x",
            signal=signal,
            benchmark=bm_label,
            commentary="Annualized burn divided by current ARR. Net new ARR was not supplied, so this is not a true burn multiple.",
        ))

    # --- NRR ---
    if t.has_revenue and t.net_revenue_retention:
        nrr_pct = t.net_revenue_retention
        nrr_lookup = _BENCHMARKS["nrr_multiple_lookup"]
        if nrr_pct >= 1.40:
            nrr_signal = ValuationSignal.STRONG
            nrr_label = nrr_lookup["140_plus"]["label"]
        elif nrr_pct >= 1.20:
            nrr_signal = ValuationSignal.STRONG
            nrr_label = nrr_lookup["120_to_139"]["label"]
        elif nrr_pct >= 1.10:
            nrr_signal = ValuationSignal.FAIR
            nrr_label = nrr_lookup["110_to_119"]["label"]
        elif nrr_pct >= 1.00:
            nrr_signal = ValuationSignal.FAIR
            nrr_label = nrr_lookup["100_to_109"]["label"]
        elif nrr_pct >= 0.80:
            nrr_signal = ValuationSignal.WEAK
            nrr_label = nrr_lookup["80_to_99"]["label"]
        else:
            nrr_signal = ValuationSignal.WARNING
            nrr_label = nrr_lookup["below_80"]["label"]

        flags.append(ScorecardFlag(
            metric="Net Revenue Retention",
            value=f"{nrr_pct:.0%}",
            signal=nrr_signal,
            benchmark=nrr_label,
            commentary="The single most powerful valuation driver for SaaS. Below 100% = erosion; above 120% = expansion engine.",
        ))

    # --- Team ---
    team_signal = ValuationSignal.FAIR
    if team.prior_exits >= 1 or (team.domain_experts and team.repeat_founder):
        team_signal = ValuationSignal.STRONG
    elif not team.technical_cofounder:
        team_signal = ValuationSignal.WEAK
    flags.append(ScorecardFlag(
        metric="Team Quality",
        value="Prior exit" if team.prior_exits >= 1 else ("Domain expert" if team.domain_experts else "Standard"),
        signal=team_signal,
        benchmark="Qualitative team assumptions; no independently established valuation premium",
        commentary="Team is the dominant variable at pre-seed. Prior exits, domain expertise, and technical depth matter most.",
    ))

    # --- TAM ---
    tam = inp.market.tam_usd_billions
    tam_signal = ValuationSignal.STRONG if tam >= 10 else (ValuationSignal.FAIR if tam >= 1 else ValuationSignal.WARNING)
    flags.append(ScorecardFlag(
        metric="Total Addressable Market",
        value=f"${tam:.0f}B",
        signal=tam_signal,
        benchmark="VC threshold: $1B+ TAM minimum; $10B+ for top-tier institutional seed",
        commentary="Market ceiling limits valuation upside. Even with 100% capture, the math needs to support 10x fund returns.",
    ))

    # Reference context does not imply company quality or pricing power.
    p50 = vdata.get('valuation_p50')
    if p50:
        flags.append(ScorecardFlag(metric='Model reference', value=f'${blended:.1f}M',
            signal=ValuationSignal.FAIR, benchmark=f'Assumed stage/sector midpoint ${p50:.1f}M',
            commentary='Reference assumptions are not observed market percentiles. Evaluate the actual ask separately.'))

    # --- Runway ---
    if t.monthly_burn_rate > 0:
        runway_months = t.cash_on_hand / t.monthly_burn_rate
        runway_signal = ValuationSignal.STRONG if runway_months >= 18 else (ValuationSignal.FAIR if runway_months >= 12 else ValuationSignal.WARNING)
        flags.append(ScorecardFlag(
            metric="Current Runway",
            value=f"{runway_months:.0f} months",
            signal=runway_signal,
            benchmark="18+ months post-close is the standard investor expectation",
            commentary="Short runway limits negotiating leverage. Raise when you have 12+ months remaining.",
        ))

    return flags


# ---------------------------------------------------------------------------
# Verdict assignment
# ---------------------------------------------------------------------------

def _assign_verdict(blended: float, vdata: dict, warnings: list[str], ask=None, basis='pre_money'):
    if ask is None:
        return ValuationVerdict.NOT_ASSESSED, 'Price not assessed — enter an ask or SAFE cap', 'Company evidence and indicated value are shown separately. No conclusion about fundraising price is implied.'
    if basis == 'safe_cap':
        median = vdata.get('safe_cap_median')
        if not median:
            return ValuationVerdict.NOT_ASSESSED, 'No compatible SAFE cap reference', 'A SAFE cap cannot be compared directly with priced-round pre-money valuations.'
        high = median * 1.5
    else:
        median, high = vdata.get('valuation_p50'), vdata.get('valuation_p75')
    if not median or not high:
        return ValuationVerdict.NOT_ASSESSED, 'Insufficient comparable evidence', 'No compatible reference is available for this price basis.'
    if ask > high:
        return ValuationVerdict.STRETCHED, 'Ask exceeds the reference range', f'Your ${ask:.1f}M ask exceeds the ${high:.1f}M reference. This is an assumption-based comparison, not an observed market percentile.'
    return ValuationVerdict.FAIR, 'Ask is within or below the reference range', 'Price positioning is separate from company quality and financing feasibility. References may be inherited assumptions.'


# ---------------------------------------------------------------------------
# Method blending
# ---------------------------------------------------------------------------

def _compute_method_blend(
    inp: StartupInput,
    vdata: dict,
    ai_params: AIParameterSet,
    warnings: Optional[list[str]] = None,
    notes: Optional[list[str]] = None,
) -> tuple[list[ValuationMethodResult], float, float, float]:
    """
    Run the four valuation methods under the given parameter set and blend
    them. The blended valuation is STRICTLY the weighted average of the
    applicable method results — there is no post-blend scalar. Any AI-native
    premium emerges from the parameter-level calibration inside the methods.

    Pass `warnings`/`notes` as None for counterfactual runs (e.g. the
    standard-parameter blend used for reporting) to avoid duplicate messages.

    Returns (method_results, blended, range_low, range_high).
    """
    notes_list = notes if notes is not None else []

    berkus = _run_berkus(inp, vdata, ai_params.berkus_caps)
    scorecard = _run_scorecard(inp, vdata, warnings, ai_params.scorecard_weights)
    rfs = _run_rfs(inp, vdata, warnings, ai_params.rfs_step_values)
    arr_mult = _run_arr_multiple(inp, vdata, ai_params.arr_multiple_uplift, notes_list)

    method_results = [berkus, scorecard, rfs, arr_mult]
    applicable = [m for m in method_results if m.applicable and m.indicated_value is not None]

    # Determine weighting: the ARR multiple's weight ramps in with ARR magnitude
    arr = inp.traction.annual_recurring_revenue or (inp.traction.monthly_recurring_revenue * 12)

    if not applicable:
        # Fallback to benchmark median
        blended = _get_vertical_baseline(vdata, inp.fundraise.stage)
        if warnings is not None:
            warnings.append("Insufficient inputs for method-based valuation — using vertical median as fallback.")
        notes_list.append("Increase input detail (team, traction, market size) for a more precise output.")
    else:
        if arr > 0 and arr_mult.applicable:
            # ARR multiple is primary once revenue is meaningful; its weight
            # ramps from 0 to the full 65% as ARR approaches the vertical's
            # arr_required_min (fallback $1M), so a first few dollars of
            # revenue can never crater a pre-revenue valuation.
            pre_revenue_values = [
                m.indicated_value for m in [berkus, scorecard, rfs]
                if m.applicable and m.indicated_value is not None
            ]
            if pre_revenue_values:
                pre_rev_avg = sum(pre_revenue_values) / len(pre_revenue_values)
                ramp_denominator = max(float(vdata.get("arr_required_min") or 1.0), 1.0)
                ramp = arr / (arr + ramp_denominator)
                arr_weight = policy('arr_weight_max') * ramp
                blended = arr_mult.indicated_value * arr_weight + pre_rev_avg * (1 - arr_weight)
                notes_list.append(
                    f"ARR multiple weighted {arr_weight:.0%} (weight ramps with ARR toward the full "
                    f"65% asymptotically; half that weight at ${ramp_denominator:.1f}M ARR); Berkus/Scorecard/RFS average weighted "
                    f"{1 - arr_weight:.0%}."
                )
            else:
                blended = arr_mult.indicated_value
                notes_list.append("ARR multiple is sole applicable method.")
        else:
            # Pre-revenue: average of applicable pre-revenue methods
            values = [m.indicated_value for m in [berkus, scorecard, rfs] if m.applicable and m.indicated_value is not None]
            blended = sum(values) / len(values)
            notes_list.append(f"Blended average of {len(values)} applicable pre-revenue methods.")

    if applicable:
        arr_result = next((m for m in applicable if m.method_name == 'arr_multiple'), None)
        qualitative = [m for m in applicable if m.method_name != 'arr_multiple']
        aw = (policy('arr_weight_max') * arr / (arr + max(float(vdata.get('arr_required_min') or 1), 1))
              if arr_result and qualitative else 1.0 if arr_result else 0.0)
        for m in applicable:
            m.blend_weight = aw if m is arr_result else (1-aw) / len(qualitative)
            m.weighted_contribution = m.blend_weight * m.indicated_value

    # Range from applicable methods
    low_vals = [m.value_low for m in applicable if m.value_low is not None]
    high_vals = [m.value_high for m in applicable if m.value_high is not None]
    range_low = min(low_vals) if low_vals else blended * 0.7
    range_high = max(high_vals) if high_vals else blended * 1.5

    return method_results, blended, range_low, range_high


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

@evidence_analysis
def run_startup_valuation(inp: StartupInput) -> StartupValuationOutput:
    """
    Full startup valuation pipeline.
    Returns StartupValuationOutput with all method results and blended value.
    """
    stage = inp.fundraise.stage
    vertical = inp.fundraise.vertical
    vdata = _get_vertical_data(vertical, stage)

    warnings: list[str] = []
    notes: list[str] = []

    # Input consistency checks
    t = inp.traction
    if t.monthly_recurring_revenue > 0 and t.annual_recurring_revenue > 0:
        implied_arr = t.monthly_recurring_revenue * 12
        if abs(implied_arr - t.annual_recurring_revenue) / t.annual_recurring_revenue > 0.20:
            warnings.append(
                f"MRR × 12 (${implied_arr:.2f}M) differs from reported ARR "
                f"(${t.annual_recurring_revenue:.2f}M) by more than 20% — check for inconsistent "
                "revenue inputs. The engine uses reported ARR."
            )
    if t.monthly_burn_rate == 0 and t.cash_on_hand == 0:
        warnings.append(
            "Burn rate and cash on hand not provided — runway-dependent scores were set to "
            "neutral rather than best-case. Add burn and cash data for a more accurate valuation."
        )

    # Resolve the AI-native parameter calibration (inputs-up matrix). For
    # non-AI-native companies, zero scores, and frozen_on verticals this
    # returns the standard parameter set (applied=False).
    ai_params = get_ai_parameters(
        inp.fundraise.is_ai_native,
        inp.fundraise.ai_native_score,
        vertical.value,
    )

    # Run all four methods and blend. The blended valuation is strictly the
    # weighted average of the applicable method results — any AI-native
    # premium is EMERGENT from the parameter-level calibration, never a
    # post-blend scalar.
    arr = inp.traction.annual_recurring_revenue or (inp.traction.monthly_recurring_revenue * 12)
    if arr > 0 and not t.has_revenue:
        warnings.append(
            "Recurring revenue was provided but has_revenue is false — the ARR multiple method "
            "was gated off. Set has_revenue=true to include it."
        )
    method_results, blended, range_low, range_high = _compute_method_blend(
        inp, vdata, ai_params, warnings, notes,
    )

    # --- AI calibration reporting: counterfactual standard-parameter blend ---
    # blended_before_ai is the SAME blend recomputed with standard parameters;
    # the emergent premium is the ratio between the two blends minus one.
    blended_before_ai: Optional[float] = None
    ai_premium_multiplier: Optional[float] = None
    ai_premium_context: Optional[str] = None

    if ai_params.applied:
        _, standard_blended, _, _ = _compute_method_blend(inp, vdata, AIParameterSet())
        blended_before_ai = standard_blended
        if standard_blended > 0:
            ai_premium_multiplier = blended / standard_blended - 1.0
        ai_premium_context = ai_params.context
        notes.append(ai_params.context)
    elif inp.fundraise.is_ai_native and ai_params.context:
        # Frozen-on verticals (and matrix errors): explain why no calibration applied
        ai_premium_context = ai_params.context
        notes.append(ai_params.context)

    # Invariant: range_low <= blended <= range_high (clamp + warn as safety net)
    if blended < range_low:
        warnings.append(
            f"Blended valuation ${blended:.1f}M fell below the computed range low "
            f"${range_low:.1f}M — range widened to include it."
        )
        range_low = blended
    if blended > range_high:
        warnings.append(
            f"Blended valuation ${blended:.1f}M exceeded the computed range high "
            f"${range_high:.1f}M — range widened to include it."
        )
        range_high = blended

    safe_cap = inp.fundraise.safe_valuation_cap if inp.fundraise.instrument == InstrumentType.SAFE else None
    if inp.fundraise.instrument == InstrumentType.SAFE and safe_cap is None:
        notes.append('No explicit SAFE cap supplied. A model pre-money estimate is not a recommended SAFE cap.')

    # Deal-mechanics basis: the deal happens at the preparer's ask when one is
    # provided — the model midpoint is only a fallback anchor. The blended
    # valuation and calibrated range are never affected by the ask.
    ask = inp.fundraise.pre_money_valuation_ask
    basis_is_ask = ask is not None and ask > 0
    basis_pre_money = float(ask) if basis_is_ask else blended
    if safe_cap is not None:
        notes.append(f'Dilution is illustrated at the explicitly supplied ${safe_cap:.1f}M {inp.fundraise.safe_type.replace("_", "-")} SAFE cap. It is separate from the pre-money model indication.')
    elif basis_is_ask:
        notes.append(
            f"Deal mechanics (implied dilution, current-round dilution, financing feasibility) are priced at "
            f"the preparer's ask of ${basis_pre_money:.1f}M pre-money, not the model midpoint (${blended:.1f}M). "
            "Projected future rounds remain anchored to reference assumptions."
        )
    else:
        notes.append(
            f"No preparer ask provided — deal mechanics are priced at the model midpoint (${blended:.1f}M pre-money)."
        )

    # Implied dilution
    if safe_cap is not None:
        basis_is_ask = True
        basis_pre_money = max(0, safe_cap - inp.fundraise.raise_amount) if inp.fundraise.safe_type == 'post_money' else safe_cap
    post_money = basis_pre_money + inp.fundraise.raise_amount
    implied_dilution = inp.fundraise.raise_amount / post_money if post_money > 0 else 0

    # Warnings
    if implied_dilution > 0.25:
        warnings.append(
            f"Implied dilution of {implied_dilution:.0%} is above the 25% threshold that many founders consider their limit at {stage.value.replace('_', ' ')}. "
            "Consider raising the valuation or reducing the raise amount."
        )
    if arr > 0 and inp.traction.net_revenue_retention < 1.0:
        warnings.append(
            f"NRR of {inp.traction.net_revenue_retention:.0%} is below 100% — you are losing more from churn than you gain from expansion. "
            "This is a top-3 concern for institutional investors and will compress your ARR multiple."
        )
    if blended > vdata.get("valuation_p75", 9999):
        # Use the requested stage's down-round rate where the benchmark has
        # one; otherwise fall back to the seed rate and say so.
        stage_medians = _BENCHMARKS["market_wide_medians"].get(stage.value, {})
        down_round_pct = stage_medians.get("down_round_pct")
        down_round_proxy_note = ""
        if down_round_pct is None:
            down_round_pct = _BENCHMARKS["market_wide_medians"]["seed"]["down_round_pct"]
            down_round_proxy_note = " (seed-stage rate used as proxy — no stage-specific data)"
        warnings.append(
            f"Model indication exceeds the inherited upper reference for your vertical. The {down_round_pct:.0%} down-round rate "
            f"is an inherited assumption{down_round_proxy_note}, not a verified current statistic. "
            "an aggressive cap today raises the next-round bar significantly."
        )

    # Dilution modeling — current round priced at the deal-mechanics basis
    # (ask when provided); projected rounds anchored to the model midpoint.
    dilution_scenarios = _build_dilution_scenarios(inp, basis_pre_money, blended)
    safe_conversion = _build_safe_conversion(inp, basis_pre_money, blended) if safe_cap is not None else None


    # An ask above the market-projected next round means the projection is a
    # down round relative to this deal price — flag it plainly.
    if basis_is_ask and len(dilution_scenarios) > 1:
        current, next_round = dilution_scenarios[0], dilution_scenarios[1]
        if next_round.pre_money < current.post_money:
            warnings.append(
                f"The market-projected {next_round.round_label.replace(' (projected)', '')} pre-money "
                f"(${next_round.pre_money:.1f}M) is below the current post-money at your ask "
                f"(${current.post_money:.1f}M) — the next round would be a down round unless "
                "performance outruns the benchmarks."
            )

    # Investor scorecard
    investor_scorecard = _build_scorecard(inp, blended, vdata)

    # Verdict
    price_ask = inp.fundraise.safe_valuation_cap if inp.fundraise.instrument == InstrumentType.SAFE else ask
    price_basis = 'safe_cap' if inp.fundraise.instrument == InstrumentType.SAFE else 'pre_money'
    price_reference = None
    if price_basis == 'safe_cap' and inp.fundraise.safe_type == 'post_money':
        match = resolve('safe_cap', 'post_money_safe_cap', stage=stage.value,
            geography='us' if inp.fundraise.geography.value != 'international' else 'international',
            size=inp.fundraise.raise_amount)
        if match['record']:
            price_reference = match['record']
    price_data = dict(vdata)
    if price_reference:
        price_data['safe_cap_median'] = price_reference.value
    verdict, headline, subtext = _assign_verdict(blended, price_data, warnings, price_ask, price_basis)

    # Percentile label
    p50 = vdata.get("valuation_p50", 0)
    p25 = vdata.get("valuation_p25", 0)
    p75 = vdata.get("valuation_p75", 0)
    p95 = vdata.get("valuation_p95", 0)
    if blended >= (p95 or 9999): pct_label = "top 5%"
    elif blended >= (p75 or 9999): pct_label = "top quartile (P75–P95)"
    elif blended >= (p50 or 9999): pct_label = "top half (P50–P75)"
    elif blended >= (p25 or 9999): pct_label = "bottom half (P25–P50)"
    else: pct_label = "bottom quartile (below P25)"

    pct_label = 'Reference band only — observed market percentile unavailable'

    traction_bar = vdata.get("traction_bar", "No traction bar available for this vertical/stage.")

    # Round timing signal
    round_timing = _compute_round_timing(inp, vdata)

    return StartupValuationOutput(
        company_name=inp.company_name,
        stage=stage,
        vertical=vertical,
        blended_valuation=round(blended, 2),
        valuation_range_low=round(range_low, 2),
        valuation_range_high=round(range_high, 2),
        recommended_safe_cap=safe_cap,
        implied_dilution=round(implied_dilution, 4),
        dilution_basis="preparer_ask" if basis_is_ask else "model_midpoint",
        dilution_basis_pre_money=round(basis_pre_money, 2),
        method_results=method_results,
        blend_adjustment=round(round(blended, 2)-sum(m.weighted_contribution for m in method_results), 8),
        price_assessment={'ask': price_ask, 'basis': price_basis, 'status': verdict.value, 'reference_id': price_reference.id if price_reference else None},
        company_evidence=[f'{inp.traction.paying_customer_count} paying customers reported',
                          f'Product stage: {inp.product.stage.value}',
                          'Qualitative inputs are user reported; not independent verification.'],
        benchmark_p25=vdata.get("valuation_p25", 0),
        benchmark_p50=vdata.get("valuation_p50", 0),
        benchmark_p75=vdata.get("valuation_p75", 0),
        benchmark_p95=vdata.get("valuation_p95", 0),
        percentile_in_market=pct_label,
        dilution_scenarios=dilution_scenarios,
        safe_conversion=safe_conversion,
        investor_scorecard=investor_scorecard,
        traction_bar="Illustrative stage assumptions: " + traction_bar.replace("top quartile", "upper model reference"),
        verdict=verdict,
        verdict_headline=headline,
        verdict_subtext=subtext,
        warnings=warnings,
        computation_notes=notes,
        vertical_benchmarks=vdata,
        ai_modifier_applied=ai_params.applied,
        ai_premium_multiplier=round(ai_premium_multiplier, 6) if ai_premium_multiplier is not None else None,
        ai_premium_context=ai_premium_context,
        blended_before_ai=round(blended_before_ai, 2) if blended_before_ai is not None else None,
        ai_native_score=inp.fundraise.ai_native_score if inp.fundraise.is_ai_native else None,
        round_timing=round_timing,
    )


# ---------------------------------------------------------------------------
# Startup Valuation Sensitivity Analysis
# ---------------------------------------------------------------------------

def run_startup_sensitivity(inp: StartupInput) -> dict:
    """
    Show founders how key inputs move the valuation needle.

    Runs the engine multiple times with perturbed inputs to build
    a sensitivity table showing the impact of each key lever.

    Returns a dict with:
    - base_valuation: the unmodified blended valuation
    - sensitivities: list of {input_name, low_value, base_value, high_value,
                              low_valuation, base_valuation, high_valuation,
                              impact_low_pct, impact_high_pct}
    - most_impactful: name of the input with the largest swing

    This is the "what moves the needle" view that founders ask for.
    """
    base_output = run_startup_valuation(inp)
    base_val = base_output.blended_valuation

    sensitivities = []

    # Define perturbations: (name, getter, setter_low, setter_high)
    # Each returns a modified copy of the input
    perturbations = []

    # 1. ARR (if applicable)
    arr = inp.traction.annual_recurring_revenue or (inp.traction.monthly_recurring_revenue * 12)
    if arr > 0:
        perturbations.append({
            "name": "ARR",
            "field": "Annual Recurring Revenue",
            "base": arr,
            "low": arr * 0.5,
            "high": arr * 2.0,
            "apply": lambda v, i=inp: _perturb_arr(i, v),
        })

    # 2. MoM Growth Rate
    if inp.traction.mom_growth_rate > 0:
        base_growth = inp.traction.mom_growth_rate
        perturbations.append({
            "name": "MoM Growth",
            "field": "Month-over-Month Growth Rate",
            "base": base_growth,
            "low": max(0.0, base_growth * 0.5),
            "high": min(1.0, base_growth * 2.0),
            "apply": lambda v, i=inp: _perturb_mom_growth(i, v),
        })

    # 3. Net Revenue Retention
    if inp.traction.has_revenue:
        base_nrr = inp.traction.net_revenue_retention
        perturbations.append({
            "name": "NRR",
            "field": "Net Revenue Retention",
            "base": base_nrr,
            "low": max(0.5, base_nrr - 0.20),
            "high": min(2.0, base_nrr + 0.20),
            "apply": lambda v, i=inp: _perturb_nrr(i, v),
        })

    # 4. TAM
    base_tam = inp.market.tam_usd_billions
    perturbations.append({
        "name": "TAM",
        "field": "Total Addressable Market ($B)",
        "base": base_tam,
        "low": base_tam * 0.5,
        "high": base_tam * 2.0,
        "apply": lambda v, i=inp: _perturb_tam(i, v),
    })

    # 5. Raise Amount
    base_raise = inp.fundraise.raise_amount
    perturbations.append({
        "name": "Raise Amount",
        "field": "Target Raise ($M)",
        "base": base_raise,
        "low": base_raise * 0.5,
        "high": base_raise * 2.0,
        "apply": lambda v, i=inp: _perturb_raise(i, v),
    })

    # 6. Team quality (repeat founder toggle)
    if not inp.team.repeat_founder:
        perturbations.append({
            "name": "Repeat Founder",
            "field": "Repeat Founder Status",
            "base": 0,
            "low": 0,
            "high": 1,
            "apply": lambda v, i=inp: _perturb_repeat_founder(i, bool(v)),
        })

    # Run perturbations
    for p in perturbations:
        try:
            low_inp = p["apply"](p["low"])
            low_out = run_startup_valuation(low_inp)
            low_val = low_out.blended_valuation
        except Exception:
            low_val = base_val

        try:
            high_inp = p["apply"](p["high"])
            high_out = run_startup_valuation(high_inp)
            high_val = high_out.blended_valuation
        except Exception:
            high_val = base_val

        impact_low = (low_val - base_val) / base_val if base_val > 0 else 0.0
        impact_high = (high_val - base_val) / base_val if base_val > 0 else 0.0

        sensitivities.append({
            "input_name": p["name"],
            "input_field": p["field"],
            "low_value": round(p["low"], 4),
            "base_value": round(p["base"], 4),
            "high_value": round(p["high"], 4),
            "low_valuation": round(low_val, 2),
            "base_valuation": round(base_val, 2),
            "high_valuation": round(high_val, 2),
            "impact_low_pct": round(impact_low, 4),
            "impact_high_pct": round(impact_high, 4),
            "total_swing": round(high_val - low_val, 2),
        })

    # Sort by total swing (most impactful first)
    sensitivities.sort(key=lambda s: s["total_swing"], reverse=True)
    most_impactful = sensitivities[0]["input_name"] if sensitivities else None

    return {
        "company_name": inp.company_name,
        "base_valuation": round(base_val, 2),
        "sensitivities": sensitivities,
        "most_impactful": most_impactful,
        "note": "Each row shows the blended valuation when that single input is changed to the low or high value, with all other inputs held constant.",
    }


def _perturb_arr(inp: StartupInput, new_arr: float) -> StartupInput:
    data = inp.model_dump()
    data["traction"]["annual_recurring_revenue"] = new_arr
    data["traction"]["monthly_recurring_revenue"] = new_arr / 12.0
    return StartupInput(**data)


def _perturb_mom_growth(inp: StartupInput, new_growth: float) -> StartupInput:
    data = inp.model_dump()
    data["traction"]["mom_growth_rate"] = new_growth
    return StartupInput(**data)


def _perturb_nrr(inp: StartupInput, new_nrr: float) -> StartupInput:
    data = inp.model_dump()
    data["traction"]["net_revenue_retention"] = new_nrr
    return StartupInput(**data)


def _perturb_tam(inp: StartupInput, new_tam: float) -> StartupInput:
    data = inp.model_dump()
    data["market"]["tam_usd_billions"] = new_tam
    return StartupInput(**data)


def _perturb_raise(inp: StartupInput, new_raise: float) -> StartupInput:
    data = inp.model_dump()
    data["fundraise"]["raise_amount"] = max(0.01, new_raise)
    return StartupInput(**data)


def _perturb_repeat_founder(inp: StartupInput, is_repeat: bool) -> StartupInput:
    data = inp.model_dump()
    data["team"]["repeat_founder"] = is_repeat
    return StartupInput(**data)
