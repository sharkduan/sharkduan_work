"""Final decode: select the highest-scoring valid covalent edge (Task 21).

Public API::

    decode_final_edge(final_state, gate) -> FinalDecodeResult

See interface-design.md Failure Reason Priority for the authoritative
gate check order.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from covalent_design.contracts.types import (
    CovalentEdge,
    EdgeValidityCheck,
    LigandAtomIdentity,
    ProteinAtomIdentity,
)

#: Gate evaluation order from interface-design.md Failure Reason Priority.
_SPEC_GATE_ORDER: tuple[str, ...] = (
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

_REQUIRED_GATE_STATE_UNAVAILABLE = "REQUIRED_GATE_STATE_UNAVAILABLE"

#: FinalLigandState is a dict carrying candidates, scores, and target context.
FinalLigandState = Dict[str, Any]


class FinalDecodeResult:
    """Result of hard-gate validity checking over all scored candidates.

    Attributes
    ----------
    generation_validity_status:
        ``"valid"`` when a candidate passed every gate check,
        ``"invalid"`` otherwise.
    selected_edge:
        The ``CovalentEdge`` of the selected candidate, or *None*.
    primary_failure_reason:
        *None* for valid results; for invalid results the first
        failure of the highest-scoring candidate.
    secondary_failure_reasons:
        Deduplicated failure codes from skipped higher-scored
        candidates, preserved for diagnostics.  Empty when no
        higher-scored candidates failed.
    edge_validity_checks:
        One ``EdgeValidityCheck`` per check per evaluated candidate.
    selected_score:
        The score of the selected candidate, or *None*.
    """

    __slots__ = (
        "generation_validity_status",
        "selected_edge",
        "primary_failure_reason",
        "secondary_failure_reasons",
        "edge_validity_checks",
        "selected_score",
    )

    def __init__(
        self,
        *,
        generation_validity_status: str,
        selected_edge: Optional[CovalentEdge] = None,
        primary_failure_reason: Optional[str] = None,
        secondary_failure_reasons: tuple[str, ...] = (),
        edge_validity_checks: tuple[EdgeValidityCheck, ...] = (),
        selected_score: Optional[float] = None,
    ) -> None:
        self.generation_validity_status = generation_validity_status
        self.selected_edge = selected_edge
        self.primary_failure_reason = primary_failure_reason
        self.secondary_failure_reasons = secondary_failure_reasons
        self.edge_validity_checks = edge_validity_checks
        self.selected_score = selected_score


def _build_covalent_edge(candidate: dict) -> CovalentEdge:
    """Build a ``CovalentEdge`` from a candidate record dict."""
    la = candidate["ligand_atom"]
    ta = candidate["target_atom"]
    return CovalentEdge(
        protein_atom=ProteinAtomIdentity(
            chain_id=ta.get("chain_id"),
            residue_number=ta.get("residue_number"),
            residue_name=ta["residue_name"],
            atom_name=ta["atom_name"],
        ),
        ligand_atom=LigandAtomIdentity(
            ligand_id=la.get("ligand_id", ""),
            atom_name=la.get("atom_name", ""),
            atom_index=la.get("atom_index"),
            chain_id=la.get("chain_id"),
        ),
        bond_type=candidate.get("bond_type", ""),
    )


def _first_failure(checks: tuple[EdgeValidityCheck, ...]) -> Optional[str]:
    """Return the failure_code of the first non-pass check, or *None*."""
    for c in checks:
        if c.status not in ("pass", "not_applicable"):
            return _failure_reason(c)
    return None


def _required_state_failure(
    checks: tuple[EdgeValidityCheck, ...],
) -> Optional[str]:
    """Return the required-state failure reason, if any check is unavailable."""
    for c in checks:
        if (
            c.status == "not_evaluable"
            or c.failure_code == _REQUIRED_GATE_STATE_UNAVAILABLE
        ):
            return f"{_REQUIRED_GATE_STATE_UNAVAILABLE}:{c.check_name}"
    return None


def _failure_reason(check: EdgeValidityCheck) -> str:
    if (
        check.status == "not_evaluable"
        or check.failure_code == _REQUIRED_GATE_STATE_UNAVAILABLE
    ):
        return f"{_REQUIRED_GATE_STATE_UNAVAILABLE}:{check.check_name}"
    return check.failure_code or f"GATE_{check.check_name.upper()}_FAIL"


def decode_final_edge(
    final_state: FinalLigandState,
    gate: Any,  # ValidityGate protocol: .evaluate(int, dict, Any) -> tuple[EdgeValidityCheck, ...]
) -> FinalDecodeResult:
    """Select the highest-scoring candidate that passes all gate checks.

    Candidates are sorted by score descending with deterministic
    tie-breaking (original list index).  The first candidate whose
    every gate check has status ``"pass"`` becomes the selected edge.

    When the top-scoring candidate fails and a lower-ranked candidate
    passes, the result is ``"valid"`` and ``secondary_failure_reasons``
    captures each skipped candidate's first failure.

    When every candidate fails the result is ``"invalid"`` and
    ``primary_failure_reason`` is the first failure of the
    highest-scoring candidate.
    """
    candidates: list = final_state.get("candidates", [])

    if not candidates:
        return FinalDecodeResult(
            generation_validity_status="invalid",
            primary_failure_reason="NO_COVALENT_EDGE_PREDICTED",
        )

    # Stable sort: descending score, then ascending original index.
    indexed: list[tuple[int, dict]] = list(enumerate(candidates))
    indexed.sort(key=lambda pair: (-_score(pair[1]), pair[0]))

    all_checks: list[EdgeValidityCheck] = []
    skipped_failures: list[str] = []
    seen_failures: set[str] = set()
    best_candidate_first_failure: Optional[str] = None
    blocking_required_state_failure: Optional[str] = None

    for rank, (orig_idx, candidate) in enumerate(indexed):
        checks = gate.evaluate(orig_idx, candidate, final_state)
        all_checks.extend(checks)

        required_state_failure = _required_state_failure(checks)
        if required_state_failure is not None:
            if blocking_required_state_failure is None:
                blocking_required_state_failure = required_state_failure

        if _all_pass(checks) and blocking_required_state_failure is None:
            return FinalDecodeResult(
                generation_validity_status="valid",
                selected_edge=_build_covalent_edge(candidate),
                secondary_failure_reasons=tuple(skipped_failures),
                edge_validity_checks=tuple(all_checks),
                selected_score=_score(candidate),
            )

        failure = required_state_failure or _first_failure(checks)
        if rank == 0:
            best_candidate_first_failure = failure

        if failure is not None and failure not in seen_failures:
            seen_failures.add(failure)
            skipped_failures.append(failure)

    return FinalDecodeResult(
        generation_validity_status="invalid",
        primary_failure_reason=(
            blocking_required_state_failure
            or best_candidate_first_failure
            or "NO_COVALENT_EDGE_PREDICTED"
        ),
        secondary_failure_reasons=tuple(skipped_failures),
        edge_validity_checks=tuple(all_checks),
    )


def _score(candidate: dict) -> float:
    return float(candidate.get("score", 0.0))


def _all_pass(checks: tuple[EdgeValidityCheck, ...]) -> bool:
    return all(c.status in ("pass", "not_applicable") for c in checks)
