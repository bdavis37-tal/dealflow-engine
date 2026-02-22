import React, { useState } from 'react'
import { ArrowLeft, ArrowRight } from 'lucide-react'
import CurrencyInput from '../inputs/CurrencyInput'
import GuidedInput from '../inputs/GuidedInput'
import type { AcquirerProfile, Industry, ModelMode } from '../../types/deal'

const INDUSTRIES: Industry[] = [
  'Software / SaaS', 'Healthcare Services', 'Manufacturing',
  'Professional Services / Consulting', 'HVAC / Mechanical Contracting',
  'Construction', 'Restaurants / Food Service', 'Retail',
  'Financial Services', 'Oil & Gas Services', 'Transportation / Logistics',
  'Real Estate Services', 'Technology Hardware', 'Pharmaceuticals',
  'Telecommunications', 'Agriculture', 'Media / Entertainment',
  'Insurance', 'Staffing / Recruiting', 'Waste Management',
]

interface Step2Props {
  acquirer: Partial<AcquirerProfile>
  mode: ModelMode
  onUpdate: (updates: Partial<AcquirerProfile>) => void
  onNext: () => void
  onBack: () => void
}

export default function Step2_BuyerProfile({ acquirer, mode, onUpdate, onNext, onBack }: Step2Props) {
  const [errors, setErrors] = useState<Record<string, string>>({})

  const validate = () => {
    const errs: Record<string, string> = {}
    if (!acquirer.revenue || acquirer.revenue <= 0) errs.revenue = 'Required'
    if (acquirer.ebitda === undefined) errs.ebitda = 'Required'
    if (!acquirer.shares_outstanding || acquirer.shares_outstanding <= 0) errs.shares = 'Required'
    if (!acquirer.share_price || acquirer.share_price <= 0) errs.price = 'Required'
    if (!acquirer.industry) errs.industry = 'Required'
    setErrors(errs)
    return Object.keys(errs).length === 0
  }

  // Auto-estimate EBITDA if revenue is entered
  const handleRevenueChange = (v: number) => {
    onUpdate({ revenue: v })
    if (!acquirer.ebitda && v > 0 && acquirer.industry) {
      // Rough default: 15% EBITDA margin
      onUpdate({ revenue: v, ebitda: Math.round(v * 0.15) })
    }
  }

  return (
    <div className="max-w-2xl mx-auto animate-slide-up">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-100 mb-2">
          Tell us about your company.
        </h1>
        <p className="text-slate-400">
          These numbers power the deal math. If you're not sure about some inputs,
          we'll apply industry estimates — you can refine them later.
        </p>
      </div>

      <div className="space-y-6">
        {/* Industry */}
        <div className="space-y-1.5">
          <label className="text-sm font-medium text-slate-300">Industry *</label>
          <select
            value={acquirer.industry ?? ''}
            onChange={e => onUpdate({ industry: e.target.value as Industry })}
            className="
              w-full bg-slate-800/40 border border-slate-700 rounded-lg px-3 py-2.5
              text-sm text-slate-100 outline-none focus:border-blue-500/60 transition-colors
            "
          >
            <option value="">Select your industry...</option>
            {INDUSTRIES.map(ind => (
              <option key={ind} value={ind}>{ind}</option>
            ))}
          </select>
          {errors.industry && <p className="text-xs text-red-400">{errors.industry}</p>}
        </div>

        {/* Revenue + EBITDA cluster */}
        <div className="rounded-xl border border-slate-700 bg-slate-800/20 p-5 space-y-4">
          <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Revenue & Profitability</h3>
          <CurrencyInput
            label="Annual Revenue"
            value={acquirer.revenue ?? 0}
            onChange={handleRevenueChange}
            help="Your company's total annual sales."
            error={errors.revenue}
            required
          />
          <CurrencyInput
            label="Annual EBITDA"
            value={acquirer.ebitda ?? 0}
            onChange={v => onUpdate({ ebitda: v })}
            help="Earnings Before Interest, Taxes, Depreciation & Amortization. Your operating profit before accounting adjustments. If unsure, use 15% of revenue as a starting point."
            error={errors.ebitda}
            required
          />
          <CurrencyInput
            label="Net Income (after-tax profit)"
            value={acquirer.net_income ?? 0}
            onChange={v => onUpdate({ net_income: v })}
            help="Your annual profit after all expenses and taxes."
          />
        </div>

        {/* Balance sheet */}
        <div className="rounded-xl border border-slate-700 bg-slate-800/20 p-5 space-y-4">
          <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Balance Sheet</h3>
          <div className="grid grid-cols-2 gap-4">
            <CurrencyInput
              label="Total Debt"
              value={acquirer.total_debt ?? 0}
              onChange={v => onUpdate({ total_debt: v })}
              help="All outstanding loans and bonds."
            />
            <CurrencyInput
              label="Cash on Hand"
              value={acquirer.cash_on_hand ?? 0}
              onChange={v => onUpdate({ cash_on_hand: v })}
              help="Cash and liquid investments available."
            />
          </div>
        </div>

        {/* Stock info */}
        <div className="rounded-xl border border-slate-700 bg-slate-800/20 p-5 space-y-4">
          <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Stock Information</h3>
          <div className="grid grid-cols-2 gap-4">
            <GuidedInput
              label="Shares Outstanding"
              value={acquirer.shares_outstanding ?? ''}
              onChange={v => onUpdate({ shares_outstanding: Number(v) })}
              type="number"
              placeholder="10,000,000"
              help="Total diluted shares outstanding."
              error={errors.shares}
              required
            />
            <GuidedInput
              label="Share Price"
              value={acquirer.share_price ?? ''}
              onChange={v => onUpdate({ share_price: Number(v) })}
              type="number"
              prefix="$"
              placeholder="25.00"
              help="Current stock price."
              error={errors.price}
              required
            />
          </div>
        </div>

        {/* Deep model extras */}
        {mode === 'deep' && (
          <div className="rounded-xl border border-blue-900/40 bg-blue-950/10 p-5 space-y-4">
            <h3 className="text-xs font-semibold text-blue-400 uppercase tracking-wider">Deep Model — Additional Inputs</h3>
            <div className="grid grid-cols-3 gap-4">
              <CurrencyInput label="Depreciation & Amortization" value={acquirer.depreciation ?? 0} onChange={v => onUpdate({ depreciation: v })} />
              <CurrencyInput label="Capital Expenditures" value={acquirer.capex ?? 0} onChange={v => onUpdate({ capex: v })} />
              <CurrencyInput label="Net Working Capital" value={acquirer.working_capital ?? 0} onChange={v => onUpdate({ working_capital: v })} />
            </div>
            <GuidedInput
              label="Tax Rate"
              value={acquirer.tax_rate ? (acquirer.tax_rate * 100).toFixed(1) : '25.0'}
              onChange={v => onUpdate({ tax_rate: Number(v) / 100 })}
              type="number"
              suffix="%"
              help="Effective combined tax rate."
              min={0}
              max={60}
            />
          </div>
        )}
      </div>

      <div className="flex gap-3 mt-8">
        <button
          onClick={onBack}
          className="flex items-center gap-2 px-5 py-3 rounded-xl border border-slate-700 text-slate-300 hover:border-slate-600 hover:text-slate-100 text-sm transition-all"
        >
          <ArrowLeft size={16} /> Back
        </button>
        <button
          onClick={() => validate() && onNext()}
          className="flex-1 flex items-center justify-center gap-2 px-6 py-3 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-semibold text-sm transition-all"
        >
          Continue <ArrowRight size={16} />
        </button>
      </div>
    </div>
  )
}
