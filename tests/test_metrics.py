import sys
import unittest
from pathlib import Path

import numpy as np
import igraph as ig

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from flow_experiment import (
    choose_sources,
    choose_target,
    compute_highways,
    graph_arrays,
    largest_component_nodes,
    set_jaccard,
    weighted_jaccard,
)


def toy_graph() -> tuple[ig.Graph, dict, np.ndarray]:
    graph = ig.Graph(
        n=5,
        edges=[(0, 1), (1, 4), (0, 2), (2, 3), (3, 4)],
        directed=False,
    )
    graph.vs["coordinates"] = ["0,0,0", "1,0,0", "0,1,0", "1,1,0", "2,0,0"]
    graph.vs["radii"] = [2.0, 3.0, 1.0, 1.5, 5.0]
    graph.vs["vessel_type"] = [3, 1, 3, 3, 2]
    arrays = graph_arrays(graph)
    lcc_nodes = largest_component_nodes(graph)
    return graph, arrays, lcc_nodes


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


class GraphSelectionTests(unittest.TestCase):
    def test_target_is_largest_vein_in_lcc(self):
        _graph, arrays, lcc_nodes = toy_graph()

        self.assertEqual(choose_target(arrays, lcc_nodes), 4)

    def test_artery_sources_are_seeded_and_type_filtered(self):
        _graph, arrays, lcc_nodes = toy_graph()

        sources = choose_sources(
            arrays, lcc_nodes, "random_arteries_in_lcc",
            num_sources=1, seed=0, pool_size=10,
        )

        self.assertEqual(sources, [1])

    def test_capillary_sources_are_seeded_and_type_filtered(self):
        _graph, arrays, lcc_nodes = toy_graph()

        sources = choose_sources(
            arrays, lcc_nodes, "diverse_capillaries_in_lcc",
            num_sources=2, seed=0, pool_size=10,
        )

        self.assertEqual(len(sources), 2)
        self.assertTrue(all(arrays["node_types"][source] == 3 for source in sources))


class HighwayUsageTests(unittest.TestCase):
    def test_highway_usage_counts_paths_to_target(self):
        graph, _arrays, _lcc_nodes = toy_graph()

        usage = compute_highways(graph, sources=[0, 1], target=4, weights=None)

        self.assertEqual(usage.tolist(), [1, 2, 0, 0, 0])


if __name__ == "__main__":
    unittest.main()
