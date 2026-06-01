from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

from covalent_design.contracts.atom_resolution import resolve_protein_atom
from covalent_design.contracts.types import (
    EdgeDenominators,
    ProteinAtomIdentity,
    StepwiseCandidate,
    StepwiseCandidateSet,
)


@dataclass(frozen=True)
class StepwiseCandidateBatch:
    """Padded per-timestep candidate view consumed by Task 20 and Task 24."""

    candidate_sets: tuple[StepwiseCandidateSet, ...]
    candidate_counts: tuple[int, ...]
    padded_shape: tuple[int, int]
    denominators_observed: EdgeDenominators


def build_stepwise_candidate_batch(
    candidate_sets: Iterable[StepwiseCandidateSet],
) -> StepwiseCandidateBatch:
    """Build a deterministic padded view without materializing tensors."""
    sets = tuple(candidate_sets)
    if not sets:
        raise ValueError("candidate_sets must not be empty")
    counts = tuple(len(candidate_set.candidates) for candidate_set in sets)
    observed = _sum_denominators(candidate_set.denominators for candidate_set in sets)
    return StepwiseCandidateBatch(
        candidate_sets=sets,
        candidate_counts=counts,
        padded_shape=(len(sets), max(counts)),
        denominators_observed=observed,
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
        altloc=positive_target_atom_dict.get("altloc"),
        insertion_code=positive_target_atom_dict.get("insertion_code"),
        structure_model=positive_target_atom_dict.get("structure_model"),
        asym_id=positive_target_atom_dict.get("asym_id"),
        atom_serial=positive_target_atom_dict.get("atom_serial"),
    )

    target_atom_name = positive_target_atom_dict["atom_name"]
    target_atom = resolve_protein_atom(
        protein_atoms,
        target_atom_index=positive_target_atom_dict.get("atom_index"),
        target_atom_name=target_atom_name,
        target_atom_identity=target_atom_identity,
    )
    tx, ty, tz = target_atom["x"], target_atom["y"], target_atom["z"]

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
    natural_positive_count = sum(
        1 for c in candidates if c.is_positive_label and not c.is_forced_positive
    )

    denominators = EdgeDenominators(
        candidate_count=total_count,
        natural_candidate_count=natural_count,
        forced_positive_count=forced_count,
        eligible_edge_count=total_count,
        masked_candidate_count=0,
        edge_loss_denominator=total_count,
        bond_type_loss_denominator=natural_positive_count,
        geometry_loss_denominator=natural_positive_count,
        message_passing_candidate_count=natural_count,
        gate_evaluated_count=total_count,
    )
    denominators.validate()

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


def _sum_denominators(denominators: Iterable[EdgeDenominators]) -> EdgeDenominators:
    values = tuple(denominators)
    total = EdgeDenominators(
        candidate_count=sum(value.candidate_count for value in values),
        natural_candidate_count=sum(value.natural_candidate_count for value in values),
        forced_positive_count=sum(value.forced_positive_count for value in values),
        eligible_edge_count=sum(value.eligible_edge_count for value in values),
        masked_candidate_count=sum(value.masked_candidate_count for value in values),
        edge_loss_denominator=sum(value.edge_loss_denominator for value in values),
        bond_type_loss_denominator=sum(value.bond_type_loss_denominator for value in values),
        geometry_loss_denominator=sum(value.geometry_loss_denominator for value in values),
        message_passing_candidate_count=sum(
            value.message_passing_candidate_count for value in values
        ),
        gate_evaluated_count=sum(value.gate_evaluated_count for value in values),
    )
    total.validate()
    return total
