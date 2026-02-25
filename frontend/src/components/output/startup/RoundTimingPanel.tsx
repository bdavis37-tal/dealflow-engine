/**
 * RoundTimingPanel — displays the round timing signal output block.
 * Shows raise signal (raise_now / raise_in_months / focus_milestones),
 * runway, milestone gaps, and inline warnings.
 */
import { AlertTriangle, CheckCircle, XCircle, Clock } from 'lucide-react'
import type { RoundTimingSignal, RaiseSignal, StartupStage } from '../../../types/startup'
import { STAGE_LABELS } from '../../../types/startup'

interface Props {
  roundTiming: RoundTimingSignal
  stage: StartupStage
}

const SIGNAL_CONFIG: Record<RaiseSignal, {
  bg: string
  border: string
  text: string
  badgeBg: string
  icon: string
}> = {
  raise_now: {
    bg: 'bg-red-900/20',
    border: 'border-red-700/50',
    text: 'text-red-400',
    badgeBg: 'bg-red-900/40 border-red-700/50',
    icon: '🔴',
  },
  raise_in_months: {
    bg: 'bg-amber-900/20',
    border: 'border-amber-700/50',
    text: 'text-amber-400',
    badgeBg: 'bg-amber-900/40 border-amber-700/50',
    icon: '🟡',
  },
  focus_milestones: {
    bg: 'bg-green-900/20',
    border: 'border-green-700/50',
    text: 'text-green-400',
    badgeBg: 'bg-green-900/40 border-green-700/50',
    icon: '🟢',
  },
}

export default function RoundTimingPanel({ roundTiming, stage }: Props) {
  const cfg = SIGNAL_CONFIG[roundTiming.signal]
  const hasRunway = roundTiming.runway_months > 0
  const stageLabel = STAGE_LABELS[stage]

  return (
    <div className={`rounded-xl border ${cfg.border} ${cfg.bg} p-5`}>
      {/* Header row */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <Clock size={15} className={cfg.text} />
          <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
            Round Timing Signal
          </span>
        </div>
        <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-xs font-semibold ${cfg.badgeBg} ${cfg.text}`}>
          <span>{cfg.icon}</span>
          {roundTiming.signal_label}
        </span>
      </div>

      {/* Detail text */}
      <p className="text-sm text-slate-300 leading-relaxed mb-4">
        {roundTiming.signal_detail}
      </p>

      {/* Runway + timeline stats */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-4">
        <StatBox
          label="Current Runway"
          value={hasRunway ? `${roundTiming.runway_months.toFixed(0)} mo` : 'Unknown'}
          warn={hasRunway && roundTiming.runway_months < 12}
        />
        <StatBox
          label={`Typical ${stageLabel} → Next`}
          value={roundTiming.months_to_next_round > 0 ? `${roundTiming.months_to_next_round.toFixed(0)} mo` : 'Terminal'}
        />
        {roundTiming.raise_in_months != null && (
          <StatBox
            label="Raise Window Opens"
            value={`~${roundTiming.raise_in_months.toFixed(0)} mo`}
            highlight
          />
        )}
      </div>

      {/* Milestone gaps */}
      {roundTiming.milestone_total_count > 0 && (
        <div className="mb-3">
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
              {stageLabel} Milestones
            </p>
            <span className="text-xs text-slate-500">
              {roundTiming.milestone_met_count}/{roundTiming.milestone_total_count} met
            </span>
          </div>

          {/* Progress bar */}
          <div className="h-1.5 bg-slate-700 rounded-full mb-3">
            <div
              className={`h-1.5 rounded-full transition-all ${
                roundTiming.milestone_met_count === roundTiming.milestone_total_count
                  ? 'bg-green-500'
                  : roundTiming.milestone_met_count >= roundTiming.milestone_total_count / 2
                  ? 'bg-amber-500'
                  : 'bg-red-500'
              }`}
              style={{
                width: `${(roundTiming.milestone_met_count / roundTiming.milestone_total_count) * 100}%`,
              }}
            />
          </div>

          {/* Gap list — only show unmet */}
          {roundTiming.milestone_gaps.length > 0 && (
            <div className="space-y-1.5">
              {roundTiming.milestone_gaps.map((gap, i) => (
                <div key={i} className="flex items-start gap-2">
                  <XCircle size={13} className="text-red-400 flex-shrink-0 mt-0.5" />
                  <span className="text-xs text-slate-400">{gap}</span>
                </div>
              ))}
            </div>
          )}

          {roundTiming.milestone_gaps.length === 0 && (
            <div className="flex items-center gap-2">
              <CheckCircle size={13} className="text-green-400" />
              <span className="text-xs text-green-400">All milestones met — strong position for next raise</span>
            </div>
          )}
        </div>
      )}

      {/* Inline warnings */}
      {roundTiming.warnings.length > 0 && (
        <div className="space-y-2 mt-3 pt-3 border-t border-slate-700/50">
          {roundTiming.warnings.map((w, i) => (
            <div key={i} className="flex items-start gap-2">
              <AlertTriangle size={13} className="text-amber-400 flex-shrink-0 mt-0.5" />
              <p className="text-xs text-amber-300 leading-relaxed">{w}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function StatBox({ label, value, warn, highlight }: {
  label: string
  value: string
  warn?: boolean
  highlight?: boolean
}) {
  return (
    <div className="bg-slate-900/40 rounded-lg p-3">
      <p className="text-xs text-slate-500 mb-1">{label}</p>
      <p className={`text-sm font-semibold ${
        warn ? 'text-amber-400' : highlight ? 'text-purple-300' : 'text-slate-200'
      }`}>
        {value}
      </p>
    </div>
  )
}
