# FLOW Notes

Controlled shortest-path experiment on a 3-D vascular graph from mouse cortex.
Not a fluid solver. Current scope: the capillary front experiment plus an artery
control group.

## Core question

With the graph, the source rule, and the drain target fixed, how much does the
choice of edge cost change the early (1%) front reached from each source, and
does the answer survive switching the start from capillaries to arteries?

Capillary starts are primary. If a radius-aware cost still produces artery-heavy
fronts even when the traversal starts from capillaries, the effect cannot be
dismissed as "you started on an artery." The artery group is the control that
checks this.

## Data

| Item | Value |
|---|---|
| Sample | HC1.5 mouse cortex |
| Graph file | `data/V2/HC1.5.gml` (~2.5 GB) |
| Nodes / edges | ~7.5 M / ~7.8 M |
| Largest connected component | ~7.45 M nodes (used for all selection) |
| Vessel type | `vessel_type` ∈ {1 artery, 2 vein, 3 capillary} |
| Geometry | per-node `coordinates` (`x,y,z` string), per-node `radii` |
| Edge length | `‖coord(u) − coord(v)‖₂` |
| Edge radius | `(r(u) + r(v)) / 2` |

The graph is loaded undirected (any directed edge attribute is collapsed with `combine_edges="first"`).

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

| Rule | Procedure |
|---|---|
| `diverse_capillaries_in_lcc` | seeded random pool of `source_pool_size` capillaries from the LCC; greedy k-center on 3-D coordinates picks `num_sources` spread points |
| `random_arteries_in_lcc` | uniform random `num_sources` arteries from the LCC |

For capillaries, random-then-k-center matters because capillaries are ~95% of
nodes and a top-radius pool would bias toward transitional vessels.

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
| H1 | Radius-aware costs reshape the 1% front relative to BFS; pure length stays BFS-like. | mean `front_1pct_overlap_with_bfs`, resistance vs length, capillary-primary | resistance overlap far below length overlap |
| H2 | Removing length from `resistance` (ablation to `radius`) shifts most but not all of the front. | mean `front_1pct_overlap_with_radius` for `resistance`, capillary-primary | overlap high but clearly below 1.0 |

Group B (arteries) is a source-type control, not a separate hypothesis.

Measured (capillary / artery): H1 length↔BFS 0.86 / 0.79, resistance↔BFS
0.31 / 0.26; H2 resistance↔radius 0.74 / 0.76. The control matches the primary
group, so the front effect is a property of the cost function, not the start
vessel type.

## Experiment matrix

| Group | Run id | Source rule | Seed | Sources | Purpose |
|---|---|---|---:|---:|---|
| A | `exp_A_capillary_seed{0,42,100,200,300}` | diverse_capillaries_in_lcc | 0/42/100/200/300 | 5 | H1, H2 |
| B | `exp_B_artery_seed{0,42,100,200,300}` | random_arteries_in_lcc | 0/42/100/200/300 | 5 | control |

Each group aggregates to 25 sources.

## Reproduction

```powershell
python src/run_all.py
python src/analyse.py
```

## Interpretation guide

- H1: compare resistance↔BFS to length↔BFS. The interesting fact is the gap.
- H2: an overlap of 0.74 means length contributes a minority of the front once
  1/r⁴ is present, roughly a quarter. It does not mean L/r⁴ is the correct
  hemodynamic cost.
- Compare A and B: matching values mean the effect is not specific to capillary
  starts.
- Artery fraction is descriptive: large jumps from BFS to resistance fronts mean
  the radius-aware cost is pulled onto thicker (mostly arterial) vessels.

## Limitations

- Undirected graph; no pressure boundaries, no junction conservation.
- L/r⁴ is a single-tube proxy.
- 1% front is source-centered and does not depend on the drain target.
- One cortex sample; seeds measure within-sample robustness only.
- No functional perfusion ground truth.
