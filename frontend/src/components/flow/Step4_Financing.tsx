import React from 'react'
import { ArrowLeft, ArrowRight, Plus, Trash2 } from 'lucide-react'
import FinancingSlider from '../inputs/FinancingSlider'
import type { DealStructure, DebtTranche, AmortizationType, ModelMode } from '../../types/deal'
import GuidedInput from '../inputs/GuidedInput'
import CurrencyInput from '../inputs/CurrencyInput'

interface Step4Props {
  structure: Partial<DealStructure>
  dealSize: number
  mode: ModelMode
  onUpdate: (updates: Partial<DealStructure>) => void
  onNext: () => void
  onBack: () => void
}

const defaultStructure = (s: Partial<DealStructure>): DealStructure => ({
  cash_percentage: s.cash_percentage ?? 1.0,
  stock_percentage: s.stock_percentage ?? 0.0,
  debt_percentage: s.debt_percentage ?? 0.0,
  debt_tranches: s.debt_tranches ?? [],
  transaction_fees_pct: s.transaction_fees_pct ?? 0.02,
  advisory_fees: s.advisory_fees ?? 0,
})

export default function Step4_Financing({ structure, dealSize, mode, onUpdate, onNext, onBack }: Step4Props) {
  const s = defaultStructure(structure)

  const handleSliderChange = (cash: number, stock: number, debt: number) => {
    const newTranches = s.debt_tranches.length > 0
      ? s.debt_tranches
      : debt > 0
        ? [{ name: 'Term Loan', amount: dealSize * (debt / 100), interest_rate: 0.08, term_years: 7, amortization_type: 'straight_line' as AmortizationType }]
        : []
    onUpdate({
      cash_percentage: cash / 100,
      stock_percentage: stock / 100,
      debt_percentage: debt / 100,
      debt_tranches: newTranches,
    })
  }

  const addTranche = () => {
    const remaining = dealSize * s.debt_percentage / Math.max(1, s.debt_tranches.length + 1)
    const newTranche: DebtTranche = {
      name: `Tranche ${s.debt_tranches.length + 1}`,
      amount: remaining,
      interest_rate: 0.08,
      term_years: 7,
      amortization_type: 'straight_line',
    }
    onUpdate({ debt_tranches: [...s.debt_tranches, newTranche] })
  }

  const removeTranche = (idx: number) => {
    onUpdate({ debt_tranches: s.debt_tranches.filter((_, i) => i !== idx) })
  }

  const updateTranche = (idx: number, updates: Partial<DebtTranche>) => {
    const updated = s.debt_tranches.map((t, i) => i === idx ? { ...t, ...updates } : t)
    onUpdate({ debt_tranches: updated })
  }

  const cash = Math.round(s.cash_percentage * 100)
  const stock = Math.round(s.stock_percentage * 100)
  const debt = Math.round(s.debt_percentage * 100)

  return (
    <div className="max-w-2xl mx-auto animate-slide-up">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-100 mb-2">How are you paying?</h1>
        <p className="text-slate-400">Drag the sliders to set how much of the deal price comes from cash, stock, or borrowed money.</p>
      </div>

      <FinancingSlider
        dealSize={dealSize}
        cash={cash}
        stock={stock}
        debt={debt}
        onChange={handleSliderChange}
      />

      {/* Deep model: tranche configuration */}
      {mode === 'deep' && s.debt_percentage > 0 && (
        <div className="mt-8 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-blue-400 uppercase tracking-wider">Debt Tranche Configuration</h2>
            <button onClick={addTranche} className="flex items-center gap-1.5 text-xs text-blue-400 hover:text-blue-300 border border-blue-800 rounded-lg px-3 py-1.5 transition-colors">
              <Plus size={13} /> Add Tranche
            </button>
          </div>

          {s.debt_tranches.map((tranche, idx) => (
            <div key={idx} className="rounded-xl border border-slate-700 bg-slate-800/20 p-4 space-y-4">
              <div className="flex items-center justify-between">
                <GuidedInput label="Tranche Name" value={tranche.name} onChange={v => updateTranche(idx, { name: v })} placeholder="e.g. Term Loan A" />
                <button onClick={() => removeTranche(idx)} className="ml-3 text-slate-500 hover:text-red-400 transition-colors mt-6">
                  <Trash2 size={15} />
                </button>
              </div>
              <div className="grid grid-cols-3 gap-3">
                <CurrencyInput label="Amount" value={tranche.amount} onChange={v => updateTranche(idx, { amount: v })} />
                <GuidedInput label="Interest Rate" value={(tranche.interest_rate * 100).toFixed(2)} onChange={v => updateTranche(idx, { interest_rate: Number(v) / 100 })} type="number" suffix="%" min={0} max={30} step={0.01} />
                <GuidedInput label="Term (years)" value={tranche.term_years} onChange={v => updateTranche(idx, { term_years: Number(v) })} type="number" min={1} max={30} />
              </div>
              <div className="space-y-1.5">
                <label className="text-sm font-medium text-slate-300">Amortization Type</label>
                <select
                  value={tranche.amortization_type}
                  onChange={e => updateTranche(idx, { amortization_type: e.target.value as AmortizationType })}
                  className="w-full bg-slate-800/40 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 outline-none focus:border-blue-500/60"
                >
                  <option value="straight_line">Straight-Line (equal principal payments)</option>
                  <option value="interest_only">Interest Only (balloon at maturity)</option>
                  <option value="bullet">Bullet (all principal at maturity)</option>
                </select>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Fees */}
      {mode === 'deep' && (
        <div className="mt-6 rounded-xl border border-slate-700 bg-slate-800/20 p-5 space-y-4">
          <h3 className="text-xs font-semibold text-blue-400 uppercase tracking-wider">Transaction Fees</h3>
          <div className="grid grid-cols-2 gap-4">
            <GuidedInput
              label="Diligence & Legal Fees"
              value={(s.transaction_fees_pct * 100).toFixed(2)}
              onChange={v => onUpdate({ transaction_fees_pct: Number(v) / 100 })}
              type="number" suffix="% of deal" min={0} max={10}
              defaultNote="~2% for mid-market deals"
            />
            <CurrencyInput label="Advisory / Bank Fees" value={s.advisory_fees} onChange={v => onUpdate({ advisory_fees: v })} />
          </div>
        </div>
      )}

      <div className="flex gap-3 mt-8">
        <button onClick={onBack} className="flex items-center gap-2 px-5 py-3 rounded-xl border border-slate-700 text-slate-300 hover:border-slate-600 text-sm transition-all">
          <ArrowLeft size={16} /> Back
        </button>
        <button onClick={onNext} className="flex-1 flex items-center justify-center gap-2 px-6 py-3 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-semibold text-sm transition-all">
          Continue <ArrowRight size={16} />
        </button>
      </div>
    </div>
  )
}
