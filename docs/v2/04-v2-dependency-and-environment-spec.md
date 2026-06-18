# V2 Dependency And Environment Spec

Date: 2026-06-16
Status: hardened planning spec

## Environment Decision

V2-beta targets Linux/WSL2 with Conda or Mamba and one CUDA-capable NVIDIA GPU. Windows remains a lightweight-check environment only. Docker is not the first implementation path unless Conda/Mamba solve proves unreliable.

ADR 0037 freezes the v2 smoke profile names as `lightweight` and `heavy`. `cpu` is not a v2 smoke profile; CPU may describe a later runtime mode, but smoke commands must use one of the two profile names.

## Install Strategy

Task 37+ should add and verify:

- `environment.yml`
- `scripts/v2_smoke_check.py`
- optional lock output after source verification
- heavy/manual verification instructions

The first environment task may create files and smoke probes, but it must not train.

## Smoke Profile Vocabulary

| Profile | Purpose | Default CI | Dependency boundary |
| --- | --- | --- | --- |
| `lightweight` | Windows-local and default-CI health check | Yes | Must not hard-import RDKit, PyTorch, CUDA-only packages, PMDM, PocketFlow, docking tools, or other heavyweight optional dependencies. |
| `heavy` | Opt-in validation for real heavyweight integrations | No | May import heavyweight optional dependencies only after the dependency and API claims are source-verified. |

## RDKit Use Cases

RDKit is required only in the heavy v2 profile for:

- molecule parsing/normalization smoke,
- sanitize/valence checks,
- scaffold key implementation,
- descriptor and drug-likeness reporting,
- generated molecule validity reporting.

RDKit must not be used as the authoritative mmCIF writer unless a later task source-verifies the exact API and accepts that backend.

## PyTorch Use Cases

PyTorch is required only in the heavy v2 profile for:

- tensor conversion adapters,
- PMDM adapter smoke,
- covalent heads on real tensors,
- CPU smoke training,
- single-GPU training,
- checkpoint save/load smoke.

PyTorch tensors must not replace public serializable contract objects at package seams.

## CUDA/GPU Policy

- Lightweight smoke path comes first.
- Single-GPU path comes second.
- Multi-GPU/DDP is out of v2-beta scope.
- GPU absence is a heavy-profile failure, not a default-CI failure.

## Heavy Test Marker And Skip Policy

- Lightweight tests must run without heavyweight optional dependencies and must not import them at module import time.
- Heavy tests must be marked before they import heavyweight dependencies.
- Heavy tests must report a structured unavailable status when their dependency, platform, license, or source verification prerequisite is absent.
- A skipped heavy test is acceptable only when it records which prerequisite was unavailable.
- Default CI may collect heavy tests, but must not execute heavyweight dependency paths unless the `heavy` profile is explicitly selected.

## Version Verification Requirement

Exact versions must be source-verified before locking. Required official sources:

- PyTorch install matrix.
- CUDA compatibility documentation.
- RDKit installation documentation.
- Conda/Mamba environment documentation.
- PMDM repository environment and license files.
- PocketFlow repository environment and license files if used.
- PyG or graph library documentation if required by PMDM.

Any version not verified from official sources must be marked `UNVERIFIED`.

## Failure Modes

| Failure | Required behavior |
| --- | --- |
| environment solve fails | emit dependency failure report, do not continue to training |
| PyTorch import fails | heavy profile fails, default CI unaffected |
| CUDA unavailable | CPU smoke may pass, GPU smoke fails explicitly |
| RDKit import fails | chemistry heavy checks fail explicitly |
| PMDM import/API fails | PMDM path blocked; baseline only if explicitly configured |
| license unknown | source/dependency cannot enter training path |

## Dependency Status Vocabulary

Task 39 freezes the dependency status enum. Every dependency entry in `dependency_statuses` must use exactly one of these values:

| Status | Meaning |
| --- | --- |
| `available` | dependency imported successfully and is usable |
| `unavailable` | dependency is missing, blocked, or not importable |
| `not_checked` | probe did not attempt to check this dependency |
| `failed` | import was attempted but raised an unexpected exception |

## Exit Codes

Task 39 freezes structured exit codes for `v2_smoke_check.py`. All exits produce valid JSON on stdout:

| Exit code | `exit_reason` | Condition |
| --- | --- | --- |
| 0 | `ok` | all required checks passed |
| 1 | `project_import_failed` | `covalent_design` package import failed |
| 2 | `heavy_dependency_unavailable` | one or more heavy-profile dependencies are not `available` |
| 3 | `unsupported_profile` | profile arg missing or not one of `lightweight` / `heavy` |

## PMDM License-Unknown Behavior

When PMDM license status is `unknown`, the heavy probe must not attempt to import PMDM. Task 39 encodes this as:

- `dependency_statuses.pmdm.status` = `unavailable`
- `dependency_statuses.pmdm.reason` = `license_unknown`
- `dependency_statuses.pmdm.import_attempted` = `false`

No PMDM module path, version, or API inspection occurs while the license is unresolved.

## CUDA Behavior When PyTorch Unavailable

When PyTorch is not `available` in the heavy profile, CUDA is reported as `not_checked` rather than `unavailable` or `failed`. The message clarifies that CUDA was not checked because PyTorch is unavailable. This avoids misreporting a missing CUDA toolkit when the PyTorch import itself already failed.

## Task 39 Commands Run

The following commands were executed on this host (Windows 11, no heavy dependencies installed) and produced the documented exit codes:

```powershell
# All tests pass; verifies contract behavior, status enum, exit codes, and PMDM/CUDA rules
pytest tests/v2/test_smoke_check.py -q

# Exit 0 - lightweight profile passes, heavy deps all not_checked
python scripts/v2_smoke_check.py --profile lightweight

# Exit 2 - heavy profile structured unavailable (PyTorch, RDKit, PMDM, PocketFlow missing; docking not on PATH)
python scripts/v2_smoke_check.py --profile heavy

# Exit 3 - invalid profile rejected with structured JSON
python scripts/v2_smoke_check.py --profile cpu
```

No installs, downloads, environment solves, or adapter code were executed. The smoke check is a stdlib-only probe script.

## Verification Commands

Planned commands, finalized in Task 37:

```bash
mamba env create -f environment.yml
conda activate covalent-design-v2
python scripts/v2_smoke_check.py --profile lightweight
python scripts/v2_smoke_check.py --profile heavy
```

## Environment Layers

Tasks 37 and 38 operate on four distinct layers that must not be confused:

| Layer | Artifact | Owning task | Editable in Task 38? | Description |
| --- | --- | --- | --- | --- |
| Environment scaffold | `environment.yml` | 37 | yes | Human-authored dependency declarations. Channels, package names, and version constraints. Heavy dependencies are commented and `UNVERIFIED`. |
| Source verification table | `docs/v2/dependency-source-verification.md` | 38 | yes (Task 38 records source evidence in the table rows; it does not change the table structure or column definitions) | Structured evidence that each dependency claim is backed by an official source. |
| Lock output | `environment.lock.yml` or conda-lock output | future/manual | no (Task 38 documents the workflow only; it does not produce real lock files) | Pinned exact-version artifact produced by `conda env export --no-builds` or conda-lock. |
| Installed environment | conda/mamba env on disk | future/manual | no (Task 38 must not run install or solve) | Reproducibly created from lock output via `mamba env create -f environment.lock.yml`. |

Documented install path:

```
environment.yml (scaffold)
    -> source verification (Task 38, manual)
    -> lock output (future/manual, after all versions are verified)
    -> installed environment (future/manual, from lock file)
```

## Task 38 No-Install / No-Solve Boundary

Task 38 is a documentation and governance task. It must not:

- Run `conda install`, `mamba install`, `pip install`, `conda env create`, `mamba env create`, or `conda env update`.
- Run `conda env export`, `conda-lock`, or any lock-file generator against a real environment.
- Download, unpack, or resolve any dependency archive.
- Execute code that imports PyTorch, RDKit, CUDA, PMDM, or other heavy dependencies.
- Change dependency versions in `environment.yml` based on unverified claims.

Task 38 may:

- Read and cross-reference official documentation URLs (PyTorch install matrix, CUDA docs, RDKit docs, Conda docs, PMDM repository files, PocketFlow repository files, PyG docs).
- Record official source URLs and version scope in `docs/v2/dependency-source-verification.md`.
- Mark rows as `verified` when an official source confirms the claim for the stated version scope.
- Mark rows as `blocked` when source review or license status blocks use.
- Document the lock-file generation workflow as a future/manual procedure.
- Add or update scaffold comments in `environment.yml`.

## Lock-File Generation Workflow (Future / Manual Only)

Lock-file generation is documented here as a planned manual procedure. It is not executed in Task 38.

Planned workflow, after all dependency versions are source-verified and uncommented in `environment.yml`:

```bash
# 1. Create conda environment from scaffold (future task, not Task 38)
mamba env create -f environment.yml
conda activate covalent-design-v2

# 2. Verify heavy imports (future task, not Task 38)
python scripts/v2_smoke_check.py --profile heavy

# 3. Export locked environment (future task, not Task 38)
conda env export --no-builds --file environment.lock.yml

# 4. Optional: use conda-lock for multi-platform reproducibility
conda-lock lock --file environment.yml --platform linux-64 --kind explicit
```

The lock output becomes the authoritative source for `mamba env create -f environment.lock.yml` in subsequent fresh installs. The lock file must be regenerated whenever a dependency version changes in the source-verified table and the corresponding change is committed to `environment.yml`.

## Project Packaging (Unresolved)

The repository does not currently contain `pyproject.toml`, `setup.py`, or `setup.cfg`. The `environment.yml` scaffold includes a commented `pip install -e .` placeholder that cannot be activated until a later task defines the project package metadata.

Implications:

- `scripts/v2_smoke_check.py` uses `$env:PYTHONPATH='src'` rather than an installed package.
- Editable install mode (`pip install -e .`) remains a future concern.
- No dependency specification can include the project itself as a pip requirement until packaging metadata exists.
- This gap does not block Task 38 because no environment solve or install is performed.
