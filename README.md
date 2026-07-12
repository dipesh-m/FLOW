# FLOW

FLOW compares shortest-path fronts and source-to-drain routes on 3-D vascular graphs. The study tests how topology, vessel length, and vessel radius change reachability and edge usage.

## Research questions

| ID | Question | Primary metric |
|---|---|---|
| H1 | Does radius-aware cost change the early front relative to BFS? | 1% front overlap with BFS |
| H2 | Does length change the radius-dominated front? | Resistance-front overlap with radius-only cost |
| H3 | Do BFS and resistance use the same source-to-drain highways? | Weighted and set Jaccard of edge usage |

## Stored results

| Dataset | Nodes | H1 resistance/BFS | H2 resistance/radius | H3 weighted Jaccard |
|---|---:|---:|---:|---:|
| `HC1.5_gurobi` | 7,506,802 | 0.306 | 0.743 | 0.025 |
| `HC1.5_clearmap` | 822,658 | 0.450 | 0.752 | 0.034 |

Each value is the mean across the configured capillary-source runs. Full statistics and figures are stored under `experiments/<graph-name>/`.

## Setup

Python 3.11 or newer is required.

Windows PowerShell:

```powershell
git clone https://github.com/dipesh-m/FLOW.git
cd FLOW
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

macOS or Linux:

```bash
git clone https://github.com/dipesh-m/FLOW.git
cd FLOW
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Graph data

Download `data.zip` from [Google Drive](https://drive.google.com/drive/folders/1cyFxu5LTmuX3N6EWKnaZU6H7_eBX0QTS?usp=sharing), extract it, and place these files in the repository:

```text
data/HC1.5_gurobi.gml
data/HC1.5_clearmap.gml
```

The first graph load creates a `.gml.pkl` cache beside the graph file. Graph files and caches are excluded from Git.

## Run the study

Each graph writes to its own directory. A new graph named `data/example.gml` writes to `experiments/example/`.

Gurobi graph:

```powershell
python src/run_all.py --graph data/HC1.5_gurobi.gml
python src/analyse.py --graph data/HC1.5_gurobi.gml
```

ClearMap graph:

```powershell
python src/run_all.py --graph data/HC1.5_clearmap.gml
python src/analyse.py --graph data/HC1.5_clearmap.gml
```

Run one configuration:

```powershell
python src/run_all.py --graph data/HC1.5_clearmap.gml --only exp_A_capillary_seed42
```

The committed results can be analysed without rerunning the experiments:

```powershell
python src/analyse.py --graph data/HC1.5_gurobi.gml
python src/analyse.py --graph data/HC1.5_clearmap.gml
```

## 3-D visualization

Napari requires OpenGL support. Front runs accept any subset of `bfs`, `length`, `resistance`, and `radius`. Highway runs compare BFS with resistance as defined by H3.

Gurobi graph:

```powershell
python src/visualize.py exp_A_capillary_seed0 --graph data/HC1.5_gurobi.gml --methods bfs resistance
python src/visualize.py exp_C_highways_capillary_seed0 --graph data/HC1.5_gurobi.gml
```

ClearMap graph:

```powershell
python src/visualize.py exp_A_capillary_seed0 --graph data/HC1.5_clearmap.gml --methods bfs resistance
python src/visualize.py exp_C_highways_capillary_seed0 --graph data/HC1.5_clearmap.gml
```

Press Space to pause or resume the animation. On limited graphics hardware, sample the background graph:

```powershell
python src/visualize.py exp_A_capillary_seed0 --graph data/HC1.5_clearmap.gml --methods bfs resistance --vessel-edges sample --vessel-nodes sample
```

## Tests

```powershell
python -m unittest discover -s tests -v
```

## Repository layout

```text
configs/                         experiment definitions
data/                            local graph files and caches
docs/methodology.md              study design and architecture
experiments/<graph-name>/        run outputs, analysis, and figures
src/                             experiment, analysis, and visualization code
tests/                           unit tests
experiments.csv                  experiment registry
```

See [docs/methodology.md](docs/methodology.md) for the cost definitions, sampling rules, metrics, and output schema.
