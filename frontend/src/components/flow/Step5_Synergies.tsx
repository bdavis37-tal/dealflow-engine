import React from 'react'
import { ArrowLeft, ArrowRight } from 'lucide-react'
import SynergyCards from '../inputs/SynergyCards'
import type { SynergyAssumptions, SynergyItem, ModelMode } from '../../types/deal'
import CurrencyInput from '../inputs/CurrencyInput'
import GuidedInput from '../inputs/GuidedInput'
import { Plus, Trash2 } from 'lucide-react'

interface Step5Props {
  synergies: SynergyAssumptions
  combinedRevenue: number
  mode: ModelMode
  onUpdate: (updates: Partial<SynergyAssumptions>) => void
  onNext: () => void
  onBack: () => void
}

export default function Step5_Synergies({ synergies, combinedRevenue, mode, onUpdate, onNext, onBack }: Step5Props) {
  const allItems = [...synergies.cost_synergies, ...synergies.revenue_synergies]

  const handleCardsChange = (items: SynergyItem[]) => {
    const cost = items.filter(i => !i.is_revenue)
    const revenue = items.filter(i => i.is_revenue)
    onUpdate({ cost_synergies: cost, revenue_synergies: revenue })
  }

  const addCustomCostSynergy = () => {
    const newItem: SynergyItem = {
      category: `Custom ${synergies.cost_synergies.length + 1}`,
      annual_amount: 500_000,
      phase_in_years: 3,
      cost_to_achieve: 0,
      is_revenue: false,
    }
    onUpdate({ cost_synergies: [...synergies.cost_synergies, newItem] })
  }

  const updateCostSynergy = (idx: number, updates: Partial<SynergyItem>) => {
    const updated = synergies.cost_synergies.map((s, i) => i === idx ? { ...s, ...updates } : s)
    onUpdate({ cost_synergies: updated })
  }

  const removeCostSynergy = (idx: number) => {
    onUpdate({ cost_synergies: synergies.cost_synergies.filter((_, i) => i !== idx) })
  }

  const totalAnnual = allItems.reduce((sum, s) => sum + s.annual_amount, 0)

  return (
    <div className="max-w-2xl mx-auto animate-slide-up">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-100 mb-2">
          What do you expect to gain from this acquisition?
        </h1>
        <p className="text-slate-400">
          Select the ways combining these companies will save money or grow revenue.
          We'll estimate the dollar value — you can adjust it.
        </p>
      </div>

      {mode === 'quick' ? (
        <div className="space-y-4">
          <SynergyCards
            combinedRevenue={combinedRevenue}
            selected={allItems}
            onChange={handleCardsChange}
          />
          {allItems.length === 0 && (
            <div className="rounded-xl border border-dashed border-slate-700 p-6 text-center text-slate-500 text-sm">
              Select at least one category above, or skip to model a no-synergy deal.
            </div>
          )}
        </div>
      ) : (
        /* Deep model: custom line items */
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-blue-400 uppercase tracking-wider">Cost Synergies</h2>
            <button onClick={addCustomCostSynergy} className="flex items-center gap-1.5 text-xs text-blue-400 hover:text-blue-300 border border-blue-800 rounded-lg px-3 py-1.5">
              <Plus size={13} /> Add Line Item
            </button>
          </div>

          {synergies.cost_synergies.map((syn, idx) => (
            <div key={idx} className="rounded-xl border border-slate-700 bg-slate-800/20 p-4 space-y-3">
              <div className="flex items-center gap-3">
                <GuidedInput label="Description" value={syn.category} onChange={v => updateCostSynergy(idx, { category: v })} placeholder="e.g. Back-office consolidation" />
                <button onClick={() => removeCostSynergy(idx)} className="text-slate-500 hover:text-red-400 mt-6 flex-shrink-0">
                  <Trash2 size={15} />
                </button>
              </div>
              <div className="grid grid-cols-3 gap-3">
                <CurrencyInput label="Annual Run-Rate" value={syn.annual_amount} onChange={v => updateCostSynergy(idx, { annual_amount: v })} />
                <GuidedInput label="Phase-In (years)" value={syn.phase_in_years} onChange={v => updateCostSynergy(idx, { phase_in_years: Number(v) })} type="number" min={1} max={7} help="Years to reach full annual run-rate." />
                <CurrencyInput label="Cost to Achieve" value={syn.cost_to_achieve} onChange={v => updateCostSynergy(idx, { cost_to_achieve: v })} help="One-time integration costs for this synergy." />
              </div>
            </div>
          ))}

          {synergies.cost_synergies.length === 0 && (
            <div className="rounded-xl border border-dashed border-slate-700 p-5 text-center text-slate-500 text-sm">
              No cost synergies added. Click "Add Line Item" or leave empty for no synergies.
            </div>
          )}
        </div>
      )}

      {/* Summary */}
      {totalAnnual > 0 && (
        <div className="mt-6 rounded-xl border border-green-900/40 bg-green-950/10 px-5 py-4 text-sm">
          <span className="text-slate-400">Total projected annual savings: </span>
          <span className="text-green-400 font-semibold tabular-nums">
            ${(totalAnnual / 1_000_000).toFixed(1)}M/year
          </span>
          <span className="text-slate-500 text-xs ml-2">at full run-rate</span>
        </div>
      )}

      <div className="flex gap-3 mt-8">
        <button onClick={onBack} className="flex items-center gap-2 px-5 py-3 rounded-xl border border-slate-700 text-slate-300 hover:border-slate-600 text-sm transition-all">
          <ArrowLeft size={16} /> Back
        </button>
        <button onClick={onNext} className="flex-1 flex items-center justify-center gap-2 px-6 py-3 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-semibold text-sm transition-all">
          Review & Generate Analysis <ArrowRight size={16} />
        </button>
      </div>
    </div>
  )
}
