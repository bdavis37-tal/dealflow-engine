/**
 * AI Co-Pilot chat panel — persistent sidebar on the results dashboard.
 * Has full deal context. Streams responses. Surfaces parameter change suggestions.
 */
import React, { useState, useRef, useEffect } from 'react'
import { MessageSquare, Send, X, ChevronRight, Loader2, Bot, User, Zap } from 'lucide-react'
import type { DealInput, DealOutput } from '../../types/deal'
import type { ChatMessage } from '../../lib/ai-api'
import { streamChat } from '../../lib/ai-api'
import AIBadge from '../shared/AIBadge'
import StreamingText from '../shared/StreamingText'

interface AIChatPanelProps {
  dealInput: DealInput
  dealOutput: DealOutput
  onApplyChanges?: (changes: Record<string, unknown>) => void
}

interface UIMessage {
  role: 'user' | 'assistant'
  content: string
  isStreaming?: boolean
  parameterChanges?: {
    description: string
    changes: Record<string, unknown>
    apply_label: string
  }
}

const QUICK_PROMPTS = [
  "Is this a good deal?",
  "What should I negotiate on?",
  "Explain the accretion/dilution bridge",
  "What would a PE firm think of these returns?",
  "Write board presentation talking points",
  "What if we financed this with all cash?",
]

function parseParameterChanges(text: string): {
  cleanText: string
  changes: UIMessage['parameterChanges']
} {
  const match = text.match(/<parameter_changes>([\s\S]*?)<\/parameter_changes>/)
  if (!match) return { cleanText: text, changes: undefined }

  const cleanText = text.replace(/<parameter_changes>[\s\S]*?<\/parameter_changes>/g, '').trim()
  try {
    const changes = JSON.parse(match[1].trim())
    return { cleanText, changes }
  } catch {
    return { cleanText, changes: undefined }
  }
}

export default function AIChatPanel({ dealInput, dealOutput, onApplyChanges }: AIChatPanelProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [messages, setMessages] = useState<UIMessage[]>([
    {
      role: 'assistant',
      content: `I have full context of this deal — ${dealInput.acquirer.company_name} acquiring ${dealInput.target.company_name} for $${(dealInput.target.acquisition_price / 1e6).toFixed(0)}M. Ask me anything.`,
    },
  ])
  const [input, setInput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [history, setHistory] = useState<ChatMessage[]>([])
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (isOpen) {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
      inputRef.current?.focus()
    }
  }, [messages, isOpen])

  const sendMessage = async (text: string) => {
    if (!text.trim() || isStreaming) return

    const userMsg: UIMessage = { role: 'user', content: text }
    const newHistory: ChatMessage[] = [...history, { role: 'user', content: text }]
    setHistory(newHistory)
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setIsStreaming(true)

    // Add a placeholder streaming message
    const streamingMsg: UIMessage = { role: 'assistant', content: '', isStreaming: true }
    setMessages(prev => [...prev, streamingMsg])

    let accumulated = ''

    await streamChat(
      newHistory,
      dealInput,
      dealOutput,
      (chunk) => {
        accumulated += chunk
        setMessages(prev => {
          const updated = [...prev]
          updated[updated.length - 1] = { role: 'assistant', content: accumulated, isStreaming: true }
          return updated
        })
      },
      () => {
        // Done — finalize the message and parse parameter changes
        const { cleanText, changes } = parseParameterChanges(accumulated)
        const finalMsg: UIMessage = {
          role: 'assistant',
          content: cleanText,
          isStreaming: false,
          parameterChanges: changes,
        }
        setMessages(prev => {
          const updated = [...prev]
          updated[updated.length - 1] = finalMsg
          return updated
        })
        setHistory(prev => [...prev, { role: 'assistant', content: cleanText }])
        setIsStreaming(false)
        bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
      },
      (err) => {
        setMessages(prev => {
          const updated = [...prev]
          updated[updated.length - 1] = {
            role: 'assistant',
            content: err,
            isStreaming: false,
          }
          return updated
        })
        setIsStreaming(false)
      },
    )
  }

  return (
    <>
      {/* Floating toggle button */}
      {!isOpen && (
        <button
          onClick={() => setIsOpen(true)}
          className="
            fixed bottom-6 right-6 z-40
            flex items-center gap-2 px-4 py-3 rounded-xl
            bg-purple-700 hover:bg-purple-600 text-white font-medium text-sm
            shadow-xl shadow-purple-900/40 transition-all
          "
        >
          <MessageSquare size={16} />
          Ask AI Co-Pilot
          <AIBadge className="ml-1" />
        </button>
      )}

      {/* Panel */}
      {isOpen && (
        <div className="fixed bottom-0 right-0 z-40 w-96 h-[600px] max-h-[85vh] flex flex-col rounded-tl-2xl border-l border-t border-slate-700 bg-slate-900 shadow-2xl animate-slide-up">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-slate-700">
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-lg bg-purple-800/60 flex items-center justify-center">
                <Bot size={14} className="text-purple-300" />
              </div>
              <div>
                <div className="text-sm font-semibold text-slate-100 flex items-center gap-1.5">
                  AI Co-Pilot
                  <AIBadge />
                </div>
                <div className="text-2xs text-slate-500">Full deal context loaded</div>
              </div>
            </div>
            <button
              onClick={() => setIsOpen(false)}
              className="text-slate-500 hover:text-slate-300 transition-colors"
            >
              <X size={16} />
            </button>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {messages.map((msg, i) => (
              <div key={i} className={`flex gap-2.5 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
                <div className={`
                  flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center text-xs
                  ${msg.role === 'user' ? 'bg-blue-700' : 'bg-purple-800/60'}
                `}>
                  {msg.role === 'user' ? <User size={11} /> : <Bot size={11} />}
                </div>
                <div className="max-w-[85%] space-y-2">
                  <div className={`
                    rounded-xl px-3 py-2.5 text-xs leading-relaxed
                    ${msg.role === 'user'
                      ? 'bg-blue-700/30 text-slate-200'
                      : 'bg-slate-800/60 text-slate-300'
                    }
                  `}>
                    {msg.isStreaming
                      ? <StreamingText text={msg.content} isStreaming={true} multiline />
                      : msg.content.split('\n').map((line, j) => (
                          <p key={j} className={line === '' ? 'h-2' : ''}>{line}</p>
                        ))
                    }
                  </div>

                  {/* Parameter change suggestion */}
                  {msg.parameterChanges && onApplyChanges && (
                    <button
                      onClick={() => onApplyChanges(msg.parameterChanges!.changes)}
                      className="flex items-center gap-1.5 text-xs text-blue-400 hover:text-blue-300 bg-blue-950/20 border border-blue-800/40 rounded-lg px-3 py-2 transition-colors w-full"
                    >
                      <Zap size={12} />
                      {msg.parameterChanges.apply_label}
                    </button>
                  )}
                </div>
              </div>
            ))}
            <div ref={bottomRef} />
          </div>

          {/* Quick prompts */}
          {messages.length <= 1 && (
            <div className="px-3 pb-2 flex flex-wrap gap-1.5">
              {QUICK_PROMPTS.slice(0, 3).map((p, i) => (
                <button
                  key={i}
                  onClick={() => sendMessage(p)}
                  className="text-2xs text-slate-400 hover:text-slate-200 bg-slate-800/60 border border-slate-700 rounded-full px-2.5 py-1 transition-colors"
                >
                  {p}
                </button>
              ))}
            </div>
          )}

          {/* Input */}
          <div className="p-3 border-t border-slate-700">
            <div className="flex gap-2">
              <input
                ref={inputRef}
                type="text"
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && sendMessage(input)}
                placeholder="Ask anything about this deal..."
                className="
                  flex-1 bg-slate-800/40 border border-slate-700 rounded-lg px-3 py-2
                  text-xs text-slate-100 placeholder-slate-500 outline-none
                  focus:border-purple-500/60 transition-colors
                "
              />
              <button
                onClick={() => sendMessage(input)}
                disabled={!input.trim() || isStreaming}
                className="flex-shrink-0 w-8 h-8 rounded-lg bg-purple-700 hover:bg-purple-600 disabled:opacity-40 flex items-center justify-center transition-colors"
              >
                {isStreaming ? <Loader2 size={13} className="animate-spin text-white" /> : <Send size={13} className="text-white" />}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
