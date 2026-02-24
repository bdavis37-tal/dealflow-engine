import type { ContributionAnalysis } from '../../types/deal'
import { formatCurrencyCompact, formatPercentage } from '../../lib/formatters'

interface ContributionAnalysisTableProps {
  data: ContributionAnalysis
  acquirerName: string
  targetName: string
}

export default function ContributionAnalysisTable({ data, acquirerName, targetName }: ContributionAnalysisTableProps) {
  const ownershipMismatch = data.rows.find(r => r.metric === 'EBITDA')
  const ebitdaContrib = ownershipMismatch?.target_pct ?? 0
  const ownershipTarget = data.implied_ownership_target
  const hasMismatch = ownershipTarget > 0 && Math.abs(ebitdaContrib - ownershipTarget) > 0.05

  return (
    <div>
      <h2 className="text-lg font-semibold text-slate-100 mb-4">Contribution Analysis</h2>
      <div className="rounded-xl border border-slate-700 bg-slate-800/20 overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-slate-700 bg-slate-800/40">
              <th className="py-2.5 pl-4 pr-2 text-left text-xs font-semibold text-slate-400 w-32">Metric</th>
              <th className="py-2.5 px-3 text-right text-xs font-semibold text-slate-400">{acquirerName}</th>
              <th className="py-2.5 px-3 text-right text-xs font-semibold text-slate-400">{targetName}</th>
              <th className="py-2.5 px-3 text-right text-xs font-semibold text-slate-400">% {acquirerName}</th>
              <th className="py-2.5 px-3 text-right text-xs font-semibold text-slate-400">% {targetName}</th>
            </tr>
          </thead>
          <tbody>
            {data.rows.map((row) => (
              <tr key={row.metric} className="border-b border-slate-800/50 hover:bg-slate-800/10">
                <td className="py-2.5 pl-4 pr-2 text-sm text-slate-300 font-medium">{row.metric}</td>
                <td className="py-2.5 px-3 text-right text-sm text-slate-200 tabular-nums">
                  {formatCurrencyCompact(row.acquirer_value)}
                </td>
                <td className="py-2.5 px-3 text-right text-sm text-slate-200 tabular-nums">
                  {formatCurrencyCompact(row.target_value)}
                </td>
                <td className="py-2.5 px-3 text-right text-sm text-blue-300 tabular-nums">
                  {formatPercentage(row.acquirer_pct * 100)}
                </td>
                <td className="py-2.5 px-3 text-right text-sm text-blue-300 tabular-nums">
                  {formatPercentage(row.target_pct * 100)}
                </td>
              </tr>
            ))}
            {/* Implied ownership row */}
            {data.implied_ownership_target > 0 && (
              <tr className="border-t border-slate-700 bg-slate-800/30">
                <td className="py-2.5 pl-4 pr-2 text-sm text-slate-300 font-semibold">
                  Implied Ownership
                </td>
                <td className="py-2.5 px-3 text-right text-sm text-slate-500" colSpan={2}>
                  (from stock consideration)
                </td>
                <td className="py-2.5 px-3 text-right text-sm text-slate-100 font-semibold tabular-nums">
                  {formatPercentage(data.implied_ownership_acquirer * 100)}
                </td>
                <td className="py-2.5 px-3 text-right text-sm text-slate-100 font-semibold tabular-nums">
                  {formatPercentage(data.implied_ownership_target * 100)}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Mismatch warning */}
      {hasMismatch && (
        <div className="mt-3 rounded-lg border border-amber-800/40 bg-amber-950/15 px-4 py-2.5 text-xs text-amber-300">
          {targetName} contributes {formatPercentage(ebitdaContrib * 100)} of combined EBITDA
          but receives {formatPercentage(ownershipTarget * 100)} implied ownership
          {ebitdaContrib < ownershipTarget
            ? ' — the acquirer is giving up more ownership than the target contributes in earnings.'
            : ' — the acquirer retains more ownership relative to the target\'s earnings contribution.'}
        </div>
      )}
    </div>
  )
}
