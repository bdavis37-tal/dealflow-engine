/**
 * Enhanced help popover with AI-powered contextual explanations.
 * Shows static text instantly, then offers "Tell me more" AI expansion.
 */
import { useState } from 'react'
import { HelpCircle, Loader2, Sparkles } from 'lucide-react'
import { explainField } from '../../lib/ai-api'
import AIBadge from '../shared/AIBadge'

interface AIHelpPopoverProps {
  fieldName: string
  fieldLabel: string
  staticHelp: string
  industry?: string
  currentValue?: string
  dealContextSummary?: string
}

export default function AIHelpPopover({
  fieldName,
  fieldLabel,
  staticHelp,
  industry = 'Manufacturing',
  currentValue,
  dealContextSummary,
}: AIHelpPopoverProps) {
  const [open, setOpen] = useState(false)
  const [aiExplanation, setAiExplanation] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(false)

  const fetchAIHelp = async () => {
    if (aiExplanation || loading) return
    setLoading(true)
    setError(false)
    try {
      const res = await explainField(
        fieldName,
        fieldLabel,
        industry,
        currentValue,
        dealContextSummary,
      )
      if (res.ai_available && res.explanation) {
        setAiExplanation(res.explanation)
      } else {
        setError(true)
      }
    } catch {
      setError(true)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="relative inline-block">
      <button
        type="button"
        onClick={() => setOpen(v => !v)}
        className="text-slate-500 hover:text-slate-300 transition-colors"
        aria-label="Help"
      >
        <HelpCircle size={13} />
      </button>

      {open && (
        <div className="absolute z-50 left-6 top-0 w-72 rounded-xl border border-slate-700 bg-slate-900 shadow-xl animate-fade-in">
          <div className="p-4 space-y-3">
            {/* Static help — always present, instant */}
            <p className="text-xs text-slate-300 leading-relaxed">{staticHelp}</p>

            {/* AI expansion */}
            {!aiExplanation && !loading && !error && (
              <button
                onClick={fetchAIHelp}
                className="flex items-center gap-1.5 text-xs text-purple-400 hover:text-purple-300 transition-colors"
              >
                <Sparkles size={11} />
                Tell me more about this for my deal
              </button>
            )}

            {loading && (
              <div className="flex items-center gap-2 text-xs text-slate-500">
                <Loader2 size={12} className="animate-spin" />
                Getting contextual explanation...
              </div>
            )}

            {aiExplanation && (
              <div className="border-t border-slate-700 pt-3 space-y-2">
                <div className="flex items-center gap-1.5">
                  <AIBadge />
                  <span className="text-2xs text-slate-500">In context of your deal</span>
                </div>
                <p className="text-xs text-slate-300 leading-relaxed">{aiExplanation}</p>
              </div>
            )}

            {error && (
              <p className="text-2xs text-slate-500 italic">AI explanation unavailable.</p>
            )}
          </div>

          {/* Close button */}
          <button
            onClick={() => setOpen(false)}
            className="absolute top-2 right-2 text-slate-600 hover:text-slate-400 text-xs"
          >
            ✕
          </button>
        </div>
      )}
    </div>
  )
}
