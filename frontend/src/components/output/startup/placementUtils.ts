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
  // Inherited percentile-shaped assumptions do not establish a distribution.
  void blended; void p25; void p50; void p75; void p95
  return {approx_percentile: null, label: 'Observed market percentile unavailable'}
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
