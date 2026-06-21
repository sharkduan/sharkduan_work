# V2 Risk Register

Date: 2026-06-16
Status: hardened planning risk register

| ID | Category | Risk | Severity | Mitigation | Owner task |
| --- | --- | --- | --- | --- | --- |
| V2-R1 | dependency | PyTorch/CUDA/RDKit/PMDM versions do not solve together | P0 | source-verified environment and smoke probes | 37-39 |
| V2-R2 | dependency | PMDM API differs from fake adapter contract | P0 | Task 47 real PMDM adapter smoke boundary validates the project-owned 7+2 output vocabulary and structured `license_unknown` unavailability without importing/executing PMDM; real PMDM API execution remains blocked until license is resolved | 47 |
| V2-R3 | license | data-source license is unknown or blocked | P0 | license audit gate before training | 43 |
| V2-R4 | data | user-provided local data is missing, misplaced, or outside the approved root | P1 | local real data manual staging requires manifests under `D:\codex_work\data` and rejects paths outside approved roots | 41 |
| V2-R5 | data | real source records do not cover all six v1 families | P1 | family readiness report with partial/deferred states | 42, 49 |
| V2-R6 | license | dependency license conflicts with project use | P1 | dependency license verification | 38 |
| V2-R7 | training | GPU memory too small for selected model | P1 | CPU smoke first, tiny GPU smoke, budget limits | 50 |
| V2-R8 | training | fallback baseline is mistaken for PMDM | P1 | explicit `baseline_mode` in manifests | 48, 51 |
| V2-R9 | sampling | stochastic sampling is non-reproducible | P1 | deterministic smoke sampling and seed recording | 54 |
| V2-R10 | evaluation | unavailable tools produce fake metrics | P1 | `not_evaluable` status required | 55, 56 |
| V2-R11 | CI | heavy dependencies leak into default CI | P1 | heavy/manual profile only | 37-39 |
| V2-R12 | contract | PyTorch/RDKit objects leak into public contracts | P1 | serializable project-owned contract outputs; Task 44 normalization, Task 45 scaffold/descriptor adapters all verified as passing no-raw-RDKit-object tests | 44-46 |
| V2-R13 | scientific validity | beta results overclaimed as publication-grade | P1 | beta release review labels scope | 59 |
| V2-R14 | pretraining | noncovalent pretraining drags beta schedule | P2 | experimental non-blocking track | 57-58 |
| V2-R15 | docking | docking engine choice becomes blocking | P2 | feasibility-only gate | 56 |
| V2-R16 | governance | existing untracked governance files create noisy baseline | P2 | resolve git hygiene separately | before Task 37 if publishing |
| V2-R17 | governance | v2 overlay docs drift from canonical ADR/spec authority | P1 | ADR 0037, `docs/v2/13-v2-task-adr-coverage.md`, and explicit sync-back rule for implemented v2 decisions | 37 and each v2 implementation task |
| V2-R18 | data | accidental agent-managed network download of real source data | P1 | v2-beta default path forbids network download; automatic download remains future optional only | 41 |
| V2-R19 | data | real raw data is accidentally committed to git | P0 | raw data stays under `D:\codex_work\data`; tracked files may contain manifests/checksums only, not raw data | 41 |
| V2-R20 | data | checksum mismatch or partial local staging is treated as valid | P0 | staging fails closed on checksum mismatch, missing manifest, partial artifact, or missing provenance | 41-42 |
| V2-R21 | data | local files are treated as trusted because they are user-provided | P1 | all local real data remains untrusted until manifest, checksum, parser, license, and provenance checks pass | 41-43 |

## Dependency Risks

- Exact heavy dependency versions remain unverified.
- PMDM/PocketFlow license and environment compatibility require official source review.
- PyG or other graph dependencies may be required by PMDM.

## Data Risks

- User-provided local source availability may differ from v1 assumptions.
- Raw structure formats may require source-specific cleaning.
- Family coverage may be insufficient for some residue-reaction families.
- Local data paths may be misconfigured or point outside the approved root.
- Partial local copies may look present but fail checksum validation.

## License Risks

- Unknown or conditional licenses can block training use.
- Dependency licenses can restrict redistribution.
- Pretraining datasets are not accepted without a separate audit.
- User-provided local files with `unknown` or `blocked` license status remain audit records only and must not enter training.

## Training Risks

- PMDM adapter may not match v1 output vocabulary; Task 47 now verifies the project-owned 7+2 vocabulary boundary, but real PMDM execution/API matching remains blocked by `license_unknown`.
- GPU resources may be insufficient.
- Tiny sweep may produce weak model signal; this is acceptable for beta if pipeline health passes.

## Sampling Risks

- Sampling may fail due to checkpoint or request incompatibility.
- Invalid decode rates may dominate early beta outputs.
- Determinism must be proven before stochastic sampling is trusted.

## Pretraining Risks

- Data availability, licenses, label compatibility, transfer value, and compute cost are all unresolved.
- Pretraining is explicitly non-blocking for v2-beta.

## Scientific Validity Risks

- V2-beta is a pipeline milestone, not a publication claim.
- RDKit validity and docking feasibility are diagnostics unless promoted later.
- Drug-likeness (Lipinski Ro5, QED) is diagnostic-only per Task 45 acceptance criteria; it does not gate `status` and is not a hard beta gate.
- Family-level reports must prevent overgeneralizing from one well-covered family.

## Compute Risks

- Heavy profile requires single-GPU access.
- Default CI must remain lightweight.
- Long sweeps are out of beta scope.

## Mitigation Plan

- Push source verification and smoke probes early.
- Keep every external dependency behind a project-owned adapter.
- Require license gates before training.
- Use deterministic fixture tests before real data.
- Use user-provided local real data under `D:\codex_work\data`; do not use agent-managed network download in the v2-beta default path.
- Treat local real data as untrusted until manifest, checksum, parser, license, and provenance checks pass.
- Keep real raw data out of git.
- Keep optional research tasks out of the beta critical path.
- Drug-likeness diagnostics remain advisory; do not hard-gate on Lipinski Ro5 or QED thresholds.
- Current project sequence: Task 45 -> Checkpoint V2-C -> Phase V2-D (Task 46+), not Task 49.
