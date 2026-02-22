"""
FastAPI routes for the startup valuation engine.
Prefix: /api/startup
"""
from __future__ import annotations

import json
import logging
import os

from fastapi import APIRouter, HTTPException
from pydantic import ValidationError

from ..engine.startup_models import StartupInput, StartupValuationOutput, StartupVertical, StartupStage
from ..engine.startup_engine import run_startup_valuation

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/startup")

_DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "startup_valuation_benchmarks.json")


@router.post("/value", response_model=StartupValuationOutput, summary="Run startup valuation")
async def value_startup(inp: StartupInput) -> StartupValuationOutput:
    """
    Run the four-method startup valuation engine.

    Returns a blended pre-money valuation, method breakdown, dilution model,
    investor scorecard, and benchmark comparison for the given vertical and stage.
    """
    try:
        logger.info(
            "Valuing startup: %s — %s %s raise $%.2fM",
            inp.company_name,
            inp.fundraise.vertical.value,
            inp.fundraise.stage.value,
            inp.fundraise.raise_amount,
        )
        result = run_startup_valuation(inp)
        return result
    except ValidationError as e:
        raise HTTPException(status_code=422, detail="Invalid startup inputs. Please check your values.")
    except Exception:
        logger.exception("Startup valuation failed")
        raise HTTPException(status_code=500, detail="Startup valuation encountered an internal error. Please try again.")


@router.get("/benchmarks", summary="Get benchmark data for a vertical and stage")
async def get_benchmarks(
    vertical: StartupVertical,
    stage: StartupStage,
) -> dict:
    """
    Return the raw benchmark data (P25/P50/P75/P95 valuations, ARR multiples, dilution)
    for a given startup vertical and fundraising stage.

    Use this to pre-fill UI components with market-calibrated defaults before the user
    provides custom inputs.
    """
    try:
        with open(_DATA_PATH, "r") as f:
            data = json.load(f)

        vdata = data.get("verticals", {}).get(vertical.value, {})
        stage_data = vdata.get(stage.value, {})

        if not stage_data:
            raise HTTPException(status_code=404, detail=f"No benchmark data for vertical '{vertical.value}' at stage '{stage.value}'.")

        return {
            "vertical": vertical.value,
            "vertical_label": vdata.get("label", vertical.value),
            "stage": stage.value,
            "benchmarks": stage_data,
            "market_wide": data.get("market_wide_medians", {}).get(stage.value, {}),
            "nrr_multiple_lookup": data.get("nrr_multiple_lookup", {}),
            "burn_multiple_bands": data.get("burn_multiple_bands", {}),
            "rule_of_40_bands": data.get("rule_of_40_bands", {}),
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to retrieve startup benchmarks")
        raise HTTPException(status_code=500, detail="Failed to retrieve benchmark data.")


@router.get("/verticals", summary="List startup verticals")
async def list_verticals() -> list[dict]:
    """Return all supported startup verticals with labels."""
    try:
        with open(_DATA_PATH, "r") as f:
            data = json.load(f)
        verticals = data.get("verticals", {})
        return [
            {
                "value": v.value,
                "label": verticals.get(v.value, {}).get("label", v.value),
                "description": verticals.get(v.value, {}).get("description", ""),
            }
            for v in StartupVertical
        ]
    except Exception:
        logger.exception("Failed to list verticals")
        raise HTTPException(status_code=500, detail="Failed to retrieve vertical list.")


@router.get("/stages", summary="List startup funding stages")
async def list_stages() -> list[dict]:
    """Return all supported funding stages."""
    return [
        {"value": "pre_seed", "label": "Pre-Seed", "description": "Idea through MVP; typically SAFE or convertible note"},
        {"value": "seed", "label": "Seed", "description": "Early traction; priced round or SAFE up to ~$4M"},
        {"value": "series_a", "label": "Series A", "description": "Scaling with proven product-market fit; $2M+ ARR typical"},
    ]
