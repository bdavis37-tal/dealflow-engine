/**
 * AI API client — all calls route through the backend to keep the API key server-side.
 * Every function degrades gracefully if AI is unavailable.
 */
import type { DealInput, DealOutput } from '../types/deal'
import type { StartupInput, StartupValuationOutput, StartupNarrativeResponse } from '../types/startup'

const BASE_URL = import.meta.env.VITE_API_URL ?? '/api'

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface ParseDealResponse {
  status: 'need_more_info' | 'ready_to_model' | 'ai_unavailable'
  follow_up_question: string | null
  extracted: Record<string, unknown>
  confidence: Record<string, number>
  summary: string
  ai_available: boolean
}

export interface NarrativeResponse {
  verdict_narrative: string | null
  risk_narratives: Record<string, string>
  executive_summary: string | null
  ai_available: boolean
  cached: boolean
}

export interface FieldHelpResponse {
  explanation: string
  ai_available: boolean
  cached: boolean
}

export interface AIStatus {
  ai_available: boolean
  model: string
  token_usage: { input: number; output: number; calls: number }
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE_URL}/ai${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`AI API ${res.status}`)
  return res.json()
}

export async function checkAIStatus(): Promise<AIStatus> {
  const res = await fetch(`${BASE_URL}/ai/status`)
  if (!res.ok) return { ai_available: false, model: '', token_usage: { input: 0, output: 0, calls: 0 } }
  return res.json()
}

export async function parseDeal(messages: ChatMessage[]): Promise<ParseDealResponse> {
  return post<ParseDealResponse>('/parse-deal', { messages })
}

export async function generateNarrative(
  deal_input: DealInput,
  deal_output: DealOutput,
): Promise<NarrativeResponse> {
  return post<NarrativeResponse>('/generate-narrative', { deal_input, deal_output })
}

export async function explainField(
  field_name: string,
  field_label: string,
  industry: string,
  current_value?: string,
  deal_context_summary?: string,
): Promise<FieldHelpResponse> {
  return post<FieldHelpResponse>('/explain-field', {
    field_name,
    field_label,
    industry,
    current_value,
    deal_context_summary,
  })
}

/**
 * Stream a chat response via SSE.
 * Calls onChunk for each text chunk, onDone when complete.
 */
export async function streamChat(
  messages: ChatMessage[],
  deal_input: DealInput | null,
  deal_output: DealOutput | null,
  onChunk: (chunk: string) => void,
  onDone: () => void,
  onError: (err: string) => void,
): Promise<void> {
  try {
    const res = await fetch(`${BASE_URL}/ai/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        messages,
        deal_input,
        deal_output,
      }),
    })

    if (!res.ok || !res.body) {
      onError(`AI unavailable (${res.status})`)
      return
    }

    const reader = res.body.getReader()
    const decoder = new TextDecoder()

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      const text = decoder.decode(value)
      const lines = text.split('\n')

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        const data = line.slice(6)
        if (data === '[DONE]') {
          onDone()
          return
        }
        if (data === '[AI_UNAVAILABLE]') {
          onError('AI features are not available. Set ANTHROPIC_API_KEY to enable.')
          return
        }
        if (data === '[STREAM_ERROR]') {
          onError('AI response stream encountered an error.')
          return
        }
        try {
          const chunk = JSON.parse(data)
          onChunk(chunk)
        } catch {
          // Ignore malformed SSE chunks
        }
      }
    }
    onDone()
  } catch (err) {
    onError(err instanceof Error ? err.message : 'Chat connection failed')
  }
}

/**
 * Stream a scenario narrative for a sensitivity cell click.
 */
export async function streamScenarioNarrative(
  payload: {
    base_deal_input: DealInput
    base_deal_output: DealOutput
    scenario_row_label: string
    scenario_col_label: string
    scenario_row_value: number
    scenario_col_value: number
    scenario_accretion_pct: number
  },
  onChunk: (chunk: string) => void,
  onDone: () => void,
): Promise<void> {
  try {
    const res = await fetch(`${BASE_URL}/ai/scenario-narrative`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })

    if (!res.ok || !res.body) return

    const reader = res.body.getReader()
    const decoder = new TextDecoder()

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      const text = decoder.decode(value)
      for (const line of text.split('\n')) {
        if (!line.startsWith('data: ')) continue
        const data = line.slice(6)
        if (data === '[DONE]') { onDone(); return }
        try { onChunk(JSON.parse(data)) } catch { /* skip */ }
      }
    }
    onDone()
  } catch {
    onDone()
  }
}

export async function generateStartupNarrative(
  startup_input: StartupInput,
  startup_output: StartupValuationOutput,
): Promise<StartupNarrativeResponse> {
  return post<StartupNarrativeResponse>('/startup-narrative', { startup_input, startup_output })
}
