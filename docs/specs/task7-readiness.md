# Task 7 Readiness: Canonical Identity And Conflict Resolution

## Status

Readiness note for Task 7. This document does not supersede ADR 0030 and does not implement canonical identity, duplicate merge, record id generation, or conflict resolution.

## Purpose

Task 7 must normalize source ingestion records into deterministic linkage identities and conflict artifacts. Before that work starts, callers need a stable input seam that does not depend on source parser internals.

## Stable Inputs

Task 7 should consume `SourceIngestRecord` values through these contract fields:

- `source_lineage`: source database, source version, source record id, raw manifest file, raw file path, raw file sha256, and row index.
- `target_atom_identity`: protein-side Structure Atom Identity fields available from ingestion.
- `ligand_atom_identity`: ligand-side atom identity fields available from ingestion.
- `linkage`: source-provided bond type and `residue_reaction_family`.
- `metadata`: source annotations retained for conflict evidence.

Task 7 must not depend on private helper names or source-specific parser implementation details in `src/covalent_design/data/sources/`.

## Required Task 7 Evidence

Task 7 implementation should add fixtures and tests for:

- duplicate canonical linkage inputs that merge lineage without using source ids as canonical ids;
- PDB/ligand matches with target atom or linkage conflicts that produce conflict groups;
- annotation conflicts resolved by source priority `CovBinderInPDB > CovPDB > CovalentInDB`, while losing values remain in lineage conflict metadata;
- deterministic `record_id` generation from normalized canonical linkage identity.

## Out Of Scope For This Note

- `src/covalent_design/data/identity.py`
- `src/covalent_design/data/conflicts.py`
- `src/covalent_design/data/normalize.py`
- canonical merge logic
- conflict artifact writing
- `record_id` generation
