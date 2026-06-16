# V2 Dependency Source Verification

Date: 2026-06-16
Status: template for Task 38

This table is the required evidence shape for Task 38. Rows are not implementation approval until their status is `verified` and the linked source is an official project source such as official documentation, official API reference, official source code, or official release notes.

| Dependency / package | Claimed API or capability | Official source URL | Version scope | License status | Verification date | Status | Owning task |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Python | v2 runtime version support | TBD official Python docs | TBD | TBD | TBD | unverified | 37 |
| Conda/Mamba | environment solve and lock workflow | TBD official Conda/Mamba docs | TBD | TBD | TBD | unverified | 38 |
| PyTorch | tensor backend, CPU/GPU smoke, CUDA compatibility | TBD official PyTorch docs | TBD | TBD | TBD | unverified | 46, 50 |
| CUDA | single-GPU runtime capability | TBD official NVIDIA/CUDA docs | TBD | TBD | TBD | unverified | 39, 50 |
| RDKit | molecule normalization, scaffold/descriptor diagnostics | TBD official RDKit docs/source | TBD | TBD | TBD | unverified | 44, 45 |
| PMDM | real backbone adapter smoke | TBD official/upstream PMDM repository docs/source | TBD | TBD | TBD | unverified | 47 |
| PocketFlow | optional reference/supervision ideas if used | TBD official/upstream PocketFlow repository docs/source | TBD | TBD | TBD | not required yet | 47 |
| Docking engine | optional feasibility probe only | TBD official engine docs/source | TBD | TBD | TBD | not required yet | 56 |

Allowed `status` values:

- `verified`: official source supports the claimed API/capability for the stated version scope.
- `unverified`: source review has not been completed; code must not depend on this claim.
- `blocked`: source review or license status blocks use.
- `not required yet`: optional future backend or capability not needed for the current implementation task.

Unverified rows must remain behind adapter boundaries or future-task notes and must not be documented as implemented contracts.
