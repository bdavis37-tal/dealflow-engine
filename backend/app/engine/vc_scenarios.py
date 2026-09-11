"""Explicit exit paths and preference-aware proceeds for the VC engine."""
from .vc_fund_models import VCDealInput, FundProfile, VCScenario, DilutionAssumptions
from .benchmark_registry import dilution_defaults


def effective_deal(deal: VCDealInput) -> VCDealInput:
    # Old callers that sent a dilution object authored an override, even if they
    # did not have the new source selector. Do not replace it during migration.
    custom = deal.dilution_source == 'custom' or ('dilution' in deal.model_fields_set and
                                                'dilution_source' not in deal.model_fields_set)
    if custom:
        return deal.model_copy(deep=True)
    return deal.model_copy(update={'dilution': DilutionAssumptions(**dilution_defaults(deal.vertical.value))}, deep=True)


def path_ownership(deal: VCDealInput, rounds: list[str]) -> tuple[float, list[dict]]:
    order = ['pre_seed', 'seed', 'series_a', 'series_b', 'series_c', 'ipo']
    entry = order.index(deal.stage.value) if deal.stage.value in order else 5
    if len(set(rounds)) != len(rounds) or rounds != sorted(rounds, key=order.index):
        raise ValueError('Future rounds must be unique and chronological')
    if any(order.index(r) <= entry for r in rounds):
        raise ValueError('Future rounds must follow the entry stage')
    mapping = dict(seed=deal.dilution.pre_seed_to_seed, series_a=deal.dilution.seed_to_a,
                   series_b=deal.dilution.a_to_b, series_c=deal.dilution.b_to_c, ipo=deal.dilution.c_to_ipo)
    ownership, stack = deal.check_size / deal.post_money_valuation, []
    for rnd in rounds:
        before = ownership
        # Distinct sequential ownership reductions, not additive percentages.
        ownership *= (1 - mapping[rnd]) * (1 - deal.dilution.option_pool_expansion)
        stack.append(dict(round=rnd, dilution_pct=1-ownership/before,
                          ownership_before=before, ownership_after=ownership))
    return ownership, stack


def build_path(label, probability, multiple, deal: VCDealInput, fund: FundProfile) -> VCScenario:
    from .vc_return_engine import _project_arr, _irr, _carry_adj_proceeds, compute_waterfall
    override = deal.scenario_assumptions.get(label)
    rounds = override.future_rounds if override and override.future_rounds is not None else deal.future_rounds
    if label == 'Bear' and not override:
        rounds = []
    ownership, _ = path_ownership(deal, rounds)
    years = override.exit_year if override and override.exit_year else deal.expected_exit_years
    notes = ['Scenario probabilities are model assumptions, not calibrated forecasts.']
    current = deal.arr if deal.arr > 0 else deal.revenue_ttm
    available, illustrative = True, bool(override)
    if override and override.exit_equity_value is not None:
        equity = override.exit_equity_value
        ev = equity + deal.exit_net_debt
        notes.append('User-specified distributable equity value; net debt is not deducted twice.')
    else:
        if override and override.exit_revenue is not None:
            revenue = override.exit_revenue
        elif label == 'Bear':
            revenue = current if deal.bear_exit_multiple_arr is not None else 0.0  # Explicit shutdown, not a revenue placeholder.
        elif current > 0:
            growth = deal.revenue_growth_rate * (1.3 if label == 'Bull' and deal.revenue_growth_rate > 0 else 1)
            revenue = _project_arr(current, growth, years)
        else:
            revenue, available = 0.0, False
            notes.append('Missing revenue: provide explicit exit revenue or distributable equity value.')
        ev = revenue * multiple
        equity = max(0, ev - deal.exit_net_debt)
    proceeds = equity * ownership
    cap_table = override.exit_cap_table if override and override.exit_cap_table is not None else deal.liquidation_stack
    common = override.exit_common_pct if override and override.exit_common_pct is not None else deal.common_shares_pct
    if cap_table and available:
        if rounds and not (override and override.exit_cap_table is not None and override.exit_common_pct is not None):
            available = False
            notes.append('Future financing with preferences requires an explicit projected exit cap table and common percentage.')
        elif not deal.investor_share_class:
            available = False
            notes.append('Select the investor share class to reconcile scenario proceeds.')
        elif any(p.ownership_pct is None for p in cap_table) or abs(common + sum(p.ownership_pct or 0 for p in cap_table)-1) > 1e-6:
            available = False
            notes.append('Provide fully diluted ownership totaling 100% across preferred and common at exit.')
        elif deal.investor_share_class not in [p.share_class for p in cap_table]:
            available = False
            notes.append('Investor share class is absent from the projected cap table.')
        else:
            projected = deal.model_copy(update=dict(liquidation_stack=cap_table, common_shares_pct=common))
            waterfall = compute_waterfall(projected, equity)
            investor_class = next(p for p in cap_table if p.share_class == deal.investor_share_class)
            fraction = deal.check_size / investor_class.invested_amount
            if fraction > 1:
                available = False
                notes.append('Investor check exceeds invested capital in the selected exit share class.')
            proceeds = waterfall.investor_total * fraction
            ownership = investor_class.ownership_pct * fraction
            notes.append('Investor owns the check-size fraction of the selected class; other investors in the class receive the balance.')
            notes.extend(waterfall.notes)
    if not available:
        proceeds = 0.0
    net = _carry_adj_proceeds(proceeds, deal.check_size, fund.carry_pct, fund.hurdle_rate, years)
    return VCScenario(label=label, probability=probability, exit_year=years, exit_multiple_arr=multiple,
        exit_enterprise_value=ev, exit_equity_value=equity, exit_ownership_pct=ownership,
        gross_proceeds_to_fund=proceeds, net_proceeds_to_fund=net,
        gross_moic=proceeds/deal.check_size, net_moic=net/deal.check_size,
        gross_irr=-1.0 if proceeds == 0 else _irr(deal.check_size, proceeds, years), net_irr=-1.0 if net == 0 else _irr(deal.check_size, net, years),
        fund_contribution_x=proceeds/fund.fund_size, available=available, illustrative=illustrative,
        outcome_description=('Insufficient inputs' if not available else
            'Illustrative user scenario' if illustrative else 'Shutdown / full loss' if label == 'Bear'
            else 'Modeled acquisition; only specified financing rounds dilute ownership'), notes=notes)
