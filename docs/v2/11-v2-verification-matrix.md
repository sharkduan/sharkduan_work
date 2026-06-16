# V2 Verification Matrix

Date: 2026-06-16
Status: hardened planning matrix

| Task | Requirement | Evidence files | Test command | Blocking for | Status | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| 37 | Environment scaffold and smoke script | `environment.yml`, `scripts/v2_smoke_check.py`, `docs/adr/0037-v2-environment-and-heavy-dependency-boundary.md` | `python scripts/v2_smoke_check.py --profile lightweight`; `python -m compileall -q scripts src` | all v2 heavy work | planned | no training; ADR 0037 accepted |
| 38 | Source-verified dependency and lock strategy | `docs/v2/dependency-source-verification.md`, `environment.yml` | `rg -n "dependency / package|official source URL|license status|verification date|owning task" docs/v2/dependency-source-verification.md`; `rg -n "verified|unverified|blocked|not required yet" docs/v2/dependency-source-verification.md` | dependency lock | planned | official sources only |
| 39 | RDKit/PyTorch/CUDA/PMDM smoke probes | `scripts/v2_smoke_check.py`, `tests/v2/test_smoke_check.py` | `pytest tests/v2/test_smoke_check.py -q` | data chemistry, model training | planned | heavy mode manual |
| 40 | V2 source manifest schema | `src/covalent_design/data/v2_manifests.py`, `tests/data/test_v2_manifests.py` | `pytest tests/data/test_v2_manifests.py -q` | source staging | planned | three sources only |
| 41 | Download/manual staging fixtures | `src/covalent_design/data/v2_intake.py`, `tests/data/test_v2_intake.py` | `pytest tests/data/test_v2_intake.py -q` | real data intake | planned | no network in default tests |
| 42 | Conversion into v1 ETL inputs | `src/covalent_design/data/v2_conversion.py`, `tests/data/test_v2_conversion.py` | `pytest tests/data/test_v2_conversion.py -q` | real ETL | planned | no training logic |
| 43 | License/provenance training gate | `src/covalent_design/data/v2_license.py`, `tests/data/test_v2_license.py` | `pytest tests/data/test_v2_license.py -q` | training eligibility | planned | unknown/blocked cannot train |
| 44 | RDKit normalization adapter | `src/covalent_design/chem/rdkit_normalize.py`, `tests/chem/test_rdkit_normalize.py` | `pytest tests/chem/test_rdkit_normalize.py -q` | chemistry reports | planned | skipped when RDKit unavailable |
| 45 | RDKit scaffold/descriptor interface | `src/covalent_design/chem/scaffolds.py`, `src/covalent_design/chem/rdkit_descriptors.py` | `pytest tests/chem/test_rdkit_descriptors.py tests/chem/test_scaffolds.py -q` | family/scaffold eval | planned | diagnostic not hard gate |
| 46 | PyTorch tensor adapter seam | `src/covalent_design/model/torch_backend.py`, `tests/model/test_torch_backend.py` | `pytest tests/model/test_torch_backend.py -q` | PMDM/training | planned | contracts stay serializable |
| 47 | Real PMDM adapter smoke | `src/covalent_design/model/pmdm_real_adapter.py`, `tests/model/test_pmdm_real_adapter.py` | `pytest tests/model/test_pmdm_real_adapter.py -q` | PMDM training path | planned | no silent fallback |
| 48 | Explicit baseline fallback | `src/covalent_design/model/non_pmdm_baseline.py`, `tests/model/test_non_pmdm_baseline.py` | `pytest tests/model/test_non_pmdm_baseline.py -q` | fallback training | planned | labeled `non_pmdm_baseline` |
| 49 | V2 training dataset eligibility | `src/covalent_design/training/v2_dataset.py`, `tests/training/test_v2_dataset.py` | `pytest tests/training/test_v2_dataset.py -q` | training loop | planned | license + family readiness gates |
| 50 | CPU/GPU training smoke loop | `src/covalent_design/training/v2_train_loop.py`, `configs/v2_train_cpu_smoke.yml` | `pytest tests/training/test_v2_train_loop.py -q`; `python -m covalent_design.training.cli.v2_train --config configs/v2_train_cpu_smoke.yml` | checkpoints/tuning | planned | GPU smoke manual |
| 51 | V2 checkpoint/experiment manifest | `src/covalent_design/training/v2_manifests.py`, `tests/training/test_v2_manifests.py` | `pytest tests/training/test_v2_manifests.py -q` | tuning/sampling | planned | no weight fixtures |
| 52 | Tiny tuning protocol | `src/covalent_design/training/v2_tuning.py`, `configs/v2_tiny_sweep.yml` | `pytest tests/training/test_v2_tuning.py -q`; `python -m covalent_design.training.cli.v2_tune --config configs/v2_tiny_sweep.yml` | checkpoint selection | planned | budget controlled |
| 53 | Sampling request/result V2 | `src/covalent_design/inference/v2_sampling.py`, `tests/inference/test_v2_sampling.py` | `pytest tests/inference/test_v2_sampling.py -q` | sampling smoke | planned | preserves failure accounting |
| 54 | Deterministic sampling smoke | `tests/inference/test_v2_sampling_smoke.py`, `configs/v2_sampling_smoke.yml` | `pytest tests/inference/test_v2_sampling_smoke.py -q` | evaluation | planned | held-out + per-family |
| 55 | V2 evaluation metrics | `src/covalent_design/evaluation/v2_metrics.py`, `tests/evaluation/test_v2_metrics.py` | `pytest tests/evaluation/test_v2_metrics.py -q` | beta gate | planned | `not_evaluable` allowed |
| 56 | Docking feasibility | `src/covalent_design/evaluation/v2_docking_feasibility.py`, `tests/evaluation/test_v2_docking_feasibility.py` | `pytest tests/evaluation/test_v2_docking_feasibility.py -q` | optional future docking | planned | non-blocking |
| 57 | Pretraining feasibility decision | `docs/v2/08-v2-noncovalent-pretraining-feasibility.md`, review doc | `rg -n "Transfer Hypothesis|Candidate Datasets|License Status|Label Compatibility|Ablation Plan|Rejection Criteria|Final Verdict" docs/v2/08-v2-noncovalent-pretraining-feasibility.md`; owner signoff in review doc | optional research | planned | non-blocking |
| 58 | Optional pretraining audit/smoke | `src/covalent_design/pretraining/`, `tests/pretraining/` | `pytest tests/pretraining -q` | future research only | optional | skipped unless approved |
| 59 | V2 beta release gate | `docs/reviews/v2-beta-release-gate-review.md`, v2 reports | `python -m compileall -q scripts src`; `python -m pytest -q`; `python -m unittest discover -s tests -t . -q` | next phase | planned | Task 57/58 non-blocking |

## Checkpoints

| Checkpoint | Covers | Required evidence |
| --- | --- | --- |
| V2-A Environment Gate | Tasks 37-39 | environment scaffold, dependency source verification, lightweight smoke |
| V2-B Data Intake Gate | Tasks 40-43 | manifests, intake, conversion, license gate |
| V2-C Chemistry Gate | Tasks 44-45 | RDKit adapter reports or explicit unavailable status |
| V2-D Training Foundation Gate | Tasks 46-51 | tensor adapter, PMDM/baseline path, dataset, training smoke, manifests |
| V2-E Tuning Gate | Task 52 | tiny sweep manifest and selected checkpoint |
| V2-F Sampling And Evaluation Gate | Tasks 53-56 | deterministic sampling, metrics, docking feasibility status |
| V2-G Optional Pretraining Decision | Task 57 | feasibility verdict; if accepted/experimental, open a separate implementation checkpoint before code lands |
| V2-H Release Gate | Task 59 | full beta closed-loop evidence |

## Default Lightweight Verification

```powershell
$env:PYTHONPATH='src'
python -m compileall -q scripts src
python -m pytest -q
python -m unittest discover -s tests -t . -q
```

## Heavy Verification Policy

Heavy commands are opt-in/manual until Task 37-39 are implemented and source-verified. Missing heavy dependencies must not fail default CI.

## Heavy Test Marker Policy

- `lightweight` tests are default-CI tests and must not import heavyweight optional dependencies.
- `heavy` tests are opt-in and must be marked before dependency import.
- Heavy tests must distinguish dependency unavailable, platform unavailable, license unavailable, source verification missing, and runtime failure.
- Default CI may verify that heavy tests are discoverable, but it must not execute heavyweight dependency paths unless the `heavy` profile is selected.
