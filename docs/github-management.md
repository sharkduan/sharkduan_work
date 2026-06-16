# GitHub Management

## Branching

- `main` is the deployable and reviewable trunk.
- Use short-lived branches named `feature/<topic>`, `fix/<topic>`, `docs/<topic>`, `research/<topic>`, or `chore/<topic>`.
- Keep branches focused and merge within a few days when possible.
- Do not force-push shared branches unless the team explicitly agrees.

## Pull Requests

Every change should go through a pull request before merging to `main`.

PRs should:

- address one logical change;
- explain why the change is needed;
- list local validation commands and experiment evidence;
- update docs or ADRs when contracts, data semantics, model design, or evaluation semantics change;
- avoid committing generated data, checkpoints, caches, local environments, or raw corpora.

## CI Policy

The first CI layer is intentionally lightweight because the project depends on large scientific stacks that are not appropriate for every pull request.

Current required checks:

- compile project-owned Python under `scripts` and `src`;
- run targeted tests under `tests/contracts`, `tests/io`, `tests/data`, and `tests/rules`;
- run `tests/ci` policy tests so the workflow and repository hygiene rules self-check;
- run `tests/cli` structured-exit tests as part of the lightweight CLI gate;
- validate required documentation exists;
- validate ADR filename numbering;
- block generated caches and large binary artifacts from the repository;
- keep GitHub Actions dependencies updated with Dependabot.

Default CI installs only minimal dependencies (pytest) and intentionally excludes RDKit, CUDA, docking, training, inference, evaluation, PMDM, and PocketFlow.

Heavy checks such as CUDA training, docking, full conda environment solves, and benchmark evaluation should run as explicit experiment jobs or manual workflows once stable fixtures and runners exist.

## Data And Artifact Policy

Commit:

- source code;
- project documentation;
- ADRs and design contracts;
- small curated rule tables when they are intended as auditable source artifacts;
- `.gitkeep` placeholders that preserve data directory structure.

Do not commit:

- raw corpora;
- generated interim or processed datasets;
- model checkpoints;
- docking outputs;
- local caches;
- local environment files;
- experiment logs.

Large artifacts should live in external storage with enough metadata in the repository to reproduce or locate them.

### Fixture Policy

Test fixtures follow a minimal-commit policy documented in [`tests/fixtures/FIXTURE_POLICY.md`](../tests/fixtures/FIXTURE_POLICY.md). Only fixture files needed for deterministic contract validation are committed. Three narrow `.gitignore` exceptions exist for docking protocol manifest validation (a zero-byte `.log` and a minimal `.pdbqt`) and training checkpoint metadata (YAML-only, no `.pt` weights).

Local cache/log artifacts (`__pycache__/`, `*.pyc`, `.pytest_cache/`) are cleaned and are not part of the committed fixture set.

### Review And Prompt Artifacts

`docs/reviews/` is project audit evidence and should be tracked when a review is used to authorize a gate, checkpoint, governance remediation, or task transition.

`tests/ci/` and `tests/fixtures/FIXTURE_POLICY.md` are governance enforcement files and should be tracked with the CI and fixture-policy changes they validate.

`prompts/` contains local agent orchestration prompts and is ignored by default. Force-add a prompt only when a task explicitly requires the exact agent instruction as reproducibility or audit evidence. Do not stage or delete prompt files automatically.

## ADR Policy

Use `docs/adr/NNNN-kebab-case.md`.

Write or update an ADR when a change affects:

- data contracts;
- residue-reaction family semantics;
- rule masks or gates;
- generation request/result schemas;
- evaluation denominators or validity semantics;
- model architecture or loss terms;
- repository governance or CI policy.

Do not delete old ADRs. Supersede them with a new ADR when a decision changes.

## Recommended GitHub Settings

After the project is pushed to GitHub, configure branch protection for `main`:

- require pull requests before merging;
- require at least one approval;
- dismiss stale approvals when new commits are pushed;
- require the `CI` workflow checks to pass;
- block force pushes;
- block branch deletion;
- require conversation resolution before merge;
- allow auto-merge only after CI and review pass.

Recommended labels:

- `bug`
- `design`
- `documentation`
- `research`
- `ci`
- `data`
- `model`
- `evaluation`
- `needs-adr-review`
- `dependencies`

## Ownership Boundaries

Treat `PMDM/` and `PocketFlow/` as upstream baseline submodules unless a PR explicitly states why their pinned commits must change. Prefer project-owned extensions under `src/covalent_design/`, project scripts under `scripts/`, and decision records under `docs/adr/`.

When updating a baseline submodule, include:

- the old and new upstream commit;
- the reason for the update;
- any compatibility impact on project-owned scripts, contracts, or experiments.
