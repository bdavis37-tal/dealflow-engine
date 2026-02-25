import { describe, it, expect } from 'vitest'
import fc from 'fast-check'
import {
  encodeState,
  decodeState,
  parseShareHash,
  SCHEMA_VERSION,
  type MAInputState,
  type StartupInputState,
  type VCInputState,
} from '../lib/shareUtils'

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const maState: MAInputState = {
  mode: 'quick',
  acquirer: { company_name: 'Acme Corp', revenue: 500, ebitda: 100 },
  target: { company_name: 'Target Co', revenue: 50, ebitda: 10, acquisition_price: 200, is_ai_native: false },
  structure: { cash_percentage: 0.7, stock_percentage: 0.3, debt_percentage: 0, debt_tranches: [], transaction_fees_pct: 0.02, advisory_fees: 0 },
  ppa: { asset_writeup: 0, asset_writeup_useful_life: 15, identifiable_intangibles: 0, intangible_useful_life: 10 },
  synergies: { cost_synergies: [], revenue_synergies: [] },
}

const startupState: StartupInputState = {
  company_name: 'Rocketship AI',
  team: { founder_count: 2, prior_exits: 1, domain_experts: true, technical_cofounder: true, repeat_founder: false, tier1_background: false, notable_advisors: false },
  traction: { has_revenue: true, monthly_recurring_revenue: 0.05, annual_recurring_revenue: 0.6, mom_growth_rate: 0.12, net_revenue_retention: 1.1, gross_margin: 0.75, monthly_burn_rate: 0.08, cash_on_hand: 0.5, paying_customer_count: 12, logo_customer_count: 15, has_lois: false, gmv_monthly: 0 },
  product: { stage: 'paying_customers', has_patent_or_ip: false, proprietary_data_moat: true, open_source_traction: false, regulatory_clearance: false },
  market: { tam_usd_billions: 10, sam_usd_millions: 200, market_growth_rate: 0.25, competitive_moat: 'medium' },
  fundraise: { stage: 'seed', vertical: 'ai_enabled_saas', geography: 'bay_area', raise_amount: 3, instrument: 'safe', pre_money_valuation_ask: null, safe_discount: 0.2, has_mfn_clause: false, existing_safe_stack: 0, is_ai_native: true, ai_native_score: 0.75 },
  is_ai_native: true,
  ai_native_score: 0.75,
  ai_answers: [true, true, true, false],
}

const vcState: VCInputState = {
  fund: {
    fund_name: 'Apex Ventures I',
    fund_size: 100,
    vintage_year: 2024,
    management_fee_pct: 0.02,
    management_fee_years: 5,
    carry_pct: 0.20,
    hurdle_rate: 0.08,
    reserve_ratio: 0.40,
    target_initial_check_count: 25,
    target_ownership_pct: 0.10,
    recycling_pct: 0.05,
    deployment_period_years: 4,
  },
  deal: {
    company_name: 'DataCo',
    post_money_valuation: 20,
    check_size: 2,
    arr: 1.5,
    revenue_growth_rate: 2.0,
    gross_margin: 0.72,
  },
}

// ---------------------------------------------------------------------------
// parseShareHash
// ---------------------------------------------------------------------------

describe('parseShareHash', () => {
  it('returns encoded string from valid hash', () => {
    expect(parseShareHash('#share=abc123')).toBe('abc123')
  })

  it('returns null for empty string', () => {
    expect(parseShareHash('')).toBeNull()
  })

  it('returns null for non-share hash', () => {
    expect(parseShareHash('#other=abc')).toBeNull()
    expect(parseShareHash('#share=')).toBeNull()
  })

  it('returns null for bare hash', () => {
    expect(parseShareHash('#')).toBeNull()
  })

  it('preserves encoded content verbatim', () => {
    const encoded = encodeState('ma', maState)
    expect(parseShareHash(`#share=${encoded}`)).toBe(encoded)
  })
})

// ---------------------------------------------------------------------------
// encodeState / decodeState — round-trip fidelity
// ---------------------------------------------------------------------------

describe('round-trip fidelity', () => {
  it('M&A state survives encode → decode', () => {
    const encoded = encodeState('ma', maState)
    const result = decodeState(encoded)
    expect(result).not.toBeNull()
    expect(result!.module).toBe('ma')
    expect(result!.v).toBe(SCHEMA_VERSION)
    expect(result!.state).toEqual(maState)
  })

  it('Startup state survives encode → decode', () => {
    const encoded = encodeState('startup', startupState)
    const result = decodeState(encoded)
    expect(result).not.toBeNull()
    expect(result!.module).toBe('startup')
    expect(result!.state).toEqual(startupState)
  })

  it('VC state survives encode → decode', () => {
    const encoded = encodeState('vc', vcState)
    const result = decodeState(encoded)
    expect(result).not.toBeNull()
    expect(result!.module).toBe('vc')
    expect(result!.state).toEqual(vcState)
  })

  it('partial state (missing fields) round-trips without error', () => {
    const partial: MAInputState = { ...maState, acquirer: {}, target: {} }
    const encoded = encodeState('ma', partial)
    const result = decodeState(encoded)
    expect(result).not.toBeNull()
    expect(result!.state).toEqual(partial)
  })
})

// ---------------------------------------------------------------------------
// decodeState — error resilience (never throws, always returns null on bad input)
// ---------------------------------------------------------------------------

describe('decodeState resilience', () => {
  it('returns null for empty string', () => {
    expect(decodeState('')).toBeNull()
  })

  it('returns null for random garbage', () => {
    expect(decodeState('not-valid-base64!!!')).toBeNull()
    expect(decodeState('aaaaaaaaaaaaaaaa')).toBeNull()
  })

  it('returns null for truncated payload', () => {
    const encoded = encodeState('ma', maState)
    expect(decodeState(encoded.slice(0, 10))).toBeNull()
  })

  it('returns null for wrong schema version', () => {
    const payload = { v: 999, module: 'ma', state: maState }
    const LZString = (await import('lz-string')).default
    const encoded = LZString.compressToEncodedURIComponent(JSON.stringify(payload))
    expect(decodeState(encoded)).toBeNull()
  })

  it('returns null for unknown module', () => {
    const payload = { v: SCHEMA_VERSION, module: 'unknown', state: maState }
    const LZString = (await import('lz-string')).default
    const encoded = LZString.compressToEncodedURIComponent(JSON.stringify(payload))
    expect(decodeState(encoded)).toBeNull()
  })

  it('returns null for missing state field', () => {
    const payload = { v: SCHEMA_VERSION, module: 'ma' }
    const LZString = (await import('lz-string')).default
    const encoded = LZString.compressToEncodedURIComponent(JSON.stringify(payload))
    expect(decodeState(encoded)).toBeNull()
  })

  it('returns null for null state', () => {
    const payload = { v: SCHEMA_VERSION, module: 'ma', state: null }
    const LZString = (await import('lz-string')).default
    const encoded = LZString.compressToEncodedURIComponent(JSON.stringify(payload))
    expect(decodeState(encoded)).toBeNull()
  })

  it('never throws for any string input', () => {
    const inputs = ['', '!!!', 'null', '{}', '[]', 'undefined', '\x00\x01\x02']
    for (const input of inputs) {
      expect(() => decodeState(input)).not.toThrow()
    }
  })
})

// ---------------------------------------------------------------------------
// encodeState — size guard
// ---------------------------------------------------------------------------

describe('encodeState size guard', () => {
  it('throws when encoded output exceeds 8000 chars', () => {
    // Build a state with a very large string field to force oversized output
    const bigString = 'x'.repeat(50_000)
    const oversized: MAInputState = {
      ...maState,
      acquirer: { ...maState.acquirer, company_name: bigString },
    }
    expect(() => encodeState('ma', oversized)).toThrow('State too large to share.')
  })

  it('does not throw for normal-sized state', () => {
    expect(() => encodeState('ma', maState)).not.toThrow()
    expect(() => encodeState('startup', startupState)).not.toThrow()
    expect(() => encodeState('vc', vcState)).not.toThrow()
  })
})

// ---------------------------------------------------------------------------
// Property-based tests (fast-check)
// ---------------------------------------------------------------------------

describe('property-based: decodeState never throws', () => {
  it('holds for any arbitrary string', () => {
    fc.assert(
      fc.property(fc.string(), (s) => {
        expect(() => decodeState(s)).not.toThrow()
      }),
    )
  })
})

describe('property-based: round-trip fidelity for MA state', () => {
  it('holds for any valid MA input state', () => {
    fc.assert(
      fc.property(
        fc.record({
          mode: fc.constantFrom('quick' as const, 'deep' as const),
          acquirer: fc.record({
            company_name: fc.string(),
            revenue: fc.float({ min: 0, max: 10000, noNaN: true }),
            ebitda: fc.float({ min: -1000, max: 5000, noNaN: true }),
          }),
          target: fc.record({
            company_name: fc.string(),
            revenue: fc.float({ min: 0, max: 5000, noNaN: true }),
            is_ai_native: fc.boolean(),
          }),
          structure: fc.constant({ cash_percentage: 1, stock_percentage: 0, debt_percentage: 0, debt_tranches: [], transaction_fees_pct: 0.02, advisory_fees: 0 }),
          ppa: fc.constant({ asset_writeup: 0, asset_writeup_useful_life: 15, identifiable_intangibles: 0, intangible_useful_life: 10 }),
          synergies: fc.constant({ cost_synergies: [], revenue_synergies: [] }),
        }),
        (state) => {
          const encoded = encodeState('ma', state as MAInputState)
          const decoded = decodeState(encoded)
          expect(decoded).not.toBeNull()
          expect(decoded!.state).toEqual(state)
        },
      ),
    )
  })
})

describe('property-based: encoded length within limit for typical state', () => {
  it('typical MA state always encodes under 8000 chars', () => {
    fc.assert(
      fc.property(
        fc.record({
          company_name: fc.string({ maxLength: 100 }),
          revenue: fc.float({ min: 0, max: 10000, noNaN: true }),
        }),
        (fields) => {
          const state: MAInputState = {
            ...maState,
            acquirer: { ...maState.acquirer, ...fields },
          }
          const encoded = encodeState('ma', state)
          expect(encoded.length).toBeLessThanOrEqual(8000)
        },
      ),
    )
  })
})
