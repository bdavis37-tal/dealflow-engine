import type { AnalysisEvidence } from '../types/evidence'
/**
 * shareUtils.ts — URL-based state sharing for Dealflow Engine.
 *
 * Encodes input state into a URL hash fragment using LZ-string compression.
 * No backend required — the entire payload lives in the hash (#share=...).
 *
 * Hash format: #share=<LZString.compressToEncodedURIComponent(JSON)>
 */
import LZString from 'lz-string'
import type {
  ModelMode,
  AcquirerProfile,
  TargetProfile,
  DealStructure,
  PurchasePriceAllocation,
  SynergyAssumptions,
} from '../types/deal'
import type {
  TeamProfile,
  TractionMetrics,
  ProductProfile,
  MarketProfile,
  FundraisingProfile,
} from '../types/startup'
import type { FundProfile, VCDealInput } from '../types/vc'

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Bump this when input shapes change incompatibly. Old links will be rejected. */
export const SCHEMA_VERSION = 2

/** Max safe length for a URL hash fragment (conservative). */
const MAX_ENCODED_LENGTH = 8000

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type ShareModule = 'ma' | 'startup' | 'vc'

export interface MAInputState {
  benchmark_version?: string
  mode: ModelMode
  acquirer: Partial<AcquirerProfile>
  target: Partial<TargetProfile>
  structure: Partial<DealStructure>
  ppa: Partial<PurchasePriceAllocation>
  synergies: SynergyAssumptions
}

export interface StartupInputState {
  benchmark_version?: string
  company_name: string
  team: Partial<TeamProfile>
  traction: Partial<TractionMetrics>
  product: Partial<ProductProfile>
  market: Partial<MarketProfile>
  fundraise: Partial<FundraisingProfile>
  is_ai_native: boolean
  ai_native_score: number
  ai_answers: [boolean, boolean, boolean, boolean]
}

export interface VCInputState {
  fund: FundProfile
  deal: Partial<VCDealInput>
}

export interface SharePayload {
  v: number
  provenance?: Omit<AnalysisEvidence, 'records'> & { record_ids: string[] }
  module: ShareModule
  state: MAInputState | StartupInputState | VCInputState
}

// ---------------------------------------------------------------------------
// Encode
// ---------------------------------------------------------------------------

/**
 * Encodes a module's input state into a URL-safe compressed string.
 * Throws a user-visible error if the result exceeds MAX_ENCODED_LENGTH.
 */
export function encodeState(
  module: ShareModule,
  state: MAInputState | StartupInputState | VCInputState,
  evidence?: AnalysisEvidence | null,
): string {
  const payload: SharePayload = { v: SCHEMA_VERSION, module, state }
  if (evidence) {
    const {records, ...metadata} = evidence
    payload.provenance = {...metadata, record_ids: records.map(r => r.id)}
  }
  const json = JSON.stringify(payload)
  const encoded = LZString.compressToEncodedURIComponent(json)

  if (encoded.length > MAX_ENCODED_LENGTH) {
    throw new Error('State too large to share.')
  }

  return encoded
}

// ---------------------------------------------------------------------------
// Decode
// ---------------------------------------------------------------------------

/**
 * Decodes a compressed string back into a SharePayload.
 * Returns null on ANY failure — never throws.
 */
export function decodeState(encoded: string): SharePayload | null {
  try {
    if (!encoded) return null

    const json = LZString.decompressFromEncodedURIComponent(encoded)
    if (!json) return null

    const payload = JSON.parse(json) as unknown

    if (
      typeof payload !== 'object' ||
      payload === null ||
      !('v' in payload) ||
      !('module' in payload) ||
      !('state' in payload)
    ) {
      return null
    }

    const p = payload as Record<string, unknown>

    if (typeof p.v !== 'number' || p.v <= 0 || ![1, SCHEMA_VERSION].includes(p.v)) return null
    if (!['ma', 'startup', 'vc'].includes(p.module as string)) return null
    if (typeof p.state !== 'object' || p.state === null) return null

    const shared = payload as SharePayload
    if (shared.v === 1) {
      if (shared.module === 'vc') {
        const state = shared.state as VCInputState
        const order = ['pre_seed', 'seed', 'series_a', 'series_b', 'series_c', 'ipo']
        const entry = order.indexOf(state.deal.stage ?? 'seed')
        state.deal = {...state.deal, benchmark_version: '2026-07-legacy',
          dilution_source: state.deal.dilution ? 'custom' : 'benchmark',
          future_rounds: state.deal.future_rounds ?? order.slice(entry + 1)}
      } else {
        (shared.state as MAInputState | StartupInputState).benchmark_version = '2026-07-legacy'
      }
    }
    return shared
  } catch {
    return null
  }
}

// ---------------------------------------------------------------------------
// Parse hash
// ---------------------------------------------------------------------------

/**
 * Extracts the encoded string from a URL hash fragment like "#share=abc123".
 * Returns null if the hash doesn't start with "#share=" or is empty.
 */
export function parseShareHash(hash: string): string | null {
  if (!hash.startsWith('#share=')) return null
  const encoded = hash.slice(7) // strip "#share="
  return encoded || null
}
