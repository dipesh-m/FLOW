# FLOW

BIMAP SS2026, FAU Erlangen. Author: Dipesh Mann.

FLOW currently tests the capillary-primary front experiment and an artery-source
control. The artery runs check whether the front effect is a property of the cost
function rather than a consequence of starting on capillaries.

FLOW is a controlled shortest-path study on a 3-D mouse cortex vascular graph
(HC1.5, ~7.5 M nodes, ~7.8 M edges). It is not a hemodynamics solver. It is a
graph proxy.

## Question

With the graph, the source rule, and the drain target fixed, how much does the
edge cost change the 1% front, and does the answer survive switching the start
from capillaries to arteries?

## Traversal methods

| Method | Edge cost | Role |
|---|---:|---|
| `bfs` | 1 | hop-count baseline |
| `length` | L | physical-distance baseline |
| `resistance` | L / r⁴ | Hagen-Poiseuille single-tube proxy |
| `radius` | 1 / r⁴ | radius-only ablation of `resistance` |

## Hypotheses

| ID | Metric | Support condition |
|---|---|---|
| H1 | mean `front_1pct_overlap_with_bfs` for `resistance` vs for `length` | resistance overlap far below length overlap |
| H2 | mean `front_1pct_overlap_with_radius` for `resistance` | radius drives most of the front, length still moves part of it |

Group B (arteries) is a source-type control, not a separate hypothesis.

## Experiment matrix

| Group | Runs | Seeds | Sources/run | Purpose |
|---|---:|---|---:|---|
| A capillary front | 5 | 0, 42, 100, 200, 300 | 5 | H1, H2 primary |
| B artery front (control) | 5 | 0, 42, 100, 200, 300 | 5 | source-type control |

All runs target the largest-radius vein in the largest connected component.

## Results (verified)

Means over seeds (25 sources per group), std in parentheses. Full values in
`experiments/analysis.json`.

| Hypothesis | Capillary | Artery | Reading |
|---|---|---|---|
| H1 length↔BFS | 0.86 (0.04) | 0.79 (0.07) | Length stays close to hop count in both. |
| H1 resistance↔BFS | 0.31 (0.15) | 0.26 (0.16) | The radius-aware cost reaches a very different front in both. |
| H2 resistance↔radius | 0.74 (0.08) | 0.76 (0.07) | Radius dominates; length still moves about a quarter. |

The control matches the primary group, so the effect is not specific to capillary
starts.

## Run it

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python src/run_all.py     # needs the HC1.5 graph under data/V2/
python src/analyse.py     # writes analysis.json + figures
```

The outputs under `experiments/` are committed, so `python src/analyse.py` alone
regenerates the analysis and figures without the 2.5 GB graph. Only a full re-run
of `run_all.py` needs the graph under `data/V2/`.

## Layout

```text
configs/        10 YAML configs (groups A, B)
data/V2/        graph (HC1.5.gml + pickle cache)
docs/notes.md   methods detail
experiments/    per-run outputs + analysis.json + _figures/
src/            flow_experiment.py, run_all.py, analyse.py
experiments.csv experiment registry
```

## Limitations

- Graph loaded undirected. No pressure boundaries or conservation laws.
- L/r⁴ is a single-tube proxy, not full hemodynamics.
- The 1% front is source-centered and does not depend on the drain target.
- One cortex sample. Seeds measure within-sample robustness only.
- No functional perfusion ground truth.
