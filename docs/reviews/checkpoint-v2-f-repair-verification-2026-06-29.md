# Checkpoint V2-F Repair Verification

Date: 2026-06-29

Scope: repair the Checkpoint V2-F review P1 that left the V2-F row in `docs/v2/11-v2-verification-matrix.md` marked as `planned`.

## Summary

Checkpoint V2-F Repair PASS.

Checkpoint V2-F may be formally closed.

Task 57 may start only after controller/user confirmation.

## Change Made

- Updated `docs/v2/11-v2-verification-matrix.md`.
- Changed `V2-F Sampling And Evaluation Gate` from `planned` to `verified-2026-06-29`.
- Added the checkpoint review report path: `docs/reviews/checkpoint-v2-f-sampling-and-evaluation-gate-review-2026-06-29.md`.
- Recorded the targeted Task 53-56 commands, CLI help command, compileall command, and git tracking boundary command.
- Preserved the distinction that V2-F evidence is fixture/smoke/lightweight evidence only and heavy/manual evidence remains separate.
- Explicitly retained the boundary: no real-data access, no real docking execution, no heavy hard imports, and no scientific-performance claim.

No source code, tests, configs, ADRs, Task 57 documents, data directories, or real-data artifacts were changed for this repair.

## Claude Code Collaboration

Claude Code windows were attempted through `codex-claude-docs.ps1` with `-ExcludeDynamicSystemPromptSections`.

The attempted read/review windows failed with `API Error: 402 Insufficient Balance`. The main controller therefore took over under the repair prompt's takeover rules and performed the minimal docs-only fix and verification.

## Verification Commands

All Python commands were run with `PYTHONPATH=src`.

- `$env:PYTHONPATH='src'; python -m pytest tests/inference/test_v2_sampling.py -q`: pass, 26 passed
- `$env:PYTHONPATH='src'; python -m pytest tests/inference/test_v2_sampling_smoke.py -q`: pass, 18 passed
- `$env:PYTHONPATH='src'; python -m pytest tests/evaluation/test_v2_metrics.py -q`: pass, 10 passed
- `$env:PYTHONPATH='src'; python -m pytest tests/evaluation/test_v2_docking_feasibility.py -q`: pass, 10 passed
- `$env:PYTHONPATH='src'; python -m covalent_design.evaluation.cli.v2_evaluate --help`: pass
- `$env:PYTHONPATH='src'; python -m compileall -q scripts src`: pass
- `git diff --check`: pass, line-ending warnings only
- `git ls-files | rg "^(data/v2/|docs/superpowers/)"`: pass, no tracked files matched

## Repair Checks

- V2-F row is no longer `planned`.
- V2-F row references the checkpoint review report.
- V2-F row lists Task 53-56 targeted tests.
- V2-F row lists `v2_evaluate --help` and compileall.
- V2-F row states fixture/smoke/lightweight evidence only.
- V2-F row states heavy/manual evidence remains separate.
- V2-F row does not imply real model sampling, real docking, or scientific performance.
- No Task 57 document was modified.
- No `src/covalent_design/pretraining/` or `tests/pretraining/` path exists.
- No `data/v2/` or `docs/superpowers/` file is tracked by git.

## Remaining P2

- `data/v2/` and `docs/superpowers/` remain untracked local workspace directories; this is correct under current policy but must be checked before any staging or push.
- `src/covalent_design/evaluation/__init__.py` top docstring still omits V2 metrics and docking feasibility. This was left deferred because it is cosmetic and outside the P1 repair.
- Task 53 flat request validation still leaves `ContractErrorInfo.location` unset. Non-blocking.
- Task 55 denominator mismatch mapping should remain covered if upstream count-error wording changes. Non-blocking.

## Final Verdict

Checkpoint V2-F Repair PASS.

Checkpoint V2-F may be formally closed.

Task 57 may start only after controller/user confirmation.
