from pathlib import Path
import unittest

from covalent_design.contracts import ContractEnvelope, ValidationReceipt
from covalent_design.data.ingest import SourceIngestIndex, ingest_source


FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "covbinder"


class CovBinderIngestionTests(unittest.TestCase):
    def test_parse_10_covbinder_records(self):
        envelope = ingest_source("covbinder_in_pdb", FIXTURE_ROOT / "valid")

        self.assertIsInstance(envelope, ContractEnvelope)
        self.assertIsInstance(envelope.payload, SourceIngestIndex)
        self.assertIsInstance(envelope.receipt, ValidationReceipt)
        self.assertTrue(envelope.receipt.ok)
        self.assertEqual("covalent_design.data.ingest_source", envelope.receipt.validator)
        self.assertEqual((), envelope.receipt.errors)
        self.assertEqual(10, envelope.payload.record_count)
        self.assertEqual(10, len(envelope.payload.records))
        self.assertEqual(0, envelope.payload.failure_count)
        self.assertEqual({}, dict(envelope.payload.failure_reason_counts))

    def test_covbinder_records_preserve_lineage_and_source_fields(self):
        envelope = ingest_source("covbinder_in_pdb", FIXTURE_ROOT / "valid")

        for record in envelope.payload.records:
            self.assertEqual("covbinder_in_pdb", record.source_database)
            self.assertEqual("fixture-2026-05-20", record.source_version)
            self.assertTrue(record.source_record_id.startswith("covbinder_in_pdb:"))
            self.assertEqual("covbinder_in_pdb/records.csv", record.raw_file_path)
            self.assertEqual(
                "6314ad77e17adfcd4a0ab51fb0fee2501e9ac4e1d9fa349b8ff171469f7991a8",
                record.raw_file_sha256,
            )
            self.assertGreaterEqual(record.row_index, 1)
            self.assertEqual(record.raw_file_path, record.lineage["raw_file_path"])
            self.assertEqual(record.raw_file_sha256, record.lineage["raw_file_sha256"])
            self.assertEqual(record.row_index, record.lineage["row_index"])
            self.assertEqual("fixture-only", record.lineage["license"])
            self.assertIn("access_notes", record.lineage)

    def test_covbinder_records_keep_protein_ligand_and_linkage_fields(self):
        envelope = ingest_source("covbinder_in_pdb", FIXTURE_ROOT / "valid")
        first = envelope.payload.records[0]

        self.assertEqual(
            {
                "pdb_id": "1abc",
                "chain_id": "A",
                "residue_number": 25,
                "residue_name": "CYS",
                "atom_name": "SG",
            },
            first.protein,
        )
        self.assertEqual(
            {
                "ligand_id": "LIG",
                "chain_id": "A",
                "residue_number": 301,
                "attachment_atom": "C1",
            },
            first.ligand,
        )
        self.assertEqual(
            {
                "bond_type": "thioether",
                "residue_reaction_family": "cysteine_thiol",
            },
            first.linkage,
        )

    def test_missing_fields_are_counted_as_failure_reasons(self):
        envelope = ingest_source("covbinder_in_pdb", FIXTURE_ROOT / "missing_fields")

        self.assertTrue(envelope.receipt.ok)
        self.assertEqual(4, envelope.payload.raw_record_count)
        self.assertEqual(2, envelope.payload.record_count)
        self.assertEqual(2, envelope.payload.failure_count)
        self.assertEqual(
            {"INGEST_MISSING_REQUIRED_FIELD": 2},
            dict(envelope.payload.failure_reason_counts),
        )
        self.assertEqual(2, len(envelope.payload.failures))
        self.assertTrue(
            all(failure.reason == "INGEST_MISSING_REQUIRED_FIELD" for failure in envelope.payload.failures)
        )

    def test_unknown_source_returns_failed_receipt(self):
        envelope = ingest_source("not_a_source", FIXTURE_ROOT / "valid")

        self.assertFalse(envelope.receipt.ok)
        self.assertEqual((), envelope.payload.records)
        self.assertEqual("SOURCE_UNSUPPORTED", envelope.receipt.errors[0].code)


if __name__ == "__main__":
    unittest.main()
