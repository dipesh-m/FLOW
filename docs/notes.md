# FLOW Notes

Controlled shortest-path experiment on a 3-D vascular graph from mouse cortex.
Not a fluid solver. Current scope: the front experiments plus the routing
experiment (H3).

## Core question

With the graph, the source rule, and the drain target fixed, how much does the
choice of edge cost change

1. the early (1%) front reached from each source, and
2. the high-usage source-to-target highways?

Capillary starts are primary. If a radius-aware cost still produces artery-heavy
fronts and very different highways even when the traversal starts from
capillaries, the effect cannot be dismissed as "you started on an artery."

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

## Drain target

`largest_vein_in_lcc`: the vein with the largest radius inside the LCC. Fixed
across every run, so source-to-target paths and highways share the same drain.

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

## Highways metric (per run)

For 100 sources and the same drain target, compute one shortest source-to-target
path under BFS and under resistance. Each edge gets a usage count: how many of
the 100 paths used it.

```text
weighted_jaccard = Σ_e min(usage_bfs[e], usage_res[e]) / Σ_e max(usage_bfs[e], usage_res[e])
set_jaccard       = |{e: usage_bfs[e]>0} ∩ {e: usage_res[e]>0}| / |{e: usage_bfs[e]>0} ∪ {e: usage_res[e]>0}|
```

Weighted Jaccard cares about shared usage mass and is sensitive to total path
length asymmetry (resistance paths are ~3× longer in edges because they prefer
many short capillary edges). Set Jaccard ignores usage counts and answers "what
fraction of the union of highway edges is shared?". Both go into `analysis.json`
and figure 3.

## Hypotheses

| ID | Statement | Metric | Supported when |
|---|---|---|---|
| H1 | Radius-aware costs reshape the 1% front relative to BFS; pure length stays BFS-like. | mean `front_1pct_overlap_with_bfs`, resistance vs length, capillary-primary | resistance overlap far below length overlap |
| H2 | Removing length from `resistance` (ablation to `radius`) shifts most but not all of the front. | mean `front_1pct_overlap_with_radius` for `resistance`, capillary-primary | overlap high but clearly below 1.0 |
| H3 | BFS and resistance pick different high-usage highways. | `weighted_jaccard_usage` and `set_jaccard_usage`, capillary-primary highways | both well below 1.0 |

Measured (capillary / artery): H1 length↔BFS 0.86 / 0.79, resistance↔BFS
0.31 / 0.26; H2 resistance↔radius 0.74 / 0.76; H3 weighted Jaccard
0.025 / 0.030, set Jaccard 0.049 / 0.090. The control matches the primary group
on every metric.

## Experiment matrix

| Group | Run id | Source rule | Seed | Sources | Purpose |
|---|---|---|---:|---:|---|
| A | `exp_A_capillary_seed{0,42,100,200,300}` | diverse_capillaries_in_lcc | 0/42/100/200/300 | 5 | H1, H2 |
| B | `exp_B_artery_seed{0,42,100,200,300}` | random_arteries_in_lcc | 0/42/100/200/300 | 5 | control |
| C | `exp_C_highways_capillary_seed{0,42,100}` | diverse_capillaries_in_lcc | 0/42/100 | 100 | H3 |
| C | `exp_C_highways_artery_seed{0,42,100}` | random_arteries_in_lcc | 0/42/100 | 100 | highways control |

A and B aggregate to 25 sources per group; each C group aggregates 3 seeds.

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
- H3: low weighted Jaccard and low set Jaccard together say "different routes
  carrying different mass." Reporting both prevents the weighted version from
  being read as "they almost agree but with slightly different mass."
- Artery fraction is descriptive: large jumps from BFS to resistance fronts mean
  the radius-aware cost is pulled onto thicker (mostly arterial) vessels.

## Limitations

- Undirected graph; no pressure boundaries, no junction conservation.
- L/r⁴ is a single-tube proxy.
- 1% front is source-centered; the target only matters for the path-level metrics
  and the highways.
- Highways use a single shortest path per (source, target). BFS ties are not
  enumerated.
- One cortex sample; seeds measure within-sample robustness only.
- No functional perfusion ground truth.
