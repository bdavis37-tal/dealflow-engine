"""Separate earnings impact, valuation evidence, credit and strategic context."""
from .benchmark_registry import resolve


def comparison(deal):
    equity = deal.target.acquisition_price
    ev = equity + deal.target.total_debt - deal.target.cash_on_hand
    match = resolve('acquisition_ev_ebitda', 'ev', revenue_basis='ttm_adjusted_ebitda',
                    geography='north_america', size=ev)
    record = match['record']
    return dict(metric='EV / TTM adjusted EBITDA', entry_multiple=ev/deal.target.ebitda if deal.target.ebitda>0 else None,
                reference=record.model_dump(mode='json') if record else None,
                fallback_reason=match['fallback_reason'],
                limitations=['Reported EBITDA is used; confirm normalization to adjusted EBITDA.',
                             'Size-matched private-equity cohort is a cross-check, not a sector-specific strategic acquisition price.'])


def downside(deal):
    from .financial_engine import run_deal
    cases = []
    for label in ['Target EBITDA -20%', 'Synergy phase-in extended 1 year', 'Debt rate +200bp']:
        variant = deal.model_copy(deep=True)
        if label.startswith('Target'):
            variant.target.ebitda *= .8
            variant.target.net_income -= deal.target.ebitda*.2*(1-deal.target.tax_rate)
        elif label.startswith('Synergy'):
            for item in variant.synergies.cost_synergies + variant.synergies.revenue_synergies:
                item.phase_in_years += 1
        else:
            for tranche in variant.structure.debt_tranches:
                tranche.interest_rate += .02
            if not variant.structure.debt_tranches:
                continue  # No explicit debt-rate scenario to perturb.
        result = run_deal(variant, include_sensitivity=False)
        first = result.pro_forma_income_statement[0]
        cases.append(dict(label=label, year1_eps=first.pro_forma_eps,
                          year1_accretion=first.accretion_dilution_pct, verdict=result.deal_verdict.value))
    return cases
