# CLAUDE.md — Dealflow Engine

## Project Overview

**Dealflow Engine** is a full-stack M&A financial modeling platform ("TurboTax meets Goldman Sachs"). It guides users through a 6-step input flow, runs institutional-grade financial computation on the backend, and returns a plain-English results dashboard with sensitivity analysis, risk flags, and an optional Claude AI co-pilot.

**Key constraint:** The deterministic financial engine is the source of truth. AI features augment and interpret — they never replace computed numbers.

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
│   │   ├── main.py                  # FastAPI entry point
│   │   ├── api/
│   │   │   ├── routes.py            # /api/v1/* (analyze, defaults, health)
│   │   │   └── ai_routes.py         # /api/ai/* (parse, narrative, chat)
│   │   ├── engine/                  # Core financial computation
│   │   │   ├── models.py            # Pydantic models — source of truth for all shapes
│   │   │   ├── financial_engine.py  # Main orchestrator: run_deal()
│   │   │   ├── circularity_solver.py
│   │   │   ├── purchase_price.py    # PPA / ASC 805
│   │   │   ├── returns.py           # IRR / MOIC
│   │   │   ├── sensitivity.py       # 2D sensitivity matrices
│   │   │   ├── risk_analyzer.py     # 6 automated risk checks
│   │   │   └── defaults.py          # Industry benchmark lookups
│   │   ├── services/
│   │   │   └── ai_service.py        # Claude API client, caching, streaming
│   │   └── data/
│   │       └── industry_benchmarks.json
│   ├── tests/
│   │   ├── test_engine.py
│   │   ├── test_circularity.py
│   │   ├── test_sensitivity.py
│   │   └── fixtures/                # JSON fixture deals for tests
│   └── pyproject.toml
│
└── frontend/
    └── src/
        ├── App.tsx                  # Route orchestrator (steps + results)
        ├── types/deal.ts            # TS interfaces — mirrors backend models.py
        ├── hooks/useDealState.ts    # Central state + localStorage persistence
        ├── lib/
        │   ├── api.ts               # Core API calls (analyzeDeal, getDefaults)
        │   ├── ai-api.ts            # AI API calls (streaming SSE support)
        │   └── formatters.ts        # Currency, pct, multiple formatters
        ├── components/
        │   ├── flow/                # Steps 1–6 + ConversationalEntry
        │   ├── output/              # Results dashboard, AI panels
        │   ├── inputs/              # GuidedInput, CurrencyInput, SynergyCards
        │   ├── layout/              # AppShell, StepIndicator, ModeToggle
        │   └── shared/              # MetricCard, HeatmapCell, AIBadge, StreamingText
        └── styles/globals.css
```

---

## Architecture & Data Flow

### 1. Input (Frontend → Backend)

User fills 6 steps → `useDealState` assembles a `DealInput` → `POST /api/v1/analyze` → `DealOutput`

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

### 2. Backend Engine Sequence (`financial_engine.py: run_deal()`)

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

### 3. Output (Backend → Frontend)

`DealOutput` JSON → `ResultsDashboard` renders:
- `Verdict` → deal verdict + headline
- `AINarrative` → AI-generated assessment (if AI enabled)
- `DealScorecard` → key metrics vs benchmarks
- EPS trajectory chart (Recharts)
- `RiskPanel` → risk flags with severity
- `SensitivityExplorer` → 3 interactive heatmaps + `ScenarioNarrative` on cell click
- `FinancialStatements` → 5-year pro forma table
- `AIChatPanel` → floating streaming co-pilot

---

## Backend Conventions

### Models (`engine/models.py`)
- **This is the source of truth.** All data shapes live here.
- `DealStructure` has a Pydantic validator enforcing `cash + stock + debt == 1.0`
- `DealOutput` is fully computed — never store or mutate it
- When adding new output fields: add to `DealOutput` here first, then surface in `financial_engine.py`, then mirror in `frontend/src/types/deal.ts`

### Financial Engine
- All monetary values are in **millions USD** (e.g., `revenue: 50.0` = $50M)
- Percentages are **decimals** (e.g., `tax_rate: 0.25` = 25%, `ebitda_margin: 0.18` = 18%)
- `projection_years` is always 5 in V1 (field exists for future extensibility)
- The engine never raises — it returns `DealOutput` with `convergence_warning: bool` if the circularity solver doesn't converge

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

### AI Service (`services/ai_service.py`)
- Model: `claude-sonnet-4-20250514` (configurable via `AI_MODEL` env var)
- `is_ai_available()` checks both `ANTHROPIC_API_KEY` presence AND package import — always call this before AI routes
- In-process LRU cache: dict keyed by MD5 hash, max 500 entries, evicts oldest
- `stream_claude()` is an async generator — consume with `async for chunk in stream_claude(...)`
- All functions return `None` / empty string gracefully when AI unavailable — never raise to callers

### API Routes
- Core routes: `GET /api/v1/health`, `GET /api/v1/industries`, `GET /api/v1/defaults`, `POST /api/v1/analyze`
- AI routes prefix: `/api/ai/` — `GET /status`, `POST /parse-deal`, `POST /generate-narrative`, `POST /explain-field`, `POST /chat` (SSE), `POST /scenario-narrative` (SSE)
- Streaming responses use `StreamingResponse(content=..., media_type="text/event-stream")`
- SSE format: `data: {json_chunk}\n\n`, terminates with `data: [DONE]\n\n`

---

## Frontend Conventions

### State Management (`hooks/useDealState.ts`)
- Single hook, single source of truth for all deal state
- Persists to `localStorage` on every change (inputs only, never output)
- `output` is always `null` on page reload — must re-run analysis
- Always starts at `step: 1` on reload

### TypeScript Types (`types/deal.ts`)
- **Keep in sync with `backend/app/engine/models.py`**
- Monetary values: `number` in millions; percentages: `number` as decimals — same conventions as backend
- `DealInput` / `DealOutput` are the two load-bearing types for the full data pipeline

### Step Flow (`App.tsx`)
- Step 1 shows `ConversationalEntry` by default (if `aiAvailable`), with "Skip AI" falling back to `Step1_DealOverview`
- `ConversationalEntry.onExtracted()` pre-populates acquirer + target and advances to Step 2
- Results are shown when `output !== null && !isLoading`
- `DealInput` is assembled in `App.tsx` from state and passed to `ResultsDashboard` for AI context

### AI Components
- `AIBadge` — always show on AI-generated content to distinguish from computed values
- `StreamingText` — use for any streaming SSE response; handles cursor animation
- `AIChatPanel` — fixed position (`bottom-0 right-0`), starts collapsed, parses `<parameter_changes>` XML from responses
- `ScenarioNarrative` — re-streams on every `rowValue`/`colValue` change (useEffect dep array)
- `AINarrative` — fires `generateNarrative()` once on mount; cached server-side by deal fingerprint

### AI API Client (`lib/ai-api.ts`)
- `streamChat()` and `streamScenarioNarrative()` read SSE via `ReadableStream` API
- Sentinel values that terminate streams: `[DONE]`, `[AI_UNAVAILABLE]`, `[STREAM_ERROR]`
- `checkAIStatus()` is called on mount in `App.tsx` and `ResultsDashboard` — result gates all AI UI

### Styling
- Dark-mode only — all classes assume dark background (slate-900/800)
- Use `text-2xs` for very small labels (custom Tailwind size defined in config)
- Verdict colors: `green-500` = accretive, `amber-500` = marginal, `red-500` = dilutive
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

All AI features degrade gracefully when `ANTHROPIC_API_KEY` is absent — no crashes, no error states shown to users.

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

## Industry Benchmarks (`data/industry_benchmarks.json`)

20 industry verticals. Each has:
- `typical_ebitda_margin` — used as smart default when no EBITDA entered
- `ev_ebitda_multiple_range` — `{low, median, high}` for purchase price risk check
- `typical_revenue_growth_rate` — default for target revenue growth
- `typical_debt_capacity_turns_ebitda` — max leverage benchmark

Adding a new industry: add an entry to `industry_benchmarks.json` AND add the string to the `Industry` union type in both `engine/models.py` and `frontend/src/types/deal.ts`.

---

## Key Design Decisions

**No database.** State is session-based (React useState + localStorage). Output is always recomputed, never cached server-side (except the AI narrative cache in-process).

**Financial accuracy over speed.** Sensitivity matrices run the full engine per cell. This is intentional — approximations could mislead users making real M&A decisions.

**Conservative circularity tolerance.** `$1 OR 0.01%` — tighter than most commercial models. Convergence warnings are surfaced to users as "⚠ Solver estimate" in the UI.

**Beginning-of-year interest convention.** Standard banking practice; debt amortizes at year-end so interest is computed on the opening balance. Document any changes to this convention in `circularity_solver.py`.

**Percentages as decimals everywhere.** `0.25` = 25%. This is consistent across all backend models and frontend types. Never mix — bugs here will silently produce wrong financial outputs (off by 100×).

**AI never writes numbers.** Claude's output (narratives, explanations, scenario stories) is always clearly badged with `AIBadge`. The computed `DealOutput` fields are never overwritten by AI responses.

**Streaming via SSE.** Chat and scenario endpoints stream via Server-Sent Events rather than WebSockets — simpler, stateless, no connection management required. Each request is independent.

---

## Adding New Features

### New financial metric
1. Add field to `DealOutput` (or a sub-model) in `backend/app/engine/models.py`
2. Compute it in `financial_engine.py`
3. Mirror the field in `frontend/src/types/deal.ts`
4. Surface it in the appropriate output component

### New industry
1. Add entry to `backend/app/data/industry_benchmarks.json`
2. Add string literal to `Industry` type in `backend/app/engine/models.py`
3. Add same string literal to `Industry` type in `frontend/src/types/deal.ts`

### New risk check
1. Add a `_your_risk(deal, ...)` function in `risk_analyzer.py` returning `RiskItem | None`
2. Call it in `analyze_risks()` and append to results list
3. The frontend `RiskPanel` renders all risk items generically — no frontend change needed

### New AI endpoint
1. Add route to `backend/app/api/ai_routes.py`
2. Use `ai_service.ask_claude()` (sync) or `ai_service.stream_claude()` (async SSE)
3. Add client function to `frontend/src/lib/ai-api.ts`
4. Always handle the `AI_UNAVAILABLE` case on the frontend
