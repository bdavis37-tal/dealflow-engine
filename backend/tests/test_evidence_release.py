"""Release protections: provenance, missing evidence, and independent cash math."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.engine.benchmark_registry import (
    BenchmarkRecord, CURRENT_VERSION, release, resolve,
)
from app.engine.financial_engine import run_deal
from app.engine.models import DealInput
from app.engine.startup_engine import run_startup_valuation
from app.engine.startup_models import StartupInput
from app.engine.vc_fund_models import FundProfile, VCDealInput
from app.engine.vc_return_engine import compute_waterfall, run_deal_comparison, run_vc_deal_evaluation
from app.main import app


def vc(**overrides):
    return VCDealInput.model_validate(dict(company_name='Evidence test', vertical='b2b_saas',
        stage='seed', post_money_valuation=20, check_size=2, arr=1, **overrides))


def fund():
    return FundProfile(fund_name='Test', fund_size=100)


def startup(**fundraise):
    return StartupInput.model_validate(dict(company_name='Test',
        market=dict(tam_usd_billions=5, sam_usd_millions=500),
        fundraise=dict(stage='pre_seed', vertical='b2b_saas', raise_amount=3, **fundraise)))


def ma():
    path = Path(__file__).parent / 'fixtures/simple_cash_deal.json'
    return DealInput.model_validate(json.loads(path.read_text(encoding='utf-8'))['input'])


def test_observation_requires_evidence_and_finite_values():
    with pytest.raises(ValidationError):
        BenchmarkRecord(id='bad', metric='price', value=2, statistic='median', unit='USD_millions', basis='ev', status='observed')
    with pytest.raises(ValidationError):
        BenchmarkRecord(id='bad', metric='price', value=float('nan'), statistic='median', unit='USD_millions', basis='ev')


@pytest.mark.parametrize('version', ['2026-07-legacy', CURRENT_VERSION])
def test_every_numeric_cell_is_bound_and_release_validates(version):
    snapshot = release(version)  # Hash, unique IDs, and binding values validated here.
    def walk(value, path):
        if isinstance(value, dict):
            for k, v in value.items():
                if not k.startswith('_'):
                    walk(v, path + [k])
        elif isinstance(value, list):
            for i, v in enumerate(value):
                walk(v, path + [str(i)])
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            assert '/'.join(path) in snapshot['bindings']
    for key, value in snapshot['datasets'].items():
        walk(value, [key])


def test_unknown_release_does_not_resolve_to_latest():
    with pytest.raises(ValueError):
        release('../../anything')


def test_projected_cap_table_rejects_duplicate_investor_classes():
    share_class = dict(share_class='Seed', invested_amount=2, ownership_pct=.1)
    with pytest.raises(ValidationError, match='Projected exit share class names must be unique'):
        vc(scenario_assumptions={'Base': dict(exit_equity_value=100,
            exit_cap_table=[share_class, share_class], exit_common_pct=.8)})


def test_software_observation_cannot_be_applied_to_hardware_or_other_stage():
    assert resolve('financing_dilution', 'ownership', stage='seed', business_model='hardware')['record'] is None
    assert resolve('financing_dilution', 'equity_value', stage='seed', business_model='software')['record'] is None
    assert resolve('financing_dilution', 'ownership', stage='growth', business_model='software')['record'] is None
    assert resolve('financing_dilution', 'ownership', stage='seed', business_model='software', as_of='2026-01-01')['record'] is None


@pytest.mark.parametrize('size,expected', [(20, 6.3), (60, 8.3), (300, 10.1), (30, None)])
def test_ma_size_cohort_and_sparse_gap(size, expected):
    match = resolve('acquisition_ev_ebitda', 'ev', revenue_basis='ttm_adjusted_ebitda', geography='north_america', size=size)
    assert (match['record'].value if match['record'] else None) == expected
    assert resolve('acquisition_ev_ebitda', 'ev', revenue_basis='arr', geography='north_america', size=size)['record'] is None


def test_versions_are_isolated_and_custom_dilution_survives():
    def evaluate(version):
        deal = vc(benchmark_version=version, future_rounds=['series_a'])
        return run_vc_deal_evaluation(deal, fund())
    versions = ['2026-07-legacy', CURRENT_VERSION] * 6
    with ThreadPoolExecutor(max_workers=4) as pool:
        outputs = list(pool.map(evaluate, versions))
    for version, out in zip(versions, outputs):
        assert out.evidence.dataset_version == version
        assert out.base_scenario.exit_ownership_pct == pytest.approx(.0815 if version.endswith('legacy') else .082)
        assert out.evidence.records
    custom = run_vc_deal_evaluation(vc(future_rounds=['series_a'], dilution={'seed_to_a': .30}, dilution_source='custom'), fund())
    assert custom.base_scenario.exit_ownership_pct == pytest.approx(.07)


def test_input_fingerprint_and_full_output_replay_are_stable():
    deal = vc()
    first = run_vc_deal_evaluation(deal, fund())
    second = run_vc_deal_evaluation(fund=fund(), deal=deal)
    assert first.model_dump() == second.model_dump()


def test_no_revenue_suppresses_expected_metrics_and_return_rank():
    deal = vc().model_copy(update={'arr': 0})
    out = run_vc_deal_evaluation(deal, fund())
    assert out.expected_moic is out.expected_irr is out.expected_value is None
    assert out.ic_memo.expected_value is None
    assert out.quick_screen.recommendation == 'insufficient_inputs'
    comparison = run_deal_comparison([(deal, fund()), (vc(), fund())])
    assert comparison.deals[0].rank_moic is None


def test_explicit_early_exit_has_no_implicit_financing_and_net_debt_is_deducted_once():
    deal = vc(scenario_assumptions={'Base': {'exit_equity_value': 100, 'exit_year': 2},
                                  'Bull': {'exit_equity_value': 200, 'exit_year': 4}}, exit_net_debt=20)
    out = run_vc_deal_evaluation(deal, fund())
    assert out.base_scenario.exit_enterprise_value == 120
    assert out.base_scenario.gross_proceeds_to_fund == 10
    assert out.base_scenario.exit_ownership_pct == .10
    assert out.base_scenario.illustrative
    npv = sum(s.probability*s.gross_proceeds_to_fund/(1+out.expected_irr)**s.exit_year
              for s in [out.bear_scenario, out.base_scenario, out.bull_scenario])
    assert npv == pytest.approx(2)


def test_declining_revenue_and_total_loss_are_represented():
    out = run_vc_deal_evaluation(vc(revenue_growth_rate=-.5), fund())
    assert out.base_scenario.exit_enterprise_value < out.base_scenario.exit_multiple_arr
    assert out.bear_scenario.gross_irr == -1


def test_round_path_validation():
    with pytest.raises(ValidationError):
        vc(future_rounds=['series_b', 'series_a'])
    with pytest.raises(ValidationError):
        vc(future_rounds=['seed'])


def test_selected_class_is_not_the_entire_fund_position():
    deal = vc(investor_share_class='Seed', common_shares_pct=.5, liquidation_stack=[
        dict(share_class='Seed', invested_amount=4, ownership_pct=.2),
        dict(share_class='Other', invested_amount=6, ownership_pct=.3)],
        scenario_assumptions={'Base': {'exit_equity_value': 100}, 'Bull': {'exit_equity_value': 200}})
    out = run_vc_deal_evaluation(deal, fund())
    # Fund invested 2 of the class's 4; class gets 20, fund gets 10.
    assert out.base_scenario.gross_proceeds_to_fund == pytest.approx(10)
    assert out.waterfall.investor_total == pytest.approx(10)
    assert out.waterfall.total_distributed == pytest.approx(100)
    assert out.base_scenario.exit_ownership_pct == pytest.approx(.10)


def test_equal_seniority_preferences_share_shortfall_proportionately():
    deal = vc(liquidation_stack=[dict(share_class='A', invested_amount=4, seniority=1, ownership_pct=.2),
                                dict(share_class='B', invested_amount=6, seniority=1, ownership_pct=.3)], common_shares_pct=.5)
    out = compute_waterfall(deal, 5)
    assert [c['gets'] for c in out.share_classes] == pytest.approx([2, 3])
    assert out.total_distributed == 5


def test_future_preferences_require_projected_cap_table():
    deal = vc(future_rounds=['series_a'], liquidation_stack=[dict(share_class='Seed', invested_amount=2, ownership_pct=.1)], common_shares_pct=.9, investor_share_class='Seed')
    out = run_vc_deal_evaluation(deal, fund())
    assert out.expected_moic is None
    assert out.waterfall is None
    assert any('projected exit cap table' in note for note in out.base_scenario.notes)


def test_startup_explicit_safe_cap_uses_compatible_observation():
    inp = startup(instrument='safe', safe_type='post_money', safe_valuation_cap=35)
    out = run_startup_valuation(inp)
    assert out.recommended_safe_cap == 35
    assert out.implied_dilution == pytest.approx(3/35, abs=.00005)
    assert any(r.metric == 'safe_cap' and r.value == 35 for r in out.evidence.records)


def test_startup_methods_reconcile_and_hardware_excludes_arr():
    inp = startup(business_model='hardware')
    inp.traction.annual_recurring_revenue = 2
    out = run_startup_valuation(inp)
    assert not next(m for m in out.method_results if m.method_name == 'arr_multiple').applicable
    assert sum(m.weighted_contribution for m in out.method_results) + out.blend_adjustment == pytest.approx(out.blended_valuation)
    assert out.verdict.value == 'not_assessed'
    assert out.recommended_safe_cap is None


def test_ai_parameters_are_traced_in_the_selected_release():
    inp = startup(is_ai_native=True, ai_native_score=1)
    out = run_startup_valuation(inp)
    assert any(r.id.startswith('legacy:ai/parameter_matrix') for r in out.evidence.records)
    assert all(r.status == 'assumed' for r in out.evidence.records if r.id.startswith('legacy:ai/'))


def test_ma_comparison_n_m_and_downside_are_independent_of_eps_verdict():
    deal = ma()
    deal.target.ebitda = -1
    out = run_deal(deal, include_sensitivity=False)
    assert out.valuation_comparison['entry_multiple'] is None
    assert 'EPS' in out.decision_basis


def test_api_defaults_and_evaluation_use_same_release():
    client = TestClient(app)
    response = client.get(f'/api/benchmarks/{CURRENT_VERSION}/vc-defaults?vertical=b2b_saas')
    assert response.status_code == 200
    assert response.json()['dilution']['seed_to_a'] == .18
    inp = vc(future_rounds=['series_a']).model_dump(mode='json', exclude_unset=True)
    response = client.post('/api/vc/evaluate', json={**inp, 'fund': fund().model_dump(mode='json')})
    assert response.status_code == 200
    assert response.json()['base_scenario']['exit_ownership_pct'] == pytest.approx(.082)
    assert response.json()['evidence']['dataset_hash'] == release()['hash']
