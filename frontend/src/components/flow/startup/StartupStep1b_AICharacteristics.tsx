/**
 * AI Characteristics Assessment — four yes/no questions that produce
 * an ai_native_score in [0.0, 1.0].  Shown when the AI toggle is ON
 * and the vertical is not frozen_on.
 *
 * Pure presentational component — parent owns state and score computation.
 */


// ── Props ──────────────────────────────────────────────────────────────────

interface AICharacteristicsProps {
  answers: [boolean, boolean, boolean, boolean]
  onAnswerChange: (index: number, value: boolean) => void
  ai_native_score: number
}

// ── Questions ──────────────────────────────────────────────────────────────

const AI_QUESTIONS = [
  'AI/ML is the core product, not a feature — the company would not exist without its AI capabilities',
  'The company has proprietary training data or models that create a defensible moat',
  'R&D spending is above 25% of revenue, primarily on AI/ML research',
  'The product improves with usage — there is a data flywheel or network effect driven by AI',
] as const

// ── Score → label helpers ──────────────────────────────────────────────────

function getScoreLabel(score: number): string {
  if (score >= 0.75) return 'Strongly AI-Native'
  if (score === 0.5) return 'Moderately AI-Native'
  if (score === 0.25) return 'Marginally AI-Native'
  return 'Not AI-Native'
}

function getScoreColor(score: number): string {
  if (score >= 0.75) return 'text-purple-300'
  if (score === 0.5) return 'text-purple-400'
  if (score === 0.25) return 'text-amber-400'
  return 'text-slate-500'
}

// ── Component ──────────────────────────────────────────────────────────────

export default function StartupStep1b_AICharacteristics({
  answers,
  onAnswerChange,
  ai_native_score,
}: AICharacteristicsProps) {
  const yesCount = answers.filter(Boolean).length

  return (
    <div className="rounded-xl border border-slate-700 bg-slate-800/30 p-6 animate-slide-up">
      <p className="text-sm font-medium text-slate-300 mb-1">
        AI Characteristics Assessment
      </p>
      <p className="text-xs text-slate-500 mb-5">
        Answer four questions to calibrate the AI-native premium. More "yes" answers
        mean a higher premium multiplier.
      </p>

      <div className="space-y-3">
        {AI_QUESTIONS.map((question, idx) => (
          <div
            key={idx}
            className={`
              flex items-start justify-between gap-4 p-4 rounded-lg border transition-all
              ${answers[idx]
                ? 'border-purple-600 bg-purple-900/20'
                : 'border-slate-700 bg-slate-800/20'}
            `}
          >
            <p className="text-sm text-slate-200 flex-1 leading-relaxed">
              {question}
            </p>

            {/* Yes / No toggle pair */}
            <div className="flex gap-1 flex-shrink-0" role="group" aria-label={`Toggle for question ${idx + 1}`}>
              <button
                type="button"
                onClick={() => onAnswerChange(idx, true)}
                aria-pressed={answers[idx]}
                className={`
                  px-3 py-1.5 rounded-l-lg text-xs font-semibold transition-all border
                  ${answers[idx]
                    ? 'bg-purple-600 border-purple-500 text-white'
                    : 'bg-slate-800 border-slate-600 text-slate-400 hover:border-slate-500'}
                `}
              >
                Yes
              </button>
              <button
                type="button"
                onClick={() => onAnswerChange(idx, false)}
                aria-pressed={!answers[idx]}
                className={`
                  px-3 py-1.5 rounded-r-lg text-xs font-semibold transition-all border
                  ${!answers[idx]
                    ? 'bg-purple-900/40 border-purple-700 text-purple-300'
                    : 'bg-slate-800 border-slate-600 text-slate-400 hover:border-slate-500'}
                `}
              >
                No
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Score summary */}
      <div className="mt-5 flex items-center gap-3 pt-4 border-t border-slate-700">
        <span className="text-sm text-slate-400">AI-Native Score:</span>
        <span className={`text-lg font-bold ${getScoreColor(ai_native_score)}`}>
          {yesCount} / 4
        </span>
        <span className="text-sm text-slate-500">—</span>
        <span className={`text-sm font-medium ${getScoreColor(ai_native_score)}`}>
          {getScoreLabel(ai_native_score)}
        </span>
      </div>
    </div>
  )
}
