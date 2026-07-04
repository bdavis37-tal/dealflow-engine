/**
 * StartupValuationPDF — investor-facing PDF export.
 *
 * Renders a clean, factual valuation report suitable for sharing with investors.
 * No internal flags, signals, or editorial commentary — only methods, calculations,
 * metrics, and inputs.
 *
 * Uses @react-pdf/renderer for in-browser PDF generation.
 */
import { Document, Page, Text, View, StyleSheet, PDFDownloadLink } from '@react-pdf/renderer'
import type { StartupValuationOutput, StartupInput } from '../../../types/startup'
import {
  VERTICAL_LABELS, STAGE_LABELS, GEOGRAPHY_LABELS,
  INSTRUMENT_LABELS, PRODUCT_STAGE_LABELS,
} from '../../../types/startup'
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
  // Highlight box
  hlBox:        { backgroundColor: C.accentLt, borderRadius: 4, padding: 12, marginBottom: 12 },
  hlLabel:      { fontSize: 8, color: C.accent, marginBottom: 4 },
  hlValue:      { fontSize: 22, fontFamily: 'Helvetica-Bold', color: C.ink },
  hlSub:        { fontSize: 8, color: C.slate, marginTop: 3 },
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

function PageFooter({ company, page }: { company: string; page: number }) {
  const date = new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })
  return (
    <View style={s.footer} fixed>
      <Text style={s.footerText}>{company} — Valuation Report · {date}</Text>
      <Text style={s.footerText}>Dealflow Engine  ·  Page {page}</Text>
    </View>
  )
}

// ---------------------------------------------------------------------------
// Page 1: Cover + Valuation Summary
// ---------------------------------------------------------------------------

function CoverPage({ output, input }: { output: StartupValuationOutput; input: StartupInput }) {
  const date = new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })
  const stage = STAGE_LABELS[output.stage]
  const vertical = VERTICAL_LABELS[output.vertical]
  const geo = GEOGRAPHY_LABELS[input.fundraise.geography]
  const instrument = INSTRUMENT_LABELS[input.fundraise.instrument]

  return (
    <Page size="A4" style={s.page}>
      {/* Accent bar */}
      <View style={s.coverAccent} />

      {/* Company name */}
      <Text style={s.coverTitle}>{output.company_name}</Text>
      <Text style={s.coverSub}>Pre-Money Valuation Analysis — {stage} Round</Text>
      <Text style={s.coverSub}>{vertical} · {geo}</Text>
      <Text style={s.coverMeta}>Prepared {date} · Dealflow Engine</Text>

      {/* Blended value highlight */}
      <View style={[s.hlBox, { marginTop: 28 }]}>
        <Text style={s.hlLabel}>BLENDED PRE-MONEY VALUATION</Text>
        <Text style={s.hlValue}>{fmtM(output.blended_valuation)}</Text>
        <Text style={s.hlSub}>
          Range: {fmtM(output.valuation_range_low)} – {fmtM(output.valuation_range_high)}
          {'   ·   '}{output.percentile_in_market}
        </Text>
      </View>

      {/* Transaction summary */}
      <SectionHead title="Transaction Details" />
      <KVRow label="Fundraising Stage"       value={stage} />
      <KVRow label="Instrument"              value={instrument} />
      <KVRow label="Raise Amount"            value={fmtM(input.fundraise.raise_amount)} />
      <KVRow label="Implied Dilution"        value={fmtPct(output.implied_dilution)} />
      {output.recommended_safe_cap != null && (
        <KVRow label="Suggested SAFE Cap" value={fmtM(output.recommended_safe_cap)} />
      )}
      {input.fundraise.pre_money_valuation_ask != null && (
        <KVRow label="Founder Ask (pre-money)" value={fmtM(input.fundraise.pre_money_valuation_ask)} />
      )}

      {/* Market benchmarks */}
      <SectionHead title="Market Benchmarks — " />
      <View style={s.tableHead}>
        <Text style={s.tableCellHd}>Percentile</Text>
        <Text style={[s.tableCellHd, s.tableRight]}>Pre-Money Valuation</Text>
      </View>
      {[
        { label: 'P25 (Bottom Quartile)',  val: output.benchmark_p25 },
        { label: 'P50 (Median)',           val: output.benchmark_p50 },
        { label: 'P75 (Top Quartile)',     val: output.benchmark_p75 },
        { label: 'P95 (Top 5%)',           val: output.benchmark_p95 },
      ].map(r => (
        <View key={r.label} style={s.tableRow}>
          <Text style={s.tableCell}>{r.label}</Text>
          <Text style={[s.tableCell, s.tableRight]}>{fmtM(r.val)}</Text>
        </View>
      ))}

      <PageFooter company={output.company_name} page={1} />
    </Page>
  )
}

// ---------------------------------------------------------------------------
// Page 2: Valuation Methods
// ---------------------------------------------------------------------------

function MethodsPage({ output }: { output: StartupValuationOutput }) {
  const applicable = output.method_results.filter(m => m.applicable && m.indicated_value != null)
  const notApplicable = output.method_results.filter(m => !m.applicable)

  return (
    <Page size="A4" style={s.page}>
      <SectionHead title="Valuation Methods" />
      <Text style={{ fontSize: 8.5, color: C.slate, marginBottom: 12, lineHeight: 1.45 }}>
        The blended valuation above is a weighted average of the applicable methods below.
        Each method is independently computed from the inputs provided.
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

      {notApplicable.length > 0 && (
        <>
          <Text style={[s.sectionHead, { marginTop: 16 }]}>Methods Not Applied</Text>
          <View style={s.rule} />
          {notApplicable.map(m => (
            <View key={m.method_name} style={s.row}>
              <Text style={s.rowLabel}>{m.method_label}</Text>
              <Text style={[s.rowValue, { color: C.mid, fontFamily: 'Helvetica' }]}>{m.rationale}</Text>
            </View>
          ))}
        </>
      )}

      {/* AI modifier note — factual, no opinion */}
      {output.ai_modifier_applied && output.ai_premium_multiplier != null && (
        <View style={[s.methodCard, { marginTop: 12, borderColor: C.accentLt, backgroundColor: C.accentLt }]}>
          <Text style={s.methodLabel}>AI-Native Premium Adjustment</Text>
          <Text style={s.methodValue}>
            {fmtMultiple(output.ai_premium_multiplier)} applied
            {output.blended_before_ai != null
              ? `  ·  Base: ${fmtM(output.blended_before_ai)} → Adjusted: ${fmtM(output.blended_valuation)}`
              : ''}
          </Text>
          {output.ai_premium_context != null && (
            <Text style={s.methodReason}>{output.ai_premium_context}</Text>
          )}
        </View>
      )}

      <PageFooter company={output.company_name} page={2} />
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

      <PageFooter company={output.company_name} page={3} />
    </Page>
  )
}

// ---------------------------------------------------------------------------
// Page 4: Team, Product, Market Inputs + Disclaimer
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

      {/* Benchmark source note */}
      <View style={{ marginTop: 20 }}>
        <Text style={[s.sectionHead, { marginBottom: 6 }]}>Data Sources</Text>
        <View style={s.rule} />
        <Text style={{ fontSize: 7.5, color: C.mid, lineHeight: 1.5 }}>
          Market benchmarks sourced from: Carta State of Private Markets Q4 2025 / Q1 2026 ·
          Carta State of Pre-Seed Q1 2026 · PitchBook-NVCA Venture Monitor FY2025 ·
          Aventis Advisors SaaS Multiples 2026 · SaaS Capital Index Q1 2026.
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

      <PageFooter company={output.company_name} page={4} />
    </Page>
  )
}

// ---------------------------------------------------------------------------
// Root PDF document
// ---------------------------------------------------------------------------

function ValuationDocument({ output, input }: { output: StartupValuationOutput; input: StartupInput }) {
  return (
    <Document
      title={`${output.company_name} — Valuation Report`}
      author="Dealflow Engine"
      subject="Pre-Money Valuation Analysis"
    >
      <CoverPage    output={output} input={input} />
      <MethodsPage  output={output} />
      <InputsPage   output={output} input={input} />
      <InputsPage2  output={output} input={input} />
    </Document>
  )
}

// ---------------------------------------------------------------------------
// Exported download button — renders inline in the dashboard
// ---------------------------------------------------------------------------

interface PDFExportButtonProps {
  output: StartupValuationOutput
  input: StartupInput
}

export default function PDFExportButton({ output, input }: PDFExportButtonProps) {
  const filename = `${output.company_name.replace(/\s+/g, '_')}_Valuation_Report.pdf`

  return (
    <PDFDownloadLink
      document={<ValuationDocument output={output} input={input} />}
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
