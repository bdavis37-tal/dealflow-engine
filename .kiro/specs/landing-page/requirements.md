# Requirements Document

## Introduction

Dealflow Engine currently drops users directly into the M&A step flow with no introductory experience. This feature adds a welcoming landing page that explains what the application does, lets users choose their analysis mode (M&A, Startup Valuation, or VC Seat Analysis), and provides a shortcut to jump straight into the current analysis view. A persistent footer displaying the BSL 1.1 license type is also added across all pages.

## Glossary

- **Landing_Page**: The initial view displayed when a user first opens the Dealflow Engine application, serving as the entry point before any analysis mode is selected.
- **App**: The root React component (App.tsx) that manages application state and view routing.
- **AppShell**: The shared layout wrapper that provides the header, step indicator, content area, and footer for all analysis modes.
- **Analysis_Mode**: One of three independent computation modules the user can select: M&A Deal Modeling, Startup Valuation, or VC Seat Analysis.
- **Mode_Selector**: The existing header control that allows users to toggle between the three analysis modes once inside an analysis flow.
- **Footer**: The bottom section of every page rendered by AppShell, displaying branding and license information.
- **Skip_Entry**: A secondary access point on the Landing_Page that routes the user directly to the current analysis view, bypassing the guided mode selection.

## Requirements

### Requirement 1: Display Landing Page on Application Load

**User Story:** As a new user, I want to see a welcoming landing page when I open the application, so that I understand what Dealflow Engine does before starting an analysis.

#### Acceptance Criteria

1. WHEN the App loads for the first time, THE App SHALL render the Landing_Page as the default view instead of the M&A step flow.
2. THE Landing_Page SHALL display the application name "Dealflow Engine" and a concise description of the platform's purpose (institutional-grade deal intelligence across M&A, Startup Valuation, and VC Seat Analysis).
3. THE Landing_Page SHALL use the existing dark-mode visual style (slate-900/800 backgrounds, slate-100 text) consistent with the rest of the application.

### Requirement 2: Mode Selection from Landing Page

**User Story:** As a user, I want to choose my analysis type from the landing page, so that I am routed directly to the correct analysis flow.

#### Acceptance Criteria

1. THE Landing_Page SHALL display three distinct call-to-action elements, one for each Analysis_Mode: M&A Deal Modeling, Startup Valuation, and VC Seat Analysis.
2. WHEN the user selects the M&A call-to-action, THE App SHALL set the active Analysis_Mode to "ma" and navigate to the M&A step flow.
3. WHEN the user selects the Startup Valuation call-to-action, THE App SHALL set the active Analysis_Mode to "startup" and navigate to the Startup step flow.
4. WHEN the user selects the VC Seat Analysis call-to-action, THE App SHALL set the active Analysis_Mode to "vc" and navigate to the VC step flow.
5. THE Landing_Page SHALL visually differentiate each call-to-action using the existing mode color scheme (blue for M&A, purple for Startup, emerald for VC).

### Requirement 3: Skip to Current Analysis View

**User Story:** As a returning user, I want a way to jump directly into the analysis view from the landing page, so that I can resume work without going through mode selection.

#### Acceptance Criteria

1. THE Landing_Page SHALL display a secondary access point (button or link) that allows the user to skip the landing page and enter the analysis view directly.
2. WHEN the user activates the Skip_Entry control, THE App SHALL navigate to the default analysis mode (M&A) step flow, matching the previous application behavior.
3. THE Skip_Entry control SHALL be visually subordinate to the three primary mode call-to-action elements so that new users are guided toward mode selection first.

### Requirement 4: Preserve Existing Mode Toggling

**User Story:** As a user already in an analysis flow, I want to continue toggling between analysis modes using the header Mode_Selector, so that my existing workflow is unaffected.

#### Acceptance Criteria

1. WHILE the user is in any analysis flow, THE AppShell SHALL continue to display the Mode_Selector in the header.
2. WHEN the user switches modes via the Mode_Selector, THE App SHALL transition to the selected Analysis_Mode without returning to the Landing_Page.
3. THE App SHALL preserve all existing state management behavior (localStorage persistence, step tracking, reset functionality) for each Analysis_Mode.

### Requirement 5: License Display in Footer

**User Story:** As a user or evaluator, I want to see the license type on every page, so that I understand the licensing terms of the software.

#### Acceptance Criteria

1. THE Footer SHALL display the text "BSL 1.1" (Business Source License 1.1) on every page rendered by AppShell.
2. THE Landing_Page SHALL include a footer that displays the "BSL 1.1" license text, consistent with the AppShell Footer styling.
3. THE Footer license text SHALL be visible without requiring the user to scroll or interact with any control, provided the footer is in the viewport.

### Requirement 6: No Regression to Existing Functionality

**User Story:** As a user, I want all existing analysis flows to continue working correctly after the landing page is added, so that my experience is only enhanced, not degraded.

#### Acceptance Criteria

1. THE App SHALL render all M&A step flow components (Steps 1 through 6, Results Dashboard, Conversational Entry) with identical behavior to the current implementation.
2. THE App SHALL render all Startup step flow components (Steps 1 through 5, Startup Dashboard) with identical behavior to the current implementation.
3. THE App SHALL render all VC flow components (Fund Setup, Quick Screen, VC Dashboard) with identical behavior to the current implementation.
4. THE App SHALL preserve all existing state hooks (useDealState, useStartupState, useVCState) and localStorage persistence without modification.
