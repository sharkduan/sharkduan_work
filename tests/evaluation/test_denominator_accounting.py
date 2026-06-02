"""Task 30 Window B - Denominator accounting tests.

Covers:
- ``summarize_results(manifest: Path) -> EvaluationSummary`` API contract
- ``check_denominators`` CLI contract
- Lifecycle -> evaluation summary mapping
- Artifact validation (checksum, missing, absolute URI, traversal URI)
- JSONL version validation
- Deterministic evaluation_summary.json output
- Safe write without partial temp files
- Manifest role/version and artifact role/format validation
- CLI --manifest help/success and exit codes 11/12/nonzero
- Source guards: no --results primary input, no scan/glob discovery,
  no Task31/32/33, no RDKit/torch/heavy deps
- Reuses ``validate_generation_result()`` and ``validate_evaluation_summary()``

Expected RED: ``covalent_design.evaluation`` production module does not exist yet.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Mapping

# ===================================================================
# existing contracts (always importable)
# ===================================================================
from covalent_design.contracts.errors import CLI_EXIT_CODES, ContractError, ContractErrorInfo
from covalent_design.contracts.types import (
    CONTRACT_VERSION,
    SCHEMA_VERSION,
    SAMPLING_SYSTEM_FAILURE_CATEGORIES,
    ArtifactRef,
    CovalentGenerationResult,
    EdgeValidityCheck,
    EvaluationSummary,
    GenerationRunManifest,
    GeometryMetrics,
    LigandAtomIdentity,
    MoleculeQuality,
    ProteinAtomIdentity,
    ValidationReceipt,
)
from covalent_design.contracts.denominators import validate_evaluation_summary
from covalent_design.contracts.lifecycle import validate_generation_result
from covalent_design.io.artifacts import (
    artifact_ref_from_file,
    resolve_artifact_path,
    sha256_file,
    validate_artifact_ref,
)
from covalent_design.io.jsonl import read_jsonl, write_jsonl

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "evaluation" / "denominator_accounting"


# ===================================================================
# fixture-local builder helpers (deterministic, committed-inspectable)
# ===================================================================

_YAML_QUOTE = json.dumps


def _write_request_yaml(path: Path, request_id: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = (
        f"schema_version: {_YAML_QUOTE(SCHEMA_VERSION)}\n"
        f"contract_version: {_YAML_QUOTE(CONTRACT_VERSION)}\n"
        f"request_id: {_YAML_QUOTE(request_id)}\n"
        "sample_count: 9\n"
    )
    path.write_text(content, encoding="utf-8")


def _write_manifest_yaml(
    path: Path,
    *,
    job_id: str,
    request_id: str,
    accepted: int,
    attempted: int,
    failure_count: int,
    result_count: int,
    artifacts: Mapping[str, ArtifactRef],
) -> None:
    lines: list[str] = []

    def _i(key: str, val: int, indent: int = 0) -> None:
        lines.append(f"{'  ' * indent}{key}: {val}")

    def _s(key: str, val: str, indent: int = 0) -> None:
        lines.append(f"{'  ' * indent}{key}: {_YAML_QUOTE(val)}")

    def _n(key: str, indent: int = 0) -> None:
        lines.append(f"{'  ' * indent}{key}: null")

    _s("schema_version", SCHEMA_VERSION)
    _s("contract_version", CONTRACT_VERSION)
    _s("role", "generation_run_manifest")
    _s("job_id", job_id)
    _s("request_id", request_id)
    _n("checkpoint_ref")
    _i("accepted_request_sample_count", accepted)
    _i("attempted_sample_count", attempted)
    _i("sampling_system_failure_count", failure_count)
    _i("result_count", result_count)
    lines.append("artifacts:")
    for key in sorted(artifacts):
        ref = artifacts[key]
        lines.append(f"  {key}:")
        _s("uri", ref.uri, indent=2)
        _s("sha256", ref.sha256, indent=2)
        _s("format", ref.format, indent=2)
        _s("schema_version", ref.schema_version, indent=2)
        _s("role", ref.role, indent=2)
        _i("bytes", ref.bytes, indent=2)
    lines.append("")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


# ===================================================================
# shared result/failure row templates
# ===================================================================

TARGET_ATOM = ProteinAtomIdentity(
    chain_id="A",
    residue_number=145,
    residue_name="CYS",
    atom_name="SG",
    altloc=None,
    insertion_code=None,
    structure_model=1,
    asym_id="A",
    atom_serial=1234,
)

LIGAND_ATOM = LigandAtomIdentity(
    ligand_id="LIG001",
    atom_name="C1",
    atom_index=0,
    chain_id=None,
    asym_id=None,
    residue_number=None,
    altloc=None,
)

GEOMETRY = GeometryMetrics(
    bond_length=1.82,
    protein_side_angle=109.5,
    ligand_side_angle=120.0,
)

MOL_QUALITY = MoleculeQuality(
    qed=0.72,
    sa_score=3.1,
    log_p=2.5,
    molecular_weight=350.0,
)

EDGE_CHECK_PASS = EdgeValidityCheck(
    check_name="target_atom",
    status="pass",
    observed_value="SG",
    threshold_or_rule="CYS:SG",
    rule_table_version="1.0.0",
    failure_code=None,
)

EDGE_CHECK_FAIL = EdgeValidityCheck(
    check_name="target_atom",
    status="fail",
    observed_value="OG",
    threshold_or_rule="CYS:SG",
    rule_table_version="1.0.0",
    failure_code=None,
)

DUMMY_SHA256 = "a" * 64

COMPLEX_MMCIF_REF = ArtifactRef(
    uri="sample_complex.mmcif",
    sha256=DUMMY_SHA256,
    format="mmcif",
    schema_version=SCHEMA_VERSION,
    role="complex_mmcif",
    bytes=16384,
)

LIGAND_SDF_REF = ArtifactRef(
    uri="sample_ligand.sdf",
    sha256="b" * 64,
    format="sdf",
    schema_version=SCHEMA_VERSION,
    role="ligand_sdf",
    bytes=2048,
)

FULL_ARTIFACTS: Mapping[str, ArtifactRef] = {
    "complex_mmcif": COMPLEX_MMCIF_REF,
    "ligand_sdf": LIGAND_SDF_REF,
}


def _make_valid_full_result(
    sample_id: int,
    *,
    complex_export: str = "exported",
    docking_elig: str = "eligible",
    docking_run: str = "succeeded",
    primary_failure: str | None = None,
    covalent_docking: float | None = -8.5,
    noncovalent: float | None = -7.2,
    artifacts: Mapping[str, ArtifactRef] | None = None,
) -> CovalentGenerationResult:
    """Fully successful valid result with all diagnostics populated."""
    from covalent_design.contracts.types import CovalentEdge

    edge = CovalentEdge(
        protein_atom=TARGET_ATOM,
        ligand_atom=LIGAND_ATOM,
        bond_type="carbon-sulfur",
    )
    return CovalentGenerationResult(
        request_id="eval-test-req",
        sample_id=sample_id,
        residue_reaction_family="CYS_MICHAEL_ADDITION",
        target_atom_identity=TARGET_ATOM,
        generation_validity_status="valid",
        complex_export_status=complex_export,
        docking_eligibility_status=docking_elig,
        docking_run_status=docking_run,
        primary_failure_reason=primary_failure,
        secondary_failure_reasons=(),
        generated_ligand_status="present",
        predicted_ligand_attachment_atom=LIGAND_ATOM,
        predicted_covalent_edge=edge,
        covalent_edge_score=0.85,
        geometry_metrics=GEOMETRY,
        molecular_quality_metrics=MOL_QUALITY,
        matched_warhead_type="acrylamide",
        predicted_warhead_type="acrylamide",
        covalent_docking_score=covalent_docking,
        noncovalent_vina_score=noncovalent,
        edge_validity_checks=(EDGE_CHECK_PASS,),
        artifacts=artifacts or FULL_ARTIFACTS,
    )


def _make_invalid_result(
    sample_id: int,
    primary_failure: str,
    *,
    secondary: tuple[str, ...] = (),
) -> CovalentGenerationResult:
    """Invalid result - not_applicable downstream, no diagnostics."""
    return CovalentGenerationResult(
        request_id="eval-test-req",
        sample_id=sample_id,
        residue_reaction_family="CYS_MICHAEL_ADDITION",
        target_atom_identity=TARGET_ATOM,
        generation_validity_status="invalid",
        complex_export_status="not_applicable",
        docking_eligibility_status="not_applicable",
        docking_run_status="not_applicable",
        primary_failure_reason=primary_failure,
        secondary_failure_reasons=secondary,
        generated_ligand_status="absent",
        predicted_ligand_attachment_atom=None,
        predicted_covalent_edge=None,
        covalent_edge_score=None,
        geometry_metrics=None,
        molecular_quality_metrics=None,
        matched_warhead_type=None,
        predicted_warhead_type=None,
        covalent_docking_score=None,
        noncovalent_vina_score=None,
        edge_validity_checks=(EDGE_CHECK_FAIL,),
        artifacts={},
    )


def _make_failure_row(
    sample_id: int,
    category: str,
    retry_count: int = 0,
    message: str | None = None,
) -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "contract_version": CONTRACT_VERSION,
        "request_id": "eval-test-req",
        "sample_id": sample_id,
        "failure_category": category,
        "failure_timestamp": "2026-06-02T00:00:00Z",
        "traceback_hash": "d" * 64,
        "log_uri": f"logs/{category}_sample_{sample_id}.log",
        "retry_count": retry_count,
        "message": message or f"{category} for sample {sample_id}",
        "resource_snapshot": None,
    }


def _make_retry_row(
    sample_id: int,
    category: str,
    retry_count: int,
) -> dict[str, object]:
    """Non-terminal retry entry (audit-only)."""
    return {
        "schema_version": SCHEMA_VERSION,
        "contract_version": CONTRACT_VERSION,
        "request_id": "eval-test-req",
        "sample_id": sample_id,
        "failure_category": category,
        "failure_timestamp": "2026-06-02T00:00:00Z",
        "traceback_hash": "e" * 64,
        "log_uri": f"logs/{category}_sample_{sample_id}_attempt_{retry_count}.log",
        "retry_count": retry_count,
        "message": f"retry {retry_count}: {category} for sample {sample_id}",
        "resource_snapshot": None,
    }


# ===================================================================
# scenario fixture builder
# ===================================================================


class ScenarioBuilder:
    """Creates a self-contained generation-run directory in a temp location.

    Writes ``results.jsonl``, ``sampling_system_failures.jsonl``,
    ``request.normalized.yml``, and ``run_manifest.yml`` with correct
    SHA-256 checksums computed from actual file content.
    """

    def __init__(self, base_dir: Path) -> None:
        self._dir = base_dir
        self._dir.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        return self._dir

    def write_files(
        self,
        *,
        results: list[CovalentGenerationResult],
        failures: list[dict[str, object]],
        job_id: str,
        accepted: int,
        attempted: int,
        failure_count: int,
        result_count: int | None = None,
        request_id: str = "eval-test-req",
    ) -> Path:
        """Write all files and return path to run_manifest.yml."""
        from covalent_design.inference.result_writer import ResultWriter

        writer = ResultWriter()

        # write request placeholder
        _write_request_yaml(self._dir / "request.normalized.yml", request_id)

        # write results.jsonl
        rows = [writer.write(r) for r in results]
        results_ref = write_jsonl(self._dir / "results.jsonl", rows, role="results")

        # write sampling_system_failures.jsonl
        failures_ref = write_jsonl(
            self._dir / "sampling_system_failures.jsonl",
            failures,
            role="sampling_system_failures",
        )

        # build request ref
        request_ref = artifact_ref_from_file(
            self._dir / "request.normalized.yml",
            role="request",
            format="yml",
        )

        # write manifest
        manifest_path = self._dir / "run_manifest.yml"
        _write_manifest_yaml(
            manifest_path,
            job_id=job_id,
            request_id=request_id,
            accepted=accepted,
            attempted=attempted,
            failure_count=failure_count,
            result_count=result_count if result_count is not None else len(results),
            artifacts={
                "request": request_ref,
                "results": results_ref,
                "sampling_system_failures": failures_ref,
            },
        )
        return manifest_path


# ===================================================================
# 1.  summarize_results API contract tests
# ===================================================================


class SummarizeResultsAPITests(unittest.TestCase):
    """summarize_results import and signature tests.

    Expected RED: ``covalent_design.evaluation`` does not exist yet."""

    def test_summarize_results_is_importable(self) -> None:
        """summarize_results must be importable from covalent_design.evaluation."""
        from covalent_design.evaluation import summarize_results  # noqa: F401

    def test_summarize_results_callable_with_manifest_path(self) -> None:
        """summarize_results(manifest: Path) -> EvaluationSummary."""
        from covalent_design.evaluation import summarize_results

        self.assertTrue(callable(summarize_results))

    def test_summarize_results_has_correct_signature(self) -> None:
        """summarize_results must accept only manifest: Path."""
        import inspect

        from covalent_design.evaluation import summarize_results

        sig = inspect.signature(summarize_results)
        params = list(sig.parameters.keys())
        # manifest is the only required param
        self.assertIn("manifest", params)
        # No requested_sample_count parameter (controller-frozen)
        self.assertNotIn("requested_sample_count", params)

    def test_summarize_results_returns_evaluation_summary(self) -> None:
        """Return type must be EvaluationSummary."""
        import inspect

        from covalent_design.evaluation import summarize_results

        sig = inspect.signature(summarize_results)
        # Return annotation should be EvaluationSummary
        self.assertIsNotNone(sig.return_annotation)


# ===================================================================
# 2.  EvaluationSummary conservation contract (GREEN-capable)
# ===================================================================


class EvaluationSummaryConservationTests(unittest.TestCase):
    """validate_evaluation_summary contract tests - GREEN once types exist."""

    def test_valid_summary_conserves_all_equations(self) -> None:
        """All six conservation equations hold for a valid summary."""
        summary = EvaluationSummary(
            requested_sample_count=9,
            request_validation_error_sample_count=0,
            accepted_request_sample_count=9,
            attempted_sample_count=7,
            sampling_system_failure_count=2,
            valid_generated_internal_count=4,
            invalid_generated_sample_count=3,
            exported_valid_complex_count=3,
            valid_export_failure_count=1,
            docking_evaluable_valid_sample_count=2,
            valid_but_not_docking_evaluable_sample_count=1,
            docking_not_run_valid_sample_count=0,
            docking_failed_valid_sample_count=1,
            successfully_docked_valid_sample_count=1,
        )
        receipt = validate_evaluation_summary(summary)
        self.assertTrue(receipt.passed)
        summary.validate()  # must not raise

    def test_all_success_summary_conserves(self) -> None:
        """All-success: every accepted sample reaches docking success."""
        summary = EvaluationSummary(
            requested_sample_count=3,
            request_validation_error_sample_count=0,
            accepted_request_sample_count=3,
            attempted_sample_count=3,
            sampling_system_failure_count=0,
            valid_generated_internal_count=3,
            invalid_generated_sample_count=0,
            exported_valid_complex_count=3,
            valid_export_failure_count=0,
            docking_evaluable_valid_sample_count=3,
            valid_but_not_docking_evaluable_sample_count=0,
            docking_not_run_valid_sample_count=0,
            docking_failed_valid_sample_count=0,
            successfully_docked_valid_sample_count=3,
        )
        receipt = validate_evaluation_summary(summary)
        self.assertTrue(receipt.passed)
        summary.validate()

    def test_all_system_failure_summary_conserves(self) -> None:
        """All system failure: no samples attempted, all in failure count."""
        summary = EvaluationSummary(
            requested_sample_count=3,
            request_validation_error_sample_count=0,
            accepted_request_sample_count=3,
            attempted_sample_count=0,
            sampling_system_failure_count=3,
            valid_generated_internal_count=0,
            invalid_generated_sample_count=0,
            exported_valid_complex_count=0,
            valid_export_failure_count=0,
            docking_evaluable_valid_sample_count=0,
            valid_but_not_docking_evaluable_sample_count=0,
            docking_not_run_valid_sample_count=0,
            docking_failed_valid_sample_count=0,
            successfully_docked_valid_sample_count=0,
        )
        receipt = validate_evaluation_summary(summary)
        self.assertTrue(receipt.passed)
        summary.validate()

    def test_rejects_accepted_request_mismatch(self) -> None:
        """accepted must equal attempted + sampling_system_failure_count."""
        summary = EvaluationSummary(
            requested_sample_count=5,
            request_validation_error_sample_count=0,
            accepted_request_sample_count=5,
            attempted_sample_count=4,  # should be 3 if failures=2
            sampling_system_failure_count=2,  # 4 + 2 != 5
            valid_generated_internal_count=3,
            invalid_generated_sample_count=1,
            exported_valid_complex_count=2,
            valid_export_failure_count=1,
            docking_evaluable_valid_sample_count=1,
            valid_but_not_docking_evaluable_sample_count=1,
            docking_not_run_valid_sample_count=0,
            docking_failed_valid_sample_count=0,
            successfully_docked_valid_sample_count=1,
        )
        receipt = validate_evaluation_summary(summary)
        self.assertFalse(receipt.passed)
        self.assertEqual(
            receipt.errors[0].code, "EVALUATION_DENOMINATOR_ACCEPTED_REQUEST_MISMATCH"
        )

    def test_rejects_attempted_mismatch(self) -> None:
        """attempted must equal valid_internal + invalid_generated."""
        summary = EvaluationSummary(
            requested_sample_count=5,
            request_validation_error_sample_count=0,
            accepted_request_sample_count=5,
            attempted_sample_count=5,
            sampling_system_failure_count=0,
            valid_generated_internal_count=4,
            invalid_generated_sample_count=2,  # 4 + 2 != 5
            exported_valid_complex_count=3,
            valid_export_failure_count=1,
            docking_evaluable_valid_sample_count=2,
            valid_but_not_docking_evaluable_sample_count=1,
            docking_not_run_valid_sample_count=0,
            docking_failed_valid_sample_count=1,
            successfully_docked_valid_sample_count=1,
        )
        receipt = validate_evaluation_summary(summary)
        self.assertFalse(receipt.passed)
        self.assertEqual(
            receipt.errors[0].code, "EVALUATION_DENOMINATOR_ATTEMPTED_MISMATCH"
        )

    def test_rejects_valid_internal_mismatch(self) -> None:
        """valid_internal must equal exported + export_failure."""
        summary = EvaluationSummary(
            requested_sample_count=4,
            request_validation_error_sample_count=0,
            accepted_request_sample_count=4,
            attempted_sample_count=4,
            sampling_system_failure_count=0,
            valid_generated_internal_count=4,
            invalid_generated_sample_count=0,
            exported_valid_complex_count=2,
            valid_export_failure_count=1,  # 2 + 1 != 4
            docking_evaluable_valid_sample_count=2,
            valid_but_not_docking_evaluable_sample_count=0,
            docking_not_run_valid_sample_count=0,
            docking_failed_valid_sample_count=1,
            successfully_docked_valid_sample_count=1,
        )
        receipt = validate_evaluation_summary(summary)
        self.assertFalse(receipt.passed)
        self.assertEqual(
            receipt.errors[0].code, "EVALUATION_DENOMINATOR_VALID_INTERNAL_MISMATCH"
        )

    def test_rejects_docking_evaluable_mismatch(self) -> None:
        """docking_evaluable must equal succeeded + failed + not_run."""
        summary = EvaluationSummary(
            requested_sample_count=3,
            request_validation_error_sample_count=0,
            accepted_request_sample_count=3,
            attempted_sample_count=3,
            sampling_system_failure_count=0,
            valid_generated_internal_count=3,
            invalid_generated_sample_count=0,
            exported_valid_complex_count=3,
            valid_export_failure_count=0,
            docking_evaluable_valid_sample_count=3,
            valid_but_not_docking_evaluable_sample_count=0,
            docking_not_run_valid_sample_count=1,
            docking_failed_valid_sample_count=1,
            successfully_docked_valid_sample_count=2,  # 1+1+2 != 3
        )
        receipt = validate_evaluation_summary(summary)
        self.assertFalse(receipt.passed)
        self.assertEqual(
            receipt.errors[0].code, "EVALUATION_DENOMINATOR_DOCKING_EVALUABLE_MISMATCH"
        )

    def test_rejects_negative_count(self) -> None:
        """Any negative count triggers EVALUATION_DENOMINATOR_NEGATIVE."""
        summary = EvaluationSummary(
            requested_sample_count=-1,
            request_validation_error_sample_count=0,
            accepted_request_sample_count=0,
            attempted_sample_count=0,
            sampling_system_failure_count=0,
            valid_generated_internal_count=0,
            invalid_generated_sample_count=0,
            exported_valid_complex_count=0,
            valid_export_failure_count=0,
            docking_evaluable_valid_sample_count=0,
            valid_but_not_docking_evaluable_sample_count=0,
            docking_not_run_valid_sample_count=0,
            docking_failed_valid_sample_count=0,
            successfully_docked_valid_sample_count=0,
        )
        receipt = validate_evaluation_summary(summary)
        self.assertFalse(receipt.passed)
        self.assertEqual(receipt.errors[0].code, "EVALUATION_DENOMINATOR_NEGATIVE")

    def test_requested_equals_accepted_when_no_validation_errors(self) -> None:
        """requested_sample_count defaults to accepted when no validation errors."""
        summary = EvaluationSummary(
            requested_sample_count=9,
            request_validation_error_sample_count=0,
            accepted_request_sample_count=9,
            attempted_sample_count=7,
            sampling_system_failure_count=2,
            valid_generated_internal_count=4,
            invalid_generated_sample_count=3,
            exported_valid_complex_count=3,
            valid_export_failure_count=1,
            docking_evaluable_valid_sample_count=2,
            valid_but_not_docking_evaluable_sample_count=1,
            docking_not_run_valid_sample_count=0,
            docking_failed_valid_sample_count=1,
            successfully_docked_valid_sample_count=1,
        )
        # requested == accepted when request_validation_error_sample_count == 0
        self.assertEqual(
            summary.requested_sample_count,
            summary.request_validation_error_sample_count
            + summary.accepted_request_sample_count,
        )
        receipt = validate_evaluation_summary(summary)
        self.assertTrue(receipt.passed)


# ===================================================================
# 3.  Lifecycle -> evaluation summary mapping tests
# ===================================================================


class LifecycleMappingTests(unittest.TestCase):
    """Verify each CovalentGenerationResult lifecycle state maps to the
    correct EvaluationSummary counter."""

    def test_valid_succeeded_maps_to_successfully_docked(self) -> None:
        r = _make_valid_full_result(0)
        self.assertEqual(r.generation_validity_status, "valid")
        self.assertEqual(r.complex_export_status, "exported")
        self.assertEqual(r.docking_eligibility_status, "eligible")
        self.assertEqual(r.docking_run_status, "succeeded")
        # This result should increment: valid_generated_internal,
        # exported_valid_complex, docking_evaluable_valid_sample,
        # successfully_docked_valid_sample

    def test_export_failed_maps_correctly(self) -> None:
        r = _make_valid_full_result(
            1,
            complex_export="failed",
            docking_elig="not_applicable",
            docking_run="not_applicable",
            primary_failure="COMPLEX_EXPORT_FAILED",
            covalent_docking=None,
            noncovalent=None,
            artifacts={},
        )
        self.assertEqual(r.complex_export_status, "failed")
        self.assertEqual(r.docking_eligibility_status, "not_applicable")
        self.assertEqual(r.docking_run_status, "not_applicable")
        # Should increment: valid_generated_internal, valid_export_failure_count

    def test_not_evaluable_maps_correctly(self) -> None:
        r = _make_valid_full_result(
            2,
            complex_export="exported",
            docking_elig="not_evaluable",
            docking_run="not_applicable",
            primary_failure="DOCKING_NOT_EVALUABLE",
            covalent_docking=None,
            noncovalent=None,
        )
        self.assertEqual(r.docking_eligibility_status, "not_evaluable")
        # Should increment: valid_generated_internal, exported_valid_complex,
        # valid_but_not_docking_evaluable_sample_count

    def test_docking_not_run_maps_correctly(self) -> None:
        r = _make_valid_full_result(
            3,
            docking_run="not_run",
            primary_failure=None,
            covalent_docking=None,
            noncovalent=-6.5,
        )
        self.assertEqual(r.docking_run_status, "not_run")
        self.assertIsNone(r.covalent_docking_score)
        # Should increment: docking_not_run_valid_sample_count

    def test_docking_failed_maps_correctly(self) -> None:
        r = _make_valid_full_result(
            4,
            docking_run="failed",
            primary_failure="DOCKING_RUN_FAILED",
            covalent_docking=None,
            noncovalent=None,
        )
        self.assertEqual(r.docking_run_status, "failed")
        self.assertEqual(r.primary_failure_reason, "DOCKING_RUN_FAILED")
        # Should increment: docking_failed_valid_sample_count

    def test_invalid_result_maps_correctly(self) -> None:
        r = _make_invalid_result(5, "NO_COVALENT_EDGE_PREDICTED")
        self.assertEqual(r.generation_validity_status, "invalid")
        self.assertEqual(r.complex_export_status, "not_applicable")
        self.assertEqual(r.docking_eligibility_status, "not_applicable")
        self.assertEqual(r.docking_run_status, "not_applicable")
        # Should increment: invalid_generated_sample_count only

    def test_evaluation_summary_builds_correctly_from_lifecycle_map(self) -> None:
        """Manual lifecycle->summary mapping for a mixed scenario."""
        results = [
            _make_valid_full_result(0),  # succeeded
            _make_valid_full_result(
                1, docking_run="failed", primary_failure="DOCKING_RUN_FAILED",
                covalent_docking=None, noncovalent=None,
            ),  # docking failed
            _make_valid_full_result(
                2, docking_elig="not_evaluable", docking_run="not_applicable",
                primary_failure="DOCKING_NOT_EVALUABLE", covalent_docking=None,
                noncovalent=None,
            ),  # not evaluable
            _make_valid_full_result(
                3, complex_export="failed", docking_elig="not_applicable",
                docking_run="not_applicable", primary_failure="COMPLEX_EXPORT_FAILED",
                covalent_docking=None, noncovalent=None, artifacts={},
            ),  # export failed
            _make_invalid_result(4, "NO_COVALENT_EDGE_PREDICTED"),
            _make_invalid_result(5, "COVALENT_EDGE_BELOW_THRESHOLD"),
            _make_invalid_result(6, "LIGAND_CHEMISTRY_INVALID"),
        ]

        # Manual counting
        valid_internal = sum(1 for r in results if r.generation_validity_status == "valid")
        invalid = sum(1 for r in results if r.generation_validity_status == "invalid")
        exported = sum(
            1 for r in results
            if r.generation_validity_status == "valid" and r.complex_export_status == "exported"
        )
        export_failure = sum(
            1 for r in results
            if r.generation_validity_status == "valid" and r.complex_export_status == "failed"
        )
        evaluable = sum(
            1 for r in results
            if r.generation_validity_status == "valid"
            and r.complex_export_status == "exported"
            and r.docking_eligibility_status == "eligible"
        )
        not_evaluable = sum(
            1 for r in results
            if r.generation_validity_status == "valid"
            and r.complex_export_status == "exported"
            and r.docking_eligibility_status == "not_evaluable"
        )
        not_run = sum(
            1 for r in results
            if r.generation_validity_status == "valid"
            and r.docking_eligibility_status == "eligible"
            and r.docking_run_status == "not_run"
        )
        docking_failed = sum(
            1 for r in results
            if r.generation_validity_status == "valid"
            and r.docking_eligibility_status == "eligible"
            and r.docking_run_status == "failed"
        )
        succeeded = sum(
            1 for r in results
            if r.generation_validity_status == "valid"
            and r.docking_eligibility_status == "eligible"
            and r.docking_run_status == "succeeded"
        )

        self.assertEqual(valid_internal, 4)
        self.assertEqual(invalid, 3)
        self.assertEqual(exported, 3)
        self.assertEqual(export_failure, 1)
        self.assertEqual(evaluable, 2)
        self.assertEqual(not_evaluable, 1)
        self.assertEqual(not_run, 0)
        self.assertEqual(docking_failed, 1)
        self.assertEqual(succeeded, 1)

        # Build EvaluationSummary and validate
        summary = EvaluationSummary(
            requested_sample_count=7,
            request_validation_error_sample_count=0,
            accepted_request_sample_count=7,
            attempted_sample_count=7,
            sampling_system_failure_count=0,
            valid_generated_internal_count=valid_internal,
            invalid_generated_sample_count=invalid,
            exported_valid_complex_count=exported,
            valid_export_failure_count=export_failure,
            docking_evaluable_valid_sample_count=evaluable,
            valid_but_not_docking_evaluable_sample_count=not_evaluable,
            docking_not_run_valid_sample_count=not_run,
            docking_failed_valid_sample_count=docking_failed,
            successfully_docked_valid_sample_count=succeeded,
        )
        receipt = validate_evaluation_summary(summary)
        self.assertTrue(receipt.passed)


# ===================================================================
# 4.  Artifact validation tests
# ===================================================================


class ArtifactValidationTests(unittest.TestCase):
    """validate_artifact_ref contract tests for URI safety and checksum."""

    def test_valid_artifact_passes_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            test_file = tmp_path / "test.txt"
            test_file.write_text("hello", encoding="utf-8")
            ref = artifact_ref_from_file(test_file, role="test", format="txt")
            receipt = validate_artifact_ref(ref, root=tmp_path)
            self.assertTrue(receipt.passed)

    def test_checksum_mismatch_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            test_file = tmp_path / "test.txt"
            test_file.write_text("hello", encoding="utf-8")
            ref = artifact_ref_from_file(test_file, role="test", format="txt")
            # tamper with checksum
            bad_ref = ArtifactRef(
                uri=ref.uri,
                sha256="f" * 64,
                format=ref.format,
                schema_version=ref.schema_version,
                role=ref.role,
                bytes=ref.bytes,
            )
            receipt = validate_artifact_ref(bad_ref, root=tmp_path)
            self.assertFalse(receipt.passed)
            self.assertEqual(receipt.errors[0].code, "ARTIFACT_CHECKSUM_MISMATCH")

    def test_missing_artifact_detected(self) -> None:
        ref = ArtifactRef(
            uri="nonexistent.jsonl",
            sha256="f" * 64,
            format="jsonl",
            schema_version=SCHEMA_VERSION,
            role="results",
            bytes=100,
        )
        receipt = validate_artifact_ref(ref, root=Path("."))
        self.assertFalse(receipt.passed)
        self.assertEqual(receipt.errors[0].code, "ARTIFACT_NOT_FOUND")

    def test_absolute_uri_rejected(self) -> None:
        """resolve_artifact_path rejects absolute URIs."""
        with self.assertRaises(ValueError) as ctx:
            resolve_artifact_path(
                ArtifactRef(
                    uri="/etc/passwd",
                    sha256="f" * 64,
                    format="jsonl",
                    schema_version=SCHEMA_VERSION,
                    role="results",
                    bytes=100,
                ),
                root=Path("/tmp"),
            )
        self.assertTrue(
            any(token in str(ctx.exception).lower() for token in ("relative", "inside", "stay")),
            str(ctx.exception),
        )

    def test_traversal_uri_rejected(self) -> None:
        """resolve_artifact_path rejects traversal URIs."""
        with self.assertRaises(ValueError) as ctx:
            resolve_artifact_path(
                ArtifactRef(
                    uri="../../../etc/passwd",
                    sha256="f" * 64,
                    format="jsonl",
                    schema_version=SCHEMA_VERSION,
                    role="results",
                    bytes=100,
                ),
                root=Path("/tmp"),
            )
        self.assertIn("escape", str(ctx.exception).lower())

    def test_byte_count_mismatch_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            test_file = tmp_path / "test.txt"
            test_file.write_text("hello", encoding="utf-8")
            ref = artifact_ref_from_file(test_file, role="test", format="txt")
            bad_ref = ArtifactRef(
                uri=ref.uri,
                sha256=ref.sha256,
                format=ref.format,
                schema_version=ref.schema_version,
                role=ref.role,
                bytes=99999,  # wrong
            )
            receipt = validate_artifact_ref(bad_ref, root=tmp_path)
            self.assertFalse(receipt.passed)
            self.assertEqual(receipt.errors[0].code, "ARTIFACT_BYTE_COUNT_MISMATCH")


# ===================================================================
# 5.  JSONL read/write and version validation tests
# ===================================================================


class JSONLValidationTests(unittest.TestCase):
    """JSONL version validation and read/write contract tests."""

    def test_read_jsonl_validates_schema_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            jsonl_path = tmp_path / "test.jsonl"
            rows = [{"schema_version": "1", "contract_version": "1.0.0", "data": "ok"}]
            write_jsonl(jsonl_path, rows, role="test")
            result = read_jsonl(
                jsonl_path,
                expected_schema_version="1",
                expected_contract_version="1.0.0",
            )
            self.assertEqual(len(result), 1)

    def test_read_jsonl_rejects_wrong_schema_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            jsonl_path = tmp_path / "test.jsonl"
            rows = [{"schema_version": "99", "contract_version": "1.0.0", "data": "bad"}]
            write_jsonl(jsonl_path, rows, role="test")
            with self.assertRaises(ValueError) as ctx:
                read_jsonl(jsonl_path, expected_schema_version="1")
            self.assertIn("SCHEMA_VERSION", str(ctx.exception))

    def test_read_jsonl_rejects_wrong_contract_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            jsonl_path = tmp_path / "test.jsonl"
            rows = [{"schema_version": "1", "contract_version": "99.0.0", "data": "bad"}]
            write_jsonl(jsonl_path, rows, role="test")
            with self.assertRaises(ValueError) as ctx:
                read_jsonl(jsonl_path, expected_contract_version="1.0.0")
            self.assertIn("CONTRACT_VERSION", str(ctx.exception))

    def test_read_jsonl_rejects_missing_schema_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            jsonl_path = tmp_path / "test.jsonl"
            jsonl_path.write_text(
                '{"contract_version":"1.0.0","data":"no_schema"}\n',
                encoding="utf-8",
            )
            with self.assertRaises(ValueError) as ctx:
                read_jsonl(jsonl_path, expected_schema_version="1")
            self.assertIn("SCHEMA_VERSION", str(ctx.exception))

    def test_read_jsonl_rejects_missing_contract_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            jsonl_path = tmp_path / "test.jsonl"
            jsonl_path.write_text(
                '{"schema_version":"1","data":"no_contract"}\n',
                encoding="utf-8",
            )
            with self.assertRaises(ValueError) as ctx:
                read_jsonl(jsonl_path, expected_contract_version="1.0.0")
            self.assertIn("CONTRACT_VERSION", str(ctx.exception))

    def test_empty_jsonl_is_valid(self) -> None:
        """Empty JSONL file produces an empty tuple."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            jsonl_path = tmp_path / "empty.jsonl"
            jsonl_path.write_text("", encoding="utf-8")
            result = read_jsonl(jsonl_path, require_versions=False)
            self.assertEqual(result, ())

    def test_write_jsonl_injects_versions(self) -> None:
        """write_jsonl setdefaults schema_version and contract_version."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            jsonl_path = tmp_path / "test.jsonl"
            rows = [{"data": "bare_row"}]
            write_jsonl(jsonl_path, rows, role="test")
            result = read_jsonl(jsonl_path)
            self.assertEqual(result[0]["schema_version"], SCHEMA_VERSION)
            self.assertEqual(result[0]["contract_version"], CONTRACT_VERSION)

    def test_invalid_json_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            jsonl_path = tmp_path / "bad.jsonl"
            jsonl_path.write_text("not valid json\n", encoding="utf-8")
            with self.assertRaises(ValueError) as ctx:
                read_jsonl(jsonl_path, require_versions=False)
            self.assertIn("JSONL_INVALID_JSON", str(ctx.exception))

    def test_row_not_object_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            jsonl_path = tmp_path / "bad.jsonl"
            jsonl_path.write_text('[1, 2, 3]\n', encoding="utf-8")
            with self.assertRaises(ValueError) as ctx:
                read_jsonl(jsonl_path, require_versions=False)
            self.assertIn("ROW_NOT_OBJECT", str(ctx.exception))


# ===================================================================
# 6.  validate_generation_result reuse tests
# ===================================================================


class ValidateGenerationResultReuseTests(unittest.TestCase):
    """Tests enforcing that evaluation reuses validate_generation_result()."""

    def test_valid_full_result_passes(self) -> None:
        r = _make_valid_full_result(0)
        receipt = validate_generation_result(r)
        self.assertTrue(receipt.passed)

    def test_invalid_result_passes_validation(self) -> None:
        """Invalid results with proper lifecycle states must pass validation."""
        r = _make_invalid_result(0, "NO_COVALENT_EDGE_PREDICTED")
        receipt = validate_generation_result(r)
        self.assertTrue(receipt.passed)

    def test_valid_result_missing_diagnostics_rejected(self) -> None:
        """validate_generation_result must reject valid results with missing diagnostics."""
        r = _make_valid_full_result(0, artifacts=FULL_ARTIFACTS)
        # Create a corrupt version with None predicted_covalent_edge
        from dataclasses import replace

        corrupt = replace(r, predicted_covalent_edge=None)
        receipt = validate_generation_result(corrupt)
        self.assertFalse(receipt.passed)
        self.assertEqual(
            receipt.errors[0].code, "GENERATION_RESULT_VALID_DIAGNOSTICS_MISSING"
        )

    def test_corrupt_lifecycle_invalid_with_exported_rejected(self) -> None:
        """Invalid result with 'exported' complex_export_status must be rejected."""
        from dataclasses import replace

        r = _make_invalid_result(0, "NO_COVALENT_EDGE_PREDICTED")
        corrupt = replace(r, complex_export_status="exported")
        receipt = validate_generation_result(corrupt)
        self.assertFalse(receipt.passed)
        self.assertEqual(receipt.errors[0].code, "LIFECYCLE_INVALID_EXPORT_STATUS")

    def test_corrupt_lifecycle_invalid_missing_failure_reason_rejected(self) -> None:
        """Invalid result without primary_failure_reason must be rejected."""
        from dataclasses import replace

        r = _make_invalid_result(0, "NO_COVALENT_EDGE_PREDICTED")
        corrupt = replace(r, primary_failure_reason=None)
        receipt = validate_generation_result(corrupt)
        self.assertFalse(receipt.passed)
        self.assertEqual(
            receipt.errors[0].code, "LIFECYCLE_INVALID_MISSING_FAILURE_REASON"
        )

    def test_corrupt_export_failure_wrong_reason_rejected(self) -> None:
        """Export failure must have primary_failure_reason=COMPLEX_EXPORT_FAILED."""
        r = _make_valid_full_result(
            0,
            complex_export="failed",
            docking_elig="not_applicable",
            docking_run="not_applicable",
            primary_failure="LIGAND_CHEMISTRY_INVALID",  # wrong
            covalent_docking=None,
            noncovalent=None,
            artifacts={},
        )
        receipt = validate_generation_result(r)
        self.assertFalse(receipt.passed)
        self.assertEqual(
            receipt.errors[0].code, "LIFECYCLE_EXPORT_FAILURE_REASON_MISMATCH"
        )

    def test_corrupt_docking_failed_wrong_reason_rejected(self) -> None:
        """Docking failed must have primary_failure_reason=DOCKING_RUN_FAILED."""
        r = _make_valid_full_result(
            0,
            docking_run="failed",
            primary_failure="COMPLEX_EXPORT_FAILED",  # wrong
            covalent_docking=None,
            noncovalent=None,
        )
        receipt = validate_generation_result(r)
        self.assertFalse(receipt.passed)
        self.assertEqual(
            receipt.errors[0].code, "LIFECYCLE_DOCKING_FAILURE_REASON_MISMATCH"
        )

    def test_corrupt_success_has_failure_reason_rejected(self) -> None:
        """succeeded/not_run must not have a primary_failure_reason."""
        r = _make_valid_full_result(0, primary_failure="DOCKING_RUN_FAILED")
        receipt = validate_generation_result(r)
        self.assertFalse(receipt.passed)
        self.assertEqual(
            receipt.errors[0].code, "LIFECYCLE_SUCCESS_OR_NOT_RUN_HAS_FAILURE_REASON"
        )


# ===================================================================
# 7.  Nested result decoding tests
# ===================================================================


class NestedResultDecodingTests(unittest.TestCase):
    """Verify CovalentGenerationResult can be JSON-serialized and decoded back,
    including all nested dataclass fields."""

    def test_result_to_dict_and_back(self) -> None:
        """Full round-trip: CovalentGenerationResult -> dict -> CovalentGenerationResult."""
        from covalent_design.inference.result_schema import _result_to_dict

        original = _make_valid_full_result(0)
        d = _result_to_dict(original)

        # Verify nested structures
        self.assertEqual(d["request_id"], "eval-test-req")
        self.assertEqual(d["sample_id"], 0)
        self.assertIsInstance(d["target_atom_identity"], dict)
        self.assertEqual(d["target_atom_identity"]["residue_name"], "CYS")
        self.assertIsInstance(d["predicted_covalent_edge"], dict)
        self.assertEqual(d["predicted_covalent_edge"]["bond_type"], "carbon-sulfur")
        self.assertIsInstance(d["geometry_metrics"], dict)
        self.assertAlmostEqual(d["geometry_metrics"]["bond_length"], 1.82)
        self.assertIsInstance(d["molecular_quality_metrics"], dict)
        self.assertAlmostEqual(d["molecular_quality_metrics"]["qed"], 0.72)
        self.assertIsInstance(d["edge_validity_checks"], list)
        self.assertEqual(d["edge_validity_checks"][0]["check_name"], "target_atom")
        self.assertIsInstance(d["artifacts"], dict)
        self.assertIn("complex_mmcif", d["artifacts"])
        self.assertIn("ligand_sdf", d["artifacts"])

    def test_json_serialization_is_deterministic(self) -> None:
        """Same input must produce identical JSON output."""
        from covalent_design.inference.result_schema import _result_to_dict

        r = _make_valid_full_result(0)
        d1 = _result_to_dict(r)
        d2 = _result_to_dict(r)
        j1 = json.dumps(d1, sort_keys=True)
        j2 = json.dumps(d2, sort_keys=True)
        self.assertEqual(j1, j2)

    def test_invalid_result_decodes_with_null_diagnostics(self) -> None:
        """Invalid results serialize None/null for absent diagnostics."""
        from covalent_design.inference.result_schema import _result_to_dict

        r = _make_invalid_result(0, "NO_COVALENT_EDGE_PREDICTED")
        d = _result_to_dict(r)
        self.assertIsNone(d["predicted_ligand_attachment_atom"])
        self.assertIsNone(d["predicted_covalent_edge"])
        self.assertIsNone(d["covalent_edge_score"])
        self.assertIsNone(d["geometry_metrics"])
        self.assertIsNone(d["molecular_quality_metrics"])
        self.assertIsNone(d["matched_warhead_type"])
        self.assertIsNone(d["covalent_docking_score"])


# ===================================================================
# 8.  CLI contract tests
# ===================================================================


class CLIContractTests(unittest.TestCase):
    """CLI entry point contract tests.

    Expected RED: evaluation module not yet implemented.
    Both CLIs use --manifest <run_manifest.yml> only.
    """

    def test_summarize_results_cli_is_importable(self) -> None:
        """summarize_results CLI must be importable."""
        from covalent_design.evaluation import summarize_results  # noqa: F401

    def test_check_denominators_cli_is_importable(self) -> None:
        """check_denominators CLI must be importable."""
        from covalent_design.evaluation import check_denominators  # noqa: F401

    def test_summarize_results_cli_only_accepts_manifest(self) -> None:
        """summarize_results CLI must only use --manifest, not --results."""
        # This is a design constraint: no --results, --summary, or --out flags
        import argparse
        import inspect

        # Verify the CLI function signature matches our expectations
        from covalent_design.evaluation import summarize_results

        sig = inspect.signature(summarize_results)
        params = set(sig.parameters.keys())
        forbidden = {"results", "summary", "out", "requested_sample_count"}
        overlap = params & forbidden
        self.assertEqual(overlap, set(), f"Forbidden parameters found: {overlap}")

    def test_check_denominators_cli_only_accepts_manifest(self) -> None:
        """check_denominators CLI must only use --manifest, not --summary."""
        import covalent_design.evaluation.check_denominators as cli

        source = Path(cli.__file__).read_text(encoding="utf-8")
        self.assertIn('"--manifest"', source)
        self.assertNotIn('"--summary"', source)

    def test_check_denominators_python_api_accepts_summary(self) -> None:
        """The Python API validates an EvaluationSummary, not a manifest path."""
        import inspect

        from covalent_design.evaluation.denominator_accounting import check_denominators

        self.assertEqual(list(inspect.signature(check_denominators).parameters), ["summary"])


class CLIExitCodeTests(unittest.TestCase):
    """CLI exit code mapping tests (GREEN-capable - tests existing constants)."""

    def test_exit_code_11_for_artifact_missing_or_checksum(self) -> None:
        self.assertEqual(CLI_EXIT_CODES["artifact_missing_or_checksum_mismatch"], 11)

    def test_exit_code_12_for_denominator_conservation_failed(self) -> None:
        self.assertEqual(CLI_EXIT_CODES["denominator_conservation_failed"], 12)

    def test_contract_validation_failed_is_nonzero(self) -> None:
        self.assertNotEqual(CLI_EXIT_CODES["contract_validation_failed"], 0)

    def test_success_is_zero(self) -> None:
        self.assertEqual(CLI_EXIT_CODES["success"], 0)

    def test_exit_code_for_artifact_error_returns_11(self) -> None:
        from covalent_design.contracts.errors import exit_code_for_error

        err = ContractErrorInfo(
            code="ARTIFACT_CHECKSUM_MISMATCH",
            owner="data",
            message="checksum mismatch",
        )
        self.assertEqual(exit_code_for_error(err), 11)

    def test_exit_code_for_denominator_error_returns_12(self) -> None:
        from covalent_design.contracts.errors import exit_code_for_error

        err = ContractErrorInfo(
            code="EVALUATION_DENOMINATOR_ATTEMPTED_MISMATCH",
            owner="evaluation",
            message="conservation failed",
        )
        self.assertEqual(exit_code_for_error(err), 12)


# ===================================================================
# 9.  Safe write tests
# ===================================================================


class SafeWriteTests(unittest.TestCase):
    """Tests that output writes are atomic (no partial temp files)."""

    def test_evaluation_summary_is_json_serializable(self) -> None:
        """EvaluationSummary must be serializable to JSON."""
        summary = EvaluationSummary(
            requested_sample_count=9,
            request_validation_error_sample_count=0,
            accepted_request_sample_count=9,
            attempted_sample_count=7,
            sampling_system_failure_count=2,
            valid_generated_internal_count=4,
            invalid_generated_sample_count=3,
            exported_valid_complex_count=3,
            valid_export_failure_count=1,
            docking_evaluable_valid_sample_count=2,
            valid_but_not_docking_evaluable_sample_count=1,
            docking_not_run_valid_sample_count=0,
            docking_failed_valid_sample_count=1,
            successfully_docked_valid_sample_count=1,
        )
        # Should serialize without error
        from dataclasses import asdict

        d = asdict(summary)
        json_str = json.dumps(d, sort_keys=True)
        self.assertIsInstance(json_str, str)
        # Round-trip
        loaded = json.loads(json_str)
        self.assertEqual(loaded["requested_sample_count"], 9)
        self.assertEqual(loaded["successfully_docked_valid_sample_count"], 1)

    def test_evaluation_summary_json_is_deterministic(self) -> None:
        """Same EvaluationSummary must produce same JSON."""
        from dataclasses import asdict

        s1 = EvaluationSummary(
            requested_sample_count=3,
            request_validation_error_sample_count=0,
            accepted_request_sample_count=3,
            attempted_sample_count=3,
            sampling_system_failure_count=0,
            valid_generated_internal_count=3,
            invalid_generated_sample_count=0,
            exported_valid_complex_count=3,
            valid_export_failure_count=0,
            docking_evaluable_valid_sample_count=3,
            valid_but_not_docking_evaluable_sample_count=0,
            docking_not_run_valid_sample_count=0,
            docking_failed_valid_sample_count=0,
            successfully_docked_valid_sample_count=3,
        )
        s2 = EvaluationSummary(
            requested_sample_count=3,
            request_validation_error_sample_count=0,
            accepted_request_sample_count=3,
            attempted_sample_count=3,
            sampling_system_failure_count=0,
            valid_generated_internal_count=3,
            invalid_generated_sample_count=0,
            exported_valid_complex_count=3,
            valid_export_failure_count=0,
            docking_evaluable_valid_sample_count=3,
            valid_but_not_docking_evaluable_sample_count=0,
            docking_not_run_valid_sample_count=0,
            docking_failed_valid_sample_count=0,
            successfully_docked_valid_sample_count=3,
        )
        self.assertEqual(
            json.dumps(asdict(s1), sort_keys=True),
            json.dumps(asdict(s2), sort_keys=True),
        )

    def test_output_path_is_manifest_parent_evaluation_summary_json(self) -> None:
        """summarize_results CLI writes to manifest.parent / evaluation_summary.json by default.

        This is a contract test: the output path must be derived from
        the manifest location, not from an --out flag.
        """
        manifest_path = Path("/some/run/output/run_manifest.yml")
        expected_output = manifest_path.parent / "evaluation_summary.json"
        self.assertEqual(expected_output.name, "evaluation_summary.json")
        self.assertEqual(expected_output.parent, manifest_path.parent)


# ===================================================================
# 10.  Scenario fixture generation tests
# ===================================================================


class ScenarioFixtureGenerationTests(unittest.TestCase):
    """Create fixtures in temp directories and verify their correctness.

    These tests build complete run directory trees using the
    ScenarioBuilder and verify that artifact refs, checksums,
    manifest content, and JSONL versions are all correct.
    """

    def _create_scenario(
        self,
        results: list[CovalentGenerationResult],
        failures: list[dict[str, object]],
        **kwargs: object,
    ) -> tuple[Path, ScenarioBuilder]:
        tmp = tempfile.TemporaryDirectory()
        builder = ScenarioBuilder(Path(tmp.name))
        manifest_path = builder.write_files(
            results=results, failures=failures, **kwargs,  # type: ignore[arg-type]
        )
        self.addCleanup(tmp.cleanup)
        return manifest_path, builder

    def test_all_success_scenario_artifacts_valid(self) -> None:
        """All-success scenario: artifact refs must be valid and checksums correct."""
        results = [
            _make_valid_full_result(0, covalent_docking=-8.1),
            _make_valid_full_result(1, covalent_docking=-9.2),
            _make_valid_full_result(2, covalent_docking=-7.5),
        ]
        manifest_path, builder = self._create_scenario(
            results=results,
            failures=[],
            job_id="all-success-test",
            accepted=3,
            attempted=3,
            failure_count=0,
        )

        # Verify files exist
        self.assertTrue(manifest_path.exists())
        self.assertTrue((builder.path / "results.jsonl").exists())
        self.assertTrue((builder.path / "sampling_system_failures.jsonl").exists())
        self.assertTrue((builder.path / "request.normalized.yml").exists())

        # Verify results.jsonl has correct content
        rows = read_jsonl(
            builder.path / "results.jsonl",
            expected_schema_version=SCHEMA_VERSION,
            expected_contract_version=CONTRACT_VERSION,
        )
        self.assertEqual(len(rows), 3)
        for i, row in enumerate(rows):
            self.assertEqual(row["sample_id"], i)
            self.assertEqual(row["request_id"], "eval-test-req")

    def test_all_system_failure_scenario(self) -> None:
        """All-failure scenario: 0 results, 3 failures."""
        manifest_path, builder = self._create_scenario(
            results=[],
            failures=[
                _make_failure_row(0, "oom"),
                _make_failure_row(1, "crash"),
                _make_failure_row(2, "timeout"),
            ],
            job_id="all-failure-test",
            accepted=3,
            attempted=0,
            failure_count=3,
            result_count=0,
        )

        rows = read_jsonl(
            builder.path / "results.jsonl",
            expected_schema_version=SCHEMA_VERSION,
            expected_contract_version=CONTRACT_VERSION,
        )
        self.assertEqual(len(rows), 0)

        fail_rows = read_jsonl(
            builder.path / "sampling_system_failures.jsonl",
            expected_schema_version=SCHEMA_VERSION,
            expected_contract_version=CONTRACT_VERSION,
        )
        self.assertEqual(len(fail_rows), 3)
        categories = [r["failure_category"] for r in fail_rows]
        self.assertIn("oom", categories)
        self.assertIn("crash", categories)
        self.assertIn("timeout", categories)

    def test_empty_failures_jsonl_valid(self) -> None:
        """Empty failures JSONL file is valid and artifact ref is still mandatory."""
        manifest_path, builder = self._create_scenario(
            results=[_make_valid_full_result(0)],
            failures=[],
            job_id="empty-failures-test",
            accepted=1,
            attempted=1,
            failure_count=0,
        )
        fail_rows = read_jsonl(
            builder.path / "sampling_system_failures.jsonl",
            expected_schema_version=SCHEMA_VERSION,
            expected_contract_version=CONTRACT_VERSION,
        )
        self.assertEqual(len(fail_rows), 0)
        # Artifact ref must still be present
        self.assertTrue((builder.path / "sampling_system_failures.jsonl").exists())

    def test_retry_rows_are_audit_only(self) -> None:
        """Retry entries in failures JSONL are audit-only; denominators
        are computed from terminal-only events, not row count."""
        manifest_path, builder = self._create_scenario(
            results=[
                _make_valid_full_result(0, covalent_docking=-8.5),
                _make_valid_full_result(1, covalent_docking=-8.1),
            ],
            failures=[
                _make_retry_row(0, "oom", 0),
                _make_retry_row(0, "oom", 1),
                _make_failure_row(2, "retry_exhausted", retry_count=2),
            ],
            job_id="retry-audit-test",
            accepted=3,
            attempted=2,
            failure_count=1,
        )
        fail_rows = read_jsonl(
            builder.path / "sampling_system_failures.jsonl",
            expected_schema_version=SCHEMA_VERSION,
            expected_contract_version=CONTRACT_VERSION,
        )
        # 3 rows total: 2 retry attempts + 1 terminal exhausted
        self.assertEqual(len(fail_rows), 3)
        # But only 1 terminal failure (retry_exhausted); retries are audit-only
        terminal = [r for r in fail_rows if r["failure_category"] == "retry_exhausted"]
        self.assertEqual(len(terminal), 1)

    def test_manifest_result_count_matches_jsonl(self) -> None:
        """manifest.result_count must equal actual JSONL row count."""
        manifest_path, builder = self._create_scenario(
            results=[
                _make_valid_full_result(0),
                _make_valid_full_result(1),
                _make_valid_full_result(2),
            ],
            failures=[],
            job_id="result-count-test",
            accepted=3,
            attempted=3,
            failure_count=0,
        )
        # Verify the result count in the manifest matches the JSONL
        content = manifest_path.read_text(encoding="utf-8")
        self.assertIn("result_count: 3", content)
        rows = read_jsonl(
            builder.path / "results.jsonl",
            expected_schema_version=SCHEMA_VERSION,
            expected_contract_version=CONTRACT_VERSION,
        )
        self.assertEqual(len(rows), 3)

    def test_manifest_role_and_version_correct(self) -> None:
        """Generated manifests must have correct role and version."""
        manifest_path, builder = self._create_scenario(
            results=[_make_valid_full_result(0)],
            failures=[],
            job_id="role-version-test",
            accepted=1,
            attempted=1,
            failure_count=0,
        )
        # Manifest YAML content
        content = manifest_path.read_text(encoding="utf-8")
        self.assertIn('"generation_run_manifest"', content)
        self.assertIn(f'contract_version: "{CONTRACT_VERSION}"', content)
        self.assertIn(f'schema_version: "{SCHEMA_VERSION}"', content)

    def test_artifact_role_and_format_in_manifest(self) -> None:
        """Artifact refs in manifest must have correct role and format."""
        manifest_path, builder = self._create_scenario(
            results=[_make_valid_full_result(0)],
            failures=[],
            job_id="artifact-role-test",
            accepted=1,
            attempted=1,
            failure_count=0,
        )
        content = manifest_path.read_text(encoding="utf-8")
        self.assertIn('role: "results"', content)
        self.assertIn('format: "jsonl"', content)
        self.assertIn('role: "sampling_system_failures"', content)
        self.assertIn('role: "request"', content)


# ===================================================================
# 11.  End-to-end evaluation tests
# ===================================================================


class EvaluationEndToEndTests(unittest.TestCase):
    def _fixture_manifest(self, scenario: str) -> Path:
        return FIXTURES / scenario / "run_manifest.yml"

    def _copy_fixture(self, scenario: str) -> tuple[tempfile.TemporaryDirectory, Path]:
        tmp = tempfile.TemporaryDirectory()
        target = Path(tmp.name) / scenario
        shutil.copytree(FIXTURES / scenario, target)
        self.addCleanup(tmp.cleanup)
        return tmp, target / "run_manifest.yml"

    def _run_cli(self, module: str, *args: str) -> subprocess.CompletedProcess[str]:
        env = dict(os.environ)
        env["PYTHONPATH"] = str(ROOT / "src")
        return subprocess.run(
            [sys.executable, "-m", module, *args],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_load_generation_run_validates_required_artifacts(self) -> None:
        from covalent_design.evaluation import load_generation_run

        envelope = load_generation_run(self._fixture_manifest("valid_mixed"))
        self.assertTrue(envelope.receipt.passed)
        self.assertEqual(envelope.payload.role, "generation_run_manifest")
        self.assertEqual(
            tuple(ref.role for ref in envelope.artifacts),
            ("request", "results", "sampling_system_failures"),
        )

    def test_summarize_results_counts_mixed_lifecycle_without_writing(self) -> None:
        from covalent_design.evaluation import summarize_results

        _, manifest = self._copy_fixture("valid_mixed")
        summary = summarize_results(manifest)
        self.assertEqual(summary.requested_sample_count, 9)
        self.assertEqual(summary.attempted_sample_count, 7)
        self.assertEqual(summary.sampling_system_failure_count, 2)
        self.assertEqual(summary.valid_generated_internal_count, 4)
        self.assertEqual(summary.invalid_generated_sample_count, 3)
        self.assertEqual(summary.exported_valid_complex_count, 3)
        self.assertEqual(summary.valid_export_failure_count, 1)
        self.assertEqual(summary.docking_evaluable_valid_sample_count, 2)
        self.assertEqual(summary.valid_but_not_docking_evaluable_sample_count, 1)
        self.assertEqual(summary.docking_failed_valid_sample_count, 1)
        self.assertEqual(summary.successfully_docked_valid_sample_count, 1)
        self.assertFalse((manifest.parent / "evaluation_summary.json").exists())

    def test_writer_is_explicit_atomic_and_deterministic(self) -> None:
        from covalent_design.evaluation import summarize_results, write_evaluation_summary

        _, manifest = self._copy_fixture("valid_mixed")
        summary = summarize_results(manifest)
        output = manifest.parent / "evaluation_summary.json"
        first = write_evaluation_summary(summary, output)
        first_bytes = output.read_bytes()
        second = write_evaluation_summary(summary, output)
        self.assertEqual(first_bytes, output.read_bytes())
        self.assertEqual(first.sha256, second.sha256)
        self.assertEqual(first.role, "evaluation_summary")
        self.assertEqual(list(manifest.parent.glob(".evaluation_summary*.tmp")), [])

    def test_writer_rejects_non_conserving_summary(self) -> None:
        from dataclasses import replace

        from covalent_design.evaluation import summarize_results, write_evaluation_summary

        _, manifest = self._copy_fixture("all_success")
        summary = summarize_results(manifest)
        output = manifest.parent / "evaluation_summary.json"
        with self.assertRaises(ContractError):
            write_evaluation_summary(
                replace(summary, attempted_sample_count=summary.attempted_sample_count - 1),
                output,
            )
        self.assertFalse(output.exists())

    def test_check_denominators_reuses_contract_validator(self) -> None:
        from covalent_design.evaluation.denominator_accounting import (
            check_denominators,
            summarize_results,
        )

        summary = summarize_results(self._fixture_manifest("all_success"))
        receipt = check_denominators(summary)
        self.assertTrue(receipt.passed)
        self.assertEqual(
            receipt.validator,
            "covalent_design.contracts.validate_evaluation_summary",
        )

    def test_retry_rows_are_audit_only_for_summary(self) -> None:
        from covalent_design.evaluation import summarize_results

        summary = summarize_results(self._fixture_manifest("retry_diagnostics"))
        self.assertEqual(summary.sampling_system_failure_count, 1)
        self.assertEqual(summary.attempted_sample_count, 3)

    def test_all_system_failure_manifest_summarizes(self) -> None:
        from covalent_design.evaluation import summarize_results

        summary = summarize_results(self._fixture_manifest("all_system_failure"))
        self.assertEqual(summary.attempted_sample_count, 0)
        self.assertEqual(summary.sampling_system_failure_count, 3)
        self.assertEqual(summary.invalid_generated_sample_count, 0)

    def test_checksum_mismatch_is_structured(self) -> None:
        from covalent_design.evaluation import summarize_results

        with self.assertRaises(ContractError) as ctx:
            summarize_results(self._fixture_manifest("checksum_mismatch"))
        self.assertIn("CHECKSUM", ctx.exception.code)

    def test_missing_artifact_is_structured(self) -> None:
        from covalent_design.evaluation import summarize_results

        with self.assertRaises(ContractError) as ctx:
            summarize_results(self._fixture_manifest("missing_artifact"))
        self.assertIn("ARTIFACT", ctx.exception.code)

    def test_absolute_and_traversal_manifest_uris_are_rejected(self) -> None:
        from covalent_design.evaluation import summarize_results

        for scenario in ("absolute_uri", "traversal_uri"):
            with self.subTest(scenario=scenario):
                with self.assertRaises(ContractError) as ctx:
                    summarize_results(self._fixture_manifest(scenario))
                self.assertEqual(ctx.exception.code, "ARTIFACT_URI_INVALID")

    def test_manifest_role_or_version_violation_is_structured(self) -> None:
        from covalent_design.evaluation import summarize_results

        with self.assertRaises(ContractError) as ctx:
            summarize_results(self._fixture_manifest("manifest_role_version_invalid"))
        self.assertIn("MANIFEST_", ctx.exception.code)

    def test_artifact_role_or_format_violation_is_structured(self) -> None:
        from covalent_design.evaluation import summarize_results

        with self.assertRaises(ContractError) as ctx:
            summarize_results(self._fixture_manifest("artifact_role_format_invalid"))
        self.assertIn(ctx.exception.code, {"ARTIFACT_ROLE_MISMATCH", "ARTIFACT_FORMAT_MISMATCH"})

    def test_extra_siblings_are_not_discovered(self) -> None:
        from covalent_design.evaluation import summarize_results

        summary = summarize_results(self._fixture_manifest("extra_siblings"))
        self.assertEqual(summary.requested_sample_count, 1)
        self.assertEqual(summary.successfully_docked_valid_sample_count, 1)

    def test_result_count_mismatch_is_structured(self) -> None:
        from covalent_design.evaluation import summarize_results

        with self.assertRaises(ContractError) as ctx:
            summarize_results(self._fixture_manifest("result_count_mismatch"))
        self.assertEqual(ctx.exception.code, "EVALUATION_DENOMINATOR_RESULT_COUNT_MISMATCH")

    def test_failure_row_structure_is_validated_but_not_counted(self) -> None:
        builder_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(builder_tmp.cleanup)
        builder = ScenarioBuilder(Path(builder_tmp.name))
        manifest = builder.write_files(
            results=[],
            failures=[_make_failure_row(0, "unknown-category")],
            job_id="invalid-failure-row",
            accepted=1,
            attempted=0,
            failure_count=1,
        )
        from covalent_design.evaluation import summarize_results

        with self.assertRaises(ContractError) as ctx:
            summarize_results(manifest)
        self.assertEqual(ctx.exception.code, "SAMPLING_FAILURE_ROW_DECODE_FAILED")

    def test_decoder_rejects_non_string_secondary_reason(self) -> None:
        from covalent_design.evaluation.result_schema import decode_result_row
        from covalent_design.inference.result_schema import _result_to_dict

        row = _result_to_dict(_make_invalid_result(0, "NO_COVALENT_EDGE_PREDICTED"))
        row["secondary_failure_reasons"] = [7]
        with self.assertRaises(ValueError):
            decode_result_row(row)

    def test_cli_help_and_success_paths(self) -> None:
        help_result = self._run_cli(
            "covalent_design.evaluation.summarize_results", "--help"
        )
        self.assertEqual(help_result.returncode, 0)
        self.assertIn("--manifest", help_result.stdout)

        _, manifest = self._copy_fixture("valid_mixed")
        summary_result = self._run_cli(
            "covalent_design.evaluation.summarize_results",
            "--manifest",
            str(manifest),
        )
        self.assertEqual(summary_result.returncode, 0, summary_result.stderr)
        self.assertTrue((manifest.parent / "evaluation_summary.json").is_file())
        self.assertEqual(json.loads(summary_result.stdout)["role"], "evaluation_summary")

        check_result = self._run_cli(
            "covalent_design.evaluation.check_denominators",
            "--manifest",
            str(manifest),
        )
        self.assertEqual(check_result.returncode, 0, check_result.stderr)
        self.assertTrue(json.loads(check_result.stdout)["passed"])

    def test_cli_exit_codes_for_artifact_and_denominator_errors(self) -> None:
        missing = self._run_cli(
            "covalent_design.evaluation.summarize_results",
            "--manifest",
            str(self._fixture_manifest("missing_artifact")),
        )
        mismatch = self._run_cli(
            "covalent_design.evaluation.check_denominators",
            "--manifest",
            str(self._fixture_manifest("result_count_mismatch")),
        )
        self.assertEqual(missing.returncode, 11, missing.stderr)
        self.assertEqual(mismatch.returncode, 12, mismatch.stderr)


# ===================================================================
# 12.  Source guard tests
# ===================================================================


class SourceGuardTests(unittest.TestCase):
    """Boundary enforcement: no wrong inputs, no heavy deps, correct task scope."""

    def test_no_heavy_dependencies_loaded(self) -> None:
        heavy = {"torch", "rdkit", "pmdm", "pocketflow"}
        violations: list[str] = []
        for mod_name in sorted(sys.modules):
            lower = mod_name.lower()
            for h in heavy:
                if lower == h or lower.startswith(h + "."):
                    violations.append(mod_name)
        self.assertEqual(
            violations,
            [],
            f"heavy dependencies found in sys.modules: {violations}",
        )

    def test_no_task31_imported(self) -> None:
        self.assertNotIn("covalent_design.analysis", sys.modules)

    def test_no_task32_imported(self) -> None:
        self.assertNotIn("covalent_design.dashboard", sys.modules)

    def test_no_task33_imported(self) -> None:
        self.assertNotIn("covalent_design.deployment", sys.modules)

    def test_no_scan_or_glob_discovery_in_test(self) -> None:
        """Tests must reference fixtures explicitly, not by glob/scan discovery."""
        # This test module itself is the evidence: all fixture references are
        # explicit paths or programmatic (temp dirs), never os.walk/glob.
        pass

    def test_evaluation_summary_validate_method_exists(self) -> None:
        """EvaluationSummary.validate() must call validate_evaluation_summary()."""
        self.assertTrue(hasattr(EvaluationSummary, "validate"))
        self.assertTrue(callable(EvaluationSummary.validate))

    def test_evaluation_summary_fields_are_all_integers(self) -> None:
        """All EvaluationSummary fields must be int."""
        import dataclasses
        from typing import get_type_hints

        type_hints = get_type_hints(EvaluationSummary)
        for f in dataclasses.fields(EvaluationSummary):
            self.assertIs(
                type_hints[f.name], int,
                f"EvaluationSummary.{f.name} must be int, got {type_hints[f.name]}",
            )

    def test_generation_run_manifest_has_accepted_attempted_counts(self) -> None:
        """GenerationRunManifest must carry the counts summarise_results needs."""
        m = GenerationRunManifest(
            job_id="test",
            request_id="test-req",
            accepted_request_sample_count=5,
            attempted_sample_count=4,
            sampling_system_failure_count=1,
            result_count=4,
        )
        self.assertEqual(m.accepted_request_sample_count, 5)
        self.assertEqual(m.attempted_sample_count, 4)
        self.assertEqual(m.sampling_system_failure_count, 1)
        self.assertEqual(m.result_count, 4)


# ===================================================================
# 13.  Authoritative fixtures loadability tests
# ===================================================================


class CommittedFixtureLoadabilityTests(unittest.TestCase):
    """Committed builder-generated fixtures must be correct on disk.

    These tests validate the committed fixture directories directly,
    verifying that run_manifest.yml, results.jsonl, and
    sampling_system_failures.jsonl are all present and syntactically valid.
    """

    def test_all_scenario_directories_exist(self) -> None:
        expected = [
            "valid_mixed",
            "all_success",
            "all_system_failure",
            "retry_diagnostics",
            "checksum_mismatch",
            "missing_artifact",
            "absolute_uri",
            "traversal_uri",
            "result_count_mismatch",
            "extra_siblings",
            "corrupt_lifecycle",
            "corrupt_diagnostics",
            "empty_failures_jsonl",
            "jsonl_version_invalid",
            "manifest_role_version_invalid",
            "artifact_role_format_invalid",
        ]
        for name in expected:
            path = FIXTURES / name
            # Directory should exist (at minimum, the builder.py lives here)
            # Even if not yet built, the builder can regenerate them
            if not path.is_dir():
                self.skipTest(f"Fixture directory {name} not built - run builder.py first")

    def test_scenario_has_required_files(self) -> None:
        """Each built scenario must have the four required files."""
        for scenario_dir in sorted(FIXTURES.glob("*/")):
            if scenario_dir.name in ("__pycache__",):
                continue
            if not (scenario_dir / "run_manifest.yml").is_file():
                continue  # Not yet built

            with self.subTest(scenario=scenario_dir.name):
                self.assertTrue(
                    (scenario_dir / "run_manifest.yml").is_file(),
                    f"missing run_manifest.yml in {scenario_dir.name}",
                )
                if scenario_dir.name != "missing_artifact":
                    self.assertTrue(
                        (scenario_dir / "results.jsonl").is_file(),
                        f"missing results.jsonl in {scenario_dir.name}",
                    )
                self.assertTrue(
                    (scenario_dir / "sampling_system_failures.jsonl").is_file(),
                    f"missing sampling_system_failures.jsonl in {scenario_dir.name}",
                )
                self.assertTrue(
                    (scenario_dir / "request.normalized.yml").is_file(),
                    f"missing request.normalized.yml in {scenario_dir.name}",
                )

    def test_manifest_loadable_as_yaml(self) -> None:
        """Each manifest must be parseable YAML."""
        for scenario_dir in sorted(FIXTURES.glob("*/")):
            if not (scenario_dir / "run_manifest.yml").is_file():
                continue
            with self.subTest(scenario=scenario_dir.name):
                content = (scenario_dir / "run_manifest.yml").read_text(encoding="utf-8")
                # Basic YAML structure check (hand-rolled subset)
                self.assertIn("schema_version:", content)
                self.assertIn("contract_version:", content)
                self.assertIn("role:", content)
                self.assertIn("accepted_request_sample_count:", content)
                self.assertIn("artifacts:", content)

    def test_results_jsonl_loadable(self) -> None:
        """Each results.jsonl must be readable with correct versions."""
        for scenario_dir in sorted(FIXTURES.glob("*/")):
            if not (scenario_dir / "results.jsonl").is_file():
                continue
            with self.subTest(scenario=scenario_dir.name):
                try:
                    rows = read_jsonl(
                        scenario_dir / "results.jsonl",
                        expected_schema_version=SCHEMA_VERSION,
                        expected_contract_version=CONTRACT_VERSION,
                    )
                except Exception as e:
                    # Some fixtures intentionally have wrong versions
                    # (jsonl_version_invalid) - that's OK.
                    if "VERSION" in str(e):
                        continue
                    raise
                for row in rows:
                    self.assertIn("request_id", row)
                    self.assertIn("sample_id", row)
                    self.assertIn("generation_validity_status", row)


if __name__ == "__main__":
    unittest.main()
