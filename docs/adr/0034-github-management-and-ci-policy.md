# GitHub Management And CI Policy

## Status

Accepted

## Date

2026-05-20

## Context

The workspace contains project-owned design documents, ADRs, ETL scaffolding, and two heavyweight upstream model baselines: PMDM and PocketFlow. The baseline environments include CUDA, RDKit, molecular tooling, docking-related dependencies, and large checkpoint/test artifacts. Installing and testing the full stack on every pull request would make CI slow, expensive, and brittle before the project has stable integration fixtures.

The project still needs GitHub management immediately: branch discipline, pull request templates, issue triage, data/artifact hygiene, ADR continuity, and a first CI gate that prevents common repository damage.

## Decision

Use trunk-based GitHub management with `main` as the protected branch and short-lived feature branches.

Add a lightweight GitHub Actions workflow that runs on pull requests and pushes to `main`. The workflow checks:

- project-owned Python syntax under `scripts` and `src`;
- repository hygiene for generated caches and large binary artifacts;
- required core documentation;
- ADR filename numbering.

Use Dependabot for GitHub Actions updates.

Use issue templates for bugs, research tasks, and design changes. Use a pull request template that requires scope, validation, data hygiene, upstream-code impact, and ADR review.

Keep heavyweight scientific validation out of the default CI gate until the project defines stable fixtures and suitable runners. Training, docking, full conda solves, and benchmark jobs should become separate manual or scheduled workflows when their inputs and runtime budgets are controlled.

## Alternatives Considered

### Full conda environment CI on every pull request

Rejected for the first GitHub management layer. The PMDM and PocketFlow environments are heavyweight, include GPU and chemistry dependencies, and are likely to produce slow or fragile CI before stable project-owned tests exist.

### Documentation-only governance without CI

Rejected. Documentation alone cannot prevent accidental commits of caches, checkpoints, raw corpora, or broken project-owned Python syntax.

### Treat upstream PMDM and PocketFlow as fully project-owned in CI

Rejected for now. These directories are baseline references and extension targets. Pull requests that modify them should explain the reason, but default CI should focus on project-owned scaffolding until ownership boundaries are narrowed.

## Consequences

The repository gets immediate GitHub governance without blocking every pull request on heavyweight scientific infrastructure. CI will catch syntax issues in owned scaffolding, missing governance docs, ADR numbering drift, and accidental binary/cache commits.

The default CI does not prove model correctness, training viability, docking behavior, or full dependency solvability. Those checks must be added incrementally as explicit experiment, integration, or benchmark workflows once stable fixtures exist.
