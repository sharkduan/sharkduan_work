"""Task 43: V2 license and provenance audit gate.

This module evaluates already-staged Task 41 evidence and, optionally,
already-produced Task 42 record references. It does not download data, execute
conversion, parse raw files, train models, or create artifacts.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping, Optional, Sequence

from covalent_design.contracts.errors import ContractErrorInfo
from covalent_design.contracts.types import (
    ContractEnvelope,
    Provenance,
    SourceIngestRecord,
    ValidationReceipt,
)
from covalent_design.data.v2_intake import V2StagingSummary
from covalent_design.data.v2_manifests import CONTRACT_VERSION

VALIDATOR_NAME = "covalent_design.data.audit_v2_training_eligibility"

LICENSE_STATUS_ALLOWED = "allowed"
LICENSE_STATUS_RESTRICTED = "restricted"
LICENSE_STATUS_BLOCKED = "blocked"
LICENSE_STATUS_UNKNOWN = "unknown"
LICENSE_STATUS_MANUAL_EXEMPT = "manual_exempt"

LICENSE_STATUSES = (
    LICENSE_STATUS_ALLOWED,
    LICENSE_STATUS_RESTRICTED,
    LICENSE_STATUS_BLOCKED,
    LICENSE_STATUS_UNKNOWN,
    LICENSE_STATUS_MANUAL_EXEMPT,
)

MANUAL_EXEMPT_NOTICE = (
    "manual_exempt data has not undergone third-party license verification; "
    "user accepts compliance responsibility"
)


@dataclass(frozen=True)
class SourceLicenseAudit:
    source_name: str
    intake_mode: str
    license_status: str
    license_evidence_ref: str
    restriction_conditions: tuple[str, ...] = ()
    restriction_conditions_satisfied: bool = False
    block_reason: str = ""


@dataclass(frozen=True)
class LicenseGateSourceReport:
    source_name: str
    intake_mode: str
    license_audit_ref: str
    license_status: str
    training_eligible: bool
    reason_codes: tuple[str, ...]
    checksum: str = ""
    manual_path: Optional[str] = None
    source_url: Optional[str] = None
    restriction_conditions: tuple[str, ...] = ()
    notice: str = ""


@dataclass(frozen=True)
class LicenseGateReport:
    sources: tuple[LicenseGateSourceReport, ...]
    status_counts: Mapping[str, int]
    training_eligible_count: int
    blocked_count: int


def load_source_license_audit(path: Path) -> SourceLicenseAudit:
    """Load a deterministic SourceLicenseAudit JSON fixture/file."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return source_license_audit_from_dict(data)


def source_license_audit_from_dict(data: Mapping[str, object]) -> SourceLicenseAudit:
    conditions = data.get("restriction_conditions", ())
    if conditions is None:
        condition_tuple: tuple[str, ...] = ()
    elif isinstance(conditions, str):
        condition_tuple = (conditions,)
    else:
        condition_tuple = tuple(str(item) for item in conditions)  # type: ignore[arg-type]

    return SourceLicenseAudit(
        source_name=str(data.get("source_name", "")),
        intake_mode=str(data.get("intake_mode", "")),
        license_status=str(data.get("license_status", "")),
        license_evidence_ref=str(data.get("license_evidence_ref", "")),
        restriction_conditions=condition_tuple,
        restriction_conditions_satisfied=bool(
            data.get("restriction_conditions_satisfied", False)
        ),
        block_reason=str(data.get("block_reason", "")),
    )


def audit_v2_training_eligibility(
    staged_evidence: Sequence[ContractEnvelope[V2StagingSummary]],
    license_audits: Mapping[str, SourceLicenseAudit | Mapping[str, object]],
    *,
    converted_records: Sequence[SourceIngestRecord] = (),
    approved_local_data_roots: Sequence[Path | str] = (),
) -> ContractEnvelope[LicenseGateReport]:
    """Evaluate whether staged v2 sources may enter training.

    ``converted_records`` is read only for preserved-reference consistency
    checks. This function never runs conversion itself.
    """
    normalized_audits = {
        ref: audit
        if isinstance(audit, SourceLicenseAudit)
        else source_license_audit_from_dict(audit)
        for ref, audit in license_audits.items()
    }
    roots = tuple(Path(root).resolve() for root in approved_local_data_roots)
    errors: list[ContractErrorInfo] = []
    reports: list[LicenseGateSourceReport] = []
    summaries_by_ref: dict[str, V2StagingSummary] = {}

    for envelope in staged_evidence:
        if not envelope.receipt.ok or envelope.payload is None:
            errors.append(
                _error(
                    "V2_LICENSE_STAGING_EVIDENCE_INVALID",
                    "Staging evidence is missing or failed validation",
                    details={
                        "staging_errors": [
                            error.code for error in envelope.receipt.errors
                        ]
                    },
                )
            )
            continue

        summary = envelope.payload
        source_errors: list[ContractErrorInfo] = []
        reason_codes: list[str] = []

        if not summary.license_audit_ref:
            _add_source_error(
                source_errors,
                reason_codes,
                "V2_LICENSE_AUDIT_REF_MISSING",
                "license_audit_ref is required for license gate evaluation",
                source_name=summary.source_name,
            )
        if not summary.checksum:
            _add_source_error(
                source_errors,
                reason_codes,
                "V2_LICENSE_CHECKSUM_MISSING",
                "checksum is required for license gate evaluation",
                source_name=summary.source_name,
            )
        if _provenance_missing(summary):
            _add_source_error(
                source_errors,
                reason_codes,
                "V2_LICENSE_PROVENANCE_MISSING",
                "local path or source URL provenance is required",
                source_name=summary.source_name,
            )
        if summary.intake_mode == "manual" and summary.manual_path and roots:
            if not _is_within_any_root(Path(summary.manual_path), roots):
                _add_source_error(
                    source_errors,
                    reason_codes,
                    "V2_LICENSE_PATH_OUTSIDE_APPROVED_ROOT",
                    "manual_path is outside the approved local data root",
                    source_name=summary.source_name,
                    details={"manual_path": summary.manual_path},
                )

        audit = None
        if summary.license_audit_ref:
            audit = normalized_audits.get(summary.license_audit_ref)
            if audit is None:
                _add_source_error(
                    source_errors,
                    reason_codes,
                    "V2_LICENSE_AUDIT_EVIDENCE_MISSING",
                    "Every staged source requires audit evidence or explicit blocked status",
                    source_name=summary.source_name,
                    details={"license_audit_ref": summary.license_audit_ref},
                )

        license_status = audit.license_status if audit else ""
        training_eligible = False
        notice = ""
        restriction_conditions: tuple[str, ...] = ()

        if audit is not None:
            status_errors, status_reasons, training_eligible, notice = (
                _evaluate_status(summary, audit)
            )
            source_errors.extend(status_errors)
            reason_codes.extend(status_reasons)
            restriction_conditions = audit.restriction_conditions

        if source_errors:
            training_eligible = False
            errors.extend(source_errors)

        reports.append(
            LicenseGateSourceReport(
                source_name=summary.source_name,
                intake_mode=summary.intake_mode,
                license_audit_ref=summary.license_audit_ref or "",
                license_status=license_status,
                training_eligible=training_eligible,
                reason_codes=tuple(_dedupe(reason_codes)),
                checksum=summary.checksum or "",
                manual_path=summary.manual_path,
                source_url=summary.source_url,
                restriction_conditions=restriction_conditions,
                notice=notice,
            )
        )
        if summary.license_audit_ref:
            summaries_by_ref[summary.license_audit_ref] = summary

    errors.extend(_cross_validate_records(converted_records, summaries_by_ref))

    report = _build_report(tuple(reports))
    input_sha256 = _sha256_json(
        {
            "audit_refs": sorted(normalized_audits),
            "converted_record_count": len(converted_records),
            "staged_count": len(staged_evidence),
        }
    )
    return ContractEnvelope(
        payload=report,
        artifacts=(),
        receipt=ValidationReceipt(
            validator=VALIDATOR_NAME,
            contract_version=CONTRACT_VERSION,
            input_sha256=input_sha256,
            ok=not errors,
            errors=tuple(errors),
        ),
        provenance=Provenance(),
    )


def license_gate_report_to_dict(report: LicenseGateReport) -> dict[str, object]:
    """Return a deterministic JSON-compatible report dictionary."""
    return {
        "blocked_count": report.blocked_count,
        "sources": [
            _source_report_to_dict(source)
            for source in sorted(
                report.sources,
                key=lambda item: (
                    item.source_name,
                    item.license_audit_ref,
                    item.license_status,
                ),
            )
        ],
        "status_counts": {
            status: int(report.status_counts.get(status, 0))
            for status in LICENSE_STATUSES
        },
        "training_eligible_count": report.training_eligible_count,
    }


def _source_report_to_dict(source: LicenseGateSourceReport) -> dict[str, object]:
    data = asdict(source)
    data["reason_codes"] = list(source.reason_codes)
    data["restriction_conditions"] = list(source.restriction_conditions)
    return dict(sorted(data.items(), key=lambda item: item[0]))


def _evaluate_status(
    summary: V2StagingSummary,
    audit: SourceLicenseAudit,
) -> tuple[list[ContractErrorInfo], list[str], bool, str]:
    errors: list[ContractErrorInfo] = []
    reasons: list[str] = []
    notice = ""
    status = audit.license_status

    if status not in LICENSE_STATUSES:
        _add_source_error(
            errors,
            reasons,
            "V2_LICENSE_STATUS_UNSUPPORTED",
            f"Unsupported license_status {status!r}",
            source_name=summary.source_name,
            details={"license_status": status, "allowed": LICENSE_STATUSES},
        )
        return errors, reasons, False, notice

    if status == LICENSE_STATUS_ALLOWED:
        return errors, reasons, True, notice

    if status == LICENSE_STATUS_RESTRICTED:
        if audit.restriction_conditions and audit.restriction_conditions_satisfied:
            return errors, reasons, True, notice
        _add_source_error(
            errors,
            reasons,
            "V2_LICENSE_RESTRICTED_CONDITIONS_UNSATISFIED",
            "restricted sources require recorded and satisfied conditions",
            source_name=summary.source_name,
        )
        return errors, reasons, False, notice

    if status == LICENSE_STATUS_BLOCKED:
        _add_source_error(
            errors,
            reasons,
            "V2_LICENSE_STATUS_BLOCKED",
            "blocked license status cannot enter training eligibility",
            source_name=summary.source_name,
        )
        return errors, reasons, False, notice

    if status == LICENSE_STATUS_UNKNOWN:
        _add_source_error(
            errors,
            reasons,
            "V2_LICENSE_STATUS_UNKNOWN_BLOCKED",
            "unknown license status cannot enter training eligibility",
            source_name=summary.source_name,
        )
        return errors, reasons, False, notice

    if status == LICENSE_STATUS_MANUAL_EXEMPT:
        if summary.intake_mode != "manual" or audit.intake_mode == "download":
            _add_source_error(
                errors,
                reasons,
                "V2_LICENSE_MANUAL_EXEMPT_DOWNLOAD",
                "manual_exempt is valid only for manual intake mode",
                source_name=summary.source_name,
            )
            return errors, reasons, False, notice
        return errors, reasons, True, MANUAL_EXEMPT_NOTICE

    raise AssertionError(f"Unhandled license status: {status}")


def _cross_validate_records(
    records: Sequence[SourceIngestRecord],
    summaries_by_ref: Mapping[str, V2StagingSummary],
) -> tuple[ContractErrorInfo, ...]:
    errors: list[ContractErrorInfo] = []
    for record in records:
        record_ref = _record_license_audit_ref(record)
        summary = summaries_by_ref.get(record_ref)
        if summary is None:
            errors.append(
                _error(
                    "V2_LICENSE_CROSS_VALIDATION_LICENSE_AUDIT_REF_MISMATCH",
                    "Converted record license_audit_ref does not match staged evidence",
                    location=record.source_record_id,
                    details={"license_audit_ref": record_ref},
                )
            )
            continue
        if summary.checksum and record.raw_file_sha256 != summary.checksum:
            errors.append(
                _error(
                    "V2_LICENSE_CROSS_VALIDATION_CHECKSUM_MISMATCH",
                    "Converted record checksum does not match staged evidence",
                    location=record.source_record_id,
                    details={
                        "expected": summary.checksum,
                        "actual": record.raw_file_sha256,
                    },
                )
            )
        if summary.manual_path and _normalize_path(record.raw_file_path) != _normalize_path(
            summary.manual_path
        ):
            errors.append(
                _error(
                    "V2_LICENSE_CROSS_VALIDATION_LOCAL_PATH_MISMATCH",
                    "Converted record raw_file_path does not match staged evidence",
                    location=record.source_record_id,
                    details={
                        "expected": summary.manual_path,
                        "actual": record.raw_file_path,
                    },
                )
            )
        record_source_url = _record_source_url(record)
        if summary.source_url and record_source_url != summary.source_url:
            errors.append(
                _error(
                    "V2_LICENSE_CROSS_VALIDATION_SOURCE_PROVENANCE_MISMATCH",
                    "Converted record source provenance does not match staged evidence",
                    location=record.source_record_id,
                    details={
                        "expected": summary.source_url,
                        "actual": record_source_url,
                    },
                )
            )
    return tuple(errors)


def _record_license_audit_ref(record: SourceIngestRecord) -> str:
    value = record.metadata.get("license_audit_ref") or record.lineage.get(
        "license_audit_ref"
    )
    return str(value or "")


def _record_source_url(record: SourceIngestRecord) -> str:
    value = record.metadata.get("source_url") or record.lineage.get("source_url")
    return str(value or "")


def _build_report(sources: tuple[LicenseGateSourceReport, ...]) -> LicenseGateReport:
    counts = {status: 0 for status in LICENSE_STATUSES}
    for source in sources:
        if source.license_status in counts:
            counts[source.license_status] += 1
    return LicenseGateReport(
        sources=tuple(
            sorted(
                sources,
                key=lambda item: (
                    item.source_name,
                    item.license_audit_ref,
                    item.license_status,
                ),
            )
        ),
        status_counts=counts,
        training_eligible_count=sum(1 for source in sources if source.training_eligible),
        blocked_count=sum(1 for source in sources if not source.training_eligible),
    )


def _provenance_missing(summary: V2StagingSummary) -> bool:
    if summary.intake_mode == "manual":
        return not summary.manual_path
    if summary.intake_mode == "download":
        return not summary.source_url
    return True


def _is_within_any_root(path: Path, roots: tuple[Path, ...]) -> bool:
    try:
        resolved = path.resolve()
    except OSError:
        resolved = path.absolute()
    for root in roots:
        try:
            resolved.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def _normalize_path(path: str) -> str:
    return str(Path(path))


def _add_source_error(
    errors: list[ContractErrorInfo],
    reason_codes: list[str],
    code: str,
    message: str,
    *,
    source_name: str,
    details: Optional[Mapping[str, object]] = None,
) -> None:
    errors.append(
        _error(
            code,
            message,
            location=source_name,
            details=details,
        )
    )
    reason_codes.append(code)


def _error(
    code: str,
    message: str,
    *,
    location: Optional[str] = None,
    details: Optional[Mapping[str, object]] = None,
) -> ContractErrorInfo:
    return ContractErrorInfo(
        code=code,
        owner="data",
        message=message,
        location=location,
        details=dict(details or {}),
    )


def _dedupe(items: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(items))


def _sha256_json(data: Mapping[str, object]) -> str:
    text = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


__all__ = [
    "LICENSE_STATUS_ALLOWED",
    "LICENSE_STATUS_BLOCKED",
    "LICENSE_STATUS_MANUAL_EXEMPT",
    "LICENSE_STATUS_RESTRICTED",
    "LICENSE_STATUS_UNKNOWN",
    "LICENSE_STATUSES",
    "LicenseGateReport",
    "LicenseGateSourceReport",
    "MANUAL_EXEMPT_NOTICE",
    "SourceLicenseAudit",
    "audit_v2_training_eligibility",
    "license_gate_report_to_dict",
    "load_source_license_audit",
    "source_license_audit_from_dict",
]
