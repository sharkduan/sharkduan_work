# Task 37: Environment Scaffold Review

Date: 2026-06-16

Scope: Task 37 verification commands against the v2 environment scaffold, recorded exit codes and structured output, and readiness assessment for Task 38. This review does not modify `environment.yml`, `scripts/v2_smoke_check.py`, `src/`, `tests/`, `.github/`, PMDM, PocketFlow, or other docs. Only this review document is created.

## Task 37 Summary

Task 37 finalized the initial v2 environment interface without running training. Deliverables:

- `environment.yml`: Conda/Mamba environment scaffold with Python, pip, and placeholder channels/dependencies annotated `UNVERIFIED`. Heavy optional dependencies (PyTorch, CUDA, RDKit, PMDM-related graph packages, PocketFlow, docking) remain commented out as per ADR 0037 boundary.
- `scripts/v2_smoke_check.py`: stdlib-only smoke probe supporting `--profile lightweight` and `--profile heavy`. Lightweight mode reports heavy dependencies as `not_required` without importing them. Heavy mode reports structured `available` / `unavailable` / `failed` statuses for each dependency.
- `docs/adr/0037-v2-environment-and-heavy-dependency-boundary.md`: accepted ADR freezing `lightweight` and `heavy` as the only v2 smoke profile names.
- `docs/v2/04-v2-dependency-and-environment-spec.md`: hardened spec consistent with ADR 0037 vocabulary.
- `docs/v2/10-v2-implementation-plan.md`: Task 37 acceptance and verification documented.
- `docs/v2/11-v2-verification-matrix.md`: Task 37 row with primary command and evidence.

## Files Changed

Task 37 created or updated:

- `environment.yml` (new)
- `scripts/v2_smoke_check.py` (new)
- `docs/reviews/task37-environment-scaffold-review-2026-06-16.md` (new)

No files under `src/`, `tests/`, `.github/`, `PMDM/`, or `PocketFlow/` were modified by Task 37. No training, download, or artifact generation was performed.

## Collaboration Evidence

- Window A produced the read-only Task 37 interface plan for `environment.yml`, `scripts/v2_smoke_check.py`, profile semantics, output schema, exit codes, and review risks.
- Window B created `environment.yml` within its assigned file boundary. The main controller narrowed active dependencies afterward to keep the scaffold minimal and avoid unverified active package claims.
- Window C created `scripts/v2_smoke_check.py` within its assigned file boundary. The main controller adjusted the status schema and heavy-unavailable exit behavior to match ADR 0037 and Task 37 acceptance.
- Window D created this review note.
- Window E completed final read-only review after the final diff and found no P0/P1/P2 blockers. Window E allowed Task 38 to start.

## Commands Run

All commands were run from repository root with `$env:PYTHONPATH='src'`.

### Lightweight Smoke

```powershell
python scripts/v2_smoke_check.py --profile lightweight
```

Result: pass, exit code 0.

Structured JSON output confirmed:

- `profile`: `lightweight`
- `overall_status`: `pass`
- `checks.project_import.status`: `pass`
- all heavy dependencies (`pytorch`, `rdkit`, `pmdm`, `pocketflow`, `cuda`, `docking`) reported as `not_required` with `required_for_profile: false`
- no errors or warnings
- `contract_version`: `v2-beta`
- `schema_version`: `1.0.0`

### Heavy Smoke

```powershell
python scripts/v2_smoke_check.py --profile heavy
```

Result: structured unavailable, exit code 2, no traceback.

Structured JSON output confirmed:

- `profile`: `heavy`
- `overall_status`: `unavailable`
- `checks.project_import.status`: `pass`
- `pytorch`: `unavailable` (ImportError, no module named `torch`)
- `rdkit`: `unavailable` (ImportError, no module named `rdkit`)
- `pmdm`: `unavailable` (ImportError, no module named `PMDM`)
- `pocketflow`: `unavailable` (ImportError, no module named `PocketFlow`)
- `cuda`: `unavailable` (PyTorch unavailable, so CUDA runtime was not checked)
- `docking`: `available` in this local environment because `vina` was found on PATH. This does not install or select a docking engine for v2-beta; it is only a structured local probe result.
- warnings array contained one `V2_ENV_DEPENDENCY_UNAVAILABLE` entry per missing required heavy dependency
- no errors array entries because project import succeeded
- exit code 2 distinguishes heavy-unavailable from lightweight-pass and from exit code 1 failed states

### Unsupported Profile

```powershell
python scripts/v2_smoke_check.py --profile cpu
```

Result: structured `V2_ENV_PROFILE_UNSUPPORTED`, exit code 3.

Structured JSON output confirmed:

- `overall_status`: `failed`
- `errors[0].code`: `V2_ENV_PROFILE_UNSUPPORTED`
- `errors[0].supported_profiles`: `["lightweight", "heavy"]`
- no dependency statuses populated because the report failed before profile-dependent checks

### Missing Profile Argument

```powershell
python scripts/v2_smoke_check.py
```

Result: exit code 3, same `V2_ENV_PROFILE_UNSUPPORTED` error as unsupported profile.

### Compileall

```powershell
python -m compileall -q scripts src
```

Result: pass, exit code 0.

### Full Regression

```powershell
python -m pytest -q
python -m unittest discover -s tests -t . -q
```

Results:

- `pytest`: 1761 passed, 326 subtests passed
- `unittest discover`: 1761 tests, OK

## No Heavy Install

No `conda`, `mamba`, `pip`, or other package manager was invoked. Heavy dependencies (PyTorch, RDKit, CUDA toolkit, PMDM, PocketFlow, docking engines, graph libraries) remain uninstalled by Task 37. The environment scaffold is a placeholder file with all heavy dependencies commented out and annotated `UNVERIFIED`.

## No Training, Download, Or Artifacts

No model training, data download, network access, sampling, evaluation, checkpoint, tuning, or artifact generation was performed. This task is strictly an environment interface and smoke probe.

## Remaining Risks

| Risk | Severity | Notes |
| --- | --- | --- |
| Heavy dependency versions and APIs are unverified | P1 | Task 38 must source-verify PyTorch, CUDA, RDKit, PMDM, PocketFlow, and graph dependency versions/license status from official sources. All placeholders are currently `UNVERIFIED`. |
| `environment.yml` has not been solver-validated | P1 | No `conda env create` or `mamba env create` has been run. Channel/version solve may fail when heavy dependencies are uncommented and pinned. |
| PMDM/PocketFlow license status is unknown | P1 | Task 38 must record license status or mark as blocking/unknown before any real PMDM import path is exercised. |
| Heavy profile not tested with real dependencies | P2 | Heavy smoke was run on Windows without PyTorch/RDKit/PMDM/PocketFlow installed. First real heavy-pass exit-code-0 requires a Linux/WSL2 Conda environment with verified package versions. |
| No heavy test marker/pytest integration yet | P2 | Task 39 will add `tests/v2/test_smoke_check.py` and pytest marker policy. The smoke script is standalone stdlib-only and does not yet integrate with the test framework. |
| CUDA runtime not probed | P2 | CUDA status correctly cascaded from PyTorch unavailability. Real CUDA availability can only be validated on a GPU-equipped Linux/WSL2 host. |

## Task 38 Readiness

Task 38 may start. The environment scaffold and smoke script are in place, the profile vocabulary is frozen per ADR 0037, lightweight smoke passes, heavy smoke reports structured unavailable with correct exit codes, and unsupported-profile rejection works. Task 38's scope - source-verifying dependency versions and defining the lock workflow - is independent of heavy dependency installation and can proceed with documentation-only changes.

## Decision

Task 37 verification is complete. Lightweight smoke passes (exit 0), heavy smoke reports structured unavailable (exit 2, no traceback), unsupported profile is rejected with `V2_ENV_PROFILE_UNSUPPORTED` (exit 3), `compileall` passes, and full regression tests pass. No heavy dependencies were installed, and no training, download, or artifact generation occurred. Task 38 may start after main-controller confirmation.
