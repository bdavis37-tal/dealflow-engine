"""
Smart defaults engine — returns sensible pre-fills based on industry and deal size.
The versioned registry distinguishes sourced observations from inherited
assumptions; defaults are editable inputs, not verified financing quotes.
"""
from __future__ import annotations
from .benchmark_registry import BenchmarkView, policy

from dataclasses import dataclass, field
from typing import Optional

from .models import Industry


# ---------------------------------------------------------------------------
# Interest rate assumptions (update periodically)
# Inherited illustrative rate ranges. Active blended defaults come from the
# selected release's policy records and are explicitly classified as assumptions.
# NOTE: all deal-size thresholds are in MILLIONS USD per project convention
# (e.g. 250.0 = $250M).
# ---------------------------------------------------------------------------
MIDDLE_MARKET_RATE_RANGE = (0.09, 0.11)   # $10M–$250M deals
LARGE_CAP_RATE_RANGE = (0.075, 0.09)      # $250M+ deals
BLENDED_MIDDLE_MARKET_RATE = 0.10
BLENDED_LARGE_CAP_RATE = 0.08

# Deal size above which large-cap financing rates apply (millions USD)
LARGE_CAP_DEAL_SIZE_THRESHOLD = 250.0

# Transaction fee scale by deal size (thresholds in millions USD)
FEE_TIERS = [
    (50.0, 0.030),            # < $50M → ~3%
    (500.0, 0.020),           # $50M–$500M → ~2%
    (float("inf"), 0.015),    # > $500M → ~1.5%
]

_BENCHMARKS: Optional[dict] = None


def _load_benchmarks():
    return BenchmarkView("ma")


@dataclass
class DefaultAssumptions:
    """Smart default assumptions for a given deal context."""
    # Financing (H1 2026 vintage — see rate constants above)
    tax_rate: float = 0.25
    transaction_fees_pct: float = 0.02
    blended_interest_rate: float = 0.10
    interest_rate_range: tuple[float, float] = field(default_factory=lambda: (0.09, 0.11))

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
    """Return typical transaction fees as % of deal size.

    Args:
        deal_size: Acquisition enterprise value in MILLIONS USD (e.g. 200.0 = $200M).
    """
    for threshold, rate in FEE_TIERS:
        if deal_size < threshold:
            return rate
    return 0.015


def get_interest_rate(deal_size: float) -> float:
    """Return blended acquisition debt interest rate based on deal size.

    Args:
        deal_size: Acquisition enterprise value in MILLIONS USD (e.g. 200.0 = $200M).
    """
    if deal_size < LARGE_CAP_DEAL_SIZE_THRESHOLD:
        return policy('financing', 'middle_market')
    return policy('financing', 'large_cap')


def get_defaults(
    industry: Industry,
    deal_size: float,
    target_revenue: float,
) -> DefaultAssumptions:
    """
    Return smart default assumptions for a deal.

    Args:
        industry: The target company's industry vertical.
        deal_size: Total acquisition price (enterprise value) in MILLIONS USD.
        target_revenue: Target's annual revenue in MILLIONS USD.

    Returns:
        DefaultAssumptions populated with industry-specific benchmarks.
    """
    benchmarks = _load_benchmarks()
    industry_key = industry.value
    ind = benchmarks[industry_key]  # Exact industry; no unrelated fallback

    tax_rate = 0.25  # US federal + blended state
    tx_fee_pct = get_transaction_fee_pct(deal_size)
    interest_rate = get_interest_rate(deal_size)

    if deal_size < LARGE_CAP_DEAL_SIZE_THRESHOLD:
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
