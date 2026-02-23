# Licensed under the Business Source License 1.1 — see LICENSE file for details
"""
Purchase Price Allocation (PPA) calculations per ASC 805 Business Combinations.

At acquisition close, the purchase price is allocated to:
  1. Net identifiable assets at fair value (tangible + intangible)
  2. Residual = Goodwill (not amortized, tested annually for impairment)

The key income statement impact:
  - Incremental D&A from asset step-ups (depreciates over useful life)
  - Intangible amortization (amortizes over useful life)
  - Goodwill (no P&L impact unless impaired — excluded from our model)

Deferred Tax Liability (DTL):
  Under ASC 805, asset step-ups and intangible allocations create temporary
  differences between book and tax basis. A DTL is recognized for these
  differences: DTL = (asset_writeup + identifiable_intangibles) × tax_rate.
  The DTL reduces the fair value of net identifiable assets (FVNA), which
  increases goodwill — this is standard practice in M&A accounting.
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
    deferred_tax_liability: float   # DTL on step-ups: (writeup + intangibles) × tax_rate
    goodwill: float                 # Residual = Price - FVNA (after DTL)
    # Annual incremental charges
    incremental_da_annual: float    # From asset writeup (straight-line over useful life)
    incremental_amort_annual: float # From intangibles (straight-line over useful life)
    total_incremental_annual: float # Combined annual P&L charge


def compute_ppa(deal: DealInput) -> PPAResult:
    """
    Perform purchase price allocation for a transaction.

    Goodwill = Purchase Price - Fair Value of Net Identifiable Assets (ASC 805)

    FVNA = Target book equity
         + PP&E step-up (asset_writeup)
         + Identifiable intangibles
         - Deferred tax liability on step-ups  (ASC 805 / ASC 740)

    The DTL arises because step-ups increase book basis above tax basis,
    creating a future taxable temporary difference. DTL = step-ups × tax_rate.

    Args:
        deal: Complete deal input including PPA assumptions.

    Returns:
        PPAResult with goodwill, DTL, and annual incremental charges.
    """
    target = deal.target
    ppa = deal.ppa
    tax_rate = deal.acquirer.tax_rate

    # Approximate target net assets (book equity)
    # = cash + NWC - pre-existing debt (rough proxy; a real model uses full BS)
    net_assets_book = (
        target.cash_on_hand
        + target.working_capital
        - target.total_debt
    )

    # Deferred tax liability on step-ups (ASC 805 / ASC 740)
    # The acquirer steps up PP&E and intangibles to FV but tax basis remains at cost,
    # so a DTL is established: DTL = taxable temporary difference × tax_rate.
    taxable_temporary_difference = ppa.asset_writeup + ppa.identifiable_intangibles
    dtl = taxable_temporary_difference * tax_rate

    # Fair value of net identifiable assets (FVNA)
    # FVNA = Book value + step-ups + intangibles - DTL
    fvna = net_assets_book + ppa.asset_writeup + ppa.identifiable_intangibles - dtl

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
        deferred_tax_liability=dtl,
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
