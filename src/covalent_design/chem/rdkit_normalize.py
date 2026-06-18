"""RDKit-backed molecule normalization adapter.

The module is lightweight-safe: RDKit is imported lazily inside the public
function, so default CI can import the adapter without installing RDKit.
"""

from __future__ import annotations

import importlib
from dataclasses import asdict, dataclass
from typing import Any, Mapping, Optional


SUPPORTED_FORMATS = ("smiles", "molblock")


@dataclass(frozen=True)
class MoleculeNormalizationResult:
    """Serializable public output for RDKit molecule normalization."""

    status: str
    input_format: str
    rdkit_available: bool
    normalized_smiles: Optional[str] = None
    atom_count: int = 0
    bond_count: int = 0
    formal_charge: int = 0
    sanitize_passed: bool = False
    valence_problem_count: int = 0
    diagnostics: tuple[Mapping[str, object], ...] = ()
    error_code: Optional[str] = None
    error_message: Optional[str] = None


def normalize_molecule(text: str, *, input_format: str = "smiles") -> MoleculeNormalizationResult:
    """Normalize a molecule using RDKit when available.

    Returns project-owned serializable data only. No RDKit ``Mol``, ``Atom``,
    or ``Bond`` objects cross this module boundary.
    """

    normalized_format = input_format.strip().lower()
    if not text or not text.strip():
        return _failure(
            normalized_format,
            "RDKIT_NORMALIZE_EMPTY_INPUT",
            "molecule input is empty",
        )
    if normalized_format not in SUPPORTED_FORMATS:
        return _failure(
            normalized_format,
            "RDKIT_NORMALIZE_UNSUPPORTED_FORMAT",
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
        return MoleculeNormalizationResult(
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
            error_code="RDKIT_NORMALIZE_RDKIT_UNAVAILABLE",
            error_message="RDKit is unavailable in this environment",
        )

    mol = _parse_molecule(chem, text, normalized_format)
    if mol is None:
        return _failure(
            normalized_format,
            "RDKIT_NORMALIZE_PARSE_FAILED",
            "RDKit could not parse molecule input",
            rdkit_available=True,
            diagnostics=(
                {
                    "category": "parse",
                    "input_format": normalized_format,
                },
            ),
        )

    problems = tuple(_chemistry_problems(chem, mol))
    try:
        chem.SanitizeMol(mol)
        sanitize_passed = True
        sanitize_error: Optional[str] = None
    except Exception as exc:  # pragma: no cover - exact exception depends on RDKit
        sanitize_passed = False
        sanitize_error = f"{type(exc).__name__}: {exc}"

    if not sanitize_passed:
        return MoleculeNormalizationResult(
            status="failed",
            input_format=normalized_format,
            rdkit_available=True,
            sanitize_passed=False,
            valence_problem_count=_valence_problem_count(problems, sanitize_error),
            diagnostics=_problem_diagnostics(problems, sanitize_error),
            error_code="RDKIT_NORMALIZE_SANITIZE_FAILED",
            error_message=sanitize_error or "RDKit molecule sanitization failed",
        )

    normalized_smiles = str(chem.MolToSmiles(mol, canonical=True))
    return MoleculeNormalizationResult(
        status="ok",
        input_format=normalized_format,
        rdkit_available=True,
        normalized_smiles=normalized_smiles,
        atom_count=int(mol.GetNumAtoms()),
        bond_count=int(mol.GetNumBonds()),
        formal_charge=sum(int(atom.GetFormalCharge()) for atom in mol.GetAtoms()),
        sanitize_passed=True,
        valence_problem_count=_valence_problem_count(problems, None),
        diagnostics=_problem_diagnostics(problems, None),
    )


def result_to_dict(result: MoleculeNormalizationResult) -> dict[str, object]:
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


def _parse_molecule(chem: Any, text: str, input_format: str) -> object:
    if input_format == "smiles":
        return chem.MolFromSmiles(text.strip(), sanitize=False)
    if input_format == "molblock":
        return chem.MolFromMolBlock(text, sanitize=False, removeHs=False)
    raise AssertionError(f"unsupported format reached parser: {input_format}")


def _chemistry_problems(chem: Any, mol: object) -> tuple[object, ...]:
    detector = getattr(chem, "DetectChemistryProblems", None)
    if detector is None:
        return ()
    try:
        return tuple(detector(mol))
    except Exception:  # pragma: no cover - defensive around optional RDKit API
        return ()


def _problem_diagnostics(
    problems: tuple[object, ...],
    sanitize_error: Optional[str],
) -> tuple[Mapping[str, object], ...]:
    diagnostics: list[Mapping[str, object]] = []
    for index, problem in enumerate(problems):
        diagnostics.append(
            {
                "category": "chemistry_problem",
                "index": index,
                "problem_type": _problem_type(problem),
                "message": _problem_message(problem),
            }
        )
    if sanitize_error:
        diagnostics.append(
            {
                "category": "sanitize",
                "message": sanitize_error,
            }
        )
    return tuple(diagnostics)


def _problem_type(problem: object) -> str:
    getter = getattr(problem, "GetType", None)
    if getter is None:
        return type(problem).__name__
    try:
        return str(getter())
    except Exception:  # pragma: no cover - defensive around RDKit object API
        return type(problem).__name__


def _problem_message(problem: object) -> str:
    for method_name in ("Message", "GetMessage"):
        method = getattr(problem, method_name, None)
        if method is not None:
            try:
                return str(method())
            except Exception:  # pragma: no cover - defensive around RDKit object API
                continue
    return str(problem)


def _valence_problem_count(
    problems: tuple[object, ...],
    sanitize_error: Optional[str],
) -> int:
    count = 0
    for problem in problems:
        text = f"{_problem_type(problem)} {_problem_message(problem)}".lower()
        if "valence" in text:
            count += 1
    if count == 0 and sanitize_error and "valence" in sanitize_error.lower():
        count = 1
    return count


def _failure(
    input_format: str,
    code: str,
    message: str,
    *,
    rdkit_available: bool = False,
    diagnostics: tuple[Mapping[str, object], ...] = (),
) -> MoleculeNormalizationResult:
    return MoleculeNormalizationResult(
        status="failed",
        input_format=input_format,
        rdkit_available=rdkit_available,
        diagnostics=diagnostics,
        error_code=code,
        error_message=message,
    )


__all__ = [
    "MoleculeNormalizationResult",
    "SUPPORTED_FORMATS",
    "normalize_molecule",
    "result_to_dict",
]
