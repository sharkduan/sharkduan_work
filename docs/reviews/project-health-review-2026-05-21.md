# Project Health Review: Tasks 1-9

Date: 2026-05-21

Scope: read-only architecture, documentation, test, and readiness review of the current project state before starting the next task.

Review methods:

- Used `zoom-out`, `improve-codebase-architecture`, `code-review-and-quality`, and `doubt-driven-development` review perspectives.
- Invoked `codex-claude-docs.ps1` in `Review` mode only, with Claude Code limited to `Read`, `Glob`, `Grep`, and `LS`.
- Cross-checked findings locally against `CONTEXT.md`, specs, ADRs, `src/covalent_design/`, `tests/`, and `.github/workflows/ci.yml`.
- Ran lightweight tests with bytecode writing disabled: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m unittest discover -s tests -t . -v`.

Verification result: 97 tests passed.

## Executive Summary

The project is in a usable intermediate state for Tasks 1-9, but it is not ready to start Task 10 without closing Task 9 and resolving interface/documentation drift.

The strongest areas are shared contracts, artifact IO, manifest validation, source ingestion, canonical identity, rule validation, and unit-level quality gates. The main risks are concentrated around normalization: `normalize_linkages()` does not consume cross-source identity resolution, its implemented API does not match the spec, it has no CLI evidence, and the Task 9 files are not yet fully tracked in git.

Decision: do not start Task 10 yet. First complete a small Task 9 stabilization pass.

## Architecture Map

Current `src/covalent_design` modules:

| Module | Responsibility | Status |
| --- | --- | --- |
| `contracts/` | Public semantic layer: `ArtifactRef`, `ValidationReceipt`, `ContractEnvelope`, `SourceIngestRecord`, lifecycle and denominator types. | Healthy, with minor compatibility complexity. |
| `io/` | Artifact references, checksum validation, JSONL read/write, receipt serialization. | Healthy. |
| `data/manifests.py` | Raw source manifest validation: required fields, checksum, byte count, extra/missing files. | Healthy. |
| `data/ingest.py` | Single-source ingestion orchestration and CLI summary. | Mostly healthy; `--out` is accepted but ignored. |
| `data/sources/` | CSV parsers for CovBinderInPDB, CovPDB, and CovalentInDB. | Functional, but repetitive. |
| `data/identity.py` | Canonical linkage identity, deterministic `record_id`, cross-source merge, conflict grouping. | Strong unit coverage. |
| `data/conflicts.py` | Conflict anchor and group data structures. | Small and clear. |
| `data/normalize.py` | Converts source records into accepted/rejected normalized records with atom mapping. | Needs stabilization before Task 10. |
| `data/quality.py` | Q0/Q1/Q2 quality gate evaluation. | Functional, but vocabulary drift risk. |
| `rules/` | Rule table schema, YAML loading, validation, CLI. | Healthy with fixture gaps. |
| `viz/` | Placeholder only. | Not implemented. |
| `candidates/`, `model/`, `training/`, `inference/`, `evaluation/` | Planned downstream modules. | Not implemented. |

Dependency direction is mostly aligned with the documented architecture:

```text
contracts
  <- io
  <- rules
  <- data.manifests
  <- data.sources
  <- data.ingest
  <- data.identity / data.conflicts
  <- data.quality
  <- data.normalize
tests/fixtures -> tests -> public/module APIs
```

No circular dependency was found in the project-owned modules. The main issue is not dependency direction, but an incomplete semantic handoff between `identity`, `normalize`, and `quality`.

## Task Completion Table

| Task | Completion | Evidence | Risk |
| --- | --- | --- | --- |
| Task 1: Shared contract package skeleton | Complete | `tests/contracts/test_core.py`, `tests/contracts/test_types.py` | P2: `contracts/core.py` is a legacy re-export subset. |
| Task 2: Denominator and lifecycle validators | Complete | `tests/contracts/test_denominators.py`, `tests/contracts/test_lifecycle.py` | P2: validation methods use lazy imports back into validator modules. |
| Task 3: Artifact IO primitives | Complete | `tests/io/test_artifacts.py`, `tests/io/test_jsonl.py` | No blocker. |
| Task 4: Raw source manifest validation | Complete | `tests/data/test_manifests.py`, `tests/data/test_validate_manifests_cli.py` | No blocker. |
| Task 5: CovBinderInPDB ingestion | Complete | `tests/data/test_ingest_covbinder.py`, `tests/data/test_ingest_cli.py` | P1: deep semantic assertions mainly cover the first row. |
| Task 6: CovPDB and CovalentInDB ingestion | Complete | `tests/data/test_ingest_covpdb.py`, `tests/data/test_ingest_covalentin_db.py` | P1: same fixture depth risk as Task 5. |
| Task 7: Canonical identity and conflict resolution | Mostly complete | `tests/data/test_identity.py`, `tests/data/test_identity_contracts.py` | P1: `task7-readiness.md` is now stale. |
| Task 8: Rule table schema and validation | Complete | `tests/rules/test_rule_table.py` | P1: missing multi-family and calibrated-success fixtures. |
| Task 9: Normalize structures and quality gates | Near complete, not closed | `tests/data/test_normalize.py`, `tests/fixtures/normalize/` | P0: API drift, no CLI, no ingest-to-normalize evidence, untracked files. |

## Documentation-Code Drift

### P0

1. `docs/specs/interface-design.md` declares:

   ```python
   def normalize_linkages(interim_root: Path, out_root: Path) -> ContractEnvelope["NormalizedLinkageIndex"]
   ```

   Actual implementation:

   ```python
   def normalize_linkages(records: tuple[SourceIngestRecord, ...]) -> ContractEnvelope[NormalizationPayload]
   ```

   Files: `docs/specs/interface-design.md`, `src/covalent_design/data/normalize.py`.

   Recommendation: keep the pure in-memory API if desired, but document it explicitly and add a CLI wrapper for the file-based command expected by the specs.

2. `docs/specs/01-data-processing.md` and `docs/specs/verification-matrix.md` require:

   ```bash
   python -m covalent_design.data.normalize --interim-root data/interim --out-root data/processed
   ```

   `src/covalent_design/data/normalize.py` has no `main()` and no CLI tests.

   Recommendation: add a `main()` and tests, or update the specs to say Task 9 is API-only and file writing begins later.

3. `docs/specs/implementation-plan.md` names `tests/data/test_normalize_quality.py`, while the actual file is `tests/data/test_normalize.py`.

   Recommendation: either rename the test file or update the implementation plan. Prefer updating the plan if the current name is accepted.

4. `docs/specs/task7-readiness.md` still says it does not implement canonical identity, duplicate merge, record id generation, or conflict resolution, and lists `identity.py`, `conflicts.py`, and `normalize.py` as out of scope.

   Recommendation: archive, rename, or rewrite this as a completed Task 7 handoff note.

### P1

1. `docs/specs/verification-matrix.md` lists the rule validation command as `python -m covalent_design.rules.validate_rule_table`, but the actual CLI is under `covalent_design.rules.cli.validate_rule_table`.

2. Some specs already describe protein chemical state as a hard gate input, but current Task 9 only handles `inferred_protein_chemical_state` as a Q2 flag. This is not necessarily wrong if full chemical-state gating belongs to a later task, but the task boundary should be made explicit.

3. `.github/workflows/ci.yml` exists and is stronger than some review output initially assumed. Documentation should treat CI as present, not missing.

## Architecture Risks

### P0: Must Fix Before Next Task

1. `normalize_linkages()` does not call `resolve_identities()`.

   Impact: duplicate cross-source records can remain duplicated, linkage identity conflicts are not excluded, and Task 10 could write a record index over semantically unresolved inputs.

   Files:

   - `src/covalent_design/data/normalize.py`
   - `src/covalent_design/data/identity.py`

   Recommendation: decide whether normalization owns identity resolution or whether Task 10 consumes both identity resolution and quality gates. In either case, add a public orchestration seam that reconciles accepted, rejected, and conflict records before record writing.

2. Task 9 files are not fully tracked in git.

   Current dirty state observed:

   ```text
    M src/covalent_design/data/__init__.py
   ?? prompts/
   ?? src/covalent_design/data/normalize.py
   ?? src/covalent_design/data/quality.py
   ?? tests/data/test_normalize.py
   ?? tests/fixtures/normalize/
   ```

   Recommendation: before new work, decide which files belong to Task 9 and stage/commit or otherwise stabilize them.

### P1: Should Fix Before Model/Record Pipeline Work

1. `quality.py` duplicates rule vocabulary already defined in `rules/schema.py`.

   Files:

   - `src/covalent_design/data/quality.py`
   - `src/covalent_design/rules/schema.py`

   Impact: adding or changing supported families in rules can silently diverge from quality gate behavior.

   Recommendation: import shared constants from `rules/schema.py`, move vocabulary to `contracts`, or pass a loaded rule table into quality evaluation.

2. Lineage is represented three ways in `SourceIngestRecord`: top-level source fields, `lineage` mapping, and `source_lineage`.

   File: `src/covalent_design/contracts/types.py`.

   Impact: future code may update one representation but not the others.

   Recommendation: freeze `SourceRecordLineage` as the typed authority, keep the mapping only for legacy/source annotations, and document the transition.

3. Source parsers repeat small parsing and failure helpers.

   Files:

   - `src/covalent_design/data/sources/covbinder_in_pdb.py`
   - `src/covalent_design/data/sources/covpdb.py`
   - `src/covalent_design/data/sources/covalentin_db.py`

   Recommendation: after Task 9 is closed, extract a small `data/sources/_shared.py` for `_text`, missing-field checks, numeric parsing, lineage construction, and failure construction. Do not do a large parser framework yet.

### P2: Can Defer

1. `QualityGateResult` lives in `data/quality.py`. If training or evaluation need it as a public semantic type, move it to `contracts`.
2. `ValidationReceipt` supports both `passed` and `ok` via custom init. Acceptable for compatibility, but eventually simplify.
3. `ArtifactRef.__post_init__` contains old positional-order compatibility logic. Remove after confirming callers no longer need it.

## Test Gaps

### P0

1. Normalization tests bypass real source ingestion.

   File: `tests/data/test_normalize.py`.

   Current tests build `SourceIngestRecord` from JSON fixtures directly. This is useful unit coverage, but it does not prove that CSV parser output flows correctly into normalization.

   Recommendation: add an ingest-to-normalize integration test that uses at least one committed CSV fixture from each source.

2. No CLI test for normalization.

   Cause: no `normalize.py` CLI exists.

   Recommendation: add CLI tests once the path-based command is implemented or revise the specs to remove the CLI requirement.

3. Protein chemical state evidence is incomplete relative to ADR 0033.

   File: `docs/adr/0033-fixed-protein-chemical-state-and-mask-gate-boundary.md`.

   Recommendation: either add a Task 9 gate for required/unavailable protein chemical state or explicitly document that full enforcement starts in a later task.

### P1

1. Ingestion tests validate counts and lineage shape across all rows, but deep semantic field checks focus mainly on the first row.

   Recommendation: add assertions that sampled later rows retain distinct PDB IDs, residues, ligand IDs, reaction families, and atom identities.

2. `test_accepted_and_rejected_counts_are_reproducible` checks only counts, not which records were accepted or rejected.

   Recommendation: assert accepted/rejected `source_record_id` and reason sets.

3. Rule table tests lack multi-family and calibrated-success fixtures.

   Recommendation: add a valid two-family fixture, duplicate-family fixture, and calibrated geometry/SMARTS pass fixture.

### P2

1. CLI `--help` is not tested.
2. JSONL tests do not appear to cover malformed JSON syntax.
3. Fixtures are intentionally lightweight but idealized: no BOM, embedded commas, quoted edge cases, empty lines, or realistic structure files.

## Next Task Readiness

Current readiness: not ready for Task 10.

Task 10 depends on:

- stable normalized accepted/rejected/conflict record semantics;
- deterministic `record_id` after cross-source identity resolution;
- clear artifact and lineage contracts;
- quality-gate reason codes that downstream reports can count;
- documentation that matches public APIs and commands.

Interfaces to freeze first:

- `normalize_linkages` API and whether it is pure in-memory, file-based CLI, or both;
- `NormalizationPayload`, `AcceptedRecord`, `RejectedRecord`, and conflict payload shape;
- accepted authority for lineage;
- quality gate reason/flag vocabulary;
- relationship between `identity.resolve_identities()` and normalization.

Maximum risk: tests stay green while duplicate/conflicting records enter the record index and become training inputs.

## Required Fixes Before Next Task

### Must Fix First

1. Close Task 9 dirty worktree and make file ownership explicit.
2. Resolve `normalize_linkages` API drift between docs and implementation.
3. Add or explicitly defer `python -m covalent_design.data.normalize` CLI.
4. Connect identity resolution to normalization or define a higher-level orchestration seam before record writing.
5. Update `task7-readiness.md` so it no longer asserts stale boundaries.
6. Add ingest-to-normalize integration evidence covering duplicate merge, conflict exclusion, and Q0/Q1/Q2 routing.

### Can Fix Later

1. Extract shared source parser helpers.
2. Consolidate quality/rule vocabulary.
3. Clarify lineage authority and deprecate duplicate representations.
4. Move `QualityGateResult` to `contracts` if downstream modules need it.
5. Add richer real-world CSV and rule fixtures.

## Recommended Workflow

1. Use `git-workflow-and-versioning` to stabilize the current dirty Task 9 files before adding new functionality.
2. Use `test-driven-development` to add failing integration tests for ingest-to-normalize and CLI behavior.
3. Use `improve-codebase-architecture` narrowly on the `identity -> normalize -> quality` seam.
4. Use `documentation-and-adrs` to update `interface-design.md`, `implementation-plan.md`, `verification-matrix.md`, and `task7-readiness.md`.
5. Use `code-review-and-quality` and `doubt-driven-development` for a second review after Task 9 is closed.

## Files That Should Not Be Touched Yet

- `PMDM/`
- `PocketFlow/`
- `src/covalent_design/model/`
- `src/covalent_design/training/`
- `src/covalent_design/inference/`
- `src/covalent_design/evaluation/`
- `src/covalent_design/candidates/`, until Task 10 produces stable record inputs
- Generated data under `data/processed/`, `data/interim/`, and `data/reports/`
- Existing accepted ADRs, unless a new decision is being recorded or an ADR is explicitly superseded

## Suggested Next Skills

| Skill | Responsibility |
| --- | --- |
| `git-workflow-and-versioning` | Stabilize current Task 9 file ownership and prepare a clean change boundary. |
| `test-driven-development` | Add regression and integration tests before changing normalization behavior. |
| `improve-codebase-architecture` | Refine the identity/normalize/quality module seam without broad refactoring. |
| `documentation-and-adrs` | Align specs and review notes with actual public APIs and decisions. |
| `code-review-and-quality` | Review the stabilized Task 9 change before moving on. |
| `doubt-driven-development` | Adversarially check claims about record reconciliation and release-gate readiness. |
