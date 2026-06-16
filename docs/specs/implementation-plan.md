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
- Each artifact includes: `schema_version`, `contract_version`, local `edge_candidates_schema_version` (value `"2"`), `record_id`, `role` (value `"edge_candidates"`), `lineage`, `positive_edge`, `negative_edges`, `denominators`, `artifact_refs`, and `empty_radius_window`.
- Local edge-candidate schema v2 adds `positive_edge.ligand_atom_index`, full `positive_edge.target_atom` identity with `atom_index`, and `positive_edge.bond_type`. Legacy flat positive-edge fields remain for compatibility.
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
- CLI: `python -m covalent_design.data.cli.write_quality_report --processed-root <processed_root> [--ingest-roots <dir> ...] [--splits-root <dir>] [--visual-checks-root <dir>] [--out <path>] [--error-out <path>]`. Prints a JSON summary (`{"ok": bool, "errors": [...]}`) to stdout and exits zero on success; data-quality failures use the project `data_quality_gate_failed` exit code.  On failure, `--error-out <path>` writes a `cli_error` JSON file (role `"cli_error"`, schema from `contracts.cli_errors`).
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

**Goal:** Convert finalized `records.jsonl` into typed `ModelBatch` instances. Fail before tensor construction on missing artifacts, checksum mismatches, or unsupported contract versions.

**Files/modules:**

- `src/covalent_design/model/batch.py`
- `src/covalent_design/model/inspect.py`
- `tests/model/test_batch.py`

**Dependencies:** Tasks 1, 13.

**Contracts:** `ModelBatch`, `BatchRecordHeader`, `BatchTensors`, `BatchSpec`, `BatchInspectionReport` — defined in `covalent_design.contracts.types`. `MODEL_BATCH_ERROR_CODES` — 6 codes. `inspect_batch` JSON output schema defined in `interface-design.md`. See ADR 0035.

**Acceptance criteria:**

- `make_model_batch(records_path, batch_spec=None)` accepts finalized `records.jsonl` (Task 13 output) and `BatchSpec | None`.
- Input is a single `records.jsonl` file — NOT a Data Release Gate bundle.
- Constructs `ModelBatch` with provenance layer (`BatchRecordHeader` per record) and computational layer (`BatchTensors` with shapes/dtypes/coordinate_frame). Carries `BatchSpec` in `ModelBatch.batch_spec`.
- `BatchRecordHeader` explicitly carries `target_atom_identity` (resolved from `protein_atom_table` artifact: chain_id, residue_number, residue_name), `target_atom_index` (from `core_labels.target_atom_index`), and `target_atom_artifact_role` (constant `"protein_atom_table"`).
- Carries `static_edge_candidates_refs` (`record_id` → Task 12 `edge_candidates` `ArtifactRef` mapping). Validates existence and checksum; per-edge contents are consumed later by Task 18.
- Fails before tensor construction with structured `ContractError` on:
  - `MODEL_BATCH_ARTIFACT_MISSING` / `_UNREADABLE` / `_CHECKSUM_MISMATCH`
  - `MODEL_BATCH_ARTIFACT_ROLE_MISSING`
  - `MODEL_BATCH_CONTRACT_VERSION_UNSUPPORTED`
  - `MODEL_BATCH_REQUIRED_STATE_UNAVAILABLE`
- Task 17 does not read the rule table; finalized records must already carry `metadata.chemical_state.status`. Missing `metadata.chemical_state` and explicit `unavailable` both fail with `MODEL_BATCH_REQUIRED_STATE_UNAVAILABLE`.
- Creates no artifacts on disk (no side effects). Output is deterministic across repeated runs with identical inputs.
- Does NOT check Data Release Gate, split eligibility, quality-tier filtering, or visual check status.
- Bond-type vocabulary discovered from `core_labels.bond_type` across records → stored in `BatchSpec.bond_type_vocabulary` with `"no_edge"` always at index 0.
- `inspect_batch --records <path> [--record-id <id>]` (CLI: `python -m covalent_design.model.inspect_batch`) prints deterministic JSON with `schema_version`, `contract_version`, `batch_spec`, `records` (list), `passed`, `errors`, `warnings`. Each per-record entry includes `record_id`, `line`, `error`/`error_code`, `provenance` (target_atom_identity, target_atom_index, target_atom_artifact_role, artifact_refs), `tensor_shapes` (all 9 shape fields + dtype/index_dtype/coordinate_frame), `denominators_expected` (all 10 fields), `batch_spec`, and `warnings`.
- `inspect_batch` shows error reason (not silent skip) when a record would fail construction.

**Verification:**

```bash
pytest tests/model/test_batch.py -q
python -m covalent_design.model.inspect_batch --records tests/fixtures/model/valid/records.jsonl --record-id REC-001
```

### Task 18: Implement Stepwise Candidate Builder

**Goal:** Rebuild covalent edge candidates at each denoising timestep from fixed target atom coordinates and current noisy/generated ligand coordinates.

**Files/modules:**

- `src/covalent_design/model/candidate_builder.py`
- `tests/model/test_stepwise_candidates.py`

**Dependencies:** Tasks 12, 17.

**Contracts:** `StepwiseCandidate`, `StepwiseCandidateSet`, `EdgeDenominators`, `ProteinAtomIdentity` — defined in `covalent_design.contracts.types`. See ADR 0035.

**Naming:** Stepwise candidates (dynamic, per-timestep) ≠ static edge candidates (Task 12 artifact, `"edge_candidates"` role). MUST use `StepwiseCandidate` / `StepwiseCandidateSet` naming — never unqualified `edge_candidates`.

**Public API:**

```python
def build_stepwise_candidates(
    *,
    protein_atoms: list[dict],
    ligand_atoms: list[dict],
    edge_candidates_artifact: dict,
    timestep_index: int,
    timestep_value: float,
    candidate_radius_angstrom: float = 4.0,
) -> StepwiseCandidateSet:
```

**Parameters:**

| Parameter | Type | Description |
| --- | --- | --- |
| `protein_atoms` | `list[dict]` | Fixed protein atom dicts. Must contain `"name"`, `"x"`, `"y"`, `"z"`. Shared resolution uses explicit `target_atom.atom_index` plus identity cross-check first; unique-name fallback exists only for legacy artifacts and ambiguous fallback fails. |
| `ligand_atoms` | `list[dict]` | Current-timestep noisy/generated ligand atom dicts. Must contain `"x"`, `"y"`, `"z"`. The `"index"` key is used when present; otherwise list position is the position-based fallback. |
| `edge_candidates_artifact` | `dict` | Task 12 static `edge_candidates.json` artifact. Positive label identity is read from `artifact["positive_edge"]` → `ligand_atom_index`, `target_atom`, `bond_type`. |
| `timestep_index` | `int` | Integer index of the current denoising timestep (passed through to `StepwiseCandidateSet.timestep_index`). |
| `timestep_value` | `float` | Current noise level t ∈ [0, 1] (passed through to `StepwiseCandidateSet.timestep_value`). |
| `candidate_radius_angstrom` | `float` | Radius in angstroms for natural-candidate inclusion. Ligand atoms with distance `< candidate_radius_angstrom` become natural candidates. Default 4.0. |

**Return:** `StepwiseCandidateSet` — immutable dataclass with:

| Field | Type | Description |
| --- | --- | --- |
| `timestep_index` | `int` | As passed by caller. |
| `timestep_value` | `float` | As passed by caller. |
| `candidates` | `tuple[StepwiseCandidate, ...]` | Sorted positive-first, then negatives by distance (ascending). |
| `positive_label_ligand_atom_index` | `int` | From `edge_candidates_artifact["positive_edge"]["ligand_atom_index"]`. |
| `positive_label_target_atom` | `ProteinAtomIdentity` | From `edge_candidates_artifact["positive_edge"]["target_atom"]`. |
| `positive_label_bond_type` | `str` | From `edge_candidates_artifact["positive_edge"]["bond_type"]`. |
| `denominators` | `EdgeDenominators` | Per-timestep counts (10 fields). |
| `empty_radius_window` | `bool` | `True` iff `natural_negative_count == 0`. |

**Acceptance criteria:**

- Builds candidates at each timestep using current `ligand_atoms` coordinates and `candidate_radius_angstrom` (default 4.0).
- Natural candidates use strict distance `< candidate_radius_angstrom` (not `<=`).
- Positive edge label (`ligand_atom_index`, `target_atom`, `bond_type`) read from Task 12 static `edge_candidates.json` — NOT from caller-supplied parameters.
- Target atom coordinates are fixed from `protein_atoms`; ligand coordinates come from the `ligand_atoms` argument every timestep.
- Positive edge force-included when noise moves it outside radius → `is_forced_positive=True`.
- Forced positives increment `EdgeDenominators.forced_positive_count` and are excluded from `bond_type_loss_denominator`, `geometry_loss_denominator`, and `message_passing_candidate_count`.
- `local_index` is a contiguous per-timestep index starting from 0; it restarts on every call and has NO cross-timestep meaning.
- `ligand_atom_index` is the stable cross-timestep identity used for force-inclusion checks and loss alignment.
- Reports `empty_radius_window=True` when zero natural negatives exist. This is a valid state, not a failure.
- The function is a pure in-memory computation; it creates no artifacts on disk.
- Deterministic: same inputs always produce identical output.
- `build_stepwise_candidate_batch(candidate_sets)` builds the deterministic padded dynamic view consumed by Task 20 and future Task 24 integration. It carries `candidate_counts`, `padded_shape`, and strict aggregated `denominators_observed`.
- Does NOT import RDKit or torch.
- Task 18 does **not** implement PMDM adapter, covalent heads, message passing, loss masks, final decode, training, inference, or evaluation.

**Verification:**

```bash
pytest tests/model/test_stepwise_candidates.py -q
```

### Task 19: Implement PMDM Adapter Skeleton

**Goal:** Provide the PMDM-compatible model boundary with explicit output key vocabulary, shape validation, and fake backbone smoke path. Task 20 fields are explicit smoke placeholders.

**Public API:**

```python
def forward_pmdm(
    *,
    batch: ModelBatch,
    config: ModelConfig,
    timestep: float = 0.5,
) -> ModelForwardOutput: ...

def validate_pmdm_outputs(
    pmdm_outputs: dict,
    *,
    batch: ModelBatch,
    config: ModelConfig,
) -> None: ...
```

**Files/modules:**

- `src/covalent_design/model/pmdm_adapter.py`
- `src/covalent_design/model/config.py`
- `tests/model/test_pmdm_adapter.py`

**Dependencies:** Task 17.

**Contracts:** `ModelConfig` frozen dataclass, `ModelForwardOutput.pmdm_outputs` key vocabulary — 9 keys (7 required, 2 optional), `SMOKE_PLACEHOLDER` sentinel. Defined in `interface-design.md` ModelConfig and PMDM Adapter Output Keys sections.

**Acceptance criteria (16 requirements):**

1. **Fake backbone smoke fixture:** produces valid PMDM outputs with correct shapes using pure Python nested lists and deterministic `random.Random(seed)` — no real PMDM, PocketFlow, torch, or RDKit import.
2. **Adapter accepts ModelBatch:** `forward_pmdm(*, batch=..., config=..., timestep=0.5)` accepts a `ModelBatch` instance constructed by Task 17 fixtures.
3. **Returns ModelForwardOutput:** output type is `ModelForwardOutput` with populated `pmdm_outputs` and `denominators_observed`.
4. **All 7 required keys present:** `ligand_atom_features`, `protein_atom_features`, `ligand_coords_denoised`, `position_loss`, `atom_type_loss`, `timestep`, `num_atom`.
5. **Optional keys disabled by default:** when `ligand_pair_feature_dim == 0` and `protein_ligand_pair_feature_dim == 0`, optional keys (`ligand_pair_features`, `protein_ligand_pair_features`) must be absent from `pmdm_outputs`.
6. **Optional keys enabled by config:** when `ligand_pair_feature_dim > 0` and `protein_ligand_pair_feature_dim > 0`, optional keys must be present with correct shapes.
7. **Required shapes:**
   - `ligand_atom_features` (B, N_lig, D_lig)
   - `protein_atom_features` (B, N_prot, D_prot)
   - `ligand_coords_denoised` (B, N_lig, 3)
   - `position_loss` scalar, `atom_type_loss` scalar
   - `timestep` scalar float, `num_atom` (B,)
8. **Missing required key raises ContractError:** `validate_pmdm_outputs` raises `ContractError(code="PMDM_MISSING_REQUIRED_KEY", owner="model")` when a required key is absent.
9. **Wrong shape raises ContractError:** `validate_pmdm_outputs` raises `ContractError(code="PMDM_SHAPE_MISMATCH", owner="model")` when a value has unexpected shape.
10. **Deterministic output with same seed:** two `forward_pmdm` calls with identical `batch`, `config`, and `timestep` produce byte-identical `pmdm_outputs`.
11. **Different seed changes output:** different seeds produce different non-scalar outputs.
12. **ModelConfig carries contract_version and rule_table_hash:** `ModelConfig` is a frozen dataclass with `contract_version` (default `"1.0.0"`) and `rule_table_hash` (default `""`).
13. **ModelConfig.to_dict() is deterministic:** repeated calls produce identical output; two instances with identical fields produce identical dicts; output is JSON-serializable.
14. **No PMDM/PocketFlow/torch/RDKit imports:** importing `pmdm_adapter` or `config` must not pull in PMDM, PocketFlow, torch, or RDKit.
15. **No Task 20 modules imported:** importing `pmdm_adapter` or `config` must not pull in `covalent_heads`, `edge_message_passing`, `final_decode`, `validity_gate`, or other Task 20+ modules.
16. **No artifacts generated:** `forward_pmdm`, `validate_pmdm_outputs`, and `ModelConfig` construction create no files on disk.

**Task 20 fields are explicit smoke placeholders:**

`ModelForwardOutput.edge_logits`, `.bond_type_logits`, `.family_logits`, and `.edge_prob_message_weights` are `SMOKE_PLACEHOLDER` sentinels — not real logits, not detached sigmoid message weights, not covalent heads, not message passing. Task 19 does NOT implement covalent heads, message passing, real logits, or detached sigmoid message weights.

`message_weight_source` is set to `"detached_edge_probability"` to satisfy the public anti-leakage guard in `ModelForwardOutput.__post_init__`. Task 19 does NOT prove Task 20 message-weight provenance.

`ModelForwardOutput.__post_init__` validates:
- `edge_prob_message_weights.requires_grad == False` (rejects trainable tensors)
- `message_weight_source in ALLOWED_MESSAGE_WEIGHT_SOURCES` (rejects label, ground_truth, target_edge, and unknown sources)

**Shape validation coverage:**

`validate_pmdm_outputs` raises `ContractError` on:
- `PMDM_MISSING_REQUIRED_KEY` — required key absent
- `PMDM_UNKNOWN_KEY` — key not in the 9-key vocabulary
- `PMDM_SHAPE_MISMATCH` — wrong shape for a required or optional key
- `PMDM_MISSING_OPTIONAL_KEY` — optional key absent when config enables it
- `PMDM_UNEXPECTED_OPTIONAL_KEY` — optional key present when config disables it

**No training/inference/evaluation artifacts:** `forward_pmdm`, `validate_pmdm_outputs`, and `ModelConfig` construction create no model, training, inference, or evaluation artifacts on disk.

**Verification:**

```bash
pytest tests/model/test_pmdm_adapter.py -q
```

### Task 20: Implement Covalent Heads And Message-Weight Interface

**Goal:** Produce edge logits, bond-type logits, family logits, and detached message weights. Enforce anti-leakage guard at construction time and at the message-passing boundary.

**Files/modules:**

- `src/covalent_design/model/covalent_heads.py`
- `src/covalent_design/model/edge_message_passing.py`
- `tests/model/test_covalent_heads.py`

**Dependencies:** Tasks 18, 19.

**Contracts:** `ModelForwardOutput` (edge_logits, bond_type_logits, family_logits, edge_prob_message_weights, message_weight_source). See ADR 0036.

**Public API:**

```python
def forward_covalent(
    *,
    pmdm_output: ModelForwardOutput,
    batch: ModelBatch,
    config: ModelConfig,
    num_families: int | None = None,
    stepwise_candidate_batch: StepwiseCandidateBatch | None = None,
) -> ModelForwardOutput:
```

Consumes a Task 19 `ModelForwardOutput` (which carries `SMOKE_PLACEHOLDER` sentinels in its covalent fields), a `ModelBatch`, and an optional Task 18 `StepwiseCandidateBatch`. Returns a new `ModelForwardOutput` with real pure-Python tensor-like objects (`_CovalentTensor`) replacing the smoke placeholders. Dynamic padded candidate shape is authoritative when supplied; the static fallback remains Task 19 smoke compatibility only.

Task 20 does **not** wrap or reimplement `forward_pmdm()`. It is a separate composition step: `forward_pmdm()` produces the PMDM backbone output with smoke placeholders; `forward_covalent()` consumes that output to fill in the covalent head logits and detached message weights.

```python
def apply_edge_message_weights(
    *,
    message_weights: object,
    source: str,
) -> object:
```

Validates the Task 20 message-weight boundary. Accepts only `message_weight_source = "detached_edge_probability"` with detached (`requires_grad == False`) prediction weights. Rejects label, ground-truth, target-edge, unknown, and trainable sources. This function is a no-op passthrough after validation; final decode and loss behavior remain later-task scope.

**Acceptance criteria:**

- `forward_covalent` consumes Task 19 `ModelForwardOutput` (with smoke placeholders) plus `ModelBatch`, `ModelConfig`, and optional Task 18 `StepwiseCandidateBatch`, and returns a new `ModelForwardOutput` with real logits. Task 24 passes the dynamic batch.
- Forward output includes `edge_logits` (B, N_candidates), `bond_type_logits` (B, N_candidates, N_bond_types), `family_logits` (B, N_families), `edge_prob_message_weights` (detached, B, N_candidates), `message_weight_source = "detached_edge_probability"`, `denominators_observed`.
- v1 **includes** family auxiliary head; `family_logits` is a required field, `family_aux_loss` is a required loss component.
- `N_bond_types` read from `BatchSpec.bond_type_vocabulary`; `N_families` auto-detected from `batch.records` family distribution when `num_families=None`.
- `edge_prob_message_weights` is `edge_logits.sigmoid().detach()`.
- `ModelForwardOutput.__post_init__` validates `not edge_prob_message_weights.requires_grad`.
- `ModelForwardOutput.__post_init__` validates `message_weight_source == "detached_edge_probability"`; `label`, `ground_truth`, `target_edge`, empty, and unknown sources fail even when `requires_grad == False`.
- `apply_edge_message_weights` is a Task 20 boundary guard (not Task 21 final decode or Task 24 loss). It rejects forbidden sources (`"label"`, `"ground_truth"`, `"target_edge"`) and unknown sources with `ValueError`. It also rejects trainable weights (`requires_grad == True`).
- Public API guard: tensor-like message weights with `requires_grad=True` trigger `ValueError`.
- Provenance/test guard: Task 20 tests must prove `edge_prob_message_weights` comes from the detached model prediction path, not label or ground-truth tensors. `requires_grad=False` alone is not a complete label-leakage proof; source provenance is required.
- Test `test_message_weights_are_detached` verifies `requires_grad == False`.
- Negative test: `requires_grad=True` tensor → `ValueError`.
- Negative test: `message_weight_source` in (`label`, `ground_truth`, `target_edge`) → `ValueError`, even with `requires_grad == False`.
- Negative test: unknown/empty `message_weight_source` → `ValueError`.

**Verification:**

```bash
pytest tests/model/test_covalent_heads.py -q
```

### Task 21: Implement Final Decode And Validity Gate

**Goal:** Select the highest-scoring gate-passing candidate or emit an invalid decode result with full failure diagnostics. Gate checks execute in defined priority order.

**Files/modules:**

- `src/covalent_design/model/final_decode.py`
- `src/covalent_design/model/validity_gate.py`
- `tests/model/test_final_decode.py`

**Dependencies:** Tasks 8, 20.

**Contracts:** Gate execution order (9 checks, stored in `_SPEC_GATE_ORDER`). `REQUIRED_GATE_STATE_UNAVAILABLE` is a global blocking condition. `FinalDecodeResult` with 6 fields including `selected_score`. See `interface-design.md` Failure Reason Priority.

**Public API:**

```python
# ValidityGate protocol (abstract, in validity_gate.py)
class ValidityGate(abc.ABC):
    @abc.abstractmethod
    def evaluate(
        self,
        candidate_index: int,
        candidate: dict,
        state: Any,
    ) -> tuple[EdgeValidityCheck, ...]: ...

# Final decode (in final_decode.py)
FinalLigandState = Dict[str, Any]  # dict with "candidates" key

def decode_final_edge(
    final_state: FinalLigandState,
    gate: Any,  # protocol: .evaluate(int, dict, Any) -> tuple[EdgeValidityCheck, ...]
) -> FinalDecodeResult: ...
```

**Constant: `_SPEC_GATE_ORDER`** (tuple of 9 strings, in gate evaluation order):
`target_atom`, `ligand_atom_class`, `bond_type`, `single_edge_representability`, `warhead_smarts`, `forbidden_smarts`, `valence`, `protonation`, `geometry`.

**Constant: `_REQUIRED_GATE_STATE_UNAVAILABLE = "REQUIRED_GATE_STATE_UNAVAILABLE"`**

**Acceptance criteria:**

- Sorts candidates by score descending with deterministic tie-breaking (original list index).
- Iterates in order: first candidate passing all applicable gate checks (`pass` or `not_applicable`) -> selected; continues otherwise.
- Top-1 fail + rank-2 pass → **valid** sample; `secondary_failure_reasons` preserves deduplicated first-failure codes from each skipped higher-scoring candidate.
- All-candidates-fail → `generation_validity_status = "invalid"`, `primary_failure_reason` set to first failure of highest-scoring candidate.
- Zero candidates → `"invalid"` with `primary_failure_reason = "NO_COVALENT_EDGE_PREDICTED"`.
- `REQUIRED_GATE_STATE_UNAVAILABLE` is a **global blocking condition**: if any evaluated candidate has a `not_evaluable` check, no candidate can be selected. The blocking failure code is `"REQUIRED_GATE_STATE_UNAVAILABLE:{check_name}"`.
- `primary_failure_reason` priority chain (all-fail): blocking required-state failure > best candidate first failure > `"NO_COVALENT_EDGE_PREDICTED"`.
- `FinalDecodeResult` has 6 fields: `generation_validity_status`, `selected_edge`, `primary_failure_reason`, `secondary_failure_reasons`, `edge_validity_checks`, `selected_score`.
- `edge_validity_checks` includes one `EdgeValidityCheck` per check per evaluated candidate (passed and failed).
- Never returns a forced edge when all candidates fail (`selected_edge` is `None` for invalid).
- `primary_failure_reason` is `None` for valid results; non-`None` for invalid.
- Deterministic: same inputs always produce identical output. Does not mutate input state.

**Verification:**

```bash
pytest tests/model/test_final_decode.py -q
```

### Task 22: Implement Training Dataset And Batch Loader

**Goal:** Filter accepted records into training splits based on policy, split assignment, and visual/quality gates.

**Files/modules:**

- `src/covalent_design/training/dataset.py`
- `src/covalent_design/training/batch.py`
- `tests/training/test_dataset.py`

**Dependencies:** Tasks 14, 17.

**Contracts:** `TrainingDatasetIndex`, `TrainingRecordEntry`, `ExclusionSummary` — defined in `covalent_design.contracts.types`.

**Exclusion priority chain (first matching reason wins):**

1. assigned split is another core split (`train`/`val`/`test`) and differs from `split_name` → `not_in_this_split`
2. assigned split is `"excluded"` → `hard_excluded_by_split`
3. `visual_check_status != "pass"` and `policy.exclude_visual_blocked=True` → `excluded_visual_blocked`
4. `quality_tier` outside accepted set → `excluded_quality_tier`
5. `policy.first_core_only=True` and record is multi-linkage → `excluded_multi_linkage`
6. `policy.exclude_q2=True` and `quality_tier == "Q2"` → `excluded_q2`
Records without a split assignment are excluded with `missing_split_assignment`
before policy filtering.

**Default `TrainingDataPolicy`** (implemented in `covalent_design.training.dataset`, exported from `covalent_design.training`):

- `first_core_only=True`
- `exclude_visual_blocked=True`
- `exclude_q2=False`
- `accepted_quality_tiers=("Q0", "Q1", "Q2")`

**Acceptance criteria:**

- `prepare_dataset(records_path, split_index_path, split_name, policy=None)` returns `ContractEnvelope[TrainingDatasetIndex]`.
- Builds exactly one split-specific dataset per call. Valid `split_name` values: `"train"`, `"val"`, `"test"`.
- Default `TrainingDataPolicy`: Q0/Q1/Q2 accepted, Q2 kept by default (excluded only when `exclude_q2=True`), visual-blocked excluded by default (`exclude_visual_blocked=True`), multi-linkage excluded when `first_core_only=True`.
- Q2 records: included by default; excluded only when `policy.exclude_q2=True`. Flag preserved in `TrainingRecordEntry.quality_tier`.
- Visual statuses other than `"pass"` are excluded when `exclude_visual_blocked=True`.
- `ExclusionSummary` equations: `total_accepted == len(records.jsonl rows)`, `records_in_split == len(TrainingDatasetIndex.records)`, `excluded_by_policy == total_accepted - records_in_split`, `sum(exclusion_reasons.values()) == excluded_by_policy`.
- `TrainingRecordEntry` preserves: `record_id`, `residue_reaction_family`, `quality_tier`, `visual_check_status`, `fallback_reason`, `manual_review_status`, and artifact refs by role.
- `TrainingDatasetIndex` is split-specific (one call per train/val/test).
- `load_training_batch(dataset, batch_id, *, batch_spec=None)` implements deterministic singleton batches named `batch-<zero-based-index>` over sorted dataset entries. It extracts one finalized row into a temporary same-directory JSONL file, delegates to Task 17 `make_model_batch()`, and removes the temporary file before return.
- Task 22 does **not** compute Task 23 masks, Task 23 denominators, Task 24 losses, run model forward, run a training loop, or generate model/training/inference/evaluation artifacts.

**Verification:**

```bash
pytest tests/training/test_dataset.py -q
```

### Task 23: Implement Loss Masks And Denominator Reports

**Goal:** Compute per-timestep loss eligibility masks with explicit condition decomposition.

**Files/modules:**

- `src/covalent_design/training/masks.py`
- `src/covalent_design/training/denominators.py`
- `tests/training/test_masks_denominators.py`

**Dependencies:** Tasks 18, 22.

**Contracts:** `MaskAudit` (15 fields), `DenominatorsStratum`, `DenominatorStratumEntry` (package-specific). Pending SMARTS + pending geometry interaction rules. Forced-positive loss participation table. See `interface-design.md`.

**Public API:**

```python
from covalent_design.training.masks import compute_mask_audit
from covalent_design.training.denominators import (
    DenominatorStratumEntry,
    aggregate_denominator_strata,
    build_edge_denominators,
    classify_timestep_bucket,
)
```

```python
compute_mask_audit(
    candidate_set: StepwiseCandidateSet,
    *,
    pending_smarts: bool = False,
    pending_geometry: bool = False,
    missing_required_chemical_state: bool = False,
    quality_tier: str = "Q1",
    exclude_q2: bool = False,
) -> MaskAudit
```

`resolve_mask_flags(...) -> NormalizedMaskFlags` owns the explicit normalized
rule/policy booleans passed into Task 23. `compute_mask_audit()` remains a
projection and does not resolve rule-table rows.

```python
build_edge_denominators(mask_audit: MaskAudit) -> EdgeDenominators
classify_timestep_bucket(timestep_value: float) -> str
aggregate_denominator_strata(
    entries: Iterable[DenominatorStratumEntry],
) -> tuple[DenominatorsStratum, ...]
```

`DenominatorStratumEntry` is a package-specific frozen dataclass with fields:
`residue_reaction_family: str`, `timestep_value: float`, `mask_audit: MaskAudit`.

**Acceptance criteria:**

**Base counts:**
- `TC = candidate_count`; `NP = natural_positive_count`; `FP = forced_positive_count`; `NN = natural_negative_count`.
- `TC == NP + FP + NN` (conservation invariant; raises `ValueError` on violation).
- `zero_negative_count = 1` iff `NN == 0` (valid state, not an error — `empty_radius_window=True` is valid).

**Mask reason counts** (independent, may overlap):
- `masked_by_pending_smarts = NP` when `pending_smarts=True`, else 0. Masks bond type target only.
- `masked_by_pending_geometry = NP` when `pending_geometry=True`, else 0. Masks geometry target only.
- `masked_by_missing_chemical_state = NP` when `missing_required_chemical_state=True`, else 0. Masks geometry targets for NP.
- `masked_by_q2_exclusion = TC` when `exclude_q2=True and quality_tier == "Q2"`, else 0. Masks all TC.
- `masked_by_forced_positive_exclusion = FP` always. Counts forced-positive exclusion.

**Eligible counts when Q2 is not excluded:**
- `edge_loss_eligible_count = TC`
- `bond_type_loss_eligible_count = 0` if `pending_smarts` else `NP`
- `geometry_loss_eligible_count = 0` if `pending_geometry or missing_required_chemical_state` else `NP`
- `message_passing_candidate_count = NP + NN`
- `gate_evaluated_count = TC`

**When Q2 is excluded** (`exclude_q2=True` and `quality_tier == "Q2"`): all five eligible counts are 0.

**Participation:**
- Natural negatives: edge existence and message passing only; never true bond or geometry targets.
- Forced positives: edge existence and gate evaluation only.
- Pending SMARTS: masks bond target only.
- Pending geometry: masks geometry target only; `missing_required_chemical_state` also masks geometry targets.
- `empty_radius_window=True` is valid, not an error.

**Denominator projection** (`build_edge_denominators`):
- `candidate_count = TC`; `natural_candidate_count = NP + NN`; `forced_positive_count = FP`.
- `eligible_edge_count = edge_loss_eligible_count`; `masked_candidate_count = TC - edge_loss_eligible_count`.
- Loss/message/gate denominator fields copy the matching eligible counts.
- Calls `EdgeDenominators.validate()` before returning.

**Timestep buckets** (`classify_timestep_bucket`):
- `early`: t ∈ [0.8, 1.0]; `mid`: t ∈ [0.3, 0.8); `late`: t ∈ [0.0, 0.3).
- Out-of-range (t < 0.0 or t > 1.0) and non-finite values raise `ValueError`.

**Strata aggregation** (`aggregate_denominator_strata`):
- Group `DenominatorStratumEntry` entries by `(residue_reaction_family, timestep_bucket)`.
- Sum all 15 `MaskAudit` fields element-wise within each group.
- Derive each group's 10-field `EdgeDenominators` via `build_edge_denominators`.
- Deterministic sort: family alphabetical ascending, then `"early"`, `"mid"`, `"late"`.

**Scope boundaries:**
- Does NOT compute numeric losses, run model forward, or run a training loop.
- Does NOT resolve rule-table rows — boolean flags must be resolved upstream.
- Does NOT introduce RDKit or torch.
- Does NOT generate checkpoints, run manifests, or training/inference/evaluation artifacts.
- Does NOT change `LossReport` serialization.

**Verification:**

```bash
pytest tests/training/test_masks_denominators.py -q
```

### Task 24: Implement Loss Report And Smoke Training Loop

**Goal:** Run one fixture-based training step with fake backbone, emit structured `LossReport`.

**Files/modules:**

- `src/covalent_design/training/losses.py`
- `src/covalent_design/training/train_loop.py`
- `src/covalent_design/training/train.py`
- `src/covalent_design/model/forward_smoke.py`
- `tests/training/test_train_smoke.py`
- `tests/model/test_forward_smoke.py`
- `configs/covalent_train_smoke.yml`
- `configs/covalent_model_smoke.yml`

**Dependencies:** Tasks 20, 22, 23.

**Contracts:** `LossReport` (with `.to_dict()`), `LossWeights` (six deterministic
default weights of `1.0`), smoke config schema `covalent_train_smoke.yml`.

`compute_losses()` signature (implemented):

```python
def compute_losses(
    output: ModelForwardOutput,
    *,
    model_batch: ModelBatch,
    stepwise_candidate_batch: StepwiseCandidateBatch,
    mask_flags: tuple[NormalizedMaskFlags, ...],
    weights: LossWeights = LossWeights(),
) -> LossReport:
```

Keyword-only after `output`. Uses pure-Python pseudo BCE/CE losses
(`_bce_with_logits`, `_cross_entropy`). `covalent_geometry_loss` is wired as
an explicit `0.0` sentinel — not a real geometry regression implementation.
PMDM losses are read from `output.pmdm_outputs["position_loss"]` and
`output.pmdm_outputs["atom_type_loss"]` as produced by the fake backbone.

**Smoke config** (`configs/covalent_train_smoke.yml`):

```yaml
records_path: tests/fixtures/training/smoke/smoke_records.jsonl
split_index_path: tests/fixtures/training/smoke/smoke_split_index.json
split_name: train
output_dir: outputs/task24-smoke
steps: 1
batch_size: 4
timestep: 0.5

model_config:
  seed: 7
  fake_backbone: true
  ligand_feature_dim: 4
  protein_feature_dim: 4
  ligand_pair_feature_dim: 0
  protein_ligand_pair_feature_dim: 0
  hidden_dim: 256
  candidate_radius_angstrom: 4.0

mask_flags:
  pending_smarts: false
  pending_geometry: false
  missing_required_chemical_state: false
  quality_tier: Q1
  exclude_q2: false

loss_weights:
  pmdm_position_loss: 1.0
  pmdm_atom_loss: 1.0
  covalent_edge_loss: 1.0
  covalent_bond_type_loss: 1.0
  covalent_geometry_loss: 1.0
  family_aux_loss: 1.0
```

**Forward smoke config** (`configs/covalent_model_smoke.yml`):

```yaml
records_path: tests/fixtures/training/smoke/smoke_records.jsonl
timestep: 0.5
model_config:
  seed: 7
  fake_backbone: true
  ligand_feature_dim: 4
  protein_feature_dim: 4
  ligand_pair_feature_dim: 0
  protein_ligand_pair_feature_dim: 0
  hidden_dim: 256
  candidate_radius_angstrom: 4.0
```

**Smoke training loop** (`run_smoke_train` in `train_loop.py`):

Loads four deterministic singleton microbatches (`batch_size=4`, one record
each via Task 22 `load_training_batch`). Per microbatch: runs
`forward_pmdm` + `forward_covalent`, builds dynamic stepwise candidates,
computes losses via `compute_losses()`. Aggregates microbatch `LossReport`s
into one step-level report via `_aggregate_microbatch_losses()` (averages
components, sums denominators/mask audits, re-aggregates strata). Writes
exactly one `train_metrics.jsonl` row.

**Acceptance criteria:**

- `LossReport.components` includes all 6 required keys: `pmdm_position_loss`, `pmdm_atom_loss`, `covalent_edge_loss`, `covalent_bond_type_loss`, `covalent_geometry_loss`, `family_aux_loss` (all v1-required).
- `LossReport` carries `EdgeDenominators` (10 fields), `MaskAudit` (15 fields), and `strata` (per-family/timestep with `mask_audit` per stratum).
- `.to_dict()` produces JSON-compatible dict matching `train_metrics.jsonl` schema.
- Smoke step completes on CPU with fake backbone (no PMDM, no GPU, no torch, no RDKit).
- Verification checks denominator field presence and non-negativity — NOT loss convergence.
- `covalent_geometry_loss` is explicit `0.0` sentinel, not a real geometry regression.
- No optimizer convergence, checkpoint, run manifest (Task 25+), torch, RDKit, real PMDM, or PocketFlow.

**Verification:**

```bash
pytest tests/training/test_train_smoke.py -q
pytest tests/model/test_forward_smoke.py -q
python -m covalent_design.model.forward_smoke --config configs/covalent_model_smoke.yml
python -m covalent_design.training.train --config configs/covalent_train_smoke.yml
```

### Task 25: Implement Training Run Manifest And Checkpoint Metadata

**Goal:** Preserve cryptographic provenance for every training run and checkpoint.

**Files/modules:**

- `src/covalent_design/training/checkpoints.py`
- `src/covalent_design/training/reports.py`
- `tests/training/test_run_manifest.py`

**Dependencies:** Task 24.

**Contracts:** `TrainingRunManifest`, `CheckpointMetadata` frozen dataclass, checkpoint manifest YAML schema, hash computation rules (canonical JSON → SHA-256). Cross-version compatibility: exact → no warning; major → hard reject; minor → warn + load; patch → silent.

**Acceptance criteria:**

- **Reports (`reports.py`):**
  - `canonical_json(value) -> str`: deterministic sorted-key JSON, no trailing whitespace.
  - `sha256_bytes(value: bytes) -> str`: returns ``sha256:<64 lowercase hex>``.
  - `sha256_file(path) -> str`: SHA-256 of exact file bytes.
  - `hash_resolved_config(resolved_config) -> str`: resolved config → canonical JSON (sorted keys) → SHA-256.
  - `hash_rule_table(path) -> str`: parse YAML → canonical JSON (sorted keys) → SHA-256.
  - `build_training_input_hashes(...) -> dict`: keyword-only. Required keys: ``records_jsonl``, ``split_index``, ``rule_table``, ``quality_report``, ``visual_check_index``. Optional key: ``release_gate`` (present only when ``release_gate_path`` is given). ``records_jsonl`` and ``split_index`` use exact-byte SHA-256; ``rule_table`` uses parsed-YAML → canonical-JSON → SHA-256; ``quality_report``, ``visual_check_index``, and ``release_gate`` use exact-byte SHA-256.
  - `build_training_run_manifest(...) -> TrainingRunManifest`: keyword-only. ``training_config_resolved_hash`` is stored separately from ``input_hashes``. Defaults: ``train_completed=False``, ``epochs_completed=0``, ``steps_completed=0``, ``crash_recovery=None``.
  - `training_run_manifest_to_dict(manifest) -> dict`: JSON-compatible dict with all 14 required keys.
- **Checkpoints (`checkpoints.py`):**
  - `CheckpointMetadata`: frozen dataclass with 11 fields (schema_version, contract_version, role, run_id, step, model_contract_version, rule_table_version, input_hashes, model_weights_uri, optimizer_state_uri, bond_type_vocabulary).
  - `checkpoint_metadata_to_dict(metadata) -> dict`: JSON-compatible dict; ``bond_type_vocabulary`` serialised as a list.
  - `write_checkpoint_metadata(path, metadata) -> Path`: validates metadata, writes deterministic YAML using project-owned pure-Python subset (sorted keys, no PyYAML dependency for writing). Byte-deterministic across repeated calls.
  - `read_checkpoint_metadata(path, *, expected_contract_version=CONTRACT_VERSION) -> tuple[CheckpointMetadata, tuple[str, ...]]`: returns (metadata, warnings). Exact version match → no warnings; major mismatch → ContractError (hard reject); minor mismatch → loads with warning; patch difference → silent.
  - `validate_checkpoint_metadata(metadata, *, expected_contract_version=CONTRACT_VERSION) -> tuple[str, ...]`: empty tuple = valid; minor mismatch returns a warning; major mismatch raises `ContractError`. Checks schema_version, role, run_id, step, bond_type_vocabulary (non-empty, no duplicates, ``no_edge`` at index 0), all 6 required input_hashes keys in ``sha256:<64 lowercase hex>`` format; ``release_gate`` optional.
- **Cross-cutting:**
  - Every hash uses uniform ``sha256:<64 lowercase hex>`` format.
  - ``quality_report`` and ``visual_check_index`` are required exact-byte audit hashes; ``release_gate`` is an optional exact-byte audit hash.
  - Audit hashes bind provenance only; training metadata code does **not** re-run the Data Release Gate.
  - Checkpoint URI targets (``model_weights_uri``, ``optimizer_state_uri``) need not exist on disk during metadata validation.
  - ``bond_type_vocabulary[0]`` must be ``"no_edge"``.
  - Task 25 writes metadata only — no real ``.pt`` weight contents, optimizer state, resume logic, torch, RDKit, PMDM, PocketFlow, or Task 26 inference.
  - Task 24 smoke training remains unchanged; Task 25 builders are explicit public APIs and do **not** silently add artifact writes to ``run_smoke_train()``.
  - Pure Python only; no torch, RDKit, PMDM, or PocketFlow imports.

**Verification:**

```bash
pytest tests/training/test_run_manifest.py -q
```

### Checkpoint B: Model And Training Gate

**Dependencies:** Tasks 17-25.

**Proof of completion:**
- `inspect_batch` outputs deterministic JSON for fixture records
- `forward_smoke` logs PMDM + covalent output shapes
- Smoke training `train_metrics.jsonl` contains all 6 loss components, `EdgeDenominators` (10 fields), `MaskAudit` (15 fields), and per-family/timestep strata
- Fixture coverage: natural positive, forced positive, zero negatives, pending geometry, pending SMARTS, missing chemical state, Q2, empty_radius_window
- `python -m compileall -q scripts src` passes

## Inference And Evaluation Tasks

### Task 26: Implement Request Schema And Validation

**Goal:** Validate `ReactiveSiteGenerationRequest` inputs before any sampling. YAML is authoritative format; JSON accepted. Altloc policy: explicit override > highest occupancy > `A`; single-conformer resolves to `None`. Structure reader is pure Python (PDB/mmCIF atom-level boundary only; no RDKit/torch).

**Files/modules:**

- `src/covalent_design/inference/request_schema.py` — `ReactiveSiteGenerationRequest`, `ValidatedRequest`, `ProteinAtomLocator`, `LigandSizeControl`, `ProteinChemicalStateRequest`
- `src/covalent_design/inference/request_validation.py` — `load_request_file`, `validate_request`, `validate_request_file`, `normalized_request_yaml`, `write_normalized_request`
- `src/covalent_design/inference/validate_request.py` — CLI entry point
- `src/covalent_design/io/structure_reader.py` — pure-Python PDB/mmCIF `AtomRecord` parser; preserves `chain_id`, `residue_number`, `residue_name`, `atom_name`, `altloc`, `occupancy`, `insertion_code`, `structure_model`, `asym_id`, `atom_serial`
- `tests/inference/test_request_validation.py`

**Dependencies:** Tasks 1, 8.

**Public types:**
- `ReactiveSiteGenerationRequest`: `request_id`, `protein_structure_uri`, `protein_structure_format`, `target_atom_identity_request` (`ProteinAtomLocator`), `residue_reaction_family`, `sample_count`, `size_control` (`LigandSizeControl | None`), `protein_chemical_state_request` (`ProteinChemicalStateRequest | None`), `target_altloc` (`str | None`)
- `ValidatedRequest`: `request`, `resolved_target_atom_identity` (`ProteinAtomIdentity`), `resolved_target_altloc` (`str | None`), `rule_table_version` (`int`)
- `LigandSizeControl`: `num_ligand_heavy_atoms` (fixed), `min_ligand_heavy_atoms`/`max_ligand_heavy_atoms` (range), or all `None` (absent)

**Acceptance criteria:**

- Request file format: YAML (`.yml`/`.yaml`) authoritative, JSON (`.json`) accepted. Auto-detected by extension. Unknown extension and malformed content both → `REQUEST_STRUCTURE_UNREADABLE`.
- All 13 `REQUEST_*` error codes covered by fixtures. No 14th code.
- Ligand size control: fixed (`num_ligand_heavy_atoms`), range (`min_`/`max_`), or absent. Conflicting forms → `REQUEST_LIGAND_SIZE_CONFLICT`. Non-integer values → deterministic error codes.
- Missing required chemical state → `REQUEST_REQUIRED_CHEMICAL_STATE_UNAVAILABLE`.
- `target_altloc` optional field; explicit override wins over occupancy; when absent → select highest occupancy or `A`; single-conformer → `None`.
- Resolved altloc recorded in `ValidatedRequest.resolved_target_altloc`.
- `ValidatedRequest` carries `rule_table_version` from the loaded rule table.
- `write_normalized_request()` produces deterministic UTF-8 YAML; callable by Task 27, not an implicit side effect of Task 26 validation.
- Task 26 does not write generation, checkpoint, sampling, or normalized artifacts.
- Structure reader is pure Python; no RDKit, no torch.
- CLI: `python -m covalent_design.inference.validate_request --request <path> [--rules <path>] [--error-out <path>]`. Default rule table: `data/rules/reaction_family_rule_table.yml`.  On `ContractError`, `--error-out <path>` writes a `cli_error` JSON file with role `"cli_error"`.
- Request validation failure is a request contract error (`ContractError(owner="request")`), not an invalid generated sample.
- Task 27 is implemented.

**Verification:**

```bash
pytest tests/inference/test_request_validation.py -q
python -m covalent_design.inference.validate_request --request request.yml
python -m covalent_design.inference.validate_request --request request.yml --rules data/rules/reaction_family_rule_table.yml
```

### Task 27: Implement Generation Run Manifest And Sampling Failure Accounting

**Goal:** Return `GenerationRunManifest`, separate sampling system failures from results, count at sample_id granularity. Inject all heavy boundaries.

**Files/modules:**

- `src/covalent_design/inference/run_manifest.py` (implemented)
- `src/covalent_design/inference/sampler.py` (implemented)
- `tests/inference/test_sampling_failures.py`

**Dependencies:** Task 26.

**Contracts:** `GenerationRunManifest`, `SamplingSystemFailure`, `SamplingPolicy` — defined in `covalent_design.contracts.types`. Retry policy: sample_id granularity, retries do not change denominator.

**Public API:**

```python
@dataclass(frozen=True)
class SamplingPolicy:
    max_retries: int
    retry_on_categories: tuple[str, ...]

def generate(
    request: ValidatedRequest,
    policy: SamplingPolicy,
    *,
    output_dir: Path,
    job_id: str,
    sampler,
    result_sink,
    checkpoint_ref: ArtifactRef | None = None,
    checkpoint_loader = None,
    clock = None,
    traceback_normalizer = None,
) -> ContractEnvelope[GenerationRunManifest]:
```

**Acceptance criteria:**

- `generate()` returns `ContractEnvelope[GenerationRunManifest]`, not `list[CovalentGenerationResult]`.
- `SamplingPolicy` requires both fields explicitly: `max_retries: int` and `retry_on_categories: tuple[str, ...]`. Retry defaults remain deliberately unfrozen.
- `SamplingSystemFailure` is a frozen 9-field dataclass: `request_id`, `sample_id`, `failure_category`, `failure_timestamp`, `traceback_hash`, `log_uri`, `retry_count`, `resource_snapshot`, `message`.
- Failure categories are exactly: `crash`, `oom`, `timeout`, `retry_exhausted`, `checkpoint_load_failed`, `sampler_invariant_violation`.
- `retry_exhausted` is an emitted terminal sentinel and cannot be configured as a retry trigger.
- `GenerationRunManifest` includes: `schema_version`, `contract_version`, `role`, `job_id`, `request_id`, `checkpoint_ref` (`ArtifactRef | None`), `accepted_request_sample_count`, `attempted_sample_count`, `sampling_system_failure_count`, `result_count`, `artifacts` (keys: `request`, `results`, `sampling_system_failures`).
- Artifact refs use relative URIs and exact-byte SHA-256 with `format`, `schema_version`, `role`, and `bytes` fields.
- `checkpoint_ref` uses `ArtifactRef | None` — no separate `CheckpointRef` type.
- `accepted_request_sample_count = attempted_sample_count + sampling_system_failure_count`.
- `attempted_sample_count` is per sample_id, not per attempt. Retries are internal and do not change the denominator.
- `sampling_system_failure_count` is deduplicated by sample_id (only fully-failed samples).
- Every intermediate failure attempt row remains in `sampling_system_failures.jsonl` (with `retry_count` = 0, 1, ...). A fully exhausted sample adds an extra `retry_exhausted` terminal sentinel row, but `sampling_system_failure_count` counts that failed sample once.
- `checkpoint_load_failed` rows are emitted per accepted sample id.
- `result_sink` is wired to `ResultWriter.write()` through `generate(result_sink=writer.write)`.
- `sampler`, `checkpoint_loader`, `clock`, and `traceback_normalizer` are injectable boundaries. No real PMDM, PocketFlow, torch, RDKit, Task 29 export, or Task 30 evaluation implementation.
- Generation writes `request.normalized.yml` before checkpoint loading and creates this sibling layout: `request.normalized.yml`, `run_manifest.yml`, `results.jsonl`, `sampling_system_failures.jsonl`, `logs/`.
- No standalone CLI for Task 27. `generate()` is a Python API called from orchestration code.

**Verification:**

```bash
pytest tests/inference/test_sampling_failures.py -q
```

### Task 28: Implement Generation Result Writer (implemented)

**Goal:** Write one complete `CovalentGenerationResult` row per attempted sample with lifecycle validation. Pure Python API — no independent CLI.

**Files/modules:**

- `src/covalent_design/inference/result_schema.py` (implemented)
- `src/covalent_design/inference/result_writer.py` (implemented)
- `tests/inference/test_result_writer.py`

**Dependencies:** Tasks 21, 27.

**Contracts:** Full `CovalentGenerationResult` (~22 fields) defined in `covalent_design.contracts.types`.

**Public API:**

```python
from covalent_design.inference.result_writer import ResultWriter

writer = ResultWriter()
row = writer.write(result)  # dict[str, object]
```

**Acceptance criteria:**

- `ResultWriter` is a stateless, reusable class importable from `covalent_design.inference.result_writer`.
- `write()` accepts a `CovalentGenerationResult` and returns `dict[str, object]`.
- Reuses `from covalent_design.contracts import validate_generation_result` for lifecycle validation.
- Contract-corrupt sampler output raises the first structured `ContractError` (with code, owner, message, location, and details) and is not silently converted to an invalid sample or sampling-system failure.
- Internally consistent invalid generated samples are retained as rows with diagnostics preserved.
- Writer rows contain every `CovalentGenerationResult` domain field as deterministic JSON-compatible values.
- Nested dataclasses become dictionaries, tuples become lists, and artifact mapping keys are stable.
- Writer rows intentionally exclude top-level `schema_version` and `contract_version`; Task 27 `write_jsonl()` injects them in `results.jsonl`.
- Task 27 integration is `generate(..., result_sink=writer.write)`.
- One result row per attempted sample.
- Valid samples: `generation_validity_status = "valid"`, ligand/edge/geometry/warhead fields populated.
- Invalid samples: `primary_failure_reason` set, `secondary_failure_reasons` with all observed failures, ligand files preserved if parseable.
- Lifecycle constraints enforced at write time (e.g., invalid → export = not_applicable).
- Request validation errors never create result rows.
- Result writer is called inside `generate()` loop; no standalone CLI.
- Does not implement Task 29 mmCIF writer/export, real docking, Task 30 evaluation, or heavy dependencies.

**Verification:**

```bash
pytest tests/inference/test_result_writer.py -q
```

### Task 29: Implement mmCIF-First Export Interface (implemented)

**Goal:** Export valid covalent complexes as mmCIF through the project-owned pure-Python writer and immutable export adapters.

**Files/modules:**

- `src/covalent_design/io/mmcif_writer.py` (implemented)
- `src/covalent_design/inference/complex_export.py` (implemented)
- `tests/inference/test_complex_export.py` (implemented)

**Dependencies:** Task 28.

**Writer:** project-owned pure-Python mmCIF writer, deterministic UTF-8 LF bytes. RDKit may be enabled later as an optional backend only after the exact API is source-verified; default CI uses the project-owned writer and does not require RDKit. Source-verification status (2026-06-02): the official RDKit `rdkit.Chem.rdmolfiles` API reference (`https://rdkit.org/docs/source/rdkit.Chem.rdmolfiles.html`) was re-checked and no `MolToMMCIFBlock` symbol was found. RDKit remains an optional future backend requiring source verification.

**Implemented API:**

```python
def write_covalent_complex(
    result: CovalentGenerationResult,
    protein_atom_table: ArtifactRef,
    ligand_coords: object,
    ligand_atom_types: object,
    ligand_bonds: object,
    covalent_edge: CovalentEdge,
    out_path: Path,
    *,
    artifact_root: Path,
) -> ArtifactRef:
    ...

def export_covalent_complex_result(...) -> CovalentGenerationResult:
    ...

def adapt_complex_export_failure(
    result: CovalentGenerationResult,
) -> CovalentGenerationResult:
    ...
```

**Acceptance criteria (implemented):**

- Project-owned pure-Python writer, deterministic UTF-8 LF bytes.
- Input protein table is ``ArtifactRef`` JSON with explicit keyword-only ``artifact_root``; no cwd guessing.
- Input and output paths reject absolute, traversing, and root-escaping boundaries.
- Writes ``_entry.id``, ``_atom_site.*`` (protein ``ATOM`` + ligand ``HETATM``), and exactly one ``_struct_conn.*`` row with ``conn_type_id = covale``.
- Ligand identity is deterministic: element-local names (``C1``, ``C2``, ``N1``), ``label_asym_id=L``, ``label_seq_id=1``, ``label_comp_id=LIG``, entity id ``2``.
- Output ``ArtifactRef`` is ``role=complex_mmcif``, ``format=mmcif`` with root-relative URI, exact bytes, and sha256.
- Success adapter ``export_covalent_complex_result``: immutable ``dataclasses.replace()``; sets exported / eligible / not_run and adds ``complex_mmcif``.
- Failure adapter ``adapt_complex_export_failure``: preserves generation-valid diagnostics; sets failed / not_applicable / not_applicable and ``COMPLEX_EXPORT_FAILED``.
- Writer validation/read/write errors raise ``ContractError(code=COMPLEX_EXPORT_FAILED, owner=inference)``.
- Export failure is not a sampling-system failure.
- No RDKit, torch, PMDM, PocketFlow, docking, or Task 30 behavior.
- PDB compatibility output is optional future compatibility output only - not implemented.

**Verification:**

```bash
pytest tests/inference/test_complex_export.py -q
```

### Task 30: Implement Evaluation Summary And Denominator Checks

**Goal:** Produce global (unstratified) `EvaluationSummary` with manifest-first input. All 6 conservation equations enforced.

**Files/modules:**

- `src/covalent_design/evaluation/__init__.py`
- `src/covalent_design/evaluation/denominator_accounting.py` — core API: `load_generation_run`, `summarize_results`, `check_denominators`, `evaluation_summary_to_dict`, `write_evaluation_summary`
- `src/covalent_design/evaluation/result_schema.py` — `decode_result_row()` for JSONL-to-`CovalentGenerationResult`
- `src/covalent_design/evaluation/summarize_results.py` — CLI entry point
- `src/covalent_design/evaluation/check_denominators.py` — CLI entry point
- `tests/evaluation/test_denominator_accounting.py`

**Dependencies:** Tasks 27, 28.

**Public API:**

```python
def load_generation_run(manifest: Path) -> ContractEnvelope[GenerationRunManifest]: ...
    """Parse and validate a generation-run manifest YAML.
    Validates the three mandatory checksum-validated artifact refs:
    request, results, sampling_system_failures. Only relative URIs accepted."""

def summarize_results(manifest: Path) -> EvaluationSummary: ...
    """Load a generation run and compute its EvaluationSummary.
    No write side effect. Every result row decoded and validated through
    validate_generation_result(). sampling_system_failure_count from manifest
    is authoritative — row count of sampling_system_failures.jsonl is not
    a denominator."""

def check_denominators(summary: EvaluationSummary) -> ValidationReceipt: ...
    """Validate the six EvaluationSummary conservation equations."""

def evaluation_summary_to_dict(summary: EvaluationSummary) -> dict[str, object]: ...
    """Serialize an EvaluationSummary to a deterministic JSON-compatible dict."""

def write_evaluation_summary(summary: EvaluationSummary, path: Path) -> ArtifactRef: ...
    """Write an EvaluationSummary atomically. Returns an ArtifactRef for the
    written file with role=evaluation_summary, format=json."""
```

**CLI:** Manifest-first:

```bash
python -m covalent_design.evaluation.summarize_results \
    --manifest outputs/generation/<job_id>/run_manifest.yml \
    [--error-out <path>]
python -m covalent_design.evaluation.check_denominators \
    --manifest outputs/generation/<job_id>/run_manifest.yml \
    [--error-out <path>]
```

The `summarize_results` CLI writes `evaluation_summary.json` to the manifest parent directory and prints the summary as deterministic JSON to stdout. `check_denominators` prints the validation receipt to stdout without writing files.  Both CLIs support `--error-out <path>` to write a `cli_error` JSON file on failure (role `"cli_error"`, schema from `contracts.cli_errors`).

**Acceptance criteria:**

- `load_generation_run(manifest)` parses and validates the manifest with checksum-validated artifact refs for exactly `request`, `results`, and `sampling_system_failures`. Missing any mandatory key is a hard error.
- Only relative artifact URIs accepted; absolute paths and traversal outside the manifest parent are rejected.
- `summarize_results(manifest)` reads manifest → loads results and failures by checksum-validated paths → decodes and validates every result row → computes `EvaluationSummary`. Has no write side effect.
- `check_denominators(summary)` delegates to `validate_evaluation_summary()` in `contracts.denominators`.
- `evaluation_summary_to_dict(summary)` produces a deterministic JSON-compatible dict with role `"evaluation_summary"`.
- `write_evaluation_summary(summary, path)` writes atomically via same-directory temp-file rename; returns an `ArtifactRef`.
- All 6 conservation equations enforced (centralized in `validate_evaluation_summary()`).
- `sampling_system_failure_count` read from manifest, not from `sampling_system_failures.jsonl` row count.
- `sampling_system_failures.jsonl` rows are schema-validated as `SamplingSystemFailure` audit evidence.
- For one manifest, `request_validation_error_sample_count = 0` and `requested_sample_count = accepted_request_sample_count`.
- `attempted_sample_count` and `result_count` must match the number of rows in `results.jsonl` (hard error on mismatch).
- Counts must not be inferred from files on disk.
- Invalid samples retained in validity denominators.
- Task 30 output: `evaluation_summary.json` (global, no strata).
- Stratified reports → Task 33. Failure-mode reports → Task 31. Docking protocol → Task 32.

**Verification:**

```bash
pytest tests/evaluation/test_denominator_accounting.py -q
python -m covalent_design.evaluation.summarize_results --manifest <run_manifest.yml>
python -m covalent_design.evaluation.check_denominators --manifest <run_manifest.yml>
```

### Task 31: Implement Lifecycle Validation And Failure Mode Reports

**Goal:** Reject corrupt lifecycle rows before aggregation; group failures by primary/secondary reason with lifecycle stage preserved globally, by family, and in evidence.

**Files/modules:**

- `src/covalent_design/evaluation/validity_metrics.py` — `validate_results_before_aggregation`, `summarize_lifecycle_statuses`
- `src/covalent_design/evaluation/failure_modes.py` — `FROZEN_REASON_STAGE_MAP`, `FailureModeReport`, `build_failure_mode_report`, `build_failure_mode_report_from_manifest`, `failure_mode_report_to_dict`, `write_failure_mode_report`
- `src/covalent_design/evaluation/lifecycle_reports.py` — thin re-export facade
- `tests/evaluation/test_lifecycle_reports.py`

**Dependencies:** Task 30 (reuses `load_validated_results` from `denominator_accounting`).

**Public API (Python only — no CLI):**

```python
# validity_metrics.py
validate_results_before_aggregation(results) -> ValidationReceipt
summarize_lifecycle_statuses(results) -> dict[str, int]

# failure_modes.py
build_failure_mode_report(results) -> FailureModeReport
build_failure_mode_report_from_manifest(manifest) -> FailureModeReport
failure_mode_report_to_dict(report) -> dict[str, object]
write_failure_mode_report(report, path) -> ArtifactRef
```

**Contracts:** `FailureModeReport` is an evaluation-package dataclass (in `failure_modes.py`), not a shared `contracts/types.py` type. `FROZEN_REASON_STAGE_MAP` maps every `FAILURE_REASON_CODES` value to one of five lifecycle stages: `generation`, `generation_gate`, `export`, `docking_eligibility`, `docking_run`.

**Acceptance criteria:**

- **Validate-all-before-aggregate:** `validate_results_before_aggregation` calls `validate_generation_result` on every row. One corrupt lifecycle row fails the WHOLE report — no survivor aggregation, no `corrupt_lifecycle_count` partial report, no partial output artifact. Both `summarize_lifecycle_statuses` and `build_failure_mode_report` call `validate_results_before_aggregation` internally and propagate failure as `ContractError`.
- **`validate_generation_result` reuse:** validation delegates to the existing Task 2 lifecycle validator; no new validation logic is duplicated.
- **`load_validated_results` reuse (Task 30 helper):** `build_failure_mode_report_from_manifest` delegates to `load_validated_results(manifest)` from `denominator_accounting`. Manifest parsing, artifact ref checks, checksum checks, JSONL schema checks, failures JSONL validation, manifest count checks, `decode_result_row()`, and `validate_generation_result()` are all preserved. Raw rows are never exposed.
- **Canonical `residue_reaction_family` grouping only.** No protein-cluster, scaffold, or split-aware strata.
- **Primary and secondary counts separate** globally and by family.
- **`primary_failure_reason=None` (success) does not contribute** to reason counts.
- **Lifecycle stage preserved** globally (`primary_reason_counts_by_stage`), by family and stage (`primary_reason_counts_by_family_and_stage`), and in every evidence entry with `primary_failure_stage` and `secondary_failure_stages`.
- **Invalid but lifecycle-consistent results** remain in statistics — counted in `lifecycle_statuses` with their failure reasons in the report.
- **Deterministic ordering:** families sorted alphabetically, reasons sorted alphabetically, evidence sorted by (family, reason, sample_id).
- **Atomic UTF-8 JSON writer:** `write_failure_mode_report` uses same-directory tempfile, fsync, and os.replace. Returns `ArtifactRef` with `role="failure_mode_report"`, `format="json"`. No temp artifacts left behind.
- **No duplication of Task 30 denominator equations.** Task 31 uses `load_validated_results` for input validation and `summarize_lifecycle_statuses` for status counting; denominator conservation remains Task 30 scope.
- **Unknown failure reasons** raise `ContractError(code="FAILURE_REPORT_REASON_NOT_MAPPED")` — no silent mapping.
- **No Task 31 CLI.** Task 31 exposes Python APIs and an explicit atomic writer only.
- **Task 32 docking protocol and Task 33 split-aware reports are outside Task 31.** Task 31 does not import or reference Task 32/33 modules.

**Verification:**

```bash
pytest tests/evaluation/test_lifecycle_reports.py -q
```

### Task 32: Implement Docking Protocol Manifest Validation And Score Index

**Goal:** Validate docking protocol manifests and build a flat `DockingScoreEligibleResultIndex`
from succeeded covalent docking results. Task 32 does not execute docking and has no CLI.

**Files/modules:**

- `src/covalent_design/evaluation/docking_protocol.py` — all public API functions
- `src/covalent_design/contracts/types.py` — shared frozen contract types
- `src/covalent_design/evaluation/__init__.py` — re-exports
- `tests/evaluation/test_docking_protocol.py`

**Dependencies:** Tasks 30, 31.

**Contracts:** ADR 0032 and `docs/covalent_generation_io_contract.md` lines 331-390 govern the
authoritative nested YAML manifest schema. Task 32 does not introduce a simplified
covalent/settings/artifacts schema.

**Shared frozen contract types** (in `covalent_design.contracts.types`):

- `ReceptorPreparation` — 10 fields: tool_name, tool_version, input_structure_uri, input_structure_sha256, output_receptor_uri, output_receptor_sha256, pH_or_protonation_policy, water_policy, cofactor_policy, metal_policy
- `LigandPreparation` — 6 fields: tool_name, tool_version, input_ligand_uri, input_ligand_sha256, charge_model, protonation_policy
- `CovalentConstraint` — 4 fields: representation, target_atom_identity, ligand_atom_identity, constraint_parameters (mapping, may be empty)
- `DockingSearchRegion` — 3 fields: center (numeric triple), size (numeric triple, components positive), unit (angstrom only)
- `PoseSelection` — 2 fields: ranking_rule (best_score | first_valid | other), score_unit
- `DockingProtocolManifest` — 14 top-level fields embedding the five sub-dataclasses

**Public API (6 functions, no CLI):**

```python
load_docking_protocol_manifest(path) -> DockingProtocolManifest
validate_docking_protocol_manifest(manifest, artifact_root) -> ValidationReceipt
docking_protocol_manifest_to_dict(manifest) -> dict[str, object]
build_docking_score_eligible_result_index(results, protocol_manifests, artifact_root) -> DockingScoreEligibleResultIndex
docking_score_eligible_result_index_to_dict(index) -> dict[str, object]
write_docking_score_eligible_result_index(index, path) -> ArtifactRef
```

**Acceptance criteria:**

1. **Manifest loader** (`load_docking_protocol_manifest`): decodes YAML with inline-JSON value
   decoding (e.g. `[10.0, 20.0, 30.0]`, `{}`). Missing nested sections default to empty dicts
   so the validator rejects them cleanly. Unreadable or non-mapping YAML raises structured
   `ContractError`.

2. **Manifest validator** (`validate_docking_protocol_manifest`): returns `ValidationReceipt`.
   Validates all required string fields are non-empty, SHA-256 fields are 64 lowercase hex,
   enum fields use allowed values, search region center/size are numeric triples (size positive),
   random_seed is int or None (bool rejected), constraint_parameters is a mapping (may be empty),
   all artifact URIs are root-relative (reject absolute paths and traversal including backslash),
   and all referenced artifact files exist with matching SHA-256.
   `engine_build_hash` is required non-empty provenance text and may be `unknown`; it is
   not a `*_sha256` field.

3. **Artifact validation scope**: full_config_uri, receptor_preparation.input_structure_uri,
   receptor_preparation.output_receptor_uri, ligand_preparation.input_ligand_uri, and
   failure_log_uri. Each must exist on disk and SHA-256 must match.

4. **failure_log_uri and failure_log_sha256 are required.** The referenced file may be zero-byte
   when the SHA-256 matches.

5. **constraint_parameters** may be an empty mapping. **random_seed** may be null.

6. **Index builder** (`build_docking_score_eligible_result_index`): validates every result via
   `validate_generation_result` first. Filters to valid + exported + eligible + succeeded +
   `covalent_docking_score is not None`. Requires every survivor to have
   `artifacts["docking_protocol_manifest"]` — missing association is a hard `ContractError`.
   `protocol_manifests` is keyed by that `ArtifactRef.uri`. Validates the manifest ArtifactRef
   (existence + checksum), reloads the referenced YAML and requires it to match the supplied
   manifest object, then validates all internal protocol artifacts. Missing supplied manifest,
   substituted manifest content, manifest ref checksum mismatch, wrong type, or corrupt internal
   artifacts all raise `ContractError` — no survivor index.

7. **QuickVina2-only exclusion**: rows with `docking_run_status = "not_run"` and
   `covalent_docking_score = null` are excluded normally. `noncovalent_vina_score` remains
   populated on those rows. A future documented covalent-linkage/constrained wrapper is not
   prohibited by engine-name string alone.

8. **Deterministic flat ordering**: entries sorted by `(request_id, sample_id, docking_protocol_id)`.

9. **Index serializer** (`docking_score_eligible_result_index_to_dict`): produces JSON-compatible
   dict with `role=docking_score_eligible_result_index`, `format=json`, `counts.total_eligible_entries`,
   and a flat `entries` list sorted deterministically.

10. **Atomic writer** (`write_docking_score_eligible_result_index`): same-directory tempfile,
    fsync, os.replace. Returns `ArtifactRef` with `role=docking_score_eligible_result_index`,
    `format=json`. No temp artifacts remain.

11. **Source guard**: no RDKit, torch, PMDM, PocketFlow, or docking engine imports. No Task 33
    imports. No directory-scanning manifest inference. No CLI.

12. **Prior content intact**: Task 31 content is not modified. Task 32 does not choose an
    authoritative docking engine and does not implement Task 33 split/family reports.

**Verification:**

```bash
pytest tests/evaluation/test_docking_protocol.py -q
```

### Task 33: Implement Split-Aware Evaluation Reports

**Goal:** Stratified per-split, per-family evaluation reports with protein-cluster and scaffold primary metrics.

**Files/modules:**

- `src/covalent_design/evaluation/split_metrics.py`
- `src/covalent_design/evaluation/reports.py`
- `tests/evaluation/test_split_reports.py`

**Dependencies:** Tasks 14, 30.

**Acceptance criteria:**

- Public APIs live in `covalent_design.evaluation.split_metrics` with a thin
  `covalent_design.evaluation.reports` facade:
  `load_split_index`, `validate_split_index_for_evaluation`,
  `load_leakage_report`, `validate_leakage_report_for_evaluation`,
  `join_results_to_split_assignments`, `summarize_split_results`,
  `build_stratified_evaluation_summary`,
  `stratified_evaluation_summary_to_dict`, and
  `write_stratified_evaluation_summary`.
- Split index inputs must carry `schema_version`, `contract_version`,
  `role="split_index"`, `assignment_count`, and assignments with
  `record_id`, `split`, `scaffold_key`, `protein_cluster_id`,
  `residue_reaction_family`, `fallback_reason`, and `manual_review_status`.
- Leakage report inputs must carry `schema_version`, `contract_version`,
  `role="leakage_report"`, split counts, fallback/manual-review counts,
  scaffold/protein-cluster overlap lists, and boolean `zero_overlap` flags.
  Counts are cross-validated against the split index.
- Frozen join key: `CovalentGenerationResult.request_id ==
  split_index.assignments[].record_id`. Task 33 does not support external
  request-record maps, `(request_id, sample_id)` matching, sample_id fallback,
  fuzzy matching, or directory scanning.
- Every result row is validated with `validate_generation_result` before
  aggregation. Corrupt rows raise structured `ContractError` before output.
- Per-split lifecycle summaries are `EvaluationSummary`-compatible for
  train/val/test. Task 33 does not rerun Task 30 manifest accounting; per-split
  sampling-system failures are not attributed without an explicit split-aware
  sampling failure input.
- Per-family breakdown uses canonical `residue_reaction_family`; no
  `reaction_family` alias is introduced.
- Scaffold and protein-cluster primary metrics come from the split index and
  include deterministic per-split `unique_count` and `values`.
- Leakage blocking risks are reported separately for scaffold and
  protein-cluster overlap; Task 33 reports risk and does not regenerate splits.
- Excluded and fallback records are reported with deterministic counts and
  fallback `record_ids`; manual review accounting is preserved.
- Optional docking score eligible index counts can be joined by request id;
  absence of docking input is valid and reported as `null`.
- Writer output is deterministic UTF-8 JSON via same-directory tempfile,
  fsync, and `os.replace`, returning an `ArtifactRef` with
  `role="stratified_evaluation_summary"`.
- No CLI is introduced in Task 33. No RDKit, torch, PMDM, PocketFlow, docking
  engine, split regeneration, Checkpoint C execution, or inference/model/training
  behavior is implemented.
- Output: `stratified_evaluation_summary.json`.

**Verification:**

```bash
python -m unittest tests.evaluation.test_split_reports -v
```

### Checkpoint C: Inference And Evaluation Gate

**Dependencies:** Tasks 26-33.

**Proof of completion:**
- All 13 request validation error fixtures pass
- `SamplingSystemFailure` fixtures: crash, OOM, timeout, retry_exhausted, checkpoint_load_failed, sampler_invariant_violation (all 6 categories)
- Valid and invalid `CovalentGenerationResult` fixtures with complete diagnostics
- mmCIF export valid + export-failure fixtures through the project-owned writer/adapter boundary
- Evaluation denominator equations pass on golden summaries
- Docking protocol manifest validation passes; QuickVina2-only rejected
- `python -m compileall -q scripts src` passes

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

- Default CI runs `python -m compileall -q scripts src`.
- Default CI runs `python -m pytest tests/contracts tests/io tests/data tests/rules -q`.
- Default CI runs `python -m pytest tests/ci -q` so CI policy and repository hygiene self-check.
- Default CI runs `python -m pytest tests/cli -q` for lightweight structured-exit coverage.
- Default CI excludes RDKit, CUDA, docking, training, inference, evaluation, PMDM, and PocketFlow.
- CI installs only minimal dependencies (pytest only).
- Repository hygiene blocks generated caches, large binaries, checkpoint/model-weight artifacts, and broad docking/log/raw-data artifacts.
- Task 35 narrow fixture exceptions are exact and are not broadened: one zero-byte `.log`, one minimal `.pdbqt`, and YAML-only checkpoint metadata files under `tests/fixtures/training/checkpoints/`.
- The project must not commit real data, real checkpoints, real model weights, or real docking outputs.

**Verification:**

```bash
python -m compileall -q scripts src
pytest tests/contracts tests/io tests/data tests/rules -q
pytest tests/ci -q
pytest tests/cli -q
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
- Which optional chemistry backend, if any, should implement the mmCIF writer adapter after source verification?
- What are the initial covalent loss weights and edge-score thresholds?
