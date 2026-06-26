# V2 Risk Register

Date: 2026-06-16
Status: hardened planning risk register

| ID | Category | Risk | Severity | Mitigation | Owner task |
| --- | --- | --- | --- | --- | --- |
| V2-R1 | dependency | PyTorch/CUDA/RDKit/PMDM versions do not solve together | P0 | source-verified environment and smoke probes | 37-39 |
| V2-R2 | dependency | PMDM API differs from fake adapter contract | P0 | Task 47 real PMDM adapter smoke boundary validates the project-owned 7+2 output vocabulary and structured `license_unknown` unavailability without importing/executing PMDM; real PMDM API execution remains blocked until license is resolved | 47 |
| V2-R3 | license | data-source license is unknown or blocked | P0 | license audit gate before training | 43 |
| V2-R4 | data | user-provided local data is missing, misplaced, or outside the approved root | P1 | local real data manual staging requires manifests under `D:\codex_work\data` and rejects paths outside approved roots | 41 |
| V2-R5 | data | real source records do not cover all six v1 families | P1 | family readiness report with partial/deferred states; Task 49 excludes blocked/deferred/partial/missing families from training eligibility | 42, 49 |
| V2-R6 | license | dependency license conflicts with project use | P1 | dependency license verification | 38 |
| V2-R7 | training | GPU memory too small for selected model | P1 | CPU smoke first, tiny GPU smoke, budget limits | 50 |
| V2-R8 | training | fallback baseline is silently activated, or output is mistaken for real PMDM | P1 | Task 48 `forward_non_pmdm_baseline()` rejects calls without explicit `baseline_mode=non_pmdm_baseline`; Task 47 `forward_pmdm_real()` returns `PMDM_REAL_LICENSE_BLOCKED` without switching paths; Task 51 manifests preserve `baseline_mode=non_pmdm_baseline`, `is_pmdm=false`, and reject unavailable PMDM as successful PMDM | 47, 48, 51 |
| V2-R9 | sampling | stochastic sampling is non-reproducible | P1 | Task 53 records deterministic request/result serialization, seed, and failure accounting; Task 54 proves deterministic fixture-mode smoke execution with same-seed/different-seed tests, selector coverage, and count conservation. Real stochastic model sampling reproducibility remains future Task 55+ review evidence. | 53-55 |
| V2-R10 | evaluation | unavailable tools produce fake metrics | P1 | Task 55 reports optional geometry, uniqueness/novelty, and RDKit evidence as `not_evaluable` when absent; Task 56 docking feasibility remains separate and non-blocking | 55, 56 |
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
| V2-R22 | license | manual_exempt source-level audit failure is treated as eligible | P0 | Task 49 now excludes `manual_exempt` with `training_eligible=false` as `excluded_manual_exempt_audit_failed` and preserves license `reason_codes` on excluded records | 43, 49 |
| V2-R23 | training | Task 50 bypasses V2 eligibility by reusing the v1 `prepare_dataset()` path | P1 | Task 50 now consumes Task 49 `V2TrainingDatasetIndex` via `prepare_v2_dataset()` and tests reject records-only configs that omit Task 49 gate reports; source inspection guards against direct v1 eligibility calls in `v2_train_loop.py` | 50 |
| V2-R24 | training | artifact path/readability/checksum validation is assumed done by Task 49 | P1 | Task 49 validates minimum artifact role presence only; Task 50 now validates existence, readability, byte size, and checksum before tensor construction with structured tests for each failure | 49, 50 |
| V2-R25 | data | malformed or zero `linkage_count` is treated as single-linkage | P2 | deferred; current Task 49 behavior remains unchanged until a later policy decision and regression tests define malformed linkage semantics | later |
| V2-R26 | training | missing dependency lock is recorded as a verified lock hash | P1 | Task 51 uses explicit dependency-lock provenance; `not_available` requires a reason and PMDM manifests require an available verified lock hash | 51 |
| V2-R27 | training | tiny tuning hides failed trials or promotes a failed trial as selected | P1 | Task 52 records every trial result with status and structured errors; selection filters to successful trials only and reports `V2_TUNE_NO_SUCCESSFUL_TRIALS` when none succeed | 52 |
| V2-R28 | training | tuning output is non-deterministic across repeated runs | P1 | Task 52 freezes trial count, seed order, Task 49 gate input references, selection metric, per-trial hashes, and sweep hash; tests compare repeated CLI/API output | 52 |
| V2-R29 | training | full-beta harness reads raw real-data roots without explicit controller authorization | P0 | Task 52.5 fixture mode uses only explicit fixture paths; heavy_manual mode fails with `V2_FULL_BETA_REAL_DATA_NOT_AUTHORIZED` unless authorization is explicit | 52.5 |
| V2-R30 | training | fixture-mode full-beta evidence is overclaimed as real heavy training | P1 | `V2FullBetaSummary` records `execution_mode`, `real_data_accessed`, `outputs_written`, nested training/tuning summaries, and structured heavy-unavailable failures | 52.5 |
| V2-R31 | training | checkpoint payloads or local heavy outputs are accidentally tracked | P1 | Task 52.5 default policy is `manifest_ref_only`; tests assert no output directory is written by default and selected checkpoint is metadata only | 52.5 |

## Dependency Risks

- Exact heavy dependency versions remain unverified.
- PMDM/PocketFlow license and environment compatibility require official source review.
- PyG or other graph dependencies may be required by PMDM.

## Data Risks

- User-provided local source availability may differ from v1 assumptions.
- Raw structure formats may require source-specific cleaning.
- Family coverage may be insufficient for some residue-reaction families; Task 49 excludes blocked/deferred/partial/missing family readiness from training eligibility.
- Local data paths may be misconfigured or point outside the approved root.
- Partial local copies may look present but fail checksum validation.

## License Risks

- Unknown or conditional licenses can block training use.
- Dependency licenses can restrict redistribution.
- Pretraining datasets are not accepted without a separate audit.
- User-provided local files with `unknown` or `blocked` license status remain audit records only and must not enter training.
- Task 49 keeps `manual_exempt` distinct from `allowed`; it can enter training eligibility only when manual intake is proven by both record metadata and license report evidence and the license report has `training_eligible=true`.

## Training Risks

- Baseline fallback may be accidentally selected when PMDM is intended; Task 48 guards this with explicit `baseline_mode` selection and structured rejection for `pmdm`, `not_selected`, or unknown modes. Task 50 keeps PMDM and baseline paths explicit and verifies that PMDM blocked status does not auto-switch to baseline.

- PMDM adapter may not match v1 output vocabulary; Task 47 now verifies the project-owned 7+2 vocabulary boundary, but real PMDM execution/API matching remains blocked by `license_unknown`.
- GPU resources may be insufficient.
- Tiny sweep may produce weak model signal; this is acceptable for beta if pipeline health passes. Task 52 selects only by the frozen smoke metric and records failed trials explicitly.
- Full-beta harness fixture success is not itself a publication-quality training claim. Task 52.5 records fixture/heavy mode, output-write status, and real-data-access status so reviewers can distinguish harness evidence from authorized heavy execution.

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
- Current project sequence after Checkpoint V2-D is Task 49 -> Task 50; do not enter Task 50 until Task 49 verification and review are complete. Task 50 must consume the Task 49 V2 dataset index and validate artifact path/readability/checksum before tensor construction.
