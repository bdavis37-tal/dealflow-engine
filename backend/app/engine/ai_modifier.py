"""
AI Valuation Parameter Calibration

Provides the inputs-up, parameter-level AI-native calibration matrix.
Instead of applying a post-blend scalar premium, the AI-native toggle now
shifts the PARAMETERS of the individual valuation methods (scorecard weights,
Berkus per-dimension caps, Risk Factor Summation step values, and the ARR
multiple) BEFORE blending. Any premium in the blended valuation is therefore
EMERGENT — it arises from the calibrated parameters, not from a multiplier.

Calibration rules (all blends are linear in ai_native_score ∈ [0, 1]):
  - Scorecard weights:  w = std + (ai − std) × score, re-normalized to sum 1.0
  - Berkus caps:        cap_d = std_d + (ai_d − std_d) × score (total stays $3.5M)
  - RFS step values:    step = std + (ai − std) × score for the three
                        volatility categories (Technology, Competition,
                        Litigation) — symmetric, so it cuts both ways
  - ARR multiple uplift: vertical_premiums[vertical] × score

frozen_on verticals (ai_ml_infrastructure, ai_enabled_saas, defense_tech)
always receive STANDARD parameters — their benchmarks already price AI.

This module is fully standalone — no imports from startup_engine or
financial_engine. It never raises; errors degrade to standard parameters.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class AIParameterSet(BaseModel):
    """
    Effective per-method parameters for one valuation run.

    All values are already blended by ai_native_score. `None` for
    scorecard_weights / berkus_caps means "use the engine's standard
    parameters" (benchmark scorecard weights; uniform $0.7M Berkus caps).

    berkus_caps is keyed by the engine's internal dimension names:
      idea, management, prototype, relationships, rollout.
    rfs_step_values maps ONLY overridden categories to their raw step value
    in USD millions (pre-baseline-scaling); absent categories use the
    benchmark default step.
    """
    scorecard_weights: Optional[dict[str, float]] = None
    berkus_caps: Optional[dict[str, float]] = None
    rfs_step_values: dict[str, float] = Field(default_factory=dict)
    arr_multiple_uplift: float = 0.0
    applied: bool = False
    context: str = ""


# ---------------------------------------------------------------------------
# Config loading — once at module import time
# ---------------------------------------------------------------------------

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
_TOGGLE_PATH = os.path.join(_DATA_DIR, "ai_toggle_config.json")
_BENCHMARKS_PATH = os.path.join(_DATA_DIR, "startup_valuation_benchmarks.json")

# Standard Berkus calibration: 5 uniform dimensions × $0.7M = $3.5M total.
_STANDARD_BERKUS_CAP = 0.7
_BERKUS_TOTAL = 3.5

# Mapping from the parameter_matrix JSON dimension names to the engine's
# internal Berkus dimension names.
_BERKUS_KEY_MAP = {
    "sound_idea": "idea",
    "quality_management": "management",
    "prototype": "prototype",
    "strategic_relationships": "relationships",
    "product_rollout": "rollout",
}


def _load_json(path: str, label: str) -> dict:
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load {label}: {e}")
        return {}


def _load_config() -> dict:
    cfg = _load_json(_TOGGLE_PATH, "ai_toggle_config.json")
    if not cfg:
        cfg = {
            "frozen_on": [],
            "frozen_off": [],
            "default_on": [],
            "default_off": [],
            "vertical_premiums": {},
            "parameter_matrix": {},
        }
    return cfg


def _load_standard_scorecard_weights() -> dict[str, float]:
    """Standard scorecard weights come from the startup benchmarks file."""
    benchmarks = _load_json(_BENCHMARKS_PATH, "startup_valuation_benchmarks.json")
    return dict(benchmarks.get("scorecard_weights", {}))


def _load_standard_rfs_step() -> float:
    benchmarks = _load_json(_BENCHMARKS_PATH, "startup_valuation_benchmarks.json")
    return float(
        benchmarks.get("risk_factor_summation", {}).get("adjustment_per_step_usd_millions", 0.25)
    )


def _validate_ai_native_matrix(matrix: dict) -> bool:
    """
    Data-integrity check at load time. The ai_native calibration must not
    embed a hidden premium: scorecard weights must sum to 1.0 and the Berkus
    cap apportionment must total $3.5M. Returns False (matrix disabled) on
    violation — engines never raise.
    """
    ai = matrix.get("ai_native", {})
    weights = ai.get("scorecard_weights") or {}
    caps = ai.get("berkus_cap_apportionment") or {}
    if weights and abs(sum(weights.values()) - 1.0) > 1e-9:
        logger.error(
            "parameter_matrix.ai_native.scorecard_weights sum to %s, not 1.0 — "
            "AI parameter matrix disabled",
            sum(weights.values()),
        )
        return False
    if caps and abs(sum(caps.values()) - _BERKUS_TOTAL) > 1e-9:
        logger.error(
            "parameter_matrix.ai_native.berkus_cap_apportionment totals %s, not %s — "
            "AI parameter matrix disabled",
            sum(caps.values()),
            _BERKUS_TOTAL,
        )
        return False
    if set(_BERKUS_KEY_MAP) != set(caps or _BERKUS_KEY_MAP):
        logger.error(
            "parameter_matrix.ai_native.berkus_cap_apportionment has unexpected keys — "
            "AI parameter matrix disabled"
        )
        return False
    return True


_CONFIG = _load_config()
_MATRIX = _CONFIG.get("parameter_matrix", {})
_MATRIX_VALID = _validate_ai_native_matrix(_MATRIX)
_STANDARD_SCORECARD_WEIGHTS = _load_standard_scorecard_weights()
_STANDARD_RFS_STEP = _load_standard_rfs_step()

_FROZEN_ON_CONTEXT = (
    "Vertical is AI-native by definition — premium already reflected in benchmarks"
)


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------


def get_ai_parameters(is_ai_native: bool, ai_native_score: float, vertical: str) -> AIParameterSet:
    """
    Return the effective parameter set for one valuation run.

    Decision table:
      1. is_ai_native=False           → standard parameters, applied=False
      2. ai_native_score=0.0          → standard parameters, applied=False
      3. vertical in frozen_on        → standard parameters, applied=False,
                                        context notes benchmarks already price AI
      4. matrix missing/invalid       → standard parameters, applied=False
      5. Normal case                  → standard→ai_native linear blend by score

    Never raises — returns standard parameters (applied=False) on any error.
    """
    try:
        score = max(0.0, min(1.0, float(ai_native_score)))

        # 1–2. Toggle off or zero score
        if not is_ai_native or score == 0.0:
            return AIParameterSet()

        # 3. Frozen-on verticals — AI pricing already baked into benchmarks
        if vertical in _CONFIG.get("frozen_on", []):
            return AIParameterSet(context=_FROZEN_ON_CONTEXT)

        # 4. Matrix missing or failed load-time validation
        ai = _MATRIX.get("ai_native", {}) if _MATRIX_VALID else {}
        if not ai:
            return AIParameterSet(
                context="AI parameter matrix unavailable — standard parameters used"
            )

        # 5. Linear blend standard → ai_native by score
        context_parts: list[str] = []

        # Scorecard weights: w = std + (ai − std) × score, re-normalized
        weights: Optional[dict[str, float]] = None
        ai_weights = ai.get("scorecard_weights") or {}
        std_weights = _STANDARD_SCORECARD_WEIGHTS
        if ai_weights and std_weights:
            blended = {
                k: std_weights.get(k, 0.0) + (ai_weights.get(k, std_weights.get(k, 0.0)) - std_weights.get(k, 0.0)) * score
                for k in std_weights
            }
            total = sum(blended.values())
            if total > 0:
                weights = {k: v / total for k, v in blended.items()}
                context_parts.append("scorecard weight shift toward product/IP")

        # Berkus caps: cap_d = 0.7 + (ai_d − 0.7) × score (total preserved at $3.5M)
        caps: Optional[dict[str, float]] = None
        ai_caps = ai.get("berkus_cap_apportionment") or {}
        if ai_caps:
            caps = {
                _BERKUS_KEY_MAP[k]: _STANDARD_BERKUS_CAP + (v - _STANDARD_BERKUS_CAP) * score
                for k, v in ai_caps.items()
                if k in _BERKUS_KEY_MAP
            }
            context_parts.append("Berkus cap re-apportionment toward engineering/IP")

        # RFS step values: step = std + (override − std) × score, per category
        rfs_steps: dict[str, float] = {}
        for category, override in (ai.get("rfs_step_value_overrides") or {}).items():
            rfs_steps[category] = _STANDARD_RFS_STEP + (float(override) - _STANDARD_RFS_STEP) * score
        if rfs_steps:
            context_parts.append("wider RFS steps for volatility categories")

        # ARR multiple uplift: vertical premium × score
        uplift = 0.0
        base_premium = _CONFIG.get("vertical_premiums", {}).get(vertical)
        if base_premium is None:
            logger.warning(
                "Vertical '%s' not found in ai_toggle_config.json vertical_premiums; "
                "ARR multiple uplift set to 0",
                vertical,
            )
        else:
            uplift = float(base_premium) * score
            if uplift > 0:
                context_parts.append(f"ARR multiple uplift {uplift:.0%}")

        return AIParameterSet(
            scorecard_weights=weights,
            berkus_caps=caps,
            rfs_step_values=rfs_steps,
            arr_multiple_uplift=uplift,
            applied=True,
            context=(
                "Premium emerges from parameter-level calibration: "
                + ", ".join(context_parts)
                + f" (AI-native score {score:.2f}, {vertical})."
            ),
        )

    except Exception as e:
        logger.exception("Unexpected error in get_ai_parameters")
        return AIParameterSet(context=f"AI parameter calibration error: {e}")
