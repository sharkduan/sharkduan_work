"""Task 23: Per-timestep mask audit computation."""

from __future__ import annotations

from dataclasses import dataclass

from covalent_design.contracts.types import MaskAudit, StepwiseCandidateSet


@dataclass(frozen=True)
class NormalizedMaskFlags:
    """Normalized rule and policy flags supplied to Task 23 mask projection."""

    pending_smarts: bool = False
    pending_geometry: bool = False
    missing_required_chemical_state: bool = False
    quality_tier: str = "Q1"
    exclude_q2: bool = False


def resolve_mask_flags(
    *,
    pending_smarts: bool = False,
    pending_geometry: bool = False,
    missing_required_chemical_state: bool = False,
    quality_tier: str = "Q1",
    exclude_q2: bool = False,
) -> NormalizedMaskFlags:
    """Own the explicit upstream-normalized inputs consumed by Task 23."""
    return NormalizedMaskFlags(
        pending_smarts=bool(pending_smarts),
        pending_geometry=bool(pending_geometry),
        missing_required_chemical_state=bool(missing_required_chemical_state),
        quality_tier=quality_tier,
        exclude_q2=bool(exclude_q2),
    )


def compute_mask_audit(
    candidate_set: StepwiseCandidateSet,
    *,
    pending_smarts: bool = False,
    pending_geometry: bool = False,
    missing_required_chemical_state: bool = False,
    quality_tier: str = "Q1",
    exclude_q2: bool = False,
) -> MaskAudit:
    tc = len(candidate_set.candidates)

    np = 0
    fp = 0
    nn = 0
    for c in candidate_set.candidates:
        if c.is_positive_label and not c.is_forced_positive:
            np += 1
        elif c.is_forced_positive:
            fp += 1
        elif not c.is_positive_label and c.within_radius:
            nn += 1

    if tc != np + fp + nn:
        raise ValueError(
            f"Malformed candidate set: TC={tc} != NP={np} + FP={fp} + NN={nn}"
        )

    zero_negative_count = 1 if nn == 0 else 0

    q2_excluded = exclude_q2 and quality_tier == "Q2"

    masked_by_pending_smarts = np if pending_smarts else 0
    masked_by_pending_geometry = np if pending_geometry else 0
    masked_by_missing_chemical_state = np if missing_required_chemical_state else 0
    masked_by_q2_exclusion = tc if q2_excluded else 0
    masked_by_forced_positive_exclusion = fp

    if q2_excluded:
        edge_loss_eligible_count = 0
        bond_type_loss_eligible_count = 0
        geometry_loss_eligible_count = 0
        message_passing_candidate_count = 0
        gate_evaluated_count = 0
    else:
        edge_loss_eligible_count = tc
        bond_type_loss_eligible_count = 0 if pending_smarts else np
        geometry_loss_eligible_count = (
            0 if (pending_geometry or missing_required_chemical_state) else np
        )
        message_passing_candidate_count = np + nn
        gate_evaluated_count = tc

    return MaskAudit(
        candidate_count=tc,
        natural_positive_count=np,
        forced_positive_count=fp,
        natural_negative_count=nn,
        zero_negative_count=zero_negative_count,
        masked_by_pending_smarts=masked_by_pending_smarts,
        masked_by_pending_geometry=masked_by_pending_geometry,
        masked_by_missing_chemical_state=masked_by_missing_chemical_state,
        masked_by_q2_exclusion=masked_by_q2_exclusion,
        masked_by_forced_positive_exclusion=masked_by_forced_positive_exclusion,
        edge_loss_eligible_count=edge_loss_eligible_count,
        bond_type_loss_eligible_count=bond_type_loss_eligible_count,
        geometry_loss_eligible_count=geometry_loss_eligible_count,
        message_passing_candidate_count=message_passing_candidate_count,
        gate_evaluated_count=gate_evaluated_count,
    )
