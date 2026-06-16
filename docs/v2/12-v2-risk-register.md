# V2 Risk Register

Date: 2026-06-16
Status: hardened planning risk register

| ID | Category | Risk | Severity | Mitigation | Owner task |
| --- | --- | --- | --- | --- | --- |
| V2-R1 | dependency | PyTorch/CUDA/RDKit/PMDM versions do not solve together | P0 | source-verified environment and smoke probes | 37-39 |
| V2-R2 | dependency | PMDM API differs from fake adapter contract | P0 | real PMDM adapter smoke before training | 47 |
| V2-R3 | license | data-source license is unknown or blocked | P0 | license audit gate before training | 43 |
| V2-R4 | data | automatic download is unavailable | P1 | manual staging manifest fallback | 41 |
| V2-R5 | data | real source records do not cover all six v1 families | P1 | family readiness report with partial/deferred states | 42, 49 |
| V2-R6 | license | dependency license conflicts with project use | P1 | dependency license verification | 38 |
| V2-R7 | training | GPU memory too small for selected model | P1 | CPU smoke first, tiny GPU smoke, budget limits | 50 |
| V2-R8 | training | fallback baseline is mistaken for PMDM | P1 | explicit `baseline_mode` in manifests | 48, 51 |
| V2-R9 | sampling | stochastic sampling is non-reproducible | P1 | deterministic smoke sampling and seed recording | 54 |
| V2-R10 | evaluation | unavailable tools produce fake metrics | P1 | `not_evaluable` status required | 55, 56 |
| V2-R11 | CI | heavy dependencies leak into default CI | P1 | heavy/manual profile only | 37-39 |
| V2-R12 | contract | PyTorch/RDKit objects leak into public contracts | P1 | serializable project-owned contract outputs | 44-46 |
| V2-R13 | scientific validity | beta results overclaimed as publication-grade | P1 | beta release review labels scope | 59 |
| V2-R14 | pretraining | noncovalent pretraining drags beta schedule | P2 | experimental non-blocking track | 57-58 |
| V2-R15 | docking | docking engine choice becomes blocking | P2 | feasibility-only gate | 56 |
| V2-R16 | governance | existing untracked governance files create noisy baseline | P2 | resolve git hygiene separately | before Task 37 if publishing |
| V2-R17 | governance | v2 overlay docs drift from canonical ADR/spec authority | P1 | ADR 0037 plus explicit sync-back rule for implemented v2 decisions | 37 and each v2 implementation task |

## Dependency Risks

- Exact heavy dependency versions remain unverified.
- PMDM/PocketFlow license and environment compatibility require official source review.
- PyG or other graph dependencies may be required by PMDM.

## Data Risks

- Source availability may differ from v1 assumptions.
- Raw structure formats may require source-specific cleaning.
- Family coverage may be insufficient for some residue-reaction families.

## License Risks

- Unknown or conditional licenses can block training use.
- Dependency licenses can restrict redistribution.
- Pretraining datasets are not accepted without a separate audit.

## Training Risks

- PMDM adapter may not match v1 output vocabulary.
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
- Keep optional research tasks out of the beta critical path.
