# Dealflow Engine

**Open-source deal intelligence platform. Institutional-grade financial modeling for M&A, startup valuation, and venture capital — designed for humans, not just bankers.**

[![License: BSL 1.1](https://img.shields.io/badge/license-BSL%201.1-orange.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![React 18](https://img.shields.io/badge/react-18-61dafb.svg)](https://react.dev)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688.svg)](https://fastapi.tiangolo.com)

<p align="center">
  <img src="screenshot.png" alt="Dealflow Engine — Landing Page" width="800" />
</p>

---

## What This Is

Dealflow Engine is a unified platform that covers the three core activities in private-market deal-making:

1. **M&A Deal Modeling** — Full merger model with pro forma statements, PPA, circularity solving, sensitivity analysis, and accretion/dilution verdicts.
2. **Startup Valuation** — Four-method valuation engine (Berkus, Scorecard, Risk Factor Summation, ARR Multiple) for pre-seed through Series A, calibrated against Carta/PitchBook data across 13 verticals including Defense Tech / National Security.
3. **VC Fund-Seat Analysis** — Evaluate deals from the investor's chair: ownership math, dilution modeling, fund returner thresholds, waterfall analysis, QSBS eligibility, pro-rata decisions, and auto-generated IC memo financials.

Each module runs a deterministic computation engine underneath. An optional Claude AI co-pilot augments the output with plain-English narratives, scenario explanations, and conversational deal entry — but the computed numbers are always the source of truth.

## Who It's For

- **Corporate development teams** evaluating acquisitions without $50K advisory models
- **Founders** pressure-testing their valuation ask before walking into an investor meeting
- **VC associates and partners** screening deals against fund economics and portfolio construction constraints
- **Finance students and analysts** learning institutional deal mechanics with a real computation engine, not static spreadsheet templates

## Quick Start

```bash
# Clone the repo
git clone https://github.com/bdavis37-tal/dealflow-engine.git
cd dealflow-engine

# Run with Docker (recommended)
docker compose up

# App is now running:
# Frontend: http://localhost:3000
# API docs:  http://localhost:8000/docs
```

No API keys, no accounts, no configuration required. AI features activate automatically when `ANTHROPIC_API_KEY` is set.

## Development Setup

### Backend (Python / FastAPI)

```bash
cd backend
pip install -e ".[dev]"

# Run the API server
uvicorn app.main:app --reload --port 8000

# Run tests
pytest tests/ -v
```

### Frontend (React / TypeScript)

```bash
cd frontend
npm install

# Start dev server (proxies /api to localhost:8000)
npm run dev

# Type-check
npm run typecheck

# Run tests
npm test
```

## Architecture

```
dealflow-engine/
├── backend/
│   ├── app/
│   │   ├── main.py                         # FastAPI app + CORS
│   │   ├── api/
│   │   │   ├── routes.py                   # /api/v1/* — M&A endpoints
│   │   │   ├── ai_routes.py                # /api/ai/* — AI co-pilot endpoints
│   │   │   ├── startup_routes.py           # /api/startup/* — Startup valuation
│   │   │   └── vc_routes.py                # /api/vc/* — VC fund-seat analysis
│   │   ├── engine/
│   │   │   ├── models.py                   # M&A Pydantic models (source of truth)
│   │   │   ├── financial_engine.py         # M&A orchestrator: run_deal()
│   │   │   ├── circularity_solver.py       # Debt/interest iterative solver
│   │   │   ├── purchase_price.py           # PPA & goodwill (ASC 805)
│   │   │   ├── sensitivity.py              # 2D sensitivity matrices
│   │   │   ├── returns.py                  # IRR / MOIC calculations
│   │   │   ├── risk_analyzer.py            # Automated risk flags
│   │   │   ├── defaults.py                 # Smart defaults engine
│   │   │   ├── startup_models.py           # Startup valuation Pydantic models
│   │   │   ├── startup_engine.py           # 4-method startup valuation engine
│   │   │   ├── vc_fund_models.py           # VC fund-seat Pydantic models
│   │   │   └── vc_return_engine.py         # VC return/ownership/waterfall engine
│   │   ├── services/
│   │   │   └── ai_service.py               # Claude API client, caching, streaming
│   │   └── data/
│   │       ├── industry_benchmarks.json    # 20 M&A industry verticals
│   │       ├── startup_valuation_benchmarks.json  # 13 startup verticals × 3 stages
│   │       └── vc_benchmarks.json          # VC stage transitions, fund construction, exit data
│   └── tests/
│       ├── test_engine.py
│       ├── test_circularity.py
│       ├── test_sensitivity.py
│       └── fixtures/                       # Known input/output pairs
│
└── frontend/
    └── src/
        ├── App.tsx                         # Mode selector + route orchestrator (landing | ma | startup | vc)
        ├── types/
        │   ├── deal.ts                     # M&A TypeScript types
        │   ├── startup.ts                  # Startup valuation types
        │   └── vc.ts                       # VC fund-seat types
        ├── hooks/
        │   ├── useDealState.ts             # M&A state + localStorage
        │   ├── useStartupState.ts          # Startup valuation state
        │   └── useVCState.ts               # VC fund-seat state
        ├── lib/
        │   ├── api.ts                      # M&A + startup API calls
        │   ├── ai-api.ts                   # AI streaming (SSE)
        │   ├── vc-api.ts                   # VC API calls
        │   └── formatters.ts               # Currency, pct, multiple formatters
        ├── components/
        │   ├── flow/                       # M&A 6-step guided input
        │   │   └── startup/                # Startup 4-step input flow
        │   ├── output/                     # M&A results dashboard
        │   │   └── startup/                # Startup valuation dashboard
        │   ├── vc/                         # VC fund setup, deal screen, dashboard,
        │   │                               #   waterfall, ownership, governance, IC memo
        │   ├── inputs/                     # Reusable form components
        │   ├── layout/                     # AppShell, LandingPage, StepIndicator, ModeToggle
        │   └── shared/                     # MetricCard, HeatmapCell, AIBadge, StreamingText
        └── styles/globals.css
```

## The Three Engines

### M&A Deal Model

Full acquisition analysis engine. Takes buyer + target financials, financing structure, PPA assumptions, and synergy estimates. Returns:

- 5-year pro forma income statements with iteratively solved interest expense
- Purchase price allocation (ASC 805) with goodwill and incremental D&A
- Accretion/dilution analysis with EPS bridge breakdown
- IRR and MOIC at exit years 3, 5, 7
- Three 2D sensitivity matrices (purchase price vs. synergies, cash mix, leverage)
- Six automated risk flags with severity ratings
- Deal scorecard with verdict: green (accretive), yellow (marginal), red (dilutive)

```python
from app.engine import run_deal
from app.engine.models import DealInput

result = run_deal(deal_input)
print(result.deal_verdict_headline)
# "This deal is accretive to earnings by 8.2% in Year 1"
```

### Startup Valuation

Four-method valuation engine for pre-seed through Series A startups across 13 verticals:

**AI/ML Infrastructure** · **AI-Enabled SaaS** · **B2B SaaS** · **Fintech** · **Healthtech** · **Biotech/Pharma** · **Deep Tech/Hardware** · **Consumer** · **Climate/Energy** · **Marketplace** · **Vertical SaaS** · **Developer Tools** · **Defense Tech / National Security**

Each vertical has its own benchmark dataset (P25/P50/P75 valuations, ARR multiples, traction bars) sourced from Carta, PitchBook, and Equidam Q3 2025. The engine anchors all pre-revenue methods to the vertical-specific P50 baseline rather than a generic market median, so a defense tech pre-seed and a consumer pre-seed produce meaningfully different outputs.

- **Berkus Method** — Qualitative factor scoring (idea, team, prototype, relationships, rollout)
- **Scorecard Method** — Team, market, product, traction, competition weighted against stage medians
- **Risk Factor Summation** — 12 risk categories adjusted from a vertical-specific base valuation
- **ARR Multiple** — Vertical-specific P25/P50/P75 revenue multiples from Carta, PitchBook, and Equidam; adjusts for NRR, growth rate, gross margin, and burn multiple

Output includes a blended pre-money valuation with confidence range, dilution modeling through future rounds, SAFE conversion mechanics, investor scorecard signals, and a market-calibrated verdict (strong / fair / stretched / at risk).

### VC Fund-Seat Analysis

Evaluates any deal from the investor's perspective, anchored to fund economics:

- **Ownership math** — Entry % through exit % after a full dilution stack (seed → A → B → C → IPO)
- **Fund returner thresholds** — "This company needs a $2.1B exit to return 1x your fund"
- **3-scenario return model** — Bear/base/bull with probability-weighted expected MOIC and IRR
- **Waterfall analysis** — Liquidation preference distribution through a multi-class cap table
- **Pro-rata decision modeling** — Exercise vs. pass expected value comparison
- **Portfolio construction** — TVPI/DPI/RVPI, concentration analysis, reserve adequacy
- **QSBS eligibility** — IRC Section 1202 tax benefit estimation (including 2025 $15M cap changes)
- **Anti-dilution modeling** — Full ratchet vs. broad-based weighted average in down rounds
- **Bridge round analysis** — Dilution impact and participation recommendation
- **IC memo financials** — Auto-generated financial section with investment thesis prompt

## API Reference

The backend exposes four route groups:

```
# M&A
POST /api/v1/analyze          — Run M&A deal model (DealInput → DealOutput)
GET  /api/v1/defaults         — Smart defaults for industry + deal size
GET  /api/v1/industries       — List supported M&A industry verticals
GET  /api/v1/health           — Health check

# Startup Valuation
POST /api/startup/value       — Run startup valuation engine
GET  /api/startup/benchmarks  — Benchmark data by vertical + stage
GET  /api/startup/verticals   — List startup verticals
GET  /api/startup/stages      — List funding stages

# VC Fund-Seat
POST /api/vc/evaluate         — Full deal evaluation from fund seat
POST /api/vc/portfolio        — Portfolio construction analysis
POST /api/vc/waterfall        — Liquidation preference waterfall
POST /api/vc/pro-rata         — Pro-rata exercise analysis
POST /api/vc/qsbs             — QSBS eligibility check (IRC §1202)
POST /api/vc/anti-dilution    — Down-round anti-dilution modeling
POST /api/vc/bridge           — Bridge/extension round analysis
GET  /api/vc/fund/defaults    — Fund profile defaults by size
GET  /api/vc/benchmarks       — VC benchmarks by vertical + stage
GET  /api/vc/health           — VC engine health check

# AI Co-pilot
GET  /api/ai/status           — AI availability check
POST /api/ai/parse-deal       — Natural language deal parsing
POST /api/ai/generate-narrative — Deal narrative generation
POST /api/ai/chat             — Streaming chat (SSE)
POST /api/ai/scenario-narrative — Scenario explanation (SSE)
POST /api/ai/explain-field    — Field-level help

GET  /docs                    — Interactive Swagger documentation
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18, TypeScript, Vite, TailwindCSS |
| Charts | Recharts |
| UI Components | Radix UI primitives |
| Backend | Python 3.11, FastAPI, Pydantic v2 |
| AI Co-pilot | Claude (Anthropic API), streaming SSE |
| Testing | pytest (backend), Vitest (frontend) |
| Deployment | Docker, docker-compose |

## Contributing

This is a build-in-public project. Contributions are welcome.

**Code standards:**
- Python: type annotations on all functions, docstrings on all public APIs
- TypeScript: strict mode, no `any`
- Financial formulas: comment explaining the finance logic, not just the code
- Tests: every new computation module needs test coverage

**To contribute:**
1. Fork the repo
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Write code + tests
4. Open a PR with a clear description of what you changed and why

**Priority contribution areas:**
- Export to Excel (structured workbook with tabs per module)
- PDF report generation (board-ready briefings, IC memos)
- Additional startup verticals and VC benchmark data
- Live market data integration (public company financials)
- Multi-target (roll-up) M&A modeling
- LBO modeling mode (pure PE returns analysis)

## Roadmap

- [ ] Live market data integration (pull public company financials automatically)
- [ ] Multi-target (roll-up) M&A modeling
- [ ] Cross-border / multi-currency deals
- [ ] User accounts + deal history
- [ ] Real-time collaboration (share a deal link)
- [ ] Excel export (structured workbook with tabs)
- [ ] PDF report generation (board-ready briefing, IC memos)
- [ ] LBO modeling mode (pure PE returns analysis)
- [ ] Comparable transaction database
- [ ] Secondary market transaction modeling
- [ ] Fund-of-funds / LP portfolio construction
- [ ] Convertible notes and preferred equity in M&A structures

## License

This project is licensed under the [Business Source License 1.1](LICENSE) (BSL 1.1).

The code is source-available — anyone can view, fork, run it locally, and modify it for personal or internal use. Commercial use (selling the software, offering it as a hosted service, or embedding it in a commercial product) requires a separate commercial license; contact [brendan@incertaintel.ai](mailto:brendan@incertaintel.ai) for licensing inquiries. On February 23, 2030 (four years from the initial release), the license automatically converts to Apache 2.0 and the code becomes fully open source. This model is used by companies like HashiCorp, Sentry, CockroachDB, and MariaDB.

---

*Built in public. Star the repo if you find it useful.*
