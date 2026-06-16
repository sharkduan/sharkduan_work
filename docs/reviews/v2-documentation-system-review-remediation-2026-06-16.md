# V2 Documentation System Review Remediation

Date: 2026-06-16
Scope: documentation, ADR, verification, and governance remediation only.

## Summary

This remediation addresses the P0/P1/P2 findings from `docs/reviews/v2-documentation-system-review-2026-06-16.md` without modifying implementation code, tests, CI, PMDM/PocketFlow, or generated scientific artifacts.

User decisions recorded:

- Adopt `lightweight` / `heavy` as the only v2 smoke profile vocabulary.
- Create ADR 0037 to freeze the v2 environment, heavy dependency, default CI, and source-verification boundary.

## P0 Status

| Finding | Status | Remediation |
| --- | --- | --- |
| Smoke profile naming conflict (`cpu` vs `lightweight`) | Resolved | ADR 0037 freezes `lightweight` and `heavy`; environment spec and implementation plan use `lightweight` for default smoke. |
| V2 hard decisions lacked ADR before Task 37 | Resolved | Added `docs/adr/0037-v2-environment-and-heavy-dependency-boundary.md`; indexed it in `docs/specs/key-design-decisions.md`. |

## P1 Status

| Finding | Status | Remediation |
| --- | --- | --- |
| Task 38 verification relied on `git diff` | Resolved | Verification now checks structured source-verification table fields and statuses. Added `docs/v2/dependency-source-verification.md` template. |
| Task 57 verification relied on `git diff` | Resolved | Verification now checks feasibility checklist fields and owner signoff. |
| CLI ownership drift between `scripts/v2_*` and package CLIs | Resolved | Interface spec now defines package module CLIs as public entrypoints and limits scripts to environment probes/thin helpers. Data, training, sampling, and evaluation specs now use package module command examples. |
| Early v2 interface contracts were field-list only | Resolved | Expanded `V2EnvironmentManifest`, `DependencySourceVerification`, `V2DataIntakeManifest`, and `SourceLicenseAudit` with purpose, producers/consumers, required fields, enums, errors, serialization, artifact role, and misuse guards. |
| Heavy test skip/marker policy was imprecise | Resolved | Environment spec and verification matrix now define heavy marker/skip behavior and structured unavailable statuses. |
| V2 overlay vs canonical specs relationship was undefined | Resolved | Project map and implementation plan now state that `docs/v2/` is a planning overlay until tasks land, with sync-back to canonical specs required after implementation. |

## P2 Status

| Finding | Status | Remediation |
| --- | --- | --- |
| Task 51-57 lacked notes | Resolved | Added scoped notes for Tasks 51-57. |
| V2-G optional phase lacked checkpoint semantics | Resolved | Verification matrix now records a V2-G optional pretraining decision gate. |
| Task 43 dependency omitted staged manifests | Resolved | Task 43 now depends on Tasks 40 and 41 when staged manifests exist. |
| Risk register lacked ADR/spec authority drift risk | Resolved | Added `V2-R17` governance drift risk. |

## Files Changed

- `docs/adr/0037-v2-environment-and-heavy-dependency-boundary.md`
- `docs/specs/key-design-decisions.md`
- `docs/v2/00-v2-project-map.md`
- `docs/v2/04-v2-dependency-and-environment-spec.md`
- `docs/v2/05-v2-data-automation-spec.md`
- `docs/v2/06-v2-training-and-tuning-spec.md`
- `docs/v2/07-v2-sampling-and-evaluation-spec.md`
- `docs/v2/08-v2-noncovalent-pretraining-feasibility.md`
- `docs/v2/09-v2-interface-and-contract-changes.md`
- `docs/v2/10-v2-implementation-plan.md`
- `docs/v2/11-v2-verification-matrix.md`
- `docs/v2/12-v2-risk-register.md`
- `docs/v2/dependency-source-verification.md`

## Remaining Risks

- Heavy dependency versions and APIs remain unverified until Task 38 fills the source-verification table with official evidence.
- The v2 implementation has not started; Task 37 must still implement the lightweight smoke probe and enforce ADR 0037 in code.
- Existing repository untracked governance files remain a git hygiene concern, but this remediation does not delete, stage, or commit files.

## Task 37 Readiness

Task 37 Ready: Yes.

Starting conditions:

- Use `lightweight` as the default smoke profile.
- Keep `heavy` opt-in/manual.
- Do not install or hard-import RDKit, PyTorch, CUDA, PMDM, PocketFlow, docking, or other heavy dependencies in default CI.
- Report missing heavy dependencies as structured unavailable statuses.
- Treat ADR 0037 as the environment and heavy dependency authority.

## Final Assessment

- Task 37 Ready: Yes.
- V2 docs v1-equivalent: Partial. The planning overlay is now coherent enough to start Task 37, but implementation-backed parity begins only as v2 tasks land.
- ADR governance adequate: Yes.
- Smoke profile frozen: Yes.
