# V2 Real Data Import Change Review - 2026-06-19

## Executive Summary

- **Overall Status:** BLOCKED
- **是否允许进入 Task 49:** 不允许。
- **最大风险摘要:** 当前仓库同时存在两套互相冲突的真实 ETL 叙事：正式 `v2_run_real_etl` 对 `D:\codex_work\data` 的运行结果是三源全部失败、0 conversion、`etl_complete=false`；但 `docs/reviews/v2-real-local-data-etl-evidence-review-2026-06-19.md` 和 `data/v2/reports/v2-real-data-pipeline-dry-run-2026-06-19.json` 声称三源产生 21,488 条 `SourceIngestRecord` 且 `training_eligible=true`。在测试仍有 14 个失败、真实 raw manifest 不能通过 Task 40 validation、`v2_run_real_etl.py` 只写 report 不写可消费 processed artifact 的情况下，不能把当前状态标记为可训练。

本次审查没有联网、没有训练模型、没有进入 Task 49/44/45/46，没有修改 `D:\codex_work\data`。按要求运行了真实 ETL 命令；该命令写入/覆盖 `data/v2/reports/window_c_real_etl_report.json`，但 `git status --short` 未显示该文件产生新的 tracked diff。

## Reviewed Files

实际阅读/检查的代码：

- `src/covalent_design/data/cli/v2_run_real_etl.py`
- `src/covalent_design/data/v2_conversion.py`
- `src/covalent_design/data/v2_intake.py`
- `src/covalent_design/data/v2_license.py`
- `src/covalent_design/data/v2_manifests.py`
- `src/covalent_design/data/__init__.py`

实际阅读/检查的测试：

- `tests/data/test_v2_real_etl_cli.py`
- `tests/data/test_v2_conversion.py`
- `tests/data/test_v2_intake.py`
- `tests/data/test_v2_license.py`
- `tests/data/test_v2_manifests.py`

实际阅读/检查的文档、报告和决策：

- `docs/reviews/v2-real-local-data-etl-evidence-review-2026-06-19.md`
- `docs/reviews/v2-real-data-etl-inference-rules-and-changes.md`
- `docs/reviews/v2-real-local-data-etl-evidence-review-2026-06-18.md`
- `docs/reviews/checkpoint-v2-b-data-intake-license-gate-review-2026-06-18.md`
- `docs/superpowers/plans/2026-06-18-v2-real-data-etl.md`
- `docs/v2/05-v2-data-automation-spec.md`
- `docs/v2/09-v2-interface-and-contract-changes.md`
- `docs/v2/10-v2-implementation-plan.md`
- `docs/v2/11-v2-verification-matrix.md`
- `docs/v2/12-v2-risk-register.md`
- `docs/adr/0038-manual-data-license-audit-exemption.md`

实际检查的数据证据：

- `D:\codex_work\data`
- `D:\codex_work\data\CovalentInDB\source_manifest.json`
- `D:\codex_work\data\CovBinderInPDB\source_manifest.json`
- `D:\codex_work\data\CovPDB\source_manifest.json`
- `data/v2/manifests/*.json`
- `data/v2/staging/*.tsv`
- `data/v2/staging/transform_*.py`
- `data/v2/reports/*.json`

## Commands Run

| Command | Result |
| --- | --- |
| `git status --short` | Pass. Showed modified `docs/v2/10-v2-implementation-plan.md`, `docs/v2/11-v2-verification-matrix.md`, `src/covalent_design/data/__init__.py`; untracked `docs/reviews/v2-real-local-data-etl-evidence-review-2026-06-18.md`, `src/covalent_design/data/cli/v2_run_real_etl.py`, `tests/data/test_v2_real_etl_cli.py`, and two fixture dirs. |
| `git diff --stat` | Pass. 3 tracked files changed, 9 insertions / 1 deletion. |
| `git diff -- src/covalent_design/data/v2_conversion.py src/covalent_design/data/cli/v2_run_real_etl.py tests/data/test_v2_real_etl_cli.py docs/v2/10-v2-implementation-plan.md docs/v2/11-v2-verification-matrix.md` | Pass. Diff showed docs updates only for v2 plan/matrix; `v2_run_real_etl.py` and `test_v2_real_etl_cli.py` are untracked, so not shown by normal `git diff`. |
| `$env:PYTHONPATH='src'; python -m compileall -q scripts src` | Pass. |
| `$env:PYTHONPATH='src'; python -m pytest tests/data/test_v2_manifests.py tests/data/test_v2_intake.py tests/data/test_v2_conversion.py tests/data/test_v2_license.py tests/data/test_v2_real_etl_cli.py -q` | Fail: 142 passed, 14 failed. Failures are concentrated in conversion tests reporting `MISSING_COLUMNS`. |
| `Test-Path -LiteralPath 'D:\codex_work\data'` | Pass: `True`. |
| `Get-ChildItem -LiteralPath 'D:\codex_work\data' -Force` | Pass. Observed three source dirs plus source archives. |
| `git ls-files \| rg "D:\\codex_work\\data|\.sdf$|\.mol2$|\.pdb$|\.cif$|\.csv$|\.tsv$|data/v2/staging|data/v2/processed|data/v2/reports"` | Fail for governance: tracked `data/v2/staging/*.tsv`, transform scripts, and reports were found. |
| `$env:PYTHONPATH='src'; python -m covalent_design.data.cli.v2_run_real_etl --raw-root D:\codex_work\data --staging-root data/v2/staging --out-root data/v2/processed --report-root data/v2/reports --source all` | Fail with exit code 1 from shell / CLI return 30. Output: `etl_complete=false`, `sources_converted=0`, `sources_failed=3`, report written to `data/v2/reports/window_c_real_etl_report.json`. |
| Python read-only manifest enumeration under `D:\codex_work\data` | Pass. Found three `source_manifest.json` files, but all fail JSON parsing with `Unexpected UTF-8 BOM`. |
| `$env:PYTHONPATH='src'; validate_v2_data_intake_manifest(D:\codex_work\data\*\source_manifest.json)` | Fail for all three: `V2_MANIFEST_INVALID_JSON`. |
| `$env:PYTHONPATH='src'; stage_source_manifest(data/v2/manifests/*_v2_manifest.json)` | Pass for repo-derived manifests; all three are `checksum_verified`. |
| `$env:PYTHONPATH='src'; convert_staged_manifest(data/v2/manifests/*_v2_manifest.json)` | Mixed: CovalentInDB 3,598 ok; CovBinderInPDB 7,375 ok; CovPDB receipt not ok with 10,515 partial payload and row parse errors. |

Debugging note: Verification failure was reproduced. Root cause is not an environment issue: conversion tests still use an older simplified TSV header, while `v2_conversion.py` now requires source-specific v1 parser columns.

Doubt-driven note: No external cross-model CLI was invoked. This review used internal adversarial checks only; the user request prohibited network activity and did not authorize external review tooling.

## Real Data Evidence Status

Formal evidence from the required command against `D:\codex_work\data`:

| source | raw data observed | manifest present | checksum verified | staging status | conversion status | license gate status | record count | training eligibility | blocking errors |
| --- | --- | --- | --- | --- | --- | --- | ---: | --- | --- |
| CovalentInDB | Yes: dir/archive observed | Yes: `D:\codex_work\data\CovalentInDB\source_manifest.json` | No | Not reached by formal CLI | Not reached by formal CLI | Not reached | 0 | Not eligible | Manifest has UTF-8 BOM; Task 40 validation returns `V2_MANIFEST_INVALID_JSON`; CLI reports `V2_ETL_SOURCE_MANIFEST_MISSING` because discovery silently ignores invalid JSON. |
| CovPDB | Yes: dir/archive observed | Yes: `D:\codex_work\data\CovPDB\source_manifest.json` | No | Not reached by formal CLI | Not reached by formal CLI | Not reached | 0 | Not eligible | Same: UTF-8 BOM / `V2_MANIFEST_INVALID_JSON`; CLI reports missing manifest. |
| CovBinderInPDB | Yes: dir/archive observed | Yes: `D:\codex_work\data\CovBinderInPDB\source_manifest.json` | No | Not reached by formal CLI | Not reached by formal CLI | Not reached | 0 | Not eligible | Same: UTF-8 BOM / `V2_MANIFEST_INVALID_JSON`; CLI reports missing manifest. |

Repo-derived evidence from `data/v2/manifests` and `data/v2/staging`:

| source | repo-derived manifest | repo-derived staging | repo-derived conversion | record count | can support Task 49? |
| --- | --- | --- | --- | ---: | --- |
| CovalentInDB | Pass | `checksum_verified` | Pass | 3,598 | No, because this is derived TSV evidence and the formal raw-root ETL gate fails. |
| CovBinderInPDB | Pass | `checksum_verified` | Pass | 7,375 | No, same reason. |
| CovPDB | Pass | `checksum_verified` | Receipt fails with row parse errors, partial payload exists | 10,515 partial | No. Partial payload with `receipt.ok=false` must not be treated as training input. |

## Core Question Answers

| # | Question | Answer |
| ---: | --- | --- |
| 1 | 真实 `D:\codex_work\data` 是否已被只读读取过？ | Yes. This review listed it and read manifests only; it did not modify it. |
| 2 | 三个源是否都已被处理？ | No under formal CLI. All three fail before staging/conversion/license. Repo-derived TSVs exist for all three, but that is not equivalent to formal raw-root processing. |
| 3 | 每个源是否都有 source manifest？ | Yes, under `D:\codex_work\data\<Source>\source_manifest.json`. |
| 4 | 每个 source manifest 是否实际通过 Task 40 validation？ | No. All three fail `V2_MANIFEST_INVALID_JSON` because of UTF-8 BOM. |
| 5 | 每个 raw file / transformed TSV 是否通过 checksum 校验？ | Raw-root formal path: No, staging not reached. Repo-derived TSV manifests: Yes for three derived TSVs. |
| 6 | 每个源是否通过 Task 41 staging？ | Raw-root formal path: No. Repo-derived manifests: Yes. |
| 7 | 每个源是否通过 Task 42 conversion？ | Raw-root formal path: No. Repo-derived path: CovalentInDB and CovBinderInPDB pass; CovPDB fails receipt with 63 row parse errors and partial payload. |
| 8 | 每个源是否通过 Task 43 license/provenance gate？ | Raw-root formal path: No, not reached. Existing 06-19 report claims all eligible, but this is not supported by the formal raw-root run. |
| 9 | `v2_conversion.py` 是否支持三个 parser target？ | It declares support for all three at `SUPPORTED_PARSER_TARGETS`, and has source-specific column schemas. However tests fail and CovPDB partial conversion fails, so support is not healthy enough for Task 49. |
| 10 | `v2_run_real_etl.py` 是 dry-run/report 还是 processed artifact producer？ | It is effectively a report-only runner. `--out-root` is created but no processed `SourceIngestRecord` artifact is written. |
| 11 | 转换结果是否是 v1-compatible `SourceIngestRecord`？ | Functionally yes for successful repo-derived conversions, but no durable processed artifact is emitted. Partial failed conversion still returns payload, which is unsafe for downstream consumption. |
| 12 | 是否保留 local path/checksum/source provenance/license audit ref？ | In `SourceIngestRecord` conversion, yes for repo-derived records. Formal raw-root path never reaches conversion. |
| 13 | 是否存在 `unknown` / `blocked` license 进入 training eligibility 的风险？ | The license module blocks `unknown` and `blocked`; no direct bypass found. The larger risk is `manual_exempt` being reported as training-ready before manifest/checksum/conversion prerequisites pass. |
| 14 | `manual_exempt` 是否只在 manual intake 下通过？ | Code enforces manual-only for `manual_exempt`; tests cover download-mode rejection. |
| 15 | 真实 raw data 是否被复制进 repo 或被 git 跟踪？ | External raw data under `D:\codex_work\data` is not tracked. But repo tracks derived real-data TSVs and reports under `data/v2/`. |
| 16 | `data/v2/staging/*.tsv`、transform scripts、manifest、report 是否应被跟踪？ | Current policy does not clearly allow derived real-data TSVs. Given they contain source-derived records, they should be treated as derived artifacts unless a policy explicitly permits tracking them. |
| 17 | `docs/v2/10`、`docs/v2/11`、06-18/06-19 reports 是否冲突？ | Yes. 06-19 says PASS/training eligible; 06-18, implementation plan, verification matrix, and formal rerun say not ready / blocked. |
| 18 | 是否可以进入 Task 49？ | No. |
| 19 | 如果不能，阻塞项是什么？ | Manifest BOM invalid JSON, formal raw-root ETL failure, failing tests, CovPDB partial conversion failure, no processed artifact output, and conflicting docs/governance around tracked derived data. |

## Code Findings

### Blocking

- **Severity:** Blocking
  - **File:** `D:\codex_work\data\*\source_manifest.json`; `src/covalent_design/data/v2_manifests.py`
  - **Evidence:** `validate_v2_data_intake_manifest()` reads with `encoding="utf-8"` at `src/covalent_design/data/v2_manifests.py:87-99`; all three real source manifests fail with `V2_MANIFEST_INVALID_JSON` / `Unexpected UTF-8 BOM`.
  - **Why it matters:** Task 40 is the first gate. If real manifests do not validate, no source can be considered staged, converted, licensed, or training eligible.
  - **Required fix:** Either rewrite the real `source_manifest.json` files as UTF-8 without BOM or deliberately update the manifest reader to accept UTF-8 BOM, then rerun Task 40 validation and real ETL.

- **Severity:** Blocking
  - **File:** `src/covalent_design/data/cli/v2_run_real_etl.py`
  - **Evidence:** Manifest discovery filters through `_is_v2_manifest()` at `src/covalent_design/data/cli/v2_run_real_etl.py:153-156`; `_is_v2_manifest()` catches JSON decode errors and returns `False` at `:279-289`; missing-source reports then fabricate expected lower-case `raw_root / parser_target / "manifest.json"` paths at `:249-258`.
  - **Why it matters:** Invalid manifests are reported as missing manifests, hiding the true root cause and pointing users at paths that do not match the actual `D:\codex_work\data\<Source>\source_manifest.json` layout.
  - **Required fix:** Report invalid candidate manifests as invalid, not missing. Discovery should either validate known source manifest filenames or surface every unreadable/invalid JSON candidate with `V2_MANIFEST_INVALID_JSON`.

- **Severity:** Blocking
  - **File:** `tests/data/test_v2_conversion.py`; `tests/data/test_v2_real_etl_cli.py`; `src/covalent_design/data/v2_conversion.py`
  - **Evidence:** Required pytest command failed: 142 passed, 14 failed. Failures are `MISSING_COLUMNS` for tests that still use simplified headers like `pdb_id/uniprot_id/residue/residue_number/ligand/ligand_name/bond_type/warhead_type`. Current `_COLUMN_SCHEMAS` require source-specific columns at `src/covalent_design/data/v2_conversion.py:511-577`, and missing columns fail at `:627-632`.
  - **Why it matters:** The Task 40-43 verification gate is red. Passing old tests was cited in docs, but the current test suite does not pass.
  - **Required fix:** Decide whether Task 42 supports only source-specific v1 parser TSV schemas or also the old simplified fixture schema. Then align fixtures, tests, and implementation and rerun the required pytest command.

- **Severity:** Blocking
  - **File:** `src/covalent_design/data/cli/v2_run_real_etl.py`
  - **Evidence:** `--out-root` is described as “Root directory for output records”, but the code only creates it at `src/covalent_design/data/cli/v2_run_real_etl.py:147-148`; converted records are held in memory at `:170`, extended at `:184`, used for license audit at `:195`, and only the report is written at `:205-208` / `:594-603`.
  - **Why it matters:** Even if conversion passed, there is no durable processed artifact for Task 49 to consume. A report saying counts passed is not a training dataset input.
  - **Required fix:** Add an explicit processed artifact contract or keep the command documented as report-only and not Task49-ready. Do not claim Task 49 readiness until a stable output artifact exists.

- **Severity:** Blocking
  - **File:** `src/covalent_design/data/v2_conversion.py`; `src/covalent_design/data/cli/v2_run_real_etl.py`
  - **Evidence:** `convert_staged_manifest(data/v2/manifests/covpdb_v2_manifest.json)` returns `receipt.ok=False`, 10,515 partial records, and row parse errors. `v2_run_real_etl.py` takes `records = list(conversion_envelope.payload)` even when `conversion_ok` is false at `:400-403`, and extends the global converted records at `:184`.
  - **Why it matters:** A downstream path can accidentally consume partial records from a failed conversion. The 06-19 report already demonstrates the confusion by presenting CovPDB as 10,515 converted records while also admitting 63 parse errors.
  - **Required fix:** Define partial conversion semantics. For Task 49 readiness, failed conversion receipts must not feed training eligibility or processed output unless there is an explicit partial-acceptance policy and denominator report.

- **Severity:** Blocking
  - **File:** `data/v2/staging/*`, `data/v2/reports/*`, `docs/reviews/v2-real-local-data-etl-evidence-review-2026-06-18.md`
  - **Evidence:** `git ls-files` shows tracked derived real-data TSVs, transform scripts, and reports. The 06-18 report says transformed TSV files and transform scripts are not committed and no TSV files are tracked at `docs/reviews/v2-real-local-data-etl-evidence-review-2026-06-18.md:124-129`.
  - **Why it matters:** The repository now contains source-derived real-data artifacts without a clear policy saying they may be tracked. That conflicts with the project’s data governance boundary and makes the review baseline untrustworthy.
  - **Required fix:** Decide artifact policy. Recommended: keep manifests/checksums/reports if allowed, but remove derived real-data TSVs from git unless explicitly approved by data governance and license policy.

### Important

- **Severity:** Important
  - **File:** `docs/reviews/v2-real-local-data-etl-evidence-review-2026-06-19.md`; `data/v2/reports/v2-real-data-pipeline-dry-run-2026-06-19.json`; `docs/v2/10-v2-implementation-plan.md`; `docs/v2/11-v2-verification-matrix.md`
  - **Evidence:** 06-19 says `Status: PASS` and all three sources `training_eligible=yes`; implementation plan at `docs/v2/10-v2-implementation-plan.md:337` says NOT READY and all three sources fail `V2_ETL_SOURCE_MANIFEST_MISSING`; verification matrix at `docs/v2/11-v2-verification-matrix.md:41` says `blocked-real-data`.
  - **Why it matters:** Future agents can pick the optimistic report and start Task 49 incorrectly.
  - **Required fix:** Mark the 06-19 report as superseded or corrected, and make one authoritative latest readiness record.

- **Severity:** Important
  - **File:** `src/covalent_design/data/v2_conversion.py`
  - **Evidence:** Imports v1 parsers at `:40-42` but the active path uses duplicated TSV schema mapping at `:511-577` and `_tsv_row_to_source_ingest_record()` at `:664-798`.
  - **Why it matters:** The comments claim alignment with v1 parser columns, but the implementation is a separate mapping layer that can drift from v1 parsers and contracts.
  - **Required fix:** Either remove unused parser imports and document the independent TSV bridge, or actually route through v1 parser contracts.

- **Severity:** Important
  - **File:** `data/v2/manifests/license_audit.json`; `src/covalent_design/data/v2_license.py`
  - **Evidence:** Repo-derived `license_audit.json` uses `source_name: "all"`. ADR 0038 permits minimal manual exemption semantics, but current reports present all sources as training eligible from this shared audit.
  - **Why it matters:** A shared audit may be acceptable if explicitly designed, but it should not obscure per-source reporting, especially when one source conversion failed.
  - **Required fix:** Clarify whether one `license_audit.json` may cover all three sources. If yes, report it as shared manual exemption and keep per-source prerequisite failures separate from license eligibility.

### Minor

- **Severity:** Minor
  - **File:** `src/covalent_design/data/cli/v2_run_real_etl.py`
  - **Evidence:** Comment at `:577-579` says ETL is complete when sources are converted or explicitly unsupported “(covpdb / covbinder_in_pdb)”, but `UNSUPPORTED_PARSER_TARGETS` is currently empty and all three parser targets are declared supported.
  - **Why it matters:** Stale comments encourage wrong interpretation of source status.
  - **Required fix:** Update comments when code is repaired.

## Test Findings

The current tests are not sufficient to claim Task 49 readiness:

- The required pytest command fails with 14 failures. That alone blocks readiness.
- The failure mode reveals a schema drift: old synthetic fixture TSVs no longer match current source-specific `_COLUMN_SCHEMAS`.
- The tests are useful synthetic checks, but they must not be treated as real-data evidence.
- Current tests do cover many failure paths: missing manifest, checksum mismatch, unsupported parser, missing license audit, forbidden training fields, blocked/unknown/manual_exempt license behavior, no network, no training artifacts, deterministic conversion.
- Missing coverage found in this review:
  - UTF-8 BOM manifests under `D:\codex_work\data`.
  - CLI discovery distinguishing invalid manifests from missing manifests.
  - Formal `v2_run_real_etl --raw-root D:\codex_work\data` with the actual source layout.
  - Partial conversion payload from failed receipt must not feed downstream training eligibility.
  - `--out-root` processed artifact contract.
  - Data-governance scan for tracked derived real-data TSVs.

## Documentation Drift

- **06-18 report vs 06-19 report:** 06-18 says `Task 49 may NOT start yet` and names pipeline integration gaps; 06-19 says `PASS`, 21,488 `SourceIngestRecords`, and all sources `training_eligible=yes`.
- **06-19 report vs formal CLI rerun:** 06-19 claims Task 40/41/42/43 passed for all sources; formal command against `D:\codex_work\data` produced `sources_failed=3`, `sources_converted=0`, `etl_complete=false`.
- **06-18 report vs git state:** 06-18 says transformed TSVs and transform scripts are not committed and no TSV files are tracked; `git ls-files` shows tracked `data/v2/staging/*.tsv` and `data/v2/staging/transform_*.py`.
- **implementation plan vs 06-19 report:** `docs/v2/10-v2-implementation-plan.md:337` says real evidence is NOT READY FOR TASK 49; 06-19 says PASS.
- **verification matrix vs 06-19 report:** `docs/v2/11-v2-verification-matrix.md:41` says `blocked-real-data`; 06-19 says all Task 40-43 gates pass.
- **evidence review vs inference-rules document:** `docs/reviews/v2-real-data-etl-inference-rules-and-changes.md` records many heuristic inference rules and known issues, but the 06-19 evidence report promotes the result to PASS without carrying those limitations into a blocking readiness decision.

## Data Governance Findings

- `D:\codex_work\data` was read-only inspected during this review. It was not modified.
- External raw data is not git-tracked by path, but repo-tracked derived data exists under `data/v2/staging`.
- `data/v2/staging/*.tsv` contains source-derived real-data rows and should be treated as derived data, not lightweight fixture evidence.
- `data/v2/reports/v2-real-data-pipeline-dry-run-2026-06-19.json` is tracked and claims training eligibility from derived evidence. This report must not be used as authoritative while formal raw-root ETL fails.
- Manifests/checksums/reports may be trackable if the project policy allows them, but the policy must clearly distinguish them from derived row-level data.
- `.gitignore` or artifact policy likely needs an update after deciding whether `data/v2/staging`, `data/v2/processed`, and `data/v2/reports` are allowed tracked artifacts.

## Task 49 Readiness

**NOT READY.**

No source is currently cleared for Task 49 through the formal raw-root ETL path:

- CovalentInDB: not ready.
- CovPDB: not ready.
- CovBinderInPDB: not ready.

Blocking items:

1. `D:\codex_work\data\*\source_manifest.json` fails Task 40 validation due UTF-8 BOM.
2. `v2_run_real_etl` formal command returns incomplete ETL: 0 converted, 3 failed.
3. Required pytest command fails with 14 conversion-related failures.
4. CovPDB repo-derived conversion is partial with `receipt.ok=false`.
5. `v2_run_real_etl.py` does not emit a durable processed artifact for Task 49.
6. Documentation/report state conflicts are severe enough that there is no single authoritative readiness record.
7. Repo currently tracks derived real-data TSVs/reports without a clear accepted governance policy.

## Required Fix Plan

1. **Fix blocking code/data-gate issues first.**
   - Make the three real `source_manifest.json` files pass Task 40 validation, either by removing BOM or intentionally supporting UTF-8 BOM.
   - Change `v2_run_real_etl` to report invalid manifests accurately instead of hiding them as missing.
   - Decide and implement a real processed artifact contract for `--out-root`, or document that the command is report-only and not a Task 49 gate.
   - Prevent partial failed conversion payloads from being treated as downstream-consumable training evidence.

2. **Fix tests next.**
   - Align synthetic fixtures with the current three-source schema, or explicitly keep backward-compatible simplified TSV support.
   - Add tests for BOM manifests, invalid-vs-missing manifest discovery, formal real-data layout, partial conversion semantics, and `--out-root` behavior.
   - Rerun the required pytest command until it passes.

3. **Fix documentation drift.**
   - Supersede or correct the 06-19 PASS report.
   - Make `docs/v2/10`, `docs/v2/11`, and latest `docs/reviews/*06-19*` agree on `NOT READY FOR TASK 49` until formal gates pass.
   - Carry heuristic inference limitations from `v2-real-data-etl-inference-rules-and-changes.md` into readiness language.

4. **Fix data governance.**
   - Decide whether `data/v2/staging/*.tsv`, transform scripts, manifests, and reports are tracked artifacts or derived artifacts.
   - If derived, remove them from git tracking and update `.gitignore` / artifact policy.
   - If tracked, document why source-derived TSVs are allowed and what license/provenance constraints apply.

5. **Finally rerun real ETL dry-run.**
   - Rerun the exact formal command against `D:\codex_work\data`.
   - Only consider Task 49 after manifest validation, checksum staging, conversion, license/provenance gate, processed artifact emission, and tests all pass.
