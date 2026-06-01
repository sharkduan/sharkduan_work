"""Build StepwiseCandidateSet fixtures for mask/denominator tests.

Usage from tests::

    from tests.fixtures.training.masks_denominators._builder import (
        MasksDenominatorsFixtureBuilder,
    )

    builder = MasksDenominatorsFixtureBuilder()
    cs = builder.build_natural_positive_set()
"""

from __future__ import annotations

from covalent_design.contracts.types import (
    EdgeDenominators,
    ProteinAtomIdentity,
    StepwiseCandidate,
    StepwiseCandidateSet,
)


def _target_atom() -> ProteinAtomIdentity:
    return ProteinAtomIdentity(
        chain_id="A",
        residue_number=145,
        residue_name="CYS",
        atom_name="SG",
        atom_serial=1234,
    )


def _make_candidate(
    local_index: int,
    ligand_atom_index: int,
    is_positive_label: bool,
    is_forced_positive: bool,
    within_radius: bool,
    distance: float,
    target_atom: ProteinAtomIdentity | None = None,
) -> StepwiseCandidate:
    return StepwiseCandidate(
        local_index=local_index,
        ligand_atom_index=ligand_atom_index,
        target_atom=target_atom or _target_atom(),
        is_positive_label=is_positive_label,
        is_forced_positive=is_forced_positive,
        within_radius=within_radius,
        distance=distance,
    )


def _make_base_denominators(
    candidate_count: int,
    natural_count: int,
    forced_count: int,
) -> EdgeDenominators:
    return EdgeDenominators(
        candidate_count=candidate_count,
        natural_candidate_count=natural_count,
        forced_positive_count=forced_count,
        eligible_edge_count=candidate_count,
        masked_candidate_count=0,
        edge_loss_denominator=candidate_count,
        bond_type_loss_denominator=natural_count,
        geometry_loss_denominator=natural_count,
        message_passing_candidate_count=natural_count,
        gate_evaluated_count=candidate_count,
    )


class MasksDenominatorsFixtureBuilder:
    """Builds StepwiseCandidateSet objects for mask/denominator test scenarios."""

    # -- natural positive (within radius) -----------------------------------

    def build_natural_positive_set(
        self,
        timestep_index: int = 0,
        timestep_value: float = 0.5,
    ) -> StepwiseCandidateSet:
        """NP=1 (within radius), NN=2, FP=0, TC=3.

        Positive ligand atom index=0 at distance 2.0 (within 4.0 radius).
        Two non-positive atoms at distances 2.2 and 3.0.
        """
        target = _target_atom()
        candidates = (
            _make_candidate(0, 0, True, False, True, 2.0, target),
            _make_candidate(1, 1, False, False, True, 2.2, target),
            _make_candidate(2, 2, False, False, True, 3.0, target),
        )
        return StepwiseCandidateSet(
            timestep_index=timestep_index,
            timestep_value=timestep_value,
            candidates=candidates,
            positive_label_ligand_atom_index=0,
            positive_label_target_atom=target,
            positive_label_bond_type="carbon-sulfur",
            denominators=_make_base_denominators(3, 3, 0),
            empty_radius_window=False,
        )

    # -- forced positive (outside radius) ----------------------------------

    def build_forced_positive_set(
        self,
        timestep_index: int = 0,
        timestep_value: float = 0.5,
    ) -> StepwiseCandidateSet:
        """NP=0, FP=1 (outside radius), NN=2, TC=3.

        Positive ligand atom index=0 at distance 5.0 (outside 4.0 radius).
        Two non-positive atoms within radius.
        """
        target = _target_atom()
        candidates = (
            _make_candidate(0, 0, True, True, False, 5.0, target),
            _make_candidate(1, 1, False, False, True, 2.2, target),
            _make_candidate(2, 2, False, False, True, 3.0, target),
        )
        return StepwiseCandidateSet(
            timestep_index=timestep_index,
            timestep_value=timestep_value,
            candidates=candidates,
            positive_label_ligand_atom_index=0,
            positive_label_target_atom=target,
            positive_label_bond_type="carbon-sulfur",
            denominators=_make_base_denominators(3, 2, 1),
            empty_radius_window=False,
        )

    # -- zero natural negatives (empty radius window) -----------------------

    def build_zero_natural_negatives_set(
        self,
        timestep_index: int = 0,
        timestep_value: float = 0.5,
    ) -> StepwiseCandidateSet:
        """NP=1 (within radius), NN=0, FP=0, TC=1.

        Only the positive atom is within radius.
        """
        target = _target_atom()
        candidates = (
            _make_candidate(0, 0, True, False, True, 2.0, target),
        )
        return StepwiseCandidateSet(
            timestep_index=timestep_index,
            timestep_value=timestep_value,
            candidates=candidates,
            positive_label_ligand_atom_index=0,
            positive_label_target_atom=target,
            positive_label_bond_type="carbon-sulfur",
            denominators=_make_base_denominators(1, 1, 0),
            empty_radius_window=True,
        )

    # -- large candidate set for multi-strata aggregation tests -------------

    def build_large_positive_set(
        self,
        timestep_index: int = 0,
        timestep_value: float = 0.5,
        num_negatives: int = 4,
    ) -> StepwiseCandidateSet:
        """NP=1, NN=num_negatives, FP=0, TC=1+num_negatives."""
        target = _target_atom()
        candidates = [
            _make_candidate(0, 0, True, False, True, 2.0, target),
        ]
        for i in range(num_negatives):
            candidates.append(
                _make_candidate(i + 1, i + 1, False, False, True, 2.0 + i * 0.5, target)
            )
        tc = 1 + num_negatives
        return StepwiseCandidateSet(
            timestep_index=timestep_index,
            timestep_value=timestep_value,
            candidates=tuple(candidates),
            positive_label_ligand_atom_index=0,
            positive_label_target_atom=target,
            positive_label_bond_type="carbon-sulfur",
            denominators=_make_base_denominators(tc, tc, 0),
            empty_radius_window=False,
        )
