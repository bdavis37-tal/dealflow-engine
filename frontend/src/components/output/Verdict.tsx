import type { DealVerdict } from '../../types/deal'

interface VerdictProps {
  verdict: DealVerdict
  headline: string
  subtext: string
}

const VERDICT_STYLES: Record<DealVerdict, {
  bg: string
  border: string
  badge: string
  badgeText: string
  glow: string
}> = {
  green: {
    bg: 'bg-green-glow',
    border: 'border-green-800/40',
    badge: 'bg-green-600',
    badgeText: 'Accretive',
    glow: '',
  },
  yellow: {
    bg: 'bg-amber-glow',
    border: 'border-amber-800/40',
    badge: 'bg-amber-600',
    badgeText: 'Marginal',
    glow: '',
  },
  red: {
    bg: 'bg-red-glow',
    border: 'border-red-800/40',
    badge: 'bg-red-600',
    badgeText: 'Dilutive',
    glow: '',
  },
}

export default function Verdict({ verdict, headline, subtext }: VerdictProps) {
  const styles = VERDICT_STYLES[verdict]

  return (
    <div className={`
      rounded-2xl border p-8 ${styles.bg} ${styles.border} animate-slide-up
    `}>
      <div className="flex items-center gap-3 mb-4">
        <span className={`
          inline-flex items-center px-3 py-1 rounded-full text-xs font-bold text-white
          ${styles.badge}
        `}>
          {styles.badgeText}
        </span>
        <span className="text-xs text-slate-500">Deal Analysis</span>
      </div>

      <h2 className={`
        text-2xl sm:text-3xl font-bold mb-3 leading-tight
        ${verdict === 'green' ? 'text-green-300' : verdict === 'yellow' ? 'text-amber-300' : 'text-red-300'}
      `}>
        {headline}
      </h2>

      <p className="text-slate-400 text-sm sm:text-base leading-relaxed max-w-2xl">
        {subtext}
      </p>
    </div>
  )
}
