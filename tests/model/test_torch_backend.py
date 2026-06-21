from __future__ import annotations

import builtins
import importlib
import json
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

from covalent_design.contracts.types import (
    BatchTensors,
    EdgeDenominators,
    ModelBatch,
)
from covalent_design.model.batch import make_model_batch
from tests.fixtures.model._builder import ModelBatchFixtureBuilder


def _valid_batch() -> ModelBatch:
    builder = ModelBatchFixtureBuilder()
    records_path = builder.write_valid()
    return make_model_batch(records_path).payload


def _empty_batch() -> ModelBatch:
    valid = _valid_batch()
    zero = EdgeDenominators(
        candidate_count=0,
        natural_candidate_count=0,
        forced_positive_count=0,
        eligible_edge_count=0,
        masked_candidate_count=0,
        edge_loss_denominator=0,
        bond_type_loss_denominator=0,
        geometry_loss_denominator=0,
        message_passing_candidate_count=0,
        gate_evaluated_count=0,
    )
    return ModelBatch(
        records=(),
        tensors=valid.tensors,
        static_edge_candidates_refs={},
        denominators_expected=zero,
        batch_spec=valid.batch_spec,
    )


def _has_torch() -> bool:
    try:
        importlib.import_module("torch")
    except ImportError:
        return False
    return True


def test_module_import_does_not_require_torch() -> None:
    sys.modules.pop("covalent_design.model.torch_backend", None)
    before = set(sys.modules)
    module = importlib.import_module("covalent_design.model.torch_backend")
    introduced = set(sys.modules) - before
    assert module is not None
    assert "torch" not in introduced


def test_missing_torch_returns_structured_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    from covalent_design.model import torch_backend

    real_import = importlib.import_module

    def fake_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "torch":
            raise ImportError("fake missing torch")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(importlib, "import_module", fake_import)

    status = torch_backend.check_torch_available()
    assert status.status == "unavailable"
    assert status.error_code == "TORCH_BACKEND_UNAVAILABLE"
    assert status.torch_version is None
    json.dumps(torch_backend.torch_backend_status_to_dict(status), sort_keys=True)


def test_convert_missing_torch_returns_contract_envelope(monkeypatch: pytest.MonkeyPatch) -> None:
    from covalent_design.model import torch_backend

    real_import = importlib.import_module

    def fake_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "torch":
            raise ImportError("fake missing torch")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(importlib, "import_module", fake_import)

    result = torch_backend.convert_batch_to_torch(_valid_batch())
    assert result.receipt.passed is False
    assert result.receipt.errors[0].code == "TORCH_BACKEND_UNAVAILABLE"
    assert result.payload is None


def test_tensor_spec_metadata_round_trips_through_json() -> None:
    from covalent_design.model import torch_backend

    spec = torch_backend.torch_tensor_spec_from_batch(_valid_batch(), device="cpu")
    encoded = json.dumps(torch_backend.torch_tensor_spec_to_dict(spec), sort_keys=True)
    decoded = json.loads(encoded)

    assert decoded["device"] == "cpu"
    assert decoded["dtype"] == "float32"
    assert decoded["index_dtype"] == "int64"
    assert decoded["record_ids"] == list(spec.record_ids)
    assert "torch." not in encoded
    assert "tensor(" not in encoded


def test_shape_dtype_device_and_record_identity_are_deterministic() -> None:
    from covalent_design.model import torch_backend

    batch = _valid_batch()
    first = torch_backend.torch_tensor_spec_to_dict(
        torch_backend.torch_tensor_spec_from_batch(batch)
    )
    second = torch_backend.torch_tensor_spec_to_dict(
        torch_backend.torch_tensor_spec_from_batch(batch)
    )

    assert first == second
    assert first["record_ids"] == [record.record_id for record in batch.records]
    assert first["tensors"]["protein_coords"]["shape"] == list(batch.tensors.protein_coords_shape)
    assert first["tensors"]["ligand_coords"]["shape"] == list(batch.tensors.ligand_coords_shape)
    assert first["tensors"]["protein_coords"]["dtype"] == "float32"
    assert first["tensors"]["candidate_to_ligand_map"]["dtype"] == "int64"
    assert first["tensors"]["positive_label_mask"]["dtype"] == "bool"
    assert first["tensors"]["protein_coords"]["device"] == "cpu"


def test_empty_batch_is_structured_failure() -> None:
    from covalent_design.model import torch_backend

    result = torch_backend.convert_batch_to_torch(_empty_batch())
    assert result.receipt.passed is False
    assert result.receipt.errors[0].code == "TORCH_BACKEND_EMPTY_BATCH"


def test_invalid_shape_is_structured_failure() -> None:
    from covalent_design.model import torch_backend

    batch = _valid_batch()
    bad_tensors = replace(batch.tensors, protein_coords_shape=(len(batch.records), -1, 3))
    bad = replace(batch, tensors=bad_tensors)

    result = torch_backend.convert_batch_to_torch(bad)
    assert result.receipt.passed is False
    assert result.receipt.errors[0].code == "TORCH_BACKEND_SHAPE_MISMATCH"


def test_missing_tensor_metadata_is_structured_failure() -> None:
    from covalent_design.model import torch_backend

    batch = _valid_batch()
    bad = replace(batch, tensors=None)  # type: ignore[arg-type]

    result = torch_backend.convert_batch_to_torch(bad)
    assert result.receipt.passed is False
    assert result.receipt.errors[0].code == "TORCH_BACKEND_TENSOR_METADATA_MISSING"


def test_conversion_does_not_access_filesystem_or_raw_data_root(monkeypatch: pytest.MonkeyPatch) -> None:
    from covalent_design.model import torch_backend

    batch = _valid_batch()

    def forbidden_open(*args: object, **kwargs: object) -> object:
        raise AssertionError("conversion must not open files")

    monkeypatch.setattr(builtins, "open", forbidden_open)
    with mock.patch.object(Path, "read_text", side_effect=AssertionError("no read_text")):
        result = torch_backend.convert_batch_to_torch(batch)

    if result.receipt.passed:
        assert result.payload is not None
    else:
        assert result.receipt.errors[0].code == "TORCH_BACKEND_UNAVAILABLE"


def test_conversion_does_not_import_pmdm_or_pocketflow() -> None:
    from covalent_design.model import torch_backend

    sys.modules.pop("PMDM", None)
    sys.modules.pop("PocketFlow", None)
    torch_backend.convert_batch_to_torch(_valid_batch())
    assert "PMDM" not in sys.modules
    assert "PocketFlow" not in sys.modules



def test_facade_exports_serializable_torch_backend_helpers_without_torch_import() -> None:
    before = set(sys.modules)
    from covalent_design.model import (
        TensorMetadata,
        torch_backend_status_to_dict,
        torch_tensor_spec_from_batch,
        torch_tensor_spec_to_dict,
    )

    introduced = set(sys.modules) - before
    assert "torch" not in introduced
    assert TensorMetadata.__name__ == "TensorMetadata"
    spec = torch_tensor_spec_from_batch(_valid_batch())
    encoded = json.dumps(torch_tensor_spec_to_dict(spec), sort_keys=True)
    assert "tensor(" not in encoded
    status = torch_backend_status_to_dict(
        SimpleNamespace(
            status="unavailable",
            torch_version=None,
            cuda_available=False,
            cuda_version=None,
            default_device="cpu",
            error_code="TORCH_BACKEND_UNAVAILABLE",
            error_message="not installed",
            diagnostics=(),
        )
    )
    assert status["status"] == "unavailable"


def test_unsupported_coordinate_dtype_is_structured_failure() -> None:
    from covalent_design.model import torch_backend

    batch = _valid_batch()
    bad_tensors = replace(batch.tensors, dtype="float64")
    bad = replace(batch, tensors=bad_tensors)

    result = torch_backend.convert_batch_to_torch(bad)
    assert result.receipt.passed is False
    assert result.receipt.errors[0].code == "TORCH_BACKEND_DTYPE_UNSUPPORTED"


def test_unsupported_index_dtype_is_structured_failure() -> None:
    from covalent_design.model import torch_backend

    batch = _valid_batch()
    bad_tensors = replace(batch.tensors, index_dtype="int32")
    bad = replace(batch, tensors=bad_tensors)

    result = torch_backend.convert_batch_to_torch(bad)
    assert result.receipt.passed is False
    assert result.receipt.errors[0].code == "TORCH_BACKEND_DTYPE_UNSUPPORTED"


@pytest.mark.skipif(not _has_torch(), reason="PyTorch is not installed")
def test_cuda_device_unavailable_is_structured_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    from covalent_design.model import torch_backend

    torch = importlib.import_module("torch")
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)

    result = torch_backend.convert_batch_to_torch(_valid_batch(), device="cuda")
    assert result.receipt.passed is False
    assert result.receipt.errors[0].code == "TORCH_BACKEND_DEVICE_UNAVAILABLE"

def test_torch_backend_status_to_dict_uses_real_dataclass() -> None:
    from covalent_design.model import torch_backend

    status = torch_backend.TorchBackendStatus(
        status="unavailable",
        torch_version=None,
        cuda_available=False,
        cuda_version=None,
        default_device="cpu",
        error_code="TORCH_BACKEND_UNAVAILABLE",
        error_message="not installed",
        diagnostics=(
            {"category": "dependency", "dependency": "torch", "status": "unavailable"},
        ),
    )

    result = torch_backend.torch_backend_status_to_dict(status)
    encoded = json.dumps(result, sort_keys=True)
    assert "TORCH_BACKEND_UNAVAILABLE" in encoded
    assert result["default_device"] == "cpu"
    assert isinstance(result["diagnostics"], list)


def test_torch_backend_aliases_match_primary_functions() -> None:
    from covalent_design.model import torch_backend

    assert torch_backend.get_torch_status is torch_backend.check_torch_available
    assert torch_backend.model_batch_to_torch is torch_backend.convert_batch_to_torch


@pytest.mark.skipif(not _has_torch(), reason="PyTorch is not installed")
def test_check_torch_available_with_real_torch_returns_available_status() -> None:
    from covalent_design.model import torch_backend

    status = torch_backend.check_torch_available()
    assert status.status == "available"
    assert isinstance(status.torch_version, str)
    assert status.torch_version
    assert isinstance(status.cuda_available, bool)
    assert status.error_code is None
    assert status.error_message is None
    assert torch_backend.torch_backend_status_to_dict(status)["status"] == "available"
@pytest.mark.skipif(not _has_torch(), reason="PyTorch is not installed")
def test_real_torch_conversion_produces_internal_tensors() -> None:
    from covalent_design.model import torch_backend

    torch = importlib.import_module("torch")
    batch = _valid_batch()

    result = torch_backend.convert_batch_to_torch(batch)

    assert result.receipt.passed is True
    assert result.payload is not None
    runtime = result.payload
    assert isinstance(runtime.protein_coords, torch.Tensor)
    assert tuple(runtime.protein_coords.shape) == batch.tensors.protein_coords_shape
    assert tuple(runtime.ligand_coords.shape) == batch.tensors.ligand_coords_shape
    assert runtime.protein_coords.dtype == torch.float32
    assert runtime.protein_atom_types.dtype == torch.long
    assert runtime.positive_label_mask.dtype == torch.bool
    assert str(runtime.protein_coords.device) == "cpu"
    assert runtime.record_ids == tuple(record.record_id for record in batch.records)
    assert runtime.protein_coords.requires_grad is False


@pytest.mark.skipif(not _has_torch(), reason="PyTorch is not installed")
def test_real_torch_conversion_public_spec_contains_no_tensor_objects() -> None:
    from covalent_design.model import torch_backend

    result = torch_backend.convert_batch_to_torch(_valid_batch())
    assert result.receipt.passed is True
    assert result.payload is not None
    spec = result.payload.to_spec()
    encoded = json.dumps(torch_backend.torch_tensor_spec_to_dict(spec), sort_keys=True)
    assert "torch." not in encoded
    assert "tensor(" not in encoded
