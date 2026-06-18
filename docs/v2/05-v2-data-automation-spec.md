# V2 Data Automation Spec

Date: 2026-06-16
Status: hardened planning spec; Task 40, Task 41, and Task 42 implemented

## Input Data Sources

V2-beta mainline includes only:

- CovalentInDB
- CovPDB
- CovBinderInPDB

Other datasets are out of mainline scope unless a later planning document accepts them.

## Local Real Data Policy

V2-beta uses user-provided local real data. Codex, Claude Code, and future agents must not download real source data from the network by default.

The local raw data root is:

```text
D:\codex_work\data
```

Agents may read files under this root only when the corresponding source manifest exists and points to the intended source-specific local path. Files under `D:\codex_work\data` are untrusted input until the following checks pass:

- source manifest validation,
- SHA-256 checksum validation,
- parser target validation,
- source provenance validation,
- license audit validation.  For `intake_mode = "manual"` data with
  `license_status = "manual_exempt"`, this step records the exemption
  rather than blocking (see ADR 0038 and License Checks below).

Real raw data, real model weights, and real docking outputs must not be committed to git.

Automatic download is not part of the current v2-beta default path. It may be described only as a future optional capability or a later explicitly approved task. Existing Task 40 `intake_mode = "download"` manifests record that a user-provided local file originated from a source URL; they must not be interpreted as permission for an agent to perform network download.

## Local Raw Data Layout

Recommended local layout:

```text
D:\codex_work\data\
  CovalentInDB\
    source_manifest.json
    raw\
  CovPDB\
    source_manifest.json
    raw\
  CovBinderInPDB\
    source_manifest.json
    raw\
```

The layout is outside the repository. Documentation and code may reference it, but this documentation task must not create, inspect, or modify files under `D:\codex_work\data`.

## Task 40 — Data Intake Manifest (IMPLEMENTED)

Implementation: `src/covalent_design/data/v2_manifests.py`

Tests: `tests/data/test_v2_manifests.py` (29 passing)

Fixtures: `tests/fixtures/v2/data_manifests/`

### Allowed Values

| Category | Allowed |
| --- | --- |
| `source_name` | `CovalentInDB`, `CovPDB`, `CovBinderInPDB` |
| `intake_mode` | `download`, `manual` |
| `checksum_algorithm` | `sha256` only |
| `parser_target` | `covalentin_db`, `covpdb`, `covbinder_in_pdb` |

### Source-to-Parser Mapping

| source_name | parser_target |
| --- | --- |
| `CovalentInDB` | `covalentin_db` |
| `CovPDB` | `covpdb` |
| `CovBinderInPDB` | `covbinder_in_pdb` |

Mismatched source_name/parser_target fails validation with `V2_MANIFEST_SOURCE_PARSER_MISMATCH`.

### Required Fields

`schema_version`, `contract_version`, `source_name`, `intake_mode`, `checksum`, `checksum_algorithm`, `parser_target`, `retrieval_date`, `license_audit_ref`, `access_notes`

### Mode-Specific Conditional Fields

| intake_mode | Required field | Validation error if missing |
| --- | --- | --- |
| `download` | `source_url` | `V2_MANIFEST_SOURCE_URL_REQUIRED` |
| `manual` | `manual_path` | `V2_MANIFEST_MANUAL_PATH_REQUIRED` |

### checksum Format

`checksum` must be a 64-character lowercase SHA-256 hex digest (regex `^[0-9a-f]{64}$`). Invalid format produces `V2_MANIFEST_CHECKSUM_INVALID`.

### Validation Contract

- Validation returns `ContractEnvelope[Optional[V2DataIntakeManifest]]`.
- All errors use structured `V2_MANIFEST_*` codes with owner `data`, machine-readable `message`, `location`, and optional `details`.
- Error codes: `V2_MANIFEST_UNREADABLE`, `V2_MANIFEST_INVALID_JSON`, `V2_MANIFEST_ROOT_NOT_OBJECT`, `V2_MANIFEST_MISSING_REQUIRED_FIELD`, `V2_MANIFEST_FORBIDDEN_FIELD`, `V2_MANIFEST_UNKNOWN_SOURCE_NAME`, `V2_MANIFEST_UNKNOWN_INTAKE_MODE`, `V2_MANIFEST_MANUAL_PATH_REQUIRED`, `V2_MANIFEST_SOURCE_URL_REQUIRED`, `V2_MANIFEST_UNSUPPORTED_CHECKSUM_ALGORITHM`, `V2_MANIFEST_CHECKSUM_INVALID`, `V2_MANIFEST_UNKNOWN_PARSER_TARGET`, `V2_MANIFEST_SOURCE_PARSER_MISMATCH`.

### Serialization

`serialize_v2_data_intake_manifest()` and `v2_data_intake_manifest_to_dict()` produce deterministic output (sorted keys, compact separators, `ensure_ascii=False`).

### Forbidden Fields (Later Tasks)

The manifest must not contain: `conversion_status`, `license_eligibility`, `license_status`, `staging_status`, `training_artifacts`, `training_eligible`, `training_split`. These produce `V2_MANIFEST_FORBIDDEN_FIELD`.

### Scope Exclusions

Task 40 does not: download raw data, stage files, convert records, inspect raw-data contents, decide license eligibility, produce training artifacts, or import heavy dependencies. No network access is performed during validation.

### Public API

`validate_v2_data_intake_manifest(manifest_path)` — validate from file path.
`v2_data_intake_manifest_from_dict(data)` — validate from in-memory mapping.
`serialize_v2_data_intake_manifest(manifest)` — deterministic JSON serialization.
`v2_data_intake_manifest_to_dict(manifest)` — deterministic dict export.

### Verification Result (2026-06-16)

```powershell
python -m pytest tests/data/test_v2_manifests.py -q
# 29 passed
```

## Task 41 - Manual Staging And Download Request Fixtures (IMPLEMENTED)

Implementation: `src/covalent_design/data/v2_intake.py`

CLI: `src/covalent_design/data/cli/v2_stage_source.py`

Tests: `tests/data/test_v2_intake.py` (19 passing)

Fixtures: `tests/fixtures/v2/data_intake/`

### Staging Contract

`stage_source_manifest(manifest_path, *, allow_download=False, output_root=None)` returns `ContractEnvelope[V2StagingSummary]`.

### Manual Mode Behavior

- Resolves `manual_path` relative to manifest directory if not absolute.
- Verifies file existence; missing file → `V2_INTAKE_MANUAL_PATH_FILE_NOT_FOUND`.
- Computes SHA-256 of the file; mismatch → `V2_INTAKE_CHECKSUM_MISMATCH` with `expected`/`actual` in details.
- Match → status `checksum_verified`.

### Download Mode Behavior

- Without `allow_download`: validates manifest, returns status `pending_download` with populated `V2DownloadRequest`; zero network access.
- With `allow_download=True`: returns `V2_INTAKE_DOWNLOAD_NOT_AVAILABLE` structured error; Task 41 does not include a real downloader.
- Missing `source_url` in download mode falls through to manifest-level validation (Task 40 contract).

`V2DownloadRequest` records `source_url`, `intended_output_name`, `source_artifact_id`, `expected_checksum`, `checksum_algorithm`, `retrieval_metadata_placeholder`, `license_audit_ref`, and `retrieval_date`.

### Status Vocabulary

| Status | Meaning |
| --- | --- |
| `checksum_verified` | Manual file exists and checksum matches |
| `pending_download` | Download manifest valid; network not performed |
| `ok` | Generic success |

Status strings are snake_case, lowercase, machine-readable.

### Staging Error Codes

All errors use `owner = "data"` with structured `V2_INTAKE_*` codes:

| Code | Trigger |
| --- | --- |
| `V2_INTAKE_MANIFEST_UNREADABLE` | Manifest file cannot be read |
| `V2_INTAKE_MANUAL_PATH_MISSING` | Manual mode but `manual_path` is empty/None |
| `V2_INTAKE_MANUAL_PATH_FILE_NOT_FOUND` | Manual file does not exist |
| `V2_INTAKE_CHECKSUM_MISMATCH` | SHA-256 mismatch |
| `V2_INTAKE_DOWNLOAD_NOT_AVAILABLE` | `allow_download=True` (blocked in Task 41) |

### Deterministic Serialization

`v2_staging_summary_to_dict()` returns sorted-key dict with only non-None fields. `serialize_v2_staging_summary()` produces compact JSON (`sort_keys=True`, `separators=(",", ":")`, `ensure_ascii=False`). Identical manifests produce identical serialized output.

### CLI

```
python -m covalent_design.data.cli.v2_stage_source --manifest <path> [--allow-download] [--output-root <dir>]
```

Outputs deterministic JSON to stdout; exit 0 on success, non-zero on failure.

### Scope Exclusions

Task 41 does not: download raw data, convert records, inspect raw-data contents beyond checksums, decide license eligibility, produce training artifacts, or create filesystem artifacts during staging. No network access is performed.

### Public API (in `covalent_design.data`)

`stage_source_manifest(manifest_path, *, allow_download=False, output_root=None)` — stage a v2 data intake manifest.
`V2StagingSummary` — frozen dataclass summary of staging operation.
`V2DownloadRequest` — frozen dataclass for pending download metadata.
`v2_staging_summary_to_dict(summary)` — deterministic dict export.
`serialize_v2_staging_summary(summary)` — deterministic JSON serialization.

### Verification Result (2026-06-16)

```powershell
python -m pytest tests/data/test_v2_intake.py -q
# 19 passed
```

## Repository Staging Layout

Proposed staging/metadata layout inside the repository or run artifact area:

```text
data/v2/staging/<source_name>/
  source_manifest.json
  license_audit.json
  manual/
  checksums.json
```

This layout is for small manifests, checksums, receipts, and derived metadata only. Real raw data stays under `D:\codex_work\data` or another user-controlled external data root and is not tracked by git.

## Manual Staging Policy

Manual staging is the v2-beta main path:

1. The user downloads CovalentInDB, CovPDB, and CovBinderInPDB data outside the repository.
2. The user places the raw data under `D:\codex_work\data\<source_name>\raw\`.
3. The user or a future task provides `source_manifest.json` for each source.
4. The staging task validates manifest fields, local path, checksum, parser target, source provenance, and license audit reference.
5. Only validated staged inputs may proceed to conversion.

Staging must not assume local files are trustworthy. It must fail closed on missing manifest, checksum mismatch, unknown parser target, missing license audit reference, path outside approved root, or unsupported source name.

## No Agent Network Download Rule

Default tests, default CI, and v2-beta manual staging tasks must not perform network access for real source data. A future automatic downloader, if ever accepted, must be a separate optional capability with explicit approval, source/license evidence, retry/cache policy, checksums, and provenance receipts.

## Conversion Pipeline

The v2 conversion path:

1. raw source manifest validation (Task 40),
2. local raw data staging from `D:\codex_work\data` (Task 41),
3. source-specific decode (Task 42 — `covalentin_db` TSV parser),
4. schema normalization into v1-compatible `SourceIngestRecord` records (Task 42),
5. artifact reference construction (Task 43+),
6. rule and family validation (Task 43+),
7. quality/visual/split gates (Task 43+),
8. family readiness report (Task 43+).

## Task 42 — Data Conversion V2 (IMPLEMENTED)

Implementation: `src/covalent_design/data/v2_conversion.py`

Tests: `tests/data/test_v2_conversion.py`

Fixtures: `tests/fixtures/v2/data_conversion/`

### Public API

`convert_staged_source(staging_envelope, *, reverify_checksum=True)` — convert a Task 41 `ContractEnvelope[V2StagingSummary]` into `ContractEnvelope[tuple[SourceIngestRecord, ...]]`.

`convert_staged_manifest(manifest_path, *, reverify_checksum=True)` — convenience: stage a manifest then convert the resulting staging evidence in one call.

### Conversion Contract

- Only `status == "checksum_verified"` (manual local file with verified checksum) is convertible.
- `pending_download` returns `V2_CONVERSION_PENDING_DOWNLOAD` — no placeholder records, no network access.
- Failed staging envelope (`receipt.ok == False`) returns `V2_CONVERSION_STAGING_FAILED`.
- Forged or non-Task-41 staging envelopes return `V2_CONVERSION_INVALID_STAGING_EVIDENCE`.
- Conversion performs no network access; tests enforce this via socket/urllib monkeypatching.

### Checksum Re-verification

- With `reverify_checksum=True` (default): re-reads and re-computes SHA-256 of the source data file; mismatch → `V2_CONVERSION_CHECKSUM_MISMATCH` with `expected`/`actual` in details.
- With `reverify_checksum=False`: trusts the staging summary checksum without re-reading the file.

### Supported Parser Targets

Task 42 supports only `covalentin_db`. Other parser targets (`covpdb`, `covbinder_in_pdb`) return `V2_CONVERSION_UNSUPPORTED_PARSER`.

### TSV Parser

Parses tab-separated source data files with required columns:

`pdb_id`, `uniprot_id`, `residue`, `residue_number`, `ligand`, `ligand_name`, `bond_type`, `warhead_type`

- Missing required columns → `V2_CONVERSION_MISSING_COLUMNS`.
- Individual row parse failures → `V2_CONVERSION_ROW_PARSE_ERROR` with `row_index` and `missing_fields` in details; valid rows still converted.
- Residue field format: `CYS145` → residue_name `CYS`, residue_number `145`; unparseable → `V2_CONVERSION_ROW_PARSE_ERROR`.
- Empty file or header-only file → empty tuple, no error.
- Unreadable file → `V2_CONVERSION_FILE_UNREADABLE`.

### Output Records

Each `SourceIngestRecord` includes:

- `source_database`, `source_version`, `source_record_id`, `row_index` — identity fields.
- `raw_file_path`, `raw_manifest_file`, `raw_file_sha256` — local path provenance and checksum reference.
- `lineage` (dict) — includes `source_database`, `source_version`, `source_record_id`, `raw_manifest_file`, `raw_file_path`, `raw_file_sha256`, `row_index`, and optionally `license_audit_ref` and `source_url`.
- `metadata` (dict) — includes `pdb_id`, and optionally `license_audit_ref` and `source_url`.
- `protein` (dict) — includes `pdb_id`, `uniprot_id`, `chain_id`, `residue`, `residue_name`, `residue_number`, `atom_name`.
- `ligand` (dict) — includes `ligand_id`, `compound_id`, `ligand_name`, `attachment_atom`, `warhead_type`.
- `linkage` (dict) — includes `bond_type`, `residue_reaction_family`.
- `source_lineage` (`SourceRecordLineage`) — structured lineage dataclass.
- `target_atom_identity` (`ProteinAtomIdentity`) — chain A, residue, SG atom.
- `ligand_atom_identity` (`LigandAtomIdentity`) — ligand ID, C1 atom.

Records feed existing v1 ETL: `normalize_linkages()` and `normalize_with_identity_resolution()` accept the output tuple directly.

### Provenance / Checksum / License Audit Reference Preservation

- `raw_file_sha256` is the source file checksum from the staging summary, propagated to every record.
- `license_audit_ref` is preserved in both `lineage` and `metadata` for downstream Task 43 eligibility decisions.
- `source_url` (when present in staging summary) is preserved in both `lineage` and `metadata`.
- `raw_file_path` and `raw_manifest_file` are absolute paths resolved during staging.
- Task 43 may read these preserved references to cross-check staged manifest evidence, but Task 43 does not execute conversion or raw parsing.

### Conversion Error Codes

All errors use `owner = "data"` with structured `V2_CONVERSION_*` codes:

| Code | Trigger |
| --- | --- |
| `V2_CONVERSION_STAGING_FAILED` | Staging envelope receipt not ok |
| `V2_CONVERSION_INVALID_STAGING_EVIDENCE` | Envelope validator is not Task 41 `stage_source_manifest` |
| `V2_CONVERSION_PAYLOAD_MISSING` | Staging envelope payload is None |
| `V2_CONVERSION_PENDING_DOWNLOAD` | Staging status is `pending_download` |
| `V2_CONVERSION_UNEXPECTED_STATUS` | Staging status is neither `checksum_verified` nor `pending_download` |
| `V2_CONVERSION_MANUAL_PATH_MISSING` | No `manual_path` in staging summary |
| `V2_CONVERSION_FILE_NOT_FOUND` | Source data file does not exist at `manual_path` |
| `V2_CONVERSION_UNSUPPORTED_PARSER` | Parser target not in Task 42 supported set |
| `V2_CONVERSION_CHECKSUM_MISMATCH` | Re-verification checksum differs from staging summary |
| `V2_CONVERSION_FILE_UNREADABLE` | Source data file cannot be read |
| `V2_CONVERSION_MISSING_COLUMNS` | TSV file missing required columns |
| `V2_CONVERSION_ROW_PARSE_ERROR` | Individual row has missing fields or unparseable residue |

### Scope Exclusions

Task 42 does not: access network, download raw data, produce training artifacts, decide license eligibility, decide training eligibility (Task 43 scope), produce family readiness reports, produce split assignments, create filesystem artifacts during conversion, or support parser targets beyond `covalentin_db`.

### Deterministic Verification

Same staging input → same `SourceIngestRecord` tuple. Same record count, same field values, same receipt structure. Output is serializable to JSON via `dataclasses.asdict()`.

### Verification Result (2026-06-16)

```powershell
python -m pytest tests/data/test_v2_conversion.py -q
# tests pass
```

## Schema Normalization

All source-specific records must normalize to existing v1 concepts:

- `CovalentComplexRecord`
- `residue_reaction_family`
- `target_atom`
- ligand attachment atom
- warhead annotation
- covalent edge label
- artifact refs
- quality and visual status

## Structure Cleaning

Cleaning must be explicit and reportable:

- protein atom table normalization,
- ligand atom table normalization,
- ligand bond normalization,
- coordinate frame provenance,
- chemical-state availability,
- failure reason for dropped structures.

## Ligand / Protein Processing

- Protein processing must preserve `Structure Atom Identity`.
- Ligand processing must preserve stable `ligand_atom_index`.
- Multi-linkage records remain excluded from first-core training unless policy changes.
- Chemical-state unavailable records must be reported, not silently repaired.

## Artifact Manifests

Every generated or staged artifact must include:

- role,
- path or URI,
- checksum,
- schema version,
- contract version,
- source provenance,
- license audit reference.

## License Checks

Allowed license statuses:

- `allowed`
- `restricted`
- `blocked`
- `unknown`
- `manual_exempt`

Only `allowed`, `restricted` with recorded and satisfied conditions, and
manual-mode `manual_exempt` records may enter training eligibility.

`unknown` and `blocked` may be recorded for audit, but Task 43 must block
them before training eligibility. Task 42 conversion does not decide
license eligibility and may only preserve references needed for Task 43.
`restricted` must preserve conditions in downstream manifests and reports.

### Task 43 Input Boundary

Task 43 consumes Task 41 staged source manifests and staging evidence. It
may also read Task 42 conversion output only to verify that preserved
`license_audit_ref`, checksum, local path provenance, and source
provenance references match the staged evidence.

Task 43 does not execute conversion, raw parsers, training, sampling, or
Task 44+ work. If staged manifest evidence and converted output references
disagree, Task 43 must fail with a structured cross-validation error.
Task 43 outputs a training eligibility gate report, or an equivalent
deterministic artifact, that records per-source license status,
eligibility, blocking reasons, and report categories.

Implemented API:

- `audit_v2_training_eligibility(staged_evidence, license_audits, converted_records=(), approved_local_data_roots=())`
- `load_source_license_audit(path)`
- `license_gate_report_to_dict(report)`

The gate returns `ContractEnvelope[LicenseGateReport]`. `LicenseGateReport`
contains one `LicenseGateSourceReport` per staged source, five-state
`status_counts`, `training_eligible_count`, and `blocked_count`.  The
report is in-memory unless a caller explicitly serializes it; Task 43
does not create training/model/inference/evaluation artifacts.

### Manual Exemption

`manual_exempt` is a soft exemption for `intake_mode = "manual"` data. It allows training without formal third-party license audit while preserving the audit trail: `license_audit_ref` remains required, and the referenced audit file must contain at minimum `license_status: "manual_exempt"`. No further fields are required for `manual_exempt` entries.

`manual_exempt` does not bypass source manifest validation, SHA-256
checksum validation, parser target validation, local path provenance,
source provenance, or license audit reference validation.

`manual_exempt` MUST NOT appear on `intake_mode = "download"` sources. Task 43 (license gate) MUST reject `manual_exempt` combined with `download` as a structured error.

Training eligibility and family readiness reports MUST list `manual_exempt` as a distinct category (not merged with `allowed`) and SHOULD include a notice that manual-exempt data has not undergone third-party license verification.

See ADR 0038 for the full decision record.

## Checksum Rules

- SHA-256 is the only accepted checksum algorithm for v2-beta staging.
- Checksums must be exact-byte checksums over the staged raw artifact or declared source archive.
- A checksum mismatch is a blocking staging failure.
- Partial, interrupted, or manually edited raw files must not be treated as valid artifacts.

## Git Tracking Rule

- Do not commit real raw data from `D:\codex_work\data`.
- Do not copy real raw data into tracked fixtures.
- Tracked fixtures must remain synthetic or minimal non-sensitive examples.
- Tracked manifests may reference external local paths only when they are clearly examples or review artifacts and do not expose private data.

## Quality Gates

V2 data automation must preserve v1 gates:

- rejected/conflict separation,
- Q0/Q1/Q2 quality tiers,
- visual check blocking,
- leakage-aware split assignments,
- family readiness.

## Verification Commands

Planned commands:

```bash
python -m covalent_design.data.cli.v2_validate_source_manifest --manifest D:\codex_work\data\<source>\source_manifest.json
python -m covalent_design.data.cli.v2_stage_source --manifest D:\codex_work\data\<source>\source_manifest.json
python -m covalent_design.data.cli.v2_convert_source --manifest data/v2/staging/<source>/source_manifest.json --out-root data/v2/processed
python -m covalent_design.data.cli.v2_run_real_etl --raw-root D:\codex_work\data --staging-root data/v2/staging --out-root data/v2/processed
```

Exact command names are finalized by the implementing tasks, but public CLIs should be package module entrypoints. Standalone scripts may wrap these commands only as developer helpers.

The commands above are planned interface shapes, not executed by this documentation task. They must not perform network download in the v2-beta default path.
