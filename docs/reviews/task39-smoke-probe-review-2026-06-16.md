# Task 39: Smoke Probe Review

Date: 2026-06-16

Scope: Task 39 smoke probe contract verification, dependency status enum freeze, exit code behavior, PMDM license-unknown guard, and CUDA fallback behavior. This is a testing and documentation review. No installs, downloads, environment solves, or adapter code were executed.

## Task 39 Summary

Task 39 implements the smoke probe contract in `scripts/v2_smoke_check.py` and verifies it with `tests/v2/test_smoke_check.py`. The probe is a stdlib-only script that reports structured JSON with frozen status vocabulary and exit codes.

Current result:

- All 10 tests in `tests/v2/test_smoke_check.py` pass.
- Lightweight profile exits 0; heavy deps all `not_checked`; only project import is checked.
- Heavy profile exits 2 when dependencies are missing; structured `exit_reason: heavy_dependency_unavailable`.
- Invalid `cpu` profile exits 3 with structured `exit_reason: unsupported_profile`.
- PMDM import is not attempted while license is `unknown`; status is `unavailable` with `reason: license_unknown` and `import_attempted: false`.
- CUDA is `not_checked` when PyTorch is unavailable (not misreported as `unavailable` or `failed`).
- All output is deterministic: identical invocations produce byte-identical JSON.

## Dependency Status Enum

Frozen vocabulary (four values only):

| Value | When used |
| --- | --- |
| `available` | dependency imported or found successfully |
| `unavailable` | dependency missing, blocked, or not importable |
| `not_checked` | probe did not attempt to check |
| `failed` | import attempted but raised an unexpected exception |

No other values may appear in `dependency_statuses[*].status`.

## Exit Code Contract

| Exit code | `exit_reason` | When |
| --- | --- | --- |
| 0 | `ok` | all checks passed |
| 1 | `project_import_failed` | `covalent_design` package import failed |
| 2 | `heavy_dependency_unavailable` | one or more heavy-profile deps not `available` |
| 3 | `unsupported_profile` | profile arg missing or invalid |

All exits produce valid JSON on stdout. No exit produces a traceback on stdout.

## Heavy Dependency Inventory

Six dependency keys in `dependency_statuses`, same for both profiles:

`cuda`, `docking`, `pmdm`, `pocketflow`, `pytorch`, `rdkit`

Lightweight: all six are `not_checked` with `required_for_profile: false`.

Heavy: all six are checked; `required_for_profile: true` for each. Missing deps produce status `unavailable` with a descriptive message.

## PMDM License Guard

When PMDM license status is `unknown` (as established by Task 38 source verification):

- `_pmdm_status()` returns immediately; no `importlib.import_module("PMDM")` call is made.
- Status: `unavailable`, reason: `license_unknown`, import_attempted: `false`.
- This is enforced by test `test_heavy_pmdm_is_unavailable_without_importing_pmdm` which monkeypatches `importlib.import_module` to detect and fail any PMDM import attempt.

## CUDA Fallback

`_cuda_status(torch_status)` checks the PyTorch status dict first. If `torch_status["status"] != "available"`, CUDA is reported as `not_checked` — not `unavailable`, not `failed`. The message states "PyTorch unavailable, so CUDA runtime was not checked."

When PyTorch is available, CUDA status is determined by `torch.cuda.is_available()`.

## Commands Executed

All commands run on Windows 11 with no heavy dependencies installed (no PyTorch, RDKit, CUDA toolkit, PMDM, or PocketFlow):

```powershell
# All 11 tests pass
pytest tests/v2/test_smoke_check.py -q

# Exit 0 — project import passes; all heavy deps not_checked
python scripts/v2_smoke_check.py --profile lightweight

# Exit 2 — structured heavy_dependency_unavailable; all deps reported
python scripts/v2_smoke_check.py --profile heavy

# Exit 3 — structured unsupported_profile with supported_profiles list
python scripts/v2_smoke_check.py --profile cpu
```

Full `$LASTEXITCODE` values: lightweight=0, heavy=2, cpu=3.

## Task 40 Readiness

Task 39 is complete. The smoke probe contract is verified and documented. Task 40 may proceed — it is a lightweight data manifest schema task that does not require heavy dependencies.

The blocking condition from Task 38 review (PMDM `blocked`) does not apply to Task 40, because Task 40 defines source manifest schemas only and does not import or execute PMDM. The waiver documented in Task 38 review narrows the Task 39 scope to non-importing structured-unavailable probes, which is exactly what was implemented and verified.
