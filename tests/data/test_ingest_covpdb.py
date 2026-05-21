from pathlib import Path
import unittest

from covalent_design.contracts import ContractEnvelope, ValidationReceipt
from covalent_design.data.ingest import SourceIngestIndex, ingest_source


FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "covpdb"


class CovPDBIngestionTests(unittest.TestCase):
    def test_parse_10_covpdb_records(self):
        envelope = ingest_source("covpdb", FIXTURE_ROOT / "valid")

        self.assertIsInstance(envelope, ContractEnvelope)
        self.assertIsInstance(envelope.payload, SourceIngestIndex)
        self.assertIsInstance(envelope.receipt, ValidationReceipt)
        self.assertTrue(envelope.receipt.ok)
        self.assertEqual("covalent_design.data.ingest_source", envelope.receipt.validator)
        self.assertEqual((), envelope.receipt.errors)
        self.assertFalse(envelope.payload.complete_for_v1)
        self.assertEqual(10, envelope.payload.record_count)
        self.assertEqual(10, len(envelope.payload.records))
        self.assertEqual(0, envelope.payload.failure_count)
        self.assertEqual({}, dict(envelope.payload.failure_reason_counts))

    def test_covpdb_records_preserve_lineage_and_source_fields(self):
        envelope = ingest_source("covpdb", FIXTURE_ROOT / "valid")

        for record in envelope.payload.records:
            self.assertEqual("covpdb", record.source_database)
            self.assertEqual("fixture-2026-05-20", record.source_version)
            self.assertTrue(record.source_record_id.startswith("covpdb:"))
            self.assertEqual("covpdb/records.csv", record.raw_file_path)
            self.assertEqual(
                "d22acedc549f5c5d5ac18172164b7e10bc883ae6ddfdd8156f47a1fc7d3e7936",
                record.raw_file_sha256,
            )
            self.assertGreaterEqual(record.row_index, 1)
            self.assertEqual(record.raw_file_path, record.lineage["raw_file_path"])
            self.assertEqual(record.raw_file_sha256, record.lineage["raw_file_sha256"])
            self.assertEqual(record.row_index, record.lineage["row_index"])
            self.assertEqual("fixture-only", record.lineage["license"])
            self.assertIn("access_notes", record.lineage)

    def test_covpdb_records_keep_core_and_structural_fields(self):
        envelope = ingest_source("covpdb", FIXTURE_ROOT / "valid")
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
        self.assertEqual(2.0, first.metadata["resolution"])
        self.assertEqual("X-RAY", first.metadata["experimental_method"])
        self.assertEqual(0.18, first.metadata["r_factor"])
        self.assertEqual(0.22, first.metadata["r_free"])
        self.assertEqual(1.82, first.metadata["linkage_distance_angstrom"])
        self.assertEqual("matched", first.metadata["structure_validation_status"])
        self.assertIn("cross_check_notes", first.metadata)

    def test_missing_fields_are_counted_as_failure_reasons(self):
        envelope = ingest_source("covpdb", FIXTURE_ROOT / "missing_fields")

        self.assertTrue(envelope.receipt.ok)
        self.assertFalse(envelope.payload.complete_for_v1)
        self.assertEqual(4, envelope.payload.raw_record_count)
        self.assertEqual(2, envelope.payload.record_count)
        self.assertEqual(2, envelope.payload.failure_count)
        self.assertEqual(
            {"INGEST_MISSING_REQUIRED_FIELD": 2},
            dict(envelope.payload.failure_reason_counts),
        )
        self.assertTrue(
            all(failure.reason == "INGEST_MISSING_REQUIRED_FIELD" for failure in envelope.payload.failures)
        )


if __name__ == "__main__":
    unittest.main()
