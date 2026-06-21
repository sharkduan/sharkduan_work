from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import replace
from pathlib import Path

import pytest

from covalent_design.contracts.errors import ContractError
from covalent_design.model.config import ModelConfig
from covalent_design.model.pmdm_adapter import (
    ALL_PMDM_OUTPUT_KEYS,
    OPTIONAL_PMDM_OUTPUT_KEYS,
    REQUIRED_PMDM_OUTPUT_KEYS,
)
from tests.fixtures.model.pmdm_adapter._builder import PMDMAdapterFixtureBuilder


def _valid_batch():
    return PMDMAdapterFixtureBuilder(seed=42).build_model_batch()


def _valid_outputs(batch, *, enable_optional: bool = False) -> dict:
    return PMDMAdapterFixtureBuilder.build_fake_pmdm_outputs(
        batch.tensors,
        seed=42,
        enable_optional=enable_optional,
    )


def test_module_import_does_not_import_heavy_or_later_task_modules() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root / "src")
    code = (
        "import json, sys; "
        "before=set(sys.modules); "
        "import covalent_design.model.pmdm_real_adapter; "
        "introduced=sorted(set(sys.modules)-before); "
        "bad=[m for m in introduced if "
        "m.lower().startswith(('pmdm','pocketflow','torch','rdkit')) "
        "or m in ("
        "'covalent_design.model.non_pmdm_baseline',"
        "'covalent_design.model.final_decode',"
        "'covalent_design.training'"
        ")]; "
        "print(json.dumps(bad)); "
        "raise SystemExit(1 if bad else 0)"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=repo_root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_license_unknown_reports_structured_unavailable_without_importing_pmdm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from covalent_design.model import pmdm_real_adapter

    def forbidden_import(name: str, *args: object, **kwargs: object) -> object:
        if name.lower().startswith(("pmdm", "pocketflow")):
            raise AssertionError(f"must not import blocked dependency {name}")
        return importlib.import_module(name, *args, **kwargs)

    monkeypatch.setattr(importlib, "import_module", forbidden_import)
    sys.modules.pop("PMDM", None)
    sys.modules.pop("PocketFlow", None)

    status = pmdm_real_adapter.check_pmdm_available()
    serialized = pmdm_real_adapter.pmdm_backend_status_to_dict(status)

    assert status.status == "unavailable"
    assert status.license_status == "unknown"
    assert status.reason == "license_unknown"
    assert status.import_attempted is False
    assert status.error_code == "PMDM_REAL_LICENSE_BLOCKED"
    assert "PMDM" not in sys.modules
    assert "PocketFlow" not in sys.modules
    json.dumps(serialized, sort_keys=True)


def test_forward_pmdm_real_fails_structured_and_never_silently_falls_back() -> None:
    from covalent_design.model import pmdm_real_adapter

    result = pmdm_real_adapter.forward_pmdm_real(
        batch=_valid_batch(),
        config=ModelConfig(rule_table_hash="sha256:fixture"),
    )

    assert result.payload is None
    assert result.receipt.passed is False
    assert result.receipt.errors[0].code == "PMDM_REAL_LICENSE_BLOCKED"
    assert result.receipt.errors[0].details["reason"] == "license_unknown"
    assert "non_pmdm_baseline" not in result.receipt.errors[0].message


def test_real_adapter_reuses_existing_pmdm_key_vocabulary() -> None:
    from covalent_design.model import pmdm_real_adapter

    assert pmdm_real_adapter.REQUIRED_PMDM_OUTPUT_KEYS == REQUIRED_PMDM_OUTPUT_KEYS
    assert pmdm_real_adapter.OPTIONAL_PMDM_OUTPUT_KEYS == OPTIONAL_PMDM_OUTPUT_KEYS
    assert pmdm_real_adapter.ALL_PMDM_OUTPUT_KEYS == ALL_PMDM_OUTPUT_KEYS


def test_output_spec_from_config_is_deterministic_and_serializable() -> None:
    from covalent_design.model import pmdm_real_adapter

    config = ModelConfig(
        rule_table_hash="sha256:fixture",
        ligand_pair_feature_dim=8,
        protein_ligand_pair_feature_dim=16,
    )
    first = pmdm_real_adapter.pmdm_output_spec_to_dict(
        pmdm_real_adapter.pmdm_output_spec_from_config(_valid_batch(), config)
    )
    second = pmdm_real_adapter.pmdm_output_spec_to_dict(
        pmdm_real_adapter.pmdm_output_spec_from_config(_valid_batch(), config)
    )

    assert first == second
    assert first["required_keys"] == list(REQUIRED_PMDM_OUTPUT_KEYS)
    assert first["optional_keys"] == list(OPTIONAL_PMDM_OUTPUT_KEYS)
    assert first["expected_shapes"]["ligand_pair_features"][-1] == 8
    assert first["expected_shapes"]["protein_ligand_pair_features"][-1] == 16
    json.dumps(first, sort_keys=True)


def test_validate_real_pmdm_outputs_accepts_valid_project_owned_payload() -> None:
    from covalent_design.model import pmdm_real_adapter

    batch = _valid_batch()
    config = ModelConfig(rule_table_hash="sha256:fixture")
    outputs = _valid_outputs(batch)

    pmdm_real_adapter.validate_real_pmdm_outputs(
        outputs,
        batch=batch,
        config=config,
    )


def test_validate_real_pmdm_outputs_rejects_unknown_key() -> None:
    from covalent_design.model import pmdm_real_adapter

    batch = _valid_batch()
    outputs = _valid_outputs(batch)
    outputs["raw_pmdm_tensor"] = object()

    with pytest.raises(ContractError) as exc_info:
        pmdm_real_adapter.validate_real_pmdm_outputs(
            outputs,
            batch=batch,
            config=ModelConfig(rule_table_hash="sha256:fixture"),
        )

    assert exc_info.value.code == "PMDM_REAL_UNKNOWN_KEY"


def test_validate_real_pmdm_outputs_rejects_missing_required_key() -> None:
    from covalent_design.model import pmdm_real_adapter

    batch = _valid_batch()
    outputs = _valid_outputs(batch)
    outputs.pop("position_loss")

    with pytest.raises(ContractError) as exc_info:
        pmdm_real_adapter.validate_real_pmdm_outputs(
            outputs,
            batch=batch,
            config=ModelConfig(rule_table_hash="sha256:fixture"),
        )

    assert exc_info.value.code == "PMDM_REAL_MISSING_REQUIRED_KEY"
    assert exc_info.value.details["key"] == "position_loss"


def test_validate_real_pmdm_outputs_rejects_wrong_shape_with_details() -> None:
    from covalent_design.model import pmdm_real_adapter

    batch = _valid_batch()
    outputs = _valid_outputs(batch)
    outputs["num_atom"] = [[value] for value in outputs["num_atom"]]

    with pytest.raises(ContractError) as exc_info:
        pmdm_real_adapter.validate_real_pmdm_outputs(
            outputs,
            batch=batch,
            config=ModelConfig(rule_table_hash="sha256:fixture"),
        )

    assert exc_info.value.code == "PMDM_REAL_SHAPE_MISMATCH"
    assert exc_info.value.details["key"] == "num_atom"
    assert "expected" in exc_info.value.details
    assert "actual" in exc_info.value.details


def test_optional_key_presence_follows_config_dimensions() -> None:
    from covalent_design.model import pmdm_real_adapter

    batch = _valid_batch()
    outputs = _valid_outputs(batch, enable_optional=True)
    disabled = ModelConfig(rule_table_hash="sha256:fixture")
    with pytest.raises(ContractError) as exc_info:
        pmdm_real_adapter.validate_real_pmdm_outputs(
            outputs,
            batch=batch,
            config=disabled,
        )
    assert exc_info.value.code == "PMDM_REAL_UNEXPECTED_OPTIONAL_KEY"

    enabled = replace(
        disabled,
        ligand_pair_feature_dim=64,
        protein_ligand_pair_feature_dim=64,
    )
    pmdm_real_adapter.validate_real_pmdm_outputs(
        outputs,
        batch=batch,
        config=enabled,
    )


def test_status_and_spec_public_payloads_contain_no_raw_dependency_objects() -> None:
    from covalent_design.model import pmdm_real_adapter

    status_payload = pmdm_real_adapter.pmdm_backend_status_to_dict(
        pmdm_real_adapter.check_pmdm_available()
    )
    spec_payload = pmdm_real_adapter.pmdm_output_spec_to_dict(
        pmdm_real_adapter.pmdm_output_spec_from_config(
            _valid_batch(),
            ModelConfig(rule_table_hash="sha256:fixture"),
        )
    )
    encoded = json.dumps(
        {"status": status_payload, "spec": spec_payload},
        sort_keys=True,
    )

    assert "tensor(" not in encoded
    assert "torch." not in encoded
    assert "rdkit." not in encoded.lower()
    assert "PMDM object" not in encoded


def test_real_adapter_functions_create_no_disk_artifacts() -> None:
    from covalent_design.model import pmdm_real_adapter

    batch = _valid_batch()
    outputs = _valid_outputs(batch)
    config = ModelConfig(rule_table_hash="sha256:fixture")

    with tempfile.TemporaryDirectory() as tmpdir:
        before = set(os.listdir(tmpdir))
        old_cwd = os.getcwd()
        try:
            os.chdir(tmpdir)
            pmdm_real_adapter.check_pmdm_available()
            pmdm_real_adapter.pmdm_output_spec_from_config(batch, config)
            pmdm_real_adapter.validate_real_pmdm_outputs(
                outputs,
                batch=batch,
                config=config,
            )
            pmdm_real_adapter.forward_pmdm_real(batch=batch, config=config)
        finally:
            os.chdir(old_cwd)
        assert set(os.listdir(tmpdir)) == before
