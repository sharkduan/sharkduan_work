# Task 24 Preflight Contract Stabilization

Date: 2026-06-01

## Scope

This patch stabilizes the Task 12 through Task 23 integration boundary before
Task 24 numeric losses or a smoke training loop are implemented. It does not
implement Task 24, Task 25, real PMDM integration, RDKit integration, or torch
integration.

## Contract Freeze Plan

1. Task 12 edge-candidate artifacts use additive local schema version `"2"`.
   Existing flat positive-edge fields remain readable; new readers use
   `ligand_atom_index`, full `target_atom` identity with `atom_index`, and
   `bond_type`.
2. Tasks 12, 17, and 18 use one shared protein-target resolver. Explicit
   index/serial locator plus identity cross-check is authoritative. Unique-name
   fallback is legacy-only and ambiguous fallback fails.
3. `EdgeDenominators` are strict conservation records. Edge loss counts all
   eligible candidates; bond-type and geometry denominators count natural
   positives only; message passing counts natural positives and natural
   negatives.
4. Task 18 exposes package-specific `StepwiseCandidateBatch`, a deterministic
   padded dynamic view. Task 20 consumes it when supplied and calls the
   message-weight guard on the actual forward path.
5. Task 22 singleton `batch-<zero-based-index>` loading delegates artifact
   validation and construction to Task 17 `make_model_batch()`.
6. Task 23 exposes `resolve_mask_flags()` as the explicit owner for normalized
   rule and policy booleans.
7. Task 24 future inputs are frozen as `ModelForwardOutput`, `ModelBatch`,
   dynamic `StepwiseCandidateBatch`, normalized mask flags, and `LossWeights`.

No architecture decision remained open for user confirmation during this
preflight patch.

## Resolved Findings

### P0

- Task 12 writer and Task 18 reader now interoperate without fixture rewriting.
- Duplicate target atom names no longer silently select the first row.
- Task 12, Task 18, and Task 23 denominator semantics agree.
- Task 22 has a working singleton loader seam through Task 17.
- Task 18 dynamic candidates now reach Task 20 shape and denominator handling.
- Task 20 production forward calls `apply_edge_message_weights()`.
- Task 23 normalized mask flags have an explicit owner.

### P1

- `LossReport.to_dict()` serializes each stratum `mask_audit`.
- `ModelBatch` preserves record `visual_check_status` provenance.
- Per-record edge denominators validate before aggregation.
- Shared denominator validation rejects under-accounting.
- Task 22 malformed split assignments, nested artifact refs, and malformed
  record objects return structured failures.
- Specs, ADR 0035, key decisions, and the verification matrix document the
  stabilized boundaries.
- `LossWeights` freezes six deterministic smoke defaults at `1.0`; calibration
  remains later workflow scope.

## Tracer Bullet

`tests.integration.test_task24_preflight.Task24TracerBulletTests` executes:

```text
Task 12 static edge artifact
  -> Task 13 finalized record reference
  -> Task 17 ModelBatch
  -> Task 18 StepwiseCandidateSet and StepwiseCandidateBatch
  -> Task 19 fake PMDM backbone
  -> Task 20 covalent heads and guarded detached message weights
  -> Task 23 normalized flags, MaskAudit, and strict EdgeDenominators
```

The tracer bullet intentionally stops before Task 24 numeric losses.

## Verification

Executed:

```powershell
$env:PYTHONPATH='src'
python -m unittest tests.integration.test_task24_preflight -v
python -m unittest discover -s tests -t . -q
python -m compileall -q scripts src
```

Results:

- Preflight integration: PASS, 15 tests.
- Full unittest suite: PASS, 921 tests.
- Python compileall: PASS.
- `git diff --check`: PASS with line-ending conversion warnings only.
- Package dependency scan: no cycles; the new `training -> model` dependency is
  the intentional Task 22 delegation to Task 17 `make_model_batch()`.
- Temporary singleton extraction scan: no `.training-batch-*.jsonl` files
  remain after tests.

## Final Self-Review

- P0 findings from the readiness review are resolved.
- P1 findings required before Task 24 are resolved.
- No Task 24 numeric loss function, training loop, CLI, checkpoint, or run
  manifest was implemented.
- No PMDM, PocketFlow, RDKit, torch, or heavy dependency was introduced.
- Existing untracked `docs/reviews/`, `prompts/`, training package, and training
  fixture trees remain unstaged. They require repository hygiene treatment by
  the maintainer before a commit.

## Deferred Work

- Implement Task 24 numeric loss computation and one-step fake-backbone smoke
  training only after this preflight patch is accepted.
- Replace smoke-only `LossWeights` defaults with calibrated values in a later
  workflow decision.
- Keep real PMDM, RDKit, and torch integration outside this stabilization patch.
