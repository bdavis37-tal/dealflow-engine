import type { FlowStep } from '../../types/deal'

const STEPS: Array<{ label: string; short: string }> = [
  { label: 'Deal Overview', short: 'Overview' },
  { label: "Buyer's Profile", short: 'Buyer' },
  { label: "Target's Profile", short: 'Target' },
  { label: 'Financing', short: 'Financing' },
  { label: 'Expected Benefits', short: 'Benefits' },
  { label: 'Review & Analyze', short: 'Analyze' },
]

interface StepIndicatorProps {
  currentStep: FlowStep
}

export default function StepIndicator({ currentStep }: StepIndicatorProps) {
  return (
    <div className="flex items-center gap-1">
      {STEPS.map((step, idx) => {
        const stepNum = (idx + 1) as FlowStep
        const isCompleted = currentStep > stepNum
        const isCurrent = currentStep === stepNum

        return (
          <div key={stepNum} className="flex items-center gap-1 flex-1">
            <div className="flex items-center gap-1.5 min-w-0">
              {/* Step dot */}
              <div
                className={`
                  w-5 h-5 rounded-full flex items-center justify-center text-2xs font-semibold flex-shrink-0 transition-all
                  ${isCompleted ? 'bg-blue-600 text-white' : ''}
                  ${isCurrent ? 'bg-blue-500 text-white ring-2 ring-blue-400/30' : ''}
                  ${!isCompleted && !isCurrent ? 'bg-slate-700 text-slate-400' : ''}
                `}
              >
                {isCompleted ? '✓' : stepNum}
              </div>
              {/* Label — hidden on small screens */}
              <span
                className={`
                  text-xs hidden sm:block truncate transition-colors
                  ${isCurrent ? 'text-slate-100 font-medium' : ''}
                  ${isCompleted ? 'text-blue-400' : ''}
                  ${!isCompleted && !isCurrent ? 'text-slate-500' : ''}
                `}
              >
                {step.short}
              </span>
            </div>

            {/* Connector line */}
            {idx < STEPS.length - 1 && (
              <div
                className={`h-px flex-1 mx-1 transition-colors ${isCompleted ? 'bg-blue-600' : 'bg-slate-700'}`}
              />
            )}
          </div>
        )
      })}
    </div>
  )
}
