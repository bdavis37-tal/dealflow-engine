/**
 * API client for the dealflow engine backend.
 */
import type { DealInput, DealOutput, Industry } from '../types/deal'
import type { StartupInput, StartupValuationOutput, StartupVertical, StartupStage } from '../types/startup'

const BASE_URL = import.meta.env.VITE_API_URL ?? '/api/v1'
const STARTUP_BASE = '/api/startup'

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.text()
    throw new Error(`API error ${res.status}: ${body}`)
  }
  return res.json() as Promise<T>
}

export async function analyzeDeal(input: DealInput, signal?: AbortSignal): Promise<DealOutput> {
  const res = await fetch(`${BASE_URL}/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
    signal,
  })
  return handleResponse<DealOutput>(res)
}

export async function getSmartDefaults(
  industry: Industry,
  dealSize: number,
  targetRevenue: number,
): Promise<Record<string, unknown>> {
  const params = new URLSearchParams({
    industry,
    deal_size: dealSize.toString(),
    target_revenue: targetRevenue.toString(),
  })
  const res = await fetch(`${BASE_URL}/defaults?${params}`)
  return handleResponse<Record<string, unknown>>(res)
}

export async function getIndustries(): Promise<Array<{ value: string; label: string }>> {
  const res = await fetch(`${BASE_URL}/industries`)
  return handleResponse<Array<{ value: string; label: string }>>(res)
}

export async function healthCheck(): Promise<{ status: string }> {
  const res = await fetch(`${BASE_URL}/health`)
  return handleResponse<{ status: string }>(res)
}

// ---------------------------------------------------------------------------
// Startup valuation API
// ---------------------------------------------------------------------------

export async function valueStartup(input: StartupInput): Promise<StartupValuationOutput> {
  const res = await fetch(`${STARTUP_BASE}/value`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
  return handleResponse<StartupValuationOutput>(res)
}

export async function getStartupBenchmarks(
  vertical: StartupVertical,
  stage: StartupStage,
): Promise<Record<string, unknown>> {
  const params = new URLSearchParams({ vertical, stage })
  const res = await fetch(`${STARTUP_BASE}/benchmarks?${params}`)
  return handleResponse<Record<string, unknown>>(res)
}

export async function getStartupVerticals(): Promise<Array<{ value: string; label: string; description: string }>> {
  const res = await fetch(`${STARTUP_BASE}/verticals`)
  return handleResponse<Array<{ value: string; label: string; description: string }>>(res)
}
