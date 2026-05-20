import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from covalent_design.data.manifests import validate_raw_manifests


def write_text(path: Path, text: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = text.encode("utf-8")
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def write_manifest(source_root: Path, files: list[dict], **overrides: object) -> Path:
    payload = {
        "source_database": "covbinder_in_pdb",
        "source_version": "2026-05-fixture",
        "retrieval_date": "2026-05-20",
        "license": "fixture-only",
        "access_notes": "committed lightweight test fixture",
        "complete_for_v1": True,
        "files": files,
    }
    payload.update(overrides)
    path = source_root / "manifest.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


class RawManifestValidationTests(unittest.TestCase):
    def test_valid_manifest_reports_inventory_and_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            raw_root = Path(tmp)
            source_root = raw_root / "covbinder_in_pdb"
            checksum = write_text(source_root / "records.csv", "id,value\n1,ok\n")
            write_manifest(
                source_root,
                [
                    {
                        "path": "records.csv",
                        "role": "records",
                        "bytes": (source_root / "records.csv").stat().st_size,
                        "sha256": checksum,
                    }
                ],
            )

            envelope = validate_raw_manifests(raw_root)

            self.assertEqual(envelope.payload.source_count, 1)
            self.assertEqual(envelope.payload.file_count, 1)
            self.assertEqual(envelope.payload.extra_files, ())
            self.assertTrue(envelope.receipt.ok)
            self.assertEqual(envelope.receipt.validator, "covalent_design.data.validate_raw_manifests")

    def test_checksum_mismatch_is_structured_manifest_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            raw_root = Path(tmp)
            source_root = raw_root / "covbinder_in_pdb"
            write_text(source_root / "records.csv", "id,value\n1,changed\n")
            write_manifest(
                source_root,
                [
                    {
                        "path": "records.csv",
                        "role": "records",
                        "bytes": (source_root / "records.csv").stat().st_size,
                        "sha256": "0" * 64,
                    }
                ],
            )

            envelope = validate_raw_manifests(raw_root)

            self.assertFalse(envelope.receipt.ok)
            errors = {error.code: error for error in envelope.receipt.errors}
            self.assertIn("RAW_MANIFEST_CHECKSUM_MISMATCH", errors)
            self.assertEqual(errors["RAW_MANIFEST_CHECKSUM_MISMATCH"].owner, "data")

    def test_unmanifested_files_are_reported_as_extras(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            raw_root = Path(tmp)
            source_root = raw_root / "covbinder_in_pdb"
            checksum = write_text(source_root / "records.csv", "id,value\n1,ok\n")
            write_text(source_root / "extra.csv", "not,declared\n")
            write_manifest(
                source_root,
                [
                    {
                        "path": "records.csv",
                        "role": "records",
                        "bytes": (source_root / "records.csv").stat().st_size,
                        "sha256": checksum,
                    }
                ],
            )

            envelope = validate_raw_manifests(raw_root)

            self.assertEqual(envelope.payload.extra_files, ("covbinder_in_pdb/extra.csv",))
            self.assertTrue(envelope.receipt.ok)

    def test_malformed_file_byte_count_is_structured_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            raw_root = Path(tmp)
            source_root = raw_root / "covbinder_in_pdb"
            checksum = write_text(source_root / "records.csv", "id,value\n1,ok\n")
            write_manifest(
                source_root,
                [
                    {
                        "path": "records.csv",
                        "role": "records",
                        "bytes": "not-an-integer",
                        "sha256": checksum,
                    }
                ],
            )

            envelope = validate_raw_manifests(raw_root)

            self.assertFalse(envelope.receipt.ok)
            self.assertEqual(envelope.receipt.errors[0].code, "RAW_MANIFEST_FILE_BYTES_INVALID")

    def test_complete_for_v1_must_be_boolean(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            raw_root = Path(tmp)
            source_root = raw_root / "covbinder_in_pdb"
            checksum = write_text(source_root / "records.csv", "id,value\n1,ok\n")
            write_manifest(
                source_root,
                [
                    {
                        "path": "records.csv",
                        "role": "records",
                        "bytes": (source_root / "records.csv").stat().st_size,
                        "sha256": checksum,
                    }
                ],
                complete_for_v1="false",
            )

            envelope = validate_raw_manifests(raw_root)

            self.assertFalse(envelope.receipt.ok)
            self.assertEqual(envelope.receipt.errors[0].code, "RAW_MANIFEST_COMPLETE_FOR_V1_INVALID")


if __name__ == "__main__":
    unittest.main()
