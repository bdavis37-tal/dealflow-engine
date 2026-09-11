import type { VCDealInput, LiquidationPreference } from '../../types/vc'

export default function ExitAssumptions({ deal, onUpdate }: {
  deal: Partial<VCDealInput>; onUpdate: (value: Partial<VCDealInput>) => void
}) {
  const rounds = ['seed', 'series_a', 'series_b', 'series_c', 'ipo']
  const currentIndex = rounds.indexOf(deal.stage ?? 'seed')
  const options = deal.stage === 'growth' ? [] : rounds.filter((_, i) => i > currentIndex)
  type Label = 'Bear' | 'Base' | 'Bull'
  type Assumption = NonNullable<VCDealInput['scenario_assumptions']>[Label]
  const updateScenario = (label: Label, updates: Assumption) => onUpdate({scenario_assumptions: {
    ...deal.scenario_assumptions, [label]: {...deal.scenario_assumptions?.[label], ...updates},
  }})
  const updateClass = (label: Label, index: number, updates: Partial<LiquidationPreference>) => {
    const stack = deal.scenario_assumptions?.[label]?.exit_cap_table ?? []
    updateScenario(label, {exit_cap_table: stack.map((row, i) => i === index ? {...row, ...updates} : row)})
  }
  return <div className="my-5 rounded-xl border border-slate-700 p-4 space-y-4">
    <h3 className="font-medium text-slate-200">Exit assumptions</h3>
    <p className="text-xs text-slate-400">Acquisition before another round is the default. Select only the financing rounds expected before exit. Probabilities remain model assumptions.</p>
    <div className="flex flex-wrap gap-4">{options.map(round => <label key={round} className="text-sm text-slate-300">
      <input type="checkbox" checked={deal.future_rounds?.includes(round) ?? false} onChange={e => onUpdate({
        future_rounds: rounds.filter(r => r === round ? e.target.checked : deal.future_rounds?.includes(r)),
      })} /> {round.replace(/_/g, ' ')}
    </label>)}</div>
    <div className="grid gap-3 md:grid-cols-3">{(['Bear', 'Base', 'Bull'] as const).map(label => <label key={label} className="text-sm text-slate-300">
      {label} exit equity value ($M, optional)
      <input aria-label={`${label} exit equity value`} type="number" min="0" step="1" className="mt-1 w-full rounded bg-slate-800 border border-slate-600 p-2" value={deal.scenario_assumptions?.[label]?.exit_equity_value ?? ''}
        onChange={e => onUpdate({scenario_assumptions: {...deal.scenario_assumptions, [label]: {
          ...deal.scenario_assumptions?.[label], exit_equity_value: e.target.value === '' ? undefined : Number(e.target.value),
        }}})} />
    </label>)}</div>
    <p className="text-xs text-slate-400">No revenue: enter Base and Bull values to evaluate returns. Bear defaults to shutdown. Explicit values are illustrative scenarios, not forecasts.</p>
    <details className="text-sm text-slate-300">
      <summary className="cursor-pointer">Scenario timing, financing and exit cap tables</summary>
      {(['Bear', 'Base', 'Bull'] as const).map(label => {
        const scenario = deal.scenario_assumptions?.[label]
        return <fieldset key={label} className="mt-4 border border-slate-700 rounded p-3 space-y-3">
          <legend className="px-2">{label}</legend>
          <label>Exit year <input aria-label={`${label} exit year`} type="number" min="1" max="20" className="ml-2 w-20 bg-slate-800 p-1" value={scenario?.exit_year ?? ''} placeholder={String(deal.expected_exit_years ?? 7)} onChange={e => updateScenario(label, {exit_year: e.target.value === '' ? undefined : Number(e.target.value)})} /></label>
          <label className="block">Financing path <select aria-label={`${label} financing path`} className="ml-2 bg-slate-800 p-1" value={scenario?.future_rounds === undefined ? 'inherit' : scenario.future_rounds.length === 0 ? 'none' : 'custom'} onChange={e => updateScenario(label, {future_rounds: e.target.value === 'inherit' ? undefined : e.target.value === 'none' ? [] : [...(deal.future_rounds ?? [])]})}>
            <option value="inherit">Use deal path</option><option value="none">Exit before another round</option><option value="custom">Choose rounds below</option>
          </select></label>
          {scenario?.future_rounds !== undefined && <div className="flex flex-wrap gap-3">{options.map(round => <label key={round}><input type="checkbox" checked={scenario.future_rounds?.includes(round) ?? false} onChange={e => updateScenario(label, {future_rounds: options.filter(r => r === round ? e.target.checked : scenario.future_rounds?.includes(r))})} /> {round.replace(/_/g, ' ')}</label>)}</div>}
          {!!deal.liquidation_stack?.length && <>
            <p className="text-xs text-slate-400">With further financing, provide the fully diluted exit capitalization. Include new preferred classes; percentages must total 100% with common.</p>
            {!scenario?.exit_cap_table ? <button type="button" className="text-blue-300 underline" onClick={() => updateScenario(label, {exit_cap_table: deal.liquidation_stack?.map(p => ({...p})), exit_common_pct: deal.common_shares_pct ?? .3})}>Start projected cap table from current classes</button> : <>
              <label className="block">Common at exit (%) <input aria-label={`${label} common at exit`} type="number" min="0" max="100" className="ml-2 w-24 bg-slate-800 p-1" value={(scenario.exit_common_pct ?? 0)*100} onChange={e => updateScenario(label, {exit_common_pct: Number(e.target.value)/100})} /></label>
              {scenario.exit_cap_table.map((row, i) => <div key={i} className="grid grid-cols-2 md:grid-cols-4 gap-2 border-t border-slate-700 pt-2">
                <label>Class <input aria-label={`${label} class ${i+1}`} className="w-full bg-slate-800 p-1" value={row.share_class} onChange={e => updateClass(label, i, {share_class:e.target.value})} /></label>
                <label>Invested ($M) <input type="number" min="0.001" step="0.1" className="w-full bg-slate-800 p-1" value={row.invested_amount} onChange={e => updateClass(label, i, {invested_amount:Number(e.target.value)})} /></label>
                <label>Ownership (%) <input type="number" min="0" max="100" className="w-full bg-slate-800 p-1" value={row.ownership_pct == null ? '' : row.ownership_pct*100} onChange={e => updateClass(label, i, {ownership_pct:e.target.value === '' ? undefined : Number(e.target.value)/100})} /></label>
                <label>Preference (x) <input type="number" min="0.5" max="3" step="0.5" className="w-full bg-slate-800 p-1" value={row.preference_multiple} onChange={e => updateClass(label, i, {preference_multiple:Number(e.target.value)})} /></label>
                <label>Priority (1 first) <input type="number" min="1" className="w-full bg-slate-800 p-1" value={row.seniority} onChange={e => updateClass(label, i, {seniority:Number(e.target.value)})} /></label>
                <p className="text-xs text-slate-400 self-center">{row.preference_type.replace(/_/g, ' ')}</p>
                <button type="button" className="text-rose-300" onClick={() => updateScenario(label, {exit_cap_table:scenario.exit_cap_table?.filter((_, j) => j !== i)})}>Remove class</button>
              </div>)}
              <button type="button" className="text-blue-300 underline" onClick={() => updateScenario(label, {exit_cap_table:[...(scenario.exit_cap_table ?? []), {share_class:'New financing', invested_amount:1, ownership_pct:0, preference_multiple:1, preference_type:'non_participating', anti_dilution:'none', seniority:1}]})}>Add financing class</button>
            </>}
          </>}
        </fieldset>
      })}
    </details>
    <p className="text-xs text-slate-400">Dilution defaults: {deal.dilution_source === 'custom' ? 'Your assumptions' : 'Selected benchmark release'} · <button type="button" className="text-blue-300 underline" onClick={() => onUpdate({dilution_source:'benchmark'})}>Use benchmark defaults</button></p>
    <label className="block text-sm text-slate-300">Net debt at exit ($M; negative for net cash)
      <input aria-label="Net debt at exit" type="number" className="ml-3 rounded bg-slate-800 border border-slate-600 p-2" value={deal.exit_net_debt ?? 0} onChange={e => onUpdate({exit_net_debt:Number(e.target.value)})} />
    </label>
    {!!deal.liquidation_stack?.length && <label className="block text-sm text-slate-300">Investor share class
      <select className="ml-3 bg-slate-800 p-2" value={deal.investor_share_class ?? ''} onChange={e => onUpdate({investor_share_class:e.target.value || undefined})}>
        <option value="">Choose class</option>{deal.liquidation_stack.map(p => <option key={p.share_class}>{p.share_class}</option>)}
      </select>
    </label>}
  </div>
}
