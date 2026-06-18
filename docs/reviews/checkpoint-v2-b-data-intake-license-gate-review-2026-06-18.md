# Checkpoint V2-B Data Intake And License Gate Review

Date: 2026-06-18

## Executive Summary

- Overall Status: PASS WITH RISKS
- Allow Task 44: conditional. The lightweight fixture gate is complete and passing, but real local data evidence under `D:\codex_work\data` was not inspected in this checkpoint because no new explicit authorization was provided.
- Largest risk: Checkpoint V2-B is proven for Tasks 40-43 contracts, fixtures, docs, and git hygiene, but not yet proven against real local user data.

## Scope

This review covers Tasks 40-43 only:

- Task 40 source intake manifest contracts.
- Task 41 local manual staging and download-mode metadata fixtures.
- Task 42 conversion from validated staged inputs into v1-compatible ETL records.
- Task 43 license/provenance training eligibility gate.

This review did not enter Task 44, did not perform network download, did not install dependencies, did not run real data conversion outside test fixtures, and did not read or modify `D:\codex_work\data`.

## Claude Code Coordination

The main controller launched five Claude Code child windows through `.\codex-claude-docs.ps1` for Checkpoint V2-B:

- Window A: evidence/scope read plan.
- Window B: test verification read plan.
- Window C: boundary audit review.
- Window D: git/local-data hygiene read plan.
- Window E: report read plan.

These windows were launched as Claude Code windows, not Codex child threads. They were kept in read/review modes for this checkpoint; the main controller ran verification, interpreted results, and wrote the final review report.

## Evidence Table

| Area | Evidence | Result | Notes |
| --- | --- | --- | --- |
| Task 40 manifest tests | `python -m pytest tests/data/test_v2_manifests.py -q` | PASS, 29 passed | Validates manifest schema, forbidden fields, deterministic serialization, and scope boundaries. |
| Task 41 intake tests | `python -m pytest tests/data/test_v2_intake.py -q` | PASS, 19 passed | Validates local staging fixtures and download-mode metadata without network download. |
| Task 42 conversion tests | `python -m pytest tests/data/test_v2_conversion.py -q` | PASS, 42 passed | Validates conversion from Task 41 staged evidence, checksum behavior, parser target boundaries, and provenance preservation. |
| Task 43 license tests | `python -m pytest tests/data/test_v2_license.py -q` | PASS, 32 passed | Validates five-state license model, `manual_exempt`, restricted conditions, cross-validation, report categories, and no training artifacts. |
| Combined Tasks 40-43 | `python -m pytest tests/data/test_v2_manifests.py tests/data/test_v2_intake.py tests/data/test_v2_conversion.py tests/data/test_v2_license.py -q` | PASS, 122 passed | Confirms the checkpoint fixture chain is internally consistent. |
| Full pytest | `python -m pytest -q` | PASS, 1894 passed, 326 subtests passed | Sequential run used to avoid shared smoke-fixture races from parallel full-suite processes. |
| Full unittest | `python -m unittest discover -s tests -t . -q` | PASS, 1761 tests | Confirms legacy unittest suite still passes. |
| Compile | `python -m compileall -q scripts src` | PASS | No syntax errors in scripts or source package. |
| Documentation inspection | `rg -n "Task 40|Task 41|Task 42|Task 43|D:\\codex_work\\data|license|provenance|allowed|restricted|blocked|unknown|manual_exempt|cross-validation|git" ...` | PASS | V2 docs contain the expected checkpoint terms, five license states, manual/download distinctions, and git boundary notes. |
| Git raw-data scan | `git ls-files \| rg "D:\\codex_work\\data|data/raw|raw_data|\\.sdf$|\\.mol2$|\\.pdb$|\\.cif$|\\.csv$|\\.tsv$"` | PASS WITH NOTE | Matched only tracked `data/raw/*/.gitkeep` placeholders. No tracked `.sdf`, `.mol2`, `.pdb`, `.cif`, `.csv`, or `.tsv` raw data files were found. |

## Test Results

Commands run:

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/data/test_v2_manifests.py -q
python -m pytest tests/data/test_v2_intake.py -q
python -m pytest tests/data/test_v2_conversion.py -q
python -m pytest tests/data/test_v2_license.py -q
python -m pytest tests/data/test_v2_manifests.py tests/data/test_v2_intake.py tests/data/test_v2_conversion.py tests/data/test_v2_license.py -q
python -m compileall -q scripts src
python -m pytest -q
python -m unittest discover -s tests -t . -q
```

Results:

- Task 40: 29 passed.
- Task 41: 19 passed.
- Task 42: 42 passed.
- Task 43: 32 passed.
- Combined Tasks 40-43: 122 passed.
- Full pytest: 1894 passed, 326 subtests passed.
- Full unittest: 1761 tests, OK.
- Compileall: pass.

## License Gate Review

The Task 43 implementation and docs support the five-state license model:

- `allowed`
- `restricted`
- `blocked`
- `unknown`
- `manual_exempt`

Observed checkpoint status:

- `allowed` passes eligibility.
- `restricted` passes only with recorded and satisfied restrictions.
- `blocked` and `unknown` do not enter training eligibility.
- `manual_exempt` remains distinct from `allowed`, is valid only for manual intake mode, and is rejected for download intake mode.
- Cross-validation covers `license_audit_ref`, checksum, local path provenance, and source provenance mismatches between staged evidence and converted records.

No evidence was found that `manual_exempt` bypasses manifest validation, checksum validation, parser target validation, local path provenance, source provenance, or license audit reference validation.

## Data Boundary Review

Tasks 40-43 remain inside the intended data-intake and license-gate boundary:

- Task 40 does not download, stage, convert, inspect raw data contents, decide license eligibility, or generate training artifacts.
- Task 41 validates local staging evidence and download-mode metadata but does not perform network download.
- Task 42 converts validated staged inputs and preserves provenance; it does not decide license or training eligibility.
- Task 43 audits license/provenance eligibility and may cross-check converted records; it does not execute conversion, raw parsers, training, sampling, or Task 44 work.

No RDKit, PyTorch, PMDM, PocketFlow, training, inference, or evaluation work was part of this checkpoint.

## Git Hygiene Review

`git status --short` shows an intentionally active V2 workspace with modified and untracked docs, source, tests, fixtures, prompts, and review files from recent V2 tasks. No staging or commit was performed.

Raw-data tracking scan:

- `git ls-files | rg "D:\\codex_work\\data|data/raw|raw_data|\\.sdf$|\\.mol2$|\\.pdb$|\\.cif$|\\.csv$|\\.tsv$"` matched `data/raw/*/.gitkeep` placeholders.
- A stricter extension scan found no tracked `.sdf`, `.mol2`, `.pdb`, `.cif`, `.csv`, or `.tsv` files.
- The repository-tracked `data/raw/*/.gitkeep` placeholders are not real raw data, but the broad checkpoint command does flag them because they sit under `data/raw`.

## Local Real Data Evidence

Real local data under `D:\codex_work\data` was not inspected in this checkpoint. The user request did not provide new explicit authorization to read or modify that external data root, and the checkpoint prompt forbids doing so without authorization.

Therefore:

- Fixture and lightweight evidence is complete.
- Real local data evidence remains pending.
- This review does not claim that real local data has been staged or license-audited.

## Blocking Issues

None for the fixture/lightweight Checkpoint V2-B gate.

## Important Issues

1. Real local data evidence is pending.
   - Severity: Important
   - Evidence: This review did not read `D:\codex_work\data`.
   - Why it matters: V2-B names local real data staging as part of the full gate.
   - Required fix: The user must either accept this fixture-only PASS WITH RISKS or explicitly authorize a later local-data evidence pass.

2. Broad raw-data git scan matches placeholder files.
   - Severity: Important
   - Evidence: `data/raw/covalentin_db/.gitkeep`, `data/raw/covbinder_in_pdb/.gitkeep`, and `data/raw/covpdb/.gitkeep` are tracked.
   - Why it matters: The checkpoint command is intentionally broad and will not be empty while placeholders remain tracked.
   - Required fix: Treat these as allowed placeholders in gate interpretation, or narrow the future raw-data scan to real raw-data extensions and non-placeholder files.

## Minor Issues

None blocking. Documentation uses both fixture/lightweight status and local-data-manual language; the review status should keep distinguishing those two evidence levels.

## Final Verdict

Checkpoint V2-B status: PASS WITH RISKS.

Task 44 may proceed only if the user accepts fixture/lightweight V2-B evidence as sufficient for now, or after a separate authorized local-data evidence pass confirms `D:\codex_work\data` staging and license-gate behavior.

If proceeding to Task 44, the next prompt should explicitly preserve these boundaries:

- Do not download data.
- Do not treat `manual_exempt` as equivalent to `allowed`.
- Do not bypass checksum, manifest, parser target, provenance, or license audit reference checks.
- Do not claim real local data evidence unless `D:\codex_work\data` was explicitly authorized and inspected.
