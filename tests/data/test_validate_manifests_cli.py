import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


def write_fixture_file(path: Path, text: str) -> str:
    data = text.encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def write_manifest(source_root: Path, *, sha256: str, size: int) -> None:
    payload = {
        "source_database": "covbinder_in_pdb",
        "source_version": "2026-05-fixture",
        "retrieval_date": "2026-05-20",
        "license": "fixture-only",
        "access_notes": "committed lightweight test fixture",
        "complete_for_v1": True,
        "files": [
            {
                "path": "records.csv",
                "role": "records",
                "bytes": size,
                "sha256": sha256,
            }
        ],
    }
    (source_root / "manifest.json").write_text(json.dumps(payload), encoding="utf-8")


class ValidateManifestsCliTests(unittest.TestCase):
    def run_cli(self, raw_root: Path) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = "src"
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "covalent_design.data.validate_manifests",
                "--raw-root",
                str(raw_root),
            ],
            cwd=Path(__file__).resolve().parents[2],
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_valid_manifest_cli_returns_json_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            raw_root = Path(tmp)
            source_root = raw_root / "covbinder_in_pdb"
            checksum = write_fixture_file(source_root / "records.csv", "id,value\n1,ok\n")
            write_manifest(
                source_root,
                sha256=checksum,
                size=(source_root / "records.csv").stat().st_size,
            )

            result = self.run_cli(raw_root)

            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads(result.stdout)
            self.assertTrue(summary["ok"])
            self.assertEqual(summary["source_count"], 1)
            self.assertEqual(summary["file_count"], 1)

    def test_invalid_manifest_cli_returns_data_quality_exit_code(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            raw_root = Path(tmp)
            source_root = raw_root / "covbinder_in_pdb"
            write_fixture_file(source_root / "records.csv", "id,value\n1,ok\n")
            write_manifest(
                source_root,
                sha256="0" * 64,
                size=(source_root / "records.csv").stat().st_size,
            )

            result = self.run_cli(raw_root)

            self.assertEqual(result.returncode, 30)
            summary = json.loads(result.stdout)
            self.assertFalse(summary["ok"])
            self.assertEqual(summary["errors"][0]["code"], "RAW_MANIFEST_CHECKSUM_MISMATCH")


if __name__ == "__main__":
    unittest.main()
