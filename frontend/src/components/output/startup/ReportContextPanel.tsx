/**
 * ReportContextPanel — perspective switch, preparer identity, and preparer
 * notes editor for the exported valuation report.
 *
 * Everything captured here is PRESENTATION-LAYER ONLY: it shapes the report
 * narrative (cover attribution + the Preparer's Representations page) and is
 * never sent to the valuation API. Computed results are bit-identical
 * regardless of what is entered here.
 */
import { useState } from 'react'
import { ChevronDown, ChevronUp, FileText, Plus, Trash2 } from 'lucide-react'
import type {
  ReportContext,
  ReportPerspective,
  PreparerNote,
  NoteAnchor,
  ContendedPlacement,
  StartupValuationOutput,
} from '../../../types/startup'
import {
  PERSPECTIVE_LABELS,
  NOTE_ANCHOR_LABELS,
  CONTENDED_PLACEMENT_LABELS,
  VERTICAL_LABELS,
  STAGE_LABELS,
} from '../../../types/startup'
import { computeModelPlacement } from './placementUtils'

interface Props {
  output: StartupValuationOutput
  reportContext: ReportContext
  onUpdate: (updates: Partial<ReportContext>) => void
  onAddNote: () => void
  onUpdateNote: (id: string, updates: Partial<Omit<PreparerNote, 'id'>>) => void
  onRemoveNote: (id: string) => void
}

const PERSPECTIVES: ReportPerspective[] = ['founder', 'investor', 'advisor']
const ANCHORS: NoteAnchor[] = ['team', 'traction', 'product', 'market', 'method', 'benchmark_placement']
const PLACEMENTS: ContendedPlacement[] = ['p25_p50', 'p50_p75', 'above_p75', 'above_p95']

export default function ReportContextPanel({
  output, reportContext, onUpdate, onAddNote, onUpdateNote, onRemoveNote,
}: Props) {
  const [open, setOpen] = useState(false)

  const placement = computeModelPlacement(
    output.blended_valuation,
    output.benchmark_p25,
    output.benchmark_p50,
    output.benchmark_p75,
    output.benchmark_p95,
  )
  const cohort = `${VERTICAL_LABELS[output.vertical]} ${STAGE_LABELS[output.stage]}`
  const noteCount = reportContext.notes.length

  return (
    <div className="rounded-xl border border-slate-700 bg-slate-800/30">
      {/* Collapsible header */}
      <button
        className="w-full px-5 py-4 flex items-center justify-between text-left"
        onClick={() => setOpen(o => !o)}
      >
        <div className="flex items-center gap-2">
          <FileText size={16} className="text-purple-400" />
          <span className="text-sm font-semibold text-slate-300 uppercase tracking-wider">
            Report Context &amp; Preparer Notes
          </span>
          <span className="text-xs text-slate-500">
            {PERSPECTIVE_LABELS[reportContext.perspective]} perspective
            {noteCount > 0 ? ` · ${noteCount} note${noteCount === 1 ? '' : 's'}` : ''}
          </span>
        </div>
        {open ? <ChevronUp size={14} className="text-slate-500" /> : <ChevronDown size={14} className="text-slate-500" />}
      </button>

      {open && (
        <div className="px-5 pb-5 space-y-5 border-t border-slate-700 pt-4">
          {/* Perspective + prepared by */}
          <div className="flex flex-wrap items-end gap-4">
            <div>
              <p className="text-xs text-slate-500 mb-1.5">Report perspective</p>
              <div className="inline-flex rounded-lg border border-slate-600 overflow-hidden">
                {PERSPECTIVES.map(p => (
                  <button
                    key={p}
                    onClick={() => onUpdate({ perspective: p })}
                    className={`px-4 py-1.5 text-sm transition-colors ${
                      reportContext.perspective === p
                        ? 'bg-purple-900/50 text-purple-200 font-medium'
                        : 'text-slate-400 hover:text-slate-200 hover:bg-slate-700/50'
                    }`}
                  >
                    {PERSPECTIVE_LABELS[p]}
                  </button>
                ))}
              </div>
            </div>
            <div className="flex-1 min-w-[200px]">
              <p className="text-xs text-slate-500 mb-1.5">Prepared by (optional)</p>
              <input
                type="text"
                value={reportContext.prepared_by ?? ''}
                onChange={e => onUpdate({ prepared_by: e.target.value || undefined })}
                placeholder="Display name shown on the report cover"
                className="w-full px-3 py-1.5 rounded-lg bg-slate-900/60 border border-slate-600 text-sm text-slate-200 placeholder-slate-600 focus:border-purple-500 focus:outline-none"
              />
            </div>
          </div>

          {/* Notes editor */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <p className="text-xs text-slate-500">
                Preparer notes — claims the reader can independently verify. They appear in a dedicated report
                section, clearly separated from computed results.
              </p>
              <button
                onClick={onAddNote}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-purple-600/50 bg-purple-900/20 text-purple-300 hover:bg-purple-900/40 text-xs font-medium transition-all flex-shrink-0 ml-4"
              >
                <Plus size={12} /> Add note
              </button>
            </div>

            {reportContext.notes.length === 0 && (
              <p className="text-xs text-slate-600 italic py-2">No notes yet.</p>
            )}

            <div className="space-y-3">
              {reportContext.notes.map((n, i) => (
                <div key={n.id} className="rounded-lg border border-slate-700 bg-slate-900/40 p-4 space-y-2">
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-slate-500 font-medium">Note {i + 1}</span>
                      <select
                        value={n.anchor}
                        onChange={e => onUpdateNote(n.id, { anchor: e.target.value as NoteAnchor })}
                        className="px-2 py-1 rounded bg-slate-800 border border-slate-600 text-xs text-slate-300 focus:border-purple-500 focus:outline-none"
                      >
                        {ANCHORS.map(a => (
                          <option key={a} value={a}>{NOTE_ANCHOR_LABELS[a]}</option>
                        ))}
                      </select>
                    </div>
                    <button
                      onClick={() => onRemoveNote(n.id)}
                      className="text-slate-600 hover:text-red-400 transition-colors"
                      title="Remove note"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                  <textarea
                    value={n.claim}
                    onChange={e => onUpdateNote(n.id, { claim: e.target.value })}
                    placeholder="Claim — what the preparer represents to the reader"
                    rows={2}
                    className="w-full px-3 py-2 rounded-lg bg-slate-800/70 border border-slate-600 text-sm text-slate-200 placeholder-slate-600 focus:border-purple-500 focus:outline-none resize-y"
                  />
                  <input
                    type="text"
                    value={n.evidence ?? ''}
                    onChange={e => onUpdateNote(n.id, { evidence: e.target.value || undefined })}
                    placeholder="How can the reader verify this? Contract vehicle, award, LOI, link…"
                    className="w-full px-3 py-1.5 rounded-lg bg-slate-800/70 border border-slate-600 text-xs text-slate-300 placeholder-slate-600 focus:border-purple-500 focus:outline-none"
                  />
                </div>
              ))}
            </div>
          </div>

          {/* Placement contention */}
          <div className="rounded-lg border border-slate-700 bg-slate-900/40 p-4">
            <p className="text-xs text-slate-500 mb-3">Benchmark placement</p>
            <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
              <div>
                <p className="text-2xs text-slate-600 uppercase tracking-wider mb-1">Model placement (computed)</p>
                <p className="text-sm text-slate-200 font-medium">
                  {placement.label} · {cohort} cohort
                </p>
              </div>
              <div>
                <p className="text-2xs text-slate-600 uppercase tracking-wider mb-1">Preparer contends</p>
                <select
                  value={reportContext.contended_placement ?? ''}
                  onChange={e =>
                    onUpdate({
                      contended_placement: e.target.value === '' ? null : (e.target.value as ContendedPlacement),
                    })
                  }
                  className="px-3 py-1.5 rounded-lg bg-slate-800 border border-slate-600 text-sm text-slate-300 focus:border-purple-500 focus:outline-none"
                >
                  <option value="">No contention</option>
                  {PLACEMENTS.map(p => (
                    <option key={p} value={p}>{CONTENDED_PLACEMENT_LABELS[p]}</option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          {/* Invariance footnote — permanent */}
          <p className="text-xs text-slate-600 leading-relaxed">
            Notes and perspective affect the report narrative only. Computed results are independent of preparer
            role and are never modified by notes.
          </p>
        </div>
      )}
    </div>
  )
}
