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
  StartupValuationOutput,
  StartupInput,
} from '../types/startup'
import { valueStartup } from '../lib/api'

const STORAGE_KEY = 'startup_valuation_state'

const defaultState: StartupState = {
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
  },
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

  // Persist inputs to localStorage
  useEffect(() => {
    const { output, isLoading, error, ...persistable } = state
    localStorage.setItem(STORAGE_KEY, JSON.stringify(persistable))
  }, [state])

  const setStep = useCallback((step: StartupFlowStep) => {
    setState(s => ({ ...s, step }))
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
    setState(s => ({ ...s, fundraise: { ...s.fundraise, ...updates } }))
  }, [])

  const reset = useCallback(() => {
    localStorage.removeItem(STORAGE_KEY)
    setState(defaultState)
  }, [])

  const runValuation = useCallback(async () => {
    const { company_name, team, traction, product, market, fundraise } = state

    setState(s => ({ ...s, isLoading: true, error: null }))

    try {
      const input: StartupInput = {
        company_name: company_name || 'My Startup',
        team: team as TeamProfile,
        traction: traction as TractionMetrics,
        product: product as ProductProfile,
        market: market as MarketProfile,
        fundraise: fundraise as FundraisingProfile,
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
    setStep,
    setCompanyName,
    updateTeam,
    updateTraction,
    updateProduct,
    updateMarket,
    updateFundraise,
    reset,
    runValuation,
  }
}
