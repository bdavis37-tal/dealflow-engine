/**
 * TypeScript interfaces for VC fund-seat analysis.
 * Mirrors backend/app/engine/vc_fund_models.py
 * All monetary values: USD millions. Rates: decimals.
 */

// ---------------------------------------------------------------------------
// Enums
// ---------------------------------------------------------------------------

export type VCStage =
  | 'pre_seed'
  | 'seed'
  | 'series_a'
  | 'series_b'
  | 'series_c'
  | 'growth'

export type VCVertical =
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

export type PreferenceType =
  | 'non_participating'
  | 'participating'
  | 'participating_capped'

export type AntiDilutionType =
  | 'none'
  | 'broad_based_wa'
  | 'full_ratchet'

// ---------------------------------------------------------------------------
// Fund Profile
// ---------------------------------------------------------------------------

export interface FundProfile {
  fund_name: string
  fund_size: number                    // USD millions
  vintage_year: number
  management_fee_pct: number           // 0.02 = 2%
  management_fee_years: number
  carry_pct: number                    // 0.20 = 20%
  hurdle_rate: number                  // 0.08 = 8%
  reserve_ratio: number                // 0.40 = 40%
  target_initial_check_count: number
  target_ownership_pct: number         // 0.10 = 10%
  recycling_pct: number
  deployment_period_years: number
}

// ---------------------------------------------------------------------------
// Deal Input
// ---------------------------------------------------------------------------

export interface DilutionAssumptions {
  seed_to_a: number
  a_to_b: number
  b_to_c: number
  c_to_ipo: number
  option_pool_expansion: number
}

export interface LiquidationPreference {
  share_class: string
  invested_amount: number
  preference_multiple: number
  preference_type: PreferenceType
  participation_cap?: number
  anti_dilution: AntiDilutionType
  seniority: number
}

export interface VCDealInput {
  company_name: string
  vertical: VCVertical
  stage: VCStage
  post_money_valuation: number
  check_size: number
  arr: number
  revenue_ttm: number
  revenue_growth_rate: number
  gross_margin: number
  burn_rate_monthly: number
  cash_on_hand: number
  dilution: DilutionAssumptions
  liquidation_stack: LiquidationPreference[]
  common_shares_pct: number
  expected_exit_years: number
  board_seat: boolean
  pro_rata_rights: boolean
  information_rights: boolean
  bear_exit_multiple_arr?: number
  base_exit_multiple_arr?: number
  bull_exit_multiple_arr?: number
  fund: FundProfile
}

// ---------------------------------------------------------------------------
// Scenario
// ---------------------------------------------------------------------------

export interface VCScenario {
  label: string
  probability: number
  exit_year: number
  exit_multiple_arr: number
  exit_enterprise_value: number
  gross_proceeds_to_fund: number
  net_proceeds_to_fund: number
  gross_moic: number
  net_moic: number
  gross_irr: number
  net_irr: number
  fund_contribution_x: number
  outcome_description: string
}

// ---------------------------------------------------------------------------
// Ownership Math
// ---------------------------------------------------------------------------

export interface DilutionStackRow {
  round: string
  dilution_pct: number
  ownership_before: number
  ownership_after: number
}

export interface OwnershipMath {
  entry_ownership_pct: number
  exit_ownership_pct: number
  dilution_stack: DilutionStackRow[]
  total_dilution_pct: number
  fund_returner_1x_exit: number
  fund_returner_3x_exit: number
  fund_returner_5x_exit: number
  exit_values_tested: number[]
  gross_proceeds_at_exits: number[]
  fund_contribution_at_exits: number[]
  required_arr_multiple_for_1x_fund?: number
  required_arr_multiple_for_3x_fund?: number
}

// ---------------------------------------------------------------------------
// Quick Screen
// ---------------------------------------------------------------------------

export type ScreenRecommendation = 'pass' | 'look_deeper' | 'strong_interest'

export interface QuickScreenResult {
  company_name: string
  stage: VCStage
  vertical: VCVertical
  post_money: number
  check_size: number
  entry_ownership_pct: number
  exit_ownership_pct: number
  fund_returner_threshold: number
  fund_returner_arr_multiple?: number
  bear_ev: number
  base_ev: number
  bull_ev: number
  bear_moic: number
  base_moic: number
  bull_moic: number
  recommendation: ScreenRecommendation
  recommendation_rationale: string
  flags: string[]
}

// ---------------------------------------------------------------------------
// Waterfall
// ---------------------------------------------------------------------------

export interface WaterfallShareClass {
  share_class: string
  type: PreferenceType
  preference_amount: number
  preference_multiple: number
  liquidation_payout: number
  conversion_value: number
  gets: number
  converted: boolean
}

export interface WaterfallDistribution {
  exit_ev: number
  share_classes: WaterfallShareClass[]
  common_gets: number
  total_distributed: number
  investor_total: number
  investor_moic: number
  conversion_was_optimal: boolean
}

// ---------------------------------------------------------------------------
// IC Memo
// ---------------------------------------------------------------------------

export interface ICMemoFinancials {
  company_name: string
  stage: VCStage
  vertical: VCVertical
  check_size: number
  post_money: number
  entry_ownership_pct: number
  instrument: string
  board_seat: boolean
  pro_rata_rights: boolean
  arr: number
  revenue_growth_rate: number
  gross_margin: number
  burn_rate_monthly: number
  runway_months?: number
  ownership_at_exit: number
  total_dilution_pct: number
  scenarios: VCScenario[]
  expected_value: number
  fund_returner_threshold: number
  fund_contribution_base: number
  arr_multiple_at_entry?: number
  stage_median_arr_multiple?: number
  valuation_vs_benchmark: string
  investment_thesis_prompt: string
  financial_summary_text: string
}

// ---------------------------------------------------------------------------
// Full Deal Output
// ---------------------------------------------------------------------------

export interface VCDealOutput {
  company_name: string
  stage: VCStage
  vertical: VCVertical
  fund_size: number
  check_size: number
  post_money: number
  ownership: OwnershipMath
  bear_scenario: VCScenario
  base_scenario: VCScenario
  bull_scenario: VCScenario
  expected_value: number
  expected_moic: number
  expected_irr: number
  quick_screen: QuickScreenResult
  waterfall?: WaterfallDistribution
  ic_memo: ICMemoFinancials
  power_law_note: string
  ownership_adequacy: 'strong' | 'acceptable' | 'thin'
  vertical_benchmarks_used: Record<string, unknown>
  flags: string[]
  warnings: string[]
  computation_notes: string[]
}

// ---------------------------------------------------------------------------
// Portfolio
// ---------------------------------------------------------------------------

export interface PortfolioPosition {
  company_name: string
  vertical: VCVertical
  stage_at_entry: VCStage
  check_size: number
  post_money_at_entry: number
  entry_ownership_pct: number
  current_ownership_pct: number
  reserve_allocated: number
  reserve_deployed: number
  last_round_valuation?: number
  status: 'active' | 'written_off' | 'exited' | 'partially_exited'
  is_lead: boolean
  vintage_year: number
  cost_basis: number
  fair_value?: number
  realized_proceeds: number
}

export interface PortfolioConstructionStats {
  fund_size: number
  investable_capital: number
  initial_check_pool: number
  reserve_pool: number
  total_initial_deployed: number
  total_reserve_deployed: number
  total_deployed: number
  pct_deployed: number
  initial_remaining: number
  reserve_remaining: number
  total_remaining: number
  company_count: number
  stage_breakdown: Record<string, number>
  vertical_breakdown: Record<string, number>
  largest_position_pct: number
  total_cost_basis: number
  total_fair_value: number
  unrealized_tvpi: number
  realized_proceeds: number
  dpi: number
  rvpi: number
  tvpi: number
  reserve_adequacy: 'adequate' | 'tight' | 'over-reserved'
  average_follow_on_multiple: number
}

export interface PortfolioOutput {
  stats: PortfolioConstructionStats
  positions: PortfolioPosition[]
  alerts: string[]
  recommendations: string[]
}

// ---------------------------------------------------------------------------
// Pro-Rata Analysis
// ---------------------------------------------------------------------------

export interface ProRataAnalysis {
  company_name: string
  next_round_valuation: number
  pro_rata_amount: number
  maintained_ownership_pct: number
  diluted_ownership_if_pass: number
  reserve_impact: number
  reserve_pct_remaining_after: number
  exercise_scenarios: VCScenario[]
  pass_scenarios: VCScenario[]
  expected_value_exercise: number
  expected_value_pass: number
  recommendation: 'exercise' | 'pass' | 'partial'
  recommendation_rationale: string
}

// ---------------------------------------------------------------------------
// QSBS
// ---------------------------------------------------------------------------

export interface QSBSEligibilityCheck {
  name: string
  passed: boolean
  note: string
}

export interface QSBSOutput {
  company_name: string
  is_eligible: boolean
  eligibility_checks: QSBSEligibilityCheck[]
  holding_period_satisfied: boolean
  years_remaining_to_qualify?: number
  exclusion_cap_per_taxpayer: number
  estimated_gain_excluded: number
  estimated_federal_tax_saved_per_lp: number
  estimated_total_lp_benefit: number
  notes: string[]
  irc_citation: string
}

// ---------------------------------------------------------------------------
// Anti-Dilution
// ---------------------------------------------------------------------------

export interface AntiDilutionOutput {
  company_name: string
  anti_dilution_type: AntiDilutionType
  original_price: number
  down_round_price: number
  adjusted_conversion_price: number
  additional_shares_issued: number
  economic_impact: number
  effective_ownership_pct_after: number
  notes: string
}

// ---------------------------------------------------------------------------
// Bridge Round
// ---------------------------------------------------------------------------

export interface BridgeRoundOutput {
  company_name: string
  bridge_amount: number
  instrument: string
  pre_bridge_ownership: number
  post_bridge_ownership_if_convert: number
  dilution_from_bridge: number
  effective_conversion_price: number
  implied_discount_to_next_round: number
  additional_runway_months?: number
  irr_if_participate?: number
  irr_if_pass?: number
  recommendation: string
  notes: string[]
}

// ---------------------------------------------------------------------------
// UI State
// ---------------------------------------------------------------------------

export type VCFlowStep = 1 | 2 | 3

export interface VCState {
  step: VCFlowStep
  fund: FundProfile
  deal: Partial<VCDealInput>
  output: VCDealOutput | null
  isLoading: boolean
  loadingMessage: string
  error: string | null
}

// ---------------------------------------------------------------------------
// VC Vertical display labels
// ---------------------------------------------------------------------------

export const VC_VERTICAL_LABELS: Record<VCVertical, string> = {
  ai_ml_infrastructure: 'AI / ML Infrastructure',
  ai_enabled_saas: 'AI-Enabled SaaS',
  b2b_saas: 'B2B SaaS',
  fintech: 'Fintech',
  healthtech: 'Healthtech',
  biotech_pharma: 'Biotech / Pharma',
  deep_tech_hardware: 'Deep Tech / Hardware',
  consumer: 'Consumer',
  climate_energy: 'Climate / Energy',
  marketplace: 'Marketplace',
  vertical_saas: 'Vertical SaaS',
  developer_tools: 'Developer Tools',
}

export const VC_STAGE_LABELS: Record<VCStage, string> = {
  pre_seed: 'Pre-Seed',
  seed: 'Seed',
  series_a: 'Series A',
  series_b: 'Series B',
  series_c: 'Series C',
  growth: 'Growth',
}

export const DEFAULT_DILUTION_ASSUMPTIONS: DilutionAssumptions = {
  seed_to_a: 0.205,
  a_to_b: 0.18,
  b_to_c: 0.16,
  c_to_ipo: 0.12,
  option_pool_expansion: 0.05,
}

export const DEFAULT_FUND_PROFILE: FundProfile = {
  fund_name: 'My Fund',
  fund_size: 100,
  vintage_year: new Date().getFullYear(),
  management_fee_pct: 0.02,
  management_fee_years: 5,
  carry_pct: 0.20,
  hurdle_rate: 0.08,
  reserve_ratio: 0.40,
  target_initial_check_count: 25,
  target_ownership_pct: 0.10,
  recycling_pct: 0.05,
  deployment_period_years: 4,
}
