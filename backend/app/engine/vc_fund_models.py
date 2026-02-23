"""
Pydantic models for VC fund-seat analysis.
All monetary values in USD millions. Percentages as decimals. IRR as decimal.

These models answer the question every VC asks before writing a check:
  "At this valuation, given my fund size and target ownership,
   what does this company need to exit at for me to care — and what's
   the probability it gets there?"
"""
from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class VCStage(str, Enum):
    PRE_SEED = "pre_seed"
    SEED = "seed"
    SERIES_A = "series_a"
    SERIES_B = "series_b"
    SERIES_C = "series_c"
    GROWTH = "growth"


class VCVertical(str, Enum):
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


class ExitType(str, Enum):
    MA_ACQUISITION = "ma_acquisition"
    IPO = "ipo"
    SECONDARY = "secondary"
    WRITE_OFF = "write_off"


class PreferenceType(str, Enum):
    NON_PARTICIPATING = "non_participating"    # 1x, convert or liquidate
    PARTICIPATING = "participating"             # 1x + pro-rata on remainder
    PARTICIPATING_CAPPED = "participating_capped"  # 1x + pro-rata up to cap


class AntiDilutionType(str, Enum):
    NONE = "none"
    BROAD_BASED_WEIGHTED_AVERAGE = "broad_based_wa"
    FULL_RATCHET = "full_ratchet"


class LPReportMetric(str, Enum):
    TVPI = "tvpi"
    DPI = "dpi"
    RVPI = "rvpi"


# ---------------------------------------------------------------------------
# Fund Profile (persisted, one per fund)
# ---------------------------------------------------------------------------

class FundProfile(BaseModel):
    """
    The investor's fund context. This is the lens through which every deal is evaluated.
    Enter once; all deal evaluations use it automatically.
    """
    fund_name: str = Field(default="My Fund")
    fund_size: float = Field(gt=0, description="Total LP commitments, USD millions")
    vintage_year: int = Field(default=2024, ge=2010, le=2035)
    management_fee_pct: float = Field(default=0.02, ge=0, le=0.04,
                                       description="Annual management fee as decimal (0.02 = 2%)")
    management_fee_years: int = Field(default=5, ge=1, le=10,
                                       description="Years management fees are charged on committed capital")
    carry_pct: float = Field(default=0.20, ge=0.10, le=0.35,
                              description="Carried interest percentage (0.20 = 20%)")
    hurdle_rate: float = Field(default=0.08, ge=0, le=0.20,
                                description="Preferred return / hurdle rate (0.08 = 8%)")
    reserve_ratio: float = Field(default=0.40, ge=0, le=0.70,
                                  description="Fraction of investable capital held for follow-on (0.40 = 40%)")
    target_initial_check_count: int = Field(default=25, ge=5, le=100,
                                             description="Target portfolio company count from initial checks")
    target_ownership_pct: float = Field(default=0.10, ge=0.01, le=0.50,
                                         description="Target initial ownership stake (0.10 = 10%)")
    recycling_pct: float = Field(default=0.05, ge=0, le=0.20,
                                  description="Return proceeds recycled back into new investments (0.05 = 5%)")
    deployment_period_years: int = Field(default=4, ge=1, le=7)

    @property
    def total_management_fees(self) -> float:
        """Total management fees paid over fee period."""
        return self.fund_size * self.management_fee_pct * self.management_fee_years

    @property
    def investable_capital(self) -> float:
        """Capital actually deployed after management fees and recycling credit."""
        recycling_credit = self.fund_size * self.recycling_pct
        return self.fund_size - self.total_management_fees + recycling_credit

    @property
    def initial_check_pool(self) -> float:
        """Capital available for initial investments (non-reserve)."""
        return self.investable_capital * (1 - self.reserve_ratio)

    @property
    def reserve_pool(self) -> float:
        """Capital reserved for follow-on investments."""
        return self.investable_capital * self.reserve_ratio

    @property
    def target_initial_check_size(self) -> float:
        """Implied initial check size given portfolio count target."""
        if self.target_initial_check_count <= 0:
            return 0.0
        return self.initial_check_pool / self.target_initial_check_count


# ---------------------------------------------------------------------------
# Liquidation Stack
# ---------------------------------------------------------------------------

class LiquidationPreference(BaseModel):
    """Terms for a single share class in the cap table."""
    share_class: str = Field(description="e.g. 'Series A Preferred', 'Series B Preferred'")
    invested_amount: float = Field(gt=0, description="Total invested by this class, USD millions")
    preference_multiple: float = Field(default=1.0, ge=0.5, le=3.0,
                                        description="Liquidation preference multiple (1.0 = 1x)")
    preference_type: PreferenceType = PreferenceType.NON_PARTICIPATING
    participation_cap: Optional[float] = Field(default=None, ge=0,
                                               description="For capped participating: cap as multiple of invested")
    anti_dilution: AntiDilutionType = AntiDilutionType.NONE
    seniority: int = Field(default=1, ge=1, description="1 = most senior (highest seniority number = junior)")


# ---------------------------------------------------------------------------
# Deal Evaluation Input (per-deal)
# ---------------------------------------------------------------------------

class DilutionAssumptions(BaseModel):
    """Expected dilution per future funding round.

    Each field represents the dilution an existing shareholder faces when that
    round closes.  E.g. ``pre_seed_to_seed`` is the dilution the pre-seed
    investor takes at the seed round, ``seed_to_a`` is dilution at Series A, etc.
    """
    pre_seed_to_seed: float = Field(default=0.205, ge=0, le=0.50,
                                     description="Dilution at Seed round (Carta median: 20.5%)")
    seed_to_a: float = Field(default=0.20, ge=0, le=0.50,
                              description="Dilution at Series A (Carta median: 20%)")
    a_to_b: float = Field(default=0.18, ge=0, le=0.50,
                           description="Dilution at Series B (typical 18-22%)")
    b_to_c: float = Field(default=0.15, ge=0, le=0.50,
                           description="Dilution at Series C (Carta median: 15%)")
    c_to_ipo: float = Field(default=0.12, ge=0, le=0.40,
                             description="Dilution from C to IPO (typical 10-15%)")
    option_pool_expansion: float = Field(default=0.05, ge=0, le=0.20,
                                          description="Option pool refresh per round (typical 5-8%)")


class VCDealInput(BaseModel):
    """
    Complete VC deal evaluation input.

    Represents a deal being evaluated from the investor's seat.
    Requires a FundProfile for context — most calculations are meaningless without it.
    """
    company_name: str
    vertical: VCVertical
    stage: VCStage

    # Deal terms
    post_money_valuation: float = Field(gt=0, description="Post-money valuation, USD millions")
    check_size: float = Field(gt=0, description="Amount you plan to invest, USD millions")

    # Company metrics
    arr: float = Field(default=0.0, ge=0, description="Current ARR, USD millions (0 if pre-revenue)")
    revenue_ttm: float = Field(default=0.0, ge=0, description="Trailing 12-month revenue if not pure SaaS, USD millions")
    revenue_growth_rate: float = Field(default=1.50, ge=0,
                                        description="Projected annual revenue growth rate (1.50 = 150%)")
    gross_margin: float = Field(default=0.70, ge=0, le=1.0)
    burn_rate_monthly: float = Field(default=0.0, ge=0, description="Monthly cash burn, USD millions")
    cash_on_hand: float = Field(default=0.0, ge=0, description="Cash in bank now, USD millions")

    # Dilution expectations
    dilution: DilutionAssumptions = Field(default_factory=DilutionAssumptions)

    # Cap table (for waterfall analysis)
    liquidation_stack: list[LiquidationPreference] = Field(default_factory=list)
    common_shares_pct: float = Field(default=0.30, ge=0, le=1.0,
                                      description="Common + ESOP as fraction of fully diluted (0.30 = 30%)")

    # Timing
    expected_exit_years: int = Field(default=7, ge=3, le=15,
                                      description="Expected years from now to exit")

    # Deal notes
    board_seat: bool = Field(default=False)
    pro_rata_rights: bool = Field(default=True)
    information_rights: bool = Field(default=True)

    # Quick-screen override: manually set scenario assumptions
    bear_exit_multiple_arr: Optional[float] = Field(default=None, ge=0,
                                                    description="Override bear case ARR multiple at exit")
    base_exit_multiple_arr: Optional[float] = Field(default=None, ge=0)
    bull_exit_multiple_arr: Optional[float] = Field(default=None, ge=0)


# ---------------------------------------------------------------------------
# Scenario definitions
# ---------------------------------------------------------------------------

class VCScenario(BaseModel):
    """One scenario (bear/base/bull) for a deal."""
    label: str                              # "Bear", "Base", "Bull"
    probability: float = Field(ge=0, le=1)
    exit_year: int = Field(ge=1, le=20)
    exit_multiple_arr: float = Field(ge=0)  # Revenue multiple at exit
    exit_enterprise_value: float            # USD millions
    gross_proceeds_to_fund: float           # USD millions (before carry)
    net_proceeds_to_fund: float             # USD millions (after carry, on gain)
    gross_moic: float
    net_moic: float
    gross_irr: float                        # Decimal
    net_irr: float                          # Decimal
    fund_contribution_x: float              # gross_proceeds / fund_size
    outcome_description: str


# ---------------------------------------------------------------------------
# Portfolio position (for portfolio dashboard)
# ---------------------------------------------------------------------------

class PortfolioPosition(BaseModel):
    """A single portfolio company tracked in the fund dashboard."""
    company_name: str
    vertical: VCVertical
    stage_at_entry: VCStage
    check_size: float
    post_money_at_entry: float
    entry_ownership_pct: float
    current_ownership_pct: float
    reserve_allocated: float = Field(default=0.0, description="Follow-on capital allocated, USD millions")
    reserve_deployed: float = Field(default=0.0, description="Follow-on capital actually deployed, USD millions")
    last_round_valuation: Optional[float] = Field(default=None)
    status: str = Field(default="active", description="active | written_off | exited | partially_exited")
    is_lead: bool = Field(default=False)
    vintage_year: int = Field(default=2024)
    cost_basis: float = Field(default=0.0, description="Total invested (initial + follow-on)")
    fair_value: Optional[float] = Field(default=None, description="Current FMV estimate, USD millions")
    realized_proceeds: float = Field(default=0.0, description="Proceeds returned to fund on exit/secondary")


# ---------------------------------------------------------------------------
# VC Analysis Output
# ---------------------------------------------------------------------------

class OwnershipMath(BaseModel):
    """Core ownership calculations — the heart of VC math."""
    entry_ownership_pct: float              # check_size / post_money
    exit_ownership_pct: float              # Entry after dilution stack
    dilution_stack: list[dict]             # Per-round breakdown
    total_dilution_pct: float              # 1 - exit/entry

    # Fund returner thresholds (at various exit values, what would this return?)
    fund_returner_1x_exit: float           # Exit needed to return 1x fund
    fund_returner_3x_exit: float           # Exit needed to return 3x fund
    fund_returner_5x_exit: float           # Exit needed to return 5x fund

    # Contribution at various exits
    exit_values_tested: list[float]        # Exit EVs tested
    gross_proceeds_at_exits: list[float]   # Gross proceeds at each exit
    fund_contribution_at_exits: list[float]  # Xof fund at each exit

    # Key multiples
    required_arr_multiple_for_1x_fund: Optional[float]  # ARR multiple needed to return 1x fund
    required_arr_multiple_for_3x_fund: Optional[float]


class QuickScreenResult(BaseModel):
    """Lightning-fast single-page screen result."""
    company_name: str
    stage: VCStage
    vertical: VCVertical
    post_money: float
    check_size: float

    entry_ownership_pct: float
    exit_ownership_pct: float  # After expected dilution

    # Fund math
    fund_returner_threshold: float       # Exit EV needed to return 1x fund
    fund_returner_arr_multiple: Optional[float]  # What ARR multiple does that imply

    # Quick scenarios (no probability weighting)
    bear_ev: float
    base_ev: float
    bull_ev: float
    bear_moic: float
    base_moic: float
    bull_moic: float

    # Pass/Look Deeper recommendation
    recommendation: str                  # "pass" | "look_deeper" | "strong_interest"
    recommendation_rationale: str

    # Key flags (list of short strings)
    flags: list[str]


class WaterfallDistribution(BaseModel):
    """Distribution of exit proceeds through cap table."""
    exit_ev: float
    share_classes: list[dict]            # Per class: name, preference_amount, conversion_value, gets
    common_gets: float
    total_distributed: float
    investor_total: float                # What THIS investor gets
    investor_moic: float
    conversion_was_optimal: bool         # True if converting was better than liquidating


class ProRataAnalysis(BaseModel):
    """Should you exercise your pro-rata right at the next round?"""
    company_name: str
    next_round_valuation: float
    pro_rata_amount: float               # How much you'd invest to maintain ownership
    maintained_ownership_pct: float
    diluted_ownership_if_pass: float

    reserve_impact: float                # Dollars pulled from reserve pool
    reserve_pct_remaining_after: float

    # Scenarios with and without exercise
    exercise_scenarios: list[VCScenario]
    pass_scenarios: list[VCScenario]

    # Recommendation
    expected_value_exercise: float
    expected_value_pass: float
    recommendation: str                  # "exercise" | "pass" | "partial"
    recommendation_rationale: str


class PortfolioConstructionStats(BaseModel):
    """Portfolio-level stats for the fund dashboard."""
    fund_size: float
    investable_capital: float
    initial_check_pool: float
    reserve_pool: float

    # Deployed
    total_initial_deployed: float
    total_reserve_deployed: float
    total_deployed: float
    pct_deployed: float

    # Remaining
    initial_remaining: float
    reserve_remaining: float
    total_remaining: float

    # Concentration
    company_count: int
    stage_breakdown: dict[str, float]    # Stage → total invested
    vertical_breakdown: dict[str, float] # Vertical → total invested
    largest_position_pct: float          # Biggest position as % of fund

    # Marks
    total_cost_basis: float
    total_fair_value: float
    unrealized_tvpi: float               # Total FMV / total cost basis
    realized_proceeds: float
    dpi: float                           # Distributed / paid-in
    rvpi: float                          # Residual / paid-in
    tvpi: float                          # Total (DPI + RVPI)

    # Projections
    reserve_adequacy: str                # "adequate" | "tight" | "over-reserved"
    average_follow_on_multiple: float    # Average reserves / initial check across portfolio


class ICMemoFinancials(BaseModel):
    """Auto-generated financial section for an IC memo."""
    company_name: str
    stage: VCStage
    vertical: VCVertical

    # Deal terms
    check_size: float
    post_money: float
    entry_ownership_pct: float
    instrument: str
    board_seat: bool
    pro_rata_rights: bool

    # Company metrics
    arr: float
    revenue_growth_rate: float
    gross_margin: float
    burn_rate_monthly: float
    runway_months: Optional[float]

    # Ownership math
    ownership_at_exit: float
    total_dilution_pct: float

    # Return scenarios
    scenarios: list[VCScenario]
    expected_value: float

    # Fund context
    fund_returner_threshold: float
    fund_contribution_base: float        # Xof fund in base case

    # Benchmarks
    arr_multiple_at_entry: Optional[float]
    stage_median_arr_multiple: Optional[float]
    valuation_vs_benchmark: str          # "at market", "above market", "below market"

    # Generated text blocks
    investment_thesis_prompt: str        # Pre-filled prompt for analyst to complete
    financial_summary_text: str          # Plain-English financial section


class VCDealOutput(BaseModel):
    """
    Complete VC deal analysis output.

    This is the answer to: "Should I write this check, at this price,
    given my fund thesis and portfolio construction constraints?"
    """
    company_name: str
    stage: VCStage
    vertical: VCVertical

    # Fund context (snapshot)
    fund_size: float
    check_size: float
    post_money: float

    # Core ownership math
    ownership: OwnershipMath

    # 3-scenario return model
    bear_scenario: VCScenario
    base_scenario: VCScenario
    bull_scenario: VCScenario
    expected_value: float                # Probability-weighted gross proceeds
    expected_moic: float
    expected_irr: float

    # Quick screen summary
    quick_screen: QuickScreenResult

    # Waterfall (if liquidation stack provided)
    waterfall: Optional[WaterfallDistribution] = None

    # IC memo materials
    ic_memo: ICMemoFinancials

    # Power law context
    power_law_note: str                  # Plain English: how many fund-returners you need
    ownership_adequacy: str             # "strong", "acceptable", "thin"

    # Benchmarks used
    vertical_benchmarks_used: dict

    # Flags and warnings
    flags: list[str]
    warnings: list[str]
    computation_notes: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Portfolio-level inputs (for the portfolio dashboard)
# ---------------------------------------------------------------------------

class PortfolioInput(BaseModel):
    """Input for portfolio construction analysis."""
    fund_profile: FundProfile
    positions: list[PortfolioPosition] = Field(default_factory=list)


class PortfolioOutput(BaseModel):
    """Complete portfolio construction output."""
    stats: PortfolioConstructionStats
    positions: list[PortfolioPosition]
    alerts: list[str]                    # "Over-concentrated in B2B SaaS", etc.
    recommendations: list[str]


# ---------------------------------------------------------------------------
# QSBS Analysis (Phase 4 — IRC Section 1202)
# ---------------------------------------------------------------------------

class QSBSInput(BaseModel):
    """Inputs for QSBS eligibility check."""
    company_name: str
    incorporated_in_c_corp: bool = Field(description="Incorporated as C-Corp (not LLC, S-Corp, partnership)")
    domestic_us_corp: bool = Field(description="US domestic corporation")
    active_business: bool = Field(description="Active business (not holding company, investment company, or professional services)")
    assets_at_issuance_under_50m: bool = Field(description="Aggregate gross assets < $50M at time of issuance")
    original_issuance: bool = Field(description="Shares acquired at original issuance (not secondary)")
    holding_period_years: float = Field(ge=0, description="Years held to date")
    investment_amount: float = Field(gt=0, description="Amount invested, USD millions")

    # New cap context (TCJA 2025)
    issuance_date_post_july_2025: bool = Field(default=False,
                                               description="Issued after July 4, 2025 (new $15M cap applies)")

    # LP context
    fund_size: float = Field(gt=0, description="Fund size for LP-level benefit calculation, USD millions")
    lp_count: int = Field(default=50, ge=1, description="Number of LPs for per-LP benefit estimation")
    lp_marginal_tax_rate: float = Field(default=0.37, ge=0, le=0.60)


class QSBSOutput(BaseModel):
    """QSBS eligibility result and tax benefit estimate."""
    company_name: str
    is_eligible: bool
    eligibility_checks: list[dict]       # Per-check: name, passed, note

    # If eligible
    holding_period_satisfied: bool       # >= 5 years
    years_remaining_to_qualify: Optional[float]

    exclusion_cap_per_taxpayer: float    # $10M or 10x basis, or $15M if new rules
    estimated_gain_excluded: float       # Min(cap, estimated gain)
    estimated_federal_tax_saved_per_lp: float
    estimated_total_lp_benefit: float

    # Caveats
    notes: list[str]
    irc_citation: str = "IRC § 1202"


# ---------------------------------------------------------------------------
# Anti-Dilution Scenario (Phase 4)
# ---------------------------------------------------------------------------

class AntiDilutionInput(BaseModel):
    """Inputs for anti-dilution scenario modeling."""
    company_name: str
    original_price_per_share: float = Field(gt=0)
    original_shares: float = Field(gt=0)
    down_round_price_per_share: float = Field(gt=0)
    down_round_new_shares_issued: float = Field(gt=0)
    anti_dilution_type: AntiDilutionType
    investor_preferred_shares: float = Field(gt=0)


class AntiDilutionOutput(BaseModel):
    """Anti-dilution adjustment calculations."""
    company_name: str
    anti_dilution_type: AntiDilutionType
    original_price: float
    down_round_price: float
    adjusted_conversion_price: float     # After anti-dilution adjustment
    additional_shares_issued: float      # Shares issued to protected investor
    economic_impact: float               # Value transferred in USD millions
    effective_ownership_pct_after: float
    notes: str


# ---------------------------------------------------------------------------
# Bridge / Extension Round (Phase 4)
# ---------------------------------------------------------------------------

class BridgeRoundInput(BaseModel):
    """Inputs for bridge / extension round modeling."""
    company_name: str
    bridge_amount: float = Field(gt=0, description="Bridge amount, USD millions")
    instrument: str = Field(default="safe", description="safe | convertible_note | equity")
    discount_rate: float = Field(default=0.20, ge=0, le=0.50)
    interest_rate: float = Field(default=0.08, ge=0, le=0.30,
                                  description="If convertible note; 0 if SAFE")
    maturity_months: int = Field(default=18, ge=6, le=36)
    pre_bridge_valuation: float = Field(gt=0)
    expected_next_round_valuation: float = Field(gt=0)
    current_ownership_pct: float = Field(gt=0, le=1.0)
    fund_is_participating: bool = Field(default=True)
    pro_rata_amount: float = Field(default=0.0, ge=0)


class BridgeRoundOutput(BaseModel):
    """Bridge round analysis."""
    company_name: str
    bridge_amount: float
    instrument: str

    # Ownership impact
    pre_bridge_ownership: float
    post_bridge_ownership_if_convert: float
    dilution_from_bridge: float

    # Economics
    effective_conversion_price: float
    implied_discount_to_next_round: float

    # Runway extension
    additional_runway_months: Optional[float]  # If burn rate known

    # IRR impact of participating vs. passing
    irr_if_participate: Optional[float]
    irr_if_pass: Optional[float]

    recommendation: str
    notes: list[str]


# ---------------------------------------------------------------------------
# LP Report (Phase 4)
# ---------------------------------------------------------------------------

class LPReportInput(BaseModel):
    """Inputs for LP report generation."""
    fund_profile: FundProfile
    positions: list[PortfolioPosition]
    report_date: str = Field(description="YYYY-MM-DD")
    include_company_names: bool = Field(default=True)


class LPReportOutput(BaseModel):
    """LP quarterly/annual report data."""
    fund_name: str
    report_date: str
    vintage_year: int

    # Performance
    committed_capital: float
    called_capital: float
    distributed_capital: float
    nav: float
    tvpi: float
    dpi: float
    rvpi: float
    net_irr: Optional[float]

    # Portfolio summary
    total_investments: int
    active_count: int
    exited_count: int
    written_off_count: int

    # Stage / vertical breakdown
    stage_breakdown: dict[str, float]
    vertical_breakdown: dict[str, float]

    # Notable events this period
    notable_events: list[str]

    # Generated narrative
    gp_commentary: str                   # Auto-generated performance commentary
