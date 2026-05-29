"""Tests for Task 18 stepwise candidate builder.

Covers 16 requirements for stepwise covalent edge candidate construction.

Public API under test:
    covalent_design.model.candidate_builder.build_stepwise_candidates(...)

These are contract and regression tests for the implemented Task 18 API.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest


# ---------------------------------------------------------------------------
# production import
# ---------------------------------------------------------------------------

_build_stepwise_candidates = None
_IMPORT_ERRORS: list[str] = []

try:
    from covalent_design.model.candidate_builder import (
        build_stepwise_candidates as _bsc,
    )
    _build_stepwise_candidates = _bsc
except ImportError as exc:
    _IMPORT_ERRORS.append(f"build_stepwise_candidates: {exc}")

# contract types (these exist already in Task 17)
from covalent_design.contracts.types import (
    EdgeDenominators,
    ProteinAtomIdentity,
    StepwiseCandidate,
    StepwiseCandidateSet,
)

from tests.fixtures.model.stepwise_candidates._builder import (
    StepwiseCandidateFixtureBuilder,
)


def _raise_if_missing() -> None:
    """Fail with a clear message if production code is not importable."""
    if not _IMPORT_ERRORS:
        return
    raise unittest.SkipTest(
        "Production code import failed. "
        + "; ".join(_IMPORT_ERRORS)
    )


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _ligand_coords_shifted(
    atoms: list[dict],
    shifts: list[tuple[float, float, float]],
) -> list[dict]:
    """Return a copy of ligand atoms with coordinates shifted for a timestep."""
    result: list[dict] = []
    for atom, (dx, dy, dz) in zip(atoms, shifts):
        a = dict(atom)
        a["x"] = a["x"] + dx
        a["y"] = a["y"] + dy
        a["z"] = a["z"] + dz
        result.append(a)
    return result


def _find_candidate_by_ligand_index(
    candidates: tuple[StepwiseCandidate, ...],
    ligand_atom_index: int,
) -> StepwiseCandidate:
    for c in candidates:
        if c.ligand_atom_index == ligand_atom_index:
            return c
    raise ValueError(
        f"No candidate with ligand_atom_index {ligand_atom_index}"
    )


# ===================================================================
# Requirement 1: natural positive within radius
# ===================================================================


class NaturalPositiveWithinRadiusTests(unittest.TestCase):
    """Requirement 1: when the positive ligand atom is within the candidate
    radius, it appears as a natural (non-forced) candidate."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = StepwiseCandidateFixtureBuilder()
        cls.protein_atoms, cls.ligand_atoms, cls.edge_candidates = (
            cls.builder.load("within_radius")
        )

    def test_positive_atom_included_as_candidate(self) -> None:
        _raise_if_missing()
        result = _build_stepwise_candidates(
            protein_atoms=self.protein_atoms,
            ligand_atoms=self.ligand_atoms,
            edge_candidates_artifact=self.edge_candidates,
            timestep_index=0,
            timestep_value=0.5,
        )
        self.assertIsInstance(result, StepwiseCandidateSet)

        pos_candidate = _find_candidate_by_ligand_index(
            result.candidates, ligand_atom_index=0
        )
        self.assertTrue(pos_candidate.is_positive_label)
        self.assertTrue(pos_candidate.within_radius)
        self.assertFalse(pos_candidate.is_forced_positive)

    def test_distance_matches_expected(self) -> None:
        _raise_if_missing()
        result = _build_stepwise_candidates(
            protein_atoms=self.protein_atoms,
            ligand_atoms=self.ligand_atoms,
            edge_candidates_artifact=self.edge_candidates,
            timestep_index=0,
            timestep_value=0.5,
        )
        pos = _find_candidate_by_ligand_index(result.candidates, 0)
        # SG at (0,0,0), C1 at (2,0,0): distance = 2.0 A
        self.assertAlmostEqual(pos.distance, 2.0, places=4)


# ===================================================================
# Requirement 2: forced positive outside radius
# ===================================================================


class ForcedPositiveOutsideRadiusTests(unittest.TestCase):
    """Requirement 2: when the positive ligand atom is outside the candidate
    radius, it is force-included as a candidate."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = StepwiseCandidateFixtureBuilder()
        cls.protein_atoms, cls.ligand_atoms, cls.edge_candidates = (
            cls.builder.load("outside_radius")
        )

    def test_positive_outside_radius_is_force_included(self) -> None:
        _raise_if_missing()
        result = _build_stepwise_candidates(
            protein_atoms=self.protein_atoms,
            ligand_atoms=self.ligand_atoms,
            edge_candidates_artifact=self.edge_candidates,
            timestep_index=0,
            timestep_value=0.5,
        )
        pos = _find_candidate_by_ligand_index(result.candidates, 0)
        self.assertTrue(pos.is_positive_label)
        self.assertFalse(pos.within_radius)
        self.assertTrue(pos.is_forced_positive)

    def test_positive_distance_exceeds_radius(self) -> None:
        _raise_if_missing()
        result = _build_stepwise_candidates(
            protein_atoms=self.protein_atoms,
            ligand_atoms=self.ligand_atoms,
            edge_candidates_artifact=self.edge_candidates,
            timestep_index=0,
            timestep_value=0.5,
        )
        pos = _find_candidate_by_ligand_index(result.candidates, 0)
        # SG at (0,0,0), C1 at (5,0,0): distance = 5.0 A
        self.assertAlmostEqual(pos.distance, 5.0, places=4)
        self.assertGreater(pos.distance, 4.0)


# ===================================================================
# Requirement 3: zero natural negatives and empty_radius_window
# ===================================================================


class ZeroNaturalNegativesTests(unittest.TestCase):
    """Requirement 3: when no non-positive ligand atoms fall within the
    radius, the candidate set has zero natural negatives and
    empty_radius_window is True."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = StepwiseCandidateFixtureBuilder()
        cls.protein_atoms, cls.ligand_atoms, cls.edge_candidates = (
            cls.builder.load("zero_natural_negatives")
        )

    def test_only_positive_candidate_present(self) -> None:
        _raise_if_missing()
        result = _build_stepwise_candidates(
            protein_atoms=self.protein_atoms,
            ligand_atoms=self.ligand_atoms,
            edge_candidates_artifact=self.edge_candidates,
            timestep_index=0,
            timestep_value=0.5,
        )
        self.assertEqual(len(result.candidates), 1)
        self.assertTrue(result.candidates[0].is_positive_label)
        self.assertFalse(result.candidates[0].is_forced_positive)

    def test_empty_radius_window_is_true(self) -> None:
        _raise_if_missing()
        result = _build_stepwise_candidates(
            protein_atoms=self.protein_atoms,
            ligand_atoms=self.ligand_atoms,
            edge_candidates_artifact=self.edge_candidates,
            timestep_index=0,
            timestep_value=0.5,
        )
        self.assertTrue(result.empty_radius_window)

    def test_natural_candidate_count_is_one(self) -> None:
        _raise_if_missing()
        result = _build_stepwise_candidates(
            protein_atoms=self.protein_atoms,
            ligand_atoms=self.ligand_atoms,
            edge_candidates_artifact=self.edge_candidates,
            timestep_index=0,
            timestep_value=0.5,
        )
        self.assertEqual(
            result.denominators.natural_candidate_count, 1
        )
        self.assertEqual(result.denominators.forced_positive_count, 0)
        self.assertEqual(result.denominators.candidate_count, 1)


# ===================================================================
# Requirement 4: per-timestep deterministic rebuild from changed
#               ligand coordinates
# ===================================================================


class PerTimestepRebuildTests(unittest.TestCase):
    """Requirements 4, 11, 12: each timestep rebuilds candidates from the
    current noisy ligand coordinates.  local_index restarts per timestep;
    ligand_atom_index is cross-timestep stable."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = StepwiseCandidateFixtureBuilder()
        cls.protein_atoms, cls.base_ligand_atoms, cls.edge_candidates = (
            cls.builder.load("within_radius")
        )

    def test_different_coordinates_produce_different_distances(self) -> None:
        """Requirement 4: rebuilding with shifted coords changes distances."""
        _raise_if_missing()
        # timestep 0: original coords
        t0 = _build_stepwise_candidates(
            protein_atoms=self.protein_atoms,
            ligand_atoms=self.base_ligand_atoms,
            edge_candidates_artifact=self.edge_candidates,
            timestep_index=0,
            timestep_value=0.3,
        )
        # timestep 1: shifted coords
        shifted = _ligand_coords_shifted(
            self.base_ligand_atoms,
            [(0.5, 0.5, 0.0), (-0.5, -0.5, 0.0), (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)],
        )
        t1 = _build_stepwise_candidates(
            protein_atoms=self.protein_atoms,
            ligand_atoms=shifted,
            edge_candidates_artifact=self.edge_candidates,
            timestep_index=1,
            timestep_value=0.7,
        )

        # distances for the same ligand_atom_index should differ
        c0 = _find_candidate_by_ligand_index(t0.candidates, 0)
        c1 = _find_candidate_by_ligand_index(t1.candidates, 0)
        self.assertNotEqual(c0.distance, c1.distance)

    def test_local_index_restarts_per_timestep(self) -> None:
        """Requirement 11: local_index starts from 0 each timestep."""
        _raise_if_missing()
        shifted = _ligand_coords_shifted(
            self.base_ligand_atoms,
            [(0.5, 0.5, 0.0), (-0.5, -0.5, 0.0), (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)],
        )
        t0 = _build_stepwise_candidates(
            protein_atoms=self.protein_atoms,
            ligand_atoms=self.base_ligand_atoms,
            edge_candidates_artifact=self.edge_candidates,
            timestep_index=0,
            timestep_value=0.3,
        )
        t1 = _build_stepwise_candidates(
            protein_atoms=self.protein_atoms,
            ligand_atoms=shifted,
            edge_candidates_artifact=self.edge_candidates,
            timestep_index=1,
            timestep_value=0.7,
        )

        # Each timestep's local_index values should be a contiguous
        # range starting from 0, independent of the previous timestep.
        t0_indices = {c.local_index for c in t0.candidates}
        t1_indices = {c.local_index for c in t1.candidates}
        self.assertIn(0, t0_indices)
        self.assertIn(0, t1_indices)
        self.assertEqual(
            max(t0_indices), len(t0.candidates) - 1,
            "local_index should be contiguous 0..N-1",
        )
        self.assertEqual(
            max(t1_indices), len(t1.candidates) - 1,
            "local_index should be contiguous 0..N-1",
        )

    def test_ligand_atom_index_cross_timestep_stable(self) -> None:
        """Requirement 12: same atom has same ligand_atom_index in both
        timesteps."""
        _raise_if_missing()
        shifted = _ligand_coords_shifted(
            self.base_ligand_atoms,
            [(0.5, 0.5, 0.0), (-0.5, -0.5, 0.0), (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)],
        )
        t0 = _build_stepwise_candidates(
            protein_atoms=self.protein_atoms,
            ligand_atoms=self.base_ligand_atoms,
            edge_candidates_artifact=self.edge_candidates,
            timestep_index=0,
            timestep_value=0.3,
        )
        t1 = _build_stepwise_candidates(
            protein_atoms=self.protein_atoms,
            ligand_atoms=shifted,
            edge_candidates_artifact=self.edge_candidates,
            timestep_index=1,
            timestep_value=0.7,
        )

        # ligand_atom_index 0 (C1) must be present in both timesteps
        c0 = _find_candidate_by_ligand_index(t0.candidates, 0)
        c1 = _find_candidate_by_ligand_index(t1.candidates, 0)
        self.assertEqual(c0.ligand_atom_index, 0)
        self.assertEqual(c1.ligand_atom_index, 0)
        # local_index may differ
        self.assertIsInstance(c0.local_index, int)
        self.assertIsInstance(c1.local_index, int)

    def test_timestep_index_and_value_preserved(self) -> None:
        """Requirement 4: StepwiseCandidateSet carries correct timestep
        metadata."""
        _raise_if_missing()
        t0 = _build_stepwise_candidates(
            protein_atoms=self.protein_atoms,
            ligand_atoms=self.base_ligand_atoms,
            edge_candidates_artifact=self.edge_candidates,
            timestep_index=5,
            timestep_value=0.42,
        )
        self.assertEqual(t0.timestep_index, 5)
        self.assertEqual(t0.timestep_value, 0.42)


# ===================================================================
# Requirement 5: candidate_radius_angstrom default 4.0
# ===================================================================


class DefaultRadiusTests(unittest.TestCase):
    """Requirement 5: the default candidate radius is 4.0 Angstroms."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = StepwiseCandidateFixtureBuilder()
        cls.protein_atoms, cls.ligand_atoms, cls.edge_candidates = (
            cls.builder.load("within_radius")
        )

    def test_default_radius_excludes_atoms_beyond_4_angstrom(self) -> None:
        _raise_if_missing()
        result = _build_stepwise_candidates(
            protein_atoms=self.protein_atoms,
            ligand_atoms=self.ligand_atoms,
            edge_candidates_artifact=self.edge_candidates,
            timestep_index=0,
            timestep_value=0.5,
            # no candidate_radius_angstrom: use default
        )
        # O1 at (6,0,0): distance 6.0 A should be excluded
        ligand_indices = {c.ligand_atom_index for c in result.candidates}
        self.assertNotIn(3, ligand_indices)  # O1 is index 3, outside 4.0

    def test_custom_radius_can_include_more_atoms(self) -> None:
        _raise_if_missing()
        result = _build_stepwise_candidates(
            protein_atoms=self.protein_atoms,
            ligand_atoms=self.ligand_atoms,
            edge_candidates_artifact=self.edge_candidates,
            timestep_index=0,
            timestep_value=0.5,
            candidate_radius_angstrom=7.0,
        )
        ligand_indices = {c.ligand_atom_index for c in result.candidates}
        self.assertIn(3, ligand_indices)  # O1 at 6.0 A now within 7.0

    def test_small_radius_excludes_nearby_atoms(self) -> None:
        _raise_if_missing()
        result = _build_stepwise_candidates(
            protein_atoms=self.protein_atoms,
            ligand_atoms=self.ligand_atoms,
            edge_candidates_artifact=self.edge_candidates,
            timestep_index=0,
            timestep_value=0.5,
            candidate_radius_angstrom=1.5,
        )
        # C2 at sqrt(5) ~= 2.236 and C3 at 3.0 both outside 1.5
        # Only the positive C1 at 2.0 is also outside, but must be
        # force-included when outside radius
        ligand_indices = {c.ligand_atom_index for c in result.candidates}
        self.assertIn(0, ligand_indices)  # positive, force-included
        self.assertNotIn(1, ligand_indices)  # C2 outside radius
        self.assertNotIn(2, ligand_indices)  # C3 outside radius


# ===================================================================
# Requirements 6 & 7: positive label from static edge_candidates artifact
# ===================================================================


class PositiveLabelFromArtifactTests(unittest.TestCase):
    """Requirements 6, 7: the positive-label bond type and ligand/target
    atom identity must come from the static edge_candidates artifact,
    not from caller-supplied parameters."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = StepwiseCandidateFixtureBuilder()
        cls.protein_atoms, cls.ligand_atoms, cls.edge_candidates = (
            cls.builder.load("within_radius")
        )

    def test_positive_label_ligand_atom_index_from_artifact(self) -> None:
        """Requirement 6: positive_label_ligand_atom_index is read from
        the edge_candidates artifact, not passed by the caller."""
        _raise_if_missing()
        result = _build_stepwise_candidates(
            protein_atoms=self.protein_atoms,
            ligand_atoms=self.ligand_atoms,
            edge_candidates_artifact=self.edge_candidates,
            timestep_index=0,
            timestep_value=0.5,
        )
        # The artifact declares positive_edge.ligand_atom_index = 0
        self.assertEqual(result.positive_label_ligand_atom_index, 0)

    def test_positive_label_target_atom_from_artifact(self) -> None:
        """Requirement 7: positive_label_target_atom is a
        ProteinAtomIdentity derived from the edge_candidates artifact."""
        _raise_if_missing()
        result = _build_stepwise_candidates(
            protein_atoms=self.protein_atoms,
            ligand_atoms=self.ligand_atoms,
            edge_candidates_artifact=self.edge_candidates,
            timestep_index=0,
            timestep_value=0.5,
        )
        target = result.positive_label_target_atom
        self.assertIsInstance(target, ProteinAtomIdentity)
        self.assertEqual(target.chain_id, "A")
        self.assertEqual(target.residue_number, 42)
        self.assertEqual(target.residue_name, "CYS")
        self.assertEqual(target.atom_name, "SG")

    def test_positive_label_bond_type_from_artifact(self) -> None:
        """Requirement 7: positive_label_bond_type is read from the
        edge_candidates artifact."""
        _raise_if_missing()
        result = _build_stepwise_candidates(
            protein_atoms=self.protein_atoms,
            ligand_atoms=self.ligand_atoms,
            edge_candidates_artifact=self.edge_candidates,
            timestep_index=0,
            timestep_value=0.5,
        )
        self.assertEqual(result.positive_label_bond_type, "carbon-sulfur")

    def test_positive_label_fields_exist_on_set(self) -> None:
        """Requirement 7: all three positive-label fields are present."""
        _raise_if_missing()
        result = _build_stepwise_candidates(
            protein_atoms=self.protein_atoms,
            ligand_atoms=self.ligand_atoms,
            edge_candidates_artifact=self.edge_candidates,
            timestep_index=0,
            timestep_value=0.5,
        )
        self.assertIsInstance(result.positive_label_ligand_atom_index, int)
        self.assertIsInstance(
            result.positive_label_target_atom, ProteinAtomIdentity
        )
        self.assertIsInstance(result.positive_label_bond_type, str)


# ===================================================================
# Requirements 8 & 9: is_forced_positive correctness
# ===================================================================


class ForcedPositiveFlagTests(unittest.TestCase):
    """Requirements 8, 9: is_forced_positive is False when the positive
    is within radius, True when outside."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = StepwiseCandidateFixtureBuilder()
        cls.wr_prot, cls.wr_lig, cls.wr_edge = cls.builder.load(
            "within_radius"
        )
        cls.or_prot, cls.or_lig, cls.or_edge = cls.builder.load(
            "outside_radius"
        )

    def test_within_radius_positive_not_forced(self) -> None:
        """Requirement 8: positive atom within radius has
        is_forced_positive = False."""
        _raise_if_missing()
        result = _build_stepwise_candidates(
            protein_atoms=self.wr_prot,
            ligand_atoms=self.wr_lig,
            edge_candidates_artifact=self.wr_edge,
            timestep_index=0,
            timestep_value=0.5,
        )
        pos = _find_candidate_by_ligand_index(result.candidates, 0)
        self.assertTrue(pos.is_positive_label)
        self.assertTrue(pos.within_radius)
        self.assertFalse(pos.is_forced_positive)

    def test_outside_radius_positive_is_forced(self) -> None:
        """Requirement 9: positive atom outside radius has
        is_forced_positive = True."""
        _raise_if_missing()
        result = _build_stepwise_candidates(
            protein_atoms=self.or_prot,
            ligand_atoms=self.or_lig,
            edge_candidates_artifact=self.or_edge,
            timestep_index=0,
            timestep_value=0.5,
        )
        pos = _find_candidate_by_ligand_index(result.candidates, 0)
        self.assertTrue(pos.is_positive_label)
        self.assertFalse(pos.within_radius)
        self.assertTrue(pos.is_forced_positive)


# ===================================================================
# Requirement 10: forced_positive_count denominator
# ===================================================================


class ForcedPositiveDenominatorTests(unittest.TestCase):
    """Requirement 10: forced_positive_count reflects the count of
    force-included positive edges in the denominators."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = StepwiseCandidateFixtureBuilder()

    def test_within_radius_forced_positive_count_zero(self) -> None:
        _raise_if_missing()
        prot, lig, edge = self.builder.load("within_radius")
        result = _build_stepwise_candidates(
            protein_atoms=prot,
            ligand_atoms=lig,
            edge_candidates_artifact=edge,
            timestep_index=0,
            timestep_value=0.5,
        )
        self.assertEqual(result.denominators.forced_positive_count, 0)

    def test_outside_radius_forced_positive_count_one(self) -> None:
        _raise_if_missing()
        prot, lig, edge = self.builder.load("outside_radius")
        result = _build_stepwise_candidates(
            protein_atoms=prot,
            ligand_atoms=lig,
            edge_candidates_artifact=edge,
            timestep_index=0,
            timestep_value=0.5,
        )
        self.assertEqual(result.denominators.forced_positive_count, 1)

    def test_denominator_equation_holds(self) -> None:
        """candidate_count == natural + forced."""
        _raise_if_missing()
        for scenario in ("within_radius", "outside_radius",
                         "zero_natural_negatives"):
            with self.subTest(scenario=scenario):
                prot, lig, edge = self.builder.load(scenario)
                result = _build_stepwise_candidates(
                    protein_atoms=prot,
                    ligand_atoms=lig,
                    edge_candidates_artifact=edge,
                    timestep_index=0,
                    timestep_value=0.5,
                )
                d = result.denominators
                self.assertEqual(
                    d.candidate_count,
                    d.natural_candidate_count + d.forced_positive_count,
                )

    def test_message_passing_excludes_forced_positives_in_v1(self) -> None:
        """message_passing_candidate_count must not include forced
        positives (ADR 0033)."""
        _raise_if_missing()
        prot, lig, edge = self.builder.load("outside_radius")
        result = _build_stepwise_candidates(
            protein_atoms=prot,
            ligand_atoms=lig,
            edge_candidates_artifact=edge,
            timestep_index=0,
            timestep_value=0.5,
        )
        d = result.denominators
        self.assertEqual(
            d.message_passing_candidate_count,
            d.natural_candidate_count,
        )

    def test_bond_and_geometry_denominators_exclude_forced_positives(self) -> None:
        _raise_if_missing()
        prot, lig, edge = self.builder.load("outside_radius")
        result = _build_stepwise_candidates(
            protein_atoms=prot,
            ligand_atoms=lig,
            edge_candidates_artifact=edge,
            timestep_index=0,
            timestep_value=0.5,
        )
        d = result.denominators
        self.assertEqual(d.bond_type_loss_denominator, d.natural_candidate_count)
        self.assertEqual(d.geometry_loss_denominator, d.natural_candidate_count)


# ===================================================================
# Requirement 13: static vs stepwise naming distinction
# ===================================================================


class StaticVsStepwiseNamingTests(unittest.TestCase):
    """Requirement 13: candidates use StepwiseCandidate type, not static
    edge-candidate naming conventions."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = StepwiseCandidateFixtureBuilder()
        cls.prot, cls.lig, cls.edge = cls.builder.load("within_radius")

    def test_all_candidates_are_stepwise_candidate_instances(self) -> None:
        _raise_if_missing()
        result = _build_stepwise_candidates(
            protein_atoms=self.prot,
            ligand_atoms=self.lig,
            edge_candidates_artifact=self.edge,
            timestep_index=0,
            timestep_value=0.5,
        )
        for c in result.candidates:
            self.assertIsInstance(c, StepwiseCandidate)

    def test_result_is_stepwise_candidate_set(self) -> None:
        _raise_if_missing()
        result = _build_stepwise_candidates(
            protein_atoms=self.prot,
            ligand_atoms=self.lig,
            edge_candidates_artifact=self.edge,
            timestep_index=0,
            timestep_value=0.5,
        )
        self.assertIsInstance(result, StepwiseCandidateSet)

    def test_candidate_has_local_index_not_static_name(self) -> None:
        """StepwiseCandidate uses local_index, not ligand_atom_name as
        the primary per-timestep identifier."""
        _raise_if_missing()
        result = _build_stepwise_candidates(
            protein_atoms=self.prot,
            ligand_atoms=self.lig,
            edge_candidates_artifact=self.edge,
            timestep_index=0,
            timestep_value=0.5,
        )
        for c in result.candidates:
            self.assertIsInstance(c.local_index, int)
            self.assertIsInstance(c.ligand_atom_index, int)
            # local_index is per-timestep; ligand_atom_index is stable
            self.assertGreaterEqual(c.local_index, 0)


# ===================================================================
# Requirement 14: deterministic output
# ===================================================================


class DeterministicOutputTests(unittest.TestCase):
    """Requirement 14: same inputs produce identical StepwiseCandidateSets
    across repeated calls."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = StepwiseCandidateFixtureBuilder()
        cls.prot, cls.lig, cls.edge = cls.builder.load("within_radius")

    def test_repeated_calls_produce_same_candidate_order(self) -> None:
        _raise_if_missing()
        kwargs = dict(
            protein_atoms=self.prot,
            ligand_atoms=self.lig,
            edge_candidates_artifact=self.edge,
            timestep_index=0,
            timestep_value=0.5,
        )
        r1 = _build_stepwise_candidates(**kwargs)
        r2 = _build_stepwise_candidates(**kwargs)

        self.assertEqual(len(r1.candidates), len(r2.candidates))
        for c1, c2 in zip(r1.candidates, r2.candidates):
            self.assertEqual(c1.local_index, c2.local_index)
            self.assertEqual(c1.ligand_atom_index, c2.ligand_atom_index)
            self.assertEqual(c1.is_positive_label, c2.is_positive_label)
            self.assertEqual(c1.is_forced_positive, c2.is_forced_positive)
            self.assertEqual(c1.within_radius, c2.within_radius)
            self.assertAlmostEqual(c1.distance, c2.distance, places=6)

    def test_repeated_calls_produce_same_denominators(self) -> None:
        _raise_if_missing()
        kwargs = dict(
            protein_atoms=self.prot,
            ligand_atoms=self.lig,
            edge_candidates_artifact=self.edge,
            timestep_index=0,
            timestep_value=0.5,
        )
        d1 = _build_stepwise_candidates(**kwargs).denominators
        d2 = _build_stepwise_candidates(**kwargs).denominators
        self.assertEqual(d1, d2)

    def test_repeated_calls_produce_same_positive_label_fields(self) -> None:
        _raise_if_missing()
        kwargs = dict(
            protein_atoms=self.prot,
            ligand_atoms=self.lig,
            edge_candidates_artifact=self.edge,
            timestep_index=0,
            timestep_value=0.5,
        )
        r1 = _build_stepwise_candidates(**kwargs)
        r2 = _build_stepwise_candidates(**kwargs)
        self.assertEqual(
            r1.positive_label_ligand_atom_index,
            r2.positive_label_ligand_atom_index,
        )
        self.assertEqual(
            r1.positive_label_target_atom,
            r2.positive_label_target_atom,
        )
        self.assertEqual(
            r1.positive_label_bond_type,
            r2.positive_label_bond_type,
        )


# ===================================================================
# Requirement 15: no model/training artifacts created
# ===================================================================


class NoModelArtifactsTests(unittest.TestCase):
    """Requirement 15: build_stepwise_candidates must not create any
    model or training artifacts on disk."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = StepwiseCandidateFixtureBuilder()
        cls.prot, cls.lig, cls.edge = cls.builder.load("within_radius")

    def test_no_files_created_in_cwd(self) -> None:
        _raise_if_missing()
        with tempfile.TemporaryDirectory() as tmpdir:
            cwd_before = set(os.listdir(tmpdir))
            # run in tmpdir to isolate side effects
            old_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                _build_stepwise_candidates(
                    protein_atoms=self.prot,
                    ligand_atoms=self.lig,
                    edge_candidates_artifact=self.edge,
                    timestep_index=0,
                    timestep_value=0.5,
                )
            finally:
                os.chdir(old_cwd)
            cwd_after = set(os.listdir(tmpdir))
            new_files = cwd_after - cwd_before - {"__pycache__"}
            self.assertEqual(
                len(new_files), 0,
                f"build_stepwise_candidates must not create files; "
                f"found {new_files}",
            )

    def test_no_temporary_directories_persist(self) -> None:
        """All computation must happen in memory; no artifact output."""
        _raise_if_missing()
        with tempfile.TemporaryDirectory() as tmpdir:
            before = set(os.listdir(tmpdir))
            old_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                _build_stepwise_candidates(
                    protein_atoms=self.prot,
                    ligand_atoms=self.lig,
                    edge_candidates_artifact=self.edge,
                    timestep_index=0,
                    timestep_value=0.5,
                )
            finally:
                os.chdir(old_cwd)
            after = set(os.listdir(tmpdir))
            self.assertEqual(
                before - {"__pycache__"},
                after - {"__pycache__"},
            )


# ===================================================================
# Requirement 16: no RDKit or torch import
# ===================================================================


class NoRdkitOrTorchImportTests(unittest.TestCase):
    """Requirement 16: the candidate_builder module must not import RDKit
    or torch."""

    def test_candidate_builder_does_not_import_rdkit_or_torch(self) -> None:
        """Verify that importing candidate_builder does not add rdkit or
        torch to sys.modules if they weren't already present."""
        # Snapshot before import
        pre_modules = set(sys.modules.keys())

        # Force re-import to detect transitive imports
        mod_name = "covalent_design.model.candidate_builder"
        if mod_name in sys.modules:
            del sys.modules[mod_name]

        try:
            from covalent_design.model import candidate_builder  # noqa: F811
        except ImportError:
            raise unittest.SkipTest(
                "Production code import failed."
            )

        post_modules = set(sys.modules.keys())
        new_modules = post_modules - pre_modules

        rdkit_new = [m for m in new_modules if m.startswith("rdkit")]
        torch_new = [m for m in new_modules if m.startswith("torch")]

        self.assertEqual(
            rdkit_new, [],
            f"candidate_builder imported rdkit modules: {rdkit_new}",
        )
        self.assertEqual(
            torch_new, [],
            f"candidate_builder imported torch modules: {torch_new}",
        )


# ===================================================================
# Additional: negative candidates have correct is_positive_label
# ===================================================================


class NegativeCandidateLabelTests(unittest.TestCase):
    """Every non-positive candidate must have is_positive_label = False."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = StepwiseCandidateFixtureBuilder()
        cls.prot, cls.lig, cls.edge = cls.builder.load("within_radius")

    def test_negative_candidates_not_positive_label(self) -> None:
        _raise_if_missing()
        result = _build_stepwise_candidates(
            protein_atoms=self.prot,
            ligand_atoms=self.lig,
            edge_candidates_artifact=self.edge,
            timestep_index=0,
            timestep_value=0.5,
        )
        for c in result.candidates:
            if c.ligand_atom_index != result.positive_label_ligand_atom_index:
                self.assertFalse(
                    c.is_positive_label,
                    f"candidate {c.ligand_atom_index} should not be "
                    f"positive label",
                )
                self.assertFalse(c.is_forced_positive)

    def test_exactly_one_positive_label(self) -> None:
        _raise_if_missing()
        for scenario in ("within_radius", "outside_radius",
                         "zero_natural_negatives"):
            with self.subTest(scenario=scenario):
                prot, lig, edge = self.builder.load(scenario)
                result = _build_stepwise_candidates(
                    protein_atoms=prot,
                    ligand_atoms=lig,
                    edge_candidates_artifact=edge,
                    timestep_index=0,
                    timestep_value=0.5,
                )
                positives = [
                    c for c in result.candidates if c.is_positive_label
                ]
                self.assertEqual(
                    len(positives), 1,
                    f"Expected exactly 1 positive label in {scenario}",
                )


class InvalidPositiveLabelTests(unittest.TestCase):
    """Static positive labels must match current ligand coordinates."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = StepwiseCandidateFixtureBuilder()
        cls.prot, cls.lig, cls.edge = cls.builder.load("within_radius")

    def test_missing_positive_ligand_atom_index_raises(self) -> None:
        _raise_if_missing()
        edge = dict(self.edge)
        positive_edge = dict(edge["positive_edge"])
        positive_edge["ligand_atom_index"] = 99
        edge["positive_edge"] = positive_edge

        with self.assertRaisesRegex(ValueError, "positive ligand_atom_index"):
            _build_stepwise_candidates(
                protein_atoms=self.prot,
                ligand_atoms=self.lig,
                edge_candidates_artifact=edge,
                timestep_index=0,
                timestep_value=0.5,
            )


if __name__ == "__main__":
    unittest.main()
