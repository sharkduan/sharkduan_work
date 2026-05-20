# Spec: Training

## Objective

Train the PMDM-compatible covalent generator on accepted monodentate records using the v1 loss stack: PMDM position loss, PMDM atom-type loss, covalent edge existence loss, covalent bond-type loss, local covalent geometry loss where calibrated, and reaction-family consistency through explicit rule masks and gates. A residue-reaction-family auxiliary head is optional diagnostic evidence only.

Training must expose mask and denominator behavior rather than hiding missing rule state, pending geometry, or force-included positives.

## Tech Stack

- Python 3.9-compatible project-owned training wrappers.
- PyTorch training loops and checkpointing.
- PMDM configuration patterns where practical.
- Lightweight CI remains compile/hygiene focused; training smoke tests use small fixtures.

## Commands

```bash
python -m covalent_design.training.prepare_dataset --records data/processed/covalent_complex_records/records.jsonl --split scaffold
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

## Success Criteria

- A smoke training run completes on a small accepted-record fixture.
- Training logs include all PMDM and covalent loss components.
- Denominator reports include candidate, natural, forced-positive, eligible, masked, edge loss, bond-type loss, geometry loss, message-passing, and gate-evaluated counts.
- Counts are stratified by family and timestep bucket.
- Missing or pending rule state is counted and masked according to the model design contract.
- Q2 keep-with-flag records are present only through the accepted-core path and are stratified in training and validation reports.
- Validation can run on random, protein-cluster, and scaffold splits.

## Open Questions

- What are the initial loss weights for edge, bond type, and geometry?
- How should edge class imbalance be handled?
- What timestep bucket definitions are used in reports?
- What minimum fixture size is enough for a smoke epoch?
- Which experiment tracking format should be used before full workflow tooling exists?
