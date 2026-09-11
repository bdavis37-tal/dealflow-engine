# Dealflow Engine improvement plan

Review date: September 11, 2026. Code baseline: `4f830d9641a86299605f7f196b7800ea252721b2`.

Recommendation: make benchmark selection and decision interpretation the next release. Preserve the deterministic engines, build a shared, versioned evidence layer, and correct the places where plausible assumptions become overly confident recommendations. Refreshing numbers alone will leave important behavior unchanged.

Scope: M&A, startup valuation, VC fund-seat analysis, their datasets, and the dashboards/narratives that interpret them. This is an implementation plan based on current code inspection and targeted source discovery, not a completed financial audit or completed data refresh. No product logic or benchmark values were changed during planning.

Current validation: all 648 backend tests passed in 23.48 seconds using Python 3.12.14 and the declared development dependencies. The initial Python 3.13 installation failed because the pinned Pydantic-core/PyO3 build did not support that interpreter; the bundled Python 3.12 runtime resolved setup. Frontend tests/build and live UI behavior were not verified in this planning review. Passing existing tests establishes a regression baseline, not empirical valuation accuracy. Add an explicit supported-Python policy to PR 1; the current `>=3.11` declaration is broader than the verified dependency compatibility.

**What the current code establishes**

| Priority | Finding | Evidence at the reviewed commit | Implication |
|---|---|---|---|
| P0 | No-revenue VC deals use an assumed $10M exit revenue base | `backend/app/engine/vc_return_engine.py`, `_build_scenario`; `run_vc_deal_evaluation` adds a warning | The placeholder still feeds proceeds, expected MOIC, screening and the memo. A warning does not remove its influence. |
| P0 | Fund quartiles are fixed TVPI buckets | `vc_return_engine.py`, `run_fund_irr_analysis`, around line 1987 | Thresholds of 2.5x/1.8x/1.3x ignore vintage and age while the output claims comparison with comparable vintage funds. |
| P0 | Startup verdict conflates model indication and price judgment | `backend/app/engine/startup_engine.py`, `_assign_verdict`, around line 1330 | A high indicated valuation becomes “stretched”; a low one becomes “at risk.” That does not independently establish that an actual ask is expensive or the company is weak. Missing P50 defaults to “fair.” |
| P0 | Defense positioning can soften a dilutive M&A verdict | `backend/app/engine/financial_engine.py`, around lines 1100–1145 | Total backlog coverage of 2x can move dilution as low as -8% into yellow. Copy says the price is justified and separately describes program-of-record funding as guaranteed. These conclusions exceed the evidence supplied. |
| P1 | Benchmark vintage and sourcing are mostly dataset/block level | All three benchmark JSON files | A Q2 2026 update label coexists with retained older vertical percentiles, estimates and stale transition assumptions. Individual outputs cannot consistently explain exactly which observation supports them. |
| P1 | Updating JSON does not update all operative assumptions | `defaults.py`; `vc_fund_models.py::DilutionAssumptions`; `frontend/src/types/vc.ts`; `vc_return_engine.py::_stage_scenario_weights` | Financing rates, dilution defaults, later-stage failure rates and bull probability construction also live in code. Current duplicated dilution defaults agree, but future refreshes can drift. |
| P1 | VC paths assume rounds through IPO and separate scenarios from waterfalls | `compute_ownership_math`; `run_vc_deal_evaluation` | Early acquisition scenarios inherit later-round dilution. Scenario proceeds use EV times ownership; the optional current-cap-table waterfall is separately reported, with an existing reconciliation note. |
| P1 | Startup range is method dispersion | `_compute_method_blend` | The low/high envelope is the minimum/maximum of applicable method ranges, not a calibrated statistical confidence interval. Existing early-revenue floor also overrides the stated weighted blend under certain inputs. |
| P1 | Documentation describes superseded behavior | README vs `ai_toggle_config.json` and `startup_engine.py` | README still describes a post-blend AI premium and defense default-on treatment; current code uses method parameters and freezes defense as already AI-priced. |

The repo already contains financial identity, edge-case, AI calibration and prior-audit regression tests. Preserve those protections. Historical test counts in audit documents are historical evidence, not a current test pass.

**1. Establish a reproducible baseline and resolve misleading outputs**

Deliver one bounded initial PR. Record backend test results, frontend typecheck/build/test results, dataset hashes and baseline output snapshots. Add targeted reproductions for the four P0 findings above before changing them.

For VC deals with no revenue, retain ownership and required-exit calculations. Require an explicit exit revenue or exit equity-value scenario before issuing a return-based recommendation; otherwise report insufficient inputs. Explicit illustrative scenarios remain available and are labeled in the headline and memo.

Remove unsupported vintage-quartile classification until a matching fund cohort is available. Preserve raw TVPI/DPI/RVPI/IRR calculations.

Separate startup outputs into company evidence, model-indicated range, actual ask/cap positioning and financing feasibility. Ask/cap comparison requires an explicit value with the correct instrument basis. Insufficient evidence must remain insufficient rather than defaulting to “fair.”

Keep M&A EPS impact, credit risk, valuation and strategic evidence as separate assessments. Backlog alone must not certify that dilution is justified. Distinguish funded backlog, total backlog, performance period and customer concentration; remove guaranteed-funding language. Any overall recommendation must expose its policy and driving constraints.

Acceptance: no recommendation can silently depend on fabricated revenue, missing comparable data, an unmatched vintage or an automatic backlog justification. Existing arithmetic identities still pass.

**2. Build one benchmark registry and refresh its highest-impact records**

Use validated, checked-in JSON and a small Python resolver first. A database or live market dependency is unnecessary for this release. Keep raw observations, transformations and model assumptions distinct.

Each record needs: stable ID; metric definition; value/statistic; unit/currency; pre-money/post-money/EV/equity/SAFE-cap basis; ARR/run-rate/TTM/forward revenue basis; stage; business model; geography; size band; observation period; publication and retrieval dates; direct source URL and table/page reference; sample size when published; observed/derived/assumed status; derivation; limitations; usage rights; and freshness status. Unknown sample sizes stay unknown.

The resolver first enforces compatible metric and valuation bases, then matches stage, business model, size, geography and time. Relax sparse cohort dimensions explicitly in a documented order. Return the selected record IDs, exclusions, fallback reason and limitations. Never silently substitute manufacturing for another M&A industry or market-wide pre-seed data for an unmatched later-stage cohort.

Share definitions and observations across startup and VC, while preserving each engine's analytical purpose. Do not force different marginal medians to reconcile: median pre-money plus median raise does not necessarily equal median post-money. Convert bases only from paired observations or mark the conversion as an estimate.

Proposed initial refresh queue:

| Data family | Refresh and segmentation | Evidence route |
|---|---|---|
| Pre-seed fundraising | SAFE caps by amount raised, instrument type, geography and AI cohort where actually published | [Carta Q2 2026 pre-seed report](https://carta.com/data/state-of-pre-seed-q2-2026/) is available, published August 13. Extract accessible tables; log gated gaps. |
| Seed/Series A | Priced-round valuations, dilution, bridges, down rounds and round timing; keep sector percentiles only where supported | Latest applicable primary Carta/PitchBook-NVCA releases at refresh time; record the underlying measurement period separately. |
| SaaS | Separate private financing, acquisition and public trading multiples; distinguish revenue denominators and growth/retention cohorts | [SaaS Capital Index](https://www.saas-capital.com/the-saas-capital-index/) and [private-company research](https://www.saas-capital.com/research/); use public-market data as a labeled cross-check, not automatic private-market parity. |
| M&A | Industry plus transaction size, profitability, buyer/deal type and date; dated financing base rates plus spreads | GF Data/ACG, original transaction disclosures, sector adviser research and official rate series. Verify availability and redistribution terms before importing. |
| VC fund performance | Vintage, fund size/strategy, observation date and gross/net metric basis | [Carta Q1 2026 fund performance](https://carta.com/data/vc-fund-performance-q1-2026/) is available; use Cambridge or other licensed primary tables only where accessible. |
| Defense | Separate software, services, autonomy/hardware and mixed businesses; stage-specific financings versus acquisitions/public comps | Primary company disclosures and source research. Large late-stage financings are contextual examples, not early-stage medians. |
| Transitions and exits | Cohort entry date, observation horizon, censoring, failure versus no next round, exit type | Cohort studies with explicit definitions. Preserve uncertain assumptions when newer defensible evidence is unavailable. |

Start with fields that drive valuations, exits, dilution and verdicts. Cover all current industries/verticals in the inventory; give unsupported cells an explicit fallback rather than inventing a complete percentile grid. AI and defense receive detailed segmentation, without tailoring the whole product to Incerta.

Refresh process: discover source → extract observation → validate metric/cohort → review transformation → run output impact report → release an immutable dataset version. Proposed cadence: monthly review for rates/public multiples, quarterly review for private-market reports, slower review for sparse cohorts. Cadence is a review schedule, not permission to relabel old data as new.

Acceptance: every active benchmark resolves to a source or an explicit assumption; incompatible metrics cannot mix; edits reach backend and frontend defaults through the same resolver; frozen versions reproduce old results; user overrides survive refreshes.

**3. Improve the three engines using that evidence layer**

| Engine | Implementation | Required validation |
|---|---|---|
| M&A | Select comps by size and business model; use suitable revenue or earnings methods; show N/M for inappropriate denominators; externalize dated financing assumptions; add downside sensitivities for synergy delay, margin, financing and exit multiple. Treat defense/AI premiums as evidence-backed adjustments or explicit scenarios. | Matched small/large deals choose different applicable cohorts; loss-making cases avoid misleading EBITDA multiples; no double counting of premiums; funding, cash flow, debt and PPA identities remain valid. |
| Startup | Establish method applicability by stage, revenue quality and business model; calibrate blend weights rather than assuming averaging improves accuracy; expose any floor as an explicit adjustment; label method dispersion honestly; separate observed AI-cohort effects from proposed premiums. | Sweep ARR across applicability/ramp thresholds to detect jumps; ensure reported method contributions reconcile to the output including adjustments; test correlated qualitative factors and missing inputs; hold out later-dated outcomes for calibration. |
| VC | Support acquisition-before-next-round, continued financing, shutdown and IPO paths with path-specific timing/dilution. Separate financing dilution from incremental pool creation to prevent ambiguous double counting. Project the exit cap table, bridge EV to distributable equity, and apply preferences to scenario proceeds before computing expected returns. | Cash/proceeds conservation; correct investor-class mapping; low exits favor preferences appropriately; early M&A avoids nonexistent IPO dilution; negative/low-growth cases are represented; user scenarios override defaults explicitly. |

For VC probability calibration, distinguish “did not raise the next round within two years” from ultimate failure. The current bull share and later-stage loss rates are heuristics; move them into labeled assumptions and use sensitivity ranges until suitable outcome evidence supports estimates. A simulation is optional later, after path semantics and data are sound.

For startups outside recurring software, do not make SaaS NRR and ARR the universal standard. Begin with explicit method exclusions and milestone evidence for hardware/biotech/services; add specialist valuation methods only with adequate inputs and independent validation.

Acceptance: the same economic facts produce consistent definitions across engines. A founder's price assessment and a VC's fund-fit assessment may legitimately differ; shared capitalization and benchmark facts may not drift.

**4. Prove relevance, not just formula correctness**

Create two distinct evaluation assets. Synthetic cases test mechanics and invariants. Dated, source-backed deal observations test relevance to actual market outcomes. Never describe a synthetic fixture as evidence that valuations are accurate.

Begin with a proposed 36-case decision suite, 12 per engine, covering sparse inputs, software versus nonsoftware, defense software versus hardware, financing structures, early exits, distressed cases and AI/non-AI cohorts. Have expected behavior and reference arithmetic reviewed independently of the implementation. Expand empirical cohorts according to available evidence rather than manufacturing a target sample size.

Use time-based calibration/holdout splits and deduplicate companies/rounds across splits. Report sample size, cohort coverage, median absolute log valuation error and interval coverage/width for suitable valuation observations. Compare against a simple matched-median baseline. Evaluate probabilities with Brier/calibration measures only when resolved, horizon-matched outcomes exist. Financing outcomes, transaction values and realized investment returns are separate targets.

Every release should report old/new output deltas, changed verdicts, source coverage, stale/fallback usage and the reasons for material changes. Proposed review triggers: any verdict flip or valuation/expected-MOIC movement over 10%; these trigger investigation, not automatic rejection. A material correction may appropriately move results much more.

Release gates: arithmetic/invariant tests pass; deterministic replay works; no unsupported “market percentile” claim; no holdout leakage; no unexplained material regression; small-sample findings remain labeled provisional. Add CI for backend tests, frontend typecheck/build/tests and dataset validation; no tracked workflow was found in this checkout.

**5. Make the evidence visible and maintainable**

Each dashboard, PDF and IC memo should show the result, the matched cohort, its vintage/basis, the strongest drivers and what input would most change the decision. Put detailed sources behind an expandable view. Keep “observed,” “estimated” and “user assumption” visibly distinct.

Carry engine version, dataset version, benchmark record IDs and input fingerprint through responses and saved/shareable analyses. Reopening an analysis should distinguish reproduction from explicit recalculation with new data. Migrate existing saved inputs without overwriting custom assumptions. Include evidence/version context in AI narrative inputs and cache identity; verify narrative claims against the deterministic result.

Update README and model descriptions to match implemented behavior. A stronger language model can help extract and explain evidence, but it cannot establish missing market observations or repair an ambiguous metric definition.

**Execution sequence and effort**

Planning estimates for one engineer with financial review; source access is the main uncertainty, not included as guaranteed turnaround.

| Order | Deliverable | Estimated engineering effort | Dependency |
|---|---|---|---|
| PR 1 | Baseline, P0 output corrections and targeted regressions | 3–5 days | None |
| PR 2 | Benchmark schema, resolver, provenance and versioning | 4–6 days | Baseline |
| PR 3 | Source-backed refresh, default wiring and impact report | 4–7 days | Registry; source access |
| PR 4 | Startup applicability, blend transparency and verdict separation refinements | 3–5 days | Resolver and refreshed cohorts |
| PR 5 | VC path/cap-table/scenario reconciliation | 5–8 days | Resolver; explicit scenario contracts |
| PR 6 | M&A cohort matching, sensitivity and decision presentation | 3–5 days | Resolver and refreshed cohorts |
| PR 7 | Holdout evaluation, provenance UI/exports, migrations and CI release gates | 4–6 days | Harness starts in PR 1; final integration follows engines |

Total proposed effort: 26–42 engineering days plus source/finance review. First useful release: PRs 1–3. If scope must shrink, ship those with honest limitations before adding advanced model features. Defer new asset classes, new providers, a live-data database and broad UI redesign.

The first implementation milestone is straightforward: a deal's result must explain which facts, comparisons and assumptions caused it, and replacing a benchmark must demonstrably update every intended consumer.
