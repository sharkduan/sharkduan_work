# Task 32 Docking Protocol Manifest Review

Date: 2026-06-03

## Scope

Task 32 adds docking protocol manifest validation and the flat
`DockingScoreEligibleResultIndex` boundary. It does not execute docking, choose an
authoritative docking engine, add a CLI, or implement Task 33 split-aware reports.

## Collaboration Record

The controller launched five Claude Code child windows in read/review mode before
write authorization:

- Window A: interface and schema design.
- Window B: TDD plan, then tests and fixtures after controller approval.
- Window C: implementation plan, then production code after controller approval.
- Window D: documentation plan.
- Window E: adversarial review plan.

Window D's final write pass and Window E's final review pass could not complete
because the external Claude API returned HTTP 402 Insufficient Balance. The
controller took over documentation sync, regression testing, and final self-review.

## Frozen Contract

The authoritative schema remains the nested YAML contract in
`docs/covalent_generation_io_contract.md` lines 331-390:

- `ReceptorPreparation`
- `LigandPreparation`
- `CovalentConstraint`
- `DockingSearchRegion`
- `PoseSelection`
- `DockingProtocolManifest`

`engine_build_hash` is required non-empty provenance text and may be `unknown`; it
is not a `*_sha256` field. Artifact checksum fields are 64-character lowercase
SHA-256 values. Relative artifact URIs, artifact existence, and exact checksums are
validated. A zero-byte failure log is accepted when its checksum matches.

## Self-Review Fixes

- Bound a succeeded result to its explicit `docking_protocol_manifest` ArtifactRef.
- Required the linked YAML file content to exactly match the supplied manifest
  object, preventing substituted-manifest survivor indexing.
- Rejected wrong manifest ArtifactRef roles.
- Preserved malformed source values so validation rejects missing or wrong-typed
  required values instead of silently applying valid defaults.
- Preserved and rejected non-mapping `constraint_parameters`.
- Kept `engine_build_hash` separate from SHA-256 artifact checksum validation.
- Corrected test helpers so invalid lifecycle fixtures remain internally coherent.
- Added narrow `.gitignore` exceptions for the committed golden receptor `.pdbqt`
  and zero-byte failure log fixture files.

## Verification

- `python -m unittest tests.evaluation.test_docking_protocol -v`: 83 passed.
- `pytest tests/evaluation/test_docking_protocol.py -q`: 83 passed.
- `python -m unittest tests.evaluation.test_lifecycle_reports -q`: 78 passed.
- `python -m unittest tests.evaluation.test_denominator_accounting -q`: 97 passed.
- `python -m unittest tests.contracts.test_lifecycle -q`: 10 passed.
- `python -m unittest tests.contracts.test_denominators -q`: 5 passed.
- `python -m unittest discover -s tests -t . -q`: 1586 passed.
- `python -m compileall -q scripts src`: passed.

## Review Outcome

No blocking Task 32 issue remains. The independent Window E final review is still a
process-level gap due to the external API billing failure. Task 33 must not start
until the controller explicitly confirms Task 32 acceptance.
