import { useState, useEffect } from 'react'
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

export default function App() {
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

  const { step, mode, acquirer, target, structure, ppa, synergies, output } = state

  const [aiAvailable, setAiAvailable] = useState(false)
  // Show conversational entry first on step 1; skip to form if user prefers
  const [showConversational, setShowConversational] = useState(true)

  useEffect(() => {
    checkAIStatus()
      .then(s => setAiAvailable(s.ai_available))
      .catch(() => setAiAvailable(false))
  }, [])

  const nav = (s: FlowStep) => () => setStep(s)

  const handleExtracted = (
    acq: Partial<AcquirerProfile>,
    tgt: Partial<TargetProfile>,
    _summary: string,
  ) => {
    updateAcquirer(acq)
    updateTarget(tgt)
    setStep(2)
  }

  // If we have output, show the results dashboard
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
