from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from covalent_design.contracts.errors import ContractError
from covalent_design.contracts.types import (
    CONTRACT_VERSION,
    TRAINING_REQUIRED_INPUT_HASH_KEYS,
)
from covalent_design.rules.validate import _parse_minimal_yaml

CHECKPOINT_REQUIRED_INPUT_HASH_KEYS = (
    *TRAINING_REQUIRED_INPUT_HASH_KEYS[:3],
    "training_config_resolved",
    *TRAINING_REQUIRED_INPUT_HASH_KEYS[3:],
)

_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_REQUIRED_FIELDS = (
    "schema_version",
    "contract_version",
    "role",
    "run_id",
    "step",
    "model_contract_version",
    "rule_table_version",
    "input_hashes",
    "model_weights_uri",
    "optimizer_state_uri",
    "bond_type_vocabulary",
)


@dataclass(frozen=True)
class CheckpointMetadata:
    schema_version: str
    contract_version: str
    role: str
    run_id: str
    step: int
    model_contract_version: str
    rule_table_version: str
    input_hashes: dict
    model_weights_uri: str
    optimizer_state_uri: str
    bond_type_vocabulary: tuple


def checkpoint_metadata_to_dict(metadata: CheckpointMetadata) -> dict:
    return {
        "schema_version": metadata.schema_version,
        "contract_version": metadata.contract_version,
        "role": metadata.role,
        "run_id": metadata.run_id,
        "step": metadata.step,
        "model_contract_version": metadata.model_contract_version,
        "rule_table_version": metadata.rule_table_version,
        "input_hashes": dict(metadata.input_hashes),
        "model_weights_uri": metadata.model_weights_uri,
        "optimizer_state_uri": metadata.optimizer_state_uri,
        "bond_type_vocabulary": list(metadata.bond_type_vocabulary),
    }


def write_checkpoint_metadata(path, metadata: CheckpointMetadata) -> Path:
    issues = _structural_issues(metadata)
    if issues:
        raise _error("CHECKPOINT_METADATA_INVALID", "; ".join(issues))
    data = checkpoint_metadata_to_dict(metadata)
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(_yaml_dump(data), encoding="utf-8")
    return output_path


def read_checkpoint_metadata(path, *, expected_contract_version=CONTRACT_VERSION):
    metadata_path = Path(path)
    try:
        data = _parse_minimal_yaml(metadata_path.read_text("utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise _error(
            "CHECKPOINT_METADATA_UNREADABLE",
            f"Cannot read checkpoint metadata: {metadata_path}",
        ) from exc
    if not isinstance(data, dict):
        raise _error("CHECKPOINT_METADATA_INVALID", "Checkpoint metadata must be a mapping")

    missing_fields = [key for key in _REQUIRED_FIELDS if key not in data]
    if missing_fields:
        raise _error(
            "CHECKPOINT_METADATA_MISSING_FIELD",
            f"Missing checkpoint metadata fields: {', '.join(missing_fields)}",
        )

    try:
        metadata = CheckpointMetadata(
            schema_version=str(data["schema_version"]),
            contract_version=str(data["contract_version"]),
            role=str(data["role"]),
            run_id=str(data["run_id"]),
            step=int(data["step"]),
            model_contract_version=str(data["model_contract_version"]),
            rule_table_version=str(data["rule_table_version"]),
            input_hashes=dict(data["input_hashes"]),
            model_weights_uri=str(data["model_weights_uri"]),
            optimizer_state_uri=str(data["optimizer_state_uri"]),
            bond_type_vocabulary=tuple(data["bond_type_vocabulary"]),
        )
    except (TypeError, ValueError) as exc:
        raise _error("CHECKPOINT_METADATA_INVALID", "Invalid checkpoint metadata types") from exc

    warnings = list(_version_warnings(
        metadata.contract_version,
        expected_contract_version,
        "contract_version",
    ))
    warnings.extend(_version_warnings(
        metadata.model_contract_version,
        expected_contract_version,
        "model_contract_version",
    ))
    structural_issues = _structural_issues(metadata)
    if structural_issues:
        raise _error("CHECKPOINT_METADATA_INVALID", "; ".join(structural_issues))

    return metadata, tuple(warnings)


def validate_checkpoint_metadata(
    metadata: CheckpointMetadata, *, expected_contract_version=CONTRACT_VERSION
):
    warnings = list(_version_warnings(
        metadata.contract_version,
        expected_contract_version,
        "contract_version",
    ))
    warnings.extend(_version_warnings(
        metadata.model_contract_version,
        expected_contract_version,
        "model_contract_version",
    ))
    return tuple(warnings) + _structural_issues(metadata)


def _structural_issues(metadata: CheckpointMetadata) -> tuple[str, ...]:
    errors: list[str] = []

    if metadata.schema_version != "1":
        errors.append(f"schema_version must be '1', got {metadata.schema_version!r}")

    if metadata.role != "checkpoint_manifest":
        errors.append(f"role must be 'checkpoint_manifest', got {metadata.role!r}")

    if not metadata.run_id:
        errors.append("run_id must not be empty")

    if metadata.step < 0:
        errors.append("step must be non-negative")

    if len(metadata.bond_type_vocabulary) == 0:
        errors.append("bond_type_vocabulary must not be empty")

    if len(set(metadata.bond_type_vocabulary)) != len(metadata.bond_type_vocabulary):
        errors.append("bond_type_vocabulary contains duplicate entries")

    if metadata.bond_type_vocabulary and metadata.bond_type_vocabulary[0] != "no_edge":
        errors.append("bond_type_vocabulary[0] must be 'no_edge'")

    for key in CHECKPOINT_REQUIRED_INPUT_HASH_KEYS:
        if key not in metadata.input_hashes:
            errors.append(f"input_hashes missing required key: {key!r}")

    for key, value in metadata.input_hashes.items():
        if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
            errors.append(f"input_hashes[{key!r}] must use sha256:<64 lowercase hex>")

    return tuple(errors)


def _version_warnings(version: str, expected: str, field_name: str) -> tuple[str, ...]:
    actual_parts = _parse_version(version, field_name)
    expected_parts = _parse_version(expected, "expected_contract_version")
    if actual_parts[0] != expected_parts[0]:
        raise _error(
            "CHECKPOINT_CONTRACT_MAJOR_VERSION_MISMATCH",
            f"{field_name} major version mismatch: file has {version}, expected {expected}",
        )
    if actual_parts[1] != expected_parts[1]:
        return (
            f"{field_name} minor version mismatch: file has {version}, expected {expected}",
        )
    return ()


def _parse_version(version: str, field_name: str) -> tuple[int, int, int]:
    parts = version.split(".")
    if len(parts) != 3 or any(not part.isdigit() for part in parts):
        raise _error(
            "CHECKPOINT_CONTRACT_VERSION_INVALID",
            f"{field_name} must be MAJOR.MINOR.PATCH, got {version!r}",
        )
    return tuple(int(part) for part in parts)  # type: ignore[return-value]


def _yaml_dump(data: dict) -> str:
    """Serialize checkpoint metadata using the project's small YAML subset."""
    return "\n".join(_yaml_lines(data)) + "\n"


def _yaml_lines(data: dict, indent: int = 0) -> list[str]:
    lines: list[str] = []
    prefix = " " * indent
    for key in sorted(data):
        value = data[key]
        if isinstance(value, dict):
            lines.append(f"{prefix}{key}:")
            lines.extend(_yaml_lines(value, indent + 2))
        elif isinstance(value, (list, tuple)):
            lines.append(f"{prefix}{key}:")
            for item in value:
                lines.append(f"{prefix}  - {_yaml_scalar(item)}")
        else:
            lines.append(f"{prefix}{key}: {_yaml_scalar(value)}")
    return lines


def _yaml_scalar(value: object) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(str(value), ensure_ascii=False)


def _error(code: str, message: str) -> ContractError:
    return ContractError(code=code, owner="training", message=message)
