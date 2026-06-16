# Task 14 Readiness P0 Stabilization Closure

Date: 2026-05-25

Status: closed for Task 14 readiness P0 items; Task 14 split algorithm not started.

## Scope

This document closes the P0 readiness issues identified in
`docs/reviews/task14-readiness-health-review-2026-05-25.md` without
implementing Task 14 split logic. The stabilization pass included
documentation updates, narrow upstream code fixes, and contract fixtures/tests.

## P0 Items Closed

| Finding | Resolution | Where |
| --- | --- | --- |
| `ingest --out` is undocumented/ignored | Implemented and documented that `--out` writes `source_records.jsonl` and `ingest_index.json`, compatible with `normalize --interim-root` | `src/covalent_design/data/ingest.py`, `tests/data/test_ingest_cli.py`, `interface-design.md`, `implementation-plan.md`, `01-data-processing.md` |
| Task 14 CLI path inconsistent | Frozen as `python -m covalent_design.data.cli.build_splits` | `interface-design.md`, `implementation-plan.md`, `verification-matrix.md`, `01-data-processing.md`, `key-design-decisions.md` |
| SplitPolicy, SplitIndex, artifact schemas missing | Added `SplitPolicy`, `SplitIndex`, `ScaffoldKeyRecord`, `LeakageReport`, `FallbackAccounting`, `FallbackEntry`, `ManualReviewRecord` contracts with field-level detail | `interface-design.md` Split Contracts section |
| `fallback_reason` not fully defined | Enum documented: `warhead_unmatched`, `missing_scaffold_input`, `missing_protein_cluster_input`, `manual_review_override` | `interface-design.md`, `01-data-processing.md` |
| `manual_review_status` not defined | Schema documented: `pending`, `approved`, `rejected` with `reviewer`, `reviewed_at` (ISO 8601), `notes` | `interface-design.md`, `01-data-processing.md` |
| Scaffold-key algorithm undefined | Recorded as unresolved user decision; fixtures may use precomputed keys until a chemistry library is accepted | `key-design-decisions.md` |
| Protein-cluster authority undefined | Recorded as deferred user decision; Task 14 uses `protein_cluster_id` when present | `key-design-decisions.md` |
| Whether Task 14 mutates records.jsonl | Documented as no: splits write separate artifacts under `--out-root` | `interface-design.md`, `01-data-processing.md`, `key-design-decisions.md` |
| Task 14 input artifact policy | Documented as finalized Task 13 `records.jsonl` with required `core_labels` and artifact refs | `interface-design.md`, `implementation-plan.md`, `01-data-processing.md` |
| Default ratios and seed | Documented as 80/10/10 and seed 42 | `interface-design.md`, `implementation-plan.md`, `01-data-processing.md` |
| Task 14 input fields can be lost | Preserved `bond_type` and explicit `warhead_type` through normalization and records; added record-input visibility tests for `pdb_id` and `ligand_bond_table` | `src/covalent_design/data/normalize.py`, `tests/data/test_normalize.py`, `tests/data/test_records.py`, `tests/fixtures/records/valid/accepted.jsonl` |
| Task 14 fixtures missing | Added readiness fixtures and passing contract tests for scaffold leakage/no-leakage, protein-cluster leakage, `warhead_unmatched`, manual review override, missing scaffold input, and missing protein-cluster input | `tests/data/test_splits_contracts.py`, `tests/fixtures/splits/` |

## P1 Items Deferred

| Finding | Reason |
| --- | --- |
| No `tests/data/test_splits.py` | Implementation not started; test file is part of Task 14 implementation |
| No end-to-end split CLI evidence | Requires Task 14 implementation; readiness freezes the path only |
| No `src/covalent_design/data/cli/build_splits.py` | Implementation not started; CLI module is part of Task 14 implementation |
| Calibration richer than Task 10 outputs | Existing behavior, not a Task 14 blocker |

## Remaining User Decisions (Explicit)

These decisions are documented as unresolved in `docs/specs/key-design-decisions.md`:

1. **Scaffold-key chemistry implementation/library** — which library (e.g., RDKit Bemis-Murcko) and normalization policy (tautomer, charge, isotope, stereochemistry handling) to use for de-warheaded scaffold key generation. Until accepted, fixtures may use precomputed scaffold keys.

2. **Protein clustering authority** — which sequence identity method, threshold, and UniProt mapping to use for the primary protein-cluster split. Task 14 uses `protein_cluster_id` when present; real clustering must be deferred until sequence/UniProt coverage is stable.

## What Was Done

- `ingest --out` now writes `source_records.jsonl` and `ingest_index.json`.
- `NormalizedLinkageRecord` now carries `bond_type` and explicit `warhead_type`.
- Task 14 readiness contract fixtures and schema tests were added.
- Existing records fixtures were updated so `bond_type` and `warhead_type` are explicit where the upstream normalized row supplies them.

## What Was Not Done

- No new ADRs were created (no irreversible decisions changed).
- Task 14 split algorithm was not implemented.
- No split CLI module was implemented.
- No train/val/test production split artifacts were generated.

## Docs Changed

- `docs/specs/interface-design.md` — ingest_source docstring, build_splits signature with SplitPolicy/SplitIndex/ScaffoldKeyRecord/LeakageReport/FallbackAccounting/ManualReviewRecord contracts, CLI path, artifact boundary, misuse guards
- `docs/specs/implementation-plan.md` — Task 14 full acceptance criteria, Task 5 ingest --out, Task 14 dependency changed to Task 13
- `docs/specs/verification-matrix.md` — expanded splits row with full evidence requirements
- `docs/specs/01-data-processing.md` — CLI path, project structure, code style rules, success criteria, ingest --out semantics
- `docs/specs/key-design-decisions.md` — new decision rows for scaffold split detail, split artifact policy, ingest --out, fallback reason/manual review, Task 14 CLI path; updated unresolved decisions with scaffold-key chemistry and protein clustering

## Code And Test Changes

- `src/covalent_design/data/ingest.py` - implemented `--out` write-out for `source_records.jsonl` and `ingest_index.json`
- `src/covalent_design/data/normalize.py` - preserves `bond_type` and `warhead_type`
- `tests/data/test_ingest_cli.py` - covers ingest write-out and normalize handoff
- `tests/data/test_normalize.py` - covers normalized linkage labels
- `tests/data/test_records.py` - covers Task 14 input visibility in record index
- `tests/data/test_splits_contracts.py` and `tests/fixtures/splits/` - freeze Task 14 readiness fixture/schema contracts

## Docs Intentionally Not Changed

- `docs/adr/` — no ADR is needed; this was a documentation stabilization pass, not a new irreversible decision
- `docs/specs/02-model.md` through `docs/specs/05-inference.md` — not relevant to Task 14 splits
- `docs/specs/00-shared-contracts.md` — split contracts documented in `interface-design.md` which is the canonical interface reference; shared contract types will move to `contracts` during implementation
