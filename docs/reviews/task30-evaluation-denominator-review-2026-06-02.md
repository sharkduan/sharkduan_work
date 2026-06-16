# Task 30 Evaluation Denominator Review - 2026-06-02

## Scope

Task 30 implements manifest-first global evaluation summary accounting only.
It does not implement Task 31 failure-mode reports, Task 32 docking protocol,
or Task 33 split-aware metrics.

## Collaboration Record

- Window A: read-only interface plan.
- Window B: plan-first tests and deterministic fixtures.
- Window C: plan-first implementation. The write session exceeded the timeout;
  the controller inspected the output and took over with minimal fixes.
- Window D: plan-first documentation synchronization.
- Window E: read-only adversarial review. No blocking findings.

## Implemented Boundary

Public Python API:

```python
load_generation_run(manifest: Path) -> ContractEnvelope[GenerationRunManifest]
summarize_results(manifest: Path) -> EvaluationSummary
check_denominators(summary: EvaluationSummary) -> ValidationReceipt
evaluation_summary_to_dict(summary: EvaluationSummary) -> dict[str, object]
write_evaluation_summary(summary: EvaluationSummary, path: Path) -> ArtifactRef
```

CLI:

```powershell
python -m covalent_design.evaluation.summarize_results --manifest <run_manifest.yml>
python -m covalent_design.evaluation.check_denominators --manifest <run_manifest.yml>
```

The manifest parent is the artifact root. Mandatory `request`, `results`, and
`sampling_system_failures` refs are validated for relative URI, role, format,
schema version, byte count, and SHA-256 before aggregation. Every result row is
decoded and passed through `validate_generation_result()`. Every failure row is
decoded as `SamplingSystemFailure` audit evidence. Failure JSONL row count is
not a denominator; the manifest count is authoritative.

All six conservation equations remain centralized in
`validate_evaluation_summary()`. The evaluation layer reuses that validator.
The writer also rejects a non-conserving summary before performing an atomic
same-directory temp-file replacement.

## Controller Fixes

- Restored the frozen `check_denominators(summary)` Python API.
- Removed write side effects from `summarize_results()`.
- Added standard CLI `--help` handling.
- Replaced Windows-incompatible overwrite rename with `os.replace()`.
- Tightened nested result decoding and structured failure-row validation.
- Corrected the retry fixture so accepted, attempted, and system-failure
  counts conserve.
- Replaced order-sensitive Task 28/29 `sys.modules` source guards with direct
  production-source boundary checks.
- Removed non-ASCII punctuation from new Task 30 code and tests.

## Verification

Passed:

```powershell
python -m unittest tests.evaluation.test_denominator_accounting -v
python -m unittest tests.contracts.test_denominators -v
python -m unittest tests.contracts.test_lifecycle -v
python -m unittest tests.inference.test_complex_export -v
python -m unittest tests.inference.test_result_writer -v
python -m unittest tests.inference.test_sampling_failures -v
python -m unittest tests.inference.test_request_validation -v
python -m unittest discover -s tests -t . -q
python -m compileall -q scripts src
python -m covalent_design.evaluation.summarize_results --help
python -m covalent_design.evaluation.check_denominators --help
```

Final full-suite result: `1422` tests passed.

A temporary copied `valid_mixed` fixture was also exercised through both CLIs.
The summary CLI wrote `evaluation_summary.json`; the denominator CLI emitted a
passing receipt. No fixture output was left in the repository.

`pytest` is not installed in the current environment, so the equivalent
`unittest` commands were used.

## Review Result

Task 30: accepted.

Task 31 readiness: yes, but do not begin Task 31 without a separate task
authorization.

## Non-Blocking Notes

- For one manifest, request-validation errors are fixed at zero and requested
  samples equal accepted samples. A later cross-run request-rejection report
  must extend this model explicitly.
- `checkpoint_ref` request/manifest cross-validation remains outside Task 30.
