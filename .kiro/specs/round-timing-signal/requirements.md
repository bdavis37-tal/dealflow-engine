# Requirements: Round Timing Signal

## Introduction

The Round Timing Signal surfaces a fundraising readiness and timing assessment in the Startup Valuation output. It tells founders how many months of runway they have, whether that runway is sufficient to reach the next funding milestone, a clear action signal, and what milestones the engine expects them to hit before the next round — all derived from data already present in `StartupInput` and `startup_valuation_benchmarks.json`. No new user inputs are required.

---

## Requirements

### 1. Runway Computation

**User story**: As a founder, I want to see exactly how many months of runway I have at my current burn rate, so I can understand my fundraising urgency.

#### Acceptance Criteria

1.1 Given `traction.monthly_burn_rate > 0`, the engine SHALL compute `runway_months = traction.cash_on_hand / traction.monthly_burn_rate` and store it on `RoundTimingSignal.runway_months`, rounded to one decimal place.

1.2 Given `traction.monthly_burn_rate == 0`, the engine SHALL set `runway_months = 0.0` and append a warning: `"No burn rate provided — runway cannot be computed. Signal defaults to raise_now."` to `RoundTimingSignal.warnings`.

1.3 `runway_months` SHALL always be `>= 0.0` (no negative values).

---

### 2. Stage-to-Stage Timeline

**User story**: As a founder, I want to know the typical time between my current stage and the next round, so I can plan my fundraising calendar against market norms.

#### Acceptance Criteria

2.1 Given `fundraise.stage == seed`, the engine SHALL set `months_to_next_round = 24` (sourced from `market_wide_medians.series_a.avg_months_seed_to_series_a`).

2.2 Given `fundraise.stage == pre_seed`, the engine SHALL set `months_to_next_round = 18` (hardcoded estimate; no benchmark field exists for pre-seed→seed).

2.3 Given `fundraise.stage == series_a`, the engine SHALL set `months_to_next_round = 0`, append a warning `"Series A is the terminal stage in this engine — no next-round timeline available."`, and set `signal = focus_milestones`.

2.4 `fundraise_process_months` SHALL be set to `3` (standard time to close a round) and included in `RoundTimingSignal` for UI display.

---

### 3. Raise Signal

**User story**: As a founder, I want a single clear action signal — raise now, raise soon, or focus on milestones — so I know what to prioritize this quarter.

#### Acceptance Criteria

3.1 The engine SHALL compute `months_until_raise_window = runway_months - months_to_next_round - fundraise_process_months`.

3.2 Given `runway_months < (fundraise_process_months + 3)` (i.e., less than ~6 months total), the engine SHALL set `signal = raise_now`.

3.3 Given `months_until_raise_window` is in the range `[0, 6]` (inclusive), the engine SHALL set `signal = raise_in_months` and set `raise_in_months = months_until_raise_window`.

3.4 Given `months_until_raise_window > 6`, the engine SHALL set `signal = focus_milestones`.

3.5 `raise_in_months` SHALL be `None` when `signal != raise_in_months`.

3.6 The three signal values SHALL be mutually exclusive and exhaustive — every input resolves to exactly one signal.

3.7 `months_until_raise_window` SHALL be stored as-is (including negative values) — it SHALL NOT be clamped, so the full severity of a short runway is visible.

---

### 4. Milestone Gaps

**User story**: As a founder, I want to know exactly what traction milestones I need to hit before my next round, so I can focus my team on the right metrics.

#### Acceptance Criteria

4.1 The engine SHALL look up the **next stage's** benchmark block (`_get_vertical_data(vertical, next_stage)`) to derive milestone criteria — not the current stage's block.

4.2 Given `next_vdata["arr_required_min"]` is not null, the engine SHALL check `traction.annual_recurring_revenue >= arr_required_min`. If not met, it SHALL append `"Reach ${arr_required_min}M ARR minimum (currently ${arr:.2f}M)"` to `milestone_gaps`.

4.3 Given `next_vdata["arr_required_typical"]` is not null, the engine SHALL check `traction.annual_recurring_revenue >= arr_required_typical`. If not met, it SHALL append `"Reach ${arr_required_typical}M ARR (typical for {next_stage}) (currently ${arr:.2f}M)"` to `milestone_gaps`.

4.4 Given `next_vdata["yoy_growth_expected"]` is not null, the engine SHALL compute `yoy_approx = traction.mom_growth_rate * 12` and check `yoy_approx >= yoy_growth_expected`. If not met, it SHALL append `"Sustain {yoy_growth_expected:.0f}x YoY growth (currently ~{yoy_approx:.1f}x)"` to `milestone_gaps`.

4.5 Given `next_vdata["traction_bar"]` is a non-empty string, the engine SHALL always append `"Traction bar for {next_stage}: {traction_bar}"` to `milestone_gaps` as qualitative context, regardless of whether quantitative criteria are met.

4.6 For verticals where quantitative ARR fields are null (e.g., `biotech_pharma`, `deep_tech_hardware` at pre-seed), the engine SHALL skip quantitative checks and use only the `traction_bar` text as the milestone descriptor. No exception SHALL be raised.

4.7 `milestone_gaps` SHALL always be a list (never null). It MAY be empty if all quantitative criteria are met and no traction bar text exists.

4.8 The engine SHALL track `milestone_met_count` (criteria already met) and `milestone_total_count` (total criteria checked). The invariant `milestone_met_count + len(quantitative_gaps) == milestone_total_count` SHALL hold at all times.

---

### 5. Output Model Integration

**User story**: As a developer, I want `RoundTimingSignal` to be a first-class field on `StartupValuationOutput` so the frontend can always rely on it being present.

#### Acceptance Criteria

5.1 A new `RaiseSignal` enum SHALL be added to `startup_models.py` with values `raise_now`, `raise_in_months`, `focus_milestones`.

5.2 A new `RoundTimingSignal` Pydantic model SHALL be added to `startup_models.py` with fields: `runway_months`, `months_to_next_round`, `fundraise_process_months`, `months_until_raise_window`, `signal`, `signal_label`, `signal_detail`, `milestone_gaps`, `milestone_met_count`, `milestone_total_count`, `raise_in_months`, `warnings`.

5.3 `StartupValuationOutput` SHALL include a `round_timing: RoundTimingSignal` field (non-optional). The field SHALL always be populated — never null.

5.4 `_compute_round_timing(inp, vdata)` SHALL be called at the end of `run_startup_valuation`, after all existing computation, and its result assigned to `round_timing` on the output object.

5.5 The engine SHALL never raise an exception from `_compute_round_timing` for any valid `StartupInput`. All edge cases SHALL be handled by returning a valid `RoundTimingSignal` with appropriate `warnings`.

---

### 6. TypeScript Type Mirror

**User story**: As a frontend developer, I want the TypeScript types to exactly mirror the backend Pydantic models so I get compile-time safety when building the UI.

#### Acceptance Criteria

6.1 A `RaiseSignal` type alias SHALL be added to `frontend/src/types/startup.ts`: `export type RaiseSignal = 'raise_now' | 'raise_in_months' | 'focus_milestones'`.

6.2 A `RoundTimingSignal` interface SHALL be added to `frontend/src/types/startup.ts` mirroring the Pydantic model field-for-field, with `raise_in_months: number | null` and `warnings: string[]`.

6.3 `StartupValuationOutput` in `startup.ts` SHALL include `round_timing: RoundTimingSignal` (non-optional).

---

### 7. RoundTimingPanel UI Component

**User story**: As a founder viewing my valuation report, I want a clear, visually distinct panel that shows my timing signal, runway, and milestone gaps so I can act on the information immediately.

#### Acceptance Criteria

7.1 A `RoundTimingPanel` component SHALL be created at `frontend/src/components/output/startup/RoundTimingPanel.tsx`.

7.2 The panel SHALL display a signal badge with color coding: `raise_now` = `red-*`, `raise_in_months` = `amber-*`, `focus_milestones` = `green-*`.

7.3 The panel SHALL display `signal_label` as the primary headline and `signal_detail` as supporting text.

7.4 The panel SHALL display `runway_months` and `months_to_next_round` as a visual runway bar or numeric comparison (e.g., "14 months runway / 27 months needed").

7.5 The panel SHALL render `milestone_gaps` as a list. Each item SHALL have a cross icon (gap not met). Items that are met (not in `milestone_gaps`) SHALL NOT be shown as gaps.

7.6 When `RoundTimingSignal.warnings` is non-empty, the panel SHALL render an inline warning section using the existing warning styling pattern from `WarningsPanel`.

7.7 The panel SHALL use the `purple-*` color scheme consistent with the startup module.

7.8 The panel SHALL follow the dark-mode-only convention (`slate-900`/`slate-800` backgrounds).

---

### 8. Dashboard Integration

**User story**: As a founder, I want the timing signal to appear prominently in my valuation report so I don't miss it.

#### Acceptance Criteria

8.1 `StartupDashboard` SHALL import and render `RoundTimingPanel` passing `output.round_timing` and `output.stage` as props.

8.2 `RoundTimingPanel` SHALL be placed after the `TractionBarPanel` and before the `WarningsPanel` in the dashboard layout, so it appears in the upper section of the report where founders look first.

8.3 The panel SHALL always render (it is never conditionally hidden) since `round_timing` is always present on the output.
