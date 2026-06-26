# Task 51 V2 Manifest Review

## Summary

Overall Status: PASS

Task 51 implements a schema-only V2 checkpoint/experiment manifest boundary and preserves the approved lazy public facade. The manifest binds environment, dependency-lock provenance, data eligibility, family readiness, training config, training summary, checkpoint metadata references, and model-path status without creating checkpoint payloads or starting Task 52 tuning.

Task 52 may start after controller confirmation. No P0/P1 blockers remain.

## Files Changed

- `src/covalent_design/training/v2_manifests.py`: Added `V2CheckpointExperimentManifest`, `V2DependencyLockProvenance`, `V2CheckpointRef`, deterministic hash/serialization helpers, builder, validation, and structured `V2_MANIFEST_*` failures.
- `src/covalent_design/training/__init__.py`: Added lazy facade exports for the Task 51 manifest API while keeping public names available without package import side effects.
- `tests/training/test_v2_manifests.py`: Added manifest schema, deterministic hash, missing provenance, dependency-lock, baseline/PMDM mismatch, lazy facade, import-side-effect, and no-weight/no-Task52 boundary tests.
- `tests/fixtures/training/v2_manifests/manifest_input.json`: Added schema-only fixture input for deterministic manifest hashing.
- `docs/v2/06-v2-training-and-tuning-spec.md`: Documented Task 51 manifest contract and dependency-lock provenance behavior.
- `docs/v2/09-v2-interface-and-contract-changes.md`: Documented `V2CheckpointExperimentManifest` public API, fields, validation, and serialization.
- `docs/v2/10-v2-implementation-plan.md`: Marked Task 51 implementation and acceptance details.
- `docs/v2/11-v2-verification-matrix.md`: Added Task 51 verification evidence and boundary checks.
- `docs/v2/12-v2-risk-register.md`: Added/updated risks for non-PMDM baseline manifest preservation and dependency-lock provenance.

Note: `docs/reviews/task51-window-c-v2-manifests-plan-2026-06-22.md` was created by a Claude Code implementation-planning window during its Plan Mode pass. That violated the Plan Mode no-write rule, so the controller took over implementation and verification. The file was left in place and not deleted.

## Manifest Schema Evidence

`V2CheckpointExperimentManifest` records:

- `environment_hash`
- `dependency_lock`
- `data_hashes`
- `dataset_index_hash`
- `family_readiness_hash`
- `training_config_hash`
- `training_summary_hash`
- `training_summary_ref`
- `checkpoint_refs`
- `baseline_mode`
- `is_pmdm`
- `pmdm_status`

The public builder is `build_v2_checkpoint_experiment_manifest(...) -> ContractEnvelope[V2CheckpointExperimentManifest]`.

## Deterministic Hash Evidence

`serialize_v2_checkpoint_experiment_manifest()` uses canonical JSON with sorted keys and compact separators. `hash_v2_checkpoint_experiment_manifest()` returns `sha256:<64 lowercase hex>`.

Tests verify repeated builds serialize and hash identically.

## Required Provenance Evidence

Validation requires environment hash, dependency-lock provenance, all required data hashes, Task 49 dataset index hash, family readiness hash, training config hash, training summary hash/ref, and checkpoint refs.

Required data hash keys:

- `records_jsonl`
- `split_index`
- `quality_report`
- `visual_check_index`
- `license_gate_report`

## Missing Provenance Failure Evidence

Missing or malformed provenance returns structured `V2_MANIFEST_*` errors with `owner="training"`.

Covered failure classes include missing environment, missing data hash, missing dataset index hash, missing family readiness hash, missing training config hash, missing training summary hash/ref, missing checkpoint refs, unsupported baseline mode, unsupported dependency-lock status, and invalid hash format.

## Dependency Lock Provenance Handling

`dependency_lock.status="available"` requires a valid lock hash.

`dependency_lock.status="not_available"` requires a reason and stores `lock_hash=null`. This records absence of a verified lock without forging a lock hash.

PMDM manifests require an available dependency lock hash.

## Baseline Mode Evidence

`baseline_mode="non_pmdm_baseline"` requires `is_pmdm=false`.

`baseline_mode="pmdm"` requires `is_pmdm=true`.

PMDM manifests with `pmdm_status` of `unavailable`, `blocked`, or `license_unknown` are rejected as successful PMDM manifests.

## Checkpoint Ref Evidence

`V2CheckpointRef` carries metadata references only:

- `checkpoint_id`
- `checkpoint_uri`
- `step`
- optional `sha256`
- `format`
- `selected`

Task 51 does not create or embed model checkpoint payloads.

## No Weight Fixture Evidence

Boundary grep found no `.pt`, `.pth`, `.ckpt`, `.bin`, `model weight`, or `weights` tokens in `src/covalent_design/training/v2_manifests.py` or `tests/fixtures/training/v2_manifests/`.

Additional greps found no Task 52/tuning/tiny-sweep references and no `D:\codex_work\data` or `data/v2` access in the Task 51 module/tests.

## Commands Run

- `git diff --check`: pass; only CRLF/LF normalization warnings.
- `python -m pytest tests/training/test_v2_manifests.py -q`: pass, 19 passed, 11 subtests passed.
- `python -m pytest tests/training/test_v2_train_loop.py -q`: pass, 12 passed.
- `python -m covalent_design.training.cli.v2_train --config configs/v2_train_cpu_smoke.yml`: pass, JSON success with `checkpoint_manifest_written=false`.
- `python -m pytest tests/training/test_v2_dataset.py -q`: pass, 27 passed.
- `python -m pytest tests/model/test_torch_backend.py tests/model/test_pmdm_real_adapter.py tests/model/test_non_pmdm_baseline.py -q`: pass, 42 passed, 4 skipped.
- `python -m pytest tests/v2/test_smoke_check.py -q`: pass, 11 passed.
- `python scripts/v2_smoke_check.py --profile lightweight`: pass, JSON `overall_status="pass"`.
- `python -m compileall -q scripts src`: pass.
- `python -m pytest -q`: pass, 2050 passed, 27 skipped, 337 subtests passed.

Boundary checks:

- `rg -n "\.pt|\.pth|\.ckpt|\.bin|model weight|weights" tests/fixtures/training/v2_manifests src/covalent_design/training/v2_manifests.py`: no hits.
- `rg -n "v2_tune|tuning|tiny_sweep|Task 52" src/covalent_design/training/v2_manifests.py tests/training/test_v2_manifests.py`: no hits.
- `rg -n "D:\\codex_work\\data|data/v2" src/covalent_design/training/v2_manifests.py tests/training/test_v2_manifests.py`: no hits.

## Claude Window Findings

- Window A/B/D/E plan/review collaboration was used.
- Window C violated Plan Mode by writing `docs/reviews/task51-window-c-v2-manifests-plan-2026-06-22.md` during planning. The controller took over immediately and kept implementation scoped.
- Final Window E re-review found no blocking issues.
- Window E initially identified supplemental coverage gaps; the controller added tests for the missing/unsupported baseline mode, unsupported dependency-lock status, missing required data hash, missing dependency-lock reason, unavailable PMDM status variants, and invalid required data hash de-duplication.

## Codex Independent Findings

- Lazy facade is preserved through `__getattr__`; Task 51 public names are exported without eager imports.
- Direct manifest import does not load `torch`, `rdkit`, `PMDM`, or `PocketFlow`.
- The manifest module is schema-only and does not start training, write checkpoint payloads, read the real data root, or implement Task 52.
- Documentation now distinguishes unavailable dependency-lock provenance from a verified dependency lock hash.

## Remaining Risks

- P2: `pmdm_status` is still free-form for non-PMDM manifests. This does not block Task 52 because PMDM success/unavailable semantics and baseline mode consistency are enforced.
- P2: The Window C plan artifact uses naming that differs from the final accepted implementation names. The implementation and docs use the accepted `V2CheckpointExperimentManifest` naming.
- P2: Worktree still contains pre-existing untracked V2 files and local evidence directories from earlier tasks. No files were staged or committed.

## Whether Task 52 May Start

Task 52 may start: Yes.

Reason:

- Task 51 manifest schema exists and is tested.
- Required provenance and missing-provenance failures are tested.
- Dependency-lock provenance is explicit and does not forge absent lock hashes.
- Baseline/PMDM semantics are enforced.
- Lazy facade avoids import side effects.
- No weight/checkpoint payload fixtures or Task 52 behavior were introduced.
- Final verification passed.
