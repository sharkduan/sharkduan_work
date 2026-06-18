# V2 Task ADR Coverage

Date: 2026-06-16
Status: hardened governance matrix

## ADR Policy For V2

V2 does not use one ADR per task. This matches v1: tasks are implementation slices, while ADRs record hard-to-reverse decisions that affect multiple tasks, public contracts, dependency boundaries, release gates, or long-term scientific strategy.

A V2 task does not need its own ADR when it only implements an already accepted contract, adds fixture coverage, writes a thin CLI wrapper, creates deterministic manifests under an accepted schema, or records local evidence for a phase gate.

A V2 decision should become an ADR only when all conditions are true:

- the choice is confirmed rather than exploratory,
- reversing it later would be expensive,
- it affects more than one future task or public contract,
- future agents would likely choose the wrong path without the rationale,
- the decision is not already covered by an accepted ADR, canonical spec, or key-design-decision entry.

## What ADR 0037 Covers

ADR 0037 is the accepted authority for the V2 environment and heavy dependency boundary. It covers:

- `lightweight` and `heavy` smoke profile vocabulary,
- default CI staying lightweight,
- heavy dependency checks being opt-in/manual,
- source verification before relying on RDKit, PyTorch, CUDA, PMDM, PocketFlow, docking tools, or similar heavyweight APIs,
- structured unavailable statuses instead of import crashes,
- rejection of `cpu` as a V2 smoke profile name.

ADR 0037 does not decide exact dependency versions, RDKit APIs, PMDM adapter internals, training objective weights, docking engine choice, or whether noncovalent pretraining becomes a long-term research line.

## Current ADR Coverage

| Decision Area | Related Tasks | Current ADR / Decision Source | Status | Adequate? | Action |
| --- | --- | --- | --- | --- | --- |
| V2 environment/heavy dependency boundary | 37-39 | ADR 0037; ADR 0034 | accepted | yes | no new ADR |
| `lightweight` / `heavy` profile vocabulary | 37-39 | ADR 0037 | accepted | yes | no new ADR |
| Default CI heavy exclusion | 37-39, 44-56, 59 | ADR 0037; ADR 0034 | accepted | yes | no new ADR |
| Source verification before dependency use | 38-39, 44-47, 56 | ADR 0037; `docs/v2/04-v2-dependency-and-environment-spec.md`; `docs/v2/dependency-source-verification.md`; `docs/reviews/task38-dependency-source-verification-review-2026-06-16.md` | accepted for boundary; Task 38 records official source URLs and lock workflow, but exact solver compatibility remains unverified and PMDM is blocked by unknown license | yes for planning boundary, no for heavy-runtime evidence | create future ADR only if source verification changes release policy or lock policy becomes release-critical |
| V2 overlay vs canonical specs | all V2 tasks | `docs/v2/00-v2-project-map.md`; `docs/specs/key-design-decisions.md` | planning rule | yes for docs phase | future ADR if V2 overlay is promoted into canonical specs with incompatible changes |
| Local real data manual staging and data license gate | 40-43, 49, 59 | ADR 0026 for manual staging/no-auto-download premise; ADR 0030 for ETL manifest/checksum/provenance gates; **ADR 0038** for manual license exemption; V2 requirements and `docs/v2/05-v2-data-automation-spec.md` for local data policy | accepted as v2-beta planning policy; ADR 0038 accepted 2026-06-17 | adequate for Task 41/42/43 documentation | future ADR if automatic download becomes default, local data root becomes canonical beyond v2-beta, or license exemption boundaries change |
| V2 serializable contract boundary | 40, 43, 46, 51, 53, 55 | `docs/specs/interface-design.md`; `docs/v2/09-v2-interface-and-contract-changes.md` | additive planning | adequate for now | future ADR if V2 changes public contract compatibility or stores dependency-native objects |
| PMDM preferred path vs baseline fallback | 47-48, 50-51, 59 | ADR 0006, ADR 0008, key decision index, V2 requirements | accepted preference; fallback planned | adequate for now | future ADR if baseline becomes first-class scientific path or PMDM is replaced |
| PyTorch tensor backend boundary | 46, 50-52 | ADR 0037 and V2 interface plan | planning boundary | adequate for now | future ADR if PyTorch objects become observable public contracts |
| RDKit heavy adapter boundary | 44-45, 55 | ADR 0037 and V2 environment spec | planning boundary | adequate for now | future ADR if RDKit becomes authoritative writer, canonical scaffold algorithm, or default-CI dependency |
| Training checkpoint/experiment manifest policy | 50-52, 59 | v1 Task 25+ patterns; V2 interface plan | additive planning | adequate for now | future ADR if checkpoint identity or promotion policy becomes release-critical |
| Sampling/evaluation denominator policy | 53-56, 59 | ADR 0032; v1 verification matrix | accepted | yes | no new ADR |
| Covalent docking score as main covalent metric candidate | 55-56, 59 | ADR 0032 for lifecycle and docking score eligibility; V2 evaluation spec | accepted as reportable only when eligible | yes for beta | future ADR if docking becomes mandatory beta or publication gate |
| Noncovalent pretraining experimental/non-blocking policy | 57-58 | `docs/v2/08-v2-noncovalent-pretraining-feasibility.md`; V2 requirements | planning decision | adequate for now | future ADR if promoted from optional research to long-term project track |

## Task-Level ADR Need

| Task Range | ADR Need | Rationale |
| --- | --- | --- |
| 37-39 | covered by ADR 0037 | environment profile, heavy/manual boundary, source-verification boundary are already accepted |
| 40-43 | ADR 0038 for manual license exemption | tasks implement user-provided local real data staging and license gates; ADR 0038 narrows ADR 0026 to permit `manual_exempt` for manual-mode data |
| 44-45 | no new ADR now | RDKit use remains a heavy adapter, not a default dependency or canonical chemistry authority |
| 46-48 | no new ADR now | PyTorch/PMDM/baseline work is behind adapters and manifests; replacement of PMDM would trigger ADR later |
| 49-52 | no new ADR now | dataset, training loop, manifest, and tuning tasks implement accepted gate and provenance patterns |
| 53-56 | covered by ADR 0032 plus ADR 0037 where heavy tools appear | denominator conservation, result lifecycle, docking eligibility, and heavy-tool unavailability already have decision sources |
| 57-58 | no new ADR now | noncovalent pretraining remains optional research and is not a v2-beta gate |
| 59 | no new ADR now | release gate aggregates task evidence and risk status; it does not introduce a new decision by itself |

## Future ADR Triggers

| Trigger | Related Task | Create ADR When | Suggested ADR Title |
| --- | --- | --- | --- |
| Automatic downloader becomes default source path | future optional task | source access, license, retry/cache policy, and redistribution implications are confirmed and the project wants agents to manage download | Placeholder title: V2 Data Acquisition And Provenance Policy |
| Local real data root becomes canonical beyond v2-beta | 41-43 | `D:\codex_work\data` is promoted from v2-beta operational policy to long-term project contract | Placeholder title: V2 Local Real Data And Provenance Policy |
| License status semantics change training eligibility (beyond ADR 0038) | 43, 49 | `restricted`, `unknown`, or `blocked` behavior changes canonical release policy beyond the exemption already granted by ADR 0038 | Placeholder title: V2 Data License And Provenance Gate |
| Lock workflow becomes release-critical | 38 | lock-file generation command, version pinning policy, and environment reproducibility requirements become canonical release policy | Placeholder title: V2 Environment Lock And Reproducibility Policy |
| Dependency-native objects cross package seams | 44-46, 51, 53, 55 | RDKit or PyTorch objects become observable public contracts instead of adapter internals | Placeholder title: V2 Serializable Contract Boundary |
| PMDM is replaced or baseline becomes co-equal | 47-48, 50, 59 | `non_pmdm_baseline` is promoted beyond explicit fallback/smoke use | Placeholder title: V2 PMDM And Baseline Training Path Policy |
| RDKit becomes canonical scaffold or writer authority | 44-45, 55 | RDKit output determines primary splits, exports, or default-CI checks | Placeholder title: V2 RDKit Authority Policy |
| Docking becomes a required beta or publication gate | 56, 59 | docking engine, protocol, license, and runtime are source-verified and made blocking | Placeholder title: V2 Docking Gate Policy |
| Noncovalent pretraining becomes long-term track | 57-58 | feasibility verdict is `accepted` and the track gates future release or research claims | Placeholder title: V2 Noncovalent Pretraining Research Track |
| V2 overlay is merged into canonical specs | 59 | V2 decisions stop being planning overlays and change the canonical implementation contract | Placeholder title: V2 Canonical Spec Promotion Policy |

## Current ADR Decision

ADR 0038 was created on 2026-06-17 to record the manual data license audit
exemption.  It refines ADR 0026's manual-staging/no-auto-download premise
by introducing `manual_exempt` as a new license status that allows
manual-mode data to enter training without formal third-party license
audit, while preserving the full audit trail and keeping download-mode
license enforcement unchanged.  Future ADR trigger titles above are
placeholders; concrete ADR numbers are assigned only when a future ADR is
actually created.
