# Requirements Document

## Introduction

The AI Valuation Modifier Toggle is an additive layer that sits alongside the vertical selector in both the Startup Valuation and M&A flows. When enabled, it applies a research-backed valuation premium on top of the base vertical's benchmarks, reflecting the 2025–2026 market reality that AI-native companies command 2–5x higher revenue multiples than non-AI peers in the same vertical.

The modifier is purely additive: core financial math (EPS, accretion/dilution, IRR) is never touched. It only affects benchmarking, scorecard context, and verdict language. Deterministic engine output remains the source of truth; AI augments analysis but never overwrites computed numbers.

## Glossary

- **AI_Modifier**: The module (`ai_modifier.py`) that computes and applies the AI-native premium to blended valuations.
- **AI_Toggle**: The UI control that enables or disables the AI-native premium layer for a given deal or startup.
- **AIModifierInput**: Pydantic model carrying `is_ai_native`, `ai_native_score`, `vertical`, and `blended_valuation` into `apply_ai_modifier()`.
- **AIModifierOutput**: Pydantic model returned by `apply_ai_modifier()` carrying `blended_after_ai`, `ai_premium_multiplier`, `ai_modifier_applied`, and `ai_premium_context`.
- **ai_native_score**: Float in [0.0, 1.0] computed as `(count of yes answers) / 4` from the AI Characteristics Assessment.
- **AI_Characteristics_Assessment**: A four-question yes/no sub-step shown when the AI Toggle is ON, used to compute `ai_native_score`.
- **Blended_Valuation**: The output of the startup engine's blending step before any AI modifier is applied.
- **Frozen_On**: Toggle state for verticals where AI-native status is definitional (e.g., `ai_ml_infrastructure`, `ai_enabled_saas`); toggle is locked ON and the assessment is skipped.
- **Frozen_Off**: Toggle state for verticals where AI premium does not apply (e.g., construction, restaurants); toggle is locked OFF.
- **Default_On**: Toggle default state for verticals where AI-native is common (e.g., `defense_tech`, `healthtech`).
- **Default_Off**: Toggle default state for verticals where AI-native is possible but not the norm.
- **Startup_Engine**: `startup_engine.py` — `run_startup_valuation(inp: StartupInput)` entry point.
- **MA_Engine**: `financial_engine.py` and `risk_analyzer.py` — `run_deal()` entry point.
- **FundraisingProfile**: Pydantic model inside `startup_models.py`; `StartupInput.fundraise` field.
- **TargetProfile**: Pydantic model inside `models.py`; `DealInput.target` field.
- **StartupValuationOutput**: Pydantic model returned by `run_startup_valuation()`.
- **DealOutput**: Pydantic model returned by `run_deal()`.
- **vdata**: The vertical benchmark data object passed to engine helper functions, containing `p25`, `p50`, `p75`, `p95`, and ARR multiples.
- **ai_toggle_config.json**: Configuration file at `backend/app/data/ai_toggle_config.json` defining per-vertical toggle behavior.
- **ai_modifier_research.md**: Research document at `backend/app/data/ai_modifier_research.md` documenting the premium multipliers and their sources.
- **industry_benchmarks.json**: M&A benchmark data file at `backend/app/data/industry_benchmarks.json`.
- **startup_valuation_benchmarks.json**: Startup benchmark data file at `backend/app/data/startup_valuation_benchmarks.json`.

---

## Requirements

### Requirement 1: AI Toggle Config File

**User Story:** As a backend developer, I want a single config file that defines per-vertical toggle behavior, so that the engine and UI can consistently enforce frozen, default-on, and default-off states without hardcoding logic.

#### Acceptance Criteria

1. THE AI_Modifier SHALL read toggle behavior from `backend/app/data/ai_toggle_config.json` at startup.
2. THE `ai_toggle_config.json` SHALL classify each startup vertical into exactly one of four categories: `frozen_on`, `frozen_off`, `default_on`, or `default_off`.
3. THE `ai_toggle_config.json` SHALL list `ai_ml_infrastructure` and `ai_enabled_saas` under `frozen_on`.
4. THE `ai_toggle_config.json` SHALL list `defense_tech`, `healthtech`, `biotech_pharma`, and `developer_tools` under `default_on`.
5. THE `ai_toggle_config.json` SHALL list all remaining 13 startup verticals and all applicable M&A industries under `default_off` or `frozen_off` as specified in the research document.
6. IF a vertical is not present in `ai_toggle_config.json`, THEN THE AI_Modifier SHALL treat it as `default_off` and emit a warning in the output.

---

### Requirement 2: AI Modifier Research Document

**User Story:** As an analyst, I want a research-backed document that explains the AI premium multipliers, so that I can trust the numbers and cite sources in client deliverables.

#### Acceptance Criteria

1. THE `ai_modifier_research.md` SHALL document the per-vertical `base_premium_multiplier` at `ai_native_score = 1.0` for all 13 startup verticals.
2. THE `ai_modifier_research.md` SHALL cite at least one real-world comparable for each non-frozen vertical premium (e.g., Palantir vs. L3Harris for `defense_tech`).
3. THE `ai_modifier_research.md` SHALL state that `frozen_on` verticals (`ai_ml_infrastructure`, `ai_enabled_saas`) use a multiplier of `1.0` because AI-native status is already priced into their benchmark ranges.
4. THE `ai_modifier_research.md` SHALL document the `ai_native_ev_ebitda_range` values added to `industry_benchmarks.json` for each M&A industry.

---

### Requirement 3: AI Modifier Core Module

**User Story:** As a backend developer, I want a standalone `apply_ai_modifier()` function, so that both the Startup and M&A engines can apply the AI premium through a single, testable interface.

#### Acceptance Criteria

1. THE AI_Modifier SHALL expose `apply_ai_modifier(inp: AIModifierInput) -> AIModifierOutput` as its public interface.
2. THE `AIModifierInput` SHALL contain: `is_ai_native: bool`, `ai_native_score: float`, `vertical: str`, `blended_valuation: float`.
3. THE `AIModifierOutput` SHALL contain: `blended_after_ai: float`, `ai_premium_multiplier: float | None`, `ai_modifier_applied: bool`, `ai_premium_context: str | None`.
4. WHEN `is_ai_native` is `False`, THE AI_Modifier SHALL return `AIModifierOutput` with `blended_after_ai` equal to `blended_valuation`, `ai_modifier_applied` equal to `False`, and `ai_premium_multiplier` equal to `None`.
5. WHEN `is_ai_native` is `True` and `ai_native_score` is `0.0`, THE AI_Modifier SHALL return `blended_after_ai` equal to `blended_valuation` with `ai_modifier_applied` equal to `False`.
6. WHEN `is_ai_native` is `True` and `ai_native_score` is greater than `0.0`, THE AI_Modifier SHALL compute `premium = base_premium_for_vertical × ai_native_score` and return `blended_after_ai = blended_valuation × (1 + premium)`.
7. WHEN `ai_native_score` is `0.5`, THE AI_Modifier SHALL apply exactly half the full vertical premium (graduated premium property).
8. WHEN the vertical is `frozen_on`, THE AI_Modifier SHALL set `ai_modifier_applied` to `False` and return `blended_after_ai` equal to `blended_valuation`, because the benchmark already reflects AI-native pricing.
9. THE AI_Modifier SHALL never raise an exception — IF an error occurs, THEN THE AI_Modifier SHALL return `AIModifierOutput` with `ai_modifier_applied` equal to `False` and a descriptive `ai_premium_context` warning string.
10. THE AI_Modifier SHALL be fully independent of `startup_engine.py` and `financial_engine.py` — it SHALL import no engine-specific code.

---

### Requirement 4: Startup Engine Integration

**User Story:** As an analyst, I want the startup valuation engine to apply the AI modifier after blending and before verdict assignment, so that AI-native startups receive market-accurate valuations without altering the underlying financial math.

#### Acceptance Criteria

1. THE `FundraisingProfile` SHALL include `is_ai_native: bool = False` as an optional field.
2. THE `StartupInput` SHALL propagate `fundraise.is_ai_native` to the engine without requiring changes to existing callers.
3. WHEN `fundraise.is_ai_native` is `True`, THE Startup_Engine SHALL call `apply_ai_modifier()` after the blending step and before `_assign_verdict()`.
4. THE Startup_Engine SHALL pass `blended_after_ai` (not `blended_valuation`) to `_assign_verdict()` when the modifier is applied.
5. THE Startup_Engine SHALL pass `blended_after_ai` (not `blended_valuation`) to `_build_scorecard()` when the modifier is applied.
6. THE `StartupValuationOutput` SHALL include `ai_modifier_applied: bool`, `ai_premium_multiplier: float | None`, and `ai_premium_context: str | None`.
7. THE `StartupValuationOutput` SHALL include `blended_before_ai: float | None` — set to the pre-modifier blended value when `ai_modifier_applied` is `True`, and `None` otherwise.
8. WHEN `fundraise.is_ai_native` is `False`, THE Startup_Engine SHALL produce output identical to the pre-feature baseline for all 143 existing test cases.
9. THE Startup_Engine SHALL include `ai_native_score: float | None` in `StartupValuationOutput` — set to the computed score when `ai_modifier_applied` is `True`, and `None` otherwise.

---

### Requirement 5: M&A Engine Integration

**User Story:** As an M&A analyst, I want the deal engine to use AI-native benchmark ranges when the target is flagged as AI-native, so that purchase price risk and scorecard context reflect AI-native peer multiples.

#### Acceptance Criteria

1. THE `TargetProfile` SHALL include `is_ai_native: bool = False` as a top-level optional field (separate from `defense_profile.is_ai_native`).
2. WHEN `target.is_ai_native` is `True`, THE MA_Engine SHALL use `ai_native_ev_ebitda_range` from `industry_benchmarks.json` in `_purchase_price_risk()` instead of the generic `ev_ebitda_multiple_range`.
3. WHEN `target.is_ai_native` is `True` and the industry is `defense`, THE MA_Engine SHALL use `defense_specific.ai_native_ev_revenue` for revenue multiple benchmarking.
4. THE `DealOutput` SHALL include `ai_modifier_applied: bool` and `ai_benchmark_context: str | None`.
5. WHEN `target.is_ai_native` is `False`, THE MA_Engine SHALL produce output identical to the pre-feature baseline for all existing test cases.
6. THE MA_Engine SHALL set `ai_benchmark_context` to a human-readable string referencing the AI-native peer multiples used (e.g., "Benchmarked against AI-native defense peers: EV/Revenue 8–30x, median 15x").
7. IF `ai_native_ev_ebitda_range` is absent for an industry in `industry_benchmarks.json`, THEN THE MA_Engine SHALL fall back to `ev_ebitda_multiple_range` and set `ai_benchmark_context` to a warning string.

---

### Requirement 6: Industry Benchmarks Update

**User Story:** As a backend developer, I want `industry_benchmarks.json` to include AI-native benchmark ranges for every M&A industry, so that the M&A engine can switch to AI-native comps without hardcoded values.

#### Acceptance Criteria

1. THE `industry_benchmarks.json` SHALL add an `ai_native_ev_ebitda_range` object to each of the 21 M&A industries, with `low`, `median`, and `high` fields.
2. THE `ai_native_ev_ebitda_range` values SHALL be higher than the corresponding `ev_ebitda_multiple_range` values for every industry, reflecting the AI-native premium.
3. THE `industry_benchmarks.json` SHALL remain valid JSON after the update — IF the file fails JSON schema validation, THEN the backend startup SHALL raise a descriptive error.

---

### Requirement 7: AI Characteristics Assessment

**User Story:** As an analyst, I want to answer four yes/no questions about a company's AI characteristics, so that the premium is calibrated to the company's actual AI-nativeness rather than a binary on/off.

#### Acceptance Criteria

1. THE AI_Characteristics_Assessment SHALL present exactly four yes/no questions when the AI Toggle is ON and the vertical is not `frozen_on`.
2. THE four questions SHALL be:
   - "AI/ML is the core product, not a feature added to existing software"
   - "The company has proprietary training data or models competitors can't easily replicate"
   - "R&D spending is above 25% of revenue"
   - "The product improves with usage — more data or users makes it better"
3. THE AI_Characteristics_Assessment SHALL compute `ai_native_score = (count of yes answers) / 4`.
4. WHEN all four answers are "yes", THE AI_Characteristics_Assessment SHALL produce `ai_native_score = 1.0`.
5. WHEN all four answers are "no", THE AI_Characteristics_Assessment SHALL produce `ai_native_score = 0.0`.
6. THE AI_Characteristics_Assessment SHALL default all four answers to "no" when first shown.
7. WHEN the AI Toggle is turned OFF, THE AI_Characteristics_Assessment SHALL reset all answers to "no" and set `ai_native_score` to `0.0`.

---

### Requirement 8: Frontend — Startup Valuation AI Toggle

**User Story:** As an analyst using the Startup Valuation flow, I want an AI-native toggle in Step 1 alongside the vertical selector, so that I can enable the AI premium layer without navigating away from the overview step.

#### Acceptance Criteria

1. THE `StartupStep1_Overview` component SHALL render the AI Toggle immediately below the vertical selector.
2. WHEN the selected vertical is `frozen_on`, THE `StartupStep1_Overview` component SHALL render the AI Toggle in a locked-ON state with a tooltip explaining "This vertical is AI-native by definition."
3. WHEN the selected vertical is `frozen_off`, THE `StartupStep1_Overview` component SHALL render the AI Toggle in a locked-OFF state with a tooltip explaining "AI premium does not apply to this vertical."
4. WHEN the selected vertical is `default_on`, THE `StartupStep1_Overview` component SHALL render the AI Toggle in the ON state by default.
5. WHEN the selected vertical is `default_off`, THE `StartupStep1_Overview` component SHALL render the AI Toggle in the OFF state by default.
6. WHEN the AI Toggle is turned ON and the vertical is not `frozen_on`, THE `StartupStep1_Overview` component SHALL display the `StartupStep1b_AICharacteristics` sub-step.
7. THE `useStartupState` hook SHALL persist `is_ai_native`, `ai_native_score`, and the four assessment answers to `localStorage`.
8. WHEN the vertical is changed, THE `StartupStep1_Overview` component SHALL re-evaluate the toggle default state according to `ai_toggle_config.json` and reset the assessment answers.

---

### Requirement 9: Frontend — AI Characteristics Sub-Step Component

**User Story:** As a frontend developer, I want a dedicated `StartupStep1b_AICharacteristics` component, so that the four-question assessment is encapsulated and reusable.

#### Acceptance Criteria

1. THE `StartupStep1b_AICharacteristics` component SHALL render four yes/no toggle rows, one per AI characteristic question.
2. THE `StartupStep1b_AICharacteristics` component SHALL display the computed `ai_native_score` as a fraction (e.g., "3 / 4") and as a descriptive label (e.g., "Strongly AI-Native", "Moderately AI-Native", "Marginally AI-Native", "Not AI-Native").
3. WHEN `ai_native_score` is `1.0`, THE `StartupStep1b_AICharacteristics` component SHALL display the label "Strongly AI-Native".
4. WHEN `ai_native_score` is `0.75`, THE `StartupStep1b_AICharacteristics` component SHALL display the label "Strongly AI-Native".
5. WHEN `ai_native_score` is `0.5`, THE `StartupStep1b_AICharacteristics` component SHALL display the label "Moderately AI-Native".
6. WHEN `ai_native_score` is `0.25`, THE `StartupStep1b_AICharacteristics` component SHALL display the label "Marginally AI-Native".
7. WHEN `ai_native_score` is `0.0`, THE `StartupStep1b_AICharacteristics` component SHALL display the label "Not AI-Native".
8. THE `StartupStep1b_AICharacteristics` component SHALL use the `purple-*` color scheme consistent with the Startup Valuation flow.

---

### Requirement 10: Frontend — M&A AI Toggle

**User Story:** As an M&A analyst, I want an AI-native toggle in the M&A Deal Overview step for the target company, so that I can flag AI-native targets and receive AI-adjusted benchmark context.

#### Acceptance Criteria

1. THE `Step1_DealOverview` component SHALL render the AI Toggle for the target company section.
2. WHEN the AI Toggle is ON, THE `Step1_DealOverview` component SHALL set `target.is_ai_native = True` in deal state.
3. WHEN the AI Toggle is OFF, THE `Step1_DealOverview` component SHALL set `target.is_ai_native = False` in deal state.
4. THE `useDealState` hook SHALL persist `target.is_ai_native` to `localStorage`.
5. THE `Step1_DealOverview` component SHALL use the `blue-*` color scheme consistent with the M&A flow.
6. WHEN the target industry is `defense` and `defense_profile.is_ai_native` is already `True`, THE `Step1_DealOverview` component SHALL render the AI Toggle in the locked-ON state.

---

### Requirement 11: Frontend — Output Display

**User Story:** As an analyst, I want the output dashboards to surface AI modifier context when applied, so that I can explain the premium to stakeholders.

#### Acceptance Criteria

1. WHEN `ai_modifier_applied` is `True` in `StartupValuationOutput`, THE `StartupDashboard` component SHALL display a banner showing the premium percentage applied and the `ai_premium_context` string.
2. WHEN `ai_modifier_applied` is `True` in `StartupValuationOutput`, THE `StartupDashboard` component SHALL display both `blended_before_ai` and `blended_after_ai` valuations for transparency.
3. WHEN `ai_modifier_applied` is `False`, THE `StartupDashboard` component SHALL not render any AI modifier UI elements.
4. WHEN `ai_modifier_applied` is `True` in `DealOutput`, THE `ResultsDashboard` component SHALL display the `ai_benchmark_context` string in the purchase price risk section.
5. WHEN `ai_modifier_applied` is `False` in `DealOutput`, THE `ResultsDashboard` component SHALL not render any AI benchmark context UI elements.

---

### Requirement 12: TypeScript Type Mirroring

**User Story:** As a frontend developer, I want the TypeScript types to mirror the updated Pydantic models exactly, so that the frontend and backend stay in sync without runtime type errors.

#### Acceptance Criteria

1. THE `frontend/src/types/startup.ts` SHALL add `is_ai_native: boolean` to the `FundraisingProfile` type with a default-compatible value of `false`.
2. THE `frontend/src/types/startup.ts` SHALL add `ai_modifier_applied: boolean`, `ai_premium_multiplier: number | null`, `ai_premium_context: string | null`, `blended_before_ai: number | null`, and `ai_native_score: number | null` to the `StartupValuationOutput` type.
3. THE `frontend/src/types/deal.ts` SHALL add `is_ai_native: boolean` to the `TargetProfile` type.
4. THE `frontend/src/types/deal.ts` SHALL add `ai_modifier_applied: boolean` and `ai_benchmark_context: string | null` to the `DealOutput` type.
5. THE TypeScript compiler SHALL report zero type errors after the type updates when running `npm run typecheck`.

---

### Requirement 13: Backward Compatibility and Test Coverage

**User Story:** As a developer, I want the AI modifier to be fully opt-in with no impact on existing behavior when disabled, so that the 143 existing tests continue to pass without modification.

#### Acceptance Criteria

1. WHEN `is_ai_native` is `False` (the default), THE Startup_Engine SHALL produce output byte-for-byte identical to the pre-feature baseline for all existing test inputs.
2. WHEN `is_ai_native` is `False` (the default), THE MA_Engine SHALL produce output byte-for-byte identical to the pre-feature baseline for all existing test inputs.
3. THE `test_ai_modifier.py` test file SHALL include a unit test for `apply_ai_modifier()` with `is_ai_native=False` verifying no premium is applied.
4. THE `test_ai_modifier.py` test file SHALL include a unit test verifying that `ai_native_score=0.5` produces exactly half the full vertical premium (graduated premium property).
5. THE `test_ai_modifier.py` test file SHALL include a unit test verifying that `frozen_on` verticals return `ai_modifier_applied=False` regardless of `ai_native_score`.
6. THE test suite SHALL include a fixture `ai_native_defense_deal.json` representing a $40M revenue AI-native defense company with toggle ON and `ai_native_score=1.0`.
7. WHEN the `ai_native_defense_deal.json` fixture is run with `is_ai_native=False`, THE MA_Engine SHALL produce output with `ai_modifier_applied=False` and no AI benchmark context.
8. THE full test suite of 143 pre-existing tests SHALL pass without modification after the feature is implemented.
