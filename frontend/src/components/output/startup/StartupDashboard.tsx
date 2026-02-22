/**
 * Main startup valuation results dashboard.
 * Renders all output panels from StartupValuationOutput.
 */
import React, { useState } from 'react'
import { RefreshCw, TrendingUp, Users, BarChart2, AlertTriangle, ChevronDown, ChevronUp, CheckCircle, AlertCircle, XCircle, Info } from 'lucide-react'
import type { StartupValuationOutput, ValuationMethodResult, DilutionScenario, ScorecardFlag, ValuationSignal, ValuationVerdict } from '../../../types/startup'
import { VERTICAL_LABELS, STAGE_LABELS } from '../../../types/startup'

interface Props {
  output: StartupValuationOutput
  onReset: () => void
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fmt(v: number | null | undefined, decimals = 1): string {
  if (v == null) return '—'
  return `$${v.toFixed(decimals)}M`
}

function fmtPct(v: number): string {
  return `${(v * 100).toFixed(1)}%`
}

function SignalBadge({ signal }: { signal: ValuationSignal }) {
  const colors: Record<ValuationSignal, string> = {
    strong: 'bg-green-900/40 text-green-300 border-green-700/50',
    fair: 'bg-blue-900/40 text-blue-300 border-blue-700/50',
    weak: 'bg-amber-900/40 text-amber-300 border-amber-700/50',
    warning: 'bg-red-900/40 text-red-300 border-red-700/50',
  }
  const icons: Record<ValuationSignal, React.ReactNode> = {
    strong: <CheckCircle size={12} />,
    fair: <Info size={12} />,
    weak: <AlertCircle size={12} />,
    warning: <XCircle size={12} />,
  }
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full border text-xs font-medium ${colors[signal]}`}>
      {icons[signal]}
      {signal.charAt(0).toUpperCase() + signal.slice(1)}
    </span>
  )
}

function VerdictBanner({ verdict, headline, subtext }: { verdict: ValuationVerdict; headline: string; subtext: string }) {
  const styles: Record<ValuationVerdict, string> = {
    strong: 'border-green-600 bg-green-900/20',
    fair: 'border-blue-600 bg-blue-900/20',
    stretched: 'border-amber-500 bg-amber-900/20',
    at_risk: 'border-red-600 bg-red-900/20',
  }
  const dots: Record<ValuationVerdict, string> = {
    strong: 'bg-green-400',
    fair: 'bg-blue-400',
    stretched: 'bg-amber-400',
    at_risk: 'bg-red-400',
  }
  const labels: Record<ValuationVerdict, string> = {
    strong: 'Well Positioned',
    fair: 'Market Rate',
    stretched: 'Stretched',
    at_risk: 'Needs Work',
  }
  return (
    <div className={`rounded-xl border p-6 ${styles[verdict]}`}>
      <div className="flex items-center gap-2 mb-2">
        <span className={`w-2.5 h-2.5 rounded-full ${dots[verdict]}`} />
        <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">{labels[verdict]}</span>
      </div>
      <h3 className="text-xl font-bold text-slate-100 mb-2">{headline}</h3>
      <p className="text-slate-400 text-sm leading-relaxed">{subtext}</p>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Panels
// ---------------------------------------------------------------------------

function ValuationRangePanel({ output }: { output: StartupValuationOutput }) {
  const { blended_valuation, valuation_range_low, valuation_range_high, recommended_safe_cap, implied_dilution, benchmark_p25, benchmark_p50, benchmark_p75, benchmark_p95, percentile_in_market } = output

  // Normalize to a 0–100 bar
  const scale = benchmark_p95 > 0 ? benchmark_p95 : blended_valuation * 2
  const p25pos = Math.min(100, (benchmark_p25 / scale) * 100)
  const p50pos = Math.min(100, (benchmark_p50 / scale) * 100)
  const p75pos = Math.min(100, (benchmark_p75 / scale) * 100)
  const blendedpos = Math.min(100, (blended_valuation / scale) * 100)

  return (
    <div className="rounded-xl border border-slate-700 bg-slate-800/30 p-6">
      <div className="flex items-center gap-2 mb-5">
        <TrendingUp size={16} className="text-purple-400" />
        <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">Valuation Range</h3>
      </div>

      {/* Main number */}
      <div className="text-center mb-6">
        <p className="text-slate-500 text-xs mb-1">Blended Pre-Money Valuation</p>
        <p className="text-5xl font-bold text-slate-100">{fmt(blended_valuation)}</p>
        <p className="text-slate-400 text-sm mt-1">Range: {fmt(valuation_range_low)} – {fmt(valuation_range_high)}</p>
        <p className="text-purple-400 text-xs mt-2 font-medium">{percentile_in_market}</p>
      </div>

      {/* Benchmark bar */}
      <div className="relative mb-3">
        <div className="h-2 bg-slate-700 rounded-full">
          <div
            className="h-2 bg-gradient-to-r from-purple-800 to-purple-500 rounded-full"
            style={{ width: `${blendedpos}%` }}
          />
        </div>
        {/* Benchmark markers */}
        {[{ pos: p25pos, label: 'P25' }, { pos: p50pos, label: 'P50' }, { pos: p75pos, label: 'P75' }].map(({ pos, label }) => (
          <div
            key={label}
            className="absolute top-0 -translate-x-1/2"
            style={{ left: `${pos}%` }}
          >
            <div className="w-px h-2 bg-slate-500" />
          </div>
        ))}
        {/* Your value marker */}
        <div
          className="absolute top-0 -translate-x-1/2"
          style={{ left: `${blendedpos}%` }}
        >
          <div className="w-2 h-2 rounded-full bg-purple-400 ring-2 ring-purple-400/30" />
        </div>
      </div>
      <div className="flex justify-between text-xs text-slate-500 mb-5">
        <span>P25 {fmt(benchmark_p25, 0)}</span>
        <span>P50 {fmt(benchmark_p50, 0)}</span>
        <span>P75 {fmt(benchmark_p75, 0)}</span>
      </div>

      {/* Key metrics */}
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-slate-900/40 rounded-lg p-3">
          <p className="text-xs text-slate-500 mb-1">Implied Dilution</p>
          <p className={`text-lg font-bold ${implied_dilution > 0.25 ? 'text-amber-400' : 'text-slate-100'}`}>
            {fmtPct(implied_dilution)}
          </p>
          <p className="text-2xs text-slate-600 mt-0.5">Raise / Post-money</p>
        </div>
        {recommended_safe_cap && (
          <div className="bg-purple-900/20 border border-purple-700/30 rounded-lg p-3">
            <p className="text-xs text-slate-500 mb-1">Suggested SAFE Cap</p>
            <p className="text-lg font-bold text-purple-300">{fmt(recommended_safe_cap)}</p>
            <p className="text-2xs text-slate-600 mt-0.5">Blended value × 1.15x</p>
          </div>
        )}
      </div>
    </div>
  )
}

function MethodBreakdownPanel({ methods }: { methods: ValuationMethodResult[] }) {
  const [expanded, setExpanded] = useState<string | null>(null)

  const colors: Record<string, string> = {
    berkus: 'bg-blue-500',
    scorecard: 'bg-purple-500',
    risk_factor_summation: 'bg-teal-500',
    arr_multiple: 'bg-green-500',
  }

  return (
    <div className="rounded-xl border border-slate-700 bg-slate-800/30 p-6">
      <div className="flex items-center gap-2 mb-5">
        <BarChart2 size={16} className="text-purple-400" />
        <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">Method Breakdown</h3>
      </div>

      <div className="space-y-3">
        {methods.map(m => (
          <div key={m.method_name} className={`rounded-lg border ${m.applicable ? 'border-slate-700' : 'border-slate-800 opacity-50'}`}>
            <button
              className="w-full p-4 flex items-center justify-between text-left"
              onClick={() => setExpanded(expanded === m.method_name ? null : m.method_name)}
              disabled={!m.applicable}
            >
              <div className="flex items-center gap-3">
                <div className={`w-2.5 h-2.5 rounded-full ${colors[m.method_name] ?? 'bg-slate-500'}`} />
                <div>
                  <p className="text-sm font-medium text-slate-200">{m.method_label}</p>
                  {!m.applicable && (
                    <p className="text-xs text-slate-600">Not applicable at this stage</p>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-3">
                {m.indicated_value != null && (
                  <span className="text-sm font-semibold text-slate-200">{fmt(m.indicated_value)}</span>
                )}
                {m.applicable && (expanded === m.method_name ? <ChevronUp size={14} className="text-slate-500" /> : <ChevronDown size={14} className="text-slate-500" />)}
              </div>
            </button>
            {expanded === m.method_name && m.applicable && (
              <div className="px-4 pb-4 border-t border-slate-700 pt-3">
                <p className="text-xs text-slate-400 mb-3 leading-relaxed">{m.rationale}</p>
                {m.value_low != null && m.value_high != null && (
                  <div className="flex gap-4 text-xs">
                    <div>
                      <span className="text-slate-600">Low: </span>
                      <span className="text-slate-300">{fmt(m.value_low)}</span>
                    </div>
                    <div>
                      <span className="text-slate-600">High: </span>
                      <span className="text-slate-300">{fmt(m.value_high)}</span>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

function DilutionPanel({ scenarios }: { scenarios: DilutionScenario[] }) {
  return (
    <div className="rounded-xl border border-slate-700 bg-slate-800/30 p-6">
      <div className="flex items-center gap-2 mb-5">
        <Users size={16} className="text-purple-400" />
        <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">Founder Dilution Model</h3>
      </div>
      <p className="text-xs text-slate-500 mb-4">
        Projected founder ownership across current and typical future rounds.
        Includes option pool refresh at each priced round (standard 10% pre-money).
      </p>

      <div className="space-y-4">
        {scenarios.map((s, i) => (
          <div key={i} className="relative pl-6">
            {/* Timeline dot */}
            <div className={`absolute left-0 top-1 w-3 h-3 rounded-full border-2 ${i === 0 ? 'bg-purple-500 border-purple-400' : 'bg-slate-700 border-slate-500'}`} />
            {i < scenarios.length - 1 && (
              <div className="absolute left-1.5 top-4 w-px h-full bg-slate-700" />
            )}

            <div className="bg-slate-900/40 rounded-lg p-4">
              <div className="flex justify-between items-start mb-2">
                <p className="text-sm font-medium text-slate-200">{s.round_label}</p>
                <div className="text-right">
                  <p className="text-xs text-slate-500">Founder after</p>
                  <p className={`text-base font-bold ${s.founder_ownership_pct_after < 0.5 ? 'text-amber-400' : 'text-slate-100'}`}>
                    {fmtPct(s.founder_ownership_pct_after)}
                  </p>
                </div>
              </div>
              <div className="grid grid-cols-3 gap-2 text-xs">
                <div>
                  <p className="text-slate-600">Pre-money</p>
                  <p className="text-slate-400">{fmt(s.pre_money)}</p>
                </div>
                <div>
                  <p className="text-slate-600">Raise</p>
                  <p className="text-slate-400">{fmt(s.raise_amount)}</p>
                </div>
                <div>
                  <p className="text-slate-600">Investor %</p>
                  <p className="text-slate-400">{fmtPct(s.investor_ownership_pct)}</p>
                </div>
              </div>
              {/* Dilution bar */}
              <div className="mt-3 h-1.5 bg-slate-700 rounded-full">
                <div
                  className="h-1.5 bg-purple-500 rounded-full"
                  style={{ width: `${(s.founder_ownership_pct_after * 100).toFixed(0)}%` }}
                />
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function ScorecardPanel({ flags }: { flags: ScorecardFlag[] }) {
  return (
    <div className="rounded-xl border border-slate-700 bg-slate-800/30 p-6">
      <div className="flex items-center gap-2 mb-5">
        <CheckCircle size={16} className="text-purple-400" />
        <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">Investor Scorecard</h3>
      </div>
      <p className="text-xs text-slate-500 mb-4">
        How institutional investors read your key metrics. These are the flags that come up in diligence.
      </p>

      <div className="space-y-3">
        {flags.map((f, i) => (
          <div key={i} className="rounded-lg border border-slate-700 p-4">
            <div className="flex items-start justify-between mb-2">
              <p className="text-sm font-medium text-slate-200">{f.metric}</p>
              <div className="flex items-center gap-2">
                <span className="text-sm font-semibold text-slate-100">{f.value}</span>
                <SignalBadge signal={f.signal} />
              </div>
            </div>
            <p className="text-xs text-slate-500 mb-1"><span className="text-slate-600">Benchmark: </span>{f.benchmark}</p>
            <p className="text-xs text-slate-500 leading-relaxed">{f.commentary}</p>
          </div>
        ))}
      </div>
    </div>
  )
}

function TractionBarPanel({ traction_bar, vertical, stage }: { traction_bar: string; vertical: string; stage: string }) {
  return (
    <div className="rounded-xl border border-purple-700/30 bg-purple-900/10 p-5">
      <p className="text-xs font-semibold text-purple-400 uppercase tracking-wider mb-2">
        What {STAGE_LABELS[stage as keyof typeof STAGE_LABELS] ?? stage} investors expect for {VERTICAL_LABELS[vertical as keyof typeof VERTICAL_LABELS] ?? vertical}
      </p>
      <p className="text-sm text-slate-300 leading-relaxed">{traction_bar}</p>
    </div>
  )
}

function WarningsPanel({ warnings, notes }: { warnings: string[]; notes: string[] }) {
  if (!warnings.length && !notes.length) return null
  return (
    <div className="space-y-3">
      {warnings.map((w, i) => (
        <div key={i} className="flex gap-3 p-4 rounded-xl border border-amber-700/40 bg-amber-900/10">
          <AlertTriangle size={16} className="text-amber-400 flex-shrink-0 mt-0.5" />
          <p className="text-sm text-amber-300 leading-relaxed">{w}</p>
        </div>
      ))}
      {notes.map((n, i) => (
        <div key={i} className="flex gap-3 p-3 rounded-lg border border-slate-700 bg-slate-800/20">
          <Info size={14} className="text-slate-500 flex-shrink-0 mt-0.5" />
          <p className="text-xs text-slate-500">{n}</p>
        </div>
      ))}
    </div>
  )
}

function SAFEPanel({ safe }: { safe: NonNullable<StartupValuationOutput['safe_conversion']> }) {
  return (
    <div className="rounded-xl border border-slate-700 bg-slate-800/30 p-6">
      <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider mb-4">SAFE Mechanics</h3>
      <div className="grid grid-cols-2 gap-4 text-sm mb-4">
        <div>
          <p className="text-slate-500 text-xs">SAFE Amount</p>
          <p className="text-slate-200 font-medium">{fmt(safe.safe_amount)}</p>
        </div>
        <div>
          <p className="text-slate-500 text-xs">Valuation Cap</p>
          <p className="text-slate-200 font-medium">{fmt(safe.valuation_cap)}</p>
        </div>
        <div>
          <p className="text-slate-500 text-xs">Implied Ownership at Cap</p>
          <p className="text-slate-200 font-medium">{fmtPct(safe.implied_ownership_pct)}</p>
        </div>
        {safe.discount_rate > 0 && (
          <div>
            <p className="text-slate-500 text-xs">Discount Rate</p>
            <p className="text-slate-200 font-medium">{fmtPct(safe.discount_rate)}</p>
          </div>
        )}
      </div>
      <p className="text-xs text-slate-500 leading-relaxed">{safe.note}</p>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main dashboard
// ---------------------------------------------------------------------------

export default function StartupDashboard({ output, onReset }: Props) {
  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <p className="text-slate-500 text-sm">{STAGE_LABELS[output.stage]} · {VERTICAL_LABELS[output.vertical]}</p>
          <h1 className="text-2xl font-bold text-slate-100">{output.company_name} — Valuation Report</h1>
        </div>
        <button
          onClick={onReset}
          className="flex items-center gap-2 px-4 py-2 rounded-lg border border-slate-600 text-slate-400 hover:text-slate-200 hover:border-slate-500 text-sm transition-all"
        >
          <RefreshCw size={14} /> Start over
        </button>
      </div>

      {/* Verdict */}
      <VerdictBanner verdict={output.verdict} headline={output.verdict_headline} subtext={output.verdict_subtext} />

      {/* Traction bar */}
      <TractionBarPanel traction_bar={output.traction_bar} vertical={output.vertical} stage={output.stage} />

      {/* Warnings / notes */}
      <WarningsPanel warnings={output.warnings} notes={output.computation_notes} />

      {/* Two-column main content */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ValuationRangePanel output={output} />
        <MethodBreakdownPanel methods={output.method_results} />
      </div>

      {/* Scorecard + Dilution */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ScorecardPanel flags={output.investor_scorecard} />
        <DilutionPanel scenarios={output.dilution_scenarios} />
      </div>

      {/* SAFE details */}
      {output.safe_conversion && (
        <SAFEPanel safe={output.safe_conversion} />
      )}

      {/* Data source footer */}
      <div className="text-center text-xs text-slate-600 pt-4 border-t border-slate-800">
        Benchmarks sourced from Carta State of Private Markets Q3 2025, PitchBook-NVCA Venture Monitor, Equidam Startup Valuation Delta H1 2025, Aventis Advisors SaaS Multiples 2025.
        <br />Not financial advice — consult a qualified advisor before making fundraising decisions.
      </div>
    </div>
  )
}
