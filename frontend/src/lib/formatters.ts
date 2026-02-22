/**
 * Formatting utilities for financial figures.
 * Uses tabular-nums where possible for alignment in tables.
 */

export function formatCurrency(value: number, compact = false): string {
  const abs = Math.abs(value)
  const sign = value < 0 ? '-' : ''

  if (compact) {
    if (abs >= 1_000_000_000) return `${sign}$${(abs / 1_000_000_000).toFixed(1)}B`
    if (abs >= 1_000_000) return `${sign}$${(abs / 1_000_000).toFixed(1)}M`
    if (abs >= 1_000) return `${sign}$${(abs / 1_000).toFixed(0)}K`
    return `${sign}$${abs.toFixed(0)}`
  }

  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value)
}

export function formatCurrencyCompact(value: number): string {
  return formatCurrency(value, true)
}

/** Format as accounting style: negative numbers in (parentheses). */
export function formatAccounting(value: number): string {
  if (value < 0) return `(${formatCurrency(Math.abs(value))})`
  return formatCurrency(value)
}

export function formatPercentage(value: number, decimals = 1, showSign = false): string {
  const formatted = `${Math.abs(value).toFixed(decimals)}%`
  if (showSign) return value >= 0 ? `+${formatted}` : `-${formatted}`
  return value < 0 ? `-${formatted}` : formatted
}

export function formatMultiple(value: number, decimals = 1): string {
  return `${value.toFixed(decimals)}×`
}

export function formatEPS(value: number): string {
  const sign = value >= 0 ? '' : '-'
  return `${sign}$${Math.abs(value).toFixed(2)}`
}

export function formatEPSChange(value: number): string {
  const sign = value >= 0 ? '+' : '-'
  return `${sign}$${Math.abs(value).toFixed(2)}`
}

/** Format a decimal interest rate as percentage string. */
export function formatRate(value: number): string {
  return `${(value * 100).toFixed(2)}%`
}

/** Format large numbers with thousands separators. */
export function formatNumber(value: number): string {
  return new Intl.NumberFormat('en-US').format(Math.round(value))
}
