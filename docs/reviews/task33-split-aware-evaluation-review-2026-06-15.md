# Task 33 Split-Aware Evaluation Review

Date: 2026-06-15

Scope: Task 33 split-aware evaluation reports only. This review does not start
Checkpoint C and does not implement Task 34+ work.

## Reviewed Files

- `src/covalent_design/evaluation/split_metrics.py`
- `src/covalent_design/evaluation/reports.py`
- `src/covalent_design/evaluation/__init__.py`
- `tests/evaluation/test_split_reports.py`
- `tests/fixtures/evaluation/split_reports/`
- `docs/specs/04-evaluation.md`
- `docs/specs/interface-design.md`
- `docs/specs/implementation-plan.md`
- `docs/specs/verification-matrix.md`
- `docs/specs/key-design-decisions.md`

## Findings

Blocking findings: none.

Non-blocking findings from the final child review:

- Split-index validation reports only the first missing required field per
  assignment. This is acceptable because the spec requires failure, not
  exhaustive per-row diagnostics.
- `_deep_sort` does not recurse into list elements. Current Task 33 lists are
  scalar strings, so this is not a current defect.
- The `per_split` dataclass annotation is broader than the serialized shape.
  Runtime behavior and tests are correct.
- Lifecycle counting relies on the invariant that every result was validated
  before aggregation. A comment was added and regression tests cover corrupt
  lifecycle rejection before aggregation.

## Acceptance Checks

- Frozen join key is `CovalentGenerationResult.request_id ==
  split_index.assignments[].record_id`.
- No external request-record map, `(request_id, sample_id)` matching,
  sample-id fallback, fuzzy matching, or directory scanning.
- Split index validation covers schema version, contract version, role,
  assignment count, duplicate record id, split enum, and required assignment
  fields.
- Leakage report validation covers schema version, contract version, role,
  cross-validated split counts, and boolean `zero_overlap` flags.
- Every result is checked by `validate_generation_result` before aggregation.
- Per-split summaries are `EvaluationSummary`-compatible for train/val/test.
- Per-family summaries use canonical `residue_reaction_family`.
- Scaffold and protein-cluster primary metrics are sourced from split index and
  emitted deterministically.
- Leakage blocking risk is explicit for scaffold and protein-cluster overlap.
- Excluded, fallback, and manual-review accounting are deterministic and
  auditable.
- Optional docking index counts are optional; absent docking is valid.
- Writer is deterministic and atomic and returns
  `ArtifactRef(role="stratified_evaluation_summary")`.
- No CLI, split regeneration, Checkpoint C execution, RDKit, torch, PMDM,
  PocketFlow, or docking engine behavior was added.

## Verification

Commands run:

- `python -m unittest tests.evaluation.test_split_reports -v` - pass
- `python -m unittest tests.evaluation.test_docking_protocol -v` - pass
- `python -m unittest tests.evaluation.test_lifecycle_reports -v` - pass
- `python -m unittest tests.evaluation.test_denominator_accounting -v` - pass
- `python -m unittest tests.contracts.test_lifecycle -v` - pass
- `python -m unittest tests.contracts.test_denominators -v` - pass
- `python -m unittest tests.data.test_splits -v` - pass
- `python -m unittest tests.data.test_splits_contracts -v` - pass
- `python -m unittest discover -s tests -t . -q` - pass, 1614 tests
- `python -m compileall -q scripts src` - pass
- `git diff --check` - pass, with existing line-ending warnings only

## Decision

Task 33 is complete and may proceed to Checkpoint C review.
