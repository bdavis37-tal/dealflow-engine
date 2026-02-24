/**
 * VCFundSetup — Step 1 of the VC flow.
 * One-time fund profile configuration.
 * Persists to localStorage so it survives page reloads.
 */

import React, { useState } from 'react'
import type { FundProfile } from '../../types/vc'

interface Props {
  fund: FundProfile
  onUpdate: (updates: Partial<FundProfile>) => void
  onNext: () => void
}

function Field({
  label,
  hint,
  children,
}: {
  label: string
  hint?: string
  children: React.ReactNode
}) {
  return (
    <div className="space-y-1">
      <label className="block text-sm font-medium text-slate-200">{label}</label>
      {hint && <p className="text-xs text-slate-500">{hint}</p>}
      {children}
    </div>
  )
}

function NumInput({
  value,
  onChange,
  prefix,
  suffix,
  step: _step = 1,
  min = 0,
}: {
  value: number
  onChange: (v: number) => void
  prefix?: string
  suffix?: string
  step?: number
  min?: number
}) {
  const [focused, setFocused] = useState(false)
  const [raw, setRaw] = useState('')

  return (
    <div className="flex items-center gap-1.5">
      {prefix && <span className="text-slate-400 text-sm w-4">{prefix}</span>}
      <input
        type="text"
        inputMode="decimal"
        value={focused ? raw : value}
        onFocus={() => { setFocused(true); setRaw(value ? String(value) : '') }}
        onBlur={() => {
          setFocused(false)
          const parsed = parseFloat(raw)
          if (!isNaN(parsed)) onChange(Math.max(parsed, min))
        }}
        onChange={e => {
          setRaw(e.target.value)
          const parsed = parseFloat(e.target.value)
          if (!isNaN(parsed)) onChange(Math.max(parsed, min))
        }}
        className="
          flex-1 bg-slate-800 border border-slate-600 rounded-lg px-3 py-2
          text-slate-100 text-sm placeholder-slate-500
          focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500/30
        "
      />
      {suffix && <span className="text-slate-400 text-sm w-6">{suffix}</span>}
    </div>
  )
}

export default function VCFundSetup({ fund, onUpdate, onNext }: Props) {
  const [showAdvanced, setShowAdvanced] = useState(false)

  // Computed derived values
  const totalFees = fund.fund_size * fund.management_fee_pct * fund.management_fee_years
  const recyclingCredit = fund.fund_size * fund.recycling_pct
  const investable = fund.fund_size - totalFees + recyclingCredit
  const initialPool = investable * (1 - fund.reserve_ratio)
  const reservePool = investable * fund.reserve_ratio
  const impliedCheck = fund.target_initial_check_count > 0
    ? initialPool / fund.target_initial_check_count
    : 0

  return (
    <div className="max-w-2xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-3">
          <div className="w-8 h-8 rounded-lg bg-emerald-600/20 border border-emerald-500/30 flex items-center justify-center">
            <span className="text-emerald-400 text-sm font-bold">1</span>
          </div>
          <h1 className="text-2xl font-bold text-slate-100">Fund Profile</h1>
        </div>
        <p className="text-slate-400 text-sm leading-relaxed">
          Set up your fund's context once. Every deal evaluation is calibrated against this.
          The engine uses your fund size, target ownership, and reserve strategy to answer:
          <span className="text-emerald-400 font-medium"> "Does this check size matter to my fund?"</span>
        </p>
      </div>

      <div className="space-y-6">
        {/* Fund Identity */}
        <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-5 space-y-4">
          <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">Fund Identity</h3>
          <div className="grid grid-cols-2 gap-4">
            <div className="col-span-2">
              <Field label="Fund Name">
                <input
                  type="text"
                  value={fund.fund_name}
                  onChange={e => onUpdate({ fund_name: e.target.value })}
                  placeholder="e.g. Sequoia Capital Fund I"
                  className="w-full bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-slate-100 text-sm focus:outline-none focus:border-emerald-500"
                />
              </Field>
            </div>
            <Field label="Fund Size" hint="Total LP commitments (USD millions)">
              <NumInput
                value={fund.fund_size}
                onChange={v => onUpdate({ fund_size: v })}
                prefix="$"
                suffix="M"
              />
            </Field>
            <Field label="Vintage Year">
              <NumInput
                value={fund.vintage_year}
                onChange={v => onUpdate({ vintage_year: v })}
                min={2010}
                step={1}
              />
            </Field>
          </div>
        </div>

        {/* Portfolio Construction */}
        <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-5 space-y-4">
          <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">Portfolio Construction</h3>
          <div className="grid grid-cols-2 gap-4">
            <Field label="Target # Portfolio Companies" hint="Initial checks only">
              <NumInput
                value={fund.target_initial_check_count}
                onChange={v => onUpdate({ target_initial_check_count: v })}
                min={5}
                step={1}
              />
            </Field>
            <Field label="Target Initial Ownership" hint="Entry ownership goal per deal">
              <NumInput
                value={Math.round(fund.target_ownership_pct * 100)}
                onChange={v => onUpdate({ target_ownership_pct: v / 100 })}
                suffix="%"
                step={1}
                min={1}
              />
            </Field>
            <Field label="Reserve Ratio" hint="% of investable capital held for follow-ons">
              <NumInput
                value={Math.round(fund.reserve_ratio * 100)}
                onChange={v => onUpdate({ reserve_ratio: v / 100 })}
                suffix="%"
                step={5}
                min={0}
              />
            </Field>
            <Field label="Deployment Period" hint="Years to deploy initial checks">
              <NumInput
                value={fund.deployment_period_years}
                onChange={v => onUpdate({ deployment_period_years: v })}
                suffix="yrs"
                step={1}
                min={1}
              />
            </Field>
          </div>
        </div>

        {/* Economics */}
        <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-5 space-y-4">
          <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">Fund Economics</h3>
          <div className="grid grid-cols-2 gap-4">
            <Field label="Management Fee" hint="Annual fee on committed capital">
              <NumInput
                value={parseFloat((fund.management_fee_pct * 100).toFixed(1))}
                onChange={v => onUpdate({ management_fee_pct: v / 100 })}
                suffix="%"
                step={0.5}
              />
            </Field>
            <Field label="Fee Period" hint="Years fees charged on committed capital">
              <NumInput
                value={fund.management_fee_years}
                onChange={v => onUpdate({ management_fee_years: v })}
                suffix="yrs"
                step={1}
                min={1}
              />
            </Field>
            <Field label="Carry" hint="Carried interest on gains above hurdle">
              <NumInput
                value={Math.round(fund.carry_pct * 100)}
                onChange={v => onUpdate({ carry_pct: v / 100 })}
                suffix="%"
                step={5}
              />
            </Field>
            <Field label="Hurdle Rate" hint="Preferred return threshold">
              <NumInput
                value={Math.round(fund.hurdle_rate * 100)}
                onChange={v => onUpdate({ hurdle_rate: v / 100 })}
                suffix="%"
                step={1}
              />
            </Field>
          </div>
          <button
            onClick={() => setShowAdvanced(v => !v)}
            className="text-xs text-slate-500 hover:text-slate-300 transition-colors"
          >
            {showAdvanced ? '▲ Hide advanced' : '▼ Show advanced (recycling)'}
          </button>
          {showAdvanced && (
            <Field label="Recycling %" hint="Return proceeds recycled into new investments">
              <NumInput
                value={parseFloat((fund.recycling_pct * 100).toFixed(1))}
                onChange={v => onUpdate({ recycling_pct: v / 100 })}
                suffix="%"
                step={1}
              />
            </Field>
          )}
        </div>

        {/* Live Summary */}
        <div className="bg-emerald-950/40 border border-emerald-700/30 rounded-xl p-5">
          <h3 className="text-sm font-semibold text-emerald-400 mb-4 uppercase tracking-wider">Fund Math Summary</h3>
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div className="space-y-2">
              <SummaryRow label="Total management fees" value={`$${totalFees.toFixed(1)}M`} />
              <SummaryRow label="Recycling credit" value={`+$${recyclingCredit.toFixed(1)}M`} dim />
              <SummaryRow label="Investable capital" value={`$${investable.toFixed(1)}M`} highlight />
            </div>
            <div className="space-y-2">
              <SummaryRow label="Initial check pool" value={`$${initialPool.toFixed(1)}M`} />
              <SummaryRow label="Reserve pool" value={`$${reservePool.toFixed(1)}M`} />
              <SummaryRow
                label="Implied check size"
                value={impliedCheck > 0 ? `$${impliedCheck.toFixed(1)}M` : '—'}
                highlight
              />
            </div>
          </div>
          {impliedCheck > 0 && (
            <p className="mt-3 text-xs text-slate-500">
              To own {(fund.target_ownership_pct * 100).toFixed(0)}% at entry, each ${impliedCheck.toFixed(1)}M
              check targets a ~${(impliedCheck / fund.target_ownership_pct).toFixed(0)}M post-money company.
            </p>
          )}
        </div>

        <button
          onClick={onNext}
          className="w-full py-3 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold rounded-xl transition-colors"
        >
          Save Fund Profile & Evaluate a Deal →
        </button>
      </div>
    </div>
  )
}

function SummaryRow({
  label,
  value,
  highlight,
  dim,
}: {
  label: string
  value: string
  highlight?: boolean
  dim?: boolean
}) {
  return (
    <div className="flex items-center justify-between">
      <span className={dim ? 'text-slate-600 text-xs' : 'text-slate-400 text-xs'}>{label}</span>
      <span className={highlight ? 'text-emerald-400 font-semibold' : dim ? 'text-slate-600' : 'text-slate-200'}>
        {value}
      </span>
    </div>
  )
}
