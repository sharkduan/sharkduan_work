from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from typing import Optional

from covalent_design.contracts.errors import ContractErrorInfo
from covalent_design.contracts.types import (
    CONTRACT_VERSION,
    EdgeDenominators,
    EvaluationSummary,
    ValidationReceipt,
)


EDGE_DENOMINATOR_VALIDATOR = "covalent_design.contracts.validate_edge_denominators"
EVALUATION_SUMMARY_VALIDATOR = "covalent_design.contracts.validate_evaluation_summary"


def validate_edge_denominators(denominators: EdgeDenominators) -> ValidationReceipt:
    errors: list[ContractErrorInfo] = []
    values = asdict(denominators)

    for name, value in values.items():
        if value < 0:
            errors.append(
                _error(
                    "EDGE_DENOMINATOR_NEGATIVE",
                    f"{name} must be non-negative",
                    name,
                    {"value": value},
                )
            )
            return _receipt(EDGE_DENOMINATOR_VALIDATOR, values, errors)

    if denominators.natural_candidate_count + denominators.forced_positive_count != denominators.candidate_count:
        errors.append(
            _error(
                "EDGE_DENOMINATOR_CANDIDATE_COUNT_MISMATCH",
                "candidate_count must equal natural_candidate_count + forced_positive_count",
                "candidate_count",
            )
        )
    if denominators.forced_positive_count > denominators.candidate_count:
        errors.append(
            _error(
                "EDGE_DENOMINATOR_FORCED_POSITIVE_EXCEEDS_CANDIDATES",
                "forced_positive_count cannot exceed candidate_count",
                "forced_positive_count",
            )
        )
    if denominators.eligible_edge_count + denominators.masked_candidate_count > denominators.candidate_count:
        errors.append(
            _error(
                "EDGE_DENOMINATOR_ELIGIBLE_MASKED_EXCEEDS_CANDIDATES",
                "eligible_edge_count + masked_candidate_count cannot exceed candidate_count",
                "eligible_edge_count",
            )
        )
    if denominators.edge_loss_denominator > denominators.eligible_edge_count:
        errors.append(
            _error(
                "EDGE_DENOMINATOR_EDGE_LOSS_EXCEEDS_ELIGIBLE",
                "edge_loss_denominator cannot exceed eligible_edge_count",
                "edge_loss_denominator",
            )
        )
    if denominators.bond_type_loss_denominator > denominators.eligible_edge_count:
        errors.append(
            _error(
                "EDGE_DENOMINATOR_BOND_TYPE_EXCEEDS_ELIGIBLE",
                "bond_type_loss_denominator cannot exceed eligible_edge_count",
                "bond_type_loss_denominator",
            )
        )
    if denominators.geometry_loss_denominator > denominators.eligible_edge_count:
        errors.append(
            _error(
                "EDGE_DENOMINATOR_GEOMETRY_EXCEEDS_ELIGIBLE",
                "geometry_loss_denominator cannot exceed eligible_edge_count",
                "geometry_loss_denominator",
            )
        )
    if denominators.message_passing_candidate_count > denominators.natural_candidate_count:
        errors.append(
            _error(
                "EDGE_DENOMINATOR_FORCED_POSITIVE_MESSAGE_PASSING",
                "message_passing_candidate_count cannot include force-included positives in v1",
                "message_passing_candidate_count",
            )
        )
    if denominators.gate_evaluated_count > denominators.candidate_count:
        errors.append(
            _error(
                "EDGE_DENOMINATOR_GATE_EXCEEDS_CANDIDATES",
                "gate_evaluated_count cannot exceed candidate_count",
                "gate_evaluated_count",
            )
        )

    return _receipt(EDGE_DENOMINATOR_VALIDATOR, values, errors)


def validate_evaluation_summary(summary: EvaluationSummary) -> ValidationReceipt:
    errors: list[ContractErrorInfo] = []
    values = asdict(summary)

    for name, value in values.items():
        if value < 0:
            errors.append(
                _error(
                    "EVALUATION_DENOMINATOR_NEGATIVE",
                    f"{name} must be non-negative",
                    name,
                    {"value": value},
                )
            )
            return _receipt(EVALUATION_SUMMARY_VALIDATOR, values, errors)

    equations = (
        (
            "EVALUATION_DENOMINATOR_REQUESTED_MISMATCH",
            summary.requested_sample_count,
            summary.request_validation_error_sample_count + summary.accepted_request_sample_count,
            "requested_sample_count",
        ),
        (
            "EVALUATION_DENOMINATOR_ACCEPTED_REQUEST_MISMATCH",
            summary.accepted_request_sample_count,
            summary.attempted_sample_count + summary.sampling_system_failure_count,
            "accepted_request_sample_count",
        ),
        (
            "EVALUATION_DENOMINATOR_ATTEMPTED_MISMATCH",
            summary.attempted_sample_count,
            summary.valid_generated_internal_count + summary.invalid_generated_sample_count,
            "attempted_sample_count",
        ),
        (
            "EVALUATION_DENOMINATOR_VALID_INTERNAL_MISMATCH",
            summary.valid_generated_internal_count,
            summary.exported_valid_complex_count + summary.valid_export_failure_count,
            "valid_generated_internal_count",
        ),
        (
            "EVALUATION_DENOMINATOR_EXPORTED_VALID_MISMATCH",
            summary.exported_valid_complex_count,
            summary.docking_evaluable_valid_sample_count + summary.valid_but_not_docking_evaluable_sample_count,
            "exported_valid_complex_count",
        ),
        (
            "EVALUATION_DENOMINATOR_DOCKING_EVALUABLE_MISMATCH",
            summary.docking_evaluable_valid_sample_count,
            summary.successfully_docked_valid_sample_count
            + summary.docking_failed_valid_sample_count
            + summary.docking_not_run_valid_sample_count,
            "docking_evaluable_valid_sample_count",
        ),
    )

    for code, left, right, location in equations:
        if left != right:
            errors.append(
                _error(
                    code,
                    f"{location} conservation failed: {left} != {right}",
                    location,
                    {"left": left, "right": right},
                )
            )
            break

    return _receipt(EVALUATION_SUMMARY_VALIDATOR, values, errors)


def _error(
    code: str,
    message: str,
    location: str,
    details: Optional[dict[str, object]] = None,
) -> ContractErrorInfo:
    return ContractErrorInfo(
        code=code,
        owner="evaluation",
        message=message,
        location=location,
        details=details or {},
    )


def _receipt(
    validator: str,
    payload: dict[str, object],
    errors: list[ContractErrorInfo],
) -> ValidationReceipt:
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
    return ValidationReceipt(
        validator=validator,
        contract_version=CONTRACT_VERSION,
        input_sha256=digest,
        passed=not errors,
        errors=tuple(errors),
    )
