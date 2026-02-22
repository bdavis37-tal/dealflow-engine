import type { HealthStatus } from '../../types/deal'

interface MetricCardProps {
  name: string
  value: string
  description?: string
  health?: HealthStatus
  benchmarkLow?: number
  benchmarkMedian?: number
  benchmarkHigh?: number
  currentValue?: number
  large?: boolean
}

const HEALTH_COLORS: Record<HealthStatus, string> = {
  good: 'text-green-400',
  fair: 'text-amber-400',
  poor: 'text-red-400',
  critical: 'text-red-500',
}

const HEALTH_BG: Record<HealthStatus, string> = {
  good: 'border-green-800/40 bg-green-950/10',
  fair: 'border-amber-800/40 bg-amber-950/10',
  poor: 'border-red-800/40 bg-red-950/10',
  critical: 'border-red-700/50 bg-red-950/20',
}

export default function MetricCard({
  name,
  value,
  description,
  health,
  benchmarkLow,
  benchmarkMedian,
  benchmarkHigh,
  currentValue,
  large,
}: MetricCardProps) {
  const hasBenchmark = benchmarkLow !== undefined && benchmarkHigh !== undefined && currentValue !== undefined
  const range = hasBenchmark ? (benchmarkHigh! - benchmarkLow!) : 0
  const position = hasBenchmark && range > 0
    ? Math.min(100, Math.max(0, ((currentValue! - benchmarkLow!) / range) * 100))
    : 0

  return (
    <div className={`
      rounded-xl border p-5 transition-all
      ${health ? HEALTH_BG[health] : 'border-slate-700 bg-slate-800/20'}
    `}>
      <div className="text-xs text-slate-500 mb-2 font-medium">{name}</div>
      <div className={`
        font-bold tabular-nums mb-1
        ${large ? 'text-3xl' : 'text-2xl'}
        ${health ? HEALTH_COLORS[health] : 'text-slate-100'}
      `}>
        {value}
      </div>
      {description && (
        <p className="text-xs text-slate-500 leading-relaxed">{description}</p>
      )}

      {/* Benchmark range bar */}
      {hasBenchmark && (
        <div className="mt-3">
          <div className="relative h-1.5 bg-slate-700 rounded-full overflow-hidden">
            {/* Median indicator */}
            {benchmarkMedian !== undefined && range > 0 && (
              <div
                className="absolute top-0 w-0.5 h-full bg-slate-500 z-10"
                style={{ left: `${((benchmarkMedian - benchmarkLow!) / range) * 100}%` }}
              />
            )}
            {/* Current value dot */}
            <div
              className={`absolute top-0 w-2 h-2 rounded-full -mt-0.5 z-20 ${health ? HEALTH_COLORS[health].replace('text-', 'bg-') : 'bg-blue-400'}`}
              style={{ left: `calc(${position}% - 4px)` }}
            />
          </div>
          <div className="flex justify-between text-2xs text-slate-600 mt-1">
            <span>{benchmarkLow?.toFixed(0)}</span>
            <span className="text-slate-500">Typical range</span>
            <span>{benchmarkHigh?.toFixed(0)}</span>
          </div>
        </div>
      )}
    </div>
  )
}
