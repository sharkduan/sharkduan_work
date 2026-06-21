# V2 Real Data Import Repair - 2026-06-19

## Executive Summary

- **Overall Status:** PASS
- **是否允许进入 Task 49:** 不直接进入 Task 49；数据导入前置条件已完成，但当前项目顺序必须先完成 Task 45 和 Checkpoint V2-C。
- **最大风险摘要:** 当前三源真实 raw-root ETL 已通过，但 processed JSONL 是真实 row-level derived artifact，只应作为本地运行产物使用，不应纳入 git。`manual_exempt` 仍是 distinct license status，不等同于 `allowed`。

## Fixed Issues

| Finding | Resolution |
| --- | --- |
| UTF-8 BOM manifests failed as invalid JSON | Manifest readers now use BOM-safe UTF-8 handling while preserving structured JSON syntax errors. |
| Existing invalid manifests were reported as missing | `v2_run_real_etl` now discovers `source_manifest.json` / `manifest.json`, reports actual invalid manifests with their real paths, and no longer fabricates lower-case missing paths when a candidate exists. |
| 14 conversion tests failed with `MISSING_COLUMNS` | The real three-source v1-compatible schema remains supported, and the legacy 8-column synthetic covalentin_db fixture path is explicitly compatible. |
| Failed conversion partial payload could flow downstream | The CLI only sends `conversion_ok=True` records to the license gate and processed output. Failed conversion payload counts can be reported, but records are blocked from downstream. |
| `--out-root` had no processed artifact contract | The CLI writes `v2_real_etl_manifest.json` plus per-source local JSONL files for sources that pass manifest, checksum, conversion, and license gates. |
| Formal raw-root ETL did not process real data | The formal command over `D:\codex_work\data` now completes all three sources. |
| Documentation contradicted itself | The optimistic 06-19 evidence report is marked superseded/corrected; the implementation plan and verification matrix point to this repair report and current machine evidence. |
| Derived row-level artifacts were tracked | `.gitignore` now excludes v2 staging TSVs and processed JSONL; the previously tracked staging TSVs were removed from git tracking without deleting local files. |

## Commands Run

| Command | Result |
| --- | --- |
| `python -m pytest tests/data/test_v2_manifests.py tests/data/test_v2_intake.py tests/data/test_v2_conversion.py tests/data/test_v2_license.py tests/data/test_v2_real_etl_cli.py -q` | Pass: 160 passed |
| `python -m pytest -q` | Pass: 1938 passed, 6 skipped, 326 subtests |
| `python -m compileall -q scripts src` | Pass |
| `python -m covalent_design.data.cli.v2_run_real_etl --raw-root D:\codex_work\data --staging-root data/v2/staging --out-root data/v2/processed --report-root data/v2/reports --source all` | Pass: 3 converted, 0 failed, `etl_complete=true` |
| `git ls-files \| rg "D:\\codex_work\\data|\.sdf$|\.mol2$|\.pdb$|\.cif$|\.csv$|\.tsv$|data/v2/staging|data/v2/processed|data/v2/reports"` | Shows tracked reports and transform scripts; row-level staging TSVs were removed from tracking |

## Real Data ETL Results

| source | manifest validation | checksum staging | conversion | license gate | processed artifact | record count | training eligibility | errors |
| --- | --- | --- | --- | --- | --- | ---: | --- | --- |
| CovalentInDB | pass | checksum_verified | pass | manual_exempt pass | `data/v2/processed/covalentin_db.records.jsonl` | 3,598 | eligible via `manual_exempt` | none |
| CovPDB | pass | checksum_verified | pass | manual_exempt pass | `data/v2/processed/covpdb.records.jsonl` | 10,578 | eligible via `manual_exempt` | none |
| CovBinderInPDB | pass | checksum_verified | pass | manual_exempt pass | `data/v2/processed/covbinder_in_pdb.records.jsonl` | 7,375 | eligible via `manual_exempt` | none |

## Processed Artifact Contract

`data/v2/processed/v2_real_etl_manifest.json` is the future Task 49 handoff manifest once the project sequence reaches Task 49. It contains:

- `contract_version`
- `pipeline`
- `etl_complete`
- per-source `source_name`, `parser_target`, `record_count`, `records_path`, checksum, local path provenance, license audit ref, license status, and gate status
- `total_records`

Each per-source `.records.jsonl` file contains deterministic JSON serialization of `SourceIngestRecord` values. Only sources that pass manifest validation, checksum staging, conversion, and license/provenance gate are written.

## Partial Conversion Policy

Failed conversions do not enter downstream:

- no license gate input,
- no processed JSONL output,
- no training eligibility,
- no successful source manifest entry.

Partial records may be counted in the ETL report for diagnostics only. There is no partial-acceptance policy in this repair.

## Documentation Corrections

- `docs/reviews/v2-real-local-data-etl-evidence-review-2026-06-19.md` is marked superseded/corrected.
- `docs/v2/10-v2-implementation-plan.md` now records the corrected formal raw-root ETL command and readiness.
- `docs/v2/11-v2-verification-matrix.md` marks V2-B as `verified-real-data`.
- `docs/v2/05-v2-data-automation-spec.md` and `docs/v2/09-v2-interface-and-contract-changes.md` now describe three-source raw-source parsing and the processed artifact boundary.

## Data Governance

- Raw data remains external under `D:\codex_work\data` and is not copied into the repository.
- Real row-level staging TSVs and processed JSONL are local derived artifacts. They are ignored by `.gitignore` and must not be committed.
- Transform scripts are retained as auditable code/evidence.
- Reports and processed manifests may be tracked as audit evidence when they do not embed row-level raw-derived payloads.
- `manual_exempt` remains distinct from `allowed`; unknown/blocked license states remain blocked.

## Remaining Risks

- The CovPDB conversion uses LINK-record inference and source-local structure parsing. This is acceptable for v2-beta ETL evidence, but downstream model/data quality tasks should preserve provenance and review any chemistry-specific assumptions.
- `manual_exempt` is a user-frozen decision and remains a compliance responsibility marker, not a third-party license verification result.

## Final Verdict

**DATA-INTAKE PREREQUISITE COMPLETE FOR FUTURE TASK 49.**

Sources that may enter future Task 49 via the processed manifest once intervening project phases complete:

- CovalentInDB
- CovPDB
- CovBinderInPDB

The current next stage remains Task 45 / Checkpoint V2-C, not Task 49. When the project sequence later reaches Task 49, it must consume the processed manifest/JSONL boundary and preserve license/provenance metadata. It must not reclassify `manual_exempt` as `allowed`.
