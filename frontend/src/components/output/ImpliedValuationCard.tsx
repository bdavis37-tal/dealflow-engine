import type { ImpliedValuation } from '../../types/deal'
import { formatCurrencyCompact, formatMultiple } from '../../lib/formatters'

interface ImpliedValuationCardProps {
  data: ImpliedValuation
}

export default function ImpliedValuationCard({ data }: ImpliedValuationCardProps) {
  const metrics = [
    { label: 'Enterprise Value', value: formatCurrencyCompact(data.enterprise_value), sub: 'Purchase price + debt assumed − cash acquired' },
    { label: 'Equity Value', value: formatCurrencyCompact(data.equity_value), sub: 'Price paid for target equity' },
    { label: 'EV / Revenue (LTM)', value: formatMultiple(data.ev_revenue_ltm), sub: 'Last twelve months' },
    { label: 'EV / EBITDA (LTM)', value: formatMultiple(data.ev_ebitda_ltm), sub: 'Last twelve months' },
    { label: 'EV / EBITDA (NTM)', value: formatMultiple(data.ev_ebitda_ntm), sub: 'Next twelve months (projected)' },
    ...(data.price_to_earnings > 0 && data.price_to_earnings < 100
      ? [{ label: 'Price / Earnings', value: formatMultiple(data.price_to_earnings), sub: 'LTM net income' }]
      : []),
  ]

  return (
    <div>
      <h2 className="text-lg font-semibold text-slate-100 mb-4">Implied Valuation</h2>
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        {metrics.map((m) => (
          <div key={m.label} className="rounded-xl border border-slate-700 bg-slate-800/20 p-4">
            <div className="text-2xs text-slate-500 mb-1 font-medium">{m.label}</div>
            <div className="text-xl font-bold text-slate-100 tabular-nums">{m.value}</div>
            <div className="text-2xs text-slate-600 mt-1">{m.sub}</div>
          </div>
        ))}
      </div>
    </div>
  )
}
