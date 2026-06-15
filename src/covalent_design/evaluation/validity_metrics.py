"""Validation and lifecycle-status counting for evaluation results.

Put here: validate_results_before_aggregation, summarize_lifecycle_statuses.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict

from covalent_design.contracts.errors import ContractError
from covalent_design.contracts.errors import ContractErrorInfo
from covalent_design.contracts.lifecycle import validate_generation_result
from covalent_design.contracts.types import (
    CONTRACT_VERSION,
    CovalentGenerationResult,
    ValidationReceipt,
)

_VALIDATOR = "covalent_design.evaluation.validate_results_before_aggregation"


def validate_results_before_aggregation(
    results: list[CovalentGenerationResult],
) -> ValidationReceipt:
    """Validate every result row before any lifecycle aggregation.

    Any corrupt lifecycle row fails the whole report.  No survivor
    aggregation, no partial output.
    """
    errors: list[ContractErrorInfo] = []

    for i, r in enumerate(results):
        receipt = validate_generation_result(r)
        if not receipt.passed:
            for err in receipt.errors:
                errors.append(
                    ContractErrorInfo(
                        code=err.code,
                        owner=err.owner,
                        message=err.message,
                        location=f"results[{i}].{err.location}"
                        if err.location
                        else f"results[{i}]",
                        details=err.details,
                    )
                )

    payload = [asdict(r) for r in results]
    digest = hashlib.sha256(
        json.dumps(payload, default=str, sort_keys=True).encode("utf-8")
    ).hexdigest()

    return ValidationReceipt(
        validator=_VALIDATOR,
        contract_version=CONTRACT_VERSION,
        input_sha256=digest,
        passed=not errors,
        errors=tuple(errors),
    )


def summarize_lifecycle_statuses(
    results: list[CovalentGenerationResult],
) -> dict[str, int]:
    """Validate and count all lifecycle statuses across a result list."""
    receipt = validate_results_before_aggregation(results)
    if not receipt.passed:
        err = receipt.errors[0]
        raise ContractError(
            code=err.code,
            owner=err.owner,
            message=err.message,
            location=err.location,
            details=err.details,
        )

    statuses: dict[str, int] = {
        "valid_generated": 0,
        "invalid_generated": 0,
        "complex_export_not_applicable": 0,
        "complex_export_exported": 0,
        "complex_export_failed": 0,
        "docking_eligibility_not_applicable": 0,
        "docking_eligibility_eligible": 0,
        "docking_eligibility_not_evaluable": 0,
        "docking_run_not_applicable": 0,
        "docking_run_not_run": 0,
        "docking_run_succeeded": 0,
        "docking_run_failed": 0,
    }
    for r in results:
        status = r.generation_validity_status
        if status == "valid":
            statuses["valid_generated"] += 1
        elif status == "invalid":
            statuses["invalid_generated"] += 1
        statuses[f"complex_export_{r.complex_export_status}"] += 1
        statuses[f"docking_eligibility_{r.docking_eligibility_status}"] += 1
        statuses[f"docking_run_{r.docking_run_status}"] += 1
    return statuses
