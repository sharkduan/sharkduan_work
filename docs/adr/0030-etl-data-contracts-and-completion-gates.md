# ETL Data Contracts and Completion Gates

## Status

Accepted

## Date

2026-05-19

## Context

The first covalent ETL must be reviewable before model training. The main unresolved risks were silent source incompleteness, ambiguous raw data provenance, source id collisions, duplicate/conflicting cross-source records, unclear `CovalentComplexRecord` boundaries, overloaded P0/P1/P2 labels, ambiguous null geometry rules, and rule-table rows that could be interpreted as permissive when they were only pending review.

## Decision

The first ETL release requires all three public sources: CovalentInDB 2.0, CovPDB, and CovBinderInPDB. Each source must pass an explicit `complete_for_v1` gate in the ETL quality report.

Raw source files remain manually staged. Every staged source directory must include a manifest with source version, retrieval date, license/access notes, file roles, byte sizes, and SHA-256 checksums. ETL ingestion fails on missing files, checksum mismatch, or missing license/access notes.

Canonical records are identified by normalized structure and linkage identity, not source ids. Cross-source duplicates merge into one record with all lineage preserved. Linkage identity conflicts are rejected from the first training core unless manually resolved. Annotation conflicts are resolved deterministically with source priority `CovBinderInPDB > CovPDB > CovalentInDB`, while losing values remain in lineage conflict metadata.

`CovalentComplexRecord` is limited to one accepted monodentate protein-ligand covalent linkage plus the core fields, metadata, lineage, and artifact references needed to train and audit it. Rejected records, conflict groups, calibration aggregates, and rule decisions are separate artifacts.

Quality-filter severities are named `Q0`, `Q1`, and `Q2`. CovalentInDB source-field priorities remain `P0-source`, `P1-source`, and `P2-source`. This avoids the previous P0/P1/P2 naming collision.

Multi-linkage records are rejected from the first training core but retain rejected-record lineage, including detected linkages and raw source checksums. Empty 4.0 Angstrom negative windows are valid and must be encoded as `negative_sampling_status: empty_radius_window`, not treated as failed negative generation.

The reaction family rule table must distinguish pending constraints from permissive constraints. Empty `allowed_warhead_smarts` means no allowed SMARTS have been approved. Null geometry bounds are valid only with explicit pending or disabled geometry status. Family id, residue, target atom, and reaction class must be internally consistent. Protein anchor atoms and ligand neighbor policies are part of the table contract, not hidden implementation choices.

## Consequences

The first release may take longer because all three required sources must clear provenance and coverage gates. In exchange, training cannot accidentally proceed from a single convenient source or from raw files with unknown version/license state.

Record counts may be lower because unresolved linkage conflicts, multi-linkage structures, and pending SMARTS families are excluded from the first training core. In exchange, accepted records have deterministic identity, auditable lineage, and clear rule compatibility.

Rule-table consumers must handle `pending`, `disabled`, and calibrated geometry states explicitly. This prevents null geometry or empty SMARTS lists from becoming accidental permissive decoding rules.
