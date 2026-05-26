"""Task 14: build_splits contract and regression tests.

These tests define and preserve the public API and CLI contract for
leakage-aware covalent splits.

Key invariants under test:

* Primary scaffold overlap across train/val/test is **zero**.
* Same ``protein_cluster_id`` must NOT span multiple splits.
* Invalid / missing core-labels input produces a structured error and
  writes **no** partial split artifacts.
* Split artifacts live under a dedicated ``--out-root``; ``records.jsonl``
  and ``artifact_manifest.json`` are never mutated.
* No visual-check or quality-report artifacts are created (Task 15/16
  scope).
"""

import json
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from covalent_design.contracts import CONTRACT_VERSION, ContractEnvelope, ValidationReceipt
from covalent_design.data.splits import build_splits

# ---------------------------------------------------------------------------
# constants
# ---------------------------------------------------------------------------

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "splits"
RECORDS_ROOT = FIXTURE_ROOT / "records"

VALID_SPLITS = frozenset({"train", "val", "test", "excluded"})
CORE_SPLITS = frozenset({"train", "val", "test"})
VALID_FALLBACK_REASONS = frozenset({
    "warhead_unmatched",
    "missing_scaffold_input",
    "missing_protein_cluster_input",
    "manual_review_override",
})
VALID_REVIEW_STATUSES = frozenset({"pending", "approved", "rejected"})

REQUIRED_CORE_LABELS_KEYS = frozenset({
    "bond_type",
    "warhead_type",
    "residue_reaction_family",
    "pdb_id",
})

REQUIRED_SPLIT_INDEX_KEYS = frozenset({
    "schema_version",
    "contract_version",
    "role",
    "split_policy",
    "assignment_count",
    "assignments",
})

REQUIRED_LEAKAGE_REPORT_KEYS = frozenset({
    "schema_version",
    "contract_version",
    "role",
    "record_count",
    "train_count",
    "val_count",
    "test_count",
    "excluded_count",
    "fallback_count",
    "fallback_by_reason",
    "manual_review_count",
    "scaffold_overlaps",
    "protein_cluster_overlaps",
    "zero_overlap",
})

REQUIRED_ASSIGNMENT_KEYS = frozenset({
    "record_id",
    "split",
    "scaffold_key",
    "protein_cluster_id",
    "residue_reaction_family",
    "fallback_reason",
    "manual_review_status",
})

CLI_MODULE = "covalent_design.data.cli.build_splits"
FROZEN_CLI_PATH = f"python -m {CLI_MODULE}"

# scenario -> (records_file, split_index_dir)
SCENARIOS = [
    ("scaffold_leakage", "scaffold_leakage_records.jsonl", "scaffold_leakage"),
    ("scaffold_no_leakage", "scaffold_no_leakage_records.jsonl", "scaffold_no_leakage"),
    ("protein_cluster_leakage", "protein_cluster_leakage_records.jsonl", "protein_cluster_leakage"),
    ("warhead_unmatched", "warhead_unmatched_records.jsonl", "warhead_unmatched"),
    ("manual_review_override", "manual_review_override_records.jsonl", "manual_review_override"),
    ("missing_scaffold_inputs", "missing_scaffold_inputs_records.jsonl", "missing_scaffold_inputs"),
    ("missing_protein_cluster_inputs", "missing_protein_cluster_inputs_records.jsonl", "missing_protein_cluster_inputs"),
]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _load_json(path: Path) -> dict:
    return json.loads(path.read_text("utf-8"))


def _load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    if not path.exists():
        return rows
    for line in path.read_text("utf-8").splitlines():
        stripped = line.strip()
        if stripped:
            rows.append(json.loads(stripped))
    return rows


def _sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


# ---------------------------------------------------------------------------
# 1. Public API contract
# ---------------------------------------------------------------------------

class BuildSplitsPublicAPITests(unittest.TestCase):
    """``build_splits()`` must return a ``ContractEnvelope`` with a valid receipt."""

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = Path(tempfile.mkdtemp(prefix="task14_api_"))
        cls.out_root = cls.tmpdir / "splits_out"
        cls.out_root.mkdir()
        cls.records_path = RECORDS_ROOT / "scaffold_no_leakage_records.jsonl"

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def test_returns_contract_envelope(self):
        envelope = build_splits(
            records_path=self.records_path,
            out_root=self.out_root,
        )
        self.assertIsInstance(envelope, ContractEnvelope)

    def test_receipt_is_present_and_valid(self):
        envelope = build_splits(
            records_path=self.records_path,
            out_root=self.out_root,
        )
        self.assertIsInstance(envelope.receipt, ValidationReceipt)
        self.assertTrue(envelope.receipt.ok)

    def test_contract_version_is_current(self):
        envelope = build_splits(
            records_path=self.records_path,
            out_root=self.out_root,
        )
        self.assertEqual(envelope.receipt.contract_version, CONTRACT_VERSION)

    def test_receipt_contains_input_sha256(self):
        envelope = build_splits(
            records_path=self.records_path,
            out_root=self.out_root,
        )
        self.assertEqual(envelope.receipt.input_sha256, _sha256_file(self.records_path))


# ---------------------------------------------------------------------------
# 2. CLI contract
# ---------------------------------------------------------------------------

class BuildSplitsCLITests(unittest.TestCase):
    """CLI entry point contract."""

    @staticmethod
    def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = "src"
        return subprocess.run(
            [sys.executable, "-m", CLI_MODULE, *args],
            cwd=Path(__file__).resolve().parents[2],
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_cli_help_returns_zero(self):
        result = self._run_cli("--help")
        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_cli_valid_records_returns_zero_and_writes_artifacts(self):
        tmpdir = Path(tempfile.mkdtemp(prefix="task14_cli_valid_"))
        try:
            out_root = tmpdir / "splits_out"
            records_file = RECORDS_ROOT / "scaffold_no_leakage_records.jsonl"
            result = self._run_cli(
                "--records", str(records_file),
                "--out-root", str(out_root),
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertTrue((out_root / "split_index.json").exists(),
                            "split_index.json must be created")
            self.assertTrue((out_root / "leakage_report.json").exists(),
                            "leakage_report.json must be created")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_cli_invalid_missing_core_labels_returns_non_zero(self):
        tmpdir = Path(tempfile.mkdtemp(prefix="task14_cli_invalid_"))
        try:
            out_root = tmpdir / "splits_out"
            records_file = FIXTURE_ROOT / "invalid_missing_core_labels" / "records.jsonl"
            result = self._run_cli(
                "--records", str(records_file),
                "--out-root", str(out_root),
            )
            self.assertNotEqual(result.returncode, 0,
                                "CLI must return non-zero for invalid records")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_frozen_cli_path_is_correct(self):
        self.assertEqual(FROZEN_CLI_PATH, "python -m covalent_design.data.cli.build_splits")


# ---------------------------------------------------------------------------
# 3. Primary scaffold overlap MUST be zero
# ---------------------------------------------------------------------------

class ScaffoldLeakagePreventionTests(unittest.TestCase):
    """The core invariant: no scaffold key may appear in more than one split."""

    def _build_and_load(self, records_file_name: str) -> dict:
        tmpdir = Path(tempfile.mkdtemp(prefix="task14_scaffold_"))
        try:
            out_root = tmpdir / "splits_out"
            out_root.mkdir()
            records_path = RECORDS_ROOT / records_file_name
            build_splits(records_path=records_path, out_root=out_root)
            return _load_json(out_root / "split_index.json")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_scaffold_no_leakage_produces_zero_overlap(self):
        split_index = self._build_and_load("scaffold_no_leakage_records.jsonl")
        scaffold_to_splits: dict[str, set[str]] = {}
        for a in split_index["assignments"]:
            sk = a.get("scaffold_key")
            if sk is None:
                continue
            scaffold_to_splits.setdefault(sk, set()).add(a["split"])

        violations = {
            sk: splits
            for sk, splits in scaffold_to_splits.items()
            if len(splits) > 1
        }
        self.assertEqual(
            {},
            violations,
            f"scaffold keys found in multiple splits: {violations}",
        )

    def test_scaffold_leakage_input_must_be_corrected(self):
        """Feed records that share a scaffold; build_splits must assign the
        shared-scaffold records to the SAME split - NOT leak across splits."""
        split_index = self._build_and_load("scaffold_leakage_records.jsonl")
        scaffold_to_splits: dict[str, set[str]] = {}
        for a in split_index["assignments"]:
            sk = a.get("scaffold_key")
            if sk is None:
                continue
            scaffold_to_splits.setdefault(sk, set()).add(a["split"])

        violations = {
            sk: splits
            for sk, splits in scaffold_to_splits.items()
            if len(splits) > 1
        }
        self.assertEqual(
            {},
            violations,
            f"scaffold keys must NOT span multiple splits: {violations}",
        )

    def test_every_scaffold_key_appears_in_at_most_one_core_split(self):
        """Even counting only train/val/test (ignoring excluded), no scaffold
        may straddle two core splits."""
        for scenario_name, records_file, _ in SCENARIOS:
            with self.subTest(scenario=scenario_name):
                tmpdir = Path(tempfile.mkdtemp(prefix=f"task14_sc_{scenario_name}_"))
                try:
                    out_root = tmpdir / "splits_out"
                    out_root.mkdir()
                    records_path = RECORDS_ROOT / records_file
                    build_splits(records_path=records_path, out_root=out_root)
                    split_index = _load_json(out_root / "split_index.json")

                    scaffold_cores: dict[str, set[str]] = {}
                    for a in split_index["assignments"]:
                        sk = a.get("scaffold_key")
                        if sk is None or a["split"] == "excluded":
                            continue
                        scaffold_cores.setdefault(sk, set()).add(a["split"])

                    violations = {
                        sk: splits
                        for sk, splits in scaffold_cores.items()
                        if len(splits) > 1
                    }
                    self.assertEqual(
                        {},
                        violations,
                        f"[{scenario_name}] scaffold_key in multiple core splits: {violations}",
                    )
                finally:
                    shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# 4. Protein-cluster integrity
# ---------------------------------------------------------------------------

class ProteinClusterIntegrityTests(unittest.TestCase):
    """Records sharing a ``protein_cluster_id`` MUST reside in the same split."""

    def _build_and_get_assignments(self, records_file_name: str) -> list[dict]:
        tmpdir = Path(tempfile.mkdtemp(prefix="task14_pc_"))
        try:
            out_root = tmpdir / "splits_out"
            out_root.mkdir()
            records_path = RECORDS_ROOT / records_file_name
            build_splits(records_path=records_path, out_root=out_root)
            split_index = _load_json(out_root / "split_index.json")
            return split_index["assignments"]
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_same_cluster_same_split_no_leakage_input(self):
        assignments = self._build_and_get_assignments("scaffold_no_leakage_records.jsonl")
        cluster_to_splits: dict[str, set[str]] = {}
        for a in assignments:
            pc = a.get("protein_cluster_id")
            if not pc:
                continue
            cluster_to_splits.setdefault(pc, set()).add(a["split"])

        violations = {
            pc: splits
            for pc, splits in cluster_to_splits.items()
            if len(splits) > 1
        }
        self.assertEqual({}, violations,
                         f"protein_cluster_id spans multiple splits: {violations}")

    def test_protein_cluster_leakage_input_must_be_corrected(self):
        """Feed records where PC001 has two records in different pre-computed
        splits.  build_splits MUST place both PC001 records in the SAME split."""
        assignments = self._build_and_get_assignments("protein_cluster_leakage_records.jsonl")
        cluster_to_splits: dict[str, set[str]] = {}
        for a in assignments:
            pc = a.get("protein_cluster_id")
            if not pc:
                continue
            cluster_to_splits.setdefault(pc, set()).add(a["split"])

        violations = {
            pc: splits
            for pc, splits in cluster_to_splits.items()
            if len(splits) > 1
        }
        self.assertEqual(
            {},
            violations,
            f"protein_cluster_id must NOT span multiple splits (leakage input): {violations}",
        )

    def test_protein_cluster_leakage_fixture_can_be_used_as_input_risk_diagnostic(self):
        """The pre-existing protein_cluster_leakage fixture demonstrates what a
        leak looks like.  This test confirms the fixture is readable and
        contains a cross-split cluster so it can serve as a diagnostic tool."""
        split_index = _load_json(FIXTURE_ROOT / "protein_cluster_leakage" / "split_index.json")
        cluster_to_splits: dict[str, set[str]] = {}
        for a in split_index["assignments"]:
            pc = a.get("protein_cluster_id")
            if not pc:
                continue
            cluster_to_splits.setdefault(pc, set()).add(a["split"])

        self.assertTrue(
            any(len(splits) > 1 for splits in cluster_to_splits.values()),
            "protein_cluster_leakage fixture must exhibit a cross-split cluster "
            "to serve as an input risk diagnostic",
        )

    def test_every_scenario_preserves_cluster_integrity(self):
        for scenario_name, records_file, _ in SCENARIOS:
            with self.subTest(scenario=scenario_name):
                tmpdir = Path(tempfile.mkdtemp(prefix=f"task14_pci_{scenario_name}_"))
                try:
                    out_root = tmpdir / "splits_out"
                    out_root.mkdir()
                    records_path = RECORDS_ROOT / records_file
                    build_splits(records_path=records_path, out_root=out_root)
                    split_index = _load_json(out_root / "split_index.json")

                    cluster_to_splits: dict[str, set[str]] = {}
                    for a in split_index["assignments"]:
                        pc = a.get("protein_cluster_id")
                        if not pc:
                            continue
                        cluster_to_splits.setdefault(pc, set()).add(a["split"])

                    violations = {
                        pc: splits
                        for pc, splits in cluster_to_splits.items()
                        if len(splits) > 1
                    }
                    self.assertEqual(
                        {},
                        violations,
                        f"[{scenario_name}] protein_cluster across splits: {violations}",
                    )
                finally:
                    shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# 5. Fallback & exclusion accounting
# ---------------------------------------------------------------------------

class FallbackAndExclusionTests(unittest.TestCase):
    """Fallback records must be excluded from core splits unless approved."""

    def _build(self, records_file_name: str) -> Path:
        tmpdir = Path(tempfile.mkdtemp(prefix="task14_fallback_"))
        self.addCleanup(lambda: shutil.rmtree(tmpdir, ignore_errors=True))
        out_root = tmpdir / "splits_out"
        out_root.mkdir()
        records_path = RECORDS_ROOT / records_file_name
        build_splits(records_path=records_path, out_root=out_root)
        return out_root

    def test_warhead_unmatched_records_are_excluded(self):
        out_root = self._build("warhead_unmatched_records.jsonl")
        split_index = _load_json(out_root / "split_index.json")
        report = _load_json(out_root / "leakage_report.json")

        warhead_fallback = [
            a for a in split_index["assignments"]
            if a["fallback_reason"] == "warhead_unmatched"
        ]
        self.assertGreater(len(warhead_fallback), 0)
        for a in warhead_fallback:
            if a.get("manual_review_status") != "approved":
                self.assertEqual("excluded", a["split"],
                                 f"unapproved warhead_unmatched must be excluded: {a['record_id']}")

        self.assertGreater(report["fallback_by_reason"].get("warhead_unmatched", 0), 0)

    def test_missing_scaffold_input_records_are_excluded(self):
        out_root = self._build("missing_scaffold_inputs_records.jsonl")
        split_index = _load_json(out_root / "split_index.json")
        report = _load_json(out_root / "leakage_report.json")

        missing = [
            a for a in split_index["assignments"]
            if a["fallback_reason"] == "missing_scaffold_input"
        ]
        self.assertGreater(len(missing), 0)
        for a in missing:
            self.assertEqual("excluded", a["split"],
                             f"missing_scaffold_input must be excluded: {a['record_id']}")
            self.assertIsNone(a["scaffold_key"])

        self.assertGreater(report["fallback_by_reason"].get("missing_scaffold_input", 0), 0)

    def test_missing_protein_cluster_input_records_are_excluded(self):
        out_root = self._build("missing_protein_cluster_inputs_records.jsonl")
        split_index = _load_json(out_root / "split_index.json")
        report = _load_json(out_root / "leakage_report.json")

        missing = [
            a for a in split_index["assignments"]
            if a["fallback_reason"] == "missing_protein_cluster_input"
        ]
        self.assertGreater(len(missing), 0)
        for a in missing:
            self.assertEqual("excluded", a["split"],
                             f"missing_protein_cluster_input must be excluded: {a['record_id']}")

        self.assertGreater(report["fallback_by_reason"].get("missing_protein_cluster_input", 0), 0)

    def test_fallback_reasons_are_restricted_to_known_values(self):
        for scenario_name, records_file, _ in SCENARIOS:
            with self.subTest(scenario=scenario_name):
                tmpdir = Path(tempfile.mkdtemp(prefix=f"task14_fr_{scenario_name}_"))
                try:
                    out_root = tmpdir / "splits_out"
                    out_root.mkdir()
                    records_path = RECORDS_ROOT / records_file
                    build_splits(records_path=records_path, out_root=out_root)
                    split_index = _load_json(out_root / "split_index.json")
                    for a in split_index["assignments"]:
                        fr = a.get("fallback_reason")
                        if fr is not None:
                            self.assertIn(fr, VALID_FALLBACK_REASONS,
                                          f"[{scenario_name}] unknown fallback_reason: {fr}")
                finally:
                    shutil.rmtree(tmpdir, ignore_errors=True)

    def test_excluded_records_not_in_train_val_test_counts(self):
        out_root = self._build("warhead_unmatched_records.jsonl")
        report = _load_json(out_root / "leakage_report.json")
        total = report["train_count"] + report["val_count"] + report["test_count"] + report["excluded_count"]
        self.assertEqual(report["record_count"], total)


# ---------------------------------------------------------------------------
# 6. Manual review override
# ---------------------------------------------------------------------------

class ManualReviewOverrideTests(unittest.TestCase):
    """manual_review_status must be respected per the split spec."""

    def _build(self, records_file_name: str) -> Path:
        tmpdir = Path(tempfile.mkdtemp(prefix="task14_review_"))
        self.addCleanup(lambda: shutil.rmtree(tmpdir, ignore_errors=True))
        out_root = tmpdir / "splits_out"
        out_root.mkdir()
        records_path = RECORDS_ROOT / records_file_name
        build_splits(records_path=records_path, out_root=out_root)
        return out_root

    def test_approved_warhead_unmatched_can_be_in_core_split(self):
        out_root = self._build("manual_review_override_records.jsonl")
        split_index = _load_json(out_root / "split_index.json")

        approved_warhead = [
            a for a in split_index["assignments"]
            if (a["fallback_reason"] == "warhead_unmatched"
                and a["manual_review_status"] == "approved")
        ]
        self.assertGreater(len(approved_warhead), 0,
                           "expected at least one approved warhead_unmatched record")
        for a in approved_warhead:
            self.assertIn(a["split"], CORE_SPLITS,
                          f"approved record must be in train/val/test: {a['record_id']}")

    def test_approved_warhead_unmatched_scaffold_key_keeps_unmatched_evidence(self):
        out_root = self._build("manual_review_override_records.jsonl")
        rows = _load_jsonl(out_root / "scaffold_keys.jsonl")
        approved_row = next(
            row for row in rows
            if row["record_id"] == "MR000000000000000000000000000003"
        )
        self.assertEqual("warhead_unmatched", approved_row["fallback_reason"])
        self.assertFalse(approved_row["warhead_match"]["matched"])
        self.assertEqual("c1ccccc1", approved_row["scaffold_key"])

    def test_review_status_on_normal_record_does_not_create_fallback(self):
        tmpdir = Path(tempfile.mkdtemp(prefix="task14_review_normal_"))
        self.addCleanup(lambda: shutil.rmtree(tmpdir, ignore_errors=True))
        records = _load_jsonl(RECORDS_ROOT / "scaffold_no_leakage_records.jsonl")
        normal_id = records[0]["record_id"]
        records[0].setdefault("metadata", {})["manual_review_status"] = "approved"
        records_path = tmpdir / "records.jsonl"
        records_path.write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n",
            "utf-8",
        )
        out_root = tmpdir / "splits_out"
        out_root.mkdir()
        build_splits(records_path=records_path, out_root=out_root)
        split_index = _load_json(out_root / "split_index.json")
        normal_assignment = next(
            a for a in split_index["assignments"]
            if a["record_id"] == normal_id
        )
        self.assertIsNone(normal_assignment["fallback_reason"])
        self.assertEqual("approved", normal_assignment["manual_review_status"])
        review_index = _load_json(out_root / "manual_review_index.json")
        reviewed_ids = {
            r["record_id"] for r in review_index["reviewed_records"]
        }
        self.assertNotIn(normal_id, reviewed_ids)

    def test_pending_warhead_unmatched_is_excluded(self):
        out_root = self._build("manual_review_override_records.jsonl")
        split_index = _load_json(out_root / "split_index.json")

        pending = [
            a for a in split_index["assignments"]
            if a["manual_review_status"] == "pending"
        ]
        self.assertGreater(len(pending), 0)
        for a in pending:
            self.assertEqual("excluded", a["split"],
                             f"pending review must be excluded: {a['record_id']}")

    def test_manual_review_status_values_are_valid(self):
        for scenario_name, records_file, _ in SCENARIOS:
            with self.subTest(scenario=scenario_name):
                tmpdir = Path(tempfile.mkdtemp(prefix=f"task14_mr_{scenario_name}_"))
                try:
                    out_root = tmpdir / "splits_out"
                    out_root.mkdir()
                    records_path = RECORDS_ROOT / records_file
                    build_splits(records_path=records_path, out_root=out_root)
                    split_index = _load_json(out_root / "split_index.json")
                    for a in split_index["assignments"]:
                        status = a.get("manual_review_status")
                        if status is not None:
                            self.assertIn(status, VALID_REVIEW_STATUSES,
                                          f"[{scenario_name}] invalid review status: {status}")
                finally:
                    shutil.rmtree(tmpdir, ignore_errors=True)

    def test_manual_review_count_matches_split_index(self):
        out_root = self._build("manual_review_override_records.jsonl")
        split_index = _load_json(out_root / "split_index.json")
        report = _load_json(out_root / "leakage_report.json")

        expected = sum(
            1 for a in split_index["assignments"]
            if a.get("manual_review_status") is not None
        )
        self.assertEqual(expected, report["manual_review_count"])


# ---------------------------------------------------------------------------
# 7. Invalid input - structured errors, no partial artifacts
# ---------------------------------------------------------------------------

class InvalidInputErrorTests(unittest.TestCase):
    """Invalid records must produce structured errors and NEVER partial output."""

    def test_missing_core_labels_fields_produce_structured_error(self):
        tmpdir = Path(tempfile.mkdtemp(prefix="task14_invalid_err_"))
        try:
            out_root = tmpdir / "splits_out"
            out_root.mkdir()
            records_path = FIXTURE_ROOT / "invalid_missing_core_labels" / "records.jsonl"

            try:
                envelope = build_splits(records_path=records_path, out_root=out_root)
            except Exception:
                # Verify no partial artifacts were written.
                self._assert_no_partial_artifacts(out_root)
                return

            self.assertFalse(envelope.receipt.ok)
            self.assertGreater(len(envelope.receipt.errors), 0,
                               "must have at least one structured error")
            error_codes = {e.code for e in envelope.receipt.errors}
            self.assertTrue(
                any("CORE_LABEL" in code or "MISSING" in code or "INVALID" in code
                    for code in error_codes),
                f"no core-label-related error code in: {error_codes}",
            )
            self._assert_no_partial_artifacts(out_root)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_missing_core_labels_does_not_write_partial_split_artifacts(self):
        tmpdir = Path(tempfile.mkdtemp(prefix="task14_no_partial_"))
        try:
            out_root = tmpdir / "splits_out"
            out_root.mkdir()
            records_path = FIXTURE_ROOT / "invalid_missing_core_labels" / "records.jsonl"

            try:
                build_splits(records_path=records_path, out_root=out_root)
            except Exception:
                pass

            self._assert_no_partial_artifacts(out_root)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def _assert_no_partial_artifacts(self, out_root: Path) -> None:
        """If split_index.json exists, it must be empty or absent."""
        split_index = out_root / "split_index.json"
        if split_index.exists():
            content = split_index.read_text("utf-8").strip()
            self.assertEqual(
                "", content,
                "split_index.json must be empty or absent on invalid input",
            )
        leakage = out_root / "leakage_report.json"
        if leakage.exists():
            content = leakage.read_text("utf-8").strip()
            self.assertEqual(
                "", content,
                "leakage_report.json must be empty or absent on invalid input",
            )

    def test_missing_residue_reaction_family_is_error(self):
        """IC-2 is missing residue_reaction_family and warhead_type - must error."""
        records = _load_jsonl(FIXTURE_ROOT / "invalid_missing_core_labels" / "records.jsonl")
        ic2 = next(r for r in records if r["record_id"] == "IC000000000000000000000000000002")
        missing = REQUIRED_CORE_LABELS_KEYS - set(ic2.get("core_labels", {}))
        self.assertGreater(len(missing), 0,
                           f"IC-2 fixture should be missing core_labels fields, got: {missing}")

    def test_missing_entire_core_labels_is_error(self):
        """IC-4 has no core_labels key at all - must error."""
        records = _load_jsonl(FIXTURE_ROOT / "invalid_missing_core_labels" / "records.jsonl")
        ic4 = next(r for r in records if r["record_id"] == "IC000000000000000000000000000004")
        self.assertNotIn("core_labels", ic4,
                         "IC-4 must have no core_labels key")


# ---------------------------------------------------------------------------
# 8. Output artifact schema
# ---------------------------------------------------------------------------

class OutputArtifactSchemaTests(unittest.TestCase):
    """Every output artifact must conform to its schema."""

    def _build(self, records_file_name: str) -> Path:
        tmpdir = Path(tempfile.mkdtemp(prefix="task14_schema_"))
        self.addCleanup(lambda: shutil.rmtree(tmpdir, ignore_errors=True))
        out_root = tmpdir / "splits_out"
        out_root.mkdir()
        records_path = RECORDS_ROOT / records_file_name
        build_splits(records_path=records_path, out_root=out_root)
        return out_root

    # -- split_index.json --------------------------------------------------

    def test_split_index_has_required_top_level_keys(self):
        out_root = self._build("scaffold_no_leakage_records.jsonl")
        split_index = _load_json(out_root / "split_index.json")
        missing = REQUIRED_SPLIT_INDEX_KEYS - set(split_index)
        self.assertEqual(set(), missing, f"split_index missing keys: {missing}")

    def test_split_index_role_is_split_index(self):
        out_root = self._build("scaffold_no_leakage_records.jsonl")
        split_index = _load_json(out_root / "split_index.json")
        self.assertEqual("split_index", split_index["role"])

    def test_split_index_versions_are_current(self):
        out_root = self._build("scaffold_no_leakage_records.jsonl")
        split_index = _load_json(out_root / "split_index.json")
        self.assertEqual("1", split_index["schema_version"])
        self.assertEqual("1.0.0", split_index["contract_version"])

    def test_split_policy_has_required_keys(self):
        out_root = self._build("scaffold_no_leakage_records.jsonl")
        split_index = _load_json(out_root / "split_index.json")
        policy = split_index["split_policy"]
        self.assertIn("algorithm", policy)
        self.assertIn("algorithm_version", policy)
        self.assertIn("random_seed", policy)
        self.assertIn("split_ratios", policy)
        self.assertIsInstance(policy["random_seed"], int)

    def test_split_ratios_sum_to_one(self):
        out_root = self._build("scaffold_no_leakage_records.jsonl")
        split_index = _load_json(out_root / "split_index.json")
        ratios = split_index["split_policy"]["split_ratios"]
        self.assertIn("train", ratios)
        self.assertIn("val", ratios)
        self.assertIn("test", ratios)
        ratio_sum = sum(ratios.values())
        self.assertTrue(0.99 <= ratio_sum <= 1.01,
                        f"split ratios must sum to ~1.0, got {ratio_sum}")

    def test_assignment_count_matches_actual(self):
        out_root = self._build("scaffold_no_leakage_records.jsonl")
        split_index = _load_json(out_root / "split_index.json")
        self.assertEqual(len(split_index["assignments"]), split_index["assignment_count"])

    def test_every_assignment_has_required_keys(self):
        out_root = self._build("scaffold_no_leakage_records.jsonl")
        split_index = _load_json(out_root / "split_index.json")
        for i, a in enumerate(split_index["assignments"]):
            missing = REQUIRED_ASSIGNMENT_KEYS - set(a)
            self.assertEqual(set(), missing,
                             f"assignment {i} missing keys: {missing}")

    def test_splits_use_valid_values(self):
        out_root = self._build("scaffold_no_leakage_records.jsonl")
        split_index = _load_json(out_root / "split_index.json")
        for a in split_index["assignments"]:
            self.assertIn(a["split"], VALID_SPLITS,
                          f"invalid split value: {a['split']}")

    def test_no_duplicate_record_ids_in_assignments(self):
        out_root = self._build("scaffold_no_leakage_records.jsonl")
        split_index = _load_json(out_root / "split_index.json")
        ids = [a["record_id"] for a in split_index["assignments"]]
        self.assertEqual(len(ids), len(set(ids)),
                         "duplicate record_id in assignments")

    def test_record_ids_in_split_index_match_input_records(self):
        out_root = self._build("scaffold_no_leakage_records.jsonl")
        split_index = _load_json(out_root / "split_index.json")
        records = _load_jsonl(RECORDS_ROOT / "scaffold_no_leakage_records.jsonl")

        index_ids = {a["record_id"] for a in split_index["assignments"]}
        record_ids = {r["record_id"] for r in records}
        self.assertEqual(record_ids, index_ids,
                         "split_index record_ids must match input record_ids exactly")

    # -- leakage_report.json -----------------------------------------------

    def test_leakage_report_has_required_keys(self):
        out_root = self._build("scaffold_no_leakage_records.jsonl")
        report = _load_json(out_root / "leakage_report.json")
        missing = REQUIRED_LEAKAGE_REPORT_KEYS - set(report)
        self.assertEqual(set(), missing, f"leakage_report missing keys: {missing}")

    def test_leakage_report_role_is_leakage_report(self):
        out_root = self._build("scaffold_no_leakage_records.jsonl")
        report = _load_json(out_root / "leakage_report.json")
        self.assertEqual("leakage_report", report["role"])

    def test_leakage_report_zero_overlap_is_boolean_dict(self):
        out_root = self._build("scaffold_no_leakage_records.jsonl")
        report = _load_json(out_root / "leakage_report.json")
        self.assertIsInstance(report["zero_overlap"], dict)
        self.assertIsInstance(report["zero_overlap"]["scaffold"], bool)
        self.assertIsInstance(report["zero_overlap"]["protein_cluster"], bool)

    def test_scaffold_overlap_entries_have_required_fields(self):
        out_root = self._build("scaffold_no_leakage_records.jsonl")
        report = _load_json(out_root / "leakage_report.json")
        for overlap in report["scaffold_overlaps"]:
            self.assertIn("scaffold_key", overlap)
            self.assertIn("overlapping_splits", overlap)
            self.assertIn("record_ids", overlap)
            self.assertGreater(len(overlap["overlapping_splits"]), 1,
                               "overlap entry must list >=2 splits")
            self.assertIsInstance(overlap["record_ids"], list)

    def test_protein_cluster_overlap_entries_have_required_fields(self):
        """The pre-existing protein_cluster_leakage fixture serves as a diagnostic
        reference; its leak entries must be well-formed."""
        report = _load_json(FIXTURE_ROOT / "protein_cluster_leakage" / "leakage_report.json")
        self.assertGreater(len(report["protein_cluster_overlaps"]), 0,
                           "fixture must exhibit protein cluster overlaps for diagnostic use")
        for overlap in report["protein_cluster_overlaps"]:
            self.assertIn("protein_cluster_id", overlap)
            self.assertIn("overlapping_splits", overlap)
            self.assertIn("record_ids", overlap)
            self.assertIsInstance(overlap["record_ids"], list)
            self.assertGreater(len(overlap["record_ids"]), 0)

    # -- fallback_accounting.json (if produced) ----------------------------

    def test_fallback_accounting_matches_split_index(self):
        out_root = self._build("warhead_unmatched_records.jsonl")
        split_index = _load_json(out_root / "split_index.json")
        report = _load_json(out_root / "leakage_report.json")

        fallback_count = sum(
            1 for a in split_index["assignments"]
            if a.get("fallback_reason") is not None
        )
        self.assertEqual(fallback_count, report["fallback_count"])
        self.assertIsInstance(report["fallback_by_reason"], dict)


# ---------------------------------------------------------------------------
# 9. Non-mutation of input files
# ---------------------------------------------------------------------------

class NonMutationTests(unittest.TestCase):
    """build_splits MUST NOT mutate records.jsonl or artifact_manifest.json."""

    def test_build_splits_does_not_mutate_input_records(self):
        tmpdir = Path(tempfile.mkdtemp(prefix="task14_nomutate_"))
        try:
            src = RECORDS_ROOT / "scaffold_no_leakage_records.jsonl"
            original_bytes = src.read_bytes()

            out_root = tmpdir / "splits_out"
            out_root.mkdir()
            build_splits(records_path=src, out_root=out_root)

            after_bytes = src.read_bytes()
            self.assertEqual(original_bytes, after_bytes,
                             "build_splits must not mutate input records file")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_output_written_only_under_out_root(self):
        tmpdir = Path(tempfile.mkdtemp(prefix="task14_outroot_"))
        try:
            src = RECORDS_ROOT / "scaffold_no_leakage_records.jsonl"
            out_root = tmpdir / "splits_out"
            out_root.mkdir()

            # Capture what exists in tmpdir before the call.
            before = set(tmpdir.rglob("*"))

            build_splits(records_path=src, out_root=out_root)

            after = set(tmpdir.rglob("*"))
            new_files = after - before
            for f in new_files:
                self.assertTrue(
                    str(f).startswith(str(out_root)),
                    f"new file outside out_root: {f}",
                )
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# 10. No visual-check or quality-report cross-contamination
# ---------------------------------------------------------------------------

class NoVisualCheckOrQualityReportTests(unittest.TestCase):
    """Task 14 MUST NOT produce Task 15/16 artifacts."""

    def _build(self, records_file_name: str) -> Path:
        tmpdir = Path(tempfile.mkdtemp(prefix="task14_noviz_"))
        self.addCleanup(lambda: shutil.rmtree(tmpdir, ignore_errors=True))
        out_root = tmpdir / "splits_out"
        out_root.mkdir()
        records_path = RECORDS_ROOT / records_file_name
        build_splits(records_path=records_path, out_root=out_root)
        return out_root

    def test_no_visual_check_artifact_written(self):
        out_root = self._build("scaffold_no_leakage_records.jsonl")
        all_files = [p.name for p in out_root.rglob("*") if p.is_file()]
        self.assertNotIn("visual_check_index.json", all_files)
        for name in all_files:
            self.assertNotIn("visual_check", name.lower(),
                             f"visual-check-related file found: {name}")

    def test_no_quality_report_artifact_written(self):
        out_root = self._build("scaffold_no_leakage_records.jsonl")
        all_files = [p.name for p in out_root.rglob("*") if p.is_file()]
        for name in all_files:
            self.assertNotIn("quality_report", name.lower(),
                             f"quality-report-related file found: {name}")

    def test_no_etl_quality_report_written(self):
        out_root = self._build("scaffold_no_leakage_records.jsonl")
        report_path = out_root / "etl_quality_report.md"
        self.assertFalse(report_path.exists(),
                         "etl_quality_report.md must NOT be written by build_splits")


# ---------------------------------------------------------------------------
# 11. Count conservation
# ---------------------------------------------------------------------------

class CountConservationTests(unittest.TestCase):
    """accepted = train + val + test + excluded."""

    def _build(self, records_file_name: str) -> tuple[dict, dict]:
        tmpdir = Path(tempfile.mkdtemp(prefix="task14_conserve_"))
        self.addCleanup(lambda: shutil.rmtree(tmpdir, ignore_errors=True))
        out_root = tmpdir / "splits_out"
        out_root.mkdir()
        records_path = RECORDS_ROOT / records_file_name
        build_splits(records_path=records_path, out_root=out_root)
        return (
            _load_json(out_root / "split_index.json"),
            _load_json(out_root / "leakage_report.json"),
        )

    def test_counts_conserve_accepted_equals_split_sum(self):
        for scenario_name, records_file, _ in SCENARIOS:
            with self.subTest(scenario=scenario_name):
                split_index, report = self._build(records_file)

                counts = {"train": 0, "val": 0, "test": 0, "excluded": 0}
                for a in split_index["assignments"]:
                    counts[a["split"]] += 1

                total = sum(counts.values())
                self.assertEqual(len(split_index["assignments"]), total)
                self.assertEqual(report["record_count"], total)
                self.assertEqual(report["train_count"], counts["train"])
                self.assertEqual(report["val_count"], counts["val"])
                self.assertEqual(report["test_count"], counts["test"])
                self.assertEqual(report["excluded_count"], counts["excluded"])

    def test_leakage_report_self_consistent(self):
        for scenario_name, records_file, _ in SCENARIOS:
            with self.subTest(scenario=scenario_name):
                split_index, report = self._build(records_file)

                self.assertEqual(
                    report["record_count"],
                    report["train_count"] + report["val_count"]
                    + report["test_count"] + report["excluded_count"],
                    f"[{scenario_name}] record count must equal split sum",
                )


# ---------------------------------------------------------------------------
# 12. Default policy
# ---------------------------------------------------------------------------

class DefaultPolicyTests(unittest.TestCase):
    """Default split ratios 80/10/10, seed 42."""

    def _build(self, records_file_name: str) -> dict:
        tmpdir = Path(tempfile.mkdtemp(prefix="task14_policy_"))
        self.addCleanup(lambda: shutil.rmtree(tmpdir, ignore_errors=True))
        out_root = tmpdir / "splits_out"
        out_root.mkdir()
        records_path = RECORDS_ROOT / records_file_name
        build_splits(records_path=records_path, out_root=out_root)
        return _load_json(out_root / "split_index.json")

    def test_default_algorithm_is_leakage_aware_covalent_splits(self):
        split_index = self._build("scaffold_no_leakage_records.jsonl")
        self.assertEqual(
            "leakage_aware_covalent_splits",
            split_index["split_policy"]["algorithm"],
        )

    def test_default_random_seed_is_42(self):
        split_index = self._build("scaffold_no_leakage_records.jsonl")
        self.assertEqual(42, split_index["split_policy"]["random_seed"])

    def test_default_ratios_are_80_10_10(self):
        split_index = self._build("scaffold_no_leakage_records.jsonl")
        ratios = split_index["split_policy"]["split_ratios"]
        self.assertEqual(0.8, ratios.get("train", 0))
        self.assertEqual(0.1, ratios.get("val", 0))
        self.assertEqual(0.1, ratios.get("test", 0))


if __name__ == "__main__":
    unittest.main()
