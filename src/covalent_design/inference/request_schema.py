"""Task 26 request schema types.

Public API dataclasses for reactive-site generation requests and
validated request output.
"""

from __future__ import annotations

from dataclasses import dataclass

from covalent_design.contracts.types import ProteinAtomIdentity


@dataclass(frozen=True)
class ProteinAtomLocator:
    """Locator describing the target protein atom in structural terms."""

    chain_id: str | None
    residue_number: int | None
    residue_name: str
    atom_name: str
    insertion_code: str | None = None
    structure_model: int | None = None
    asym_id: str | None = None


@dataclass(frozen=True)
class LigandSizeControl:
    """Fixed or range ligand-size constraints.  Exactly one mode must be set."""

    num_ligand_heavy_atoms: int | None = None
    min_ligand_heavy_atoms: int | None = None
    max_ligand_heavy_atoms: int | None = None


@dataclass(frozen=True)
class ProteinChemicalStateRequest:
    """User-supplied or tool-inferred chemical state of the target atom."""

    target_atom_formal_charge: int | None = None
    target_atom_protonation_state: str | None = None
    target_atom_hydrogen_state: str | None = None
    protein_preparation_policy: str | None = None
    chemical_state_source: str | None = None
    chemical_state_tool_name: str | None = None
    chemical_state_tool_version: str | None = None
    chemical_state_confidence: str | None = None


@dataclass(frozen=True)
class ReactiveSiteGenerationRequest:
    """A complete reactive-site generation request."""

    request_id: str
    protein_structure_uri: str
    protein_structure_format: str
    target_atom_identity_request: ProteinAtomLocator
    residue_reaction_family: str
    sample_count: int
    size_control: LigandSizeControl | None = None
    protein_chemical_state_request: ProteinChemicalStateRequest | None = None
    target_altloc: str | None = None


@dataclass(frozen=True)
class ValidatedRequest:
    """A validated reactive-site generation request with resolved identities."""

    request: ReactiveSiteGenerationRequest
    resolved_target_atom_identity: ProteinAtomIdentity
    resolved_target_altloc: str | None
    rule_table_version: int
