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
    dataset_results_dir,
    front_nodes,
    graph_arrays,
    largest_component_nodes,
    set_jaccard,
    validate_graph_counts,
    weighted_jaccard,
)
from visualize import _align_camera_with_xy, _highway_edge_colours


def toy_graph() -> tuple[ig.Graph, dict, np.ndarray]:
    """Build a small vascular graph for metric and selection tests."""
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
        """Set Jaccard must ignore usage magnitude."""
        left = np.array([50, 10, 0, 5])
        right = np.array([1, 0, 20, 5])

        self.assertAlmostEqual(set_jaccard(left, right), 0.5)

    def test_weighted_jaccard_uses_edge_counts(self):
        """Weighted Jaccard must retain usage magnitude."""
        left = np.array([50, 10, 0, 5])
        right = np.array([1, 0, 20, 5])

        self.assertAlmostEqual(weighted_jaccard(left, right), 6 / 85)

    def test_identical_empty_usage_is_identical(self):
        """Two empty usage vectors must have full similarity."""
        left = np.zeros(4, dtype=int)
        right = np.zeros(4, dtype=int)

        self.assertEqual(set_jaccard(left, right), 1.0)
        self.assertEqual(weighted_jaccard(left, right), 1.0)


class GraphSelectionTests(unittest.TestCase):
    def test_target_is_largest_vein_in_lcc(self):
        """Target selection must choose the largest vein in the LCC."""
        _graph, arrays, lcc_nodes = toy_graph()

        self.assertEqual(choose_target(arrays, lcc_nodes), 4)

    def test_artery_sources_are_seeded_and_type_filtered(self):
        """Artery sampling must respect the seed and vessel type."""
        _graph, arrays, lcc_nodes = toy_graph()

        sources = choose_sources(
            arrays, lcc_nodes, "random_arteries_in_lcc",
            num_sources=1, seed=0, pool_size=10,
        )

        self.assertEqual(sources, [1])

    def test_capillary_sources_are_seeded_and_type_filtered(self):
        """Capillary sampling must respect the seed and vessel type."""
        _graph, arrays, lcc_nodes = toy_graph()

        sources = choose_sources(
            arrays, lcc_nodes, "diverse_capillaries_in_lcc",
            num_sources=2, seed=0, pool_size=10,
        )

        self.assertEqual(len(sources), 2)
        self.assertTrue(all(arrays["node_types"][source] == 3 for source in sources))


class FrontSelectionTests(unittest.TestCase):
    def test_front_uses_nearest_one_percent_of_reachable_nodes(self):
        """Front selection must return the nearest reachable percentile."""
        distances = np.arange(200, dtype=float)
        distances[[0, 1]] = np.inf

        selected = front_nodes(distances)

        self.assertEqual(selected.tolist(), [2])


class HighwayUsageTests(unittest.TestCase):
    def test_highway_usage_counts_paths_to_target(self):
        """Highway usage must count each traversed path edge."""
        graph, _arrays, _lcc_nodes = toy_graph()

        usage = compute_highways(graph, sources=[0, 1], target=4, weights=None)

        self.assertEqual(usage.tolist(), [1, 2, 0, 0, 0])


class ResultPathTests(unittest.TestCase):
    def test_dataset_result_folder_uses_graph_stem(self):
        """Result directories must use the input graph stem."""
        result = dataset_results_dir(Path("experiments"), Path("data/HC1.5_clearmap.gml"))

        self.assertEqual(result, Path("experiments/HC1.5_clearmap"))

    def test_graph_count_mismatch_is_rejected(self):
        """Graph validation must reject mismatched result metadata."""
        graph, _arrays, _lcc_nodes = toy_graph()

        with self.assertRaisesRegex(ValueError, "Graph does not match"):
            validate_graph_counts(graph, {"nodes": 10, "edges": 20})

    def test_matching_graph_counts_are_accepted(self):
        """Graph validation must accept matching result metadata."""
        graph, _arrays, _lcc_nodes = toy_graph()

        validate_graph_counts(graph, {"nodes": 5, "edges": 5})


class CameraAlignmentTests(unittest.TestCase):
    def test_camera_uses_graph_xy_plane(self):
        """Camera alignment must preserve the graph x-y orientation."""
        class Camera:
            def set_view_direction(self, **kwargs):
                """Record the requested camera directions."""
                self.kwargs = kwargs

        class Viewer:
            camera = Camera()

        viewer = Viewer()
        _align_camera_with_xy(viewer)

        self.assertEqual(viewer.camera.kwargs["view_direction"], (0, 0, -1))
        self.assertEqual(viewer.camera.kwargs["up_direction"], (0, 1, 0))

    def test_highway_colours_stay_in_napari_range(self):
        """Highway colours must stay within Napari's RGBA range."""
        colours = _highway_edge_colours("resistance", np.array([1, 2, 100]))

        self.assertGreaterEqual(float(colours.min()), 0.0)
        self.assertLessEqual(float(colours.max()), 1.0)


if __name__ == "__main__":
    unittest.main()
