import type { ModelMode } from '../../types/deal'

interface ModeToggleProps {
  mode: ModelMode
  onChange: (mode: ModelMode) => void
}

export default function ModeToggle({ mode, onChange }: ModeToggleProps) {
  return (
    <div className="flex items-center gap-1 bg-slate-800/60 rounded-lg p-0.5 border border-slate-700/50">
      <button
        onClick={() => onChange('quick')}
        className={`
          px-3 py-1 rounded-md text-xs font-medium transition-all
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
        className={`
          px-3 py-1 rounded-md text-xs font-medium transition-all
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
