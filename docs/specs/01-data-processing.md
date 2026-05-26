# Spec: Data Processing

## Objective

Build the ETL module that produces an auditable covalent training corpus before model work begins. The module ingests manually staged CovalentInDB 2.0, CovPDB, and CovBinderInPDB data; normalizes atom-level monodentate covalent linkages; writes `CovalentComplexRecord` indexes and external artifacts; creates rule calibration evidence, edge candidates, leakage-aware splits, visual checks, and an ETL quality report.

Success means downstream model and training code can consume accepted monodentate records without consulting raw source-specific formats.

## Tech Stack

- Python 3.9-compatible project-owned code.
- Optional molecular dependencies for full runs: RDKit and structure parsers capable of PDB/mmCIF/SDF handling.
- Storage: JSONL indexes, YAML manifests, CSV calibration sheets, and external tensor/table artifacts.
- No automatic raw-data downloader in v1.

## Commands

```bash
python -m covalent_design.data.validate_manifests --raw-root data/raw
python -m covalent_design.data.ingest --source covbinder_in_pdb --raw-root data/raw --out data/interim
python -m covalent_design.data.ingest --source covpdb --raw-root data/raw --out data/interim
python -m covalent_design.data.ingest --source covalentin_db --raw-root data/raw --out data/interim
python -m covalent_design.data.normalize --interim-root data/interim --out-root data/processed
python -m covalent_design.data.build_record_index --processed-root data/processed
python -m covalent_design.rules.cli.validate_rule_table --rules data/rules/reaction_family_rule_table.yml
python -m covalent_design.rules.cli.build_calibration_sheet --records data/processed/records.jsonl --rules data/rules/reaction_family_rule_table.yml --out-csv data/rules/rule_calibration_sheet.csv
python -m covalent_design.candidates.cli.build_edge_candidates --records <records.jsonl> --radius 4.0
python -m covalent_design.data.cli.finalize_record_manifests --records <records.jsonl>
python -m covalent_design.data.cli.build_splits --records data/processed/covalent_complex_records/records.jsonl --out-root data/splits
python -m covalent_design.viz.cli.export_visual_checks --records data/processed/covalent_complex_records/records.jsonl --out-root data/viz [--sample-count N] [--seed 42]
python -m covalent_design.data.cli.write_quality_report --processed-root data/processed --ingest-roots data/interim/covbinder_in_pdb --ingest-roots data/interim/covpdb --ingest-roots data/interim/covalentin_db --splits-root data/splits --visual-checks-root data/viz --out data/reports/quality_report.json
python -m compileall -q scripts src
```

## Project Structure

```text
src/covalent_design/data/
  manifests.py
  ingest.py
  sources/
    covbinder_in_pdb.py
    covpdb.py
    covalentin_db.py
  identity.py
  normalize.py
  records.py
  artifact_manifests.py
  quality.py
  splits.py
  quality_report.py
  cli/
    build_splits.py
    finalize_record_manifests.py
    write_quality_report.py

src/covalent_design/rules/
  schema.py
  calibration.py
  validate.py
  cli/
    build_calibration_sheet.py
    validate_rule_table.py

src/covalent_design/candidates/
  edge_candidates.py
  cli/
    build_edge_candidates.py

src/covalent_design/viz/
  visual_checks.py
  cli/
    export_visual_checks.py

data/raw/
data/interim/
data/processed/
data/rules/
data/reports/
```

## Code Style

Keep every transform inspectable and deterministic. Parsers may be source-specific; normalized outputs must be source-independent.

```python
def build_record_id(identity: CanonicalLinkageIdentity) -> str:
    payload = identity.to_normalized_json()
    return sha256(payload.encode("utf-8")).hexdigest()[:32]
```

Rules:

- Every source record keeps `source_database`, `source_version`, `raw_manifest_file`, `raw_file_path`, `raw_file_sha256`, row locator, and license reference.
- Cross-source duplicates merge only when canonical linkage identity matches.
- Linkage identity conflicts produce conflict artifacts and are excluded from the first training core.
- Quality severities are `Q0`, `Q1`, and `Q2`; do not reuse CovalentInDB field priority names for quality behavior.
- Task 9 treats `required_gate_state_unavailable` as a Q0 rejection flag when present. Full protein chemical-state inference and flag population remain an explicit pre-training-core dependency, not an implied side effect of normalization.
- Large protein, ligand, coordinate, and edge tensors are external artifacts, not inline JSONL arrays.
- Record writing is two-phase: `build_record_index` (Task 10) writes the accepted/rejected/conflict indexes and the four required non-edge artifact references (`protein_atom_table`, `ligand_atom_table`, `ligand_bond_table`, `coordinates`); `finalize_record_manifests` (Task 13) runs after edge candidates exist, validates embedded `artifact_refs` in every `edge_candidates.json`, appends the `edge_candidates` artifact ref to each accepted record's `artifacts` list, and updates `artifact_manifest.json`. Task 13 fails hard on missing `edge_candidates.json`, checksum mismatches in embedded artifact refs, pre-existing `edge_candidates` refs (duplicate detection), and obsolete manifest entries not linked to any accepted record. No partial writes: if any error is detected, `records.jsonl` and `artifact_manifest.json` are not modified. Task 10 does not generate `edge_candidates`, `visual_check`, or split keys — those are appended or verified by later tasks.
- `ingest --out <dir>` writes `source_records.jsonl` and `ingest_index.json` under the output directory. This directory is compatible as `--interim-root` input to `normalize`, enabling a documented end-to-end CLI pipeline.
- Split artifacts are written under a dedicated `--out-root` and must not mutate `records.jsonl` or `artifact_manifest.json`. Task 14 consumes finalized Task 13 records.
- Task 14 does **not** produce visual check or quality report artifacts (Task 15/16 scope).
- Task 15 consumes finalized Task 13 `records.jsonl` (accepted records with artifact refs including `edge_candidates`). It writes visual check artifacts under `--out-root` and must not mutate `records.jsonl` or `artifact_manifest.json`.
- Task 15 does **not** generate an ETL quality report (Task 16 scope).
- Default `SplitPolicy`: algorithm `"leakage_aware_covalent_splits"`, algorithm_version `"1.0.0"`, random_seed `42`, split_ratios `{"train": 0.80, "val": 0.10, "test": 0.10}`.
- Scaffold key derivation uses `algorithm: "fixture_key"` (metadata-based hashing of core_labels identity fields: `warhead_type`, `residue_reaction_family`, `bond_type`, `ligand_atom_element`, `ligand_atom_index`, `ligand_atom_name`, `target_atom_index`, `target_atom_name`). Precomputed `scaffold_key` values from `metadata` bypass derivation. A user-accepted chemistry library (e.g., RDKit Bemis-Murcko) is required before production use — this is recorded as an unresolved user decision in `docs/specs/key-design-decisions.md`.
- Protein clustering uses `protein_cluster_id` when present in `metadata`; the real clustering authority (sequence identity method, threshold, UniProt mapping) is a deferred user decision.
- `fallback_reason` values: `warhead_unmatched`, `missing_scaffold_input`, `missing_protein_cluster_input`, `manual_review_override`. Fallback priority chain: `missing_protein_cluster_input` > `missing_scaffold_input` > `warhead_unmatched` > `manual_review_override`.
- `manual_review_status` values: `pending`, `approved`, `rejected`. `reviewer`, `reviewed_at`, and `notes` are deferred until a manual review workflow is established.
- `warhead_unmatched` fallback records are excluded from primary scaffold release metrics unless `manual_review_status = "approved"`.

## Testing Strategy

Required smoke tests:

- `source_manifest_checksum_check`
- `parse_10_covbinder_records`
- `linkage_atom_mapping_check`
- `monodentate_filter_check`
- `dedupe_conflict_resolution_check`
- `records_jsonl_schema_check`
- `artifact_manifest_consistency_check`
- `edge_candidate_label_check`
- `geometry_summary_check`
- `protein_chemical_state_check`
- `scaffold_key_generation_check`
- `scaffold_split_leakage_check`
- `protein_cluster_integrity_check`
- `scaffold_fallback_accounting_check`
- `manual_review_override_check`
- `split_artifact_schema_check`
- `split_count_conservation_check`
- `split_non_mutation_check`
- `visual_check_schema_check`
- `visual_check_deterministic_sampling_check`
- `visual_check_gate_semantics_check`
- `visual_check_optional_geometry_check`

Tests live under `tests/data/`, `tests/rules/`, `tests/candidates/`, and `tests/viz/` once a test suite is introduced.

## Boundaries

Always:

- Require raw source manifests with version, date, license/access notes, file roles, bytes, and SHA-256 checksums.
- Preserve rejected records and conflict groups with audit lineage.
- Treat all three sources as required for v1 completion gates.

Ask first:

- Adding automatic download.
- Changing source priority `CovBinderInPDB > CovPDB > CovalentInDB`.
- Adding new supported residue-reaction families.

Never:

- Treat files absent from the manifest as ingested inputs.
- Silently overwrite conflicting source annotations.
- Include multi-linkage records in the v1 training core.
- Interpret empty SMARTS lists or null geometry bounds as permissive rules.

## Success Criteria

- Each required source has `complete_for_v1: true` in `data/reports/etl_quality_report.md`.
- Accepted `CovalentComplexRecord` rows each contain exactly one monodentate covalent linkage and one positive edge label.
- Rejected records and conflict groups are counted with reasons and lineage.
- `data/rules/rule_calibration_sheet.csv` exists with 14 columns (family_id, sample_count, representative_record_ids, target_atom_distribution, ligand_attachment_element_distribution, warhead_distribution, bond_length_summary, protein_side_angle_summary, ligand_side_angle_summary, outlier_record_ids, manual_decision, notes, pending_smarts_marker, pending_geometry_marker) and supports manual review.
- `data/rules/reaction_family_rule_table.yml` validates against the rule schema.
- Radius-bounded candidate artifacts include explicit `empty_radius_window` semantics when no local negatives exist.
- Random, protein-cluster, and de-warheaded scaffold splits exist and primary scaffold overlap is zero across train/val/test. Protein-cluster overlap is also zero across train/val/test.
- Scaffold split artifacts include `scaffold_keys.jsonl` per-record entries with `algorithm: "fixture_key"`, `warhead_match` sub-object, scaffold key, and fallback reason. Records with `fallback_reason = "warhead_unmatched"` are excluded from primary scaffold release metrics unless `manual_review_status = "approved"`.
- `split_index.json` contains assignments with per-record split, scaffold_key, protein_cluster_id, residue_reaction_family, fallback_reason, and manual_review_status.
- `leakage_report.json` reports `scaffold_overlaps` and `protein_cluster_overlaps` lists and `zero_overlap` flags.
- `fallback_accounting.json` reports per-reason counts and record_ids.
- `manual_review_index.json` records review status (`pending`/`approved`/`rejected`). `reviewer`, `reviewed_at`, and `notes` fields are deferred until a manual review workflow is established.
- Split artifacts are written under a dedicated output root and do not mutate `records.jsonl` or `artifact_manifest.json`.
- Visual checks are exported for sampled records via `python -m covalent_design.viz.cli.export_visual_checks`. Output artifacts are written under `--out-root` and include `visual_check_index.json` (with `sample_policy`, `status_counts` for `pending`/`pass`/`fail`/`needs_rule_review`, `blocking_counts`, and per-record entries with `artifact_ref`) and per-record `artifacts/<record_id>/visual_check.json` (with `target_atom`, `ligand_attachment_atom`, `covalent_edge`, `residue_reaction_family`, `warhead_annotation`, optional `distance` and `local_angles` from `metadata.geometry`, `status`, and `blocking_first_core`). Sampling is deterministic by `record_id` sort order with a configurable `--seed` (default 42). `--sample-count` is optional; when omitted all accepted records are sampled. Missing geometry values are `null` — this is valid output, not a failure. Status values: `pending` (blocks until reviewed), `pass` (does not block), `fail` (blocks until resolved), `needs_rule_review` (blocks until curator decision). `blocking_first_core` is `true` for `pending`, `fail`, and `needs_rule_review`; `false` only for `pass`. Visual check artifacts do not mutate `records.jsonl` or `artifact_manifest.json`. Task 15 does not generate an ETL quality report — the quality report that reconciles sources, records, candidates, splits, and visual checks is Task 16 scope.

## Task 16 Quality Report

The Task 16 ETL quality report is written by `python -m covalent_design.data.cli.write_quality_report`. It reports per-source `complete_for_v1` as a source coverage signal, not as the count reconciliation equation itself. Count reconciliation is explicit: accepted records must have readable edge-candidate artifacts, split assignment totals must match accepted records when split input is provided, and visual check status/blocking totals must match sampled records when visual input is provided.

## Open Questions

- What exact raw file shapes will be staged for each source?
- Which artifact format should store atom tables and coordinates?
- Which protein clustering algorithm and threshold define the protein-cluster split?
- Who signs off manual rule calibration and visual inspection status?
- Which chemical-state inference tool is acceptable when state is not explicit?
