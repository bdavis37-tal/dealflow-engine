import type { AnalysisEvidence } from '../../types/evidence'

export default function EvidencePanel({ evidence, analysis }: { evidence?: AnalysisEvidence | null; analysis?: { input: unknown; output: unknown } }) {
  if (!evidence) return null
  return <details className="my-5 rounded-xl border border-slate-700 bg-slate-900 p-4 text-sm">
    <summary className="cursor-pointer text-slate-200">Assumptions and sources · {evidence.observed_count} observed · {evidence.assumed_count} assumed</summary>
    <p className="mt-3 text-slate-400">Dataset {evidence.dataset_version} · engine {evidence.engine_version}. Recalculating with another release may change the result.</p>
    {evidence.limitations.map(note => <p key={note} className="mt-2 text-amber-200">{note}</p>)}
    <div className="mt-3 max-h-80 overflow-auto space-y-3">
      {evidence.records.map(record => <div key={record.id} className="border-t border-slate-800 pt-2">
        <p className="text-slate-200">{record.metric.replace(/_/g, ' ')}: {record.value} {record.unit} <span className="text-slate-500">({record.statistic}; {record.status})</span></p>
        <p className="text-xs text-slate-400">{record.basis} · {record.observation_period ?? 'Observation date unknown'} · {record.freshness}</p>
        {record.source_url && <a href={record.source_url} target="_blank" rel="noreferrer" className="text-blue-300 underline">Source · {record.source_locator}</a>}
        {record.limitations.map(note => <p key={note} className="text-xs text-slate-500">{note}</p>)}
      </div>)}
    </div>
    {analysis && <button className="mt-3 text-blue-300 underline" onClick={() => {
      const blob = new Blob([JSON.stringify({schema_version: 2, ...analysis}, null, 2)], {type: 'application/json'})
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a'); a.href = url; a.download = `dealflow-analysis-${evidence.dataset_version}.json`; a.click()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    }}>Download inputs, results and evidence</button>}
    <p className="mt-3 break-all text-xs text-slate-600">Dataset fingerprint: {evidence.dataset_hash}</p>
  </details>
}
