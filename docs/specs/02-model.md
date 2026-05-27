# Spec: Model

## Objective

Build a PMDM-compatible fixed-protein ligand diffusion extension for de novo covalent inhibitor generation. The model keeps PMDM's pocket-conditioned ligand diffusion backbone and adds explicit reactive-site conditioning, residue-reaction-family conditioning, stepwise soft covalent cross-edge scoring, bond-type scoring, optional family auxiliary diagnostics, and a final hard covalent edge decode interface.

The model must support a single covalent attachment event and must not rewrite the project as a PocketFlow backbone.

## Tech Stack

- Python 3.9-compatible project-owned wrappers and adapters.
- PyTorch model components.
- PMDM as the baseline diffusion backbone.
- PocketFlow only as design inspiration for candidate-edge and local context supervision.

## Commands

```bash
python -m covalent_design.model.inspect_batch --records data/processed/covalent_complex_records/records.jsonl --record-id <record_id>
python -m covalent_design.model.forward_smoke --config configs/covalent_model_smoke.yml
python -m covalent_design.model.export_arch_summary --config configs/covalent_model_smoke.yml --out data/reports/model_arch_summary.md
python -m compileall -q scripts src
```

## Project Structure

```text
src/covalent_design/model/
  pmdm_adapter.py
  batch.py
  conditioning.py
  reactive_site_features.py
  family_conditioning.py
  candidate_builder.py
  covalent_heads.py
  edge_message_passing.py
  geometry_features.py
  final_decode.py
  validity_gate.py
  size_prior.py

configs/
  covalent_model_smoke.yml
  covalent_model_v1.yml
```

## Code Style

Separate learnable behavior from non-learnable constraints. Model code may expose rule masks and gate features, but it must not describe masked feasibility as learned chemistry.

```python
edge_logits = edge_head(candidate_features)
edge_prob = edge_logits.sigmoid()
message_weight = edge_prob.detach()
message_weight_source = "detached_edge_probability"
context = apply_soft_cross_edge_messages(context, candidates, message_weight)
```

Rules:

- Stepwise candidates are rebuilt from fixed protein coordinates and current noisy or generated ligand coordinates.
- The positive training edge is force-included when diffusion noise moves it outside the candidate radius.
- Force-included positives are counted separately and excluded from v1 soft edge message passing and geometry regression.
- Ground-truth edge labels are not used as training-time message weights, and any `ModelForwardOutput` using label/ground_truth/target_edge as `message_weight_source` is invalid.
- Final hard decoding can reject all candidates and return an invalid sample path.

## Testing Strategy

Unit tests should cover:

- Candidate construction at noisy timestep `t`.
- Forced-positive inclusion and denominator counts.
- No-edge negative labels and loss eligibility.
- Detached predicted probabilities for message passing.
- Covalent head tensor shapes for edge existence and bond type.
- Family conditioning uses `residue_reaction_family`.
- Ligand heavy-atom controls map to PMDM-style `num_atom`.
- Final validity gate can reject every candidate.

Tests should use tiny fixture records, not full raw corpora.

## Boundaries

Always:

- Keep protein coordinates fixed.
- Use `residue_reaction_family` as the primary condition.
- Emit at most one final covalent cross edge.
- Preserve distinction between matched warhead evidence and predicted warhead diagnostics.

Ask first:

- Editing upstream PMDM files directly.
- Adding scheduled sampling, non-detached edge-message gradients, or a new backbone.
- Enabling chemistry families outside the first-pass vocabulary.

Never:

- Predict the reactive residue as a model target in v1.
- Use a fixed ligand attachment slot.
- Do full complex diffusion.
- Repair an invalid generated ligand by post-hoc adding, deleting, or switching the covalent edge.
- Treat PocketFlow flow likelihood as part of the v1 model objective.

## Success Criteria

- A model smoke forward pass consumes a batch derived from accepted `CovalentComplexRecord` artifacts.
- Forward outputs include PMDM-compatible predictions plus covalent edge logits, bond-type logits, and denominator metadata.
- Stepwise candidates use current coordinate state and the 4.0 Angstrom candidate radius.
- Forced positives, natural candidates, message-passing candidates, and gate-evaluated candidates are counted separately.
- Final decode selects the highest-scoring candidate that passes the rule gate or records a valid invalid-sample failure path.

## Open Questions

Resolved (2026-05-26 contract freeze, see ADR 0035):

- **Bond-type vocabulary:** Dynamically discovered from `core_labels.bond_type` across records + `"no_edge"` at index 0. Stored in `BatchSpec.bond_type_vocabulary`. ~6 positive classes + no_edge for v1.
- **Family auxiliary head:** Included in v1. `family_logits` is a required `ModelForwardOutput` field; `family_aux_loss` is a required `LossReport` component.
- **PMDM integration:** Adapter pattern with explicit output key vocabulary (9 keys: 7 required + 2 optional). Fake backbone for smoke tests. See `interface-design.md` PMDM Adapter Output Keys.
- **Task 17 input bundle:** Consumes a single finalized Task 13 `records.jsonl` (five artifact roles per record). Task 17 does NOT check Data Release Gate, split assignment, quality-tier eligibility, or visual check status. ``make_model_batch()`` creates no artifacts on disk (no side effects).
- **Target atom sourcing:** ``BatchRecordHeader.target_atom_identity`` is resolved from ``protein_atom_table`` artifact (chain_id, residue_number, residue_name); ``target_atom_index`` comes from ``core_labels.target_atom_index``; ``target_atom_artifact_role`` is constant ``"protein_atom_table"``.
- **Static edge candidates:** Task 17 validates existence and checksum and records them in ``static_edge_candidates_refs`` (``record_id → ArtifactRef`` mapping). Per-edge contents (positive label identity, bond type) are consumed later by Task 18, not by ``make_model_batch()`` itself.

Still open for v1:

- How should final edge-score thresholds be calibrated?
- Does size prior remain PMDM-style, or become family-conditioned in v1?
