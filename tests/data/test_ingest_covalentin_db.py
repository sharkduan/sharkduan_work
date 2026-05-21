from pathlib import Path
import unittest

from covalent_design.contracts import ContractEnvelope, ValidationReceipt
from covalent_design.data.ingest import SourceIngestIndex, ingest_source


FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "covalentin_db"


class CovalentInDBIngestionTests(unittest.TestCase):
    def test_parse_10_covalentin_db_records(self):
        envelope = ingest_source("covalentin_db", FIXTURE_ROOT / "valid")

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

    def test_covalentin_db_records_preserve_lineage_and_source_fields(self):
        envelope = ingest_source("covalentin_db", FIXTURE_ROOT / "valid")

        for record in envelope.payload.records:
            self.assertEqual("covalentin_db", record.source_database)
            self.assertEqual("fixture-2026-05-20", record.source_version)
            self.assertTrue(record.source_record_id.startswith("covalentin_db:"))
            self.assertEqual("covalentin_db/records.csv", record.raw_file_path)
            self.assertEqual(
                "0eefc186e3421c5878e543eb4c5da7bf8d335c3d3cf94052cd74d4b910263a83",
                record.raw_file_sha256,
            )
            self.assertGreaterEqual(record.row_index, 1)
            self.assertEqual(record.raw_file_path, record.lineage["raw_file_path"])
            self.assertEqual(record.raw_file_sha256, record.lineage["raw_file_sha256"])
            self.assertEqual(record.row_index, record.lineage["row_index"])
            self.assertIn("license", record.lineage)
            self.assertIn("access_notes", record.lineage)

    def test_p0_source_fields_are_core_fields(self):
        envelope = ingest_source("covalentin_db", FIXTURE_ROOT / "valid")
        first = envelope.payload.records[0]

        self.assertEqual(
            {
                "target_name": "Kinase A",
                "uniprot_id": "P11111",
                "residue": "Cys",
                "residue_name": "CYS",
                "atom_name": "SG",
            },
            first.protein,
        )
        self.assertEqual(
            {
                "compound_id": "CID0001",
                "attachment_atom": "C1",
                "warhead_class": "acrylamide",
            },
            first.ligand,
        )
        self.assertEqual(
            {
                "bond_type": "thioether",
                "residue_reaction_family": "cysteine_michael_addition",
            },
            first.linkage,
        )

    def test_p1_p2_fields_are_metadata_only(self):
        envelope = ingest_source("covalentin_db", FIXTURE_ROOT / "valid")
        first = envelope.payload.records[0]

        self.assertEqual("1abc", first.metadata["pdb_id"])
        self.assertEqual("A", first.metadata["chain"])
        self.assertEqual(2.0, first.metadata["resolution"])
        self.assertEqual(12.5, first.metadata["ic50_nm"])
        self.assertIsNone(first.metadata["ki_nm"])
        self.assertEqual("biochemical", first.metadata["assay_type"])
        self.assertEqual("Smith 2020", first.metadata["reference"])
        self.assertEqual("10.1000/cid0001", first.metadata["doi"])
        self.assertEqual(2020, first.metadata["year"])
        self.assertNotIn("pdb_id", first.protein)
        self.assertNotIn("pdb_id", first.ligand)
        self.assertNotIn("pdb_id", first.linkage)
        self.assertFalse(hasattr(first, "canonical_record_id"))

    def test_missing_p0_fields_are_counted_as_failure_reasons(self):
        envelope = ingest_source("covalentin_db", FIXTURE_ROOT / "missing_fields")

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
