from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Mapping

from covalent_design.contracts.errors import ContractErrorInfo
from covalent_design.contracts.types import SCHEMA_VERSION, ArtifactRef, ValidationReceipt


def write_validation_receipt(path: Path, receipt: ValidationReceipt):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(receipt_to_dict(receipt), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return ArtifactRef(
        uri=path.name,
        sha256=_sha256_file(path),
        format="json",
        schema_version=SCHEMA_VERSION,
        bytes=path.stat().st_size,
        role="validation_receipt",
    )


def read_validation_receipt(path: Path) -> ValidationReceipt:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("VALIDATION_RECEIPT_ROOT_NOT_OBJECT")
    return receipt_from_dict(payload)


def receipt_to_dict(receipt: ValidationReceipt) -> dict[str, object]:
    return {
        "validator": receipt.validator,
        "contract_version": receipt.contract_version,
        "input_sha256": receipt.input_sha256,
        "passed": receipt.passed,
        "warnings": tuple(_error_to_dict(warning) for warning in receipt.warnings),
        "errors": tuple(_error_to_dict(error) for error in receipt.errors),
    }


def receipt_from_dict(payload: Mapping[str, object]) -> ValidationReceipt:
    return ValidationReceipt(
        validator=_require_str(payload, "validator"),
        contract_version=_require_str(payload, "contract_version"),
        input_sha256=_require_str(payload, "input_sha256"),
        passed=_require_bool(payload, "passed"),
        warnings=tuple(_error_from_dict(item) for item in _require_list(payload, "warnings")),
        errors=tuple(_error_from_dict(item) for item in _require_list(payload, "errors")),
    )


def _error_to_dict(error: ContractErrorInfo) -> dict[str, object]:
    return {
        "code": error.code,
        "owner": error.owner,
        "message": error.message,
        "location": error.location,
        "details": dict(error.details),
    }


def _error_from_dict(payload: object) -> ContractErrorInfo:
    if not isinstance(payload, dict):
        raise ValueError("VALIDATION_RECEIPT_ERROR_NOT_OBJECT")
    details = payload.get("details", {})
    if not isinstance(details, dict):
        raise ValueError("VALIDATION_RECEIPT_ERROR_DETAILS_NOT_OBJECT")
    return ContractErrorInfo(
        code=_require_str(payload, "code"),
        owner=_require_str(payload, "owner"),  # type: ignore[arg-type]
        message=_require_str(payload, "message"),
        location=payload.get("location") if isinstance(payload.get("location"), str) else None,
        details=details,
    )


def _require_str(payload: Mapping[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str):
        raise ValueError(f"VALIDATION_RECEIPT_{key.upper()}_INVALID")
    return value


def _require_bool(payload: Mapping[str, object], key: str) -> bool:
    value = payload.get(key)
    if not isinstance(value, bool):
        raise ValueError(f"VALIDATION_RECEIPT_{key.upper()}_INVALID")
    return value


def _require_list(payload: Mapping[str, object], key: str) -> list[object]:
    value = payload.get(key, [])
    if not isinstance(value, list):
        raise ValueError(f"VALIDATION_RECEIPT_{key.upper()}_INVALID")
    return value


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
