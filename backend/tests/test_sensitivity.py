"""
Tests for the sensitivity matrix generator.
Verifies matrix dimensions, monotonicity, and format.
"""
import pytest
from app.engine.sensitivity import build_sensitivity_matrix, generate_all_sensitivity_matrices
from app.engine.models import DealInput, DealVerdict
from app.engine.financial_engine import run_deal
import json
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_deal(filename: str) -> DealInput:
    with open(FIXTURES_DIR / filename) as f:
        data = json.load(f)
    return DealInput(**data["input"])


class TestBuildSensitivityMatrix:
    """Unit tests for the matrix builder."""

    def test_dimensions_match(self):
        rows = [1.0, 2.0, 3.0]
        cols = [10.0, 20.0, 30.0, 40.0]
        matrix = build_sensitivity_matrix(
            title="Test",
            row_label="Row",
            col_label="Col",
            row_values=rows,
            col_values=cols,
            compute_fn=lambda r, c: r * c / 100,
        )
        assert len(matrix.data) == len(rows)
        for row in matrix.data:
            assert len(row) == len(cols)
        assert len(matrix.data_labels) == len(rows)
        for row_labels in matrix.data_labels:
            assert len(row_labels) == len(cols)

    def test_values_are_computed(self):
        """Verify compute_fn is actually called for each cell."""
        called = []
        def fn(r, c):
            called.append((r, c))
            return 0.05

        build_sensitivity_matrix("T", "R", "C", [1, 2], [10, 20, 30], fn)
        assert len(called) == 6  # 2 rows × 3 cols

    def test_formatting(self):
        matrix = build_sensitivity_matrix(
            title="T", row_label="R", col_label="C",
            row_values=[0.0], col_values=[5.0, -3.0],
            compute_fn=lambda r, c: c / 100,
        )
        labels = matrix.data_labels[0]
        assert "+" in labels[0] or "%" in labels[0], "Positive should show + sign"
        assert "-" in labels[1], "Negative should show - sign"

    def test_monotone_function_produces_monotone_matrix(self):
        """If compute_fn is monotone in each dimension, matrix should be monotone."""
        rows = [0.0, 5.0, 10.0, 15.0, 20.0]
        cols = [0.0, 2.5, 5.0, 7.5, 10.0]
        matrix = build_sensitivity_matrix(
            title="T", row_label="Price", col_label="Synergies",
            row_values=rows, col_values=cols,
            compute_fn=lambda price, syn: (syn - price) / 20,  # Higher synergy = better
        )
        # Each row: as column increases, value should increase
        for row_idx in range(len(rows)):
            row_vals = matrix.data[row_idx]
            for col_idx in range(1, len(cols)):
                assert row_vals[col_idx] >= row_vals[col_idx - 1] - 0.001


class TestGenerateAllMatrices:
    """Integration tests for full matrix generation."""

    def test_simple_deal_generates_three_matrices(self):
        deal = load_deal("simple_cash_deal.json")
        def stub_fn(d: DealInput) -> float:
            # Quick stub to avoid full re-run for each cell
            return 0.05
        matrices = generate_all_sensitivity_matrices(deal, stub_fn)
        assert len(matrices) == 3

    def test_matrix_titles_are_unique(self):
        deal = load_deal("simple_cash_deal.json")
        matrices = generate_all_sensitivity_matrices(deal, lambda d: 0.0)
        titles = [m.title for m in matrices]
        assert len(set(titles)) == len(titles), "All matrix titles should be unique"

    def test_matrix_row_col_labels_set(self):
        deal = load_deal("simple_cash_deal.json")
        matrices = generate_all_sensitivity_matrices(deal, lambda d: 0.02)
        for m in matrices:
            assert m.row_label
            assert m.col_label

    def test_full_run_generates_real_matrices(self):
        """Full deal run produces non-trivial sensitivity values."""
        deal = load_deal("mixed_financing_synergies.json")
        output = run_deal(deal)
        assert len(output.sensitivity_matrices) == 3
        # At least some non-zero values
        all_values = [
            v
            for matrix in output.sensitivity_matrices
            for row in matrix.data
            for v in row
        ]
        assert any(abs(v) > 0.001 for v in all_values), "Sensitivity matrices should have non-zero values"

    def test_purchase_price_vs_synergy_direction(self):
        """
        Higher purchase price → worse accretion.
        Higher synergies → better accretion.
        The top-left cell (low price, high synergy) should dominate bottom-right.
        """
        deal = load_deal("mixed_financing_synergies.json")
        output = run_deal(deal)
        pp_syn_matrix = next(
            m for m in output.sensitivity_matrices if "Purchase Price" in m.title and "Syner" in m.title
        )
        # Compare top-left (lowest price, highest synergy % = col[-1]) vs bottom-right
        # Matrix: rows = price premiums (negative = lower price), cols = synergy achievement
        top_left = pp_syn_matrix.data[0][-1]    # Lowest price, highest synergy
        bottom_right = pp_syn_matrix.data[-1][0]  # Highest price, zero synergy
        assert top_left > bottom_right, (
            f"Low price + high synergy ({top_left:.3f}) should beat "
            f"high price + no synergy ({bottom_right:.3f})"
        )
