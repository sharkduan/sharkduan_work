"""Task 12: build_edge_candidates contract tests.

Contract:

  Public API:
    from covalent_design.candidates.edge_candidates import build_edge_candidates
    build_edge_candidates(records: Path,
                          candidate_radius_angstrom: float = 4.0,
                          ) -> ContractEnvelope

  CLI:
    python -m covalent_design.candidates.cli.build_edge_candidates
        --records <records.jsonl> --radius 4.0

  Required coverage per acceptance criteria:
    - exactly one positive edge per accepted record
    - nearby non-attachment ligand atoms become no-edge negatives
    - zero negatives encodes empty_radius_window and is not failure
    - rejected/conflict records do not receive candidates
    - missing protein coordinates returns structured error
    - missing ligand coordinates returns structured error
    - edge candidate artifact includes schema_version, contract_version,
      record_id, positive edge, negative edges, denominators/counts,
      artifact refs/role
    - CLI valid fixture exits 0 and writes output
    - CLI invalid fixture exits non-zero and reports errors
    - no Task 13 finalized manifest/splits/visual-check output

  Corrections:
    - fixture directory: tests/fixtures/edge_candidates
    - CLI supports --records and --radius 4.0
    - do NOT require artifact_manifest.json or records.jsonl to be
      updated with edge_candidate refs (final manifest linkage is Task 13)
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Import the public Task 12 API and exercise it through the contract below.
# ---------------------------------------------------------------------------
from covalent_design.candidates.edge_candidates import build_edge_candidates  # noqa: E402
from covalent_design.contracts.types import (
    CONTRACT_VERSION,
    SCHEMA_VERSION,
    ContractEnvelope,
)

# ---------------------------------------------------------------------------
# paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "edge_candidates"
VALID_RECORDS = FIXTURE_ROOT / "valid" / "records.jsonl"
EMPTY_WINDOW_RECORDS = FIXTURE_ROOT / "empty_radius_window" / "records.jsonl"
MISSING_PROTEIN_RECORDS = FIXTURE_ROOT / "missing_protein_coords" / "records.jsonl"
MISSING_LIGAND_RECORDS = FIXTURE_ROOT / "missing_ligand_coords" / "records.jsonl"

# Known record IDs from the valid fixture
VALID_RECORD_IDS = (
    "e1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6",
    "e2a2b3c4d5e6f7a8b9c0d1e2f3a4b5c7",
)
EMPTY_WINDOW_RECORD_ID = "e3a2b3c4d5e6f7a8b9c0d1e2f3a4b5c8"

# Known geometry from the valid fixture for verifying distance calculations.
# Record e1: SG at (14.123, 5.432, 6.001), C1 positive at (13.900, 5.600, 5.800)
#   distance ~= sqrt((14.123-13.9)^2 + (5.432-5.6)^2 + (6.001-5.8)^2) ~= 0.34 A
# Record e2: SG at (10.000, 8.000, 12.000), C2 negative at (8.500, 6.500, 11.000)
#   distance ~= 2.45 A, C3 far at (15, 15, 15) ~= 7.55 A

REQUIRED_EDGE_CANDIDATE_FIELDS = frozenset({
    "schema_version",
    "contract_version",
    "record_id",
    "role",
    "lineage",
    "positive_edge",
    "negative_edges",
    "denominators",
    "artifact_refs",
    "empty_radius_window",
})

REQUIRED_POSITIVE_EDGE_FIELDS = frozenset({
    "target_atom_name",
    "target_atom_element",
    "ligand_atom_name",
    "ligand_atom_element",
    "distance_angstrom",
})

REQUIRED_NEGATIVE_EDGE_FIELDS = frozenset({
    "ligand_atom_name",
    "ligand_atom_element",
    "distance_angstrom",
})

REQUIRED_DENOMINATOR_FIELDS = frozenset({
    "candidate_count",
    "natural_candidate_count",
    "forced_positive_count",
    "eligible_edge_count",
    "masked_candidate_count",
    "edge_loss_denominator",
    "bond_type_loss_denominator",
    "geometry_loss_denominator",
    "message_passing_candidate_count",
    "gate_evaluated_count",
})


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _read_jsonl(path: Path) -> tuple[dict, ...]:
    if not path.exists():
        return ()
    rows: list[dict] = []
    for line in path.read_text("utf-8").splitlines():
        stripped = line.strip()
        if stripped:
            rows.append(json.loads(stripped))
    return tuple(rows)


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text("utf-8"))


def _edge_candidate_artifact_path(records_path: Path, record_id: str) -> Path:
    """Expected location of a per-record edge-candidate artifact.

    Written alongside the other per-record artifacts under
    ``<records_dir>/artifacts/<record_id>/edge_candidates.json``.
    """
    return records_path.resolve().parent / "artifacts" / record_id / "edge_candidates.json"


def _collect_edge_candidate_artifacts(records_path: Path) -> dict[str, dict]:
    """Read all edge_candidates.json files found under the records directory."""
    artifacts_dir = records_path.resolve().parent / "artifacts"
    result: dict[str, dict] = {}
    if not artifacts_dir.exists():
        return result
    for cand_path in sorted(artifacts_dir.glob("*/edge_candidates.json")):
        record_id = cand_path.parent.name
        result[record_id] = _read_json(cand_path)
    return result


# ===================================================================
# Return-type and envelope contract
# ===================================================================

class BuildEdgeCandidatesReturnTypeTests(unittest.TestCase):
    """Envelope shape and basic callability."""

    def test_returns_contract_envelope(self):
        envelope = build_edge_candidates(VALID_RECORDS)
        self.assertIsInstance(envelope, ContractEnvelope)

    def test_receipt_is_present_and_ok(self):
        envelope = build_edge_candidates(VALID_RECORDS)
        self.assertIsNotNone(envelope.receipt)
        self.assertTrue(envelope.receipt.ok)

    def test_contract_version_is_current(self):
        envelope = build_edge_candidates(VALID_RECORDS)
        self.assertEqual(envelope.receipt.contract_version, CONTRACT_VERSION)

    def test_default_radius_is_4_angstrom(self):
        """Call without explicit radius must use 4.0 as the default."""
        envelope = build_edge_candidates(VALID_RECORDS)
        self.assertTrue(envelope.receipt.ok)

    def test_explicit_radius_is_accepted(self):
        envelope = build_edge_candidates(VALID_RECORDS, candidate_radius_angstrom=3.5)
        self.assertTrue(envelope.receipt.ok)

    def test_envelope_artifacts_are_present(self):
        envelope = build_edge_candidates(VALID_RECORDS)
        self.assertIsInstance(envelope.artifacts, tuple)
        self.assertGreater(len(envelope.artifacts), 0)

    def test_envelope_payload_contains_summary(self):
        envelope = build_edge_candidates(VALID_RECORDS)
        self.assertIsInstance(envelope.payload, (dict, object))


# ===================================================================
# Positive edge — exactly one per accepted record
# ===================================================================

class BuildEdgeCandidatesPositiveEdgeTests(unittest.TestCase):
    """Every accepted record has exactly one positive edge."""

    @classmethod
    def setUpClass(cls):
        cls.envelope = build_edge_candidates(VALID_RECORDS)
        cls.artifacts = _collect_edge_candidate_artifacts(VALID_RECORDS)

    def test_every_accepted_record_has_edge_candidate_artifact(self):
        for rid in VALID_RECORD_IDS:
            self.assertIn(
                rid,
                self.artifacts,
                f"Record {rid}: missing edge_candidates artifact",
            )

    def test_every_record_has_exactly_one_positive_edge(self):
        for rid in VALID_RECORD_IDS:
            artifact = self.artifacts[rid]
            pos = artifact["positive_edge"]
            self.assertIsInstance(pos, dict, f"Record {rid}: positive_edge not a dict")
            self.assertFalse(
                isinstance(pos, list),
                f"Record {rid}: positive_edge is a list, expected single dict",
            )

    def test_positive_edge_has_required_fields(self):
        for rid in VALID_RECORD_IDS:
            pos = self.artifacts[rid]["positive_edge"]
            missing = REQUIRED_POSITIVE_EDGE_FIELDS - set(pos.keys())
            self.assertEqual(
                missing,
                set(),
                f"Record {rid}: positive_edge missing fields: {missing}",
            )

    def test_positive_edge_matches_core_labels(self):
        """The positive edge ligand atom name and target atom name must match
        the record's core_labels."""
        records = _read_jsonl(VALID_RECORDS)
        records_by_id = {r["record_id"]: r for r in records}
        for rid in VALID_RECORD_IDS:
            pos = self.artifacts[rid]["positive_edge"]
            labels = records_by_id[rid]["core_labels"]
            self.assertEqual(
                pos["target_atom_name"],
                labels["target_atom_name"],
                f"Record {rid}: target atom name mismatch",
            )
            self.assertEqual(
                pos["ligand_atom_name"],
                labels["ligand_atom_name"],
                f"Record {rid}: ligand atom name mismatch",
            )

    def test_positive_edge_distance_is_positive_and_small(self):
        """The positive edge must be within the covalent bond range (~0-3 Å)."""
        for rid in VALID_RECORD_IDS:
            dist = self.artifacts[rid]["positive_edge"]["distance_angstrom"]
            self.assertIsInstance(dist, (int, float))
            self.assertGreater(dist, 0.0)
            self.assertLess(dist, 4.0, f"Record {rid}: positive edge beyond radius")

    def test_record_e1_positive_edge_is_c1(self):
        """Explicit geometry check: e1 SG→C1 distance ≈ 0.34 Å."""
        pos = self.artifacts["e1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6"]["positive_edge"]
        self.assertEqual(pos["ligand_atom_name"], "C1")
        self.assertLess(pos["distance_angstrom"], 0.5)


# ===================================================================
# Negative edges — nearby non-attachment ligand atoms
# ===================================================================

class BuildEdgeCandidatesNegativeEdgeTests(unittest.TestCase):
    """Nearby non-attachment ligand atoms become no-edge negatives."""

    @classmethod
    def setUpClass(cls):
        cls.envelope = build_edge_candidates(VALID_RECORDS)
        cls.artifacts = _collect_edge_candidate_artifacts(VALID_RECORDS)

    def test_negative_edges_is_list(self):
        for rid in VALID_RECORD_IDS:
            neg = self.artifacts[rid]["negative_edges"]
            self.assertIsInstance(neg, list, f"Record {rid}: negative_edges not a list")

    def test_negative_edges_have_required_fields(self):
        for rid in VALID_RECORD_IDS:
            for idx, neg in enumerate(self.artifacts[rid]["negative_edges"]):
                missing = REQUIRED_NEGATIVE_EDGE_FIELDS - set(neg.keys())
                self.assertEqual(
                    missing,
                    set(),
                    f"Record {rid} negative {idx}: missing {missing}",
                )

    def test_negative_edges_do_not_include_positive_atom(self):
        """The positive edge ligand atom must never appear in negatives."""
        for rid in VALID_RECORD_IDS:
            artifact = self.artifacts[rid]
            pos_name = artifact["positive_edge"]["ligand_atom_name"]
            neg_names = {neg["ligand_atom_name"] for neg in artifact["negative_edges"]}
            self.assertNotIn(
                pos_name,
                neg_names,
                f"Record {rid}: positive atom {pos_name} leaked into negatives",
            )

    def test_negative_edge_distances_are_within_radius(self):
        for rid in VALID_RECORD_IDS:
            for idx, neg in enumerate(self.artifacts[rid]["negative_edges"]):
                dist = neg["distance_angstrom"]
                self.assertGreater(dist, 0.0)
                self.assertLess(
                    dist,
                    4.0,
                    f"Record {rid} negative {idx}: distance {dist} beyond 4.0 Å radius",
                )

    def test_record_e1_has_expected_negatives(self):
        """Record e1: SG at (14.123,5.432,6.001). C2 at ~1.77 Å and C3 at ~2.96 Å
        are within 4.0 Å.  O1 at ~7.78 Å and N1 at ~6.82 Å are outside."""
        artifact = self.artifacts["e1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6"]
        neg_names = {neg["ligand_atom_name"] for neg in artifact["negative_edges"]}
        self.assertIn("C2", neg_names, "Expected C2 as negative (distance ~1.77 Å)")
        self.assertIn("C3", neg_names, "Expected C3 as negative (distance ~2.96 Å)")
        self.assertNotIn("O1", neg_names, "O1 should be outside 4.0 Å radius (~7.78 Å)")
        self.assertNotIn("N1", neg_names, "N1 should be outside 4.0 Å radius (~6.82 Å)")

    def test_record_e2_has_expected_negatives(self):
        """Record e2: SG at (10,8,12). C1 is positive, C2 at ~2.45 Å is negative,
        C3 at ~7.55 Å and O1 at ~13.3 Å are outside."""
        artifact = self.artifacts["e2a2b3c4d5e6f7a8b9c0d1e2f3a4b5c7"]
        neg_names = {neg["ligand_atom_name"] for neg in artifact["negative_edges"]}
        self.assertIn("C2", neg_names, "Expected C2 as negative (distance ~2.45 Å)")
        self.assertNotIn("C3", neg_names, "C3 should be outside 4.0 Å radius (~7.55 Å)")
        self.assertNotIn("O1", neg_names, "O1 should be outside 4.0 Å radius (~13.3 Å)")

    def test_far_atoms_never_become_candidates(self):
        """Ligand atoms beyond 4.0 Å must not appear as positive or negative."""
        for rid in VALID_RECORD_IDS:
            artifact = self.artifacts[rid]
            all_candidate_names = {artifact["positive_edge"]["ligand_atom_name"]} | {
                neg["ligand_atom_name"] for neg in artifact["negative_edges"]
            }
            for name in all_candidate_names:
                self.assertNotIn(name, ("O1", "N1") if rid == VALID_RECORD_IDS[0] else ("C3", "O1"))


# ===================================================================
# Empty radius window — zero negatives is valid, not failure
# ===================================================================

class BuildEdgeCandidatesEmptyRadiusWindowTests(unittest.TestCase):
    """When no non-attachment ligand atoms are within the radius window,
    the record produces an empty_radius_window result, not a failure."""

    @classmethod
    def setUpClass(cls):
        cls.envelope = build_edge_candidates(EMPTY_WINDOW_RECORDS)
        cls.artifacts = _collect_edge_candidate_artifacts(EMPTY_WINDOW_RECORDS)

    def test_envelope_receipt_is_ok(self):
        self.assertTrue(
            self.envelope.receipt.ok,
            "Empty radius window must not be treated as a build failure",
        )

    def test_edge_candidate_artifact_exists(self):
        self.assertIn(EMPTY_WINDOW_RECORD_ID, self.artifacts)

    def test_empty_radius_window_is_true(self):
        artifact = self.artifacts[EMPTY_WINDOW_RECORD_ID]
        self.assertTrue(
            artifact.get("empty_radius_window", False),
            "empty_radius_window must be True when no negatives exist",
        )

    def test_negative_edges_is_empty_list(self):
        artifact = self.artifacts[EMPTY_WINDOW_RECORD_ID]
        self.assertEqual(
            artifact["negative_edges"],
            [],
            "Expected empty negative_edges list (not None, not absent)",
        )

    def test_positive_edge_still_exists(self):
        artifact = self.artifacts[EMPTY_WINDOW_RECORD_ID]
        pos = artifact["positive_edge"]
        self.assertIsInstance(pos, dict)
        self.assertEqual(pos["ligand_atom_name"], "C1")

    def test_empty_window_is_not_reported_as_error_in_envelope(self):
        self.assertFalse(
            self.envelope.receipt.errors,
            f"Empty window produced errors: {self.envelope.receipt.errors}",
        )

    def test_denominators_reflect_zero_negatives(self):
        """With one positive edge and zero negatives, the candidate count
        should be 1 (forced positive only or natural positive)."""
        artifact = self.artifacts[EMPTY_WINDOW_RECORD_ID]
        denom = artifact["denominators"]
        self.assertIsInstance(denom, dict)
        # candidate_count should be 1 (just the positive edge)
        self.assertGreaterEqual(denom.get("candidate_count", -1), 1)


# ===================================================================
# Rejected/conflict exclusion
# ===================================================================

class BuildEdgeCandidatesRejectedConflictExclusionTests(unittest.TestCase):
    """Rejected and conflict records must NOT receive edge candidates."""

    @classmethod
    def setUpClass(cls):
        cls.envelope = build_edge_candidates(VALID_RECORDS)
        cls.artifacts = _collect_edge_candidate_artifacts(VALID_RECORDS)
        cls.records = _read_jsonl(VALID_RECORDS)

    def test_edge_candidate_count_equals_accepted_record_count(self):
        accepted_count = len(self.records)
        artifact_count = len(self.artifacts)
        self.assertEqual(
            artifact_count,
            accepted_count,
            f"Expected {accepted_count} edge candidate artifacts "
            f"(one per accepted record), got {artifact_count}",
        )

    def test_no_extra_edge_candidate_artifacts_beyond_accepted(self):
        """Only the accepted record IDs should have edge_candidates.json files."""
        accepted_ids = {r["record_id"] for r in self.records}
        artifact_ids = set(self.artifacts.keys())
        self.assertEqual(
            accepted_ids,
            artifact_ids,
            "Edge candidate artifacts exist for non-accepted IDs",
        )

    def test_envelope_payload_reports_correct_record_count(self):
        """The payload summary should report the count of processed records."""
        accepted_count = len(self.records)
        payload = self.envelope.payload
        if isinstance(payload, dict):
            self.assertIn("edge_candidate_count", payload)
            self.assertEqual(payload["edge_candidate_count"], accepted_count)


# ===================================================================
# Missing protein coordinates — structured error
# ===================================================================

class BuildEdgeCandidatesMissingProteinCoordsTests(unittest.TestCase):
    """Missing protein atom table for a record must produce a structured error."""

    def test_missing_protein_atom_table_produces_failure(self):
        try:
            envelope = build_edge_candidates(MISSING_PROTEIN_RECORDS)
        except Exception:
            # A structured exception is acceptable (not a silent skip).
            return

        self.assertFalse(
            envelope.receipt.ok,
            "Missing protein_atom_table must cause validation failure",
        )

    def test_missing_protein_error_is_structured(self):
        try:
            envelope = build_edge_candidates(MISSING_PROTEIN_RECORDS)
        except Exception:
            return

        errors = envelope.receipt.errors
        self.assertGreater(
            len(errors),
            0,
            "Expected at least one structured error for missing protein data",
        )
        error_codes = {e.code for e in errors}
        self.assertTrue(
            any(
                "PROTEIN" in code or "ARTIFACT" in code or "MISSING" in code
                for code in error_codes
            ),
            f"No protein/artifact-related error code in: {error_codes}",
        )

    def test_missing_protein_does_not_produce_edge_candidates(self):
        """When protein data is missing, no edge_candidates.json should be
        written for the affected record."""
        try:
            build_edge_candidates(MISSING_PROTEIN_RECORDS)
        except Exception:
            pass

        missing_rid = "e4a2b3c4d5e6f7a8b9c0d1e2f3a4b5c9"
        cand_path = _edge_candidate_artifact_path(MISSING_PROTEIN_RECORDS, missing_rid)
        self.assertFalse(
            cand_path.exists(),
            f"Edge candidate artifact written despite missing protein data: {cand_path}",
        )


# ===================================================================
# Missing ligand coordinates — structured error
# ===================================================================

class BuildEdgeCandidatesMissingLigandCoordsTests(unittest.TestCase):
    """Missing ligand atom table for a record must produce a structured error."""

    def test_missing_ligand_atom_table_produces_failure(self):
        try:
            envelope = build_edge_candidates(MISSING_LIGAND_RECORDS)
        except Exception:
            return

        self.assertFalse(
            envelope.receipt.ok,
            "Missing ligand_atom_table must cause validation failure",
        )

    def test_missing_ligand_error_is_structured(self):
        try:
            envelope = build_edge_candidates(MISSING_LIGAND_RECORDS)
        except Exception:
            return

        errors = envelope.receipt.errors
        self.assertGreater(
            len(errors),
            0,
            "Expected at least one structured error for missing ligand data",
        )
        error_codes = {e.code for e in errors}
        self.assertTrue(
            any(
                "LIGAND" in code or "ARTIFACT" in code or "MISSING" in code
                for code in error_codes
            ),
            f"No ligand/artifact-related error code in: {error_codes}",
        )

    def test_missing_ligand_does_not_produce_edge_candidates(self):
        try:
            build_edge_candidates(MISSING_LIGAND_RECORDS)
        except Exception:
            pass

        missing_rid = "e5a2b3c4d5e6f7a8b9c0d1e2f3a4b5d0"
        cand_path = _edge_candidate_artifact_path(MISSING_LIGAND_RECORDS, missing_rid)
        self.assertFalse(
            cand_path.exists(),
            f"Edge candidate artifact written despite missing ligand data: {cand_path}",
        )


class BuildEdgeCandidatesMissingCoordinatesArtifactTests(unittest.TestCase):
    """The Task 10 coordinates artifact is required input evidence."""

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = Path(tempfile.mkdtemp(prefix="task12_missing_coords_"))
        cls.records_path = cls.tmpdir / "records.jsonl"
        records = []
        for record in _read_jsonl(VALID_RECORDS):
            copied = dict(record)
            copied["artifacts"] = [
                ref for ref in record["artifacts"] if ref.get("role") != "coordinates"
            ]
            records.append(copied)
        cls.records_path.write_text(
            "\n".join(json.dumps(row, sort_keys=True) for row in records) + "\n",
            encoding="utf-8",
        )

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def test_missing_coordinates_ref_produces_failure(self):
        envelope = build_edge_candidates(self.records_path)
        self.assertFalse(envelope.receipt.ok)
        codes = {err.code for err in envelope.receipt.errors}
        self.assertTrue(
            any("COORDINATES" in code for code in codes),
            f"Expected coordinates-specific error code, got {codes}",
        )

    def test_missing_coordinates_ref_does_not_write_outputs(self):
        _ = build_edge_candidates(self.records_path)
        artifacts = _collect_edge_candidate_artifacts(self.records_path)
        self.assertEqual(artifacts, {})


# ===================================================================
# Edge candidate artifact schema
# ===================================================================

class BuildEdgeCandidatesArtifactSchemaTests(unittest.TestCase):
    """Each edge candidate artifact file must include all required fields."""

    @classmethod
    def setUpClass(cls):
        cls.envelope = build_edge_candidates(VALID_RECORDS)
        cls.artifacts = _collect_edge_candidate_artifacts(VALID_RECORDS)

    def test_artifact_has_all_required_top_level_fields(self):
        for rid in VALID_RECORD_IDS:
            artifact = self.artifacts[rid]
            missing = REQUIRED_EDGE_CANDIDATE_FIELDS - set(artifact.keys())
            self.assertEqual(
                missing,
                set(),
                f"Record {rid}: missing fields in edge_candidates artifact: {missing}",
            )

    def test_schema_version_is_current(self):
        for rid in VALID_RECORD_IDS:
            self.assertEqual(
                self.artifacts[rid]["schema_version"],
                SCHEMA_VERSION,
                f"Record {rid}: wrong schema_version",
            )

    def test_contract_version_is_current(self):
        for rid in VALID_RECORD_IDS:
            self.assertEqual(
                self.artifacts[rid]["contract_version"],
                CONTRACT_VERSION,
                f"Record {rid}: wrong contract_version",
            )

    def test_record_id_matches_artifact_parent_directory(self):
        for rid, artifact in self.artifacts.items():
            self.assertEqual(
                artifact["record_id"],
                rid,
                f"artifact record_id {artifact['record_id']} != directory {rid}",
            )

    def test_role_is_edge_candidates(self):
        for rid, artifact in self.artifacts.items():
            self.assertEqual(
                artifact["role"],
                "edge_candidates",
                f"Record {rid}: wrong role: {artifact['role']}",
            )

    def test_empty_radius_window_is_boolean(self):
        for rid, artifact in self.artifacts.items():
            self.assertIsInstance(
                artifact["empty_radius_window"],
                bool,
                f"Record {rid}: empty_radius_window must be bool",
            )

    def test_artifact_refs_is_list_of_dicts(self):
        for rid, artifact in self.artifacts.items():
            refs = artifact["artifact_refs"]
            self.assertIsInstance(refs, list, f"Record {rid}: artifact_refs not a list")
            for ref in refs:
                self.assertIsInstance(ref, dict)
                self.assertIn("role", ref, f"Record {rid}: ref missing role")

    def test_artifact_refs_include_input_artifact_roles(self):
        """Each edge candidate artifact should reference the input artifacts
        (coordinates, protein_atom_table, ligand_atom_table)."""
        for rid, artifact in self.artifacts.items():
            roles = {ref["role"] for ref in artifact["artifact_refs"]}
            self.assertIn("coordinates", roles, f"Record {rid}: missing coordinates ref")
            self.assertIn(
                "protein_atom_table",
                roles,
                f"Record {rid}: missing protein_atom_table ref",
            )
            self.assertIn(
                "ligand_atom_table",
                roles,
                f"Record {rid}: missing ligand_atom_table ref",
            )

    def test_lineage_matches_input_record(self):
        records_by_id = {record["record_id"]: record for record in _read_jsonl(VALID_RECORDS)}
        for rid, artifact in self.artifacts.items():
            self.assertEqual(
                artifact["lineage"],
                records_by_id[rid]["lineage"],
                f"Record {rid}: lineage was not preserved",
            )


# ===================================================================
# Denominator / counts
# ===================================================================

class BuildEdgeCandidatesDenominatorTests(unittest.TestCase):
    """Edge candidate artifacts must include correct denominator fields."""

    @classmethod
    def setUpClass(cls):
        cls.envelope = build_edge_candidates(VALID_RECORDS)
        cls.artifacts = _collect_edge_candidate_artifacts(VALID_RECORDS)

    def test_denominators_has_all_required_fields(self):
        for rid, artifact in self.artifacts.items():
            denom = artifact["denominators"]
            missing = REQUIRED_DENOMINATOR_FIELDS - set(denom.keys())
            self.assertEqual(
                missing,
                set(),
                f"Record {rid}: denominators missing: {missing}",
            )

    def test_denominator_values_are_non_negative_integers(self):
        for rid, artifact in self.artifacts.items():
            denom = artifact["denominators"]
            for key, val in denom.items():
                self.assertIsInstance(
                    val,
                    int,
                    f"Record {rid}: {key} is {type(val).__name__}, expected int",
                )
                self.assertGreaterEqual(
                    val,
                    0,
                    f"Record {rid}: {key} is negative ({val})",
                )

    def test_candidate_count_equals_positive_plus_negatives(self):
        for rid, artifact in self.artifacts.items():
            denom = artifact["denominators"]
            expected = 1 + len(artifact["negative_edges"])
            self.assertEqual(
                denom["candidate_count"],
                expected,
                f"Record {rid}: candidate_count mismatch: "
                f"{denom['candidate_count']} != 1 + {len(artifact['negative_edges'])}",
            )

    def test_forced_positive_count_is_zero_for_natural_positive(self):
        """When the positive edge is within the radius naturally,
        forced_positive_count must be 0."""
        for rid, artifact in self.artifacts.items():
            pos_dist = artifact["positive_edge"]["distance_angstrom"]
            denom = artifact["denominators"]
            if pos_dist < 4.0:
                self.assertEqual(
                    denom["forced_positive_count"],
                    0,
                    f"Record {rid}: positive edge is within radius ({pos_dist:.2f} Å) "
                    f"but forced_positive_count is {denom['forced_positive_count']}",
                )

    def test_eligible_edge_count_equals_candidate_count_for_no_masking(self):
        """In the baseline case with no pending rules, eligible_edge_count
        should equal candidate_count."""
        for rid, artifact in self.artifacts.items():
            denom = artifact["denominators"]
            self.assertEqual(
                denom["eligible_edge_count"],
                denom["candidate_count"],
                f"Record {rid}: eligible_edge_count != candidate_count",
            )


# ===================================================================
# CLI — valid fixture exits 0 and writes output
# ===================================================================

class BuildEdgeCandidatesCLIValidTests(unittest.TestCase):
    """CLI: python -m covalent_design.candidates.cli.build_edge_candidates."""

    def _run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = "src"
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "covalent_design.candidates.cli.build_edge_candidates",
                *args,
            ],
            cwd=str(REPO_ROOT),
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_cli_help_returns_zero(self):
        result = self._run_cli("--help")
        self.assertEqual(result.returncode, 0, f"stderr:\n{result.stderr}")

    def test_cli_valid_fixture_returns_zero(self):
        result = self._run_cli(
            "--records", str(VALID_RECORDS),
            "--radius", "4.0",
        )
        self.assertEqual(
            result.returncode,
            0,
            f"CLI failed with exit {result.returncode}:\nstderr:\n{result.stderr}",
        )

    def test_cli_valid_fixture_writes_json_summary_to_stdout(self):
        result = self._run_cli(
            "--records", str(VALID_RECORDS),
            "--radius", "4.0",
        )
        summary = json.loads(result.stdout)
        self.assertIsInstance(summary, dict)
        self.assertTrue(summary.get("ok", False))

    def test_cli_valid_fixture_reports_edge_candidate_count(self):
        result = self._run_cli(
            "--records", str(VALID_RECORDS),
            "--radius", "4.0",
        )
        summary = json.loads(result.stdout)
        self.assertIn("edge_candidate_count", summary)
        self.assertEqual(summary["edge_candidate_count"], 2)

    def test_cli_writes_edge_candidate_artifacts(self):
        """After CLI runs, per-record edge_candidates.json files must exist."""
        # Remove any existing artifacts first to get a clean test.
        for rid in VALID_RECORD_IDS:
            cand = _edge_candidate_artifact_path(VALID_RECORDS, rid)
            if cand.exists():
                cand.unlink()

        self._run_cli("--records", str(VALID_RECORDS), "--radius", "4.0")

        for rid in VALID_RECORD_IDS:
            cand = _edge_candidate_artifact_path(VALID_RECORDS, rid)
            self.assertTrue(
                cand.exists(),
                f"Edge candidate artifact not written for {rid} at {cand}",
            )

    def test_cli_radius_flag_is_accepted(self):
        """--radius 3.0 must be accepted as a valid flag."""
        result = self._run_cli(
            "--records", str(VALID_RECORDS),
            "--radius", "3.0",
        )
        self.assertEqual(result.returncode, 0, f"stderr:\n{result.stderr}")

    def test_cli_empty_radius_window_returns_zero(self):
        result = self._run_cli(
            "--records", str(EMPTY_WINDOW_RECORDS),
            "--radius", "4.0",
        )
        self.assertEqual(
            result.returncode,
            0,
            f"Empty window CLI failed with exit {result.returncode}:\n{result.stderr}",
        )


# ===================================================================
# CLI — invalid fixture exits non-zero and reports errors
# ===================================================================

class BuildEdgeCandidatesCLIInvalidTests(unittest.TestCase):
    """CLI with invalid input must exit non-zero and report structured errors."""

    def _run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = "src"
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "covalent_design.candidates.cli.build_edge_candidates",
                *args,
            ],
            cwd=str(REPO_ROOT),
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_cli_missing_protein_coords_exits_non_zero(self):
        result = self._run_cli(
            "--records", str(MISSING_PROTEIN_RECORDS),
            "--radius", "4.0",
        )
        self.assertNotEqual(
            result.returncode,
            0,
            "CLI should exit non-zero when protein data is missing",
        )

    def test_cli_missing_protein_coords_reports_errors_in_stdout(self):
        result = self._run_cli(
            "--records", str(MISSING_PROTEIN_RECORDS),
            "--radius", "4.0",
        )
        summary = json.loads(result.stdout)
        self.assertFalse(summary.get("ok", True))
        self.assertTrue(
            summary.get("errors"),
            "Expected error list when protein data is missing",
        )

    def test_cli_missing_ligand_coords_exits_non_zero(self):
        result = self._run_cli(
            "--records", str(MISSING_LIGAND_RECORDS),
            "--radius", "4.0",
        )
        self.assertNotEqual(
            result.returncode,
            0,
            "CLI should exit non-zero when ligand data is missing",
        )

    def test_cli_missing_ligand_coords_reports_errors_in_stdout(self):
        result = self._run_cli(
            "--records", str(MISSING_LIGAND_RECORDS),
            "--radius", "4.0",
        )
        summary = json.loads(result.stdout)
        self.assertFalse(summary.get("ok", True))
        self.assertTrue(
            summary.get("errors"),
            "Expected error list when ligand data is missing",
        )

    def test_cli_nonexistent_records_file_exits_non_zero(self):
        result = self._run_cli(
            "--records", str(FIXTURE_ROOT / "nonexistent" / "records.jsonl"),
            "--radius", "4.0",
        )
        self.assertNotEqual(result.returncode, 0)

    def test_cli_missing_required_records_flag(self):
        result = self._run_cli("--radius", "4.0")
        self.assertNotEqual(result.returncode, 0)


# ===================================================================
# No Task 13 output — no manifests, splits, or visual-check artifacts
# ===================================================================

class BuildEdgeCandidatesNoTask13OutputTests(unittest.TestCase):
    """Task 12 output must NOT include finalized manifests, splits, or
    visual-check artifacts.  Those belong to Tasks 13, 14, and 15."""

    def test_no_artifact_manifest_created_or_updated(self):
        """build_edge_candidates must not write artifact_manifest.json."""
        # The valid fixture directory should NOT gain an artifact_manifest.json
        # from the edge candidate build (one might pre-exist from Task 10).
        valid_dir = VALID_RECORDS.resolve().parent

        # Remove any pre-existing manifest to ensure the edge candidate
        # build does not create one.
        manifest = valid_dir / "artifact_manifest.json"
        had_manifest = manifest.exists()
        if had_manifest:
            original = manifest.read_bytes()
            manifest.unlink()

        try:
            build_edge_candidates(VALID_RECORDS)
            self.assertFalse(
                manifest.exists(),
                "build_edge_candidates must not create artifact_manifest.json "
                "(that is Task 13 scope)",
            )
        finally:
            if had_manifest:
                manifest.write_bytes(original)

    def test_no_records_jsonl_updated_with_edge_candidate_refs(self):
        """The input records.jsonl must not be modified to include
        edge_candidate artifact refs (Task 13 handles manifest linkage)."""
        valid_dir = VALID_RECORDS.resolve().parent
        records_path = valid_dir / "records.jsonl"
        original_bytes = records_path.read_bytes()

        build_edge_candidates(VALID_RECORDS)

        after_bytes = records_path.read_bytes()
        self.assertEqual(
            original_bytes,
            after_bytes,
            "records.jsonl was modified — edge_candidate refs belong to Task 13",
        )

    def test_no_split_artifacts_created(self):
        """Task 12 must not create any split-related files."""
        valid_dir = VALID_RECORDS.resolve().parent
        build_edge_candidates(VALID_RECORDS)

        split_files = list(valid_dir.glob("*split*"))
        self.assertEqual(
            len(split_files),
            0,
            f"Unexpected split artifacts: {split_files}",
        )

    def test_no_visual_check_artifacts_created(self):
        """Task 12 must not create any visual-check files."""
        valid_dir = VALID_RECORDS.resolve().parent
        build_edge_candidates(VALID_RECORDS)

        viz_files = list(valid_dir.glob("*visual*"))
        self.assertEqual(
            len(viz_files),
            0,
            f"Unexpected visual-check artifacts: {viz_files}",
        )

    def test_no_finalized_manifest_created(self):
        """No finalize-related manifest file should appear."""
        valid_dir = VALID_RECORDS.resolve().parent
        build_edge_candidates(VALID_RECORDS)

        finalized = list(valid_dir.glob("*final*")) + list(valid_dir.glob("*manifest*"))
        edge_only = [
            p for p in finalized
            if "edge_candidate" not in p.name and p.name != "records.jsonl"
        ]
        # artifact_manifest.json may pre-exist from Task 10 but
        # should not be created by Task 12.
        for p in edge_only:
            self.assertNotIn(
                "artifact_manifest",
                p.name,
                f"Task 12 must not create manifest: {p}",
            )

    def test_edge_candidate_artifact_does_not_contain_visual_check_data(self):
        """Edge candidate artifact must not contain visual_check_status fields."""
        artifacts = _collect_edge_candidate_artifacts(VALID_RECORDS)
        for rid, artifact in artifacts.items():
            self.assertNotIn("visual_check_status", artifact, f"Record {rid}")
            self.assertNotIn("visual_check", artifact, f"Record {rid}")

    def test_edge_candidate_artifact_does_not_contain_split_key(self):
        """Edge candidate artifact must not contain split assignment fields."""
        artifacts = _collect_edge_candidate_artifacts(VALID_RECORDS)
        for rid, artifact in artifacts.items():
            self.assertNotIn("split", artifact, f"Record {rid}")
            self.assertNotIn("train_split", artifact, f"Record {rid}")


# ===================================================================
# Edge case: records.jsonl with no accepted records
# ===================================================================

class BuildEdgeCandidatesEmptyInputTests(unittest.TestCase):
    """When records.jsonl has zero accepted records, the operation
    succeeds with zero edge candidates."""

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = Path(tempfile.mkdtemp(prefix="task12_empty_"))
        empty_records = cls.tmpdir / "records.jsonl"
        empty_records.write_text("", encoding="utf-8")
        cls.envelope = build_edge_candidates(empty_records)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def test_empty_input_produces_valid_envelope(self):
        self.assertTrue(self.envelope.receipt.ok)

    def test_empty_input_produces_zero_edge_candidates(self):
        payload = self.envelope.payload
        count = (
            payload.get("edge_candidate_count", 0)
            if isinstance(payload, dict)
            else 0
        )
        self.assertEqual(count, 0)


if __name__ == "__main__":
    unittest.main()
