# Codebase Audit Report — Dealflow Engine

**Date:** 2026-03-13
**Auditor:** Comprehensive multi-domain audit (engine, API, frontend, tests, infrastructure)
**Branch:** `claude/audit-dealflow-engine-SMikT`
**Previous audit:** 2026-02-24 (134 tests passing, 0 critical issues)

---

## Executive Summary

This audit covers all layers of the Dealflow Engine: backend computation engines (M&A, Startup, VC), API routes and services, frontend application, test suite, benchmark data, and deployment infrastructure. The codebase is architecturally sound and well-documented, but this deeper audit reveals **3 critical financial calculation bugs**, **significant security hardening needs**, **major test coverage gaps** in the Startup and VC modules, and **UX/accessibility improvements** required for production readiness.

| Severity | Count | Categories |
|----------|-------|------------|
| **Critical** | 6 | Financial logic bugs, CORS, cache collisions |
| **High** | 14 | Security gaps, missing validation, test coverage |
| **Medium** | 18 | Performance, UX, consistency, data quality |
| **Low** | 15+ | Documentation, maintainability, polish |

---

## Table of Contents

1. [Critical Issues — Fix Immediately](#1-critical-issues)
2. [Backend Engine Findings](#2-backend-engine-findings)
3. [API & Security Findings](#3-api--security-findings)
4. [Frontend Findings](#4-frontend-findings)
5. [Test Coverage Analysis](#5-test-coverage-analysis)
6. [Benchmark Data Quality](#6-benchmark-data-quality)
7. [Infrastructure & Deployment](#7-infrastructure--deployment)
8. [Recommendations by Priority](#8-recommendations-by-priority)

---

## 1. Critical Issues

### CRIT-1: Currency Scaling 1000x Error in Sensitivity Matrix Labels

**File:** `backend/app/engine/sensitivity.py:22-32`
**Impact:** All sensitivity matrix axis labels display incorrectly (off by 1000x)

The `_format_currency_compact()` function divides monetary values by 1,000,000 (converting dollars to millions), but per project convention all monetary values are **already in millions**. A $50M synergy (value=50.0) displays as "$0.0M".

**Fix:** Remove the division operations; values are already in millions:
```python
def _format_currency_compact(value: float) -> str:
    abs_val = abs(value)
    sign = "-" if value < 0 else ""
    if abs_val >= 1000:
        return f"{sign}${abs_val/1000:.1f}B"
    if abs_val >= 1:
        return f"{sign}${abs_val:.1f}M"
    return f"{sign}${abs_val*1000:.0f}K"
```

---

### CRIT-2: Accretion/Dilution Percentage Inverted for Loss-Making Acquirers

**File:** `backend/app/engine/financial_engine.py:378`
**Impact:** Deals with negative acquirer EPS show inverted accretion/dilution signals

The `abs()` on the denominator inverts the sign when standalone EPS is negative:
```python
# Current (BUGGY):
(pro_forma_eps - standalone_eps_yr) / abs(standalone_eps_yr) * 100

# Example: Acquirer EPS = -$1.00, Pro forma EPS = +$0.50
# Correct: (0.50 - (-1.00)) / (-1.00) * 100 = -150% (shows improvement but from negative base)
# Current: (0.50 - (-1.00)) / abs(-1.00) * 100 = +150% (WRONG sign)
```

**Fix:** Remove `abs()` from the denominator. Consider special handling for negative-to-positive EPS transitions.

---

### CRIT-3: Acquisition Interest Field Includes Total Interest (Not Just New Debt)

**File:** `backend/app/engine/financial_engine.py:418`
**Impact:** Pro forma detail breakdown double-counts interest in Deep mode

The `acquisition_interest` field in `IncomeStatementYear` receives total `interest_exp` (acquirer + target + new debt), but the field is documented as "Interest from new deal debt" only. Users in deep mode see inflated interest drag.

**Fix:** Compute acquisition-specific debt interest separately from the debt tranches.

---

### CRIT-4: Overly Permissive CORS Configuration

**File:** `backend/app/main.py:67-73`
**Impact:** Security vulnerability in production deployments

```python
allow_methods=["*"],   # Permits DELETE, PATCH, etc.
allow_headers=["*"],   # Allows any header
allow_credentials=True  # Combined with above, credential leakage risk
```

**Fix:** Restrict to explicit allowlists:
```python
allow_methods=["GET", "POST", "OPTIONS"],
allow_headers=["Content-Type", "Accept"],
```

---

### CRIT-5: AI Cache Key Collisions from Aggressive Rounding

**File:** `backend/app/api/ai_routes.py:292-299`
**Impact:** Different deals receive cached narratives from other deals

Cache keys are built from values rounded to nearest $1000:
```python
str(round(request.deal_input.target.acquisition_price, -3))  # $50.4M and $49.6M both → $50M
```

Two deals with similar (but different) financials get the same cache key and serve each other's AI narratives.

**Fix:** Hash the full deal input instead of rounded approximations.

---

### CRIT-6: Cache Implementation Is Not LRU and Has Unbounded Growth

**File:** `backend/app/services/ai_service.py:43-61`
**Impact:** Memory exhaustion in production; stale cache entries never expire

- Uses FIFO eviction (evicts oldest inserted), not LRU
- No TTL — cached entries never expire
- No per-entry size limit (single entry could be 10MB+)
- Not thread-safe for concurrent access

**Fix:** Replace with `OrderedDict`-based TTL cache or use `cachetools.TTLCache`.

---

## 2. Backend Engine Findings

### 2.1 Financial Logic Issues

| ID | Issue | File | Severity | Description |
|----|-------|------|----------|-------------|
| ENG-1 | Risk severity inversion | `risk_analyzer.py:391` | HIGH | Revenue synergy concentration risk has no smooth escalation between 50-70% |
| ENG-2 | Silent defense backlog zeros | `financial_engine.py:147` | HIGH | Zero backlog treated same as missing data — no warning issued |
| ENG-3 | Pydantic mutation bypass | `sensitivity.py:267` | HIGH | Direct field mutation bypasses Pydantic validators |
| ENG-4 | Convergence OR vs AND | `circularity_solver.py:234` | MEDIUM | OR logic allows convergence on absolute tolerance alone for small deals |
| ENG-5 | Percentage convention violation | `risk_analyzer.py:293` | MEDIUM | Uses 0-100 scale instead of decimal convention |
| ENG-6 | Synergy phase-in > projection years | `financial_engine.py:72` | MEDIUM | No warning when synergies never reach full run-rate |
| ENG-7 | Negative EBITDA handling inconsistent | `financial_engine.py:258` | MEDIUM | Different fallback strategies across functions |
| ENG-8 | Sensitivity magic numbers | `sensitivity.py:221` | MEDIUM | Hardcoded ranges not configurable |
| ENG-9 | IRR docstring mismatch | `returns.py:43,68` | LOW | Claims -1.0 return on non-convergence but returns best estimate |
| ENG-10 | Synergy category unbounded | `models.py:240` | LOW | No enum validation on category strings |

### 2.2 Positive Findings

- No SQL injection, shell injection, or code injection vulnerabilities
- All engines return output objects with warnings — they never raise exceptions
- Pydantic validators enforce `cash + stock + debt == 1.0` on `DealStructure`
- Circularity solver has proper convergence warning flag
- Sensitivity matrix prevents recursive generation via `include_sensitivity=False`
- `_safe_float()` guards final outputs against NaN/Infinity

---

## 3. API & Security Findings

### 3.1 Security Vulnerabilities

| ID | Issue | Severity | Description |
|----|-------|----------|-------------|
| SEC-1 | No request size limits | HIGH | No max body size configured — multi-GB payloads accepted |
| SEC-2 | Unvalidated numeric ranges | HIGH | Monetary inputs unbounded — extreme values cause overflow |
| SEC-3 | JSON parsing unsafe | HIGH | `clean.split("```")[1]` — IndexError if only one backtick pair |
| SEC-4 | Unvalidated string fields | HIGH | `ChatMessage.content` has no max length; `role` is unbounded string |
| SEC-5 | No array size limits | HIGH | `ChatRequest.messages` can be 100,000+ items |
| SEC-6 | No rate limiting | MEDIUM | AI endpoints can be called unlimited times (token depletion) |
| SEC-7 | No security headers | MEDIUM | Missing X-Frame-Options, CSP, HSTS, X-Content-Type-Options |
| SEC-8 | Debug info leakage | MEDIUM | Root endpoint advertises `/docs` (Swagger) in production |
| SEC-9 | Streaming no disconnect detection | MEDIUM | Server continues streaming after client disconnects, wasting tokens |

### 3.2 Error Handling Gaps

| ID | Issue | Severity |
|----|-------|----------|
| ERR-1 | Bare exception handlers | HIGH | Generic 500 errors with no distinction between causes |
| ERR-2 | Silent exception swallowing | HIGH | Corrupted cache entries silently ignored, not invalidated |
| ERR-3 | Stream error details lost | MEDIUM | Client receives `[STREAM_ERROR]` with no actionable info |
| ERR-4 | Exception details not logged | MEDIUM | `logger.warning()` used instead of `logger.exception()` |

### 3.3 API Design Issues

| ID | Issue | Severity |
|----|-------|----------|
| API-1 | Inconsistent HTTP status codes | HIGH | POST returns 200 instead of 201; AI unavailable returns 200 not 503 |
| API-2 | No API versioning for non-M&A routes | MEDIUM | `/api/startup/` and `/api/vc/` have no version prefix |
| API-3 | Inconsistent error response schema | MEDIUM | Different endpoints return different error formats |
| API-4 | Blocking sync Claude calls | HIGH | `ask_claude()` blocks event loop thread; should be async |

---

## 4. Frontend Findings

### 4.1 Security Issues

| ID | Issue | Severity | Description |
|----|-------|----------|-------------|
| FE-SEC-1 | Unencrypted localStorage | MEDIUM | Financial data (deal terms, fund sizes) stored in plaintext |
| FE-SEC-2 | URL-encoded deal state | MEDIUM | Share links expose deal parameters in browser history and referrer headers |
| FE-SEC-3 | Partial object coercion | MEDIUM | `acquirer as AcquirerProfile` casts from Partial without validation |
| FE-SEC-4 | Double type casting bypass | LOW | `output.ic_memo as unknown as VCInputState['deal']` bypasses type system |

### 4.2 UX & Error Handling

| ID | Issue | Severity | Description |
|----|-------|----------|-------------|
| FE-UX-1 | Silent error suppression | MEDIUM | Errors caught but users see only generic "error" state |
| FE-UX-2 | Loading state race condition | MEDIUM | Rapid requests cause AbortController cleanup races |
| FE-UX-3 | No request timeout | LOW | Fetch calls have no timeout — backend hang = infinite loading |
| FE-UX-4 | Streaming fragility | MEDIUM | Network drop during SSE = frozen UI indefinitely |
| FE-UX-5 | Interval memory leak | LOW | Message rotation interval not cleaned on component unmount |
| FE-UX-6 | Inconsistent error messages | LOW | `api.ts` vs `vc-api.ts` handle errors differently |

### 4.3 Performance Issues

| ID | Issue | Severity | Description |
|----|-------|----------|-------------|
| FE-PERF-1 | localStorage on every state change | LOW | JSON.stringify of full deal on every keystroke |
| FE-PERF-2 | Tab panels all re-render | LOW | VCDashboard re-renders all 7+ hidden panels on tab switch |
| FE-PERF-3 | No lazy loading of heavy components | LOW | Recharts loaded eagerly for all modes |

### 4.4 Accessibility Issues

| ID | Issue | Severity | Description |
|----|-------|----------|-------------|
| FE-A11Y-1 | Missing ARIA labels | MEDIUM | Only ~27 aria-* attributes across 70+ components |
| FE-A11Y-2 | Color-only status indicators | MEDIUM | Verdict/recommendation color not paired with text labels |
| FE-A11Y-3 | Insufficient focus indicators | MEDIUM | Default focus rings low-contrast in dark mode |
| FE-A11Y-4 | Form labels not associated | LOW | `<label>` not linked to `<input>` via `htmlFor`/`id` |
| FE-A11Y-5 | Icon-only buttons | LOW | Share, New Deal, Help buttons lack `aria-label` |
| FE-A11Y-6 | No skip navigation link | LOW | Long tab chain for keyboard users |

### 4.5 Responsive Design Issues

| ID | Issue | Severity |
|----|-------|----------|
| FE-RESP-1 | Horizontal table overflow | MEDIUM | Financial tables (10+ columns) overflow on mobile |
| FE-RESP-2 | VCDashboard 9 tabs | LOW | Tabs wrap awkwardly on mobile |
| FE-RESP-3 | Popover positioning | LOW | `w-72` (288px) overflows on 375px screens |

### 4.6 Input Validation

| ID | Issue | Severity | Description |
|----|-------|----------|-------------|
| FE-VAL-1 | Unsafe number parsing | MEDIUM | Regex allows multiple decimals ("1.2.3"), scientific notation |
| FE-VAL-2 | No parsed value bounds | LOW | Accepts Infinity, -Infinity, unrealistic numbers |
| FE-VAL-3 | AI toggle config orphans | LOW | References non-existent verticals in `frozen_off` config |

---

## 5. Test Coverage Analysis

### 5.1 Current State

| Module | Test Coverage | Status |
|--------|-------------|--------|
| M&A Circularity Solver | ~95% | Strong |
| M&A Financial Engine | ~70% | Acceptable but weak assertions |
| M&A Risk Analyzer | ~60% | Weak |
| Startup Engine (round timing only) | ~5% | **CRITICAL GAP** |
| VC Engine | **0%** | **CRITICAL GAP** |
| AI Service | ~20% | Weak |

### 5.2 Critical: Startup Engine Untested

The core `run_startup_valuation()` orchestrator and all 4 valuation methods (Berkus, Scorecard, Risk Factor Summation, Comparable Benchmarks) have zero dedicated tests. Only the `_compute_round_timing()` helper is tested via property-based tests. Missing coverage:

- Method weighting and blending logic
- Dilution scenario modeling (pre-seed → seed → Series A)
- SAFE conversion mechanics (discount rates, valuation caps)
- Verdict assignment (strong / fair / stretched / at_risk)
- Per-vertical per-stage behavior (13 verticals x 3 stages)
- Edge cases: zero-revenue startups, negative burn, SAFE stacking

### 5.3 Critical: VC Engine Completely Untested

All 9 functions in `vc_return_engine.py` have zero test coverage:

- `run_vc_deal_evaluation()` — Main orchestrator
- `compute_ownership_math()` — Entry % → exit % through dilution
- `build_scenarios()` — Bear/base/bull model
- `compute_waterfall()` — Liquidation preference distribution
- `compute_pro_rata()` — Exercise vs. pass analysis
- `run_portfolio_analysis()` — TVPI/DPI/RVPI
- `run_qsbs_analysis()` — IRC §1202 eligibility
- `run_anti_dilution()` — Full ratchet vs. weighted average
- `run_bridge_analysis()` — Bridge round modeling

### 5.4 M&A Test Weaknesses

- **Weak assertions:** 5% tolerance on entry multiples (too lenient for $10B+ deals)
- **Broad bounds:** `-1000 < pro_forma_eps < 1000` doesn't validate sign correctness
- **Missing fixtures:** No all-debt, negative-EBITDA, cross-industry, mega-deal, or no-synergy fixtures
- **Only 3 core industries tested** out of 21

### 5.5 Dependency Blocker

**`hypothesis` is missing from `pyproject.toml` dev dependencies** but imported in `test_round_timing.py`. Running `pip install -e ".[dev]"` will not install it, causing test failures.

---

## 6. Benchmark Data Quality

### 6.1 Industry Benchmarks (M&A)

- **Coverage:** 21/21 industries present — complete
- **Issue:** AI-native premium inconsistencies (Insurance at 100% premium vs SaaS at 75% — counterintuitive)
- **Issue:** Financial Services 55% EBITDA margin is 2.5x higher than medians — needs citation
- **Issue:** No source attribution per-vertical
- **Issue:** No schema validation (range order not enforced: `low <= median <= high`)

### 6.2 Startup Valuation Benchmarks

- **Coverage:** 13/13 verticals x 3 stages — complete
- **Issue:** Pre-seed ARR multiples may be present (meaningless for pre-revenue companies)
- **Issue:** AI ML Infrastructure pre-seed check size range ($100K-$2M) is 2-4x larger than standard — undocumented
- **Issue:** Defense Tech pre-seed valuation ($6M) lower than Biotech ($8M) despite higher barriers — questionable
- **Issue:** No confidence intervals or sample sizes documented
- **Issue:** Dilution path not validated end-to-end (founder ownership at each stage)

### 6.3 VC Fund Benchmarks

- **Coverage:** 13/13 verticals x 6 stages — complete
- **Issue:** Stage transition probabilities questionable (Seed → Series A at 26% seems low vs Carta data)
- **Issue:** Series A dilution (15%) lower than Seed (17%) — unusual, undocumented rationale
- **Issue:** Missing P95 exit multiples (critical for modeling power law "grand slam" scenarios)
- **Issue:** No per-vertical power law distribution
- **Issue:** Fund construction templates lack key details (IRR targets, portfolio count)

---

## 7. Infrastructure & Deployment

### 7.1 Docker Compose

| Issue | Severity | Description |
|-------|----------|-------------|
| No env_file directive | **CRITICAL** | `ANTHROPIC_API_KEY` not passed to backend container |
| No resource limits | MEDIUM | Backend/frontend can consume unlimited CPU/memory |
| Health check M&A only | MEDIUM | `/api/v1/health` doesn't validate startup/VC modules |
| No logging configuration | MEDIUM | Logs accumulate indefinitely |
| No volume persistence | LOW | Logs and temp files lost on restart |

### 7.2 Backend Dockerfile

| Issue | Severity | Description |
|-------|----------|-------------|
| Hardcoded dependency versions | HIGH | Diverges from pyproject.toml; creates maintenance burden |
| No test stage | MEDIUM | Cannot run tests during container build |
| No HEALTHCHECK instruction | LOW | Relies entirely on docker-compose |

### 7.3 Frontend Dockerfile

| Issue | Severity | Description |
|-------|----------|-------------|
| No HTTP security headers | **CRITICAL** | Missing CSP, X-Frame-Options, HSTS |
| No HTTPS/TLS | HIGH | All communication in plaintext |
| Nginx runs as root | MEDIUM | No non-root user created |
| Missing proxy headers | MEDIUM | No X-Forwarded-For, X-Forwarded-Proto |
| No gzip compression | LOW | Static assets served uncompressed |

### 7.4 Dependencies

| Issue | Severity | Description |
|-------|----------|-------------|
| Loose version pinning (`>=`) | HIGH | Non-reproducible builds; breaking changes possible |
| No lock files | HIGH | pip and npm builds are non-deterministic |
| `hypothesis` missing from dev deps | **BLOCKER** | Tests cannot run after fresh install |
| No CI/CD pipeline | MEDIUM | No automated testing or deployment |
| No security scanning | MEDIUM | No pip-audit, bandit, or npm audit in pipeline |

---

## 8. Recommendations by Priority

### Phase 1: Critical Fixes (Immediate)

These issues affect financial accuracy, security, or ability to run tests.

| # | Issue | Effort | Impact |
|---|-------|--------|--------|
| 1 | Fix `_format_currency_compact()` scaling (CRIT-1) | 30 min | Sensitivity matrix labels correct |
| 2 | Fix accretion/dilution `abs()` bug (CRIT-2) | 30 min | Correct signals for loss-making acquirers |
| 3 | Fix `acquisition_interest` field (CRIT-3) | 1 hr | Accurate pro forma detail breakdown |
| 4 | Restrict CORS methods/headers (CRIT-4) | 15 min | Security hardening |
| 5 | Fix cache key collision (CRIT-5) | 1 hr | Correct AI narratives per deal |
| 6 | Add `hypothesis` to dev dependencies | 2 min | Unblock test suite |
| 7 | Add `env_file: .env` to docker-compose | 2 min | AI features work in containers |

### Phase 2: Security Hardening (Before Production)

| # | Issue | Effort |
|---|-------|--------|
| 8 | Add request body size limits | 30 min |
| 9 | Add Pydantic field constraints on numeric inputs (min/max) | 2 hrs |
| 10 | Add max_length to string/array fields (ChatMessage, etc.) | 1 hr |
| 11 | Fix JSON markdown parsing (bounds check on split) | 30 min |
| 12 | Add HTTP security headers to nginx | 30 min |
| 13 | Replace cache with proper TTL + LRU implementation | 2 hrs |
| 14 | Make `ask_claude()` async | 2 hrs |
| 15 | Add rate limiting on AI endpoints | 2 hrs |
| 16 | Pin dependency versions (use `~=` instead of `>=`) | 1 hr |

### Phase 3: Test Coverage (Next Sprint)

| # | Issue | Effort |
|---|-------|--------|
| 17 | Create `test_startup_engine.py` — 4 methods, 13 verticals, edge cases | 3-5 days |
| 18 | Create `test_vc_engine.py` — ownership, scenarios, waterfall, QSBS | 5-7 days |
| 19 | Strengthen M&A test assertions (tighter tolerances, sign checks) | 1 day |
| 20 | Add missing M&A fixtures (all-debt, negative EBITDA, mega-deal) | 1 day |
| 21 | Create CI/CD pipeline (GitHub Actions) | 2 hrs |

### Phase 4: UX & Accessibility

| # | Issue | Effort |
|---|-------|--------|
| 22 | Add ARIA labels to interactive elements | 2 days |
| 23 | Add text labels to color-only indicators (verdict, recommendation) | 1 day |
| 24 | Fix AbortController race condition in `useDealState` | 2 hrs |
| 25 | Add request timeouts to all fetch calls | 1 hr |
| 26 | Fix CurrencyInput number parsing (reject multiple decimals) | 1 hr |
| 27 | Handle horizontal table overflow for mobile | 2 hrs |
| 28 | Add form label associations (htmlFor/id) | 2 hrs |
| 29 | Validate Partial objects before API submission | 2 hrs |

### Phase 5: Data Quality & Documentation

| # | Issue | Effort |
|---|-------|--------|
| 30 | Add source citations to all benchmark data files | 2 days |
| 31 | Validate stage transition probabilities against Carta 2025 data | 1 day |
| 32 | Add P95 exit multiples to VC benchmarks | 1 day |
| 33 | Document AI-native premium rationale per industry | 1 day |
| 34 | Add schema validation script for benchmark JSON files | 1 day |
| 35 | Standardize percentage convention across all engine code | 2 hrs |

### Phase 6: Nice to Have

| # | Issue | Effort |
|---|-------|--------|
| 36 | Version all API routes consistently (v1 prefix) | 1 hr |
| 37 | Lazy-load heavy components (Recharts) | 2 hrs |
| 38 | Add gzip compression to nginx | 15 min |
| 39 | Standardize error response schema across all endpoints | 2 hrs |
| 40 | Add pre-commit hooks (ruff, formatting) | 30 min |
| 41 | Move sensitivity matrix ranges to configuration | 1 hr |
| 42 | Add synergy phase-in warning when > projection_years | 30 min |
| 43 | localStorage serialization debounce (only persist on blur/submit) | 1 hr |

---

## Summary

The Dealflow Engine has a solid architectural foundation with three well-separated computation modules, proper Pydantic validation, and comprehensive documentation. The M&A module is the most mature with reasonable test coverage. However, this audit reveals:

1. **3 critical financial calculation bugs** that produce incorrect outputs (sensitivity labels, accretion/dilution sign, interest allocation)
2. **Major security gaps** requiring hardening before production (CORS, request limits, cache implementation, input validation)
3. **0% test coverage** for the VC engine and only ~5% for the Startup engine
4. **Accessibility deficits** that would exclude screen reader and keyboard users
5. **Infrastructure gaps** (missing secrets injection, no HTTPS, no CI/CD)

The financial bugs are the highest priority — they silently produce wrong numbers for users making real investment decisions. Security hardening is the second priority. Test coverage for Startup/VC modules is the third.

**Overall assessment:** Strong foundation, needs targeted fixes before production deployment.
