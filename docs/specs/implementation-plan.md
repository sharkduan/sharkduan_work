# Implementation Plan: Covalent Design Modules

## Overview

This plan breaks the final specifications and interface design into implementable, testable tasks. It follows the accepted project order: shared contracts first, ETL and rule artifacts before model work, then model/training, then inference/evaluation, then governance fixtures.

Implementation should keep every task small enough for one focused session and leave the repository in a compilable state.

## Dependency Graph

```text
Shared contract types and validators
  -> artifact IO and validation receipts
  -> raw manifest validation
  -> source ingestion
  -> normalized linkage identity
  -> rule table validation
  -> record index
  -> edge candidates
  -> final record manifests
  -> splits, visual checks, ETL quality report
  -> model batch adapter
  -> covalent heads and final decode
  -> training dataset and losses
  -> training reports
  -> inference request validation
  -> generation result lifecycle
  -> mmCIF export
  -> evaluation denominator accounting
  -> docking protocol reporting
```

## Milestones

### M1: Shared Contract Foundation

Goal: Provide the stable schemas, validation receipts, artifact references, structured errors, and denominator checks used by every module.

### M2: ETL And Rule Release Gate

Goal: Build auditable data processing artifacts through accepted records, rule validation, edge candidates, splits, visual checks, and quality reports.

### M3: Model And Training Smoke Path

Goal: Load accepted record bundles into a PMDM-compatible covalent model path and compute losses with explicit masks and denominators.

### M4: Inference And Evaluation Smoke Path

Goal: Validate requests, write valid/invalid result rows, account for sampling system failures, export complexes, and evaluate lifecycle denominators.

### M5: Governance And Release Fixtures

Goal: Add minimal committed fixtures and checks that prove the public interfaces and release gates work without requiring heavyweight scientific environments in default CI.

## Tasks

### Task 1: Create Shared Contract Package Skeleton

**Goal:** Establish `covalent_design.contracts` as the only public semantic layer.

**Files/modules:**

- `src/covalent_design/contracts/__init__.py`
- `src/covalent_design/contracts/types.py`
- `src/covalent_design/contracts/errors.py`
- `tests/contracts/`

**Dependencies:** None.

**Acceptance criteria:**

- `ArtifactRef`, `ValidationReceipt`, `ContractEnvelope`, and `ContractError` exist.
- Public enum-like values are centralized for quality, visual status, lifecycle status, request errors, and failure reasons.
- Importing from `covalent_design.contracts` works from tests.

**Verification:**

```bash
python -m compileall -q scripts src
pytest tests/contracts -q
```

### Task 2: Implement Denominator And Lifecycle Validators

**Goal:** Make denominator conservation and result lifecycle constraints executable.

**Files/modules:**

- `src/covalent_design/contracts/denominators.py`
- `src/covalent_design/contracts/lifecycle.py`
- `tests/contracts/test_denominators.py`
- `tests/contracts/test_lifecycle.py`

**Dependencies:** Task 1.

**Acceptance criteria:**

- `EdgeDenominators.validate()` rejects negative counts and invalid forced-positive/message-passing combinations.
- `EvaluationSummary.validate()` enforces all IO contract conservation equations.
- `CovalentGenerationResult` lifecycle validation rejects impossible generation/export/docking state combinations.

**Verification:**

```bash
pytest tests/contracts/test_denominators.py tests/contracts/test_lifecycle.py -q
```

### Task 3: Implement Artifact IO Primitives

**Goal:** Provide checksum, manifest, and validation receipt utilities for downstream modules.

**Files/modules:**

- `src/covalent_design/io/artifacts.py`
- `src/covalent_design/io/jsonl.py`
- `src/covalent_design/contracts/receipts.py`
- `tests/io/test_artifacts.py`

**Dependencies:** Task 1.

**Acceptance criteria:**

- `ArtifactRef` can be generated from a file and validated against sha256.
- JSONL read/write preserves schema version and contract version fields.
- Validation receipts can be written and read as JSON.

**Verification:**

```bash
pytest tests/io/test_artifacts.py -q
```

### Task 4: Validate Raw Source Manifests

**Goal:** Implement the raw data manifest gate before any source parser can run.

**Files/modules:**

- `src/covalent_design/data/manifests.py`
- `src/covalent_design/data/validate_manifests.py`
- `tests/data/test_manifests.py`
- `tests/fixtures/raw_manifest/`

**Dependencies:** Tasks 1, 3.

**Acceptance criteria:**

- Missing files, checksum mismatch, missing license/access notes, and unstaged extras are reported.
- Files absent from the manifest are ignored by default and listed as extras.
- CLI exits with structured contract error on failure.

**Verification:**

```bash
python -m covalent_design.data.validate_manifests --raw-root tests/fixtures/raw_manifest/valid
pytest tests/data/test_manifests.py -q
```

### Task 5: Add Source Ingestion Interface And CovBinder Smoke Parser

**Goal:** Implement the first source-specific ingestion path using CovBinderInPDB fixtures.

**Files/modules:**

- `src/covalent_design/data/ingest.py`
- `src/covalent_design/data/sources/covbinder_in_pdb.py`
- `tests/data/test_ingest_covbinder.py`
- `tests/data/test_ingest_cli.py`
- `tests/fixtures/covbinder/`

**Dependencies:** Task 4.

**Acceptance criteria:**

- Parser emits source-specific records with lineage fields.
- Parser failure reasons are counted.
- `parse_10_covbinder_records` fixture passes.

**Verification:**

```bash
pytest tests/data/test_ingest_covbinder.py -q
```

### Task 6: Add CovPDB And CovalentInDB Source Parsers

**Goal:** Complete required source ingestion coverage for v1 gates.

**Files/modules:**

- `src/covalent_design/data/sources/covpdb.py`
- `src/covalent_design/data/sources/covalentin_db.py`
- `tests/data/test_ingest_covpdb.py`
- `tests/data/test_ingest_covalentin_db.py`

**Dependencies:** Task 5.

**Acceptance criteria:**

- CovPDB structural records preserve resolution and structural cross-check fields.
- CovalentInDB P0-source fields are parsed and P1/P2 fields are preserved only as metadata.
- Per-source raw manifest coverage can report `complete_for_v1: false` until all gates pass. This is a single-source coverage signal, not the all-source ETL release gate.

**Verification:**

```bash
pytest tests/data/test_ingest_covpdb.py tests/data/test_ingest_covalentin_db.py -q
```

### Task 7: Implement Canonical Identity And Conflict Resolution

**Goal:** Normalize source records into deterministic linkage identities and conflict artifacts.

**Files/modules:**

- `src/covalent_design/data/identity.py`
- `src/covalent_design/data/conflicts.py`
- `tests/data/test_identity.py`

**Dependencies:** Tasks 5, 6.

**Acceptance criteria:**

- Matching canonical keys merge lineage.
- PDB/ligand matches with target/linkage conflicts produce conflict groups.
- `record_id` is deterministic and source ids are not used as canonical ids.

**Verification:**

```bash
pytest tests/data/test_identity.py -q
```

### Task 8: Implement Rule Table Schema And Validation

**Goal:** Make rule-table validation executable before accepted record construction.

**Files/modules:**

- `src/covalent_design/rules/schema.py`
- `src/covalent_design/rules/validate.py`
- `src/covalent_design/rules/cli/validate_rule_table.py`
- `tests/rules/test_rule_table.py`

**Dependencies:** Task 1.

**Acceptance criteria:**

- `family_id == residue_reaction_family` is enforced.
- Empty SMARTS and null geometry are pending/disabled, never permissive.
- Missing anchor atom, ligand neighbor policy, protein state requirements, or valence delta fails validation.

**Verification:**

```bash
pytest tests/rules/test_rule_table.py -q
```

### Task 9: Normalize Structures And Apply Quality Gates

**Goal:** Convert linkage records into accepted/rejected normalized records with atom mapping and Q0/Q1/Q2 behavior.

**Files/modules:**

- `src/covalent_design/data/normalize.py`
- `src/covalent_design/data/quality.py`
- `tests/data/test_normalize_quality.py`

**Dependencies:** Tasks 7, 8.

**Acceptance criteria:**

- Target atom and ligand attachment atom mapping is verified.
- Multi-linkage records are rejected from first training core with lineage.
- Q0 hard rejection, Q1 default rejection, and Q2 keep-with-flag behavior are tested.

**Verification:**

```bash
pytest tests/data/test_normalize_quality.py -q
```

### Task 10: Build Record Index And Artifact References

**Goal:** Write accepted record indexes and non-edge artifacts without embedding large arrays.

**Files/modules:**

- `src/covalent_design/data/records.py`
- `src/covalent_design/data/artifact_manifests.py`
- `tests/data/test_records.py`

**Dependencies:** Task 9.

**Acceptance criteria:**

- `records.jsonl` contains schema version, core labels, lineage, metadata, and artifact references.
- Protein atom table, ligand atom table, ligand bond table, and coordinates are external artifacts.
- Rejected and conflict indexes are separate from accepted `CovalentComplexRecord`.

**Verification:**

```bash
pytest tests/data/test_records.py -q
```

### Task 11: Build Rule Calibration Sheet

**Goal:** Generate reviewable per-family evidence for rule curation.

**Files/modules:**

- `src/covalent_design/rules/calibration.py`
- `src/covalent_design/rules/cli/build_calibration_sheet.py`
- `tests/rules/test_calibration.py`

**Dependencies:** Task 10.

**Acceptance criteria:**

- Calibration sheet includes sample count, representative structures, atom distributions, warhead distribution, geometry summaries, outliers, manual decision, and notes.
- Families with pending SMARTS or geometry are clearly marked.

**Verification:**

```bash
pytest tests/rules/test_calibration.py -q
```

### Task 12: Build Radius-Bounded Edge Candidates

**Goal:** Produce positive and no-edge candidate artifacts for accepted records.

**Files/modules:**

- `src/covalent_design/candidates/edge_candidates.py`
- `src/covalent_design/candidates/cli/build_edge_candidates.py`
- `tests/candidates/test_edge_candidates.py`

**Dependencies:** Tasks 8, 10.

**Acceptance criteria:**

- Every accepted record has exactly one positive edge.
- Nearby non-attachment ligand atoms become no-edge negatives.
- Zero negative windows are encoded as `empty_radius_window`, not failure.

**Verification:**

```bash
pytest tests/candidates/test_edge_candidates.py -q
```

### Task 13: Finalize Record Manifests

**Goal:** Close the two-phase record/artifact manifest lifecycle.

**Files/modules:**

- `src/covalent_design/data/artifact_manifests.py`
- `src/covalent_design/data/cli/finalize_record_manifests.py`
- `tests/data/test_finalize_record_manifests.py`

**Dependencies:** Task 12.

**Acceptance criteria:**

- Every accepted record manifest includes edge-candidate artifact path, format, and checksum.
- Missing or checksum-mismatched edge candidate artifact fails hard.
- No obsolete artifact manifest exists without record linkage unless explicitly marked obsolete or rejected.

**Verification:**

```bash
pytest tests/data/test_finalize_record_manifests.py -q
```

### Task 14: Build Leakage-Aware Splits

**Goal:** Generate random, protein-cluster, and de-warheaded scaffold splits with leakage checks.

**Files/modules:**

- `src/covalent_design/data/splits.py`
- `src/covalent_design/data/cli/build_splits.py`
- `tests/data/test_splits.py`

**Dependencies:** Tasks 10, 11.

**Acceptance criteria:**

- Random, protein-cluster, and scaffold split artifacts are written.
- Primary de-warheaded scaffold overlap across train/val/test is zero.
- `warhead_unmatched` fallback records are excluded from primary scaffold release metrics unless manually reviewed.

**Verification:**

```bash
pytest tests/data/test_splits.py -q
```

### Task 15: Export Visual Checks

**Goal:** Generate sampled visual inspection artifacts and enforce visual gate semantics.

**Files/modules:**

- `src/covalent_design/viz/visual_checks.py`
- `src/covalent_design/viz/cli/export_visual_checks.py`
- `tests/viz/test_visual_checks.py`

**Dependencies:** Tasks 10, 12.

**Acceptance criteria:**

- Sampled artifacts include target atom, ligand attachment atom, covalent edge, family, warhead annotation, distance, and local angles when available.
- `fail` and `needs_rule_review` statuses block sampled records from first-core release until resolved.

**Verification:**

```bash
pytest tests/viz/test_visual_checks.py -q
```

### Task 16: Write ETL Quality Report

**Goal:** Produce the release-gate report that reconciles sources, records, candidates, splits, and visual checks.

**Files/modules:**

- `src/covalent_design/data/quality_report.py`
- `src/covalent_design/data/cli/write_quality_report.py`
- `tests/data/test_quality_report.py`

**Dependencies:** Tasks 13, 14, 15.

**Acceptance criteria:**

- Report includes source coverage, accepted/rejected summary, family/residue/warhead distributions, linkage quality, geometry quality, protein chemical-state quality, candidate statistics, split statistics, and visual check index.
- Per-source `complete_for_v1` gates are reported.
- Accepted, rejected, conflict, and visual-blocked counts reconcile.

**Verification:**

```bash
pytest tests/data/test_quality_report.py -q
```

### Checkpoint A: Data Release Gate

**Dependencies:** Tasks 1-16.

**Acceptance criteria:**

- Verification matrix rows through visual checks and ETL quality report pass on fixtures.
- `python -m compileall -q scripts src` passes.
- No project-owned code imports from PMDM/PocketFlow for ETL.

## Model And Training Tasks

### Task 17: Implement Model Batch Contracts

**Goal:** Convert accepted record bundles into typed model batches without leaking raw artifact details.

**Files/modules:**

- `src/covalent_design/model/batch.py`
- `src/covalent_design/model/inspect.py`
- `tests/model/test_batch.py`

**Dependencies:** Tasks 1, 13.

**Acceptance criteria:**

- `ModelBatch` carries record ids, family keys, target atom identities, ligand heavy-atom count, edge candidates, and expected denominators.
- Missing artifact references fail before tensor construction.
- `inspect_batch` CLI reports batch shape and contract metadata.

**Verification:**

```bash
pytest tests/model/test_batch.py -q
```

### Task 18: Implement Stepwise Candidate Builder For Model State

**Goal:** Rebuild candidates from noisy/generated ligand coordinates during model forward.

**Files/modules:**

- `src/covalent_design/model/candidate_builder.py`
- `tests/model/test_stepwise_candidates.py`

**Dependencies:** Tasks 12, 17.

**Acceptance criteria:**

- Candidates are built from fixed target atom coordinates and current ligand coordinates.
- Positive edge is force-included when noise moves it outside radius.
- Forced positives are counted separately.

**Verification:**

```bash
pytest tests/model/test_stepwise_candidates.py -q
```

### Task 19: Implement PMDM Adapter Skeleton

**Goal:** Provide the PMDM-compatible model boundary without modifying upstream PMDM by default.

**Files/modules:**

- `src/covalent_design/model/pmdm_adapter.py`
- `src/covalent_design/model/config.py`
- `tests/model/test_pmdm_adapter.py`

**Dependencies:** Task 17.

**Acceptance criteria:**

- Adapter accepts `ModelBatch` and returns PMDM-compatible outputs in a `ModelForwardOutput`.
- Checkpoint/config metadata includes contract version and rule table hash fields.
- Tests use a lightweight fake backbone if PMDM dependencies are unavailable.

**Verification:**

```bash
pytest tests/model/test_pmdm_adapter.py -q
```

### Task 20: Implement Covalent Heads And Message-Weight Interface

**Goal:** Add edge existence, bond type, and optional family auxiliary output contracts.

**Files/modules:**

- `src/covalent_design/model/covalent_heads.py`
- `src/covalent_design/model/edge_message_passing.py`
- `tests/model/test_covalent_heads.py`

**Dependencies:** Tasks 18, 19.

**Acceptance criteria:**

- Forward output includes edge logits, bond-type logits, optional family logits, and observed denominators.
- Message weights are detached predicted probabilities.
- Ground-truth labels cannot be passed as message weights through public APIs.

**Verification:**

```bash
pytest tests/model/test_covalent_heads.py -q
```

### Task 21: Implement Final Decode And Validity Gate Interface

**Goal:** Select a valid final covalent edge or emit an invalid decode result.

**Files/modules:**

- `src/covalent_design/model/final_decode.py`
- `src/covalent_design/model/validity_gate.py`
- `tests/model/test_final_decode.py`

**Dependencies:** Tasks 8, 20.

**Acceptance criteria:**

- Final decode sorts candidates by score and applies rule-first gate checks.
- All-candidates-fail path returns invalid result metadata, not a forced edge.
- Gate records edge validity checks and failure reasons.

**Verification:**

```bash
pytest tests/model/test_final_decode.py -q
```

### Task 22: Implement Training Dataset And Batch Loader

**Goal:** Prepare accepted-core training datasets from validated record bundles and split artifacts.

**Files/modules:**

- `src/covalent_design/training/dataset.py`
- `src/covalent_design/training/batch.py`
- `tests/training/test_dataset.py`

**Dependencies:** Tasks 14, 17.

**Acceptance criteria:**

- Default `TrainingDataPolicy(first_core_only=True)` rejects rejected/conflict/multi-linkage indexes.
- Q2 keep-with-flag records are included only through accepted-core path and retain flags.
- Dataset consumes verified split manifests.

**Verification:**

```bash
pytest tests/training/test_dataset.py -q
```

### Task 23: Implement Loss Masks And Denominator Reports

**Goal:** Compute loss eligibility masks and denominator counts from model outputs and rule states.

**Files/modules:**

- `src/covalent_design/training/masks.py`
- `src/covalent_design/training/denominators.py`
- `tests/training/test_masks_denominators.py`

**Dependencies:** Tasks 18, 22.

**Acceptance criteria:**

- Natural positives, forced positives, zero negatives, pending geometry, pending SMARTS, missing state, and Q2 cases are covered.
- Geometry denominator excludes forced positives by default.
- Bond-type denominator excludes no-edge negatives and forced positives by default.

**Verification:**

```bash
pytest tests/training/test_masks_denominators.py -q
```

### Task 24: Implement Loss Report And Smoke Training Loop

**Goal:** Run one fixture-based training step and emit structured loss reports.

**Files/modules:**

- `src/covalent_design/training/losses.py`
- `src/covalent_design/training/train_loop.py`
- `tests/training/test_train_smoke.py`

**Dependencies:** Tasks 20, 23.

**Acceptance criteria:**

- `LossReport` includes all PMDM and covalent loss components.
- Reaction-family consistency through rule masks/gates is required; family auxiliary head remains optional.
- One smoke step completes with fake or minimal backbone.

**Verification:**

```bash
pytest tests/training/test_train_smoke.py -q
```

### Task 25: Implement Training Run Manifest And Checkpoint Metadata

**Goal:** Preserve provenance for train runs and checkpoints.

**Files/modules:**

- `src/covalent_design/training/checkpoints.py`
- `src/covalent_design/training/reports.py`
- `tests/training/test_run_manifest.py`

**Dependencies:** Task 24.

**Acceptance criteria:**

- Run manifest stores config hash, record bundle hash, split hash, rule table hash, denominator report URI, and contract version.
- Checkpoint manifest stores model contract version, rule table version/hash, record bundle hash, and config hash.

**Verification:**

```bash
pytest tests/training/test_run_manifest.py -q
```

### Checkpoint B: Model And Training Gate

**Dependencies:** Tasks 17-25.

**Acceptance criteria:**

- Model forward smoke test passes.
- Training smoke run logs required loss and denominator fields.
- Forced-positive and Q2 stratification fixtures pass.
- `python -m compileall -q scripts src` passes.

## Inference And Evaluation Tasks

### Task 26: Implement Request Schema And Validation

**Goal:** Reject invalid `ReactiveSiteGenerationRequest` inputs before sampling.

**Files/modules:**

- `src/covalent_design/inference/request_schema.py`
- `src/covalent_design/inference/request_validation.py`
- `tests/inference/test_request_validation.py`

**Dependencies:** Tasks 1, 8.

**Acceptance criteria:**

- All `REQUEST_*` error fixtures are covered.
- Ligand size control enforces fixed-or-range-or-absent semantics.
- Missing required chemical state produces `REQUEST_REQUIRED_CHEMICAL_STATE_UNAVAILABLE`.

**Verification:**

```bash
pytest tests/inference/test_request_validation.py -q
```

### Task 27: Implement Generation Run Manifest And Sampling Failure Accounting

**Goal:** Separate request errors, attempted samples, and sampling system failures.

**Files/modules:**

- `src/covalent_design/inference/run_manifest.py`
- `src/covalent_design/inference/sampler.py`
- `tests/inference/test_sampling_failures.py`

**Dependencies:** Task 26.

**Acceptance criteria:**

- `generate()` returns a `GenerationRunManifest`, not a list of results.
- Sampler crash, OOM, timeout, and retry exhaustion write `sampling_system_failures.jsonl`.
- Accepted request counts reconcile as attempted plus sampling-system-failed.

**Verification:**

```bash
pytest tests/inference/test_sampling_failures.py -q
```

### Task 28: Implement Generation Result Writer

**Goal:** Write one `CovalentGenerationResult` row per attempted sample.

**Files/modules:**

- `src/covalent_design/inference/result_schema.py`
- `src/covalent_design/inference/result_writer.py`
- `tests/inference/test_result_writer.py`

**Dependencies:** Tasks 21, 27.

**Acceptance criteria:**

- Valid and invalid sample rows validate lifecycle constraints.
- Invalid rows preserve available ligand, edge, geometry, warhead, and failure diagnostics.
- Request validation errors never create result rows.

**Verification:**

```bash
pytest tests/inference/test_result_writer.py -q
```

### Task 29: Implement mmCIF-First Export Interface

**Goal:** Export valid covalent complexes or record export failure lifecycle status.

**Files/modules:**

- `src/covalent_design/io/mmcif_writer.py`
- `src/covalent_design/inference/complex_export.py`
- `tests/inference/test_complex_export.py`

**Dependencies:** Task 28.

**Acceptance criteria:**

- Valid result exports authoritative mmCIF with structured linkage identity when possible.
- Export failure produces `COMPLEX_EXPORT_FAILED` and leaves docking eligibility not applicable.
- PDB export is optional compatibility output only.

**Verification:**

```bash
pytest tests/inference/test_complex_export.py -q
```

### Task 30: Implement Evaluation Summary And Denominator Checks

**Goal:** Produce lifecycle-aware evaluation summaries from generation run artifacts.

**Files/modules:**

- `src/covalent_design/evaluation/denominator_accounting.py`
- `src/covalent_design/evaluation/result_schema.py`
- `tests/evaluation/test_denominator_accounting.py`

**Dependencies:** Tasks 27, 28.

**Acceptance criteria:**

- Evaluation uses run manifest counts, results, and sampling failure artifacts.
- All conservation equations are enforced.
- Invalid samples are retained in validity and failure-mode denominators.

**Verification:**

```bash
pytest tests/evaluation/test_denominator_accounting.py -q
```

### Task 31: Implement Lifecycle Validation And Failure Mode Reports

**Goal:** Reject corrupt result states before aggregation and report failure modes.

**Files/modules:**

- `src/covalent_design/evaluation/validity_metrics.py`
- `src/covalent_design/evaluation/failure_modes.py`
- `tests/evaluation/test_lifecycle_reports.py`

**Dependencies:** Task 30.

**Acceptance criteria:**

- Corrupt succeeded-docking lifecycle fixtures are rejected before metric aggregation.
- Primary and secondary failure reasons are grouped without hiding lifecycle stage.
- Reports stratify by `residue_reaction_family`.

**Verification:**

```bash
pytest tests/evaluation/test_lifecycle_reports.py -q
```

### Task 32: Implement Docking Protocol Manifest Interface

**Goal:** Validate covalent docking protocol manifests and protect docking score eligibility.

**Files/modules:**

- `src/covalent_design/evaluation/docking_protocol.py`
- `tests/evaluation/test_docking_protocol.py`

**Dependencies:** Task 31.

**Acceptance criteria:**

- Complete protocol manifest is required for covalent docking scores.
- QuickVina2-only fixture can populate `noncovalent_vina_score` but not `covalent_docking_score`.
- `DockingScoreEligibleResultIndex` includes only valid, exported, eligible, succeeded samples with complete protocol manifests.

**Verification:**

```bash
pytest tests/evaluation/test_docking_protocol.py -q
```

### Task 33: Implement Split-Aware Evaluation Reports

**Goal:** Report primary protein-cluster and scaffold results without random-only leakage.

**Files/modules:**

- `src/covalent_design/evaluation/split_metrics.py`
- `src/covalent_design/evaluation/reports.py`
- `tests/evaluation/test_split_reports.py`

**Dependencies:** Tasks 14, 30.

**Acceptance criteria:**

- Reports include protein-cluster and de-warheaded scaffold primary metrics.
- Random split is clearly labeled as debug/secondary.
- Scaffold fallback exclusions are reported.

**Verification:**

```bash
pytest tests/evaluation/test_split_reports.py -q
```

### Checkpoint C: Inference And Evaluation Gate

**Dependencies:** Tasks 26-33.

**Acceptance criteria:**

- Request validation, result lifecycle, sampling failure, mmCIF export, denominator, and docking protocol fixtures pass.
- Evaluation denominator equations pass.
- `python -m compileall -q scripts src` passes.

## Governance And Fixture Tasks

### Task 34: Add CLI Entry Points And Structured Exit Handling

**Goal:** Make public command surfaces match the interface design.

**Files/modules:**

- `src/covalent_design/*/cli/*.py`
- `src/covalent_design/contracts/cli_errors.py`
- `tests/cli/test_exit_codes.py`

**Dependencies:** Tasks 4, 8, 12, 16, 17, 24, 26, 30.

**Acceptance criteria:**

- CLIs map `ContractError` categories to documented exit codes.
- Machine-readable `error.json` can be written when requested.
- Human-readable errors do not need to be parsed by downstream tools.

**Verification:**

```bash
pytest tests/cli/test_exit_codes.py -q
```

### Task 35: Commit Minimal Fixture Set

**Goal:** Provide small, policy-compliant fixtures for lightweight tests.

**Files/modules:**

- `tests/fixtures/`
- `docs/specs/verification-matrix.md`
- `.gitignore`

**Dependencies:** Tasks 1-34 as fixture needs are known.

**Acceptance criteria:**

- Fixture set avoids raw corpora, generated large data, checkpoints, docking outputs, and caches.
- Fixtures cover manifest, record, rule, candidate, result, denominator, and docking protocol contracts.
- Repository hygiene still passes.

**Verification:**

```bash
pytest tests -q
python -m compileall -q scripts src
```

### Task 36: Extend Lightweight CI For Project-Owned Fixtures

**Goal:** Add stable, lightweight contract tests to CI without requiring scientific stacks.

**Files/modules:**

- `.github/workflows/ci.yml`
- `tests/`
- `docs/github-management.md` if CI policy text changes

**Dependencies:** Task 35.

**Acceptance criteria:**

- CI runs compile checks and lightweight contract/fixture tests.
- CI still blocks generated caches and large binary artifacts.
- Heavy RDKit/CUDA/docking workflows remain out of default CI unless fixtures and runners are explicitly approved.

**Verification:**

```bash
python -m compileall -q scripts src
pytest tests/contracts tests/io tests/data tests/rules -q
```

## Recommended Implementation Order

1. Tasks 1-3: shared contracts and artifact IO.
2. Tasks 4-8: manifest, ingestion, identity, and rule validation.
3. Tasks 9-16: ETL record path through quality report.
4. Tasks 17-21: model batch, adapter, heads, and final decode.
5. Tasks 22-25: training dataset, losses, and run manifests.
6. Tasks 26-29: inference request, generation run, result writing, and export.
7. Tasks 30-33: evaluation accounting, lifecycle, docking protocol, and split reports.
8. Tasks 34-36: CLIs, fixtures, and CI.

## Parallelization Opportunities

- After Task 1, Task 3 and Task 8 can proceed in parallel.
- After Task 4, CovBinder, CovPDB, and CovalentInDB source parser work can be parallelized if they write disjoint source modules.
- After Task 10, rule calibration, edge candidates, splits, and visual checks can proceed in parallel with coordination on artifact references.
- After Task 17, model heads and training dataset work can proceed in parallel if batch contracts are stable.
- After Task 26, result writer and evaluation denominator fixtures can proceed in parallel once lifecycle contracts are stable.

## Risks And Mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Schema validation dependency remains undecided | Interfaces may need refactor | Start with dataclasses and validator functions; isolate validation behind `contracts` |
| Scientific dependencies are unavailable in CI | Tests may be brittle | Use fixture and fake-backbone tests in default CI; reserve RDKit/CUDA/docking for manual workflows |
| Source raw formats differ from assumptions | Parser rework | Keep source parser outputs behind `SourceIngestIndex`; preserve raw locators and failure reasons |
| Artifact format choice changes | Downstream churn | Route large data through `ArtifactRef` and loader adapters |
| PMDM integration requires upstream edits | Merge and provenance risk | Start with adapter/fake backbone; require explicit PR if upstream baseline changes |
| Docking protocol not finalized | Evaluation incomplete | Implement manifest validation and not-evaluable path before engine integration |

## Open Questions Before Full V1 Release

- Which schema validation library, if any, should replace plain dataclass validators?
- Which large artifact formats are canonical for atom tables, coordinates, and tensors?
- Which protein chemical-state inference tool and confidence policy are accepted?
- Which protein clustering method and threshold define the primary target split?
- Which covalent docking engine and constraint representation are authoritative?
- Which mmCIF writer should be used?
- What are the initial covalent loss weights and edge-score thresholds?
