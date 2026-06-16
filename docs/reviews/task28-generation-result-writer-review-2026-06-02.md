# Task 28 Generation Result Writer Review

Date: 2026-06-02

## Scope

Task 28 implements deterministic, JSON-compatible serialization for
`CovalentGenerationResult` and integrates it with the Task 27 `result_sink`
boundary. Task 29 mmCIF export, docking execution, and Task 30 evaluation remain
out of scope.

## Collaboration

Five Claude Code subwindows were launched in read/review mode before any Task 28
write authorization:

- Window A: API and boundary design
- Window B: tests and committed fixtures
- Window C: production implementation
- Window D: documentation synchronization
- Window E: adversarial final review

The controller approved each write scope after reviewing the corresponding plan.
Window B introduced one fake-sampler fixture bug (`ValidatedRequest` request-id
access path); the controller repaired it with a one-line test-only change.

## Implemented Boundary

```python
from covalent_design.inference.result_writer import ResultWriter

writer = ResultWriter()
row = writer.write(result)
```

`ResultWriter.write()`:

- requires `CovalentGenerationResult`;
- calls `from covalent_design.contracts import validate_generation_result`;
- raises the first structured `ContractError` when validation fails;
- preserves internally consistent invalid sample diagnostics;
- returns deterministic JSON-compatible values;
- converts nested dataclasses to dictionaries and tuples to lists;
- sorts artifact mapping keys;
- does not mutate the input;
- excludes top-level `schema_version` and `contract_version`, which Task 27
  `write_jsonl()` injects into `results.jsonl`;
- does not directly write JSONL or expose a standalone CLI.

## Verification

Passed:

```text
python -m unittest tests.inference.test_result_writer -v
  67 tests
python -m unittest tests.inference.test_sampling_failures -v
  35 tests
python -m unittest tests.inference.test_request_validation -v
  72 tests
python -m unittest tests.contracts.test_lifecycle -v
  10 tests
python -m unittest discover -s tests -t . -q
  1280 tests
python -m compileall -q scripts src
git diff --check
```

The Window E review reported no blockers and approved progression to Task 29.

## Residual Non-Blocking Notes

- Additional lifecycle-validator corrupt-state fixtures could cover less common
  error branches before Task 29 expands the export path.
- The current Task 28 suite already covers the two critical writer boundaries:
  non-contract values are rejected and corrupt sampler results propagate as
  fatal `ContractError` values instead of becoming sampling-system failures.

## Decision

Task 28 is accepted. Task 29 may start only after explicit controller approval.
