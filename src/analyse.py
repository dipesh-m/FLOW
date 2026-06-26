"""Aggregate FLOW outputs into analysis.json and figures.

Formal metrics:
    H1: mean front_1pct_overlap_with_bfs for resistance, capillary-primary runs.
    H2: mean front_1pct_overlap_with_radius for resistance, capillary-primary runs.
        Radius dominates the cost, but length still moves about a quarter of the
        front, so the overlap sits near 0.74 rather than at 1.0.
    H3: weighted_jaccard_usage and set_jaccard_usage for the capillary-primary
        highways runs, aggregated as mean +/- std over seeds. Weighted Jaccard
        reflects shared usage mass; set Jaccard is a plain overlap of which
        edges are used.

Artery fractions are descriptive context, not formal tests.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from statistics import mean, stdev
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.cm import ScalarMappable
from matplotlib.collections import LineCollection
from matplotlib.colors import LogNorm, Normalize
from matplotlib.lines import Line2D

EXP_DIR = Path("experiments")
FIG_DIR = EXP_DIR / "_figures"
GRAPH_PATH = Path("data") / "V2" / "HC1.5.gml"
GRAPH_CACHE_PATH = Path("data") / "V2" / "HC1.5.gml.pkl"

METHODS = ("bfs", "length", "resistance", "radius")
SOURCE_GROUP = {
    "diverse_capillaries_in_lcc": "capillary_primary",
    "random_arteries_in_lcc": "artery_control",
}
COLOURS = {
    "bfs": "#737373", "length": "#1f77b4",
    "resistance": "#c43c39", "radius": "#2ca25f",
    "capillary_primary": "#c43c39", "artery_control": "#1f77b4",
}
LABELS = {
    "bfs": "BFS", "length": "Length",
    "resistance": "Resistance", "radius": "Radius",
    "capillary_primary": "Capillary primary", "artery_control": "Artery control",
}
SEED0_FIGURES = {
    "capillary_primary": ("fig4_highways_heatmap_capillary.png", "H3 seed 0: capillary starts to drain"),
    "artery_control": ("fig5_highways_heatmap_artery.png", "H3 seed 0: artery starts to drain"),
}


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _read_json(path: Path) -> dict[str, Any] | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def _stats(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {"mean": None, "std": None, "n": 0}
    return {
        "mean": float(mean(values)),
        "std": float(stdev(values)) if len(values) > 1 else 0.0,
        "n": len(values),
    }


def _front_dirs() -> list[Path]:
    if not EXP_DIR.exists():
        return []
    return [
        p for p in sorted(EXP_DIR.iterdir())
        if p.is_dir() and not p.name.startswith("_") and (p / "metrics.csv").exists()
    ]


def _highway_dirs() -> list[Path]:
    if not EXP_DIR.exists():
        return []
    return [
        p for p in sorted(EXP_DIR.iterdir())
        if p.is_dir() and (p / "highways_summary.json").exists()
    ]


def _collect_front_group(dirs: list[Path]) -> dict[str, Any]:
    overlap_bfs: dict[str, list[float]] = {m: [] for m in METHODS}
    artery: dict[str, list[float]] = {m: [] for m in METHODS}
    res_radius: list[float] = []
    per_run: dict[str, Any] = {}

    for d in dirs:
        rows = _read_csv(d / "metrics.csv")
        if not rows:
            continue
        local: dict[str, list[float]] = {m: [] for m in METHODS}
        local_art: dict[str, list[float]] = {m: [] for m in METHODS}
        local_rr: list[float] = []
        for row in rows:
            method = row.get("method")
            if method not in METHODS:
                continue
            try:
                ob = float(row["front_1pct_overlap_with_bfs"])
                af = float(row["front_1pct_artery_fraction"])
            except (KeyError, ValueError):
                continue
            overlap_bfs[method].append(ob)
            artery[method].append(af)
            local[method].append(ob)
            local_art[method].append(af)
            if method == "resistance":
                v = row.get("front_1pct_overlap_with_radius")
                if v not in (None, ""):
                    try:
                        f = float(v)
                        res_radius.append(f)
                        local_rr.append(f)
                    except ValueError:
                        pass
        per_run[d.name] = {
            "n_sources": len(local["bfs"]),
            "resistance_overlap_with_bfs": _stats(local["resistance"]),
            "resistance_overlap_with_radius": _stats(local_rr),
            "resistance_artery_fraction": _stats(local_art["resistance"]),
        }

    return {
        "n_experiments": len(dirs),
        "n_sources": len(overlap_bfs["bfs"]),
        "overlap_with_bfs": {m: _stats(overlap_bfs[m]) for m in METHODS},
        "resistance_overlap_with_radius": _stats(res_radius),
        "artery_fraction": {m: _stats(artery[m]) for m in METHODS},
        "per_experiment": per_run,
    }


def _collect_highways() -> dict[str, Any]:
    groups: dict[str, dict[str, list]] = {
        g: {"weighted": [], "set": [], "runs": []}
        for g in ("capillary_primary", "artery_control")
    }
    for d in _highway_dirs():
        s = _read_json(d / "highways_summary.json")
        if s is None:
            continue
        group = SOURCE_GROUP.get(str(s.get("source_rule")))
        if group is None:
            continue
        wj, sj = s.get("weighted_jaccard_usage"), s.get("set_jaccard_usage")
        if wj is not None:
            groups[group]["weighted"].append(float(wj))
        if sj is not None:
            groups[group]["set"].append(float(sj))
        groups[group]["runs"].append({
            "run_id": s.get("run_id", d.name),
            "seed": s.get("seed"),
            "n_sources": s.get("n_sources"),
            "weighted_jaccard_usage": wj,
            "set_jaccard_usage": sj,
        })
    out: dict[str, Any] = {}
    for g, vals in groups.items():
        if not vals["runs"]:
            out[g] = None
            continue
        out[g] = {
            "n_runs": len(vals["runs"]),
            "n_sources": vals["runs"][0]["n_sources"],
            "weighted_jaccard_usage": _stats(vals["weighted"]),
            "set_jaccard_usage": _stats(vals["set"]),
            "per_run": vals["runs"],
        }
    return out


def summarise() -> dict[str, Any]:
    by_group: dict[str, list[Path]] = {"capillary_primary": [], "artery_control": []}
    lcc_nodes = lcc_art_frac = None
    for d in _front_dirs():
        s = _read_json(d / "summary.json")
        if s is None:
            continue
        g = SOURCE_GROUP.get(str(s.get("source_rule")))
        if g is None:
            continue
        by_group[g].append(d)
        if lcc_nodes is None:
            lcc_nodes = s.get("largest_component_nodes")
            lcc_art_frac = s.get("lcc_artery_fraction")

    fronts = {g: _collect_front_group(paths) for g, paths in by_group.items()}
    highways = _collect_highways()
    cap = fronts["capillary_primary"]
    art = fronts["artery_control"]
    h3_cap = highways.get("capillary_primary") or {}

    hypotheses: dict[str, Any] = {
        "H1": {
            "statement": "Radius-aware costs reshape the 1% front relative to BFS from capillary starts; length-only stays BFS-like.",
            "metric": "mean front_1pct_overlap_with_bfs (resistance, capillary-primary)",
            "value": cap["overlap_with_bfs"]["resistance"],
            "reference_length_overlap_with_bfs": cap["overlap_with_bfs"]["length"],
        },
        "H2": {
            "statement": "Radius dominates the resistance cost, but length is not negligible: dropping it (resistance to radius) still changes about a quarter of the 1% front.",
            "metric": "mean front_1pct_overlap_with_radius (resistance, capillary-primary)",
            "value": cap["resistance_overlap_with_radius"],
        },
    }
    if h3_cap:
        hypotheses["H3"] = {
            "statement": "BFS and resistance pick different high-usage source-to-target highways.",
            "metric_primary": "weighted_jaccard_usage (capillary-primary highways, mean over seeds)",
            "weighted_jaccard": h3_cap.get("weighted_jaccard_usage"),
            "set_jaccard": h3_cap.get("set_jaccard_usage"),
        }

    return {
        "lcc_nodes": lcc_nodes,
        "lcc_artery_fraction": lcc_art_frac,
        "front_1pct": fronts,
        "highways": highways,
        "hypotheses": hypotheses,
        "descriptive_context": {
            "capillary_primary_resistance_artery_fraction": cap["artery_fraction"]["resistance"],
            "capillary_primary_bfs_artery_fraction": cap["artery_fraction"]["bfs"],
            "artery_control_resistance_overlap_with_bfs": art["overlap_with_bfs"]["resistance"],
            "artery_control_resistance_overlap_with_radius": art["resistance_overlap_with_radius"],
        },
    }


# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------

def _mean(b: dict[str, Any] | None) -> float:
    return 0.0 if not b or b.get("mean") is None else float(b["mean"])


def _std(b: dict[str, Any] | None) -> float:
    return 0.0 if not b or b.get("std") is None else float(b["std"])


def _label_bar(ax, x, y, err=0.0, digits=2) -> None:
    ax.text(x, y + err + 0.025, f"{y:.{digits}f}", ha="center", va="bottom", fontsize=9)


def fig1_front_overlap(a: dict[str, Any]) -> None:
    fig, ax = plt.subplots(figsize=(8.5, 4.8), constrained_layout=True)
    methods = ("length", "resistance", "radius")
    groups = tuple(g for g in ("capillary_primary", "artery_control")
                   if a["front_1pct"][g]["n_sources"] > 0)
    x = np.arange(len(methods))
    width = 0.36 if len(groups) > 1 else 0.5
    offsets = (-width / 2, width / 2) if len(groups) > 1 else (0.0,)
    for off, g in zip(offsets, groups):
        ov = a["front_1pct"][g]["overlap_with_bfs"]
        means = [_mean(ov[m]) for m in methods]
        errs = [_std(ov[m]) for m in methods]
        bars = ax.bar(x + off, means, width, yerr=errs, capsize=3,
                      color=COLOURS[g], edgecolor="black", alpha=0.9, label=LABELS[g])
        for b, m_, e_ in zip(bars, means, errs):
            _label_bar(ax, b.get_x() + b.get_width() / 2, m_, e_)
    ax.axhline(1.0, color="#555", linestyle=":", linewidth=1)
    ax.text(len(methods) - 0.5, 1.005, "BFS self-overlap = 1.0", fontsize=8, color="#555",
            ha="right", va="bottom")
    ax.set_xticks(x)
    ax.set_xticklabels([LABELS[m] for m in methods])
    ax.set_ylabel("1% front overlap with BFS (mean ± std)")
    ax.set_ylim(0, 1.18)
    ax.set_title("H1: How much does the early front diverge from BFS?")
    n_cap = a["front_1pct"]["capillary_primary"]["n_sources"]
    n_art = a["front_1pct"]["artery_control"]["n_sources"]
    label = f"capillary n={n_cap}" + (f"; artery n={n_art}" if n_art > 0 else "")
    ax.text(0.01, 0.97, label,
            transform=ax.transAxes, ha="left", va="top", fontsize=9)
    ax.legend(frameon=False, loc="upper right")
    ax.grid(axis="y", alpha=0.25)
    out = FIG_DIR / "fig1_h1_front_overlap.png"
    fig.savefig(out, dpi=170)
    plt.close(fig)
    print("saved", out)


def fig2_radius_overlap(a: dict[str, Any]) -> None:
    fig, ax = plt.subplots(figsize=(6.8, 4.8), constrained_layout=True)
    groups = tuple(g for g in ("capillary_primary", "artery_control")
                   if a["front_1pct"][g]["n_sources"] > 0)
    vals = [a["front_1pct"][g]["resistance_overlap_with_radius"] for g in groups]
    means = [_mean(v) for v in vals]
    errs = [_std(v) for v in vals]
    x = np.arange(len(groups))
    bars = ax.bar(x, means, 0.55, yerr=errs, capsize=4,
                  color=[COLOURS[g] for g in groups], edgecolor="black")
    for b, m_, e_ in zip(bars, means, errs):
        _label_bar(ax, b.get_x() + b.get_width() / 2, m_, e_)
    ax.axhline(1.0, color="#555", linestyle=":", linewidth=1)
    ax.text(len(groups) - 0.5, 1.005, "identical = 1.0", fontsize=8, color="#555",
            ha="right", va="bottom")
    ax.set_xticks(x)
    ax.set_xticklabels([LABELS[g] for g in groups])
    ax.set_ylabel("Resistance ↔ radius-only 1% front overlap")
    ax.set_ylim(0, 1.18)
    ax.set_title("H2: Dropping length still changes about a quarter of the front")
    out = FIG_DIR / "fig2_h2_radius_overlap.png"
    fig.savefig(out, dpi=170)
    plt.close(fig)
    print("saved", out)


def fig3_highways(a: dict[str, Any]) -> None:
    fig, ax = plt.subplots(figsize=(7.6, 4.8), constrained_layout=True)
    groups = ("capillary_primary", "artery_control")
    metrics = ("weighted_jaccard_usage", "set_jaccard_usage")
    metric_labels = ("Weighted Jaccard\n(usage mass)", "Set Jaccard\n(which edges)")
    x = np.arange(len(metrics))
    width = 0.36
    all_tops = []
    for off, g in zip((-width / 2, width / 2), groups):
        h = a["highways"].get(g) or {}
        means = [_mean(h.get(m)) for m in metrics]
        errs = [_std(h.get(m)) for m in metrics]
        bars = ax.bar(x + off, means, width, yerr=errs, capsize=3,
                      color=COLOURS[g], edgecolor="black", alpha=0.9, label=LABELS[g])
        for b, v, e in zip(bars, means, errs):
            top = v + e
            all_tops.append(top)
            ax.text(b.get_x() + b.get_width() / 2, top + 0.003, f"{v:.3f}",
                    ha="center", va="bottom", fontsize=9)
    y_max = max(all_tops) * 1.45 if all_tops else 0.15
    ax.set_ylim(0, y_max)
    ax.text(0.99, 0.03, "identical = 1.0", fontsize=9, color="#555",
            ha="right", va="bottom", transform=ax.transAxes)
    ax.set_xticks(x)
    ax.set_xticklabels(metric_labels)
    ax.set_ylabel("BFS ↔ resistance highway overlap (mean ± std)")
    ax.set_title("H3: BFS and resistance highways overlap")
    h_cap = a["highways"].get("capillary_primary") or {}
    h_art = a["highways"].get("artery_control") or {}
    ax.text(0.01, 0.97,
            f"capillary: {h_cap.get('n_runs')} seeds x {h_cap.get('n_sources')} sources; "
            f"artery: {h_art.get('n_runs')} seeds x {h_art.get('n_sources')} sources",
            transform=ax.transAxes, ha="left", va="top", fontsize=9)
    ax.legend(frameon=False, loc="upper right")
    ax.grid(axis="y", alpha=0.25)
    out = FIG_DIR / "fig3_h3_highways_jaccard.png"
    fig.savefig(out, dpi=170)
    plt.close(fig)
    print("saved", out)


def _local_graph_path() -> Path | None:
    if GRAPH_PATH.exists():
        return GRAPH_PATH
    if GRAPH_CACHE_PATH.exists():
        return GRAPH_CACHE_PATH
    return None


def _load_coords_and_edges(graph_path: Path) -> tuple[np.ndarray, np.ndarray]:
    if graph_path.suffix == ".pkl":
        import pickle

        with graph_path.open("rb") as f:
            graph = pickle.load(f)
        if graph.is_directed():
            graph = graph.as_undirected(combine_edges="first")
    else:
        from flow_experiment import load_graph

        graph = load_graph(graph_path)
    coords = np.asarray(
        [list(map(float, c.split(","))) for c in graph.vs["coordinates"]],
        dtype=np.float64,
    )
    edges = np.asarray(graph.get_edgelist(), dtype=np.int64)
    return coords, edges


def _seed0_highway_dirs() -> dict[str, Path]:
    out: dict[str, Path] = {}
    for d in _highway_dirs():
        s = _read_json(d / "highways_summary.json")
        if s is None or int(s.get("seed", -1)) != 0:
            continue
        group = SOURCE_GROUP.get(str(s.get("source_rule")))
        if group in SEED0_FIGURES:
            out[group] = d
    return out


def _read_usage(path: Path) -> dict[int, int]:
    usage: dict[int, int] = {}
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            usage[int(row["edge_id"])] = int(row["usage"])
    return usage


def _plot_extent(
    coords: np.ndarray,
    edges: np.ndarray,
    usages: tuple[dict[int, int], dict[int, int]],
    sources: list[int],
    target: int,
) -> tuple[float, float, float, float]:
    edge_ids = sorted(set(usages[0]) | set(usages[1]))
    nodes = set(sources)
    nodes.add(target)
    if edge_ids:
        used_edges = edges[np.asarray(edge_ids, dtype=np.int64)]
        nodes.update(int(n) for n in used_edges.ravel())
    xy = coords[np.asarray(sorted(nodes), dtype=np.int64), :2]
    xmin, ymin = xy.min(axis=0)
    xmax, ymax = xy.max(axis=0)
    pad = 0.04 * max(float(xmax - xmin), float(ymax - ymin), 1.0)
    return float(xmin - pad), float(xmax + pad), float(ymin - pad), float(ymax + pad)


def _line_segments(
    coords: np.ndarray, edges: np.ndarray, usage: dict[int, int]
) -> tuple[np.ndarray, np.ndarray]:
    edge_ids = np.asarray(sorted(usage), dtype=np.int64)
    counts = np.asarray([usage[int(eid)] for eid in edge_ids], dtype=np.float64)
    used_edges = edges[edge_ids]
    segments = np.stack(
        [coords[used_edges[:, 0], :2], coords[used_edges[:, 1], :2]],
        axis=1,
    )
    order = np.argsort(counts)
    return segments[order], counts[order]


def _highway_seed0_figure(
    coords: np.ndarray,
    edges: np.ndarray,
    run_dir: Path,
    out_path: Path,
    title: str,
) -> None:
    summary = _read_json(run_dir / "highways_summary.json")
    if summary is None:
        return

    bfs_usage = _read_usage(run_dir / "highways_bfs.csv")
    resistance_usage = _read_usage(run_dir / "highways_resistance.csv")
    sources = [int(x) for x in summary["sources"]]
    target = int(summary["target"])
    max_count = max(max(bfs_usage.values()), max(resistance_usage.values()))
    norm = LogNorm(vmin=1, vmax=max_count) if max_count > 1 else Normalize(vmin=0, vmax=1)
    cmap = "viridis"

    fig, axes = plt.subplots(1, 2, figsize=(15.5, 7.2), constrained_layout=True)
    xmin, xmax, ymin, ymax = _plot_extent(
        coords, edges, (bfs_usage, resistance_usage), sources, target
    )
    source_xy = coords[np.asarray(sources, dtype=np.int64), :2]
    target_xy = coords[target, :2]

    for ax, method, usage in (
        (axes[0], "BFS", bfs_usage),
        (axes[1], "Resistance", resistance_usage),
    ):
        segments, counts = _line_segments(coords, edges, usage)
        widths = 0.2 + 2.6 * np.log1p(counts) / np.log1p(max_count)
        lc = LineCollection(
            segments, array=counts, cmap=cmap, norm=norm, linewidths=widths,
            alpha=0.88, zorder=2,
        )
        ax.add_collection(lc)
        ax.scatter(
            source_xy[:, 0], source_xy[:, 1], s=18, marker="o",
            facecolor="#2b8cbe", edgecolor="white", linewidth=0.35, zorder=4,
        )
        ax.scatter(
            [target_xy[0]], [target_xy[1]], s=95, marker="X",
            facecolor="#c43c39", edgecolor="black", linewidth=0.5, zorder=5,
        )
        ax.set_xlim(xmin, xmax)
        ax.set_ylim(ymin, ymax)
        ax.set_aspect("equal", adjustable="box")
        ax.set_title(f"{method} paths")
        ax.set_xlabel("x coordinate")
        ax.set_ylabel("y coordinate")
        ax.grid(alpha=0.18, linewidth=0.6)
        ax.text(
            0.02, 0.02,
            f"{len(usage):,} used edges; {sum(usage.values()):,} path-edge traversals",
            transform=ax.transAxes, ha="left", va="bottom", fontsize=8,
            bbox={"facecolor": "white", "edgecolor": "#dddddd", "alpha": 0.86},
        )

    handles = [
        Line2D([0], [0], marker="o", color="none", markerfacecolor="#2b8cbe",
               markeredgecolor="white", markersize=7, label="Start nodes"),
        Line2D([0], [0], marker="X", color="none", markerfacecolor="#c43c39",
               markeredgecolor="black", markersize=8, label="Drain target"),
    ]
    axes[1].legend(handles=handles, frameon=True, facecolor="white", edgecolor="#dddddd",
                   loc="upper right")
    cbar = fig.colorbar(ScalarMappable(norm=norm, cmap=cmap), ax=axes, shrink=0.82, pad=0.015)
    cbar.set_label("Path usage count")
    fig.suptitle(
        f"{title}: BFS vs resistance highways ({summary['n_sources']} starts)",
        fontsize=13,
    )
    fig.savefig(out_path, dpi=190)
    plt.close(fig)
    print("saved", out_path)


def fig4_fig5_highway_seed0_maps() -> None:
    graph_path = _local_graph_path()
    if graph_path is None:
        print("skipped fig4/fig5 highway maps: data/V2/HC1.5.gml not found")
        return
    runs = _seed0_highway_dirs()
    if not runs:
        return
    coords, edges = _load_coords_and_edges(graph_path)
    for group, (filename, title) in SEED0_FIGURES.items():
        run_dir = runs.get(group)
        if run_dir is None:
            continue
        _highway_seed0_figure(coords, edges, run_dir, FIG_DIR / filename, title)


def _fmt(b: dict[str, Any] | None) -> str:
    if not b or b.get("mean") is None:
        return "n/a"
    return f"{b['mean']:.3f} (sd {b['std']:.3f}, n={b['n']})"


def main() -> None:
    EXP_DIR.mkdir(parents=True, exist_ok=True)
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    a = summarise()
    out_path = EXP_DIR / "analysis.json"
    out_path.write_text(json.dumps(a, indent=2), encoding="utf-8")
    print(f"wrote {out_path}")

    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "font.size": 10,
    })
    fig1_front_overlap(a)
    fig2_radius_overlap(a)
    if a["highways"].get("capillary_primary"):
        fig3_highways(a)
        fig4_fig5_highway_seed0_maps()

    h = a["hypotheses"]
    print("H1 (resistance overlap with BFS, capillary):", _fmt(h["H1"]["value"]))
    print("H1 (length overlap with BFS, capillary):    ", _fmt(h["H1"]["reference_length_overlap_with_bfs"]))
    print("H2 (resistance overlap with radius, capillary):", _fmt(h["H2"]["value"]))
    if "H3" in h:
        print("H3 weighted Jaccard (capillary):", _fmt(h["H3"]["weighted_jaccard"]))
        print("H3 set Jaccard (capillary):     ", _fmt(h["H3"]["set_jaccard"]))


if __name__ == "__main__":
    main()
