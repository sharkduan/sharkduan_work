"""Task 52.5 V2 full-beta training harness boundary.

This module coordinates the existing V2 dataset/training/tuning/manifest
contracts for a full-beta run. It does not access raw local data roots, write
checkpoint payloads, start later pipeline work, or import heavyweight optional
dependencies at module import time.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Mapping, Optional

from covalent_design._yaml_loader import load_yaml_config
from covalent_design.contracts.errors import ContractErrorInfo
from covalent_design.contracts.types import (
    CONTRACT_VERSION,
    SCHEMA_VERSION,
    ContractEnvelope,
    Provenance,
    ValidationReceipt,
)
from covalent_design.model.non_pmdm_baseline import BASELINE_MODE_NON_PMDM
from covalent_design.training.v2_manifests import (
    DEPENDENCY_LOCK_NOT_AVAILABLE,
    V2CheckpointRef,
    V2DependencyLockProvenance,
    build_v2_checkpoint_experiment_manifest,
    v2_checkpoint_experiment_manifest_to_dict,
    v2_hash_file,
    v2_hash_object,
)
from covalent_design.training.v2_train_loop import run_v2_train, v2_training_summary_to_dict
from covalent_design.training.v2_tuning import run_v2_tune, v2_tuning_summary_to_dict

VALIDATOR_NAME = "covalent_design.training.v2_full_beta"

V2_FULL_BETA_CONFIG_MISSING = "V2_FULL_BETA_CONFIG_MISSING"
V2_FULL_BETA_CONFIG_UNREADABLE = "V2_FULL_BETA_CONFIG_UNREADABLE"
V2_FULL_BETA_REQUIRED_FIELD_MISSING = "V2_FULL_BETA_REQUIRED_FIELD_MISSING"
V2_FULL_BETA_REAL_DATA_NOT_AUTHORIZED = "V2_FULL_BETA_REAL_DATA_NOT_AUTHORIZED"
V2_FULL_BETA_HEAVY_ENV_UNAVAILABLE = "V2_FULL_BETA_HEAVY_ENV_UNAVAILABLE"
V2_FULL_BETA_TUNING_FAILED = "V2_FULL_BETA_TUNING_FAILED"
V2_FULL_BETA_TRAINING_FAILED = "V2_FULL_BETA_TRAINING_FAILED"
V2_FULL_BETA_MANIFEST_FAILED = "V2_FULL_BETA_MANIFEST_FAILED"

_REQUIRED_CONFIG_KEYS = (
    "execution_mode",
    "runtime_budget_seconds",
    "seed",
    "device",
    "model_mode",
    "split_name",
    "records_path",
    "split_index_path",
    "visual_check_index_path",
    "quality_report_path",
    "family_readiness_report_path",
    "license_gate_report_path",
    "checkpoint_policy",
    "checkpoint_selection_metric",
)
_VALID_EXECUTION_MODES = ("fixture", "heavy_manual")
_VALID_CHECKPOINT_POLICIES = ("manifest_ref_only",)
_RAW_ROOT = "d:" + "\\codex_work" + "\\data"


@dataclass(frozen=True)
class V2FullBetaConfig:
    execution_mode: str
    runtime_budget_seconds: int
    seed: int
    device: str
    model_mode: str
    split_name: str
    records_path: str
    split_index_path: str
    visual_check_index_path: str
    quality_report_path: str
    family_readiness_report_path: str
    license_gate_report_path: str
    checkpoint_policy: str
    checkpoint_selection_metric: str
    real_data_authorized: bool = False
    require_heavy_environment: bool = False
    output_root: str = ""
    steps: int = 1
    batch_size: int = 1
    tuning_config_path: str = ""
    profile: str = ""
    config_path: str = ""
    schema_version: str = SCHEMA_VERSION
    contract_version: str = CONTRACT_VERSION

    def to_training_config(self) -> dict[str, object]:
        return _sorted_mapping(
            {
                "schema_version": self.schema_version,
                "contract_version": self.contract_version,
                "profile": self.profile,
                "device": self.device,
                "model_mode": self.model_mode,
                "split_name": self.split_name,
                "records_path": self.records_path,
                "split_index_path": self.split_index_path,
                "visual_check_index_path": self.visual_check_index_path,
                "quality_report_path": self.quality_report_path,
                "family_readiness_report_path": self.family_readiness_report_path,
                "license_gate_report_path": self.license_gate_report_path,
                "steps": self.steps,
                "batch_size": self.batch_size,
                "seed": self.seed,
            }
        )

    def to_dict(self) -> dict[str, object]:
        return _sorted_mapping(
            {
                **self.to_training_config(),
                "execution_mode": self.execution_mode,
                "runtime_budget_seconds": self.runtime_budget_seconds,
                "real_data_authorized": self.real_data_authorized,
                "require_heavy_environment": self.require_heavy_environment,
                "output_root": self.output_root,
                "checkpoint_policy": self.checkpoint_policy,
                "checkpoint_selection_metric": self.checkpoint_selection_metric,
                "tuning_config_path": self.tuning_config_path,
                "config_path": self.config_path,
            }
        )


@dataclass(frozen=True)
class V2FullBetaSummary:
    success: bool
    execution_mode: str
    device: str
    model_mode: str
    checkpoint_policy: str
    checkpoint_selection_metric: str
    selected_checkpoint_ref: Optional[Mapping[str, object]]
    selected_checkpoint_justification: str
    training: Mapping[str, object]
    tuning: Mapping[str, object]
    manifest: Mapping[str, object]
    outputs_written: bool = False
    real_data_accessed: bool = False
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    warnings: tuple[str, ...] = ()
    diagnostics: tuple[Mapping[str, object], ...] = ()
    config: Mapping[str, object] = field(default_factory=dict)
    summary_hash: str = ""
    schema_version: str = SCHEMA_VERSION
    contract_version: str = CONTRACT_VERSION

    def to_dict(self) -> dict[str, object]:
        return v2_full_beta_summary_to_dict(self)


def run_v2_full_beta_train(config: object) -> ContractEnvelope[V2FullBetaSummary]:
    loaded = _load_config(config)
    if isinstance(loaded, ContractEnvelope):
        return loaded
    resolved = loaded

    authorization_error = _validate_real_data_boundary(resolved)
    if authorization_error is not None:
        return _failed_summary(resolved, authorization_error, "authorization rejected before training")

    tuning_summary: Mapping[str, object] = {"status": "not_configured"}
    if resolved.tuning_config_path:
        tuning_envelope = run_v2_tune(resolved.tuning_config_path)
        tuning_summary = v2_tuning_summary_to_dict(tuning_envelope.payload)
        if not tuning_envelope.receipt.passed:
            error = tuning_envelope.receipt.errors[0]
            return _failed_summary(
                resolved,
                _error(V2_FULL_BETA_TUNING_FAILED, f"Task 52 tuning failed: {error.message}"),
                "tuning failed before full-beta training",
                tuning=tuning_summary,
            )

    training_envelope = run_v2_train(resolved.to_training_config())
    training_summary = v2_training_summary_to_dict(training_envelope.payload)
    if not training_envelope.receipt.passed:
        error = training_envelope.receipt.errors[0]
        code = (
            V2_FULL_BETA_HEAVY_ENV_UNAVAILABLE
            if error.code == "V2_TRAIN_CUDA_UNAVAILABLE" and resolved.require_heavy_environment
            else V2_FULL_BETA_TRAINING_FAILED
        )
        return _failed_summary(
            resolved,
            _error(code, f"Task 50 training boundary failed: {error.message}"),
            "training failed before checkpoint selection",
            tuning=tuning_summary,
            training=training_summary,
        )

    manifest_envelope = _build_manifest(resolved, training_summary, tuning_summary)
    if not manifest_envelope.receipt.passed:
        error = manifest_envelope.receipt.errors[0]
        return _failed_summary(
            resolved,
            _error(V2_FULL_BETA_MANIFEST_FAILED, f"Task 51 manifest binding failed: {error.message}"),
            "manifest validation failed",
            tuning=tuning_summary,
            training=training_summary,
            manifest=_manifest_failure(manifest_envelope),
        )

    manifest_dict = v2_checkpoint_experiment_manifest_to_dict(manifest_envelope.payload)
    selected = manifest_dict["checkpoint_refs"][0]
    summary = V2FullBetaSummary(
        success=True,
        execution_mode=resolved.execution_mode,
        device=resolved.device,
        model_mode=resolved.model_mode,
        checkpoint_policy=resolved.checkpoint_policy,
        checkpoint_selection_metric=resolved.checkpoint_selection_metric,
        selected_checkpoint_ref=selected,
        selected_checkpoint_justification=(
            f"selected manifest-ref checkpoint by {resolved.checkpoint_selection_metric}; "
            "payload writing remains outside the default fixture run"
        ),
        training=training_summary,
        tuning=tuning_summary,
        manifest={
            "status": "built",
            "validation_passed": True,
            "manifest": manifest_dict,
        },
        warnings=tuple(str(item) for item in training_summary.get("warnings", [])),
        config=resolved.to_dict(),
    )
    return _envelope(_with_hash(summary))


def v2_full_beta_summary_to_dict(summary: V2FullBetaSummary) -> dict[str, object]:
    return _sorted_mapping(
        {
            "schema_version": summary.schema_version,
            "contract_version": summary.contract_version,
            "success": summary.success,
            "error_code": summary.error_code,
            "error_message": summary.error_message,
            "execution_mode": summary.execution_mode,
            "device": summary.device,
            "model_mode": summary.model_mode,
            "checkpoint_policy": summary.checkpoint_policy,
            "checkpoint_selection_metric": summary.checkpoint_selection_metric,
            "selected_checkpoint_ref": summary.selected_checkpoint_ref,
            "selected_checkpoint_justification": summary.selected_checkpoint_justification,
            "training": summary.training,
            "tuning": summary.tuning,
            "manifest": summary.manifest,
            "outputs_written": summary.outputs_written,
            "real_data_accessed": summary.real_data_accessed,
            "warnings": list(summary.warnings),
            "diagnostics": [dict(item) for item in summary.diagnostics],
            "config": dict(summary.config),
            "summary_hash": summary.summary_hash,
        }
    )


def _load_config(config: object) -> V2FullBetaConfig | ContractEnvelope[V2FullBetaSummary]:
    config_path = ""
    if isinstance(config, (str, Path)):
        path = Path(config)
        config_path = str(path.resolve())
        if not path.exists():
            return _config_failure(V2_FULL_BETA_CONFIG_MISSING, f"config file not found: {path}", config_path)
        try:
            raw = load_yaml_config(str(path))
        except OSError as exc:
            return _config_failure(V2_FULL_BETA_CONFIG_UNREADABLE, str(exc), config_path)
    elif isinstance(config, Mapping):
        raw = dict(config)
    else:
        return _config_failure(V2_FULL_BETA_CONFIG_UNREADABLE, "config must be a path or mapping", "")

    missing = [key for key in _REQUIRED_CONFIG_KEYS if raw.get(key) in (None, "")]
    if missing:
        return _config_failure(
            V2_FULL_BETA_REQUIRED_FIELD_MISSING,
            "Task 52.5 requires config fields: " + ", ".join(missing),
            config_path,
        )
    execution_mode = str(raw["execution_mode"])
    if execution_mode not in _VALID_EXECUTION_MODES:
        return _config_failure(
            V2_FULL_BETA_REQUIRED_FIELD_MISSING,
            f"unsupported execution_mode {execution_mode!r}",
            "execution_mode",
        )
    checkpoint_policy = str(raw["checkpoint_policy"])
    if checkpoint_policy not in _VALID_CHECKPOINT_POLICIES:
        return _config_failure(
            V2_FULL_BETA_REQUIRED_FIELD_MISSING,
            f"unsupported checkpoint_policy {checkpoint_policy!r}",
            "checkpoint_policy",
        )
    return V2FullBetaConfig(
        execution_mode=execution_mode,
        runtime_budget_seconds=int(raw["runtime_budget_seconds"]),
        seed=int(raw["seed"]),
        device=str(raw["device"]),
        model_mode=str(raw["model_mode"]),
        split_name=str(raw["split_name"]),
        records_path=str(raw["records_path"]),
        split_index_path=str(raw["split_index_path"]),
        visual_check_index_path=str(raw["visual_check_index_path"]),
        quality_report_path=str(raw["quality_report_path"]),
        family_readiness_report_path=str(raw["family_readiness_report_path"]),
        license_gate_report_path=str(raw["license_gate_report_path"]),
        checkpoint_policy=checkpoint_policy,
        checkpoint_selection_metric=str(raw["checkpoint_selection_metric"]),
        real_data_authorized=bool(raw.get("real_data_authorized", False)),
        require_heavy_environment=bool(raw.get("require_heavy_environment", False)),
        output_root=str(raw.get("output_root", "")),
        steps=int(raw.get("steps", 1) or 1),
        batch_size=int(raw.get("batch_size", 1) or 1),
        tuning_config_path=str(raw.get("tuning_config_path", "")),
        profile=str(raw.get("profile", "")),
        config_path=config_path,
        schema_version=str(raw.get("schema_version", SCHEMA_VERSION)),
        contract_version=str(raw.get("contract_version", CONTRACT_VERSION)),
    )


def _validate_real_data_boundary(config: V2FullBetaConfig) -> Optional[ContractErrorInfo]:
    if config.execution_mode == "heavy_manual" and not config.real_data_authorized:
        return _error(
            V2_FULL_BETA_REAL_DATA_NOT_AUTHORIZED,
            "heavy_manual full-beta training requires explicit controller authorization",
        )
    if not config.real_data_authorized:
        for key, value in config.to_dict().items():
            if isinstance(value, str) and _looks_like_raw_data_root(value):
                return _error(
                    V2_FULL_BETA_REAL_DATA_NOT_AUTHORIZED,
                    f"config field {key} points at the raw local data root without authorization",
                    str(key),
                )
    return None


def _looks_like_raw_data_root(value: str) -> bool:
    normalized = value.replace("/", "\\").lower()
    return normalized == _RAW_ROOT or normalized.startswith(_RAW_ROOT + "\\")


def _build_manifest(
    config: V2FullBetaConfig,
    training_summary: Mapping[str, object],
    tuning_summary: Mapping[str, object],
) -> ContractEnvelope:
    training_summary_hash = v2_hash_object(training_summary)
    checkpoint = V2CheckpointRef(
        checkpoint_id="v2-full-beta-selected",
        checkpoint_uri="manifest-ref://v2-full-beta/selected",
        step=config.steps,
        sha256=training_summary_hash,
        format="manifest_ref",
        selected=True,
    )
    dataset_index_hash = v2_hash_object(training_summary.get("dataset", {}))
    data_hashes = {
        "records_jsonl": v2_hash_file(config.records_path),
        "split_index": v2_hash_file(config.split_index_path),
        "quality_report": v2_hash_file(config.quality_report_path),
        "visual_check_index": v2_hash_file(config.visual_check_index_path),
        "license_gate_report": v2_hash_file(config.license_gate_report_path),
    }
    return build_v2_checkpoint_experiment_manifest(
        manifest_id="v2-full-beta-training-manifest",
        environment_hash=v2_hash_object(
            {
                "device": config.device,
                "execution_mode": config.execution_mode,
                "model_mode": config.model_mode,
                "profile": config.profile,
            }
        ),
        dependency_lock=V2DependencyLockProvenance(
            status=DEPENDENCY_LOCK_NOT_AVAILABLE,
            reason="verified dependency lock is not required for fixture-mode full-beta harness evidence",
        ),
        data_hashes=data_hashes,
        dataset_index_hash=dataset_index_hash,
        family_readiness_hash=v2_hash_file(config.family_readiness_report_path),
        training_config_hash=v2_hash_object(config.to_dict()),
        training_summary_hash=training_summary_hash,
        training_summary_ref="memory://v2-full-beta/training-summary",
        checkpoint_refs=(checkpoint,),
        baseline_mode=config.model_mode,
        is_pmdm=config.model_mode == "pmdm",
        pmdm_status="not_required" if config.model_mode == BASELINE_MODE_NON_PMDM else "available",
        run_id="v2-full-beta-fixture",
        warnings=tuple(str(item) for item in training_summary.get("warnings", [])),
        diagnostics=(
            {
                "tuning_selected_trial_id": tuning_summary.get("selected_trial_id"),
                "tuning_summary_hash": v2_hash_object(tuning_summary),
            },
        ),
    )


def _failed_summary(
    config: V2FullBetaConfig,
    error: ContractErrorInfo,
    justification: str,
    *,
    tuning: Optional[Mapping[str, object]] = None,
    training: Optional[Mapping[str, object]] = None,
    manifest: Optional[Mapping[str, object]] = None,
) -> ContractEnvelope[V2FullBetaSummary]:
    summary = V2FullBetaSummary(
        success=False,
        error_code=error.code,
        error_message=error.message,
        execution_mode=config.execution_mode,
        device=config.device,
        model_mode=config.model_mode,
        checkpoint_policy=config.checkpoint_policy,
        checkpoint_selection_metric=config.checkpoint_selection_metric,
        selected_checkpoint_ref=None,
        selected_checkpoint_justification=justification,
        tuning=tuning or {"status": "not_run"},
        training=training or {"status": "not_run", "success": False},
        manifest=manifest or {"status": "not_built", "validation_passed": False},
        config=config.to_dict(),
    )
    return _envelope(_with_hash(summary), errors=(error,))


def _config_failure(code: str, message: str, location: str) -> ContractEnvelope[V2FullBetaSummary]:
    config = V2FullBetaConfig(
        execution_mode="fixture",
        runtime_budget_seconds=0,
        seed=0,
        device="cpu",
        model_mode=BASELINE_MODE_NON_PMDM,
        split_name="",
        records_path="",
        split_index_path="",
        visual_check_index_path="",
        quality_report_path="",
        family_readiness_report_path="",
        license_gate_report_path="",
        checkpoint_policy="manifest_ref_only",
        checkpoint_selection_metric="",
        config_path=location,
    )
    return _failed_summary(config, _error(code, message, location), "configuration rejected")


def _manifest_failure(envelope: ContractEnvelope) -> Mapping[str, object]:
    return {
        "status": "failed",
        "validation_passed": False,
        "errors": [dict(error.__dict__) for error in envelope.receipt.errors],
    }


def _with_hash(summary: V2FullBetaSummary) -> V2FullBetaSummary:
    return replace(summary, summary_hash=_summary_hash(summary))


def _summary_hash(summary: V2FullBetaSummary) -> str:
    without_hash = replace(summary, summary_hash="")
    data = json.dumps(
        v2_full_beta_summary_to_dict(without_hash),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def _envelope(
    summary: V2FullBetaSummary,
    *,
    errors: tuple[ContractErrorInfo, ...] = (),
) -> ContractEnvelope[V2FullBetaSummary]:
    return ContractEnvelope(
        payload=summary,
        artifacts=(),
        receipt=ValidationReceipt(
            validator=VALIDATOR_NAME,
            contract_version=CONTRACT_VERSION,
            input_sha256=summary.summary_hash.removeprefix("sha256:"),
            passed=not errors,
            errors=errors,
        ),
        provenance=Provenance(),
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


def _sorted_mapping(value: Mapping[str, object]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, item in sorted(value.items(), key=lambda pair: str(pair[0])):
        if isinstance(item, Mapping):
            result[str(key)] = _sorted_mapping({str(k): v for k, v in item.items()})
        elif isinstance(item, tuple):
            result[str(key)] = [
                _sorted_mapping(x) if isinstance(x, Mapping) else x for x in item
            ]
        elif isinstance(item, list):
            result[str(key)] = [
                _sorted_mapping(x) if isinstance(x, Mapping) else x for x in item
            ]
        else:
            result[str(key)] = item
    return result


__all__ = [
    "V2FullBetaConfig",
    "V2FullBetaSummary",
    "V2_FULL_BETA_CONFIG_MISSING",
    "V2_FULL_BETA_CONFIG_UNREADABLE",
    "V2_FULL_BETA_HEAVY_ENV_UNAVAILABLE",
    "V2_FULL_BETA_MANIFEST_FAILED",
    "V2_FULL_BETA_REAL_DATA_NOT_AUTHORIZED",
    "V2_FULL_BETA_REQUIRED_FIELD_MISSING",
    "V2_FULL_BETA_TRAINING_FAILED",
    "V2_FULL_BETA_TUNING_FAILED",
    "run_v2_full_beta_train",
    "v2_full_beta_summary_to_dict",
]
