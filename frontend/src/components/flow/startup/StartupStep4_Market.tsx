/**
 * Step 4: Market size, moat, round structure details.
 */
import React, { useState } from 'react'
import { ArrowRight, ArrowLeft, Info } from 'lucide-react'
import type { MarketProfile, FundraisingProfile } from '../../../types/startup'

interface Step4Props {
  market: Partial<MarketProfile>
  fundraise: Partial<FundraisingProfile>
  onUpdateMarket: (updates: Partial<MarketProfile>) => void
  onUpdateFundraise: (updates: Partial<FundraisingProfile>) => void
  onNext: () => void
  onBack: () => void
}

function Tooltip({ text }: { text: string }) {
  const [show, setShow] = useState(false)
  return (
    <div className="relative inline-block">
      <Info size={13} className="text-slate-500 cursor-help" onMouseEnter={() => setShow(true)} onMouseLeave={() => setShow(false)} />
      {show && (
        <div className="absolute z-10 w-56 p-2 text-xs bg-slate-700 border border-slate-600 rounded-lg shadow-xl left-5 top-0">
          {text}
        </div>
      )}
    </div>
  )
}

export default function StartupStep4_Market({
  market,
  fundraise,
  onUpdateMarket,
  onUpdateFundraise,
  onNext,
  onBack,
}: Step4Props) {
  const isSafe = fundraise.instrument === 'safe'

  return (
    <div className="max-w-2xl mx-auto animate-slide-up">
      <div className="mb-8">
        <h2 className="text-2xl font-bold text-slate-100 mb-2">Market & round details</h2>
        <p className="text-slate-400">
          Market size sets the ceiling on your valuation. VCs need to see a credible path to $1B+ TAM
          to justify the return profile — no fund can return its capital on a $200M market.
        </p>
      </div>

      <div className="space-y-6">
        {/* TAM / SAM */}
        <div className="rounded-xl border border-slate-700 bg-slate-800/30 p-6 space-y-4">
          <p className="text-sm font-medium text-slate-300">Market sizing</p>

          <div>
            <div className="flex items-center gap-2 mb-1">
              <label className="text-sm text-slate-400">Total Addressable Market (TAM)</label>
              <Tooltip text="The total global demand for your category if every potential customer used your product. VCs want $1B+ minimum; $10B+ for top-tier institutional seed." />
            </div>
            <div className="relative">
              <span className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400 font-medium">$</span>
              <input
                type="number"
                min={0}
                step={0.1}
                value={market.tam_usd_billions ?? ''}
                onChange={e => onUpdateMarket({ tam_usd_billions: parseFloat(e.target.value) || 0 })}
                placeholder="5.0"
                className="w-full bg-slate-900 border border-slate-600 rounded-lg pl-8 pr-12 py-3 text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-purple-500"
              />
              <span className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-500 text-sm">B</span>
            </div>
            {(market.tam_usd_billions ?? 0) > 0 && (market.tam_usd_billions ?? 0) < 1 && (
              <p className="text-amber-400 text-xs mt-1">
                TAM below $1B will challenge institutional investor narrative. Consider whether the market definition is too narrow.
              </p>
            )}
          </div>

          <div>
            <div className="flex items-center gap-2 mb-1">
              <label className="text-sm text-slate-400">Serviceable Addressable Market (SAM)</label>
              <Tooltip text="The realistic portion of TAM your product can serve today — bounded by geography, customer segment, and distribution. This is what investors actually model." />
            </div>
            <div className="relative">
              <span className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400 font-medium">$</span>
              <input
                type="number"
                min={0}
                step={1}
                value={market.sam_usd_millions ?? ''}
                onChange={e => onUpdateMarket({ sam_usd_millions: parseFloat(e.target.value) || 0 })}
                placeholder="200"
                className="w-full bg-slate-900 border border-slate-600 rounded-lg pl-8 pr-12 py-3 text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-purple-500"
              />
              <span className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-500 text-sm">M</span>
            </div>
          </div>

          <div>
            <div className="flex items-center gap-2 mb-1">
              <label className="text-sm text-slate-400">Annual market growth rate</label>
              <Tooltip text="How fast the overall market is growing. Fast-growing markets (30%+) compress competitive risk and support premium multiples." />
            </div>
            <div className="relative">
              <input
                type="number"
                min={0}
                step={1}
                value={((market.market_growth_rate ?? 0.15) * 100).toFixed(0)}
                onChange={e => onUpdateMarket({ market_growth_rate: parseFloat(e.target.value) / 100 || 0 })}
                placeholder="15"
                className="w-full bg-slate-900 border border-slate-600 rounded-lg px-4 pr-10 py-3 text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-purple-500"
              />
              <span className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-500 text-sm">%</span>
            </div>
          </div>
        </div>

        {/* Competitive moat */}
        <div className="rounded-xl border border-slate-700 bg-slate-800/30 p-6">
          <div className="flex items-center gap-2 mb-1">
            <p className="text-sm font-medium text-slate-300">Competitive moat</p>
            <Tooltip text="How hard is it for a well-funded competitor to replicate your core advantage? High = network effects, proprietary data, or deep regulatory moat." />
          </div>
          <p className="text-slate-500 text-xs mb-4">
            Honest assessment — investors will probe this in diligence. "We're first mover" is not a moat.
          </p>
          <div className="grid grid-cols-3 gap-3">
            {(['low', 'medium', 'high'] as const).map(moat => (
              <button
                key={moat}
                onClick={() => onUpdateMarket({ competitive_moat: moat })}
                className={`
                  p-3 rounded-lg border text-sm font-medium transition-all
                  ${market.competitive_moat === moat
                    ? moat === 'high'
                      ? 'border-green-500 bg-green-900/30 text-green-300'
                      : moat === 'low'
                        ? 'border-amber-500 bg-amber-900/30 text-amber-300'
                        : 'border-purple-500 bg-purple-900/40 text-purple-200'
                    : 'border-slate-600 text-slate-400 hover:border-slate-500'
                  }
                `}
              >
                {moat === 'low' ? 'Low (easily copied)' : moat === 'medium' ? 'Medium (some barriers)' : 'High (strong defensibility)'}
              </button>
            ))}
          </div>
        </div>

        {/* SAFE-specific fields */}
        {isSafe && (
          <div className="rounded-xl border border-slate-700 bg-slate-800/30 p-6 space-y-4">
            <p className="text-sm font-medium text-slate-300">SAFE structure</p>

            <div>
              <div className="flex items-center gap-2 mb-1">
                <label className="text-sm text-slate-400">Your valuation cap ask (optional)</label>
                <Tooltip text="The pre-money valuation cap on your SAFE. The engine will calculate the recommended cap from the blended valuation if you leave this blank." />
              </div>
              <div className="relative">
                <span className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400">$</span>
                <input
                  type="number"
                  min={0}
                  step={0.5}
                  value={fundraise.pre_money_valuation_ask ?? ''}
                  onChange={e => onUpdateFundraise({ pre_money_valuation_ask: e.target.value ? parseFloat(e.target.value) : null })}
                  placeholder="Leave blank to use engine output"
                  className="w-full bg-slate-900 border border-slate-600 rounded-lg pl-8 pr-12 py-3 text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-purple-500"
                />
                <span className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-500 text-sm">M</span>
              </div>
            </div>

            <div>
              <div className="flex items-center gap-2 mb-1">
                <label className="text-sm text-slate-400">Discount rate (if any)</label>
                <Tooltip text="A 20% discount means your SAFE converts at 20% below the next round's price. Common but less standard than cap-only SAFEs." />
              </div>
              <div className="relative">
                <input
                  type="number"
                  min={0}
                  max={50}
                  step={5}
                  value={((fundraise.safe_discount ?? 0) * 100).toFixed(0)}
                  onChange={e => onUpdateFundraise({ safe_discount: parseFloat(e.target.value) / 100 || 0 })}
                  placeholder="0"
                  className="w-full bg-slate-900 border border-slate-600 rounded-lg px-4 pr-10 py-3 text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-purple-500"
                />
                <span className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-500 text-sm">%</span>
              </div>
            </div>

            <div>
              <div className="flex items-center gap-2 mb-1">
                <label className="text-sm text-slate-400">Existing SAFE stack (outstanding, not yet converted)</label>
                <Tooltip text="Total face value of SAFEs you've already issued that haven't converted yet. These will convert at the next priced round and dilute founders before the new investor comes in." />
              </div>
              <div className="relative">
                <span className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400">$</span>
                <input
                  type="number"
                  min={0}
                  step={0.1}
                  value={fundraise.existing_safe_stack ?? ''}
                  onChange={e => onUpdateFundraise({ existing_safe_stack: parseFloat(e.target.value) || 0 })}
                  placeholder="0"
                  className="w-full bg-slate-900 border border-slate-600 rounded-lg pl-8 pr-12 py-3 text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-purple-500"
                />
                <span className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-500 text-sm">M</span>
              </div>
            </div>

            <div
              className={`
                flex items-center justify-between p-3 rounded-lg border cursor-pointer
                ${fundraise.has_mfn_clause ? 'border-amber-600 bg-amber-900/20' : 'border-slate-700 hover:border-slate-600'}
              `}
              onClick={() => onUpdateFundraise({ has_mfn_clause: !fundraise.has_mfn_clause })}
            >
              <div>
                <p className="text-sm text-slate-200">MFN clause on any prior SAFE</p>
                <p className="text-xs text-slate-500 mt-0.5">Most Favored Nation — if you issue better terms later, existing holders automatically get them</p>
              </div>
              <div className={`w-10 h-5 rounded-full transition-colors ml-4 flex-shrink-0 ${fundraise.has_mfn_clause ? 'bg-amber-600' : 'bg-slate-600'}`}>
                <div className={`w-4 h-4 rounded-full bg-white shadow transition-transform mt-0.5 ${fundraise.has_mfn_clause ? 'translate-x-5' : 'translate-x-0.5'}`} />
              </div>
            </div>
          </div>
        )}
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
          Run Valuation <ArrowRight size={18} />
        </button>
      </div>
    </div>
  )
}
