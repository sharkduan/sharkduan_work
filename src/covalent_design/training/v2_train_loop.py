"""Task 50: V2 CPU/GPU training smoke loop boundary.

The loop consumes Task 49 V2 eligibility inputs, validates artifact references,
selects an explicit model path, and emits a deterministic smoke summary. It
does not construct checkpoints, write model weights, run sampling, or bypass
V2 eligibility gates with the v1 training dataset path.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Optional

from covalent_design._yaml_loader import load_yaml_config
from covalent_design.contracts.errors import ContractErrorInfo
from covalent_design.contracts.types import (
    CONTRACT_VERSION,
    SCHEMA_VERSION,
    ArtifactRef,
    ContractEnvelope,
    EdgeDenominators,
    LossReport,
    MaskAudit,
    Provenance,
    REQUIRED_LOSS_COMPONENT_KEYS,
    ValidationReceipt,
)
from covalent_design.model.non_pmdm_baseline import (
    BASELINE_MODE_NON_PMDM,
    BASELINE_NOT_PMDM_WARNING,
    BASELINE_NOT_PMDM_WARNING_CODE,
    baseline_mode_selection_to_dict,
    check_baseline_mode,
)
from covalent_design.model.pmdm_real_adapter import check_pmdm_available, pmdm_backend_status_to_dict
from covalent_design.model.torch_backend import check_torch_available
from covalent_design.training.v2_dataset import (
    V2TrainingDatasetIndex,
    prepare_v2_dataset,
    v2_training_dataset_index_to_dict,
)

VALID_MODEL_MODES = ("pmdm", BASELINE_MODE_NON_PMDM)
VALID_DEVICES = ("cpu", "cuda")
VALIDATOR_NAME = "covalent_design.training.v2_train_loop"

V2_TRAIN_TASK49_INPUTS_MISSING = "V2_TRAIN_TASK49_INPUTS_MISSING"
V2_TRAIN_ARTIFACT_MISSING = "V2_TRAIN_ARTIFACT_MISSING"
V2_TRAIN_ARTIFACT_UNREADABLE = "V2_TRAIN_ARTIFACT_UNREADABLE"
V2_TRAIN_ARTIFACT_BYTE_MISMATCH = "V2_TRAIN_ARTIFACT_BYTE_MISMATCH"
V2_TRAIN_ARTIFACT_CHECKSUM_MISMATCH = "V2_TRAIN_ARTIFACT_CHECKSUM_MISMATCH"
V2_TRAIN_CUDA_UNAVAILABLE = "V2_TRAIN_CUDA_UNAVAILABLE"
V2_TRAIN_MODEL_MODE_UNSUPPORTED = "V2_TRAIN_MODEL_MODE_UNSUPPORTED"
V2_TRAIN_DENOMINATOR_DRIFT = "V2_TRAIN_DENOMINATOR_DRIFT"
V2_TRAIN_CONFIG_MISSING = "V2_TRAIN_CONFIG_MISSING"
V2_TRAIN_CONFIG_UNREADABLE = "V2_TRAIN_CONFIG_UNREADABLE"
V2_TRAIN_DEVICE_UNSUPPORTED = "V2_TRAIN_DEVICE_UNSUPPORTED"

_TASK49_REQUIRED_CONFIG_KEYS = (
    "records_path",
    "split_index_path",
    "split_name",
    "visual_check_index_path",
    "quality_report_path",
    "family_readiness_report_path",
    "license_gate_report_path",
)


@dataclass(frozen=True)
class V2TrainLoopConfig:
    """Resolved Task 50 smoke-loop configuration."""

    device: str
    model_mode: str
    split_name: str
    records_path: str
    split_index_path: str
    visual_check_index_path: str
    quality_report_path: str
    family_readiness_report_path: str
    license_gate_report_path: str
    steps: int = 1
    batch_size: int = 1
    expected_denominators: Mapping[str, int] = field(default_factory=dict)
    config_path: str = ""
    profile: str = ""
    schema_version: str = SCHEMA_VERSION
    contract_version: str = CONTRACT_VERSION

    def to_dict(self) -> dict[str, object]:
        return {
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
            "expected_denominators": dict(sorted(self.expected_denominators.items())),
            "config_path": self.config_path,
        }


@dataclass(frozen=True)
class V2TrainingSummary:
    """Deterministic JSON-safe summary for a Task 50 smoke run."""

    success: bool
    device: str
    model_mode: str
    dataset: Mapping[str, object]
    artifact_preflight: Mapping[str, object]
    model_path: Mapping[str, object]
    phases: Mapping[str, bool]
    denominator_status: str
    loss_report: Optional[LossReport] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    warnings: tuple[str, ...] = ()
    publication_claims: tuple[str, ...] = ()
    config: Mapping[str, object] = field(default_factory=dict)
    diagnostics: tuple[Mapping[str, object], ...] = ()
    schema_version: str = SCHEMA_VERSION
    contract_version: str = CONTRACT_VERSION

    @property
    def cuda_requested(self) -> bool:
        return self.device.startswith("cuda")

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "schema_version": self.schema_version,
            "contract_version": self.contract_version,
            "success": self.success,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "device": self.device,
            "cuda_requested": self.cuda_requested,
            "model_mode": self.model_mode,
            "model_path": _json_mapping(self.model_path),
            "dataset": _json_mapping(self.dataset),
            "artifact_preflight": _json_mapping(self.artifact_preflight),
            "phases": dict(sorted(self.phases.items())),
            "denominator_status": self.denominator_status,
            "warnings": list(self.warnings),
            "publication_claims": list(self.publication_claims),
            "config": _json_mapping(self.config),
            "diagnostics": [_json_mapping(item) for item in self.diagnostics],
        }
        if self.loss_report is not None:
            result["loss_report"] = self.loss_report.to_dict()
        return result


def run_v2_train(config: object) -> ContractEnvelope[V2TrainingSummary]:
    """Run the deterministic Task 50 smoke loop from a config path or mapping."""
    loaded = _load_config(config)
    if isinstance(loaded, ContractEnvelope):
        return loaded
    resolved = loaded

    dataset_envelope = prepare_v2_dataset(
        resolved.records_path,
        resolved.split_index_path,
        resolved.split_name,
        visual_check_index_path=resolved.visual_check_index_path,
        quality_report_path=resolved.quality_report_path,
        family_readiness_report_path=resolved.family_readiness_report_path,
        license_gate_report_path=resolved.license_gate_report_path,
    )
    if not dataset_envelope.receipt.passed:
        error = dataset_envelope.receipt.errors[0]
        return _failed_summary(
            resolved,
            error.code,
            error.message,
            dataset=_empty_dataset_summary(resolved),
            artifact_preflight=_empty_preflight("not_run"),
            model_path=_model_path_not_selected(resolved.model_mode),
            phases=_phases(preflight=False, tensor=False, model=False),
        )

    dataset = dataset_envelope.payload
    dataset_summary = _dataset_summary(dataset)
    preflight = _validate_artifacts(dataset)
    if isinstance(preflight, ContractErrorInfo):
        return _failed_summary(
            resolved,
            preflight.code,
            preflight.message,
            dataset=dataset_summary,
            artifact_preflight=_preflight_failure(preflight),
            model_path=_model_path_not_selected(resolved.model_mode),
            phases=_phases(preflight=False, tensor=False, model=False),
        )

    if resolved.device.startswith("cuda"):
        torch_status = check_torch_available()
        if not torch_status.cuda_available:
            return _failed_summary(
                resolved,
                V2_TRAIN_CUDA_UNAVAILABLE,
                "CUDA was requested but is unavailable for the Task 50 GPU smoke config",
                dataset=dataset_summary,
                artifact_preflight=preflight,
                model_path=_model_path_not_selected(resolved.model_mode),
                phases=_phases(preflight=True, tensor=False, model=False),
                diagnostics=(_status_to_mapping(torch_status),),
            )

    if resolved.model_mode == "pmdm":
        pmdm_status = check_pmdm_available()
        if pmdm_status.status != "available":
            code = pmdm_status.error_code or "V2_TRAIN_PMDM_UNAVAILABLE"
            return _failed_summary(
                resolved,
                code,
                pmdm_status.error_message or "PMDM backend unavailable",
                dataset=dataset_summary,
                artifact_preflight=preflight,
                model_path={
                    "selected_mode": "pmdm",
                    "baseline_mode": None,
                    "is_pmdm": True,
                    "status": pmdm_status.status,
                    "error_code": code,
                },
                phases=_phases(preflight=True, tensor=False, model=True),
                diagnostics=(pmdm_backend_status_to_dict(pmdm_status),),
            )
        model_path = {
            "selected_mode": "pmdm",
            "baseline_mode": None,
            "is_pmdm": True,
            "status": "available",
        }
        warnings: tuple[str, ...] = ()
    else:
        selection = check_baseline_mode(resolved.model_mode)
        if not selection.accepted:
            return _failed_summary(
                resolved,
                selection.error_code or V2_TRAIN_MODEL_MODE_UNSUPPORTED,
                selection.error_message or f"unsupported model_mode {resolved.model_mode!r}",
                dataset=dataset_summary,
                artifact_preflight=preflight,
                model_path=baseline_mode_selection_to_dict(selection),
                phases=_phases(preflight=True, tensor=False, model=True),
            )
        model_path = {
            **baseline_mode_selection_to_dict(selection),
            "status": "available",
            "warning_code": BASELINE_NOT_PMDM_WARNING_CODE,
        }
        warnings = (BASELINE_NOT_PMDM_WARNING,)

    loss_report = _build_smoke_loss_report(dataset)
    denominator_error = _check_expected_denominators(loss_report, resolved.expected_denominators)
    if denominator_error is not None:
        return _failed_summary(
            resolved,
            denominator_error.code,
            denominator_error.message,
            dataset=dataset_summary,
            artifact_preflight=preflight,
            model_path=model_path,
            phases=_phases(preflight=True, tensor=False, model=True),
            loss_report=loss_report,
            denominator_status="failed",
            warnings=warnings,
        )

    summary = V2TrainingSummary(
        success=True,
        device=resolved.device,
        model_mode=resolved.model_mode,
        dataset=dataset_summary,
        artifact_preflight=preflight,
        model_path=model_path,
        phases=_phases(preflight=True, tensor=False, model=True),
        denominator_status="passed",
        loss_report=loss_report,
        warnings=warnings,
        config=resolved.to_dict(),
    )
    return _envelope(summary)


def v2_training_summary_to_dict(summary: V2TrainingSummary) -> dict[str, object]:
    """Return a deterministic JSON-compatible representation."""
    return summary.to_dict()


def _load_config(config: object) -> V2TrainLoopConfig | ContractEnvelope[V2TrainingSummary]:
    config_path = ""
    if isinstance(config, (str, Path)):
        path = Path(config)
        config_path = str(path.resolve())
        if not path.exists():
            return _config_failure(V2_TRAIN_CONFIG_MISSING, f"config file not found: {path}", config_path)
        try:
            raw = load_yaml_config(str(path))
        except OSError as exc:
            return _config_failure(V2_TRAIN_CONFIG_UNREADABLE, str(exc), config_path)
    elif isinstance(config, Mapping):
        raw = dict(config)
    else:
        return _config_failure(V2_TRAIN_CONFIG_UNREADABLE, "config must be a path or mapping", "")

    missing = [key for key in _TASK49_REQUIRED_CONFIG_KEYS if not raw.get(key)]
    if missing:
        return _config_failure(
            V2_TRAIN_TASK49_INPUTS_MISSING,
            "Task 50 requires Task 49 V2 gate inputs: " + ", ".join(missing),
            config_path,
        )
    device = str(raw.get("device", "cpu"))
    model_mode = str(raw.get("model_mode", raw.get("baseline_mode", BASELINE_MODE_NON_PMDM)))
    if device not in VALID_DEVICES and not device.startswith("cuda"):
        return _config_failure(V2_TRAIN_DEVICE_UNSUPPORTED, f"unsupported device {device!r}", config_path)
    if model_mode not in VALID_MODEL_MODES:
        return _config_failure(V2_TRAIN_MODEL_MODE_UNSUPPORTED, f"unsupported model_mode {model_mode!r}", config_path)

    expected = raw.get("expected_denominators", {})
    if not isinstance(expected, Mapping):
        expected = {}
    return V2TrainLoopConfig(
        device=device,
        model_mode=model_mode,
        split_name=str(raw["split_name"]),
        records_path=str(raw["records_path"]),
        split_index_path=str(raw["split_index_path"]),
        visual_check_index_path=str(raw["visual_check_index_path"]),
        quality_report_path=str(raw["quality_report_path"]),
        family_readiness_report_path=str(raw["family_readiness_report_path"]),
        license_gate_report_path=str(raw["license_gate_report_path"]),
        steps=int(raw.get("steps", 1) or 1),
        batch_size=int(raw.get("batch_size", 1) or 1),
        expected_denominators={str(k): int(v) for k, v in expected.items()},
        config_path=config_path,
        profile=str(raw.get("profile", "")),
        schema_version=str(raw.get("schema_version", SCHEMA_VERSION)),
        contract_version=str(raw.get("contract_version", CONTRACT_VERSION)),
    )


def _validate_artifacts(dataset: V2TrainingDatasetIndex) -> Mapping[str, object] | ContractErrorInfo:
    base_dir = Path(dataset.records_path).resolve().parent if dataset.records_path else Path.cwd()
    checked: list[dict[str, object]] = []
    for entry in sorted(dataset.records, key=lambda item: item.record_id):
        for role, ref in sorted(entry.artifact_refs.items(), key=lambda item: item[0]):
            path = _resolve_artifact_path(base_dir, ref)
            if not path.exists():
                return _error(
                    V2_TRAIN_ARTIFACT_MISSING,
                    f"artifact not found for {entry.record_id}:{role}: {path}",
                    str(path),
                    {"record_id": entry.record_id, "role": role},
                )
            try:
                if path.is_dir():
                    raise OSError("artifact path is a directory")
                data = path.read_bytes()
            except OSError as exc:
                return _error(
                    V2_TRAIN_ARTIFACT_UNREADABLE,
                    f"artifact unreadable for {entry.record_id}:{role}: {exc}",
                    str(path),
                    {"record_id": entry.record_id, "role": role},
                )
            actual_bytes = len(data)
            if ref.bytes and actual_bytes != ref.bytes:
                return _error(
                    V2_TRAIN_ARTIFACT_BYTE_MISMATCH,
                    f"artifact byte count mismatch for {entry.record_id}:{role}",
                    str(path),
                    {
                        "record_id": entry.record_id,
                        "role": role,
                        "expected_bytes": ref.bytes,
                        "actual_bytes": actual_bytes,
                    },
                )
            actual_sha = hashlib.sha256(data).hexdigest()
            if ref.sha256 and actual_sha != ref.sha256:
                return _error(
                    V2_TRAIN_ARTIFACT_CHECKSUM_MISMATCH,
                    f"artifact checksum mismatch for {entry.record_id}:{role}",
                    str(path),
                    {
                        "record_id": entry.record_id,
                        "role": role,
                        "expected_sha256": ref.sha256,
                        "actual_sha256": actual_sha,
                    },
                )
            checked.append(
                {
                    "record_id": entry.record_id,
                    "role": role,
                    "path": str(path),
                    "bytes": actual_bytes,
                    "sha256": actual_sha,
                }
            )
    return {
        "status": "passed",
        "checked_artifact_count": len(checked),
        "checked_artifacts": checked,
    }


def _resolve_artifact_path(base_dir: Path, ref: ArtifactRef) -> Path:
    uri_path = Path(ref.uri)
    if uri_path.is_absolute():
        return uri_path
    return (base_dir / uri_path).resolve()


def _build_smoke_loss_report(dataset: V2TrainingDatasetIndex) -> LossReport:
    candidate_count = len(dataset.records)
    denominators = EdgeDenominators(
        candidate_count=candidate_count,
        natural_candidate_count=candidate_count,
        forced_positive_count=0,
        eligible_edge_count=candidate_count,
        masked_candidate_count=0,
        edge_loss_denominator=candidate_count,
        bond_type_loss_denominator=candidate_count,
        geometry_loss_denominator=candidate_count,
        message_passing_candidate_count=candidate_count,
        gate_evaluated_count=candidate_count,
    )
    mask_audit = MaskAudit(
        candidate_count=candidate_count,
        natural_positive_count=0,
        forced_positive_count=0,
        natural_negative_count=candidate_count,
        zero_negative_count=1 if candidate_count == 0 else 0,
        masked_by_pending_smarts=0,
        masked_by_pending_geometry=0,
        masked_by_missing_chemical_state=0,
        masked_by_q2_exclusion=0,
        masked_by_forced_positive_exclusion=0,
        edge_loss_eligible_count=candidate_count,
        bond_type_loss_eligible_count=candidate_count,
        geometry_loss_eligible_count=candidate_count,
        message_passing_candidate_count=candidate_count,
        gate_evaluated_count=candidate_count,
    )
    components = {key: 0.0 for key in REQUIRED_LOSS_COMPONENT_KEYS}
    return LossReport(
        step=0,
        total_loss=0.0,
        components=components,
        denominators=denominators,
        mask_audit=mask_audit,
    )


def _check_expected_denominators(
    report: LossReport,
    expected: Mapping[str, int],
) -> Optional[ContractErrorInfo]:
    if not expected:
        return None
    observed = report.to_dict().get("denominators", {})
    if not isinstance(observed, Mapping):
        observed = {}
    mismatches = {
        key: {"expected": value, "observed": observed.get(key)}
        for key, value in sorted(expected.items())
        if observed.get(key) != value
    }
    if not mismatches:
        return None
    return _error(
        V2_TRAIN_DENOMINATOR_DRIFT,
        "observed denominators differ from expected smoke config",
        "expected_denominators",
        {"mismatches": mismatches},
    )


def _dataset_summary(dataset: V2TrainingDatasetIndex) -> dict[str, object]:
    data = v2_training_dataset_index_to_dict(dataset)
    return {
        "source": "V2TrainingDatasetIndex",
        "split_name": dataset.split_name,
        "records_path": dataset.records_path,
        "eligible_count": len(dataset.records),
        "excluded_count": len(dataset.excluded_records),
        "record_ids": [entry.record_id for entry in dataset.records],
        "exclusion_summary": data["exclusion_summary"],
    }


def _empty_dataset_summary(config: V2TrainLoopConfig) -> dict[str, object]:
    return {
        "source": "V2TrainingDatasetIndex",
        "split_name": config.split_name,
        "records_path": config.records_path,
        "eligible_count": 0,
        "excluded_count": 0,
        "record_ids": [],
    }


def _empty_preflight(status: str) -> dict[str, object]:
    return {"status": status, "checked_artifact_count": 0, "checked_artifacts": []}


def _preflight_failure(error: ContractErrorInfo) -> dict[str, object]:
    return {
        **_empty_preflight("failed"),
        "error_code": error.code,
        "error_message": error.message,
        "location": error.location,
        "details": dict(error.details),
    }


def _model_path_not_selected(model_mode: str) -> dict[str, object]:
    return {
        "selected_mode": model_mode,
        "baseline_mode": None,
        "is_pmdm": model_mode == "pmdm",
        "status": "not_run",
    }


def _phases(*, preflight: bool, tensor: bool, model: bool) -> dict[str, bool]:
    return {
        "task49_dataset_loaded": True,
        "artifact_preflight_completed": preflight,
        "tensor_construction_started": tensor,
        "model_path_selected": model,
        "checkpoint_manifest_written": False,
    }


def _failed_summary(
    config: V2TrainLoopConfig,
    code: str,
    message: str,
    *,
    dataset: Mapping[str, object],
    artifact_preflight: Mapping[str, object],
    model_path: Mapping[str, object],
    phases: Mapping[str, bool],
    loss_report: Optional[LossReport] = None,
    denominator_status: str = "not_run",
    warnings: tuple[str, ...] = (),
    diagnostics: tuple[Mapping[str, object], ...] = (),
) -> ContractEnvelope[V2TrainingSummary]:
    summary = V2TrainingSummary(
        success=False,
        error_code=code,
        error_message=message,
        device=config.device,
        model_mode=config.model_mode,
        dataset=dataset,
        artifact_preflight=artifact_preflight,
        model_path=model_path,
        phases=phases,
        denominator_status=denominator_status,
        loss_report=loss_report,
        warnings=warnings,
        config=config.to_dict(),
        diagnostics=diagnostics,
    )
    return _envelope(summary, errors=(_error(code, message),))


def _config_failure(code: str, message: str, location: str) -> ContractEnvelope[V2TrainingSummary]:
    config = V2TrainLoopConfig(
        device="cpu",
        model_mode=BASELINE_MODE_NON_PMDM,
        split_name="",
        records_path="",
        split_index_path="",
        visual_check_index_path="",
        quality_report_path="",
        family_readiness_report_path="",
        license_gate_report_path="",
        config_path=location,
    )
    return _failed_summary(
        config,
        code,
        message,
        dataset=_empty_dataset_summary(config),
        artifact_preflight=_empty_preflight("not_run"),
        model_path=_model_path_not_selected(config.model_mode),
        phases=_phases(preflight=False, tensor=False, model=False),
    )


def _envelope(
    summary: V2TrainingSummary,
    *,
    errors: tuple[ContractErrorInfo, ...] = (),
) -> ContractEnvelope[V2TrainingSummary]:
    return ContractEnvelope(
        payload=summary,
        artifacts=(),
        receipt=ValidationReceipt(
            validator=VALIDATOR_NAME,
            contract_version=CONTRACT_VERSION,
            input_sha256=_summary_digest(summary),
            passed=not errors,
            errors=errors,
        ),
        provenance=Provenance(),
    )


def _summary_digest(summary: V2TrainingSummary) -> str:
    data = json.dumps(summary.to_dict(), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


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


def _json_mapping(data: Mapping[str, object]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in sorted(data.items(), key=lambda item: str(item[0])):
        if isinstance(value, Mapping):
            result[str(key)] = _json_mapping(value)
        elif isinstance(value, tuple):
            result[str(key)] = list(value)
        elif isinstance(value, list):
            result[str(key)] = [
                _json_mapping(item) if isinstance(item, Mapping) else item
                for item in value
            ]
        else:
            result[str(key)] = value
    return result


def _status_to_mapping(status: object) -> Mapping[str, object]:
    if hasattr(status, "__dict__"):
        return dict(status.__dict__)
    return {"status": str(status)}


__all__ = [
    "V2TrainLoopConfig",
    "V2TrainingSummary",
    "run_v2_train",
    "v2_training_summary_to_dict",
]
