# Task 50 V2 Training Loop Review

Date: 2026-06-22

## Summary

Overall Status: PASS

Task 50 implements the V2 CPU/GPU training smoke-loop boundary. The implementation consumes the Task 49 `V2TrainingDatasetIndex` path through `prepare_v2_dataset()`, validates artifact existence/readability/byte size/checksum before tensor construction, keeps PMDM and non-PMDM baseline modes explicit, and emits a deterministic JSON summary from the package CLI.

Task 51 may start after user confirmation. Task 50 does not implement checkpoint/experiment manifests, tuning, sampling, inference, evaluation, or real model weights.

## Files Changed

- `src/covalent_design/training/v2_train_loop.py`: new Task 50 smoke-loop API, config resolution, Task 49 dataset loading, artifact preflight, explicit PMDM/baseline mode selection, smoke `LossReport`, denominator drift check, deterministic summary serialization.
- `src/covalent_design/training/cli/v2_train.py`: new package CLI entrypoint.
- `src/covalent_design/training/cli/__init__.py`: new CLI package marker.
- `src/covalent_design/training/__init__.py`: preserves public facade names with lazy exports, including Task 50 names.
- `tests/training/test_v2_train_loop.py`: Task 50 tests for CPU CLI, GPU unavailable behavior, Task 49 consumption, direct-record bypass rejection, artifact preflight failures, PMDM/baseline mode behavior, denominator drift, deterministic output, and no Task 51 artifacts.
- `tests/fixtures/training/v2_train_loop/`: lightweight Task 50 fixtures.
- `configs/v2_train_cpu_smoke.yml`: CPU smoke config over test fixture paths.
- `configs/v2_train_gpu_smoke.yml`: GPU smoke config requiring CUDA.
- `docs/v2/06-v2-training-and-tuning-spec.md`: Task 50 smoke behavior and boundaries.
- `docs/v2/09-v2-interface-and-contract-changes.md`: `V2TrainLoopConfig` / `V2TrainingSummary` contract.
- `docs/v2/10-v2-implementation-plan.md`: Task 50 marked implemented as lightweight smoke boundary.
- `docs/v2/11-v2-verification-matrix.md`: Task 50 evidence and status.
- `docs/v2/12-v2-risk-register.md`: Task 50 bypass/artifact-preflight risks updated.

## CPU Smoke Evidence

Command:

```powershell
$env:PYTHONPATH='src'
python -m covalent_design.training.cli.v2_train --config configs/v2_train_cpu_smoke.yml
```

Result: pass, exit 0.

Evidence from JSON summary:

- `success=true`
- `device="cpu"`
- `cuda_requested=false`
- `dataset.eligible_count=1`
- `artifact_preflight.status="passed"`
- `phases.tensor_construction_started=false`
- `publication_claims=[]`

## GPU Smoke Behavior

The committed GPU smoke config `configs/v2_train_gpu_smoke.yml` sets:

- `device: "cuda"`
- `model_mode: "non_pmdm_baseline"`

Test evidence:

- `tests/training/test_v2_train_loop.py::test_gpu_cuda_unavailable_fails_without_traceback`
- Monkeypatches CUDA status unavailable.
- Expects structured `V2_TRAIN_CUDA_UNAVAILABLE`.
- Confirms no traceback text and `tensor_construction_started=false`.

## Task49 Index Consumption Evidence

Implementation evidence:

- `src/covalent_design/training/v2_train_loop.py` imports and calls `prepare_v2_dataset()`.
- `run_v2_train()` requires all Task 49 inputs: `records_path`, `split_index_path`, `visual_check_index_path`, `quality_report_path`, `family_readiness_report_path`, `license_gate_report_path`, and `split_name`.
- Missing Task 49 gate reports fail with `V2_TRAIN_TASK49_INPUTS_MISSING`.

Search evidence:

```powershell
rg -n "prepare_dataset\(" src/covalent_design/training/v2_train_loop.py src/covalent_design/training/cli/v2_train.py tests/training/test_v2_train_loop.py
```

Result: no output.

## Artifact Preflight Evidence

Implementation evidence:

- `_validate_artifacts()` checks each eligible `ArtifactRef`.
- Checks are performed after Task 49 dataset loading and before CUDA/model path logic.
- Failure summaries keep `phases.tensor_construction_started=false`.

Test evidence:

- Missing artifact path: `V2_TRAIN_ARTIFACT_MISSING`
- Unreadable artifact path: `V2_TRAIN_ARTIFACT_UNREADABLE`
- Byte mismatch: `V2_TRAIN_ARTIFACT_BYTE_MISMATCH`
- Checksum mismatch: `V2_TRAIN_ARTIFACT_CHECKSUM_MISMATCH`
- Valid refs: `artifact_preflight.status="passed"`

## PMDM/Baseline Mode Evidence

PMDM mode:

- `model_mode="pmdm"` calls `check_pmdm_available()`.
- PMDM unavailable returns `PMDM_REAL_LICENSE_BLOCKED`.
- PMDM unavailable summary has `baseline_mode=null`, `is_pmdm=true`.
- No automatic fallback to baseline occurs.

Baseline mode:

- `model_mode="non_pmdm_baseline"` calls `check_baseline_mode()`.
- Successful summary includes `baseline_mode="non_pmdm_baseline"`.
- Successful summary includes `is_pmdm=false`.
- Successful summary includes `warning_code="BASELINE_NOT_PMDM_WARNING"` and warning text.

## Loss/Denominator Evidence

Task 50 creates a smoke `LossReport` with all required loss components:

- `pmdm_position_loss`
- `pmdm_atom_loss`
- `covalent_edge_loss`
- `covalent_bond_type_loss`
- `covalent_geometry_loss`
- `family_aux_loss`

The summary includes `loss_report.denominators` and `loss_report.mask_audit`. Denominator drift is tested with an impossible expected denominator and fails as `V2_TRAIN_DENOMINATOR_DRIFT`.

## CLI Evidence

Commands:

```powershell
$env:PYTHONPATH='src'
python -m covalent_design.training.cli.v2_train --help
python -m covalent_design.training.cli.v2_train --config configs/v2_train_cpu_smoke.yml
```

Results:

- `--help`: pass.
- CPU smoke config: pass, exit 0, deterministic JSON summary.

## Commands Run

Baseline before implementation:

```powershell
git status --short
git diff --stat
$env:PYTHONPATH='src'
python -m pytest tests/training/test_v2_dataset.py -q
python -m pytest tests/training/test_dataset.py tests/training/test_masks_denominators.py tests/training/test_train_smoke.py -q
python -m pytest tests/model/test_torch_backend.py tests/model/test_pmdm_real_adapter.py tests/model/test_non_pmdm_baseline.py -q
python -m pytest tests/v2/test_smoke_check.py -q
python scripts/v2_smoke_check.py --profile lightweight
python -m compileall -q scripts src
```

Task 50 verification:

```powershell
$env:PYTHONPATH='src'
python -m unittest tests.training.test_v2_train_loop -v
python -m pytest tests/training/test_v2_train_loop.py -q
python -m covalent_design.training.cli.v2_train --help
python -m covalent_design.training.cli.v2_train --config configs/v2_train_cpu_smoke.yml
python -m pytest tests/training/test_v2_dataset.py -q
python -m pytest tests/training/test_dataset.py tests/training/test_masks_denominators.py tests/training/test_train_smoke.py tests/training/test_v2_dataset.py tests/training/test_v2_train_loop.py -q
python -m pytest tests/model/test_torch_backend.py tests/model/test_pmdm_real_adapter.py tests/model/test_non_pmdm_baseline.py -q
python -m pytest tests/v2/test_smoke_check.py -q
python scripts/v2_smoke_check.py --profile lightweight
python -m unittest discover -s tests -t . -q
python -m compileall -q scripts src
git diff --check
```

Observed results:

- `tests.training.test_v2_train_loop`: 12 tests pass.
- `pytest tests/training/test_v2_train_loop.py -q`: 12 passed.
- Task 49 regression: 27 passed.
- Training regression group: 252 passed, 9 subtests passed.
- Model boundary regression: 42 passed, 4 skipped.
- V2 smoke check tests: 11 passed.
- `scripts/v2_smoke_check.py --profile lightweight`: overall_status `pass`.
- Full unittest discover: 1800 tests pass.
- compileall: pass.
- `git diff --check`: no whitespace errors; only line-ending warnings.

## Claude Window Findings

Claude Code windows were launched through `codex-claude-docs.ps1` with `-Mode Read` or `-Mode Review` and `-ExcludeDynamicSystemPromptSections`.

- Window A provided a read-only interface/config/summary/preflight plan.
- Window B provided a read-only test and fixture plan.
- Window C provided a read-only implementation plan.
- Window D provided a read-only documentation gap plan.
- Window E performed final read-only review.

Window E verdict: PASS with no blocking issues. It confirmed Task 49 consumption, artifact preflight before tensor construction, CPU/GPU behavior, PMDM no-auto-fallback, explicit baseline diagnostics, deterministic JSON, no Task 51 artifacts, and lazy facade behavior.

Window E non-blocking notes:

- `_validate_artifacts()` has a defensive `Path.cwd()` fallback if `records_path` is empty; normal Task 49 output sets `records_path`.
- Directory artifacts are reported as generic unreadable artifacts, which is acceptable for Task 50.
- GPU config uses `non_pmdm_baseline`; this matches current PMDM blocked status.

## Codex Independent Findings

Codex independently checked:

- `rg -n "prepare_dataset\(" ...`: no output for Task 50 source/CLI/test files.
- `rg -n "D:\\codex_work\\data|data/v2" ...`: no output for Task 50 source/CLI/test/config files.
- `git ls-files | rg "^(data/v2/|docs/superpowers/)"`: no tracked files under those paths.
- Task 51 files do not exist:
  - `src/covalent_design/training/v2_manifests.py`: false
  - `tests/training/test_v2_manifests.py`: false
  - `src/covalent_design/training/v2_tuning.py`: false
  - `tests/training/test_v2_tuning.py`: false

The broad filename scan finds pre-existing manifests, checkpoint references, PMDM/PocketFlow upstream weights, and v1 checkpoint code elsewhere in the repository. None are created by Task 50 and the Task 50 source/config/test files do not create checkpoint manifests or model weights.

## Remaining Risks

- PMDM real execution remains blocked by unknown upstream license; Task 50 correctly fails PMDM mode rather than auto-falling back.
- GPU success path remains manual-profile and depends on CUDA availability. The lightweight test proves structured CUDA-unavailable failure.
- Existing untracked `data/v2/`, `docs/superpowers/`, and prior review files remain git hygiene items. Task 50 did not track them.

## Whether Task 51 May Start

Task 51 May Start: Yes, after user confirmation.

Reason:

- No P0/P1 Task 50 blockers remain.
- CPU smoke CLI runs.
- GPU unavailable behavior is structured.
- Task 49 bypass risk is covered by implementation and tests.
- Artifact preflight fail-before-tensor behavior is covered.
- PMDM blocked does not auto-switch baseline.
- Full unittest and compileall pass.
- Task 51 files were not implemented in Task 50.
