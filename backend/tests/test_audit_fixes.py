"""
Regression tests for the valuation-metrics audit fixes (F-1 .. F-22).

Each test class maps to an audit finding and pins the corrected behavior so a
regression reintroducing the defect fails loudly. Hand workpapers are included
in comments where exact values are asserted.

All monetary values are in MILLIONS USD per project convention.
"""
import json
import math
import pytest
from pathlib import Path

from app.engine.models import (
    AmortizationType,
    DealInput,
    DealVerdict,
    DebtTranche,
    SynergyItem,
)
from app.engine.financial_engine import run_deal
from app.engine.purchase_price import compute_ppa
from app.engine.returns import compute_returns, _irr
from app.engine.sensitivity import build_sensitivity_matrix, generate_all_sensitivity_matrices
from app.engine import defaults as dflt

FIXTURES_DIR = Path(__file__).parent / "fixtures"

ALL_FIXTURES = [
    "simple_cash_deal.json",
    "mixed_financing_synergies.json",
    "leveraged_deal.json",
    "all_stock_deal.json",
    "extreme_leverage_deal.json",
    "loss_making_acquirer.json",
    "ai_native_defense_deal.json",
    "defense_ai_acquisition.json",
]


def load_deal(filename: str) -> DealInput:
    with open(FIXTURES_DIR / filename) as f:
        data = json.load(f)
    return DealInput(**data["input"])


# ---------------------------------------------------------------------------
# F-1 / F-5 / F-19: returns valued on the target-side stream, FCF subtracts all
# debt paydown, no artificial equity floor
# ---------------------------------------------------------------------------
class TestReturnsTargetSideStream:

    def test_hand_computed_irr_moic_small_deal(self):
        """
        WORKPAPER (single-scenario check on compute_returns):
          EV = 100, cash 50% / stock 0% / debt 50%; fees = 2.
          Equity invested (F-19) = 100 x 0.50 + 2 = 52 (no floor).
          Target EBITDA = 10 -> entry multiple = 10.0x.
          deal EBITDA = [12]*5; ending acq debt = [50,45,40,35,30];
          deal FCF (post ALL paydown, F-5) = [5]*5.
          Exit year 3 at 10.0x: exit EV = 120.
            Cumulative deal cash = 5+5+5 = 15; net debt = 40 - 15 = 25.
            Exit equity = 120 - 25 = 95.
            MOIC = 95 / 52 = 1.826923x.
            IRR = (95/52)^(1/3) - 1 = 22.25% (1.826923^(1/3) = 1.222497).
        """
        deal = load_deal("simple_cash_deal.json")
        deal = deal.model_copy(deep=True)
        deal.target.acquisition_price = 100.0
        deal.target.ebitda = 10.0
        deal.structure.cash_percentage = 0.50
        deal.structure.stock_percentage = 0.0
        deal.structure.debt_percentage = 0.50

        result = compute_returns(
            deal,
            deal_ebitda_by_year=[12.0] * 5,
            ending_debt_by_year=[50.0, 45.0, 40.0, 35.0, 30.0],
            deal_fcf_by_year=[5.0] * 5,
            transaction_costs=2.0,
        )
        assert abs(result.entry_multiple - 10.0) < 1e-9
        assert abs(result.equity_invested - 52.0) < 1e-9

        s = next(x for x in result.scenarios if x.exit_year == 3 and abs(x.exit_multiple - 10.0) < 1e-9)
        assert abs(s.exit_enterprise_value - 120.0) < 1e-9
        assert abs(s.moic - 95.0 / 52.0) < 1e-9
        assert abs(s.irr - ((95.0 / 52.0) ** (1.0 / 3.0) - 1.0)) < 1e-6

    def test_leveraged_fixture_returns_are_sane(self):
        """
        F-1 regression: the audit reproduced IRR 103% / MOIC 34.6x on the
        leveraged fixture because the exit valued the whole combined company
        against a target-only equity check. On the target+synergy stream the
        base-case 5-year returns must be aggressive-but-sane.
        """
        deal = load_deal("leveraged_deal.json")
        out = run_deal(deal, include_sensitivity=False)
        ra = out.returns_analysis
        base5 = next(
            s for s in ra.scenarios
            if s.exit_year == 5 and abs(s.exit_multiple - ra.entry_multiple) < 0.6
        )
        assert base5.moic < 10.0, f"MOIC {base5.moic:.1f}x still combined-company inflated"
        assert base5.irr < 0.60, f"IRR {base5.irr:.0%} still combined-company inflated"
        assert base5.moic > 1.0 and base5.irr > 0.0, "Deal with $25M synergies should still return"

    def test_exit_ev_is_target_side_not_combined(self):
        """Exit EV at the entry multiple must be scaled to target+synergy EBITDA,
        far below combined EBITDA x multiple."""
        deal = load_deal("leveraged_deal.json")
        out = run_deal(deal, include_sensitivity=False)
        ra = out.returns_analysis
        base5 = next(
            s for s in ra.scenarios
            if s.exit_year == 5 and abs(s.exit_multiple - ra.entry_multiple) < 0.6
        )
        combined_ebitda_y5 = out.pro_forma_income_statement[4].ebitda
        assert base5.exit_enterprise_value < combined_ebitda_y5 * ra.entry_multiple * 0.5, (
            "Exit EV appears to be valuing the combined company"
        )

    def test_no_equity_floor_full_debt_deal(self):
        """F-19: ~100% debt deal -> equity check ~= fees only; IRR/MOIC flagged NM."""
        deal = load_deal("simple_cash_deal.json").model_copy(deep=True)
        deal.structure.cash_percentage = 0.0
        deal.structure.stock_percentage = 0.0
        deal.structure.debt_percentage = 1.0
        result = compute_returns(
            deal,
            deal_ebitda_by_year=[6.0] * 5,
            ending_debt_by_year=[50.0] * 5,
            deal_fcf_by_year=[1.0] * 5,
            transaction_costs=0.0,
        )
        # Old code floored equity at 10% of price (5.0); now it is exactly 0
        assert result.equity_invested == 0.0
        assert result.notes, "Near-zero equity must be flagged with a note"
        assert all(s.moic == 0.0 and s.irr == 0.0 for s in result.scenarios)


# ---------------------------------------------------------------------------
# F-20: IRR solver robustness
# ---------------------------------------------------------------------------
class TestIRRSolver:

    def test_simple_doubling(self):
        # -100 now, +200 in 1 year -> IRR = 100%
        assert abs(_irr([-100.0, 200.0]) - 1.0) < 1e-6

    def test_three_year_hand_computed(self):
        # -100 now, +172.8 in year 3 -> IRR = 1.728^(1/3) - 1 = 20%
        assert abs(_irr([-100.0, 0.0, 0.0, 172.8]) - 0.20) < 1e-6

    def test_no_sign_change_returns_minus_one(self):
        assert _irr([100.0, 100.0]) == -1.0
        assert _irr([-100.0, -100.0]) == -1.0

    def test_total_loss_never_below_minus_100pct(self):
        # -100 now, +1 in year 5 -> IRR close to -60%; must never be <= -1
        irr = _irr([-100.0, 0.0, 0.0, 0.0, 0.0, 1.0])
        assert -1.0 < irr < 0.0

    def test_extreme_gain_does_not_raise(self):
        # Newton would explode; bisection fallback must handle it (F-20)
        irr = _irr([-0.001, 1000.0])
        assert irr > 1.0 and not math.isnan(irr)

    def test_alternating_signs_does_not_raise(self):
        irr = _irr([-100.0, 300.0, -250.0, 100.0])
        assert isinstance(irr, float) and not math.isnan(irr)


# ---------------------------------------------------------------------------
# F-2 / F-3: pro forma NI anchored to actual net income + foregone cash interest
# ---------------------------------------------------------------------------
class TestProFormaAnchoring:

    def test_simple_cash_deal_roughly_flat(self):
        """
        The audit's headline defect: simple_cash_deal reported +41.2% phantom
        Year-1 accretion because the margin rebuild deleted both companies'
        existing below-EBIT items. Anchored to actual NI (F-2) with foregone
        cash interest (F-3) and fees, Year 1 is roughly flat.

        WORKPAPER: acq EBT0 = 15/0.75 = 20 (x1.03), tgt EBT0 = 3/0.75 = 4 (x1.04);
        - PPA D&A 0.825 - foregone 50 x 4.3% = 2.15 - fees 1.25
        => EBT = 20.535, NI = 15.40125, EPS 1.540125 vs standalone 1.545 => -0.32%.
        """
        out = run_deal(load_deal("simple_cash_deal.json"), include_sensitivity=False)
        y1 = out.pro_forma_income_statement[0]
        assert -1.0 < y1.accretion_dilution_pct < 1.0, (
            f"Expected ~flat Year 1, got {y1.accretion_dilution_pct:+.2f}%"
        )
        assert abs(y1.net_income - 15.40125) < 1e-6

    def test_existing_interest_survives_in_pro_forma(self):
        """Existing below-EBIT items (interest) must appear in the IS."""
        out = run_deal(load_deal("simple_cash_deal.json"), include_sensitivity=False)
        y1 = out.pro_forma_income_statement[0]
        # acq existing items = 30 - 5 - 20 = 5; tgt = 6 - 0.8 - 4 = 1.2 (grown 1yr)
        expected = 5.0 * 1.03 + 1.2 * 1.04
        assert abs(y1.existing_interest - expected) < 1e-9

    def test_foregone_interest_deducted(self):
        """F-3: cash consideration x cash_yield deducted every year, pre-tax."""
        out = run_deal(load_deal("simple_cash_deal.json"), include_sensitivity=False)
        for yr in out.pro_forma_income_statement:
            assert abs(yr.foregone_cash_interest - 50.0 * 0.043) < 1e-9
        # Bridge carries an explicit after-tax foregone-interest drag
        b1 = out.accretion_dilution_bridge[0]
        assert b1.foregone_interest_drag < 0

    def test_cash_yield_is_overridable(self):
        deal = load_deal("simple_cash_deal.json").model_copy(deep=True)
        deal.structure.cash_yield = 0.0
        out = run_deal(deal, include_sensitivity=False)
        y1 = out.pro_forma_income_statement[0]
        assert y1.foregone_cash_interest == 0.0
        # Removing the 2.15 pre-tax drag raises NI by 2.15 x 0.75
        assert abs(y1.net_income - (15.40125 + 2.15 * 0.75)) < 1e-6

    def test_cash_shortfall_warns_not_raises(self):
        """F-3/F-9: validate acquirer cash covers cash uses; warn, never raise."""
        deal = load_deal("simple_cash_deal.json").model_copy(deep=True)
        deal.acquirer.cash_on_hand = 10.0  # needs 50 + 1.25 fees
        out = run_deal(deal, include_sensitivity=False)
        assert any("exceeds cash on hand" in n for n in out.computation_notes)


# ---------------------------------------------------------------------------
# F-4: loss-making acquirer — NM convention and verdict off the EPS delta
# ---------------------------------------------------------------------------
class TestLossMakingAcquirer:

    def setup_method(self):
        with open(FIXTURES_DIR / "loss_making_acquirer.json") as f:
            self.fixture = json.load(f)
        self.deal = DealInput(**self.fixture["input"])
        self.output = run_deal(self.deal, include_sensitivity=False)
        self.expected = self.fixture["expected"]

    def test_accretion_marked_nm(self):
        y1 = self.output.pro_forma_income_statement[0]
        assert y1.accretion_is_nm is True

    def test_eps_improvement_reports_positive_accretion(self):
        """EPS improves from -1.03 to -0.995 — the % must be POSITIVE (F-4).
        The old code divided by the signed -1.03 and flipped the sign."""
        y1 = self.output.pro_forma_income_statement[0]
        assert abs(y1.pro_forma_eps - self.expected["year1_pro_forma_eps_approx"]) < 1e-4
        assert abs(y1.acquirer_standalone_eps - self.expected["year1_standalone_eps_approx"]) < 1e-9
        assert y1.pro_forma_eps > y1.acquirer_standalone_eps
        assert y1.accretion_dilution_pct > 0, "Improving EPS must not report dilution"
        assert abs(y1.accretion_dilution_pct - self.expected["year1_accretion_pct_approx"]) < 0.01

    def test_verdict_driven_by_eps_delta_not_red(self):
        assert self.output.deal_verdict != DealVerdict.RED
        # +3.37% > 2% threshold -> green
        assert self.output.deal_verdict == DealVerdict.GREEN

    def test_scorecard_shows_nm(self):
        metric = next(m for m in self.output.deal_scorecard if m.name == "Year 1 Accretion / Dilution")
        assert metric.formatted_value == "NM"

    def test_abs_denominator_identity(self):
        """accretion% == delta / |standalone| x 100 for every year."""
        for yr in self.output.pro_forma_income_statement:
            expected = (yr.pro_forma_eps - yr.acquirer_standalone_eps) / abs(yr.acquirer_standalone_eps) * 100
            assert abs(yr.accretion_dilution_pct - expected) < 1e-6


# ---------------------------------------------------------------------------
# F-6: sensitivity base cell == headline accretion; no synthetic base synergy
# ---------------------------------------------------------------------------
class TestSensitivityBaseCell:

    def _base_cell_matches(self, filename: str):
        deal = load_deal(filename)
        out = run_deal(deal, include_sensitivity=True)
        headline = out.pro_forma_income_statement[0].accretion_dilution_pct / 100
        m = next(x for x in out.sensitivity_matrices if x.title == "Purchase Price vs Synergies")
        assert m.base_row_idx >= 0 and m.base_col_idx >= 0
        base_cell = m.data[m.base_row_idx][m.base_col_idx]
        assert base_cell is not None
        assert abs(base_cell - headline) < 5e-4, (
            f"{filename}: base cell {base_cell:.4f} != headline {headline:.4f}"
        )
        return m

    def test_base_cell_matches_headline_with_synergies(self):
        self._base_cell_matches("mixed_financing_synergies.json")

    def test_base_cell_matches_headline_zero_synergy_deal(self):
        """The audit found a 2%-of-revenue synergy silently injected into EVERY
        column (incl. base) for zero-synergy deals: base cell 170.6% vs headline
        41.2%. The $0 column must now be the true base case."""
        m = self._base_cell_matches("simple_cash_deal.json")
        # Zero-synergy deals use the absolute-dollar axis, clearly labeled
        assert m.base_col_idx == 0
        assert m.col_values[0] == 0.0
        assert "(Base)" in m.col_display_labels[0]
        assert m.note is not None and "no modeled synergies" in m.note.lower()

    def test_cash_mix_base_cell_matches_headline(self):
        # Use an on-grid cash mix (60%) so a base column exists; the fixture's
        # 50% cash is between grid points and correctly suppresses the highlight.
        deal = load_deal("mixed_financing_synergies.json").model_copy(deep=True)
        deal.structure.cash_percentage = 0.60
        deal.structure.stock_percentage = 0.20
        deal.structure.debt_percentage = 0.20
        out = run_deal(deal, include_sensitivity=True)
        headline = out.pro_forma_income_statement[0].accretion_dilution_pct / 100
        m = next(x for x in out.sensitivity_matrices if "Cash/Stock" in x.title)
        assert m.base_row_idx >= 0 and m.base_col_idx >= 0
        assert "(Base)" in m.col_display_labels[m.base_col_idx]
        base_cell = m.data[m.base_row_idx][m.base_col_idx]
        assert base_cell is not None
        assert abs(base_cell - headline) < 5e-4

    def test_off_grid_cash_mix_suppresses_base_highlight(self):
        """The fixture's 50% cash is not a grid point — no column may be
        highlighted as (Base)."""
        deal = load_deal("mixed_financing_synergies.json")
        out = run_deal(deal, include_sensitivity=True)
        m = next(x for x in out.sensitivity_matrices if "Cash/Stock" in x.title)
        assert m.base_col_idx == -1
        assert all("(Base)" not in lbl for lbl in m.col_display_labels)


# ---------------------------------------------------------------------------
# F-7: leverage axis alive, sized off target EBITDA, tranches rescaled
# ---------------------------------------------------------------------------
class TestLeverageAxis:

    def test_leverage_columns_vary_when_acquirer_is_larger(self):
        """The audit found every column pegged at the 95% debt cap whenever the
        acquirer out-sized the target (axis dead). Columns must now differ."""
        deal = load_deal("leveraged_deal.json")  # acquirer EBITDA 200 vs target 45
        out = run_deal(deal, include_sensitivity=True)
        m = next(x for x in out.sensitivity_matrices if x.title == "Interest Rate vs Leverage")
        row = [v for v in m.data[0] if v is not None]
        assert len(set(round(v, 4) for v in row)) >= 3, (
            f"Leverage axis is dead — row values {row}"
        )

    def test_axis_is_labeled_target_ebitda(self):
        deal = load_deal("leveraged_deal.json")
        out = run_deal(deal, include_sensitivity=True)
        m = next(x for x in out.sensitivity_matrices if x.title == "Interest Rate vs Leverage")
        assert "Target EBITDA" in m.col_label

    def test_base_highlight_suppressed_when_off_grid(self):
        """Actual leverage = 400 / 45 = 8.9x target EBITDA — outside the 2-7x
        grid, so no column may be highlighted as (Base)."""
        deal = load_deal("leveraged_deal.json")
        out = run_deal(deal, include_sensitivity=True)
        m = next(x for x in out.sensitivity_matrices if x.title == "Interest Rate vs Leverage")
        assert m.base_col_idx == -1
        assert all("(Base)" not in lbl for lbl in m.col_display_labels)
        assert m.note is not None and "outside" in m.note

    def test_explicit_tranches_rescaled(self):
        """3.0x target EBITDA (45) = 135 total debt; explicit tranches (400 total)
        must be rescaled proportionally, preserving the 250/100/50 mix."""
        deal = load_deal("leveraged_deal.json")
        captured = {}

        def capture_fn(d: DealInput):
            total = sum(t.amount for t in d.structure.debt_tranches)
            captured[round(total, 4)] = [t.amount for t in d.structure.debt_tranches]
            return 0.0

        generate_all_sensitivity_matrices(deal, capture_fn)
        # 3.0x x 45 = 135 (below the 0.95 x 500 = 475 cap)
        assert 135.0 in captured, f"Expected a 135 total-debt scenario, got {sorted(captured)}"
        amounts = captured[135.0]
        scale = 135.0 / 400.0
        assert abs(amounts[0] - 250.0 * scale) < 1e-6
        assert abs(amounts[1] - 100.0 * scale) < 1e-6
        assert abs(amounts[2] - 50.0 * scale) < 1e-6


# ---------------------------------------------------------------------------
# F-21: failed sensitivity cells -> None / "n/a" / note, never silent 0.0
# ---------------------------------------------------------------------------
class TestSensitivityCellFailures:

    def test_failed_cell_is_none_with_note(self):
        def fn(r, c):
            if r == 2.0 and c == 20.0:
                raise ValueError("boom")
            return 0.05

        m = build_sensitivity_matrix("T", "R", "C", [1.0, 2.0], [10.0, 20.0], fn)
        assert m.data[1][1] is None
        assert m.data_labels[1][1] == "n/a"
        assert m.data[0][0] == 0.05
        assert m.note is not None and "1 cell(s) failed" in m.note

    def test_none_return_treated_as_failure(self):
        m = build_sensitivity_matrix("T", "R", "C", [1.0], [1.0], lambda r, c: None)
        assert m.data[0][0] is None
        assert m.data_labels[0][0] == "n/a"


# ---------------------------------------------------------------------------
# F-8: defaults thresholds in millions + H1 2026 rates
# ---------------------------------------------------------------------------
class TestDefaultsTiering:

    def test_fee_tiers_in_millions(self):
        """The audit found thresholds in raw dollars, so every deal (in millions)
        fell below 50_000_000 and got the 3% small-deal fee."""
        assert dflt.get_transaction_fee_pct(30.0) == 0.030    # < $50M
        assert dflt.get_transaction_fee_pct(200.0) == 0.020   # $50M-$500M
        assert dflt.get_transaction_fee_pct(600.0) == 0.015   # > $500M
        assert dflt.get_transaction_fee_pct(49.999) == 0.030
        assert dflt.get_transaction_fee_pct(50.0) == 0.020

    def test_interest_rate_tiers_in_millions(self):
        assert dflt.get_interest_rate(100.0) == dflt.BLENDED_MIDDLE_MARKET_RATE
        assert dflt.get_interest_rate(249.999) == dflt.BLENDED_MIDDLE_MARKET_RATE
        assert dflt.get_interest_rate(250.0) == dflt.BLENDED_LARGE_CAP_RATE
        assert dflt.get_interest_rate(2000.0) == dflt.BLENDED_LARGE_CAP_RATE

    def test_h1_2026_rate_levels(self):
        assert dflt.BLENDED_MIDDLE_MARKET_RATE == 0.10
        assert dflt.MIDDLE_MARKET_RATE_RANGE == (0.09, 0.11)
        assert dflt.BLENDED_LARGE_CAP_RATE == 0.08
        assert dflt.LARGE_CAP_RATE_RANGE == (0.075, 0.09)

    def test_raw_dollar_guard_warns(self):
        deal = load_deal("simple_cash_deal.json").model_copy(deep=True)
        deal.acquirer.revenue = 200_000_000.0  # raw dollars by mistake
        out = run_deal(deal, include_sensitivity=False)
        assert any("raw dollars" in n for n in out.computation_notes)


# ---------------------------------------------------------------------------
# F-9: Sources & Uses always balances
# ---------------------------------------------------------------------------
class TestSourcesAndUsesBalance:

    @pytest.mark.parametrize("filename", ALL_FIXTURES)
    def test_balanced_for_all_fixtures(self, filename):
        out = run_deal(load_deal(filename), include_sensitivity=False)
        snu = out.sources_and_uses
        assert snu is not None
        assert snu.balanced is True, (
            f"{filename}: sources {snu.total_sources:.2f} != uses {snu.total_uses:.2f}"
        )
        assert abs(snu.total_sources - snu.total_uses) < 0.01

    def test_simple_cash_deal_hand_computed(self):
        """
        WORKPAPER: EV 50, target debt 0, target cash 2, fees 1.25.
          Uses: equity purchase (50 - 0 + 2) = 52, fees 1.25 -> 53.25.
          Sources: acquirer cash 50, target cash 2, gap 1.25 from acquirer -> 53.25.
        """
        out = run_deal(load_deal("simple_cash_deal.json"), include_sensitivity=False)
        snu = out.sources_and_uses
        assert abs(snu.total_uses - 53.25) < 1e-6
        assert abs(snu.total_sources - 53.25) < 1e-6
        labels = [u.label for u in snu.uses]
        assert "Purchase of Target Equity" in labels
        assert "Transaction Fees & Expenses" in labels

    def test_refinance_line_present_when_target_has_debt(self):
        out = run_deal(load_deal("leveraged_deal.json"), include_sensitivity=False)
        labels = [u.label for u in out.sources_and_uses.uses]
        assert "Refinance Target Debt" in labels


# ---------------------------------------------------------------------------
# F-10: acquisition_price is ENTERPRISE VALUE everywhere
# ---------------------------------------------------------------------------
class TestEnterpriseValueConvention:

    def test_goodwill_uses_equity_consideration(self):
        """
        WORKPAPER (mixed fixture): EV 200, tgt debt 5, tgt cash 3.
          Equity consideration = 200 - 5 + 3 = 198.
          FVNA = book equity (3 + 8 - 5 = 6) + writeup 5 + intangibles 20
                 - DTL (25 x 25% = 6.25) = 24.75.
          Goodwill = 198 - 24.75 = 173.25 (old EV-based code produced 175.25,
          overstated by target net debt of 2).
        """
        deal = load_deal("mixed_financing_synergies.json")
        result = compute_ppa(deal)
        assert abs(result.equity_consideration - 198.0) < 1e-9
        assert abs(result.goodwill - 173.25) < 1e-9

    def test_goodwill_shrinks_with_target_debt(self):
        """More target debt (same EV) -> less equity bought -> less goodwill."""
        base = load_deal("simple_cash_deal.json")
        with_debt = base.model_copy(deep=True)
        with_debt.target.total_debt = 10.0
        g_base = compute_ppa(base).goodwill
        g_debt = compute_ppa(with_debt).goodwill
        # Equity consideration falls by 10; book equity also falls by 10 inside
        # FVNA, so goodwill is unchanged by the book-value channel but the
        # consideration channel dominates: goodwill must not INCREASE.
        assert g_debt <= g_base + 1e-9

    def test_implied_valuation_ev_vs_equity(self):
        out = run_deal(load_deal("leveraged_deal.json"), include_sensitivity=False)
        iv = out.implied_valuation
        # EV = acquisition_price = 500; equity = 500 - 30 + 10 = 480
        assert abs(iv.enterprise_value - 500.0) < 1e-9
        assert abs(iv.equity_value - 480.0) < 1e-9
        # EV/EBITDA on EV; P/E on equity value
        assert abs(iv.ev_ebitda_ltm - 500.0 / 45.0) < 1e-9
        assert abs(iv.price_to_earnings - 480.0 / 22.0) < 1e-9


# ---------------------------------------------------------------------------
# F-12 / F-13: cost-to-achieve expensed; revenue synergies at target margin
# ---------------------------------------------------------------------------
class TestSynergyEconomics:

    def _base_deal(self) -> DealInput:
        return load_deal("simple_cash_deal.json").model_copy(deep=True)

    def test_cost_to_achieve_hits_pl(self):
        """F-12: identical synergy, one with $6M CTA over 3 years -> Year 1
        EBITDA lower by exactly 2.0 (6/3)."""
        clean = self._base_deal()
        clean.synergies.cost_synergies = [SynergyItem(
            category="Ops", annual_amount=3.0, phase_in_years=3, cost_to_achieve=0.0)]
        costly = self._base_deal()
        costly.synergies.cost_synergies = [SynergyItem(
            category="Ops", annual_amount=3.0, phase_in_years=3, cost_to_achieve=6.0)]
        out_clean = run_deal(clean, include_sensitivity=False)
        out_costly = run_deal(costly, include_sensitivity=False)
        y1c, y1x = out_clean.pro_forma_income_statement[0], out_costly.pro_forma_income_statement[0]
        assert abs((y1c.ebitda - y1x.ebitda) - 2.0) < 1e-9
        assert abs(y1x.integration_costs - 2.0) < 1e-9
        # After the phase-in window the CTA drag disappears
        y4c, y4x = out_clean.pro_forma_income_statement[3], out_costly.pro_forma_income_statement[3]
        assert abs(y4c.ebitda - y4x.ebitda) < 1e-9

    def test_revenue_synergies_flow_at_target_margin(self):
        """F-13: $10M revenue synergy adds 10 x target EBITDA margin (15%) = 1.5
        to EBITDA — not $10M at 100% margin."""
        base = self._base_deal()
        with_rev = self._base_deal()
        with_rev.synergies.revenue_synergies = [SynergyItem(
            category="Cross-sell", annual_amount=10.0, phase_in_years=1,
            cost_to_achieve=0.0, is_revenue=True)]
        y1_base = run_deal(base, include_sensitivity=False).pro_forma_income_statement[0]
        y1_rev = run_deal(with_rev, include_sensitivity=False).pro_forma_income_statement[0]
        assert abs((y1_rev.revenue - y1_base.revenue) - 10.0) < 1e-9
        ebitda_lift = y1_rev.ebitda - y1_base.ebitda
        assert abs(ebitda_lift - 10.0 * 0.15) < 1e-9, (
            f"Revenue synergy flowed at {ebitda_lift/10.0:.0%} margin, expected 15%"
        )


# ---------------------------------------------------------------------------
# F-14: breakeven synergy is the closed-form Year-1 EPS-neutral level
# ---------------------------------------------------------------------------
class TestBreakevenSynergy:

    def test_injecting_breakeven_synergy_neutralizes_year1(self):
        """Solve-and-verify: read the scorecard breakeven, inject exactly that
        synergy (1-year phase-in, no CTA) and Year-1 accretion must be ~0."""
        deal = load_deal("simple_cash_deal.json")  # dilutive -0.32% baseline
        out = run_deal(deal, include_sensitivity=False)
        breakeven = next(
            m for m in out.deal_scorecard if m.name == "Breakeven Annual Savings"
        ).value
        assert breakeven > 0, "Dilutive deal must need positive synergies to break even"

        modified = deal.model_copy(deep=True)
        modified.synergies.cost_synergies = [SynergyItem(
            category="Breakeven test", annual_amount=breakeven,
            phase_in_years=1, cost_to_achieve=0.0)]
        y1 = run_deal(modified, include_sensitivity=False).pro_forma_income_statement[0]
        assert abs(y1.accretion_dilution_pct) < 0.02, (
            f"Injecting the breakeven synergy left {y1.accretion_dilution_pct:+.3f}%"
        )

    def test_accretive_deal_breakeven_is_zero(self):
        """A comfortably accretive deal needs no synergies to break even."""
        deal = load_deal("simple_cash_deal.json").model_copy(deep=True)
        deal.target.acquisition_price = 25.0  # half price -> strongly accretive
        out = run_deal(deal, include_sensitivity=False)
        assert out.pro_forma_income_statement[0].accretion_dilution_pct > 0
        breakeven = next(
            m for m in out.deal_scorecard if m.name == "Breakeven Annual Savings"
        ).value
        assert breakeven == 0.0


# ---------------------------------------------------------------------------
# F-15 / F-16: risk analyzer thresholds
# ---------------------------------------------------------------------------
class TestRiskAnalyzerFixes:

    def test_leverage_risk_includes_tranches_and_industry_turns(self):
        """
        extreme_leverage fixture: tranches 135 + 90 + 45 = 270, acquirer debt 30
        -> total 300 vs combined EBITDA 37 = 8.11x. Professional Services debt
        capacity = 3.5x -> critical at 5.25x -> CRITICAL severity.
        """
        out = run_deal(load_deal("extreme_leverage_deal.json"), include_sensitivity=False)
        risk = next(r for r in out.risk_assessment if r.metric_name == "Post-Close Total Debt / EBITDA")
        assert abs(risk.current_value - 300.0 / 37.0) < 0.01
        assert abs(risk.threshold_value - 3.5 * 1.5) < 1e-9
        assert risk.severity.value == "critical"
        # F-15: no negative decline percentage in the tolerance text
        assert "-%" not in risk.tolerance_band and "falls by more than -" not in risk.tolerance_band

    def test_leverage_tolerance_text_when_already_above_critical(self):
        out = run_deal(load_deal("extreme_leverage_deal.json"), include_sensitivity=False)
        risk = next(r for r in out.risk_assessment if r.metric_name == "Post-Close Total Debt / EBITDA")
        assert "must grow" in risk.tolerance_band

    def test_purchase_price_threshold_is_flag_trigger(self):
        """F-16: threshold_value must be the actual trigger (industry high),
        not the 1.5x-median severity escalation level."""
        out = run_deal(load_deal("extreme_leverage_deal.json"), include_sensitivity=False)
        risk = next(r for r in out.risk_assessment if r.metric_name == "Entry EV/EBITDA Multiple")
        # Professional Services high = 12x (entry is 300/12 = 25x)
        assert abs(risk.threshold_value - 12.0) < 1e-9
        assert "12.0×" in risk.tolerance_band


# ---------------------------------------------------------------------------
# F-17: rate-sensitivity risk uses pro forma shares and explicit tranches
# ---------------------------------------------------------------------------
class TestRateSensitivityRisk:

    def _make_deal(self) -> DealInput:
        deal = load_deal("simple_cash_deal.json").model_copy(deep=True)
        # EV 100, 50% stock at $25 -> 2.0M new shares -> 12.0M pro forma shares
        deal.target.acquisition_price = 100.0
        deal.structure.cash_percentage = 0.0
        deal.structure.stock_percentage = 0.50
        deal.structure.debt_percentage = 0.50
        deal.structure.debt_tranches = [DebtTranche(
            name="TL", amount=60.0, interest_rate=0.08, term_years=7,
            amortization_type=AmortizationType.STRAIGHT_LINE,
        )]
        return deal

    def test_breakeven_bp_uses_pro_forma_shares_and_tranches(self):
        """
        WORKPAPER: acquisition debt = explicit tranche 60 (NOT debt% x price);
        pro forma shares = 10 + (100 x 50% / 25) = 12 (F-17: not standalone 10).
        EPS drag per 100bp = 60 x 0.01 x (1 - 0.25) / 12 = 0.0375.
        With Y1 EPS accretion of +$0.02: breakeven = 0.02 / 0.0375 x 100 = 53.3bp
        (< 100bp -> HIGH). The old standalone-share code produced 44.4bp.
        """
        from types import SimpleNamespace
        from app.engine.risk_analyzer import _interest_rate_sensitivity_risk

        deal = self._make_deal()
        fake_output = SimpleNamespace(pro_forma_income_statement=[
            SimpleNamespace(pro_forma_eps=1.52, acquirer_standalone_eps=1.50)
        ])
        risk = _interest_rate_sensitivity_risk(deal, fake_output, 1.33)
        assert risk is not None
        expected_bp = 0.02 / (60.0 * 0.01 * 0.75 / 12.0) * 100
        assert abs(risk.current_value - expected_bp) < 0.01, (
            f"breakeven {risk.current_value:.1f}bp != {expected_bp:.1f}bp — "
            "standalone shares or debt% shorthand may have regressed"
        )
        assert risk.severity.value == "high"  # < 100bp headroom

    def test_tranches_counted_even_when_debt_pct_zero(self):
        """Explicit tranches with debt_percentage=0 must still register debt."""
        from types import SimpleNamespace
        from app.engine.risk_analyzer import _interest_rate_sensitivity_risk

        deal = self._make_deal()
        deal.structure.cash_percentage = 0.50
        deal.structure.debt_percentage = 0.0  # tranches remain
        fake_output = SimpleNamespace(pro_forma_income_statement=[
            SimpleNamespace(pro_forma_eps=1.52, acquirer_standalone_eps=1.50)
        ])
        risk = _interest_rate_sensitivity_risk(deal, fake_output, 1.33)
        assert risk is not None, "Old code used debt% x price = 0 and never flagged"


# ---------------------------------------------------------------------------
# F-22: balance sheet at close balances via disclosed plug
# ---------------------------------------------------------------------------
class TestBalanceSheetPlug:

    @pytest.mark.parametrize("filename", ["simple_cash_deal.json", "leveraged_deal.json"])
    def test_assets_equal_liabilities_plus_equity(self, filename):
        out = run_deal(load_deal(filename), include_sensitivity=False)
        bs = out.balance_sheet_at_close
        assert abs(bs.combined_total_assets - (bs.combined_total_liabilities + bs.combined_equity)) < 1e-6

    def test_plug_disclosed_in_notes(self):
        out = run_deal(load_deal("simple_cash_deal.json"), include_sensitivity=False)
        bs = out.balance_sheet_at_close
        if abs(bs.balancing_plug) > 0.5:
            assert any("balancing plug" in n for n in out.computation_notes)


# ---------------------------------------------------------------------------
# F-11: solver receives synergy-inclusive, grown inputs
# ---------------------------------------------------------------------------
class TestSolverInputConsistency:

    def test_synergies_accelerate_debt_paydown(self):
        """More synergies -> more FCF in the solver -> faster optional paydown
        (previously the solver saw synergy-exclusive EBITDA, so synergies had
        zero effect on the debt schedule)."""
        base = load_deal("mixed_financing_synergies.json").model_copy(deep=True)
        no_syn = base.model_copy(deep=True)
        no_syn.synergies.cost_synergies = []
        no_syn.synergies.revenue_synergies = []
        out_syn = run_deal(base, include_sensitivity=False)
        out_no = run_deal(no_syn, include_sensitivity=False)
        # Year-2+ acquisition interest should be lower with synergies (faster sweep)
        y3_syn = out_syn.pro_forma_income_statement[2].acquisition_interest
        y3_no = out_no.pro_forma_income_statement[2].acquisition_interest
        assert y3_syn <= y3_no + 1e-9
