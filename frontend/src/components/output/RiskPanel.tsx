import type { RiskItem, RiskSeverity } from '../../types/deal'

interface RiskPanelProps {
  risks: RiskItem[]
}

const SEVERITY_STYLES: Record<RiskSeverity, { badge: string; border: string; bg: string }> = {
  critical: { badge: 'bg-red-600 text-white', border: 'border-red-700/50', bg: 'bg-red-950/20' },
  high:     { badge: 'bg-orange-600 text-white', border: 'border-orange-700/50', bg: 'bg-orange-950/15' },
  medium:   { badge: 'bg-amber-600 text-white', border: 'border-amber-700/50', bg: 'bg-amber-950/15' },
  low:      { badge: 'bg-slate-600 text-white', border: 'border-slate-700/50', bg: 'bg-slate-800/20' },
}

function RiskCard({ risk }: { risk: RiskItem }) {
  const styles = SEVERITY_STYLES[risk.severity]

  return (
    <div className={`rounded-xl border p-5 ${styles.border} ${styles.bg}`}>
      <div className="flex items-start justify-between gap-3 mb-3">
        <div>
          <span className={`inline-block px-2.5 py-0.5 rounded-full text-2xs font-bold uppercase tracking-wide ${styles.badge} mb-2`}>
            {risk.severity}
          </span>
          <h3 className="text-sm font-semibold text-slate-200">{risk.metric_name}</h3>
        </div>
        <div className="text-right text-xs text-slate-400 tabular-nums flex-shrink-0">
          <div className="text-slate-300 font-semibold">{risk.current_value.toFixed(1)}</div>
          <div className="text-slate-500">vs {risk.threshold_value.toFixed(1)} threshold</div>
        </div>
      </div>

      <p className="text-sm text-slate-400 leading-relaxed mb-3">{risk.plain_english}</p>

      <div className="text-xs text-slate-500 bg-slate-900/40 rounded-lg px-3 py-2 border border-slate-700/30">
        <span className="text-slate-400 font-medium">Tolerance: </span>
        {risk.tolerance_band}
      </div>
    </div>
  )
}

export default function RiskPanel({ risks }: RiskPanelProps) {
  if (risks.length === 0) {
    return (
      <div>
        <h2 className="text-lg font-semibold text-slate-100 mb-4">Risk Assessment</h2>
        <div className="rounded-xl border border-green-800/30 bg-green-950/10 px-5 py-4 text-sm text-green-400">
          ✓ No significant risk flags identified for this deal structure.
        </div>
      </div>
    )
  }

  return (
    <div>
      <h2 className="text-lg font-semibold text-slate-100 mb-4">
        Risk Assessment
        <span className="ml-2 text-sm font-normal text-slate-500">
          {risks.length} flag{risks.length !== 1 ? 's' : ''} identified
        </span>
      </h2>
      <div className="space-y-4">
        {risks.map((risk, idx) => (
          <RiskCard key={idx} risk={risk} />
        ))}
      </div>
    </div>
  )
}
