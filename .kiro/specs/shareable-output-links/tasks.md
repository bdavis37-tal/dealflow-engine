c# Tasks: Shareable Output Links

## Task List

- [x] 1. Install lz-string dependency
  - [x] 1.1 Run `npm install lz-string` and `npm install --save-dev @types/lz-string` in `frontend/`
  - [x] 1.2 Verify `lz-string` and `@types/lz-string` appear in `frontend/package.json`

- [x] 2. Create shareUtils.ts
  - [x] 2.1 Create `frontend/src/lib/shareUtils.ts` with `ShareModule`, `SharePayload`, `MAInputState`, `StartupInputState`, `VCInputState` type definitions
  - [x] 2.2 Implement `encodeState(module, state)` — JSON.stringify + LZString.compressToEncodedURIComponent, with length guard (throw if > 8000 chars)
  - [x] 2.3 Implement `decodeState(encoded)` — LZString decompress + JSON.parse + structural validation, returns `null` on any failure, never throws
  - [x] 2.4 Implement `parseShareHash(hash)` — extracts encoded string from `#share=...`, returns `null` if absent or empty
  - [x] 2.5 Export `SCHEMA_VERSION = 1` constant

- [-] 3. Write unit tests for shareUtils.ts
  - [x] 3.1 Create `frontend/src/test/shareUtils.test.ts`
  - [x] 3.2 Test round-trip fidelity for M&A, Startup, and VC state objects
  - [x] 3.3 Test `decodeState` returns `null` for empty string, random garbage, truncated payload, wrong version, unknown module
  - [x] 3.4 Test `parseShareHash` for valid hash, empty string, non-share hash
  - [x] 3.5 Test `encodeState` throws when output exceeds 8000 chars (mock oversized state)

- [x] 4. Create ShareButton component
  - [x] 4.1 Create `frontend/src/components/shared/ShareButton.tsx`
  - [x] 4.2 Accept `module`, `inputState`, `colorScheme`, and optional `className` props
  - [x] 4.3 On click: call `encodeState`, set `window.location.hash`, copy URL to clipboard
  - [x] 4.4 Implement 2-second "Copied!" feedback state, then revert to "Share"
  - [x] 4.5 Handle clipboard API unavailability with `window.prompt` fallback
  - [x] 4.6 Catch `encodeState` size error and display inline "State too large to share." message
  - [x] 4.7 Apply correct Tailwind color classes based on `colorScheme` prop (`blue-*`, `purple-*`, `emerald-*`)

- [x] 5. Add hash hydration to App.tsx
  - [x] 5.1 Add a `useEffect([], [])` at the top of `App` that calls `parseShareHash` and `decodeState` on mount
  - [x] 5.2 For `module === 'ma'`: call the existing `useDealState` updaters (`updateAcquirer`, `updateTarget`, `updateStructure`, `updatePPA`, `updateSynergies`, `setMode`) with decoded fields
  - [x] 5.3 For `module === 'startup'`: call `useStartupState` updaters (`setCompanyName`, `updateTeam`, `updateTraction`, `updateProduct`, `updateMarket`, `updateFundraise`, `setAINative`) with decoded fields
  - [x] 5.4 For `module === 'vc'`: call `useVCState` updaters (`updateFund`, `updateDeal`) with decoded fields
  - [x] 5.5 After hydration, call `setAppView(payload.module)` and clear `window.location.hash = ""`
  - [x] 5.6 If `decodeState` returns `null`, do nothing (silent fallback)

- [x] 6. Add ShareButton to M&A ResultsDashboard
  - [x] 6.1 Import `ShareButton` in `frontend/src/components/output/ResultsDashboard.tsx`
  - [x] 6.2 Accept `dealInput` (already a prop) to construct `MAInputState`
  - [x] 6.3 Render `<ShareButton module="ma" inputState={...} colorScheme="blue" />` in the results header area

- [x] 7. Add ShareButton to Startup StartupDashboard
  - [x] 7.1 Import `ShareButton` in `frontend/src/components/output/startup/StartupDashboard.tsx`
  - [x] 7.2 Accept `startupInput` (already a prop) to construct `StartupInputState`; also accept `isAiNative`, `aiNativeScore`, `aiAnswers` props or derive from existing props
  - [x] 7.3 Render `<ShareButton module="startup" inputState={...} colorScheme="purple" />` in the results header area

- [x] 8. Add ShareButton to VC VCDashboard
  - [x] 8.1 Import `ShareButton` in `frontend/src/components/vc/VCDashboard.tsx`
  - [x] 8.2 Accept `fund` and `deal` props (already available) to construct `VCInputState`
  - [x] 8.3 Render `<ShareButton module="vc" inputState={...} colorScheme="emerald" />` in the results header area

- [x] 9. Type-check and lint
  - [x] 9.1 Run `npm run typecheck` in `frontend/` — zero errors
  - [x] 9.2 Run `npm run lint` in `frontend/` — zero new warnings
