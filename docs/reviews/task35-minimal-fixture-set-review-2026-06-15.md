# Task 35: Minimal Fixture Set Review

Date: 2026-06-15

Scope: Window D execute — verification matrix fixture evidence, fixture policy documentation, and fixture inventory audit. This review does not modify code, tests, CI, PMDM, or PocketFlow. Task 36 has not started.

## Fixture Inventory Summary

All fixture directories under `tests/fixtures/` were inventoried by extension and role:

| Directory | Count (approx.) | Extensions | Contract Area |
| --- | --- | --- | --- |
| `raw_manifest/` | 4 files | `.json`, `.csv` | Source manifest validation |
| `covbinder/` | 4 files | `.csv`, `.json` | CovBinder ingest parsing |
| `covpdb/` | 4 files | `.csv`, `.json` | CovPDB ingest parsing |
| `covalentin_db/` | 4 files | `.csv`, `.json` | CovalentInDB ingest parsing |
| `rules/` | 5 files | `.yml` | Rule table schema validation |
| `calibration/` | 2 files | `.yml`, `.jsonl` | Rule calibration sheet |
| `normalize/` | 14 files | `.json`, `.jsonl` | Quality tiers, duplicates, conflicts |
| `records/valid/` | 11 files | `.jsonl`, `.json`, `.pdb` | CovalentComplexRecord contract |
| `records/missing_artifact/` | 7 files | `.jsonl`, `.json` | Missing-artifact error path |
| `edge_candidates/` | 20 files | `.jsonl`, `.json`, `.pdb` | Edge candidate generation |
| `finalize_record_manifests/` | 22 files | `.jsonl`, `.json`, `.pdb` | Final manifest integrity |
| `model/` | 38 files | `.jsonl`, `.json`, `.pdb` | Model batch, stepwise candidates, PMDM adapter, covalent heads, final decode |
| `training/dataset/` | 2 files | `.jsonl`, `.json` | Training dataset preparation |
| `training/smoke/` | 14 files | `.jsonl`, `.json`, `.pdb` | Smoke training loop |
| `training/run_manifest/` | 6 files | `.yml`, `.jsonl`, `.json` | Run manifest provenance |
| `training/checkpoints/` | 4 files | `.yml` | Checkpoint metadata (YAML only) |
| `training/masks_denominators/` | 1 file | `.py` | Mask/denominator builder |
| `inference/request_validation/` | 42 files | `.yml`, `.json`, `.pdb`, `.cif`, `.txt` | Request validation (13 error + 8 valid + structures) |
| `inference/sampling_failures/` | 10 files | `.json`, `.yml` | Sampling system failure lifecycle |
| `inference/result_writer/` | 22 files | `.json`, `.py` | Result writer lifecycle |
| `inference/complex_export/` | 5 files | `.json`, `.mmcif` | mmCIF export validation |
| `evaluation/denominator_accounting/` | 64 files | `.yml`, `.jsonl` | Denominator conservation (16 scenarios) |
| `evaluation/lifecycle_reports/` | 12 files | `.yml`, `.jsonl` | Lifecycle and failure-mode reports (3 scenarios) |
| `evaluation/docking_protocol/` | 8 files | `.yml`, `.pdb`, `.sdf`, `.pdbqt`, `.log`, `.txt`, `.py` | Docking protocol manifest |
| `evaluation/split_reports/` | 8 files | `.json` | Split-aware evaluation |
| `cli/` | 1 file | `.py` | Package marker (intentionally minimal) |

Total committed fixture files: approximately 300 files across 26 directories.

## Policy Compliance

### Allowed Types Present

All committed fixture files fall into allowed categories: JSON, JSONL, YAML, CSV, PDB, mmCIF, SDF, TXT config stubs, and Python builder/init modules. No prohibited types were found.

### Narrow Exceptions Verified

Three narrow `.gitignore` exceptions are active and justified:

1. **`tests/fixtures/evaluation/docking_protocol/valid_manifest/output/receptor.pdbqt`** — present, referenced by docking protocol manifest for SHA-256 validation. Blocked by the general `*.pdbqt` rule; unblocked by the narrow exception.

2. **`tests/fixtures/evaluation/docking_protocol/valid_manifest/logs/docking_failure.log`** — present, zero bytes (SHA-256: `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`). Blocked by the general `*.log` rule; unblocked by the narrow exception.

3. **YAML checkpoint metadata under `tests/fixtures/training/checkpoints/`** — four files present: `valid_checkpoint.yml`, `minor_version_checkpoint.yml`, `major_version_checkpoint.yml`, `no_release_gate_checkpoint.yml`. All are pure YAML with `schema_version`, `contract_version`, `role`, `run_id`, `step`, hashes, URIs, and `bond_type_vocabulary`. No `.pt` weights or optimizer state. Blocked by the general `checkpoints/` rule; unblocked by the narrow exception.

### Prohibited Types Absent

No `__pycache__/`, `*.pyc`, `*.pt`, `*.ckpt`, `*.pth`, `*.safetensors`, `*.tmp`, `*.temp`, or local environment files exist under `tests/fixtures/`. The only `.log` and `.pdbqt` files are the excepted ones.

### CLI Fixture Directory

`tests/fixtures/cli/` contains only `__init__.py` with the docstring `"""CLI test fixtures (Task 34 Window B)."""`. This is intentional: Task 34 CLI tests primarily reuse existing task fixtures and temp directories to avoid duplicating fixtures.

## Hygiene Actions

- Confirmed zero `__pycache__/` directories or `*.pyc` files under `tests/fixtures/`.
- Confirmed the only `.log` file is the excepted zero-byte docking failure log.
- Confirmed the only `.pdbqt` file is the excepted docking protocol output marker.
- Confirmed no `.gitkeep` files exist under `tests/fixtures/` (not needed; `.gitignore` handles data directory structure separately).
- The `.gitignore` file was reviewed and the main controller is handling it; no modifications were made.

## Verification Matrix Changes

The verification matrix (`docs/specs/verification-matrix.md`) was updated with a **Fixture Coverage** table mapping every contract area to its fixture evidence directory. The table covers:

- Raw source manifests, source parsing, normalization
- CovalentComplexRecord, rule table, rule calibration sheet
- Edge candidates, final record manifests
- Model batch, stepwise candidates, PMDM adapter, covalent heads, final decode
- Training dataset, masks/denominators, smoke train, run manifest
- Request validation, sampling failures, result writer, mmCIF export
- Evaluation denominators, lifecycle reports, docking protocol, split-aware evaluation
- CLI tests (minimal package marker)

## Test Commands

The following commands validate that the existing fixture set supports all contract tests (run from repository root with `PYTHONPATH=src`):

- `python -m compileall -q scripts src` — compilation guard
- `python -m unittest discover -s tests -t . -q` — full regression (1614 tests as of Checkpoint C)
- `git diff --check` — whitespace validation (expected line-ending warnings only)
- `rg "__pycache__|\.pyc$" tests/fixtures/` — no cache artifacts (expected: no matches)
- `rg "\.(pt|ckpt|pth|safetensors)$" tests/fixtures/` — no checkpoint binaries (expected: no matches)

## Task 36 Boundary

Task 36 has not started. This report is a documentation-only Window D execution. No code, test, fixture, CI, PMDM, or PocketFlow files were modified.

The fixture policy, verification matrix, and github-management docs provide the governance baseline for Task 36 to reference when it begins.

## Decision

Task 35 documentation is complete. Task 36 may start after main-controller approval.
