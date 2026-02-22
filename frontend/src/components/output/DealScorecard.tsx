import type { ScorecardMetric } from '../../types/deal'
import MetricCard from '../shared/MetricCard'

interface DealScorecardProps {
  metrics: ScorecardMetric[]
}

export default function DealScorecard({ metrics }: DealScorecardProps) {
  return (
    <div>
      <h2 className="text-lg font-semibold text-slate-100 mb-4">Deal Scorecard</h2>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {metrics.map(m => (
          <MetricCard
            key={m.name}
            name={m.name}
            value={m.formatted_value}
            description={m.description}
            health={m.health_status}
            benchmarkLow={m.benchmark_low}
            benchmarkMedian={m.benchmark_median}
            benchmarkHigh={m.benchmark_high}
            currentValue={m.value}
          />
        ))}
      </div>
    </div>
  )
}
