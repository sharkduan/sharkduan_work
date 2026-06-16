# Task 14 前项目健康审查

Date: 2026-05-25

Scope: Task 1-13 已完成后的只读健康审查，目标是判断当前项目是否具备进入 Task 14: Build Leakage-Aware Splits 的前置条件。

Review mode: read-only. This document records findings only. It does not implement Task 14 and does not request code changes in this file.

Verification:

- Command: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m unittest discover -s tests -t . -v`
- Result: 334 tests passed.
- Worktree after verification: only `docs/reviews/` and `prompts/` were untracked.

## Executive Summary

当前结论：不建议直接开始实现 Task 14。可以进入 Task 14 的需求冻结和测试设计阶段，但在写 split 代码前必须先补齐 split policy、artifact schema、fallback accounting 和 CLI pipeline 语义。

Tasks 1-13 的总体状态比上一次 Task 9 审查明显健康。`normalize_with_identity_resolution()`、normalize CLI、Task 10 record index、Task 11 calibration sheet、Task 12 edge candidates、Task 13 finalized manifests 都已存在，并且有较完整的单元测试和 CLI 测试支撑。

主要阻塞集中在 Task 14 输入契约，而不是已有模块是否能运行：

- P0: `ingest --out` 仍被忽略，文档中的 `ingest -> normalize --interim-root` CLI pipeline 不可直接跑通。
- P0: Task 14 的 scaffold key、protein-cluster policy、fallback reason、manual review schema 尚未冻结。
- P0: Task 10/records 输出对 Task 14 所需字段不够稳定，尤其是 `bond_type`、`warhead_type`、protein clustering 输入和 scaffold 输入。
- P0: Task 14 CLI 路径在文档中不一致。

Decision: do not implement Task 14 yet. First perform a small Task 14 specification and fixture pass.

## Architecture Map

Current `src/covalent_design` modules:

| Module | Responsibility | Task 14 readiness |
| --- | --- | --- |
| `contracts/` | Public semantic contracts: `ArtifactRef`, `ValidationReceipt`, `ContractEnvelope`, lifecycle, denominators, identity-adjacent types. | Mostly stable. Split-specific contracts are not defined yet. |
| `io/` | JSONL IO, artifact refs, checksum, bytes, relative path validation. | Healthy. |
| `data/manifests.py` | Raw source manifest validation. | Healthy. |
| `data/ingest.py` | Single-source ingestion orchestration and CLI summary. | P0: `--out` is accepted but ignored. |
| `data/sources/` | CovBinderInPDB, CovPDB, CovalentInDB CSV parsers. | Functional, but split-relevant ligand/protein fields are not guaranteed downstream. |
| `data/identity.py` | Canonical linkage identity, deterministic `record_id`, duplicate merge, conflict grouping. | Healthy. |
| `data/conflicts.py` | Conflict anchor and group structures. | Healthy. |
| `data/normalize.py` | Identity-aware normalization, accepted/rejected/conflict routing, CLI. | Mostly healthy; normalized record shape is narrow for Task 14. |
| `data/quality.py` | Q0/Q1/Q2 quality gates. | Healthy for current scope. |
| `data/records.py` | Task 10 record index and non-edge artifact refs. | P0/P1: split-relevant fields need review before Task 14. |
| `rules/` | Rule table validation and calibration sheet generation. | Healthy. |
| `candidates/` | Radius-bounded edge candidate artifacts and CLI. | Healthy for Task 12; not a scaffold source. |
| `data/artifact_manifests.py` | Task 13 finalized record/artifact manifest lifecycle. | Healthy. |
| `data/splits.py` | Planned Task 14 module. | Not implemented. |
| `viz/` | Placeholder for later visual checks. | Not relevant to Task 14 implementation start. |

Dependency direction remains broadly aligned:

```text
contracts
  <- io
  <- data / rules / candidates
  <- CLI wrappers
tests -> public APIs and CLI entrypoints
```

No project-owned circular dependency was found. The risk is semantic: Task 14 needs a deeper split contract than the current record artifacts expose.

## Task 1-13 Completion Table

| Task | Completion | Evidence | Risk |
| --- | --- | --- | --- |
| Task 1: Shared contracts | Complete | `tests/contracts/*` | P2: legacy compatibility remains in `ArtifactRef` and `ValidationReceipt`. |
| Task 2: Denominators and lifecycle | Complete | `tests/contracts/test_denominators.py`, `tests/contracts/test_lifecycle.py` | P2. |
| Task 3: Artifact IO | Complete | `tests/io/test_artifacts.py`, `tests/io/test_jsonl.py` | Low. |
| Task 4: Raw manifests | Complete | `tests/data/test_manifests.py`, `tests/data/test_validate_manifests_cli.py` | Low. |
| Task 5: CovBinderInPDB ingestion | Mostly complete | `tests/data/test_ingest_covbinder.py`, `tests/data/test_ingest_cli.py` | P0: CLI `--out` is not a real pipeline output. |
| Task 6: CovPDB and CovalentInDB ingestion | Mostly complete | `tests/data/test_ingest_covpdb.py`, `tests/data/test_ingest_covalentin_db.py` | P1: split-relevant source fields are not fully preserved downstream. |
| Task 7: Canonical identity and conflicts | Complete | `tests/data/test_identity.py`, `tests/data/test_identity_contracts.py`, updated `task7-readiness.md` | Low. |
| Task 8: Rule table validation | Complete | `tests/rules/test_rule_table.py` | Low. |
| Task 9: Normalize and quality gates | Mostly complete | `tests/data/test_normalize.py`, `tests/data/test_normalize_cli.py` | P1: normalized output is intentionally narrow and may not carry enough split metadata. |
| Task 10: Record index and non-edge artifacts | Complete | `tests/data/test_records.py` | P0/P1: Task 14 input fields require stabilization. |
| Task 11: Rule calibration sheet | Complete | `tests/rules/test_calibration.py` | P1: calibration fixtures are richer than some Task 10 records. |
| Task 12: Edge candidates | Complete | `tests/candidates/test_edge_candidates.py` | P1: path/checksum hardening can wait but should be addressed before untrusted artifacts. |
| Task 13: Finalize record manifests | Complete | `tests/data/test_finalize_record_manifests.py` | Low. |

## Documentation Review

The documentation now matches Tasks 10-13 better than it did in the previous Task 9 review. The remaining serious gaps are around Task 14.

Relevant documentation signals:

- `docs/specs/implementation-plan.md` defines Task 14 as random, protein-cluster, and de-warheaded scaffold splits, but the details are high level.
- `docs/specs/verification-matrix.md` requires scaffold key artifact, zero primary overlap check, fallback reason accounting, and diagnostic overlap report.
- `docs/specs/01-data-processing.md` requires random, protein-cluster, and de-warheaded scaffold splits, and says `warhead_unmatched` fallback records are excluded from primary scaffold release metrics unless manually reviewed.
- `docs/specs/key-design-decisions.md` says the primary scaffold key is de-warheaded scaffold plus residue-reaction-family stratification.
- `docs/adr/0032-generation-result-and-evaluation-contract.md` requires scaffold-key artifact, warhead-removal evidence, algorithm/version, normalization policy, and leakage report.

The issue is not that Task 14 is undocumented. The issue is that it is not decision-complete enough for implementation.

## Documentation-Code Drift

### P0

1. Documented ingest pipeline is not directly executable.

   Docs show:

   ```bash
   python -m covalent_design.data.ingest --source covbinder_in_pdb --raw-root data/raw --out data/interim
   python -m covalent_design.data.normalize --interim-root data/interim --out-root data/processed
   ```

   Actual `ingest_source()` accepts `out` but discards it with `del out`. The CLI prints a JSON summary but does not write a source record index that `normalize --interim-root` can consume.

   Impact: Task 14 cannot rely on a documented full CLI path from raw source fixtures to finalized records.

2. Task 14 CLI path is inconsistent.

   Some docs refer to:

   ```bash
   python -m covalent_design.data.build_splits
   ```

   The implementation plan file list says:

   ```text
   src/covalent_design/data/cli/build_splits.py
   ```

   Recommendation: freeze one public CLI path before implementation. Prefer `python -m covalent_design.data.cli.build_splits` for consistency with Task 13.

### P1

1. Task 14 dependencies are ambiguous.

   The implementation plan says Task 14 depends on Tasks 10 and 11. Current workflow also has Task 12 and Task 13 before Task 14. Decide whether splits consume Task 10 records or Task 13 finalized records.

2. Previous review findings need a closure note.

   `docs/reviews/project-health-review-2026-05-21.md` is now historical. Many Task 9 blockers are closed, but there is no explicit closure document. This is useful but not blocking.

## Requirement Gaps

### P0

1. Scaffold key algorithm is not defined.

   Missing decisions:

   - Whether to use RDKit Bemis-Murcko scaffold, custom graph key, or stored fixture key.
   - How warhead atoms are identified and removed.
   - Whether tautomer, charge, salt, isotope, stereochemistry, and attachment dummy atoms are normalized.
   - Whether scaffold key includes residue-reaction-family or is stored separately and stratified later.

2. Protein-cluster policy is not defined.

   `docs/specs/01-data-processing.md` still lists protein clustering method and threshold as an open question.

   Missing decisions:

   - Sequence identity method or fixture-provided `protein_cluster_id`.
   - Threshold.
   - Fallback when sequence or UniProt is missing.
   - Whether same PDB target but different chain/residue can cross split.

3. `fallback_reason` schema is not defined.

   Only `warhead_unmatched` is named. Missing:

   - Full enum.
   - Whether fallback records are assigned split labels.
   - Whether fallback records appear in training, diagnostics, or neither.
   - How fallback reason counts are reported.

4. Manual review override is not defined.

   Docs say `warhead_unmatched` records are excluded unless manually reviewed, but do not define:

   - `manual_review_status` field.
   - Reviewer identity or timestamp.
   - Approved/rejected values.
   - Where the review file lives.

5. Split artifact schema is missing.

   Missing:

   - File names and roles.
   - Whether splits mutate `records.jsonl`.
   - Leakage report shape.
   - Count conservation equations.
   - Random seed and split ratios.

### P1

1. Records do not consistently carry protein clustering inputs.

   Current records often expose `pdb_id`, but not a stable `protein_cluster_id`, sequence id, or complete UniProt field.

2. Records do not consistently carry scaffold inputs.

   Current ligand atom and bond tables are lightweight graph fixtures, not necessarily chemically complete enough for de-warheaded scaffold derivation.

## Grill-Me Questions For User

### P0

1. What is the authoritative scaffold-key method for Task 14?

   Recommended answer: use RDKit Bemis-Murcko on the ligand graph after removing matched warhead atoms; write algorithm name/version, removed atom ids, matched warhead evidence, normalized scaffold string, and failure reason into a scaffold-key artifact.

2. What should happen when warhead matching fails?

   Recommended answer: assign `fallback_reason = "warhead_unmatched"`, exclude from primary scaffold release metrics, include in diagnostic accounting, and allow inclusion only when `manual_review_status = "approved"`.

3. What is the protein-cluster authority for the first implementation?

   Recommended answer: for Task 14 fixtures, use an explicit `protein_cluster_id` field if present. Do not invent real sequence clustering until sequence or UniProt coverage is stable. Document this as a temporary scaffold implementation policy.

4. Should Task 14 mutate `records.jsonl` and `artifact_manifest.json`?

   Recommended answer: no for the first implementation. Write separate split artifacts and split manifest artifacts first. Mutating finalized records should be a later explicit task.

### P1

5. Should Task 14 consume finalized Task 13 records or Task 10 records?

   Recommended answer: consume finalized Task 13 records when available, but require only `record_id`, `core_labels`, `metadata`, lineage, and the non-edge ligand/protein artifacts.

6. What are the default split ratios and random seed?

   Recommended answer: use deterministic defaults, for example 80/10/10 and a fixed seed, with explicit small-fixture fallback behavior.

## Code Quality Findings

### P0

1. `ingest --out` is not implemented as a real output.

   File: `src/covalent_design/data/ingest.py`

   Impact: the documented raw-to-normalized CLI pipeline is misleading. Task 14 should not build on that pipeline until it is either implemented or the docs are corrected.

2. Task 10 record output can lose `bond_type` and `warhead_type`.

   Files:

   - `src/covalent_design/data/normalize.py`
   - `src/covalent_design/data/records.py`

   `records.py` reads `normalized["bond_type"]` and `normalized["warhead_type"]`, but `NormalizedLinkageRecord` does not define those fields. This can produce empty `core_labels` values and weakens calibration, scaffold fallback, and split diagnostics.

### P1

1. Edge candidate input artifacts are read before full artifact validation.

   File: `src/covalent_design/candidates/edge_candidates.py`

   Impact: current fixtures are safe, but malformed record artifact refs could escape root or bypass checksum validation before reads. Harden before accepting untrusted artifacts.

2. Edge candidate artifacts are not a scaffold source.

   Edge candidate artifacts embed references to `coordinates`, `protein_atom_table`, and `ligand_atom_table`, but not `ligand_bond_table`. Task 14 must consume record artifacts or ligand graph artifacts directly.

### P2

1. `ValidationReceipt` still supports both `passed` and `ok`.
2. `ArtifactRef.__post_init__` still has legacy positional compatibility.
3. Parser helper duplication remains in `data/sources/`.

## Test Gaps

### P0

1. No `tests/data/test_splits.py` exists yet.
2. No Task 14 fixtures exist for scaffold leakage, protein-cluster leakage, fallback reason accounting, or manual review override.
3. No end-to-end CLI evidence proves `ingest -> normalize -> build_record_index -> build_edge_candidates -> finalize_record_manifests` from a single command chain.
4. No fixture proves `warhead_unmatched` is excluded from primary scaffold metrics.

### P1

1. Calibration tests use richer fixture records than some Task 10 outputs.
2. Candidate tests are strong on geometry but weaker on artifact-ref path/checksum hardening.
3. Some tests write deterministic output into fixture directories. No diff was observed, but future test changes could hide fixture churn.

## Integration Risks

### P0

1. False confidence from passing unit tests.

   The tests prove Tasks 1-13 behavior in their current fixture universe. They do not prove Task 14 has sufficient scaffold/protein grouping inputs.

2. Protein leakage may be under-detected.

   If Task 14 falls back to `pdb_id` or source ids instead of a real cluster key, protein-cluster split metrics can look valid while still leaking homologous targets.

3. Scaffold leakage may be under-detected.

   If Task 14 uses whole-ligand scaffold or ligand id instead of de-warheaded scaffold, recurring warhead/scaffold families can leak across train/val/test.

4. Fallback records may pollute primary metrics.

   Without a frozen `fallback_reason` and manual review schema, `warhead_unmatched` records can accidentally enter primary scaffold release metrics.

## Task 14 Readiness

Current readiness: not ready for implementation.

Ready activities:

- Define Task 14 split policy.
- Define split artifact schema.
- Define test fixtures.
- Decide CLI path.
- Decide whether split artifacts mutate finalized records.

Not ready activities:

- Implement `data/splits.py`.
- Implement split CLI.
- Generate real release splits.
- Use split outputs for model or training work.

Interfaces to freeze first:

- `SplitPolicy`
- `SplitIndex`
- scaffold-key artifact schema
- leakage report schema
- fallback reason enum
- manual review override schema
- CLI path and output directory policy

## Required Fixes Before Task 14

### P0: Must Fix First

1. Implement or remove the documented `ingest --out` pipeline behavior.
2. Freeze Task 14 CLI path.
3. Add a spec section for `SplitPolicy`, `SplitIndex`, scaffold-key artifacts, fallback accounting, and leakage reports.
4. Preserve or derive Task 14 input fields: `bond_type`, `warhead_type`, ligand graph/scaffold input, protein cluster input.
5. Create Task 14 fixtures before implementation:
   - scaffold leakage fixture
   - scaffold no-leakage fixture
   - protein-cluster leakage fixture
   - `warhead_unmatched` fallback fixture
   - manual review override fixture

### P1: Should Fix Soon

1. Add integration evidence from normalized output through Task 11 calibration.
2. Harden edge candidate artifact ref validation before reads.
3. Add explicit count conservation tests for accepted, excluded, fallback, train, val, and test rows.

## Deferrable Improvements

- Extract shared source parser helpers.
- Move split enums to `contracts` only after Task 14 shape is proven.
- Add richer chemistry fixtures with realistic ligand graphs.
- Add a closure note for the 2026-05-21 review.
- Clean up legacy compatibility shims after public callers stabilize.

## Recommended Next Workflow

1. Use `grill-me` to answer the P0 split-policy questions in this document.
2. Use `documentation-and-adrs` to update specs and record any irreversible scaffold/protein split decisions.
3. Use `api-and-interface-design` to freeze `SplitPolicy`, `SplitIndex`, artifact roles, and CLI path.
4. Use `test-driven-development` to write failing Task 14 fixtures and tests before implementation.
5. Use `source-driven-development` if RDKit or another chemistry library is selected for scaffold extraction.
6. Use `code-review-and-quality` and `doubt-driven-development` before accepting Task 14.

## Files That Should Not Be Touched Yet

- `PMDM/`
- `PocketFlow/`
- `src/covalent_design/model/`
- `src/covalent_design/training/`
- `src/covalent_design/inference/`
- `src/covalent_design/evaluation/`
- Generated data under `data/processed/`, `data/interim/`, and `data/reports/`
- Existing accepted ADRs, unless a new ADR explicitly supersedes or extends them
