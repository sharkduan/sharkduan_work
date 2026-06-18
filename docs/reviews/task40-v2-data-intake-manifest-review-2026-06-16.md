# Task 40 V2 Data Intake Manifest — Review

Date: 2026-06-16
Status: approved
Scope: Task 40 only (manifest schema and validation)
Gate: Window D WRITE APPROVED

## Actual Implementation

### Source Module

`src/covalent_design/data/v2_manifests.py` — 355 lines, frozen-dataclass manifest, pure validation, zero side effects.

### Test Module

`tests/data/test_v2_manifests.py` — 315 lines, 29 tests passing.

### Committed Fixtures

`tests/fixtures/v2/data_manifests/` — 6 valid + 9 invalid manifest JSON files.

## Schema Conformance

### Allowed Values

| Category | Allowed |
| --- | --- |
| `source_name` | `CovalentInDB`, `CovPDB`, `CovBinderInPDB` |
| `intake_mode` | `download`, `manual` |
| `checksum_algorithm` | `sha256` |
| `parser_target` | `covalentin_db`, `covpdb`, `covbinder_in_pdb` |

### Source-to-Parser Enforcement

`SOURCE_TO_PARSER_TARGET` dict enforces exact match. Mismatch produces `V2_MANIFEST_SOURCE_PARSER_MISMATCH`.

### Required Fields (10)

`schema_version`, `contract_version`, `source_name`, `intake_mode`, `checksum`, `checksum_algorithm`, `parser_target`, `retrieval_date`, `license_audit_ref`, `access_notes`

Any missing required field produces `V2_MANIFEST_MISSING_REQUIRED_FIELD`.

### Optional Mode-Specific Fields

| Field | Required when | Validation error |
| --- | --- | --- |
| `source_url` | `intake_mode = "download"` | `V2_MANIFEST_SOURCE_URL_REQUIRED` |
| `manual_path` | `intake_mode = "manual"` | `V2_MANIFEST_MANUAL_PATH_REQUIRED` |

### checksum Validation

- Algorithm must be `sha256`; anything else → `V2_MANIFEST_UNSUPPORTED_CHECKSUM_ALGORITHM`.
- Digest must be 64 lowercase hex chars (regex `^[0-9a-f]{64}$`); invalid → `V2_MANIFEST_CHECKSUM_INVALID`.

### Forbidden Fields (Later Tasks)

`conversion_status`, `license_eligibility`, `license_status`, `staging_status`, `training_artifacts`, `training_eligible`, `training_split` — all rejected with `V2_MANIFEST_FORBIDDEN_FIELD`.

## Validation Contract

- Function: `validate_v2_data_intake_manifest(manifest_path: Path) -> ContractEnvelope[Optional[V2DataIntakeManifest]]`
- In-memory path: `v2_data_intake_manifest_from_dict(data) -> ContractEnvelope[Optional[V2DataIntakeManifest]]`
- All errors are `ContractErrorInfo` with `owner = "data"`, structured `V2_MANIFEST_*` code, `message`, `location`, and optional `details`.
- Unreadable file → `V2_MANIFEST_UNREADABLE`
- Invalid JSON → `V2_MANIFEST_INVALID_JSON`
- Root not an object → `V2_MANIFEST_ROOT_NOT_OBJECT`
- Returns `payload = None` on validation failure, `payload = V2DataIntakeManifest` on success.

## Deterministic Serialization

- `serialize_v2_data_intake_manifest()` → compact JSON with sorted keys, `separators=(",", ":")`, `ensure_ascii=False`.
- `v2_data_intake_manifest_to_dict()` → sorted dict.
- Roundtrip identity verified by test `test_serialization_is_deterministic`.

## Explicit Scope Boundaries (NOT in Task 40)

- No raw-data download
- No file staging
- No record conversion
- No license eligibility decisions
- No training artifact generation
- No heavy dependency imports (RDKit, PyTorch, CUDA, PMDM, PocketFlow)
- No network access during validation (proven by `test_download_mode_does_not_perform_network_access`)

## Test Coverage Summary (29 tests)

| Category | Tests |
| --- | --- |
| Valid manifests | `test_valid_manual_manifest`, `test_valid_download_manifest`, `test_allowed_source_names` (×3 parametric), `test_allowed_intake_modes` (×2 parametric) |
| Unknown values | `test_unknown_source_name_fails`, `test_unknown_intake_mode_fails`, `test_unknown_parser_target_fails` |
| Missing required | `test_missing_checksum_fails`, `test_missing_parser_target_fails`, `test_license_audit_ref_is_required`, `test_empty_license_audit_ref_fails` |
| Checksum validation | `test_unsupported_checksum_algorithm_fails`, `test_invalid_sha256_checksum_format_fails` |
| Mode-specific | `test_manual_mode_requires_manual_path`, `test_download_mode_requires_source_url` |
| Source-parser mismatch | `test_source_parser_mismatch_fails` |
| File/memory entry | `test_invalid_json_file_fails_with_structured_error`, `test_json_root_must_be_object` |
| Committed fixtures | `test_committed_fixture_valid_download_covpdb`, `test_committed_fixture_unknown_source_fails` |
| Contract properties | `test_serialization_is_deterministic`, `test_validation_errors_are_structured_and_machine_readable`, `test_manifest_rejects_later_task_fields`, `test_validation_does_not_create_artifacts`, `test_download_mode_does_not_perform_network_access`, `test_constants_are_closed_to_task40_scope` |

## Verification Command

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/data/test_v2_manifests.py -q
# 29 passed
```

## Compliance With Task 40 Acceptance Criteria

| Criterion | Status |
| --- | --- |
| Manifest supports CovalentInDB, CovPDB, CovBinderInPDB only | PASS — `ALLOWED_SOURCE_NAMES` tuple; unknown rejected |
| Records mode, source URL or manual path, checksum, parser target, retrieval date, license audit ref | PASS — all 10 required fields + mode-specific fields |
| Unknown source names fail | PASS — `V2_MANIFEST_UNKNOWN_SOURCE_NAME` |
| Missing checksum fails | PASS — `V2_MANIFEST_MISSING_REQUIRED_FIELD` |
| No download yet | PASS — network access monkeypatched/blocked in tests |

## Decision

Task 40 is complete and verified. No blocking issues. The manifest schema, validation, error codes, serialization, and test coverage all match the accepted acceptance criteria. The implementation correctly bounds Task 40 scope and defers download/staging/conversion/license/training to later tasks.

**Proceed to Task 41.**
