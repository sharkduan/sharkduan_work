# V2 Implementation Plan

Date: 2026-06-16
Status: hardened v2-beta task plan
Target: `v2-beta`

## Overview

Task 37+ continues after v1 Tasks 1-36. The plan keeps v2-beta focused on one minimum usable closed loop: real environment, real or manually staged data, ETL and family readiness, PMDM or explicit fallback smoke, small training, sampling, and evaluation.

Each task has one primary goal and should fit in one focused session. Heavy dependency work starts with smoke probes before real training.

ADR 0037 is the authority for v2 environment boundaries, heavyweight optional dependencies, and the frozen `lightweight` / `heavy` smoke profile vocabulary. V2 docs are planning overlays until their tasks land; implemented v2 decisions must be synchronized back into canonical specs during or after the relevant implementation task.

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
rg -n "dependency / package|official source URL|license status|verification date|owning task" docs/v2/dependency-source-verification.md
rg -n "verified|unverified|blocked|not required yet" docs/v2/dependency-source-verification.md
```

**Notes:** Do not cite blogs, StackOverflow, or AI summaries as authority.

### Task 39: Add RDKit/PyTorch/CUDA Smoke Probe Spec

**Goal:** Make heavy dependency probes executable and separately skippable.

**Files/modules:**

- `scripts/v2_smoke_check.py`
- `tests/v2/test_smoke_check.py`
- `docs/v2/11-v2-verification-matrix.md`

**Dependencies:** Tasks 37, 38.

**Acceptance:**

- Lightweight probe passes without RDKit/PyTorch installed.
- Heavy probe reports PyTorch import, CUDA availability, RDKit import, PMDM path/import, and project import.
- Probe output is deterministic JSON.
- Missing heavy dependency returns non-zero only in heavy mode.

**Verification:**

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/v2/test_smoke_check.py -q
python scripts/v2_smoke_check.py --profile lightweight
```

**Notes:** Heavy profile may be manual until the environment is available.

### Checkpoint V2-A: Environment Gate

**Goal:** Confirm the v2-beta environment plan is executable before data or training work.

**Required evidence:**

- environment scaffold exists,
- source verification document exists,
- lightweight smoke passes,
- heavy smoke behavior is documented.

## Phase V2-B: Data Automation

### Task 40: Design Real Data Intake Manifest V2

**Goal:** Define the source manifest schema for automatic and manual raw data intake.

**Files/modules:**

- `src/covalent_design/data/v2_manifests.py`
- `tests/data/test_v2_manifests.py`
- `docs/v2/05-v2-data-automation-spec.md`

**Dependencies:** Checkpoint V2-A.

**Acceptance:**

- Manifest supports CovalentInDB, CovPDB, and CovBinderInPDB only.
- Manifest records mode, source URL or manual path, checksum, parser target, retrieval date, and license audit ref.
- Unknown source names fail.
- Missing checksum fails.

**Verification:**

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/data/test_v2_manifests.py -q
```

**Notes:** No real download yet.

### Task 41: Add Source Download And Manual Staging Fixtures

**Goal:** Implement fixture-first download/manual staging behavior.

**Files/modules:**

- `src/covalent_design/data/v2_intake.py`
- `src/covalent_design/data/cli/v2_stage_source.py`
- `tests/data/test_v2_intake.py`
- `tests/fixtures/v2/data_intake/`

**Dependencies:** Tasks 40, 41.

**Acceptance:**

- Manual staging fixture validates path and checksum.
- Download mode can be represented without network in tests.
- Download attempts are disabled unless explicitly requested.
- Output manifests are deterministic.

**Verification:**

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/data/test_v2_intake.py -q
python -m covalent_design.data.cli.v2_stage_source --manifest tests/fixtures/v2/data_intake/manual/source_manifest.json
```

**Notes:** Real network download requires separate approval and license evidence.

### Task 42: Design Data Conversion Pipeline V2

**Goal:** Connect v2 intake manifests to v1-compatible ETL inputs.

**Files/modules:**

- `src/covalent_design/data/v2_conversion.py`
- `tests/data/test_v2_conversion.py`
- `docs/v2/05-v2-data-automation-spec.md`

**Dependencies:** Tasks 40, 41.

**Acceptance:**

- Conversion output can feed existing v1 ingestion/normalization.
- Source-specific records retain provenance.
- Schema normalization failures are structured.
- No training artifacts are produced.

**Verification:**

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/data/test_v2_conversion.py -q
```

**Notes:** Keep source parsing separate from training.

### Task 43: Design License And Provenance Audit Gate

**Goal:** Block training use of unlicensed or unknown source data.

**Files/modules:**

- `src/covalent_design/data/v2_license.py`
- `tests/data/test_v2_license.py`
- `docs/v2/05-v2-data-automation-spec.md`

**Dependencies:** Task 40.

**Acceptance:**

- License statuses are `allowed`, `allowed_with_conditions`, `unknown`, `blocked`.
- `unknown` and `blocked` fail training eligibility.
- `allowed_with_conditions` preserves conditions in manifests.
- Every staged source has audit evidence or explicit blocked status.

**Verification:**

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/data/test_v2_license.py -q
```

**Notes:** License audit is a hard pre-training gate. It depends on Task 41 when staged manifests exist, because the gate must evaluate the same manifests that later conversion and training eligibility consume.

### Checkpoint V2-B: Data Intake Gate

**Goal:** Confirm three-source intake and license audit can run on fixtures before real data.

**Required evidence:**

- manifest tests pass,
- intake tests pass,
- license gate tests pass,
- no source with unknown/blocked license enters training eligibility.

## Phase V2-C: RDKit Integration

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

**Verification:**

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/chem/test_rdkit_normalize.py -q
```

**Notes:** Tests must be written so default CI can skip heavy checks explicitly.

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

## Phase V2-D: PyTorch Training Foundation

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

### Checkpoint V2-D: Training Foundation Gate

**Goal:** Confirm tensor, model, dataset, and training smoke paths are ready for tuning.

## Phase V2-E: Hyperparameter Tuning

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

### Checkpoint V2-E: Tuning Gate

**Goal:** Confirm one selected checkpoint exists with auditable provenance.

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
