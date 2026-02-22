/**
 * Tappable synergy category cards for Quick Model.
 * Each card expands to show estimated dollar amount.
 */
import React, { useState } from 'react'
import type { SynergyItem } from '../../types/deal'
import CurrencyInput from './CurrencyInput'

interface SynergyCategory {
  id: string
  emoji: string
  title: string
  description: string
  estimatedPctRevenue: number  // Default estimate as % of combined revenue
  isRevenue: boolean
}

const SYNERGY_CATEGORIES: SynergyCategory[] = [
  {
    id: 'back_office',
    emoji: '🏢',
    title: 'Combine back-office functions',
    description: 'HR, finance, IT, legal — eliminate duplicate teams and systems.',
    estimatedPctRevenue: 0.025,
    isRevenue: false,
  },
  {
    id: 'procurement',
    emoji: '📦',
    title: 'Better supplier pricing',
    description: 'Combined purchasing power reduces cost of goods sold.',
    estimatedPctRevenue: 0.015,
    isRevenue: false,
  },
  {
    id: 'duplicate_costs',
    emoji: '💰',
    title: 'Eliminate duplicate costs',
    description: 'Offices, software subscriptions, overlapping roles.',
    estimatedPctRevenue: 0.020,
    isRevenue: false,
  },
  {
    id: 'cross_sell',
    emoji: '📈',
    title: "Cross-sell to each other's customers",
    description: 'Offer your products to their customers and vice versa.',
    estimatedPctRevenue: 0.030,
    isRevenue: true,
  },
  {
    id: 'facilities',
    emoji: '🔧',
    title: 'Combine operations or facilities',
    description: 'Consolidate manufacturing, distribution, or service locations.',
    estimatedPctRevenue: 0.018,
    isRevenue: false,
  },
]

interface SynergyCardsProps {
  combinedRevenue: number
  selected: SynergyItem[]
  onChange: (items: SynergyItem[]) => void
}

export default function SynergyCards({ combinedRevenue, selected, onChange }: SynergyCardsProps) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set())

  const isSelected = (id: string) => selected.some(s => s.category === id)

  const getItem = (id: string): SynergyItem | undefined => selected.find(s => s.category === id)

  const toggle = (cat: SynergyCategory) => {
    const exists = isSelected(cat.id)
    if (exists) {
      onChange(selected.filter(s => s.category !== cat.id))
      setExpanded(prev => { const next = new Set(prev); next.delete(cat.id); return next })
    } else {
      const estimate = Math.round(combinedRevenue * cat.estimatedPctRevenue)
      const newItem: SynergyItem = {
        category: cat.id,
        annual_amount: estimate,
        phase_in_years: 3,
        cost_to_achieve: Math.round(estimate * 0.5),
        is_revenue: cat.isRevenue,
      }
      onChange([...selected, newItem])
      setExpanded(prev => new Set([...prev, cat.id]))
    }
  }

  const updateAmount = (id: string, amount: number) => {
    onChange(selected.map(s => s.category === id ? { ...s, annual_amount: amount } : s))
  }

  return (
    <div className="space-y-3">
      {SYNERGY_CATEGORIES.map(cat => {
        const sel = isSelected(cat.id)
        const item = getItem(cat.id)
        const exp = expanded.has(cat.id)

        return (
          <div
            key={cat.id}
            className={`
              rounded-xl border transition-all cursor-pointer
              ${sel
                ? 'border-blue-500/60 bg-blue-950/20'
                : 'border-slate-700 bg-slate-800/30 hover:border-slate-600'
              }
            `}
          >
            <div
              className="flex items-start gap-3 p-4"
              onClick={() => toggle(cat)}
            >
              <div className="text-2xl flex-shrink-0 mt-0.5">{cat.emoji}</div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-2">
                  <p className={`text-sm font-medium ${sel ? 'text-blue-300' : 'text-slate-300'}`}>
                    {cat.title}
                  </p>
                  <div className={`
                    w-4 h-4 rounded-full border-2 flex-shrink-0 flex items-center justify-center transition-colors
                    ${sel ? 'border-blue-500 bg-blue-500' : 'border-slate-600'}
                  `}>
                    {sel && <span className="text-white text-2xs font-bold">✓</span>}
                  </div>
                </div>
                <p className="text-xs text-slate-500 mt-0.5">{cat.description}</p>
              </div>
            </div>

            {/* Expanded — edit amount */}
            {sel && exp && item && (
              <div
                className="px-4 pb-4 border-t border-slate-700/50 pt-3 animate-fade-in"
                onClick={e => e.stopPropagation()}
              >
                <CurrencyInput
                  label="Estimated annual savings"
                  value={item.annual_amount}
                  onChange={v => updateAmount(cat.id, v)}
                  defaultNote={`We estimated ~$${(combinedRevenue * cat.estimatedPctRevenue / 1_000_000).toFixed(1)}M based on typical deals. Adjust if you have a better number.`}
                />
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
