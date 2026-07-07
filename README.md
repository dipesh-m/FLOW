# FLOW

Controlled shortest-path study on a 3-D vascular graph (HC1.5, ~7.5 M nodes).
Edge cost determines which vessels get reached first and which carry routed traffic.

## Hypotheses

| ID | Question | Metric |
|---|---|---|
| H1 | Does radius-aware cost change the early front vs BFS? | `front_1pct_overlap_with_bfs` |
| H2 | Does removing length from resistance still change the front? | `front_1pct_overlap_with_radius` |
| H3 | Do BFS and resistance route traffic through the same edges? | `weighted_jaccard_usage`, `set_jaccard_usage` |

## Results

| Hypothesis | Capillary | Artery (control) |
|---|---|---|
| H1 length vs BFS | 0.86 (0.04) | 0.79 (0.07) |
| H1 resistance vs BFS | 0.31 (0.15) | 0.26 (0.16) |
| H2 resistance vs radius | 0.74 (0.08) | 0.76 (0.07) |
| H3 weighted Jaccard | 0.025 (0.003) | 0.030 (0.003) |
| H3 set Jaccard | 0.049 (0.003) | 0.090 (0.003) |

Full values in `experiments/analysis.json`. Figures in `experiments/_figures/`.
The figures include overlap summaries, highway maps, and BFS-vs-resistance front maps.

## Getting started

Windows Command Prompt:

```cmd
git clone https://github.com/dipesh-m/FLOW.git
cd FLOW
python -m venv .venv
.venv\Scripts\activate.bat
python -m pip install -r requirements.txt
```

macOS/Linux:

```bash
git clone https://github.com/dipesh-m/FLOW.git
cd FLOW
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Python 3.11+.

## Graph files

Download `data.zip` from [Google Drive](https://drive.google.com/drive/folders/1cyFxu5LTmuX3N6EWKnaZU6H7_eBX0QTS?usp=sharing).

Extract it and copy the extracted `data/` folder into the repository root. The expected layout is:

```text
data/HC1.5_gurobi.gml
data/HC1.5_clearmap.gml
```

The pickle cache is created next to each GML file.

## Full re-run

The default graph is `data/HC1.5_gurobi.gml`.

```powershell
python src/run_all.py
python src/analyse.py
```

Use another GML file:

```powershell
python src/run_all.py --graph data/HC1.5_clearmap.gml
python src/analyse.py --graph data/HC1.5_clearmap.gml
```

Output is written under `experiments/`. A later run overwrites files with the same run names. Copy `experiments/` first if you need to keep a previous result.

Run one config:

```powershell
python src/run_all.py --only exp_A_capillary_seed42
```

To keep two graph runs side by side, write to a named output folder:

```powershell
python src/run_all.py --graph data/HC1.5_gurobi.gml --output experiments_gurobi
python src/analyse.py --experiments experiments_gurobi --graph data/HC1.5_gurobi.gml
python src/run_all.py --graph data/HC1.5_clearmap.gml --output experiments_clearmap
python src/analyse.py --experiments experiments_clearmap --graph data/HC1.5_clearmap.gml
```

## Regenerate analysis from committed outputs

The experiment outputs are committed. This command refreshes `analysis.json` and figures. Coordinate-based figures require the matching graph file under `data/`.

```powershell
python src/analyse.py
```

## 3-D visualization

The Napari viewer requires a workstation with working OpenGL support.
The command takes a run id from the experiment output folder. Front runs (`exp_A_*`, `exp_B_*`) show animated 1% front growth. Highway runs (`exp_C_*`) show source-to-drain highway edges, with edge width grouped by usage count.

```powershell
python -m pip install "napari[all]"
```

Default output folder:

```powershell
python src/visualize.py exp_A_capillary_seed0 --methods bfs resistance
python src/visualize.py exp_C_highways_capillary_seed0
```

Named output folder:

```powershell
python src/visualize.py exp_A_capillary_seed0 --graph data/HC1.5_gurobi.gml --experiments experiments_gurobi --methods bfs resistance
python src/visualize.py exp_C_highways_capillary_seed0 --graph data/HC1.5_gurobi.gml --experiments experiments_gurobi
```

## Tests

```powershell
python -m unittest discover -s tests
```

The tests cover Jaccard metrics, source/target selection, and highway usage counts on a small graph.

## Layout

```text
configs/        16 YAML experiment configs
data/           graph files and pickle caches
docs/notes.md   methods notes
experiments/    run outputs + analysis.json + _figures/
src/            flow_experiment.py, run_all.py, analyse.py, visualize.py
tests/          unit tests
experiments.csv experiment registry
```
