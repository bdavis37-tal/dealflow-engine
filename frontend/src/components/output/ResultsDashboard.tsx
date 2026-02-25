import { useState, useEffect } from 'react'
import { Download, RotateCcw } from 'lucide-react'
import type { DealInput, DealOutput, ModelMode } from '../../types/deal'
import ShareButton from '../shared/ShareButton'
import type { MAInputState } from '../../lib/shareUtils'
import Verdict from './Verdict'
import DealScorecard from './DealScorecard'
import RiskPanel from './RiskPanel'
import SensitivityExplorer from './SensitivityExplorer'
import FinancialStatements from './FinancialStatements'
import AINarrative from './AINarrative'
import AIChatPanel from './AIChatPanel'
import DefensePositioningCard from './DefensePositioningCard'
import SourcesAndUsesTable from './SourcesAndUsesTable'
import ContributionAnalysisTable from './ContributionAnalysisTable'
import CreditProfile from './CreditProfile'
import ImpliedValuationCard from './ImpliedValuationCard'
import ReturnsDetail from './ReturnsDetail'
import { checkAIStatus } from '../../lib/ai-api'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine
} from 'recharts'

interface ResultsDashboardProps {
  output: DealOutput
  dealInput: DealInput
  onReset: () => void
  mode?: ModelMode
}

export default function ResultsDashboard({ output, dealInput, onReset, mode }: ResultsDashboardProps) {
  const [showNotes, setShowNotes] = useState(false)
  const [aiAvailable, setAiAvailable] = useState(false)

  useEffect(() => {
    checkAIStatus()
      .then(s => setAiAvailable(s.ai_available))
      .catch(() => setAiAvailable(false))
  }, [])

  const chartData = output.pro_forma_income_statement.map(yr => ({
    year: yr.fiscal_year_label || `Year ${yr.year}`,
    proFormaEPS: yr.pro_forma_eps,
    standaloneEPS: yr.acquirer_standalone_eps,
    adPct: yr.accretion_dilution_pct,
  }))

  return (
    <div className="animate-fade-in space-y-10 pb-24">
      {/* Header bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Deal Analysis</h1>
          <p className="text-sm text-slate-500 mt-1">
            {dealInput.acquirer.company_name} acquiring {dealInput.target.company_name}
          </p>
        </div>
        <div className="flex items-center gap-3 flex-shrink-0">
          {output.convergence_warning && (
            <span className="text-xs text-amber-400 border border-amber-800/40 rounded-lg px-3 py-1">
              Solver estimate
            </span>
          )}
          {aiAvailable && (
            <span className="text-2xs text-purple-400 border border-purple-800/30 rounded-full px-2 py-0.5">
              AI co-pilot enabled
            </span>
          )}
          <ShareButton
            module="ma"
            inputState={{
              mode: dealInput.mode,
              acquirer: dealInput.acquirer,
              target: dealInput.target,
              structure: dealInput.structure,
              ppa: dealInput.ppa,
              synergies: dealInput.synergies,
            } satisfies MAInputState}
            colorScheme="blue"
          />
          <button
            onClick={onReset}
            className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-200 border border-slate-700 rounded-lg px-3 py-1.5 transition-colors"
          >
            <RotateCcw size={12} /> New Deal
          </button>
        </div>
      </div>

      {/* Verdict — hero section */}
      <Verdict
        verdict={output.deal_verdict}
        headline={output.deal_verdict_headline}
        subtext={output.deal_verdict_subtext}
      />

      {/* AI Narrative — appears below verdict when AI is available */}
      <AINarrative
        dealInput={dealInput}
        dealOutput={output}
        aiAvailable={aiAvailable}
      />

      {/* Defense Positioning — only for Defense & National Security deals */}
      {output.defense_positioning && (
        <DefensePositioningCard positioning={output.defense_positioning} />
      )}

      {/* Sources & Uses of Funds — fundamental deal presentation element */}
      {output.sources_and_uses && (
        <SourcesAndUsesTable data={output.sources_and_uses} />
      )}

      {/* Implied Valuation Metrics */}
      {output.implied_valuation && (
        <ImpliedValuationCard data={output.implied_valuation} />
      )}

      {/* Scorecard */}
      <DealScorecard metrics={output.deal_scorecard} />

      {/* Credit Profile — post-close credit metrics */}
      {output.credit_metrics && (
        <CreditProfile metrics={output.credit_metrics} />
      )}

      {/* EPS Chart */}
      <div>
        <h2 className="text-lg font-semibold text-slate-100 mb-4">EPS Trajectory</h2>
        <div className="rounded-xl border border-slate-700 bg-slate-800/20 p-5">
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={chartData} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e2a3a" />
              <XAxis dataKey="year" tick={{ fill: '#64748b', fontSize: 11 }} />
              <YAxis tick={{ fill: '#64748b', fontSize: 11 }} tickFormatter={(v: number) => `$${v.toFixed(2)}`} />
              <Tooltip
                contentStyle={{ backgroundColor: '#0d1526', border: '1px solid #1e2a3a', borderRadius: 8 }}
                labelStyle={{ color: '#94a3b8' }}
                formatter={(value: number, name: string) => [
                  `$${value.toFixed(2)}`,
                  name === 'proFormaEPS' ? 'Pro Forma EPS' : 'Standalone EPS',
                ]}
              />
              <ReferenceLine y={0} stroke="#334155" />
              <Line
                type="monotone"
                dataKey="standaloneEPS"
                stroke="#475569"
                strokeWidth={2}
                strokeDasharray="5 5"
                dot={false}
                name="Standalone EPS"
              />
              <Line
                type="monotone"
                dataKey="proFormaEPS"
                stroke={output.deal_verdict === 'green' ? '#22c55e' : output.deal_verdict === 'yellow' ? '#f59e0b' : '#ef4444'}
                strokeWidth={2.5}
                dot={{ r: 4, fill: output.deal_verdict === 'green' ? '#22c55e' : '#ef4444' }}
                name="Pro Forma EPS"
              />
            </LineChart>
          </ResponsiveContainer>
          <div className="flex gap-4 mt-2 justify-center text-xs text-slate-500">
            <div className="flex items-center gap-1.5">
              <div className="w-6 h-0.5 border-t-2 border-dashed border-slate-500" />
              Standalone EPS
            </div>
            <div className="flex items-center gap-1.5">
              <div className={`w-6 h-0.5 border-t-2 ${output.deal_verdict === 'green' ? 'border-green-500' : 'border-red-500'}`} />
              Pro Forma EPS
            </div>
          </div>
        </div>
      </div>

      {/* Contribution Analysis */}
      {output.contribution_analysis && (
        <ContributionAnalysisTable
          data={output.contribution_analysis}
          acquirerName={dealInput.acquirer.company_name}
          targetName={dealInput.target.company_name}
        />
      )}

      {/* AI Benchmark Context — only for AI-native targets */}
      {output.ai_modifier_applied && output.ai_benchmark_context && (
        <div className="rounded-xl border border-blue-600/40 bg-blue-900/15 px-5 py-3 flex items-start gap-3">
          <span className="mt-0.5 text-blue-400 text-sm">i</span>
          <p className="text-sm text-blue-300/90 leading-relaxed">
            {output.ai_benchmark_context}
          </p>
        </div>
      )}

      {/* Risk Panel */}
      <RiskPanel risks={output.risk_assessment} />

      {/* Sensitivity Explorer — now with AI scenario stories on cell click */}
      {output.sensitivity_matrices.length > 0 && (
        <div className="rounded-xl border border-slate-700 bg-slate-800/10 p-6">
          <SensitivityExplorer
            matrices={output.sensitivity_matrices}
            dealInput={dealInput}
            dealOutput={output}
            aiAvailable={aiAvailable}
          />
        </div>
      )}

      {/* Financial Statements */}
      <div className="rounded-xl border border-slate-700 bg-slate-800/10 p-6">
        <FinancialStatements
          incomeStatement={output.pro_forma_income_statement}
          mode={mode}
        />
      </div>

      {/* Returns Analysis — equity check, FCF to equity, IRR/MOIC matrix */}
      <div className="rounded-xl border border-slate-700 bg-slate-800/10 p-6">
        <ReturnsDetail
          returns={output.returns_analysis}
          dealInput={dealInput}
          fiscalYearStart={output.fiscal_year_start}
        />
      </div>

      {/* Computation notes */}
      {output.computation_notes.length > 0 && (
        <div>
          <button
            onClick={() => setShowNotes(v => !v)}
            className="text-xs text-slate-500 hover:text-slate-400 underline"
          >
            {showNotes ? 'Hide' : 'Show'} model notes ({output.computation_notes.length})
          </button>
          {showNotes && (
            <ul className="mt-2 space-y-1">
              {output.computation_notes.map((note, i) => (
                <li key={i} className="text-xs text-slate-500">- {note}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      {/* Bottom CTA */}
      <div className="border-t border-slate-800 pt-8 flex items-center justify-between">
        <button
          onClick={onReset}
          className="flex items-center gap-2 px-4 py-2 rounded-lg border border-slate-700 text-slate-400 hover:text-slate-200 text-sm transition-colors"
        >
          <RotateCcw size={14} /> Model Another Deal
        </button>
        <button
          className="flex items-center gap-2 px-4 py-2 rounded-lg border border-slate-700 text-slate-400 text-sm transition-colors opacity-50 cursor-not-allowed"
          title="Export coming soon"
        >
          <Download size={14} /> Export PDF
        </button>
      </div>

      {/* AI Co-Pilot — floating chat panel, bottom-right */}
      <AIChatPanel
        dealInput={dealInput}
        dealOutput={output}
      />
    </div>
  )
}
