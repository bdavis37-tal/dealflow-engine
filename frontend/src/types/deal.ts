import type { AnalysisEvidence } from './evidence'
/**
 * TypeScript interfaces mirroring the backend Pydantic models.
 * Keep in sync with backend/app/engine/models.py
 */

export type Industry =
  | 'Software / SaaS'
  | 'Healthcare Services'
  | 'Manufacturing'
  | 'Professional Services / Consulting'
  | 'HVAC / Mechanical Contracting'
  | 'Construction'
  | 'Restaurants / Food Service'
  | 'Retail'
  | 'Financial Services'
  | 'Oil & Gas Services'
  | 'Transportation / Logistics'
  | 'Real Estate Services'
  | 'Technology Hardware'
  | 'Pharmaceuticals'
  | 'Telecommunications'
  | 'Agriculture'
  | 'Media / Entertainment'
  | 'Insurance'
  | 'Staffing / Recruiting'
  | 'Waste Management'
  | 'Defense & National Security'

// Defense & National Security types
export type ClearanceLevel = 'unclassified' | 'secret' | 'top_secret' | 'ts_sci' | 'sap'
export type DeploymentClassification = 'cloud_il2' | 'cloud_il4' | 'cloud_il5' | 'cloud_il6' | 'on_prem_scif' | 'edge_tactical' | 'ddil'
export type DefenseSoftwareType =
  | 'C2 (Command & Control)'
  | 'ISR Processing'
  | 'Logistics / Supply Chain'
  | 'Predictive Maintenance'
  | 'Cybersecurity'
  | 'Decision Support'
  | 'Autonomous Systems'
  | 'Training / Simulation'
export type ContractVehicleType =
  | 'OTA (Other Transaction Authority)'
  | 'GWAC (Government-Wide Acquisition Contract)'
  | 'IDIQ (Indefinite Delivery/Indefinite Quantity)'
  | 'BPA (Blanket Purchase Agreement)'
  | 'SBIR/STTR'
  | 'Prime Contract'
  | 'Subcontract'

export interface DefenseProfile {
  is_ai_native: boolean
  contract_backlog_total: number
  contract_backlog_funded: number
  idiq_ceiling_value: number
  contract_vehicles: ContractVehicleType[]
  clearance_level: ClearanceLevel
  authorization_certifications: string[]
  customer_concentration_dod_pct: number
  programs_of_record: number
  deployment_classification: DeploymentClassification[]
  software_type: DefenseSoftwareType[]
  ip_ownership: string
}

export interface DefensePositioning {
  clearance_level: string
  active_contract_vehicles: number
  programs_of_record: number
  combined_backlog: number
  backlog_coverage_ratio: number
  revenue_visibility_years: number
  ev_revenue_multiple: number
  clearance_premium_applied: number
  certification_premium_applied: number
  program_of_record_premium_applied: number
  total_defense_premium_pct: number
  is_ai_native: boolean
  positioning_summary: string
}

export type AmortizationType = 'straight_line' | 'interest_only' | 'bullet'
export type RiskSeverity = 'low' | 'medium' | 'high' | 'critical'
export type HealthStatus = 'good' | 'fair' | 'poor' | 'critical'
export type DealVerdict = 'green' | 'yellow' | 'red'
export type ModelMode = 'quick' | 'deep'

// ---------------------------------------------------------------------------
// Inputs
// ---------------------------------------------------------------------------

export interface AcquirerProfile {
  company_name: string
  revenue: number
  ebitda: number
  net_income: number
  total_debt: number
  cash_on_hand: number
  shares_outstanding: number
  share_price: number
  tax_rate: number
  depreciation: number
  capex: number
  working_capital: number
  industry: Industry
}

export interface TargetProfile {
  company_name: string
  revenue: number
  ebitda: number
  net_income: number
  total_debt: number
  cash_on_hand: number
  tax_rate: number
  depreciation: number
  capex: number
  working_capital: number
  industry: Industry
  acquisition_price: number
  revenue_growth_rate: number
  defense_profile?: DefenseProfile
  is_ai_native: boolean
}

export interface DebtTranche {
  name: string
  amount: number
  interest_rate: number
  term_years: number
  amortization_type: AmortizationType
}

export interface DealStructure {
  cash_percentage: number
  stock_percentage: number
  debt_percentage: number
  debt_tranches: DebtTranche[]
  transaction_fees_pct: number
  advisory_fees: number
  /** Pre-tax yield foregone on cash used as consideration (decimal, default 0.043) */
  cash_yield?: number
}

export interface PurchasePriceAllocation {
  asset_writeup: number
  asset_writeup_useful_life: number
  identifiable_intangibles: number
  intangible_useful_life: number
}

export interface SynergyItem {
  category: string
  annual_amount: number
  phase_in_years: number
  cost_to_achieve: number
  is_revenue: boolean
}

export interface SynergyAssumptions {
  cost_synergies: SynergyItem[]
  revenue_synergies: SynergyItem[]
}

export interface DealInput {
  benchmark_version?: string
  acquirer: AcquirerProfile
  target: TargetProfile
  structure: DealStructure
  ppa: PurchasePriceAllocation
  synergies: SynergyAssumptions
  mode: ModelMode
  projection_years: number
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------

export interface IncomeStatementYear {
  year: number
  fiscal_year_label: string
  revenue: number
  cogs: number
  gross_profit: number
  sga: number
  ebitda: number
  da: number
  ebit: number
  interest_expense: number
  ebt: number
  taxes: number
  net_income: number
  acquirer_standalone_eps: number
  pro_forma_eps: number
  accretion_dilution_pct: number
  /** True when standalone EPS <= 0 — accretion % is Not Meaningful; use the EPS delta */
  accretion_is_nm: boolean
  // Pro forma adjustment detail
  acquirer_revenue: number
  target_revenue: number
  synergy_revenue: number
  acquirer_ebitda: number
  target_ebitda: number
  synergy_cost: number
  incremental_da: number
  acquisition_interest: number
  /** Implied pre-existing below-EBIT items (acquirer + target existing interest) */
  existing_interest: number
  /** Lost yield on cash used as consideration */
  foregone_cash_interest: number
  /** Synergy cost-to-achieve expensed this year */
  integration_costs: number
  transaction_costs: number
}

export interface BalanceSheetAtClose {
  goodwill: number
  identifiable_intangibles: number
  ppe_writeup: number
  new_acquisition_debt: number
  cash_used: number
  shares_issued: number
  target_equity_eliminated: number
  combined_total_assets: number
  combined_total_liabilities: number
  combined_equity: number
  /** Disclosed plug forcing Assets == Liabilities + Equity on the simplified opening BS */
  balancing_plug: number
}

export interface AccretionDilutionBridge {
  year: number
  target_earnings_contribution: number
  interest_expense_drag: number
  da_adjustment: number
  synergy_benefit: number
  share_dilution_impact: number
  /** Lost yield on cash consideration (after-tax, per share) */
  foregone_interest_drag: number
  tax_impact: number
  total_accretion_dilution: number
  total_accretion_dilution_pct: number
}

export interface SensitivityMatrix {
  title: string
  row_label: string
  col_label: string
  row_values: number[]
  col_values: number[]
  /** [row][col] accretion decimal; null = cell failed to compute (rendered "n/a") */
  data: (number | null)[][]
  data_labels: string[][]
  base_row_idx: number
  base_col_idx: number
  row_display_labels: string[]
  col_display_labels: string[]
  /** Assumption / data-quality note (e.g. hypothetical synergy axis, failed cells) */
  note: string | null
}

export interface ReturnScenario {
  exit_year: number
  exit_multiple: number
  exit_enterprise_value: number
  irr: number
  moic: number
}

export interface ReturnsAnalysis {
  entry_multiple: number
  equity_invested: number
  scenarios: ReturnScenario[]
  /** Deal-attributable FCF after all debt service */
  annual_fcf_to_equity: number[]
  /** e.g. near-zero equity check warning (IRR/MOIC not meaningful) */
  notes: string[]
}

export interface RiskItem {
  description: string
  severity: RiskSeverity
  metric_name: string
  current_value: number
  threshold_value: number
  tolerance_band: string
  plain_english: string
}

export interface ScorecardMetric {
  name: string
  value: number
  formatted_value: string
  benchmark_low: number
  benchmark_median: number
  benchmark_high: number
  health_status: HealthStatus
  description: string
}

export interface SourcesAndUsesItem {
  label: string
  amount: number
}

export interface SourcesAndUses {
  sources: SourcesAndUsesItem[]
  uses: SourcesAndUsesItem[]
  total_sources: number
  total_uses: number
  balanced: boolean
}

export interface ContributionRow {
  metric: string
  acquirer_value: number
  target_value: number
  acquirer_pct: number
  target_pct: number
}

export interface ContributionAnalysis {
  rows: ContributionRow[]
  implied_ownership_acquirer: number
  implied_ownership_target: number
}

export interface CreditMetrics {
  total_debt_to_ebitda: number
  net_debt_to_ebitda: number
  interest_coverage: number
  fixed_charge_coverage: number
  debt_to_total_cap: number
}

export interface ImpliedValuation {
  enterprise_value: number
  equity_value: number
  ev_revenue_ltm: number
  ev_ebitda_ltm: number
  ev_ebitda_ntm: number
  price_to_earnings: number
}

export interface DealOutput {
  decision_basis?: string
  valuation_comparison?: {metric: string; entry_multiple: number | null; reference: import('./evidence').BenchmarkRecord | null; fallback_reason: string | null; limitations: string[]}
  downside_scenarios?: {label: string; year1_eps: number; year1_accretion: number; verdict: string}[]
  evidence?: AnalysisEvidence | null
  pro_forma_income_statement: IncomeStatementYear[]
  balance_sheet_at_close: BalanceSheetAtClose
  accretion_dilution_bridge: AccretionDilutionBridge[]
  sensitivity_matrices: SensitivityMatrix[]
  returns_analysis: ReturnsAnalysis
  risk_assessment: RiskItem[]
  deal_verdict: DealVerdict
  deal_verdict_headline: string
  deal_verdict_subtext: string
  deal_scorecard: ScorecardMetric[]
  sources_and_uses?: SourcesAndUses
  contribution_analysis?: ContributionAnalysis
  credit_metrics?: CreditMetrics
  implied_valuation?: ImpliedValuation
  fiscal_year_start: number
  defense_positioning?: DefensePositioning
  ai_modifier_applied: boolean
  ai_benchmark_context: string | null
  convergence_warning: boolean
  computation_notes: string[]
}

// ---------------------------------------------------------------------------
// UI State
// ---------------------------------------------------------------------------

export type FlowStep = 1 | 2 | 3 | 4 | 5 | 6

export interface DealState {
  benchmark_version?: string
  step: FlowStep
  mode: ModelMode
  acquirer: Partial<AcquirerProfile>
  target: Partial<TargetProfile>
  structure: Partial<DealStructure>
  ppa: Partial<PurchasePriceAllocation>
  synergies: SynergyAssumptions
  output: DealOutput | null
  isLoading: boolean
  loadingMessage: string
  error: string | null
}
