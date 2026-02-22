import React, { useState, useEffect } from 'react'
import AppShell from './components/layout/AppShell'
import Step1_DealOverview from './components/flow/Step1_DealOverview'
import Step2_BuyerProfile from './components/flow/Step2_BuyerProfile'
import Step3_TargetProfile from './components/flow/Step3_TargetProfile'
import Step4_Financing from './components/flow/Step4_Financing'
import Step5_Synergies from './components/flow/Step5_Synergies'
import Step6_Review from './components/flow/Step6_Review'
import ResultsDashboard from './components/output/ResultsDashboard'
import ConversationalEntry from './components/flow/ConversationalEntry'
import { useDealState } from './hooks/useDealState'
import type { FlowStep, DealInput, AcquirerProfile, TargetProfile } from './types/deal'
import { checkAIStatus } from './lib/ai-api'

// Startup flow
import { useStartupState } from './hooks/useStartupState'
import StartupStep1_Overview from './components/flow/startup/StartupStep1_Overview'
import StartupStep2_Team from './components/flow/startup/StartupStep2_Team'
import StartupStep3_Traction from './components/flow/startup/StartupStep3_Traction'
import StartupStep4_Market from './components/flow/startup/StartupStep4_Market'
import StartupStep5_Review from './components/flow/startup/StartupStep5_Review'
import StartupDashboard from './components/output/startup/StartupDashboard'
import type { StartupFlowStep } from './types/startup'

// VC Investor flow
import { useVCState } from './hooks/useVCState'
import VCFundSetup from './components/vc/VCFundSetup'
import VCQuickScreen from './components/vc/VCQuickScreen'
import VCDashboard from './components/vc/VCDashboard'

type AppMode = 'ma' | 'startup' | 'vc'

// ---------------------------------------------------------------------------
// Mode selector bar
// ---------------------------------------------------------------------------
function AppModeSelector({ active, onChange }: { active: AppMode; onChange: (m: AppMode) => void }) {
  return (
    <div className="max-w-2xl mx-auto mb-8">
      <div className="flex gap-2 p-1 bg-slate-800/60 border border-slate-700 rounded-xl">
        <button
          onClick={() => onChange('ma')}
          className={`
            flex-1 py-2 px-3 rounded-lg text-sm font-medium transition-all
            ${active === 'ma'
              ? 'bg-blue-600 text-white shadow'
              : 'text-slate-400 hover:text-slate-200'
            }
          `}
        >
          M&A Deal Modeling
        </button>
        <button
          onClick={() => onChange('startup')}
          className={`
            flex-1 py-2 px-3 rounded-lg text-sm font-medium transition-all
            ${active === 'startup'
              ? 'bg-purple-600 text-white shadow'
              : 'text-slate-400 hover:text-slate-200'
            }
          `}
        >
          Startup Valuation
        </button>
        <button
          onClick={() => onChange('vc')}
          className={`
            flex-1 py-2 px-3 rounded-lg text-sm font-medium transition-all
            ${active === 'vc'
              ? 'bg-emerald-600 text-white shadow'
              : 'text-slate-400 hover:text-slate-200'
            }
          `}
        >
          VC Investor
        </button>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Startup-specific shell (purple branding, simplified nav)
// ---------------------------------------------------------------------------
function StartupShell({
  children,
  onModeChange,
  step,
  totalSteps,
}: {
  children: React.ReactNode
  onModeChange: (m: AppMode) => void
  step?: number
  totalSteps?: number
}) {
  return (
    <div className="min-h-screen bg-navy-900 text-slate-100 font-sans">
      <header className="border-b border-slate-800 bg-navy-800/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-purple-500 to-purple-700 flex items-center justify-center">
              <span className="text-white text-xs font-bold">DE</span>
            </div>
            <span className="font-semibold text-slate-100 text-sm">Dealflow Engine</span>
            <span className="text-slate-600 text-sm">·</span>
            <span className="text-purple-400 text-sm font-medium">Startup Valuation</span>
          </div>
          <div className="flex gap-1 p-1 bg-slate-800/60 border border-slate-700 rounded-xl">
            <button onClick={() => onModeChange('ma')} className="py-1.5 px-3 rounded-lg text-xs font-medium text-slate-400 hover:text-slate-200 transition-all">M&A</button>
            <button className="py-1.5 px-3 rounded-lg text-xs font-medium bg-purple-600 text-white">Startup</button>
            <button onClick={() => onModeChange('vc')} className="py-1.5 px-3 rounded-lg text-xs font-medium text-slate-400 hover:text-slate-200 transition-all">VC</button>
          </div>
        </div>
      </header>

      {step != null && totalSteps != null && (
        <div className="border-b border-slate-800 bg-navy-800/40">
          <div className="max-w-6xl mx-auto px-4 sm:px-6 py-3">
            <div className="flex items-center gap-2">
              {Array.from({ length: totalSteps }, (_, i) => i + 1).map(s => (
                <div key={s} className="flex items-center gap-2">
                  <div className={`
                    w-6 h-6 rounded-full flex items-center justify-center text-xs font-semibold
                    ${step === s ? 'bg-purple-600 text-white' : step > s ? 'bg-purple-900/40 text-purple-400' : 'bg-slate-800 text-slate-500'}
                  `}>
                    {s}
                  </div>
                  {s < totalSteps && <div className={`w-8 h-px ${step > s ? 'bg-purple-600' : 'bg-slate-700'}`} />}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      <main className="max-w-6xl mx-auto px-4 sm:px-6 py-8">{children}</main>

      <footer className="border-t border-slate-800 mt-20 py-6">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 flex items-center justify-between text-2xs text-slate-500">
          <span>Dealflow Engine — MIT License — Open Source</span>
          <a
            href="https://github.com/bdavis37-tal/dealflow-engine"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-slate-300 transition-colors"
          >
            GitHub →
          </a>
        </div>
      </footer>
    </div>
  )
}

// ---------------------------------------------------------------------------
// VC shell (emerald branding)
// ---------------------------------------------------------------------------
function VCShell({
  children,
  onModeChange,
  step,
  totalSteps,
}: {
  children: React.ReactNode
  onModeChange: (m: AppMode) => void
  step?: number
  totalSteps?: number
}) {
  return (
    <div className="min-h-screen bg-navy-900 text-slate-100 font-sans">
      <header className="border-b border-slate-800 bg-navy-800/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-emerald-500 to-emerald-700 flex items-center justify-center">
              <span className="text-white text-xs font-bold">DE</span>
            </div>
            <span className="font-semibold text-slate-100 text-sm">Dealflow Engine</span>
            <span className="text-slate-600 text-sm">·</span>
            <span className="text-emerald-400 text-sm font-medium">VC Investor</span>
          </div>
          <div className="flex gap-1 p-1 bg-slate-800/60 border border-slate-700 rounded-xl">
            <button onClick={() => onModeChange('ma')} className="py-1.5 px-3 rounded-lg text-xs font-medium text-slate-400 hover:text-slate-200 transition-all">M&A</button>
            <button onClick={() => onModeChange('startup')} className="py-1.5 px-3 rounded-lg text-xs font-medium text-slate-400 hover:text-slate-200 transition-all">Startup</button>
            <button className="py-1.5 px-3 rounded-lg text-xs font-medium bg-emerald-600 text-white">VC</button>
          </div>
        </div>
      </header>

      {step != null && totalSteps != null && (
        <div className="border-b border-slate-800 bg-navy-800/40">
          <div className="max-w-6xl mx-auto px-4 sm:px-6 py-3">
            <div className="flex items-center gap-2">
              {Array.from({ length: totalSteps }, (_, i) => i + 1).map(s => (
                <div key={s} className="flex items-center gap-2">
                  <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-semibold
                    ${step === s ? 'bg-emerald-600 text-white' : step > s ? 'bg-emerald-900/40 text-emerald-400' : 'bg-slate-800 text-slate-500'}`}>
                    {s}
                  </div>
                  {s < totalSteps && <div className={`w-8 h-px ${step > s ? 'bg-emerald-600' : 'bg-slate-700'}`} />}
                </div>
              ))}
              <span className="ml-3 text-xs text-slate-500">
                {step === 1 ? 'Fund Profile' : step === 2 ? 'Deal Screen' : 'Results'}
              </span>
            </div>
          </div>
        </div>
      )}

      <main className="max-w-6xl mx-auto px-4 sm:px-6 py-8">{children}</main>

      <footer className="border-t border-slate-800 mt-20 py-6">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 flex items-center justify-between text-2xs text-slate-500">
          <span>Dealflow Engine — MIT License — Open Source</span>
          <a href="https://github.com/bdavis37-tal/dealflow-engine" target="_blank" rel="noopener noreferrer" className="hover:text-slate-300 transition-colors">GitHub →</a>
        </div>
      </footer>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main App
// ---------------------------------------------------------------------------
export default function App() {
  const [appMode, setAppMode] = useState<AppMode>('ma')

  // M&A state
  const {
    state,
    setStep,
    setMode,
    updateAcquirer,
    updateTarget,
    updateStructure,
    updatePPA,
    updateSynergies,
    reset,
    runAnalysis,
  } = useDealState()

  // Startup state
  const {
    state: startupState,
    setStep: setStartupStep,
    setCompanyName,
    updateTeam,
    updateTraction,
    updateProduct,
    updateMarket,
    updateFundraise,
    reset: resetStartup,
    runValuation,
  } = useStartupState()

  // VC state
  const {
    state: vcState,
    setStep: setVCStep,
    updateFund,
    updateDeal: updateVCDeal,
    resetDeal: resetVCDeal,
    resetAll: resetVC,
    runEvaluation,
  } = useVCState()

  const { step, mode, acquirer, target, structure, ppa, synergies, output } = state

  const [aiAvailable, setAiAvailable] = useState(false)
  const [showConversational, setShowConversational] = useState(true)

  useEffect(() => {
    checkAIStatus()
      .then(s => setAiAvailable(s.ai_available))
      .catch(() => setAiAvailable(false))
  }, [])

  const nav = (s: FlowStep) => () => setStep(s)
  const navStartup = (s: StartupFlowStep) => () => setStartupStep(s)

  const handleExtracted = (
    acq: Partial<AcquirerProfile>,
    tgt: Partial<TargetProfile>,
    _summary: string,
  ) => {
    updateAcquirer(acq)
    updateTarget(tgt)
    setStep(2)
  }

  // ---------------------------------------------------------------------------
  // Startup flow
  // ---------------------------------------------------------------------------
  if (appMode === 'startup') {
    if (startupState.output && !startupState.isLoading) {
      return (
        <StartupShell onModeChange={setAppMode}>
          <StartupDashboard output={startupState.output} onReset={resetStartup} />
        </StartupShell>
      )
    }

    return (
      <StartupShell
        onModeChange={setAppMode}
        step={Math.min(startupState.step, 4)}
        totalSteps={4}
      >
        {startupState.step === 1 && (
          <StartupStep1_Overview
            company_name={startupState.company_name}
            fundraise={startupState.fundraise}
            onNameChange={setCompanyName}
            onUpdateFundraise={updateFundraise}
            onNext={navStartup(2)}
          />
        )}
        {startupState.step === 2 && (
          <StartupStep2_Team
            team={startupState.team}
            onUpdate={updateTeam}
            onNext={navStartup(3)}
            onBack={navStartup(1)}
          />
        )}
        {startupState.step === 3 && (
          <StartupStep3_Traction
            traction={startupState.traction}
            product={startupState.product}
            onUpdateTraction={updateTraction}
            onUpdateProduct={updateProduct}
            onNext={navStartup(4)}
            onBack={navStartup(2)}
          />
        )}
        {startupState.step === 4 && !startupState.isLoading && (
          <StartupStep4_Market
            market={startupState.market}
            fundraise={startupState.fundraise}
            onUpdateMarket={updateMarket}
            onUpdateFundraise={updateFundraise}
            onNext={runValuation}
            onBack={navStartup(3)}
          />
        )}
        {startupState.isLoading && (
          <StartupStep5_Review
            state={startupState}
            onBack={navStartup(4)}
            onRun={runValuation}
          />
        )}
      </StartupShell>
    )
  }

  // ---------------------------------------------------------------------------
  // VC Investor flow
  // ---------------------------------------------------------------------------
  if (appMode === 'vc') {
    // Results view
    if (vcState.output && !vcState.isLoading) {
      return (
        <VCShell onModeChange={setAppMode}>
          <VCDashboard
            output={vcState.output}
            fund={vcState.fund}
            onNewDeal={resetVCDeal}
            onReset={resetVC}
          />
        </VCShell>
      )
    }

    return (
      <VCShell onModeChange={setAppMode} step={vcState.step} totalSteps={2}>
        {vcState.step === 1 && (
          <VCFundSetup
            fund={vcState.fund}
            onUpdate={updateFund}
            onNext={() => setVCStep(2)}
          />
        )}
        {(vcState.step === 2 || vcState.isLoading) && (
          <VCQuickScreen
            deal={vcState.deal}
            fund={vcState.fund}
            onUpdate={updateVCDeal}
            onBack={() => setVCStep(1)}
            onRun={runEvaluation}
            isLoading={vcState.isLoading}
            error={vcState.error}
          />
        )}
      </VCShell>
    )
  }

  // ---------------------------------------------------------------------------
  // M&A flow (original, unchanged)
  // ---------------------------------------------------------------------------
  if (output && !state.isLoading) {
    const dealInput: DealInput = {
      acquirer: acquirer as AcquirerProfile,
      target: target as TargetProfile,
      structure,
      ppa,
      synergies,
      mode,
      projection_years: 5,
    }
    return (
      <AppShell step={6} mode={mode} onModeChange={setMode} showNav={false}>
        <ResultsDashboard output={output} dealInput={dealInput} onReset={reset} />
      </AppShell>
    )
  }

  const combinedRevenue = (acquirer.revenue ?? 0) + (target.revenue ?? 0)
  const dealSize = target.acquisition_price ?? 0

  return (
    <AppShell step={step} mode={mode} onModeChange={setMode}>
      {step === 1 && (
        <AppModeSelector active={appMode} onChange={setAppMode} />
      )}

      {step === 1 && showConversational && (
        <ConversationalEntry
          aiAvailable={aiAvailable}
          onExtracted={handleExtracted}
          onSkipToForm={() => setShowConversational(false)}
        />
      )}
      {step === 1 && !showConversational && (
        <Step1_DealOverview
          acquirer={acquirer}
          target={target}
          onUpdateAcquirer={updateAcquirer}
          onUpdateTarget={updateTarget}
          onNext={nav(2)}
        />
      )}
      {step === 2 && (
        <Step2_BuyerProfile
          acquirer={acquirer}
          mode={mode}
          onUpdate={updateAcquirer}
          onNext={nav(3)}
          onBack={nav(1)}
        />
      )}
      {step === 3 && (
        <Step3_TargetProfile
          target={target}
          mode={mode}
          onUpdate={updateTarget}
          onNext={nav(4)}
          onBack={nav(2)}
        />
      )}
      {step === 4 && (
        <Step4_Financing
          structure={structure}
          dealSize={dealSize}
          mode={mode}
          onUpdate={updateStructure}
          onNext={nav(5)}
          onBack={nav(3)}
        />
      )}
      {step === 5 && (
        <Step5_Synergies
          synergies={synergies}
          combinedRevenue={combinedRevenue}
          mode={mode}
          onUpdate={updateSynergies}
          onNext={nav(6)}
          onBack={nav(4)}
        />
      )}
      {(step === 6 || state.isLoading) && (
        <Step6_Review
          state={state}
          onBack={nav(5)}
          onRun={runAnalysis}
        />
      )}
    </AppShell>
  )
}
