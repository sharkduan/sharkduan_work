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
- `dependency_statuses`: object keyed by dependency name, with status enum `available`, `unavailable`, `not_checked`, or `failed`.
- `generated_at`: ISO-8601 timestamp or deterministic fixture timestamp.

Optional fields, required only when available or heavy profile requests them:

- `cuda_available`: boolean.
- `cuda_version`: string or null.
- `gpu_name`: string or null.
- `pytorch_version`: string or null.
- `rdkit_version`: string or null.
- `rdkit_version`: string or null.
- `pmdm_status`: enum `available`, `unavailable`, `api_mismatch`, `license_unknown`, or `not_required`.
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
- `status`: enum `verified`, `unverified`, `blocked`, or
- `verification date`
- `status`: enum `verified`, `unverified`, `blocked`, or `not required yet`
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

### V2TrainingDatasetIndex

Purpose: Task 49 split-specific training eligibility index for V2-beta.

Implementation: `src/covalent_design/training/v2_dataset.py`

Producer: `prepare_v2_dataset(records_path, split_index_path, split_name, *, visual_check_index_path, quality_report_path, family_readiness_report_path, license_gate_report_path, policy=None)`. Consumer: Task 50 training loop planning and later training manifests.

Serialization: deterministic JSON-compatible dataclasses. The API returns `ContractEnvelope[V2TrainingDatasetIndex]` and builds exactly one split per call.

`V2TrainingRecordEntry` preserves `record_id`, residue-reaction family, quality tier, visual status, license status, family readiness status, fallback/manual review metadata, source name, intake mode, and artifact refs.

`V2ExcludedRecord` preserves `record_id`, deterministic `primary_reason`, all applicable reasons, residue-reaction family, quality tier, visual status, license status, family readiness status, split assignment, source name, intake mode, and source license `reason_codes` as `license_reason_codes`.

Task 49 eligibility rules:

- `manual_exempt` remains distinct from `allowed`.
- `manual_exempt` is eligible only when record metadata and license report both prove manual intake and the license report has `training_eligible=true`.
- `manual_exempt` with `training_eligible=false` is excluded with `excluded_manual_exempt_audit_failed`.
- Task 49 performs minimum artifact role presence validation and excludes records with no usable artifact roles as `excluded_missing_artifact_roles`.
- Task 49 does not validate artifact path existence, readability, bytes, or checksums; Task 50 must fail before tensor construction on those checks.
- Task 49 does not compute masks, losses, model forward passes, checkpoints, or training artifacts.

Task 50 boundary: V2 training must consume the Task 49 `V2TrainingDatasetIndex` or an equivalent validated envelope. It must not bypass Task 49 by calling the v1 `prepare_dataset()` source directly.
### V2TrainLoopConfig And V2TrainingSummary

Purpose: Task 50 CPU/GPU training smoke-loop boundary for V2-beta.

Implementation: `src/covalent_design/training/v2_train_loop.py` and CLI `python -m covalent_design.training.cli.v2_train --config <config.yml>`.

Producer: `run_v2_train(config)` accepts either a config path or mapping and returns `ContractEnvelope[V2TrainingSummary]`. The public `covalent_design.training` facade preserves `run_v2_train`, `V2TrainLoopConfig`, `V2TrainingSummary`, and `v2_training_summary_to_dict` as lazy exports to avoid package import side effects.

Input contract: the config must provide Task 49 gate inputs (`records_path`, `split_index_path`, `visual_check_index_path`, `quality_report_path`, `family_readiness_report_path`, `license_gate_report_path`, and `split_name`) plus `device` and explicit `model_mode` (`pmdm` or `non_pmdm_baseline`). Task 50 does not accept finalized records alone as training eligibility proof.

Preflight contract: after Task 49 builds `V2TrainingDatasetIndex`, Task 50 validates each eligible artifact reference for path existence, readability, byte count, and SHA-256 checksum before tensor construction. Structured error codes are `V2_TRAIN_ARTIFACT_MISSING`, `V2_TRAIN_ARTIFACT_UNREADABLE`, `V2_TRAIN_ARTIFACT_BYTE_MISMATCH`, and `V2_TRAIN_ARTIFACT_CHECKSUM_MISMATCH`.

Model-path contract: `model_mode=pmdm` checks the PMDM availability boundary and does not auto-switch to baseline when PMDM is blocked. `model_mode=non_pmdm_baseline` records `baseline_mode="non_pmdm_baseline"`, `is_pmdm=false`, and the baseline warning. CPU smoke does not require CUDA. GPU config requires CUDA and reports `V2_TRAIN_CUDA_UNAVAILABLE` if unavailable.

Summary contract: `V2TrainingSummary` is deterministic JSON and includes `dataset`, `artifact_preflight`, `model_path`, `phases`, `loss_report`, `denominator_status`, `warnings`, and empty `publication_claims`. Task 50 does not write Task 51 checkpoint manifests, model weights, sampling outputs, inference artifacts, or evaluation artifacts.
### V2SamplingRequest And V2SamplingResult

Purpose: Task 53 package-interface contract for beta sampling requests and result summaries. Task 53 defines schema, validation, deterministic serialization, and failure taxonomy only; it does not execute sampling or write artifacts.

Implementation: `src/covalent_design/inference/v2_sampling.py`

Producer: request builders or later sampling CLIs. Consumer: Task 54 deterministic sampling smoke, Task 55 evaluation, and release reviews.

Serialization: deterministic JSON with sorted keys and compact separators. Hash helpers return `sha256:<hex>`.

`V2SamplingRequest` required contract fields:

- `request_id`
- `checkpoint_ref`
- `checkpoint_manifest_ref`
- `environment_manifest_ref`
- exactly one selector: `split_name` (`train`, `val`, `test`) or explicit `record_ids`
- `random_seed`
- `sample_count`
- `output_root`
- `baseline_mode`: `pmdm` or `non_pmdm_baseline`
- `generation_mode`: `reactive_site`

Optional request fields:

- `family_filter`
- `max_retries`
- `retry_on_categories`

Misuse guards:

- `reference_ligand` generation is rejected; Task 53 remains reactive-site only.
- selector absence and selector conflict return distinct structured errors.
- retry policy categories must remain within the existing sampling system failure vocabulary and must not include terminal `retry_exhausted`.
- `output_root` is not created by Task 53.

`V2SamplingResult` required contract fields:

- checkpoint, checkpoint-manifest, and environment-manifest refs
- baseline mode, selector metadata, random seed
- requested, attempted, valid, invalid, and sampling-system-failure counts
- invalid decode diagnostics
- sampling system failures
- export, docking, and evaluation statuses

Count conservation:

```text
valid_sample_count + invalid_sample_count == attempted_sample_count
attempted_sample_count + sampling_system_failure_count == requested_sample_count
```

Failure taxonomy is explicit and non-interchangeable:

- request validation failure
- sampling system failure
- invalid generated sample
- export failure
- docking not run
- evaluation artifact corruption

Task boundary: Task 53 performs no model forward, true sampling, result export, mmCIF writing, docking, evaluation, real-data-root access, or heavyweight dependency import. Task 54 consumes this contract to prove deterministic sampling smoke execution.

Task 54 fixture runner: `run_deterministic_fixture_sampling(request, fixture_records, fixture_split_index=None) -> V2SamplingResult` is a lightweight, in-memory smoke helper. It accepts already-loaded fixture records and an optional fixture split index, applies split or record-id selectors plus `family_filter`, produces deterministic valid/invalid/system-failure accounting from the request seed, and returns a `V2SamplingResult`. It does not read `D:\codex_work\data`, does not read or write `data/v2`, does not create `output_root`, and does not implement Task 55 evaluation, Task 56 docking, mmCIF export, or real model sampling.

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

Verification (2026-06-16): `python -m pytest tests/data/test_v2_manifests.py -q` - 29 passed.

### V2Conversion

Purpose: convert Task 41 validated local staged inputs (checksum-verified manual files) to v1-compatible `SourceIngestRecord` records (Task 42 IMPLEMENTED).

Implementation: `src/covalent_design/data/v2_conversion.py`

Producer: `convert_staged_source()` / `convert_staged_manifest()`. Consumer: v1 ETL pipelines (`normalize_linkages`, `normalize_with_identity_resolution`), Task 43 license gate.

Public API:

- `convert_staged_source(staging_envelope: ContractEnvelope[V2StagingSummary], *, reverify_checksum: bool = True) ->ContractEnvelope[tuple[SourceIngestRecord, ...]]`
- `convert_staged_manifest(manifest_path: Path, *, reverify_checksum: bool = True) ->ContractEnvelope[tuple[SourceIngestRecord, ...]]`

Conversion contract:

- Only `status == "checksum_verified"` (manual local file) is convertible.
- `pending_download` returns `V2_CONVERSION_PENDING_DOWNLOAD` - no placeholder records.
- Failed staging envelope returns `V2_CONVERSION_STAGING_FAILED`.
- Forged or non-Task-41 staging envelopes return `V2_CONVERSION_INVALID_STAGING_EVIDENCE`.
- Optional checksum re-verification (`reverify_checksum=True` by default): re-reads the file and recomputes SHA-256; mismatch -> `V2_CONVERSION_CHECKSUM_MISMATCH`.
- Zero network access enforced by tests.
- No filesystem artifacts written during conversion (purely in-memory).

Supported parser targets: `covalentin_db`, `covpdb`, and `covbinder_in_pdb`.

Accepted input shapes:

- CovalentInDB real CSV (`Covalent_Complex_Records.csv`).
- CovBinderInPDB real CSV (`CovBinderInPDB_2022Q4_AllRecords.csv`).
- CovPDB extracted local PDB directory, discovered from the checksum-verified archive manifest path.
- v1-compatible TSV bridge schemas for all three parser targets.
- Legacy 8-column synthetic covalentin_db TSV fixtures.

`v2_run_real_etl` is the artifact-producing orchestration layer. It writes
`data/v2/processed/v2_real_etl_manifest.json` plus per-source local JSONL
records only for sources that pass manifest validation, checksum staging,
conversion, and license/provenance gate. Failed conversion payloads are not
fed to the license gate or processed output.

Output: `ContractEnvelope[tuple[SourceIngestRecord, ...]]` where each record carries:

- `source_database`, `source_version`, `source_record_id`, `row_index`
- `raw_file_path`, `raw_manifest_file`, `raw_file_sha256` -provenance
- `lineage` (dict) -includes `license_audit_ref` and `source_url` when available
- `metadata` (dict) -includes `pdb_id`, `license_audit_ref`, `source_url`
- `protein` (dict), `ligand` (dict), `linkage` (dict)
- `source_lineage` (`SourceRecordLineage`)
- `target_atom_identity` (`ProteinAtomIdentity`), `ligand_atom_identity` (`LigandAtomIdentity`)
- `artifacts` is always empty `()` -artifact refs are Task 43+ scope

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

### V2CheckpointExperimentManifest

Purpose: Task 51 manifest binding environment, dependency lock provenance, Task 49 data eligibility, family readiness, Task 50 training summary, and checkpoint references.

Implementation: `src/covalent_design/training/v2_manifests.py`

Public API:

- `build_v2_checkpoint_experiment_manifest(...) -> ContractEnvelope[V2CheckpointExperimentManifest]`
- `v2_checkpoint_experiment_manifest_to_dict(manifest) -> dict[str, object]`
- `serialize_v2_checkpoint_experiment_manifest(manifest) -> str`
- `hash_v2_checkpoint_experiment_manifest(manifest) -> str`
- `validate_v2_checkpoint_experiment_manifest(manifest) -> ValidationReceipt`
- `v2_hash_bytes`, `v2_hash_file`, and `v2_hash_object`

Required fields:

- `manifest_id`
- `run_id`
- `environment_hash`
- `dependency_lock`
- `data_hashes`
- `dataset_index_hash`
- `family_readiness_hash`
- `training_config_hash`
- `training_summary_hash`
- `training_summary_ref`
- `checkpoint_refs`
- `baseline_mode`
- `is_pmdm`
- `pmdm_status`
- `model_contract_version`

`data_hashes` must include `records_jsonl`, `split_index`, `quality_report`, `visual_check_index`, and `license_gate_report`. Every hash uses `sha256:<64 lowercase hex>`.

`dependency_lock` is a `V2DependencyLockProvenance` object with `status`, `lock_hash`, `uri`, `format`, and `reason`. `status="available"` requires a valid lock hash. `status="not_available"` records explicit provenance that no verified lock file exists and must not be treated as a verified lock hash. PMDM manifests require an available lock hash.

`checkpoint_refs` are `V2CheckpointRef` entries with checkpoint id, metadata URI, step, optional metadata hash, format, and selected flag. They are references only; Task 51 does not create or embed checkpoint payloads.

Baseline rules:

- `baseline_mode="non_pmdm_baseline"` requires `is_pmdm=false`.
- `baseline_mode="pmdm"` requires `is_pmdm=true`.
- unavailable, blocked, or license-unknown PMDM status cannot be recorded as a successful PMDM checkpoint manifest.

Validation returns structured `V2_MANIFEST_*` errors for missing environment, dependency lock provenance, data hashes, dataset index hash, family readiness hash, training config hash, training summary hash/ref, checkpoint refs, invalid hash format, PMDM/baseline mismatch, and unavailable PMDM success.

Serialization is deterministic JSON with sorted keys and compact separators. The module is lightweight-safe and has no PMDM, PocketFlow, RDKit, or PyTorch hard import.

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

### RDKit Descriptor Computation Report

Purpose: heavy-profile molecular descriptor computation and drug-likeness diagnostics for Task 45.

Implementation: `src/covalent_design/chem/rdkit_descriptors.py`

Public API:

- `compute_descriptors(text, input_format="smiles") -> DescriptorResult`
- `descriptor_result_to_dict(result) -> dict[str, object]`

Supported input formats:

- `smiles`
- `molblock`

Output boundary:

- `DescriptorResult` is project-owned serializable data (frozen dataclass).
- The public result includes `status`, `input_format`, `rdkit_available`, `descriptors` (mapping of 11 public-facing descriptor keys to Python built-in values), `diagnostics`, `error_code`, `error_message`.
- Raw RDKit `Mol`, `Atom`, `Bond`, or descriptor objects (e.g. numpy scalars) must not cross the package seam.
- Numpy scalars from RDKit internals are coerced to Python `float` before exposure.

Public descriptor keys (via `_DESCRIPTOR_KEY_MAP`):

- `molecular_weight`, `logp`, `num_h_acceptors`, `num_h_donors`, `num_rotatable_bonds`, `tpsa`, `num_rings`, `num_heavy_atoms`, `fraction_csp3`, `num_aromatic_rings`, `molar_refractivity`.

Descriptor computation strategy:

- Primary path: `rdkit.Chem.Descriptors.CalcMolDescriptors`.
- Manual fallback: individual `rdkit.Chem.Descriptors` functions and `rdkit.Chem.Crippen` when the bulk API is unavailable.
- Descriptor keys that cannot be computed are silently omitted from the output dict (graceful degradation).

Drug-likeness diagnostics (diagnostic-only, not a hard gate):

- Lipinski Rule of 5: violations counted (MW>500, LogP>5, HBD>5, HBA>10); field `passes` reports overall compliance without gating `status`.
- QED: computed via `rdkit.Chem.QED.qed()` when available; reported as `None` when computation fails.
- Both diagnostics appear in the `diagnostics` tuple with `category: "druglikeness"`.
- Result `status` remains `"ok"` even when molecules fail drug-likeness thresholds.

Environment behavior:

- Module import is lightweight-safe -`importlib.import_module` used for RDKit inside function bodies, no hard RDKit import at module level.
- When RDKit is unavailable: `status = "unavailable"`, `error_code = "DESCRIPTOR_RDKIT_UNAVAILABLE"`.
- When RDKit is available: real `CalcMolDescriptors` computation plus drug-likeness diagnostics.

Structured failure codes:

- `DESCRIPTOR_RDKIT_UNAVAILABLE`
- `DESCRIPTOR_EMPTY_INPUT`
- `DESCRIPTOR_UNSUPPORTED_FORMAT`
- `DESCRIPTOR_PARSE_FAILED`

Scope exclusions:

- Task 45 does not implement mmCIF writing, PyTorch tensor conversion, docking, model forward, training, inference, evaluation, or real-data directory access.
- Drug-likeness is diagnostic-only; it is not a hard beta gate.

### RDKit Scaffold Derivation Report

Purpose: heavy-profile Bemis-Murcko scaffold derivation for Task 45.

Implementation: `src/covalent_design/chem/scaffolds.py`

Public API:

- `derive_scaffold(text, input_format="smiles") -> ScaffoldResult`
- `scaffold_result_to_dict(result) -> dict[str, object]`

Supported input formats:

- `smiles`
- `molblock`

Output boundary:

- `ScaffoldResult` is project-owned serializable data (frozen dataclass).
- The public result includes `status`, `input_format`, `rdkit_available`, `scaffold_smiles` (canonical SMILES of the Bemis-Murcko scaffold or acyclic fallback), `atom_count`, `scaffold_type` (`"bemis_murcko"` or `"acyclic_fallback"`), `diagnostics`, `error_code`, `error_message`.
- Raw RDKit `Mol`, `Atom`, or `Bond` objects must not cross the package seam -scaffold molecule is converted to canonical SMILES before the API boundary.

Scaffold derivation strategy:

- Uses official `rdkit.Chem.Scaffolds.MurckoScaffold.GetScaffoldForMol` API.
- Acyclic molecules that produce an empty Murcko scaffold (0 atoms in scaffold) fall back to the canonical molecule SMILES with `scaffold_type: "acyclic_fallback"`.

Environment behavior:

- Module import is lightweight-safe -`importlib.import_module` used for RDKit inside function bodies, no hard RDKit import at module level.
- When RDKit is unavailable: `status = "unavailable"`, `error_code = "SCAFFOLD_RDKIT_UNAVAILABLE"`.
- When RDKit is available: real Bemis-Murcko derivation with acyclic fallback.

Structured failure codes:

- `SCAFFOLD_RDKIT_UNAVAILABLE`
- `SCAFFOLD_EMPTY_INPUT`
- `SCAFFOLD_UNSUPPORTED_FORMAT`
- `SCAFFOLD_PARSE_FAILED`

Scope exclusions:

- Task 45 scaffold derivation is a chemistry diagnostic; it does not gate training eligibility, family readiness, or any downstream pipeline step.
- Task 45 does not implement mmCIF writing, PyTorch tensor conversion, docking, model forward, training, inference, evaluation, or real-data directory access.

### Chemistry Module Public Surface (Task 45 Updated)

Task 45 updates `src/covalent_design/chem/__init__.py` to export all three chemistry adapters from a single public surface:

- `normalize_molecule`, `MoleculeNormalizationResult`, `result_to_dict` (Task 44)
- `compute_descriptors`, `DescriptorResult`, `descriptor_result_to_dict` (Task 45)
- `derive_scaffold`, `ScaffoldResult`, `scaffold_result_to_dict` (Task 45)

All exports are lightweight-safe -importing `covalent_design.chem` does not trigger an RDKit import.

### PyTorch Tensor Backend Boundary (Task 46)

Purpose: optional heavy-profile conversion from `ModelBatch` metadata to an internal PyTorch tensor runtime object.

Public API:

- `covalent_design.model.torch_backend.check_torch_available() -> TorchBackendStatus`
- `covalent_design.model.torch_backend.convert_batch_to_torch(batch, device="cpu") -> ContractEnvelope[Optional[TorchTensorBatch]]`
- `torch_tensor_spec_from_batch(batch, device="cpu") -> TorchTensorSpec`
- `torch_tensor_spec_to_dict(spec) -> dict`
- `torch_backend_status_to_dict(status) -> dict`

Boundary rules:

- Importing `covalent_design.model.torch_backend` does not import PyTorch.
- PyTorch is loaded only inside function bodies with `importlib.import_module("torch")`.
- Missing PyTorch is represented as `TORCH_BACKEND_UNAVAILABLE` in a structured status or failed `ContractEnvelope`; public APIs do not expose raw `ImportError`.
- Existing public contract objects remain JSON-serializable and do not contain `torch.Tensor`.
- `TorchTensorBatch` may contain real `torch.Tensor` values, but it is an internal runtime object only.
- Public serialization uses `TorchTensorSpec`, which records deterministic shape, dtype, device, record identity, and coordinate-frame metadata.
- CPU is the default Task 46 device. CUDA/GPU execution is not required for Task 46.

Structured error codes:

- `TORCH_BACKEND_UNAVAILABLE`
- `TORCH_BACKEND_EMPTY_BATCH`
- `TORCH_BACKEND_TENSOR_METADATA_MISSING`
- `TORCH_BACKEND_SHAPE_MISMATCH`
- `TORCH_BACKEND_DTYPE_UNSUPPORTED`
- `TORCH_BACKEND_DEVICE_UNAVAILABLE`
- `TORCH_BACKEND_CONVERSION_FAILED`

Scope exclusions:

- Task 46 does not import PMDM or PocketFlow.
- Task 46 does not read `D:\codex_work\data`.
- Task 46 does not implement training, sampling, inference, evaluation, Task 47, Task 48, or Task 49.
- When PyTorch is unavailable, docs and reports must not claim real PyTorch-backed conversion has executed.
### PMDM Real Adapter Boundary (Task 47)

Purpose: project-owned smoke boundary for the real PMDM adapter while PMDM remains blocked by `license_unknown`.

Public API:

- `covalent_design.model.pmdm_real_adapter.check_pmdm_available() -> PmdmBackendStatus`
- `pmdm_backend_status_to_dict(status) -> dict`
- `pmdm_output_spec_from_config(batch, config) -> PmdmOutputSpec`
- `pmdm_output_spec_to_dict(spec) -> dict`
- `validate_real_pmdm_outputs(pmdm_outputs, *, batch, config) -> None`
- `forward_pmdm_real(*, batch, config, timestep=0.5) -> ContractEnvelope[Optional[ModelForwardOutput]]`

Required PMDM output keys are exactly: `ligand_atom_features`, `protein_atom_features`, `ligand_coords_denoised`, `position_loss`, `atom_type_loss`, `timestep`, and `num_atom`. Optional keys are exactly `ligand_pair_features` and `protein_ligand_pair_features`; they are required only when the corresponding `ModelConfig` feature dimensions are positive, and rejected when disabled.

PMDM is currently unavailable for execution. `check_pmdm_available()` returns structured status with `status: unavailable`, `license_status: unknown`, `reason: license_unknown`, and `import_attempted: false`. The module does not import, load, or execute PMDM/PocketFlow while PMDM is blocked.

No-silent-fallback rule: a PMDM-mode call that reaches `forward_pmdm_real()` returns a failed model `ContractEnvelope` with `PMDM_REAL_LICENSE_BLOCKED`; it must not switch to `non_pmdm_baseline`. Task 48 owns any explicitly selected baseline path.

Structured error codes include `PMDM_REAL_LICENSE_BLOCKED`, `PMDM_REAL_UNAVAILABLE`, `PMDM_REAL_API_MISMATCH`, `PMDM_REAL_MISSING_REQUIRED_KEY`, `PMDM_REAL_MISSING_OPTIONAL_KEY`, `PMDM_REAL_UNEXPECTED_OPTIONAL_KEY`, `PMDM_REAL_UNKNOWN_KEY`, `PMDM_REAL_SHAPE_MISMATCH`, and `PMDM_REAL_UNSERIALIZABLE_PAYLOAD`.

Boundary rules:

- Public status/spec payloads are JSON-serializable project-owned data.
- Raw PMDM, PocketFlow, PyTorch, RDKit, or PyG objects must not cross this boundary.
- Task 47 does not implement Task 48 baseline fallback, Task 49 training data, training loops, sampling, inference, evaluation, or real-data-root access.
### Non-PMDM Baseline Boundary (Task 48)

Purpose: explicit, labeled non-PMDM model forward path for when PMDM is unavailable or deliberately bypassed. This is an engineering smoke fallback, not the preferred scientific path and not PMDM.

Implementation: `src/covalent_design/model/non_pmdm_baseline.py`

Public API:

- `check_baseline_available() -> NonPmdmBaselineStatus`
- `baseline_status_to_dict(status) -> dict`
- `check_baseline_mode(requested_mode: str) -> BaselineModeSelection`
- `baseline_mode_selection_to_dict(selection) -> dict`
- `forward_non_pmdm_baseline(*, batch, config, timestep=0.5, baseline_mode="not_selected") -> ContractEnvelope[Optional[ModelForwardOutput]]`
- `baseline_envelope_to_dict(envelope) -> dict`
- `validate_baseline_pmdm_outputs(pmdm_outputs, *, batch, config) -> None`

Explicit selection rule: `forward_non_pmdm_baseline()` defaults to `baseline_mode="not_selected"` and returns `BASELINE_MODE_NOT_SELECTED`. It succeeds only when the caller explicitly passes `baseline_mode="non_pmdm_baseline"`. Passing `baseline_mode="pmdm"` returns `BASELINE_MODE_MISMATCH`; unknown modes return `BASELINE_MODE_UNSUPPORTED`.

No-silent-fallback rule: PMDM-mode calls remain owned by Task 47 `forward_pmdm_real()`, which returns `PMDM_REAL_LICENSE_BLOCKED` while PMDM is license-blocked. Task 47 never switches to `non_pmdm_baseline`, and Task 48 never self-activates from PMDM unavailability. A future consumer must choose the baseline path explicitly.

Status/report schema: `NonPmdmBaselineStatus` and successful baseline envelopes carry `baseline_mode: "non_pmdm_baseline"`, `is_pmdm: false`, `pmdm_import_attempted: false`, and machine-readable warning text `baseline is not PMDM; this is a smoke-only path`.

Output contract: the baseline returns `ContractEnvelope[ModelForwardOutput]`. The payload contains the seven required PMDM-compatible output keys (`ligand_atom_features`, `protein_atom_features`, `ligand_coords_denoised`, `position_loss`, `atom_type_loss`, `timestep`, `num_atom`) and the same optional-key policy as the PMDM smoke adapter: `ligand_pair_features` and `protein_ligand_pair_features` appear only when their `ModelConfig` feature dimensions are positive. Values are deterministic project-owned Python data, not real PMDM computation.

Serialization boundary: public status, selection, and envelope summaries are JSON-serializable project-owned data. Raw PMDM, PocketFlow, PyTorch tensor, RDKit, or PyG objects must not cross this boundary.

Structured error/warning codes include `BASELINE_MODE_NOT_SELECTED`, `BASELINE_MODE_MISMATCH`, `BASELINE_MODE_UNSUPPORTED`, `BASELINE_BACKEND_UNAVAILABLE`, `BASELINE_CONFIG_INVALID`, and `BASELINE_NOT_PMDM_WARNING`.

Scope exclusion: Task 48 does not implement Task 49 training dataset eligibility, training loop, losses, optimizer, checkpointing, sampling, inference, evaluation, or real-data-root access.

### V2 Tiny Tuning Protocol (Task 52)

Purpose: deterministic, budget-controlled hyperparameter protocol over the Task
50 training boundary.

Implementation:

- `src/covalent_design/training/v2_tuning.py`
- CLI: `python -m covalent_design.training.cli.v2_tune --config configs/v2_tiny_sweep.yml`

Public API:

- `run_v2_tune(config) -> ContractEnvelope[V2TuningSummary]`
- `v2_trial_result_to_dict(result) -> dict`
- `v2_tuning_summary_to_dict(summary) -> dict`

Config contract: `V2TinySweepConfig` requires explicit `trial_count`,
`runtime_budget_seconds`, `seeds`, `selection_metric`, `selection_mode`, device
and model-mode selection, and the Task 49 gate input references consumed by Task
50. The lightweight config uses comma-separated seeds because the project YAML
loader intentionally supports a small scalar subset. `runtime_budget_seconds` is
recorded and validated as the smoke protocol budget; Task 52 does not implement a
wall-clock timeout. Seeds are part of deterministic trial identity and hashes; Task
50 smoke summaries are deterministic and do not currently consume stochastic state.

Trial contract: each `V2TrialResult` records a deterministic `trial_id`, ordinal
index, seed, status, model mode, `config_hash`, `result_hash`, metric values,
selected-checkpoint metadata, diagnostics, and structured error fields when a
trial fails.

Summary contract: `V2TuningSummary` records the config path, frozen selection
metric/mode, explicit budget, deterministic trial ordering, all trial results,
successful/failed counts, selected trial, `sweep_config_hash`,
`sweep_result_hash`, and a machine-readable selected checkpoint reference. Failed
trials remain in the report and cannot be promoted as the selected checkpoint.

Boundary rules:

- Task 52 calls the Task 50 training-loop API for each trial.
- Task 52 does not read the real-data root.
- Task 52 does not create binary checkpoint payloads.
- Task 52 does not implement sampling, inference, evaluation, loss redesign, or
  full training orchestration.
### V2 Full Beta Training Harness (Task 52.5)

Purpose: numbered full-beta training harness that binds Task 49 eligibility, Task 50 training summary, Task 51 manifest provenance, and Task 52 tuning evidence before Checkpoint V2-E.

Implementation:

- `src/covalent_design/training/v2_full_beta.py`
- CLI: `python -m covalent_design.training.cli.v2_full_beta_train --config configs/v2_full_beta_train.yml`

Public API:

- `run_v2_full_beta_train(config) -> ContractEnvelope[V2FullBetaSummary]`
- `v2_full_beta_summary_to_dict(summary) -> dict`

Config contract: `V2FullBetaConfig` requires `execution_mode`, `runtime_budget_seconds`, `seed`, `device`, `model_mode`, split name, the same Task 49 gate input paths consumed by Task 50, `checkpoint_policy`, and `checkpoint_selection_metric`. The only v1 checkpoint policy is `manifest_ref_only`. The default config uses `execution_mode="fixture"` and does not read raw real-data roots.

Summary contract: `V2FullBetaSummary` records success/error state, execution mode, device, model mode, checkpoint policy, selection metric, selected checkpoint reference, selection justification, nested Task 50 training summary, nested Task 52 tuning summary, Task 51 manifest validation result, output-write status, real-data-access status, config, diagnostics, warnings, and a deterministic `summary_hash`.

Boundary rules:

- Task 52.5 composes Tasks 49-52 and does not rebuild their internal validation logic.
- Heavy/manual execution requires explicit controller authorization before real local data paths are used.
- Missing heavy runtime requirements return structured failure and do not select a checkpoint.
- Failed Task 50 training or failed Task 52 tuning never produces a selected checkpoint.
- Successful fixture-mode runs may produce manifest-ref checkpoint metadata, but they do not create or track model payloads.
- Task 52.5 does not implement later pipeline stages, result writing, model-payload publication, or evaluation.
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
