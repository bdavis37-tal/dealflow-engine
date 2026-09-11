import importlib.util
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location('empirical', Path(__file__).parents[1] / 'scripts/evaluate_empirical.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def observation(**overrides):
    return dict(company_id='test', event_id='round', target='valuation', basis='pre_money', cohort='test',
                feature_cutoff='2026-01-01', prediction_date='2026-01-02', benchmark_available_date='2025-12-01',
                outcome_date='2026-08-01', source_url='https://example.com/test-only', source_locator='Synthetic unit test',
                prediction_artifact_hash='test-only', actual=20, prediction=20, matched_median=10,
                range_low=15, range_high=25, **overrides)


def test_empty_empirical_dataset_cannot_claim_accuracy():
    assert module.evaluate([], '2026-07-01')['status'] == 'not_evaluated'


def test_independent_error_and_interval_arithmetic():
    result = module.evaluate([observation()], '2026-07-01')['metrics'][0]
    assert result['median_absolute_log_error'] == 0
    assert result['interval_coverage'] == 1
    assert result['median_relative_width'] == .5
    assert result['matched_median_log_error'] == pytest.approx(.69314718)


def test_lookahead_is_rejected():
    row = observation()
    row['benchmark_available_date'] = '2026-09-01'
    with pytest.raises(ValueError, match='Look-ahead'):
        module.evaluate([row], '2026-07-01')


def test_duplicate_events_are_rejected():
    with pytest.raises(ValueError, match='Duplicate'):
        module.evaluate([observation(), observation()], '2026-07-01')


def test_companies_cannot_leak_across_split():
    earlier = observation()
    earlier.update(event_id='earlier', outcome_date='2026-02-01')
    with pytest.raises(ValueError, match='Company leakage'):
        module.evaluate([earlier, observation()], '2026-07-01')


def test_unresolved_probabilities_are_rejected():
    row = observation()
    row.update(target='binary_outcome', actual=0, prediction=.3, horizon_months=24, resolved=False)
    with pytest.raises(ValueError, match='resolved'):
        module.evaluate([row], '2026-07-01')
