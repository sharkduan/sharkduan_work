"""Task 49 V2 training dataset eligibility tests."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path

from covalent_design.contracts import ContractEnvelope

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "training" / "v2_dataset"
RECORDS = FIXTURE_ROOT / "records.jsonl"
SPLITS = FIXTURE_ROOT / "split_index.json"
VISUAL = FIXTURE_ROOT / "visual_check_index.json"
QUALITY = FIXTURE_ROOT / "quality_report.json"
FAMILY = FIXTURE_ROOT / "family_readiness_report.json"
LICENSE = FIXTURE_ROOT / "license_gate_report.json"


def _prepare(split_name: str = "train", policy=None):
    return _prepare_with_paths(split_name=split_name, policy=policy)


def _prepare_with_paths(
    split_name: str = "train",
    policy=None,
    *,
    records_path=RECORDS,
    split_index_path=SPLITS,
    visual_check_index_path=VISUAL,
    quality_report_path=QUALITY,
    family_readiness_report_path=FAMILY,
    license_gate_report_path=LICENSE,
):
    from covalent_design.training.v2_dataset import prepare_v2_dataset

    return prepare_v2_dataset(
        records_path,
        split_index_path,
        split_name,
        visual_check_index_path=visual_check_index_path,
        quality_report_path=quality_report_path,
        family_readiness_report_path=family_readiness_report_path,
        license_gate_report_path=license_gate_report_path,
        policy=policy,
    )


def _ids(envelope):
    return [record.record_id for record in envelope.payload.records]


def _excluded(envelope, record_id):
    return next(record for record in envelope.payload.excluded_records if record.record_id == record_id)


def _write_json(path, value) -> None:
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path, rows) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


class V2DatasetAPIContractTests(unittest.TestCase):
    def test_prepare_v2_dataset_is_importable(self) -> None:
        from covalent_design.training.v2_dataset import prepare_v2_dataset

        self.assertTrue(callable(prepare_v2_dataset))

    def test_prepare_v2_dataset_returns_contract_envelope(self) -> None:
        envelope = _prepare()
        self.assertIsInstance(envelope, ContractEnvelope)
        self.assertTrue(envelope.receipt.ok)
        self.assertEqual("train", envelope.payload.split_name)

    def test_invalid_split_name_returns_structured_error(self) -> None:
        envelope = _prepare("dev")
        self.assertFalse(envelope.receipt.ok)
        self.assertEqual("V2_DATASET_INVALID_SPLIT_NAME", envelope.receipt.errors[0].code)
        self.assertEqual("training", envelope.receipt.errors[0].owner)


class V2EligibilityGateTests(unittest.TestCase):
    def test_eligible_record_passes_all_gates(self) -> None:
        envelope = _prepare()
        self.assertIn("REC-ELIG", _ids(envelope))

    def test_blocked_family_is_excluded(self) -> None:
        envelope = _prepare()
        rec = _excluded(envelope, "REC-BLOCK-FAMILY")
        self.assertEqual("excluded_family_blocked", rec.primary_reason)

    def test_blocked_and_unknown_license_are_excluded(self) -> None:
        envelope = _prepare()
        self.assertEqual("excluded_license_blocked", _excluded(envelope, "REC-LIC-BLOCK").primary_reason)
        self.assertEqual("excluded_license_unknown", _excluded(envelope, "REC-LIC-UNKNOWN").primary_reason)

    def test_restricted_license_requires_satisfied_conditions(self) -> None:
        envelope = _prepare()
        self.assertEqual("excluded_license_restricted_unsatisfied", _excluded(envelope, "REC-REST-BAD").primary_reason)
        self.assertIn("REC-REST-OK", _ids(envelope))


    def test_missing_license_audit_ref_is_excluded(self) -> None:
        rows = RECORDS.read_text("utf-8").splitlines()
        mutated = []
        for line in rows:
            row = json.loads(line)
            if row["record_id"] == "REC-ELIG":
                row["metadata"].pop("license_audit_ref", None)
            mutated.append(json.dumps(row, sort_keys=True))
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_records = Path(tmpdir) / "records.jsonl"
            tmp_records.write_text("\n".join(mutated) + "\n", encoding="utf-8")
            from covalent_design.training.v2_dataset import prepare_v2_dataset

            envelope = prepare_v2_dataset(
                tmp_records,
                SPLITS,
                "train",
                visual_check_index_path=VISUAL,
                quality_report_path=QUALITY,
                family_readiness_report_path=FAMILY,
                license_gate_report_path=LICENSE,
            )
        self.assertEqual("excluded_license_audit_missing", _excluded(envelope, "REC-ELIG").primary_reason)
    def test_manual_exempt_only_allowed_for_manual_intake_mode(self) -> None:
        envelope = _prepare()
        self.assertIn("REC-MANUAL-OK", _ids(envelope))
        manual_entry = next(record for record in envelope.payload.records if record.record_id == "REC-MANUAL-OK")
        self.assertEqual("manual_exempt", manual_entry.license_status)
        self.assertEqual("excluded_manual_exempt_non_manual", _excluded(envelope, "REC-MANUAL-DOWNLOAD").primary_reason)
    def test_manual_exempt_audit_failed_is_excluded_even_in_manual_mode(self) -> None:
        license_report = json.loads(LICENSE.read_text("utf-8"))
        for source in license_report["sources"]:
            if source["license_audit_ref"] == "audit/manual_ok":
                source["training_eligible"] = False
                source["reason_codes"] = ["V2_LICENSE_MANUAL_EXEMPT_AUDIT_FAILED"]
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_license = Path(tmpdir) / "license_gate_report.json"
            _write_json(tmp_license, license_report)
            envelope = _prepare_with_paths(license_gate_report_path=tmp_license)
        excluded = _excluded(envelope, "REC-MANUAL-OK")
        self.assertEqual("excluded_manual_exempt_audit_failed", excluded.primary_reason)
        self.assertIn("excluded_manual_exempt_audit_failed", excluded.all_reasons)
        self.assertEqual(("V2_LICENSE_MANUAL_EXEMPT_AUDIT_FAILED",), excluded.license_reason_codes)

    def test_missing_split_assignment_is_excluded(self) -> None:
        split_index = json.loads(SPLITS.read_text("utf-8"))
        split_index["assignments"] = [
            item for item in split_index["assignments"] if item["record_id"] != "REC-ELIG"
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_splits = Path(tmpdir) / "split_index.json"
            _write_json(tmp_splits, split_index)
            envelope = _prepare_with_paths(split_index_path=tmp_splits)
        self.assertEqual("missing_split_assignment", _excluded(envelope, "REC-ELIG").primary_reason)

    def test_deferred_and_partial_family_readiness_are_excluded(self) -> None:
        for family_status, expected_reason in (
            ("deferred", "excluded_family_deferred"),
            ("partial", "excluded_family_partial"),
        ):
            family_report = json.loads(FAMILY.read_text("utf-8"))
            for family in family_report["families"]:
                if family["family"] == "CYS_MICHAEL_ADDITION":
                    family["status"] = family_status
            with tempfile.TemporaryDirectory() as tmpdir:
                tmp_family = Path(tmpdir) / "family_readiness_report.json"
                _write_json(tmp_family, family_report)
                envelope = _prepare_with_paths(family_readiness_report_path=tmp_family)
            self.assertEqual(expected_reason, _excluded(envelope, "REC-ELIG").primary_reason)

    def test_missing_artifact_roles_are_excluded_without_path_validation(self) -> None:
        rows = [json.loads(line) for line in RECORDS.read_text("utf-8").splitlines()]
        for row in rows:
            if row["record_id"] == "REC-ELIG":
                for artifact in row["artifacts"]:
                    artifact["role"] = ""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_records = Path(tmpdir) / "records.jsonl"
            _write_jsonl(tmp_records, rows)
            envelope = _prepare_with_paths(records_path=tmp_records)
        self.assertEqual("excluded_missing_artifact_roles", _excluded(envelope, "REC-ELIG").primary_reason)

    def test_visual_blocked_statuses_are_excluded_and_pass_is_non_blocking(self) -> None:
        envelope = _prepare()
        for record_id in ("REC-VIS-FAIL", "REC-VIS-PENDING", "REC-VIS-REVIEW"):
            self.assertEqual("excluded_visual_blocked", _excluded(envelope, record_id).primary_reason)
        self.assertIn("REC-ELIG", _ids(envelope))

    def test_split_policy_excludes_other_and_excluded_splits(self) -> None:
        envelope = _prepare()
        self.assertEqual("not_in_this_split", _excluded(envelope, "REC-OTHER-SPLIT").primary_reason)
        self.assertEqual("hard_excluded_by_split", _excluded(envelope, "REC-SPLIT-EXCLUDED").primary_reason)

    def test_quality_and_multi_linkage_gates(self) -> None:
        envelope = _prepare()
        self.assertEqual("excluded_quality_tier", _excluded(envelope, "REC-Q3").primary_reason)
        self.assertEqual("excluded_multi_linkage", _excluded(envelope, "REC-MULTI").primary_reason)


class V2Q2PolicyTests(unittest.TestCase):
    def test_q2_is_kept_by_default_and_tier_is_preserved(self) -> None:
        envelope = _prepare()
        self.assertIn("REC-Q2", _ids(envelope))
        entry = next(record for record in envelope.payload.records if record.record_id == "REC-Q2")
        self.assertEqual("Q2", entry.quality_tier)

    def test_q2_is_excluded_only_when_policy_says_so(self) -> None:
        from covalent_design.training.v2_dataset import V2TrainingDataPolicy

        envelope = _prepare(policy=V2TrainingDataPolicy(exclude_q2=True))
        self.assertEqual("excluded_q2", _excluded(envelope, "REC-Q2").primary_reason)


class V2ExclusionAccountingTests(unittest.TestCase):
    def test_exclusion_summary_accounts_for_every_record(self) -> None:
        envelope = _prepare()
        summary = envelope.payload.exclusion_summary
        self.assertEqual(17, summary.input_count)
        self.assertEqual(len(envelope.payload.records), summary.eligible_count)
        self.assertEqual(len(envelope.payload.excluded_records), summary.excluded_count)
        self.assertEqual(summary.input_count, summary.eligible_count + summary.excluded_count)
        self.assertEqual(summary.excluded_count, sum(summary.primary_reason_counts.values()))

    def test_primary_reason_is_deterministic_and_all_reasons_preserve_multiple_causes(self) -> None:
        first = _prepare()
        second = _prepare()
        first_reasons = [(r.record_id, r.primary_reason, r.all_reasons) for r in first.payload.excluded_records]
        second_reasons = [(r.record_id, r.primary_reason, r.all_reasons) for r in second.payload.excluded_records]
        self.assertEqual(first_reasons, second_reasons)
        multi = _excluded(first, "REC-MULTI-REASONS")
        self.assertEqual("excluded_license_blocked", multi.primary_reason)
        self.assertIn("excluded_visual_blocked", multi.all_reasons)
        self.assertIn("excluded_quality_tier", multi.all_reasons)
        self.assertIn("excluded_multi_linkage", multi.all_reasons)

    def test_output_order_is_deterministic(self) -> None:
        envelope = _prepare()
        self.assertEqual(sorted(_ids(envelope)), _ids(envelope))
        excluded_ids = [record.record_id for record in envelope.payload.excluded_records]
        self.assertEqual(sorted(excluded_ids), excluded_ids)

    def test_output_is_json_serializable(self) -> None:
        from covalent_design.training.v2_dataset import v2_training_dataset_index_to_dict

        envelope = _prepare()
        json.dumps(v2_training_dataset_index_to_dict(envelope.payload), sort_keys=True)
        json.dumps(asdict(envelope.payload.exclusion_summary), sort_keys=True)
    def test_excluded_records_preserve_source_intake_and_license_reason_codes(self) -> None:
        envelope = _prepare()
        blocked = _excluded(envelope, "REC-LIC-BLOCK")
        self.assertEqual("FixtureBlocked", blocked.source_name)
        self.assertEqual("manual", blocked.intake_mode)
        self.assertEqual(("V2_LICENSE_STATUS_BLOCKED",), blocked.license_reason_codes)


class V2StructuredErrorTests(unittest.TestCase):
    def test_missing_records_file_returns_structured_error(self) -> None:
        from covalent_design.training.v2_dataset import prepare_v2_dataset

        envelope = prepare_v2_dataset(
            FIXTURE_ROOT / "missing.jsonl",
            SPLITS,
            "train",
            visual_check_index_path=VISUAL,
            quality_report_path=QUALITY,
            family_readiness_report_path=FAMILY,
            license_gate_report_path=LICENSE,
        )
        self.assertFalse(envelope.receipt.ok)
        self.assertEqual("V2_DATASET_RECORDS_FILE_MISSING", envelope.receipt.errors[0].code)

    def test_missing_report_file_returns_structured_error(self) -> None:
        from covalent_design.training.v2_dataset import prepare_v2_dataset

        envelope = prepare_v2_dataset(
            RECORDS,
            SPLITS,
            "train",
            visual_check_index_path=VISUAL,
            quality_report_path=QUALITY,
            family_readiness_report_path=FAMILY,
            license_gate_report_path=FIXTURE_ROOT / "missing_license.json",
        )
        self.assertFalse(envelope.receipt.ok)
        self.assertEqual("V2_DATASET_LICENSE_REPORT_MISSING", envelope.receipt.errors[0].code)


class V2ModuleBoundaryTests(unittest.TestCase):
    def test_module_does_not_import_forbidden_heavy_or_task50_modules(self) -> None:
        code = """
import json
import sys
before = set(sys.modules)
from covalent_design.training.v2_dataset import prepare_v2_dataset
loaded = set(sys.modules) - before
forbidden_terms = ("pmdm", "pocketflow", "torch", "rdkit", "losses", "train_loop", "checkpoints")
forbidden = sorted(name for name in loaded for term in forbidden_terms if term in name.lower())
print(json.dumps({"callable": callable(prepare_v2_dataset), "forbidden": forbidden}, sort_keys=True))
"""
        env = os.environ.copy()
        env["PYTHONPATH"] = "src"
        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd=Path(__file__).resolve().parents[2],
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(result.stdout)
        self.assertTrue(payload["callable"])
        self.assertEqual([], payload["forbidden"])

    def test_source_does_not_reference_real_data_root_or_forbidden_imports(self) -> None:
        source = Path("src/covalent_design/training/v2_dataset.py").read_text("utf-8")
        self.assertNotIn("D:\\codex_work\\data", source)
        for text in ("import torch", "import rdkit", "pmdm_real_adapter", "PocketFlow", "compute_losses", "run_smoke_train"):
            self.assertNotIn(text, source)


if __name__ == "__main__":
    unittest.main()
