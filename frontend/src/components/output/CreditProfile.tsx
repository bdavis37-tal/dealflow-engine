import type { CreditMetrics } from '../../types/deal'
import { formatMultiple, formatPercentage } from '../../lib/formatters'

interface CreditProfileProps {
  metrics: CreditMetrics
}

interface CreditRow {
  label: string
  value: number
  formatted: string
  greenRange: string
  yellowRange: string
  redRange: string
  health: 'good' | 'fair' | 'poor'
}

function getHealth(value: number, greenMin: number, yellowMin: number, higherIsBetter: boolean): 'good' | 'fair' | 'poor' {
  if (higherIsBetter) {
    if (value >= greenMin) return 'good'
    if (value >= yellowMin) return 'fair'
    return 'poor'
  }
  if (value <= greenMin) return 'good'
  if (value <= yellowMin) return 'fair'
  return 'poor'
}

const HEALTH_COLORS = {
  good: 'text-green-400',
  fair: 'text-amber-400',
  poor: 'text-red-400',
}

const HEALTH_DOT = {
  good: 'bg-green-500',
  fair: 'bg-amber-500',
  poor: 'bg-red-500',
}

export default function CreditProfile({ metrics }: CreditProfileProps) {
  const rows: CreditRow[] = [
    {
      label: 'Total Debt / EBITDA',
      value: metrics.total_debt_to_ebitda,
      formatted: formatMultiple(metrics.total_debt_to_ebitda),
      greenRange: '< 3.0×',
      yellowRange: '3.0–5.0×',
      redRange: '> 5.0×',
      health: getHealth(metrics.total_debt_to_ebitda, 3.0, 5.0, false),
    },
    {
      label: 'Net Debt / EBITDA',
      value: metrics.net_debt_to_ebitda,
      formatted: formatMultiple(metrics.net_debt_to_ebitda),
      greenRange: '< 2.5×',
      yellowRange: '2.5–4.5×',
      redRange: '> 4.5×',
      health: getHealth(metrics.net_debt_to_ebitda, 2.5, 4.5, false),
    },
    {
      label: 'Interest Coverage (EBITDA / Interest)',
      value: metrics.interest_coverage,
      formatted: metrics.interest_coverage >= 99 ? 'N/A' : formatMultiple(metrics.interest_coverage),
      greenRange: '> 3.0×',
      yellowRange: '2.0–3.0×',
      redRange: '< 2.0×',
      health: metrics.interest_coverage >= 99 ? 'good' : getHealth(metrics.interest_coverage, 3.0, 2.0, true),
    },
    {
      label: 'Fixed Charge Coverage',
      value: metrics.fixed_charge_coverage,
      formatted: metrics.fixed_charge_coverage >= 99 ? 'N/A' : formatMultiple(metrics.fixed_charge_coverage),
      greenRange: '> 1.5×',
      yellowRange: '1.0–1.5×',
      redRange: '< 1.0×',
      health: metrics.fixed_charge_coverage >= 99 ? 'good' : getHealth(metrics.fixed_charge_coverage, 1.5, 1.0, true),
    },
    {
      label: 'Debt / Total Capitalization',
      value: metrics.debt_to_total_cap * 100,
      formatted: formatPercentage(metrics.debt_to_total_cap * 100),
      greenRange: '< 40%',
      yellowRange: '40–60%',
      redRange: '> 60%',
      health: getHealth(metrics.debt_to_total_cap, 0.40, 0.60, false),
    },
  ]

  return (
    <div>
      <h2 className="text-lg font-semibold text-slate-100 mb-4">Credit Profile</h2>
      <div className="rounded-xl border border-slate-700 bg-slate-800/20 overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-slate-700 bg-slate-800/40">
              <th className="py-2.5 pl-4 pr-2 text-left text-xs font-semibold text-slate-400">Metric</th>
              <th className="py-2.5 px-3 text-right text-xs font-semibold text-slate-400">Value</th>
              <th className="py-2.5 px-3 text-center text-xs font-semibold text-green-500/80">Healthy</th>
              <th className="py-2.5 px-3 text-center text-xs font-semibold text-amber-500/80">Watch</th>
              <th className="py-2.5 px-3 text-center text-xs font-semibold text-red-500/80">Concern</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.label} className="border-b border-slate-800/50 hover:bg-slate-800/10">
                <td className="py-2.5 pl-4 pr-2 text-sm text-slate-300">
                  <div className="flex items-center gap-2">
                    <div className={`w-2 h-2 rounded-full flex-shrink-0 ${HEALTH_DOT[row.health]}`} />
                    {row.label}
                  </div>
                </td>
                <td className={`py-2.5 px-3 text-right text-sm font-semibold tabular-nums ${HEALTH_COLORS[row.health]}`}>
                  {row.formatted}
                </td>
                <td className="py-2.5 px-3 text-center text-xs text-slate-500">{row.greenRange}</td>
                <td className="py-2.5 px-3 text-center text-xs text-slate-500">{row.yellowRange}</td>
                <td className="py-2.5 px-3 text-center text-xs text-slate-500">{row.redRange}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
