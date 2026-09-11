# Benchmark releases and evaluation

The September 11, 2026 release separates observations from model assumptions. It contains 1,214 numeric records: 8 reviewed observations and 1,206 inherited assumptions. A record count is not an accuracy score. The source panel reports records selected during a calculation, including its sensitivity and default-selection work.

## Reviewed observations

| Records | Value and scope | Primary source | Use |
|---|---|---|---|
| Software financing dilution | Seed 18%; A 18%; B 12%. Software rounds in the six months before July 10, 2026; bridges excluded. Per-stage sample counts unavailable. | [Carta software benchmarks](https://carta.com/data/linkedin-vc-fundraising-benchmarks-2026/) | Software-only default dilution; no automatic incremental option pool added. |
| Large pre-seed SAFE cap | $35M median post-money SAFE cap for Q2 2026 raises **over** $2.5M. Broad US cohort; no sector-specific percentile grid inferred. | [Carta SAFE caps, August 25, 2026](https://carta.com/data/safe-valuation-caps-q2-2026/) | Explicit post-money SAFE ask comparison only in the compatible raise-size cohort. |
| Post-money SAFE share | 91% of Q2 2026 SAFEs. | [Carta SAFE caps](https://carta.com/data/safe-valuation-caps-q2-2026/) | Instrument-mix reference; never a financing valuation. |
| M&A size cross-checks | 6.3x for $10–25M TEV; 8.3x for $50–100M; 10.1x for $250–500M. Pooled 2021–Q3 2025 means, TTM adjusted EBITDA, North American private-equity transactions. | [GF Data Q3 2025 ESOP report, p. 2](https://gfdata.com/wp-content/uploads/Q3-25_GFData_ESOP_Report.pdf) | Size comparison, explicitly stale and broader than a sector/strategic-buyer cohort. Uncovered size bands remain unavailable. |

Only individual factual observations are included. No underlying proprietary transaction dataset is redistributed. Unknown sample sizes remain null. Observation period, publication date and retrieval date are separate fields.

The [Carta Q2 pre-seed report](https://carta.com/data/state-of-pre-seed-q2-2026/) does not supply every accessible size/sector table needed here. The [SaaS Capital Index](https://www.saas-capital.com/the-saas-capital-index/) uses market capitalization and annualized quarterly revenue; it is not imported as private EV/ARR. The [Carta Q1 fund-performance report](https://carta.com/data/vc-fund-performance-q1-2026/) does not establish a complete matched vintage/size/net-metric quartile table in this release. Fund quartiles therefore remain unavailable. Detailed sector, defense software versus hardware, transaction-type, and probability-calibration cohorts require further source-backed data.

## Runtime contract

`app/data/benchmarks/manifest.json` identifies immutable release files and SHA-256 hashes. The registry validates hashes, record schema, unique IDs, and numeric bindings at load. `.gitattributes` disables newline conversion for benchmark JSON so byte hashes survive Windows/Linux checkouts. Calculation makes no market-data network calls. Numeric list entries as well as scalar dictionary fields are classified. Binding paths are opaque identifiers; some original industry names contain `/`.

`benchmark_version` selects a snapshot. Context-local views isolate simultaneous requests. Every main engine response includes engine version, dataset version/hash, canonical input fingerprint, record IDs, source metadata and limitations. Internal sensitivities accumulate into the outer calculation's evidence. AI parameters and financing-policy defaults use the same request context.

The resolver enforces metric, valuation basis, revenue denominator, stage, specific business model, geography and size compatibility. It can use a broader record only when that record leaves a requested dimension unspecified; the response describes the broader match. It never borrows a specifically incompatible cohort. Sparse or inaccessible cells remain assumed or unavailable.

The original July JSON data are retained for provenance. `2026-07-legacy` preserves inherited numeric benchmark values; it does **not** restore the old engine's bugs. Recalculating with engine 2.0 can differ from a historical engine 1.0 result. Schema-v1 share links migrate to the legacy dataset, preserve explicitly supplied dilution, and retain their old implied financing path. New links carry the actual inputs and the output's evidence identity. New dataset selection is explicit. JSON exports include full input/output evidence; startup PDFs and VC memo text include source/version context.

## Publishing a subsequent dataset

1. Copy the latest snapshot to a **new** version filename. Never overwrite a published predecessor.
2. Add each observation with its exact metric, statistic, unit, basis, denominator, cohort, dates, URL, page/table locator and limitations. Keep derivations and assumptions separate. Do not infer marginal-median conversions or fill missing percentile grids.
3. Change a binding only when the observation matches its consumer. Keep the backing cell and bound value equal. New specialist observations need an explicit resolver consumer and cohort tests.
4. Register the new filename and byte hash in the manifest. Update the supported version list/default and dataset selector as a reviewed code change; pin old saved analyses.
5. Run the commands below, review every verdict change or valuation/expected-MOIC movement over 10%, and document why each material change is appropriate. Review rates/public references monthly and private-market releases quarterly; review dates do not refresh observation dates.

```bash
cd backend
python scripts/validate_benchmarks.py
pytest -q
python scripts/evaluate_engines.py --output ../reports/current.json --baseline ../reports/baseline.json
python scripts/evaluate_empirical.py --input app/data/benchmarks/empirical_observations.json --output ../reports/empirical.json --split-date 2026-07-01
cd ../frontend
npm run typecheck
npm test -- --run
npm run build
```

## What evaluation establishes

The 36-case synthetic suite contains 12 cases per engine. It detects output changes and mechanical regressions; it is not evidence of market accuracy. Dedicated regression tests additionally cover incompatible cohorts, concurrent releases, no-revenue results, preferred-class ownership, pari-passu shortfalls, explicit dates, declining growth, SAFE bases, method reconciliation and sharing.

`empirical_observations.json` is intentionally empty. The empirical report is `not_evaluated`; no holdout calibration claim is made. The harness accepts frozen out-of-sample predictions accompanied by outcome sources. Each row requires `company_id`, `event_id`, `target`, `basis`, `cohort`, `feature_cutoff`, `prediction_date`, `benchmark_available_date`, `outcome_date`, `source_url`, `source_locator`, and `prediction_artifact_hash`. Dates must satisfy benchmark availability <= feature cutoff <= prediction < outcome. Companies cannot cross calibration and holdout; company/event/target duplicates are rejected.

For `target: valuation`, supply positive `actual`, `prediction`, `matched_median`, `range_low`, and `range_high`. Reports contain median absolute log error, matched-median error, interval coverage and relative width. For `target: binary_outcome`, supply a 0/1 actual, probability, `horizon_months`, and `resolved: true`; the harness reports Brier score and observed versus predicted frequency. Different horizons and bases cannot be pooled. Neither a fixture nor an in-sample fitted prediction belongs in that file.

## Remaining model boundaries

- Startup blend weights, qualitative premiums, failure rates and scenario probabilities remain explicit, uncalibrated assumptions. Non-recurring businesses exclude ARR valuation; specialist hardware/biotech methods require additional inputs and independent validation.
- M&A's headline is an EPS-impact assessment. Strategic backlog does not justify dilution. GF Data is a North American size cross-check, not an industry-specific valuation conclusion. Downside rows change EBITDA, synergy phase-in duration and debt rates; existing exit-multiple sensitivities remain separate.
- VC fund-returner thresholds are pro-rata equity illustrations before preferences and net-debt adjustments. Actual scenario proceeds apply the selected exit capitalization and preferences. The investor receives its check-size fraction of the selected class, not that entire class's proceeds.
- A future financing path with preferred securities requires projected exit capitalization. Pro-rata follow-on analysis rejects preference structures that lack separate exercise/pass capitalization; its timing illustration places checks at time zero. SAFE conversion without fully diluted shares remains an illustration, not a definitive cap table.
- Optional AI narrative prompts and cache identities preserve evidence context. This release validates deterministic output and prompt construction; it does not claim a live-model narrative accuracy evaluation.
