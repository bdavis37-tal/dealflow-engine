"""
AI Valuation Modifier

Applies a research-backed AI-native premium to blended startup valuations.
The premium is graduated: it scales linearly with ai_native_score (0.0–1.0)
derived from a four-question AI Characteristics Assessment.

This module is fully standalone — no imports from startup_engine or financial_engine.
It never raises exceptions; errors are returned as pass-through outputs with warnings.
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


class AIModifierInput(BaseModel):
    is_ai_native: bool
    ai_native_score: float = Field(ge=0.0, le=1.0)
    vertical: str
    blended_valuation: float = Field(gt=0.0)


class AIModifierOutput(BaseModel):
    blended_after_ai: float
    ai_premium_multiplier: Optional[float] = None
    ai_modifier_applied: bool = False
    ai_premium_context: Optional[str] = None


# ---------------------------------------------------------------------------
# Config loading — once at module import time
# ---------------------------------------------------------------------------

_DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "ai_toggle_config.json")


def _load_config() -> dict:
    try:
        with open(_DATA_PATH, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load ai_toggle_config.json: {e}")
        return {
            "frozen_on": [],
            "frozen_off": [],
            "default_on": [],
            "default_off": [],
            "vertical_premiums": {},
        }


_CONFIG = _load_config()


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------


def apply_ai_modifier(inp: AIModifierInput) -> AIModifierOutput:
    """
    Apply the AI-native premium to a blended startup valuation.

    Decision table:
      1. is_ai_native=False          → pass-through
      2. ai_native_score=0.0         → pass-through
      3. vertical in frozen_on       → pass-through (benchmark already reflects AI pricing)
      4. vertical not in premiums    → pass-through with warning
      5. Normal case                 → blended × (1 + base_premium × score)

    Never raises — returns AIModifierOutput with ai_modifier_applied=False on any error.
    """
    try:
        # Clamp score to [0.0, 1.0] defensively
        score = max(0.0, min(1.0, inp.ai_native_score))

        # Guard: blended_valuation must be positive
        if inp.blended_valuation <= 0:
            logger.warning("blended_valuation <= 0 (%s); returning pass-through", inp.blended_valuation)
            return AIModifierOutput(
                blended_after_ai=inp.blended_valuation,
                ai_modifier_applied=False,
                ai_premium_multiplier=None,
                ai_premium_context="blended_valuation must be positive",
            )

        # 1. Toggle is OFF
        if not inp.is_ai_native:
            return AIModifierOutput(
                blended_after_ai=inp.blended_valuation,
                ai_modifier_applied=False,
                ai_premium_multiplier=None,
                ai_premium_context=None,
            )

        # 2. Score is zero — no premium to apply
        if score == 0.0:
            return AIModifierOutput(
                blended_after_ai=inp.blended_valuation,
                ai_modifier_applied=False,
                ai_premium_multiplier=None,
                ai_premium_context=None,
            )

        # 3. Frozen-on verticals — premium already baked into benchmarks
        frozen_on = _CONFIG.get("frozen_on", [])
        if inp.vertical in frozen_on:
            return AIModifierOutput(
                blended_after_ai=inp.blended_valuation,
                ai_modifier_applied=False,
                ai_premium_multiplier=None,
                ai_premium_context=(
                    "Vertical is AI-native by definition — premium already reflected in benchmarks"
                ),
            )

        # 4. Vertical not found in vertical_premiums
        vertical_premiums = _CONFIG.get("vertical_premiums", {})
        base_premium = vertical_premiums.get(inp.vertical)
        if base_premium is None:
            logger.warning(
                "Vertical '%s' not found in ai_toggle_config.json vertical_premiums; "
                "treating as default_off with no premium",
                inp.vertical,
            )
            return AIModifierOutput(
                blended_after_ai=inp.blended_valuation,
                ai_modifier_applied=False,
                ai_premium_multiplier=None,
                ai_premium_context=(
                    f"Vertical '{inp.vertical}' not found in AI modifier config — no premium applied"
                ),
            )

        # 5. Normal case: graduated premium
        premium = base_premium * score
        blended_after_ai = inp.blended_valuation * (1 + premium)

        return AIModifierOutput(
            blended_after_ai=blended_after_ai,
            ai_premium_multiplier=premium,
            ai_modifier_applied=True,
            ai_premium_context=(
                f"AI-native premium: {premium:.0%} applied ({inp.vertical} at score {score})"
            ),
        )

    except Exception as e:
        logger.exception("Unexpected error in apply_ai_modifier")
        return AIModifierOutput(
            blended_after_ai=inp.blended_valuation,
            ai_modifier_applied=False,
            ai_premium_multiplier=None,
            ai_premium_context=f"AI modifier error: {e}",
        )
