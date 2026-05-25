import unittest
from pathlib import Path

from covalent_design.data.ingest import ingest_source


PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "covbinder"
READINESS_DOC = PROJECT_ROOT / "docs" / "specs" / "task7-readiness.md"


class Task7IdentityContractBoundaryTests(unittest.TestCase):
    def test_ingested_records_expose_typed_identity_inputs_for_task7(self) -> None:
        envelope = ingest_source("covbinder_in_pdb", FIXTURE_ROOT / "valid")
        record = envelope.payload.records[0]

        self.assertIsNotNone(record.source_lineage)
        self.assertIsNotNone(record.target_atom_identity)
        self.assertIsNotNone(record.ligand_atom_identity)
        self.assertEqual(record.source_lineage.source_database, "covbinder_in_pdb")
        self.assertEqual(record.target_atom_identity.residue_name, "CYS")
        self.assertEqual(record.target_atom_identity.atom_name, "SG")
        self.assertEqual(record.ligand_atom_identity.atom_name, "C1")
        self.assertEqual(record.linkage["residue_reaction_family"], "cysteine_thiol")

    def test_task7_handoff_note_defines_completed_boundary(self) -> None:
        text = READINESS_DOC.read_text(encoding="utf-8")

        self.assertIn("Task 7 must not depend on private helper names", text)
        self.assertIn("CovBinderInPDB > CovPDB > CovalentInDB", text)
        self.assertIn("Completed", text)
        self.assertIn("CanonicalLinkageIdentity", text)
        self.assertIn("normalize_with_identity_resolution", text)
        self.assertIn("Conflicts never enter accepted normalized output", text)


if __name__ == "__main__":
    unittest.main()
