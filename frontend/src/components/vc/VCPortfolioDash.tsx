/**
 * VCPortfolioDash — Portfolio construction dashboard.
 * Tracks deployment, concentration, TVPI/DPI/RVPI, and reserve adequacy.
 * Works with localStorage-persisted positions.
 */

import { useState, useEffect } from 'react'
import type { FundProfile, PortfolioPosition, PortfolioOutput } from '../../types/vc'
import { VC_VERTICAL_LABELS, VC_STAGE_LABELS } from '../../types/vc'
import { analyzePortfolio } from '../../lib/vc-api'

interface Props {
  fund: FundProfile
}

const POSITIONS_KEY = 'vc_portfolio_positions'

function loadPositions(): PortfolioPosition[] {
  try {
    const s = localStorage.getItem(POSITIONS_KEY)
    return s ? JSON.parse(s) : []
  } catch { return [] }
}
function savePositions(pos: PortfolioPosition[]) {
  try { localStorage.setItem(POSITIONS_KEY, JSON.stringify(pos)) } catch {}
}

function fmt(n: number, dec = 1) {
  return n.toLocaleString('en-US', { minimumFractionDigits: dec, maximumFractionDigits: dec })
}
function pct(n: number) { return `${(n * 100).toFixed(1)}%` }

const STATUS_COLORS = {
  active: 'text-emerald-400',
  written_off: 'text-red-400',
  exited: 'text-blue-400',
  partially_exited: 'text-amber-400',
}

function AddPositionModal({
  onAdd,
  onClose,
}: {
  onAdd: (p: PortfolioPosition) => void
  onClose: () => void
}) {
  const [form, setForm] = useState<Partial<PortfolioPosition>>({
    status: 'active',
    stage_at_entry: 'seed',
    vertical: 'b2b_saas',
    is_lead: false,
    vintage_year: new Date().getFullYear(),
    reserve_allocated: 0,
    reserve_deployed: 0,
    realized_proceeds: 0,
  })

  const ok = form.company_name && form.check_size && form.post_money_at_entry && form.entry_ownership_pct

  function submit() {
    if (!ok) return
    const pos: PortfolioPosition = {
      company_name: form.company_name!,
      vertical: form.vertical!,
      stage_at_entry: form.stage_at_entry!,
      check_size: form.check_size!,
      post_money_at_entry: form.post_money_at_entry!,
      entry_ownership_pct: form.entry_ownership_pct! / 100,
      current_ownership_pct: form.current_ownership_pct
        ? form.current_ownership_pct / 100
        : form.entry_ownership_pct! / 100,
      reserve_allocated: form.reserve_allocated ?? 0,
      reserve_deployed: form.reserve_deployed ?? 0,
      last_round_valuation: form.last_round_valuation,
      status: form.status as PortfolioPosition['status'],
      is_lead: form.is_lead ?? false,
      vintage_year: form.vintage_year ?? new Date().getFullYear(),
      cost_basis: (form.check_size ?? 0) + (form.reserve_deployed ?? 0),
      fair_value: form.fair_value,
      realized_proceeds: form.realized_proceeds ?? 0,
    }
    onAdd(pos)
    onClose()
  }

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
      <div className="bg-slate-900 border border-slate-700 rounded-2xl p-6 w-full max-w-lg space-y-4 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-slate-100">Add Portfolio Company</h3>
          <button onClick={onClose} className="text-slate-500 hover:text-slate-300 text-xl">×</button>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div className="col-span-2">
            <FLabel>Company Name</FLabel>
            <FInput value={form.company_name ?? ''} onChange={v => setForm(f => ({...f, company_name: v}))} placeholder="Acme AI" />
          </div>
          <div>
            <FLabel>Stage at Entry</FLabel>
            <select
              value={form.stage_at_entry}
              onChange={e => setForm(f => ({...f, stage_at_entry: e.target.value as any}))}
              className="w-full bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-slate-100 text-sm focus:outline-none focus:border-emerald-500"
            >
              {Object.entries(VC_STAGE_LABELS).map(([v, l]) => (
                <option key={v} value={v}>{l}</option>
              ))}
            </select>
          </div>
          <div>
            <FLabel>Vertical</FLabel>
            <select
              value={form.vertical}
              onChange={e => setForm(f => ({...f, vertical: e.target.value as any}))}
              className="w-full bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-slate-100 text-sm focus:outline-none focus:border-emerald-500"
            >
              {Object.entries(VC_VERTICAL_LABELS).map(([v, l]) => (
                <option key={v} value={v}>{l}</option>
              ))}
            </select>
          </div>
          <div>
            <FLabel>Check Size ($M)</FLabel>
            <FNumInput value={form.check_size ?? 0} onChange={v => setForm(f => ({...f, check_size: v}))} />
          </div>
          <div>
            <FLabel>Post-Money at Entry ($M)</FLabel>
            <FNumInput value={form.post_money_at_entry ?? 0} onChange={v => setForm(f => ({...f, post_money_at_entry: v}))} />
          </div>
          <div>
            <FLabel>Entry Ownership (%)</FLabel>
            <FNumInput value={form.entry_ownership_pct ?? 0} onChange={v => setForm(f => ({...f, entry_ownership_pct: v}))} step={0.1} />
          </div>
          <div>
            <FLabel>Current Valuation ($M)</FLabel>
            <FNumInput value={form.last_round_valuation ?? 0} onChange={v => setForm(f => ({...f, last_round_valuation: v || undefined}))} />
          </div>
          <div>
            <FLabel>Fair Value ($M)</FLabel>
            <FNumInput value={form.fair_value ?? 0} onChange={v => setForm(f => ({...f, fair_value: v || undefined}))} />
          </div>
          <div>
            <FLabel>Reserve Allocated ($M)</FLabel>
            <FNumInput value={form.reserve_allocated ?? 0} onChange={v => setForm(f => ({...f, reserve_allocated: v}))} />
          </div>
          <div>
            <FLabel>Reserve Deployed ($M)</FLabel>
            <FNumInput value={form.reserve_deployed ?? 0} onChange={v => setForm(f => ({...f, reserve_deployed: v}))} />
          </div>
          <div>
            <FLabel>Status</FLabel>
            <select
              value={form.status}
              onChange={e => setForm(f => ({...f, status: e.target.value as any}))}
              className="w-full bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-slate-100 text-sm focus:outline-none focus:border-emerald-500"
            >
              <option value="active">Active</option>
              <option value="written_off">Written Off</option>
              <option value="exited">Exited</option>
              <option value="partially_exited">Partially Exited</option>
            </select>
          </div>
          <div>
            <FLabel>Vintage Year</FLabel>
            <FNumInput value={form.vintage_year ?? new Date().getFullYear()} onChange={v => setForm(f => ({...f, vintage_year: v}))} step={1} />
          </div>
        </div>

        <div className="flex gap-3 pt-2">
          <button onClick={onClose} className="flex-1 py-2.5 border border-slate-700 rounded-xl text-slate-400 hover:text-slate-200 text-sm transition-colors">Cancel</button>
          <button onClick={submit} disabled={!ok} className={`flex-1 py-2.5 rounded-xl font-semibold text-sm transition-colors ${ok ? 'bg-emerald-600 hover:bg-emerald-500 text-white' : 'bg-slate-700 text-slate-500 cursor-not-allowed'}`}>
            Add Company
          </button>
        </div>
      </div>
    </div>
  )
}

function FLabel({ children }: { children: React.ReactNode }) {
  return <label className="block text-xs font-medium text-slate-400 mb-1">{children}</label>
}
function FInput({ value, onChange, placeholder }: { value: string; onChange: (v: string) => void; placeholder?: string }) {
  return <input type="text" value={value} onChange={e => onChange(e.target.value)} placeholder={placeholder} className="w-full bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-slate-100 text-sm focus:outline-none focus:border-emerald-500" />
}
function FNumInput({ value, onChange, step = 0.1 }: { value: number; onChange: (v: number) => void; step?: number }) {
  return <input type="number" value={value || ''} step={step} onChange={e => onChange(parseFloat(e.target.value) || 0)} className="w-full bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-slate-100 text-sm focus:outline-none focus:border-emerald-500" />
}

export default function VCPortfolioDash({ fund }: Props) {
  const [positions, setPositions] = useState<PortfolioPosition[]>(loadPositions)
  const [output, setOutput] = useState<PortfolioOutput | null>(null)
  const [showAdd, setShowAdd] = useState(false)
  const [, setLoading] = useState(false)

  useEffect(() => {
    savePositions(positions)
    if (positions.length === 0) { setOutput(null); return }
    setLoading(true)
    analyzePortfolio({ fund_profile: fund, positions })
      .then(r => { setOutput(r); setLoading(false) })
      .catch(() => setLoading(false))
  }, [positions, fund])

  function addPosition(p: PortfolioPosition) {
    setPositions(prev => [...prev, p])
  }
  function removePosition(idx: number) {
    setPositions(prev => prev.filter((_, i) => i !== idx))
  }

  const stats = output?.stats

  return (
    <div className="space-y-5">
      {/* Header actions */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-slate-100">Portfolio Dashboard</h2>
        <button
          onClick={() => setShowAdd(true)}
          className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium rounded-lg transition-colors"
        >
          + Add Company
        </button>
      </div>

      {/* Fund overview */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard label="Fund Size" value={`$${fmt(fund.fund_size)}M`} />
        <StatCard
          label="Investable Capital"
          value={`$${fmt(fund.fund_size - fund.fund_size * fund.management_fee_pct * fund.management_fee_years)}M`}
        />
        <StatCard
          label="Initial Pool"
          value={`$${fmt((fund.fund_size - fund.fund_size * fund.management_fee_pct * fund.management_fee_years) * (1 - fund.reserve_ratio))}M`}
        />
        <StatCard
          label="Reserve Pool"
          value={`$${fmt((fund.fund_size - fund.fund_size * fund.management_fee_pct * fund.management_fee_years) * fund.reserve_ratio)}M`}
        />
      </div>

      {/* Portfolio metrics (when positions exist) */}
      {stats && (
        <>
          {/* Deployment */}
          <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-5">
            <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-4">Deployment</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <StatCard label="Total Deployed" value={`$${fmt(stats.total_deployed)}M`} highlight={stats.pct_deployed > 0.8} />
              <StatCard label="% Deployed" value={pct(stats.pct_deployed)} highlight={stats.pct_deployed > 0.9} />
              <StatCard label="Initial Remaining" value={`$${fmt(stats.initial_remaining)}M`} />
              <StatCard label="Reserve Remaining" value={`$${fmt(stats.reserve_remaining)}M`} />
            </div>

            {/* Deployment bar */}
            <div className="mt-4">
              <div className="flex h-2 rounded-full overflow-hidden bg-slate-700">
                <div
                  className="bg-emerald-500"
                  style={{ width: pct(Math.min(stats.total_initial_deployed / stats.initial_check_pool, 1)) }}
                  title="Initial deployed"
                />
              </div>
              <div className="flex justify-between mt-1 text-xs text-slate-500">
                <span>Initial: ${fmt(stats.total_initial_deployed)}M / ${fmt(stats.initial_check_pool)}M</span>
                <span>Reserves: ${fmt(stats.total_reserve_deployed)}M / ${fmt(stats.reserve_pool)}M</span>
              </div>
            </div>

            {/* Reserve adequacy badge */}
            <div className={`mt-3 inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium
              ${stats.reserve_adequacy === 'adequate'
                ? 'bg-emerald-900/30 text-emerald-400 border border-emerald-700/30'
                : stats.reserve_adequacy === 'tight'
                ? 'bg-amber-900/30 text-amber-400 border border-amber-700/30'
                : 'bg-red-900/30 text-red-400 border border-red-700/30'}`}
            >
              Reserve: {stats.reserve_adequacy}
            </div>
          </div>

          {/* Performance */}
          <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-5">
            <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-4">Performance Marks</h3>
            <div className="grid grid-cols-3 gap-4">
              <PerfMetric label="TVPI" value={`${fmt(stats.tvpi)}x`} color={stats.tvpi >= 2 ? 'green' : stats.tvpi >= 1 ? 'yellow' : 'red'} sub="Total / Paid-In" />
              <PerfMetric label="DPI" value={`${fmt(stats.dpi)}x`} color={stats.dpi >= 1 ? 'green' : 'neutral'} sub="Distributed / Paid-In" />
              <PerfMetric label="RVPI" value={`${fmt(stats.rvpi)}x`} color="neutral" sub="Residual / Paid-In" />
            </div>
          </div>

          {/* Concentration */}
          <div className="grid grid-cols-2 gap-4">
            <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-5">
              <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">By Stage</h3>
              {Object.entries(stats.stage_breakdown).map(([stage, amt]) => (
                <ConcentrationBar
                  key={stage}
                  label={VC_STAGE_LABELS[stage as keyof typeof VC_STAGE_LABELS] ?? stage}
                  value={amt}
                  total={stats.total_cost_basis}
                />
              ))}
            </div>
            <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-5">
              <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">By Vertical</h3>
              {Object.entries(stats.vertical_breakdown)
                .sort((a, b) => b[1] - a[1])
                .slice(0, 5)
                .map(([v, amt]) => (
                  <ConcentrationBar
                    key={v}
                    label={VC_VERTICAL_LABELS[v as keyof typeof VC_VERTICAL_LABELS] ?? v}
                    value={amt}
                    total={stats.total_cost_basis}
                    flag={amt / stats.total_cost_basis > 0.35}
                  />
                ))}
            </div>
          </div>

          {/* Alerts */}
          {output.alerts.length > 0 && (
            <div className="space-y-2">
              {output.alerts.map((alert, i) => (
                <div key={i} className="flex items-start gap-2 text-xs text-amber-300 bg-amber-950/20 border border-amber-800/20 rounded-lg px-3 py-2">
                  <span>⚠</span><span>{alert}</span>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {/* Position table */}
      {positions.length > 0 && (
        <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-5">
          <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-4">
            Portfolio ({positions.length} companies)
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-700">
                  {['Company', 'Stage', 'Check', 'Entry Own.', 'FMV', 'Status', ''].map(h => (
                    <th key={h} className="text-left py-2 text-slate-500 text-xs font-medium">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {positions.map((pos, i) => (
                  <tr key={i} className="border-b border-slate-800 hover:bg-slate-800/30">
                    <td className="py-2 text-slate-200 font-medium">{pos.company_name}</td>
                    <td className="py-2 text-slate-400 text-xs">{VC_STAGE_LABELS[pos.stage_at_entry]}</td>
                    <td className="py-2 text-slate-300">${fmt(pos.check_size)}M</td>
                    <td className="py-2 text-slate-300">{pct(pos.entry_ownership_pct)}</td>
                    <td className="py-2 text-slate-300">{pos.fair_value ? `$${fmt(pos.fair_value)}M` : '—'}</td>
                    <td className={`py-2 text-xs font-medium ${STATUS_COLORS[pos.status]}`}>
                      {pos.status.replace(/_/g, ' ')}
                    </td>
                    <td className="py-2">
                      <button
                        onClick={() => removePosition(i)}
                        className="text-slate-600 hover:text-red-400 text-xs transition-colors"
                      >
                        remove
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {positions.length === 0 && (
        <div className="text-center py-16 text-slate-500">
          <div className="text-4xl mb-3">📊</div>
          <div className="text-sm">No portfolio companies yet.</div>
          <div className="text-xs mt-1">Add companies to track deployment and performance.</div>
        </div>
      )}

      {showAdd && <AddPositionModal onAdd={addPosition} onClose={() => setShowAdd(false)} />}
    </div>
  )
}

function StatCard({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div className="bg-slate-800/60 border border-slate-700 rounded-lg p-3">
      <div className="text-xs text-slate-500">{label}</div>
      <div className={`text-sm font-semibold mt-0.5 ${highlight ? 'text-amber-400' : 'text-slate-200'}`}>{value}</div>
    </div>
  )
}

function PerfMetric({ label, value, sub, color }: { label: string; value: string; sub: string; color: string }) {
  const colors = { green: 'text-emerald-400', yellow: 'text-amber-400', red: 'text-red-400', neutral: 'text-slate-200' }
  return (
    <div className="text-center">
      <div className={`text-2xl font-bold ${colors[color as keyof typeof colors]}`}>{value}</div>
      <div className="text-xs text-slate-300 mt-0.5">{label}</div>
      <div className="text-xs text-slate-500">{sub}</div>
    </div>
  )
}

function ConcentrationBar({ label, value, total, flag }: { label: string; value: number; total: number; flag?: boolean }) {
  const p = total > 0 ? value / total : 0
  return (
    <div className="mb-2">
      <div className="flex justify-between text-xs mb-0.5">
        <span className={flag ? 'text-amber-400' : 'text-slate-400'}>{label}</span>
        <span className={flag ? 'text-amber-400 font-medium' : 'text-slate-400'}>{pctRound(p)}</span>
      </div>
      <div className="h-1.5 bg-slate-700 rounded-full overflow-hidden">
        <div
          className={flag ? 'h-full bg-amber-500 rounded-full' : 'h-full bg-emerald-500 rounded-full'}
          style={{ width: pctRound(p) }}
        />
      </div>
    </div>
  )
}

function pctRound(n: number) { return `${(n * 100).toFixed(0)}%` }
