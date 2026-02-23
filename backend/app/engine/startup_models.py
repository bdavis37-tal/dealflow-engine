"""
Pydantic models for startup valuation inputs and outputs.
All monetary values in USD millions. Percentages as decimals.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class StartupStage(str, Enum):
    PRE_SEED = "pre_seed"
    SEED = "seed"
    SERIES_A = "series_a"


class StartupVertical(str, Enum):
    AI_ML_INFRASTRUCTURE = "ai_ml_infrastructure"
    AI_ENABLED_SAAS = "ai_enabled_saas"
    B2B_SAAS = "b2b_saas"
    FINTECH = "fintech"
    HEALTHTECH = "healthtech"
    BIOTECH_PHARMA = "biotech_pharma"
    DEEP_TECH_HARDWARE = "deep_tech_hardware"
    CONSUMER = "consumer"
    CLIMATE_ENERGY = "climate_energy"
    MARKETPLACE = "marketplace"
    VERTICAL_SAAS = "vertical_saas"
    DEVELOPER_TOOLS = "developer_tools"
    DEFENSE_TECH = "defense_tech"


class InstrumentType(str, Enum):
    SAFE = "safe"
    CONVERTIBLE_NOTE = "convertible_note"
    PRICED_EQUITY = "priced_equity"


class Geography(str, Enum):
    BAY_AREA = "bay_area"
    NEW_YORK = "new_york"
    BOSTON = "boston"
    SEATTLE = "seattle"
    AUSTIN = "austin"
    LOS_ANGELES = "los_angeles"
    CHICAGO = "chicago"
    OTHER_US = "other_us"
    INTERNATIONAL = "international"


class ProductStage(str, Enum):
    IDEA = "idea"
    MVP = "mvp"
    BETA = "beta"
    PAYING_CUSTOMERS = "paying_customers"
    SCALING = "scaling"


class ValuationSignal(str, Enum):
    STRONG = "strong"
    FAIR = "fair"
    WEAK = "weak"
    WARNING = "warning"


# ---------------------------------------------------------------------------
# Input models
# ---------------------------------------------------------------------------

class TeamProfile(BaseModel):
    """Founder and leadership team signals."""
    founder_count: int = Field(default=2, ge=1, le=10)
    prior_exits: int = Field(default=0, ge=0, description="Number of prior successful exits by founders")
    domain_experts: bool = Field(default=False, description="Founders have direct domain expertise in the vertical")
    technical_cofounder: bool = Field(default=True, description="At least one technical co-founder")
    repeat_founder: bool = Field(default=False, description="At least one repeat founder")
    tier1_background: bool = Field(default=False, description="Google/Meta/McKinsey/top-4 bank background")
    notable_advisors: bool = Field(default=False, description="Operationally relevant advisors with credibility in the vertical")


class TractionMetrics(BaseModel):
    """Revenue and growth traction data."""
    has_revenue: bool = Field(default=False)
    monthly_recurring_revenue: float = Field(default=0.0, ge=0.0, description="Current MRR in USD millions")
    annual_recurring_revenue: float = Field(default=0.0, ge=0.0, description="Current ARR in USD millions")
    mom_growth_rate: float = Field(default=0.0, ge=0.0, description="MoM revenue growth rate as decimal (0.15 = 15%)")
    net_revenue_retention: float = Field(default=1.0, ge=0.0, le=3.0, description="NRR as decimal (1.20 = 120%)")
    gross_margin: float = Field(default=0.7, ge=0.0, le=1.0, description="Gross margin as decimal")
    monthly_burn_rate: float = Field(default=0.0, ge=0.0, description="Monthly cash burn in USD millions")
    cash_on_hand: float = Field(default=0.0, ge=0.0, description="Current cash in USD millions")
    paying_customer_count: int = Field(default=0, ge=0)
    logo_customer_count: int = Field(default=0, ge=0, description="Enterprise logos / reference customers")
    has_lois: bool = Field(default=False, description="Has signed Letters of Intent from prospective customers")
    gmv_monthly: float = Field(default=0.0, ge=0.0, description="Gross Merchandise Value per month (marketplaces), USD millions")


class ProductProfile(BaseModel):
    """Product maturity and IP signals."""
    stage: ProductStage = ProductStage.MVP
    has_patent_or_ip: bool = Field(default=False, description="Filed or granted patents / trade secrets")
    proprietary_data_moat: bool = Field(default=False, description="Unique data that competitors cannot easily replicate")
    open_source_traction: bool = Field(default=False, description="1K+ GitHub stars or significant OSS community")
    regulatory_clearance: bool = Field(default=False, description="FDA / regulatory approval or clear compliance path")


class MarketProfile(BaseModel):
    """Market size and competitive landscape."""
    tam_usd_billions: float = Field(gt=0.0, description="Total Addressable Market in USD billions")
    sam_usd_millions: float = Field(gt=0.0, description="Serviceable Addressable Market in USD millions")
    market_growth_rate: float = Field(default=0.15, ge=0.0, description="Annual market growth rate as decimal")
    competitive_moat: str = Field(default="medium", description="low | medium | high")


class FundraisingProfile(BaseModel):
    """Current round details."""
    stage: StartupStage
    vertical: StartupVertical
    geography: Geography = Geography.OTHER_US
    raise_amount: float = Field(gt=0.0, description="Target raise amount in USD millions")
    instrument: InstrumentType = InstrumentType.SAFE
    pre_money_valuation_ask: Optional[float] = Field(default=None, ge=0.0, description="Founder's pre-money ask in USD millions; null = use engine output")
    safe_discount: float = Field(default=0.0, ge=0.0, le=0.5, description="SAFE discount rate if applicable (0.20 = 20%)")
    has_mfn_clause: bool = Field(default=False)
    existing_safe_stack: float = Field(default=0.0, ge=0.0, description="Total outstanding SAFEs not yet converted, USD millions")
    is_ai_native: bool = Field(default=False, description="AI-native toggle — enables graduated premium layer")
    ai_native_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Score from 4-question AI assessment [0.0–1.0]")


class StartupInput(BaseModel):
    """Complete startup valuation input — the single input to the engine."""
    company_name: str
    team: TeamProfile = Field(default_factory=TeamProfile)
    traction: TractionMetrics = Field(default_factory=TractionMetrics)
    product: ProductProfile = Field(default_factory=ProductProfile)
    market: MarketProfile
    fundraise: FundraisingProfile

    # Berkus / Scorecard custom overrides (optional)
    berkus_scores: Optional[dict[str, float]] = Field(
        default=None,
        description="Optional override for Berkus 5 dimensions. Keys: idea, management, prototype, relationships, rollout. Values 0.0–1.0."
    )
    scorecard_scores: Optional[dict[str, float]] = Field(
        default=None,
        description="Optional override for Scorecard 7 factors. Values 0.5–1.5 (1.0 = average)."
    )
    risk_factor_scores: Optional[dict[str, int]] = Field(
        default=None,
        description="Optional override for Risk Factor Summation. Values -2 to +2 per category."
    )


# ---------------------------------------------------------------------------
# Output models
# ---------------------------------------------------------------------------

class ValuationMethodResult(BaseModel):
    """Output from a single valuation method."""
    method_name: str
    method_label: str
    indicated_value: Optional[float]  # pre-money in USD millions; None if method not applicable
    value_low: Optional[float]
    value_high: Optional[float]
    applicable: bool
    rationale: str
    inputs_used: dict


class DilutionScenario(BaseModel):
    """Ownership and dilution across one round."""
    round_label: str
    pre_money: float
    raise_amount: float
    post_money: float
    investor_ownership_pct: float
    founder_ownership_pct_before: float
    founder_ownership_pct_after: float
    dilution_this_round: float


class SAFEConversionSummary(BaseModel):
    """How a SAFE converts at the next priced round."""
    safe_amount: float
    valuation_cap: float
    discount_rate: float
    conversion_price_at_cap: float  # cap / shares at next round
    implied_ownership_pct: float
    note: str


class ScorecardFlag(BaseModel):
    """A single scorecard signal — investor-grade metric check."""
    metric: str
    value: str
    signal: ValuationSignal
    benchmark: str
    commentary: str


class ValuationVerdict(str, Enum):
    STRONG = "strong"        # Top quartile for stage; founder has pricing power
    FAIR = "fair"            # Median range; standard market terms
    STRETCHED = "stretched"  # Above median; growth must accelerate to sustain
    AT_RISK = "at_risk"      # Below median; re-examine fundamentals before raising


class StartupValuationOutput(BaseModel):
    """Complete startup valuation engine output."""
    company_name: str
    stage: StartupStage
    vertical: StartupVertical

    # Core outputs
    blended_valuation: float              # Weighted average of applicable methods, USD millions
    valuation_range_low: float           # P25 of applicable methods
    valuation_range_high: float          # P75 of applicable methods
    recommended_safe_cap: Optional[float]  # Suggested cap if raising on SAFE
    implied_dilution: float              # Raise amount / post-money

    # Method breakdown
    method_results: list[ValuationMethodResult]

    # Benchmarks
    benchmark_p25: float
    benchmark_p50: float
    benchmark_p75: float
    benchmark_p95: float
    percentile_in_market: str            # e.g. "top quartile", "median range"

    # Dilution modeling
    dilution_scenarios: list[DilutionScenario]   # Pre-seed → Seed → Series A projection
    safe_conversion: Optional[SAFEConversionSummary]

    # Scorecard flags
    investor_scorecard: list[ScorecardFlag]
    traction_bar: str                    # What this vertical requires to command median valuation

    # Verdict
    verdict: ValuationVerdict
    verdict_headline: str
    verdict_subtext: str

    # Risk warnings
    warnings: list[str]
    computation_notes: list[str]

    # Raw benchmark data (pass-through for UI)
    vertical_benchmarks: dict

    # AI modifier outputs (all None/False when modifier not applied)
    ai_modifier_applied: bool = Field(default=False)
    ai_premium_multiplier: Optional[float] = Field(default=None, description="Effective premium factor applied")
    ai_premium_context: Optional[str] = Field(default=None, description="Human-readable premium explanation")
    blended_before_ai: Optional[float] = Field(default=None, description="Pre-modifier blended value, USD millions")
    ai_native_score: Optional[float] = Field(default=None, description="Score from 4-question assessment [0.0–1.0]")
