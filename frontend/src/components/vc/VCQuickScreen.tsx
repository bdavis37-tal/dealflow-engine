/**
 * VCQuickScreen — Step 2 of the VC flow.
 * Single-screen deal input: 60-second screener.
 * Collects just enough info to run the full evaluation.
 */

import React, { useState } from 'react'
import type { VCDealInput, VCVertical, VCStage, FundProfile } from '../../types/vc'
import { VC_VERTICAL_LABELS, VC_STAGE_LABELS, DEFAULT_DILUTION_ASSUMPTIONS } from '../../types/vc'

interface Props {
  deal: Partial<VCDealInput>
  fund: FundProfile
  onUpdate: (updates: Partial<VCDealInput>) => void
  onBack: () => void
  onRun: () => void
  isLoading: boolean
  error: string | null
}

function Label({ children }: { children: React.ReactNode }) {
  return <label className="block text-sm font-medium text-slate-200 mb-1">{children}</label>
}

function Hint({ children }: { children: React.ReactNode }) {
  return <p className="text-xs text-slate-500 mb-1.5">{children}</p>
}

function Row({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <Label>{label}</Label>
      {hint && <Hint>{hint}</Hint>}
      {children}
    </div>
  )
}

function CurrencyInput({
  value,
  onChange,
  placeholder = '0',
  suffix = 'M',
}: {
  value: number
  onChange: (v: number) => void
  placeholder?: string
  suffix?: string
}) {
  return (
    <div className="flex items-center gap-1.5">
      <span className="text-slate-400 text-sm">$</span>
      <input
        type="number"
        value={value || ''}
        onChange={e => onChange(parseFloat(e.target.value) || 0)}
        placeholder={placeholder}
        className="flex-1 bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-slate-100 text-sm focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500/30"
      />
      <span className="text-slate-400 text-sm w-4">{suffix}</span>
    </div>
  )
}

function PctInput({
  value,
  onChange,
  step = 5,
}: {
  value: number
  onChange: (v: number) => void
  step?: number
}) {
  return (
    <div className="flex items-center gap-1.5">
      <input
        type="number"
        value={value || ''}
        step={step}
        min={0}
        max={1000}
        onChange={e => onChange(parseFloat(e.target.value) || 0)}
        className="flex-1 bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-slate-100 text-sm focus:outline-none focus:border-emerald-500"
      />
      <span className="text-slate-400 text-sm w-4">%</span>
    </div>
  )
}

function Select<T extends string>({
  value,
  onChange,
  options,
}: {
  value: T
  onChange: (v: T) => void
  options: { value: T; label: string }[]
}) {
  return (
    <select
      value={value}
      onChange={e => onChange(e.target.value as T)}
      className="w-full bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-slate-100 text-sm focus:outline-none focus:border-emerald-500 cursor-pointer"
    >
      {options.map(o => (
        <option key={o.value} value={o.value}>{o.label}</option>
      ))}
    </select>
  )
}

const VERTICAL_OPTIONS = Object.entries(VC_VERTICAL_LABELS).map(([v, l]) => ({
  value: v as VCVertical,
  label: l,
}))

const STAGE_OPTIONS = Object.entries(VC_STAGE_LABELS).map(([v, l]) => ({
  value: v as VCStage,
  label: l,
}))

const EXIT_YEAR_OPTIONS = [3, 4, 5, 6, 7, 8, 10, 12].map(y => ({
  value: String(y),
  label: `${y} years`,
}))

export default function VCQuickScreen({ deal, fund, onUpdate, onBack, onRun, isLoading, error }: Props) {
  const [showDilution, setShowDilution] = useState(false)

  const dilution = deal.dilution ?? DEFAULT_DILUTION_ASSUMPTIONS

  // Live ownership preview
  const entryPct = deal.post_money_valuation && deal.check_size
    ? deal.check_size / deal.post_money_valuation
    : null

  // Rough exit ownership after default dilution (seed stage)
  const exitPct = entryPct
    ? entryPct * (1 - dilution.seed_to_a) * (1 - dilution.a_to_b) * (1 - dilution.b_to_c) * (1 - dilution.c_to_ipo)
    : null

  const frThreshold = exitPct && exitPct > 0 ? fund.fund_size / exitPct : null

  const arrMultipleAtEntry = deal.arr && deal.arr > 0 && deal.post_money_valuation
    ? deal.post_money_valuation / deal.arr
    : null

  const runway = deal.burn_rate_monthly && deal.burn_rate_monthly > 0 && deal.cash_on_hand
    ? deal.cash_on_hand / deal.burn_rate_monthly
    : null

  const canRun = !!(deal.company_name && deal.post_money_valuation && deal.check_size && deal.vertical && deal.stage)

  return (
    <div className="max-w-2xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-3">
          <div className="w-8 h-8 rounded-lg bg-emerald-600/20 border border-emerald-500/30 flex items-center justify-center">
            <span className="text-emerald-400 text-sm font-bold">2</span>
          </div>
          <h1 className="text-2xl font-bold text-slate-100">Deal Screen</h1>
        </div>
        <p className="text-slate-400 text-sm">
          Enter the deal terms. The engine computes ownership math, fund-returner threshold,
          and a 3-scenario return model — instantly.
        </p>
      </div>

      <div className="space-y-5">
        {/* Company Identity */}
        <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-5 space-y-4">
          <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Company</h3>
          <Row label="Company Name">
            <input
              type="text"
              value={deal.company_name ?? ''}
              onChange={e => onUpdate({ company_name: e.target.value })}
              placeholder="e.g. Acme AI"
              className="w-full bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-slate-100 text-sm focus:outline-none focus:border-emerald-500"
            />
          </Row>
          <div className="grid grid-cols-2 gap-4">
            <Row label="Stage">
              <Select
                value={(deal.stage ?? 'seed') as VCStage}
                onChange={v => onUpdate({ stage: v })}
                options={STAGE_OPTIONS}
              />
            </Row>
            <Row label="Vertical">
              <Select
                value={(deal.vertical ?? 'b2b_saas') as VCVertical}
                onChange={v => onUpdate({ vertical: v })}
                options={VERTICAL_OPTIONS}
              />
            </Row>
          </div>
        </div>

        {/* Deal Terms */}
        <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-5 space-y-4">
          <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Deal Terms</h3>
          <div className="grid grid-cols-2 gap-4">
            <Row label="Post-Money Valuation" hint="Cap table post-close, USD millions">
              <CurrencyInput
                value={deal.post_money_valuation ?? 0}
                onChange={v => onUpdate({ post_money_valuation: v })}
                placeholder="e.g. 20"
              />
            </Row>
            <Row label="Your Check Size" hint="Amount you plan to invest, USD millions">
              <CurrencyInput
                value={deal.check_size ?? 0}
                onChange={v => onUpdate({ check_size: v })}
                placeholder="e.g. 2"
              />
            </Row>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <Row label="Expected Exit" hint="Years from today">
              <Select
                value={String(deal.expected_exit_years ?? 7)}
                onChange={v => onUpdate({ expected_exit_years: parseInt(v) })}
                options={EXIT_YEAR_OPTIONS}
              />
            </Row>
            <div className="space-y-3">
              <div className="flex items-center gap-4 pt-5">
                <label className="flex items-center gap-2 text-sm text-slate-300 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={deal.board_seat ?? false}
                    onChange={e => onUpdate({ board_seat: e.target.checked })}
                    className="w-4 h-4 accent-emerald-500"
                  />
                  Board Seat
                </label>
                <label className="flex items-center gap-2 text-sm text-slate-300 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={deal.pro_rata_rights ?? true}
                    onChange={e => onUpdate({ pro_rata_rights: e.target.checked })}
                    className="w-4 h-4 accent-emerald-500"
                  />
                  Pro-Rata
                </label>
              </div>
            </div>
          </div>
        </div>

        {/* Company Metrics */}
        <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-5 space-y-4">
          <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Company Metrics</h3>
          <div className="grid grid-cols-2 gap-4">
            <Row label="ARR" hint="Current annual recurring revenue, USD millions">
              <CurrencyInput
                value={deal.arr ?? 0}
                onChange={v => onUpdate({ arr: v })}
                placeholder="0 if pre-revenue"
              />
            </Row>
            <Row label="Revenue Growth" hint="Projected YoY growth rate">
              <PctInput
                value={Math.round((deal.revenue_growth_rate ?? 1.5) * 100)}
                onChange={v => onUpdate({ revenue_growth_rate: v / 100 })}
                step={10}
              />
            </Row>
            <Row label="Gross Margin">
              <PctInput
                value={Math.round((deal.gross_margin ?? 0.70) * 100)}
                onChange={v => onUpdate({ gross_margin: v / 100 })}
                step={5}
              />
            </Row>
            <Row label="Monthly Burn" hint="Net cash burn, USD millions">
              <CurrencyInput
                value={deal.burn_rate_monthly ?? 0}
                onChange={v => onUpdate({ burn_rate_monthly: v })}
                placeholder="0"
              />
            </Row>
            <Row label="Cash on Hand" hint="Current cash balance, USD millions">
              <CurrencyInput
                value={deal.cash_on_hand ?? 0}
                onChange={v => onUpdate({ cash_on_hand: v })}
                placeholder="0"
              />
            </Row>
          </div>
        </div>

        {/* Dilution Assumptions (collapsible) */}
        <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-5">
          <button
            onClick={() => setShowDilution(v => !v)}
            className="w-full flex items-center justify-between"
          >
            <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
              Dilution Assumptions
            </h3>
            <span className="text-xs text-slate-500">
              {showDilution ? '▲ Hide' : '▼ Edit (defaults: Carta 2024 medians)'}
            </span>
          </button>

          {showDilution && (
            <div className="mt-4 grid grid-cols-2 gap-4">
              {[
                { key: 'seed_to_a' as const, label: 'Seed → A dilution' },
                { key: 'a_to_b' as const, label: 'A → B dilution' },
                { key: 'b_to_c' as const, label: 'B → C dilution' },
                { key: 'c_to_ipo' as const, label: 'C → IPO dilution' },
                { key: 'option_pool_expansion' as const, label: 'Option pool / round' },
              ].map(({ key, label }) => (
                <Row key={key} label={label}>
                  <PctInput
                    value={Math.round(dilution[key] * 100)}
                    onChange={v => onUpdate({ dilution: { ...dilution, [key]: v / 100 } })}
                    step={1}
                  />
                </Row>
              ))}
            </div>
          )}
        </div>

        {/* Live Preview Box */}
        {entryPct !== null && (
          <div className="bg-emerald-950/40 border border-emerald-700/30 rounded-xl p-5">
            <h3 className="text-xs font-semibold text-emerald-400 uppercase tracking-wider mb-4">Live Preview</h3>
            <div className="grid grid-cols-2 gap-3 text-sm">
              <PreviewRow
                label="Entry ownership"
                value={`${(entryPct * 100).toFixed(1)}%`}
                flag={entryPct < (fund.target_ownership_pct * 0.7)}
                flagText="Below target"
              />
              <PreviewRow
                label="Exit ownership (est.)"
                value={exitPct ? `${(exitPct * 100).toFixed(1)}%` : '—'}
              />
              <PreviewRow
                label="Fund-returner threshold"
                value={frThreshold ? `$${frThreshold.toFixed(0)}M exit` : '—'}
              />
              {arrMultipleAtEntry !== null && (
                <PreviewRow
                  label="Entry ARR multiple"
                  value={`${arrMultipleAtEntry.toFixed(0)}x`}
                  flag={arrMultipleAtEntry > 80}
                  flagText="Elevated"
                />
              )}
              {runway !== null && (
                <PreviewRow
                  label="Runway"
                  value={`${runway.toFixed(0)} months`}
                  flag={runway < 12}
                  flagText="Short"
                />
              )}
            </div>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="bg-red-950/40 border border-red-700/30 rounded-xl p-4 text-sm text-red-300">
            {error}
          </div>
        )}

        {/* Actions */}
        <div className="flex gap-3">
          <button
            onClick={onBack}
            className="px-5 py-3 text-sm text-slate-400 hover:text-slate-200 border border-slate-700 rounded-xl transition-colors"
          >
            ← Fund Setup
          </button>
          <button
            onClick={onRun}
            disabled={!canRun || isLoading}
            className={`
              flex-1 py-3 font-semibold rounded-xl transition-all text-sm
              ${canRun && !isLoading
                ? 'bg-emerald-600 hover:bg-emerald-500 text-white'
                : 'bg-slate-700 text-slate-500 cursor-not-allowed'
              }
            `}
          >
            {isLoading ? 'Running evaluation…' : 'Run Deal Evaluation →'}
          </button>
        </div>
      </div>
    </div>
  )
}

function PreviewRow({
  label,
  value,
  flag,
  flagText,
}: {
  label: string
  value: string
  flag?: boolean
  flagText?: string
}) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-slate-400 text-xs">{label}</span>
      <div className="flex items-center gap-2">
        <span className={flag ? 'text-amber-400 font-semibold' : 'text-slate-200'}>{value}</span>
        {flag && flagText && (
          <span className="text-amber-500 text-2xs bg-amber-950/50 px-1.5 py-0.5 rounded">
            {flagText}
          </span>
        )}
      </div>
    </div>
  )
}
