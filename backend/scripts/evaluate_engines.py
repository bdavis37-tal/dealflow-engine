"""Deterministic synthetic decision suite; never evidence of market accuracy."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

from app.engine.financial_engine import run_deal
from app.engine.models import DealInput
from app.engine.startup_engine import run_startup_valuation
from app.engine.startup_models import StartupInput
from app.engine.vc_return_engine import run_vc_deal_evaluation
from app.engine.vc_fund_models import VCDealInput, FundProfile

ROOT = Path(__file__).resolve().parents[1]


def cases():
    fixtures = sorted((ROOT / 'tests/fixtures').glob('*.json'))
    ma = [json.loads(p.read_text()) for p in fixtures if not p.name.startswith('golden')]
    for i in range(12):
        deal = copy.deepcopy(ma[i % len(ma)]['input'])
        if i >= len(ma):
            deal['target']['acquisition_price'] *= 1.5
        yield f'ma-{i:02}', 'ma', deal
    for i, vertical in enumerate(['b2b_saas', 'defense_tech', 'deep_tech_hardware', 'biotech_pharma']):
        for j, arr in enumerate([0, 0.2, 2]):
            inp = dict(company_name=f'Synthetic {vertical} {arr}',
                       market=dict(tam_usd_billions=5, sam_usd_millions=500),
                       fundraise=dict(stage='seed', vertical=vertical, raise_amount=2),
                       traction=dict(has_revenue=arr > 0, annual_recurring_revenue=arr))
            yield f'startup-{i*3+j:02}', 'startup', inp
            yield f'vc-{i*3+j:02}', 'vc', dict(company_name=inp['company_name'], vertical=vertical,
                      stage='seed', post_money_valuation=20, check_size=2, arr=arr)


def evaluate():
    results = []
    for case_id, engine, inp in cases():
        if engine == 'ma':
            out = run_deal(DealInput.model_validate(inp), include_sensitivity=False)
            value, verdict = out.pro_forma_income_statement[0].pro_forma_eps, out.deal_verdict.value
        elif engine == 'startup':
            out = run_startup_valuation(StartupInput.model_validate(inp))
            value, verdict = out.blended_valuation, out.verdict.value
        else:
            out = run_vc_deal_evaluation(VCDealInput.model_validate(inp), FundProfile(fund_name='Synthetic', fund_size=100))
            value, verdict = out.expected_moic, out.quick_screen.recommendation
        evidence = getattr(out, 'evidence', None)
        results.append(dict(id=case_id, engine=engine, input=inp, value=value, verdict=verdict,
                            evidence=evidence.model_dump(mode='json') if evidence else None))
    return dict(kind='synthetic_mechanics_only', cases=results,
                data_hashes={p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                             for p in sorted((ROOT / 'app/data').glob('*.json'))})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--baseline')
    args = parser.parse_args()
    report = evaluate()
    if args.baseline:
        old = {c['id']: c for c in json.loads(Path(args.baseline).read_text())['cases']}
        report['material_changes'] = []
        for case in report['cases']:
            previous = old[case['id']]
            delta = ((case['value'] - previous['value']) / abs(previous['value'])
                     if case['value'] is not None and previous['value'] else None)
            if case['verdict'] != previous['verdict'] or delta is None or abs(delta) > .1:
                report['material_changes'].append(dict(id=case['id'], before=previous['value'],
                    after=case['value'], relative_change=delta, verdict_before=previous['verdict'],
                    verdict_after=case['verdict']))
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    print(f'{len(report["cases"])} synthetic cases written to {path}')
