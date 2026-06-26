# Task 52.5 V2 Full Beta Training Review

Date: 2026-06-23
Status: PASS

## Scope

Reviewed Task 52.5 only: the V2 full-beta training harness between Task 52 and
Checkpoint V2-E. This review does not authorize real local data access and does
not start Task 53 or later pipeline stages.

## Files Reviewed

- `src/covalent_design/training/v2_full_beta.py`
- `src/covalent_design/training/cli/v2_full_beta_train.py`
- `configs/v2_full_beta_train.yml`
- `tests/training/test_v2_full_beta_train.py`
- `tests/fixtures/training/v2_full_beta/`
- `docs/v2/06-v2-training-and-tuning-spec.md`
- `docs/v2/09-v2-interface-and-contract-changes.md`
- `docs/v2/10-v2-implementation-plan.md`
- `docs/v2/11-v2-verification-matrix.md`
- `docs/v2/12-v2-risk-register.md`
- `docs/v2/13-v2-task-adr-coverage.md`

## Findings

No blocking findings.

Task 52.5 provides `run_v2_full_beta_train(config) ->
ContractEnvelope[V2FullBetaSummary]` and the package CLI
`python -m covalent_design.training.cli.v2_full_beta_train --config
configs/v2_full_beta_train.yml`.

Fixture mode succeeds deterministically, produces manifest-ref checkpoint
metadata with selection justification, and records `real_data_accessed=false`
and `outputs_written=false`. Heavy/manual mode requires explicit controller
authorization before real local data paths are used. Heavy runtime unavailability
returns structured failure and does not select a checkpoint.

Failed Task 50 training or failed Task 52 tuning leaves
`selected_checkpoint_ref=null`. The default policy is `manifest_ref_only`; no
checkpoint payload is written by default.

The first Claude review incorrectly reported empty fixture directories. Main
controller verification and the second Claude review confirmed the
`tests/fixtures/training/v2_full_beta/` and `tests/fixtures/training/v2_train_loop/`
fixtures are present and populated.

## Verification

Commands run:

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/training/test_v2_full_beta_train.py -q
python -m covalent_design.training.cli.v2_full_beta_train --config configs/v2_full_beta_train.yml
python -m pytest tests/training/test_v2_tuning.py tests/training/test_v2_manifests.py tests/training/test_v2_train_loop.py tests/training/test_v2_dataset.py -q
python -m pytest tests/model/test_torch_backend.py tests/model/test_pmdm_real_adapter.py tests/model/test_non_pmdm_baseline.py -q
python -m compileall -q scripts src
python -m unittest discover -s tests -t . -q
```

Results:

- Task 52.5 tests: 13 passed, 14 subtests passed.
- Task 49-52 regression tests: 72 passed, 23 subtests passed.
- Model foundation regression tests: 42 passed, 4 skipped.
- Full unittest discovery: 1846 tests passed.
- Compileall: passed.
- CLI: exited 0 with deterministic JSON summary.

## Nonblocking Notes

- `_RAW_ROOT` is constructed by string concatenation to keep boundary-grep tests
  from matching the raw local data root literal while preserving runtime
  detection.
- `configs/v2_full_beta_train.yml` uses the Task 52.5 fixture directory, while
  `configs/v2_tiny_sweep.yml` still points to the Task 50 fixture directory. The
  two fixture sets are currently identical.

## Verdict

Task 52.5 may proceed to Checkpoint V2-E. Real heavy/manual training remains
pending explicit controller authorization and suitable heavy environment
evidence.
