/**
 * Step 2: Team profile — the single most important pre-seed valuation driver.
 */
import React from 'react'
import { ArrowRight, ArrowLeft } from 'lucide-react'
import type { TeamProfile } from '../../../types/startup'

interface Step2Props {
  team: Partial<TeamProfile>
  onUpdate: (updates: Partial<TeamProfile>) => void
  onNext: () => void
  onBack: () => void
}

interface ToggleRowProps {
  label: string
  description: string
  value: boolean
  onChange: (v: boolean) => void
  premium?: string
}

function ToggleRow({ label, description, value, onChange, premium }: ToggleRowProps) {
  return (
    <div
      className={`
        flex items-start justify-between p-4 rounded-lg border cursor-pointer transition-all
        ${value ? 'border-purple-600 bg-purple-900/20' : 'border-slate-700 bg-slate-800/20 hover:border-slate-600'}
      `}
      onClick={() => onChange(!value)}
    >
      <div className="flex-1 pr-4">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-slate-200">{label}</span>
          {premium && (
            <span className="text-xs text-purple-400 bg-purple-900/40 px-2 py-0.5 rounded-full">{premium}</span>
          )}
        </div>
        <p className="text-xs text-slate-500 mt-0.5">{description}</p>
      </div>
      <div className={`
        w-10 h-5 rounded-full transition-colors flex-shrink-0 mt-0.5
        ${value ? 'bg-purple-600' : 'bg-slate-600'}
      `}>
        <div className={`
          w-4 h-4 rounded-full bg-white shadow transition-transform mt-0.5
          ${value ? 'translate-x-5' : 'translate-x-0.5'}
        `} />
      </div>
    </div>
  )
}

export default function StartupStep2_Team({ team, onUpdate, onNext, onBack }: Step2Props) {
  return (
    <div className="max-w-2xl mx-auto animate-slide-up">
      <div className="mb-8">
        <h2 className="text-2xl font-bold text-slate-100 mb-2">Your founding team</h2>
        <p className="text-slate-400">
          Team quality is the single largest valuation driver at pre-seed — representing up to 30% of the
          Scorecard and Berkus weighting. Be honest here; this feeds directly into your valuation range.
        </p>
      </div>

      <div className="space-y-6">
        {/* Founder count */}
        <div className="rounded-xl border border-slate-700 bg-slate-800/30 p-6">
          <label className="block text-sm font-medium text-slate-300 mb-3">Number of co-founders</label>
          <div className="flex gap-3">
            {[1, 2, 3, 4].map(n => (
              <button
                key={n}
                onClick={() => onUpdate({ founder_count: n })}
                className={`
                  w-14 h-12 rounded-lg border text-sm font-semibold transition-all
                  ${(team.founder_count ?? 2) === n
                    ? 'border-purple-500 bg-purple-900/40 text-purple-200'
                    : 'border-slate-600 text-slate-400 hover:border-slate-500'
                  }
                `}
              >
                {n}
              </button>
            ))}
          </div>
        </div>

        {/* Prior exits */}
        <div className="rounded-xl border border-slate-700 bg-slate-800/30 p-6">
          <label className="block text-sm font-medium text-slate-300 mb-1">Prior successful exits</label>
          <p className="text-slate-500 text-xs mb-3">
            Even one prior exit immediately adds $1–5M to your valuation in angel and VC conversations — it's the
            highest-signal credential you can have.
          </p>
          <div className="flex gap-3">
            {[0, 1, 2, 3].map(n => (
              <button
                key={n}
                onClick={() => onUpdate({ prior_exits: n })}
                className={`
                  w-14 h-12 rounded-lg border text-sm font-semibold transition-all
                  ${(team.prior_exits ?? 0) === n
                    ? 'border-purple-500 bg-purple-900/40 text-purple-200'
                    : 'border-slate-600 text-slate-400 hover:border-slate-500'
                  }
                `}
              >
                {n === 3 ? '3+' : n}
              </button>
            ))}
          </div>
        </div>

        {/* Boolean signals */}
        <div className="rounded-xl border border-slate-700 bg-slate-800/30 p-6 space-y-3">
          <p className="text-sm font-medium text-slate-300 mb-4">Team signals</p>

          <ToggleRow
            label="Technical co-founder"
            description="At least one founder who can build the core product independently"
            value={team.technical_cofounder ?? true}
            onChange={v => onUpdate({ technical_cofounder: v })}
            premium="Required for AI/deep tech"
          />
          <ToggleRow
            label="Domain expert founders"
            description="Founders have direct working experience in the vertical they're disrupting (ex-Stripe in fintech, ex-Epic in healthtech)"
            value={team.domain_experts ?? false}
            onChange={v => onUpdate({ domain_experts: v })}
            premium="+10–15% on Scorecard"
          />
          <ToggleRow
            label="Repeat founder"
            description="At least one founder who has built and led a company before"
            value={team.repeat_founder ?? false}
            onChange={v => onUpdate({ repeat_founder: v })}
          />
          <ToggleRow
            label="Tier 1 background"
            description="Google/Meta/Amazon/McKinsey/Goldman/top-4 bank — signals execution capability to new investors"
            value={team.tier1_background ?? false}
            onChange={v => onUpdate({ tier1_background: v })}
          />
          <ToggleRow
            label="Notable advisors"
            description="Operationally relevant advisors with credibility in your specific vertical (not just famous names)"
            value={team.notable_advisors ?? false}
            onChange={v => onUpdate({ notable_advisors: v })}
          />
        </div>
      </div>

      <div className="mt-8 flex gap-3">
        <button
          onClick={onBack}
          className="px-6 py-4 rounded-xl border border-slate-600 text-slate-300 hover:border-slate-500 transition-all flex items-center gap-2"
        >
          <ArrowLeft size={16} /> Back
        </button>
        <button
          onClick={onNext}
          className="flex-1 flex items-center justify-center gap-2 px-6 py-4 rounded-xl bg-purple-600 hover:bg-purple-500 text-white font-semibold transition-all"
        >
          Continue — Traction & Revenue <ArrowRight size={18} />
        </button>
      </div>
    </div>
  )
}
