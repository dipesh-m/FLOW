"""Napari viewer for FLOW experiment outputs."""

from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path

import numpy as np

from flow_experiment import (
    graph_arrays,
    largest_component_nodes,
    load_graph,
    method_weights,
    run_method,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GRAPH_PATH = REPO_ROOT / "data" / "HC1.5_gurobi.gml"
DEFAULT_EXP_DIR = REPO_ROOT / "experiments"

N_FRAMES = 40
MAX_FRONT_POINTS = 6000
BACKGROUND_POINTS = 60_000

METHOD_COLOURS = {
    "bfs": (0.45, 0.45, 0.45, 1.0),
    "length": (0.12, 0.47, 0.71, 1.0),
    "resistance": (0.77, 0.24, 0.22, 1.0),
    "radius": (0.17, 0.63, 0.37, 1.0),
}
METHOD_LABELS = {
    "bfs": "BFS (hop count)",
    "length": "Length (L)",
    "resistance": "Resistance (L/r^4)",
    "radius": "Radius (1/r^4)",
}
SOURCE_COLOUR = (1.0, 1.0, 0.2, 1.0)
TARGET_COLOUR = (0.0, 0.85, 0.95, 1.0)


def _abs_path(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


def _load_summary(run_dir: Path) -> dict:
    for name in ("summary.json", "highways_summary.json"):
        path = run_dir / name
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    raise FileNotFoundError(f"No summary in {run_dir}")


def _read_highway_csv(path: Path) -> tuple[np.ndarray, np.ndarray]:
    edges, usage = [], []
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            edges.append([int(row["src"]), int(row["dst"])])
            usage.append(int(row["usage"]))
    return np.asarray(edges, dtype=np.int64), np.asarray(usage, dtype=np.int64)


def _prefer_hardware_opengl() -> None:
    os.environ.setdefault("QT_OPENGL", "desktop")
    os.environ.setdefault("NAPARI_ASYNC", "1")


def _print_gpu_info() -> None:
    try:
        from vispy import sys_info

        lines = []
        for line in sys_info().splitlines():
            lower = line.lower()
            if "gl version" in lower or "gl vendor" in lower or "gl renderer" in lower:
                lines.append(line.strip())
        if lines:
            print("OpenGL renderer:")
            for line in lines:
                print(f"  {line}")
    except Exception as exc:
        print(f"OpenGL renderer: unavailable ({exc})")


def _background(viewer, coords: np.ndarray, lcc: np.ndarray) -> None:
    rng = np.random.default_rng(0)
    idx = rng.choice(lcc, size=min(len(lcc), BACKGROUND_POINTS), replace=False)
    viewer.add_points(
        coords[idx],
        name="LCC sample",
        size=0.7,
        face_color=(0.7, 0.7, 0.7, 0.18),
        border_width=0,
    )


def _front_growth(coords: np.ndarray, front_nodes: np.ndarray, distance: np.ndarray) -> np.ndarray:
    nodes = front_nodes[np.argsort(distance[front_nodes], kind="stable")]
    if len(nodes) > MAX_FRONT_POINTS:
        nodes = nodes[np.linspace(0, len(nodes) - 1, MAX_FRONT_POINTS).astype(int)]
    appear = np.floor(np.linspace(0, N_FRAMES - 1, len(nodes))).astype(int)

    frames, xyz = [], []
    for node, first in zip(nodes.tolist(), appear.tolist()):
        present = np.arange(first, N_FRAMES)
        frames.append(present)
        xyz.append(np.repeat(coords[node][None, :], len(present), axis=0))
    return np.column_stack([np.concatenate(frames), np.concatenate(xyz)])


def visualize_front(viewer, graph, arrays, summary, methods: list[str]) -> None:
    coords = arrays["coords"]
    sources = [int(s) for s in summary["sources"]]
    target = int(summary["target"])
    _background(viewer, coords, largest_component_nodes(graph))

    for method in methods:
        weights = method_weights(method, arrays)
        weight_list = weights.tolist() if weights is not None else None
        chunks = []
        for src in sources:
            result = run_method(graph, arrays, method, 1, src, target)
            dist = np.asarray(
                graph.distances(source=src, weights=weight_list, mode="all")[0],
                dtype=np.float64,
            )
            chunks.append(_front_growth(coords, result.front_nodes, dist))
        viewer.add_points(
            np.concatenate(chunks, axis=0),
            name=f"1% front: {METHOD_LABELS.get(method, method)}",
            size=1.8,
            face_color=METHOD_COLOURS.get(method, (1, 0, 1, 1)),
            border_width=0,
        )

    viewer.add_points(coords[sources], name="source nodes", size=16,
                      face_color=SOURCE_COLOUR, border_color="black")
    viewer.add_points(coords[[target]], name="drain target", size=24,
                      face_color=TARGET_COLOUR, border_color="black")

    viewer.text_overlay.visible = True
    viewer.text_overlay.text = (
        f"{summary['run_id']}\n"
        "yellow: sources\ncyan: drain target\n"
        + "\n".join(METHOD_LABELS.get(method, method) for method in methods)
    )
    viewer.text_overlay.font_size = 10
    viewer.dims.set_point(0, 0)


def _usage_masks(usage: np.ndarray) -> list[tuple[str, np.ndarray, float]]:
    return [
        ("usage 1", usage == 1, 0.7),
        ("usage 2-4", (usage >= 2) & (usage <= 4), 1.2),
        ("usage 5-9", (usage >= 5) & (usage <= 9), 2.0),
        ("usage >=10", usage >= 10, 3.2),
    ]


def visualize_highways(viewer, graph, arrays, run_dir: Path, summary: dict) -> None:
    coords = arrays["coords"]
    sources = [int(s) for s in summary["sources"]]
    target = int(summary["target"])
    _background(viewer, coords, largest_component_nodes(graph))

    for method in ("bfs", "resistance"):
        edges, usage = _read_highway_csv(run_dir / f"highways_{method}.csv")
        if len(edges) == 0:
            continue
        origin = coords[edges[:, 0]]
        vectors = np.stack([origin, coords[edges[:, 1]] - origin], axis=1)
        for label, mask, width in _usage_masks(usage):
            if not np.any(mask):
                continue
            viewer.add_vectors(
                vectors[mask],
                name=f"{METHOD_LABELS[method]} highways, {label}",
                edge_width=width,
                vector_style="line",
                edge_color=METHOD_COLOURS[method],
            )

    viewer.add_points(coords[sources], name="source nodes", size=12,
                      face_color=SOURCE_COLOUR, border_color="black")
    viewer.add_points(coords[[target]], name="drain target", size=22,
                      face_color=TARGET_COLOUR, border_color="black")
    viewer.text_overlay.visible = True
    viewer.text_overlay.text = (
        f"{summary['run_id']}\n"
        "yellow: sources\ncyan: drain target\n"
        "gray: BFS highways\nred: resistance highways"
    )
    viewer.text_overlay.font_size = 10


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_id", nargs="?", help="Run id under the experiments folder.")
    parser.add_argument("--run", dest="run_option", help="Run id under the experiments folder.")
    parser.add_argument("--graph", type=Path, default=DEFAULT_GRAPH_PATH, help="Path to the GML graph.")
    parser.add_argument("--experiments", type=Path, default=DEFAULT_EXP_DIR, help="Experiment output folder.")
    parser.add_argument("--methods", nargs="+", default=["bfs", "resistance"],
                        choices=["bfs", "length", "resistance", "radius"],
                        help="Front methods to animate.")
    args = parser.parse_args()
    run_id = args.run_option or args.run_id
    if not run_id:
        raise SystemExit("Run id required. Example: python src/visualize.py exp_A_capillary_seed0")

    graph_path = _abs_path(args.graph)
    exp_dir = _abs_path(args.experiments)
    run_dir = exp_dir / run_id
    if not run_dir.exists():
        raise SystemExit(f"Run dir not found: {run_dir}")
    summary = _load_summary(run_dir)

    _prefer_hardware_opengl()
    try:
        import napari
    except ImportError as exc:
        raise SystemExit("napari not installed. Run: python -m pip install \"napari[all]\"") from exc

    print(f"Loading graph: {graph_path}")
    graph = load_graph(graph_path)
    arrays = graph_arrays(graph)

    viewer = napari.Viewer(title=f"FLOW {run_id}", ndisplay=3)
    _print_gpu_info()
    if summary.get("mode") == "highways":
        visualize_highways(viewer, graph, arrays, run_dir, summary)
    else:
        visualize_front(viewer, graph, arrays, summary, args.methods)
    napari.run()


if __name__ == "__main__":
    main()
