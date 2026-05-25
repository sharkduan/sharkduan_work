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
python -m covalent_design.rules.build_calibration_sheet --records data/processed/covalent_complex_records/records.jsonl
python -m covalent_design.rules.validate_rule_table --rules data/rules/reaction_family_rule_table.yml
python -m covalent_design.candidates.build_edge_candidates --records data/processed/covalent_complex_records/records.jsonl --radius 4.0
python -m covalent_design.data.finalize_record_manifests --records data/processed/covalent_complex_records/records.jsonl
python -m covalent_design.data.build_splits --records data/processed/covalent_complex_records/records.jsonl
python -m covalent_design.viz.export_visual_checks --records data/processed/covalent_complex_records/records.jsonl
python -m covalent_design.data.write_quality_report --out data/reports/etl_quality_report.md
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

src/covalent_design/rules/
  schema.py
  calibration.py
  validate.py

src/covalent_design/candidates/
  edge_candidates.py

src/covalent_design/viz/
  visual_checks.py

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
- Record writing is two-phase: `build_record_index` writes the accepted/rejected/conflict indexes and non-edge artifacts; `finalize_record_manifests` runs after edge candidates exist and must fail if any accepted record lacks a manifest entry for edge candidates.

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
- `visual_check_export`
- `visual_check_status_gate`
- `scaffold_fallback_accounting_check`

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
- `data/rules/rule_calibration_sheet.csv` exists and supports manual review.
- `data/rules/reaction_family_rule_table.yml` validates against the rule schema.
- Radius-bounded candidate artifacts include explicit `empty_radius_window` semantics when no local negatives exist.
- Random, protein-cluster, and de-warheaded scaffold splits exist and primary scaffold overlap is zero across train/val/test.
- Scaffold split artifacts include fallback reasons. Records with `fallback_reason = "warhead_unmatched"` are excluded from primary scaffold release metrics unless manually reviewed.
- Visual checks are exported for sampled records and include status fields. A sampled record with `fail` is removed from the first training core until the failure is resolved; `needs_rule_review` blocks release for that sampled record until a rule decision is recorded.

## Open Questions

- What exact raw file shapes will be staged for each source?
- Which artifact format should store atom tables and coordinates?
- Which protein clustering algorithm and threshold define the protein-cluster split?
- Who signs off manual rule calibration and visual inspection status?
- Which chemical-state inference tool is acceptable when state is not explicit?
