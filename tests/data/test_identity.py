import sys
import unittest

from covalent_design.contracts import (
    LigandAtomIdentity,
    ProteinAtomIdentity,
    SourceIngestRecord,
    SourceRecordLineage,
)
from covalent_design.data.identity import (
    build_record_id,
    canonical_identity_from_record,
    normalize_identity_json,
    resolve_identities,
)


def source_record(
    source_database: str,
    *,
    source_record_id: str,
    pdb_id: str = "1ABC",
    protein_chain: str = "A",
    residue_number: int = 25,
    residue_name: str = "CYS",
    target_atom: str = "SG",
    ligand_id: str = "LIG",
    ligand_chain: str = "A",
    ligand_residue_number: int = 301,
    ligand_atom: str = "C1",
    bond_type: str = "thioether",
    residue_reaction_family: str = "cysteine_thiol",
    annotation_label: str = "annotation",
) -> SourceIngestRecord:
    lineage = SourceRecordLineage(
        source_database=source_database,
        source_version="fixture",
        source_record_id=source_record_id,
        raw_manifest_file=f"{source_database}/manifest.json",
        raw_file_path=f"{source_database}/records.csv",
        raw_file_sha256=source_database[:1] * 64,
        row_index=1,
    )
    return SourceIngestRecord(
        source_database=source_database,
        source_version="fixture",
        source_record_id=source_record_id,
        raw_manifest_file=lineage.raw_manifest_file,
        raw_file_path=lineage.raw_file_path,
        raw_file_sha256=lineage.raw_file_sha256,
        row_index=lineage.row_index,
        lineage={"source_record_id": source_record_id},
        protein={"pdb_id": pdb_id},
        ligand={"ligand_id": ligand_id},
        linkage={
            "bond_type": bond_type,
            "residue_reaction_family": residue_reaction_family,
        },
        metadata={"annotation_label": annotation_label},
        source_lineage=lineage,
        target_atom_identity=ProteinAtomIdentity(
            chain_id=protein_chain,
            residue_number=residue_number,
            residue_name=residue_name,
            atom_name=target_atom,
            structure_model=1,
        ),
        ligand_atom_identity=LigandAtomIdentity(
            ligand_id=ligand_id,
            chain_id=ligand_chain,
            residue_number=ligand_residue_number,
            atom_name=ligand_atom,
        ),
    )


class CanonicalIdentityTests(unittest.TestCase):
    def test_matching_canonical_keys_merge_all_lineage(self) -> None:
        covbinder = source_record("covbinder_in_pdb", source_record_id="covbinder:row:1")
        covpdb = source_record("covpdb", source_record_id="covpdb:row:99")

        result = resolve_identities((covbinder, covpdb))

        self.assertEqual(0, len(result.rejected_inputs))
        self.assertEqual(0, len(result.conflict_groups))
        self.assertEqual(1, len(result.merged_records))
        merged = result.merged_records[0]
        self.assertEqual(
            ("covbinder_in_pdb:covbinder:row:1", "covpdb:covpdb:row:99"),
            tuple(f"{lineage.source_database}:{lineage.source_record_id}" for lineage in merged.lineage),
        )

    def test_source_record_id_does_not_participate_in_record_id(self) -> None:
        left = source_record("covbinder_in_pdb", source_record_id="source-id-a")
        right = source_record("covbinder_in_pdb", source_record_id="source-id-b")

        left_identity = canonical_identity_from_record(left)
        right_identity = canonical_identity_from_record(right)

        self.assertEqual(build_record_id(left_identity), build_record_id(right_identity))
        self.assertNotIn("source-id-a", normalize_identity_json(left_identity))
        self.assertNotIn("source_record_id", normalize_identity_json(left_identity))

    def test_same_source_record_id_with_different_canonical_fields_does_not_merge(self) -> None:
        left = source_record("covbinder_in_pdb", source_record_id="same-source-id", target_atom="SG")
        right = source_record("covpdb", source_record_id="same-source-id", target_atom="OG")

        result = resolve_identities((left, right))

        self.assertEqual(0, len(result.merged_records))
        self.assertEqual(1, len(result.conflict_groups))

    def test_same_pdb_ligand_with_different_linkage_atom_produces_conflict_group(self) -> None:
        left = source_record("covbinder_in_pdb", source_record_id="a", ligand_atom="C1")
        right = source_record("covpdb", source_record_id="b", ligand_atom="C2")

        result = resolve_identities((left, right))

        self.assertEqual(1, len(result.conflict_groups))
        conflict = result.conflict_groups[0]
        self.assertEqual("LINKAGE_IDENTITY_CONFLICT", conflict.reason)
        self.assertEqual(2, len(conflict.conflicting_identities))
        self.assertEqual(2, len(conflict.lineage))

    def test_annotation_priority_keeps_lower_priority_lineage_and_alternatives(self) -> None:
        covalentin_db = source_record(
            "covalentin_db",
            source_record_id="low",
            annotation_label="low-priority-value",
        )
        covbinder = source_record(
            "covbinder_in_pdb",
            source_record_id="high",
            annotation_label="high-priority-value",
        )

        result = resolve_identities((covalentin_db, covbinder))

        merged = result.merged_records[0]
        self.assertEqual("high-priority-value", merged.preferred_annotations["annotation_label"])
        self.assertEqual(2, len(merged.lineage))
        self.assertEqual(
            ("high-priority-value", "low-priority-value"),
            tuple(value.value for value in merged.annotation_alternatives["annotation_label"]),
        )

    def test_record_id_is_deterministic(self) -> None:
        identity = canonical_identity_from_record(source_record("covbinder_in_pdb", source_record_id="a"))

        self.assertEqual(build_record_id(identity), build_record_id(identity))
        self.assertEqual(32, len(build_record_id(identity)))

    def test_normalized_identity_json_order_does_not_affect_record_id(self) -> None:
        left = canonical_identity_from_record(source_record("covbinder_in_pdb", source_record_id="a"))
        right = canonical_identity_from_record(
            source_record(
                "covbinder_in_pdb",
                source_record_id="b",
                annotation_label="different-non-identity-annotation",
            )
        )

        self.assertEqual(normalize_identity_json(left), normalize_identity_json(right))
        self.assertEqual(build_record_id(left), build_record_id(right))

    def test_missing_identity_critical_fields_are_rejected_not_dropped(self) -> None:
        malformed = source_record("covbinder_in_pdb", source_record_id="bad", pdb_id="")

        result = resolve_identities((malformed,))

        self.assertEqual(0, len(result.merged_records))
        self.assertEqual(0, len(result.conflict_groups))
        self.assertEqual(1, len(result.rejected_inputs))
        self.assertEqual("IDENTITY_CRITICAL_FIELD_MISSING", result.rejected_inputs[0].reason)
        self.assertIn("structure_id", result.rejected_inputs[0].missing_fields)

    def test_identity_modules_do_not_import_heavy_chemistry_dependencies(self) -> None:
        self.assertNotIn("rdkit", sys.modules)
        self.assertNotIn("openbabel", sys.modules)


if __name__ == "__main__":
    unittest.main()
