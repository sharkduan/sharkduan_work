import json
import os
import subprocess
import sys
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


if __name__ == "__main__":
    unittest.main()
