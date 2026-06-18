from __future__ import annotations

import dataclasses
import json
from typing import Any

import pytest

from covalent_design.chem import rdkit_normalize
from covalent_design.chem.rdkit_normalize import (
    MoleculeNormalizationResult,
    normalize_molecule,
    result_to_dict,
)


def _rdkit_chem_available() -> bool:
    try:
        __import__("rdkit.Chem")
    except Exception:
        return False
    return True


RDKIT_AVAILABLE = _rdkit_chem_available()


def test_module_import_does_not_require_rdkit_objects() -> None:
    assert hasattr(rdkit_normalize, "normalize_molecule")
    result = MoleculeNormalizationResult(
        status="unavailable",
        input_format="smiles",
        rdkit_available=False,
    )
    for value in dataclasses.asdict(result).values():
        assert not value.__class__.__module__.startswith("rdkit")


def test_rdkit_unavailable_returns_structured_result(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rdkit_normalize, "_load_rdkit_chem", lambda: None)

    result = normalize_molecule("CCO", input_format="smiles")

    assert result.status == "unavailable"
    assert result.error_code == "RDKIT_NORMALIZE_RDKIT_UNAVAILABLE"
    assert result.diagnostics[0]["category"] == "dependency"
    assert result_to_dict(result)["status"] == "unavailable"


def test_empty_input_structured_failure() -> None:
    result = normalize_molecule("   ", input_format="smiles")

    assert result.status == "failed"
    assert result.error_code == "RDKIT_NORMALIZE_EMPTY_INPUT"
    assert result.normalized_smiles is None


def test_unsupported_format_structured_failure() -> None:
    result = normalize_molecule("CCO", input_format="inchi")

    assert result.status == "failed"
    assert result.error_code == "RDKIT_NORMALIZE_UNSUPPORTED_FORMAT"
    assert result.input_format == "inchi"


def test_result_output_is_serializable_and_deterministic(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rdkit_normalize, "_load_rdkit_chem", lambda: None)

    first = result_to_dict(normalize_molecule("CCO", input_format="smiles"))
    second = result_to_dict(normalize_molecule("CCO", input_format="smiles"))

    assert first == second
    assert json.dumps(first, sort_keys=True, separators=(",", ":")) == json.dumps(
        second,
        sort_keys=True,
        separators=(",", ":"),
    )


def test_public_output_does_not_expose_raw_rdkit_objects(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rdkit_normalize, "_load_rdkit_chem", lambda: None)

    result = normalize_molecule("CCO", input_format="smiles")

    for value in dataclasses.asdict(result).values():
        assert not value.__class__.__module__.startswith("rdkit")


@pytest.mark.heavy
@pytest.mark.skipif(not RDKIT_AVAILABLE, reason="RDKit unavailable in this environment")
def test_heavy_smiles_parsing_and_sanitize_behavior_runs_when_rdkit_available() -> None:
    result = normalize_molecule("CCO", input_format="smiles")

    assert result.status == "ok"
    assert result.rdkit_available is True
    assert result.normalized_smiles == "CCO"
    assert result.atom_count == 3
    assert result.bond_count == 2
    assert result.sanitize_passed is True
    assert result.valence_problem_count == 0


@pytest.mark.heavy
@pytest.mark.skipif(not RDKIT_AVAILABLE, reason="RDKit unavailable in this environment")
def test_heavy_invalid_molecule_input_structured_failure() -> None:
    result = normalize_molecule("C1CC", input_format="smiles")

    assert result.status == "failed"
    assert result.error_code == "RDKIT_NORMALIZE_PARSE_FAILED"
    assert result.normalized_smiles is None


@pytest.mark.heavy
@pytest.mark.skipif(not RDKIT_AVAILABLE, reason="RDKit unavailable in this environment")
def test_heavy_valence_related_diagnostics() -> None:
    result = normalize_molecule("[CH5]", input_format="smiles")

    assert result.status == "failed"
    assert result.error_code == "RDKIT_NORMALIZE_SANITIZE_FAILED"
    assert result.sanitize_passed is False
    assert result.valence_problem_count >= 1
    assert any("valence" in str(item).lower() for item in result.diagnostics)


@pytest.mark.heavy
@pytest.mark.skipif(not RDKIT_AVAILABLE, reason="RDKit unavailable in this environment")
def test_heavy_molblock_parsing() -> None:
    molblock = """
  Mrv2014 09192006082D

  2  1  0  0  0  0            999 V2000
    0.0000    0.0000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
    1.2000    0.0000    0.0000 O   0  0  0  0  0  0  0  0  0  0  0  0
  1  2  1  0  0  0  0
M  END
"""
    result = normalize_molecule(molblock, input_format="molblock")

    assert result.status == "ok"
    assert result.normalized_smiles == "CO"
    assert result.atom_count == 2


@pytest.mark.heavy
@pytest.mark.skipif(not RDKIT_AVAILABLE, reason="RDKit unavailable in this environment")
def test_heavy_invalid_molblock_structured_failure() -> None:
    result = normalize_molecule("not a molblock", input_format="molblock")

    assert result.status == "failed"
    assert result.error_code == "RDKIT_NORMALIZE_PARSE_FAILED"
    assert result.normalized_smiles is None


@pytest.mark.heavy
def test_heavy_tests_have_real_execution_when_rdkit_is_available() -> None:
    if not RDKIT_AVAILABLE:
        pytest.skip("RDKit unavailable in this environment")

    assert normalize_molecule("CCO", input_format="smiles").status == "ok"
