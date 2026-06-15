"""Evaluation denominator accounting - load, count, validate, and write.

Core API functions for Task 30 evaluation.  No RDKit, torch, or heavy deps.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Mapping

from covalent_design._yaml_loader import load_yaml_config
from covalent_design.contracts.errors import ContractError
from covalent_design.contracts.types import (
    CONTRACT_VERSION,
    SCHEMA_VERSION,
    ArtifactRef,
    ContractEnvelope,
    EvaluationSummary,
    GenerationRunManifest,
    Provenance,
    SamplingSystemFailure,
    ValidationReceipt,
)
from covalent_design.contracts.denominators import validate_evaluation_summary
from covalent_design.contracts.lifecycle import validate_generation_result
from covalent_design.evaluation.result_schema import decode_result_row
from covalent_design.io.artifacts import resolve_artifact_path, sha256_file, validate_artifact_ref
from covalent_design.io.jsonl import read_jsonl

REQUIRED_ARTIFACT_KEYS = ("request", "results", "sampling_system_failures")


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------


def load_generation_run(manifest: Path) -> ContractEnvelope[GenerationRunManifest]:
    """Parse and validate a generation-run manifest YAML.

    Returns a ContractEnvelope with the GenerationRunManifest payload and
    validated artifact references.
    """
    manifest = Path(manifest)
    root = manifest.parent.resolve()

    raw = _parse_manifest_yaml(manifest)
    _validate_manifest_header(raw, manifest)

    artifacts_raw = raw.get("artifacts")
    if not isinstance(artifacts_raw, dict):
        raise _error("MANIFEST_ARTIFACTS_MISSING", "Manifest must contain an artifacts map", "artifacts")

    for key in REQUIRED_ARTIFACT_KEYS:
        if key not in artifacts_raw:
            raise _error(
                "MANIFEST_REQUIRED_ARTIFACT_KEY_MISSING",
                f"Manifest artifacts must contain key {key!r}",
                f"artifacts.{key}",
            )

    request_ref = _build_and_validate_ref(
        artifacts_raw["request"], root, "request", "yml"
    )
    results_ref = _build_and_validate_ref(
        artifacts_raw["results"], root, "results", "jsonl"
    )
    failures_ref = _build_and_validate_ref(
        artifacts_raw["sampling_system_failures"], root, "sampling_system_failures", "jsonl"
    )

    checkpoint_ref: ArtifactRef | None = None
    cp_raw = raw.get("checkpoint_ref")
    if cp_raw is not None and isinstance(cp_raw, dict):
        checkpoint_ref = _decode_manual_artifact_ref(cp_raw)

    manifest_obj = GenerationRunManifest(
        schema_version=SCHEMA_VERSION,
        contract_version=CONTRACT_VERSION,
        role="generation_run_manifest",
        job_id=_require_str(raw, "job_id"),
        request_id=_require_str(raw, "request_id"),
        checkpoint_ref=checkpoint_ref,
        accepted_request_sample_count=_require_int(raw, "accepted_request_sample_count"),
        attempted_sample_count=_require_int(raw, "attempted_sample_count"),
        sampling_system_failure_count=_require_int(raw, "sampling_system_failure_count"),
        result_count=_require_int(raw, "result_count"),
        artifacts={
            "request": request_ref,
            "results": results_ref,
            "sampling_system_failures": failures_ref,
        },
    )

    manifest_sha256 = sha256_file(manifest)
    return ContractEnvelope(
        payload=manifest_obj,
        artifacts=(request_ref, results_ref, failures_ref),
        receipt=ValidationReceipt(
            validator="covalent_design.evaluation.load_generation_run",
            contract_version=CONTRACT_VERSION,
            input_sha256=manifest_sha256,
            passed=True,
        ),
        provenance=Provenance(
            inputs={
                "manifest": ArtifactRef(
                    uri=manifest.name,
                    sha256=manifest_sha256,
                    format="yml",
                    schema_version=SCHEMA_VERSION,
                    role="generation_run_manifest",
                    bytes=manifest.stat().st_size,
                )
            }
        ),
    )


def load_validated_results(manifest: Path) -> list[CovalentGenerationResult]:
    """Load a generation-run manifest and return fully validated results.

    Preserves all Task 30 validation: manifest parsing, artifact ref
    checks, checksum checks, JSONL schema checks, failures JSONL
    validation, manifest count checks, decode_result_row(), and
    validate_generation_result().

    Never exposes raw rows.  Does not produce denominator equations.
    """
    from covalent_design.contracts.types import CovalentGenerationResult

    decoded, _ = _load_and_validate_results(manifest)
    return decoded


def summarize_results(manifest: Path) -> EvaluationSummary:
    """Load a generation run and compute its EvaluationSummary.

    This API has no write side effect. Use ``write_evaluation_summary`` to
    persist the result. The CLI composes the two operations.
    """
    decoded, run = _load_and_validate_results(manifest)
    summary = _count_lifecycle(decoded, run)
    _raise_receipt_error(check_denominators(summary))
    return summary


def check_denominators(summary: EvaluationSummary) -> ValidationReceipt:
    """Validate the six EvaluationSummary conservation equations."""
    if not isinstance(summary, EvaluationSummary):
        raise TypeError("check_denominators() requires an EvaluationSummary")
    return validate_evaluation_summary(summary)


def evaluation_summary_to_dict(summary: EvaluationSummary) -> dict[str, object]:
    """Serialize an EvaluationSummary to a deterministic JSON-compatible dict."""
    return {
        "schema_version": SCHEMA_VERSION,
        "contract_version": CONTRACT_VERSION,
        "role": "evaluation_summary",
        "requested_sample_count": summary.requested_sample_count,
        "request_validation_error_sample_count": summary.request_validation_error_sample_count,
        "accepted_request_sample_count": summary.accepted_request_sample_count,
        "attempted_sample_count": summary.attempted_sample_count,
        "sampling_system_failure_count": summary.sampling_system_failure_count,
        "valid_generated_internal_count": summary.valid_generated_internal_count,
        "invalid_generated_sample_count": summary.invalid_generated_sample_count,
        "exported_valid_complex_count": summary.exported_valid_complex_count,
        "valid_export_failure_count": summary.valid_export_failure_count,
        "docking_evaluable_valid_sample_count": summary.docking_evaluable_valid_sample_count,
        "valid_but_not_docking_evaluable_sample_count": summary.valid_but_not_docking_evaluable_sample_count,
        "docking_not_run_valid_sample_count": summary.docking_not_run_valid_sample_count,
        "docking_failed_valid_sample_count": summary.docking_failed_valid_sample_count,
        "successfully_docked_valid_sample_count": summary.successfully_docked_valid_sample_count,
    }


def write_evaluation_summary(summary: EvaluationSummary, path: Path) -> ArtifactRef:
    """Write an EvaluationSummary to *path* atomically.

    Uses a same-directory temp file that is renamed into place.
    Returns an ArtifactRef for the written file.
    """
    path = Path(path)
    _raise_receipt_error(check_denominators(summary))
    _write_summary_atomic(summary, path)
    return ArtifactRef(
        uri=path.name,
        sha256=sha256_file(path),
        format="json",
        schema_version=SCHEMA_VERSION,
        role="evaluation_summary",
        bytes=path.stat().st_size,
    )


# ---------------------------------------------------------------------------
# internal: load and validate (shared by summarize_results and
# load_validated_results)
# ---------------------------------------------------------------------------


def _load_and_validate_results(
    manifest: Path,
) -> tuple[list[CovalentGenerationResult], GenerationRunManifest]:
    from covalent_design.contracts.types import CovalentGenerationResult

    manifest = Path(manifest)
    envelope = load_generation_run(manifest)
    run = envelope.payload
    root = manifest.parent

    results_rows = _read_results_jsonl(root, run)
    _read_failures_jsonl(root, run)

    if run.result_count != len(results_rows):
        raise _error(
            "EVALUATION_DENOMINATOR_RESULT_COUNT_MISMATCH",
            f"manifest.result_count={run.result_count} but results JSONL has {len(results_rows)} rows",
            "result_count",
            details={"manifest_count": run.result_count, "actual_count": len(results_rows)},
        )
    if run.attempted_sample_count != len(results_rows):
        raise _error(
            "EVALUATION_DENOMINATOR_ATTEMPTED_COUNT_MISMATCH",
            f"manifest.attempted_sample_count={run.attempted_sample_count} but results JSONL has {len(results_rows)} rows",
            "attempted_sample_count",
            details={"manifest_count": run.attempted_sample_count, "actual_count": len(results_rows)},
        )

    decoded = _decode_and_validate_results(results_rows)
    return decoded, run


# ---------------------------------------------------------------------------
# internal: manifest parsing and validation
# ---------------------------------------------------------------------------


def _parse_manifest_yaml(manifest: Path) -> dict[str, object]:
    try:
        raw = load_yaml_config(str(manifest))
    except Exception as exc:
        raise _error(
            "MANIFEST_YAML_UNREADABLE",
            f"Cannot parse manifest YAML: {exc}",
            str(manifest),
        ) from exc
    if not isinstance(raw, dict):
        raise _error(
            "MANIFEST_ROOT_NOT_OBJECT",
            "Manifest YAML root must be a mapping",
            str(manifest),
        )
    return raw


def _validate_manifest_header(raw: dict[str, object], manifest: Path) -> None:
    sv = raw.get("schema_version")
    if sv != SCHEMA_VERSION:
        raise _error(
            "MANIFEST_SCHEMA_VERSION_UNSUPPORTED",
            f"Expected schema_version {SCHEMA_VERSION!r}, got {sv!r}",
            "schema_version",
            details={"expected": SCHEMA_VERSION, "found": sv},
        )
    cv = raw.get("contract_version")
    if cv != CONTRACT_VERSION:
        raise _error(
            "MANIFEST_CONTRACT_VERSION_UNSUPPORTED",
            f"Expected contract_version {CONTRACT_VERSION!r}, got {cv!r}",
            "contract_version",
            details={"expected": CONTRACT_VERSION, "found": cv},
        )
    role = raw.get("role")
    if role != "generation_run_manifest":
        raise _error(
            "MANIFEST_ROLE_INVALID",
            f"Expected role 'generation_run_manifest', got {role!r}",
            "role",
            details={"expected": "generation_run_manifest", "found": role},
        )


def _build_and_validate_ref(
    raw: object,
    root: Path,
    expected_role: str,
    expected_format: str,
) -> ArtifactRef:
    if not isinstance(raw, dict):
        raise _error(
            "ARTIFACT_REF_NOT_OBJECT",
            f"Artifact entry for {expected_role!r} must be a mapping",
            expected_role,
        )

    uri = _require_str(raw, "uri")
    sha256_val = _require_str(raw, "sha256")
    fmt = _require_str(raw, "format")
    role = _require_str(raw, "role")
    schema_ver = raw.get("schema_version", SCHEMA_VERSION)
    if not isinstance(schema_ver, str):
        raise _error(
            "ARTIFACT_REF_SCHEMA_VERSION_INVALID",
            f"Artifact {expected_role!r} schema_version must be a string",
            expected_role,
        )
    if schema_ver != SCHEMA_VERSION:
        raise _error(
            "ARTIFACT_REF_SCHEMA_VERSION_UNSUPPORTED",
            f"Artifact {expected_role!r} schema_version must be {SCHEMA_VERSION!r}",
            f"artifacts.{expected_role}.schema_version",
            details={"expected": SCHEMA_VERSION, "found": schema_ver},
        )
    bytes_val = _require_int(raw, "bytes")

    ref = ArtifactRef(
        uri=uri,
        sha256=sha256_val,
        format=fmt,
        schema_version=schema_ver,
        role=role,
        bytes=bytes_val,
    )

    _validate_ref_uri(ref, root)

    v_receipt = validate_artifact_ref(ref, root=root)
    if not v_receipt.passed:
        err = v_receipt.errors[0]
        raise ContractError(
            code=err.code,
            owner=err.owner,
            message=err.message,
            location=err.location,
            details=err.details,
        )

    if role != expected_role:
        raise _error(
            "ARTIFACT_ROLE_MISMATCH",
            f"Artifact {expected_role!r} has unexpected role {role!r}",
            f"artifacts.{expected_role}.role",
            details={"expected": expected_role, "found": role},
        )
    if fmt != expected_format:
        raise _error(
            "ARTIFACT_FORMAT_MISMATCH",
            f"Artifact {expected_role!r} has unexpected format {fmt!r}",
            f"artifacts.{expected_role}.format",
            details={"expected": expected_format, "found": fmt},
        )

    return ref


def _validate_ref_uri(ref: ArtifactRef, root: Path) -> None:
    try:
        resolve_artifact_path(ref, root=root)
    except ValueError as exc:
        raise _error(
            "ARTIFACT_URI_INVALID",
            str(exc),
            ref.uri,
        ) from exc


def _decode_manual_artifact_ref(d: dict[str, object]) -> ArtifactRef:
    return ArtifactRef(
        uri=_require_str(d, "uri"),
        sha256=_require_str(d, "sha256"),
        format=_require_str(d, "format"),
        schema_version=_str(d.get("schema_version"), "1"),
        role=_str(d.get("role"), ""),
        bytes=_require_int(d, "bytes"),
    )


# ---------------------------------------------------------------------------
# internal: JSONL reading
# ---------------------------------------------------------------------------


def _read_results_jsonl(root: Path, run: GenerationRunManifest) -> tuple[dict[str, object], ...]:
    results_ref = run.artifacts["results"]
    results_path = resolve_artifact_path(results_ref, root=root)
    try:
        return read_jsonl(
            results_path,
            expected_schema_version=SCHEMA_VERSION,
            expected_contract_version=CONTRACT_VERSION,
        )
    except ValueError as exc:
        msg = str(exc)
        if "SCHEMA_VERSION" in msg.upper():
            raise _error(
                "JSONL_SCHEMA_VERSION_UNSUPPORTED",
                msg,
                str(results_path),
            ) from exc
        if "CONTRACT_VERSION" in msg.upper():
            raise _error(
                "JSONL_CONTRACT_VERSION_UNSUPPORTED",
                msg,
                str(results_path),
            ) from exc
        raise _error(
            "JSONL_READ_ERROR",
            msg,
            str(results_path),
        ) from exc


def _read_failures_jsonl(root: Path, run: GenerationRunManifest) -> tuple[dict[str, object], ...]:
    failures_ref = run.artifacts["sampling_system_failures"]
    failures_path = resolve_artifact_path(failures_ref, root=root)
    try:
        rows = read_jsonl(
            failures_path,
            expected_schema_version=SCHEMA_VERSION,
            expected_contract_version=CONTRACT_VERSION,
        )
    except ValueError as exc:
        msg = str(exc)
        if "SCHEMA_VERSION" in msg.upper():
            raise _error(
                "JSONL_SCHEMA_VERSION_UNSUPPORTED",
                msg,
                str(failures_path),
            ) from exc
        if "CONTRACT_VERSION" in msg.upper():
            raise _error(
                "JSONL_CONTRACT_VERSION_UNSUPPORTED",
                msg,
                str(failures_path),
            ) from exc
        raise _error(
            "JSONL_READ_ERROR",
            msg,
            str(failures_path),
        ) from exc
    _validate_failure_rows(rows)
    return rows


def _validate_failure_rows(rows: tuple[dict[str, object], ...]) -> None:
    for i, row in enumerate(rows):
        try:
            snapshot = row.get("resource_snapshot")
            if snapshot is not None and not isinstance(snapshot, dict):
                raise ValueError("resource_snapshot must be a mapping or null")
            SamplingSystemFailure(
                request_id=_require_str(row, "request_id"),
                sample_id=_require_int(row, "sample_id"),
                failure_category=_require_str(row, "failure_category"),
                failure_timestamp=_require_str(row, "failure_timestamp"),
                traceback_hash=_require_str(row, "traceback_hash"),
                log_uri=_require_str(row, "log_uri"),
                retry_count=_require_int(row, "retry_count"),
                resource_snapshot=snapshot,
                message=_str(row.get("message"), ""),
            )
        except (KeyError, TypeError, ValueError, ContractError) as exc:
            raise _error(
                "SAMPLING_FAILURE_ROW_DECODE_FAILED",
                f"Cannot decode sampling_system_failures row {i}: {exc}",
                f"sampling_system_failures[{i}]",
            ) from exc


# ---------------------------------------------------------------------------
# internal: decode and validate results
# ---------------------------------------------------------------------------


def _decode_and_validate_results(
    rows: tuple[dict[str, object], ...],
) -> list[CovalentGenerationResult]:
    from covalent_design.contracts.types import CovalentGenerationResult

    decoded: list[CovalentGenerationResult] = []
    for i, row in enumerate(rows):
        try:
            result = decode_result_row(row)
        except (KeyError, TypeError, ValueError) as exc:
            raise _error(
                "RESULT_ROW_DECODE_FAILED",
                f"Cannot decode results row {i}: {exc}",
                f"results[{i}]",
            ) from exc
        receipt = validate_generation_result(result)
        if not receipt.passed:
            err = receipt.errors[0]
            raise ContractError(
                code=err.code,
                owner=err.owner,
                message=err.message,
                location=f"results[{i}].{err.location}" if err.location else f"results[{i}]",
                details=err.details,
            )
        decoded.append(result)
    return decoded


# ---------------------------------------------------------------------------
# internal: lifecycle counting
# ---------------------------------------------------------------------------


def _count_lifecycle(
    results: list[CovalentGenerationResult],
    run: GenerationRunManifest,
) -> EvaluationSummary:
    valid_internal = 0
    invalid_generated = 0
    exported_valid = 0
    export_failure = 0
    docking_evaluable = 0
    not_docking_evaluable = 0
    docking_not_run = 0
    docking_failed = 0
    docking_succeeded = 0

    for r in results:
        if r.generation_validity_status == "valid":
            valid_internal += 1
            if r.complex_export_status == "exported":
                exported_valid += 1
                if r.docking_eligibility_status == "eligible":
                    docking_evaluable += 1
                    if r.docking_run_status == "not_run":
                        docking_not_run += 1
                    elif r.docking_run_status == "failed":
                        docking_failed += 1
                    elif r.docking_run_status == "succeeded":
                        docking_succeeded += 1
                elif r.docking_eligibility_status == "not_evaluable":
                    not_docking_evaluable += 1
            elif r.complex_export_status == "failed":
                export_failure += 1
        elif r.generation_validity_status == "invalid":
            invalid_generated += 1

    return EvaluationSummary(
        requested_sample_count=run.accepted_request_sample_count,
        request_validation_error_sample_count=0,
        accepted_request_sample_count=run.accepted_request_sample_count,
        attempted_sample_count=run.attempted_sample_count,
        sampling_system_failure_count=run.sampling_system_failure_count,
        valid_generated_internal_count=valid_internal,
        invalid_generated_sample_count=invalid_generated,
        exported_valid_complex_count=exported_valid,
        valid_export_failure_count=export_failure,
        docking_evaluable_valid_sample_count=docking_evaluable,
        valid_but_not_docking_evaluable_sample_count=not_docking_evaluable,
        docking_not_run_valid_sample_count=docking_not_run,
        docking_failed_valid_sample_count=docking_failed,
        successfully_docked_valid_sample_count=docking_succeeded,
    )


# ---------------------------------------------------------------------------
# internal: atomic write
# ---------------------------------------------------------------------------


def _write_summary_atomic(summary: EvaluationSummary, path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    payload = evaluation_summary_to_dict(summary)
    json_text = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)

    fd, tmp_path_str = tempfile.mkstemp(
        suffix=".tmp",
        prefix=".evaluation_summary",
        dir=str(path.parent),
    )
    tmp_path = Path(tmp_path_str)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(json_text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    except BaseException:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        raise


def _raise_receipt_error(receipt: ValidationReceipt) -> None:
    if receipt.passed:
        return
    err = receipt.errors[0]
    raise ContractError(
        code=err.code,
        owner=err.owner,
        message=err.message,
        location=err.location,
        details=err.details,
    )


# ---------------------------------------------------------------------------
# internal: error construction
# ---------------------------------------------------------------------------


def _error(
    code: str,
    message: str,
    location: str | None = None,
    *,
    details: dict[str, object] | None = None,
) -> ContractError:
    return ContractError(
        code=code,
        owner="evaluation",
        message=message,
        location=location,
        details=details or {},
    )


# ---------------------------------------------------------------------------
# internal: type-safe extractors
# ---------------------------------------------------------------------------


def _require_str(d: Mapping[str, object], key: str) -> str:
    v = d[key]
    if not isinstance(v, str):
        raise _error(
            "TYPE_ERROR",
            f"Expected string for {key!r}, got {type(v).__name__}",
            key,
        )
    return v


def _str(v: object, default: str) -> str:
    if v is None:
        return default
    if not isinstance(v, str):
        raise _error(
            "TYPE_ERROR",
            f"Expected string, got {type(v).__name__}",
        )
    return v


def _require_int(d: Mapping[str, object], key: str) -> int:
    v = d[key]
    if isinstance(v, bool) or not isinstance(v, int):
        raise _error(
            "TYPE_ERROR",
            f"Expected integer for {key!r}, got {type(v).__name__}",
            key,
        )
    return v
