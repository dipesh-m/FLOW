import csv
import json
import unittest
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
DATASETS = ("HC1.5_clearmap", "HC1.5_gurobi")


def read_registry() -> list[dict[str, str]]:
    with (REPO_ROOT / "experiments.csv").open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def read_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


class RepositoryIntegrityTests(unittest.TestCase):
    def test_registry_and_configs_match(self):
        registry = read_registry()
        by_run = {row["run_id"]: row for row in registry}
        config_paths = sorted((REPO_ROOT / "configs").glob("*.yaml"))

        self.assertEqual(len(registry), 16)
        self.assertEqual(len({row["uid"] for row in registry}), len(registry))
        self.assertEqual(len(by_run), len(registry))
        self.assertEqual({path.stem for path in config_paths}, set(by_run))

        for path in config_paths:
            with self.subTest(run_id=path.stem):
                config = read_yaml(path)
                row = by_run[path.stem]
                self.assertEqual(config["run_id"], path.stem)
                self.assertEqual(config["seed"], int(row["seed"]))
                self.assertEqual(config["source_rule"], row["source_rule"])
                expected_mode = "highways" if path.stem.startswith("exp_C_") else "front"
                self.assertEqual(config["mode"], expected_mode)

    def test_stored_results_cover_registered_runs(self):
        run_ids = {row["run_id"] for row in read_registry()}

        for dataset in DATASETS:
            dataset_dir = REPO_ROOT / "experiments" / dataset
            stored_runs = {
                path.name
                for path in dataset_dir.iterdir()
                if path.is_dir() and not path.name.startswith("_")
            }
            with self.subTest(dataset=dataset):
                self.assertEqual(stored_runs, run_ids)

    def test_stored_result_metadata_matches_configs(self):
        configs = {
            path.stem: read_yaml(path)
            for path in (REPO_ROOT / "configs").glob("*.yaml")
        }

        for dataset in DATASETS:
            graph_counts = set()
            for run_id, config in configs.items():
                run_dir = REPO_ROOT / "experiments" / dataset / run_id
                summary_name = (
                    "highways_summary.json" if config["mode"] == "highways" else "summary.json"
                )
                summary = json.loads((run_dir / summary_name).read_text(encoding="utf-8"))
                with self.subTest(dataset=dataset, run_id=run_id):
                    self.assertEqual(read_yaml(run_dir / "config.yaml"), config)
                    self.assertEqual(summary["run_id"], run_id)
                    self.assertEqual(summary["mode"], config["mode"])
                    self.assertEqual(summary["seed"], config["seed"])
                    self.assertEqual(summary["source_rule"], config["source_rule"])
                    if config["mode"] == "front":
                        expected_rows = config["num_sources"] * len(summary["methods"])
                        self.assertEqual(len(read_csv(run_dir / "metrics.csv")), expected_rows)
                        self.assertEqual(len(read_csv(run_dir / "paths.csv")), expected_rows)
                        self.assertTrue((run_dir / "graph_summary.csv").is_file())
                    else:
                        self.assertEqual(summary["n_sources"], config["num_sources"])
                        for method in summary["methods"]:
                            self.assertTrue((run_dir / f"highways_{method}.csv").is_file())
                graph_counts.add(
                    (summary["nodes"], summary["edges"], summary["largest_component_nodes"])
                )
            with self.subTest(dataset=dataset, field="graph_counts"):
                self.assertEqual(len(graph_counts), 1)

    def test_stored_analysis_covers_all_seed_replicates(self):
        for dataset in DATASETS:
            path = REPO_ROOT / "experiments" / dataset / "analysis.json"
            analysis = json.loads(path.read_text(encoding="utf-8"))
            with self.subTest(dataset=dataset):
                self.assertEqual(analysis["front_1pct"]["capillary_primary"]["n_experiments"], 5)
                self.assertEqual(analysis["front_1pct"]["artery_control"]["n_experiments"], 5)
                self.assertEqual(analysis["highways"]["capillary_primary"]["n_runs"], 3)
                self.assertEqual(analysis["highways"]["artery_control"]["n_runs"], 3)
