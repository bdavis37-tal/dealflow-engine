"""
Smart defaults engine — returns sensible pre-fills based on industry and deal size.
Benchmarks are sourced from publicly available industry research (Duff & Phelps,
Damodaran, PitchBook, and sector-specific public comps).
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Optional

from .models import Industry


# ---------------------------------------------------------------------------
# Interest rate assumptions (update periodically)
# These represent typical acquisition financing rates as of 2024-2025.
# ---------------------------------------------------------------------------
MIDDLE_MARKET_RATE_RANGE = (0.07, 0.09)   # $10M–$250M deals
LARGE_CAP_RATE_RANGE = (0.055, 0.075)     # $250M+ deals
BLENDED_MIDDLE_MARKET_RATE = 0.08
BLENDED_LARGE_CAP_RATE = 0.065

# Transaction fee scale by deal size
FEE_TIERS = [
    (50_000_000, 0.030),      # < $50M → ~3%
    (500_000_000, 0.020),     # $50M–$500M → ~2%
    (float("inf"), 0.015),    # > $500M → ~1.5%
]

_BENCHMARKS: Optional[dict] = None


def _load_benchmarks() -> dict:
    global _BENCHMARKS
    if _BENCHMARKS is None:
        data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
        path = os.path.join(data_dir, "industry_benchmarks.json")
        with open(path) as f:
            _BENCHMARKS = json.load(f)
    return _BENCHMARKS


@dataclass
class DefaultAssumptions:
    """Smart default assumptions for a given deal context."""
    # Financing
    tax_rate: float = 0.25
    transaction_fees_pct: float = 0.02
    blended_interest_rate: float = 0.08
    interest_rate_range: tuple[float, float] = field(default_factory=lambda: (0.07, 0.09))

    # Industry benchmarks
    ebitda_margin: float = 0.15
    gross_margin: float = 0.45
    sga_pct_revenue: float = 0.20
    working_capital_pct_revenue: float = 0.10
    capex_pct_revenue: float = 0.03
    da_pct_revenue: float = 0.04
    ev_ebitda_low: float = 6.0
    ev_ebitda_median: float = 9.0
    ev_ebitda_high: float = 13.0
    revenue_growth_rate: float = 0.05
    debt_capacity_turns: float = 4.0

    # Synergy benchmarks (as % of combined SG&A or COGS)
    back_office_synergy_pct_sga: float = 0.03
    procurement_synergy_pct_cogs: float = 0.02
    facility_synergy_pct_revenue: float = 0.01

    # PPA defaults
    asset_writeup_pct_ppe: float = 0.10
    intangible_pct_purchase_price: float = 0.15


def get_transaction_fee_pct(deal_size: float) -> float:
    """Return typical transaction fees as % of deal size, scaled by deal size."""
    for threshold, rate in FEE_TIERS:
        if deal_size < threshold:
            return rate
    return 0.015


def get_interest_rate(deal_size: float) -> float:
    """Return blended acquisition debt interest rate based on deal size."""
    if deal_size < 250_000_000:
        return BLENDED_MIDDLE_MARKET_RATE
    return BLENDED_LARGE_CAP_RATE


def get_defaults(
    industry: Industry,
    deal_size: float,
    target_revenue: float,
) -> DefaultAssumptions:
    """
    Return smart default assumptions for a deal.

    Args:
        industry: The target company's industry vertical.
        deal_size: Total acquisition price (enterprise value).
        target_revenue: Target's annual revenue.

    Returns:
        DefaultAssumptions populated with industry-specific benchmarks.
    """
    benchmarks = _load_benchmarks()
    industry_key = industry.value
    ind = benchmarks.get(industry_key, benchmarks["Manufacturing"])  # fallback

    tax_rate = 0.25  # US federal + blended state
    tx_fee_pct = get_transaction_fee_pct(deal_size)
    interest_rate = get_interest_rate(deal_size)

    if deal_size < 250_000_000:
        rate_range = MIDDLE_MARKET_RATE_RANGE
    else:
        rate_range = LARGE_CAP_RATE_RANGE

    ev_ebitda = ind.get("ev_ebitda_multiple_range", {})

    return DefaultAssumptions(
        tax_rate=tax_rate,
        transaction_fees_pct=tx_fee_pct,
        blended_interest_rate=interest_rate,
        interest_rate_range=rate_range,
        ebitda_margin=ind.get("typical_ebitda_margin", 0.15),
        gross_margin=ind.get("typical_gross_margin", 0.45),
        sga_pct_revenue=ind.get("typical_sga_pct_revenue", 0.20),
        working_capital_pct_revenue=ind.get("typical_working_capital_pct_revenue", 0.10),
        capex_pct_revenue=ind.get("typical_capex_pct_revenue", 0.03),
        da_pct_revenue=ind.get("typical_da_pct_revenue", 0.04),
        ev_ebitda_low=ev_ebitda.get("low", 6.0),
        ev_ebitda_median=ev_ebitda.get("median", 9.0),
        ev_ebitda_high=ev_ebitda.get("high", 13.0),
        revenue_growth_rate=ind.get("typical_revenue_growth_rate", 0.05),
        debt_capacity_turns=ind.get("typical_debt_capacity_turns_ebitda", 4.0),
        back_office_synergy_pct_sga=0.03,
        procurement_synergy_pct_cogs=0.02,
        facility_synergy_pct_revenue=0.01,
        asset_writeup_pct_ppe=0.10,
        intangible_pct_purchase_price=0.15,
    )
