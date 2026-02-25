# Requirements: Shareable Output Links

## Overview

Users can generate a shareable URL from any module's results screen that encodes the current input state into the URL hash fragment. Recipients open the link and see the same inputs pre-populated, then re-run the engine themselves. No backend storage is used.

---

## Requirement 1: URL Encoding of Input State

**User Story**: As a user viewing analysis results, I want to generate a shareable URL so that I can send my exact inputs to a co-founder, advisor, or investor without them having to re-enter everything.

### Acceptance Criteria

1.1 — Clicking the Share button on any results screen encodes the current module's input state into the URL hash as `#share=<lz-string-compressed-base64>`.

1.2 — The encoded payload contains a schema version field (`v`), a module identifier (`module`), and the input state (`state`). It never contains output data, loading state, or error state.

1.3 — The `lz-string` library (`compressToEncodedURIComponent` / `decompressFromEncodedURIComponent`) is used for compression. The resulting string is URL-safe without additional encoding.

1.4 — The encoded URL is automatically copied to the clipboard when the Share button is clicked.

1.5 — If the clipboard API is unavailable (non-HTTPS context), a fallback `window.prompt` dialog displays the URL for manual copying.

1.6 — The Share button shows a "Copied!" confirmation for 2 seconds after a successful copy, then reverts to its default label.

---

## Requirement 2: URL Decoding and State Hydration

**User Story**: As a recipient of a share link, I want the app to automatically pre-populate the input form with the sender's data when I open the URL so that I can review and re-run the analysis without re-entering anything.

### Acceptance Criteria

2.1 — On app mount, if `window.location.hash` starts with `#share=`, the app attempts to decode and hydrate state before rendering any module UI.

2.2 — After successful hydration, the app navigates to the correct module view (`'ma'`, `'startup'`, or `'vc'`) as indicated by the `module` field in the decoded payload.

2.3 — After hydration, the module's input form is pre-populated with the decoded state values. The user starts at step 1 of the input flow regardless of what step the sender was on.

2.4 — After hydration, `window.location.hash` is cleared so that refreshing the page loads the app normally without re-triggering hydration.

2.5 — Output, loading state, and error state are never hydrated from the URL — they always start at their default values (`null`, `false`, `null`).

---

## Requirement 3: Error Resilience

**User Story**: As a recipient of a share link, I want the app to load normally even if the link is malformed, expired, or from an incompatible version, so that I'm never stuck on a broken screen.

### Acceptance Criteria

3.1 — If the hash fragment cannot be decompressed or parsed as valid JSON, the app silently ignores it and loads in the default state. No error is thrown or displayed.

3.2 — If the decoded payload's schema version (`v`) does not match the current `SCHEMA_VERSION` constant, the payload is rejected and the app loads in the default state.

3.3 — If the decoded payload's `module` field is not one of `'ma' | 'startup' | 'vc'`, the payload is rejected and the app loads in the default state.

3.4 — `decodeState()` never throws under any input — it always returns either a valid `SharePayload` or `null`.

3.5 — If the encoded state is too large (compressed+encoded string exceeds 8000 characters), the Share button displays an inline error message: "State too large to share." No URL is generated.

---

## Requirement 4: Module Coverage

**User Story**: As a user of any of the three modules, I want the share feature available on my results screen so that I can share any type of analysis.

### Acceptance Criteria

4.1 — A Share button appears on the M&A `ResultsDashboard` component when results are displayed.

4.2 — A Share button appears on the Startup `StartupDashboard` component when results are displayed.

4.3 — A Share button appears on the VC `VCDashboard` component when results are displayed.

4.4 — The Share button uses the module's color scheme: `blue-*` for M&A, `purple-*` for Startup, `emerald-*` for VC.

---

## Requirement 5: Input State Completeness

**User Story**: As a sender, I want all of my input fields to be preserved in the share link so that the recipient sees exactly what I entered.

### Acceptance Criteria

5.1 — For M&A: the encoded state includes `mode`, `acquirer`, `target`, `structure`, `ppa`, and `synergies`.

5.2 — For Startup: the encoded state includes `company_name`, `team`, `traction`, `product`, `market`, `fundraise`, `is_ai_native`, `ai_native_score`, and `ai_answers`.

5.3 — For VC: the encoded state includes `fund` and `deal`.

5.4 — Partial state objects (fields with `undefined` or missing values) are encoded and decoded without error; missing fields fall back to the hook's default values on hydration.

---

## Requirement 6: No Backend Changes

**User Story**: As a developer, I want the share feature to require zero backend changes so that it can be shipped independently of any backend work.

### Acceptance Criteria

6.1 — No new FastAPI endpoints are added.

6.2 — No new Pydantic models are added to the backend.

6.3 — The feature is entirely implemented in the frontend (`shareUtils.ts`, `ShareButton.tsx`, and changes to `App.tsx` and the three results dashboard components).

6.4 — The hash fragment is never sent to the server (browser behavior guarantees this).
