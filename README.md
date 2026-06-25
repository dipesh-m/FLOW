# FLOW

FLOW is a controlled shortest-path experiment on a 3-D mouse cortex vascular graph (HC1.5, ~7.5 M nodes, ~7.8 M edges). It asks one question:

> With the graph, source rule, and drain target fixed, how much does the choice of edge cost change which graph regions are reached first and which source-to-target routes carry the most paths?

This is not a hemodynamics solver. It is a graph proxy.

## Traversal methods

| Method | Edge cost | Role |
|---|---:|---|
| `bfs` | 1 | hop-count baseline |
| `length` | L | physical-distance baseline |
| `resistance` | L / r⁴ | Hagen-Poiseuille single-tube proxy |
| `radius` | 1 / r⁴ | radius-only ablation of `resistance` |

## Hypotheses (formal metrics)

| ID | Metric | Support condition |
|---|---|---|
| H1 | mean `front_1pct_overlap_with_bfs` for `resistance` in capillary-primary runs | low (≪ `length` overlap which stays BFS-like) |
| H2 | mean `front_1pct_overlap_with_radius` for `resistance` in capillary-primary runs | radius drives most of the cost, but length still matters (overlap well below 1.0) |
| H3 | `weighted_jaccard_usage` and `set_jaccard_usage` between BFS and resistance highways (capillary-primary) | low (different edges, different usage mass) |

Artery fraction in the 1% front is reported as descriptive context only.

## Experiment matrix

| Group | Runs | Seeds | Purpose |
|---|---:|---|---|
| A capillary front | 5 | 0, 42, 100, 200, 300 | H1, H2 primary |
| B artery front (control) | 5 | 0, 42, 100, 200, 300 | source-type control |
| C highways capillary | 3 | 0, 42, 100 | H3 primary |
| C highways artery (control) | 3 | 0, 42, 100 | highways control |

A and B use 5 sources per run (25 sources per group). C uses 100 sources per run (300 sources per group). All runs target the largest-radius vein in the LCC.

## Repository layout

```text
FLOW/
  configs/                YAML configs (16 total)
  data/V2/HC1.5.gml       graph (+ pickle cache)
  docs/notes.md           extended methods
  experiments/            generated outputs (per run + analysis.json + _figures/)
  src/
    flow_experiment.py    core: loading, selection, traversals, metrics, both run drivers
    run_all.py            loads graph once, runs every config in configs/
    analyse.py            builds analysis.json and the three figures
  experiments.csv         experiment registry
  requirements.txt
```

## Setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Python 3.11+. The graph is ~2.5 GB GML; a pickle cache is created on first load and reused (~30 s warm vs ~10 min cold).

## Run everything

```powershell
python src/run_all.py        # loads graph once, runs all 16 configs (~30-40 min)
python src/analyse.py        # writes experiments/analysis.json + figures
```

The run outputs under `experiments/` are committed, so `python src/analyse.py`
alone regenerates `analysis.json` and all three figures without the 2.5 GB graph.
Only a full re-run of `run_all.py` needs the graph under `data/V2/`.

To run a single config:

```powershell
python src/run_all.py --only exp_A_capillary_seed42
```

## Outputs

Per front run (`experiments/<run_id>/`):

| File | Contents |
|---|---|
| `config.yaml` | frozen config copy |
| `summary.json` | graph stats, sources, target, methods, seed |
| `metrics.csv` | one row per (source, method) with the 1% front numbers |
| `paths.csv` | source-to-target shortest-path hops, length, mean radius |
| `graph_summary.csv` | one-row graph-level summary |

Per highways run:

| File | Contents |
|---|---|
| `config.yaml`, `highways_summary.json` | config + per-edge usage statistics, Jaccard values |
| `highways_bfs.csv`, `highways_resistance.csv` | edges with usage > 0 |

Aggregate:

| File | Contents |
|---|---|
| `experiments/analysis.json` | H1, H2, H3 values and descriptive context |
| `experiments/_figures/fig1_h1_front_overlap.png` | H1 |
| `experiments/_figures/fig2_h2_radius_overlap.png` | H2 |
| `experiments/_figures/fig3_h3_highways_jaccard.png` | H3 (weighted + set Jaccard) |

## Results

Numbers below are means over seeds (capillary-primary, 25 sources; std in parentheses). Full values in `experiments/analysis.json`.

| Hypothesis | Result | Reading |
|---|---|---|
| H1 | `length`↔BFS front overlap 0.86 (0.04); `resistance`↔BFS 0.31 (0.15) | Supported. Hop-count and physical distance reach almost the same early front; the radius-weighted cost reaches a very different one. |
| H2 | `resistance`↔`radius` front overlap 0.74 (0.08) | Partial. Radius drives most of the resistance front, but dropping length still changes about a quarter of it. Length is not negligible. |
| H3 | BFS↔resistance highways: weighted Jaccard 0.025 (0.003), set Jaccard 0.049 (0.003) | Supported. The two cost rules route load through almost disjoint edge sets. |

The artery control (group B) shows the same pattern (H2 overlap 0.76, H3 set Jaccard 0.090), so the effect is not specific to capillary sources.

## Limitations

- Graph loaded undirected. No pressure boundaries or conservation laws.
- L/r⁴ is a single-tube proxy, not full hemodynamics.
- The 1% front is source-centered and does not depend on the drain target.
- Highways use one shortest path per source-target pair; BFS ties are not enumerated.
- One cortex sample. Seeds measure within-sample robustness only.
- No functional perfusion ground truth.
