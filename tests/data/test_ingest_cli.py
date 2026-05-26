import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "covbinder"


class IngestCliTests(unittest.TestCase):
    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = "src"
        return subprocess.run(
            [sys.executable, "-m", "covalent_design.data.ingest", *args],
            cwd=Path(__file__).resolve().parents[2],
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_valid_source_ingest_cli_returns_json_summary(self) -> None:
        result = self.run_cli(
            "--source",
            "covbinder_in_pdb",
            "--raw-root",
            str(FIXTURE_ROOT / "valid"),
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        summary = json.loads(result.stdout)
        self.assertTrue(summary["ok"])
        self.assertEqual(summary["source"], "covbinder_in_pdb")
        self.assertEqual(summary["source_database"], "covbinder_in_pdb")
        self.assertEqual(summary["record_count"], 10)
        self.assertEqual(summary["failure_count"], 0)
        self.assertEqual(summary["failure_counts"], {})
        self.assertEqual(summary["complete_for_v1_scope"], "single_source_raw_manifest")

    def test_unsupported_source_ingest_cli_returns_structured_error(self) -> None:
        result = self.run_cli(
            "--source",
            "not_a_source",
            "--raw-root",
            str(FIXTURE_ROOT / "valid"),
        )

        self.assertEqual(result.returncode, 30)
        summary = json.loads(result.stdout)
        self.assertFalse(summary["ok"])
        self.assertEqual(summary["errors"][0]["code"], "SOURCE_UNSUPPORTED")

    def test_out_writes_source_records_jsonl_and_ingest_index_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir)
            result = self.run_cli(
                "--source",
                "covbinder_in_pdb",
                "--raw-root",
                str(FIXTURE_ROOT / "valid"),
                "--out",
                str(out_dir),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            records_path = out_dir / "source_records.jsonl"
            index_path = out_dir / "ingest_index.json"
            self.assertTrue(records_path.exists(), f"Missing {records_path}")
            self.assertTrue(index_path.exists(), f"Missing {index_path}")

            records_lines = records_path.read_text("utf-8").strip().splitlines()
            self.assertEqual(len(records_lines), 10)

            index = json.loads(index_path.read_text("utf-8"))
            self.assertEqual(index["source_database"], "covbinder_in_pdb")
            self.assertEqual(index["record_count"], 10)
            self.assertIn("records", index)
            self.assertEqual(len(index["records"]), 10)

    def test_out_feeds_normalize_interim_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir)
            ingest_result = self.run_cli(
                "--source",
                "covbinder_in_pdb",
                "--raw-root",
                str(FIXTURE_ROOT / "valid"),
                "--out",
                str(out_dir),
            )
            self.assertEqual(ingest_result.returncode, 0, ingest_result.stderr)

            env = os.environ.copy()
            env["PYTHONPATH"] = "src"
            normalize_result = subprocess.run(
                [sys.executable, "-m", "covalent_design.data.normalize", "--interim-root", str(out_dir)],
                cwd=Path(__file__).resolve().parents[2],
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(normalize_result.returncode, 0, normalize_result.stderr)
            summary = json.loads(normalize_result.stdout)
            self.assertTrue(summary["ok"])
            self.assertGreater(summary["input_record_count"], 0)


if __name__ == "__main__":
    unittest.main()
