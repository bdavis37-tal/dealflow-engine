"""
Pydantic data models for all deal inputs and outputs.
These models are the single source of truth for data shapes across the engine.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class Industry(str, Enum):
    SOFTWARE_SAAS = "Software / SaaS"
    HEALTHCARE_SERVICES = "Healthcare Services"
    MANUFACTURING = "Manufacturing"
    PROFESSIONAL_SERVICES = "Professional Services / Consulting"
    HVAC = "HVAC / Mechanical Contracting"
    CONSTRUCTION = "Construction"
    RESTAURANTS = "Restaurants / Food Service"
    RETAIL = "Retail"
    FINANCIAL_SERVICES = "Financial Services"
    OIL_GAS = "Oil & Gas Services"
    TRANSPORTATION = "Transportation / Logistics"
    REAL_ESTATE = "Real Estate Services"
    TECH_HARDWARE = "Technology Hardware"
    PHARMACEUTICALS = "Pharmaceuticals"
    TELECOM = "Telecommunications"
    AGRICULTURE = "Agriculture"
    MEDIA = "Media / Entertainment"
    INSURANCE = "Insurance"
    STAFFING = "Staffing / Recruiting"
    WASTE_MANAGEMENT = "Waste Management"
    DEFENSE = "Defense & National Security"


class AmortizationType(str, Enum):
    STRAIGHT_LINE = "straight_line"
    INTEREST_ONLY = "interest_only"
    BULLET = "bullet"


class RiskSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class HealthStatus(str, Enum):
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    CRITICAL = "critical"


class DealVerdict(str, Enum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"


class ModelMode(str, Enum):
    QUICK = "quick"
    DEEP = "deep"


# ---------------------------------------------------------------------------
# Defense & National Security enums
# ---------------------------------------------------------------------------

class ClearanceLevel(str, Enum):
    UNCLASSIFIED = "unclassified"
    SECRET = "secret"
    TOP_SECRET = "top_secret"
    TS_SCI = "ts_sci"
    SAP = "sap"


class DeploymentClassification(str, Enum):
    CLOUD_IL2 = "cloud_il2"
    CLOUD_IL4 = "cloud_il4"
    CLOUD_IL5 = "cloud_il5"
    CLOUD_IL6 = "cloud_il6"
    ON_PREM_SCIF = "on_prem_scif"
    EDGE_TACTICAL = "edge_tactical"
    DDIL = "ddil"


class DefenseSoftwareType(str, Enum):
    C2 = "C2 (Command & Control)"
    ISR = "ISR Processing"
    LOGISTICS = "Logistics / Supply Chain"
    PREDICTIVE_MAINTENANCE = "Predictive Maintenance"
    CYBERSECURITY = "Cybersecurity"
    DECISION_SUPPORT = "Decision Support"
    AUTONOMOUS_SYSTEMS = "Autonomous Systems"
    TRAINING_SIMULATION = "Training / Simulation"


class ContractVehicleType(str, Enum):
    OTA = "OTA (Other Transaction Authority)"
    GWAC = "GWAC (Government-Wide Acquisition Contract)"
    IDIQ = "IDIQ (Indefinite Delivery/Indefinite Quantity)"
    BPA = "BPA (Blanket Purchase Agreement)"
    SBIR_STTR = "SBIR/STTR"
    PRIME = "Prime Contract"
    SUBCONTRACT = "Subcontract"


# ---------------------------------------------------------------------------
# Defense-specific input sub-models
# ---------------------------------------------------------------------------

class DefenseProfile(BaseModel):
    """Defense & National Security specific attributes for a target company."""
    is_ai_native: bool = Field(default=False, description="AI-native defense company vs traditional defense contractor")
    contract_backlog_total: float = Field(default=0.0, ge=0, description="Total value of awarded contracts not yet recognized as revenue")
    contract_backlog_funded: float = Field(default=0.0, ge=0, description="Funded/obligated portion of backlog (near-certain revenue)")
    idiq_ceiling_value: float = Field(default=0.0, ge=0, description="Total ceiling value of IDIQ contracts")
    contract_vehicles: list[ContractVehicleType] = Field(default_factory=list)
    clearance_level: ClearanceLevel = Field(default=ClearanceLevel.UNCLASSIFIED)
    authorization_certifications: list[str] = Field(default_factory=list, description="FedRAMP High, IL5, CMMC Level 3, etc.")
    customer_concentration_dod_pct: float = Field(default=0.0, ge=0, le=1, description="% of revenue from DoD")
    programs_of_record: int = Field(default=0, ge=0, description="Number of DoD programs of record the software is embedded in")
    deployment_classification: list[DeploymentClassification] = Field(default_factory=list)
    software_type: list[DefenseSoftwareType] = Field(default_factory=list)
    ip_ownership: str = Field(default="company_owned", description="company_owned, government_purpose_rights, or unlimited_rights")


# ---------------------------------------------------------------------------
# Defense-specific output sub-models
# ---------------------------------------------------------------------------

class DefensePositioning(BaseModel):
    """Strategic defense positioning summary in deal output."""
    clearance_level: str
    active_contract_vehicles: int
    programs_of_record: int
    combined_backlog: float
    backlog_coverage_ratio: float  # backlog / annual revenue
    revenue_visibility_years: float  # funded backlog / annual revenue
    ev_revenue_multiple: float
    clearance_premium_applied: float  # percentage premium
    certification_premium_applied: float
    program_of_record_premium_applied: float
    total_defense_premium_pct: float
    is_ai_native: bool
    positioning_summary: str


# ---------------------------------------------------------------------------
# Input sub-models
# ---------------------------------------------------------------------------

class AcquirerProfile(BaseModel):
    """Financial profile of the acquiring company."""
    company_name: str
    revenue: float = Field(gt=0, description="Annual revenue in dollars")
    ebitda: float = Field(description="Annual EBITDA in dollars")
    net_income: float = Field(description="Annual net income in dollars")
    total_debt: float = Field(ge=0, description="Total outstanding debt")
    cash_on_hand: float = Field(ge=0, description="Cash and cash equivalents")
    shares_outstanding: float = Field(gt=0, description="Diluted shares outstanding")
    share_price: float = Field(gt=0, description="Current share price")
    tax_rate: float = Field(default=0.25, ge=0, le=1, description="Effective tax rate")
    depreciation: float = Field(ge=0, description="Annual D&A expense")
    capex: float = Field(ge=0, description="Annual capital expenditures")
    working_capital: float = Field(description="Net working capital")
    industry: Industry

    @property
    def market_cap(self) -> float:
        return self.shares_outstanding * self.share_price

    @property
    def eps(self) -> float:
        return self.net_income / self.shares_outstanding if self.shares_outstanding else 0


class TargetProfile(BaseModel):
    """Financial profile of the target company."""
    company_name: str
    revenue: float = Field(gt=0, description="Annual revenue in dollars")
    ebitda: float = Field(description="Annual EBITDA in dollars")
    net_income: float = Field(description="Annual net income in dollars")
    total_debt: float = Field(ge=0, description="Total outstanding debt (assumed/refinanced)")
    cash_on_hand: float = Field(ge=0, description="Cash acquired in transaction")
    tax_rate: float = Field(default=0.25, ge=0, le=1)
    depreciation: float = Field(ge=0)
    capex: float = Field(ge=0)
    working_capital: float
    industry: Industry
    acquisition_price: float = Field(gt=0, description="Total enterprise value paid")
    revenue_growth_rate: float = Field(default=0.05, description="Projected annual revenue growth (5-year horizon)")
    defense_profile: Optional[DefenseProfile] = Field(default=None, description="Defense-specific attributes (only when industry is Defense & National Security)")
    is_ai_native: bool = Field(default=False, description="AI-native toggle for M&A target — switches to AI-native benchmark ranges")


class DebtTranche(BaseModel):
    """A single tranche of acquisition financing debt."""
    name: str = Field(description="e.g. 'Term Loan A', 'Revolver', 'Mezzanine'")
    amount: float = Field(gt=0)
    interest_rate: float = Field(gt=0, le=1, description="Annual interest rate as decimal")
    term_years: int = Field(gt=0, le=30)
    amortization_type: AmortizationType = AmortizationType.STRAIGHT_LINE


class DealStructure(BaseModel):
    """How the acquisition is financed."""
    cash_percentage: float = Field(ge=0, le=1)
    stock_percentage: float = Field(ge=0, le=1)
    debt_percentage: float = Field(ge=0, le=1)
    debt_tranches: list[DebtTranche] = Field(default_factory=list)
    transaction_fees_pct: float = Field(default=0.02, ge=0, le=0.1)
    advisory_fees: float = Field(default=0.0, ge=0)

    @model_validator(mode="after")
    def validate_percentages(self) -> "DealStructure":
        total = self.cash_percentage + self.stock_percentage + self.debt_percentage
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"cash + stock + debt must equal 100% (got {total:.1%})")
        return self


class PurchasePriceAllocation(BaseModel):
    """Step-up of acquired assets to fair value per ASC 805."""
    asset_writeup: float = Field(default=0.0, ge=0, description="PP&E fair value step-up")
    asset_writeup_useful_life: int = Field(default=15, gt=0)
    identifiable_intangibles: float = Field(default=0.0, ge=0, description="Customer lists, IP, trade names, etc.")
    intangible_useful_life: int = Field(default=10, gt=0)
    # Goodwill is always calculated: Purchase Price - FVNA


class SynergyItem(BaseModel):
    """A single synergy line item."""
    category: str
    annual_amount: float = Field(gt=0, description="Full-run-rate annual synergy value")
    phase_in_years: int = Field(default=3, ge=1, le=7, description="Years to reach full run-rate")
    cost_to_achieve: float = Field(default=0.0, ge=0, description="One-time cost to realize this synergy")
    is_revenue: bool = Field(default=False, description="True = revenue synergy, False = cost synergy")


class SynergyAssumptions(BaseModel):
    cost_synergies: list[SynergyItem] = Field(default_factory=list)
    revenue_synergies: list[SynergyItem] = Field(default_factory=list)


class DealInput(BaseModel):
    """Complete deal model input — passed to the financial engine."""
    acquirer: AcquirerProfile
    target: TargetProfile
    structure: DealStructure
    ppa: PurchasePriceAllocation = Field(default_factory=PurchasePriceAllocation)
    synergies: SynergyAssumptions = Field(default_factory=SynergyAssumptions)
    mode: ModelMode = ModelMode.QUICK
    projection_years: int = Field(default=5, ge=3, le=10)


# ---------------------------------------------------------------------------
# Output sub-models
# ---------------------------------------------------------------------------

class IncomeStatementYear(BaseModel):
    year: int
    fiscal_year_label: str = ""  # e.g. "FY2026E"
    revenue: float
    cogs: float
    gross_profit: float
    sga: float
    ebitda: float
    da: float
    ebit: float
    interest_expense: float
    ebt: float
    taxes: float
    net_income: float
    # EPS
    acquirer_standalone_eps: float
    pro_forma_eps: float
    accretion_dilution_pct: float
    # Pro forma adjustment detail (Deep mode transparency)
    acquirer_revenue: float = 0.0
    target_revenue: float = 0.0
    synergy_revenue: float = 0.0
    acquirer_ebitda: float = 0.0
    target_ebitda: float = 0.0
    synergy_cost: float = 0.0
    incremental_da: float = 0.0    # PPA-related D&A only
    acquisition_interest: float = 0.0  # Interest from new deal debt
    transaction_costs: float = 0.0  # One-time fees (Year 1 only)


class BalanceSheetAtClose(BaseModel):
    """Simplified pro forma balance sheet at transaction close."""
    goodwill: float
    identifiable_intangibles: float
    ppe_writeup: float
    new_acquisition_debt: float
    cash_used: float
    shares_issued: float
    target_equity_eliminated: float
    combined_total_assets: float
    combined_total_liabilities: float
    combined_equity: float


class AccretionDilutionBridge(BaseModel):
    year: int
    target_earnings_contribution: float
    interest_expense_drag: float
    da_adjustment: float           # Incremental D&A from PPA
    synergy_benefit: float
    share_dilution_impact: float   # Change in EPS from new shares issued
    tax_impact: float
    total_accretion_dilution: float
    total_accretion_dilution_pct: float


class SensitivityMatrix(BaseModel):
    title: str
    row_label: str
    col_label: str
    row_values: list[float]
    col_values: list[float]
    data: list[list[float]]         # [row][col] = accretion/dilution %
    data_labels: list[list[str]]    # formatted strings
    # Base case indices for highlighting
    base_row_idx: int = -1          # Row index of base case (-1 = none)
    base_col_idx: int = -1          # Col index of base case (-1 = none)
    # Display labels with absolute values (e.g. "$50M (Base)")
    row_display_labels: list[str] = Field(default_factory=list)
    col_display_labels: list[str] = Field(default_factory=list)


class ReturnScenario(BaseModel):
    exit_year: int
    exit_multiple: float
    exit_enterprise_value: float
    irr: float
    moic: float


class ReturnsAnalysis(BaseModel):
    entry_multiple: float
    equity_invested: float = 0.0           # Cash equity check at close
    scenarios: list[ReturnScenario]
    annual_fcf_to_equity: list[float] = Field(default_factory=list)  # Annual FCF after debt service


class RiskItem(BaseModel):
    description: str
    severity: RiskSeverity
    metric_name: str
    current_value: float
    threshold_value: float
    tolerance_band: str
    plain_english: str


class ScorecardMetric(BaseModel):
    name: str
    value: float
    formatted_value: str
    benchmark_low: float
    benchmark_median: float
    benchmark_high: float
    health_status: HealthStatus
    description: str


class SourcesAndUsesItem(BaseModel):
    """Single line in sources & uses table."""
    label: str
    amount: float

class SourcesAndUses(BaseModel):
    """Sources & Uses of Funds — foundation of every deal presentation."""
    sources: list[SourcesAndUsesItem]
    uses: list[SourcesAndUsesItem]
    total_sources: float
    total_uses: float
    balanced: bool  # True if sources == uses (within tolerance)

class ContributionRow(BaseModel):
    """Single metric row in contribution analysis."""
    metric: str
    acquirer_value: float
    target_value: float
    acquirer_pct: float  # decimal, e.g. 0.75 = 75%
    target_pct: float

class ContributionAnalysis(BaseModel):
    """What each company contributes to the combined entity."""
    rows: list[ContributionRow]
    implied_ownership_acquirer: float  # From deal structure (stock consideration)
    implied_ownership_target: float

class CreditMetrics(BaseModel):
    """Post-close credit profile — standard covenant metrics."""
    total_debt_to_ebitda: float       # Total Debt / EBITDA
    net_debt_to_ebitda: float         # (Total Debt - Cash) / EBITDA
    interest_coverage: float          # EBITDA / Interest Expense
    fixed_charge_coverage: float      # (EBITDA - CapEx) / (Interest + Mandatory Amort)
    debt_to_total_cap: float          # Debt / (Debt + Equity)

class ImpliedValuation(BaseModel):
    """Implied valuation multiples from the transaction price."""
    enterprise_value: float           # Purchase price + assumed debt - cash acquired
    equity_value: float               # Purchase price (equity component)
    ev_revenue_ltm: float             # EV / LTM Revenue
    ev_ebitda_ltm: float              # EV / LTM EBITDA
    ev_ebitda_ntm: float              # EV / NTM EBITDA (Year 1 projected)
    price_to_earnings: float          # Price / LTM Net Income

class DealOutput(BaseModel):
    """Complete deal analysis output from the financial engine."""
    pro_forma_income_statement: list[IncomeStatementYear]
    balance_sheet_at_close: BalanceSheetAtClose
    accretion_dilution_bridge: list[AccretionDilutionBridge]
    sensitivity_matrices: list[SensitivityMatrix]
    returns_analysis: ReturnsAnalysis
    risk_assessment: list[RiskItem]
    deal_verdict: DealVerdict
    deal_verdict_headline: str
    deal_verdict_subtext: str
    deal_scorecard: list[ScorecardMetric]
    # New professional analytics
    sources_and_uses: Optional[SourcesAndUses] = None
    contribution_analysis: Optional[ContributionAnalysis] = None
    credit_metrics: Optional[CreditMetrics] = None
    implied_valuation: Optional[ImpliedValuation] = None
    fiscal_year_start: int = 2026  # Base fiscal year for projections
    # Defense-specific output (populated only for Defense & National Security deals)
    defense_positioning: Optional[DefensePositioning] = None
    # AI modifier outputs
    ai_modifier_applied: bool = Field(default=False)
    ai_benchmark_context: Optional[str] = Field(default=None, description="AI-native benchmark context string for purchase price risk section")
    # Metadata
    convergence_warning: bool = False
    computation_notes: list[str] = Field(default_factory=list)
