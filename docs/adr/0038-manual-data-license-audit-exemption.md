# ADR-0038: Manual Data License Audit Exemption

## Status

Accepted

## Date

2026-06-17

## Context

ADR 0026 established that users manually stage raw source files under
`data/raw/`, deferring automatic download.  ADR 0026 supplies the manual
raw-data staging and no-auto-download premise.  ADR 0030 and the V2 data
automation specs carry the broader staged-data trust chain: manifest
validation, SHA-256 checksum, parser target, source provenance, and
license audit.  The V2 data automation spec (Task 40-43) encodes these
steps and establishes `allowed`, `restricted`, `unknown`, and `blocked`
as the license audit statuses before this ADR, with `unknown` and
`blocked` unconditionally blocking training eligibility.

Manual data presents a distinct trust profile from download-mode data.
When the user physically obtains and places source files, the user is
already exercising custody and judgment over the data.  Requiring a
formal third-party license audit for manually-staged data adds friction
without commensurate value when the data is used for internal research
and the user accepts responsibility for the data's provenance.  At the
same time, the project must preserve the full audit trail for
download-mode data, whose provenance is inherently less controllable.

The decision introduces a fifth license status, `manual_exempt`, that
allows manual-mode data to enter training while keeping the audit trail
intact and download-mode license gates unchanged.

## Decision

A new license status `manual_exempt` is added to the license audit
vocabulary.  The full set becomes:

- `allowed`
- `restricted`
- `blocked`
- `unknown`
- `manual_exempt`

### Exemption semantics (soft exemption)

`license_audit_ref` remains a required field in source manifests for all
intake modes (Task 40 manifest schema is unchanged).  The audit file
referenced by `license_audit_ref` must exist and contain at minimum a
`license_status` field set to `manual_exempt`.  No further fields
(`exemption_rationale`, `exemption_approved_by`, or external license
evidence) are required for `manual_exempt` entries.

`manual_exempt` does not bypass manifest validation, checksum validation,
parser target validation, local path provenance, source provenance, or the
presence of `license_audit_ref`.  It changes only the training-eligibility
meaning of the license audit status for manual-mode data.

### Task 43 behaviour

- `manual_exempt` → **pass** training eligibility; record the status in
  training manifests and family readiness reports with an explicit label:
  "not verified by third-party license audit; user accepts compliance
  responsibility."

- `unknown` and `blocked` → **block** training eligibility (unchanged
  from existing policy).

- `allowed` → **pass** training eligibility (unchanged).

- `restricted` → **pass** training eligibility only when the restriction
  conditions are recorded and satisfied; conditions remain visible in
  downstream manifests and reports.

### Cross-validation rule (one-way constraint)

Exactly one enforcement rule links intake mode to license status:

- `license_status = "manual_exempt"` AND `intake_mode = "download"` →
  Task 43 MUST reject with a structured error.

Manual-mode data MAY carry any valid license status (`allowed`,
`restricted`, `blocked`, `unknown`, or `manual_exempt`).
There is no requirement that manual data use `manual_exempt`
exclusively.

### Reporting

Training eligibility reports and family readiness reports MUST list
`manual_exempt` as a distinct category, not merged with `allowed`.  The
report SHOULD include a concise notice that manual-exempt data has not
undergone third-party license verification.

### Relationship to ADR 0026

This ADR is a narrow exception and refinement of ADR 0026; it does
**not** supersede it.  ADR 0026's manual raw-data staging and
no-auto-download premise remains intact.  The broader
manifest/checksum/parser/provenance/license trust chain remains carried
by ADR 0030 and the V2 data automation specs.  This ADR refines only the
license-audit step by adding a mode-dependent gate semantic: strict
blocking for download-mode data, record-and-pass for manual-mode data
carrying `manual_exempt`.  All other checks (manifest, checksum, parser,
local path provenance, and source provenance) are unchanged for both
modes.

### Future migration

`manual_exempt` → `allowed` (or any other status) migration is permitted
if the user later obtains formal license evidence.  This ADR does not
prescribe a migration protocol; that is deferred to the task or ADR that
encounters the need.

## Consequences

### What becomes easier

- Manual data can be staged and used for training without a formal
  license audit, reducing the barrier to running real-data experiments.

- The audit trail remains complete — `license_audit_ref` is never
  absent, so provenance tooling never encounters a missing reference.

- Download-mode license enforcement is fully preserved; no new
  circumvention path is created (enforced by the cross-validation rule).

### What becomes harder

- `manual_exempt` sources are visibly distinct in training reports.
  Reviewers (collaborators, future maintainers, or publication reviewers)
  can identify which data sources lack formal license review.

- If the project transitions to a publication or regulatory submission
  phase where all data must have formal license evidence, every
  `manual_exempt` source must be individually migrated — a deliberate
  friction that prevents silent gaps.

### Risks and mitigations

- **Risk:** A future agent or contributor misreads `manual_exempt` as
  "license audit passed" and removes the explicit report label.
  **Mitigation:** The ADR itself is the authoritative record; the
  explicit reporting requirement makes the distinction visible.

- **Risk:** The user forgets why a source was exempted.
  **Mitigation:** The audit file itself (`license_audit.json`) serves as
  the permanent record.  If future circumstances require rationale or
  approver metadata, those fields can be added to the audit schema in a
  later decision without affecting the gate logic.

## Alternatives Considered

- **Hard exemption (make `license_audit_ref` optional for manual mode).**
  Rejected because removing the reference entirely breaks the provenance
  chain — downstream tooling that walks every source record to its audit
  evidence would hit a dead end.  The soft exemption preserves
  traceability at negligible cost.

- **Reuse `unknown` with intake_mode cross-validation (no new status).**
  Rejected because two semantically distinct situations ("we tried to
  determine the license and could not" vs "we deliberately chose not to
  audit") would share the same status code, making reports ambiguous and
  future automated decisions unreliable.

- **Require `exemption_rationale` and `exemption_approved_by` for
  `manual_exempt`.**
  Rejected as premature — these fields add friction without a current
  use case.  They can be added later if audit requirements tighten.

- **Require manual-mode data to use `manual_exempt` exclusively.**
  Rejected because it prevents the user from performing a formal license
  audit on a manually-staged source and recording the result.
  Flexibility is preserved by the one-way constraint.

## Affected Artifacts

| Artifact | Change |
|---|---|
| `docs/adr/0038-manual-data-license-audit-exemption.md` | new — this document |
| `docs/v2/05-v2-data-automation-spec.md` | extend License Checks to five states; add cross-validation rule; add reporting requirement |
| `docs/v2/03-v2-requirements.md` | distinguish manual/download license behaviour |
| `docs/v2/10-v2-implementation-plan.md` | extend Task 43 acceptance criteria |
| `docs/v2/00-v2-project-map.md` | note policy change in Architecture Risks or applicable section |
| `docs/v2/13-v2-task-adr-coverage.md` | add ADR 0038 to coverage table |
| `src/covalent_design/data/v2_license.py` | (future — Task 43 implementation) |
| `tests/data/test_v2_license.py` | (future — Task 43 implementation) |

No changes are required for Tasks 40, 41, or 42.  Their verified status
is preserved.
