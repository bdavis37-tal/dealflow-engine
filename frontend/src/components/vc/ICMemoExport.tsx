/**
 * ICMemoExport — Auto-populated IC memo financial section.
 * Copy-to-clipboard export for deal memos and investment committee presentations.
 */

import { useState } from 'react'
import type { ICMemoFinancials, VCScenario } from '../../types/vc'
import { VC_VERTICAL_LABELS, VC_STAGE_LABELS } from '../../types/vc'

interface Props {
  memo: ICMemoFinancials
  fundName: string
}

function fmt(n: number, dec = 1) {
  return n.toLocaleString('en-US', { minimumFractionDigits: dec, maximumFractionDigits: dec })
}
function pct(n: number, dec = 1) { return `${(n * 100).toFixed(dec)}%` }
function fmtEV(ev: number) {
  if (ev >= 1000) return `$${(ev / 1000).toFixed(1)}B`
  return `$${ev.toFixed(0)}M`
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  function copy() {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }
  return (
    <button
      onClick={copy}
      className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-slate-400 hover:text-slate-200 border border-slate-700 rounded-lg transition-colors"
    >
      {copied ? '✓ Copied' : '⎘ Copy'}
    </button>
  )
}

function ScenarioRow({ scenario }: { scenario: VCScenario }) {
  const colors = { Bear: 'text-red-400', Base: 'text-emerald-400', Bull: 'text-blue-400' }
  const color = colors[scenario.label as keyof typeof colors] ?? 'text-slate-300'
  return (
    <tr className="border-b border-slate-800">
      <td className={`py-2 font-medium text-sm ${color}`}>{scenario.label}</td>
      <td className="py-2 text-right text-slate-400 text-sm">{pct(scenario.probability, 0)}</td>
      <td className="py-2 text-right text-slate-300 text-sm">{fmtEV(scenario.exit_enterprise_value)}</td>
      <td className="py-2 text-right text-slate-200 text-sm font-medium">{fmt(scenario.gross_moic)}x</td>
      <td className="py-2 text-right text-slate-300 text-sm">{pct(scenario.gross_irr, 0)}</td>
      <td className="py-2 text-right text-slate-300 text-sm">${fmt(scenario.gross_proceeds_to_fund)}M</td>
      <td className="py-2 text-right text-slate-400 text-sm">{fmt(scenario.fund_contribution_x, 2)}x</td>
    </tr>
  )
}

export default function ICMemoExport({ memo, fundName }: Props) {
  const [activeTab, setActiveTab] = useState<'financial' | 'thesis'>('financial')

  const financialText = buildFinancialText(memo, fundName)
  const thesisText = memo.investment_thesis_prompt

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-5">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-base font-semibold text-slate-100">IC Memo — Financial Section</h3>
            <p className="text-xs text-slate-500 mt-0.5">Auto-populated from deal inputs. Copy for investment committee.</p>
          </div>
          <CopyButton text={financialText} />
        </div>

        {/* Tabs */}
        <div className="flex gap-1 p-1 bg-slate-800 rounded-lg mb-4 w-fit">
          {(['financial', 'thesis'] as const).map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors capitalize ${
                activeTab === tab
                  ? 'bg-slate-700 text-slate-200'
                  : 'text-slate-500 hover:text-slate-300'
              }`}
            >
              {tab === 'financial' ? 'Financials' : 'Thesis Template'}
            </button>
          ))}
        </div>

        {activeTab === 'financial' && (
          <div className="space-y-5">
            {/* Deal overview */}
            <div>
              <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Deal Overview</div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                <MemoField label="Company" value={memo.company_name} />
                <MemoField label="Stage" value={VC_STAGE_LABELS[memo.stage]} />
                <MemoField label="Vertical" value={VC_VERTICAL_LABELS[memo.vertical]} />
                <MemoField label="Instrument" value={memo.instrument} />
                <MemoField label="Check Size" value={`$${fmt(memo.check_size)}M`} />
                <MemoField label="Post-Money" value={`$${fmt(memo.post_money)}M`} />
                <MemoField label="Entry Ownership" value={pct(memo.entry_ownership_pct)} highlight />
                <MemoField label="Board Seat" value={memo.board_seat ? 'Yes' : 'No'} />
                <MemoField label="Pro-Rata" value={memo.pro_rata_rights ? 'Yes' : 'No'} />
              </div>
            </div>

            {/* Company metrics */}
            <div>
              <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Company Metrics</div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                <MemoField label="ARR" value={memo.arr > 0 ? `$${fmt(memo.arr)}M` : 'Pre-revenue'} />
                <MemoField label="Revenue Growth" value={pct(memo.revenue_growth_rate)} />
                <MemoField label="Gross Margin" value={pct(memo.gross_margin)} />
                <MemoField label="Monthly Burn" value={memo.burn_rate_monthly > 0 ? `$${fmt(memo.burn_rate_monthly)}M/mo` : 'N/A'} />
                {memo.runway_months !== undefined && memo.runway_months !== null && (
                  <MemoField
                    label="Runway"
                    value={`${memo.runway_months.toFixed(0)} months`}
                    highlight={memo.runway_months < 12}
                    flagColor="amber"
                  />
                )}
                {memo.arr_multiple_at_entry && (
                  <MemoField
                    label="Entry ARR Multiple"
                    value={`${memo.arr_multiple_at_entry.toFixed(0)}x`}
                    sub={`vs ${memo.stage_median_arr_multiple?.toFixed(0)}x median`}
                  />
                )}
                <MemoField
                  label="Valuation vs Market"
                  value={memo.valuation_vs_benchmark}
                  highlight={memo.valuation_vs_benchmark === 'above market'}
                  flagColor="amber"
                />
              </div>
            </div>

            {/* Ownership */}
            <div>
              <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Ownership & Return Summary</div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                <MemoField label="Entry Ownership" value={pct(memo.entry_ownership_pct)} highlight />
                <MemoField label="Exit Ownership (est.)" value={pct(memo.ownership_at_exit)} />
                <MemoField label="Total Dilution" value={pct(memo.total_dilution_pct)} />
                <MemoField label="Expected Value" value={`$${fmt(memo.expected_value)}M`} highlight />
                <MemoField
                  label="Fund Returner Threshold"
                  value={`${memo.fund_returner_threshold >= 1000 ? `$${(memo.fund_returner_threshold/1000).toFixed(1)}B` : `$${memo.fund_returner_threshold.toFixed(0)}M`}`}
                />
                <MemoField
                  label="Base Case Contribution"
                  value={`${fmt(memo.fund_contribution_base, 2)}x fund`}
                  highlight
                />
              </div>
            </div>

            {/* Scenarios table */}
            <div>
              <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Return Scenarios</div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-700">
                      {['Scenario', 'Prob.', 'Exit EV', 'MOIC', 'IRR', 'Proceeds', 'Fund Contrib.'].map(h => (
                        <th key={h} className={`py-2 text-slate-500 text-xs font-medium ${h === 'Scenario' ? 'text-left' : 'text-right'}`}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {memo.scenarios.map((s, i) => <ScenarioRow key={i} scenario={s} />)}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Summary paragraph */}
            <div>
              <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Financial Summary</div>
              <div className="bg-slate-900 border border-slate-700 rounded-lg p-4 text-sm text-slate-300 leading-relaxed font-mono text-xs">
                {memo.financial_summary_text}
              </div>
            </div>
          </div>
        )}

        {activeTab === 'thesis' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <p className="text-xs text-slate-500">Pre-filled thesis template. Complete the bracketed sections.</p>
              <CopyButton text={thesisText} />
            </div>
            <div className="bg-slate-900 border border-slate-700 rounded-lg p-4 text-sm text-slate-300 leading-relaxed font-mono text-xs whitespace-pre-wrap">
              {thesisText}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function MemoField({
  label,
  value,
  sub,
  highlight,
  flagColor,
}: {
  label: string
  value: string
  sub?: string
  highlight?: boolean
  flagColor?: 'amber' | 'red'
}) {
  return (
    <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-2.5">
      <div className="text-xs text-slate-500 mb-0.5">{label}</div>
      <div className={`text-sm font-medium ${
        highlight
          ? (flagColor === 'amber' ? 'text-amber-400' : flagColor === 'red' ? 'text-red-400' : 'text-emerald-400')
          : 'text-slate-200'
      }`}>
        {value}
      </div>
      {sub && <div className="text-xs text-slate-600 mt-0.5">{sub}</div>}
    </div>
  )
}

function buildFinancialText(memo: ICMemoFinancials, fundName: string): string {
  const lines = [
    `INVESTMENT COMMITTEE MEMO — FINANCIAL SECTION`,
    `${fundName} | ${new Date().toLocaleDateString('en-US', { month: 'long', year: 'numeric' })}`,
    ``,
    `COMPANY: ${memo.company_name}`,
    `STAGE: ${VC_STAGE_LABELS[memo.stage]} | VERTICAL: ${VC_VERTICAL_LABELS[memo.vertical]}`,
    ``,
    `DEAL TERMS`,
    `- Check Size: $${fmt(memo.check_size)}M`,
    `- Post-Money Valuation: $${fmt(memo.post_money)}M`,
    `- Entry Ownership: ${pct(memo.entry_ownership_pct)}`,
    `- Instrument: ${memo.instrument}`,
    `- Board Seat: ${memo.board_seat ? 'Yes' : 'No'}`,
    `- Pro-Rata Rights: ${memo.pro_rata_rights ? 'Yes' : 'No'}`,
    ``,
    `COMPANY METRICS`,
    `- ARR: ${memo.arr > 0 ? `$${fmt(memo.arr)}M` : 'Pre-revenue'}`,
    `- Revenue Growth Rate: ${pct(memo.revenue_growth_rate)}`,
    `- Gross Margin: ${pct(memo.gross_margin)}`,
    memo.burn_rate_monthly > 0 ? `- Monthly Burn: $${fmt(memo.burn_rate_monthly)}M` : null,
    memo.runway_months ? `- Runway: ${memo.runway_months.toFixed(0)} months` : null,
    memo.arr_multiple_at_entry ? `- Entry ARR Multiple: ${memo.arr_multiple_at_entry.toFixed(0)}x (benchmark: ${memo.stage_median_arr_multiple?.toFixed(0)}x)` : null,
    `- Valuation vs. Market: ${memo.valuation_vs_benchmark}`,
    ``,
    `OWNERSHIP & RETURNS`,
    `- Entry Ownership: ${pct(memo.entry_ownership_pct)}`,
    `- Expected Exit Ownership: ${pct(memo.ownership_at_exit)} (after ${pct(memo.total_dilution_pct)} dilution)`,
    `- Fund Returner Threshold: ${memo.fund_returner_threshold >= 1000 ? `$${(memo.fund_returner_threshold/1000).toFixed(1)}B` : `$${memo.fund_returner_threshold.toFixed(0)}M`} exit needed to return 1x fund`,
    `- Base Case Fund Contribution: ${fmt(memo.fund_contribution_base, 2)}x`,
    ``,
    `RETURN SCENARIOS`,
    `  Scenario  | Prob.   | Exit EV      | MOIC  | IRR   | Proceeds`,
    ...memo.scenarios.map(s =>
      `  ${s.label.padEnd(9)} | ${(s.probability * 100).toFixed(0).padStart(5)}%  | ${fmtEV(s.exit_enterprise_value).padStart(12)} | ${fmt(s.gross_moic).padStart(5)}x | ${(s.gross_irr * 100).toFixed(0).padStart(4)}% | $${fmt(s.gross_proceeds_to_fund)}M`
    ),
    ``,
    `Expected Value (probability-weighted): $${fmt(memo.expected_value)}M`,
    ``,
    `FINANCIAL SUMMARY`,
    memo.financial_summary_text,
  ]
  return lines.filter(l => l !== null).join('\n')
}
