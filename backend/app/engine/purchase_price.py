"""
Purchase Price Allocation (PPA) calculations per ASC 805 Business Combinations.

At acquisition close, the purchase price is allocated to:
  1. Net identifiable assets at fair value (tangible + intangible)
  2. Residual = Goodwill (not amortized, tested annually for impairment)

The key income statement impact:
  - Incremental D&A from asset step-ups (depreciates over useful life)
  - Intangible amortization (amortizes over useful life)
  - Goodwill (no P&L impact unless impaired — excluded from our model)
"""
from __future__ import annotations

from dataclasses import dataclass

from .models import DealInput, PurchasePriceAllocation as PPAInput


@dataclass
class PPAResult:
    """Results of purchase price allocation."""
    purchase_price: float           # Enterprise value paid
    net_assets_book_value: float    # Target's pre-deal book equity (approx)
    asset_writeup: float            # PP&E fair value step-up
    identifiable_intangibles: float # Customer relationships, IP, trade names, etc.
    goodwill: float                 # Residual = Price - FVNA
    # Annual incremental charges
    incremental_da_annual: float    # From asset writeup (straight-line over useful life)
    incremental_amort_annual: float # From intangibles (straight-line over useful life)
    total_incremental_annual: float # Combined annual P&L charge


def compute_ppa(deal: DealInput) -> PPAResult:
    """
    Perform purchase price allocation for a transaction.

    Goodwill = Purchase Price - Fair Value of Net Identifiable Assets (ASC 805)
    Fair Value of Net Identifiable Assets = Target book equity + asset step-ups + intangibles
    - Target's assumed debt (refinanced/assumed into the transaction)
    + Target's cash (acquired)

    Args:
        deal: Complete deal input including PPA assumptions.

    Returns:
        PPAResult with goodwill and annual incremental charges.
    """
    target = deal.target
    ppa = deal.ppa

    # Approximate target net assets (book equity) = assets - liabilities
    # We use a simplified proxy: revenue * NWC% as proxy for book equity
    # In a real model this would use the target's balance sheet directly.
    # Here we estimate net assets = cash + NWC - debt (rough proxy)
    net_assets_book = (
        target.cash_on_hand
        + target.working_capital
        - target.total_debt
    )

    # Fair value of net identifiable assets (FVNA)
    # FVNA = Book value + asset step-ups + identifiable intangibles
    fvna = net_assets_book + ppa.asset_writeup + ppa.identifiable_intangibles

    # Goodwill is the residual — what you paid above the fair value of what you got
    # Goodwill = Purchase Price - FVNA
    goodwill = max(0.0, target.acquisition_price - fvna)

    # Annual D&A from asset writeup: straight-line over useful life
    # Per ASC 805, PP&E is stepped up to fair value and depreciated from that higher basis
    incremental_da = (
        ppa.asset_writeup / ppa.asset_writeup_useful_life
        if ppa.asset_writeup_useful_life > 0 and ppa.asset_writeup > 0
        else 0.0
    )

    # Annual amortization of identifiable intangibles: straight-line over useful life
    # Examples: customer lists (7-10yr), trade names (10-20yr), non-competes (3-5yr)
    incremental_amort = (
        ppa.identifiable_intangibles / ppa.intangible_useful_life
        if ppa.intangible_useful_life > 0 and ppa.identifiable_intangibles > 0
        else 0.0
    )

    return PPAResult(
        purchase_price=target.acquisition_price,
        net_assets_book_value=net_assets_book,
        asset_writeup=ppa.asset_writeup,
        identifiable_intangibles=ppa.identifiable_intangibles,
        goodwill=goodwill,
        incremental_da_annual=incremental_da,
        incremental_amort_annual=incremental_amort,
        total_incremental_annual=incremental_da + incremental_amort,
    )


def get_transaction_costs(deal: DealInput) -> float:
    """
    Compute total transaction costs (fees) for the deal.
    These are expensed under ASC 805 (not capitalized into goodwill).

    Returns:
        Total transaction costs in dollars.
    """
    deal_size = deal.target.acquisition_price
    pct_fee = deal.structure.transaction_fees_pct
    advisory = deal.structure.advisory_fees
    return deal_size * pct_fee + advisory
