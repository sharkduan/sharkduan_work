# Task 7 Handoff: Canonical Identity And Conflict Resolution (Completed)

## Status

Completed. Task 7 implementation is integrated with Task 9 normalization. This note replaces the previous readiness draft and reflects the actual delivered artifacts.

## Delivered Modules

| Module | Responsibility |
| --- | --- |
| `src/covalent_design/data/identity.py` | `CanonicalLinkageIdentity`, `build_record_id`, `resolve_identities`, `canonical_identity_from_record`, `IdentityResolutionResult`, `MergedIdentityRecord`, `RejectedIdentityInput` |
| `src/covalent_design/data/conflicts.py` | `ConflictAnchor`, `ConflictGroup` |
| `src/covalent_design/data/normalize.py` | `normalize_linkages` (in-memory API), `normalize_with_identity_resolution` (pipeline seam), CLI `main()` |

## Delivered Tests

| Test file | Coverage |
| --- | --- |
| `tests/data/test_identity.py` | `canonical_identity_from_record`, `build_record_id` determinism, `resolve_identities` duplicate merge and conflict grouping, `RejectedIdentityInput` for missing critical fields |
| `tests/data/test_identity_contracts.py` | Identity contract boundary assertions |
| `tests/data/test_normalize.py` | `IdentityResolutionIntegrationTests`: duplicate merge into normalization, conflict exclusion from accepted output, rejected identity input exposure; `IngestToNormalizeIntegrationTests`: end-to-end identity-resolution-to-normalization pipeline |
| `tests/data/test_normalize_cli.py` | CLI coverage for `--interim-root`, `--ingest-index`, `--raw-root`, `--source` input modes |

## Key Design Decisions (Implemented)

- **`record_id` is deterministic**: built from SHA-256 of sorted canonical linkage identity JSON. Source ids are never used as canonical ids.
- **Duplicate merge by canonical identity key**: records sharing the same `CanonicalLinkageIdentity` merge into one `MergedIdentityRecord` with combined lineage.
- **Conflict grouping by anchor**: records sharing the same `ConflictAnchor` (structure + ligand) but differing linkage identities produce a `ConflictGroup`. Conflicts never enter accepted normalized output.
- **Source priority**: `CovBinderInPDB > CovPDB > CovalentInDB` for annotation resolution. Losing values are preserved in `annotation_alternatives`.
- **Two public APIs**: `normalize_linkages()` is the pure in-memory API for callers that have already resolved identities. `normalize_with_identity_resolution()` is the pipeline seam that runs identity resolution before normalization.
- **CLI always resolves identities**: the `main()` entry point calls `normalize_with_identity_resolution` internally. All input modes (`--interim-root`, `--ingest-index`, `--raw-root`) route through identity resolution.

## Contract Boundary

Task 7 and Task 9 consume `SourceIngestRecord` values through these stable fields:

- `source_lineage: SourceRecordLineage` — typed authority for source provenance.
- `target_atom_identity: ProteinAtomIdentity | None` — protein-side atom identity.
- `ligand_atom_identity: LigandAtomIdentity | None` — ligand-side atom identity.
- `linkage: Mapping[str, object]` — bond type and `residue_reaction_family`.
- `protein`, `ligand`, `metadata` — mappings retained for quality gate evaluation and downstream annotation.

Task 7 must not depend on private helper names or private parser internals in
`src/covalent_design/data/sources/`.

## Downstream Consumers

Task 10 (record index) should consume:

- `NormalizationPayload.accepted` — `AcceptedRecord` values with `NormalizedLinkageRecord` and `QualityGateResult`.
- `NormalizationPayload.rejected` — `RejectedRecord` values with reasons.
- `NormalizationPayload.conflicts` — `ConflictGroup` values (excluded from training core).
- `NormalizationPayload.rejected_identity_inputs` — `RejectedIdentityInput` values (excluded entirely).
- `NormalizedLinkageRecord.record_id` — deterministic, ready for index keys.
