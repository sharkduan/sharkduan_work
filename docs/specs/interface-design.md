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
    records: tuple[SourceIngestRecord, ...],
) -> ContractEnvelope[NormalizationPayload]: ...
    """Normalize already-selected source records without identity reconciliation.

    This is a pure in-memory API for unit tests and callers that have already
    resolved duplicates/conflicts upstream.  For the pipeline seam that merges
    cross-source records and excludes linkage conflicts, use
    ``normalize_with_identity_resolution``.
    """

def normalize_with_identity_resolution(
    records: tuple[SourceIngestRecord, ...],
) -> ContractEnvelope[NormalizationPayload]: ...
    """Resolve canonical identities, merge duplicates, exclude conflicts,
    then normalize and route through quality gates."""

def build_record_index(
    processed_root: Path,
) -> ContractEnvelope[dict[str, object]]: ...
    """Build accepted, rejected, and conflict indexes from Task 9 output.

    Inputs are ``processed_root/accepted.jsonl``, ``rejected.jsonl``,
    ``conflicts.jsonl``, and ``processed_root/artifacts/{record_id}/{role}.*``.
    Outputs are ``records.jsonl``, ``rejected_index.jsonl``,
    ``conflict_index.jsonl``, and ``artifact_manifest.json``.

    Missing a required non-edge artifact role (protein_atom_table,
    ligand_atom_table, ligand_bond_table, or coordinates) is a hard
    validation failure — the envelope returns ``passed=False`` with
    structured ``ContractErrorInfo`` entries and no partial output.
    """

def build_edge_candidates(
    records_path: Path,
    candidate_radius_angstrom: float = 4.0,
) -> ContractEnvelope[dict[str, object]]: ...
    """Build per-record edge-candidate artifacts for accepted records.

    Reads ``records_path`` (a JSONL of accepted ``CovalentComplexRecord``
    rows) and writes one external artifact per record at
    ``<records_dir>/artifacts/<record_id>/edge_candidates.json``.

    Each artifact carries ``schema_version``, ``contract_version``,
    ``record_id``, ``role`` (``"edge_candidates"``), ``lineage``,
    ``positive_edge``, ``negative_edges``, ``denominators`` (10 fields),
    ``artifact_refs``, and ``empty_radius_window``.  Zero negatives is a valid
    ``empty_radius_window``, not a failure.  Missing ``coordinates``,
    protein atom-table, or ligand atom-table refs produce structured
    ``ContractErrorInfo`` entries and the envelope returns ``ok=False``.

    This function does **not** update ``records.jsonl`` or
    ``artifact_manifest.json`` — that finalization is Task 13 scope.
    """

def build_splits(
    records: "RecordIndex",
    policy: "SplitPolicy",
) -> ContractEnvelope["SplitIndex"]: ...

def finalize_record_manifests(
    records_path: Path,
) -> ContractEnvelope[dict[str, object]]: ...
    """Append edge-candidate artifact refs to every accepted record and update the
    artifact manifest.

    Reads ``records_path`` (a JSONL of accepted ``CovalentComplexRecord`` rows)
    and ``artifact_manifest.json`` from the same directory.  For every accepted
    record validates that ``artifacts/<record_id>/edge_candidates.json`` exists
    and contains valid embedded artifact refs whose checksums match the files
    they reference.

    Hard failures (no partial writes to ``records.jsonl`` or
    ``artifact_manifest.json``):

    * ``EDGE_CANDIDATE_ARTIFACT_MISSING`` — ``edge_candidates.json`` not found for a record
    * ``EDGE_CANDIDATE_ARTIFACT_DUPLICATE`` — an ``edge_candidates`` artifact ref is
      already present in the record or manifest (re-run guard)
    * ``EDGE_CANDIDATE_RECORD_ID_MISMATCH`` / ``EDGE_CANDIDATE_ROLE_INVALID`` —
      ``edge_candidates.json`` does not identify the accepted record or role it is
      linked to
    * ``EDGE_CANDIDATE_UNREADABLE`` — ``edge_candidates.json`` cannot be parsed
    * Checksum mismatches in any embedded artifact ref inside ``edge_candidates.json``
    * ``ARTIFACT_MANIFEST_OBSOLETE_UNLINKED`` — manifest contains entries for record
      ids not present in ``records.jsonl``

    On success, appends the ``edge_candidates`` ref to each record's ``artifacts``
    list and updates ``artifact_manifest.json``.  Writes are deterministic across
    repeated runs with identical inputs.  This function does **not** generate edge
    candidates, splits, visual checks, or quality reports — those are Task 12,
    Task 14, Task 15, and Task 16 scope respectively.
    """

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
# Alternative input modes:
python -m covalent_design.data.normalize --source covbinder_in_pdb --raw-root tests/fixtures/normalize
python -m covalent_design.data.normalize --ingest-index data/interim/ingest_index.json
python -m covalent_design.data.normalize --interim-root data/interim --out data/reports/normalize_summary.json
python -m covalent_design.data.build_record_index --processed-root data/processed
python -m covalent_design.candidates.cli.build_edge_candidates --records <records.jsonl> --radius 4.0
python -m covalent_design.data.cli.finalize_record_manifests --records <records.jsonl>
python -m covalent_design.data.build_splits --records data/processed/covalent_complex_records/records.jsonl
python -m covalent_design.data.write_quality_report --out data/reports/etl_quality_report.md
```

### Artifact Boundary

`records.jsonl` contains only identifiers, normalized labels, lineage, quality flags, metadata, and `ArtifactRef` entries. Task 10 writes the four required non-edge artifact roles:

- `protein_atom_table`
- `ligand_atom_table`
- `ligand_bond_table`
- `coordinates`

Missing any of these four roles is a hard validation failure. `edge_candidates`, `visual_check`, and split keys are appended by later tasks (Task 12 and beyond) and are not present in Task 10 output.

Task 13 appends the `edge_candidates` artifact role to each accepted record and to `artifact_manifest.json`. After finalization, every accepted record has exactly five artifact roles. Task 13 validates embedded artifact refs inside `edge_candidates.json` and fails hard on missing files, checksum mismatches, duplicate edge-candidate refs, and obsolete unlinked manifest entries. No partial writes occur on error.

Rejected records and conflict groups are separate indexes (`rejected_index.jsonl`, `conflict_index.jsonl`). They are not iterable as accepted `CovalentComplexRecord` values unless explicitly requested through a rejected/conflict API.

### Misuse Guards

- `build_record_id()` recalculates deterministic ids from canonical linkage identity; caller-supplied ids are verified, not trusted.
- `QualitySeverity` and CovalentInDB source-field priority are different enum types.
- Missing a required non-edge artifact role (`protein_atom_table`, `ligand_atom_table`, `ligand_bond_table`, or `coordinates`) produces a hard validation failure with structured `ContractErrorInfo` entries — accepted records must never be silently skipped.
- `empty_radius_window` is a valid negative-sampling status, not a candidate-build failure (Task 12).
- `finalize_record_manifests()` fails hard if any accepted record lacks an `edge_candidates.json` artifact, if embedded artifact ref checksums do not match, if an `edge_candidates` ref is already present (duplicate), or if `artifact_manifest.json` contains entries not linked to any accepted record. No partial writes occur on error (Task 13).
- Visual check `fail` or `needs_rule_review` blocks sampled records from first-core release until resolved (Task 15).

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
    rules: Path,
    out_csv: Path | None = None,
    out_json: Path | None = None,
) -> ContractEnvelope[dict]: ...

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

### CLI

```bash
python -m covalent_design.rules.cli.validate_rule_table --rules data/rules/reaction_family_rule_table.yml
python -m covalent_design.rules.cli.build_calibration_sheet --records <records.jsonl> --rules <rule_table.yml> [--out-csv <csv>] [--out-json <json>]
```

### Calibration Sheet Semantics

`build_calibration_sheet` generates a per-family CSV review sheet from `records.jsonl` and the rule table. The CSV has 14 columns:

- `family_id` — reaction family identifier matching the rule table.
- `sample_count` — number of accepted records for this family.
- `representative_record_ids` — JSON-serialized sorted list of record_ids.
- `target_atom_distribution` — JSON-serialized frequency of target atom names.
- `ligand_attachment_element_distribution` — JSON-serialized frequency of ligand attachment element symbols (from `core_labels.ligand_atom_element`).
- `warhead_distribution` — JSON-serialized frequency of `warhead_type` values.
- `bond_length_summary` — min/max/mean summary of bond lengths from `metadata.geometry`.
- `protein_side_angle_summary` — min/max/mean summary of protein-side angles from `metadata.geometry`.
- `ligand_side_angle_summary` — min/max/mean summary of ligand-side angles from `metadata.geometry`.
- `outlier_record_ids` — empty `[]` placeholder for manual review entries.
- `manual_decision` — empty string for manual review entries.
- `notes` — rule table notes or "No accepted samples in current dataset." for zero-sample families.
- `pending_smarts_marker` — `"pending"` when the rule table `warhead_rule_status` is `pending` or `allowed_warhead_smarts` is empty; `"calibrated"` when `warhead_rule_status` is `calibrated` with non-empty SMARTS.
- `pending_geometry_marker` — `"pending"` when any of `bond_length`, `protein_side_angle`, or `ligand_side_angle` geometry status is not `calibrated`; `"calibrated"` when all three are explicitly calibrated.

Geometry summaries read pre-computed values from `records.jsonl` entries under `metadata.geometry.{bond_length, protein_side_angle, ligand_side_angle}.value`. No 3D coordinate re-computation is performed. No `edge_candidates` files, directories, or artifact roles are generated — edge candidates are Task 12 scope.

Families with zero accepted records still produce a row with `sample_count=0`, empty distributions, and notes indicating no accepted samples. Output is byte-deterministic across repeated runs with identical inputs.

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
| Records to training core | Q0/Q1/Q2, visual gate, conflict exclusion, non-edge artifact checksums for the 4 required roles |
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
