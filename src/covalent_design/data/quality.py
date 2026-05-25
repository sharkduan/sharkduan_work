"""Quality gate evaluation for normalized linkage records.

Q0: hard reject gates, such as missing atom mapping or multi-linkage v1.
Q1: structural quality reject gates, such as resolution > 3.0 Angstrom.
Q2: keep-with-flag gates, such as non_human_protein.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from covalent_design.rules.schema import VALID_REACTION_CLASSES, VALID_RESIDUE_NAMES


@dataclass(frozen=True)
class QualityGateResult:
    quality_tier: str
    first_core_eligible: bool
    reasons: tuple[str, ...]
    flags: tuple[str, ...]


_RESOLUTION_LIMIT_ANGSTROM = 3.0
_Q0_FLAG_REASONS = {
    "missing_ligand_coordinates": "MISSING_LIGAND_COORDINATES",
    "malformed_ligand_bond_table": "MALFORMED_LIGAND_BOND_TABLE",
    "required_gate_state_unavailable": "REQUIRED_GATE_STATE_UNAVAILABLE",
    "unsupported_residue_reaction_family": "UNSUPPORTED_RESIDUE_REACTION_FAMILY",
}
_Q1_FLAG_REASONS = {
    "extreme_bond_length_outlier": "EXTREME_BOND_LENGTH_OUTLIER",
    "severe_protein_ligand_clash": "SEVERE_PROTEIN_LIGAND_CLASH",
    "incomplete_ligand_heavy_atoms": "INCOMPLETE_LIGAND_HEAVY_ATOMS",
    "alternate_location_ambiguity": "ALTERNATE_LOCATION_AMBIGUITY",
}
_Q2_FLAGS = frozenset({
    "missing_activity_data",
    "missing_assay_data",
    "non_human_protein",
    "low_confidence_warhead_mapping",
    "inferred_protein_chemical_state",
})


def evaluate_quality_gates(
    protein: Mapping[str, object],
    linkage: Mapping[str, object],
    metadata: Mapping[str, object],
) -> QualityGateResult:
    reasons: list[str] = []
    flags: list[str] = []
    quality_tier = ""
    first_core_eligible = True
    quality_flags = _quality_flags(metadata)

    atom_mapping = metadata.get("atom_mapping")
    if atom_mapping is None:
        reasons.append("ATOM_MAPPING_MISSING")
        quality_tier = "Q0"
        first_core_eligible = False
    elif (
        isinstance(atom_mapping, Mapping)
        and atom_mapping.get("mapping_verified") is not True
    ):
        reasons.append("ATOM_MAPPING_UNVERIFIED")
        quality_tier = "Q0"
        first_core_eligible = False

    if not _is_supported_family(linkage.get("residue_reaction_family")):
        reasons.append("UNSUPPORTED_RESIDUE_REACTION_FAMILY")
        quality_tier = "Q0"
        first_core_eligible = False

    linkage_count = linkage.get("linkage_count", 1)
    if isinstance(linkage_count, (int, float)) and int(linkage_count) > 1:
        reasons.append("MULTI_LINKAGE_V1_REJECT")
        quality_tier = "Q0"
        first_core_eligible = False

    for flag, reason in _Q0_FLAG_REASONS.items():
        if flag in quality_flags and reason not in reasons:
            reasons.append(reason)
            quality_tier = "Q0"
            first_core_eligible = False

    if quality_tier != "Q0":
        resolution = protein.get("resolution_angstrom")
        if resolution is not None:
            try:
                if float(resolution) > _RESOLUTION_LIMIT_ANGSTROM:
                    reasons.append("RESOLUTION_GT_3A")
                    quality_tier = "Q1"
                    first_core_eligible = False
            except (TypeError, ValueError):
                pass

        for flag, reason in _Q1_FLAG_REASONS.items():
            if flag in quality_flags and reason not in reasons:
                reasons.append(reason)
                quality_tier = "Q1"
                first_core_eligible = False

    if quality_tier not in ("Q0", "Q1"):
        for flag in sorted(_Q2_FLAGS):
            if flag in quality_flags:
                flags.append(flag)
        if flags:
            quality_tier = "Q2"
            first_core_eligible = False

    return QualityGateResult(
        quality_tier=quality_tier,
        first_core_eligible=first_core_eligible,
        reasons=tuple(reasons),
        flags=tuple(flags),
    )


def _quality_flags(metadata: Mapping[str, object]) -> frozenset[str]:
    flags = metadata.get("quality_flags", ())
    if isinstance(flags, (list, tuple, set, frozenset)):
        return frozenset(str(flag) for flag in flags)
    return frozenset()


def _is_supported_family(value: object) -> bool:
    if value is None:
        return False
    text = str(value).strip()
    if "_" not in text:
        return False
    residue_token, reaction_class = text.split("_", 1)
    return (
        residue_token in VALID_RESIDUE_NAMES
        and reaction_class in VALID_REACTION_CLASSES
    )
