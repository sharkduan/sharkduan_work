# V2 Implementation Plan

Date: 2026-06-16
Status: hardened v2-beta task plan
Target: `v2-beta`

## Overview

Task 37+ continues after v1 Tasks 1-36. The plan keeps v2-beta focused on one minimum usable closed loop: real environment, real or manually staged data, ETL and family readiness, PMDM or explicit fallback smoke, small training, sampling, and evaluation.

Each task has one primary goal and should fit in one focused session. Heavy dependency work starts with smoke probes before real training.

ADR 0037 is the authority for v2 environment boundaries, heavyweight optional dependencies, and the frozen `lightweight` / `heavy` smoke profile vocabulary. V2 docs are planning overlays until their tasks land; implemented v2 decisions must be synchronized back into canonical specs during or after the relevant implementation task.

V2 follows the v1 task-slicing standard:

- one task owns one primary deliverable,
- task dependencies are explicit and ordered by prerequisite evidence,
- every task has checkable acceptance criteria and a verification command,
- every phase ends in a checkpoint gate,
- implementation details do not get ADRs unless they are hard-to-reverse cross-task decisions.

The Task-to-decision coverage matrix lives in `docs/v2/13-v2-task-adr-coverage.md`. That document explains why ADRs are decision-scoped rather than task-scoped.

## Phase V2-A: Environment And Dependency Foundation

### Task 37: Finalize V2 Environment Policy And Scaffold

**Goal:** Create the initial v2 environment interface without running training.

**Files/modules:**

- `environment.yml`
- `scripts/v2_smoke_check.py`
- `docs/v2/04-v2-dependency-and-environment-spec.md`
- `docs/adr/0037-v2-environment-and-heavy-dependency-boundary.md`

**Dependencies:** v1 Tasks 1-36 complete; ADR 0037 accepted.

**Acceptance:**

- `environment.yml` exists with source-verification placeholders for Python, PyTorch, CUDA, RDKit, PMDM-related graph dependencies, and project package install mode.
- `scripts/v2_smoke_check.py` exists and can run in lightweight mode without importing unavailable heavy dependencies as hard failures.
- Heavy profile reports missing PyTorch/RDKit/CUDA/PMDM as structured dependency status.
- Default CI is not changed to install heavy dependencies.
- `lightweight` and `heavy` are the only v2 smoke profile names.

**Verification:**

```powershell
$env:PYTHONPATH='src'
python scripts/v2_smoke_check.py --profile lightweight
python -m compileall -q scripts src
```

**Notes:** No training, no source download, no RDKit/PyTorch installation in this task.

### Task 38: Add Dependency Specification And Lock Strategy

**Goal:** Source-verify dependency version choices and define the lock workflow.

**Files/modules:**

- `docs/v2/04-v2-dependency-and-environment-spec.md`
- `docs/v2/dependency-source-verification.md`
- `docs/reviews/task38-dependency-source-verification-review-2026-06-16.md`
- optional `environment.lock.yml` or documented lock output

**Dependencies:** Task 37.

**Acceptance:**

- Official sources are recorded for PyTorch, CUDA, RDKit, Conda/Mamba, PMDM, and any graph dependency.
- Unverified versions are marked `UNVERIFIED`.
- Lock-file generation command is documented.
- PMDM/PocketFlow license status is recorded or marked blocking/unknown.
- The source verification table includes dependency/package, claimed API, official source URL, version scope, license status, verification date, status, and owning task.

**Verification:**

```powershell
# Structured source-verification checks (no git diff)
rg -n "dependency / package|official source URL|license status|verification date|owning task" docs/v2/dependency-source-verification.md
rg -n "^\\| (Python|Conda/Mamba|pip|PyTorch|CUDA|RDKit|PMDM|pytorch-scatter|pytorch-sparse|pytorch-cluster|pytorch-geometric|pytorch-spline-conv|PocketFlow|Project package install mode|Docking engine) \\|" docs/v2/dependency-source-verification.md
rg -n "verified|unverified|blocked|not required yet" docs/v2/dependency-source-verification.md
rg -n "lock|Lock|LOCK|environment.lock" docs/v2/dependency-source-verification.md docs/v2/04-v2-dependency-and-environment-spec.md
rg -n "Task 39 may NOT start|PMDM|blocked|lock workflow" docs/reviews/task38-dependency-source-verification-review-2026-06-16.md
```

**Notes:** Do not cite blogs, StackOverflow, or AI summaries as authority. Task 39 must not start while PMDM is `blocked` or while PyTorch/CUDA/RDKit/PMDM version compatibility remains unverified, unless a later explicit waiver narrows Task 39 to non-importing structured-unavailable probes.

### Task 39: Add RDKit/PyTorch/CUDA Smoke Probe Spec

**Goal:** Make heavy dependency probes executable and separately skippable.

**Files/modules:**

- `scripts/v2_smoke_check.py`
- `tests/v2/test_smoke_check.py`
- `docs/v2/11-v2-verification-matrix.md`

**Dependencies:** Tasks 37, 38.

**Acceptance:**

- Lightweight probe passes without RDKit/PyTorch installed.
- Heavy probe reports PyTorch import, CUDA availability, RDKit import, PMDM path/import, PocketFlow import, docking availability, and project import.
- Probe output is deterministic JSON.
- Missing heavy dependency returns non-zero only in heavy mode.
- Dependency status enum is frozen as `available`/`unavailable`/`not_checked`/`failed`.
- Lightweight profile checks project import only; all six heavy deps (cuda, docking, pmdm, pocketflow, pytorch, rdkit) marked `not_checked`.
- Heavy profile returns structured `unavailable` with exit code 2 when dependencies are missing; exit code 0 when all available.
- Invalid profile (including `cpu`) returns exit code 3 with `exit_reason: unsupported_profile` and `supported_profiles: ["lightweight", "heavy"]`.
- CUDA is reported as `not_checked` when PyTorch is unavailable (not `unavailable` or `failed`).
- PMDM is reported as `unavailable` with `reason: license_unknown` and `import_attempted: false`; no PMDM import is attempted while license is unknown.
- No installs, downloads, environment solves, or adapter code are executed by the smoke probe.
- All tests in `tests/v2/test_smoke_check.py` pass.

**Verification:**

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/v2/test_smoke_check.py -q
python scripts/v2_smoke_check.py --profile lightweight
```

**Verified on 2026-06-16 (this host, Windows 11, no heavy deps):**

- `pytest tests/v2/test_smoke_check.py -q` — all tests passed
- `python scripts/v2_smoke_check.py --profile lightweight` — exit 0
- `python scripts/v2_smoke_check.py --profile heavy` — exit 2 (structured, `exit_reason: heavy_dependency_unavailable`)
- `python scripts/v2_smoke_check.py --profile cpu` — exit 3 (structured, `exit_reason: unsupported_profile`)

**Notes:** Heavy profile may be manual until the environment is available.

### Checkpoint V2-A: Environment Gate

**Goal:** Confirm the v2-beta environment plan is executable before data or training work.

**Required evidence:**

- environment scaffold exists,
- source verification document exists,
- lightweight smoke passes,
- heavy smoke behavior is documented.

## Phase V2-B: Data Intake And License Gate

### Task 40: Design Real Data Intake Manifest V2 (IMPLEMENTED)

**Goal:** Define the source manifest schema and validation for download and manual raw data intake.

**Files/modules:**

- `src/covalent_design/data/v2_manifests.py`
- `tests/data/test_v2_manifests.py`
- `tests/fixtures/v2/data_manifests/`
- `docs/v2/05-v2-data-automation-spec.md`
- `docs/v2/09-v2-interface-and-contract-changes.md`
- `docs/reviews/task40-v2-data-intake-manifest-review-2026-06-16.md`

**Dependencies:** Checkpoint V2-A.

**Acceptance:**

- Manifest supports `CovalentInDB`, `CovPDB`, and `CovBinderInPDB` only.
- Intake modes are exactly `download` and `manual`.
- Required fields: `schema_version`, `contract_version`, `source_name`, `intake_mode`, `checksum`, `checksum_algorithm`, `parser_target`, `retrieval_date`, `license_audit_ref`, `access_notes`.
- Mode-specific fields: `source_url` required for `download`; `manual_path` required for `manual`.
- `checksum_algorithm` only `sha256`; `checksum` is 64-character lowercase hex digest.
- `parser_target` must match `source_name` (enforced by `SOURCE_TO_PARSER_TARGET` mapping).
- Unknown source names, intake modes, parser targets, or checksum algorithms fail with structured `V2_MANIFEST_*` errors.
- Missing required fields, missing mode-specific fields, and checksum format violations each produce distinct error codes.
- Validation returns `ContractEnvelope[Optional[V2DataIntakeManifest]]` with machine-readable error codes (owner `data`).
- Serialization is deterministic (sorted keys, compact separators, `ensure_ascii=False`).
- Later-task fields (`conversion_status`, `license_eligibility`, `license_status`, `staging_status`, `training_artifacts`, `training_eligible`, `training_split`) are rejected with `V2_MANIFEST_FORBIDDEN_FIELD`.
- No download, staging, conversion, license eligibility, training, or heavy dependency import is performed.
- 29 tests pass; committed fixtures cover all three sources in both download and manual modes plus negative cases.

**Verification:**

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/data/test_v2_manifests.py -q
```

**Verified on 2026-06-16:** `pytest tests/data/test_v2_manifests.py -q` — 29 passed.

**Notes:** No download or staging in this task. Task 41 (staging) and Task 43 (license audit) build on this manifest.

### Task 41: Add Local Real Data Manual Staging Fixtures (IMPLEMENTED)

**Goal:** Implement fixture-first local manual staging behavior without performing network downloads or treating local files as trusted.

**Files/modules:**

- `src/covalent_design/data/v2_intake.py`
- `src/covalent_design/data/cli/v2_stage_source.py`
- `tests/data/test_v2_intake.py`
- `tests/fixtures/v2/data_intake/`
- `docs/v2/05-v2-data-automation-spec.md`

**Dependencies:** Task 40.

**Acceptance:**

- Manual staging fixture validates manifest shape, local path, checksum metadata, source name, parser target, provenance, and license audit reference.
- Download-mode manifests may be represented only as source-origin metadata for user-provided local files, with source URL, intended output name or source artifact id, expected checksum, checksum algorithm, retrieval metadata placeholder, and license audit reference.
- Agent-managed download attempts are disabled by default.
- Any attempt to perform a real network download in Task 41 returns a structured error.
- No network access is performed in default tests or default CLI verification.
- The v2-beta real-data path is user-provided local data under `D:\codex_work\data`.
- Local files remain untrusted until manifest, checksum, parser target, license audit reference, and provenance checks pass.
- Real raw data must not be copied into tracked fixtures or committed to git.
- Output summaries are deterministic.
- No conversion output, license eligibility decision, or training artifact is produced.

**Verification:**

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/data/test_v2_intake.py -q
python -m covalent_design.data.cli.v2_stage_source --manifest tests/fixtures/v2/data_intake/download/source_manifest.json
rg -n "Local Real Data Policy|D:\\codex_work\\data|No Agent Network Download Rule|Git Tracking Rule" docs/v2/05-v2-data-automation-spec.md
```

**Verified on 2026-06-16:** `pytest tests/data/test_v2_intake.py -q` — 19 passed. CLI exits 0 for valid download-mode manifest representation, non-zero with structured JSON for unknown source.

**Notes:** Task 41 is not permission for agents to download real source data. `intake_mode = "download"` records source-origin metadata for a user-provided local file only. Automatic download is a future optional capability that would require a separate approved task, explicit user approval, and license evidence.

### Task 42: Design Data Conversion Pipeline V2 (IMPLEMENTED)

**Goal:** Convert validated local staged inputs to v1-compatible ETL inputs.

**Files/modules:**

- `src/covalent_design/data/v2_conversion.py`
- `tests/data/test_v2_conversion.py`
- `tests/fixtures/v2/data_conversion/`
- `docs/v2/05-v2-data-automation-spec.md`
- `docs/v2/09-v2-interface-and-contract-changes.md`

**Dependencies:** Tasks 40, 41, and Task 42 preserved provenance references.

**Acceptance:**

- Conversion consumes only Task 41 validated local staged inputs (`status == checksum_verified`), not remote sources.
- `pending_download` is rejected with structured `V2_CONVERSION_PENDING_DOWNLOAD` error; no placeholder records.
- Conversion output (`tuple[SourceIngestRecord, ...]`) feeds existing v1 `normalize_linkages()` and `normalize_with_identity_resolution()`.
- Source-specific records retain local path provenance (`raw_file_path`, `raw_manifest_file`), checksum reference (`raw_file_sha256`), source URL provenance when available, and license audit reference.
- Optional checksum re-verification (`reverify_checksum=True` by default) re-reads the file and recomputes SHA-256.
- Task 42 supports only `covalentin_db` parser target; `covpdb` and `covbinder_in_pdb` return `V2_CONVERSION_UNSUPPORTED_PARSER`.
- TSV parser validates required columns (`pdb_id`, `uniprot_id`, `residue`, `residue_number`, `ligand`, `ligand_name`, `bond_type`, `warhead_type`); missing columns fail with `V2_CONVERSION_MISSING_COLUMNS`.
- Individual row parse failures use `V2_CONVERSION_ROW_PARSE_ERROR` with `row_index`/`missing_fields` details; valid rows are still converted.
- Empty files and header-only files return empty tuple without error.
- Residue field parsing (`CYS145` → `CYS`, `145`) is validated; unparseable residues fail the row.
- 12 structured `V2_CONVERSION_*` error codes, all with `owner = "data"`, including forged-envelope rejection via `V2_CONVERSION_INVALID_STAGING_EVIDENCE`.
- Zero network access — enforced by socket/urllib monkeypatch in tests.
- No filesystem artifacts written during conversion (purely in-memory).
- No training artifacts, license eligibility decisions, or split assignments are produced — Task 43 owns training eligibility.
- Deterministic: same staging input produces identical `SourceIngestRecord` tuple.
- Output is JSON-serializable via `dataclasses.asdict()`.

**Verification:**

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/data/test_v2_conversion.py -q
```

**Verified on 2026-06-16:** `pytest tests/data/test_v2_conversion.py -q` — tests pass.

**Notes:** Keep source parsing separate from training. Task 42 must not perform network download and must not treat local files as trusted without Task 41 staging evidence. `pending_download` is not convertible — download the source first, then re-stage with manual intake mode. Task 42 produces `SourceIngestRecord` objects that feed directly into v1 `normalize_linkages()` and `normalize_with_identity_resolution()`.

### Task 43: Design License And Provenance Audit Gate

**Goal:** Block training use of unlicensed or unknown source data, with a
soft exemption for manually-staged data (ADR 0038).

**Files/modules:**

- `src/covalent_design/data/v2_license.py`
- `tests/data/test_v2_license.py`
- `docs/v2/05-v2-data-automation-spec.md`

**Dependencies:** Tasks 40, 41; Task 42 output may be read only for preserved-reference cross-validation.

**Acceptance:**

- License statuses are exactly `allowed`, `restricted`, `blocked`, `unknown`, `manual_exempt`.
- `allowed` passes training eligibility.
- `restricted` passes training eligibility only when restriction conditions are recorded and satisfied; the conditions are preserved in manifests and reports.
- `unknown` fails training eligibility.
- `blocked` fails training eligibility.
- `manual_exempt` passes training eligibility only for `intake_mode = "manual"` sources; records the exemption in training manifests and reports with an explicit notice that the data has not undergone third-party license verification.
- `manual_exempt` combined with `intake_mode = "download"` fails with a structured error (cross-validation rule).
- `manual_exempt` remains a distinct report category and must not be merged with `allowed`.
- Task 43 consumes Task 41 staged source manifests and staging evidence.
- Task 43 may read Task 42 conversion output only to cross-validate preserved `license_audit_ref`, checksum, local path provenance, and source provenance references.
- Task 43 does not execute conversion, raw parsing, training, sampling, or Task 44+ work.
- Staged manifest evidence and converted output reference mismatch fails with a structured cross-validation error.
- Every staged source has audit evidence or explicit blocked status.
- Missing manifest, missing checksum, missing provenance, missing license audit reference, or path outside the approved local data root fails eligibility.
- Tests cover `allowed`, `restricted`, `blocked`, `unknown`, and `manual_exempt` fixtures.
- Tests cover manual/download cross-validation, including download-mode plus `manual_exempt` rejection.
- Tests cover report output categories, including distinct `manual_exempt`.
- Tests cover audit reference preservation.
- Tests prove no data download, raw-data conversion, model training, sampling, or training artifacts are produced.
- Public API is `audit_v2_training_eligibility()` returning `ContractEnvelope[LicenseGateReport]`; `load_source_license_audit()` and `license_gate_report_to_dict()` support audit fixture loading and deterministic report serialization.
- See ADR 0038 for the full decision record.

**Verification:**

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/data/test_v2_license.py -q
python -m pytest tests/data/test_v2_manifests.py tests/data/test_v2_intake.py tests/data/test_v2_conversion.py tests/data/test_v2_license.py -q
rg -n "allowed|restricted|blocked|unknown|manual_exempt|cross-validation|report output|audit reference" tests/data/test_v2_license.py docs/v2/05-v2-data-automation-spec.md
rg -n "no download|no conversion|no training|no sampling|Task 44" docs/v2/10-v2-implementation-plan.md docs/v2/11-v2-verification-matrix.md
```

**Notes:** License audit is a hard pre-training gate for download-mode data. It evaluates Task 41 staged manifest evidence and may cross-check Task 42 preserved references, but it does not run conversion. `unknown` and `blocked` may be recorded for audit, but must not enter training. `manual_exempt` is accepted for manual-mode data only (ADR 0038). Task 43 lightweight tests currently cover five-state fixtures, restricted-condition handling, unsupported status, multi-source counts, manual/download cross-validation, manual_exempt prerequisite checks, reference mismatch errors, deterministic output, and no network/conversion/training artifacts.

### Checkpoint V2-B: Data Intake Gate

**Goal:** Confirm three-source intake and license audit can run on fixtures before real data.

**Required evidence:**

- manifest tests pass,
- intake tests pass,
- license gate tests pass,
- validated local real data from `D:\codex_work\data` is staged without network download,
- no source with unknown/blocked license enters training eligibility,
- no real raw data is committed to git.

## Phase V2-C: Chemistry / RDKit Heavy Adapters

### Task 44: Design RDKit Molecule Normalization Interface

**Goal:** Add a heavy-profile RDKit adapter for molecule parsing and normalization.

**Files/modules:**

- `src/covalent_design/chem/rdkit_normalize.py`
- `tests/chem/test_rdkit_normalize.py`
- `docs/v2/04-v2-dependency-and-environment-spec.md`

**Dependencies:** Checkpoint V2-A, Task 38.

**Acceptance:**

- Adapter is skipped or reports unavailable when RDKit is absent.
- Heavy test path validates sanitize/valence behavior when RDKit is available.
- Public output is project-owned serializable data, not raw RDKit objects.
- Default CI remains RDKit-free.
- Module import does not hard-import RDKit.
- Public API is `normalize_molecule(text, input_format="smiles")`, returning `MoleculeNormalizationResult`; `result_to_dict()` emits deterministic JSON-compatible data.
- Structured failures include RDKit unavailable, empty input, unsupported format, parse failure, and sanitize/valence failure.
- Task 44 does not implement Task 45 scaffold/descriptor/drug-likeness behavior or Task 46 PyTorch behavior.

**Verification:**

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/chem/test_rdkit_normalize.py -q
python -m pytest tests/v2/test_smoke_check.py -q
python scripts/v2_smoke_check.py --profile lightweight
```

**Task 44 verification evidence on 2026-06-18:**

- Lightweight interpreter:
  - `python -m pytest tests/chem/test_rdkit_normalize.py -q` - 6 passed, 6 skipped because RDKit is not installed in the lightweight interpreter.
  - `python -m pytest tests/v2/test_smoke_check.py -q` - 11 passed.
  - `python scripts/v2_smoke_check.py --profile lightweight` - exit 0, RDKit `not_checked`.
- Official conda-forge environment creation was attempted twice:
  - `conda create -n covalent-design-v2 -c conda-forge python=3.10 rdkit -y`
  - `conda create -n covalent-design-v2 --override-channels -c conda-forge python=3.10 rdkit -y`
  - Both attempts failed with `CondaHTTPError: HTTP 000 CONNECTION FAILED` while retrieving official conda-forge repodata.
- After user approval to use a mirror, a new dedicated environment was created without using the existing `my_rdkit` environment:
  - `conda create -n covalent-design-v2 --override-channels -c https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud/conda-forge python=3.10 rdkit -y`
  - Environment location: `D:\anaconda\envs\covalent-design-v2`
  - `conda run -n covalent-design-v2 python --version` - Python 3.10.20.
  - `conda run -n covalent-design-v2 python -c "import rdkit; print(rdkit.__version__)"` - RDKit 2026.03.1.
  - `conda install -n covalent-design-v2 --override-channels -c https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud/conda-forge pytest -y` installed pytest only into this new environment for test execution.
  - `$env:PYTHONPATH='src'; conda run -n covalent-design-v2 python -m pytest tests/chem/test_rdkit_normalize.py -q` - 12 passed.
- Heavy smoke in the same new environment:
  - `$env:PYTHONPATH='src'; conda run -n covalent-design-v2 python scripts/v2_smoke_check.py --profile heavy` - exit 1 with `exit_reason: heavy_dependency_unavailable`.
  - RDKit subcheck was `available`, version `2026.03.1`.
  - The remaining unavailable heavy dependencies were PyTorch, CUDA, PMDM, and PocketFlow; these are outside Task 44.

**Notes:** Tests are written so default CI can skip heavy checks explicitly. Task 44 is verified for the RDKit normalization adapter in a newly created dedicated conda environment. This evidence does not claim that the later full heavy stack is ready; PyTorch, CUDA, PMDM, and PocketFlow remain future task concerns.
### Task 45: Design RDKit Scaffold, Descriptor, And Drug-Likeness Interface

**Goal:** Provide chemistry diagnostics for data and generated outputs.

**Files/modules:**

- `src/covalent_design/chem/rdkit_descriptors.py`
- `src/covalent_design/chem/scaffolds.py`
- `tests/chem/test_rdkit_descriptors.py`
- `tests/chem/test_scaffolds.py`

**Dependencies:** Task 44.

**Acceptance:**

- Scaffold key derivation is source-verified or marked unavailable.
- Descriptor report is deterministic.
- Drug-likeness output is diagnostic, not a hard beta gate.
- No model forward/loss code imports RDKit.

**Verification:**

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/chem/test_rdkit_descriptors.py tests/chem/test_scaffolds.py -q
```

**Notes:** Do not implement docking here.

### Checkpoint V2-C: Chemistry Gate

**Goal:** Confirm RDKit-backed checks are isolated, optional in CI, and useful for reports.

## Phase V2-D: Tensor / PMDM / Baseline Training Foundation

### Task 46: Design PyTorch Tensor Backend Boundary

**Goal:** Add a tensor adapter seam behind existing v1 contracts.

**Files/modules:**

- `src/covalent_design/model/torch_backend.py`
- `tests/model/test_torch_backend.py`
- `docs/v2/09-v2-interface-and-contract-changes.md`

**Dependencies:** Checkpoint V2-A, Task 38.

**Acceptance:**

- `ModelBatch` converts to torch tensors only when PyTorch is available.
- Missing PyTorch is a structured heavy-profile failure.
- Public contract objects remain serializable.
- Default CI can run without PyTorch.

**Verification:**

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/model/test_torch_backend.py -q
```

**Notes:** CPU smoke precedes GPU work.

### Task 47: Design Real PMDM Adapter Smoke Path

**Goal:** Validate the real PMDM adapter against the v1 PMDM output vocabulary.

**Files/modules:**

- `src/covalent_design/model/pmdm_real_adapter.py`
- `tests/model/test_pmdm_real_adapter.py`
- `docs/v2/06-v2-training-and-tuning-spec.md`

**Dependencies:** Task 46.

**Acceptance:**

- Real PMDM import/API status is reported.
- Output includes the seven required PMDM keys.
- Optional keys follow existing config behavior.
- PMDM unavailable blocks PMDM mode but does not silently switch baseline.

**Verification:**

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/model/test_pmdm_real_adapter.py -q
```

**Notes:** No full training in this task.

### Task 48: Design Explicit Non-PMDM Baseline Fallback

**Goal:** Provide a labeled fallback only when PMDM is unavailable or deliberately bypassed.

**Files/modules:**

- `src/covalent_design/model/non_pmdm_baseline.py`
- `tests/model/test_non_pmdm_baseline.py`
- `docs/v2/09-v2-interface-and-contract-changes.md`

**Dependencies:** Task 46.

**Acceptance:**

- Baseline manifests include `baseline_mode: non_pmdm_baseline`.
- PMDM mode and baseline mode cannot be confused.
- Baseline forward path satisfies output contracts.
- Reports warn that baseline is not PMDM.

**Verification:**

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/model/test_non_pmdm_baseline.py -q
```

**Notes:** This is a fallback, not the preferred scientific path.

### Checkpoint V2-D: Tensor / PMDM / Baseline Foundation Gate

**Goal:** Confirm tensor conversion, PMDM mode, and baseline mode are all explicit before training-loop work starts.

**Required evidence:**

- PyTorch tensor adapter behavior is source-verified or reported unavailable,
- PMDM adapter smoke reports the seven required PMDM keys or structured unavailability,
- baseline fallback is labeled `non_pmdm_baseline`,
- PMDM and baseline modes cannot be silently confused.

## Phase V2-E: Training Loop And Tuning

### Task 49: Design Training Dataset V2

**Goal:** Extend training selection to use family readiness and license gates.

**Files/modules:**

- `src/covalent_design/training/v2_dataset.py`
- `tests/training/test_v2_dataset.py`
- `docs/v2/06-v2-training-and-tuning-spec.md`

**Dependencies:** Checkpoint V2-B, Task 43.

**Acceptance:**

- Training eligibility requires split policy, visual/quality policy, license audit, and family readiness.
- Q2 behavior remains explicit.
- Blocked families do not enter training.
- Exclusion summary accounts for every excluded record.

**Verification:**

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/training/test_v2_dataset.py -q
```

**Notes:** Do not compute losses here.

### Task 50: Design Training Loop V2

**Goal:** Run CPU smoke and single-GPU smoke through the selected model path.

**Files/modules:**

- `src/covalent_design/training/v2_train_loop.py`
- `src/covalent_design/training/cli/v2_train.py`
- `tests/training/test_v2_train_loop.py`
- `configs/v2_train_cpu_smoke.yml`
- `configs/v2_train_gpu_smoke.yml`

**Dependencies:** Tasks 46, 47 or 48, 49.

**Acceptance:**

- CPU smoke completes without GPU.
- GPU smoke requires CUDA and fails clearly if unavailable.
- PMDM vs baseline mode is explicit.
- Loss report and denominators are preserved.
- No publication performance claim is emitted.

**Verification:**

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/training/test_v2_train_loop.py -q
python -m covalent_design.training.cli.v2_train --config configs/v2_train_cpu_smoke.yml
```

**Notes:** Full beta run remains later.

### Task 51: Design Checkpoint And Experiment Manifest V2

**Goal:** Bind environment, data, family readiness, and training outputs in manifests.

**Files/modules:**

- `src/covalent_design/training/v2_manifests.py`
- `tests/training/test_v2_manifests.py`
- `docs/v2/09-v2-interface-and-contract-changes.md`

**Dependencies:** Task 50.

**Acceptance:**

- Manifest records environment hash, dependency lock hash, data hashes, family readiness hash, config hash, checkpoint refs, and baseline mode.
- Missing required provenance fails.
- Output is deterministic.
- No model weight files are committed as fixtures.

**Verification:**

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/training/test_v2_manifests.py -q
```

**Notes:** Defines manifest schemas only; it must not start training or commit model weights. Heavy dependency provenance is metadata and does not make default CI install heavy packages.

### Task 52: Design Hyperparameter Tuning Protocol

**Goal:** Run a tiny, budget-controlled sweep with deterministic manifests.

**Files/modules:**

- `src/covalent_design/training/v2_tuning.py`
- `src/covalent_design/training/cli/v2_tune.py`
- `tests/training/test_v2_tuning.py`
- `configs/v2_tiny_sweep.yml`

**Dependencies:** Checkpoint V2-D.

**Acceptance:**

- Trial count and runtime budget are explicit.
- Each trial records config and result hashes.
- Selected checkpoint is justified by a frozen metric.
- Failed trials are reported, not hidden.

**Verification:**

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/training/test_v2_tuning.py -q
python -m covalent_design.training.cli.v2_tune --config configs/v2_tiny_sweep.yml
```

**Notes:** Tuning is budget-controlled and manifest-driven. It must not silently promote failed trials or create untracked heavyweight outputs.

### Checkpoint V2-E: Training Loop And Tuning Gate

**Goal:** Confirm dataset eligibility, training smoke, manifest capture, and tuning selection have auditable provenance.

**Required evidence:**

- training eligibility excludes blocked sources and families,
- CPU smoke training completes or fails with a structured reason,
- GPU/full heavy training remains manual unless the heavy profile is explicitly selected,
- experiment manifests bind environment, dependency, data, family readiness, config, and checkpoint hashes,
- tiny sweep output records trial results and a selected checkpoint without hiding failed trials.

## Phase V2-F: Sampling And Evaluation

### Task 53: Design Sampling Request And Result V2

**Goal:** Extend sampling inputs/outputs for beta checkpoint evaluation.

**Files/modules:**

- `src/covalent_design/inference/v2_sampling.py`
- `tests/inference/test_v2_sampling.py`
- `docs/v2/07-v2-sampling-and-evaluation-spec.md`

**Dependencies:** Checkpoint V2-E.

**Acceptance:**

- Request includes checkpoint, split/family selector, seed, sample count, and output root.
- Result links to checkpoint and environment manifests.
- Invalid and system failures remain separated.
- Output is deterministic for deterministic smoke mode.

**Verification:**

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/inference/test_v2_sampling.py -q
```

**Notes:** Sampling remains a package-interface contract here; final export, mmCIF writing, and evaluation stay in their own task boundaries unless a later task explicitly changes that.

### Task 54: Design Deterministic Sampling Smoke Tests

**Goal:** Prove sampling can run on a small held-out/per-family fixture.

**Files/modules:**

- `tests/inference/test_v2_sampling_smoke.py`
- `tests/fixtures/v2/sampling/`
- `configs/v2_sampling_smoke.yml`

**Dependencies:** Task 53.

**Acceptance:**

- Same seed produces identical outputs.
- Held-out selector works.
- Per-family selector works.
- Failure accounting is preserved.

**Verification:**

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/inference/test_v2_sampling_smoke.py -q
```

**Notes:** Deterministic smoke proves repeatability only. It is not a scientific quality claim.

### Task 55: Design Evaluation Metrics V2

**Goal:** Add beta evaluation reports for sampled outputs.

**Files/modules:**

- `src/covalent_design/evaluation/v2_metrics.py`
- `src/covalent_design/evaluation/cli/v2_evaluate.py`
- `tests/evaluation/test_v2_metrics.py`

**Dependencies:** Tasks 53, 54.

**Acceptance:**

- Report includes validity, family metrics, covalent geometry, uniqueness/novelty when evaluable, RDKit validity when available, and failure accounting.
- `not_evaluable` is explicit when a tool is absent.
- Denominator conservation is checked.
- Output is deterministic.

**Verification:**

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/evaluation/test_v2_metrics.py -q
```

**Notes:** Metrics must distinguish unavailable evidence from negative results so optional heavy-tool gaps are not misreported as model failures.

### Task 56: Design Docking Feasibility Gate

**Goal:** Determine whether docking can be added later without making it a beta gate.

**Files/modules:**

- `src/covalent_design/evaluation/v2_docking_feasibility.py`
- `tests/evaluation/test_v2_docking_feasibility.py`
- `docs/v2/07-v2-sampling-and-evaluation-spec.md`

**Dependencies:** Task 55.

**Acceptance:**

- Engine choice, license, install path, CLI/API probe, input/output format, and runtime are reported.
- Missing engine reports `not_evaluable`.
- Docking failure does not fail v2-beta release.
- No real docking output is required.

**Verification:**

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/evaluation/test_v2_docking_feasibility.py -q
```

**Notes:** Docking remains feasibility-only and non-blocking for v2-beta unless a later accepted decision promotes it.

### Checkpoint V2-F: Sampling And Evaluation Gate

**Goal:** Confirm held-out/per-family sampling and evaluation reports are auditable.

## Phase V2-G: Optional Noncovalent Pretraining

### Task 57: Decide Noncovalent Pretraining Feasibility

**Goal:** Keep pretraining as an experimental decision, not a beta blocker.

**Files/modules:**

- `docs/v2/08-v2-noncovalent-pretraining-feasibility.md`
- `docs/reviews/v2-pretraining-feasibility-review.md`

**Dependencies:** Checkpoint V2-F.

**Acceptance:**

- Verdict is one of `accepted`, `experimental`, `rejected`, or `unresolved`.
- Data license, label compatibility, transfer hypothesis, compute cost, and evaluation plan are reviewed.
- V2-beta release does not depend on this task.

**Verification:**

```powershell
rg -n "Transfer Hypothesis|Candidate Datasets|License Status|Label Compatibility|Ablation Plan|Rejection Criteria|Final Verdict" docs/v2/08-v2-noncovalent-pretraining-feasibility.md
rg -n "accepted|experimental|rejected|unresolved" docs/v2/08-v2-noncovalent-pretraining-feasibility.md
```

**Notes:** This is a feasibility decision, not an implementation task. A positive verdict still requires a later implementation task before pretraining is treated as implemented.

### Task 58: Optional Noncovalent Pretraining Data Audit And Smoke Objective

**Goal:** If Task 57 permits, audit candidate data and define a tiny smoke objective.

**Files/modules:**

- `src/covalent_design/pretraining/`
- `tests/pretraining/`
- `docs/v2/08-v2-noncovalent-pretraining-feasibility.md`

**Dependencies:** Task 57 only if verdict permits.

**Acceptance:**

- Candidate data license audit exists.
- Smoke objective is fixture-only.
- No pretraining corpus enters v2-beta mainline.
- Negative decision is acceptable and does not block release.

**Verification:**

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/pretraining -q
```

**Notes:** Optional; skip if pretraining remains experimental without implementation approval.

## Phase V2-H: Release Gate

### Task 59: V2 Beta Release Gate

**Goal:** Decide whether v2-beta meets the minimum usable closed loop.

**Files/modules:**

- `docs/reviews/v2-beta-release-gate-review.md`
- `docs/v2/11-v2-verification-matrix.md`
- `docs/v2/12-v2-risk-register.md`

**Dependencies:** Checkpoints V2-A through V2-F. Task 57/58 are non-blocking unless explicitly promoted.

**Acceptance:**

- Environment smoke evidence exists.
- License gate evidence exists.
- Real or manual-staged data path evidence exists.
- Family readiness report exists.
- PMDM or explicit baseline training evidence exists.
- Held-out/per-family sampling and evaluation reports exist.
- No P0/P1 unresolved blocker remains.

**Verification:**

```powershell
$env:PYTHONPATH='src'
python -m compileall -q scripts src
python -m pytest -q
python -m unittest discover -s tests -t . -q
```

**Notes:** Do not enter a paper/release claim unless a separate review accepts that scope.

### Checkpoint V2-H: V2 Beta Release Gate

**Goal:** Decide whether the v2-beta closed loop is ready for the next implementation phase.

**Required evidence:**

- Checkpoints V2-A through V2-F are complete,
- optional Checkpoint V2-G is either skipped with rationale or completed as a research-only track,
- `docs/v2/11-v2-verification-matrix.md` has evidence status for every task,
- `docs/v2/12-v2-risk-register.md` has no unresolved P0/P1 blocker,
- release review records the final go/no-go verdict and scope boundaries.
