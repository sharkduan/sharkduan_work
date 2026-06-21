"""Task 46: optional PyTorch tensor backend boundary.

Importing this module must not import PyTorch. Real ``torch.Tensor`` objects
only appear in ``TorchTensorBatch``, an internal runtime object. Public
metadata is exposed through JSON-safe specs.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Mapping, Optional

from covalent_design.contracts.errors import ContractErrorInfo
from covalent_design.contracts.types import (
    CONTRACT_VERSION,
    SCHEMA_VERSION,
    BatchTensors,
    ContractEnvelope,
    ModelBatch,
    Provenance,
    ValidationReceipt,
)

TORCH_BACKEND_UNAVAILABLE = "TORCH_BACKEND_UNAVAILABLE"
TORCH_BACKEND_EMPTY_BATCH = "TORCH_BACKEND_EMPTY_BATCH"
TORCH_BACKEND_TENSOR_METADATA_MISSING = "TORCH_BACKEND_TENSOR_METADATA_MISSING"
TORCH_BACKEND_SHAPE_MISMATCH = "TORCH_BACKEND_SHAPE_MISMATCH"
TORCH_BACKEND_DTYPE_UNSUPPORTED = "TORCH_BACKEND_DTYPE_UNSUPPORTED"
TORCH_BACKEND_DEVICE_UNAVAILABLE = "TORCH_BACKEND_DEVICE_UNAVAILABLE"
TORCH_BACKEND_CONVERSION_FAILED = "TORCH_BACKEND_CONVERSION_FAILED"

TORCH_BACKEND_ERROR_CODES = (
    TORCH_BACKEND_UNAVAILABLE,
    TORCH_BACKEND_EMPTY_BATCH,
    TORCH_BACKEND_TENSOR_METADATA_MISSING,
    TORCH_BACKEND_SHAPE_MISMATCH,
    TORCH_BACKEND_DTYPE_UNSUPPORTED,
    TORCH_BACKEND_DEVICE_UNAVAILABLE,
    TORCH_BACKEND_CONVERSION_FAILED,
)

_VALIDATOR = "covalent_design.model.torch_backend"
_DEFAULT_DEVICE = "cpu"


@dataclass(frozen=True)
class TorchBackendStatus:
    status: str
    torch_version: Optional[str]
    cuda_available: bool
    cuda_version: Optional[str]
    default_device: str = _DEFAULT_DEVICE
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    diagnostics: tuple[Mapping[str, object], ...] = ()


@dataclass(frozen=True)
class TensorMetadata:
    shape: tuple[int, ...]
    dtype: str
    device: str


@dataclass(frozen=True)
class TorchTensorSpec:
    record_ids: tuple[str, ...]
    tensors: Mapping[str, TensorMetadata]
    dtype: str
    index_dtype: str
    device: str
    coordinate_frame: str
    schema_version: str = SCHEMA_VERSION
    contract_version: str = CONTRACT_VERSION


@dataclass(frozen=True)
class TorchTensorBatch:
    """Internal runtime object that may contain real torch.Tensor values."""

    protein_coords: object
    ligand_coords: object
    protein_atom_types: object
    ligand_atom_types: object
    ligand_bonds: object
    edge_candidates: object
    positive_label_mask: object
    candidate_to_ligand_map: object
    candidate_to_protein_map: object
    record_ids: tuple[str, ...]
    batch_spec: object
    device: str
    dtype: str
    index_dtype: str
    coordinate_frame: str

    def to_spec(self) -> TorchTensorSpec:
        tensors = {
            "protein_coords": _metadata_from_tensor(self.protein_coords, "float32", self.device),
            "ligand_coords": _metadata_from_tensor(self.ligand_coords, "float32", self.device),
            "protein_atom_types": _metadata_from_tensor(self.protein_atom_types, "int64", self.device),
            "ligand_atom_types": _metadata_from_tensor(self.ligand_atom_types, "int64", self.device),
            "ligand_bonds": _metadata_from_tensor(self.ligand_bonds, "float32", self.device),
            "edge_candidates": _metadata_from_tensor(self.edge_candidates, "int64", self.device),
            "positive_label_mask": _metadata_from_tensor(self.positive_label_mask, "bool", self.device),
            "candidate_to_ligand_map": _metadata_from_tensor(self.candidate_to_ligand_map, "int64", self.device),
            "candidate_to_protein_map": _metadata_from_tensor(self.candidate_to_protein_map, "int64", self.device),
        }
        return TorchTensorSpec(
            record_ids=self.record_ids,
            tensors=tensors,
            dtype=self.dtype,
            index_dtype=self.index_dtype,
            device=self.device,
            coordinate_frame=self.coordinate_frame,
        )


def check_torch_available() -> TorchBackendStatus:
    try:
        torch = _load_torch()
    except ImportError as exc:
        return TorchBackendStatus(
            status="unavailable",
            torch_version=None,
            cuda_available=False,
            cuda_version=None,
            error_code=TORCH_BACKEND_UNAVAILABLE,
            error_message=str(exc),
            diagnostics=(
                {"category": "dependency", "dependency": "torch", "status": "unavailable"},
            ),
        )

    cuda_available = bool(torch.cuda.is_available())
    cuda_version = getattr(getattr(torch, "version", None), "cuda", None)
    return TorchBackendStatus(
        status="available",
        torch_version=str(getattr(torch, "__version__", "")),
        cuda_available=cuda_available,
        cuda_version=str(cuda_version) if cuda_version is not None else None,
        diagnostics=(
            {"category": "dependency", "dependency": "torch", "status": "available"},
        ),
    )


def torch_backend_status_to_dict(status: TorchBackendStatus) -> dict[str, object]:
    return {
        "status": status.status,
        "torch_version": status.torch_version,
        "cuda_available": status.cuda_available,
        "cuda_version": status.cuda_version,
        "default_device": status.default_device,
        "error_code": status.error_code,
        "error_message": status.error_message,
        "diagnostics": [dict(item) for item in status.diagnostics],
    }


def torch_tensor_spec_from_batch(
    batch: ModelBatch,
    *,
    device: str = _DEFAULT_DEVICE,
) -> TorchTensorSpec:
    error = _validate_batch_metadata(batch)
    if error is not None:
        raise ValueError(error.message)
    return _build_tensor_spec(batch, device=_normalize_device_string(device))


def torch_tensor_spec_to_dict(spec: TorchTensorSpec) -> dict[str, object]:
    return {
        "schema_version": spec.schema_version,
        "contract_version": spec.contract_version,
        "record_ids": list(spec.record_ids),
        "dtype": spec.dtype,
        "index_dtype": spec.index_dtype,
        "device": spec.device,
        "coordinate_frame": spec.coordinate_frame,
        "tensors": {
            key: {
                "shape": list(value.shape),
                "dtype": value.dtype,
                "device": value.device,
            }
            for key, value in sorted(spec.tensors.items())
        },
    }


def convert_batch_to_torch(
    batch: ModelBatch,
    *,
    device: str = _DEFAULT_DEVICE,
) -> ContractEnvelope[Optional[TorchTensorBatch]]:
    error = _validate_batch_metadata(batch)
    if error is not None:
        return _failure(error)

    normalized_device = _normalize_device_string(device)
    try:
        torch = _load_torch()
    except ImportError as exc:
        return _failure(
            _error(
                TORCH_BACKEND_UNAVAILABLE,
                "PyTorch is not installed in this environment",
                details={"exception": str(exc)},
            )
        )

    if normalized_device.startswith("cuda") and not bool(torch.cuda.is_available()):
        return _failure(
            _error(
                TORCH_BACKEND_DEVICE_UNAVAILABLE,
                f"requested device {device!r} is not available",
            )
        )

    try:
        tensors = batch.tensors
        torch_device = torch.device(normalized_device)
        runtime = TorchTensorBatch(
            protein_coords=torch.zeros(tensors.protein_coords_shape, dtype=torch.float32, device=torch_device),
            ligand_coords=torch.zeros(tensors.ligand_coords_shape, dtype=torch.float32, device=torch_device),
            protein_atom_types=torch.zeros(tensors.protein_atom_types_shape, dtype=torch.long, device=torch_device),
            ligand_atom_types=torch.zeros(tensors.ligand_atom_types_shape, dtype=torch.long, device=torch_device),
            ligand_bonds=torch.zeros(tensors.ligand_bonds_shape, dtype=torch.float32, device=torch_device),
            edge_candidates=torch.full(tensors.edge_candidates_shape, -1, dtype=torch.long, device=torch_device),
            positive_label_mask=torch.zeros(tensors.positive_label_mask_shape, dtype=torch.bool, device=torch_device),
            candidate_to_ligand_map=torch.full(tensors.candidate_to_ligand_map_shape, -1, dtype=torch.long, device=torch_device),
            candidate_to_protein_map=torch.full(tensors.candidate_to_protein_map_shape, -1, dtype=torch.long, device=torch_device),
            record_ids=tuple(record.record_id for record in batch.records),
            batch_spec=batch.batch_spec,
            device=str(torch_device),
            dtype=tensors.dtype,
            index_dtype=tensors.index_dtype,
            coordinate_frame=tensors.coordinate_frame,
        )
    except Exception as exc:  # pragma: no cover - defensive structured boundary
        return _failure(
            _error(
                TORCH_BACKEND_CONVERSION_FAILED,
                f"failed to construct torch tensor batch: {exc}",
            )
        )

    return ContractEnvelope(
        payload=runtime,
        artifacts=(),
        receipt=ValidationReceipt(
            validator=_VALIDATOR,
            contract_version=CONTRACT_VERSION,
            input_sha256="",
            passed=True,
        ),
        provenance=Provenance(),
    )


model_batch_to_torch = convert_batch_to_torch
get_torch_status = check_torch_available


def _load_torch() -> object:
    return importlib.import_module("torch")


_REQUIRED_SHAPES = {
    "protein_coords_shape": 3,
    "ligand_coords_shape": 3,
    "protein_atom_types_shape": 2,
    "ligand_atom_types_shape": 2,
    "ligand_bonds_shape": 3,
    "edge_candidates_shape": 2,
    "positive_label_mask_shape": 2,
    "candidate_to_ligand_map_shape": 2,
    "candidate_to_protein_map_shape": 2,
}


def _validate_batch_metadata(batch: ModelBatch) -> Optional[ContractErrorInfo]:
    if getattr(batch, "tensors", None) is None:
        return _error(
            TORCH_BACKEND_TENSOR_METADATA_MISSING,
            "ModelBatch.tensors is required for tensor conversion",
        )
    if len(getattr(batch, "records", ())) == 0:
        return _error(
            TORCH_BACKEND_EMPTY_BATCH,
            "ModelBatch.records must contain at least one record",
        )

    tensors = batch.tensors
    if not isinstance(tensors, BatchTensors):
        return _error(
            TORCH_BACKEND_TENSOR_METADATA_MISSING,
            "ModelBatch.tensors must be a BatchTensors instance",
        )
    if tensors.dtype != "float32":
        return _error(
            TORCH_BACKEND_DTYPE_UNSUPPORTED,
            f"unsupported tensor dtype {tensors.dtype!r}",
        )
    if tensors.index_dtype != "int64":
        return _error(
            TORCH_BACKEND_DTYPE_UNSUPPORTED,
            f"unsupported index dtype {tensors.index_dtype!r}",
        )

    batch_size = len(batch.records)
    for name, expected_rank in _REQUIRED_SHAPES.items():
        shape = getattr(tensors, name, None)
        if not _shape_is_valid(shape, expected_rank, batch_size):
            return _error(
                TORCH_BACKEND_SHAPE_MISMATCH,
                f"invalid tensor shape metadata {name}={shape!r}",
                details={"field": name, "shape": repr(shape)},
            )
    return None


def _shape_is_valid(shape: object, expected_rank: int, batch_size: int) -> bool:
    if not isinstance(shape, tuple):
        return False
    if len(shape) != expected_rank:
        return False
    if not all(isinstance(dim, int) and dim > 0 for dim in shape):
        return False
    return shape[0] == batch_size


def _build_tensor_spec(batch: ModelBatch, *, device: str) -> TorchTensorSpec:
    tensors = batch.tensors
    metadata = {
        "protein_coords": TensorMetadata(tensors.protein_coords_shape, tensors.dtype, device),
        "ligand_coords": TensorMetadata(tensors.ligand_coords_shape, tensors.dtype, device),
        "protein_atom_types": TensorMetadata(tensors.protein_atom_types_shape, tensors.index_dtype, device),
        "ligand_atom_types": TensorMetadata(tensors.ligand_atom_types_shape, tensors.index_dtype, device),
        "ligand_bonds": TensorMetadata(tensors.ligand_bonds_shape, tensors.dtype, device),
        "edge_candidates": TensorMetadata(tensors.edge_candidates_shape, tensors.index_dtype, device),
        "positive_label_mask": TensorMetadata(tensors.positive_label_mask_shape, "bool", device),
        "candidate_to_ligand_map": TensorMetadata(tensors.candidate_to_ligand_map_shape, tensors.index_dtype, device),
        "candidate_to_protein_map": TensorMetadata(tensors.candidate_to_protein_map_shape, tensors.index_dtype, device),
    }
    return TorchTensorSpec(
        record_ids=tuple(record.record_id for record in batch.records),
        tensors=metadata,
        dtype=tensors.dtype,
        index_dtype=tensors.index_dtype,
        device=device,
        coordinate_frame=tensors.coordinate_frame,
    )


def _metadata_from_tensor(tensor: object, dtype: str, device: str) -> TensorMetadata:
    shape = tuple(int(dim) for dim in getattr(tensor, "shape", ()))
    tensor_device = str(getattr(tensor, "device", device))
    return TensorMetadata(shape=shape, dtype=dtype, device=tensor_device)


def _normalize_device_string(device: str) -> str:
    if not device:
        return _DEFAULT_DEVICE
    return str(device)


def _failure(error: ContractErrorInfo) -> ContractEnvelope[Optional[TorchTensorBatch]]:
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
    "TORCH_BACKEND_ERROR_CODES",
    "TorchBackendStatus",
    "TensorMetadata",
    "TorchTensorBatch",
    "TorchTensorSpec",
    "check_torch_available",
    "convert_batch_to_torch",
    "get_torch_status",
    "model_batch_to_torch",
    "torch_backend_status_to_dict",
    "torch_tensor_spec_from_batch",
    "torch_tensor_spec_to_dict",
]
