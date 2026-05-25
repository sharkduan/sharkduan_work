"""Task 10: build_record_index contract tests."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from covalent_design.contracts import (
    CONTRACT_VERSION,
    SCHEMA_VERSION,
    ArtifactRef,
    ContractEnvelope,
)
from covalent_design.io.artifacts import sha256_file, validate_artifact_ref

# ---------------------------------------------------------------
# Import the public Task 10 API and exercise it through the contract below.
# ---------------------------------------------------------------
from covalent_design.data.records import build_record_index  # noqa: E402

# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "records"
VALID_ROOT = FIXTURE_ROOT / "valid"
MISSING_ARTIFACT_ROOT = FIXTURE_ROOT / "missing_artifact"

REQUIRED_ARTIFACT_ROLES = frozenset({
    "protein_atom_table",
    "ligand_atom_table",
    "ligand_bond_table",
    "coordinates",
})

RECORD_JSONL_FIELDS = frozenset({
    "schema_version",
    "contract_version",
    "record_id",
    "core_labels",
    "lineage",
    "metadata",
    "artifacts",
})

ARTIFACT_REF_FIELDS = frozenset({"uri", "sha256", "format", "bytes", "role"})


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _read_jsonl(path: Path) -> tuple[dict, ...]:
    """Read a JSONL file, returning a tuple of dict rows (empty lines skipped)."""
    if not path.exists():
        return ()
    rows: list[dict] = []
    for line in path.read_text("utf-8").splitlines():
        stripped = line.strip()
        if stripped:
            rows.append(json.loads(stripped))
    return tuple(rows)


def _sha256_jsonl(path: Path) -> str:
    """SHA-256 digest of the file's raw bytes (byte-level determinism check)."""
    return sha256_file(path)


# ---------------------------------------------------------------------------
# test cases
# ---------------------------------------------------------------------------

class BuildRecordIndexReturnTypeTests(unittest.TestCase):
    """Envelope and payload shape."""

    def test_returns_contract_envelope(self):
        envelope = build_record_index(VALID_ROOT)
        self.assertIsInstance(envelope, ContractEnvelope)

    def test_receipt_is_present_and_valid(self):
        envelope = build_record_index(VALID_ROOT)
        self.assertIsNotNone(envelope.receipt)
        self.assertTrue(envelope.receipt.ok)

    def test_schema_and_contract_versions_are_current(self):
        envelope = build_record_index(VALID_ROOT)
        self.assertEqual(envelope.receipt.contract_version, CONTRACT_VERSION)


class BuildRecordIndexCLITests(unittest.TestCase):
    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = "src"
        return subprocess.run(
            [sys.executable, "-m", "covalent_design.data.build_record_index", *args],
            cwd=Path(__file__).resolve().parents[2],
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_build_record_index_cli_help_returns_zero(self):
        result = self.run_cli("--help")

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_build_record_index_cli_valid_fixture_returns_json_summary(self):
        result = self.run_cli("--processed-root", str(VALID_ROOT))

        self.assertEqual(result.returncode, 0, result.stderr)
        summary = json.loads(result.stdout)
        self.assertTrue(summary["ok"])
        self.assertEqual(summary["record_count"], 2)
        self.assertEqual(summary["rejected_count"], 1)
        self.assertEqual(summary["conflict_count"], 1)

    def test_build_record_index_cli_missing_artifact_returns_non_zero(self):
        result = self.run_cli("--processed-root", str(MISSING_ARTIFACT_ROOT))

        self.assertNotEqual(result.returncode, 0)
        summary = json.loads(result.stdout)
        self.assertFalse(summary["ok"])
        self.assertTrue(summary["errors"])


class RecordsJsonlSchemaTests(unittest.TestCase):
    """``records.jsonl`` line-level schema."""

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = Path(tempfile.mkdtemp(prefix="task10_records_schema_"))
        cls.envelope = build_record_index(VALID_ROOT)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    @property
    def records_path(self) -> Path:
        # Output files are expected to be written under processed_root.
        return VALID_ROOT / "records.jsonl"

    def test_records_jsonl_exists(self):
        self.assertTrue(
            self.records_path.exists(),
            f"records.jsonl not found at {self.records_path}",
        )

    def test_every_row_has_required_top_level_fields(self):
        for idx, row in enumerate(_read_jsonl(self.records_path)):
            missing = RECORD_JSONL_FIELDS - set(row.keys())
            self.assertEqual(
                missing,
                set(),
                f"Row {idx} missing fields: {missing}",
            )

    def test_every_row_has_non_empty_record_id(self):
        for idx, row in enumerate(_read_jsonl(self.records_path)):
            self.assertIsInstance(row.get("record_id"), str)
            self.assertGreater(len(row["record_id"]), 0, f"Row {idx}: empty record_id")

    def test_schema_version_is_string(self):
        for idx, row in enumerate(_read_jsonl(self.records_path)):
            self.assertIsInstance(row.get("schema_version"), str, f"Row {idx}")

    def test_contract_version_is_string(self):
        for idx, row in enumerate(_read_jsonl(self.records_path)):
            self.assertIsInstance(row.get("contract_version"), str, f"Row {idx}")

    def test_lineage_is_present(self):
        for idx, row in enumerate(_read_jsonl(self.records_path)):
            self.assertIn("lineage", row, f"Row {idx}: missing lineage")
            self.assertIsInstance(row["lineage"], list, f"Row {idx}: lineage not a list")

    def test_metadata_is_present(self):
        for idx, row in enumerate(_read_jsonl(self.records_path)):
            self.assertIn("metadata", row, f"Row {idx}: missing metadata")
            self.assertIsInstance(row["metadata"], dict, f"Row {idx}")

    def test_core_labels_is_present(self):
        for idx, row in enumerate(_read_jsonl(self.records_path)):
            self.assertIn("core_labels", row, f"Row {idx}: missing core_labels")

    def test_core_labels_include_linkage_atom_fields(self):
        required = {
            "pdb_id",
            "residue_reaction_family",
            "target_atom_name",
            "target_atom_index",
            "ligand_atom_name",
            "ligand_atom_index",
            "ligand_atom_element",
        }
        for idx, row in enumerate(_read_jsonl(self.records_path)):
            labels = row["core_labels"]
            self.assertEqual(required - set(labels), set(), f"Row {idx}")

    def test_core_labels_include_ligand_atom_element_for_calibration(self):
        for idx, row in enumerate(_read_jsonl(self.records_path)):
            labels = row["core_labels"]
            self.assertIsInstance(labels["ligand_atom_element"], str, f"Row {idx}")
            self.assertGreater(len(labels["ligand_atom_element"]), 0, f"Row {idx}")

    def test_metadata_preserves_quality_gate_state(self):
        for idx, row in enumerate(_read_jsonl(self.records_path)):
            metadata = row["metadata"]
            self.assertIn("quality", metadata, f"Row {idx}: missing quality metadata")
            self.assertIn("first_core_eligible", metadata["quality"], f"Row {idx}")
            self.assertIn("quality_flags", metadata["quality"], f"Row {idx}")

    def test_artifacts_is_list_of_dicts(self):
        for idx, row in enumerate(_read_jsonl(self.records_path)):
            artifacts = row.get("artifacts")
            self.assertIsInstance(artifacts, list, f"Row {idx}")
            for art_idx, art in enumerate(artifacts):
                self.assertIsInstance(
                    art,
                    dict,
                    f"Row {idx} artifact {art_idx}",
                )


class ArtifactRefContractTests(unittest.TestCase):
    """Every ``ArtifactRef`` in ``records.jsonl`` must be externally verifiable."""

    @classmethod
    def setUpClass(cls):
        cls.envelope = build_record_index(VALID_ROOT)
        cls.records = _read_jsonl(VALID_ROOT / "records.jsonl")

    # ------------------------------------------------------------------
    # required roles
    # ------------------------------------------------------------------

    def test_every_record_has_all_required_artifact_roles(self):
        for idx, row in enumerate(self.records):
            roles_present = {art["role"] for art in row["artifacts"]}
            missing = REQUIRED_ARTIFACT_ROLES - roles_present
            self.assertEqual(
                missing,
                set(),
                f"Record {idx} (id={row.get('record_id')}): "
                f"missing artifact roles: {missing}",
            )

    def test_required_roles_are_exactly_four_per_record(self):
        for idx, row in enumerate(self.records):
            required_roles = {
                art["role"]
                for art in row["artifacts"]
                if art["role"] in REQUIRED_ARTIFACT_ROLES
            }
            self.assertEqual(
                len(required_roles),
                4,
                f"Record {idx}: expected 4 required roles, got {len(required_roles)}",
            )

    # ------------------------------------------------------------------
    # ArtifactRef field completeness
    # ------------------------------------------------------------------

    def test_every_artifact_ref_has_required_fields(self):
        for idx, row in enumerate(self.records):
            for art_idx, art in enumerate(row["artifacts"]):
                missing = ARTIFACT_REF_FIELDS - set(art.keys())
                self.assertEqual(
                    missing,
                    set(),
                    f"Record {idx} artifact {art_idx}: missing {missing}",
                )

    def test_uri_is_non_empty_relative_path(self):
        for idx, row in enumerate(self.records):
            for art_idx, art in enumerate(row["artifacts"]):
                uri = art["uri"]
                self.assertIsInstance(uri, str)
                self.assertGreater(len(uri), 0)
                self.assertNotIn(
                    "..",
                    Path(uri).parts,
                    f"Record {idx} artifact {art_idx}: uri must not escape root",
                )
                self.assertFalse(
                    Path(uri).is_absolute(),
                    f"Record {idx} artifact {art_idx}: uri must be relative",
                )

    def test_sha256_is_64_char_hex(self):
        for idx, row in enumerate(self.records):
            for art_idx, art in enumerate(row["artifacts"]):
                sha = art["sha256"]
                self.assertIsInstance(sha, str)
                self.assertEqual(len(sha), 64, f"Record {idx} artifact {art_idx}")
                self.assertTrue(
                    all(c in "0123456789abcdef" for c in sha),
                    f"Record {idx} artifact {art_idx}: non-hex sha256",
                )

    def test_format_is_non_empty(self):
        for idx, row in enumerate(self.records):
            for art_idx, art in enumerate(row["artifacts"]):
                fmt = art["format"]
                self.assertIsInstance(fmt, str)
                self.assertGreater(len(fmt), 0)

    def test_bytes_field_is_positive_integer(self):
        for idx, row in enumerate(self.records):
            for art_idx, art in enumerate(row["artifacts"]):
                nbytes = art["bytes"]
                self.assertIsInstance(nbytes, int)
                self.assertGreater(nbytes, 0, f"Record {idx} artifact {art_idx}")

    def test_role_is_non_empty_string(self):
        for idx, row in enumerate(self.records):
            for art_idx, art in enumerate(row["artifacts"]):
                role = art["role"]
                self.assertIsInstance(role, str)
                self.assertGreater(len(role), 0)

    # ------------------------------------------------------------------
    # external verification: every ArtifactRef must resolve and validate
    # ------------------------------------------------------------------

    def test_every_artifact_ref_validates_against_processed_root(self):
        for idx, row in enumerate(self.records):
            for art_idx, art in enumerate(row["artifacts"]):
                ref = ArtifactRef(
                    uri=art["uri"],
                    sha256=art["sha256"],
                    format=art["format"],
                    bytes=art["bytes"],
                    role=art["role"],
                )
                receipt = validate_artifact_ref(ref, root=VALID_ROOT)
                self.assertTrue(
                    receipt.ok,
                    f"Record {idx} artifact {art_idx} (role={art['role']}, "
                    f"uri={art['uri']}): {receipt.errors}",
                )

    # ------------------------------------------------------------------
    # no embeddings
    # ------------------------------------------------------------------

    def test_protein_atom_table_is_not_embedded_inline(self):
        for idx, row in enumerate(self.records):
            for art in row["artifacts"]:
                self.assertNotIn("atoms", art, f"Record {idx}: inline atom data found in ArtifactRef")
                self.assertNotIn("data", art, f"Record {idx}: inline data in ArtifactRef")

    def test_coordinates_artifact_has_uri_not_inline_content(self):
        for idx, row in enumerate(self.records):
            coord_arts = [art for art in row["artifacts"] if art["role"] == "coordinates"]
            for art in coord_arts:
                self.assertIn("uri", art)
                actual_path = VALID_ROOT / art["uri"]
                self.assertTrue(
                    actual_path.exists(),
                    f"Record {idx}: coordinates artifact missing at {actual_path}",
                )


class RejectedIndexSeparationTests(unittest.TestCase):
    """Rejected records must go to ``rejected_index.jsonl``, not ``records.jsonl``."""

    @classmethod
    def setUpClass(cls):
        cls.envelope = build_record_index(VALID_ROOT)
        cls.accepted_records = _read_jsonl(VALID_ROOT / "records.jsonl")
        cls.rejected_index = _read_jsonl(VALID_ROOT / "rejected_index.jsonl")

    def test_rejected_index_jsonl_exists(self):
        self.assertTrue(
            (VALID_ROOT / "rejected_index.jsonl").exists(),
            "rejected_index.jsonl not found",
        )

    def test_rejected_index_is_non_empty(self):
        self.assertGreater(len(self.rejected_index), 0)

    def test_rejected_record_ids_do_not_appear_in_records_jsonl(self):
        accepted_ids = {row["record_id"] for row in self.accepted_records}
        rejected_ids = {row.get("record_id") for row in self.rejected_index if row.get("record_id")}
        overlap = accepted_ids & rejected_ids
        self.assertEqual(
            overlap,
            set(),
            f"Rejected IDs leaked into accepted records: {overlap}",
        )

    def test_rejected_index_contains_source_lineage(self):
        for idx, row in enumerate(self.rejected_index):
            self.assertTrue(
                "lineage" in row or "source_lineage" in row,
                f"Rejected row {idx}: missing lineage info",
            )


class ConflictIndexSeparationTests(unittest.TestCase):
    """Conflicts must go to ``conflict_index.jsonl``, not ``records.jsonl``."""

    @classmethod
    def setUpClass(cls):
        cls.envelope = build_record_index(VALID_ROOT)
        cls.accepted_records = _read_jsonl(VALID_ROOT / "records.jsonl")
        cls.conflict_index = _read_jsonl(VALID_ROOT / "conflict_index.jsonl")

    def test_conflict_index_jsonl_exists(self):
        self.assertTrue(
            (VALID_ROOT / "conflict_index.jsonl").exists(),
            "conflict_index.jsonl not found",
        )

    def test_conflict_index_is_non_empty(self):
        self.assertGreater(len(self.conflict_index), 0)

    def test_conflict_entries_contain_conflict_group_id(self):
        for idx, row in enumerate(self.conflict_index):
            self.assertIn(
                "conflict_group_id",
                row,
                f"Conflict row {idx}: missing conflict_group_id",
            )

    def test_conflict_ids_do_not_appear_in_records_jsonl(self):
        accepted_ids = {row["record_id"] for row in self.accepted_records}
        conflict_ids = {
            row.get("conflict_group_id")
            for row in self.conflict_index
            if row.get("conflict_group_id")
        }
        overlap = accepted_ids & conflict_ids
        self.assertEqual(
            overlap,
            set(),
            f"Conflict IDs leaked into accepted records: {overlap}",
        )


class ArtifactManifestTests(unittest.TestCase):
    """``artifact_manifest.json`` contract."""

    @classmethod
    def setUpClass(cls):
        cls.envelope = build_record_index(VALID_ROOT)
        cls.manifest_path = VALID_ROOT / "artifact_manifest.json"
        cls.manifest = (
            json.loads(cls.manifest_path.read_text("utf-8"))
            if cls.manifest_path.exists()
            else None
        )

    def test_artifact_manifest_exists(self):
        self.assertIsNotNone(
            self.manifest,
            f"artifact_manifest.json not found at {self.manifest_path}",
        )

    def test_manifest_is_json_object_or_array(self):
        self.assertIsInstance(self.manifest, (dict, list))

    def test_manifest_references_all_records(self):
        records = _read_jsonl(VALID_ROOT / "records.jsonl")
        all_record_ids = {row["record_id"] for row in records}
        self.assertIsInstance(self.manifest, dict)
        self.assertTrue(all_record_ids.issubset(set(self.manifest.keys())))


class ByteDeterminismTests(unittest.TestCase):
    """Repeated runs must produce byte-identical output."""

    def test_two_runs_produce_identical_records_jsonl(self):
        build_record_index(VALID_ROOT)
        first_bytes = (VALID_ROOT / "records.jsonl").read_bytes()

        build_record_index(VALID_ROOT)
        second_bytes = (VALID_ROOT / "records.jsonl").read_bytes()
        self.assertEqual(
            hashlib.sha256(first_bytes).hexdigest(),
            hashlib.sha256(second_bytes).hexdigest(),
        )

    def test_two_runs_produce_identical_rejected_index(self):
        build_record_index(VALID_ROOT)
        first_sha = _sha256_jsonl(VALID_ROOT / "rejected_index.jsonl")

        build_record_index(VALID_ROOT)
        second_sha = _sha256_jsonl(VALID_ROOT / "rejected_index.jsonl")

        self.assertEqual(first_sha, second_sha)

    def test_two_runs_produce_identical_conflict_index(self):
        build_record_index(VALID_ROOT)
        first_sha = _sha256_jsonl(VALID_ROOT / "conflict_index.jsonl")

        build_record_index(VALID_ROOT)
        second_sha = _sha256_jsonl(VALID_ROOT / "conflict_index.jsonl")

        self.assertEqual(first_sha, second_sha)

    def test_two_runs_produce_identical_artifact_manifest(self):
        build_record_index(VALID_ROOT)
        first_sha = sha256_file(VALID_ROOT / "artifact_manifest.json")

        build_record_index(VALID_ROOT)
        second_sha = sha256_file(VALID_ROOT / "artifact_manifest.json")

        self.assertEqual(first_sha, second_sha)


class MissingArtifactFailureTests(unittest.TestCase):
    """Missing a required artifact must produce a validation failure or structured
    error - never a silent skip."""

    def test_missing_coordinates_artifact_produces_failure_not_silent(self):
        # This fixture has protein_atom_table, ligand_atom_table,
        # ligand_bond_table but NO coordinates artifact.
        try:
            envelope = build_record_index(MISSING_ARTIFACT_ROOT)
        except Exception:
            # A structured exception is also an acceptable failure mode
            # (just not a silent skip).
            return

        # If no exception is raised, the receipt/envelope must signal failure.
        self.assertFalse(
            envelope.receipt.ok,
            "Expected validation failure when a required artifact is missing, "
            "but receipt.ok is True (silent skip)",
        )

    def test_missing_artifact_error_is_not_generic(self):
        try:
            envelope = build_record_index(MISSING_ARTIFACT_ROOT)
        except Exception:
            return

        errors = envelope.receipt.errors
        self.assertGreater(
            len(errors),
            0,
            "Expected at least one structured error for missing artifact",
        )
        error_codes = {e.code for e in errors}
        self.assertTrue(
            any("ARTIFACT" in code or "MISSING" in code for code in error_codes),
            f"No artifact-related error code found in: {error_codes}",
        )

    def test_missing_artifact_does_not_produce_partial_records_jsonl(self):
        """When an artifact is missing, no half-baked records.jsonl should be written."""
        # Clean up any stale output before the run.
        stale = MISSING_ARTIFACT_ROOT / "records.jsonl"
        if stale.exists():
            stale.unlink()

        try:
            build_record_index(MISSING_ARTIFACT_ROOT)
        except Exception:
            pass

        if stale.exists():
            rows = _read_jsonl(stale)
            self.assertEqual(
                len(rows),
                0,
                "records.jsonl should be empty or absent when a required "
                "artifact is missing",
            )


class NoEdgeCandidatesTests(unittest.TestCase):
    """Task 10 output must NOT generate edge_candidates (that's a later task)."""

    @classmethod
    def setUpClass(cls):
        cls.envelope = build_record_index(VALID_ROOT)

    def test_records_jsonl_has_no_edge_candidates_field(self):
        for idx, row in enumerate(_read_jsonl(VALID_ROOT / "records.jsonl")):
            self.assertNotIn(
                "edge_candidates",
                row,
                f"Row {idx}: edge_candidates field found (belongs to a later task)",
            )

    def test_artifact_manifest_has_no_edge_artifacts(self):
        manifest_path = VALID_ROOT / "artifact_manifest.json"
        if not manifest_path.exists():
            return
        manifest = json.loads(manifest_path.read_text("utf-8"))
        manifest_str = json.dumps(manifest)
        self.assertNotIn("edge_candidate", manifest_str.lower())
        self.assertNotIn("edge_candidates", manifest_str.lower())

    def test_no_edge_related_artifact_roles_in_records(self):
        for idx, row in enumerate(_read_jsonl(VALID_ROOT / "records.jsonl")):
            for art in row.get("artifacts", []):
                role = art.get("role", "")
                self.assertNotIn(
                    "edge",
                    role.lower(),
                    f"Record {idx}: edge-related artifact role: {role}",
                )


class EmptyProcessedRootEdgeCaseTests(unittest.TestCase):
    """Edge case: processed_root with no accepted records."""

    @classmethod
    def setUpClass(cls):
        cls.empty_root = Path(tempfile.mkdtemp(prefix="task10_empty_"))
        (cls.empty_root / "accepted.jsonl").write_text("", encoding="utf-8")
        (cls.empty_root / "rejected.jsonl").write_text("", encoding="utf-8")
        (cls.empty_root / "conflicts.jsonl").write_text("", encoding="utf-8")
        cls.envelope = build_record_index(cls.empty_root)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.empty_root, ignore_errors=True)

    def test_empty_input_produces_valid_envelope(self):
        self.assertIsInstance(self.envelope, ContractEnvelope)

    def test_empty_input_produces_empty_or_minimal_records_jsonl(self):
        records = _read_jsonl(self.empty_root / "records.jsonl")
        self.assertEqual(len(records), 0)

    def test_empty_input_produces_empty_rejected_index(self):
        rejected = _read_jsonl(self.empty_root / "rejected_index.jsonl")
        self.assertEqual(len(rejected), 0)

    def test_empty_input_produces_empty_conflict_index(self):
        conflicts = _read_jsonl(self.empty_root / "conflict_index.jsonl")
        self.assertEqual(len(conflicts), 0)


if __name__ == "__main__":
    unittest.main()
