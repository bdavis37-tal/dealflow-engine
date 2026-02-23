import { Shield, FileText, Lock, Server } from 'lucide-react'
import type { DefensePositioning } from '../../types/deal'

interface DefensePositioningCardProps {
  positioning: DefensePositioning
}

function formatCurrency(value: number): string {
  const abs = Math.abs(value)
  const sign = value < 0 ? '-' : ''
  if (abs >= 1_000_000_000) return `${sign}$${(abs / 1_000_000_000).toFixed(1)}B`
  if (abs >= 1_000_000) return `${sign}$${(abs / 1_000_000).toFixed(1)}M`
  if (abs >= 1_000) return `${sign}$${(abs / 1_000).toFixed(0)}K`
  return `${sign}$${abs.toFixed(0)}`
}

export default function DefensePositioningCard({ positioning: p }: DefensePositioningCardProps) {
  return (
    <div className="rounded-xl border border-emerald-800/40 bg-emerald-950/10 p-6 space-y-5 animate-fade-in">
      <div className="flex items-center gap-2">
        <Shield size={18} className="text-emerald-400" />
        <h2 className="text-lg font-semibold text-emerald-300">Defense Positioning</h2>
        {p.is_ai_native && (
          <span className="text-2xs text-purple-400 border border-purple-800/30 rounded-full px-2 py-0.5 ml-2">
            AI-Native
          </span>
        )}
      </div>

      {/* Summary */}
      <p className="text-sm text-slate-300 leading-relaxed">{p.positioning_summary}</p>

      {/* Key metrics grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="rounded-lg border border-slate-700 bg-slate-800/30 p-3">
          <div className="flex items-center gap-1.5 text-xs text-slate-500 mb-1">
            <Lock size={12} />
            Clearance
          </div>
          <div className="text-sm font-semibold text-slate-100">{p.clearance_level}</div>
        </div>

        <div className="rounded-lg border border-slate-700 bg-slate-800/30 p-3">
          <div className="flex items-center gap-1.5 text-xs text-slate-500 mb-1">
            <FileText size={12} />
            Backlog
          </div>
          <div className="text-sm font-semibold text-slate-100">{formatCurrency(p.combined_backlog)}</div>
          <div className="text-2xs text-slate-500">{p.backlog_coverage_ratio.toFixed(1)}× revenue</div>
        </div>

        <div className="rounded-lg border border-slate-700 bg-slate-800/30 p-3">
          <div className="flex items-center gap-1.5 text-xs text-slate-500 mb-1">
            <Server size={12} />
            Contract Vehicles
          </div>
          <div className="text-sm font-semibold text-slate-100">{p.active_contract_vehicles}</div>
        </div>

        <div className="rounded-lg border border-slate-700 bg-slate-800/30 p-3">
          <div className="text-xs text-slate-500 mb-1">Revenue Visibility</div>
          <div className="text-sm font-semibold text-slate-100">{p.revenue_visibility_years.toFixed(1)} years</div>
          <div className="text-2xs text-slate-500">from funded backlog</div>
        </div>
      </div>

      {/* Premium breakdown */}
      {p.total_defense_premium_pct > 0 && (
        <div className="rounded-lg border border-slate-700/50 bg-slate-800/20 p-4">
          <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Valuation Premium Breakdown</h4>
          <div className="space-y-2">
            {p.clearance_premium_applied > 0 && (
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-400">Clearance premium ({p.clearance_level})</span>
                <span className="text-emerald-400 font-medium">+{(p.clearance_premium_applied * 100).toFixed(0)}%</span>
              </div>
            )}
            {p.certification_premium_applied > 0 && (
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-400">Authorization & certification premium</span>
                <span className="text-emerald-400 font-medium">+{(p.certification_premium_applied * 100).toFixed(0)}%</span>
              </div>
            )}
            {p.program_of_record_premium_applied > 0 && (
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-400">Program of record premium ({p.programs_of_record} POR{p.programs_of_record !== 1 ? 's' : ''})</span>
                <span className="text-emerald-400 font-medium">+{(p.program_of_record_premium_applied * 100).toFixed(0)}%</span>
              </div>
            )}
            <div className="flex items-center justify-between text-xs border-t border-slate-700/50 pt-2 mt-2">
              <span className="text-slate-300 font-medium">Total defense premium</span>
              <span className="text-emerald-300 font-semibold">+{(p.total_defense_premium_pct * 100).toFixed(0)}%</span>
            </div>
          </div>
        </div>
      )}

      {/* EV/Revenue context */}
      <div className="text-xs text-slate-500">
        Implied EV/Revenue: <span className="text-slate-300 font-medium">{p.ev_revenue_multiple.toFixed(1)}×</span>
        {p.is_ai_native
          ? ' — comparable to AI-native defense platforms (Palantir 18×, Anduril 22×, Shield AI 15×)'
          : ' — comparable to traditional defense IT (Booz Allen 3.5×, Leidos 1.8×, SAIC 1.2×)'}
      </div>
    </div>
  )
}
