# V2 Requirements

Date: 2026-06-16
Status: hardened planning requirements
Target: `v2-beta`

## Version Policy

The only formal target in this plan is `v2-beta`. The plan uses internal checkpoints to reduce risk, but it does not create separate public `v2-alpha` or `v2-release` commitments.

## V2-Beta Requirements

### Environment

- Provide a project-level Linux/WSL2 Conda/Mamba environment spec.
- Add a smoke script that reports Python, PyTorch, CUDA, RDKit, PMDM, and project import status.
- Keep Windows limited to lightweight checks.
- Keep default CI free of RDKit, PyTorch, CUDA, PMDM, PocketFlow, and docking engines.
- Add a heavy/manual profile for dependency and GPU checks.

### Data Automation

- Cover only CovalentInDB, CovPDB, and CovBinderInPDB.
- Support automatic download when source access and license are verified.
- Support manual raw-file staging when download is blocked or unreliable.
- Require checksums, source URLs or manual-source notes, retrieval date, parser target, and license audit status.
- Do not let `unknown` or `blocked` license status enter training.

### ETL And Family Readiness

- Reuse v1 ETL contracts and artifact gates.
- Emit family-level readiness for the six v1 residue-reaction families.
- Mark families as `ready`, `partial`, `blocked`, or `deferred`.
- Prevent silent training on insufficient or blocked families.

### RDKit Heavy-Profile Use

- Use RDKit for molecule normalization, sanitize/valence checks, scaffold key implementation, basic descriptors, and result validity reporting.
- Do not use RDKit in model forward, loss computation, or default CI.
- Do not promote any RDKit API claim without official source verification.

### PyTorch / PMDM Heavy-Profile Use

- Use PyTorch for real tensor conversion, PMDM adapter smoke, model forward, training loop, and checkpoint smoke.
- Prefer real PMDM. If unavailable, use a clearly labeled `non_pmdm_baseline`.
- Do not silently fall back from PMDM to the baseline.
- Preserve v1 serializable contract objects at module seams.

### Training And Tuning

- Run CPU/smoke training before GPU/full heavy training.
- Run a small budget-controlled tuning protocol.
- Record run manifests, environment hashes, data hashes, family readiness hashes, and checkpoint metadata.
- Do not claim publication-grade performance.

### Sampling And Evaluation

- Provide deterministic smoke sampling before stochastic sampling.
- Evaluate held-out split and per-family strata.
- Report validity, covalent edge diagnostics, geometry diagnostics, family metrics, uniqueness/novelty, RDKit basic validity, and failure accounting.
- Treat docking as feasibility-only unless later promoted by a source-verified decision.

## Optional Research Track

Noncovalent pretraining is experimental and non-blocking for v2-beta. It requires a separate license audit, label compatibility analysis, transfer hypothesis, ablation plan, and rejection criteria before implementation.

## Non-Goals

- No new mainline data source beyond the three v1 sources.
- No multi-GPU or distributed training requirement.
- No production serving API.
- No full docking implementation as a beta gate.
- No paper-level result claim.
- No default-CI heavy dependency expansion.

## Acceptance Criteria

- V2 heavy environment can be created or fails with documented dependency reasons.
- Smoke script reports all required dependency statuses.
- License audit gates source use before training.
- Data intake emits deterministic manifests for download or manual staging.
- Family readiness report exists before training.
- PMDM path or `non_pmdm_baseline` is explicit in manifests.
- Training and sampling complete under the beta budget.
- Evaluation reports deterministic denominators and failure reasons.

## Open Verification Items

- Official source URLs and licenses for CovalentInDB, CovPDB, and CovBinderInPDB.
- PMDM and PocketFlow license and compatibility status.
- Exact PyTorch, CUDA, RDKit, PyG, and Conda/Mamba versions.
- Docking engine choice, license, and runtime feasibility.
- Real-data coverage for all six v1 families.
