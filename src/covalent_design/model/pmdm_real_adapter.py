"""Task 47 real-PMDM adapter smoke boundary.

PMDM is currently blocked by unknown upstream license status.  This module
therefore defines the project-owned status, vocabulary, and validation boundary
without importing, loading, or executing PMDM.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import ModuleType
from typing import Mapping, Optional

from covalent_design.contracts.errors import ContractError, ContractErrorInfo
from covalent_design.contracts.types import (
    CONTRACT_VERSION,
    ContractEnvelope,
    ModelBatch,
    ModelForwardOutput,
    Provenance,
    ValidationReceipt,
)
from covalent_design.model.config import ModelConfig
from covalent_design.model.pmdm_adapter import (
    ALL_PMDM_OUTPUT_KEYS,
    OPTIONAL_PMDM_OUTPUT_KEYS,
    REQUIRED_PMDM_OUTPUT_KEYS,
)

PMDM_REAL_LICENSE_BLOCKED = "PMDM_REAL_LICENSE_BLOCKED"
PMDM_REAL_UNAVAILABLE = "PMDM_REAL_UNAVAILABLE"
PMDM_REAL_API_MISMATCH = "PMDM_REAL_API_MISMATCH"
PMDM_REAL_MISSING_REQUIRED_KEY = "PMDM_REAL_MISSING_REQUIRED_KEY"
PMDM_REAL_MISSING_OPTIONAL_KEY = "PMDM_REAL_MISSING_OPTIONAL_KEY"
PMDM_REAL_UNEXPECTED_OPTIONAL_KEY = "PMDM_REAL_UNEXPECTED_OPTIONAL_KEY"
PMDM_REAL_UNKNOWN_KEY = "PMDM_REAL_UNKNOWN_KEY"
PMDM_REAL_SHAPE_MISMATCH = "PMDM_REAL_SHAPE_MISMATCH"
PMDM_REAL_UNSERIALIZABLE_PAYLOAD = "PMDM_REAL_UNSERIALIZABLE_PAYLOAD"

PMDM_REAL_ERROR_CODES = (
    PMDM_REAL_LICENSE_BLOCKED,
    PMDM_REAL_UNAVAILABLE,
    PMDM_REAL_API_MISMATCH,
    PMDM_REAL_MISSING_REQUIRED_KEY,
    PMDM_REAL_MISSING_OPTIONAL_KEY,
    PMDM_REAL_UNEXPECTED_OPTIONAL_KEY,
    PMDM_REAL_UNKNOWN_KEY,
    PMDM_REAL_SHAPE_MISMATCH,
    PMDM_REAL_UNSERIALIZABLE_PAYLOAD,
)

_VALIDATOR = "covalent_design.model.pmdm_real_adapter"
_LICENSE_UNKNOWN_REASON = "license_unknown"


@dataclass(frozen=True)
class PmdmBackendStatus:
    status: str
    license_status: str
    import_attempted: bool
    reason: Optional[str] = None
    pmdm_version: Optional[str] = None
    pmdm_path: Optional[str] = None
    available_keys: tuple[str, ...] = ()
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    diagnostics: tuple[Mapping[str, object], ...] = ()


@dataclass(frozen=True)
class PmdmOutputSpec:
    required_keys: tuple[str, ...]
    optional_keys: tuple[str, ...]
    expected_shapes: Mapping[str, tuple[int, ...]]
    enabled_optional_keys: tuple[str, ...]
    contract_version: str = CONTRACT_VERSION


def check_pmdm_available() -> PmdmBackendStatus:
    """Return the current real-PMDM dependency status.

    The current project decision is fail-closed: PMDM license is unknown, so no
    PMDM import attempt is permitted.  This function intentionally does not use
    importlib for PMDM while that status remains blocked.
    """

    return PmdmBackendStatus(
        status="unavailable",
        license_status="unknown",
        import_attempted=False,
        reason=_LICENSE_UNKNOWN_REASON,
        error_code=PMDM_REAL_LICENSE_BLOCKED,
        error_message=(
            "PMDM is blocked because upstream license status is unknown; "
            "real PMDM import, load, or execution is disabled."
        ),
        diagnostics=(
            {
                "category": "dependency",
                "dependency": "PMDM",
                "status": "blocked",
                "reason": _LICENSE_UNKNOWN_REASON,
            },
        ),
    )


def pmdm_backend_status_to_dict(status: PmdmBackendStatus) -> dict[str, object]:
    return {
        "status": status.status,
        "license_status": status.license_status,
        "import_attempted": status.import_attempted,
        "reason": status.reason,
        "pmdm_version": status.pmdm_version,
        "pmdm_path": status.pmdm_path,
        "available_keys": list(status.available_keys),
        "error_code": status.error_code,
        "error_message": status.error_message,
        "diagnostics": [dict(item) for item in status.diagnostics],
    }


def pmdm_output_spec_from_config(
    batch: ModelBatch,
    config: object,
) -> PmdmOutputSpec:
    cfg = _normalize_config(config)
    tensors = batch.tensors
    batch_size = tensors.protein_coords_shape[0]
    ligand_count = tensors.ligand_coords_shape[1]
    protein_count = tensors.protein_coords_shape[1]

    shapes = {
        "ligand_atom_features": (
            batch_size,
            ligand_count,
            cfg.ligand_feature_dim,
        ),
        "protein_atom_features": (
            batch_size,
            protein_count,
            cfg.protein_feature_dim,
        ),
        "ligand_coords_denoised": (batch_size, ligand_count, 3),
        "position_loss": (),
        "atom_type_loss": (),
        "timestep": (),
        "num_atom": (batch_size,),
    }
    enabled_optional = []
    if cfg.ligand_pair_feature_dim > 0:
        shapes["ligand_pair_features"] = (
            batch_size,
            ligand_count,
            ligand_count,
            cfg.ligand_pair_feature_dim,
        )
        enabled_optional.append("ligand_pair_features")
    if cfg.protein_ligand_pair_feature_dim > 0:
        shapes["protein_ligand_pair_features"] = (
            batch_size,
            protein_count,
            ligand_count,
            cfg.protein_ligand_pair_feature_dim,
        )
        enabled_optional.append("protein_ligand_pair_features")

    return PmdmOutputSpec(
        required_keys=REQUIRED_PMDM_OUTPUT_KEYS,
        optional_keys=OPTIONAL_PMDM_OUTPUT_KEYS,
        expected_shapes=shapes,
        enabled_optional_keys=tuple(enabled_optional),
        contract_version=cfg.contract_version,
    )


def pmdm_output_spec_to_dict(spec: PmdmOutputSpec) -> dict[str, object]:
    return {
        "contract_version": spec.contract_version,
        "required_keys": list(spec.required_keys),
        "optional_keys": list(spec.optional_keys),
        "enabled_optional_keys": list(spec.enabled_optional_keys),
        "expected_shapes": {
            key: list(value)
            for key, value in sorted(spec.expected_shapes.items())
        },
    }


def validate_real_pmdm_outputs(
    pmdm_outputs: Mapping[str, object],
    *,
    batch: ModelBatch,
    config: object,
) -> None:
    spec = pmdm_output_spec_from_config(batch, config)

    for key in REQUIRED_PMDM_OUTPUT_KEYS:
        if key not in pmdm_outputs:
            raise _contract_error(
                PMDM_REAL_MISSING_REQUIRED_KEY,
                f"real PMDM output missing required key {key!r}",
                details={"key": key},
            )

    allowed = set(ALL_PMDM_OUTPUT_KEYS)
    for key, value in sorted(pmdm_outputs.items()):
        if key not in allowed:
            raise _contract_error(
                PMDM_REAL_UNKNOWN_KEY,
                f"real PMDM output contains unknown key {key!r}",
                details={"key": key},
            )
        _ensure_json_safe(value, key=key)

    enabled_optional = set(spec.enabled_optional_keys)
    for key in OPTIONAL_PMDM_OUTPUT_KEYS:
        is_present = key in pmdm_outputs
        should_be_present = key in enabled_optional
        if should_be_present and not is_present:
            raise _contract_error(
                PMDM_REAL_MISSING_OPTIONAL_KEY,
                f"real PMDM output missing enabled optional key {key!r}",
                details={"key": key},
            )
        if is_present and not should_be_present:
            raise _contract_error(
                PMDM_REAL_UNEXPECTED_OPTIONAL_KEY,
                f"real PMDM output contains disabled optional key {key!r}",
                details={"key": key},
            )

    for key, expected in sorted(spec.expected_shapes.items()):
        actual = _shape_of(pmdm_outputs[key])
        if actual != expected:
            raise _contract_error(
                PMDM_REAL_SHAPE_MISMATCH,
                f"real PMDM output {key!r} shape {actual} != expected {expected}",
                details={
                    "key": key,
                    "expected": list(expected),
                    "actual": list(actual),
                },
            )


def forward_pmdm_real(
    *,
    batch: ModelBatch,
    config: object,
    timestep: float = 0.5,
) -> ContractEnvelope[Optional[ModelForwardOutput]]:
    """Real PMDM forward boundary.

    While PMDM is license-blocked this returns a failed envelope and never
    silently substitutes the Task 48 baseline path.
    """

    del batch, config, timestep
    status = check_pmdm_available()
    return _failure(
        _error(
            PMDM_REAL_LICENSE_BLOCKED,
            "PMDM mode is unavailable because PMDM license status is unknown.",
            details={
                "status": status.status,
                "license_status": status.license_status,
                "reason": status.reason,
                "import_attempted": status.import_attempted,
            },
        )
    )


def _normalize_config(config: object) -> ModelConfig:
    if all(
        hasattr(config, name)
        for name in (
            "contract_version",
            "rule_table_hash",
            "ligand_feature_dim",
            "protein_feature_dim",
            "ligand_pair_feature_dim",
            "protein_ligand_pair_feature_dim",
        )
    ):
        return ModelConfig(
            contract_version=str(getattr(config, "contract_version")),
            rule_table_hash=str(getattr(config, "rule_table_hash")),
            fake_backbone=bool(getattr(config, "fake_backbone", True)),
            hidden_dim=int(getattr(config, "hidden_dim", 256)),
            ligand_feature_dim=int(getattr(config, "ligand_feature_dim")),
            protein_feature_dim=int(getattr(config, "protein_feature_dim")),
            ligand_pair_feature_dim=int(getattr(config, "ligand_pair_feature_dim")),
            protein_ligand_pair_feature_dim=int(
                getattr(config, "protein_ligand_pair_feature_dim")
            ),
            seed=int(getattr(config, "seed", 42)),
            candidate_radius_angstrom=float(
                getattr(config, "candidate_radius_angstrom", 4.0)
            ),
        )
    if isinstance(config, Mapping):
        return ModelConfig(
            contract_version=str(config.get("contract_version", CONTRACT_VERSION)),
            rule_table_hash=str(config.get("rule_table_hash", "")),
            fake_backbone=bool(config.get("fake_backbone", True)),
            hidden_dim=int(config.get("hidden_dim", 256)),
            ligand_feature_dim=int(config.get("ligand_feature_dim", 128)),
            protein_feature_dim=int(config.get("protein_feature_dim", 128)),
            ligand_pair_feature_dim=int(
                config.get(
                    "ligand_pair_feature_dim",
                    config.get("pair_feature_dim", 0),
                )
            ),
            protein_ligand_pair_feature_dim=int(
                config.get(
                    "protein_ligand_pair_feature_dim",
                    config.get("cross_feature_dim", 0),
                )
            ),
            seed=int(config.get("seed", 42)),
            candidate_radius_angstrom=float(
                config.get("candidate_radius_angstrom", 4.0)
            ),
        )
    raise TypeError(f"Unsupported PMDM real adapter config type: {type(config).__name__}")


def _shape_of(value: object) -> tuple[int, ...]:
    if isinstance(value, (int, float, type(None))):
        return ()
    if isinstance(value, (list, tuple)):
        if not value:
            return (0,)
        inner = _shape_of(value[0])
        return (len(value),) + inner
    shape = getattr(value, "shape", None)
    if shape is not None:
        return tuple(int(dim) for dim in shape)
    return ()


def _ensure_json_safe(value: object, *, key: str) -> None:
    if value is None or isinstance(value, (str, int, float, bool)):
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            _ensure_json_safe(item, key=key)
        return
    if isinstance(value, Mapping):
        for map_key, map_value in value.items():
            if not isinstance(map_key, str):
                raise _contract_error(
                    PMDM_REAL_UNSERIALIZABLE_PAYLOAD,
                    f"real PMDM output {key!r} contains a non-string mapping key",
                    details={"key": key},
                )
            _ensure_json_safe(map_value, key=key)
        return
    if isinstance(value, ModuleType) or getattr(value, "__module__", "").startswith(
        ("torch", "rdkit", "PMDM", "PocketFlow")
    ):
        raise _contract_error(
            PMDM_REAL_UNSERIALIZABLE_PAYLOAD,
            f"real PMDM output {key!r} exposes a raw dependency object",
            details={"key": key, "type": type(value).__name__},
        )
    raise _contract_error(
        PMDM_REAL_UNSERIALIZABLE_PAYLOAD,
        f"real PMDM output {key!r} is not JSON-serializable",
        details={"key": key, "type": type(value).__name__},
    )


def _failure(
    error: ContractErrorInfo,
) -> ContractEnvelope[Optional[ModelForwardOutput]]:
    return ContractEnvelope(
        payload=None,
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


def _contract_error(
    code: str,
    message: str,
    *,
    details: Optional[Mapping[str, object]] = None,
) -> ContractError:
    return ContractError(
        code=code,
        owner="model",
        message=message,
        details=details or {},
    )


def _error(
    code: str,
    message: str,
    *,
    details: Optional[Mapping[str, object]] = None,
) -> ContractErrorInfo:
    return ContractErrorInfo(
        code=code,
        owner="model",
        message=message,
        details=details or {},
    )


__all__ = [
    "ALL_PMDM_OUTPUT_KEYS",
    "OPTIONAL_PMDM_OUTPUT_KEYS",
    "PMDM_REAL_ERROR_CODES",
    "PMDM_REAL_LICENSE_BLOCKED",
    "PMDM_REAL_UNAVAILABLE",
    "PmdmBackendStatus",
    "PmdmOutputSpec",
    "REQUIRED_PMDM_OUTPUT_KEYS",
    "check_pmdm_available",
    "forward_pmdm_real",
    "pmdm_backend_status_to_dict",
    "pmdm_output_spec_from_config",
    "pmdm_output_spec_to_dict",
    "validate_real_pmdm_outputs",
]
