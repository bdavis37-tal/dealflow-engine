import React from 'react'

interface LandingPageProps {
  onSelectMode: (mode: 'ma' | 'startup' | 'vc') => void
  onSkip: () => void
}

const MODE_CARDS = [
  {
    mode: 'ma' as const,
    title: 'M&A Deal Modeling',
    emoji: '🏦',
    description:
      'Full merger model with pro forma statements, accretion/dilution, sensitivity analysis, and deal verdicts.',
    borderColor: 'border-blue-500/50',
    hoverBorder: 'hover:border-blue-400',
    accentBar: 'from-blue-500 to-blue-600',
    accentText: 'text-blue-400',
  },
  {
    mode: 'startup' as const,
    title: 'Startup Valuation',
    emoji: '🚀',
    description:
      'Four-method valuation engine for pre-seed through Series A, calibrated against market data.',
    borderColor: 'border-purple-500/50',
    hoverBorder: 'hover:border-purple-400',
    accentBar: 'from-purple-500 to-purple-600',
    accentText: 'text-purple-400',
  },
  {
    mode: 'vc' as const,
    title: 'VC Seat Analysis',
    emoji: '💼',
    description:
      "Evaluate deals from the investor's chair — ownership math, fund returners, waterfall analysis, and IC memos.",
    borderColor: 'border-emerald-500/50',
    hoverBorder: 'hover:border-emerald-400',
    accentBar: 'from-emerald-500 to-emerald-600',
    accentText: 'text-emerald-400',
  },
] as const

export default function LandingPage({ onSelectMode, onSkip }: LandingPageProps) {
  const handleCardKeyDown = (
    e: React.KeyboardEvent,
    mode: 'ma' | 'startup' | 'vc',
  ) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      onSelectMode(mode)
    }
  }

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100 font-sans flex flex-col">
      {/* Header */}
      <header className="border-b border-slate-800 bg-slate-800/80 backdrop-blur-sm">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 h-14 flex items-center">
          <div className="flex items-center gap-3">
            <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
              <span className="text-white text-xs font-bold">DE</span>
            </div>
            <span className="font-semibold text-slate-100 text-sm">
              Dealflow Engine
            </span>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="flex-1 flex flex-col items-center justify-center px-4 sm:px-6">
        <div className="max-w-4xl mx-auto text-center pt-20 pb-12">
          <h1 className="text-4xl sm:text-5xl font-bold tracking-tight mb-4">
            Dealflow Engine
          </h1>
          <p className="text-lg sm:text-xl text-slate-400 font-medium mb-3">
            Institutional-grade deal intelligence
          </p>
          <p className="text-sm sm:text-base text-slate-500 max-w-2xl mx-auto leading-relaxed">
            Model M&amp;A deals, value startups, and analyze VC investments — all
            in one platform. Deterministic engines you can trust, augmented by AI.
          </p>
        </div>

        {/* Mode cards */}
        <div className="max-w-4xl w-full mx-auto grid grid-cols-1 md:grid-cols-3 gap-6 pb-10">
          {MODE_CARDS.map((card) => (
            <div
              key={card.mode}
              role="button"
              tabIndex={0}
              onClick={() => onSelectMode(card.mode)}
              onKeyDown={(e) => handleCardKeyDown(e, card.mode)}
              className={`
                bg-slate-800/50 border ${card.borderColor} rounded-xl p-6
                cursor-pointer transition-all
                ${card.hoverBorder} hover:bg-slate-800/80 hover:scale-[1.02]
                focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900
                relative overflow-hidden
              `}
            >
              {/* Accent bar */}
              <div
                className={`absolute top-0 left-0 right-0 h-1 bg-gradient-to-r ${card.accentBar}`}
              />
              <div className="text-2xl mb-3">{card.emoji}</div>
              <h2 className={`text-lg font-semibold mb-2 ${card.accentText}`}>
                {card.title}
              </h2>
              <p className="text-sm text-slate-400 leading-relaxed">
                {card.description}
              </p>
            </div>
          ))}
        </div>

        {/* Skip button */}
        <button
          onClick={onSkip}
          className="text-sm text-slate-500 hover:text-slate-300 transition-colors mt-4 mb-16"
        >
          Skip to analysis →
        </button>
      </section>

      {/* Footer */}
      <footer className="border-t border-slate-800 mt-20 py-6">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 flex items-center justify-between text-2xs text-slate-500">
          <div className="flex items-center gap-3">
            <span className="text-slate-400 font-medium">Dealflow Engine</span>
            <span className="hidden sm:inline">
              Institutional-grade deal intelligence
            </span>
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
