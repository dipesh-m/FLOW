# FLOW Project Notes

Controlled shortest-path experiment on a 3-D vascular graph.

## Core question

With the graph and source rule fixed, how much does the choice of edge cost change the early (1%) front reached from each source? Capillary starts are primary.

## Data

| Item | Value |
|---|---|
| Nodes / edges | ~7.5 M / ~7.8 M |
| Largest connected component | ~7.45 M nodes (used for all selection) |
| Vessel type | `vessel_type` ∈ {1 artery, 2 vein, 3 capillary} |
| Geometry | per-node `coordinates` (`x,y,z` string), per-node `radii` |
| Edge length | `‖coord(u) − coord(v)‖₂` |
| Edge radius | `(r(u) + r(v)) / 2` |

Graph loaded undirected.

## Traversal methods

| Method | Edge cost | Notes |
|---|---:|---|
| `bfs` | 1 | igraph BFS, no weights |
| `length` | L | physical distance |
| `resistance` | L / r⁴ | Hagen-Poiseuille proxy; `r = max(r, 1e-6)` |
| `radius` | 1 / r⁴ | ablation that drops L from `resistance` |

`resistance` and `radius` differ only by the multiplicative `L` factor, so any difference between their fronts is the contribution of length.

## Source selection

`diverse_capillaries_in_lcc`: draw a seeded random pool of `source_pool_size` capillaries from the LCC; greedy k-center on the 3-D coordinates picks `num_sources` spatially spread points. Random-then-k-center matters because capillaries are ~95% of nodes and a "top-radius" pool would bias toward transitional vessels.

## Drain target

Always `largest_vein_in_lcc`: the vein with the largest radius inside the LCC. Fixed across every run.

## Front metric (per source, per method)

Single-source shortest-path distance from the source to all nodes under the chosen cost.

`metrics.csv` columns:

| Column | Meaning |
|---|---|
| `front_1pct_nodes` | size of the front (~74 532 for 7.45 M LCC) |
| `front_1pct_overlap_with_bfs` | `|front_method ∩ front_bfs| / |front_method|` |
| `front_1pct_artery_fraction` | artery share inside the front |
| `front_1pct_overlap_with_radius` | overlap with the `radius` front |

## Hypotheses

| ID | Statement | Metric | Supported when |
|---|---|---|---|
| H1 | Radius-aware costs reshape the 1% front relative to BFS; pure length stays BFS-like. | mean `front_1pct_overlap_with_bfs` for `resistance` vs the same for `length`, capillary-primary | resistance overlap is far below length overlap |
| H2 | Removing length from `resistance` (ablation to `radius`) barely changes the front. | mean `front_1pct_overlap_with_radius` for `resistance`, capillary-primary | overlap close to 1.0 |

## Experiment matrix

| Group | Run id | Source rule | Seed | Sources |
|---|---|---|---:|---:|
| A | `exp_A_capillary_seed{0,42,100,200,300}` | diverse_capillaries_in_lcc | 0/42/100/200/300 | 5 |

A aggregates to 25 sources.

## Reproduction

```powershell
cd FLOW
python src/run_all.py
python src/analyse.py
```