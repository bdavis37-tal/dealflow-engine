"""Evaluate frozen out-of-sample predictions; never manufacture market labels.

Input contract is documented in docs/BENCHMARKS.md. Valuation targets and
binary horizon-resolved outcomes are scored separately, by cohort and basis.
"""
import argparse
from datetime import date
import json
import math
from pathlib import Path
from statistics import median


def evaluate(rows, split_date):
    split = date.fromisoformat(split_date)
    seen, companies = set(), {'calibration': set(), 'holdout': set()}
    groups = {}
    for row in rows:
        key = (row['company_id'], row['event_id'], row['target'])
        if key in seen:
            raise ValueError('Duplicate company/event/target')
        seen.add(key)
        cutoff = date.fromisoformat(row['feature_cutoff'])
        predicted = date.fromisoformat(row['prediction_date'])
        outcome = date.fromisoformat(row['outcome_date'])
        benchmark_date = date.fromisoformat(row['benchmark_available_date'])
        if not (benchmark_date <= cutoff <= predicted < outcome):
            raise ValueError('Look-ahead leakage: evidence/features/prediction must precede outcome')
        if not row.get('source_url') or not row.get('source_locator') or not row.get('prediction_artifact_hash'):
            raise ValueError('Outcome source and frozen prediction artifact hash are required')
        partition = 'calibration' if outcome < split else 'holdout'
        companies[partition].add(row['company_id'])
        group = (partition, row['cohort'], row['target'], row['basis'])
        groups.setdefault(group, []).append(row)
    if companies['calibration'] & companies['holdout']:
        raise ValueError('Company leakage across calibration and holdout')
    metrics = []
    for (partition, cohort, target, basis), sample in groups.items():
        result = dict(partition=partition, cohort=cohort, target=target, basis=basis, n=len(sample))
        if target == 'valuation':
            for row in sample:
                if min(row['actual'], row['prediction'], row['matched_median']) <= 0:
                    raise ValueError('Log valuation error requires positive values')
                if not 0 < row['range_low'] <= row['range_high']:
                    raise ValueError('Invalid valuation interval')
            result.update(median_absolute_log_error=median(abs(math.log(r['prediction']/r['actual'])) for r in sample),
                matched_median_log_error=median(abs(math.log(r['matched_median']/r['actual'])) for r in sample),
                interval_coverage=sum(r['range_low'] <= r['actual'] <= r['range_high'] for r in sample)/len(sample),
                median_relative_width=median((r['range_high']-r['range_low'])/r['actual'] for r in sample))
        elif target == 'binary_outcome':
            for row in sample:
                if row['actual'] not in (0, 1) or not 0 <= row['prediction'] <= 1 or not row.get('horizon_months') or not row.get('resolved'):
                    raise ValueError('Probability evaluation requires resolved, horizon-defined binary outcomes')
            if len({r['horizon_months'] for r in sample}) != 1:
                raise ValueError('Do not mix probability horizons within a cohort')
            result.update(brier_score=sum((r['prediction']-r['actual'])**2 for r in sample)/len(sample),
                          mean_probability=sum(r['prediction'] for r in sample)/len(sample),
                          observed_rate=sum(r['actual'] for r in sample)/len(sample))
        else:
            raise ValueError('Unsupported empirical target')
        result['interpretation'] = 'Provisional; assess cohort coverage and sample size before calibration'
        metrics.append(result)
    return dict(status='not_evaluated' if not rows else 'provisional', observation_count=len(rows), metrics=metrics,
                limitations=['Synthetic fixtures are excluded. Empty cohorts do not establish accuracy or calibrated probabilities.'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--split-date', required=True)
    args = parser.parse_args()
    report = evaluate(json.loads(Path(args.input).read_text(encoding='utf-8')), args.split_date)
    Path(args.output).write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(f"{report['status']}: {report['observation_count']} empirical observations")
