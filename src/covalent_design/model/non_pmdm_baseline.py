"""Explicit non-PMDM baseline forward path for Task 48.

This module provides a deterministic, PMDM-free smoke path. It is selected
explicitly with ``baseline_mode="non_pmdm_baseline"`` and is never an automatic
fallback from the license-blocked real PMDM path.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Mapping, Optional

from covalent_design.contracts.errors import ContractErrorInfo
from covalent_design.contracts.types import (
    CONTRACT_VERSION,
    MESSAGE_WEIGHT_SOURCE_DETACHED_EDGE_PROBABILITY,
    ContractEnvelope,
    ModelForwardOutput,
    Provenance,
    ValidationReceipt,
)
from covalent_design.model.pmdm_adapter import (
    ALL_PMDM_OUTPUT_KEYS,
    OPTIONAL_PMDM_OUTPUT_KEYS,
    REQUIRED_PMDM_OUTPUT_KEYS,
    SMOKE_PLACEHOLDER,
    validate_pmdm_outputs,
)

BASELINE_MODE_PMDM = "pmdm"
BASELINE_MODE_NON_PMDM = "non_pmdm_baseline"
BASELINE_MODE_NOT_SELECTED = "not_selected"
ALLOWED_BASELINE_MODES = (
    BASELINE_MODE_PMDM,
    BASELINE_MODE_NON_PMDM,
    BASELINE_MODE_NOT_SELECTED,
)

BASELINE_NOT_PMDM_WARNING = "baseline is not PMDM; this is a smoke-only path"

BASELINE_MODE_UNSUPPORTED = "BASELINE_MODE_UNSUPPORTED"
BASELINE_MODE_MISMATCH = "BASELINE_MODE_MISMATCH"
BASELINE_MODE_NOT_SELECTED_CODE = "BASELINE_MODE_NOT_SELECTED"
BASELINE_BACKEND_UNAVAILABLE = "BASELINE_BACKEND_UNAVAILABLE"
BASELINE_CONFIG_INVALID = "BASELINE_CONFIG_INVALID"
BASELINE_NOT_PMDM_WARNING_CODE = "BASELINE_NOT_PMDM_WARNING"

BASELINE_ERROR_CODES = (
    BASELINE_MODE_UNSUPPORTED,
    BASELINE_MODE_MISMATCH,
    BASELINE_MODE_NOT_SELECTED_CODE,
    BASELINE_BACKEND_UNAVAILABLE,
    BASELINE_CONFIG_INVALID,
)


@dataclass(frozen=True)
class NonPmdmBaselineStatus:
    """Serializable status for the explicit non-PMDM baseline path."""

    status: str = "available"
    baseline_mode: str = BASELINE_MODE_NON_PMDM
    is_pmdm: bool = False
    pmdm_import_attempted: bool = False
    deterministic: bool = True
    warning: str = BASELINE_NOT_PMDM_WARNING
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    diagnostics: tuple[Mapping[str, object], ...] = (
        {
            "category": "baseline",
            "status": BASELINE_MODE_NON_PMDM,
            "warning": BASELINE_NOT_PMDM_WARNING,
        },
    )


@dataclass(frozen=True)
class BaselineModeSelection:
    """Audit record for a caller's explicit model-mode selection."""

    selected_mode: str
    accepted: bool
    baseline_mode: str = BASELINE_MODE_NON_PMDM
    is_pmdm: bool = False
    warning: Optional[str] = BASELINE_NOT_PMDM_WARNING
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    diagnostics: tuple[Mapping[str, object], ...] = ()


def _info(
    *,
    code: str,
    message: str,
    details: Optional[Mapping[str, object]] = None,
) -> ContractErrorInfo:
    return ContractErrorInfo(
        code=code,
        owner="model",
        message=message,
        details=dict(details or {}),
    )


def _receipt(
    *,
    passed: bool,
    warnings: tuple[ContractErrorInfo, ...] = (),
    errors: tuple[ContractErrorInfo, ...] = (),
) -> ValidationReceipt:
    return ValidationReceipt(
        validator="covalent_design.model.non_pmdm_baseline",
        contract_version=CONTRACT_VERSION,
        input_sha256="not_applicable",
        passed=passed,
        warnings=warnings,
        errors=errors,
    )


def _failed_envelope(error: ContractErrorInfo) -> ContractEnvelope[Optional[ModelForwardOutput]]:
    return ContractEnvelope(
        payload=None,
        artifacts=(),
        receipt=_receipt(passed=False, errors=(error,)),
        provenance=Provenance(),
    )


def _get_shape(obj: object) -> tuple[int, ...]:
    if isinstance(obj, (int, float, type(None))):
        return ()
    if isinstance(obj, list):
        if not obj:
            return (0,)
        return (len(obj),) + _get_shape(obj[0])
    return ()


def _normalize_config(config: object) -> dict[str, object]:
    """Accept ModelConfig-like objects or flat dict configs."""
    if hasattr(config, "ligand_feature_dim"):
        ligand_pair_dim = int(getattr(config, "ligand_pair_feature_dim", 0))
        cross_pair_dim = int(getattr(config, "protein_ligand_pair_feature_dim", 0))
        return {
            "ligand_feature_dim": int(getattr(config, "ligand_feature_dim")),
            "protein_feature_dim": int(getattr(config, "protein_feature_dim")),
            "pair_feature_dim": ligand_pair_dim,
            "cross_feature_dim": cross_pair_dim,
            "enable_ligand_pair": ligand_pair_dim > 0,
            "enable_cross_pair": cross_pair_dim > 0,
            "seed": int(getattr(config, "seed", 42)),
        }

    if not isinstance(config, Mapping):
        raise TypeError("config must be a ModelConfig-like object or mapping")

    enable_optional = bool(config.get("enable_optional_pair_features", False))
    pair_dim = int(config.get("pair_feature_dim", 0))
    cross_dim = int(config.get("cross_feature_dim", 0))
    if enable_optional:
        enable_ligand_pair = True
        enable_cross_pair = True
    else:
        enable_ligand_pair = pair_dim > 0
        enable_cross_pair = cross_dim > 0
    return {
        "ligand_feature_dim": int(config.get("ligand_feature_dim", 128)),
        "protein_feature_dim": int(config.get("protein_feature_dim", 128)),
        "pair_feature_dim": pair_dim,
        "cross_feature_dim": cross_dim,
        "enable_ligand_pair": enable_ligand_pair,
        "enable_cross_pair": enable_cross_pair,
        "seed": int(config.get("seed", 42)),
    }


def _zeros(shape: tuple[int, ...]) -> object:
    if not shape:
        return 0.0
    size = shape[0]
    return [_zeros(shape[1:]) for _ in range(size)]


def _build_baseline_pmdm_outputs(
    tensors: object,
    *,
    config: object,
    timestep: float,
) -> dict[str, object]:
    cfg = _normalize_config(config)
    batch_size = tensors.protein_coords_shape[0]
    ligand_atoms = tensors.ligand_coords_shape[1]
    protein_atoms = tensors.protein_coords_shape[1]
    ligand_feature_dim = int(cfg["ligand_feature_dim"])
    protein_feature_dim = int(cfg["protein_feature_dim"])

    outputs: dict[str, object] = {
        "ligand_atom_features": _zeros((batch_size, ligand_atoms, ligand_feature_dim)),
        "protein_atom_features": _zeros((batch_size, protein_atoms, protein_feature_dim)),
        "ligand_coords_denoised": _zeros((batch_size, ligand_atoms, 3)),
        "position_loss": 0.0,
        "atom_type_loss": 0.0,
        "timestep": float(timestep),
        "num_atom": [ligand_atoms for _ in range(batch_size)],
    }

    if bool(cfg["enable_ligand_pair"]):
        outputs["ligand_pair_features"] = _zeros(
            (batch_size, ligand_atoms, ligand_atoms, int(cfg["pair_feature_dim"]))
        )
    if bool(cfg["enable_cross_pair"]):
        outputs["protein_ligand_pair_features"] = _zeros(
            (batch_size, protein_atoms, ligand_atoms, int(cfg["cross_feature_dim"]))
        )
    return outputs


def _selection_error(requested_mode: str) -> ContractErrorInfo:
    if requested_mode == BASELINE_MODE_NOT_SELECTED:
        return _info(
            code=BASELINE_MODE_NOT_SELECTED_CODE,
            message="non-PMDM baseline was not explicitly selected",
            details={
                "requested_mode": requested_mode,
                "required_mode": BASELINE_MODE_NON_PMDM,
            },
        )
    if requested_mode == BASELINE_MODE_PMDM:
        return _info(
            code=BASELINE_MODE_MISMATCH,
            message=(
                "PMDM mode was requested; non-PMDM baseline must not be used as "
                "an automatic fallback"
            ),
            details={
                "selected_mode": requested_mode,
                "required_mode": BASELINE_MODE_NON_PMDM,
            },
        )
    return _info(
        code=BASELINE_MODE_UNSUPPORTED,
        message=f"unsupported baseline mode {requested_mode!r}",
        details={
            "selected_mode": requested_mode,
            "allowed_modes": list(ALLOWED_BASELINE_MODES),
        },
    )


def select_baseline_mode(requested_mode: str) -> BaselineModeSelection:
    """Validate an explicit model-mode choice for Task 48."""
    if requested_mode == BASELINE_MODE_NON_PMDM:
        return BaselineModeSelection(
            selected_mode=requested_mode,
            accepted=True,
            diagnostics=(
                {
                    "category": "baseline",
                    "status": BASELINE_MODE_NON_PMDM,
                    "warning": BASELINE_NOT_PMDM_WARNING,
                },
            ),
        )
    error = _selection_error(requested_mode)
    return BaselineModeSelection(
        selected_mode=requested_mode,
        accepted=False,
        warning=None,
        error_code=error.code,
        error_message=error.message,
        diagnostics=(
            {
                "category": "baseline",
                "status": "rejected",
                "requested_mode": requested_mode,
                "error_code": error.code,
            },
        ),
    )


def check_baseline_mode(requested_mode: str) -> BaselineModeSelection:
    """Alias for callers that want a status object instead of forwarding."""
    return select_baseline_mode(requested_mode)


def check_baseline_available() -> NonPmdmBaselineStatus:
    """Return the structured availability of the dependency-free baseline."""
    return NonPmdmBaselineStatus()


def baseline_status_to_dict(status: NonPmdmBaselineStatus) -> dict[str, object]:
    return {
        "status": status.status,
        "baseline_mode": status.baseline_mode,
        "is_pmdm": status.is_pmdm,
        "pmdm_import_attempted": status.pmdm_import_attempted,
        "deterministic": status.deterministic,
        "warning": status.warning,
        "error_code": status.error_code,
        "error_message": status.error_message,
        "diagnostics": [dict(item) for item in status.diagnostics],
    }


def baseline_mode_selection_to_dict(selection: BaselineModeSelection) -> dict[str, object]:
    return {
        "selected_mode": selection.selected_mode,
        "accepted": selection.accepted,
        "baseline_mode": selection.baseline_mode,
        "is_pmdm": selection.is_pmdm,
        "warning": selection.warning,
        "error_code": selection.error_code,
        "error_message": selection.error_message,
        "diagnostics": [dict(item) for item in selection.diagnostics],
    }


def validate_baseline_pmdm_outputs(
    pmdm_outputs: dict[str, object],
    *,
    batch: object,
    config: object,
) -> None:
    """Validate baseline outputs against the existing PMDM smoke vocabulary."""
    validate_pmdm_outputs(pmdm_outputs, batch=batch, config=config)


def forward_non_pmdm_baseline(
    *,
    batch: object,
    config: object,
    timestep: float = 0.5,
    baseline_mode: str = BASELINE_MODE_NOT_SELECTED,
) -> ContractEnvelope[Optional[ModelForwardOutput]]:
    """Run the explicit, deterministic non-PMDM baseline path.

    The default mode is ``not_selected`` so callers cannot enter this path by
    omission. A successful payload is produced only when the caller passes
    ``baseline_mode="non_pmdm_baseline"``.
    """
    selection = select_baseline_mode(baseline_mode)
    if not selection.accepted:
        return _failed_envelope(_selection_error(baseline_mode))

    pmdm_outputs = _build_baseline_pmdm_outputs(
        batch.tensors,
        config=config,
        timestep=timestep,
    )
    validate_baseline_pmdm_outputs(pmdm_outputs, batch=batch, config=config)

    output = ModelForwardOutput(
        pmdm_outputs=pmdm_outputs,
        edge_logits=SMOKE_PLACEHOLDER,
        bond_type_logits=SMOKE_PLACEHOLDER,
        family_logits=SMOKE_PLACEHOLDER,
        edge_prob_message_weights=SMOKE_PLACEHOLDER,
        message_weight_source=MESSAGE_WEIGHT_SOURCE_DETACHED_EDGE_PROBABILITY,
        denominators_observed=batch.denominators_expected,
    )
    warning = _info(
        code=BASELINE_NOT_PMDM_WARNING_CODE,
        message=BASELINE_NOT_PMDM_WARNING,
        details={
            "baseline_mode": BASELINE_MODE_NON_PMDM,
            "is_pmdm": False,
            "required_keys": list(REQUIRED_PMDM_OUTPUT_KEYS),
            "optional_keys": list(OPTIONAL_PMDM_OUTPUT_KEYS),
        },
    )
    return ContractEnvelope(
        payload=output,
        artifacts=(),
        receipt=_receipt(passed=True, warnings=(warning,)),
        provenance=Provenance(),
    )


def _error_info_to_dict(error: ContractErrorInfo) -> dict[str, object]:
    return {
        "code": error.code,
        "owner": error.owner,
        "message": error.message,
        "location": error.location,
        "details": dict(error.details),
    }


def _forward_output_to_dict(output: Optional[ModelForwardOutput]) -> Optional[dict[str, object]]:
    if output is None:
        return None
    return {
        "pmdm_outputs": dict(output.pmdm_outputs),
        "edge_logits": repr(output.edge_logits),
        "bond_type_logits": repr(output.bond_type_logits),
        "family_logits": repr(output.family_logits),
        "edge_prob_message_weights": repr(output.edge_prob_message_weights),
        "message_weight_source": output.message_weight_source,
        "denominators_observed": asdict(output.denominators_observed),
        "baseline_mode": BASELINE_MODE_NON_PMDM,
        "is_pmdm": False,
        "warning": BASELINE_NOT_PMDM_WARNING,
    }


def baseline_envelope_to_dict(
    envelope: ContractEnvelope[Optional[ModelForwardOutput]],
) -> dict[str, object]:
    """Serialize a baseline envelope without exposing raw dependency objects."""
    return {
        "payload": _forward_output_to_dict(envelope.payload),
        "artifacts": [asdict(artifact) for artifact in envelope.artifacts],
        "receipt": {
            "validator": envelope.receipt.validator,
            "contract_version": envelope.receipt.contract_version,
            "input_sha256": envelope.receipt.input_sha256,
            "passed": envelope.receipt.passed,
            "warnings": [_error_info_to_dict(item) for item in envelope.receipt.warnings],
            "errors": [_error_info_to_dict(item) for item in envelope.receipt.errors],
        },
        "provenance": {
            "producer_name": envelope.provenance.producer_name,
            "producer_version": envelope.provenance.producer_version,
            "git_commit": envelope.provenance.git_commit,
            "inputs": {key: asdict(value) for key, value in envelope.provenance.inputs.items()},
        },
        "baseline_mode": BASELINE_MODE_NON_PMDM,
        "is_pmdm": False,
        "warning": BASELINE_NOT_PMDM_WARNING,
    }


__all__ = [
    "ALL_PMDM_OUTPUT_KEYS",
    "ALLOWED_BASELINE_MODES",
    "BASELINE_ERROR_CODES",
    "BASELINE_MODE_NON_PMDM",
    "BASELINE_MODE_NOT_SELECTED",
    "BASELINE_MODE_PMDM",
    "BASELINE_NOT_PMDM_WARNING",
    "BASELINE_NOT_PMDM_WARNING_CODE",
    "BaselineModeSelection",
    "NonPmdmBaselineStatus",
    "OPTIONAL_PMDM_OUTPUT_KEYS",
    "REQUIRED_PMDM_OUTPUT_KEYS",
    "baseline_envelope_to_dict",
    "baseline_mode_selection_to_dict",
    "baseline_status_to_dict",
    "check_baseline_available",
    "check_baseline_mode",
    "forward_non_pmdm_baseline",
    "select_baseline_mode",
    "validate_baseline_pmdm_outputs",
]