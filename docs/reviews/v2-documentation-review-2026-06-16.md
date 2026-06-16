# V2 Documentation Review

Date: 2026-06-16
Reviewer: Codex
Scope: `docs/v2/*` planning documents

## Review Result

Status: ready for user review as planning documentation.

This review does not approve implementation. It confirms that the draft v2 documentation is internally consistent with the user-confirmed v2-beta direction and does not claim unimplemented v2 code.

## Checked Against User Decisions

- Target is `v2-beta`.
- Linux/WSL2 Conda/Mamba single-GPU environment is primary.
- Windows remains lightweight only.
- Three v1 sources remain the only v2-beta mainline data sources.
- Automatic download plus manual fallback is documented.
- Strict license audit is documented.
- PMDM preferred path and labeled fallback baseline are documented.
- RDKit is documented as heavy-profile requirement, not default CI dependency.
- Docking is feasibility-only.
- Noncovalent pretraining is experimental only.
- No ADR is added for unresolved ideas.

## Findings

No blocking documentation findings found.

## Non-Blocking Notes

- Source verification is still required before Task 37 freezes dependency versions.
- Data source URLs and license terms are intentionally not asserted as verified.
- PMDM/PocketFlow compatibility remains a Task 37/42 risk.
- The working tree still contains pre-existing governance remediation changes and untracked review/CI files outside this v2 documentation scope.

## Recommendation

Proceed to user review of the v2 documentation set. If accepted, the next implementation milestone should be Task 37: V2 Environment And Dependency Lock.
