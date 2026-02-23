/**
 * VCOwnershipPanel — Core ownership math display.
 * Shows: entry %, dilution waterfall, exit %, fund returner thresholds,
 * and a contribution table at various exit values.
 */

import type { OwnershipMath, FundProfile } from '../../types/vc'

interface Props {
  ownership: OwnershipMath
  fund: FundProfile
  checkSize: number
  postMoney: number
  arr: number
}

function fmt(n: number, decimals = 1) {
  return n.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })
}

function pct(n: number) {
  return `${(n * 100).toFixed(1)}%`
}

export default function VCOwnershipPanel({ ownership, fund, checkSize, postMoney: _, arr }: Props) {
  const {
    entry_ownership_pct,
    exit_ownership_pct,
    dilution_stack,
    total_dilution_pct,
    fund_returner_1x_exit,
    fund_returner_3x_exit,
    fund_returner_5x_exit,
    exit_values_tested,
    gross_proceeds_at_exits,
    fund_contribution_at_exits,
    required_arr_multiple_for_1x_fund,
    required_arr_multiple_for_3x_fund,
  } = ownership

  const adequacy = entry_ownership_pct >= fund.target_ownership_pct * 0.9 ? 'strong'
    : entry_ownership_pct >= fund.target_ownership_pct * 0.7 ? 'acceptable'
    : 'thin'

  return (
    <div className="space-y-5">
      {/* Ownership headline */}
      <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-5">
        <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-4">Ownership Math</h3>
        <div className="grid grid-cols-3 gap-4">
          <OwnMetric
            label="Entry Ownership"
            value={pct(entry_ownership_pct)}
            sub={`${pct(fund.target_ownership_pct)} target`}
            highlight={adequacy === 'strong' ? 'green' : adequacy === 'acceptable' ? 'yellow' : 'red'}
          />
          <OwnMetric
            label="Exit Ownership"
            value={pct(exit_ownership_pct)}
            sub={`After dilution stack`}
            highlight="neutral"
          />
          <OwnMetric
            label="Total Dilution"
            value={pct(total_dilution_pct)}
            sub={`${dilution_stack.length} rounds modeled`}
            highlight="neutral"
          />
        </div>

        {/* Adequacy badge */}
        <div className={`mt-4 inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium
          ${adequacy === 'strong' ? 'bg-emerald-900/40 text-emerald-400 border border-emerald-700/30'
          : adequacy === 'acceptable' ? 'bg-amber-900/40 text-amber-400 border border-amber-700/30'
          : 'bg-red-900/40 text-red-400 border border-red-700/30'}`
        }>
          <span className={
            adequacy === 'strong' ? 'text-emerald-400'
            : adequacy === 'acceptable' ? 'text-amber-400'
            : 'text-red-400'
          }>
            {adequacy === 'strong' ? '✓' : adequacy === 'acceptable' ? '⚠' : '✗'}
          </span>
          Ownership {adequacy} vs {pct(fund.target_ownership_pct)} target
        </div>
      </div>

      {/* Dilution waterfall table */}
      {dilution_stack.length > 0 && (
        <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-5">
          <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-4">Dilution Stack</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-700">
                  <th className="text-left py-2 text-slate-500 text-xs font-medium">Round</th>
                  <th className="text-right py-2 text-slate-500 text-xs font-medium">Dilution</th>
                  <th className="text-right py-2 text-slate-500 text-xs font-medium">Before</th>
                  <th className="text-right py-2 text-slate-500 text-xs font-medium">After</th>
                </tr>
              </thead>
              <tbody>
                {dilution_stack.map((row, i) => (
                  <tr key={i} className="border-b border-slate-800">
                    <td className="py-2 text-slate-300">{row.round}</td>
                    <td className="py-2 text-right text-red-400">{pct(row.dilution_pct)}</td>
                    <td className="py-2 text-right text-slate-400">{pct(row.ownership_before)}</td>
                    <td className="py-2 text-right text-slate-200">{pct(row.ownership_after)}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr>
                  <td className="py-2 text-slate-300 font-semibold">Exit</td>
                  <td className="py-2 text-right text-red-400 font-semibold">{pct(total_dilution_pct)}</td>
                  <td className="py-2 text-right text-slate-400">{pct(entry_ownership_pct)}</td>
                  <td className="py-2 text-right text-emerald-400 font-semibold">{pct(exit_ownership_pct)}</td>
                </tr>
              </tfoot>
            </table>
          </div>
        </div>
      )}

      {/* Fund Returner Thresholds */}
      <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-5">
        <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-4">
          Fund Returner Thresholds
        </h3>
        <p className="text-xs text-slate-500 mb-4">
          Exit enterprise value needed to return 1x / 3x / 5x the ${fmt(fund.fund_size)}M fund
          from this single position.
        </p>
        <div className="space-y-3">
          {[
            { label: '1x Fund', value: fund_returner_1x_exit, arrMult: required_arr_multiple_for_1x_fund, color: 'emerald' },
            { label: '3x Fund', value: fund_returner_3x_exit, arrMult: required_arr_multiple_for_3x_fund, color: 'amber' },
            { label: '5x Fund', value: fund_returner_5x_exit, arrMult: null, color: 'red' },
          ].map(({ label, value, arrMult, color }) => (
            <div key={label} className={`flex items-center justify-between py-2 px-3 rounded-lg
              ${color === 'emerald' ? 'bg-emerald-950/30 border border-emerald-800/20'
              : color === 'amber' ? 'bg-amber-950/30 border border-amber-800/20'
              : 'bg-red-950/30 border border-red-800/20'}`}
            >
              <span className={`text-sm font-medium
                ${color === 'emerald' ? 'text-emerald-300'
                : color === 'amber' ? 'text-amber-300'
                : 'text-red-300'}`}>
                {label}
              </span>
              <div className="text-right">
                <div className="text-slate-200 font-semibold text-sm">
                  ${value >= 1000 ? `${(value / 1000).toFixed(1)}B` : `${value.toFixed(0)}M`} exit
                </div>
                {arrMult && arr > 0 && (
                  <div className="text-xs text-slate-500">
                    {arrMult.toFixed(0)}x ARR at ${(arr).toFixed(1)}M current ARR
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Contribution Table */}
      <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-5">
        <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-4">
          Proceeds at Exit Scenarios
        </h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-700">
                <th className="text-left py-2 text-slate-500 text-xs font-medium">Exit EV</th>
                <th className="text-right py-2 text-slate-500 text-xs font-medium">Gross Proceeds</th>
                <th className="text-right py-2 text-slate-500 text-xs font-medium">Fund Contribution</th>
                <th className="text-right py-2 text-slate-500 text-xs font-medium">MOIC</th>
              </tr>
            </thead>
            <tbody>
              {exit_values_tested.map((ev, i) => {
                const gp = gross_proceeds_at_exits[i]
                const fc = fund_contribution_at_exits[i]
                const moic = checkSize > 0 ? gp / checkSize : 0
                const isHighlight = fc >= 1.0
                return (
                  <tr key={ev} className={`border-b border-slate-800 ${isHighlight ? 'bg-emerald-950/20' : ''}`}>
                    <td className="py-2 text-slate-300">
                      ${ev >= 1000 ? `${(ev / 1000).toFixed(0)}B` : `${ev.toFixed(0)}M`}
                    </td>
                    <td className="py-2 text-right text-slate-200">
                      ${gp.toFixed(1)}M
                    </td>
                    <td className={`py-2 text-right font-medium ${fc >= 1.0 ? 'text-emerald-400' : fc >= 0.5 ? 'text-amber-400' : 'text-slate-400'}`}>
                      {fc.toFixed(2)}x fund
                    </td>
                    <td className="py-2 text-right text-slate-300">
                      {moic.toFixed(1)}x
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
        <p className="mt-2 text-xs text-slate-600">
          Proceeds = exit EV × {pct(exit_ownership_pct)} exit ownership. Fund contribution = proceeds / ${fmt(fund.fund_size)}M fund.
        </p>
      </div>
    </div>
  )
}

function OwnMetric({
  label,
  value,
  sub,
  highlight,
}: {
  label: string
  value: string
  sub: string
  highlight: 'green' | 'yellow' | 'red' | 'neutral'
}) {
  const colors = {
    green: 'text-emerald-400',
    yellow: 'text-amber-400',
    red: 'text-red-400',
    neutral: 'text-slate-200',
  }
  return (
    <div className="text-center">
      <div className={`text-2xl font-bold ${colors[highlight]}`}>{value}</div>
      <div className="text-xs text-slate-300 mt-0.5">{label}</div>
      <div className="text-xs text-slate-500 mt-0.5">{sub}</div>
    </div>
  )
}
