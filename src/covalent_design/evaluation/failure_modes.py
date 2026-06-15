"""Failure mode report aggregation, serialization, and atomic writer.

Put here: frozen reason-stage mapping, FailureModeReport dataclass,
build/aggregation functions, serialization, and writer.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

from covalent_design.contracts.errors import ContractError
from covalent_design.contracts.types import (
    CONTRACT_VERSION,
    SCHEMA_VERSION,
    ArtifactRef,
    CovalentGenerationResult,
)
from covalent_design.evaluation.validity_metrics import (
    summarize_lifecycle_statuses,
    validate_results_before_aggregation,
)
from covalent_design.io.artifacts import sha256_file

# ---------------------------------------------------------------------------
# frozen reason -> stage mapping
# ---------------------------------------------------------------------------

FROZEN_REASON_STAGE_MAP: Mapping[str, str] = {
    # generation
    "LIGAND_RECONSTRUCTION_FAILED": "generation",
    "LIGAND_CHEMISTRY_INVALID": "generation",
    "NO_COVALENT_EDGE_PREDICTED": "generation",
    "COVALENT_EDGE_BELOW_THRESHOLD": "generation",
    # generation_gate
    "REACTION_FAMILY_RULE_FAIL": "generation_gate",
    "WARHEAD_MATCH_FAIL": "generation_gate",
    "VALENCE_CHECK_FAIL": "generation_gate",
    "GEOMETRY_CHECK_FAIL": "generation_gate",
    "REQUIRED_GATE_STATE_UNAVAILABLE": "generation_gate",
    "UNSUPPORTED_GENERATED_CHEMISTRY": "generation_gate",
    # export
    "COMPLEX_EXPORT_FAILED": "export",
    # docking_eligibility
    "DOCKING_NOT_EVALUABLE": "docking_eligibility",
    # docking_run
    "DOCKING_RUN_FAILED": "docking_run",
}

# ---------------------------------------------------------------------------
# report dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FailureModeReport:
    """Aggregated failure mode report with global and per-family counts."""

    primary_reason_counts: Mapping[str, int] = field(default_factory=dict)
    secondary_reason_counts: Mapping[str, int] = field(default_factory=dict)
    primary_reason_counts_by_family: Mapping[str, Mapping[str, int]] = field(
        default_factory=dict
    )
    secondary_reason_counts_by_family: Mapping[str, Mapping[str, int]] = field(
        default_factory=dict
    )
    primary_reason_counts_by_stage: Mapping[str, Mapping[str, int]] = field(
        default_factory=dict
    )
    secondary_reason_counts_by_stage: Mapping[str, Mapping[str, int]] = field(
        default_factory=dict
    )
    primary_reason_counts_by_family_and_stage: Mapping[
        str, Mapping[str, Mapping[str, int]]
    ] = field(default_factory=dict)
    secondary_reason_counts_by_family_and_stage: Mapping[
        str, Mapping[str, Mapping[str, int]]
    ] = field(default_factory=dict)
    lifecycle_statuses: Mapping[str, int] = field(default_factory=dict)
    evidence: tuple[Mapping[str, object], ...] = ()


# ---------------------------------------------------------------------------
# aggregation / build
# ---------------------------------------------------------------------------


def build_failure_mode_report(
    results: list[CovalentGenerationResult],
) -> FailureModeReport:
    """Validate all rows, then aggregate failure mode statistics.

    Calls validate_results_before_aggregation internally.  If any row is
    corrupt the whole report is rejected — no survivor aggregation.
    """
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

    primary_global: dict[str, int] = {}
    secondary_global: dict[str, int] = {}
    primary_by_family: dict[str, dict[str, int]] = {}
    secondary_by_family: dict[str, dict[str, int]] = {}
    primary_by_stage: dict[str, dict[str, int]] = {}
    secondary_by_stage: dict[str, dict[str, int]] = {}
    primary_by_family_and_stage: dict[str, dict[str, dict[str, int]]] = {}
    secondary_by_family_and_stage: dict[str, dict[str, dict[str, int]]] = {}
    evidence_entries: list[dict[str, object]] = []

    for r in results:
        family = r.residue_reaction_family

        primary = r.primary_failure_reason
        if primary is not None:
            stage = _reason_stage(primary)
            primary_global[primary] = primary_global.get(primary, 0) + 1
            primary_by_family.setdefault(family, {})
            primary_by_family[family][primary] = (
                primary_by_family[family].get(primary, 0) + 1
            )
            _increment_nested(primary_by_stage, stage, primary)
            _increment_family_stage(
                primary_by_family_and_stage, family, stage, primary
            )

        for sec in r.secondary_failure_reasons:
            stage = _reason_stage(sec)
            secondary_global[sec] = secondary_global.get(sec, 0) + 1
            secondary_by_family.setdefault(family, {})
            secondary_by_family[family][sec] = (
                secondary_by_family[family].get(sec, 0) + 1
            )
            _increment_nested(secondary_by_stage, stage, sec)
            _increment_family_stage(
                secondary_by_family_and_stage, family, stage, sec
            )

        if primary is not None:
            evidence_entries.append(
                {
                    "residue_reaction_family": family,
                    "sample_id": r.sample_id,
                    "primary_failure_reason": primary,
                    "primary_failure_stage": _reason_stage(primary),
                    "secondary_failure_reasons": list(r.secondary_failure_reasons),
                    "secondary_failure_stages": [
                        {
                            "reason": reason,
                            "lifecycle_stage": _reason_stage(reason),
                        }
                        for reason in r.secondary_failure_reasons
                    ],
                }
            )

    # deterministic ordering: family -> reason -> sample_id
    evidence_entries.sort(
        key=lambda e: (
            str(e["residue_reaction_family"]),
            str(e["primary_failure_reason"]),
            int(e["sample_id"]),  # type: ignore[arg-type]
        )
    )

    lifecycle_statuses = summarize_lifecycle_statuses(results)

    return FailureModeReport(
        primary_reason_counts=_sorted_dict(primary_global),
        secondary_reason_counts=_sorted_dict(secondary_global),
        primary_reason_counts_by_family=_sorted_nested_dict(primary_by_family),
        secondary_reason_counts_by_family=_sorted_nested_dict(secondary_by_family),
        primary_reason_counts_by_stage=_sorted_nested_dict(primary_by_stage),
        secondary_reason_counts_by_stage=_sorted_nested_dict(secondary_by_stage),
        primary_reason_counts_by_family_and_stage=_sorted_family_stage_dict(
            primary_by_family_and_stage
        ),
        secondary_reason_counts_by_family_and_stage=_sorted_family_stage_dict(
            secondary_by_family_and_stage
        ),
        lifecycle_statuses=lifecycle_statuses,
        evidence=tuple(evidence_entries),
    )


def build_failure_mode_report_from_manifest(
    manifest: Path,
) -> FailureModeReport:
    """Load validated results from a generation-run manifest, then build a
    failure mode report."""
    from covalent_design.evaluation.denominator_accounting import (
        load_validated_results,
    )

    results = load_validated_results(manifest)
    return build_failure_mode_report(results)


# ---------------------------------------------------------------------------
# serialization
# ---------------------------------------------------------------------------


def failure_mode_report_to_dict(report: FailureModeReport) -> dict[str, object]:
    """Serialize a FailureModeReport to a deterministic JSON-compatible dict."""
    return {
        "schema_version": SCHEMA_VERSION,
        "contract_version": CONTRACT_VERSION,
        "role": "failure_mode_report",
        "primary_reason_counts": dict(report.primary_reason_counts),
        "secondary_reason_counts": dict(report.secondary_reason_counts),
        "primary_reason_counts_by_family": {
            fam: dict(counts)
            for fam, counts in report.primary_reason_counts_by_family.items()
        },
        "secondary_reason_counts_by_family": {
            fam: dict(counts)
            for fam, counts in report.secondary_reason_counts_by_family.items()
        },
        "primary_reason_counts_by_stage": {
            stage: dict(counts)
            for stage, counts in report.primary_reason_counts_by_stage.items()
        },
        "secondary_reason_counts_by_stage": {
            stage: dict(counts)
            for stage, counts in report.secondary_reason_counts_by_stage.items()
        },
        "primary_reason_counts_by_family_and_stage": {
            family: {
                stage: dict(counts)
                for stage, counts in stages.items()
            }
            for family, stages in report.primary_reason_counts_by_family_and_stage.items()
        },
        "secondary_reason_counts_by_family_and_stage": {
            family: {
                stage: dict(counts)
                for stage, counts in stages.items()
            }
            for family, stages in report.secondary_reason_counts_by_family_and_stage.items()
        },
        "lifecycle_statuses": dict(report.lifecycle_statuses),
        "evidence": [dict(e) for e in report.evidence],
    }


# ---------------------------------------------------------------------------
# atomic writer
# ---------------------------------------------------------------------------


def write_failure_mode_report(report: FailureModeReport, path: Path) -> ArtifactRef:
    """Write *report* to *path* atomically.

    Uses a same-directory tempfile that is fsync'd and os.replace'd into
    place.  Returns an ArtifactRef for the written file.
    """
    if not isinstance(report, FailureModeReport):
        raise TypeError(
            f"Expected FailureModeReport, got {type(report).__name__}"
        )

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    payload = failure_mode_report_to_dict(report)
    json_text = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)

    fd, tmp_path_str = tempfile.mkstemp(
        suffix=".tmp",
        prefix=".failure_mode_report",
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
        role="failure_mode_report",
        bytes=path.stat().st_size,
    )


# ---------------------------------------------------------------------------
# internal helpers
# ---------------------------------------------------------------------------


def _sorted_dict(d: dict[str, int]) -> dict[str, int]:
    return dict(sorted(d.items()))


def _sorted_nested_dict(
    d: dict[str, dict[str, int]],
) -> dict[str, dict[str, int]]:
    return {fam: _sorted_dict(counts) for fam, counts in sorted(d.items())}


def _sorted_family_stage_dict(
    d: dict[str, dict[str, dict[str, int]]],
) -> dict[str, dict[str, dict[str, int]]]:
    return {
        family: _sorted_nested_dict(stages)
        for family, stages in sorted(d.items())
    }


def _increment_nested(
    counts: dict[str, dict[str, int]],
    outer_key: str,
    reason: str,
) -> None:
    counts.setdefault(outer_key, {})
    counts[outer_key][reason] = counts[outer_key].get(reason, 0) + 1


def _increment_family_stage(
    counts: dict[str, dict[str, dict[str, int]]],
    family: str,
    stage: str,
    reason: str,
) -> None:
    counts.setdefault(family, {})
    _increment_nested(counts[family], stage, reason)


def _reason_stage(reason: str) -> str:
    try:
        return FROZEN_REASON_STAGE_MAP[reason]
    except KeyError as exc:
        raise ContractError(
            code="FAILURE_REPORT_REASON_NOT_MAPPED",
            owner="evaluation",
            message=f"Failure reason has no lifecycle-stage mapping: {reason}",
            location="failure_reason",
            details={"reason": reason},
        ) from exc
