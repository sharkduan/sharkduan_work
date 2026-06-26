# Checkpoint V2-D: Tensor / PMDM / Baseline Foundation Gate Review

Date: 2026-06-21

## Executive Summary

Overall Status: PASS WITH RISKS

Checkpoint V2-D may be accepted as the foundation gate for the next phase, but this review does not start Task 49. The core gate evidence is present: Task 46 exposes tensor conversion behind a bounded adapter, Task 47 keeps real PMDM blocked as structured `license_unknown` unavailability, and Task 48 provides an explicit `non_pmdm_baseline` path without silently replacing PMDM mode.

Largest residual risks:

- PMDM remains unavailable because license status is still `unknown`; this is an explicit block, not a bypass.
- There is no full-stack PMDM dependency lock or graph-dependency execution path yet.
- Future consumers in Task 49/50/51 still need explicit mode guards so `non_pmdm_baseline` cannot be treated as PMDM by mistake.
- Task 49 must remain data/training-dataset scoped and must not import or execute tensor, PMDM, or baseline runtime modules.

## Scope

Reviewed:

- `src/covalent_design/model/torch_backend.py`
- `src/covalent_design/model/pmdm_real_adapter.py`
- `src/covalent_design/model/non_pmdm_baseline.py`
- `tests/model/test_torch_backend.py`
- `tests/model/test_pmdm_real_adapter.py`
- `tests/model/test_non_pmdm_baseline.py`
- `docs/v2/06-v2-training-and-tuning-spec.md`
- `docs/v2/09-v2-interface-and-contract-changes.md`
- `docs/v2/10-v2-implementation-plan.md`
- `docs/v2/11-v2-verification-matrix.md`
- `docs/v2/12-v2-risk-register.md`
- `docs/v2/dependency-source-verification.md`
- `docs/adr/0037-v2-environment-and-heavy-dependency-boundary.md`

Out of scope:

- Task 49 implementation.
- Training dataset, training loop, sampling, inference, and evaluation.
- PMDM/PocketFlow installation or execution.
- Access to `D:\codex_work\data`.
- New feature code in `src/` or `tests/`.

## Evidence Table

| Area | Status | Evidence |
| --- | --- | --- |
| Task 46 tensor boundary | Pass | Lightweight tests pass; heavy `covalent-design-v2` evidence verifies PyTorch conversion and CUDA availability while public contracts remain serializable. |
| Task 47 PMDM smoke boundary | Pass | `check_pmdm_available()` reports structured unavailable with `license_status=unknown`, `reason=license_unknown`, and `import_attempted=false`; PMDM mode does not silently fall back. |
| Task 48 baseline boundary | Pass with risks | Baseline path is explicitly labeled `baseline_mode=non_pmdm_baseline`, carries `is_pmdm=false`, and warns that baseline is not PMDM. Future consumer-side guards remain necessary. |
| Default CI profile | Pass | Lightweight commands do not hard-import PMDM, PocketFlow, RDKit, PyTorch, CUDA graph dependencies, or real-data roots. |
| Public payloads | Pass | Task 46/47/48 public payloads are project-owned serializable metadata, not raw heavy runtime objects. |
| Sequencing | Pass | Current phase remains Checkpoint V2-D; Task 49 is not started by this review. |

## Commands Executed

Baseline commands run by the controller before report writing:

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/model/test_torch_backend.py tests/model/test_pmdm_real_adapter.py tests/model/test_non_pmdm_baseline.py -q
```

Result: 42 passed, 4 skipped.

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/model -q
```

Result: 278 passed, 4 skipped.

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/v2/test_smoke_check.py -q
```

Result: 11 passed.

```powershell
$env:PYTHONPATH='src'
python scripts/v2_smoke_check.py --profile lightweight
```

Result: exit 0, JSON `overall_status` was `pass`; heavy dependencies were `not_checked`.

```powershell
$env:PYTHONPATH='src'
python -m compileall -q scripts src
```

Result: pass.

Task 48 heavy cross-check evidence recorded before this checkpoint:

```powershell
$env:PYTHONPATH='src'
conda run -n covalent-design-v2 python -m pytest tests/model/test_non_pmdm_baseline.py -q
```

Result: 15 passed.

## Task 46 Tensor Review

Verdict: PASS for V2-D tensor criterion.

Findings:

- P0: none.
- P1: none blocking V2-D.
- P2: batch-size mismatch, non-`BatchTensors` guard, and conversion catch-all branches could use direct tests later.

Evidence:

- `torch_backend` keeps PyTorch behind lazy import and reports structured unavailability in lightweight mode.
- `TorchTensorBatch` is an internal runtime object; public payloads use serializable tensor specs.
- Heavy verification in the `covalent-design-v2` environment confirms real PyTorch conversion without making the default profile heavy.
- No PMDM/PocketFlow import, real-data access, or training artifacts are part of Task 46.

## Task 47 PMDM Review

Verdict: PASS for V2-D PMDM criterion.

Findings:

- P0: none.
- P1: none.
- P2: additional negative tests could assert real-data root non-access and fake raw heavy-object rejection, but current module does not open files or expose raw heavy objects.

Evidence:

- PMDM remains structured unavailable with `license_status=unknown`.
- `check_pmdm_available()` does not import PMDM.
- `forward_pmdm_real()` returns `PMDM_REAL_LICENSE_BLOCKED` rather than falling back to baseline mode.
- Required PMDM-compatible key vocabulary remains explicit.
- No hard import of PMDM, PocketFlow, PyTorch, RDKit, or PyG exists in the PMDM smoke boundary.

## Task 48 Baseline Review

Verdict: PASS WITH RISKS for V2-D baseline criterion.

Findings:

- P0: none.
- P1: future consumers still need cross-module guards proving PMDM code never calls Task 48 as an implicit fallback.
- P1: `V2EnvironmentManifest.baseline_mode` propagation is not yet exercised end-to-end; this belongs to later manifest/checkpoint tasks.
- P2: alias and optional-pair-feature branches could use additional narrow tests later.

Evidence:

- Baseline output is labeled `baseline_mode=non_pmdm_baseline`.
- Baseline output carries `is_pmdm=false`.
- Baseline warnings state that the baseline is not PMDM.
- Baseline selection is explicit; omitted, PMDM, and unknown modes fail structured.
- Output uses the PMDM-compatible smoke vocabulary without importing or executing PMDM.

## Cross-Mode Integration Review

Verdict: PASS WITH RISKS.

The three paths are distinguishable at the producer boundary:

- Tensor conversion is an adapter boundary.
- PMDM mode is license-blocked and does not silently fall back.
- Baseline mode is explicit and labeled as non-PMDM.

Residual integration risk remains at future consumers: Task 49/50/51 must check mode fields such as `baseline_mode` and `is_pmdm`, not only the presence of PMDM-compatible output keys.

## Findings By Severity

### P0

None.

### P1

- PMDM remains blocked by `license_unknown`; this is acceptable for V2-D only because it is structured and not bypassed.
- No full-stack PMDM lock or graph-dependency execution path exists yet.
- Future consumer-side guards are required so `non_pmdm_baseline` is never treated as PMDM.
- Task 49 must stay data/training-dataset scoped and import-isolated from tensor, PMDM, and baseline runtime modules.

### P2

- Task 46 has minor untested negative branches.
- Task 47 has minor symmetry gaps around explicit non-access and raw-object rejection tests.
- Task 48 has minor untested alias and optional-feature branches.
- A future cross-module integration test should exercise Task 46/47/48 together before training-loop work.

## Residual Risks

- PMDM remains license-blocked and unavailable for execution.
- Heavy PMDM graph dependencies are not installed or locked.
- Baseline mode is explicit at the producer, but later consumers still need explicit guards.
- Task 49 can proceed only if it remains a training dataset task and does not import model runtime modules.

## Go/No-Go Verdict

Checkpoint V2-D verdict: PASS WITH RISKS.

Task 49 may be the next phase after user confirmation, but this review does not enter Task 49. Task 49 must preserve the V2-D boundary:

- Do not import or execute PMDM.
- Do not import Task 46/47/48 runtime modules unless explicitly required by a later scoped task.
- Do not treat `non_pmdm_baseline` as PMDM.
- Do not silently fall back from PMDM blocked/unavailable to baseline success.
- Keep default CI lightweight.

## Final Verification Status

Final controller verification completed after report and documentation sync:

| Command | Result |
| --- | --- |
| `python -m pytest tests/model/test_torch_backend.py tests/model/test_pmdm_real_adapter.py tests/model/test_non_pmdm_baseline.py -q` | 42 passed, 4 skipped |
| `python -m pytest tests/model -q` | 278 passed, 4 skipped, 31 subtests passed |
| `python -m pytest tests/v2/test_smoke_check.py -q` | 11 passed |
| `python scripts/v2_smoke_check.py --profile lightweight` | exit 0; `overall_status=pass`; heavy dependencies `not_checked` |
| `python -m compileall -q scripts src` | pass |
| `python -m pytest -q` | 1992 passed, 27 skipped, 326 subtests passed |
| `python -m unittest discover -s tests -t . -q` | 1761 tests, OK |
| `conda run -n covalent-design-v2 python -m pytest tests/model/test_torch_backend.py tests/model/test_pmdm_real_adapter.py tests/model/test_non_pmdm_baseline.py -q` | 46 passed |

Final gate review found no P0 blocker and returned GO / PASS WITH RISKS. Checkpoint V2-D is accepted with the residual risks listed above. Task 49 may proceed only after user confirmation and must preserve the data-only/import-isolated boundary stated in this report.
