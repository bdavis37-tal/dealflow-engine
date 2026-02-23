import React from 'react'
import StepIndicator from './StepIndicator'
import ModelDepthToggle from './ModelDepthToggle'
import type { ModelMode } from '../../types/deal'

type AppMode = 'ma' | 'startup' | 'vc'

// ---------------------------------------------------------------------------
// Mode accent color schemes
// ---------------------------------------------------------------------------
const MODE_COLORS: Record<AppMode, {
  gradient: string
  accentText: string
  accentLabel: string
}> = {
  ma: {
    gradient: 'from-blue-500 to-blue-700',
    accentText: 'text-blue-400',
    accentLabel: 'M&A Deal Modeling',
  },
  startup: {
    gradient: 'from-purple-500 to-purple-700',
    accentText: 'text-purple-400',
    accentLabel: 'Startup Valuation',
  },
  vc: {
    gradient: 'from-emerald-500 to-emerald-700',
    accentText: 'text-emerald-400',
    accentLabel: 'VC Investor',
  },
}

const MODE_ACTIVE_BG: Record<AppMode, string> = {
  ma: 'bg-blue-600 text-white shadow-sm',
  startup: 'bg-purple-600 text-white shadow-sm',
  vc: 'bg-emerald-600 text-white shadow-sm',
}

// ---------------------------------------------------------------------------
// Step configs per mode
// ---------------------------------------------------------------------------
const MODE_STEPS: Record<AppMode, Array<{ label: string; short: string }>> = {
  ma: [
    { label: 'Deal Overview', short: 'Overview' },
    { label: "Buyer's Profile", short: 'Buyer' },
    { label: "Target's Profile", short: 'Target' },
    { label: 'Financing', short: 'Financing' },
    { label: 'Expected Benefits', short: 'Benefits' },
    { label: 'Review & Analyze', short: 'Analyze' },
  ],
  startup: [
    { label: 'Overview & Fundraise', short: 'Overview' },
    { label: 'Team', short: 'Team' },
    { label: 'Traction & Product', short: 'Traction' },
    { label: 'Market', short: 'Market' },
  ],
  vc: [
    { label: 'Fund Profile', short: 'Fund' },
    { label: 'Deal Screen', short: 'Deal' },
  ],
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------
interface AppShellProps {
  children: React.ReactNode
  appMode: AppMode
  onAppModeChange: (mode: AppMode) => void
  /** Navigate back to landing page */
  onHome?: () => void
  /** Current step (1-indexed) */
  step?: number
  /** Whether we're showing results (hides step nav, shows completed state) */
  isResults?: boolean
  /** M&A model depth toggle */
  modelMode?: ModelMode
  onModelModeChange?: (mode: ModelMode) => void
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export default function AppShell({
  children,
  appMode,
  onAppModeChange,
  onHome,
  step,
  isResults,
  modelMode,
  onModelModeChange,
}: AppShellProps) {
  const modeColor = MODE_COLORS[appMode]
  const steps = MODE_STEPS[appMode]
  const totalSteps = steps.length

  return (
    <div className="min-h-screen bg-navy-900 text-slate-100 font-sans">
      {/* Header */}
      <header className="border-b border-slate-800 bg-navy-800/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 h-14 flex items-center justify-between">
          {/* Logo + mode label */}
          <button
            onClick={onHome}
            className="flex items-center gap-3 hover:opacity-80 transition-opacity focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-1 focus-visible:ring-offset-slate-900 rounded-lg"
            title="Back to home"
          >
            <div className={`w-7 h-7 rounded-lg bg-gradient-to-br ${modeColor.gradient} flex items-center justify-center`}>
              <span className="text-white text-xs font-bold">DE</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="font-semibold text-slate-100 text-sm">Dealflow Engine</span>
              <span className="text-slate-600 text-sm hidden sm:inline">&middot;</span>
              <span className={`${modeColor.accentText} text-sm font-medium hidden sm:inline`}>{modeColor.accentLabel}</span>
            </div>
          </button>

          {/* Right side: mode selector + model depth toggle */}
          <div className="flex items-center gap-3">
            {/* Model depth toggle (M&A only) */}
            {modelMode && onModelModeChange && (
              <ModelDepthToggle mode={modelMode} onChange={onModelModeChange} />
            )}

            {/* Mode selector - always visible */}
            <div className="flex gap-0.5 p-0.5 bg-slate-800/60 border border-slate-700/50 rounded-lg">
              {(['ma', 'startup', 'vc'] as const).map(m => (
                <button
                  key={m}
                  onClick={() => onAppModeChange(m)}
                  aria-pressed={appMode === m}
                  className={`
                    py-1.5 px-2.5 rounded-md text-xs font-medium transition-all
                    focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-1 focus-visible:ring-offset-slate-900
                    ${appMode === m
                      ? MODE_ACTIVE_BG[m]
                      : 'text-slate-400 hover:text-slate-200'
                    }
                  `}
                >
                  {m === 'ma' ? 'M&A' : m === 'startup' ? 'Startup' : 'VC'}
                </button>
              ))}
            </div>
          </div>
        </div>
      </header>

      {/* Step indicator */}
      {step != null && !isResults && (
        <div className="border-b border-slate-800 bg-navy-800/40">
          <div className="max-w-6xl mx-auto px-4 sm:px-6 py-3">
            <StepIndicator
              currentStep={step}
              steps={steps}
              appMode={appMode}
            />
          </div>
        </div>
      )}

      {/* Results completion bar */}
      {isResults && (
        <div className="border-b border-slate-800 bg-navy-800/40">
          <div className="max-w-6xl mx-auto px-4 sm:px-6 py-2.5">
            <div className="flex items-center gap-2 text-xs">
              {steps.map((s, i) => (
                <React.Fragment key={i}>
                  <span className={`${modeColor.accentText} flex items-center gap-1`}>
                    <span className="opacity-60">&#10003;</span>
                    <span className="hidden sm:inline text-slate-500">{s.short}</span>
                  </span>
                  {i < totalSteps - 1 && <span className={`w-4 h-px ${modeColor.accentText.replace('text-', 'bg-')} opacity-30`} />}
                </React.Fragment>
              ))}
              <span className="ml-2 text-slate-500">&middot;</span>
              <span className={`${modeColor.accentText} font-medium`}>Results</span>
            </div>
          </div>
        </div>
      )}

      {/* Main content */}
      <main className="max-w-6xl mx-auto px-4 sm:px-6 py-8">
        {children}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-800 mt-20 py-6">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 flex items-center justify-between text-2xs text-slate-500">
          <div className="flex items-center gap-3">
            <span className="text-slate-400 font-medium">Dealflow Engine</span>
            <span className="hidden sm:inline">Institutional-grade deal intelligence</span>
          </div>
          <div className="flex items-center gap-4">
            <a
              href="https://github.com/bdavis37-tal/dealflow-engine"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-slate-300 transition-colors"
            >
              GitHub
            </a>
            <span className="text-slate-700">&middot;</span>
            <span>BSL 1.1</span>
          </div>
        </div>
      </footer>
    </div>
  )
}
