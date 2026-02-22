/**
 * VCReturnScenarios — 3-scenario First Chicago return model from LP seat.
 * Bear / Base / Bull with probability weights, MOIC, IRR, fund contribution.
 */

import React, { useState } from 'react'
import type { VCScenario, VCDealOutput } from '../../types/vc'

interface Props {
  output: VCDealOutput
}

function pct(n: number, dec = 0) {
  return `${(n * 100).toFixed(dec)}%`
}
function fmt(n: number, dec = 1) {
  return n.toLocaleString('en-US', { minimumFractionDigits: dec, maximumFractionDigits: dec })
}
function fmtEV(ev: number) {
  if (ev >= 1000) return `$${(ev / 1000).toFixed(1)}B`
  return `$${ev.toFixed(0)}M`
}

function ScenarioCard({ scenario, isBase }: { scenario: VCScenario; isBase?: boolean }) {
  const colorMap = {
    Bear: { bg: 'bg-red-950/30', border: 'border-red-800/30', accent: 'text-red-400', probBg: 'bg-red-900/20' },
    Base: { bg: 'bg-emerald-950/30', border: 'border-emerald-700/30', accent: 'text-emerald-400', probBg: 'bg-emerald-900/20' },
    Bull: { bg: 'bg-blue-950/30', border: 'border-blue-800/30', accent: 'text-blue-400', probBg: 'bg-blue-900/20' },
  }
  const colors = colorMap[scenario.label as keyof typeof colorMap] ?? colorMap.Base

  return (
    <div className={`${colors.bg} border ${colors.border} rounded-xl p-5 ${isBase ? 'ring-1 ring-emerald-600/40' : ''}`}>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <span className={`text-lg font-bold ${colors.accent}`}>{scenario.label}</span>
          {isBase && (
            <span className="text-xs bg-emerald-900/50 text-emerald-400 px-1.5 py-0.5 rounded">
              base
            </span>
          )}
        </div>
        <div className={`${colors.probBg} px-2 py-1 rounded text-xs font-medium ${colors.accent}`}>
          {pct(scenario.probability)} probability
        </div>
      </div>

      {/* Key metrics */}
      <div className="grid grid-cols-2 gap-3 mb-4">
        <Metric label="Exit EV" value={fmtEV(scenario.exit_enterprise_value)} accent={colors.accent} large />
        <Metric label="ARR Multiple" value={`${scenario.exit_multiple_arr.toFixed(0)}x ARR`} accent={colors.accent} />
        <Metric label="Gross MOIC" value={`${fmt(scenario.gross_moic)}x`} accent={colors.accent} large />
        <Metric label="Net MOIC" value={`${fmt(scenario.net_moic)}x`} accent="text-slate-400" />
        <Metric label="Gross IRR" value={pct(scenario.gross_irr)} accent={colors.accent} />
        <Metric label="Net IRR" value={pct(scenario.net_irr)} accent="text-slate-400" />
        <Metric label="Fund Contribution" value={`${fmt(scenario.fund_contribution_x)}x`} accent={colors.accent} />
        <Metric label="Exit Year" value={`Year ${scenario.exit_year}`} accent="text-slate-400" />
      </div>

      {/* Gross Proceeds */}
      <div className="border-t border-slate-700/50 pt-3">
        <div className="flex justify-between text-sm">
          <span className="text-slate-500">Gross proceeds to fund</span>
          <span className="text-slate-200 font-medium">${fmt(scenario.gross_proceeds_to_fund)}M</span>
        </div>
        <div className="flex justify-between text-sm mt-1">
          <span className="text-slate-500">Net proceeds (after carry)</span>
          <span className="text-slate-300">${fmt(scenario.net_proceeds_to_fund)}M</span>
        </div>
      </div>

      {/* Description */}
      <p className="mt-3 text-xs text-slate-500 leading-relaxed">
        {scenario.outcome_description}
      </p>
    </div>
  )
}

function Metric({ label, value, accent, large }: { label: string; value: string; accent: string; large?: boolean }) {
  return (
    <div>
      <div className="text-xs text-slate-500">{label}</div>
      <div className={`${large ? 'text-lg' : 'text-sm'} font-semibold ${accent}`}>{value}</div>
    </div>
  )
}

export default function VCReturnScenarios({ output }: Props) {
  const { bear_scenario, base_scenario, bull_scenario, expected_value, expected_moic, expected_irr, fund_size, check_size } = output

  const ev_moic = check_size > 0 ? expected_value / check_size : 0

  return (
    <div className="space-y-5">
      {/* Expected Value Summary */}
      <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-5">
        <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-4">
          Probability-Weighted Expected Return
        </h3>
        <div className="grid grid-cols-3 gap-4">
          <EVMetric
            label="Expected Value"
            value={`$${expected_value.toFixed(1)}M`}
            sub="Gross, probability-weighted"
          />
          <EVMetric
            label="Expected MOIC"
            value={`${expected_moic.toFixed(1)}x`}
            sub="On total invested"
            highlight={expected_moic >= 3 ? 'green' : expected_moic >= 1.5 ? 'yellow' : 'red'}
          />
          <EVMetric
            label="Expected IRR"
            value={`${(expected_irr * 100).toFixed(0)}%`}
            sub="Gross IRR"
            highlight={expected_irr >= 0.25 ? 'green' : expected_irr >= 0.15 ? 'yellow' : 'red'}
          />
        </div>

        {/* Probability bar */}
        <div className="mt-4">
          <div className="flex h-3 rounded-full overflow-hidden">
            <div
              className="bg-red-600/60"
              style={{ width: `${bear_scenario.probability * 100}%` }}
              title={`Bear: ${(bear_scenario.probability * 100).toFixed(0)}%`}
            />
            <div
              className="bg-emerald-600/60"
              style={{ width: `${base_scenario.probability * 100}%` }}
              title={`Base: ${(base_scenario.probability * 100).toFixed(0)}%`}
            />
            <div
              className="bg-blue-500/60"
              style={{ width: `${bull_scenario.probability * 100}%` }}
              title={`Bull: ${(bull_scenario.probability * 100).toFixed(0)}%`}
            />
          </div>
          <div className="flex justify-between mt-1 text-xs text-slate-500">
            <span>Bear {(bear_scenario.probability * 100).toFixed(0)}%</span>
            <span>Base {(base_scenario.probability * 100).toFixed(0)}%</span>
            <span>Bull {(bull_scenario.probability * 100).toFixed(0)}%</span>
          </div>
        </div>

        {/* Fund contribution note */}
        <div className="mt-3 text-xs text-slate-500">
          Expected contribution: {(expected_value / fund_size).toFixed(2)}x of ${fund_size.toFixed(0)}M fund
          {expected_value / fund_size >= 1 && (
            <span className="text-emerald-400 ml-2">— expected to return 1x+ the fund</span>
          )}
        </div>
      </div>

      {/* Power Law Note */}
      <div className="bg-amber-950/20 border border-amber-800/20 rounded-xl p-4">
        <div className="flex items-start gap-2">
          <span className="text-amber-400 text-sm mt-0.5">⚡</span>
          <p className="text-xs text-slate-400 leading-relaxed">{output.power_law_note}</p>
        </div>
      </div>

      {/* 3 Scenario Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <ScenarioCard scenario={bear_scenario} />
        <ScenarioCard scenario={base_scenario} isBase />
        <ScenarioCard scenario={bull_scenario} />
      </div>

      {/* Flags and Warnings */}
      {(output.flags.length > 0 || output.warnings.length > 0) && (
        <div className="space-y-2">
          {output.flags.map((flag, i) => (
            <div key={i} className="flex items-start gap-2 text-xs text-amber-300 bg-amber-950/20 border border-amber-800/20 rounded-lg px-3 py-2">
              <span className="mt-0.5">⚠</span>
              <span>{flag}</span>
            </div>
          ))}
          {output.warnings.map((w, i) => (
            <div key={i} className="flex items-start gap-2 text-xs text-slate-400 bg-slate-800/50 border border-slate-700 rounded-lg px-3 py-2">
              <span className="mt-0.5">ℹ</span>
              <span>{w}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function EVMetric({ label, value, sub, highlight }: {
  label: string
  value: string
  sub: string
  highlight?: 'green' | 'yellow' | 'red'
}) {
  const colors = { green: 'text-emerald-400', yellow: 'text-amber-400', red: 'text-red-400' }
  return (
    <div className="text-center">
      <div className={`text-2xl font-bold ${highlight ? colors[highlight] : 'text-slate-200'}`}>{value}</div>
      <div className="text-xs text-slate-300 mt-0.5">{label}</div>
      <div className="text-xs text-slate-500">{sub}</div>
    </div>
  )
}
