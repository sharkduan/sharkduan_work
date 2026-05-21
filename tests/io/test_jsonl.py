import json
import tempfile
import unittest
from pathlib import Path

from covalent_design.contracts import CONTRACT_VERSION, SCHEMA_VERSION
from covalent_design.io.jsonl import read_jsonl


class JsonlVersionValidationTests(unittest.TestCase):
    def test_reader_accepts_matching_versions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "records.jsonl"
            path.write_text(
                json.dumps({"schema_version": SCHEMA_VERSION, "contract_version": CONTRACT_VERSION, "data": "ok"}) + "\n",
                encoding="utf-8",
            )
            rows = read_jsonl(path, expected_schema_version=SCHEMA_VERSION, expected_contract_version=CONTRACT_VERSION)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["data"], "ok")

    def test_reader_rejects_unexpected_schema_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "records.jsonl"
            path.write_text(
                json.dumps({"schema_version": "2", "contract_version": CONTRACT_VERSION}) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "JSONL_SCHEMA_VERSION_UNSUPPORTED"):
                read_jsonl(path, expected_schema_version=SCHEMA_VERSION)

    def test_reader_rejects_unexpected_contract_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "records.jsonl"
            path.write_text(
                json.dumps({"schema_version": SCHEMA_VERSION, "contract_version": "2.0.0"}) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "JSONL_CONTRACT_VERSION_UNSUPPORTED"):
                read_jsonl(path, expected_contract_version=CONTRACT_VERSION)

    def test_require_versions_true_rejects_missing_schema_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "records.jsonl"
            path.write_text(
                json.dumps({"contract_version": CONTRACT_VERSION, "data": "x"}) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "JSONL_SCHEMA_VERSION_MISSING"):
                read_jsonl(path)

    def test_require_versions_true_rejects_missing_contract_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "records.jsonl"
            path.write_text(
                json.dumps({"schema_version": SCHEMA_VERSION, "data": "x"}) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "JSONL_CONTRACT_VERSION_MISSING"):
                read_jsonl(path)

    def test_require_versions_false_allows_missing_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "records.jsonl"
            path.write_text(
                json.dumps({"data": "bare"}) + "\n",
                encoding="utf-8",
            )
            rows = read_jsonl(path, require_versions=False)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["data"], "bare")

    def test_expected_schema_version_fails_when_field_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "records.jsonl"
            path.write_text(
                json.dumps({"contract_version": CONTRACT_VERSION, "data": "x"}) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "JSONL_SCHEMA_VERSION_MISSING"):
                read_jsonl(path, expected_schema_version=SCHEMA_VERSION)

    def test_expected_contract_version_fails_when_field_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "records.jsonl"
            path.write_text(
                json.dumps({"schema_version": SCHEMA_VERSION, "data": "x"}) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "JSONL_CONTRACT_VERSION_MISSING"):
                read_jsonl(path, expected_contract_version=CONTRACT_VERSION)

    def test_expected_version_missing_even_without_require_versions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "records.jsonl"
            path.write_text(
                json.dumps({"contract_version": CONTRACT_VERSION, "data": "x"}) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "JSONL_SCHEMA_VERSION_MISSING"):
                read_jsonl(path, require_versions=False, expected_schema_version=SCHEMA_VERSION)


if __name__ == "__main__":
    unittest.main()
