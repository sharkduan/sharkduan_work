# Task 38: Dependency Source Verification Review

Date: 2026-06-16

Scope: Task 38 source-verification table audit, lock workflow status, and Task 39 readiness assessment. This is a documentation-only review. No package install, environment solve, lock-file generation, dependency download, or heavy dependency import was performed.

## Task 38 Summary

Task 38 records official-source evidence for the v2 dependency scaffold and documents the future lock workflow. It does not prove that the environment solves, and it does not produce an authoritative lock file.

Current result:

- Official source URLs are recorded for Python, Conda/Mamba, pip, PyTorch, CUDA, RDKit, PMDM, the PMDM PyG/graph stack, PocketFlow, project editable install mode, and docking selection status.
- Exact version compatibility remains `unverified` because no Conda/Mamba solve was run.
- PMDM is `blocked` because the upstream repository and local submodule do not contain a LICENSE file.
- PocketFlow is `not required yet`; its local `PocketFlow/Liscense` file is MIT, but it remains a reference-only dependency.
- The lock workflow is documented, but no lock file was generated.

## Source Verification Table Audit

The table in `docs/v2/dependency-source-verification.md` was inspected.

| Dependency / package | Source evidence status | License status | Table status | Assessment |
| --- | --- | --- | --- | --- |
| Python | official Python docs and devguide URLs recorded | PSF License | unverified | Python 3.10 support window is sourced, but exact minor/patch lock remains unverified. |
| Conda/Mamba | official docs URLs recorded | BSD-3-Clause for conda and mamba | unverified | Environment and solver docs are linked; exact tool versions and solve behavior remain unverified. |
| pip | official pip docs URL recorded | MIT | unverified | Editable local install docs are linked; repo lacks `pyproject.toml`/`setup.py`, so install mode remains unresolved. |
| PyTorch | official PyTorch install URL recorded | BSD-3-Clause | unverified | Required for heavy path; exact PyTorch/CUDA/Python combination is not solver-verified. |
| CUDA | official NVIDIA CUDA docs URL recorded | NVIDIA EULA | unverified | Required for GPU path; toolkit/driver compatibility is not runtime-verified. |
| RDKit | official RDKit docs/source URLs recorded | BSD-3-Clause | unverified | Required for heavy chemistry path; exact version remains unverified. |
| PMDM | upstream repository URL and local `PMDM/mol.yml` evidence recorded | unknown, no LICENSE file found | blocked | PMDM must not be imported or executed until license status is resolved or an explicit waiver narrows later tasks to non-importing probes. |
| PMDM PyG/graph stack | upstream package URLs and PMDM pin evidence recorded | MIT for listed PyG packages | unverified | Exact compatibility with selected PyTorch/CUDA/Python stack remains unverified. |
| PocketFlow | upstream URL and local license evidence recorded | MIT via `PocketFlow/Liscense` | not required yet | Optional reference only; not promoted to required v2 dependency. |
| Project package install mode | official pip local-project docs URL recorded | project-owned / pip MIT | unverified | Editable install is blocked by missing project packaging metadata. |
| Docking engine | no engine selected | not applicable | not required yet | Optional feasibility task only. |

## Lock Workflow Status

The lock workflow is documented in both `docs/v2/dependency-source-verification.md` and `docs/v2/04-v2-dependency-and-environment-spec.md`.

No lock file was generated. No `conda env create`, `mamba env create`, `conda env export`, `conda-lock`, or `pip install` command was run. `environment.yml` remains a scaffold with heavy dependencies commented out and marked `UNVERIFIED`.

## Task 39 Readiness

**Task 39 may NOT start without a waiver or prerequisite resolution.**

Rationale:

1. PMDM is `blocked` because its upstream license is unknown. Any Task 39 behavior that imports or executes PMDM is blocked.
2. PyTorch, CUDA, RDKit, and the PMDM graph stack have official source URLs, but exact version compatibility remains `unverified`.
3. The lock workflow is documented but not executed. A later task must either solve and lock the environment or explicitly scope Task 39 to structured-unavailable probes that do not import blocked dependencies.

Task 39 may start only after one of these is true:

- PMDM license is resolved and the required heavy dependency versions are source- and solver-verified; or
- a new explicit controller-approved waiver narrows Task 39 to non-importing structured-unavailable probe behavior and documents that PMDM remains blocked.

## Commands Run

These commands were used as structured documentation checks:

```powershell
rg -n "dependency / package|official source URL|license status|verification date|owning task" docs/v2/dependency-source-verification.md
rg -n "^\\| (Python|Conda/Mamba|pip|PyTorch|CUDA|RDKit|PMDM|pytorch-scatter|pytorch-sparse|pytorch-cluster|pytorch-geometric|pytorch-spline-conv|PocketFlow|Project package install mode|Docking engine) \\|" docs/v2/dependency-source-verification.md
rg -n "verified|unverified|blocked|not required yet" docs/v2/dependency-source-verification.md
rg -n "lock|Lock|LOCK|environment.lock" docs/v2/dependency-source-verification.md docs/v2/04-v2-dependency-and-environment-spec.md
rg -n "StackOverflow|blog|tutorial|AI summary|ChatGPT|unofficial" docs/v2/dependency-source-verification.md docs/v2/04-v2-dependency-and-environment-spec.md
```

## Remaining Risks

| Risk | Severity | Notes |
| --- | --- | --- |
| PMDM license unknown | P0 for PMDM import/execution | PMDM must remain blocked until license is resolved or a waiver narrows later work to non-import probes. |
| Heavy dependency solve untested | P1 | Official URLs are recorded, but no Conda/Mamba solve or lock file exists. |
| CUDA/PyTorch/RDKit exact versions unverified | P1 | Exact compatible versions must be selected and solver-validated before heavy runtime use. |
| Project editable install unresolved | P2 | Repo lacks package metadata; current verification continues to use `PYTHONPATH=src`. |

## Decision

Task 38 documentation requirements are met for source URL recording, license status recording, and lock workflow design. Task 39 is **blocked by default** because PMDM is blocked and heavy dependency compatibility is unverified. A later controller-approved waiver may allow Task 39 to implement only structured-unavailable, non-importing probe behavior.
