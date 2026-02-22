/**
 * Reusable guided input component.
 * Shows label, help tooltip, smart default indicator, and validation.
 */
import React, { useState } from 'react'
import { HelpCircle } from 'lucide-react'

interface GuidedInputProps {
  label: string
  help?: string
  value: string | number
  onChange: (value: string) => void
  type?: 'text' | 'number' | 'email'
  placeholder?: string
  prefix?: string
  suffix?: string
  defaultNote?: string
  error?: string
  required?: boolean
  min?: number
  max?: number
  step?: number
  disabled?: boolean
}

export default function GuidedInput({
  label,
  help,
  value,
  onChange,
  type = 'text',
  placeholder,
  prefix,
  suffix,
  defaultNote,
  error,
  required,
  min,
  max,
  step,
  disabled,
}: GuidedInputProps) {
  const [showHelp, setShowHelp] = useState(false)

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
              aria-label="Help"
            >
              <HelpCircle size={13} />
            </button>
          )}
        </label>
        {defaultNote && (
          <span className="text-2xs text-blue-400 font-normal">Smart default</span>
        )}
      </div>

      {showHelp && help && (
        <p className="text-xs text-slate-400 bg-slate-800/60 rounded-md px-3 py-2 border border-slate-700/50 animate-fade-in">
          {help}
        </p>
      )}

      <div className={`
        flex items-center rounded-lg border transition-colors
        ${error ? 'border-red-500/60 bg-red-950/10' : 'border-slate-700 bg-slate-800/40 focus-within:border-blue-500/60'}
        ${disabled ? 'opacity-50' : ''}
      `}>
        {prefix && (
          <span className="pl-3 pr-1 text-slate-400 text-sm select-none">{prefix}</span>
        )}
        <input
          type={type}
          value={value}
          onChange={e => onChange(e.target.value)}
          placeholder={placeholder}
          disabled={disabled}
          min={min}
          max={max}
          step={step}
          className="
            flex-1 bg-transparent px-3 py-2.5 text-sm text-slate-100
            placeholder-slate-500 outline-none tabular-nums
            [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none
            [&::-webkit-inner-spin-button]:appearance-none
          "
        />
        {suffix && (
          <span className="pr-3 pl-1 text-slate-400 text-sm select-none">{suffix}</span>
        )}
      </div>

      {defaultNote && (
        <p className="text-2xs text-slate-500">{defaultNote}</p>
      )}

      {error && (
        <p className="text-xs text-red-400">{error}</p>
      )}
    </div>
  )
}
