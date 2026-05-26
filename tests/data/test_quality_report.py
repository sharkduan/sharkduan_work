"""Task 16: write_quality_report contract and regression tests.

These tests define the public API and CLI contract for the ETL quality report
that reconciles sources, records, candidates, splits, and visual checks.

Key invariants under test:

* Source coverage reports per-source ``complete_for_v1`` gates.
* Accepted, rejected, conflict, and visual-blocked counts reconcile.
* Family, residue, and warhead distributions are derived from core_labels.
* Linkage quality, geometry quality, and protein chemical-state quality
  sections are present with correct stats.
* Candidate stats aggregate across all edge_candidates artifacts.
* Split stats come from split_index.json.
* Visual check index summary includes status_counts and blocking_counts.
* ``pending``, ``fail``, and ``needs_rule_review`` statuses all block
  first-core release; only ``pass`` is non-blocking.
* Missing required input artifacts produce structured ``ContractErrorInfo``
  with ``receipt.ok=False`` and no partial output.
* Inconsistent counts produce a structured error.
* CLI valid input exits zero; invalid input exits non-zero.
* Output is byte-deterministic across repeated runs with identical inputs.
* No model or training artifacts are generated.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# constants
# ---------------------------------------------------------------------------

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "quality_report"
VALID_ROOT = FIXTURE_ROOT / "valid"
MISSING_INGEST_ROOT = FIXTURE_ROOT / "missing_ingest"
INCONSISTENT_COUNTS_ROOT = FIXTURE_ROOT / "inconsistent_counts"

VALID_RECORDS_PATH = VALID_ROOT / "records.jsonl"
VALID_INGEST_ROOTS = [
    VALID_ROOT / "ingest" / "covbinder_in_pdb",
    VALID_ROOT / "ingest" / "covpdb",
]
VALID_SPLITS_ROOT = VALID_ROOT / "splits"
VALID_VISUAL_CHECKS_ROOT = VALID_ROOT / "visual_checks"

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

_IMPORT_ERROR = None
try:
    from covalent_design.data.quality_report import write_quality_report

    _HAS_MODULE = True
except ImportError as exc:
    _IMPORT_ERROR = exc
    _HAS_MODULE = False
    write_quality_report = None  # type: ignore[assignment]


def _sha256_json(data: object) -> str:
    payload = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped:
            rows.append(json.loads(stripped))
    return rows


# ---------------------------------------------------------------------------
# fixture sanity checks
# ---------------------------------------------------------------------------


class FixtureSanityTests(unittest.TestCase):
    """Verify that fixture files are well-formed JSON and internally consistent."""

    def test_valid_records_jsonl_loads(self):
        records = _load_jsonl(VALID_RECORDS_PATH)
        self.assertEqual(len(records), 3, "valid fixture expects 3 accepted records")
        for rec in records:
            self.assertIn("record_id", rec)
            self.assertIn("core_labels", rec)
            self.assertIn("artifacts", rec)
            roles = {a.get("role") for a in rec["artifacts"]}
            self.assertIn("edge_candidates", roles)

    def test_valid_rejected_index_loads(self):
        rejected = _load_jsonl(VALID_ROOT / "rejected_index.jsonl")
        self.assertEqual(len(rejected), 2)
        for row in rejected:
            self.assertIn("record_id", row)
            self.assertIn("reason", row)

    def test_valid_conflict_index_loads(self):
        conflicts = _load_jsonl(VALID_ROOT / "conflict_index.jsonl")
        self.assertEqual(len(conflicts), 1)
        self.assertIn("conflict_group_id", conflicts[0])

    def test_valid_edge_candidates_load(self):
        for rec_id in ("REC001", "REC002", "REC003"):
            path = VALID_ROOT / "artifacts" / rec_id / "edge_candidates.json"
            ec = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(ec["record_id"], rec_id)
            self.assertEqual(ec["role"], "edge_candidates")
            self.assertIn("denominators", ec)
            self.assertIn("positive_edge", ec)

    def test_valid_ingest_indexes_load(self):
        for src_dir in ("covbinder_in_pdb", "covpdb"):
            path = VALID_ROOT / "ingest" / src_dir / "ingest_index.json"
            idx = json.loads(path.read_text(encoding="utf-8"))
            self.assertIn("complete_for_v1", idx)
            self.assertIn("record_count", idx)

    def test_valid_split_index_loads(self):
        path = VALID_ROOT / "splits" / "split_index.json"
        si = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(si["role"], "split_index")
        self.assertIn("assignments", si)
        self.assertIn("split_policy", si)

    def test_valid_visual_check_index_loads(self):
        path = VALID_ROOT / "visual_checks" / "visual_check_index.json"
        vci = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(vci["role"], "visual_check_index")
        self.assertIn("status_counts", vci)
        self.assertIn("blocking_counts", vci)
        self.assertIn("pending", vci["status_counts"])
        self.assertIn("pass", vci["status_counts"])
        self.assertIn("needs_rule_review", vci["status_counts"])

    def test_missing_ingest_fixture_loads(self):
        records = _load_jsonl(MISSING_INGEST_ROOT / "records.jsonl")
        self.assertGreater(len(records), 0)

    def test_inconsistent_counts_fixture_loads(self):
        records = _load_jsonl(INCONSISTENT_COUNTS_ROOT / "records.jsonl")
        self.assertGreater(len(records), 0)
        # Verify ingest index exists
        ingest_path = INCONSISTENT_COUNTS_ROOT / "ingest" / "covbinder_in_pdb" / "ingest_index.json"
        self.assertTrue(ingest_path.exists())


# ---------------------------------------------------------------------------
# contract tests
# ---------------------------------------------------------------------------


class QualityReportContractTests(unittest.TestCase):
    """Tests for the write_quality_report function.

    These require the production module to exist.
    """

    # -- source coverage ----------------------------------------------------

    def test_source_coverage_includes_all_sources(self):
        """Per-source complete_for_v1 and record counts appear in source_coverage."""
        envelope = write_quality_report(
            processed_root=VALID_ROOT,
            ingest_roots=VALID_INGEST_ROOTS,
        )
        self.assertTrue(envelope.receipt.ok)
        report = envelope.payload

        self.assertIn("source_coverage", report)
        sc = report["source_coverage"]
        self.assertIsInstance(sc, dict)

        # Both ingest sources should appear
        source_names = set(sc.keys())
        self.assertIn("covbinder_in_pdb", source_names)
        self.assertIn("covpdb", source_names)

    def test_per_source_complete_for_v1_reported(self):
        """Each source reports its complete_for_v1 flag."""
        envelope = write_quality_report(
            processed_root=VALID_ROOT,
            ingest_roots=VALID_INGEST_ROOTS,
        )
        report = envelope.payload
        sc = report["source_coverage"]

        # covbinder_in_pdb has complete_for_v1: true
        self.assertTrue(
            sc["covbinder_in_pdb"]["complete_for_v1"],
            "covbinder_in_pdb should be complete_for_v1: true",
        )
        # covpdb has complete_for_v1: true
        self.assertTrue(
            sc["covpdb"]["complete_for_v1"],
            "covpdb should be complete_for_v1: true",
        )

    def test_source_coverage_includes_record_and_failure_counts(self):
        """Each source entry includes record_count and failure_count."""
        envelope = write_quality_report(
            processed_root=VALID_ROOT,
            ingest_roots=VALID_INGEST_ROOTS,
        )
        report = envelope.payload
        for source_name, entry in report["source_coverage"].items():
            with self.subTest(source=source_name):
                self.assertIn("record_count", entry)
                self.assertIn("failure_count", entry)
                self.assertIsInstance(entry["record_count"], int)
                self.assertIsInstance(entry["failure_count"], int)

    # -- reconciliation -----------------------------------------------------

    def test_accepted_rejected_conflict_counts_present(self):
        """Reconciliation section includes accepted, rejected, and conflict counts."""
        envelope = write_quality_report(
            processed_root=VALID_ROOT,
            ingest_roots=VALID_INGEST_ROOTS,
        )
        report = envelope.payload

        self.assertIn("reconciliation", report, "Report must have reconciliation section")
        rec = report["reconciliation"]
        self.assertEqual(rec["accepted_count"], 3, "3 accepted records in valid fixture")
        self.assertEqual(rec["rejected_count"], 2, "2 rejected records in valid fixture")
        self.assertEqual(rec["conflict_count"], 1, "1 conflict group in valid fixture")

    def test_visual_blocked_count_in_reconciliation(self):
        """Visual-blocked count represents records blocked by visual check status."""
        envelope = write_quality_report(
            processed_root=VALID_ROOT,
            ingest_roots=VALID_INGEST_ROOTS,
            visual_checks_root=VALID_VISUAL_CHECKS_ROOT,
        )
        report = envelope.payload
        rec = report["reconciliation"]

        self.assertIn("visual_blocked_count", rec)
        # pending=1 + needs_rule_review=1 = 2 blocked
        self.assertEqual(
            rec["visual_blocked_count"],
            2,
            "2 records are visual-blocked (pending + needs_rule_review)",
        )

    def test_counts_reconcile(self):
        """accepted + rejected + conflict equals total accounted records."""
        envelope = write_quality_report(
            processed_root=VALID_ROOT,
            ingest_roots=VALID_INGEST_ROOTS,
            visual_checks_root=VALID_VISUAL_CHECKS_ROOT,
        )
        report = envelope.payload
        rec = report["reconciliation"]

        self.assertIn("reconciled", rec)
        self.assertIn("total_accounted", rec)
        accounted = rec["accepted_count"] + rec["rejected_count"] + rec["conflict_count"]
        self.assertEqual(rec["total_accounted"], accounted)

    # -- family distribution -------------------------------------------------

    def test_family_distribution(self):
        """Family distribution is derived from core_labels.residue_reaction_family."""
        envelope = write_quality_report(processed_root=VALID_ROOT)
        report = envelope.payload

        self.assertIn("family_distribution", report)
        fd = report["family_distribution"]
        self.assertIsInstance(fd, dict)
        self.assertEqual(fd.get("CYS_Michael_addition"), 2, "2 CYS_Michael_addition records")
        self.assertEqual(fd.get("LYS_SN2"), 1, "1 LYS_SN2 record")

    def test_residue_distribution(self):
        """Residue distribution is derived from residue_reaction_family residue token."""
        envelope = write_quality_report(processed_root=VALID_ROOT)
        report = envelope.payload

        self.assertIn("residue_distribution", report)
        rd = report["residue_distribution"]
        self.assertIsInstance(rd, dict)
        self.assertGreaterEqual(rd.get("CYS", 0), 2)
        self.assertGreaterEqual(rd.get("LYS", 0), 1)

    def test_warhead_distribution(self):
        """Warhead distribution is derived from core_labels.warhead_type."""
        envelope = write_quality_report(processed_root=VALID_ROOT)
        report = envelope.payload

        self.assertIn("warhead_distribution", report)
        wd = report["warhead_distribution"]
        self.assertIsInstance(wd, dict)
        self.assertEqual(wd.get("acrylamide"), 2, "2 acrylamide records")
        self.assertEqual(wd.get("chloroacetamide"), 1, "1 chloroacetamide record")

    # -- linkage quality -----------------------------------------------------

    def test_linkage_quality_bond_type_distribution(self):
        """Linkage quality section shows bond_type distribution."""
        envelope = write_quality_report(processed_root=VALID_ROOT)
        report = envelope.payload

        self.assertIn("linkage_quality", report)
        lq = report["linkage_quality"]
        self.assertIn("bond_type_distribution", lq)
        btd = lq["bond_type_distribution"]
        self.assertIsInstance(btd, dict)
        self.assertGreaterEqual(btd.get("covalent", 0), 3)

    def test_linkage_quality_linkage_count_distribution(self):
        """Linkage quality section includes linkage count distribution."""
        envelope = write_quality_report(processed_root=VALID_ROOT)
        report = envelope.payload

        lq = report["linkage_quality"]
        self.assertIn("linkage_count_distribution", lq)

    # -- geometry quality ----------------------------------------------------

    def test_geometry_quality_stats(self):
        """Geometry quality section aggregates geometry attributes from metadata."""
        envelope = write_quality_report(processed_root=VALID_ROOT)
        report = envelope.payload

        self.assertIn("geometry_quality", report)
        gq = report["geometry_quality"]
        for key in ("bond_length", "protein_side_angle", "ligand_side_angle"):
            with self.subTest(geometry_stat=key):
                self.assertIn(key, gq, f"geometry_quality must include {key}")
                stat = gq[key]
                for stat_key in ("min", "max", "mean", "count"):
                    self.assertIn(stat_key, stat, f"{key} stat missing {stat_key}")

        # 3 records have geometry in valid fixture
        self.assertEqual(gq["bond_length"]["count"], 3)

    def test_geometry_quality_records_missing_geometry(self):
        """Geometry quality reports count of records with no geometry data."""
        envelope = write_quality_report(processed_root=VALID_ROOT)
        report = envelope.payload

        gq = report["geometry_quality"]
        self.assertIn("records_missing_geometry", gq)
        self.assertEqual(gq["records_missing_geometry"], 0)

    # -- protein chemical-state quality ---------------------------------------

    def test_protein_chemical_state_quality(self):
        """Protein chemical-state quality section reports explicit vs inferred states."""
        envelope = write_quality_report(processed_root=VALID_ROOT)
        report = envelope.payload

        self.assertIn("protein_chemical_state_quality", report)
        pcs = report["protein_chemical_state_quality"]
        self.assertIn("explicit_state_count", pcs)
        self.assertIn("inferred_state_count", pcs)
        # REC001 and REC002 are explicit, REC003 is inferred
        self.assertEqual(pcs["explicit_state_count"], 2)
        self.assertEqual(pcs["inferred_state_count"], 1)

    def test_protein_chemical_state_summarizes_flags(self):
        """Protein chemical-state section flags records with inferred state."""
        envelope = write_quality_report(processed_root=VALID_ROOT)
        report = envelope.payload

        pcs = report["protein_chemical_state_quality"]
        self.assertIn("records_with_inferred_state", pcs)
        self.assertIsInstance(pcs["records_with_inferred_state"], list)

    # -- candidate stats -----------------------------------------------------

    def test_candidate_stats_from_edge_artifacts(self):
        """Candidate stats aggregate denominator fields from edge_candidates artifacts."""
        envelope = write_quality_report(processed_root=VALID_ROOT)
        report = envelope.payload

        self.assertIn("candidate_stats", report)
        cs = report["candidate_stats"]
        # These fields must be present and aggregated across records
        for field in (
            "total_candidates",
            "total_natural_candidates",
            "total_forced_positives",
            "empty_radius_window_count",
            "record_count",
        ):
            with self.subTest(field=field):
                self.assertIn(field, cs)
                self.assertIsInstance(cs[field], int)

        # 3 records, edge candidates artifact for each
        self.assertEqual(cs["record_count"], 3)
        # REC001: 4, REC002: 3, REC003: 6 -> total 13
        self.assertEqual(cs["total_candidates"], 13)
        # All are natural positives, no forced positives
        self.assertEqual(cs["total_forced_positives"], 0)
        # No empty radius windows
        self.assertEqual(cs["empty_radius_window_count"], 0)

    # -- split stats ---------------------------------------------------------

    def test_split_stats_from_split_index(self):
        """Split stats are derived from split_index.json."""
        envelope = write_quality_report(
            processed_root=VALID_ROOT,
            splits_root=VALID_SPLITS_ROOT,
        )
        report = envelope.payload

        self.assertIn("split_stats", report)
        ss = report["split_stats"]
        for field in ("train_count", "val_count", "test_count", "excluded_count"):
            with self.subTest(field=field):
                self.assertIn(field, ss)
                self.assertIsInstance(ss[field], int)

        self.assertEqual(ss["train_count"], 2)
        self.assertEqual(ss["val_count"], 1)
        self.assertEqual(ss["excluded_count"], 0)

    def test_split_stats_fallback_count(self):
        """Split stats include fallback count from split assignments."""
        envelope = write_quality_report(
            processed_root=VALID_ROOT,
            splits_root=VALID_SPLITS_ROOT,
        )
        report = envelope.payload
        ss = report["split_stats"]
        self.assertIn("fallback_count", ss)
        self.assertEqual(ss["fallback_count"], 0)

    def test_split_stats_omitted_when_no_splits_root(self):
        """When splits_root is None, split_stats is omitted or empty."""
        envelope = write_quality_report(processed_root=VALID_ROOT, splits_root=None)
        report = envelope.payload
        # Split stats should be absent or all zeros
        ss = report.get("split_stats")
        if ss is not None:
            total = sum(
                ss.get(k, 0) for k in ("train_count", "val_count", "test_count", "excluded_count")
            )
            self.assertEqual(total, 0, "split_stats should be zero when no splits_root")

    # -- visual check index summary ------------------------------------------

    def test_visual_check_index_summary(self):
        """Visual check index summary is derived from visual_check_index.json."""
        envelope = write_quality_report(
            processed_root=VALID_ROOT,
            visual_checks_root=VALID_VISUAL_CHECKS_ROOT,
        )
        report = envelope.payload

        self.assertIn("visual_check_summary", report)
        vcs = report["visual_check_summary"]
        for field in ("sampled_count", "total_accepted", "status_counts", "blocking_counts"):
            with self.subTest(field=field):
                self.assertIn(field, vcs)

        self.assertEqual(vcs["sampled_count"], 3)
        self.assertEqual(vcs["total_accepted"], 3)

    def test_visual_check_status_counts_match_fixture(self):
        """Status counts in the report match visual_check_index.json."""
        envelope = write_quality_report(
            processed_root=VALID_ROOT,
            visual_checks_root=VALID_VISUAL_CHECKS_ROOT,
        )
        vcs = envelope.payload["visual_check_summary"]
        sc = vcs["status_counts"]
        self.assertEqual(sc["pending"], 1)
        self.assertEqual(sc["pass"], 1)
        self.assertEqual(sc["fail"], 0)
        self.assertEqual(sc["needs_rule_review"], 1)

    def test_pending_fail_needs_rule_review_blocking(self):
        """pending, fail, and needs_rule_review statuses are all blocking."""
        envelope = write_quality_report(
            processed_root=VALID_ROOT,
            visual_checks_root=VALID_VISUAL_CHECKS_ROOT,
        )
        vcs = envelope.payload["visual_check_summary"]
        bc = vcs["blocking_counts"]
        self.assertIn("blocking_first_core", bc)
        self.assertIn("non_blocking", bc)
        # pending (1) + needs_rule_review (1) = 2 blocking
        self.assertEqual(bc["blocking_first_core"], 2)
        # pass (1) = 1 non-blocking
        self.assertEqual(bc["non_blocking"], 1)

    def test_pass_non_blocking(self):
        """pass status is non-blocking for first-core release."""
        envelope = write_quality_report(
            processed_root=VALID_ROOT,
            visual_checks_root=VALID_VISUAL_CHECKS_ROOT,
        )
        vcs = envelope.payload["visual_check_summary"]
        bc = vcs["blocking_counts"]
        sc = vcs["status_counts"]
        # pass count should equal non_blocking count
        self.assertEqual(sc["pass"], bc["non_blocking"])

    def test_visual_check_summary_omitted_when_no_visual_checks_root(self):
        """When visual_checks_root is None, visual_check_summary is omitted or empty."""
        envelope = write_quality_report(
            processed_root=VALID_ROOT,
            visual_checks_root=None,
        )
        report = envelope.payload
        vcs = report.get("visual_check_summary")
        if vcs is not None:
            self.assertEqual(vcs.get("sampled_count", 0), 0)

    # -- quality tier distribution --------------------------------------------

    def test_quality_tier_distribution(self):
        """Report includes distribution of quality tiers across accepted records."""
        envelope = write_quality_report(processed_root=VALID_ROOT)
        report = envelope.payload

        self.assertIn("quality_tier_distribution", report)
        qtd = report["quality_tier_distribution"]
        self.assertEqual(qtd.get("Q0"), 2, "REC001, REC002 are Q0")
        self.assertEqual(qtd.get("Q2"), 1, "REC003 is Q2")

    # -- error handling: missing input artifact -------------------------------

    def test_missing_input_artifact_structured_error(self):
        """Missing required input returns structured ContractErrorInfo with ok=False."""
        # processed_root that does not exist
        envelope = write_quality_report(
            processed_root=Path("/nonexistent/path/to/processed"),
        )
        self.assertFalse(
            envelope.receipt.ok,
            "Receipt should be ok=False when processed_root is missing",
        )
        self.assertGreater(
            len(envelope.receipt.errors), 0,
            "Receipt should have at least one ContractErrorInfo",
        )
        err = envelope.receipt.errors[0]
        self.assertEqual(err.owner, "data")
        self.assertTrue(
            err.code in ("PROCESSED_ROOT_NOT_FOUND", "RECORDS_FILE_NOT_FOUND"),
            f"Expected structured error code, got: {err.code}",
        )

    def test_missing_records_jsonl_error(self):
        """Missing records.jsonl in processed_root yields structured error."""
        with tempfile.TemporaryDirectory() as tmp:
            processed = Path(tmp)
            envelope = write_quality_report(processed_root=processed)
            self.assertFalse(envelope.receipt.ok)
            codes = {e.code for e in envelope.receipt.errors}
            self.assertTrue(
                "RECORDS_FILE_NOT_FOUND" in codes or "RECORDS_UNREADABLE" in codes,
                f"Expected RECORDS_FILE_NOT_FOUND error, got: {codes}",
            )

    def test_no_partial_output_on_error(self):
        """When the function fails, no partial quality_report.json is written."""
        out_path = None
        with tempfile.TemporaryDirectory() as tmp:
            processed = Path(tmp)
            out_path = Path(tmp) / "should_not_exist.json"
            envelope = write_quality_report(
                processed_root=processed,
                out_path=out_path,
            )
            self.assertFalse(envelope.receipt.ok)
            self.assertFalse(
                out_path.exists(),
                "Partial output file must not be written on error",
            )

    # -- error handling: inconsistent counts ---------------------------------

    def test_inconsistent_count_structured_error(self):
        """Split and accepted-record counts must reconcile or fail structurally."""
        with tempfile.TemporaryDirectory() as tmp:
            splits_root = Path(tmp) / "splits"
            splits_root.mkdir()
            split_index = {
                "schema_version": "1",
                "contract_version": "1.0.0",
                "role": "split_index",
                "split_policy": {"random_seed": 42},
                "assignment_count": 2,
                "assignments": [
                    {"record_id": "REC001", "split": "train", "fallback_reason": None},
                    {"record_id": "REC002", "split": "val", "fallback_reason": None},
                ],
            }
            (splits_root / "split_index.json").write_text(
                json.dumps(split_index, sort_keys=True),
                encoding="utf-8",
            )

            envelope = write_quality_report(
                processed_root=VALID_ROOT,
                splits_root=splits_root,
            )

        self.assertFalse(envelope.receipt.ok)
        self.assertFalse(envelope.payload["reconciliation"]["split_counts_match"])
        self.assertTrue(
            any(error.code == "COUNT_RECONCILIATION_FAILED"
                for error in envelope.receipt.errors),
            [error.code for error in envelope.receipt.errors],
        )

    def test_unreadable_rejected_index_structured_error(self):
        """Unreadable rejected index must not silently collapse rejected_count to zero."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "processed"
            shutil.copytree(VALID_ROOT, root)
            (root / "rejected_index.jsonl").write_text("{not valid jsonl\n", encoding="utf-8")

            envelope = write_quality_report(processed_root=root)

        self.assertFalse(envelope.receipt.ok)
        self.assertTrue(
            any(error.code == "REJECTED_INDEX_UNREADABLE"
                for error in envelope.receipt.errors),
            [error.code for error in envelope.receipt.errors],
        )

    def test_unreadable_conflict_index_structured_error(self):
        """Unreadable conflict index must not silently collapse conflict_count to zero."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "processed"
            shutil.copytree(VALID_ROOT, root)
            (root / "conflict_index.jsonl").write_text("{not valid jsonl\n", encoding="utf-8")

            envelope = write_quality_report(processed_root=root)

        self.assertFalse(envelope.receipt.ok)
        self.assertTrue(
            any(error.code == "CONFLICT_INDEX_UNREADABLE"
                for error in envelope.receipt.errors),
            [error.code for error in envelope.receipt.errors],
        )

    def test_unreadable_visual_check_index_structured_error(self):
        """Unreadable visual check index must produce a diagnostic data error."""
        with tempfile.TemporaryDirectory() as tmp:
            visual_root = Path(tmp) / "visual_checks"
            shutil.copytree(VALID_VISUAL_CHECKS_ROOT, visual_root)
            (visual_root / "visual_check_index.json").write_text("{not valid json\n", encoding="utf-8")

            envelope = write_quality_report(
                processed_root=VALID_ROOT,
                visual_checks_root=visual_root,
            )

        self.assertFalse(envelope.receipt.ok)
        self.assertTrue(
            any(error.code == "VISUAL_CHECK_INDEX_UNREADABLE"
                for error in envelope.receipt.errors),
            [error.code for error in envelope.receipt.errors],
        )

    # -- deterministic output -------------------------------------------------

    def test_deterministic_output(self):
        """Two runs with identical inputs produce byte-identical output."""
        with tempfile.TemporaryDirectory() as tmp:
            out1 = Path(tmp) / "report1.json"
            out2 = Path(tmp) / "report2.json"

            env1 = write_quality_report(
                processed_root=VALID_ROOT,
                ingest_roots=VALID_INGEST_ROOTS,
                splits_root=VALID_SPLITS_ROOT,
                visual_checks_root=VALID_VISUAL_CHECKS_ROOT,
                out_path=out1,
            )
            env2 = write_quality_report(
                processed_root=VALID_ROOT,
                ingest_roots=VALID_INGEST_ROOTS,
                splits_root=VALID_SPLITS_ROOT,
                visual_checks_root=VALID_VISUAL_CHECKS_ROOT,
                out_path=out2,
            )

            self.assertTrue(env1.receipt.ok)
            self.assertTrue(env2.receipt.ok)

            hash1 = hashlib.sha256(out1.read_bytes()).hexdigest()
            hash2 = hashlib.sha256(out2.read_bytes()).hexdigest()
            self.assertEqual(hash1, hash2, "Output must be byte-deterministic")

    # -- no model/training artifacts ------------------------------------------

    def test_no_model_or_training_artifacts_generated(self):
        """The quality report writes no model or training artifacts."""
        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "quality_report.json"
            envelope = write_quality_report(
                processed_root=VALID_ROOT,
                ingest_roots=VALID_INGEST_ROOTS,
                splits_root=VALID_SPLITS_ROOT,
                visual_checks_root=VALID_VISUAL_CHECKS_ROOT,
                out_path=out_path,
            )
            self.assertTrue(envelope.receipt.ok)

            # Enumerate all files written under tmp
            all_files = list(Path(tmp).rglob("*"))
            model_keywords = ("model", "training", "batch", "checkpoint", "weights", "tensor")
            for fpath in all_files:
                if fpath.is_file():
                    path_str = str(fpath).lower()
                    for kw in model_keywords:
                        self.assertNotIn(
                            kw,
                            path_str,
                            f"Model/training keyword '{kw}' found in output: {fpath}",
                        )

    # -- report structure ----------------------------------------------------

    def test_report_has_schema_and_contract_version(self):
        """Report output includes schema_version and contract_version."""
        envelope = write_quality_report(processed_root=VALID_ROOT)
        report = envelope.payload
        self.assertEqual(report.get("schema_version"), "1")
        self.assertEqual(report.get("contract_version"), "1.0.0")

    def test_report_has_role(self):
        """Report output has role 'quality_report'."""
        envelope = write_quality_report(processed_root=VALID_ROOT)
        self.assertEqual(envelope.payload.get("role"), "quality_report")

    def test_all_required_sections_present(self):
        """Report includes all required top-level sections."""
        envelope = write_quality_report(
            processed_root=VALID_ROOT,
            ingest_roots=VALID_INGEST_ROOTS,
            splits_root=VALID_SPLITS_ROOT,
            visual_checks_root=VALID_VISUAL_CHECKS_ROOT,
        )
        report = envelope.payload

        required_sections = [
            "source_coverage",
            "reconciliation",
            "family_distribution",
            "residue_distribution",
            "warhead_distribution",
            "linkage_quality",
            "geometry_quality",
            "protein_chemical_state_quality",
            "candidate_stats",
            "quality_tier_distribution",
        ]
        for section in required_sections:
            self.assertIn(
                section,
                report,
                f"Required section '{section}' missing from quality report",
            )

    # -- source coverage: missing source --------------------------------------

    def test_source_coverage_handles_missing_ingest_root(self):
        """When an ingest root does not contain ingest_index.json, it is reported."""
        envelope = write_quality_report(
            processed_root=MISSING_INGEST_ROOT,
            ingest_roots=[MISSING_INGEST_ROOT / "nonexistent_source"],
        )
        report = envelope.payload
        sc = report.get("source_coverage", {})
        self.assertIsInstance(sc, dict)
        self.assertIn("nonexistent_source", sc)
        self.assertFalse(sc["nonexistent_source"]["complete_for_v1"])
        self.assertTrue(sc["nonexistent_source"]["missing_ingest_index"])
        self.assertFalse(envelope.receipt.ok)
        self.assertTrue(
            any(error.code == "SOURCE_COVERAGE_INCOMPLETE"
                for error in envelope.receipt.errors),
            [error.code for error in envelope.receipt.errors],
        )

    # -- candidate stats: forced positive ------------------------------------

    def test_candidate_stats_empty_radius_window_tracked(self):
        """empty_radius_window_count comes from edge_candidates artifacts."""
        envelope = write_quality_report(processed_root=VALID_ROOT)
        cs = envelope.payload["candidate_stats"]
        self.assertIn("empty_radius_window_count", cs)


# ---------------------------------------------------------------------------
# CLI contract tests
# ---------------------------------------------------------------------------


class QualityReportCLITests(unittest.TestCase):
    """Tests for the CLI entry point.

    python -m covalent_design.data.cli.write_quality_report
    """

    CLI_MODULE = "covalent_design.data.cli.write_quality_report"

    def _run_cli(self, *args: str) -> subprocess.CompletedProcess:
        cmd = [sys.executable, "-m", self.CLI_MODULE, *args]
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )

    # -- valid input ----------------------------------------------------------

    def test_cli_valid_input_exits_zero(self):
        """CLI exits 0 with valid inputs and writes report."""
        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "quality_report.json"
            proc = self._run_cli(
                "--processed-root", str(VALID_ROOT),
                "--ingest-roots", str(VALID_ROOT / "ingest" / "covbinder_in_pdb"),
                "--ingest-roots", str(VALID_ROOT / "ingest" / "covpdb"),
                "--splits-root", str(VALID_SPLITS_ROOT),
                "--visual-checks-root", str(VALID_VISUAL_CHECKS_ROOT),
                "--out", str(out_path),
            )
            self.assertEqual(
                proc.returncode, 0,
                f"CLI should exit 0 on valid input, got {proc.returncode}\n"
                f"stderr: {proc.stderr}\nstdout: {proc.stdout}",
            )
            self.assertTrue(out_path.exists(), "Output file must exist after successful run")
            report = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertIn("reconciliation", report)

    def test_cli_valid_produces_json_summary_stdout(self):
        """CLI prints a JSON summary to stdout on success."""
        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "report.json"
            proc = self._run_cli(
                "--processed-root", str(VALID_ROOT),
                "--ingest-roots", str(VALID_ROOT / "ingest" / "covbinder_in_pdb"),
                "--ingest-roots", str(VALID_ROOT / "ingest" / "covpdb"),
                "--out", str(out_path),
            )
            self.assertEqual(proc.returncode, 0)
            try:
                summary = json.loads(proc.stdout)
                self.assertIn("ok", summary)
            except json.JSONDecodeError:
                self.fail(f"CLI stdout is not valid JSON: {proc.stdout[:200]}")

    # -- invalid input -------------------------------------------------------

    def test_cli_invalid_processed_root_exits_nonzero(self):
        """CLI exits non-zero when processed-root is missing."""
        proc = self._run_cli(
            "--processed-root", "/nonexistent/processed/root",
            "--out", "/tmp/report.json",
        )
        self.assertNotEqual(proc.returncode, 0, "CLI should exit non-zero on invalid input")

    def test_cli_missing_required_arg_exits_nonzero(self):
        """CLI exits non-zero when required --processed-root is missing."""
        proc = self._run_cli()
        self.assertNotEqual(
            proc.returncode, 0,
            f"CLI should exit non-zero with no arguments, got {proc.returncode}",
        )

    # -- deterministic output via CLI ----------------------------------------

    def test_cli_deterministic_output(self):
        """Two CLI runs with same inputs produce byte-identical output files."""
        with tempfile.TemporaryDirectory() as tmp:
            out1 = Path(tmp) / "report1.json"
            out2 = Path(tmp) / "report2.json"

            args_template = [
                "--processed-root", str(VALID_ROOT),
                "--ingest-roots", str(VALID_ROOT / "ingest" / "covbinder_in_pdb"),
                "--ingest-roots", str(VALID_ROOT / "ingest" / "covpdb"),
                "--splits-root", str(VALID_SPLITS_ROOT),
                "--visual-checks-root", str(VALID_VISUAL_CHECKS_ROOT),
            ]

            p1 = self._run_cli(*args_template, "--out", str(out1))
            p2 = self._run_cli(*args_template, "--out", str(out2))

            self.assertEqual(p1.returncode, 0)
            self.assertEqual(p2.returncode, 0)

            h1 = hashlib.sha256(out1.read_bytes()).hexdigest()
            h2 = hashlib.sha256(out2.read_bytes()).hexdigest()
            self.assertEqual(h1, h2, "CLI output must be byte-deterministic")

    # -- no model/training artifacts via CLI ---------------------------------

    def test_cli_no_model_or_training_artifacts(self):
        """CLI produces no model or training artifacts in the output directory."""
        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "quality_report.json"
            proc = self._run_cli(
                "--processed-root", str(VALID_ROOT),
                "--ingest-roots", str(VALID_ROOT / "ingest" / "covbinder_in_pdb"),
                "--out", str(out_path),
            )
            self.assertEqual(proc.returncode, 0)
            all_files = list(Path(tmp).rglob("*"))
            model_keywords = ("model", "training", "batch", "checkpoint", "weights", "tensor")
            for fpath in all_files:
                if fpath.is_file():
                    path_str = str(fpath).lower()
                    for kw in model_keywords:
                        self.assertNotIn(kw, path_str)


# ---------------------------------------------------------------------------
# module-level expected-failure markers
# ---------------------------------------------------------------------------


class QualityReportModuleExists(unittest.TestCase):
    """Verify the Task 16 module entry points exist."""

    def test_quality_report_module_path_planned(self):
        """Module should live at covalent_design.data.quality_report."""
        spec_path = (
            Path(__file__).resolve().parents[2]
            / "src" / "covalent_design" / "data" / "quality_report.py"
        )
        self.assertTrue(spec_path.exists(), f"Missing module file: {spec_path}")

    def test_write_quality_report_cli_module_planned(self):
        """CLI module should live at covalent_design.data.cli.write_quality_report."""
        spec_path = (
            Path(__file__).resolve().parents[2]
            / "src" / "covalent_design" / "data" / "cli" / "write_quality_report.py"
        )
        self.assertTrue(spec_path.exists(), f"Missing CLI module file: {spec_path}")

    def test_quality_report_module_imports(self):
        """Production API should be importable by Task 16 tests."""
        self.assertIsNone(_IMPORT_ERROR, f"Import failed: {_IMPORT_ERROR!r}")
        self.assertTrue(callable(write_quality_report))


# ---------------------------------------------------------------------------
# coverage smoke: section presence even without optional inputs
# ---------------------------------------------------------------------------


class QualityReportOptionalInputsTests(unittest.TestCase):
    """Tests for behavior when optional inputs (ingest, splits, visual checks)
    are omitted."""

    def test_minimal_report_without_optional_inputs(self):
        """Report succeeds with only processed_root (no ingest, splits, visual)."""
        envelope = write_quality_report(processed_root=VALID_ROOT)
        self.assertTrue(envelope.receipt.ok)
        report = envelope.payload

        # Core sections always present
        for section in (
            "reconciliation",
            "family_distribution",
            "residue_distribution",
            "warhead_distribution",
            "linkage_quality",
            "candidate_stats",
            "quality_tier_distribution",
        ):
            self.assertIn(section, report)

    def test_ingest_roots_empty_list(self):
        """Empty ingest_roots list yields empty source_coverage."""
        envelope = write_quality_report(
            processed_root=VALID_ROOT,
            ingest_roots=[],
        )
        report = envelope.payload
        sc = report.get("source_coverage", {})
        self.assertEqual(len(sc), 0)
        self.assertTrue(report["reconciliation"]["all_sources_complete_for_v1"])
        self.assertTrue(envelope.receipt.ok)

    def test_no_visual_checks_root_no_visual_summary(self):
        """Without visual_checks_root, visual_check_summary is omitted or zeroed."""
        envelope = write_quality_report(
            processed_root=VALID_ROOT,
            visual_checks_root=None,
        )
        report = envelope.payload
        vcs = report.get("visual_check_summary")
        if vcs is not None:
            self.assertEqual(vcs.get("sampled_count", 0), 0)
            self.assertEqual(vcs.get("total_accepted", 0), 0)

    def test_no_splits_root_no_split_stats(self):
        """Without splits_root, split_stats is omitted or zeroed."""
        envelope = write_quality_report(
            processed_root=VALID_ROOT,
            splits_root=None,
        )
        report = envelope.payload
        ss = report.get("split_stats")
        if ss is not None:
            total = sum(v for k, v in ss.items() if k.endswith("_count") and isinstance(v, int))
            self.assertEqual(total, 0)


# ---------------------------------------------------------------------------
# integrity: all accepted records have edge_candidates refs
# ---------------------------------------------------------------------------


class QualityReportEdgeCandidateIntegrityTests(unittest.TestCase):
    """Verify edge_candidate artifact integrity within the report."""

    def test_every_accepted_record_has_edge_candidates(self):
        """Each accepted record's edge_candidates artifact is reachable."""
        envelope = write_quality_report(processed_root=VALID_ROOT)
        self.assertTrue(envelope.receipt.ok)
        cs = envelope.payload["candidate_stats"]
        self.assertEqual(
            cs["record_count"],
            3,
            "candidate_stats record_count should equal accepted record count",
        )

    def test_candidate_stats_match_artifacts(self):
        """Aggregate candidate stats match sum across edge_candidates files."""
        envelope = write_quality_report(processed_root=VALID_ROOT)
        cs = envelope.payload["candidate_stats"]

        # Manually sum from known edge_candidates fixtures
        expected_total = 4 + 3 + 6  # REC001(4) + REC002(3) + REC003(6)
        self.assertEqual(cs["total_candidates"], expected_total)

        expected_natural = 4 + 3 + 6
        self.assertEqual(cs["total_natural_candidates"], expected_natural)

        expected_forced = 0
        self.assertEqual(cs["total_forced_positives"], expected_forced)

    def test_linkage_count_distribution_key(self):
        """Monodentate v1 report explicitly counts one linkage per accepted record."""
        envelope = write_quality_report(processed_root=VALID_ROOT)
        self.assertEqual(
            envelope.payload["linkage_quality"]["linkage_count_distribution"],
            {"1": 3},
        )
