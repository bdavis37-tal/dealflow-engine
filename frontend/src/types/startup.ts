/**
 * TypeScript interfaces mirroring backend/app/engine/startup_models.py
 * Keep in sync with the Python models.
 */

// ---------------------------------------------------------------------------
// Enumerations
// ---------------------------------------------------------------------------

export type StartupStage = 'pre_seed' | 'seed' | 'series_a'

export type StartupVertical =
  | 'ai_ml_infrastructure'
  | 'ai_enabled_saas'
  | 'b2b_saas'
  | 'fintech'
  | 'healthtech'
  | 'biotech_pharma'
  | 'deep_tech_hardware'
  | 'consumer'
  | 'climate_energy'
  | 'marketplace'
  | 'vertical_saas'
  | 'developer_tools'
  | 'defense_tech'

export type InstrumentType = 'safe' | 'convertible_note' | 'priced_equity'

export type Geography =
  | 'bay_area'
  | 'new_york'
  | 'boston'
  | 'seattle'
  | 'austin'
  | 'los_angeles'
  | 'chicago'
  | 'other_us'
  | 'international'

export type ProductStage = 'idea' | 'mvp' | 'beta' | 'paying_customers' | 'scaling'

export type ValuationSignal = 'strong' | 'fair' | 'weak' | 'warning'

export type ValuationVerdict = 'strong' | 'fair' | 'stretched' | 'at_risk'

export type RaiseSignal = 'raise_now' | 'raise_in_months' | 'focus_milestones'

// ---------------------------------------------------------------------------
// Input models
// ---------------------------------------------------------------------------

export interface TeamProfile {
  founder_count: number
  prior_exits: number
  domain_experts: boolean
  technical_cofounder: boolean
  repeat_founder: boolean
  tier1_background: boolean
  notable_advisors: boolean
}

export interface TractionMetrics {
  has_revenue: boolean
  monthly_recurring_revenue: number
  annual_recurring_revenue: number
  mom_growth_rate: number
  net_revenue_retention: number
  gross_margin: number
  monthly_burn_rate: number
  cash_on_hand: number
  paying_customer_count: number
  logo_customer_count: number
  has_lois: boolean
  gmv_monthly: number
}

export interface ProductProfile {
  stage: ProductStage
  has_patent_or_ip: boolean
  proprietary_data_moat: boolean
  open_source_traction: boolean
  regulatory_clearance: boolean
}

export interface MarketProfile {
  tam_usd_billions: number
  sam_usd_millions: number
  market_growth_rate: number
  competitive_moat: 'low' | 'medium' | 'high'
}

export interface FundraisingProfile {
  stage: StartupStage
  vertical: StartupVertical
  geography: Geography
  raise_amount: number
  instrument: InstrumentType
  pre_money_valuation_ask: number | null
  safe_discount: number
  has_mfn_clause: boolean
  existing_safe_stack: number
  is_ai_native: boolean
  ai_native_score: number
}

export interface StartupInput {
  company_name: string
  team: TeamProfile
  traction: TractionMetrics
  product: ProductProfile
  market: MarketProfile
  fundraise: FundraisingProfile
  berkus_scores?: Record<string, number> | null
  scorecard_scores?: Record<string, number> | null
  risk_factor_scores?: Record<string, number> | null
}

// ---------------------------------------------------------------------------
// Output models
// ---------------------------------------------------------------------------

export interface ValuationMethodResult {
  method_name: string
  method_label: string
  indicated_value: number | null
  value_low: number | null
  value_high: number | null
  applicable: boolean
  rationale: string
  inputs_used: Record<string, unknown>
}

export interface DilutionScenario {
  round_label: string
  pre_money: number
  raise_amount: number
  post_money: number
  investor_ownership_pct: number
  founder_ownership_pct_before: number
  founder_ownership_pct_after: number
  dilution_this_round: number
}

export interface SAFEConversionSummary {
  safe_amount: number
  valuation_cap: number
  discount_rate: number
  conversion_price_at_cap: number
  implied_ownership_pct: number
  note: string
}

export interface RoundTimingSignal {
  runway_months: number
  months_to_next_round: number
  fundraise_process_months: number
  months_until_raise_window: number
  signal: RaiseSignal
  signal_label: string
  signal_detail: string
  milestone_gaps: string[]
  milestone_met_count: number
  milestone_total_count: number
  raise_in_months: number | null
  warnings: string[]
}

export interface ScorecardFlag {
  metric: string
  value: string
  signal: ValuationSignal
  benchmark: string
  commentary: string
}

export interface StartupValuationOutput {
  company_name: string
  stage: StartupStage
  vertical: StartupVertical

  blended_valuation: number
  valuation_range_low: number
  valuation_range_high: number
  recommended_safe_cap: number | null
  implied_dilution: number

  method_results: ValuationMethodResult[]

  benchmark_p25: number
  benchmark_p50: number
  benchmark_p75: number
  benchmark_p95: number
  percentile_in_market: string

  dilution_scenarios: DilutionScenario[]
  safe_conversion: SAFEConversionSummary | null

  investor_scorecard: ScorecardFlag[]
  traction_bar: string

  verdict: ValuationVerdict
  verdict_headline: string
  verdict_subtext: string

  warnings: string[]
  computation_notes: string[]

  vertical_benchmarks: Record<string, unknown>

  // AI modifier outputs (all null/false when modifier not applied)
  ai_modifier_applied: boolean
  ai_premium_multiplier: number | null
  ai_premium_context: string | null
  blended_before_ai: number | null
  ai_native_score: number | null
  round_timing: RoundTimingSignal
}

// ---------------------------------------------------------------------------
// UI State
// ---------------------------------------------------------------------------

export type StartupFlowStep = 1 | 2 | 3 | 4 | 5

export interface StartupState {
  step: StartupFlowStep
  company_name: string
  team: Partial<TeamProfile>
  traction: Partial<TractionMetrics>
  product: Partial<ProductProfile>
  market: Partial<MarketProfile>
  fundraise: Partial<FundraisingProfile>
  is_ai_native: boolean
  ai_native_score: number
  ai_answers: [boolean, boolean, boolean, boolean]
  output: StartupValuationOutput | null
  isLoading: boolean
  error: string | null
}

// ---------------------------------------------------------------------------
// Vertical / stage display helpers
// ---------------------------------------------------------------------------

export const VERTICAL_LABELS: Record<StartupVertical, string> = {
  ai_ml_infrastructure: 'AI / ML Infrastructure',
  ai_enabled_saas: 'AI-Enabled SaaS',
  b2b_saas: 'B2B SaaS (Traditional)',
  fintech: 'Fintech',
  healthtech: 'Healthcare / HealthTech',
  biotech_pharma: 'Biotech / Pharma',
  deep_tech_hardware: 'Deep Tech / Hardware',
  consumer: 'Consumer',
  climate_energy: 'Climate / Energy',
  marketplace: 'Marketplace',
  vertical_saas: 'Vertical / Industry SaaS',
  developer_tools: 'Developer Tools / Infrastructure',
  defense_tech: 'Defense Tech / National Security',
}

export const STAGE_LABELS: Record<StartupStage, string> = {
  pre_seed: 'Pre-Seed',
  seed: 'Seed',
  series_a: 'Series A',
}

export const GEOGRAPHY_LABELS: Record<Geography, string> = {
  bay_area: 'Bay Area / SF',
  new_york: 'New York',
  boston: 'Boston',
  seattle: 'Seattle',
  austin: 'Austin',
  los_angeles: 'Los Angeles',
  chicago: 'Chicago',
  other_us: 'Other US',
  international: 'International',
}

export const INSTRUMENT_LABELS: Record<InstrumentType, string> = {
  safe: 'SAFE (Simple Agreement for Future Equity)',
  convertible_note: 'Convertible Note',
  priced_equity: 'Priced Equity Round',
}

export const PRODUCT_STAGE_LABELS: Record<ProductStage, string> = {
  idea: 'Idea / Concept',
  mvp: 'MVP Built',
  beta: 'Beta Users',
  paying_customers: 'Paying Customers',
  scaling: 'Scaling Revenue',
}

// ---------------------------------------------------------------------------
// AI Narrative
// ---------------------------------------------------------------------------

export interface StartupNarrativeResponse {
  verdict_narrative: string | null
  scorecard_commentary: Record<string, string>
  executive_summary: string | null
  ai_available: boolean
  cached: boolean
}
