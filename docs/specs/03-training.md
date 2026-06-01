# Spec: Training

## Objective

Train the PMDM-compatible covalent generator on accepted monodentate records using the v1 loss stack: PMDM position loss, PMDM atom-type loss, covalent edge existence loss, covalent bond-type loss, local covalent geometry loss where calibrated, and reaction-family consistency through explicit rule masks and gates. The residue-reaction-family auxiliary head is required in v1 and remains diagnostic rather than authoritative.

Training must expose mask and denominator behavior rather than hiding missing rule state, pending geometry, or force-included positives.

## Tech Stack

- Python 3.9-compatible project-owned training wrappers.
- PyTorch training loops and checkpointing.
- PMDM configuration patterns where practical.
- Lightweight CI remains compile/hygiene focused; training smoke tests use small fixtures.

## Commands

```bash
# Task 22 currently exposes a Python API:
# prepare_dataset(records_path, split_index_path, split_name, policy=None)
python -m covalent_design.training.train --config configs/covalent_train_smoke.yml
python -m covalent_design.training.validate_epoch --checkpoint outputs/checkpoints/latest.pt --split val
python -m covalent_design.training.report_denominators --run outputs/runs/<run_id>
python -m compileall -q scripts src
```

## Project Structure

```text
src/covalent_design/training/
  dataset.py
  batch.py
  sampler.py
  masks.py
  losses.py
  denominators.py
  train_loop.py
  validation_loop.py
  checkpoints.py
  reports.py

configs/
  covalent_train_smoke.yml
  covalent_train_v1.yml
```

Generated run outputs must stay ignored by git.

## Code Style

Loss code returns structured dictionaries with named loss values, mask sources, and denominators.

```python
losses = {
    "pmdm_position_loss": position_loss,
    "pmdm_atom_loss": atom_loss,
    "covalent_edge_loss": edge_loss,
    "covalent_bond_type_loss": bond_type_loss,
    "covalent_geometry_loss": geometry_loss,
    "denominators": denominators.to_dict(),
}
```

Rules:

- Every mask source is inspectable.
- Reports are stratified by `residue_reaction_family` and timestep bucket.
- Pending SMARTS, pending geometry, missing required protein state, and forced positives have explicit denominator behavior.
- No-edge negatives train edge existence and optional contrast only; they do not receive true bond or angle regression targets.
- Q2 keep-with-flag records are eligible for v1 training only when they otherwise pass accepted-core gates. Their quality flags must be preserved in the batch and reported separately so sensitivity analyses can compare all accepted records against Q2-excluded subsets.

## Testing Strategy

Training tests should use tiny fixtures covering:

- Natural positive candidate.
- Force-included positive candidate.
- Zero-negative `empty_radius_window`.
- Pending geometry.
- Pending SMARTS.
- Missing required protein chemical state.
- Q0/Q1 rejected records absent from training.
- Q2 keep-with-flag records included with quality-flag reporting.
- Scaffold/protein split isolation.

Verification checks:

- Denominator conservation for each fixture.
- Geometry denominator excludes force-included positives by default.
- Bond-type denominator excludes no-edge negatives and force-included positives by default.
- Edge loss denominator includes eligible positives and negatives.
- One smoke training step completes on fixture data.

## Boundaries

Always:

- Train on accepted monodentate records only.
- Use protein-cluster and scaffold splits as primary generalization evidence.
- Keep loss masks and denominators in the training report.

Ask first:

- Adding affinity, docking, QED, SA, logP, toxicity, selectivity, or ADMET objectives.
- Enabling mixed precision, DDP, scheduled sampling, or non-detached edge message gradients as release criteria.
- Changing first-pass quality inclusion rules.

Never:

- Train on unresolved conflicts or multi-linkage records.
- Treat random split as the only reported evaluation split.
- Regress covalent geometry on no-edge negatives as if they had true covalent bond geometry.
- Use rule gates to silently relabel or repair training labels.

Task 22 (dataset preparation and batch-loader boundary):

- ``prepare_dataset()`` builds exactly one split-specific dataset per call from ``records.jsonl`` and ``split_index.json``. Valid ``split_name`` values: ``"train"``, ``"val"``, ``"test"``.
- Default ``TrainingDataPolicy``: ``first_core_only=True``, ``exclude_visual_blocked=True``, ``exclude_q2=False``, ``accepted_quality_tiers=("Q0", "Q1", "Q2")``.
- Q2 is kept by default and excluded only when ``exclude_q2=True``.
- Visual statuses other than ``"pass"`` are excluded by default.
- ``load_training_batch(dataset, batch_id, *, batch_spec=None)`` implements deterministic singleton batches named ``batch-<zero-based-index>`` over sorted dataset entries. It delegates construction and artifact validation to Task 17 ``make_model_batch()`` and removes its temporary same-directory JSONL extraction before returning.
- Task 22 does **not** compute Task 23 masks, Task 23 denominators, Task 24 losses, run model forward, run a training loop, or generate model/training/inference/evaluation artifacts.

Task 23 (loss masks and denominator reports):

**Public API:**

```python
from covalent_design.training.masks import compute_mask_audit
from covalent_design.training.denominators import (
    DenominatorStratumEntry,
    aggregate_denominator_strata,
    build_edge_denominators,
    classify_timestep_bucket,
)
```

``resolve_mask_flags(...) -> NormalizedMaskFlags`` owns the explicit
upstream-normalized rule/policy booleans consumed by Task 23.

``compute_mask_audit(candidate_set, *, pending_smarts=False, pending_geometry=False, missing_required_chemical_state=False, quality_tier="Q1", exclude_q2=False) -> MaskAudit`` decomposes a per-timestep ``StepwiseCandidateSet`` into the 15-field ``MaskAudit``. Task 23 does not resolve rule-table rows.

``build_edge_denominators(mask_audit: MaskAudit) -> EdgeDenominators`` projects a ``MaskAudit`` into the 10-field ``EdgeDenominators`` used by losses.

``classify_timestep_bucket(timestep_value: float) -> str`` maps continuous timesteps to ``"early"`` (t ∈ [0.8, 1.0]), ``"mid"`` (t ∈ [0.3, 0.8)), or ``"late"`` (t ∈ [0.0, 0.3)). Raises ``ValueError`` for out-of-range or non-finite values.

``aggregate_denominator_strata(entries: Iterable[DenominatorStratumEntry]) -> tuple[DenominatorsStratum, ...]`` groups entries by ``(residue_reaction_family, timestep_bucket)``, sums all 15 ``MaskAudit`` fields element-wise, derives ``EdgeDenominators`` per group, and returns tuples sorted by family name alphabetical then early/mid/late.

``DenominatorStratumEntry`` is a package-specific frozen dataclass with fields ``residue_reaction_family: str``, ``timestep_value: float``, ``mask_audit: MaskAudit``.

**Mask audit semantics:**

```text
TC = candidate_count          NP = natural_positive_count
FP = forced_positive_count    NN = natural_negative_count
TC == NP + FP + NN            zero_negative_count = 1 iff NN == 0 (valid, not error)
```

Mask reason counts are independent and may overlap:
- ``masked_by_pending_smarts = NP`` when ``pending_smarts=True`` (masks bond target only)
- ``masked_by_pending_geometry = NP`` when ``pending_geometry=True`` (masks geometry target only)
- ``masked_by_missing_chemical_state = NP`` when ``missing_required_chemical_state=True`` (masks geometry targets for NP)
- ``masked_by_q2_exclusion = TC`` when ``exclude_q2=True and quality_tier == "Q2"`` (masks all TC)
- ``masked_by_forced_positive_exclusion = FP`` (always)

Eligible counts when Q2 is not excluded: edge_loss = TC, bond_type_loss = 0 if pending_smarts else NP, geometry_loss = 0 if pending_geometry or missing_required_chemical_state else NP, message_passing = NP + NN, gate_evaluated = TC. All five are zero when Q2 is excluded.

Participation: natural negatives → edge existence + message passing only (never true bond or geometry targets); forced positives → edge existence + gate only; pending SMARTS → masks bond target only; pending geometry → masks geometry target only; ``empty_radius_window=True`` is valid.

**Denominator projection:** Candidate count = TC, natural candidate count = NP + NN, forced positive count = FP, eligible edge count = edge_loss_eligible, masked candidate count = TC - edge_loss_eligible. Loss/message/gate denominator fields copy the matching eligible counts from the ``MaskAudit``.

**Task 23 does NOT** compute numeric losses, run model forward, run a training loop, resolve rule-table rows, generate checkpoints or run manifests, introduce RDKit or torch, or change ``LossReport`` serialization.

## Success Criteria

- A smoke training run completes on a small accepted-record fixture.
- Training logs include all PMDM and covalent loss components.
- Denominator reports include candidate, natural, forced-positive, eligible, masked, edge loss, bond-type loss, geometry loss, message-passing, and gate-evaluated counts.
- Counts are stratified by family and timestep bucket.
- Missing or pending rule state is counted and masked according to the model design contract.
- Q2 keep-with-flag records are present only through the accepted-core path and are stratified in training and validation reports.
- Validation can run on random, protein-cluster, and scaffold splits.

## Open Questions

Resolved (2026-05-26 contract freeze, see ADR 0035, ADR 0036):

- **Loss components:** All 6 components required in v1 (pmdm_position_loss, pmdm_atom_loss, covalent_edge_loss, covalent_bond_type_loss, covalent_geometry_loss, family_aux_loss). family_aux_loss is NOT optional.
- **Forced-positive participation:** edge_existence_loss yes; bond_type_loss no; geometry_loss no; message_passing no; gate yes. See `interface-design.md` Forced-Positive Loss Participation table.
- **Pending SMARTS + geometry interaction:** edge_existence_loss unaffected; bond_type masked by SMARTS; geometry masked by geometry. See `interface-design.md` Pending Interaction.
- **Timestep buckets:** `early` [0.8, 1.0], `mid` [0.3, 0.8), `late` [0.0, 0.3).
- **Smoke training config:** `covalent_train_smoke.yml` with `fake_backbone: true`, `steps: 1`, `batch_size: 4`. See `implementation-plan.md` Task 24.
- **Loss weights smoke defaults:** `LossWeights` freezes all six v1 component
  weights to `1.0` for Task 24 smoke integration. Calibration remains later
  workflow work.
- **Hash computation:** Config → canonical JSON → SHA-256; Record bundle → SHA-256 of records.jsonl; Split → SHA-256 of split_index.json. See ADR 0035.
- **Message-weight leakage:** Runtime `requires_grad` check in `ModelForwardOutput.__post_init__`, plus Task 20 provenance tests proving message weights come from detached model predictions rather than labels. See ADR 0036.

Still open for v1:

- What calibrated loss weights should replace the smoke-only `LossWeights`
  defaults for non-smoke training?
- How should edge class imbalance be handled?
- What minimum fixture size is enough for a smoke epoch?
- Which experiment tracking format should be used before full workflow tooling exists?
