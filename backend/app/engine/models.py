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


class ReturnScenario(BaseModel):
    exit_year: int
    exit_multiple: float
    exit_enterprise_value: float
    irr: float
    moic: float


class ReturnsAnalysis(BaseModel):
    entry_multiple: float
    scenarios: list[ReturnScenario]


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
    # Metadata
    convergence_warning: bool = False
    computation_notes: list[str] = Field(default_factory=list)
