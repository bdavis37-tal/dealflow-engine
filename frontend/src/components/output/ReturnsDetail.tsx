import { useState, Fragment } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import type { ReturnsAnalysis, DealInput } from '../../types/deal'
import { formatCurrencyCompact, formatMultiple, formatPercentage } from '../../lib/formatters'

interface ReturnsDetailProps {
  returns: ReturnsAnalysis
  dealInput: DealInput
  fiscalYearStart: number
}

export default function ReturnsDetail({ returns, dealInput, fiscalYearStart }: ReturnsDetailProps) {
  const [open, setOpen] = useState(false)

  const acquisitionPrice = dealInput.target.acquisition_price
  const struct = dealInput.structure
  const cashPortion = acquisitionPrice * struct.cash_percentage
  const stockPortion = acquisitionPrice * struct.stock_percentage
  const debtPortion = acquisitionPrice * struct.debt_percentage

  // Group scenarios by exit year for the return matrix
  const exitYears = [...new Set(returns.scenarios.map(s => s.exit_year))].sort()
  const exitMultiples = [...new Set(returns.scenarios.map(s => s.exit_multiple))].sort((a, b) => a - b)

  // Build a lookup for quick access
  const scenarioMap = new Map<string, { irr: number; moic: number; exit_ev: number }>()
  for (const s of returns.scenarios) {
    scenarioMap.set(`${s.exit_year}-${s.exit_multiple}`, {
      irr: s.irr,
      moic: s.moic,
      exit_ev: s.exit_enterprise_value,
    })
  }

  return (
    <div>
      <button
        onClick={() => setOpen(v => !v)}
        className="flex items-center gap-2 text-slate-400 hover:text-slate-200 text-sm font-medium transition-colors"
      >
        {open ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
        {open ? 'Hide' : 'Show'} Returns Analysis
      </button>

      {open && (
        <div className="mt-4 animate-fade-in space-y-6">
          {/* Entry Equity Check */}
          <div>
            <h3 className="text-sm font-semibold text-slate-300 mb-3">Equity Investment at Close</h3>
            <div className="rounded-xl border border-slate-700 bg-slate-800/20 overflow-hidden">
              <table className="w-full">
                <tbody>
                  <tr className="border-b border-slate-800/50">
                    <td className="py-2 pl-4 pr-2 text-xs text-slate-400">Acquisition Price</td>
                    <td className="py-2 px-3 text-right text-xs text-slate-200 tabular-nums font-semibold">
                      {formatCurrencyCompact(acquisitionPrice)}
                    </td>
                  </tr>
                  {cashPortion > 0 && (
                    <tr className="border-b border-slate-800/50">
                      <td className="py-2 pl-8 pr-2 text-xs text-slate-500">
                        Cash ({formatPercentage(struct.cash_percentage * 100, 0)})
                      </td>
                      <td className="py-2 px-3 text-right text-xs text-slate-300 tabular-nums">
                        {formatCurrencyCompact(cashPortion)}
                      </td>
                    </tr>
                  )}
                  {stockPortion > 0 && (
                    <tr className="border-b border-slate-800/50">
                      <td className="py-2 pl-8 pr-2 text-xs text-slate-500">
                        Stock ({formatPercentage(struct.stock_percentage * 100, 0)})
                      </td>
                      <td className="py-2 px-3 text-right text-xs text-slate-300 tabular-nums">
                        {formatCurrencyCompact(stockPortion)}
                      </td>
                    </tr>
                  )}
                  {debtPortion > 0 && (
                    <tr className="border-b border-slate-800/50">
                      <td className="py-2 pl-8 pr-2 text-xs text-slate-500">
                        Debt ({formatPercentage(struct.debt_percentage * 100, 0)})
                      </td>
                      <td className="py-2 px-3 text-right text-xs text-slate-300 tabular-nums">
                        {formatCurrencyCompact(debtPortion)}
                      </td>
                    </tr>
                  )}
                  <tr className="border-b border-slate-800/50 bg-slate-800/20">
                    <td className="py-2 pl-4 pr-2 text-xs text-slate-200 font-semibold">Equity Invested (Cash + Stock)</td>
                    <td className="py-2 px-3 text-right text-xs text-slate-100 tabular-nums font-bold">
                      {formatCurrencyCompact(returns.equity_invested)}
                    </td>
                  </tr>
                  <tr>
                    <td className="py-2 pl-4 pr-2 text-xs text-slate-400">Entry EV / EBITDA</td>
                    <td className="py-2 px-3 text-right text-xs text-slate-200 tabular-nums font-semibold">
                      {formatMultiple(returns.entry_multiple)}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          {/* Annual Free Cash Flow to Equity */}
          {returns.annual_fcf_to_equity.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-slate-300 mb-3">Free Cash Flow to Equity</h3>
              <div className="rounded-xl border border-slate-700 bg-slate-800/20 overflow-hidden">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-slate-700">
                      <th className="py-2.5 pl-4 pr-2 text-left text-xs font-semibold text-slate-400 w-48" />
                      {returns.annual_fcf_to_equity.map((_, i) => (
                        <th key={i} className="py-2.5 px-3 text-right text-xs font-semibold text-slate-400">
                          FY{fiscalYearStart + i}E
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    <tr className="border-b border-slate-800/50">
                      <td className="py-2 pl-4 pr-2 text-xs text-slate-300 font-medium">FCF to Equity</td>
                      {returns.annual_fcf_to_equity.map((fcf, i) => (
                        <td key={i} className={`py-2 px-3 text-right text-xs tabular-nums font-medium ${fcf < 0 ? 'text-red-300' : 'text-slate-200'}`}>
                          {formatCurrencyCompact(fcf)}
                        </td>
                      ))}
                    </tr>
                    <tr>
                      <td className="py-2 pl-4 pr-2 text-xs text-slate-400">Cumulative</td>
                      {returns.annual_fcf_to_equity.map((_, i) => {
                        const cumulative = returns.annual_fcf_to_equity.slice(0, i + 1).reduce((a, b) => a + b, 0)
                        return (
                          <td key={i} className={`py-2 px-3 text-right text-xs tabular-nums ${cumulative < 0 ? 'text-red-300' : 'text-slate-300'}`}>
                            {formatCurrencyCompact(cumulative)}
                          </td>
                        )
                      })}
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* IRR / MOIC Return Matrix */}
          {exitYears.length > 0 && exitMultiples.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-slate-300 mb-3">Return Matrix (IRR / MOIC)</h3>
              <div className="rounded-xl border border-slate-700 bg-slate-800/20 overflow-x-auto">
                <table className="w-full min-w-[500px]">
                  <thead>
                    <tr className="border-b border-slate-700">
                      <th className="py-2.5 pl-4 pr-2 text-left text-xs font-semibold text-slate-400" rowSpan={2}>
                        Exit Multiple
                      </th>
                      {exitYears.map(yr => (
                        <th key={yr} className="py-2 px-3 text-center text-xs font-semibold text-slate-400" colSpan={2}>
                          Year {yr} Exit
                        </th>
                      ))}
                    </tr>
                    <tr className="border-b border-slate-700 bg-slate-800/40">
                      {exitYears.map(yr => (
                        <Fragment key={yr}>
                          <th className="py-1.5 px-2 text-center text-2xs font-medium text-slate-500">IRR</th>
                          <th className="py-1.5 px-2 text-center text-2xs font-medium text-slate-500">MOIC</th>
                        </Fragment>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {exitMultiples.map(mult => {
                      const isBase = Math.abs(mult - returns.entry_multiple) < 0.05
                      return (
                        <tr
                          key={mult}
                          className={`border-b border-slate-800/50 ${isBase ? 'bg-blue-950/20' : 'hover:bg-slate-800/10'}`}
                        >
                          <td className={`py-2 pl-4 pr-2 text-xs tabular-nums ${isBase ? 'text-blue-400 font-semibold' : 'text-slate-400'}`}>
                            {formatMultiple(mult)}{isBase ? ' (Entry)' : ''}
                          </td>
                          {exitYears.map(yr => {
                            const s = scenarioMap.get(`${yr}-${mult}`)
                            if (!s) return (
                              <Fragment key={yr}>
                                <td className="py-2 px-2 text-center text-xs text-slate-600">—</td>
                                <td className="py-2 px-2 text-center text-xs text-slate-600">—</td>
                              </Fragment>
                            )
                            const irrColor = s.irr >= 0.20 ? 'text-green-400' : s.irr >= 0.10 ? 'text-slate-200' : s.irr >= 0 ? 'text-amber-400' : 'text-red-400'
                            const moicColor = s.moic >= 2.0 ? 'text-green-400' : s.moic >= 1.0 ? 'text-slate-200' : 'text-red-400'
                            return (
                              <Fragment key={yr}>
                                <td className={`py-2 px-2 text-center text-xs tabular-nums font-medium ${irrColor}`}>
                                  {s.irr <= -1 ? 'NM' : formatPercentage(s.irr * 100, 1)}
                                </td>
                                <td className={`py-2 px-2 text-center text-xs tabular-nums font-medium ${moicColor}`}>
                                  {formatMultiple(s.moic)}
                                </td>
                              </Fragment>
                            )
                          })}
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
              <div className="flex items-center gap-3 mt-2 text-2xs text-slate-500">
                <div className="flex items-center gap-1.5">
                  <div className="w-3 h-3 rounded-sm bg-blue-950/40 ring-1 ring-blue-500/40" />
                  <span>Entry multiple</span>
                </div>
                <span>|</span>
                <span className="text-green-400">IRR ≥ 20%</span>
                <span className="text-amber-400">0–10%</span>
                <span className="text-red-400">Negative</span>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
