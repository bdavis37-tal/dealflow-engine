"""
Test suite for the VC return engine.

Tests cover all public functions in vc_return_engine.py including the main
orchestrator, ownership math, scenario engine, waterfall analysis, pro-rata,
portfolio construction, QSBS, anti-dilution, bridge round, and edge cases.

All monetary values in USD millions. Percentages as decimals (0.20 = 20%).
"""
import pytest

from app.engine.vc_fund_models import (
    AntiDilutionInput,
    AntiDilutionType,
    BridgeRoundInput,
    CarryStructure,
    DilutionAssumptions,
    FundProfile,
    GPCarryInput,
    LiquidationPreference,
    PortfolioInput,
    PortfolioPosition,
    PreferenceType,
    QSBSInput,
    SAFEConversionInput,
    SAFETerms,
    VCDealInput,
    VCStage,
    VCVertical,
)
from app.engine.vc_return_engine import (
    compute_ownership_math,
    compute_pro_rata,
    compute_scenarios,
    compute_waterfall,
    run_anti_dilution,
    run_bridge_analysis,
    run_gp_carry_analysis,
    run_portfolio_analysis,
    run_qsbs_analysis,
    run_safe_conversion,
    run_vc_deal_evaluation,
    _irr,
    _load_benchmarks,
)

TOLERANCE = 0.001  # 0.1%


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def seed_fund() -> FundProfile:
    """Typical $100M seed fund."""
    return FundProfile(
        fund_name="Test Seed Fund I",
        fund_size=100.0,
        vintage_year=2024,
        management_fee_pct=0.02,
        management_fee_years=5,
        carry_pct=0.20,
        hurdle_rate=0.08,
        reserve_ratio=0.40,
        target_initial_check_count=25,
        target_ownership_pct=0.10,
        recycling_pct=0.05,
        deployment_period_years=4,
    )


@pytest.fixture
def series_a_fund() -> FundProfile:
    """$300M Series A fund with higher ownership targets."""
    return FundProfile(
        fund_name="Growth Ventures II",
        fund_size=300.0,
        vintage_year=2024,
        management_fee_pct=0.02,
        management_fee_years=5,
        carry_pct=0.20,
        hurdle_rate=0.08,
        reserve_ratio=0.50,
        target_initial_check_count=20,
        target_ownership_pct=0.15,
        recycling_pct=0.05,
        deployment_period_years=4,
    )


@pytest.fixture
def default_dilution() -> DilutionAssumptions:
    """Default dilution assumptions (Carta medians)."""
    return DilutionAssumptions()


@pytest.fixture
def seed_deal(default_dilution) -> VCDealInput:
    """Typical seed-stage B2B SaaS deal."""
    return VCDealInput(
        company_name="Acme SaaS",
        vertical=VCVertical.B2B_SAAS,
        stage=VCStage.SEED,
        post_money_valuation=20.0,
        check_size=2.0,
        arr=0.5,
        revenue_growth_rate=2.0,
        gross_margin=0.75,
        burn_rate_monthly=0.15,
        cash_on_hand=3.0,
        dilution=default_dilution,
        expected_exit_years=7,
        pro_rata_rights=True,
        board_seat=False,
    )


@pytest.fixture
def pre_seed_deal(default_dilution) -> VCDealInput:
    """Pre-seed AI/ML deal, pre-revenue."""
    return VCDealInput(
        company_name="NeuralNet Labs",
        vertical=VCVertical.AI_ML_INFRASTRUCTURE,
        stage=VCStage.PRE_SEED,
        post_money_valuation=12.0,
        check_size=1.5,
        arr=0.0,
        revenue_growth_rate=0.0,
        gross_margin=0.0,
        burn_rate_monthly=0.1,
        cash_on_hand=1.5,
        dilution=default_dilution,
        expected_exit_years=8,
    )


@pytest.fixture
def deal_with_liquidation_stack(default_dilution) -> VCDealInput:
    """Series A deal with a liquidation preference stack."""
    return VCDealInput(
        company_name="StackCo",
        vertical=VCVertical.FINTECH,
        stage=VCStage.SERIES_A,
        post_money_valuation=50.0,
        check_size=5.0,
        arr=2.0,
        revenue_growth_rate=1.5,
        gross_margin=0.70,
        burn_rate_monthly=0.3,
        cash_on_hand=5.0,
        dilution=default_dilution,
        expected_exit_years=6,
        common_shares_pct=0.30,
        liquidation_stack=[
            LiquidationPreference(
                share_class="Series A Preferred",
                invested_amount=10.0,
                preference_multiple=1.0,
                preference_type=PreferenceType.NON_PARTICIPATING,
                seniority=1,
            ),
            LiquidationPreference(
                share_class="Seed Preferred",
                invested_amount=3.0,
                preference_multiple=1.0,
                preference_type=PreferenceType.NON_PARTICIPATING,
                seniority=2,
            ),
        ],
    )


@pytest.fixture
def benchmarks() -> dict:
    return _load_benchmarks()


# ---------------------------------------------------------------------------
# 1. Fund Profile Computed Properties
# ---------------------------------------------------------------------------

class TestFundProfileComputed:
    """Verify FundProfile computed properties match hand calculations."""

    def test_total_management_fees(self, seed_fund):
        # 100M * 0.02 * 5 = 10M
        assert seed_fund.total_management_fees == pytest.approx(10.0)

    def test_investable_capital(self, seed_fund):
        # 100 - 10 + (100 * 0.05) = 95M
        assert seed_fund.investable_capital == pytest.approx(95.0)

    def test_initial_check_pool(self, seed_fund):
        # 95 * (1 - 0.40) = 57M
        assert seed_fund.initial_check_pool == pytest.approx(57.0)

    def test_reserve_pool(self, seed_fund):
        # 95 * 0.40 = 38M
        assert seed_fund.reserve_pool == pytest.approx(38.0)

    def test_target_initial_check_size(self, seed_fund):
        # 57 / 25 = 2.28M
        assert seed_fund.target_initial_check_size == pytest.approx(57.0 / 25.0)

    def test_series_a_fund_larger_reserves(self, series_a_fund):
        # 300M fund: fees = 300*0.02*5 = 30M, recycling = 15M
        # investable = 300 - 30 + 15 = 285M
        # reserves = 285 * 0.50 = 142.5M
        assert series_a_fund.investable_capital == pytest.approx(285.0)
        assert series_a_fund.reserve_pool == pytest.approx(142.5)


# ---------------------------------------------------------------------------
# 2. Ownership Math
# ---------------------------------------------------------------------------

class TestOwnershipMath:
    """Test compute_ownership_math with known inputs."""

    def test_entry_ownership_basic(self, seed_fund, default_dilution):
        """Entry % = check_size / post_money."""
        ownership = compute_ownership_math(
            check_size=2.0,
            post_money=20.0,
            stage=VCStage.SEED,
            dilution=default_dilution,
            fund_profile=seed_fund,
            arr=0.5,
        )
        assert ownership.entry_ownership_pct == pytest.approx(0.10, abs=1e-6)

    def test_exit_ownership_after_dilution(self, seed_fund, default_dilution):
        """Seed investor diluted through Series A, B, C, IPO + option pool."""
        ownership = compute_ownership_math(
            check_size=2.0,
            post_money=20.0,
            stage=VCStage.SEED,
            dilution=default_dilution,
            fund_profile=seed_fund,
            arr=0.5,
        )
        # Carta FY2025 medians (M9 sync):
        # Seed → Series A: diluted by (seed_to_a + option_pool_expansion) = 0.185 + 0.05 = 0.235
        # Then Series B: 0.13 + 0.05 = 0.18
        # Then Series C: 0.11 + 0.05 = 0.16
        # Then IPO: 0.12 + 0.05 = 0.17
        # exit = 0.10 * (1-0.235) * (1-0.18) * (1-0.16) * (1-0.17)
        expected = 0.10 * 0.765 * 0.82 * 0.84 * 0.83
        assert ownership.exit_ownership_pct == pytest.approx(expected, rel=1e-4)

    def test_total_dilution_pct(self, seed_fund, default_dilution):
        ownership = compute_ownership_math(
            check_size=2.0,
            post_money=20.0,
            stage=VCStage.SEED,
            dilution=default_dilution,
            fund_profile=seed_fund,
            arr=0.5,
        )
        expected_dilution = 1.0 - (ownership.exit_ownership_pct / ownership.entry_ownership_pct)
        assert ownership.total_dilution_pct == pytest.approx(expected_dilution, rel=1e-4)

    def test_dilution_stack_length_seed(self, seed_fund, default_dilution):
        """Seed investor faces 4 dilution events: A, B, C, IPO."""
        ownership = compute_ownership_math(
            check_size=2.0,
            post_money=20.0,
            stage=VCStage.SEED,
            dilution=default_dilution,
            fund_profile=seed_fund,
            arr=0.5,
        )
        assert len(ownership.dilution_stack) == 4

    def test_dilution_stack_length_series_a(self, seed_fund, default_dilution):
        """Series A investor faces 3 dilution events: B, C, IPO."""
        ownership = compute_ownership_math(
            check_size=5.0,
            post_money=50.0,
            stage=VCStage.SERIES_A,
            dilution=default_dilution,
            fund_profile=seed_fund,
            arr=2.0,
        )
        assert len(ownership.dilution_stack) == 3

    def test_growth_stage_no_dilution(self, seed_fund, default_dilution):
        """Growth-stage investor has no future dilution rounds."""
        ownership = compute_ownership_math(
            check_size=10.0,
            post_money=200.0,
            stage=VCStage.GROWTH,
            dilution=default_dilution,
            fund_profile=seed_fund,
            arr=30.0,
        )
        assert len(ownership.dilution_stack) == 0
        assert ownership.entry_ownership_pct == ownership.exit_ownership_pct
        assert ownership.total_dilution_pct == pytest.approx(0.0)

    def test_fund_returner_thresholds(self, seed_fund, default_dilution):
        """Fund returner = fund_size * target_x / exit_ownership_pct."""
        ownership = compute_ownership_math(
            check_size=2.0,
            post_money=20.0,
            stage=VCStage.SEED,
            dilution=default_dilution,
            fund_profile=seed_fund,
            arr=0.5,
        )
        exit_pct = ownership.exit_ownership_pct
        assert ownership.fund_returner_1x_exit == pytest.approx(100.0 / exit_pct, rel=1e-4)
        assert ownership.fund_returner_3x_exit == pytest.approx(300.0 / exit_pct, rel=1e-4)
        assert ownership.fund_returner_5x_exit == pytest.approx(500.0 / exit_pct, rel=1e-4)

    def test_fund_returner_3x_gt_1x(self, seed_fund, default_dilution):
        ownership = compute_ownership_math(
            check_size=2.0,
            post_money=20.0,
            stage=VCStage.SEED,
            dilution=default_dilution,
            fund_profile=seed_fund,
            arr=0.5,
        )
        assert ownership.fund_returner_3x_exit > ownership.fund_returner_1x_exit
        assert ownership.fund_returner_5x_exit > ownership.fund_returner_3x_exit

    def test_arr_multiple_for_fund_returner(self, seed_fund, default_dilution):
        """Required ARR multiple = fund_returner_exit / ARR."""
        ownership = compute_ownership_math(
            check_size=2.0,
            post_money=20.0,
            stage=VCStage.SEED,
            dilution=default_dilution,
            fund_profile=seed_fund,
            arr=0.5,
        )
        expected_1x = ownership.fund_returner_1x_exit / 0.5
        assert ownership.required_arr_multiple_for_1x_fund == pytest.approx(expected_1x, rel=1e-4)

    def test_arr_multiple_none_when_no_arr(self, seed_fund, default_dilution):
        ownership = compute_ownership_math(
            check_size=2.0,
            post_money=20.0,
            stage=VCStage.SEED,
            dilution=default_dilution,
            fund_profile=seed_fund,
            arr=0.0,
        )
        assert ownership.required_arr_multiple_for_1x_fund is None
        assert ownership.required_arr_multiple_for_3x_fund is None

    def test_exit_values_tested(self, seed_fund, default_dilution):
        ownership = compute_ownership_math(
            check_size=2.0,
            post_money=20.0,
            stage=VCStage.SEED,
            dilution=default_dilution,
            fund_profile=seed_fund,
            arr=0.5,
        )
        assert 50.0 in ownership.exit_values_tested
        assert 1000.0 in ownership.exit_values_tested
        assert len(ownership.gross_proceeds_at_exits) == len(ownership.exit_values_tested)
        assert len(ownership.fund_contribution_at_exits) == len(ownership.exit_values_tested)


# ---------------------------------------------------------------------------
# 3. Scenario Engine
# ---------------------------------------------------------------------------

class TestScenarios:
    """Test compute_scenarios bear/base/bull model."""

    def test_three_scenarios_returned(self, seed_deal, seed_fund, benchmarks):
        ownership = compute_ownership_math(
            seed_deal.check_size, seed_deal.post_money_valuation,
            seed_deal.stage, seed_deal.dilution, seed_fund, seed_deal.arr,
        )
        bear, base, bull = compute_scenarios(
            seed_deal, seed_fund, ownership.exit_ownership_pct, benchmarks,
        )
        assert bear.label == "Bear"
        assert base.label == "Base"
        assert bull.label == "Bull"

    def test_probabilities_sum_to_one(self, seed_deal, seed_fund, benchmarks):
        ownership = compute_ownership_math(
            seed_deal.check_size, seed_deal.post_money_valuation,
            seed_deal.stage, seed_deal.dilution, seed_fund, seed_deal.arr,
        )
        bear, base, bull = compute_scenarios(
            seed_deal, seed_fund, ownership.exit_ownership_pct, benchmarks,
        )
        assert bear.probability + base.probability + bull.probability == pytest.approx(1.0)

    def test_bear_base_bull_ordering(self, seed_deal, seed_fund, benchmarks):
        """Bull exit EV > base exit EV > bear exit EV."""
        ownership = compute_ownership_math(
            seed_deal.check_size, seed_deal.post_money_valuation,
            seed_deal.stage, seed_deal.dilution, seed_fund, seed_deal.arr,
        )
        bear, base, bull = compute_scenarios(
            seed_deal, seed_fund, ownership.exit_ownership_pct, benchmarks,
        )
        assert bull.exit_enterprise_value > base.exit_enterprise_value
        assert base.exit_enterprise_value > bear.exit_enterprise_value

    def test_bull_moic_gt_base(self, seed_deal, seed_fund, benchmarks):
        ownership = compute_ownership_math(
            seed_deal.check_size, seed_deal.post_money_valuation,
            seed_deal.stage, seed_deal.dilution, seed_fund, seed_deal.arr,
        )
        bear, base, bull = compute_scenarios(
            seed_deal, seed_fund, ownership.exit_ownership_pct, benchmarks,
        )
        assert bull.gross_moic > base.gross_moic > bear.gross_moic

    def test_exit_multiples_from_benchmarks(self, seed_deal, seed_fund, benchmarks):
        """B2B SaaS upside multiples: base=5.0, bull=12.0. Bear is a write-off (0x)."""
        ownership = compute_ownership_math(
            seed_deal.check_size, seed_deal.post_money_valuation,
            seed_deal.stage, seed_deal.dilution, seed_fund, seed_deal.arr,
        )
        bear, base, bull = compute_scenarios(
            seed_deal, seed_fund, ownership.exit_ownership_pct, benchmarks,
        )
        assert bear.exit_multiple_arr == pytest.approx(0.0)  # failure branch
        assert base.exit_multiple_arr == pytest.approx(5.0)
        assert bull.exit_multiple_arr == pytest.approx(12.0)

    def test_override_exit_multiples(self, seed_fund, default_dilution, benchmarks):
        """Manual exit multiple overrides should be used."""
        deal = VCDealInput(
            company_name="Override Co",
            vertical=VCVertical.B2B_SAAS,
            stage=VCStage.SEED,
            post_money_valuation=20.0,
            check_size=2.0,
            arr=0.5,
            dilution=default_dilution,
            bear_exit_multiple_arr=1.0,
            base_exit_multiple_arr=3.0,
            bull_exit_multiple_arr=8.0,
        )
        ownership = compute_ownership_math(
            deal.check_size, deal.post_money_valuation,
            deal.stage, deal.dilution, seed_fund, deal.arr,
        )
        bear, base, bull = compute_scenarios(
            deal, seed_fund, ownership.exit_ownership_pct, benchmarks,
        )
        assert bear.exit_multiple_arr == pytest.approx(1.0)
        assert base.exit_multiple_arr == pytest.approx(3.0)
        assert bull.exit_multiple_arr == pytest.approx(8.0)

    def test_gross_proceeds_positive_upside_zero_bear(self, seed_deal, seed_fund, benchmarks):
        """C5 regression: bear is a write-off (zero proceeds, -100% IRR);
        base/bull remain positive."""
        ownership = compute_ownership_math(
            seed_deal.check_size, seed_deal.post_money_valuation,
            seed_deal.stage, seed_deal.dilution, seed_fund, seed_deal.arr,
        )
        bear, base, bull = compute_scenarios(
            seed_deal, seed_fund, ownership.exit_ownership_pct, benchmarks,
        )
        assert bear.gross_proceeds_to_fund == pytest.approx(0.0)
        assert bear.gross_moic == pytest.approx(0.0)
        assert bear.gross_irr == pytest.approx(-1.0)
        assert base.gross_proceeds_to_fund > 0
        assert bull.gross_proceeds_to_fund > 0

    def test_bear_probability_seeded_from_stage_benchmarks(self, seed_deal, seed_fund, benchmarks):
        """C5 regression: seed-stage failure mass comes from seed_to_failure (0.62)."""
        ownership = compute_ownership_math(
            seed_deal.check_size, seed_deal.post_money_valuation,
            seed_deal.stage, seed_deal.dilution, seed_fund, seed_deal.arr,
        )
        bear, base, bull = compute_scenarios(
            seed_deal, seed_fund, ownership.exit_ownership_pct, benchmarks,
        )
        expected_fail = benchmarks["stage_transition_probabilities"]["seed_to_failure"]
        assert bear.probability == pytest.approx(expected_fail)
        assert bear.probability + base.probability + bull.probability == pytest.approx(1.0)

    def test_bear_override_is_salvage_on_current_arr(self, seed_fund, default_dilution, benchmarks):
        """C5: a user-supplied bear multiple is a salvage multiple on CURRENT ARR."""
        deal = VCDealInput(
            company_name="Salvage Co",
            vertical=VCVertical.B2B_SAAS,
            stage=VCStage.SEED,
            post_money_valuation=20.0,
            check_size=2.0,
            arr=1.0,
            revenue_growth_rate=2.0,
            dilution=default_dilution,
            bear_exit_multiple_arr=1.5,
        )
        ownership = compute_ownership_math(
            deal.check_size, deal.post_money_valuation,
            deal.stage, deal.dilution, seed_fund, deal.arr,
        )
        bear, _, _ = compute_scenarios(deal, seed_fund, ownership.exit_ownership_pct, benchmarks)
        assert bear.exit_enterprise_value == pytest.approx(1.5 * 1.0)  # no growth projection

    def test_growth_decay_bounds_projection(self, seed_fund, default_dilution, benchmarks):
        """C5: growth decays annually — a 200% grower over 7 years projects far
        below constant compounding (3^7 ≈ 2187x) and within the 100x cap."""
        deal = VCDealInput(
            company_name="Hypergrowth Co",
            vertical=VCVertical.B2B_SAAS,
            stage=VCStage.SEED,
            post_money_valuation=20.0,
            check_size=2.0,
            arr=1.0,
            revenue_growth_rate=2.0,
            dilution=default_dilution,
            expected_exit_years=7,
        )
        ownership = compute_ownership_math(
            deal.check_size, deal.post_money_valuation,
            deal.stage, deal.dilution, seed_fund, deal.arr,
        )
        _, base, _ = compute_scenarios(deal, seed_fund, ownership.exit_ownership_pct, benchmarks)
        implied_arr = base.exit_enterprise_value / base.exit_multiple_arr
        assert implied_arr <= 100.0 * deal.arr + 1e-9   # hard cap honored
        assert implied_arr < (1 + 2.0) ** 7             # far below constant compounding

    def test_net_proceeds_le_gross(self, seed_deal, seed_fund, benchmarks):
        """Net proceeds (after carry) should not exceed gross."""
        ownership = compute_ownership_math(
            seed_deal.check_size, seed_deal.post_money_valuation,
            seed_deal.stage, seed_deal.dilution, seed_fund, seed_deal.arr,
        )
        bear, base, bull = compute_scenarios(
            seed_deal, seed_fund, ownership.exit_ownership_pct, benchmarks,
        )
        for sc in [bear, base, bull]:
            assert sc.net_proceeds_to_fund <= sc.gross_proceeds_to_fund

    def test_pre_revenue_deal_uses_placeholder(self, pre_seed_deal, seed_fund, benchmarks):
        """Pre-revenue deal uses $10M ARR placeholder for upside exit EVs;
        bear remains a write-off."""
        ownership = compute_ownership_math(
            pre_seed_deal.check_size, pre_seed_deal.post_money_valuation,
            pre_seed_deal.stage, pre_seed_deal.dilution, seed_fund, pre_seed_deal.arr,
        )
        bear, base, bull = compute_scenarios(
            pre_seed_deal, seed_fund, ownership.exit_ownership_pct, benchmarks,
        )
        # AI/ML base=10.0, bull=25.0 exit multiples × $10M placeholder (0% growth)
        assert bear.exit_enterprise_value == pytest.approx(0.0)
        assert base.exit_enterprise_value == pytest.approx(10.0 * 10.0, rel=0.01)
        assert bull.exit_enterprise_value == pytest.approx(25.0 * 10.0, rel=0.01)


# ---------------------------------------------------------------------------
# 4. Quick Screen Recommendation
# ---------------------------------------------------------------------------

class TestQuickScreen:
    """Test pass / look_deeper / strong_interest recommendation logic."""

    def test_recommendation_is_valid_value(self, seed_deal, seed_fund):
        output = run_vc_deal_evaluation(seed_deal, seed_fund)
        assert output.quick_screen.recommendation in ("pass", "look_deeper", "strong_interest")

    def test_small_check_still_screens(self, seed_fund, default_dilution):
        """Tiny check into a large fund should flag as concern."""
        deal = VCDealInput(
            company_name="Tiny Co",
            vertical=VCVertical.B2B_SAAS,
            stage=VCStage.SEED,
            post_money_valuation=20.0,
            check_size=0.5,  # Well below target of ~2.28M
            arr=0.3,
            dilution=default_dilution,
        )
        output = run_vc_deal_evaluation(deal, seed_fund)
        # Small check → ownership thin → likely pass
        assert output.quick_screen.entry_ownership_pct < seed_fund.target_ownership_pct

    def test_strong_interest_possible(self, seed_fund, default_dilution, benchmarks):
        """A deal with very high base MOIC and adequate ownership should rate strong_interest."""
        deal = VCDealInput(
            company_name="Unicorn Seed",
            vertical=VCVertical.AI_ML_INFRASTRUCTURE,
            stage=VCStage.SEED,
            post_money_valuation=10.0,
            check_size=1.0,
            arr=1.0,
            revenue_growth_rate=3.0,
            gross_margin=0.85,
            dilution=default_dilution,
            expected_exit_years=5,
        )
        output = run_vc_deal_evaluation(deal, seed_fund)
        # With 1.0M ARR and 3x growth rate, high exit multiples for AI/ML,
        # the base case MOIC should be very high
        assert output.quick_screen.base_moic > 5.0

    def test_flags_list_type(self, seed_deal, seed_fund):
        output = run_vc_deal_evaluation(seed_deal, seed_fund)
        assert isinstance(output.quick_screen.flags, list)
        for flag in output.quick_screen.flags:
            assert isinstance(flag, str)

    def test_short_runway_flagged(self, seed_fund, default_dilution):
        """Company with <12 months runway should be flagged."""
        deal = VCDealInput(
            company_name="Low Runway Co",
            vertical=VCVertical.B2B_SAAS,
            stage=VCStage.SEED,
            post_money_valuation=20.0,
            check_size=2.0,
            arr=0.5,
            burn_rate_monthly=0.5,  # 0.5M/month
            cash_on_hand=4.0,  # 8 months runway
            dilution=default_dilution,
        )
        output = run_vc_deal_evaluation(deal, seed_fund)
        runway_flags = [f for f in output.quick_screen.flags if "runway" in f.lower()]
        assert len(runway_flags) > 0


# ---------------------------------------------------------------------------
# 5. Waterfall Analysis
# ---------------------------------------------------------------------------

class TestWaterfall:
    """Test compute_waterfall with various preference structures."""

    def test_non_participating_conversion_optimal(self, deal_with_liquidation_stack):
        """At high exit EV, conversion should be better than liquidation preference."""
        # Series A invested $10M at 1x pref into $50M post; common = 30%
        # At $500M exit, conversion value should exceed $10M pref
        result = compute_waterfall(deal_with_liquidation_stack, 500.0)
        assert result.exit_ev == 500.0
        assert result.total_distributed == 500.0
        assert result.investor_total > 0
        # At $500M, conversion should be optimal for the most senior class
        assert result.conversion_was_optimal is True

    def test_non_participating_liquidation_preferred_at_low_ev(self, default_dilution):
        """At low exit EV, liquidation preference should be better than conversion."""
        deal = VCDealInput(
            company_name="LowExit",
            vertical=VCVertical.FINTECH,
            stage=VCStage.SERIES_A,
            post_money_valuation=50.0,
            check_size=5.0,
            arr=1.0,
            dilution=default_dilution,
            common_shares_pct=0.30,
            liquidation_stack=[
                LiquidationPreference(
                    share_class="Series A Preferred",
                    invested_amount=10.0,
                    preference_multiple=1.0,
                    preference_type=PreferenceType.NON_PARTICIPATING,
                    seniority=1,
                ),
            ],
        )
        # At exit = $12M, preferred gets $10M (1x pref), conversion < $10M
        result = compute_waterfall(deal, 12.0)
        assert result.investor_total == pytest.approx(10.0, abs=0.01)
        assert result.conversion_was_optimal is False

    def test_participating_preferred_gets_pref_plus_prorata(self, default_dilution):
        """Participating preferred gets liquidation pref + share of remainder."""
        deal = VCDealInput(
            company_name="ParticipCo",
            vertical=VCVertical.FINTECH,
            stage=VCStage.SERIES_A,
            post_money_valuation=50.0,
            check_size=5.0,
            arr=2.0,
            dilution=default_dilution,
            common_shares_pct=0.30,
            liquidation_stack=[
                LiquidationPreference(
                    share_class="Series A Preferred",
                    invested_amount=10.0,
                    preference_multiple=1.0,
                    preference_type=PreferenceType.PARTICIPATING,
                    seniority=1,
                ),
            ],
        )
        result = compute_waterfall(deal, 100.0)
        # Gets $10M pref + pro-rata of remainder
        assert result.investor_total > 10.0

    def _capped_deal(self, default_dilution) -> VCDealInput:
        return VCDealInput(
            company_name="CappedCo",
            vertical=VCVertical.FINTECH,
            stage=VCStage.SERIES_A,
            post_money_valuation=50.0,
            check_size=5.0,
            arr=2.0,
            dilution=default_dilution,
            common_shares_pct=0.30,
            liquidation_stack=[
                LiquidationPreference(
                    share_class="Series A Preferred",
                    invested_amount=10.0,
                    preference_multiple=1.0,
                    preference_type=PreferenceType.PARTICIPATING_CAPPED,
                    participation_cap=3.0,  # 3x cap
                    seniority=1,
                ),
            ],
        )

    def test_participating_capped_moderate_exit(self, default_dilution):
        """At a moderate exit the cap binds: pref + participation capped at 3x."""
        deal = self._capped_deal(default_dilution)
        # $40M exit: stay → pref 10 + 0.7×30 = 31 → capped at 30. Convert → 0.7×40 = 28.
        result = compute_waterfall(deal, 40.0)
        assert result.investor_total == pytest.approx(30.0, abs=0.01)
        assert result.conversion_was_optimal is False

    def test_participating_capped_converts_at_high_exit(self, default_dilution):
        """C3(a) regression: at a $1B exit the capped class exercises its
        CONVERSION option (~$700M as-converted) instead of the $30M cap."""
        deal = self._capped_deal(default_dilution)
        result = compute_waterfall(deal, 1000.0)
        # Sole preferred: as-converted fraction = (10/10) × (1 − 0.30) = 0.70
        assert result.investor_total == pytest.approx(700.0, rel=0.001)
        assert result.conversion_was_optimal is True

    def test_ownership_pct_used_for_conversion(self, default_dilution):
        """C3(b): explicit ownership_pct drives as-converted value instead of
        dollar-proportional estimation."""
        deal = VCDealInput(
            company_name="OwnPctCo",
            vertical=VCVertical.FINTECH,
            stage=VCStage.SERIES_A,
            post_money_valuation=50.0,
            check_size=5.0,
            arr=2.0,
            dilution=default_dilution,
            common_shares_pct=0.30,
            liquidation_stack=[
                LiquidationPreference(
                    share_class="Series A Preferred",
                    invested_amount=10.0,
                    preference_multiple=1.0,
                    preference_type=PreferenceType.NON_PARTICIPATING,
                    seniority=1,
                    ownership_pct=0.25,  # explicit as-converted stake
                ),
            ],
        )
        result = compute_waterfall(deal, 400.0)
        # Converting: residual pool = 400, weights = 0.30 common + 0.25 class
        # class gets 400 × 0.25/0.55
        assert result.investor_total == pytest.approx(400.0 * 0.25 / 0.55, rel=1e-6)
        assert not any("dollar-proportionally" in n for n in result.notes)

    def test_fallback_note_when_no_ownership_pct(self, deal_with_liquidation_stack):
        """C3(b): dollar-proportional fallback is flagged in notes."""
        result = compute_waterfall(deal_with_liquidation_stack, 100.0)
        assert any("dollar-proportionally" in n for n in result.notes)

    def test_total_distributed_never_exceeds_exit_ev(self, default_dilution, deal_with_liquidation_stack):
        """C3 invariant: sum of all distributions ≤ exit EV."""
        capped = self._capped_deal(default_dilution)
        for deal in (capped, deal_with_liquidation_stack):
            for ev in [0.0, 5.0, 12.0, 40.0, 100.0, 500.0, 1000.0]:
                result = compute_waterfall(deal, ev)
                paid = sum(d["gets"] for d in result.share_classes) + result.common_gets
                assert paid <= ev + 1e-6, f"over-distributed at EV={ev}"
                assert result.total_distributed == pytest.approx(paid, abs=1e-6)

    def test_investor_proceeds_monotonic_in_exit_ev(self, default_dilution, deal_with_liquidation_stack):
        """C3 invariant: investor proceeds never decrease as exit EV rises."""
        capped = self._capped_deal(default_dilution)
        for deal in (capped, deal_with_liquidation_stack):
            evs = [0, 5, 10, 20, 30, 40, 60, 100, 200, 400, 700, 1000]
            prev = -1.0
            for ev in evs:
                result = compute_waterfall(deal, float(ev))
                assert result.investor_total >= prev - 1e-6, f"non-monotonic at EV={ev}"
                prev = result.investor_total

    def test_junior_conversion_returns_pref_to_pool(self, default_dilution):
        """C3(c): when a class converts, its preference returns to the residual
        pool shared by the others."""
        deal = VCDealInput(
            company_name="RepoolCo",
            vertical=VCVertical.FINTECH,
            stage=VCStage.SERIES_A,
            post_money_valuation=50.0,
            check_size=5.0,
            arr=2.0,
            dilution=default_dilution,
            common_shares_pct=0.30,
            liquidation_stack=[
                LiquidationPreference(
                    share_class="Series A Preferred",
                    invested_amount=10.0,
                    preference_type=PreferenceType.PARTICIPATING,
                    seniority=1,
                    ownership_pct=0.40,
                ),
                LiquidationPreference(
                    share_class="Seed Preferred",
                    invested_amount=5.0,
                    preference_type=PreferenceType.NON_PARTICIPATING,
                    seniority=2,
                    ownership_pct=0.20,
                ),
            ],
        )
        result = compute_waterfall(deal, 200.0)
        seed_row = result.share_classes[1]
        # Seed converts at this EV; participating A's residual share must be
        # computed on the pool INCLUDING seed's forfeited preference.
        assert seed_row["converted"] is True
        # Residual = 200 − 10 (A pref) = 190; weights: 0.30 + 0.40 + 0.20 = 0.90
        assert result.share_classes[0]["gets"] == pytest.approx(10.0 + 190.0 * 0.40 / 0.90, rel=1e-6)
        assert seed_row["gets"] == pytest.approx(190.0 * 0.20 / 0.90, rel=1e-6)

    def test_preference_amount_reflects_multiple(self, default_dilution):
        """M11: preference_amount = invested × preference multiple."""
        deal = VCDealInput(
            company_name="MultCo",
            vertical=VCVertical.FINTECH,
            stage=VCStage.SERIES_A,
            post_money_valuation=50.0,
            check_size=5.0,
            dilution=default_dilution,
            common_shares_pct=0.30,
            liquidation_stack=[
                LiquidationPreference(
                    share_class="Series A Preferred",
                    invested_amount=10.0,
                    preference_multiple=2.0,
                    preference_type=PreferenceType.NON_PARTICIPATING,
                    seniority=1,
                ),
            ],
        )
        result = compute_waterfall(deal, 21.0)
        row = result.share_classes[0]
        assert row["preference_amount"] == pytest.approx(20.0)  # 2x on $10M
        assert row["invested_amount"] == pytest.approx(10.0)
        assert result.investor_total == pytest.approx(20.0, abs=0.01)

    def test_common_gets_remainder(self, deal_with_liquidation_stack):
        """Common shareholders get exit_ev minus preferred distributions."""
        result = compute_waterfall(deal_with_liquidation_stack, 200.0)
        assert result.common_gets >= 0.0
        total_preferred = sum(d["gets"] for d in result.share_classes)
        assert result.common_gets == pytest.approx(200.0 - total_preferred, abs=0.01)

    def test_zero_exit_ev(self, deal_with_liquidation_stack):
        """At $0 exit, nobody gets anything."""
        result = compute_waterfall(deal_with_liquidation_stack, 0.0)
        assert result.investor_total == 0.0
        assert result.common_gets == 0.0

    def test_single_investor_waterfall(self, default_dilution):
        """Single investor in liquidation stack."""
        deal = VCDealInput(
            company_name="SingleInvestor",
            vertical=VCVertical.B2B_SAAS,
            stage=VCStage.SEED,
            post_money_valuation=20.0,
            check_size=2.0,
            dilution=default_dilution,
            common_shares_pct=0.50,
            liquidation_stack=[
                LiquidationPreference(
                    share_class="Seed Preferred",
                    invested_amount=2.0,
                    preference_multiple=1.0,
                    preference_type=PreferenceType.NON_PARTICIPATING,
                    seniority=1,
                ),
            ],
        )
        result = compute_waterfall(deal, 50.0)
        assert result.investor_total > 0
        assert len(result.share_classes) == 1


# ---------------------------------------------------------------------------
# 6. Pro-Rata Analysis
# ---------------------------------------------------------------------------

class TestProRata:
    """Test compute_pro_rata exercise vs. pass analysis."""

    def test_pro_rata_returns_recommendation(self, seed_deal, seed_fund, benchmarks):
        ownership = compute_ownership_math(
            seed_deal.check_size, seed_deal.post_money_valuation,
            seed_deal.stage, seed_deal.dilution, seed_fund, seed_deal.arr,
        )
        result = compute_pro_rata(
            deal=seed_deal,
            fund=seed_fund,
            ownership=ownership,
            next_round_valuation=60.0,
            pro_rata_check=1.0,
            benchmarks=benchmarks,
        )
        assert result.recommendation in ("exercise", "pass", "partial")
        assert len(result.recommendation_rationale) > 0

    def test_exercise_vs_pass_scenarios_count(self, seed_deal, seed_fund, benchmarks):
        ownership = compute_ownership_math(
            seed_deal.check_size, seed_deal.post_money_valuation,
            seed_deal.stage, seed_deal.dilution, seed_fund, seed_deal.arr,
        )
        result = compute_pro_rata(
            deal=seed_deal,
            fund=seed_fund,
            ownership=ownership,
            next_round_valuation=60.0,
            pro_rata_check=1.0,
            benchmarks=benchmarks,
        )
        assert len(result.exercise_scenarios) == 3  # bear/base/bull
        assert len(result.pass_scenarios) == 3

    def test_maintained_ownership_gt_diluted(self, seed_deal, seed_fund, benchmarks):
        """Exercising should preserve higher ownership than passing."""
        ownership = compute_ownership_math(
            seed_deal.check_size, seed_deal.post_money_valuation,
            seed_deal.stage, seed_deal.dilution, seed_fund, seed_deal.arr,
        )
        result = compute_pro_rata(
            deal=seed_deal,
            fund=seed_fund,
            ownership=ownership,
            next_round_valuation=60.0,
            pro_rata_check=1.0,
            benchmarks=benchmarks,
        )
        assert result.maintained_ownership_pct > result.diluted_ownership_if_pass

    def test_reserve_impact(self, seed_deal, seed_fund, benchmarks):
        ownership = compute_ownership_math(
            seed_deal.check_size, seed_deal.post_money_valuation,
            seed_deal.stage, seed_deal.dilution, seed_fund, seed_deal.arr,
        )
        pro_rata_check = 2.0
        result = compute_pro_rata(
            deal=seed_deal,
            fund=seed_fund,
            ownership=ownership,
            next_round_valuation=60.0,
            pro_rata_check=pro_rata_check,
            benchmarks=benchmarks,
        )
        assert result.reserve_impact == pro_rata_check
        assert 0.0 <= result.reserve_pct_remaining_after <= 1.0


# ---------------------------------------------------------------------------
# 7. Portfolio Analysis
# ---------------------------------------------------------------------------

class TestPortfolioAnalysis:
    """Test run_portfolio_analysis with TVPI/DPI/RVPI."""

    def _make_positions(self) -> list[PortfolioPosition]:
        return [
            PortfolioPosition(
                company_name="Alpha",
                vertical=VCVertical.B2B_SAAS,
                stage_at_entry=VCStage.SEED,
                check_size=2.0,
                post_money_at_entry=20.0,
                entry_ownership_pct=0.10,
                current_ownership_pct=0.06,
                reserve_allocated=1.0,
                reserve_deployed=0.5,
                cost_basis=2.5,
                fair_value=8.0,
                realized_proceeds=0.0,
                status="active",
            ),
            PortfolioPosition(
                company_name="Beta",
                vertical=VCVertical.FINTECH,
                stage_at_entry=VCStage.SEED,
                check_size=2.0,
                post_money_at_entry=25.0,
                entry_ownership_pct=0.08,
                current_ownership_pct=0.05,
                reserve_allocated=1.0,
                reserve_deployed=0.0,
                cost_basis=2.0,
                fair_value=1.0,
                realized_proceeds=0.0,
                status="active",
            ),
            PortfolioPosition(
                company_name="Gamma",
                vertical=VCVertical.AI_ML_INFRASTRUCTURE,
                stage_at_entry=VCStage.SEED,
                check_size=2.0,
                post_money_at_entry=15.0,
                entry_ownership_pct=0.133,
                current_ownership_pct=0.0,
                cost_basis=2.0,
                fair_value=0.0,
                realized_proceeds=0.0,
                status="written_off",
            ),
            PortfolioPosition(
                company_name="Delta",
                vertical=VCVertical.B2B_SAAS,
                stage_at_entry=VCStage.SEED,
                check_size=2.0,
                post_money_at_entry=18.0,
                entry_ownership_pct=0.111,
                current_ownership_pct=0.0,
                cost_basis=2.0,
                fair_value=0.0,
                realized_proceeds=15.0,
                status="exited",
            ),
        ]

    def test_tvpi_computation(self, seed_fund):
        """C4 + M2: residual FV counts held positions only (fair_value of 0.0 is
        a real mark, never replaced by cost); denominator is called capital
        including the management-fee load."""
        positions = self._make_positions()
        inp = PortfolioInput(fund_profile=seed_fund, positions=positions)
        result = run_portfolio_analysis(inp)
        total_fv = sum(
            (p.fair_value if p.fair_value is not None else p.cost_basis)
            for p in positions
            if p.status in ("active", "partially_exited")
        )
        total_realized = sum(p.realized_proceeds for p in positions)
        total_deployed = sum(p.check_size for p in positions) + sum(p.reserve_deployed for p in positions)
        called_capital = total_deployed + seed_fund.total_management_fees
        expected_dpi = total_realized / called_capital
        expected_rvpi = total_fv / called_capital
        assert result.stats.dpi == pytest.approx(expected_dpi, rel=1e-3)
        assert result.stats.rvpi == pytest.approx(expected_rvpi, rel=1e-3)
        assert result.stats.tvpi == pytest.approx(expected_dpi + expected_rvpi, rel=1e-3)

    def test_written_off_position_not_marked_at_cost(self, seed_fund):
        """C4 regression: a written-off company (fair_value=0.0) must contribute
        $0 to residual value — `or cost_basis` used to resurrect it at cost."""
        positions = self._make_positions()
        inp = PortfolioInput(fund_profile=seed_fund, positions=positions)
        result = run_portfolio_analysis(inp)
        # Alpha fv=8, Beta fv=1 (active); Gamma written off fv=0; Delta exited.
        assert result.stats.total_fair_value == pytest.approx(9.0)

    def test_exited_proceeds_in_dpi_not_rvpi(self, seed_fund):
        """C4: exited position's value lives in DPI only."""
        positions = self._make_positions()
        inp = PortfolioInput(fund_profile=seed_fund, positions=positions)
        result = run_portfolio_analysis(inp)
        called = (sum(p.check_size for p in positions)
                  + sum(p.reserve_deployed for p in positions)
                  + seed_fund.total_management_fees)
        assert result.stats.dpi == pytest.approx(15.0 / called, rel=1e-6)
        # Delta's $15M exit does not appear in residual FV
        assert result.stats.rvpi == pytest.approx(9.0 / called, rel=1e-6)

    def test_reserve_over_committed_label(self, seed_fund):
        """M3: allocations above 110% of the reserve pool = 'over-committed'."""
        positions = [
            PortfolioPosition(
                company_name="BigReserve",
                vertical=VCVertical.B2B_SAAS,
                stage_at_entry=VCStage.SEED,
                check_size=2.0,
                post_money_at_entry=20.0,
                entry_ownership_pct=0.10,
                current_ownership_pct=0.10,
                reserve_allocated=seed_fund.reserve_pool * 1.5,  # 150% of pool
                cost_basis=2.0,
                status="active",
            ),
        ]
        result = run_portfolio_analysis(PortfolioInput(fund_profile=seed_fund, positions=positions))
        assert result.stats.reserve_adequacy == "over-committed"
        assert any("over-committed" in a for a in result.alerts)

    def test_company_count(self, seed_fund):
        positions = self._make_positions()
        inp = PortfolioInput(fund_profile=seed_fund, positions=positions)
        result = run_portfolio_analysis(inp)
        assert result.stats.company_count == 4

    def test_stage_breakdown(self, seed_fund):
        positions = self._make_positions()
        inp = PortfolioInput(fund_profile=seed_fund, positions=positions)
        result = run_portfolio_analysis(inp)
        assert "seed" in result.stats.stage_breakdown

    def test_vertical_breakdown(self, seed_fund):
        positions = self._make_positions()
        inp = PortfolioInput(fund_profile=seed_fund, positions=positions)
        result = run_portfolio_analysis(inp)
        assert "b2b_saas" in result.stats.vertical_breakdown

    def test_reserve_adequacy(self, seed_fund):
        positions = self._make_positions()
        inp = PortfolioInput(fund_profile=seed_fund, positions=positions)
        result = run_portfolio_analysis(inp)
        assert result.stats.reserve_adequacy in ("adequate", "tight", "over-reserved")

    def test_empty_portfolio(self, seed_fund):
        """Empty portfolio should not crash."""
        inp = PortfolioInput(fund_profile=seed_fund, positions=[])
        result = run_portfolio_analysis(inp)
        assert result.stats.company_count == 0
        assert result.stats.tvpi == 0.0

    def test_alerts_type(self, seed_fund):
        positions = self._make_positions()
        inp = PortfolioInput(fund_profile=seed_fund, positions=positions)
        result = run_portfolio_analysis(inp)
        assert isinstance(result.alerts, list)
        assert isinstance(result.recommendations, list)


# ---------------------------------------------------------------------------
# 8. QSBS Analysis
# ---------------------------------------------------------------------------

class TestQSBS:
    """Test run_qsbs_analysis for IRC Section 1202 eligibility."""

    def _make_qsbs_input(self, **overrides) -> QSBSInput:
        defaults = dict(
            company_name="QSBS Corp",
            incorporated_in_c_corp=True,
            domestic_us_corp=True,
            active_business=True,
            assets_at_issuance_under_50m=True,
            original_issuance=True,
            holding_period_years=6.0,
            investment_amount=2.0,
            fund_size=100.0,
            lp_count=50,
        )
        defaults.update(overrides)
        return QSBSInput(**defaults)

    def test_default_tax_rate_is_ltcg_plus_niit(self):
        """C1(c): benefit is measured at 23.8% (20% LTCG + 3.8% NIIT), not the
        37% ordinary rate."""
        assert QSBSInput(**dict(
            company_name="X", incorporated_in_c_corp=True, domestic_us_corp=True,
            active_business=True, assets_at_issuance_under_50m=True,
            original_issuance=True, holding_period_years=6.0,
            investment_amount=1.0, fund_size=100.0,
        )).lp_marginal_tax_rate == pytest.approx(0.238)

    def test_fully_eligible(self):
        result = run_qsbs_analysis(self._make_qsbs_input())
        assert result.is_eligible is True
        assert result.holding_period_satisfied is True
        assert result.years_remaining_to_qualify == 0.0

    def test_not_c_corp_ineligible(self):
        result = run_qsbs_analysis(self._make_qsbs_input(incorporated_in_c_corp=False))
        assert result.is_eligible is False

    def test_not_active_business_ineligible(self):
        result = run_qsbs_analysis(self._make_qsbs_input(active_business=False))
        assert result.is_eligible is False

    def test_secondary_shares_ineligible(self):
        result = run_qsbs_analysis(self._make_qsbs_input(original_issuance=False))
        assert result.is_eligible is False

    def test_holding_period_not_met(self):
        result = run_qsbs_analysis(self._make_qsbs_input(holding_period_years=3.0))
        assert result.is_eligible is True
        assert result.holding_period_satisfied is False
        assert result.years_remaining_to_qualify == pytest.approx(2.0)

    def test_exclusion_cap_pre_july_2025(self):
        """C1(a): §1202(b)(1) cap is the GREATER of $10M and 10× basis."""
        result = run_qsbs_analysis(self._make_qsbs_input(
            investment_amount=2.0,
            issuance_date_post_july_2025=False,
        ))
        # 10x basis = $20M > $10M dollar cap → cap = $20M
        assert result.exclusion_cap_per_taxpayer == pytest.approx(20.0)

    def test_exclusion_cap_post_july_2025(self):
        """After July 2025 (OBBBA): $15M dollar cap; still the greater-of rule."""
        result = run_qsbs_analysis(self._make_qsbs_input(
            investment_amount=1.0,
            issuance_date_post_july_2025=True,
        ))
        # 10x basis = $10M < $15M dollar cap → cap = $15M
        assert result.exclusion_cap_per_taxpayer == pytest.approx(15.0)

    def test_exclusion_cap_small_investment(self):
        """C1(a) regression: when 10x basis < $10M, the DOLLAR cap is the floor
        (greater-of, not lesser-of)."""
        result = run_qsbs_analysis(self._make_qsbs_input(
            investment_amount=0.5,
            issuance_date_post_july_2025=False,
        ))
        # 10x basis = $5M, dollar cap $10M → max = $10M
        assert result.exclusion_cap_per_taxpayer == pytest.approx(10.0)

    def test_tax_benefit_estimation(self):
        """C1(b)+(c): per-LP allocable gain/basis with per-LP caps, at 23.8%."""
        result = run_qsbs_analysis(self._make_qsbs_input(
            investment_amount=2.0,
            lp_count=10,
        ))
        # Fund gain at 10x = $20M → per-LP gain $2M, per-LP basis $0.2M
        # Per-LP cap = max($10M, 10×$0.2M) = $10M → excluded per LP = $2M
        # Tax saved per LP = $2M × 23.8% = $0.476M; total = $4.76M
        assert result.estimated_federal_tax_saved_per_lp == pytest.approx(2.0 * 0.238, rel=0.01)
        assert result.estimated_total_lp_benefit == pytest.approx(2.0 * 0.238 * 10, rel=0.01)
        assert result.estimated_gain_excluded == pytest.approx(20.0, rel=0.01)

    def test_per_lp_cap_binds_on_huge_position(self):
        """C1(b) regression: fund-level benefit is NOT lp_count × a fund-level
        exclusion — the per-LP cap binds on each LP's allocable share."""
        result = run_qsbs_analysis(self._make_qsbs_input(
            investment_amount=200.0,   # 10x gain = $2,000M
            fund_size=1000.0,
            lp_count=10,
        ))
        # Per-LP gain $200M, per-LP basis $20M → per-LP cap = max(10, 200) = $200M
        # → excluded per LP = $200M (10x-basis limb), NOT capped at $10M each
        assert result.estimated_federal_tax_saved_per_lp == pytest.approx(200.0 * 0.238, rel=0.01)
        # And with tiny basis per LP the dollar cap binds:
        result2 = run_qsbs_analysis(self._make_qsbs_input(
            investment_amount=20.0,    # per-LP gain $4M with 50 LPs
            lp_count=50,
        ))
        # per-LP gain = 200/50 = $4M < per-LP cap max(10, 4) = $10M → all excluded
        assert result2.estimated_federal_tax_saved_per_lp == pytest.approx(4.0 * 0.238, rel=0.01)

    def test_obbba_tiered_exclusion(self):
        """C1(d): post-July-2025 stock gets 50%/75%/100% at 3/4/5 years."""
        for years, pct in [(2.9, 0.0), (3.0, 0.50), (4.0, 0.75), (5.0, 1.0), (6.5, 1.0)]:
            result = run_qsbs_analysis(self._make_qsbs_input(
                holding_period_years=years,
                issuance_date_post_july_2025=True,
            ))
            assert result.exclusion_pct_applicable == pytest.approx(pct), f"at {years}y"
        # Pre-July-2025 stock remains all-or-nothing at 5 years
        for years, pct in [(3.0, 0.0), (4.9, 0.0), (5.0, 1.0)]:
            result = run_qsbs_analysis(self._make_qsbs_input(
                holding_period_years=years,
                issuance_date_post_july_2025=False,
            ))
            assert result.exclusion_pct_applicable == pytest.approx(pct), f"at {years}y"

    def test_obbba_asset_threshold_75m(self):
        """C1(d): gross-asset check reflects the $75M OBBBA threshold."""
        result = run_qsbs_analysis(self._make_qsbs_input(issuance_date_post_july_2025=True))
        assert any("$75M" in c["name"] for c in result.eligibility_checks)
        result_pre = run_qsbs_analysis(self._make_qsbs_input(issuance_date_post_july_2025=False))
        assert any("$50M" in c["name"] for c in result_pre.eligibility_checks)

    def test_eligibility_checks_list(self):
        result = run_qsbs_analysis(self._make_qsbs_input())
        assert len(result.eligibility_checks) == 5
        for check in result.eligibility_checks:
            assert "name" in check
            assert "passed" in check


# ---------------------------------------------------------------------------
# 9. Anti-Dilution
# ---------------------------------------------------------------------------

class TestAntiDilution:
    """Test run_anti_dilution for full ratchet and broad-based WA."""

    def _make_input(self, anti_type: AntiDilutionType) -> AntiDilutionInput:
        return AntiDilutionInput(
            company_name="DownRound Inc",
            original_price_per_share=10.0,
            original_shares=1_000_000,
            down_round_price_per_share=5.0,
            down_round_new_shares_issued=200_000,
            anti_dilution_type=anti_type,
            investor_preferred_shares=100_000,
        )

    def test_no_anti_dilution(self):
        result = run_anti_dilution(self._make_input(AntiDilutionType.NONE))
        assert result.adjusted_conversion_price == pytest.approx(10.0)
        assert result.additional_shares_issued == pytest.approx(0.0)
        assert result.economic_impact == pytest.approx(0.0)

    def test_full_ratchet_price_resets(self):
        """Full ratchet: conversion price resets to down-round price."""
        result = run_anti_dilution(self._make_input(AntiDilutionType.FULL_RATCHET))
        assert result.adjusted_conversion_price == pytest.approx(5.0)
        # Additional shares = 100K * (10/5) - 100K = 100K
        assert result.additional_shares_issued == pytest.approx(100_000.0)

    def test_full_ratchet_additional_shares(self):
        result = run_anti_dilution(self._make_input(AntiDilutionType.FULL_RATCHET))
        expected = 100_000 * 10.0 / 5.0 - 100_000
        assert result.additional_shares_issued == pytest.approx(expected)

    def test_broad_based_wa_price_between(self):
        """Broad-based WA: adjusted price should be between down-round and original price."""
        result = run_anti_dilution(self._make_input(AntiDilutionType.BROAD_BASED_WEIGHTED_AVERAGE))
        assert result.adjusted_conversion_price > 5.0  # down round price
        assert result.adjusted_conversion_price < 10.0  # original price

    def test_broad_based_wa_formula(self):
        """Verify broad-based WA formula: NCP = OCP * (A+B)/(A+C)."""
        inp = self._make_input(AntiDilutionType.BROAD_BASED_WEIGHTED_AVERAGE)
        result = run_anti_dilution(inp)
        A = 1_000_000  # original shares
        B = (200_000 * 5.0) / 10.0  # money raised / original price = 100K
        C = 200_000  # new shares
        expected_price = 10.0 * (A + B) / (A + C)
        assert result.adjusted_conversion_price == pytest.approx(expected_price, rel=1e-4)

    def test_broad_based_wa_fewer_additional_shares_than_ratchet(self):
        """BBWA should issue fewer additional shares than full ratchet."""
        ratchet = run_anti_dilution(self._make_input(AntiDilutionType.FULL_RATCHET))
        bbwa = run_anti_dilution(self._make_input(AntiDilutionType.BROAD_BASED_WEIGHTED_AVERAGE))
        assert bbwa.additional_shares_issued < ratchet.additional_shares_issued

    def test_economic_impact_positive_on_down_round(self):
        """Down round with protection transfers value to protected investor."""
        ratchet = run_anti_dilution(self._make_input(AntiDilutionType.FULL_RATCHET))
        assert ratchet.economic_impact > 0

    def test_effective_ownership_increases(self):
        """Anti-dilution should increase effective ownership vs. no protection."""
        no_protection = run_anti_dilution(self._make_input(AntiDilutionType.NONE))
        ratchet = run_anti_dilution(self._make_input(AntiDilutionType.FULL_RATCHET))
        assert ratchet.effective_ownership_pct_after > no_protection.effective_ownership_pct_after


# ---------------------------------------------------------------------------
# 10. Bridge Round Analysis
# ---------------------------------------------------------------------------

class TestBridgeAnalysis:
    """Test run_bridge_analysis for bridge round modeling."""

    def _make_bridge_input(self, **overrides) -> BridgeRoundInput:
        defaults = dict(
            company_name="Bridge Co",
            bridge_amount=2.0,
            instrument="safe",
            discount_rate=0.20,
            interest_rate=0.0,
            maturity_months=18,
            pre_bridge_valuation=30.0,
            expected_next_round_valuation=60.0,
            current_ownership_pct=0.10,
            fund_is_participating=True,
            pro_rata_amount=0.5,
        )
        defaults.update(overrides)
        return BridgeRoundInput(**defaults)

    def test_safe_bridge_dilutes_at_conversion(self):
        """H4: a SAFE bridge dilutes at conversion into the next round at the
        discounted valuation, not at the pre-bridge valuation."""
        result = run_bridge_analysis(self._make_bridge_input())
        # effective conversion valuation = 60 × 0.8 = 48; dilution = 2/(48+2)
        assert result.dilution_from_bridge == pytest.approx(2.0 / 50.0, rel=1e-4)

    def test_equity_bridge_dilutes_at_pre_bridge_valuation(self):
        result = run_bridge_analysis(self._make_bridge_input(instrument="equity"))
        # dilution = bridge / (pre_bridge + bridge) = 2 / 32 = 0.0625
        assert result.dilution_from_bridge == pytest.approx(2.0 / 32.0, rel=1e-4)

    def test_convertible_note_interest_converts(self):
        """H4: accrued interest converts with principal and increases dilution."""
        no_interest = run_bridge_analysis(self._make_bridge_input(
            instrument="convertible_note", interest_rate=0.0,
        ))
        with_interest = run_bridge_analysis(self._make_bridge_input(
            instrument="convertible_note", interest_rate=0.08, maturity_months=18,
        ))
        accrued = 2.0 * 0.08 * (18 / 12.0)  # 0.24
        expected = (2.0 + accrued) / (48.0 + 2.0 + accrued)
        assert with_interest.dilution_from_bridge == pytest.approx(expected, rel=1e-4)
        assert with_interest.dilution_from_bridge > no_interest.dilution_from_bridge

    def test_post_bridge_ownership(self):
        result = run_bridge_analysis(self._make_bridge_input())
        expected = 0.10 * (1 - 2.0 / 50.0)
        assert result.post_bridge_ownership_if_convert == pytest.approx(expected, rel=1e-4)

    def test_effective_conversion_price(self):
        result = run_bridge_analysis(self._make_bridge_input())
        # effective = next_round_val * (1 - discount) = 60 * 0.80 = 48
        assert result.effective_conversion_price == pytest.approx(48.0, rel=1e-4)

    def test_implied_discount(self):
        result = run_bridge_analysis(self._make_bridge_input())
        assert result.implied_discount_to_next_round == pytest.approx(0.20, rel=1e-4)

    def test_recommendation_is_structured(self):
        """H4: recommendation is a real participate/pass/monitor decision."""
        result = run_bridge_analysis(self._make_bridge_input())
        assert result.recommendation in ("participate", "pass", "monitor")

    def test_not_participating_yields_monitor(self):
        result = run_bridge_analysis(self._make_bridge_input(fund_is_participating=False))
        assert result.recommendation == "monitor"

    def test_pass_when_no_discount_and_negligible_dilution(self):
        """H4: both branches no longer unconditionally say 'participate'."""
        result = run_bridge_analysis(self._make_bridge_input(
            discount_rate=0.0,          # no discount economics
            bridge_amount=0.1,          # negligible dilution
            pro_rata_amount=0.2,        # benefit ≪ 10% of the check
        ))
        assert result.recommendation == "pass"

    def test_notes_include_conversion_info(self):
        result = run_bridge_analysis(self._make_bridge_input())
        assert len(result.notes) > 0
        assert any("discount" in n.lower() or "convert" in n.lower() for n in result.notes)

    def test_convertible_note_interest_accrual(self):
        """Convertible note with interest should mention accrued interest in notes."""
        result = run_bridge_analysis(self._make_bridge_input(
            instrument="convertible_note",
            interest_rate=0.08,
        ))
        assert any("interest" in n.lower() for n in result.notes)

    def test_additional_runway_from_real_burn(self):
        """H4: runway = bridge / monthly_burn when burn is provided."""
        result = run_bridge_analysis(self._make_bridge_input(monthly_burn=0.25))
        assert result.additional_runway_months == pytest.approx(2.0 / 0.25)

    def test_additional_runway_none_without_burn(self):
        """H4 regression: no fabricated 18-month constant when burn is unknown."""
        result = run_bridge_analysis(self._make_bridge_input())
        assert result.additional_runway_months is None
        assert any("burn" in n.lower() for n in result.notes)


# ---------------------------------------------------------------------------
# 11. Main Orchestrator — run_vc_deal_evaluation
# ---------------------------------------------------------------------------

class TestRunVCDealEvaluation:
    """Test the main orchestrator end-to-end."""

    def test_output_has_all_required_fields(self, seed_deal, seed_fund):
        output = run_vc_deal_evaluation(seed_deal, seed_fund)
        assert output.company_name == "Acme SaaS"
        assert output.stage == VCStage.SEED
        assert output.vertical == VCVertical.B2B_SAAS
        assert output.fund_size == 100.0
        assert output.check_size == 2.0
        assert output.post_money == 20.0

    def test_ownership_math_populated(self, seed_deal, seed_fund):
        output = run_vc_deal_evaluation(seed_deal, seed_fund)
        assert output.ownership.entry_ownership_pct > 0
        assert output.ownership.exit_ownership_pct > 0
        assert output.ownership.exit_ownership_pct < output.ownership.entry_ownership_pct

    def test_three_scenarios_populated(self, seed_deal, seed_fund):
        output = run_vc_deal_evaluation(seed_deal, seed_fund)
        assert output.bear_scenario.label == "Bear"
        assert output.base_scenario.label == "Base"
        assert output.bull_scenario.label == "Bull"

    def test_expected_value_is_probability_weighted(self, seed_deal, seed_fund):
        output = run_vc_deal_evaluation(seed_deal, seed_fund)
        expected = (
            output.bear_scenario.gross_proceeds_to_fund * output.bear_scenario.probability
            + output.base_scenario.gross_proceeds_to_fund * output.base_scenario.probability
            + output.bull_scenario.gross_proceeds_to_fund * output.bull_scenario.probability
        )
        assert output.expected_value == pytest.approx(expected, rel=1e-4)

    def test_expected_moic(self, seed_deal, seed_fund):
        output = run_vc_deal_evaluation(seed_deal, seed_fund)
        assert output.expected_moic == pytest.approx(
            output.expected_value / seed_deal.check_size, rel=1e-4,
        )

    def test_quick_screen_populated(self, seed_deal, seed_fund):
        output = run_vc_deal_evaluation(seed_deal, seed_fund)
        assert output.quick_screen is not None
        assert output.quick_screen.company_name == "Acme SaaS"

    def test_waterfall_none_when_no_stack(self, seed_deal, seed_fund):
        """No liquidation stack → waterfall should be None."""
        assert len(seed_deal.liquidation_stack) == 0
        output = run_vc_deal_evaluation(seed_deal, seed_fund)
        assert output.waterfall is None

    def test_waterfall_populated_when_stack_exists(self, deal_with_liquidation_stack, seed_fund):
        output = run_vc_deal_evaluation(deal_with_liquidation_stack, seed_fund)
        assert output.waterfall is not None
        assert output.waterfall.exit_ev > 0

    def test_ic_memo_populated(self, seed_deal, seed_fund):
        output = run_vc_deal_evaluation(seed_deal, seed_fund)
        assert output.ic_memo is not None
        assert output.ic_memo.company_name == "Acme SaaS"
        assert len(output.ic_memo.financial_summary_text) > 50
        assert len(output.ic_memo.investment_thesis_prompt) > 50

    def test_ownership_adequacy(self, seed_deal, seed_fund):
        output = run_vc_deal_evaluation(seed_deal, seed_fund)
        assert output.ownership_adequacy in ("strong", "acceptable", "thin")

    def test_power_law_note_not_empty(self, seed_deal, seed_fund):
        output = run_vc_deal_evaluation(seed_deal, seed_fund)
        assert len(output.power_law_note) > 20

    def test_vertical_benchmarks_used(self, seed_deal, seed_fund):
        output = run_vc_deal_evaluation(seed_deal, seed_fund)
        assert isinstance(output.vertical_benchmarks_used, dict)
        assert len(output.vertical_benchmarks_used) > 0

    def test_flags_and_warnings_are_lists(self, seed_deal, seed_fund):
        output = run_vc_deal_evaluation(seed_deal, seed_fund)
        assert isinstance(output.flags, list)
        assert isinstance(output.warnings, list)

    def test_pre_revenue_warning(self, pre_seed_deal, seed_fund):
        """Pre-revenue deal should produce a revenue placeholder warning."""
        output = run_vc_deal_evaluation(pre_seed_deal, seed_fund)
        assert any("revenue" in w.lower() or "placeholder" in w.lower() for w in output.warnings)

    def test_ic_memo_instrument_type(self, seed_deal, seed_fund):
        """Seed deal should use SAFE instrument."""
        output = run_vc_deal_evaluation(seed_deal, seed_fund)
        assert output.ic_memo.instrument == "SAFE"

    def test_series_a_instrument_type(self, deal_with_liquidation_stack, seed_fund):
        """Series A deal should use Priced Equity instrument."""
        output = run_vc_deal_evaluation(deal_with_liquidation_stack, seed_fund)
        assert output.ic_memo.instrument == "Priced Equity"


# ---------------------------------------------------------------------------
# 12. Edge Cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_zero_dilution(self, seed_fund):
        """Zero dilution assumptions mean no ownership loss."""
        dilution = DilutionAssumptions(
            pre_seed_to_seed=0.0,
            seed_to_a=0.0,
            a_to_b=0.0,
            b_to_c=0.0,
            c_to_ipo=0.0,
            option_pool_expansion=0.0,
        )
        ownership = compute_ownership_math(
            check_size=2.0,
            post_money=20.0,
            stage=VCStage.SEED,
            dilution=dilution,
            fund_profile=seed_fund,
            arr=0.5,
        )
        assert ownership.entry_ownership_pct == ownership.exit_ownership_pct
        assert ownership.total_dilution_pct == pytest.approx(0.0)

    def test_max_dilution(self, seed_fund):
        """High dilution should still produce valid output."""
        dilution = DilutionAssumptions(
            pre_seed_to_seed=0.30,
            seed_to_a=0.30,
            a_to_b=0.30,
            b_to_c=0.30,
            c_to_ipo=0.30,
            option_pool_expansion=0.10,
        )
        ownership = compute_ownership_math(
            check_size=2.0,
            post_money=20.0,
            stage=VCStage.PRE_SEED,
            dilution=dilution,
            fund_profile=seed_fund,
            arr=0.0,
        )
        assert ownership.exit_ownership_pct > 0
        assert ownership.exit_ownership_pct < ownership.entry_ownership_pct

    def test_small_check_large_fund(self):
        """Very small check into a very large fund should not crash."""
        fund = FundProfile(
            fund_size=500.0,
            target_initial_check_count=20,
            target_ownership_pct=0.15,
        )
        deal = VCDealInput(
            company_name="Tiny Deal",
            vertical=VCVertical.B2B_SAAS,
            stage=VCStage.SEED,
            post_money_valuation=10.0,
            check_size=0.5,
            arr=0.1,
        )
        output = run_vc_deal_evaluation(deal, fund)
        assert output is not None
        assert output.ownership.entry_ownership_pct == pytest.approx(0.05)

    def test_growth_stage_deal(self, seed_fund):
        """Growth stage deal has no future dilution rounds."""
        deal = VCDealInput(
            company_name="GrowthCo",
            vertical=VCVertical.B2B_SAAS,
            stage=VCStage.GROWTH,
            post_money_valuation=500.0,
            check_size=20.0,
            arr=50.0,
            revenue_growth_rate=0.5,
        )
        output = run_vc_deal_evaluation(deal, seed_fund)
        assert output.ownership.entry_ownership_pct == output.ownership.exit_ownership_pct
        assert len(output.ownership.dilution_stack) == 0

    def test_no_liquidation_stack_orchestrator(self, seed_deal, seed_fund):
        """Main orchestrator with no liquidation stack should produce None waterfall."""
        output = run_vc_deal_evaluation(seed_deal, seed_fund)
        assert output.waterfall is None

    def test_all_verticals_have_benchmarks(self, benchmarks):
        """All VCVertical enum values should have benchmark data."""
        for v in VCVertical:
            vdata = benchmarks.get("verticals", {}).get(v.value, {})
            # Not all verticals may have data — but at least the main ones should
            if v.value in ("b2b_saas", "fintech", "ai_ml_infrastructure"):
                assert "exit_multiples" in vdata, f"Missing exit_multiples for {v.value}"


# ---------------------------------------------------------------------------
# 13. Helper Functions
# ---------------------------------------------------------------------------

class TestHelpers:
    """Test helper functions used across the engine."""

    def test_irr_simple(self):
        """$1 invested, $2 returned in 1 year = 100% IRR."""
        assert _irr(1.0, 2.0, 1.0) == pytest.approx(1.0)

    def test_irr_multi_year(self):
        """$1 invested, $4 returned in 2 years = 100% IRR."""
        assert _irr(1.0, 4.0, 2.0) == pytest.approx(1.0)

    def test_irr_zero_investment(self):
        assert _irr(0.0, 10.0, 5.0) == 0.0

    def test_irr_zero_proceeds(self):
        assert _irr(10.0, 0.0, 5.0) == 0.0

    def test_irr_zero_years(self):
        assert _irr(10.0, 20.0, 0.0) == 0.0

    def test_load_benchmarks_returns_dict(self):
        b = _load_benchmarks()
        assert isinstance(b, dict)
        assert "verticals" in b


# ---------------------------------------------------------------------------
# 14. GP Carry (C2)
# ---------------------------------------------------------------------------

class TestGPCarry:
    """GP carry waterfall: crash fix, catch-up mechanics, called-capital timing."""

    def _make_input(self, seed_fund, **overrides) -> GPCarryInput:
        defaults = dict(
            fund_profile=seed_fund,
            carry_structure=CarryStructure.WHOLE_FUND,
            gp_commit_pct=0.02,
            catch_up_pct=1.00,
            catch_up_target=0.20,
            clawback_escrow_pct=0.30,
            num_gps=2,
            gp_salary_annual=0.4,
            total_distributions=300.0,
            fund_life_years=10,
        )
        defaults.update(overrides)
        return GPCarryInput(**defaults)

    def test_no_crash_between_1x_and_hurdle(self, seed_fund):
        """C2(a) regression: 1.1x gross used to raise UnboundLocalError."""
        result = run_gp_carry_analysis(self._make_input(seed_fund, total_distributions=110.0))
        assert result.total_gp_carry == pytest.approx(0.0)  # all profit absorbed by hurdle
        assert result.lp_total_distributions == pytest.approx(110.0)

    def test_no_crash_across_gross_multiple_sweep(self, seed_fund):
        """Engine never raises across the 0.5x–5x range."""
        for dist in [50.0, 100.0, 105.0, 130.0, 180.0, 216.0, 300.0, 500.0]:
            result = run_gp_carry_analysis(self._make_input(seed_fund, total_distributions=dist))
            assert result.total_gp_carry >= 0.0
            assert result.lp_total_distributions + result.total_gp_carry == pytest.approx(dist)

    def test_zero_hurdle_gp_take_is_exactly_carry(self):
        """C2(b): with no hurdle there is no catch-up; GP take = carry% × profit."""
        fund = FundProfile(fund_size=100.0, hurdle_rate=0.0, carry_pct=0.20)
        result = run_gp_carry_analysis(self._make_input(fund, total_distributions=300.0))
        assert result.catch_up_amount == pytest.approx(0.0)
        assert result.total_gp_carry == pytest.approx(0.20 * 200.0)

    def test_fully_caught_up_totals_carry_pct_of_profit(self, seed_fund):
        """C2(b) regression: no double-count — once fully caught up, total GP
        take equals carry% × total profit exactly."""
        result = run_gp_carry_analysis(self._make_input(seed_fund, total_distributions=300.0))
        total_profit = 300.0 - 100.0
        assert result.total_gp_carry == pytest.approx(0.20 * total_profit, rel=1e-9)
        # And the catch-up itself equals carry/(1−carry) × preferred
        assert result.catch_up_amount == pytest.approx(
            (0.20 / 0.80) * result.preferred_return_amount, rel=1e-9,
        )

    def test_preferred_uses_called_capital_timing(self, seed_fund):
        """C2/M5: preferred return is less than a day-0 lump-sum compound on
        the full commitment."""
        result = run_gp_carry_analysis(self._make_input(seed_fund, total_distributions=500.0))
        day0_lump = 100.0 * ((1.08 ** 10) - 1)
        assert 0 < result.preferred_return_amount < day0_lump
        assert any("call timing" in n or "called evenly" in n for n in result.notes)


# ---------------------------------------------------------------------------
# 15. SAFE Conversion (H3)
# ---------------------------------------------------------------------------

class TestSAFEConversion:
    """Post-money SAFE math, MFN issuance ordering, option pool sizing."""

    def test_post_money_safe_ownership_equals_amount_over_cap(self):
        """H3 regression: $5M post-money SAFE at $10M cap = 50% of the
        post-SAFE capitalization (engine used to say 33.3%)."""
        inp = SAFEConversionInput(
            company_name="PostMoneyCo",
            safe_stack=[SAFETerms(
                investor_name="Lead",
                safe_amount=5.0,
                valuation_cap=10.0,
                discount_rate=0.0,
                is_post_money=True,
            )],
            priced_round_pre_money=30.0,
            priced_round_amount=10.0,
            pre_safe_shares_outstanding=10_000_000,
            option_pool_pct=0.0,
        )
        result = run_safe_conversion(inp)
        shares = result.conversions[0].shares_issued
        pre_round = 10_000_000
        # SAFE owns amount/cap = 50% of (pre-round + SAFE shares)
        assert shares / (pre_round + shares) == pytest.approx(0.50, rel=1e-6)

    def test_pre_money_safe_unchanged(self):
        """Pre-money SAFE: cap over pre-round shares."""
        inp = SAFEConversionInput(
            company_name="PreMoneyCo",
            safe_stack=[SAFETerms(
                investor_name="Angel",
                safe_amount=5.0,
                valuation_cap=10.0,
                discount_rate=0.0,
                is_post_money=False,
            )],
            priced_round_pre_money=30.0,
            priced_round_amount=10.0,
            pre_safe_shares_outstanding=10_000_000,
            option_pool_pct=0.0,
        )
        result = run_safe_conversion(inp)
        shares = result.conversions[0].shares_issued
        # cap pps = 10/10M = $1 → 5M shares → 33.3% of pre+safe
        assert shares == pytest.approx(5_000_000, rel=1e-6)

    def test_mfn_only_inherits_from_later_safes(self):
        """H3: MFN looks forward (stack order = issuance order), never backward."""
        inp = SAFEConversionInput(
            company_name="MFNCo",
            safe_stack=[
                SAFETerms(investor_name="EarlyCheap", safe_amount=1.0,
                          valuation_cap=5.0, is_post_money=False),   # earlier, better cap
                SAFETerms(investor_name="MFN Holder", safe_amount=1.0,
                          valuation_cap=12.0, has_mfn=True, is_post_money=False),
                SAFETerms(investor_name="LaterBetter", safe_amount=1.0,
                          valuation_cap=8.0, is_post_money=False),   # later, better than 12
            ],
            priced_round_pre_money=30.0,
            priced_round_amount=10.0,
            pre_safe_shares_outstanding=10_000_000,
            option_pool_pct=0.0,
        )
        result = run_safe_conversion(inp)
        mfn = result.conversions[1]
        later = result.conversions[2]
        early = result.conversions[0]
        # MFN inherits the $8M cap from the LATER safe — not $5M from the earlier one
        assert mfn.conversion_price == pytest.approx(later.conversion_price, rel=1e-9)
        assert mfn.conversion_price > early.conversion_price
        assert mfn.mfn_adjusted is True

    def test_mfn_with_no_later_safes_is_unchanged(self):
        inp = SAFEConversionInput(
            company_name="MFNLastCo",
            safe_stack=[
                SAFETerms(investor_name="Cheap", safe_amount=1.0,
                          valuation_cap=5.0, is_post_money=False),
                SAFETerms(investor_name="MFN Last", safe_amount=1.0,
                          valuation_cap=12.0, has_mfn=True, is_post_money=False),
            ],
            priced_round_pre_money=30.0,
            priced_round_amount=10.0,
            pre_safe_shares_outstanding=10_000_000,
            option_pool_pct=0.0,
        )
        result = run_safe_conversion(inp)
        assert result.conversions[1].mfn_adjusted is False
        # Still converts on its own $12M cap
        assert result.conversions[1].conversion_price == pytest.approx(12.0 / 10_000_000, rel=1e-9)

    def test_option_pool_pct_of_post_money(self):
        """H3: pool is option_pool_pct of the POST-money fully diluted total."""
        inp = SAFEConversionInput(
            company_name="PoolCo",
            safe_stack=[SAFETerms(investor_name="S", safe_amount=1.0,
                                  valuation_cap=10.0, is_post_money=False)],
            priced_round_pre_money=30.0,
            priced_round_amount=10.0,
            pre_safe_shares_outstanding=10_000_000,
            option_pool_pct=0.10,
        )
        result = run_safe_conversion(inp)
        assert result.option_pool_shares / result.total_shares == pytest.approx(0.10, rel=1e-4)

    def test_input_safe_terms_not_mutated(self):
        """MFN adjustment must not mutate the caller's SAFE objects."""
        stack = [
            SAFETerms(investor_name="MFN", safe_amount=1.0, valuation_cap=None,
                      has_mfn=True, is_post_money=False),
            SAFETerms(investor_name="Late", safe_amount=1.0, valuation_cap=6.0,
                      is_post_money=False),
        ]
        inp = SAFEConversionInput(
            company_name="NoMutate",
            safe_stack=stack,
            priced_round_pre_money=30.0,
            priced_round_amount=10.0,
            pre_safe_shares_outstanding=10_000_000,
            option_pool_pct=0.0,
        )
        run_safe_conversion(inp)
        assert stack[0].valuation_cap is None  # unchanged


# ---------------------------------------------------------------------------
# 16. Fund-returner thresholds (H5)
# ---------------------------------------------------------------------------

class TestFundReturnerNet:
    def test_net_thresholds_exceed_gross_above_breakeven(self, seed_fund, default_dilution):
        ownership = compute_ownership_math(
            check_size=2.0, post_money=20.0, stage=VCStage.SEED,
            dilution=default_dilution, fund_profile=seed_fund, arr=0.5,
        )
        # Carry drag means the net thresholds sit above the gross ones
        assert ownership.fund_returner_1x_exit_net > ownership.fund_returner_1x_exit
        assert ownership.fund_returner_3x_exit_net > ownership.fund_returner_3x_exit
        assert ownership.fund_returner_5x_exit_net > ownership.fund_returner_5x_exit

    def test_net_threshold_formula(self, seed_fund, default_dilution):
        """D = (target×F − carry×check) / (1 − carry), divided by exit %."""
        ownership = compute_ownership_math(
            check_size=2.0, post_money=20.0, stage=VCStage.SEED,
            dilution=default_dilution, fund_profile=seed_fund, arr=0.5,
        )
        exit_pct = ownership.exit_ownership_pct
        expected_1x = ((100.0 - 0.20 * 2.0) / 0.80) / exit_pct
        assert ownership.fund_returner_1x_exit_net == pytest.approx(expected_1x, rel=1e-6)


# ---------------------------------------------------------------------------
# 17. Pro-rata (H1)
# ---------------------------------------------------------------------------

class TestProRataRebuild:
    def test_pass_leg_does_not_double_dilute(self, seed_deal, seed_fund, benchmarks):
        """H1 regression: the pass leg uses exit_ownership_pct as-is (it already
        contains all future dilution) — a_to_b is not re-applied."""
        ownership = compute_ownership_math(
            seed_deal.check_size, seed_deal.post_money_valuation,
            seed_deal.stage, seed_deal.dilution, seed_fund, seed_deal.arr,
        )
        result = compute_pro_rata(seed_deal, seed_fund, ownership, 60.0, 1.0, benchmarks)
        assert result.diluted_ownership_if_pass == pytest.approx(ownership.exit_ownership_pct)

    def test_maintain_leg_offsets_next_round_new_money(self, seed_deal, seed_fund, benchmarks):
        """Exercising offsets the next round's new-money dilution (pool refresh
        still applies)."""
        ownership = compute_ownership_math(
            seed_deal.check_size, seed_deal.post_money_valuation,
            seed_deal.stage, seed_deal.dilution, seed_fund, seed_deal.arr,
        )
        result = compute_pro_rata(seed_deal, seed_fund, ownership, 60.0, 1.0, benchmarks)
        round_only = seed_deal.dilution.seed_to_a  # first future round, ex-pool
        expected = ownership.exit_ownership_pct / (1 - round_only)
        assert result.maintained_ownership_pct == pytest.approx(expected, rel=1e-6)

    def test_exit_evs_reuse_scenario_engine(self, seed_deal, seed_fund, benchmarks):
        """H1: no hardcoded 2/7/15× multiples — EVs come from compute_scenarios."""
        ownership = compute_ownership_math(
            seed_deal.check_size, seed_deal.post_money_valuation,
            seed_deal.stage, seed_deal.dilution, seed_fund, seed_deal.arr,
        )
        bear, base, bull = compute_scenarios(
            seed_deal, seed_fund, ownership.exit_ownership_pct, benchmarks,
        )
        result = compute_pro_rata(seed_deal, seed_fund, ownership, 60.0, 1.0, benchmarks)
        evs = [s.exit_enterprise_value for s in result.exercise_scenarios]
        assert evs == pytest.approx([bear.exit_enterprise_value,
                                     base.exit_enterprise_value,
                                     bull.exit_enterprise_value])
        probs = [s.probability for s in result.exercise_scenarios]
        assert sum(probs) == pytest.approx(1.0)

    def test_net_metrics_are_carry_consistent(self, seed_deal, seed_fund, benchmarks):
        """H1: net proceeds/MOIC come from _carry_adj_proceeds, not flat
        moic×(1−carry) / irr×0.85 haircuts."""
        ownership = compute_ownership_math(
            seed_deal.check_size, seed_deal.post_money_valuation,
            seed_deal.stage, seed_deal.dilution, seed_fund, seed_deal.arr,
        )
        result = compute_pro_rata(seed_deal, seed_fund, ownership, 60.0, 1.0, benchmarks)
        for sc in result.exercise_scenarios + result.pass_scenarios:
            assert sc.net_proceeds_to_fund <= sc.gross_proceeds_to_fund + 1e-9
            if sc.gross_proceeds_to_fund > 0:
                # net MOIC must equal net proceeds / cost, not a flat haircut
                cost = sc.gross_proceeds_to_fund / sc.gross_moic
                assert sc.net_moic == pytest.approx(sc.net_proceeds_to_fund / cost, rel=1e-6)

    def test_decision_rule_incremental_vs_check(self, seed_deal, seed_fund, benchmarks):
        """Exercise iff expected incremental proceeds > pro-rata check."""
        ownership = compute_ownership_math(
            seed_deal.check_size, seed_deal.post_money_valuation,
            seed_deal.stage, seed_deal.dilution, seed_fund, seed_deal.arr,
        )
        result = compute_pro_rata(seed_deal, seed_fund, ownership, 60.0, 1.0, benchmarks)
        incremental = result.expected_value_exercise - result.expected_value_pass
        if incremental > 1.0:
            assert result.recommendation == "exercise"
        elif incremental > 0:
            assert result.recommendation == "partial"
        else:
            assert result.recommendation == "pass"


# ---------------------------------------------------------------------------
# 18. Defaults sync (M9) and orchestrator notes (M1/M8)
# ---------------------------------------------------------------------------

class TestDefaultsAndNotes:
    def test_dilution_defaults_match_carta_fy2025(self):
        """M9: defaults synced to the refreshed benchmark medians."""
        d = DilutionAssumptions()
        assert d.pre_seed_to_seed == pytest.approx(0.195)   # dilution at Seed
        assert d.seed_to_a == pytest.approx(0.185)          # dilution at Series A
        assert d.a_to_b == pytest.approx(0.13)              # dilution at Series B
        assert d.b_to_c == pytest.approx(0.11)              # dilution at Series C
        assert d.c_to_ipo == pytest.approx(0.12)            # IPO kept at 12%

    def test_expected_irr_note_present(self, seed_deal, seed_fund):
        """M8: expected_irr is labeled as the IRR of expected proceeds."""
        output = run_vc_deal_evaluation(seed_deal, seed_fund)
        assert any("expected_irr" in n for n in output.computation_notes)

    def test_waterfall_reconciliation_note(self, deal_with_liquidation_stack, seed_fund):
        """M1: waterfall vs scenario proceeds reconciled at the base exit EV."""
        output = run_vc_deal_evaluation(deal_with_liquidation_stack, seed_fund)
        assert output.waterfall is not None
        assert any("waterfall" in n.lower() for n in output.computation_notes)
        assert any("waterfall" in n.lower() or "scenario" in n.lower()
                   for n in output.waterfall.notes)

    def test_expected_value_includes_failure_mass(self, seed_deal, seed_fund):
        """C5(b): expected value is dragged down by the write-off branch —
        it must sit below base-case proceeds."""
        output = run_vc_deal_evaluation(seed_deal, seed_fund)
        assert output.bear_scenario.gross_proceeds_to_fund == pytest.approx(0.0)
        assert output.expected_value < output.base_scenario.gross_proceeds_to_fund
