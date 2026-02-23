---
inclusion: fileMatch
fileMatchPattern: "backend/**/*.py"
---

# Backend Conventions

## Stack

- Python 3.11+, FastAPI, Pydantic v2
- Ruff for linting and formatting (line-length 100)
- Type annotations on all functions, docstrings on all public APIs

## Engine Architecture

Three independent engines — no shared computational code:

| Module | Engine File | Entry Point | Models |
|---|---|---|---|
| M&A | `financial_engine.py` | `run_deal()` | `models.py` |
| Startup | `startup_engine.py` | `run_startup_valuation()` | `startup_models.py` |
| VC | `vc_return_engine.py` | `run_vc_deal_evaluation()` | `vc_fund_models.py` |

## Circularity Solver

- Convergence: `abs_diff <= 1.0` OR `rel_diff <= 0.0001`
- Max 100 iterations
- Beginning-of-year interest convention

## Sensitivity Matrices

- Each cell calls `run_deal()` independently
- Always use `model_copy(deep=True)` — never mutate the base input

## Risk Analyzer

- Returns `list[RiskItem]`
- Absent items = no risk (not zero severity)

## AI Service

- Default model: `claude-sonnet-4-20250514`
- Always check `is_ai_available()` before AI routes
- Functions return `None`/empty gracefully when AI is unavailable

## API Route Prefixes

| Prefix | Module |
|---|---|
| `/api/v1/` | M&A |
| `/api/startup/` | Startup |
| `/api/vc/` | VC |
| `/api/ai/` | AI |

## SSE Streaming

- Use `StreamingResponse` with `text/event-stream` content type
- Format: `data: {json}\n\n`
- Terminate with `data: [DONE]\n\n`

## Testing

- pytest, fixtures in `tests/fixtures/`
- Sensitivity tests are slow by design (full engine run per cell)

## Code Style Notes

- Financial formulas: comment explaining the finance logic, not just the code
- Benchmark data files live in `app/data/` — when adding new verticals, update both the JSON and the corresponding enum

## Vertical Benchmark Pattern

Each vertical has its own benchmark block in `startup_valuation_benchmarks.json` and `vc_benchmarks.json`.

**Critical rule:** Pre-revenue valuation methods (Berkus, Scorecard, RFS) must use `_get_vertical_baseline(vdata, stage)` — NOT the market-wide median — as their anchor. This ensures defense tech ($10M P50) and consumer ($3.5M P50) produce different outputs even with identical inputs.

**RFS adjustment scaling:** `adj_per_step` scales proportionally to the vertical baseline so each step remains ~3.2% of baseline regardless of vertical size.

**Vertical-specific risk factors in RFS:**
- `Legislation / Political`: penalizes FINTECH, HEALTHTECH, BIOTECH_PHARMA, DEFENSE_TECH
- `Manufacturing / Operations`: penalizes DEEP_TECH_HARDWARE, CLIMATE_ENERGY, BIOTECH_PHARMA
- `Exit Potential`: bonus for AI_ML_INFRASTRUCTURE, AI_ENABLED_SAAS, DEFENSE_TECH
- `Management`: penalizes missing tech cofounder for AI_ML_INFRASTRUCTURE, DEVELOPER_TOOLS
