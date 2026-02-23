/**
 * Central state for VC fund-seat analysis mode.
 * Single hook, single source of truth.
 * Persists fund profile to localStorage (deals are ephemeral).
 */

import { useState, useEffect, useCallback } from 'react'
import type {
  VCState,
  VCFlowStep,
  FundProfile,
  VCDealInput,
  VCDealOutput,
  DilutionAssumptions,
} from '../types/vc'
import { DEFAULT_FUND_PROFILE, DEFAULT_DILUTION_ASSUMPTIONS } from '../types/vc'
import { evaluateDeal } from '../lib/vc-api'

const FUND_STORAGE_KEY = 'vc_fund_profile'

function loadFundFromStorage(): FundProfile {
  try {
    const stored = localStorage.getItem(FUND_STORAGE_KEY)
    if (stored) return { ...DEFAULT_FUND_PROFILE, ...JSON.parse(stored) }
  } catch {
    // ignore
  }
  return { ...DEFAULT_FUND_PROFILE }
}

const DEFAULT_DEAL: Partial<VCDealInput> = {
  company_name: '',
  post_money_valuation: 0,
  check_size: 0,
  arr: 0,
  revenue_ttm: 0,
  revenue_growth_rate: 1.5,
  gross_margin: 0.70,
  burn_rate_monthly: 0,
  cash_on_hand: 0,
  dilution: { ...DEFAULT_DILUTION_ASSUMPTIONS },
  liquidation_stack: [],
  common_shares_pct: 0.30,
  expected_exit_years: 7,
  board_seat: false,
  pro_rata_rights: true,
  information_rights: true,
}

const INITIAL_STATE: VCState = {
  step: 1,
  fund: loadFundFromStorage(),
  deal: { ...DEFAULT_DEAL },
  output: null,
  isLoading: false,
  loadingMessage: '',
  error: null,
}

export function useVCState() {
  const [state, setState] = useState<VCState>(INITIAL_STATE)

  // Persist fund to localStorage on every change
  useEffect(() => {
    try {
      localStorage.setItem(FUND_STORAGE_KEY, JSON.stringify(state.fund))
    } catch {
      // ignore
    }
  }, [state.fund])

  const setStep = useCallback((step: VCFlowStep) => {
    setState(s => ({ ...s, step }))
  }, [])

  const updateFund = useCallback((updates: Partial<FundProfile>) => {
    setState(s => ({ ...s, fund: { ...s.fund, ...updates } }))
  }, [])

  const updateDeal = useCallback((updates: Partial<VCDealInput>) => {
    setState(s => ({ ...s, deal: { ...s.deal, ...updates } }))
  }, [])

  const updateDilution = useCallback((updates: Partial<DilutionAssumptions>) => {
    setState(s => ({
      ...s,
      deal: {
        ...s.deal,
        dilution: { ...(s.deal.dilution ?? DEFAULT_DILUTION_ASSUMPTIONS), ...updates },
      },
    }))
  }, [])

  const resetDeal = useCallback(() => {
    setState(s => ({
      ...s,
      step: 2,
      deal: { ...DEFAULT_DEAL },
      output: null,
      error: null,
    }))
  }, [])

  const resetAll = useCallback(() => {
    setState({
      ...INITIAL_STATE,
      fund: state.fund,  // preserve fund profile
    })
  }, [state.fund])

  const runEvaluation = useCallback(async () => {
    const { fund, deal } = state
    if (!deal.company_name || !deal.post_money_valuation || !deal.check_size) {
      setState(s => ({ ...s, error: 'Please enter company name, post-money valuation, and check size to evaluate the deal.' }))
      return
    }

    setState(s => ({ ...s, isLoading: true, loadingMessage: 'Running deal evaluation…', error: null }))

    try {
      const fullInput: VCDealInput = {
        company_name: deal.company_name ?? '',
        vertical: deal.vertical ?? 'b2b_saas',
        stage: deal.stage ?? 'seed',
        post_money_valuation: deal.post_money_valuation ?? 0,
        check_size: deal.check_size ?? 0,
        arr: deal.arr ?? 0,
        revenue_ttm: deal.revenue_ttm ?? 0,
        revenue_growth_rate: deal.revenue_growth_rate ?? 1.5,
        gross_margin: deal.gross_margin ?? 0.70,
        burn_rate_monthly: deal.burn_rate_monthly ?? 0,
        cash_on_hand: deal.cash_on_hand ?? 0,
        dilution: deal.dilution ?? { ...DEFAULT_DILUTION_ASSUMPTIONS },
        liquidation_stack: deal.liquidation_stack ?? [],
        common_shares_pct: deal.common_shares_pct ?? 0.30,
        expected_exit_years: deal.expected_exit_years ?? 7,
        board_seat: deal.board_seat ?? false,
        pro_rata_rights: deal.pro_rata_rights ?? true,
        information_rights: deal.information_rights ?? true,
        bear_exit_multiple_arr: deal.bear_exit_multiple_arr,
        base_exit_multiple_arr: deal.base_exit_multiple_arr,
        bull_exit_multiple_arr: deal.bull_exit_multiple_arr,
        fund,
      }

      const output = await evaluateDeal(fullInput)
      setState(s => ({
        ...s,
        output,
        isLoading: false,
        loadingMessage: '',
        step: 3,
      }))
    } catch (err) {
      setState(s => ({
        ...s,
        isLoading: false,
        loadingMessage: '',
        error: err instanceof Error ? err.message : 'Evaluation failed. Please try again.',
      }))
    }
  }, [state])

  return {
    state,
    setStep,
    updateFund,
    updateDeal,
    updateDilution,
    resetDeal,
    resetAll,
    runEvaluation,
  }
}
