"""Checks for propagation semantics and the two checked-in FRAM inputs."""

from fractions import Fraction
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fram_safety.analysis import (  # noqa: E402
    analyze,
    describe,
    exact_distribution,
    load_model,
    load_weights,
    target_coefficients,
)


class AnalysisTests(unittest.TestCase):
    def test_diamond_propagation_counts_shared_upstream_once(self):
        functions = {0: "source", 1: "left", 2: "right", 3: "target"}
        weights = {
            (0, 1, "I"): Fraction(1),
            (0, 2, "I"): Fraction(1),
            (1, 3, "I"): Fraction(1),
            (2, 3, "I"): Fraction(1),
        }
        coefficients = target_coefficients(functions, weights, target=3)
        self.assertEqual(coefficients[0], 2)
        distribution, nodes = exact_distribution(coefficients, set(), target=3)
        self.assertEqual(nodes, [0, 1, 2])
        self.assertEqual(sum(distribution.values()), 27)
        self.assertEqual(describe(distribution)["mean"], 4.0)

    def test_checked_in_models_have_matching_weights(self):
        for name, expected in (("original", (25, 33)), ("mitigated", (30, 38))):
            with self.subTest(model=name):
                functions, edges = load_model(ROOT / "models" / f"{name}.xfmv")
                weights = load_weights(ROOT / "configs" / f"{name}_weights.csv", edges)
                self.assertEqual((len(functions), len(edges)), expected)
                self.assertEqual(len(weights), expected[1])

    def test_original_case_mean_matches_published_table(self):
        summary, _ = analyze(
            ROOT / "models/original.xfmv", ROOT / "configs/original_weights.csv", set()
        )
        self.assertEqual(summary["mean"], 33.0)
        self.assertEqual(summary["max"], 66.0)

    def test_cycle_is_rejected_instead_of_using_an_arbitrary_order(self):
        with self.assertRaisesRegex(ValueError, "cycle"):
            target_coefficients(
                {0: "a", 1: "b", 2: "target"},
                {(0, 1, "I"): Fraction(1), (1, 0, "I"): Fraction(1),
                 (1, 2, "I"): Fraction(1)},
                target=2,
            )


if __name__ == "__main__":
    unittest.main()
