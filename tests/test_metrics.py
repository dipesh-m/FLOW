import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from flow_experiment import set_jaccard, weighted_jaccard


class JaccardMetricTests(unittest.TestCase):
    def test_set_jaccard_uses_edge_presence(self):
        left = np.array([50, 10, 0, 5])
        right = np.array([1, 0, 20, 5])

        self.assertAlmostEqual(set_jaccard(left, right), 0.5)

    def test_weighted_jaccard_uses_edge_counts(self):
        left = np.array([50, 10, 0, 5])
        right = np.array([1, 0, 20, 5])

        self.assertAlmostEqual(weighted_jaccard(left, right), 6 / 85)

    def test_identical_empty_usage_is_identical(self):
        left = np.zeros(4, dtype=int)
        right = np.zeros(4, dtype=int)

        self.assertEqual(set_jaccard(left, right), 1.0)
        self.assertEqual(weighted_jaccard(left, right), 1.0)


if __name__ == "__main__":
    unittest.main()
