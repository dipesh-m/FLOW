# FLOW

Biomedical Image Analysis Project SS2026, FAU Erlangen.

FLOW currently tests the capillary-primary front experiment. It asks whether the
choice of edge cost changes which graph regions are reached first.

FLOW is a controlled shortest-path study on a 3-D vascular graph
(HC1.5, ~7.5 M nodes, ~7.8 M edges).

## Question

With the graph, the capillary source rule, and the drain target fixed, how much
does the edge cost change the 1% front reached from each source?

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

## Experiment matrix

| Group | Runs | Seeds | Sources/run | Purpose |
|---|---:|---|---:|---|
| A capillary front | 5 | 0, 42, 100, 200, 300 | 5 | H1, H2 |

All runs target the largest-radius vein in the largest connected component.

## Results (current)

Means over 25 capillary sources, std in parentheses. Full values in
`experiments/analysis.json`.

| Hypothesis | Result | Reading |
|---|---|---|
| H1 | length↔BFS 0.86 (0.04); resistance↔BFS 0.31 (0.15) | Supported. Length stays close to hop count; the radius-aware cost reaches a very different front. |
| H2 | resistance↔radius 0.74 (0.08) | Partial. Radius drives most of the front; dropping length still changes about a quarter of it. |

## Run it

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python src/run_all.py     # needs the HC1.5 graph under data/V2/
python src/analyse.py     # writes analysis.json + figures
```

Graph data not available publicly.
