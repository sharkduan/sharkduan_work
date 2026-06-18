# Checkpoint V2-A Environment Gate Review - 2026-06-16

## Executive Summary

- Overall status: PASS WITH RISKS
- Can start Task 40: Yes
- Highest risk areas: heavy dependency solver compatibility remains unverified; PMDM is blocked by unknown upstream license; no lock file has been generated.
- Required next action: start Task 40 only within its lightweight manifest-schema boundary. Do not install heavy dependencies, download real data, or import/execute PMDM/PocketFlow/RDKit/PyTorch/CUDA paths.

Checkpoint V2-A confirms that the v2-beta environment plan is executable before data or training work. It verifies the scaffold, source verification record, lightweight smoke path, heavy structured-unavailable behavior, and ADR 0037 boundary. It does not approve heavy runtime execution.

## Verification Results

| Command | Exit code | Result | Notes |
| --- | ---: | --- | --- |
| `git status --short` | 0 | pass | Working tree contains expected Task 38/39/V2 documentation and smoke-probe changes; no staging or commit performed. |
| `git diff --stat` | 0 | pass | Diff is documentation/environment scaffold plus `scripts/v2_smoke_check.py`; no `src/`, PMDM, PocketFlow, or Task 40 implementation changes observed. |
| `python -m pytest tests/v2/test_smoke_check.py -q` | 0 | pass | 11 smoke-probe tests passed. |
| `python scripts/v2_smoke_check.py --profile lightweight` | 0 | pass | Project import passes; all six heavy dependency statuses are `not_checked`; no warnings or errors. |
| `python scripts/v2_smoke_check.py --profile heavy` | 2 | expected structured unavailable | Missing PyTorch/RDKit/PocketFlow and PMDM license block are reported as structured statuses; no traceback. Docking binary was detected on PATH. |
| `python scripts/v2_smoke_check.py --profile cpu` | 3 | expected structured failure | Unsupported profile rejected with `V2_ENV_PROFILE_UNSUPPORTED`; supported profiles are `lightweight` and `heavy`. |
| `python -m compileall -q scripts src` | 0 | pass | No syntax/bytecode compile failures. |
| `python -m pytest -q` | 0 | pass | 1772 tests passed, 326 subtests passed. |
| `python -m unittest discover -s tests -t . -q` | 0 | pass | 1761 unittest tests passed. |
| `rg -n "dependency / package\|official source URL\|license status\|verification date\|owning task" docs/v2/dependency-source-verification.md` | 0 | pass | Required source-verification columns present. |
| `rg -n "verified\|unverified\|blocked\|not required yet" docs/v2/dependency-source-verification.md` | 0 | pass | Status vocabulary and dependency rows present. |
| `rg -n -- "--profile cpu\|cpu profile" docs/v2 docs/adr scripts tests` | 0 | pass | `cpu` rejection documented/tested. |

## Task 37 Evidence

- `environment.yml` exists and remains an environment scaffold, not a solved lock file.
- `scripts/v2_smoke_check.py` exists and is stdlib-only at module import time.
- `docs/adr/0037-v2-environment-and-heavy-dependency-boundary.md` exists and defines the `lightweight`/`heavy` boundary.
- `lightweight` profile result: exit 0, `status: pass`, heavy dependencies all `not_checked`.
- `heavy` profile result: exit 2 in the current environment, `status: unavailable`, missing or blocked dependencies reported structurally.
- `cpu` rejection result: exit 3, `status: failed`, `exit_reason: unsupported_profile`.
- ADR 0037 consistency: implementation and tests use only `lightweight` and `heavy`; `cpu` is invalid.

Verdict: PASS. The scaffold exists and enforces the expected profile vocabulary.

## Task 38 Evidence

- `docs/v2/dependency-source-verification.md` exists.
- The dependency table records the required columns: dependency/package, claimed capability, official source URL, version scope, license status, verification date, status, and owning task.
- Status distribution observed from the table: 12 `unverified`, 1 `blocked`, 2 `not required yet`, 0 `verified`.
- PMDM is explicitly `blocked`: upstream/local PMDM lacks a LICENSE file, so PMDM must not be imported, loaded, or executed.
- PocketFlow license status is recorded as MIT via upstream file `Liscense`, but it remains `not required yet`.
- Lock workflow is documented, but no Conda/Mamba solve or lock generation was performed.
- No unverified dependency claim is marked verified without an official source.

Verdict: PASS WITH RISKS. The source-verification document is complete enough for Checkpoint V2-A, but heavy dependency compatibility is not solved and PMDM remains blocked.

## Task 39 Evidence

- `tests/v2/test_smoke_check.py` exists and passes: 11 tests.
- JSON output is deterministic for lightweight profile.
- Heavy missing dependencies produce structured statuses and no traceback.
- Dependency status enum is frozen as `available`, `unavailable`, `not_checked`, `failed`.
- PMDM heavy probe does not import PMDM while license is unknown; it reports `status: unavailable`, `reason: license_unknown`, and `import_attempted: false`.
- CUDA is `not_checked` when PyTorch is unavailable.
- Default/lightweight path does not require RDKit, PyTorch, CUDA, PMDM, PocketFlow, or docking.

Verdict: PASS. The smoke-probe contract is implemented, documented, and tested.

## ADR 0037 Boundary Check

- Lightweight path: checks project import and marks heavy dependencies `not_checked`; it does not hard-import heavy dependency packages.
- Heavy path: opt-in/manual via `--profile heavy`; missing dependencies are structured status records, not tracebacks.
- Default CI: remains lightweight; no CI change was made to install heavy dependencies.
- Source verification: heavy dependencies remain behind documented verification and lock-generation gates.
- Unavailable dependency behavior: heavy profile exits non-zero with JSON, while lightweight remains green.

Verdict: ADR 0037 is enforced by the current implementation and documentation.

## Findings By Severity

### P0 Blocking

None.

### P1 Important

1. Title: Heavy dependency version compatibility remains unresolved.
   Evidence: `dependency-source-verification.md` lists PyTorch, CUDA, RDKit, PyG stack, Conda/Mamba, pip, and project editable install as `unverified`; no lock file exists.
   Impact: Heavy runtime, model integration, and PMDM adapter work cannot rely on a solved environment yet.
   Recommended fix: Perform the documented lock workflow in a later dependency-lock task after source verification is complete.
   Suggested skill: source-driven-development.

2. Title: PMDM remains blocked by unknown license.
   Evidence: PMDM row is `blocked`; Task 39 smoke reports PMDM `unavailable` with `reason: license_unknown` and `import_attempted: false`.
   Impact: PMDM import/execution paths remain unavailable until license is resolved or a narrow non-importing waiver applies.
   Recommended fix: Resolve upstream license status or keep all PMDM execution paths blocked.
   Suggested skill: documentation-and-adrs.

3. Title: Task 39 review summary has one stale count.
   Evidence: `docs/reviews/task39-smoke-probe-review-2026-06-16.md` says "All 10 tests" in the summary, while the command block and current test run confirm 11 tests.
   Impact: Documentation inconsistency only; it does not affect code, tests, or Checkpoint V2-A outcome.
   Recommended fix: Update the Task 39 review summary count when normal documentation cleanup is allowed.
   Suggested skill: documentation-and-adrs.

### P2 Moderate

1. Title: Project editable install remains unresolved.
   Evidence: `dependency-source-verification.md` records no `pyproject.toml` or `setup.py` yet.
   Impact: Future package install and lock workflows need project packaging metadata.
   Recommended fix: Add project packaging in a later packaging task.
   Suggested skill: api-and-interface-design.

2. Title: PyG dependency row scopes are inherited from PMDM Python 3.9 pins.
   Evidence: Source verification records PMDM `mol.yml` pins while V2 targets Python 3.10.
   Impact: Future solver work may find version incompatibilities.
   Recommended fix: Split exact V2 version compatibility from PMDM reference pins before lock approval.
   Suggested skill: source-driven-development.

### P3 Minor

1. Title: Deterministic generated timestamp is a sentinel.
   Evidence: `scripts/v2_smoke_check.py` uses `1970-01-01T00:00:00Z` for deterministic smoke output.
   Impact: The field should not be treated as a real provenance timestamp.
   Recommended fix: Keep as-is for smoke tests or document it as a deterministic sentinel if reused in a manifest context.
   Suggested skill: documentation-and-adrs.

## Remaining Risks

- Heavy dependency versions: PyTorch/CUDA/RDKit/PyG/PMDM stack compatibility is unverified until a future solver run and lock file.
- PMDM/PocketFlow license: PMDM is blocked by unknown license; PocketFlow is MIT but not required yet.
- Future lock generation: no authoritative lock file exists; documented workflow is pending.
- Default CI boundary: currently lightweight-only; future CI changes must not install heavy dependencies without an explicit task and review.
- Source verification gaps: 0 dependency rows are currently `verified`; this is acceptable for V2-A but must be addressed before heavy execution tasks.

## Final Verdict

Task 40 may start.

Task 40 start boundary:

- Allowed: lightweight schema/design work for real data intake manifests.
- Not allowed: installing heavy dependencies, solving environments, downloading real data, importing/executing PMDM/PocketFlow/RDKit/PyTorch/CUDA, training, sampling, docking, inference, or evaluation.
- PMDM remains blocked for execution paths until license status is resolved.
- Heavy dependency compatibility remains outside Task 40 scope.
