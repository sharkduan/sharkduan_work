# Interface Design: Covalent Design Modules

## Status

Reviewed interface design based on the final development specifications.

This document defines the public interfaces between project-owned modules. It is contract-first documentation: implementation should conform to these APIs unless a later ADR or spec update changes the boundary.

## Design Principles

- `contracts` is the only public semantic layer. Modules must not duplicate enum values, lifecycle statuses, denominator equations, or failure codes.
- Cross-module values move as immutable contract objects, artifact references, and validation receipts. Avoid passing raw dictionaries, unvalidated paths, pandas dataframes, or naked tensors across module boundaries.
- CLI commands are thin wrappers around typed Python APIs. CLIs parse arguments, call public APIs, write artifacts, and map structured errors to exit codes.
- Large data moves as `ArtifactRef`, not inline arrays. The owning module controls loading into memory.
- Every generated artifact that can be consumed downstream has a manifest and a validation receipt.
- Public interfaces are additive by default. Breaking field changes, enum changes, denominator changes, lifecycle changes, or `record_id` algorithm changes require a major contract version.

## Package Boundaries

```text
src/covalent_design/
  contracts/     Shared schemas, enums, errors, validation, versions
  data/          Raw manifests, ingestion, normalization, records, splits
  rules/         Rule table loading, validation, calibration
  candidates/    Edge candidate construction and validation
  model/         PMDM adapter, covalent heads, final decode, validity gate
  training/      Dataset, batch collation, losses, masks, checkpoints
  inference/     Request validation, sampling, result writing, export
  evaluation/    Denominators, lifecycle validation, docking, reports
  io/            Structure and artifact IO helpers
  viz/           Visual inspection artifacts
```

Allowed dependency direction:

```text
contracts
  <- data, rules, candidates, io, viz
  <- model
  <- training
  <- inference
  <- evaluation
```

Important constraints:

- `data` does not depend on `model`, `training`, `inference`, or `evaluation`.
- `model` does not read raw source formats.
- `training` may call model public APIs, but `model` must not import training.
- `evaluation` reads inference artifacts and result schemas, but must not import the sampler.
- `rules` may be used by all modules, but rule schemas still live in `contracts`.

## Shared Contracts

### Core Envelope

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Generic, Literal, Mapping, Optional, Sequence, TypeVar

T = TypeVar("T")

@dataclass(frozen=True)
class ArtifactRef:
    uri: str
    sha256: str
    format: str
    schema_version: str
    role: str

@dataclass(frozen=True)
class ValidationReceipt:
    validator: str
    contract_version: str
    input_sha256: str
    passed: bool
    warnings: tuple[str, ...]
    errors: tuple["ContractErrorInfo", ...]

@dataclass(frozen=True)
class ContractEnvelope(Generic[T]):
    payload: T
    artifacts: tuple[ArtifactRef, ...]
    receipt: ValidationReceipt
    provenance: "Provenance"
```

Downstream modules should consume `ContractEnvelope[T]` or explicitly validated artifacts, not arbitrary paths.

### Errors

```python
@dataclass(frozen=True)
class ContractError(Exception):
    code: str
    owner: Literal[
        "request",
        "data",
        "rules",
        "model",
        "training",
        "inference",
        "evaluation",
        "system",
    ]
    message: str
    details: Mapping[str, object]
```

CLI exit codes:

| Code | Meaning |
| --- | --- |
| `0` | Success |
| `1` | Unclassified runtime error |
| `2` | CLI argument error |
| `10` | Schema or contract validation failed |
| `11` | Artifact missing or checksum mismatch |
| `12` | Denominator conservation failed |
| `20` | Request validation failed with `REQUEST_*` code |
| `30` | Data quality gate failed |
| `40` | Model or training contract violation |
| `50` | Sampling system failure exceeded policy |
| `60` | Docking protocol invalid or not evaluable |
| `70` | Unsupported version or incompatible artifact |

Human-readable errors go to stderr. Machine-readable errors should be written to `error.json` under `--out` or `--error-out` when provided.

### Core Types

Shared contracts define:

- `CovalentComplexRecord`
- `ReactiveSiteGenerationRequest`
- `CovalentGenerationResult`
- `ProteinAtomIdentity`
- `LigandAtomIdentity`
- `ReactionFamilyRuleRow`
- `EdgeCandidateSet`
- `EdgeDenominators`
- `EvaluationSummary`
- `DockingProtocolManifest`
- `SamplingSystemFailure`

Enums and status values must be imported from `contracts`; modules must not redeclare string literals locally.

### Versioning

Every public artifact has:

```yaml
schema_version: 1
contract_version: "1.0.0"
producer:
  package_name: covalent_design
  package_version: ""
  git_commit: ""
```

Compatibility rules:

- Patch: validation bug fixes only; no legal/illegal boundary changes.
- Minor: additive optional fields, artifact roles, warning codes, or report sections.
- Major: field rename/removal, enum deletion, denominator equation change, lifecycle semantic change, `record_id` algorithm change, or `residue_reaction_family` semantic change.
- A run may use only one `contract_version`.
- Checkpoints bind model contract version, rule table version, record bundle hash, and training code version.

## Data Processing Interfaces

### Python API

```python
def validate_raw_manifests(raw_root: Path) -> ContractEnvelope["RawSourceInventory"]: ...

def ingest_source(
    source: "SourceName",
    raw_root: Path,
    out: Path,
) -> ContractEnvelope["SourceIngestIndex"]: ...

def normalize_linkages(
    interim_root: Path,
    out_root: Path,
) -> ContractEnvelope["NormalizedLinkageIndex"]: ...

def build_record_index(
    processed_root: Path,
    rule_table: "ReactionFamilyRuleTable",
) -> ContractEnvelope["RecordIndex"]: ...

def build_edge_candidates(
    records: "RecordIndex",
    candidate_radius_angstrom: float = 4.0,
) -> ContractEnvelope["EdgeCandidateIndex"]: ...

def build_splits(
    records: "RecordIndex",
    policy: "SplitPolicy",
) -> ContractEnvelope["SplitIndex"]: ...

def finalize_record_manifests(
    records: "RecordIndex",
    candidates: "EdgeCandidateIndex",
) -> ContractEnvelope["RecordBundle"]: ...

def write_quality_report(
    bundle: "RecordBundle",
    out: Path,
) -> ContractEnvelope["EtlQualityReport"]: ...
```

### CLI

```bash
python -m covalent_design.data.validate_manifests --raw-root data/raw
python -m covalent_design.data.ingest --source covbinder_in_pdb --raw-root data/raw --out data/interim
python -m covalent_design.data.normalize --interim-root data/interim --out-root data/processed
python -m covalent_design.data.build_record_index --processed-root data/processed
python -m covalent_design.candidates.build_edge_candidates --records data/processed/covalent_complex_records/records.jsonl --radius 4.0
python -m covalent_design.data.finalize_record_manifests --records data/processed/covalent_complex_records/records.jsonl
python -m covalent_design.data.build_splits --records data/processed/covalent_complex_records/records.jsonl
python -m covalent_design.data.write_quality_report --out data/reports/etl_quality_report.md
```

### Artifact Boundary

`records.jsonl` contains only identifiers, normalized labels, lineage, quality flags, metadata, and `ArtifactRef` entries. These are external artifacts:

- `protein_atom_table`
- `ligand_atom_table`
- `ligand_bond_table`
- `coordinates`
- `edge_candidates`
- `visual_check`
- split keys

Rejected records and conflict groups are separate indexes. They are not iterable as accepted `CovalentComplexRecord` values unless explicitly requested through a rejected/conflict API.

### Misuse Guards

- `build_record_id()` recalculates deterministic ids from canonical linkage identity; caller-supplied ids are verified, not trusted.
- `QualitySeverity` and CovalentInDB source-field priority are different enum types.
- `empty_radius_window` is a valid negative-sampling status, not a candidate-build failure.
- `finalize_record_manifests()` fails if any accepted record lacks an edge-candidate artifact checksum.
- Visual check `fail` or `needs_rule_review` blocks sampled records from first-core release until resolved.

## Rules And Candidate Interfaces

```python
def load_rule_table(path: Path) -> "ReactionFamilyRuleTable": ...

def validate_rule_table(
    table: "ReactionFamilyRuleTable",
) -> ContractEnvelope["RuleValidationReport"]: ...

def resolve_rule(
    table: "ReactionFamilyRuleTable",
    residue_reaction_family: "ResidueReactionFamily",
) -> "ReactionFamilyRuleRow": ...

def build_calibration_sheet(
    records: Path,
    out: Path,
) -> ContractEnvelope["CalibrationReport"]: ...

def validate_edge_candidate_artifact(
    record: "CovalentComplexRecord",
    artifact: ArtifactRef,
) -> ValidationReceipt: ...
```

Rule validation must enforce:

- `family_id == residue_reaction_family`.
- Empty `allowed_warhead_smarts` means pending unless the row explicitly says `not_applicable`.
- Null geometry bounds require pending or disabled geometry status.
- Missing required chemical state cannot pass a hard gate.

For SMARTS and geometry, prefer discriminated contracts such as `CalibratedSmarts`, `PendingSmarts`, and `NotApplicableSmarts` instead of ambiguous `list[str] | None`.

## Model Interfaces

### Python API

```python
def build_covalent_model(
    config: "ModelConfig",
    registry: "ContractRegistry",
) -> "CovalentDiffusionModel": ...

def make_model_batch(
    records: "RecordBundle",
    batch_spec: "BatchSpec",
) -> ContractEnvelope["ModelBatch"]: ...

def forward_covalent(
    model: "CovalentDiffusionModel",
    batch: "ModelBatch",
) -> "ModelForwardOutput": ...

def decode_final_edge(
    final_state: "FinalLigandState",
    gate: "ValidityGate",
) -> "FinalDecodeResult": ...

def inspect_batch(
    records: "RecordBundle",
    record_id: "RecordId",
) -> "BatchInspectionReport": ...
```

### Public Types

```python
@dataclass(frozen=True)
class ModelBatch:
    records: tuple["RecordId", ...]
    residue_reaction_family: "TensorRef"
    target_atom_identity: tuple["ProteinAtomIdentity", ...]
    ligand_num_atom: "TensorRef"
    edge_candidates: "EdgeCandidateTensorRef"
    denominators_expected: "EdgeDenominators"

@dataclass(frozen=True)
class ModelForwardOutput:
    pmdm_outputs: Mapping[str, "TensorRef"]
    edge_logits: "TensorRef"
    bond_type_logits: "TensorRef"
    edge_prob_message_weights: "TensorRef"
    denominators_observed: "EdgeDenominators"
```

`TensorRef` may be backed by an in-memory tensor inside a run, but public module boundaries should preserve denominator metadata and provenance. Training should not bypass `ModelForwardOutput` and compute losses directly from bare logits.

### CLI

```bash
python -m covalent_design.model.inspect_batch --records data/processed/covalent_complex_records/records.jsonl --record-id <record_id>
python -m covalent_design.model.forward_smoke --config configs/covalent_model_smoke.yml
python -m covalent_design.model.export_arch_summary --config configs/covalent_model_smoke.yml --out data/reports/model_arch_summary.md
```

### Misuse Guards

- Use `candidate_radius_angstrom`, not `radius` or `pocket_radius`, for covalent edge candidates.
- Forced positives are represented explicitly and excluded from v1 message passing and geometry regression.
- Message weights are detached predicted probabilities, never ground-truth labels.
- `decode_final_edge()` returns valid or invalid; it never returns a best failed edge as a valid result.

## Training Interfaces

### Python API

```python
def prepare_dataset(
    records: "RecordBundle",
    split: "SplitName",
    policy: "TrainingDataPolicy",
) -> ContractEnvelope["TrainingDatasetIndex"]: ...

def load_training_batch(
    dataset: "TrainingDatasetIndex",
    batch_id: "BatchId",
) -> "ModelBatch": ...

def compute_losses(
    output: "ModelForwardOutput",
    batch: "ModelBatch",
    weights: "LossWeights",
) -> "LossReport": ...

def train(config: "TrainConfig") -> ContractEnvelope["TrainingRunManifest"]: ...

def validate_epoch(
    checkpoint: "CheckpointRef",
    split: "SplitName",
) -> ContractEnvelope["ValidationReport"]: ...

def report_denominators(
    run: "TrainingRunManifest",
) -> "DenominatorReport": ...
```

### Public Types

```python
@dataclass(frozen=True)
class LossReport:
    total_loss: "TensorRef"
    components: Mapping[str, "TensorRef"]
    masks: Mapping[str, "MaskAudit"]
    denominators: "EdgeDenominators"
    strata: tuple["DenominatorStratum", ...]
```

Required components:

- `pmdm_position_loss`
- `pmdm_atom_loss`
- `covalent_edge_loss`
- `covalent_bond_type_loss`
- `covalent_geometry_loss`
- optional `family_aux_loss`

### CLI

```bash
python -m covalent_design.training.prepare_dataset --records data/processed/covalent_complex_records/records.jsonl --split scaffold
python -m covalent_design.training.train --config configs/covalent_train_smoke.yml
python -m covalent_design.training.validate_epoch --checkpoint outputs/checkpoints/latest.pt --split val
python -m covalent_design.training.report_denominators --run outputs/runs/<run_id>
```

### Artifact Boundary

```text
outputs/runs/<run_id>/
  run_manifest.yml
  config.resolved.yml
  train_metrics.jsonl
  validation_metrics.jsonl
  denominator_report.yml
  checkpoints/
```

Checkpoint manifests include contract version, rule table version/hash, record bundle hash, split hash, and model config hash.

### Misuse Guards

- `TrainingDataPolicy(first_core_only=True)` is the default. Including rejected, conflict, or multi-linkage records raises `DATASET_CONTRACT_VIOLATION`.
- Q2 keep-with-flag records are eligible only through accepted-core gates and must be stratified in reports.
- Pending geometry produces zero geometry denominator, not an unbounded geometry loss.
- Training reports distinguish debug random split from primary protein-cluster and scaffold splits.

## Inference Interfaces

### Python API

```python
def validate_request(
    request: "ReactiveSiteGenerationRequest",
    rules: "ReactionFamilyRuleTable",
) -> "ValidatedRequest": ...

def generate(
    request: "ValidatedRequest",
    checkpoint: "CheckpointRef",
    out: Path,
) -> ContractEnvelope["GenerationRunManifest"]: ...

def sample_one(
    request: "ValidatedRequest",
    sampler: "Sampler",
    sample_id: int,
) -> "CovalentGenerationResult | SamplingSystemFailure": ...

def export_complexes(
    results: "GenerationResultIndex",
    output_format: Literal["mmcif", "pdb_compat"] = "mmcif",
) -> "ExportReport": ...

def summarize(
    results: "GenerationResultIndex",
) -> "GenerationRunSummary": ...
```

### Request Type

```python
@dataclass(frozen=True)
class ReactiveSiteGenerationRequest:
    request_id: str
    protein_structure_uri: str
    protein_structure_format: Literal["mmcif", "pdb"]
    target_atom_identity_request: "ProteinAtomLocator"
    residue_reaction_family: "ResidueReactionFamily"
    sample_count: int
    size_control: "LigandSizeControl | None"
    protein_chemical_state_request: "ProteinChemicalStateRequest | None"
```

`LigandSizeControl` must represent exactly one of:

- fixed `num_ligand_heavy_atoms`
- inclusive range `min_ligand_heavy_atoms` and `max_ligand_heavy_atoms`
- absent, meaning model size prior

### Result Type

```python
@dataclass(frozen=True)
class CovalentGenerationResult:
    request_id: str
    sample_id: int
    residue_reaction_family: "ResidueReactionFamily"
    target_atom_identity: "ProteinAtomIdentity"
    generation_validity_status: Literal["valid", "invalid"]
    complex_export_status: Literal["not_applicable", "exported", "failed"]
    docking_eligibility_status: Literal["not_applicable", "eligible", "not_evaluable"]
    docking_run_status: Literal["not_applicable", "not_run", "succeeded", "failed"]
    primary_failure_reason: "FailureReason | None"
    secondary_failure_reasons: tuple["FailureReason", ...]
    edge_validity_checks: tuple["EdgeValidityCheck", ...]
    artifacts: Mapping[str, ArtifactRef]
```

### CLI

```bash
python -m covalent_design.inference.validate_request --request request.yml
python -m covalent_design.inference.generate --request request.yml --checkpoint outputs/checkpoints/model.pt --out outputs/generation/<job_id>
python -m covalent_design.inference.export_complexes --results outputs/generation/<job_id>/results.jsonl
python -m covalent_design.inference.summarize --results outputs/generation/<job_id>/results.jsonl
```

### Artifact Boundary

```text
outputs/generation/<job_id>/
  request.normalized.yml
  run_manifest.yml
  results.jsonl
  sampling_system_failures.jsonl
  ligands/
  complexes/mmcif/
  complexes/pdb_optional/
  logs/
```

`generate()` returns a `GenerationRunManifest`, not `list[CovalentGenerationResult]`. Results and sampling system failures are sibling artifacts so evaluation can enforce:

```text
accepted_request_sample_count =
  attempted_sample_count + sampling_system_failure_count
```

### Misuse Guards

- Request validation failure returns `REQUEST_*` and does not create a sample result row.
- Sampling crash, OOM, timeout, or retry exhaustion creates `SamplingSystemFailure`, not an invalid generated sample.
- `predicted_warhead_type` is diagnostic only; validity gates use matched structural evidence and rule checks.
- Ligand size is decided before denoising; size mismatch is not a successful sample filter.

## Evaluation Interfaces

### Python API

```python
def load_generation_run(
    manifest: Path,
) -> ContractEnvelope["GenerationRunManifest"]: ...

def summarize_results(
    run: "GenerationRunManifest",
) -> "EvaluationSummary": ...

def check_denominators(
    summary: "EvaluationSummary",
) -> ValidationReceipt: ...

def validate_lifecycle(
    result: "CovalentGenerationResult",
) -> ValidationReceipt: ...

def run_covalent_docking(
    protocol: "DockingProtocolManifest",
    results: "GenerationResultIndex",
) -> "DockingRunReport": ...

def docking_score_eligible_results(
    results: "GenerationResultIndex",
    protocol: "DockingProtocolManifest",
) -> "DockingScoreEligibleResultIndex": ...

def report(
    summary: "EvaluationSummary",
    split: "SplitName",
    out: Path,
) -> "ReportArtifact": ...
```

### Summary Type

```python
@dataclass(frozen=True)
class EvaluationSummary:
    requested_sample_count: int
    request_validation_error_sample_count: int
    accepted_request_sample_count: int
    attempted_sample_count: int
    sampling_system_failure_count: int
    valid_generated_internal_count: int
    invalid_generated_sample_count: int
    exported_valid_complex_count: int
    valid_export_failure_count: int
    docking_evaluable_valid_sample_count: int
    valid_but_not_docking_evaluable_sample_count: int
    docking_not_run_valid_sample_count: int
    docking_failed_valid_sample_count: int
    successfully_docked_valid_sample_count: int
```

Required equations:

```text
requested = request_validation_error + accepted_request
accepted_request = attempted + sampling_system_failure
attempted = valid_internal + invalid_sample
valid_internal = exported_valid_complex + valid_export_failure
exported_valid_complex = docking_evaluable_valid + valid_but_not_docking_evaluable
docking_evaluable_valid = successfully_docked + docking_failed + docking_not_run
```

### CLI

```bash
python -m covalent_design.evaluation.summarize_results --results outputs/generation/<job_id>/results.jsonl --out outputs/eval/summary.yml
python -m covalent_design.evaluation.check_denominators --summary outputs/eval/summary.yml
python -m covalent_design.evaluation.run_covalent_docking --manifest configs/docking_protocol.yml --results outputs/generation/<job_id>/results.jsonl
python -m covalent_design.evaluation.report --summary outputs/eval/summary.yml --split scaffold --out outputs/eval/report.md
```

### Misuse Guards

- `summarize_results()` uses generation run manifest counts, result rows, and sampling failure artifacts. It must not infer requested or attempted counts from files present on disk.
- `covalent_docking_score` aggregation accepts only `DockingScoreEligibleResultIndex`, which is produced by lifecycle and protocol validation.
- QuickVina2-only output can populate `noncovalent_vina_score`, not `covalent_docking_score`.
- Invalid samples remain in validity, failure-mode, and ligand-exists denominators when applicable.

## Boundary Validation Points

| Boundary | Validation |
| --- | --- |
| Raw data to ETL | manifest schema, checksum, license/access notes |
| Source records to normalized records | canonical identity, atom mapping, monodentate filter |
| Records to training core | Q0/Q1/Q2, visual gate, conflict exclusion, artifact checksums |
| Rule table to gates | `family_id`, SMARTS status, geometry status, required chemical state |
| Records to model batch | tensor shapes, family key, edge candidate artifact, quality flags |
| Model to training loss | denominator validity, forced-positive masks, detached message weights |
| Request to inference | all `REQUEST_*` validation errors before sampling |
| Sampler to results | one result row per attempted sample; run-level system failure artifact otherwise |
| Results to evaluation | lifecycle validation and denominator equations |
| Docking to score aggregation | complete covalent protocol manifest and successful lifecycle |

## Acceptance

The interface design is accepted when:

- Every module has public Python APIs and matching CLI commands.
- Cross-module schemas live in `contracts`.
- Artifacts have references, checksums, schema versions, and validation receipts.
- Structured errors and exit codes are consistent across CLIs.
- Version compatibility rules are explicit.
- Misuse guards cover `residue_reaction_family`, pending SMARTS/geometry, forced positives, invalid samples, sampling failures, and docking score eligibility.
