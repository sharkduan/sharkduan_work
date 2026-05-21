"""Typed schemas for the reaction family rule table."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# first-pass residue vocabulary
# ---------------------------------------------------------------------------

VALID_RESIDUE_NAMES = frozenset({"CYS", "SER", "LYS"})

RESIDUE_ATOM_CONTRACT: dict[str, str] = {
    "CYS": "SG",
    "SER": "OG",
    "LYS": "NZ",
}

VALID_REACTION_CLASSES = frozenset({
    "MICHAEL_ADDITION",
    "NUCLEOPHILIC_SUBSTITUTION",
    "DISULFIDE_EXCHANGE",
    "ACYLATION",
    "PHOSPHONYLATION",
    "SCHIFF_BASE",
})

VALID_WARHEAD_STATUSES = frozenset({"calibrated", "pending", "not_applicable"})
VALID_GEOMETRY_STATUSES = frozenset({"calibrated", "pending", "disabled"})
VALID_PROTEIN_STATE_VALUES = frozenset({
    "required",
    "optional",
    "not_applicable",
    "required_or_inferred",
})
VALID_LIGAND_NEIGHBOR_POLICIES = frozenset({
    "first_heavy_atom_excluding_target",
    "warhead_reaction_center_neighbor",
    "manual_atom_map_neighbor",
    "not_applicable",
})
VALID_ANCHOR_ATOMS: dict[str, str] = {
    "CYS": "CB",
    "SER": "CB",
    "LYS": "CE",
}


# ---------------------------------------------------------------------------
# nested types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GeometryRange:
    min: Optional[float]
    max: Optional[float]
    unit: str


@dataclass(frozen=True)
class GeometryStatus:
    bond_length: str
    protein_side_angle: str
    ligand_side_angle: str


@dataclass(frozen=True)
class ProteinStateRequirements:
    target_atom_formal_charge: str
    target_atom_protonation_state: str
    explicit_hydrogen_state: str


@dataclass(frozen=True)
class ValenceDelta:
    target_atom: int
    ligand_attachment_atom: int


# ---------------------------------------------------------------------------
# rule row and table
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ReactionFamilyRuleRow:
    family_id: str
    target_residue_name: str
    target_atom_name: str
    residue_reaction_class: str
    allowed_ligand_attachment_elements: tuple[str, ...]
    allowed_covalent_bond_types: tuple[str, ...]
    allowed_warhead_smarts: tuple[str, ...]
    warhead_rule_status: str
    forbidden_warhead_smarts: tuple[str, ...] = ()
    bond_length_range: GeometryRange = field(
        default_factory=lambda: GeometryRange(None, None, "angstrom")
    )
    protein_side_angle_range: GeometryRange = field(
        default_factory=lambda: GeometryRange(None, None, "degree")
    )
    ligand_side_angle_range: GeometryRange = field(
        default_factory=lambda: GeometryRange(None, None, "degree")
    )
    geometry_status: GeometryStatus = field(
        default_factory=lambda: GeometryStatus("pending", "pending", "pending")
    )
    anchor_atom_name: Optional[str] = None
    ligand_neighbor_policy: Optional[str] = None
    protein_state_requirements: Optional[ProteinStateRequirements] = None
    valence_delta: Optional[ValenceDelta] = None
    notes: str = ""


@dataclass(frozen=True)
class ReactionFamilyRuleTable:
    version: int
    families: tuple[ReactionFamilyRuleRow, ...]
    input_sha256: str = ""


@dataclass
class RuleValidationReport:
    families: list[dict]
    ok: bool = True
    error_codes: list[str] = field(default_factory=list)
