# V2 Interface And Contract Changes

Date: 2026-06-16
Status: proposed additive contract plan

## Compatibility Policy

V2-beta changes are additive. Existing v1 contracts remain valid. Heavy dependency objects must not leak across public package seams.

## Module Boundaries

| Module | V2 delta | Boundary rule |
| --- | --- | --- |
| `contracts` | additive v2 manifest/report dataclasses | preserve v1 facade imports |
| `data` | source download/staging, license audit, family readiness | no training logic |
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

Purpose: source-level license and provenance decision for data intake.

Producer: Task 43 license gate. Consumer: conversion, training eligibility, release review.

Serialization: deterministic JSON. Artifact role: `source_license_audit`.

Required fields:

- `source_name`: enum `CovalentInDB`, `CovPDB`, or `CovBinderInPDB`.
- `license_status`: enum `allowed`, `allowed_with_conditions`, `unknown`, or `blocked`.
- `license_evidence_ref`: artifact ref or URL string.
- `retrieval_url`: URL string or null for manual staging.
- `retrieval_method`: enum `automatic`, `manual`, or `not_retrieved`.
- `retrieved_at`: ISO-8601 timestamp or null.
- `checksum`: `sha256:<hex>` or null.
- `allowed_for_training`: boolean.
- `blocking_reason`: string or null.

Misuse guard: `unknown` and `blocked` must not enter training eligibility. `allowed_with_conditions` must preserve its conditions.

### V2DataIntakeManifest

Purpose: source download/manual staging manifest.

Producer: Task 40/41 intake. Consumer: conversion and license audit.

Serialization: deterministic JSON. Artifact role: `v2_data_intake_manifest`.

Required fields:

- `schema_version`: string.
- `contract_version`: string.
- `source_name`: enum `CovalentInDB`, `CovPDB`, or `CovBinderInPDB`.
- `mode`: enum `automatic` or `manual`.
- `local_path`: string or null.
- `checksum`: `sha256:<hex>`.
- `file_count`: integer.
- `parser_name`: string.
- `license_audit_ref`: artifact ref or null until Task 43.
- `status`: enum `pending`, `staged`, `converted`, `unavailable`, `skipped`, or `error`.

Optional fields:

- `source_url`: URL string.
- `retrieval_date`: ISO-8601 date.
- `manual_reason`: string.
- `error_code`: string.
- `error_message`: string.

Misuse guard: download attempts are disabled unless explicitly requested. Missing checksum fails validation.

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

## CLI Boundaries

Future v2 CLIs should be thin wrappers around typed Python interfaces. Planned families:

- environment smoke,
- source download/staging,
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
- download checksum mismatch,
- schema normalization failure,
- family readiness blocked,
- PMDM unavailable without explicit fallback,
- denominator drift,
- label leakage risk.
