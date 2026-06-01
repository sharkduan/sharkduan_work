"""Tests for Task 23 mask and denominator computations.

Public API under test:
    covalent_design.training.masks.compute_mask_audit
    covalent_design.training.denominators.build_edge_denominators
    covalent_design.training.denominators.classify_timestep_bucket
    covalent_design.training.denominators.aggregate_denominator_strata
    covalent_design.training.denominators.DenominatorStratumEntry

Covers all Task 23 acceptance criteria.
"""

from __future__ import annotations

import sys
import unittest


# ---------------------------------------------------------------------------
# production imports
# ---------------------------------------------------------------------------

_compute_mask_audit = None
_build_edge_denominators = None
_classify_timestep_bucket = None
_aggregate_denominator_strata = None
_DenominatorStratumEntry = None
_IMPORT_ERRORS: list[str] = []

try:
    from covalent_design.training.masks import compute_mask_audit as _cma

    _compute_mask_audit = _cma
except ImportError as exc:
    _IMPORT_ERRORS.append(f"compute_mask_audit: {exc}")

try:
    from covalent_design.training.denominators import (
        DenominatorStratumEntry as _dse,
        aggregate_denominator_strata as _ads,
        build_edge_denominators as _bed,
        classify_timestep_bucket as _ctb,
    )

    _build_edge_denominators = _bed
    _classify_timestep_bucket = _ctb
    _aggregate_denominator_strata = _ads
    _DenominatorStratumEntry = _dse
except ImportError as exc:
    _IMPORT_ERRORS.append(f"denominators: {exc}")

from covalent_design.contracts.types import (
    DenominatorsStratum,
    EdgeDenominators,
    MaskAudit,
)
from covalent_design.contracts.errors import ContractError

from tests.fixtures.training.masks_denominators._builder import (
    MasksDenominatorsFixtureBuilder,
)


def _raise_if_missing() -> None:
    if not _IMPORT_ERRORS:
        return
    raise AssertionError(
        "Production code import failed. " + "; ".join(_IMPORT_ERRORS)
    )


# ===================================================================
# Acceptance Criterion: all 15 MaskAudit fields
# ===================================================================


class MaskAuditAllFieldsTests(unittest.TestCase):
    """Every MaskAudit field is populated and has the correct type."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = MasksDenominatorsFixtureBuilder()

    def test_all_15_mask_audit_fields_populated_natural_positive(self) -> None:
        _raise_if_missing()
        cs = self.builder.build_natural_positive_set()
        audit = _compute_mask_audit(cs)

        self.assertIsInstance(audit, MaskAudit)
        # field names and types
        self.assertIsInstance(audit.candidate_count, int)
        self.assertIsInstance(audit.natural_positive_count, int)
        self.assertIsInstance(audit.forced_positive_count, int)
        self.assertIsInstance(audit.natural_negative_count, int)
        self.assertIsInstance(audit.zero_negative_count, int)
        self.assertIsInstance(audit.masked_by_pending_smarts, int)
        self.assertIsInstance(audit.masked_by_pending_geometry, int)
        self.assertIsInstance(audit.masked_by_missing_chemical_state, int)
        self.assertIsInstance(audit.masked_by_q2_exclusion, int)
        self.assertIsInstance(audit.masked_by_forced_positive_exclusion, int)
        self.assertIsInstance(audit.edge_loss_eligible_count, int)
        self.assertIsInstance(audit.bond_type_loss_eligible_count, int)
        self.assertIsInstance(audit.geometry_loss_eligible_count, int)
        self.assertIsInstance(audit.message_passing_candidate_count, int)
        self.assertIsInstance(audit.gate_evaluated_count, int)


# ===================================================================
# Acceptance Criterion: TC == NP + FP + NN conservation
# ===================================================================


class MaskAuditConservationEquationTests(unittest.TestCase):
    """TC must equal NP + FP + NN for every valid scenario."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = MasksDenominatorsFixtureBuilder()

    def test_conservation_natural_positive(self) -> None:
        _raise_if_missing()
        cs = self.builder.build_natural_positive_set()
        audit = _compute_mask_audit(cs)

        self.assertEqual(
            audit.candidate_count,
            audit.natural_positive_count
            + audit.forced_positive_count
            + audit.natural_negative_count,
        )

    def test_conservation_forced_positive(self) -> None:
        _raise_if_missing()
        cs = self.builder.build_forced_positive_set()
        audit = _compute_mask_audit(cs)

        self.assertEqual(
            audit.candidate_count,
            audit.natural_positive_count
            + audit.forced_positive_count
            + audit.natural_negative_count,
        )

    def test_conservation_zero_natural_negatives(self) -> None:
        _raise_if_missing()
        cs = self.builder.build_zero_natural_negatives_set()
        audit = _compute_mask_audit(cs)

        self.assertEqual(
            audit.candidate_count,
            audit.natural_positive_count
            + audit.forced_positive_count
            + audit.natural_negative_count,
        )


# ===================================================================
# Acceptance Criterion: zero_negative_count
# ===================================================================


class MaskAuditZeroNegativeCountTests(unittest.TestCase):
    """zero_negative_count is 1 when NN == 0, 0 otherwise."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = MasksDenominatorsFixtureBuilder()

    def test_zero_negative_count_is_one_when_no_natural_negatives(self) -> None:
        _raise_if_missing()
        cs = self.builder.build_zero_natural_negatives_set()
        audit = _compute_mask_audit(cs)

        self.assertEqual(audit.natural_negative_count, 0)
        self.assertEqual(audit.zero_negative_count, 1)

    def test_zero_negative_count_is_zero_when_negatives_exist(self) -> None:
        _raise_if_missing()
        cs = self.builder.build_natural_positive_set()
        audit = _compute_mask_audit(cs)

        self.assertGreater(audit.natural_negative_count, 0)
        self.assertEqual(audit.zero_negative_count, 0)


# ===================================================================
# Acceptance Criterion: natural positive (NP counts)
# ===================================================================


class MaskAuditNaturalPositiveTests(unittest.TestCase):
    """Natural positive: NP = count(is_positive_label and not is_forced_positive)."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = MasksDenominatorsFixtureBuilder()

    def test_natural_positive_count_matches_candidates(self) -> None:
        _raise_if_missing()
        cs = self.builder.build_natural_positive_set()
        audit = _compute_mask_audit(cs)

        self.assertEqual(audit.natural_positive_count, 1)
        self.assertEqual(audit.candidate_count, 3)

    def test_default_mask_reason_counts_are_zero(self) -> None:
        _raise_if_missing()
        cs = self.builder.build_natural_positive_set()
        audit = _compute_mask_audit(cs)

        self.assertEqual(audit.masked_by_pending_smarts, 0)
        self.assertEqual(audit.masked_by_pending_geometry, 0)
        self.assertEqual(audit.masked_by_missing_chemical_state, 0)
        self.assertEqual(audit.masked_by_q2_exclusion, 0)
        self.assertEqual(audit.masked_by_forced_positive_exclusion, 0)

    def test_default_eligible_counts(self) -> None:
        _raise_if_missing()
        cs = self.builder.build_natural_positive_set()
        audit = _compute_mask_audit(cs)

        self.assertEqual(audit.edge_loss_eligible_count, 3)
        self.assertEqual(audit.bond_type_loss_eligible_count, 1)
        self.assertEqual(audit.geometry_loss_eligible_count, 1)
        self.assertEqual(audit.message_passing_candidate_count, 3)
        self.assertEqual(audit.gate_evaluated_count, 3)


# ===================================================================
# Acceptance Criterion: forced positive
# ===================================================================


class MaskAuditForcedPositiveTests(unittest.TestCase):
    """Forced positive: FP = count(is_forced_positive)."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = MasksDenominatorsFixtureBuilder()

    def test_forced_positive_count_and_masked_by_forced_positive_exclusion(self) -> None:
        _raise_if_missing()
        cs = self.builder.build_forced_positive_set()
        audit = _compute_mask_audit(cs)

        self.assertEqual(audit.forced_positive_count, 1)
        self.assertEqual(audit.masked_by_forced_positive_exclusion, 1)
        self.assertEqual(audit.natural_positive_count, 0)

    def test_forced_positive_only_in_edge_and_gate(self) -> None:
        _raise_if_missing()
        cs = self.builder.build_forced_positive_set()
        audit = _compute_mask_audit(cs)

        # edge loss includes FP (eligible = TC)
        self.assertEqual(audit.edge_loss_eligible_count, 3)
        # bond type only for natural positives (NP=0)
        self.assertEqual(audit.bond_type_loss_eligible_count, 0)
        # geometry only for natural positives (NP=0)
        self.assertEqual(audit.geometry_loss_eligible_count, 0)
        # message passing excludes FP (NP+NN=2)
        self.assertEqual(audit.message_passing_candidate_count, 2)
        # gate includes FP (TC=3)
        self.assertEqual(audit.gate_evaluated_count, 3)


# ===================================================================
# Acceptance Criterion: zero natural negatives
# ===================================================================


class MaskAuditZeroNaturalNegativesTests(unittest.TestCase):
    """NN=0: zero_negative_count=1, empty_radius_window=True is valid."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = MasksDenominatorsFixtureBuilder()

    def test_zero_natural_negatives_scenario(self) -> None:
        _raise_if_missing()
        cs = self.builder.build_zero_natural_negatives_set()
        audit = _compute_mask_audit(cs)

        self.assertEqual(audit.candidate_count, 1)
        self.assertEqual(audit.natural_positive_count, 1)
        self.assertEqual(audit.forced_positive_count, 0)
        self.assertEqual(audit.natural_negative_count, 0)
        self.assertEqual(audit.zero_negative_count, 1)

    def test_message_passing_is_np_only_when_nn_zero(self) -> None:
        _raise_if_missing()
        cs = self.builder.build_zero_natural_negatives_set()
        audit = _compute_mask_audit(cs)

        self.assertEqual(audit.message_passing_candidate_count, 1)
        self.assertEqual(audit.bond_type_loss_eligible_count, 1)
        self.assertEqual(audit.geometry_loss_eligible_count, 1)
        self.assertEqual(audit.gate_evaluated_count, 1)

    def test_empty_radius_window_true_does_not_error(self) -> None:
        _raise_if_missing()
        cs = self.builder.build_zero_natural_negatives_set()
        self.assertTrue(cs.empty_radius_window)

        audit = _compute_mask_audit(cs)
        self.assertEqual(audit.natural_negative_count, 0)


# ===================================================================
# Acceptance Criterion: pending SMARTS masks bond targets
# ===================================================================


class MaskAuditPendingSmartsTests(unittest.TestCase):
    """pending_smarts=True masks bond type targets only."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = MasksDenominatorsFixtureBuilder()

    def test_pending_smarts_masks_bond_type(self) -> None:
        _raise_if_missing()
        cs = self.builder.build_natural_positive_set()
        audit = _compute_mask_audit(cs, pending_smarts=True)

        self.assertEqual(audit.masked_by_pending_smarts, 1)
        self.assertEqual(audit.bond_type_loss_eligible_count, 0)

    def test_pending_smarts_does_not_mask_other_targets(self) -> None:
        _raise_if_missing()
        cs = self.builder.build_natural_positive_set()
        audit = _compute_mask_audit(cs, pending_smarts=True)

        self.assertEqual(audit.edge_loss_eligible_count, 3)
        self.assertEqual(audit.geometry_loss_eligible_count, 1)
        self.assertEqual(audit.message_passing_candidate_count, 3)
        self.assertEqual(audit.gate_evaluated_count, 3)

    def test_pending_smarts_masked_by_count_correct(self) -> None:
        _raise_if_missing()
        cs = self.builder.build_natural_positive_set()
        audit = _compute_mask_audit(cs, pending_smarts=True)

        self.assertEqual(audit.masked_by_pending_smarts, audit.natural_positive_count)


# ===================================================================
# Acceptance Criterion: pending geometry masks geometry targets
# ===================================================================


class MaskAuditPendingGeometryTests(unittest.TestCase):
    """pending_geometry=True masks geometry targets only."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = MasksDenominatorsFixtureBuilder()

    def test_pending_geometry_masks_geometry(self) -> None:
        _raise_if_missing()
        cs = self.builder.build_natural_positive_set()
        audit = _compute_mask_audit(cs, pending_geometry=True)

        self.assertEqual(audit.masked_by_pending_geometry, 1)
        self.assertEqual(audit.geometry_loss_eligible_count, 0)

    def test_pending_geometry_does_not_mask_other_targets(self) -> None:
        _raise_if_missing()
        cs = self.builder.build_natural_positive_set()
        audit = _compute_mask_audit(cs, pending_geometry=True)

        self.assertEqual(audit.edge_loss_eligible_count, 3)
        self.assertEqual(audit.bond_type_loss_eligible_count, 1)
        self.assertEqual(audit.message_passing_candidate_count, 3)
        self.assertEqual(audit.gate_evaluated_count, 3)

    def test_pending_geometry_masked_by_count_correct(self) -> None:
        _raise_if_missing()
        cs = self.builder.build_natural_positive_set()
        audit = _compute_mask_audit(cs, pending_geometry=True)

        self.assertEqual(
            audit.masked_by_pending_geometry, audit.natural_positive_count
        )


# ===================================================================
# Acceptance Criterion: both pending
# ===================================================================


class MaskAuditBothPendingTests(unittest.TestCase):
    """Both pending_smarts and pending_geometry active simultaneously."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = MasksDenominatorsFixtureBuilder()

    def test_both_pending_mask_both_targets(self) -> None:
        _raise_if_missing()
        cs = self.builder.build_natural_positive_set()
        audit = _compute_mask_audit(cs, pending_smarts=True, pending_geometry=True)

        self.assertEqual(audit.masked_by_pending_smarts, 1)
        self.assertEqual(audit.masked_by_pending_geometry, 1)
        self.assertEqual(audit.bond_type_loss_eligible_count, 0)
        self.assertEqual(audit.geometry_loss_eligible_count, 0)

    def test_both_pending_still_trains_edge_and_gate(self) -> None:
        _raise_if_missing()
        cs = self.builder.build_natural_positive_set()
        audit = _compute_mask_audit(cs, pending_smarts=True, pending_geometry=True)

        self.assertEqual(audit.edge_loss_eligible_count, 3)
        self.assertEqual(audit.message_passing_candidate_count, 3)
        self.assertEqual(audit.gate_evaluated_count, 3)


# ===================================================================
# Acceptance Criterion: missing required chemical state
# ===================================================================


class MaskAuditMissingChemicalStateTests(unittest.TestCase):
    """missing_required_chemical_state=True masks geometry targets."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = MasksDenominatorsFixtureBuilder()

    def test_missing_chemical_state_masks_geometry(self) -> None:
        _raise_if_missing()
        cs = self.builder.build_natural_positive_set()
        audit = _compute_mask_audit(cs, missing_required_chemical_state=True)

        self.assertEqual(audit.masked_by_missing_chemical_state, 1)
        self.assertEqual(audit.geometry_loss_eligible_count, 0)

    def test_missing_chemical_state_does_not_mask_bond_type(self) -> None:
        _raise_if_missing()
        cs = self.builder.build_natural_positive_set()
        audit = _compute_mask_audit(cs, missing_required_chemical_state=True)

        self.assertEqual(audit.bond_type_loss_eligible_count, 1)

    def test_missing_chemical_state_does_not_mask_edge(self) -> None:
        _raise_if_missing()
        cs = self.builder.build_natural_positive_set()
        audit = _compute_mask_audit(cs, missing_required_chemical_state=True)

        self.assertEqual(audit.edge_loss_eligible_count, 3)

    def test_pending_geometry_and_missing_state_both_mask_geometry(self) -> None:
        _raise_if_missing()
        cs = self.builder.build_natural_positive_set()
        audit = _compute_mask_audit(
            cs,
            pending_geometry=True,
            missing_required_chemical_state=True,
        )

        self.assertEqual(audit.masked_by_pending_geometry, 1)
        self.assertEqual(audit.masked_by_missing_chemical_state, 1)
        self.assertEqual(audit.geometry_loss_eligible_count, 0)


# ===================================================================
# Acceptance Criterion: Q2 default keep
# ===================================================================


class MaskAuditQ2DefaultKeepTests(unittest.TestCase):
    """Q2 records are kept by default (exclude_q2=False)."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = MasksDenominatorsFixtureBuilder()

    def test_q2_default_keep_does_not_mask(self) -> None:
        _raise_if_missing()
        cs = self.builder.build_natural_positive_set()
        audit = _compute_mask_audit(cs, quality_tier="Q2")

        self.assertEqual(audit.masked_by_q2_exclusion, 0)
        self.assertGreater(audit.edge_loss_eligible_count, 0)
        self.assertGreater(audit.bond_type_loss_eligible_count, 0)
        self.assertGreater(audit.geometry_loss_eligible_count, 0)
        self.assertGreater(audit.message_passing_candidate_count, 0)
        self.assertGreater(audit.gate_evaluated_count, 0)

    def test_q1_default_keep_does_not_mask(self) -> None:
        _raise_if_missing()
        cs = self.builder.build_natural_positive_set()
        audit = _compute_mask_audit(cs, quality_tier="Q1")

        self.assertEqual(audit.masked_by_q2_exclusion, 0)


# ===================================================================
# Acceptance Criterion: exclude_q2=True
# ===================================================================


class MaskAuditQ2ExcludeTests(unittest.TestCase):
    """exclude_q2=True with quality_tier='Q2' zeroes all eligible counts."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = MasksDenominatorsFixtureBuilder()

    def test_q2_excluded_masks_all_candidates(self) -> None:
        _raise_if_missing()
        cs = self.builder.build_natural_positive_set()
        audit = _compute_mask_audit(cs, quality_tier="Q2", exclude_q2=True)

        self.assertEqual(audit.masked_by_q2_exclusion, audit.candidate_count)

    def test_q2_excluded_all_eligible_counts_zero(self) -> None:
        _raise_if_missing()
        cs = self.builder.build_natural_positive_set()
        audit = _compute_mask_audit(cs, quality_tier="Q2", exclude_q2=True)

        self.assertEqual(audit.edge_loss_eligible_count, 0)
        self.assertEqual(audit.bond_type_loss_eligible_count, 0)
        self.assertEqual(audit.geometry_loss_eligible_count, 0)
        self.assertEqual(audit.message_passing_candidate_count, 0)
        self.assertEqual(audit.gate_evaluated_count, 0)

    def test_exclude_q2_does_not_affect_q1(self) -> None:
        _raise_if_missing()
        cs = self.builder.build_natural_positive_set()
        audit = _compute_mask_audit(cs, quality_tier="Q1", exclude_q2=True)

        self.assertEqual(audit.masked_by_q2_exclusion, 0)
        self.assertGreater(audit.edge_loss_eligible_count, 0)


# ===================================================================
# Acceptance Criterion: forced positive participation table
# ===================================================================


class ForcedPositiveParticipationTableTests(unittest.TestCase):
    """FP participates in edge existence and gate evaluation only."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = MasksDenominatorsFixtureBuilder()

    def test_fp_in_edge_eligible(self) -> None:
        _raise_if_missing()
        cs = self.builder.build_forced_positive_set()
        audit = _compute_mask_audit(cs)

        # edge_loss_eligible_count = TC = 3 (includes FP)
        self.assertEqual(audit.edge_loss_eligible_count, 3)

    def test_fp_not_in_bond_type_eligible(self) -> None:
        _raise_if_missing()
        cs = self.builder.build_forced_positive_set()
        audit = _compute_mask_audit(cs)

        # NP = 0, so bond_type_loss_eligible_count = 0
        self.assertEqual(audit.bond_type_loss_eligible_count, 0)

    def test_fp_not_in_geometry_eligible(self) -> None:
        _raise_if_missing()
        cs = self.builder.build_forced_positive_set()
        audit = _compute_mask_audit(cs)

        self.assertEqual(audit.geometry_loss_eligible_count, 0)

    def test_fp_not_in_message_passing(self) -> None:
        _raise_if_missing()
        cs = self.builder.build_forced_positive_set()
        audit = _compute_mask_audit(cs)

        # NP+NN = 2 (excludes FP)
        self.assertEqual(audit.message_passing_candidate_count, 2)

    def test_fp_in_gate_evaluated(self) -> None:
        _raise_if_missing()
        cs = self.builder.build_forced_positive_set()
        audit = _compute_mask_audit(cs)

        # gate = TC = 3 (includes FP)
        self.assertEqual(audit.gate_evaluated_count, 3)

    def test_masked_by_forced_positive_exclusion_matches_fp_count(self) -> None:
        _raise_if_missing()
        cs = self.builder.build_forced_positive_set()
        audit = _compute_mask_audit(cs)

        self.assertEqual(
            audit.masked_by_forced_positive_exclusion,
            audit.forced_positive_count,
        )


# ===================================================================
# Acceptance Criterion: natural negatives only edge/message passing
# ===================================================================


class NaturalNegativesParticipationTests(unittest.TestCase):
    """NN participate in edge loss and message passing only; no bond or geometry."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = MasksDenominatorsFixtureBuilder()

    def test_natural_negatives_are_in_message_passing(self) -> None:
        _raise_if_missing()
        cs = self.builder.build_natural_positive_set()
        audit = _compute_mask_audit(cs)

        # NP=1, NN=2 → message_passing = 3
        self.assertEqual(
            audit.message_passing_candidate_count,
            audit.natural_positive_count + audit.natural_negative_count,
        )

    def test_natural_negatives_do_not_inflate_bond_type_eligible(self) -> None:
        _raise_if_missing()
        cs = self.builder.build_natural_positive_set()
        audit = _compute_mask_audit(cs)

        # bond_type_loss eligible = NP only (1), not NP+NN (3)
        self.assertEqual(audit.bond_type_loss_eligible_count, 1)
        self.assertNotEqual(
            audit.bond_type_loss_eligible_count,
            audit.message_passing_candidate_count,
        )

    def test_natural_negatives_do_not_inflate_geometry_eligible(self) -> None:
        _raise_if_missing()
        cs = self.builder.build_natural_positive_set()
        audit = _compute_mask_audit(cs)

        self.assertEqual(audit.geometry_loss_eligible_count, 1)
        self.assertNotEqual(
            audit.geometry_loss_eligible_count,
            audit.message_passing_candidate_count,
        )

    def test_natural_negatives_contribute_to_edge_loss(self) -> None:
        _raise_if_missing()
        cs = self.builder.build_natural_positive_set()
        audit = _compute_mask_audit(cs)

        # edge includes all candidates (TC=3)
        self.assertEqual(audit.edge_loss_eligible_count, 3)

    def test_natural_negatives_contribute_to_gate(self) -> None:
        _raise_if_missing()
        cs = self.builder.build_natural_positive_set()
        audit = _compute_mask_audit(cs)

        self.assertEqual(audit.gate_evaluated_count, 3)


# ===================================================================
# Acceptance Criterion: all 10 EdgeDenominators fields
# ===================================================================


class EdgeDenominatorsFieldTests(unittest.TestCase):
    """All 10 EdgeDenominators fields are built correctly from MaskAudit."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = MasksDenominatorsFixtureBuilder()

    def test_all_10_edge_denominators_fields_populated(self) -> None:
        _raise_if_missing()
        cs = self.builder.build_natural_positive_set()
        audit = _compute_mask_audit(cs)
        denoms = _build_edge_denominators(audit)

        self.assertIsInstance(denoms, EdgeDenominators)
        self.assertIsInstance(denoms.candidate_count, int)
        self.assertIsInstance(denoms.natural_candidate_count, int)
        self.assertIsInstance(denoms.forced_positive_count, int)
        self.assertIsInstance(denoms.eligible_edge_count, int)
        self.assertIsInstance(denoms.masked_candidate_count, int)
        self.assertIsInstance(denoms.edge_loss_denominator, int)
        self.assertIsInstance(denoms.bond_type_loss_denominator, int)
        self.assertIsInstance(denoms.geometry_loss_denominator, int)
        self.assertIsInstance(denoms.message_passing_candidate_count, int)
        self.assertIsInstance(denoms.gate_evaluated_count, int)

    def test_candidate_count_projection(self) -> None:
        _raise_if_missing()
        cs = self.builder.build_natural_positive_set()
        audit = _compute_mask_audit(cs)
        denoms = _build_edge_denominators(audit)

        self.assertEqual(denoms.candidate_count, audit.candidate_count)

    def test_natural_candidate_count_is_np_plus_nn(self) -> None:
        _raise_if_missing()
        cs = self.builder.build_natural_positive_set()
        audit = _compute_mask_audit(cs)
        denoms = _build_edge_denominators(audit)

        self.assertEqual(
            denoms.natural_candidate_count,
            audit.natural_positive_count + audit.natural_negative_count,
        )

    def test_forced_positive_count_projection(self) -> None:
        _raise_if_missing()
        cs = self.builder.build_forced_positive_set()
        audit = _compute_mask_audit(cs)
        denoms = _build_edge_denominators(audit)

        self.assertEqual(denoms.forced_positive_count, audit.forced_positive_count)

    def test_eligible_edge_count_projection(self) -> None:
        _raise_if_missing()
        cs = self.builder.build_natural_positive_set()
        audit = _compute_mask_audit(cs)
        denoms = _build_edge_denominators(audit)

        self.assertEqual(denoms.eligible_edge_count, audit.edge_loss_eligible_count)

    def test_masked_candidate_count_is_tc_minus_eligible_edge(self) -> None:
        _raise_if_missing()
        cs = self.builder.build_natural_positive_set()
        audit = _compute_mask_audit(cs, exclude_q2=False)
        denoms = _build_edge_denominators(audit)

        self.assertEqual(
            denoms.masked_candidate_count,
            audit.candidate_count - audit.edge_loss_eligible_count,
        )

    def test_edge_loss_denominator_matches_eligible_edge(self) -> None:
        _raise_if_missing()
        cs = self.builder.build_natural_positive_set()
        audit = _compute_mask_audit(cs)
        denoms = _build_edge_denominators(audit)

        self.assertEqual(
            denoms.edge_loss_denominator, audit.edge_loss_eligible_count
        )

    def test_bond_type_loss_denominator_projection(self) -> None:
        _raise_if_missing()
        cs = self.builder.build_natural_positive_set()
        audit = _compute_mask_audit(cs)
        denoms = _build_edge_denominators(audit)

        self.assertEqual(
            denoms.bond_type_loss_denominator,
            audit.bond_type_loss_eligible_count,
        )

    def test_geometry_loss_denominator_projection(self) -> None:
        _raise_if_missing()
        cs = self.builder.build_natural_positive_set()
        audit = _compute_mask_audit(cs)
        denoms = _build_edge_denominators(audit)

        self.assertEqual(
            denoms.geometry_loss_denominator,
            audit.geometry_loss_eligible_count,
        )

    def test_message_passing_projection(self) -> None:
        _raise_if_missing()
        cs = self.builder.build_natural_positive_set()
        audit = _compute_mask_audit(cs)
        denoms = _build_edge_denominators(audit)

        self.assertEqual(
            denoms.message_passing_candidate_count,
            audit.message_passing_candidate_count,
        )

    def test_gate_evaluated_projection(self) -> None:
        _raise_if_missing()
        cs = self.builder.build_natural_positive_set()
        audit = _compute_mask_audit(cs)
        denoms = _build_edge_denominators(audit)

        self.assertEqual(
            denoms.gate_evaluated_count, audit.gate_evaluated_count
        )


# ===================================================================
# build_edge_denominators Q2 exclusion
# ===================================================================


class BuildEdgeDenominatorsQ2ExclusionTests(unittest.TestCase):
    """build_edge_denominators with Q2-excluded mask audit."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = MasksDenominatorsFixtureBuilder()

    def test_q2_excluded_produces_all_zero_denominators(self) -> None:
        _raise_if_missing()
        cs = self.builder.build_natural_positive_set()
        audit = _compute_mask_audit(cs, quality_tier="Q2", exclude_q2=True)
        denoms = _build_edge_denominators(audit)

        self.assertEqual(denoms.eligible_edge_count, 0)
        self.assertEqual(denoms.masked_candidate_count, audit.candidate_count)
        self.assertEqual(denoms.edge_loss_denominator, 0)
        self.assertEqual(denoms.bond_type_loss_denominator, 0)
        self.assertEqual(denoms.geometry_loss_denominator, 0)
        self.assertEqual(denoms.message_passing_candidate_count, 0)
        self.assertEqual(denoms.gate_evaluated_count, 0)

    def test_q2_excluded_natural_and_forced_counts_preserved(self) -> None:
        _raise_if_missing()
        cs = self.builder.build_natural_positive_set()
        audit = _compute_mask_audit(cs, quality_tier="Q2", exclude_q2=True)
        denoms = _build_edge_denominators(audit)

        # structural counts preserved even when everything is Q2-excluded
        self.assertEqual(denoms.candidate_count, 3)
        self.assertEqual(denoms.natural_candidate_count, 3)
        self.assertEqual(denoms.forced_positive_count, 0)


# ===================================================================
# build_edge_denominators with pending masks
# ===================================================================


class BuildEdgeDenominatorsMaskedTests(unittest.TestCase):
    """build_edge_denominators with various mask flags active."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = MasksDenominatorsFixtureBuilder()

    def test_pending_smarts_masks_bond_type_denominator(self) -> None:
        _raise_if_missing()
        cs = self.builder.build_natural_positive_set()
        audit = _compute_mask_audit(cs, pending_smarts=True)
        denoms = _build_edge_denominators(audit)

        self.assertEqual(denoms.bond_type_loss_denominator, 0)
        self.assertGreater(denoms.edge_loss_denominator, 0)

    def test_pending_geometry_masks_geometry_denominator(self) -> None:
        _raise_if_missing()
        cs = self.builder.build_natural_positive_set()
        audit = _compute_mask_audit(cs, pending_geometry=True)
        denoms = _build_edge_denominators(audit)

        self.assertEqual(denoms.geometry_loss_denominator, 0)
        self.assertGreater(denoms.edge_loss_denominator, 0)

    def test_both_pending_masks_bond_and_geometry_denominators(self) -> None:
        _raise_if_missing()
        cs = self.builder.build_natural_positive_set()
        audit = _compute_mask_audit(
            cs, pending_smarts=True, pending_geometry=True
        )
        denoms = _build_edge_denominators(audit)

        self.assertEqual(denoms.bond_type_loss_denominator, 0)
        self.assertEqual(denoms.geometry_loss_denominator, 0)
        self.assertGreater(denoms.edge_loss_denominator, 0)


# ===================================================================
# build_edge_denominators forced positive
# ===================================================================


class BuildEdgeDenominatorsForcedPositiveTests(unittest.TestCase):
    """build_edge_denominators with forced positives."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = MasksDenominatorsFixtureBuilder()

    def test_forced_positive_edge_only(self) -> None:
        _raise_if_missing()
        cs = self.builder.build_forced_positive_set()
        audit = _compute_mask_audit(cs)
        denoms = _build_edge_denominators(audit)

        self.assertEqual(denoms.candidate_count, 3)
        self.assertEqual(denoms.forced_positive_count, 1)
        self.assertEqual(denoms.natural_candidate_count, 2)
        self.assertEqual(denoms.edge_loss_denominator, 3)
        self.assertEqual(denoms.bond_type_loss_denominator, 0)
        self.assertEqual(denoms.geometry_loss_denominator, 0)
        self.assertEqual(denoms.message_passing_candidate_count, 2)
        self.assertEqual(denoms.gate_evaluated_count, 3)

    def test_forced_positive_denominator_conservation(self) -> None:
        _raise_if_missing()
        cs = self.builder.build_forced_positive_set()
        audit = _compute_mask_audit(cs)
        denoms = _build_edge_denominators(audit)

        self.assertEqual(
            denoms.candidate_count,
            denoms.natural_candidate_count + denoms.forced_positive_count,
        )


class BuildEdgeDenominatorsValidationTests(unittest.TestCase):
    """Invalid projections must fail instead of returning a bad contract."""

    def test_negative_edge_eligibility_raises_value_error(self) -> None:
        _raise_if_missing()
        audit = MaskAudit(
            candidate_count=0,
            natural_positive_count=0,
            forced_positive_count=0,
            natural_negative_count=0,
            zero_negative_count=1,
            masked_by_pending_smarts=0,
            masked_by_pending_geometry=0,
            masked_by_missing_chemical_state=0,
            masked_by_q2_exclusion=0,
            masked_by_forced_positive_exclusion=0,
            edge_loss_eligible_count=-1,
            bond_type_loss_eligible_count=0,
            geometry_loss_eligible_count=0,
            message_passing_candidate_count=0,
            gate_evaluated_count=0,
        )
        with self.assertRaises(ContractError):
            _build_edge_denominators(audit)


# ===================================================================
# Acceptance Criterion: timestep bucket boundaries
# ===================================================================


class TimestepBucketBoundaryTests(unittest.TestCase):
    """classify_timestep_bucket: early [0.8, 1.0], mid [0.3, 0.8), late [0.0, 0.3)."""

    @classmethod
    def setUpClass(cls) -> None:
        pass

    def test_early_lower_boundary_inclusive(self) -> None:
        _raise_if_missing()
        self.assertEqual(_classify_timestep_bucket(0.8), "early")

    def test_early_upper_boundary_inclusive(self) -> None:
        _raise_if_missing()
        self.assertEqual(_classify_timestep_bucket(1.0), "early")

    def test_early_mid_range(self) -> None:
        _raise_if_missing()
        self.assertEqual(_classify_timestep_bucket(0.9), "early")

    def test_mid_lower_boundary_inclusive(self) -> None:
        _raise_if_missing()
        self.assertEqual(_classify_timestep_bucket(0.3), "mid")

    def test_mid_just_below_early(self) -> None:
        _raise_if_missing()
        self.assertEqual(_classify_timestep_bucket(0.79), "mid")

    def test_mid_mid_range(self) -> None:
        _raise_if_missing()
        self.assertEqual(_classify_timestep_bucket(0.5), "mid")

    def test_late_just_below_mid(self) -> None:
        _raise_if_missing()
        self.assertEqual(_classify_timestep_bucket(0.29), "late")

    def test_late_lower_boundary_inclusive(self) -> None:
        _raise_if_missing()
        self.assertEqual(_classify_timestep_bucket(0.0), "late")

    def test_late_mid_range(self) -> None:
        _raise_if_missing()
        self.assertEqual(_classify_timestep_bucket(0.15), "late")


# ===================================================================
# Acceptance Criterion: timestep bucket out-of-range rejection
# ===================================================================


class TimestepBucketOutOfRangeTests(unittest.TestCase):
    """Values outside [0.0, 1.0] raise ValueError."""

    def test_negative_value_raises_value_error(self) -> None:
        _raise_if_missing()
        with self.assertRaises(ValueError):
            _classify_timestep_bucket(-0.01)

    def test_above_one_raises_value_error(self) -> None:
        _raise_if_missing()
        with self.assertRaises(ValueError):
            _classify_timestep_bucket(1.01)

    def test_negative_large_raises_value_error(self) -> None:
        _raise_if_missing()
        with self.assertRaises(ValueError):
            _classify_timestep_bucket(-5.0)

    def test_above_one_large_raises_value_error(self) -> None:
        _raise_if_missing()
        with self.assertRaises(ValueError):
            _classify_timestep_bucket(10.0)

    def test_nan_raises_value_error(self) -> None:
        _raise_if_missing()
        with self.assertRaises(ValueError):
            _classify_timestep_bucket(float("nan"))


# ===================================================================
# Acceptance Criterion: deterministic strata ordering
# ===================================================================


class StrataOrderingAndConservationTests(unittest.TestCase):
    """aggregate_denominator_strata groups and sorts deterministically."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = MasksDenominatorsFixtureBuilder()

    def _make_entry(
        self,
        family: str,
        timestep_value: float,
        audit: MaskAudit,
    ) -> object:
        _raise_if_missing()
        return _DenominatorStratumEntry(
            residue_reaction_family=family,
            timestep_value=timestep_value,
            mask_audit=audit,
        )

    def test_strata_sorted_by_family_alphabetically(self) -> None:
        _raise_if_missing()
        cs = self.builder.build_natural_positive_set(timestep_value=0.9)
        audit = _compute_mask_audit(cs)

        entries = [
            self._make_entry("cysteine_thiol", 0.9, audit),
            self._make_entry("arginine_urea", 0.9, audit),
            self._make_entry("lysine_imine", 0.9, audit),
        ]
        strata = _aggregate_denominator_strata(entries)

        families = [s.residue_reaction_family for s in strata]
        self.assertEqual(
            families,
            ["arginine_urea", "cysteine_thiol", "lysine_imine"],
        )

    def test_strata_sorted_by_bucket_within_family(self) -> None:
        _raise_if_missing()
        audit_early = _compute_mask_audit(
            self.builder.build_natural_positive_set(timestep_value=0.9)
        )
        audit_mid = _compute_mask_audit(
            self.builder.build_natural_positive_set(timestep_value=0.5)
        )
        audit_late = _compute_mask_audit(
            self.builder.build_natural_positive_set(timestep_value=0.1)
        )

        entries = [
            self._make_entry("cysteine_thiol", 0.5, audit_mid),
            self._make_entry("cysteine_thiol", 0.1, audit_late),
            self._make_entry("cysteine_thiol", 0.9, audit_early),
        ]
        strata = _aggregate_denominator_strata(entries)

        buckets = [(s.residue_reaction_family, s.timestep_bucket) for s in strata]
        self.assertEqual(
            buckets,
            [
                ("cysteine_thiol", "early"),
                ("cysteine_thiol", "mid"),
                ("cysteine_thiol", "late"),
            ],
        )

    def test_strata_multi_family_multi_bucket(self) -> None:
        _raise_if_missing()

        entries = [
            self._make_entry(
                "serine_ester", 0.9,
                _compute_mask_audit(
                    self.builder.build_natural_positive_set(timestep_value=0.9)
                ),
            ),
            self._make_entry(
                "cysteine_thiol", 0.5,
                _compute_mask_audit(
                    self.builder.build_natural_positive_set(timestep_value=0.5)
                ),
            ),
            self._make_entry(
                "cysteine_thiol", 0.1,
                _compute_mask_audit(
                    self.builder.build_natural_positive_set(timestep_value=0.1)
                ),
            ),
            self._make_entry(
                "serine_ester", 0.2,
                _compute_mask_audit(
                    self.builder.build_natural_positive_set(timestep_value=0.2)
                ),
            ),
        ]
        strata = _aggregate_denominator_strata(entries)

        result = [(s.residue_reaction_family, s.timestep_bucket) for s in strata]
        self.assertEqual(
            result,
            [
                ("cysteine_thiol", "mid"),
                ("cysteine_thiol", "late"),
                ("serine_ester", "early"),
                ("serine_ester", "late"),
            ],
        )

    def test_aggregation_conserves_total_counts(self) -> None:
        _raise_if_missing()
        audit1 = _compute_mask_audit(
            self.builder.build_natural_positive_set(timestep_value=0.9)
        )
        audit2 = _compute_mask_audit(
            self.builder.build_natural_positive_set(timestep_value=0.5)
        )

        entries = [
            self._make_entry("cysteine_thiol", 0.9, audit1),
            self._make_entry("cysteine_thiol", 0.5, audit2),
        ]
        strata = _aggregate_denominator_strata(entries)

        total_candidates = sum(s.denominators.candidate_count for s in strata)
        self.assertEqual(
            total_candidates,
            audit1.candidate_count + audit2.candidate_count,
        )

    def test_stratum_contains_both_denominators_and_mask_audit(self) -> None:
        _raise_if_missing()
        cs = self.builder.build_natural_positive_set(timestep_value=0.9)
        audit = _compute_mask_audit(cs)

        entries = [self._make_entry("cysteine_thiol", 0.9, audit)]
        strata = _aggregate_denominator_strata(entries)

        self.assertEqual(len(strata), 1)
        self.assertIsInstance(strata[0], DenominatorsStratum)
        self.assertEqual(strata[0].residue_reaction_family, "cysteine_thiol")
        self.assertEqual(strata[0].timestep_bucket, "early")
        self.assertIsInstance(strata[0].denominators, EdgeDenominators)
        self.assertIsInstance(strata[0].mask_audit, MaskAudit)

    def test_identical_entry_produces_single_stratum(self) -> None:
        _raise_if_missing()
        cs = self.builder.build_natural_positive_set(timestep_value=0.9)
        audit = _compute_mask_audit(cs)

        entries = [
            self._make_entry("cysteine_thiol", 0.9, audit),
            self._make_entry("cysteine_thiol", 0.85, audit),
        ]
        strata = _aggregate_denominator_strata(entries)

        self.assertEqual(len(strata), 1)
        self.assertEqual(strata[0].timestep_bucket, "early")
        # aggregated candidate_count = 3 + 3 = 6
        self.assertEqual(strata[0].denominators.candidate_count, 6)

    def test_aggregated_mask_audit_sums_all_fields(self) -> None:
        _raise_if_missing()
        audit1 = _compute_mask_audit(
            self.builder.build_natural_positive_set(timestep_value=0.9)
        )
        audit2 = _compute_mask_audit(
            self.builder.build_natural_positive_set(timestep_value=0.85)
        )

        entries = [
            self._make_entry("cysteine_thiol", 0.9, audit1),
            self._make_entry("cysteine_thiol", 0.85, audit2),
        ]
        strata = _aggregate_denominator_strata(entries)

        aggregated = strata[0].mask_audit
        self.assertEqual(
            aggregated.candidate_count,
            audit1.candidate_count + audit2.candidate_count,
        )
        self.assertEqual(
            aggregated.natural_positive_count,
            audit1.natural_positive_count + audit2.natural_positive_count,
        )


# ===================================================================
# Acceptance Criterion: conservation equations hold under aggregation
# ===================================================================


class StrataConservationEquationTests(unittest.TestCase):
    """For aggregated strata: TC == NP + FP + NN holds."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = MasksDenominatorsFixtureBuilder()

    def _make_entry(self, family: str, timestep_value: float, audit: MaskAudit) -> object:
        _raise_if_missing()
        return _DenominatorStratumEntry(
            residue_reaction_family=family,
            timestep_value=timestep_value,
            mask_audit=audit,
        )

    def test_conservation_holds_in_every_stratum(self) -> None:
        _raise_if_missing()
        entries = []
        for tv in (0.9, 0.85, 0.5, 0.45, 0.1):
            cs = self.builder.build_natural_positive_set(timestep_value=tv)
            entries.append(
                self._make_entry("cysteine_thiol", tv, _compute_mask_audit(cs))
            )

        strata = _aggregate_denominator_strata(entries)

        for stratum in strata:
            m = stratum.mask_audit
            self.assertEqual(
                m.candidate_count,
                m.natural_positive_count
                + m.forced_positive_count
                + m.natural_negative_count,
                f"conservation failed in {stratum.timestep_bucket}",
            )

    def test_conservation_holds_across_multiple_families(self) -> None:
        _raise_if_missing()
        entries = []
        for family in ("cysteine_thiol", "serine_ester", "lysine_imine"):
            for tv in (0.9, 0.5, 0.1):
                cs = self.builder.build_natural_positive_set(timestep_value=tv)
                entries.append(
                    self._make_entry(family, tv, _compute_mask_audit(cs))
                )

        strata = _aggregate_denominator_strata(entries)

        self.assertEqual(len(strata), 9)  # 3 families x 3 buckets
        for stratum in strata:
            m = stratum.mask_audit
            self.assertEqual(
                m.candidate_count,
                m.natural_positive_count
                + m.forced_positive_count
                + m.natural_negative_count,
            )


# ===================================================================
# Acceptance Criterion: no losses, model forward, training loop,
#   checkpoint/run-manifest, artifact writes, RDKit, or torch
# ===================================================================


class NoLossesModelForwardEtcTests(unittest.TestCase):
    """The masks/denominators modules must not import or depend on loss
    computation, model forward, training loop, checkpointing, run manifests,
    artifact I/O, RDKit, or torch."""

    def test_mask_module_no_rdkit_or_torch(self) -> None:
        pre_modules = set(sys.modules.keys())

        mod_name = "covalent_design.training.masks"
        if mod_name in sys.modules:
            del sys.modules[mod_name]

        try:
            from covalent_design.training import masks  # noqa: F811
        except ImportError:
            raise AssertionError("Production code import failed.")

        post_modules = set(sys.modules.keys())
        new_modules = post_modules - pre_modules

        rdkit_new = [m for m in new_modules if m.startswith("rdkit")]
        torch_new = [m for m in new_modules if m.startswith("torch")]

        self.assertEqual(
            rdkit_new, [],
            f"masks module imported rdkit: {rdkit_new}",
        )
        self.assertEqual(
            torch_new, [],
            f"masks module imported torch: {torch_new}",
        )

    def test_denominator_module_no_rdkit_or_torch(self) -> None:
        pre_modules = set(sys.modules.keys())

        mod_name = "covalent_design.training.denominators"
        if mod_name in sys.modules:
            del sys.modules[mod_name]

        try:
            from covalent_design.training import denominators  # noqa: F811
        except ImportError:
            raise AssertionError("Production code import failed.")

        post_modules = set(sys.modules.keys())
        new_modules = post_modules - pre_modules

        rdkit_new = [m for m in new_modules if m.startswith("rdkit")]
        torch_new = [m for m in new_modules if m.startswith("torch")]

        self.assertEqual(
            rdkit_new, [],
            f"denominators module imported rdkit: {rdkit_new}",
        )
        self.assertEqual(
            torch_new, [],
            f"denominators module imported torch: {torch_new}",
        )


if __name__ == "__main__":
    unittest.main()
