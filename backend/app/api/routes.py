"""
FastAPI route definitions for the dealflow engine API.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from ..engine import run_deal, round_financial_output
from ..engine.models import DealInput, DealOutput, Industry
from ..engine.defaults import get_defaults, get_transaction_fee_pct, get_interest_rate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1")


@router.post("/analyze", response_model=DealOutput, summary="Run deal analysis")
async def analyze_deal(deal: DealInput) -> DealOutput:
    """
    Execute the full M&A deal model and return structured results.

    Accepts a complete DealInput and returns a DealOutput with:
    - 5-year pro forma income statements
    - Accretion/dilution analysis
    - Sensitivity matrices
    - IRR/MOIC returns
    - Risk assessment
    - Deal verdict and scorecard
    """
    try:
        logger.info(
            "Analyzing deal: %s acquiring %s for $%,.0f",
            deal.acquirer.company_name,
            deal.target.company_name,
            deal.target.acquisition_price,
        )
        result = run_deal(deal)
        return JSONResponse(content=round_financial_output(result))
    except ValidationError as e:
        raise HTTPException(status_code=422, detail="Invalid deal inputs. Please check your values and try again.")
    except Exception:
        logger.exception("Deal analysis failed")
        raise HTTPException(status_code=500, detail="Deal analysis encountered an internal error. Please try again.")


@router.get("/defaults", summary="Get smart defaults for a deal")
async def get_smart_defaults(
    industry: Industry,
    deal_size: float,
    target_revenue: float,
) -> dict[str, Any]:
    """
    Return recommended default assumptions for a given industry and deal size.

    Use this to pre-fill form fields with intelligent estimates before the user
    provides custom inputs.
    """
    try:
        defaults = get_defaults(industry, deal_size, target_revenue)
        return {
            "tax_rate": defaults.tax_rate,
            "transaction_fees_pct": defaults.transaction_fees_pct,
            "blended_interest_rate": defaults.blended_interest_rate,
            "interest_rate_range": {
                "low": defaults.interest_rate_range[0],
                "high": defaults.interest_rate_range[1],
            },
            "industry_benchmarks": {
                "ebitda_margin": defaults.ebitda_margin,
                "gross_margin": defaults.gross_margin,
                "sga_pct_revenue": defaults.sga_pct_revenue,
                "working_capital_pct_revenue": defaults.working_capital_pct_revenue,
                "capex_pct_revenue": defaults.capex_pct_revenue,
                "da_pct_revenue": defaults.da_pct_revenue,
                "ev_ebitda_low": defaults.ev_ebitda_low,
                "ev_ebitda_median": defaults.ev_ebitda_median,
                "ev_ebitda_high": defaults.ev_ebitda_high,
                "revenue_growth_rate": defaults.revenue_growth_rate,
                "debt_capacity_turns": defaults.debt_capacity_turns,
            },
            "synergy_benchmarks": {
                "back_office_synergy_pct_sga": defaults.back_office_synergy_pct_sga,
                "procurement_synergy_pct_cogs": defaults.procurement_synergy_pct_cogs,
                "facility_synergy_pct_revenue": defaults.facility_synergy_pct_revenue,
            },
        }
    except Exception:
        logger.exception("Failed to retrieve defaults for industry=%s deal_size=%s", industry, deal_size)
        raise HTTPException(status_code=500, detail="Failed to retrieve industry defaults.")


@router.get("/industries", summary="List supported industries")
async def list_industries() -> list[dict[str, str]]:
    """Return all supported industry verticals."""
    return [{"value": ind.value, "label": ind.value} for ind in Industry]


@router.get("/health", summary="Health check")
async def health_check() -> dict[str, str]:
    """Simple health check endpoint."""
    return {"status": "healthy", "service": "dealflow-engine"}
