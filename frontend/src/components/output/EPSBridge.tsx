/**
 * Year 1 accretion/dilution bridge — walks standalone EPS to pro forma EPS
 * through the deal's per-share effects. All values are per-share dollars,
 * after-tax, reconciled by the engine to the income-statement EPS delta.
 */
import { useState } from 'react'
import type { AccretionDilutionBridge } from '../../types/deal'
import { formatEPSChange, formatPercentage } from '../../lib/formatters'

interface EPSBridgeProps {
  bridge: AccretionDilutionBridge[]
  /** Year-1 accretion % is Not Meaningful (standalone EPS <= 0) */
  isNm?: boolean
}

interface BridgeRow {
  label: string
  value: number
}

export default function EPSBridge({ bridge, isNm = false }: EPSBridgeProps) {
  const [yearIdx, setYearIdx] = useState(0)
  const yr = bridge[yearIdx]
  if (!yr) return null

  const rows: BridgeRow[] = [
    { label: 'Target earnings contribution', value: yr.target_earnings_contribution },
    { label: 'New debt interest (after-tax)', value: yr.interest_expense_drag },
    { label: 'Foregone interest on cash', value: yr.foregone_interest_drag },
    { label: 'Incremental D&A (PPA)', value: yr.da_adjustment },
    { label: 'Synergies (net, after-tax)', value: yr.synergy_benefit },
    { label: 'Share dilution', value: yr.share_dilution_impact },
    { label: 'Taxes & other reconciling', value: yr.tax_impact },
  ].filter(r => Math.abs(r.value) > 0.0005)

  const maxAbs = Math.max(...rows.map(r => Math.abs(r.value)), Math.abs(yr.total_accretion_dilution), 0.01)

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-slate-100">EPS Bridge</h2>
        <div className="flex gap-1">
          {bridge.map((b, i) => (
            <button
              key={b.year}
              onClick={() => setYearIdx(i)}
              className={`px-2.5 py-1 rounded-md text-2xs font-medium transition-colors ${
                i === yearIdx
                  ? 'bg-blue-600 text-white'
                  : 'bg-slate-800 text-slate-500 hover:text-slate-300 border border-slate-700'
              }`}
            >
              Y{b.year}
            </button>
          ))}
        </div>
      </div>

      <div className="rounded-xl border border-slate-700 bg-slate-800/20 divide-y divide-slate-800/50">
        {rows.map(r => (
          <div key={r.label} className="flex items-center gap-3 px-4 py-2">
            <span className="text-xs text-slate-400 w-56 flex-shrink-0">{r.label}</span>
            <div className="flex-1 flex items-center h-4">
              <div
                className={`h-2 rounded-sm ${r.value >= 0 ? 'bg-green-700/70' : 'bg-red-700/70'}`}
                style={{ width: `${Math.max(2, (Math.abs(r.value) / maxAbs) * 100)}%` }}
              />
            </div>
            <span className={`text-xs tabular-nums font-medium w-20 text-right ${r.value >= 0 ? 'text-green-400' : 'text-red-400'}`}>
              {formatEPSChange(r.value)}
            </span>
          </div>
        ))}

        <div className="flex items-center gap-3 px-4 py-2.5 bg-slate-800/30">
          <span className="text-xs font-semibold text-slate-200 w-56 flex-shrink-0">
            Total EPS impact (Year {yr.year})
          </span>
          <span className="flex-1 text-2xs text-slate-500">
            {isNm && yearIdx === 0 ? (
              <span
                className="cursor-help"
                title="Standalone EPS ≤ 0 — percentage not meaningful; verdict driven by EPS delta"
              >
                NM — judge the dollar delta
              </span>
            ) : (
              `${formatPercentage(yr.total_accretion_dilution_pct, 1, true)} vs standalone`
            )}
          </span>
          <span className={`text-xs tabular-nums font-bold w-20 text-right ${yr.total_accretion_dilution >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {formatEPSChange(yr.total_accretion_dilution)}
          </span>
        </div>
      </div>
    </div>
  )
}
