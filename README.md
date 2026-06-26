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
| H1 length↔BFS | 0.86 (0.04) | 0.79 (0.07) |
| H1 resistance↔BFS | 0.31 (0.15) | 0.26 (0.16) |
| H2 resistance↔radius | 0.74 (0.08) | 0.76 (0.07) |
| H3 weighted Jaccard | 0.025 (0.003) | 0.030 (0.003) |
| H3 set Jaccard | 0.049 (0.003) | 0.090 (0.003) |

Full values in `experiments/analysis.json`. Figures in `experiments/_figures/`.

## Getting started

```powershell
git clone https://github.com/dipesh-m/FLOW.git
cd FLOW
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

On macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Python 3.11+.

## Full re-run

Place the HC1.5 GML under `data/V2/HC1.5.gml` (~2.5 GB). A pickle cache speeds up graph loads.

```powershell
python src/run_all.py
python src/analyse.py
```

Expected output: experiment folders under `experiments/`, `experiments/analysis.json`, and figures under `experiments/_figures/`.

Run one config:

```powershell
python src/run_all.py --only exp_A_capillary_seed42
```

## Regenerate analysis from committed outputs

The experiment outputs are committed. This command refreshes `analysis.json` and figures. Coordinate-based figures require `data/V2/HC1.5.gml`.

```powershell
python src/analyse.py
```

## Layout

```text
configs/        16 YAML experiment configs
data/V2/        graph file (not committed)
docs/notes.md   methods notes
experiments/    run outputs + analysis.json + _figures/
src/            flow_experiment.py, run_all.py, analyse.py
experiments.csv experiment registry
```
