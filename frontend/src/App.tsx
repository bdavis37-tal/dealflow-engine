// Licensed under the Business Source License 1.1 — see LICENSE file for details
import { useState, useEffect } from 'react'
import AppShell from './components/layout/AppShell'
import LandingPage from './components/layout/LandingPage'
import Step1_DealOverview from './components/flow/Step1_DealOverview'
import Step2_BuyerProfile from './components/flow/Step2_BuyerProfile'
import Step3_TargetProfile from './components/flow/Step3_TargetProfile'
import Step4_Financing from './components/flow/Step4_Financing'
import Step5_Synergies from './components/flow/Step5_Synergies'
import Step6_Review from './components/flow/Step6_Review'
import ResultsDashboard from './components/output/ResultsDashboard'
import ConversationalEntry from './components/flow/ConversationalEntry'
import { useDealState } from './hooks/useDealState'
import type { DealInput, DealStructure, PurchasePriceAllocation, AcquirerProfile, TargetProfile } from './types/deal'
import { checkAIStatus } from './lib/ai-api'

// Startup flow
import { useStartupState } from './hooks/useStartupState'
import StartupStep1_Overview from './components/flow/startup/StartupStep1_Overview'
import StartupStep2_Team from './components/flow/startup/StartupStep2_Team'
import StartupStep3_Traction from './components/flow/startup/StartupStep3_Traction'
import StartupStep4_Market from './components/flow/startup/StartupStep4_Market'
import StartupStep5_Review from './components/flow/startup/StartupStep5_Review'
import StartupDashboard from './components/output/startup/StartupDashboard'
import type { StartupFlowStep, TeamProfile, TractionMetrics, ProductProfile, MarketProfile, FundraisingProfile } from './types/startup'

// VC Investor flow
import { useVCState } from './hooks/useVCState'
import VCFundSetup from './components/vc/VCFundSetup'
import VCQuickScreen from './components/vc/VCQuickScreen'
import VCDashboard from './components/vc/VCDashboard'

type AppMode = 'ma' | 'startup' | 'vc'
type AppView = 'landing' | 'ma' | 'startup' | 'vc'

// ---------------------------------------------------------------------------
// Main App
// ---------------------------------------------------------------------------
export default function App() {
  const [appView, setAppView] = useState<AppView>('landing')

  // M&A state
  const {
    state,
    setStep,
    setMode,
    updateAcquirer,
    updateTarget,
    updateStructure,
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
    setAINative,
    updateAIAnswer,
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

  const nav = (s: number) => () => setStep(s as 1 | 2 | 3 | 4 | 5 | 6)
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
  // Landing page
  // ---------------------------------------------------------------------------
  if (appView === 'landing') {
    return (
      <LandingPage
        onSelectMode={(mode) => setAppView(mode)}
        onSkip={() => setAppView('ma')}
      />
    )
  }

  // ---------------------------------------------------------------------------
  // Startup flow
  // ---------------------------------------------------------------------------
  if (appView === 'startup') {
    if (startupState.output && !startupState.isLoading) {
      return (
        <AppShell appMode="startup" onAppModeChange={(m: AppMode) => setAppView(m)} onHome={() => setAppView('landing')} isResults>
          <StartupDashboard
            output={startupState.output}
            startupInput={{
              company_name: startupState.company_name,
              team: startupState.team as TeamProfile,
              traction: startupState.traction as TractionMetrics,
              product: startupState.product as ProductProfile,
              market: startupState.market as MarketProfile,
              fundraise: startupState.fundraise as FundraisingProfile,
            }}
            onReset={resetStartup}
          />
        </AppShell>
      )
    }

    return (
      <AppShell
        appMode="startup"
        onAppModeChange={(m: AppMode) => setAppView(m)}
        onHome={() => setAppView('landing')}
        step={Math.min(startupState.step, 4)}
      >
        {startupState.step === 1 && (
          <StartupStep1_Overview
            company_name={startupState.company_name}
            fundraise={startupState.fundraise}
            is_ai_native={startupState.is_ai_native}
            ai_native_score={startupState.ai_native_score}
            ai_answers={startupState.ai_answers}
            onNameChange={setCompanyName}
            onUpdateFundraise={updateFundraise}
            onSetAINative={setAINative}
            onUpdateAIAnswer={updateAIAnswer}
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
      </AppShell>
    )
  }

  // ---------------------------------------------------------------------------
  // VC Investor flow
  // ---------------------------------------------------------------------------
  if (appView === 'vc') {
    // Results view
    if (vcState.output && !vcState.isLoading) {
      return (
        <AppShell appMode="vc" onAppModeChange={(m: AppMode) => setAppView(m)} onHome={() => setAppView('landing')} isResults>
          <VCDashboard
            output={vcState.output}
            fund={vcState.fund}
            onNewDeal={resetVCDeal}
            onReset={resetVC}
          />
        </AppShell>
      )
    }

    return (
      <AppShell appMode="vc" onAppModeChange={(m: AppMode) => setAppView(m)} onHome={() => setAppView('landing')} step={vcState.step}>
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
      </AppShell>
    )
  }

  // ---------------------------------------------------------------------------
  // M&A flow
  // ---------------------------------------------------------------------------
  if (output && !state.isLoading) {
    const dealInput: DealInput = {
      acquirer: acquirer as AcquirerProfile,
      target: target as TargetProfile,
      structure: structure as DealStructure,
      ppa: ppa as PurchasePriceAllocation,
      synergies,
      mode,
      projection_years: 5,
    }
    return (
      <AppShell appMode="ma" onAppModeChange={(m: AppMode) => setAppView(m)} onHome={() => setAppView('landing')} isResults>
        <ResultsDashboard output={output} dealInput={dealInput} onReset={reset} mode={mode} />
      </AppShell>
    )
  }

  const combinedRevenue = (acquirer.revenue ?? 0) + (target.revenue ?? 0)
  const dealSize = target.acquisition_price ?? 0

  return (
    <AppShell
      appMode="ma"
      onAppModeChange={(m: AppMode) => setAppView(m)}
      onHome={() => setAppView('landing')}
      step={step}
      modelMode={mode}
      onModelModeChange={setMode}
    >
      {step === 1 && aiAvailable && showConversational && (
        <ConversationalEntry
          aiAvailable={aiAvailable}
          onExtracted={handleExtracted}
          onSkipToForm={() => setShowConversational(false)}
        />
      )}
      {step === 1 && (!aiAvailable || !showConversational) && (
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
