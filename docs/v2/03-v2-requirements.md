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
- Use user-provided local real data as the v2-beta mainline data acquisition path.
- Use `D:\codex_work\data` as the local raw data root.
- Support manual raw-file staging from the local data root.
- Do not perform agent-managed network download of real source data by default.
- Treat automatic download as a future optional capability or explicitly approved future task, not the current v2-beta default path.
- Require checksums, source URLs or manual-source notes, retrieval date, parser target, local path, and license audit status.
- Treat local files as untrusted until manifest, checksum, parser validation, license, and provenance checks pass.
- Do not let `unknown` or `blocked` license status enter training.  For
  `intake_mode = "manual"` data, `manual_exempt` is an accepted license
  status that records the exemption without blocking training (ADR 0038).
- `restricted` license status may enter training only when conditions are
  recorded and satisfied, and those conditions remain reportable.
- `manual_exempt` does not bypass manifest, checksum, parser target, local
  path, source provenance, or license audit reference validation.
- Do not commit real raw data to git.

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

## Governance Requirements

- Task 37+ must keep the V1 task standard: one primary deliverable, explicit dependencies, checkable acceptance criteria, verification command, and phase checkpoint evidence.
- ADRs are decision-scoped, not task-scoped. A task needs ADR coverage only when it depends on a hard-to-reverse cross-task decision.
- ADR 0037 covers the V2 environment boundary, heavy dependency boundary, source-verification boundary, and `lightweight` / `heavy` smoke profile vocabulary.
- `docs/v2/13-v2-task-adr-coverage.md` must identify which tasks are covered by ADR 0037, which inherit v1 ADRs, and which future conditions would trigger a new ADR.
- No V2 implementation task may promote optional noncovalent pretraining, docking, or a non-PMDM baseline into a beta blocker without a future explicit decision record.

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
- Data intake emits deterministic manifests for user-provided local real data and manual staging.
- Family readiness report exists before training.
- PMDM path or `non_pmdm_baseline` is explicit in manifests.
- Training and sampling complete under the beta budget.
- Evaluation reports deterministic denominators and failure reasons.

## Open Verification Items

- Official source URLs and licenses for CovalentInDB, CovPDB, and CovBinderInPDB.
- User-provided local raw data manifests, checksums, and provenance under `D:\codex_work\data`.
- PMDM and PocketFlow license and compatibility status.
- Exact PyTorch, CUDA, RDKit, PyG, and Conda/Mamba versions.
- Docking engine choice, license, and runtime feasibility.
- Real-data coverage for all six v1 families.
