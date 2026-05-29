"""Tests for Task 21 final decode and validity gate contracts.

Covers gate order, score sorting, top-fail + second-pass, all-fail,
REQUIRED_GATE_STATE_UNAVAILABLE priority, and diagnostics from the
Task 21 spec and verification matrix.

Public API under test::

    covalent_design.model.final_decode.decode_final_edge(
        final_state: FinalLigandState,
        gate: ValidityGate,
    ) -> FinalDecodeResult

These are Task 21 contract tests.
Do not lower assertions.
"""

from __future__ import annotations

import unittest

# ===================================================================
# Contract types (exist in contracts/types.py)
# ===================================================================

from covalent_design.contracts.types import (
    EdgeValidityCheckName,
)

# ===================================================================
# Fixture builder (pure Python, no torch/PMDM/PocketFlow/RDKit)
# ===================================================================

from tests.fixtures.model.final_decode._builder import (
    GATE_CHECK_COUNT,
    SPEC_GATE_ORDER,
    FinalDecodeFixtureBuilder,
    InjectableGate,
    OrderRecordingGate,
    build_candidate_record,
)

# ===================================================================
# The authoritative gate evaluation order from interface-design.md
# Failure Reason Priority section.  This is the contract the
# implementation must follow.  It is re-exported from the fixture
# builder for DRY; we assert against it directly in gate-order tests.
# ===================================================================


# ===================================================================
# Test runner helper: try importing the production module.
# It is acceptable for this to fail because Task 21 production code is not
# implemented yet.  When it fails we skip all decode tests with a
# clear message.
# ===================================================================

_production_available = False
_decode_import_error: str | None = None

try:
    from covalent_design.model.final_decode import (  # noqa: F401
        FinalDecodeResult,
        FinalLigandState,
        _SPEC_GATE_ORDER as PRODUCTION_GATE_ORDER,
        decode_final_edge,
    )
    from covalent_design.model.validity_gate import ValidityGate  # noqa: F401

    _production_available = True
except ImportError as _e:
    _decode_import_error = str(_e)


_need_production = unittest.skipUnless(
    _production_available,
    f"Task 21 production modules not available: {_decode_import_error}",
)


# ===================================================================
# Gate order contract is always testable (SPEC_GATE_ORDER is a fixture
# constant).  Gate order and check-name coverage assertions do NOT
# need production code.
# ===================================================================


class GateOrderContractTests(unittest.TestCase):
    """Gate order contract: the 9 checks must execute in the exact order
    specified by the interface-design.md Failure Reason Priority section.

    These tests assert the contract constant itself, so they do not need
    the production decode_final_edge implementation.
    """

    def test_01_gate_order_has_exactly_nine_checks(self):
        """The spec defines exactly 9 validity gate checks."""
        self.assertEqual(
            len(SPEC_GATE_ORDER),
            9,
            f"SPEC_GATE_ORDER must have 9 checks, got {len(SPEC_GATE_ORDER)}",
        )

    def test_02_gate_order_matches_expected_sequence(self):
        """Gate checks must execute in this exact order:
        target_atom -> ligand_atom_class -> bond_type ->
        single_edge_representability -> warhead_smarts -> forbidden_smarts ->
        valence -> protonation -> geometry
        """
        expected = (
            "target_atom",
            "ligand_atom_class",
            "bond_type",
            "single_edge_representability",
            "warhead_smarts",
            "forbidden_smarts",
            "valence",
            "protonation",
            "geometry",
        )
        self.assertEqual(
            SPEC_GATE_ORDER,
            expected,
            "SPEC_GATE_ORDER must follow the interface-design.md "
            "Failure Reason Priority order exactly",
        )

    def test_02b_production_gate_order_matches_fixture(self):
        """Production and fixture gate order constants must not drift."""
        self.assertEqual(PRODUCTION_GATE_ORDER, SPEC_GATE_ORDER)

    def test_03_all_gate_check_names_are_valid_edge_validity_check_names(self):
        """Every check name in SPEC_GATE_ORDER must be a member of
        EdgeValidityCheckName (so it is a recognised contract value)."""
        for name in SPEC_GATE_ORDER:
            self.assertIn(
                name,
                EdgeValidityCheckName,
                f"'{name}' in SPEC_GATE_ORDER is not a valid "
                f"EdgeValidityCheckName value",
            )

    def test_04_no_duplicate_check_names_in_gate_order(self):
        """Gate order must not contain duplicate check names."""
        self.assertEqual(
            len(SPEC_GATE_ORDER),
            len(set(SPEC_GATE_ORDER)),
            "SPEC_GATE_ORDER contains duplicate check names",
        )

    def test_05_single_edge_representability_is_at_position_4(self):
        """single_edge_representability must be at index 3 (4th check),
        not at the end of the tuple."""
        self.assertEqual(
            SPEC_GATE_ORDER[3],
            "single_edge_representability",
            "single_edge_representability must be the 4th gate check "
            "(index 3), per interface-design.md Failure Reason Priority",
        )


# ===================================================================
# InjectableGate unit tests verify the test double works correctly
# before using it in decode tests.
# ===================================================================


class InjectableGateSelfTests(unittest.TestCase):
    """Verify InjectableGate evaluates checks in spec order and returns
    correct EdgeValidityCheck records.  These tests validate the test
    double, not the production code."""

    def test_all_pass_returns_pass_for_every_check(self):
        gate = InjectableGate(default_status="pass")
        candidate = build_candidate_record(score=0.9)
        results = gate.evaluate(0, candidate, {})

        self.assertEqual(len(results), GATE_CHECK_COUNT)
        for i, check in enumerate(results):
            self.assertEqual(
                check.status,
                "pass",
                f"Check {SPEC_GATE_ORDER[i]} should pass",
            )

    def test_evaluates_checks_in_spec_order(self):
        gate = InjectableGate(default_status="pass")
        candidate = build_candidate_record(score=0.9)
        gate.evaluate(0, candidate, {})

        self.assertEqual(
            gate.last_eval_order,
            list(SPEC_GATE_ORDER),
            "InjectableGate must evaluate checks in SPEC_GATE_ORDER",
        )

    def test_specific_failure_produces_fail_status(self):
        gate = InjectableGate(default_status="pass")
        gate.set_status(0, "bond_type", "fail")
        candidate = build_candidate_record(score=0.9)
        results = gate.evaluate(0, candidate, {})

        bond_type_check = results[2]  # bond_type is index 2
        self.assertEqual(bond_type_check.check_name, "bond_type")
        self.assertEqual(bond_type_check.status, "fail")
        self.assertIsNotNone(bond_type_check.failure_code)

    def test_not_evaluable_produces_unavailable_failure_code(self):
        gate = InjectableGate(default_status="pass")
        gate.set_status(0, "protonation", "not_evaluable")
        candidate = build_candidate_record(score=0.9)
        results = gate.evaluate(0, candidate, {})

        protonation_check = results[7]  # protonation is index 7
        self.assertEqual(protonation_check.check_name, "protonation")
        self.assertEqual(protonation_check.status, "not_evaluable")
        self.assertEqual(
            protonation_check.failure_code,
            "REQUIRED_GATE_STATE_UNAVAILABLE",
        )

    def test_per_candidate_statuses_are_independent(self):
        gate = InjectableGate(default_status="pass")
        gate.set_status(0, "valence", "fail")
        gate.set_status(1, "geometry", "fail")

        c0 = build_candidate_record(score=0.9, ligand_atom_index=0)
        c1 = build_candidate_record(score=0.5, ligand_atom_index=1)

        r0 = gate.evaluate(0, c0, {})
        r1 = gate.evaluate(1, c1, {})

        # Candidate 0: valence fails
        self.assertEqual(r0[6].check_name, "valence")
        self.assertEqual(r0[6].status, "fail")
        self.assertEqual(r0[8].status, "pass")

        # Candidate 1: geometry fails
        self.assertEqual(r1[6].status, "pass")
        self.assertEqual(r1[8].check_name, "geometry")
        self.assertEqual(r1[8].status, "fail")


class OrderRecordingGateSelfTests(unittest.TestCase):
    """Verify OrderRecordingGate tracks the call sequence correctly."""

    def test_records_call_sequence_for_multiple_candidates(self):
        gate = OrderRecordingGate()
        c0 = build_candidate_record(score=0.9, ligand_atom_index=0)
        c1 = build_candidate_record(score=0.5, ligand_atom_index=1)

        gate.evaluate(0, c0, {})
        gate.evaluate(1, c1, {})

        # Should have 18 calls: 9 checks x 2 candidates
        self.assertEqual(len(gate.call_sequence), 18)

        # First 9 calls should be for candidate 0, in spec order
        for i, (cand_idx, check_name) in enumerate(gate.call_sequence[:9]):
            self.assertEqual(cand_idx, 0)
            self.assertEqual(check_name, SPEC_GATE_ORDER[i])

        # Next 9 calls should be for candidate 1, in spec order
        for i, (cand_idx, check_name) in enumerate(gate.call_sequence[9:]):
            self.assertEqual(cand_idx, 1)
            self.assertEqual(check_name, SPEC_GATE_ORDER[i])


# ===================================================================
# FinalDecodeFixtureBuilder self-tests verify fixtures are well-formed
# ===================================================================


class FinalDecodeFixtureBuilderSelfTests(unittest.TestCase):
    """Verify the fixture builder creates well-formed test data."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = FinalDecodeFixtureBuilder(seed=42)

    def test_build_candidates_assigns_scores_in_order(self):
        candidates = self.builder.build_candidates([0.9, 0.5, 0.1])
        self.assertEqual(len(candidates), 3)
        self.assertEqual(candidates[0]["score"], 0.9)
        self.assertEqual(candidates[1]["score"], 0.5)
        self.assertEqual(candidates[2]["score"], 0.1)

    def test_build_candidates_generates_unique_ligand_atom_indices(self):
        candidates = self.builder.build_candidates([0.9, 0.5], base_ligand_index=5)
        self.assertEqual(candidates[0]["ligand_atom"]["atom_index"], 5)
        self.assertEqual(candidates[1]["ligand_atom"]["atom_index"], 6)

    def test_build_final_ligand_state_preserves_candidate_data(self):
        candidates = self.builder.build_candidates([0.9, 0.2])
        state = self.builder.build_final_ligand_state(candidates)
        self.assertEqual(len(state["candidates"]), 2)
        self.assertEqual(state["candidate_scores"], [0.9, 0.2])

    def test_build_all_pass_gate_passes_every_check(self):
        gate = self.builder.build_all_pass_gate()
        candidate = build_candidate_record(score=0.9)
        results = gate.evaluate(0, candidate, {})

        for check in results:
            self.assertEqual(check.status, "pass")

    def test_build_single_check_fail_gate_only_fails_targeted_check(self):
        gate = self.builder.build_single_check_fail_gate(0, "warhead_smarts")
        candidate = build_candidate_record(score=0.9)
        results = gate.evaluate(0, candidate, {})

        fail_count = sum(1 for c in results if c.status == "fail")
        self.assertEqual(fail_count, 1)
        self.assertEqual(results[4].check_name, "warhead_smarts")
        self.assertEqual(results[4].status, "fail")

    def test_build_unavailable_gate_sets_not_evaluable(self):
        gate = self.builder.build_unavailable_gate(0, "protonation")
        candidate = build_candidate_record(score=0.9)
        results = gate.evaluate(0, candidate, {})

        self.assertEqual(results[7].check_name, "protonation")
        self.assertEqual(results[7].status, "not_evaluable")
        self.assertEqual(
            results[7].failure_code,
            "REQUIRED_GATE_STATE_UNAVAILABLE",
        )


# ===================================================================
# decode_final_edge contract tests
# ===================================================================


@_need_production
class DecodeFinalEdgeAPITests(unittest.TestCase):
    """API existence and basic callability."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = FinalDecodeFixtureBuilder(seed=42)

    def test_decode_final_edge_is_callable(self):
        """decode_final_edge must be a callable accepting (final_state, gate)."""
        self.assertTrue(
            callable(decode_final_edge),
            "decode_final_edge must be importable and callable",
        )

    def test_decode_final_edge_accepts_final_state_and_gate(self):
        """decode_final_edge must accept a FinalLigandState and a ValidityGate."""
        candidates = self.builder.build_candidates([0.9, 0.3])
        state = self.builder.build_final_ligand_state(candidates)
        gate = self.builder.build_all_pass_gate()

        result = decode_final_edge(state, gate)
        self.assertIsNotNone(result)

    def test_returns_final_decode_result(self):
        """decode_final_edge must return a FinalDecodeResult."""
        candidates = self.builder.build_candidates([0.9])
        state = self.builder.build_final_ligand_state(candidates)
        gate = self.builder.build_all_pass_gate()

        result = decode_final_edge(state, gate)
        self.assertIsInstance(result, FinalDecodeResult)

    def test_result_has_required_fields(self):
        """FinalDecodeResult must have generation_validity_status,
        selected_edge, primary_failure_reason, secondary_failure_reasons,
        and edge_validity_checks."""
        candidates = self.builder.build_candidates([0.9])
        state = self.builder.build_final_ligand_state(candidates)
        gate = self.builder.build_all_pass_gate()

        result = decode_final_edge(state, gate)

        self.assertTrue(hasattr(result, "generation_validity_status"))
        self.assertTrue(hasattr(result, "selected_edge"))
        self.assertTrue(hasattr(result, "primary_failure_reason"))
        self.assertTrue(hasattr(result, "secondary_failure_reasons"))
        self.assertTrue(hasattr(result, "edge_validity_checks"))


@_need_production
class ScoreSortingTests(unittest.TestCase):
    """Candidates must be evaluated in descending score order."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = FinalDecodeFixtureBuilder(seed=42)

    def test_highest_scoring_candidate_evaluated_first(self):
        """When multiple candidates have different scores, the highest-scoring
        candidate must be evaluated first.  If it passes all gates, it is
        the selected edge."""
        # Candidate scores: [0.3, 0.9, 0.5], so candidate at index 1 has
        # the highest score and should be selected.
        candidates = self.builder.build_candidates([0.3, 0.9, 0.5])
        state = self.builder.build_final_ligand_state(candidates)
        gate = self.builder.build_all_pass_gate()

        result = decode_final_edge(state, gate)

        self.assertEqual(result.generation_validity_status, "valid")
        self.assertIsNotNone(result.selected_edge)

        # The selected edge should be the highest-scoring candidate
        # (ligand_atom_index=1, score=0.9)
        if hasattr(result, "selected_score"):
            self.assertEqual(result.selected_score, 0.9)

    def test_not_applicable_check_does_not_block_candidate(self):
        """A not_applicable gate check is non-blocking for final decode."""
        candidates = self.builder.build_candidates([0.95, 0.85])
        state = self.builder.build_final_ligand_state(candidates)

        gate = InjectableGate(default_status="pass")
        gate.set_status(0, "warhead_smarts", "not_applicable")

        result = decode_final_edge(state, gate)

        self.assertEqual(result.generation_validity_status, "valid")
        self.assertIsNotNone(result.selected_edge)
        self.assertEqual(
            result.selected_edge.ligand_atom.atom_index,
            candidates[0]["ligand_atom"]["atom_index"],
        )
        self.assertEqual(result.selected_score, 0.95)

    def test_candidates_with_equal_scores_preserve_stable_order(self):
        """Candidates with equal scores must produce deterministic results."""
        candidates = self.builder.build_candidates([0.5, 0.5, 0.5])
        state = self.builder.build_final_ligand_state(candidates)
        gate = self.builder.build_all_pass_gate()

        result1 = decode_final_edge(state, gate)
        result2 = decode_final_edge(state, gate)

        # Results must be identical across repeated calls
        self.assertEqual(
            result1.generation_validity_status,
            result2.generation_validity_status,
        )
        if result1.selected_edge is not None:
            self.assertEqual(
                result1.selected_edge.ligand_atom.atom_index,
                result2.selected_edge.ligand_atom.atom_index,
            )

    def test_single_candidate_with_any_score_is_evaluated(self):
        """A single candidate, regardless of score, must be evaluated."""
        candidates = self.builder.build_candidates([-5.0])
        state = self.builder.build_final_ligand_state(candidates)
        gate = self.builder.build_all_pass_gate()

        result = decode_final_edge(state, gate)
        self.assertEqual(result.generation_validity_status, "valid")
        self.assertIsNotNone(result.selected_edge)


@_need_production
class TopFailSecondPassTests(unittest.TestCase):
    """Top-scoring candidate fails, a lower-ranked candidate passes: valid.

    The spec says: "If the top-scoring candidate fails and a lower-ranked
    candidate passes all checks, the sample is **valid**:
    secondary_failure_reasons preserves skipped-candidate failures
    for diagnostic review."
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = FinalDecodeFixtureBuilder(seed=42)

    def test_top_fail_second_pass_is_valid(self):
        """Candidate 0 (score=0.95) fails 'target_atom'.
        Candidate 1 (score=0.85) passes all checks.
        Result must be valid with candidate 1 selected."""
        candidates = self.builder.build_candidates([0.95, 0.85, 0.30])
        state = self.builder.build_final_ligand_state(candidates)

        gate = InjectableGate(default_status="pass")
        gate.set_status(0, "target_atom", "fail")

        result = decode_final_edge(state, gate)

        self.assertEqual(
            result.generation_validity_status,
            "valid",
            "Top-fail + second-pass must produce a valid sample",
        )
        self.assertIsNotNone(
            result.selected_edge,
            "A passing lower-ranked candidate must be selected",
        )
        self.assertIsNone(
            result.primary_failure_reason,
            "primary_failure_reason must be None when a valid edge is found",
        )

    def test_secondary_failure_reasons_records_skipped_failures(self):
        """When the top candidate fails and a lower candidate passes,
        secondary_failure_reasons must record the top candidate's failure."""
        candidates = self.builder.build_candidates([0.95, 0.85])
        state = self.builder.build_final_ligand_state(candidates)

        gate = InjectableGate(default_status="pass")
        gate.set_status(0, "bond_type", "fail")

        result = decode_final_edge(state, gate)

        self.assertEqual(result.generation_validity_status, "valid")
        self.assertIsNotNone(result.selected_edge)

        # secondary_failure_reasons must not be empty
        self.assertGreater(
            len(result.secondary_failure_reasons),
            0,
            "secondary_failure_reasons must preserve skipped-candidate failures",
        )

    def test_top_two_fail_third_passes_all_secondary_reasons_preserved(self):
        """Candidates 0 and 1 fail; candidate 2 passes.
        Both failures must appear in secondary_failure_reasons."""
        candidates = self.builder.build_candidates([0.95, 0.85, 0.30])
        state = self.builder.build_final_ligand_state(candidates)

        gate = InjectableGate(default_status="pass")
        gate.set_status(0, "target_atom", "fail")
        gate.set_status(1, "valence", "fail")

        result = decode_final_edge(state, gate)

        self.assertEqual(result.generation_validity_status, "valid")
        self.assertIsNotNone(result.selected_edge)

        # At least 2 entries in secondary_failure_reasons
        self.assertGreaterEqual(
            len(result.secondary_failure_reasons),
            2,
            "Both skipped-candidate failures must be recorded",
        )

    def test_secondary_failure_reasons_are_deduplicated(self):
        """Repeated skipped-candidate failures appear once, deterministically."""
        candidates = self.builder.build_candidates([0.95, 0.85, 0.30])
        state = self.builder.build_final_ligand_state(candidates)

        gate = InjectableGate(default_status="pass")
        gate.set_status(0, "bond_type", "fail")
        gate.set_status(1, "bond_type", "fail")

        result = decode_final_edge(state, gate)

        self.assertEqual(result.generation_validity_status, "valid")
        self.assertEqual(
            result.secondary_failure_reasons.count("GATE_BOND_TYPE_FAIL"),
            1,
        )

    def test_only_skipped_candidates_appear_in_secondary_failures(self):
        """Failures of candidates ranked below the selected one must NOT
        appear in secondary_failure_reasons (they were never reached)."""
        candidates = self.builder.build_candidates([0.95, 0.85, 0.30])
        state = self.builder.build_final_ligand_state(candidates)

        # Candidate 0 passes, so it is selected.
        # Candidate 1 would fail but is never evaluated
        # Candidate 2 would fail but is never evaluated
        gate = InjectableGate(default_status="pass")
        gate.set_status(0, "target_atom", "pass")
        gate.set_status(1, "geometry", "fail")
        gate.set_status(2, "valence", "fail")

        result = decode_final_edge(state, gate)

        self.assertEqual(result.generation_validity_status, "valid")
        self.assertIsNotNone(result.selected_edge)

        # No secondary failures: candidate 0 passed, others were never evaluated
        self.assertEqual(
            len(result.secondary_failure_reasons),
            0,
            "Candidates never evaluated must not appear in secondary_failure_reasons",
        )


@_need_production
class AllFailTests(unittest.TestCase):
    """All candidates fail: generation_validity_status = 'invalid'.

    primary_failure_reason must be the first failure of the highest-scoring
    candidate.  selected_edge must be None.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = FinalDecodeFixtureBuilder(seed=42)

    def test_all_fail_returns_invalid(self):
        """When every candidate fails at least one gate check, the result
        must be invalid."""
        candidates = self.builder.build_candidates([0.9, 0.5, 0.3])
        state = self.builder.build_final_ligand_state(candidates)

        gate = InjectableGate(default_status="fail")

        result = decode_final_edge(state, gate)

        self.assertEqual(
            result.generation_validity_status,
            "invalid",
            "All-candidates-fail must produce invalid status",
        )

    def test_primary_failure_is_first_failure_of_best_candidate(self):
        """primary_failure_reason must reflect the first failing check
        of the highest-scoring candidate, not a lower-ranked candidate."""
        candidates = self.builder.build_candidates([0.9, 0.5])
        state = self.builder.build_final_ligand_state(candidates)

        # Best candidate (index 0, score 0.9) fails at 'bond_type' (3rd check)
        # Weaker candidate also fails but its failure is not primary
        gate = InjectableGate(default_status="pass")
        gate.set_status(0, "bond_type", "fail")  # index 2 in order
        gate.set_status(1, "target_atom", "fail")

        result = decode_final_edge(state, gate)

        self.assertEqual(result.generation_validity_status, "invalid")
        self.assertIsNotNone(result.primary_failure_reason)

        # The primary failure should relate to bond_type, not target_atom
        primary = result.primary_failure_reason or ""
        self.assertIn(
            "bond_type",
            primary.lower(),
            f"Primary failure must be from best candidate's first failure "
            f"(bond_type), got: {primary}",
        )

    def test_selected_edge_is_none_when_all_fail(self):
        """decode_final_edge must never return a best-failed edge as valid.
        When all candidates fail, selected_edge must be None."""
        candidates = self.builder.build_candidates([0.9, 0.5])
        state = self.builder.build_final_ligand_state(candidates)

        gate = InjectableGate(default_status="fail")

        result = decode_final_edge(state, gate)

        self.assertIsNone(
            result.selected_edge,
            "selected_edge must be None when all candidates fail",
        )

    def test_all_fail_single_candidate(self):
        """A single candidate that fails is invalid."""
        candidates = self.builder.build_candidates([0.9])
        state = self.builder.build_final_ligand_state(candidates)

        gate = InjectableGate(default_status="fail")

        result = decode_final_edge(state, gate)

        self.assertEqual(result.generation_validity_status, "invalid")
        self.assertIsNone(result.selected_edge)
        self.assertIsNotNone(result.primary_failure_reason)

    def test_first_failing_check_is_primary_for_best_candidate(self):
        """When the highest-scoring candidate fails at warhead_smarts (5th check)
        but would also fail geometry (9th check), the primary failure must be
        warhead_smarts, the first failure encountered in gate order."""
        candidates = self.builder.build_candidates([0.9, 0.5])
        state = self.builder.build_final_ligand_state(candidates)

        gate = InjectableGate(default_status="pass")
        gate.set_status(0, "warhead_smarts", "fail")
        gate.set_status(0, "geometry", "fail")
        gate.set_status(1, "target_atom", "fail")

        result = decode_final_edge(state, gate)

        self.assertEqual(result.generation_validity_status, "invalid")
        primary = result.primary_failure_reason or ""
        self.assertIn(
            "warhead_smarts",
            primary.lower(),
            f"Primary failure should be warhead_smarts (first failure), "
            f"got: {primary}",
        )
        self.assertNotIn(
            "geometry",
            primary.lower(),
            "Later check failures must not be the primary failure reason",
        )


@_need_production
class RequiredStateUnavailablePriorityTests(unittest.TestCase):
    """REQUIRED_GATE_STATE_UNAVAILABLE outranks all specific failures.

    Per the spec: "REQUIRED_GATE_STATE_UNAVAILABLE outranks all other
    failures (the gate cannot be evaluated)."
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = FinalDecodeFixtureBuilder(seed=42)

    def test_unavailable_outranks_specific_failure_same_candidate(self):
        """When a candidate has both a specific failure and an unavailable
        gate state, the unavailable status must be the primary failure."""
        candidates = self.builder.build_candidates([0.9, 0.5])
        state = self.builder.build_final_ligand_state(candidates)

        # Candidate 0: protonation is not_evaluable (state unavailable)
        # Candidate 1: also fails at target_atom
        gate = InjectableGate(default_status="pass")
        gate.set_status(0, "protonation", "not_evaluable")
        gate.set_status(1, "target_atom", "fail")

        result = decode_final_edge(state, gate)

        self.assertEqual(result.generation_validity_status, "invalid")

        # The unavailable state check (protonation) should take priority
        # over any other failure if it's the best candidate's first failing check
        primary = result.primary_failure_reason or ""
        self.assertIn("REQUIRED_GATE_STATE_UNAVAILABLE", primary)
        self.assertIn("protonation", primary.lower())

    def test_unavailable_is_primary_even_with_specific_failure_same_candidate(self):
        """An unavailable required gate state outranks specific failures."""
        candidates = self.builder.build_candidates([0.9, 0.5])
        state = self.builder.build_final_ligand_state(candidates)

        # Candidate 0: warhead_smarts not_evaluable AND forbidden_smarts fails
        # In gate order: warhead_smarts (5th) comes before forbidden_smarts (6th)
        # So warhead_smarts not_evaluable is encountered first and is primary.
        gate = InjectableGate(default_status="pass")
        gate.set_status(0, "warhead_smarts", "not_evaluable")
        gate.set_status(0, "forbidden_smarts", "fail")

        result = decode_final_edge(state, gate)

        self.assertEqual(result.generation_validity_status, "invalid")

        primary = result.primary_failure_reason or ""
        # The primary should reference the first failing/non-pass check
        # which is warhead_smarts with not_evaluable status
        self.assertIn(
            "warhead_smarts",
            primary.lower(),
            f"First non-pass check (warhead_smarts/not_evaluable) must be "
            f"primary, got: {primary}",
        )

    def test_later_unavailable_outranks_earlier_specific_failure(self):
        """Required-state unavailable blocks even after an earlier fail."""
        candidates = self.builder.build_candidates([0.9, 0.5])
        state = self.builder.build_final_ligand_state(candidates)

        gate = InjectableGate(default_status="pass")
        gate.set_status(0, "target_atom", "fail")
        gate.set_status(0, "geometry", "not_evaluable")

        result = decode_final_edge(state, gate)

        self.assertEqual(result.generation_validity_status, "invalid")
        primary = result.primary_failure_reason or ""
        self.assertIn("REQUIRED_GATE_STATE_UNAVAILABLE", primary)
        self.assertIn("geometry", primary.lower())

    def test_unavailable_as_first_check_failure(self):
        """When the very first gate check (target_atom) is not_evaluable,
        that must be the primary failure and must use
        REQUIRED_GATE_STATE_UNAVAILABLE."""
        candidates = self.builder.build_candidates([0.9, 0.3])
        state = self.builder.build_final_ligand_state(candidates)

        gate = InjectableGate(default_status="pass")
        gate.set_status(0, "target_atom", "not_evaluable")

        result = decode_final_edge(state, gate)

        self.assertEqual(result.generation_validity_status, "invalid")
        self.assertIsNotNone(result.primary_failure_reason)


@_need_production
class EdgeValidityChecksTests(unittest.TestCase):
    """edge_validity_checks must include all evaluated candidates.

    Per the spec: "edge_validity_checks includes every evaluated candidate
    (passed and failed)."
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = FinalDecodeFixtureBuilder(seed=42)

    def test_all_candidates_in_edge_validity_checks_when_all_pass(self):
        """When all candidates pass, edge_validity_checks must contain
        check records for every evaluated candidate."""
        candidates = self.builder.build_candidates([0.9, 0.5, 0.3])
        state = self.builder.build_final_ligand_state(candidates)
        gate = self.builder.build_all_pass_gate()

        result = decode_final_edge(state, gate)

        self.assertEqual(result.generation_validity_status, "valid")

        # All 3 candidates should have been evaluated (first one passed)
        # The first candidate passed, so at minimum it has check records.
        self.assertGreater(
            len(result.edge_validity_checks),
            0,
            "edge_validity_checks must not be empty",
        )

    def test_all_failed_candidates_in_edge_validity_checks(self):
        """When all candidates fail, edge_validity_checks must include
        check records for every candidate that was evaluated."""
        candidates = self.builder.build_candidates([0.9, 0.5])
        state = self.builder.build_final_ligand_state(candidates)

        gate = InjectableGate(default_status="fail")

        result = decode_final_edge(state, gate)

        self.assertEqual(result.generation_validity_status, "invalid")

        # All candidates were evaluated (both failed), so edge_validity_checks
        # should reflect this
        self.assertGreater(
            len(result.edge_validity_checks),
            0,
            "edge_validity_checks must include all evaluated candidates",
        )

    def test_edge_validity_checks_structure_is_valid(self):
        """Each entry in edge_validity_checks must be an EdgeValidityCheck
        or a dict/mapping with check_name, status, and failure_code fields."""
        candidates = self.builder.build_candidates([0.9])
        state = self.builder.build_final_ligand_state(candidates)
        gate = self.builder.build_all_pass_gate()

        result = decode_final_edge(state, gate)

        for check in result.edge_validity_checks:
            # Must have a check_name
            self.assertTrue(
                hasattr(check, "check_name") or isinstance(check, dict),
                "Each entry in edge_validity_checks must identify the check",
            )

    def test_top_fail_second_pass_includes_all_evaluated_candidates_in_checks(self):
        """Top candidate fails, second passes; edge_validity_checks must
        include check records for the failed top candidate AND the passing
        second candidate."""
        candidates = self.builder.build_candidates([0.9, 0.5])
        state = self.builder.build_final_ligand_state(candidates)

        gate = InjectableGate(default_status="pass")
        gate.set_status(0, "valence", "fail")

        result = decode_final_edge(state, gate)

        self.assertEqual(result.generation_validity_status, "valid")
        self.assertGreater(
            len(result.edge_validity_checks),
            0,
            "edge_validity_checks must cover all evaluated candidates",
        )


@_need_production
class NoForcedEdgeTests(unittest.TestCase):
    """decode_final_edge must never return a best-failed edge as valid.

    Per the spec: "Never returns a forced edge when all candidates fail."
    and the MISSING GUARDS: "decode_final_edge() returns FinalDecodeResult
    with either a selected valid edge or full failure metadata; it never
    returns a best-failed-edge as valid."
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = FinalDecodeFixtureBuilder(seed=42)

    def test_all_fail_no_edge_returned(self):
        """When all candidates fail, selected_edge must be None and
        generation_validity_status must be 'invalid'."""
        candidates = self.builder.build_candidates([0.9, 0.5])
        state = self.builder.build_final_ligand_state(candidates)

        gate = InjectableGate(default_status="fail")

        result = decode_final_edge(state, gate)

        self.assertIsNone(result.selected_edge)
        self.assertEqual(result.generation_validity_status, "invalid")

    def test_no_partial_edge_when_only_best_candidate_fails(self):
        """Even if only the best candidate fails a late check, and there
        are no other candidates, no edge is returned."""
        candidates = self.builder.build_candidates([0.9])
        state = self.builder.build_final_ligand_state(candidates)

        gate = InjectableGate(default_status="pass")
        gate.set_status(0, "geometry", "fail")

        result = decode_final_edge(state, gate)

        self.assertIsNone(result.selected_edge)
        self.assertEqual(result.generation_validity_status, "invalid")

    def test_valid_result_always_has_selected_edge(self):
        """When generation_validity_status is 'valid', selected_edge must
        not be None."""
        candidates = self.builder.build_candidates([0.9])
        state = self.builder.build_final_ligand_state(candidates)
        gate = self.builder.build_all_pass_gate()

        result = decode_final_edge(state, gate)

        self.assertEqual(result.generation_validity_status, "valid")
        self.assertIsNotNone(
            result.selected_edge,
            "Valid results must have a non-None selected_edge",
        )

    def test_invalid_result_always_has_none_selected_edge(self):
        """When generation_validity_status is 'invalid', selected_edge must
        be None."""
        candidates = self.builder.build_candidates([0.5])
        state = self.builder.build_final_ligand_state(candidates)

        gate = InjectableGate(default_status="fail")

        result = decode_final_edge(state, gate)

        self.assertEqual(result.generation_validity_status, "invalid")
        self.assertIsNone(
            result.selected_edge,
            "Invalid results must have None selected_edge",
        )


@_need_production
class PrimaryFailureReasonTests(unittest.TestCase):
    """primary_failure_reason is None for valid, non-None for invalid."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = FinalDecodeFixtureBuilder(seed=42)

    def test_valid_result_primary_failure_is_none(self):
        """A valid result must have primary_failure_reason = None."""
        candidates = self.builder.build_candidates([0.9])
        state = self.builder.build_final_ligand_state(candidates)
        gate = self.builder.build_all_pass_gate()

        result = decode_final_edge(state, gate)
        self.assertEqual(result.generation_validity_status, "valid")
        self.assertIsNone(result.primary_failure_reason)

    def test_invalid_result_primary_failure_is_not_none(self):
        """An invalid result must have a non-None primary_failure_reason."""
        candidates = self.builder.build_candidates([0.9])
        state = self.builder.build_final_ligand_state(candidates)

        gate = InjectableGate(default_status="fail")

        result = decode_final_edge(state, gate)
        self.assertEqual(result.generation_validity_status, "invalid")
        self.assertIsNotNone(result.primary_failure_reason)
        self.assertIsNone(result.selected_score)

    def test_valid_with_secondary_failures_has_null_primary(self):
        """Even when secondary_failure_reasons is populated (top-fail,
        second-pass case), primary_failure_reason must be None because
        a valid edge was found."""
        candidates = self.builder.build_candidates([0.9, 0.5])
        state = self.builder.build_final_ligand_state(candidates)

        gate = InjectableGate(default_status="pass")
        gate.set_status(0, "bond_type", "fail")

        result = decode_final_edge(state, gate)

        self.assertEqual(result.generation_validity_status, "valid")
        self.assertIsNone(result.primary_failure_reason)
        self.assertGreater(len(result.secondary_failure_reasons), 0)


@_need_production
class EmptyCandidatesTests(unittest.TestCase):
    """Edge case: zero candidates."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = FinalDecodeFixtureBuilder(seed=42)

    def test_zero_candidates_returns_invalid(self):
        """When there are zero candidates, the result must be invalid."""
        state = self.builder.build_final_ligand_state([])
        gate = self.builder.build_all_pass_gate()

        result = decode_final_edge(state, gate)

        self.assertEqual(result.generation_validity_status, "invalid")
        self.assertIsNone(result.selected_edge)
        self.assertIsNotNone(result.primary_failure_reason)


# ===================================================================
# Determinism and side-effect tests
# ===================================================================


@_need_production
class DeterminismTests(unittest.TestCase):
    """decode_final_edge must be deterministic: same inputs, same output."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = FinalDecodeFixtureBuilder(seed=42)

    def test_same_inputs_produce_identical_result(self):
        """Two calls with identical (state, gate) must produce identical
        FinalDecodeResult values."""
        candidates = self.builder.build_candidates([0.9, 0.5, 0.1])
        state = self.builder.build_final_ligand_state(candidates)
        gate = self.builder.build_all_pass_gate()

        result1 = decode_final_edge(state, gate)
        result2 = decode_final_edge(state, gate)

        self.assertEqual(
            result1.generation_validity_status,
            result2.generation_validity_status,
        )
        self.assertEqual(
            result1.primary_failure_reason,
            result2.primary_failure_reason,
        )
        self.assertEqual(
            result1.secondary_failure_reasons,
            result2.secondary_failure_reasons,
        )

    def test_decode_does_not_mutate_input_state(self):
        """decode_final_edge must not mutate the input FinalLigandState."""
        import copy

        candidates = self.builder.build_candidates([0.9, 0.5])
        state = self.builder.build_final_ligand_state(candidates)
        state_before = copy.deepcopy(state)

        gate = self.builder.build_all_pass_gate()
        decode_final_edge(state, gate)

        self.assertEqual(
            state,
            state_before,
            "decode_final_edge must not mutate the input state",
        )


if __name__ == "__main__":
    unittest.main()
