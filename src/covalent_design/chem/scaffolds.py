"""RDKit-backed Bemis-Murcko scaffold derivation adapter.

The module is lightweight-safe: RDKit is imported lazily inside the public
function, so default CI can import the adapter without installing RDKit.
"""

from __future__ import annotations

import importlib
from dataclasses import asdict, dataclass
from typing import Any, Mapping, Optional

SUPPORTED_FORMATS = ("smiles", "molblock")


@dataclass(frozen=True)
class ScaffoldResult:
    """Serializable public output for Bemis-Murcko scaffold derivation."""

    status: str
    input_format: str
    rdkit_available: bool
    scaffold_smiles: Optional[str] = None
    atom_count: int = 0
    scaffold_type: Optional[str] = None
    diagnostics: tuple[Mapping[str, object], ...] = ()
    error_code: Optional[str] = None
    error_message: Optional[str] = None


def derive_scaffold(
    text: str, *, input_format: str = "smiles"
) -> ScaffoldResult:
    """Derive the Bemis-Murcko scaffold from a molecule input.

    Returns project-owned serializable data only. No RDKit ``Mol``, ``Atom``,
    or ``Bond`` objects cross this module boundary.
    """

    normalized_format = input_format.strip().lower()
    if not text or not text.strip():
        return _failure(
            normalized_format,
            "SCAFFOLD_EMPTY_INPUT",
            "molecule input is empty",
        )
    if normalized_format not in SUPPORTED_FORMATS:
        return _failure(
            normalized_format,
            "SCAFFOLD_UNSUPPORTED_FORMAT",
            f"unsupported molecule input format {input_format!r}",
            diagnostics=(
                {
                    "category": "input_format",
                    "supported_formats": SUPPORTED_FORMATS,
                },
            ),
        )

    chem = _load_rdkit_chem()
    if chem is None:
        return ScaffoldResult(
            status="unavailable",
            input_format=normalized_format,
            rdkit_available=False,
            diagnostics=(
                {
                    "category": "dependency",
                    "dependency": "rdkit",
                    "message": "RDKit is unavailable in this environment",
                },
            ),
            error_code="SCAFFOLD_RDKIT_UNAVAILABLE",
            error_message="RDKit is unavailable in this environment",
        )

    mol = _parse_molecule(chem, text, normalized_format)
    if mol is None:
        return _failure(
            normalized_format,
            "SCAFFOLD_PARSE_FAILED",
            "RDKit could not parse molecule input",
            rdkit_available=True,
            diagnostics=(
                {
                    "category": "parse",
                    "input_format": normalized_format,
                },
            ),
        )

    # Sanitize to catch chemically invalid molecules (e.g. unclosed rings)
    try:
        chem.SanitizeMol(mol)
    except Exception as exc:
        return _failure(
            normalized_format,
            "SCAFFOLD_PARSE_FAILED",
            f"RDKit molecule sanitization failed: {exc}",
            rdkit_available=True,
            diagnostics=(
                {
                    "category": "sanitize",
                    "message": f"{type(exc).__name__}: {exc}",
                },
            ),
        )

    try:
        scaffold_mol = _derive_murcko_scaffold(chem, mol)
    except Exception as exc:
        return _failure(
            normalized_format,
            "SCAFFOLD_PARSE_FAILED",
            f"scaffold derivation failed: {exc}",
            rdkit_available=True,
            diagnostics=(
                {
                    "category": "scaffold",
                    "message": f"{type(exc).__name__}: {exc}",
                },
            ),
        )

    if scaffold_mol is None:
        return _failure(
            normalized_format,
            "SCAFFOLD_PARSE_FAILED",
            "scaffold derivation returned None",
            rdkit_available=True,
            diagnostics=(
                {
                    "category": "scaffold",
                    "message": "GetScaffoldForMol returned None",
                },
            ),
        )

    scaffold_smiles = str(chem.MolToSmiles(scaffold_mol, canonical=True))
    if not scaffold_smiles and int(scaffold_mol.GetNumAtoms()) == 0:
        fallback_smiles = str(chem.MolToSmiles(mol, canonical=True))
        return ScaffoldResult(
            status="ok",
            input_format=normalized_format,
            rdkit_available=True,
            scaffold_smiles=fallback_smiles,
            atom_count=int(mol.GetNumAtoms()),
            scaffold_type="acyclic_fallback",
            diagnostics=(
                {
                    "category": "scaffold",
                    "fallback_reason": "acyclic_murcko_scaffold_empty",
                    "message": "RDKit Murcko scaffold is empty for acyclic input; using canonical molecule SMILES as project-owned fallback",
                },
            ),
        )
    return ScaffoldResult(
        status="ok",
        input_format=normalized_format,
        rdkit_available=True,
        scaffold_smiles=scaffold_smiles,
        atom_count=int(scaffold_mol.GetNumAtoms()),
        scaffold_type="bemis_murcko",
    )


def scaffold_result_to_dict(result: ScaffoldResult) -> dict[str, object]:
    """Return a deterministic JSON-compatible result dictionary."""

    data = asdict(result)
    data["diagnostics"] = [
        {key: item[key] for key in sorted(item)}
        for item in result.diagnostics
    ]
    return {key: data[key] for key in sorted(data)}


def _load_rdkit_chem() -> Optional[Any]:
    try:
        return importlib.import_module("rdkit.Chem")
    except ImportError:
        return None


def _parse_molecule(
    chem: Any, text: str, input_format: str
) -> Optional[Any]:
    if input_format == "smiles":
        return chem.MolFromSmiles(text.strip(), sanitize=False)
    if input_format == "molblock":
        return chem.MolFromMolBlock(text, sanitize=False, removeHs=False)
    raise AssertionError(f"unsupported format reached parser: {input_format}")


def _derive_murcko_scaffold(chem: Any, mol: Any) -> Any:
    """Derive Bemis-Murcko scaffold from an RDKit Mol.

    Uses the official RDKit MurckoScaffold API.  Returns the scaffold Mol
    object (which is converted to SMILES before crossing the module boundary).
    """
    MurckoScaffold = importlib.import_module(
        "rdkit.Chem.Scaffolds.MurckoScaffold"
    )
    return MurckoScaffold.GetScaffoldForMol(mol)


def _failure(
    input_format: str,
    code: str,
    message: str,
    *,
    rdkit_available: bool = False,
    diagnostics: tuple[Mapping[str, object], ...] = (),
) -> ScaffoldResult:
    return ScaffoldResult(
        status="failed",
        input_format=input_format,
        rdkit_available=rdkit_available,
        diagnostics=diagnostics,
        error_code=code,
        error_message=message,
    )


__all__ = [
    "ScaffoldResult",
    "SUPPORTED_FORMATS",
    "derive_scaffold",
    "scaffold_result_to_dict",
]
