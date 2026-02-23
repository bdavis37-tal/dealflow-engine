/**
 * AI-generated narrative panel for startup valuation results.
 * User opts in via toggle — AI never auto-runs.
 * Degrades gracefully when AI is unavailable (hides entirely).
 */
import { useState } from 'react'
import { Loader2, ChevronDown, ChevronUp, FileText, Sparkles } from 'lucide-react'
import type { StartupInput, StartupValuationOutput, StartupNarrativeResponse, ScorecardFlag } from '../../../types/startup'
import { generateStartupNarrative } from '../../../lib/ai-api'
import AIBadge from '../../shared/AIBadge'

interface Props {
  startupInput: StartupInput
  output: StartupValuationOutput
  aiAvailable: boolean
}

export default function StartupAINarrative({ startupInput, output, aiAvailable }: Props) {
  const [enabled, setEnabled] = useState(false)
  const [loading, setLoading] = useState(false)
  const [narrative, setNarrative] = useState<StartupNarrativeResponse | null>(null)
  const [showSummary, setShowSummary] = useState(false)

  if (!aiAvailable) return null

  function handleToggle() {
    if (enabled) {
      setEnabled(false)
      return
    }
    setEnabled(true)
    if (narrative) return // already fetched

    setLoading(true)
    generateStartupNarrative(startupInput, output)
      .then(setNarrative)
      .catch(() => setNarrative(null))
      .finally(() => setLoading(false))
  }

  // Find scorecard flags that have commentary
  const flagsWithCommentary: ScorecardFlag[] = narrative
    ? output.investor_scorecard.filter(f => narrative.scorecard_commentary[f.metric])
    : []

  return (
    <div className="space-y-3">
      {/* Toggle button */}
      <button
        onClick={handleToggle}
        className={`flex items-center gap-2 px-4 py-2 rounded-lg border text-sm transition-all ${
          enabled
            ? 'border-purple-600 bg-purple-950/30 text-purple-300'
            : 'border-slate-700 bg-slate-800/30 text-slate-400 hover:border-purple-700 hover:text-purple-400'
        }`}
      >
        <Sparkles size={14} />
        {enabled ? 'Hide AI assessment' : 'Get AI assessment'}
        <AIBadge />
      </button>

      {/* Content */}
      {enabled && (
        <div className="space-y-4 animate-fade-in">
          {loading && (
            <div className="rounded-xl border border-purple-800/30 bg-purple-950/10 p-5">
              <div className="flex items-center gap-3">
                <Loader2 size={16} className="animate-spin text-purple-400" />
                <div>
                  <span className="text-sm text-slate-300">Generating VC advisor's take...</span>
                  <div className="text-xs text-slate-500 mt-0.5">Claude is reviewing the valuation</div>
                </div>
              </div>
              <div className="mt-4 space-y-2 animate-pulse">
                <div className="h-3 bg-slate-800 rounded w-full" />
                <div className="h-3 bg-slate-800 rounded w-5/6" />
                <div className="h-3 bg-slate-800 rounded w-4/6" />
              </div>
            </div>
          )}

          {!loading && narrative?.verdict_narrative && (
            <>
              {/* Verdict narrative */}
              <div className="rounded-xl border border-purple-800/30 bg-purple-950/10 p-5">
                <div className="flex items-center gap-2 mb-3">
                  <AIBadge />
                  <span className="text-xs text-slate-500">VC advisor's take</span>
                  {narrative.cached && <span className="text-xs text-slate-600">cached</span>}
                </div>
                <p className="text-sm text-slate-200 leading-relaxed font-medium">
                  {narrative.verdict_narrative}
                </p>
              </div>

              {/* Scorecard commentary */}
              {flagsWithCommentary.length > 0 && (
                <div className="space-y-2">
                  {flagsWithCommentary.map(flag => (
                    <div key={flag.metric} className="rounded-lg border border-slate-700/50 bg-slate-800/20 px-4 py-3">
                      <div className="flex items-center gap-2 mb-1">
                        <AIBadge />
                        <span className="text-xs text-slate-500">{flag.metric}</span>
                      </div>
                      <p className="text-xs text-slate-300 leading-relaxed">
                        {narrative.scorecard_commentary[flag.metric]}
                      </p>
                    </div>
                  ))}
                </div>
              )}

              {/* Executive summary — collapsible */}
              {narrative.executive_summary && (
                <div className="rounded-xl border border-slate-700 bg-slate-800/10 overflow-hidden">
                  <button
                    onClick={() => setShowSummary(v => !v)}
                    className="w-full flex items-center justify-between px-5 py-3 text-sm text-slate-400 hover:text-slate-200 transition-colors"
                  >
                    <div className="flex items-center gap-2">
                      <FileText size={14} />
                      IC Memo Summary
                      <AIBadge />
                    </div>
                    {showSummary ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                  </button>
                  {showSummary && (
                    <div className="px-5 pb-5 border-t border-slate-700/50 pt-4 animate-fade-in">
                      {narrative.executive_summary.split('\n\n').map((para, i) => (
                        <p key={i} className="text-xs text-slate-300 leading-relaxed mb-3 last:mb-0">
                          {para}
                        </p>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </>
          )}

          {!loading && narrative && !narrative.verdict_narrative && (
            <p className="text-xs text-slate-500 px-1">AI assessment unavailable for this valuation.</p>
          )}
        </div>
      )}
    </div>
  )
}
