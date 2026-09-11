import type { FundraisingProfile } from '../../../types/startup'

export default function ValuationAssumptions({ value, onChange }: {
  value: Partial<FundraisingProfile>; onChange: (value: Partial<FundraisingProfile>) => void
}) {
  return <div className="grid gap-4 md:grid-cols-2 my-4">
    <label className="text-sm text-slate-300">Business model
      <select className="block w-full mt-1 bg-slate-800 border border-slate-600 p-2 rounded" value={value.business_model ?? 'auto'} onChange={e => onChange({business_model:e.target.value as FundraisingProfile['business_model']})}>
        <option value="auto">Use sector default</option><option value="recurring_software">Recurring software</option><option value="hardware">Hardware</option><option value="services">Services</option><option value="biotech">Biotech</option><option value="mixed">Mixed business</option>
      </select>
    </label>
    <label className="text-sm text-slate-300">{value.instrument === 'safe' ? 'Explicit SAFE cap ($M)' : 'Pre-money ask ($M)'}
      <input type="number" min="0" step="0.1" className="block w-full mt-1 bg-slate-800 border border-slate-600 p-2 rounded" value={(value.instrument === 'safe' ? value.safe_valuation_cap : value.pre_money_valuation_ask) ?? ''}
        onChange={e => onChange(value.instrument === 'safe' ? {safe_valuation_cap:e.target.value === '' ? undefined : Number(e.target.value)} : {pre_money_valuation_ask:e.target.value === '' ? null : Number(e.target.value)})} />
      <span className="block mt-1 text-xs text-slate-500">Optional. An indicated pre-money value is not a SAFE cap.</span>
    </label>
  </div>
}
