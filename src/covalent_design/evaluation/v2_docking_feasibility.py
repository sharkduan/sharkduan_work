"""Task 56 V2 docking feasibility report.

This module records explicit feasibility evidence for a future optional docking
integration. It does not invoke external engines, read real data roots, or
produce docking artifacts.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from typing import Mapping, Optional, Sequence

from covalent_design.contracts.errors import ContractErrorInfo
from covalent_design.contracts.types import (
    ContractEnvelope,
    Provenance,
    SCHEMA_VERSION,
    ValidationReceipt,
)
from covalent_design.inference.v2_sampling import V2_SAMPLING_CONTRACT_VERSION

V2_DOCKING_FEASIBILITY_CONTRACT_VERSION = V2_SAMPLING_CONTRACT_VERSION
V2_DOCKING_FEASIBILITY_ROLE = "v2_docking_feasibility_report"
_VALIDATOR = "covalent_design.evaluation.v2_docking_feasibility"

FEASIBILITY_STATUSES = (
    "feasible",
    "not_evaluable",
    "failed_probe",
    "license_unknown",
)
LICENSE_STATUSES = (
    "allowed",
    "restricted",
    "blocked",
    "unknown",
    "manual_exempt",
    "not_applicable",
)
PROBE_STATUSES = ("passed", "failed", "not_attempted")
FORMAT_SUPPORT_STATUSES = ("supported", "unsupported", "not_checked")


@dataclass(frozen=True)
class V2DockingFeasibilityReport:
    """Serializable feasibility report for optional future docking."""

    request_id: str
    report_id: str
    engine_candidate: str
    feasibility_status: str
    license_status: str
    install_path: Optional[str]
    missing_install_reason: Optional[str]
    cli_probe_status: str
    api_probe_status: str
    input_format_support: Mapping[str, object]
    output_format_support: Mapping[str, object]
    probe_duration_seconds: Optional[float]
    engine_version: Optional[str] = None
    not_evaluable_reason: Optional[str] = None
    non_blocking: bool = True
    beta_release_impact: str = "none"
    output_artifact_required: bool = False
    no_real_docking_executed: bool = True
    model_performance_impact: str = "none"
    schema_version: str = SCHEMA_VERSION
    contract_version: str = V2_DOCKING_FEASIBILITY_CONTRACT_VERSION
    role: str = V2_DOCKING_FEASIBILITY_ROLE


def build_v2_docking_feasibility_report(
    evidence: Mapping[str, object],
    *,
    request_id: str = "v2-docking-feasibility",
) -> ContractEnvelope[Optional[V2DockingFeasibilityReport]]:
    """Build a feasibility report from explicit evidence.

    Evidence must be provided by tests or a future environment probe. This
    function intentionally does not execute any external command.
    """

    errors = _validate_evidence(evidence)
    if errors:
        return _envelope(None, errors, evidence)

    report = V2DockingFeasibilityReport(
        request_id=request_id,
        report_id="",
        engine_candidate=_string(evidence, "engine_candidate", "unspecified"),
        feasibility_status=_string(evidence, "feasibility_status", "not_evaluable"),
        license_status=_string(evidence, "license_status", "not_applicable"),
        install_path=_optional_string(evidence.get("install_path")),
        missing_install_reason=_optional_string(evidence.get("missing_install_reason")),
        cli_probe_status=_string(evidence, "cli_probe_status", "not_attempted"),
        api_probe_status=_string(evidence, "api_probe_status", "not_attempted"),
        input_format_support=_format_support(evidence.get("input_format_support")),
        output_format_support=_format_support(evidence.get("output_format_support")),
        probe_duration_seconds=_optional_float(evidence.get("probe_duration_seconds")),
        engine_version=_optional_string(evidence.get("engine_version")),
        not_evaluable_reason=_optional_string(evidence.get("not_evaluable_reason")),
    )
    report_id = "sha256:" + hashlib.sha256(
        serialize_v2_docking_feasibility_report(report).encode("utf-8")
    ).hexdigest()
    report = replace(report, report_id=report_id)
    return _envelope(report, (), evidence)


def v2_docking_feasibility_report_to_dict(
    report: V2DockingFeasibilityReport,
) -> dict[str, object]:
    return _sort_mapping(
        {
            "api_probe_status": report.api_probe_status,
            "beta_release_impact": report.beta_release_impact,
            "cli_probe_status": report.cli_probe_status,
            "contract_version": report.contract_version,
            "engine_candidate": report.engine_candidate,
            "engine_version": report.engine_version,
            "feasibility_status": report.feasibility_status,
            "input_format_support": report.input_format_support,
            "install_path": report.install_path,
            "license_status": report.license_status,
            "missing_install_reason": report.missing_install_reason,
            "model_performance_impact": report.model_performance_impact,
            "no_real_docking_executed": report.no_real_docking_executed,
            "non_blocking": report.non_blocking,
            "not_evaluable_reason": report.not_evaluable_reason,
            "output_artifact_required": report.output_artifact_required,
            "output_format_support": report.output_format_support,
            "probe_duration_seconds": report.probe_duration_seconds,
            "report_id": report.report_id,
            "request_id": report.request_id,
            "role": report.role,
            "schema_version": report.schema_version,
        }
    )


def serialize_v2_docking_feasibility_report(
    report: V2DockingFeasibilityReport,
) -> str:
    return _canonical_json(v2_docking_feasibility_report_to_dict(report))


def hash_v2_docking_feasibility_report(report: V2DockingFeasibilityReport) -> str:
    return "sha256:" + hashlib.sha256(
        serialize_v2_docking_feasibility_report(report).encode("utf-8")
    ).hexdigest()


def _validate_evidence(evidence: Mapping[str, object]) -> tuple[ContractErrorInfo, ...]:
    if not isinstance(evidence, Mapping):
        return (_error("V2_DOCKING_FEASIBILITY_EVIDENCE_INVALID", "evidence must be an object"),)

    errors: list[ContractErrorInfo] = []
    status = _string(evidence, "feasibility_status", "not_evaluable")
    license_status = _string(evidence, "license_status", "not_applicable")
    cli_status = _string(evidence, "cli_probe_status", "not_attempted")
    api_status = _string(evidence, "api_probe_status", "not_attempted")
    input_support = _format_support(evidence.get("input_format_support"))
    output_support = _format_support(evidence.get("output_format_support"))
    duration = _optional_float(evidence.get("probe_duration_seconds"))

    if status not in FEASIBILITY_STATUSES:
        errors.append(_error("V2_DOCKING_FEASIBILITY_STATUS_UNSUPPORTED", f"unsupported feasibility_status: {status}"))
    if license_status not in LICENSE_STATUSES:
        errors.append(_error("V2_DOCKING_FEASIBILITY_LICENSE_UNSUPPORTED", f"unsupported license_status: {license_status}"))
    if cli_status not in PROBE_STATUSES:
        errors.append(_error("V2_DOCKING_FEASIBILITY_PROBE_STATUS_UNSUPPORTED", f"unsupported cli_probe_status: {cli_status}"))
    if api_status not in PROBE_STATUSES:
        errors.append(_error("V2_DOCKING_FEASIBILITY_PROBE_STATUS_UNSUPPORTED", f"unsupported api_probe_status: {api_status}"))
    if duration is not None and duration < 0:
        errors.append(_error("V2_DOCKING_FEASIBILITY_RUNTIME_INVALID", "probe_duration_seconds must be non-negative"))

    if status == "feasible":
        if license_status not in ("allowed", "restricted", "manual_exempt"):
            errors.append(_error("V2_DOCKING_FEASIBILITY_CLAIM_INVALID", "feasible status requires usable license evidence"))
        if not _optional_string(evidence.get("install_path")):
            errors.append(_error("V2_DOCKING_FEASIBILITY_CLAIM_INVALID", "feasible status requires install_path"))
        if "passed" not in (cli_status, api_status):
            errors.append(_error("V2_DOCKING_FEASIBILITY_CLAIM_INVALID", "feasible status requires a passed CLI or API probe"))
        if input_support["status"] != "supported" or output_support["status"] != "supported":
            errors.append(_error("V2_DOCKING_FEASIBILITY_CLAIM_INVALID", "feasible status requires supported input and output formats"))
        if duration is None:
            errors.append(_error("V2_DOCKING_FEASIBILITY_CLAIM_INVALID", "feasible status requires probe duration evidence"))

    if status == "license_unknown" and license_status != "unknown":
        errors.append(_error("V2_DOCKING_FEASIBILITY_CLAIM_INVALID", "license_unknown status requires license_status=unknown"))
    if status == "failed_probe" and "failed" not in (cli_status, api_status):
        errors.append(_error("V2_DOCKING_FEASIBILITY_CLAIM_INVALID", "failed_probe status requires a failed CLI or API probe"))

    return tuple(errors)


def _format_support(raw: object) -> dict[str, object]:
    if not isinstance(raw, Mapping):
        return {"status": "not_checked", "supported_formats": []}
    status = raw.get("status")
    if status not in FORMAT_SUPPORT_STATUSES:
        status = "not_checked"
    formats = raw.get("supported_formats", ())
    if not isinstance(formats, Sequence) or isinstance(formats, (str, bytes)):
        formats = ()
    return _sort_mapping(
        {
            "status": status,
            "supported_formats": [str(item) for item in formats],
        }
    )


def _envelope(
    payload: Optional[V2DockingFeasibilityReport],
    errors: tuple[ContractErrorInfo, ...],
    evidence: Mapping[str, object],
) -> ContractEnvelope[Optional[V2DockingFeasibilityReport]]:
    return ContractEnvelope(
        payload=payload,
        artifacts=(),
        receipt=ValidationReceipt(
            validator=_VALIDATOR,
            contract_version=V2_DOCKING_FEASIBILITY_CONTRACT_VERSION,
            input_sha256=_sha256_obj(evidence),
            passed=not errors,
            errors=errors,
        ),
        provenance=Provenance(inputs={}),
    )


def _error(code: str, message: str) -> ContractErrorInfo:
    return ContractErrorInfo(code=code, owner="evaluation", message=message)


def _string(mapping: Mapping[str, object], key: str, default: str) -> str:
    value = mapping.get(key)
    if isinstance(value, str) and value:
        return value
    return default


def _optional_string(value: object) -> Optional[str]:
    if isinstance(value, str) and value:
        return value
    return None


def _optional_float(value: object) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _sort_mapping(value: Mapping[str, object]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key in sorted(value):
        item = value[key]
        if isinstance(item, Mapping):
            result[key] = _sort_mapping(item)
        elif isinstance(item, list):
            result[key] = [_sort_value(part) for part in item]
        elif isinstance(item, tuple):
            result[key] = [_sort_value(part) for part in item]
        else:
            result[key] = item
    return result


def _sort_value(value: object) -> object:
    if isinstance(value, Mapping):
        return _sort_mapping(value)
    if isinstance(value, list):
        return [_sort_value(part) for part in value]
    if isinstance(value, tuple):
        return [_sort_value(part) for part in value]
    return value


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_obj(value: object) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json(_sort_value(value)).encode("utf-8")).hexdigest()


__all__ = [
    "V2_DOCKING_FEASIBILITY_CONTRACT_VERSION",
    "V2DockingFeasibilityReport",
    "build_v2_docking_feasibility_report",
    "hash_v2_docking_feasibility_report",
    "serialize_v2_docking_feasibility_report",
    "v2_docking_feasibility_report_to_dict",
]
