import { useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import type { IncomeStatementYear } from '../../types/deal'
import { formatAccounting, formatPercentage } from '../../lib/formatters'

interface FinancialStatementsProps {
  incomeStatement: IncomeStatementYear[]
}

function Row({
  label,
  values,
  bold,
  indent,
  isPercentage,
  highlight,
}: {
  label: string
  values: number[]
  bold?: boolean
  indent?: boolean
  isPercentage?: boolean
  highlight?: boolean
}) {
  const fmt = (v: number) => isPercentage ? formatPercentage(v, 1, true) : formatAccounting(v)

  return (
    <tr className={`
      border-b border-slate-800/50 transition-colors
      ${highlight ? 'bg-slate-800/20' : 'hover:bg-slate-800/10'}
    `}>
      <td className={`
        py-2 pl-4 pr-2 text-xs text-left
        ${bold ? 'font-semibold text-slate-200' : 'text-slate-400'}
        ${indent ? 'pl-8' : ''}
      `}>
        {label}
      </td>
      {values.map((v, i) => (
        <td key={i} className={`
          py-2 px-3 text-xs text-right tabular-nums
          ${bold ? 'font-semibold text-slate-200' : 'text-slate-300'}
          ${v < 0 ? 'text-red-300' : ''}
          ${highlight ? 'font-bold' : ''}
        `}>
          {fmt(v)}
        </td>
      ))}
    </tr>
  )
}

export default function FinancialStatements({ incomeStatement }: FinancialStatementsProps) {
  const [open, setOpen] = useState(false)

  return (
    <div>
      <button
        onClick={() => setOpen(v => !v)}
        className="flex items-center gap-2 text-slate-400 hover:text-slate-200 text-sm font-medium transition-colors"
      >
        {open ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
        {open ? 'Hide' : 'Show'} Detailed Financial Statements
      </button>

      {open && (
        <div className="mt-4 overflow-x-auto animate-fade-in">
          <table className="w-full min-w-[640px]">
            <thead>
              <tr className="border-b border-slate-700">
                <th className="py-2.5 pl-4 pr-2 text-left text-xs font-semibold text-slate-400 w-48">
                  Pro Forma Income Statement
                </th>
                {incomeStatement.map(yr => (
                  <th key={yr.year} className="py-2.5 px-3 text-right text-xs font-semibold text-slate-400">
                    Year {yr.year}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              <Row label="Revenue" values={incomeStatement.map(y => y.revenue)} bold />
              <Row label="Cost of Goods Sold" values={incomeStatement.map(y => -y.cogs)} indent />
              <Row label="Gross Profit" values={incomeStatement.map(y => y.gross_profit)} bold highlight />
              <Row label="SG&A" values={incomeStatement.map(y => -y.sga)} indent />
              <Row label="EBITDA" values={incomeStatement.map(y => y.ebitda)} bold highlight />
              <Row label="Depreciation & Amortization" values={incomeStatement.map(y => -y.da)} indent />
              <Row label="EBIT" values={incomeStatement.map(y => y.ebit)} bold />
              <Row label="Interest Expense" values={incomeStatement.map(y => -y.interest_expense)} indent />
              <Row label="Earnings Before Tax" values={incomeStatement.map(y => y.ebt)} bold />
              <Row label="Taxes" values={incomeStatement.map(y => -y.taxes)} indent />
              <Row label="Net Income" values={incomeStatement.map(y => y.net_income)} bold highlight />
              <tr className="border-b border-slate-700 h-2" />
              <tr className="border-b border-slate-800/50">
                <td className="py-2 pl-4 text-xs font-semibold text-slate-400">EPS</td>
                {incomeStatement.map(yr => (
                  <td key={yr.year} className="py-2 px-3 text-right" />
                ))}
              </tr>
              <Row label="Acquirer Standalone EPS" values={incomeStatement.map(y => y.acquirer_standalone_eps)} indent />
              <Row label="Pro Forma EPS" values={incomeStatement.map(y => y.pro_forma_eps)} indent bold />
              <Row
                label="Accretion / (Dilution) %"
                values={incomeStatement.map(y => y.accretion_dilution_pct)}
                bold highlight isPercentage
              />
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
