import type { ModelMode } from '../../types/deal'

interface ModelDepthToggleProps {
  mode: ModelMode
  onChange: (mode: ModelMode) => void
}

export default function ModelDepthToggle({ mode, onChange }: ModelDepthToggleProps) {
  return (
    <div className="flex items-center gap-1 bg-slate-800/60 rounded-lg p-0.5 border border-slate-700/50" role="group" aria-label="Analysis depth">
      <button
        onClick={() => onChange('quick')}
        aria-pressed={mode === 'quick'}
        aria-label="Quick analysis model"
        className={`
          px-3 py-1.5 rounded-md text-xs font-medium transition-all
          focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-1 focus-visible:ring-offset-slate-900
          ${mode === 'quick'
            ? 'bg-blue-600 text-white shadow-sm'
            : 'text-slate-400 hover:text-slate-200'
          }
        `}
      >
        Quick Model
      </button>
      <button
        onClick={() => onChange('deep')}
        aria-pressed={mode === 'deep'}
        aria-label="Deep analysis model with full sensitivity"
        className={`
          px-3 py-1.5 rounded-md text-xs font-medium transition-all
          focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-1 focus-visible:ring-offset-slate-900
          ${mode === 'deep'
            ? 'bg-blue-600 text-white shadow-sm'
            : 'text-slate-400 hover:text-slate-200'
          }
        `}
      >
        Deep Model
      </button>
    </div>
  )
}
