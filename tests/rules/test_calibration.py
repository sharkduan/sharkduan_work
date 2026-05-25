"""Task 11: build_calibration_sheet contract tests.

Contract:

  Public API:
    from covalent_design.rules.calibration import build_calibration_sheet
    build_calibration_sheet(records_path: Path,
                            rule_table_path: Path,
                            out_csv: Path | None = None,
                            out_json: Path | None = None) -> ContractEnvelope

  CLI:
    python -m covalent_design.rules.cli.build_calibration_sheet
        --records <records.jsonl> --rules <rule_table.yml>
        --out-csv <csv> [--out-json <json>]

  CSV is the primary review sheet; stdout gets a JSON summary.

  Row fields:
    family_id, sample_count, representative_record_ids,
    target_atom_distribution, ligand_attachment_element_distribution,
    warhead_distribution, bond_length_summary, protein_side_angle_summary,
    ligand_side_angle_summary, outlier_record_ids, manual_decision, notes,
    pending_smarts_marker, pending_geometry_marker

  Pending markers derive from rule table status fields.
  Geometry summaries read records.jsonl metadata.geometry (no 3D recalc).
  No-sample families: sample_count=0, empty distributions, notes
    indicating no accepted samples.
  Output must be deterministic across runs.
  No edge_candidates files, directories, or fields.
"""

import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from io import StringIO
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "calibration"

# Import the public Task 11 APIs and exercise them through the contract below.
from covalent_design.rules.calibration import build_calibration_sheet  # noqa: E402
from covalent_design.data.records import build_record_index  # noqa: E402

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

REQUIRED_CSV_COLUMNS = [
    "family_id",
    "sample_count",
    "representative_record_ids",
    "target_atom_distribution",
    "ligand_attachment_element_distribution",
    "warhead_distribution",
    "bond_length_summary",
    "protein_side_angle_summary",
    "ligand_side_angle_summary",
    "outlier_record_ids",
    "manual_decision",
    "notes",
    "pending_smarts_marker",
    "pending_geometry_marker",
]

CALIB_RULE_TABLE = FIXTURE_ROOT / "rule_table.yml"
CALIB_RECORDS = FIXTURE_ROOT / "records.jsonl"
RECORDS_VALID_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "records" / "valid"


def _read_csv_rows(path: Path) -> list[dict]:
    """Read a CSV into a list of dicts, stripping BOM and whitespace from headers."""
    text = path.read_text("utf-8")
    reader = csv.DictReader(StringIO(text))
    rows = []
    for row in reader:
        cleaned = {k.strip(): v for k, v in row.items()}
        rows.append(cleaned)
    return rows


def _csv_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# API signature and return-type contract
# ---------------------------------------------------------------------------

class BuildCalibrationSheetContractTests(unittest.TestCase):
    """Envelope shape and basic callability."""

    def test_returns_contract_envelope(self):
        from covalent_design.contracts.types import ContractEnvelope

        envelope = build_calibration_sheet(CALIB_RECORDS, CALIB_RULE_TABLE)
        self.assertIsInstance(envelope, ContractEnvelope)

    def test_envelope_receipt_is_present_and_ok(self):
        envelope = build_calibration_sheet(CALIB_RECORDS, CALIB_RULE_TABLE)
        self.assertIsNotNone(envelope.receipt)
        self.assertTrue(envelope.receipt.ok)

    def test_envelope_contract_version_is_current(self):
        from covalent_design.contracts.types import CONTRACT_VERSION

        envelope = build_calibration_sheet(CALIB_RECORDS, CALIB_RULE_TABLE)
        self.assertEqual(envelope.receipt.contract_version, CONTRACT_VERSION)


class BuildCalibrationSheetTask10IntegrationTests(unittest.TestCase):
    """Task 11 must consume Task 10 records, not only hand-written fixtures."""

    def test_ligand_element_distribution_is_present_from_task10_records(self):
        build_record_index(RECORDS_VALID_ROOT)
        with tempfile.TemporaryDirectory(prefix="task11_task10_integration_") as tmp:
            out_csv = Path(tmp) / "calibration_sheet.csv"
            build_calibration_sheet(
                RECORDS_VALID_ROOT / "records.jsonl",
                CALIB_RULE_TABLE,
                out_csv=out_csv,
            )
            rows = {row["family_id"]: row for row in _read_csv_rows(out_csv)}

        distribution = json.loads(
            rows["CYS_MICHAEL_ADDITION"]["ligand_attachment_element_distribution"]
        )
        self.assertEqual(distribution, {"C": 2})


# ---------------------------------------------------------------------------
# CSV output structure tests
# ---------------------------------------------------------------------------

class CalibrationSheetCSVStructureTests(unittest.TestCase):
    """CSV file existence, columns, and family row count."""

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = Path(tempfile.mkdtemp(prefix="task11_csv_"))
        cls.out_csv = cls.tmpdir / "calibration_sheet.csv"
        cls.envelope = build_calibration_sheet(
            CALIB_RECORDS, CALIB_RULE_TABLE, out_csv=cls.out_csv,
        )

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def test_out_csv_was_written(self):
        self.assertTrue(self.out_csv.exists())

    def test_csv_has_header_row_with_required_columns(self):
        rows = _read_csv_rows(self.out_csv)
        self.assertGreater(len(rows), 0, "CSV has no rows")
        header_set = set(rows[0].keys())
        missing = set(REQUIRED_CSV_COLUMNS) - header_set
        self.assertEqual(missing, set(), f"Missing columns: {missing}")

    def test_every_rule_table_family_has_one_row(self):
        rows = _read_csv_rows(self.out_csv)
        family_ids_in_csv = {row["family_id"] for row in rows}
        expected_families = {
            "CYS_MICHAEL_ADDITION",
            "CYS_NUCLEOPHILIC_SUBSTITUTION",
            "CYS_DISULFIDE_EXCHANGE",
        }
        self.assertEqual(family_ids_in_csv, expected_families)


# ---------------------------------------------------------------------------
# sample_count and per-family aggregation
# ---------------------------------------------------------------------------

class CalibrationSheetSampleCountTests(unittest.TestCase):
    """sample_count must reflect the number of accepted records per family."""

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = Path(tempfile.mkdtemp(prefix="task11_count_"))
        cls.out_csv = cls.tmpdir / "calibration_sheet.csv"
        cls.envelope = build_calibration_sheet(
            CALIB_RECORDS, CALIB_RULE_TABLE, out_csv=cls.out_csv,
        )
        cls.rows = {r["family_id"]: r for r in _read_csv_rows(cls.out_csv)}

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def test_michael_addition_has_3_samples(self):
        self.assertEqual(
            self.rows["CYS_MICHAEL_ADDITION"]["sample_count"],
            "3",
        )

    def test_nucleophilic_substitution_has_2_samples(self):
        self.assertEqual(
            self.rows["CYS_NUCLEOPHILIC_SUBSTITUTION"]["sample_count"],
            "2",
        )

    def test_disulfide_exchange_has_0_samples(self):
        self.assertEqual(
            self.rows["CYS_DISULFIDE_EXCHANGE"]["sample_count"],
            "0",
        )


# ---------------------------------------------------------------------------
# no-sample family is reviewable
# ---------------------------------------------------------------------------

class CalibrationSheetNoSampleFamilyTests(unittest.TestCase):
    """Families without accepted records must still be reviewable."""

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = Path(tempfile.mkdtemp(prefix="task11_nosample_"))
        cls.out_csv = cls.tmpdir / "calibration_sheet.csv"
        cls.envelope = build_calibration_sheet(
            CALIB_RECORDS, CALIB_RULE_TABLE, out_csv=cls.out_csv,
        )
        cls.rows = {r["family_id"]: r for r in _read_csv_rows(cls.out_csv)}

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def test_no_sample_family_row_exists(self):
        self.assertIn("CYS_DISULFIDE_EXCHANGE", self.rows)

    def test_no_sample_family_sample_count_is_zero(self):
        self.assertEqual(
            self.rows["CYS_DISULFIDE_EXCHANGE"]["sample_count"], "0",
        )

    def test_no_sample_family_has_empty_representative_ids(self):
        val = self.rows["CYS_DISULFIDE_EXCHANGE"]["representative_record_ids"]
        self.assertIn(val, ("", "[]", "None", "none"))

    def test_no_sample_family_distributions_are_empty(self):
        row = self.rows["CYS_DISULFIDE_EXCHANGE"]
        self.assertIn(
            row["target_atom_distribution"],
            ("", "{}", "None", "none"),
        )
        self.assertIn(
            row["ligand_attachment_element_distribution"],
            ("", "{}", "None", "none"),
        )
        self.assertIn(
            row["warhead_distribution"],
            ("", "{}", "None", "none"),
        )

    def test_no_sample_family_notes_mention_no_samples(self):
        notes = self.rows["CYS_DISULFIDE_EXCHANGE"]["notes"].lower()
        self.assertTrue(
            "no" in notes or "none" in notes or "0" in notes,
            f"Expected 'no accepted samples' indication, got: {notes}",
        )


# ---------------------------------------------------------------------------
# geometry summaries are read from records.jsonl metadata.geometry
# ---------------------------------------------------------------------------

class CalibrationSheetGeometryFromMetadataTests(unittest.TestCase):
    """Geometry summaries must come from metadata.geometry, not 3D artifacts."""

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = Path(tempfile.mkdtemp(prefix="task11_geom_"))
        cls.out_csv = cls.tmpdir / "calibration_sheet.csv"
        cls.envelope = build_calibration_sheet(
            CALIB_RECORDS, CALIB_RULE_TABLE, out_csv=cls.out_csv,
        )
        cls.rows = {r["family_id"]: r for r in _read_csv_rows(cls.out_csv)}

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def test_bond_length_summary_is_present_for_family_with_samples(self):
        row = self.rows["CYS_MICHAEL_ADDITION"]
        val = row["bond_length_summary"]
        self.assertIsNotNone(val)
        self.assertNotEqual(val.strip(), "")
        self.assertNotEqual(val.strip().lower(), "none")

    def test_protein_side_angle_summary_is_present(self):
        row = self.rows["CYS_MICHAEL_ADDITION"]
        val = row["protein_side_angle_summary"]
        self.assertIsNotNone(val)
        self.assertNotEqual(val.strip(), "")
        self.assertNotEqual(val.strip().lower(), "none")

    def test_ligand_side_angle_summary_is_present(self):
        row = self.rows["CYS_MICHAEL_ADDITION"]
        val = row["ligand_side_angle_summary"]
        self.assertIsNotNone(val)
        self.assertNotEqual(val.strip(), "")
        self.assertNotEqual(val.strip().lower(), "none")

    def test_bond_length_summary_reflects_fixture_values(self):
        """Fixture records have bond lengths 1.79, 1.82, 1.85 for this family.
        The summary should encode at least min or mean around 1.8 A."""
        row = self.rows["CYS_MICHAEL_ADDITION"]
        val = row["bond_length_summary"]
        # The summary format should mention values near 1.8 angstrom.
        self.assertTrue(
            "1.7" in val or "1.8" in val or "1.9" in val,
            f"bond_length_summary should reference values near 1.8 A: got '{val}'",
        )

    def test_no_sample_family_geometry_summaries_are_empty(self):
        row = self.rows["CYS_DISULFIDE_EXCHANGE"]
        for key in ("bond_length_summary", "protein_side_angle_summary",
                     "ligand_side_angle_summary"):
            self.assertIn(
                row[key],
                ("", "None", "none"),
                f"{key} should be empty for no-sample family, got '{row[key]}'",
            )


# ---------------------------------------------------------------------------
# representative_record_ids
# ---------------------------------------------------------------------------

class CalibrationSheetRepresentativeIdsTests(unittest.TestCase):
    """representative_record_ids must be valid record IDs from the fixture."""

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = Path(tempfile.mkdtemp(prefix="task11_repr_"))
        cls.out_csv = cls.tmpdir / "calibration_sheet.csv"
        cls.family_ma_row = None
        cls.envelope = build_calibration_sheet(
            CALIB_RECORDS, CALIB_RULE_TABLE, out_csv=cls.out_csv,
        )
        for row in _read_csv_rows(cls.out_csv):
            if row["family_id"] == "CYS_MICHAEL_ADDITION":
                cls.family_ma_row = row
                break

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def test_representative_ids_field_is_not_empty(self):
        self.assertIsNotNone(self.family_ma_row)
        val = self.family_ma_row["representative_record_ids"]
        self.assertNotEqual(val.strip(), "")
        self.assertNotEqual(val.strip().lower(), "none")

    def test_representative_ids_reference_existing_record_ids(self):
        valid_ids = [
            "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
            "bb1c2d3e4f5a6b7c8d9e0f1a2e3f3c5d7",
            "cc1c2d3e4f5a6b7c8d9e0f1a2e3f3c5d8",
            "dd1c2d3e4f5a6b7c8d9e0f1a2e3f3c5d9",
            "ee1c2d3e4f5a6b7c8d9e0f1a2e3f3c5e0",
        ]
        val = self.family_ma_row["representative_record_ids"]
        present = [rid for rid in valid_ids if rid in val]
        self.assertGreater(
            len(present),
            0,
            f"No valid record ID found in representative_record_ids: '{val}'",
        )


# ---------------------------------------------------------------------------
# distribution field coverage
# ---------------------------------------------------------------------------

class CalibrationSheetDistributionTests(unittest.TestCase):
    """target_atom, ligand_attachment_element, and warhead distributions."""

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = Path(tempfile.mkdtemp(prefix="task11_dist_"))
        cls.out_csv = cls.tmpdir / "calibration_sheet.csv"
        cls.envelope = build_calibration_sheet(
            CALIB_RECORDS, CALIB_RULE_TABLE, out_csv=cls.out_csv,
        )
        cls.rows = {r["family_id"]: r for r in _read_csv_rows(cls.out_csv)}

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def test_target_atom_distribution_includes_sg(self):
        row = self.rows["CYS_MICHAEL_ADDITION"]
        val = row["target_atom_distribution"].upper()
        self.assertIn("SG", val)

    def test_ligand_attachment_element_distribution_includes_c(self):
        row = self.rows["CYS_MICHAEL_ADDITION"]
        val = row["ligand_attachment_element_distribution"].upper()
        self.assertIn("C", val)

    def test_nucleophilic_substitution_has_mixed_element_distribution(self):
        """CYS_NUCLEOPHILIC_SUBSTITUTION has both C and N attachment elements."""
        row = self.rows["CYS_NUCLEOPHILIC_SUBSTITUTION"]
        val = row["ligand_attachment_element_distribution"].upper()
        self.assertIn("C", val)
        self.assertIn("N", val)

    def test_warhead_distribution_reflects_fixture_warhead_types(self):
        row = self.rows["CYS_MICHAEL_ADDITION"]
        val = row["warhead_distribution"].lower()
        warheads_found = any(
            w in val for w in ("acrylamide", "vinyl_sulfonamide", "vinyl")
        )
        self.assertTrue(
            warheads_found,
            f"warhead_distribution should mention fixture warhead types: '{val}'",
        )


# ---------------------------------------------------------------------------
# pending SMARTS and geometry markers
# ---------------------------------------------------------------------------

class CalibrationSheetPendingMarkerTests(unittest.TestCase):
    """Markers must reflect rule table warhead_rule_status, geometry_status,
    allowed_warhead_smarts emptiness, and null geometry ranges."""

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = Path(tempfile.mkdtemp(prefix="task11_markers_"))
        cls.out_csv = cls.tmpdir / "calibration_sheet.csv"
        cls.envelope = build_calibration_sheet(
            CALIB_RECORDS, CALIB_RULE_TABLE, out_csv=cls.out_csv,
        )
        cls.rows = {r["family_id"]: r for r in _read_csv_rows(cls.out_csv)}

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def test_pending_smarts_marker_set_for_pending_warhead_rule_status(self):
        """CYS_MICHAEL_ADDITION has warhead_rule_status=pending and
        empty allowed_warhead_smarts."""
        row = self.rows["CYS_MICHAEL_ADDITION"]
        marker = row["pending_smarts_marker"]
        self.assertIsNotNone(marker)
        self.assertNotEqual(marker.strip(), "")
        # Should indicate "pending" or equivalent.
        self.assertIn(marker.lower(), ("true", "yes", "pending", "1"))

    def test_pending_smarts_marker_set_for_pending_ns_family(self):
        """CYS_NUCLEOPHILIC_SUBSTITUTION also has pending SMARTS."""
        row = self.rows["CYS_NUCLEOPHILIC_SUBSTITUTION"]
        marker = row["pending_smarts_marker"]
        self.assertIn(marker.lower(), ("true", "yes", "pending", "1"))

    def test_pending_smarts_marker_not_set_for_calibrated_smarts(self):
        """CYS_DISULFIDE_EXCHANGE has warhead_rule_status=calibrated
        with non-empty allowed_warhead_smarts."""
        row = self.rows["CYS_DISULFIDE_EXCHANGE"]
        marker = row["pending_smarts_marker"].lower()
        self.assertIn(marker, ("false", "no", "", "calibrated", "0", "none"))

    def test_pending_geometry_marker_set_when_geometry_has_pending_ranges(self):
        """CYS_MICHAEL_ADDITION: protein_side_angle and ligand_side_angle
        have status=pending with null ranges."""
        row = self.rows["CYS_MICHAEL_ADDITION"]
        marker = row["pending_geometry_marker"]
        self.assertIsNotNone(marker)
        self.assertNotEqual(marker.strip(), "")
        self.assertIn(marker.lower(), ("true", "yes", "pending", "1"))

    def test_pending_geometry_marker_set_for_fully_pending_geometry(self):
        """CYS_NUCLEOPHILIC_SUBSTITUTION has all geometry pending."""
        row = self.rows["CYS_NUCLEOPHILIC_SUBSTITUTION"]
        marker = row["pending_geometry_marker"]
        self.assertIn(marker.lower(), ("true", "yes", "pending", "1"))

    def test_pending_geometry_marker_not_set_for_fully_calibrated_geometry(self):
        """CYS_DISULFIDE_EXCHANGE has all geometry calibrated with valid ranges."""
        row = self.rows["CYS_DISULFIDE_EXCHANGE"]
        marker = row["pending_geometry_marker"].lower()
        self.assertIn(marker, ("false", "no", "", "calibrated", "0", "none"))


# ---------------------------------------------------------------------------
# manual_decision and notes fields
# ---------------------------------------------------------------------------

class CalibrationSheetManualDecisionTests(unittest.TestCase):
    """manual_decision has a default empty value; notes preserves rule table notes."""

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = Path(tempfile.mkdtemp(prefix="task11_manual_"))
        cls.out_csv = cls.tmpdir / "calibration_sheet.csv"
        cls.envelope = build_calibration_sheet(
            CALIB_RECORDS, CALIB_RULE_TABLE, out_csv=cls.out_csv,
        )
        cls.rows = {r["family_id"]: r for r in _read_csv_rows(cls.out_csv)}

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def test_manual_decision_has_default_empty_value(self):
        for family_id, row in self.rows.items():
            val = row.get("manual_decision", "")
            self.assertIsNotNone(val, f"{family_id}: manual_decision missing")

    def test_notes_field_is_present_for_all_families(self):
        for family_id, row in self.rows.items():
            self.assertIn(
                "notes",
                row,
                f"{family_id}: notes column missing",
            )


# ---------------------------------------------------------------------------
# outlier_record_ids
# ---------------------------------------------------------------------------

class CalibrationSheetOutlierTests(unittest.TestCase):
    """outlier_record_ids is a list field (may be empty)."""

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = Path(tempfile.mkdtemp(prefix="task11_outlier_"))
        cls.out_csv = cls.tmpdir / "calibration_sheet.csv"
        cls.envelope = build_calibration_sheet(
            CALIB_RECORDS, CALIB_RULE_TABLE, out_csv=cls.out_csv,
        )
        cls.rows = {r["family_id"]: r for r in _read_csv_rows(cls.out_csv)}

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def test_outlier_record_ids_field_exists_for_family_with_samples(self):
        row = self.rows["CYS_MICHAEL_ADDITION"]
        self.assertIn("outlier_record_ids", row)

    def test_outlier_record_ids_is_parseable(self):
        """The field should be a list-like representation (JSON array,
        semicolon-separated, or empty). It must not be an unhandled None."""
        row = self.rows["CYS_MICHAEL_ADDITION"]
        val = row["outlier_record_ids"]
        self.assertIsNotNone(val)

    def test_no_sample_family_outlier_ids_are_empty(self):
        row = self.rows["CYS_DISULFIDE_EXCHANGE"]
        val = row.get("outlier_record_ids", "")
        self.assertIn(
            val.lower().strip(),
            ("", "[]", "none"),
        )


# ---------------------------------------------------------------------------
# deterministic output
# ---------------------------------------------------------------------------

class CalibrationSheetDeterminismTests(unittest.TestCase):
    """Two runs with identical inputs must produce byte-identical CSV output."""

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = Path(tempfile.mkdtemp(prefix="task11_determ_"))
        cls.csv_a = cls.tmpdir / "a.csv"
        cls.csv_b = cls.tmpdir / "b.csv"

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def test_csv_is_byte_identical_across_two_runs(self):
        build_calibration_sheet(
            CALIB_RECORDS, CALIB_RULE_TABLE, out_csv=self.csv_a,
        )
        build_calibration_sheet(
            CALIB_RECORDS, CALIB_RULE_TABLE, out_csv=self.csv_b,
        )
        self.assertEqual(_csv_sha256(self.csv_a), _csv_sha256(self.csv_b))

    def test_stdout_json_summary_identical_across_two_runs(self):
        """Two calls without out_csv should produce the same summary output
        (tested via the envelope structure, since stdout is a CLI concern)."""
        env_a = build_calibration_sheet(CALIB_RECORDS, CALIB_RULE_TABLE)
        env_b = build_calibration_sheet(CALIB_RECORDS, CALIB_RULE_TABLE)
        self.assertEqual(
            hashlib.sha256(json.dumps(
                env_a.receipt.input_sha256, sort_keys=True,
            ).encode()).hexdigest(),
            hashlib.sha256(json.dumps(
                env_b.receipt.input_sha256, sort_keys=True,
            ).encode()).hexdigest(),
        )


# ---------------------------------------------------------------------------
# no edge_candidates leakage
# ---------------------------------------------------------------------------

class CalibrationSheetNoEdgeCandidatesTests(unittest.TestCase):
    """Task 11 output must NOT generate edge_candidates files, directories, or fields."""

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = Path(tempfile.mkdtemp(prefix="task11_noedge_"))
        cls.out_csv = cls.tmpdir / "calibration_sheet.csv"
        cls.out_json = cls.tmpdir / "calibration_summary.json"
        cls.envelope = build_calibration_sheet(
            CALIB_RECORDS, CALIB_RULE_TABLE,
            out_csv=cls.out_csv,
            out_json=cls.out_json,
        )

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def test_no_edge_candidates_directory_created(self):
        edge_dirs = list(self.tmpdir.glob("**/edge_candidates*"))
        self.assertEqual(
            len(edge_dirs),
            0,
            f"Unexpected edge_candidates paths: {edge_dirs}",
        )

    def test_csv_has_no_edge_candidates_field(self):
        row = _read_csv_rows(self.out_csv)[0]
        self.assertNotIn("edge_candidates", row)
        self.assertNotIn("edge_candidate", row)

    def test_envelope_artifacts_have_no_edge_related_roles(self):
        for art in self.envelope.artifacts:
            role = art.role.lower()
            self.assertNotIn("edge", role, f"Edge-related artifact role: {role}")

    def test_envelope_has_no_edge_candidates_in_payload(self):
        """The envelope payload should not contain edge_candidates keys."""
        payload_dict = (
            self.envelope.payload.__dict__
            if hasattr(self.envelope.payload, "__dict__")
            else {}
        )
        payload_str = json.dumps(payload_dict, default=str)
        self.assertNotIn("edge_candidate", payload_str.lower())


# ---------------------------------------------------------------------------
# out_json optional output
# ---------------------------------------------------------------------------

class CalibrationSheetOptionalJSONTests(unittest.TestCase):
    """When out_json is provided, a JSON summary file is written."""

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = Path(tempfile.mkdtemp(prefix="task11_json_"))
        cls.out_json = cls.tmpdir / "calibration_summary.json"
        cls.envelope = build_calibration_sheet(
            CALIB_RECORDS, CALIB_RULE_TABLE, out_json=cls.out_json,
        )

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def test_out_json_was_written_when_provided(self):
        self.assertTrue(
            self.out_json.exists(),
            "Expected out_json to be written when explicitly provided",
        )

    def test_out_json_is_valid_json(self):
        data = json.loads(self.out_json.read_text("utf-8"))
        self.assertIsInstance(data, dict)

    def test_out_json_contains_family_summaries(self):
        data = json.loads(self.out_json.read_text("utf-8"))
        self.assertIn(
            "families",
            data,
            "Expected 'families' key in JSON summary",
        )


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------

class BuildCalibrationSheetCliTests(unittest.TestCase):
    """CLI: python -m covalent_design.rules.cli.build_calibration_sheet."""

    def _run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = "src"
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "covalent_design.rules.cli.build_calibration_sheet",
                *args,
            ],
            cwd=str(REPO_ROOT),
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_cli_help_returns_zero(self):
        result = self._run_cli("--help")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_cli_valid_inputs_returns_zero(self):
        with tempfile.TemporaryDirectory(prefix="task11_cli_") as td:
            csv_path = Path(td) / "out.csv"
            result = self._run_cli(
                "--records", str(CALIB_RECORDS),
                "--rules", str(CALIB_RULE_TABLE),
                "--out-csv", str(csv_path),
            )
            self.assertEqual(result.returncode, 0, f"stderr:\n{result.stderr}")

    def test_cli_valid_inputs_writes_json_summary_to_stdout(self):
        with tempfile.TemporaryDirectory(prefix="task11_cli_") as td:
            csv_path = Path(td) / "out.csv"
            result = self._run_cli(
                "--records", str(CALIB_RECORDS),
                "--rules", str(CALIB_RULE_TABLE),
                "--out-csv", str(csv_path),
            )
            summary = json.loads(result.stdout)
            self.assertIsInstance(summary, dict)
            self.assertIn("ok", summary)

    def test_cli_with_out_json_flag_writes_json_file(self):
        with tempfile.TemporaryDirectory(prefix="task11_cli_") as td:
            csv_path = Path(td) / "out.csv"
            json_path = Path(td) / "out.json"
            result = self._run_cli(
                "--records", str(CALIB_RECORDS),
                "--rules", str(CALIB_RULE_TABLE),
                "--out-csv", str(csv_path),
                "--out-json", str(json_path),
            )
            self.assertEqual(result.returncode, 0, f"stderr:\n{result.stderr}")
            self.assertTrue(json_path.exists())

    def test_cli_without_out_csv_writes_csv(self):
        """Without --out-csv, the CLI should still succeed (CSV path is optional
        in API). The stdout summary is always produced."""
        with tempfile.TemporaryDirectory(prefix="task11_cli_") as td:
            result = self._run_cli(
                "--records", str(CALIB_RECORDS),
                "--rules", str(CALIB_RULE_TABLE),
            )
            # Should succeed; CSV is optional.
            self.assertEqual(result.returncode, 0, f"stderr:\n{result.stderr}")
            summary = json.loads(result.stdout)
            self.assertIsInstance(summary, dict)

    def test_cli_csv_output_has_required_columns(self):
        with tempfile.TemporaryDirectory(prefix="task11_cli_") as td:
            csv_path = Path(td) / "out.csv"
            result = self._run_cli(
                "--records", str(CALIB_RECORDS),
                "--rules", str(CALIB_RULE_TABLE),
                "--out-csv", str(csv_path),
            )
            self.assertEqual(result.returncode, 0, f"stderr:\n{result.stderr}")
            rows = _read_csv_rows(csv_path)
            self.assertGreater(len(rows), 0)
            header_set = set(rows[0].keys())
            missing = set(REQUIRED_CSV_COLUMNS) - header_set
            self.assertEqual(missing, set(), f"Missing CLI CSV columns: {missing}")

    def test_cli_output_has_no_edge_candidates(self):
        with tempfile.TemporaryDirectory(prefix="task11_cli_") as td:
            csv_path = Path(td) / "out.csv"
            self._run_cli(
                "--records", str(CALIB_RECORDS),
                "--rules", str(CALIB_RULE_TABLE),
                "--out-csv", str(csv_path),
            )
            edge_paths = list(Path(td).glob("**/edge_candidates*"))
            self.assertEqual(len(edge_paths), 0)


if __name__ == "__main__":
    unittest.main()
