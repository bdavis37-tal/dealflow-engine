/**
 * WaterfallAnalyzer — Liquidation preference waterfall.
 * Interactive exit-price slider + distribution chart per share class.
 */

import { useState } from 'react'
import type { VCDealOutput, WaterfallShareClass } from '../../types/vc'

interface Props {
  output: VCDealOutput
}

function fmt(n: number, dec = 1) {
  return n.toLocaleString('en-US', { minimumFractionDigits: dec, maximumFractionDigits: dec })
}
function fmtEV(ev: number) {
  if (ev >= 1000) return `$${(ev / 1000).toFixed(1)}B`
  return `$${ev.toFixed(0)}M`
}

export default function WaterfallAnalyzer({ output }: Props) {
  const [exitEV, setExitEV] = useState(output.base_scenario.exit_enterprise_value)

  // Use pre-computed waterfall from output if available, or show placeholder
  const waterfall = output.waterfall

  if (!waterfall && (!output.ic_memo || output.ic_memo.arr === 0)) {
    return (
      <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-8 text-center">
        <div className="text-3xl mb-3">📋</div>
        <div className="text-sm text-slate-400">No cap table provided.</div>
        <div className="text-xs text-slate-500 mt-1">
          Add liquidation preferences in the deal screen to model the waterfall.
        </div>
      </div>
    )
  }

  const maxEV = Math.max(
    output.bull_scenario.exit_enterprise_value * 1.5,
    output.ownership.fund_returner_3x_exit * 1.2
  )
  const minEV = 1

  // Compute simplified waterfall at current slider value
  const investorPct = output.ownership.exit_ownership_pct

  // At slider exit, compute investor proceeds
  const investorProceeds = exitEV * investorPct
  const investorMoic = output.ic_memo ? investorProceeds / output.check_size : 0

  const scenarios = [
    { label: 'Bear', ev: output.bear_scenario.exit_enterprise_value, color: 'bg-red-500' },
    { label: 'Base', ev: output.base_scenario.exit_enterprise_value, color: 'bg-emerald-500' },
    { label: 'Bull', ev: output.bull_scenario.exit_enterprise_value, color: 'bg-blue-500' },
    { label: '1x Fund', ev: output.ownership.fund_returner_1x_exit, color: 'bg-amber-500' },
  ]

  return (
    <div className="space-y-5">
      <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-5">
        <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-4">
          Waterfall Analyzer
        </h3>

        {/* Exit slider */}
        <div className="mb-6">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-slate-300">Exit Enterprise Value</span>
            <span className="text-emerald-400 font-semibold text-lg">{fmtEV(exitEV)}</span>
          </div>
          <input
            type="range"
            min={minEV}
            max={maxEV}
            step={(maxEV - minEV) / 200}
            value={exitEV}
            onChange={e => setExitEV(parseFloat(e.target.value))}
            className="w-full accent-emerald-500"
          />
          <div className="flex justify-between mt-1 text-xs text-slate-600">
            <span>${minEV}M</span>
            <span>{fmtEV(maxEV)}</span>
          </div>

          {/* Scenario markers */}
          <div className="flex flex-wrap gap-2 mt-3">
            {scenarios.map(s => (
              <button
                key={s.label}
                onClick={() => setExitEV(Math.max(s.ev, minEV))}
                className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs border transition-colors
                  ${Math.abs(exitEV - s.ev) < s.ev * 0.02
                    ? 'bg-slate-700 border-slate-500 text-slate-200'
                    : 'border-slate-700 text-slate-500 hover:text-slate-300'
                  }`}
              >
                <span className={`w-2 h-2 rounded-full ${s.color}`} />
                {s.label}
              </button>
            ))}
          </div>
        </div>

        {/* Distribution */}
        <div className="space-y-3">
          <div className="text-xs text-slate-500 uppercase tracking-wider font-medium">Distribution at {fmtEV(exitEV)}</div>

          {/* If we have pre-computed waterfall data */}
          {waterfall && (
            <>
              {exitEV !== waterfall.exit_ev && (
                <p className="text-2xs text-slate-600">
                  Bars scale the exact distribution computed at {fmtEV(waterfall.exit_ev)} linearly —
                  preference breakpoints are not re-solved at the slider value.
                </p>
              )}
              {waterfall.share_classes.map((cls, i) => (
                <WaterfallBar
                  key={i}
                  shareClass={cls}
                  exitEV={exitEV}
                  scaledGets={cls.gets * (exitEV / output.base_scenario.exit_enterprise_value)}
                />
              ))}
              <WaterfallBar
                shareClass={{
                  share_class: 'Common + ESOP',
                  type: 'non_participating',
                  preference_amount: 0,
                  preference_multiple: 0,
                  liquidation_payout: 0,
                  conversion_value: 0,
                  gets: waterfall.common_gets * (exitEV / output.base_scenario.exit_enterprise_value),
                  converted: false,
                }}
                exitEV={exitEV}
                scaledGets={waterfall.common_gets * (exitEV / output.base_scenario.exit_enterprise_value)}
                isCommon
              />
            </>
          )}

          {/* Simplified if no stack */}
          {!waterfall && (
            <>
              <SimpleBar label="This Investment" pct={output.ownership.exit_ownership_pct} exitEV={exitEV} />
              <SimpleBar label="Other Preferred" pct={0.40} exitEV={exitEV} />
              <SimpleBar label="Common + ESOP" pct={0.30} exitEV={exitEV} />
            </>
          )}
        </div>

        {/* Investor summary */}
        <div className="mt-5 pt-4 border-t border-slate-700 grid grid-cols-2 gap-4">
          <div>
            <div className="text-xs text-slate-500">Your proceeds at this exit</div>
            <div className="text-xl font-bold text-emerald-400">${fmt(investorProceeds)}M</div>
          </div>
          <div>
            <div className="text-xs text-slate-500">MOIC at this exit</div>
            <div className={`text-xl font-bold ${investorMoic >= 3 ? 'text-emerald-400' : investorMoic >= 1 ? 'text-amber-400' : 'text-red-400'}`}>
              {fmt(investorMoic)}x
            </div>
          </div>
          {waterfall?.conversion_was_optimal && (
            <div className="col-span-2 text-xs text-emerald-400 bg-emerald-950/20 rounded-lg px-3 py-1.5">
              ✓ Conversion to common was optimal vs. liquidating preference at this exit
            </div>
          )}
        </div>
      </div>

      {/* Share class detail — exact engine output at the computed exit */}
      {waterfall && waterfall.share_classes.length > 0 && (
        <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-5">
          <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">
            Share Class Detail
          </h3>
          <p className="text-xs text-slate-500 mb-4">
            Exact distribution computed at {fmtEV(waterfall.exit_ev)}. Preference = invested × liquidation multiple.
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-700">
                  <th className="text-left py-2 text-slate-500 text-xs font-medium">Class</th>
                  <th className="text-right py-2 text-slate-500 text-xs font-medium">Invested</th>
                  <th className="text-right py-2 text-slate-500 text-xs font-medium">Preference (× mult)</th>
                  <th className="text-right py-2 text-slate-500 text-xs font-medium">Liq. Payout</th>
                  <th className="text-right py-2 text-slate-500 text-xs font-medium">Conv. Value</th>
                  <th className="text-right py-2 text-slate-500 text-xs font-medium">Receives</th>
                </tr>
              </thead>
              <tbody>
                {waterfall.share_classes.map((cls, i) => (
                  <tr key={i} className="border-b border-slate-800">
                    <td className="py-2 text-slate-300">
                      {cls.share_class}
                      {cls.converted && <span className="ml-2 text-emerald-600 text-2xs">converted</span>}
                    </td>
                    <td className="py-2 text-right text-slate-400">
                      {cls.invested_amount != null ? `$${fmt(cls.invested_amount)}M` : '—'}
                    </td>
                    <td className="py-2 text-right text-slate-300">
                      ${fmt(cls.preference_amount)}M
                      <span className="text-slate-600 text-2xs ml-1">({cls.preference_multiple.toFixed(1)}x)</span>
                    </td>
                    <td className="py-2 text-right text-slate-400">${fmt(cls.liquidation_payout)}M</td>
                    <td className="py-2 text-right text-slate-400">${fmt(cls.conversion_value)}M</td>
                    <td className="py-2 text-right text-slate-200 font-medium">${fmt(cls.gets)}M</td>
                  </tr>
                ))}
                <tr>
                  <td className="py-2 text-slate-500">Common + ESOP</td>
                  <td className="py-2 text-right text-slate-600">—</td>
                  <td className="py-2 text-right text-slate-600">—</td>
                  <td className="py-2 text-right text-slate-600">—</td>
                  <td className="py-2 text-right text-slate-600">—</td>
                  <td className="py-2 text-right text-slate-300">${fmt(waterfall.common_gets)}M</td>
                </tr>
              </tbody>
            </table>
          </div>

          {/* Approximation / reconciliation notes from the engine */}
          {waterfall.notes.length > 0 && (
            <div className="mt-4 space-y-1">
              {waterfall.notes.map((n, i) => (
                <div key={i} className="text-xs text-slate-500 flex items-start gap-2">
                  <span className="mt-0.5">ℹ</span><span>{n}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function WaterfallBar({
  shareClass,
  exitEV,
  scaledGets,
  isCommon,
}: {
  shareClass: WaterfallShareClass | { share_class: string; gets: number; converted: boolean }
  exitEV: number
  scaledGets: number
  isCommon?: boolean
}) {
  const pctOfEV = exitEV > 0 ? scaledGets / exitEV : 0
  return (
    <div>
      <div className="flex items-center justify-between text-xs mb-1">
        <div className="flex items-center gap-2">
          <span className={isCommon ? 'text-slate-500' : (shareClass as WaterfallShareClass).converted ? 'text-emerald-400' : 'text-slate-300'}>
            {shareClass.share_class}
          </span>
          {(shareClass as WaterfallShareClass).converted && (
            <span className="text-emerald-600 text-2xs">converted</span>
          )}
        </div>
        <div className="flex items-center gap-3">
          <span className="text-slate-500">{(pctOfEV * 100).toFixed(1)}%</span>
          <span className={isCommon ? 'text-slate-500' : 'text-slate-200 font-medium'}>
            ${scaledGets.toFixed(0)}M
          </span>
        </div>
      </div>
      <div className="h-3 bg-slate-700 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${
            isCommon ? 'bg-slate-500' : (shareClass as WaterfallShareClass).converted ? 'bg-emerald-500' : 'bg-blue-500'
          }`}
          style={{ width: `${Math.min(pctOfEV * 100, 100)}%` }}
        />
      </div>
    </div>
  )
}

function SimpleBar({ label, pct: p, exitEV }: { label: string; pct: number; exitEV: number }) {
  const proceeds = exitEV * p
  return (
    <div>
      <div className="flex items-center justify-between text-xs mb-1">
        <span className="text-slate-400">{label}</span>
        <div className="flex items-center gap-3">
          <span className="text-slate-500">{(p * 100).toFixed(0)}%</span>
          <span className="text-slate-200">${proceeds.toFixed(0)}M</span>
        </div>
      </div>
      <div className="h-3 bg-slate-700 rounded-full overflow-hidden">
        <div
          className="h-full rounded-full bg-emerald-500/60"
          style={{ width: `${Math.min(p * 100, 100)}%` }}
        />
      </div>
    </div>
  )
}
