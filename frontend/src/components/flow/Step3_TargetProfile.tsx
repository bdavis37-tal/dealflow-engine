import React, { useState } from 'react'
import { ArrowLeft, ArrowRight, ChevronDown, ChevronUp, Shield } from 'lucide-react'
import CurrencyInput from '../inputs/CurrencyInput'
import GuidedInput from '../inputs/GuidedInput'
import type {
  TargetProfile, Industry, ModelMode, DefenseProfile,
  ClearanceLevel, ContractVehicleType, DeploymentClassification, DefenseSoftwareType
} from '../../types/deal'

const INDUSTRIES: Industry[] = [
  'Software / SaaS', 'Healthcare Services', 'Manufacturing',
  'Professional Services / Consulting', 'HVAC / Mechanical Contracting',
  'Construction', 'Restaurants / Food Service', 'Retail',
  'Financial Services', 'Oil & Gas Services', 'Transportation / Logistics',
  'Real Estate Services', 'Technology Hardware', 'Pharmaceuticals',
  'Telecommunications', 'Agriculture', 'Media / Entertainment',
  'Insurance', 'Staffing / Recruiting', 'Waste Management',
  'Defense & National Security',
]

const CLEARANCE_LEVELS: { value: ClearanceLevel; label: string; desc: string }[] = [
  { value: 'unclassified', label: 'Unclassified', desc: 'No facility clearance required' },
  { value: 'secret', label: 'Secret', desc: 'Standard classified work' },
  { value: 'top_secret', label: 'Top Secret', desc: 'High-level classified programs' },
  { value: 'ts_sci', label: 'Top Secret/SCI', desc: 'Highest level — significant barrier to entry' },
  { value: 'sap', label: 'SAP', desc: 'Special Access Programs — compartmented' },
]

const CONTRACT_VEHICLES: ContractVehicleType[] = [
  'OTA (Other Transaction Authority)',
  'GWAC (Government-Wide Acquisition Contract)',
  'IDIQ (Indefinite Delivery/Indefinite Quantity)',
  'BPA (Blanket Purchase Agreement)',
  'SBIR/STTR',
  'Prime Contract',
  'Subcontract',
]

const DEPLOYMENT_OPTIONS: { value: DeploymentClassification; label: string }[] = [
  { value: 'cloud_il2', label: 'Cloud IL2' },
  { value: 'cloud_il4', label: 'Cloud IL4' },
  { value: 'cloud_il5', label: 'Cloud IL5' },
  { value: 'cloud_il6', label: 'Cloud IL6' },
  { value: 'on_prem_scif', label: 'On-Prem (SCIF)' },
  { value: 'edge_tactical', label: 'Edge / Tactical' },
  { value: 'ddil', label: 'DDIL (Disconnected)' },
]

const SOFTWARE_TYPES: DefenseSoftwareType[] = [
  'C2 (Command & Control)',
  'ISR Processing',
  'Logistics / Supply Chain',
  'Predictive Maintenance',
  'Cybersecurity',
  'Decision Support',
  'Autonomous Systems',
  'Training / Simulation',
]

const CERT_OPTIONS = [
  'FedRAMP Moderate', 'FedRAMP High', 'IL4', 'IL5', 'IL6',
  'CMMC Level 2', 'CMMC Level 3', 'SOC2', 'StateRAMP',
]

const DEFAULT_DEFENSE_PROFILE: DefenseProfile = {
  is_ai_native: false,
  contract_backlog_total: 0,
  contract_backlog_funded: 0,
  idiq_ceiling_value: 0,
  contract_vehicles: [],
  clearance_level: 'unclassified',
  authorization_certifications: [],
  customer_concentration_dod_pct: 0,
  programs_of_record: 0,
  deployment_classification: [],
  software_type: [],
  ip_ownership: 'company_owned',
}

interface Step3Props {
  target: Partial<TargetProfile>
  mode: ModelMode
  onUpdate: (updates: Partial<TargetProfile>) => void
  onNext: () => void
  onBack: () => void
}

export default function Step3_TargetProfile({ target, mode, onUpdate, onNext, onBack }: Step3Props) {
  const [showAssumptions, setShowAssumptions] = useState(false)
  const [errors, setErrors] = useState<Record<string, string>>({})

  const validate = () => {
    const errs: Record<string, string> = {}
    if (!target.revenue || target.revenue <= 0) errs.revenue = 'Required'
    if (target.ebitda === undefined) errs.ebitda = 'Required'
    if (!target.industry) errs.industry = 'Required'
    setErrors(errs)
    return Object.keys(errs).length === 0
  }

  const handleRevenueChange = (v: number) => {
    const updates: Partial<TargetProfile> = { revenue: v }
    // Auto-estimate fields from revenue if in quick mode
    if (mode === 'quick' && v > 0) {
      if (!target.ebitda) updates.ebitda = Math.round(v * 0.12)
      if (!target.net_income) updates.net_income = Math.round(v * 0.07)
      if (!target.depreciation) updates.depreciation = Math.round(v * 0.04)
      if (!target.capex) updates.capex = Math.round(v * 0.03)
      if (!target.working_capital) updates.working_capital = Math.round(v * 0.10)
    }
    onUpdate(updates)
  }

  return (
    <div className="max-w-2xl mx-auto animate-slide-up">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-100 mb-2">
          Tell us about the company you're buying.
        </h1>
        <p className="text-slate-400">
          {mode === 'quick'
            ? "Revenue and profitability are the key inputs. We'll estimate the rest from industry benchmarks."
            : 'Enter the target\'s full financial profile for the most accurate model.'
          }
        </p>
      </div>

      <div className="space-y-6">
        <div className="space-y-1.5">
          <label className="text-sm font-medium text-slate-300">Industry *</label>
          <select
            value={target.industry ?? ''}
            onChange={e => onUpdate({ industry: e.target.value as Industry })}
            className="w-full bg-slate-800/40 border border-slate-700 rounded-lg px-3 py-2.5 text-sm text-slate-100 outline-none focus:border-blue-500/60 transition-colors"
          >
            <option value="">Select target's industry...</option>
            {INDUSTRIES.map(ind => <option key={ind} value={ind}>{ind}</option>)}
          </select>
          {errors.industry && <p className="text-xs text-red-400">{errors.industry}</p>}
        </div>

        <div className="rounded-xl border border-slate-700 bg-slate-800/20 p-5 space-y-4">
          <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Financials</h3>
          <CurrencyInput
            label="Annual Revenue"
            value={target.revenue ?? 0}
            onChange={handleRevenueChange}
            help="The target's total annual sales."
            error={errors.revenue}
            required
          />
          <CurrencyInput
            label="Annual EBITDA"
            value={target.ebitda ?? 0}
            onChange={v => onUpdate({ ebitda: v })}
            help="Operating profit before interest, taxes, and accounting adjustments."
            error={errors.ebitda}
            required
          />
          <CurrencyInput
            label="Annual Net Income"
            value={target.net_income ?? 0}
            onChange={v => onUpdate({ net_income: v })}
            help="After-tax profit."
          />
        </div>

        {/* Assumptions panel for Quick Model */}
        {mode === 'quick' && (
          <div className="rounded-xl border border-slate-700/50 bg-slate-800/10 overflow-hidden">
            <button
              onClick={() => setShowAssumptions(v => !v)}
              className="w-full flex items-center justify-between px-5 py-3 text-sm text-slate-400 hover:text-slate-300 transition-colors"
            >
              <span>Our assumptions (auto-calculated from your inputs)</span>
              {showAssumptions ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
            </button>
            {showAssumptions && (
              <div className="px-5 pb-5 space-y-4 border-t border-slate-700/50 pt-4 animate-fade-in">
                <p className="text-xs text-slate-500">These are estimated from industry benchmarks. Switch to Deep Model to customize them.</p>
                <div className="grid grid-cols-2 gap-4">
                  <div className="text-xs text-slate-400">
                    <span className="text-slate-500">Revenue growth rate</span>
                    <div className="text-slate-200 font-medium tabular-nums">5% / year</div>
                  </div>
                  <div className="text-xs text-slate-400">
                    <span className="text-slate-500">Tax rate</span>
                    <div className="text-slate-200 font-medium tabular-nums">25%</div>
                  </div>
                  <div className="text-xs text-slate-400">
                    <span className="text-slate-500">D&A</span>
                    <div className="text-slate-200 font-medium tabular-nums">4% of revenue</div>
                  </div>
                  <div className="text-xs text-slate-400">
                    <span className="text-slate-500">CapEx</span>
                    <div className="text-slate-200 font-medium tabular-nums">3% of revenue</div>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Deep model extras */}
        {mode === 'deep' && (
          <div className="rounded-xl border border-blue-900/40 bg-blue-950/10 p-5 space-y-4">
            <h3 className="text-xs font-semibold text-blue-400 uppercase tracking-wider">Deep Model — Additional Inputs</h3>
            <div className="grid grid-cols-2 gap-4">
              <CurrencyInput label="Total Debt" value={target.total_debt ?? 0} onChange={v => onUpdate({ total_debt: v })} help="Debt assumed or refinanced at close." />
              <CurrencyInput label="Cash Acquired" value={target.cash_on_hand ?? 0} onChange={v => onUpdate({ cash_on_hand: v })} help="Cash acquired with the business." />
              <CurrencyInput label="D&A" value={target.depreciation ?? 0} onChange={v => onUpdate({ depreciation: v })} />
              <CurrencyInput label="CapEx" value={target.capex ?? 0} onChange={v => onUpdate({ capex: v })} />
              <CurrencyInput label="Net Working Capital" value={target.working_capital ?? 0} onChange={v => onUpdate({ working_capital: v })} />
            </div>
            <GuidedInput
              label="Annual Revenue Growth Rate"
              value={target.revenue_growth_rate ? (target.revenue_growth_rate * 100).toFixed(1) : '5.0'}
              onChange={v => onUpdate({ revenue_growth_rate: Number(v) / 100 })}
              type="number" suffix="%" min={-20} max={100}
              help="Expected annual revenue growth over the 5-year projection period."
            />
          </div>
        )}

        {/* Defense & National Security specific inputs */}
        {target.industry === 'Defense & National Security' && (() => {
          const dp = target.defense_profile ?? DEFAULT_DEFENSE_PROFILE
          const updateDefense = (updates: Partial<DefenseProfile>) => {
            onUpdate({ defense_profile: { ...dp, ...updates } })
          }
          return (
            <div className="rounded-xl border border-emerald-900/40 bg-emerald-950/10 p-5 space-y-5">
              <div className="flex items-center gap-2">
                <Shield size={16} className="text-emerald-400" />
                <h3 className="text-xs font-semibold text-emerald-400 uppercase tracking-wider">Defense & National Security Profile</h3>
              </div>

              {/* AI Toggle */}
              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={dp.is_ai_native}
                  onChange={e => updateDefense({ is_ai_native: e.target.checked })}
                  className="w-4 h-4 rounded border-slate-600 bg-slate-800 text-emerald-500 focus:ring-emerald-500/30"
                />
                <div>
                  <span className="text-sm font-medium text-slate-200">AI-native defense company</span>
                  <p className="text-xs text-slate-500">Shifts valuation to AI-comparable multiples (EV/Revenue) rather than traditional defense (EV/EBITDA)</p>
                </div>
              </label>

              {/* Contract Backlog */}
              <div className="space-y-4">
                <h4 className="text-xs font-medium text-slate-400">Contract Backlog</h4>
                <CurrencyInput
                  label="Total Contract Backlog"
                  value={dp.contract_backlog_total}
                  onChange={v => updateDefense({ contract_backlog_total: v })}
                  help="All awarded contracts not yet recognized as revenue. This is the single biggest valuation driver in defense."
                />
                <CurrencyInput
                  label="Funded Backlog"
                  value={dp.contract_backlog_funded}
                  onChange={v => updateDefense({ contract_backlog_funded: v })}
                  help="Government-obligated portion. Funded backlog is near-certain revenue."
                />
                <CurrencyInput
                  label="IDIQ Ceiling Value"
                  value={dp.idiq_ceiling_value}
                  onChange={v => updateDefense({ idiq_ceiling_value: v })}
                  help="Total ceiling of IDIQ contracts. Represents addressable revenue under existing vehicles."
                />
              </div>

              {/* Clearance Level */}
              <div className="space-y-2">
                <label className="text-xs font-medium text-slate-400">Facility Clearance Level</label>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                  {CLEARANCE_LEVELS.map(cl => (
                    <button
                      key={cl.value}
                      type="button"
                      onClick={() => updateDefense({ clearance_level: cl.value })}
                      className={`text-left px-3 py-2 rounded-lg border text-xs transition-all ${
                        dp.clearance_level === cl.value
                          ? 'border-emerald-500/60 bg-emerald-900/20 text-emerald-300'
                          : 'border-slate-700 bg-slate-800/30 text-slate-400 hover:border-slate-600'
                      }`}
                    >
                      <div className="font-medium">{cl.label}</div>
                      <div className="text-2xs text-slate-500 mt-0.5">{cl.desc}</div>
                    </button>
                  ))}
                </div>
              </div>

              {/* Contract Vehicles */}
              <div className="space-y-2">
                <label className="text-xs font-medium text-slate-400">Contract Vehicles Held</label>
                <div className="flex flex-wrap gap-2">
                  {CONTRACT_VEHICLES.map(cv => (
                    <button
                      key={cv}
                      type="button"
                      onClick={() => {
                        const current = dp.contract_vehicles
                        updateDefense({
                          contract_vehicles: current.includes(cv)
                            ? current.filter(v => v !== cv)
                            : [...current, cv]
                        })
                      }}
                      className={`px-3 py-1.5 rounded-lg border text-xs transition-all ${
                        dp.contract_vehicles.includes(cv)
                          ? 'border-emerald-500/60 bg-emerald-900/20 text-emerald-300'
                          : 'border-slate-700 bg-slate-800/30 text-slate-400 hover:border-slate-600'
                      }`}
                    >
                      {cv}
                    </button>
                  ))}
                </div>
              </div>

              {/* Certifications */}
              <div className="space-y-2">
                <label className="text-xs font-medium text-slate-400">Authorization & Certifications</label>
                <div className="flex flex-wrap gap-2">
                  {CERT_OPTIONS.map(cert => (
                    <button
                      key={cert}
                      type="button"
                      onClick={() => {
                        const current = dp.authorization_certifications
                        updateDefense({
                          authorization_certifications: current.includes(cert)
                            ? current.filter(c => c !== cert)
                            : [...current, cert]
                        })
                      }}
                      className={`px-3 py-1.5 rounded-lg border text-xs transition-all ${
                        dp.authorization_certifications.includes(cert)
                          ? 'border-emerald-500/60 bg-emerald-900/20 text-emerald-300'
                          : 'border-slate-700 bg-slate-800/30 text-slate-400 hover:border-slate-600'
                      }`}
                    >
                      {cert}
                    </button>
                  ))}
                </div>
              </div>

              {/* Programs of Record & DoD Concentration */}
              <div className="grid grid-cols-2 gap-4">
                <GuidedInput
                  label="Programs of Record"
                  value={String(dp.programs_of_record)}
                  onChange={v => updateDefense({ programs_of_record: Math.max(0, parseInt(v) || 0) })}
                  type="number" min={0} max={50}
                  help="Number of DoD programs of record the software is embedded in. Being on a POR means multi-year guaranteed funding."
                />
                <GuidedInput
                  label="DoD Revenue %"
                  value={(dp.customer_concentration_dod_pct * 100).toFixed(0)}
                  onChange={v => updateDefense({ customer_concentration_dod_pct: Math.min(1, Math.max(0, Number(v) / 100)) })}
                  type="number" suffix="%" min={0} max={100}
                  help="Percentage of revenue from Department of Defense."
                />
              </div>

              {/* Deployment & Software Type */}
              <div className="space-y-2">
                <label className="text-xs font-medium text-slate-400">Deployment Environment</label>
                <div className="flex flex-wrap gap-2">
                  {DEPLOYMENT_OPTIONS.map(d => (
                    <button
                      key={d.value}
                      type="button"
                      onClick={() => {
                        const current = dp.deployment_classification
                        updateDefense({
                          deployment_classification: current.includes(d.value)
                            ? current.filter(v => v !== d.value)
                            : [...current, d.value]
                        })
                      }}
                      className={`px-3 py-1.5 rounded-lg border text-xs transition-all ${
                        dp.deployment_classification.includes(d.value)
                          ? 'border-emerald-500/60 bg-emerald-900/20 text-emerald-300'
                          : 'border-slate-700 bg-slate-800/30 text-slate-400 hover:border-slate-600'
                      }`}
                    >
                      {d.label}
                    </button>
                  ))}
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-xs font-medium text-slate-400">Software Category</label>
                <div className="flex flex-wrap gap-2">
                  {SOFTWARE_TYPES.map(st => (
                    <button
                      key={st}
                      type="button"
                      onClick={() => {
                        const current = dp.software_type
                        updateDefense({
                          software_type: current.includes(st)
                            ? current.filter(v => v !== st)
                            : [...current, st]
                        })
                      }}
                      className={`px-3 py-1.5 rounded-lg border text-xs transition-all ${
                        dp.software_type.includes(st)
                          ? 'border-emerald-500/60 bg-emerald-900/20 text-emerald-300'
                          : 'border-slate-700 bg-slate-800/30 text-slate-400 hover:border-slate-600'
                      }`}
                    >
                      {st}
                    </button>
                  ))}
                </div>
              </div>

              {/* IP Ownership */}
              <div className="space-y-2">
                <label className="text-xs font-medium text-slate-400">IP Ownership</label>
                <select
                  value={dp.ip_ownership}
                  onChange={e => updateDefense({ ip_ownership: e.target.value })}
                  className="w-full bg-slate-800/40 border border-slate-700 rounded-lg px-3 py-2.5 text-sm text-slate-100 outline-none focus:border-emerald-500/60 transition-colors"
                >
                  <option value="company_owned">Company Owned (full IP rights)</option>
                  <option value="government_purpose_rights">Government Purpose Rights (limited govt use)</option>
                  <option value="unlimited_rights">Government Unlimited Rights (govt can share freely)</option>
                </select>
                <p className="text-2xs text-slate-500">Software IP ownership varies by contract type. SBIR/STTR provides strongest protections.</p>
              </div>
            </div>
          )
        })()}
      </div>

      <div className="flex gap-3 mt-8">
        <button onClick={onBack} className="flex items-center gap-2 px-5 py-3 rounded-xl border border-slate-700 text-slate-300 hover:border-slate-600 text-sm transition-all">
          <ArrowLeft size={16} /> Back
        </button>
        <button onClick={() => validate() && onNext()} className="flex-1 flex items-center justify-center gap-2 px-6 py-3 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-semibold text-sm transition-all">
          Continue <ArrowRight size={16} />
        </button>
      </div>
    </div>
  )
}
