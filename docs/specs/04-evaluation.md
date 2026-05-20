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
python -m covalent_design.evaluation.summarize_results --results outputs/generation/results.jsonl --out outputs/eval/summary.yml
python -m covalent_design.evaluation.check_denominators --summary outputs/eval/summary.yml
python -m covalent_design.evaluation.run_covalent_docking --manifest configs/docking_protocol.yml --results outputs/generation/results.jsonl
python -m covalent_design.evaluation.report --summary outputs/eval/summary.yml --split scaffold --out outputs/eval/report.md
python -m compileall -q scripts src
```

## Project Structure

```text
src/covalent_design/evaluation/
  result_schema.py
  denominator_accounting.py
  validity_metrics.py
  failure_modes.py
  split_metrics.py
  docking_protocol.py
  reports.py

configs/
  docking_protocol.yml
```

## Code Style

Metric functions must receive explicit denominators and lifecycle fields. They must not infer missing samples from files present on disk.

```python
def covalent_docking_scores(results: Iterable[CovalentGenerationResult]) -> list[float]:
    return [
        result.covalent_docking_score
        for result in results
        if result.generation_validity_status == "valid"
        and result.complex_export_status == "exported"
        and result.docking_eligibility_status == "eligible"
        and result.docking_run_status == "succeeded"
        and protocol_manifest_is_complete(result.docking_protocol_manifest_uri)
    ]
```

Rules:

- Request validation errors do not create sample results and do not enter generation denominators.
- Sampling system failures are run-level artifacts and enter `sampling_system_failure_count`; they do not create `CovalentGenerationResult` rows.
- Attempted invalid samples remain result records.
- Export, docking eligibility, docking run, and generation validity are separate lifecycle fields.
- Lifecycle constraints and docking protocol manifest completeness are validated before metric aggregation.
- Every reported rate names its denominator.

## Testing Strategy

Golden fixtures must cover:

- Request validation errors excluded from generation denominators.
- Invalid generated samples retained with failure reasons.
- Valid internal result with mmCIF export failure.
- Valid exported result that is not docking-evaluable.
- Docking-eligible sample with `not_run`, `failed`, and `succeeded` run statuses.
- Corrupt sample with `docking_run_status = succeeded` but invalid lifecycle or incomplete protocol manifest rejected before aggregation.
- Sampling system failure artifact counted outside attempted sample records.
- QuickVina2-only score rejected as `covalent_docking_score`.
- Scaffold split primary overlap check.

Conservation equations from the IO contract must be tested exactly.

## Boundaries

Always:

- Report invalid rates separately from docking scores.
- Aggregate `covalent_docking_score` only when `docking_run_status = succeeded`.
- Report by `residue_reaction_family` and primary split where possible.

Ask first:

- Changing docking protocol manifest fields.
- Defining any docking behavior for invalid samples.
- Adding new top-level validity or lifecycle status values.

Never:

- Collapse generation validity, export status, docking eligibility, and docking run into a single flag.
- Assign artificial docking scores to invalid samples.
- Drop invalid samples from uniqueness, validity, or failure-mode denominators where applicable.
- Report random split as the only primary generalization result.

## Success Criteria

- All denominator conservation equations pass for generated summaries.
- Reports include requested, accepted, attempted, sampling-system-failed, valid, invalid, exported, docking-evaluable, docked, failed, and not-run counts.
- Failure modes are grouped by primary and secondary failure reasons.
- Primary evaluation reports protein-cluster and de-warheaded scaffold split results.
- Covalent docking protocol manifests include engine, version, full config, receptor preparation, ligand preparation, covalent constraint, search region, pose selection, checksums, and failure logs.

## Open Questions

- Which covalent docking engine and representation are authoritative for v1?
- Is docking required for all valid samples or a reviewed subset?
- What score unit and pose ranking convention should be standardized?
- How should multi-label failure reasons be summarized without hiding the primary lifecycle failure?
- Is manual structural review part of the release gate or a separate analysis artifact?
