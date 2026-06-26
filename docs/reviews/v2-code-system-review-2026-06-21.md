# V2 已实现代码与文档-代码一致性系统审查

Date: 2026-06-21

Mode: read-only review plus one report write. This report did not modify `src/`, `tests/`, `configs/`, or `scripts`, did not enter Task 50, did not train, did not access `D:\codex_work\data`, and did not commit.

## Executive Summary

Verdict: **NO-GO for Task 50**.

Reason: the normal targeted test baseline passes, but adversarial review found a P0 semantic gap in Task 49. `prepare_v2_dataset()` can admit a `manual_exempt` record even when the supplied license gate report says that source has `training_eligible=false`. Under the user's severity rules, this is an erroneous training entry / license gate bypass candidate, so Task 50 must not start until fixed and covered by a regression test.

High-signal state:

- Targeted verification passed: data V2 160 passed; chem 18 passed / 23 skipped; model 42 passed / 4 skipped; Task 49 dataset 22 passed; V2 smoke tests 11 passed; lightweight smoke JSON passed; `compileall` passed.
- The passing Task 49 tests do not catch the P0 because the fixture only covers `manual_exempt` with `training_eligible=true` and `manual_exempt` + download.
- The Task 49 import-boundary test is weaker than it appears: in a clean subprocess, importing `covalent_design.training.v2_dataset` also imports `covalent_design.training.train_loop`, `covalent_design.training.losses`, `covalent_design.training.checkpoints`, and `covalent_design.model.pmdm_adapter`.
- Worktree remains dirty from pre-existing/current changes. This review added only this report file.

## Review Scope

Reviewed implementation and documentation around V2 data, chemistry, model foundation, and Task 49 training eligibility:

- `src/covalent_design/data/`
- `src/covalent_design/chem/`
- `src/covalent_design/model/`
- `src/covalent_design/training/`
- `scripts/v2_smoke_check.py`
- `tests/data/test_v2_*.py`
- `tests/chem/test_rdkit_*.py`, `tests/chem/test_scaffolds.py`
- `tests/model/test_torch_backend.py`, `tests/model/test_pmdm_real_adapter.py`, `tests/model/test_non_pmdm_baseline.py`
- `tests/training/test_v2_dataset.py`
- `tests/v2/test_smoke_check.py`
- `docs/v2/04-v2-dependency-and-environment-spec.md`
- `docs/v2/05-v2-data-automation-spec.md`
- `docs/v2/06-v2-training-and-tuning-spec.md`
- `docs/v2/09-v2-interface-and-contract-changes.md`
- `docs/v2/10-v2-implementation-plan.md`
- `docs/v2/11-v2-verification-matrix.md`
- `docs/v2/12-v2-risk-register.md`
- `docs/adr/0037-v2-environment-and-heavy-dependency-boundary.md`
- `docs/adr/0038-manual-data-license-audit-exemption.md`
- `docs/reviews/`

Explicitly not reviewed by direct data access:

- `D:\codex_work\data`
- raw source data contents
- training execution or Task 50 implementation

## Commands Run

Initial state:

```powershell
git status --short
```

Observed relevant dirty state:

```text
 M docs/v2/06-v2-training-and-tuning-spec.md
 M docs/v2/09-v2-interface-and-contract-changes.md
 M docs/v2/10-v2-implementation-plan.md
 M docs/v2/11-v2-verification-matrix.md
 M docs/v2/12-v2-risk-register.md
 M src/covalent_design/model/__init__.py
 M src/covalent_design/training/__init__.py
?? data/v2/
?? docs/reviews/checkpoint-v2-d-foundation-gate-review-2026-06-21.md
?? docs/superpowers/
?? src/covalent_design/model/non_pmdm_baseline.py
?? src/covalent_design/training/v2_dataset.py
?? tests/fixtures/training/v2_dataset/
?? tests/model/test_non_pmdm_baseline.py
?? tests/training/test_v2_dataset.py
```

```powershell
git diff --stat
```

Result: 7 tracked files changed, 197 insertions / 39 deletions, plus untracked files/directories listed above.

Required baseline:

```powershell
$env:PYTHONPATH='src'; python -m pytest tests/data/test_v2_manifests.py tests/data/test_v2_intake.py tests/data/test_v2_conversion.py tests/data/test_v2_license.py tests/data/test_v2_real_etl_cli.py -q
```

Result: `160 passed in 4.01s`.

```powershell
$env:PYTHONPATH='src'; python -m pytest tests/chem/test_rdkit_normalize.py tests/chem/test_rdkit_descriptors.py tests/chem/test_scaffolds.py -q
```

Result: `18 passed, 23 skipped`.

```powershell
$env:PYTHONPATH='src'; python -m pytest tests/model/test_torch_backend.py tests/model/test_pmdm_real_adapter.py tests/model/test_non_pmdm_baseline.py -q
```

Result: `42 passed, 4 skipped`.

```powershell
$env:PYTHONPATH='src'; python -m pytest tests/training/test_v2_dataset.py -q
```

Result: `22 passed`.

```powershell
$env:PYTHONPATH='src'; python -m pytest tests/v2/test_smoke_check.py -q
```

Result: `11 passed`.

```powershell
$env:PYTHONPATH='src'; python scripts/v2_smoke_check.py --profile lightweight
```

Result: exit 0, JSON `overall_status=pass`, heavy dependencies all `not_checked`.

```powershell
$env:PYTHONPATH='src'; python -m compileall -q scripts src
```

Result: pass.

Adversarial probes:

```powershell
$env:PYTHONPATH='src'; python -c "<mutate fixture license report so audit/manual_ok has training_eligible=false, then call prepare_v2_dataset>"
```

Result:

```json
{"eligible_ids":["REC-ELIG","REC-MANUAL-OK","REC-Q2","REC-REST-OK"],"manual_ok_eligible":true,"ok":true}
```

Interpretation: P0 confirmed. A source-level license report entry with `license_status="manual_exempt"` and `training_eligible=false` can still produce an eligible Task 49 record when record/report intake modes are `manual`.

```powershell
$env:PYTHONPATH='src'; python -c "import json, sys; before=set(sys.modules); import covalent_design.training.v2_dataset; introduced=sorted(set(sys.modules)-before); bad=[m for m in introduced if any(t in m.lower() for t in ('losses','train_loop','checkpoints','torch','rdkit','pmdm','pocketflow'))]; print(json.dumps({'bad': bad, 'count': len(bad)}, sort_keys=True))"
```

Result:

```json
{"bad":["covalent_design.model.pmdm_adapter","covalent_design.training.checkpoints","covalent_design.training.losses","covalent_design.training.train_loop"],"count":4}
```

Interpretation: Task 49's current import-boundary test is not proving the clean package import boundary claimed by the docs.

Git publication guard:

```powershell
git ls-files | rg "^(data/v2/|docs/superpowers/)"
```

Result: no output, exit 1 from `rg`, meaning no tracked files under those prefixes were found.

Claude Code windows:

- Window A module map: first run exited 0 but produced no narrative; retry failed with Claude CLI `API Error: 402 Insufficient Balance`.
- Window B data/license: completed and reported no P0 in the data/license chain; found Task 50 must not copy the v1 `prepare_dataset()` path.
- Window C chemistry: first run exited 0 but produced no narrative; retry failed with `402`.
- Window D model foundation: completed and reported no P0; PMDM license remains structured blocked; future consumers must keep baseline and PMDM modes distinct.
- Window E training dataset eligibility: completed and reported no P0, P1 duplicate `training/__init__.py` import, and Task 49 test gaps. Codex refined the manual-exempt finding into the P0 above after dynamic verification.
- Window F docs drift: first run exited 0 but produced no narrative; retry failed with `402`.

## Current V2 Status

| Area | Current status | Evidence | Caveat |
| --- | --- | --- | --- |
| Task 37-39 environment smoke | Lightweight verified | `tests/v2/test_smoke_check.py` 11 passed; lightweight smoke JSON pass | Interface doc has status enum drift |
| Task 40-43 data/license | Targeted tests pass | 160 data tests passed | This review did not read `D:\codex_work\data`; current repo has untracked `data/v2/` local artifacts |
| V2-B real local ETL evidence | Documented as repaired/verified | `docs/reviews/v2-real-data-import-repair-2026-06-19.md`; verification matrix | Not rerun here because request forbids `D:\codex_work\data` access |
| Task 44-45 chemistry | Lightweight tests pass; RDKit skipped here | 18 passed / 23 skipped | Heavy RDKit evidence exists in docs but was not rerun |
| Task 46 tensor backend | Targeted tests pass | model test group 42 passed / 4 skipped | PyTorch-backed tests skipped in this environment |
| Task 47 real PMDM boundary | Structured unavailable | `pmdm_real_adapter.py:79-105`, `247-272`; tests pass | PMDM license remains unknown/blocked |
| Task 48 non-PMDM baseline | Implemented and tested | `non_pmdm_baseline.py`; tests pass | Consumer-side no-confusion guard still belongs to Task 50/51 |
| Task 49 dataset eligibility | Implemented, tests pass, but semantically unsafe | `v2_dataset.py`; 22 tests pass | P0 manual-exempt eligibility bug and P1 import-boundary test weakness |
| Task 50 | Planned only | docs list planned `v2_train_loop.py`, CLI, configs | Must not start until P0 is fixed |

## Claude Window Findings Summary

Window B found the V2 data/license chain is mostly coherent:

- Manifest, staging, conversion, and license gate are ordered and fail closed.
- `download + manual_exempt`, `blocked`, `unknown`, and unsatisfied `restricted` are blocked in Task 43.
- The ETL CLI writes processed artifacts only for `conversion_ok` and `license_eligible is True`.
- P1: existing v1 `src/covalent_design/training/train_loop.py:195` calls `prepare_dataset()` and has no V2 license/family gate; Task 50 must not reuse that path unchanged.

Window D found the model foundation coherent but still risk-bearing:

- `pmdm_real_adapter.py:79-105` does not import PMDM and reports `license_unknown`.
- `forward_pmdm_real()` fails with `PMDM_REAL_LICENSE_BLOCKED` and does not silently fall back.
- `non_pmdm_baseline.py` must be explicitly selected and carries `baseline_mode="non_pmdm_baseline"` plus `is_pmdm=false`.
- P1: Task 50/51 must preserve `baseline_mode`/`is_pmdm`, not just check PMDM-compatible output keys.

Window E found Task 49 mostly aligned:

- It confirmed the seven gate categories, count conservation, deterministic order, JSON serialization, and basic module-boundary test.
- It found P1 duplicate imports in `src/covalent_design/training/__init__.py:80-88`.
- It found missing tests for `missing_split_assignment`, family `deferred`, and family `partial`.
- Codex independently escalated the `manual_exempt` eligibility handling to P0 after verifying that `training_eligible=false` is ignored for manual-exempt sources.

Windows A/C/F did not provide usable findings due either empty output or Claude CLI balance failure. This report therefore uses Codex main-controller review to fill architecture, chemistry, and docs-drift coverage.

## Codex Independent Findings

Main independent conclusions:

- The V2 code has the right broad architecture direction: `data` owns source intake/conversion/license, `chem` isolates RDKit, `model` isolates PyTorch/PMDM/baseline, and Task 49 is intended to be data-only eligibility.
- The implementation has one P0 contract break in Task 49: it treats `manual_exempt` as eligible based on mode checks without respecting the source-level `training_eligible` field from the license report.
- The training package facade undermines the Task 49 import-boundary claim because importing `covalent_design.training.v2_dataset` loads v1 training loop/loss/checkpoint modules through `training/__init__.py`.
- Documentation is close but not clean: `docs/v2/09-v2-interface-and-contract-changes.md` still lists the wrong environment dependency status enum.
- Current tests are broad enough to catch most happy/failure paths but not adversarial contradictions in upstream reports.

## Reconciled P0 Findings

### P0-1: Task 49 can admit a manual-exempt record even when the license report says `training_eligible=false`

File:

- `src/covalent_design/training/v2_dataset.py:290-305`
- `src/covalent_design/training/v2_dataset.py:430-446`
- `tests/fixtures/training/v2_dataset/license_gate_report.json:11-12`
- `docs/v2/06-v2-training-and-tuning-spec.md:26-38`
- `docs/v2/10-v2-implementation-plan.md:620-630`

Evidence:

- `_parse_license_report()` preserves `training_eligible` in `_LicenseEntry` at `v2_dataset.py:443`.
- `_all_exclusion_reasons()` handles `restricted and not training_eligible` at `v2_dataset.py:298-299`.
- For `manual_exempt`, it only checks `policy.allow_manual_exempt`, record `context.intake_mode`, and report `intake_mode` at `v2_dataset.py:300-303`.
- The generic `elif not license_entry.training_eligible` at `v2_dataset.py:304-305` is not reached for `manual_exempt`.
- A temporary fixture mutation setting `audit/manual_ok` to `training_eligible=false` still produced `manual_ok_eligible=true` and `ok=true`.

Impact:

- A failed or contradictory license gate report can be weakened by Task 49.
- This violates the intended "license audit is a hard pre-training gate" semantics.
- This is an erroneous training entry risk and therefore P0 by the user's stated severity definition.

Recommendation:

- Before Task 50, change Task 49 so any source-level `training_eligible=false` excludes the record for all license statuses, including `manual_exempt`.
- Add a regression test that mutates or fixtures a `manual_exempt` source with `training_eligible=false` and asserts exclusion, probably with primary reason `excluded_license_audit_failed` or a more specific `excluded_manual_exempt_audit_failed`.
- Decide whether `reason_codes` should also be preserved in `V2ExcludedRecord` for auditability.

Task 50 implication:

- **Task 50 must not start until this is fixed and verified.**

## Reconciled P1 Findings

### P1-1: Task 49 import-boundary test is giving false confidence

File:

- `src/covalent_design/training/__init__.py:1-15`
- `src/covalent_design/training/__init__.py:34-42`
- `tests/training/test_v2_dataset.py:215-228`
- `docs/reviews/checkpoint-v2-d-foundation-gate-review-2026-06-21.md:13-16`, `200-206`

Evidence:

- The test imports `covalent_design.training.v2_dataset` after many earlier tests have already imported the module, so `before = set(sys.modules)` can hide prior imports.
- A clean subprocess shows the import introduces `covalent_design.training.train_loop`, `covalent_design.training.losses`, `covalent_design.training.checkpoints`, and `covalent_design.model.pmdm_adapter`.

Impact:

- The documented Task 49 boundary says it must remain data/training-dataset scoped and must not import model runtime modules.
- Current package facade import behavior violates that claim, even though it does not import blocked real PMDM or heavy dependencies.

Recommendation:

- Make the test use a clean subprocess, mirroring the model tests.
- Consider making `src/covalent_design/training/__init__.py` lazy, or avoid importing v1 training loop/loss/checkpoint modules at package import time.

### P1-2: `src/covalent_design/training/__init__.py` duplicates V2 dataset imports

File:

- `src/covalent_design/training/__init__.py:34-42`
- `src/covalent_design/training/__init__.py:80-88`

Evidence:

- The second block repeats the same V2 imports already present before `__all__`.

Impact:

- Not behavior-breaking, but it increases confusion in a package facade that already has import-boundary risk.

Recommendation:

- Remove the duplicate block and use this as the small cleanup point when fixing the import boundary.

### P1-3: Environment dependency status enum drifts between interface docs and implementation

File:

- `docs/v2/09-v2-interface-and-contract-changes.md:40`
- `docs/v2/04-v2-dependency-and-environment-spec.md:114-124`
- `scripts/v2_smoke_check.py:24`
- `tests/v2/test_smoke_check.py:16`
- `docs/v2/11-v2-verification-matrix.md:14`

Evidence:

- Interface doc says dependency statuses are `available`, `unavailable`, `unverified`, or `not_required`.
- Code/tests/spec matrix use `available`, `unavailable`, `not_checked`, and `failed`.

Impact:

- Consumers of `V2EnvironmentManifest` may implement against the wrong vocabulary.
- Task 50/51 manifest work could encode stale enum values.

Recommendation:

- Update `docs/v2/09-v2-interface-and-contract-changes.md` to match Task 39's frozen enum from `docs/v2/04` and code.

### P1-4: Task 50 must not inherit the v1 training loop dataset path

File:

- `src/covalent_design/training/train_loop.py:195`
- `src/covalent_design/training/dataset.py:62`
- `docs/v2/10-v2-implementation-plan.md:644-672`
- `docs/v2/11-v2-verification-matrix.md:24-25`

Evidence:

- Existing v1 smoke loop calls `prepare_dataset()`, not `prepare_v2_dataset()`.
- Window B correctly noted v1 `prepare_dataset()` does not enforce V2 license/family readiness gates.

Impact:

- If Task 50 copies the v1 loop pattern, it can bypass Task 49 entirely.

Recommendation:

- Task 50 acceptance tests must fail if the training entrypoint consumes records directly without a `V2TrainingDatasetIndex`.
- The config schema should require explicit Task 49 input artifacts or a prebuilt Task 49 index.

### P1-5: Task 49 artifact refs are preserved but not validated

File:

- `src/covalent_design/training/v2_dataset.py:454-469`
- `src/covalent_design/training/v2_dataset.py:207-220`
- `docs/v2/06-v2-training-and-tuning-spec.md:36`

Evidence:

- Task 49 converts record artifact rows into `ArtifactRef` objects and carries them forward.
- It does not verify required roles, path existence, checksum, bytes, or artifact readability.

Impact:

- This may be acceptable if Task 50 owns fail-before-tensor artifact validation, but the ownership must be explicit.
- Otherwise Task 49 can label a record eligible while the record is unusable for model batch construction.

Recommendation:

- Decide and document whether Task 49 is only eligibility selection or also validates minimum artifact roles.
- If Task 50 owns it, add Task 50 tests proving missing/unreadable artifacts fail before tensor conversion.

### P1-6: Fixture/test gaps around documented branches

File:

- `tests/training/test_v2_dataset.py`
- `src/covalent_design/training/v2_dataset.py:283-288`
- `src/covalent_design/training/v2_dataset.py:307-315`

Evidence:

- No direct test for `missing_split_assignment`.
- No direct fixture/test for family readiness `deferred` and `partial`.
- No direct test for `manual_exempt` with source-level `training_eligible=false`; this is the P0.

Impact:

- Tests pass while some documented gate branches are unproved.

Recommendation:

- Add one focused fixture or mutation test for each missing branch.

## Reconciled P2 Findings

### P2-1: `V2ExcludedRecord` lacks source/intake provenance

File:

- `src/covalent_design/training/v2_dataset.py:77-87`
- `src/covalent_design/training/v2_dataset.py:193-205`

Impact:

- Excluded audit rows require joining back to the original records to answer source/intake questions.

Recommendation:

- Consider adding `source_name` and `intake_mode` to excluded records if review/debug workflows need standalone audit output.

### P2-2: Linkage count defaulting can hide malformed zero/non-integer values

File:

- `src/covalent_design/training/v2_dataset.py:470-474`

Impact:

- Non-integer linkage counts default to 1. A malformed or zero-linkage record may look like a single-linkage record.

Recommendation:

- Later, either document the default or make invalid/missing linkage count a separate exclusion reason.

### P2-3: Current chemistry verification is lightweight only in this review

File:

- `tests/chem/test_rdkit_normalize.py`
- `tests/chem/test_rdkit_descriptors.py`
- `tests/chem/test_scaffolds.py`
- `docs/reviews/checkpoint-v2-c-chemistry-gate-review-2026-06-19.md`

Evidence:

- This run produced `18 passed, 23 skipped`.
- Heavy RDKit evidence is documented in the V2-C checkpoint but was not rerun here.

Impact:

- Not a Task 50 blocker, but do not claim fresh heavy RDKit evidence from this review.

### P2-4: `src/covalent_design/model/__init__.py` has no newline at EOF

File:

- `src/covalent_design/model/__init__.py:119`

Impact:

- Hygiene only.

## False Positives / Planned Work Not Defects

- Missing Task 50 files are not defects yet: `src/covalent_design/training/v2_train_loop.py`, `src/covalent_design/training/cli/v2_train.py`, and `configs/v2_train_*.yml` are documented as planned.
- PMDM being unavailable is not a defect. `pmdm_real_adapter.py` intentionally reports `license_unknown` and does not import PMDM.
- `non_pmdm_baseline` being a smoke path is not a defect if consumers explicitly select it and preserve `baseline_mode` / `is_pmdm`.
- RDKit-heavy tests skipping in the default environment are expected for lightweight mode.
- Old review documents that describe earlier blocked real-data states are historical artifacts. The current authoritative story must prefer the repaired review and current verification matrix, but historical reports should not be rewritten casually.
- Untracked `data/v2/` and `docs/superpowers/` are not automatically code defects, but they must not be accidentally added to a publication commit unless explicitly approved.

## Documentation-Code Drift

P0 drift:

- `docs/v2/06-v2-training-and-tuning-spec.md:27` says failed license audit excludes records. `src/covalent_design/training/v2_dataset.py:300-305` does not exclude `manual_exempt` when the license report carries `training_eligible=false`.

P1 drift:

- `docs/v2/09-v2-interface-and-contract-changes.md:40` lists stale dependency statuses. Code and Task 39 spec use `not_checked` and `failed`.
- `docs/reviews/checkpoint-v2-d-foundation-gate-review-2026-06-21.md:200-206` requires Task 49 to stay import-isolated from runtime/model modules. A clean subprocess import of `covalent_design.training.v2_dataset` currently loads v1 training loop/loss/checkpoint modules and fake PMDM adapter via the package facade.

No blocking drift found:

- Task 47 PMDM docs match code: `license_unknown`, `import_attempted=false`, no silent fallback.
- Task 48 baseline docs match code: explicit `baseline_mode="non_pmdm_baseline"`, no default success, no PMDM mode fallback.
- Chemistry docs match the lightweight-safe adapter boundary and diagnostic-only drug-likeness policy.

## Architecture Risks

The broad direction is healthy:

- `data` owns manifest/staging/conversion/license.
- `chem` owns RDKit-backed normalization, scaffold, and descriptor adapters with lazy imports and serializable results.
- `model` owns tensor conversion, PMDM boundary, and explicit baseline boundary.
- `training.v2_dataset` is intended to own eligibility selection only.

Main architectural risks:

- P0: Task 49 weakens upstream license report semantics for manual-exempt sources.
- P1: `training/__init__.py` is an eager facade over v1 training loop/loss/checkpoint modules, which makes clean import boundaries difficult to prove.
- P1: Task 50 could accidentally reuse v1 `run_smoke_train()`/`prepare_dataset()` and bypass V2 eligibility.
- P1: Artifact validation ownership between Task 49 and Task 50 is not frozen tightly enough.
- P1: Baseline and PMDM-compatible output vocabulary can be confused downstream if Task 50/51 check only tensor/output shapes.

## Test Coverage Gaps

P0 test gap:

- Add a Task 49 regression test for `manual_exempt + training_eligible=false` and assert the record is excluded.

P1 test gaps:

- Replace or supplement `test_module_does_not_import_forbidden_heavy_or_task50_modules` with a clean subprocess import test.
- Add `missing_split_assignment` coverage.
- Add family `deferred` and `partial` coverage.
- Add Task 50 start-gate tests that fail if the V2 train loop uses v1 `prepare_dataset()`.
- Add Task 50 artifact-readiness tests: missing/unreadable artifact refs should fail before tensor conversion.

P2 test gaps:

- Assert `restricted` status is preserved on eligible entries, not only that the record is eligible.
- Add malformed/non-integer/zero `linkage_count` behavior tests after deciding policy.

## Heavy Dependency Risks

- PMDM remains blocked by unknown license. This is expected and currently safe because code does not import PMDM and returns structured failure.
- PyTorch heavy behavior was partially skipped in this default run: model group had 4 skipped tests.
- RDKit-heavy behavior was skipped here: chem group had 23 skipped tests.
- No heavy dependency was installed or executed by this review.
- Task 50 must keep CPU smoke lightweight and make GPU/PMDM/RDKit-heavy paths opt-in/manual.

## Data/License/Real-Data Risks

P0:

- Task 49 can admit manual-exempt records from a failed source-level license report.

P1:

- `data/v2/` currently exists as an untracked local artifact directory with processed JSONL, reports, staging TSVs, and transform scripts. It is not tracked according to `git ls-files`, but it is visible in `git status --short`.
- This review did not rerun real ETL over `D:\codex_work\data`; do not cite this report as fresh raw-root ETL evidence.

Healthy evidence:

- Data V2 targeted tests pass.
- `v2_run_real_etl.py` writes processed artifacts only for `conversion_ok` and `license_eligible is True` at `src/covalent_design/data/cli/v2_run_real_etl.py:713-722`.
- Task 43 tests cover blocked/unknown/restricted/manual/download and provenance mismatch cases.

## PMDM/Baseline Risks

Current model boundary is structurally sound:

- `pmdm_real_adapter.py:79-105` reports PMDM unavailable without import.
- `forward_pmdm_real()` returns `PMDM_REAL_LICENSE_BLOCKED` and does not call baseline.
- `forward_non_pmdm_baseline()` defaults to `not_selected` and succeeds only with explicit `non_pmdm_baseline`.

Residual risks:

- Task 50/51 must propagate `baseline_mode`, `is_pmdm`, and warning diagnostics into training manifests/checkpoint metadata.
- Task 50 must not auto-select baseline because PMDM is blocked.
- Task 50 tests must distinguish PMDM-unavailable failure from explicitly selected baseline success.

## Task 49 / Task 50 Boundary Review

Task 49 should be a pre-training eligibility gate. It must not train, build tensors, compute masks/losses, load PMDM, or write checkpoints.

Current boundary status:

- Functionally, `prepare_v2_dataset()` itself imports only stdlib, contracts, and JSONL helpers.
- Package import behavior is not clean because `covalent_design.training.__init__` eagerly imports v1 training loop/loss/checkpoint code.
- The current Task 49 tests pass but do not prove this boundary in a clean process.
- Task 49 output is not safe enough for Task 50 because of the P0 `manual_exempt` eligibility bug.

Task 50 should consume:

- A fixed and tested `V2TrainingDatasetIndex`.
- Explicit model mode selection: `pmdm` or `non_pmdm_baseline`.
- Explicit artifact paths and fail-before-tensor validation.
- Explicit baseline diagnostics preserved into run/checkpoint manifests.

Task 50 must not consume:

- Raw finalized records directly without Task 49 gating.
- v1 `prepare_dataset()` as the training eligibility source.
- PMDM-compatible output keys as evidence that a run was real PMDM.

## Go/No-Go Verdict

Overall V2 code health: **useful but not ready for Task 50**.

Task 50 may start: **No**.

Why:

- P0 license/eligibility semantic bug exists in Task 49.
- The exact Task 50 input gate is therefore not safe.
- A passing test suite is insufficient here because the failing semantic condition is untested and was reproduced with a temporary fixture mutation.

Minimum start gate:

1. Fix Task 49 so `training_eligible=false` excludes every source status, including `manual_exempt`.
2. Add a regression test for `manual_exempt + training_eligible=false`.
3. Fix or explicitly accept the Task 49 import-boundary behavior, then update the test so it proves the actual clean import boundary.
4. Patch `docs/v2/09` dependency status enum drift.
5. Confirm `git status --short` still keeps `data/v2/` and `docs/superpowers/` untracked unless the user explicitly wants to publish them.

## Whether Task 50 May Start

**No, not yet.**

Allowed next work:

- Patch Task 49 eligibility logic and tests.
- Patch docs drift.
- Clean up package facade/import-boundary tests.
- Re-run the same targeted verification.

Not allowed yet:

- Implementing `v2_train_loop.py`.
- Creating Task 50 configs.
- Running training.
- Treating current Task 49 output as training-safe.

## Required Fix Prompt Guidance

Use this fix prompt sequence:

1. **test-driven-development + code-review-and-quality**
   - Add a failing Task 49 test for `manual_exempt` license report entry with `training_eligible=false`.
   - Expected behavior: record is excluded, envelope remains deterministic, exclusion reason is explicit.

2. **api-and-interface-design**
   - Freeze the exact exclusion reason name for source-level failed audits, especially for `manual_exempt`.
   - Decide whether `V2ExcludedRecord` should include source reason codes from `LicenseGateReport`.

3. **incremental-implementation**
   - Patch only `src/covalent_design/training/v2_dataset.py` and the focused tests first.
   - Keep the fix independent from Task 50.

4. **improve-codebase-architecture**
   - Address `training/__init__.py` import eagerness and duplicate V2 imports.
   - Replace the Task 49 import-boundary test with a subprocess version.

5. **documentation-and-adrs**
   - Update `docs/v2/09-v2-interface-and-contract-changes.md` dependency status enum.
   - Update Task 49 docs only if the exact exclusion reason vocabulary changes.
   - No new ADR is required unless the manual-exempt semantics change beyond "respect training_eligible".

6. **doubt-driven-development**
   - Re-run an adversarial review after the patch: mutate upstream reports, invert booleans, remove split assignments, and verify no failed gate can become eligible.

Suggested verification after fixes:

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/training/test_v2_dataset.py -q
python -m pytest tests/data/test_v2_manifests.py tests/data/test_v2_intake.py tests/data/test_v2_conversion.py tests/data/test_v2_license.py tests/data/test_v2_real_etl_cli.py -q
python -m pytest tests/model/test_torch_backend.py tests/model/test_pmdm_real_adapter.py tests/model/test_non_pmdm_baseline.py -q
python -m pytest tests/v2/test_smoke_check.py -q
python scripts/v2_smoke_check.py --profile lightweight
python -m compileall -q scripts src
git status --short
```
