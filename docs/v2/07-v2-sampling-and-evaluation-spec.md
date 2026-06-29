# V2 Sampling And Evaluation Spec

Date: 2026-06-16
Status: Task 53 contract implemented; Task 54 deterministic fixture smoke implemented; Task 55 evaluation metrics implemented; Task 56 docking feasibility implemented

## Task 53 Sampling Contract Scope

Task 53 implements only the package-interface contract in `src/covalent_design/inference/v2_sampling.py` and tests in `tests/inference/test_v2_sampling.py`.

Task 53 does not execute sampling, run model forward passes, write generated complexes, export mmCIF, perform docking, perform evaluation, or access real data roots. Task 54 adds deterministic fixture-mode sampling smoke only. Evaluation metrics and docking feasibility remain Tasks 55 and 56.

## Task 54 Deterministic Fixture Smoke Scope

Task 54 implements a lightweight in-memory smoke runner, `run_deterministic_fixture_sampling(request, fixture_records, fixture_split_index=None)`, plus fixture records, split index, and `configs/v2_sampling_smoke.yml`. The runner consumes `V2SamplingRequest` and returns `V2SamplingResult`; it does not read fixture paths itself, does not write `output_root`, and does not create generated molecule, complex, mmCIF, docking, or evaluation artifacts.

Task 54 proves:

- same seed produces identical serialized results and hashes,
- different seed changes deterministic fixture output,
- held-out split selectors work for `train`, `val`, and `test` fixture records,
- per-family filtering works on fixture record metadata,
- explicit `record_ids` bypass split selection,
- invalid decode diagnostics and sampling system failures remain separate,
- count conservation still holds,
- no hard import of RDKit, PyTorch, CUDA, PMDM, PocketFlow, or docking tools is introduced.

Task 54 is not real stochastic model sampling and is not a scientific quality claim. It does not implement Task 55 metrics, Task 56 docking feasibility, result export, or real-data-root access.

## Sampling Request Schema

`V2SamplingRequest` extends existing reactive-site request semantics with:

- `request_id`,
- `checkpoint_ref`,
- `checkpoint_manifest_ref`,
- `environment_manifest_ref`,
- exactly one selector: `split_name` (`train`, `val`, `test`) or explicit `record_ids`,
- optional residue-reaction `family_filter`,
- `random_seed`,
- `sample_count`,
- `output_root`,
- `max_retries`,
- `retry_on_categories`,
- `baseline_mode` (`pmdm` or `non_pmdm_baseline`),
- `generation_mode = "reactive_site"`.

The request must remain explicit reactive-site generation. `reference_ligand` generation is rejected by the contract.

Task 53 validates the request and returns `ContractEnvelope[Optional[V2SamplingRequest]]` from `build_v2_sampling_request()`. It records structured `V2_SAMPLING_*` errors for missing checkpoint references, selector absence/conflict, unsupported split, invalid family/record selectors, invalid seed/sample count/output root/retry policy, unsupported baseline mode, and unsupported generation mode.

The `output_root` field is a requested destination for later tasks. Task 53 validation does not create directories or write outputs.

## Sampling Result Schema

`V2SamplingResult` is a deterministic result-summary contract. It links:

- `checkpoint_ref`,
- `checkpoint_manifest_ref`,
- `environment_manifest_ref`,
- `baseline_mode`,
- selector metadata,
- seed and count fields,
- invalid decode diagnostics,
- sampling system failures,
- export, docking, and evaluation statuses.

Task 53 enforces count conservation:

```text
valid_sample_count + invalid_sample_count == attempted_sample_count
attempted_sample_count + sampling_system_failure_count == requested_sample_count
```

`serialize_v2_sampling_request()`, `serialize_v2_sampling_result()`, `hash_v2_sampling_request()`, and `hash_v2_sampling_result()` provide deterministic JSON and SHA-256 identity for request/result contracts.

## Failure Accounting

Failures must remain separated:

- `request_validation_failure`,
- `sampling_system_failure`,
- `invalid_generated_sample`,
- `export_failure`,
- `docking_not_run`,
- `evaluation_artifact_corruption`.

Task 53 implements this distinction through:

- request validation envelopes,
- `V2SamplingSystemFailure`,
- `V2InvalidDecodeDiagnostic`,
- `V2SamplingResult` export/docking/evaluation status fields.

Invalid decode diagnostics are generated-sample diagnostics. Sampling system failures are runtime/system events and are not counted as generated samples. Export, docking, and evaluation statuses are placeholders for later tasks and must not imply that Task 53 ran those steps.

## Sampling Outputs

Task 53 does not emit filesystem artifacts. Later sampling tasks may emit:

- generation run manifest,
- result rows,
- sampling system failures,
- invalid decode diagnostics,
- optional generated complex artifacts,
- sampling summary.

Those outputs belong to Task 55+ or later production sampling/export tasks and must preserve the Task 53/54 request/result failure taxonomy.

## Validity Metrics

Evaluation must report, in Task 55 or later:

- requested/attempted/valid/invalid/exported counts,
- validity gate pass/fail reasons,
- covalent edge prediction diagnostics,
- bond-type diagnostics,
- family diagnostics,
- lifecycle conservation equations.

Task 53 only defines contract fields needed to carry those counts and diagnostics later.

## Uniqueness And Novelty

V2-beta should report uniqueness/novelty only when the required scaffold and molecule identity tools are source-verified. If unavailable, the report must say `not_evaluable`, not invent values.

## Covalent Geometry Checks

Report distance and local geometry diagnostics using existing v1 geometry contracts and RDKit-heavy checks only when available.

## Drug-Likeness Checks

RDKit descriptors and simple drug-likeness reports are heavy-profile diagnostics. They are not hard beta gates unless a later accepted decision promotes them.

## Safety Filters

Safety filters are limited to basic chemistry validity and rule-table compatibility in v2-beta. ADMET-style downstream safety-property claims are out of scope.

## Optional Docking Policy

Docking remains feasibility-only:

- source-verify engine and license,
- prove fixture CLI/API execution,
- record runtime and output schema,
- do not block v2-beta if infeasible.

Task 53 records `docking_status = "not_run"` by default; it does not perform docking.

## Evaluation Report

Task 55 implements `build_v2_evaluation_report()` in `src/covalent_design/evaluation/v2_metrics.py` and the CLI `python -m covalent_design.evaluation.cli.v2_evaluate`. The report consumes a `V2SamplingResult` plus optional explicit fixture/evidence metadata; it does not read approved real-data roots or local V2 data artifacts, and does not write evaluation artifacts.

The report includes:

- validity metrics,
- fixture-backed family metrics when record metadata is provided,
- covalent geometry diagnostics when explicit geometry evidence is provided,
- uniqueness/novelty when explicit identity evidence is provided,
- RDKit validity summary when explicit RDKit evidence is provided,
- failure accounting,
- denominator conservation.

Unavailable optional evidence is reported as `status: "not_evaluable"` with a reason and must not be interpreted as negative model performance. Docking remains Task 56; Task 55 records `docking_evaluation_status = "not_evaluable"` and does not choose, import, or run a docking engine.

## Task 56 Docking Feasibility Gate

Task 56 implements `build_v2_docking_feasibility_report()` in `src/covalent_design/evaluation/v2_docking_feasibility.py`. The report is evidence-driven: callers provide explicit engine evidence, and the module validates and serializes it deterministically. The module does not invoke a docking engine, does not create docking artifacts, does not install or download tools, and does not read real-data roots.

The report records engine candidate/status, license status, install path or missing-install reason, CLI/API probe status, input/output format support, probe duration when evidence exists, and non-blocking beta-release semantics. Missing engines, unknown license status, unsupported formats, and failed probes are represented as `not_evaluable`, `license_unknown`, or `failed_probe`; none are negative model-performance results.

Task 56 remains feasibility-only. A later accepted decision is required before docking can become a required beta gate or before actual docking execution is added.
## Verification Commands

Task 53 contract verification:

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/inference/test_v2_sampling.py -q
```

Planned later commands, not implemented by Task 53:

```powershell
python -m pytest tests/inference/test_v2_sampling_smoke.py -q
python -m pytest tests/evaluation/test_v2_metrics.py -q
```
