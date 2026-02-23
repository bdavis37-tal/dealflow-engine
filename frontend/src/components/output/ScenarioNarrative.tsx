/**
 * Streams a one-paragraph scenario story when a user clicks a sensitivity cell.
 */
import { useState, useEffect } from 'react'
import { Loader2 } from 'lucide-react'
import type { DealInput, DealOutput } from '../../types/deal'
import { streamScenarioNarrative } from '../../lib/ai-api'
import AIBadge from '../shared/AIBadge'
import StreamingText from '../shared/StreamingText'

interface ScenarioNarrativeProps {
  dealInput: DealInput
  dealOutput: DealOutput
  rowLabel: string
  colLabel: string
  rowValue: number
  colValue: number
  accretionPct: number   // The accretion/dilution % for this scenario cell
  aiAvailable: boolean
}

export default function ScenarioNarrative({
  dealInput,
  dealOutput,
  rowLabel,
  colLabel,
  rowValue,
  colValue,
  accretionPct,
  aiAvailable,
}: ScenarioNarrativeProps) {
  const [text, setText] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [, setHasLoaded] = useState(false)

  useEffect(() => {
    if (!aiAvailable) return

    setText('')
    setHasLoaded(false)
    setIsStreaming(true)

    streamScenarioNarrative(
      {
        base_deal_input: dealInput,
        base_deal_output: dealOutput,
        scenario_row_label: rowLabel,
        scenario_col_label: colLabel,
        scenario_row_value: rowValue,
        scenario_col_value: colValue,
        scenario_accretion_pct: accretionPct,
      },
      (chunk) => setText(prev => prev + chunk),
      () => {
        setIsStreaming(false)
        setHasLoaded(true)
      },
    )
  }, [rowValue, colValue]) // Re-run when scenario cell changes

  if (!aiAvailable) return null

  if (!text && isStreaming) {
    return (
      <div className="flex items-center gap-2 text-xs text-slate-500 mt-3 py-2">
        <Loader2 size={12} className="animate-spin" />
        Generating scenario story...
      </div>
    )
  }

  if (!text) return null

  return (
    <div className="mt-4 rounded-lg border border-purple-800/30 bg-purple-950/10 p-4 animate-fade-in">
      <div className="flex items-center gap-2 mb-2">
        <AIBadge />
        <span className="text-2xs text-slate-500">Scenario story</span>
      </div>
      <StreamingText
        text={text}
        isStreaming={isStreaming}
        className="text-xs text-slate-300 leading-relaxed"
      />
    </div>
  )
}
