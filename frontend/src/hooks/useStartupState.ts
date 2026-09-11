/**
 * Central state management for the startup valuation flow.
 * Mirrors useDealState.ts patterns: useState + localStorage persistence.
 */
import { useState, useCallback, useEffect } from 'react'
import type {
  StartupState,
  StartupFlowStep,
  TeamProfile,
  TractionMetrics,
  ProductProfile,
  MarketProfile,
  FundraisingProfile,
  StartupInput,
  ReportContext,
  PreparerNote,
} from '../types/startup'
import { valueStartup } from '../lib/api'

const STORAGE_KEY = 'startup_valuation_state'

// Report context is presentation-layer state ONLY. It is persisted under its
// own key and is intentionally NEVER included in the /api/startup/value
// payload — computed results must be identical regardless of perspective.
const REPORT_CONTEXT_KEY = 'startup_report_context'

const defaultReportContext: ReportContext = {
  perspective: 'founder',
  notes: [],
  contended_placement: null,
}

function loadReportContext(): ReportContext {
  try {
    const raw = localStorage.getItem(REPORT_CONTEXT_KEY)
    if (!raw) return defaultReportContext
    const parsed = JSON.parse(raw) as Partial<ReportContext>
    return {
      ...defaultReportContext,
      ...parsed,
      notes: Array.isArray(parsed.notes) ? parsed.notes : [],
    }
  } catch {
    return defaultReportContext
  }
}

function makeNoteId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return `note_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
}

const AI_TOGGLE_CONFIG = {
  frozen_on: ['ai_ml_infrastructure', 'ai_enabled_saas'] as const,
  frozen_off: ['construction', 'restaurants', 'retail', 'real_estate', 'agriculture', 'waste_management', 'staffing'] as const,
  default_on: ['defense_tech', 'healthtech', 'biotech_pharma', 'developer_tools'] as const,
  default_off: ['b2b_saas', 'fintech', 'deep_tech_hardware', 'consumer', 'climate_energy', 'marketplace', 'vertical_saas'] as const,
}

function getDefaultAIToggle(vertical: string): boolean {
  if ((AI_TOGGLE_CONFIG.frozen_on as readonly string[]).includes(vertical)) return true
  if ((AI_TOGGLE_CONFIG.default_on as readonly string[]).includes(vertical)) return true
  return false
}

const defaultState: StartupState = {
  benchmark_version: '2026-09-11',
  step: 1,
  company_name: '',
  team: {
    founder_count: 2,
    prior_exits: 0,
    domain_experts: false,
    technical_cofounder: true,
    repeat_founder: false,
    tier1_background: false,
    notable_advisors: false,
  },
  traction: {
    has_revenue: false,
    monthly_recurring_revenue: 0,
    annual_recurring_revenue: 0,
    mom_growth_rate: 0,
    net_revenue_retention: 1.0,
    gross_margin: 0.7,
    monthly_burn_rate: 0,
    cash_on_hand: 0,
    paying_customer_count: 0,
    logo_customer_count: 0,
    has_lois: false,
    gmv_monthly: 0,
  },
  product: {
    stage: 'mvp',
    has_patent_or_ip: false,
    proprietary_data_moat: false,
    open_source_traction: false,
    regulatory_clearance: false,
  },
  market: {
    tam_usd_billions: 1,
    sam_usd_millions: 50,
    market_growth_rate: 0.15,
    competitive_moat: 'medium',
  },
  fundraise: {
    stage: 'pre_seed',
    vertical: 'b2b_saas',
    geography: 'other_us',
    raise_amount: 1.0,
    instrument: 'safe',
    pre_money_valuation_ask: null,
    safe_discount: 0,
    has_mfn_clause: false,
    existing_safe_stack: 0,
    is_ai_native: false,
    ai_native_score: 0,
  },
  is_ai_native: false,
  ai_native_score: 0,
  ai_answers: [false, false, false, false],
  output: null,
  isLoading: false,
  error: null,
}

function loadFromStorage(): StartupState {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return defaultState
    const parsed = JSON.parse(raw) as Partial<StartupState>
    return {
      ...defaultState,
      ...parsed,
      benchmark_version: parsed.benchmark_version ?? '2026-07-legacy',
      output: null,
      isLoading: false,
      error: null,
      step: 1,
    }
  } catch {
    return defaultState
  }
}

export function useStartupState() {
  const [state, setState] = useState<StartupState>(loadFromStorage)
  const [reportContext, setReportContext] = useState<ReportContext>(loadReportContext)

  // Persist inputs to localStorage
  useEffect(() => {
    const { output: _output, isLoading: _isLoading, error: _error, ...persistable } = state
    localStorage.setItem(STORAGE_KEY, JSON.stringify(persistable))
  }, [state])

  // Persist report context under its own key (never part of the API payload)
  useEffect(() => {
    localStorage.setItem(REPORT_CONTEXT_KEY, JSON.stringify(reportContext))
  }, [reportContext])

  const setBenchmarkVersion = useCallback((benchmark_version: string) => {
    setState(s => ({...s, benchmark_version, output: null, step: 1}))
  }, [])

  const setStep = useCallback((step: StartupFlowStep) => {
    setState(s => ({ ...s, step }))
  }, [])

  // Go back to a specific step from results — preserves all input data, clears output
  const goToStep = useCallback((step: StartupFlowStep) => {
    setState(s => ({ ...s, step, output: null, error: null }))
  }, [])

  const setCompanyName = useCallback((name: string) => {
    setState(s => ({ ...s, company_name: name }))
  }, [])

  const updateTeam = useCallback((updates: Partial<TeamProfile>) => {
    setState(s => ({ ...s, team: { ...s.team, ...updates } }))
  }, [])

  const updateTraction = useCallback((updates: Partial<TractionMetrics>) => {
    setState(s => ({ ...s, traction: { ...s.traction, ...updates } }))
  }, [])

  const updateProduct = useCallback((updates: Partial<ProductProfile>) => {
    setState(s => ({ ...s, product: { ...s.product, ...updates } }))
  }, [])

  const updateMarket = useCallback((updates: Partial<MarketProfile>) => {
    setState(s => ({ ...s, market: { ...s.market, ...updates } }))
  }, [])

  const updateFundraise = useCallback((updates: Partial<FundraisingProfile>) => {
    setState(s => {
      const newFundraise = { ...s.fundraise, ...updates }
      // Reset AI toggle when vertical changes
      if (updates.vertical && updates.vertical !== s.fundraise.vertical) {
        const defaultOn = getDefaultAIToggle(updates.vertical)
        return {
          ...s,
          fundraise: newFundraise,
          is_ai_native: defaultOn,
          ai_native_score: 0,
          ai_answers: [false, false, false, false] as [boolean, boolean, boolean, boolean],
        }
      }
      return { ...s, fundraise: newFundraise }
    })
  }, [])

  const reset = useCallback(() => {
    localStorage.removeItem(STORAGE_KEY)
    setState(defaultState)
  }, [])

  // --- Report context actions (presentation only — never sent to the API) ---

  const updateReportContext = useCallback((updates: Partial<ReportContext>) => {
    setReportContext(c => ({ ...c, ...updates }))
  }, [])

  const addNote = useCallback((note?: Partial<Omit<PreparerNote, 'id'>>) => {
    setReportContext(c => ({
      ...c,
      notes: [
        ...c.notes,
        { id: makeNoteId(), anchor: note?.anchor ?? 'traction', claim: note?.claim ?? '', evidence: note?.evidence },
      ],
    }))
  }, [])

  const updateNote = useCallback((id: string, updates: Partial<Omit<PreparerNote, 'id'>>) => {
    setReportContext(c => ({
      ...c,
      notes: c.notes.map(n => (n.id === id ? { ...n, ...updates } : n)),
    }))
  }, [])

  const removeNote = useCallback((id: string) => {
    setReportContext(c => ({ ...c, notes: c.notes.filter(n => n.id !== id) }))
  }, [])

  const restoreAIState = useCallback((is_ai_native: boolean, ai_native_score: number, ai_answers: [boolean, boolean, boolean, boolean]) => {
    setState(s => ({...s, is_ai_native, ai_native_score, ai_answers}))
  }, [])

  const setAINative = useCallback((value: boolean) => {
    setState(s => ({
      ...s,
      is_ai_native: value,
      // Reset answers when toggling off
      ...(value ? {} : { ai_answers: [false, false, false, false] as [boolean, boolean, boolean, boolean], ai_native_score: 0 }),
    }))
  }, [])

  const updateAIAnswer = useCallback((index: number, value: boolean) => {
    setState(s => {
      const newAnswers = [...s.ai_answers] as [boolean, boolean, boolean, boolean]
      newAnswers[index] = value
      const score = newAnswers.filter(Boolean).length / 4
      return { ...s, ai_answers: newAnswers, ai_native_score: score }
    })
  }, [])

  const runValuation = useCallback(async () => {
    const { company_name, team, traction, product, market, fundraise } = state

    setState(s => ({ ...s, isLoading: true, error: null }))

    try {
      const input: StartupInput = {
        benchmark_version: state.benchmark_version,
        company_name: company_name || 'My Startup',
        team: team as TeamProfile,
        traction: traction as TractionMetrics,
        product: product as ProductProfile,
        market: market as MarketProfile,
        fundraise: {
          ...(fundraise as FundraisingProfile),
          is_ai_native: state.is_ai_native,
          ai_native_score: state.ai_native_score,
        },
      }

      const output = await valueStartup(input)

      setState(s => ({
        ...s,
        output,
        isLoading: false,
        step: 5 as StartupFlowStep,
      }))
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Valuation failed'
      setState(s => ({ ...s, isLoading: false, error: message }))
    }
  }, [state])

  return {
    state,
    setBenchmarkVersion,
    setStep,
    goToStep,
    setCompanyName,
    updateTeam,
    updateTraction,
    updateProduct,
    updateMarket,
    updateFundraise,
    reset,
    runValuation,
    setAINative,
    restoreAIState,
    updateAIAnswer,
    reportContext,
    updateReportContext,
    addNote,
    updateNote,
    removeNote,
  }
}
