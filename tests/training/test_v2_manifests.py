from __future__ import annotations

import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

from covalent_design.training.v2_manifests import (
    BASELINE_MODE_NON_PMDM,
    BASELINE_MODE_PMDM,
    DEPENDENCY_LOCK_AVAILABLE,
    DEPENDENCY_LOCK_NOT_AVAILABLE,
    V2_MANIFEST_BASELINE_PMDM_MISMATCH,
    V2_MANIFEST_BASELINE_MODE_MISSING,
    V2_MANIFEST_BASELINE_MODE_UNSUPPORTED,
    V2_MANIFEST_CHECKPOINT_REFS_MISSING,
    V2_MANIFEST_DATA_HASH_MISSING,
    V2_MANIFEST_DATASET_INDEX_HASH_MISSING,
    V2_MANIFEST_DEPENDENCY_LOCK_HASH_MISSING,
    V2_MANIFEST_DEPENDENCY_LOCK_PROVENANCE_MISSING,
    V2_MANIFEST_DEPENDENCY_LOCK_REASON_MISSING,
    V2_MANIFEST_DEPENDENCY_LOCK_STATUS_INVALID,
    V2_MANIFEST_ENVIRONMENT_HASH_MISSING,
    V2_MANIFEST_FAMILY_READINESS_HASH_MISSING,
    V2_MANIFEST_PMDM_UNAVAILABLE_SUCCESS,
    V2_MANIFEST_TRAINING_CONFIG_HASH_MISSING,
    V2_MANIFEST_TRAINING_SUMMARY_HASH_MISSING,
    V2_MANIFEST_TRAINING_SUMMARY_REF_MISSING,
    V2CheckpointRef,
    V2DependencyLockProvenance,
    build_v2_checkpoint_experiment_manifest,
    hash_v2_checkpoint_experiment_manifest,
    serialize_v2_checkpoint_experiment_manifest,
    v2_checkpoint_experiment_manifest_to_dict,
    v2_hash_file,
    v2_hash_object,
)

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "training" / "v2_manifests"
HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class V2ManifestTests(unittest.TestCase):
    def test_valid_baseline_manifest_records_required_provenance(self) -> None:
        envelope = _build_manifest()

        self.assertTrue(envelope.receipt.passed, envelope.receipt.errors)
        data = v2_checkpoint_experiment_manifest_to_dict(envelope.payload)
        self.assertEqual(data["role"], "v2_checkpoint_experiment_manifest")
        self.assertEqual(data["baseline_mode"], BASELINE_MODE_NON_PMDM)
        self.assertFalse(data["is_pmdm"])
        self.assertEqual(data["dependency_lock"]["status"], DEPENDENCY_LOCK_NOT_AVAILABLE)
        self.assertIsNone(data["dependency_lock"]["lock_hash"])
        for key in (
            "environment_hash",
            "dataset_index_hash",
            "family_readiness_hash",
            "training_config_hash",
            "training_summary_hash",
        ):
            self.assertRegex(data[key], HASH_RE)
        self.assertEqual(sorted(data["data_hashes"]), [
            "license_gate_report",
            "quality_report",
            "records_jsonl",
            "split_index",
            "visual_check_index",
        ])
        self.assertEqual(data["checkpoint_refs"][0]["checkpoint_uri"], "checkpoint-ref://run-1/step-0")

    def test_output_is_deterministic(self) -> None:
        first = _build_manifest().payload
        second = _build_manifest().payload

        self.assertEqual(
            serialize_v2_checkpoint_experiment_manifest(first),
            serialize_v2_checkpoint_experiment_manifest(second),
        )
        self.assertEqual(
            hash_v2_checkpoint_experiment_manifest(first),
            hash_v2_checkpoint_experiment_manifest(second),
        )

    def test_dependency_lock_available_requires_real_hash_shape(self) -> None:
        envelope = _build_manifest(
            dependency_lock=V2DependencyLockProvenance(
                status=DEPENDENCY_LOCK_AVAILABLE,
                lock_hash="not-a-real-hash",
                uri="env-lock.yml",
                format="yaml",
            )
        )

        self.assertFalse(envelope.receipt.passed)
        self.assertEqual(envelope.receipt.errors[0].code, "V2_MANIFEST_HASH_FORMAT_INVALID")

    def test_dependency_lock_not_available_is_explicit_not_forged(self) -> None:
        envelope = _build_manifest(
            dependency_lock=V2DependencyLockProvenance(
                status=DEPENDENCY_LOCK_NOT_AVAILABLE,
                lock_hash=None,
                reason="lock workflow documented but no verified lock file exists",
            )
        )

        self.assertTrue(envelope.receipt.passed, envelope.receipt.errors)
        data = v2_checkpoint_experiment_manifest_to_dict(envelope.payload)
        self.assertEqual(data["dependency_lock"]["status"], DEPENDENCY_LOCK_NOT_AVAILABLE)
        self.assertIsNone(data["dependency_lock"]["lock_hash"])
        self.assertIn("documented", data["dependency_lock"]["reason"])

    def test_missing_provenance_failures_are_structured(self) -> None:
        cases = [
            ("environment_hash", "", V2_MANIFEST_ENVIRONMENT_HASH_MISSING),
            ("dataset_index_hash", "", V2_MANIFEST_DATASET_INDEX_HASH_MISSING),
            ("family_readiness_hash", "", V2_MANIFEST_FAMILY_READINESS_HASH_MISSING),
            ("training_config_hash", "", V2_MANIFEST_TRAINING_CONFIG_HASH_MISSING),
            ("training_summary_hash", "", V2_MANIFEST_TRAINING_SUMMARY_HASH_MISSING),
            ("training_summary_ref", "", V2_MANIFEST_TRAINING_SUMMARY_REF_MISSING),
            ("checkpoint_refs", (), V2_MANIFEST_CHECKPOINT_REFS_MISSING),
        ]
        for field, value, code in cases:
            with self.subTest(field=field):
                envelope = _build_manifest(**{field: value})
                self.assertFalse(envelope.receipt.passed)
                self.assertEqual(envelope.receipt.errors[0].code, code)
                self.assertEqual(envelope.receipt.errors[0].owner, "training")

    def test_missing_dependency_lock_provenance_fails(self) -> None:
        envelope = _build_manifest(dependency_lock=None)

        self.assertFalse(envelope.receipt.passed)
        self.assertEqual(
            envelope.receipt.errors[0].code,
            V2_MANIFEST_DEPENDENCY_LOCK_PROVENANCE_MISSING,
        )

    def test_pmdm_manifest_requires_available_lock_hash(self) -> None:
        envelope = _build_manifest(
            baseline_mode=BASELINE_MODE_PMDM,
            is_pmdm=True,
            pmdm_status="available",
            dependency_lock=V2DependencyLockProvenance(
                status=DEPENDENCY_LOCK_NOT_AVAILABLE,
                reason="no verified lock file",
            ),
        )

        self.assertFalse(envelope.receipt.passed)
        codes = [error.code for error in envelope.receipt.errors]
        self.assertIn(V2_MANIFEST_DEPENDENCY_LOCK_HASH_MISSING, codes)

    def test_baseline_mode_and_is_pmdm_must_agree(self) -> None:
        envelope = _build_manifest(
            baseline_mode=BASELINE_MODE_NON_PMDM,
            is_pmdm=True,
        )

        self.assertFalse(envelope.receipt.passed)
        self.assertEqual(envelope.receipt.errors[0].code, V2_MANIFEST_BASELINE_PMDM_MISMATCH)

    def test_pmdm_unavailable_cannot_be_recorded_as_successful_pmdm(self) -> None:
        envelope = _build_manifest(
            baseline_mode=BASELINE_MODE_PMDM,
            is_pmdm=True,
            pmdm_status="unavailable",
            dependency_lock=V2DependencyLockProvenance(
                status=DEPENDENCY_LOCK_AVAILABLE,
                lock_hash=_hash("dependency-lock"),
                uri="env-lock.yml",
                format="yaml",
            ),
        )

        self.assertFalse(envelope.receipt.passed)
        codes = [error.code for error in envelope.receipt.errors]
        self.assertIn(V2_MANIFEST_PMDM_UNAVAILABLE_SUCCESS, codes)

    def test_pmdm_blocked_or_license_unknown_cannot_be_recorded_as_successful_pmdm(self) -> None:
        for status in ("blocked", "license_unknown"):
            with self.subTest(status=status):
                envelope = _build_manifest(
                    baseline_mode=BASELINE_MODE_PMDM,
                    is_pmdm=True,
                    pmdm_status=status,
                    dependency_lock=V2DependencyLockProvenance(
                        status=DEPENDENCY_LOCK_AVAILABLE,
                        lock_hash=_hash("dependency-lock"),
                        uri="env-lock.yml",
                        format="yaml",
                    ),
                )

                self.assertFalse(envelope.receipt.passed)
                codes = [error.code for error in envelope.receipt.errors]
                self.assertIn(V2_MANIFEST_PMDM_UNAVAILABLE_SUCCESS, codes)

    def test_pmdm_mode_requires_is_pmdm_true(self) -> None:
        envelope = _build_manifest(
            baseline_mode=BASELINE_MODE_PMDM,
            is_pmdm=False,
            pmdm_status="available",
        )

        self.assertFalse(envelope.receipt.passed)
        self.assertEqual(envelope.receipt.errors[0].code, V2_MANIFEST_BASELINE_PMDM_MISMATCH)

    def test_dependency_lock_not_available_requires_reason(self) -> None:
        envelope = _build_manifest(
            dependency_lock=V2DependencyLockProvenance(
                status=DEPENDENCY_LOCK_NOT_AVAILABLE,
                lock_hash=None,
                reason="",
            )
        )

        self.assertFalse(envelope.receipt.passed)
        self.assertEqual(envelope.receipt.errors[0].code, V2_MANIFEST_DEPENDENCY_LOCK_REASON_MISSING)

    def test_invalid_required_data_hash_reports_once(self) -> None:
        envelope = _build_manifest(
            data_hashes={
                "records_jsonl": "bad",
                "split_index": v2_hash_object({"REC-V2-MANIFEST": "train"}),
                "quality_report": v2_hash_object({"REC-V2-MANIFEST": "Q1"}),
                "visual_check_index": v2_hash_object({"REC-V2-MANIFEST": "pass"}),
                "license_gate_report": v2_hash_object({"REC-V2-MANIFEST": "allowed"}),
            }
        )

        self.assertFalse(envelope.receipt.passed)
        matching = [
            error
            for error in envelope.receipt.errors
            if error.code == "V2_MANIFEST_HASH_FORMAT_INVALID"
            and error.location == "data_hashes.records_jsonl"
        ]
        self.assertEqual(len(matching), 1)

    def test_missing_required_data_hash_fails(self) -> None:
        data_hashes = {
            "split_index": v2_hash_object({"REC-V2-MANIFEST": "train"}),
            "quality_report": v2_hash_object({"REC-V2-MANIFEST": "Q1"}),
            "visual_check_index": v2_hash_object({"REC-V2-MANIFEST": "pass"}),
            "license_gate_report": v2_hash_object({"REC-V2-MANIFEST": "allowed"}),
        }
        envelope = _build_manifest(data_hashes=data_hashes)

        self.assertFalse(envelope.receipt.passed)
        self.assertEqual(envelope.receipt.errors[0].code, V2_MANIFEST_DATA_HASH_MISSING)

    def test_missing_or_unsupported_baseline_mode_fails(self) -> None:
        cases = [
            ("", V2_MANIFEST_BASELINE_MODE_MISSING),
            ("unsupported", V2_MANIFEST_BASELINE_MODE_UNSUPPORTED),
        ]
        for mode, code in cases:
            with self.subTest(mode=mode):
                envelope = _build_manifest(baseline_mode=mode)

                self.assertFalse(envelope.receipt.passed)
                self.assertEqual(envelope.receipt.errors[0].code, code)

    def test_unsupported_dependency_lock_status_fails(self) -> None:
        envelope = _build_manifest(
            dependency_lock=V2DependencyLockProvenance(
                status="bogus",
                lock_hash=None,
                reason="invalid status",
            )
        )

        self.assertFalse(envelope.receipt.passed)
        self.assertEqual(envelope.receipt.errors[0].code, V2_MANIFEST_DEPENDENCY_LOCK_STATUS_INVALID)

    def test_public_training_facade_lazy_exports_manifest_api(self) -> None:
        import covalent_design.training as training

        self.assertIn("build_v2_checkpoint_experiment_manifest", training.__all__)
        self.assertNotIn("build_v2_checkpoint_experiment_manifest", training.__dict__)
        func = training.build_v2_checkpoint_experiment_manifest
        self.assertTrue(callable(func))
        self.assertIn("build_v2_checkpoint_experiment_manifest", training.__dict__)

    def test_manifest_module_import_has_no_task50_heavy_side_effects(self) -> None:
        code = (
            "import sys;"
            "import covalent_design.training.v2_manifests;"
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

    def test_source_and_fixtures_stay_in_manifest_boundary(self) -> None:
        source = ROOT / "src" / "covalent_design" / "training" / "v2_manifests.py"
        paths = [source, *FIXTURE_ROOT.rglob("*")]
        forbidden_fragments = (".pt", ".pth", ".ck" + "pt", ".bin", "model " + "weight", "weights")
        for path in paths:
            if path.is_dir():
                continue
            text = path.read_text("utf-8")
            for token in forbidden_fragments:
                self.assertNotIn(token, text, str(path))
        task_tokens = ("v2_" + "tune", "tiny_" + "sweep", "Task " + "52")
        for token in task_tokens:
            self.assertNotIn(token, source.read_text("utf-8"))


def _build_manifest(**overrides):
    payload = _load_fixture()
    data_hashes = {
        "records_jsonl": v2_hash_object({"record_id": "REC-V2-MANIFEST"}),
        "split_index": v2_hash_object({"REC-V2-MANIFEST": "train"}),
        "quality_report": v2_hash_object({"REC-V2-MANIFEST": "Q1"}),
        "visual_check_index": v2_hash_object({"REC-V2-MANIFEST": "pass"}),
        "license_gate_report": v2_hash_object({"REC-V2-MANIFEST": "allowed"}),
    }
    params = {
        "manifest_id": "manifest-run-1",
        "run_id": "run-1",
        "environment_hash": v2_hash_object(payload["environment"]),
        "dependency_lock": V2DependencyLockProvenance(
            status=DEPENDENCY_LOCK_NOT_AVAILABLE,
            lock_hash=None,
            reason="lock workflow documented but no verified lock file exists",
        ),
        "data_hashes": data_hashes,
        "dataset_index_hash": v2_hash_object(payload["dataset_index"]),
        "family_readiness_hash": v2_hash_object(payload["family_readiness"]),
        "training_config_hash": v2_hash_object(payload["config"]),
        "training_summary_hash": v2_hash_file(FIXTURE_ROOT / "manifest_input.json"),
        "training_summary_ref": "fixture://training-summary/run-1",
        "checkpoint_refs": (
            V2CheckpointRef(
                checkpoint_id="checkpoint-run-1-step-0",
                checkpoint_uri="checkpoint-ref://run-1/step-0",
                step=0,
                sha256=v2_hash_object({"checkpoint_id": "checkpoint-run-1-step-0"}),
            ),
        ),
        "baseline_mode": BASELINE_MODE_NON_PMDM,
        "is_pmdm": False,
        "warnings": ("baseline is not PMDM; this is a smoke-only path",),
    }
    params.update(overrides)
    return build_v2_checkpoint_experiment_manifest(**params)


def _load_fixture() -> dict[str, object]:
    return json.loads((FIXTURE_ROOT / "manifest_input.json").read_text("utf-8"))


def _hash(value: str) -> str:
    return "sha256:" + __import__("hashlib").sha256(value.encode("utf-8")).hexdigest()


if __name__ == "__main__":
    unittest.main()
