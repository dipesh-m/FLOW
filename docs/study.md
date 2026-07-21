# Study

## Objective

FLOW evaluates how edge-cost definitions affect shortest-path fronts and source-to-drain routes in two fixed 3-D vascular graphs. The study compares topology, physical length, and radius-dependent costs under controlled source and target selection.

## Hypotheses

- **H1:** Including vessel radius changes shortest-path fronts compared with topology- and length-based routing.
- **H2:** Vessel radius affects resistance-weighted routes more than vessel length.
- **H3:** Topology-based and resistance-weighted routing produce different source-to-drain highways.

## Experimental design

Each front run uses one seeded source set for all four cost methods. Each highway run uses one seeded source set and one drain target for BFS and resistance. The edge-cost definition is the controlled change within a run.

| Group | Runs | Sources per run | Role |
|---|---:|---:|---|
| A, capillary fronts | 5 seeds | 5 | Primary evaluation of H1 and H2 |
| B, artery fronts | 5 seeds | 5 | Source-type control for H1 and H2 |
| C, capillary highways | 3 seeds | 100 | Primary evaluation of H3 |
| C, artery highways | 3 seeds | 100 | Source-type control for H3 |

The experiment registry in [`experiments.csv`](../experiments.csv) records each run ID, hypothesis, controlled change, metric, and interpretation. The YAML files under [`configs/`](../configs/) define the source rule, seed, source count, and run mode.

## Methods

### Input graphs

| Graph | Nodes | Edges | Largest connected component |
|---|---:|---:|---:|
| `HC1.5_gurobi.gml` | 7,506,802 | 7,832,373 | 7,453,213 |
| `HC1.5_clearmap.gml` | 822,658 | 1,168,039 | 813,874 |

Each node supplies a 3-D coordinate, radius, and vessel type. Each edge radius is the mean of its endpoint radii. The implementation clamps radii to `1e-6` before applying inverse fourth-power costs.

### Edge costs

| Method | Edge cost | Role |
|---|---:|---|
| BFS | `1` | Topology baseline |
| Length | `L` | Physical-distance control |
| Resistance | `L / r^4` | Radius-aware path proxy |
| Radius | `1 / r^4` | Resistance ablation without length |

The resistance cost follows the length and radius dependence of the single-tube Hagen-Poiseuille relation. FLOW uses this term as a graph cost and does not model pressure, velocity, or fluid dynamics.

### Sources and target

Capillary runs draw a seeded random pool from capillary nodes in the largest connected component, then apply greedy k-center selection in 3-D. Artery-control runs use a seeded uniform sample of artery nodes from the same component.

All runs use the largest-radius vein in the largest connected component as the drain target.

### Metrics

The front for one source and method contains the nearest 1% of reachable nodes. H1 compares the length and resistance fronts with BFS. H2 compares the resistance front with the radius-only front and with BFS.

Highway experiments count how many source-to-target paths use each edge. H3 reports:

```text
weighted_jaccard = sum(min(usage_bfs, usage_resistance))
                   / sum(max(usage_bfs, usage_resistance))

set_jaccard = |used_bfs intersection used_resistance|
              / |used_bfs union used_resistance|
```

## Results

Values report mean +/- sample standard deviation. Front statistics contain 25 source-level comparisons from five seeded capillary runs. Highway statistics contain three seeded runs with 100 capillary sources per run.

| Graph | Length/BFS front overlap | Resistance/BFS front overlap | Resistance/radius front overlap | Highway weighted Jaccard | Highway set Jaccard |
|---|---:|---:|---:|---:|---:|
| `HC1.5_gurobi` | 0.856 +/- 0.038 | 0.306 +/- 0.148 | 0.743 +/- 0.081 | 0.025 +/- 0.003 | 0.049 +/- 0.003 |
| `HC1.5_clearmap` | 0.821 +/- 0.063 | 0.450 +/- 0.198 | 0.752 +/- 0.074 | 0.034 +/- 0.001 | 0.054 +/- 0.005 |

The observed ordering is consistent with H1 in both graphs: length-weighted fronts retain more overlap with BFS than resistance-weighted fronts. Resistance/radius overlap exceeds resistance/BFS overlap in both graphs, consistent with H2. Low weighted and set Jaccard values show limited agreement between BFS and resistance highway usage, consistent with H3.

The artery-source runs provide a source-type control. Full per-run values, artery-control summaries, and figures are stored under [`experiments/`](../experiments/).

## Interpretation limits

The analysis describes two supplied graph reconstructions and the configured source-selection rules. Seed replicates measure variation across sampled source sets. The study does not estimate population-level effects or perform statistical hypothesis tests.

The resistance term ranks graph paths through a simplified vessel-cost proxy. It does not represent a hemodynamic simulation.

## Conclusion

Across both graphs, radius-dependent costs changed early shortest-path fronts relative to the topology baseline. Length weighting remained closer to BFS, while resistance weighting remained closer to radius-only weighting than to BFS. BFS and resistance also concentrated source-to-drain traffic on different edge sets. These conclusions apply to the analyzed graphs, cost definitions, and sampling design.

## Output schema

```text
experiments/<graph-name>/
|-- analysis.json
|-- _figures/
`-- <run_id>/
    |-- config.yaml
    |-- summary.json or highways_summary.json
    |-- metrics.csv and paths.csv
    `-- highways_bfs.csv and highways_resistance.csv
```

Front runs produce `metrics.csv`, `paths.csv`, `graph_summary.csv`, and `summary.json`. Highway runs produce one edge-usage CSV per method and `highways_summary.json`. Files that do not apply to a run type are absent.
