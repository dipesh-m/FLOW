"""Napari viewer for FLOW experiment outputs."""

from __future__ import annotations

import argparse
import csv
import json
import os
import warnings
from pathlib import Path

import numpy as np

from flow_experiment import (
    dataset_results_dir,
    graph_arrays,
    largest_component_nodes,
    load_graph,
    method_weights,
    run_method,
    validate_graph_counts,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GRAPH_PATH = REPO_ROOT / "data" / "HC1.5_gurobi.gml"
DEFAULT_EXPERIMENTS_ROOT = REPO_ROOT / "experiments"

DEFAULT_FRAMES = 360
DEFAULT_FPS = 60
DEFAULT_FRAME_STEP = 3
DEFAULT_END_HOLD_MS = 150
MIN_FLOW_EDGE_FRAMES = 10
SAMPLED_VESSEL_EDGES = 300_000
SAMPLED_VESSEL_NODES = 300_000
VESSEL_EDGE_WIDTH = 3.5
VESSEL_EDGE_OPACITY = 0.14
VESSEL_NODE_SIZE = 0.18
VESSEL_NODE_OPACITY = 0.10
FRONT_FLOW_EDGE_WIDTH = 5.0
FRONT_FLOW_EDGE_OPACITY = 0.94
HIGHWAY_FLOW_EDGE_WIDTH = 6.0
HIGHWAY_FLOW_OPACITY = 0.98
HIGHWAY_GLOW_MIN_USAGE = 3
HIGHWAY_GLOW_TIERS = (
    ("shared", 0.50, 14.0, 0.24),
    ("major", 0.75, 24.0, 0.40),
    ("main", 0.90, 36.0, 0.56),
)
FRONT_SOURCE_SIZE = 30
FRONT_TARGET_SIZE = 48
HIGHWAY_SOURCE_SIZE = 26
HIGHWAY_TARGET_SIZE = 46
MARKER_BORDER_WIDTH = 0.3
TEXT_OVERLAY_FONT_SIZE = 10

METHOD_COLOURS = {
    "bfs": [0.02, 0.62, 1.0, 1.0],
    "length": [1.0, 0.62, 0.05, 1.0],
    "resistance": [1.0, 0.10, 0.06, 1.0],
    "radius": [0.08, 0.78, 0.32, 1.0],
}
METHOD_COLOUR_LABELS = {
    "bfs": "blue",
    "length": "gold",
    "resistance": "red",
    "radius": "green",
}
METHOD_LABELS = {
    "bfs": "BFS (hop count)",
    "length": "Length (L)",
    "resistance": "Resistance (L/r^4)",
    "radius": "Radius (1/r^4)",
}
VESSEL_EDGE_COLOUR = [0.68, 0.72, 0.76, 0.62]
VESSEL_NODE_COLOUR = [0.68, 0.72, 0.76, 0.12]
SOURCE_COLOUR = [1.0, 0.86, 0.08, 1.0]
TARGET_COLOUR = [0.0, 0.92, 1.0, 1.0]
SOURCE_BORDER_COLOUR = [1.0, 0.48, 0.0, 1.0]
TARGET_BORDER_COLOUR = [0.72, 1.0, 1.0, 1.0]
HIGHWAY_USAGE_COLOUR = [0.16, 1.0, 0.36, 1.0]
HIGHWAY_GLOW_COLOUR = [0.20, 1.0, 0.46, 1.0]


def _abs_path(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


def _load_summary(run_dir: Path) -> dict:
    for name in ("summary.json", "highways_summary.json"):
        path = run_dir / name
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    raise FileNotFoundError(f"No summary in {run_dir}")


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


def _configure_text_overlay(viewer, text: str) -> None:
    viewer.text_overlay.visible = True
    viewer.text_overlay.text = text
    viewer.text_overlay.font_size = TEXT_OVERLAY_FONT_SIZE
    viewer.text_overlay.position = "top_left"
    try:
        viewer.text_overlay.color = "white"
    except Exception:
        pass


def _align_camera_with_xy(viewer) -> None:
    """Show graph x from left to right and y from bottom to top."""
    warnings.filterwarnings(
        "ignore",
        message="Gimbal lock detected.*",
        category=UserWarning,
        module=r"napari\..*",
    )
    viewer.camera.set_view_direction(
        view_direction=(0, 0, -1),
        up_direction=(0, 1, 0),
    )


def _edge_vectors(coords: np.ndarray, edges: np.ndarray) -> np.ndarray:
    origin = coords[edges[:, 0]]
    vectors = np.stack([origin, coords[edges[:, 1]] - origin], axis=1)
    return vectors.astype(np.float32, copy=False)


def _highway_edge_colours(method: str, usage: np.ndarray) -> np.ndarray:
    base = np.asarray(METHOD_COLOURS[method], dtype=np.float32)
    highlight = np.asarray(HIGHWAY_USAGE_COLOUR, dtype=np.float32)
    max_count = int(usage.max()) if len(usage) else 1
    if max_count <= 1:
        return np.tile(base, (len(usage), 1))

    usage_scale = np.log1p(usage.astype(np.float32)) / np.log1p(float(max_count))
    blend = np.clip((usage_scale - 0.35) / 0.65, 0.0, 1.0)[:, None]
    colours = base + (highlight - base) * blend
    colours[:, 3] = 1.0
    np.clip(colours, 0.0, 1.0, out=colours)
    return colours


def _highway_glow_tiers(usage: np.ndarray) -> list[tuple[str, float, float, np.ndarray]]:
    if len(usage) == 0:
        return []
    repeated_edges = usage[usage >= HIGHWAY_GLOW_MIN_USAGE]
    if len(repeated_edges) == 0:
        return []

    thresholds = [
        max(HIGHWAY_GLOW_MIN_USAGE, int(np.quantile(repeated_edges, quantile)))
        for _, quantile, _, _ in HIGHWAY_GLOW_TIERS
    ]
    out: list[tuple[str, float, float, np.ndarray]] = []
    for idx, (label, _, width, opacity) in enumerate(HIGHWAY_GLOW_TIERS):
        lower = thresholds[idx]
        if idx + 1 < len(thresholds):
            upper = thresholds[idx + 1]
            mask = (usage >= lower) & (usage < upper)
        else:
            mask = usage >= lower
        if np.any(mask):
            out.append((label, width, opacity, mask))
    return out


def _refresh_vector_layer(layer, data: np.ndarray) -> None:
    layer._data = data
    layer.set_view_slice()
    layer.events.set_data()


def _lcc_edges(edge_endpoints: np.ndarray, lcc: np.ndarray, n_nodes: int) -> np.ndarray:
    in_lcc = np.zeros(n_nodes, dtype=bool)
    in_lcc[lcc] = True
    return edge_endpoints[in_lcc[edge_endpoints[:, 0]] & in_lcc[edge_endpoints[:, 1]]]


def _graph_edges(edge_endpoints: np.ndarray, lcc: np.ndarray, n_nodes: int, scope: str) -> np.ndarray:
    if scope == "all":
        return edge_endpoints
    return _lcc_edges(edge_endpoints, lcc, n_nodes)


def _graph_nodes(lcc: np.ndarray, n_nodes: int, scope: str) -> np.ndarray:
    if scope == "all":
        return np.arange(n_nodes, dtype=np.int64)
    return lcc


def _select_edges(edges: np.ndarray, mode: str, max_edges: int) -> np.ndarray:
    if mode == "off":
        return np.empty((0, 2), dtype=np.int64)
    if mode == "sample" and len(edges) > max_edges:
        rng = np.random.default_rng(0)
        idx = rng.choice(len(edges), size=max_edges, replace=False)
        return edges[np.sort(idx)]
    return edges


def _select_nodes(nodes: np.ndarray, mode: str, max_nodes: int) -> np.ndarray:
    if mode == "off":
        return np.empty(0, dtype=np.int64)
    if mode == "sample" and len(nodes) > max_nodes:
        rng = np.random.default_rng(0)
        idx = rng.choice(len(nodes), size=max_nodes, replace=False)
        return nodes[np.sort(idx)]
    return nodes


def _vessel_graph(
    viewer,
    coords: np.ndarray,
    edge_endpoints: np.ndarray,
    lcc: np.ndarray,
    scope: str,
    edge_mode: str,
    max_edges: int,
    node_mode: str,
    max_nodes: int,
) -> None:
    nodes = _select_nodes(_graph_nodes(lcc, len(coords), scope), node_mode, max_nodes)
    edges = _select_edges(
        _graph_edges(edge_endpoints, lcc, len(coords), scope),
        edge_mode,
        max_edges,
    )
    scope_label = "full graph" if scope == "all" else "LCC"

    if len(edges):
        viewer.add_vectors(
            _edge_vectors(coords, edges),
            name=f"background: {scope_label} vessel edges ({len(edges):,})",
            edge_width=VESSEL_EDGE_WIDTH,
            vector_style="line",
            edge_color=VESSEL_EDGE_COLOUR,
            opacity=VESSEL_EDGE_OPACITY,
            blending="translucent_no_depth",
        )
    if len(nodes):
        viewer.add_points(
            coords[nodes],
            name=f"background: {scope_label} vessel nodes ({len(nodes):,})",
            size=VESSEL_NODE_SIZE,
            face_color=VESSEL_NODE_COLOUR,
            border_width=0,
            opacity=VESSEL_NODE_OPACITY,
            blending="translucent_no_depth",
            visible=False,
        )


class _FlowAnimData:
    """Edge geometry + timing, sorted by first-appearance frame.

    ``fill_vectors(frame, out, offscreen)`` uses binary search to find the visible count,
    then computes partial-progress vectors for growing edges.  Per-frame
    cost is O(log N + visible) with contiguous memory access.
    """

    __slots__ = ("base", "delta", "first_frame", "inv_duration", "n_frames", "order")

    def __init__(
        self,
        base: np.ndarray,
        delta: np.ndarray,
        first_frame: np.ndarray,
        duration: np.ndarray,
        n_frames: int,
    ) -> None:
        self.order = np.argsort(first_frame, kind="stable")
        self.base = np.ascontiguousarray(base[self.order])            # (N, 3) float32
        self.delta = np.ascontiguousarray(delta[self.order])           # (N, 3) float32
        self.first_frame = np.ascontiguousarray(first_frame[self.order])  # (N,) float32, sorted
        self.inv_duration = np.ascontiguousarray(
            (1.0 / np.maximum(duration[self.order], MIN_FLOW_EDGE_FRAMES)).astype(np.float32)
        )  # (N,) float32
        self.n_frames = n_frames

    def fill_vectors(self, frame: int, out: np.ndarray, offscreen: np.ndarray) -> int:
        """Write growing edge-flow vectors into an existing fixed-size buffer."""
        out.fill(0.0)
        out[:, 0, :] = offscreen
        n = int(np.searchsorted(self.first_frame, frame, side="right"))
        if n == 0:
            return 0
        idx = np.arange(n, dtype=np.int64)
        progress = np.clip(
            (frame - self.first_frame[idx]) * self.inv_duration[idx], 0.0, 1.0
        )
        out[:len(idx), 0, :] = self.base[idx]
        out[:len(idx), 1, :] = progress[:, None] * self.delta[idx]
        return len(idx)


def _build_front_anim(
    coords: np.ndarray,
    edge_endpoints: np.ndarray,
    front_nodes: np.ndarray,
    distance: np.ndarray,
    n_frames: int,
) -> _FlowAnimData | None:
    """Compact animation data for front-growth edges."""
    front_mask = np.zeros(len(coords), dtype=bool)
    front_mask[front_nodes] = True
    mask = front_mask[edge_endpoints[:, 0]] & front_mask[edge_endpoints[:, 1]]
    if not np.any(mask):
        return None

    edges = edge_endpoints[mask]
    d0 = distance[edges[:, 0]]
    d1 = distance[edges[:, 1]]
    finite = np.isfinite(d0) & np.isfinite(d1)
    edges = edges[finite]
    d0 = d0[finite]
    d1 = d1[finite]
    if len(edges) == 0:
        return None

    swap = d0 > d1
    oriented = edges.copy()
    oriented[swap] = oriented[swap][:, ::-1]
    start_dist = np.minimum(d0, d1)
    end_dist = np.maximum(d0, d1)
    cutoff = float(np.nanmax(distance[front_nodes]))
    if cutoff <= 0.0:
        return None

    coords32 = coords.astype(np.float32, copy=False)
    base = coords32[oriented[:, 0]]
    delta = coords32[oriented[:, 1]] - base
    edge_order = np.lexsort((end_dist, start_dist))
    first_frame = np.empty(len(edges), dtype=np.float32)
    first_frame[edge_order] = np.linspace(
        0.0,
        max(1.0, float(n_frames - MIN_FLOW_EDGE_FRAMES)),
        len(edges),
        dtype=np.float32,
    )
    duration = np.full(len(edges), MIN_FLOW_EDGE_FRAMES, dtype=np.float32)

    return _FlowAnimData(base, delta, first_frame, duration, n_frames)


def _build_highway_anim(
    graph,
    arrays: dict[str, np.ndarray],
    method: str,
    sources: list[int],
    target: int,
    run_dir: Path,
    n_frames: int,
) -> tuple[_FlowAnimData, np.ndarray] | None:
    usage = _read_highway_usage(run_dir, method, graph.ecount())
    used_eids = np.flatnonzero(usage > 0)
    if len(used_eids) == 0:
        return None

    weights = method_weights(method, arrays)
    weight_list = weights.tolist() if weights is not None else None
    coords32 = arrays["coords"].astype(np.float32, copy=False)
    edge_endpoints = arrays["edge_endpoints"]
    used_edges = edge_endpoints[used_eids]
    base = coords32[used_edges[:, 0]].copy()
    delta = (coords32[used_edges[:, 1]] - base).copy()
    first_frame = np.full(len(used_eids), np.inf, dtype=np.float32)
    duration = np.full(len(used_eids), MIN_FLOW_EDGE_FRAMES, dtype=np.float32)
    local_idx = {int(eid): i for i, eid in enumerate(used_eids.tolist())}

    for source in sources:
        path = graph.get_shortest_paths(source, to=target, weights=weight_list, output="vpath")[0]
        if len(path) < 2:
            continue
        pairs = list(zip(path[:-1], path[1:]))
        eids = np.asarray(graph.get_eids(pairs), dtype=np.int64)
        lengths = arrays["edge_lengths"][eids]
        total = float(lengths.sum())
        if total <= 0.0:
            continue

        cumulative = np.concatenate([[0.0], np.cumsum(lengths)])
        start_frames = ((cumulative[:-1] / total) * (n_frames - 1)).astype(np.float32)
        end_frames = ((cumulative[1:] / total) * (n_frames - 1)).astype(np.float32)
        edge_duration = np.maximum(end_frames - start_frames, 1.0)

        for edge_idx, eid in enumerate(eids.tolist()):
            idx = local_idx.get(int(eid))
            if idx is None or start_frames[edge_idx] >= first_frame[idx]:
                continue
            first_frame[idx] = start_frames[edge_idx]
            duration[idx] = edge_duration[edge_idx]
            src, dst = pairs[edge_idx]
            base[idx] = coords32[src]
            delta[idx] = coords32[dst] - base[idx]

    first_frame[~np.isfinite(first_frame)] = 0.0
    anim = _FlowAnimData(base, delta, first_frame, duration, n_frames)
    return anim, usage[used_eids][anim.order]


def _read_highway_usage(run_dir: Path, method: str, edge_count: int) -> np.ndarray:
    usage = np.zeros(edge_count, dtype=np.int64)
    with (run_dir / f"highways_{method}.csv").open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            usage[int(row["edge_id"])] = int(row["usage"])
    return usage


class FlowAnimator:
    def __init__(self, viewer, fps: int, frame_step: int, loop: bool, end_hold_ms: int) -> None:
        from qtpy.QtCore import QTimer, Qt

        self._fps = fps
        self._frame_step = frame_step
        self._loop = loop
        self._end_hold_ticks = max(0, round(end_hold_ms / max(1, 1000 // fps)))
        self._hold_ticks_remaining = 0
        self._frame = 0
        self._n_frames = 0
        self._layers: list[tuple] = []
        self._playing = False

        parent = getattr(getattr(viewer, "window", None), "_qt_window", None)
        timer_type = getattr(getattr(Qt, "TimerType", Qt), "PreciseTimer", None)

        self._timer = QTimer(parent)
        if timer_type is not None:
            self._timer.setTimerType(timer_type)
        self._timer.setInterval(max(1, 1000 // fps))
        self._timer.timeout.connect(self._tick)

        self._start_timer = QTimer(parent)
        if timer_type is not None:
            self._start_timer.setTimerType(timer_type)
        self._start_timer.setSingleShot(True)
        self._start_timer.setInterval(350)
        self._start_timer.timeout.connect(self.start)

        try:
            viewer.bind_key("Space", self._on_space, overwrite=True)
        except Exception:
            pass

    def add_layer(
        self,
        layer,
        anim_data: _FlowAnimData,
        offscreen: np.ndarray,
        buffer: np.ndarray,
    ) -> None:
        self._layers.append((layer, anim_data, offscreen, buffer))
        self._n_frames = max(self._n_frames, anim_data.n_frames)

    def start(self) -> None:
        if not self._layers:
            print("FlowAnimator: no layers, nothing to animate")
            return
        if self._start_timer.isActive():
            self._start_timer.stop()
        self._frame = 0
        self._hold_ticks_remaining = 0
        self._playing = True
        print(f"FlowAnimator: {len(self._layers)} layers, "
              f"{self._n_frames} frames @ {self._fps} fps, step {self._frame_step}, "
              f"loop={self._loop}, hold_ticks={self._end_hold_ticks}")
        self._tick()
        if self._playing:
            self._timer.start()

    def deferred_start(self) -> None:
        self._start_timer.start()

    def stop(self) -> None:
        self._playing = False
        self._timer.stop()

    def toggle(self) -> None:
        if self._playing:
            self.stop()
        elif self._frame >= self._n_frames - 1:
            self.start()
        else:
            self._playing = True
            self._timer.start()

    def _on_space(self, viewer) -> None:
        self.toggle()

    def _tick(self) -> None:
        try:
            if self._hold_ticks_remaining > 0:
                for layer, anim, offscreen, buffer in self._layers:
                    anim.fill_vectors(self._n_frames - 1, buffer, offscreen)
                    _refresh_vector_layer(layer, buffer)
                self._hold_ticks_remaining -= 1
                if self._hold_ticks_remaining == 0:
                    self._frame = 0
                return

            for layer, anim, offscreen, buffer in self._layers:
                anim.fill_vectors(self._frame, buffer, offscreen)
                _refresh_vector_layer(layer, buffer)
            next_frame = self._frame + self._frame_step
            if next_frame < self._n_frames:
                self._frame = next_frame
            elif self._loop:
                self._frame = self._n_frames - 1
                for layer, anim, offscreen, buffer in self._layers:
                    anim.fill_vectors(self._frame, buffer, offscreen)
                    _refresh_vector_layer(layer, buffer)
                self._hold_ticks_remaining = self._end_hold_ticks
                if self._hold_ticks_remaining == 0:
                    self._frame = 0
            else:
                self._frame = self._n_frames - 1
                for layer, anim, offscreen, buffer in self._layers:
                    anim.fill_vectors(self._frame, buffer, offscreen)
                    _refresh_vector_layer(layer, buffer)
                self.stop()
        except Exception as exc:
            self._timer.stop()
            import traceback
            traceback.print_exc()
            print(f"FlowAnimator: stopped on error: {exc}")


def visualize_front(
    viewer,
    graph,
    arrays,
    summary,
    methods: list[str],
    graph_scope: str,
    vessel_edges: str,
    max_vessel_edges: int,
    vessel_nodes: str,
    max_vessel_nodes: int,
) -> None:
    n_frames = DEFAULT_FRAMES
    coords = arrays["coords"]
    edge_endpoints = arrays["edge_endpoints"]
    offscreen = (coords.min(axis=0) - float(np.ptp(coords, axis=0).max()) * 2.0).astype(np.float32)
    sources = [int(s) for s in summary["sources"]]
    target = int(summary["target"])
    lcc = largest_component_nodes(graph)
    _vessel_graph(
        viewer, coords, edge_endpoints, lcc, graph_scope,
        vessel_edges, max_vessel_edges, vessel_nodes, max_vessel_nodes,
    )

    animator = FlowAnimator(
        viewer, DEFAULT_FPS, DEFAULT_FRAME_STEP, True, DEFAULT_END_HOLD_MS
    )

    for method in methods:
        weights = method_weights(method, arrays)
        weight_list = weights.tolist() if weights is not None else None
        parts: list[_FlowAnimData] = []
        for src in sources:
            result = run_method(graph, arrays, method, 1, src, target)
            dist = np.asarray(
                graph.distances(source=src, weights=weight_list, mode="all")[0],
                dtype=np.float64,
            )
            anim = _build_front_anim(coords, edge_endpoints, result.front_nodes, dist, n_frames)
            if anim is not None:
                parts.append(anim)
        if not parts:
            continue

        merged = _FlowAnimData(
            np.concatenate([p.base for p in parts], axis=0),
            np.concatenate([p.delta for p in parts], axis=0),
            np.concatenate([p.first_frame for p in parts], axis=0),
            1.0 / np.concatenate([p.inv_duration for p in parts], axis=0),
            n_frames,
        )

        colour = METHOD_COLOURS.get(method, [1, 0, 1, 1])
        buffer = np.zeros((len(merged.base), 2, 3), dtype=np.float32)
        layer = viewer.add_vectors(
            buffer,
            name=f"flow toggle: {METHOD_LABELS.get(method, method)}",
            edge_width=FRONT_FLOW_EDGE_WIDTH,
            vector_style="line",
            edge_color=colour,
            opacity=FRONT_FLOW_EDGE_OPACITY,
            blending="translucent_no_depth",
        )
        buffer = layer.data
        merged.fill_vectors(0, buffer, offscreen)
        _refresh_vector_layer(layer, buffer)
        animator.add_layer(layer, merged, offscreen, buffer)

    viewer.add_points(coords[sources], name="source nodes", size=FRONT_SOURCE_SIZE,
                      face_color=SOURCE_COLOUR, border_color=SOURCE_BORDER_COLOUR,
                      border_width=MARKER_BORDER_WIDTH,
                      blending="translucent_no_depth")
    viewer.add_points(coords[[target]], name="drain target", size=FRONT_TARGET_SIZE,
                      face_color=TARGET_COLOUR, border_color=TARGET_BORDER_COLOUR,
                      border_width=MARKER_BORDER_WIDTH,
                      symbol="x",
                      blending="translucent_no_depth")

    _configure_text_overlay(
        viewer,
        f"{summary['run_id']}\n"
        "sources: yellow | drain: cyan\n"
        + "\n".join(
            f"{METHOD_COLOUR_LABELS.get(method, 'magenta')}: {METHOD_LABELS.get(method, method)}"
            for method in methods
        )
        + "\n[Space] play/pause"
    )

    viewer._flow_animator = animator
    animator.deferred_start()


def visualize_highways(
    viewer,
    graph,
    arrays,
    run_dir: Path,
    summary: dict,
    graph_scope: str,
    vessel_edges: str,
    max_vessel_edges: int,
    vessel_nodes: str,
    max_vessel_nodes: int,
) -> None:
    n_frames = DEFAULT_FRAMES
    coords = arrays["coords"]
    edge_endpoints = arrays["edge_endpoints"]
    offscreen = (coords.min(axis=0) - float(np.ptp(coords, axis=0).max()) * 2.0).astype(np.float32)
    sources = [int(s) for s in summary["sources"]]
    target = int(summary["target"])
    lcc = largest_component_nodes(graph)
    _vessel_graph(
        viewer, coords, edge_endpoints, lcc, graph_scope,
        vessel_edges, max_vessel_edges, vessel_nodes, max_vessel_nodes,
    )

    animator = FlowAnimator(
        viewer, DEFAULT_FPS, DEFAULT_FRAME_STEP, True, DEFAULT_END_HOLD_MS
    )

    for method in ("bfs", "resistance"):
        highway = _build_highway_anim(graph, arrays, method, sources, target, run_dir, n_frames)
        if highway is None:
            continue
        anim, usage = highway
        for glow_label, glow_width, glow_opacity, glow_mask in _highway_glow_tiers(usage):
            glow_anim = _FlowAnimData(
                anim.base[glow_mask],
                anim.delta[glow_mask],
                anim.first_frame[glow_mask],
                1.0 / anim.inv_duration[glow_mask],
                n_frames,
            )
            glow_buffer = np.zeros((len(glow_anim.base), 2, 3), dtype=np.float32)
            glow_layer = viewer.add_vectors(
                glow_buffer,
                name=f"glow: {METHOD_LABELS[method]} {glow_label} highways",
                edge_width=glow_width,
                vector_style="line",
                edge_color=HIGHWAY_GLOW_COLOUR,
                opacity=glow_opacity,
                blending="additive",
            )
            glow_buffer = glow_layer.data
            glow_anim.fill_vectors(0, glow_buffer, offscreen)
            _refresh_vector_layer(glow_layer, glow_buffer)
            animator.add_layer(glow_layer, glow_anim, offscreen, glow_buffer)

        buffer = np.zeros((len(anim.base), 2, 3), dtype=np.float32)
        layer = viewer.add_vectors(
            buffer,
            name=f"flow toggle: {METHOD_LABELS[method]} highways",
            edge_width=HIGHWAY_FLOW_EDGE_WIDTH,
            vector_style="line",
            edge_color=_highway_edge_colours(method, usage),
            opacity=HIGHWAY_FLOW_OPACITY,
            blending="translucent_no_depth",
        )
        buffer = layer.data
        anim.fill_vectors(0, buffer, offscreen)
        _refresh_vector_layer(layer, buffer)
        animator.add_layer(layer, anim, offscreen, buffer)

    viewer.add_points(coords[sources], name="source nodes", size=HIGHWAY_SOURCE_SIZE,
                      face_color=SOURCE_COLOUR, border_color=SOURCE_BORDER_COLOUR,
                      border_width=MARKER_BORDER_WIDTH,
                      blending="translucent_no_depth")
    viewer.add_points(coords[[target]], name="drain target", size=HIGHWAY_TARGET_SIZE,
                      face_color=TARGET_COLOUR, border_color=TARGET_BORDER_COLOUR,
                      border_width=MARKER_BORDER_WIDTH,
                      symbol="x",
                      blending="translucent_no_depth")
    _configure_text_overlay(
        viewer,
        f"{summary['run_id']}\n"
        "sources: yellow | drain: cyan\n"
        "blue: BFS | red: resistance\n"
        "gold: higher path usage\n"
        "[Space] play/pause"
    )

    viewer._flow_animator = animator
    animator.deferred_start()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_id", help="Run id under the dataset result folder.")
    parser.add_argument("--graph", type=Path, default=DEFAULT_GRAPH_PATH, help="Path to the GML graph.")
    parser.add_argument("--experiments", type=Path, help="Override the dataset result folder.")
    parser.add_argument("--methods", nargs="+", default=["bfs", "resistance"],
                        choices=["bfs", "length", "resistance", "radius"],
                        help="Front methods to animate.")
    parser.add_argument("--graph-scope", choices=["all", "lcc"], default="all",
                        help="Draw all graph nodes/edges or only the largest connected component.")
    parser.add_argument("--vessel-edges", choices=["all", "sample", "off"], default="all",
                        help="Draw the underlying vessel edges.")
    parser.add_argument("--max-vessel-edges", type=int, default=SAMPLED_VESSEL_EDGES,
                        help="Number of vessel edges to draw when --vessel-edges sample is used.")
    parser.add_argument("--vessel-nodes", choices=["all", "sample", "off"], default="all",
                        help="Load a hidden background vessel-node layer for napari eye toggling.")
    parser.add_argument("--max-vessel-nodes", type=int, default=SAMPLED_VESSEL_NODES,
                        help="Number of vessel nodes to draw when --vessel-nodes sample is used.")
    args = parser.parse_args()
    run_id = args.run_id

    graph_path = _abs_path(args.graph)
    exp_dir = (
        dataset_results_dir(DEFAULT_EXPERIMENTS_ROOT, graph_path)
        if args.experiments is None
        else _abs_path(args.experiments)
    )
    run_dir = exp_dir / run_id
    if not run_dir.exists():
        raise SystemExit(f"Run dir not found: {run_dir}")
    summary = _load_summary(run_dir)

    _prefer_hardware_opengl()
    try:
        import napari
    except ImportError as exc:
        raise SystemExit("napari not installed. Run: python -m pip install -r requirements.txt") from exc

    print(f"Loading graph: {graph_path}")
    graph = load_graph(graph_path)
    validate_graph_counts(graph, summary)
    arrays = graph_arrays(graph)

    viewer = napari.Viewer(title=f"FLOW {run_id}", ndisplay=3)
    _print_gpu_info()
    if summary.get("mode") == "highways":
        visualize_highways(
            viewer, graph, arrays, run_dir, summary,
            args.graph_scope, args.vessel_edges, args.max_vessel_edges,
            args.vessel_nodes, args.max_vessel_nodes,
        )
    else:
        visualize_front(
            viewer, graph, arrays, summary, args.methods,
            args.graph_scope, args.vessel_edges, args.max_vessel_edges,
            args.vessel_nodes, args.max_vessel_nodes,
        )
    _align_camera_with_xy(viewer)
    napari.run()


if __name__ == "__main__":
    main()
