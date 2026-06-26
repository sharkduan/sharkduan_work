# V2 Code System Review Fix Report

Date: 2026-06-22
Repository: `D:\codex_work\共价抑制剂设计`
Mode: implementation remediation before Task 50

## Summary

Overall status: PASS.

The P0 and P1 blockers from `docs/reviews/v2-code-system-review-2026-06-21.md` are remediated. Task 49 now fails closed for `manual_exempt` sources when the license gate report says `training_eligible=false`, preserves source license audit reason codes on excluded records, proves the import boundary in a clean subprocess, and documents the Task 49 / Task 50 artifact validation split.

Task 50 may start after the final verification commands in this report remain green. Task 50 must still consume the Task 49 `V2TrainingDatasetIndex` or an equivalent validated envelope and must not call the v1 `prepare_dataset()` source directly.

## Phase 0 User Decisions

- The dedicated exclusion reason for `manual_exempt + training_eligible=false` is `excluded_manual_exempt_audit_failed`.
- Excluded records preserve source license report reason codes as `license_reason_codes`.
- Task 49 performs minimum artifact role validation only. Path existence, readability, byte count, and checksum validation are Task 50 fail-before-tensor responsibilities.
- `V2ExcludedRecord` carries `source_name` and `intake_mode`.
- `linkage_count` zero/missing/non-integer behavior is recorded as P2 deferred and was not changed.
- The public `covalent_design.training` facade keeps public names but now uses lazy loading to avoid package import side effects.

## Files Changed

- `src/covalent_design/training/v2_dataset.py`: added `excluded_manual_exempt_audit_failed`, `license_reason_codes`, `source_name`, `intake_mode`, and minimum artifact role presence exclusion.
- `src/covalent_design/training/__init__.py`: converted eager public facade imports to lazy `__getattr__` exports while preserving existing public names.
- `tests/training/test_v2_dataset.py`: added regression coverage for manual-exempt failed audit, missing split assignment, deferred/partial family readiness, missing artifact roles, excluded-record provenance, and clean subprocess import boundary.
- `docs/v2/06-v2-training-and-tuning-spec.md`: documented updated Task 49 eligibility semantics, excluded-record audit fields, and artifact-validation boundary.
- `docs/v2/09-v2-interface-and-contract-changes.md`: fixed environment dependency status enum and added the `V2TrainingDatasetIndex` contract section.
- `docs/v2/10-v2-implementation-plan.md`: updated Task 49 evidence and Task 50 input/artifact validation requirements.
- `docs/v2/11-v2-verification-matrix.md`: updated Task 49 evidence to 27 tests and added Task 50 boundary expectations.
- `docs/v2/12-v2-risk-register.md`: recorded the remediated manual-exempt risk, Task 50 v1-bypass risk, artifact validation ownership, and deferred linkage-count policy.
- `docs/reviews/v2-code-system-review-fix-2026-06-22.md`: this report.

## P0 Fix Evidence

### Manual-exempt audit failure bypass

Status: fixed.

`prepare_v2_dataset()` now excludes a `manual_exempt` source when the license gate report has `training_eligible=false`, using primary reason `excluded_manual_exempt_audit_failed`.

Evidence:

- Regression test: `tests/training/test_v2_dataset.py::V2EligibilityGateTests::test_manual_exempt_audit_failed_is_excluded_even_in_manual_mode`.
- Independent mutation probe output:

```json
{"license_reason_codes":["V2_LICENSE_MANUAL_EXEMPT_AUDIT_FAILED"],"manual_ok_eligible":false,"ok":true,"primary_reason":"excluded_manual_exempt_audit_failed"}
```

## P1 Fix Evidence

### Import-boundary false confidence

Status: fixed.

`tests/training/test_v2_dataset.py` now runs the import-boundary assertion in a clean subprocess. `src/covalent_design/training/__init__.py` now preserves the facade names with lazy imports and avoids loading losses, train loop, checkpoints, PMDM, PocketFlow, RDKit, or torch from a `v2_dataset` import.

Independent subprocess probe output:

```json
{"callable":true,"forbidden":[]}
```

### Duplicate training facade imports

Status: fixed.

The duplicate eager import block in `src/covalent_design/training/__init__.py` was replaced by a single `_EXPORTS` map and lazy `__getattr__`.

### Dependency status enum drift

Status: fixed.

`docs/v2/09-v2-interface-and-contract-changes.md` now uses the implemented `V2EnvironmentManifest.dependency_statuses` enum: `available`, `unavailable`, `not_checked`, `failed`.

### Excluded-record audit provenance

Status: fixed.

`V2ExcludedRecord` now preserves `source_name`, `intake_mode`, and `license_reason_codes`. The regression test verifies `REC-LIC-BLOCK` carries `FixtureBlocked`, `manual`, and `("V2_LICENSE_STATUS_BLOCKED",)`.

### Missing branch coverage

Status: fixed.

New tests cover missing split assignment, family readiness `deferred`, family readiness `partial`, and missing artifact role presence.

## Deferred P2 Items

- `linkage_count` zero/missing/non-integer behavior remains unchanged and is documented as P2 deferred. No behavior was changed without a later policy decision.
- `src/covalent_design/model/__init__.py` newline-at-EOF hygiene was noted by the prior review but was outside this remediation scope.
- Task 50 still must prove it consumes `V2TrainingDatasetIndex` and validates artifact paths/readability/checksums before tensor construction.

## Claude Window Findings

Claude Code final review ran in read-only Review mode with `-ExcludeDynamicSystemPromptSections`.

Verdict: PASS. It reported all P0 and P1 issues remediated, verified lazy facade behavior, confirmed Task 49 only does minimum artifact role presence validation, confirmed docs do not claim Task 50 is implemented, and found no forbidden real-data, PMDM/PocketFlow/RDKit/torch, model-forward, masks, losses, train-loop, or artifact generation changes.

## Codex Independent Findings

- The Task 49 eligibility chain now respects source-level license gate `training_eligible` for all license statuses, including `manual_exempt`.
- The clean subprocess import proof is stronger than the previous in-process `sys.modules` check.
- The docs now explicitly split Task 49 artifact role presence from Task 50 path/readability/checksum validation.
- `data/v2/` and `docs/superpowers/` remain untracked according to `git ls-files | rg "^(data/v2/|docs/superpowers/)"` returning no output.

## Commands Run

```powershell
git status --short
```

Observed dirty state includes tracked V2 docs/facade changes plus pre-existing/untracked V2 work. No staging or commit was performed.

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/training/test_v2_dataset.py -q
```

Result: `27 passed`.

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/training/test_dataset.py tests/training/test_masks_denominators.py tests/training/test_train_smoke.py -q
```

Result: `213 passed, 9 subtests passed`.

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/training/test_dataset.py tests/training/test_masks_denominators.py tests/training/test_train_smoke.py tests/training/test_v2_dataset.py -q
```

Result: `240 passed, 9 subtests passed`.

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/data/test_v2_manifests.py tests/data/test_v2_intake.py tests/data/test_v2_conversion.py tests/data/test_v2_license.py tests/data/test_v2_real_etl_cli.py -q
```

Result: `160 passed`.

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/model/test_torch_backend.py tests/model/test_pmdm_real_adapter.py tests/model/test_non_pmdm_baseline.py -q
```

Result: `42 passed, 4 skipped`.

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/v2/test_smoke_check.py -q
```

Result: `11 passed`.

```powershell
$env:PYTHONPATH='src'
python scripts/v2_smoke_check.py --profile lightweight
```

Result: `overall_status=pass`, dependency statuses `not_checked` for heavy dependencies.

```powershell
$env:PYTHONPATH='src'
python -m compileall -q scripts src
```

Result: pass.

```powershell
git ls-files | rg "^(data/v2/|docs/superpowers/)"
```

Result: no output, `rg` exit 1, meaning those local artifact directories are not tracked.


## Final Verification Addendum

```powershell
$env:PYTHONPATH='src'
python -m pytest -q
```

Result: `2019 passed, 27 skipped, 326 subtests passed`.

```powershell
$env:PYTHONPATH='src'
python -m unittest discover -s tests -t . -q
```

Result: `Ran 1788 tests`; `OK`.

```powershell
git diff --check
```

Result: pass. Git emitted CRLF normalization warnings for existing working-copy files, but no whitespace errors.
## Remaining Risks

- Task 50 must be implemented against Task 49 `V2TrainingDatasetIndex`; direct v1 `prepare_dataset()` use is a known P1 risk for Task 50 and is documented in the risk register.
- Task 50 must validate artifact path/readability/checksum before tensor construction; Task 49 intentionally validates only role presence.
- PMDM remains license-blocked/structured unavailable; Task 50 must preserve explicit PMDM vs non-PMDM baseline selection.
- `linkage_count` malformed-value semantics remain P2 deferred.

## Whether Task 50 May Start

Task 50 may start after the final verification suite remains green.

Start conditions for Task 50 prompt:

- Consume Task 49 `V2TrainingDatasetIndex` or an equivalent validated envelope.
- Do not call v1 `prepare_dataset()` directly as the V2 eligibility source.
- Validate artifact path existence, readability, bytes, and checksum before tensor construction.
- Keep PMDM and non-PMDM baseline modes explicit.
- Do not read `D:\codex_work\data` unless a future task explicitly permits it.