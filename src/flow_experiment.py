"""FLOW core: graph loading, source/target selection, traversals, metrics.

Two experiment kinds share one graph load:

    front      shortest-path distance from each source to all nodes;
               compare the 1% closest nodes ("front") across costs.
    highways   shortest source-to-target paths under BFS and resistance;
               compare per-edge usage vectors.

Edge costs:
    bfs         1                   topology only
    length      L                   physical distance
    resistance  L / r^4             Hagen-Poiseuille single-tube proxy
    radius      1 / r^4             radius-only ablation of resistance

FLOW models vascular transport as a controlled graph proxy on a fixed graph,
with a fixed source rule and drain target.
"""

from __future__ import annotations

import csv
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any, Iterable

import igraph as ig
import numpy as np
import yaml

VESSEL_TYPE_NAMES = {1: "artery", 2: "vein", 3: "capillary"}
FRONT_FRACTION = 0.01
FRONT_METHODS = ("bfs", "length", "resistance", "radius")
HIGHWAY_METHODS = ("bfs", "resistance")
VALID_SOURCE_RULES = ("diverse_capillaries_in_lcc", "random_arteries_in_lcc")


def dataset_results_dir(experiments_root: Path, graph_path: Path) -> Path:
    """Return the result directory associated with a graph file."""
    return experiments_root / graph_path.stem


def validate_graph_counts(graph: ig.Graph, summary: dict[str, Any]) -> None:
    """Reject result files created from a different graph."""
    expected_nodes = summary.get("nodes")
    expected_edges = summary.get("edges")
    if expected_nodes == graph.vcount() and expected_edges == graph.ecount():
        return
    raise ValueError(
        "Graph does not match the experiment results: "
        f"results use {expected_nodes} nodes and {expected_edges} edges; "
        f"loaded graph has {graph.vcount()} nodes and {graph.ecount()} edges."
    )


@dataclass(frozen=True)
class MethodResult:
    method: str
    source_index: int
    source_node: int
    target_node: int
    runtime_s: float
    reachable_nodes: int
    front_nodes: np.ndarray
    path_hops: int
    path_length: float
    path_mean_radius: float


def log(message: str, t0: float) -> None:
    print(f"[{perf_counter() - t0:7.1f}s] {message}", flush=True)


def load_config(config_path: Path) -> dict[str, Any]:
    with config_path.open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    if not isinstance(config, dict):
        raise ValueError(f"Config must be a YAML mapping: {config_path}")

    config.setdefault("mode", "front")
    config.setdefault("num_sources", 5)
    config.setdefault("source_pool_size", 200)
    config.setdefault("seed", 42)

    for key in ("run_id", "source_rule"):
        if key not in config:
            raise ValueError(f"Config missing required key '{key}': {config_path}")
    if config["mode"] not in ("front", "highways"):
        raise ValueError(f"Unknown mode {config['mode']!r}")
    if config["source_rule"] not in VALID_SOURCE_RULES:
        raise ValueError(f"Unknown source_rule {config['source_rule']!r}")
    return config


_NODE_KEYS = ("coordinates", "radii", "vessel_type")
_INT_NODE_KEYS = {"vessel_type"}


def _streaming_load_gml(graph_path: Path) -> ig.Graph:
    node_attrs: dict[str, list] = {k: [] for k in _NODE_KEYS}
    edge_src: list[int] = []
    edge_dst: list[int] = []

    in_node = in_edge = False
    cur: dict[str, str] = {}
    with open(graph_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            if s == "node [":
                in_node, cur = True, {}
                continue
            if s == "edge [":
                in_edge, cur = True, {}
                continue
            if s == "]":
                if in_node:
                    for k in _NODE_KEYS:
                        v = cur.get(k)
                        if v is None:
                            node_attrs[k].append(None)
                        elif k in _INT_NODE_KEYS:
                            try:
                                node_attrs[k].append(int(float(v)))
                            except ValueError:
                                node_attrs[k].append(None)
                        elif k == "radii":
                            try:
                                node_attrs[k].append(float(v))
                            except ValueError:
                                node_attrs[k].append(None)
                        else:
                            node_attrs[k].append(v)
                    in_node = False
                elif in_edge:
                    edge_src.append(int(cur["source"]))
                    edge_dst.append(int(cur["target"]))
                    in_edge = False
                continue
            sp = s.split(" ", 1)
            if len(sp) != 2:
                continue
            k, v = sp[0], sp[1].strip()
            if v.startswith('"') and v.endswith('"'):
                v = v[1:-1]
            cur[k] = v

    n = len(node_attrs["radii"])
    g = ig.Graph(n=n, edges=list(zip(edge_src, edge_dst)), directed=False)
    for k, vals in node_attrs.items():
        if any(v is not None for v in vals):
            g.vs[k] = vals
    return g


def _is_streaming_format(graph_path: Path) -> bool:
    try:
        with open(graph_path, "r", encoding="utf-8", errors="replace") as f:
            for _ in range(50):
                line = f.readline()
                if not line:
                    return False
                if line.strip() == "node [":
                    return True
    except OSError:
        return False
    return False


def load_graph(graph_path: Path) -> ig.Graph:
    """Load a vascular GML file and reuse a pickle cache when available."""
    import pickle

    cache = graph_path.with_suffix(graph_path.suffix + ".pkl")
    if cache.exists() and cache.stat().st_mtime >= graph_path.stat().st_mtime:
        try:
            with open(cache, "rb") as f:
                g = pickle.load(f)
            return g.as_undirected(combine_edges="first") if g.is_directed() else g
        except Exception:
            pass
    if _is_streaming_format(graph_path):
        g = _streaming_load_gml(graph_path)
        try:
            with open(cache, "wb") as f:
                pickle.dump(g, f, protocol=pickle.HIGHEST_PROTOCOL)
        except OSError:
            pass
    else:
        g = ig.Graph.Read_GML(str(graph_path))
    return g.as_undirected(combine_edges="first") if g.is_directed() else g


def _require_attrs(graph: ig.Graph, attrs: Iterable[str]) -> None:
    missing = [a for a in attrs if a not in graph.vertex_attributes()]
    if missing:
        raise ValueError(f"Graph missing vertex attributes: {', '.join(missing)}")


def parse_vertex_coordinates(graph: ig.Graph) -> np.ndarray:
    _require_attrs(graph, ["coordinates"])
    return np.asarray(
        [list(map(float, c.split(","))) for c in graph.vs["coordinates"]],
        dtype=np.float64,
    )


def edge_endpoint_array(graph: ig.Graph) -> np.ndarray:
    return np.asarray(graph.get_edgelist(), dtype=np.int64)


def graph_arrays(graph: ig.Graph) -> dict[str, Any]:
    """All edge weights and node arrays needed for any method."""
    _require_attrs(graph, ["radii", "vessel_type"])
    node_radii = np.asarray(graph.vs["radii"], dtype=np.float64)
    node_types = np.asarray(graph.vs["vessel_type"], dtype=np.int32)
    eps = edge_endpoint_array(graph)

    coords = parse_vertex_coordinates(graph)
    edge_lengths = np.linalg.norm(coords[eps[:, 1]] - coords[eps[:, 0]], axis=1).astype(np.float64)
    edge_radii = ((node_radii[eps[:, 0]] + node_radii[eps[:, 1]]) / 2.0).astype(np.float64)

    safe_r4 = np.maximum(edge_radii, 1e-6) ** 4
    return {
        "node_radii": node_radii,
        "node_types": node_types,
        "coords": coords,
        "edge_endpoints": eps,
        "edge_lengths": edge_lengths,
        "edge_radii": edge_radii,
        "edge_resistance": edge_lengths / safe_r4,
        "edge_inv_radius4": 1.0 / safe_r4,
    }


def largest_component_nodes(graph: ig.Graph) -> np.ndarray:
    comps = graph.connected_components(mode="weak")
    return np.asarray(comps[int(np.argmax(comps.sizes()))], dtype=np.int64)


def lcc_artery_fraction(node_types: np.ndarray, lcc_nodes: np.ndarray) -> float:
    lcc_t = node_types[lcc_nodes]
    return float((lcc_t == 1).sum()) / len(lcc_nodes)


def _k_center(coords: np.ndarray, candidates: np.ndarray, k: int) -> list[int]:
    if len(candidates) <= k:
        return [int(x) for x in candidates]
    pool = coords[candidates]
    chosen = [0]
    min_dist = np.linalg.norm(pool - pool[0], axis=1)
    min_dist[0] = -np.inf
    while len(chosen) < k:
        nxt = int(np.argmax(min_dist))
        chosen.append(nxt)
        np.minimum(min_dist, np.linalg.norm(pool - pool[nxt], axis=1), out=min_dist)
        min_dist[nxt] = -np.inf
    return [int(candidates[i]) for i in chosen]


def choose_sources(
    arrays: dict[str, np.ndarray],
    lcc_nodes: np.ndarray,
    source_rule: str,
    num_sources: int,
    seed: int,
    pool_size: int,
) -> list[int]:
    """Capillary rule: random pool from LCC capillaries then k-center for spread.
    Artery rule: uniform random sample from LCC arteries.
    """
    lcc_types = arrays["node_types"][lcc_nodes]
    if source_rule == "diverse_capillaries_in_lcc":
        candidates = lcc_nodes[lcc_types == 3]
        type_name = "capillary"
    elif source_rule == "random_arteries_in_lcc":
        candidates = lcc_nodes[lcc_types == 1]
        type_name = "artery"
    else:
        raise ValueError(f"Unknown source_rule {source_rule!r}")
    if len(candidates) < num_sources:
        raise ValueError(f"Need {num_sources} {type_name} nodes in LCC, found {len(candidates)}.")

    rng = np.random.default_rng(seed)
    if source_rule == "random_arteries_in_lcc":
        idx = rng.choice(len(candidates), size=num_sources, replace=False)
        return [int(candidates[i]) for i in idx]

    eff_pool = max(num_sources, min(pool_size, len(candidates)))
    pool = candidates[rng.choice(len(candidates), size=eff_pool, replace=False)]
    return _k_center(arrays["coords"], pool, num_sources)


def choose_target(arrays: dict[str, np.ndarray], lcc_nodes: np.ndarray) -> int:
    """Largest-radius vein in the LCC. Fixed drain target across all runs."""
    veins = lcc_nodes[arrays["node_types"][lcc_nodes] == 2]
    if len(veins) == 0:
        raise ValueError("No vein nodes in LCC.")
    return int(veins[int(np.argmax(arrays["node_radii"][veins]))])


def method_weights(method: str, arrays: dict[str, np.ndarray]) -> np.ndarray | None:
    if method == "bfs":
        return None
    if method == "length":
        return arrays["edge_lengths"]
    if method == "resistance":
        return arrays["edge_resistance"]
    if method == "radius":
        return arrays["edge_inv_radius4"]
    raise ValueError(f"Unknown method {method!r}")


def _edge_ids_for_path(graph: ig.Graph, path_nodes: list[int]) -> list[int]:
    if len(path_nodes) < 2:
        return []
    return graph.get_eids(list(zip(path_nodes[:-1], path_nodes[1:])))


def front_nodes(distance: np.ndarray) -> np.ndarray:
    """Return the nearest 1% of reachable nodes."""
    reachable = np.isfinite(distance)
    n_reach = int(reachable.sum())
    ordered = np.argsort(np.where(reachable, distance, np.inf), kind="stable")
    return ordered[: max(1, int(n_reach * FRONT_FRACTION))]


def run_method(
    graph: ig.Graph,
    arrays: dict[str, np.ndarray],
    method: str,
    source_index: int,
    source_node: int,
    target_node: int,
) -> MethodResult:
    weights = method_weights(method, arrays)
    weight_list = weights.tolist() if isinstance(weights, np.ndarray) else weights

    t0 = perf_counter()
    distance = np.asarray(
        graph.distances(source=source_node, weights=weight_list, mode="all")[0],
        dtype=np.float64,
    )
    runtime_s = perf_counter() - t0

    path_nodes = graph.get_shortest_paths(
        source_node, to=target_node, weights=weight_list, output="vpath"
    )[0]
    eids = np.asarray(_edge_ids_for_path(graph, path_nodes), dtype=np.int64)
    path_length = float(arrays["edge_lengths"][eids].sum()) if len(eids) else 0.0
    path_mean_radius = float(arrays["edge_radii"][eids].mean()) if len(eids) else 0.0

    return MethodResult(
        method=method,
        source_index=source_index,
        source_node=source_node,
        target_node=target_node,
        runtime_s=runtime_s,
        reachable_nodes=int(np.isfinite(distance).sum()),
        front_nodes=front_nodes(distance),
        path_hops=max(0, len(path_nodes) - 1),
        path_length=path_length,
        path_mean_radius=path_mean_radius,
    )


def _overlap(a: np.ndarray, b: np.ndarray) -> float:
    if len(a) == 0:
        return 0.0
    return len(set(a.tolist()) & set(b.tolist())) / len(a)


def _artery_fraction(node_types: np.ndarray, nodes: np.ndarray) -> float:
    if len(nodes) == 0:
        return 0.0
    return float((node_types[nodes] == 1).sum()) / len(nodes)


def metric_rows(
    results: list[MethodResult], node_types: np.ndarray
) -> list[dict[str, Any]]:
    by_method = {r.method: r for r in results}
    if "bfs" not in by_method:
        raise ValueError("Method list must include 'bfs'.")
    bfs_front = by_method["bfs"].front_nodes
    radius_front = by_method["radius"].front_nodes if "radius" in by_method else None

    rows: list[dict[str, Any]] = []
    for r in results:
        row = {
            "uid": f"src{r.source_index}_{r.method}",
            "source_index": r.source_index,
            "source_node": r.source_node,
            "target_node": r.target_node,
            "method": r.method,
            "runtime_s": round(r.runtime_s, 6),
            "reachable_nodes": r.reachable_nodes,
            "front_1pct_nodes": len(r.front_nodes),
            "front_1pct_overlap_with_bfs": round(_overlap(r.front_nodes, bfs_front), 6),
            "front_1pct_artery_fraction": round(_artery_fraction(node_types, r.front_nodes), 6),
        }
        if radius_front is not None:
            row["front_1pct_overlap_with_radius"] = round(_overlap(r.front_nodes, radius_front), 6)
        rows.append(row)
    return rows


def path_row(r: MethodResult) -> dict[str, Any]:
    return {
        "uid": f"src{r.source_index}_{r.method}",
        "source_index": r.source_index,
        "source_node": r.source_node,
        "target_node": r.target_node,
        "method": r.method,
        "path_hops": r.path_hops,
        "path_length_um": round(r.path_length, 4),
        "path_mean_radius_um": round(r.path_mean_radius, 4),
    }


def graph_summary_row(graph: ig.Graph, arrays: dict[str, np.ndarray], lcc_nodes: np.ndarray) -> dict[str, Any]:
    nt = arrays["node_types"]
    nr = arrays["node_radii"]
    el = arrays["edge_lengths"]
    er = arrays["edge_radii"]
    row = {
        "nodes": graph.vcount(),
        "edges": graph.ecount(),
        "largest_component_nodes": int(len(lcc_nodes)),
        "lcc_artery_fraction": round(lcc_artery_fraction(nt, lcc_nodes), 6),
        "node_radius_min": round(float(nr.min()), 6),
        "node_radius_mean": round(float(nr.mean()), 6),
        "node_radius_max": round(float(nr.max()), 6),
        "edge_length_min": round(float(el.min()), 6),
        "edge_length_mean": round(float(el.mean()), 6),
        "edge_length_max": round(float(el.max()), 6),
        "edge_radius_min": round(float(er.min()), 6),
        "edge_radius_mean": round(float(er.mean()), 6),
        "edge_radius_max": round(float(er.max()), 6),
    }
    for vtype, name in VESSEL_TYPE_NAMES.items():
        row[f"{name}_nodes"] = int(np.sum(nt == vtype))
    return row


def compute_highways(
    graph: ig.Graph, sources: list[int], target: int, weights: np.ndarray | None
) -> np.ndarray:
    weight_list = weights.tolist() if isinstance(weights, np.ndarray) else weights
    usage = np.zeros(graph.ecount(), dtype=np.int64)
    for source in sources:
        epaths = graph.get_shortest_paths(
            source, to=target, weights=weight_list, output="epath"
        )
        if not epaths or not epaths[0]:
            continue
        np.add.at(usage, np.asarray(epaths[0], dtype=np.int64), 1)
    return usage


def weighted_jaccard(left: np.ndarray, right: np.ndarray) -> float:
    den = float(np.maximum(left, right).sum())
    return 1.0 if den == 0.0 else float(np.minimum(left, right).sum()) / den


def set_jaccard(left: np.ndarray, right: np.ndarray) -> float:
    a, b = left > 0, right > 0
    union = int((a | b).sum())
    return 1.0 if union == 0 else float((a & b).sum()) / union


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"No rows to write: {path}")
    fieldnames: list[str] = []
    for r in rows:
        for k in r:
            if k not in fieldnames:
                fieldnames.append(k)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def run_front(
    graph: ig.Graph,
    arrays: dict[str, np.ndarray],
    lcc_nodes: np.ndarray,
    config: dict[str, Any],
    config_path: Path,
    output_root: Path,
    t0: float,
) -> Path:
    out_dir = output_root / config["run_id"]
    out_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(config_path, out_dir / "config.yaml")

    sources = choose_sources(
        arrays, lcc_nodes,
        config["source_rule"], int(config["num_sources"]),
        int(config["seed"]), int(config["source_pool_size"]),
    )
    target = choose_target(arrays, lcc_nodes)
    log(f"  {config['run_id']}: target={target} (r={arrays['node_radii'][target]:.1f} um), sources={sources}", t0)

    metrics_all: list[dict[str, Any]] = []
    paths_all: list[dict[str, Any]] = []

    for src_idx, source in enumerate(sources, start=1):
        results: list[MethodResult] = []
        for method in FRONT_METHODS:
            r = run_method(graph, arrays, method, src_idx, source, target)
            results.append(r)
            paths_all.append(path_row(r))
        metrics_all.extend(metric_rows(results, arrays["node_types"]))
        log(f"  src {src_idx}/{len(sources)} done", t0)

    write_csv(out_dir / "metrics.csv", metrics_all)
    write_csv(out_dir / "paths.csv", paths_all)
    write_csv(out_dir / "graph_summary.csv", [graph_summary_row(graph, arrays, lcc_nodes)])
    summary = {
        "run_id": config["run_id"],
        "mode": "front",
        "nodes": graph.vcount(),
        "edges": graph.ecount(),
        "largest_component_nodes": int(len(lcc_nodes)),
        "lcc_artery_fraction": round(lcc_artery_fraction(arrays["node_types"], lcc_nodes), 6),
        "source_rule": config["source_rule"],
        "target_rule": "largest_vein_in_lcc",
        "seed": int(config["seed"]),
        "num_sources": int(config["num_sources"]),
        "source_pool_size": int(config["source_pool_size"]),
        "sources": sources,
        "target": target,
        "methods": list(FRONT_METHODS),
        "front_fraction": FRONT_FRACTION,
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return out_dir


def run_highways(
    graph: ig.Graph,
    arrays: dict[str, np.ndarray],
    lcc_nodes: np.ndarray,
    config: dict[str, Any],
    config_path: Path,
    output_root: Path,
    t0: float,
) -> Path:
    out_dir = output_root / config["run_id"]
    out_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(config_path, out_dir / "config.yaml")

    sources = choose_sources(
        arrays, lcc_nodes,
        config["source_rule"], int(config["num_sources"]),
        int(config["seed"]), int(config["source_pool_size"]),
    )
    target = choose_target(arrays, lcc_nodes)
    log(f"  {config['run_id']}: target={target}, n_sources={len(sources)}", t0)

    usage_by_method: dict[str, np.ndarray] = {}
    for method in HIGHWAY_METHODS:
        usage = compute_highways(graph, sources, target, method_weights(method, arrays))
        usage_by_method[method] = usage
        log(
            f"    {method}: total path edges={int(usage.sum()):,}, unique={int((usage > 0).sum()):,}",
            t0,
        )

    eps = arrays["edge_endpoints"]
    for method in HIGHWAY_METHODS:
        usage = usage_by_method[method]
        nz = np.flatnonzero(usage > 0)
        with (out_dir / f"highways_{method}.csv").open("w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["edge_id", "src", "dst", "length_um", "radius_um", "usage"])
            for eid in nz.tolist():
                w.writerow([
                    eid, int(eps[eid, 0]), int(eps[eid, 1]),
                    round(float(arrays["edge_lengths"][eid]), 4),
                    round(float(arrays["edge_radii"][eid]), 4),
                    int(usage[eid]),
                ])

    wj = weighted_jaccard(usage_by_method["bfs"], usage_by_method["resistance"])
    sj = set_jaccard(usage_by_method["bfs"], usage_by_method["resistance"])

    summary = {
        "run_id": config["run_id"],
        "mode": "highways",
        "nodes": graph.vcount(),
        "edges": graph.ecount(),
        "largest_component_nodes": int(len(lcc_nodes)),
        "source_rule": config["source_rule"],
        "target_rule": "largest_vein_in_lcc",
        "seed": int(config["seed"]),
        "n_sources": len(sources),
        "sources": sources,
        "target": int(target),
        "methods": list(HIGHWAY_METHODS),
        "weighted_jaccard_usage": wj,
        "set_jaccard_usage": sj,
        "usage_summary": {
            m: {
                "total_path_edges": int(usage_by_method[m].sum()),
                "unique_edges_used": int((usage_by_method[m] > 0).sum()),
            }
            for m in HIGHWAY_METHODS
        },
    }
    (out_dir / "highways_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return out_dir
