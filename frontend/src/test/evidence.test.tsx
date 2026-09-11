import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, cleanup } from '@testing-library/react'
import LZString from 'lz-string'
import { decodeState, encodeState, type VCInputState } from '../lib/shareUtils'
import { DEFAULT_FUND_PROFILE } from '../types/vc'
import EvidencePanel from '../components/shared/EvidencePanel'
import ExitAssumptions from '../components/vc/ExitAssumptions'
import { computeModelPlacement } from '../components/output/startup/placementUtils'

describe('evidence and replay', () => {
  it('migrates old VC inputs without replacing custom dilution', () => {
    const old = {v:1, module:'vc', state:{fund:DEFAULT_FUND_PROFILE, deal:{stage:'seed', dilution:{seed_to_a:.31}}}}
    const result = decodeState(LZString.compressToEncodedURIComponent(JSON.stringify(old)))
    const state = result!.state as VCInputState
    expect(state.deal.benchmark_version).toBe('2026-07-legacy')
    expect(state.deal.dilution_source).toBe('custom')
    expect(state.deal.dilution?.seed_to_a).toBe(.31)
    expect(state.deal.future_rounds).toEqual(['series_a','series_b','series_c','ipo'])
  })

  it('shares the actual scenario inputs and benchmark identity', () => {
    const state: VCInputState = {fund:DEFAULT_FUND_PROFILE, deal:{company_name:'Test', benchmark_version:'2026-09-11', future_rounds:[], scenario_assumptions:{Base:{exit_equity_value:100, exit_year:2}}}}
    const evidence = {engine_version:'2.0.0', dataset_version:'2026-09-11', dataset_hash:'hash', input_fingerprint:'input', records:[], observed_count:0, assumed_count:0, limitations:[]}
    const decoded = decodeState(encodeState('vc', state, evidence))!
    expect(decoded.state).toEqual(state)
    expect(decoded.provenance?.dataset_hash).toBe('hash')
    expect(decoded.provenance?.record_ids).toEqual([])
  })

  it('never infers an observed percentile from assumed anchors', () => {
    expect(computeModelPlacement(15, 10, 20, 30, 40).approx_percentile).toBeNull()
  })

  it('shows provenance, assumptions and a direct source together', () => {
    render(<EvidencePanel evidence={{engine_version:'2.0.0',dataset_version:'2026-09-11',dataset_hash:'hash',input_fingerprint:'input',observed_count:1,assumed_count:0,limitations:['Uncalibrated probabilities'],records:[{id:'source',metric:'financing_dilution',value:.18,unit:'fraction',statistic:'median',basis:'ownership',status:'observed',source_url:'https://carta.com/data/linkedin-vc-fundraising-benchmarks-2026/',source_locator:'Software',observation_period:'6 months before July 10, 2026',freshness:'current',limitations:[]}]}} />)
    fireEvent.click(screen.getByText(/Assumptions and sources/))
    expect(screen.getByText('Uncalibrated probabilities')).toBeInTheDocument()
    expect(screen.getByRole('link', {name:/Source/})).toHaveAttribute('href','https://carta.com/data/linkedin-vc-fundraising-benchmarks-2026/')
    cleanup()
  })

  it('preserves one scenario when another is edited', () => {
    const update = vi.fn()
    render(<ExitAssumptions deal={{stage:'seed',scenario_assumptions:{Bull:{exit_equity_value:200}}}} onUpdate={update} />)
    fireEvent.change(screen.getByLabelText('Base exit equity value'), {target:{value:'100'}})
    expect(update).toHaveBeenCalledWith({scenario_assumptions:{Bull:{exit_equity_value:200},Base:{exit_equity_value:100}}})
    cleanup()
  })
})
