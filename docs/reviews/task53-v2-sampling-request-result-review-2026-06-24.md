# Task 53 V2 Sampling Request/Result Review

Date: 2026-06-24
Status: PASS
Scope: Task 53 package-interface contract only

## Executive Summary

Task 53 is implemented as a lightweight, contract-only V2 sampling request/result boundary.

Overall status: PASS.

Task 54 may start after controller confirmation. Task 53 does not execute sampling, model forward passes, export, mmCIF writing, docking, evaluation, or real-data-root access.

## Reviewed Files

- `src/covalent_design/inference/v2_sampling.py`
- `src/covalent_design/inference/__init__.py`
- `tests/inference/test_v2_sampling.py`
- `docs/v2/07-v2-sampling-and-evaluation-spec.md`
- `docs/v2/09-v2-interface-and-contract-changes.md`
- `docs/v2/10-v2-implementation-plan.md`
- `docs/v2/11-v2-verification-matrix.md`
- `docs/v2/12-v2-risk-register.md`
- `src/covalent_design/contracts/types.py`
- `src/covalent_design/contracts/errors.py`

## Implementation Summary

Task 53 adds `src/covalent_design/inference/v2_sampling.py` with:

- `V2SamplingRequest`
- `V2SamplingResult`
- `V2InvalidDecodeDiagnostic`
- `V2SamplingSystemFailure`
- `build_v2_sampling_request()` returning `ContractEnvelope[Optional[V2SamplingRequest]]`
- deterministic request/result serialization and SHA-256 hash helpers
- structured `V2_SAMPLING_*` request validation failures

The `covalent_design.inference` facade exports the new V2 sampling contract symbols.

## Acceptance Trace

- Request includes checkpoint ref, checkpoint manifest ref, environment manifest ref, split-or-record selector, family filter, random seed, sample count, output root, retry policy, baseline mode, and `generation_mode="reactive_site"`.
- Exactly one selector is allowed: `split_name` or `record_ids`.
- `reference_ligand` generation is rejected.
- Result links checkpoint, checkpoint manifest, and environment manifest refs.
- Invalid generated samples and sampling system failures are distinct types.
- Failure concepts remain distinct: request validation, sampling system failure, invalid generated sample, export failure, docking not run, and evaluation artifact corruption.
- Result count conservation is enforced:

```text
valid_sample_count + invalid_sample_count == attempted_sample_count
attempted_sample_count + sampling_system_failure_count == requested_sample_count
```

- Serialization and hashes are deterministic.
- No true sampling, export, evaluation, docking, mmCIF writing, artifact generation, real-data-root access, or heavy hard imports are implemented.

## Blocking Issues

None.

## Important Issues

None.

## Minor Issues

- `ContractErrorInfo.location` is currently left unset for request validation errors. This is acceptable for Task 53 but could be enriched later.
- Individual helper serialization functions for invalid decode diagnostics and system failures are covered through result serialization, not by standalone tests.

## Boundary Review

Task 53 keeps future-task boundaries intact:

- Task 54 deterministic sampling smoke remains planned.
- Task 55 evaluation metrics remain planned.
- Task 56 docking feasibility remains planned.
- No RDKit, PyTorch, CUDA, PMDM, PocketFlow, Vina, docking, or evaluation module is hard-imported by `v2_sampling.py`.
- `output_root` is validated as a field but not created.
- `D:\codex_work\data` and `data/v2` are not referenced by Task 53 source/tests after source-guard cleanup.

Boundary `rg` scans found only allowed concept/status references such as `docking_not_run`, `evaluation_artifact_corruption`, `baseline_mode="pmdm"`, and documentation references that keep Task 54+ planned.

## Claude Code Review

A read-only Claude Code Review window was run with `-Mode Review -ExcludeDynamicSystemPromptSections`.

Result:

- P0: none
- P1: none
- P2: two advisory items listed above
- Go/no-go: GO for Task 54

## Verification

Commands run by controller:

```powershell
$env:PYTHONPATH='src'; python -m pytest tests/inference/test_v2_sampling.py -q
$env:PYTHONPATH='src'; python -m pytest tests/training/test_v2_full_beta_train.py -q
$env:PYTHONPATH='src'; python -m pytest tests/training/test_v2_tuning.py -q
$env:PYTHONPATH='src'; python -m pytest tests/training/test_v2_manifests.py -q
$env:PYTHONPATH='src'; python -m pytest tests/training/test_v2_train_loop.py -q
$env:PYTHONPATH='src'; python -m pytest tests/training/test_v2_dataset.py -q
$env:PYTHONPATH='src'; python -m pytest tests/model/test_torch_backend.py tests/model/test_pmdm_real_adapter.py tests/model/test_non_pmdm_baseline.py -q
$env:PYTHONPATH='src'; python -m pytest tests/v2/test_smoke_check.py -q
$env:PYTHONPATH='src'; python scripts/v2_smoke_check.py --profile lightweight
$env:PYTHONPATH='src'; python -m pytest -q
$env:PYTHONPATH='src'; python -m compileall -q scripts src
git diff --check
git ls-files | rg "^(data/v2/|docs/superpowers/)"
```

Observed results:

- `tests/inference/test_v2_sampling.py`: 26 passed
- `tests/training/test_v2_full_beta_train.py`: 13 passed, 14 subtests passed
- `tests/training/test_v2_tuning.py`: 14 passed, 12 subtests passed
- `tests/training/test_v2_manifests.py`: 19 passed, 11 subtests passed
- `tests/training/test_v2_train_loop.py`: 12 passed
- `tests/training/test_v2_dataset.py`: 27 passed
- model foundation tests: 42 passed, 4 skipped
- v2 smoke tests: 11 passed
- `scripts/v2_smoke_check.py --profile lightweight`: pass
- full pytest: 2103 passed, 27 skipped, 363 subtests passed
- compileall: pass
- `git diff --check`: pass, with Git line-ending warnings only
- tracked local artifact guard: no `data/v2/` or `docs/superpowers/` tracked paths

## Final Verdict

Task 53 is complete and verified.

Task 54 may proceed after main-controller acceptance. Task 54 must consume the Task 53 request/result contracts and remain limited to deterministic sampling smoke unless a later task prompt explicitly expands scope.
