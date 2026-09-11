"""
Pydantic models for startup valuation inputs and outputs.
All monetary values in USD millions. Percentages as decimals.
"""
from __future__ import annotations
from .benchmark_registry import AnalysisEvidence, VersionedInput

import logging
from enum import Enum
from typing import Literal, Optional
from pydantic import model_validator, BaseModel, Field, field_validator

logger = logging.getLogger(__name__)


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


class RaiseSignal(str, Enum):
    RAISE_NOW = "raise_now"
    RAISE_IN_MONTHS = "raise_in_months"
    FOCUS_MILESTONES = "focus_milestones"


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
    competitive_moat: Literal["low", "medium", "high"] = Field(default="medium", description="low | medium | high")

    @field_validator("competitive_moat", mode="before")
    @classmethod
    def _coerce_competitive_moat(cls, v: object) -> str:
        """Coerce/normalize moat values instead of raising (engines never raise)."""
        if isinstance(v, str):
            normalized = v.strip().lower()
            if normalized in ("low", "medium", "high"):
                return normalized
        logger.warning("Unknown competitive_moat value %r — defaulting to 'medium'", v)
        return "medium"


class FundraisingProfile(BaseModel):
    safe_valuation_cap: Optional[float] = Field(default=None, gt=0, description="Explicit SAFE cap; never a pre-money ask")
    business_model: Literal["auto", "recurring_software", "hardware", "services", "biotech", "mixed"] = "auto"
    """Current round details."""
    stage: StartupStage
    vertical: StartupVertical
    geography: Geography = Geography.OTHER_US
    raise_amount: float = Field(gt=0.0, description="Target raise amount in USD millions")
    instrument: InstrumentType = InstrumentType.SAFE
    pre_money_valuation_ask: Optional[float] = Field(default=None, ge=0.0, description="Founder's pre-money ask in USD millions; null = use engine output")
    safe_type: Literal["post_money", "pre_money"] = Field(
        default="post_money",
        description="SAFE mechanics. post_money (YC 2018+ standard, ~87% of market): ownership = raise/cap. pre_money (legacy): ownership = raise/(cap+raise).",
    )
    safe_discount: float = Field(default=0.0, ge=0.0, le=0.5, description="SAFE discount rate if applicable (0.20 = 20%)")
    has_mfn_clause: bool = Field(default=False)
    existing_safe_stack: float = Field(default=0.0, ge=0.0, description="Total outstanding SAFEs not yet converted, USD millions")
    is_ai_native: bool = Field(default=False, description="AI-native toggle — enables graduated premium layer")
    ai_native_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Score from 4-question AI assessment [0.0–1.0]")

    @model_validator(mode='after')
    def validate_safe_cap(self):
        if self.safe_type == 'post_money' and self.safe_valuation_cap is not None and self.safe_valuation_cap <= self.raise_amount:
            raise ValueError('Post-money SAFE cap must exceed the raise amount')
        return self


class StartupInput(VersionedInput):
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
    blend_weight: float = 0.0
    weighted_contribution: float = 0.0
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
    safe_type: str = "post_money"  # 'post_money' | 'pre_money'
    # Per-share conversion price requires a share count, which the engine does
    # not model — None unless shares outstanding are known.
    conversion_price_at_cap: Optional[float] = None
    implied_ownership_pct: float  # ownership implied by the cap alone
    next_round_pre_money: Optional[float] = None   # projected next priced round pre-money
    conversion_valuation: Optional[float] = None   # min(cap, next_round_pre × (1 − discount))
    conversion_ownership_pct: Optional[float] = None  # ownership at projected conversion
    governing_term: Optional[str] = None  # 'cap' | 'discount' — which term set the conversion price
    note: str


class RoundTimingSignal(BaseModel):
    """Round timing recommendation based on runway and stage milestones."""
    runway_months: float = Field(description="Months of runway remaining (cash / monthly burn). 0 if burn rate is zero.")
    months_to_next_round: float = Field(description="Typical months from current stage to next raise, per vertical benchmarks.")
    fundraise_process_months: float = Field(default=6.0, description="Assumed fundraise process duration in months.")
    months_until_raise_window: float = Field(description="months_to_next_round - fundraise_process_months. Negative = already in window.")
    signal: RaiseSignal
    signal_label: str = Field(description="Short human-readable label, e.g. 'Raise Now'.")
    signal_detail: str = Field(description="1–2 sentence explanation of the signal.")
    milestone_gaps: list[str] = Field(default_factory=list, description="List of unmet milestone strings for the current stage/vertical.")
    milestone_met_count: int = Field(default=0)
    milestone_total_count: int = Field(default=0)
    raise_in_months: Optional[float] = Field(default=None, description="Populated when signal=raise_in_months; months until raise window opens.")
    warnings: list[str] = Field(default_factory=list)


class ScorecardFlag(BaseModel):
    """A single scorecard signal — investor-grade metric check."""
    metric: str
    value: str
    signal: ValuationSignal
    benchmark: str
    commentary: str


class ValuationVerdict(str, Enum):
    """
    Verdict for the blended valuation relative to the vertical/stage benchmark
    distribution and the founder's ask. Exact mapping (see
    startup_engine._assign_verdict):
      STRETCHED: blended >= P75 — above-market; strong story required to sustain
      STRONG:    P50 <= blended < P75 — top half; founder has pricing power
      FAIR:      P25 <= blended < P50 — below median but market-rate terms
      AT_RISK:   blended < P25 — below-market; hit milestones before raising
    """
    STRONG = "strong"        # P50–P75: top half; founder has pricing power
    FAIR = "fair"            # P25–P50: below median; standard market terms
    STRETCHED = "stretched"  # >= P75: top quartile; growth must accelerate to sustain
    NOT_ASSESSED = "not_assessed"
    AT_RISK = "at_risk"      # < P25: below market; re-examine fundamentals before raising


class StartupValuationOutput(BaseModel):
    evidence: AnalysisEvidence | None = None
    """Complete startup valuation engine output."""
    company_name: str
    stage: StartupStage
    vertical: StartupVertical

    range_basis: str = "Method dispersion; not a statistical confidence interval"
    blend_adjustment: float = 0.0
    price_assessment: dict = Field(default_factory=dict)
    company_evidence: list[str] = Field(default_factory=list)
    # Core outputs
    blended_valuation: float              # Weighted average of applicable methods, USD millions
    valuation_range_low: float           # P25 of applicable methods
    valuation_range_high: float          # P75 of applicable methods
    recommended_safe_cap: Optional[float]  # Suggested cap if raising on SAFE
    implied_dilution: float              # Raise amount / post-money at the deal-mechanics basis

    # Deal-mechanics basis: the actual deal (dilution, SAFE conversion, projected
    # rounds) prices off the preparer's ask when one is provided — the model
    # midpoint is only the fallback. The blend/range above never depends on the ask.
    dilution_basis: str = Field(default="model_midpoint", description="'preparer_ask' | 'model_midpoint'")
    dilution_basis_pre_money: float = Field(default=0.0, description="Pre-money the deal mechanics are priced at, USD millions")

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

    # AI calibration outputs (all None/False when calibration not applied).
    # The premium is EMERGENT: it arises from parameter-level calibration of
    # the individual methods (scorecard weights, Berkus caps, RFS steps, ARR
    # multiple uplift) applied BEFORE blending — never a post-blend scalar.
    ai_modifier_applied: bool = Field(default=False)
    ai_premium_multiplier: Optional[float] = Field(default=None, description="Emergent premium: blended / standard-parameter blend − 1")
    ai_premium_context: Optional[str] = Field(default=None, description="Human-readable calibration explanation")
    blended_before_ai: Optional[float] = Field(default=None, description="Counterfactual blend under standard (non-AI) parameters, USD millions")
    ai_native_score: Optional[float] = Field(default=None, description="Score from 4-question assessment [0.0–1.0]")

    # Round timing signal
    round_timing: RoundTimingSignal
