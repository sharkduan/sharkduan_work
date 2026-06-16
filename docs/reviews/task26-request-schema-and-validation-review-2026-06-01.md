# Task 26 Request Schema And Validation Review

Date: 2026-06-01

## Scope

Task 26 implements request schema loading, semantic validation, normalized YAML
serialization, and the validation CLI. Task 27 sampling and generation remain
out of scope.

## Review Result

Status: pass

Window E adversarial review found no blockers. The implementation:

- loads authoritative YAML and accepted JSON request files;
- validates the exact 13 `REQUEST_*` error codes without adding a fourteenth;
- resolves PDB and mmCIF atom identity with deterministic altloc behavior;
- treats empty parsed structures as `REQUEST_STRUCTURE_UNREADABLE`;
- preserves PDB model selection and atom serial identity;
- rejects non-integer sample count and ligand-size controls with deterministic
  semantic errors;
- writes deterministic UTF-8 normalized YAML only when the writer API is
  explicitly called;
- exposes deterministic JSON through
  `python -m covalent_design.inference.validate_request`;
- does not import RDKit, torch, PMDM, or PocketFlow;
- does not implement Task 27 sampling or generate inference artifacts.

## Verification

```powershell
$env:PYTHONPATH='src'
python -m unittest tests.inference.test_request_validation -v
python -m unittest discover -s tests -t . -q
python -m compileall -q scripts src
python -m covalent_design.inference.validate_request --help
python -m covalent_design.inference.validate_request --request tests\fixtures\inference\request_validation\valid_request.yml
python -m covalent_design.inference.validate_request --request tests\fixtures\inference\request_validation\valid_request.json
git diff --check
```

Results:

- Task 26 tests: 72 passed.
- Full unittest suite: 1178 passed.
- `compileall`: passed.
- CLI help: passed.
- YAML fixture CLI: passed.
- JSON fixture CLI: passed.
- `git diff --check`: passed.

Optional `python -m pytest tests/inference/test_request_validation.py -q`
could not run because pytest is not installed in the current environment.

## Non-Blocking Follow-Ups

- Add explicit input type checks for identity string fields if stricter request
  schema rejection is desired.
- Add mmCIF multi-model and `asym_id` locator fixtures when expanding the
  structure-reader compatibility surface.

## Decision

Task 26 is accepted. Task 27 may start after controller confirmation.
