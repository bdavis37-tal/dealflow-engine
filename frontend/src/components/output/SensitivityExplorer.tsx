import { useState } from 'react'
import type { SensitivityMatrix, DealInput, DealOutput } from '../../types/deal'
import HeatmapCell from '../shared/HeatmapCell'
import ScenarioNarrative from './ScenarioNarrative'

interface SensitivityExplorerProps {
  matrices: SensitivityMatrix[]
  dealInput?: DealInput
  dealOutput?: DealOutput
  aiAvailable?: boolean
}

export default function SensitivityExplorer({
  matrices,
  dealInput,
  dealOutput,
  aiAvailable = false,
}: SensitivityExplorerProps) {
  const [activeIdx, setActiveIdx] = useState(0)
  const [pinned, setPinned] = useState<[number, number] | null>(null)

  const matrix = matrices[activeIdx]
  if (!matrix) return null

  const handleCellClick = (r: number, c: number) => {
    if (pinned && pinned[0] === r && pinned[1] === c) {
      setPinned(null)
    } else {
      setPinned([r, c])
    }
  }

  const pinnedLabel = pinned
    ? `Row: ${matrix.row_values[pinned[0]]} | Col: ${matrix.col_values[pinned[1]]} → ${matrix.data_labels[pinned[0]][pinned[1]]}`
    : null

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-slate-100">Sensitivity Explorer</h2>
        <p className="text-xs text-slate-500">Showing Year 1 Accretion / Dilution</p>
      </div>

      {/* Matrix tabs */}
      <div className="flex gap-2 mb-5 flex-wrap">
        {matrices.map((m, idx) => (
          <button
            key={idx}
            onClick={() => { setActiveIdx(idx); setPinned(null) }}
            className={`
              px-3 py-1.5 rounded-lg text-xs font-medium transition-all
              ${activeIdx === idx
                ? 'bg-blue-600 text-white'
                : 'bg-slate-800 text-slate-400 hover:text-slate-200 border border-slate-700'
              }
            `}
          >
            {m.title}
          </button>
        ))}
      </div>

      {/* Pinned scenario info */}
      {pinnedLabel && (
        <div className="mb-4 rounded-lg border border-blue-800/40 bg-blue-950/15 px-4 py-2 text-xs text-blue-300">
          📌 Pinned: {pinnedLabel}
        </div>
      )}

      {/* Heatmap */}
      <div className="overflow-x-auto">
        <div className="min-w-[500px]">
          {/* Column header */}
          <div className="flex gap-1 mb-1">
            <div className="w-20 flex-shrink-0" />
            {matrix.col_values.map((cv, cidx) => (
              <div key={cidx} className="flex-1 text-center text-2xs text-slate-500 tabular-nums">
                {typeof cv === 'number' ? cv.toFixed(0) : cv}
              </div>
            ))}
          </div>

          {/* Axis label — col */}
          <div className="flex mb-3">
            <div className="w-20 flex-shrink-0" />
            <div className="flex-1 text-center text-2xs text-slate-600 italic">{matrix.col_label}</div>
          </div>

          {/* Rows */}
          {matrix.data.map((row, ridx) => (
            <div key={ridx} className="flex gap-1 mb-1 items-center">
              <div className="w-20 flex-shrink-0 text-right text-2xs text-slate-500 tabular-nums pr-2">
                {matrix.row_values[ridx].toFixed(0)}
              </div>
              {row.map((val, cidx) => (
                <div key={cidx} className="flex-1">
                  <HeatmapCell
                    value={val}
                    label={matrix.data_labels[ridx][cidx]}
                    isHighlighted={pinned !== null && pinned[0] === ridx && pinned[1] === cidx}
                    onClick={() => handleCellClick(ridx, cidx)}
                  />
                </div>
              ))}
            </div>
          ))}

          {/* Row axis label */}
          <div className="flex mt-2">
            <div className="w-20 flex-shrink-0" />
            <div className="flex-1 text-center text-2xs text-slate-600 italic">{matrix.row_label}</div>
          </div>
        </div>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-3 mt-4 text-2xs text-slate-500">
        <span>Less accretive →</span>
        <div className="flex gap-0.5">
          {['bg-red-600', 'bg-red-700/70', 'bg-red-800/50', 'bg-amber-800/40', 'bg-green-800/60', 'bg-green-700/80', 'bg-green-600'].map((cls, i) => (
            <div key={i} className={`w-6 h-3 rounded-sm ${cls}`} />
          ))}
        </div>
        <span>← More accretive</span>
      </div>

      {/* AI Scenario Narrative — appears when a cell is pinned */}
      {pinned && dealInput && dealOutput && (
        <ScenarioNarrative
          dealInput={dealInput}
          dealOutput={dealOutput}
          rowLabel={matrix.row_label}
          colLabel={matrix.col_label}
          rowValue={matrix.row_values[pinned[0]]}
          colValue={matrix.col_values[pinned[1]]}
          accretionPct={matrix.data[pinned[0]][pinned[1]] * 100}
          aiAvailable={aiAvailable}
        />
      )}
    </div>
  )
}
