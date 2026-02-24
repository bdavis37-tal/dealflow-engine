/**
 * Currency input with formatted display and validation.
 */
import React, { useState } from 'react'
import { HelpCircle } from 'lucide-react'

interface CurrencyInputProps {
  label: string
  value: number
  onChange: (value: number) => void
  help?: string
  defaultNote?: string
  placeholder?: string
  required?: boolean
  error?: string
  min?: number
}

function formatDisplay(value: number): string {
  if (!value && value !== 0) return ''
  if (Math.abs(value) >= 1_000_000_000) return `$${(value / 1_000_000_000).toFixed(2)}B`
  if (Math.abs(value) >= 1_000_000) return `$${(value / 1_000_000).toFixed(2)}M`
  if (Math.abs(value) >= 1_000) return `$${(value / 1_000).toFixed(0)}K`
  return `$${value.toFixed(0)}`
}

export default function CurrencyInput({
  label,
  value,
  onChange,
  help,
  defaultNote,
  placeholder = '$0',
  required,
  error,
  min = 0,
}: CurrencyInputProps) {
  const [focused, setFocused] = useState(false)
  const [showHelp, setShowHelp] = useState(false)
  const [rawInput, setRawInput] = useState('')

  const handleFocus = () => {
    setFocused(true)
    setRawInput(value ? value.toString() : '')
  }

  const handleBlur = () => {
    setFocused(false)
    if (!rawInput.trim()) return // empty is fine, keep previous value
    const parsed = parseFloat(rawInput.replace(/[^0-9.-]/g, ''))
    if (!isNaN(parsed) && parsed >= min) {
      onChange(parsed)
    }
    // If invalid, silently revert to previous value display (no state change).
    // The formatted display will show the last valid value on blur.
  }

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value
    setRawInput(val)
    // Propagate valid numbers immediately for live calculations
    const parsed = parseFloat(val.replace(/[^0-9.-]/g, ''))
    if (!isNaN(parsed) && parsed >= min) {
      onChange(parsed)
    }
  }

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <label className="text-sm font-medium text-slate-300 flex items-center gap-1.5">
          {label}
          {required && <span className="text-red-400 text-xs">*</span>}
          {help && (
            <button
              type="button"
              onClick={() => setShowHelp(v => !v)}
              className="text-slate-500 hover:text-slate-300 transition-colors"
            >
              <HelpCircle size={13} />
            </button>
          )}
        </label>
        {defaultNote && (
          <span className="text-2xs text-blue-400">Smart default</span>
        )}
      </div>

      {showHelp && help && (
        <p className="text-xs text-slate-400 bg-slate-800/60 rounded-md px-3 py-2 border border-slate-700/50 animate-fade-in">
          {help}
        </p>
      )}

      <div className={`
        flex items-center rounded-lg border transition-colors
        ${error ? 'border-red-500/60' : focused ? 'border-blue-500/60' : 'border-slate-700'}
        bg-slate-800/40
      `}>
        <input
          type="text"
          inputMode="decimal"
          value={focused ? rawInput : (value ? formatDisplay(value) : '')}
          onChange={handleChange}
          onFocus={handleFocus}
          onBlur={handleBlur}
          placeholder={placeholder}
          className="
            flex-1 bg-transparent px-3 py-2.5 text-sm text-slate-100
            placeholder-slate-500 outline-none tabular-nums
            [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none
            [&::-webkit-inner-spin-button]:appearance-none
          "
        />
      </div>

      {defaultNote && !error && (
        <p className="text-2xs text-slate-500">{defaultNote}</p>
      )}
      {error && <p className="text-xs text-red-400">{error}</p>}
    </div>
  )
}
