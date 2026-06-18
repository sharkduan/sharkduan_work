# V2 Intent

Date: 2026-06-16
Status: accepted planning intent
Target label: `v2-beta`

## Goal

V2-beta turns the v1 contract-complete scaffold into a real, reproducible, single-GPU experimental pipeline while preserving v1's release-gate discipline.

The main outcome is not a publication-grade model. The main outcome is a stable pipeline that can:

- create and validate a real environment,
- acquire or stage real data from the three v1 sources,
- run ETL and family readiness checks,
- integrate a PMDM-compatible backbone or explicitly labeled fallback baseline,
- train and tune within a small budget,
- sample held-out examples,
- evaluate validity and family-level behavior,
- produce auditable reports.

## User

The immediate user is the project maintainer/operator who needs to run the covalent inhibitor pipeline from source data through training and sampling without relying on hidden manual steps. A later scientific user can consume the reports, but v2-beta is primarily an operator-facing reproducibility milestone.

## Why Now

Tasks 1-36 completed the v1 contract scaffold. The next bottleneck is no longer schema design; it is proving that the contracts survive real dependencies, real source data, and a real training/sampling path.

## Confirmed User Decisions

- Target stage: `v2-beta`.
- Primary environment: Linux/WSL2 plus Conda/Mamba and one CUDA GPU.
- Windows role: lightweight checks only.
- Data sources: only CovalentInDB, CovPDB, and CovBinderInPDB for v2-beta mainline.
- Data acquisition: user-provided local real data under `D:\codex_work\data`, staged manually with manifest, checksum, license, and provenance checks.
- Dependency strategy: project-level `environment.yml` and smoke check script.
- Backbone: real PMDM preferred; project PyTorch fallback allowed only as `non_pmdm_baseline`.
- RDKit: required for basic chemical validity and scaffold/chemistry checks.
- Families: six v1 residue-reaction families are the intended scope, gated by family-level readiness.
- Tuning: small budget-controlled sweep.
- Sampling: held-out split plus per-family stratified sampling.
- Docking: feasibility gate first; not a required v2-beta release gate.
- Delivery priority: pipeline stability first, model effect second.
- License policy: strict source and dependency license audit, with ADR 0038
  preserving a manual-mode `manual_exempt` record-and-pass exception while
  keeping download-mode, `unknown`, and `blocked` gates strict.
- Noncovalent pretraining: experimental research track, not v2-beta mainline.
- Planning decisions: record as planning docs, not irreversible ADRs.

## Non-Goals

- No Task 37+ implementation in this documentation task.
- No RDKit, PyTorch, CUDA, PMDM, PocketFlow, or docking installation here.
- No publication-grade performance promise.
- No new data source beyond the three v1 sources.
- No multi-GPU or cluster training requirement.
- No production serving API.
- No final paper claims.
- No noncovalent pretraining in the v2-beta critical path.

## Success Definition

V2-beta is successful when a fresh Linux/WSL2 single-GPU environment can execute a documented heavy profile that proves:

- dependencies solve and smoke checks pass,
- source data or manual raw-file fallback is staged with license evidence or
  an ADR 0038 manual exemption audit record,
- ETL reports family-level readiness,
- model training runs on the agreed backbone path,
- sampling and evaluation produce deterministic, auditable outputs,
- failures are explicit rather than silent.
