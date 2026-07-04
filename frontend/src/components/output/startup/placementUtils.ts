/**
 * Client-side benchmark placement math for the report-context feature.
 *
 * Computes where the model's blended valuation sits in the vertical/stage
 * benchmark distribution by linear interpolation between the P25/P50/P75/P95
 * anchors. Used by the dashboard ReportContextPanel and the PDF placement
 * reconciliation block. Presentation-only — never feeds back into the engine.
 */
import type { ContendedPlacement } from '../../../types/startup'

export interface ModelPlacement {
  /** Approximate percentile 25–95 when interpolable, null when out of range */
  approx_percentile: number | null
  /** Plain-English placement, e.g. "~P62", "below P25", "above P95", "above P75" */
  label: string
}

/**
 * Linear interpolation of `blended` against the benchmark percentile anchors.
 * - blended < P25 → "below P25"
 * - blended > P95 → "above P95"
 * - p95 missing/invalid → interpolate only to P75; beyond P75 → "above P75"
 */
export function computeModelPlacement(
  blended: number,
  p25: number,
  p50: number,
  p75: number,
  p95: number | null | undefined,
): ModelPlacement {
  const anchors: Array<[number, number]> = []
  if (p25 > 0) anchors.push([25, p25])
  if (p50 > 0) anchors.push([50, p50])
  if (p75 > 0) anchors.push([75, p75])
  const p95Valid = p95 != null && p95 > 0 && p75 > 0 && p95 > p75
  if (p95Valid) anchors.push([95, p95 as number])

  if (anchors.length < 2 || blended <= 0) {
    return { approx_percentile: null, label: 'not determinable from available benchmarks' }
  }

  const [loPct, loVal] = anchors[0]
  const [hiPct, hiVal] = anchors[anchors.length - 1]

  if (blended < loVal) {
    return { approx_percentile: null, label: `below P${loPct}` }
  }
  if (blended > hiVal) {
    // When P95 is unavailable we can only assert "above P75" — never extrapolate.
    return { approx_percentile: null, label: `above P${hiPct}` }
  }

  for (let i = 0; i < anchors.length - 1; i++) {
    const [aPct, aVal] = anchors[i]
    const [bPct, bVal] = anchors[i + 1]
    if (blended >= aVal && blended <= bVal) {
      const frac = bVal === aVal ? 0 : (blended - aVal) / (bVal - aVal)
      const pct = Math.round(aPct + frac * (bPct - aPct))
      return { approx_percentile: pct, label: `~P${pct}` }
    }
  }
  // Unreachable given the range checks above; keep a safe fallback.
  return { approx_percentile: null, label: 'not determinable from available benchmarks' }
}

/** Lower bound of the percentile band a contended placement asserts. */
const CONTENTION_LOWER_BOUND: Record<ContendedPlacement, number> = {
  p25_p50: 25,
  p50_p75: 50,
  above_p75: 75,
  above_p95: 95,
}

/**
 * True when the preparer's contended placement is at or below the model's own
 * placement — i.e. the contention asks for nothing the model doesn't already
 * grant. The reconciliation copy must never editorialize in the preparer's
 * favor, so this is the ONLY case where agreement is stated.
 */
export function contentionConsistentWithModel(
  contended: ContendedPlacement,
  placement: ModelPlacement,
): boolean {
  const lowerBound = CONTENTION_LOWER_BOUND[contended]
  if (placement.approx_percentile != null) {
    return placement.approx_percentile >= lowerBound
  }
  // "above P95" model placement satisfies every band; "above P75" satisfies up to above_p75.
  if (placement.label === 'above P95') return true
  if (placement.label === 'above P75') return lowerBound <= 75
  return false
}
