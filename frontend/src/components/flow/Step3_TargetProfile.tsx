import React, { useState } from 'react'
import { ArrowLeft, ArrowRight, ChevronDown, ChevronUp } from 'lucide-react'
import CurrencyInput from '../inputs/CurrencyInput'
import GuidedInput from '../inputs/GuidedInput'
import type { TargetProfile, Industry, ModelMode } from '../../types/deal'

const INDUSTRIES: Industry[] = [
  'Software / SaaS', 'Healthcare Services', 'Manufacturing',
  'Professional Services / Consulting', 'HVAC / Mechanical Contracting',
  'Construction', 'Restaurants / Food Service', 'Retail',
  'Financial Services', 'Oil & Gas Services', 'Transportation / Logistics',
  'Real Estate Services', 'Technology Hardware', 'Pharmaceuticals',
  'Telecommunications', 'Agriculture', 'Media / Entertainment',
  'Insurance', 'Staffing / Recruiting', 'Waste Management',
]

interface Step3Props {
  target: Partial<TargetProfile>
  mode: ModelMode
  onUpdate: (updates: Partial<TargetProfile>) => void
  onNext: () => void
  onBack: () => void
}

export default function Step3_TargetProfile({ target, mode, onUpdate, onNext, onBack }: Step3Props) {
  const [showAssumptions, setShowAssumptions] = useState(false)
  const [errors, setErrors] = useState<Record<string, string>>({})

  const validate = () => {
    const errs: Record<string, string> = {}
    if (!target.revenue || target.revenue <= 0) errs.revenue = 'Required'
    if (target.ebitda === undefined) errs.ebitda = 'Required'
    if (!target.industry) errs.industry = 'Required'
    setErrors(errs)
    return Object.keys(errs).length === 0
  }

  const handleRevenueChange = (v: number) => {
    const updates: Partial<TargetProfile> = { revenue: v }
    // Auto-estimate fields from revenue if in quick mode
    if (mode === 'quick' && v > 0) {
      if (!target.ebitda) updates.ebitda = Math.round(v * 0.12)
      if (!target.net_income) updates.net_income = Math.round(v * 0.07)
      if (!target.depreciation) updates.depreciation = Math.round(v * 0.04)
      if (!target.capex) updates.capex = Math.round(v * 0.03)
      if (!target.working_capital) updates.working_capital = Math.round(v * 0.10)
    }
    onUpdate(updates)
  }

  return (
    <div className="max-w-2xl mx-auto animate-slide-up">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-100 mb-2">
          Tell us about the company you're buying.
        </h1>
        <p className="text-slate-400">
          {mode === 'quick'
            ? "Revenue and profitability are the key inputs. We'll estimate the rest from industry benchmarks."
            : 'Enter the target\'s full financial profile for the most accurate model.'
          }
        </p>
      </div>

      <div className="space-y-6">
        <div className="space-y-1.5">
          <label className="text-sm font-medium text-slate-300">Industry *</label>
          <select
            value={target.industry ?? ''}
            onChange={e => onUpdate({ industry: e.target.value as Industry })}
            className="w-full bg-slate-800/40 border border-slate-700 rounded-lg px-3 py-2.5 text-sm text-slate-100 outline-none focus:border-blue-500/60 transition-colors"
          >
            <option value="">Select target's industry...</option>
            {INDUSTRIES.map(ind => <option key={ind} value={ind}>{ind}</option>)}
          </select>
          {errors.industry && <p className="text-xs text-red-400">{errors.industry}</p>}
        </div>

        <div className="rounded-xl border border-slate-700 bg-slate-800/20 p-5 space-y-4">
          <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Financials</h3>
          <CurrencyInput
            label="Annual Revenue"
            value={target.revenue ?? 0}
            onChange={handleRevenueChange}
            help="The target's total annual sales."
            error={errors.revenue}
            required
          />
          <CurrencyInput
            label="Annual EBITDA"
            value={target.ebitda ?? 0}
            onChange={v => onUpdate({ ebitda: v })}
            help="Operating profit before interest, taxes, and accounting adjustments."
            error={errors.ebitda}
            required
          />
          <CurrencyInput
            label="Annual Net Income"
            value={target.net_income ?? 0}
            onChange={v => onUpdate({ net_income: v })}
            help="After-tax profit."
          />
        </div>

        {/* Assumptions panel for Quick Model */}
        {mode === 'quick' && (
          <div className="rounded-xl border border-slate-700/50 bg-slate-800/10 overflow-hidden">
            <button
              onClick={() => setShowAssumptions(v => !v)}
              className="w-full flex items-center justify-between px-5 py-3 text-sm text-slate-400 hover:text-slate-300 transition-colors"
            >
              <span>Our assumptions (auto-calculated from your inputs)</span>
              {showAssumptions ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
            </button>
            {showAssumptions && (
              <div className="px-5 pb-5 space-y-4 border-t border-slate-700/50 pt-4 animate-fade-in">
                <p className="text-xs text-slate-500">These are estimated from industry benchmarks. Switch to Deep Model to customize them.</p>
                <div className="grid grid-cols-2 gap-4">
                  <div className="text-xs text-slate-400">
                    <span className="text-slate-500">Revenue growth rate</span>
                    <div className="text-slate-200 font-medium tabular-nums">5% / year</div>
                  </div>
                  <div className="text-xs text-slate-400">
                    <span className="text-slate-500">Tax rate</span>
                    <div className="text-slate-200 font-medium tabular-nums">25%</div>
                  </div>
                  <div className="text-xs text-slate-400">
                    <span className="text-slate-500">D&A</span>
                    <div className="text-slate-200 font-medium tabular-nums">4% of revenue</div>
                  </div>
                  <div className="text-xs text-slate-400">
                    <span className="text-slate-500">CapEx</span>
                    <div className="text-slate-200 font-medium tabular-nums">3% of revenue</div>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Deep model extras */}
        {mode === 'deep' && (
          <div className="rounded-xl border border-blue-900/40 bg-blue-950/10 p-5 space-y-4">
            <h3 className="text-xs font-semibold text-blue-400 uppercase tracking-wider">Deep Model — Additional Inputs</h3>
            <div className="grid grid-cols-2 gap-4">
              <CurrencyInput label="Total Debt" value={target.total_debt ?? 0} onChange={v => onUpdate({ total_debt: v })} help="Debt assumed or refinanced at close." />
              <CurrencyInput label="Cash Acquired" value={target.cash_on_hand ?? 0} onChange={v => onUpdate({ cash_on_hand: v })} help="Cash acquired with the business." />
              <CurrencyInput label="D&A" value={target.depreciation ?? 0} onChange={v => onUpdate({ depreciation: v })} />
              <CurrencyInput label="CapEx" value={target.capex ?? 0} onChange={v => onUpdate({ capex: v })} />
              <CurrencyInput label="Net Working Capital" value={target.working_capital ?? 0} onChange={v => onUpdate({ working_capital: v })} />
            </div>
            <GuidedInput
              label="Annual Revenue Growth Rate"
              value={target.revenue_growth_rate ? (target.revenue_growth_rate * 100).toFixed(1) : '5.0'}
              onChange={v => onUpdate({ revenue_growth_rate: Number(v) / 100 })}
              type="number" suffix="%" min={-20} max={100}
              help="Expected annual revenue growth over the 5-year projection period."
            />
          </div>
        )}
      </div>

      <div className="flex gap-3 mt-8">
        <button onClick={onBack} className="flex items-center gap-2 px-5 py-3 rounded-xl border border-slate-700 text-slate-300 hover:border-slate-600 text-sm transition-all">
          <ArrowLeft size={16} /> Back
        </button>
        <button onClick={() => validate() && onNext()} className="flex-1 flex items-center justify-center gap-2 px-6 py-3 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-semibold text-sm transition-all">
          Continue <ArrowRight size={16} />
        </button>
      </div>
    </div>
  )
}
