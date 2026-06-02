# Spec: Evaluation

## Objective

Evaluate generated covalent inhibitors with denominator conservation, explicit lifecycle states, split-aware reporting, rule/gate failure modes, mmCIF export status, docking eligibility, and covalent docking scores only where the covalent docking protocol succeeds.

Evaluation must make invalid generated samples visible instead of deleting them or assigning artificial docking scores.

## Tech Stack

- Python 3.9-compatible project-owned evaluation code.
- JSONL/YAML result and summary artifacts.
- Optional docking tools only behind explicit protocol manifests.
- QuickVina2 may be reported only as a noncovalent baseline or compatibility metric unless wrapped in a reviewed covalent protocol.

## Commands

```bash
python -m covalent_design.evaluation.summarize_results --manifest <run_manifest.yml>
python -m covalent_design.evaluation.check_denominators --manifest <run_manifest.yml>
python -m compileall -q scripts src
```

## Project Structure

```text
src/covalent_design/evaluation/
  __init__.py
  result_schema.py
  summarize_results.py          # CLI entry point
  check_denominators.py         # CLI entry point
  denominator_accounting.py     # core API functions
```

## Python API

```python
def load_generation_run(manifest: Path) -> ContractEnvelope[GenerationRunManifest]: ...
    """Parse and validate a generation-run manifest YAML.

    Returns a ContractEnvelope with the GenerationRunManifest payload and
    checksum-validated artifact references for request, results, and
    sampling_system_failures.
    """

def summarize_results(manifest: Path) -> EvaluationSummary: ...
    """Load a generation run and compute its EvaluationSummary.

    This API has no write side effect.  Use write_evaluation_summary to
    persist the result.  The CLI composes the two operations.
    """

def check_denominators(summary: EvaluationSummary) -> ValidationReceipt: ...
    """Validate the six EvaluationSummary conservation equations."""

def evaluation_summary_to_dict(summary: EvaluationSummary) -> dict[str, object]: ...
    """Serialize an EvaluationSummary to a deterministic JSON-compatible dict."""

def write_evaluation_summary(summary: EvaluationSummary, path: Path) -> ArtifactRef: ...
    """Write an EvaluationSummary to *path* atomically.

    Uses a same-directory temp file that is renamed into place.
    Returns an ArtifactRef for the written file.
    """
```

## CLI

```bash
# Compute and write evaluation_summary.json beside the manifest; print summary to stdout
python -m covalent_design.evaluation.summarize_results --manifest <run_manifest.yml>

# Validate conservation equations, print receipt to stdout (no file write)
python -m covalent_design.evaluation.check_denominators --manifest <run_manifest.yml>
```

`summarize_results` writes `evaluation_summary.json` to the manifest parent directory.
`check_denominators` recomputes the summary from the manifest and prints the validation receipt without writing files.

## Counting Rules

Manifest-first: every count comes from the manifest and the checksum-validated result/failure artifacts it references. Counts must not be inferred from files present on disk.

### Manifest Fields Used

| Manifest field | Role |
| --- | --- |
| `accepted_request_sample_count` | Becomes `requested_sample_count` and `accepted_request_sample_count` in the summary |
| `attempted_sample_count` | Number of attempted samples (one per sample_id) |
| `sampling_system_failure_count` | Authoritative count of fully-failed samples |
| `result_count` | Must equal the number of rows in `results.jsonl` |

### Result Row Processing

Every row in `results.jsonl` is decoded through `decode_result_row()` and validated
through `validate_generation_result()`.  Invalid rows (decode or lifecycle failures)
produce structured `ContractError`, not silent skips.

### Sampling System Failures

`sampling_system_failures.jsonl` rows are schema-validated as `SamplingSystemFailure`
audit evidence.  The row count in the file is not used as a denominator; the
manifest's `sampling_system_failure_count` is authoritative.

### Lifecycle Counting

Results are counted by lifecycle status:

```
attempted = valid_generated_internal + invalid_generated
valid_generated_internal = exported_valid_complex + valid_export_failure
exported_valid_complex = docking_evaluable_valid + valid_but_not_docking_evaluable
docking_evaluable_valid = successfully_docked + docking_failed + docking_not_run
```

Valid samples proceed through the lifecycle: generation validity -> export status ->
docking eligibility -> docking run status.  Invalid samples do not advance past
the validity check.

## Testing Strategy

Golden fixtures must cover:

- Request validation errors excluded from generation denominators.
- Invalid generated samples retained with failure reasons.
- Valid internal result with mmCIF export failure.
- Valid exported result that is not docking-evaluable.
- Docking-eligible sample with `not_run`, `failed`, and `succeeded` run statuses.
- Corrupt lifecycle rows rejected before aggregation.
- Sampling system failure artifact rows validated as audit evidence, with row count not used as a denominator.
- Manifest `sampling_system_failure_count` used as the authoritative count.

Conservation equations from the IO contract must be tested exactly (see `validate_evaluation_summary`).

## Boundaries

Always:

- Read counts from the manifest, not from files on disk.
- Mandatory checksum-validated artifact refs are `request`, `results`, and `sampling_system_failures`.
- Use relative artifact URIs only; no absolute paths or traversal outside the manifest parent.
- Treat `sampling_system_failure_count` in the manifest as authoritative.
- Schema-validate every `sampling_system_failures.jsonl` row as audit evidence.
- Decode and validate every result row through `validate_generation_result()`.
- Separate generation validity, export status, docking eligibility, and docking run status as lifecycle fields.
- Task 30 is global unstratified summary only.

Ask first:

- Changing the six conservation equations.
- Documenting Task 31 failure-mode reports, Task 32 docking protocol, or Task 33 stratification.

Never:

- Collapse generation validity, export status, docking eligibility, and docking run into a single flag.
- Infer counts from directory scanning, sibling artifact presence, or `--results`/`--summary` file paths.
- Use the row count of `sampling_system_failures.jsonl` as a denominator.

## Success Criteria

- All six conservation equations pass for generated summaries.
- Manifest-first: `summarize_results(manifest)` loads artifacts by checksum-validated paths with no disk scanning.
- Python `summarize_results()` has no write side effect; `write_evaluation_summary()` and the CLI handle persistence.
- `evaluation_summary.json` written atomically beside the manifest by the CLI.
- For one manifest, `request_validation_error_sample_count = 0` and `requested_sample_count = accepted_request_sample_count`.
- `sampling_system_failure_count` comes from the manifest, not from row counts in `sampling_system_failures.jsonl`.
- Every result row decoded and validated; corrupt rows produce structured errors, not silent skips.

## Open Questions

Resolved (2026-06-02 Task 30 freeze):

- **Evaluation CLI:** manifest-first (`--manifest <run_manifest.yml>`). Counts from manifest, not from disk. See `interface-design.md`.
- **Python API:** Five public functions: `load_generation_run`, `summarize_results`, `check_denominators`, `evaluation_summary_to_dict`, `write_evaluation_summary`. Summarize has no write side effect.
- **Task 30 vs Task 33 scope:** Task 30 = global unstratified summary only. Task 33 = per-split, per-family stratified reports. See `implementation-plan.md`.
- **Failure reason priority:** Gate execution order determines primary failure. `REQUIRED_GATE_STATE_UNAVAILABLE` outranks all. See `interface-design.md` Failure Reason Priority.
- **Retry counting:** sample_id granularity; retries internal; denominator not affected. See ADR 0035.
- **Sampling system failures:** `sampling_system_failures.jsonl` rows are schema-validated audit evidence. Row count is not a denominator; `sampling_system_failure_count` in the manifest is authoritative.

Still open for v1:

- Which covalent docking engine and representation are authoritative for v1?
- Is docking required for all valid samples or a reviewed subset?
- What score unit and pose ranking convention should be standardized?
- How should multi-label failure reasons be summarized without hiding the primary lifecycle failure?
- Is manual structural review part of the release gate or a separate analysis artifact?
