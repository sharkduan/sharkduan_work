# Task 31 Lifecycle Reports Review

Date: 2026-06-03

## Scope

Task 31 implements lifecycle validation and failure-mode reports only. It does
not implement Task 32 docking protocol validation or Task 33 split-aware
reports.

## Collaboration

- Window A planned the public interfaces and Task 30 checked-result helper.
- Window B added Task 31 tests and deterministic fixtures.
- Window C implemented the evaluation modules and Task 30 helper extraction.
- Window D synchronized the evaluation documentation.
- Window E performed a read-only final review.
- The controller rejected an early partial-report interpretation and enforced
  all-or-nothing lifecycle-corruption rejection.

## Accepted Design

- `validate_results_before_aggregation()` reuses
  `contracts.lifecycle.validate_generation_result()`.
- Any corrupt row fails the whole report before aggregation. No survivor
  aggregation and no partial artifact are allowed.
- `load_validated_results()` preserves Task 30 manifest, artifact, checksum,
  JSONL, sampling-failure-row, count, decode, and lifecycle validation.
- Failure modes group by canonical `residue_reaction_family`.
- Primary and secondary failure reasons are reported separately.
- Lifecycle stages are preserved globally, by family, and in evidence:
  `generation`, `generation_gate`, `export`, `docking_eligibility`,
  `docking_run`.
- Failure-mode JSON output is deterministic and written atomically.
- Task 30 denominator equations remain owned by Task 30.

## Verification

Passed:

```powershell
$env:PYTHONPATH='src'
python -m unittest tests.evaluation.test_lifecycle_reports -v
python -m unittest tests.evaluation.test_denominator_accounting -v
python -m unittest tests.contracts.test_lifecycle -v
python -m unittest tests.contracts.test_denominators -v
python -m unittest discover -s tests -t . -q
python -m compileall -q scripts src
```

Results:

- Task 31 lifecycle reports: 78 tests passed.
- Task 30 denominator accounting: 97 tests passed.
- Lifecycle and denominator contracts: 15 tests passed.
- Full suite: 1503 tests passed.
- Temporary copied fixture: repeated atomic writes were byte-identical.
- Corrupt manifest fixture: rejected with no partial report artifact.

## Final Review

Window E found no blocking issues. Two low-risk gaps remain:

- The defensive `_reason_stage()` unmapped-reason branch is not directly
  triggered because the authoritative lifecycle validator rejects unknown
  reasons first and mapping completeness tests prove exact coverage.
- Temp-file cleanup on an injected `os.fsync()` or `os.replace()` failure is
  implemented but not fault-injection tested.

## Decision

Task 31 is accepted. Task 32 may start after controller confirmation.
