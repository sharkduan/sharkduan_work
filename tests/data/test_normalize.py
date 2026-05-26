import importlib
import json
import sys
import unittest
from pathlib import Path

from covalent_design.contracts import (
    ContractEnvelope,
    LigandAtomIdentity,
    ProteinAtomIdentity,
    SourceIngestRecord,
    SourceRecordLineage,
    ValidationReceipt,
)
from covalent_design.data import resolve_identities
from covalent_design.data.conflicts import ConflictGroup
from covalent_design.data.ingest import ingest_source


FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "normalize"
INGEST_FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures"


def _record_from_fixture(name):
    payload = json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))
    lineage = SourceRecordLineage(
        source_database=payload["source_database"],
        source_version=payload["source_version"],
        source_record_id=payload["source_record_id"],
        raw_manifest_file="normalize-fixture-manifest.json",
        raw_file_path=str(FIXTURE_ROOT / name),
        raw_file_sha256="fixture-sha256",
        row_index=payload["row_index"],
    )
    target = payload["target_atom"]
    ligand = payload["ligand_atom"]
    return SourceIngestRecord(
        source_database=payload["source_database"],
        source_version=payload["source_version"],
        source_record_id=payload["source_record_id"],
        raw_manifest_file=lineage.raw_manifest_file,
        raw_file_path=lineage.raw_file_path,
        raw_file_sha256=lineage.raw_file_sha256,
        row_index=lineage.row_index,
        lineage={},
        protein={
            "pdb_id": payload["pdb_id"],
            "resolution_angstrom": payload["quality"]["resolution_angstrom"],
        },
        ligand={"ligand_id": ligand["ligand_id"]},
        linkage=payload["linkage"],
        metadata={
            "atom_mapping": payload.get("atom_mapping"),
            "quality_flags": tuple(payload["quality"].get("flags", [])),
        },
        source_lineage=lineage,
        target_atom_identity=ProteinAtomIdentity(**target),
        ligand_atom_identity=LigandAtomIdentity(**ligand),
    )


def _normalize(*fixture_names):
    from covalent_design.data.normalize import normalize_linkages

    records = tuple(_record_from_fixture(name) for name in fixture_names)
    return normalize_linkages(records)


class NormalizeLinkageTests(unittest.TestCase):
    def test_valid_source_record_converts_to_normalized_linkage_record(self):
        envelope = _normalize("clean_record.json")

        self.assertIsInstance(envelope, ContractEnvelope)
        self.assertIsInstance(envelope.receipt, ValidationReceipt)
        self.assertTrue(envelope.receipt.ok)
        self.assertEqual(envelope.payload.counts["accepted"], 1)
        self.assertEqual(envelope.payload.counts["rejected"], 0)

        accepted = envelope.payload.accepted[0]
        normalized = accepted.normalized
        self.assertEqual(normalized.pdb_id, "1abc")
        self.assertEqual(normalized.residue_reaction_family, "CYS_MICHAEL_ADDITION")
        self.assertNotEqual(normalized.record_id, "clean-1")
        self.assertTrue(accepted.gate_result.first_core_eligible)

    def test_normalized_record_preserves_source_lineage(self):
        envelope = _normalize("clean_record.json")

        lineage = envelope.payload.accepted[0].normalized.source_lineage
        self.assertEqual(lineage.source_database, "covbinder_in_pdb")
        self.assertEqual(lineage.source_record_id, "clean-1")
        self.assertEqual(lineage.row_index, 0)
        lineage_ids = {
            item.source_record_id
            for item in envelope.payload.accepted[0].normalized.source_lineages
        }
        self.assertEqual(lineage_ids, {"clean-1"})

    def test_atom_mapping_is_explicit_not_implied_by_source_row(self):
        envelope = _normalize("clean_record.json")

        mapping = envelope.payload.accepted[0].normalized.atom_mapping
        self.assertEqual(mapping.target_atom_index, 10)
        self.assertEqual(mapping.ligand_atom_index, 3)
        self.assertEqual(mapping.target_atom_name, "SG")
        self.assertEqual(mapping.ligand_atom_name, "C1")
        self.assertTrue(mapping.mapping_verified)

    def test_q0_missing_atom_mapping_is_hard_rejected_with_lineage(self):
        envelope = _normalize("q0_missing_atom_mapping.json")

        self.assertEqual(envelope.payload.counts["accepted"], 0)
        self.assertEqual(envelope.payload.counts["rejected"], 1)
        rejected = envelope.payload.rejected[0]
        self.assertEqual(rejected.gate_result.quality_tier, "Q0")
        self.assertFalse(rejected.gate_result.first_core_eligible)
        self.assertIn("ATOM_MAPPING_MISSING", rejected.gate_result.reasons)
        self.assertEqual(
            rejected.normalized.source_lineage.source_record_id,
            "q0-mapping",
        )

    def test_q0_unverified_atom_mapping_is_hard_rejected(self):
        envelope = _normalize("q0_unverified_atom_mapping.json")

        self.assertEqual(envelope.payload.counts["accepted"], 0)
        rejected = envelope.payload.rejected[0]
        self.assertEqual(rejected.gate_result.quality_tier, "Q0")
        self.assertFalse(rejected.gate_result.first_core_eligible)
        self.assertIn("ATOM_MAPPING_UNVERIFIED", rejected.gate_result.reasons)
        self.assertFalse(rejected.normalized.atom_mapping.mapping_verified)

    def test_q1_resolution_issue_is_rejected_with_reason(self):
        envelope = _normalize("q1_resolution_outlier.json")

        self.assertEqual(envelope.payload.counts["accepted"], 0)
        rejected = envelope.payload.rejected[0]
        self.assertEqual(rejected.gate_result.quality_tier, "Q1")
        self.assertFalse(rejected.gate_result.first_core_eligible)
        self.assertIn("RESOLUTION_GT_3A", rejected.gate_result.reasons)

    def test_q2_record_is_kept_with_flag_but_not_first_core_eligible(self):
        envelope = _normalize("q2_non_human.json")

        self.assertEqual(envelope.payload.counts["accepted"], 1)
        self.assertEqual(envelope.payload.counts["rejected"], 0)
        accepted = envelope.payload.accepted[0]
        self.assertEqual(accepted.gate_result.quality_tier, "Q2")
        self.assertIn("non_human_protein", accepted.gate_result.flags)
        self.assertFalse(accepted.gate_result.first_core_eligible)

    def test_general_q2_flags_are_kept_but_not_first_core_eligible(self):
        envelope = _normalize("q2_missing_activity.json")

        self.assertEqual(envelope.payload.counts["accepted"], 1)
        accepted = envelope.payload.accepted[0]
        self.assertEqual(accepted.gate_result.quality_tier, "Q2")
        self.assertIn("missing_activity_data", accepted.gate_result.flags)
        self.assertIn("missing_assay_data", accepted.gate_result.flags)
        self.assertFalse(accepted.gate_result.first_core_eligible)

    def test_unsupported_residue_reaction_family_is_q0_rejected(self):
        envelope = _normalize("q0_unsupported_family.json")

        self.assertEqual(envelope.payload.counts["accepted"], 0)
        rejected = envelope.payload.rejected[0]
        self.assertEqual(rejected.gate_result.quality_tier, "Q0")
        self.assertIn(
            "UNSUPPORTED_RESIDUE_REACTION_FAMILY",
            rejected.gate_result.reasons,
        )

    def test_multi_linkage_record_is_rejected_for_v1_first_core(self):
        envelope = _normalize("q0_multi_linkage.json")

        self.assertEqual(envelope.payload.counts["accepted"], 0)
        rejected = envelope.payload.rejected[0]
        self.assertEqual(rejected.gate_result.quality_tier, "Q0")
        self.assertIn("MULTI_LINKAGE_V1_REJECT", rejected.gate_result.reasons)

    def test_accepted_and_rejected_counts_are_reproducible(self):
        fixtures = (
            "clean_record.json",
            "q2_non_human.json",
            "q0_missing_atom_mapping.json",
            "q1_resolution_outlier.json",
            "q0_multi_linkage.json",
        )

        first = _normalize(*fixtures).payload.counts
        second = _normalize(*fixtures).payload.counts

        self.assertEqual(first, second)
        self.assertEqual(first["accepted"], 2)
        self.assertEqual(first["rejected"], 3)

    def test_rejected_records_keep_reason_and_source_lineage(self):
        envelope = _normalize("q1_resolution_outlier.json")
        rejected = envelope.payload.rejected[0]

        self.assertEqual(rejected.reason, "RESOLUTION_GT_3A")
        self.assertEqual(rejected.normalized.source_lineage.source_database, "covpdb")
        self.assertEqual(
            rejected.normalized.source_lineage.source_record_id,
            "q1-resolution",
        )

    def test_normalization_modules_do_not_import_heavy_chemistry_dependencies(self):
        importlib.import_module("covalent_design.data.normalize")
        importlib.import_module("covalent_design.data.quality")

        for module_name in ("rdkit", "openbabel", "MDAnalysis"):
            self.assertNotIn(module_name, sys.modules)


class IdentityResolutionIntegrationTests(unittest.TestCase):
    """Identity resolution: duplicate merge and conflict detection."""

    def test_duplicate_records_merge_to_single_merged_identity(self):
        result = resolve_identities((
            _record_from_fixture("duplicate_a.json"),
            _record_from_fixture("duplicate_b.json"),
        ))

        self.assertEqual(len(result.merged_records), 1)
        self.assertEqual(len(result.conflict_groups), 0)
        self.assertEqual(len(result.rejected_inputs), 0)

    def test_merged_duplicate_record_has_combined_lineage(self):
        result = resolve_identities((
            _record_from_fixture("duplicate_a.json"),
            _record_from_fixture("duplicate_b.json"),
        ))

        merged = result.merged_records[0]
        self.assertEqual(len(merged.lineage), 2)
        source_ids = {lineage.source_record_id for lineage in merged.lineage}
        self.assertEqual(source_ids, {"dup-a", "dup-b"})

    def test_merged_duplicate_preferred_annotations_from_highest_priority_source(self):
        result = resolve_identities((
            _record_from_fixture("duplicate_a.json"),
            _record_from_fixture("duplicate_b.json"),
        ))

        merged = result.merged_records[0]
        self.assertIn("atom_mapping", merged.preferred_annotations)

    def test_conflict_group_produced_when_same_anchor_different_identity(self):
        result = resolve_identities((
            _record_from_fixture("conflict_a.json"),
            _record_from_fixture("conflict_b.json"),
        ))

        self.assertEqual(len(result.conflict_groups), 1)
        self.assertEqual(len(result.merged_records), 0)
        self.assertIsInstance(result.conflict_groups[0], ConflictGroup)
        self.assertEqual(
            result.conflict_groups[0].reason,
            "LINKAGE_IDENTITY_CONFLICT",
        )

    def test_conflict_group_lineage_contains_both_source_record_ids(self):
        result = resolve_identities((
            _record_from_fixture("conflict_a.json"),
            _record_from_fixture("conflict_b.json"),
        ))

        group = result.conflict_groups[0]
        source_ids = {lineage.source_record_id for lineage in group.lineage}
        self.assertEqual(source_ids, {"conflict-a", "conflict-b"})

    def test_conflict_group_contains_two_distinct_identities(self):
        result = resolve_identities((
            _record_from_fixture("conflict_a.json"),
            _record_from_fixture("conflict_b.json"),
        ))

        group = result.conflict_groups[0]
        self.assertEqual(len(group.conflicting_identities), 2)

    def test_accepted_merged_set_contains_correct_source_record_ids(self):
        result = resolve_identities((
            _record_from_fixture("clean_record.json"),
            _record_from_fixture("duplicate_a.json"),
            _record_from_fixture("duplicate_b.json"),
        ))

        all_lineage_ids: set[str] = set()
        for merged in result.merged_records:
            for lineage in merged.lineage:
                all_lineage_ids.add(lineage.source_record_id)
        self.assertIn("clean-1", all_lineage_ids)
        self.assertIn("dup-a", all_lineage_ids)
        self.assertIn("dup-b", all_lineage_ids)
        self.assertEqual(len(result.merged_records), 2)

    def test_reject_identity_input_with_missing_critical_fields(self):
        bad_record = SourceIngestRecord(
            source_database="covpdb",
            source_version="v1",
            source_record_id="bad-1",
            raw_manifest_file="m.json",
            raw_file_path="f.json",
            raw_file_sha256="abc",
            row_index=0,
            lineage={},
            protein={"pdb_id": "bad1"},
            ligand={},
            linkage={},
            metadata={},
            source_lineage=SourceRecordLineage(
                source_database="covpdb",
                source_version="v1",
                source_record_id="bad-1",
                raw_manifest_file="m.json",
                raw_file_path="f.json",
                raw_file_sha256="abc",
                row_index=0,
            ),
            target_atom_identity=ProteinAtomIdentity(
                chain_id="A",
                residue_number=None,
                residue_name="",
                atom_name="",
            ),
            ligand_atom_identity=None,
        )

        result = resolve_identities((bad_record,))

        self.assertEqual(len(result.rejected_inputs), 1)
        rejected = result.rejected_inputs[0]
        self.assertEqual(rejected.reason, "IDENTITY_CRITICAL_FIELD_MISSING")
        self.assertEqual(
            rejected.source_lineage.source_record_id, "bad-1",
        )

    def test_rejected_input_has_missing_fields_list(self):
        bad_record = SourceIngestRecord(
            source_database="covpdb",
            source_version="v1",
            source_record_id="bad-2",
            raw_manifest_file="m.json",
            raw_file_path="f.json",
            raw_file_sha256="abc",
            row_index=0,
            lineage={},
            protein={"pdb_id": "bad2"},
            ligand={},
            linkage={},
            metadata={},
            source_lineage=SourceRecordLineage(
                source_database="covpdb",
                source_version="v1",
                source_record_id="bad-2",
                raw_manifest_file="m.json",
                raw_file_path="f.json",
                raw_file_sha256="abc",
                row_index=0,
            ),
            target_atom_identity=ProteinAtomIdentity(
                chain_id="A",
                residue_number=None,
                residue_name="",
                atom_name="",
            ),
            ligand_atom_identity=None,
        )

        result = resolve_identities((bad_record,))

        rejected = result.rejected_inputs[0]
        self.assertIn("ligand_atom_identity", rejected.missing_fields)
        self.assertIn("residue_reaction_family", rejected.missing_fields)


class IngestToNormalizeIntegrationTests(unittest.TestCase):
    """End-to-end: identity resolution feeds into normalization acceptance."""

    def test_duplicate_merged_records_count_matches_normalize_accepted(self):
        from covalent_design.data.normalize import normalize_with_identity_resolution

        records = (
            _record_from_fixture("clean_record.json"),
            _record_from_fixture("duplicate_a.json"),
            _record_from_fixture("duplicate_b.json"),
        )
        identity_result = resolve_identities(records)

        self.assertEqual(len(identity_result.merged_records), 2)
        self.assertEqual(len(identity_result.conflict_groups), 0)

        normalize_envelope = normalize_with_identity_resolution(records)
        self.assertEqual(normalize_envelope.payload.counts["accepted"], 2)
        self.assertEqual(normalize_envelope.payload.counts["rejected"], 0)
        self.assertEqual(normalize_envelope.payload.counts["conflicts"], 0)

        merged = [
            accepted for accepted in normalize_envelope.payload.accepted
            if {
                lineage.source_record_id
                for lineage in accepted.normalized.source_lineages
            } == {"dup-a", "dup-b"}
        ]
        self.assertEqual(len(merged), 1)

    def test_conflict_group_not_entering_accepted_normalized_output(self):
        from covalent_design.data.normalize import normalize_with_identity_resolution

        records = (
            _record_from_fixture("conflict_a.json"),
            _record_from_fixture("conflict_b.json"),
        )
        identity_result = resolve_identities(records)

        self.assertEqual(len(identity_result.conflict_groups), 1)
        self.assertEqual(len(identity_result.merged_records), 0)

        conflict_lineage_ids = {
            lineage.source_record_id
            for group in identity_result.conflict_groups
            for lineage in group.lineage
        }
        self.assertEqual(conflict_lineage_ids, {"conflict-a", "conflict-b"})

        self.assertNotIn("conflict-a", {
            lineage.source_record_id
            for merged in identity_result.merged_records
            for lineage in merged.lineage
        })
        self.assertNotIn("conflict-b", {
            lineage.source_record_id
            for merged in identity_result.merged_records
            for lineage in merged.lineage
        })

        normalize_envelope = normalize_with_identity_resolution(records)
        self.assertEqual(normalize_envelope.payload.counts["accepted"], 0)
        self.assertEqual(normalize_envelope.payload.counts["rejected"], 0)
        self.assertEqual(normalize_envelope.payload.counts["conflicts"], 1)
        conflict_ids = {
            lineage.source_record_id
            for group in normalize_envelope.payload.conflicts
            for lineage in group.lineage
        }
        self.assertEqual(conflict_ids, {"conflict-a", "conflict-b"})

    def test_normalize_payload_exposes_rejected_identity_inputs(self):
        from covalent_design.data.normalize import normalize_with_identity_resolution

        bad_record = SourceIngestRecord(
            source_database="covpdb",
            source_version="v1",
            source_record_id="bad-normalize",
            raw_manifest_file="m.json",
            raw_file_path="f.json",
            raw_file_sha256="abc",
            row_index=0,
            lineage={},
            protein={"pdb_id": "bad-normalize"},
            ligand={},
            linkage={},
            metadata={},
            source_lineage=SourceRecordLineage(
                source_database="covpdb",
                source_version="v1",
                source_record_id="bad-normalize",
                raw_manifest_file="m.json",
                raw_file_path="f.json",
                raw_file_sha256="abc",
                row_index=0,
            ),
            target_atom_identity=ProteinAtomIdentity(
                chain_id="A",
                residue_number=None,
                residue_name="",
                atom_name="",
            ),
            ligand_atom_identity=None,
        )

        envelope = normalize_with_identity_resolution((bad_record,))

        self.assertEqual(envelope.payload.counts["accepted"], 0)
        self.assertEqual(envelope.payload.counts["rejected"], 0)
        self.assertEqual(envelope.payload.counts["rejected_identity_inputs"], 1)
        self.assertEqual(
            envelope.payload.rejected_identity_inputs[0].source_lineage.source_record_id,
            "bad-normalize",
        )

    def test_csv_ingest_outputs_flow_into_identity_normalization_seam(self):
        from covalent_design.data.normalize import normalize_with_identity_resolution

        records = []
        for source, fixture_dir in (
            ("covbinder_in_pdb", INGEST_FIXTURE_ROOT / "covbinder" / "valid"),
            ("covpdb", INGEST_FIXTURE_ROOT / "covpdb" / "valid"),
            ("covalentin_db", INGEST_FIXTURE_ROOT / "covalentin_db" / "valid"),
        ):
            ingest_envelope = ingest_source(source, fixture_dir)
            self.assertTrue(ingest_envelope.receipt.ok)
            self.assertGreaterEqual(len(ingest_envelope.payload.records), 2)
            records.extend(ingest_envelope.payload.records[:2])

        normalize_envelope = normalize_with_identity_resolution(tuple(records))

        self.assertTrue(normalize_envelope.receipt.ok)
        self.assertEqual(
            normalize_envelope.payload.counts,
            {
                "accepted": 0,
                "rejected": 2,
                "conflicts": 0,
                "rejected_identity_inputs": 2,
            },
        )
        rejected_lineage_sets = {
            tuple(lineage.source_database for lineage in rejected.normalized.source_lineages)
            for rejected in normalize_envelope.payload.rejected
        }
        self.assertEqual(rejected_lineage_sets, {("covbinder_in_pdb", "covpdb")})
        rejected_identity_sources = {
            rejected.source_lineage.source_database
            for rejected in normalize_envelope.payload.rejected_identity_inputs
        }
        self.assertEqual(rejected_identity_sources, {"covalentin_db"})


    def test_normalized_record_preserves_bond_type(self) -> None:
        envelope = _normalize("clean_record.json")

        normalized = envelope.payload.accepted[0].normalized
        self.assertEqual(normalized.bond_type, "single")

    def test_normalized_record_has_explicit_empty_warhead_type_when_unavailable(self) -> None:
        envelope = _normalize("clean_record.json")

        normalized = envelope.payload.accepted[0].normalized
        self.assertEqual(normalized.warhead_type, "")


class QualityGateEdgeCaseTests(unittest.TestCase):
    """Q0/Q1/Q2 routing edge cases."""

    def test_q0_flag_quality_flag_triggers_rejection(self):
        envelope = _normalize("q0_flag_missing_ligand.json")

        self.assertEqual(envelope.payload.counts["accepted"], 0)
        self.assertEqual(envelope.payload.counts["rejected"], 1)
        rejected = envelope.payload.rejected[0]
        self.assertEqual(rejected.gate_result.quality_tier, "Q0")
        self.assertIn("MISSING_LIGAND_COORDINATES", rejected.gate_result.reasons)

    def test_q1_flag_quality_flag_triggers_rejection(self):
        envelope = _normalize("q1_flag_extreme_bond.json")

        self.assertEqual(envelope.payload.counts["accepted"], 0)
        self.assertEqual(envelope.payload.counts["rejected"], 1)
        rejected = envelope.payload.rejected[0]
        self.assertEqual(rejected.gate_result.quality_tier, "Q1")
        self.assertIn("EXTREME_BOND_LENGTH_OUTLIER", rejected.gate_result.reasons)

    def test_q0_takes_precedence_over_q1_when_both_conditions_present(self):
        envelope = _normalize("q0_over_q1.json")

        self.assertEqual(envelope.payload.counts["accepted"], 0)
        self.assertEqual(envelope.payload.counts["rejected"], 1)
        rejected = envelope.payload.rejected[0]
        self.assertEqual(rejected.gate_result.quality_tier, "Q0")
        self.assertIn("ATOM_MAPPING_UNVERIFIED", rejected.gate_result.reasons)
        self.assertNotIn("RESOLUTION_GT_3A", rejected.gate_result.reasons)

    def test_clean_record_has_empty_quality_tier_and_is_first_core_eligible(self):
        envelope = _normalize("clean_record.json")

        accepted = envelope.payload.accepted[0]
        self.assertEqual(accepted.gate_result.quality_tier, "")
        self.assertTrue(accepted.gate_result.first_core_eligible)

    def test_accepted_set_source_record_ids_are_correct(self):
        fixtures = (
            "clean_record.json",
            "q2_non_human.json",
            "q2_missing_activity.json",
        )

        envelope = _normalize(*fixtures)

        accepted_source_ids = {
            accepted.normalized.source_lineage.source_record_id
            for accepted in envelope.payload.accepted
        }
        self.assertEqual(
            accepted_source_ids,
            {"clean-1", "q2-non-human", "q2-missing-activity"},
        )

    def test_rejected_set_source_record_ids_and_reasons(self):
        fixtures = (
            "q0_missing_atom_mapping.json",
            "q1_resolution_outlier.json",
            "q0_multi_linkage.json",
        )

        envelope = _normalize(*fixtures)

        rejected_map = {
            rejected.normalized.source_lineage.source_record_id: rejected.reason
            for rejected in envelope.payload.rejected
        }
        self.assertEqual(len(rejected_map), 3)
        self.assertEqual(rejected_map["q0-mapping"], "ATOM_MAPPING_MISSING")
        self.assertEqual(rejected_map["q1-resolution"], "RESOLUTION_GT_3A")
        self.assertEqual(rejected_map["q0-multi"], "MULTI_LINKAGE_V1_REJECT")

    def test_mixed_accepted_rejected_source_ids_are_disjoint(self):
        fixtures = (
            "clean_record.json",
            "q2_non_human.json",
            "q0_missing_atom_mapping.json",
            "q1_resolution_outlier.json",
        )

        envelope = _normalize(*fixtures)

        accepted_ids = {
            accepted.normalized.source_lineage.source_record_id
            for accepted in envelope.payload.accepted
        }
        rejected_ids = {
            rejected.normalized.source_lineage.source_record_id
            for rejected in envelope.payload.rejected
        }
        self.assertTrue(accepted_ids.isdisjoint(rejected_ids))

    def test_rejected_reason_is_first_reason_from_gate_result(self):
        envelope = _normalize("q0_missing_atom_mapping.json")

        rejected = envelope.payload.rejected[0]
        self.assertEqual(rejected.reason, rejected.gate_result.reasons[0])
        self.assertEqual(rejected.reason, "ATOM_MAPPING_MISSING")


if __name__ == "__main__":
    unittest.main()
