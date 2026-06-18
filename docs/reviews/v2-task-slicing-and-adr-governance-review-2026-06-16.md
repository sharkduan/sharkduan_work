# V2 Task Slicing And ADR Governance Review

Date: 2026-06-16
Reviewer: Codex
Scope: documentation-only governance hardening

## Executive Summary

Overall status: PASS WITH RISKS.

Can start Task 37: Yes, only as the environment scaffold and lightweight smoke implementation described in `docs/v2/10-v2-implementation-plan.md`. Task 37 must not install heavy dependencies, train a model, download data, modify PMDM/PocketFlow, or change default CI heavy dependency behavior.

Main changes made:

- Hardened Task 37+ plan to match the v1 task/checkpoint/verification standard.
- Fixed V2 phase naming and the Task 41 self-dependency.
- Added Checkpoint V2-H for the beta release gate.
- Rebuilt the V2 verification matrix with one row per task and explicit `Mode`.
- Added `docs/v2/13-v2-task-adr-coverage.md` to map tasks to decisions, ADR coverage, and future ADR triggers.
- Indexed V2 task/ADR governance in `docs/specs/key-design-decisions.md`.

## V1 Baseline

V1 tasks are split by stable deliverable: shared contracts first, ETL and quality gates before model work, model/training smoke before inference/evaluation, and governance/release fixtures last. Each task has a goal, file/module scope, dependencies, acceptance criteria, and concrete verification.

V1 ADRs are not created per task. They are created for decisions that are cross-task and hard to reverse, such as ETL completion gates, stepwise edge supervision, generation result lifecycle, chemical-state boundaries, CI policy, and model batch contracts.

Many v1 tasks do not have ADRs because they implement accepted contracts, add fixture coverage, or wire local CLI/report behavior. This is correct: an ADR is for rationale behind a decision, not evidence that a task exists.

## V1 Equivalence Assessment

| Area | V1 Standard | V2 Status After Hardening | Verdict |
| --- | --- | --- | --- |
| Task slicing | single-goal tasks with dependencies and acceptance criteria | Task 37-59 now keep uniform fields and phase gates | pass |
| ADR governance | ADRs for durable cross-task decisions, not task count | ADR policy and coverage matrix added | pass |
| Verification matrix | every area/task has evidence and commands | every Task 37-59 has evidence, command, status, mode, and notes | pass |
| Checkpoints | each milestone has required evidence | V2-A through V2-H checkpoints present | pass |
| Interface contracts | public seams stay serializable and additive | interface spec plus coverage matrix preserve this | pass with risk |
| Risk register | risks mapped to owner tasks and mitigations | risk register now points to ADR coverage matrix for governance drift | pass |

## Task Slicing Audit

| Task | Current Problem | Split Needed | Proposed Replacement | ADR Coverage | Verification Gap |
| --- | --- | --- | --- | --- | --- |
| 37-39 | good sequence, but governance link was implicit | no | environment profile, source verification, smoke probe remain separate | ADR 0037 | matrix now includes mode/evidence |
| 40-43 | Task 41 depended on itself; phase name did not show license gate | no | Task 41 now depends on Task 40; phase renamed to Data Intake And License Gate | v1 data gate decisions plus future ADR trigger | matrix now names source set and license evidence |
| 44-45 | phase name too narrow | no | phase renamed Chemistry / RDKit Heavy Adapters | ADR 0037 for heavy boundary | matrix marks heavy-manual |
| 46-48 | mixed with later training tasks in one phase | no | phase now ends at tensor/PMDM/baseline foundation checkpoint | ADR 0037 plus PMDM key decisions | checkpoint added |
| 49-52 | training loop/tuning checkpoint was too narrow | no | phase renamed Training Loop And Tuning and checkpoint evidence expanded | existing v1 manifest/training patterns | matrix marks GPU/manual split |
| 53-56 | adequate but docking needed explicit non-blocking status | no | docking remains feasibility-only | ADR 0032 plus future ADR trigger | matrix marks `not_evaluable` and heavy-manual |
| 57-58 | adequate but needed governance trace | no | optional research status is tied to ADR trigger policy | future ADR only if promoted | matrix marks optional-research |
| 59 | release task lacked its own checkpoint | no | Checkpoint V2-H added | release aggregation, no new ADR | checkpoint evidence added |

## ADR Governance Audit

Current V2 did only add ADR 0037. After review, that is sufficient for entering Task 37 because Task 37 is exactly the environment/heavy dependency boundary implementation. It would be premature to create ADRs for data download, RDKit APIs, PMDM fallback, docking, or noncovalent pretraining before those choices are confirmed by implementation evidence.

Tasks that do not need ADR now:

- Tasks 40-43 implement source manifests, staging, conversion, and license checks under inherited v1 data-gate principles.
- Tasks 44-45 implement heavy RDKit adapters, but RDKit is not yet a canonical chemistry authority.
- Tasks 46-52 implement tensor, PMDM/baseline, training, manifest, and tuning paths behind accepted adapter/provenance patterns.
- Tasks 57-58 remain optional research and must not become release blockers without a later decision.
- Task 59 aggregates evidence and does not introduce a new technical decision.

Tasks covered by ADR 0037:

- Tasks 37-39 directly: smoke profiles, source verification, heavy/manual behavior.
- Tasks 44-56 indirectly: RDKit, PyTorch, CUDA, PMDM, PocketFlow, docking, and other heavy dependencies must remain opt-in/manual and source-verified.

Future ADRs are required only if a planned choice becomes confirmed and durable. Triggers are now listed in `docs/v2/13-v2-task-adr-coverage.md`, including data license/provenance gate promotion, serializable contract changes, PMDM replacement or baseline promotion, RDKit authority changes, docking as a required gate, noncovalent pretraining promotion, and V2 canonical spec promotion.

No new ADR was added in this pass. This is intentional and aligned with v1 governance.

## Verification Matrix Audit

Every Task 37-59 now has:

- requirement,
- evidence files,
- test or inspection command,
- blocking relationship,
- status,
- mode,
- notes.

The mode vocabulary is explicit: `lightweight`, `heavy-manual`, `network-manual`, `gpu-manual`, `docs-only`, and `optional-research`. Docs-only checks use `rg` inspections; heavy/network/GPU work remains manual.

## Remaining Risks

| Severity | Risk | Status |
| --- | --- | --- |
| P0 | heavy dependency versions, PMDM API, and data licenses are not verified | expected before Task 37; handled by Tasks 37-43 |
| P1 | V2 overlay may drift from canonical specs | mitigated by project map, key decision index, and ADR coverage matrix |
| P1 | baseline fallback could be mistaken for PMDM | mitigated by Task 48/51 manifest requirements |
| P2 | noncovalent pretraining could distract from beta | mitigated by optional-research mode and future ADR trigger |
| P2 | docking may become prematurely blocking | mitigated by feasibility-only task and ADR trigger |

## Final Verdict

Task 37 is allowed to start.

Required Task 37 boundaries:

- implement only the environment scaffold and lightweight smoke probe,
- use `--profile lightweight` and `--profile heavy`, never `--profile cpu`,
- keep default CI lightweight,
- report missing heavy dependencies as structured statuses,
- do not run RDKit/PyTorch/CUDA/PMDM/PocketFlow training paths,
- do not download real data,
- do not modify PMDM or PocketFlow,
- update V2 docs if implementation evidence changes a planned decision.
