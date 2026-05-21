import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from covalent_design.contracts import CONTRACT_VERSION, SCHEMA_VERSION, ContractErrorInfo, ValidationReceipt
from covalent_design.contracts.receipts import read_validation_receipt, write_validation_receipt
from covalent_design.io.artifacts import artifact_ref_from_file, validate_artifact_ref
from covalent_design.io.jsonl import read_jsonl, write_jsonl


class ArtifactIoTests(unittest.TestCase):
    def test_artifact_ref_from_file_validates_checksum_and_size(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact_path = root / "records.jsonl"
            artifact_path.write_text('{"record_id": "rec-1"}\n', encoding="utf-8")

            ref = artifact_ref_from_file(artifact_path, role="record_index", root=root)
            receipt = validate_artifact_ref(ref, root=root)

            self.assertEqual(ref.uri, "records.jsonl")
            self.assertEqual(ref.format, "jsonl")
            self.assertEqual(ref.schema_version, SCHEMA_VERSION)
            self.assertTrue(receipt.passed)

    def test_artifact_validation_reports_checksum_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact_path = root / "records.jsonl"
            artifact_path.write_text('{"record_id": "rec-1"}\n', encoding="utf-8")
            ref = artifact_ref_from_file(artifact_path, role="record_index", root=root)
            artifact_path.write_text('{"record_id": "rec-2"}\n', encoding="utf-8")

            receipt = validate_artifact_ref(ref, root=root)

            self.assertFalse(receipt.passed)
            self.assertEqual(receipt.errors[0].code, "ARTIFACT_CHECKSUM_MISMATCH")

    def test_artifact_validation_rejects_absolute_uri(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact_path = root / "records.jsonl"
            artifact_path.write_text('{"record_id": "rec-1"}\n', encoding="utf-8")
            ref = artifact_ref_from_file(artifact_path, role="record_index", root=root)
            ref = replace(ref, uri=artifact_path.resolve().as_posix())

            receipt = validate_artifact_ref(ref, root=root)

            self.assertFalse(receipt.passed)
            self.assertEqual(receipt.errors[0].code, "ARTIFACT_URI_INVALID")

    def test_artifact_validation_checks_zero_byte_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact_path = root / "records.jsonl"
            artifact_path.write_text('{"record_id": "rec-1"}\n', encoding="utf-8")
            ref = artifact_ref_from_file(artifact_path, role="record_index", root=root)
            ref = replace(ref, bytes=0)

            receipt = validate_artifact_ref(ref, root=root)

            self.assertFalse(receipt.passed)
            self.assertEqual(receipt.errors[0].code, "ARTIFACT_BYTE_COUNT_MISMATCH")


class JsonlIoTests(unittest.TestCase):
    def test_jsonl_write_and_read_preserves_versions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "records.jsonl"
            ref = write_jsonl(
                path,
                [
                    {"record_id": "rec-1", "value": 1},
                    {"record_id": "rec-2", "value": 2},
                ],
                role="record_index",
            )

            rows = read_jsonl(path)

            self.assertEqual(ref.format, "jsonl")
            self.assertEqual(rows[0]["schema_version"], SCHEMA_VERSION)
            self.assertEqual(rows[0]["contract_version"], CONTRACT_VERSION)
            self.assertEqual(rows[1]["record_id"], "rec-2")

    def test_jsonl_reader_rejects_missing_contract_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "records.jsonl"
            path.write_text(json.dumps({"schema_version": SCHEMA_VERSION}) + "\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "JSONL_CONTRACT_VERSION_MISSING"):
                read_jsonl(path)


class ValidationReceiptIoTests(unittest.TestCase):
    def test_validation_receipt_round_trips_through_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "receipt.json"
            receipt = ValidationReceipt(
                validator="tests.io",
                contract_version=CONTRACT_VERSION,
                input_sha256="a" * 64,
                passed=False,
                errors=(
                    ContractErrorInfo(
                        code="TEST_ERROR",
                        owner="data",
                        message="fixture",
                        location="records.jsonl",
                        details={"line": 1},
                    ),
                ),
            )

            ref = write_validation_receipt(path, receipt)
            loaded = read_validation_receipt(path)

            self.assertEqual(ref.role, "validation_receipt")
            self.assertFalse(loaded.passed)
            self.assertEqual(loaded.errors[0].code, "TEST_ERROR")
            self.assertEqual(loaded.errors[0].details["line"], 1)


if __name__ == "__main__":
    unittest.main()
