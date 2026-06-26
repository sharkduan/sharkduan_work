# Checkpoint V2-E Training Loop And Tuning Gate Review

Date: 2026-06-24

Repository: `D:\codex_work\共价抑制剂设计`

Checkpoint: V2-E, Training Loop And Tuning Gate

Overall status: PASS WITH RISKS

Task 53 may start: YES, after controller/user accepts this checkpoint report. Do not start Task 53 automatically from this review.

## Scope

This read-only checkpoint reviewed whether Tasks 49-52.5 form an auditable V2 training and tuning closure:

- Task 49: V2 training dataset eligibility.
- Task 50: CPU/GPU training smoke loop.
- Task 51: V2 checkpoint and experiment manifest.
- Task 52: tiny tuning protocol.
- Task 52.5: full-beta training harness.

The review did not implement Task 53, did not run sampling, inference, or evaluation, did not access `D:\codex_work\data`, and did not run real heavy training. The only file written by this checkpoint is this report.

## Documents Reviewed

- `CONTEXT.md`
- `docs/v2/06-v2-training-and-tuning-spec.md`
- `docs/v2/09-v2-interface-and-contract-changes.md`
- `docs/v2/10-v2-implementation-plan.md`
- `docs/v2/11-v2-verification-matrix.md`
- `docs/v2/12-v2-risk-register.md`
- `docs/v2/13-v2-task-adr-coverage.md`
- `docs/reviews/v2-code-system-review-fix-2026-06-22.md`
- `docs/reviews/task50-v2-training-loop-review-2026-06-22.md`
- `docs/reviews/task51-v2-manifest-review-2026-06-22.md`
- `docs/reviews/task52-v2-tuning-review-2026-06-22.md`
- `docs/reviews/task52-5-v2-full-beta-training-review-2026-06-23.md`

## Code Reviewed

- `src/covalent_design/training/v2_dataset.py`
- `src/covalent_design/training/v2_train_loop.py`
- `src/covalent_design/training/v2_manifests.py`
- `src/covalent_design/training/v2_tuning.py`
- `src/covalent_design/training/v2_full_beta.py`
- `src/covalent_design/training/cli/v2_train.py`
- `src/covalent_design/training/cli/v2_tune.py`
- `src/covalent_design/training/cli/v2_full_beta_train.py`
- `tests/training/test_v2_dataset.py`
- `tests/training/test_v2_train_loop.py`
- `tests/training/test_v2_manifests.py`
- `tests/training/test_v2_tuning.py`
- `tests/training/test_v2_full_beta_train.py`
- `configs/v2_train_cpu_smoke.yml`
- `configs/v2_train_gpu_smoke.yml`
- `configs/v2_tiny_sweep.yml`
- `configs/v2_full_beta_train.yml`

## Commands Run

Baseline and final verification:

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/training/test_v2_dataset.py -q
python -m pytest tests/training/test_v2_train_loop.py -q
python -m pytest tests/training/test_v2_manifests.py -q
python -m pytest tests/training/test_v2_tuning.py -q
python -m pytest tests/training/test_v2_full_beta_train.py -q
python -m covalent_design.training.cli.v2_train --config configs/v2_train_cpu_smoke.yml
python -m covalent_design.training.cli.v2_tune --config configs/v2_tiny_sweep.yml
python -m covalent_design.training.cli.v2_full_beta_train --config configs/v2_full_beta_train.yml
python -m pytest tests/model/test_torch_backend.py tests/model/test_pmdm_real_adapter.py tests/model/test_non_pmdm_baseline.py -q
python -m pytest tests/v2/test_smoke_check.py -q
python scripts/v2_smoke_check.py --profile lightweight
python -m unittest discover -s tests -t . -q
python -m compileall -q scripts src
```

Boundary checks:

```powershell
rg -n "prepare_dataset\(" src/covalent_design/training/v2_train_loop.py src/covalent_design/training/v2_full_beta.py tests/training/test_v2_train_loop.py tests/training/test_v2_full_beta_train.py
rg -n "Task 53|v2_sampling|sampling|inference|evaluation" src/covalent_design/training/v2_dataset.py src/covalent_design/training/v2_train_loop.py src/covalent_design/training/v2_manifests.py src/covalent_design/training/v2_tuning.py src/covalent_design/training/v2_full_beta.py tests/training/test_v2_dataset.py tests/training/test_v2_train_loop.py tests/training/test_v2_manifests.py tests/training/test_v2_tuning.py tests/training/test_v2_full_beta_train.py configs/v2_train_cpu_smoke.yml configs/v2_train_gpu_smoke.yml configs/v2_tiny_sweep.yml configs/v2_full_beta_train.yml
rg -n "\.pt|\.pth|\.ckpt|\.bin|model weight|weights" src/covalent_design/training/v2_dataset.py src/covalent_design/training/v2_train_loop.py src/covalent_design/training/v2_manifests.py src/covalent_design/training/v2_tuning.py src/covalent_design/training/v2_full_beta.py tests/training/test_v2_dataset.py tests/training/test_v2_train_loop.py tests/training/test_v2_manifests.py tests/training/test_v2_tuning.py tests/training/test_v2_full_beta_train.py tests/fixtures/training/v2_dataset tests/fixtures/training/v2_train_loop tests/fixtures/training/v2_manifests tests/fixtures/training/v2_tuning tests/fixtures/training/v2_full_beta configs/v2_train_cpu_smoke.yml configs/v2_train_gpu_smoke.yml configs/v2_tiny_sweep.yml configs/v2_full_beta_train.yml
rg -n "D:\\codex_work\\data|data/v2" src/covalent_design/training/v2_dataset.py src/covalent_design/training/v2_train_loop.py src/covalent_design/training/v2_manifests.py src/covalent_design/training/v2_tuning.py src/covalent_design/training/v2_full_beta.py tests/training/test_v2_dataset.py tests/training/test_v2_train_loop.py tests/training/test_v2_manifests.py tests/training/test_v2_tuning.py tests/training/test_v2_full_beta_train.py configs/v2_train_cpu_smoke.yml configs/v2_train_gpu_smoke.yml configs/v2_tiny_sweep.yml configs/v2_full_beta_train.yml
git status --short
git ls-files | rg "^(data/v2/|docs/superpowers/)"
```

## Command Results

- `tests/training/test_v2_dataset.py`: 27 passed.
- `tests/training/test_v2_train_loop.py`: 12 passed.
- `tests/training/test_v2_manifests.py`: 19 passed, 11 subtests passed.
- `tests/training/test_v2_tuning.py`: 14 passed, 12 subtests passed.
- `tests/training/test_v2_full_beta_train.py`: 13 passed, 14 subtests passed.
- Model foundation tests: 42 passed, 4 skipped.
- V2 smoke check tests: 11 passed.
- `scripts/v2_smoke_check.py --profile lightweight`: `overall_status=pass`; heavy dependencies were `not_checked` by lightweight profile.
- `python -m unittest discover -s tests -t . -q`: 1846 tests passed.
- `python -m compileall -q scripts src`: passed.
- `v2_train` CLI: success, CPU, `non_pmdm_baseline`, `eligible_count=1`, `tensor_construction_started=false`, `checkpoint_manifest_written=false`.
- `v2_tune` CLI: success, `trial_count=3`, selected `trial-000`, failed count 0, selection metric `total_loss`.
- `v2_full_beta_train` CLI: success, `execution_mode=fixture`, `real_data_accessed=false`, `outputs_written=false`, checkpoint policy `manifest_ref_only`, selected checkpoint format `manifest_ref`.

## Window A-E Findings

### Window A: Dataset And License Gate

Verdict: PASS.

- P0: none.
- P1: none.
- P2: quality-tier missing values currently default to `Q1`; val/test positive-path coverage is lighter than train; malformed/zero `linkage_count` defaults remain deferred.
- Evidence: `manual_exempt` still requires manual intake and `training_eligible=true`; blocked/unknown/restricted-unsatisfied statuses are excluded; family, visual, quality, split, and artifact-role gates are enforced; no raw data root access was found.

### Window B: Training Loop And Artifact Preflight

Verdict: PASS.

- P0: none.
- P1: none.
- P2: empty `records_path` fallback is unreachable in normal Task 49 flow; directory artifacts map to generic unreadable status; GPU smoke config uses the explicit non-PMDM baseline path.
- Evidence: Task 50 consumes `prepare_v2_dataset()` with seven V2 gate inputs; no v1 `prepare_dataset()` bypass was found; artifact preflight runs before tensor/model phases; PMDM unavailable does not silently fallback; baseline mode is explicit and warning-bearing.

### Window C: Manifest And Tuning

Verdict: PASS.

- P0: none.
- P1: none.
- P2: manifest naming differs from an earlier plan artifact; manifest hash includes dependency lock despite earlier reproducibility intent; runtime budget is recorded but not enforced as a wall-clock interrupter; baseline `pmdm_status` is free-form; fixture directories duplicate some data.
- Evidence: manifests bind environment, dependency, data, dataset, family, config, training summary, checkpoint refs, baseline mode, `is_pmdm`, and PMDM status; tuning selection excludes failed trials and uses deterministic metric/tiebreaking; no checkpoint payloads are written.

### Window D: Full Beta Harness

Verdict: PASS.

- P0: none.
- P1 reported by window, controller disposition: non-blocking future-evolution risks, treated as P2 for this checkpoint.
- P2: `pmdm_status` is not enum-restricted for baseline manifests; `is_pmdm` uses exact `model_mode == "pmdm"`; duplicated fixture directories may drift; raw-root detection is intentionally constructed rather than a single literal; `outputs_written` is currently always false.
- Evidence: `execution_mode` is explicit; `heavy_manual` requires authorization; raw-data paths are blocked before training; selected checkpoint is manifest-ref metadata only; no weights, sampling, inference, or evaluation are produced.

### Window E: Cross-Cut Boundary And Documentation

Verdict: PASS WITH RISKS.

- P0: none.
- P1: V2-E gate review file was missing before this report; verification matrix V2-E row still says `planned`.
- P2: untracked `docs/superpowers/` and `data/v2/` remain local hygiene risks; fixture-mode evidence is correctly documented but is not real heavy training evidence; an old Task 51 plan artifact uses superseded naming.
- Evidence: docs now cover Tasks 49-52.5; Task 53 remains gated on Checkpoint V2-E; risk register covers real-data authorization, fixture overclaim, checkpoint-payload tracking, failed checkpoint selection, and PMDM license boundary.

## P0/P1/P2 Findings

### P0

None.

### P1

1. `docs/v2/11-v2-verification-matrix.md` still marks the V2-E row as `planned` even though this checkpoint has now produced verification evidence. This does not invalidate the current read-only gate report, but it should be synchronized before committing or presenting V2-E as closed.

### P2

1. `quality_tier` missing values default to `Q1` in the dataset path; document or fail-close in a later hardening task if desired.
2. V2 val/test split positive-path coverage is less explicit than train.
3. Manifest hash behavior includes dependency lock metadata; this is deterministic in fixture scope but differs from an earlier plan note.
4. `pmdm_status` is loosely validated for baseline manifests.
5. Fixture directories for training loop and full-beta contain duplicated data and may drift.
6. `data/v2/` and `docs/superpowers/` are untracked local artifacts; keep them out of commits unless explicitly approved.

## Evidence Table For Tasks 49-52.5

| Task | Evidence | Result |
| --- | --- | --- |
| 49 | `tests/training/test_v2_dataset.py`; Window A review | PASS, dataset/license gate is suitable as V2-E input gate |
| 50 | `tests/training/test_v2_train_loop.py`; `v2_train` CLI; Window B review | PASS, Task 49 dataset consumed and artifact preflight happens before tensor construction |
| 51 | `tests/training/test_v2_manifests.py`; Window C review | PASS, manifest provenance and checkpoint refs are metadata-only and deterministic |
| 52 | `tests/training/test_v2_tuning.py`; `v2_tune` CLI; Window C review | PASS, failed trials are not selected and selection is metric-justified |
| 52.5 | `tests/training/test_v2_full_beta_train.py`; `v2_full_beta_train` CLI; Window D review | PASS, fixture full-beta harness composes Tasks 49-52 and keeps heavy/manual evidence distinct |

## Boundary Checks

- v1 `prepare_dataset(` bypass in `v2_train_loop.py` / `v2_full_beta.py`: no matches.
- V2 raw data literal / `data/v2` references in reviewed source, tests, configs: no direct matches in V2 source/configs; split-token test guard strings exist by design.
- Task 53 / sampling / inference / evaluation references in V2 training scope: only a negative docstring in `v2_train_loop.py` saying it does not run sampling.
- Model-weight / checkpoint-payload tokens in V2 training scope: only negative test guard strings and negative docstring; no actual V2 payload writing path found.
- `git ls-files | rg "^(data/v2/|docs/superpowers/)"`: no tracked `data/v2/` or `docs/superpowers/` files.
- `git status --short`: many V2 task files and local evidence remain unstaged/untracked, including `data/v2/` and `docs/superpowers/`; this is a hygiene risk but not a V2-E functional blocker.

## Heavy/Manual Evidence Status

Current checkpoint evidence is lightweight and fixture-mode only. It proves the full-beta harness contract, deterministic summaries, manifest-ref checkpoint selection, failed-trial exclusion, and authorization gates. It does not prove real heavy training throughput, real PMDM execution, or publication-quality training performance.

## Real Data Authorization Status

No `D:\codex_work\data` access was performed during this checkpoint. Task 52.5 fixture mode reported `real_data_accessed=false`. Heavy/manual mode remains authorization-gated and should not be run without an explicit user/controller authorization in that turn.

## Fixture vs Heavy Evidence Distinction

Fixture-mode full-beta success is harness evidence, not real heavy training evidence. The CLI explicitly reports `execution_mode=fixture`, `real_data_accessed=false`, and `outputs_written=false`. Reports and future prompts must not describe this as completed real heavy training.

## Go/No-Go Verdict

Go status: PASS WITH RISKS.

Task 49-52.5 targeted tests, CLI checks, model foundation checks, V2 smoke checks, compileall, and full unittest all passed. The Claude Code review windows found no P0 blocker. The remaining issues are documentation/status hygiene and future-hardening risks, not current evidence that the V2-E training/tuning closure is unsafe.

## Whether Task 53 May Start

Task 53 may start only after this checkpoint report is accepted by the controller/user. Task 53 must remain a separate task and must not inherit a claim that fixture-mode full-beta evidence is real heavy training evidence.

Before committing or publishing the V2-E closure, update `docs/v2/11-v2-verification-matrix.md` so the V2-E row no longer says `planned`.

## Required Remediation Prompt If NO-GO

Not applicable. This checkpoint is not NO-GO.

If the controller wants to clean the non-blocking P1 before Task 53, use this narrow remediation:

```text
Update docs/v2/11-v2-verification-matrix.md only. Change the Checkpoint V2-E row from planned to verified-2026-06-24 (or the repository-standard verified status) and mention that verification is lightweight fixture-mode, with no real heavy training or real-data access claim. Do not modify src, tests, configs, or start Task 53.
```
