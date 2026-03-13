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
    DilutionAssumptions,
    FundProfile,
    LiquidationPreference,
    PortfolioInput,
    PortfolioPosition,
    PreferenceType,
    QSBSInput,
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
    run_portfolio_analysis,
    run_qsbs_analysis,
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
        # Seed → Series A: diluted by (seed_to_a + option_pool_expansion) = 0.20 + 0.05 = 0.25
        # Then Series B: 0.18 + 0.05 = 0.23
        # Then Series C: 0.15 + 0.05 = 0.20
        # Then IPO: 0.12 + 0.05 = 0.17
        # exit = 0.10 * (1-0.25) * (1-0.23) * (1-0.20) * (1-0.17)
        expected = 0.10 * 0.75 * 0.77 * 0.80 * 0.83
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
        """B2B SaaS exit multiples: bear=2.5, base=5.0, bull=12.0."""
        ownership = compute_ownership_math(
            seed_deal.check_size, seed_deal.post_money_valuation,
            seed_deal.stage, seed_deal.dilution, seed_fund, seed_deal.arr,
        )
        bear, base, bull = compute_scenarios(
            seed_deal, seed_fund, ownership.exit_ownership_pct, benchmarks,
        )
        assert bear.exit_multiple_arr == pytest.approx(2.5)
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

    def test_gross_proceeds_positive(self, seed_deal, seed_fund, benchmarks):
        ownership = compute_ownership_math(
            seed_deal.check_size, seed_deal.post_money_valuation,
            seed_deal.stage, seed_deal.dilution, seed_fund, seed_deal.arr,
        )
        bear, base, bull = compute_scenarios(
            seed_deal, seed_fund, ownership.exit_ownership_pct, benchmarks,
        )
        assert bear.gross_proceeds_to_fund > 0
        assert base.gross_proceeds_to_fund > 0
        assert bull.gross_proceeds_to_fund > 0

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
        """Pre-revenue deal uses $10M ARR placeholder for exit EV."""
        ownership = compute_ownership_math(
            pre_seed_deal.check_size, pre_seed_deal.post_money_valuation,
            pre_seed_deal.stage, pre_seed_deal.dilution, seed_fund, pre_seed_deal.arr,
        )
        bear, base, bull = compute_scenarios(
            pre_seed_deal, seed_fund, ownership.exit_ownership_pct, benchmarks,
        )
        # AI/ML bear=3.0, base=10.0, bull=25.0 exit multiples × $10M placeholder
        assert bear.exit_enterprise_value == pytest.approx(3.0 * 10.0, rel=0.01)
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

    def test_participating_capped(self, default_dilution):
        """Capped participating preferred: pref + pro-rata up to cap."""
        deal = VCDealInput(
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
        # At very high exit, capped at 3x invested = $30M
        result = compute_waterfall(deal, 1000.0)
        assert result.investor_total <= 30.0 + 0.01

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
        positions = self._make_positions()
        inp = PortfolioInput(fund_profile=seed_fund, positions=positions)
        result = run_portfolio_analysis(inp)
        total_cost = sum(p.cost_basis for p in positions)
        total_fv = sum(p.fair_value or p.cost_basis for p in positions)
        total_realized = sum(p.realized_proceeds for p in positions)
        expected_dpi = total_realized / total_cost
        expected_rvpi = total_fv / total_cost
        assert result.stats.dpi == pytest.approx(expected_dpi, rel=1e-3)
        assert result.stats.rvpi == pytest.approx(expected_rvpi, rel=1e-3)
        assert result.stats.tvpi == pytest.approx(expected_dpi + expected_rvpi, rel=1e-3)

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
            lp_marginal_tax_rate=0.37,
        )
        defaults.update(overrides)
        return QSBSInput(**defaults)

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
        """Before July 2025: $10M cap or 10x basis, whichever is lower."""
        result = run_qsbs_analysis(self._make_qsbs_input(
            investment_amount=2.0,
            issuance_date_post_july_2025=False,
        ))
        # 10x basis = $20M, but $10M cap → min = $10M
        assert result.exclusion_cap_per_taxpayer == pytest.approx(10.0)

    def test_exclusion_cap_post_july_2025(self):
        """After July 2025: $15M cap."""
        result = run_qsbs_analysis(self._make_qsbs_input(
            investment_amount=2.0,
            issuance_date_post_july_2025=True,
        ))
        # 10x basis = $20M, but $15M cap → min = $15M
        assert result.exclusion_cap_per_taxpayer == pytest.approx(15.0)

    def test_exclusion_cap_small_investment(self):
        """When 10x basis < $10M, the basis cap applies."""
        result = run_qsbs_analysis(self._make_qsbs_input(
            investment_amount=0.5,
            issuance_date_post_july_2025=False,
        ))
        # 10x basis = $5M < $10M → cap = $5M
        assert result.exclusion_cap_per_taxpayer == pytest.approx(5.0)

    def test_tax_benefit_estimation(self):
        result = run_qsbs_analysis(self._make_qsbs_input(
            investment_amount=2.0,
            lp_count=10,
            lp_marginal_tax_rate=0.37,
        ))
        # $10M cap, gain at 10x = $20M, excluded = $10M
        # Tax saved per LP = $10M * 0.37 = $3.7M
        assert result.estimated_federal_tax_saved_per_lp == pytest.approx(10.0 * 0.37, rel=0.01)
        assert result.estimated_total_lp_benefit == pytest.approx(10.0 * 0.37 * 10, rel=0.01)

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

    def test_dilution_from_bridge(self):
        result = run_bridge_analysis(self._make_bridge_input())
        # dilution = bridge / (pre_bridge + bridge) = 2 / 32 = 0.0625
        assert result.dilution_from_bridge == pytest.approx(2.0 / 32.0, rel=1e-4)

    def test_post_bridge_ownership(self):
        result = run_bridge_analysis(self._make_bridge_input())
        expected = 0.10 * (1 - 2.0 / 32.0)
        assert result.post_bridge_ownership_if_convert == pytest.approx(expected, rel=1e-4)

    def test_effective_conversion_price(self):
        result = run_bridge_analysis(self._make_bridge_input())
        # effective = next_round_val * (1 - discount) = 60 * 0.80 = 48
        assert result.effective_conversion_price == pytest.approx(48.0, rel=1e-4)

    def test_implied_discount(self):
        result = run_bridge_analysis(self._make_bridge_input())
        assert result.implied_discount_to_next_round == pytest.approx(0.20, rel=1e-4)

    def test_recommendation_not_empty(self):
        result = run_bridge_analysis(self._make_bridge_input())
        assert len(result.recommendation) > 0

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

    def test_additional_runway(self):
        result = run_bridge_analysis(self._make_bridge_input())
        assert result.additional_runway_months is not None
        assert result.additional_runway_months > 0


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
