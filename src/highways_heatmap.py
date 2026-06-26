"""Generate highway heatmap figures from committed experiment outputs.

Loads the graph for node coordinates, reads highways_bfs.csv and
highways_resistance.csv from each group C run, aggregates usage across
seeds, and produces two figures:

    fig4_highways_heatmap_capillary.png   (capillary-primary group)
    fig5_highways_heatmap_artery.png      (artery-control group)

Each figure has two panels: BFS highways (left) and resistance highways (right),
shown as a 2-D projection with edges colored by aggregated usage count.

Usage from FLOW-3/:
    python src/highways_heatmap.py
"""

from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.collections import LineCollection
from matplotlib.colors import LogNorm

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[1]
EXP_DIR = REPO_ROOT / "experiments"
FIG_DIR = EXP_DIR / "_figures"

# Graph can live in a sibling folder (FLOW-final) or locally under data/V2/.
_CANDIDATES = [
    REPO_ROOT / "data" / "V2" / "HC1.5.gml.pkl",
    REPO_ROOT.parent / "FLOW-final" / "data" / "V2" / "HC1.5.gml.pkl",
    REPO_ROOT.parent / "FLOW-final" / "data" / "V2" / "HC1.5.gml",
]

GROUPS = {
    "capillary": [
        "exp_C_highways_capillary_seed0",
        "exp_C_highways_capillary_seed42",
        "exp_C_highways_capillary_seed100",
    ],
    "artery": [
        "exp_C_highways_artery_seed0",
        "exp_C_highways_artery_seed42",
        "exp_C_highways_artery_seed100",
    ],
}


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def find_graph_path() -> Path:
    for p in _CANDIDATES:
        if p.exists():
            return p
    raise FileNotFoundError(
        "Graph not found. Place HC1.5.gml or its .pkl cache under data/V2/ "
        "or in ../FLOW-final/data/V2/."
    )


def load_coords(graph_path: Path) -> np.ndarray:
    """Load graph and extract node coordinates as (N, 3) float64 array."""
    import pickle
    import igraph as ig

    if graph_path.suffix == ".pkl":
        print(f"Loading pickle cache: {graph_path.name}")
        with open(graph_path, "rb") as f:
            g = pickle.load(f)
        if g.is_directed():
            g = g.as_undirected(combine_edges="first")
    else:
        print(f"Loading GML: {graph_path.name}")
        g = ig.Graph.Read_GML(str(graph_path))
        if g.is_directed():
            g = g.as_undirected(combine_edges="first")

    print(f"  {g.vcount():,} nodes, {g.ecount():,} edges")
    coords = np.asarray(
        [list(map(float, c.split(","))) for c in g.vs["coordinates"]],
        dtype=np.float64,
    )
    edges = np.asarray(g.get_edgelist(), dtype=np.int64)
    return coords, edges


def read_highway_csv(path: Path) -> dict[int, int]:
    """Return {edge_id: usage_count} from a highway CSV."""
    usage = {}
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            eid = int(row["edge_id"])
            u = int(row["usage"])
            usage[eid] = u
    return usage


def aggregate_usage(run_ids: list[str], method: str) -> dict[int, int]:
    """Sum usage counts across seeds for one method."""
    total: dict[int, int] = defaultdict(int)
    for rid in run_ids:
        csv_path = EXP_DIR / rid / f"highways_{method}.csv"
        if not csv_path.exists():
            print(f"  warning: {csv_path} not found, skipping")
            continue
        for eid, count in read_highway_csv(csv_path).items():
            total[eid] += count
    return dict(total)


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------

def make_heatmap_figure(
    coords: np.ndarray,
    edges: np.ndarray,
    bfs_usage: dict[int, int],
    res_usage: dict[int, int],
    title: str,
    out_path: Path,
) -> None:
    fig, axes = plt.subplots(
        1, 2, figsize=(16, 7.5), constrained_layout=True,
        facecolor="#1a1a2e",
    )

    for ax, usage, method_label in [
        (axes[0], bfs_usage, "BFS"),
        (axes[1], res_usage, "Resistance (L/r\u2074)"),
    ]:
        ax.set_facecolor("#1a1a2e")
        if not usage:
            ax.set_title(f"{method_label}: no data", color="white")
            continue

        used_eids = sorted(usage.keys())
        counts = np.array([usage[e] for e in used_eids])
        used_edges = edges[used_eids]

        src_coords = coords[used_edges[:, 0]]
        dst_coords = coords[used_edges[:, 1]]
        segments = np.stack([src_coords[:, :2], dst_coords[:, :2]], axis=1)

        # Sort by usage so high-usage edges are drawn on top
        order = np.argsort(counts)
        segments = segments[order]
        counts = counts[order]

        norm = LogNorm(vmin=max(1, counts.min()), vmax=counts.max())
        lw = np.clip(0.15 + counts * 0.12, 0.15, 3.5)
        lc = LineCollection(
            segments, array=counts.astype(float), cmap="inferno", norm=norm,
            linewidths=lw, zorder=1,
        )
        ax.add_collection(lc)

        cbar = fig.colorbar(lc, ax=ax, shrink=0.8, pad=0.02)
        cbar.set_label("Usage count", color="white", fontsize=10)
        cbar.ax.yaxis.set_tick_params(color="white")
        plt.setp(cbar.ax.yaxis.get_ticklabels(), color="white")

        ax.set_xlim(coords[:, 0].min(), coords[:, 0].max())
        ax.set_ylim(coords[:, 1].min(), coords[:, 1].max())
        ax.set_aspect("equal")
        ax.set_title(f"{method_label} highways", fontsize=12, color="white")
        ax.set_xlabel("x (\u03bcm)", color="white")
        ax.set_ylabel("y (\u03bcm)", color="white")
        ax.tick_params(colors="white")
        for spine in ax.spines.values():
            spine.set_color("#444")

        n_edges = len(used_eids)
        total_usage = int(counts.sum())
        ax.text(
            0.02, 0.02,
            f"{n_edges:,} edges, {total_usage:,} total traversals",
            transform=ax.transAxes, fontsize=8, color="#aaa",
            ha="left", va="bottom",
        )

    fig.suptitle(title, fontsize=14, fontweight="bold", color="white")
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=200, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"saved {out_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    graph_path = find_graph_path()
    print(f"Graph: {graph_path}")
    coords, edges = load_coords(graph_path)

    for group_key, run_ids in GROUPS.items():
        print(f"\nGroup: {group_key}")
        bfs_usage = aggregate_usage(run_ids, "bfs")
        res_usage = aggregate_usage(run_ids, "resistance")
        print(f"  BFS: {len(bfs_usage):,} unique edges, resistance: {len(res_usage):,} unique edges")

        if group_key == "capillary":
            title = "Capillary-primary highways: BFS vs Resistance"
            out = FIG_DIR / "fig4_highways_heatmap_capillary.png"
        else:
            title = "Artery-control highways: BFS vs Resistance"
            out = FIG_DIR / "fig5_highways_heatmap_artery.png"

        make_heatmap_figure(coords, edges, bfs_usage, res_usage, title, out)


if __name__ == "__main__":
    main()
