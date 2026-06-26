"""Task 52: deterministic V2 tiny-sweep tuning protocol.

The module is manifest-driven. It runs budgeted Task 50 smoke trials, records
trial config/result hashes, reports failures, and selects only a successful
trial by a frozen metric. It does not create checkpoint payloads.
"""

from __future__ import annotations

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
    REQUIRED_LOSS_COMPONENT_KEYS,
    ValidationReceipt,
)
from covalent_design.training.v2_manifests import v2_hash_object
from covalent_design.training.v2_train_loop import (
    VALID_DEVICES,
    VALID_MODEL_MODES,
    run_v2_train,
    v2_training_summary_to_dict,
)

VALIDATOR_NAME = "covalent_design.training.v2_tuning"

V2_TUNE_CONFIG_MISSING = "V2_TUNE_CONFIG_MISSING"
V2_TUNE_CONFIG_UNREADABLE = "V2_TUNE_CONFIG_UNREADABLE"
V2_TUNE_TRIAL_COUNT_MISSING = "V2_TUNE_TRIAL_COUNT_MISSING"
V2_TUNE_TRIAL_COUNT_INVALID = "V2_TUNE_TRIAL_COUNT_INVALID"
V2_TUNE_RUNTIME_BUDGET_MISSING = "V2_TUNE_RUNTIME_BUDGET_MISSING"
V2_TUNE_RUNTIME_BUDGET_INVALID = "V2_TUNE_RUNTIME_BUDGET_INVALID"
V2_TUNE_SEEDS_MISSING = "V2_TUNE_SEEDS_MISSING"
V2_TUNE_SEEDS_INVALID = "V2_TUNE_SEEDS_INVALID"
V2_TUNE_SEEDS_COUNT_MISMATCH = "V2_TUNE_SEEDS_COUNT_MISMATCH"
V2_TUNE_SEEDS_DUPLICATE = "V2_TUNE_SEEDS_DUPLICATE"
V2_TUNE_SELECTION_METRIC_MISSING = "V2_TUNE_SELECTION_METRIC_MISSING"
V2_TUNE_SELECTION_METRIC_UNSUPPORTED = "V2_TUNE_SELECTION_METRIC_UNSUPPORTED"
V2_TUNE_SELECTION_MODE_UNSUPPORTED = "V2_TUNE_SELECTION_MODE_UNSUPPORTED"
V2_TUNE_TASK49_INPUTS_MISSING = "V2_TUNE_TASK49_INPUTS_MISSING"
V2_TUNE_DEVICE_UNSUPPORTED = "V2_TUNE_DEVICE_UNSUPPORTED"
V2_TUNE_MODEL_MODE_UNSUPPORTED = "V2_TUNE_MODEL_MODE_UNSUPPORTED"
V2_TUNE_TRIAL_MODE_COUNT_MISMATCH = "V2_TUNE_TRIAL_MODE_COUNT_MISMATCH"
V2_TUNE_METRIC_NOT_COMPUTABLE = "V2_TUNE_METRIC_NOT_COMPUTABLE"
V2_TUNE_NO_SUCCESSFUL_TRIALS = "V2_TUNE_NO_SUCCESSFUL_TRIALS"

_TASK49_REQUIRED_CONFIG_KEYS = (
    "records_path",
    "split_index_path",
    "split_name",
    "visual_check_index_path",
    "quality_report_path",
    "family_readiness_report_path",
    "license_gate_report_path",
)
_VALID_SELECTION_METRICS = ("total_loss",) + tuple(REQUIRED_LOSS_COMPONENT_KEYS)
_VALID_SELECTION_MODES = ("minimize", "maximize")


@dataclass(frozen=True)
class V2TinySweepConfig:
    trial_count: int
    runtime_budget_seconds: int
    seeds: tuple[int, ...]
    selection_metric: str
    selection_mode: str
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
    trial_model_modes: tuple[str, ...] = ()
    expected_denominators: Mapping[str, int] = field(default_factory=dict)
    profile: str = ""
    config_path: str = ""
    schema_version: str = SCHEMA_VERSION
    contract_version: str = CONTRACT_VERSION

    def to_dict(self) -> dict[str, object]:
        return _sorted_mapping(
            {
                "schema_version": self.schema_version,
                "contract_version": self.contract_version,
                "profile": self.profile,
                "trial_count": self.trial_count,
                "runtime_budget_seconds": self.runtime_budget_seconds,
                "seeds": list(self.seeds),
                "selection_metric": self.selection_metric,
                "selection_mode": self.selection_mode,
                "device": self.device,
                "model_mode": self.model_mode,
                "trial_model_modes": list(self.trial_model_modes),
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
        )

    def training_config_for_trial(self, trial_index: int, seed: int) -> dict[str, object]:
        model_mode = (
            self.trial_model_modes[trial_index]
            if self.trial_model_modes
            else self.model_mode
        )
        return _sorted_mapping(
            {
                "schema_version": self.schema_version,
                "contract_version": self.contract_version,
                "profile": self.profile,
                "device": self.device,
                "model_mode": model_mode,
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
                "seed": seed,
            }
        )


@dataclass(frozen=True)
class V2TrialResult:
    trial_id: str
    trial_index: int
    seed: int
    status: str
    success: bool
    selected: bool
    config_hash: str
    result_hash: str
    selection_metric_name: str
    selection_metric_value: Optional[float]
    metric_values: Mapping[str, Optional[float]]
    checkpoint_ref: Optional[Mapping[str, object]]
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    training_summary: Optional[Mapping[str, object]] = None
    warnings: tuple[str, ...] = ()
    diagnostics: tuple[Mapping[str, object], ...] = ()
    schema_version: str = SCHEMA_VERSION
    contract_version: str = CONTRACT_VERSION

    def to_dict(self) -> dict[str, object]:
        return v2_trial_result_to_dict(self)


@dataclass(frozen=True)
class V2TuningSummary:
    success: bool
    trial_count: int
    runtime_budget_seconds: int
    seeds: tuple[int, ...]
    selection_metric: str
    selection_mode: str
    selected_trial_id: Optional[str]
    selected_checkpoint_ref: Optional[Mapping[str, object]]
    best_metric_value: Optional[float]
    selection_justification: str
    trials: tuple[V2TrialResult, ...]
    failed_trials: tuple[V2TrialResult, ...]
    successful_count: int
    failed_count: int
    sweep_config_hash: str
    sweep_result_hash: str = ""
    config: Mapping[str, object] = field(default_factory=dict)
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    warnings: tuple[str, ...] = ()
    diagnostics: tuple[Mapping[str, object], ...] = ()
    schema_version: str = SCHEMA_VERSION
    contract_version: str = CONTRACT_VERSION

    def to_dict(self) -> dict[str, object]:
        return v2_tuning_summary_to_dict(self)


def run_v2_tune(config: object) -> ContractEnvelope[V2TuningSummary]:
    loaded = _load_sweep_config(config)
    if isinstance(loaded, ContractEnvelope):
        return loaded

    sweep_config = loaded
    trials = tuple(
        _run_trial(sweep_config, trial_index, seed)
        for trial_index, seed in enumerate(sweep_config.seeds)
    )
    selected = _select_trial(trials, sweep_config.selection_mode)
    selected_trial = selected[0]
    selected_id = selected_trial.trial_id if selected_trial is not None else None
    selected_ref = selected_trial.checkpoint_ref if selected_trial is not None else None
    trials_with_selection = tuple(
        replace(trial, selected=trial.trial_id == selected_id) for trial in trials
    )
    failed_trials = tuple(trial for trial in trials_with_selection if not trial.success)
    successful_count = len(trials_with_selection) - len(failed_trials)
    error_code = None if selected_trial is not None else V2_TUNE_NO_SUCCESSFUL_TRIALS
    error_message = None if selected_trial is not None else "no successful trial can be selected"
    summary = V2TuningSummary(
        success=selected_trial is not None,
        trial_count=sweep_config.trial_count,
        runtime_budget_seconds=sweep_config.runtime_budget_seconds,
        seeds=sweep_config.seeds,
        selection_metric=sweep_config.selection_metric,
        selection_mode=sweep_config.selection_mode,
        selected_trial_id=selected_id,
        selected_checkpoint_ref=selected_ref,
        best_metric_value=(
            selected_trial.selection_metric_value if selected_trial is not None else None
        ),
        selection_justification=selected[1],
        trials=trials_with_selection,
        failed_trials=failed_trials,
        successful_count=successful_count,
        failed_count=len(failed_trials),
        sweep_config_hash=v2_hash_object(sweep_config.to_dict()),
        config=sweep_config.to_dict(),
        error_code=error_code,
        error_message=error_message,
    )
    summary = replace(summary, sweep_result_hash=_summary_hash(summary))
    errors = (
        (_error(V2_TUNE_NO_SUCCESSFUL_TRIALS, "no successful trials were available for selection"),)
        if not summary.success
        else ()
    )
    return _envelope(summary, errors=errors)


def v2_trial_result_to_dict(result: V2TrialResult) -> dict[str, object]:
    return _sorted_mapping(
        {
            "schema_version": result.schema_version,
            "contract_version": result.contract_version,
            "trial_id": result.trial_id,
            "trial_index": result.trial_index,
            "seed": result.seed,
            "status": result.status,
            "success": result.success,
            "selected": result.selected,
            "config_hash": result.config_hash,
            "result_hash": result.result_hash,
            "selection_metric_name": result.selection_metric_name,
            "selection_metric_value": result.selection_metric_value,
            "metric_values": dict(result.metric_values),
            "checkpoint_ref": result.checkpoint_ref,
            "error_code": result.error_code,
            "error_message": result.error_message,
            "training_summary": result.training_summary,
            "warnings": list(result.warnings),
            "diagnostics": [dict(item) for item in result.diagnostics],
        }
    )


def v2_tuning_summary_to_dict(summary: V2TuningSummary) -> dict[str, object]:
    return _sorted_mapping(
        {
            "schema_version": summary.schema_version,
            "contract_version": summary.contract_version,
            "success": summary.success,
            "error_code": summary.error_code,
            "error_message": summary.error_message,
            "trial_count": summary.trial_count,
            "runtime_budget_seconds": summary.runtime_budget_seconds,
            "seeds": list(summary.seeds),
            "selection_metric": summary.selection_metric,
            "selection_mode": summary.selection_mode,
            "selected_trial_id": summary.selected_trial_id,
            "selected_checkpoint_ref": summary.selected_checkpoint_ref,
            "best_metric_value": summary.best_metric_value,
            "selection_justification": summary.selection_justification,
            "successful_count": summary.successful_count,
            "failed_count": summary.failed_count,
            "trials": [v2_trial_result_to_dict(trial) for trial in summary.trials],
            "failed_trials": [
                v2_trial_result_to_dict(trial) for trial in summary.failed_trials
            ],
            "sweep_config_hash": summary.sweep_config_hash,
            "sweep_result_hash": summary.sweep_result_hash,
            "config": dict(summary.config),
            "warnings": list(summary.warnings),
            "diagnostics": [dict(item) for item in summary.diagnostics],
        }
    )


def _load_sweep_config(config: object) -> V2TinySweepConfig | ContractEnvelope[V2TuningSummary]:
    config_path = ""
    if isinstance(config, (str, Path)):
        path = Path(config)
        config_path = str(path.resolve())
        if not path.exists():
            return _config_failure(V2_TUNE_CONFIG_MISSING, f"config file not found: {path}", config_path)
        try:
            raw = load_yaml_config(str(path))
        except OSError as exc:
            return _config_failure(V2_TUNE_CONFIG_UNREADABLE, str(exc), config_path)
    elif isinstance(config, Mapping):
        raw = dict(config)
    else:
        return _config_failure(V2_TUNE_CONFIG_UNREADABLE, "config must be a path or mapping", "")

    error = _validate_required_config(raw, config_path)
    if error is not None:
        return _config_failure(error.code, error.message, error.location or config_path)

    trial_count = int(raw["trial_count"])
    seeds = _parse_int_tuple(raw["seeds"])
    trial_model_modes = _parse_str_tuple(raw.get("trial_model_modes", ""))
    expected = raw.get("expected_denominators", {})
    if not isinstance(expected, Mapping):
        expected = {}

    return V2TinySweepConfig(
        trial_count=trial_count,
        runtime_budget_seconds=int(raw["runtime_budget_seconds"]),
        seeds=seeds,
        selection_metric=str(raw["selection_metric"]),
        selection_mode=str(raw.get("selection_mode", "minimize")),
        device=str(raw.get("device", "cpu")),
        model_mode=str(raw.get("model_mode", "non_pmdm_baseline")),
        split_name=str(raw["split_name"]),
        records_path=str(raw["records_path"]),
        split_index_path=str(raw["split_index_path"]),
        visual_check_index_path=str(raw["visual_check_index_path"]),
        quality_report_path=str(raw["quality_report_path"]),
        family_readiness_report_path=str(raw["family_readiness_report_path"]),
        license_gate_report_path=str(raw["license_gate_report_path"]),
        steps=int(raw.get("steps", 1) or 1),
        batch_size=int(raw.get("batch_size", 1) or 1),
        trial_model_modes=trial_model_modes,
        expected_denominators={str(k): int(v) for k, v in expected.items()},
        profile=str(raw.get("profile", "")),
        config_path=config_path,
        schema_version=str(raw.get("schema_version", SCHEMA_VERSION)),
        contract_version=str(raw.get("contract_version", CONTRACT_VERSION)),
    )


def _validate_required_config(raw: Mapping[str, object], config_path: str) -> Optional[ContractErrorInfo]:
    if "trial_count" not in raw:
        return _error(V2_TUNE_TRIAL_COUNT_MISSING, "trial_count is required", "trial_count")
    try:
        trial_count = int(raw["trial_count"])
    except (TypeError, ValueError):
        return _error(V2_TUNE_TRIAL_COUNT_INVALID, "trial_count must be a positive integer", "trial_count")
    if trial_count < 1:
        return _error(V2_TUNE_TRIAL_COUNT_INVALID, "trial_count must be positive", "trial_count")
    if "runtime_budget_seconds" not in raw:
        return _error(
            V2_TUNE_RUNTIME_BUDGET_MISSING,
            "runtime_budget_seconds is required",
            "runtime_budget_seconds",
        )
    try:
        if int(raw["runtime_budget_seconds"]) < 1:
            return _error(
                V2_TUNE_RUNTIME_BUDGET_INVALID,
                "runtime_budget_seconds must be positive",
                "runtime_budget_seconds",
            )
    except (TypeError, ValueError):
        return _error(
            V2_TUNE_RUNTIME_BUDGET_INVALID,
            "runtime_budget_seconds must be a positive integer",
            "runtime_budget_seconds",
        )
    if "seeds" not in raw:
        return _error(V2_TUNE_SEEDS_MISSING, "seeds are required", "seeds")
    try:
        seeds = _parse_int_tuple(raw["seeds"])
    except ValueError as exc:
        return _error(V2_TUNE_SEEDS_INVALID, str(exc), "seeds")
    if not seeds:
        return _error(V2_TUNE_SEEDS_MISSING, "seeds are required", "seeds")
    if len(seeds) != trial_count:
        return _error(
            V2_TUNE_SEEDS_COUNT_MISMATCH,
            "len(seeds) must equal trial_count",
            "seeds",
        )
    if len(set(seeds)) != len(seeds):
        return _error(V2_TUNE_SEEDS_DUPLICATE, "seeds must be unique", "seeds")
    if "selection_metric" not in raw:
        return _error(
            V2_TUNE_SELECTION_METRIC_MISSING,
            "selection_metric is required",
            "selection_metric",
        )
    if str(raw["selection_metric"]) not in _VALID_SELECTION_METRICS:
        return _error(
            V2_TUNE_SELECTION_METRIC_UNSUPPORTED,
            f"unsupported selection_metric {raw['selection_metric']!r}",
            "selection_metric",
        )
    if str(raw.get("selection_mode", "minimize")) not in _VALID_SELECTION_MODES:
        return _error(
            V2_TUNE_SELECTION_MODE_UNSUPPORTED,
            "selection_mode must be minimize or maximize",
            "selection_mode",
        )
    missing = [key for key in _TASK49_REQUIRED_CONFIG_KEYS if not raw.get(key)]
    if missing:
        return _error(
            V2_TUNE_TASK49_INPUTS_MISSING,
            "Task 52 requires Task 49 V2 gate inputs: " + ", ".join(missing),
            "task49_inputs",
            {"missing": missing},
        )
    device = str(raw.get("device", "cpu"))
    if device not in VALID_DEVICES and not device.startswith("cuda"):
        return _error(V2_TUNE_DEVICE_UNSUPPORTED, f"unsupported device {device!r}", "device")
    model_mode = str(raw.get("model_mode", "non_pmdm_baseline"))
    if model_mode not in VALID_MODEL_MODES:
        return _error(
            V2_TUNE_MODEL_MODE_UNSUPPORTED,
            f"unsupported model_mode {model_mode!r}",
            "model_mode",
        )
    modes = _parse_str_tuple(raw.get("trial_model_modes", ""))
    if modes and len(modes) != trial_count:
        return _error(
            V2_TUNE_TRIAL_MODE_COUNT_MISMATCH,
            "trial_model_modes length must equal trial_count",
            "trial_model_modes",
        )
    for mode in modes:
        if mode not in VALID_MODEL_MODES:
            return _error(
                V2_TUNE_MODEL_MODE_UNSUPPORTED,
                f"unsupported trial model_mode {mode!r}",
                "trial_model_modes",
            )
    return None


def _run_trial(config: V2TinySweepConfig, trial_index: int, seed: int) -> V2TrialResult:
    trial_id = f"trial-{trial_index:03d}"
    train_config = config.training_config_for_trial(trial_index, seed)
    config_hash = v2_hash_object(train_config)
    envelope = run_v2_train(train_config)
    summary_dict = v2_training_summary_to_dict(envelope.payload)
    metric_value = _extract_metric(summary_dict, config.selection_metric)
    success = envelope.receipt.passed and metric_value is not None
    error_code = envelope.payload.error_code
    error_message = envelope.payload.error_message
    status = "completed" if success else "failed"
    if envelope.receipt.passed and metric_value is None:
        error_code = V2_TUNE_METRIC_NOT_COMPUTABLE
        error_message = f"selection metric {config.selection_metric!r} is not computable"
    metric_values = {
        metric: _extract_metric(summary_dict, metric) for metric in _VALID_SELECTION_METRICS
    }
    result_hash = v2_hash_object(
        {
            "trial_id": trial_id,
            "trial_index": trial_index,
            "seed": seed,
            "config_hash": config_hash,
            "training_summary": summary_dict,
            "selection_metric": config.selection_metric,
            "selection_metric_value": metric_value,
            "success": success,
            "error_code": error_code,
        }
    )
    checkpoint_ref = (
        {
            "trial_id": trial_id,
            "checkpoint_uri": f"manifest-ref://v2-tuning/{trial_id}",
            "format": "manifest_ref",
            "result_hash": result_hash,
        }
        if success
        else None
    )
    return V2TrialResult(
        trial_id=trial_id,
        trial_index=trial_index,
        seed=seed,
        status=status,
        success=success,
        selected=False,
        config_hash=config_hash,
        result_hash=result_hash,
        selection_metric_name=config.selection_metric,
        selection_metric_value=metric_value if success else None,
        metric_values=metric_values,
        checkpoint_ref=checkpoint_ref,
        error_code=error_code,
        error_message=error_message,
        training_summary=summary_dict,
        warnings=tuple(str(item) for item in summary_dict.get("warnings", [])),
        diagnostics=tuple(
            item if isinstance(item, Mapping) else {"diagnostic": str(item)}
            for item in summary_dict.get("diagnostics", [])
            if isinstance(summary_dict.get("diagnostics", []), list)
        ),
    )


def _extract_metric(summary: Mapping[str, object], metric: str) -> Optional[float]:
    loss = summary.get("loss_report")
    if not isinstance(loss, Mapping):
        return None
    if metric == "total_loss":
        return _as_float(loss.get("total_loss"))
    components = loss.get("components")
    if isinstance(components, Mapping):
        return _as_float(components.get(metric))
    return None


def _select_trial(
    trials: tuple[V2TrialResult, ...],
    mode: str,
) -> tuple[Optional[V2TrialResult], str]:
    candidates = [
        trial for trial in trials if trial.success and trial.selection_metric_value is not None
    ]
    if not candidates:
        return None, "no successful trial with computable frozen metric; no checkpoint selected"
    reverse = mode == "maximize"
    selected = sorted(
        candidates,
        key=lambda trial: (
            -float(trial.selection_metric_value)
            if reverse
            else float(trial.selection_metric_value),
            trial.trial_index,
        ),
    )[0]
    return (
        selected,
        (
            f"{selected.trial_id} selected by frozen metric "
            f"{selected.selection_metric_name}={selected.selection_metric_value} "
            f"using {mode}; failed trials excluded from selection"
        ),
    )


def _config_failure(code: str, message: str, location: str) -> ContractEnvelope[V2TuningSummary]:
    summary = V2TuningSummary(
        success=False,
        trial_count=0,
        runtime_budget_seconds=0,
        seeds=(),
        selection_metric="",
        selection_mode="",
        selected_trial_id=None,
        selected_checkpoint_ref=None,
        best_metric_value=None,
        selection_justification="configuration rejected before trial execution",
        trials=(),
        failed_trials=(),
        successful_count=0,
        failed_count=0,
        sweep_config_hash="",
        config={"config_path": location},
        error_code=code,
        error_message=message,
    )
    return _envelope(summary, errors=(_error(code, message, location),))


def _envelope(
    summary: V2TuningSummary,
    *,
    errors: tuple[ContractErrorInfo, ...] = (),
) -> ContractEnvelope[V2TuningSummary]:
    return ContractEnvelope(
        payload=summary,
        artifacts=(),
        receipt=ValidationReceipt(
            validator=VALIDATOR_NAME,
            contract_version=CONTRACT_VERSION,
            input_sha256=_summary_hash(summary).removeprefix("sha256:"),
            passed=not errors,
            errors=errors,
        ),
        provenance=Provenance(),
    )


def _summary_hash(summary: V2TuningSummary) -> str:
    data = v2_tuning_summary_to_dict(replace(summary, sweep_result_hash=""))
    return v2_hash_object(data)


def _parse_int_tuple(value: object) -> tuple[int, ...]:
    if isinstance(value, str):
        parts = [part.strip() for part in value.split(",") if part.strip()]
    elif isinstance(value, (list, tuple)):
        parts = list(value)
    else:
        raise ValueError("seeds must be a comma-separated string or list")
    try:
        return tuple(int(part) for part in parts)
    except (TypeError, ValueError) as exc:
        raise ValueError("seeds must contain integers") from exc


def _parse_str_tuple(value: object) -> tuple[str, ...]:
    if value is None or value == "":
        return ()
    if isinstance(value, str):
        return tuple(part.strip() for part in value.split(",") if part.strip())
    if isinstance(value, (list, tuple)):
        return tuple(str(part) for part in value)
    return (str(value),)


def _as_float(value: object) -> Optional[float]:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


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
    "V2TinySweepConfig",
    "V2TrialResult",
    "V2TuningSummary",
    "V2_TUNE_CONFIG_MISSING",
    "V2_TUNE_CONFIG_UNREADABLE",
    "V2_TUNE_DEVICE_UNSUPPORTED",
    "V2_TUNE_METRIC_NOT_COMPUTABLE",
    "V2_TUNE_MODEL_MODE_UNSUPPORTED",
    "V2_TUNE_NO_SUCCESSFUL_TRIALS",
    "V2_TUNE_RUNTIME_BUDGET_INVALID",
    "V2_TUNE_RUNTIME_BUDGET_MISSING",
    "V2_TUNE_SEEDS_COUNT_MISMATCH",
    "V2_TUNE_SEEDS_DUPLICATE",
    "V2_TUNE_SEEDS_INVALID",
    "V2_TUNE_SEEDS_MISSING",
    "V2_TUNE_SELECTION_METRIC_MISSING",
    "V2_TUNE_SELECTION_METRIC_UNSUPPORTED",
    "V2_TUNE_SELECTION_MODE_UNSUPPORTED",
    "V2_TUNE_TASK49_INPUTS_MISSING",
    "V2_TUNE_TRIAL_COUNT_INVALID",
    "V2_TUNE_TRIAL_COUNT_MISSING",
    "run_v2_tune",
    "v2_trial_result_to_dict",
    "v2_tuning_summary_to_dict",
]
