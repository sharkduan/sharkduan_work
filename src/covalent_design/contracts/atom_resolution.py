"""Shared protein target-atom resolution for data and model boundaries."""

from __future__ import annotations

from dataclasses import asdict
from typing import Mapping, Optional, Sequence

from covalent_design.contracts.types import ProteinAtomIdentity


def resolve_protein_atom(
    atoms: Sequence[Mapping[str, object]],
    *,
    target_atom_index: Optional[int] = None,
    target_atom_name: str = "",
    target_atom_identity: Optional[ProteinAtomIdentity] = None,
) -> Mapping[str, object]:
    """Resolve one target atom without silently choosing an ambiguous name."""
    expected_name = target_atom_identity.atom_name if target_atom_identity else target_atom_name

    if target_atom_index is not None:
        indexed = [atom for atom in atoms if atom.get("index") == target_atom_index]
        serialized = [atom for atom in atoms if atom.get("serial") == target_atom_index]
        positional = [atoms[target_atom_index]] if 0 <= target_atom_index < len(atoms) else []
        candidates = _deduplicate_atoms(indexed + serialized + positional)
        matches = [
            atom
            for atom in candidates
            if _selected_atom_matches(atom, expected_name, target_atom_identity)
        ]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise ValueError(f"target atom index {target_atom_index!r} is ambiguous")
        return _resolve_unique_name_fallback(atoms, expected_name, target_atom_identity)

    return _resolve_unique_name_fallback(atoms, expected_name, target_atom_identity)


def _resolve_unique_name_fallback(
    atoms: Sequence[Mapping[str, object]],
    expected_name: str,
    identity: Optional[ProteinAtomIdentity],
) -> Mapping[str, object]:
    matches = [
        atom
        for atom in atoms
        if atom.get("name") == expected_name
        and _matches_identity(atom, identity)
    ]
    if not matches:
        raise ValueError(f"target atom {expected_name!r} was not found")
    if len(matches) != 1:
        raise ValueError(f"target atom name fallback for {expected_name!r} is ambiguous")
    return matches[0]


def protein_atom_identity_from_table(
    protein_data: Mapping[str, object],
    atom: Mapping[str, object],
) -> ProteinAtomIdentity:
    """Build the full identity carried by static and dynamic candidate paths."""
    return ProteinAtomIdentity(
        chain_id=_optional_text(atom.get("chain_id", protein_data.get("chain_id"))),
        residue_number=_optional_int(atom.get("residue_number", protein_data.get("residue_number"))),
        residue_name=str(atom.get("residue_name", protein_data.get("residue_name", ""))),
        atom_name=str(atom.get("name", atom.get("atom_name", ""))),
        altloc=_optional_text(atom.get("altloc")),
        insertion_code=_optional_text(atom.get("insertion_code")),
        structure_model=_optional_int(atom.get("structure_model")),
        asym_id=_optional_text(atom.get("asym_id")),
        atom_serial=_optional_int(atom.get("serial", atom.get("atom_serial"))),
    )


def protein_atom_identity_to_dict(identity: ProteinAtomIdentity) -> dict[str, object]:
    return asdict(identity)


def _validate_selected_atom(
    atom: Mapping[str, object],
    expected_name: str,
    identity: Optional[ProteinAtomIdentity],
) -> None:
    if expected_name and atom.get("name") != expected_name:
        raise ValueError(
            f"target atom index selected {atom.get('name')!r}, expected {expected_name!r}"
        )
    if not _matches_identity(atom, identity):
        raise ValueError("target atom index does not match the required target identity")


def _selected_atom_matches(
    atom: Mapping[str, object],
    expected_name: str,
    identity: Optional[ProteinAtomIdentity],
) -> bool:
    try:
        _validate_selected_atom(atom, expected_name, identity)
    except ValueError:
        return False
    return True


def _deduplicate_atoms(
    atoms: Sequence[Mapping[str, object]],
) -> list[Mapping[str, object]]:
    seen: set[int] = set()
    result: list[Mapping[str, object]] = []
    for atom in atoms:
        marker = id(atom)
        if marker in seen:
            continue
        seen.add(marker)
        result.append(atom)
    return result


def _matches_identity(
    atom: Mapping[str, object],
    identity: Optional[ProteinAtomIdentity],
) -> bool:
    if identity is None:
        return True
    comparisons = (
        ("name", identity.atom_name),
        ("chain_id", identity.chain_id),
        ("residue_number", identity.residue_number),
        ("residue_name", identity.residue_name),
        ("altloc", identity.altloc),
        ("insertion_code", identity.insertion_code),
        ("structure_model", identity.structure_model),
        ("asym_id", identity.asym_id),
        ("serial", identity.atom_serial),
    )
    for key, expected in comparisons:
        if expected in (None, "") or key not in atom:
            continue
        if atom.get(key) != expected:
            return False
    return True


def _optional_text(value: object) -> Optional[str]:
    if value in (None, ""):
        return None
    return str(value)


def _optional_int(value: object) -> Optional[int]:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    return int(value)
