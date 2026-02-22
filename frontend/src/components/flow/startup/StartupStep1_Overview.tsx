/**
 * Step 1: Company name, vertical, stage, geography, raise amount, instrument.
 * The "front door" of the startup valuation flow.
 */
import React, { useState } from 'react'
import { ArrowRight } from 'lucide-react'
import type { FundraisingProfile, StartupVertical, StartupStage, Geography, InstrumentType } from '../../../types/startup'
import { VERTICAL_LABELS, STAGE_LABELS, GEOGRAPHY_LABELS, INSTRUMENT_LABELS } from '../../../types/startup'

interface Step1Props {
  company_name: string
  fundraise: Partial<FundraisingProfile>
  onNameChange: (name: string) => void
  onUpdateFundraise: (updates: Partial<FundraisingProfile>) => void
  onNext: () => void
}

const VERTICALS = Object.entries(VERTICAL_LABELS) as [StartupVertical, string][]
const STAGES = Object.entries(STAGE_LABELS) as [StartupStage, string][]
const GEOS = Object.entries(GEOGRAPHY_LABELS) as [Geography, string][]
const INSTRUMENTS = Object.entries(INSTRUMENT_LABELS) as [InstrumentType, string][]

export default function StartupStep1_Overview({
  company_name,
  fundraise,
  onNameChange,
  onUpdateFundraise,
  onNext,
}: Step1Props) {
  const [errors, setErrors] = useState<Record<string, string>>({})

  const validate = () => {
    const errs: Record<string, string> = {}
    if (!company_name.trim()) errs.name = 'Company name is required'
    if (!fundraise.vertical) errs.vertical = 'Select a vertical'
    if (!fundraise.stage) errs.stage = 'Select a stage'
    if (!fundraise.raise_amount || fundraise.raise_amount <= 0) errs.raise = 'Enter the amount you are raising'
    setErrors(errs)
    return Object.keys(errs).length === 0
  }

  const handleNext = () => {
    if (validate()) onNext()
  }

  return (
    <div className="max-w-2xl mx-auto animate-slide-up">
      <div className="mb-10">
        <div className="inline-flex items-center gap-2 bg-purple-900/30 border border-purple-700/50 rounded-full px-4 py-1.5 mb-4">
          <span className="w-2 h-2 rounded-full bg-purple-400"></span>
          <span className="text-purple-300 text-sm font-medium">Startup Valuation</span>
        </div>
        <h1 className="text-3xl font-bold text-slate-100 mb-3">
          What are you building?
        </h1>
        <p className="text-slate-400 text-lg">
          Tell us the basics about your company and this fundraising round.
          We'll use live benchmarks from Carta, PitchBook, and Equidam to give you
          an institutional-grade valuation range in seconds.
        </p>
      </div>

      <div className="space-y-6">
        {/* Company name */}
        <div className="rounded-xl border border-slate-700 bg-slate-800/30 p-6">
          <label className="block text-sm font-medium text-slate-300 mb-2">
            Company name <span className="text-red-400">*</span>
          </label>
          <input
            type="text"
            value={company_name}
            onChange={e => onNameChange(e.target.value)}
            placeholder="e.g. Acme AI"
            className={`
              w-full bg-slate-900 border rounded-lg px-4 py-3 text-slate-100 placeholder-slate-500
              focus:outline-none focus:ring-2 focus:ring-purple-500 transition-colors
              ${errors.name ? 'border-red-500' : 'border-slate-600'}
            `}
          />
          {errors.name && <p className="text-red-400 text-xs mt-1">{errors.name}</p>}
        </div>

        {/* Vertical */}
        <div className="rounded-xl border border-slate-700 bg-slate-800/30 p-6">
          <label className="block text-sm font-medium text-slate-300 mb-1">
            What industry / vertical? <span className="text-red-400">*</span>
          </label>
          <p className="text-slate-500 text-xs mb-3">
            This determines which benchmark dataset we use for the valuation comparison.
          </p>
          <select
            value={fundraise.vertical ?? ''}
            onChange={e => onUpdateFundraise({ vertical: e.target.value as StartupVertical })}
            className={`
              w-full bg-slate-900 border rounded-lg px-4 py-3 text-slate-100
              focus:outline-none focus:ring-2 focus:ring-purple-500 transition-colors
              ${errors.vertical ? 'border-red-500' : 'border-slate-600'}
            `}
          >
            <option value="">Select a vertical...</option>
            {VERTICALS.map(([v, label]) => (
              <option key={v} value={v}>{label}</option>
            ))}
          </select>
          {errors.vertical && <p className="text-red-400 text-xs mt-1">{errors.vertical}</p>}
        </div>

        {/* Stage */}
        <div className="rounded-xl border border-slate-700 bg-slate-800/30 p-6">
          <label className="block text-sm font-medium text-slate-300 mb-1">
            Fundraising stage <span className="text-red-400">*</span>
          </label>
          <div className="grid grid-cols-3 gap-3 mt-3">
            {STAGES.map(([s, label]) => (
              <button
                key={s}
                onClick={() => onUpdateFundraise({ stage: s })}
                className={`
                  p-3 rounded-lg border text-sm font-medium transition-all
                  ${fundraise.stage === s
                    ? 'border-purple-500 bg-purple-900/40 text-purple-200'
                    : 'border-slate-600 bg-slate-800/30 text-slate-400 hover:border-slate-500'
                  }
                `}
              >
                {label}
              </button>
            ))}
          </div>
          {errors.stage && <p className="text-red-400 text-xs mt-2">{errors.stage}</p>}
        </div>

        {/* Raise amount + Instrument */}
        <div className="rounded-xl border border-slate-700 bg-slate-800/30 p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">
              How much are you raising? <span className="text-red-400">*</span>
            </label>
            <p className="text-slate-500 text-xs mb-3">In USD millions (e.g. 1.5 = $1.5M)</p>
            <div className="relative">
              <span className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400 font-medium">$</span>
              <input
                type="number"
                min={0}
                step={0.1}
                value={fundraise.raise_amount ?? ''}
                onChange={e => onUpdateFundraise({ raise_amount: parseFloat(e.target.value) || 0 })}
                placeholder="1.5"
                className={`
                  w-full bg-slate-900 border rounded-lg pl-8 pr-12 py-3 text-slate-100 placeholder-slate-500
                  focus:outline-none focus:ring-2 focus:ring-purple-500 transition-colors
                  ${errors.raise ? 'border-red-500' : 'border-slate-600'}
                `}
              />
              <span className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-500 text-sm">M</span>
            </div>
            {errors.raise && <p className="text-red-400 text-xs mt-1">{errors.raise}</p>}
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-3">Instrument</label>
            <div className="space-y-2">
              {INSTRUMENTS.map(([inst, label]) => (
                <label key={inst} className="flex items-center gap-3 cursor-pointer group">
                  <input
                    type="radio"
                    name="instrument"
                    value={inst}
                    checked={fundraise.instrument === inst}
                    onChange={() => onUpdateFundraise({ instrument: inst })}
                    className="accent-purple-500"
                  />
                  <span className="text-slate-300 text-sm group-hover:text-slate-100 transition-colors">{label}</span>
                </label>
              ))}
            </div>
          </div>
        </div>

        {/* Geography */}
        <div className="rounded-xl border border-slate-700 bg-slate-800/30 p-6">
          <label className="block text-sm font-medium text-slate-300 mb-1">Geography</label>
          <p className="text-slate-500 text-xs mb-3">
            Location affects the Berkus baseline — Bay Area and NY command a 1.5–1.8x premium on average valuations.
          </p>
          <select
            value={fundraise.geography ?? 'other_us'}
            onChange={e => onUpdateFundraise({ geography: e.target.value as Geography })}
            className="w-full bg-slate-900 border border-slate-600 rounded-lg px-4 py-3 text-slate-100 focus:outline-none focus:ring-2 focus:ring-purple-500"
          >
            {GEOS.map(([g, label]) => (
              <option key={g} value={g}>{label}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="mt-8">
        <button
          onClick={handleNext}
          className="
            w-full flex items-center justify-center gap-2 px-6 py-4 rounded-xl
            bg-purple-600 hover:bg-purple-500 text-white font-semibold text-base
            transition-all shadow-lg shadow-purple-900/30
          "
        >
          Continue — Tell us about your team
          <ArrowRight size={18} />
        </button>
        <p className="text-center text-xs text-slate-500 mt-3">
          All data stays in your browser. Nothing is stored on our servers.
        </p>
      </div>
    </div>
  )
}
