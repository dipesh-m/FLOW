"""Aggregate FLOW outputs into analysis.json and two figures.

Formal metrics (capillary-primary runs):
    H1: mean front_1pct_overlap_with_bfs for resistance (low) vs length (BFS-like).
    H2: mean front_1pct_overlap_with_radius for resistance (high; length adds
        little once radius is in the cost).
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from statistics import mean, stdev
from typing import Any

import matplotlib.pyplot as plt
import numpy as np

EXP_DIR = Path("experiments")
FIG_DIR = EXP_DIR / "_figures"

METHODS = ("bfs", "length", "resistance", "radius")
SOURCE_GROUP = {"diverse_capillaries_in_lcc": "capillary_primary"}
COLOURS = {
    "bfs": "#737373", "length": "#1f77b4",
    "resistance": "#c43c39", "radius": "#2ca25f",
    "capillary_primary": "#c43c39",
}
LABELS = {
    "bfs": "BFS", "length": "Length",
    "resistance": "Resistance", "radius": "Radius",
    "capillary_primary": "Capillary primary",
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


def summarise() -> dict[str, Any]:
    by_group: dict[str, list[Path]] = {"capillary_primary": []}
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
    cap = fronts["capillary_primary"]

    return {
        "lcc_nodes": lcc_nodes,
        "lcc_artery_fraction": lcc_art_frac,
        "front_1pct": fronts,
        "hypotheses": {
            "H1": {
                "statement": "Radius-aware costs reshape the 1% front relative to BFS from capillary starts; length-only stays BFS-like.",
                "metric": "mean front_1pct_overlap_with_bfs (resistance, capillary-primary)",
                "value": cap["overlap_with_bfs"]["resistance"],
                "reference_length_overlap_with_bfs": cap["overlap_with_bfs"]["length"],
            },
            "H2": {
                "statement": "Removing length from the resistance cost barely changes the front; radius dominates.",
                "metric": "mean front_1pct_overlap_with_radius (resistance, capillary-primary)",
                "value": cap["resistance_overlap_with_radius"],
            },
        },
        "descriptive_context": {
            "capillary_primary_resistance_artery_fraction": cap["artery_fraction"]["resistance"],
            "capillary_primary_bfs_artery_fraction": cap["artery_fraction"]["bfs"],
        },
    }


def _mean(b: dict[str, Any] | None) -> float:
    return 0.0 if not b or b.get("mean") is None else float(b["mean"])


def _std(b: dict[str, Any] | None) -> float:
    return 0.0 if not b or b.get("std") is None else float(b["std"])


def _label_bar(ax, x, y, err=0.0, digits=2) -> None:
    ax.text(x, y + err + 0.025, f"{y:.{digits}f}", ha="center", va="bottom", fontsize=9)


def fig1_front_overlap(a: dict[str, Any]) -> None:
    fig, ax = plt.subplots(figsize=(7.0, 4.8), constrained_layout=True)
    methods = ("length", "resistance", "radius")
    x = np.arange(len(methods))
    ov = a["front_1pct"]["capillary_primary"]["overlap_with_bfs"]
    means = [_mean(ov[m]) for m in methods]
    errs = [_std(ov[m]) for m in methods]
    bars = ax.bar(x, means, 0.55, yerr=errs, capsize=4,
                  color=[COLOURS[m] for m in methods], edgecolor="black", alpha=0.9)
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
    ax.text(0.01, 0.97, f"capillary n={n_cap}", transform=ax.transAxes,
            ha="left", va="top", fontsize=9)
    ax.grid(axis="y", alpha=0.25)
    out = FIG_DIR / "fig1_h1_front_overlap.png"
    fig.savefig(out, dpi=170)
    plt.close(fig)
    print("saved", out)


def fig2_radius_overlap(a: dict[str, Any]) -> None:
    fig, ax = plt.subplots(figsize=(6.5, 5.0), constrained_layout=True)
    v = a["front_1pct"]["capillary_primary"]["resistance_overlap_with_radius"]
    m_, e_ = _mean(v), _std(v)
    bars = ax.bar([0], [m_], 0.45, yerr=[e_], capsize=5,
                  color=COLOURS["capillary_primary"], edgecolor="black")
    for b in bars:
        _label_bar(ax, b.get_x() + b.get_width() / 2, m_, e_)
    ax.axhline(1.0, color="#555", linestyle=":", linewidth=1)
    ax.text(0.95, 1.005, "identical = 1.0", fontsize=8, color="#555",
            ha="right", va="bottom", transform=ax.get_yaxis_transform())
    ax.set_xticks([0])
    ax.set_xticklabels([LABELS["capillary_primary"]])
    ax.set_xlim(-0.6, 0.6)
    ax.set_ylabel("Resistance \u2194 radius-only 1% front overlap")
    ax.set_ylim(0, 1.18)
    n_cap = a["front_1pct"]["capillary_primary"]["n_sources"]
    ax.text(0.02, 0.97, f"capillary n={n_cap}", transform=ax.transAxes,
            ha="left", va="top", fontsize=9)
    ax.grid(axis="y", alpha=0.25)
    ax.set_title("H2: dropping length from the resistance cost\nbarely moves the front",
                 fontsize=11)
    out = FIG_DIR / "fig2_h2_radius_overlap.png"
    fig.savefig(out, dpi=170)
    plt.close(fig)
    print("saved", out)


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

    h = a["hypotheses"]
    print("H1 (resistance overlap with BFS, capillary):", _fmt(h["H1"]["value"]))
    print("H1 (length overlap with BFS, capillary):    ", _fmt(h["H1"]["reference_length_overlap_with_bfs"]))
    print("H2 (resistance overlap with radius, capillary):", _fmt(h["H2"]["value"]))


if __name__ == "__main__":
    main()
