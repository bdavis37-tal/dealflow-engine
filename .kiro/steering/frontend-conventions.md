---
inclusion: fileMatch
fileMatchPattern: "frontend/**/*.{ts,tsx}"
---

# Frontend Conventions

## Stack

- React 18, TypeScript strict mode (no `any`), Vite, TailwindCSS
- Vitest for testing, setup in `src/test/setup.ts`
- UI primitives from Radix UI, charts from Recharts

## App Modes

Three modes: `'ma' | 'startup' | 'vc'` — each has its own shell, state hook, API prefix, and color scheme.

## State Hooks

| Mode | Hook | Color |
|---|---|---|
| M&A | `useDealState` | `blue-*` |
| Startup | `useStartupState` | `purple-*` |
| VC | `useVCState` | `emerald-*` |

- All hooks persist to `localStorage`
- Output is always `null` on reload (recompute required)

## Types

- Types live in `src/types/` and mirror backend Pydantic models exactly
- Monetary values = number in millions, percentages = decimals

## API Clients

| Client | Covers |
|---|---|
| `api.ts` | M&A + Startup |
| `vc-api.ts` | VC |
| `ai-api.ts` | AI streaming |

## AI Streaming

- SSE via `ReadableStream`
- Sentinel values: `[DONE]`, `[AI_UNAVAILABLE]`, `[STREAM_ERROR]`
- Always badge AI-generated content with the `AIBadge` component

## Theming

- Dark-mode only — all classes assume dark background (`slate-900`/`slate-800`)
- Mode colors: M&A = `blue-*`, Startup = `purple-*`, VC = `emerald-*`
- Verdict colors: `green-500` (accretive/strong), `amber-500` (marginal/fair), `red-500` (dilutive/at-risk)
- AI UI: `purple-*` color family
- Custom animations: `animate-fade-in`, `animate-slide-up`

## Component Organization

| Directory | Purpose |
|---|---|
| `flow/` | Step input components |
| `output/` | Result display components |
| `vc/` | VC-specific panels |
| `inputs/` | Form components |
| `layout/` | Shell/layout components |
| `shared/` | Reusable components |

## GuidedInput

- With `fieldName` prop → activates AI help
- Without `fieldName` → falls back to static tooltip
