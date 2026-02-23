/**
 * Visual triple-slider for cash/stock/debt mix.
 * Three segments must always sum to 100%.
 */
import React from 'react'
import { formatCurrencyCompact } from '../../lib/formatters'

interface FinancingSliderProps {
  dealSize: number
  cash: number     // 0–100
  stock: number    // 0–100
  debt: number     // 0–100 (derived: 100 - cash - stock)
  onChange: (cash: number, stock: number, debt: number) => void
}

export default function FinancingSlider({ dealSize, cash, stock, debt, onChange }: FinancingSliderProps) {
  const handleCashChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newCash = Math.min(100, Math.max(0, Number(e.target.value)))
    const remaining = 100 - newCash
    // Proportionally redistribute between stock and debt
    const stockRatio = stock + debt > 0 ? stock / (stock + debt) : 0.5
    const newStock = Math.round(remaining * stockRatio)
    const newDebt = remaining - newStock
    onChange(newCash, newStock, newDebt)
  }

  const handleStockChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newStock = Math.min(100, Math.max(0, Number(e.target.value)))
    const remaining = 100 - newStock
    const cashRatio = cash + debt > 0 ? cash / (cash + debt) : 0.5
    const newCash = Math.round(remaining * cashRatio)
    const newDebt = remaining - newCash
    onChange(newCash, newStock, newDebt)
  }

  const cashAmt = dealSize * (cash / 100)
  const stockAmt = dealSize * (stock / 100)
  const debtAmt = dealSize * (debt / 100)

  return (
    <div className="space-y-6">
      {/* Visual bar */}
      <div className="relative h-8 rounded-lg overflow-hidden flex">
        <div
          className="bg-green-600 transition-all duration-200 flex items-center justify-center"
          style={{ width: `${cash}%` }}
        >
          {cash > 10 && (
            <span className="text-xs font-semibold text-white">{cash}%</span>
          )}
        </div>
        <div
          className="bg-blue-600 transition-all duration-200 flex items-center justify-center"
          style={{ width: `${stock}%` }}
        >
          {stock > 10 && (
            <span className="text-xs font-semibold text-white">{stock}%</span>
          )}
        </div>
        <div
          className="bg-amber-600 transition-all duration-200 flex items-center justify-center"
          style={{ width: `${debt}%` }}
        >
          {debt > 10 && (
            <span className="text-xs font-semibold text-white">{debt}%</span>
          )}
        </div>
      </div>

      {/* Legend */}
      <div className="grid grid-cols-3 gap-3 text-center text-xs">
        <div>
          <div className="w-3 h-3 bg-green-600 rounded-sm mx-auto mb-1" />
          <div className="text-slate-300 font-medium">Cash</div>
          <div className="text-slate-500">{formatCurrencyCompact(cashAmt)}</div>
        </div>
        <div>
          <div className="w-3 h-3 bg-blue-600 rounded-sm mx-auto mb-1" />
          <div className="text-slate-300 font-medium">Stock</div>
          <div className="text-slate-500">{formatCurrencyCompact(stockAmt)}</div>
        </div>
        <div>
          <div className="w-3 h-3 bg-amber-600 rounded-sm mx-auto mb-1" />
          <div className="text-slate-300 font-medium">Debt</div>
          <div className="text-slate-500">{formatCurrencyCompact(debtAmt)}</div>
        </div>
      </div>

      {/* Sliders */}
      <div className="space-y-4" role="group" aria-label="Deal financing mix">
        <div className="space-y-2">
          <label htmlFor="slider-cash" className="text-xs text-slate-400">Cash: {cash}%</label>
          <input
            id="slider-cash"
            type="range" min={0} max={100} value={cash}
            onChange={handleCashChange}
            aria-label={`Cash percentage: ${cash}%`}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={cash}
            className="w-full accent-green-500"
          />
        </div>
        <div className="space-y-2">
          <label htmlFor="slider-stock" className="text-xs text-slate-400">Stock: {stock}%</label>
          <input
            id="slider-stock"
            type="range" min={0} max={100} value={stock}
            onChange={handleStockChange}
            aria-label={`Stock percentage: ${stock}%`}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={stock}
            className="w-full accent-blue-500"
          />
        </div>
        <div className="space-y-2">
          <label htmlFor="slider-debt" className="text-xs text-slate-400">Debt: {debt}% (auto-calculated)</label>
          <input
            id="slider-debt"
            type="range" min={0} max={100} value={debt}
            readOnly
            aria-label={`Debt percentage: ${debt}% (auto-calculated)`}
            aria-disabled="true"
            className="w-full accent-amber-500 opacity-50"
          />
        </div>
      </div>

      {/* Plain-English summary */}
      <div className="rounded-lg bg-slate-800/40 border border-slate-700/50 px-4 py-3 text-sm text-slate-300">
        You're paying{' '}
        {cash > 0 && <span className="text-green-400 font-medium">{cash}% with cash ({formatCurrencyCompact(cashAmt)})</span>}
        {cash > 0 && (stock > 0 || debt > 0) && ', '}
        {stock > 0 && <span className="text-blue-400 font-medium">{stock}% with new stock ({formatCurrencyCompact(stockAmt)})</span>}
        {stock > 0 && debt > 0 && ', and '}
        {debt > 0 && <span className="text-amber-400 font-medium">{debt}% with new debt ({formatCurrencyCompact(debtAmt)})</span>}
        .
      </div>
    </div>
  )
}
