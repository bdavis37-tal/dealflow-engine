import React from 'react'
import StepIndicator from './StepIndicator'
import ModeToggle from './ModeToggle'
import type { FlowStep, ModelMode } from '../../types/deal'

interface AppShellProps {
  children: React.ReactNode
  step: FlowStep
  mode: ModelMode
  onModeChange: (mode: ModelMode) => void
  showNav?: boolean
}

export default function AppShell({ children, step, mode, onModeChange, showNav = true }: AppShellProps) {
  return (
    <div className="min-h-screen bg-navy-900 text-slate-100 font-sans">
      {/* Header */}
      <header className="border-b border-slate-800 bg-navy-800/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-blue-500 to-blue-700 flex items-center justify-center">
              <span className="text-white text-xs font-bold">DE</span>
            </div>
            <span className="font-semibold text-slate-100 text-sm">Dealflow Engine</span>
          </div>

          {showNav && (
            <ModeToggle mode={mode} onChange={onModeChange} />
          )}
        </div>
      </header>

      {/* Step indicator */}
      {showNav && step < 6 && (
        <div className="border-b border-slate-800 bg-navy-800/40">
          <div className="max-w-6xl mx-auto px-4 sm:px-6 py-3">
            <StepIndicator currentStep={step} />
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
          <span>Dealflow Engine — MIT License — Open Source</span>
          <a
            href="https://github.com/bdavis37-tal/dealflow-engine"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-slate-300 transition-colors"
          >
            GitHub →
          </a>
        </div>
      </footer>
    </div>
  )
}
