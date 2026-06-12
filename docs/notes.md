# FLOW Notes

Controlled shortest-path experiment on a 3-D vascular graph.
Current scope: the capillary front experiment.

## Core question

With the graph, the capillary source rule, and the drain target fixed, how much
does the choice of edge cost change the early (1%) front reached from each
source?

## Data

| Item | Value |
|---|---|
| Sample | HC1.5 vascular graph |
| Graph file | `data/V2/HC1.5.gml` (~2.5 GB) |
| Nodes / edges | ~7.5 M / ~7.8 M |
| Largest connected component | ~7.45 M nodes (used for all selection) |
| Vessel type | `vessel_type` ∈ {1 artery, 2 vein, 3 capillary} |
| Geometry | per-node `coordinates` (`x,y,z` string), per-node `radii` |
| Edge length | `‖coord(u) − coord(v)‖₂` |
| Edge radius | `(r(u) + r(v)) / 2` |

The graph is loaded undirected (any directed edge attribute is collapsed with `combine_edges="first"`).

Graph data not available publicly.

## Traversal methods

| Method | Edge cost | Notes |
|---|---:|---|
| `bfs` | 1 | igraph BFS, no weights |
| `length` | L | length in same coordinate units as the graph |
| `resistance` | L / r⁴ | Hagen-Poiseuille proxy; `r = max(r, 1e-6)` to avoid div-by-zero |
| `radius` | 1 / r⁴ | ablation that drops L from `resistance` |

`resistance` and `radius` differ only by the multiplicative `L` factor, so any
difference between their fronts is the contribution of length.

## Source selection

`diverse_capillaries_in_lcc`: draw a seeded random pool of `source_pool_size`
capillaries from the LCC; greedy k-center on the 3-D coordinates picks
`num_sources` spatially spread points. Random-then-k-center matters because
capillaries are ~95% of nodes and a top-radius pool would bias toward
transitional vessels.

## Drain target

`largest_vein_in_lcc`: the vein with the largest radius inside the LCC. Fixed
across every run.

## Front metric (per source, per method)

For each method, FLOW computes single-source shortest-path distance from the
source to all nodes. The 1% front is the closest
`max(1, ⌊0.01 · reachable⌋)` reachable nodes under that cost (~74 532 for the
7.45 M LCC).

`metrics.csv` columns (per row = one source × one method):

| Column | Meaning |
|---|---|
| `front_1pct_nodes` | size of the front |
| `front_1pct_overlap_with_bfs` | `|front_method ∩ front_bfs| / |front_method|` |
| `front_1pct_artery_fraction` | artery share inside the front |
| `front_1pct_overlap_with_radius` | overlap with the `radius` front |

The overlap is a same-size-set intersection over front size, so it is symmetric
and bounded in `[0, 1]`.

## Hypotheses

| ID | Statement | Metric | Supported when |
|---|---|---|---|
| H1 | Radius-aware costs reshape the 1% front relative to BFS; pure length stays BFS-like. | mean `front_1pct_overlap_with_bfs`, resistance vs length | resistance overlap far below length overlap |
| H2 | Removing length from `resistance` (ablation to `radius`) shifts most but not all of the front. | mean `front_1pct_overlap_with_radius` for `resistance` | overlap high but clearly below 1.0 |

Measured: H1 length↔BFS 0.86 (sd 0.04), resistance↔BFS 0.31 (sd 0.15);
H2 resistance↔radius 0.74 (sd 0.08). H2 is an ablation: radius drives most of
the resistance front, but dropping length still changes about a quarter of it.

## Experiment matrix

| Group | Run id | Source rule | Seed | Sources | Purpose |
|---|---|---|---:|---:|---|
| A | `exp_A_capillary_seed{0,42,100,200,300}` | diverse_capillaries_in_lcc | 0/42/100/200/300 | 5 | H1, H2 |

Group A aggregates to 25 sources.

## Reproduction

```powershell
python src/run_all.py
python src/analyse.py
```

`src/run_all.py` loads the graph once and iterates every YAML in `configs/`.
`src/analyse.py` reads every run's outputs and writes `experiments/analysis.json`
plus the front figures.

## Interpretation guide

- H1: compare resistance↔BFS to length↔BFS. The interesting fact is the gap.
- H2: an overlap of 0.74 means length contributes a minority of the front once
  1/r⁴ is present, roughly a quarter.
- Artery fraction is descriptive: large jumps from BFS to resistance fronts mean
  the radius-aware cost is pulled onto thicker (mostly arterial) vessels.
