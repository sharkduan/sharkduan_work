# V2 Interface And Contract Changes

Date: 2026-06-16
Status: proposed additive contract plan

## Compatibility Policy

V2-beta changes are additive. Existing v1 contracts remain valid. Heavy dependency objects must not leak across public package seams.

## Module Boundaries

| Module | V2 delta | Boundary rule |
| --- | --- | --- |
| `contracts` | additive v2 manifest/report dataclasses | preserve v1 facade imports |
| `data` | local real data staging, source provenance, license audit, family readiness | no training logic and no agent-managed network download by default |
| `rules` | no mainline rule authority change | rule table remains authoritative |
| `model` | PyTorch/PMDM adapters behind v1 contracts | no raw dependency objects in serialized contracts |
| `training` | real training loop and tuning manifests | no data download or ETL logic |
| `inference` | v2 sampling request/result extensions | no training loop |
| `evaluation` | beta evaluation and optional docking feasibility | no docking execution in default path |

## Proposed New Contracts

### V2EnvironmentManifest

Purpose: deterministic environment probe result for Task 37+.

Producer: v2 smoke probe. Consumer: dependency gates, training manifests, release review.

Serialization: deterministic JSON. Artifact role: `v2_environment_manifest`.

Required fields:

- `schema_version`: string.
- `contract_version`: string.
- `environment_name`: string.
- `profile`: enum `lightweight` or `heavy`.
- `platform`: string.
- `python_version`: string.
- `dependency_statuses`: object keyed by dependency name, with status enum `available`, `unavailable`, `unverified`, or `not_required`.
- `generated_at`: ISO-8601 timestamp or deterministic fixture timestamp.

Optional fields, required only when available or heavy profile requests them:

- `cuda_available`: boolean.
- `cuda_version`: string or null.
- `gpu_name`: string or null.
- `pytorch_version`: string or null.
- `rdkit_version`: string or null.
- `pmdm_status`: enum `available`, `unavailable`, `api_mismatch`, `license_unknown`, or `not_required`.
- `baseline_mode`: enum `pmdm`, `non_pmdm_baseline`, or `not_selected`.
- `dependency_lock_hash`: `sha256:<hex>` or null.

Misuse guard: `lightweight` profile must not hard-import heavyweight optional dependencies. Missing heavy dependencies are data in `dependency_statuses`, not import crashes.

Failure codes:

- `V2_ENV_PROFILE_UNSUPPORTED`
- `V2_ENV_DEPENDENCY_UNAVAILABLE`
- `V2_ENV_SOURCE_UNVERIFIED`
- `V2_ENV_PLATFORM_UNSUPPORTED`

### DependencySourceVerification

Purpose: Task 38 authority table for external dependency/API claims.

Producer: source-verification task. Consumer: v2 smoke, adapter tasks, release review.

Serialization: markdown table or deterministic JSON with equivalent fields. Artifact role: `v2_dependency_source_verification`.

Required fields:

- `dependency / package`
- `claimed API or capability`
- `official source URL`
- `version scope`
- `license status`
- `verification date`
- `status`: enum `verified`, `unverified`, `blocked`, or `not required yet`
- `owning task`

Misuse guard: unverified rows cannot be cited as implemented contracts and must remain behind adapter boundaries or future-task notes.

### SourceLicenseAudit

Purpose: source-level license and provenance decision for local real-data intake.

Implementation: `src/covalent_design/data/v2_license.py`

Producer: Task 43 license gate via `audit_v2_training_eligibility()`. Consumer: training eligibility, release review, and consistency checks against conversion outputs. Task 43 may read Task 42 converted records only to verify preserved `license_audit_ref` and provenance references; it must not run conversion or raw parsers.

Serialization: deterministic JSON. Artifact role: `source_license_audit`.

Input audit record fields:

- `source_name`: enum `CovalentInDB`, `CovPDB`, or `CovBinderInPDB`.
- `intake_mode`: enum `download` or `manual`, copied from the validated source manifest.
- `license_status`: enum `allowed`, `restricted`, `blocked`, `unknown`, or `manual_exempt`.
- `license_evidence_ref`: artifact ref, URL string, or manual exemption audit record ref. For `manual_exempt`, this points to the audit record containing `license_status: "manual_exempt"` and does not require external third-party license evidence.
- `restriction_conditions`: optional list of condition strings for `restricted`.
- `restriction_conditions_satisfied`: boolean for `restricted`.
- `block_reason`: optional text for `blocked`.

Misuse guards:

- `manual_exempt` is valid only with `intake_mode = "manual"`.
- `manual_exempt` with `intake_mode = "download"` is a structured Task 43 error.
- `manual_exempt` does not bypass manifest validation, checksum validation, parser target validation, local path provenance, source provenance, or required `license_audit_ref`.
- `unknown` and `blocked` must not enter training eligibility.
- `restricted` may enter training eligibility only when restriction conditions are recorded and satisfied, and those conditions must be preserved in downstream manifests and reports.
- Training eligibility and family readiness reports must list `manual_exempt` separately from `allowed`.

Task 43 API:

- `load_source_license_audit(path)` loads deterministic JSON audit records.
- `audit_v2_training_eligibility(staged_evidence, license_audits, converted_records=(), approved_local_data_roots=())` returns `ContractEnvelope[LicenseGateReport]`.
- `LicenseGateReport` records `sources`, five-state `status_counts`, `training_eligible_count`, and `blocked_count`.
- `LicenseGateSourceReport` records source name, intake mode, `license_audit_ref`, license status, eligibility, stable reason codes, checksum, manual path/source URL provenance, restricted conditions, and the `manual_exempt` notice when applicable.
- `license_gate_report_to_dict(report)` emits deterministic JSON-compatible output.

Structured error categories:

- staging evidence invalid or missing
- checksum/provenance/license audit reference missing
- manual path outside approved local data root
- missing audit evidence
- unsupported license status
- restricted conditions unsatisfied
- blocked or unknown license status
- `manual_exempt` on download intake
- staged evidence versus converted output mismatches for `license_audit_ref`, checksum, local path provenance, or source provenance

### V2DataIntakeManifest

Purpose: source-origin/manual staging manifest schema and validation (Task 40 IMPLEMENTED).

Implementation: `src/covalent_design/data/v2_manifests.py`

Producer: `validate_v2_data_intake_manifest()` / `v2_data_intake_manifest_from_dict()`. Consumer: conversion and license audit (Tasks 41-43).

Serialization: deterministic JSON via `serialize_v2_data_intake_manifest()` (sorted keys, compact separators, `ensure_ascii=False`). Artifact role: `v2_data_intake_manifest`.

Dataclass: `V2DataIntakeManifest` (frozen).

Required fields:

- `schema_version`: string. Code constant `SCHEMA_VERSION = "1.0.0"`.
- `contract_version`: string. Code constant `CONTRACT_VERSION = "v2-beta"`.
- `source_name`: enum `CovalentInDB`, `CovPDB`, `CovBinderInPDB`.
- `intake_mode`: enum `download`, `manual`. In v2-beta, `download` records user-provided local data that originated from a source URL; it does not authorize an agent to perform network download.
- `checksum`: 64-character lowercase SHA-256 hex digest.
- `checksum_algorithm`: enum `sha256` only.
- `parser_target`: enum `covalentin_db`, `covpdb`, `covbinder_in_pdb`. Must match source_name per `SOURCE_TO_PARSER_TARGET` mapping.
- `retrieval_date`: string.
- `license_audit_ref`: string.
- `access_notes`: string.

Optional mode-specific fields:

- `source_url`: string or null. Required when `intake_mode = download`.
- `manual_path`: string or null. Required when `intake_mode = manual`.

Validation returns `ContractEnvelope[Optional[V2DataIntakeManifest]]` with structured `V2_MANIFEST_*` error codes (owner `data`).

Error codes: `V2_MANIFEST_UNREADABLE`, `V2_MANIFEST_INVALID_JSON`, `V2_MANIFEST_ROOT_NOT_OBJECT`, `V2_MANIFEST_MISSING_REQUIRED_FIELD`, `V2_MANIFEST_FORBIDDEN_FIELD`, `V2_MANIFEST_UNKNOWN_SOURCE_NAME`, `V2_MANIFEST_UNKNOWN_INTAKE_MODE`, `V2_MANIFEST_MANUAL_PATH_REQUIRED`, `V2_MANIFEST_SOURCE_URL_REQUIRED`, `V2_MANIFEST_UNSUPPORTED_CHECKSUM_ALGORITHM`, `V2_MANIFEST_CHECKSUM_INVALID`, `V2_MANIFEST_UNKNOWN_PARSER_TARGET`, `V2_MANIFEST_SOURCE_PARSER_MISMATCH`.

Forbidden fields (rejected with `V2_MANIFEST_FORBIDDEN_FIELD`, belong to later tasks): `conversion_status`, `license_eligibility`, `license_status`, `staging_status`, `training_artifacts`, `training_eligible`, `training_split`.

Scope exclusion: Task 40 does not download, stage, convert, inspect raw data, decide license eligibility, produce training artifacts, or import heavy dependencies. No network access during validation.

Misuse guard: missing checksum fails validation with `V2_MANIFEST_MISSING_REQUIRED_FIELD`. Mismatched source/parser fails with `V2_MANIFEST_SOURCE_PARSER_MISMATCH`.

Verification (2026-06-16): `python -m pytest tests/data/test_v2_manifests.py -q` — 29 passed.

### V2Conversion

Purpose: convert Task 41 validated local staged inputs (checksum-verified manual files) to v1-compatible `SourceIngestRecord` records (Task 42 IMPLEMENTED).

Implementation: `src/covalent_design/data/v2_conversion.py`

Producer: `convert_staged_source()` / `convert_staged_manifest()`. Consumer: v1 ETL pipelines (`normalize_linkages`, `normalize_with_identity_resolution`), Task 43 license gate.

Public API:

- `convert_staged_source(staging_envelope: ContractEnvelope[V2StagingSummary], *, reverify_checksum: bool = True) → ContractEnvelope[tuple[SourceIngestRecord, ...]]`
- `convert_staged_manifest(manifest_path: Path, *, reverify_checksum: bool = True) → ContractEnvelope[tuple[SourceIngestRecord, ...]]`

Conversion contract:

- Only `status == "checksum_verified"` (manual local file) is convertible.
- `pending_download` returns `V2_CONVERSION_PENDING_DOWNLOAD` — no placeholder records.
- Failed staging envelope returns `V2_CONVERSION_STAGING_FAILED`.
- Forged or non-Task-41 staging envelopes return `V2_CONVERSION_INVALID_STAGING_EVIDENCE`.
- Optional checksum re-verification (`reverify_checksum=True` by default): re-reads the file and recomputes SHA-256; mismatch → `V2_CONVERSION_CHECKSUM_MISMATCH`.
- Zero network access enforced by tests.
- No filesystem artifacts written during conversion (purely in-memory).

Supported parser targets: `covalentin_db` only (Task 42 scope). `covpdb` and `covbinder_in_pdb` return `V2_CONVERSION_UNSUPPORTED_PARSER`.

TSV parser required columns: `pdb_id`, `uniprot_id`, `residue`, `residue_number`, `ligand`, `ligand_name`, `bond_type`, `warhead_type`.

Output: `ContractEnvelope[tuple[SourceIngestRecord, ...]]` where each record carries:

- `source_database`, `source_version`, `source_record_id`, `row_index`
- `raw_file_path`, `raw_manifest_file`, `raw_file_sha256` — provenance
- `lineage` (dict) — includes `license_audit_ref` and `source_url` when available
- `metadata` (dict) — includes `pdb_id`, `license_audit_ref`, `source_url`
- `protein` (dict), `ligand` (dict), `linkage` (dict)
- `source_lineage` (`SourceRecordLineage`)
- `target_atom_identity` (`ProteinAtomIdentity`), `ligand_atom_identity` (`LigandAtomIdentity`)
- `artifacts` is always empty `()` — artifact refs are Task 43+ scope

Error codes (all `owner = "data"`, `V2_CONVERSION_*` prefix):

- `V2_CONVERSION_STAGING_FAILED`
- `V2_CONVERSION_INVALID_STAGING_EVIDENCE`
- `V2_CONVERSION_PAYLOAD_MISSING`
- `V2_CONVERSION_PENDING_DOWNLOAD`
- `V2_CONVERSION_UNEXPECTED_STATUS`
- `V2_CONVERSION_MANUAL_PATH_MISSING`
- `V2_CONVERSION_FILE_NOT_FOUND`
- `V2_CONVERSION_UNSUPPORTED_PARSER`
- `V2_CONVERSION_CHECKSUM_MISMATCH`
- `V2_CONVERSION_FILE_UNREADABLE`
- `V2_CONVERSION_MISSING_COLUMNS`
- `V2_CONVERSION_ROW_PARSE_ERROR`

Forbidden output fields (belong to Task 43+): `training_eligible`, `training_split`, `license_eligibility`, `license_status`, `split_assignment`, `model_artifacts`, `inference_artifacts`.

Scope exclusion: Task 42 does not access network, download data, decide license eligibility, decide training eligibility, produce training artifacts, produce family readiness reports, produce split assignments, or write filesystem artifacts. Task 43 owns training eligibility.

Deterministic: same staging input produces identical `SourceIngestRecord` tuple. Output is JSON-serializable via `dataclasses.asdict()`.

Verification (2026-06-16): `python -m pytest tests/data/test_v2_conversion.py -q`.

### FamilyReadinessReport

- `family`
- `accepted_count`
- `blocked_count`
- `split_counts`
- `visual_blocked_count`
- `chemical_state_unavailable_count`
- `scaffold_coverage`
- `status`
- `reason`

### V2TrainingRunManifest

- `run_id`
- `environment_manifest_hash`
- `data_manifest_hashes`
- `family_readiness_hash`
- `training_config_hash`
- `checkpoint_refs`
- `baseline_mode`
- `metrics`

### V2SamplingEvaluationReport

- `checkpoint_hash`
- `split_name`
- `family_filter`
- `sample_count`
- `valid_count`
- `invalid_count`
- `invalid_reasons`
- `rdkit_validity_summary`
- `docking_feasibility_ref`

## Artifact Schemas

V2 artifacts should use deterministic JSON/YAML with:

- schema version,
- contract version,
- role,
- exact-byte checksum,
- source references,
- dependency/environment references where relevant.

## Chemistry Interfaces

### RDKit Molecule Normalization Report

Purpose: heavy-profile molecule parsing and normalization adapter for Task 44.

Implementation: `src/covalent_design/chem/rdkit_normalize.py`

Public API:

- `normalize_molecule(text, input_format="smiles") -> MoleculeNormalizationResult`
- `result_to_dict(result) -> dict[str, object]`

Supported input formats:

- `smiles`
- `molblock`

Output boundary:

- `MoleculeNormalizationResult` is project-owned serializable data.
- The public result includes status, input format, RDKit availability, canonical normalized SMILES when available, atom/bond counts, formal charge, sanitize status, valence problem count, diagnostics, and structured error fields.
- Raw RDKit `Mol`, `Atom`, `Bond`, or chemistry problem objects must not cross the package seam.

Environment behavior:

- Module import is lightweight-safe and must not hard-import RDKit.
- When RDKit is unavailable, normalization returns `status = "unavailable"` with `RDKIT_NORMALIZE_RDKIT_UNAVAILABLE`.
- In a heavy environment with RDKit available, the adapter performs real RDKit parsing, sanitization, canonical SMILES generation, and valence-related diagnostics.

Structured failure codes:

- `RDKIT_NORMALIZE_RDKIT_UNAVAILABLE`
- `RDKIT_NORMALIZE_EMPTY_INPUT`
- `RDKIT_NORMALIZE_UNSUPPORTED_FORMAT`
- `RDKIT_NORMALIZE_PARSE_FAILED`
- `RDKIT_NORMALIZE_SANITIZE_FAILED`

Scope exclusions:

- Task 44 does not implement scaffold keys, descriptors, drug-likeness, mmCIF writing, PyTorch tensor conversion, model forward, training, inference, evaluation, or real-data directory access.

## CLI Boundaries

Future v2 CLIs should be thin wrappers around typed Python interfaces. Planned families:

- environment smoke,
- local real-data staging,
- license audit,
- real ETL orchestration,
- RDKit chemistry reports,
- training smoke/full run,
- tuning,
- sampling,
- evaluation.

Canonical functional entrypoints live under package modules, for example `python -m covalent_design.data.cli.v2_stage_source` or `python -m covalent_design.training.cli.v2_train`. Developer scripts under `scripts/` are allowed only for environment probes or thin local helpers. The known exception is `scripts/v2_smoke_check.py`, which remains the Task 37 environment smoke helper because it must run before package-level heavy adapters exist.

When a script and a package CLI both exist, docs must name the package CLI as the public interface and describe the script as a wrapper.

## Error Semantics

V2 errors should use structured codes and never silently continue on:

- dependency unavailable,
- source license unknown or blocked,
- local data checksum mismatch,
- schema normalization failure,
- family readiness blocked,
- PMDM unavailable without explicit fallback,
- denominator drift,
- label leakage risk.
