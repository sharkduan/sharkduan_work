from __future__ import annotations

import math

from covalent_design.contracts.types import (
    EdgeDenominators,
    ProteinAtomIdentity,
    StepwiseCandidate,
    StepwiseCandidateSet,
)


def build_stepwise_candidates(
    *,
    protein_atoms: list[dict],
    ligand_atoms: list[dict],
    edge_candidates_artifact: dict,
    timestep_index: int,
    timestep_value: float,
    candidate_radius_angstrom: float = 4.0,
) -> StepwiseCandidateSet:
    positive_edge = edge_candidates_artifact["positive_edge"]
    positive_ligand_atom_index: int = positive_edge["ligand_atom_index"]
    positive_target_atom_dict: dict = positive_edge["target_atom"]
    positive_bond_type: str = positive_edge["bond_type"]

    target_atom_identity = ProteinAtomIdentity(
        chain_id=positive_target_atom_dict.get("chain_id"),
        residue_number=positive_target_atom_dict.get("residue_number"),
        residue_name=positive_target_atom_dict["residue_name"],
        atom_name=positive_target_atom_dict["atom_name"],
    )

    target_atom_name = positive_target_atom_dict["atom_name"]
    target_coords = None
    for atom in protein_atoms:
        if atom.get("name") == target_atom_name:
            target_coords = (atom["x"], atom["y"], atom["z"])
            break
    if target_coords is None:
        raise ValueError(
            f"Target atom {target_atom_name!r} not found in protein_atoms"
        )

    tx, ty, tz = target_coords

    entries: list[dict] = []
    positive_found = False
    for position, lig_atom in enumerate(ligand_atoms):
        lig_index = lig_atom.get("index", position)
        dx = lig_atom["x"] - tx
        dy = lig_atom["y"] - ty
        dz = lig_atom["z"] - tz
        distance = math.sqrt(dx * dx + dy * dy + dz * dz)

        is_positive = lig_index == positive_ligand_atom_index
        within_radius = distance < candidate_radius_angstrom

        if is_positive:
            positive_found = True
            entries.append({
                "ligand_atom_index": lig_index,
                "distance": distance,
                "is_positive_label": True,
                "is_forced_positive": not within_radius,
                "within_radius": within_radius,
            })
        elif within_radius:
            entries.append({
                "ligand_atom_index": lig_index,
                "distance": distance,
                "is_positive_label": False,
                "is_forced_positive": False,
                "within_radius": True,
            })

    if not positive_found:
        raise ValueError(
            "positive ligand_atom_index "
            f"{positive_ligand_atom_index!r} not found in ligand_atoms"
        )

    positive_entries = [e for e in entries if e["is_positive_label"]]
    negative_entries = [e for e in entries if not e["is_positive_label"]]
    negative_entries.sort(key=lambda e: (e["distance"], e["ligand_atom_index"]))

    sorted_entries = positive_entries + negative_entries

    candidates: list[StepwiseCandidate] = []
    for local_idx, entry in enumerate(sorted_entries):
        candidates.append(StepwiseCandidate(
            local_index=local_idx,
            ligand_atom_index=entry["ligand_atom_index"],
            target_atom=target_atom_identity,
            is_positive_label=entry["is_positive_label"],
            is_forced_positive=entry["is_forced_positive"],
            within_radius=entry["within_radius"],
            distance=entry["distance"],
        ))

    total_count = len(candidates)
    natural_count = sum(1 for c in candidates if c.within_radius)
    forced_count = sum(1 for c in candidates if c.is_forced_positive)
    natural_negative_count = sum(
        1 for c in candidates if not c.is_positive_label and c.within_radius
    )

    denominators = EdgeDenominators(
        candidate_count=total_count,
        natural_candidate_count=natural_count,
        forced_positive_count=forced_count,
        eligible_edge_count=total_count,
        masked_candidate_count=0,
        edge_loss_denominator=total_count,
        bond_type_loss_denominator=natural_count,
        geometry_loss_denominator=natural_count,
        message_passing_candidate_count=natural_count,
        gate_evaluated_count=total_count,
    )

    return StepwiseCandidateSet(
        timestep_index=timestep_index,
        timestep_value=timestep_value,
        candidates=tuple(candidates),
        positive_label_ligand_atom_index=positive_ligand_atom_index,
        positive_label_target_atom=target_atom_identity,
        positive_label_bond_type=positive_bond_type,
        denominators=denominators,
        empty_radius_window=(natural_negative_count == 0),
    )
