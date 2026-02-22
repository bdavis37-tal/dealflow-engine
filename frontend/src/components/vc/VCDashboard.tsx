/**
 * VCDashboard — Full VC deal results dashboard.
 * Renders after deal evaluation completes (Step 3 of VC flow).
 * Tabs: Overview | Ownership | Returns | Waterfall | IC Memo | Portfolio
 */

import React, { useState } from 'react'
import type { VCDealOutput, FundProfile } from '../../types/vc'
import { VC_VERTICAL_LABELS, VC_STAGE_LABELS } from '../../types/vc'
import VCOwnershipPanel from './VCOwnershipPanel'
import VCReturnScenarios from './VCReturnScenarios'
import WaterfallAnalyzer from './WaterfallAnalyzer'
import ICMemoExport from './ICMemoExport'
import VCPortfolioDash from './VCPortfolioDash'
import VCGovernanceTools from './VCGovernanceTools'

interface Props {
  output: VCDealOutput
  fund: FundProfile
  onNewDeal: () => void
  onReset: () => void
}

type Tab = 'overview' | 'ownership' | 'returns' | 'waterfall' | 'memo' | 'portfolio' | 'governance'

const TABS: { id: Tab; label: string }[] = [
  { id: 'overview', label: 'Overview' },
  { id: 'ownership', label: 'Ownership' },
  { id: 'returns', label: 'Returns' },
  { id: 'waterfall', label: 'Waterfall' },
  { id: 'memo', label: 'IC Memo' },
  { id: 'portfolio', label: 'Portfolio' },
  { id: 'governance', label: 'QSBS / Legal' },
]

function fmt(n: number, dec = 1) {
  return n.toLocaleString('en-US', { minimumFractionDigits: dec, maximumFractionDigits: dec })
}
function pct(n: number) { return `${(n * 100).toFixed(1)}%` }
function fmtEV(ev: number) {
  if (ev >= 1000) return `$${(ev / 1000).toFixed(1)}B`
  return `$${ev.toFixed(0)}M`
}

export default function VCDashboard({ output, fund, onNewDeal, onReset }: Props) {
  const [tab, setTab] = useState<Tab>('overview')

  const rec = output.quick_screen.recommendation
  const recColors = {
    strong_interest: { bg: 'bg-emerald-900/40', border: 'border-emerald-600/40', text: 'text-emerald-400', icon: '🟢' },
    look_deeper: { bg: 'bg-amber-900/40', border: 'border-amber-600/40', text: 'text-amber-400', icon: '🟡' },
    pass: { bg: 'bg-red-900/40', border: 'border-red-600/40', text: 'text-red-400', icon: '🔴' },
  }
  const rc = recColors[rec]

  return (
    <div className="max-w-5xl mx-auto">
      {/* Hero — Verdict + Quick screen */}
      <div className={`${rc.bg} border ${rc.border} rounded-2xl p-6 mb-6`}>
        <div className="flex items-start justify-between mb-4">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <span className="text-2xl">{rc.icon}</span>
              <h1 className={`text-2xl font-bold ${rc.text}`}>
                {rec === 'strong_interest' ? 'Strong Interest'
                 : rec === 'look_deeper' ? 'Look Deeper'
                 : 'Pass'}
              </h1>
            </div>
            <p className="text-slate-300 text-sm leading-relaxed max-w-xl">
              {output.quick_screen.recommendation_rationale}
            </p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={onNewDeal}
              className="px-4 py-2 text-sm text-slate-400 hover:text-slate-200 border border-slate-700 rounded-xl transition-colors"
            >
              New Deal
            </button>
            <button
              onClick={onReset}
              className="px-4 py-2 text-sm text-slate-500 hover:text-slate-300 transition-colors"
            >
              Reset
            </button>
          </div>
        </div>

        {/* Key numbers at a glance */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <HeroMetric label="Entry Ownership" value={pct(output.ownership.entry_ownership_pct)} />
          <HeroMetric label="Base Case MOIC" value={`${fmt(output.base_scenario.gross_moic)}x`} highlight />
          <HeroMetric label="Expected IRR" value={pct(output.expected_irr)} />
          <HeroMetric label="Fund Returner" value={fmtEV(output.ownership.fund_returner_1x_exit)} />
          <HeroMetric label="Base Contribution" value={`${fmt(output.base_scenario.fund_contribution_x, 2)}x fund`} />
        </div>

        {/* Company + deal context */}
        <div className="mt-4 pt-4 border-t border-slate-700/50 flex flex-wrap items-center gap-3 text-xs text-slate-500">
          <span className="text-slate-300 font-medium">{output.company_name}</span>
          <span>·</span>
          <span>{VC_STAGE_LABELS[output.stage]}</span>
          <span>·</span>
          <span>{VC_VERTICAL_LABELS[output.vertical]}</span>
          <span>·</span>
          <span>${fmt(output.check_size)}M @ ${fmt(output.post_money)}M post</span>
          <span>·</span>
          <span>{fund.fund_name} (${fmt(fund.fund_size)}M)</span>
        </div>
      </div>

      {/* Flags (compact) */}
      {output.quick_screen.flags.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-5">
          {output.quick_screen.flags.map((flag, i) => (
            <div key={i} className="flex items-center gap-1.5 text-xs text-amber-300 bg-amber-950/20 border border-amber-800/20 px-2.5 py-1 rounded-full">
              <span>⚠</span>
              <span>{flag}</span>
            </div>
          ))}
        </div>
      )}

      {/* Navigation tabs */}
      <div className="flex gap-1 p-1 bg-slate-800/60 border border-slate-700 rounded-xl mb-6 overflow-x-auto">
        {TABS.map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`flex-1 min-w-fit px-3 py-2 rounded-lg text-xs font-medium transition-all whitespace-nowrap
              ${tab === t.id
                ? 'bg-emerald-700/80 text-white shadow'
                : 'text-slate-400 hover:text-slate-200'
              }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {tab === 'overview' && <OverviewTab output={output} fund={fund} />}
      {tab === 'ownership' && (
        <VCOwnershipPanel
          ownership={output.ownership}
          fund={fund}
          checkSize={output.check_size}
          postMoney={output.post_money}
          arr={output.ic_memo.arr}
        />
      )}
      {tab === 'returns' && <VCReturnScenarios output={output} />}
      {tab === 'waterfall' && <WaterfallAnalyzer output={output} />}
      {tab === 'memo' && <ICMemoExport memo={output.ic_memo} fundName={fund.fund_name} />}
      {tab === 'portfolio' && <VCPortfolioDash fund={fund} />}
      {tab === 'governance' && <VCGovernanceTools fund={fund} />}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Overview Tab — Summary of all key outputs
// ---------------------------------------------------------------------------
function OverviewTab({ output, fund }: { output: VCDealOutput; fund: FundProfile }) {
  return (
    <div className="space-y-5">
      {/* 3-scenario summary table */}
      <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-5">
        <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-4">3-Scenario Return Model</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-700">
                {['', 'Prob.', 'Exit EV', 'MOIC', 'IRR', 'Fund Contrib.'].map(h => (
                  <th key={h} className={`py-2 text-slate-500 text-xs font-medium ${h ? 'text-right' : 'text-left'}`}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {[output.bear_scenario, output.base_scenario, output.bull_scenario].map((s) => {
                const colors = { Bear: 'text-red-400', Base: 'text-emerald-400', Bull: 'text-blue-400' }
                return (
                  <tr key={s.label} className="border-b border-slate-800">
                    <td className={`py-2.5 font-semibold text-sm ${colors[s.label as keyof typeof colors]}`}>{s.label}</td>
                    <td className="py-2.5 text-right text-slate-400">{pct(s.probability)}</td>
                    <td className="py-2.5 text-right text-slate-300">{fmtEV(s.exit_enterprise_value)}</td>
                    <td className={`py-2.5 text-right font-bold ${s.gross_moic >= 10 ? 'text-emerald-400' : s.gross_moic >= 3 ? 'text-amber-400' : 'text-red-400'}`}>
                      {fmt(s.gross_moic)}x
                    </td>
                    <td className="py-2.5 text-right text-slate-300">{pct(s.gross_irr)}</td>
                    <td className={`py-2.5 text-right ${s.fund_contribution_x >= 1 ? 'text-emerald-400 font-semibold' : 'text-slate-400'}`}>
                      {fmt(s.fund_contribution_x, 2)}x
                    </td>
                  </tr>
                )
              })}
            </tbody>
            <tfoot>
              <tr className="bg-slate-900/40">
                <td className="py-2.5 text-slate-300 font-semibold text-sm">Expected</td>
                <td className="py-2.5 text-right text-slate-500 text-xs">weighted</td>
                <td className="py-2.5 text-right text-slate-400">—</td>
                <td className="py-2.5 text-right text-slate-200 font-bold">{fmt(output.expected_moic)}x</td>
                <td className="py-2.5 text-right text-slate-300">{pct(output.expected_irr)}</td>
                <td className="py-2.5 text-right text-slate-400">{fmt(output.expected_value / fund.fund_size, 2)}x</td>
              </tr>
            </tfoot>
          </table>
        </div>
      </div>

      {/* Ownership summary */}
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-5">
          <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-4">Ownership Summary</h3>
          <div className="space-y-2 text-sm">
            <SummaryRow label="Entry Ownership" value={pct(output.ownership.entry_ownership_pct)} highlight />
            <SummaryRow label="Exit Ownership" value={pct(output.ownership.exit_ownership_pct)} />
            <SummaryRow label="Total Dilution" value={pct(output.ownership.total_dilution_pct)} />
            <SummaryRow label="Status" value={
              output.ownership_adequacy === 'strong' ? '✓ Strong' :
              output.ownership_adequacy === 'acceptable' ? '⚠ Acceptable' : '✗ Thin'
            } highlight={output.ownership_adequacy !== 'strong'} />
          </div>
        </div>

        <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-5">
          <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-4">Fund Returner</h3>
          <div className="space-y-2 text-sm">
            <SummaryRow label="1x Fund Exit" value={fmtEV(output.ownership.fund_returner_1x_exit)} />
            <SummaryRow label="3x Fund Exit" value={fmtEV(output.ownership.fund_returner_3x_exit)} />
            <SummaryRow
              label="Base achieves 1x fund?"
              value={output.base_scenario.exit_enterprise_value > output.ownership.fund_returner_1x_exit ? '✓ Yes' : '✗ No'}
              highlight
            />
          </div>
        </div>
      </div>

      {/* Company snapshot */}
      <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-5">
        <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-4">Company Snapshot</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
          <SummaryCard label="ARR" value={output.ic_memo.arr > 0 ? `$${fmt(output.ic_memo.arr)}M` : 'Pre-revenue'} />
          <SummaryCard label="Revenue Growth" value={pct(output.ic_memo.revenue_growth_rate)} />
          <SummaryCard label="Gross Margin" value={pct(output.ic_memo.gross_margin)} />
          {output.ic_memo.runway_months && (
            <SummaryCard
              label="Runway"
              value={`${output.ic_memo.runway_months.toFixed(0)} mo`}
              warn={output.ic_memo.runway_months < 12}
            />
          )}
          {output.ic_memo.arr_multiple_at_entry && (
            <SummaryCard label="Entry ARR Multiple" value={`${output.ic_memo.arr_multiple_at_entry.toFixed(0)}x`} />
          )}
          <SummaryCard label="Vs. Market" value={output.ic_memo.valuation_vs_benchmark} />
        </div>
      </div>

      {/* Power law note */}
      <div className="bg-amber-950/20 border border-amber-800/20 rounded-xl p-4">
        <div className="flex items-start gap-2">
          <span className="text-amber-400 text-sm mt-0.5">⚡</span>
          <p className="text-xs text-slate-400 leading-relaxed">{output.power_law_note}</p>
        </div>
      </div>
    </div>
  )
}

function HeroMetric({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div className="bg-slate-900/40 rounded-xl px-4 py-3 text-center">
      <div className={`text-lg font-bold ${highlight ? 'text-emerald-400' : 'text-slate-200'}`}>{value}</div>
      <div className="text-xs text-slate-500 mt-0.5">{label}</div>
    </div>
  )
}

function SummaryRow({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div className="flex items-center justify-between py-1 border-b border-slate-800">
      <span className="text-slate-500 text-xs">{label}</span>
      <span className={`font-medium text-xs ${highlight ? 'text-emerald-400' : 'text-slate-300'}`}>{value}</span>
    </div>
  )
}

function SummaryCard({ label, value, warn }: { label: string; value: string; warn?: boolean }) {
  return (
    <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-2.5">
      <div className="text-xs text-slate-500">{label}</div>
      <div className={`text-sm font-medium mt-0.5 ${warn ? 'text-amber-400' : 'text-slate-200'}`}>{value}</div>
    </div>
  )
}
