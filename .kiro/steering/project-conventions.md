# Dealflow Engine — Project Conventions

## Overview

Dealflow Engine is a full-stack deal intelligence platform with three independent computation modules:

- **M&A Financial Modeling** — merger/acquisition deal analysis
- **Startup Valuation** — early-stage company valuation
- **VC Fund-Seat Analysis** — venture capital fund return modeling

Deterministic engines are the source of truth. AI augments analysis but never replaces or overwrites computed numbers.

## Monorepo Structure

- `backend/` — Python 3.11+, FastAPI
- `frontend/` — React 18, TypeScript, Vite, TailwindCSS
- Docker Compose for full-stack orchestration

## Key Commands

**Backend:**
```bash
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
pytest tests/ -v
ruff check app/
ruff format app/
```

**Frontend:**
```bash
npm install
npm run dev
npm run typecheck
npm run build
npm test
npm run lint
```

**Docker:**
```bash
docker compose up
docker compose up --build
```

## Universal Conventions

- All monetary values in **millions USD** (e.g., `revenue: 50.0` = $50M)
- Percentages as **decimals everywhere** (e.g., `0.25` = 25%). Never mix — off-by-100x bugs are silent.
- Engines never raise exceptions — they return output objects with warnings/flags
- Three engines share no computational code — they are fully independent
- No database — state is session-based (React `useState` + `localStorage`)
- AI never writes numbers — computed output is never overwritten by AI

## Adding New Features

Always follow this order:
1. Pydantic model (backend)
2. Engine logic (backend)
3. Mirror types in frontend TypeScript
4. UI component (frontend)

## Type Sync Rule

Backend Pydantic models are source of truth. Frontend TypeScript types must mirror them exactly.

| Backend | Frontend |
|---|---|
| `models.py` | `deal.ts` |
| `startup_models.py` | `startup.ts` |
| `vc_fund_models.py` | `vc.ts` |
