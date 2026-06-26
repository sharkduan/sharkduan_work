"""Task 51 V2 checkpoint and experiment manifest contracts.

The module is intentionally schema-only.  It records deterministic provenance
for later training outputs without starting training or creating checkpoint
payload artifacts.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Optional

from covalent_design.contracts.errors import ContractErrorInfo
from covalent_design.contracts.types import (
    CONTRACT_VERSION,
    SCHEMA_VERSION,
    ContractEnvelope,
    Provenance,
    ValidationReceipt,
)

VALIDATOR_NAME = "covalent_design.training.v2_manifests"
ROLE_V2_EXPERIMENT_MANIFEST = "v2_checkpoint_experiment_manifest"
DEPENDENCY_LOCK_AVAILABLE = "available"
DEPENDENCY_LOCK_NOT_AVAILABLE = "not_available"
BASELINE_MODE_PMDM = "pmdm"
BASELINE_MODE_NON_PMDM = "non_pmdm_baseline"
V2_MODEL_CONTRACT_VERSION = "v2-beta"

V2_REQUIRED_DATA_HASH_KEYS = (
    "records_jsonl",
    "split_index",
    "quality_report",
    "visual_check_index",
    "license_gate_report",
)

_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_DEPENDENCY_LOCK_STATUSES = (DEPENDENCY_LOCK_AVAILABLE, DEPENDENCY_LOCK_NOT_AVAILABLE)
_BASELINE_MODES = (BASELINE_MODE_PMDM, BASELINE_MODE_NON_PMDM)

V2_MANIFEST_ENVIRONMENT_HASH_MISSING = "V2_MANIFEST_ENVIRONMENT_HASH_MISSING"
V2_MANIFEST_DEPENDENCY_LOCK_PROVENANCE_MISSING = "V2_MANIFEST_DEPENDENCY_LOCK_PROVENANCE_MISSING"
V2_MANIFEST_DEPENDENCY_LOCK_HASH_MISSING = "V2_MANIFEST_DEPENDENCY_LOCK_HASH_MISSING"
V2_MANIFEST_DATA_HASH_MISSING = "V2_MANIFEST_DATA_HASH_MISSING"
V2_MANIFEST_DATASET_INDEX_HASH_MISSING = "V2_MANIFEST_DATASET_INDEX_HASH_MISSING"
V2_MANIFEST_FAMILY_READINESS_HASH_MISSING = "V2_MANIFEST_FAMILY_READINESS_HASH_MISSING"
V2_MANIFEST_TRAINING_CONFIG_HASH_MISSING = "V2_MANIFEST_TRAINING_CONFIG_HASH_MISSING"
V2_MANIFEST_TRAINING_SUMMARY_HASH_MISSING = "V2_MANIFEST_TRAINING_SUMMARY_HASH_MISSING"
V2_MANIFEST_TRAINING_SUMMARY_REF_MISSING = "V2_MANIFEST_TRAINING_SUMMARY_REF_MISSING"
V2_MANIFEST_CHECKPOINT_REFS_MISSING = "V2_MANIFEST_CHECKPOINT_REFS_MISSING"
V2_MANIFEST_BASELINE_MODE_MISSING = "V2_MANIFEST_BASELINE_MODE_MISSING"
V2_MANIFEST_BASELINE_MODE_UNSUPPORTED = "V2_MANIFEST_BASELINE_MODE_UNSUPPORTED"
V2_MANIFEST_BASELINE_PMDM_MISMATCH = "V2_MANIFEST_BASELINE_PMDM_MISMATCH"
V2_MANIFEST_PMDM_UNAVAILABLE_SUCCESS = "V2_MANIFEST_PMDM_UNAVAILABLE_SUCCESS"
V2_MANIFEST_HASH_FORMAT_INVALID = "V2_MANIFEST_HASH_FORMAT_INVALID"
V2_MANIFEST_DEPENDENCY_LOCK_STATUS_INVALID = "V2_MANIFEST_DEPENDENCY_LOCK_STATUS_INVALID"
V2_MANIFEST_DEPENDENCY_LOCK_REASON_MISSING = "V2_MANIFEST_DEPENDENCY_LOCK_REASON_MISSING"
V2_MANIFEST_CHECKPOINT_REF_INVALID = "V2_MANIFEST_CHECKPOINT_REF_INVALID"


@dataclass(frozen=True)
class V2DependencyLockProvenance:
    """Dependency lock provenance without pretending an absent lock was verified."""

    status: str
    lock_hash: Optional[str] = None
    uri: str = ""
    format: str = ""
    reason: str = ""


@dataclass(frozen=True)
class V2CheckpointRef:
    """Metadata reference for a later checkpoint output, not checkpoint content."""

    checkpoint_id: str
    checkpoint_uri: str
    step: int
    sha256: Optional[str] = None
    format: str = "manifest_ref"
    selected: bool = False


@dataclass(frozen=True)
class V2CheckpointExperimentManifest:
    """Deterministic V2 manifest binding run inputs and output references."""

    manifest_id: str
    environment_hash: str
    dependency_lock: V2DependencyLockProvenance
    data_hashes: Mapping[str, str]
    dataset_index_hash: str
    family_readiness_hash: str
    training_config_hash: str
    training_summary_hash: str
    training_summary_ref: str
    checkpoint_refs: tuple[V2CheckpointRef, ...]
    baseline_mode: str
    is_pmdm: bool
    pmdm_status: str = "not_required"
    run_id: str = ""
    model_contract_version: str = V2_MODEL_CONTRACT_VERSION
    schema_version: str = SCHEMA_VERSION
    contract_version: str = CONTRACT_VERSION
    role: str = ROLE_V2_EXPERIMENT_MANIFEST
    warnings: tuple[str, ...] = ()
    diagnostics: tuple[Mapping[str, object], ...] = field(default_factory=tuple)


def v2_hash_bytes(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def v2_hash_file(path: str | Path) -> str:
    return v2_hash_bytes(Path(path).read_bytes())


def v2_hash_object(value: object) -> str:
    return v2_hash_bytes(_canonical_json(value).encode("utf-8"))


def build_v2_checkpoint_experiment_manifest(
    *,
    manifest_id: str,
    environment_hash: str,
    dependency_lock: V2DependencyLockProvenance,
    data_hashes: Mapping[str, str],
    dataset_index_hash: str,
    family_readiness_hash: str,
    training_config_hash: str,
    training_summary_hash: str,
    training_summary_ref: str,
    checkpoint_refs: tuple[V2CheckpointRef, ...],
    baseline_mode: str,
    is_pmdm: bool,
    pmdm_status: str = "not_required",
    run_id: str = "",
    model_contract_version: str = V2_MODEL_CONTRACT_VERSION,
    warnings: tuple[str, ...] = (),
    diagnostics: tuple[Mapping[str, object], ...] = (),
) -> ContractEnvelope[V2CheckpointExperimentManifest]:
    manifest = V2CheckpointExperimentManifest(
        manifest_id=manifest_id,
        environment_hash=environment_hash,
        dependency_lock=dependency_lock,
        data_hashes=dict(data_hashes),
        dataset_index_hash=dataset_index_hash,
        family_readiness_hash=family_readiness_hash,
        training_config_hash=training_config_hash,
        training_summary_hash=training_summary_hash,
        training_summary_ref=training_summary_ref,
        checkpoint_refs=tuple(checkpoint_refs),
        baseline_mode=baseline_mode,
        is_pmdm=is_pmdm,
        pmdm_status=pmdm_status,
        run_id=run_id,
        model_contract_version=model_contract_version,
        warnings=tuple(warnings),
        diagnostics=tuple(diagnostics),
    )
    return _envelope(manifest)


def v2_checkpoint_experiment_manifest_to_dict(
    manifest: V2CheckpointExperimentManifest,
) -> dict[str, object]:
    return _sorted_mapping(
        {
            "schema_version": manifest.schema_version,
            "contract_version": manifest.contract_version,
            "role": manifest.role,
            "manifest_id": manifest.manifest_id,
            "run_id": manifest.run_id,
            "model_contract_version": manifest.model_contract_version,
            "environment_hash": manifest.environment_hash,
            "dependency_lock": _dependency_lock_to_dict(manifest.dependency_lock),
            "data_hashes": dict(manifest.data_hashes),
            "dataset_index_hash": manifest.dataset_index_hash,
            "family_readiness_hash": manifest.family_readiness_hash,
            "training_config_hash": manifest.training_config_hash,
            "training_summary_hash": manifest.training_summary_hash,
            "training_summary_ref": manifest.training_summary_ref,
            "checkpoint_refs": [
                _checkpoint_ref_to_dict(ref) for ref in manifest.checkpoint_refs
            ],
            "baseline_mode": manifest.baseline_mode,
            "is_pmdm": manifest.is_pmdm,
            "pmdm_status": manifest.pmdm_status,
            "warnings": list(manifest.warnings),
            "diagnostics": [dict(item) for item in manifest.diagnostics],
        }
    )


def serialize_v2_checkpoint_experiment_manifest(
    manifest: V2CheckpointExperimentManifest,
) -> str:
    return _canonical_json(v2_checkpoint_experiment_manifest_to_dict(manifest))


def hash_v2_checkpoint_experiment_manifest(
    manifest: V2CheckpointExperimentManifest,
) -> str:
    return v2_hash_bytes(serialize_v2_checkpoint_experiment_manifest(manifest).encode("utf-8"))


def validate_v2_checkpoint_experiment_manifest(
    manifest: V2CheckpointExperimentManifest,
) -> ValidationReceipt:
    errors = tuple(_validate_manifest(manifest))
    return ValidationReceipt(
        validator=VALIDATOR_NAME,
        contract_version=CONTRACT_VERSION,
        input_sha256=hashlib.sha256(
            serialize_v2_checkpoint_experiment_manifest(manifest).encode("utf-8")
        ).hexdigest(),
        passed=not errors,
        errors=errors,
    )


def _envelope(
    manifest: V2CheckpointExperimentManifest,
) -> ContractEnvelope[V2CheckpointExperimentManifest]:
    receipt = validate_v2_checkpoint_experiment_manifest(manifest)
    return ContractEnvelope(
        payload=manifest,
        artifacts=(),
        receipt=receipt,
        provenance=Provenance(),
    )


def _validate_manifest(
    manifest: V2CheckpointExperimentManifest,
) -> list[ContractErrorInfo]:
    errors: list[ContractErrorInfo] = []
    if not manifest.environment_hash:
        errors.append(_error(V2_MANIFEST_ENVIRONMENT_HASH_MISSING, "environment_hash is required"))
    elif not _valid_hash(manifest.environment_hash):
        errors.append(_hash_error("environment_hash"))

    errors.extend(_validate_baseline_fields(manifest))
    errors.extend(_validate_dependency_lock(manifest.dependency_lock, manifest.is_pmdm))

    for key in V2_REQUIRED_DATA_HASH_KEYS:
        value = manifest.data_hashes.get(key)
        if not value:
            errors.append(
                _error(
                    V2_MANIFEST_DATA_HASH_MISSING,
                    f"data_hashes missing required key: {key}",
                    f"data_hashes.{key}",
                    {"key": key},
                )
            )
        elif not _valid_hash(value):
            errors.append(_hash_error(f"data_hashes.{key}"))
    for key, value in sorted(manifest.data_hashes.items()):
        if key in V2_REQUIRED_DATA_HASH_KEYS:
            continue
        if value and not _valid_hash(value):
            errors.append(_hash_error(f"data_hashes.{key}"))

    errors.extend(
        _required_hash_errors(
            (
                ("dataset_index_hash", manifest.dataset_index_hash, V2_MANIFEST_DATASET_INDEX_HASH_MISSING),
                ("family_readiness_hash", manifest.family_readiness_hash, V2_MANIFEST_FAMILY_READINESS_HASH_MISSING),
                ("training_config_hash", manifest.training_config_hash, V2_MANIFEST_TRAINING_CONFIG_HASH_MISSING),
                ("training_summary_hash", manifest.training_summary_hash, V2_MANIFEST_TRAINING_SUMMARY_HASH_MISSING),
            )
        )
    )

    if not manifest.training_summary_ref:
        errors.append(
            _error(
                V2_MANIFEST_TRAINING_SUMMARY_REF_MISSING,
                "training_summary_ref is required",
                "training_summary_ref",
            )
        )

    if not manifest.checkpoint_refs:
        errors.append(_error(V2_MANIFEST_CHECKPOINT_REFS_MISSING, "checkpoint_refs is required"))
    for index, ref in enumerate(manifest.checkpoint_refs):
        errors.extend(_validate_checkpoint_ref(ref, index))

    return errors


def _validate_dependency_lock(
    lock: Optional[V2DependencyLockProvenance],
    is_pmdm: bool,
) -> list[ContractErrorInfo]:
    if lock is None:
        return [
            _error(
                V2_MANIFEST_DEPENDENCY_LOCK_PROVENANCE_MISSING,
                "dependency_lock provenance is required",
                "dependency_lock",
            )
        ]
    errors: list[ContractErrorInfo] = []
    if lock.status not in _DEPENDENCY_LOCK_STATUSES:
        errors.append(
            _error(
                V2_MANIFEST_DEPENDENCY_LOCK_STATUS_INVALID,
                f"unsupported dependency lock status: {lock.status!r}",
                "dependency_lock.status",
            )
        )
    if lock.status == DEPENDENCY_LOCK_AVAILABLE:
        if not lock.lock_hash:
            errors.append(
                _error(
                    V2_MANIFEST_DEPENDENCY_LOCK_HASH_MISSING,
                    "available dependency lock requires lock_hash",
                    "dependency_lock.lock_hash",
                )
            )
        elif not _valid_hash(lock.lock_hash):
            errors.append(_hash_error("dependency_lock.lock_hash"))
    if lock.status == DEPENDENCY_LOCK_NOT_AVAILABLE and not lock.reason:
        errors.append(
            _error(
                V2_MANIFEST_DEPENDENCY_LOCK_REASON_MISSING,
                "not_available dependency lock requires reason",
                "dependency_lock.reason",
            )
        )
    if is_pmdm and lock.status != DEPENDENCY_LOCK_AVAILABLE:
        errors.append(
            _error(
                V2_MANIFEST_DEPENDENCY_LOCK_HASH_MISSING,
                "PMDM manifests require an available dependency lock hash",
                "dependency_lock.lock_hash",
            )
        )
    return errors


def _validate_checkpoint_ref(
    ref: V2CheckpointRef,
    index: int,
) -> list[ContractErrorInfo]:
    errors: list[ContractErrorInfo] = []
    prefix = f"checkpoint_refs.{index}"
    if not ref.checkpoint_id:
        errors.append(_error(V2_MANIFEST_CHECKPOINT_REF_INVALID, "checkpoint_id is required", prefix))
    if not ref.checkpoint_uri:
        errors.append(_error(V2_MANIFEST_CHECKPOINT_REF_INVALID, "checkpoint_uri is required", prefix))
    if ref.step < 0:
        errors.append(_error(V2_MANIFEST_CHECKPOINT_REF_INVALID, "step must be non-negative", prefix))
    if ref.sha256 is not None and not _valid_hash(ref.sha256):
        errors.append(_hash_error(f"{prefix}.sha256"))
    return errors


def _validate_baseline_fields(
    manifest: V2CheckpointExperimentManifest,
) -> list[ContractErrorInfo]:
    errors: list[ContractErrorInfo] = []
    if not manifest.baseline_mode:
        errors.append(_error(V2_MANIFEST_BASELINE_MODE_MISSING, "baseline_mode is required"))
        return errors
    if manifest.baseline_mode not in _BASELINE_MODES:
        errors.append(
            _error(
                V2_MANIFEST_BASELINE_MODE_UNSUPPORTED,
                f"unsupported baseline_mode: {manifest.baseline_mode!r}",
                "baseline_mode",
            )
        )
        return errors
    if manifest.baseline_mode == BASELINE_MODE_NON_PMDM and manifest.is_pmdm:
        errors.append(
            _error(
                V2_MANIFEST_BASELINE_PMDM_MISMATCH,
                "non_pmdm_baseline requires is_pmdm=false",
                "is_pmdm",
            )
        )
    if manifest.baseline_mode == BASELINE_MODE_PMDM and not manifest.is_pmdm:
        errors.append(
            _error(
                V2_MANIFEST_BASELINE_PMDM_MISMATCH,
                "pmdm baseline_mode requires is_pmdm=true",
                "is_pmdm",
            )
        )
    if (
        manifest.baseline_mode == BASELINE_MODE_PMDM
        and manifest.pmdm_status in ("unavailable", "blocked", "license_unknown")
    ):
        errors.append(
            _error(
                V2_MANIFEST_PMDM_UNAVAILABLE_SUCCESS,
                "unavailable PMDM cannot be recorded as successful PMDM checkpoint",
                "pmdm_status",
            )
        )
    return errors


def _required_hash_errors(
    fields: tuple[tuple[str, str, str], ...],
) -> list[ContractErrorInfo]:
    errors: list[ContractErrorInfo] = []
    for location, value, missing_code in fields:
        if not value:
            errors.append(_error(missing_code, f"{location} is required", location))
        elif not _valid_hash(value):
            errors.append(_hash_error(location))
    return errors


def _checkpoint_ref_to_dict(ref: V2CheckpointRef) -> dict[str, object]:
    return _sorted_mapping(
        {
            "checkpoint_id": ref.checkpoint_id,
            "checkpoint_uri": ref.checkpoint_uri,
            "step": ref.step,
            "sha256": ref.sha256,
            "format": ref.format,
            "selected": ref.selected,
        }
    )


def _dependency_lock_to_dict(lock: Optional[V2DependencyLockProvenance]) -> Optional[dict[str, object]]:
    if lock is None:
        return None
    return _sorted_mapping(
        {
            "status": lock.status,
            "lock_hash": lock.lock_hash,
            "uri": lock.uri,
            "format": lock.format,
            "reason": lock.reason,
        }
    )


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sorted_mapping(value: Mapping[str, object]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, item in sorted(value.items(), key=lambda pair: pair[0]):
        if isinstance(item, Mapping):
            result[key] = _sorted_mapping({str(k): v for k, v in item.items()})
        elif isinstance(item, tuple):
            result[key] = [
                _sorted_mapping(x) if isinstance(x, Mapping) else x for x in item
            ]
        elif isinstance(item, list):
            result[key] = [
                _sorted_mapping(x) if isinstance(x, Mapping) else x for x in item
            ]
        else:
            result[key] = item
    return result


def _valid_hash(value: object) -> bool:
    return isinstance(value, str) and bool(_SHA256_RE.fullmatch(value))


def _hash_error(location: str) -> ContractErrorInfo:
    return _error(
        V2_MANIFEST_HASH_FORMAT_INVALID,
        "hash values must use sha256:<64 lowercase hex>",
        location,
    )


def _error(
    code: str,
    message: str,
    location: str = "",
    details: Optional[Mapping[str, object]] = None,
) -> ContractErrorInfo:
    return ContractErrorInfo(
        code=code,
        owner="training",
        message=message,
        location=location,
        details=details or {},
    )


__all__ = [
    "BASELINE_MODE_NON_PMDM",
    "BASELINE_MODE_PMDM",
    "DEPENDENCY_LOCK_AVAILABLE",
    "DEPENDENCY_LOCK_NOT_AVAILABLE",
    "ROLE_V2_EXPERIMENT_MANIFEST",
    "V2CheckpointExperimentManifest",
    "V2CheckpointRef",
    "V2DependencyLockProvenance",
    "V2_REQUIRED_DATA_HASH_KEYS",
    "build_v2_checkpoint_experiment_manifest",
    "hash_v2_checkpoint_experiment_manifest",
    "serialize_v2_checkpoint_experiment_manifest",
    "v2_checkpoint_experiment_manifest_to_dict",
    "v2_hash_bytes",
    "v2_hash_file",
    "v2_hash_object",
    "validate_v2_checkpoint_experiment_manifest",
]
