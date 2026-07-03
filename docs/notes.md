# FLOW Notes

## Edge costs

| Method | Cost | Notes |
|---|---:|---|
| `bfs` | 1 | igraph BFS, no weights |
| `length` | L | physical distance |
| `resistance` | L / r^4 | `r = max(r, 1e-6)` |
| `radius` | 1 / r^4 | ablation: drops L from resistance |

## Source selection

| Rule | Procedure |
|---|---|
| `diverse_capillaries_in_lcc` | random pool then greedy k-center on 3-D coords |
| `random_arteries_in_lcc` | uniform random arteries from LCC |

## Drain target

Largest-radius vein in the LCC. Fixed across all runs.

## Front metric

1% closest reachable nodes under each cost. Overlap computed as `|front_a intersection front_b| / |front_a|`.

## Highways metric

100 shortest source-to-target paths under BFS and resistance. Per-edge usage counts, then:

```text
weighted_jaccard = sum min(usage_bfs, usage_res) / sum max(usage_bfs, usage_res)
set_jaccard      = |used_bfs intersection used_res| / |used_bfs union used_res|
```

## Experiment groups

| Group | Configs | Sources/run | Purpose |
|---|---|---:|---|
| A capillary front | 5 seeds | 5 | H1, H2 |
| B artery front | 5 seeds | 5 | control |
| C highways capillary | 3 seeds | 100 | H3 |
| C highways artery | 3 seeds | 100 | control |
