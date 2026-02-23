import { useState } from 'react'
import { ArrowRight } from 'lucide-react'
import GuidedInput from '../inputs/GuidedInput'
import CurrencyInput from '../inputs/CurrencyInput'
import type { AcquirerProfile, TargetProfile } from '../../types/deal'

interface Step1Props {
  acquirer: Partial<AcquirerProfile>
  target: Partial<TargetProfile>
  onUpdateAcquirer: (updates: Partial<AcquirerProfile>) => void
  onUpdateTarget: (updates: Partial<TargetProfile>) => void
  onNext: () => void
}

export default function Step1_DealOverview({
  acquirer,
  target,
  onUpdateAcquirer,
  onUpdateTarget,
  onNext,
}: Step1Props) {
  const [errors, setErrors] = useState<Record<string, string>>({})

  const validate = () => {
    const errs: Record<string, string> = {}
    if (!acquirer.company_name?.trim()) errs.acq_name = 'Enter the buyer\'s name (e.g. "Acme Corp")'
    if (!target.company_name?.trim()) errs.tgt_name = 'Enter the target company name or a brief description'
    if (!target.acquisition_price || target.acquisition_price <= 0) errs.price = 'Enter the total purchase price in millions (e.g. 50 for $50M)'
    setErrors(errs)
    return Object.keys(errs).length === 0
  }

  const handleNext = () => {
    if (validate()) onNext()
  }

  return (
    <div className="max-w-2xl mx-auto animate-slide-up">
      <div className="mb-10">
        <h1 className="text-3xl font-bold text-slate-100 mb-3">
          Let's model your deal.
        </h1>
        <p className="text-slate-400 text-lg">
          Tell us about the companies involved. Don't worry about being precise yet —
          we'll ask for more detail in the next steps.
        </p>
      </div>

      <div className="space-y-8">
        {/* Acquirer */}
        <div className="rounded-xl border border-slate-700 bg-slate-800/30 p-6 space-y-4">
          <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">
            The Buyer (Your Company)
          </h2>
          <GuidedInput
            label="Company name"
            value={acquirer.company_name ?? ''}
            onChange={v => onUpdateAcquirer({ company_name: v })}
            placeholder="e.g. Acme Corp"
            help="The company making the acquisition."
            error={errors.acq_name}
            required
          />
        </div>

        {/* Target */}
        <div className="rounded-xl border border-slate-700 bg-slate-800/30 p-6 space-y-4">
          <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">
            The Target (Company You're Buying)
          </h2>
          <GuidedInput
            label="Company name or description"
            value={target.company_name ?? ''}
            onChange={v => onUpdateTarget({ company_name: v })}
            placeholder="e.g. 'Beta LLC' or 'a $30M HVAC company in Texas'"
            help="The company you're acquiring. Can be a name or a description."
            error={errors.tgt_name}
            required
          />
          <CurrencyInput
            label="Approximate deal size (total price)"
            value={target.acquisition_price ?? 0}
            onChange={v => onUpdateTarget({ acquisition_price: v })}
            placeholder="$50,000,000"
            help="The total amount to acquire the target, including any debt they carry. This is the full 'price tag' on the business — not just equity. A rough estimate is fine for now."
            error={errors.price}
            required
          />

          {/* AI-Native Toggle */}
          {(() => {
            const defenseLockedOn = target.defense_profile?.is_ai_native === true
            const isOn = defenseLockedOn || (target.is_ai_native ?? false)

            return (
              <div className="flex items-center justify-between pt-2 border-t border-slate-700">
                <div>
                  <span className="text-sm font-medium text-slate-300">AI-Native Company</span>
                  <p className="text-xs text-slate-500 mt-0.5">
                    {defenseLockedOn
                      ? 'Locked — defense profile already flagged as AI-native.'
                      : 'Enable to benchmark against AI-native peer multiples.'}
                  </p>
                </div>
                <div className="relative group">
                  <button
                    type="button"
                    role="switch"
                    aria-checked={isOn}
                    disabled={defenseLockedOn}
                    onClick={() => onUpdateTarget({ is_ai_native: !isOn })}
                    className={`
                      relative inline-flex h-6 w-11 items-center rounded-full transition-colors
                      ${isOn ? 'bg-blue-600' : 'bg-slate-600'}
                      ${defenseLockedOn ? 'opacity-70 cursor-not-allowed' : 'cursor-pointer'}
                    `}
                  >
                    <span className={`
                      inline-block h-4 w-4 rounded-full bg-white transition-transform
                      ${isOn ? 'translate-x-6' : 'translate-x-1'}
                    `} />
                  </button>
                  {defenseLockedOn && (
                    <span className="absolute bottom-full right-0 mb-2 px-2 py-1 text-xs text-slate-300 bg-slate-700 rounded shadow-lg whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
                      Defense profile is already flagged as AI-native
                    </span>
                  )}
                </div>
              </div>
            )
          })()}
        </div>
      </div>

      <div className="mt-8">
        <button
          onClick={handleNext}
          className="
            w-full flex items-center justify-center gap-2 px-6 py-4 rounded-xl
            bg-blue-600 hover:bg-blue-500 text-white font-semibold text-base
            transition-all shadow-lg shadow-blue-900/30
          "
        >
          Let's Model This Deal
          <ArrowRight size={18} />
        </button>
        <p className="text-center text-xs text-slate-500 mt-3">
          Your data stays in your browser. Nothing is stored on our servers.
        </p>
      </div>
    </div>
  )
}
