export interface BenchmarkRecord {
  id: string
  metric: string
  value: number
  statistic: string
  unit: string
  basis: string
  status: 'observed' | 'derived' | 'assumed'
  source_url: string | null
  source_locator: string | null
  observation_period: string | null
  freshness: string
  limitations: string[]
}

export interface AnalysisEvidence {
  engine_version: string
  dataset_version: string
  dataset_hash: string
  input_fingerprint: string
  records: BenchmarkRecord[]
  observed_count: number
  assumed_count: number
  limitations: string[]
}
