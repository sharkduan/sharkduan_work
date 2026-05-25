import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "normalize"


class NormalizeCLITests(unittest.TestCase):
    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = "src"
        return subprocess.run(
            [sys.executable, "-m", "covalent_design.data.normalize", *args],
            cwd=Path(__file__).resolve().parents[2],
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_normalize_module_exports_main_function(self):
        from covalent_design.data.normalize import main
        self.assertTrue(callable(main))

    def test_normalize_cli_help_returns_zero(self):
        result = self.run_cli("--help")

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_normalize_cli_requires_source_argument(self):
        result = self.run_cli()

        self.assertNotEqual(result.returncode, 0)

    def test_normalize_cli_accepts_source_and_raw_root(self):
        result = self.run_cli(
            "--source", "covbinder_in_pdb",
            "--raw-root", str(FIXTURE_ROOT),
        )

        summary = json.loads(result.stdout)
        self.assertIn("accepted_record_count", summary)
        self.assertIn("rejected_record_count", summary)

    def test_normalize_cli_reports_accepted_and_rejected_counts(self):
        result = self.run_cli(
            "--source", "covbinder_in_pdb",
            "--raw-root", str(FIXTURE_ROOT),
        )

        summary = json.loads(result.stdout)
        self.assertIsInstance(summary.get("accepted_record_count"), int)
        self.assertIsInstance(summary.get("rejected_record_count"), int)

    def test_normalize_cli_reports_conflict_groups(self):
        result = self.run_cli(
            "--source", "covbinder_in_pdb",
            "--raw-root", str(FIXTURE_ROOT),
        )

        summary = json.loads(result.stdout)
        self.assertIn("conflict_group_count", summary)

    def test_normalize_cli_reports_quality_tier_summary(self):
        result = self.run_cli(
            "--source", "covbinder_in_pdb",
            "--raw-root", str(FIXTURE_ROOT),
        )

        summary = json.loads(result.stdout)
        self.assertIn("quality_tier_counts", summary)

    def test_normalize_cli_returns_non_zero_on_unsupported_source(self):
        result = self.run_cli(
            "--source", "not_a_source",
            "--raw-root", str(FIXTURE_ROOT),
        )

        self.assertNotEqual(result.returncode, 0)

    def test_normalize_cli_produces_stable_deterministic_output(self):
        first = self.run_cli(
            "--source", "covbinder_in_pdb",
            "--raw-root", str(FIXTURE_ROOT),
        )
        second = self.run_cli(
            "--source", "covbinder_in_pdb",
            "--raw-root", str(FIXTURE_ROOT),
        )

        self.assertEqual(
            json.loads(first.stdout),
            json.loads(second.stdout),
        )

    def test_normalize_cli_writes_output_to_out_path_when_specified(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "normalize_out.json"
            result = self.run_cli(
                "--source", "covbinder_in_pdb",
                "--raw-root", str(FIXTURE_ROOT),
                "--out", str(out_path),
            )

            self.assertTrue(out_path.exists(), f"Expected {out_path} to exist")
            written = json.loads(out_path.read_text())
            stdout = json.loads(result.stdout)
            self.assertEqual(written, stdout)


class NormalizeCLIIntegrationTests(unittest.TestCase):
    """CLI tests that validate normalization from ingest index input."""

    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = "src"
        return subprocess.run(
            [sys.executable, "-m", "covalent_design.data.normalize", *args],
            cwd=Path(__file__).resolve().parents[2],
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def write_interim(self, root: Path, fixture_names: tuple[str, ...]) -> None:
        root.mkdir(parents=True, exist_ok=True)
        records_path = root / "source_records.jsonl"
        with records_path.open("w", encoding="utf-8") as handle:
            for fixture_name in fixture_names:
                payload = json.loads((FIXTURE_ROOT / fixture_name).read_text(encoding="utf-8"))
                handle.write(json.dumps(payload, sort_keys=True))
                handle.write("\n")

    def test_normalize_cli_accepts_ingest_index_as_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            ingest_index_path = Path(tmp) / "ingest_index.json"
            ingest_index_path.write_text(json.dumps({
                "source_database": "covbinder_in_pdb",
                "source_version": "2026-05-21",
                "records": [],
                "failures": [],
            }))

            result = self.run_cli(
                "--ingest-index", str(ingest_index_path),
            )

            self.assertEqual(result.returncode, 0, result.stderr)

    def test_normalize_cli_rejects_missing_ingest_index_file(self):
        result = self.run_cli(
            "--ingest-index", "/nonexistent/path/index.json",
        )

        self.assertNotEqual(result.returncode, 0)

    def test_normalize_cli_interim_roundtrip_merges_and_excludes_conflicts(self):
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            interim_root = temp_root / "interim"
            out_root = temp_root / "processed"
            self.write_interim(interim_root, (
                "clean_record.json",
                "duplicate_a.json",
                "duplicate_b.json",
                "conflict_a.json",
                "conflict_b.json",
                "q0_unverified_atom_mapping.json",
                "q2_non_human.json",
            ))

            result = self.run_cli(
                "--interim-root", str(interim_root),
                "--out-root", str(out_root),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads(result.stdout)
            self.assertTrue(summary["ok"])
            self.assertEqual(summary["input_record_count"], 7)
            self.assertEqual(summary["accepted_record_count"], 3)
            self.assertEqual(summary["rejected_record_count"], 1)
            self.assertEqual(summary["conflict_group_count"], 1)
            self.assertEqual(summary["rejected_identity_input_count"], 0)
            self.assertTrue((out_root / "accepted.jsonl").exists())
            self.assertTrue((out_root / "rejected.jsonl").exists())
            self.assertTrue((out_root / "conflicts.jsonl").exists())

    def test_normalize_cli_summary_reports_reason_and_flag_sets(self):
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            interim_root = temp_root / "interim"
            out_root = temp_root / "processed"
            self.write_interim(interim_root, (
                "q0_missing_atom_mapping.json",
                "q1_resolution_outlier.json",
                "q2_missing_activity.json",
            ))

            result = self.run_cli(
                "--interim-root", str(interim_root),
                "--out-root", str(out_root),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads(result.stdout)
            self.assertEqual(
                set(summary["rejected_reason_counts"]),
                {"ATOM_MAPPING_MISSING", "RESOLUTION_GT_3A"},
            )
            self.assertEqual(
                set(summary["quality_flag_counts"]),
                {"missing_activity_data", "missing_assay_data"},
            )


if __name__ == "__main__":
    unittest.main()
