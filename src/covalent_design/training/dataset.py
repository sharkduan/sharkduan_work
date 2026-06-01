"""Task 22: Training dataset preparation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional

from covalent_design.contracts.errors import ContractError
from covalent_design.contracts.types import (
    CONTRACT_VERSION,
    SCHEMA_VERSION,
    ArtifactRef,
    ContractEnvelope,
    ExclusionSummary,
    Provenance,
    TrainingDatasetIndex,
    TrainingRecordEntry,
    ValidationReceipt,
)
from covalent_design.io.jsonl import read_jsonl

_VALIDATOR = "covalent_design.training.prepare_dataset"

VALID_SPLIT_NAMES = ("train", "val", "test")
CORE_SPLITS = ("train", "val", "test")


@dataclass(frozen=True)
class TrainingDataPolicy:
    """Exclusion policy controlling which records enter a training split."""

    first_core_only: bool = True
    exclude_visual_blocked: bool = True
    exclude_q2: bool = False
    accepted_quality_tiers: tuple[str, ...] = ("Q0", "Q1", "Q2")

    def __post_init__(self) -> None:
        tiers = self.accepted_quality_tiers
        if not isinstance(tiers, tuple):
            tiers = tuple(tiers)
            object.__setattr__(self, "accepted_quality_tiers", tiers)
        if not tiers:
            raise ValueError("accepted_quality_tiers must not be empty")
        for tier in tiers:
            if not isinstance(tier, str) or not tier:
                raise ValueError(
                    f"accepted_quality_tiers must contain non-empty strings, "
                    f"got {tier!r}"
                )

    def to_dict(self) -> dict[str, object]:
        return {
            "first_core_only": self.first_core_only,
            "exclude_visual_blocked": self.exclude_visual_blocked,
            "exclude_q2": self.exclude_q2,
            "accepted_quality_tiers": self.accepted_quality_tiers,
        }


def prepare_dataset(
    records_path: object,
    split_index_path: object,
    split_name: str,
    policy: Optional[TrainingDataPolicy] = None,
) -> ContractEnvelope[TrainingDatasetIndex]:
    """Build a ``TrainingDatasetIndex`` for one split.

    Reads ``records.jsonl`` and a ``split_index.json``, applies exclusion
    rules in priority order, and returns an envelope with the eligible
    ``TrainingRecordEntry`` objects.
    """
    if policy is None:
        policy = TrainingDataPolicy()

    rec_path = Path(records_path)
    split_path = Path(split_index_path)

    # -- validate split_name --
    if split_name not in VALID_SPLIT_NAMES:
        return _failed_envelope(
            [
                _training_error(
                    "TRAINING_INVALID_SPLIT_NAME",
                    f"split_name must be one of {VALID_SPLIT_NAMES}, "
                    f"got {split_name!r}",
                    location=str(rec_path),
                )
            ],
            input_sha256="",
        )

    # -- validate records file exists --
    if not rec_path.exists():
        return _failed_envelope(
            [
                _training_error(
                    "TRAINING_RECORDS_FILE_MISSING",
                    f"records file not found: {rec_path}",
                    location=str(rec_path),
                )
            ],
            input_sha256="",
        )

    # -- read records --
    try:
        rows = read_jsonl(rec_path)
    except (ValueError, OSError) as exc:
        return _failed_envelope(
            [
                _training_error(
                    "TRAINING_RECORDS_FILE_UNREADABLE",
                    str(exc),
                    location=str(rec_path),
                )
            ],
            input_sha256="",
        )

    # -- validate and read split index --
    if not split_path.exists():
        return _failed_envelope(
            [
                _training_error(
                    "TRAINING_SPLIT_INDEX_MISSING",
                    f"split index file not found: {split_path}",
                    location=str(split_path),
                )
            ],
            input_sha256="",
        )

    try:
        split_data = json.loads(split_path.read_text("utf-8"))
    except (ValueError, OSError) as exc:
        return _failed_envelope(
            [
                _training_error(
                    "TRAINING_SPLIT_INDEX_UNREADABLE",
                    str(exc),
                    location=str(split_path),
                )
            ],
            input_sha256="",
        )

    input_errors = _validate_input_shapes(rows, split_data, rec_path, split_path)
    if input_errors:
        return _failed_envelope(input_errors)

    # -- build split assignment lookup --
    assignments: dict[str, dict] = {}
    for a in split_data.get("assignments", []):
        assignments[a["record_id"]] = a

    # -- apply exclusion priority and build records --
    included: list[TrainingRecordEntry] = []
    exclusion_reasons: dict[str, int] = {}

    for row in rows:
        record_id = row["record_id"]
        assignment = assignments.get(record_id)

        reason = _determine_exclusion(row, assignment, split_name, policy)
        if reason is not None:
            exclusion_reasons[reason] = exclusion_reasons.get(reason, 0) + 1
            continue

        entry = _build_entry(row, assignment)
        included.append(entry)

    # -- sort deterministically by record_id --
    included.sort(key=lambda e: e.record_id)

    total_accepted = len(rows)
    records_in_split = len(included)
    excluded_by_policy = total_accepted - records_in_split

    # -- only positive reason counts --
    filtered_reasons = {k: v for k, v in exclusion_reasons.items() if v > 0}

    summary = ExclusionSummary(
        total_accepted=total_accepted,
        records_in_split=records_in_split,
        excluded_by_policy=excluded_by_policy,
        exclusion_reasons=filtered_reasons,
    )

    index = TrainingDatasetIndex(
        policy=policy.to_dict(),
        split_name=split_name,
        records=tuple(included),
        excluded_summary=summary,
        records_path=str(rec_path.resolve()),
    )

    receipt = ValidationReceipt(
        validator=_VALIDATOR,
        contract_version=CONTRACT_VERSION,
        input_sha256="",
        passed=True,
    )

    return ContractEnvelope(
        payload=index,
        artifacts=(),
        receipt=receipt,
        provenance=Provenance(),
    )


def _determine_exclusion(
    row: dict,
    assignment: Optional[dict],
    split_name: str,
    policy: TrainingDataPolicy,
) -> Optional[str]:
    """Return the first exclusion reason for *row*, or ``None`` if included."""
    metadata = row.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}

    # Priority 1: not in this split (another core split)
    if assignment is None:
        return "missing_split_assignment"
    assigned_split = assignment.get("split")
    if assigned_split in CORE_SPLITS and assigned_split != split_name:
        return "not_in_this_split"

    # Priority 2: hard excluded by split
    if assigned_split == "excluded":
        return "hard_excluded_by_split"

    # Priority 3: visual blocked
    visual = metadata.get("visual_check_status", "pending")
    if policy.exclude_visual_blocked and visual != "pass":
        return "excluded_visual_blocked"

    # Priority 4: quality tier not accepted
    quality = metadata.get("quality")
    if isinstance(quality, dict):
        tier = quality.get("quality_tier", "Q1")
    else:
        tier = "Q1"
    if tier not in policy.accepted_quality_tiers:
        return "excluded_quality_tier"

    # Priority 5: multi-linkage
    linkage_count = metadata.get("linkage_count", 1)
    if (
        policy.first_core_only
        and isinstance(linkage_count, int)
        and linkage_count > 1
    ):
        return "excluded_multi_linkage"

    # Priority 6: Q2 exclusion
    if policy.exclude_q2 and tier == "Q2":
        return "excluded_q2"

    return None


def _build_entry(
    row: dict,
    assignment: Optional[dict],
) -> TrainingRecordEntry:
    core = row.get("core_labels", {})
    metadata = row.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}

    quality = metadata.get("quality")
    if isinstance(quality, dict):
        tier = quality.get("quality_tier", "Q1")
    else:
        tier = "Q1"

    visual = metadata.get("visual_check_status", "pending")

    residue_family = core.get("residue_reaction_family", "")

    fallback = assignment.get("fallback_reason") if assignment else None
    manual_review = assignment.get("manual_review_status") if assignment else None

    # Build artifact refs keyed by role
    artifact_refs: dict[str, ArtifactRef] = {}
    artifacts_list = row.get("artifacts")
    if isinstance(artifacts_list, list):
        for art in artifacts_list:
            if not isinstance(art, dict):
                continue
            ref = ArtifactRef(
                uri=art["uri"],
                sha256=art["sha256"],
                format=art["format"],
                schema_version=art.get("schema_version", SCHEMA_VERSION),
                role=art.get("role", ""),
                bytes=int(art.get("bytes", 0)),
            )
            if ref.role:
                artifact_refs[ref.role] = ref

    return TrainingRecordEntry(
        record_id=row["record_id"],
        residue_reaction_family=residue_family,
        quality_tier=tier,
        visual_check_status=visual,
        fallback_reason=fallback,
        manual_review_status=manual_review,
        artifact_refs=artifact_refs,
    )


def _training_error(
    code: str,
    message: str,
    location: str = "",
    details: Optional[dict] = None,
) -> ContractError:
    return ContractError(
        code=code,
        owner="training",
        message=message,
        location=location,
        details=details or {},
    )


def _validate_input_shapes(
    rows: tuple[dict[str, object], ...],
    split_data: object,
    records_path: Path,
    split_path: Path,
) -> list[ContractError]:
    errors: list[ContractError] = []
    if not isinstance(split_data, dict):
        return [
            _training_error(
                "TRAINING_SPLIT_INDEX_INVALID",
                "split index root must be an object",
                location=str(split_path),
            )
        ]
    assignments = split_data.get("assignments")
    if not isinstance(assignments, list):
        return [
            _training_error(
                "TRAINING_SPLIT_INDEX_INVALID",
                "split index assignments must be a list",
                location=str(split_path),
            )
        ]
    for index, assignment in enumerate(assignments):
        if not isinstance(assignment, dict):
            errors.append(
                _training_error(
                    "TRAINING_SPLIT_ASSIGNMENT_INVALID",
                    "split assignment must be an object",
                    location=f"{split_path}:assignments[{index}]",
                )
            )
            continue
        if not isinstance(assignment.get("record_id"), str) or not assignment["record_id"]:
            errors.append(
                _training_error(
                    "TRAINING_SPLIT_ASSIGNMENT_INVALID",
                    "split assignment record_id must be a non-empty string",
                    location=f"{split_path}:assignments[{index}]",
                )
            )
        assigned_split = assignment.get("split")
        if not isinstance(assigned_split, str):
            errors.append(
                _training_error(
                    "TRAINING_SPLIT_ASSIGNMENT_INVALID",
                    "split assignment split must be a string",
                    location=f"{split_path}:assignments[{index}]",
                )
            )
        elif assigned_split not in (*CORE_SPLITS, "excluded"):
            errors.append(
                _training_error(
                    "TRAINING_SPLIT_ASSIGNMENT_INVALID",
                    "split assignment split must be train, val, test, or excluded",
                    location=f"{split_path}:assignments[{index}]",
                )
            )

    for index, row in enumerate(rows):
        location = f"{records_path}:line {index + 1}"
        record_id = row.get("record_id")
        if not isinstance(record_id, str) or not record_id:
            errors.append(
                _training_error(
                    "TRAINING_RECORD_INVALID",
                    "record_id must be a non-empty string",
                    location=location,
                )
            )
        if "core_labels" in row and not isinstance(row["core_labels"], dict):
            errors.append(
                _training_error(
                    "TRAINING_RECORD_INVALID",
                    "core_labels must be an object",
                    location=location,
                )
            )
        if "metadata" in row and not isinstance(row["metadata"], dict):
            errors.append(
                _training_error(
                    "TRAINING_RECORD_INVALID",
                    "metadata must be an object",
                    location=location,
                )
            )
        artifacts = row.get("artifacts")
        if not isinstance(artifacts, list):
            errors.append(
                _training_error(
                    "TRAINING_RECORD_INVALID",
                    "artifacts must be a list",
                    location=location,
                )
            )
            continue
        for artifact_index, artifact in enumerate(artifacts):
            location = f"{records_path}:line {index + 1}:artifacts[{artifact_index}]"
            if not isinstance(artifact, dict):
                errors.append(
                    _training_error(
                        "TRAINING_ARTIFACT_REF_INVALID",
                        "artifact entry must be an object",
                        location=location,
                    )
                )
                continue
            for key in ("uri", "sha256", "format", "role"):
                if not isinstance(artifact.get(key), str) or not artifact[key]:
                    errors.append(
                        _training_error(
                            "TRAINING_ARTIFACT_REF_INVALID",
                            f"artifact {key} must be a non-empty string",
                            location=location,
                        )
                    )
            if "bytes" in artifact and not isinstance(artifact["bytes"], int):
                errors.append(
                    _training_error(
                        "TRAINING_ARTIFACT_REF_INVALID",
                        "artifact bytes must be an int when present",
                        location=location,
                    )
                )
            if "schema_version" in artifact and not isinstance(
                artifact["schema_version"], str
            ):
                errors.append(
                    _training_error(
                        "TRAINING_ARTIFACT_REF_INVALID",
                        "artifact schema_version must be a string when present",
                        location=location,
                    )
                )
    return errors


def _failed_envelope(
    errors: list[ContractError],
    input_sha256: str = "",
) -> ContractEnvelope[TrainingDatasetIndex]:
    error_infos = tuple(e.to_info() for e in errors)

    receipt = ValidationReceipt(
        validator=_VALIDATOR,
        contract_version=CONTRACT_VERSION,
        input_sha256=input_sha256,
        passed=False,
        errors=error_infos,
    )

    empty_index = TrainingDatasetIndex(
        policy={},
        split_name="",
        records=(),
        excluded_summary=ExclusionSummary(
            total_accepted=0,
            records_in_split=0,
            excluded_by_policy=0,
            exclusion_reasons={},
        ),
    )

    return ContractEnvelope(
        payload=empty_index,
        artifacts=(),
        receipt=receipt,
        provenance=Provenance(),
    )
