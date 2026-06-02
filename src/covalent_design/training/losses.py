"""Task 24: Deterministic smoke-loss computation.

Implements ``compute_losses`` with pure-Python pseudo BCE/CE losses.
No torch, RDKit, PMDM backbone, or PocketFlow dependency.
"""

from __future__ import annotations

import math
from covalent_design.contracts.types import (
    REQUIRED_LOSS_COMPONENT_KEYS,
    EdgeDenominators,
    LossReport,
    LossWeights,
    MaskAudit,
    ModelBatch,
    ModelForwardOutput,
)
from covalent_design.model.candidate_builder import StepwiseCandidateBatch
from covalent_design.training.denominators import (
    DenominatorStratumEntry,
    aggregate_denominator_strata,
    build_edge_denominators,
)
from covalent_design.training.masks import NormalizedMaskFlags, compute_mask_audit


# ---------------------------------------------------------------------------
# numeric helpers
# ---------------------------------------------------------------------------


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def _softmax(logits: list[float]) -> list[float]:
    max_logit = max(logits)
    exps = [math.exp(x - max_logit) for x in logits]
    total = sum(exps)
    return [e / total for e in exps]


def _bce_with_logits(logit: float, label: float) -> float:
    """Numerically stable binary cross-entropy with logits."""
    if logit >= 0.0:
        return math.log1p(math.exp(-logit)) + (1.0 - label) * logit
    else:
        return math.log1p(math.exp(logit)) - label * logit


def _cross_entropy(logits: list[float], target_index: int) -> float:
    probs = _softmax(logits)
    return -math.log(max(probs[target_index], 1e-12))


def _sum_denominators(denom_list: list[EdgeDenominators]) -> EdgeDenominators:
    if not denom_list:
        return EdgeDenominators(
            candidate_count=0,
            natural_candidate_count=0,
            forced_positive_count=0,
            eligible_edge_count=0,
            masked_candidate_count=0,
            edge_loss_denominator=0,
            bond_type_loss_denominator=0,
            geometry_loss_denominator=0,
            message_passing_candidate_count=0,
            gate_evaluated_count=0,
        )
    total = EdgeDenominators(
        candidate_count=sum(d.candidate_count for d in denom_list),
        natural_candidate_count=sum(d.natural_candidate_count for d in denom_list),
        forced_positive_count=sum(d.forced_positive_count for d in denom_list),
        eligible_edge_count=sum(d.eligible_edge_count for d in denom_list),
        masked_candidate_count=sum(d.masked_candidate_count for d in denom_list),
        edge_loss_denominator=sum(d.edge_loss_denominator for d in denom_list),
        bond_type_loss_denominator=sum(d.bond_type_loss_denominator for d in denom_list),
        geometry_loss_denominator=sum(d.geometry_loss_denominator for d in denom_list),
        message_passing_candidate_count=sum(d.message_passing_candidate_count for d in denom_list),
        gate_evaluated_count=sum(d.gate_evaluated_count for d in denom_list),
    )
    total.validate()
    return total


def _sum_mask_audits(audits: list[MaskAudit]) -> MaskAudit:
    if not audits:
        return MaskAudit(
            candidate_count=0,
            natural_positive_count=0,
            forced_positive_count=0,
            natural_negative_count=0,
            zero_negative_count=0,
            masked_by_pending_smarts=0,
            masked_by_pending_geometry=0,
            masked_by_missing_chemical_state=0,
            masked_by_q2_exclusion=0,
            masked_by_forced_positive_exclusion=0,
            edge_loss_eligible_count=0,
            bond_type_loss_eligible_count=0,
            geometry_loss_eligible_count=0,
            message_passing_candidate_count=0,
            gate_evaluated_count=0,
        )
    return MaskAudit(
        candidate_count=sum(a.candidate_count for a in audits),
        natural_positive_count=sum(a.natural_positive_count for a in audits),
        forced_positive_count=sum(a.forced_positive_count for a in audits),
        natural_negative_count=sum(a.natural_negative_count for a in audits),
        zero_negative_count=sum(a.zero_negative_count for a in audits),
        masked_by_pending_smarts=sum(a.masked_by_pending_smarts for a in audits),
        masked_by_pending_geometry=sum(a.masked_by_pending_geometry for a in audits),
        masked_by_missing_chemical_state=sum(a.masked_by_missing_chemical_state for a in audits),
        masked_by_q2_exclusion=sum(a.masked_by_q2_exclusion for a in audits),
        masked_by_forced_positive_exclusion=sum(a.masked_by_forced_positive_exclusion for a in audits),
        edge_loss_eligible_count=sum(a.edge_loss_eligible_count for a in audits),
        bond_type_loss_eligible_count=sum(a.bond_type_loss_eligible_count for a in audits),
        geometry_loss_eligible_count=sum(a.geometry_loss_eligible_count for a in audits),
        message_passing_candidate_count=sum(a.message_passing_candidate_count for a in audits),
        gate_evaluated_count=sum(a.gate_evaluated_count for a in audits),
    )


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------


def compute_losses(
    output: ModelForwardOutput,
    *,
    model_batch: ModelBatch,
    stepwise_candidate_batch: StepwiseCandidateBatch,
    mask_flags: tuple[NormalizedMaskFlags, ...],
    weights: LossWeights = LossWeights(),
) -> LossReport:
    """Compute all six required loss components from one forward output.

    Keyword-only parameters
    -----------------------
    output : ModelForwardOutput
        Task 20 forward output carrying edge/bond-type/family logits.
    model_batch : ModelBatch
        Provides per-record provenance and bond-type vocabulary.
    stepwise_candidate_batch : StepwiseCandidateBatch
        Dynamic per-timestep candidate sets with labels.
    mask_flags : NormalizedMaskFlags
        Resolved rule and policy flags that determine eligible counts.
    weights : LossWeights, optional
        Smoke defaults to ``LossWeights()`` (all 1.0).

    Returns
    -------
    LossReport
        Structured loss report with all six components, weighted total,
        aggregated denominators, mask audit, and strata.
    """
    B = len(model_batch.records)
    if len(stepwise_candidate_batch.candidate_sets) != B:
        raise ValueError("stepwise_candidate_batch must align with model_batch records")
    if len(mask_flags) != B:
        raise ValueError("mask_flags must align with model_batch records")

    # -- PMDM losses direct from fake backbone -------------------------------
    pmdm_position_loss = float(output.pmdm_outputs["position_loss"])
    pmdm_atom_loss = float(output.pmdm_outputs["atom_type_loss"])

    # -- per-record family index ---------------------------------------------
    family_set = sorted({rec.residue_reaction_family for rec in model_batch.records})
    family_to_idx = {fam: i for i, fam in enumerate(family_set)}

    # -- accumulators --------------------------------------------------------
    edge_loss_sum = 0.0
    edge_loss_count = 0

    bond_type_loss_sum = 0.0
    bond_type_loss_count = 0

    family_loss_sum = 0.0
    family_loss_count = 0

    strata_entries: list[DenominatorStratumEntry] = []
    per_record_denoms: list[EdgeDenominators] = []
    per_record_audits: list[MaskAudit] = []

    vocab = list(model_batch.batch_spec.bond_type_vocabulary) if model_batch.batch_spec else ["no_edge"]

    for b in range(B):
        record = model_batch.records[b]
        candidate_set = stepwise_candidate_batch.candidate_sets[b]

        record_flags = mask_flags[b]
        audit = compute_mask_audit(
            candidate_set,
            pending_smarts=record_flags.pending_smarts,
            pending_geometry=record_flags.pending_geometry,
            missing_required_chemical_state=record_flags.missing_required_chemical_state,
            quality_tier=record_flags.quality_tier,
            exclude_q2=record_flags.exclude_q2,
        )
        denom = build_edge_denominators(audit)

        per_record_audits.append(audit)
        per_record_denoms.append(denom)

        strata_entries.append(
            DenominatorStratumEntry(
                residue_reaction_family=record.residue_reaction_family,
                timestep_value=candidate_set.timestep_value,
                mask_audit=audit,
            )
        )

        edge_logits_row = output.edge_logits.data[b]
        bond_type_logits_row = output.bond_type_logits.data[b]
        family_logits_row = output.family_logits.data[b]
        candidate_count = len(candidate_set.candidates)
        if len(edge_logits_row) < candidate_count:
            raise ValueError("edge_logits row is shorter than the dynamic candidate set")
        if len(bond_type_logits_row) < candidate_count:
            raise ValueError(
                "bond_type_logits row is shorter than the dynamic candidate set"
            )

        # -- edge BCE ----------------------------------------------------
        eligible_edge = audit.edge_loss_eligible_count
        if eligible_edge > 0:
            for c_idx, cand in enumerate(candidate_set.candidates):
                logit = float(edge_logits_row[c_idx])
                label = 1.0 if cand.is_positive_label else 0.0
                edge_loss_sum += _bce_with_logits(logit, label)
            edge_loss_count += eligible_edge

        # -- bond-type CE -------------------------------------------------
        bond_eligible = audit.bond_type_loss_eligible_count
        if bond_eligible > 0:
            bond_type = candidate_set.positive_label_bond_type
            target_idx = vocab.index(bond_type) if bond_type in vocab else 0
            for c_idx, cand in enumerate(candidate_set.candidates):
                if cand.is_positive_label and not cand.is_forced_positive:
                    logits = [float(v) for v in bond_type_logits_row[c_idx]]
                    bond_type_loss_sum += _cross_entropy(logits, target_idx)
            bond_type_loss_count += bond_eligible

        # -- family aux CE ------------------------------------------------
        target_fam_idx = family_to_idx.get(record.residue_reaction_family, 0)
        fam_logits = [float(v) for v in family_logits_row]
        family_loss_sum += _cross_entropy(fam_logits, target_fam_idx)
        family_loss_count += 1

    # -- normalise -----------------------------------------------------------
    edge_loss = edge_loss_sum / max(edge_loss_count, 1)
    bond_loss = bond_type_loss_sum / max(bond_type_loss_count, 1)
    family_loss = family_loss_sum / max(family_loss_count, 1)
    geometry_loss = 0.0  # explicit sentinel

    # -- aggregate across records --------------------------------------------
    total_denom = _sum_denominators(per_record_denoms)
    total_audit = _sum_mask_audits(per_record_audits)
    strata = aggregate_denominator_strata(strata_entries)

    components = {
        "pmdm_position_loss": pmdm_position_loss,
        "pmdm_atom_loss": pmdm_atom_loss,
        "covalent_edge_loss": edge_loss,
        "covalent_bond_type_loss": bond_loss,
        "covalent_geometry_loss": geometry_loss,
        "family_aux_loss": family_loss,
    }

    total_loss = (
        weights.pmdm_position_loss * pmdm_position_loss
        + weights.pmdm_atom_loss * pmdm_atom_loss
        + weights.covalent_edge_loss * edge_loss
        + weights.covalent_bond_type_loss * bond_loss
        + weights.covalent_geometry_loss * geometry_loss
        + weights.family_aux_loss * family_loss
    )

    return LossReport(
        total_loss=total_loss,
        components=components,
        denominators=total_denom,
        mask_audit=total_audit,
        strata=strata,
    )
