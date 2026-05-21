from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from covalent_design.contracts import SourceRecordLineage


@dataclass(frozen=True)
class ConflictAnchor:
    structure_id: str
    ligand_id: str
    ligand_chain_id: Optional[str]
    ligand_asym_id: Optional[str]
    ligand_residue_number: Optional[int]


@dataclass(frozen=True)
class ConflictGroup:
    conflict_group_id: str
    anchor: ConflictAnchor
    lineage: tuple[SourceRecordLineage, ...]
    conflicting_identities: tuple[object, ...]
    reason: str
