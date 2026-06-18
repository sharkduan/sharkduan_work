# V2 Local Real Data Policy Review

Date: 2026-06-16
Scope: documentation-only revision for user-provided local real data

## Executive Summary

Overall status: PASS WITH RISKS.

Selected policy: v2-beta uses user-provided local real data under `D:\codex_work\data`. Agents must not perform network download of real source data by default.

Whether Task 41 may start: Yes, within the local manual staging boundary. Task 41 may use fixtures and later read user-provided local data only through manifest/checksum/license/provenance validation. This documentation task did not read `D:\codex_work\data`.

Whether real download is allowed yet: No. Agent-managed network download is not part of the v2-beta default path. Automatic download is a future optional capability only after explicit approval and a separate task/decision.

## Current Data Acquisition Policy

- Real data is provided by the user.
- Local raw data root: `D:\codex_work\data`.
- Files under that root are untrusted until validated.
- Required guards: source manifest, SHA-256 checksum, parser target validation, source provenance, and license audit.
- `unknown` and `blocked` license statuses may be recorded for audit, but must not enter training.
- Real raw data, real weights, and real docking outputs must not be committed to git.

## Updated Task Slicing

| Task | Updated meaning |
| --- | --- |
| Task 40 | Manifest schema and validation only. Already implemented; no download/staging/conversion/training. |
| Task 41 | Local real data manual staging fixtures and CLI boundary. Default verification remains fixture-based and no-network. |
| Task 42 | Conversion from validated local staged inputs to v1 ETL inputs. No remote source access. |
| Task 43 | License/provenance training gate over local staged manifests. `unknown`/`blocked` fail eligibility. |

## Claim Review

| Claim | Evidence For | Evidence Against | Verdict | Required Fixes |
| --- | --- | --- | --- | --- |
| V2 docs say real data is local user-provided data | `01`, `03`, `05`, `10`, `11` mention `D:\codex_work\data` | Task 40 implementation still has `intake_mode = download` as a schema value | PASS | Keep documenting that `download` records source origin and does not authorize agent network download |
| Default tests and default CI do not network | `05` No Agent Network Download Rule; `11` Task 41 remains lightweight fixture verification | Existing fixture name includes `download_valid` | PASS | Future implementation should consider renaming fixtures if confusion persists |
| Real data requires manifest/license/provenance/checksum | `03`, `05`, `10`, `11`, `12` all state these checks | None found in allowed docs | PASS | None |
| Task slicing still follows v1 style | Task 41/42/43 remain separate: staging, conversion, license gate | Task 41 is already implemented under prior wording | PASS WITH RISK | Future Task 41 follow-up may need docs/code alignment if command names change |
| `unknown`/`blocked` license cannot train | `03`, `05`, `10`, `11`, `12` preserve this | None found | PASS | None |
| Real raw data is not committed to git | `00`, `01`, `03`, `05`, `10`, `11`, `12` state no git tracking | No `.gitignore` change was made in this docs-only task | PASS WITH RISK | When implementation starts, verify `.gitignore` or equivalent excludes real data paths |

## Verification Matrix Changes

- Task 41 mode changed from `network-manual` to `local-data-manual`.
- V2-B checkpoint now requires local staging from `D:\codex_work\data`, no raw-data git tracking, and no unknown/blocked training source.
- Mode vocabulary now includes `local-data-manual` and `future-network-optional`.

## ADR Decision

No new ADR was added.

Reason: the local real data policy is a confirmed v2-beta operational policy, but it does not yet change a canonical code contract or long-term repository-wide data acquisition architecture. `docs/v2/13-v2-task-adr-coverage.md` now records future ADR triggers if automatic download becomes default, if `D:\codex_work\data` becomes a long-term canonical root beyond v2-beta, or if license eligibility semantics change release policy.

## Findings

| Severity | Finding | Status |
| --- | --- | --- |
| P0 | Real raw data could be committed if implementation lacks ignore rules | mitigated in docs; must verify during implementation |
| P1 | Task 40 schema still contains `download` mode, which can be misread | mitigated by docs clarifying source-origin recording vs agent download permission |
| P1 | User-provided local data can be falsely trusted | mitigated by manifest/checksum/parser/license/provenance requirements |
| P2 | Automatic download remains as future optional capability | acceptable; not a v2-beta default path |

## Final Verdict

Task 41 may proceed as local manual staging work.

Task 41 does not permit agent-managed network download.

Real local data may be read only in a future implementation/review context where the filesystem rules allow it and the read is tied to a manifest, checksum, license, parser, and provenance validation path. This documentation task did not read or modify `D:\codex_work\data`.
