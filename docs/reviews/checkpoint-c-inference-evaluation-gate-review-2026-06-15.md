# Checkpoint C: Inference And Evaluation Gate Review

Date: 2026-06-15

Scope: Tasks 26-33 inference and evaluation gate verification. This review did not start Task 34 and did not add new CLI, model, training, inference, or evaluation feature code.

## Dependency Scope

- Task 26 request validation
- Task 27 sampling failure lifecycle
- Task 28 result writer lifecycle
- Task 29 complex export / mmCIF writer boundary
- Task 30 denominator accounting
- Task 31 lifecycle and failure-mode reports
- Task 32 docking protocol accounting
- Task 33 split-aware evaluation reports

## Collaboration Evidence

- Window A produced a read-only gate matrix and highlighted missing executable evidence risks.
- Window B and Window C produced read-only static plans/reviews for inference and evaluation scope. Their internal shell execution was unavailable, so the main controller ran all required tests directly.
- Window D produced a report plan used for this gate report.
- Window E final review was run after this report was written.

## Commands Run

All commands were run with `PYTHONPATH=src`.

- `python -m unittest tests.inference.test_request_validation -v`: passed, 72 tests.
- `python -m unittest tests.inference.test_sampling_failures -v`: passed, 35 tests.
- `python -m unittest tests.inference.test_result_writer -v`: passed, 67 tests.
- `python -m unittest tests.inference.test_complex_export -v`: passed, 47 tests.
- `python -m unittest tests.evaluation.test_denominator_accounting -v`: passed, 97 tests.
- `python -m unittest tests.evaluation.test_lifecycle_reports -v`: passed, 78 tests.
- `python -m unittest tests.evaluation.test_docking_protocol -v`: passed, 83 tests.
- `python -m unittest tests.evaluation.test_split_reports -v`: passed, 28 tests.
- `python -m unittest tests.contracts.test_lifecycle -v`: passed, 10 tests.
- `python -m unittest tests.contracts.test_denominators -v`: passed, 5 tests.
- `python -m unittest tests.data.test_splits -v`: passed, 56 tests.
- `python -m unittest tests.data.test_splits_contracts -v`: passed, 29 tests.
- `python -m unittest discover -s tests -t . -q`: passed, 1614 tests.
- `python -m compileall -q scripts src`: passed.
- `python -m covalent_design.evaluation.summarize_results --manifest <temp-copy>/run_manifest.yml`: passed.
- `python -m covalent_design.evaluation.check_denominators --manifest <temp-copy>/run_manifest.yml`: passed.
- `rg` forbidden import guard for `rdkit`, `torch`, `PMDM`, `PocketFlow`, `pmdm`, and `pocketflow` under inference/evaluation and structure/mmCIF IO: no matches.
- `git status --short`: dirty workspace with expected tracked and untracked Task 30-33 files.
- `git diff --stat`: reviewed.
- `git diff --check`: passed with line-ending warnings only.

## Request Validation Evidence

`tests.inference.test_request_validation` passed. Evidence covers valid JSON/YAML request parity, normalized request output, request contract validation, and rule-table version propagation.

Gate status: pass.

## Sampling Failure Evidence

`tests.inference.test_sampling_failures` passed. Evidence covers the frozen `SamplingSystemFailure` schema, retry policy validation, timestamp validation, and retry category handling.

Gate status: pass.

## Result Writer Evidence

`tests.inference.test_result_writer` passed. Evidence covers valid/invalid generation lifecycle rows, docking/export state consistency, covalent versus noncovalent score separation, and result row schema behavior.

Gate status: pass.

## mmCIF Export Evidence

`tests.inference.test_complex_export` passed. Evidence covers structure reader and writer importability, deterministic atom ordering, ligand atom naming, exported artifact refs, and rejection of invalid generation results. No RDKit dependency was imported or required.

Gate status: pass.

## Denominator Accounting Evidence

`tests.evaluation.test_denominator_accounting` passed. Evidence covers denominator conservation, sampling system failure accounting, result lifecycle reuse, CLI summary generation, and contract validation.

The CLI temp-copy check wrote `evaluation_summary.json` only under a temporary copy of `tests/fixtures/evaluation/denominator_accounting/valid_mixed`; no fixture pollution was detected.

Gate status: pass.

## Lifecycle And Failure-Mode Evidence

`tests.evaluation.test_lifecycle_reports` and `tests.contracts.test_lifecycle` passed. Evidence covers lifecycle report shape, failure-mode buckets, deterministic report writes, atomic write behavior, and generation-result lifecycle validation.

Gate status: pass.

## Docking Protocol Evidence

`tests.evaluation.test_docking_protocol` passed. Evidence covers docking-score eligible result selection, summary validation, deterministic report writing, no directory-scanning inference, no real docking imports, and no heavy dependency loading.

Gate status: pass.

## Split-Aware Evaluation Evidence

`tests.evaluation.test_split_reports`, `tests.data.test_splits`, and `tests.data.test_splits_contracts` passed. Evidence covers split index validation, train/val/test/excluded accounting, leakage checks, split metrics, and report API importability.

Gate status: pass.

## Full Regression Evidence

The full unittest suite passed:

- `Ran 1614 tests in 36.038s`
- `OK`

`compileall` over `scripts` and `src` passed.

Gate status: pass.

## Blocking Findings

None.

Window A initially flagged missing executable gate evidence and absence of a single gate document. The main controller resolved those risks by running the full Checkpoint C command set directly, executing the CLI temp-copy checks, and writing this gate review report.

## Non-Blocking Findings

- Subwindow B/C shell execution was unavailable inside those windows. The main controller executed the required test commands directly and recorded the evidence here.
- `git diff --check` reported line-ending warnings for existing working-tree files. It did not report whitespace errors.
- The workspace remains dirty with tracked and untracked Task 30-33 files, review docs, prompts, tests, and fixtures. No staging or commit was performed.

## Residual Risks

- No blocking Task 34 risk remains from Checkpoint C based on the executed tests and source guards.
- The dirty workspace should be reviewed and staged intentionally before any commit.

## Decision

Checkpoint C decision: PASS.

Task 34 may start after main-controller confirmation.
