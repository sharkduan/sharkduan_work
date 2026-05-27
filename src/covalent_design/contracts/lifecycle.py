from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from typing import Optional

from covalent_design.contracts.errors import ContractErrorInfo
from covalent_design.contracts.types import (
    CONTRACT_VERSION,
    ComplexExportStatus,
    CovalentGenerationResult,
    DockingEligibilityStatus,
    DockingRunStatus,
    EdgeValidityCheckName,
    EdgeValidityCheckStatus,
    FAILURE_REASON_CODES,
    GenerationValidityStatus,
    LigandStatus,
    ValidationReceipt,
)


LIFECYCLE_VALIDATOR = "covalent_design.contracts.validate_lifecycle"
GENERATION_RESULT_VALIDATOR = "covalent_design.contracts.validate_generation_result"


def validate_lifecycle(result: CovalentGenerationResult) -> ValidationReceipt:
    errors: list[ContractErrorInfo] = []

    _validate_allowed_values(result, errors)
    if not errors:
        _validate_lifecycle_constraints(result, errors)
    if not errors:
        _validate_edge_checks(result, errors)

    return _receipt(LIFECYCLE_VALIDATOR, result, errors)


def validate_generation_result(result: CovalentGenerationResult) -> ValidationReceipt:
    """Validate expanded generation-result diagnostics in addition to lifecycle state.

    ``validate_lifecycle`` intentionally remains the narrow status-transition
    validator used by legacy fixtures. This validator is the Task 28+ boundary:
    it checks the expanded diagnostic and score fields without making every
    caller fill those fields just to exercise lifecycle logic.
    """

    errors: list[ContractErrorInfo] = []

    _validate_allowed_values(result, errors)
    if not errors:
        _validate_lifecycle_constraints(result, errors)
    if not errors:
        _validate_edge_checks(result, errors)
    if not errors:
        _validate_generation_diagnostics(result, errors)

    return _receipt(GENERATION_RESULT_VALIDATOR, result, errors)


def _validate_allowed_values(
    result: CovalentGenerationResult,
    errors: list[ContractErrorInfo],
) -> None:
    checks = (
        (
            result.generation_validity_status,
            GenerationValidityStatus,
            "generation_validity_status",
            "LIFECYCLE_GENERATION_VALIDITY_STATUS_INVALID",
        ),
        (
            result.complex_export_status,
            ComplexExportStatus,
            "complex_export_status",
            "LIFECYCLE_COMPLEX_EXPORT_STATUS_INVALID",
        ),
        (
            result.docking_eligibility_status,
            DockingEligibilityStatus,
            "docking_eligibility_status",
            "LIFECYCLE_DOCKING_ELIGIBILITY_STATUS_INVALID",
        ),
        (
            result.docking_run_status,
            DockingRunStatus,
            "docking_run_status",
            "LIFECYCLE_DOCKING_RUN_STATUS_INVALID",
        ),
        (
            result.generated_ligand_status,
            LigandStatus,
            "generated_ligand_status",
            "GENERATION_RESULT_LIGAND_STATUS_INVALID",
        ),
    )
    for value, allowed, location, code in checks:
        if value not in allowed:
            errors.append(_error(code, f"Unsupported {location}: {value}", location))
            return

    _validate_failure_reason(result.primary_failure_reason, "primary_failure_reason", errors)
    for index, reason in enumerate(result.secondary_failure_reasons):
        _validate_failure_reason(reason, f"secondary_failure_reasons[{index}]", errors)
        if errors:
            return


def _validate_lifecycle_constraints(
    result: CovalentGenerationResult,
    errors: list[ContractErrorInfo],
) -> None:
    if result.generation_validity_status == "invalid":
        if result.complex_export_status != "not_applicable":
            errors.append(
                _error(
                    "LIFECYCLE_INVALID_EXPORT_STATUS",
                    "Invalid generated samples cannot be exported",
                    "complex_export_status",
                )
            )
            return
        if result.docking_eligibility_status != "not_applicable":
            errors.append(
                _error(
                    "LIFECYCLE_INVALID_DOCKING_ELIGIBILITY_STATUS",
                    "Invalid generated samples cannot be docking eligible",
                    "docking_eligibility_status",
                )
            )
            return
        if result.docking_run_status != "not_applicable":
            errors.append(
                _error(
                    "LIFECYCLE_INVALID_DOCKING_RUN_STATUS",
                    "Invalid generated samples cannot have docking run status",
                    "docking_run_status",
                )
            )
            return
        if result.primary_failure_reason is None:
            errors.append(
                _error(
                    "LIFECYCLE_INVALID_MISSING_FAILURE_REASON",
                    "Invalid generated samples require a primary failure reason",
                    "primary_failure_reason",
                )
            )
        return

    if result.complex_export_status == "not_applicable":
        errors.append(
            _error(
                "LIFECYCLE_VALID_EXPORT_STATUS_NOT_APPLICABLE",
                "Valid generated samples must either export or record export failure",
                "complex_export_status",
            )
        )
        return

    if result.complex_export_status == "failed":
        if result.docking_eligibility_status != "not_applicable" or result.docking_run_status != "not_applicable":
            errors.append(
                _error(
                    "LIFECYCLE_EXPORT_FAILURE_DOCKING_STATUS_INVALID",
                    "Export failures cannot continue to docking eligibility or run states",
                    "docking_eligibility_status",
                )
            )
            return
        if result.primary_failure_reason != "COMPLEX_EXPORT_FAILED":
            errors.append(
                _error(
                    "LIFECYCLE_EXPORT_FAILURE_REASON_MISMATCH",
                    "complex_export_status=failed requires primary_failure_reason=COMPLEX_EXPORT_FAILED",
                    "primary_failure_reason",
                )
            )
        return

    if "complex_mmcif" not in result.artifacts:
        errors.append(
            _error(
                "LIFECYCLE_EXPORTED_COMPLEX_ARTIFACT_MISSING",
                "complex_export_status=exported requires a complex_mmcif artifact",
                "artifacts.complex_mmcif",
            )
        )
        return

    if result.docking_eligibility_status not in ("eligible", "not_evaluable"):
        errors.append(
            _error(
                "LIFECYCLE_EXPORTED_DOCKING_ELIGIBILITY_INVALID",
                "Exported valid samples must be eligible or not_evaluable for docking",
                "docking_eligibility_status",
            )
        )
        return

    if result.docking_eligibility_status == "not_evaluable":
        if result.docking_run_status != "not_applicable":
            errors.append(
                _error(
                    "LIFECYCLE_DOCKING_NOT_EVALUABLE_RUN_STATUS_INVALID",
                    "Docking not-evaluable samples cannot have a docking run status",
                    "docking_run_status",
                )
            )
            return
        if result.primary_failure_reason != "DOCKING_NOT_EVALUABLE":
            errors.append(
                _error(
                    "LIFECYCLE_DOCKING_NOT_EVALUABLE_REASON_MISMATCH",
                    "docking_eligibility_status=not_evaluable requires primary_failure_reason=DOCKING_NOT_EVALUABLE",
                    "primary_failure_reason",
                )
            )
        return

    if result.docking_run_status == "not_applicable":
        errors.append(
            _error(
                "LIFECYCLE_ELIGIBLE_DOCKING_RUN_STATUS_INVALID",
                "Docking-eligible samples require not_run, succeeded, or failed",
                "docking_run_status",
            )
        )
        return
    if result.docking_run_status == "failed" and result.primary_failure_reason != "DOCKING_RUN_FAILED":
        errors.append(
            _error(
                "LIFECYCLE_DOCKING_FAILURE_REASON_MISMATCH",
                "docking_run_status=failed requires primary_failure_reason=DOCKING_RUN_FAILED",
                "primary_failure_reason",
            )
        )
        return
    if result.docking_run_status in ("succeeded", "not_run") and result.primary_failure_reason is not None:
        errors.append(
            _error(
                "LIFECYCLE_SUCCESS_OR_NOT_RUN_HAS_FAILURE_REASON",
                "Successful or intentionally not-run docking must not have a primary failure reason",
                "primary_failure_reason",
            )
        )


def _validate_generation_diagnostics(
    result: CovalentGenerationResult,
    errors: list[ContractErrorInfo],
) -> None:
    if result.generation_validity_status == "valid":
        missing_fields: list[str] = []
        if result.generated_ligand_status != "present":
            missing_fields.append("generated_ligand_status")
        if result.predicted_ligand_attachment_atom is None:
            missing_fields.append("predicted_ligand_attachment_atom")
        if result.predicted_covalent_edge is None:
            missing_fields.append("predicted_covalent_edge")
        if result.covalent_edge_score is None:
            missing_fields.append("covalent_edge_score")
        if result.geometry_metrics is None:
            missing_fields.append("geometry_metrics")
        if result.molecular_quality_metrics is None:
            missing_fields.append("molecular_quality_metrics")
        if result.matched_warhead_type is None:
            missing_fields.append("matched_warhead_type")
        if missing_fields:
            errors.append(
                _error(
                    "GENERATION_RESULT_VALID_DIAGNOSTICS_MISSING",
                    "Valid generated samples require ligand, edge, geometry, quality, and matched-warhead diagnostics",
                    "diagnostics",
                    details={"missing_fields": tuple(missing_fields)},
                )
            )
            return

    if result.docking_run_status == "succeeded":
        if result.covalent_docking_score is None:
            errors.append(
                _error(
                    "GENERATION_RESULT_COVALENT_DOCKING_SCORE_MISSING",
                    "docking_run_status=succeeded requires covalent_docking_score",
                    "covalent_docking_score",
                )
            )
        return

    if result.covalent_docking_score is not None:
        errors.append(
            _error(
                "GENERATION_RESULT_COVALENT_DOCKING_SCORE_NOT_ALLOWED",
                "covalent_docking_score is only allowed when docking_run_status=succeeded",
                "covalent_docking_score",
            )
        )


def _validate_edge_checks(
    result: CovalentGenerationResult,
    errors: list[ContractErrorInfo],
) -> None:
    for index, check in enumerate(result.edge_validity_checks):
        if check.check_name not in EdgeValidityCheckName:
            errors.append(
                _error(
                    "EDGE_VALIDITY_CHECK_NAME_INVALID",
                    f"Unsupported edge validity check: {check.check_name}",
                    f"edge_validity_checks[{index}].check_name",
                )
            )
            return
        if check.status not in EdgeValidityCheckStatus:
            errors.append(
                _error(
                    "EDGE_VALIDITY_CHECK_STATUS_INVALID",
                    f"Unsupported edge validity check status: {check.status}",
                    f"edge_validity_checks[{index}].status",
                )
            )
            return
        _validate_failure_reason(check.failure_code, f"edge_validity_checks[{index}].failure_code", errors)
        if errors:
            return


def _validate_failure_reason(
    reason: Optional[str],
    location: str,
    errors: list[ContractErrorInfo],
) -> None:
    if reason is not None and reason not in FAILURE_REASON_CODES:
        errors.append(
            _error(
                "FAILURE_REASON_CODE_INVALID",
                f"Unsupported failure reason: {reason}",
                location,
            )
        )


def _receipt(
    validator: str,
    result: CovalentGenerationResult,
    errors: list[ContractErrorInfo],
) -> ValidationReceipt:
    payload = asdict(result)
    digest = hashlib.sha256(
        json.dumps(payload, default=str, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return ValidationReceipt(
        validator=validator,
        contract_version=CONTRACT_VERSION,
        input_sha256=digest,
        passed=not errors,
        errors=tuple(errors),
    )


def _error(
    code: str,
    message: str,
    location: str,
    *,
    details: Optional[dict[str, object]] = None,
) -> ContractErrorInfo:
    return ContractErrorInfo(
        code=code,
        owner="evaluation",
        message=message,
        location=location,
        details=details or {},
    )
