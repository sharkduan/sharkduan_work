# Spec: Shared Contracts

## Objective

Define the cross-module contracts that every implementation module must use without redefining them locally. These contracts keep data processing, model code, training, inference, and evaluation aligned on the same vocabulary, record identity, lifecycle states, rule authority, artifact provenance, and denominator accounting.

Assumptions:

- Specifications are implementation prerequisites, not implementation code.
- Project-owned code lives under `src/covalent_design/`.
- PMDM and PocketFlow remain upstream baselines unless a later PR explicitly changes that boundary.
- The first release is monodentate-only and ETL-first.

Authoritative source documents:

- `CONTEXT.md`
- `docs/covalent_etl_plan.md`
- `docs/reaction_family_rule_table_schema.md`
- `docs/covalent_model_design.md`
- `docs/covalent_generation_io_contract.md`
- `docs/adr/0001-*.md` through `docs/adr/0034-*.md`

## Tech Stack

- Language: Python 3.9-compatible project-owned code.
- Scientific stack: RDKit, PyTorch, molecular structure parsers, docking tools, and CUDA environments are optional for heavyweight workflows and must not be required by lightweight CI until fixtures exist.
- Storage: JSONL indexes plus external artifact files for large arrays and tensors.
- Documentation: Markdown specs and ADRs under `docs/`.

## Commands

```bash
python -m compileall -q scripts src
python -m covalent_design.contracts.validate_specs --spec-root docs/specs
python -m covalent_design.contracts.validate_artifacts --records data/processed/covalent_complex_records/records.jsonl
```

The second and third commands are target implementation commands. They define expected interfaces before code exists.

## Project Structure

```text
docs/specs/
  00-shared-contracts.md
  01-data-processing.md
  02-model.md
  03-training.md
  04-evaluation.md
  05-inference.md
  verification-matrix.md

src/covalent_design/
  contracts/     Shared schemas, enums, failure reasons, denominator checks
  data/          ETL, normalization, records, splits, quality reports
  rules/         Rule table schema, calibration, validation, SMARTS gates
  candidates/    Radius-bounded covalent edge candidate generation
  model/         PMDM-compatible covalent model extension
  training/      Datasets, losses, masks, denominator logging
  inference/     Request validation, sampling, final decode, result writing
  evaluation/    Metrics, denominator accounting, docking protocol reports
  io/            Structure and artifact IO helpers
  viz/           Visual inspection artifact export
```

## Code Style

Use schema-first, explicit contracts. Prefer typed dataclasses or an equivalent validation layer for cross-module records.

```python
@dataclass(frozen=True)
class EdgeDenominators:
    candidate_count: int
    natural_candidate_count: int
    forced_positive_count: int
    eligible_edge_count: int
    masked_candidate_count: int
    edge_loss_denominator: int
    bond_type_loss_denominator: int
    geometry_loss_denominator: int
    message_passing_candidate_count: int
    gate_evaluated_count: int

    def validate(self) -> None:
        if self.forced_positive_count > self.candidate_count:
            raise ValueError("forced positives cannot exceed total candidates")
```

Conventions:

- `residue_reaction_family` is the canonical primary key. Do not replace it with `reaction_family`.
- In the reaction-family rule table, `family_id` is the serialized rule-table key for `residue_reaction_family`; v1 validation must require `family_id == residue_reaction_family` for every supported family.
- `record_id` is deterministic from normalized covalent linkage identity, never from source ids.
- Invalid generated samples are records with failure metadata, not missing rows.
- Empty `allowed_warhead_smarts` means pending unless explicitly marked otherwise by rule status.
- Null geometry bounds are valid only when paired with pending or disabled geometry status.

Shared enum and equation contracts are imported by reference from the authoritative design documents. Implementations must validate against the source documents below rather than create local variants.

| Contract | Required values or rules | Authority |
| --- | --- | --- |
| Quality severities | `Q0`, `Q1`, `Q2` | `docs/covalent_etl_plan.md`, ADR 0030 |
| Rule status values | `warhead_rule_status: calibrated | pending | not_applicable`; geometry status `calibrated | pending | disabled` | `docs/reaction_family_rule_table_schema.md` |
| Visual check status | `pending`, `pass`, `fail`, `needs_rule_review`; sampled `fail` blocks first training core until resolved | `docs/covalent_etl_plan.md` |
| Request validation errors | All `REQUEST_*` codes from the IO contract | `docs/covalent_generation_io_contract.md` |
| Result lifecycle statuses | `generation_validity_status`, `complex_export_status`, `docking_eligibility_status`, `docking_run_status` allowed values and constraints | `docs/covalent_generation_io_contract.md` |
| Generation/export/docking failure reasons | All failure reason codes from the IO contract | `docs/covalent_generation_io_contract.md` |
| Edge validity checks | Required check names and `pass | fail | not_applicable | not_evaluable` statuses | `docs/covalent_generation_io_contract.md` |
| Edge denominator counts | Candidate, natural, forced-positive, eligible, masked, loss, message-passing, and gate-evaluated counts | `docs/covalent_model_design.md` |
| Evaluation conservation equations | Requested, accepted, attempted, sampling failure, valid, invalid, exported, docking-evaluable, docked, failed, and not-run conservation | `docs/covalent_generation_io_contract.md` |

Evaluation accounting must include system failures that happen after request validation but before a sample result exists:

```text
requested_sample_count =
  request_validation_error_sample_count +
  accepted_request_sample_count

accepted_request_sample_count =
  attempted_sample_count +
  sampling_system_failure_count

attempted_sample_count =
  valid_generated_internal_count +
  invalid_generated_sample_count
```

Sampling system failures are run-level failures such as sampler crash, OOM, timeout, or retry exhaustion. They are not `CovalentGenerationResult` rows, but they must have a run artifact and enter evaluation denominators.

## Testing Strategy

- Contract tests validate schema, enum values, failure reason codes, and denominator equations.
- Golden fixtures cover valid records, rejected records, conflict groups, valid generated results, invalid generated results, export failures, docking failures, and request validation errors.
- Lightweight CI compiles `scripts` and `src`; heavyweight scientific tests are separate until stable fixtures and runners exist.

## Boundaries

Always:

- Preserve lineage, checksums, rule versions, and lifecycle status fields.
- Report denominators explicitly where masks, gates, splits, export, or docking can change counts.
- Keep request validation errors outside generation denominators.

Ask first:

- Adding a new data source, supported residue-reaction family, docking protocol, training objective, or generated output format.
- Changing PMDM or PocketFlow upstream baseline code.
- Changing default CI from lightweight compile/hygiene checks to heavyweight scientific workflows.

Never:

- Auto-download raw corpora in v1.
- Train on unresolved linkage conflicts, multi-linkage records, or records missing required gate state.
- Use ground-truth covalent edge labels as message-passing weights during training.
- Label QuickVina2-only scores as covalent docking scores.
- Drop invalid samples from result or evaluation denominators.

## Success Criteria

- All module specs reference this shared contract instead of duplicating cross-module semantics.
- Shared status names, failure reasons, and denominator equations are testable by fixtures.
- A future implementation can validate records, results, manifests, and reports against one contract layer.

## Open Questions

- Should schema validation use only standard-library dataclasses, or add a validation dependency?
- Which artifact formats are canonical for large arrays: `.pt`, `.npz`, parquet-style tables, or a combination?
- Which protein chemical-state inference tool and version are acceptable for v1?
- Which covalent docking engine becomes the first authoritative docking protocol?
