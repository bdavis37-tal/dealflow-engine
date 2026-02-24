# Finance Review — Senior Banker Lens

**Date:** 2026-02-24
**Reviewer Perspective:** 15-20 year bulge bracket investment banker / PE fund principal
**Scope:** M&A module only (Module 1)

---

## Executive Summary

The Dealflow Engine's M&A module produces a competent first-pass analysis with a solid circularity solver, reasonable accretion/dilution mechanics, and well-structured sensitivity matrices. However, several gaps would be immediately apparent to a senior finance professional reviewing the output. The most critical: **no Sources & Uses table** (the foundation of every deal presentation), **no contribution analysis**, **missing credit metrics beyond leverage**, **generic year labels instead of fiscal year notation**, and **no base case highlighting in sensitivity tables**.

The underlying financial math is largely sound. The issues are primarily in presentation completeness and a handful of missing analytics that are standard in any bank merger model.

---

## Findings

### Critical (Would undermine credibility with a senior banker)

#### C1. No Sources & Uses of Funds Table

**Gap:** The results dashboard has no Sources & Uses table. This is the single most fundamental output in any deal presentation — it appears on the first page of every investment bank pitch book and merger proxy. A senior banker would look for this before anything else.

**Standard Format:**
```
SOURCES                              USES
──────────────────────────          ──────────────────────────
Cash from Acquirer BS     $XXM      Purchase Price (Equity)  $XXM
New Debt Financing        $XXM      Refinance Target Debt    $XXM
Stock Issuance            $XXM      Transaction Fees         $XXM
──────────────────────────          ──────────────────────────
Total Sources             $XXM      Total Uses               $XXM
```

Sources must equal Uses — this is a check figure. The engine already computes all components (cash_used, new_acquisition_debt, shares_issued × share_price, transaction fees, target debt). This is purely a presentation gap.

**Current state:** Balance sheet at close stores the raw components but doesn't present them in this standard format. The data exists — the presentation doesn't.

**Fix:** Add `SourcesAndUses` output model to backend, compute in `run_deal()`, display as a prominent table in ResultsDashboard.

---

#### C2. Fiscal Year Labels Show "Year 1, Year 2..." Instead of FY Notation

**Gap:** The income statement, EPS chart, and all time-series outputs label columns as "Year 1", "Year 2", etc. This is a hallmark of a student model. Every professional merger model labels projections with actual fiscal years: **FY2026E**, **FY2027E**, etc. (where E = Estimated/Projected).

**Affected locations:**
- `FinancialStatements.tsx` column headers (line 76): `Year {yr.year}`
- `ResultsDashboard.tsx` EPS chart x-axis (line 34): `Year ${yr.year}`
- `SensitivityExplorer.tsx` labels
- Backend `IncomeStatementYear.year` field is an integer (1, 2, 3...) with no fiscal year context

**Fix:** Add `fiscal_year_start` to `DealOutput` computed from the current date. Frontend renders `FY{year}E` labels. Backend computes the base year.

---

#### C3. No Contribution Analysis

**Gap:** Bankers always want to see what each company contributes to the combined entity. This is compared to the ownership split to assess fairness. If the acquirer is giving up 30% ownership but the target only contributes 20% of EBITDA, that's dilutive.

**Standard Format:**
| Metric | Acquirer | Target | % Acquirer | % Target |
|--------|----------|--------|------------|----------|
| Revenue | $XXM | $XXM | XX% | XX% |
| EBITDA | $XXM | $XXM | XX% | XX% |
| Net Income | $XXM | $XXM | XX% | XX% |

Plus: Implied ownership split from deal structure, highlighting any mismatch.

**Current state:** Neither the engine nor the frontend produces this analysis. All the data exists in `DealInput` — it just needs computation and display.

**Fix:** Add `ContributionAnalysis` output model, compute in `run_deal()`, display as a table in ResultsDashboard.

---

#### C4. Missing Credit Metrics Post-Close

**Gap:** The scorecard shows Post-Close Leverage (Debt/EBITDA) but a banker tracks a fuller credit picture:

- **Net Debt / EBITDA** — debt minus cash (often the more relevant metric for credit committees)
- **Interest Coverage Ratio** — EBITDA / Interest Expense. Below 2.0× is a red flag.
- **Fixed Charge Coverage Ratio** — (EBITDA - CapEx) / (Interest + Mandatory Amortization). Stricter test.
- **Debt / Total Capitalization** — debt / (debt + equity). Shows capital structure risk.

These are standard covenant metrics that every lender reviews. Absence would signal the model was built by someone who hasn't been through a credit committee process.

**Current state:** Only `post_close_leverage` (Debt/EBITDA) is computed in the scorecard. Interest expense exists in the income statement but isn't presented as a coverage ratio.

**Fix:** Compute all four credit metrics from existing data, add to `DealOutput`, display as a "Credit Profile" section or additional scorecard metrics.

---

### Important (Noticeable to a senior person)

#### I1. Pro Forma Income Statement Lacks Adjustment Column

**Gap:** The financial statements show a single set of combined numbers per year. A standard bank merger model shows the pro forma in a multi-column format:

```
                    Acquirer  |  Target  |  Pro Forma Adj  |  Combined
Revenue              $XXM        $XXM         $XXM             $XXM
EBITDA               $XXM        $XXM         $XXM             $XXM
...
```

The Pro Forma Adjustments column shows: incremental D&A from PPA, new interest expense from acquisition debt, synergies (phased), transaction costs (Year 1), and tax effects of adjustments. This makes the bridge from standalone to combined fully transparent.

**Current state:** `IncomeStatementYear` stores only the combined totals. Individual components exist in the engine calculation but are not preserved for display.

**Impact:** A senior banker reviewing the income statement can't trace how each line item is derived. They have to trust the combined numbers without being able to verify the bridge.

**Fix:** Expand `IncomeStatementYear` to include breakdown fields (acquirer_revenue, target_revenue, synergy_revenue, etc.). The frontend can show the multi-column view in Deep mode, combined view in Quick mode.

---

#### I2. No Implied Valuation Metrics

**Gap:** The scorecard shows entry EV/EBITDA but a banker expects the full implied valuation picture:

- **Enterprise Value** (stated explicitly — purchase price + assumed debt - cash acquired)
- **Equity Value** (purchase price for the equity, if different from EV)
- **EV / Revenue** (LTM)
- **EV / EBITDA** (LTM — already shown)
- **EV / EBITDA** (NTM — first projected year)
- **Price / Earnings** (if applicable)

LTM = Last Twelve Months (historical). NTM = Next Twelve Months (projected). Showing both tells you whether you're paying for the company as it is today or as it will be next year.

**Current state:** Only entry EV/EBITDA is computed. Enterprise Value is essentially the acquisition_price but isn't broken out with its components.

**Fix:** Add implied valuation metrics to `DealOutput`, compute in `run_deal()`, display in a compact valuation summary section.

---

#### I3. Sensitivity Table Missing Base Case Highlight

**Gap:** In bank merger models, the base case cell in each sensitivity matrix is always highlighted (bold, border, or distinct color) so the user can immediately see where the current assumptions sit relative to the range. The current sensitivity tables show no distinction between the base case cell and any other cell.

**Current state:** `SensitivityExplorer.tsx` renders all cells identically via `HeatmapCell`. The 0% premium row and 100% synergy achievement column contain the base case, but nothing visually distinguishes it.

**Fix:** Pass base case row/col indices from the backend (or compute on frontend from the 0/100 values). Add visual highlight (ring/border) to the base case cell in the heatmap.

---

#### I4. Sensitivity Table Axis Labels Show Deltas Only

**Gap:** Sensitivity axis labels show relative values (e.g., "-20, -10, 0, 10, 20, 30, 40" for Price Premium) without showing the actual absolute values. A banker wants to see the actual purchase prices alongside the premiums.

**Current state:** `row_values` and `col_values` are rendered as-is (e.g., `cv.toFixed(0)`). For the Purchase Price vs Synergies matrix, rows show premium percentages and columns show synergy achievement percentages.

**Fix:** Add `row_display_labels` and `col_display_labels` to `SensitivityMatrix` with formatted absolute values (e.g., "$45M (-10%)", "$50M (Base)", "$55M (+10%)").

---

#### I5. Deal Returns Lack Exit Math Transparency

**Gap:** The returns analysis shows IRR and MOIC scenarios but doesn't clearly expose the underlying math:

- **Entry equity check** — how much equity is going in at close
- **Exit EV → Exit Equity bridge** — exit_multiple × exit_EBITDA - net_debt = equity proceeds
- **Cash flow to equity** — annual FCF after debt service (the intermediate stream that feeds IRR)

A PE professional wants to see the math, not just the answer. They need to verify the assumptions.

**Current state:** `ReturnsAnalysis` has `entry_multiple` and `scenarios[]` with IRR/MOIC. The equity invested calculation and exit math are internal to `returns.py` but not exposed in the output.

**Fix:** Add `equity_invested`, `exit_equity_bridge` (showing the math), and `annual_fcf_to_equity` to the returns output. Display in a dedicated returns detail section.

---

#### I6. Interest Expense Not Broken Out in Income Statement

**Gap:** The income statement shows a single "Interest Expense" line that blends existing debt service with new acquisition financing interest. A banker expects to see:
- Existing acquirer interest (pre-deal debt service)
- Incremental acquisition interest (new debt from this transaction)

This distinction matters because the incremental interest is the deal-specific drag on accretion.

**Current state:** `interest_expense` in `IncomeStatementYear` is the total from the debt solver (which only models acquisition debt). Pre-existing debt interest isn't modeled.

**Fix:** This is related to I1 (adjustment column). When the pro forma shows the multi-column format, existing interest on pre-deal debt would be in the Acquirer standalone column, and incremental acquisition interest in the Pro Forma Adjustments column.

---

### Nice-to-Have (Polish — deferred to backlog)

#### N1. Football Field Valuation Chart
A horizontal bar chart showing implied valuation ranges from multiple methodologies (comparable companies, precedent transactions, DCF, LBO). Would require additional valuation inputs beyond what the current engine collects.

#### N2. Synergy Phase-in Chart
Visual timeline showing cost synergies and revenue synergies ramping to full run-rate. The data exists in the engine (linear phasing per SynergyItem) but isn't visualized separately.

#### N3. Debt Paydown Waterfall Chart
Visual showing year-by-year debt reduction across tranches. The data exists in the circularity solver output but isn't surfaced to the frontend.

#### N4. Working Capital Modeling
Working capital changes are assumed static in cash flow projections. A more rigorous model would project NWC as a percentage of revenue and model year-over-year changes.

#### N5. Net Operating Loss (NOL) Carryforwards
Tax rate is constant across all years. A real model might account for NOLs from transaction costs or pre-existing target losses that offset future taxable income.

#### N6. Refinancing Risk Modeling
Current model assumes all debt can be refinanced at the same rate through maturity. A stress scenario for rate resets would add depth.

#### N7. Pro Forma Balance Sheet Projection
Currently only the opening balance sheet at close is modeled. Year-over-year BS projections (building assets, debt paydown, retained earnings) would complete the three-statement model.

#### N8. Accounting for Negative Numbers in Parentheses
The income statement uses formatAccounting() which wraps negatives in parentheses, but the sign convention isn't fully consistent. Expenses shown as negative numbers with a minus sign are technically correct but not the convention in professional financial statements (where expenses are positive numbers in a line that is subtracted structurally).

#### N9. Transaction Fee Breakdown
Advisory, legal, and financing fees are lumped into a single transaction_fees_pct + advisory_fees. Banks typically break these out: M&A advisory, debt commitment, legal, accounting, and other.

#### N10. Basis Points Display for Interest Rate Sensitivity
The interest rate sensitivity table shows percentages (5%, 6%, 7%...). In certain contexts, bankers use basis points (500bps, 600bps). The current approach is acceptable but adding "+150bps" secondary labels would add polish.

---

## Implementation Priority

### This Build (Critical + Important)
1. **C1** Sources & Uses table
2. **C2** Fiscal year labeling
3. **C3** Contribution analysis
4. **C4** Credit metrics (interest coverage, FCCR, debt/total cap)
5. **I1** Pro forma income statement adjustment columns (Deep mode only)
6. **I2** Implied valuation metrics
7. **I3** Sensitivity base case highlight
8. **I4** Sensitivity absolute axis labels
9. **I5** Deal returns transparency

### Backlog (Nice-to-Have)
N1 through N10 documented above — implement in future iterations.

---

## Financial Logic Review Notes

### Things Done Well
- Circularity solver is robust (average-balance interest, convergence tolerance of $1/0.01%)
- PPA mechanics follow ASC 805 correctly (DTL on step-ups, goodwill as residual)
- Synergy phasing is linear, which is conservative and defensible
- Transaction costs correctly expensed in Year 1 per ASC 805
- Sensitivity matrices use full engine re-runs per cell (accurate, not approximated)

### Calculation Accuracy Notes
- Gross margin approximation (EBITDA margin + 20%) is a reasonable simplification for a first-pass model
- Standalone EPS growing at flat 3% is acceptable for a merger model (not a DCF)
- Tax calculation uses a flat effective rate, which is standard for merger models (vs. marginal rates in a full corporate model)
- The accretion/dilution bridge reconciles exactly by construction (uses a residual "tax impact" reconciling item), which is the right approach
