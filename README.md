# FLOW

Biomedical Image Analysis Project SS2026, FAU Erlangen.

FLOW is a controlled shortest-path experiment on a 3-D vascular graph ( ~7.5 M nodes, ~7.8 M edges). It asks the question:

> With the graph, source rule, and drain target fixed, how much does the choice of edge cost change which graph regions are reached first and which source-to-target routes carry the most paths?

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
| H2 | mean `front_1pct_overlap_with_radius` for `resistance` in capillary-primary runs | high (≈ 1.0 = length adds little once radius is in the cost) |

Artery fraction in the 1% front is reported as descriptive context only.

## Experiment matrix

| Group | Runs | Seeds | Purpose |
|---|---:|---|---|
| A capillary front | 5 | 0, 42, 100, 200, 300 | H1, H2 primary |

Each run uses 5 capillary sources selected by random pool + greedy 3-D k-center (25 sources aggregated across seeds). All runs target the largest-radius vein in the LCC.

## Repository layout

```text
FLOW/
  configs/                YAML configs
  data/V2/HC1.5.gml       graph (+ pickle cache, gitignored)
  docs/notes.md           extended methods
  experiments/            generated outputs (per run + analysis.json + _figures/)
  src/
    flow_experiment.py    core: loading, selection, traversals, metrics
    run_all.py            loads graph once, runs every config in configs/
    analyse.py            builds analysis.json and the two figures
  experiments.csv         experiment registry
  requirements.txt
```

## Setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run everything

```powershell
python src/run_all.py        # loads graph once, runs all configs
python src/analyse.py        # writes experiments/analysis.json + figures
```

To run a single config:

```powershell
python src/run_all.py --only exp_A_capillary_seed42
```

## Outputs

Per run (`experiments/<run_id>/`):

| File | Contents |
|---|---|
| `config.yaml` | frozen config copy |
| `summary.json` | graph stats, sources, target, methods, seed |
| `metrics.csv` | one row per (source, method) with the 1% front numbers |
| `paths.csv` | source-to-target shortest-path hops, length, mean radius |
| `graph_summary.csv` | one-row graph-level summary |

Aggregate:

| File | Contents |
|---|---|
| `experiments/analysis.json` | H1 and H2 values plus descriptive context |
| `experiments/_figures/fig1_h1_front_overlap.png` | H1 |
| `experiments/_figures/fig2_h2_radius_overlap.png` | H2 |

---

Graph data not available publicly.
