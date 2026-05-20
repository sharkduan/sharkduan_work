# Covalent ETL Plan

This document defines the first implementation phase for the covalent inhibitor design project. The phase builds validated supervision artifacts before modifying the PMDM model.

## Goal

Build an auditable covalent training corpus for de novo covalent inhibitor generation.

The ETL must produce:

- `CovalentComplexRecord` entries
- `Reaction Family Rule Table`
- `Rule Calibration Sheet`
- radius-bounded covalent edge candidates
- leakage-aware dataset splits
- visual inspection artifacts for target atoms and ligand attachment atoms

## Source Databases

The first corpus combines three public sources:

- CovalentInDB
- CovPDB
- CovBinderInPDB

Each source contributes different evidence:

- CovalentInDB: inhibitor, target, warhead, reaction mechanism, binding-site, and cocrystal annotations
- CovPDB: high-resolution covalent protein-ligand complexes, ligands, warheads, targetable residues, and mechanisms
- CovBinderInPDB: atom-level residue-binder covalent records from PDB/mmCIF structures

## Source Priority

The first implementation should start with CovBinderInPDB because it is closest to the atom-level covalent linkage schema needed for `CovalentComplexRecord` and cross-edge supervision.

CovalentInDB 2.0 is also a required dataset source, not an optional reference. It should be integrated after the first CovBinderInPDB parsing path is validated, because it provides broad inhibitor coverage, cocrystal structures, target annotations, warhead types, covalent binding sites, and reaction mechanisms.

CovPDB remains a required structural benchmark and cross-check source for high-resolution covalent protein-ligand complexes.

## Required Source Completion Gates

All three sources are required before the first ETL phase is considered complete. A source is `complete_for_v1` only when it satisfies every gate below:

```text
raw files are listed in the staging manifest
raw file checksums are recorded and stable for the run
license and access notes are recorded
source parser emits source-specific records
parser failures are counted with failure reasons
source records are normalized into candidate linkage records where structure data exists
cross-source identity fields are populated when available
source coverage appears in the ETL quality report
```

Per-source gates:

- CovBinderInPDB: atom-level residue-binder linkage fields are parsed, target atom and ligand attachment atom mapping is attempted, and monodentate acceptance/rejection status is assigned.
- CovPDB: structural complex records are parsed, resolution is preserved, ligand and warhead annotations are normalized, and structural cross-check evidence can be joined by PDB id and ligand identity.
- CovalentInDB 2.0: P0-source annotation fields are parsed, cocrystal/PDB references are preserved, and inhibitor/target/warhead/reaction annotations can be joined to structural records when possible.

The quality report must expose `complete_for_v1: true|false` for each source. A missing or incomplete required source blocks the first ETL phase even if another source has enough records for smoke tests.

## Raw Data Staging

The first ETL does not automatically download external datasets. Users manually download and place source files under:

```text
data/raw/covalentin_db/
data/raw/covpdb/
data/raw/covbinder_in_pdb/
```

ETL scripts only read, parse, normalize, and validate files already staged in `data/raw/`.

Automatic downloading may be added later after source URLs, access requirements, and licensing expectations are reviewed.

Every staged source directory must include a manifest:

```text
data/raw/covalentin_db/manifest.yml
data/raw/covpdb/manifest.yml
data/raw/covbinder_in_pdb/manifest.yml
```

Required manifest fields:

```yaml
source_database: CovalentInDB | CovPDB | CovBinderInPDB
source_version: ""
download_or_export_date: YYYY-MM-DD
retrieval_method: manual_download | manual_export | received_archive
source_url_or_reference: ""
license_name: ""
license_url_or_terms_reference: ""
redistribution_allowed: true | false | unknown
files:
  - path: relative/path/from/source/root
    bytes: 0
    sha256: ""
    role: structure | table | annotation | archive | readme | other
    format: csv | tsv | json | sdf | pdb | mmcif | zip | other
notes: ""
```

The ETL must fail source ingestion when a file listed in the manifest is missing, has a checksum mismatch, or lacks a license/access note. Files not listed in the manifest must be ignored by default and reported as unstaged extras.

## CovalentInDB 2.0 Field Priority

Field priority names describe data contract severity only. They are separate from quality-filter severity names used later in this document.

P0-source fields must be parsed in the first CovalentInDB integration:

```text
inhibitor id / name
target id / name / UniProt
PDB id / cocrystal structure id
covalent binding site
warhead type
covalent reaction mechanism
```

P1-source fields should be preserved when available, but must not enter the first training loss:

```text
activity fields
assay information
drug / clinical status
noncovalent interaction annotations
```

P2-source fields are future extensions and should not be part of the first supervised training set:

```text
ADMET predictions
virtual screening library compounds
natural products with covalent binding potential
```

The first training path uses P0-source fields only. P1-source and P2-source fields may be retained for later filtering, ranking, guidance, or analysis.

## Directory Layout

Raw source files:

```text
data/raw/covalentin_db/
data/raw/covpdb/
data/raw/covbinder_in_pdb/
```

Intermediate normalized artifacts:

```text
data/interim/parsed_structures/
data/interim/normalized_ligands/
data/interim/linkage_records/
```

Processed training artifacts:

```text
data/processed/covalent_complex_records/
data/processed/edge_candidates/
data/processed/splits/
data/processed/splits/scaffold_keys/
```

Rules and reports:

```text
data/rules/reaction_family_rule_table.yml
data/rules/rule_calibration_sheet.csv
data/reports/etl_quality_report.md
data/reports/sampled_visual_checks/
```

Implementation code:

```text
src/covalent_design/data/
src/covalent_design/rules/
src/covalent_design/viz/
```

## ETL Stages

### 1. Ingest Sources

Parse raw CovalentInDB, CovPDB, and CovBinderInPDB files into source-specific records.

Required outputs:

- source record id
- source database name
- PDB id where available
- target metadata
- ligand metadata
- warhead and reaction mechanism annotations where available
- original structure file references

Each source-specific record must keep:

```text
source_record_id
source_database
source_version
raw_manifest_file
raw_file_path
raw_file_sha256
raw_row_or_entry_locator
source_license_name
source_license_reference
```

### 1a. Resolve Canonical Record Identity

The canonical unit is one accepted monodentate protein-ligand covalent linkage in one biological structure context. The canonical identity key is:

```text
pdb_id
model_id
protein_chain_id
target_residue_name
target_residue_seq_id
target_residue_insertion_code
target_atom_name
ligand_chain_id
ligand_component_id
ligand_instance_id
ligand_attachment_atom_name_or_index
residue_reaction_family
```

`record_id` is a deterministic hash of the canonical identity key after normalization. Source-specific identifiers are never used as canonical ids.

Cross-source duplicate handling:

```text
if canonical identity keys match:
    merge evidence into one CovalentComplexRecord
    append all source references to lineage.sources

if PDB id and ligand match but target atom or linkage identity conflicts:
    do not merge
    emit conflict group
    reject from first training core unless manually resolved

if annotation fields conflict but linkage identity agrees:
    keep the structural linkage
    choose normalized annotation by source priority CovBinderInPDB > CovPDB > CovalentInDB
    preserve losing values in lineage.conflicts
```

Conflict resolution must be deterministic and reported. The first ETL must not silently overwrite source annotations.

### 2. Extract Atom-Level Linkages

Extract protein-ligand covalent linkages from PDB/mmCIF records.

Required fields:

- protein chain id
- target residue name
- target residue sequence id
- target atom name
- ligand component id
- ligand atom name or index
- covalent distance where available
- source linkage record

### 3. Normalize Ligands and Structures

Normalize ligand atom tables, ligand bond tables, coordinates, residue identifiers, and protein atom tables.

Quality checks:

- ligand atom count matches coordinate table
- ligand bond table is chemically parseable
- target atom exists in protein atom table
- ligand attachment atom maps to ligand atom table
- covalent linkage is monodentate for the first version

The first training core accepts only monodentate protein-ligand covalent records:

```text
if exactly one protein-ligand covalent linkage:
    accepted_core = true

if two or more protein-ligand covalent linkages:
    accepted_core = false
    quality_flags += ["multi_covalent_linkage"]
    rejection_reason = "first version supports monodentate only"
```

Rejected multi-linkage records must still keep lineage sufficient for audit:

```text
rejected_record_id
source_database
source_record_id
canonical_identity_fields_available
all_detected_linkages
raw_file_path
raw_file_sha256
rejection_reason
quality_flags
```

They are excluded from `records.jsonl` used for training, but included in the rejected-record index and ETL quality report.

### Quality Filtering

Quality severity names describe ETL acceptance behavior. They are separate from CovalentInDB field priority names.

Q0 hard rejection criteria:

```text
missing target atom
missing ligand attachment atom
missing ligand coordinates
unmappable ligand atom index or atom name
malformed ligand bond table
multi-covalent linkage
unsupported residue-reaction family
missing required protein chemical state for a required gate
```

Q1 default rejection criteria, counted in reports:

```text
X-ray resolution worse than 3.0 Angstrom
covalent bond length extreme outlier
severe protein-ligand clash
incomplete ligand heavy atoms
alternate location ambiguity at target atom or ligand attachment atom
```

Q2 keep-with-flag criteria:

```text
missing activity data
missing assay data
non-human protein
low-confidence warhead mapping
protein chemical state inferred rather than explicit
```

First-version training core policy:

```text
Q0: hard reject
Q1: reject by default and count in quality report
Q2: keep with quality flags
```

A high-quality record is acceptable for the first training core only when all thresholds below pass:

```text
source completeness: at least one required source supplies structural linkage evidence
identity: deterministic record_id is populated and duplicate/conflict status is resolved
linkage: exactly one protein-ligand covalent linkage
atom mapping: target atom and ligand attachment atom both map to atom tables
ligand completeness: ligand heavy atoms and bond table are parseable
coordinates: protein and ligand coordinates exist for all required atoms
resolution: X-ray resolution is <= 3.0 Angstrom when resolution is available
protein chemical state: target atom formal charge, protonation state, and hydrogen handling satisfy the rule-table state requirements or are explicitly marked unsupported
geometry: covalent bond length is inside the reviewed rule range, or the family geometry is explicitly pending and not used for geometry-gated evaluation
reaction family: family exists in the validated rule table
edge labels: exactly one positive edge label exists
negative labels: no-edge candidate semantics are recorded even when zero negatives are found
visual status: selected samples have manual status recorded before release
```

### 4. Build CovalentComplexRecord

Create minimal training records with:

```text
record_id
lineage.sources
pdb_id
model_id
protein_chain_id
protein_atom_table
ligand_atom_table
ligand_bond_table
target_residue_name
target_residue_seq_id
target_residue_insertion_code
target_atom_name
target_atom_index
protein_preparation_policy
target_atom_formal_charge
target_atom_protonation_state
target_atom_hydrogen_state
protein_chemical_state_status
ligand_attachment_atom_index
covalent_bond_type
residue_reaction_family
warhead_type
complex_coordinates
quality_flags
```

The record is split into core and metadata fields.

Core fields are used by the first supervised training path:

```text
structure fields
atom tables
bond tables
covalent attachment labels
residue-reaction family
warhead type
coordinates
quality flags
```

Metadata fields should be preserved when available but must not enter the first training loss:

```text
IC50, Ki, Kd, EC50
kinact/KI
assay information
clinical or drug status
source links
```

Excluded from the first training loss:

- IC50, Ki, Kd
- kinact/KI
- ADMET
- toxicity
- selectivity panel
- commercial availability

Record storage uses a JSONL index with external structure and tensor artifacts:

```text
data/processed/covalent_complex_records/records.jsonl
data/processed/covalent_complex_records/structures/
data/processed/covalent_complex_records/ligands/
```

Each JSONL row stores:

```text
record_id
schema_version
lineage.sources
pdb_id
core labels
quality_flags
paths to structure artifacts
metadata
```

Large arrays and tensors should not be embedded directly in JSONL. Store protein atom tables, ligand atom tables, coordinates, and edge candidates as separate `.pt`, `.npz`, or parquet-style artifacts.

Schema boundary:

- `CovalentComplexRecord` contains one accepted monodentate linkage and the minimum fields needed to train, validate, and audit that linkage.
- Source-specific fields that are not normalized into core labels remain under `metadata.source_annotations`.
- Rejected records and conflict groups are not `CovalentComplexRecord` entries; they live in separate rejection and conflict indexes.
- Calibration aggregates and rule decisions are not embedded in each record; they are linked by `residue_reaction_family` and artifact manifests.

Required JSONL fields:

```text
record_id
schema_version
pdb_id
model_id
protein_chain_id
ligand_chain_id
ligand_component_id
ligand_instance_id
target_residue_name
target_residue_seq_id
target_residue_insertion_code
target_atom_name
target_atom_index
protein_preparation_policy
target_atom_formal_charge
target_atom_protonation_state
target_atom_hydrogen_state
protein_chemical_state_status
ligand_attachment_atom_index
covalent_bond_type
residue_reaction_family
warhead_type
quality_flags
lineage.sources
artifacts
metadata
```

Required artifact manifest fields per record:

```yaml
record_id: ""
schema_version: 1
artifacts:
  protein_atom_table: {path: "", sha256: "", format: ""}
  ligand_atom_table: {path: "", sha256: "", format: ""}
  ligand_bond_table: {path: "", sha256: "", format: ""}
  coordinates: {path: "", sha256: "", format: ""}
  edge_candidates: {path: "", sha256: "", format: ""}
  visual_check: {path: "", sha256: "", status: pending | pass | fail | not_sampled}
```

Index consistency checks:

```text
every records.jsonl row has an artifact manifest
every artifact path in records.jsonl exists in the artifact manifest
every artifact manifest checksum matches the file
record_id in records.jsonl equals record_id in every linked artifact manifest
no artifact manifest exists for a missing records.jsonl row unless it is marked rejected or obsolete
```

### 5. Build Rule Calibration Sheet

Summarize per-family evidence for manual review.

Required columns:

```text
family_id
sample_count
representative_pdb_ids
target_atom_distribution
ligand_attachment_element_distribution
warhead_type_distribution
common_warhead_smarts
bond_length_summary
protein_side_angle_summary
ligand_side_angle_summary
outlier_records
manual_decision
notes
```

### 6. Build Reaction Family Rule Table

Create the first manually reviewed rule table from calibration evidence.

The first-pass vocabulary is:

- `CYS_MICHAEL_ADDITION`
- `CYS_NUCLEOPHILIC_SUBSTITUTION`
- `CYS_DISULFIDE_EXCHANGE`
- `SER_ACYLATION`
- `SER_PHOSPHONYLATION`
- `LYS_SCHIFF_BASE`

### 7. Build Radius-Bounded Edge Candidates

For each record, construct candidate covalent cross edges:

```text
positive:
  target_atom -> ligand_attachment_atom

negatives:
  target_atom -> ligand atoms within 4.0 Angstrom except the attachment atom
```

If no ligand atoms other than the attachment atom are within 4.0 Angstrom, the record is still valid. The edge candidate artifact must encode:

```text
positive_edge_count = 1
negative_edge_count = 0
negative_sampling_status = "empty_radius_window"
negative_radius_angstrom = 4.0
```

An empty 4.0 Angstrom negative set means "no local no-edge candidates were available under the chosen radius", not "the record has no negative supervision requirement globally". Such records remain eligible for training, but the quality report must count them separately for positive/negative ratio review.

Optional hard negatives:

- chemically plausible hetero atoms near the target atom with wrong warhead context

Rejected strategy:

- all target-to-ligand atom pairs as negatives

### 8. Build Leakage-Aware Splits

Create:

- random split for debugging
- protein-cluster split for target generalization
- de-warheaded scaffold split for chemical scaffold generalization

Primary evaluation must use protein-cluster and scaffold splits.

The primary scaffold split key is:

```text
dewarheaded_scaffold_key + residue_reaction_family
```

Each scaffold-split record must have a scaffold-key artifact:

```yaml
record_id: ""
residue_reaction_family: ""
warhead_match_source: rule_table_smarts | curated_annotation | manual_override | unknown
warhead_match_rule_id: ""
removed_warhead_atom_indices: []
dewarheaded_parent_smiles: ""
scaffold_algorithm: murcko | other
scaffold_algorithm_version: ""
normalization_policy:
  salt_handling: remove | keep | not_applicable
  tautomer_policy: canonicalize | preserve
  protonation_policy: neutralize | preserve
  stereochemistry_policy: preserve | strip_for_split
dewarheaded_scaffold_key: ""
whole_ligand_scaffold_key: ""
warhead_scaffold_key: ""
fallback_reason: null
```

Fallback and leakage rules:

- if no warhead can be matched, set `fallback_reason = "warhead_unmatched"` and exclude the record from primary scaffold-split release metrics unless manually reviewed
- whole-ligand scaffold and warhead-scaffold keys are diagnostic only and must not replace `dewarheaded_scaffold_key`
- split assignment must be generated before model training and must not depend on docking availability
- train/val/test overlap for `dewarheaded_scaffold_key` must be zero
- train/val/test overlaps for whole-ligand and warhead-scaffold keys must be reported as diagnostics

### 9. Export Visual Checks

Generate sampled visual inspection artifacts for manual review.

Each visual check should show:

- protein target atom
- ligand attachment atom
- predicted or extracted covalent edge
- residue-reaction family
- warhead annotation
- bond distance and local angles

Sampling and status requirements:

```text
sample at least 10 accepted records for smoke tests
sample at least min(50, accepted_count) records for first release review
include at least one sample per supported residue-reaction family when available
oversample records with Q2 flags and geometry-pending families
record status as pending, pass, fail, or needs_rule_review
```

Visual check status is blocking only for sampled records. A sampled record with `fail` is removed from the first training core unless the failure is resolved and the status is updated.

### 10. Write ETL Quality Report

Generate:

```text
data/reports/etl_quality_report.md
```

The report must include:

```text
1. Source coverage
2. Accepted/rejected summary
3. Reaction family distribution
4. Target residue distribution
5. Warhead type distribution
6. Linkage quality
7. Geometry quality
8. Protein chemical-state quality
9. Edge candidate statistics
10. Split statistics
11. Visual check index
```

Required content:

- source coverage: records read, parsed, failed by source
- accepted/rejected summary: accepted core count, Q0/Q1/Q2 counts, rejection reason distribution
- reaction family distribution: sample count per `residue_reaction_family`
- target residue distribution: residue count by CYS, SER, LYS, and any excluded residues
- warhead type distribution: frequency table for normalized warhead types
- linkage quality: covalent bond length distribution and extreme outlier records
- geometry quality: protein-side and ligand-side angle distributions
- protein chemical-state quality: explicit, inferred, missing, and unsupported target-state counts by residue-reaction family
- edge candidate statistics: candidates per record, negative examples per record, positive/negative ratio
- split statistics: train/val/test counts, family distributions, primary de-warheaded scaffold overlap, diagnostic whole-ligand scaffold overlap, diagnostic warhead-scaffold overlap, and scaffold fallback counts
- visual check index: sampled visual artifact paths and manual review status

The accepted/rejected summary must use the names `Q0`, `Q1`, and `Q2`. If older reports mention `P0`, `P1`, or `P2` for quality filters, they must be treated as stale.

## Acceptance Criteria

The first ETL phase is complete when:

- all three required sources have `complete_for_v1: true` in the quality report
- every raw source file used by ETL is covered by a manifest with version, checksum, and license/access fields
- high-quality `CovalentComplexRecord` files exist for the supported reaction families
- required protein chemical-state fields are present, inferred with provenance, or rejected as unsupported before training
- canonical `record_id` values are deterministic, cross-source duplicates are merged, and unresolved conflicts are excluded with audit lineage
- the `Rule Calibration Sheet` is generated and manually reviewed
- the `Reaction Family Rule Table` exists and passes validation
- radius-bounded edge candidates exist with positive labels and no-edge candidate labels or explicit empty-radius-window semantics
- random, protein-cluster, and scaffold splits exist
- scaffold split artifacts include de-warheaded scaffold keys, warhead removal evidence, algorithm/version, normalization policy, and leakage checks
- sampled visual checks support manual inspection and include status values
- an ETL quality report lists accepted records, rejected records, conflict groups, rejection reasons, source completion gates, and visual review status
- record indexes, artifact manifests, and artifact checksums pass consistency validation

## First Smoke Tests

The first implementation should pass these tests before scaling beyond a small sample:

```text
parse_10_covbinder_records
linkage_atom_mapping_check
monodentate_filter_check
edge_candidate_label_check
geometry_summary_check
protein_chemical_state_check
visual_check_export
records_jsonl_schema_check
artifact_manifest_consistency_check
source_manifest_checksum_check
dedupe_conflict_resolution_check
scaffold_key_generation_check
scaffold_split_leakage_check
```

Test expectations:

- `parse_10_covbinder_records`: parse 10 CovBinderInPDB covalent records.
- `linkage_atom_mapping_check`: every target atom and ligand attachment atom maps to an atom table.
- `monodentate_filter_check`: multi-covalent-link samples are filtered or marked outside first-version training core.
- `edge_candidate_label_check`: every accepted record has one positive covalent edge and records radius-bounded no-edge candidate semantics, including `empty_radius_window` when zero negatives are found.
- `geometry_summary_check`: bond distance, protein-side angle, and ligand-side angle can be computed.
- `protein_chemical_state_check`: records with required missing formal charge, protonation, or hydrogen state are rejected or marked unsupported; inferred states retain method and provenance.
- `visual_check_export`: at least 10 visual check artifacts can be exported.
- `records_jsonl_schema_check`: every `records.jsonl` row conforms to the CovalentComplexRecord schema.
- `artifact_manifest_consistency_check`: every record artifact path exists and checksum validation passes.
- `source_manifest_checksum_check`: every staged raw file used by ETL matches its manifest checksum.
- `dedupe_conflict_resolution_check`: duplicate records merge deterministically and unresolved conflicts are excluded with lineage.
- `scaffold_key_generation_check`: every scaffold-split record has a de-warheaded scaffold artifact or an explicit reviewed fallback reason.
- `scaffold_split_leakage_check`: train/val/test overlap for the primary de-warheaded scaffold key is zero and diagnostic overlaps are reported.
