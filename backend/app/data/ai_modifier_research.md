# AI Valuation Modifier — Research & Methodology

## Overview

This document details the per-vertical `base_premium_multiplier` values used by `apply_ai_modifier()` and the `ai_native_ev_ebitda_range` values added to `industry_benchmarks.json`. All premiums reflect the 2025–2026 market reality that AI-native companies command materially higher revenue and EBITDA multiples than non-AI peers in the same vertical.

All monetary values are in millions USD. Percentages are expressed as decimals.

---

## Frozen-On Verticals (Multiplier = 1.0, Pass-Through)

These verticals are AI-native by definition. Their benchmark ranges in `startup_valuation_benchmarks.json` already price in AI-native status, so the modifier returns pass-through (`ai_modifier_applied = False`).

| Vertical | `base_premium_multiplier` | Rationale |
|---|---|---|
| `ai_ml_infrastructure` | 1.0 (pass-through) | Foundation models, GPU compute, MLOps — AI is the entire product. Benchmark p50 valuations (pre-seed $10M, seed $28M, Series A $90M) already reflect AI-native pricing. Applying an additional premium would double-count. |
| `ai_enabled_saas` | 1.0 (pass-through) | Vertical SaaS with meaningful AI differentiation. Benchmark ranges (pre-seed $8M, seed $22M, Series A $60M) are calibrated to AI-enabled companies specifically. |

---

## Non-Frozen Vertical Premiums (at `ai_native_score = 1.0`)

The `base_premium_multiplier` is the premium factor applied at full score. The formula is:

```
blended_after_ai = blended_valuation × (1 + base_premium × ai_native_score)
```

For example, `defense_tech` at score 1.0: `blended × (1 + 1.5) = blended × 2.5`.

### defense_tech — Premium: 1.5

AI-native defense companies command dramatically higher multiples than traditional defense primes.

**Comparable:** Palantir (PLTR) trades at ~18x EV/Revenue as a public AI-native defense platform, while L3Harris (LHX) trades at ~2.1x EV/Revenue as a traditional prime. Anduril's last private round implied ~22x EV/Revenue. The 8–10x gap between AI-native and traditional defense peers justifies the highest premium in the model.

### healthtech — Premium: 1.0

AI-native healthtech companies (clinical decision support, diagnostic AI, drug-target prediction) command roughly double the multiples of traditional health IT.

**Comparable:** Tempus AI (TEM) trades at ~12x EV/Revenue with its AI-driven precision medicine platform, while legacy health IT companies like Cerner (pre-Oracle acquisition) traded at ~5–6x. Viz.ai's stroke detection platform raised at valuations implying 15–20x ARR multiples vs. 5–8x for traditional clinical SaaS.

### biotech_pharma — Premium: 0.8

AI-native drug discovery platforms (in-silico screening, generative chemistry) trade at a premium over traditional CROs and biotech, though the gap is narrower due to binary clinical trial risk.

**Comparable:** Recursion Pharmaceuticals (RXRX) trades at ~8x EV/Revenue with its AI-driven drug discovery platform, while traditional CROs like ICON trade at ~3–4x. Insilico Medicine's AI-discovered drug candidates reached clinical trials faster, justifying premium valuations at the seed/Series A stage.

### b2b_saas — Premium: 0.8

B2B SaaS companies that embed AI as a core differentiator (not a feature bolt-on) command meaningfully higher multiples than traditional SaaS.

**Comparable:** Monday.com (MNDY) with AI workflow automation trades at ~15x EV/Revenue, while traditional project management SaaS trades at 6–8x. Gong.io's AI-native revenue intelligence platform raised at 25x+ ARR multiples vs. 8–12x for traditional CRM tools.

### vertical_saas — Premium: 0.7

Vertical SaaS with AI-driven workflow automation commands a premium over traditional vertical software, though the premium is moderated by smaller TAMs.

**Comparable:** Veeva Systems (VEEV) with AI-enhanced life sciences cloud trades at ~12x EV/Revenue, while traditional vertical SaaS trades at 5–7x. Procore's construction management platform saw valuation uplift after integrating AI-powered project risk prediction.

### fintech — Premium: 0.6

AI-native fintech (fraud detection, underwriting, algorithmic trading) commands a moderate premium over traditional fintech, tempered by regulatory constraints.

**Comparable:** Upstart (UPST) with AI-native lending trades at ~8x EV/Revenue at peak, while traditional lending platforms trade at 3–4x. Stripe's AI-powered fraud detection (Radar) is a key driver of its premium valuation vs. legacy payment processors.

### developer_tools — Premium: 0.5

AI-native developer tools (code generation, automated testing, AI-powered observability) command a premium over traditional DevOps tooling.

**Comparable:** GitHub Copilot drove meaningful valuation uplift for Microsoft's developer tools segment. Snyk's AI-powered security scanning raised at ~15x ARR vs. 8–10x for traditional SAST/DAST tools. Cursor's AI-native IDE achieved rapid adoption, validating the premium.

### climate_energy — Premium: 0.5

AI-native climate tech (grid optimization, carbon accounting, predictive maintenance) commands a moderate premium over traditional cleantech.

**Comparable:** Arcadia's AI-powered energy data platform raised at premium valuations vs. traditional energy management software. Climavision's AI weather prediction platform commands higher multiples than traditional meteorological services.

### consumer — Premium: 0.4

AI-native consumer apps (personalization engines, generative content, AI companions) command a modest premium, tempered by high churn and competitive dynamics.

**Comparable:** Character.AI raised at ~20x implied revenue multiples with its AI companion platform, while traditional consumer social apps trade at 5–8x. Lensa AI's viral growth demonstrated the premium AI-native consumer products can command, though sustainability is uncertain.

### deep_tech_hardware — Premium: 0.4

AI-native hardware (edge AI chips, autonomous systems, AI-powered robotics) commands a moderate premium over traditional hardware, limited by capital intensity and longer development cycles.

**Comparable:** Cerebras Systems' AI-specific chip architecture raised at premium valuations vs. traditional semiconductor companies. Figure AI's humanoid robotics platform (with AI-native control systems) raised at ~$2.6B valuation, well above traditional robotics companies at similar revenue stages.

### marketplace — Premium: 0.3

AI-native marketplaces (AI-powered matching, dynamic pricing, automated curation) command the smallest premium, as marketplace economics are primarily driven by network effects rather than AI differentiation.

**Comparable:** Faire's AI-powered wholesale marketplace trades at a modest premium over traditional B2B marketplaces. Instacart's AI-driven logistics and personalization contributed to its premium vs. traditional delivery platforms, though the uplift is smaller than in pure software verticals.

---

## AI-Native EV/EBITDA Ranges for M&A Industries

The following `ai_native_ev_ebitda_range` values are added to each of the 21 industries in `industry_benchmarks.json`. Each range has `low`, `median`, and `high` fields, all strictly above the corresponding `ev_ebitda_multiple_range` values.

For `frozen_off` industries (construction, restaurants, retail, real_estate, agriculture, waste_management, staffing), the AI-native ranges represent a minimal uplift — these industries have limited AI premium applicability, but the ranges are included for completeness and to satisfy the schema invariant that `ai_native_ev_ebitda_range.median > ev_ebitda_multiple_range.median`.

| Industry | Base EV/EBITDA (low/med/high) | AI-Native EV/EBITDA (low/med/high) |
|---|---|---|
| Software / SaaS | 12 / 20 / 35 | 20 / 35 / 60 |
| Healthcare Services | 8 / 12 / 18 | 12 / 18 / 28 |
| Manufacturing | 5 / 8 / 12 | 7 / 11 / 16 |
| Professional Services / Consulting | 7 / 10 / 15 | 10 / 15 / 22 |
| HVAC / Mechanical Contracting | 5 / 7 / 10 | 6 / 9 / 13 |
| Construction | 4 / 6 / 9 | 5 / 7 / 10 |
| Restaurants / Food Service | 8 / 12 / 18 | 9 / 14 / 20 |
| Retail | 5 / 8 / 12 | 6 / 9 / 14 |
| Financial Services | 8 / 12 / 18 | 12 / 18 / 28 |
| Oil & Gas Services | 4 / 7 / 11 | 6 / 10 / 15 |
| Transportation / Logistics | 5 / 8 / 12 | 7 / 11 / 16 |
| Real Estate Services | 8 / 12 / 18 | 9 / 14 / 20 |
| Technology Hardware | 7 / 11 / 17 | 10 / 16 / 25 |
| Pharmaceuticals | 10 / 16 / 25 | 14 / 22 / 35 |
| Telecommunications | 5 / 8 / 11 | 7 / 11 / 15 |
| Agriculture | 5 / 8 / 12 | 6 / 9 / 14 |
| Media / Entertainment | 8 / 13 / 20 | 11 / 18 / 28 |
| Insurance | 7 / 11 / 16 | 9 / 14 / 21 |
| Staffing / Recruiting | 5 / 8 / 12 | 6 / 9 / 14 |
| Waste Management | 8 / 12 / 17 | 9 / 14 / 19 |
| Defense & National Security | 10 / 16 / 30 | 15 / 25 / 45 |

For the Defense & National Security industry, the existing `defense_specific.ai_native_ev_revenue` range (8 / 15 / 30) is already present in the benchmarks and provides revenue multiple context for AI-native defense targets.
