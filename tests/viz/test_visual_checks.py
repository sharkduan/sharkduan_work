from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Optional

from covalent_design.contracts import CONTRACT_VERSION, ContractEnvelope, ValidationReceipt
from covalent_design.viz.visual_checks import export_visual_checks


FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "visual_checks"
VALID_RECORDS = FIXTURE_ROOT / "valid" / "records.jsonl"
INVALID_MISSING_ARTIFACT_RECORDS = (
    FIXTURE_ROOT / "invalid_missing_artifact" / "records.jsonl"
)
CLI_MODULE = "covalent_design.viz.cli.export_visual_checks"

VALID_STATUSES = {"pending", "pass", "fail", "needs_rule_review"}
BLOCKING_STATUSES = {"pending", "fail", "needs_rule_review"}


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text("utf-8"))


def _sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


class VisualCheckFixtureMixin:
    def setUp(self) -> None:
        self.tmpdir = Path(tempfile.mkdtemp(prefix="task15_visual_checks_"))
        self.out_root = self.tmpdir / "visual_out"

    def tearDown(self) -> None:
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def export_valid(self, sample_count: Optional[int] = None):
        return export_visual_checks(
            records_path=VALID_RECORDS,
            out_root=self.out_root,
            sample_count=sample_count,
            seed=42,
        )

    def index(self) -> dict:
        return _load_json(self.out_root / "visual_check_index.json")

    def visual_artifact(self, record_id: str) -> dict:
        return _load_json(self.out_root / "artifacts" / record_id / "visual_check.json")


class VisualCheckAPITests(VisualCheckFixtureMixin, unittest.TestCase):
    def test_returns_contract_envelope_with_ok_receipt(self):
        envelope = self.export_valid()
        self.assertIsInstance(envelope, ContractEnvelope)
        self.assertIsInstance(envelope.receipt, ValidationReceipt)
        self.assertTrue(envelope.receipt.ok)
        self.assertEqual(CONTRACT_VERSION, envelope.receipt.contract_version)
        self.assertEqual(_sha256_file(VALID_RECORDS), envelope.receipt.input_sha256)

    def test_valid_fixture_exports_visual_check_index_json(self):
        envelope = self.export_valid()
        self.assertTrue(envelope.receipt.ok)
        index_path = self.out_root / "visual_check_index.json"
        self.assertTrue(index_path.exists())
        index = self.index()
        self.assertEqual("visual_check_index", index["role"])
        self.assertEqual("1", index["schema_version"])
        self.assertEqual(CONTRACT_VERSION, index["contract_version"])
        self.assertEqual(
            {"sample_count", "seed", "total_accepted"},
            set(index["sample_policy"]),
        )
        self.assertEqual(5, index["sample_policy"]["total_accepted"])
        self.assertEqual(5, len(index["records"]))

    def test_sampled_visual_artifact_contains_required_evidence(self):
        self.export_valid(sample_count=1)
        index = self.index()
        entry = index["records"][0]
        artifact = self.visual_artifact(entry["record_id"])

        self.assertEqual("visual_check", artifact["role"])
        self.assertEqual(entry["record_id"], artifact["record_id"])
        self.assertEqual(entry["status"], artifact["status"])
        self.assertEqual(
            entry["blocking_first_core"],
            artifact["blocking_first_core"],
        )
        self.assertIn("artifact_ref", entry)
        self.assertEqual("visual_check", entry["artifact_ref"]["role"])
        self.assertEqual("json", entry["artifact_ref"]["format"])
        self.assertGreater(entry["artifact_ref"]["bytes"], 0)
        self.assertRegex(entry["artifact_ref"]["sha256"], r"^[0-9a-f]{64}$")
        self.assertIn("target_atom", artifact)
        self.assertEqual("SG", artifact["target_atom"]["name"])
        self.assertEqual("S", artifact["target_atom"]["element"])
        self.assertIn("ligand_attachment_atom", artifact)
        self.assertEqual("C1", artifact["ligand_attachment_atom"]["name"])
        self.assertIn("covalent_edge", artifact)
        self.assertEqual("SG", artifact["covalent_edge"]["target_atom"]["name"])
        self.assertEqual("S", artifact["covalent_edge"]["target_atom"]["element"])
        self.assertEqual("C1", artifact["covalent_edge"]["ligand_atom"]["name"])
        self.assertEqual("C", artifact["covalent_edge"]["ligand_atom"]["element"])
        self.assertIn("bond_length", artifact["covalent_edge"])
        self.assertIn("bond_type", artifact["covalent_edge"])
        self.assertEqual("CYS_MICHAEL_ADDITION", artifact["residue_reaction_family"])
        self.assertNotIn("family", artifact)
        self.assertIn("warhead_annotation", artifact)
        self.assertIn("warhead_type", artifact["warhead_annotation"])
        self.assertIn("warhead_smarts", artifact["warhead_annotation"])

    def test_distance_and_local_angles_are_included_when_available(self):
        self.export_valid(sample_count=1)
        index = self.index()
        artifact = self.visual_artifact(index["records"][0]["record_id"])

        self.assertIn("distance", artifact)
        self.assertNotIn("distance_unit", artifact)
        self.assertIsInstance(artifact["distance"], float)
        self.assertIn("local_angles", artifact)
        self.assertIsInstance(artifact["local_angles"]["protein_side"], float)
        self.assertIsInstance(artifact["local_angles"]["ligand_side"], float)

    def test_missing_optional_distance_or_angles_does_not_fail(self):
        envelope = self.export_valid(sample_count=5)
        self.assertTrue(envelope.receipt.ok)
        index = self.index()
        missing_geometry_entry = next(
            item
            for item in index["records"]
            if item["record_id"] == "VC000000000000000000000000000005"
        )
        artifact = self.visual_artifact(missing_geometry_entry["record_id"])
        self.assertIsNone(artifact["distance"])
        self.assertIsNone(artifact["local_angles"])

    def test_status_gate_semantics_are_explicit(self):
        self.export_valid(sample_count=5)
        index = self.index()
        statuses = {entry["record_id"]: entry for entry in index["records"]}

        self.assertEqual("pass", statuses["VC000000000000000000000000000001"]["status"])
        self.assertFalse(
            statuses["VC000000000000000000000000000001"]["blocking_first_core"]
        )
        self.assertEqual("fail", statuses["VC000000000000000000000000000002"]["status"])
        self.assertTrue(
            statuses["VC000000000000000000000000000002"]["blocking_first_core"]
        )
        self.assertEqual(
            "needs_rule_review",
            statuses["VC000000000000000000000000000003"]["status"],
        )
        self.assertTrue(
            statuses["VC000000000000000000000000000003"]["blocking_first_core"]
        )
        self.assertEqual(
            "pending",
            statuses["VC000000000000000000000000000004"]["status"],
        )
        self.assertTrue(
            statuses["VC000000000000000000000000000004"]["blocking_first_core"]
        )

    def test_index_counts_blocking_statuses(self):
        self.export_valid(sample_count=5)
        index = self.index()
        self.assertEqual(5, len(index["records"]))
        self.assertEqual(1, index["status_counts"]["pass"])
        self.assertEqual(1, index["status_counts"]["fail"])
        self.assertEqual(1, index["status_counts"]["needs_rule_review"])
        self.assertEqual(2, index["status_counts"]["pending"])
        self.assertEqual(
            {"blocking_first_core": 4, "non_blocking": 1},
            index["blocking_counts"],
        )
        for entry in index["records"]:
            self.assertIn(entry["status"], VALID_STATUSES)
            self.assertEqual(
                entry["status"] in BLOCKING_STATUSES,
                entry["blocking_first_core"],
            )

    def test_default_sample_count_exports_all_records(self):
        self.export_valid()
        index = self.index()
        self.assertIsNone(index["sample_policy"]["sample_count"])
        self.assertEqual(5, len(index["records"]))

    def test_output_is_deterministic_for_same_seed(self):
        first_dir = self.tmpdir / "first"
        second_dir = self.tmpdir / "second"
        export_visual_checks(VALID_RECORDS, first_dir, sample_count=3, seed=7)
        export_visual_checks(VALID_RECORDS, second_dir, sample_count=3, seed=7)

        first = (first_dir / "visual_check_index.json").read_bytes()
        second = (second_dir / "visual_check_index.json").read_bytes()
        self.assertEqual(first, second)

    def test_no_task16_quality_report_is_generated(self):
        self.export_valid(sample_count=5)
        names = {path.name for path in self.out_root.rglob("*") if path.is_file()}
        self.assertNotIn("quality_report.json", names)
        self.assertNotIn("etl_quality_report.md", names)
        for name in names:
            self.assertNotIn("quality_report", name.lower())

    def test_invalid_missing_edge_candidate_returns_structured_error(self):
        envelope = export_visual_checks(
            records_path=INVALID_MISSING_ARTIFACT_RECORDS,
            out_root=self.out_root,
            sample_count=1,
            seed=42,
        )
        self.assertFalse(envelope.receipt.ok)
        self.assertGreater(len(envelope.receipt.errors), 0)
        self.assertTrue(
            any("EDGE" in error.code or "ARTIFACT" in error.code
                for error in envelope.receipt.errors),
            [error.code for error in envelope.receipt.errors],
        )
        self.assertFalse((self.out_root / "visual_check_index.json").exists())

    def test_missing_core_labels_returns_structured_error(self):
        source_root = FIXTURE_ROOT / "valid"
        records = [
            json.loads(line)
            for line in VALID_RECORDS.read_text("utf-8").splitlines()
            if line.strip()
        ]
        invalid = dict(records[0])
        invalid.pop("core_labels", None)
        fixture_root = self.tmpdir / "missing_core_labels"
        shutil.copytree(source_root / "artifacts", fixture_root / "artifacts")
        records_path = fixture_root / "records.jsonl"
        records_path.write_text(json.dumps(invalid) + "\n", "utf-8")

        envelope = export_visual_checks(
            records_path=records_path,
            out_root=self.out_root,
            sample_count=1,
            seed=42,
        )

        self.assertFalse(envelope.receipt.ok)
        self.assertTrue(
            any("CORE_LABELS" in error.code for error in envelope.receipt.errors),
            [error.code for error in envelope.receipt.errors],
        )
        self.assertFalse((self.out_root / "visual_check_index.json").exists())


class VisualCheckCLITests(unittest.TestCase):
    @staticmethod
    def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = "src"
        return subprocess.run(
            [sys.executable, "-m", CLI_MODULE, *args],
            cwd=Path(__file__).resolve().parents[2],
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_cli_help_returns_zero(self):
        result = self.run_cli("--help")
        self.assertEqual(0, result.returncode, msg=result.stderr)

    def test_cli_valid_fixture_returns_zero_and_outputs_json_summary(self):
        tmpdir = Path(tempfile.mkdtemp(prefix="task15_cli_valid_"))
        try:
            out_root = tmpdir / "visual_out"
            result = self.run_cli(
                "--records", str(VALID_RECORDS),
                "--out-root", str(out_root),
                "--sample-count", "5",
                "--seed", "42",
            )
            self.assertEqual(0, result.returncode, msg=result.stderr)
            summary = json.loads(result.stdout)
            self.assertTrue(summary["ok"])
            self.assertEqual("export_visual_checks_summary", summary["role"])
            self.assertEqual(5, summary["sampled_count"])
            self.assertTrue((out_root / "visual_check_index.json").exists())
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_cli_invalid_fixture_returns_nonzero_and_json_errors(self):
        tmpdir = Path(tempfile.mkdtemp(prefix="task15_cli_invalid_"))
        try:
            out_root = tmpdir / "visual_out"
            result = self.run_cli(
                "--records", str(INVALID_MISSING_ARTIFACT_RECORDS),
                "--out-root", str(out_root),
                "--sample-count", "1",
            )
            self.assertNotEqual(0, result.returncode)
            summary = json.loads(result.stdout)
            self.assertFalse(summary["ok"])
            self.assertGreater(len(summary["errors"]), 0)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
