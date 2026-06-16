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

## Verification Commands

Planned commands, finalized in Task 37:

```bash
mamba env create -f environment.yml
conda activate covalent-design-v2
python scripts/v2_smoke_check.py --profile lightweight
python scripts/v2_smoke_check.py --profile heavy
```
