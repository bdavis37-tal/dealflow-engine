import type { SourcesAndUses } from '../../types/deal'
import { formatCurrencyCompact } from '../../lib/formatters'

interface SourcesAndUsesTableProps {
  data: SourcesAndUses
  /** Opening balance-sheet balancing plug ($M) — disclosed as a footnote when non-zero */
  balancingPlug?: number
}

export default function SourcesAndUsesTable({ data, balancingPlug = 0 }: SourcesAndUsesTableProps) {
  return (
    <div>
      <h2 className="text-lg font-semibold text-slate-100 mb-4">Sources & Uses of Funds</h2>
      <div className="grid grid-cols-2 gap-4">
        {/* Sources */}
        <div className="rounded-xl border border-slate-700 bg-slate-800/20 overflow-hidden">
          <div className="px-4 py-2.5 bg-slate-800/40 border-b border-slate-700">
            <h3 className="text-xs font-semibold text-slate-300 uppercase tracking-wide">Sources</h3>
          </div>
          <div className="divide-y divide-slate-800/50">
            {data.sources.map((item, i) => (
              <div key={i} className="flex items-center justify-between px-4 py-2.5">
                <span className="text-sm text-slate-400">{item.label}</span>
                <span className="text-sm text-slate-200 tabular-nums font-medium">
                  {formatCurrencyCompact(item.amount)}
                </span>
              </div>
            ))}
          </div>
          <div className="flex items-center justify-between px-4 py-3 bg-slate-800/30 border-t border-slate-700">
            <span className="text-sm font-semibold text-slate-200">Total Sources</span>
            <span className="text-sm font-bold text-slate-100 tabular-nums">
              {formatCurrencyCompact(data.total_sources)}
            </span>
          </div>
        </div>

        {/* Uses */}
        <div className="rounded-xl border border-slate-700 bg-slate-800/20 overflow-hidden">
          <div className="px-4 py-2.5 bg-slate-800/40 border-b border-slate-700">
            <h3 className="text-xs font-semibold text-slate-300 uppercase tracking-wide">Uses</h3>
          </div>
          <div className="divide-y divide-slate-800/50">
            {data.uses.map((item, i) => (
              <div key={i} className="flex items-center justify-between px-4 py-2.5">
                <span className="text-sm text-slate-400">{item.label}</span>
                <span className="text-sm text-slate-200 tabular-nums font-medium">
                  {formatCurrencyCompact(item.amount)}
                </span>
              </div>
            ))}
          </div>
          <div className="flex items-center justify-between px-4 py-3 bg-slate-800/30 border-t border-slate-700">
            <span className="text-sm font-semibold text-slate-200">Total Uses</span>
            <span className="text-sm font-bold text-slate-100 tabular-nums">
              {formatCurrencyCompact(data.total_uses)}
            </span>
          </div>
        </div>
      </div>

      {/* Balance check */}
      {!data.balanced && (
        <div className="mt-2 text-xs text-amber-400">
          Sources and Uses do not balance — check deal structure assumptions.
        </div>
      )}

      {/* Opening balance-sheet plug disclosure */}
      {Math.abs(balancingPlug) > 0.005 && (
        <p className="mt-2 text-2xs text-slate-500">
          Opening balance sheet includes a {formatCurrencyCompact(balancingPlug)} balancing
          plug so Assets = Liabilities + Equity (see model notes).
        </p>
      )}
    </div>
  )
}
