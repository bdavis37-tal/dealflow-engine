interface HeatmapCellProps {
  value: number   // accretion/dilution as decimal (e.g. 0.05 = 5%)
  label: string
  isHighlighted?: boolean
  onClick?: () => void
  onMouseEnter?: () => void
  onMouseLeave?: () => void
}

function getColorClass(value: number): string {
  // Color: green for accretive (positive), red for dilutive (negative)
  if (value > 0.10) return 'bg-green-600 text-white'
  if (value > 0.05) return 'bg-green-700/80 text-green-100'
  if (value > 0.02) return 'bg-green-800/60 text-green-200'
  if (value > -0.02) return 'bg-amber-800/40 text-amber-200'
  if (value > -0.05) return 'bg-red-800/50 text-red-200'
  if (value > -0.10) return 'bg-red-700/70 text-red-100'
  return 'bg-red-600 text-white'
}

export default function HeatmapCell({
  value,
  label,
  isHighlighted,
  onClick,
  onMouseEnter,
  onMouseLeave,
}: HeatmapCellProps) {
  return (
    <div
      className={`
        relative h-12 flex items-center justify-center text-xs font-semibold
        tabular-nums cursor-pointer transition-all rounded-sm
        ${getColorClass(value)}
        ${isHighlighted ? 'ring-2 ring-white/60 z-10 scale-105' : 'hover:brightness-110'}
      `}
      onClick={onClick}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
      title={label}
    >
      {label}
    </div>
  )
}
