"""Load one graph, then run YAML configs in configs/.

Usage from FLOW/:
    python src/run_all.py
    python src/run_all.py --graph data/HC1.5_clearmap.gml
    python src/run_all.py --only exp_A_capillary_seed42
"""

from __future__ import annotations

import argparse
from pathlib import Path
from time import perf_counter

from flow_experiment import (
    graph_arrays, largest_component_nodes, load_config, load_graph, log,
    run_front, run_highways,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GRAPH_PATH = REPO_ROOT / "data" / "HC1.5_gurobi.gml"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "experiments"
DEFAULT_CONFIG_DIR = REPO_ROOT / "configs"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="Substring filter on config file name.")
    ap.add_argument("--graph", type=Path, default=DEFAULT_GRAPH_PATH, help="Path to the GML graph.")
    ap.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_ROOT, help="Experiment output folder.")
    ap.add_argument("--config-dir", type=Path, default=DEFAULT_CONFIG_DIR, help="Config folder.")
    args = ap.parse_args()

    graph_path = args.graph if args.graph.is_absolute() else REPO_ROOT / args.graph
    output_root = args.output if args.output.is_absolute() else REPO_ROOT / args.output
    config_dir = args.config_dir if args.config_dir.is_absolute() else REPO_ROOT / args.config_dir

    configs = sorted(config_dir.glob("*.yaml"))
    if args.only:
        configs = [c for c in configs if args.only in c.name]
    if not configs:
        raise SystemExit("No configs matched.")

    t0 = perf_counter()
    log(f"Loading graph: {graph_path}", t0)
    graph = load_graph(graph_path)
    log(f"Loaded {graph.vcount():,} nodes, {graph.ecount():,} edges", t0)

    log("Building derived arrays", t0)
    arrays = graph_arrays(graph)
    lcc_nodes = largest_component_nodes(graph)
    log(f"LCC: {len(lcc_nodes):,} nodes", t0)

    for cfg_path in configs:
        config = load_config(cfg_path)
        log(f">>> {config['run_id']} ({config['mode']})", t0)
        if config["mode"] == "front":
            out = run_front(graph, arrays, lcc_nodes, config, cfg_path, output_root, t0)
        else:
            out = run_highways(graph, arrays, lcc_nodes, config, cfg_path, output_root, t0)
        log(f"<<< {out}", t0)

    log("All runs done.", t0)


if __name__ == "__main__":
    main()
