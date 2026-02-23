/**
 * Conversational deal entry — replaces/wraps Step 1 for AI-powered onboarding.
 * User describes their deal in natural language; Claude extracts structured parameters.
 * Falls back gracefully to manual form if AI unavailable.
 */
import React, { useState, useRef, useEffect } from 'react'
import { Send, ArrowRight, Sparkles, Bot, User, ChevronDown } from 'lucide-react'
import type { AcquirerProfile, TargetProfile, Industry } from '../../types/deal'
import type { ChatMessage, ParseDealResponse } from '../../lib/ai-api'
import { parseDeal } from '../../lib/ai-api'
import AIBadge from '../shared/AIBadge'

interface ConversationalEntryProps {
  onExtracted: (
    acquirer: Partial<AcquirerProfile>,
    target: Partial<TargetProfile>,
    summary: string,
  ) => void
  onSkipToForm: () => void
  aiAvailable: boolean
}

interface UIMessage {
  role: 'user' | 'assistant' | 'system'
  content: string
  isExtracting?: boolean
}

const EXAMPLE_PROMPTS = [
  "We're a $50M HVAC company looking to buy a competitor doing $20M in revenue with ~18% EBITDA margins, asking price around $30M",
  "Our SaaS company ($200M ARR) wants to acquire a smaller competitor for $80M. They do $15M revenue at 22% margins.",
  "Small manufacturing co, $30M revenue, considering buying a distributor at $12M EBITDA for $90M",
]

export default function ConversationalEntry({
  onExtracted,
  onSkipToForm,
  aiAvailable,
}: ConversationalEntryProps) {
  const [messages, setMessages] = useState<UIMessage[]>([
    {
      role: 'assistant',
      content: "Tell me about the deal you're considering. For example: *\"We're a $50M HVAC company looking to acquire a competitor doing $20M with 18% margins for around $30M.\"*\n\nI'll extract the details and pre-fill the model for you.",
    },
  ])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [extracted, setExtracted] = useState<ParseDealResponse | null>(null)
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([])
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const sendMessage = async (text: string) => {
    if (!text.trim() || isLoading) return

    const userMsg: UIMessage = { role: 'user', content: text }
    const newHistory: ChatMessage[] = [...chatHistory, { role: 'user', content: text }]

    setMessages(prev => [...prev, userMsg])
    setChatHistory(newHistory)
    setInput('')
    setIsLoading(true)

    try {
      const response = await parseDeal(newHistory)

      const assistantContent = response.summary || response.follow_up_question || "Let me know if you'd like to adjust anything before we model this."

      setMessages(prev => [...prev, {
        role: 'assistant',
        content: assistantContent,
      }])
      setChatHistory(prev => [...prev, { role: 'assistant', content: assistantContent }])

      if (response.status === 'ready_to_model' && response.extracted) {
        setExtracted(response)
      }
    } catch {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: "I couldn't fully parse those details. Try including specific numbers — for example: buyer revenue, target revenue, EBITDA margins, and asking price. Or switch to the guided form below.",
      }])
    } finally {
      setIsLoading(false)
    }
  }

  const handleProceed = () => {
    if (!extracted) return

    const e = extracted.extracted
    const acquirer: Partial<AcquirerProfile> = {
      company_name: (e.acquirer_name as string) || 'Your Company',
      revenue: (e.acquirer_revenue as number) || 0,
      ebitda: (e.acquirer_ebitda as number) || 0,
      industry: (e.acquirer_industry as Industry) || undefined,
      tax_rate: 0.25,
      shares_outstanding: 10_000_000,
      share_price: 10,
      total_debt: 0,
      cash_on_hand: 0,
      net_income: 0,
      depreciation: 0,
      capex: 0,
      working_capital: 0,
    }

    const revenue = e.target_revenue as number || 0
    const margin = e.target_ebitda_margin as number || 0
    const ebitda = (e.target_ebitda as number) || (margin > 0 && revenue > 0 ? revenue * margin : 0)

    const target: Partial<TargetProfile> = {
      company_name: (e.target_name as string) || 'Target Company',
      revenue,
      ebitda,
      net_income: ebitda * 0.6,
      industry: (e.target_industry as Industry) || (e.acquirer_industry as Industry) || undefined,
      acquisition_price: (e.acquisition_price as number) || 0,
      revenue_growth_rate: 0.05,
      tax_rate: 0.25,
      total_debt: 0,
      cash_on_hand: 0,
      depreciation: revenue * 0.04,
      capex: revenue * 0.03,
      working_capital: revenue * 0.10,
    }

    onExtracted(acquirer, target, extracted.summary)
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage(input)
    }
  }

  if (!aiAvailable) {
    // Graceful degradation — show skip button prominently
    return (
      <div className="max-w-2xl mx-auto animate-slide-up">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-slate-100 mb-3">Let's model your deal.</h1>
          <p className="text-slate-400 text-lg">
            Tell us about the companies involved and we'll run the analysis.
          </p>
        </div>
        <div className="rounded-xl border border-slate-700 bg-slate-800/20 p-6 text-center space-y-4">
          <p className="text-slate-400 text-sm">AI-powered conversational entry requires an Anthropic API key.</p>
          <button
            onClick={onSkipToForm}
            className="flex items-center justify-center gap-2 px-6 py-3 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-semibold text-sm transition-all mx-auto"
          >
            Continue with guided form <ArrowRight size={16} />
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-2xl mx-auto animate-slide-up">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-100 mb-1 flex items-center gap-2">
            <Sparkles size={20} className="text-purple-400" />
            Tell me about your deal.
          </h1>
          <p className="text-slate-500 text-sm">I'll extract the details and pre-fill the model.</p>
        </div>
        <AIBadge />
      </div>

      {/* Chat window */}
      <div className="rounded-xl border border-slate-700 bg-slate-900/60 overflow-hidden">
        <div className="h-72 overflow-y-auto p-4 space-y-4">
          {messages.map((msg, i) => (
            <div key={i} className={`flex gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
              <div className={`
                flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center text-xs
                ${msg.role === 'user' ? 'bg-blue-700' : 'bg-purple-800/60'}
              `}>
                {msg.role === 'user' ? <User size={13} /> : <Bot size={13} />}
              </div>
              <div className={`
                rounded-xl px-4 py-2.5 text-sm leading-relaxed max-w-[85%]
                ${msg.role === 'user'
                  ? 'bg-blue-700/30 text-slate-200'
                  : 'bg-slate-800/60 text-slate-300'
                }
              `}>
                {msg.content.split('*').map((part, j) => (
                  j % 2 === 1
                    ? <em key={j} className="not-italic text-slate-200 font-medium">{part}</em>
                    : <span key={j}>{part}</span>
                ))}
              </div>
            </div>
          ))}

          {isLoading && (
            <div className="flex gap-3">
              <div className="w-7 h-7 rounded-full bg-purple-800/60 flex items-center justify-center">
                <Bot size={13} />
              </div>
              <div className="bg-slate-800/60 rounded-xl px-4 py-3 flex gap-1 items-center">
                {[0, 1, 2].map(i => (
                  <div key={i} className="w-1.5 h-1.5 rounded-full bg-slate-400 animate-bounce" style={{ animationDelay: `${i * 150}ms` }} />
                ))}
              </div>
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        {/* Input area */}
        <div className="border-t border-slate-700 p-3 bg-slate-900/40">
          <div className="flex gap-2 items-end">
            <textarea
              ref={inputRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Describe the deal..."
              rows={2}
              className="
                flex-1 bg-slate-800/40 border border-slate-700 rounded-lg px-3 py-2
                text-sm text-slate-100 placeholder-slate-500 outline-none
                focus:border-purple-500/60 resize-none transition-colors
              "
            />
            <button
              onClick={() => sendMessage(input)}
              disabled={!input.trim() || isLoading}
              className="flex-shrink-0 w-9 h-9 rounded-lg bg-purple-700 hover:bg-purple-600 disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center transition-colors"
            >
              <Send size={15} className="text-white" />
            </button>
          </div>
        </div>
      </div>

      {/* Example prompts */}
      {messages.length <= 1 && (
        <div className="mt-4 space-y-2">
          <p className="text-xs text-slate-500">Try an example:</p>
          {EXAMPLE_PROMPTS.map((p, i) => (
            <button
              key={i}
              onClick={() => sendMessage(p)}
              className="block w-full text-left text-xs text-slate-400 hover:text-slate-200 bg-slate-800/30 hover:bg-slate-800/60 border border-slate-700/50 rounded-lg px-3 py-2 transition-all"
            >
              "{p}"
            </button>
          ))}
        </div>
      )}

      {/* Proceed card when extracted */}
      {extracted && (
        <div className="mt-5 rounded-xl border border-green-800/40 bg-green-950/15 p-5 animate-slide-up">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-green-400">Ready to model</span>
              <AIBadge />
            </div>
          </div>
          <p className="text-xs text-slate-400 mb-4">{extracted.summary}</p>
          <div className="flex gap-3">
            <button
              onClick={handleProceed}
              className="flex-1 flex items-center justify-center gap-2 px-5 py-3 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-semibold text-sm transition-all"
            >
              Proceed to Model <ArrowRight size={15} />
            </button>
            <button
              onClick={() => setExtracted(null)}
              className="px-4 py-3 rounded-xl border border-slate-700 text-slate-400 hover:text-slate-200 text-sm transition-colors"
            >
              Keep chatting
            </button>
          </div>
        </div>
      )}

      {/* Switch to manual form link */}
      <div className="mt-4 text-center">
        <button
          onClick={onSkipToForm}
          className="text-xs text-slate-500 hover:text-slate-300 transition-colors"
        >
          Prefer to fill in fields manually? <span className="underline">Use the guided form</span>
        </button>
      </div>
    </div>
  )
}
