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
context = apply_soft_cross_edge_messages(context, candidates, message_weight)
```

Rules:

- Stepwise candidates are rebuilt from fixed protein coordinates and current noisy or generated ligand coordinates.
- The positive training edge is force-included when diffusion noise moves it outside the candidate radius.
- Force-included positives are counted separately and excluded from v1 soft edge message passing and geometry regression.
- Ground-truth edge labels are not used as training-time message weights.
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

- Should the PMDM integration be a pure adapter, a shallow subclass, or a small fork with explicit patch boundaries?
- What exact bond-type vocabulary should be exposed by the covalent bond head?
- Is the optional family auxiliary head included in v1 or reserved for diagnostics after the first training run?
- How should final edge-score thresholds be calibrated?
- Does size prior remain PMDM-style, or become family-conditioned in v1?
