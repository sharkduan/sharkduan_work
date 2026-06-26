"""Task 55 V2 evaluation metrics contract.

The module evaluates lightweight V2 sampling-result summaries and explicit
fixture/evidence metadata. It does not read real data roots, run docking, import
heavy chemistry/model dependencies, or publish scientific conclusions.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Mapping, Optional, Sequence

from covalent_design.contracts.errors import ContractErrorInfo
from covalent_design.contracts.types import (
    ArtifactRef,
    ContractEnvelope,
    Provenance,
    SCHEMA_VERSION,
    ValidationReceipt,
)
from covalent_design.inference.v2_sampling import (
    V2InvalidDecodeDiagnostic,
    V2SamplingResult,
    V2SamplingSystemFailure,
    V2_SAMPLING_CONTRACT_VERSION,
    V2_SAMPLING_FAILURE_CONCEPTS,
    v2_sampling_result_to_dict,
)

V2_EVALUATION_CONTRACT_VERSION = V2_SAMPLING_CONTRACT_VERSION
V2_EVALUATION_ROLE = "v2_evaluation_report"
_VALIDATOR = "covalent_design.evaluation.v2_metrics"


@dataclass(frozen=True)
class V2EvaluationReport:
    """Deterministic V2 evaluation report for Task 55."""

    request_id: str
    report_id: str
    validity_metrics: Mapping[str, object]
    family_metrics: Mapping[str, object]
    covalent_geometry_metrics: Mapping[str, object]
    uniqueness_novelty_metrics: Mapping[str, object]
    rdkit_validity_metrics: Mapping[str, object]
    failure_accounting: Mapping[str, object]
    denominator_conservation: Mapping[str, object]
    baseline_mode: str
    split_name: Optional[str]
    random_seed: int
    docking_evaluation_status: str = "not_evaluable"
    schema_version: str = SCHEMA_VERSION
    contract_version: str = V2_EVALUATION_CONTRACT_VERSION
    role: str = V2_EVALUATION_ROLE


def build_v2_evaluation_report(
    sampling_result: V2SamplingResult,
    *,
    fixture_records: Sequence[Mapping[str, object]] = (),
    fixture_split_index: Optional[Mapping[str, object]] = None,
    geometry_evidence: Optional[Mapping[str, object]] = None,
    uniqueness_evidence: Optional[Mapping[str, object]] = None,
    rdkit_evidence: Optional[Mapping[str, object]] = None,
) -> ContractEnvelope[V2EvaluationReport]:
    """Build a deterministic report from a Task 53/54 sampling result."""

    errors = _denominator_errors(sampling_result)
    if errors:
        return _envelope(_empty_report(sampling_result), errors, sampling_result)

    validity = _validity_metrics(sampling_result)
    family = _family_metrics(
        sampling_result,
        fixture_records=fixture_records,
        fixture_split_index=fixture_split_index,
    )
    geometry = _geometry_metrics(geometry_evidence)
    uniqueness = _uniqueness_metrics(uniqueness_evidence)
    rdkit = _rdkit_metrics(rdkit_evidence)
    failures = _failure_accounting(sampling_result)
    conservation = _denominator_conservation(sampling_result)

    report = V2EvaluationReport(
        request_id=sampling_result.request_id,
        report_id="",
        validity_metrics=validity,
        family_metrics=family,
        covalent_geometry_metrics=geometry,
        uniqueness_novelty_metrics=uniqueness,
        rdkit_validity_metrics=rdkit,
        failure_accounting=failures,
        denominator_conservation=conservation,
        baseline_mode=sampling_result.baseline_mode,
        split_name=sampling_result.split_name,
        random_seed=sampling_result.random_seed,
    )
    report_id = "sha256:" + hashlib.sha256(
        serialize_v2_evaluation_report(report).encode("utf-8")
    ).hexdigest()
    report = replace(report, report_id=report_id)
    return _envelope(report, (), sampling_result)


def load_v2_sampling_result_file(path: Path | str) -> ContractEnvelope[Optional[V2SamplingResult]]:
    """Load a V2SamplingResult JSON file with structured validation errors."""

    path_obj = Path(path)
    if not path_obj.exists():
        return _load_envelope(
            None,
            (
                _error(
                    "V2_EVALUATION_INPUT_MISSING",
                    f"sampling result file does not exist: {path_obj}",
                ),
            ),
            "",
        )
    try:
        raw = json.loads(path_obj.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        return _load_envelope(
            None,
            (_error("V2_EVALUATION_INPUT_CORRUPT", str(exc)),),
            "",
        )
    input_hash = _sha256_obj(raw)
    try:
        result = _sampling_result_from_mapping(raw)
    except ValueError as exc:
        code = "V2_EVALUATION_DENOMINATOR_MISMATCH" if "count" in str(exc) else "V2_EVALUATION_INPUT_INVALID"
        return _load_envelope(None, (_error(code, str(exc)),), input_hash)
    except (KeyError, TypeError) as exc:
        return _load_envelope(None, (_error("V2_EVALUATION_INPUT_INVALID", str(exc)),), input_hash)
    return _load_envelope(result, (), input_hash)


def load_json_mapping_file(path: Path | str) -> ContractEnvelope[Optional[Mapping[str, object]]]:
    path_obj = Path(path)
    if not path_obj.exists():
        return _load_envelope(
            None,
            (_error("V2_EVALUATION_INPUT_MISSING", f"input file does not exist: {path_obj}"),),
            "",
        )
    try:
        payload = json.loads(path_obj.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        return _load_envelope(None, (_error("V2_EVALUATION_INPUT_CORRUPT", str(exc)),), "")
    if not isinstance(payload, Mapping):
        return _load_envelope(None, (_error("V2_EVALUATION_INPUT_INVALID", "expected JSON object"),), _sha256_obj(payload))
    return _load_envelope(payload, (), _sha256_obj(payload))


def load_records_jsonl(path: Path | str) -> ContractEnvelope[Optional[tuple[Mapping[str, object], ...]]]:
    path_obj = Path(path)
    if not path_obj.exists():
        return _load_envelope(
            None,
            (_error("V2_EVALUATION_INPUT_MISSING", f"records file does not exist: {path_obj}"),),
            "",
        )
    records: list[Mapping[str, object]] = []
    try:
        for line in path_obj.read_text(encoding="utf-8-sig").splitlines():
            if line.strip():
                item = json.loads(line)
                if not isinstance(item, Mapping):
                    raise ValueError("records JSONL line must be an object")
                records.append(item)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return _load_envelope(None, (_error("V2_EVALUATION_INPUT_CORRUPT", str(exc)),), "")
    return _load_envelope(tuple(records), (), _sha256_obj(records))


def v2_evaluation_report_to_dict(report: V2EvaluationReport) -> dict[str, object]:
    return _sort_mapping(
        {
            "schema_version": report.schema_version,
            "contract_version": report.contract_version,
            "role": report.role,
            "request_id": report.request_id,
            "report_id": report.report_id,
            "baseline_mode": report.baseline_mode,
            "split_name": report.split_name,
            "random_seed": report.random_seed,
            "validity_metrics": report.validity_metrics,
            "family_metrics": report.family_metrics,
            "covalent_geometry_metrics": report.covalent_geometry_metrics,
            "uniqueness_novelty_metrics": report.uniqueness_novelty_metrics,
            "rdkit_validity_metrics": report.rdkit_validity_metrics,
            "failure_accounting": report.failure_accounting,
            "denominator_conservation": report.denominator_conservation,
            "docking_evaluation_status": report.docking_evaluation_status,
        }
    )


def serialize_v2_evaluation_report(report: V2EvaluationReport) -> str:
    return _canonical_json(v2_evaluation_report_to_dict(report))


def hash_v2_evaluation_report(report: V2EvaluationReport) -> str:
    return "sha256:" + hashlib.sha256(
        serialize_v2_evaluation_report(report).encode("utf-8")
    ).hexdigest()


def _validity_metrics(result: V2SamplingResult) -> dict[str, object]:
    attempted = result.attempted_sample_count
    requested = result.requested_sample_count
    return _sort_mapping(
        {
            "status": "computed",
            "requested_sample_count": requested,
            "attempted_sample_count": attempted,
            "valid_sample_count": result.valid_sample_count,
            "invalid_sample_count": result.invalid_sample_count,
            "sampling_system_failure_count": result.sampling_system_failure_count,
            "valid_rate_of_attempted": _rate(result.valid_sample_count, attempted),
            "valid_rate_of_requested": _rate(result.valid_sample_count, requested),
        }
    )


def _family_metrics(
    result: V2SamplingResult,
    *,
    fixture_records: Sequence[Mapping[str, object]],
    fixture_split_index: Optional[Mapping[str, object]],
) -> dict[str, object]:
    records = tuple(sorted(fixture_records, key=lambda item: _string(item, "record_id", "")))
    if not records:
        return {"reason": "fixture_family_metadata_absent", "status": "not_evaluable"}

    failed_sample_ids = {item.sample_id for item in result.sampling_system_failures}
    invalid_sample_ids = {item.sample_id for item in result.invalid_decode_diagnostics}
    by_family: dict[str, dict[str, int]] = {}
    for sample_id in range(result.requested_sample_count):
        record = records[(sample_id // 2) % len(records)]
        record_id = _string(record, "record_id", f"record-{sample_id}")
        family = _string(record, "residue_reaction_family", "UNKNOWN_FAMILY")
        split_name = _split_for_record(record_id, record, fixture_split_index)
        if result.split_name is not None and split_name not in (result.split_name, "unknown"):
            family = f"{family}|outside_{result.split_name}"
        bucket = by_family.setdefault(
            family,
            {
                "invalid_sample_count": 0,
                "requested_sample_count": 0,
                "sampling_system_failure_count": 0,
                "valid_sample_count": 0,
            },
        )
        bucket["requested_sample_count"] += 1
        if sample_id in failed_sample_ids:
            bucket["sampling_system_failure_count"] += 1
        elif sample_id in invalid_sample_ids:
            bucket["invalid_sample_count"] += 1
        else:
            bucket["valid_sample_count"] += 1
    return _sort_mapping({"families": _sort_mapping(by_family), "status": "computed"})


def _geometry_metrics(evidence: Optional[Mapping[str, object]]) -> dict[str, object]:
    if evidence is None:
        return {"reason": "geometry_evidence_absent", "status": "not_evaluable"}
    values = evidence.get("bond_length_angstrom", ())
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        return {"reason": "geometry_evidence_invalid", "status": "not_evaluable"}
    lengths = [float(value) for value in values]
    mean_length = sum(lengths) / len(lengths) if lengths else None
    return _sort_mapping(
        {
            "bond_length_count": len(lengths),
            "bond_length_mean_angstrom": mean_length,
            "geometry_failure_count": int(evidence.get("geometry_failure_count", 0)),
            "status": "computed",
        }
    )


def _uniqueness_metrics(evidence: Optional[Mapping[str, object]]) -> dict[str, object]:
    if evidence is None:
        return {"reason": "uniqueness_evidence_absent", "status": "not_evaluable"}
    raw_sample_ids = evidence.get("sample_ids", ())
    raw_known = evidence.get("known_generated_ids", ())
    if not isinstance(raw_sample_ids, Sequence) or isinstance(raw_sample_ids, (str, bytes)):
        return {"reason": "uniqueness_evidence_invalid", "status": "not_evaluable"}
    sample_ids = [str(item) for item in raw_sample_ids]
    known = {str(item) for item in raw_known} if isinstance(raw_known, Sequence) else set()
    unique = set(sample_ids)
    novel = unique - known
    return _sort_mapping(
        {
            "generated_identifier_count": len(sample_ids),
            "novel_identifier_count": len(novel),
            "novelty_rate": _rate(len(novel), len(unique)),
            "status": "computed",
            "unique_identifier_count": len(unique),
            "uniqueness_rate": _rate(len(unique), len(sample_ids)),
        }
    )


def _rdkit_metrics(evidence: Optional[Mapping[str, object]]) -> dict[str, object]:
    if evidence is None:
        return {"reason": "rdkit_evidence_absent", "status": "not_evaluable"}
    valid = int(evidence.get("valid_count", 0))
    invalid = int(evidence.get("invalid_count", 0))
    total = valid + invalid
    return _sort_mapping(
        {
            "invalid_count": invalid,
            "status": "computed",
            "valid_count": valid,
            "valid_rate": _rate(valid, total),
        }
    )


def _failure_accounting(result: V2SamplingResult) -> dict[str, object]:
    categories = {name: 0 for name in V2_SAMPLING_FAILURE_CONCEPTS}
    categories["sampling_system_failure"] = result.sampling_system_failure_count
    categories["invalid_generated_sample"] = result.invalid_sample_count
    categories["export_failure"] = 1 if result.export_status == "failed" else 0
    categories["docking_not_run"] = 1 if result.docking_status in ("not_run", "not_implemented") else 0
    invalid_reasons = _count_by(
        item.failure_reason for item in result.invalid_decode_diagnostics
    )
    system_categories = _count_by(
        item.failure_category for item in result.sampling_system_failures
    )
    return _sort_mapping(
        {
            "categories": _sort_mapping(categories),
            "invalid_decode_failure_reasons": _sort_mapping(invalid_reasons),
            "sampling_system_failure_categories": _sort_mapping(system_categories),
            "status": "computed",
        }
    )


def _denominator_conservation(result: V2SamplingResult) -> dict[str, object]:
    equations = {
        "attempted_plus_system_failures_equals_requested": (
            result.attempted_sample_count + result.sampling_system_failure_count,
            result.requested_sample_count,
        ),
        "valid_plus_invalid_equals_attempted": (
            result.valid_sample_count + result.invalid_sample_count,
            result.attempted_sample_count,
        ),
        "invalid_diagnostics_equal_invalid_count": (
            len(result.invalid_decode_diagnostics),
            result.invalid_sample_count,
        ),
        "system_failure_events_equal_system_failure_count": (
            len(result.sampling_system_failures),
            result.sampling_system_failure_count,
        ),
    }
    checks = {
        key: {"left": left, "passed": left == right, "right": right}
        for key, (left, right) in equations.items()
    }
    return _sort_mapping({"checks": _sort_mapping(checks), "passed": all(item["passed"] for item in checks.values())})


def _denominator_errors(result: V2SamplingResult) -> tuple[ContractErrorInfo, ...]:
    conservation = _denominator_conservation(result)
    if conservation["passed"]:
        return ()
    return (
        _error(
            "V2_EVALUATION_DENOMINATOR_MISMATCH",
            "sampling result denominator equations do not reconcile",
        ),
    )


def _sampling_result_from_mapping(raw: Mapping[str, object]) -> V2SamplingResult:
    kwargs = dict(raw)
    for key in ("checkpoint_manifest_ref", "environment_manifest_ref", "checkpoint_ref"):
        kwargs[key] = _artifact_from_mapping(kwargs[key])  # type: ignore[index]
    kwargs["family_filter"] = tuple(kwargs.get("family_filter", ()))
    kwargs["invalid_decode_diagnostics"] = tuple(
        V2InvalidDecodeDiagnostic(**dict(item))  # type: ignore[arg-type]
        for item in kwargs.get("invalid_decode_diagnostics", ())
    )
    kwargs["sampling_system_failures"] = tuple(
        V2SamplingSystemFailure(**dict(item))  # type: ignore[arg-type]
        for item in kwargs.get("sampling_system_failures", ())
    )
    for optional in ("schema_version", "contract_version", "role"):
        kwargs.pop(optional, None)
    return V2SamplingResult(**kwargs)  # type: ignore[arg-type]


def _artifact_from_mapping(raw: object) -> ArtifactRef:
    if not isinstance(raw, Mapping):
        raise TypeError("artifact ref must be an object")
    return ArtifactRef(
        uri=str(raw.get("uri", "")),
        sha256=str(raw.get("sha256", "")),
        format=str(raw.get("format", "")),
        schema_version=str(raw.get("schema_version", SCHEMA_VERSION)),
        role=str(raw.get("role", "")),
        bytes=int(raw.get("bytes", 0)),
    )


def _empty_report(result: V2SamplingResult) -> V2EvaluationReport:
    return V2EvaluationReport(
        request_id=result.request_id,
        report_id="",
        validity_metrics={},
        family_metrics={},
        covalent_geometry_metrics={},
        uniqueness_novelty_metrics={},
        rdkit_validity_metrics={},
        failure_accounting={},
        denominator_conservation={},
        baseline_mode=result.baseline_mode,
        split_name=result.split_name,
        random_seed=result.random_seed,
    )


def _envelope(
    payload: V2EvaluationReport,
    errors: tuple[ContractErrorInfo, ...],
    result: V2SamplingResult,
) -> ContractEnvelope[V2EvaluationReport]:
    receipt = ValidationReceipt(
        validator=_VALIDATOR,
        contract_version=V2_EVALUATION_CONTRACT_VERSION,
        input_sha256=_sha256_obj(v2_sampling_result_to_dict(result)),
        passed=not errors,
        errors=errors,
    )
    return ContractEnvelope(
        payload=payload,
        artifacts=(),
        receipt=receipt,
        provenance=Provenance(inputs={}),
    )


def _load_envelope(
    payload: object,
    errors: tuple[ContractErrorInfo, ...],
    input_sha256: str,
) -> ContractEnvelope[object]:
    receipt = ValidationReceipt(
        validator=_VALIDATOR,
        contract_version=V2_EVALUATION_CONTRACT_VERSION,
        input_sha256=input_sha256,
        passed=not errors,
        errors=errors,
    )
    return ContractEnvelope(
        payload=payload,
        artifacts=(),
        receipt=receipt,
        provenance=Provenance(),
    )


def errors_to_dict(errors: Sequence[ContractErrorInfo]) -> dict[str, object]:
    return {
        "errors": [
            {
                "code": error.code,
                "details": dict(error.details),
                "location": error.location,
                "message": error.message,
                "owner": error.owner,
            }
            for error in errors
        ],
        "status": "error",
    }


def _error(code: str, message: str) -> ContractErrorInfo:
    return ContractErrorInfo(code=code, owner="evaluation", message=message)


def _record_id(record: Mapping[str, object], fallback: str) -> str:
    return _string(record, "record_id", fallback)


def _split_for_record(
    record_id: str,
    record: Mapping[str, object],
    fixture_split_index: Optional[Mapping[str, object]],
) -> str:
    if fixture_split_index is None:
        return _string(record, "split_name", "unknown")
    raw = fixture_split_index.get(record_id)
    if isinstance(raw, str):
        return raw
    if isinstance(raw, Mapping):
        split = raw.get("split_name", raw.get("split"))
        if isinstance(split, str):
            return split
    return _string(record, "split_name", "unknown")


def _string(record: Mapping[str, object], key: str, default: str) -> str:
    value = record.get(key)
    if isinstance(value, str) and value:
        return value
    return default


def _count_by(items: Sequence[str] | object) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:  # type: ignore[union-attr]
        counts[str(item)] = counts.get(str(item), 0) + 1
    return counts


def _rate(numerator: int, denominator: int) -> Optional[float]:
    if denominator == 0:
        return None
    return numerator / denominator


def _sort_mapping(value: Mapping[str, object]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key in sorted(value):
        item = value[key]
        if isinstance(item, Mapping):
            result[key] = _sort_mapping(item)
        elif isinstance(item, tuple):
            result[key] = [_sort_value(part) for part in item]
        elif isinstance(item, list):
            result[key] = [_sort_value(part) for part in item]
        else:
            result[key] = item
    return result


def _sort_value(value: object) -> object:
    if isinstance(value, Mapping):
        return _sort_mapping(value)
    if isinstance(value, tuple):
        return [_sort_value(part) for part in value]
    if isinstance(value, list):
        return [_sort_value(part) for part in value]
    return value


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_obj(value: object) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json(_sort_value(value)).encode("utf-8")).hexdigest()


__all__ = [
    "V2_EVALUATION_CONTRACT_VERSION",
    "V2EvaluationReport",
    "build_v2_evaluation_report",
    "errors_to_dict",
    "hash_v2_evaluation_report",
    "load_json_mapping_file",
    "load_records_jsonl",
    "load_v2_sampling_result_file",
    "serialize_v2_evaluation_report",
    "v2_evaluation_report_to_dict",
]
