"""Task 49: V2 training dataset eligibility selection.

This module consumes finalized records and precomputed V2 gate reports. It does
not read raw real-data roots, run model code, compute losses, or create
checkpoints.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Mapping, Optional, Sequence

from covalent_design.contracts.errors import ContractErrorInfo
from covalent_design.contracts.types import (
    CONTRACT_VERSION,
    SCHEMA_VERSION,
    ArtifactRef,
    ContractEnvelope,
    Provenance,
    ValidationReceipt,
)
from covalent_design.io.jsonl import read_jsonl

VALID_SPLIT_NAMES = ("train", "val", "test")
CORE_SPLITS = ("train", "val", "test")
_VALIDATOR = "covalent_design.training.prepare_v2_dataset"


@dataclass(frozen=True)
class V2TrainingDataPolicy:
    """Policy for V2 dataset eligibility gates."""

    first_core_only: bool = True
    exclude_visual_blocked: bool = True
    exclude_q2: bool = False
    accepted_quality_tiers: tuple[str, ...] = ("Q0", "Q1", "Q2")
    allow_manual_exempt: bool = True

    def __post_init__(self) -> None:
        tiers = self.accepted_quality_tiers
        if not isinstance(tiers, tuple):
            object.__setattr__(self, "accepted_quality_tiers", tuple(tiers))
            tiers = tuple(tiers)
        if not tiers:
            raise ValueError("accepted_quality_tiers must not be empty")
        for tier in tiers:
            if not isinstance(tier, str) or not tier:
                raise ValueError("accepted_quality_tiers must contain non-empty strings")

    def to_dict(self) -> dict[str, object]:
        return {
            "first_core_only": self.first_core_only,
            "exclude_visual_blocked": self.exclude_visual_blocked,
            "exclude_q2": self.exclude_q2,
            "accepted_quality_tiers": tuple(self.accepted_quality_tiers),
            "allow_manual_exempt": self.allow_manual_exempt,
        }


@dataclass(frozen=True)
class V2TrainingRecordEntry:
    record_id: str
    residue_reaction_family: str
    quality_tier: str
    visual_check_status: str
    license_status: str
    family_readiness_status: str
    fallback_reason: Optional[str]
    manual_review_status: Optional[str]
    artifact_refs: Mapping[str, ArtifactRef]
    source_name: str = ""
    intake_mode: str = ""


@dataclass(frozen=True)
class V2ExcludedRecord:
    record_id: str
    primary_reason: str
    all_reasons: tuple[str, ...]
    residue_reaction_family: str
    quality_tier: str
    visual_check_status: str
    license_status: str
    family_readiness_status: str
    split_assignment: str
    license_reason_codes: tuple[str, ...] = ()
    source_name: str = ""
    intake_mode: str = ""


@dataclass(frozen=True)
class V2ExclusionSummary:
    input_count: int
    eligible_count: int
    excluded_count: int
    primary_reason_counts: Mapping[str, int]
    license_status_counts: Mapping[str, int] = field(default_factory=dict)
    family_readiness_counts: Mapping[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class V2TrainingDatasetIndex:
    policy: Mapping[str, object]
    split_name: str
    records: tuple[V2TrainingRecordEntry, ...]
    excluded_records: tuple[V2ExcludedRecord, ...]
    exclusion_summary: V2ExclusionSummary
    records_path: str = ""


@dataclass(frozen=True)
class _LicenseEntry:
    license_status: str
    training_eligible: bool
    intake_mode: str
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class _RecordContext:
    row: Mapping[str, object]
    record_id: str
    family: str
    license_ref: str
    source_name: str
    intake_mode: str
    linkage_count: int
    artifact_refs: Mapping[str, ArtifactRef]


def prepare_v2_dataset(
    records_path: object,
    split_index_path: object,
    split_name: str,
    *,
    visual_check_index_path: object,
    quality_report_path: object,
    family_readiness_report_path: object,
    license_gate_report_path: object,
    policy: Optional[V2TrainingDataPolicy] = None,
) -> ContractEnvelope[V2TrainingDatasetIndex]:
    """Build a V2 training dataset index for one split."""
    if policy is None:
        policy = V2TrainingDataPolicy()
    if split_name not in VALID_SPLIT_NAMES:
        return _failed_envelope(
            "V2_DATASET_INVALID_SPLIT_NAME",
            f"split_name must be one of {VALID_SPLIT_NAMES}, got {split_name!r}",
            location=str(records_path),
        )

    loaded = _load_inputs(
        records_path,
        split_index_path,
        visual_check_index_path,
        quality_report_path,
        family_readiness_report_path,
        license_gate_report_path,
    )
    if isinstance(loaded, ContractEnvelope):
        return loaded
    rows, splits, visual, quality, family, licenses = loaded

    eligible: list[V2TrainingRecordEntry] = []
    excluded: list[V2ExcludedRecord] = []
    reason_counts: dict[str, int] = {}
    license_counts: dict[str, int] = {}
    family_counts: dict[str, int] = {}

    for row in rows:
        context = _record_context(row)
        assignment = splits.get(context.record_id, {})
        split_assignment = str(assignment.get("split", ""))
        visual_status = visual.get(context.record_id, "pending")
        quality_tier = quality.get(context.record_id, "Q1")
        license_entry = licenses.get(context.license_ref)
        license_status = license_entry.license_status if license_entry else "missing"
        family_status = family.get(context.family, "missing")
        reasons = _all_exclusion_reasons(
            context,
            split_assignment,
            split_name,
            visual_status,
            quality_tier,
            license_entry,
            family_status,
            policy,
        )
        license_counts[license_status] = license_counts.get(license_status, 0) + 1
        family_counts[family_status] = family_counts.get(family_status, 0) + 1
        if reasons:
            primary = reasons[0]
            reason_counts[primary] = reason_counts.get(primary, 0) + 1
            excluded.append(
                V2ExcludedRecord(
                    record_id=context.record_id,
                    primary_reason=primary,
                    all_reasons=tuple(reasons),
                    residue_reaction_family=context.family,
                    quality_tier=quality_tier,
                    visual_check_status=visual_status,
                    license_status=license_status,
                    family_readiness_status=family_status,
                    split_assignment=split_assignment,
                    license_reason_codes=license_entry.reason_codes if license_entry else (),
                    source_name=context.source_name,
                    intake_mode=context.intake_mode,
                )
            )
            continue
        eligible.append(
            V2TrainingRecordEntry(
                record_id=context.record_id,
                residue_reaction_family=context.family,
                quality_tier=quality_tier,
                visual_check_status=visual_status,
                license_status=license_status,
                family_readiness_status=family_status,
                fallback_reason=assignment.get("fallback_reason"),
                manual_review_status=assignment.get("manual_review_status"),
                artifact_refs=context.artifact_refs,
                source_name=context.source_name,
                intake_mode=context.intake_mode,
            )
        )

    eligible.sort(key=lambda item: item.record_id)
    excluded.sort(key=lambda item: item.record_id)
    reason_counts = dict(sorted(reason_counts.items()))
    summary = V2ExclusionSummary(
        input_count=len(rows),
        eligible_count=len(eligible),
        excluded_count=len(excluded),
        primary_reason_counts=reason_counts,
        license_status_counts=dict(sorted(license_counts.items())),
        family_readiness_counts=dict(sorted(family_counts.items())),
    )
    payload = V2TrainingDatasetIndex(
        policy=policy.to_dict(),
        split_name=split_name,
        records=tuple(eligible),
        excluded_records=tuple(excluded),
        exclusion_summary=summary,
        records_path=str(Path(records_path).resolve()),
    )
    return ContractEnvelope(
        payload=payload,
        artifacts=(),
        receipt=ValidationReceipt(
            validator=_VALIDATOR,
            contract_version=CONTRACT_VERSION,
            input_sha256="",
            passed=True,
        ),
        provenance=Provenance(),
    )


def v2_training_dataset_index_to_dict(index: V2TrainingDatasetIndex) -> dict[str, object]:
    """Return deterministic JSON-compatible dictionary."""
    data = asdict(index)
    data["records"] = [_entry_to_dict(entry) for entry in index.records]
    data["excluded_records"] = [asdict(record) for record in index.excluded_records]
    return data


def _entry_to_dict(entry: V2TrainingRecordEntry) -> dict[str, object]:
    data = asdict(entry)
    data["artifact_refs"] = {
        key: asdict(value)
        for key, value in sorted(entry.artifact_refs.items(), key=lambda item: item[0])
    }
    return data


def _all_exclusion_reasons(
    context: _RecordContext,
    split_assignment: str,
    split_name: str,
    visual_status: str,
    quality_tier: str,
    license_entry: Optional[_LicenseEntry],
    family_status: str,
    policy: V2TrainingDataPolicy,
) -> list[str]:
    reasons: list[str] = []
    if split_assignment in CORE_SPLITS and split_assignment != split_name:
        reasons.append("not_in_this_split")
    elif split_assignment == "excluded":
        reasons.append("hard_excluded_by_split")
    elif not split_assignment:
        reasons.append("missing_split_assignment")

    if license_entry is None:
        reasons.append("excluded_license_audit_missing")
    else:
        status = license_entry.license_status
        if status == "blocked":
            reasons.append("excluded_license_blocked")
        elif status == "unknown":
            reasons.append("excluded_license_unknown")
        elif status == "restricted" and not license_entry.training_eligible:
            reasons.append("excluded_license_restricted_unsatisfied")
        elif status == "manual_exempt":
            report_mode = license_entry.intake_mode
            if not policy.allow_manual_exempt or context.intake_mode != "manual" or report_mode != "manual":
                reasons.append("excluded_manual_exempt_non_manual")
            elif not license_entry.training_eligible:
                reasons.append("excluded_manual_exempt_audit_failed")
        elif not license_entry.training_eligible:
            reasons.append("excluded_license_audit_failed")

    if family_status in ("blocked", "deferred", "partial", "missing"):
        if family_status == "blocked":
            reasons.append("excluded_family_blocked")
        elif family_status == "deferred":
            reasons.append("excluded_family_deferred")
        elif family_status == "partial":
            reasons.append("excluded_family_partial")
        else:
            reasons.append("excluded_family_missing")

    if policy.exclude_visual_blocked and visual_status != "pass":
        reasons.append("excluded_visual_blocked")
    if quality_tier not in policy.accepted_quality_tiers:
        reasons.append("excluded_quality_tier")
    if policy.first_core_only and context.linkage_count > 1:
        reasons.append("excluded_multi_linkage")
    if policy.exclude_q2 and quality_tier == "Q2":
        reasons.append("excluded_q2")
    if not context.artifact_refs:
        reasons.append("excluded_missing_artifact_roles")
    return reasons


def _load_inputs(
    records_path: object,
    split_index_path: object,
    visual_check_index_path: object,
    quality_report_path: object,
    family_readiness_report_path: object,
    license_gate_report_path: object,
) -> tuple[tuple[Mapping[str, object], ...], Mapping[str, Mapping[str, object]], Mapping[str, str], Mapping[str, str], Mapping[str, str], Mapping[str, _LicenseEntry]] | ContractEnvelope[V2TrainingDatasetIndex]:
    record_rows = _read_records(records_path)
    if isinstance(record_rows, ContractEnvelope):
        return record_rows
    split_data = _read_json_object(split_index_path, "V2_DATASET_SPLIT_INDEX_MISSING", "V2_DATASET_SPLIT_INDEX_UNREADABLE")
    if isinstance(split_data, ContractEnvelope):
        return split_data
    visual_data = _read_json_object(visual_check_index_path, "V2_DATASET_VISUAL_INDEX_MISSING", "V2_DATASET_VISUAL_INDEX_UNREADABLE")
    if isinstance(visual_data, ContractEnvelope):
        return visual_data
    quality_data = _read_json_object(quality_report_path, "V2_DATASET_QUALITY_REPORT_MISSING", "V2_DATASET_QUALITY_REPORT_UNREADABLE")
    if isinstance(quality_data, ContractEnvelope):
        return quality_data
    family_data = _read_json_object(family_readiness_report_path, "V2_DATASET_FAMILY_REPORT_MISSING", "V2_DATASET_FAMILY_REPORT_UNREADABLE")
    if isinstance(family_data, ContractEnvelope):
        return family_data
    license_data = _read_json_object(license_gate_report_path, "V2_DATASET_LICENSE_REPORT_MISSING", "V2_DATASET_LICENSE_REPORT_UNREADABLE")
    if isinstance(license_data, ContractEnvelope):
        return license_data
    return (
        record_rows,
        _parse_split_index(split_data),
        _parse_record_statuses(visual_data, "visual_check_status"),
        _parse_record_statuses(quality_data, "quality_tier"),
        _parse_family_report(family_data),
        _parse_license_report(license_data),
    )


def _read_records(path_like: object) -> tuple[Mapping[str, object], ...] | ContractEnvelope[V2TrainingDatasetIndex]:
    path = Path(path_like)
    if not path.exists():
        return _failed_envelope("V2_DATASET_RECORDS_FILE_MISSING", f"records file not found: {path}", location=str(path))
    try:
        return tuple(read_jsonl(path))
    except (OSError, ValueError) as exc:
        return _failed_envelope("V2_DATASET_RECORDS_FILE_UNREADABLE", str(exc), location=str(path))


def _read_json_object(path_like: object, missing_code: str, unreadable_code: str) -> Mapping[str, object] | ContractEnvelope[V2TrainingDatasetIndex]:
    path = Path(path_like)
    if not path.exists():
        return _failed_envelope(missing_code, f"file not found: {path}", location=str(path))
    try:
        data = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError) as exc:
        return _failed_envelope(unreadable_code, str(exc), location=str(path))
    if not isinstance(data, dict):
        return _failed_envelope(unreadable_code, "JSON root must be an object", location=str(path))
    return data


def _parse_split_index(data: Mapping[str, object]) -> Mapping[str, Mapping[str, object]]:
    assignments = data.get("assignments", [])
    result: dict[str, Mapping[str, object]] = {}
    if isinstance(assignments, Sequence) and not isinstance(assignments, (str, bytes)):
        for assignment in assignments:
            if isinstance(assignment, Mapping):
                record_id = str(assignment.get("record_id", ""))
                if record_id:
                    result[record_id] = dict(assignment)
    return result


def _parse_record_statuses(data: Mapping[str, object], field: str) -> Mapping[str, str]:
    result: dict[str, str] = {}
    records = data.get("records")
    if isinstance(records, Sequence) and not isinstance(records, (str, bytes)):
        for item in records:
            if isinstance(item, Mapping):
                record_id = str(item.get("record_id", ""))
                if record_id:
                    result[record_id] = str(item.get(field, ""))
        return result
    for key, value in data.items():
        if isinstance(value, Mapping):
            result[str(key)] = str(value.get(field, ""))
    return result


def _parse_family_report(data: Mapping[str, object]) -> Mapping[str, str]:
    families = data.get("families")
    result: dict[str, str] = {}
    if isinstance(families, Sequence) and not isinstance(families, (str, bytes)):
        for item in families:
            if isinstance(item, Mapping):
                family = str(item.get("family", ""))
                if family:
                    result[family] = str(item.get("status", "missing"))
        return result
    for key, value in data.items():
        result[str(key)] = str(value)
    return result


def _parse_license_report(data: Mapping[str, object]) -> Mapping[str, _LicenseEntry]:
    sources = data.get("sources", [])
    result: dict[str, _LicenseEntry] = {}
    if isinstance(sources, Sequence) and not isinstance(sources, (str, bytes)):
        for item in sources:
            if not isinstance(item, Mapping):
                continue
            ref = str(item.get("license_audit_ref", ""))
            if not ref:
                continue
            reasons = item.get("reason_codes", ())
            result[ref] = _LicenseEntry(
                license_status=str(item.get("license_status", "")),
                training_eligible=bool(item.get("training_eligible", False)),
                intake_mode=str(item.get("intake_mode", "")),
                reason_codes=tuple(str(reason) for reason in reasons) if isinstance(reasons, Sequence) and not isinstance(reasons, (str, bytes)) else (),
            )
    return result


def _record_context(row: Mapping[str, object]) -> _RecordContext:
    record_id = str(row.get("record_id", ""))
    core = row.get("core_labels") if isinstance(row.get("core_labels"), Mapping) else {}
    metadata = row.get("metadata") if isinstance(row.get("metadata"), Mapping) else {}
    artifacts: dict[str, ArtifactRef] = {}
    artifact_rows = row.get("artifacts", ())
    if isinstance(artifact_rows, Sequence) and not isinstance(artifact_rows, (str, bytes)):
        for item in artifact_rows:
            if not isinstance(item, Mapping):
                continue
            ref = ArtifactRef(
                uri=str(item.get("uri", "")),
                sha256=str(item.get("sha256", "")),
                format=str(item.get("format", "")),
                schema_version=str(item.get("schema_version", SCHEMA_VERSION)),
                role=str(item.get("role", "")),
                bytes=int(item.get("bytes", 0) or 0),
            )
            if ref.role:
                artifacts[ref.role] = ref
    linkage_count = metadata.get("linkage_count", 1)
    try:
        linkage_count_int = int(linkage_count)
    except (TypeError, ValueError):
        linkage_count_int = 1
    return _RecordContext(
        row=row,
        record_id=record_id,
        family=str(core.get("residue_reaction_family", "")),
        license_ref=str(metadata.get("license_audit_ref", "")),
        source_name=str(metadata.get("source_name", row.get("source_database", ""))),
        intake_mode=str(metadata.get("intake_mode", "")),
        linkage_count=linkage_count_int,
        artifact_refs=artifacts,
    )


def _failed_envelope(code: str, message: str, location: str = "") -> ContractEnvelope[V2TrainingDatasetIndex]:
    error = ContractErrorInfo(code=code, owner="training", message=message, location=location, details={})
    payload = V2TrainingDatasetIndex(
        policy={},
        split_name="",
        records=(),
        excluded_records=(),
        exclusion_summary=V2ExclusionSummary(
            input_count=0,
            eligible_count=0,
            excluded_count=0,
            primary_reason_counts={},
        ),
    )
    return ContractEnvelope(
        payload=payload,
        artifacts=(),
        receipt=ValidationReceipt(
            validator=_VALIDATOR,
            contract_version=CONTRACT_VERSION,
            input_sha256="",
            passed=False,
            errors=(error,),
        ),
        provenance=Provenance(),
    )


__all__ = [
    "V2ExcludedRecord",
    "V2ExclusionSummary",
    "V2TrainingDataPolicy",
    "V2TrainingDatasetIndex",
    "V2TrainingRecordEntry",
    "prepare_v2_dataset",
    "v2_training_dataset_index_to_dict",
]
