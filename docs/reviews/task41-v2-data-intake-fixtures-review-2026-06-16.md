# Task 41 V2 Data Intake Fixtures — Review

Date: 2026-06-16
Status: approved
Scope: Task 41 only (manual staging and download request fixtures)
Gate: Window D WRITE APPROVED

## Actual Implementation

### Source Module

`src/covalent_design/data/v2_intake.py` — 354 lines, pure staging logic, zero network access, no conversion/training/license decisions.

Public API:
- `stage_source_manifest(manifest_path, *, allow_download=False, output_root=None)` → `ContractEnvelope[V2StagingSummary]`
- `V2StagingSummary` — frozen dataclass with `source_name`, `intake_mode`, `status`, `source_url`, `manual_path`, `output_root`, `checksum`, `checksum_algorithm`, `parser_target`, `license_audit_ref`, `download_request`
- `V2DownloadRequest` — frozen dataclass for pending-download metadata
- `v2_staging_summary_to_dict(summary)` / `serialize_v2_staging_summary(summary)` — deterministic serialization

### CLI Module

`src/covalent_design/data/cli/v2_stage_source.py` — thin argparse wrapper around `stage_source_manifest`. Flags: `--manifest` (required), `--allow-download` (default false), `--output-root` (optional). Outputs deterministic JSON to stdout; exit code 0 on success, non-zero on failure.

### Package Exports

`src/covalent_design/data/__init__.py` — `V2DownloadRequest`, `V2StagingSummary`, `serialize_v2_staging_summary`, `stage_source_manifest`, `v2_staging_summary_to_dict` are all publicly exported.

### Test Module

`tests/data/test_v2_intake.py` — 19 tests passing.

### Committed Fixtures

`tests/fixtures/v2/data_intake/` — 6 fixture scenarios:

| Directory | Purpose |
| --- | --- |
| `manual/` | Manual intake with synthetic sample data file and valid checksum |
| `manual_checksum_mismatch/` | Manual intake with real sample data file and mismatched checksum |
| `manual_missing_file/` | Manual intake referencing nonexistent file path |
| `download/` | Download request intake with valid manifest; no network access |
| `download_missing_url/` | Download intake missing required `source_url` field |
| `unknown_source/` | Unknown source name must be rejected |
| `unknown_intake_mode/` | Unknown intake mode (`streaming`) must be rejected |

## Staging Contract

### Manual Mode

- Resolves `manual_path` relative to manifest directory if not absolute.
- Verifies file existence → `V2_INTAKE_MANUAL_PATH_FILE_NOT_FOUND` if missing.
- Computes SHA-256 of the file and compares against manifest `checksum`.
- Checksum mismatch → `V2_INTAKE_CHECKSUM_MISMATCH` with `expected` and `actual` in details.
- Matching checksum → status `checksum_verified`.

### Download Mode (Without Network)

- Validates manifest fully without touching the network (proven by monkeypatch blocking `socket.create_connection`, `socket.socket`, `urllib.request.urlopen`, `urllib.request.urlretrieve`).
- Returns `V2StagingSummary` with status `pending_download` and a populated `V2DownloadRequest`.
- `V2DownloadRequest` includes: `source_url`, `intended_output_name` (derived from URL path), `source_artifact_id`, `expected_checksum`, `checksum_algorithm`, `retrieval_metadata_placeholder` (with `network_access: not_performed_task41`), `license_audit_ref`, `retrieval_date`.
- Missing `source_url` in download mode → validation fails at the manifest level (Task 40 contract).

### Download Mode (With `allow_download=True`)

- Returns `V2_INTAKE_DOWNLOAD_NOT_AVAILABLE` structured error.
- No network connection is attempted.
- Real download belongs to a later task.

### Status Vocabulary

| Status | Meaning |
| --- | --- |
| `checksum_verified` | Manual file exists and checksum matches |
| `pending_download` | Download mode manifest valid; no network performed |
| `ok` | Generic success |

Status strings are snake_case, lowercase, machine-readable.

## Error Codes

All errors use `owner = "data"` with structured `V2_INTAKE_*` codes:

| Code | Trigger |
| --- | --- |
| `V2_INTAKE_MANIFEST_UNREADABLE` | Manifest file cannot be read |
| `V2_INTAKE_MANUAL_PATH_MISSING` | Manual mode but `manual_path` is empty/None |
| `V2_INTAKE_MANUAL_PATH_FILE_NOT_FOUND` | Manual file does not exist at resolved path |
| `V2_INTAKE_CHECKSUM_MISMATCH` | Computed SHA-256 differs from manifest `checksum` |
| `V2_INTAKE_DOWNLOAD_NOT_AVAILABLE` | `allow_download=True` requested (blocked in Task 41) |

Manifest-level validation errors (from Task 40) propagate through: unknown source names, unknown intake modes, missing required fields, checksum format violations, source-parser mismatches, etc.

## Deterministic Serialization

- `v2_staging_summary_to_dict()` returns sorted-key dict with only non-None fields.
- `serialize_v2_staging_summary()` produces compact JSON (`sort_keys=True`, `separators=(",", ":")`, `ensure_ascii=False`).
- Identical manifests produce identical serialized summaries (verified by `test_summary_status_names_are_deterministic`, `test_summary_serialization_is_stable`).
- Status names are machine-readable snake_case (verified by `test_status_names_are_machine_readable`).

## Explicit Scope Boundaries (NOT in Task 41)

- No raw-data download or network access
- No file conversion or record parsing of raw-data contents
- No license eligibility decisions
- No training artifact generation
- No heavy dependency imports (RDKit, PyTorch, CUDA, PMDM, PocketFlow)
- No filesystem artifacts created during staging (proven by `test_no_files_created_during_staging`)
- No `conversion_status`, `license_eligibility`, `license_status`, `training_artifacts`, `training_eligible`, or `training_split` fields on `V2StagingSummary` (proven by `test_no_conversion_license_or_training_fields_in_summary`)

## Test Coverage Summary (19 tests)

| Category | Tests |
| --- | --- |
| Manual staging | `test_valid_manual_verifies_file_and_checksum`, `test_missing_manual_path_fails`, `test_checksum_mismatch_fails` |
| Download request | `test_valid_download_passes_without_network`, `test_allow_download_fails_structured_no_network`, `test_missing_source_url_fails`, `test_no_network_access_whatsoever` |
| Validation errors | `test_unknown_source_fails`, `test_unknown_intake_mode_fails` |
| Deterministic summary | `test_summary_status_names_are_deterministic`, `test_summary_serialization_is_stable`, `test_status_names_are_machine_readable` |
| No artifacts | `test_no_files_created_during_staging`, `test_no_conversion_license_or_training_fields_in_summary` |
| CLI | `test_manual_exits_0_json`, `test_download_exits_0_json`, `test_invalid_exits_nonzero_json`, `test_cli_manual_with_output_root`, `test_cli_allow_download_fails_structured` |

## Verification Commands

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/data/test_v2_intake.py -q
python -m covalent_design.data.cli.v2_stage_source --manifest tests/fixtures/v2/data_intake/download/source_manifest.json
python -m covalent_design.data.cli.v2_stage_source --manifest tests/fixtures/v2/data_intake/unknown_source/manifest.json
```

## Compliance With Task 41 Acceptance Criteria

| Criterion | Status |
| --- | --- |
| Manual staging fixture validates path and checksum | PASS — file existence + SHA-256 verification |
| Download mode can be represented without network in tests | PASS — monkeypatch blocks all network paths, `download_request` populated |
| Download attempts are disabled unless explicitly requested | PASS — `allow_download=True` returns `V2_INTAKE_DOWNLOAD_NOT_AVAILABLE` |
| Output manifests are deterministic | PASS — sorted-key dicts, stable serialization, machine-readable status names |
| No network in default tests | PASS — all network paths blocked in download tests |
| No conversion, license, or training artifacts | PASS — no filesystem writes, no forbidden fields on summary |

## Decision

Task 41 is complete and verified. No blocking issues. The staging logic correctly handles manual checksum verification and download-mode fixture representation without network access. The CLI produces deterministic JSON output. Scope boundaries are explicitly enforced: no download, no conversion, no license decisions, no training artifacts.

**Proceed to Task 42.**

## Final Review Follow-Up

Window E final review found no P0/P1 blockers. The main controller fixed the actionable P2/P3 items before final verification:

- Success receipts now use the input manifest SHA-256 for `ValidationReceipt.input_sha256` instead of hashing the output summary.
- The unreachable Task 41 unknown-intake-mode branch was removed; unknown intake modes remain owned by Task 40 manifest validation.
- Error-code assertions in `tests/data/test_v2_intake.py` now check exact expected codes.
- `manual_checksum_mismatch/manifest.json` was added so the checksum-mismatch fixture is used by tests.
