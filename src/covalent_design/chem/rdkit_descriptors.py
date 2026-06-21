"""RDKit-backed molecular descriptor computation adapter.

The module is lightweight-safe: RDKit is imported lazily inside the public
function, so default CI can import the adapter without installing RDKit.

Drug-likeness output is diagnostic-only and not a hard beta gate.
"""

from __future__ import annotations

import importlib
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping, Optional

SUPPORTED_FORMATS = ("smiles", "molblock")

# Map RDKit CalcMolDescriptors keys to public-facing descriptor names
_DESCRIPTOR_KEY_MAP: dict[str, str] = {
    "MolWt": "molecular_weight",
    "MolLogP": "logp",
    "NumHAcceptors": "num_h_acceptors",
    "NumHDonors": "num_h_donors",
    "NumRotatableBonds": "num_rotatable_bonds",
    "TPSA": "tpsa",
    "RingCount": "num_rings",
    "HeavyAtomCount": "num_heavy_atoms",
    "FractionCSP3": "fraction_csp3",
    "NumAromaticRings": "num_aromatic_rings",
    "MolMR": "molar_refractivity",
}


@dataclass(frozen=True)
class DescriptorResult:
    """Serializable public output for molecular descriptor computation."""

    status: str
    input_format: str
    rdkit_available: bool
    descriptors: Mapping[str, object] = field(default_factory=dict)
    diagnostics: tuple[Mapping[str, object], ...] = ()
    error_code: Optional[str] = None
    error_message: Optional[str] = None


def compute_descriptors(
    text: str, *, input_format: str = "smiles"
) -> DescriptorResult:
    """Compute molecular descriptors using RDKit when available.

    Returns project-owned serializable data only. No RDKit ``Mol``, ``Atom``,
    or ``Bond`` objects cross this module boundary.

    Drug-likeness metrics (Lipinski Rule of 5, QED) are included as
    diagnostic-only annotations and do not gate the ``status`` field.
    """

    normalized_format = input_format.strip().lower()
    if not text or not text.strip():
        return _failure(
            normalized_format,
            "DESCRIPTOR_EMPTY_INPUT",
            "molecule input is empty",
        )
    if normalized_format not in SUPPORTED_FORMATS:
        return _failure(
            normalized_format,
            "DESCRIPTOR_UNSUPPORTED_FORMAT",
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
        return DescriptorResult(
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
            error_code="DESCRIPTOR_RDKIT_UNAVAILABLE",
            error_message="RDKit is unavailable in this environment",
        )

    mol = _parse_molecule(chem, text, normalized_format)
    if mol is None:
        return _failure(
            normalized_format,
            "DESCRIPTOR_PARSE_FAILED",
            "RDKit could not parse molecule input",
            rdkit_available=True,
            diagnostics=(
                {
                    "category": "parse",
                    "input_format": normalized_format,
                },
            ),
        )

    # Sanitize to catch chemically invalid molecules before computing descriptors
    try:
        chem.SanitizeMol(mol)
    except Exception as exc:
        return _failure(
            normalized_format,
            "DESCRIPTOR_PARSE_FAILED",
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
        raw_descriptors = _compute_raw_descriptors(mol)
    except Exception as exc:
        return _failure(
            normalized_format,
            "DESCRIPTOR_PARSE_FAILED",
            f"descriptor computation failed: {exc}",
            rdkit_available=True,
            diagnostics=(
                {
                    "category": "computation",
                    "message": f"{type(exc).__name__}: {exc}",
                },
            ),
        )

    # Build public-facing descriptor dict — only Python built-in types
    public_descriptors: dict[str, object] = {}
    for rdkit_key, public_key in _DESCRIPTOR_KEY_MAP.items():
        if rdkit_key in raw_descriptors:
            value = raw_descriptors[rdkit_key]
            if isinstance(value, (int, float, str, bool, type(None))):
                public_descriptors[public_key] = value
            else:
                # Coerce non-primitive RDKit return values (e.g. numpy scalars)
                public_descriptors[public_key] = float(value)

    # Drug-likeness diagnostics — diagnostic only, not a hard gate
    druglikeness_diagnostics = _compute_druglikeness_diagnostics(
        public_descriptors, raw_descriptors, mol
    )

    return DescriptorResult(
        status="ok",
        input_format=normalized_format,
        rdkit_available=True,
        descriptors=public_descriptors,
        diagnostics=tuple(druglikeness_diagnostics),
    )


def descriptor_result_to_dict(
    result: DescriptorResult,
) -> dict[str, object]:
    """Return a deterministic JSON-compatible result dictionary."""

    data = asdict(result)
    data["diagnostics"] = [
        {key: item[key] for key in sorted(item)}
        for item in result.diagnostics
    ]
    return {key: data[key] for key in sorted(data)}


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


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


def _compute_raw_descriptors(mol: Any) -> dict[str, Any]:
    """Return the raw descriptor dict from RDKit CalcMolDescriptors.

    Falls back to manual descriptor-by-descriptor computation when the
    bulk CalcMolDescriptors function is unavailable or raises.
    """
    try:
        Descriptors = importlib.import_module("rdkit.Chem.Descriptors")
        return dict(Descriptors.CalcMolDescriptors(mol, missingVal=None, silent=True))
    except Exception:
        return _compute_core_descriptors_manually(mol)


def _compute_core_descriptors_manually(mol: Any) -> dict[str, Any]:
    """Compute a minimal descriptor set without CalcMolDescriptors."""
    result: dict[str, Any] = {}

    # Crippen descriptors (LogP, MR)
    try:
        Crippen = importlib.import_module("rdkit.Chem.Crippen")
        result["MolLogP"] = float(Crippen.MolLogP(mol))
        result["MolMR"] = float(Crippen.MolMR(mol))
    except Exception:
        pass

    # Standard molecular descriptors
    try:
        Descriptors = importlib.import_module("rdkit.Chem.Descriptors")
        result["MolWt"] = float(Descriptors.MolWt(mol))
        result["TPSA"] = float(Descriptors.TPSA(mol))
        result["NumHAcceptors"] = int(Descriptors.NumHAcceptors(mol))
        result["NumHDonors"] = int(Descriptors.NumHDonors(mol))
        result["NumRotatableBonds"] = int(Descriptors.NumRotatableBonds(mol))
        result["RingCount"] = int(Descriptors.RingCount(mol))
        result["HeavyAtomCount"] = int(Descriptors.HeavyAtomCount(mol))
        result["FractionCSP3"] = float(Descriptors.FractionCSP3(mol))
        result["NumAromaticRings"] = int(Descriptors.NumAromaticRings(mol))
    except Exception:
        pass

    return result


def _compute_druglikeness_diagnostics(
    public_descriptors: dict[str, object],
    raw_descriptors: dict[str, Any],
    mol: Any,
) -> tuple[Mapping[str, object], ...]:
    """Compute drug-likeness metrics (diagnostic-only, not a hard gate)."""

    diagnostics: list[Mapping[str, object]] = []

    # --- Lipinski Rule of 5 ------------------------------------------------
    mw = public_descriptors.get("molecular_weight", 0)
    logp = public_descriptors.get("logp", 0)
    hbd = public_descriptors.get("num_h_donors", 0)
    hba = public_descriptors.get("num_h_acceptors", 0)

    lipinski_violations = 0
    lipinski_details: list[str] = []

    if isinstance(mw, (int, float)) and mw > 500:
        lipinski_violations += 1
        lipinski_details.append(f"MW={mw:.1f}>500")
    if isinstance(logp, (int, float)) and logp > 5:
        lipinski_violations += 1
        lipinski_details.append(f"LogP={logp:.1f}>5")
    if isinstance(hbd, (int, float)) and hbd > 5:
        lipinski_violations += 1
        lipinski_details.append(f"HBD={hbd}>5")
    if isinstance(hba, (int, float)) and hba > 10:
        lipinski_violations += 1
        lipinski_details.append(f"HBA={hba}>10")

    diagnostics.append(
        {
            "category": "druglikeness",
            "rule": "Lipinski Rule of 5",
            "violations": lipinski_violations,
            "details": lipinski_details,
            "passes": lipinski_violations <= 1,
        }
    )

    # --- QED ---------------------------------------------------------------
    try:
        QED = importlib.import_module("rdkit.Chem.QED")
        qed_value = float(QED.qed(mol))
    except Exception:
        qed_value = None

    diagnostics.append(
        {
            "category": "druglikeness",
            "metric": "QED",
            "value": qed_value,
        }
    )

    return tuple(diagnostics)


def _failure(
    input_format: str,
    code: str,
    message: str,
    *,
    rdkit_available: bool = False,
    diagnostics: tuple[Mapping[str, object], ...] = (),
) -> DescriptorResult:
    return DescriptorResult(
        status="failed",
        input_format=input_format,
        rdkit_available=rdkit_available,
        diagnostics=diagnostics,
        error_code=code,
        error_message=message,
    )


__all__ = [
    "DescriptorResult",
    "SUPPORTED_FORMATS",
    "compute_descriptors",
    "descriptor_result_to_dict",
]
