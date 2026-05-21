import unittest
from dataclasses import FrozenInstanceError

from covalent_design.contracts import (
    LigandAtomIdentity,
    ProteinAtomIdentity,
    SourceIngestRecord,
    SourceRecordLineage,
)


class IdentityContractTests(unittest.TestCase):
    def test_protein_atom_identity_carries_structure_atom_locator_fields(self) -> None:
        identity = ProteinAtomIdentity(
            structure_model=1,
            chain_id="A",
            asym_id="A_AUTH",
            residue_name="CYS",
            residue_number=145,
            insertion_code="",
            altloc="A",
            atom_name="SG",
            atom_serial=1234,
        )

        self.assertEqual(identity.structure_model, 1)
        self.assertEqual(identity.asym_id, "A_AUTH")
        self.assertEqual(identity.atom_serial, 1234)
        with self.assertRaises(FrozenInstanceError):
            identity.atom_name = "CB"  # type: ignore[misc]

    def test_ligand_atom_identity_carries_chain_residue_and_index_fields(self) -> None:
        identity = LigandAtomIdentity(
            ligand_id="LIG",
            chain_id="B",
            asym_id="B_AUTH",
            residue_number=301,
            atom_name="C1",
            atom_index=7,
            altloc=None,
        )

        self.assertEqual(identity.ligand_id, "LIG")
        self.assertEqual(identity.chain_id, "B")
        self.assertEqual(identity.atom_index, 7)

    def test_source_ingest_record_preserves_legacy_maps_and_typed_identity(self) -> None:
        lineage = SourceRecordLineage(
            source_database="covbinder_in_pdb",
            source_version="fixture",
            source_record_id="covbinder_in_pdb:records.csv:row:1",
            raw_manifest_file="covbinder_in_pdb/manifest.json",
            raw_file_path="covbinder_in_pdb/records.csv",
            raw_file_sha256="a" * 64,
            row_index=1,
        )
        target = ProteinAtomIdentity(
            chain_id="A",
            residue_number=25,
            residue_name="CYS",
            atom_name="SG",
        )
        ligand = LigandAtomIdentity(
            ligand_id="LIG",
            chain_id="A",
            residue_number=301,
            atom_name="C1",
        )

        record = SourceIngestRecord(
            source_database="covbinder_in_pdb",
            source_version="fixture",
            source_record_id=lineage.source_record_id,
            raw_manifest_file=lineage.raw_manifest_file,
            raw_file_path=lineage.raw_file_path,
            raw_file_sha256=lineage.raw_file_sha256,
            row_index=lineage.row_index,
            lineage={"raw_file_path": lineage.raw_file_path},
            protein={"residue_name": "CYS"},
            ligand={"ligand_id": "LIG"},
            linkage={"residue_reaction_family": "cysteine_thiol"},
            metadata={},
            source_lineage=lineage,
            target_atom_identity=target,
            ligand_atom_identity=ligand,
        )

        self.assertEqual(record.lineage["raw_file_path"], lineage.raw_file_path)
        self.assertEqual(record.source_lineage, lineage)
        self.assertEqual(record.target_atom_identity, target)
        self.assertEqual(record.ligand_atom_identity, ligand)


if __name__ == "__main__":
    unittest.main()
