# Checkpoint V2-C Chemistry / RDKit Heavy Adapter Gate Review

**Date:** 2026-06-19
**Status:** Gate review for Tasks 44-45, authorizing transition to Phase V2-D

## Executive Summary

- **Overall Status:** PASS
- **Task 46 may proceed:** YES — within the V2-D tensor adapter boundary only. This permits starting Task 46 only; it does not implement Task 46 and does not advance to Task 49.
- **Scope covers only Task 44 and Task 45 chemistry adapters:** RDKit normalization (`rdkit_normalize.py`), scaffold derivation (`scaffolds.py`), and molecular descriptor computation (`rdkit_descriptors.py`), together with their test suites and the `chem/__init__.py` public facade.
- **Scope explicitly does not cover:** Task 46+ implementation, Task 47 (PMDM adapter), Task 48 (non-PMDM baseline), Task 49 (training dataset eligibility), or any Phase V2-E/V2-F/V2-G/H work. Checkpoint V2-C is a gate between chemistry adapters (Phase V2-C) and tensor/model foundation (Phase V2-D).
- **Highest risk areas:** no full-stack lock file exists for the heavy environment; exact RDKit/PyTorch/CUDA solver compatibility remains unconfirmed; PMDM is still blocked by unknown upstream license; RDKit was installed via Tsinghua conda-forge mirror after two upstream conda-forge failures (mirror provenance is recorded but not independently verified).
- **Required next action:** start Task 46 within its PyTorch tensor adapter boundary. Do not install, import, or execute PMDM, PocketFlow, docking engines, or training loops. Do not bypass the V2-A/V2-B gate preconditions.

Checkpoint V2-C confirms that the Task 44 and Task 45 chemistry adapter implementations satisfy all V2-beta contracts: lightweight-safe imports, structured unavailable status when RDKit is absent, deterministic project-owned serializable output, no raw RDKit objects crossing the module seam, drug-likeness diagnostic-only semantics, and Bemis-Murcko scaffold source verification. Both lightweight (default CI) and heavy (opt-in `conda run -n covalent-design-v2`) test profiles pass.

## Scope And Boundary

### In-Scope (This Checkpoint)

| Item | Status |
| --- | --- |
| Task 44: RDKit normalization adapter (`rdkit_normalize.py`) | Implemented and verified |
| Task 45: RDKit scaffold adapter (`scaffolds.py`) | Implemented and verified |
| Task 45: RDKit descriptor adapter (`rdkit_descriptors.py`) | Implemented and verified |
| Chemistry facade (`chem/__init__.py`) | Implemented — re-exports all three adapter public APIs |
| Lightweight test profile | Verified — all lightweight tests pass; RDKit-backed tests correctly skip |
| Heavy test profile | Verified — all heavy tests pass under `conda run -n covalent-design-v2` with RDKit 2026.03.1 |
| Boundary enforcement (no hard RDKit import, no raw RDKit objects, diagnostic-only drug-likeness, no docking, no PyTorch) | Verified by code review and dedicated test assertions (see Boundary Review section) |
| Package seam contract (project-owned serializable output, deterministic serialization) | Verified by code review and dedicated test assertions (see Package Seam Review section) |

### Out-of-Scope (Explicitly Excluded)

| Item | Reason |
| --- | --- |
| Task 46 (PyTorch tensor adapter) | Phase V2-D — requires this checkpoint to pass first |
| Task 47 (PMDM real adapter) | Phase V2-D — blocked by PMDM license; not part of V2-C gate |
| Task 48 (non-PMDM baseline) | Phase V2-D — not part of V2-C gate |
| Task 49 (V2 training dataset eligibility) | Phase V2-E — requires V2-D gate first |
| Tasks 50-59 (training, sampling, evaluation, release) | Future phases — out of scope |
| Real data root access (`D:\codex_work\data`) | V2-B concern — not read during this checkpoint |
| Docking engine | Future Task 56 — explicitly excluded per implementation plan |
| PyTorch, CUDA, PMDM, PocketFlow | Heavy dependencies for later phases — not imported or referenced in V2-C adapters |
| Full-stack lock file generation | Dependency lock is a V2-A/V2-D concern — not required for chemistry adapters |

## Evidence Table

### Lightweight Verification (Default CI — No RDKit Required)

| Command | Result | Notes |
| --- | --- | --- |
| `python -m pytest tests/chem/test_rdkit_normalize.py -q` | 6 passed, 6 skipped | Lightweight: input validation, unavailable path, serialization, and no-raw-RDKit-object tests pass; 6 RDKit-backed heavy tests correctly skip |
| `python -m pytest tests/chem/test_rdkit_descriptors.py tests/chem/test_scaffolds.py -q` | 12 passed, 17 skipped | Lightweight: 6 descriptor + 6 scaffold tests pass (input validation, unavailable path, serialization, no-raw-RDKit-object); 9 descriptor + 8 scaffold RDKit-backed heavy tests correctly skip |
| `python -m pytest tests/v2/test_smoke_check.py -q` | 11 passed | Smoke-probe contract tests — no regression from Checkpoint V2-A |
| `python scripts/v2_smoke_check.py --profile lightweight` | exit 0, `overall_status=pass` | Project import passes; all heavy dependency statuses `not_checked` |
| `python -m compileall -q scripts src` | pass | No syntax or bytecode-compile errors in scripts or source packages |

### Heavy Verification (Opt-In `covalent-design-v2` Conda Environment)

| Command | Result | Notes |
| --- | --- | --- |
| `conda run -n covalent-design-v2 python -c "import rdkit; print(rdkit.__version__)"` | `2026.03.1` | RDKit installed in `covalent-design-v2` environment; Python 3.10.20 |
| `conda run -n covalent-design-v2 python -m pytest tests/chem/test_rdkit_normalize.py -q` | 12 passed | All normalizer tests pass: lightweight + RDKit-backed (SMILES parse, molblock parse, sanitize, valence, charge, and heavy no-raw-RDKit-object assertions) |
| `conda run -n covalent-design-v2 python -m pytest tests/chem/test_rdkit_descriptors.py tests/chem/test_scaffolds.py -q` | 29 passed | All descriptor + scaffold tests pass: lightweight + RDKit-backed (15 descriptor: CalcMolDescriptors, Lipinski Ro5, QED diagnostic-only, manual fallback; 14 scaffold: Bemis-Murcko derivation, acyclic fallback, molblock, sanitize failure, heavy no-raw-RDKit-object) |

### Full Suite Verification

| Command | Result | Notes |
| --- | --- | --- |
| `python -m pytest -q` | 1950 passed, 23 skipped, 326 subtests passed | Full lightweight pytest suite — all V2-A, V2-B, and V2-C tests pass; 23 skips are chemistry RDKit-backed tests in lightweight profile (expected and correct) |
| `python -m unittest discover -s tests -t . -q` | 1761 tests, OK | Legacy unittest suite — no regressions |

### Boundary Audit Evidence

| Check | Result | Evidence |
| --- | --- | --- |
| No hard RDKit import at module level | PASS | All three adapter modules (`rdkit_normalize.py`, `rdkit_descriptors.py`, `scaffolds.py`) use `importlib.import_module("rdkit.Chem")` inside public functions only, guarded by try/except ImportError |
| Lightweight module import does not trigger RDKit | PASS | `test_module_import_does_not_require_rdkit()` / `test_module_import_does_not_require_rdkit_objects()` pass in all three test files |
| Structured unavailable output when RDKit absent | PASS | All three adapters return `status="unavailable"`, `rdkit_available=False`, error_code with `_RDKIT_UNAVAILABLE` suffix, and dependency-category diagnostics when `_load_rdkit_chem()` returns None |
| No raw RDKit objects cross module boundary | PASS | `test_public_output_does_not_expose_raw_rdkit_objects()` passes (all three adapters); `test_heavy_output_no_raw_rdkit_objects()` / `test_heavy_scaffold_output_no_raw_rdkit_objects()` passes (heavy profile); all return types (`MoleculeNormalizationResult`, `DescriptorResult`, `ScaffoldResult`) are frozen dataclasses with Python built-in types only |
| Drug-likeness is diagnostic-only | PASS | `test_heavy_druglikeness_is_diagnostic_only()` and `test_heavy_druglikeness_in_serializable_output()` pass; Lipinski Ro5 violations and QED values appear in `diagnostics` tuple under `"category": "druglikeness"` — they do not gate `status` (status remains `"ok"` even for molecules that fail Lipinski/QED thresholds) |
| No docking code in chemistry adapters | PASS | `grep -i dock` across `src/covalent_design/chem/` returns zero matches |
| No PyTorch import or reference | PASS | `grep -i torch` across `src/covalent_design/chem/` returns zero matches |
| No real-data-root access | PASS | Chemistry adapters accept molecule text (SMILES/molblock strings) as input; they do not reference `D:\codex_work\data`, file paths, manifests, staging, or conversion artifacts |
| Bemis-Murcko scaffold source verified | PASS | `_derive_murcko_scaffold()` imports `rdkit.Chem.Scaffolds.MurckoScaffold` and calls `GetScaffoldForMol()` — the canonical RDKit API for Bemis-Murcko scaffold derivation |
| Descriptor computation primary path | PASS | `_compute_raw_descriptors()` uses `rdkit.Chem.Descriptors.CalcMolDescriptors()` as primary path with `_compute_core_descriptors_manually()` as defensive fallback |
| `chem/__init__.py` does not hard-import RDKit | PASS | `__init__.py` imports names from the three adapter modules, which themselves use lazy RDKit loading; no `import rdkit` appears in `__init__.py` |
| No PyTorch, PMDM, PocketFlow, or CUDA import | PASS | `grep` across `src/covalent_design/chem/` finds zero references to PyTorch, PMDM, PocketFlow, CUDA, or docking |

### Package Seam Review

| Check | Result | Evidence |
| --- | --- | --- |
| All public return types are project-owned | PASS | `MoleculeNormalizationResult`, `DescriptorResult`, `ScaffoldResult` — all frozen dataclasses defined within the project package |
| Deterministic output | PASS | `test_result_output_is_serializable_and_deterministic()` passes for all three adapters; `result_to_dict()`, `descriptor_result_to_dict()`, and `scaffold_result_to_dict()` produce sorted-key deterministic dictionaries with JSON round-trip |
| No raw RDKit Mol, Atom, Bond in output | PASS | All adapter functions convert RDKit objects to Python primitives (str for SMILES, int for counts, float for descriptors) before returning; dedicated no-raw-RDKit-object tests verify deep inspection |
| Error codes are structured | PASS | Each adapter defines distinct error codes: `RDKIT_NORMALIZE_*`, `DESCRIPTOR_*`, `SCAFFOLD_*` — covering empty input, unsupported format, RDKit unavailable, parse failure, sanitize failure, and scaffold derivation failure |
| Descriptor key map is public-facing | PASS | RDKit-internal names (e.g., `MolWt`, `MolLogP`) are mapped to public-facing names (e.g., `molecular_weight`, `logp`) via `_DESCRIPTOR_KEY_MAP` |
| Non-primitive RDKit return values are coerced | PASS | `float(value)` coercion handles RDKit descriptors that return numpy scalars or other non-primitive types |
| Acyclic fallback scaffold type | PASS | When `GetScaffoldForMol` returns an empty scaffold (acyclic molecule), the adapter returns `scaffold_type="acyclic_fallback"` with the canonical molecule SMILES — no None or empty scaffold leaks |

## Architecture Compliance

### ADR 0037 Compliance

| Requirement | Status |
| --- | --- |
| Lightweight profile must not hard-import RDKit | PASS — lazy `importlib.import_module` with ImportError guard |
| Heavy dependencies are opt-in/manual | PASS — RDKit path requires explicit `conda run -n covalent-design-v2` invocation |
| Default CI must remain lightweight | PASS — RDKit-backed tests skip (6+17=23 skipped) in default environment |
| Heavy unavailable must be structured, not a traceback | PASS — all three adapters return structured `status="unavailable"` with diagnostics and error_code |

### V2 Risk Register Compliance

| Risk ID | Risk | Mitigation Status |
| --- | --- | --- |
| V2-R12 | PyTorch/RDKit objects leak into public contracts | MITIGATED — Task 44/45 chemistry adapters verified as passing no-raw-RDKit-object tests; all output is project-owned serializable data |
| V2-R17 | V2 overlay docs drift from canonical ADR/spec authority | MITIGATED — adapter implementations align with ADR 0037 boundary, `docs/v2/04-v2-dependency-and-environment-spec.md`, and `docs/v2/09-v2-interface-and-contract-changes.md` |

## Findings By Severity

### P0 Blocking

**None.** No blocking issues prevent Task 46 from starting within its PyTorch tensor adapter boundary.

### P1 Important

1. **Title:** No full-stack lock file exists for the heavy environment.
   **Evidence:** `environment.lock.yml` has not been generated. RDKit 2026.03.1 was solved and installed in `covalent-design-v2`, but PyTorch, CUDA, and PMDM graph dependencies remain unresolved in that environment. The dependency source verification table still lists 12 rows as `unverified`.
   **Impact:** Task 46 and later heavy tasks may encounter solver conflicts when adding PyTorch/CUDA/PMDM dependencies to the same environment. Task 46 must be prepared to operate in a PyTorch-only or separate environment if necessary.
   **Why not P0:** The chemistry adapters (Tasks 44-45) are complete and verified in the `covalent-design-v2` environment with RDKit 2026.03.1. The lock file gap is a forward risk for Task 46+, not a chemistry gate blocker.
   **Recommended fix:** Execute the documented lock workflow when Task 38 dependencies are resolved, or narrow Task 46 to PyTorch-only smoke before attempting full-stack solve.
   **Related risks:** V2-R1 (PyTorch/CUDA/RDKit/PMDM versions may not solve together).

2. **Title:** RDKit was installed via Tsinghua conda-forge mirror after two HTTP 000 failures from upstream conda-forge.
   **Evidence:** The Task 44 verification notes in `docs/v2/11-v2-verification-matrix.md` record: "official conda-forge env creation failed twice with HTTP 000; after user-approved Tsinghua conda-forge mirror, new `covalent-design-v2` env was created at `D:\anaconda\envs\covalent-design-v2` without using `my_rdkit`."
   **Impact:** The mirror provenance is not independently verified. The installed RDKit 2026.03.1 package integrity has not been compared against an official conda-forge checksum. For scientific work, this should be resolved before publication claims.
   **Why not P0:** All 41 chemistry heavy tests pass against the installed RDKit, functional behavior matches the documented API, and the environment is self-consistent. The mirror is a known community mirror (Tsinghua TUNA), not an arbitrary source. The risk is procedural provenance, not functional correctness.
   **Recommended fix:** When upstream conda-forge connectivity is restored, re-solve from official channels and record checksums. Keep the mirror-provenance note in the risk register until verified.
   **Related risks:** V2-R1, dependency source verification table RDKit row.

3. **Title:** PMDM remains blocked by unknown upstream license.
   **Evidence:** `docs/v2/dependency-source-verification.md` records PMDM as `blocked` with `license status: unknown`. This status has not changed since Checkpoint V2-A.
   **Impact:** PMDM adapter work (Task 47) remains unavailable. Task 46 does not require PMDM and can proceed independently, but Task 48 (non-PMDM baseline) may need scheduling changes if PMDM remains blocked.
   **Why not P1 for V2-C:** This is a V2-D/Task 47 concern. V2-C chemistry adapters do not reference PMDM in any way. The risk is recorded here for visibility but does not gate Task 46.
   **Recommended fix:** Resolve PMDM license status before Task 47, or proceed with Task 48 (non-PMDM baseline) as the primary training path if PMDM remains blocked.
   **Related risks:** V2-R2, V2-R3.

### P2 Moderate

1. **Title:** Exact RDKit version pin is not locked.
   **Evidence:** The `environment.yml` scaffold does not pin an exact RDKit version. The installed RDKit 2026.03.1 was resolved ad-hoc during environment creation. Source verification table still shows RDKit as `unverified`.
   **Impact:** Future environment recreation may produce a different RDKit version. The Bemis-Murcko scaffold API and CalcMolDescriptors API are stable across RDKit versions, so the functional risk is low.
   **Recommended fix:** Pin exact RDKit version when the lock file is generated.

2. **Title:** Conda environment creation required a user-approved workaround (mirror channel).
   **Evidence:** Standard `conda env create` against conda-forge failed with HTTP 000 on two attempts. The Tsinghua mirror was used as a workaround. The `environment.yml` does not record the mirror channel.
   **Impact:** Reproducibility of the exact environment creation path is not fully documented. A different network or time may produce different results.
   **Recommended fix:** Document the mirror channel as an allowed alternative in `environment.yml` comments or in `docs/v2/04-v2-dependency-and-environment-spec.md`.

### P3 Minor

1. **Title:** Drug-likeness diagnostic format uses `"druglikeness"` category string (compound word) rather than spaced or hyphenated form.
   **Evidence:** `src/covalent_design/chem/rdkit_descriptors.py` line 279 and test assertions use `"druglikeness"`.
   **Impact:** Cosmetic — consumers of diagnostics may need to handle this exact string. The category is documented and tested.
   **Recommended fix:** Keep as-is for consistency with existing test assertions; document the diagnostic category vocabulary if it expands.

## Remaining Risks

| Risk | Severity | Owner | Mitigation |
| --- | --- | --- | --- |
| No full-stack lock file | P1 | Task 38 (future lock task) | Narrow Task 46 to PyTorch-only smoke; do not require PMDM graph dependencies |
| Mirror-provenance for RDKit install | P1 | Task 44 closure | Re-verify from official channels when available |
| PMDM license blocked | P1 | Task 47 gate | Proceed with non-PMDM baseline (Task 48) if PMDM remains blocked |
| Exact RDKit version unpinned | P2 | Lock task | Pin during lock generation |
| Conda mirror channel undocumented | P2 | Task 44 closure | Add to environment docs or `environment.yml` comments |
| Forward risk: PyTorch/RDKit version conflict | P1 | Task 46 | V2-R1; chemistry adapters are verified in current environment, but adding PyTorch may require a separate or extended solve |

## Test Coverage Summary

| Module | Lightweight tests | Heavy tests | Total | Coverage |
| --- | ---: | ---: | --- | --- |
| `rdkit_normalize.py` | 6 passed | 6 passed | 12 | Input validation, unavailable path, SMILES/molblock parse, sanitize, valence, charge, empty input, unsupported format, serialization, determinism, no-raw-RDKit-objects |
| `rdkit_descriptors.py` | 6 passed | 9 passed | 15 | Input validation, unavailable path, CalcMolDescriptors, Lipinski Ro5, QED, manual fallback, sanitize failure, empty input, unsupported format, serialization, determinism, no-raw-RDKit-objects, drug-likeness diagnostic-only |
| `scaffolds.py` | 6 passed | 8 passed | 14 | Input validation, unavailable path, Bemis-Murcko scaffold, acyclic fallback, molblock input, sanitize failure, empty input, unsupported format, serialization, determinism, no-raw-RDKit-objects |

**Total chemistry test assertions across three modules: 41 (12+15+14) in heavy profile, 18 (6+6+6) in lightweight profile.**

## Verification Commands Executed

```powershell
# Lightweight profile
$env:PYTHONPATH='src'
python -m pytest tests/chem/test_rdkit_normalize.py -q
python -m pytest tests/chem/test_rdkit_descriptors.py tests/chem/test_scaffolds.py -q
python -m pytest tests/v2/test_smoke_check.py -q
python scripts/v2_smoke_check.py --profile lightweight
python -m compileall -q scripts src

# Heavy profile
conda run -n covalent-design-v2 python -c "import rdkit; print(rdkit.__version__)"
conda run -n covalent-design-v2 python -m pytest tests/chem/test_rdkit_normalize.py -q
conda run -n covalent-design-v2 python -m pytest tests/chem/test_rdkit_descriptors.py tests/chem/test_scaffolds.py -q

# Full suite
python -m pytest -q
python -m unittest discover -s tests -t . -q
```

All commands exited successfully with the test counts and pass/fail/skip distributions recorded in the Evidence Table above.

## Verification Against V2-C Checkpoint Criteria

Per `docs/v2/11-v2-verification-matrix.md` checkpoint row for V2-C:

| Criterion | Status | Evidence |
| --- | --- | --- |
| RDKit adapter reports (normalization, scaffold/descriptor, drug-likeness) | PASS | Three adapter modules implemented and tested; all lightweight and heavy tests pass |
| No default-CI RDKit import | PASS | Lazy import via `importlib.import_module`; module-level import tests pass without RDKit |
| Drug-likeness diagnostic-only | PASS | Dedicated test assertions; Lipinski Ro5/QED in diagnostics tuple; status remains `"ok"` regardless of violations |
| No raw RDKit objects cross seam | PASS | Dedicated no-raw-RDKit-object tests (both lightweight and heavy); all return types are frozen dataclasses of Python built-in types |

## Final Verdict

**READY FOR TASK 46.**

Checkpoint V2-C confirms that the Task 44 and Task 45 chemistry adapter implementations satisfy all V2-beta contracts for the chemistry/RDKit heavy adapter gate. Both lightweight and heavy test profiles pass, boundary enforcement is proven by dedicated test assertions, and the package seam contract (project-owned serializable data, deterministic output, no raw RDKit objects) is fully verified.

**This verdict permits starting Task 46 only.** It does not implement Task 46 and does not advance to Task 49. Specifically:

- **Allowed in Task 46:** PyTorch tensor adapter design and implementation (`src/covalent_design/model/torch_backend.py`), lightweight tests that do not hard-import PyTorch, heavy tests under `conda run -n covalent-design-v2`, and serializable contract design for tensor-backed outputs.
- **Not allowed in Task 46:** importing, loading, or executing PMDM modules; installing PyTorch/CUDA/PMDM graph dependencies into default CI; accessing `D:\codex_work\data`; performing training, sampling, inference, or evaluation; bypassing the V2-A/V2-B gate preconditions; advancing to Task 47, 48, or 49 without passing Checkpoint V2-D.
- **PMDM remains blocked** for all execution paths until upstream license is resolved, per `docs/v2/dependency-source-verification.md` and ADR 0037 boundary.
- **The no-full-stack-lock-file and mirror-provenance risks** are recorded as P1 Important issues for Task 46+ awareness but do not block the chemistry gate.

Task 46 must respect the project sequence: Task 45 → Checkpoint V2-C → Phase V2-D (Tasks 46-48) → Checkpoint V2-D → Phase V2-E (Tasks 49-52), as recorded in `docs/v2/12-v2-risk-register.md`.
