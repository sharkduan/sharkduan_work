"""Task 50 V2 training smoke loop tests.

These tests keep Task 50 narrow: consume Task 49's V2 eligibility envelope,
validate referenced artifacts before tensor construction, select an explicit
PMDM or non-PMDM smoke path, and emit deterministic JSON summaries.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "training" / "v2_train_loop"
CPU_CONFIG = ROOT / "configs" / "v2_train_cpu_smoke.yml"


class V2TrainLoopTests(unittest.TestCase):
    def test_cpu_smoke_cli_outputs_deterministic_baseline_summary(self) -> None:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT / "src")
        first = subprocess.run(
            [
                sys.executable,
                "-m",
                "covalent_design.training.cli.v2_train",
                "--config",
                str(CPU_CONFIG),
            ],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        second = subprocess.run(
            [
                sys.executable,
                "-m",
                "covalent_design.training.cli.v2_train",
                "--config",
                str(CPU_CONFIG),
            ],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(first.stdout, second.stdout)
        summary = json.loads(first.stdout)
        self.assertTrue(summary["success"])
        self.assertEqual(summary["device"], "cpu")
        self.assertFalse(summary["cuda_requested"])
        self.assertEqual(summary["model_path"]["baseline_mode"], "non_pmdm_baseline")
        self.assertFalse(summary["model_path"]["is_pmdm"])
        self.assertEqual(
            summary["model_path"]["warning_code"],
            "BASELINE_NOT_PMDM_WARNING",
        )
        self.assertEqual(summary["dataset"]["eligible_count"], 1)
        self.assertEqual(summary["artifact_preflight"]["status"], "passed")
        self.assertFalse(summary["phases"]["tensor_construction_started"])
        self.assertIn("loss_report", summary)
        self.assertIn("denominators", summary["loss_report"])
        self.assertEqual(summary["denominator_status"], "passed")
        self.assertEqual(summary["publication_claims"], [])

    def test_run_v2_train_uses_task49_inputs_not_v1_dataset_bypass(self) -> None:
        from covalent_design.training import run_v2_train, v2_training_summary_to_dict

        envelope = run_v2_train(str(CPU_CONFIG))

        self.assertTrue(envelope.receipt.passed)
        summary = v2_training_summary_to_dict(envelope.payload)
        self.assertEqual(summary["dataset"]["source"], "V2TrainingDatasetIndex")
        self.assertEqual(summary["dataset"]["records_path"], str((FIXTURE_DIR / "records.jsonl").resolve()))
        source_text = (ROOT / "src" / "covalent_design" / "training" / "v2_train_loop.py").read_text("utf-8")
        self.assertNotIn("prepare_" + "dataset(", source_text)

    def test_direct_records_without_v2_gate_reports_fails_structured(self) -> None:
        from covalent_design.training.v2_train_loop import run_v2_train

        envelope = run_v2_train(
            {
                "device": "cpu",
                "model_mode": "non_pmdm_baseline",
                "split_name": "train",
                "records_path": str(FIXTURE_DIR / "records.jsonl"),
                "split_index_path": str(FIXTURE_DIR / "split_index.json"),
            }
        )

        self.assertFalse(envelope.receipt.passed)
        self.assertEqual(envelope.receipt.errors[0].code, "V2_TRAIN_TASK49_INPUTS_MISSING")
        self.assertFalse(envelope.payload.phases["tensor_construction_started"])

    def test_artifact_missing_fails_before_tensor_construction(self) -> None:
        from covalent_design.training.v2_train_loop import run_v2_train

        with _mutable_fixture() as temp_dir:
            records_path = temp_dir / "records.jsonl"
            row = _read_record(records_path)
            row["artifacts"][0]["uri"] = "artifacts/REC-V2-SMOKE/missing.pdb"
            _write_record(records_path, row)

            envelope = run_v2_train(_config_for(temp_dir))

        self.assertFalse(envelope.receipt.passed)
        self.assertEqual(envelope.receipt.errors[0].code, "V2_TRAIN_ARTIFACT_MISSING")
        self.assertFalse(envelope.payload.phases["tensor_construction_started"])

    def test_artifact_unreadable_fails_before_tensor_construction(self) -> None:
        from covalent_design.training.v2_train_loop import run_v2_train

        with _mutable_fixture() as temp_dir:
            records_path = temp_dir / "records.jsonl"
            row = _read_record(records_path)
            row["artifacts"][0]["uri"] = "artifacts/REC-V2-SMOKE"
            _write_record(records_path, row)

            envelope = run_v2_train(_config_for(temp_dir))

        self.assertFalse(envelope.receipt.passed)
        self.assertEqual(envelope.receipt.errors[0].code, "V2_TRAIN_ARTIFACT_UNREADABLE")
        self.assertFalse(envelope.payload.phases["tensor_construction_started"])

    def test_artifact_byte_mismatch_fails_before_tensor_construction(self) -> None:
        from covalent_design.training.v2_train_loop import run_v2_train

        with _mutable_fixture() as temp_dir:
            records_path = temp_dir / "records.jsonl"
            row = _read_record(records_path)
            row["artifacts"][0]["bytes"] = 999
            _write_record(records_path, row)

            envelope = run_v2_train(_config_for(temp_dir))

        self.assertFalse(envelope.receipt.passed)
        self.assertEqual(envelope.receipt.errors[0].code, "V2_TRAIN_ARTIFACT_BYTE_MISMATCH")
        self.assertFalse(envelope.payload.phases["tensor_construction_started"])

    def test_artifact_checksum_mismatch_fails_before_tensor_construction(self) -> None:
        from covalent_design.training.v2_train_loop import run_v2_train

        with _mutable_fixture() as temp_dir:
            records_path = temp_dir / "records.jsonl"
            row = _read_record(records_path)
            row["artifacts"][0]["sha256"] = "0" * 64
            _write_record(records_path, row)

            envelope = run_v2_train(_config_for(temp_dir))

        self.assertFalse(envelope.receipt.passed)
        self.assertEqual(envelope.receipt.errors[0].code, "V2_TRAIN_ARTIFACT_CHECKSUM_MISMATCH")
        self.assertFalse(envelope.payload.phases["tensor_construction_started"])

    def test_gpu_cuda_unavailable_fails_without_traceback(self) -> None:
        from covalent_design.model.torch_backend import TorchBackendStatus
        import covalent_design.training.v2_train_loop as v2_train_loop

        unavailable = TorchBackendStatus(
            status="unavailable",
            torch_version=None,
            cuda_available=False,
            cuda_version=None,
            error_code="TORCH_BACKEND_UNAVAILABLE",
            error_message="torch unavailable in test",
        )
        with mock.patch.object(v2_train_loop, "check_torch_available", return_value=unavailable):
            envelope = v2_train_loop.run_v2_train({**_config_for(FIXTURE_DIR), "device": "cuda"})

        self.assertFalse(envelope.receipt.passed)
        self.assertEqual(envelope.receipt.errors[0].code, "V2_TRAIN_CUDA_UNAVAILABLE")
        self.assertNotIn("Traceback", envelope.payload.error_message or "")
        self.assertFalse(envelope.payload.phases["tensor_construction_started"])

    def test_pmdm_unavailable_does_not_auto_switch_to_baseline(self) -> None:
        from covalent_design.training.v2_train_loop import run_v2_train, v2_training_summary_to_dict

        envelope = run_v2_train({**_config_for(FIXTURE_DIR), "model_mode": "pmdm"})

        self.assertFalse(envelope.receipt.passed)
        self.assertEqual(envelope.receipt.errors[0].code, "PMDM_REAL_LICENSE_BLOCKED")
        summary = v2_training_summary_to_dict(envelope.payload)
        self.assertEqual(summary["model_path"]["selected_mode"], "pmdm")
        self.assertIsNone(summary["model_path"]["baseline_mode"])
        self.assertTrue(summary["model_path"]["is_pmdm"])

    def test_denominator_drift_fails_structured(self) -> None:
        from covalent_design.training.v2_train_loop import run_v2_train

        config = _config_for(FIXTURE_DIR)
        config["expected_denominators"] = {"candidate_count": 999}
        envelope = run_v2_train(config)

        self.assertFalse(envelope.receipt.passed)
        self.assertEqual(envelope.receipt.errors[0].code, "V2_TRAIN_DENOMINATOR_DRIFT")
        self.assertEqual(envelope.payload.denominator_status, "failed")

    def test_public_training_facade_stays_lazy_for_task50_exports(self) -> None:
        import covalent_design.training as training

        self.assertIn("run_v2_train", training.__all__)
        self.assertNotIn("run_v2_train", training.__dict__)
        func = training.run_v2_train
        self.assertTrue(callable(func))
        self.assertIn("run_v2_train", training.__dict__)

    def test_task50_files_do_not_reference_real_data_or_task51_outputs(self) -> None:
        paths = [
            ROOT / "src" / "covalent_design" / "training" / "v2_train_loop.py",
            ROOT / "src" / "covalent_design" / "training" / "cli" / "v2_train.py",
            ROOT / "tests" / "training" / "test_v2_train_loop.py",
            ROOT / "configs" / "v2_train_cpu_smoke.yml",
            ROOT / "configs" / "v2_train_gpu_smoke.yml",
        ]
        forbidden = ("D:" + "\\\\codex_work\\\\data", "data" + "/v2", "checkpoint_" + "manifest_path", "checkpoint_" + "output", "model_" + "weights")
        for path in paths:
            text = path.read_text("utf-8")
            for token in forbidden:
                self.assertNotIn(token, text, path)


def _read_record(path: Path) -> dict[str, object]:
    return json.loads(path.read_text("utf-8").strip())


def _write_record(path: Path, row: dict[str, object]) -> None:
    path.write_text(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")


def _config_for(base: Path) -> dict[str, object]:
    return {
        "device": "cpu",
        "model_mode": "non_pmdm_baseline",
        "split_name": "train",
        "records_path": str(base / "records.jsonl"),
        "split_index_path": str(base / "split_index.json"),
        "visual_check_index_path": str(base / "visual_check_index.json"),
        "quality_report_path": str(base / "quality_report.json"),
        "family_readiness_report_path": str(base / "family_readiness_report.json"),
        "license_gate_report_path": str(base / "license_gate_report.json"),
        "steps": 1,
        "batch_size": 1,
    }


class _mutable_fixture:
    def __enter__(self) -> Path:
        self._temp = tempfile.TemporaryDirectory()
        self.path = Path(self._temp.name) / "fixture"
        shutil.copytree(FIXTURE_DIR, self.path)
        return self.path

    def __exit__(self, exc_type, exc, tb) -> None:
        self._temp.cleanup()


if __name__ == "__main__":
    unittest.main()
