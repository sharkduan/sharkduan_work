# Task 17+ Change Review

Review date: 2026-05-26

Mode: Review only. This document records review findings only. It does not modify source, tests, specs, or ADRs.

Reviewed change set:

- `src/covalent_design/contracts/types.py`
- `docs/specs/interface-design.md`
- `docs/specs/implementation-plan.md`
- `docs/specs/key-design-decisions.md`
- `docs/specs/verification-matrix.md`
- `docs/specs/02-model.md`
- `docs/specs/03-training.md`
- `docs/specs/04-evaluation.md`
- `docs/specs/05-inference.md`
- `docs/adr/0035-task17-model-batch-contract.md`
- `docs/adr/0036-message-weight-leakage-prevention.md`

Skills applied:

- `code-review-and-quality`
- `code-reviewer`
- `doubt-driven-development`
- `api-and-interface-design`
- `documentation-and-adrs`
- `test-driven-development`
- `debugging-and-error-recovery` for the failing verification command

## Verdict

Task 17 Ready: **No**

Task 17+ Docs Ready: **No**

Contract Types Acceptable: **No**

Short reason:

- Current verification fails because `CovalentGenerationResult` expanded its constructor without updating existing lifecycle contract tests.
- `ModelForwardOutput.__post_init__` is promised by docs/ADR as the message-weight leakage guard, but it is not implemented in code.
- Task 17 `ModelBatch` still does not expose a stable reactive-site/target-atom contract needed by Task 18/19.

## Verification

Commands run:

- `git status --short`: pass
- `git diff -- src/covalent_design/contracts/types.py`: pass
- `git diff -- docs/specs/interface-design.md`: pass
- `git diff -- docs/specs/implementation-plan.md`: pass
- `git diff -- docs/specs/key-design-decisions.md`: pass
- `git diff -- docs/specs/verification-matrix.md`: pass
- `git diff -- docs/specs/02-model.md`: pass
- `git diff -- docs/specs/03-training.md`: pass
- `git diff -- docs/specs/04-evaluation.md`: pass
- `git diff -- docs/specs/05-inference.md`: pass
- `git diff -- docs/adr/0035-task17-model-batch-contract.md`: no output because file is untracked; reviewed with direct file read
- `git diff -- docs/adr/0036-message-weight-leakage-prevention.md`: no output because file is untracked; reviewed with direct file read
- `git diff --cached`: pass, no staged changes
- `$env:PYTHONPATH='src'; python -m compileall -q scripts src`: **pass**
- `$env:PYTHONPATH='src'; python -m unittest discover -s tests -t . -q`: **fail**

Failure summary:

```text
Ran 504 tests in 22.399s
FAILED (errors=4)
```

Failing tests:

- `tests.contracts.test_lifecycle.LifecycleContractTests.test_invalid_generation_requires_not_applicable_downstream_statuses`
- `tests.contracts.test_lifecycle.LifecycleContractTests.test_invalid_generation_rejects_exported_complex_status`
- `tests.contracts.test_lifecycle.LifecycleContractTests.test_export_failure_requires_complex_export_failure_reason`
- `tests.contracts.test_lifecycle.LifecycleContractTests.test_docking_success_requires_exported_artifact`

Root cause:

`CovalentGenerationResult` now requires 10 additional constructor arguments:

- `generated_ligand_status`
- `predicted_ligand_attachment_atom`
- `predicted_covalent_edge`
- `covalent_edge_score`
- `geometry_metrics`
- `molecular_quality_metrics`
- `matched_warhead_type`
- `predicted_warhead_type`
- `covalent_docking_score`
- `noncovalent_vina_score`

Existing lifecycle tests still instantiate the old shape.

Additional source-driven check:

- Local environment has no RDKit: `rdkit False`.
- A search of official RDKit rdmolfiles documentation did not provide evidence that `rdkit.Chem.rdmolfiles.MolToMMCIFBlock` exists.

## P0 Blocking Issues

### [P0] `CovalentGenerationResult` expansion breaks existing contract tests

File:

- `src/covalent_design/contracts/types.py`
- `tests/contracts/test_lifecycle.py`

Evidence:

- `CovalentGenerationResult` starts at `src/covalent_design/contracts/types.py:263`.
- Existing tests instantiate `CovalentGenerationResult(...)` at `tests/contracts/test_lifecycle.py:43`, `:63`, `:84`, and `:108`.
- `python -m unittest discover -s tests -t . -q` fails with missing required positional arguments for the new diagnostic fields.

Impact:

The change is not merge-ready. Existing lifecycle contract tests cannot run, so no downstream Task 28/30 lifecycle assumptions should be trusted.

Recommendation:

Choose one consistent strategy:

1. Provide safe defaults for nullable diagnostic fields so legacy lifecycle tests and simple fixtures remain concise.
2. Or update existing tests and add fixture builders for full result rows.

In either case, add tests for the new field semantics, not only constructor compatibility.

### [P0] Message-weight leakage prevention is documented but not implemented

File:

- `src/covalent_design/contracts/types.py`
- `docs/specs/interface-design.md`
- `docs/adr/0036-message-weight-leakage-prevention.md`

Evidence:

- `ModelForwardOutput` is defined at `src/covalent_design/contracts/types.py:465`.
- It has no `__post_init__`.
- `docs/specs/interface-design.md` says `ModelForwardOutput.__post_init__` validates `edge_prob_message_weights.requires_grad == False`.
- ADR 0036 makes the same runtime assertion the core anti-leakage mechanism.

Impact:

The central enforcement mechanism in ADR 0036 does not exist. Task 20 negative tests would not be able to prove the promised public API guard.

Recommendation:

Implement `ModelForwardOutput.__post_init__` or change the docs/ADR to say the check is future Task 20 scope.

Also revisit the mechanism: `requires_grad == False` catches accidentally passing logits, but it does not reliably detect labels, since label tensors commonly also have `requires_grad == False`.

### [P0] Task 17 `ModelBatch` lacks explicit reactive-site / target-atom contract

File:

- `src/covalent_design/contracts/types.py`
- `docs/specs/interface-design.md`
- `docs/adr/0035-task17-model-batch-contract.md`

Evidence:

- `BatchRecordHeader` records identity, family, quality, visual status, chemical state, split/fallback, and artifact refs.
- `BatchTensors` records shapes and dtypes.
- `ModelBatch` records headers, tensor metadata, static edge candidate refs, and expected denominators.
- None of these fields explicitly expose `target_atom_identity`, target atom index, reactive-site locator, or target atom mapping.

Impact:

Task 18 stepwise candidates and Task 19 PMDM adapter both require a fixed reactive target atom. If this remains implicit inside artifact files, Task 17 is not a stable contract boundary.

Recommendation:

Add explicit target atom identity and target atom index/mapping to the Task 17 contract, either in `BatchRecordHeader` or in a dedicated reactive-site batch field. Alternatively, document exactly which artifact schema field is the authoritative source and require `inspect_batch` to surface it.

## P1 Important Issues

### [P1] New public contract types are not exported from `covalent_design.contracts`

File:

- `src/covalent_design/contracts/__init__.py`

Evidence:

- `contracts/__init__.py` exports old contract types but not `ModelBatch`, `BatchSpec`, `ModelForwardOutput`, `LossReport`, `GenerationRunManifest`, and related Task 17+ types.
- `from covalent_design.contracts import ModelBatch` raises `ImportError`.

Impact:

The docs describe these as public contracts, but consumers cannot import them from the public `contracts` facade. This encourages inconsistent imports from `contracts.types`.

Recommendation:

If these are public contracts, export them from `contracts/__init__.py` and `__all__`. If they are intentionally internal, update docs/ADR language.

### [P1] `LossReport` required components are not validated

File:

- `src/covalent_design/contracts/types.py`
- `docs/specs/interface-design.md`

Evidence:

- `LossReport` starts at `src/covalent_design/contracts/types.py:579`.
- `components` defaults to an empty mapping.
- No `__post_init__` checks for the six required keys.
- `docs/specs/interface-design.md` says `components` keys are validated at construction.

Impact:

Task 24 can produce an incomplete `LossReport` while still satisfying the dataclass constructor.

Recommendation:

Add construction-time validation for:

- `pmdm_position_loss`
- `pmdm_atom_loss`
- `covalent_edge_loss`
- `covalent_bond_type_loss`
- `covalent_geometry_loss`
- `family_aux_loss`

Or move the validation responsibility to a writer/validator and update the docs.

### [P1] `LossReport.to_dict()` does not serialize the full `MaskAudit`

File:

- `src/covalent_design/contracts/types.py`
- `docs/specs/verification-matrix.md`

Evidence:

- `_mask_audit_dict()` serializes only a subset of `MaskAudit`.
- The verification matrix says Checkpoint B requires `MaskAudit` 15 fields.

Impact:

Checkpoint B evidence cannot be produced from the current serializer as documented.

Recommendation:

Serialize every `MaskAudit` field, including:

- `candidate_count`
- `natural_positive_count`
- `forced_positive_count`
- `natural_negative_count`
- `zero_negative_count`
- all masked-by counts
- all eligible/denominator counts

### [P1] Lifecycle validator does not validate the new `CovalentGenerationResult` semantics

File:

- `src/covalent_design/contracts/lifecycle.py`
- `src/covalent_design/contracts/types.py`

Evidence:

`validate_lifecycle()` still validates:

- lifecycle status values
- failure reason codes
- lifecycle transition constraints
- edge validity check values
- `complex_mmcif` artifact when exported

It does not validate:

- `generated_ligand_status`
- whether valid samples have ligand/edge/geometry diagnostics
- whether invalid samples preserve available diagnostics
- whether `covalent_docking_score` is present only when docking succeeds
- whether `noncovalent_vina_score` is separated from `covalent_docking_score`
- whether required artifacts match lifecycle state beyond `complex_mmcif`

Impact:

The result contract can look complete while allowing semantically invalid rows.

Recommendation:

Extend lifecycle validation or add a separate `validate_generation_result()` that covers the expanded result schema.

### [P1] RDKit mmCIF writer decision appears unsupported

File:

- `docs/specs/interface-design.md`
- `docs/specs/implementation-plan.md`
- `docs/specs/key-design-decisions.md`
- `docs/specs/05-inference.md`

Evidence:

- Docs freeze v1 writer as `rdkit.Chem.rdmolfiles.MolToMMCIFBlock`.
- Local environment has no RDKit.
- Official RDKit rdmolfiles docs inspected during review did not provide evidence of `MolToMMCIFBlock`.
- README says default CI does not install RDKit.

Impact:

Task 29 may be locked to a non-existent or unavailable API. Verification cannot be assumed to be runnable in the current project environment.

Recommendation:

Before Task 29, verify the exact writer against official RDKit documentation or choose an internal/project-owned mmCIF writer. If RDKit remains required, mark Task 29 verification as heavyweight/manual unless a local fixture runner is added.

### [P1] PMDM adapter required key count is inconsistent

File:

- `docs/adr/0035-task17-model-batch-contract.md`
- `docs/specs/implementation-plan.md`
- `docs/specs/interface-design.md`

Evidence:

ADR 0035 says 6 required keys, but lists 7:

- `ligand_atom_features`
- `protein_atom_features`
- `ligand_coords_denoised`
- `position_loss`
- `atom_type_loss`
- `timestep`
- `num_atom`

Implementation plan also says 8 keys with 6 required and 2 optional, but its list includes 7 required.

Impact:

Task 19 tests may disagree on whether 6 or 7 required keys are correct.

Recommendation:

Correct the count everywhere. The current listed set is 7 required plus 2 optional.

### [P1] `REQUEST_*` error count is wrong

File:

- `src/covalent_design/contracts/types.py`
- `docs/specs/implementation-plan.md`
- `docs/specs/verification-matrix.md`

Evidence:

`REQUEST_VALIDATION_ERROR_CODES` contains 13 values:

1. `REQUEST_STRUCTURE_UNREADABLE`
2. `REQUEST_TARGET_RESIDUE_NOT_FOUND`
3. `REQUEST_TARGET_RESIDUE_AMBIGUOUS`
4. `REQUEST_TARGET_ATOM_NOT_FOUND`
5. `REQUEST_RESIDUE_NAME_MISMATCH`
6. `REQUEST_FAMILY_UNSUPPORTED`
7. `REQUEST_RESIDUE_FAMILY_CONFLICT`
8. `REQUEST_ATOM_FAMILY_CONFLICT`
9. `REQUEST_SAMPLE_COUNT_INVALID`
10. `REQUEST_LIGAND_SIZE_INVALID`
11. `REQUEST_LIGAND_SIZE_RANGE_INVALID`
12. `REQUEST_LIGAND_SIZE_CONFLICT`
13. `REQUEST_REQUIRED_CHEMICAL_STATE_UNAVAILABLE`

Docs say all 12 `REQUEST_*` errors.

Impact:

Task 26 fixture coverage may miss one error code.

Recommendation:

Update docs to 13, or remove/merge one error code deliberately.

### [P1] Training run manifest omits quality and visual gate hashes after separating governance from runtime

File:

- `src/covalent_design/contracts/types.py`
- `docs/specs/interface-design.md`
- `docs/adr/0035-task17-model-batch-contract.md`

Evidence:

- ADR 0035 says the Data Release Gate is governance, not runtime.
- Task 25 manifest input hashes include records, split, and rule table.
- Quality report hash and visual check hash are explicitly not included in training manifest.

Impact:

Two training runs using the same `records.jsonl` and split can have different release-gate context, but the checkpoint manifest will not capture that difference. This weakens reproducibility and auditability.

Recommendation:

Either include Data Release Gate artifacts in `TrainingRunManifest.input_hashes`, or document a separate release approval manifest that checkpoint metadata references.

## P2 Follow-up Issues

### [P2] `contracts/types.py` is becoming too broad

File:

- `src/covalent_design/contracts/types.py`

Evidence:

One file now contains source ingest records, generation results, model batches, stepwise candidates, training reports, training manifests, and inference manifests.

Impact:

This is manageable for the freeze, but likely to become hard to maintain as Tasks 17-33 are implemented.

Recommendation:

Consider later splitting into:

- `contracts/model.py`
- `contracts/training.py`
- `contracts/inference.py`
- `contracts/evaluation.py`

Then re-export stable public types through `contracts/__init__.py`.

### [P2] Enum-like vocabularies remain plain tuples and fields remain plain strings

File:

- `src/covalent_design/contracts/types.py`

Evidence:

Status and reason vocabularies are tuple constants. Most dataclass fields are `str`.

Impact:

Type checkers cannot catch misspelled status values. Runtime validators must carry the safety burden.

Recommendation:

Acceptable short-term for Python 3.9 compatibility, but add validators for high-risk public types.

### [P2] Resolved/open question sections still contain residual ambiguity

File:

- `docs/specs/02-model.md`
- `docs/specs/05-inference.md`

Evidence:

- PMDM adapter pattern is marked resolved, but `02-model.md` still asks whether integration should be pure adapter, subclass, or fork.
- Default pocket radius is marked resolved as 4.0, but `05-inference.md` still asks for default pocket radius and sampling step count.

Impact:

Not blocking Task 17, but confusing for downstream implementers.

Recommendation:

Split remaining questions so only unresolved parts remain.

## Documentation-Code Drift

- `ModelForwardOutput.__post_init__` is documented but absent in code.
- `LossReport.components` construction validation is documented but absent in code.
- `LossReport.to_dict()` does not output the full documented `MaskAudit`.
- `REQUEST_*` count is 13 in code but 12 in docs.
- PMDM adapter required key count is documented as 6 but listed as 7.
- Task 17+ types are in `contracts/types.py` but not exported from `contracts/__init__.py`.
- `CovalentGenerationResult` expanded, but `validate_lifecycle()` does not validate the expanded semantics.

## Contract Design Risks

- `CovalentGenerationResult` is now large and constructor-heavy. Without defaults or builders, tests and callers become noisy.
- Nullable diagnostics can hide required lifecycle semantics unless validators enforce state-specific requirements.
- The message-weight anti-leakage guard is insufficient as written: `requires_grad=False` cannot distinguish detached predictions from ordinary label tensors.
- `ModelBatch` is closer to a shape/provenance manifest than an actual batch. This can be fine, but the name and consumer responsibilities must stay precise.
- Task 17 not checking the Data Release Gate is architecturally defensible, but some later manifest must bind the release decision to training/checkpoint provenance.
- The RDKit mmCIF writer decision appears premature and may be incorrect.

## ADR / Decision Quality

ADR 0035:

- Useful decision record for the Task 17 boundary.
- Still needs a clearer executable link between Data Release Gate approval and training/checkpoint provenance.
- Contains the PMDM required-key count inconsistency.

ADR 0036:

- Correctly identifies label leakage as a major risk.
- The stated runtime mechanism is not implemented in code.
- The mechanism is also incomplete because labels may have `requires_grad=False`.

Key decisions:

- Helpful as a compact index.
- Some entries duplicate schema details that may be better kept in `interface-design.md`.
- `mmCIF writer` decision should not be considered stable until the RDKit API is source-verified.

## Task 17 Minimal Start Gate

Before Task 17 starts, these must be true:

- `python -m unittest discover -s tests -t . -q` passes.
- `CovalentGenerationResult` constructor/test strategy is repaired.
- `ModelForwardOutput.__post_init__` is either implemented or the docs/ADR are corrected to mark it as future Task 20 scope.
- `ModelBatch` explicitly exposes reactive-site target atom identity and target atom index/mapping, or the artifact schema source is made explicit and surfaced by `inspect_batch`.
- Task 17 contract types are exported consistently from `covalent_design.contracts` if they are public.
- Task 17 tests cover missing artifact, unreadable artifact, checksum mismatch, missing role, unsupported contract version, and required state unavailable.
- Task 17 is confirmed to depend only on finalized Task 13 `records.jsonl` plus existing artifact refs, not on Task 18+ outputs.

## Recommended Next Action

Choose one:

- A. Start Task 17
- B. Patch docs only
- C. Patch contract types only
- D. Patch both docs and contract types
- E. Re-run interview/grill because design intent is still unclear

Recommended choice:

**D. Patch both docs and contract types**

Reason:

- Current code changes break tests.
- Current docs/ADRs promise behavior not implemented in code.
- Some documentation decisions conflict with code or with external API evidence.
- Task 17 can become ready after a focused patch round, but it should not start while the contract layer is red.

## Final Decision

Task 17 implementation should not start yet.

Minimum patch scope before Task 17:

1. Repair `CovalentGenerationResult` compatibility and lifecycle tests.
2. Implement or revise the documented message-weight guard.
3. Add explicit reactive-site/target-atom fields or source contract to `ModelBatch`.
4. Export public Task 17+ contract types consistently.
5. Fix documentation counts and unsupported RDKit writer claim.
6. Re-run compileall and unittest.
