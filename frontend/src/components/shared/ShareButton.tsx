/**
 * ShareButton — encodes current module input state into the URL hash
 * and copies the full URL to clipboard.
 */
import { useState } from 'react'
import { Share2, Check, AlertCircle } from 'lucide-react'
import { encodeState } from '../../lib/shareUtils'
import type { ShareModule, MAInputState, StartupInputState, VCInputState } from '../../lib/shareUtils'

interface ShareButtonProps {
  module: ShareModule
  inputState: MAInputState | StartupInputState | VCInputState
  colorScheme: 'blue' | 'purple' | 'emerald'
  className?: string
}

const COLOR_CLASSES = {
  blue: {
    base: 'border-blue-700/60 text-blue-400 hover:text-blue-200 hover:border-blue-500',
    copied: 'border-blue-600 text-blue-300 bg-blue-900/20',
  },
  purple: {
    base: 'border-purple-700/60 text-purple-400 hover:text-purple-200 hover:border-purple-500',
    copied: 'border-purple-600 text-purple-300 bg-purple-900/20',
  },
  emerald: {
    base: 'border-emerald-700/60 text-emerald-400 hover:text-emerald-200 hover:border-emerald-500',
    copied: 'border-emerald-600 text-emerald-300 bg-emerald-900/20',
  },
}

export default function ShareButton({ module, inputState, colorScheme, className = '' }: ShareButtonProps) {
  const [status, setStatus] = useState<'idle' | 'copied' | 'error'>('idle')
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  const colors = COLOR_CLASSES[colorScheme]

  const handleShare = async () => {
    let encoded: string
    try {
      encoded = encodeState(module, inputState)
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : 'Failed to encode state.')
      setStatus('error')
      return
    }

    // Set hash on current URL
    const url = `${window.location.origin}${window.location.pathname}#share=${encoded}`

    try {
      await navigator.clipboard.writeText(url)
    } catch {
      // Clipboard API unavailable — fallback prompt
      window.prompt('Copy this link to share:', url)
    }

    // Update hash in address bar (non-navigating)
    window.history.replaceState(null, '', `#share=${encoded}`)

    setStatus('copied')
    setErrorMsg(null)
    setTimeout(() => setStatus('idle'), 2000)
  }

  if (status === 'error' && errorMsg) {
    return (
      <div className={`flex items-center gap-1.5 text-xs text-red-400 border border-red-700/50 rounded-lg px-3 py-1.5 ${className}`}>
        <AlertCircle size={12} />
        {errorMsg}
      </div>
    )
  }

  return (
    <button
      onClick={handleShare}
      className={`flex items-center gap-1.5 text-xs border rounded-lg px-3 py-1.5 transition-colors ${
        status === 'copied' ? colors.copied : colors.base
      } ${className}`}
      title="Copy shareable link"
    >
      {status === 'copied' ? (
        <>
          <Check size={12} />
          Copied!
        </>
      ) : (
        <>
          <Share2 size={12} />
          Share
        </>
      )}
    </button>
  )
}
