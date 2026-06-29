# Checkpoint V2-F Sampling And Evaluation Gate Review

Date: 2026-06-29

Mode: read-only gate review. No source, test, config, ADR, V2 spec, data, or `data/v2` files were modified. This report is the only new file produced by the checkpoint review.

## 1. Review Scope

Checkpoint V2-F asks whether held-out/per-family sampling and evaluation reports are auditable before Task 57 starts.

Reviewed task range:

- Task 53: V2 sampling request/result contracts.
- Task 54: deterministic fixture sampling smoke.
- Task 55: V2 evaluation metrics report.
- Task 56: docking feasibility report.

This review does not start Task 57, does not implement new sampling/evaluation/docking/training behavior, does not download data, and does not run real docking.

## 2. Documents Reviewed

- `CONTEXT.md`
- `docs/v2/00-v2-project-map.md`
- `docs/v2/04-v2-dependency-and-environment-spec.md`
- `docs/v2/07-v2-sampling-and-evaluation-spec.md`
- `docs/v2/10-v2-implementation-plan.md`
- `docs/v2/11-v2-verification-matrix.md`
- `docs/v2/12-v2-risk-register.md`
- `docs/reviews/task53-v2-sampling-request-result-review-2026-06-24.md`
- `docs/reviews/task54-v2-deterministic-sampling-smoke-review-2026-06-24.md`
- `docs/reviews/task55-v2-evaluation-metrics-review-2026-06-26.md`
- `docs/reviews/task56-v2-docking-feasibility-review-2026-06-26.md`

## 3. Code And Test Files Reviewed

- `src/covalent_design/inference/v2_sampling.py`
- `src/covalent_design/evaluation/v2_metrics.py`
- `src/covalent_design/evaluation/v2_docking_feasibility.py`
- `src/covalent_design/evaluation/cli/v2_evaluate.py`
- `src/covalent_design/evaluation/__init__.py`
- `tests/inference/test_v2_sampling.py`
- `tests/inference/test_v2_sampling_smoke.py`
- `tests/evaluation/test_v2_metrics.py`
- `tests/evaluation/test_v2_docking_feasibility.py`
- `tests/fixtures/v2/sampling/`
- `tests/fixtures/v2/evaluation/`
- `tests/fixtures/v2/docking_feasibility/`
- `configs/v2_sampling_smoke.yml`

## 4. Commands Run

All Python commands were run with `PYTHONPATH=src`.

- `$env:PYTHONPATH='src'; python -m pytest tests/inference/test_v2_sampling.py -q`
- `$env:PYTHONPATH='src'; python -m pytest tests/inference/test_v2_sampling_smoke.py -q`
- `$env:PYTHONPATH='src'; python -m pytest tests/evaluation/test_v2_metrics.py -q`
- `$env:PYTHONPATH='src'; python -m pytest tests/evaluation/test_v2_docking_feasibility.py -q`
- `$env:PYTHONPATH='src'; python -m covalent_design.evaluation.cli.v2_evaluate --help`
- `$env:PYTHONPATH='src'; python -m compileall -q scripts src`
- `rg -n "D:\\\\codex_work\\\\data|data/v2" src/covalent_design/inference src/covalent_design/evaluation tests/inference tests/evaluation docs/v2/07-v2-sampling-and-evaluation-spec.md`
- `rg -n "rdkit|torch|cuda|PMDM|PocketFlow|pmdm|pocketflow|vina|smina|gnina|autodock|dock6|qvina|quickvina" src/covalent_design/inference src/covalent_design/evaluation tests/inference tests/evaluation`
- `rg -n "real docking|execute docking|run docking|docking output|pdbqt|dock score|vina score|binding affinity|potency|toxicity|selectivity|clinical" src/covalent_design/inference src/covalent_design/evaluation tests/inference tests/evaluation docs/v2/07-v2-sampling-and-evaluation-spec.md`
- `git status --short`
- `git ls-files | rg "^(data/v2/|docs/superpowers/)"`

## 5. Command Results

- `tests/inference/test_v2_sampling.py`: pass, 26 passed.
- `tests/inference/test_v2_sampling_smoke.py`: pass, 18 passed.
- `tests/evaluation/test_v2_metrics.py`: pass, 10 passed.
- `tests/evaluation/test_v2_docking_feasibility.py`: pass, 10 passed.
- `python -m covalent_design.evaluation.cli.v2_evaluate --help`: pass; CLI help printed successfully.
- `python -m compileall -q scripts src`: pass.
- Data-root grep: no matches.
- Heavy/docking-term grep: matches found only in existing v1-era tests/modules, explicit no-heavy-import guard tests, `non_pmdm_baseline` strings, RDKit-evidence field names, and docking-protocol fixture strings. No Task 53-56 hard import or real execution path was found.
- Scientific-claim grep: matches found in existing v1 docking protocol fixtures and boundary docstrings such as "No real docking execution." No Task 53-56 scientific performance claim was found.
- `git ls-files | rg "^(data/v2/|docs/superpowers/)"`: no tracked files matched.

## 6. Task 53 Evidence Summary

Claude Code Window A reviewed Task 53 read-only and returned PASS.

Evidence:

- `V2SamplingRequest` and `V2SamplingResult` are deterministic contract objects.
- Request validation returns structured `V2_SAMPLING_*` errors through `ContractEnvelope`.
- Checkpoint, checkpoint manifest, and environment manifest refs are explicit `ArtifactRef` fields.
- Count conservation is enforced for result counts.
- Failure taxonomy separates request validation, system failure, invalid generated sample, export failure, docking-not-run, and evaluation artifact corruption.
- Task 53 does not execute true sampling, model forward, export, docking, evaluation, real-data-root access, or artifact generation.

Findings:

- P0: none.
- P1: none.
- P2: `ContractErrorInfo.location` remains unset for flat request errors; individual diagnostic serializers are tested transitively rather than standalone.

## 7. Task 54 Evidence Summary

Claude Code Window B reviewed Task 54 read-only and returned PASS.

Evidence:

- Same seed produces identical deterministic fixture sampling output and hash.
- Different seed changes output.
- Train, val, test, per-family, and explicit record-id selectors are tested.
- Invalid decode and system failures remain separate.
- Empty selection fails closed through system-failure accounting.
- Smoke runner does not create output roots, mmCIF, docking, or evaluation artifacts.
- No hard RDKit/PyTorch/PMDM/PocketFlow import or real-data-root access was found.

Findings:

- P0: none.
- P1: none.
- P2: none blocking.

## 8. Task 55 Evidence Summary

Claude Code Window C reviewed Task 55 read-only and returned PASS.

Evidence:

- Evaluation report serialization and hash are deterministic.
- CLI help and CLI JSON path are available.
- Report includes validity, family coverage, geometry, uniqueness/novelty, optional RDKit-evidence summary, docking status, and failure accounting.
- Denominator mismatch returns structured `V2_EVALUATION_DENOMINATOR_MISMATCH`.
- Optional unavailable evidence is `status: "not_evaluable"` with a reason, not a negative model-performance result.
- The module does not write artifacts, hard import heavy dependencies, read real-data roots, or make scientific performance claims.

Findings:

- P0: none.
- P1: none.
- P2: `load_v2_sampling_result_file` maps denominator mismatch via current count-error wording; covered by regression tests but should remain watched if upstream exception text changes.

## 9. Task 56 Evidence Summary

Claude Code Window D reviewed Task 56 read-only and returned PASS.

Evidence:

- Docking feasibility is evidence-only.
- Report records engine candidate/status, license, install path or missing reason, CLI/API probe status, input/output support, and probe duration.
- Missing engine is `not_evaluable`.
- Failed probe and unknown license are non-blocking.
- Invalid feasible claims fail with `V2_DOCKING_FEASIBILITY_CLAIM_INVALID`.
- No real docking execution, docking output, engine installation, subprocess probing, heavy hard import, or real-data access was found.
- The report is not a docking result and includes no binding-affinity, pose-score, selectivity, toxicity, clinical, or publication-performance claim.

Findings:

- P0: none.
- P1: none.
- P2: future host-engine probing must be explicitly scoped outside Task 56.

## 10. Cross-Cutting Boundary Checks

Claude Code Window E reviewed cross-cutting V2-F consistency and found one P1 documentation drift.

Boundary checks:

- Task 53-56 code and tests preserve the distinction between contract, deterministic smoke, metrics report, and feasibility report.
- `not_evaluable` is consistently used for unavailable optional evidence or missing feasibility evidence.
- Fixture/smoke/lightweight evidence is not described as real scientific performance evidence.
- No tracked `data/v2/` or `docs/superpowers/` files were found.

## 11. Fixture/Smoke/Lightweight/Heavy-Manual Distinction

- Task 53 is package-interface contract evidence only.
- Task 54 is deterministic fixture smoke evidence only.
- Task 55 is fixture/evidence-contract metrics reporting only.
- Task 56 is docking feasibility evidence only.
- Heavy/manual evidence remains separate from lightweight CI evidence.
- V2-F does not claim real stochastic model sampling, real docking, complete real-data evaluation, or scientific model quality.

## 12. Real Data Access Status

No Task 53-56 code path reviewed here reads `D:\codex_work\data` or `data/v2`.

`data/v2/` is present as an untracked workspace directory in `git status --short`, but `git ls-files | rg "^(data/v2/|docs/superpowers/)"` returned no tracked files. The review did not read or modify `data/v2/` or `D:\codex_work\data`.

## 13. Heavy Dependency Status

Task 53-56 lightweight code paths do not hard import RDKit, PyTorch, CUDA, PMDM, PocketFlow, or docking engines.

The broad grep command reports existing references in v1-era tests/modules, no-heavy-import guard tests, `non_pmdm_baseline`, and optional RDKit-evidence field names. These are not hard imports in the V2-F lightweight path.

## 14. Docking Execution Status

No real docking execution was found in Task 53-56 V2-F code paths.

Task 55 reports docking evaluation as `not_evaluable` or not-run evidence. Task 56 reports feasibility evidence and explicitly does not execute docking or produce docking output.

## 15. Scientific Claim Boundary

No Task 53-56 artifact reviewed here claims binding affinity, potency, toxicity, selectivity, clinical efficacy, docking score performance, or publication-quality scientific model performance.

The reviewed outputs remain auditability reports over fixtures and explicit evidence.

## 16. Artifact/Git Tracking Boundary

Current `git status --short` includes expected modified/untracked implementation work:

- Modified V2 Task 56 docs and evaluation facade.
- Untracked Task 56 source, tests, fixtures, and Task 56 review report.
- Untracked `data/v2/`.
- Untracked `docs/superpowers/`.

No tracked `data/v2/` or `docs/superpowers/` files were found.

## 17. P0 Findings

None.

## 18. P1 Findings

### P1-1: V2-F checkpoint row remains `planned` in the verification matrix

- File: `docs/v2/11-v2-verification-matrix.md`
- Evidence: the Task 53-56 rows are `verified-lightweight`, but the row `V2-F Sampling And Evaluation Gate` still has gate status `planned`.
- Why it matters: the checkpoint cannot be formally presented as closed while the canonical verification matrix still says the checkpoint is planned.
- Required fix: update the V2-F row after this review is accepted, marking the gate as verified with the appropriate date and lightweight/heavy-manual semantics.

## 19. P2 Findings

- P2-1: `data/v2/` and `docs/superpowers/` remain untracked local workspace directories. This is correct under current policy, but still needs hygiene awareness before any commit or push.
- P2-2: `src/covalent_design/evaluation/__init__.py` exports Task 55/56 symbols but its top docstring still describes older Task 30-33 evaluation modules only. This is cosmetic.
- P2-3: Task 53 flat validation errors do not set field-level `ContractErrorInfo.location`. Non-blocking.
- P2-4: Task 55 denominator mismatch mapping relies on current count-error wording. Covered by tests, but worth keeping stable.

## 20. Required Fixes Before Task 57

1. Update `docs/v2/11-v2-verification-matrix.md` so `V2-F Sampling And Evaluation Gate` is no longer `planned`.
2. Re-run the V2-F final verification commands after that docs-only update.
3. Confirm no `data/v2/` or `docs/superpowers/` files are accidentally staged or tracked.

## 21. Recommended Fixes After Task 57

- Consider updating `src/covalent_design/evaluation/__init__.py` docstring to mention V2 metrics and docking feasibility exports.
- Keep Task 56 host-engine probing as a future explicitly scoped task, not an implication of the feasibility report.
- Preserve the fixture/smoke/lightweight/heavy-manual vocabulary in Task 57 prompts and reviews.

## 22. Final Go/No-Go Verdict

Checkpoint V2-F status: NO-GO for formal closure until the verification matrix P1 drift is repaired.

Technical evidence status: PASS. Task 53, Task 54, Task 55, and Task 56 targeted tests pass, CLI help passes, compileall passes, and no P0 technical boundary violation was found.

Reason for NO-GO: the canonical verification matrix still marks `V2-F Sampling And Evaluation Gate` as `planned`, which conflicts with the task-level verified evidence and must be corrected before declaring the checkpoint closed.

## 23. Whether Task 57 May Start

Task 57 may not start yet.

Task 57 may start after:

1. The V2-F verification matrix row is updated.
2. The final V2-F verification commands are re-run.
3. The controller confirms the updated checkpoint status.
