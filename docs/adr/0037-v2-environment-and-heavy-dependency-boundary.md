# ADR 0037: V2 Environment And Heavy Dependency Boundary

Status: Accepted

Date: 2026-06-16

## Context

V2 planning introduces optional heavyweight capabilities such as RDKit-based chemistry checks, PyTorch-backed model paths, CUDA-enabled smoke runs, PMDM/PocketFlow adapters, docking, and real-data ETL checks. The v1 repository currently keeps default CI lightweight and must remain runnable on Windows without installing those heavyweight stacks.

Task 37 is the first v2 implementation task. It needs a stable environment boundary before any code is written so later tasks do not accidentally make RDKit, PyTorch, CUDA, PMDM, PocketFlow, or docking tools mandatory for default CI.

## Decision

V2 uses exactly two smoke profile names:

- `lightweight`: default profile for local Windows and default CI. It must not hard-import RDKit, PyTorch, CUDA-only packages, PMDM, PocketFlow, docking tools, or other heavyweight optional dependencies. Missing heavyweight dependencies must be reported as structured unavailable statuses, not import crashes.
- `heavy`: opt-in profile for Linux, WSL2, or Conda/Mamba environments that intentionally install heavyweight optional dependencies. Heavy checks may validate real RDKit/PyTorch/CUDA/PMDM/PocketFlow/docking integrations only after each dependency and API claim is source-verified.

The old `cpu` profile name is not a v2 smoke profile. CPU may describe a runtime mode for a later training or inference job, but smoke commands must use `--profile lightweight` or `--profile heavy`.

Default CI runs only the `lightweight` profile. Heavy checks are manual, scheduled, or opt-in until the project explicitly adds heavyweight dependency installation and cost controls.

## Source Verification Boundary

Before v2 code relies on a real external API from RDKit, PyTorch, CUDA packages, PMDM, PocketFlow, docking tools, or another heavyweight dependency, the claim must be tied to an official project source such as official documentation, official API reference, official source code, or official release notes. Unsupported or unverified APIs must remain behind adapter boundaries or future-task notes.

## Relationship To ADR 0034

ADR 0034 keeps repository governance and default CI lightweight. This ADR extends that boundary for v2 by defining the heavyweight dependency path and by freezing `lightweight` / `heavy` smoke profile vocabulary.

## Alternatives Considered

- Keep `cpu` / `heavy` as smoke profile names. Rejected because v2 docs already use `lightweight`, and `cpu` can be confused with later CPU runtime modes that may still require PyTorch.
- Add heavyweight dependencies to default CI immediately. Rejected because this would make CI slower, more fragile, and dependent on tools that are not yet source-verified or implemented.
- Treat missing heavyweight dependencies as skipped tests only. Rejected because v2 needs structured unavailable statuses that downstream checks can inspect.

## Consequences

- Task 37 must implement a lightweight smoke probe first.
- Heavy checks cannot become default CI gates without an explicit follow-up decision.
- V2 docs and tests must use `lightweight` and `heavy` consistently.
- Future heavy adapters must fail closed with structured unavailable statuses when dependencies or chemical state are unavailable.
- Documentation must not freeze unverified third-party API names as implemented contracts.

## Related Tasks

- Task 37: environment smoke and v2 health probe.
- Task 38: source verification table for heavyweight dependencies and external APIs.
- Task 44-46: optional RDKit-backed real-data checks.
- Task 50-56: optional PyTorch/PMDM/PocketFlow/heavy model paths.
- Task 58-59: integration and release candidate gates.

## Related Specs

- `docs/v2/04-v2-dependency-and-environment-spec.md`
- `docs/v2/10-v2-implementation-plan.md`
- `docs/v2/11-v2-verification-matrix.md`
- `docs/specs/key-design-decisions.md`

## Verification Expectations

- `python scripts/v2_smoke_check.py --profile lightweight` is the default v2 smoke gate.
- `python scripts/v2_smoke_check.py --profile heavy` is opt-in/manual.
- Documentation checks must reject deprecated CPU-named smoke profiles in v2 smoke commands.
- Heavy dependency checks must distinguish dependency unavailable, unverified API, unsupported platform, and failed runtime check.
