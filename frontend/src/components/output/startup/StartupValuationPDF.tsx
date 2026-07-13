/**
 * StartupValuationPDF — investor-facing PDF export.
 *
 * Headline logic: an investor reading this wants two numbers — the calibrated
 * valuation range and what the preparer is asking for. When an ask is stated
 * it headlines the cover next to the range (with its cohort placement), the
 * benchmark table slots it into the distribution and shades the preparer's
 * contended band, and the dilution model prices the current round at the ask.
 * The blended point estimate is demoted to "model midpoint" — a derivable
 * detail on the methods page, and the headline fallback only when no ask or
 * placement is stated.
 *
 * Preparer advocacy stays quarantined in a clearly labeled representations
 * section that the model provably does not incorporate — report context
 * (perspective, notes, contended placement) lives only in frontend state and
 * is never sent to the valuation API. The ask, by contrast, IS a model input:
 * it prices deal mechanics (dilution, SAFE cap) but never moves the blend or
 * range.
 *
 * Uses @react-pdf/renderer for in-browser PDF generation.
 */
import { Fragment } from 'react'
import { Document, Page, Text, View, StyleSheet, PDFDownloadLink, Svg, Rect, Line } from '@react-pdf/renderer'
import type { StartupValuationOutput, StartupInput, ReportContext, PreparerNote, ContendedPlacement } from '../../../types/startup'
import {
  VERTICAL_LABELS, STAGE_LABELS, GEOGRAPHY_LABELS,
  INSTRUMENT_LABELS, PRODUCT_STAGE_LABELS,
  PERSPECTIVE_LABELS, NOTE_ANCHOR_LABELS, CONTENDED_PLACEMENT_LABELS,
} from '../../../types/startup'
import { computeModelPlacement, contentionConsistentWithModel } from './placementUtils'
import { FileDown } from 'lucide-react'

// ---------------------------------------------------------------------------
// Formatting helpers (PDF context — no DOM APIs)
// ---------------------------------------------------------------------------

function fmtM(v: number | null | undefined): string {
  if (v == null) return '—'
  return `$${new Intl.NumberFormat('en-US').format(Math.round(v))}M`
}

function fmtPct(v: number): string {
  return `${(v * 100).toFixed(1)}%`
}

function fmtMultiple(v: number): string {
  return `${v.toFixed(1)}×`
}

/** Notes that actually carry a claim — empty drafts are never printed. */
function printableNotes(ctx: ReportContext): PreparerNote[] {
  return ctx.notes.filter(n => n.claim.trim().length > 0)
}

// ---------------------------------------------------------------------------
// Palette & styles
// ---------------------------------------------------------------------------

const C = {
  black:    '#0a0a0a',
  ink:      '#1a1a2e',
  slate:    '#374151',
  mid:      '#6b7280',
  light:    '#9ca3af',
  rule:     '#e5e7eb',
  bg:       '#f9fafb',
  white:    '#ffffff',
  accent:   '#6d28d9',   // purple — matches Startup mode
  accentLt: '#ede9fe',
}

const s = StyleSheet.create({
  page:         { fontFamily: 'Helvetica', fontSize: 9, color: C.ink, backgroundColor: C.white, paddingHorizontal: 48, paddingVertical: 44 },
  // Cover
  coverAccent:  { height: 6, backgroundColor: C.accent, marginBottom: 32 },
  coverTitle:   { fontSize: 26, fontFamily: 'Helvetica-Bold', color: C.ink, marginBottom: 6 },
  coverSub:     { fontSize: 11, color: C.slate, marginBottom: 4 },
  coverMeta:    { fontSize: 9, color: C.mid, marginTop: 20 },
  coverRule:    { height: 1, backgroundColor: C.rule, marginTop: 28, marginBottom: 10 },
  coverDiscl:   { fontSize: 7.5, color: C.light, lineHeight: 1.4 },
  // Section headers
  sectionHead:  { fontSize: 7, fontFamily: 'Helvetica-Bold', color: C.accent, textTransform: 'uppercase', letterSpacing: 1.2, marginBottom: 8, marginTop: 20 },
  rule:         { height: 1, backgroundColor: C.rule, marginBottom: 10 },
  // Key-value rows
  row:          { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 4, borderBottomWidth: 1, borderBottomColor: C.rule },
  rowLabel:     { fontSize: 9, color: C.mid, flex: 1 },
  rowValue:     { fontSize: 9, fontFamily: 'Helvetica-Bold', color: C.ink, textAlign: 'right' },
  // Highlight box (range-first headline)
  hlBox:        { backgroundColor: C.accentLt, borderRadius: 4, padding: 14, marginBottom: 12 },
  hlLabel:      { fontSize: 8, fontFamily: 'Helvetica-Bold', color: C.accent, letterSpacing: 1, marginBottom: 5 },
  hlValue:      { fontSize: 22, fontFamily: 'Helvetica-Bold', color: C.ink },
  hlUnit:       { fontSize: 10, fontFamily: 'Helvetica', color: C.slate },
  hlSub:        { fontSize: 8, color: C.slate, marginTop: 3 },
  // Paired headline: the range AND what the preparer is asking for
  hlGrid:       { flexDirection: 'row', marginBottom: 12 },
  hlCellRange:  { flex: 1.1, backgroundColor: C.bg, borderWidth: 1, borderColor: C.rule, borderRadius: 4, padding: 14, marginRight: 8 },
  hlCellAsk:    { flex: 1, backgroundColor: C.accentLt, borderRadius: 4, padding: 14 },
  hlValueSm:    { fontSize: 17, fontFamily: 'Helvetica-Bold', color: C.ink },
  // Method card
  methodCard:   { borderWidth: 1, borderColor: C.rule, borderRadius: 4, padding: 10, marginBottom: 8 },
  methodLabel:  { fontSize: 10, fontFamily: 'Helvetica-Bold', color: C.ink, marginBottom: 4 },
  methodValue:  { fontSize: 14, fontFamily: 'Helvetica-Bold', color: C.accent, marginBottom: 4 },
  methodReason: { fontSize: 8, color: C.slate, lineHeight: 1.45 },
  methodRange:  { fontSize: 8, color: C.mid, marginTop: 3 },
  // Table
  tableHead:    { flexDirection: 'row', backgroundColor: C.bg, paddingVertical: 5, paddingHorizontal: 6, borderBottomWidth: 1, borderBottomColor: C.rule },
  tableRow:     { flexDirection: 'row', paddingVertical: 5, paddingHorizontal: 6, borderBottomWidth: 1, borderBottomColor: C.rule },
  tableCell:    { fontSize: 8.5, color: C.ink, flex: 1 },
  tableCellHd:  { fontSize: 7.5, fontFamily: 'Helvetica-Bold', color: C.mid, textTransform: 'uppercase', flex: 1 },
  tableRight:   { textAlign: 'right' },
  // Representations
  represBox:    { borderWidth: 1, borderColor: C.rule, borderLeftWidth: 3, borderLeftColor: C.accent, borderRadius: 3, padding: 10, marginBottom: 8, backgroundColor: C.bg },
  represHead:   { fontSize: 9, fontFamily: 'Helvetica-Bold', color: C.ink, marginBottom: 4 },
  represClaim:  { fontSize: 8.5, color: C.slate, lineHeight: 1.5 },
  represEvid:   { fontSize: 8, color: C.mid, marginTop: 4 },
  represEvidNone:{ fontSize: 8, color: C.light, marginTop: 4, fontFamily: 'Helvetica-Oblique' },
  disclBox:     { borderWidth: 1, borderColor: C.rule, borderRadius: 3, padding: 10, marginBottom: 14, backgroundColor: C.bg },
  // Chart text
  chartLabel:   { position: 'absolute', fontSize: 7, color: C.slate },
  chartValue:   { position: 'absolute', fontSize: 7, fontFamily: 'Helvetica-Bold', color: C.ink, textAlign: 'right' },
  chartBench:   { position: 'absolute', fontSize: 6, color: C.light, textAlign: 'center' },
  legendRow:    { flexDirection: 'row', flexWrap: 'wrap', marginTop: 6 },
  legendItem:   { flexDirection: 'row', alignItems: 'center', marginRight: 14, marginBottom: 2 },
  legendText:   { fontSize: 6.5, color: C.mid, marginLeft: 4 },
  // Footer
  footer:       { position: 'absolute', bottom: 28, left: 48, right: 48, flexDirection: 'row', justifyContent: 'space-between' },
  footerText:   { fontSize: 7, color: C.light },
})

// ---------------------------------------------------------------------------
// Reusable PDF sub-components
// ---------------------------------------------------------------------------

function KVRow({ label, value }: { label: string; value: string }) {
  return (
    <View style={s.row}>
      <Text style={s.rowLabel}>{label}</Text>
      <Text style={s.rowValue}>{value}</Text>
    </View>
  )
}

function SectionHead({ title }: { title: string }) {
  return (
    <>
      <Text style={s.sectionHead}>{title}</Text>
      <View style={s.rule} />
    </>
  )
}

function PageFooter({ company }: { company: string }) {
  const date = new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })
  return (
    <View style={s.footer} fixed>
      <Text style={s.footerText}>{company} — Valuation Report · {date}</Text>
      <Text style={s.footerText} render={({ pageNumber }) => `Dealflow Engine  ·  Page ${pageNumber}`} />
    </View>
  )
}

/**
 * The percentile anchors bounding the preparer's asserted position: the
 * explicit contended placement when set, otherwise the band the ask falls in.
 */
function preparerBand(
  contended: ContendedPlacement | null,
  askPercentile: number | null,
  askLabel: string | null,
): string[] {
  if (contended != null) {
    return {
      p25_p50: ['P25', 'P50'],
      p50_p75: ['P50', 'P75'],
      above_p75: ['P75'],
      above_p95: ['P95'],
    }[contended]
  }
  if (askPercentile != null) {
    if (askPercentile >= 95) return ['P95']
    if (askPercentile >= 75) return ['P75', 'P95']
    if (askPercentile >= 50) return ['P50', 'P75']
    return ['P25', 'P50']
  }
  if (askLabel === 'above P95') return ['P95']
  if (askLabel === 'above P75') return ['P75']
  if (askLabel === 'below P25') return ['P25']
  return []
}

function BenchmarkTable({ output, ask, contended }: {
  output: StartupValuationOutput
  ask: number | null
  contended: ContendedPlacement | null
}) {
  const askPlacement = ask != null
    ? computeModelPlacement(ask, output.benchmark_p25, output.benchmark_p50, output.benchmark_p75, output.benchmark_p95)
    : null
  const band = (ask != null || contended != null)
    ? preparerBand(contended, askPlacement?.approx_percentile ?? null, askPlacement?.label ?? null)
    : []

  type Row = { key: string; label: string; val: number | null; isAsk?: boolean }
  const rows: Row[] = [
    { key: 'P25', label: 'P25 (Bottom Quartile)', val: output.benchmark_p25 },
    { key: 'P50', label: 'P50 (Median)',          val: output.benchmark_p50 },
    { key: 'P75', label: 'P75 (Top Quartile)',    val: output.benchmark_p75 },
    { key: 'P95', label: 'P95 (Top 5%)',          val: output.benchmark_p95 },
  ]
  // The ask slots into the distribution where it actually sits.
  if (ask != null) {
    const idx = rows.findIndex(r => (r.val ?? 0) > ask)
    rows.splice(idx === -1 ? rows.length : idx, 0, {
      key: 'ask',
      label: "Preparer's Ask",
      val: ask,
      isAsk: true,
    })
  }

  return (
    <>
      <View style={s.tableHead}>
        <Text style={s.tableCellHd}>Percentile</Text>
        <Text style={[s.tableCellHd, s.tableRight]}>Pre-Money Valuation</Text>
      </View>
      {rows.map(r => {
        const inBand = !r.isAsk && band.includes(r.key)
        const rowStyle = r.isAsk
          ? [s.tableRow, { backgroundColor: C.accentLt, borderLeftWidth: 3, borderLeftColor: C.accent }]
          : inBand
            ? [s.tableRow, { backgroundColor: C.bg }]
            : [s.tableRow]
        const cellStyle = (r.isAsk || inBand)
          ? [s.tableCell, { fontFamily: 'Helvetica-Bold' as const }]
          : [s.tableCell]
        return (
          <View key={r.key} style={rowStyle}>
            <Text style={r.isAsk ? [...cellStyle, { color: C.accent }] : cellStyle}>
              {r.label}
              {r.isAsk && askPlacement != null && (
                <Text style={{ color: C.slate, fontFamily: 'Helvetica' }}>
                  {'  '}({askPlacement.label} of cohort)
                </Text>
              )}
              {inBand && band[0] === r.key && (
                <Text style={{ color: C.accent, fontSize: 7.5 }}>
                  {'   '}PREPARER'S POSITION
                </Text>
              )}
            </Text>
            <Text style={r.isAsk ? [...cellStyle, s.tableRight, { color: C.accent }] : [...cellStyle, s.tableRight]}>
              {fmtM(r.val)}
            </Text>
          </View>
        )
      })}
      {(band.length > 0) && (
        <Text style={{ fontSize: 6.5, color: C.mid, marginTop: 4 }}>
          {contended != null
            ? `Shaded band: the preparer's contended placement — ${CONTENDED_PLACEMENT_LABELS[contended]}.`
            : "Shaded band: where the preparer's ask sits in the cohort distribution."}
          {' '}The band is the preparer's assertion, not a model output.
        </Text>
      )}
    </>
  )
}

// ---------------------------------------------------------------------------
// Football field chart (SVG primitives + absolutely positioned text overlays).
//
// Note on the installed @react-pdf/renderer 4.5.1 API: SVG <Text> only types
// SVGPresentationAttributes (no fontSize control), so all chart labels are
// regular Text nodes absolutely positioned over the Svg — same visual result,
// full typographic control, and it typechecks.
// ---------------------------------------------------------------------------

const CHART_W = 499            // A4 width 595 − 2×48 padding
const ROW_H = 30               // per-method row: label line + bar
const TOP_PAD = 14             // room for gridline percentile labels
const AXIS_H = 16              // benchmark $ values under the plot

interface FieldRow {
  label: string
  low: number
  high: number
  indicated: number
}

function FootballField({ output, input }: { output: StartupValuationOutput; input: StartupInput }) {
  const rows: FieldRow[] = output.method_results
    .filter(m => m.applicable && m.indicated_value != null)
    .map(m => ({
      label: m.method_label,
      // Fall back to ±20% of the indicated value when a method has no range.
      low: m.value_low ?? (m.indicated_value as number) * 0.8,
      high: m.value_high ?? (m.indicated_value as number) * 1.2,
      indicated: m.indicated_value as number,
    }))

  const benchmarks = [
    { pct: 'P25', val: output.benchmark_p25 },
    { pct: 'P50', val: output.benchmark_p50 },
    { pct: 'P75', val: output.benchmark_p75 },
    { pct: 'P95', val: output.benchmark_p95 },
  ].filter(b => b.val > 0)

  const ask = input.fundraise.pre_money_valuation_ask

  const plotted: number[] = [
    ...rows.flatMap(r => [r.low, r.high, r.indicated]),
    ...benchmarks.map(b => b.val),
    output.blended_valuation,
    ...(ask != null ? [ask] : []),
  ].filter(v => v > 0)

  if (rows.length === 0 || plotted.length < 2) return null

  const minV = Math.min(...plotted)
  const maxV = Math.max(...plotted)
  const lo = Math.max(0, 0.8 * minV)
  const hi = 1.15 * maxV
  if (hi <= lo) return null

  const xFor = (v: number) => 1 + ((v - lo) / (hi - lo)) * (CHART_W - 2)

  const plotH = TOP_PAD + rows.length * ROW_H + 6
  const totalH = plotH + AXIS_H
  const midX = xFor(output.blended_valuation)

  return (
    <View style={{ marginTop: 16 }}>
      <View style={{ position: 'relative', height: totalH }}>
        <Svg width={CHART_W} height={plotH}>
          {/* Benchmark gridlines — the market context the range is read against */}
          {benchmarks.map(b => (
            <Line
              key={b.pct}
              x1={xFor(b.val)} x2={xFor(b.val)}
              y1={TOP_PAD - 3} y2={plotH}
              stroke={C.rule} strokeWidth={0.9}
            />
          ))}

          {/* Method range bars with indicated-value ticks */}
          {rows.map((r, i) => {
            const barY = TOP_PAD + i * ROW_H + 13
            const x0 = xFor(r.low)
            const x1 = xFor(r.high)
            const tickX = xFor(r.indicated)
            return (
              <Fragment key={r.label}>
                <Rect
                  x={x0} y={barY}
                  width={Math.max(1, x1 - x0)} height={9}
                  fill={C.rule} stroke={C.light} strokeWidth={0.5}
                />
                <Line
                  x1={tickX} x2={tickX}
                  y1={barY - 2} y2={barY + 11}
                  stroke={C.ink} strokeWidth={1.4}
                />
              </Fragment>
            )
          })}

          {/* Model midpoint — thin dashed reference line (the blend is derivable
              from the method bars; the deal-relevant marker is the ask) */}
          <Line
            x1={midX} x2={midX} y1={TOP_PAD - 3} y2={plotH}
            stroke={C.mid} strokeWidth={0.9} strokeDasharray="3 2"
          />

          {/* Preparer's ask — the price on the table; solid accent, most prominent */}
          {ask != null && (
            <Line
              x1={xFor(ask)} x2={xFor(ask)}
              y1={TOP_PAD - 3} y2={plotH}
              stroke={C.accent} strokeWidth={1.6}
            />
          )}
        </Svg>

        {/* Gridline percentile labels (top) */}
        {benchmarks.map(b => (
          <Text key={`hd-${b.pct}`} style={[s.chartBench, { top: 0, left: xFor(b.val) - 10, width: 20 }]}>
            {b.pct}
          </Text>
        ))}

        {/* Method labels (left) and indicated values (right) per row */}
        {rows.map((r, i) => (
          <Text key={`lb-${r.label}`} style={[s.chartLabel, { top: TOP_PAD + i * ROW_H + 2, left: 0 }]}>
            {r.label}
          </Text>
        ))}
        {rows.map((r, i) => (
          <Text key={`vl-${r.label}`} style={[s.chartValue, { top: TOP_PAD + i * ROW_H + 2, right: 0, width: 70 }]}>
            {fmtM(r.indicated)}
          </Text>
        ))}

        {/* Benchmark values (axis, below plot) */}
        {benchmarks.map(b => (
          <Text key={`ax-${b.pct}`} style={[s.chartBench, { top: plotH + 3, left: xFor(b.val) - 24, width: 48 }]}>
            {fmtM(b.val)}
          </Text>
        ))}
      </View>

      {/* Legend */}
      <View style={s.legendRow}>
        {ask != null && (
          <View style={s.legendItem}>
            <View style={{ width: 12, height: 1.6, backgroundColor: C.accent }} />
            <Text style={s.legendText}>Preparer's ask {fmtM(ask)}</Text>
          </View>
        )}
        <View style={s.legendItem}>
          <View style={{ width: 12, height: 6, backgroundColor: C.rule, borderWidth: 0.5, borderColor: C.light }} />
          <Text style={s.legendText}>Method range (tick = indicated value)</Text>
        </View>
        <View style={s.legendItem}>
          <View style={{ width: 12, borderBottomWidth: 1, borderBottomColor: C.mid, borderStyle: 'dashed' }} />
          <Text style={s.legendText}>Model midpoint {fmtM(output.blended_valuation)}</Text>
        </View>
      </View>
      <Text style={{ fontSize: 6.5, color: C.light, marginTop: 3 }}>
        Vertical gridlines: P25 / P50 / P75 / P95 — {VERTICAL_LABELS[output.vertical]} {STAGE_LABELS[output.stage]} cohort.
        Values in USD millions, pre-money.
      </Text>
    </View>
  )
}

// ---------------------------------------------------------------------------
// Page 1: Cover + Calibrated Valuation Range (football field)
// ---------------------------------------------------------------------------

function CoverPage({ output, input, reportContext }: {
  output: StartupValuationOutput
  input: StartupInput
  reportContext: ReportContext
}) {
  const date = new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })
  const stage = STAGE_LABELS[output.stage]
  const vertical = VERTICAL_LABELS[output.vertical]
  const geo = GEOGRAPHY_LABELS[input.fundraise.geography]
  const instrument = INSTRUMENT_LABELS[input.fundraise.instrument]
  const perspectiveLabel = PERSPECTIVE_LABELS[reportContext.perspective]
  const preparedBy = reportContext.prepared_by?.trim() || perspectiveLabel

  const ask = input.fundraise.pre_money_valuation_ask
  const contended = reportContext.contended_placement ?? null
  const askPlacement = ask != null
    ? computeModelPlacement(ask, output.benchmark_p25, output.benchmark_p50, output.benchmark_p75, output.benchmark_p95)
    : null
  const atAsk = output.dilution_basis === 'preparer_ask'

  return (
    <Page size="A4" style={s.page}>
      {/* Accent bar */}
      <View style={s.coverAccent} />

      {/* Company name */}
      <Text style={s.coverTitle}>{output.company_name}</Text>
      <Text style={s.coverSub}>Pre-Money Valuation Analysis — {stage} Round</Text>
      <Text style={s.coverSub}>{vertical} · {geo}</Text>
      <Text style={s.coverMeta}>Prepared {date} · Dealflow Engine</Text>
      <Text style={[s.coverMeta, { marginTop: 3 }]}>Prepared by: {preparedBy} ({perspectiveLabel})</Text>
      <Text style={[s.coverDiscl, { marginTop: 6 }]}>
        Computed results are independent of preparer role. Preparer representations, if any, appear in a
        dedicated section and are not inputs to the model.
      </Text>

      {/* Headline: the two numbers an investor actually needs — the calibrated
          range and what the preparer is asking for. The model midpoint is a
          derivable detail and lives on the methods page, not here. */}
      {ask != null ? (
        <View style={[s.hlGrid, { marginTop: 22 }]}>
          <View style={s.hlCellRange}>
            <Text style={[s.hlLabel, { color: C.slate }]}>CALIBRATED VALUATION RANGE</Text>
            <Text style={s.hlValueSm}>
              {fmtM(output.valuation_range_low)} – {fmtM(output.valuation_range_high)}
            </Text>
            <Text style={[s.hlSub, { marginTop: 6 }]}>
              pre-money · {vertical} {stage} cohort
            </Text>
          </View>
          <View style={s.hlCellAsk}>
            <Text style={s.hlLabel}>PREPARER'S ASK</Text>
            <Text style={s.hlValueSm}>
              {fmtM(ask)}
              <Text style={s.hlUnit}>  pre-money</Text>
            </Text>
            <Text style={[s.hlSub, { marginTop: 6 }]}>
              Cohort placement: {askPlacement?.label}
              {contended != null ? ` · positioned as ${CONTENDED_PLACEMENT_LABELS[contended]}` : ''}
            </Text>
          </View>
        </View>
      ) : (
        <View style={[s.hlBox, { marginTop: 22 }]}>
          <Text style={s.hlLabel}>CALIBRATED VALUATION RANGE</Text>
          <Text style={s.hlValue}>
            {fmtM(output.valuation_range_low)} – {fmtM(output.valuation_range_high)}
            <Text style={s.hlUnit}>  pre-money</Text>
          </Text>
          {contended != null ? (
            <Text style={[s.hlSub, { marginTop: 6 }]}>
              Preparer positions the company: {CONTENDED_PLACEMENT_LABELS[contended]} (no dollar ask stated)
            </Text>
          ) : (
            <Text style={[s.hlSub, { marginTop: 6 }]}>Model midpoint: {fmtM(output.blended_valuation)}</Text>
          )}
        </View>
      )}

      {/* Football field — the range in market context */}
      <FootballField output={output} input={input} />

      {/* Transaction summary */}
      <SectionHead title="Transaction Details" />
      {ask != null && (
        <KVRow label="Preparer's Ask (pre-money)" value={fmtM(ask)} />
      )}
      <KVRow label="Fundraising Stage"       value={stage} />
      <KVRow label="Instrument"              value={instrument} />
      <KVRow label="Raise Amount"            value={fmtM(input.fundraise.raise_amount)} />
      <KVRow
        label={`Implied Dilution (at ${atAsk ? "preparer's ask" : 'model midpoint'})`}
        value={fmtPct(output.implied_dilution)}
      />
      {output.recommended_safe_cap != null && (
        <KVRow label="Suggested SAFE Cap" value={fmtM(output.recommended_safe_cap)} />
      )}

      <PageFooter company={output.company_name} />
    </Page>
  )
}

// ---------------------------------------------------------------------------
// Page 2: Market Benchmarks + Valuation Methods
// ---------------------------------------------------------------------------

function MethodsPage({ output, input, reportContext }: {
  output: StartupValuationOutput
  input: StartupInput
  reportContext: ReportContext
}) {
  const applicable = output.method_results.filter(m => m.applicable && m.indicated_value != null)

  return (
    <Page size="A4" style={s.page}>
      {/* Market benchmarks — the distribution the range is calibrated against,
          with the preparer's ask slotted in where it sits */}
      <SectionHead title={`Market Benchmarks — ${VERTICAL_LABELS[output.vertical]} ${STAGE_LABELS[output.stage]} cohort`} />
      <BenchmarkTable
        output={output}
        ask={input.fundraise.pre_money_valuation_ask}
        contended={reportContext.contended_placement ?? null}
      />

      <SectionHead title="Valuation Methods" />
      <Text style={{ fontSize: 8.5, color: C.slate, marginBottom: 12, lineHeight: 1.45 }}>
        The calibrated range on page 1 is derived from the applicable methods below; their weighted blend
        is the model midpoint of {fmtM(output.blended_valuation)} ({output.percentile_in_market}).
        Model verdict: {output.verdict_headline}. Each method is independently computed from the inputs provided.
      </Text>

      {applicable.map(m => (
        <View key={m.method_name} style={s.methodCard}>
          <Text style={s.methodLabel}>{m.method_label}</Text>
          <Text style={s.methodValue}>{fmtM(m.indicated_value)}</Text>
          <Text style={s.methodReason}>{m.rationale}</Text>
          {m.value_low != null && m.value_high != null && (
            <Text style={s.methodRange}>
              Range: {fmtM(m.value_low)} – {fmtM(m.value_high)}
            </Text>
          )}
        </View>
      ))}

      {/* AI modifier note — factual, no opinion */}
      {output.ai_modifier_applied && output.ai_premium_multiplier != null && (
        <View style={[s.methodCard, { marginTop: 12, borderColor: C.accentLt, backgroundColor: C.accentLt }]}>
          <Text style={s.methodLabel}>AI-Native Premium Adjustment</Text>
          <Text style={s.methodValue}>
            {fmtMultiple(output.ai_premium_multiplier)} applied
            {output.blended_before_ai != null
              ? `  ·  Base: ${fmtM(output.blended_before_ai)}  ·  Adjusted: ${fmtM(output.blended_valuation)}`
              : ''}
          </Text>
          {output.ai_premium_context != null && (
            <Text style={s.methodReason}>{output.ai_premium_context}</Text>
          )}
        </View>
      )}

      <PageFooter company={output.company_name} />
    </Page>
  )
}

// ---------------------------------------------------------------------------
// Page 3: Dilution Model + Key Inputs
// ---------------------------------------------------------------------------

function InputsPage({ output, input }: { output: StartupValuationOutput; input: StartupInput }) {
  const t = input.traction

  return (
    <Page size="A4" style={s.page}>

      {/* Dilution table */}
      <SectionHead title="Founder Dilution Model" />
      <Text style={{ fontSize: 8.5, color: C.slate, marginBottom: 10, lineHeight: 1.4 }}>
        Projected founder ownership across current and modeled future rounds.
        {output.dilution_basis === 'preparer_ask'
          ? ` The current round is priced at the preparer's ask of ${fmtM(output.dilution_basis_pre_money)} pre-money — the deal actually on the table — not the model midpoint.`
          : ` The current round is priced at the model midpoint of ${fmtM(output.dilution_basis_pre_money)} pre-money (no preparer ask was stated).`}
        {' '}Future rounds are market projections from cohort benchmarks.
        Standard 10% option pool refresh assumed at each priced round.
      </Text>
      <View style={s.tableHead}>
        <Text style={[s.tableCellHd, { flex: 1.4 }]}>Round</Text>
        <Text style={[s.tableCellHd, s.tableRight]}>Pre-Money</Text>
        <Text style={[s.tableCellHd, s.tableRight]}>Raise</Text>
        <Text style={[s.tableCellHd, s.tableRight]}>Investor %</Text>
        <Text style={[s.tableCellHd, s.tableRight]}>Founder After</Text>
      </View>
      {output.dilution_scenarios.map((d, i) => (
        <View key={i} style={s.tableRow}>
          <Text style={[s.tableCell, { flex: 1.4 }]}>{d.round_label}</Text>
          <Text style={[s.tableCell, s.tableRight]}>{fmtM(d.pre_money)}</Text>
          <Text style={[s.tableCell, s.tableRight]}>{fmtM(d.raise_amount)}</Text>
          <Text style={[s.tableCell, s.tableRight]}>{fmtPct(d.investor_ownership_pct)}</Text>
          <Text style={[s.tableCell, s.tableRight]}>{fmtPct(d.founder_ownership_pct_after)}</Text>
        </View>
      ))}

      {/* SAFE mechanics */}
      {output.safe_conversion != null && (
        <>
          <SectionHead title="SAFE Conversion Mechanics" />
          <KVRow label="SAFE Amount"                  value={fmtM(output.safe_conversion.safe_amount)} />
          <KVRow label="Valuation Cap"                value={fmtM(output.safe_conversion.valuation_cap)} />
          {output.safe_conversion.discount_rate > 0 && (
            <KVRow label="Discount Rate"              value={fmtPct(output.safe_conversion.discount_rate)} />
          )}
          <KVRow label="Implied Ownership at Cap"     value={fmtPct(output.safe_conversion.implied_ownership_pct)} />
        </>
      )}

      {/* Traction inputs */}
      <SectionHead title="Traction Metrics Provided" />
      {t.has_revenue && t.annual_recurring_revenue > 0 && (
        <KVRow label="Annual Recurring Revenue (ARR)" value={fmtM(t.annual_recurring_revenue)} />
      )}
      {t.monthly_recurring_revenue > 0 && (
        <KVRow label="Monthly Recurring Revenue (MRR)" value={fmtM(t.monthly_recurring_revenue)} />
      )}
      {t.mom_growth_rate > 0 && (
        <KVRow label="MoM Revenue Growth Rate"         value={fmtPct(t.mom_growth_rate)} />
      )}
      {t.net_revenue_retention !== 1.0 && (
        <KVRow label="Net Revenue Retention (NRR)"     value={fmtPct(t.net_revenue_retention)} />
      )}
      <KVRow label="Gross Margin"                      value={fmtPct(t.gross_margin)} />
      {t.paying_customer_count > 0 && (
        <KVRow label="Paying Customers"                value={`${t.paying_customer_count}`} />
      )}
      {t.monthly_burn_rate > 0 && (
        <KVRow label="Monthly Burn Rate"               value={fmtM(t.monthly_burn_rate)} />
      )}
      {t.cash_on_hand > 0 && (
        <KVRow label="Cash on Hand"                    value={fmtM(t.cash_on_hand)} />
      )}

      <PageFooter company={output.company_name} />
    </Page>
  )
}

// ---------------------------------------------------------------------------
// Page 4: Team, Product, Market Inputs + Provenance + Disclaimer
// ---------------------------------------------------------------------------

function InputsPage2({ output, input }: { output: StartupValuationOutput; input: StartupInput }) {
  const team = input.team
  const prod = input.product

  return (
    <Page size="A4" style={s.page}>

      {/* Team inputs */}
      <SectionHead title="Team Profile Provided" />
      <KVRow label="Founder Count"              value={`${team.founder_count}`} />
      <KVRow label="Prior Exits"                value={`${team.prior_exits}`} />
      <KVRow label="Technical Co-founder"       value={team.technical_cofounder ? 'Yes' : 'No'} />
      <KVRow label="Domain Experts"             value={team.domain_experts ? 'Yes' : 'No'} />
      <KVRow label="Repeat Founder"             value={team.repeat_founder ? 'Yes' : 'No'} />
      <KVRow label="Tier-1 Background"          value={team.tier1_background ? 'Yes' : 'No'} />
      <KVRow label="Notable Advisors"           value={team.notable_advisors ? 'Yes' : 'No'} />

      {/* Product inputs */}
      <SectionHead title="Product Profile Provided" />
      <KVRow label="Product Stage"              value={PRODUCT_STAGE_LABELS[prod.stage]} />
      <KVRow label="Patent / IP"                value={prod.has_patent_or_ip ? 'Yes' : 'No'} />
      <KVRow label="Proprietary Data Moat"      value={prod.proprietary_data_moat ? 'Yes' : 'No'} />
      <KVRow label="Open Source Traction"       value={prod.open_source_traction ? 'Yes' : 'No'} />
      <KVRow label="Regulatory Clearance"       value={prod.regulatory_clearance ? 'Yes' : 'No'} />

      {/* Market inputs */}
      <SectionHead title="Market Profile Provided" />
      <KVRow label="Total Addressable Market (TAM)" value={`$${new Intl.NumberFormat('en-US').format(Math.round(input.market.tam_usd_billions))}B`} />
      <KVRow label="Serviceable Addressable Market (SAM)" value={fmtM(input.market.sam_usd_millions)} />
      <KVRow label="Annual Market Growth Rate"  value={fmtPct(input.market.market_growth_rate)} />
      <KVRow label="Competitive Moat"           value={input.market.competitive_moat.charAt(0).toUpperCase() + input.market.competitive_moat.slice(1)} />

      {/* Provenance */}
      <View style={{ marginTop: 20 }}>
        <Text style={[s.sectionHead, { marginBottom: 6 }]}>Provenance</Text>
        <View style={s.rule} />
        <Text style={{ fontSize: 7.5, color: C.mid, lineHeight: 1.5 }}>
          Benchmark data: Carta State of Private Markets Q4 2025 / Q1 2026, Carta State of Pre-Seed Q1 2026,
          PitchBook-NVCA Venture Monitor FY2025, Aventis Advisors SaaS Multiples 2026, SaaS Capital Index
          Q1 2026 (2026-Q2 vintage). Valuation methods: weighted blend of the methods on page 2; weights and
          applicability as shown. Engine: Dealflow Engine startup valuation module.
          Vertical: {VERTICAL_LABELS[output.vertical]} · Stage: {STAGE_LABELS[output.stage]}.
        </Text>
      </View>

      {/* Legal disclaimer */}
      <View style={{ marginTop: 16, paddingTop: 12, borderTopWidth: 1, borderTopColor: C.rule }}>
        <Text style={[s.sectionHead, { marginBottom: 6 }]}>Important Disclaimer</Text>
        <Text style={{ fontSize: 7.5, color: C.mid, lineHeight: 1.55 }}>
          This report is generated by Dealflow Engine and is provided for informational purposes only.
          It does not constitute financial, legal, or investment advice. The valuation figures presented
          are model outputs based on inputs provided by the user and publicly available market benchmarks.
          Actual valuations in arm's-length transactions may differ materially. Recipients should conduct
          their own independent due diligence and consult qualified financial and legal advisors before
          making any investment decisions. Past market benchmarks are not indicative of future performance.
        </Text>
      </View>

      <PageFooter company={output.company_name} />
    </Page>
  )
}

// ---------------------------------------------------------------------------
// Conditional page: Preparer's Representations + placement reconciliation.
// Advocacy is quarantined here — the model provably does not incorporate it.
// ---------------------------------------------------------------------------

const REPRESENTATIONS_TITLE: Record<ReportContext['perspective'], string> = {
  founder: "Preparer's Representations",
  investor: 'Diligence Notes',
  advisor: "Advisor's Notes",
}

function RepresentationsPage({ output, input, reportContext }: {
  output: StartupValuationOutput
  input: StartupInput
  reportContext: ReportContext
}) {
  const notes = printableNotes(reportContext)
  const contended = reportContext.contended_placement ?? null
  const title = REPRESENTATIONS_TITLE[reportContext.perspective]
  const ask = input.fundraise.pre_money_valuation_ask
  const askPlacement = ask != null
    ? computeModelPlacement(ask, output.benchmark_p25, output.benchmark_p50, output.benchmark_p75, output.benchmark_p95)
    : null

  const placement = computeModelPlacement(
    output.blended_valuation,
    output.benchmark_p25,
    output.benchmark_p50,
    output.benchmark_p75,
    output.benchmark_p95,
  )
  const cohort = `${VERTICAL_LABELS[output.vertical]} ${STAGE_LABELS[output.stage]}`

  // Note numbers (1-based, in printed order) whose anchor is benchmark_placement
  const placementNoteNumbers = notes
    .map((n, i) => ({ n, num: i + 1 }))
    .filter(({ n }) => n.anchor === 'benchmark_placement')
    .map(({ num }) => num)
  const basis = placementNoteNumbers.length > 0
    ? `Representation${placementNoteNumbers.length > 1 ? 's' : ''} ${placementNoteNumbers.join(', ')}`
    : 'see representations above'

  return (
    <Page size="A4" style={s.page}>
      <SectionHead title={title} />

      {/* Standing disclaimer — same copy regardless of perspective */}
      <View style={s.disclBox}>
        <Text style={{ fontSize: 8, color: C.slate, lineHeight: 1.55 }}>
          The computed valuation range in this report does not incorporate the representations below.
          They are statements of the preparer, presented for the reader's independent assessment.
          Where evidence references are provided, readers are encouraged to verify them directly.
        </Text>
      </View>

      {notes.map((n, i) => (
        <View key={n.id} style={s.represBox}>
          <Text style={s.represHead}>Representation {i + 1} — {NOTE_ANCHOR_LABELS[n.anchor]}</Text>
          <Text style={s.represClaim}>{n.claim}</Text>
          {n.evidence?.trim()
            ? <Text style={s.represEvid}>Evidence: {n.evidence.trim()}</Text>
            : <Text style={s.represEvidNone}>No evidence reference provided</Text>}
        </View>
      ))}

      {/* Placement reconciliation — factual, never in the preparer's favor */}
      {contended != null && (
        <View style={[s.disclBox, { marginTop: 12, borderLeftWidth: 3, borderLeftColor: C.accent }]}>
          <Text style={{ fontSize: 8, fontFamily: 'Helvetica-Bold', color: C.ink, marginBottom: 4 }}>
            Placement Reconciliation
          </Text>
          <Text style={{ fontSize: 8.5, color: C.slate, lineHeight: 1.55 }}>
            Model placement: {placement.label} of {cohort} cohort.
            {ask != null && askPlacement != null
              ? ` Preparer's ask: ${fmtM(ask)} (${askPlacement.label} of cohort).`
              : ''}
            {' '}Preparer contends: {CONTENDED_PLACEMENT_LABELS[contended]}.
            {' '}Basis: {basis}.
            {contentionConsistentWithModel(contended, placement)
              ? " Preparer's contention is consistent with the model."
              : ''}
          </Text>
        </View>
      )}

      <PageFooter company={output.company_name} />
    </Page>
  )
}

// ---------------------------------------------------------------------------
// Root PDF document
// ---------------------------------------------------------------------------

function ValuationDocument({ output, input, reportContext }: {
  output: StartupValuationOutput
  input: StartupInput
  reportContext: ReportContext
}) {
  const showRepresentations =
    printableNotes(reportContext).length > 0 || reportContext.contended_placement != null

  return (
    <Document
      title={`${output.company_name} — Valuation Report`}
      author="Dealflow Engine"
      subject="Pre-Money Valuation Analysis"
    >
      <CoverPage    output={output} input={input} reportContext={reportContext} />
      <MethodsPage  output={output} input={input} reportContext={reportContext} />
      <InputsPage   output={output} input={input} />
      <InputsPage2  output={output} input={input} />
      {showRepresentations && (
        <RepresentationsPage output={output} input={input} reportContext={reportContext} />
      )}
    </Document>
  )
}

// ---------------------------------------------------------------------------
// Exported download button — renders inline in the dashboard
// ---------------------------------------------------------------------------

interface PDFExportButtonProps {
  output: StartupValuationOutput
  input: StartupInput
  reportContext: ReportContext
}

export default function PDFExportButton({ output, input, reportContext }: PDFExportButtonProps) {
  const filename = `${output.company_name.replace(/\s+/g, '_')}_Valuation_Report.pdf`

  return (
    <PDFDownloadLink
      document={<ValuationDocument output={output} input={input} reportContext={reportContext} />}
      fileName={filename}
    >
      {({ loading }: { loading: boolean }) => (
        <button
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 rounded-lg border border-purple-600/50 bg-purple-900/20 text-purple-300 hover:bg-purple-900/40 hover:border-purple-500 text-sm font-medium transition-all disabled:opacity-50 disabled:cursor-wait"
          title="Export investor-facing PDF report"
        >
          <FileDown size={14} />
          {loading ? 'Building PDF…' : 'Export PDF'}
        </button>
      )}
    </PDFDownloadLink>
  )
}

// Exported for the smoke-render script (not used by the app UI)
export { ValuationDocument }
