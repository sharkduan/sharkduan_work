# Final Development Specification

## Status

Reviewed and consolidated after the `grill-with-docs` and `doubt-driven-development` pass.

This directory is the implementation entrypoint for project-owned development under `src/covalent_design/`. The specifications translate the accepted project context, design contracts, and ADR set into implementable module boundaries and verification gates.

No new ADR is introduced by this consolidation. The decisions summarized here are already covered by existing ADRs and design contracts.

## Source Of Truth

Read these files in order before implementation:

1. `00-shared-contracts.md`
2. `01-data-processing.md`
3. `02-model.md`
4. `03-training.md`
5. `05-inference.md`
6. `04-evaluation.md`
7. `verification-matrix.md`
8. `key-design-decisions.md`
9. `interface-design.md`
10. `implementation-plan.md`

The canonical domain language remains in `CONTEXT.md`. The detailed design contracts remain in:

- `docs/covalent_etl_plan.md`
- `docs/reaction_family_rule_table_schema.md`
- `docs/covalent_model_design.md`
- `docs/covalent_generation_io_contract.md`
- `docs/github-management.md`
- `docs/adr/`

## Final Module Scope

| Module | Spec | Purpose |
| --- | --- | --- |
| Shared contracts | `00-shared-contracts.md` | Cross-module schemas, enum sources, denominators, lifecycle rules, and authority boundaries |
| Data processing | `01-data-processing.md` | Three-source ETL, records, rules, edge candidates, splits, visual checks, and ETL quality report |
| Model | `02-model.md` | PMDM-compatible fixed-protein ligand diffusion extension with stepwise covalent edge prediction |
| Training | `03-training.md` | PMDM and covalent losses with explicit masks, rule consistency, and denominator reports |
| Inference | `05-inference.md` | `ReactiveSiteGenerationRequest` validation, sampling, final decode, result writing, and mmCIF export |
| Evaluation | `04-evaluation.md` | Lifecycle-aware metrics, denominator conservation, split reporting, and covalent docking protocol handling |
| Verification | `verification-matrix.md` | Evidence required before each module or gate can be considered complete |
| Interfaces | `interface-design.md` | Public Python APIs, CLI surfaces, artifact boundaries, errors, versions, and misuse guards |
| Implementation plan | `implementation-plan.md` | Development tasks, dependency order, checkpoints, acceptance criteria, and verification commands |

## Implementation Order

The implementation order is intentionally not the same as document order. Build the data foundation first, then the model path, then inference and evaluation.

```text
1. Shared contract scaffolding
2. Data processing and rule validation
3. Edge candidates, splits, visual checks, and ETL quality report
4. Model adapter and covalent heads
5. Training dataset, losses, masks, and denominator reports
6. Inference request validation, final decode, and result writing
7. Evaluation denominator accounting and docking protocol reports
8. Governance and CI fixture coverage
```

## Release Gates

### Data Release Gate

- All three sources report `complete_for_v1: true`.
- Raw manifests include version, retrieval date, license/access notes, roles, byte counts, and checksums.
- Accepted, rejected, and conflict records reconcile.
- Every accepted record has one monodentate covalent linkage and one positive covalent edge.
- Final artifact manifests include edge-candidate artifacts with checksums.
- Rule calibration sheet and rule table are present and validated.
- Visual check `fail` and `needs_rule_review` statuses block sampled records from first-core release until resolved.
- Scaffold split artifacts account for fallback reasons, and `warhead_unmatched` records are excluded from primary scaffold metrics unless manually reviewed.

### Model And Training Gate

- Model forward smoke test passes on accepted fixture records.
- Stepwise candidates are built from current noisy or generated ligand coordinates.
- Forced positives are counted separately and excluded from v1 message passing and geometry regression.
- Training logs all PMDM and covalent loss components.
- Reaction-family consistency through explicit rule masks and gates is required.
- Q2 keep-with-flag records enter training only through accepted-core gates and remain stratified in reports.
- Denominator reports include candidate, natural, forced-positive, eligible, masked, loss, message-passing, and gate-evaluated counts.

### Inference And Evaluation Gate

- Request validation fixtures cover every request error code from the IO contract.
- Request validation errors stop before sampling and stay outside generation denominators.
- Accepted request samples reconcile as `attempted_sample_count + sampling_system_failure_count`.
- Every attempted sample writes one `CovalentGenerationResult`.
- Sampling system failures are run-level artifacts, not invalid generated samples.
- Valid results export mmCIF or record export failure.
- Invalid results preserve available diagnostics and failure reasons.
- Evaluation denominator equations pass.
- Docking scores aggregate only for valid, exported, docking-eligible, successfully docked samples with complete protocol manifests.

## Current Open Decisions

The following are not blockers for writing the first implementation scaffolding, but they must be resolved before full v1 release:

- Schema validation dependency: standard-library dataclasses versus a validation library.
- Large artifact formats: `.pt`, `.npz`, parquet-style tables, or a documented combination.
- Protein chemical-state inference tool and accepted confidence policy.
- Protein-cluster split method and threshold.
- Covalent docking engine and authoritative protocol representation.
- mmCIF writer library or internal writer.
- Initial edge, bond-type, and geometry loss weights.
- Edge-score threshold calibration.

## Pull Request Expectations

Every implementation PR should state:

- Which spec section it implements.
- Which verification matrix rows are satisfied.
- Which gate, if any, remains blocked.
- Whether it touches only project-owned code or also modifies PMDM/PocketFlow baselines.
- Which local commands were run.

Default lightweight validation remains:

```bash
python -m compileall -q scripts src
```
