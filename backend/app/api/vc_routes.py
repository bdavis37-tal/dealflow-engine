"""
FastAPI routes for the VC fund-seat analysis engine.
Prefix: /api/vc

Answers the question every VC investor asks before writing a check:
  "At this valuation, what does this company need to exit at for my fund to care?"
"""
from __future__ import annotations

import json
import logging
import os

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from ..engine import round_financial_output
from ..engine.vc_fund_models import (
    AntiDilutionInput,
    BridgeRoundInput,
    FundProfile,
    PortfolioInput,
    QSBSInput,
    VCDealInput,
    VCDealOutput,
    VCVertical,
    VCStage,
)
from ..engine.vc_return_engine import (
    run_vc_deal_evaluation,
    run_portfolio_analysis,
    run_qsbs_analysis,
    run_anti_dilution,
    run_bridge_analysis,
    compute_waterfall,
    compute_pro_rata,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/vc")

_DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "vc_benchmarks.json")


# ---------------------------------------------------------------------------
# Core deal evaluation
# ---------------------------------------------------------------------------

class DealEvalRequest(VCDealInput):
    """Combines deal input with fund profile for evaluation."""
    fund: FundProfile


@router.post("/evaluate", response_model=VCDealOutput, summary="Evaluate a deal from the VC fund seat")
async def evaluate_deal(request: DealEvalRequest) -> VCDealOutput:
    """
    Run the full VC deal evaluation engine.

    Accepts a VCDealInput + FundProfile and returns:
    - Core ownership math (entry %, exit % after dilution stack)
    - Fund returner thresholds (what exit is needed to matter to the fund)
    - 3-scenario return model (bear/base/bull with probabilities)
    - Quick screen recommendation (pass / look deeper / strong interest)
    - Waterfall analysis (if cap table provided)
    - IC memo financial section (auto-populated)
    - Power law context
    """
    try:
        logger.info(
            "VC evaluation: %s | %s %s | $%.1fM @ $%.0fM post-money",
            request.company_name,
            request.vertical.value,
            request.stage.value,
            request.check_size,
            request.post_money_valuation,
        )
        # Extract fund from request and create deal input
        fund = request.fund
        deal = VCDealInput(**request.model_dump(exclude={"fund"}))
        result = run_vc_deal_evaluation(deal, fund)
        return JSONResponse(content=round_financial_output(result))
    except ValidationError as e:
        raise HTTPException(status_code=422, detail="Invalid deal or fund inputs.")
    except Exception:
        logger.exception("VC deal evaluation failed")
        raise HTTPException(status_code=500, detail="VC deal evaluation encountered an internal error.")


# ---------------------------------------------------------------------------
# Fund profile defaults
# ---------------------------------------------------------------------------

@router.get("/fund/defaults", summary="Get recommended fund profile defaults by fund size")
async def get_fund_defaults(fund_size_usd_m: float) -> dict:
    """
    Return recommended fund profile defaults based on fund size.

    Calibrated to Cambridge Associates / First Round Capital best practices.
    """
    try:
        with open(_DATA_PATH, "r") as f:
            benchmarks = json.load(f)

        construction = benchmarks.get("fund_construction", {})

        if fund_size_usd_m <= 100:
            template = construction.get("typical_seed_fund", {})
        else:
            template = construction.get("typical_series_a_fund", {})

        check_low, check_high = template.get("initial_check_range_usd_m", [1.0, 3.0])
        target_check = (fund_size_usd_m - fund_size_usd_m * 0.10 * 5) * (1 - template.get("reserve_ratio", 0.40)) / template.get("portfolio_count", [25, 40])[0]

        return {
            "fund_size": fund_size_usd_m,
            "recommended_defaults": {
                "management_fee_pct": 0.02,
                "management_fee_years": 5,
                "carry_pct": 0.20,
                "hurdle_rate": 0.08,
                "reserve_ratio": template.get("reserve_ratio", 0.40),
                "target_initial_check_count": template.get("portfolio_count", [25, 40])[0],
                "target_ownership_pct": template.get("target_ownership_pct", 0.10),
                "deployment_period_years": template.get("deployment_period_years", 3),
                "recycling_pct": 0.05,
            },
            "computed": {
                "investable_capital": fund_size_usd_m - (fund_size_usd_m * 0.02 * 5),
                "implied_initial_check": round(target_check, 2),
                "initial_check_range": {"low": check_low, "high": check_high},
                "reserve_pool": fund_size_usd_m * (1 - 0.10) * template.get("reserve_ratio", 0.40),
            },
            "power_law_context": benchmarks.get("fund_construction", {}).get("power_law_returns", {}),
        }
    except Exception:
        logger.exception("Failed to retrieve fund defaults")
        raise HTTPException(status_code=500, detail="Failed to retrieve fund defaults.")


# ---------------------------------------------------------------------------
# Portfolio construction
# ---------------------------------------------------------------------------

@router.post("/portfolio", summary="Analyze portfolio construction and fund deployment")
async def analyze_portfolio(inp: PortfolioInput):
    """
    Compute portfolio-level construction metrics: TVPI, DPI, RVPI,
    stage/vertical concentration, reserve adequacy, and deployment status.
    """
    try:
        result = run_portfolio_analysis(inp)
        return JSONResponse(content=round_financial_output(result))
    except Exception:
        logger.exception("Portfolio analysis failed")
        raise HTTPException(status_code=500, detail="Portfolio analysis failed.")


# ---------------------------------------------------------------------------
# Waterfall analysis
# ---------------------------------------------------------------------------

class WaterfallRequest(VCDealInput):
    exit_ev: float


@router.post("/waterfall", summary="Compute liquidation preference waterfall at a given exit EV")
async def analyze_waterfall(request: WaterfallRequest):
    """
    Distribute exit proceeds through the liquidation preference stack.
    Returns per-class distribution amounts and optimal conversion decisions.
    """
    try:
        deal = VCDealInput(**request.model_dump(exclude={"exit_ev"}))
        result = compute_waterfall(deal, request.exit_ev)
        return JSONResponse(content=round_financial_output(result))
    except Exception:
        logger.exception("Waterfall analysis failed")
        raise HTTPException(status_code=500, detail="Waterfall analysis failed.")


# ---------------------------------------------------------------------------
# Pro-rata analysis
# ---------------------------------------------------------------------------

class ProRataRequest(VCDealInput):
    fund: FundProfile
    next_round_valuation: float
    pro_rata_check: float


@router.post("/pro-rata", summary="Analyze whether to exercise pro-rata rights")
async def analyze_pro_rata(request: ProRataRequest):
    """
    Model the expected value of exercising vs. passing on pro-rata rights.
    Returns scenario comparison and a recommendation.
    """
    try:
        from ..engine.vc_return_engine import compute_ownership_math
        fund = request.fund
        deal = VCDealInput(**request.model_dump(exclude={"fund", "next_round_valuation", "pro_rata_check"}))
        ownership = compute_ownership_math(
            check_size=deal.check_size,
            post_money=deal.post_money_valuation,
            stage=deal.stage,
            dilution=deal.dilution,
            fund_profile=fund,
            arr=deal.arr,
        )
        with open(_DATA_PATH, "r") as f:
            benchmarks = json.load(f)
        result = compute_pro_rata(deal, fund, ownership, request.next_round_valuation, request.pro_rata_check, benchmarks)
        return JSONResponse(content=round_financial_output(result))
    except Exception:
        logger.exception("Pro-rata analysis failed")
        raise HTTPException(status_code=500, detail="Pro-rata analysis failed.")


# ---------------------------------------------------------------------------
# QSBS eligibility
# ---------------------------------------------------------------------------

@router.post("/qsbs", summary="Check QSBS eligibility and estimate tax benefit (IRC §1202)")
async def check_qsbs(inp: QSBSInput):
    """
    Run the QSBS eligibility checklist and estimate LP-level federal tax benefit.
    Reflects the new $15M exclusion cap for shares issued after July 4, 2025.
    """
    try:
        result = run_qsbs_analysis(inp)
        return JSONResponse(content=round_financial_output(result))
    except Exception:
        logger.exception("QSBS analysis failed")
        raise HTTPException(status_code=500, detail="QSBS analysis failed.")


# ---------------------------------------------------------------------------
# Anti-dilution analysis
# ---------------------------------------------------------------------------

@router.post("/anti-dilution", summary="Model anti-dilution adjustment in a down round")
async def analyze_anti_dilution(inp: AntiDilutionInput):
    """
    Compute the anti-dilution adjustment for full ratchet vs. broad-based weighted average.
    Returns adjusted conversion price, additional shares issued, and economic impact.
    """
    try:
        result = run_anti_dilution(inp)
        return JSONResponse(content=round_financial_output(result))
    except Exception:
        logger.exception("Anti-dilution analysis failed")
        raise HTTPException(status_code=500, detail="Anti-dilution analysis failed.")


# ---------------------------------------------------------------------------
# Bridge round analysis
# ---------------------------------------------------------------------------

@router.post("/bridge", summary="Model a bridge or extension round")
async def analyze_bridge(inp: BridgeRoundInput):
    """
    Analyze a bridge / extension round: dilution impact, effective conversion price,
    and fund participation recommendation.
    """
    try:
        result = run_bridge_analysis(inp)
        return JSONResponse(content=round_financial_output(result))
    except Exception:
        logger.exception("Bridge analysis failed")
        raise HTTPException(status_code=500, detail="Bridge analysis failed.")


# ---------------------------------------------------------------------------
# Benchmark data
# ---------------------------------------------------------------------------

@router.get("/benchmarks", summary="Get VC benchmarks for a vertical and stage")
async def get_benchmarks(
    vertical: VCVertical,
    stage: VCStage,
) -> dict:
    """
    Return VC benchmark data for a given vertical and stage:
    - Median/P25/P75 post-money valuations
    - Typical raise amounts
    - ARR multiples
    - Dilution benchmarks
    - Exit multiple ranges
    - Time-to-next-round data
    """
    try:
        with open(_DATA_PATH, "r") as f:
            data = json.load(f)

        vdata = data.get("verticals", {}).get(vertical.value, {})
        stage_data = vdata.get(stage.value, {})

        if not stage_data:
            raise HTTPException(
                status_code=404,
                detail=f"No benchmark data for vertical '{vertical.value}' at stage '{stage.value}'."
            )

        return {
            "vertical": vertical.value,
            "vertical_label": vdata.get("label", vertical.value),
            "stage": stage.value,
            "benchmarks": stage_data,
            "exit_multiples": vdata.get("exit_multiples", {}),
            "dilution": data.get("dilution_per_round", {}).get(stage.value, {}),
            "time_to_next_round": data.get("time_to_next_round", {}),
            "transition_probabilities": data.get("stage_transition_probabilities", {}),
            "burn_multiple_bands": data.get("burn_multiple_benchmarks", {}),
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to retrieve VC benchmarks")
        raise HTTPException(status_code=500, detail="Failed to retrieve VC benchmarks.")


@router.get("/verticals", summary="List VC-supported verticals")
async def list_vc_verticals() -> list[dict]:
    """Return all supported startup verticals with labels and descriptions."""
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
            for v in VCVertical
        ]
    except Exception:
        logger.exception("Failed to list VC verticals")
        raise HTTPException(status_code=500, detail="Failed to retrieve VC vertical list.")


@router.get("/stages", summary="List VC investment stages")
async def list_vc_stages() -> list[dict]:
    """Return all supported investment stages."""
    return [
        {"value": "pre_seed", "label": "Pre-Seed", "description": "Idea through MVP; < $3M raise"},
        {"value": "seed", "label": "Seed", "description": "Early traction; $2-6M raise; SAFE or priced"},
        {"value": "series_a", "label": "Series A", "description": "PMF proven; $8-25M; $1.5M+ ARR"},
        {"value": "series_b", "label": "Series B", "description": "Scaling; $20-60M; $5M+ ARR"},
        {"value": "series_c", "label": "Series C", "description": "Expansion; $40-100M+; $15M+ ARR"},
        {"value": "growth", "label": "Growth / Late Stage", "description": "Pre-IPO / secondary; $100M+"},
    ]


@router.get("/health", summary="VC engine health check")
async def vc_health() -> dict:
    return {"status": "healthy", "service": "vc-fund-engine"}
