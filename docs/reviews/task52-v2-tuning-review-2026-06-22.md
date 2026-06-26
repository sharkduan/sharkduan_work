# Task 52 V2 Tuning Review

Date: 2026-06-22
Status: PASS - verified-lightweight

## Executive Summary

Task 52 implements the V2 tiny hyperparameter tuning protocol as a deterministic lightweight sweep over the Task 50 training-loop boundary.

Overall status: PASS.
Checkpoint V2-E may start after controller acceptance.

Largest residual risk: the current `runtime_budget_seconds` is a required recorded budget contract, not a wall-clock interrupter. This is documented as acceptable for the lightweight smoke scope; a hard timeout belongs to a later heavy/full run if needed.

## Changed Files Reviewed

- `src/covalent_design/training/v2_tuning.py`: Task 52 API, config validation, per-trial execution, hashes, selection, failed-trial reporting.
- `src/covalent_design/training/cli/v2_tune.py`: package CLI entrypoint.
- `src/covalent_design/training/__init__.py`: lazy public facade for tuning API.
- `configs/v2_tiny_sweep.yml`: deterministic three-trial smoke sweep config.
- `tests/training/test_v2_tuning.py`: Task 52 API, CLI, determinism, failure, boundary, and validation tests.
- `tests/fixtures/training/v2_tuning/README.md`: fixture namespace marker.
- `docs/v2/06-v2-training-and-tuning-spec.md`: tuning protocol semantics.
- `docs/v2/09-v2-interface-and-contract-changes.md`: Task 52 interface contract.
- `docs/v2/10-v2-implementation-plan.md`: Task 52 acceptance and notes.
- `docs/v2/11-v2-verification-matrix.md`: Task 52 verification row.
- `docs/v2/12-v2-risk-register.md`: tuning failure and determinism risks.

## Contract Evidence

- Public API: `run_v2_tune(config) -> ContractEnvelope[V2TuningSummary]`.
- CLI: `python -m covalent_design.training.cli.v2_tune --config configs/v2_tiny_sweep.yml`.
- Config requires explicit `trial_count`, `runtime_budget_seconds`, `seeds`, `selection_metric`, `selection_mode`, Task 49 gate references, `device`, and `model_mode`.
- Trial IDs are deterministic local IDs (`trial-000`, `trial-001`, ...), ordered by the explicit seed list.
- The selected checkpoint ref is manifest-style metadata (`manifest-ref://v2-tuning/<trial_id>`) and does not create a model payload.

## Determinism And Hash Evidence

- Each trial records `config_hash` and `result_hash`.
- The sweep records `sweep_config_hash` and `sweep_result_hash`.
- Tests compare repeated API and CLI runs byte-for-byte or dict-for-dict.
- The CLI emits compact sorted JSON.

## Selection And Failure Evidence

- Selection is by frozen `selection_metric` and `selection_mode`.
- Failed trials remain in `trials` and `failed_trials`.
- Failed trials are excluded from selection.
- All-failed sweeps return structured `V2_TUNE_NO_SUCCESSFUL_TRIALS`.
- Additional validation tests cover unsupported `selection_mode` and mismatched `trial_model_modes` length.

## Boundary Evidence

- Task 52 reuses Task 50 `run_v2_train()` summaries and does not reimplement Task 49/50 validation.
- Boundary grep found no `D:\codex_work\data` or `data/v2` references in Task 52 source/test/config.
- Boundary grep found no Task 53/sampling/inference/evaluation references in Task 52 source/test/config.
- Boundary grep found no `.pt`, `.pth`, `.ckpt`, `.bin`, model weight, or weights strings in Task 52 source/test/config/fixture namespace.
- `git ls-files` found no tracked `data/v2/` or `docs/superpowers/` files.

## Claude Code Review

Final Claude Code Review returned PASS with no blocking issues.

Important findings from review:

- `runtime_budget_seconds` is recorded but not enforced as a wall-clock timeout.
- Trial seeds are recorded and hashed, but Task 50 smoke training is deterministic and does not currently consume stochastic state.

Resolution:

- Documented both semantics in `docs/v2/06-v2-training-and-tuning-spec.md`, `docs/v2/09-v2-interface-and-contract-changes.md`, and `docs/v2/10-v2-implementation-plan.md`.
- Kept V2-E checkpoint status as `planned` because this task only completes Task 52; Checkpoint V2-E still needs its own gate review.

## Verification Commands

Passed:

```powershell
$env:PYTHONPATH='src'; python -m pytest tests/training/test_v2_tuning.py -q  # 14 passed, 12 subtests
$env:PYTHONPATH='src'; python -m covalent_design.training.cli.v2_tune --config configs/v2_tiny_sweep.yml
$env:PYTHONPATH='src'; python -m pytest tests/training/test_v2_manifests.py -q
$env:PYTHONPATH='src'; python -m pytest tests/training/test_v2_train_loop.py -q
$env:PYTHONPATH='src'; python -m covalent_design.training.cli.v2_train --config configs/v2_train_cpu_smoke.yml
$env:PYTHONPATH='src'; python -m pytest tests/training/test_v2_dataset.py -q
$env:PYTHONPATH='src'; python -m pytest tests/model/test_torch_backend.py tests/model/test_pmdm_real_adapter.py tests/model/test_non_pmdm_baseline.py -q
$env:PYTHONPATH='src'; python -m pytest tests/v2/test_smoke_check.py -q
$env:PYTHONPATH='src'; python scripts/v2_smoke_check.py --profile lightweight
$env:PYTHONPATH='src'; python -m compileall -q scripts src
$env:PYTHONPATH='src'; python -m pytest -q
```

Full pytest result: 2064 passed, 27 skipped, 349 subtests passed.

`git diff --check` result: no whitespace errors; only CRLF normalization warnings on existing working-copy files.

Boundary scans passed:

```powershell
rg -n "D:\\codex_work\\data|data/v2" src/covalent_design/training/v2_tuning.py tests/training/test_v2_tuning.py configs/v2_tiny_sweep.yml
rg -n "Task 53|v2_sampling|sampling|inference|evaluation" src/covalent_design/training/v2_tuning.py tests/training/test_v2_tuning.py configs/v2_tiny_sweep.yml
rg -n "\.pt|\.pth|\.ckpt|\.bin|model weight|weights" src/covalent_design/training/v2_tuning.py tests/training/test_v2_tuning.py tests/fixtures/training/v2_tuning configs/v2_tiny_sweep.yml
git ls-files | rg "^(data/v2/|docs/superpowers/)"
```

All expected no-match scans returned no matches.

## Remaining Risks

- No blocking Task 52 risks.
- Wall-clock budget enforcement is not implemented in Task 52 lightweight scope; documented as future heavy/full-run behavior if needed.
- Seeds currently distinguish deterministic trials and hashes; Task 50 smoke loop has no random training path to consume them.

## Final Verdict

Task 52 is complete and verified-lightweight.

Allowed next step: Checkpoint V2-E Training Loop And Tuning Gate.

Do not start Task 53 until Checkpoint V2-E is explicitly reviewed and accepted.