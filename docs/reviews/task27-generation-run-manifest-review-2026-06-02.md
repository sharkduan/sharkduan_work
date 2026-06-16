# Task 27 Generation Run Manifest Review

Date: 2026-06-02

## Scope

Task 27 implements generation-run orchestration and sampling-system-failure
accounting only. It does not implement the Task 28 result lifecycle writer,
Task 29 complex export, or evaluation.

## Collaboration

Five Claude Code subwindows were launched in Plan/Read or Review mode before
write execution:

- Window A: interface design.
- Window B: tests and fixtures. The main controller took over after the write
  window exceeded the time limit.
- Window C: production implementation and a narrow boundary-fix pass.
- Window D: documentation synchronization.
- Window E: adversarial read-only review. Final result: no blocking findings.

## Implemented Contract

- `generate()` accepts only `ValidatedRequest` and returns
  `ContractEnvelope[GenerationRunManifest]`.
- `SamplingPolicy` requires explicit `max_retries` and
  `retry_on_categories`; no production retry defaults were invented.
- `SamplingSystemFailure` retains the frozen 9-field schema and validates
  category, non-negative sample/retry indices, ISO 8601 timestamps, and
  lowercase SHA-256 traceback hashes.
- The six failure categories are `crash`, `oom`, `timeout`,
  `retry_exhausted`, `checkpoint_load_failed`, and
  `sampler_invariant_violation`.
- Generation writes `request.normalized.yml` before checkpoint loading, then
  writes `results.jsonl`, `sampling_system_failures.jsonl`, and
  `run_manifest.yml`, with a sibling `logs/` directory.
- Manifest artifact references are relative and include exact-byte SHA-256,
  byte count, format, schema version, and role.
- Accounting is at `sample_id` granularity:

```text
accepted_request_sample_count =
    attempted_sample_count + sampling_system_failure_count
```

- Retry attempts do not increase denominators. Intermediate failure rows are
  retained. Fully exhausted samples add a terminal `retry_exhausted` row while
  counting once as a final sampling-system failure.
- Checkpoint-load failures are emitted once per accepted sample id without
  loading real Torch weights.

## Additional Hardening

- `request.normalized.yml` and `run_manifest.yml` writers use explicit LF
  newlines for cross-platform deterministic bytes.
- Three committed `run_manifest.yml` fixtures are real golden files and are
  compared byte-for-byte in tests.
- The timestamp validator rejects non-`T` separators and trailing text.
- Retry state-machine coverage includes multiple retry categories, zero
  retries, retry success, retry exhaustion, and signal-field propagation.

## Verification

Passed:

```text
python -m unittest tests.inference.test_sampling_failures -v
  35 tests
python -m unittest tests.inference.test_request_validation -v
  72 tests
python -m unittest discover -s tests -t . -q
  1213 tests
python -m compileall -q scripts src
```

Optional `pytest` checks were not run because the environment reports:

```text
No module named pytest
```

A temporary mixed run was inspected manually. It contained:

```text
request.normalized.yml
run_manifest.yml
results.jsonl
sampling_system_failures.jsonl
logs/
```

The inspected count equation was `3 = 2 + 1`; all manifest ArtifactRefs
validated against the temporary generation root.

## Review Result

Task 27 is accepted. Window E reported no blocking findings. No Task 28 code,
Torch, RDKit, PMDM, PocketFlow, output-directory scanning, staging, or commit
was introduced.

## Non-Blocking Notes

- `resource_snapshot` is a JSON-facing mapping boundary. Samplers should pass
  JSON-serializable values; Task 27 intentionally does not coerce arbitrary
  runtime objects to strings.
- Fixture `.log` files are optional diagnostic examples and remain subject to
  the repository's existing log ignore policy.
