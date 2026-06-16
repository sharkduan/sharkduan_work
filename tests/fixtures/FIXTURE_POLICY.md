# Fixture Policy

## Policy Statement

Only a minimal, verifiable fixture set is committed to the repository. Fixtures exist to support deterministic contract validation in automated tests. Every committed fixture must be traceable to a specific verification-matrix row or test module contract.

## Allowed Fixture Types

| Type | Purpose | Example Path |
| --- | --- | --- |
| JSON schemas and manifests | Source metadata, artifact manifests, record indexes | `tests/fixtures/raw_manifest/` |
| CSV source records | Ingest and parse contract validation | `tests/fixtures/covbinder/`, `tests/fixtures/covpdb/`, `tests/fixtures/covalentin_db/` |
| JSONL record files | Normalization, record writing, model batch construction | `tests/fixtures/records/`, `tests/fixtures/edge_candidates/`, `tests/fixtures/finalize_record_manifests/`, `tests/fixtures/model/`, `tests/fixtures/training/` |
| JSON artifact tables | Protein atom, ligand atom, ligand bond, coordinates, edge candidates | `tests/fixtures/records/valid/artifacts/`, `tests/fixtures/model/valid/artifacts/`, etc. |
| PDB coordinate files | Structure coordinates for record artifacts and inference testing | `tests/fixtures/records/valid/artifacts/*/coordinates.pdb`, `tests/fixtures/inference/request_validation/structures/` |
| mmCIF files | Complex export golden output | `tests/fixtures/inference/complex_export/golden_complex.mmcif` |
| SDF ligand files | Docking protocol input fixtures | `tests/fixtures/evaluation/docking_protocol/valid_manifest/input/ligand.sdf` |
| YAML rule tables | Rule validation and calibration | `tests/fixtures/rules/`, `tests/fixtures/calibration/rule_table.yml` |
| YAML checkpoint metadata | Training run manifest contract validation | `tests/fixtures/training/checkpoints/*.yml` |
| YAML request fixtures | Inference request validation | `tests/fixtures/inference/request_validation/` |
| YAML run manifests | Evaluation denominator and lifecycle report validation | `tests/fixtures/evaluation/denominator_accounting/`, `tests/fixtures/evaluation/lifecycle_reports/` |
| JSON split/leakage indexes | Split-aware evaluation contracts | `tests/fixtures/evaluation/split_reports/` |
| JSON generation results | Result writer and lifecycle contract validation | `tests/fixtures/inference/result_writer/`, `tests/fixtures/inference/sampling_failures/` |
| JSON quality/visual-check reports | Run manifest audit hash validation | `tests/fixtures/training/run_manifest/` |
| TXT config stubs | Docking protocol manifest validation | `tests/fixtures/evaluation/docking_protocol/valid_manifest/configs/docking_config.txt` |
| Python builder modules | Programmatic fixture construction for complex scenarios | `tests/fixtures/*/builder.py`, `tests/fixtures/*/_builder.py` |
| `__init__.py` package markers | Python package resolution for test discovery | Throughout `tests/fixtures/` |

## Prohibited Artifact Types

The following must never appear under `tests/fixtures/`:

- Model checkpoints (`.pt`, `.ckpt`, `.pth`, `.safetensors`)
- Training optimizer state files
- Large binary corpora or raw datasets
- Generated interim or processed data directories
- Docking engine outputs (beyond the excepted minimal `.pdbqt` and `.log`)
- Log files (beyond the excepted minimal `docking_failure.log`)
- Python bytecode (`.pyc`, `__pycache__/`)
- Local cache or environment artifacts (`.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `.env`)
- Temporary files (`.tmp`, `.temp`, `tmp/`, `temp/`)
- Wandb, TensorBoard, or Lightning log directories
- Experiment run outputs

## Narrow Exceptions

Three narrow exceptions are carved out in `.gitignore` to support specific contract tests that need minimal binary or log presence:

1. **`tests/fixtures/evaluation/docking_protocol/valid_manifest/output/receptor.pdbqt`**
   - Required by Task 32 docking protocol manifest validation.
   - Validates that the protocol manifest references an output `.pdbqt` artifact with a correct SHA-256 checksum.
   - This is a minimal (empty or near-empty) marker file, not a real docking output.

2. **`tests/fixtures/evaluation/docking_protocol/valid_manifest/logs/docking_failure.log`**
   - Required by Task 32 to validate the `failure_log_sha256` contract.
   - This is a zero-byte file (SHA-256: `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`), not a real log.

3. **YAML-only training checkpoint metadata fixture files under `tests/fixtures/training/checkpoints/`**
   - Required by Task 25 run manifest contract validation.
   - Files are pure YAML metadata (schema_version, contract_version, role, run_id, step, hashes, URIs, bond_type_vocabulary).
   - No `.pt` weights, optimizer state, or binary checkpoint data.
   - Current files: `valid_checkpoint.yml`, `minor_version_checkpoint.yml`, `major_version_checkpoint.yml`, `no_release_gate_checkpoint.yml`.

## CLI Fixture Directory

`tests/fixtures/cli/` is intentionally a minimal package marker (`__init__.py` only). Task 34 CLI tests primarily reuse existing task fixtures and temp dirs to avoid duplicating fixtures.

## Hygiene

- Local cache/log artifacts (`__pycache__/`, `*.pyc`, `*.log` beyond the excepted file, `*.pdbqt` beyond the excepted file, `.pytest_cache/`) are cleaned and are not part of the committed fixture set.
- Repository hygiene uses two layers: `.gitignore` blocks local cache/log/model/binary artifacts by default, and the CI `repository-hygiene` job blocks the same committed artifact classes on tracked files.
- Model and binary suffixes blocked by both layers include `.ckpt`, `.pt`, `.pth`, `.pkl`, `.npy`, `.npz`, and `.safetensors`.
- The only committed exceptions are the narrow fixture paths listed above.
- No `.gitkeep` placeholders exist under `tests/fixtures/`; no data directory scaffolding is needed.

## Enforcement

- CI validates that no prohibited artifact type appears in `tests/fixtures/`.
- New fixture directories must be traceable to a verification-matrix row or test module contract.
- Exceptions to this policy require a PR-level justification and an ADR.
