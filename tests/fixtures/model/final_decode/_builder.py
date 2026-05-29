"""Fixtures for final decode and validity gate contract tests (Task 21).

Provides pure-Python injectable gate implementations and fixture builders
for testing ``decode_final_edge`` without torch, PMDM, PocketFlow, or RDKit.

Usage from tests::

    from tests.fixtures.model.final_decode._builder import (
        FinalDecodeFixtureBuilder,
        InjectableGate,
    )

    builder = FinalDecodeFixtureBuilder()
    state = builder.build_final_ligand_state(scores=[0.9, 0.5, 0.3])
    gate = builder.build_all_pass_gate()
"""

from __future__ import annotations

import copy
from typing import Optional

from covalent_design.contracts.types import (
    CovalentEdge,
    EdgeValidityCheck,
    LigandAtomIdentity,
    ProteinAtomIdentity,
)

# The correct gate evaluation order per interface-design.md Failure Reason Priority.
# This is authoritative over the current EdgeValidityCheckName tuple ordering.
SPEC_GATE_ORDER: tuple[str, ...] = (
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

GATE_CHECK_COUNT = len(SPEC_GATE_ORDER)

# Re-export for convenience
__all__ = [
    "FinalDecodeFixtureBuilder",
    "GATE_CHECK_COUNT",
    "InjectableGate",
    "OrderRecordingGate",
    "SPEC_GATE_ORDER",
    "build_candidate_record",
    "make_covalent_edge",
]


def make_covalent_edge(
    ligand_atom_name: str = "C1",
    ligand_atom_index: int = 0,
    ligand_id: str = "LIG",
    target_atom_name: str = "SG",
    target_residue_name: str = "CYS",
    target_residue_number: int = 145,
    target_chain_id: str = "A",
    bond_type: str = "carbon-sulfur",
) -> CovalentEdge:
    """Build a minimal CovalentEdge for test assertions."""
    return CovalentEdge(
        protein_atom=ProteinAtomIdentity(
            chain_id=target_chain_id,
            residue_number=target_residue_number,
            residue_name=target_residue_name,
            atom_name=target_atom_name,
        ),
        ligand_atom=LigandAtomIdentity(
            ligand_id=ligand_id,
            atom_name=ligand_atom_name,
            atom_index=ligand_atom_index,
        ),
        bond_type=bond_type,
    )


def build_candidate_record(
    *,
    ligand_atom_name: str = "C1",
    ligand_atom_index: int = 0,
    ligand_id: str = "LIG",
    ligand_chain_id: str = "A",
    target_atom_name: str = "SG",
    target_residue_name: str = "CYS",
    target_residue_number: int = 145,
    target_chain_id: str = "A",
    bond_type: str = "carbon-sulfur",
    score: float = 0.5,
) -> dict:
    """Build a candidate record dict with identity fields and a score.

    Returns a plain dict so tests can construct FinalLigandState without
    depending on the exact production dataclass structure.
    """
    return {
        "ligand_atom": {
            "ligand_id": ligand_id,
            "atom_name": ligand_atom_name,
            "atom_index": ligand_atom_index,
            "chain_id": ligand_chain_id,
        },
        "target_atom": {
            "chain_id": target_chain_id,
            "residue_number": target_residue_number,
            "residue_name": target_residue_name,
            "atom_name": target_atom_name,
        },
        "bond_type": bond_type,
        "score": score,
    }


def _make_edge_validity_check(
    check_name: str,
    status: str,
    observed_value: str = "",
    threshold_or_rule: str = "",
    failure_code: Optional[str] = None,
    rule_table_version: str = "1.0.0",
) -> EdgeValidityCheck:
    return EdgeValidityCheck(
        check_name=check_name,
        status=status,
        observed_value=observed_value,
        threshold_or_rule=threshold_or_rule,
        rule_table_version=rule_table_version,
        failure_code=failure_code,
    )


class InjectableGate:
    """A validity gate with pre-configured per-candidate per-check results.

    Each (candidate_index, check_name) pair maps to a status string
    (``"pass"``, ``"fail"``, ``"not_evaluable"``, ``"not_applicable"``).
    The gate evaluates checks in SPEC_GATE_ORDER. The decoder decides
    which non-passing statuses are blocking.

    ``not_evaluable`` maps to ``REQUIRED_GATE_STATE_UNAVAILABLE`` and
    outranks all ``"fail"`` results.
    """

    def __init__(
        self,
        check_map: dict[tuple[int, str], str] | None = None,
        *,
        default_status: str = "pass",
        rule_table_version: str = "1.0.0",
    ) -> None:
        self._check_map: dict[tuple[int, str], str] = {}
        if check_map is not None:
            self._check_map.update(check_map)
        self._default_status = default_status
        self.rule_table_version = rule_table_version
        self._eval_order: list[str] = []

    def status_for(self, candidate_index: int, check_name: str) -> str:
        return self._check_map.get(
            (candidate_index, check_name), self._default_status
        )

    def set_status(self, candidate_index: int, check_name: str, status: str) -> None:
        self._check_map[(candidate_index, check_name)] = status

    def evaluate(
        self,
        candidate_index: int,
        candidate: dict,
        state: object,
    ) -> tuple[EdgeValidityCheck, ...]:
        """Evaluate all 9 gate checks for one candidate in spec order.

        Returns a tuple of EdgeValidityCheck records (one per gate check).
        The decoder decides the primary failure from the returned checks.
        """
        self._eval_order = []
        results: list[EdgeValidityCheck] = []
        for check_name in SPEC_GATE_ORDER:
            self._eval_order.append(check_name)
            status = self.status_for(candidate_index, check_name)
            failure_code: Optional[str] = None
            observed = ""
            threshold = ""

            if status == "fail":
                failure_code = f"GATE_{check_name.upper()}_FAIL"
                observed = f"candidate_{candidate_index}_value"
                threshold = f"rule_threshold_for_{check_name}"
            elif status == "not_evaluable":
                failure_code = "REQUIRED_GATE_STATE_UNAVAILABLE"
                observed = "unavailable"
                threshold = "required_state_not_present"

            results.append(
                _make_edge_validity_check(
                    check_name=check_name,
                    status=status,
                    observed_value=observed,
                    threshold_or_rule=threshold,
                    failure_code=failure_code,
                    rule_table_version=self.rule_table_version,
                )
            )
        return tuple(results)

    @property
    def last_eval_order(self) -> list[str]:
        return list(self._eval_order)


class OrderRecordingGate(InjectableGate):
    """A gate that records the exact sequence of (candidate_index, check_name)
    evaluations while passing all checks.

    Use this to verify that decode_final_edge calls checks in the
    spec-defined order.
    """

    def __init__(self, rule_table_version: str = "1.0.0") -> None:
        super().__init__(default_status="pass", rule_table_version=rule_table_version)
        self.call_sequence: list[tuple[int, str]] = []

    def evaluate(
        self,
        candidate_index: int,
        candidate: dict,
        state: object,
    ) -> tuple[EdgeValidityCheck, ...]:
        results: list[EdgeValidityCheck] = []
        for check_name in SPEC_GATE_ORDER:
            self.call_sequence.append((candidate_index, check_name))
            results.append(
                _make_edge_validity_check(
                    check_name=check_name,
                    status="pass",
                    rule_table_version=self.rule_table_version,
                )
            )
        return tuple(results)


class FinalDecodeFixtureBuilder:
    """Builds test fixtures for final decode contract tests (Task 21).

    All outputs are pure Python objects; no torch, PMDM, PocketFlow, or RDKit.
    """

    def __init__(self, seed: int = 42) -> None:
        self._seed = seed

    # -- candidate builders ------------------------------------------------

    def build_candidates(
        self,
        scores: list[float],
        *,
        base_ligand_index: int = 0,
        ligand_id: str = "LIG",
        target_atom_name: str = "SG",
        target_residue_name: str = "CYS",
        target_residue_number: int = 145,
        target_chain_id: str = "A",
        bond_type: str = "carbon-sulfur",
    ) -> list[dict]:
        """Build a list of candidate records with the given scores.

        Scores are assigned in order; candidate 0 gets scores[0], etc.
        Ligand atom indices start from *base_ligand_index*.
        """
        candidates = []
        for i, score in enumerate(scores):
            candidates.append(
                build_candidate_record(
                    ligand_atom_name=f"C{i + 1}",
                    ligand_atom_index=base_ligand_index + i,
                    ligand_id=ligand_id,
                    target_atom_name=target_atom_name,
                    target_residue_name=target_residue_name,
                    target_residue_number=target_residue_number,
                    target_chain_id=target_chain_id,
                    bond_type=bond_type,
                    score=score,
                )
            )
        return candidates

    # -- gate builders -----------------------------------------------------

    def build_all_pass_gate(self) -> InjectableGate:
        """A gate where all 9 checks pass for every candidate."""
        return InjectableGate(default_status="pass")

    def build_all_fail_gate(
        self,
        fail_at_check: str = "target_atom",
    ) -> InjectableGate:
        """A gate where every candidate fails at the specified check.

        All checks before *fail_at_check* in gate order pass; the
        targeted check and all subsequent checks also fail.
        """
        gate = InjectableGate(default_status="fail")
        # Make checks before fail_at_check pass so the targeted check
        # is the first failure for each candidate.
        fail_index = SPEC_GATE_ORDER.index(fail_at_check)
        for check_name in SPEC_GATE_ORDER[:fail_index]:
            for ci in range(100):  # broad coverage
                gate.set_status(ci, check_name, "pass")
        return gate

    def build_gate_from_map(
        self,
        check_map: dict[tuple[int, str], str],
        default_status: str = "pass",
    ) -> InjectableGate:
        """Build a gate with explicit per-(candidate_index, check_name) statuses."""
        gate = InjectableGate(
            check_map=check_map, default_status=default_status
        )
        return gate

    def build_single_check_fail_gate(
        self,
        candidate_index: int,
        check_name: str,
    ) -> InjectableGate:
        """A gate where only one specific (candidate, check) fails;
        all others pass."""
        gate = InjectableGate(default_status="pass")
        gate.set_status(candidate_index, check_name, "fail")
        return gate

    def build_unavailable_gate(
        self,
        candidate_index: int,
        check_name: str = "target_atom",
    ) -> InjectableGate:
        """A gate where one candidate has REQUIRED_GATE_STATE_UNAVAILABLE
        at the specified check."""
        gate = InjectableGate(default_status="pass")
        gate.set_status(candidate_index, check_name, "not_evaluable")
        return gate

    def build_order_recording_gate(self) -> OrderRecordingGate:
        """A gate that records check evaluation order (all checks pass)."""
        return OrderRecordingGate()

    # -- final state builder -----------------------------------------------

    def build_final_ligand_state(
        self,
        candidates: list[dict],
        *,
        target_atom_name: str = "SG",
        target_residue_name: str = "CYS",
        target_residue_number: int = 145,
        target_chain_id: str = "A",
        bond_type_vocabulary: tuple[str, ...] = (
            "no_edge",
            "carbon-sulfur",
            "carbon-nitrogen",
            "carbon-oxygen",
            "disulfide",
            "phosphorus-oxygen",
        ),
    ) -> dict:
        """Build a dict representing the final ligand state at decode time.

        Returns a plain dict with candidate scores, identities, and
        target context so tests can call decode_final_edge without
        depending on the exact production FinalLigandState shape.
        """
        return {
            "candidates": copy.deepcopy(candidates),
            "candidate_scores": [c["score"] for c in candidates],
            "target_atom": {
                "chain_id": target_chain_id,
                "residue_number": target_residue_number,
                "residue_name": target_residue_name,
                "atom_name": target_atom_name,
            },
            "bond_type_vocabulary": list(bond_type_vocabulary),
        }

    # -- expected result builders ------------------------------------------

    @staticmethod
    def expected_valid_result(
        selected_ligand_atom_name: str = "C1",
        selected_ligand_atom_index: int = 0,
        selected_score: float = 0.9,
        bond_type: str = "carbon-sulfur",
        edge_validity_checks: tuple[EdgeValidityCheck, ...] = (),
        secondary_failure_reasons: tuple[str, ...] = (),
    ) -> dict:
        """Expected fields for a valid decode result."""
        return {
            "generation_validity_status": "valid",
            "selected_ligand_atom_name": selected_ligand_atom_name,
            "selected_ligand_atom_index": selected_ligand_atom_index,
            "selected_score": selected_score,
            "bond_type": bond_type,
            "primary_failure_reason": None,
            "secondary_failure_reasons": secondary_failure_reasons,
            "edge_validity_checks": edge_validity_checks,
        }

    @staticmethod
    def expected_invalid_result(
        primary_failure_reason: str,
        secondary_failure_reasons: tuple[str, ...] = (),
        edge_validity_checks: tuple[EdgeValidityCheck, ...] = (),
    ) -> dict:
        """Expected fields for an invalid decode result."""
        return {
            "generation_validity_status": "invalid",
            "selected_edge": None,
            "selected_score": None,
            "primary_failure_reason": primary_failure_reason,
            "secondary_failure_reasons": secondary_failure_reasons,
            "edge_validity_checks": edge_validity_checks,
        }
