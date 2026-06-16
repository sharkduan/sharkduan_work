# Task 17+ 项目文档健康审查

Review date: 2026-05-26

Scope: Task 17+ Project Documentation Review. This review covers model, training, inference, evaluation, checkpoint, governance, and fixture documentation readiness before starting Task 17.

Review mode: read-only audit. This document records findings only. It does not implement Task 17 or later tasks, does not generate tests, and does not modify source/spec/ADR files.

Primary sources reviewed:

- `CONTEXT.md`
- `README.md`
- `docs/specs/README.md`
- `docs/specs/implementation-plan.md`
- `docs/specs/interface-design.md`
- `docs/specs/verification-matrix.md`
- `docs/specs/02-model.md`
- `docs/specs/03-training.md`
- `docs/specs/04-evaluation.md`
- `docs/specs/05-inference.md`
- `docs/specs/key-design-decisions.md`
- `docs/covalent_model_design.md`
- `docs/covalent_generation_io_contract.md`
- `docs/covalent_etl_plan.md`
- `docs/adr/`
- `docs/reviews/`
- `src/covalent_design/`
- `tests/`
- `.github/workflows/ci.yml`

Skills applied conceptually:

- `zoom-out`
- `source-driven-development`
- `grill-with-docs`
- `doubt-driven-development`
- `documentation-and-adrs`
- `api-and-interface-design`
- `code-review-and-quality`
- `academic-researcher`

## Executive Summary

Verdict: **Do not start Task 17 implementation yet.**

The project is ready for a **Task 17 contract-freeze and fixture-design pass**, but not for direct model code implementation.

The Task 17+ documentation has a coherent high-level direction:

- ETL-first implementation order is preserved.
- PMDM remains the generation backbone.
- New covalent logic belongs under project-owned `src/covalent_design/`.
- Stepwise covalent edge candidates are rebuilt from current noisy/generated ligand coordinates.
- Forced positives are counted separately.
- Message weights must be detached predicted probabilities, not labels.
- Final decode may reject every candidate and emit an invalid sample.
- Inference uses request validation before sampling.
- Every attempted sample writes one result row.
- Sampling system failures are run-level artifacts, not invalid generated samples.
- mmCIF is authoritative; PDB is optional compatibility output.
- Evaluation uses lifecycle-aware denominator conservation.
- QuickVina2-only output is not a covalent docking score.

The blocker is at the Task 17 boundary: `ModelBatch` is not yet precise enough to be implemented safely.

Current implementation state observed during review:

- No `src/covalent_design/model/` package exists yet.
- No `src/covalent_design/training/` package exists yet.
- No `src/covalent_design/inference/` package exists yet.
- No `src/covalent_design/evaluation/` package exists yet.
- `src/covalent_design/contracts/types.py` already contains some downstream-facing shared types and constants:
  - `REQUEST_VALIDATION_ERROR_CODES`
  - `FAILURE_REASON_CODES`
  - `CovalentGenerationResult`
  - `EdgeDenominators`
  - `EvaluationSummary`
- `ModelBatch`, `ModelForwardOutput`, `ReactiveSiteGenerationRequest`, `TrainingRunManifest`, `GenerationRunManifest`, `SamplingSystemFailure`, and `DockingProtocolManifest` are documented but not implemented.

Current worktree state observed during review:

- Modified files exist in `docs/specs/`, `src/covalent_design/data/`, and `tests/`.
- Untracked directories/files include `docs/reviews/`, `prompts/`, Task 14/15/16 related modules and fixtures.
- This audit did not revert or modify any pre-existing worktree changes.

## Task 17+ Architecture Map

Expected Task 1-16 to Task 17+ flow:

```text
raw/source manifests
-> source ingest
-> normalized records
-> canonical identity / conflicts / quality
-> CovalentComplexRecord JSONL
-> rule validation and calibration sheet
-> radius-bounded static edge candidates
-> finalized record manifests
-> leakage-aware splits
-> visual checks
-> ETL quality report / Data Release Gate
-> ModelBatch
-> stepwise candidate builder
-> PMDM adapter
-> covalent heads
-> final decode / validity gate
-> training dataset
-> loss masks and denominator reports
-> training run manifest and checkpoint metadata
-> request validation
-> generation run manifest
-> generation result rows
-> mmCIF export
-> evaluation denominator checks
-> lifecycle, docking, and split-aware reports
```

Documented package responsibilities:

| Package | Intended responsibility | Current state |
| --- | --- | --- |
| `contracts` | Public semantic layer: artifact refs, errors, receipts, lifecycle, denominators, result/evaluation shared types. | Partially implemented. Contains some future-facing inference/evaluation contracts. |
| `io` | JSONL and artifact IO helpers. | Implemented for current data path. |
| `data` | Ingest, normalize, identity, records, manifests, splits, quality report. | Task 1-16 related work present, including dirty/untracked changes. |
| `rules` | Rule schema, validation, calibration. | Implemented for current data path. |
| `candidates` | Static radius-bounded edge candidate artifacts. | Implemented for Task 12 style artifacts. |
| `viz` | Visual inspection artifacts. | Present as untracked Task 15 style work. |
| `model` | Batch, PMDM adapter, stepwise candidates, heads, final decode. | Not present. Planned. |
| `training` | Dataset, batch loader, masks, losses, run/checkpoint manifests. | Not present. Planned. |
| `inference` | Request validation, sampling, result writing, export. | Not present. Planned. |
| `evaluation` | Denominator checks, lifecycle reports, docking protocol, split metrics. | Not present. Planned. |

Dependency direction is conceptually sound:

```text
contracts
<- io
<- data/rules/candidates/viz
<- model
<- training
<- inference/evaluation
```

However, Task 17 needs a stronger boundary between:

- Data Release Gate artifacts.
- Accepted-core record bundle.
- Static Task 12 edge candidates.
- Dynamic Task 18 stepwise candidates.
- Training-only labels.
- Inference-time generated candidates.

## Task 17-25 Model/Training Documentation Review

### Task 17: Implement Model Batch Contracts

Status: **P0 blocker before implementation.**

Documented goal:

- Convert accepted record bundles into typed model batches.
- Carry record ids, family keys, target atom identities, ligand heavy-atom count, edge candidates, and expected denominators.
- Fail before tensor construction on missing artifact refs.
- Provide `inspect_batch` CLI.

Problem:

The current `ModelBatch` sketch is too thin for implementation. It does not yet specify enough fields to construct the PMDM-compatible covalent model input without implementer guesswork.

Missing from the Task 17 contract:

- Tensor shape conventions.
- Tensor dtype conventions.
- Coordinate frame conventions.
- Protein atom table reference.
- Ligand atom table reference.
- Ligand bond table reference.
- Coordinates artifact reference.
- Static edge candidate artifact reference.
- Split assignment reference.
- Quality flag and Q2 handling.
- Visual check gate status.
- Data Release Gate status.
- Protein chemical state fields.
- Rule table version/hash.
- Positive edge label identity.
- Bond type vocabulary.
- Warhead metadata source.
- Local geometry metrics source.
- Exact `BatchSpec`.
- Exact `BatchInspectionReport`.
- Exact CLI JSON output.
- Error codes for fail-before-tensor behavior.

Why this matters:

Task 17 is the first model boundary. If it is ambiguous, Tasks 18-25 will bake in accidental assumptions about data release, quality gates, static candidates, dynamic candidates, labels, and chemical state.

Required before implementation:

- Freeze `ModelBatch`.
- Freeze `BatchSpec`.
- Freeze `BatchInspectionReport`.
- Freeze Task 17 input bundle.
- Freeze fail-before-tensor error codes.
- Freeze `inspect_batch` CLI behavior.

### Task 18: Implement Stepwise Candidate Builder For Model State

Status: **P1, mostly clear but boundary incomplete.**

Strong points:

- Documentation correctly says candidates are rebuilt from fixed target atom coordinates and current noisy/generated ligand coordinates.
- Forced positives are counted separately.
- Forced positives are excluded from v1 soft edge message passing and geometry regression.

Missing:

- Exact `StepwiseCandidateSet` schema.
- Whether Task 18 consumes Task 12 static candidates directly, only their labels, or only their artifact metadata.
- Denominator schema for each timestep.
- Whether candidate IDs are stable across timesteps.
- How forced positives are represented in tensors.
- Whether forced positives can contribute to edge existence loss when outside radius.
- How zero-natural-candidate windows are reported.

Risk:

Static edge candidates from Task 12 may be confused with dynamic candidates generated during denoising. These are not equivalent and must not share one unqualified artifact/type name.

### Task 19: Implement PMDM Adapter Skeleton

Status: **P1, direction clear but contract incomplete.**

Strong points:

- Documentation states PMDM should not be modified by default.
- Tests may use a lightweight fake backbone if PMDM dependencies are unavailable.
- Adapter accepts `ModelBatch` and returns `ModelForwardOutput`.
- Config/checkpoint metadata should include contract version and rule table hash.

Missing:

- Exact PMDM input mapping.
- Exact PMDM output key names in `ModelForwardOutput.pmdm_outputs`.
- Fake backbone minimum interface.
- Adapter config schema.
- Checkpoint metadata schema.
- What happens when PMDM is unavailable outside tests.

Risk:

Without adapter IO shape definitions, Task 19 can pass fake tests while failing to constrain real PMDM integration.

### Task 20: Implement Covalent Heads And Message-Weight Interface

Status: **P1, leakage principle clear but API guard missing.**

Strong points:

- Edge logits, bond-type logits, optional family logits, and observed denominators are documented.
- Message weights must be detached predicted probabilities.
- Ground-truth labels must not be passed as message weights.

Missing:

- Type-level or runtime guard preventing label tensors from being used as message weights.
- Expected tensor shapes for candidate-level logits.
- Bond-type vocabulary source.
- Whether family auxiliary head is in v1 or diagnostics-only after first run.
- How denominator validation is attached to model output.

Risk:

Tests could verify that one happy-path output is detached while public APIs still allow label leakage in another call path.

### Task 21: Implement Final Decode And Validity Gate Interface

Status: **P1, concept clear but lifecycle metadata incomplete.**

Strong points:

- Final decode sorts candidates by score.
- Rule-first gate is applied.
- All-candidates-fail must return invalid metadata rather than forcing an edge.
- Gate records edge validity checks and failure reasons.

Missing:

- Exact `FinalDecodeResult` schema.
- Failure reason priority.
- Whether failed higher-ranked candidates are preserved when a lower-ranked candidate passes.
- Exact lifecycle status transition into `CovalentGenerationResult`.
- Whether invalid decode can still carry ligand files, edge scores, geometry metrics, and matched warhead diagnostics.

Risk:

Final decode could collapse a rich lifecycle into a boolean valid/invalid result, making Task 28/30 evaluation incomplete.

### Task 22: Implement Training Dataset And Batch Loader

Status: **P0 depends on Task 17.**

Strong points:

- `TrainingDataPolicy(first_core_only=True)` is documented as default.
- Rejected, conflict, and multi-linkage records should not enter training.
- Q2 keep-with-flag records are eligible only through accepted-core gates and must remain stratified.
- Dataset should consume verified split manifests.

Missing:

- Exact `TrainingDatasetIndex` schema.
- Whether Task 22 consumes quality report, split index, visual check index, or a combined Data Release Gate bundle.
- Whether visual-blocked records are hard excluded.
- Whether scaffold fallback pending records can enter training.
- Whether random split is allowed for smoke only.
- How split assignment is attached to batch/report.

Risk:

Training dataset can become a second independent quality gate that drifts from Task 16 Data Release Gate semantics.

### Task 23: Implement Loss Masks And Denominator Reports

Status: **P1, denominator vocabulary strong but audit schema missing.**

Strong points:

- `EdgeDenominators` exists in code.
- Natural positives, forced positives, zero negatives, pending geometry, pending SMARTS, missing state, and Q2 cases are documented.
- Geometry denominator excludes forced positives by default.
- Bond-type denominator excludes no-edge negatives and forced positives by default.

Missing:

- Exact `MaskAudit` schema.
- Per-condition denominator equations.
- How denominator strata encode family and timestep bucket.
- How pending SMARTS and pending geometry interact when both are present.
- Whether Q2 stratification is in denominators or report metadata.

Risk:

Tests may check total counts while missing semantic mask correctness.

### Task 24: Implement Loss Report And Smoke Training Loop

Status: **P1, testable but fixture/config contract missing.**

Strong points:

- Required loss components are named.
- Fake/minimal backbone is allowed.
- Family auxiliary head remains optional.
- One smoke step on fixture data is the right scope.

Missing:

- Smoke config schema.
- Fixture dataset path.
- Expected `LossReport` serialized form.
- Required PMDM components under fake backbone.
- Exact assertion set for family consistency through masks/gates.

Risk:

Smoke training can become a compile-level test rather than a semantic denominator/mask test.

### Task 25: Implement Training Run Manifest And Checkpoint Metadata

Status: **P1, provenance direction clear but schema missing.**

Strong points:

- Run manifest should store config hash, record bundle hash, split hash, rule table hash, denominator report URI, and contract version.
- Checkpoint manifest should store model contract version, rule table version/hash, record bundle hash, and config hash.

Missing:

- Formal `TrainingRunManifest` schema.
- Formal checkpoint manifest schema.
- How config hash is computed.
- How record bundle hash is computed.
- How split hash is computed.
- Whether quality report and visual check hashes are included.
- Compatibility rules for loading checkpoints across contract versions.

Risk:

Reproducibility may be claimed without binding to the exact Data Release Gate inputs used for training.

## Task 26-30 Inference/Evaluation Documentation Review

### Task 26: Implement Request Schema And Validation

Status: **P1, good IO contract but schema drift exists.**

Strong points:

- `docs/covalent_generation_io_contract.md` gives a detailed request contract.
- Request validation errors are excluded from generation denominators.
- Ligand size controls are fixed/range/absent.
- Missing required chemical state maps to `REQUEST_REQUIRED_CHEMICAL_STATE_UNAVAILABLE`.

Missing:

- Canonical request file format: YAML, JSON, or both.
- Exact dataclass/schema fields across `interface-design.md` and `covalent_generation_io_contract.md`.
- Namespace handling for chain/asym identifiers.
- Alternate-location atom policy.
- Default pocket radius and sampling step policy.

Risk:

Different documents can lead to subtly different request schemas.

### Task 27: Implement Generation Run Manifest And Sampling Failure Accounting

Status: **P1, accounting concept clear but artifact schema missing.**

Strong points:

- `generate()` returns `GenerationRunManifest`, not a list of results.
- Request errors, attempted samples, and system failures are separate.
- Crash/OOM/timeout/retry-exhausted are run-level failures.
- Accepted request samples reconcile as attempted plus sampling-system-failed.

Missing:

- Formal `GenerationRunManifest`.
- Formal `SamplingSystemFailure`.
- Retry counting policy.
- Whether failure row includes traceback hash, log URI, resource info, retry count, and sample id.
- How partial result files are handled after crash.

Risk:

Sampling failures may be counted inconsistently across generation and evaluation.

### Task 28: Implement Generation Result Writer

Status: **P1, lifecycle direction strong but code/document type mismatch.**

Strong points:

- One attempted sample must produce one result row.
- Valid and invalid rows validate lifecycle constraints.
- Invalid rows preserve diagnostics.
- Request validation errors never create result rows.

Drift:

- The code-level `CovalentGenerationResult` currently has fewer fields than `docs/covalent_generation_io_contract.md` requires.

Missing in code-level type relative to docs:

- `generated_ligand_status`
- `molecular_quality_metrics`
- `covalent_edge_score`
- `geometry_metrics`
- `ligand_sdf_uri`
- `complex_mmcif_uri`
- `predicted_ligand_attachment_atom`
- `predicted_covalent_edge`
- `matched_warhead_type`
- `predicted_warhead_type`
- `covalent_docking_score`
- `noncovalent_vina_score`
- docking protocol refs

Risk:

Task 28 can write lifecycle-valid rows that are not diagnostically complete enough for Task 30+ evaluation.

### Task 29: Implement mmCIF-First Export Interface

Status: **P1/P2 depending on scope.**

Strong points:

- mmCIF is authoritative.
- PDB is optional compatibility output only.
- Export failure maps to `COMPLEX_EXPORT_FAILED`.

Missing:

- mmCIF writer library or internal writer decision.
- Exact linkage representation.
- Atom identity mapping from generated ligand to exported complex.
- How export failure preserves diagnostics.
- Whether ligand-only SDF is written for invalid samples.

Risk:

Without a writer decision, tests may validate a simplified fake export that does not guarantee authoritative mmCIF behavior.

### Task 30: Implement Evaluation Summary And Denominator Checks

Status: **P1, equations strong but manifest dependency missing.**

Strong points:

- Conservation equations are documented.
- `EvaluationSummary` exists in code.
- Invalid samples remain in validity and failure-mode denominators.
- Evaluation must not infer requested/attempted counts from files on disk.

Missing:

- Formal `GenerationRunManifest` input.
- Whether CLI should accept manifest only, or results plus manifest.
- How corrupt lifecycle rows are handled before aggregation.
- How sampling failure artifacts are loaded.
- Whether evaluation summary includes split/family strata in v1 Task 30 or later Task 33.

Risk:

Evaluation can pass denominator equations using incomplete or inferred run counts.

## Checkpoint B/C Review

### Checkpoint B: Model And Training Gate

Status: **Not ready until Task 17 schema is frozen.**

Documented acceptance:

- Model forward smoke test passes.
- Training smoke run logs required loss and denominator fields.
- Forced-positive and Q2 stratification fixtures pass.
- `python -m compileall -q scripts src` passes.

Missing:

- Explicit command list for all Checkpoint B evidence.
- Fixture bundle that covers forced positive, zero negatives, missing state, pending geometry, pending SMARTS, and Q2.
- Contract version and artifact hash evidence.

Risk:

Checkpoint B can pass on synthetic tensors that do not prove compatibility with Task 1-16 outputs.

### Checkpoint C: Inference And Evaluation Gate

Status: **Documented as Task 26-33, not Task 26-30 only.**

Observation:

`implementation-plan.md` defines Checkpoint C dependencies as Tasks 26-33. Therefore Task 30 alone cannot close the inference/evaluation gate.

Required after Task 30:

- Lifecycle validation and failure mode reports.
- Docking protocol manifest interface.
- Split-aware evaluation reports.

Risk:

Stopping at Task 30 would verify denominator equations but not docking protocol eligibility or split-aware reporting.

## Documentation-Code Interface Drift

### P0: Public API is documented before implementation, but Task 17 needs a placement decision

Documented but not implemented:

- `ModelBatch`
- `ModelForwardOutput`
- `BatchSpec`
- `BatchInspectionReport`
- `TrainingDatasetIndex`
- `TrainingRunManifest`
- `CheckpointRef`
- `ReactiveSiteGenerationRequest`
- `ValidatedRequest`
- `GenerationRunManifest`
- `SamplingSystemFailure`
- `DockingProtocolManifest`

Decision needed:

Should these live in `contracts` as public semantic types, or in package-specific modules with only shared enums in `contracts`?

Impact:

If this is not decided before Task 17, package boundaries will drift.

### P1: `CovalentGenerationResult` is narrower in code than in documents

Code currently models lifecycle and artifacts, but not the full result diagnostics specified by the IO contract.

Impact:

Task 28 and Task 30 may become incompatible unless the code type is later expanded or result diagnostics are represented inside artifacts with a documented schema.

### P1: Evaluation CLI input shape is inconsistent

Some docs show `summarize_results --results ...`; interface principles say evaluation must use run manifest counts, result rows, and sampling failure artifacts.

Required before Task 30:

Decide whether evaluation CLI is manifest-first:

```text
python -m covalent_design.evaluation.summarize_results --manifest outputs/generation/<job_id>/run_manifest.yml
```

or mixed input:

```text
python -m covalent_design.evaluation.summarize_results --results ... --manifest ...
```

The first is safer.

## Missing Schemas And Contracts

### P0: Must define before Task 17

1. `ModelBatch`
2. `BatchSpec`
3. `BatchInspectionReport`
4. Task 17 input bundle
5. Data Release Gate bundle consumption policy
6. fail-before-tensor error codes
7. `inspect_batch` output schema
8. static vs dynamic candidate boundary
9. chemical-state handling in batch construction
10. visual/quality/split gate handling in batch construction

### P1: Must define before specific later tasks

1. `StepwiseCandidateSet`
2. `ModelForwardOutput` PMDM output vocabulary
3. `MaskAudit`
4. `TrainingDatasetIndex`
5. `LossReport` serialized schema
6. `TrainingRunManifest`
7. checkpoint manifest
8. `ReactiveSiteGenerationRequest` canonical schema
9. `GenerationRunManifest`
10. `SamplingSystemFailure`
11. `CovalentGenerationResult` complete row schema
12. `ExportReport`
13. `DockingProtocolManifest`
14. `DockingScoreEligibleResultIndex`

## Missing Error Codes / Failure Reasons

### P0: Task 17 model batch errors

Needed:

- `MODEL_BATCH_ARTIFACT_MISSING`
- `MODEL_BATCH_CHECKSUM_MISMATCH`
- `MODEL_BATCH_CONTRACT_VERSION_UNSUPPORTED`
- `MODEL_BATCH_REQUIRED_STATE_UNAVAILABLE`
- `MODEL_BATCH_RELEASE_GATE_FAILED`
- `MODEL_BATCH_EDGE_CANDIDATES_MISSING`
- `MODEL_BATCH_COORDINATES_MISSING`
- `MODEL_BATCH_RULE_TABLE_MISMATCH`
- `MODEL_BATCH_SPLIT_MANIFEST_MISMATCH`

Why:

Task 17 acceptance says missing artifact references fail before tensor construction. That must be testable as structured model/training contract failure, not generic exception text.

### P1: Final decode and result lifecycle failures

Needed:

- Failure priority ordering.
- Whether multiple failed gate checks are all preserved.
- Whether `NO_COVALENT_EDGE_PREDICTED` or `COVALENT_EDGE_BELOW_THRESHOLD` wins when no candidate passes.
- Whether `REQUIRED_GATE_STATE_UNAVAILABLE` outranks geometry/SMARTS checks.

### P1: Sampling system failure codes

Needed:

- crash
- OOM
- timeout
- retry exhausted
- checkpoint load failure
- sampler invariant violation

These should be run-level failure categories, not `CovalentGenerationResult.primary_failure_reason`.

## Missing Test Fixtures

### P0: Must exist before Task 17 implementation

1. Minimal accepted finalized record that builds one valid `ModelBatch`.
2. Missing required artifact ref fails before tensor construction.
3. Artifact checksum mismatch fails before tensor construction.
4. Missing `coordinates` artifact fails before tensor construction.
5. Missing `edge_candidates` artifact fails before tensor construction.
6. Missing required protein chemical state follows the chosen Task 17 policy.
7. `inspect_batch` prints deterministic JSON summary.

### P1: Needed before Tasks 18-25

1. Natural positive within radius.
2. Forced positive outside radius.
3. Zero natural negatives.
4. Pending SMARTS.
5. Pending geometry.
6. Missing required protein state.
7. Q2 keep-with-flag accepted-core record.
8. Rejected/conflict/multi-linkage exclusion.
9. Scaffold split assignment.
10. Protein-cluster split assignment.
11. Visual-blocked record.
12. Denominator conservation across family/timestep strata.

### P1: Needed before Tasks 26-30

1. All `REQUEST_*` validation errors.
2. Valid request with fixed ligand heavy atom count.
3. Valid request with size range.
4. Request with conflicting fixed/range size controls.
5. Sampling crash/OOM/timeout/retry-exhausted artifacts.
6. Valid generation result.
7. Invalid generation result with ligand diagnostics.
8. All-candidates-fail result.
9. Valid internal result with mmCIF export failure.
10. Valid exported result not docking-evaluable.
11. Corrupt lifecycle row.
12. QuickVina2-only score rejected as covalent docking score.
13. Evaluation conservation equations.

## Scientific/Methodological Questions

### P1: academic-researcher follow-up required before claiming method strength

1. Forced-positive training policy.

   Question: Does force-including positives outside radius preserve supervision without biasing edge recall or calibration?

2. Detached predicted message weights.

   Question: Is stop-gradient predicted-probability message passing sufficient to prevent label leakage while maintaining training stability?

3. Final rule-first gate.

   Question: How should learned model performance be reported separately from non-learnable rule gate failures?

4. Covalent docking protocol.

   Question: Which covalent docking engine and linkage/constraint representation are scientifically acceptable for v1?

5. Scaffold split method.

   Question: Which de-warheading and scaffold-key algorithm is acceptable for production claims beyond fixture keys?

6. Protein-cluster split method.

   Question: Which sequence identity threshold and clustering authority should define protein generalization?

## Grill-Me Questions For User

### P0: Must answer before Task 17

1. Is `ModelBatch` allowed to contain only tensor refs, or must it also preserve artifact refs/provenance for audit?

   You need one answer. If `inspect_batch` must trace data back to artifacts, provenance cannot be optional.

2. What exactly is the Task 17 input?

   Is it only `records.jsonl`, or is it a Data Release Gate bundle containing finalized manifests, split index, quality report, visual check index, rule table hash, and edge candidates?

3. Who excludes visual-blocked or release-gate-failed records?

   Task 17 batch construction, Task 22 dataset policy, or neither? If neither, blocked records can enter training.

4. What is Task 12 `edge_candidates` in Task 17?

   Is it a static supervision artifact, an audit artifact, or the actual candidate source for training? It cannot silently be all three.

5. Missing protein chemical state: fail-before-tensor or downstream mask?

   Pick the rule. If both are allowed, specify exactly which fields decide the path.

6. Is Q2 keep-with-flag included in the default Task 17 batch?

   If yes, where is the quality flag carried? If no, how does Task 22 include it through accepted-core gates?

7. Are scaffold fallback pending records eligible for training?

   If yes, how are they excluded from primary scaffold metrics? If no, which gate removes them?

### P1: Must answer before specific later tasks

1. Task 18: Are stepwise candidate IDs stable across timesteps or regenerated per timestep?
2. Task 20: What concrete API guard prevents label tensors from becoming message weights?
3. Task 21: If the top candidate fails and the second candidate passes, is the sample valid?
4. Task 21: Are failed higher-ranked candidate diagnostics preserved in valid results?
5. Task 24: What is the minimum fake backbone output required for smoke training?
6. Task 26: Is request input YAML, JSON, or both?
7. Task 26: What is the alternate-location atom policy?
8. Task 27: Are retries counted as attempted samples, sampling system failures, or both?
9. Task 29: Which mmCIF writer is authoritative for v1?
10. Task 32: If no covalent docking engine is available, can Checkpoint C pass with protocol validation only?

## P0 Must Answer Before Task 17

1. Freeze `ModelBatch`.
2. Freeze `BatchSpec`.
3. Freeze `BatchInspectionReport`.
4. Freeze Task 17 input bundle.
5. Freeze Data Release Gate consumption policy.
6. Freeze fail-before-tensor error codes.
7. Freeze `inspect_batch` CLI output.
8. Freeze static/dynamic edge candidate boundary.
9. Freeze chemical-state handling.
10. Freeze visual/quality/split gate handling.

## P1 Must Answer Before Specific Later Task

1. Task 18: `StepwiseCandidateSet` schema and timestep denominator behavior.
2. Task 19: fake PMDM backbone interface and adapter output vocabulary.
3. Task 20: anti-leakage message-weight API.
4. Task 21: final decode failure priority and invalid result metadata.
5. Task 22: `TrainingDatasetIndex` and Data Release Gate consumption.
6. Task 23: `MaskAudit` and denominator strata schema.
7. Task 24: smoke config and expected `LossReport`.
8. Task 25: run/checkpoint manifest schema.
9. Task 26: canonical request schema and file format.
10. Task 27: sampling failure artifact schema.
11. Task 28: full result row schema.
12. Task 29: mmCIF writer and linkage representation.
13. Task 30: manifest-first evaluation CLI.

## P2 Deferrable Documentation Improvements

1. Add a Task 17+ artifact flow diagram to `docs/specs/README.md`.
2. Convert open questions in `02-model.md`, `03-training.md`, `04-evaluation.md`, and `05-inference.md` into "blocked before Task X" tables.
3. Add a review closure index under `docs/reviews/`.
4. Later simplify `ArtifactRef` compatibility behavior after callers are stable.
5. Later simplify `ValidationReceipt` `passed`/`ok` compatibility.
6. Add examples for all major manifest JSON/YAML files once schemas are frozen.

## Recommended ADRs Or Spec Updates

### Required before Task 17

1. ADR or decision note: Data Release Gate to ModelBatch boundary.
2. `interface-design.md`: full `ModelBatch`, `BatchSpec`, `BatchInspectionReport`, and `inspect_batch` schema.
3. `02-model.md`: static Task 12 candidates vs dynamic Task 18 candidates.
4. `verification-matrix.md`: Task 17 evidence commands and fixtures.

### Required before Task 20

1. ADR or decision note: message-weight leakage-prevention design.

### Required before Task 29/32

1. ADR or decision note: mmCIF writer and covalent docking protocol authority.

### Required before Task 30

1. `interface-design.md` and `04-evaluation.md`: manifest-first evaluation input contract.

## Recommended Skill Workflow For Fixing The Docs

1. `api-and-interface-design`

   Freeze `ModelBatch`, manifests, request/result schemas, and CLI output contracts.

2. `grill-with-docs`

   Ask the P0 questions one by one and update the docs only after each decision is explicit.

3. `documentation-and-adrs`

   Write the ADRs and spec updates for contract boundaries.

4. `doubt-driven-development`

   Review the frozen contracts for semantic holes that tests could miss.

5. `code-review-and-quality`

   Review the final Task 17 implementation plan before code starts.

6. `academic-researcher`

   Follow up on forced positives, detached message weights, covalent docking, scaffold keys, and protein clustering method evidence.

## Files That Should Not Be Touched Yet

Do not modify these until the Task 17 contract is frozen:

- `PMDM/`
- `PocketFlow/`
- `src/covalent_design/model/`
- `src/covalent_design/training/`
- `src/covalent_design/inference/`
- `src/covalent_design/evaluation/`

Do not modify these as part of the Task 17 documentation freeze unless the change is specifically scoped:

- `src/covalent_design/data/`
- `src/covalent_design/rules/`
- `src/covalent_design/candidates/`
- `src/covalent_design/viz/`
- existing Task 1-16 fixtures

## Required Fixes Before Task 17

Required documentation fixes:

1. Define Task 17 input bundle.
2. Define full `ModelBatch`.
3. Define fail-before-tensor errors.
4. Define `inspect_batch` output.
5. Define static/dynamic candidate boundary.
6. Define chemical-state handling.
7. Define release-gate handling.
8. Add Task 17 fixtures to the verification matrix.

Required user decisions:

1. Is Task 17 input `records.jsonl` or full release bundle?
2. Where do quality/visual/split gates apply?
3. What does Task 12 edge candidate artifact mean for Task 17?
4. How is missing chemical state handled?
5. Where do Q2 and scaffold fallback records enter or leave the pipeline?

## Deferrable Improvements

Can wait until after Task 17 contract freeze:

1. Full inference request schema examples.
2. Full generation result diagnostics examples.
3. Docking protocol manifest examples.
4. Production scaffold key chemistry library decision.
5. Production protein clustering authority.
6. Review closure dashboard.

## Final Readiness Decision

Current status:

```text
Task 17 implementation readiness: NO
Task 17 contract-freeze readiness: YES
Task 17 fixture-design readiness: YES
Task 18+ implementation readiness: NO
Checkpoint B readiness: NO
Checkpoint C readiness: NO
```

The next correct action is not to implement `src/covalent_design/model/batch.py` immediately. The next correct action is to freeze the Task 17 public contract and update the relevant specs/ADR first.
