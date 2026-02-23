# CLAUDE.md — Dealflow Engine

## Project Overview

**Dealflow Engine** is a full-stack deal intelligence platform covering the three core activities in private-market deal-making: M&A financial modeling, startup valuation, and venture capital fund-seat analysis. Each module runs a deterministic computation engine, delivers plain-English results dashboards, and is augmented by an optional Claude AI co-pilot.

The platform is organized as three independent but co-located engines sharing a single frontend (mode selector in `App.tsx`) and backend (FastAPI with dedicated route groups).

**Key constraint:** The deterministic financial engines are the source of truth. AI features augment and interpret — they never replace computed numbers.

---

## Essential Commands

### Backend
```bash
# Install (from /backend)
pip install -e ".[dev]"

# Dev server (hot reload)
uvicorn app.main:app --reload --port 8000

# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_engine.py -v

# Lint
ruff check app/

# Format
ruff format app/
```

### Frontend
```bash
# Install (from /frontend)
npm install

# Dev server — proxies /api → localhost:8000
npm run dev

# Type-check (no emit)
npm run typecheck

# Build for production
npm run build

# Run tests
npm test

# Lint
npm run lint
```

### Docker (full stack)
```bash
# Start everything
docker compose up

# Rebuild after dependency changes
docker compose up --build

# Frontend: http://localhost:3000
# Backend API: http://localhost:8000
# Swagger docs: http://localhost:8000/docs
```

---

## Repository Structure

```
dealflow-engine/
├── backend/
│   ├── app/
│   │   ├── main.py                         # FastAPI entry point (all 4 routers)
│   │   ├── api/
│   │   │   ├── routes.py                   # /api/v1/* (M&A: analyze, defaults, health)
│   │   │   ├── ai_routes.py                # /api/ai/* (parse, narrative, chat)
│   │   │   ├── startup_routes.py           # /api/startup/* (value, benchmarks)
│   │   │   └── vc_routes.py                # /api/vc/* (evaluate, portfolio, waterfall, etc.)
│   │   ├── engine/                         # Core computation — 3 independent engines
│   │   │   ├── models.py                   # M&A Pydantic models — source of truth for M&A shapes
│   │   │   ├── financial_engine.py         # M&A orchestrator: run_deal()
│   │   │   ├── circularity_solver.py       # Debt/interest iterative solver
│   │   │   ├── purchase_price.py           # PPA / ASC 805
│   │   │   ├── returns.py                  # IRR / MOIC
│   │   │   ├── sensitivity.py              # 2D sensitivity matrices
│   │   │   ├── risk_analyzer.py            # 6 automated risk checks
│   │   │   ├── defaults.py                 # Industry benchmark lookups
│   │   │   ├── startup_models.py           # Startup valuation Pydantic models
│   │   │   ├── startup_engine.py           # 4-method startup valuation: run_startup_valuation()
│   │   │   ├── vc_fund_models.py           # VC fund-seat Pydantic models
│   │   │   └── vc_return_engine.py         # VC return engine: run_vc_deal_evaluation()
│   │   ├── services/
│   │   │   └── ai_service.py               # Claude API client, caching, streaming
│   │   └── data/
│   │       ├── industry_benchmarks.json    # 20 M&A industry verticals
│   │       ├── startup_valuation_benchmarks.json  # 12 startup verticals × 3 stages
│   │       └── vc_benchmarks.json          # VC fund construction, exit data, stage transitions
│   ├── tests/
│   │   ├── test_engine.py
│   │   ├── test_circularity.py
│   │   ├── test_sensitivity.py
│   │   └── fixtures/                       # JSON fixture deals for tests
│   └── pyproject.toml
│
└── frontend/
    └── src/
        ├── App.tsx                         # AppMode selector (ma | startup | vc) + route orchestrator
        ├── types/
        │   ├── deal.ts                     # M&A TS interfaces — mirrors models.py
        │   ├── startup.ts                  # Startup TS interfaces — mirrors startup_models.py
        │   └── vc.ts                       # VC TS interfaces — mirrors vc_fund_models.py
        ├── hooks/
        │   ├── useDealState.ts             # M&A state + localStorage persistence
        │   ├── useStartupState.ts          # Startup valuation state + localStorage
        │   └── useVCState.ts               # VC fund + deal state + localStorage
        ├── lib/
        │   ├── api.ts                      # M&A + startup API calls
        │   ├── ai-api.ts                   # AI API calls (streaming SSE support)
        │   ├── vc-api.ts                   # VC API calls
        │   └── formatters.ts               # Currency, pct, multiple formatters
        ├── components/
        │   ├── flow/                       # M&A Steps 1–6 + ConversationalEntry
        │   │   └── startup/                # Startup Steps 1–5 (overview, team, traction, market, review)
        │   ├── output/                     # M&A results dashboard, AI panels
        │   │   └── startup/                # StartupDashboard — valuation results
        │   ├── vc/                         # VC components (7 total):
        │   │   ├── VCFundSetup.tsx         #   Fund profile configuration
        │   │   ├── VCQuickScreen.tsx        #   Deal screening input
        │   │   ├── VCDashboard.tsx          #   Results overview
        │   │   ├── VCOwnershipPanel.tsx     #   Ownership math + dilution stack
        │   │   ├── VCReturnScenarios.tsx    #   Bear/base/bull return model
        │   │   ├── WaterfallAnalyzer.tsx    #   Liquidation preference waterfall
        │   │   ├── VCPortfolioDash.tsx      #   Portfolio construction dashboard
        │   │   ├── VCGovernanceTools.tsx     #   QSBS, anti-dilution, bridge, pro-rata
        │   │   └── ICMemoExport.tsx         #   Auto-generated IC memo
        │   ├── inputs/                     # GuidedInput, CurrencyInput, SynergyCards
        │   ├── layout/                     # AppShell, StepIndicator, ModeToggle
        │   └── shared/                     # MetricCard, HeatmapCell, AIBadge, StreamingText
        └── styles/globals.css
```

---

## Architecture & Data Flow

### App Modes

The frontend has three modes, selectable via `AppModeSelector` in `App.tsx`:

| Mode | State Hook | API Prefix | Engine Entry Point |
|------|-----------|------------|-------------------|
| `ma` | `useDealState` | `/api/v1/` | `run_deal()` |
| `startup` | `useStartupState` | `/api/startup/` | `run_startup_valuation()` |
| `vc` | `useVCState` | `/api/vc/` | `run_vc_deal_evaluation()` |

Each mode has its own shell (branding color: blue for M&A, purple for Startup, emerald for VC), step indicator, state hook, and results dashboard. The modes are independent — switching modes does not clear state.

### Module 1: M&A Deal Modeling

**Input flow:** 6 steps → `useDealState` assembles `DealInput` → `POST /api/v1/analyze` → `DealOutput`

```
DealInput {
  acquirer: AcquirerProfile    # Buyer financials
  target: TargetProfile        # Target financials + acquisition_price
  structure: DealStructure     # cash% + stock% + debt% (must sum to 1.0)
  ppa: PurchasePriceAllocation # Asset writeups + intangible allocations
  synergies: SynergyAssumptions
  mode: 'quick' | 'deep'
  projection_years: 5
}
```

**Engine sequence** (`financial_engine.py: run_deal()`):
```
1. compute_ppa()               → goodwill, incremental D&A
2. build_debt_schedule()       → iterative circularity solver (up to 100 iters)
3. 5-year pro forma loop       → combined income statement per year
4. accretion_dilution_bridge() → EPS bridge breakdown
5. compute_returns()           → IRR/MOIC at exit years 3/5/7
6. generate_all_sensitivity_matrices() → 3 heatmaps (~100–200 engine calls each)
7. analyze_risks()             → up to 6 RiskItem flags
8. build_scorecard()           → 8–12 ScorecardMetric items
9. assign_verdict()            → 'green' | 'yellow' | 'red'
```

**Output:** `DealOutput` JSON → `ResultsDashboard` renders verdict, EPS chart, scorecard, risk panel, sensitivity heatmaps, pro forma table, AI narrative, and chat co-pilot.

### Module 2: Startup Valuation

**Input flow:** 4 steps (overview/fundraise, team, traction/product, market) → `useStartupState` assembles `StartupInput` → `POST /api/startup/value` → `StartupValuationOutput`

```
StartupInput {
  company_name: str
  team: TeamProfile            # Founders, exits, domain expertise, backgrounds
  traction: TractionMetrics    # MRR, ARR, growth, NRR, burn, customers
  product: ProductProfile      # Stage (idea→scaling), IP, data moat, regulatory
  market: MarketProfile        # TAM, SAM, growth rate, competitive moat
  fundraise: FundraisingProfile # Stage, vertical, geography, raise amount, instrument, SAFE terms
}
```

**Engine** (`startup_engine.py: run_startup_valuation()`):
- **Berkus Method** — 5-dimension qualitative scoring (idea, management, prototype, relationships, rollout)
- **Scorecard Method** — 7-factor weighted comparison to stage median (team 30%, market 25%, product 15%, traction 10%, competition 10%, partnerships 5%, need for funding 5%)
- **Risk Factor Summation** — 12 risk categories, each -2 to +2 adjustment from vertical-specific base
- **Comparable Benchmarks** — Direct P25/P50/P75 lookup from `startup_valuation_benchmarks.json`

Output: blended pre-money valuation, method breakdown, dilution path (pre-seed → seed → Series A), SAFE conversion mechanics, investor scorecard flags, market percentile, and verdict (strong / fair / stretched / at_risk).

**Benchmark data:** 12 verticals (AI/ML Infrastructure, AI-Enabled SaaS, B2B SaaS, Fintech, Healthtech, Biotech/Pharma, Deep Tech/Hardware, Consumer, Climate/Energy, Marketplace, Vertical SaaS, Developer Tools) × 3 stages (pre-seed, seed, Series A). Sourced from Carta 2024, PitchBook-NVCA, Equidam, Aventis Advisors.

### Module 3: VC Fund-Seat Analysis

**Input flow:** 2 steps (fund profile, deal screen) → `useVCState` assembles `VCDealInput + FundProfile` → `POST /api/vc/evaluate` → `VCDealOutput`

```
FundProfile {
  fund_size, vintage_year, management_fee_pct, carry_pct, hurdle_rate,
  reserve_ratio, target_initial_check_count, target_ownership_pct, recycling_pct
}

VCDealInput {
  company_name, vertical, stage,
  post_money_valuation, check_size,
  arr, revenue_growth_rate, gross_margin, burn_rate_monthly, cash_on_hand,
  dilution: DilutionAssumptions,        # Per-round dilution expectations
  liquidation_stack: [LiquidationPreference],  # Cap table for waterfall
  expected_exit_years
}
```

**Engine** (`vc_return_engine.py`):
- `compute_ownership_math()` — Entry % → exit % through dilution stack, fund returner thresholds (1x, 3x, 5x)
- `build_scenarios()` — Bear/base/bull with exit multiples from `vc_benchmarks.json`, probability-weighted expected value
- `compute_waterfall()` — Liquidation preference distribution through multi-class cap table (non-participating, participating, capped)
- `compute_pro_rata()` — Exercise vs. pass expected value comparison
- `run_portfolio_analysis()` — TVPI/DPI/RVPI, concentration, reserve adequacy
- `run_qsbs_analysis()` — IRC §1202 eligibility and LP tax benefit estimation
- `run_anti_dilution()` — Full ratchet vs. broad-based weighted average modeling
- `run_bridge_analysis()` — Bridge round dilution and participation recommendation

Output includes: ownership math, 3-scenario return model, quick screen recommendation (pass / look deeper / strong interest), waterfall distribution, IC memo financials with auto-generated text, and power law context.

**Benchmark data:** 12 verticals × 6 stages (pre-seed through growth), stage transition probabilities, fund construction templates, exit multiple distributions, dilution-per-round medians. Sourced from Cambridge Associates, Carta 2024, AngelList, PitchBook, First Round Capital.

---

## Backend Conventions

### General Conventions (All Engines)
- All monetary values are in **millions USD** (e.g., `revenue: 50.0` = $50M)
- Percentages are **decimals** (e.g., `tax_rate: 0.25` = 25%, `ebitda_margin: 0.18` = 18%)
- Engines never raise — they return output objects with warnings/flags for edge cases
- Each engine has its own models file as source of truth for data shapes

### M&A Models (`engine/models.py`)
- **Source of truth for all M&A data shapes.**
- `DealStructure` has a Pydantic validator enforcing `cash + stock + debt == 1.0`
- `DealOutput` is fully computed — never store or mutate it
- When adding new M&A output fields: add to `DealOutput` here first, then surface in `financial_engine.py`, then mirror in `frontend/src/types/deal.ts`

### Startup Models (`engine/startup_models.py`)
- **Source of truth for all startup valuation data shapes.**
- Enums: `StartupStage` (pre_seed, seed, series_a), `StartupVertical` (12 verticals), `InstrumentType` (SAFE, convertible note, priced equity), `Geography` (9 regions), `ProductStage` (idea → scaling)
- `StartupInput` aggregates `TeamProfile`, `TractionMetrics`, `ProductProfile`, `MarketProfile`, `FundraisingProfile`
- `StartupValuationOutput` includes `method_results[]`, `dilution_scenarios[]`, `investor_scorecard[]`, and a `ValuationVerdict`

### VC Fund Models (`engine/vc_fund_models.py`)
- **Source of truth for all VC fund-seat data shapes.**
- `FundProfile` has computed properties: `investable_capital`, `initial_check_pool`, `reserve_pool`, `target_initial_check_size`
- `VCDealInput` combines company metrics + deal terms + dilution assumptions + optional cap table
- `VCDealOutput` includes `OwnershipMath`, 3× `VCScenario`, `QuickScreenResult`, optional `WaterfallDistribution`, `ICMemoFinancials`
- Additional models: `QSBSInput/Output`, `AntiDilutionInput/Output`, `BridgeRoundInput/Output`, `PortfolioInput/Output`, `LPReportInput/Output`

### Financial Engine (M&A)
- `projection_years` is always 5 in V1 (field exists for future extensibility)
- The engine returns `DealOutput` with `convergence_warning: bool` if the circularity solver doesn't converge

### Circularity Solver (`circularity_solver.py`)
- Solves the circular dependency: debt balance → interest expense → net income → cash flow → debt paydown
- Convergence: `abs_diff <= 1.0` (dollar) **OR** `rel_diff <= 0.0001` (0.01%)
- Max 100 iterations; sets `convergence_warning=True` if not converged
- Interest computed on **beginning-of-year** balances (standard banking convention)
- Amortization types: `straight_line`, `interest_only`, `bullet`

### Sensitivity Matrices (`sensitivity.py`)
- Each cell calls `run_deal()` with a modified `DealInput` — this is slow by design (pure Python, no parallelism in V1)
- Uses `model_copy(deep=True)` to isolate each scenario — never mutate the base input
- All cells return Year 1 accretion/dilution as a decimal (e.g., `0.123` = 12.3%)

### Risk Analyzer (`risk_analyzer.py`)
- Returns `list[RiskItem]` — absent items mean no risk detected (not zero severity)
- Thresholds: leverage >4x = medium, >6x = critical; synergy concentration >50% revenue = high
- Each risk has `tolerance_band` — a plain-English range ("4x–6x EBITDA")

### Startup Engine (`startup_engine.py`)
- `run_startup_valuation()` runs all 4 methods, weights applicable results, and produces a blended valuation
- Methods can be `applicable: false` — e.g., Berkus is pre-seed/seed only; comparable benchmarks require vertical match
- Dilution scenarios model forward from current round through Series A
- SAFE conversion math handles discount rates and valuation caps

### VC Return Engine (`vc_return_engine.py`)
- `run_vc_deal_evaluation()` is the main orchestrator — requires both `VCDealInput` and `FundProfile`
- Ownership dilution stack models per-round dilution from entry stage to exit
- Fund returner thresholds compute the exit enterprise value needed at 1x, 3x, 5x fund size
- Scenarios use vertical-specific exit multiples from `vc_benchmarks.json`
- Waterfall is only computed when `liquidation_stack` is non-empty
- IC memo section auto-generates a financial summary and investment thesis prompt

### AI Service (`services/ai_service.py`)
- Model: `claude-sonnet-4-20250514` (configurable via `AI_MODEL` env var)
- `is_ai_available()` checks both `ANTHROPIC_API_KEY` presence AND package import — always call this before AI routes
- In-process LRU cache: dict keyed by MD5 hash, max 500 entries, evicts oldest
- `stream_claude()` is an async generator — consume with `async for chunk in stream_claude(...)`
- All functions return `None` / empty string gracefully when AI unavailable — never raise to callers

### API Routes
- M&A routes: `GET /api/v1/health`, `GET /api/v1/industries`, `GET /api/v1/defaults`, `POST /api/v1/analyze`
- AI routes prefix: `/api/ai/` — `GET /status`, `POST /parse-deal`, `POST /generate-narrative`, `POST /explain-field`, `POST /chat` (SSE), `POST /scenario-narrative` (SSE)
- Startup routes prefix: `/api/startup/` — `POST /value`, `GET /benchmarks`, `GET /verticals`, `GET /stages`
- VC routes prefix: `/api/vc/` — `POST /evaluate`, `POST /portfolio`, `POST /waterfall`, `POST /pro-rata`, `POST /qsbs`, `POST /anti-dilution`, `POST /bridge`, `GET /fund/defaults`, `GET /benchmarks`, `GET /verticals`, `GET /stages`, `GET /health`
- Streaming responses use `StreamingResponse(content=..., media_type="text/event-stream")`
- SSE format: `data: {json_chunk}\n\n`, terminates with `data: [DONE]\n\n`

---

## Frontend Conventions

### App Modes (`App.tsx`)
- `AppMode = 'ma' | 'startup' | 'vc'`
- Each mode has its own shell component: `AppShell` (M&A, blue), `StartupShell` (purple), `VCShell` (emerald)
- Mode selector is rendered on M&A step 1 and in the header bar for startup/VC modes
- Switching modes preserves state in all modes (each has independent localStorage)

### State Management
- **M&A:** `useDealState` — persists inputs to `localStorage`, `output` is always `null` on reload
- **Startup:** `useStartupState` — persists inputs to `localStorage`, `output` is always `null` on reload
- **VC:** `useVCState` — persists `fund` and `deal` inputs, `output` is always `null` on reload; `resetDeal()` clears deal state but keeps fund profile

### TypeScript Types
- **M&A:** `types/deal.ts` — mirrors `backend/app/engine/models.py`
- **Startup:** `types/startup.ts` — mirrors `backend/app/engine/startup_models.py`
- **VC:** `types/vc.ts` — mirrors `backend/app/engine/vc_fund_models.py`
- Monetary values: `number` in millions; percentages: `number` as decimals — same conventions as backend across all modules

### Step Flow
- **M&A:** 6 steps. Step 1 shows `ConversationalEntry` by default (if `aiAvailable`), with "Skip AI" falling back to `Step1_DealOverview`. Results shown when `output !== null && !isLoading`.
- **Startup:** 4 input steps + loading review step. Steps: Overview/Fundraise → Team → Traction/Product → Market. Results in `StartupDashboard`.
- **VC:** 2 input steps. Steps: Fund Profile → Deal Screen. Results in `VCDashboard` with sub-panels for ownership, scenarios, waterfall, portfolio, governance tools, and IC memo export.

### AI Components (M&A only currently)
- `AIBadge` — always show on AI-generated content to distinguish from computed values
- `StreamingText` — use for any streaming SSE response; handles cursor animation
- `AIChatPanel` — fixed position (`bottom-0 right-0`), starts collapsed, parses `<parameter_changes>` XML from responses
- `ScenarioNarrative` — re-streams on every `rowValue`/`colValue` change (useEffect dep array)
- `AINarrative` — fires `generateNarrative()` once on mount; cached server-side by deal fingerprint

### AI API Client (`lib/ai-api.ts`)
- `streamChat()` and `streamScenarioNarrative()` read SSE via `ReadableStream` API
- Sentinel values that terminate streams: `[DONE]`, `[AI_UNAVAILABLE]`, `[STREAM_ERROR]`
- `checkAIStatus()` is called on mount in `App.tsx` and `ResultsDashboard` — result gates all AI UI

### VC API Client (`lib/vc-api.ts`)
- `evaluateDeal()` — POST to `/api/vc/evaluate`
- `getVCBenchmarks()`, `getVCVerticals()`, `getVCStages()`, `getVCFundDefaults()`
- Portfolio, waterfall, pro-rata, QSBS, anti-dilution, bridge — each has a dedicated function

### Styling
- Dark-mode only — all classes assume dark background (slate-900/800)
- Use `text-2xs` for very small labels (custom Tailwind size defined in config)
- Mode colors: M&A = `blue-*`, Startup = `purple-*`, VC = `emerald-*`
- Verdict colors: `green-500` = accretive/strong, `amber-500` = marginal/fair, `red-500` = dilutive/at-risk
- AI-related UI: `purple-*` color family consistently
- Animations: `animate-fade-in` (opacity), `animate-slide-up` (translate+opacity)

### GuidedInput AI Help
- Pass `fieldName` prop to `GuidedInput` to activate `AIHelpPopover` instead of static tooltip
- Pass `industry` prop to give AI better context for the field explanation
- Without `fieldName`, falls back to the original static inline help behavior

---

## Environment Variables

Copy `.env.example` to `.env` in the project root:

```bash
ANTHROPIC_API_KEY=sk-ant-...    # Required for all AI features
AI_ENABLED=true                  # Master feature flag
AI_MODEL=claude-sonnet-4-20250514

# Token budgets (adjust for cost control)
AI_MAX_TOKENS_NARRATIVE=1500
AI_MAX_TOKENS_CHAT=2000
AI_MAX_TOKENS_HELP=300
AI_MAX_TOKENS_PARSE=800
AI_MAX_TOKENS_SCENARIO=400
```

All AI features degrade gracefully when `ANTHROPIC_API_KEY` is absent — no crashes, no error states shown to users. Startup and VC modules are fully functional without AI.

---

## Testing

### Backend (pytest)
```bash
pytest tests/ -v                           # All tests
pytest tests/test_circularity.py -v       # Circularity solver (fast, ~13 tests)
pytest tests/test_engine.py -v            # Engine integration (3 fixture deals)
pytest tests/test_sensitivity.py -v       # Sensitivity matrices (slow — runs engine per cell)
```

**Test fixtures** (`tests/fixtures/*.json`): Three pre-built `DealInput` JSON files representing common deal archetypes. Load via `json.load()` and pass to `run_deal()`.

**Note:** Sensitivity tests are slow because each matrix cell requires a full `run_deal()` call. Expect 15–30 seconds for the full test suite.

### Frontend (Vitest)
```bash
npm test          # Watch mode
npm run test:ui   # Browser-based Vitest UI
```

Setup file: `src/test/setup.ts` — loads `@testing-library/jest-dom` matchers.

---

## Benchmark Data

### M&A Industry Benchmarks (`data/industry_benchmarks.json`)

20 industry verticals. Each has:
- `typical_ebitda_margin` — used as smart default when no EBITDA entered
- `ev_ebitda_multiple_range` — `{low, median, high}` for purchase price risk check
- `typical_revenue_growth_rate` — default for target revenue growth
- `typical_debt_capacity_turns_ebitda` — max leverage benchmark

Adding a new M&A industry: add an entry to `industry_benchmarks.json` AND add the string to the `Industry` union type in both `engine/models.py` and `frontend/src/types/deal.ts`.

### Startup Valuation Benchmarks (`data/startup_valuation_benchmarks.json`)

12 verticals × 3 stages (pre-seed, seed, Series A). Each entry includes:
- `valuation_p25/p50/p75/p95` — Pre-money valuation percentiles
- `round_size_median` — Typical raise amount
- `typical_dilution` — Median dilution for the stage
- `arr_multiple_p25/p50/p75` — ARR multiples (seed and Series A)
- `traction_bar` — Plain-English description of what's needed to command median valuation

Also includes market-wide medians, NRR multiple lookup tables, burn multiple bands, and Rule of 40 benchmarks.

Adding a new startup vertical: add to `startup_valuation_benchmarks.json` AND add to `StartupVertical` enum in `startup_models.py` AND mirror in `frontend/src/types/startup.ts`.

### VC Benchmarks (`data/vc_benchmarks.json`)

Comprehensive VC data sourced from Carta, Cambridge Associates, AngelList, PitchBook, First Round Capital:
- `time_to_next_round` — Median/P25/P75 days between rounds
- `stage_transition_probabilities` — e.g., seed → Series A = 26%
- `dilution_per_round` — Median dilution at each stage
- `verticals` — 12 verticals × 6 stages with post-money valuations, raise amounts, ARR multiples, exit multiples
- `fund_construction` — Templates for typical seed and Series A funds (portfolio count, reserve ratio, ownership targets)
- `power_law_returns` — Distribution of fund returns
- `burn_multiple_benchmarks` — Efficiency bands by stage

---

## Key Design Decisions

**No database.** State is session-based (React useState + localStorage). Output is always recomputed, never cached server-side (except the AI narrative cache in-process).

**Three independent engines.** M&A, startup, and VC engines share no computational code. They can be used independently via their respective API endpoints. The frontend is the integration point.

**Financial accuracy over speed.** Sensitivity matrices run the full engine per cell. This is intentional — approximations could mislead users making real M&A decisions.

**Conservative circularity tolerance.** `$1 OR 0.01%` — tighter than most commercial models. Convergence warnings are surfaced to users as "Solver estimate" in the UI.

**Beginning-of-year interest convention.** Standard banking practice; debt amortizes at year-end so interest is computed on the opening balance. Document any changes to this convention in `circularity_solver.py`.

**Percentages as decimals everywhere.** `0.25` = 25%. This is consistent across all backend models and frontend types in all three modules. Never mix — bugs here will silently produce wrong financial outputs (off by 100x).

**AI never writes numbers.** Claude's output (narratives, explanations, scenario stories) is always clearly badged with `AIBadge`. The computed output fields are never overwritten by AI responses.

**Streaming via SSE.** Chat and scenario endpoints stream via Server-Sent Events rather than WebSockets — simpler, stateless, no connection management required. Each request is independent.

**Fund profile persists across deals.** In the VC module, the fund profile is entered once and reused for all deal evaluations. `resetDeal()` clears only the deal state, not the fund.

**VC quick screen is intentionally opinionated.** The recommendation (pass / look deeper / strong interest) is computed deterministically from fund returner math, not from AI. It answers: "At this price, can this deal move the needle for my fund?"

---

## Adding New Features

### New M&A financial metric
1. Add field to `DealOutput` (or a sub-model) in `backend/app/engine/models.py`
2. Compute it in `financial_engine.py`
3. Mirror the field in `frontend/src/types/deal.ts`
4. Surface it in the appropriate output component

### New M&A industry
1. Add entry to `backend/app/data/industry_benchmarks.json`
2. Add string literal to `Industry` type in `backend/app/engine/models.py`
3. Add same string literal to `Industry` type in `frontend/src/types/deal.ts`

### New M&A risk check
1. Add a `_your_risk(deal, ...)` function in `risk_analyzer.py` returning `RiskItem | None`
2. Call it in `analyze_risks()` and append to results list
3. The frontend `RiskPanel` renders all risk items generically — no frontend change needed

### New startup vertical
1. Add entry to `backend/app/data/startup_valuation_benchmarks.json` (all 3 stages)
2. Add value to `StartupVertical` enum in `backend/app/engine/startup_models.py`
3. Add same value to the vertical type in `frontend/src/types/startup.ts`

### New startup valuation method
1. Implement the method function in `startup_engine.py`, returning `ValuationMethodResult`
2. Call it in `run_startup_valuation()` and include in the blending logic
3. Frontend `StartupDashboard` renders method results generically — no frontend change needed

### New VC vertical
1. Add entry to `backend/app/data/vc_benchmarks.json` (all applicable stages)
2. Add value to `VCVertical` enum in `backend/app/engine/vc_fund_models.py`
3. Add same value to the vertical type in `frontend/src/types/vc.ts`

### New VC analysis endpoint
1. Add route to `backend/app/api/vc_routes.py`
2. Implement computation in `vc_return_engine.py`
3. Add client function to `frontend/src/lib/vc-api.ts`
4. Add UI component in `frontend/src/components/vc/`

### New AI endpoint
1. Add route to `backend/app/api/ai_routes.py`
2. Use `ai_service.ask_claude()` (sync) or `ai_service.stream_claude()` (async SSE)
3. Add client function to `frontend/src/lib/ai-api.ts`
4. Always handle the `AI_UNAVAILABLE` case on the frontend
