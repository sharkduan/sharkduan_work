"""Task 33 split-aware evaluation report construction.

Join generation results to split assignments, compute stratified metrics,
and output deterministic JSON-compatible reports.  No RDKit, torch, or
heavy dependencies.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from covalent_design.contracts.errors import ContractError, ContractErrorInfo
from covalent_design.contracts.types import (
    CONTRACT_VERSION,
    SCHEMA_VERSION,
    ArtifactRef,
    CovalentGenerationResult,
    ValidationReceipt,
)
from covalent_design.contracts.lifecycle import validate_generation_result
from covalent_design.io.artifacts import sha256_file

_VALIDATOR = "covalent_design.evaluation.split_metrics"
_VALID_SPLITS = frozenset({"train", "val", "test", "excluded"})
_PRIMARY_SPLITS = ("train", "val", "test")

_ASSIGNMENT_REQUIRED_FIELDS = (
    "record_id",
    "split",
    "scaffold_key",
    "protein_cluster_id",
    "residue_reaction_family",
    "fallback_reason",
    "manual_review_status",
)

_LEAKAGE_REQUIRED_KEYS = (
    "schema_version",
    "contract_version",
    "role",
    "record_count",
    "train_count",
    "val_count",
    "test_count",
    "excluded_count",
    "fallback_count",
    "fallback_by_reason",
    "manual_review_count",
    "scaffold_overlaps",
    "protein_cluster_overlaps",
    "zero_overlap",
)


# ---------------------------------------------------------------------------
# public types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class JoinedAssignment:
    """One generation result joined to its split-index assignment."""

    result: CovalentGenerationResult
    split: str
    scaffold_key: str | None
    protein_cluster_id: str
    residue_reaction_family: str
    fallback_reason: str | None
    manual_review_status: str | None


@dataclass(frozen=True)
class StratifiedEvaluationSummary:
    """Full stratified evaluation report across splits, families, scaffolds,
    protein clusters, leakage checks, fallback exclusions, and docking."""

    per_split: Mapping[str, Mapping[str, int]]
    per_family: Mapping[str, Mapping[str, int]]
    scaffold_primary_metrics: Mapping[str, object]
    protein_cluster_primary_metrics: Mapping[str, object]
    leakage_report_section: Mapping[str, object]
    excluded_summary: Mapping[str, int]
    fallback_exclusions: Mapping[str, object]
    manual_review_accounting: Mapping[str, int]
    docking_score_eligible_counts: Mapping[str, object] | None


# ---------------------------------------------------------------------------
# load / validate split index
# ---------------------------------------------------------------------------


def load_split_index(path: Path) -> dict[str, object]:
    """Load a split-index JSON file, validate it, and return the parsed dict.

    Raises ContractError on any structural or semantic violation.
    """
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise _error(
            "SPLIT_REPORT_SPLIT_INDEX_INVALID",
            f"Cannot load split index: {exc}",
            str(path),
        ) from exc
    receipt = _validate_split_index(data)
    if not receipt.passed:
        err = receipt.errors[0]
        raise ContractError(
            code=err.code,
            owner=err.owner,
            message=err.message,
            location=err.location,
            details=err.details,
        )
    return data


def validate_split_index_for_evaluation(
    data: dict[str, object],
) -> ValidationReceipt:
    """Validate an already-loaded split-index dict, returning a receipt."""
    return _validate_split_index(data)


# ---------------------------------------------------------------------------
# load / validate leakage report
# ---------------------------------------------------------------------------


def load_leakage_report(path: Path) -> dict[str, object]:
    """Load a leakage-report JSON file and return the parsed dict.

    Does *not* validate structure on load — call
    ``validate_leakage_report_for_evaluation`` separately.
    """
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise _error(
            "SPLIT_REPORT_LEAKAGE_REPORT_INVALID",
            f"Cannot load leakage report: {exc}",
            str(path),
        ) from exc
    return data


def validate_leakage_report_for_evaluation(
    leakage: dict[str, object],
    split_index: dict[str, object],
) -> ValidationReceipt:
    """Validate a leakage-report dict against a validated split index."""
    errors: list[ContractErrorInfo] = []

    if not isinstance(leakage, dict):
        errors.append(
            _info("SPLIT_REPORT_LEAKAGE_REPORT_INVALID", "Leakage report must be a JSON object")
        )
        return _receipt(leakage, errors)

    for key in _LEAKAGE_REQUIRED_KEYS:
        if key not in leakage:
            errors.append(
                _info(
                    "SPLIT_REPORT_LEAKAGE_REPORT_INVALID",
                    f"Leakage report missing required key: {key!r}",
                )
            )

    if errors:
        return _receipt(leakage, errors)

    if leakage.get("schema_version") != SCHEMA_VERSION:
        errors.append(
            _info(
                "SPLIT_REPORT_LEAKAGE_REPORT_INVALID",
                f"schema_version must be {SCHEMA_VERSION!r}",
            )
        )
    if leakage.get("contract_version") != CONTRACT_VERSION:
        errors.append(
            _info(
                "SPLIT_REPORT_LEAKAGE_REPORT_INVALID",
                f"contract_version must be {CONTRACT_VERSION!r}",
            )
        )
    if leakage.get("role") != "leakage_report":
        errors.append(
            _info(
                "SPLIT_REPORT_LEAKAGE_REPORT_INVALID",
                "role must be 'leakage_report'",
            )
        )

    zero_overlap = leakage.get("zero_overlap")
    if not isinstance(zero_overlap, dict):
        errors.append(
            _info(
                "SPLIT_REPORT_LEAKAGE_REPORT_INVALID",
                "zero_overlap must be an object",
            )
        )
    else:
        for key in ("scaffold", "protein_cluster"):
            if not isinstance(zero_overlap.get(key), bool):
                errors.append(
                    _info(
                        "SPLIT_REPORT_LEAKAGE_REPORT_INVALID",
                        f"zero_overlap.{key} must be boolean",
                    )
                )

    # cross-validate counts against split_index
    si_assignments = split_index.get("assignments", [])
    if isinstance(si_assignments, list):
        expected_counts = _count_splits(si_assignments)
        _validate_leakage_count(leakage, "record_count", len(si_assignments), errors)
        for split_name in ("train", "val", "test", "excluded"):
            lk_key = f"{split_name}_count"
            expected = expected_counts.get(split_name, 0)
            _validate_leakage_count(leakage, lk_key, expected, errors)

        fallback_by_reason: dict[str, int] = {}
        manual_review_count = 0
        for assignment in si_assignments:
            if not isinstance(assignment, dict):
                continue
            reason = assignment.get("fallback_reason")
            if isinstance(reason, str) and reason:
                fallback_by_reason[reason] = fallback_by_reason.get(reason, 0) + 1
            review_status = assignment.get("manual_review_status")
            if isinstance(review_status, str) and review_status:
                manual_review_count += 1

        _validate_leakage_count(
            leakage,
            "fallback_count",
            sum(fallback_by_reason.values()),
            errors,
        )
        _validate_leakage_count(
            leakage,
            "manual_review_count",
            manual_review_count,
            errors,
        )

        actual_fallback_by_reason = leakage.get("fallback_by_reason")
        if not isinstance(actual_fallback_by_reason, dict):
            errors.append(
                _info(
                    "SPLIT_REPORT_LEAKAGE_REPORT_INVALID",
                    "fallback_by_reason must be an object",
                )
            )
        elif dict(sorted(actual_fallback_by_reason.items())) != dict(
            sorted(fallback_by_reason.items())
        ):
            errors.append(
                _info(
                    "SPLIT_REPORT_LEAKAGE_REPORT_INVALID",
                    "fallback_by_reason does not match split_index fallback assignments",
                )
            )

    return _receipt(leakage, errors)


# ---------------------------------------------------------------------------
# join results to split assignments
# ---------------------------------------------------------------------------


def join_results_to_split_assignments(
    results: tuple[CovalentGenerationResult, ...],
    split_index: dict[str, object],
) -> tuple[JoinedAssignment, ...]:
    """Join generation results to split-index assignments by request_id == record_id.

    Raises ContractError(code=SPLIT_REPORT_ASSIGNMENT_MISSING) when any result
    has no matching assignment.
    """
    _raise_on_receipt_errors(validate_split_index_for_evaluation(split_index))

    assignments: dict[str, dict[str, object]] = {}
    for a in split_index["assignments"]:
        rid = a["record_id"]
        assignments[rid] = a

    joined: list[JoinedAssignment] = []
    for r in results:
        result_receipt = validate_generation_result(r)
        if not result_receipt.passed:
            err = result_receipt.errors[0]
            raise _error(
                "SPLIT_REPORT_RESULT_VALIDATION_FAILED",
                f"Result failed lifecycle validation: {err.message}",
                f"request_id={r.request_id}",
                details={"source_code": err.code},
            )
        a = assignments.get(r.request_id)
        if a is None:
            raise _error(
                "SPLIT_REPORT_ASSIGNMENT_MISSING",
                f"No split assignment for request_id={r.request_id!r}",
                f"request_id={r.request_id}",
            )
        joined.append(
            JoinedAssignment(
                result=r,
                split=a["split"],
                scaffold_key=a.get("scaffold_key"),
                protein_cluster_id=a["protein_cluster_id"],
                residue_reaction_family=a["residue_reaction_family"],
                fallback_reason=a.get("fallback_reason"),
                manual_review_status=a.get("manual_review_status"),
            )
        )

    return tuple(joined)


# ---------------------------------------------------------------------------
# summarise split results (standalone helper)
# ---------------------------------------------------------------------------


def summarize_split_results(
    results: tuple[CovalentGenerationResult, ...],
    split_index: dict[str, object],
) -> dict[str, object]:
    """Return a per-split lifecycle summary dict without leakage or docking."""
    joined = join_results_to_split_assignments(results, split_index)
    by_split: dict[str, list[JoinedAssignment]] = {s: [] for s in _PRIMARY_SPLITS}
    for j in joined:
        if j.split in by_split:
            by_split[j.split].append(j)

    per_split: dict[str, object] = {}
    for split_name in _PRIMARY_SPLITS:
        per_split[split_name] = {
            "summary": _compute_split_lifecycle(by_split[split_name]),
        }
    return {"per_split": per_split}


# ---------------------------------------------------------------------------
# build stratified evaluation summary
# ---------------------------------------------------------------------------


def build_stratified_evaluation_summary(
    results: tuple[CovalentGenerationResult, ...],
    split_index: dict[str, object],
    leakage: dict[str, object],
    *,
    docking_index: dict[str, object] | None = None,
) -> StratifiedEvaluationSummary:
    """Build the complete stratified evaluation summary.

    Joins results to split assignments, computes per-split and per-family
    lifecycle metrics, scaffold/protein-cluster primary metrics, leakage
    blocking risks, excluded/fallback accounting, and optional docking counts.
    """
    _raise_on_receipt_errors(validate_split_index_for_evaluation(split_index))
    _raise_on_receipt_errors(validate_leakage_report_for_evaluation(leakage, split_index))
    joined = join_results_to_split_assignments(results, split_index)

    # -- per-split lifecycle -------------------------------------------------
    by_split: dict[str, list[JoinedAssignment]] = {s: [] for s in _PRIMARY_SPLITS}
    for j in joined:
        if j.split in by_split:
            by_split[j.split].append(j)

    per_split: dict[str, Mapping[str, int]] = {}
    for split_name in _PRIMARY_SPLITS:
        per_split[split_name] = {
            "summary": _compute_split_lifecycle(by_split[split_name]),
        }

    # -- per-family lifecycle ------------------------------------------------
    by_family: dict[str, list[JoinedAssignment]] = {}
    for j in joined:
        if j.split in _PRIMARY_SPLITS:
            by_family.setdefault(j.residue_reaction_family, []).append(j)

    per_family: dict[str, Mapping[str, int]] = {}
    for family in sorted(by_family):
        per_family[family] = _compute_split_lifecycle(by_family[family])

    # -- scaffold primary metrics (from split_index, not recomputed) ---------
    scaffold_per_split: dict[str, dict[str, object]] = {}
    for split_name in _PRIMARY_SPLITS:
        scaffolds: set[str] = set()
        for j in by_split[split_name]:
            sk = j.scaffold_key
            if isinstance(sk, str) and sk:
                scaffolds.add(sk)
        scaffold_per_split[split_name] = {
            "unique_count": len(scaffolds),
            "values": sorted(scaffolds),
        }
    scaffold_primary_metrics: dict[str, object] = {
        "per_split": scaffold_per_split,
    }

    # -- protein-cluster primary metrics -------------------------------------
    cluster_per_split: dict[str, dict[str, object]] = {}
    for split_name in _PRIMARY_SPLITS:
        clusters: set[str] = set()
        for j in by_split[split_name]:
            clusters.add(j.protein_cluster_id)
        cluster_per_split[split_name] = {
            "unique_count": len(clusters),
            "values": sorted(clusters),
        }
    protein_cluster_primary_metrics: dict[str, object] = {
        "per_split": cluster_per_split,
    }

    # -- leakage report section ----------------------------------------------
    zero_overlap = leakage.get("zero_overlap", {})
    if not isinstance(zero_overlap, dict):
        zero_overlap = {}
    leakage_section: dict[str, object] = {
        "zero_overlap": {
            "scaffold": bool(zero_overlap.get("scaffold", True)),
            "protein_cluster": bool(zero_overlap.get("protein_cluster", True)),
        },
        "blocking_primary_leakage": {
            "scaffold": not bool(zero_overlap.get("scaffold", True)),
            "protein_cluster": not bool(zero_overlap.get("protein_cluster", True)),
        },
    }

    # -- excluded / fallback / manual review accounting ----------------------
    excluded: list[JoinedAssignment] = [
        j for j in joined if j.split == "excluded"
    ]
    excluded_summary = {"excluded_record_count": len(excluded)}

    fallback_by_reason: dict[str, dict[str, int]] = {}
    manual_review: dict[str, int] = {}
    for j in excluded:
        reason = j.fallback_reason
        if isinstance(reason, str) and reason:
            bucket = fallback_by_reason.setdefault(
                reason,
                {"count": 0, "record_ids": []},
            )
            bucket["count"] += 1
            bucket["record_ids"].append(j.result.request_id)

        mrs = j.manual_review_status
        if isinstance(mrs, str) and mrs:
            manual_review[mrs] = manual_review.get(mrs, 0) + 1

    # Also count manual_review across all assignments (not just excluded)
    manual_review_all: dict[str, int] = {}
    for a in split_index.get("assignments", []):
        mrs = a.get("manual_review_status") if isinstance(a, dict) else None
        if isinstance(mrs, str) and mrs:
            manual_review_all[mrs] = manual_review_all.get(mrs, 0) + 1

    fallback_exclusions: dict[str, object] = {
        "by_reason": {
            reason: {
                "count": value["count"],
                "record_ids": sorted(value["record_ids"]),
            }
            for reason, value in sorted(fallback_by_reason.items())
        },
    }

    manual_review_accounting = dict(sorted(manual_review_all.items()))
    if not manual_review_accounting:
        manual_review_accounting = {}

    # -- optional docking index counts ---------------------------------------
    docking_counts: dict[str, object] | None = None
    if docking_index is not None:
        docking_counts = _compute_docking_counts(docking_index, split_index)

    return StratifiedEvaluationSummary(
        per_split=per_split,
        per_family=per_family,
        scaffold_primary_metrics=scaffold_primary_metrics,
        protein_cluster_primary_metrics=protein_cluster_primary_metrics,
        leakage_report_section=leakage_section,
        excluded_summary=excluded_summary,
        fallback_exclusions=fallback_exclusions,
        manual_review_accounting=manual_review_accounting,
        docking_score_eligible_counts=docking_counts,
    )


# ---------------------------------------------------------------------------
# serialization
# ---------------------------------------------------------------------------


def stratified_evaluation_summary_to_dict(
    summary: StratifiedEvaluationSummary,
) -> dict[str, object]:
    """Serialize a StratifiedEvaluationSummary to a deterministic JSON-compatible dict."""
    result: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "contract_version": CONTRACT_VERSION,
        "role": "stratified_evaluation_summary",
        "per_split": {
            split_name: dict(split_data)
            for split_name, split_data in sorted(summary.per_split.items())
        },
        "per_family": {
            family: dict(family_data)
            for family, family_data in sorted(summary.per_family.items())
        },
        "scaffold_primary_metrics": _deep_sort(summary.scaffold_primary_metrics),
        "protein_cluster_primary_metrics": _deep_sort(
            summary.protein_cluster_primary_metrics
        ),
        "leakage_report": _deep_sort(summary.leakage_report_section),
        "excluded_summary": dict(sorted(summary.excluded_summary.items())),
        "fallback_exclusions": _deep_sort(summary.fallback_exclusions),
        "manual_review_accounting": dict(
            sorted(summary.manual_review_accounting.items())
        ),
    }
    if summary.docking_score_eligible_counts is not None:
        result["docking_score_eligible_counts"] = _deep_sort(
            summary.docking_score_eligible_counts
        )
    else:
        result["docking_score_eligible_counts"] = None
    return result


# ---------------------------------------------------------------------------
# atomic writer
# ---------------------------------------------------------------------------


def write_stratified_evaluation_summary(
    summary: StratifiedEvaluationSummary,
    path: Path,
) -> ArtifactRef:
    """Write *summary* to *path* atomically.

    Uses a same-directory tempfile that is fsync'd and os.replace'd into
    place.  Returns an ArtifactRef for the written file.
    """
    if not isinstance(summary, StratifiedEvaluationSummary):
        raise TypeError(
            f"Expected StratifiedEvaluationSummary, got {type(summary).__name__}"
        )

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    payload = stratified_evaluation_summary_to_dict(summary)
    json_text = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)

    fd, tmp_path_str = tempfile.mkstemp(
        suffix=".tmp",
        prefix=".stratified_evaluation_summary",
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

    return ArtifactRef(
        uri=path.name,
        sha256=sha256_file(path),
        format="json",
        schema_version=SCHEMA_VERSION,
        role="stratified_evaluation_summary",
        bytes=path.stat().st_size,
    )


# ===========================================================================
# internal helpers
# ===========================================================================


def _validate_split_index(data: object) -> ValidationReceipt:
    if not isinstance(data, dict):
        return _receipt(
            {},
            [_info("SPLIT_REPORT_SPLIT_INDEX_INVALID", "Split index must be a JSON object")],
        )

    errors: list[ContractErrorInfo] = []

    if data.get("schema_version") != SCHEMA_VERSION:
        errors.append(
            _info(
                "SPLIT_REPORT_SPLIT_INDEX_INVALID",
                f"schema_version must be {SCHEMA_VERSION!r}",
            )
        )
    if data.get("contract_version") != CONTRACT_VERSION:
        errors.append(
            _info(
                "SPLIT_REPORT_SPLIT_INDEX_INVALID",
                f"contract_version must be {CONTRACT_VERSION!r}",
            )
        )
    if data.get("role") != "split_index":
        errors.append(
            _info(
                "SPLIT_REPORT_SPLIT_INDEX_INVALID",
                "role must be 'split_index'",
            )
        )

    assignment_count = data.get("assignment_count")
    assignments = data.get("assignments")

    if isinstance(assignment_count, bool) or not isinstance(assignment_count, int):
        errors.append(
            _info("SPLIT_REPORT_SPLIT_INDEX_INVALID", "assignment_count must be an integer")
        )
    if not isinstance(assignments, list):
        errors.append(
            _info("SPLIT_REPORT_SPLIT_INDEX_INVALID", "assignments must be a list")
        )

    if errors:
        return _receipt(data, errors)

    if assignment_count != len(assignments):
        errors.append(
            _info(
                "SPLIT_REPORT_SPLIT_INDEX_INVALID",
                f"assignment_count ({assignment_count}) != len(assignments) ({len(assignments)})",
            )
        )

    seen_ids: set[str] = set()
    for i, a in enumerate(assignments):
        if not isinstance(a, dict):
            errors.append(
                _info(
                    "SPLIT_REPORT_SPLIT_INDEX_INVALID",
                    f"assignments[{i}] must be an object",
                )
            )
            continue

        record_id = a.get("record_id")
        if isinstance(record_id, str):
            if record_id in seen_ids:
                errors.append(
                    _info(
                        "SPLIT_REPORT_ASSIGNMENT_DUPLICATE",
                        f"Duplicate record_id {record_id!r}",
                    )
                )
            seen_ids.add(record_id)
        else:
            errors.append(
                _info(
                    "SPLIT_REPORT_SPLIT_INDEX_INVALID",
                    f"assignments[{i}].record_id must be a string",
                )
            )

        split = a.get("split")
        if not isinstance(split, str) or split not in _VALID_SPLITS:
            errors.append(
                _info(
                    "SPLIT_REPORT_SPLIT_INDEX_INVALID",
                    f"assignments[{i}].split must be one of train/val/test/excluded, got {split!r}",
                )
            )

        for field in _ASSIGNMENT_REQUIRED_FIELDS:
            if field not in a:
                errors.append(
                    _info(
                        "SPLIT_REPORT_SPLIT_INDEX_INVALID",
                        f"assignments[{i}] missing required field {field!r}",
                    )
                )
                break  # one missing-field error per assignment is enough

    return _receipt(data, errors)


def _count_splits(
    assignments: list[dict[str, object]],
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for a in assignments:
        s = a.get("split")
        if isinstance(s, str):
            counts[s] = counts.get(s, 0) + 1
    return counts


def _validate_leakage_count(
    leakage: dict[str, object],
    key: str,
    expected: int,
    errors: list[ContractErrorInfo],
) -> None:
    actual = leakage.get(key)
    if isinstance(actual, bool) or not isinstance(actual, int):
        errors.append(
            _info(
                "SPLIT_REPORT_LEAKAGE_REPORT_INVALID",
                f"Leakage {key} must be an integer",
            )
        )
        return
    if actual != expected:
        errors.append(
            _info(
                "SPLIT_REPORT_LEAKAGE_REPORT_INVALID",
                f"Leakage {key}={actual} but split_index has {expected}",
            )
        )


def _compute_split_lifecycle(
    entries: list[JoinedAssignment],
) -> dict[str, int]:
    """Compute a full EvaluationSummary-compatible dict for joined results.

    Per-split sampling-system failures are not attributable in Task 33 inputs, so
    each split summary is over attempted result rows only.
    """
    attempted = len(entries)
    valid_internal = 0
    invalid_generated = 0
    exported_valid = 0
    export_failure = 0
    docking_evaluable = 0
    not_docking_evaluable = 0
    docking_not_run = 0
    docking_failed = 0
    docking_succeeded = 0

    for j in entries:
        r = j.result
        # join_results_to_split_assignments validates every row first; these
        # branches are counting only already-accepted lifecycle states.
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

    return {
        "requested_sample_count": attempted,
        "request_validation_error_sample_count": 0,
        "accepted_request_sample_count": attempted,
        "attempted_sample_count": attempted,
        "sampling_system_failure_count": 0,
        "valid_generated_internal_count": valid_internal,
        "invalid_generated_sample_count": invalid_generated,
        "exported_valid_complex_count": exported_valid,
        "valid_export_failure_count": export_failure,
        "docking_evaluable_valid_sample_count": docking_evaluable,
        "valid_but_not_docking_evaluable_sample_count": not_docking_evaluable,
        "docking_not_run_valid_sample_count": docking_not_run,
        "docking_failed_valid_sample_count": docking_failed,
        "successfully_docked_valid_sample_count": docking_succeeded,
    }


def _compute_docking_counts(
    docking_index: dict[str, object],
    split_index: dict[str, object],
) -> dict[str, object]:
    """Count docking entries per split and per family using split_index assignments."""
    record_to_assignment: dict[str, dict[str, object]] = {}
    for a in split_index.get("assignments", []):
        if isinstance(a, dict):
            rid = a.get("record_id")
            if isinstance(rid, str):
                record_to_assignment[rid] = a

    per_split: dict[str, int] = {s: 0 for s in _PRIMARY_SPLITS}
    per_family: dict[str, int] = {}

    entries = docking_index.get("entries", [])
    if isinstance(entries, list):
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            rid = entry.get("request_id")
            if not isinstance(rid, str):
                continue
            a = record_to_assignment.get(rid)
            if a is None:
                continue
            split = a.get("split")
            if isinstance(split, str) and split in _PRIMARY_SPLITS:
                per_split[split] = per_split.get(split, 0) + 1
            family = a.get("residue_reaction_family")
            if isinstance(family, str) and family:
                per_family[family] = per_family.get(family, 0) + 1

    return {
        "per_split": dict(sorted(per_split.items())),
        "per_family": dict(sorted(per_family.items())),
    }


def _deep_sort(d: Mapping[str, object]) -> dict[str, object]:
    """Recursively sort dict keys for deterministic output."""
    result: dict[str, object] = {}
    for key in sorted(d):
        value = d[key]
        if isinstance(value, dict):
            result[key] = _deep_sort(value)
        elif isinstance(value, list):
            result[key] = list(value)
        else:
            result[key] = value
    return result


def _receipt(
    data: object,
    errors: list[ContractErrorInfo],
) -> ValidationReceipt:
    digest = hashlib.sha256(
        json.dumps(data, default=str, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return ValidationReceipt(
        validator=_VALIDATOR,
        contract_version=CONTRACT_VERSION,
        input_sha256=digest,
        passed=not errors,
        errors=tuple(errors),
    )


def _raise_on_receipt_errors(receipt: ValidationReceipt) -> None:
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


def _info(
    code: str,
    message: str,
    location: str | None = None,
    *,
    details: dict[str, object] | None = None,
) -> ContractErrorInfo:
    return ContractErrorInfo(
        code=code,
        owner="evaluation",
        message=message,
        location=location,
        details=details or {},
    )
