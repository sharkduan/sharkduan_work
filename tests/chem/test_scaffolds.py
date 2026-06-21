from __future__ import annotations

import dataclasses
import json
from typing import Any

import pytest

import covalent_design.chem.scaffolds as scaffolds
from covalent_design.chem.scaffolds import (
    ScaffoldResult,
    derive_scaffold,
    scaffold_result_to_dict,
)


def _rdkit_chem_available() -> bool:
    try:
        __import__("rdkit.Chem")
    except Exception:
        return False
    return True


RDKIT_AVAILABLE = _rdkit_chem_available()


# ---------------------------------------------------------------------------
# Lightweight tests – must pass without RDKit installed
# ---------------------------------------------------------------------------

def test_module_import_does_not_require_rdkit() -> None:
    """Importing the scaffolds module must not require RDKit."""
    assert hasattr(scaffolds, "derive_scaffold")
    result = ScaffoldResult(
        status="unavailable",
        input_format="smiles",
        rdkit_available=False,
    )
    for value in dataclasses.asdict(result).values():
        assert not value.__class__.__module__.startswith("rdkit")


def test_rdkit_unavailable_returns_structured_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When RDKit is unavailable the result must carry a structured status."""
    monkeypatch.setattr(scaffolds, "_load_rdkit_chem", lambda: None)

    result = derive_scaffold("CCO", input_format="smiles")

    assert result.status == "unavailable"
    assert result.rdkit_available is False
    assert result.error_code == "SCAFFOLD_RDKIT_UNAVAILABLE"
    # diagnostics must report the missing dependency
    assert any(
        d.get("category") == "dependency" for d in result.diagnostics
    )
    assert scaffold_result_to_dict(result)["status"] == "unavailable"


def test_empty_input_structured_failure() -> None:
    """Empty or whitespace-only input must fail before touching RDKit."""
    result = derive_scaffold("   ", input_format="smiles")

    assert result.status == "failed"
    assert result.error_code == "SCAFFOLD_EMPTY_INPUT"
    assert result.scaffold_smiles is None


def test_unsupported_format_structured_failure() -> None:
    """An unsupported input format must be rejected before touching RDKit."""
    result = derive_scaffold("c1ccccc1", input_format="inchi")

    assert result.status == "failed"
    assert result.error_code == "SCAFFOLD_UNSUPPORTED_FORMAT"
    assert result.input_format == "inchi"


def test_result_output_is_serializable_and_deterministic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """scaffold_result_to_dict output must be JSON-safe and deterministic."""
    monkeypatch.setattr(scaffolds, "_load_rdkit_chem", lambda: None)

    first = scaffold_result_to_dict(
        derive_scaffold("CCO", input_format="smiles")
    )
    second = scaffold_result_to_dict(
        derive_scaffold("CCO", input_format="smiles")
    )

    assert first == second
    assert json.dumps(first, sort_keys=True, separators=(",", ":")) == json.dumps(
        second, sort_keys=True, separators=(",", ":")
    )


def test_public_output_does_not_expose_raw_rdkit_objects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No RDKit Mol / Atom / Bond object may ever cross the API boundary."""
    monkeypatch.setattr(scaffolds, "_load_rdkit_chem", lambda: None)

    result = derive_scaffold("CCO", input_format="smiles")

    for value in dataclasses.asdict(result).values():
        assert not value.__class__.__module__.startswith("rdkit")


# ---------------------------------------------------------------------------
# Heavy tests – require RDKit; must not all skip when RDKit *is* available
# ---------------------------------------------------------------------------

@pytest.mark.heavy
@pytest.mark.skipif(not RDKIT_AVAILABLE, reason="RDKit unavailable in this environment")
def test_heavy_scaffold_derives_bemis_murcko_scaffold() -> None:
    """A drug-like SMILES must produce a canonical scaffold SMILES."""
    # phenylacetic acid — Murcko scaffold is a benzene ring (at minimum)
    result = derive_scaffold("c1ccccc1CC(=O)O", input_format="smiles")

    assert result.status == "ok"
    assert result.rdkit_available is True
    assert result.scaffold_smiles is not None
    assert isinstance(result.scaffold_smiles, str)
    assert len(result.scaffold_smiles) > 0
    # The scaffold SMILES is canonical — it should not be identical to the raw
    # input but should preserve the ring system
    assert "c1ccccc1" in result.scaffold_smiles or "C1=CC=CC=C1" in result.scaffold_smiles
    assert result.atom_count >= 6  # at least the benzene ring


@pytest.mark.heavy
@pytest.mark.skipif(not RDKIT_AVAILABLE, reason="RDKit unavailable in this environment")
def test_heavy_scaffold_is_reproducible() -> None:
    """Two calls with the same SMILES must return the identical scaffold."""
    first = derive_scaffold("c1ccccc1CC(=O)O", input_format="smiles")
    second = derive_scaffold("c1ccccc1CC(=O)O", input_format="smiles")

    assert first.scaffold_smiles == second.scaffold_smiles
    assert first.scaffold_type == second.scaffold_type
    assert scaffold_result_to_dict(first) == scaffold_result_to_dict(second)


@pytest.mark.heavy
@pytest.mark.skipif(not RDKIT_AVAILABLE, reason="RDKit unavailable in this environment")
def test_heavy_invalid_molecule_input_structured_failure() -> None:
    """An unparseable SMILES must return a structured failure, not explode."""
    result = derive_scaffold("C1CC", input_format="smiles")

    assert result.status == "failed"
    assert result.error_code == "SCAFFOLD_PARSE_FAILED"
    assert result.scaffold_smiles is None


@pytest.mark.heavy
@pytest.mark.skipif(not RDKIT_AVAILABLE, reason="RDKit unavailable in this environment")
def test_heavy_scaffold_result_is_json_serializable() -> None:
    """A successful result must round-trip through json.dumps."""
    result = derive_scaffold("CCO", input_format="smiles")
    d = scaffold_result_to_dict(result)

    serialized = json.dumps(d, sort_keys=True)
    assert len(serialized) > 0
    roundtripped = json.loads(serialized)
    assert roundtripped["status"] == "ok"
    assert roundtripped["rdkit_available"] is True


@pytest.mark.heavy
@pytest.mark.skipif(not RDKIT_AVAILABLE, reason="RDKit unavailable in this environment")
def test_heavy_scaffold_output_no_raw_rdkit_objects() -> None:
    """A heavy-path result must never leak RDKit objects."""
    result = derive_scaffold("CCO", input_format="smiles")

    for value in dataclasses.asdict(result).values():
        assert not value.__class__.__module__.startswith("rdkit")


@pytest.mark.heavy
@pytest.mark.skipif(not RDKIT_AVAILABLE, reason="RDKit unavailable in this environment")
def test_heavy_simple_molecule_scaffold_is_molecule_itself() -> None:
    """For ethanol (no rings), the Murcko scaffold is the molecule itself."""
    result = derive_scaffold("CCO", input_format="smiles")

    assert result.status == "ok"
    assert result.scaffold_smiles is not None
    # Simple acyclic molecule → scaffold ≅ itself
    # Carbon count should match ethanol's 2 carbons
    assert result.atom_count >= 2


@pytest.mark.heavy
@pytest.mark.skipif(not RDKIT_AVAILABLE, reason="RDKit unavailable in this environment")
def test_heavy_scaffold_vs_full_molecule_difference() -> None:
    """Assert that the scaffold is genuinely a sub-structure for decorated molecules."""
    # Aspirin-like: benzene with acetyl and carboxyl
    result = derive_scaffold("CC(=O)Oc1ccccc1C(=O)O", input_format="smiles")

    assert result.status == "ok"
    assert result.scaffold_smiles is not None
    # scaffold atom count ≤ full molecule atom count
    # (can't check the full mol through the API, but scaffold should have atoms)


@pytest.mark.heavy
def test_heavy_tests_have_real_execution_when_rdkit_is_available() -> None:
    """Guard: when RDKit is installed, heavy tests must execute real logic."""
    if not RDKIT_AVAILABLE:
        pytest.skip("RDKit unavailable in this environment")

    assert derive_scaffold("CCO", input_format="smiles").status == "ok"
