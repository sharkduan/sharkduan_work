# V2 Dependency Source Verification

Date: 2026-06-16
Status: source review evidence for Task 38

This document records the official-source evidence for every dependency listed or planned in the V2 environment scaffold (`environment.yml`). Rows are not implementation approval until their status is `verified` and the linked source is an official project source (official documentation, official API reference, official source code, or official release notes).

## Verification Table

| dependency / package | claimed API or capability | official source URL | version scope | license status | verification date | status | owning task |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Python | v2 runtime version support (3.10 placeholder) | https://docs.python.org/3/ ; https://devguide.python.org/versions/ | 3.10 (placeholder; exact minor/patch unverified; Python devguide records Python 3.10 in security support until 2026-10) | PSF License (permissive, BSD-like) | 2026-06-16 | unverified | 37, 39 |
| Conda/Mamba | environment solve and lock workflow | https://docs.conda.io/projects/conda/en/latest/ ; https://mamba.readthedocs.io/en/latest/ | conda >=23.x / mamba >=1.x (unverified exact version) | BSD-3-Clause (conda); BSD-3-Clause (mamba) | 2026-06-16 | unverified | 38 |
| pip | package install tooling for editable install mode | https://pip.pypa.io/en/stable/ | >=23.x (unverified exact version) | MIT | 2026-06-16 | unverified | 37, 38 |
| PyTorch | tensor backend, CPU/GPU smoke, CUDA compatibility | https://pytorch.org/get-started/locally/ | 2.x with CUDA 11.8 or 12.x (exact version unverified; PMDM mol.yml pins 2.1.1+cu118) | BSD-3-Clause (PyTorch) | 2026-06-16 | unverified | 46, 50 |
| CUDA | single-GPU runtime capability | https://docs.nvidia.com/cuda/ | 11.8 or 12.x toolkit (exact version unverified; PMDM mol.yml pins cudatoolkit 11.8.0) | NVIDIA EULA (proprietary) | 2026-06-16 | unverified | 39, 50 |
| RDKit | molecule normalization, scaffold/descriptor diagnostics | https://www.rdkit.org/docs/ ; https://github.com/rdkit/rdkit | >=2022.09 (unverified exact version; PMDM mol.yml pins 2022.09.1) | BSD-3-Clause | 2026-06-16 | unverified | 44, 45 |
| PMDM | real backbone adapter smoke | https://github.com/Layne-Huang/PMDM | HEAD of main branch (commit unverified; Zenodo DOI 10.5281/zenodo.10631313 for pretrained weights) | **unknown** -- no LICENSE file found in upstream repository at `https://github.com/Layne-Huang/PMDM` | 2026-06-16 | blocked | 47 |
| pytorch-scatter | PMDM graph dependency (scatter operations) | https://github.com/rusty1s/pytorch_scatter | >=2.1.2+pt21cu118 (unverified; PMDM mol.yml pip pin) | MIT | 2026-06-16 | unverified | 47 |
| pytorch-sparse | PMDM graph dependency (sparse operations) | https://github.com/rusty1s/pytorch_sparse | >=0.6.18+pt21cu118 (unverified; PMDM mol.yml pip pin) | MIT | 2026-06-16 | unverified | 47 |
| pytorch-cluster | PMDM graph dependency (cluster operations) | https://github.com/rusty1s/pytorch_cluster | >=1.6.3+pt21cu118 (unverified; PMDM mol.yml pip pin) | MIT | 2026-06-16 | unverified | 47 |
| pytorch-geometric | PMDM graph dependency (PyG GNN framework) | https://pytorch-geometric.readthedocs.io/ ; https://github.com/pyg-team/pytorch_geometric | >=2.4.0 (unverified; PMDM mol.yml pip pin) | MIT | 2026-06-16 | unverified | 47 |
| pytorch-spline-conv | PMDM graph dependency (spline convolution) | https://github.com/rusty1s/pytorch_spline_conv | >=1.2.2+pt21cu118 (unverified; PMDM mol.yml pip pin) | MIT | 2026-06-16 | unverified | 47 |
| PocketFlow | optional reference/supervision ideas only | https://github.com/Saoge123/PocketFlow | HEAD of master branch (commit unverified) | MIT (file `Liscense` in repo root, copyright NicholasYe 2021) | 2026-06-16 | not required yet | 47 |
| Project package install mode | editable install (`pip install -e .`) | https://pip.pypa.io/en/stable/topics/local-project-installs/ | pip >=23.x (no pyproject.toml/setup.py exists yet) | MIT (pip) | 2026-06-16 | unverified | 37, 38 |
| Docking engine | optional feasibility probe only; no engine selected | not selected -- no official source to verify | not applicable | not applicable | 2026-06-16 | not required yet | 56 |

## Status Definitions

| Status | Meaning |
| --- | --- |
| `verified` | Official source supports the claimed API/capability for the stated version scope. |
| `unverified` | Source review has not been completed; code must not depend on this claim. |
| `blocked` | Source review or license status blocks use. Dependency must not enter any training or execution path. |
| `not required yet` | Optional future backend or capability not needed for the current implementation task. |

Unverified rows must remain behind adapter boundaries or future-task notes and must not be documented as implemented contracts.

## Lock Workflow

The active `conda-forge` and `defaults` channels in `environment.yml` are treated as Conda infrastructure channels, not package rows. They remain subject to the Conda/Mamba solver and lock workflow recorded here.

### Intended lock strategy

The V2 environment uses Conda/Mamba for the solve step. The lock workflow is documented here as a specification; actual lock output is produced only after exact versions and solver compatibility are confirmed (future task after source verification).

1. **Solve**: `mamba env create -f environment.yml` (or `conda env create -f environment.yml`).
2. **Export**: After successful solve, export the resolved environment:
   ```bash
   conda env export -n covalent-design-v2 --no-builds > environment.lock.yml
   ```
   or use `conda-lock` for multi-platform reproducible locks:
   ```bash
   conda-lock lock -f environment.yml -p linux-64
   ```
3. **Record**: Commit the lock file alongside `environment.yml` with a dated provenance note.
4. **Verify**: Run `scripts/v2_smoke_check.py --profile lightweight` and `--profile heavy` against the locked environment before declaring the lock valid.

### Current lock status

No lock file has been generated. Exact version compatibility between Python 3.10, PyTorch 2.x, CUDA toolkit, RDKit, and the PMDM graph dependency stack has not been confirmed through a Conda/Mamba solver run. All version scopes remain `unverified` until a successful solve produces a lock file with pinned exact versions.

### Lock preconditions

- All dependency rows in the verification table must be `verified` or `not required yet` before a lock file is considered authoritative.
- No `blocked` dependency may appear in the lock file.
- `unverified` dependencies may appear in a draft lock for solver testing only; such a lock must carry an `UNVERIFIED` header and must not be used as a training environment authority.

## License Blocking Rules

### General rule

A dependency whose license is unknown or that lacks a discoverable license file in its official upstream repository is **blocked** from entering any training, inference, or execution path. This applies to both direct imports and transitive dependencies that are required for V2 functionality.

### PMDM license -- explicit blocked status

The PMDM upstream repository at `https://github.com/Layne-Huang/PMDM` does not contain a LICENSE file. The README references a Zenodo deposit (DOI 10.5281/zenodo.10631313) but does not declare a license. The paper is published in Nature Communications under Springer Nature terms, but the code repository itself lacks an explicit open-source license.

**Ruling**: PMDM is **blocked** for all V2 execution paths until a license file is added to the upstream repository or the authors provide an explicit written license grant. The PMDM adapter code may exist in the repository as a planned integration point, but it must not import, load, or execute any PMDM module. Smoke probes must report PMDM status as `blocked` with reason `license_unknown`.

### PocketFlow -- not required, not promoted

PocketFlow (`https://github.com/Saoge123/PocketFlow`) carries an MIT license (file `Liscense` in repo root, copyright NicholasYe 2021). However, PocketFlow is an **optional reference** for supervision ideas only and must not be promoted to a required dependency. Its status of `not required yet` reflects the project decision that PMDM remains the generation backbone and PocketFlow is not a v2-beta gate.

### License categories and V2 eligibility

| License category | V2 eligibility | Examples |
| --- | --- | --- |
| Permissive (MIT, BSD, Apache 2.0, PSF) | eligible after source verification | Python, pip, PyTorch, RDKit, PyG packages, PocketFlow (if ever promoted) |
| Proprietary with free runtime (NVIDIA EULA) | eligible for GPU path after source verification; must not be a default-CI dependency | CUDA toolkit, cuDNN |
| Unknown / missing | **blocked** -- cannot enter any path | PMDM (current state) |
| Copyleft / GPL | review required; may be blocked depending on linkage and distribution scope | not currently encountered in V2 dependency tree |
| Conditional / non-commercial | review required; must not block academic research use without explicit check | to be assessed if encountered |

### License gate before training

The license audit is a pre-training gate (V2-R3, V2-R6). Before any heavy-profile training or real PMDM adapter smoke:

1. Every dependency in the active environment must have a known license status.
2. Any `blocked` or `unknown` license must be resolved or the dependency path must remain inactive.
3. The training run manifest must record the license status of every imported dependency.

## PMDM Graph Dependency Stack

PMDM's published environment (`mol.yml` in the upstream repository) requires the following PyTorch Geometric packages installed via pip with CUDA 11.8 suffixes. These are listed in the verification table above as separate rows because each has its own upstream repository and version compatibility matrix.

The exact version pins from the PMDM `mol.yml` (pip section) are recorded here for reference but are **not verified** for compatibility with the V2 target Python 3.10 and a potentially different PyTorch/CUDA combination:

```
torch-scatter==2.1.2+pt21cu118
torch-sparse==0.6.18+pt21cu118
torch-cluster==1.6.3+pt21cu118
torch-geometric==2.4.0
torch-spline-conv==1.2.2+pt21cu118
```

V2 targets Python 3.10 (PMDM uses Python 3.9). The PyTorch and CUDA versions for V2 have not been locked. Until exact version compatibility is confirmed through a solver run, all PMDM graph dependencies remain `unverified`.

## Docking Engine

No docking engine has been selected. QuickVina 2 is referenced by PMDM's evaluation scripts (`evaluation/docking_2.py`, `evaluation/docking_2_single.py`) but is not a V2 dependency. Docking is an optional feasibility probe only (V2-R15). Its status is `not required yet` and must not become a beta blocker without a future explicit decision record.

## Verification Evidence Summary

| Evidence item | Source | Date checked |
| --- | --- | --- |
| Python PSF license | https://docs.python.org/3/license.html | 2026-06-16 |
| Conda BSD-3-Clause | https://github.com/conda/conda/blob/main/LICENSE.txt | 2026-06-16 |
| Mamba BSD-3-Clause | https://github.com/mamba-org/mamba/blob/main/LICENSE | 2026-06-16 |
| PyTorch BSD-3-Clause | https://github.com/pytorch/pytorch/blob/main/LICENSE | 2026-06-16 |
| CUDA EULA | https://docs.nvidia.com/cuda/eula.html | 2026-06-16 |
| RDKit BSD-3-Clause | https://github.com/rdkit/rdkit/blob/master/license.txt | 2026-06-16 |
| PMDM no license | checked `https://github.com/Layne-Huang/PMDM` -- no LICENSE file; confirmed in local submodule at `PMDM/` | 2026-06-16 |
| PyG/pytorch-geometric MIT | https://github.com/pyg-team/pytorch_geometric/blob/master/LICENSE | 2026-06-16 |
| pytorch-scatter MIT | https://github.com/rusty1s/pytorch_scatter/blob/master/LICENSE | 2026-06-16 |
| pytorch-sparse MIT | https://github.com/rusty1s/pytorch_sparse/blob/master/LICENSE | 2026-06-16 |
| pytorch-cluster MIT | https://github.com/rusty1s/pytorch_cluster/blob/master/LICENSE | 2026-06-16 |
| pytorch-spline-conv MIT | https://github.com/rusty1s/pytorch_spline_conv/blob/master/LICENSE | 2026-06-16 |
| PocketFlow MIT | local submodule file `PocketFlow/Liscense` (MIT, copyright NicholasYe 2021) | 2026-06-16 |
| pip MIT | https://github.com/pypa/pip/blob/main/LICENSE.txt | 2026-06-16 |

## Open Items

- Exact Python minor/patch version for V2 (currently 3.10 placeholder, not locked).
- PyTorch version and CUDA toolkit version: must be compatible with each other, with the PMDM graph dependency stack, and with the V2 Python version.
- PMDM license resolution: blocked until upstream adds a LICENSE file or authors provide written grant.
- Solver compatibility: Conda/Mamba solve with Python 3.10 + PyTorch 2.x + CUDA + RDKit + PMDM graph stack has not been attempted.
- pyproject.toml or setup.py for project package: does not yet exist; editable install mode cannot be verified.
- Docking engine selection: not in scope for v2-beta.
