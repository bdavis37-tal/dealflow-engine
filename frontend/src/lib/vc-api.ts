/**
 * VC fund-seat API client.
 * Calls /api/vc/* endpoints.
 */

import type {
  VCDealInput,
  VCDealOutput,
  FundProfile,
  PortfolioInput,
  PortfolioOutput,
  QSBSOutput,
  AntiDilutionOutput,
  BridgeRoundOutput,
  ProRataAnalysis,
  WaterfallDistribution,
  GPCarryInput,
  GPCarryOutput,
  FundIRRInput,
  FundIRROutput,
  SAFEConversionInput,
  SAFEConversionOutput,
  DealComparisonOutput,
  VCNarrativeResponse,
} from '../types/vc'

const BASE = '/api/vc'

async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || `API error ${res.status}`)
  }
  return res.json()
}

async function apiGet<T>(path: string, params?: Record<string, string | number>): Promise<T> {
  const url = new URL(`${BASE}${path}`, window.location.origin)
  if (params) {
    Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, String(v)))
  }
  const res = await fetch(url.toString())
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || `API error ${res.status}`)
  }
  return res.json()
}

// ---------------------------------------------------------------------------
// Core deal evaluation
// ---------------------------------------------------------------------------

export async function evaluateDeal(deal: VCDealInput): Promise<VCDealOutput> {
  return apiPost<VCDealOutput>('/evaluate', deal)
}

// ---------------------------------------------------------------------------
// Fund profile defaults
// ---------------------------------------------------------------------------

export async function getFundDefaults(fundSizeUsdM: number): Promise<{
  fund_size: number
  recommended_defaults: Partial<FundProfile>
  computed: {
    investable_capital: number
    implied_initial_check: number
    initial_check_range: { low: number; high: number }
    reserve_pool: number
  }
  power_law_context: Record<string, unknown>
}> {
  return apiGet('/fund/defaults', { fund_size_usd_m: fundSizeUsdM })
}

// ---------------------------------------------------------------------------
// Portfolio
// ---------------------------------------------------------------------------

export async function analyzePortfolio(inp: PortfolioInput): Promise<PortfolioOutput> {
  return apiPost<PortfolioOutput>('/portfolio', inp)
}

// ---------------------------------------------------------------------------
// Waterfall
// ---------------------------------------------------------------------------

export async function analyzeWaterfall(
  deal: VCDealInput,
  exitEv: number,
): Promise<WaterfallDistribution> {
  return apiPost<WaterfallDistribution>('/waterfall', { ...deal, exit_ev: exitEv })
}

// ---------------------------------------------------------------------------
// Pro-rata
// ---------------------------------------------------------------------------

export async function analyzeProRata(
  deal: VCDealInput,
  fund: FundProfile,
  nextRoundValuation: number,
  proRataCheck: number,
): Promise<ProRataAnalysis> {
  return apiPost<ProRataAnalysis>('/pro-rata', {
    ...deal,
    fund,
    next_round_valuation: nextRoundValuation,
    pro_rata_check: proRataCheck,
  })
}

// ---------------------------------------------------------------------------
// QSBS
// ---------------------------------------------------------------------------

export interface QSBSInput {
  company_name: string
  incorporated_in_c_corp: boolean
  domestic_us_corp: boolean
  active_business: boolean
  assets_at_issuance_under_50m: boolean
  original_issuance: boolean
  holding_period_years: number
  investment_amount: number
  issuance_date_post_july_2025: boolean
  fund_size: number
  lp_count: number
  lp_marginal_tax_rate: number
}

export async function checkQSBS(inp: QSBSInput): Promise<QSBSOutput> {
  return apiPost<QSBSOutput>('/qsbs', inp)
}

// ---------------------------------------------------------------------------
// Anti-dilution
// ---------------------------------------------------------------------------

export interface AntiDilutionInput {
  company_name: string
  original_price_per_share: number
  original_shares: number
  down_round_price_per_share: number
  down_round_new_shares_issued: number
  anti_dilution_type: 'none' | 'broad_based_wa' | 'full_ratchet'
  investor_preferred_shares: number
}

export async function analyzeAntiDilution(inp: AntiDilutionInput): Promise<AntiDilutionOutput> {
  return apiPost<AntiDilutionOutput>('/anti-dilution', inp)
}

// ---------------------------------------------------------------------------
// Bridge round
// ---------------------------------------------------------------------------

export interface BridgeRoundInput {
  company_name: string
  bridge_amount: number
  instrument: string
  discount_rate: number
  interest_rate: number
  maturity_months: number
  pre_bridge_valuation: number
  expected_next_round_valuation: number
  current_ownership_pct: number
  fund_is_participating: boolean
  pro_rata_amount: number
}

export async function analyzeBridge(inp: BridgeRoundInput): Promise<BridgeRoundOutput> {
  return apiPost<BridgeRoundOutput>('/bridge', inp)
}

// ---------------------------------------------------------------------------
// Benchmarks
// ---------------------------------------------------------------------------

export async function getVCBenchmarks(
  vertical: string,
  stage: string,
): Promise<Record<string, unknown>> {
  return apiGet('/benchmarks', { vertical, stage })
}

export async function listVCVerticals(): Promise<{ value: string; label: string; description: string }[]> {
  return apiGet('/verticals')
}

export async function listVCStages(): Promise<{ value: string; label: string; description: string }[]> {
  return apiGet('/stages')
}


// ---------------------------------------------------------------------------
// GP Carry Economics (Phase 5)
// ---------------------------------------------------------------------------

export async function analyzeGPCarry(inp: GPCarryInput): Promise<GPCarryOutput> {
  return apiPost<GPCarryOutput>('/gp-carry', inp)
}


// ---------------------------------------------------------------------------
// Fund-Level IRR & J-Curve (Phase 5)
// ---------------------------------------------------------------------------

export async function analyzeFundIRR(inp: FundIRRInput): Promise<FundIRROutput> {
  return apiPost<FundIRROutput>('/fund-irr', inp)
}


// ---------------------------------------------------------------------------
// SAFE Conversion Modeling (Phase 5)
// ---------------------------------------------------------------------------

export async function analyzeSAFEConversion(inp: SAFEConversionInput): Promise<SAFEConversionOutput> {
  return apiPost<SAFEConversionOutput>('/safe-conversion', inp)
}


// ---------------------------------------------------------------------------
// Deal Comparison (Phase 5)
// ---------------------------------------------------------------------------

export interface DealComparisonRequest {
  deals: (VCDealInput & { fund: FundProfile })[]
}

export async function compareDeals(req: DealComparisonRequest): Promise<DealComparisonOutput> {
  return apiPost<DealComparisonOutput>('/compare', req)
}


// ---------------------------------------------------------------------------
// VC AI Narrative (Phase 5)
// ---------------------------------------------------------------------------

export interface VCNarrativeRequest {
  deal_input: VCDealInput
  deal_output: VCDealOutput
  fund_profile: FundProfile
}

export async function generateVCNarrative(req: VCNarrativeRequest): Promise<VCNarrativeResponse> {
  const res = await fetch('/api/ai/vc-narrative', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || `API error ${res.status}`)
  }
  return res.json()
}
