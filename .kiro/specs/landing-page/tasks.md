# Implementation Plan: Landing Page

## Overview

Add a landing page as the default entry point for Dealflow Engine. Introduce an `AppView` type in `App.tsx` to conditionally render the new `LandingPage` component, update the AppShell footer to show "BSL 1.1", and add property-based tests with `fast-check`. All changes are frontend-only (React 18, TypeScript, TailwindCSS).

## Tasks

- [x] 1. Install fast-check and update AppShell footer
  - [x] 1.1 Add `fast-check` as a dev dependency
    - Run `npm install -D fast-check` in the `frontend/` directory
    - _Requirements: Testing infrastructure (Design: Testing Strategy)_

  - [x] 1.2 Update AppShell footer to display "BSL 1.1" instead of "Open Source"
    - In `frontend/src/components/layout/AppShell.tsx`, replace the `<span>Open Source</span>` text with `<span>BSL 1.1</span>`
    - No other changes to AppShell
    - _Requirements: 5.1_

- [x] 2. Create the LandingPage component
  - [x] 2.1 Create `frontend/src/components/layout/LandingPage.tsx`
    - Define `LandingPageProps` interface with `onSelectMode: (mode: 'ma' | 'startup' | 'vc') => void` and `onSkip: () => void`
    - Render a minimal header with "Dealflow Engine" branding (no mode selector)
    - Render a hero section with the app name and a concise platform description ("Institutional-grade deal intelligence across M&A, Startup Valuation, and VC Seat Analysis")
    - Render three mode-selection cards in a responsive grid:
      - M&A Deal Modeling (blue accent: `border-blue-500` / `text-blue-400`)
      - Startup Valuation (purple accent: `border-purple-500` / `text-purple-400`)
      - VC Seat Analysis (emerald accent: `border-emerald-500` / `text-emerald-400`)
    - Each card calls `onSelectMode` with the corresponding mode value on click
    - Render a visually subordinate skip button below the cards (smaller, muted styling) that calls `onSkip`
    - Render a footer with "Dealflow Engine" branding and "BSL 1.1" license text, styled consistently with AppShell footer
    - Use dark-mode styling throughout (`bg-slate-900`, `text-slate-100`, `border-slate-800`)
    - _Requirements: 1.2, 1.3, 2.1, 2.5, 3.1, 3.3, 5.2_

- [x] 3. Integrate LandingPage into App.tsx
  - [x] 3.1 Add `AppView` type and update state in `App.tsx`
    - Add `type AppView = 'landing' | 'ma' | 'startup' | 'vc'` (keep existing `AppMode` type unchanged)
    - Change `useState<AppMode>('ma')` to `useState<AppView>('landing')`
    - Import `LandingPage` from `./components/layout/LandingPage`
    - When `appView === 'landing'`, render `<LandingPage onSelectMode={(mode) => setAppView(mode)} onSkip={() => setAppView('ma')} />`
    - For `'ma' | 'startup' | 'vc'` views, render existing flows unchanged, passing `appView` as `appMode` to `AppShell`
    - Wire `onAppModeChange` from `AppShell` to `setAppView` so mode selector still works
    - _Requirements: 1.1, 2.2, 2.3, 2.4, 3.2, 4.1, 4.2, 4.3, 6.1, 6.2, 6.3, 6.4_

- [x] 4. Checkpoint
  - Ensure the app compiles without errors (`npm run typecheck`), renders the landing page on load, navigates to each mode, and the footer shows "BSL 1.1" in both the landing page and AppShell. Ask the user if questions arise.

- [ ] 5. Write tests for LandingPage and App integration
  - [ ]* 5.1 Write property test: Mode selection navigates to the correct analysis flow
    - **Property 1: Mode selection navigates to the correct analysis flow**
    - Generator: `fc.constantFrom('ma', 'startup', 'vc')`
    - Render `LandingPage`, click the card for the generated mode, assert `onSelectMode` was called with that mode
    - Create test file at `frontend/src/test/LandingPage.property.test.tsx`
    - **Validates: Requirements 2.2, 2.3, 2.4**

  - [ ]* 5.2 Write property test: Mode switching never returns to landing page
    - **Property 3: Mode switching never returns to landing page**
    - Generator: `fc.tuple(fc.constantFrom('ma', 'startup', 'vc'), fc.constantFrom('ma', 'startup', 'vc')).filter(([a, b]) => a !== b)`
    - Render `AppShell` with source mode, click the target mode button, assert `onAppModeChange` was called with the target mode (not `'landing'`)
    - Add to `frontend/src/test/LandingPage.property.test.tsx`
    - **Validates: Requirements 4.2**

  - [ ]* 5.3 Write property test: BSL 1.1 license text is visible in footer across all views
    - **Property 4: BSL 1.1 license text is visible in footer across all views**
    - Generator: `fc.constantFrom('landing', 'ma', 'startup', 'vc')`
    - Render the appropriate component (LandingPage for `'landing'`, AppShell for others), assert footer contains "BSL 1.1"
    - Add to `frontend/src/test/LandingPage.property.test.tsx`
    - **Validates: Requirements 5.1, 5.2**

  - [ ]* 5.4 Write unit tests for LandingPage
    - Test that "Dealflow Engine" and platform description text are rendered (Req 1.2)
    - Test that exactly 3 mode cards are rendered (Req 2.1)
    - Test that skip button exists and calls `onSkip` when clicked (Req 3.1, 3.2)
    - Test that App renders LandingPage on initial load (Req 1.1)
    - Test that LandingPage footer contains "BSL 1.1" (Req 5.2)
    - Create test file at `frontend/src/test/LandingPage.test.tsx`
    - _Requirements: 1.1, 1.2, 2.1, 3.1, 3.2, 5.2_

- [ ] 6. Final checkpoint
  - Ensure all tests pass (`npm test`), ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- All code is TypeScript with React 18 + TailwindCSS, no backend changes
