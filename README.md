# Dealflow Engine

**Open-source M&A financial modeling engine. TurboTax meets Goldman Sachs — guided deal analysis for everyone, not just bankers.**

[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![React 18](https://img.shields.io/badge/react-18-61dafb.svg)](https://react.dev)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688.svg)](https://fastapi.tiangolo.com)

---

## The Problem

M&A financial modeling is broken.

Professional merger models cost $50,000+ when done by advisors. DIY Excel models require years of finance training to build correctly. And even when you have the model, interpreting it requires even more expertise.

The result: most acquisitions — especially in the lower middle market — get analyzed with gut feel and rough math on a napkin. Deals close at the wrong price. Synergies are overestimated. Debt loads cripple the combined company. Acquirers overpay and wonder why the deal didn't work.

## The Solution

Dealflow Engine is a guided, institutional-grade M&A modeling tool designed for humans.

- **Guided flow** — Six steps, one question cluster at a time. No blank spreadsheet to stare at.
- **Smart defaults** — Industry benchmarks pre-fill every field. Most users never need to change them.
- **Plain-English output** — "This deal is accretive by 12.3% in Year 1" — not a table of numbers you have to interpret.
- **Institutional math** — The engine underneath is the same computational model used by investment banks: pro forma statements, PPA, iterative circularity solving, sensitivity matrices, IRR/MOIC.
- **Two modes** — Quick Model for business owners and operators. Deep Model for finance professionals who want every lever.

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

That's it. No API keys, no accounts, no configuration.

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
├── backend/                     # Python FastAPI application
│   ├── app/
│   │   ├── main.py              # FastAPI app + CORS
│   │   ├── api/routes.py        # REST endpoints
│   │   └── engine/              # Core financial computation
│   │       ├── models.py        # Pydantic data models
│   │       ├── financial_engine.py    # Main orchestrator
│   │       ├── circularity_solver.py  # Debt/interest iterative solver
│   │       ├── purchase_price.py      # PPA & goodwill (ASC 805)
│   │       ├── sensitivity.py         # 2D sensitivity matrices
│   │       ├── returns.py             # IRR / MOIC calculations
│   │       ├── risk_analyzer.py       # Plain-English risk flags
│   │       └── defaults.py            # Smart defaults engine
│   └── tests/                   # pytest test suite
│       ├── test_engine.py
│       ├── test_circularity.py
│       ├── test_sensitivity.py
│       └── fixtures/            # Known input/output pairs
└── frontend/                    # React + TypeScript + Vite
    └── src/
        ├── components/
        │   ├── flow/            # 6-step guided input experience
        │   ├── output/          # Results dashboard components
        │   ├── inputs/          # Reusable form components
        │   └── layout/          # Shell, nav, step indicator
        ├── hooks/useDealState.ts  # Central state management
        ├── types/deal.ts          # TypeScript types (mirrors backend)
        └── lib/                   # API client, formatters
```

### The Financial Engine

The engine is a standalone Python module that takes a `DealInput` and returns a `DealOutput`. It can be used completely independently of the web UI.

```python
from app.engine import run_deal
from app.engine.models import DealInput, AcquirerProfile, TargetProfile, DealStructure

deal = DealInput(
    acquirer=AcquirerProfile(
        company_name="Acme Corp",
        revenue=200_000_000,
        ebitda=30_000_000,
        net_income=15_000_000,
        total_debt=20_000_000,
        cash_on_hand=80_000_000,
        shares_outstanding=10_000_000,
        share_price=25.00,
        tax_rate=0.25,
        depreciation=5_000_000,
        capex=4_000_000,
        working_capital=18_000_000,
        industry="Manufacturing",
    ),
    target=TargetProfile(
        company_name="Target LLC",
        revenue=40_000_000,
        ebitda=6_000_000,
        net_income=3_000_000,
        total_debt=0,
        cash_on_hand=2_000_000,
        tax_rate=0.25,
        depreciation=800_000,
        capex=600_000,
        working_capital=4_000_000,
        industry="Manufacturing",
        acquisition_price=50_000_000,
        revenue_growth_rate=0.04,
    ),
    structure=DealStructure(
        cash_percentage=1.0,
        stock_percentage=0.0,
        debt_percentage=0.0,
        debt_tranches=[],
        transaction_fees_pct=0.025,
        advisory_fees=0,
    ),
)

result = run_deal(deal)
print(result.deal_verdict_headline)
# "This deal is accretive to earnings by 8.2% in Year 1"
```

### Computational Model

**Pro Forma Income Statement** — 5-year annual projections combining buyer + target, with synergy phase-in curves, PPA-adjusted D&A, and iteratively solved interest expense.

**Purchase Price Allocation (ASC 805)** — Asset writeups, identifiable intangibles, and goodwill calculation. Incremental D&A flows through the income statement automatically.

**Circularity Solver** — The debt/interest/income/cashflow circularity is solved iteratively (Newton-style, tolerance $1 or 0.01%, max 100 iterations). No circular reference errors.

**Sensitivity Matrices** — 3 standard 2D matrices: Purchase Price vs Synergies, Purchase Price vs Cash Mix, Interest Rate vs Leverage. Each cell shows Year 1 accretion/dilution.

**Returns Analysis** — IRR and MOIC at exit years 3, 5, 7 across entry ± 2× exit multiples in 0.5× steps.

**Risk Analysis** — 6 automated risk flags: leverage, synergy execution, interest rate sensitivity, purchase price vs benchmarks, integration cost payback, revenue synergy concentration.

## API Reference

The backend exposes a simple REST API:

```
POST /api/v1/analyze          — Run deal model (DealInput → DealOutput)
GET  /api/v1/defaults         — Smart defaults for industry + deal size
GET  /api/v1/industries       — List supported industry verticals
GET  /api/v1/health           — Health check
GET  /docs                    — Interactive API documentation (Swagger)
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18, TypeScript, Vite, TailwindCSS |
| Charts | Recharts |
| UI Components | Radix UI primitives |
| Backend | Python 3.11, FastAPI, Pydantic v2 |
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
- Additional industry benchmark data
- Export to Excel (structured workbook)
- PDF report generation
- Additional risk checks
- UI polish / animations

## Roadmap

**V2 priorities:**
- [ ] Live market data integration (pull public company financials automatically)
- [ ] Multi-target (roll-up) modeling
- [ ] Cross-border / multi-currency deals
- [ ] User accounts + deal history
- [ ] Real-time collaboration (share a deal link)
- [ ] Excel export (structured workbook with tabs)
- [ ] PDF report generation (board-ready briefing)
- [ ] Convertible notes and preferred equity
- [ ] LBO modeling mode (pure PE returns analysis)
- [ ] Comparable transaction database

## License

MIT — free to use, modify, and distribute. See [LICENSE](LICENSE).

---

*Built in public. Star the repo if you find it useful.*
