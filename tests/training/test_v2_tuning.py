from __future__ import annotations

import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

from covalent_design.training.v2_tuning import (
    V2_TUNE_CONFIG_MISSING,
    V2_TUNE_MODEL_MODE_UNSUPPORTED,
    V2_TUNE_NO_SUCCESSFUL_TRIALS,
    V2_TUNE_RUNTIME_BUDGET_MISSING,
    V2_TUNE_SELECTION_METRIC_MISSING,
    V2_TUNE_SELECTION_METRIC_UNSUPPORTED,
    V2_TUNE_SELECTION_MODE_UNSUPPORTED,
    V2_TUNE_SEEDS_COUNT_MISMATCH,
    V2_TUNE_SEEDS_DUPLICATE,
    V2_TUNE_SEEDS_MISSING,
    V2_TUNE_TASK49_INPUTS_MISSING,
    V2_TUNE_TRIAL_COUNT_INVALID,
    V2_TUNE_TRIAL_COUNT_MISSING,
    V2_TUNE_TRIAL_MODE_COUNT_MISMATCH,
    run_v2_tune,
    v2_tuning_summary_to_dict,
)

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs" / "v2_tiny_sweep.yml"
HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class V2TuningTests(unittest.TestCase):
    def test_valid_tiny_sweep_records_explicit_budget_seeds_and_hashes(self) -> None:
        envelope = run_v2_tune(CONFIG)

        self.assertTrue(envelope.receipt.passed, envelope.receipt.errors)
        report = v2_tuning_summary_to_dict(envelope.payload)
        self.assertTrue(report["success"])
        self.assertEqual(report["trial_count"], 3)
        self.assertEqual(report["runtime_budget_seconds"], 300)
        self.assertEqual(report["seeds"], [101, 202, 303])
        self.assertEqual(report["selection_metric"], "total_loss")
        self.assertEqual(report["selection_mode"], "minimize")
        self.assertRegex(report["sweep_config_hash"], HASH_RE)
        self.assertRegex(report["sweep_result_hash"], HASH_RE)
        self.assertEqual(len(report["trials"]), 3)
        for trial in report["trials"]:
            self.assertRegex(trial["config_hash"], HASH_RE)
            self.assertRegex(trial["result_hash"], HASH_RE)
            self.assertEqual(trial["status"], "completed")
            self.assertEqual(trial["selection_metric_name"], "total_loss")

    def test_repeated_runs_are_deterministic(self) -> None:
        first = v2_tuning_summary_to_dict(run_v2_tune(CONFIG).payload)
        second = v2_tuning_summary_to_dict(run_v2_tune(CONFIG).payload)

        self.assertEqual(first, second)
        self.assertEqual(first["sweep_result_hash"], second["sweep_result_hash"])
        self.assertEqual(
            [trial["result_hash"] for trial in first["trials"]],
            [trial["result_hash"] for trial in second["trials"]],
        )

    def test_trial_order_follows_explicit_seed_order(self) -> None:
        report = v2_tuning_summary_to_dict(run_v2_tune(CONFIG).payload)

        self.assertEqual(
            [(trial["trial_id"], trial["seed"]) for trial in report["trials"]],
            [("trial-000", 101), ("trial-001", 202), ("trial-002", 303)],
        )

    def test_selection_uses_frozen_metric_and_justification(self) -> None:
        report = v2_tuning_summary_to_dict(run_v2_tune(CONFIG).payload)

        self.assertEqual(report["selected_trial_id"], "trial-000")
        self.assertEqual(report["selected_checkpoint_ref"]["trial_id"], "trial-000")
        self.assertEqual(report["selected_checkpoint_ref"]["format"], "manifest_ref")
        self.assertIn("total_loss", report["selection_justification"])
        self.assertTrue(report["trials"][0]["selected"])
        self.assertFalse(report["trials"][1]["selected"])

    def test_failed_trials_are_reported_and_not_selected(self) -> None:
        config = _valid_config_dict()
        config["trial_model_modes"] = "pmdm,non_pmdm_baseline,non_pmdm_baseline"
        envelope = run_v2_tune(config)

        self.assertTrue(envelope.receipt.passed, envelope.receipt.errors)
        report = v2_tuning_summary_to_dict(envelope.payload)
        self.assertEqual(report["trial_count"], 3)
        self.assertEqual(report["successful_count"], 2)
        self.assertEqual(report["failed_count"], 1)
        self.assertEqual(len(report["failed_trials"]), 1)
        self.assertEqual(report["failed_trials"][0]["trial_id"], "trial-000")
        self.assertFalse(report["failed_trials"][0]["success"])
        self.assertNotEqual(report["selected_trial_id"], "trial-000")
        self.assertEqual(len(report["trials"]), 3)

    def test_all_failed_trials_return_structured_no_selection_error(self) -> None:
        config = _valid_config_dict()
        config["model_mode"] = "pmdm"
        envelope = run_v2_tune(config)

        self.assertFalse(envelope.receipt.passed)
        self.assertEqual(envelope.receipt.errors[0].code, V2_TUNE_NO_SUCCESSFUL_TRIALS)
        report = v2_tuning_summary_to_dict(envelope.payload)
        self.assertFalse(report["success"])
        self.assertIsNone(report["selected_trial_id"])
        self.assertIsNone(report["selected_checkpoint_ref"])
        self.assertEqual(report["successful_count"], 0)
        self.assertEqual(report["failed_count"], 3)

    def test_missing_required_config_fields_fail_structured(self) -> None:
        cases = [
            ("trial_count", V2_TUNE_TRIAL_COUNT_MISSING),
            ("runtime_budget_seconds", V2_TUNE_RUNTIME_BUDGET_MISSING),
            ("seeds", V2_TUNE_SEEDS_MISSING),
            ("selection_metric", V2_TUNE_SELECTION_METRIC_MISSING),
            ("records_path", V2_TUNE_TASK49_INPUTS_MISSING),
        ]
        for field, code in cases:
            with self.subTest(field=field):
                config = _valid_config_dict()
                config.pop(field)
                envelope = run_v2_tune(config)
                self.assertFalse(envelope.receipt.passed)
                self.assertEqual(envelope.receipt.errors[0].code, code)

    def test_invalid_config_values_fail_structured(self) -> None:
        cases = [
            ({"trial_count": 0}, V2_TUNE_TRIAL_COUNT_INVALID),
            ({"seeds": "101,202"}, V2_TUNE_SEEDS_COUNT_MISMATCH),
            ({"seeds": "101,101,202"}, V2_TUNE_SEEDS_DUPLICATE),
            ({"selection_metric": "accuracy"}, V2_TUNE_SELECTION_METRIC_UNSUPPORTED),
            ({"selection_mode": "average"}, V2_TUNE_SELECTION_MODE_UNSUPPORTED),
            ({"model_mode": "unknown"}, V2_TUNE_MODEL_MODE_UNSUPPORTED),
            ({"trial_model_modes": "non_pmdm_baseline,pmdm"}, V2_TUNE_TRIAL_MODE_COUNT_MISMATCH),
        ]
        for override, code in cases:
            with self.subTest(override=override):
                config = _valid_config_dict()
                config.update(override)
                envelope = run_v2_tune(config)
                self.assertFalse(envelope.receipt.passed)
                self.assertEqual(envelope.receipt.errors[0].code, code)

    def test_missing_config_file_fails_structured(self) -> None:
        envelope = run_v2_tune(ROOT / "configs" / "does-not-exist.yml")

        self.assertFalse(envelope.receipt.passed)
        self.assertEqual(envelope.receipt.errors[0].code, V2_TUNE_CONFIG_MISSING)

    def test_cli_valid_config_outputs_deterministic_json(self) -> None:
        first = _run_cli(str(CONFIG))
        second = _run_cli(str(CONFIG))

        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(first.stdout, second.stdout)
        data = json.loads(first.stdout)
        self.assertTrue(data["success"])
        self.assertEqual(data["trial_count"], 3)
        self.assertEqual(data["selected_trial_id"], "trial-000")

    def test_cli_invalid_config_exits_nonzero_with_json_error(self) -> None:
        result = _run_cli(str(ROOT / "configs" / "does-not-exist.yml"))

        self.assertNotEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertFalse(data["success"])
        self.assertEqual(data["error_code"], V2_TUNE_CONFIG_MISSING)

    def test_lazy_facade_exports_tuning_api(self) -> None:
        import covalent_design.training as training

        self.assertIn("run_v2_tune", training.__all__)
        self.assertNotIn("run_v2_tune", training.__dict__)
        self.assertTrue(callable(training.run_v2_tune))
        self.assertIn("run_v2_tune", training.__dict__)

    def test_tuning_module_import_has_no_heavy_side_effects(self) -> None:
        code = (
            "import sys;"
            "import covalent_design.training.v2_tuning;"
            "assert all(name not in sys.modules for name in "
            "('torch','rdkit','PMDM','PocketFlow'))"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd=ROOT,
            env={"PYTHONPATH": str(ROOT / "src")},
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_source_and_config_stay_in_task52_boundary(self) -> None:
        paths = [
            ROOT / "src" / "covalent_design" / "training" / "v2_tuning.py",
            ROOT / "src" / "covalent_design" / "training" / "cli" / "v2_tune.py",
            ROOT / "tests" / "training" / "test_v2_tuning.py",
            CONFIG,
        ]
        forbidden = (
            "D:\\codex_work\\" + "data",
            "data/" + "v2",
            "." + "pt",
            "." + "pth",
            "." + "ckpt",
            "." + "bin",
            "model " + "weight",
            "weight" + "s",
            "Task " + "53",
            "v2_" + "sam" + "pling",
            "sam" + "pling",
            "infer" + "ence",
            "eval" + "uation",
        )
        for path in paths:
            if not path.exists():
                continue
            text = path.read_text("utf-8")
            for token in forbidden:
                self.assertNotIn(token, text, f"{path}: {token}")


def _valid_config_dict() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "contract_version": "1.0",
        "profile": "tiny_sweep",
        "trial_count": 3,
        "runtime_budget_seconds": 300,
        "seeds": "101,202,303",
        "selection_metric": "total_loss",
        "selection_mode": "minimize",
        "device": "cpu",
        "model_mode": "non_pmdm_baseline",
        "split_name": "train",
        "records_path": "tests/fixtures/training/v2_train_loop/records.jsonl",
        "split_index_path": "tests/fixtures/training/v2_train_loop/split_index.json",
        "visual_check_index_path": "tests/fixtures/training/v2_train_loop/visual_check_index.json",
        "quality_report_path": "tests/fixtures/training/v2_train_loop/quality_report.json",
        "family_readiness_report_path": "tests/fixtures/training/v2_train_loop/family_readiness_report.json",
        "license_gate_report_path": "tests/fixtures/training/v2_train_loop/license_gate_report.json",
        "steps": 1,
        "batch_size": 1,
    }


def _run_cli(config: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "covalent_design.training.cli.v2_tune", "--config", config],
        cwd=ROOT,
        env={"PYTHONPATH": str(ROOT / "src")},
        text=True,
        capture_output=True,
        check=False,
    )


if __name__ == "__main__":
    unittest.main()
