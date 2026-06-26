"""Task 53 V2 sampling request/result package-interface contracts.

This module defines schema, validation, and deterministic serialization for the
V2 sampling boundary. It intentionally does not execute sampling, export
complex artifacts, run metrics, or call heavy optional dependencies.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Mapping, Optional, Sequence

from covalent_design.contracts.errors import ContractErrorInfo
from covalent_design.contracts.types import (
    ArtifactRef,
    ContractEnvelope,
    FAILURE_REASON_CODES,
    Provenance,
    SAMPLING_SYSTEM_FAILURE_CATEGORIES,
    SCHEMA_VERSION,
    ValidationReceipt,
)

V2_SAMPLING_CONTRACT_VERSION = "v2-beta"
VALID_SPLIT_NAMES = ("train", "val", "test")
VALID_BASELINE_MODES = ("pmdm", "non_pmdm_baseline")
VALID_GENERATION_MODES = ("reactive_site",)

V2_SAMPLING_FAILURE_CONCEPTS = (
    "request_validation_failure",
    "sampling_system_failure",
    "invalid_generated_sample",
    "export_failure",
    "docking_not_run",
    "evaluation_artifact_corruption",
)

VALID_EXPORT_STATUSES = ("not_implemented", "failed")
VALID_DOCKING_STATUSES = ("not_run", "not_implemented")
VALID_EVALUATION_STATUSES = ("not_implemented", "artifact_corrupt")

_VALIDATOR = "covalent_design.inference.v2_sampling"


@dataclass(frozen=True)
class V2SamplingRequest:
    """V2 explicit reactive-site sampling request.

    Exactly one selector must be used: a split name or explicit record ids.
    Reference-ligand generation is not part of this contract.
    """

    request_id: str
    checkpoint_ref: ArtifactRef
    checkpoint_manifest_ref: ArtifactRef
    environment_manifest_ref: ArtifactRef
    random_seed: int
    sample_count: int
    output_root: str
    baseline_mode: str
    split_name: Optional[str] = None
    record_ids: tuple[str, ...] = ()
    family_filter: tuple[str, ...] = ()
    max_retries: int = 0
    retry_on_categories: tuple[str, ...] = ()
    generation_mode: str = "reactive_site"
    schema_version: str = SCHEMA_VERSION
    contract_version: str = V2_SAMPLING_CONTRACT_VERSION
    role: str = "v2_sampling_request"

    def __post_init__(self) -> None:
        object.__setattr__(self, "record_ids", tuple(self.record_ids))
        object.__setattr__(self, "family_filter", tuple(self.family_filter))
        object.__setattr__(self, "retry_on_categories", tuple(self.retry_on_categories))
        _validate_request_fields(self, raise_errors=True)


@dataclass(frozen=True)
class V2InvalidDecodeDiagnostic:
    """Per-sample invalid decode diagnostic, separate from system failures."""

    request_id: str
    sample_id: int
    failure_reason: str
    message: str = ""
    schema_version: str = SCHEMA_VERSION
    contract_version: str = V2_SAMPLING_CONTRACT_VERSION
    role: str = "v2_invalid_decode_diagnostic"

    def __post_init__(self) -> None:
        if self.sample_id < 0:
            raise ValueError("sample_id must be non-negative")
        if self.failure_reason not in FAILURE_REASON_CODES:
            raise ValueError(f"unknown failure_reason: {self.failure_reason!r}")


@dataclass(frozen=True)
class V2SamplingSystemFailure:
    """V2 sampling system failure event, not a generated sample row."""

    request_id: str
    sample_id: int
    failure_category: str
    message: str = ""
    retry_count: int = 0
    schema_version: str = SCHEMA_VERSION
    contract_version: str = V2_SAMPLING_CONTRACT_VERSION
    role: str = "v2_sampling_system_failure"

    def __post_init__(self) -> None:
        if self.sample_id < 0:
            raise ValueError("sample_id must be non-negative")
        if self.retry_count < 0:
            raise ValueError("retry_count must be non-negative")
        if self.failure_category not in SAMPLING_SYSTEM_FAILURE_CATEGORIES:
            raise ValueError(f"unknown failure_category: {self.failure_category!r}")


@dataclass(frozen=True)
class V2SamplingResult:
    """V2 sampling result summary for the lightweight sampling boundary."""

    request_id: str
    checkpoint_manifest_ref: ArtifactRef
    environment_manifest_ref: ArtifactRef
    checkpoint_ref: ArtifactRef
    baseline_mode: str
    split_name: Optional[str]
    family_filter: tuple[str, ...]
    random_seed: int
    requested_sample_count: int
    attempted_sample_count: int
    valid_sample_count: int
    invalid_sample_count: int
    sampling_system_failure_count: int
    invalid_decode_diagnostics: tuple[V2InvalidDecodeDiagnostic, ...] = ()
    sampling_system_failures: tuple[V2SamplingSystemFailure, ...] = ()
    export_status: str = "not_implemented"
    docking_status: str = "not_run"
    evaluation_status: str = "not_implemented"
    schema_version: str = SCHEMA_VERSION
    contract_version: str = V2_SAMPLING_CONTRACT_VERSION
    role: str = "v2_sampling_result"

    def __post_init__(self) -> None:
        object.__setattr__(self, "family_filter", tuple(self.family_filter))
        object.__setattr__(
            self,
            "invalid_decode_diagnostics",
            tuple(self.invalid_decode_diagnostics),
        )
        object.__setattr__(
            self,
            "sampling_system_failures",
            tuple(self.sampling_system_failures),
        )
        _validate_result_fields(self)


def build_v2_sampling_request(raw: Mapping[str, object]) -> ContractEnvelope[Optional[V2SamplingRequest]]:
    """Build a request and return structured validation errors on failure."""

    try:
        kwargs = dict(raw)
        request = V2SamplingRequest(**kwargs)  # type: ignore[arg-type]
    except TypeError as exc:
        error = _error("V2_SAMPLING_REQUIRED_FIELD_MISSING", str(exc))
        return _envelope(None, (error,))
    except ValueError as exc:
        code = _code_from_message(str(exc))
        error = _error(code, str(exc))
        return _envelope(None, (error,))
    return _envelope(request, ())


def validate_v2_sampling_request(request: V2SamplingRequest) -> ValidationReceipt:
    errors = tuple(_validate_request_fields(request, raise_errors=False))
    return _receipt(request, errors)


def v2_sampling_request_to_dict(request: V2SamplingRequest) -> dict[str, object]:
    return _sorted_mapping(
        {
            "schema_version": request.schema_version,
            "contract_version": request.contract_version,
            "role": request.role,
            "request_id": request.request_id,
            "checkpoint_ref": _artifact_ref_to_dict(request.checkpoint_ref),
            "checkpoint_manifest_ref": _artifact_ref_to_dict(request.checkpoint_manifest_ref),
            "environment_manifest_ref": _artifact_ref_to_dict(request.environment_manifest_ref),
            "split_name": request.split_name,
            "record_ids": list(request.record_ids),
            "family_filter": list(request.family_filter),
            "random_seed": request.random_seed,
            "sample_count": request.sample_count,
            "output_root": request.output_root,
            "max_retries": request.max_retries,
            "retry_on_categories": list(request.retry_on_categories),
            "baseline_mode": request.baseline_mode,
            "generation_mode": request.generation_mode,
        }
    )


def serialize_v2_sampling_request(request: V2SamplingRequest) -> str:
    return _canonical_json(v2_sampling_request_to_dict(request))


def hash_v2_sampling_request(request: V2SamplingRequest) -> str:
    return _sha256_text(serialize_v2_sampling_request(request))


def v2_invalid_decode_diagnostic_to_dict(diagnostic: V2InvalidDecodeDiagnostic) -> dict[str, object]:
    return _sorted_mapping(
        {
            "schema_version": diagnostic.schema_version,
            "contract_version": diagnostic.contract_version,
            "role": diagnostic.role,
            "request_id": diagnostic.request_id,
            "sample_id": diagnostic.sample_id,
            "failure_reason": diagnostic.failure_reason,
            "message": diagnostic.message,
        }
    )


def v2_sampling_system_failure_to_dict(failure: V2SamplingSystemFailure) -> dict[str, object]:
    return _sorted_mapping(
        {
            "schema_version": failure.schema_version,
            "contract_version": failure.contract_version,
            "role": failure.role,
            "request_id": failure.request_id,
            "sample_id": failure.sample_id,
            "failure_category": failure.failure_category,
            "message": failure.message,
            "retry_count": failure.retry_count,
        }
    )


def v2_sampling_result_to_dict(result: V2SamplingResult) -> dict[str, object]:
    return _sorted_mapping(
        {
            "schema_version": result.schema_version,
            "contract_version": result.contract_version,
            "role": result.role,
            "request_id": result.request_id,
            "checkpoint_manifest_ref": _artifact_ref_to_dict(result.checkpoint_manifest_ref),
            "environment_manifest_ref": _artifact_ref_to_dict(result.environment_manifest_ref),
            "checkpoint_ref": _artifact_ref_to_dict(result.checkpoint_ref),
            "baseline_mode": result.baseline_mode,
            "split_name": result.split_name,
            "family_filter": list(result.family_filter),
            "random_seed": result.random_seed,
            "requested_sample_count": result.requested_sample_count,
            "attempted_sample_count": result.attempted_sample_count,
            "valid_sample_count": result.valid_sample_count,
            "invalid_sample_count": result.invalid_sample_count,
            "sampling_system_failure_count": result.sampling_system_failure_count,
            "invalid_decode_diagnostics": [
                v2_invalid_decode_diagnostic_to_dict(item)
                for item in result.invalid_decode_diagnostics
            ],
            "sampling_system_failures": [
                v2_sampling_system_failure_to_dict(item)
                for item in result.sampling_system_failures
            ],
            "export_status": result.export_status,
            "docking_status": result.docking_status,
            "evaluation_status": result.evaluation_status,
        }
    )


def serialize_v2_sampling_result(result: V2SamplingResult) -> str:
    return _canonical_json(v2_sampling_result_to_dict(result))


def hash_v2_sampling_result(result: V2SamplingResult) -> str:
    return _sha256_text(serialize_v2_sampling_result(result))


def run_deterministic_fixture_sampling(
    request: V2SamplingRequest,
    fixture_records: Sequence[Mapping[str, object]],
    *,
    fixture_split_index: Optional[Mapping[str, object]] = None,
) -> V2SamplingResult:
    """Run deterministic in-memory fixture sampling for Task 54 smoke tests.

    This helper proves selector handling, seed determinism, and failure
    accounting without reading data roots, writing artifacts, or invoking model,
    docking, export, or evaluation code.
    """

    records = _select_fixture_records(
        request,
        fixture_records,
        fixture_split_index=fixture_split_index,
    )
    if not records:
        failures = tuple(
            V2SamplingSystemFailure(
                request_id=request.request_id,
                sample_id=sample_id,
                failure_category="sampler_invariant_violation",
                message=f"no eligible fixture records for sample {sample_id}",
                retry_count=0,
            )
            for sample_id in range(request.sample_count)
        )
        return V2SamplingResult(
            request_id=request.request_id,
            checkpoint_manifest_ref=request.checkpoint_manifest_ref,
            environment_manifest_ref=request.environment_manifest_ref,
            checkpoint_ref=request.checkpoint_ref,
            baseline_mode=request.baseline_mode,
            split_name=request.split_name,
            family_filter=request.family_filter,
            random_seed=request.random_seed,
            requested_sample_count=request.sample_count,
            attempted_sample_count=0,
            valid_sample_count=0,
            invalid_sample_count=0,
            sampling_system_failure_count=request.sample_count,
            sampling_system_failures=failures,
        )

    invalid_diagnostics: list[V2InvalidDecodeDiagnostic] = []
    system_failures: list[V2SamplingSystemFailure] = []
    valid_count = 0
    attempted_count = 0
    retry_category = _fixture_retry_category(request)

    for sample_id in range(request.sample_count):
        record = records[(sample_id // 2) % len(records)]
        record_id = _record_string(record, "record_id", f"record-{sample_id}")
        family = _record_string(record, "residue_reaction_family", "UNKNOWN_FAMILY")
        split = _fixture_record_split(record_id, fixture_split_index)
        message = f"{record_id}|{family}|{split}|fixture deterministic sampling"
        outcome = (request.random_seed + sample_id) % 5
        if outcome == 0:
            system_failures.append(
                V2SamplingSystemFailure(
                    request_id=request.request_id,
                    sample_id=sample_id,
                    failure_category=retry_category,
                    message=message + "|system failure",
                    retry_count=1 if request.max_retries > 0 else 0,
                )
            )
        else:
            attempted_count += 1
            if outcome in (1, 3):
                invalid_diagnostics.append(
                    V2InvalidDecodeDiagnostic(
                        request_id=request.request_id,
                        sample_id=sample_id,
                        failure_reason="LIGAND_CHEMISTRY_INVALID",
                        message=message + "|invalid decode",
                    )
                )
            else:
                valid_count += 1

    return V2SamplingResult(
        request_id=request.request_id,
        checkpoint_manifest_ref=request.checkpoint_manifest_ref,
        environment_manifest_ref=request.environment_manifest_ref,
        checkpoint_ref=request.checkpoint_ref,
        baseline_mode=request.baseline_mode,
        split_name=request.split_name,
        family_filter=request.family_filter,
        random_seed=request.random_seed,
        requested_sample_count=request.sample_count,
        attempted_sample_count=attempted_count,
        valid_sample_count=valid_count,
        invalid_sample_count=len(invalid_diagnostics),
        sampling_system_failure_count=len(system_failures),
        invalid_decode_diagnostics=tuple(invalid_diagnostics),
        sampling_system_failures=tuple(system_failures),
    )


def _select_fixture_records(
    request: V2SamplingRequest,
    fixture_records: Sequence[Mapping[str, object]],
    *,
    fixture_split_index: Optional[Mapping[str, object]],
) -> tuple[Mapping[str, object], ...]:
    by_id: dict[str, Mapping[str, object]] = {}
    for record in fixture_records:
        record_id = _record_string(record, "record_id", "")
        if record_id:
            by_id[record_id] = record

    if request.record_ids:
        selected = tuple(by_id[record_id] for record_id in request.record_ids if record_id in by_id)
    else:
        selected_items: list[Mapping[str, object]] = []
        for record in fixture_records:
            record_id = _record_string(record, "record_id", "")
            if _fixture_record_split(record_id, fixture_split_index) == request.split_name:
                selected_items.append(record)
        selected = tuple(selected_items)

    if request.family_filter:
        allowed = set(request.family_filter)
        selected = tuple(
            record
            for record in selected
            if _record_string(record, "residue_reaction_family", "") in allowed
        )

    return tuple(sorted(selected, key=lambda item: _record_string(item, "record_id", "")))


def _fixture_record_split(
    record_id: str,
    fixture_split_index: Optional[Mapping[str, object]],
) -> str:
    if fixture_split_index is None:
        return "unknown"
    raw = fixture_split_index.get(record_id)
    if isinstance(raw, str):
        return raw
    if isinstance(raw, Mapping):
        split = raw.get("split_name", raw.get("split"))
        if isinstance(split, str):
            return split
    return "unknown"


def _fixture_retry_category(request: V2SamplingRequest) -> str:
    for category in request.retry_on_categories:
        if category in SAMPLING_SYSTEM_FAILURE_CATEGORIES:
            return category
    return "sampler_invariant_violation"


def _record_string(record: Mapping[str, object], key: str, default: str) -> str:
    value = record.get(key)
    if isinstance(value, str) and value:
        return value
    return default


def _validate_request_fields(
    request: V2SamplingRequest,
    *,
    raise_errors: bool,
) -> tuple[ContractErrorInfo, ...]:
    errors: list[ContractErrorInfo] = []
    if request.checkpoint_ref is None:
        errors.append(_error("V2_SAMPLING_CHECKPOINT_REF_MISSING", "checkpoint_ref is required"))
    if request.checkpoint_manifest_ref is None:
        errors.append(_error("V2_SAMPLING_CHECKPOINT_MANIFEST_REF_MISSING", "checkpoint_manifest_ref is required"))
    if request.environment_manifest_ref is None:
        errors.append(_error("V2_SAMPLING_ENVIRONMENT_MANIFEST_REF_MISSING", "environment_manifest_ref is required"))
    has_split = request.split_name is not None
    has_records = bool(request.record_ids)
    if not has_split and not has_records:
        errors.append(_error("V2_SAMPLING_SELECTOR_MISSING", "split_name or record_ids is required"))
    if has_split and has_records:
        errors.append(_error("V2_SAMPLING_SELECTOR_CONFLICT", "use split_name or record_ids, not both"))
    if request.split_name is not None and request.split_name not in VALID_SPLIT_NAMES:
        errors.append(_error("V2_SAMPLING_SPLIT_NAME_UNSUPPORTED", "split_name must be train, val, or test"))
    if any(not isinstance(item, str) or not item for item in request.record_ids):
        errors.append(_error("V2_SAMPLING_RECORD_SELECTOR_INVALID", "record_ids must be non-empty strings"))
    if any(not isinstance(item, str) or not item for item in request.family_filter):
        errors.append(_error("V2_SAMPLING_FAMILY_FILTER_INVALID", "family_filter must contain non-empty strings"))
    if not _is_int(request.random_seed) or request.random_seed < 0:
        errors.append(_error("V2_SAMPLING_RANDOM_SEED_INVALID", "random_seed must be a non-negative integer"))
    if not _is_int(request.sample_count) or request.sample_count <= 0:
        errors.append(_error("V2_SAMPLING_SAMPLE_COUNT_INVALID", "sample_count must be a positive integer"))
    if not isinstance(request.output_root, str) or not request.output_root:
        errors.append(_error("V2_SAMPLING_OUTPUT_ROOT_MISSING", "output_root is required"))
    if not _is_int(request.max_retries) or request.max_retries < 0:
        errors.append(_error("V2_SAMPLING_MAX_RETRIES_INVALID", "max_retries must be a non-negative integer"))
    if "retry_exhausted" in request.retry_on_categories:
        errors.append(_error("V2_SAMPLING_RETRY_POLICY_INVALID", "retry_exhausted is a terminal sentinel"))
    invalid_retry = set(request.retry_on_categories) - set(SAMPLING_SYSTEM_FAILURE_CATEGORIES)
    if invalid_retry:
        errors.append(_error("V2_SAMPLING_RETRY_POLICY_INVALID", f"unknown retry categories: {sorted(invalid_retry)}"))
    if request.baseline_mode not in VALID_BASELINE_MODES:
        errors.append(_error("V2_SAMPLING_BASELINE_MODE_UNSUPPORTED", "baseline_mode is unsupported"))
    if request.generation_mode not in VALID_GENERATION_MODES:
        errors.append(_error("V2_SAMPLING_GENERATION_MODE_UNSUPPORTED", "generation_mode must remain reactive_site"))
    if errors and raise_errors:
        first = errors[0]
        raise ValueError(first.message)
    return tuple(errors)


def _validate_result_fields(result: V2SamplingResult) -> None:
    for name in (
        "requested_sample_count",
        "attempted_sample_count",
        "valid_sample_count",
        "invalid_sample_count",
        "sampling_system_failure_count",
    ):
        value = getattr(result, name)
        if not _is_int(value) or value < 0:
            raise ValueError(f"{name} must be a non-negative integer")
    if result.valid_sample_count + result.invalid_sample_count != result.attempted_sample_count:
        raise ValueError("valid_sample_count + invalid_sample_count must equal attempted_sample_count")
    if result.attempted_sample_count + result.sampling_system_failure_count != result.requested_sample_count:
        raise ValueError("attempted_sample_count + sampling_system_failure_count must equal requested_sample_count")
    if result.baseline_mode not in VALID_BASELINE_MODES:
        raise ValueError("baseline_mode is unsupported")
    if result.split_name is not None and result.split_name not in VALID_SPLIT_NAMES:
        raise ValueError("split_name must be train, val, or test")
    if any(not isinstance(item, str) or not item for item in result.family_filter):
        raise ValueError("family_filter must contain non-empty strings")
    if not _is_int(result.random_seed) or result.random_seed < 0:
        raise ValueError("random_seed must be a non-negative integer")
    if result.export_status not in VALID_EXPORT_STATUSES:
        raise ValueError("export_status is unsupported")
    if result.docking_status not in VALID_DOCKING_STATUSES:
        raise ValueError("docking_status is unsupported")
    if result.evaluation_status not in VALID_EVALUATION_STATUSES:
        raise ValueError("evaluation_status is unsupported")


def _envelope(
    payload: Optional[V2SamplingRequest],
    errors: tuple[ContractErrorInfo, ...],
) -> ContractEnvelope[Optional[V2SamplingRequest]]:
    receipt = ValidationReceipt(
        validator=_VALIDATOR,
        contract_version=V2_SAMPLING_CONTRACT_VERSION,
        input_sha256="",
        passed=not errors,
        errors=errors,
    )
    return ContractEnvelope(
        payload=payload,
        artifacts=(),
        receipt=receipt,
        provenance=Provenance(),
    )


def _receipt(value: object, errors: tuple[ContractErrorInfo, ...]) -> ValidationReceipt:
    return ValidationReceipt(
        validator=_VALIDATOR,
        contract_version=V2_SAMPLING_CONTRACT_VERSION,
        input_sha256=hashlib.sha256(repr(value).encode("utf-8")).hexdigest(),
        passed=not errors,
        errors=errors,
    )


def _code_from_message(message: str) -> str:
    mapping = (
        ("checkpoint_ref", "V2_SAMPLING_CHECKPOINT_REF_MISSING"),
        ("checkpoint_manifest_ref", "V2_SAMPLING_CHECKPOINT_MANIFEST_REF_MISSING"),
        ("environment_manifest_ref", "V2_SAMPLING_ENVIRONMENT_MANIFEST_REF_MISSING"),
        ("not both", "V2_SAMPLING_SELECTOR_CONFLICT"),
        ("split_name or record_ids", "V2_SAMPLING_SELECTOR_MISSING"),
        ("family_filter", "V2_SAMPLING_FAMILY_FILTER_INVALID"),
        ("random_seed", "V2_SAMPLING_RANDOM_SEED_INVALID"),
        ("sample_count", "V2_SAMPLING_SAMPLE_COUNT_INVALID"),
        ("output_root", "V2_SAMPLING_OUTPUT_ROOT_MISSING"),
        ("max_retries", "V2_SAMPLING_MAX_RETRIES_INVALID"),
        ("retry_exhausted", "V2_SAMPLING_RETRY_POLICY_INVALID"),
        ("retry categories", "V2_SAMPLING_RETRY_POLICY_INVALID"),
        ("baseline_mode", "V2_SAMPLING_BASELINE_MODE_UNSUPPORTED"),
        ("generation_mode", "V2_SAMPLING_GENERATION_MODE_UNSUPPORTED"),
    )
    for needle, code in mapping:
        if needle in message:
            return code
    return "V2_SAMPLING_REQUEST_INVALID"


def _error(code: str, message: str, location: Optional[str] = None) -> ContractErrorInfo:
    return ContractErrorInfo(
        code=code,
        owner="inference",
        message=message,
        location=location,
        details={},
    )


def _artifact_ref_to_dict(ref: ArtifactRef) -> dict[str, object]:
    return _sorted_mapping(
        {
            "uri": ref.uri,
            "sha256": ref.sha256,
            "format": ref.format,
            "schema_version": ref.schema_version,
            "role": ref.role,
            "bytes": ref.bytes,
        }
    )


def _sorted_mapping(value: Mapping[str, object]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key in sorted(value):
        item = value[key]
        if isinstance(item, dict):
            result[key] = _sorted_mapping(item)
        else:
            result[key] = item
    return result


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


__all__ = [
    "V2_SAMPLING_CONTRACT_VERSION",
    "V2_SAMPLING_FAILURE_CONCEPTS",
    "V2InvalidDecodeDiagnostic",
    "V2SamplingRequest",
    "V2SamplingResult",
    "V2SamplingSystemFailure",
    "build_v2_sampling_request",
    "hash_v2_sampling_request",
    "hash_v2_sampling_result",
    "run_deterministic_fixture_sampling",
    "serialize_v2_sampling_request",
    "serialize_v2_sampling_result",
    "v2_invalid_decode_diagnostic_to_dict",
    "v2_sampling_request_to_dict",
    "v2_sampling_result_to_dict",
    "v2_sampling_system_failure_to_dict",
    "validate_v2_sampling_request",
]