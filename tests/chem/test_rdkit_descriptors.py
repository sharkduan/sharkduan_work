from __future__ import annotations

import dataclasses
import json
from typing import Any

import pytest

import covalent_design.chem.rdkit_descriptors as rdkit_descriptors
from covalent_design.chem.rdkit_descriptors import (
    DescriptorResult,
    compute_descriptors,
    descriptor_result_to_dict,
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
    """Importing the descriptors module must not trigger an RDKit import."""
    assert hasattr(rdkit_descriptors, "compute_descriptors")
    result = DescriptorResult(
        status="unavailable",
        input_format="smiles",
        rdkit_available=False,
    )
    for value in dataclasses.asdict(result).values():
        assert not value.__class__.__module__.startswith("rdkit")


def test_rdkit_unavailable_returns_structured_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When RDKit is absent the output is still structured and JSON-safe."""
    monkeypatch.setattr(rdkit_descriptors, "_load_rdkit_chem", lambda: None)

    result = compute_descriptors("CCO", input_format="smiles")

    assert result.status == "unavailable"
    assert result.rdkit_available is False
    assert result.error_code == "DESCRIPTOR_RDKIT_UNAVAILABLE"
    assert any(
        d.get("category") == "dependency" for d in result.diagnostics
    )
    assert descriptor_result_to_dict(result)["status"] == "unavailable"


def test_empty_input_structured_failure() -> None:
    """Empty/whitespace SMILES must fail before any RDKit call."""
    result = compute_descriptors("   ", input_format="smiles")

    assert result.status == "failed"
    assert result.error_code == "DESCRIPTOR_EMPTY_INPUT"
    assert result.descriptors == {}


def test_unsupported_format_structured_failure() -> None:
    """A format that the module doesn't handle must fail immediately."""
    result = compute_descriptors("CCO", input_format="inchi")

    assert result.status == "failed"
    assert result.error_code == "DESCRIPTOR_UNSUPPORTED_FORMAT"
    assert result.input_format == "inchi"


def test_result_output_is_serializable_and_deterministic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """descriptor_result_to_dict output must round-trip through json."""
    monkeypatch.setattr(rdkit_descriptors, "_load_rdkit_chem", lambda: None)

    first = descriptor_result_to_dict(
        compute_descriptors("CCO", input_format="smiles")
    )
    second = descriptor_result_to_dict(
        compute_descriptors("CCO", input_format="smiles")
    )

    assert first == second
    assert json.dumps(first, sort_keys=True, separators=(",", ":")) == json.dumps(
        second, sort_keys=True, separators=(",", ":")
    )


def test_public_output_does_not_expose_raw_rdkit_objects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The public dataclass must contain only Python built-ins and project types."""
    monkeypatch.setattr(rdkit_descriptors, "_load_rdkit_chem", lambda: None)

    result = compute_descriptors("CCO", input_format="smiles")

    for value in dataclasses.asdict(result).values():
        assert not value.__class__.__module__.startswith("rdkit")


# ---------------------------------------------------------------------------
# Heavy tests – require RDKit; must not all skip when RDKit *is* available
# ---------------------------------------------------------------------------

@pytest.mark.heavy
@pytest.mark.skipif(not RDKIT_AVAILABLE, reason="RDKit unavailable in this environment")
def test_heavy_computes_core_descriptors() -> None:
    """A valid molecule must produce a descriptor dictionary with core fields."""
    # ethanol
    result = compute_descriptors("CCO", input_format="smiles")

    assert result.status == "ok"
    assert result.rdkit_available is True
    assert isinstance(result.descriptors, dict)
    assert len(result.descriptors) > 0

    # Core descriptor keys we expect from any sensible descriptor module
    core_keys = {
        "fraction_csp3",
        "logp",
        "molar_refractivity",
        "molecular_weight",
        "num_aromatic_rings",
        "num_h_acceptors",
        "num_h_donors",
        "num_heavy_atoms",
        "num_rings",
        "num_rotatable_bonds",
        "tpsa",
    }
    found = set(result.descriptors.keys())
    assert core_keys.issubset(found), (
        f"Missing core descriptor keys: {core_keys - found}"
    )

    # sanity: ethanol molecular weight ≈ 46
    mw = result.descriptors["molecular_weight"]
    assert isinstance(mw, (int, float))
    assert 45.0 < mw < 47.0


@pytest.mark.heavy
@pytest.mark.skipif(not RDKIT_AVAILABLE, reason="RDKit unavailable in this environment")
def test_heavy_descriptors_are_deterministic() -> None:
    """Two calls for the same molecule must yield identical descriptor dicts."""
    first = compute_descriptors("c1ccccc1C(=O)O", input_format="smiles")
    second = compute_descriptors("c1ccccc1C(=O)O", input_format="smiles")

    assert first.descriptors == second.descriptors
    assert descriptor_result_to_dict(first) == descriptor_result_to_dict(second)


@pytest.mark.heavy
@pytest.mark.skipif(not RDKIT_AVAILABLE, reason="RDKit unavailable in this environment")
def test_heavy_druglikeness_is_diagnostic_only() -> None:
    """Drug-likeness fields must be present but have diagnostic-only semantics.

    They must NOT act as a hard beta gate — the result status is still "ok"
    even for molecules that fail Lipinski or QED thresholds.
    """
    # A deliberately poor drug candidate (large, many donors/acceptors)
    # should still compute descriptors successfully
    result = compute_descriptors(
        "CCCCCCCCCCCCCCCCCCCCCCCCCCCCCC(=O)NCCCCCCCC(=O)O",
        input_format="smiles",
    )

    assert result.status == "ok", f"Status should be ok, got {result.status}"
    assert result.error_code is None

    # Drug-likeness diagnostics must exist as a separate, clearly-named section
    diagnostics = list(result.diagnostics)
    druglikeness_diags = [
        d for d in diagnostics
        if d.get("category") in ("druglikeness", "drug_likeness")
    ]
    assert len(druglikeness_diags) >= 1, (
        f"Expected at least one drug-likeness diagnostic, got diagnostics: {diagnostics}"
    )

    # At least one drug-likeness diagnostic should contain a rule-of-5 or QED
    # assessment
    druglikeness_text = " ".join(
        json.dumps(d, sort_keys=True) for d in druglikeness_diags
    ).lower()
    assert "qed" in druglikeness_text or "lipinski" in druglikeness_text or "rule" in druglikeness_text, (
        f"Drug-likeness diagnostics should mention QED/Lipinski: {druglikeness_text}"
    )


@pytest.mark.heavy
@pytest.mark.skipif(not RDKIT_AVAILABLE, reason="RDKit unavailable in this environment")
def test_heavy_druglikeness_diagnostics_are_json_serializable() -> None:
    """Drug-likeness diagnostics must be part of the serializable output."""
    result = compute_descriptors("CCO", input_format="smiles")
    d = descriptor_result_to_dict(result)

    # The dict must contain a diagnostics entry
    assert "diagnostics" in d
    serialized = json.dumps(d, sort_keys=True)
    roundtripped = json.loads(serialized)
    assert roundtripped["status"] == "ok"
    assert isinstance(roundtripped["diagnostics"], list)


@pytest.mark.heavy
@pytest.mark.skipif(not RDKIT_AVAILABLE, reason="RDKit unavailable in this environment")
def test_heavy_invalid_molecule_input_structured_failure() -> None:
    """An unparseable SMILES must return structured failure with empty descriptors."""
    result = compute_descriptors("XxNotASmiles99", input_format="smiles")

    assert result.status == "failed"
    assert result.error_code == "DESCRIPTOR_PARSE_FAILED"
    assert result.descriptors == {}


@pytest.mark.heavy
@pytest.mark.skipif(not RDKIT_AVAILABLE, reason="RDKit unavailable in this environment")
def test_heavy_output_no_raw_rdkit_objects() -> None:
    """A heavy-path descriptor result must never contain RDKit internals."""
    result = compute_descriptors("CCO", input_format="smiles")

    for value in dataclasses.asdict(result).values():
        assert not value.__class__.__module__.startswith("rdkit")

    # also check inside the descriptors dict
    for val in result.descriptors.values():
        assert not val.__class__.__module__.startswith("rdkit")


@pytest.mark.heavy
@pytest.mark.skipif(not RDKIT_AVAILABLE, reason="RDKit unavailable in this environment")
def test_heavy_molblock_input_format() -> None:
    """Molecules can be provided as molblock strings."""
    molblock = """
  Mrv2014 09192006082D

  2  1  0  0  0  0            999 V2000
    0.0000    0.0000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
    1.2000    0.0000    0.0000 O   0  0  0  0  0  0  0  0  0  0  0  0
  1  2  1  0  0  0  0
M  END
"""
    result = compute_descriptors(molblock, input_format="molblock")

    assert result.status == "ok"
    assert result.input_format == "molblock"
    assert isinstance(result.descriptors, dict)
    assert len(result.descriptors) > 0


@pytest.mark.heavy
@pytest.mark.skipif(not RDKIT_AVAILABLE, reason="RDKit unavailable in this environment")
def test_heavy_different_molecules_produce_different_descriptors() -> None:
    """Structural differences must be reflected in descriptor values."""
    ethanol = compute_descriptors("CCO", input_format="smiles")
    benzene = compute_descriptors("c1ccccc1", input_format="smiles")

    # These two molecules differ in at least one descriptor
    diffs = [
        key
        for key in ethanol.descriptors
        if key in benzene.descriptors
        and ethanol.descriptors[key] != benzene.descriptors[key]
    ]
    assert len(diffs) >= 1, (
        f"Expected ethanol and benzene to differ in at least one descriptor, "
        f"but all common keys matched"
    )

    # ring count specifically must differ
    if "num_rings" in ethanol.descriptors and "num_rings" in benzene.descriptors:
        assert ethanol.descriptors["num_rings"] != benzene.descriptors["num_rings"]


@pytest.mark.heavy
def test_heavy_tests_have_real_execution_when_rdkit_is_available() -> None:
    """Guard: when RDKit is installed, heavy tests must execute real logic."""
    if not RDKIT_AVAILABLE:
        pytest.skip("RDKit unavailable in this environment")

    assert compute_descriptors("CCO", input_format="smiles").status == "ok"
