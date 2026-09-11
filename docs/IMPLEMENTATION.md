# Engine 2.0 implementation and validation

Implemented locally on `codex/engine-evidence-upgrade`, starting from `4f830d9641a86299605f7f196b7800ea252721b2`. The original [plan](../ENGINE_IMPROVEMENT_PLAN.md) remains the design record; this document describes delivered behavior and remaining evidence dependencies.

## Delivered

| Area | Result |
| --- | --- |
| Benchmark infrastructure | Immutable July legacy and September 11 releases, SHA-256 validation, numeric-cell classification, cohort compatibility, request-isolated selection, canonical input fingerprints and per-record evidence. |
| Source refresh | Eight narrowly applicable published observations from Carta and GF Data. The other 1,206 records are explicitly inherited assumptions. No fabricated percentile tables or fund quartiles. See [sources and limitations](BENCHMARKS.md). |
| Startup | Explicit business-model applicability; smooth ARR weighting; visible weights and contributions; no hidden valuation floor; explicit SAFE caps; distinct company evidence, model indication and actual ask/cap comparison. No observed percentile inferred from assumed reference bands. |
| VC | Explicit future financing paths, incremental option-pool treatment, separate scenario dates and exit capitalization, EV-to-equity bridge, preferred-class proceeds, pari-passu shortfalls and capped participation redistribution. Missing exit evidence suppresses return screening. Comparison and pro-rata routes respect unavailable or unsupported cases. |
| M&A | EPS-based decision separated from strategy; North American transaction-size cross-checks; N/M for nonpositive EBITDA; explicit policy financing assumptions; downside cases for EBITDA, synergy phase-in duration and financing cost. |
| Product | Dataset selector, evidence panels, input/output JSON export, versioned share migration, startup PDF and VC memo evidence context, and AI prompts/cache identities tied to evidence. README includes a real application screenshot. |
| Evaluation | 36-case synthetic before/after report, regression tests, empirical archive validator and metrics harness, and GitHub Actions for tests, build and benchmark validation. |

## Verified locally

- Backend: **678 tests passed**, including evidence/version isolation, source compatibility, economic identities, missing inputs, preferred securities, SAFE mechanics and empirical split validation.
- Frontend: **27 tests passed**, TypeScript check passed, production build passed.
- Both dataset hashes, schemas, numeric coverage and bindings validated.
- All **36 synthetic cases** evaluated against the frozen baseline. [Impact review](../reports/impact.md) explains all 24 flagged cases; 12 M&A cases retained their headline EPS/verdict.
- Browser smoke checks exercised dataset switching, VC unavailable and explicit-exit results, M&A results and startup valuation. A five-page startup PDF was downloaded and visually reviewed, including its evidence page. The tested M&A/startup browser flows reported no uncaught page errors. The README screenshot was captured from the running application.

The build retains a large-bundle warning and an outdated Browserslist database notice. Backend tests emit dependency deprecation warnings. These do not prevent the checked build or test runs. Remote CI and a live Claude narrative evaluation were not run.

## Evidence still required

The empirical observation archive is intentionally empty and its report says `not_evaluated`. Startup weights, AI adjustments, failure probabilities and return scenarios remain assumptions; this release does not establish valuation accuracy or probability calibration. Obtaining dated, legally reusable outcomes and cohort tables remains necessary before making those claims. Specialist hardware/biotech valuation methods and fully diluted SAFE conversion require additional inputs and validation.

The legacy dataset preserves old benchmark values under the corrected engine. It does not reproduce engine 1.0 bugs. Preferred future financing requires projected exit capitalization; unsupported pro-rata cases return a clear validation error. See [model boundaries](BENCHMARKS.md#remaining-model-boundaries) for the exact limits.

## Reproduce

Use Python 3.11 or 3.12; the local verification used 3.12. Install backend `.[dev]` and frontend dependencies, then run the commands in [BENCHMARKS.md](BENCHMARKS.md#publishing-a-subsequent-dataset). Start the API with `uvicorn app.main:app --reload --port 8000` and the frontend with `npm run dev`.

For another local API port, set `DEALFLOW_API_TARGET` before starting Vite, for example `http://127.0.0.1:8011`. This changes the development proxy only. No production deployment or remote push was performed.
