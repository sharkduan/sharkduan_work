# V2 Idea Refinement

Date: 2026-06-16
Status: planning synthesis

## How Might We

How might we evolve v1 from contract-complete smoke scaffolding into a real v2-beta covalent inhibitor design pipeline without pretending that early real-data and real-model results are publication-grade?

## Options Considered

| Option | Description | Benefit | Main Risk | Decision |
| --- | --- | --- | --- | --- |
| v2-alpha | Broaden sources, families, docking, and training at once | Ambitious coverage | Too many unverified dependencies and data assumptions | Reject |
| v2-beta | Real environment, real data path, real backbone boundary, small training/eval loop | Stable next milestone | Still depends on PMDM/data/license verification | Accept |
| v2-research | Noncovalent pretraining, paper-focused optimization, broader baselines | Research upside | Expensive and uncertain | Defer |

## Recommended Direction

Use v2-beta as the next milestone. It should be narrow, testable, and honest:

- one primary Linux/WSL2 CUDA environment,
- one real-data acquisition pipeline for the three v1 sources,
- one PMDM-compatible model path or labeled fallback,
- one small training/tuning budget,
- one held-out and per-family evaluation package,
- explicit family readiness and license gates.

## Rejected Directions

- Formal `v2-alpha`/`v2-release` version split: rejected for now. V2-beta is the only named target; internal checkpoints still exist.
- Paper-grade result target: rejected for v2-beta because data, dependency, and baseline verification must come first.
- Docking-as-release-gate: rejected for v2-beta until a source-verified engine and fixture path exist.
- Noncovalent pretraining mainline: rejected from the beta critical path and retained only as an experimental track.

## MVP Scope

1. Create v2 environment and dependency lock.
2. Verify source and dependency licenses.
3. Automate or manually stage the three v1 raw data sources.
4. Run real ETL and family readiness checks.
5. Add RDKit basic chemical validity and scaffold checks.
6. Integrate real PMDM boundary or labeled fallback baseline.
7. Run budgeted training smoke and small sweep.
8. Sample held-out and per-family outputs.
9. Evaluate validity, family coverage, and lifecycle reports.
10. Run docking feasibility checks only if source-verified tooling is available.

## Not Doing In V2-Beta

- Noncovalent pretraining as a mainline requirement.
- Exhaustive residue-reaction family expansion beyond the six v1 families.
- Production docking gate.
- Publication-level benchmark claims.
- Multi-GPU optimization.
- New public serving or deployment system.
- Task 29 RDKit mmCIF backend unless source-verified later.

## Key Assumptions To Validate

- PMDM can be imported or adapted in the selected environment.
- Data-source access is technically and legally available.
- Six-family data coverage is sufficient or can be reported as partial readiness.
- RDKit and PyTorch can coexist in the environment.
- One GPU is enough for smoke and small sweep runs.
- Heavy v2 checks can remain outside default CI.

## Pretraining Track Verdict

Noncovalent pretraining is an experimental research track. It may be explored after v2-beta can run end to end. It must have separate data licenses, transfer hypotheses, and rejection criteria before implementation.
