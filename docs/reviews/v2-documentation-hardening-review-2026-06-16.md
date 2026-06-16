# V2 Documentation Hardening Review

Date: 2026-06-16
Scope: `docs/v2/*`

## Overall Verdict

PASS

The v2 documentation now reaches a v1-like planning granularity for Task 37+. It preserves the user-confirmed `v2-beta` target, records noncovalent pretraining as experimental/non-blocking, and avoids presenting unverified dependency claims as accepted facts.

## V1-Level Completeness Assessment

| Area | Assessment |
| --- | --- |
| Task granularity | PASS: Tasks 37-59 include Goal, Files/modules, Dependencies, Acceptance, Verification, and Notes where relevant. |
| Phase/checkpoint structure | PASS: V2-A through V2-H checkpoints are defined. |
| Verification matrix | PASS: every Task 37-59 has requirement, evidence files, command, blocking target, status, and notes. |
| Interface/contracts | PASS: proposed v2 contracts are additive and preserve v1 seams. |
| Dependency boundary | PASS: RDKit/PyTorch/CUDA/PMDM are heavy-profile only and require source verification. |
| Data boundary | PASS: three v1 sources only; automatic download and manual staging are separated. |
| Training/sampling boundary | PASS: CPU smoke precedes GPU/full, tiny sweep precedes broader tuning, deterministic sampling precedes stochastic sampling. |
| Pretraining | PASS: experimental, not mainline, not blocking v2-beta. |

## Remaining Gaps

- Exact official dependency sources and versions are intentionally unresolved until Task 38.
- Exact real source URLs and license terms are intentionally unresolved until Task 43.
- Docking engine choice remains feasibility-only.
- Existing repository governance/untracked file state is outside this v2 documentation hardening scope.

## Findings

### P0

None.

### P1

None.

### P2

- V2 task numbers are planned but not merged into `docs/specs/implementation-plan.md`. This is intentional because the user confirmed Task 37+ should remain in `docs/v2/` until v2-beta baseline approval.
- Heavy verification commands are planned shapes, not implemented commands. Each implementing task must freeze exact command names.

## Required User Decisions

No blocking user decisions remain for documentation hardening.

Recorded decisions:

- Formal target is `v2-beta`.
- Minimum closed loop includes environment, data, ETL, family readiness, PMDM or explicit fallback, small training, sampling, and evaluation.
- RDKit remains data/evaluation heavy-profile support only.
- PyTorch remains model/training heavy-profile support only.
- Mainline data sources are CovalentInDB, CovPDB, and CovBinderInPDB.
- License audit is a hard pre-training gate.
- Noncovalent pretraining is experimental and non-blocking.
- Task 37+ remains in `docs/v2/` for now.

## Task 37+ Readiness

Task 37 may start after the user accepts the v2 documentation baseline.

Task 37 should not install dependencies silently. It should create the environment scaffold and smoke-check interface, then report dependency availability.

## Whether Task 37 May Start

Yes, from a documentation-readiness standpoint.

Recommended next action: start Task 37: Finalize V2 Environment Policy And Scaffold.
