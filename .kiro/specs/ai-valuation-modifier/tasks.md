# Implementation Plan: AI Valuation Modifier Toggle

## Overview

Implement the AI Valuation Modifier Toggle as a purely additive layer on top of existing blended valuations. Follow the project convention order: Pydantic models → engine logic → frontend types → hooks → UI components → output display.

## Tasks

- [x] 1. Baseline test run and data files
  - Run `pytest tests/ -v` to confirm all 143 existing tests pass before any changes
  - Create `backend/app/data/ai_toggle_config.json` with `frozen_on`, `frozen_off`, `default_on`, `default_off` categories and `vertical_premiums` map
  - Create `backend/app/data/ai_modifier_research.md` documenting per-vertical `base_premium_multiplier` values, real-world comparables, and `ai_native_ev_ebitda_range` values for M&A industries
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.2, 2.3, 2.4_

- [ ] 2. Backend Pydantic models
  - [x] 2.1 Update `backend/app/engine/startup_models.py`
    - Add `is_ai_native: bool = Field(default=False)` to `FundraisingProfile`
    - Add `ai_native_score: float = Field(default=0.0, ge=0.0, le=1.0)` to `FundraisingProfile`
    - Add five fields to `StartupValuationOutput`: `ai_modifier_applied`, `ai_premium_multiplier`, `ai_premium_context`, `blended_before_ai`, `ai_native_score`
    - _Requirements: 4.1, 4.6, 4.7, 4.9_

  - [x] 2.2 Update `backend/app/engine/models.py`
    - Add `is_ai_native: bool = Field(default=False)` to `TargetProfile`
    - Add `ai_modifier_applied: bool` and `ai_benchmark_context: Optional[str]` to `DealOutput`
    - _Requirements: 5.1, 5.4_

- [ ] 3. AI Modifier core module
  - [x] 3.1 Create `backend/app/engine/ai_modifier.py`
    - Define `AIModifierInput` and `AIModifierOutput` Pydantic models
    - Load `ai_toggle_config.json` once at module import time (same pattern as `_BENCHMARKS`)
    - Implement `apply_ai_modifier(inp: AIModifierInput) -> AIModifierOutput` with the decision table: `is_ai_native=False` → pass-through; `score=0.0` → pass-through; `frozen_on` vertical → pass-through; otherwise apply `blended_valuation × (1 + base_premium × score)`
    - Wrap entire function body in `try/except Exception` — never raise
    - Handle missing vertical in config (treat as `default_off`, emit warning in `ai_premium_context`)
    - No imports from `startup_engine.py` or `financial_engine.py`
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 3.10_

  - [ ]* 3.2 Write unit tests for `apply_ai_modifier()` in `backend/tests/test_ai_modifier.py`
    - `is_ai_native=False` → pass-through for any vertical and valuation
    - `ai_native_score=0.0` with `is_ai_native=True` → pass-through, `ai_modifier_applied=False`
    - `frozen_on` vertical (`ai_ml_infrastructure`) with `is_ai_native=True`, `score=1.0` → pass-through
    - `defense_tech` with `score=1.0` → `blended_after_ai = blended × 2.5`
    - `defense_tech` with `score=0.5` → `blended_after_ai = blended × 1.75`
    - Unknown vertical → pass-through with warning string in `ai_premium_context`
    - Negative valuation → no exception raised
    - _Requirements: 13.3, 13.4, 13.5_

  - [ ]* 3.3 Write property-based tests in `backend/tests/test_ai_modifier_properties.py` (requires `hypothesis` in dev dependencies)
    - **Property 1: Backward Compatibility** — `is_ai_native=False` produces identical output to baseline
    - **Validates: Requirements 13.1, 13.2, 3.4, 5.5**
    - **Property 2: Graduated Premium Formula** — `blended_after_ai = blended × (1 + base_premium × score)` for all non-frozen verticals and scores in (0.0, 1.0]
    - **Validates: Requirements 3.6, 3.7**
    - **Property 3: Frozen-On Pass-Through** — `ai_ml_infrastructure` and `ai_enabled_saas` always return `ai_modifier_applied=False`
    - **Validates: Requirements 3.8**
    - **Property 4: Zero-Score No-Op** — `score=0.0` with `is_ai_native=True` returns `ai_modifier_applied=False`
    - **Validates: Requirements 3.5**
    - **Property 5: No-Exception Guarantee** — any input including malformed returns `AIModifierOutput` without raising
    - **Validates: Requirements 3.9**
    - **Property 6: Config Completeness** — every `StartupVertical` enum value in exactly one category
    - **Validates: Requirements 1.2**
    - **Property 7: AI-Native Benchmark Uplift Invariant** — `ai_native_ev_ebitda_range.median > ev_ebitda_multiple_range.median` for all industries
    - **Validates: Requirements 6.1, 6.2**
    - **Property 8: Score Computation Correctness** — `score = sum(answers) / 4` for all 16 boolean combinations
    - **Validates: Requirements 7.3, 7.4, 7.5**
    - **Property 9: Score Label Monotonicity** — correct label for each of the 5 score values
    - **Validates: Requirements 9.2, 9.3, 9.4, 9.5, 9.6, 9.7**

- [x] 4. Update `industry_benchmarks.json`
  - Add `ai_native_ev_ebitda_range` object (`low`, `median`, `high`) to each of the 21 M&A industry entries
  - Ensure every `ai_native_ev_ebitda_range.median` is strictly greater than the corresponding `ev_ebitda_multiple_range.median`
  - For the defense industry, also add `defense_specific.ai_native_ev_revenue` for revenue multiple context
  - Validate the file remains valid JSON
  - _Requirements: 6.1, 6.2, 6.3_

- [ ] 5. Startup engine integration
  - [x] 5.1 Update `backend/app/engine/startup_engine.py`
    - Import `apply_ai_modifier` and `AIModifierInput` from `ai_modifier`
    - After the blending step and before `_assign_verdict()`, conditionally call `apply_ai_modifier()` when `inp.fundraise.is_ai_native` is `True`
    - When `ai_mod_output.ai_modifier_applied` is `True`, set `blended_before_ai = blended` and replace `blended` with `blended_after_ai`
    - Pass the (possibly modified) `blended` to both `_assign_verdict()` and `_build_scorecard()`
    - Populate the five new `StartupValuationOutput` fields from `ai_mod_output`
    - _Requirements: 4.2, 4.3, 4.4, 4.5, 4.8_

  - [ ]* 5.2 Write integration test for startup engine with AI modifier
    - `run_startup_valuation()` with `is_ai_native=True`, `ai_native_score=1.0`, `vertical=defense_tech` → verify `ai_modifier_applied=True`, `blended_before_ai` is set
    - `run_startup_valuation()` with `is_ai_native=False` → verify output identical to pre-feature baseline
    - _Requirements: 13.1, 13.8_

- [ ] 6. M&A engine integration
  - [x] 6.1 Update `backend/app/engine/risk_analyzer.py`
    - In `_purchase_price_risk()`, check `deal.target.is_ai_native`; when `True`, use `ai_native_ev_ebitda_range` from benchmarks instead of `ev_ebitda_multiple_range`
    - Fall back to `ev_ebitda_multiple_range` with a warning string when `ai_native_ev_ebitda_range` is absent
    - For defense industry with `is_ai_native=True`, additionally reference `defense_specific.ai_native_ev_revenue`
    - _Requirements: 5.2, 5.3, 5.7_

  - [x] 6.2 Update `backend/app/engine/financial_engine.py`
    - Set `ai_modifier_applied` and `ai_benchmark_context` on `DealOutput` based on `target.is_ai_native` and whether an AI-native range was found
    - Set `ai_benchmark_context` to a human-readable string referencing the AI-native peer multiples used (e.g., "Benchmarked against AI-native defense peers: EV/Revenue 8–30x, median 15x")
    - _Requirements: 5.4, 5.6_

  - [x] 6.3 Create fixture `backend/tests/fixtures/ai_native_defense_deal.json`
    - $40M revenue AI-native defense company (`Sentinel AI`), `acquisition_price: 320.0`, `is_ai_native: true`, `ai_native_score: 1.0`
    - _Requirements: 13.6_

  - [ ]* 6.4 Write unit tests for M&A AI modifier integration
    - Fixture with `is_ai_native=True` → `ai_modifier_applied=True`, `ai_benchmark_context` is non-null
    - Fixture with `is_ai_native=False` → `ai_modifier_applied=False`, `ai_benchmark_context=None`, output identical to baseline
    - _Requirements: 13.7, 13.8_

- [x] 7. Backend checkpoint — run full test suite
  - Run `pytest tests/ -v` and confirm all 143 pre-existing tests pass plus new tests
  - Ensure all tests pass, ask the user if questions arise.
  - _Requirements: 13.8_

- [ ] 8. Frontend TypeScript types
  - [x] 8.1 Update `frontend/src/types/startup.ts`
    - Add `is_ai_native: boolean` to `FundraisingProfile`
    - Add five fields to `StartupValuationOutput`: `ai_modifier_applied`, `ai_premium_multiplier`, `ai_premium_context`, `blended_before_ai`, `ai_native_score`
    - Add `is_ai_native`, `ai_native_score`, `ai_answers` to `StartupState`
    - _Requirements: 12.1, 12.2_

  - [x] 8.2 Update `frontend/src/types/deal.ts`
    - Add `is_ai_native: boolean` to `TargetProfile`
    - Add `ai_modifier_applied: boolean` and `ai_benchmark_context: string | null` to `DealOutput`
    - _Requirements: 12.3, 12.4_

  - Run `npm run typecheck` after both type files are updated and confirm zero errors
  - _Requirements: 12.5_

- [ ] 9. Frontend state hooks
  - [x] 9.1 Update `frontend/src/hooks/useStartupState.ts`
    - Add `is_ai_native`, `ai_native_score`, and `ai_answers: [boolean, boolean, boolean, boolean]` state with `localStorage` persistence
    - Derive `ai_native_score` from `ai_answers` as `answers.filter(Boolean).length / 4`
    - When vertical changes, reset toggle to config-driven default state and reset all four answers to `false`
    - _Requirements: 8.7, 8.8_

  - [x] 9.2 Update `frontend/src/hooks/useDealState.ts`
    - Add `target.is_ai_native` with `localStorage` persistence
    - _Requirements: 10.4_

- [ ] 10. Frontend — Startup flow UI
  - [x] 10.1 Create `frontend/src/components/flow/startup/StartupStep1b_AICharacteristics.tsx`
    - Render four yes/no toggle rows for the AI characteristic questions
    - Display `ai_native_score` as fraction (e.g., "3 / 4") and descriptive label ("Strongly AI-Native", "Moderately AI-Native", "Marginally AI-Native", "Not AI-Native")
    - Use `purple-*` color scheme
    - Props: `answers`, `onAnswerChange`, `ai_native_score`
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 9.8_

  - [x] 10.2 Update `frontend/src/components/flow/startup/StartupStep1_Overview.tsx`
    - Add AI Toggle row immediately below the vertical selector
    - Render toggle in locked-ON state with tooltip for `frozen_on` verticals
    - Render toggle in locked-OFF state with tooltip for `frozen_off` verticals
    - Render toggle ON by default for `default_on` verticals, OFF for `default_off`
    - Show `StartupStep1b_AICharacteristics` sub-step when toggle is ON and vertical is not `frozen_on`
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_

  - [ ]* 10.3 Write unit tests for `StartupStep1b_AICharacteristics`
    - Renders 4 toggle rows
    - Score label mapping for all 5 score values (covers Property 9)
    - Toggle locked-ON state renders correctly for `frozen_on` vertical
    - Answers reset when vertical changes
    - _Requirements: 9.1, 9.2_

- [x] 11. Frontend — M&A flow UI
  - Update `frontend/src/components/flow/Step1_DealOverview.tsx`
  - Add AI Toggle for the target company section using `blue-*` color scheme
  - When toggle ON, set `target.is_ai_native = true` in deal state; when OFF, set `false`
  - When `defense_profile.is_ai_native` is already `true`, render toggle in locked-ON state
  - _Requirements: 10.1, 10.2, 10.3, 10.5, 10.6_

- [ ] 12. Frontend — Output display
  - [x] 12.1 Update `frontend/src/components/output/startup/StartupDashboard.tsx`
    - When `ai_modifier_applied=true`, display a banner showing premium percentage and `ai_premium_context` string
    - When `ai_modifier_applied=true`, display both `blended_before_ai` and `blended_after_ai` for transparency
    - When `ai_modifier_applied=false`, render no AI modifier UI elements
    - _Requirements: 11.1, 11.2, 11.3_

  - [x] 12.2 Update the M&A results dashboard component
    - When `ai_modifier_applied=true` in `DealOutput`, display `ai_benchmark_context` in the purchase price risk section
    - When `ai_modifier_applied=false`, render no AI benchmark context UI elements
    - _Requirements: 11.4, 11.5_

  - [ ]* 12.3 Write unit tests for output display components
    - `StartupDashboard` renders AI modifier banner when `ai_modifier_applied=true`
    - `StartupDashboard` renders nothing AI-related when `ai_modifier_applied=false`
    - `useStartupState` persists `is_ai_native`, `ai_native_score`, `ai_answers` to localStorage
    - _Requirements: 11.1, 11.3_

- [x] 13. Final checkpoint — full test suite
  - Run `pytest tests/ -v` to confirm all backend tests pass
  - Run `npm run typecheck` to confirm zero TypeScript errors
  - Run `npm test` to confirm all frontend tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP
- All monetary values in millions USD; percentages as decimals
- `apply_ai_modifier()` must never raise — catch-all exception handling is required
- The M&A engine does NOT call `apply_ai_modifier()` — it reads `ai_native_ev_ebitda_range` directly from benchmarks
- Property tests require `hypothesis` added to `[project.optional-dependencies] dev` in `pyproject.toml`
