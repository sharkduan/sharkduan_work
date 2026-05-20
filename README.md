# Covalent Inhibitor Design

Research workspace for a PMDM-compatible covalent inhibitor generation model. The project defines data contracts, ADRs, and implementation scaffolding for de novo generation of complete covalent inhibitors conditioned on explicit protein-side reactive sites.

## Repository Layout

| Path | Purpose |
| --- | --- |
| `CONTEXT.md` | Domain language and terminology that future work should preserve. |
| `docs/` | Model, ETL, rule-table, and IO contract documents. |
| `docs/adr/` | Accepted architecture and research decision records. |
| `src/covalent_design/` | Project-owned implementation namespace. |
| `scripts/` | Small project-owned utility scripts. |
| `PMDM/` | Upstream PMDM baseline code used for reference and extension. |
| `PocketFlow/` | Upstream PocketFlow baseline code used for reference and supervision ideas. |
| `data/` | Local data staging tree. Generated/raw data stay out of git except `.gitkeep` files. |

## Quick Start

This repository currently separates lightweight project governance from heavyweight model environments. CI validates project-owned Python syntax and repository hygiene without installing CUDA, RDKit, or docking stacks.

Clone with the upstream model baselines:

```bash
git clone --recurse-submodules <repo-url>
```

If the repository is already cloned:

```bash
git submodule update --init --recursive
```

For PMDM baseline work:

```bash
conda env create -f PMDM/mol.yml
conda activate mol
```

For PocketFlow baseline work:

```bash
conda env create -f PocketFlow/environment.yml
conda activate pocketflow
```

## Local Checks

Run the checks that mirror the current GitHub Actions workflow:

```bash
python -m compileall -q scripts src
```

Before opening a PR, also review:

- `docs/github-management.md` for branch, PR, CI, and data policies.
- `CONTEXT.md` for accepted project language.
- `docs/adr/` for prior decisions that may constrain the change.

## GitHub Workflow

Use short-lived branches from `main`, open pull requests for all changes, and require CI plus review before merging. See `docs/github-management.md` for the repository settings to apply in GitHub.
