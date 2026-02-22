/**
 * Step 5: Review inputs, trigger valuation, show loading state.
 */
import React from 'react'
import { ArrowLeft, Loader2, Zap } from 'lucide-react'
import type { StartupState } from '../../../types/startup'
import { VERTICAL_LABELS, STAGE_LABELS } from '../../../types/startup'

interface Step5Props {
  state: StartupState
  onBack: () => void
  onRun: () => void
}

export default function StartupStep5_Review({ state, onBack, onRun }: Step5Props) {
  const { isLoading, error, company_name, fundraise, traction, team } = state
  const arr = traction.annual_recurring_revenue || (traction.monthly_recurring_revenue || 0) * 12

  if (isLoading) {
    return (
      <div className="max-w-xl mx-auto text-center py-20 animate-fade-in">
        <div className="w-16 h-16 rounded-full bg-purple-900/40 border border-purple-700 flex items-center justify-center mx-auto mb-6">
          <Loader2 size={28} className="text-purple-400 animate-spin" />
        </div>
        <h2 className="text-xl font-bold text-slate-100 mb-2">Running your valuation...</h2>
        <p className="text-slate-400 text-sm">
          Applying Berkus, Scorecard, Risk Factor Summation, and ARR multiple methods against
          live benchmarks from Carta, PitchBook, and Equidam.
        </p>
        <div className="mt-6 space-y-2 text-xs text-slate-500">
          <p>Calibrating against {VERTICAL_LABELS[fundraise.vertical ?? 'b2b_saas']} benchmarks...</p>
          <p>Building dilution model across rounds...</p>
          <p>Generating investor scorecard...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-2xl mx-auto animate-slide-up">
      <div className="mb-8">
        <h2 className="text-2xl font-bold text-slate-100 mb-2">Ready to value {company_name || 'your startup'}?</h2>
        <p className="text-slate-400">
          Review your inputs below, then run the engine to get your institutional-grade valuation range.
        </p>
      </div>

      {error && (
        <div className="mb-6 p-4 rounded-xl border border-red-700 bg-red-900/20 text-red-300 text-sm">
          {error}
        </div>
      )}

      <div className="space-y-4 mb-8">
        {/* Deal summary */}
        <div className="rounded-xl border border-slate-700 bg-slate-800/30 p-5">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">Round Summary</p>
          <div className="grid grid-cols-2 gap-y-3 text-sm">
            <div>
              <p className="text-slate-500">Company</p>
              <p className="text-slate-200 font-medium">{company_name || '—'}</p>
            </div>
            <div>
              <p className="text-slate-500">Stage</p>
              <p className="text-slate-200 font-medium">{STAGE_LABELS[fundraise.stage ?? 'pre_seed']}</p>
            </div>
            <div>
              <p className="text-slate-500">Vertical</p>
              <p className="text-slate-200 font-medium">{VERTICAL_LABELS[fundraise.vertical ?? 'b2b_saas']}</p>
            </div>
            <div>
              <p className="text-slate-500">Raise Amount</p>
              <p className="text-slate-200 font-medium">${fundraise.raise_amount?.toFixed(1) ?? '—'}M</p>
            </div>
            <div>
              <p className="text-slate-500">Instrument</p>
              <p className="text-slate-200 font-medium capitalize">{fundraise.instrument?.replace('_', ' ') ?? '—'}</p>
            </div>
            <div>
              <p className="text-slate-500">Geography</p>
              <p className="text-slate-200 font-medium capitalize">{fundraise.geography?.replace('_', ' ') ?? '—'}</p>
            </div>
          </div>
        </div>

        {/* Team + traction */}
        <div className="grid grid-cols-2 gap-4">
          <div className="rounded-xl border border-slate-700 bg-slate-800/30 p-5">
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">Team</p>
            <div className="space-y-1.5 text-sm">
              <div className="flex justify-between">
                <span className="text-slate-500">Co-founders</span>
                <span className="text-slate-300">{team.founder_count}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Prior exits</span>
                <span className="text-slate-300">{team.prior_exits}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Technical co-founder</span>
                <span className={team.technical_cofounder ? 'text-green-400' : 'text-red-400'}>
                  {team.technical_cofounder ? 'Yes' : 'No'}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Domain expert</span>
                <span className={team.domain_experts ? 'text-green-400' : 'text-slate-400'}>
                  {team.domain_experts ? 'Yes' : 'No'}
                </span>
              </div>
            </div>
          </div>

          <div className="rounded-xl border border-slate-700 bg-slate-800/30 p-5">
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">Traction</p>
            <div className="space-y-1.5 text-sm">
              <div className="flex justify-between">
                <span className="text-slate-500">ARR</span>
                <span className="text-slate-300">{arr > 0 ? `$${arr.toFixed(2)}M` : 'Pre-revenue'}</span>
              </div>
              {arr > 0 && (
                <>
                  <div className="flex justify-between">
                    <span className="text-slate-500">NRR</span>
                    <span className="text-slate-300">{((traction.net_revenue_retention ?? 1) * 100).toFixed(0)}%</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">MoM growth</span>
                    <span className="text-slate-300">{((traction.mom_growth_rate ?? 0) * 100).toFixed(0)}%</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Customers</span>
                    <span className="text-slate-300">{traction.paying_customer_count}</span>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      </div>

      <div className="flex gap-3">
        <button
          onClick={onBack}
          className="px-6 py-4 rounded-xl border border-slate-600 text-slate-300 hover:border-slate-500 transition-all flex items-center gap-2"
        >
          <ArrowLeft size={16} /> Back
        </button>
        <button
          onClick={onRun}
          className="flex-1 flex items-center justify-center gap-2 px-6 py-4 rounded-xl bg-purple-600 hover:bg-purple-500 text-white font-semibold text-base transition-all shadow-lg shadow-purple-900/30"
        >
          <Zap size={18} />
          Run Valuation — 4 Methods, Live Benchmarks
        </button>
      </div>
    </div>
  )
}
