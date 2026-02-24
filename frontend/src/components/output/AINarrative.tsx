/**
 * Displays AI-generated deal narratives (verdict, risks, executive summary).
 * Fetches on mount, shows skeleton while loading, degrades gracefully.
 */
import { useState, useEffect } from 'react'
import { Loader2, ChevronDown, ChevronUp, FileText } from 'lucide-react'
import type { DealInput, DealOutput } from '../../types/deal'
import { generateNarrative, type NarrativeResponse } from '../../lib/ai-api'
import AIBadge from '../shared/AIBadge'

interface AINarrativeProps {
  dealInput: DealInput
  dealOutput: DealOutput
  aiAvailable: boolean
}

export default function AINarrative({ dealInput, dealOutput, aiAvailable }: AINarrativeProps) {
  const [narrative, setNarrative] = useState<NarrativeResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [showSummary, setShowSummary] = useState(false)

  useEffect(() => {
    if (!aiAvailable) return
    setLoading(true)

    generateNarrative(dealInput, dealOutput)
      .then(setNarrative)
      .catch(() => setNarrative(null))
      .finally(() => setLoading(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps -- fire once on mount; deal data is stable at this point
  }, [])

  if (!aiAvailable) return null

  if (loading) {
    return (
      <div className="rounded-xl border border-purple-800/30 bg-purple-950/10 p-5">
        <div className="flex items-center gap-3">
          <Loader2 size={16} className="animate-spin text-purple-400" />
          <div>
            <span className="text-sm text-slate-300">Generating banker's assessment...</span>
            <div className="text-2xs text-slate-500 mt-0.5">Claude is reviewing the deal numbers</div>
          </div>
        </div>
        {/* Skeleton lines */}
        <div className="mt-4 space-y-2 animate-pulse">
          <div className="h-3 bg-slate-800 rounded w-full" />
          <div className="h-3 bg-slate-800 rounded w-5/6" />
          <div className="h-3 bg-slate-800 rounded w-4/6" />
        </div>
      </div>
    )
  }

  if (!narrative?.verdict_narrative) return null

  return (
    <div className="space-y-4">
      {/* Verdict narrative */}
      <div className="rounded-xl border border-purple-800/30 bg-purple-950/10 p-5">
        <div className="flex items-center gap-2 mb-3">
          <AIBadge />
          <span className="text-xs text-slate-500">Advisor's take</span>
          {narrative.cached && <span className="text-2xs text-slate-600">cached</span>}
        </div>
        <p className="text-sm text-slate-200 leading-relaxed font-medium">
          {narrative.verdict_narrative}
        </p>
      </div>

      {/* Risk narratives — only if risks exist */}
      {Object.keys(narrative.risk_narratives).length > 0 && (
        <div className="space-y-2">
          {Object.entries(narrative.risk_narratives).map(([metric, text]) => (
            <div key={metric} className="rounded-lg border border-slate-700/50 bg-slate-800/20 px-4 py-3">
              <div className="flex items-center gap-2 mb-1">
                <AIBadge />
                <span className="text-2xs text-slate-500">{metric}</span>
              </div>
              <p className="text-xs text-slate-300 leading-relaxed">{text}</p>
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
              Executive Summary
              <AIBadge />
            </div>
            {showSummary ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </button>
          {showSummary && (
            <div className="px-5 pb-5 border-t border-slate-700/50 pt-4 animate-fade-in">
              <div className="prose prose-sm prose-invert max-w-none">
                {narrative.executive_summary.split('\n\n').map((para, i) => (
                  <p key={i} className="text-xs text-slate-300 leading-relaxed mb-3 last:mb-0">
                    {para}
                  </p>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
