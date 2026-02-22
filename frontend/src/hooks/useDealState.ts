/**
 * Central state management for the deal flow.
 * Uses React useState + localStorage for persistence across reloads.
 */
import { useState, useCallback, useEffect, useRef } from 'react'
import type {
  DealState,
  FlowStep,
  ModelMode,
  AcquirerProfile,
  TargetProfile,
  DealStructure,
  PurchasePriceAllocation,
  SynergyAssumptions,
  DealOutput,
  DealInput,
} from '../types/deal'
import { analyzeDeal } from '../lib/api'

const STORAGE_KEY = 'dealflow_state'

const LOADING_MESSAGES = [
  'Building combined financial statements...',
  'Calculating deal returns...',
  'Running 500+ sensitivity scenarios...',
  'Analyzing risks and tolerances...',
  'Preparing your deal briefing...',
]

const defaultState: DealState = {
  step: 1,
  mode: 'quick',
  acquirer: {},
  target: {},
  structure: {
    cash_percentage: 1.0,
    stock_percentage: 0.0,
    debt_percentage: 0.0,
    debt_tranches: [],
    transaction_fees_pct: 0.02,
    advisory_fees: 0,
  },
  ppa: {
    asset_writeup: 0,
    asset_writeup_useful_life: 15,
    identifiable_intangibles: 0,
    intangible_useful_life: 10,
  },
  synergies: {
    cost_synergies: [],
    revenue_synergies: [],
  },
  output: null,
  isLoading: false,
  loadingMessage: '',
  error: null,
}

function loadFromStorage(): DealState {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return defaultState
    const parsed = JSON.parse(raw) as Partial<DealState>
    return {
      ...defaultState,
      ...parsed,
      output: null,        // Never persist output — always re-compute
      isLoading: false,
      loadingMessage: '',
      error: null,
      step: 1,             // Always start at step 1 on reload
    }
  } catch {
    return defaultState
  }
}

export function useDealState() {
  const [state, setState] = useState<DealState>(loadFromStorage)
  // Track the in-flight AbortController so repeated clicks cancel stale requests
  const abortControllerRef = useRef<AbortController | null>(null)

  // Persist input state (not output) to localStorage
  useEffect(() => {
    const { output, isLoading, loadingMessage, error, ...persistable } = state
    localStorage.setItem(STORAGE_KEY, JSON.stringify(persistable))
  }, [state])

  const setStep = useCallback((step: FlowStep) => {
    setState(s => ({ ...s, step }))
  }, [])

  const setMode = useCallback((mode: ModelMode) => {
    setState(s => ({ ...s, mode }))
  }, [])

  const updateAcquirer = useCallback((updates: Partial<AcquirerProfile>) => {
    setState(s => ({ ...s, acquirer: { ...s.acquirer, ...updates } }))
  }, [])

  const updateTarget = useCallback((updates: Partial<TargetProfile>) => {
    setState(s => ({ ...s, target: { ...s.target, ...updates } }))
  }, [])

  const updateStructure = useCallback((updates: Partial<DealStructure>) => {
    setState(s => ({ ...s, structure: { ...s.structure, ...updates } }))
  }, [])

  const updatePPA = useCallback((updates: Partial<PurchasePriceAllocation>) => {
    setState(s => ({ ...s, ppa: { ...s.ppa, ...updates } }))
  }, [])

  const updateSynergies = useCallback((updates: Partial<SynergyAssumptions>) => {
    setState(s => ({ ...s, synergies: { ...s.synergies, ...updates } }))
  }, [])

  const reset = useCallback(() => {
    localStorage.removeItem(STORAGE_KEY)
    setState(defaultState)
  }, [])

  const runAnalysis = useCallback(async () => {
    const { acquirer, target, structure, ppa, synergies, mode, isLoading } = state

    // Prevent overlapping requests: if already loading, abort the in-flight request
    // and start fresh rather than silently stacking duplicate calls.
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }
    const controller = new AbortController()
    abortControllerRef.current = controller

    setState(s => ({ ...s, isLoading: true, error: null, loadingMessage: LOADING_MESSAGES[0] }))

    // Show loading messages with artificial delays for perceived quality
    let msgIdx = 1
    const msgInterval = setInterval(() => {
      if (msgIdx < LOADING_MESSAGES.length) {
        setState(s => ({ ...s, loadingMessage: LOADING_MESSAGES[msgIdx] }))
        msgIdx++
      }
    }, 1200)

    try {
      const input: DealInput = {
        acquirer: acquirer as AcquirerProfile,
        target: target as TargetProfile,
        structure: structure as DealStructure,
        ppa: ppa as PurchasePriceAllocation,
        synergies,
        mode,
        projection_years: 5,
      }

      const output = await analyzeDeal(input, controller.signal)

      // Ignore stale response if this request was superseded by a newer one
      if (controller.signal.aborted) return

      clearInterval(msgInterval)
      abortControllerRef.current = null
      setState(s => ({
        ...s,
        output,
        isLoading: false,
        loadingMessage: '',
        step: 6 as FlowStep,
      }))
    } catch (err) {
      clearInterval(msgInterval)
      // Ignore abort errors — a newer request has taken over
      if (err instanceof Error && err.name === 'AbortError') return
      abortControllerRef.current = null
      const message = err instanceof Error ? err.message : 'Analysis failed'
      setState(s => ({ ...s, isLoading: false, loadingMessage: '', error: message }))
    }
  }, [state])

  return {
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
  }
}
