# V2 Manual Exempt Documentation Review

Date: 2026-06-18
Scope: documentation-only system review of ADR 0038 and `manual_exempt` downstream documentation.

## Executive Summary

- Overall Status: BLOCKED
- Whether Task 43 may start: No. The core `manual_exempt` decision is accepted, but Task 43 should not start until the documentation contract is reconciled.
- Largest risk: the V2 docs currently describe two incompatible license-status vocabularies. The review prompt defines the five-state model as `allowed`, `restricted`, `blocked`, `unknown`, and `manual_exempt`, while ADR 0038, the data automation spec, and the implementation plan use `allowed_with_conditions` instead of `restricted`; `docs/v2/09-v2-interface-and-contract-changes.md` still lists only four statuses and omits `manual_exempt`.

## Fixed User Decision

- `manual_exempt` is a frozen user design decision.
- This review does not judge whether `manual_exempt` should exist.
- This review checks only documentation expression, boundaries, downstream task slicing, and testability.
- This review does not recommend removing `manual_exempt`.
- This review does not recommend forcing manual mode back to download-mode license audit standards.

## Reviewed Files

- `CONTEXT.md`
- `docs/adr/0026-manual-raw-data-staging.md`
- `docs/adr/0038-manual-data-license-audit-exemption.md`
- `docs/v2/00-v2-project-map.md`
- `docs/v2/01-v2-intent.md`
- `docs/v2/03-v2-requirements.md`
- `docs/v2/05-v2-data-automation-spec.md`
- `docs/v2/09-v2-interface-and-contract-changes.md`
- `docs/v2/10-v2-implementation-plan.md`
- `docs/v2/11-v2-verification-matrix.md`
- `docs/v2/13-v2-task-adr-coverage.md`
- `docs/reviews/v2-local-real-data-policy-review-2026-06-16.md`

Note: the prompt referenced `docs/adr/0026-data-license-and-provenance-policy.md`, but the repository contains `docs/adr/0026-manual-raw-data-staging.md`. This review used the actual ADR 0026 file.

## Blocking Issues

### B1. License-status vocabulary is inconsistent across the reviewed docs

- Severity: Blocking
- File: `docs/adr/0038-manual-data-license-audit-exemption.md`; `docs/v2/05-v2-data-automation-spec.md`; `docs/v2/10-v2-implementation-plan.md`; `docs/v2/13-v2-task-adr-coverage.md`
- Evidence:
  - The review contract asks for five states: `allowed`, `restricted`, `blocked`, `unknown`, `manual_exempt`.
  - ADR 0038 lists `allowed`, `allowed_with_conditions`, `unknown`, `blocked`, `manual_exempt`.
  - `docs/v2/05-v2-data-automation-spec.md` lists `allowed_with_conditions` in License Checks and says only `allowed`, compatible `allowed_with_conditions`, and `manual_exempt` may enter training.
  - `docs/v2/10-v2-implementation-plan.md` Task 43 acceptance also uses `allowed_with_conditions`.
  - `docs/v2/13-v2-task-adr-coverage.md` Future ADR Triggers also refers to `allowed_with_conditions`.
- Why it matters: Task 43 implementers and tests cannot know whether the accepted restricted-status state is named `restricted` or `allowed_with_conditions`. That would directly affect enum validation, fixture naming, report categories, and migration behavior.
- Required fix: align all V2 docs and ADR 0038 to one canonical five-state vocabulary before Task 43 starts.

### B2. `SourceLicenseAudit` contract omits `manual_exempt`

- Severity: Blocking
- File: `docs/v2/09-v2-interface-and-contract-changes.md`
- Evidence:
  - The `SourceLicenseAudit` section defines `license_status` as enum `allowed`, `allowed_with_conditions`, `unknown`, or `blocked`.
  - It does not include `manual_exempt`.
  - It also requires `license_evidence_ref`, while ADR 0038 states that for `manual_exempt`, the referenced audit file may contain only `license_status: "manual_exempt"` and no external license evidence.
- Why it matters: Task 43 is expected to implement the license/provenance gate. Its interface document still describes a schema that cannot represent the accepted ADR 0038 state and may force evidence fields that ADR 0038 explicitly made unnecessary for `manual_exempt`.
- Required fix: update the `SourceLicenseAudit` schema so it can represent `manual_exempt` and its soft-exemption evidence requirements without contradicting ADR 0038.

### B3. Task 43 acceptance and verification are not yet sufficient to prove `manual_exempt`

- Severity: Blocking
- File: `docs/v2/10-v2-implementation-plan.md`; `docs/v2/11-v2-verification-matrix.md`
- Evidence:
  - Task 43 acceptance includes the status list, unknown/blocked failure, `manual_exempt` manual pass, download cross-validation failure, and condition preservation.
  - It does not explicitly require fixture coverage for every status, report-output categories, or manual/download negative coverage.
  - The verification matrix Task 43 inspection command only searches for `unknown|blocked|training|license|provenance` in the data automation spec. It does not mention `manual_exempt`, cross-validation, restricted/conditional status, or report output expectations.
- Why it matters: The current Task 43 docs do not yet force tests for the exact failure modes this ADR introduces. An implementation could pass a minimal unknown/blocked gate while missing manual-exempt reporting or download-mode rejection.
- Required fix: extend Task 43 acceptance and verification to require tests or fixtures for `manual_exempt`, download-mode rejection, unknown, blocked, restricted/conditional status, cross-validation failure, and report category output.

## Important Issues

### I1. ADR 0038 has no explicit Date section

- Severity: Important
- File: `docs/adr/0038-manual-data-license-audit-exemption.md`
- Evidence: ADR 0038 has `## Status` followed by `Accepted`, then `## Context`; no date field is present.
- Why it matters: The ADR coverage doc says ADR 0038 was accepted on 2026-06-17, but the ADR itself does not carry the date. This weakens ADR lifecycle traceability.
- Required fix: add the accepted date to ADR 0038.

### I2. ADR 0038 relationship to ADR 0026 is directionally correct but overstates ADR 0026's content

- Severity: Important
- File: `docs/adr/0038-manual-data-license-audit-exemption.md`; `docs/adr/0026-manual-raw-data-staging.md`
- Evidence:
  - ADR 0038 says ADR 0026 together with ADRs 0021-0029 and ADR 0030 define a five-step trust chain.
  - Actual ADR 0026 is a short manual raw-data staging decision. It defers automatic downloading but does not itself define license/provenance policy.
- Why it matters: The intended relationship is still a narrow exception, not supersession. However, future readers may look for the license/provenance policy in ADR 0026 and not find it.
- Required fix: clarify that ADR 0026 contributes the manual-staging/no-auto-download premise, while ADR 0030 and the V2 specs carry the fuller manifest/checksum/provenance/license gate details.

### I3. `docs/v2/01-v2-intent.md` still says strict source license audit without naming the exemption

- Severity: Important
- File: `docs/v2/01-v2-intent.md`
- Evidence: Confirmed User Decisions includes "License policy: strict source and dependency license audit." It does not mention ADR 0038 or the manual-mode soft exemption.
- Why it matters: The intent file is a high-level authority for V2. Without the ADR 0038 caveat, it can be read as contradicting the accepted manual-mode exemption.
- Required fix: update the intent statement so "strict" remains true for download/unknown/blocked paths while acknowledging the manual-mode `manual_exempt` record-and-pass behavior.

### I4. Task 43 dependency boundary is ambiguous around Task 42 conversion output

- Severity: Important
- File: `docs/v2/05-v2-data-automation-spec.md`; `docs/v2/10-v2-implementation-plan.md`
- Evidence:
  - The data automation spec says Task 42 preserves `license_audit_ref` for downstream Task 43 eligibility decisions.
  - Task 43 dependencies list only Tasks 40 and 41.
  - Task 43 notes say it evaluates the same local staged manifests that later conversion and training eligibility consume.
- Why it matters: It is unclear whether Task 43 consumes only source manifests/staging summaries, converted `SourceIngestRecord` outputs, or both. That affects test fixture design and cross-validation coverage.
- Required fix: document Task 43's exact input boundary.

### I5. Future ADR trigger numbering has duplicate suggested ADR numbers

- Severity: Important
- File: `docs/v2/13-v2-task-adr-coverage.md`
- Evidence:
  - Multiple Future ADR Triggers suggest ADR 0039 for different future decisions.
  - ADR 0040 and ADR 0041 are also reused for more than one suggested title.
- Why it matters: The document otherwise acts as a governance map. Duplicate suggested numbers are not fatal, but they can confuse the next ADR author and create accidental numbering drift.
- Required fix: make the suggested numbering unambiguous or mark numbers as placeholders.

## Minor Issues

### M1. `docs/v2/05-v2-data-automation-spec.md` phrase "must not enter conversion outputs used for training eligibility" is imprecise

- Severity: Minor
- File: `docs/v2/05-v2-data-automation-spec.md`
- Evidence: The License Checks section says `unknown` and `blocked` "must not enter conversion outputs used for training eligibility."
- Why it matters: Task 42 conversion does not decide license eligibility. The intended gate appears to be before training eligibility, not necessarily before conversion output existence.
- Required fix: clarify the stage at which unknown/blocked are blocked.

### M2. Project-map dependency row still says "license-audited source seam"

- Severity: Minor
- File: `docs/v2/00-v2-project-map.md`
- Evidence: The dependency boundary map describes user-provided local source data as "manifest, checksum, parser validation, and license-audited source seam"; later text correctly mentions `manual_exempt`.
- Why it matters: The row is not wrong for audited paths, but it does not surface the manual-mode soft exemption where readers first scan the boundary map.
- Required fix: add a short pointer to ADR 0038 in that row or nearby.

## ADR 0038 Review

- Status/date/title: Title and status are clear. Date is missing from the ADR itself.
- Context: Sufficiently explains why manual data has a different trust profile from download-mode data.
- Decision: Clear that `manual_exempt` is a soft exemption, not removal of `license_audit_ref`.
- Relation to ADR 0026: Correctly says ADR 0038 narrows and does not supersede ADR 0026. The relationship should be worded more precisely because actual ADR 0026 is only the manual raw-data staging/no-auto-download decision.
- Alternatives considered: Covers hard exemption, reusing `unknown`, required rationale/approver fields, and manual-only exclusivity.
- Consequences: Concrete enough for reporting and future migration. It explicitly preserves download-mode enforcement.
- Supersede/narrow exception conflict: No direct conflict found. ADR 0038 states "narrows" and "does not supersede." The only issue is over-broad attribution to ADR 0026.

## Five-State License Model Review

Expected review model:

- `allowed`
- `restricted`
- `blocked`
- `unknown`
- `manual_exempt`

Observed documentation model:

- ADR 0038, data automation spec, implementation plan, and ADR coverage use `allowed_with_conditions`, not `restricted`.
- Interface document `SourceLicenseAudit` is still four-state and omits `manual_exempt`.
- `manual_exempt` semantics are otherwise consistent where it is mentioned: manual-mode pass, download-mode structured rejection, distinct report category, no merge with `allowed`.
- Manual/download distinction is mostly clear: manual-mode can use any valid status; download-mode cannot use `manual_exempt`; automatic download remains future optional and not a default V2-beta path.

Verdict: not globally consistent until `restricted` vs `allowed_with_conditions` and `SourceLicenseAudit` are reconciled.

## Task Boundary Review

- Task 41: clear boundary for local manual staging, checksum verification, no conversion, no license eligibility decision, no network download.
- Task 42: clear boundary for conversion from checksum-verified staged manual input to v1-compatible `SourceIngestRecord` tuples; it preserves `license_audit_ref` but does not decide license/training eligibility.
- Task 43: conceptually scoped to license/provenance training gate and does not download, convert, train, or sample. However, its exact input boundary is ambiguous: docs mention staged manifests, later conversion consumers, and downstream converted records.
- No evidence found that Task 43 is incorrectly expanded into real download, conversion, model training, or sampling tests.

## Verification And Testability Review

Task 43 currently has partial acceptance criteria. It needs stronger, explicit testability before implementation:

- `manual_exempt` fixture: implied but not explicitly required.
- download-mode fixture: implied by cross-validation rule but not explicitly named.
- unknown fixture: required only generally.
- blocked fixture: required only generally.
- restricted fixture: not covered because docs use `allowed_with_conditions`.
- cross-validation failure fixture: required conceptually but not explicitly listed as fixture/test.
- report output expectations: report category and explicit notice are required in ADR 0038 and data automation spec, but not carried into Task 43 acceptance or verification matrix strongly enough.

## ADR Coverage Review

- ADR 0038 is correctly added to Current ADR Coverage for local real data manual staging and license gate.
- Task-Level ADR Need correctly maps Tasks 40-43 to ADR 0038.
- Current ADR Decision correctly says ADR 0038 narrows ADR 0026 and preserves download-mode enforcement.
- Future ADR Triggers have numbering conflicts through repeated suggested ADR numbers.
- Future ADR Triggers still refer to `allowed_with_conditions`; this should align with the final five-state vocabulary before Task 43.
- Task-Level ADR Need is broadly consistent with the implementation plan, subject to the Task 43 input-boundary ambiguity noted above.

## Questions For User

None. The user decision that `manual_exempt` exists and is allowed in specific manual mode is sufficiently explicit for this review. The remaining issues are documentation consistency and task-testability fixes, not missing product decisions.

## Final Verdict

- Task 43 may start: No, not yet.
- Must fix before Task 43:
  - align the license-status vocabulary globally;
  - update `SourceLicenseAudit` to include `manual_exempt` and its evidence semantics;
  - strengthen Task 43 acceptance/verification for five statuses, cross-validation, and report output;
  - clarify Task 43 input boundary.
- If Task 43 prompt is drafted after those fixes, it should explicitly emphasize:
  - `manual_exempt` is accepted only for `intake_mode = "manual"`;
  - `manual_exempt` on `download` is a structured error;
  - `unknown` and `blocked` remain blocking;
  - the audit reference, manifest, checksum, parser target, provenance, and local path checks still run;
  - reports must keep `manual_exempt` distinct from `allowed`;
  - Task 43 must not download, convert raw data, train models, sample, or enter later V2 tasks.
