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
- `ingest --out <dir>` writes `source_records.jsonl` and `ingest_index.json` under the output directory, compatible with `normalize --interim-root`.
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

**Goal:** Convert linkage records into accepted/rejected normalized records with atom mapping and Q0/Q1/Q2 behavior. Includes cross-source identity resolution (duplicate merge, conflict exclusion) and a CLI entry point.

**Files/modules:**

- `src/covalent_design/data/normalize.py`
- `src/covalent_design/data/quality.py`
- `tests/data/test_normalize.py`
- `tests/data/test_normalize_cli.py`
- `tests/fixtures/normalize/`

**Dependencies:** Tasks 7, 8.

**Acceptance criteria:**

- Target atom and ligand attachment atom mapping is verified.
- Multi-linkage records are rejected from first training core with lineage.
- Q0 hard rejection, Q1 default rejection, and Q2 keep-with-flag behavior are tested.
- Cross-source duplicate records merge lineage; linkage identity conflicts produce conflict groups excluded from accepted output.
- CLI accepts `--interim-root`, `--ingest-index`, `--raw-root`, and `--source` input modes and writes accepted/rejected/conflict JSONL outputs.
- `required_gate_state_unavailable` is recognized as a Q0 quality flag; full protein chemical-state inference/population is deferred and must be wired before any first-core or training release gate relies on protein state.

**Verification:**

```bash
pytest tests/data/test_normalize.py tests/data/test_normalize_cli.py -q
python -m covalent_design.data.normalize --interim-root tests/fixtures/normalize/interim --out-root data/processed/normalize-smoke
```

### Task 10: Build Record Index And Artifact References

**Goal:** Write accepted record indexes and required non-edge artifact references without embedding large arrays.

**Files/modules:**

- `src/covalent_design/data/records.py`
- `src/covalent_design/data/artifact_manifests.py`
- `src/covalent_design/data/build_record_index.py`
- `tests/data/test_records.py`
- `tests/fixtures/records/`

**Dependencies:** Task 9.

**Acceptance criteria:**

- `build_record_index(processed_root)` reads `accepted.jsonl`, `rejected.jsonl`, and `conflicts.jsonl` from `processed_root` and discovers per-record artifacts under `processed_root/artifacts/{record_id}/{role}.*`.
- Missing any of the four required non-edge artifact roles (`protein_atom_table`, `ligand_atom_table`, `ligand_bond_table`, `coordinates`) is a hard validation failure: the envelope returns `passed=False` with structured `ContractErrorInfo` entries and no partial `records.jsonl` is written.
- `records.jsonl` rows each contain `schema_version`, `contract_version`, `record_id`, `core_labels`, `lineage`, `metadata`, and `artifacts` (a list of `ArtifactRef` dicts) with sorted-by-record_id output.
- `rejected_index.jsonl` and `conflict_index.jsonl` are separate from accepted records.
- `artifact_manifest.json` maps each `record_id` to its `ArtifactRef` entries.
- All output is byte-deterministic across repeated runs with identical inputs.
- Task 10 does **not** generate `edge_candidates`, `visual_check`, or split keys — those are appended by later tasks.

**Verification:**

```bash
pytest tests/data/test_records.py -q
python -m covalent_design.data.build_record_index --processed-root tests/fixtures/records/valid
```

### Task 11: Build Rule Calibration Sheet

**Goal:** Generate reviewable per-family evidence for rule curation.

**Files/modules:**

- `src/covalent_design/rules/calibration.py`
- `src/covalent_design/rules/cli/build_calibration_sheet.py`
- `tests/rules/test_calibration.py`
- `tests/fixtures/calibration/`

**Dependencies:** Task 10.

**Acceptance criteria:**

- Calibration CSV has 14 columns: `family_id`, `sample_count`, `representative_record_ids`, `target_atom_distribution`, `ligand_attachment_element_distribution`, `warhead_distribution`, `bond_length_summary`, `protein_side_angle_summary`, `ligand_side_angle_summary`, `outlier_record_ids`, `manual_decision`, `notes`, `pending_smarts_marker`, `pending_geometry_marker`.
- Geometry summaries read pre-computed values from `records.jsonl` entries under `metadata.geometry` (no 3D coordinate re-computation is performed).
- No `edge_candidates` files, directories, or artifact roles are generated — edge candidates are Task 12 scope.
- `pending_smarts_marker` is `"pending"` when the rule table `warhead_rule_status` is `pending` or `allowed_warhead_smarts` is empty; `"calibrated"` when `warhead_rule_status` is `calibrated` with non-empty SMARTS.
- `pending_geometry_marker` is `"pending"` when any of `bond_length`, `protein_side_angle`, or `ligand_side_angle` geometry status is not `calibrated`; `"calibrated"` when all three are explicitly calibrated.
- Families with zero accepted records still produce a row with `sample_count=0`, empty distributions, and an informational notes field.
- Output is byte-deterministic across repeated runs with identical inputs.

**Verification:**

```bash
python -m covalent_design.rules.cli.build_calibration_sheet --records <records.jsonl> --rules <rule_table.yml> --out-csv <out-csv>
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

- Public API: `covalent_design.candidates.edge_candidates.build_edge_candidates(records_path: Path, candidate_radius_angstrom: float = 4.0) -> ContractEnvelope`.
- CLI: `python -m covalent_design.candidates.cli.build_edge_candidates --records <records.jsonl> --radius 4.0`.
- Every accepted record has exactly one positive edge.
- Nearby non-attachment ligand atoms within `candidate_radius_angstrom` become no-edge negatives.
- One per-record external artifact is written at `<records_dir>/artifacts/<record_id>/edge_candidates.json`.
- Each artifact includes: `schema_version`, `contract_version`, `record_id`, `role` (value `"edge_candidates"`), `lineage`, `positive_edge`, `negative_edges`, `denominators`, `artifact_refs`, and `empty_radius_window`.
- `denominators` has 10 fields: `candidate_count`, `natural_candidate_count`, `forced_positive_count`, `eligible_edge_count`, `masked_candidate_count`, `edge_loss_denominator`, `bond_type_loss_denominator`, `geometry_loss_denominator`, `message_passing_candidate_count`, `gate_evaluated_count`.
- Zero negative windows encode `empty_radius_window: true` with an empty `negative_edges` list — this is a valid result, not a failure.
- Missing `coordinates`, `protein_atom_table`, or `ligand_atom_table` artifact refs produce structured `ContractErrorInfo` entries; the envelope returns `ok=False` and no partial output is written for the affected record.
- Task 12 does **not** update `records.jsonl` or `artifact_manifest.json` with edge-candidate refs, and does not produce splits, visual-check, or finalized-manifest artifacts — those are Task 13–15 scope.

**Verification:**

```bash
pytest tests/candidates/test_edge_candidates.py -q
python -m covalent_design.candidates.cli.build_edge_candidates --records tests/fixtures/edge_candidates/valid/records.jsonl --radius 4.0
```

### Task 13: Finalize Record Manifests

**Goal:** Close the two-phase record/artifact manifest lifecycle by appending edge-candidate artifact refs to every accepted record and updating the manifest.

**Files/modules:**

- `src/covalent_design/data/artifact_manifests.py`
- `src/covalent_design/data/cli/finalize_record_manifests.py`
- `tests/data/test_finalize_record_manifests.py`
- `tests/fixtures/finalize_record_manifests/`

**Dependencies:** Task 12.

**Acceptance criteria:**

- Public API: `finalize_record_manifests(records_path: Path) -> ContractEnvelope[dict[str, object]]` reads `records.jsonl` and `artifact_manifest.json` from the same directory. For every accepted record, discovers `artifacts/<record_id>/edge_candidates.json` and validates embedded `artifact_refs` inside it (each ref's checksum must match the referenced file on disk).
- Hard failures (envelope returns `ok=False`, no partial writes to `records.jsonl` or `artifact_manifest.json`):
  - `EDGE_CANDIDATE_ARTIFACT_MISSING`: `edge_candidates.json` not found for a record.
  - `EDGE_CANDIDATE_ARTIFACT_DUPLICATE`: an `edge_candidates` artifact ref is already present in the record or manifest (re-run guard).
  - `EDGE_CANDIDATE_RECORD_ID_MISMATCH` / `EDGE_CANDIDATE_ROLE_INVALID`: `edge_candidates.json` does not identify the accepted record or role it is linked to.
  - `EDGE_CANDIDATE_UNREADABLE`: `edge_candidates.json` cannot be parsed.
  - Checksum mismatch in any embedded artifact ref inside `edge_candidates.json`.
  - `ARTIFACT_MANIFEST_OBSOLETE_UNLINKED`: `artifact_manifest.json` contains entries for record ids not present in `records.jsonl`.
  - `RECORDS_UNREADABLE` / `ARTIFACT_MANIFEST_UNREADABLE`: input files cannot be parsed.
- On success, appends an `edge_candidates` `ArtifactRef` dict to each accepted record's `artifacts` list and to `artifact_manifest.json`. Artifact lists remain sorted by role.
- `rejected_index.jsonl` and `conflict_index.jsonl` are not modified.
- Output is byte-deterministic across repeated runs with identical inputs.
- Task 13 does **not** generate edge candidates (Task 12), splits (Task 14), visual checks (Task 15), or quality reports (Task 16).
- CLI: `python -m covalent_design.data.cli.finalize_record_manifests --records <records.jsonl>` prints a JSON summary (`ok`, `record_count`, `edge_candidate_count`, `errors`) to stdout and exits zero on success, non-zero on error.

**Verification:**

```bash
pytest tests/data/test_finalize_record_manifests.py -q
python -m covalent_design.data.cli.finalize_record_manifests --records tests/fixtures/finalize_record_manifests/valid/records.jsonl
```

### Task 14: Build Leakage-Aware Splits

**Goal:** Generate leakage-aware train/val/test splits with scaffold key derivation, protein cluster integrity enforcement, fallback accounting, and manual review overrides.

**Files/modules:**

- `src/covalent_design/data/splits.py`
- `src/covalent_design/data/cli/build_splits.py`
- `tests/data/test_splits.py`
- `tests/data/test_splits_contracts.py`
- `tests/fixtures/splits/`

**Dependencies:** Task 13.

**Acceptance criteria:**

- CLI: `python -m covalent_design.data.cli.build_splits --records <records.jsonl> --policy <policy.json> --out-root <out_root>`. `--policy` is optional; defaults to 80/10/10 ratios, seed 42, algorithm `leakage_aware_covalent_splits`.
- Public API: `build_splits(records_path: Path, out_root: Path, policy: SplitPolicy | None = None) -> ContractEnvelope[list[dict]]`. Returns a `ContractEnvelope` whose payload is the assignment list and whose `receipt.ok` indicates success.
- Consumes finalized Task 13 `records.jsonl` (accepted records with `core_labels` and artifact refs including `edge_candidates`).
- Required input fields: `record_id`, `core_labels.bond_type`, `core_labels.warhead_type`, `core_labels.residue_reaction_family`, `core_labels.pdb_id`. Optional: `protein_cluster_id` (from `metadata`), `manual_review_status` (from `metadata`), `scaffold_key` (precomputed, from `metadata` — bypasses derivation).
- Does **not** mutate `records.jsonl` or `artifact_manifest.json`. All split artifacts are written under `--out-root`.
- Does **not** produce visual check or quality report artifacts (Task 15/16 scope).
- Writes `split_index.json`: JSON envelope with `schema_version`, `contract_version`, `role`, `split_policy`, `assignment_count`, and `assignments` list. Each assignment has `record_id`, `split` (`train`/`val`/`test`/`excluded`), `scaffold_key`, `protein_cluster_id`, `residue_reaction_family`, `fallback_reason`, `manual_review_status`.
- Writes `scaffold_keys.jsonl`: per-record JSONL artifacts with `schema_version`, `contract_version`, `record_id`, `role` (`"scaffold_key"`), `algorithm` (`"fixture_key"` until chemistry library accepted), `algorithm_version`, `warhead_match` (`{matched, warhead_type, warhead_smarts, removed_atom_indices}`), `scaffold_key`, `fallback_reason`.
- `fallback_reason` values: `warhead_unmatched`, `missing_scaffold_input`, `missing_protein_cluster_input`, `manual_review_override`.
- `manual_review_status` values: `pending`, `approved`, `rejected`.
- Writes `leakage_report.json`: JSON envelope with `record_count`, `train_count`/`val_count`/`test_count`/`excluded_count`, `fallback_count`, `fallback_by_reason`, `manual_review_count`, `scaffold_overlaps` list, `protein_cluster_overlaps` list, and `zero_overlap` flags.
- Writes `fallback_accounting.json`: JSON envelope with `fallback_count` and `fallback_by_reason` mapping (each reason → `{count, record_ids}`).
- Writes `manual_review_index.json`: JSON envelope with `review_count` and `reviewed_records` list (`{record_id, split, fallback_reason, manual_review_status}`).
- Core invariants: zero primary scaffold overlap across train/val/test; zero protein-cluster overlap across train/val/test; accepted_record_count = train + val + test + excluded.
- `reviewer`, `reviewed_at`, and `notes` fields on manual review entries are deferred until a manual review workflow is established.
- Scaffold key derivation uses `algorithm: "fixture_key"` (metadata-based hashing of `core_labels` identity fields: `warhead_type`, `residue_reaction_family`, `bond_type`, `ligand_atom_element`, `ligand_atom_index`, `ligand_atom_name`, `target_atom_index`, `target_atom_name`) until a user-accepted chemistry library is available. Precomputed `scaffold_key` values from `metadata` bypass derivation.
- Protein clustering enforces same-split placement via `protein_cluster_id`. Records missing the key are excluded with `missing_protein_cluster_input`. Real clustering authority is a deferred user decision.
- Fallback priority chain: `missing_protein_cluster_input` > `missing_scaffold_input` > `warhead_unmatched` > `manual_review_override`.
- `warhead_unmatched` records are excluded from primary split metrics unless `manual_review_status = "approved"`.
- Count conservation: `len(assignments) == train + val + test + excluded`.
- Invalid input (missing `core_labels` or required fields) returns `receipt.ok=False` with structured `ContractErrorInfo` entries and writes no partial split artifacts.

**Verification:**

```bash
pytest tests/data/test_splits.py tests/data/test_splits_contracts.py -q
python -m covalent_design.data.cli.build_splits --records tests/fixtures/splits/records/scaffold_no_leakage_records.jsonl --out-root data/splits/smoke
```

### Task 15: Export Visual Checks

**Goal:** Generate sampled visual inspection artifacts with deterministic sampling, detailed per-record fields, and explicit gate/blocking semantics.

**Files/modules:**

- `src/covalent_design/viz/visual_checks.py`
- `src/covalent_design/viz/cli/export_visual_checks.py`
- `tests/viz/test_visual_checks.py`
- `tests/fixtures/visual_checks/`

**Dependencies:** Tasks 10, 13.

**Acceptance criteria:**

- CLI: `python -m covalent_design.viz.cli.export_visual_checks --records <records.jsonl> --out-root <out_root> [--sample-count N] [--seed 42]`. `--sample-count` is optional; when omitted all accepted records are sampled. `--seed` defaults to 42.
- Public API: `export_visual_checks(records_path: Path, out_root: Path, sample_count: Optional[int] = None, seed: int = 42) -> ContractEnvelope[VisualCheckIndex]`. Returns a `ContractEnvelope` whose payload is the `VisualCheckIndex` and whose `receipt.ok` indicates success.
- Consumes finalized Task 13 `records.jsonl` (accepted records with `core_labels` and artifact refs including `edge_candidates`).
- Required input fields: `record_id`, `core_labels` (including `residue_reaction_family`, `warhead_type`, `target_atom_*`, `ligand_atom_*`), and `edge_candidates` artifact ref (for positive edge data). Optional: `metadata.geometry` (for `distance` and `local_angles`).
- Does **not** mutate `records.jsonl` or `artifact_manifest.json`. All visual check artifacts are written under `--out-root`.
- Does **not** produce an ETL quality report (Task 16 scope).
- Writes `visual_check_index.json` under `out_root`: JSON envelope with `schema_version` (`"1"`), `contract_version` (`"1.0.0"`), `role` (`"visual_check_index"`), `sample_policy` (`{sample_count, seed, total_accepted}`), `status_counts` (`{pending, pass, fail, needs_rule_review}`), `blocking_counts` (`{blocking_first_core, non_blocking}`), and `records` list. Each `records` entry has `record_id`, `status`, `blocking_first_core`, and `artifact_ref` (an `ArtifactRef` pointing to `artifacts/<record_id>/visual_check.json`).
- Writes `artifacts/<record_id>/visual_check.json` for each sampled record: JSON artifact with `schema_version`, `contract_version`, `record_id`, `role` (`"visual_check"`), `target_atom` (ProteinAtomIdentity dict), `ligand_attachment_atom` (LigandAtomIdentity dict), `covalent_edge` (`{target_atom, ligand_atom, bond_type, bond_length}` from edge_candidates positive edge), `residue_reaction_family`, `warhead_annotation` (`{warhead_type, warhead_smarts | null}`), `distance` (float | null, from `metadata.geometry.bond_length.value`), `local_angles` (`{protein_side: float | null, ligand_side: float | null}` | null, from `metadata.geometry`), `status` (one of `"pending"`, `"pass"`, `"fail"`, `"needs_rule_review"`), and `blocking_first_core` (bool).
- Status values and gate semantics:
  - `pending` — visual check not yet performed; blocks first-core release until reviewed.
  - `pass` — visual inspection passed; does not block.
  - `fail` — structural or annotation defect confirmed; blocks release until resolved.
  - `needs_rule_review` — rule table cannot decide; blocks release until curator decision.
  - `blocking_first_core` is `true` for `pending`, `fail`, and `needs_rule_review`; `false` only for `pass`.
- Optional geometry policy: `distance` and `local_angles` fields are populated from `metadata.geometry` when available; missing values are written as `null` (valid output, not a failure). Geometry presence/absence does not affect `status` assignment.
- Deterministic sampling: records are sorted by `record_id` before sampling. Given identical inputs (same `records_path`, `sample_count`, `seed`), the selected subset and all output files are byte-deterministic across repeated runs.
- When `sample_count` is `None`, all accepted records are sampled.
- Invalid input (missing required `core_labels` fields or `edge_candidates` ref) returns `receipt.ok=False` with structured `ContractErrorInfo` entries and writes no partial visual check artifacts.

**Verification:**

```bash
python -m unittest tests.viz.test_visual_checks -v
python -m covalent_design.viz.cli.export_visual_checks --records tests/fixtures/visual_checks/valid/records.jsonl --out-root data/viz/smoke --sample-count 5 --seed 42
```

### Task 16: Write ETL Quality Report

**Goal:** Produce the release-gate report that reconciles sources, records, candidates, splits, and visual checks.

**Files/modules:**

- `src/covalent_design/data/quality_report.py`
- `src/covalent_design/data/cli/write_quality_report.py`
- `tests/data/test_quality_report.py`
- `tests/fixtures/quality_report/`

**Dependencies:** Tasks 13, 14, 15.

**Acceptance criteria:**

- Public API: `write_quality_report(processed_root: Path, *, ingest_roots: Optional[list[Path]] = None, splits_root: Optional[Path] = None, visual_checks_root: Optional[Path] = None, out_path: Optional[Path] = None) -> ContractEnvelope[dict]`. Returns a `ContractEnvelope` whose payload is the full report dict (role `"quality_report"`) and whose `receipt.ok` reflects source coverage and count reconciliation status.
- CLI: `python -m covalent_design.data.cli.write_quality_report --processed-root <processed_root> [--ingest-roots <dir> ...] [--splits-root <dir>] [--visual-checks-root <dir>] [--out <path>]`. Prints a JSON summary (`{"ok": bool, "errors": [...]}`) to stdout and exits zero on success; data-quality failures use the project `data_quality_gate_failed` exit code.
- Reads `records.jsonl`, `rejected_index.jsonl`, and `conflict_index.jsonl` from `processed_root`. Discovers per-record `edge_candidates.json` artifacts under `processed_root/artifacts/<record_id>/`.
- Report includes all required sections: `source_coverage`, `reconciliation`, `family_distribution`, `residue_distribution`, `warhead_distribution`, `linkage_quality`, `geometry_quality`, `protein_chemical_state_quality`, `candidate_stats`, `quality_tier_distribution`. When `--splits-root` is provided, `split_stats` is included. When `--visual-checks-root` is provided, `visual_check_summary` is included.
- **`source_coverage`**: populated from each `--ingest-roots` entry's `ingest_index.json`. Each source entry reports `complete_for_v1`, `record_count`, and `failure_count`. Missing or unreadable `ingest_index.json` is reported with `complete_for_v1: false` and a diagnostic flag (`missing_ingest_index` or `unreadable_ingest_index`).
- **`reconciliation`**: includes `accepted_count`, `rejected_count`, `conflict_count`, `visual_blocked_count`, `total_accounted`, `all_sources_complete_for_v1`, `candidate_coverage_ok`, `split_counts_match`, `visual_counts_match`, and `reconciled`. Count reconciliation equation: `total_accounted = accepted_count + rejected_count + conflict_count`; `reconciled = candidate_coverage_ok and split_counts_match and visual_counts_match`. Incomplete source coverage is reported separately through `all_sources_complete_for_v1: false` and produces a `SOURCE_COVERAGE_INCOMPLETE` structured error.
- **`visual_blocked_count`**: derived from `visual_check_index.json` → `blocking_counts.blocking_first_core`. Represents sampled records blocked from first-core release by visual check status (`pending`, `fail`, or `needs_rule_review`).
- **Count reconciliation**: `complete_for_v1` remains a per-source coverage signal and is reported separately from the `reconciled` count equations. `reconciled` means candidate coverage, split totals, and visual status/blocking totals reconcile. Count failures produce `COUNT_RECONCILIATION_FAILED`; incomplete source coverage produces `SOURCE_COVERAGE_INCOMPLETE`.
- **`family_distribution`**: from `core_labels.residue_reaction_family`. **`residue_distribution`**: derived by splitting `residue_reaction_family` on `"_"` and taking the residue token. **`warhead_distribution`**: from `core_labels.warhead_type`.
- **`linkage_quality`**: includes `bond_type_distribution` (from `core_labels.bond_type`) and `linkage_count_distribution` (always `{"1": accepted_count}` for monodentate-only v1).
- **`geometry_quality`**: min/max/mean/count stats for `bond_length`, `protein_side_angle`, `ligand_side_angle` from `metadata.geometry`, plus `records_missing_geometry` count.
- **`protein_chemical_state_quality`**: `explicit_state_count`, `inferred_state_count`, and `records_with_inferred_state` list.
- **`candidate_stats`**: aggregates `denominators` fields (`candidate_count`, `natural_candidate_count`, `forced_positive_count`) and `empty_radius_window` flag across all records with readable `edge_candidates.json` artifacts. Includes `empty_radius_window_count` and `record_count` (count of records with readable edge-candidate artifacts).
- **`split_stats`**: `train_count`, `val_count`, `test_count`, `excluded_count`, `fallback_count` from `split_index.json` assignments.
- **`visual_check_summary`**: `sampled_count`, `total_accepted`, `status_counts` (`pending`/`pass`/`fail`/`needs_rule_review`), and `blocking_counts` (`blocking_first_core`/`non_blocking`) from `visual_check_index.json`.
- **`quality_tier_distribution`**: from `metadata.quality.quality_tier`.
- Missing `records.jsonl` returns `receipt.ok=False` with `RECORDS_FILE_NOT_FOUND`; unreadable `records.jsonl` returns `RECORDS_UNREADABLE`. Unreadable `rejected_index.jsonl`, `conflict_index.jsonl`, or provided `visual_check_index.json` returns structured data errors (`REJECTED_INDEX_UNREADABLE`, `CONFLICT_INDEX_UNREADABLE`, `VISUAL_CHECK_INDEX_UNREADABLE`) instead of silently zeroing counts. No partial output is written for missing required record input.
- Output is byte-deterministic across repeated runs with identical inputs.
- The report is the **Data Release Gate** (Checkpoint A) artifact: all sources `complete_for_v1`, `visual_blocked_count == 0`, `reconciled == true`, and `total_accounted > 0` must hold before model training begins.
- Does **not** produce model, training, or inference artifacts.

**Verification:**

```bash
pytest tests/data/test_quality_report.py -q
python -m covalent_design.data.cli.write_quality_report --processed-root tests/fixtures/quality_report/valid --ingest-roots tests/fixtures/quality_report/valid/ingest/covbinder_in_pdb --ingest-roots tests/fixtures/quality_report/valid/ingest/covpdb --splits-root tests/fixtures/quality_report/valid/splits --visual-checks-root tests/fixtures/quality_report/valid/visual_checks --out data/reports/quality_report.json
```

### Checkpoint A: Data Release Gate

**Dependencies:** Tasks 1-16.

**Acceptance criteria:**

- All required sources report `complete_for_v1: true` in the ETL quality report.
- `reconciled` is `true`; `SOURCE_COVERAGE_INCOMPLETE` errors are absent.
- `visual_blocked_count` is zero (no sampled records blocked by `pending`, `fail`, or `needs_rule_review`).
- `total_accounted > 0` and equals `accepted_count + rejected_count + conflict_count`.
- Verification matrix rows through visual checks and ETL quality report pass on fixtures.
- `python -m compileall -q scripts src` passes.
- No project-owned code imports from PMDM/PocketFlow for ETL.
- The quality report JSON is byte-deterministic across repeated runs with identical inputs.
- `complete_for_v1` source coverage and `reconciled` count equations both pass; neither one substitutes for the other.

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
