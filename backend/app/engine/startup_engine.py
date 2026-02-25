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

import json
import logging
import math
import os
from typing import Optional

from .ai_modifier import AIModifierInput, AIModifierOutput, apply_ai_modifier
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

def _load_benchmarks() -> dict:
    with open(_DATA_PATH, "r") as f:
        return json.load(f)

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
    Uses vertical p50 when available; falls back to market-wide pre-seed median.
    This ensures defense tech, AI infra, etc. are anchored to their own comps
    rather than the generic $7.7M market median.
    """
    market_median = _BENCHMARKS["market_wide_medians"]["pre_seed"]["valuation_median"]
    vertical_p50 = vdata.get("valuation_p50")
    if vertical_p50 and vertical_p50 > 0:
        return float(vertical_p50)
    return market_median


# ---------------------------------------------------------------------------
# Method 1: Berkus Method
# ---------------------------------------------------------------------------

def _score_berkus_dimension(
    label: str,
    signal: bool | float,
    weight: float = 1.0,
) -> float:
    """Return a 0–1 score for a single Berkus dimension."""
    if isinstance(signal, bool):
        return 1.0 if signal else 0.4  # 0.4 = partial credit for presence alone
    return float(max(0.0, min(1.0, signal)))


def _run_berkus(inp: StartupInput, vdata: dict) -> ValuationMethodResult:
    """
    Berkus Method: 5 factors × up to 20% of regional median = max valuation.
    Updated formulation: each dimension = score × 20% × regional_median.
    """
    # Regional baseline
    regional_premium = _get_regional_premium(inp.fundraise.geography.value)
    vertical_baseline = _get_vertical_baseline(vdata, inp.fundraise.stage)
    regional_median = vertical_baseline * regional_premium

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

    # Calculate indicated value
    factor_max = 0.20 * regional_median  # max per dimension
    indicated = (s_idea + s_management + s_prototype + s_relationships + s_rollout) * factor_max
    value_low = indicated * 0.7
    value_high = indicated * 1.4

    return ValuationMethodResult(
        method_name="berkus",
        method_label="Berkus Method",
        indicated_value=round(indicated, 2),
        value_low=round(value_low, 2),
        value_high=round(value_high, 2),
        applicable=inp.fundraise.stage == StartupStage.PRE_SEED,
        rationale=(
            f"5 dimensions scored against regional median of ${regional_median:.1f}M "
            f"({inp.fundraise.geography.value.replace('_', ' ').title()} premium {regional_premium:.1f}x). "
            f"Scores: Idea {s_idea:.0%}, Team {s_management:.0%}, Product {s_prototype:.0%}, "
            f"Relationships {s_relationships:.0%}, Sales {s_rollout:.0%}."
        ),
        inputs_used={
            "regional_median": regional_median,
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

def _run_scorecard(inp: StartupInput, vdata: dict) -> ValuationMethodResult:
    """
    Scorecard Method: 7 weighted factors vs. regional comparable.
    Weighted sum (50–150% range) × regional median.
    """
    regional_premium = _get_regional_premium(inp.fundraise.geography.value)
    vertical_baseline = _get_vertical_baseline(vdata, inp.fundraise.stage)
    regional_median = vertical_baseline * regional_premium

    weights = _BENCHMARKS["scorecard_weights"]

    if inp.scorecard_scores:
        scores = inp.scorecard_scores
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
        runway = (inp.traction.cash_on_hand / inp.traction.monthly_burn_rate) if inp.traction.monthly_burn_rate > 0 else 24
        if runway >= 18: financing_score = 1.2
        elif runway >= 12: financing_score = 1.0
        elif runway >= 6: financing_score = 0.8
        else: financing_score = 0.6

        # Other factors
        other_score = 1.0
        if prod.regulatory_clearance: other_score = 1.2
        if inp.fundraise.geography.value in ["bay_area", "new_york"]: other_score = min(1.5, other_score + 0.1)

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
            "scores": {k: round(v, 2) for k, v in scores.items()},
        },
    )


# ---------------------------------------------------------------------------
# Method 3: Risk Factor Summation
# ---------------------------------------------------------------------------

def _run_rfs(inp: StartupInput, vdata: dict) -> ValuationMethodResult:
    """
    Risk Factor Summation: 12 categories, each -2 to +2.
    Each step = ±$250K (±$0.25M). Starting baseline = scorecard indicated value.
    """
    regional_premium = _get_regional_premium(inp.fundraise.geography.value)
    vertical_baseline = _get_vertical_baseline(vdata, inp.fundraise.stage)
    base = vertical_baseline * regional_premium
    # Scale adjustment per step proportionally to vertical baseline.
    # The benchmark $0.25M/step was calibrated for the ~$7.7M market median.
    # For defense tech ($10M+) or AI infra ($10M+), flat $0.25M is negligible;
    # scaling keeps each step at ~3.2% of baseline regardless of vertical.
    market_median = _BENCHMARKS["market_wide_medians"]["pre_seed"]["valuation_median"]
    raw_adj = _BENCHMARKS["risk_factor_summation"]["adjustment_per_step_usd_millions"]
    adj_per_step = raw_adj * (base / market_median) if market_median > 0 else raw_adj

    if inp.risk_factor_scores:
        rfs = inp.risk_factor_scores
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
        runway = (t.cash_on_hand / t.monthly_burn_rate) if t.monthly_burn_rate > 0 else 18
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

    total_adjustment = sum(rfs.values()) * adj_per_step
    indicated = base + total_adjustment
    indicated = max(0.5, indicated)  # floor at $500K

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
            f"(${adj_per_step:.2f}M per step)."
        ),
        inputs_used={
            "base": base,
            "adjustment_per_step": adj_per_step,
            "scores": rfs,
            "total_adjustment": round(total_adjustment, 2),
        },
    )


# ---------------------------------------------------------------------------
# Method 4: ARR Multiple
# ---------------------------------------------------------------------------

def _run_arr_multiple(inp: StartupInput, vdata: dict) -> ValuationMethodResult:
    """
    ARR Multiple method. Uses NRR and growth rate to select the appropriate multiple band.
    Only applicable when ARR > 0.
    """
    t = inp.traction
    arr = t.annual_recurring_revenue or (t.monthly_recurring_revenue * 12)

    if arr <= 0:
        return ValuationMethodResult(
            method_name="arr_multiple",
            method_label="ARR Multiple",
            indicated_value=None,
            value_low=None,
            value_high=None,
            applicable=False,
            rationale="No ARR reported — ARR multiple method not applicable.",
            inputs_used={"arr": 0},
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

    base_multiple = p50_multiple

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

    adjusted_multiple = base_multiple * (1 + nrr_adj + growth_adj + gm_adj + burn_adj)
    adjusted_multiple = max(1.0, adjusted_multiple)

    indicated = arr * adjusted_multiple
    value_low = arr * (p25_multiple or adjusted_multiple * 0.7)
    value_high = arr * (p75_multiple or adjusted_multiple * 1.4)

    # Rule of 40
    yoy_growth_pct = mom * 12 * 100 if mom else 0
    ebitda_margin_pct = (1 - inp.traction.gross_margin) * -100  # rough proxy
    rule_of_40 = yoy_growth_pct + ebitda_margin_pct

    return ValuationMethodResult(
        method_name="arr_multiple",
        method_label="ARR Multiple",
        indicated_value=round(indicated, 2),
        value_low=round(value_low, 2),
        value_high=round(value_high, 2),
        applicable=True,
        rationale=(
            f"ARR ${arr:.2f}M × {adjusted_multiple:.1f}x adjusted multiple "
            f"(base {base_multiple:.0f}x, NRR {nrr:.0%} adj {nrr_adj:+.0%}, "
            f"growth adj {growth_adj:+.0%}, GM adj {gm_adj:+.0%})."
        ),
        inputs_used={
            "arr": arr,
            "base_multiple_p50": base_multiple,
            "adjusted_multiple": round(adjusted_multiple, 2),
            "nrr": nrr,
            "mom_growth": mom,
            "gross_margin": gm,
            "rule_of_40_approx": round(rule_of_40, 1),
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

def _build_dilution_scenarios(
    inp: StartupInput,
    blended_pre_money: float,
) -> list[DilutionScenario]:
    """
    Project dilution across the current round and the next two typical rounds.
    """
    raise_amount = inp.fundraise.raise_amount
    stage = inp.fundraise.stage
    scenarios: list[DilutionScenario] = []

    # Starting ownership
    existing_safe_pct = 0.0
    if inp.fundraise.existing_safe_stack > 0 and blended_pre_money > 0:
        existing_safe_pct = min(0.30, inp.fundraise.existing_safe_stack / blended_pre_money)

    founder_pct = 1.0 - existing_safe_pct

    # Current round
    post_money = blended_pre_money + raise_amount
    inv_pct = raise_amount / post_money
    new_founder_pct = founder_pct * (1 - inv_pct)

    scenarios.append(DilutionScenario(
        round_label=f"Current ({stage.value.replace('_', ' ').title()})",
        pre_money=round(blended_pre_money, 2),
        raise_amount=round(raise_amount, 2),
        post_money=round(post_money, 2),
        investor_ownership_pct=round(inv_pct, 4),
        founder_ownership_pct_before=round(founder_pct, 4),
        founder_ownership_pct_after=round(new_founder_pct, 4),
        dilution_this_round=round(inv_pct, 4),
    ))

    founder_pct = new_founder_pct

    # Next round projections based on typical market data
    next_rounds: list[tuple[str, float, float, float]] = []  # (label, pre_money, raise, option_pool)
    series_a_median = _BENCHMARKS["market_wide_medians"]["series_a"]["valuation_pre_money_median"]
    if stage == StartupStage.PRE_SEED:
        seed_median = _BENCHMARKS["market_wide_medians"]["seed"]["valuation_pre_money_median"]
        # Projected Seed pre-money must exceed current post-money (step-up floor: 1.5x post-money)
        seed_pre = max(seed_median, post_money * 1.5)
        seed_post = seed_pre + 3.0
        # Projected Series A pre-money must exceed projected Seed post-money (floor: 2x seed post)
        series_a_pre = max(series_a_median, seed_post * 2.0)
        next_rounds = [
            ("Seed (projected)", seed_pre, 3.0, 0.10),
            ("Series A (projected)", series_a_pre, 10.0, 0.10),
        ]
    elif stage == StartupStage.SEED:
        # Projected Series A pre-money must exceed current post-money (floor: 2x post-money)
        series_a_pre = max(series_a_median, post_money * 2.0)
        next_rounds = [
            ("Series A (projected)", series_a_pre, 10.0, 0.10),
        ]

    for label, next_pre, next_raise, option_pool in next_rounds:
        # Option pool shuffle: pool comes out of pre-money
        pre_with_pool = next_pre  # pool already baked in to market medians
        pool_dilution = option_pool  # applied to existing shareholders
        post = pre_with_pool + next_raise
        inv_pct = next_raise / post
        # Founder diluted by option pool first, then investor
        founder_after_pool = founder_pct * (1 - pool_dilution)
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
    blended_pre_money: float,
) -> Optional[SAFEConversionSummary]:
    """
    Model how the current SAFE converts at the next hypothetical priced round.
    """
    if inp.fundraise.instrument != InstrumentType.SAFE:
        return None

    cap = inp.fundraise.pre_money_valuation_ask or blended_pre_money
    discount = inp.fundraise.safe_discount
    raise_amount = inp.fundraise.raise_amount

    # At conversion: investor gets shares at the LOWER of (cap price) or (discount price)
    implied_ownership = raise_amount / (cap + raise_amount)

    note_parts = [f"SAFE of ${raise_amount:.2f}M with a ${cap:.1f}M valuation cap."]
    if discount > 0:
        note_parts.append(f"Includes {discount:.0%} discount on conversion price.")
    if inp.fundraise.has_mfn_clause:
        note_parts.append("MFN clause present — monitor any subsequent SAFE issuances.")
    if inp.fundraise.existing_safe_stack > 0:
        note_parts.append(
            f"${inp.fundraise.existing_safe_stack:.1f}M in existing SAFEs not yet converted — "
            "cumulative dilution at next priced round will be higher than this single instrument."
        )

    return SAFEConversionSummary(
        safe_amount=raise_amount,
        valuation_cap=cap,
        discount_rate=discount,
        conversion_price_at_cap=round(cap / 10.0, 4),  # illustrative; real calc needs share count
        implied_ownership_pct=round(implied_ownership, 4),
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
            metric="Burn Multiple",
            value=f"{burn_mult:.1f}x",
            signal=signal,
            benchmark=bm_label,
            commentary="Net ARR added per dollar burned. Below 1.5x is strong; above 2.5x is a Series A red flag.",
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
        benchmark="30% of Berkus/Scorecard weight; prior exit = immediate $1–5M premium",
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

    # --- Valuation vs. benchmark ---
    p25 = vdata.get("valuation_p25", 0)
    p75 = vdata.get("valuation_p75", 0)
    p50 = vdata.get("valuation_p50", 0)
    if blended and p50:
        if blended >= p75:
            vs_signal = ValuationSignal.WARNING
            vs_label = "Top quartile — above-average growth required to sustain at next round"
        elif blended >= p50:
            vs_signal = ValuationSignal.FAIR
            vs_label = "Median range — market-rate terms"
        elif blended >= p25:
            vs_signal = ValuationSignal.WEAK
            vs_label = "Bottom quartile — re-evaluate traction or team before raising"
        else:
            vs_signal = ValuationSignal.WARNING
            vs_label = "Below P25 — consider bridge round or additional milestones first"

        flags.append(ScorecardFlag(
            metric="Valuation vs. Benchmark",
            value=f"${blended:.1f}M",
            signal=vs_signal,
            benchmark=f"P25 ${p25:.0f}M | P50 ${p50:.0f}M | P75 ${p75:.0f}M ({inp.fundraise.vertical.value.replace('_', ' ')}, {stage.value.replace('_', ' ')})",
            commentary="Where your implied valuation sits within the Carta/PitchBook benchmark distribution for your vertical and stage.",
        ))

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

def _assign_verdict(
    blended: float,
    vdata: dict,
    warnings: list[str],
) -> tuple[ValuationVerdict, str, str]:
    p25 = vdata.get("valuation_p25", 0)
    p50 = vdata.get("valuation_p50", 0)
    p75 = vdata.get("valuation_p75", 0)

    if not p50:
        return ValuationVerdict.FAIR, "Indicative range computed", "Limited benchmarks available for this vertical/stage combination."

    if blended >= p75:
        return (
            ValuationVerdict.STRETCHED,
            "Above-market valuation — strong story required",
            f"Your indicated ${blended:.1f}M is in the top quartile for this vertical/stage (P75 = ${p75:.0f}M). "
            "This is achievable with an exceptional team or breakout traction, but requires ~3x ARR growth before the next round to avoid a flat or down round.",
        )
    elif blended >= p50:
        return (
            ValuationVerdict.STRONG,
            "Well-positioned at median to top-half range",
            f"Your indicated ${blended:.1f}M sits between the P50 (${p50:.0f}M) and P75 (${p75:.0f}M) for your vertical. "
            "You have pricing power. Standard terms apply.",
        )
    elif blended >= p25:
        return (
            ValuationVerdict.FAIR,
            "Market-rate — room to grow before raising",
            f"Your indicated ${blended:.1f}M is in the P25–P50 range (${p25:.0f}M–${p50:.0f}M). "
            "Consider adding 1–2 additional milestones to strengthen your position before committing to a cap.",
        )
    else:
        return (
            ValuationVerdict.AT_RISK,
            "Below-market — milestone first, then raise",
            f"Your indicated ${blended:.1f}M is below the P25 (${p25:.0f}M) for your vertical/stage. "
            "Focus on reaching a clear product or traction milestone before formalizing the round.",
        )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

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

    # Run all four methods
    berkus = _run_berkus(inp, vdata)
    scorecard = _run_scorecard(inp, vdata)
    rfs = _run_rfs(inp, vdata)
    arr_mult = _run_arr_multiple(inp, vdata)

    method_results = [berkus, scorecard, rfs, arr_mult]

    # Determine weighting: ARR multiple dominates once revenue exists
    arr = inp.traction.annual_recurring_revenue or (inp.traction.monthly_recurring_revenue * 12)
    applicable = [m for m in method_results if m.applicable and m.indicated_value is not None]

    if not applicable:
        # Fallback to benchmark median
        blended = vdata.get("valuation_p50") or _BENCHMARKS["market_wide_medians"]["pre_seed"]["valuation_median"]
        warnings.append("Insufficient inputs for method-based valuation — using vertical median as fallback.")
        notes.append("Increase input detail (team, traction, market size) for a more precise output.")
    else:
        if arr > 0 and arr_mult.applicable:
            # ARR multiple is primary; others are cross-checks
            pre_revenue_values = [
                m.indicated_value for m in [berkus, scorecard, rfs]
                if m.applicable and m.indicated_value is not None
            ]
            if pre_revenue_values:
                pre_rev_avg = sum(pre_revenue_values) / len(pre_revenue_values)
                blended = arr_mult.indicated_value * 0.65 + pre_rev_avg * 0.35
                notes.append("ARR multiple weighted 65%; Berkus/Scorecard/RFS average weighted 35%.")
            else:
                blended = arr_mult.indicated_value
                notes.append("ARR multiple is sole applicable method.")
        else:
            # Pre-revenue: average of applicable pre-revenue methods
            values = [m.indicated_value for m in [berkus, scorecard, rfs] if m.applicable and m.indicated_value is not None]
            blended = sum(values) / len(values)
            notes.append(f"Blended average of {len(values)} applicable pre-revenue methods.")

    # --- AI Modifier: apply graduated premium for AI-native startups ---
    blended_before_ai: Optional[float] = None
    ai_mod_output: Optional[AIModifierOutput] = None

    if inp.fundraise.is_ai_native:
        ai_mod_output = apply_ai_modifier(AIModifierInput(
            is_ai_native=True,
            ai_native_score=inp.fundraise.ai_native_score,
            vertical=inp.fundraise.vertical.value,
            blended_valuation=blended,
        ))
        if ai_mod_output.ai_modifier_applied:
            blended_before_ai = blended
            blended = ai_mod_output.blended_after_ai

    # Range from applicable methods
    low_vals = [m.value_low for m in applicable if m.value_low is not None]
    high_vals = [m.value_high for m in applicable if m.value_high is not None]
    range_low = min(low_vals) if low_vals else blended * 0.7
    range_high = max(high_vals) if high_vals else blended * 1.5

    # Recommended SAFE cap (slight premium on blended; market convention is ~10–20% above)
    safe_cap = None
    if inp.fundraise.instrument == InstrumentType.SAFE:
        safe_cap = round(blended * 1.15, 1)  # 15% premium on blended value is market convention
        notes.append(f"Recommended SAFE cap of ${safe_cap:.1f}M = blended value × 1.15x (standard market premium).")

    # Implied dilution
    post_money = blended + inp.fundraise.raise_amount
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
    market_med_down_round_pct = _BENCHMARKS["market_wide_medians"]["seed"]["down_round_pct"]
    if blended > vdata.get("valuation_p75", 9999):
        warnings.append(
            f"Valuation is above P75 for your vertical. Note that {market_med_down_round_pct:.0%} of all 2023–2025 rounds were down rounds — "
            "an aggressive cap today raises the next-round bar significantly."
        )

    # Dilution modeling
    dilution_scenarios = _build_dilution_scenarios(inp, blended)
    safe_conversion = _build_safe_conversion(inp, blended)

    # Investor scorecard
    investor_scorecard = _build_scorecard(inp, blended, vdata)

    # Verdict
    verdict, headline, subtext = _assign_verdict(blended, vdata, warnings)

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
        method_results=method_results,
        benchmark_p25=vdata.get("valuation_p25", 0),
        benchmark_p50=vdata.get("valuation_p50", 0),
        benchmark_p75=vdata.get("valuation_p75", 0),
        benchmark_p95=vdata.get("valuation_p95", 0),
        percentile_in_market=pct_label,
        dilution_scenarios=dilution_scenarios,
        safe_conversion=safe_conversion,
        investor_scorecard=investor_scorecard,
        traction_bar=traction_bar,
        verdict=verdict,
        verdict_headline=headline,
        verdict_subtext=subtext,
        warnings=warnings,
        computation_notes=notes,
        vertical_benchmarks=vdata,
        ai_modifier_applied=ai_mod_output.ai_modifier_applied if ai_mod_output else False,
        ai_premium_multiplier=ai_mod_output.ai_premium_multiplier if ai_mod_output else None,
        ai_premium_context=ai_mod_output.ai_premium_context if ai_mod_output else None,
        blended_before_ai=blended_before_ai,
        ai_native_score=inp.fundraise.ai_native_score if inp.fundraise.is_ai_native else None,
        round_timing=round_timing,
    )
