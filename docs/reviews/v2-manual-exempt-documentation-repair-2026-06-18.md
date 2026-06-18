# V2 Manual Exempt Documentation Repair

Date: 2026-06-18
Scope: documentation-only repair for ADR 0038 and downstream `manual_exempt` Task 43 readiness.

## Summary

Repair status: complete for the documentation blockers identified in `docs/reviews/v2-manual-exempt-documentation-review-2026-06-18.md`.

Whether Task 43 may start: yes, from a documentation-contract perspective.

The repair preserves the frozen user decision that `manual_exempt` is valid for manual-mode data under ADR 0038. It does not remove, weaken, or relitigate that decision. It also preserves strict blocking for download-mode `manual_exempt`, `blocked`, and `unknown` license states.

## Files Changed

- `docs/adr/0038-manual-data-license-audit-exemption.md`: added Date, clarified ADR 0026 relationship, unified license status vocabulary, added restricted-condition semantics, and stated that `manual_exempt` does not bypass manifest/checksum/parser/provenance/audit-reference checks.
- `docs/v2/00-v2-project-map.md`: added ADR 0038 caveat to the first license-audited source seam.
- `docs/v2/01-v2-intent.md`: added ADR 0038 caveat to strict license audit language and success definition.
- `docs/v2/03-v2-requirements.md`: added `restricted` and `manual_exempt` semantics and non-bypass language.
- `docs/v2/05-v2-data-automation-spec.md`: unified five-state model, clarified Task 42/43 boundary, added Task 43 input boundary, clarified report categories and non-bypass rules.
- `docs/v2/09-v2-interface-and-contract-changes.md`: updated `SourceLicenseAudit` to support all five statuses, `manual_exempt` evidence semantics, manual/download cross-validation, and non-bypass guards.
- `docs/v2/10-v2-implementation-plan.md`: expanded Task 43 acceptance criteria and verification checks for five states, fixtures, cross-validation, report categories, and scope exclusions.
- `docs/v2/11-v2-verification-matrix.md`: expanded Task 43 and V2-B verification rows for five-status fixtures, `manual_exempt` rejection in download mode, report categories, and no download/conversion/training artifacts.
- `docs/v2/13-v2-task-adr-coverage.md`: clarified ADR 0026/0030/0038 roles and replaced duplicated future ADR numbers with placeholder titles.

## Blocking Issues Resolved

- B1 license-status vocabulary inconsistency: resolved by replacing `allowed_with_conditions` with `restricted` across `docs/v2` and `docs/adr`, and aligning the five-state model as `allowed`, `restricted`, `blocked`, `unknown`, `manual_exempt`.
- B2 `SourceLicenseAudit` omitted `manual_exempt`: resolved by adding `manual_exempt`, `intake_mode`, manual exemption audit record semantics, cross-validation rules, and non-bypass guards.
- B3 Task 43 acceptance/verification insufficient: resolved by requiring five fixture states, download-mode plus `manual_exempt` rejection, cross-validation failure, report output categories, audit reference preservation, and no download/conversion/training/sampling artifacts.

## Important Issues Resolved

- I1 ADR 0038 missing Date: resolved with `2026-06-17`.
- I2 ADR 0038 overstated ADR 0026: resolved by limiting ADR 0026 to manual staging/no-auto-download and assigning the broader trust chain to ADR 0030 plus V2 specs.
- I3 intent drift around strict license audit: resolved by adding ADR 0038 caveat while preserving strict download/blocked/unknown gates.
- I4 Task 43 input boundary ambiguity: resolved by documenting that Task 43 consumes Task 41 staged evidence and may only read Task 42 conversion output for reference consistency checks.
- I5 duplicate future ADR numbers: resolved by converting future entries to unnumbered placeholder titles.

## Minor Issues Resolved

- M1 imprecise "conversion outputs used for training eligibility" phrasing: resolved by clarifying that Task 42 preserves references and Task 43 blocks training eligibility.
- M2 project map first license-audited seam omitted manual exemption caveat: resolved by adding an ADR 0038 caveat in the dependency boundary map.

## Remaining Risks

- Task 43 implementation is still pending by design; tests and code must implement the documented gate without downloading data, converting raw data, training, or sampling.
- Existing review files and V2 implementation files remain untracked from earlier work; this repair did not stage, commit, delete, or classify them.

## Task 43 Readiness Verdict

READY

Task 43 prompt should emphasize:

- The license statuses are exactly `allowed`, `restricted`, `blocked`, `unknown`, `manual_exempt`.
- `manual_exempt` is allowed only with `intake_mode = "manual"`.
- `manual_exempt` with `intake_mode = "download"` is a structured error.
- `restricted` passes only when conditions are recorded and satisfied.
- `blocked` and `unknown` always block training eligibility.
- `manual_exempt` remains a separate report category, not merged with `allowed`.
- Manifest, checksum, parser target, local path provenance, source provenance, and `license_audit_ref` checks still run.
- Task 43 consumes Task 41 staged evidence and may only read Task 42 converted output for reference consistency checks.
- Task 43 must not download data, execute conversion, parse raw data, train models, sample, or enter Task 44+.

## Verification

Commands run:

- `rg "allowed_with_conditions" docs/v2 docs/adr`: pass, no matches.
- `rg "manual_exempt" docs/v2 docs/adr`: pass, expected matches present.
- `rg "SourceLicenseAudit|license_status|restricted|manual_exempt" docs/v2/09-v2-interface-and-contract-changes.md`: pass, five-state contract and guards present.
- `rg "Task 43|manual_exempt|restricted|unknown|blocked|download" docs/v2/10-v2-implementation-plan.md docs/v2/11-v2-verification-matrix.md`: pass, Task 43 boundaries and verification present.
- `rg "ADR 0038|0039|0040|0041|placeholder" docs/v2/13-v2-task-adr-coverage.md`: pass for ADR 0038 and placeholders; repeated concrete future ADR numbers removed.

No code tests were run because this was a documentation-only repair and the task forbids code/test changes.
