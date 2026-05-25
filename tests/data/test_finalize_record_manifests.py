from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from covalent_design.contracts.types import CONTRACT_VERSION, ContractEnvelope
from covalent_design.data.artifact_manifests import finalize_record_manifests
from covalent_design.io.artifacts import sha256_file


FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "finalize_record_manifests"
REQUIRED_NON_EDGE_ROLES = {
    "coordinates",
    "ligand_atom_table",
    "ligand_bond_table",
    "protein_atom_table",
}


def _copy_fixture(name: str) -> tuple[tempfile.TemporaryDirectory[str], Path]:
    temp_dir = tempfile.TemporaryDirectory()
    src = FIXTURE_ROOT / name
    dst = Path(temp_dir.name) / name
    shutil.copytree(src, dst)
    return temp_dir, dst


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _role_map(record: dict[str, object]) -> dict[str, dict[str, object]]:
    artifacts = record.get("artifacts", [])
    if not isinstance(artifacts, list):
        return {}
    return {
        str(ref.get("role", "")): ref
        for ref in artifacts
        if isinstance(ref, dict)
    }


class FinalizeRecordManifestsValidTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir, self.root = _copy_fixture("valid")
        self.records_path = self.root / "records.jsonl"
        self.before_records = _read_jsonl(self.records_path)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_returns_contract_envelope_with_receipt(self) -> None:
        envelope = finalize_record_manifests(self.records_path)

        self.assertIsInstance(envelope, ContractEnvelope)
        self.assertTrue(envelope.receipt.ok)
        self.assertEqual(CONTRACT_VERSION, envelope.receipt.contract_version)
        self.assertEqual(len(self.before_records), envelope.payload["record_count"])

    def test_appends_edge_candidate_ref_to_every_accepted_record(self) -> None:
        finalize_record_manifests(self.records_path)

        for record in _read_jsonl(self.records_path):
            ref = _role_map(record).get("edge_candidates")
            self.assertIsNotNone(ref)
            self.assertEqual("json", ref["format"])
            self.assertGreater(ref["bytes"], 0)
            self.assertRegex(ref["sha256"], r"^[0-9a-f]{64}$")
            self.assertTrue((self.root / str(ref["uri"])).exists())

    def test_preserves_non_edge_artifacts_and_record_fields(self) -> None:
        before_by_id = {str(row["record_id"]): row for row in self.before_records}

        finalize_record_manifests(self.records_path)

        for after in _read_jsonl(self.records_path):
            before = before_by_id[str(after["record_id"])]
            self.assertEqual(before["core_labels"], after["core_labels"])
            self.assertEqual(before["lineage"], after["lineage"])
            self.assertEqual(before["metadata"], after["metadata"])
            before_roles = _role_map(before)
            after_roles = _role_map(after)
            for role in REQUIRED_NON_EDGE_ROLES:
                self.assertEqual(before_roles[role], after_roles[role])

    def test_updates_artifact_manifest_with_edge_candidates(self) -> None:
        finalize_record_manifests(self.records_path)

        manifest = json.loads((self.root / "artifact_manifest.json").read_text(encoding="utf-8"))
        record_ids = {str(row["record_id"]) for row in _read_jsonl(self.records_path)}
        self.assertEqual(record_ids, set(manifest))
        for refs in manifest.values():
            roles = [ref["role"] for ref in refs]
            self.assertEqual(sorted(roles), roles)
            self.assertEqual(REQUIRED_NON_EDGE_ROLES | {"edge_candidates"}, set(roles))

    def test_edge_candidate_checksum_matches_written_file(self) -> None:
        finalize_record_manifests(self.records_path)

        for record in _read_jsonl(self.records_path):
            ref = _role_map(record)["edge_candidates"]
            self.assertEqual(ref["sha256"], sha256_file(self.root / str(ref["uri"])))

    def test_rejected_and_conflict_indexes_are_not_rewritten_or_edge_required(self) -> None:
        rejected_path = self.root / "rejected_index.jsonl"
        conflict_path = self.root / "conflict_index.jsonl"
        rejected_before = rejected_path.read_bytes()
        conflict_before = conflict_path.read_bytes()

        envelope = finalize_record_manifests(self.records_path)

        self.assertTrue(envelope.receipt.ok)
        self.assertEqual(rejected_before, rejected_path.read_bytes())
        self.assertEqual(conflict_before, conflict_path.read_bytes())

    def test_deterministic_output_across_repeated_runs(self) -> None:
        finalize_record_manifests(self.records_path)
        first_records = self.records_path.read_bytes()
        first_manifest = (self.root / "artifact_manifest.json").read_bytes()

        finalize_record_manifests(self.records_path)

        self.assertEqual(first_records, self.records_path.read_bytes())
        self.assertEqual(first_manifest, (self.root / "artifact_manifest.json").read_bytes())

    def test_no_split_or_visual_artifacts_are_created(self) -> None:
        finalize_record_manifests(self.records_path)

        names = [path.name.lower() for path in self.root.rglob("*")]
        self.assertFalse(any("split" in name for name in names))
        self.assertFalse(any("visual" in name for name in names))


class FinalizeRecordManifestsFailureTests(unittest.TestCase):
    def _run_failure_fixture(self, fixture: str) -> tuple[object, Path, tempfile.TemporaryDirectory[str]]:
        temp_dir, root = _copy_fixture(fixture)
        envelope = finalize_record_manifests(root / "records.jsonl")
        return envelope, root, temp_dir

    def test_missing_edge_candidate_fails_hard(self) -> None:
        envelope, _root, temp_dir = self._run_failure_fixture("missing_edge_candidate")
        self.addCleanup(temp_dir.cleanup)

        self.assertFalse(envelope.receipt.ok)
        codes = {error.code for error in envelope.receipt.errors}
        self.assertTrue(any("EDGE" in code and "MISSING" in code for code in codes))

    def test_checksum_mismatch_fails_hard(self) -> None:
        envelope, _root, temp_dir = self._run_failure_fixture("checksum_mismatch")
        self.addCleanup(temp_dir.cleanup)

        self.assertFalse(envelope.receipt.ok)
        codes = {error.code for error in envelope.receipt.errors}
        self.assertTrue(any("CHECKSUM" in code for code in codes))

    def test_obsolete_unlinked_manifest_entry_fails(self) -> None:
        envelope, _root, temp_dir = self._run_failure_fixture("obsolete_manifest")
        self.addCleanup(temp_dir.cleanup)

        self.assertFalse(envelope.receipt.ok)
        codes = {error.code for error in envelope.receipt.errors}
        self.assertTrue(any("OBSOLETE" in code or "UNLINKED" in code for code in codes))

    def test_obsolete_or_rejected_marked_manifest_entry_is_allowed(self) -> None:
        temp_dir, root = _copy_fixture("valid")
        self.addCleanup(temp_dir.cleanup)
        manifest_path = root / "artifact_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["obsolete-record"] = {"obsolete": True, "reason": "superseded"}
        manifest["rejected-record"] = {"status": "rejected", "reason": "Q0"}
        manifest_path.write_text(
            json.dumps(manifest, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )

        envelope = finalize_record_manifests(root / "records.jsonl")

        self.assertTrue(envelope.receipt.ok, envelope.receipt.errors)

    def test_manifest_only_duplicate_edge_candidate_ref_fails(self) -> None:
        temp_dir, root = _copy_fixture("valid")
        self.addCleanup(temp_dir.cleanup)
        manifest_path = root / "artifact_manifest.json"
        records = _read_jsonl(root / "records.jsonl")
        record_id = str(records[0]["record_id"])
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest[record_id].append(
            {
                "bytes": 10,
                "format": "json",
                "role": "edge_candidates",
                "schema_version": "1",
                "sha256": "0" * 64,
                "uri": f"artifacts/{record_id}/edge_candidates.json",
            }
        )
        manifest_path.write_text(
            json.dumps(manifest, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )

        envelope = finalize_record_manifests(root / "records.jsonl")

        self.assertFalse(envelope.receipt.ok)
        self.assertIn(
            "EDGE_CANDIDATE_ARTIFACT_DUPLICATE",
            {error.code for error in envelope.receipt.errors},
        )

    def test_edge_candidate_record_id_mismatch_fails(self) -> None:
        temp_dir, root = _copy_fixture("valid")
        self.addCleanup(temp_dir.cleanup)
        records = _read_jsonl(root / "records.jsonl")
        record_id = str(records[0]["record_id"])
        edge_path = root / "artifacts" / record_id / "edge_candidates.json"
        edge_payload = json.loads(edge_path.read_text(encoding="utf-8"))
        edge_payload["record_id"] = "different-record-id"
        edge_path.write_text(
            json.dumps(edge_payload, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )

        envelope = finalize_record_manifests(root / "records.jsonl")

        self.assertFalse(envelope.receipt.ok)
        self.assertIn(
            "EDGE_CANDIDATE_RECORD_ID_MISMATCH",
            {error.code for error in envelope.receipt.errors},
        )

    def test_malformed_edge_candidate_json_fails(self) -> None:
        temp_dir, root = _copy_fixture("valid")
        self.addCleanup(temp_dir.cleanup)
        records = _read_jsonl(root / "records.jsonl")
        record_id = str(records[0]["record_id"])
        edge_path = root / "artifacts" / record_id / "edge_candidates.json"
        edge_path.write_text("{not-json", encoding="utf-8")

        envelope = finalize_record_manifests(root / "records.jsonl")

        self.assertFalse(envelope.receipt.ok)
        self.assertIn("EDGE_CANDIDATE_UNREADABLE", {error.code for error in envelope.receipt.errors})

    def test_preexisting_edge_candidate_ref_fails_deterministically(self) -> None:
        envelope, root, temp_dir = self._run_failure_fixture("duplicate_edge_candidate")
        self.addCleanup(temp_dir.cleanup)
        first_records = (root / "records.jsonl").read_bytes()

        second = finalize_record_manifests(root / "records.jsonl")

        self.assertFalse(envelope.receipt.ok)
        self.assertFalse(second.receipt.ok)
        self.assertEqual(first_records, (root / "records.jsonl").read_bytes())
        codes = {error.code for error in envelope.receipt.errors}
        self.assertTrue(any("DUPLICATE" in code for code in codes))

    def test_edge_candidate_role_invalid_fails(self) -> None:
        temp_dir, root = _copy_fixture("valid")
        self.addCleanup(temp_dir.cleanup)
        records = _read_jsonl(root / "records.jsonl")
        record_id = str(records[0]["record_id"])
        edge_path = root / "artifacts" / record_id / "edge_candidates.json"
        edge_payload = json.loads(edge_path.read_text(encoding="utf-8"))
        edge_payload["role"] = "visual_check"
        edge_path.write_text(
            json.dumps(edge_payload, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )

        envelope = finalize_record_manifests(root / "records.jsonl")

        self.assertFalse(envelope.receipt.ok)
        self.assertIn("EDGE_CANDIDATE_ROLE_INVALID", {error.code for error in envelope.receipt.errors})


class FinalizeRecordManifestsCLITests(unittest.TestCase):
    def _run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = "src"
        return subprocess.run(
            [sys.executable, "-m", "covalent_design.data.cli.finalize_record_manifests", *args],
            cwd=Path(__file__).resolve().parents[2],
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def test_cli_help_returns_zero(self) -> None:
        result = self._run_cli("--help")

        self.assertEqual(0, result.returncode, result.stderr)

    def test_cli_valid_fixture_returns_json_summary(self) -> None:
        temp_dir, root = _copy_fixture("valid")
        self.addCleanup(temp_dir.cleanup)

        result = self._run_cli("--records", str(root / "records.jsonl"))

        self.assertEqual(0, result.returncode, result.stderr)
        summary = json.loads(result.stdout)
        self.assertTrue(summary["ok"])
        self.assertEqual(2, summary["record_count"])
        self.assertEqual(2, summary["edge_candidate_count"])

    def test_cli_invalid_fixture_returns_nonzero_and_errors(self) -> None:
        temp_dir, root = _copy_fixture("missing_edge_candidate")
        self.addCleanup(temp_dir.cleanup)

        result = self._run_cli("--records", str(root / "records.jsonl"))

        self.assertEqual(11, result.returncode)
        summary = json.loads(result.stdout)
        self.assertFalse(summary["ok"])
        self.assertTrue(summary["errors"])

    def test_cli_duplicate_edge_ref_returns_artifact_exit_code(self) -> None:
        temp_dir, root = _copy_fixture("duplicate_edge_candidate")
        self.addCleanup(temp_dir.cleanup)

        result = self._run_cli("--records", str(root / "records.jsonl"))

        self.assertEqual(11, result.returncode)
        summary = json.loads(result.stdout)
        self.assertFalse(summary["ok"])
        self.assertTrue(summary["errors"])


if __name__ == "__main__":
    unittest.main()
