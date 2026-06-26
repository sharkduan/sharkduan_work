from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from covalent_design.training.v2_full_beta import (
    V2_FULL_BETA_CONFIG_MISSING,
    V2_FULL_BETA_HEAVY_ENV_UNAVAILABLE,
    V2_FULL_BETA_REAL_DATA_NOT_AUTHORIZED,
    V2_FULL_BETA_REQUIRED_FIELD_MISSING,
    V2_FULL_BETA_TRAINING_FAILED,
    run_v2_full_beta_train,
    v2_full_beta_summary_to_dict,
)

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs" / "v2_full_beta_train.yml"
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "training" / "v2_full_beta"


class V2FullBetaTrainTests(unittest.TestCase):
    def test_fixture_mode_run_produces_manifest_bound_training_summary(self) -> None:
        envelope = run_v2_full_beta_train(CONFIG)

        self.assertTrue(envelope.receipt.passed, envelope.receipt.errors)
        report = v2_full_beta_summary_to_dict(envelope.payload)
        self.assertTrue(report["success"])
        self.assertEqual(report["execution_mode"], "fixture")
        self.assertEqual(report["device"], "cpu")
        self.assertFalse(report["real_data_accessed"])
        self.assertFalse(report["outputs_written"])
        self.assertEqual(report["checkpoint_policy"], "manifest_ref_only")
        self.assertEqual(report["checkpoint_selection_metric"], "total_loss")
        self.assertTrue(report["training"]["success"])
        self.assertTrue(report["manifest"]["validation_passed"])
        self.assertEqual(report["manifest"]["manifest"]["baseline_mode"], "non_pmdm_baseline")
        self.assertEqual(report["manifest"]["manifest"]["checkpoint_refs"][0]["format"], "manifest_ref")
        self.assertTrue(report["selected_checkpoint_ref"]["selected"])
        self.assertIn("total_loss", report["selected_checkpoint_justification"])
        self.assertEqual(report["tuning"]["selected_trial_id"], "trial-000")

    def test_repeated_fixture_runs_are_deterministic(self) -> None:
        first = v2_full_beta_summary_to_dict(run_v2_full_beta_train(CONFIG).payload)
        second = v2_full_beta_summary_to_dict(run_v2_full_beta_train(CONFIG).payload)

        self.assertEqual(first, second)
        self.assertEqual(first["summary_hash"], second["summary_hash"])

    def test_missing_required_config_fields_fail_structured(self) -> None:
        for field in (
            "execution_mode",
            "runtime_budget_seconds",
            "seed",
            "device",
            "model_mode",
            "split_name",
            "records_path",
            "split_index_path",
            "visual_check_index_path",
            "quality_report_path",
            "family_readiness_report_path",
            "license_gate_report_path",
            "checkpoint_policy",
            "checkpoint_selection_metric",
        ):
            with self.subTest(field=field):
                config = _valid_config()
                config.pop(field)
                envelope = run_v2_full_beta_train(config)
                self.assertFalse(envelope.receipt.passed)
                self.assertEqual(envelope.receipt.errors[0].code, V2_FULL_BETA_REQUIRED_FIELD_MISSING)
                self.assertFalse(envelope.payload.selected_checkpoint_ref)

    def test_missing_config_file_fails_structured(self) -> None:
        envelope = run_v2_full_beta_train(ROOT / "configs" / "missing-v2-full-beta.yml")

        self.assertFalse(envelope.receipt.passed)
        self.assertEqual(envelope.receipt.errors[0].code, V2_FULL_BETA_CONFIG_MISSING)

    def test_heavy_manual_real_data_requires_explicit_authorization(self) -> None:
        config = _valid_config()
        config["execution_mode"] = "heavy_manual"
        config["real_data_authorized"] = False

        envelope = run_v2_full_beta_train(config)

        self.assertFalse(envelope.receipt.passed)
        self.assertEqual(envelope.receipt.errors[0].code, V2_FULL_BETA_REAL_DATA_NOT_AUTHORIZED)
        report = v2_full_beta_summary_to_dict(envelope.payload)
        self.assertFalse(report["real_data_accessed"])
        self.assertIsNone(report["selected_checkpoint_ref"])

    def test_cuda_heavy_unavailable_returns_structured_failure_without_checkpoint(self) -> None:
        config = _valid_config()
        config["device"] = "cuda"
        config["require_heavy_environment"] = True

        envelope = run_v2_full_beta_train(config)

        self.assertFalse(envelope.receipt.passed)
        self.assertEqual(envelope.receipt.errors[0].code, V2_FULL_BETA_HEAVY_ENV_UNAVAILABLE)
        report = v2_full_beta_summary_to_dict(envelope.payload)
        self.assertFalse(report["training"]["success"])
        self.assertIsNone(report["selected_checkpoint_ref"])
        self.assertNotIn("Traceback", report["error_message"] or "")

    def test_training_failure_does_not_select_checkpoint(self) -> None:
        config = _valid_config()
        config["model_mode"] = "pmdm"

        envelope = run_v2_full_beta_train(config)

        self.assertFalse(envelope.receipt.passed)
        self.assertEqual(envelope.receipt.errors[0].code, V2_FULL_BETA_TRAINING_FAILED)
        report = v2_full_beta_summary_to_dict(envelope.payload)
        self.assertFalse(report["training"]["success"])
        self.assertIsNone(report["selected_checkpoint_ref"])
        self.assertEqual(report["manifest"]["status"], "not_built")

    def test_cli_valid_config_outputs_deterministic_json(self) -> None:
        first = _run_cli(str(CONFIG))
        second = _run_cli(str(CONFIG))

        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(first.stdout, second.stdout)
        data = json.loads(first.stdout)
        self.assertTrue(data["success"])
        self.assertEqual(data["execution_mode"], "fixture")

    def test_cli_invalid_config_exits_nonzero_with_json_error(self) -> None:
        result = _run_cli(str(ROOT / "configs" / "missing-v2-full-beta.yml"))

        self.assertNotEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertFalse(data["success"])
        self.assertEqual(data["error_code"], V2_FULL_BETA_CONFIG_MISSING)

    def test_public_training_facade_exports_full_beta_api_lazily(self) -> None:
        import covalent_design.training as training

        self.assertIn("run_v2_full_beta_train", training.__all__)
        self.assertNotIn("run_v2_full_beta_train", training.__dict__)
        self.assertTrue(callable(training.run_v2_full_beta_train))
        self.assertIn("run_v2_full_beta_train", training.__dict__)

    def test_full_beta_module_import_has_no_heavy_side_effects(self) -> None:
        code = (
            "import sys;"
            "import covalent_design.training.v2_full_beta;"
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

    def test_task52_5_files_stay_before_later_stage_and_payload_boundaries(self) -> None:
        paths = [
            ROOT / "src" / "covalent_design" / "training" / "v2_full_beta.py",
            ROOT / "src" / "covalent_design" / "training" / "cli" / "v2_full_beta_train.py",
            ROOT / "tests" / "training" / "test_v2_full_beta_train.py",
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
            text = path.read_text("utf-8")
            for token in forbidden:
                self.assertNotIn(token, text, f"{path}: {token}")

    def test_no_outputs_are_written_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            config = _valid_config()
            config["output_root"] = str(Path(temp) / "run")
            envelope = run_v2_full_beta_train(config)

            self.assertTrue(envelope.receipt.passed, envelope.receipt.errors)
            self.assertFalse(Path(config["output_root"]).exists())


def _valid_config() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "contract_version": "1.0",
        "profile": "v2_full_beta_fixture",
        "execution_mode": "fixture",
        "real_data_authorized": False,
        "require_heavy_environment": False,
        "output_root": "local-only-v2-full-beta-output",
        "checkpoint_policy": "manifest_ref_only",
        "checkpoint_selection_metric": "total_loss",
        "runtime_budget_seconds": 600,
        "seed": 4242,
        "device": "cpu",
        "model_mode": "non_pmdm_baseline",
        "split_name": "train",
        "records_path": str(FIXTURE_DIR / "records.jsonl"),
        "split_index_path": str(FIXTURE_DIR / "split_index.json"),
        "visual_check_index_path": str(FIXTURE_DIR / "visual_check_index.json"),
        "quality_report_path": str(FIXTURE_DIR / "quality_report.json"),
        "family_readiness_report_path": str(FIXTURE_DIR / "family_readiness_report.json"),
        "license_gate_report_path": str(FIXTURE_DIR / "license_gate_report.json"),
        "steps": 1,
        "batch_size": 1,
        "tuning_config_path": str(ROOT / "configs" / "v2_tiny_sweep.yml"),
    }


def _run_cli(config: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run(
        [sys.executable, "-m", "covalent_design.training.cli.v2_full_beta_train", "--config", config],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


if __name__ == "__main__":
    unittest.main()
