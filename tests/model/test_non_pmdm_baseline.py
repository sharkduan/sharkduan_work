from __future__ import annotations

import builtins
import importlib
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import replace
from pathlib import Path

import pytest

from covalent_design.contracts import ContractEnvelope, ModelForwardOutput
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


def _valid_config(*, optional: bool = False) -> ModelConfig:
    base = ModelConfig(rule_table_hash="sha256:fixture")
    if not optional:
        return base
    return replace(
        base,
        ligand_pair_feature_dim=64,
        protein_ligand_pair_feature_dim=64,
    )


def _shape(obj: object) -> tuple[int, ...]:
    return PMDMAdapterFixtureBuilder.get_shape(obj)


def _forward(*, optional: bool = False):
    from covalent_design.model import non_pmdm_baseline

    return non_pmdm_baseline.forward_non_pmdm_baseline(
        batch=_valid_batch(),
        config=_valid_config(optional=optional),
        timestep=0.5,
        baseline_mode=non_pmdm_baseline.BASELINE_MODE_NON_PMDM,
    )


def test_module_import_does_not_import_heavy_or_later_task_modules() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root / "src")
    code = (
        "import json, sys; "
        "before=set(sys.modules); "
        "import covalent_design.model.non_pmdm_baseline; "
        "introduced=sorted(set(sys.modules)-before); "
        "bad=[m for m in introduced if "
        "m.lower().startswith(('pmdm','pocketflow','torch','rdkit','pyg','pytorch_geometric')) "
        "or m in ('covalent_design.training','covalent_design.inference','covalent_design.evaluation')]; "
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


def test_baseline_status_is_explicitly_non_pmdm_and_serializable() -> None:
    from covalent_design.model import non_pmdm_baseline

    status = non_pmdm_baseline.check_baseline_available()
    payload = non_pmdm_baseline.baseline_status_to_dict(status)

    assert payload["baseline_mode"] == "non_pmdm_baseline"
    assert payload["is_pmdm"] is False
    assert payload["pmdm_import_attempted"] is False
    assert payload["status"] == "available"
    assert "not PMDM" in payload["warning"]
    json.dumps(payload, sort_keys=True)


def test_baseline_requires_explicit_selection() -> None:
    from covalent_design.model import non_pmdm_baseline

    result = non_pmdm_baseline.forward_non_pmdm_baseline(
        batch=_valid_batch(),
        config=_valid_config(),
    )

    assert result.payload is None
    assert result.receipt.passed is False
    assert result.receipt.errors[0].code == "BASELINE_MODE_NOT_SELECTED"
    assert result.receipt.errors[0].details["requested_mode"] == "not_selected"


def test_pmdm_mode_does_not_silently_fallback_to_baseline() -> None:
    from covalent_design.model import non_pmdm_baseline

    result = non_pmdm_baseline.forward_non_pmdm_baseline(
        batch=_valid_batch(),
        config=_valid_config(),
        baseline_mode=non_pmdm_baseline.BASELINE_MODE_PMDM,
    )

    assert result.payload is None
    assert result.receipt.passed is False
    assert result.receipt.errors[0].code == "BASELINE_MODE_MISMATCH"
    assert result.receipt.errors[0].details["selected_mode"] == "pmdm"


def test_unknown_mode_is_structured_error() -> None:
    from covalent_design.model import non_pmdm_baseline

    result = non_pmdm_baseline.forward_non_pmdm_baseline(
        batch=_valid_batch(),
        config=_valid_config(),
        baseline_mode="fallback",
    )

    assert result.payload is None
    assert result.receipt.passed is False
    assert result.receipt.errors[0].code == "BASELINE_MODE_UNSUPPORTED"


def test_forward_returns_contract_envelope_and_not_pmdm_warning() -> None:
    result = _forward()

    assert isinstance(result, ContractEnvelope)
    assert isinstance(result.payload, ModelForwardOutput)
    assert result.receipt.passed is True
    assert result.receipt.validator == "covalent_design.model.non_pmdm_baseline"
    assert result.receipt.warnings[0].code == "BASELINE_NOT_PMDM_WARNING"
    assert result.receipt.warnings[0].details["baseline_mode"] == "non_pmdm_baseline"
    assert result.receipt.warnings[0].details["is_pmdm"] is False
    assert result.artifacts == ()


def test_forward_outputs_all_required_pmdm_compatible_keys() -> None:
    result = _forward()
    assert result.payload is not None

    outputs = result.payload.pmdm_outputs
    for key in REQUIRED_PMDM_OUTPUT_KEYS:
        assert key in outputs
    assert set(outputs).issubset(set(ALL_PMDM_OUTPUT_KEYS))


def test_optional_keys_follow_model_config_dimensions() -> None:
    disabled = _forward(optional=False)
    assert disabled.payload is not None
    assert not any(key in disabled.payload.pmdm_outputs for key in OPTIONAL_PMDM_OUTPUT_KEYS)

    enabled = _forward(optional=True)
    assert enabled.payload is not None
    for key in OPTIONAL_PMDM_OUTPUT_KEYS:
        assert key in enabled.payload.pmdm_outputs


def test_output_shapes_match_batch_and_config() -> None:
    batch = _valid_batch()
    config = _valid_config(optional=True)
    from covalent_design.model import non_pmdm_baseline

    result = non_pmdm_baseline.forward_non_pmdm_baseline(
        batch=batch,
        config=config,
        timestep=0.25,
        baseline_mode=non_pmdm_baseline.BASELINE_MODE_NON_PMDM,
    )
    assert result.payload is not None
    outputs = result.payload.pmdm_outputs

    b_size = batch.tensors.protein_coords_shape[0]
    n_lig = batch.tensors.ligand_coords_shape[1]
    n_prot = batch.tensors.protein_coords_shape[1]

    assert _shape(outputs["ligand_atom_features"]) == (b_size, n_lig, config.ligand_feature_dim)
    assert _shape(outputs["protein_atom_features"]) == (b_size, n_prot, config.protein_feature_dim)
    assert _shape(outputs["ligand_coords_denoised"]) == (b_size, n_lig, 3)
    assert _shape(outputs["position_loss"]) == ()
    assert _shape(outputs["atom_type_loss"]) == ()
    assert _shape(outputs["timestep"]) == ()
    assert _shape(outputs["num_atom"]) == (b_size,)
    assert _shape(outputs["ligand_pair_features"]) == (b_size, n_lig, n_lig, config.ligand_pair_feature_dim)
    assert _shape(outputs["protein_ligand_pair_features"]) == (b_size, n_prot, n_lig, config.protein_ligand_pair_feature_dim)


def test_forward_output_is_deterministic_and_json_serializable() -> None:
    from covalent_design.model import non_pmdm_baseline

    first = non_pmdm_baseline.baseline_envelope_to_dict(_forward(optional=True))
    second = non_pmdm_baseline.baseline_envelope_to_dict(_forward(optional=True))

    assert first == second
    encoded = json.dumps(first, sort_keys=True)
    assert "non_pmdm_baseline" in encoded
    assert "baseline is not PMDM" in encoded
    assert "tensor(" not in encoded
    assert "torch." not in encoded
    assert "rdkit." not in encoded.lower()
    assert "PMDM object" not in encoded


def test_model_forward_output_contract_and_denominators_are_preserved() -> None:
    batch = _valid_batch()
    from covalent_design.model import non_pmdm_baseline

    result = non_pmdm_baseline.forward_non_pmdm_baseline(
        batch=batch,
        config=_valid_config(),
        baseline_mode=non_pmdm_baseline.BASELINE_MODE_NON_PMDM,
    )

    assert result.payload is not None
    assert result.payload.denominators_observed == batch.denominators_expected
    assert result.payload.message_weight_source == "detached_edge_probability"
    assert getattr(result.payload.edge_prob_message_weights, "requires_grad", False) is False


def test_validate_baseline_outputs_rejects_shape_mismatch() -> None:
    from covalent_design.model import non_pmdm_baseline

    batch = _valid_batch()
    result = non_pmdm_baseline.forward_non_pmdm_baseline(
        batch=batch,
        config=_valid_config(),
        baseline_mode=non_pmdm_baseline.BASELINE_MODE_NON_PMDM,
    )
    assert result.payload is not None
    outputs = dict(result.payload.pmdm_outputs)
    outputs["num_atom"] = [[value] for value in outputs["num_atom"]]

    with pytest.raises(ContractError) as exc_info:
        non_pmdm_baseline.validate_baseline_pmdm_outputs(
            outputs,
            batch=batch,
            config=_valid_config(),
        )
    assert exc_info.value.code == "PMDM_SHAPE_MISMATCH"


def test_baseline_does_not_call_real_or_fake_pmdm(monkeypatch: pytest.MonkeyPatch) -> None:
    from covalent_design.model import pmdm_adapter, pmdm_real_adapter, non_pmdm_baseline

    def forbidden(*args: object, **kwargs: object) -> object:
        raise AssertionError("baseline must not call PMDM paths")

    monkeypatch.setattr(pmdm_adapter, "forward_pmdm", forbidden)
    monkeypatch.setattr(pmdm_real_adapter, "forward_pmdm_real", forbidden)

    result = non_pmdm_baseline.forward_non_pmdm_baseline(
        batch=_valid_batch(),
        config=_valid_config(),
        baseline_mode=non_pmdm_baseline.BASELINE_MODE_NON_PMDM,
    )
    assert result.receipt.passed is True


def test_functions_create_no_disk_artifacts_or_real_data_access(monkeypatch: pytest.MonkeyPatch) -> None:
    from covalent_design.model import non_pmdm_baseline

    original_open = builtins.open

    def guarded_open(file: object, *args: object, **kwargs: object):
        if str(file).lower().startswith("d:\\codex_work\\data".lower()):
            raise AssertionError("must not access real data root")
        return original_open(file, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", guarded_open)

    with tempfile.TemporaryDirectory() as tmpdir:
        before = set(os.listdir(tmpdir))
        old_cwd = os.getcwd()
        try:
            os.chdir(tmpdir)
            non_pmdm_baseline.check_baseline_available()
            non_pmdm_baseline.forward_non_pmdm_baseline(
                batch=_valid_batch(),
                config=_valid_config(),
                baseline_mode=non_pmdm_baseline.BASELINE_MODE_NON_PMDM,
            )
        finally:
            os.chdir(old_cwd)
        assert set(os.listdir(tmpdir)) == before


def test_public_exports_are_lazy_and_available() -> None:
    from covalent_design.model import (
        BASELINE_MODE_NON_PMDM,
        NonPmdmBaselineStatus,
        check_baseline_available,
        forward_non_pmdm_baseline,
    )

    assert BASELINE_MODE_NON_PMDM == "non_pmdm_baseline"
    assert check_baseline_available().is_pmdm is False
    assert NonPmdmBaselineStatus().baseline_mode == "non_pmdm_baseline"
    assert callable(forward_non_pmdm_baseline)