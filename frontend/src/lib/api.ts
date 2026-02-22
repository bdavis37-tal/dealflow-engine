/**
 * API client for the dealflow engine backend.
 */
import type { DealInput, DealOutput, Industry } from '../types/deal'

const BASE_URL = import.meta.env.VITE_API_URL ?? '/api/v1'

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.text()
    throw new Error(`API error ${res.status}: ${body}`)
  }
  return res.json() as Promise<T>
}

export async function analyzeDeal(input: DealInput): Promise<DealOutput> {
  const res = await fetch(`${BASE_URL}/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
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
