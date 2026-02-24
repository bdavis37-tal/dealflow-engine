# Architecture — Dealflow Engine

## System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      React Frontend                          │
│                                                              │
│  ┌───────────┐  ┌──────────────┐  ┌────────────────┐       │
│  │  M&A Flow │  │ Startup Flow │  │ VC Investor Flow│       │
│  │  (6 steps)│  │  (4 steps)   │  │  (2 steps)     │       │
│  └─────┬─────┘  └──────┬───────┘  └───────┬────────┘       │
│        │               │                   │                 │
│  ┌─────▼─────┐  ┌──────▼───────┐  ┌───────▼────────┐       │
│  │Results    │  │Startup       │  │VCDashboard     │       │
│  │Dashboard  │  │Dashboard     │  │+ Sub-panels    │       │
│  └───────────┘  └──────────────┘  └────────────────┘       │
│                                                              │
│  State: useDealState | useStartupState | useVCState          │
│  Persistence: localStorage (inputs only, never outputs)      │
└──────────────────────────┬───────────────────────────────────┘
                           │ HTTP / SSE
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                   FastAPI Backend                             │
│                                                              │
│  ┌──────────┐  ┌───────────┐  ┌─────────┐  ┌──────────┐   │
│  │/api/v1/* │  │/api/ai/*  │  │/api/     │  │/api/vc/* │   │
│  │M&A routes│  │AI routes  │  │startup/* │  │VC routes │   │
│  │(analyze, │  │(chat, SSE │  │(value,   │  │(evaluate,│   │
│  │ defaults)│  │ narrative)│  │ benchmk) │  │ portfolio│   │
│  └────┬─────┘  └─────┬─────┘  └────┬─────┘  └────┬─────┘   │
│       │              │              │              │          │
│  ┌────▼──────────────▼──────────────▼──────────────▼────┐   │
│  │                 Engine Layer                           │   │
│  │                                                       │   │
│  │  ┌─────────────┐ ┌───────────┐ ┌───────────────┐    │   │
│  │  │financial_   │ │startup_   │ │vc_return_     │    │   │
│  │  │engine.py    │ │engine.py  │ │engine.py      │    │   │
│  │  │             │ │           │ │               │    │   │
│  │  │• run_deal() │ │• run_     │ │• run_vc_deal_ │    │   │
│  │  │• PPA        │ │  startup_ │ │  evaluation() │    │   │
│  │  │• Debt solver│ │  valuation│ │• Waterfall    │    │   │
│  │  │• Sensitivity│ │• 4 methods│ │• Portfolio    │    │   │
│  │  │• Returns    │ │• Blending │ │• Scenarios    │    │   │
│  │  │• Risk       │ │           │ │               │    │   │
│  │  └─────────────┘ └───────────┘ └───────────────┘    │   │
│  │                                                       │   │
│  │  ┌─────────────────────────────────────────────┐     │   │
│  │  │ Shared: models.py | ai_modifier.py | data/  │     │   │
│  │  └─────────────────────────────────────────────┘     │   │
│  └───────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ AI Service (optional) — Claude API via ai_service.py  │   │
│  │ • Narrative generation  • Chat co-pilot               │   │
│  │ • Deal parsing          • Field explanations          │   │
│  │ • Scenario stories      • Caching (in-process LRU)    │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Engine Modules

### M&A Financial Engine (`financial_engine.py`)

The core computation pipeline for M&A deal modeling:

1. **Purchase Price Allocation (PPA)** — ASC 805 compliant allocation of purchase price to tangible assets, intangibles, and residual goodwill. Computes deferred tax liability on step-ups.

2. **Circularity Solver** — Resolves the circular dependency between debt balance, interest expense, net income, free cash flow, and debt paydown. Uses iterative convergence with damping factor (0.5) and tolerance of $1 or 0.01%. Supports straight-line, interest-only, and bullet amortization across multiple tranches.

3. **Pro Forma Income Statement** — 5-7 year projection combining acquirer and target financials with synergy phase-in, PPA charges, and debt service.

4. **Accretion/Dilution Bridge** — Reconciled EPS walk from standalone to pro forma. Components: target earnings contribution, interest drag, D&A adjustment, synergy benefit, share dilution, and a reconciling tax/residual item that ensures exact tie to IS.

5. **Sensitivity Matrices** — Three 2D heatmaps (price vs synergy, financing mix vs growth, entry multiple vs exit multiple). Each cell re-runs the full engine with `include_sensitivity=False` to prevent recursive re-entry.

6. **Returns Analysis** — IRR (Newton-Raphson) and MOIC at exit years 3/5/7 across a range of exit multiples. Uses cumulative FCF roll-forward for cash balance at exit.

7. **Risk Analyzer** — Six automated risk checks: leverage, purchase price premium, synergy concentration, interest coverage, debt service coverage, customer concentration. Defense deals add four more: DoD concentration, contract vehicle count, clearance utilization, IP ownership.

8. **Deal Scorecard & Verdict** — 8-12 metrics with health status (good/fair/poor/critical). Verdict (green/yellow/red) based on Year 1 accretion with defense backlog adjustment.

### Defense Vertical & AI Modifier

The Defense & National Security vertical includes:

- **Defense Positioning** — Clearance premiums (unclassified → SAP), certification premiums (FedRAMP, IL4-6, CMMC), program of record premiums. These stack and are reported separately.
- **AI-Native Toggle** — Graduated premium system. Verticals are classified as `frozen_on` (always AI), `frozen_off` (never AI), `default_on`, or `default_off`. The premium adjusts benchmark ranges based on vertical-specific multipliers.
- **Design Decision** — Graduated premiums (0.3× to 1.5× per vertical) rather than binary on/off. This reflects the reality that AI readiness varies by sector.

### Startup Valuation Engine (`startup_engine.py`)

Four valuation methods run in parallel and blend:

1. **Berkus Method** — Qualitative 5-dimension scoring (pre-seed/seed only)
2. **Scorecard Method** — 7-factor weighted comparison to stage median
3. **Risk Factor Summation** — 12 risk categories with ±2 adjustments from base
4. **Comparable Benchmarks** — Direct P25/P50/P75 lookup from benchmark data

Output includes SAFE conversion mechanics, dilution path modeling, and investor scorecard.

### VC Return Engine (`vc_return_engine.py`)

Fund-level analysis for VC partners evaluating deals:

- **Ownership Math** — Entry % through dilution stack to exit
- **Fund Returner Thresholds** — Exit EV needed at 1x, 3x, 5x fund size
- **Scenario Modeling** — Bear/base/bull with probability-weighted expected value
- **Waterfall** — Multi-class liquidation preference distribution
- **Portfolio Analysis** — TVPI/DPI/RVPI, concentration, reserve adequacy
- **Governance Tools** — QSBS eligibility, anti-dilution modeling, bridge analysis

## Data Flow: M&A Deal Input to Output

```
User Input (6 steps)
    │
    ▼
DealInput (Pydantic model)
    │
    ├──► compute_ppa() ──────────────► goodwill, incremental D&A
    │
    ├──► build_debt_schedule() ──────► interest by year, ending balances
    │         (iterative solver)
    │
    ├──► 5-year pro forma loop ──────► IncomeStatementYear[]
    │         (revenue, COGS, SGA, EBITDA, EBIT, interest, tax, NI, EPS)
    │
    ├──► accretion_dilution_bridge() ► AccretionDilutionBridge[]
    │
    ├──► compute_returns() ──────────► IRR/MOIC scenarios
    │
    ├──► generate_sensitivity() ─────► 3 × SensitivityMatrix
    │         (runs engine N×M times)
    │
    ├──► analyze_risks() ────────────► RiskItem[]
    │
    ├──► build_scorecard() ──────────► ScorecardMetric[]
    │
    └──► assign_verdict() ───────────► green | yellow | red
    │
    ▼
DealOutput (complete JSON response)
    │
    ▼
ResultsDashboard (React)
    ├── Verdict banner
    ├── EPS accretion/dilution chart
    ├── Deal scorecard with health indicators
    ├── Risk panel
    ├── Sensitivity heatmaps (interactive)
    ├── Pro forma financial table
    └── AI narrative + chat co-pilot (optional)
```

## Key Design Decisions

### Financial Accuracy Over Speed
Sensitivity matrices run the full engine per cell (~100-200 cells × 3 matrices). This is slow (~5s) but intentional — approximations could mislead users making real M&A decisions. Each cell is isolated via `model_copy(deep=True)`.

### Circularity Solver Approach
The debt-interest-NI-FCF-paydown circular dependency is solved iteratively with a damping factor rather than algebraically. This handles any number of tranches with different amortization types. Convergence threshold ($1 or 0.01%) is tighter than most commercial models.

### AI Augments, Never Replaces
The deterministic engine is the source of truth for all numbers. Claude AI provides interpretation (narratives, explanations, scenario stories) but never generates or modifies financial figures. All AI output is clearly badged in the UI.

### Smart Defaults Philosophy
Every input field has an industry-specific default from benchmark data. This means a user can model a deal with just 4 inputs (acquirer name, target name, deal size, industry) and get a meaningful result. The smart defaults come from `industry_benchmarks.json` (20 verticals).

### Three Independent Engines
M&A, Startup, and VC engines share no computational code. They can be used independently via their API endpoints. The frontend is the integration point. This was a deliberate choice to keep each engine's financial logic self-contained and auditable.

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, Radix UI |
| Backend | Python 3.11+, FastAPI, Pydantic v2, Uvicorn |
| AI (optional) | Anthropic Claude API via `anthropic` SDK |
| Testing | pytest (backend), Vitest (frontend) |
| Styling | Dark-mode only, Tailwind CSS, Lucide icons |
| Deployment | Docker Compose (frontend + backend) |
