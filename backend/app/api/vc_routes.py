"""
FastAPI routes for the VC fund-seat analysis engine.
Prefix: /api/vc

Answers the question every VC investor asks before writing a check:
  "At this valuation, what does this company need to exit at for my fund to care?"
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ValidationError

from ..engine.vc_fund_models import (
    AntiDilutionInput,
    AntiDilutionOutput,
    BridgeRoundInput,
    BridgeRoundOutput,
    DealComparisonOutput,
    FundProfile,
    FundIRRInput,
    FundIRROutput,
    GPCarryInput,
    GPCarryOutput,
    PortfolioInput,
    PortfolioOutput,
    ProRataAnalysis,
    QSBSInput,
    QSBSOutput,
    SAFEConversionInput,
    SAFEConversionOutput,
    VCDealInput,
    VCDealOutput,
    VCVertical,
    VCStage,
    WaterfallDistribution,
)
from ..engine.vc_scenarios import effective_deal
from ..engine.benchmark_registry import _version
from ..engine.vc_return_engine import (
    _load_benchmarks,
    run_vc_deal_evaluation,
    run_portfolio_analysis,
    run_qsbs_analysis,
    run_anti_dilution,
    run_bridge_analysis,
    run_gp_carry_analysis,
    run_fund_irr_analysis,
    run_safe_conversion,
    run_deal_comparison,
    compute_ownership_math,
    compute_waterfall,
    compute_pro_rata,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/vc")

# Benchmarks are static — load once at module import (cached in the engine).
_BENCHMARKS: dict = _load_benchmarks()


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
        deal = VCDealInput(**request.model_dump(exclude={"fund"}, exclude_unset=True))
        return run_vc_deal_evaluation(deal, fund)
    except ValidationError:
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
    All computed figures come from FundProfile's computed properties so the
    fee, recycling, and reserve math is consistent with the rest of the engine.
    """
    try:
        construction = _BENCHMARKS.get("fund_construction", {})

        if fund_size_usd_m <= 100:
            template = construction.get("typical_seed_fund", {})
        else:
            template = construction.get("typical_series_a_fund", {})

        check_low, check_high = template.get("initial_check_range_usd_m", [1.0, 3.0])

        # Build the actual FundProfile so all derived numbers share one
        # definition of fees / recycling / reserves.
        profile = FundProfile(
            fund_size=fund_size_usd_m,
            management_fee_pct=template.get("management_fee_pct", 0.02),
            management_fee_years=5,
            carry_pct=template.get("carry_pct", 0.20),
            hurdle_rate=0.08,
            reserve_ratio=template.get("reserve_ratio", 0.40),
            target_initial_check_count=template.get("portfolio_count", [25, 40])[0],
            target_ownership_pct=template.get("target_ownership_pct", 0.10),
            recycling_pct=0.05,
            deployment_period_years=template.get("deployment_period_years", 3),
        )

        return {
            "fund_size": fund_size_usd_m,
            "recommended_defaults": {
                "management_fee_pct": profile.management_fee_pct,
                "management_fee_years": profile.management_fee_years,
                "carry_pct": profile.carry_pct,
                "hurdle_rate": profile.hurdle_rate,
                "reserve_ratio": profile.reserve_ratio,
                "target_initial_check_count": profile.target_initial_check_count,
                "target_ownership_pct": profile.target_ownership_pct,
                "deployment_period_years": profile.deployment_period_years,
                "recycling_pct": profile.recycling_pct,
            },
            "computed": {
                "total_management_fees": round(profile.total_management_fees, 2),
                "investable_capital": round(profile.investable_capital, 2),
                "initial_check_pool": round(profile.initial_check_pool, 2),
                "implied_initial_check": round(profile.target_initial_check_size, 2),
                "initial_check_range": {"low": check_low, "high": check_high},
                "reserve_pool": round(profile.reserve_pool, 2),
            },
            "power_law_context": construction.get("power_law_returns", {}),
        }
    except Exception:
        logger.exception("Failed to retrieve fund defaults")
        raise HTTPException(status_code=500, detail="Failed to retrieve fund defaults.")


# ---------------------------------------------------------------------------
# Portfolio construction
# ---------------------------------------------------------------------------

@router.post("/portfolio", response_model=PortfolioOutput,
             summary="Analyze portfolio construction and fund deployment")
async def analyze_portfolio(inp: PortfolioInput) -> PortfolioOutput:
    """
    Compute portfolio-level construction metrics: TVPI, DPI, RVPI,
    stage/vertical concentration, reserve adequacy, and deployment status.
    """
    try:
        return run_portfolio_analysis(inp)
    except Exception:
        logger.exception("Portfolio analysis failed")
        raise HTTPException(status_code=500, detail="Portfolio analysis failed.")


# ---------------------------------------------------------------------------
# Waterfall analysis
# ---------------------------------------------------------------------------

class WaterfallRequest(VCDealInput):
    exit_ev: float


@router.post("/waterfall", response_model=WaterfallDistribution,
             summary="Compute liquidation preference waterfall at a given exit EV")
async def analyze_waterfall(request: WaterfallRequest) -> WaterfallDistribution:
    """
    Distribute exit proceeds through the liquidation preference stack.
    Returns per-class distribution amounts and optimal conversion decisions.
    """
    try:
        deal = VCDealInput(**request.model_dump(exclude={"exit_ev"}))
        return compute_waterfall(deal, request.exit_ev)
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


@router.post("/pro-rata", response_model=ProRataAnalysis,
             summary="Analyze whether to exercise pro-rata rights")
async def analyze_pro_rata(request: ProRataRequest) -> ProRataAnalysis:
    """
    Model the expected value of exercising vs. passing on pro-rata rights.
    Returns scenario comparison and a recommendation.
    """
    try:
        fund = request.fund
        deal = VCDealInput(**request.model_dump(exclude={"fund", "next_round_valuation", "pro_rata_check"}, exclude_unset=True))
        token = _version.set(deal.benchmark_version)
        deal = effective_deal(deal)
        ownership = compute_ownership_math(
            check_size=deal.check_size,
            post_money=deal.post_money_valuation,
            stage=deal.stage,
            dilution=deal.dilution,
            fund_profile=fund,
            arr=deal.arr,
            future_rounds=deal.future_rounds,
        )
        return compute_pro_rata(
            deal, fund, ownership,
            request.next_round_valuation, request.pro_rata_check, _BENCHMARKS,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception:
        logger.exception("Pro-rata analysis failed")
        raise HTTPException(status_code=500, detail="Pro-rata analysis failed.")
    finally:
        if 'token' in locals():
            _version.reset(token)


# ---------------------------------------------------------------------------
# QSBS eligibility
# ---------------------------------------------------------------------------

@router.post("/qsbs", response_model=QSBSOutput,
             summary="Check QSBS eligibility and estimate tax benefit (IRC §1202)")
async def check_qsbs(inp: QSBSInput) -> QSBSOutput:
    """
    Run the QSBS eligibility checklist and estimate LP-level federal tax benefit.
    Reflects the OBBBA (post-July 4, 2025) $15M cap, $75M gross-asset threshold,
    and tiered 50/75/100% exclusion at 3/4/5-year holding periods.
    """
    try:
        return run_qsbs_analysis(inp)
    except Exception:
        logger.exception("QSBS analysis failed")
        raise HTTPException(status_code=500, detail="QSBS analysis failed.")


# ---------------------------------------------------------------------------
# Anti-dilution analysis
# ---------------------------------------------------------------------------

@router.post("/anti-dilution", response_model=AntiDilutionOutput,
             summary="Model anti-dilution adjustment in a down round")
async def analyze_anti_dilution(inp: AntiDilutionInput) -> AntiDilutionOutput:
    """
    Compute the anti-dilution adjustment for full ratchet vs. broad-based weighted average.
    Returns adjusted conversion price, additional shares issued, and economic impact.
    """
    try:
        return run_anti_dilution(inp)
    except Exception:
        logger.exception("Anti-dilution analysis failed")
        raise HTTPException(status_code=500, detail="Anti-dilution analysis failed.")


# ---------------------------------------------------------------------------
# Bridge round analysis
# ---------------------------------------------------------------------------

@router.post("/bridge", response_model=BridgeRoundOutput,
             summary="Model a bridge or extension round")
async def analyze_bridge(inp: BridgeRoundInput) -> BridgeRoundOutput:
    """
    Analyze a bridge / extension round: dilution impact, effective conversion price,
    and fund participation recommendation.
    """
    try:
        return run_bridge_analysis(inp)
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
        vdata = _BENCHMARKS.get("verticals", {}).get(vertical.value, {})
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
            "dilution": _BENCHMARKS.get("dilution_per_round", {}).get(stage.value, {}),
            "time_to_next_round": _BENCHMARKS.get("time_to_next_round", {}),
            "transition_probabilities": _BENCHMARKS.get("stage_transition_probabilities", {}),
            "burn_multiple_bands": _BENCHMARKS.get("burn_multiple_benchmarks", {}),
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
        verticals = _BENCHMARKS.get("verticals", {})
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


# ---------------------------------------------------------------------------
# GP Carry Economics
# ---------------------------------------------------------------------------

@router.post("/gp-carry", response_model=GPCarryOutput,
             summary="Model GP carry economics through the fund waterfall")
async def analyze_gp_carry(inp: GPCarryInput) -> GPCarryOutput:
    """
    Compute GP carry economics including:
    - Full waterfall (return of capital → hurdle → catch-up → carry split)
    - Per-GP compensation breakdown
    - Clawback exposure (deal-by-deal vs. whole-fund)
    - LP net returns after carry
    """
    try:
        return run_gp_carry_analysis(inp)
    except Exception:
        logger.exception("GP carry analysis failed")
        raise HTTPException(status_code=500, detail="GP carry analysis failed.")


# ---------------------------------------------------------------------------
# Fund-Level IRR & J-Curve
# ---------------------------------------------------------------------------

@router.post("/fund-irr", response_model=FundIRROutput,
             summary="Compute fund-level IRR and J-curve")
async def analyze_fund_irr(inp: FundIRRInput) -> FundIRROutput:
    """
    Compute fund-level performance metrics:
    - Gross and net IRR (Newton-Raphson on cashflows)
    - J-curve visualization data
    - TVPI/DPI/RVPI
    - Vintage quartile estimate
    """
    try:
        return run_fund_irr_analysis(inp)
    except Exception:
        logger.exception("Fund IRR analysis failed")
        raise HTTPException(status_code=500, detail="Fund IRR analysis failed.")


# ---------------------------------------------------------------------------
# SAFE Conversion Modeling
# ---------------------------------------------------------------------------

@router.post("/safe-conversion", response_model=SAFEConversionOutput,
             summary="Model SAFE stack conversion at a priced round")
async def analyze_safe_conversion(inp: SAFEConversionInput) -> SAFEConversionOutput:
    """
    Model a stack of SAFEs converting at a priced equity round:
    - Per-SAFE conversion price and shares
    - Cap vs. discount determination
    - MFN clause application
    - Full post-conversion cap table
    - Founder dilution breakdown
    """
    try:
        return run_safe_conversion(inp)
    except Exception:
        logger.exception("SAFE conversion analysis failed")
        raise HTTPException(status_code=500, detail="SAFE conversion analysis failed.")


# ---------------------------------------------------------------------------
# Deal Comparison
# ---------------------------------------------------------------------------

class DealComparisonRequest(BaseModel):
    """Multiple deals for side-by-side comparison."""
    deals: list[DealEvalRequest]


@router.post("/compare", response_model=DealComparisonOutput,
             summary="Compare multiple deals side-by-side")
async def compare_deals(request: DealComparisonRequest) -> DealComparisonOutput:
    """
    Evaluate multiple deals and produce a ranked comparison for IC discussion.
    Returns per-deal metrics with rankings on MOIC, IRR, and ownership.
    """
    try:
        deal_fund_pairs = []
        for d in request.deals:
            fund = d.fund
            deal = VCDealInput(**d.model_dump(exclude={"fund"}))
            deal_fund_pairs.append((deal, fund))
        return run_deal_comparison(deal_fund_pairs)
    except Exception:
        logger.exception("Deal comparison failed")
        raise HTTPException(status_code=500, detail="Deal comparison failed.")
