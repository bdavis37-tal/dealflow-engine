# Tasks: Round Timing Signal

## Implementation Plan

### 1. Backend — Pydantic Models

- [ ] 1.1 Add `RaiseSignal` enum to `backend/app/engine/startup_models.py` with values `raise_now`, `raise_in_months`, `focus_milestones`
- [ ] 1.2 Add `RoundTimingSignal` Pydantic model to `startup_models.py` with all fields: `runway_months`, `months_to_next_round`, `fundraise_process_months`, `months_until_raise_window`, `signal`, `signal_label`, `signal_detail`, `milestone_gaps`, `milestone_met_count`, `milestone_total_count`, `raise_in_months`, `warnings`
- [ ] 1.3 Add `round_timing: RoundTimingSignal` field to `StartupValuationOutput` (non-optional)

### 2. Backend — Engine Logic

- [ ] 2.1 Add `_next_stage_for(stage: StartupStage) -> StartupStage | None` helper to `startup_engine.py` (pre_seed→seed, seed→series_a, series_a→None)
- [ ] 2.2 Implement `_compute_round_timing(inp: StartupInput, vdata: dict) -> RoundTimingSignal` in `startup_engine.py` covering: runway computation, zero-burn edge case, stage timeline lookup, Series A terminal case, signal resolution, milestone gap loop, label/detail string generation
- [ ] 2.3 Call `_compute_round_timing` at the end of `run_startup_valuation` and assign result to `round_timing` on the returned `StartupValuationOutput`

### 3. Frontend — TypeScript Types

- [ ] 3.1 Add `RaiseSignal` type alias to `frontend/src/types/startup.ts`
- [ ] 3.2 Add `RoundTimingSignal` interface to `startup.ts` mirroring the Pydantic model
- [ ] 3.3 Add `round_timing: RoundTimingSignal` to `StartupValuationOutput` interface in `startup.ts`

### 4. Frontend — RoundTimingPanel Component

- [ ] 4.1 Create `frontend/src/components/output/startup/RoundTimingPanel.tsx` with signal badge (red/amber/green), `signal_label` headline, `signal_detail` text, runway display, milestone gaps list with cross icons, and inline warnings section
- [ ] 4.2 Wire `RoundTimingPanel` into `StartupDashboard.tsx` — import, place after `TractionBarPanel` and before `WarningsPanel`, pass `output.round_timing` and `output.stage`

### 5. Tests

- [ ] 5.1 Write unit tests for `_compute_round_timing` covering: zero burn rate, Series A terminal stage, seed + 14 months runway (raise_now), seed + 30 months runway (raise_in_months), seed + 40 months runway (focus_milestones), pre-seed + 24 months runway, biotech null ARR fields, all 13 verticals × 3 stages (no exceptions)
- [ ] 5.2 Write property-based tests using `hypothesis` verifying: no exceptions for any valid input, `runway_months == cash_on_hand / monthly_burn_rate` when burn > 0, signal is always one of three enum values, `milestone_gaps` is always a list of strings, `round_timing` always present on `run_startup_valuation` output
