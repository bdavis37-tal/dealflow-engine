/**
 * Formatting utilities for financial figures.
 * Uses tabular-nums where possible for alignment in tables.
 */

/**
 * Round a number to eliminate IEEE 754 floating-point noise.
 * Converts values like 0.12300000000000001 → 0.123 and
 * 12.000000000000002 → 12. Uses toPrecision(12) to strip
 * noise digits while preserving meaningful precision.
 */
export function roundFinancial(value: number): number {
  if (!Number.isFinite(value)) return value
  return Number(value.toPrecision(12))
}

/**
 * Format a monetary value denominated in MILLIONS USD (project convention:
 * `50.0` means $50M). Mirrors the backend's `_format_currency`.
 * E.g. 50 → "$50.0M", 1800 → "$1.8B", 0.25 → "$250K".
 */
export function formatCurrency(value: number): string {
  const v = roundFinancial(value)
  const abs = Math.abs(v)
  const sign = v < 0 ? '-' : ''

  if (abs >= 1_000) return `${sign}$${(abs / 1_000).toFixed(1)}B`
  if (abs >= 1) return `${sign}$${abs.toFixed(1)}M`
  if (abs >= 0.001) return `${sign}$${(abs * 1_000).toFixed(0)}K`
  return '$0'
}

export function formatCurrencyCompact(value: number): string {
  return formatCurrency(value)
}

/** Format as accounting style: negative numbers in (parentheses). Millions-denominated. */
export function formatAccounting(value: number): string {
  if (value < 0) return `(${formatCurrency(Math.abs(value))})`
  return formatCurrency(value)
}

export function formatPercentage(value: number, decimals = 1, showSign = false): string {
  const v = roundFinancial(value)
  const formatted = `${Math.abs(v).toFixed(decimals)}%`
  if (showSign) return v >= 0 ? `+${formatted}` : `-${formatted}`
  return v < 0 ? `-${formatted}` : formatted
}

export function formatMultiple(value: number, decimals = 1): string {
  return `${roundFinancial(value).toFixed(decimals)}×`
}

export function formatEPS(value: number): string {
  const v = roundFinancial(value)
  const sign = v >= 0 ? '' : '-'
  return `${sign}$${Math.abs(v).toFixed(2)}`
}

export function formatEPSChange(value: number): string {
  const v = roundFinancial(value)
  const sign = v >= 0 ? '+' : '-'
  return `${sign}$${Math.abs(v).toFixed(2)}`
}

/** Format a decimal interest rate as percentage string. */
export function formatRate(value: number): string {
  return `${roundFinancial(value * 100).toFixed(2)}%`
}

/** Format large numbers with thousands separators. */
export function formatNumber(value: number): string {
  return new Intl.NumberFormat('en-US').format(Math.round(roundFinancial(value)))
}
