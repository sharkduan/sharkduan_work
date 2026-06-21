# V2 Training And Tuning Spec

Date: 2026-06-16
Status: hardened planning spec

## Dataset Input

Training consumes v1-compatible finalized records plus split index, visual checks, quality report, family readiness report, and license audit references. It must not train on records blocked by license, family readiness, visual status, quality policy, or split policy.

## Model Input

Training reuses:

- `ModelBatch`
- stepwise candidates
- PMDM adapter output vocabulary
- covalent heads
- final decode diagnostics

PyTorch tensor adapters may sit behind these contracts, but public contract objects stay serializable.

### PMDM Adapter Output Vocabulary

Task 47 freezes the real-PMDM adapter smoke vocabulary without executing PMDM while its license remains unknown. The seven required keys are:

- `ligand_atom_features`
- `protein_atom_features`
- `ligand_coords_denoised`
- `position_loss`
- `atom_type_loss`
- `timestep`
- `num_atom`

The two optional keys are `ligand_pair_features` and `protein_ligand_pair_features`. They are present only when the corresponding `ModelConfig` feature dimensions are positive, and absent when those dimensions are zero.

When PMDM is blocked by `license_unknown`, PMDM-mode execution records structured unavailability with `status: unavailable`, `reason: license_unknown`, and `import_attempted: false`. It must not silently switch to `non_pmdm_baseline`.

## Training Objective

V2-beta objective remains aligned with v1:

- PMDM position loss,
- PMDM atom loss,
- covalent edge loss,
- covalent bond type loss,
- covalent geometry loss,
- family auxiliary loss.

Real numerical loss implementation may replace smoke pseudo-losses only after Task 46-50 validate tensor and PMDM seams.

## Loss Functions

The first real loss implementation must:

- preserve v1 `LossReport` required components,
- preserve mask and denominator accounting,
- keep forced-positive behavior auditable,
- reject denominator drift.

## Checkpoint Policy

Checkpoint metadata must include:

- environment manifest hash,
- dependency lock hash,
- source/data manifest hashes,
- family readiness hash,
- training config hash,
- rule table hash,
- model contract version,
- baseline mode (`pmdm` or `non_pmdm_baseline`).

## Hyperparameter Search

The first search is tiny and budget-controlled:

- fixed trial count,
- fixed random seeds,
- fixed split,
- explicit budget,
- deterministic trial manifests,
- selected checkpoint justification.

## Training Manifest

Every run records:

- run id,
- start/end time,
- environment hash,
- data hash,
- checkpoint refs,
- metrics,
- failure diagnostics,
- whether PMDM or fallback was used,
- PMDM status details when PMDM is unavailable (`status`, `reason`, and `import_attempted`),
- explicit `baseline_mode` when the Task 48 baseline is selected.

## Runtime Budget

The beta budget is intentionally small. Exact limits are set in Task 52, but the plan must support CPU smoke, single-GPU smoke, and small full run modes.

## Smoke And Full Modes

- CPU smoke: proves tensor path and losses without GPU.
- GPU smoke: proves CUDA availability and one forward/backward path.
- Full beta run: small training budget over ready families.

## Verification Commands

Planned commands:

```bash
python -m covalent_design.training.cli.v2_train --config configs/v2_train_cpu_smoke.yml
python -m covalent_design.training.cli.v2_train --config configs/v2_train_gpu_smoke.yml
python -m covalent_design.training.cli.v2_tune --config configs/v2_tiny_sweep.yml
```

Exact commands are finalized by future tasks, but public CLIs should be package module entrypoints. Developer scripts may wrap these commands only as local helpers.
