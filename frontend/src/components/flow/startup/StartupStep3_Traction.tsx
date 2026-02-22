/**
 * Step 3: Revenue, growth, NRR, burn — the metrics that drive ARR multiple.
 */
import React, { useState } from 'react'
import { ArrowRight, ArrowLeft, Info } from 'lucide-react'
import type { TractionMetrics, ProductProfile, ProductStage } from '../../../types/startup'
import { PRODUCT_STAGE_LABELS } from '../../../types/startup'

interface Step3Props {
  traction: Partial<TractionMetrics>
  product: Partial<ProductProfile>
  onUpdateTraction: (updates: Partial<TractionMetrics>) => void
  onUpdateProduct: (updates: Partial<ProductProfile>) => void
  onNext: () => void
  onBack: () => void
}

const PRODUCT_STAGES = Object.entries(PRODUCT_STAGE_LABELS) as [ProductStage, string][]

function Tooltip({ text }: { text: string }) {
  const [show, setShow] = useState(false)
  return (
    <div className="relative inline-block">
      <Info
        size={13}
        className="text-slate-500 cursor-help"
        onMouseEnter={() => setShow(true)}
        onMouseLeave={() => setShow(false)}
      />
      {show && (
        <div className="absolute z-10 w-56 p-2 text-xs bg-slate-700 border border-slate-600 rounded-lg shadow-xl left-5 top-0">
          {text}
        </div>
      )}
    </div>
  )
}

function NumberInput({
  label,
  value,
  onChange,
  placeholder,
  prefix,
  suffix,
  help,
  step = 0.01,
}: {
  label: string
  value: number
  onChange: (v: number) => void
  placeholder?: string
  prefix?: string
  suffix?: string
  help?: string
  step?: number
}) {
  return (
    <div>
      <div className="flex items-center gap-2 mb-1">
        <label className="text-sm font-medium text-slate-300">{label}</label>
        {help && <Tooltip text={help} />}
      </div>
      <div className="relative">
        {prefix && <span className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400">{prefix}</span>}
        <input
          type="number"
          min={0}
          step={step}
          value={value || ''}
          onChange={e => onChange(parseFloat(e.target.value) || 0)}
          placeholder={placeholder}
          className={`
            w-full bg-slate-900 border border-slate-600 rounded-lg py-3 text-slate-100 placeholder-slate-500
            focus:outline-none focus:ring-2 focus:ring-purple-500 transition-colors
            ${prefix ? 'pl-8' : 'pl-4'} ${suffix ? 'pr-10' : 'pr-4'}
          `}
        />
        {suffix && <span className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400 text-sm">{suffix}</span>}
      </div>
    </div>
  )
}

export default function StartupStep3_Traction({
  traction,
  product,
  onUpdateTraction,
  onUpdateProduct,
  onNext,
  onBack,
}: Step3Props) {
  const hasRevenue = traction.has_revenue ?? false

  return (
    <div className="max-w-2xl mx-auto animate-slide-up">
      <div className="mb-8">
        <h2 className="text-2xl font-bold text-slate-100 mb-2">Traction & product stage</h2>
        <p className="text-slate-400">
          Once you have ARR, the ARR multiple becomes your primary valuation method.
          NRR is the single most powerful driver — above 120% can double your multiple.
        </p>
      </div>

      <div className="space-y-6">
        {/* Product stage */}
        <div className="rounded-xl border border-slate-700 bg-slate-800/30 p-6">
          <label className="block text-sm font-medium text-slate-300 mb-3">Where is your product today?</label>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {PRODUCT_STAGES.map(([s, label]) => (
              <button
                key={s}
                onClick={() => onUpdateProduct({ stage: s })}
                className={`
                  p-3 rounded-lg border text-sm text-left transition-all
                  ${product.stage === s
                    ? 'border-purple-500 bg-purple-900/40 text-purple-200'
                    : 'border-slate-600 text-slate-400 hover:border-slate-500'
                  }
                `}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        {/* Revenue toggle */}
        <div className="rounded-xl border border-slate-700 bg-slate-800/30 p-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <p className="text-sm font-medium text-slate-200">Do you have any revenue?</p>
              <p className="text-xs text-slate-500 mt-0.5">
                Even $1K MRR switches your primary valuation method from pre-revenue to ARR multiple
              </p>
            </div>
            <button
              onClick={() => onUpdateTraction({ has_revenue: !hasRevenue })}
              className={`w-12 h-6 rounded-full transition-colors ${hasRevenue ? 'bg-purple-600' : 'bg-slate-600'}`}
            >
              <div className={`w-5 h-5 rounded-full bg-white shadow transition-transform mx-0.5 ${hasRevenue ? 'translate-x-6' : 'translate-x-0'}`} />
            </button>
          </div>

          {hasRevenue && (
            <div className="space-y-4 pt-4 border-t border-slate-700">
              <div className="grid grid-cols-2 gap-4">
                <NumberInput
                  label="Monthly MRR"
                  value={traction.monthly_recurring_revenue ?? 0}
                  onChange={v => onUpdateTraction({ monthly_recurring_revenue: v, annual_recurring_revenue: v * 12 })}
                  prefix="$"
                  suffix="M"
                  placeholder="0.05"
                  help="Monthly Recurring Revenue in USD millions. $0.05 = $50K MRR."
                />
                <NumberInput
                  label="ARR (auto-fills)"
                  value={traction.annual_recurring_revenue ?? 0}
                  onChange={v => onUpdateTraction({ annual_recurring_revenue: v })}
                  prefix="$"
                  suffix="M"
                  placeholder="0.6"
                  help="Annual Recurring Revenue. Auto-filled from MRR × 12. Override if your ARR differs."
                />
              </div>

              <NumberInput
                label="MoM revenue growth"
                value={(traction.mom_growth_rate ?? 0) * 100}
                onChange={v => onUpdateTraction({ mom_growth_rate: v / 100 })}
                suffix="%"
                placeholder="15"
                step={1}
                help="Month-over-month revenue growth rate. 20%+ is strong at seed; 3x annual is the Series A bar."
              />

              <NumberInput
                label="Net Revenue Retention (NRR)"
                value={(traction.net_revenue_retention ?? 1.0) * 100}
                onChange={v => onUpdateTraction({ net_revenue_retention: v / 100 })}
                suffix="%"
                placeholder="110"
                step={1}
                help="The percentage of revenue retained from existing customers including expansions and churn. Above 120% means expansion outpaces churn. This is the #1 SaaS valuation driver."
              />

              <NumberInput
                label="Gross margin"
                value={(traction.gross_margin ?? 0.7) * 100}
                onChange={v => onUpdateTraction({ gross_margin: v / 100 })}
                suffix="%"
                placeholder="70"
                step={1}
                help="Revenue minus cost of goods sold, divided by revenue. SaaS is typically 60–80%. Below 40% signals unit economics pressure."
              />

              <div className="grid grid-cols-2 gap-4">
                <NumberInput
                  label="Paying customers"
                  value={traction.paying_customer_count ?? 0}
                  onChange={v => onUpdateTraction({ paying_customer_count: Math.round(v) })}
                  placeholder="12"
                  step={1}
                  help="Number of unique paying accounts today."
                />
                <NumberInput
                  label="Enterprise logos"
                  value={traction.logo_customer_count ?? 0}
                  onChange={v => onUpdateTraction({ logo_customer_count: Math.round(v) })}
                  placeholder="3"
                  step={1}
                  help="Named enterprise reference customers — these de-risk the deal significantly for investors."
                />
              </div>
            </div>
          )}
        </div>

        {/* Burn / runway */}
        <div className="rounded-xl border border-slate-700 bg-slate-800/30 p-6 space-y-4">
          <p className="text-sm font-medium text-slate-300">Cash position</p>
          <div className="grid grid-cols-2 gap-4">
            <NumberInput
              label="Monthly burn rate"
              value={traction.monthly_burn_rate ?? 0}
              onChange={v => onUpdateTraction({ monthly_burn_rate: v })}
              prefix="$"
              suffix="M"
              placeholder="0.1"
              help="Net cash burned per month in USD millions. $0.1 = $100K/month burn."
            />
            <NumberInput
              label="Cash on hand"
              value={traction.cash_on_hand ?? 0}
              onChange={v => onUpdateTraction({ cash_on_hand: v })}
              prefix="$"
              suffix="M"
              placeholder="0.5"
              help="Total cash and cash equivalents today in USD millions."
            />
          </div>
          {(traction.monthly_burn_rate ?? 0) > 0 && (traction.cash_on_hand ?? 0) > 0 && (
            <div className={`
              p-3 rounded-lg text-sm
              ${((traction.cash_on_hand ?? 0) / (traction.monthly_burn_rate ?? 1)) >= 18
                ? 'bg-green-900/20 border border-green-700/30 text-green-300'
                : 'bg-amber-900/20 border border-amber-700/30 text-amber-300'
              }
            `}>
              Current runway: {((traction.cash_on_hand ?? 0) / (traction.monthly_burn_rate ?? 1)).toFixed(0)} months
              {((traction.cash_on_hand ?? 0) / (traction.monthly_burn_rate ?? 1)) < 12 && (
                <span className="ml-2 text-xs">— Investors want 18+ months post-close</span>
              )}
            </div>
          )}
        </div>

        {/* LOIs + IP */}
        <div className="rounded-xl border border-slate-700 bg-slate-800/30 p-6 space-y-3">
          <p className="text-sm font-medium text-slate-300 mb-1">Additional signals</p>
          {[
            {
              key: 'has_lois',
              label: 'Signed LOIs or pilot agreements',
              desc: 'Binding Letters of Intent from prospective customers',
              value: traction.has_lois ?? false,
              onChange: (v: boolean) => onUpdateTraction({ has_lois: v }),
            },
            {
              key: 'has_patent_or_ip',
              label: 'Filed or granted patents / trade secrets',
              desc: 'Core IP protection that limits competitor replication',
              value: product.has_patent_or_ip ?? false,
              onChange: (v: boolean) => onUpdateProduct({ has_patent_or_ip: v }),
            },
            {
              key: 'proprietary_data_moat',
              label: 'Proprietary data moat',
              desc: 'Unique training data or network effects that competitors cannot easily acquire',
              value: product.proprietary_data_moat ?? false,
              onChange: (v: boolean) => onUpdateProduct({ proprietary_data_moat: v }),
            },
            {
              key: 'open_source_traction',
              label: 'Open-source traction (1K+ GitHub stars)',
              desc: 'Significant developer community signals product quality for dev tool / infra companies',
              value: product.open_source_traction ?? false,
              onChange: (v: boolean) => onUpdateProduct({ open_source_traction: v }),
            },
          ].map(item => (
            <div
              key={item.key}
              className={`
                flex items-start justify-between p-3 rounded-lg border cursor-pointer transition-all
                ${item.value ? 'border-purple-600 bg-purple-900/20' : 'border-slate-700 hover:border-slate-600'}
              `}
              onClick={() => item.onChange(!item.value)}
            >
              <div className="flex-1 pr-4">
                <p className="text-sm text-slate-200">{item.label}</p>
                <p className="text-xs text-slate-500 mt-0.5">{item.desc}</p>
              </div>
              <div className={`w-10 h-5 rounded-full transition-colors flex-shrink-0 mt-0.5 ${item.value ? 'bg-purple-600' : 'bg-slate-600'}`}>
                <div className={`w-4 h-4 rounded-full bg-white shadow transition-transform mt-0.5 ${item.value ? 'translate-x-5' : 'translate-x-0.5'}`} />
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="mt-8 flex gap-3">
        <button
          onClick={onBack}
          className="px-6 py-4 rounded-xl border border-slate-600 text-slate-300 hover:border-slate-500 transition-all flex items-center gap-2"
        >
          <ArrowLeft size={16} /> Back
        </button>
        <button
          onClick={onNext}
          className="flex-1 flex items-center justify-center gap-2 px-6 py-4 rounded-xl bg-purple-600 hover:bg-purple-500 text-white font-semibold transition-all"
        >
          Continue — Market & Competition <ArrowRight size={18} />
        </button>
      </div>
    </div>
  )
}
