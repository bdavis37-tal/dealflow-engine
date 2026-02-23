type AppMode = 'ma' | 'startup' | 'vc'

interface StepDef {
  label: string
  short: string
}

const MODE_ACCENT: Record<AppMode, {
  completed: string
  current: string
  currentRing: string
  connector: string
  completedText: string
  currentText: string
}> = {
  ma: {
    completed: 'bg-blue-600 text-white',
    current: 'bg-blue-500 text-white',
    currentRing: 'ring-blue-400/30',
    connector: 'bg-blue-600',
    completedText: 'text-blue-400',
    currentText: 'text-slate-100',
  },
  startup: {
    completed: 'bg-purple-600 text-white',
    current: 'bg-purple-500 text-white',
    currentRing: 'ring-purple-400/30',
    connector: 'bg-purple-600',
    completedText: 'text-purple-400',
    currentText: 'text-slate-100',
  },
  vc: {
    completed: 'bg-emerald-600 text-white',
    current: 'bg-emerald-500 text-white',
    currentRing: 'ring-emerald-400/30',
    connector: 'bg-emerald-600',
    completedText: 'text-emerald-400',
    currentText: 'text-slate-100',
  },
}

interface StepIndicatorProps {
  currentStep: number
  steps: StepDef[]
  appMode: AppMode
}

export default function StepIndicator({ currentStep, steps, appMode }: StepIndicatorProps) {
  const accent = MODE_ACCENT[appMode]

  return (
    <div className="flex items-center gap-1">
      {steps.map((step, idx) => {
        const stepNum = idx + 1
        const isCompleted = currentStep > stepNum
        const isCurrent = currentStep === stepNum

        return (
          <div key={stepNum} className="flex items-center gap-1 flex-1">
            <div className="flex items-center gap-1.5 min-w-0">
              {/* Step dot */}
              <div
                className={`
                  w-5 h-5 rounded-full flex items-center justify-center text-2xs font-semibold flex-shrink-0 transition-all duration-300
                  ${isCompleted ? accent.completed : ''}
                  ${isCurrent ? `${accent.current} ring-2 ${accent.currentRing}` : ''}
                  ${!isCompleted && !isCurrent ? 'bg-slate-700 text-slate-400' : ''}
                `}
              >
                {isCompleted ? '✓' : stepNum}
              </div>
              {/* Label — always visible, truncated on mobile */}
              <span
                className={`
                  text-xs truncate transition-colors duration-300 max-w-[48px] sm:max-w-none
                  ${isCurrent ? `${accent.currentText} font-medium` : ''}
                  ${isCompleted ? accent.completedText : ''}
                  ${!isCompleted && !isCurrent ? 'text-slate-500' : ''}
                `}
              >
                {step.short}
              </span>
            </div>

            {/* Connector line */}
            {idx < steps.length - 1 && (
              <div
                className={`h-px flex-1 mx-1 transition-all duration-500 ${isCompleted ? accent.connector : 'bg-slate-700'}`}
              />
            )}
          </div>
        )
      })}
    </div>
  )
}
