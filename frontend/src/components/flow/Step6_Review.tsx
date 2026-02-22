import React from 'react'
import { ArrowLeft, Loader2, TrendingUp } from 'lucide-react'
import type { DealState } from '../../types/deal'
import { formatCurrencyCompact, formatPercentage, formatMultiple } from '../../lib/formatters'

interface Step6Props {
  state: DealState
  onBack: () => void
  onRun: () => void
}

function AssumptionCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-slate-800/30 border border-slate-700/50 rounded-lg px-4 py-3">
      <div className="text-xs text-slate-500 mb-0.5">{label}</div>
      <div className="text-sm font-medium text-slate-200 tabular-nums">{value}</div>
    </div>
  )
}

export default function Step6_Review({ state, onBack, onRun }: Step6Props) {
  const { acquirer, target, structure, synergies, isLoading, loadingMessage, error } = state

  const totalSynergies = [
    ...synergies.cost_synergies,
    ...synergies.revenue_synergies,
  ].reduce((sum, s) => sum + s.annual_amount, 0)

  const dealSize = target.acquisition_price ?? 0
  const entryMultipleEst = target.ebitda && target.ebitda > 0
    ? (dealSize / target.ebitda).toFixed(1) + '×'
    : '—'

  if (isLoading) {
    return (
      <div className="max-w-2xl mx-auto animate-fade-in">
        <div className="flex flex-col items-center justify-center py-24 text-center space-y-6">
          <div className="relative">
            <div className="w-16 h-16 rounded-2xl bg-blue-600/20 border border-blue-500/30 flex items-center justify-center">
              <TrendingUp size={28} className="text-blue-400" />
            </div>
            <Loader2 size={20} className="absolute -top-2 -right-2 text-blue-400 animate-spin" />
          </div>
          <div>
            <h2 className="text-xl font-semibold text-slate-100 mb-2">Modeling your deal...</h2>
            <p className="text-slate-400 text-sm animate-pulse-slow">{loadingMessage}</p>
          </div>
          <div className="w-48 h-1 bg-slate-800 rounded-full overflow-hidden">
            <div className="h-full bg-blue-500 rounded-full animate-pulse w-2/3" />
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-2xl mx-auto animate-slide-up">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-100 mb-2">Review your assumptions</h1>
        <p className="text-slate-400">Double-check your inputs before we run the analysis.</p>
      </div>

      {error && (
        <div className="mb-6 rounded-xl border border-red-500/40 bg-red-950/20 px-5 py-4 text-sm text-red-300">
          <strong>Analysis error:</strong> {error}
        </div>
      )}

      <div className="space-y-6">
        {/* Deal Overview */}
        <div>
          <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Deal Overview</h3>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            <AssumptionCard label="Buyer" value={acquirer.company_name || '—'} />
            <AssumptionCard label="Target" value={target.company_name || '—'} />
            <AssumptionCard label="Deal Size" value={formatCurrencyCompact(dealSize)} />
            <AssumptionCard label="Implied Multiple" value={entryMultipleEst} />
            <AssumptionCard label="Buyer Revenue" value={formatCurrencyCompact(acquirer.revenue ?? 0)} />
            <AssumptionCard label="Target Revenue" value={formatCurrencyCompact(target.revenue ?? 0)} />
          </div>
        </div>

        {/* Financing */}
        <div>
          <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Deal Financing</h3>
          <div className="grid grid-cols-3 gap-3">
            <AssumptionCard label="Cash" value={formatPercentage((structure.cash_percentage ?? 0) * 100)} />
            <AssumptionCard label="Stock" value={formatPercentage((structure.stock_percentage ?? 0) * 100)} />
            <AssumptionCard label="Debt" value={formatPercentage((structure.debt_percentage ?? 0) * 100)} />
          </div>
          {(structure.debt_tranches?.length ?? 0) > 0 && (
            <div className="mt-2 text-xs text-slate-500">
              {structure.debt_tranches?.length} debt tranche(s) configured
            </div>
          )}
        </div>

        {/* Synergies */}
        <div>
          <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Expected Benefits</h3>
          {totalSynergies > 0 ? (
            <div className="grid grid-cols-2 gap-3">
              <AssumptionCard label="Annual Cost Savings" value={formatCurrencyCompact(synergies.cost_synergies.reduce((s, i) => s + i.annual_amount, 0))} />
              <AssumptionCard label="Annual Revenue Synergies" value={formatCurrencyCompact(synergies.revenue_synergies.reduce((s, i) => s + i.annual_amount, 0))} />
            </div>
          ) : (
            <div className="rounded-lg bg-slate-800/30 border border-slate-700/50 px-4 py-3 text-sm text-slate-500">
              No synergies — modeling a standalone acquisition.
            </div>
          )}
        </div>
      </div>

      {/* Run button */}
      <div className="mt-10">
        <button
          onClick={onRun}
          disabled={isLoading}
          className="
            w-full flex items-center justify-center gap-3 px-6 py-5 rounded-xl
            bg-gradient-to-r from-blue-600 to-blue-500 hover:from-blue-500 hover:to-blue-400
            text-white font-bold text-lg transition-all shadow-xl shadow-blue-900/30
            disabled:opacity-60 disabled:cursor-not-allowed
          "
        >
          <TrendingUp size={22} />
          Generate Analysis
        </button>
        <p className="text-center text-xs text-slate-500 mt-3">
          Runs 500+ scenarios and produces an institutional-grade deal brief.
        </p>
      </div>

      <div className="mt-4">
        <button onClick={onBack} className="w-full flex items-center justify-center gap-2 text-slate-500 hover:text-slate-300 text-sm py-2 transition-colors">
          <ArrowLeft size={14} /> Edit inputs
        </button>
      </div>
    </div>
  )
}
