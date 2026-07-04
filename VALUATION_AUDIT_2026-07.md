# Valuation Metrics Audit & Benchmark Refresh — July 2026

**Date:** 2026-07-03
**Branch:** `claude/valuation-metrics-audit-ucdejk`
**Scope:** All three computation engines (M&A, Startup Valuation, VC Fund-Seat), all three benchmark data files, API routes, tests, and frontend type parity.
**Prior audits:** 2026-02-24 (finance review), 2026-03-13 (43 findings, all remediated). This audit does not re-report items fixed in those passes; a sample of prior fixes was re-verified as landed.

**Status:** Complete. Backend suite **596 passing** (was 436 at baseline — ~160 new regression/invariant tests, including a new `test_audit_fixes.py` and per-finding regression classes). Frontend typecheck clean, Vitest 22 passing. Three bug-enshrining tests corrected. `pip install -e ".[dev]"` packaging fixed (was broken).

---

## 1. Methodology

Four independent audit workstreams ran in parallel:

1. **M&A engine audit** — line-by-line review of `financial_engine.py`, `circularity_solver.py`, `purchase_price.py`, `returns.py`, `sensitivity.py`, `risk_analyzer.py`, `defaults.py` with **empirical reproduction** of every suspected defect against the fixture deals.
2. **Startup engine audit** — same approach for `startup_engine.py`, `startup_models.py`, benchmark JSON consumption, and frontend type drift.
3. **VC engine audit** — same approach for `vc_return_engine.py`, `vc_fund_models.py`, all 11 VC analysis endpoints, with formula verification against NVCA model documents and IRC §1202.
4. **Benchmark research** — web research of primary sources (Carta, PitchBook-NVCA, Aventis Advisors, SaaS Capital, GF Data, Cambridge Associates/Carta fund performance, Damodaran, company disclosures) to refresh every metric in the three data files to 2025/2026 vintage where authoritative newer data exists.

Every numeric claim in the findings was reproduced by executing the engine — no finding is based on code reading alone.

---

## 2. Benchmark Data Refresh (committed: `data: refresh all benchmark files to 2025/2026 vintage`)

### 2.1 `industry_benchmarks.json` (M&A)

EV/EBITDA ranges re-anchored to 2025–2026 middle-market evidence (GF Data FY2025 avg 7.2x for $10–500M TEV deals; size-stratified 5.9x at $10–25M to 10.0x at $100–250M). Notable corrections:

| Industry | Old median | New median | Basis |
|---|---|---|---|
| Restaurants / Food Service | 12x | 6x | Franchisee/casual 3–7x, QSR 5–7x (Auxo/CT Acquisitions/GBQ 2026) |
| Professional Services | 10x | 8x | 4–7x institutionalized; GF Data business services 7.4x |
| Media / Entertainment | 13x | 9x | Digital 9–10x vs legacy 4–5x |
| Real Estate Services | 12x | 9x | Property mgmt 7–13x by type; small firms ~4x |
| Healthcare Services | 12x | 11x | LMM 5–9x; PE deal median ~13.5x; public ~11.5x |
| Financial Services | 12x | 10x | Sector median ~10.3x; RIA ~11x |
| Insurance | 11x | 12x | Brokerage $1M+ EBITDA avg 11.8x (SICA Fletcher H1 2025) |
| Agriculture | 8x | 9x | Food & Ag median 9.54x (PCE Q3 2025) |
| Software / SaaS | 20x | 19x | Aventis: software all-deal median 19x; range widened down to 8x (LMM) |
| Staffing / Recruiting | 8x | 6x | 4–7x majority (SIA/adAstra) |
| Waste Management | 12x | 10x | Hauling 6.5–8.5x; integrated 10–14x |
| Pharmaceuticals | 16x | 15x | Damodaran Jan 2026: ~15.3x |

Also: AI-native ranges rescaled proportionally (~1.4–1.5x sector base median premium); defense comparables marked to H1 2026 (Anduril $61B Series H on ~$2.2B 2025 revenue ≈ 28x; Shield AI $12.7B on ~$540M 2026E ≈ 24x forward; Palantir ~55x EV/Revenue flagged as a peak-cycle mark); `_meta` provenance block added.

### 2.2 `startup_valuation_benchmarks.json`

| Metric | Old | New | Source |
|---|---|---|---|
| Seed post-money median | $20M | $24M (record) | Carta Q4 2025 |
| Series A post-money median | — | $78.7M (+37% YoY) | Carta Q4 2025 |
| Down-round share | 18% | 12% | Carta Q4 2025 / Q1 2026 |
| Seed→A conversion (2yr) | 20% | 15% | Carta cohorts (2022–23) via mid-2025 data |
| Seed→A median time | 24 mo | 20 mo (616 days) | Carta Q2 2025 |
| Pre-seed dilution | 13% | 12.5% | Carta FY2025 |
| Pre-seed SAFE cap median | $15M | $10M (+ by-round-size table: $7.5M/<$250K, $10M/$250K–1M, $15M/$1–2.5M) | Carta State of Pre-Seed FY2025–Q1 2026 |
| SAFE share of pre-seed | 92% | 93% | Carta Q1 2026 |

Every vertical's Series A block now carries `valuation_p95` (previously missing — the engine read it and returned 0). Defense tech re-anchored to PitchBook 2025 Defense Tech Vertical Snapshot (seed P50 $35M → $24M; Series A P50 $120M → $85M pre-money; dispersion widened — hot AI-native deals price at 17–50x revenue while the median seed stayed moderate). AI-vertical percentiles retained: they already embed the Carta-measured AI premium (+38% at Series A); the refresh notes explicitly warn against stacking further AI premia on top.

### 2.3 `vc_benchmarks.json`

| Metric | Old | New | Source |
|---|---|---|---|
| Seed→Series A transition | 0.26 | 0.15 | Carta cohort data mid-2025 (30.6% for 2018 cohort → ~15% for 2022–23 cohorts) |
| Pre-seed→seed transition | 0.45 | 0.50 | 2025 industry benchmarks |
| Dilution medians (pre-seed/seed/A/B/C) | 18/20.5/20/18/15% | 12.5/19.5/18.5/13/11% | Carta FY2025 |
| Seed→A timing | 766 days | 616 days | Carta Q2 2025 |
| A→B timing | 540 days | 780 days (directional) | Carta/SaaStr 2025 — exact median unpublished |
| SaaS M&A exit ARR multiple (median/P75) | 5.5x / 9x | 4.5x / 8x | Aventis 2026 (543 deals) |
| IPO ARR multiple (median) | 12x | 10x | Trimmed for Q1 2026 public-SaaS re-rating (~3.3x trading medians) |
| Down-round prevalence | 17% | 12% | Carta Q1 2026 |
| Defense tech bear exit multiple | 5.0x | 2.5x | 5x ARR bear exceeded the global median M&A exit — made defense deals un-failable in scenario models |

New: `fund_performance_benchmarks` block (Carta VC Fund Performance Q4 2025, 2,500+ funds — 2017 vintage median TVPI ~1.85x, P90 3.52x, median DPI 0.27x, median net IRR 13.5%; 2021/2022 vintages ~1%); AI premium block (+38% at Series A); Series A→B / B→C transitions retained but explicitly flagged stale (no authoritative 2025+ publication).

**Metrics deliberately NOT overwritten** (no newer authoritative data found; flagged in file notes): Series A→B and B→C transition probabilities, Series C-specific dilution (annotated as historical), Cambridge Associates official vintage tables (Carta fund performance used instead), most per-vertical × per-stage valuation percentiles (no per-vertical 2025 publication below the market-wide level).

---

## 3. Engine Findings & Remediation

All findings were empirically reproduced before fixing. Full detail lives in the git history of this branch; summary below.

### 3.1 M&A engine (10 critical/high, 13 medium)

Headline defects fixed:

- **F-1 Returns category error** — IRR/MOIC "sold the whole combined company" (acquirer + target + synergies) against a target-only equity check: leveraged fixture showed 103% IRR / 34.6x MOIC on a $100M check. Exit is now valued on the target-side EBITDA stream.
- **F-2 Phantom accretion** — pro forma NI was rebuilt from EBITDA margins, silently deleting the acquirer's and target's existing below-EBIT items while the standalone comparator used actual net income (+41% "accretion" on a roughly-flat deal). Pro forma now anchors to actual net incomes plus explicit deal adjustments.
- **F-3 Foregone interest on cash** — cash consideration was free money; now modeled at a configurable short rate with cash-sufficiency validation.
- **F-4 Loss-maker sign flip** — improving EPS from −$1.03 to +$2.18 reported −312% accretion and a red verdict; now Δ/|base| with NM handling.
- **F-5 Double-counted amortization** — mandatory principal wasn't deducted from FCF but was reflected in ending debt (~$71M phantom exit equity on a $100M term loan).
- **F-6/F-7 Sensitivity anchors** — the base-case heatmap cell disagreed with the headline verdict by 129 points on zero-synergy deals (phantom synergy injection); the leverage axis was dead (all columns identical) for any acquirer larger than its target.
- **F-8 Units regime** — `defaults.py` fee/rate tiers were in raw dollars against the millions convention, so every deal got 3% fees at middle-market rates; thresholds converted, financing rates refreshed to H1 2026 credit markets (middle-market ~SOFR+500–700 → 9–11%; upper-MM ~8–9%).
- **F-9 Sources & Uses imbalance** — the S&U table never footed (fees and refinancing had no funding source).
- **F-10 EV vs equity-value conflation** — `acquisition_price` was treated as EV in some code paths and equity value in others; goodwill was overstated by target net debt. Now defined as EV with derived equity consideration.
- The golden regression file — which had **enshrined the phantom +41.18% accretion** — was regenerated with a hand-computed workpaper.

### 3.2 Startup valuation engine (3 critical, 4 high, 6 medium)

- **S-1 Revenue cliff** — the first $50K of ARR cut the blended valuation ~63% and flipped the verdict strong→at_risk (fixed ARR-method weight at any ARR>0). Weight now ramps with ARR magnitude; monotonicity enforced and tested.
- **S-2 SAFE mechanics** — conversion used pre-money math though 87% of the market is post-money SAFEs (understating founder dilution by up to 5 points); the discount field existed but never entered any arithmetic. Post-money mechanics now default; conversion computed at the projected next priced round with cap-vs-discount governing-term reporting.
- **S-3 Unbounded AI premium** — up to +150% applied on top of benchmarks that already price AI (defense tech), producing blended values outside the engine's own reported range. Defense tech frozen, premium capped, ranges recomputed post-modifier with a bracket assertion.
- **S-4/S-5** — user overrides now validated/clamped (a partial scorecard override could silently deflate valuation; unclamped risk scores could 4x it); ARR-method range inversion fixed.
- **S-6 Berkus recalibrated** — per-dimension cap was up to $13.5M total (vs the accepted ~$3–3.5M ceiling), making it a fourth copy of the benchmark median instead of an independent sanity check.
- **S-8 Rule of 40 proxy** — MoM growth was linearized (12% MoM → 144% instead of 289% YoY) and EBITDA margin fabricated from gross margin; both corrected.

**Confirmed landed impact (fixture deals):**

| Fixture | Y1 accretion before → after | 5yr base IRR / MOIC after |
|---|---|---|
| simple_cash_deal | +41.18% → −0.32% | n/a (all cash) |
| leveraged_deal | (IRR 103% / MOIC 34.6x) → −13.55% Y1 | 39.9% / 5.37x |
| loss_making_acquirer (new fixture) | +3.37% (NM-flagged) → green | n/a |

### 3.3 VC fund-seat engine (5 critical, 5 high, 11 medium)

- **C-1 QSBS §1202** — exclusion cap used `min(10M, 10× basis)` where the statute says **greater of** (a $20M investment showed a $10M cap instead of $200M); per-LP benefit multiplied fund-level gain by LP count (~25x overstatement); OBBBA July-2025 changes half-implemented (missing $75M asset test and 3/4/5-year tiered exclusion). All corrected.
- **C-2 GP carry** — `/api/vc/gp-carry` crashed with `UnboundLocalError` for any fund between 1.0x and ~2.16x gross (i.e., most real funds mid-life); catch-up mechanics double-counted carry (GP took 36% of profits on a 20% carry fund). Rebuilt to standard LPA mechanics.
- **C-3 Waterfall** — capped participating preferred never received the conversion option (a $1B exit paid $30M where as-converted value was ~$700M — and a test enshrined it); conversion decisions now iterate senior→junior to a fixed point; optional `ownership_pct` on the liquidation stack enables share-based conversion values.
- **C-4 RVPI falsiness bug** — written-off companies (`fair_value=0.0`) counted at full cost in residual value via Python `or`.
- **C-5 Scenario realism** — bear case had no loss mass (bear MOIC 1.2x at 40% probability, vs the module's own data showing ~60% of seed checks fail); growth compounded uncapped-in-practice (base case = top-decile outcome). Scenarios now carry stage-conditional failure probability from the transition benchmarks and growth decay. A plain seed deal that previously showed an inflated ~5.2x expected MOIC with no downside now shows 62% write-off probability and a realistic 2.16x probability-weighted expected MOIC.
- **H-2 fund defaults** — three contradictory fee bases in one API response (one line assumed 10%/yr management fees — half the fund).
- Dilution assumption defaults (backend + frontend) synced to the refreshed Carta FY2025 medians.

### 3.4 Cross-cutting

- Three existing tests **asserted buggy behavior** (QSBS min-cap, TVPI `or`-falsiness, capped-participating ceiling) — all corrected alongside their fixes.
- Vacuous test assertions fixed (`assert len(x) >= 0`, an identity test with an `or year == 1` escape hatch, a goodwill test that loaded an expected value and never compared it).
- `pyproject.toml` packaging fixed — the documented `pip install -e ".[dev]"` did not work (hatchling could not resolve the package).
- `CLAUDE.md` drift corrected (13 verticals, average-balance interest convention, full route lists, data vintages).

---

## 4. Phase 2 (2026-07-04): AI Parameter-Matrix Refactor + UI Closure

### 4.1 AI premium: from post-blend scalar to inputs-up calibration

The original AI-native premium — even after the Phase 1 cap — remained a post-blend scalar (`blended × (1 + premium)`). Phase 2 removed it entirely and replaced it with a **parameter-level configuration matrix** (`ai_toggle_config.json → parameter_matrix`), applied per-method *before* blending and interpolated by `ai_native_score`:

- **ARR/comparable method**: the vertical's own multiple is uplifted by the configured premium × score, **capped at the same-stage AI-enabled-SaaS median** — a toggle can move a traditional company toward what a genuine AI company commands, never past it.
- **Scorecard**: AI-native weight variant (product/IP 15→25%, competition 10→15%, marketing 10→5%; renormalized).
- **Berkus**: caps re-apportioned toward prototype/IP and strategic relationships (total preserved at $3.5M — no hidden premium).
- **Risk Factor Summation**: Technology/Competition/Litigation steps at $0.5M vs $0.25M (symmetric volatility scaling).
- **Frozen verticals** (AI/ML infra, AI-enabled SaaS, defense tech) receive **zero** parameter shifts — their benchmarks already price AI.

The final blended value is now strictly the weighted average of method results; the reported premium is **emergent** (computed against a standard-parameter counterfactual blend). Reference b2b_saas seed at $1M ARR: score 0 → 0%, score 0.5 → +22.2%, score 1.0 → +44.4% — monotonic, within the defensible (0%, 60%] window, invariant-tested (+46 tests, backend suite now 642).

### 4.2 UI closure of remediation fields

All engine fields added during remediation are now user-reachable: M&A `cash_yield` input, NM-accretion display, interest breakout and integration-cost P&L lines, a new per-year **EPS bridge waterfall** (the bridge output previously rendered nowhere), n/a sensitivity cells with matrix notes; VC bridge `monthly_burn`, a **cap-table/liquidation-stack editor** (previously nonexistent — the waterfall pointed at a missing editor), optional as-converted `ownership_pct`, gross-vs-net fund-returner rows, QSBS OBBBA tier display, honest write-off-bear scenario rendering, over-committed reserve state; IC memo relabeled gross/net.

### 4.3 Latent frontend unit bug (found during wiring)

`lib/formatters.ts` formatted millions-denominated state as raw dollars, and the custom-synergy default (`500_000`) would have submitted **$500 billion** of synergies to the engine. Formatters rewritten millions-denominated; all downstream `/1e6` double-conversions fixed. A `-0`-vs-`+0` flake in the share-link property test was also root-caused (fast-check generates `-0`; `JSON.stringify(-0) === "0"`) and fixed via JSON-canonical comparison.

## 5. Residual Risks & Recommended Next Steps

1. **Cap-table primitive.** Waterfall, pro-rata, SAFE conversion, and anti-dilution all approximate share math with dollar proportions unless `ownership_pct` is supplied. A first-class share-count cap table would eliminate the remaining approximation error.
2. **Stale transition stages.** Series A→B and B→C probabilities have no post-2024 authoritative source; revisit when PitchBook/Carta publish 2026 cohort tables.
3. **Public-SaaS regime watch.** The Q1 2026 AI-disruption re-rating (public SaaS ~3.3x EV/Rev) is the single biggest regime change encoded in this refresh; if it reverses, IPO/exit multiples should be revisited.
4. **§163(j) interest deductibility** (~30% ATI cap) is not modeled in the M&A engine — highly leveraged deals deduct all interest.
5. **Outcome-distribution upgrade.** The 3-scenario model now carries loss mass, but a Correlation-Ventures-style outcome bucket model (0x / <1x / 1–3x / 3–10x / >10x) seeded from the transition data would be more defensible in front of an IC.
