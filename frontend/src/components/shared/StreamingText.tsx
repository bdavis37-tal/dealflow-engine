/**
 * Renders streaming text with a typing-cursor animation.
 * Used for all AI-generated content that streams in real time.
 */
import { useEffect, useState } from 'react'

interface StreamingTextProps {
  text: string
  isStreaming: boolean
  className?: string
  /** If true, render markdown-style line breaks */
  multiline?: boolean
}

export default function StreamingText({
  text,
  isStreaming,
  className = '',
  multiline = false,
}: StreamingTextProps) {
  const [showCursor, setShowCursor] = useState(true)

  useEffect(() => {
    if (!isStreaming) return
    const interval = setInterval(() => setShowCursor(v => !v), 500)
    return () => clearInterval(interval)
  }, [isStreaming])

  if (!text && !isStreaming) return null

  if (multiline) {
    return (
      <div className={`leading-relaxed ${className}`}>
        {text.split('\n').map((line, i) => (
          <p key={i} className={line === '' ? 'h-3' : 'mb-2'}>
            {line}
          </p>
        ))}
        {isStreaming && (
          <span className={`inline-block w-0.5 h-4 bg-purple-400 ml-0.5 transition-opacity ${showCursor ? 'opacity-100' : 'opacity-0'}`} />
        )}
      </div>
    )
  }

  return (
    <span className={className}>
      {text}
      {isStreaming && (
        <span className={`inline-block w-0.5 h-4 bg-purple-400 ml-0.5 align-middle transition-opacity ${showCursor ? 'opacity-100' : 'opacity-0'}`} />
      )}
    </span>
  )
}
