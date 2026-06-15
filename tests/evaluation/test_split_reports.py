"""Task 33 split-aware evaluation report contract tests."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Mapping

from covalent_design.contracts.errors import ContractError
from covalent_design.contracts.lifecycle import validate_generation_result
from covalent_design.contracts.denominators import validate_evaluation_summary
from covalent_design.contracts.types import (
    ArtifactRef,
    CovalentEdge,
    CovalentGenerationResult,
    EdgeValidityCheck,
    GeometryMetrics,
    LigandAtomIdentity,
    MoleculeQuality,
    ProteinAtomIdentity,
    EvaluationSummary,
)


FIXTURES = Path("tests/fixtures/evaluation/split_reports")
SCHEMA_VERSION = "1"
CONTRACT_VERSION = "1.0.0"
DUMMY_SHA256 = "a" * 64

TARGET_ATOM = ProteinAtomIdentity(
    chain_id="A",
    residue_number=145,
    residue_name="CYS",
    atom_name="SG",
    atom_serial=1234,
)
LIGAND_ATOM = LigandAtomIdentity(
    ligand_id="LIG",
    atom_name="C4",
    atom_index=4,
)
EDGE_CHECK_PASS = EdgeValidityCheck(
    check_name="geometry",
    status="pass",
    observed_value="ok",
    threshold_or_rule="fixture",
    rule_table_version="test",
)
GEOMETRY = GeometryMetrics(
    bond_length=1.82,
    protein_side_angle=108.0,
    ligand_side_angle=113.0,
)
MOL_QUALITY = MoleculeQuality(qed=0.5, sa_score=3.0, log_p=1.2, molecular_weight=300.0)
COMPLEX_REF = ArtifactRef(
    uri="complex.mmcif",
    sha256=DUMMY_SHA256,
    format="mmcif",
    schema_version=SCHEMA_VERSION,
    role="complex_mmcif",
    bytes=100,
)
LIGAND_REF = ArtifactRef(
    uri="ligand.sdf",
    sha256="b" * 64,
    format="sdf",
    schema_version=SCHEMA_VERSION,
    role="ligand_sdf",
    bytes=100,
)
FULL_ARTIFACTS: Mapping[str, ArtifactRef] = {
    "complex_mmcif": COMPLEX_REF,
    "ligand_sdf": LIGAND_REF,
}


def _result(
    record_id: str,
    sample_id: int,
    *,
    family: str = "CYS_MICHAEL_ADDITION",
    generation_validity: str = "valid",
    complex_export: str = "exported",
    docking_eligibility: str = "eligible",
    docking_run: str = "succeeded",
    primary_failure: str | None = None,
    covalent_docking: float | None = -8.5,
    noncovalent: float | None = -7.0,
) -> CovalentGenerationResult:
    edge = CovalentEdge(
        protein_atom=TARGET_ATOM,
        ligand_atom=LIGAND_ATOM,
        bond_type="carbon-sulfur",
    )
    if generation_validity == "invalid":
        return CovalentGenerationResult(
            request_id=record_id,
            sample_id=sample_id,
            residue_reaction_family=family,
            target_atom_identity=TARGET_ATOM,
            generation_validity_status="invalid",
            complex_export_status="not_applicable",
            docking_eligibility_status="not_applicable",
            docking_run_status="not_applicable",
            primary_failure_reason=primary_failure or "GEOMETRY_CHECK_FAIL",
            secondary_failure_reasons=(),
        )
    return CovalentGenerationResult(
        request_id=record_id,
        sample_id=sample_id,
        residue_reaction_family=family,
        target_atom_identity=TARGET_ATOM,
        generation_validity_status="valid",
        complex_export_status=complex_export,
        docking_eligibility_status=docking_eligibility,
        docking_run_status=docking_run,
        primary_failure_reason=primary_failure,
        secondary_failure_reasons=(),
        generated_ligand_status="present",
        predicted_ligand_attachment_atom=LIGAND_ATOM,
        predicted_covalent_edge=edge,
        covalent_edge_score=0.9,
        geometry_metrics=GEOMETRY,
        molecular_quality_metrics=MOL_QUALITY,
        matched_warhead_type="acrylamide",
        predicted_warhead_type="acrylamide",
        covalent_docking_score=covalent_docking,
        noncovalent_vina_score=noncovalent,
        edge_validity_checks=(EDGE_CHECK_PASS,),
        artifacts=FULL_ARTIFACTS,
    )


def _valid_results() -> tuple[CovalentGenerationResult, ...]:
    return (
        _result("SR000000000000000000000000000001", 0, family="CYS_MICHAEL_ADDITION"),
        _result("SR000000000000000000000000000002", 1, family="CYS_MICHAEL_ADDITION"),
        _result("SR000000000000000000000000000003", 2, family="CYS_MICHAEL_ADDITION", generation_validity="invalid"),
        _result("SR000000000000000000000000000004", 3, family="LYS_IMINE_FORMATION"),
        _result("SR000000000000000000000000000005", 4, family="CYS_MICHAEL_ADDITION"),
        _result("SR000000000000000000000000000006", 5, family="CYS_MICHAEL_ADDITION"),
    )


def _load_fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class SplitReportImportTests(unittest.TestCase):
    def test_public_api_is_importable(self) -> None:
        from covalent_design.evaluation.split_metrics import (  # noqa: F401
            build_stratified_evaluation_summary,
            join_results_to_split_assignments,
            load_leakage_report,
            load_split_index,
            stratified_evaluation_summary_to_dict,
            summarize_split_results,
            validate_leakage_report_for_evaluation,
            validate_split_index_for_evaluation,
            write_stratified_evaluation_summary,
        )


class SplitIndexValidationTests(unittest.TestCase):
    def test_valid_split_index_loads_and_validates(self) -> None:
        from covalent_design.evaluation.split_metrics import (
            load_split_index,
            validate_split_index_for_evaluation,
        )

        split_index = load_split_index(FIXTURES / "valid_split_index.json")
        receipt = validate_split_index_for_evaluation(split_index)
        self.assertTrue(receipt.passed)
        self.assertEqual(split_index["assignment_count"], len(split_index["assignments"]))

    def test_assignment_count_mismatch_fails(self) -> None:
        from covalent_design.evaluation.split_metrics import load_split_index

        with self.assertRaises(ContractError) as ctx:
            load_split_index(FIXTURES / "split_index_count_mismatch.json")
        self.assertEqual(ctx.exception.code, "SPLIT_REPORT_SPLIT_INDEX_INVALID")

    def test_duplicate_record_id_fails(self) -> None:
        from covalent_design.evaluation.split_metrics import load_split_index

        with self.assertRaises(ContractError) as ctx:
            load_split_index(FIXTURES / "split_index_duplicate_record_id.json")
        self.assertEqual(ctx.exception.code, "SPLIT_REPORT_ASSIGNMENT_DUPLICATE")

    def test_invalid_split_value_fails(self) -> None:
        from covalent_design.evaluation.split_metrics import load_split_index

        with self.assertRaises(ContractError) as ctx:
            load_split_index(FIXTURES / "split_index_invalid_split.json")
        self.assertEqual(ctx.exception.code, "SPLIT_REPORT_SPLIT_INDEX_INVALID")

    def test_missing_required_assignment_field_fails(self) -> None:
        from covalent_design.evaluation.split_metrics import load_split_index

        with self.assertRaises(ContractError) as ctx:
            load_split_index(FIXTURES / "split_index_missing_field.json")
        self.assertEqual(ctx.exception.code, "SPLIT_REPORT_SPLIT_INDEX_INVALID")

    def test_split_index_role_and_versions_are_validated(self) -> None:
        from covalent_design.evaluation.split_metrics import validate_split_index_for_evaluation

        split_index = _load_fixture("valid_split_index.json")
        split_index["role"] = "records_index"
        split_index["schema_version"] = "999"
        split_index["contract_version"] = "999"
        receipt = validate_split_index_for_evaluation(split_index)
        self.assertFalse(receipt.passed)
        self.assertEqual(
            {error.code for error in receipt.errors},
            {"SPLIT_REPORT_SPLIT_INDEX_INVALID"},
        )


class LeakageReportValidationTests(unittest.TestCase):
    def test_valid_leakage_report_loads_and_validates(self) -> None:
        from covalent_design.evaluation.split_metrics import (
            load_leakage_report,
            load_split_index,
            validate_leakage_report_for_evaluation,
        )

        split_index = load_split_index(FIXTURES / "valid_split_index.json")
        leakage = load_leakage_report(FIXTURES / "valid_leakage_report.json")
        receipt = validate_leakage_report_for_evaluation(leakage, split_index)
        self.assertTrue(receipt.passed)

    def test_leakage_report_role_versions_and_zero_overlap_shape_are_validated(self) -> None:
        from covalent_design.evaluation.split_metrics import (
            load_split_index,
            validate_leakage_report_for_evaluation,
        )

        split_index = load_split_index(FIXTURES / "valid_split_index.json")
        leakage = _load_fixture("valid_leakage_report.json")
        leakage["role"] = "quality_report"
        leakage["schema_version"] = "999"
        leakage["contract_version"] = "999"
        leakage["zero_overlap"] = {"scaffold": "yes", "protein_cluster": True}
        receipt = validate_leakage_report_for_evaluation(leakage, split_index)
        self.assertFalse(receipt.passed)
        self.assertEqual(
            {error.code for error in receipt.errors},
            {"SPLIT_REPORT_LEAKAGE_REPORT_INVALID"},
        )

    def test_scaffold_overlap_is_reported_as_blocking_risk(self) -> None:
        from covalent_design.evaluation.split_metrics import (
            build_stratified_evaluation_summary,
            load_leakage_report,
            load_split_index,
            stratified_evaluation_summary_to_dict,
        )

        split_index = load_split_index(FIXTURES / "valid_split_index.json")
        leakage = load_leakage_report(FIXTURES / "leakage_scaffold_overlap.json")
        summary = build_stratified_evaluation_summary(_valid_results(), split_index, leakage)
        data = stratified_evaluation_summary_to_dict(summary)
        self.assertFalse(data["leakage_report"]["zero_overlap"]["scaffold"])
        self.assertTrue(data["leakage_report"]["blocking_primary_leakage"]["scaffold"])

    def test_protein_cluster_overlap_is_reported_as_blocking_risk(self) -> None:
        from covalent_design.evaluation.split_metrics import (
            build_stratified_evaluation_summary,
            load_leakage_report,
            load_split_index,
            stratified_evaluation_summary_to_dict,
        )

        split_index = load_split_index(FIXTURES / "valid_split_index.json")
        leakage = load_leakage_report(FIXTURES / "leakage_protein_cluster_overlap.json")
        summary = build_stratified_evaluation_summary(_valid_results(), split_index, leakage)
        data = stratified_evaluation_summary_to_dict(summary)
        self.assertFalse(data["leakage_report"]["zero_overlap"]["protein_cluster"])
        self.assertTrue(data["leakage_report"]["blocking_primary_leakage"]["protein_cluster"])

    def test_builder_rejects_invalid_leakage_report(self) -> None:
        from covalent_design.evaluation.split_metrics import (
            build_stratified_evaluation_summary,
            load_split_index,
        )

        split_index = load_split_index(FIXTURES / "valid_split_index.json")
        leakage = _load_fixture("valid_leakage_report.json")
        leakage["record_count"] = 999
        leakage["train_count"] = 999
        with self.assertRaises(ContractError) as ctx:
            build_stratified_evaluation_summary(_valid_results(), split_index, leakage)
        self.assertEqual(ctx.exception.code, "SPLIT_REPORT_LEAKAGE_REPORT_INVALID")

    def test_leakage_record_count_must_match_split_index(self) -> None:
        from covalent_design.evaluation.split_metrics import (
            load_split_index,
            validate_leakage_report_for_evaluation,
        )

        split_index = load_split_index(FIXTURES / "valid_split_index.json")
        leakage = _load_fixture("valid_leakage_report.json")
        leakage["record_count"] = 999
        receipt = validate_leakage_report_for_evaluation(leakage, split_index)
        self.assertFalse(receipt.passed)
        self.assertIn(
            "record_count",
            " ".join(error.message for error in receipt.errors),
        )

    def test_leakage_fallback_by_reason_must_match_split_index(self) -> None:
        from covalent_design.evaluation.split_metrics import (
            load_split_index,
            validate_leakage_report_for_evaluation,
        )

        split_index = load_split_index(FIXTURES / "valid_split_index.json")
        leakage = _load_fixture("valid_leakage_report.json")
        leakage["fallback_by_reason"] = {"missing_scaffold_input": 2}
        receipt = validate_leakage_report_for_evaluation(leakage, split_index)
        self.assertFalse(receipt.passed)
        self.assertIn(
            "fallback_by_reason",
            " ".join(error.message for error in receipt.errors),
        )

    def test_leakage_manual_review_count_must_match_split_index(self) -> None:
        from covalent_design.evaluation.split_metrics import (
            load_split_index,
            validate_leakage_report_for_evaluation,
        )

        split_index = load_split_index(FIXTURES / "valid_split_index.json")
        leakage = _load_fixture("valid_leakage_report.json")
        leakage["manual_review_count"] = 0
        receipt = validate_leakage_report_for_evaluation(leakage, split_index)
        self.assertFalse(receipt.passed)
        self.assertIn(
            "manual_review_count",
            " ".join(error.message for error in receipt.errors),
        )


class ResultJoinAndSummaryTests(unittest.TestCase):
    def setUp(self) -> None:
        from covalent_design.evaluation.split_metrics import load_leakage_report, load_split_index

        self.split_index = load_split_index(FIXTURES / "valid_split_index.json")
        self.leakage = load_leakage_report(FIXTURES / "valid_leakage_report.json")
        self.results = _valid_results()

    def test_results_are_valid_lifecycle_rows(self) -> None:
        for result in self.results:
            self.assertTrue(validate_generation_result(result).passed)

    def test_join_uses_request_id_as_record_id(self) -> None:
        from covalent_design.evaluation.split_metrics import join_results_to_split_assignments

        joined = join_results_to_split_assignments(self.results, self.split_index)
        train_ids = [entry.result.request_id for entry in joined if entry.split == "train"]
        self.assertEqual(
            train_ids,
            [
                "SR000000000000000000000000000001",
                "SR000000000000000000000000000002",
            ],
        )

    def test_join_accepts_empty_result_tuple(self) -> None:
        from covalent_design.evaluation.split_metrics import join_results_to_split_assignments

        self.assertEqual(join_results_to_split_assignments((), self.split_index), ())

    def test_join_does_not_guess_by_sample_id_or_family(self) -> None:
        from covalent_design.evaluation.split_metrics import join_results_to_split_assignments

        bad = (_result("UNMAPPED", 1, family="CYS_MICHAEL_ADDITION"),)
        with self.assertRaises(ContractError) as ctx:
            join_results_to_split_assignments(bad, self.split_index)
        self.assertEqual(ctx.exception.code, "SPLIT_REPORT_ASSIGNMENT_MISSING")

    def test_join_rejects_corrupt_lifecycle_result_before_aggregation(self) -> None:
        from covalent_design.evaluation.split_metrics import join_results_to_split_assignments

        corrupt = CovalentGenerationResult(
            request_id="SR000000000000000000000000000001",
            sample_id=0,
            residue_reaction_family="CYS_MICHAEL_ADDITION",
            target_atom_identity=TARGET_ATOM,
            generation_validity_status="invalid",
            complex_export_status="not_applicable",
            docking_eligibility_status="not_applicable",
            docking_run_status="succeeded",
            primary_failure_reason="GEOMETRY_CHECK_FAIL",
            secondary_failure_reasons=(),
        )
        with self.assertRaises(ContractError) as ctx:
            join_results_to_split_assignments((corrupt,), self.split_index)
        self.assertEqual(ctx.exception.code, "SPLIT_REPORT_RESULT_VALIDATION_FAILED")

    def test_split_summary_has_train_val_test_and_excluded_accounting(self) -> None:
        from covalent_design.evaluation.split_metrics import (
            build_stratified_evaluation_summary,
            stratified_evaluation_summary_to_dict,
        )

        summary = build_stratified_evaluation_summary(self.results, self.split_index, self.leakage)
        data = stratified_evaluation_summary_to_dict(summary)
        self.assertEqual(set(data["per_split"].keys()), {"train", "val", "test"})
        self.assertEqual(data["per_split"]["train"]["summary"]["accepted_request_sample_count"], 2)
        self.assertEqual(data["per_split"]["val"]["summary"]["invalid_generated_sample_count"], 1)
        self.assertEqual(data["per_split"]["test"]["summary"]["accepted_request_sample_count"], 1)
        self.assertEqual(data["excluded_summary"]["excluded_record_count"], 2)

    def test_per_split_summaries_are_evaluation_summary_compatible(self) -> None:
        from covalent_design.evaluation.split_metrics import (
            build_stratified_evaluation_summary,
            stratified_evaluation_summary_to_dict,
        )

        summary = build_stratified_evaluation_summary(self.results, self.split_index, self.leakage)
        data = stratified_evaluation_summary_to_dict(summary)
        for split_name in ("train", "val", "test"):
            split_summary = EvaluationSummary(**data["per_split"][split_name]["summary"])
            self.assertTrue(
                validate_evaluation_summary(split_summary).passed,
                split_name,
            )

    def test_summarize_split_results_standalone_is_evaluation_summary_compatible(self) -> None:
        from covalent_design.evaluation.split_metrics import summarize_split_results

        data = summarize_split_results(self.results, self.split_index)
        self.assertEqual(set(data["per_split"].keys()), {"train", "val", "test"})
        for split_name in ("train", "val", "test"):
            split_summary = EvaluationSummary(**data["per_split"][split_name]["summary"])
            self.assertTrue(validate_evaluation_summary(split_summary).passed, split_name)

    def test_family_breakdown_uses_residue_reaction_family(self) -> None:
        from covalent_design.evaluation.split_metrics import (
            build_stratified_evaluation_summary,
            stratified_evaluation_summary_to_dict,
        )

        summary = build_stratified_evaluation_summary(self.results, self.split_index, self.leakage)
        data = stratified_evaluation_summary_to_dict(summary)
        self.assertIn("CYS_MICHAEL_ADDITION", data["per_family"])
        self.assertIn("LYS_IMINE_FORMATION", data["per_family"])
        self.assertNotIn("reaction_family", json.dumps(data, sort_keys=True))

    def test_primary_metric_sections_use_split_index_scaffold_and_cluster(self) -> None:
        from covalent_design.evaluation.split_metrics import (
            build_stratified_evaluation_summary,
            stratified_evaluation_summary_to_dict,
        )

        summary = build_stratified_evaluation_summary(self.results, self.split_index, self.leakage)
        data = stratified_evaluation_summary_to_dict(summary)
        self.assertEqual(data["protein_cluster_primary_metrics"]["per_split"]["train"]["unique_count"], 2)
        self.assertEqual(
            data["protein_cluster_primary_metrics"]["per_split"]["train"]["values"],
            ["PC_A", "PC_B"],
        )
        self.assertEqual(data["scaffold_primary_metrics"]["per_split"]["train"]["unique_count"], 2)
        self.assertIn("CC=CC=O", data["scaffold_primary_metrics"]["per_split"]["train"]["values"])

    def test_fallback_and_manual_review_accounting_are_reported(self) -> None:
        from covalent_design.evaluation.split_metrics import (
            build_stratified_evaluation_summary,
            stratified_evaluation_summary_to_dict,
        )

        summary = build_stratified_evaluation_summary(self.results, self.split_index, self.leakage)
        data = stratified_evaluation_summary_to_dict(summary)
        self.assertEqual(data["fallback_exclusions"]["by_reason"]["missing_scaffold_input"]["count"], 1)
        self.assertEqual(
            data["fallback_exclusions"]["by_reason"]["missing_scaffold_input"]["record_ids"],
            ["SR000000000000000000000000000005"],
        )
        self.assertEqual(data["fallback_exclusions"]["by_reason"]["warhead_unmatched"]["count"], 1)
        self.assertEqual(data["manual_review_accounting"]["pending"], 1)


class OptionalDockingAndWriterTests(unittest.TestCase):
    def test_optional_docking_index_counts_by_split_and_family(self) -> None:
        from covalent_design.evaluation.split_metrics import (
            build_stratified_evaluation_summary,
            load_leakage_report,
            load_split_index,
            stratified_evaluation_summary_to_dict,
        )

        split_index = load_split_index(FIXTURES / "valid_split_index.json")
        leakage = load_leakage_report(FIXTURES / "valid_leakage_report.json")
        docking_index = {
            "entries": [
                {
                    "request_id": "SR000000000000000000000000000001",
                    "sample_id": 0,
                    "docking_protocol_id": "dock-a",
                },
                {
                    "request_id": "SR000000000000000000000000000004",
                    "sample_id": 3,
                    "docking_protocol_id": "dock-b",
                },
            ]
        }
        summary = build_stratified_evaluation_summary(_valid_results(), split_index, leakage, docking_index=docking_index)
        data = stratified_evaluation_summary_to_dict(summary)
        self.assertEqual(data["docking_score_eligible_counts"]["per_split"]["train"], 1)
        self.assertEqual(data["docking_score_eligible_counts"]["per_split"]["test"], 1)
        self.assertEqual(
            data["docking_score_eligible_counts"]["per_family"]["CYS_MICHAEL_ADDITION"],
            1,
        )

    def test_absent_docking_index_is_allowed(self) -> None:
        from covalent_design.evaluation.split_metrics import (
            build_stratified_evaluation_summary,
            load_leakage_report,
            load_split_index,
            stratified_evaluation_summary_to_dict,
        )

        summary = build_stratified_evaluation_summary(
            _valid_results(),
            load_split_index(FIXTURES / "valid_split_index.json"),
            load_leakage_report(FIXTURES / "valid_leakage_report.json"),
        )
        data = stratified_evaluation_summary_to_dict(summary)
        self.assertIsNone(data["docking_score_eligible_counts"])

    def test_writer_is_deterministic_and_returns_artifact_ref(self) -> None:
        from covalent_design.evaluation.split_metrics import (
            build_stratified_evaluation_summary,
            load_leakage_report,
            load_split_index,
            write_stratified_evaluation_summary,
        )

        summary = build_stratified_evaluation_summary(
            _valid_results(),
            load_split_index(FIXTURES / "valid_split_index.json"),
            load_leakage_report(FIXTURES / "valid_leakage_report.json"),
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "stratified_evaluation_summary.json"
            ref1 = write_stratified_evaluation_summary(summary, path)
            first = path.read_bytes()
            ref2 = write_stratified_evaluation_summary(summary, path)
            second = path.read_bytes()
            self.assertEqual(first, second)
            self.assertEqual(hashlib.sha256(first).hexdigest(), ref1.sha256)
            self.assertEqual(ref1, ref2)
            self.assertEqual(ref1.role, "stratified_evaluation_summary")
            self.assertFalse(list(Path(tmp).glob("*.tmp")))

    def test_writer_does_not_mutate_inputs(self) -> None:
        from covalent_design.evaluation.split_metrics import (
            build_stratified_evaluation_summary,
            load_leakage_report,
            load_split_index,
            write_stratified_evaluation_summary,
        )

        split_path = FIXTURES / "valid_split_index.json"
        leakage_path = FIXTURES / "valid_leakage_report.json"
        before = (split_path.read_bytes(), leakage_path.read_bytes())
        summary = build_stratified_evaluation_summary(
            _valid_results(),
            load_split_index(split_path),
            load_leakage_report(leakage_path),
        )
        with tempfile.TemporaryDirectory() as tmp:
            write_stratified_evaluation_summary(summary, Path(tmp) / "stratified_evaluation_summary.json")
        after = (split_path.read_bytes(), leakage_path.read_bytes())
        self.assertEqual(before, after)


class SourceGuardTests(unittest.TestCase):
    def test_no_heavy_dependencies_loaded(self) -> None:
        import covalent_design.evaluation.split_metrics  # noqa: F401

        forbidden = {"rdkit", "torch", "PMDM", "PocketFlow", "vina", "openbabel"}
        loaded = set(sys.modules)
        self.assertFalse(forbidden & loaded)


if __name__ == "__main__":
    unittest.main()
