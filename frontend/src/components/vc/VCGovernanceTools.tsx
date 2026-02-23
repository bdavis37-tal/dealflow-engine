/**
 * VCGovernanceTools — Phase 4 governance/tax tools.
 * QSBS eligibility screener, Anti-dilution modeler, Bridge round modeler.
 * Standalone panel that can be shown from the portfolio or deal views.
 */

import { useState } from 'react'
import type { FundProfile, QSBSOutput, AntiDilutionOutput, BridgeRoundOutput } from '../../types/vc'
import { checkQSBS, analyzeAntiDilution, analyzeBridge } from '../../lib/vc-api'
import type { QSBSInput, AntiDilutionInput, BridgeRoundInput } from '../../lib/vc-api'

interface Props {
  fund: FundProfile
}

type GovernanceTool = 'qsbs' | 'antidilution' | 'bridge'

function fmt(n: number, dec = 1) {
  return n.toLocaleString('en-US', { minimumFractionDigits: dec, maximumFractionDigits: dec })
}
function pct(n: number) { return `${(n * 100).toFixed(1)}%` }

// ---------------------------------------------------------------------------
// QSBS Screener
// ---------------------------------------------------------------------------
function QSBSScreener({ fund }: { fund: FundProfile }) {
  const [form, setForm] = useState<QSBSInput>({
    company_name: '',
    incorporated_in_c_corp: false,
    domestic_us_corp: false,
    active_business: false,
    assets_at_issuance_under_50m: false,
    original_issuance: false,
    holding_period_years: 0,
    investment_amount: 0,
    issuance_date_post_july_2025: false,
    fund_size: fund.fund_size,
    lp_count: 50,
    lp_marginal_tax_rate: 0.37,
  })
  const [result, setResult] = useState<QSBSOutput | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function run() {
    if (!form.company_name || !form.investment_amount) return
    setLoading(true); setError(null)
    try {
      const r = await checkQSBS({ ...form, fund_size: fund.fund_size })
      setResult(r)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Analysis failed')
    } finally {
      setLoading(false)
    }
  }

  const boolChecks: { key: keyof QSBSInput; label: string; note: string }[] = [
    { key: 'incorporated_in_c_corp', label: 'C-Corporation', note: 'Must be a domestic C-Corp (not LLC, S-Corp, or partnership)' },
    { key: 'domestic_us_corp', label: 'US Domestic Corporation', note: 'Organized under US state law' },
    { key: 'active_business', label: 'Active Trade or Business', note: 'Cannot be professional services, finance, insurance, or holding company' },
    { key: 'assets_at_issuance_under_50m', label: 'Assets ≤ $50M at Issuance', note: 'Aggregate gross assets at time of stock issuance' },
    { key: 'original_issuance', label: 'Original Issuance', note: 'Acquired directly from corporation (not secondary market)' },
    { key: 'issuance_date_post_july_2025', label: 'Issued After July 4, 2025', note: 'New $15M exclusion cap applies (vs $10M prior)' },
  ]

  return (
    <div className="space-y-5">
      <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-5 space-y-4">
        <div>
          <h3 className="text-sm font-semibold text-slate-200 mb-1">QSBS Eligibility (IRC §1202)</h3>
          <p className="text-xs text-slate-500">
            Qualified Small Business Stock: eligible gains excluded from federal income tax
            (up to $10M or $15M per taxpayer post-July 4, 2025).
          </p>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div className="col-span-2">
            <label className="block text-xs font-medium text-slate-400 mb-1">Company Name</label>
            <input
              type="text"
              value={form.company_name}
              onChange={e => setForm(f => ({...f, company_name: e.target.value}))}
              className="w-full bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-slate-100 text-sm focus:outline-none focus:border-emerald-500"
              placeholder="Acme AI"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-400 mb-1">Investment Amount ($M)</label>
            <input type="number" value={form.investment_amount || ''} onChange={e => setForm(f => ({...f, investment_amount: parseFloat(e.target.value) || 0}))} className="w-full bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-slate-100 text-sm focus:outline-none focus:border-emerald-500" />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-400 mb-1">Years Held</label>
            <input type="number" step={0.5} value={form.holding_period_years || ''} onChange={e => setForm(f => ({...f, holding_period_years: parseFloat(e.target.value) || 0}))} className="w-full bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-slate-100 text-sm focus:outline-none focus:border-emerald-500" />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-400 mb-1">LP Count</label>
            <input type="number" value={form.lp_count} onChange={e => setForm(f => ({...f, lp_count: parseInt(e.target.value) || 50}))} className="w-full bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-slate-100 text-sm focus:outline-none focus:border-emerald-500" />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-400 mb-1">LP Marginal Tax Rate</label>
            <div className="flex items-center gap-1.5">
              <input type="number" value={Math.round(form.lp_marginal_tax_rate * 100)} step={1} onChange={e => setForm(f => ({...f, lp_marginal_tax_rate: (parseFloat(e.target.value) || 37) / 100}))} className="flex-1 bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-slate-100 text-sm focus:outline-none focus:border-emerald-500" />
              <span className="text-slate-400 text-sm">%</span>
            </div>
          </div>
        </div>

        <div className="space-y-2">
          <div className="text-xs font-medium text-slate-400 mb-1">Eligibility Checklist</div>
          {boolChecks.map(({ key, label, note }) => (
            <label key={String(key)} className="flex items-start gap-3 cursor-pointer group">
              <input
                type="checkbox"
                checked={form[key] as boolean}
                onChange={e => setForm(f => ({...f, [key]: e.target.checked}))}
                className="mt-0.5 w-4 h-4 accent-emerald-500 cursor-pointer"
              />
              <div>
                <div className="text-sm text-slate-200 group-hover:text-slate-100">{label}</div>
                <div className="text-xs text-slate-500">{note}</div>
              </div>
            </label>
          ))}
        </div>

        <button
          onClick={run}
          disabled={loading || !form.company_name || !form.investment_amount}
          className={`w-full py-2.5 rounded-xl font-semibold text-sm transition-colors
            ${!loading && form.company_name && form.investment_amount
              ? 'bg-emerald-600 hover:bg-emerald-500 text-white'
              : 'bg-slate-700 text-slate-500 cursor-not-allowed'
            }`}
        >
          {loading ? 'Checking eligibility…' : 'Check QSBS Eligibility'}
        </button>
      </div>

      {error && (
        <div className="text-xs text-red-300 bg-red-950/30 border border-red-800/20 rounded-lg p-3">{error}</div>
      )}

      {result && (
        <div className={`border rounded-xl p-5 space-y-4 ${result.is_eligible ? 'bg-emerald-950/30 border-emerald-700/30' : 'bg-red-950/20 border-red-800/20'}`}>
          <div className="flex items-center gap-3">
            <span className={`text-2xl ${result.is_eligible ? 'text-emerald-400' : 'text-red-400'}`}>
              {result.is_eligible ? '✓' : '✗'}
            </span>
            <div>
              <div className={`text-lg font-bold ${result.is_eligible ? 'text-emerald-400' : 'text-red-400'}`}>
                {result.is_eligible ? 'QSBS Eligible' : 'Not QSBS Eligible'}
              </div>
              <div className="text-xs text-slate-500">
                {result.holding_period_satisfied ? '5-year holding period satisfied' : `${result.years_remaining_to_qualify?.toFixed(1)} more years needed for exclusion`}
              </div>
            </div>
          </div>

          {result.is_eligible && result.holding_period_satisfied && (
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div className="bg-slate-900/50 rounded-lg p-3">
                <div className="text-xs text-slate-500">Exclusion cap / taxpayer</div>
                <div className="text-lg font-bold text-emerald-400">${fmt(result.exclusion_cap_per_taxpayer)}M</div>
                <div className="text-xs text-slate-500">{result.irc_citation}</div>
              </div>
              <div className="bg-slate-900/50 rounded-lg p-3">
                <div className="text-xs text-slate-500">Est. tax saved / LP</div>
                <div className="text-lg font-bold text-emerald-400">${fmt(result.estimated_federal_tax_saved_per_lp)}M</div>
                <div className="text-xs text-slate-500">at {pct(0.37)} marginal rate</div>
              </div>
              <div className="col-span-2 bg-slate-900/50 rounded-lg p-3">
                <div className="text-xs text-slate-500">Total LP benefit (all {result.estimated_total_lp_benefit ? form.lp_count : '?'} LPs)</div>
                <div className="text-2xl font-bold text-emerald-400">${fmt(result.estimated_total_lp_benefit)}M</div>
                <div className="text-xs text-slate-600">Each LP separately qualifies; assumes equal ownership</div>
              </div>
            </div>
          )}

          <div className="space-y-1">
            {result.notes.map((n, i) => (
              <div key={i} className="text-xs text-slate-400 flex items-start gap-2">
                <span>ℹ</span><span>{n}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Anti-Dilution Modeler
// ---------------------------------------------------------------------------
function AntiDilutionModeler() {
  const [form, setForm] = useState<AntiDilutionInput>({
    company_name: '',
    original_price_per_share: 0,
    original_shares: 0,
    down_round_price_per_share: 0,
    down_round_new_shares_issued: 0,
    anti_dilution_type: 'broad_based_wa',
    investor_preferred_shares: 0,
  })
  const [result, setResult] = useState<AntiDilutionOutput | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function run() {
    setLoading(true); setError(null)
    try {
      const r = await analyzeAntiDilution(form)
      setResult(r)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Analysis failed')
    } finally { setLoading(false) }
  }

  const ok = form.company_name && form.original_price_per_share && form.original_shares && form.down_round_price_per_share && form.investor_preferred_shares

  return (
    <div className="space-y-5">
      <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-5 space-y-4">
        <div>
          <h3 className="text-sm font-semibold text-slate-200 mb-1">Anti-Dilution Modeler</h3>
          <p className="text-xs text-slate-500">
            Model the anti-dilution adjustment for a down round.
            Compare full ratchet vs. broad-based weighted average.
          </p>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div className="col-span-2">
            <label className="block text-xs font-medium text-slate-400 mb-1">Company</label>
            <input type="text" value={form.company_name} onChange={e => setForm(f => ({...f, company_name: e.target.value}))} className="w-full bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-slate-100 text-sm focus:outline-none focus:border-emerald-500" placeholder="Acme AI" />
          </div>
          {[
            { key: 'original_price_per_share' as const, label: 'Original Price / Share ($)' },
            { key: 'original_shares' as const, label: 'Total Shares Outstanding' },
            { key: 'down_round_price_per_share' as const, label: 'Down Round Price / Share ($)' },
            { key: 'down_round_new_shares_issued' as const, label: 'New Shares in Down Round' },
            { key: 'investor_preferred_shares' as const, label: 'Your Preferred Shares' },
          ].map(({ key, label }) => (
            <div key={key}>
              <label className="block text-xs font-medium text-slate-400 mb-1">{label}</label>
              <input type="number" value={(form[key] as number) || ''} onChange={e => setForm(f => ({...f, [key]: parseFloat(e.target.value) || 0}))} className="w-full bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-slate-100 text-sm focus:outline-none focus:border-emerald-500" />
            </div>
          ))}
          <div className="col-span-2">
            <label className="block text-xs font-medium text-slate-400 mb-1">Anti-Dilution Type</label>
            <select value={form.anti_dilution_type} onChange={e => setForm(f => ({...f, anti_dilution_type: e.target.value as any}))} className="w-full bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-slate-100 text-sm focus:outline-none focus:border-emerald-500">
              <option value="none">None</option>
              <option value="broad_based_wa">Broad-Based Weighted Average</option>
              <option value="full_ratchet">Full Ratchet</option>
            </select>
          </div>
        </div>
        <button onClick={run} disabled={!ok || loading} className={`w-full py-2.5 rounded-xl font-semibold text-sm transition-colors ${ok && !loading ? 'bg-emerald-600 hover:bg-emerald-500 text-white' : 'bg-slate-700 text-slate-500 cursor-not-allowed'}`}>
          {loading ? 'Computing…' : 'Compute Adjustment'}
        </button>
      </div>

      {error && <div className="text-xs text-red-300 bg-red-950/30 border border-red-800/20 rounded-lg p-3">{error}</div>}

      {result && (
        <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-5 space-y-3">
          <h4 className="text-sm font-semibold text-slate-200">
            {result.anti_dilution_type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())} Result
          </h4>
          <div className="grid grid-cols-2 gap-3 text-sm">
            <MetricBox label="Original Price" value={`$${fmt(result.original_price, 4)}`} />
            <MetricBox label="Down Round Price" value={`$${fmt(result.down_round_price, 4)}`} />
            <MetricBox label="Adjusted Conv. Price" value={`$${fmt(result.adjusted_conversion_price, 4)}`} highlight />
            <MetricBox label="Additional Shares" value={fmt(result.additional_shares_issued, 0)} />
            <MetricBox label="Value Transferred" value={`$${fmt(result.economic_impact)}M`} />
            <MetricBox label="New Ownership %" value={pct(result.effective_ownership_pct_after)} highlight />
          </div>
          <div className="text-xs text-slate-400 bg-slate-900/50 rounded-lg p-3">{result.notes}</div>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Bridge Round Modeler
// ---------------------------------------------------------------------------
function BridgeModeler() {
  const [form, setForm] = useState<BridgeRoundInput>({
    company_name: '',
    bridge_amount: 0,
    instrument: 'safe',
    discount_rate: 0.20,
    interest_rate: 0,
    maturity_months: 18,
    pre_bridge_valuation: 0,
    expected_next_round_valuation: 0,
    current_ownership_pct: 0,
    fund_is_participating: true,
    pro_rata_amount: 0,
  })
  const [result, setResult] = useState<BridgeRoundOutput | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function run() {
    setLoading(true); setError(null)
    try {
      const r = await analyzeBridge(form)
      setResult(r)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Analysis failed')
    } finally { setLoading(false) }
  }

  const ok = form.company_name && form.bridge_amount && form.pre_bridge_valuation && form.current_ownership_pct

  return (
    <div className="space-y-5">
      <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-5 space-y-4">
        <div>
          <h3 className="text-sm font-semibold text-slate-200 mb-1">Bridge / Extension Round Modeler</h3>
          <p className="text-xs text-slate-500">
            Analyze the dilution impact and conversion economics of a bridge round.
          </p>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div className="col-span-2">
            <label className="block text-xs font-medium text-slate-400 mb-1">Company</label>
            <input type="text" value={form.company_name} onChange={e => setForm(f => ({...f, company_name: e.target.value}))} className="w-full bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-slate-100 text-sm focus:outline-none focus:border-emerald-500" placeholder="Acme AI" />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-400 mb-1">Bridge Amount ($M)</label>
            <input type="number" value={form.bridge_amount || ''} onChange={e => setForm(f => ({...f, bridge_amount: parseFloat(e.target.value) || 0}))} className="w-full bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-slate-100 text-sm focus:outline-none focus:border-emerald-500" />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-400 mb-1">Instrument</label>
            <select value={form.instrument} onChange={e => setForm(f => ({...f, instrument: e.target.value}))} className="w-full bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-slate-100 text-sm focus:outline-none focus:border-emerald-500">
              <option value="safe">SAFE</option>
              <option value="convertible_note">Convertible Note</option>
              <option value="equity">Equity</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-400 mb-1">Discount Rate (%)</label>
            <input type="number" value={Math.round(form.discount_rate * 100)} step={5} onChange={e => setForm(f => ({...f, discount_rate: (parseFloat(e.target.value) || 20) / 100}))} className="w-full bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-slate-100 text-sm focus:outline-none focus:border-emerald-500" />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-400 mb-1">Pre-Bridge Valuation ($M)</label>
            <input type="number" value={form.pre_bridge_valuation || ''} onChange={e => setForm(f => ({...f, pre_bridge_valuation: parseFloat(e.target.value) || 0}))} className="w-full bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-slate-100 text-sm focus:outline-none focus:border-emerald-500" />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-400 mb-1">Expected Next Round ($M)</label>
            <input type="number" value={form.expected_next_round_valuation || ''} onChange={e => setForm(f => ({...f, expected_next_round_valuation: parseFloat(e.target.value) || 0}))} className="w-full bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-slate-100 text-sm focus:outline-none focus:border-emerald-500" />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-400 mb-1">Current Ownership (%)</label>
            <input type="number" step={0.1} value={Math.round(form.current_ownership_pct * 1000) / 10 || ''} onChange={e => setForm(f => ({...f, current_ownership_pct: (parseFloat(e.target.value) || 0) / 100}))} className="w-full bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-slate-100 text-sm focus:outline-none focus:border-emerald-500" />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-400 mb-1">Maturity (months)</label>
            <input type="number" value={form.maturity_months} step={6} onChange={e => setForm(f => ({...f, maturity_months: parseInt(e.target.value) || 18}))} className="w-full bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-slate-100 text-sm focus:outline-none focus:border-emerald-500" />
          </div>
        </div>
        <button onClick={run} disabled={!ok || loading} className={`w-full py-2.5 rounded-xl font-semibold text-sm transition-colors ${ok && !loading ? 'bg-emerald-600 hover:bg-emerald-500 text-white' : 'bg-slate-700 text-slate-500 cursor-not-allowed'}`}>
          {loading ? 'Analyzing…' : 'Analyze Bridge Round'}
        </button>
      </div>

      {error && <div className="text-xs text-red-300 bg-red-950/30 border border-red-800/20 rounded-lg p-3">{error}</div>}

      {result && (
        <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-5 space-y-4">
          <h4 className="text-sm font-semibold text-slate-200">Bridge Analysis — {result.company_name}</h4>
          <div className="grid grid-cols-2 gap-3 text-sm">
            <MetricBox label="Pre-Bridge Ownership" value={pct(result.pre_bridge_ownership)} />
            <MetricBox label="Post-Bridge Ownership" value={pct(result.post_bridge_ownership_if_convert)} highlight />
            <MetricBox label="Dilution from Bridge" value={pct(result.dilution_from_bridge)} />
            <MetricBox label="Effective Conv. Price" value={`$${fmt(result.effective_conversion_price, 0)}M`} />
            <MetricBox label="Implied Discount" value={pct(result.implied_discount_to_next_round)} />
            {result.additional_runway_months && <MetricBox label="Runway Added (est.)" value={`${result.additional_runway_months.toFixed(0)} mo`} />}
          </div>
          <div className="bg-emerald-950/20 border border-emerald-700/20 rounded-lg p-3">
            <div className="text-xs font-medium text-emerald-400 mb-1">Recommendation</div>
            <div className="text-sm text-slate-300">{result.recommendation}</div>
          </div>
          <div className="space-y-1">
            {result.notes.map((n, i) => (
              <div key={i} className="text-xs text-slate-500 flex items-start gap-2"><span>ℹ</span><span>{n}</span></div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function MetricBox({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-2.5">
      <div className="text-xs text-slate-500">{label}</div>
      <div className={`text-sm font-semibold mt-0.5 ${highlight ? 'text-emerald-400' : 'text-slate-200'}`}>{value}</div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------
export default function VCGovernanceTools({ fund }: Props) {
  const [tool, setTool] = useState<GovernanceTool>('qsbs')

  const tools: { id: GovernanceTool; label: string; description: string }[] = [
    { id: 'qsbs', label: 'QSBS §1202', description: 'IRC §1202 eligibility screener + LP tax benefit' },
    { id: 'antidilution', label: 'Anti-Dilution', description: 'Full ratchet vs. broad-based WA in down rounds' },
    { id: 'bridge', label: 'Bridge Round', description: 'SAFE / convertible note bridge analysis' },
  ]

  return (
    <div className="space-y-5">
      {/* Tool selector */}
      <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-3">
        <div className="grid grid-cols-3 gap-2">
          {tools.map(t => (
            <button
              key={t.id}
              onClick={() => setTool(t.id)}
              className={`p-3 rounded-lg text-left transition-all ${
                tool === t.id
                  ? 'bg-emerald-700/30 border border-emerald-600/30'
                  : 'hover:bg-slate-700/50'
              }`}
            >
              <div className={`text-xs font-semibold ${tool === t.id ? 'text-emerald-400' : 'text-slate-300'}`}>
                {t.label}
              </div>
              <div className="text-xs text-slate-500 mt-0.5">{t.description}</div>
            </button>
          ))}
        </div>
      </div>

      {tool === 'qsbs' && <QSBSScreener fund={fund} />}
      {tool === 'antidilution' && <AntiDilutionModeler />}
      {tool === 'bridge' && <BridgeModeler />}
    </div>
  )
}
