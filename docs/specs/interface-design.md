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

### CLI Error JSON Schema

All CLIs write a frozen error JSON schema when `--error-out <path>` is provided.
The file is written only on failure (non-zero exit); success paths do not produce
an error JSON file.  Parent directories are created automatically.

**Schema:**

```json
{
  "schema_version": "<SCHEMA_VERSION>",
  "contract_version": "<CONTRACT_VERSION>",
  "role": "cli_error",
  "ok": false,
  "exit_code": <int>,
  "error": {
    "code": "<error code>",
    "owner": "<contract owner>",
    "message": "<human-readable message>",
    "location": "<optional field or path>",
    "details": {}
  }
}
```

- `role` is always exactly `"cli_error"` — no other value is allowed.
- `ok` is always `false`.
- `exit_code` matches the process exit code (one of the CLI exit codes above).
- `error.code`, `error.owner`, and `error.message` are always present.
- `error.location` is `null` when no location is applicable.
- `error.details` defaults to `{}`.

This schema lives in `covalent_design.contracts.cli_errors` and is consumed by
all CLIs via `contract_error_to_cli_json()` and `exception_to_cli_json()`.

### `--error-out` Support

| CLI | Flag | Notes |
| --- | --- | --- |
| `validate_request` | `--error-out <path>` | Writes `cli_error` JSON on `ContractError` |
| `summarize_results` | `--error-out <path>` | Writes `cli_error` JSON on any exception |
| `check_denominators` | `--error-out <path>` | Writes `cli_error` JSON on any exception |
| `write_quality_report` | `--error-out <path>` | Writes `cli_error` JSON on receipt failure |

Other CLIs (`finalize_record_manifests`, `build_splits`, `build_edge_candidates`,
`validate_rule_table`, `build_calibration_sheet`, `export_visual_checks`,
`inspect_batch`, `forward_smoke`, `train`) do not yet support `--error-out`.

### Tasks Without CLIs

Task 31 (lifecycle reports), Task 32 (docking protocol), and Task 33 (split
metrics) are Python APIs only — no CLI entry points exist for these tasks.
Their modules (`lifecycle_reports.py`, `failure_modes.py`, `validity_metrics.py`,
`docking_protocol.py`, `split_metrics.py`, `reports.py`) must not expose `main()`
or `argparse` symbols.

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
- `SplitPolicy`
- `SplitIndex` (JSON envelope)
- `ScaffoldKeyRecord` (JSONL artifact)
- `LeakageReport` (JSON envelope)
- `FallbackAccounting` (JSON envelope)
- `ManualReviewIndex` (JSON envelope)

### Split Contracts

```python
@dataclass(frozen=True)
class SplitPolicy:
    algorithm: str                                # "leakage_aware_covalent_splits"
    algorithm_version: str                        # "1.0.0"
    random_seed: int                              # 42
    split_ratios: Mapping[str, float]             # {"train": 0.80, "val": 0.10, "test": 0.10}
```

`SplitPolicy` is serialised into `split_index.json` under the `split_policy` key. It carries algorithm provenance and randomisation controls. The default is an 80/10/10 ratio with seed 42 and algorithm `leakage_aware_covalent_splits`.

### SplitIndex

`split_index.json` is a JSON envelope (not a frozen dataclass). Its top-level keys:

- `schema_version` 鈥?`"1"`
- `contract_version` 鈥?`"1.0.0"`
- `role` 鈥?`"split_index"`
- `split_policy` 鈥?embedded `SplitPolicy` dict
- `assignment_count` 鈥?number of assignment entries
- `assignments` 鈥?list of per-record assignment objects

Each assignment entry has these required keys:

- `record_id` (str)
- `split` (str) 鈥?one of `"train"`, `"val"`, `"test"`, `"excluded"`
- `scaffold_key` (str | null)
- `protein_cluster_id` (str | null)
- `residue_reaction_family` (str)
- `fallback_reason` (str | null)
- `manual_review_status` (str | null)

### ScaffoldKeyRecord

`scaffold_keys.jsonl` contains one JSON object per record. Each object has these required fields:

```python
{
    "schema_version": str,         # "1"
    "contract_version": str,       # "1.0.0"
    "record_id": str,
    "role": str,                   # "scaffold_key"
    "algorithm": str,              # "fixture_key" (until chemistry library accepted)
    "algorithm_version": str,      # "1.0.0"
    "warhead_match": {
        "matched": bool,
        "warhead_type": str | None,
        "warhead_smarts": str | None,      # deferred until chemistry library accepted
        "removed_atom_indices": list[int]  # empty until chemistry library accepted
    },
    "scaffold_key": str | None,    # null when fallback_reason is set
    "fallback_reason": str | None  # null when scaffold_key produced successfully
}
```

`algorithm` is `"fixture_key"` until a user-accepted chemistry library (e.g. RDKit Bemis-Murcko) is available 鈥?see `docs/specs/key-design-decisions.md`.

### LeakageReport

`leakage_report.json` is a JSON envelope with these required keys:

- `schema_version` 鈥?`"1"`
- `contract_version` 鈥?`"1.0.0"`
- `role` 鈥?`"leakage_report"`
- `record_count` 鈥?total assignment count
- `train_count`, `val_count`, `test_count`, `excluded_count` 鈥?per-split record counts
- `fallback_count` 鈥?total records with a fallback reason
- `fallback_by_reason` 鈥?`{reason: count}` mapping
- `manual_review_count` 鈥?total records under manual review
- `scaffold_overlaps` 鈥?list of `{scaffold_key, overlapping_splits, record_ids}` for violated scaffolds
- `protein_cluster_overlaps` 鈥?list of `{protein_cluster_id, overlapping_splits, record_ids}` for violated clusters
- `zero_overlap` 鈥?`{"scaffold": bool, "protein_cluster": bool}` indicating whether overlaps are absent

### FallbackAccounting

`fallback_accounting.json` is a JSON envelope with these required keys:

- `schema_version` 鈥?`"1"`
- `contract_version` 鈥?`"1.0.0"`
- `role` 鈥?`"fallback_accounting"`
- `fallback_count` 鈥?total fallback records
- `fallback_by_reason` 鈥?`{reason: {"count": int, "record_ids": [str]}}` mapping

### ManualReviewIndex

`manual_review_index.json` is a JSON envelope with these required keys:

- `schema_version` 鈥?`"1"`
- `contract_version` 鈥?`"1.0.0"`
- `role` 鈥?`"manual_review_index"`
- `review_count` 鈥?number of records under review
- `reviewed_records` 鈥?list of `{record_id, split, fallback_reason, manual_review_status}`

`reviewer`, `reviewed_at` (ISO 8601), and `notes` fields are deferred until a manual review workflow is established 鈥?see `docs/specs/key-design-decisions.md`. They will be additive (minor version) additions to the `reviewed_records` entries.

`fallback_reason` values (this is the minimal v1 enum):

- `warhead_unmatched` 鈥?warhead SMARTS did not match the ligand; scaffold key could not be derived
- `missing_scaffold_input` 鈥?required core_labels fields for scaffold key derivation are absent
- `missing_protein_cluster_input` 鈥?no protein cluster identifier available in metadata
- `manual_review_override` 鈥?record was manually reviewed and the override status controls assignment

`manual_review_status` values:

- `pending` 鈥?review has not been performed
- `approved` 鈥?reviewer approved the record for primary split metrics
- `rejected` 鈥?reviewer excluded the record

`reviewer`, `reviewed_at` (ISO 8601), and `notes` fields are deferred until a manual review workflow is established. They will be added as optional fields on `reviewed_records` entries in `manual_review_index.json` (minor version change).

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
    """Ingest a single source and write source records and an ingest index.

    Writes ``source_records.jsonl`` and ``ingest_index.json`` under
    ``out``.  The output directory is compatible with
    ``normalize --interim-root`` so the documented CLI pipeline can
    be executed end-to-end.
    """

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
    validation failure 鈥?the envelope returns ``passed=False`` with
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
    ``edge_candidates_schema_version`` (local value ``"2"``), ``record_id``,
    ``role`` (``"edge_candidates"``), ``lineage``, ``positive_edge``,
    ``negative_edges``, ``denominators`` (10 fields), ``artifact_refs``, and
    ``empty_radius_window``.  The v2 ``positive_edge`` adds
    ``ligand_atom_index``, a full ``target_atom`` identity with
    ``atom_index``, and ``bond_type`` while retaining the legacy flat fields
    for compatibility.  Zero negatives is a valid ``empty_radius_window``,
    not a failure.  Missing ``coordinates``,
    protein atom-table, or ligand atom-table refs produce structured
    ``ContractErrorInfo`` entries and the envelope returns ``ok=False``.

    This function does **not** update ``records.jsonl`` or
    ``artifact_manifest.json`` 鈥?that finalization is Task 13 scope.
    """

def build_splits(
    records_path: Path,
    out_root: Path,
    policy: "SplitPolicy | None" = None,
) -> ContractEnvelope[list[dict]]: ...
    """Build leakage-aware train/val/test splits.

    Reads finalized Task 13 ``records.jsonl`` (accepted records with
    ``core_labels`` and artifact refs including ``edge_candidates``).
    Writes split artifacts under ``out_root`` without mutating
    ``records.jsonl`` or ``artifact_manifest.json``.

    Required ``core_labels`` fields: ``bond_type``, ``warhead_type``,
    ``residue_reaction_family``, ``pdb_id``.

    Optional metadata fields used when present:
      - ``protein_cluster_id`` 鈥?for protein cluster integrity enforcement
      - ``manual_review_status`` 鈥?for manual review override logic
      - ``scaffold_key`` 鈥?precomputed scaffold key (bypasses derivation)

    Output artifacts:
      - ``split_index.json`` 鈥?split assignments with per-record metadata
      - ``scaffold_keys.jsonl`` 鈥?per-record scaffold key artifacts with
        algorithm metadata, warhead evidence, and fallback reason
      - ``leakage_report.json`` 鈥?overlap diagnostics across splits with
        scaffold and protein_cluster zero-overlap flags
      - ``fallback_accounting.json`` 鈥?per-reason counts and record_ids for
        records excluded from primary split metrics
      - ``manual_review_index.json`` 鈥?records flagged for manual review
        with ``manual_review_status``

    Default ``SplitPolicy``:
      - algorithm: ``"leakage_aware_covalent_splits"``
      - algorithm_version: ``"1.0.0"``
      - random_seed: ``42``
      - split_ratios: ``{"train": 0.80, "val": 0.10, "test": 0.10}``

    Scaffold key derivation uses ``algorithm: "fixture_key"`` (metadata-based
    hashing of core_labels fields) until a user-accepted chemistry library is
    available.  Precomputed ``scaffold_key`` values from ``metadata`` are
    accepted as an override.

    Protein clustering enforces that records sharing a ``protein_cluster_id``
    reside in the same split.  Records missing ``protein_cluster_id`` receive
    fallback reason ``missing_protein_cluster_input`` and are excluded.
    Real clustering authority (sequence identity, UniProt mapping) is a
    deferred user decision.

    Core invariants:
      - Zero primary scaffold overlap across train/val/test.
      - Zero protein-cluster overlap across train/val/test.
      - accepted_record_count == train + val + test + excluded.
      - Input ``records.jsonl`` and ``artifact_manifest.json`` are never mutated.
    """

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

    * ``EDGE_CANDIDATE_ARTIFACT_MISSING`` 鈥?``edge_candidates.json`` not found for a record
    * ``EDGE_CANDIDATE_ARTIFACT_DUPLICATE`` 鈥?an ``edge_candidates`` artifact ref is
      already present in the record or manifest (re-run guard)
    * ``EDGE_CANDIDATE_RECORD_ID_MISMATCH`` / ``EDGE_CANDIDATE_ROLE_INVALID`` 鈥?      ``edge_candidates.json`` does not identify the accepted record or role it is
      linked to
    * ``EDGE_CANDIDATE_UNREADABLE`` 鈥?``edge_candidates.json`` cannot be parsed
    * Checksum mismatches in any embedded artifact ref inside ``edge_candidates.json``
    * ``ARTIFACT_MANIFEST_OBSOLETE_UNLINKED`` 鈥?manifest contains entries for record
      ids not present in ``records.jsonl``

    On success, appends the ``edge_candidates`` ref to each record's ``artifacts``
    list and updates ``artifact_manifest.json``.  Writes are deterministic across
    repeated runs with identical inputs.  This function does **not** generate edge
    candidates, splits, visual checks, or quality reports 鈥?those are Task 12,
    Task 14, Task 15, and Task 16 scope respectively.
    """

def export_visual_checks(
    records_path: Path,
    out_root: Path,
    sample_count: int | None = None,
    seed: int = 42,
) -> ContractEnvelope["VisualCheckIndex"]: ...
    """Sample accepted records and export visual inspection artifacts.

    Reads ``records_path`` (a JSONL of accepted ``CovalentComplexRecord`` rows
    with artifact refs including ``edge_candidates``).  Samples up to
    ``sample_count`` records deterministically using ``seed``.  When
    ``sample_count`` is ``None``, all accepted records are sampled.

    Writes under ``out_root``:
      - ``visual_check_index.json`` 鈥?a ``VisualCheckIndex`` envelope
      - ``artifacts/<record_id>/visual_check.json`` 鈥?one per-record
        ``VisualCheckRecord`` artifact

    Sampling is deterministic: given the same input records (sorted by
    ``record_id``), same ``sample_count``, and same ``seed``, the selected
    subset is identical across runs.

    This function does **not** generate an ETL quality report 鈥?that is
    Task 16 scope.
    """

def write_quality_report(
    processed_root: Path,
    *,
    ingest_roots: Optional[list[Path]] = None,
    splits_root: Optional[Path] = None,
    visual_checks_root: Optional[Path] = None,
    out_path: Optional[Path] = None,
) -> ContractEnvelope[dict]: ...
    """Produce the ETL quality report reconciling sources, records, candidates,
    splits, and visual checks.

    Reads ``records.jsonl``, ``rejected_index.jsonl``, and
    ``conflict_index.jsonl`` from ``processed_root``.  Discovers per-record
    ``edge_candidates.json`` artifacts under
    ``processed_root/artifacts/<record_id>/``.

    When ``ingest_roots`` is provided, reads ``ingest_index.json`` from each
    root to populate ``source_coverage`` with per-source ``complete_for_v1``,
    ``record_count``, and ``failure_count``.

    When ``splits_root`` is provided, reads ``split_index.json`` to populate
    ``split_stats`` (train/val/test/excluded/fallback counts).

    When ``visual_checks_root`` is provided, reads ``visual_check_index.json``
    to populate ``visual_check_summary`` and derive ``visual_blocked_count``
    from ``blocking_counts.blocking_first_core``.

    Writes the report JSON to ``out_path`` when provided.  Returns a
    ``ContractEnvelope`` whose payload is the full report dict and whose
    ``receipt.ok`` reflects reconciliation status.
    """
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
python -m covalent_design.data.cli.build_splits --records <records.jsonl> --policy <policy.json> --out-root <out_root>
python -m covalent_design.viz.cli.export_visual_checks --records <records.jsonl> --out-root <out_root> [--sample-count N] [--seed 42]
python -m covalent_design.data.cli.write_quality_report --processed-root <processed_root> [--ingest-roots <dir> ...] [--splits-root <dir>] [--visual-checks-root <dir>] [--out <path>]
```

### Artifact Boundary

`records.jsonl` contains only identifiers, normalized labels, lineage, quality flags, metadata, and `ArtifactRef` entries. Task 10 writes the four required non-edge artifact roles:

- `protein_atom_table`
- `ligand_atom_table`
- `ligand_bond_table`
- `coordinates`

Missing any of these four roles is a hard validation failure. `edge_candidates`, `visual_check`, and split keys are appended by later tasks (Task 12 and beyond) and are not present in Task 10 output.

Task 13 appends the `edge_candidates` artifact role to each accepted record and to `artifact_manifest.json`. After finalization, every accepted record has exactly five artifact roles. Task 13 validates embedded artifact refs inside `edge_candidates.json` and fails hard on missing files, checksum mismatches, duplicate edge-candidate refs, and obsolete unlinked manifest entries. No partial writes occur on error.

Task 14 consumes finalized Task 13 `records.jsonl` and writes separate split artifacts under `--out-root`. It must not mutate `records.jsonl` or `artifact_manifest.json`. Required input fields: `record_id`, `core_labels` (including `bond_type`, `warhead_type`, `residue_reaction_family`, `pdb_id`), and non-edge artifact refs (`protein_atom_table`, `ligand_atom_table`, `ligand_bond_table`, `coordinates`). Optional input fields: `protein_cluster_id` (used when present; records missing it fall back with `missing_protein_cluster_input`), `manual_review_status` (from metadata; used for review override logic), and `scaffold_key` (precomputed key from metadata; bypasses derivation). Output artifacts: `split_index.json` (assignments with per-record split, scaffold_key, protein_cluster_id, residue_reaction_family, fallback_reason, manual_review_status), `scaffold_keys.jsonl` (per-record scaffold key artifacts with `warhead_match` sub-object), `leakage_report.json` (overlap lists with zero_overlap flags), `fallback_accounting.json` (per-reason record_id lists), `manual_review_index.json` (reviewed records with status).

Task 15 consumes finalized Task 13 `records.jsonl` (accepted records with artifact refs including `edge_candidates`) and writes separate visual check artifacts under `--out-root`. It must not mutate `records.jsonl` or `artifact_manifest.json`. Sampling is deterministic by `record_id` sort order with a configurable `--seed` (default 42). Output artifacts: `visual_check_index.json` (index with sample policy, status counts, blocking counts, and per-record entries with artifact refs) and `artifacts/<record_id>/visual_check.json` (per-record artifacts with target atom, ligand attachment atom, covalent edge, residue-reaction family, warhead annotation, optional distance/local angles, status, and `blocking_first_core` flag). Task 15 does not generate an ETL quality report 鈥?that is Task 16 scope.

Scaffold key generation requires a user-approved chemistry implementation or library. Until one is accepted, fixtures may use precomputed scaffold keys. This is recorded as an unresolved user decision (see `docs/specs/key-design-decisions.md`).

Rejected records and conflict groups are separate indexes (`rejected_index.jsonl`, `conflict_index.jsonl`). They are not iterable as accepted `CovalentComplexRecord` values unless explicitly requested through a rejected/conflict API.

### Misuse Guards

- `build_record_id()` recalculates deterministic ids from canonical linkage identity; caller-supplied ids are verified, not trusted.
- `QualitySeverity` and CovalentInDB source-field priority are different enum types.
- Missing a required non-edge artifact role (`protein_atom_table`, `ligand_atom_table`, `ligand_bond_table`, or `coordinates`) produces a hard validation failure with structured `ContractErrorInfo` entries 鈥?accepted records must never be silently skipped.
- `empty_radius_window` is a valid negative-sampling status, not a candidate-build failure (Task 12).
- `finalize_record_manifests()` fails hard if any accepted record lacks an `edge_candidates.json` artifact, if embedded artifact ref checksums do not match, if an `edge_candidates` ref is already present (duplicate), or if `artifact_manifest.json` contains entries not linked to any accepted record. No partial writes occur on error (Task 13).
- Visual check `pending`, `fail`, and `needs_rule_review` all block sampled records from first-core release until resolved; only `pass` is non-blocking (Task 15).
- Split artifacts must not mutate `records.jsonl` or `artifact_manifest.json`; splits write separate artifacts under a dedicated output root.
- Scaffold key generation uses `algorithm: "fixture_key"` (metadata-based hashing) until a user-accepted chemistry library is available; precomputed `scaffold_key` values from `metadata` are accepted as overrides. The algorithm/library decision remains open (see `docs/specs/key-design-decisions.md`).
- Protein clustering for the primary split uses `protein_cluster_id` when present; records missing it are excluded with `missing_protein_cluster_input`. Real clustering authority (sequence identity, UniProt mapping) is a deferred user decision.
- `fallback_reason` records with `manual_review_status = "approved"` may enter primary scaffold metrics; `pending` and `rejected` records are excluded.
- `reviewer`, `reviewed_at`, and `notes` fields on manual review entries are deferred until a manual review workflow is established.

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

- `family_id` 鈥?reaction family identifier matching the rule table.
- `sample_count` 鈥?number of accepted records for this family.
- `representative_record_ids` 鈥?JSON-serialized sorted list of record_ids.
- `target_atom_distribution` 鈥?JSON-serialized frequency of target atom names.
- `ligand_attachment_element_distribution` 鈥?JSON-serialized frequency of ligand attachment element symbols (from `core_labels.ligand_atom_element`).
- `warhead_distribution` 鈥?JSON-serialized frequency of `warhead_type` values.
- `bond_length_summary` 鈥?min/max/mean summary of bond lengths from `metadata.geometry`.
- `protein_side_angle_summary` 鈥?min/max/mean summary of protein-side angles from `metadata.geometry`.
- `ligand_side_angle_summary` 鈥?min/max/mean summary of ligand-side angles from `metadata.geometry`.
- `outlier_record_ids` 鈥?empty `[]` placeholder for manual review entries.
- `manual_decision` 鈥?empty string for manual review entries.
- `notes` 鈥?rule table notes or "No accepted samples in current dataset." for zero-sample families.
- `pending_smarts_marker` 鈥?`"pending"` when the rule table `warhead_rule_status` is `pending` or `allowed_warhead_smarts` is empty; `"calibrated"` when `warhead_rule_status` is `calibrated` with non-empty SMARTS.
- `pending_geometry_marker` 鈥?`"pending"` when any of `bond_length`, `protein_side_angle`, or `ligand_side_angle` geometry status is not `calibrated`; `"calibrated"` when all three are explicitly calibrated.

Geometry summaries read pre-computed values from `records.jsonl` entries under `metadata.geometry.{bond_length, protein_side_angle, ligand_side_angle}.value`. No 3D coordinate re-computation is performed. No `edge_candidates` files, directories, or artifact roles are generated 鈥?edge candidates are Task 12 scope.

Families with zero accepted records still produce a row with `sample_count=0`, empty distributions, and notes indicating no accepted samples. Output is byte-deterministic across repeated runs with identical inputs.

## Visual Checks Interfaces

### Python API

```python
def export_visual_checks(
    records_path: Path,
    out_root: Path,
    sample_count: int | None = None,
    seed: int = 42,
) -> ContractEnvelope["VisualCheckIndex"]: ...
```

### CLI

```bash
python -m covalent_design.viz.cli.export_visual_checks --records <records.jsonl> --out-root <out_root> [--sample-count N] [--seed 42]
```

### Output Artifacts

`visual_check_index.json` (JSON envelope) written at `<out_root>/visual_check_index.json`:

- `schema_version` 鈥?`"1"`
- `contract_version` 鈥?`"1.0.0"`
- `role` 鈥?`"visual_check_index"`
- `sample_policy` 鈥?`{"sample_count": N | null, "seed": 42, "total_accepted": N}`
- `status_counts` 鈥?`{"pending": N, "pass": N, "fail": N, "needs_rule_review": N}`
- `blocking_counts` 鈥?`{"blocking_first_core": N, "non_blocking": N}`
- `records` 鈥?list of per-record index entries, each with `record_id`, `status`, `blocking_first_core`, and `artifact_ref` (an `ArtifactRef` pointing to `artifacts/<record_id>/visual_check.json`)

Per-record artifacts at `<out_root>/artifacts/<record_id>/visual_check.json`:

- `schema_version` 鈥?`"1"`
- `contract_version` 鈥?`"1.0.0"`
- `record_id` 鈥?str
- `role` 鈥?`"visual_check"`
- `target_atom` 鈥?`ProteinAtomIdentity` dict
- `ligand_attachment_atom` 鈥?`LigandAtomIdentity` dict
- `covalent_edge` 鈥?`{target_atom, ligand_atom, bond_type, bond_length}` (from `edge_candidates` positive edge)
- `residue_reaction_family` 鈥?str
- `warhead_annotation` 鈥?`{warhead_type, warhead_smarts | null}`
- `distance` 鈥?float | null (bond length in angstroms, from `metadata.geometry.bond_length.value`)
- `local_angles` 鈥?`{protein_side: float | null, ligand_side: float | null}` | null (from `metadata.geometry`)
- `status` 鈥?one of `"pending"`, `"pass"`, `"fail"`, `"needs_rule_review"`
- `blocking_first_core` 鈥?bool

### Status Values And Gate Semantics

| Status | Blocks first-core release? | Meaning |
| --- | --- | --- |
| `pending` | Yes (until reviewed) | Visual check not yet performed |
| `pass` | No | Visual inspection passed; record eligible |
| `fail` | Yes | Structural or annotation defect confirmed |
| `needs_rule_review` | Yes (until rule decision) | Rule table cannot decide; requires curator input |

`blocking_first_core` is `true` for `pending`, `fail`, and `needs_rule_review`; `false` only for `pass`.

### Optional Geometry Policy

- `distance` and `local_angles` fields are populated from `metadata.geometry` when available.
- Missing geometry values are written as `null` 鈥?this is valid output, not a failure.
- Geometry presence/absence does not affect `status` assignment. Task 15 does not infer `pass`, `fail`, or `needs_rule_review`; it reads `metadata.visual_check_status` when present and otherwise initializes sampled records as `pending`. Manual review or a later explicit review workflow is responsible for changing status values before first-core release.

### Deterministic Sampling Policy

- Records are sorted by `record_id` before sampling.
- Given identical inputs (same `records_path` content, same `sample_count`, same `seed`), the selected subset and all output files are byte-deterministic across repeated runs.
- When `sample_count` is `None`, all accepted records are included.

### Task Boundary

Task 15 does **not** generate an ETL quality report. The quality report that reconciles sources, records, candidates, splits, and visual checks is Task 16 scope. Visual check artifacts are consumed by the Task 16 report, not produced by it.

## ETL Quality Report Interfaces

### Python API

```python
def write_quality_report(
    processed_root: Path,
    *,
    ingest_roots: list[Path] | None = None,
    splits_root: Path | None = None,
    visual_checks_root: Path | None = None,
    out_path: Path | None = None,
) -> ContractEnvelope[dict]: ...
```

### CLI

```bash
python -m covalent_design.data.cli.write_quality_report \
    --processed-root <processed_root> \
    [--ingest-roots <dir> ...] \
    [--splits-root <dir>] \
    [--visual-checks-root <dir>] \
    [--out <path>]
```

`--ingest-roots` may be repeated for each source root containing `ingest_index.json`.

### Output: ETLQualityReport Schema

`write_quality_report` produces a JSON envelope with role `"quality_report"`. The payload is the report dict with the following sections:

**Top-level envelope fields:**

- `schema_version` 鈥?`"1"`
- `contract_version` 鈥?`"1.0.0"`
- `role` 鈥?`"quality_report"`

**`source_coverage`** 鈥?`{source_name: {complete_for_v1, record_count, failure_count}}` dict. Populated from each `--ingest-roots` entry's `ingest_index.json`. When an ingest root lacks `ingest_index.json`, the source is reported with `complete_for_v1: false`, `record_count: 0`, `failure_count: 0`, and `missing_ingest_index: true`. When the index file exists but is unreadable, `unreadable_ingest_index: true` is set instead.

**`reconciliation`** 鈥?dict with these keys:

- `accepted_count` 鈥?from `records.jsonl` row count
- `rejected_count` 鈥?from `rejected_index.jsonl` row count
- `conflict_count` 鈥?from `conflict_index.jsonl` row count
- `visual_blocked_count` 鈥?from `visual_check_index.json` 鈫?`blocking_counts.blocking_first_core`; records blocked from first-core release by visual check status (`pending`, `fail`, `needs_rule_review`)
- `total_accounted` 鈥?`accepted_count + rejected_count + conflict_count`
- `all_sources_complete_for_v1` 鈥?`true` when every provided source reports `complete_for_v1: true`; also `true` when no `ingest_roots` are provided
- `candidate_coverage_ok` 鈥?`true` when candidate artifact coverage matches `accepted_count`
- `split_counts_match` 鈥?`true` when provided split totals match `accepted_count`
- `visual_counts_match` 鈥?`true` when provided visual status and blocking totals are internally consistent and match `accepted_count`
- `reconciled` 鈥?`candidate_coverage_ok and split_counts_match and visual_counts_match`; incomplete source coverage is reported separately as `SOURCE_COVERAGE_INCOMPLETE`

**`family_distribution`** 鈥?`{residue_reaction_family: count}` from `core_labels.residue_reaction_family` across accepted records.

**`residue_distribution`** 鈥?`{residue_token: count}` derived by splitting `residue_reaction_family` on `"_"` and taking the first element (e.g. `CYS_Michael_addition` 鈫?`CYS`).

**`warhead_distribution`** 鈥?`{warhead_type: count}` from `core_labels.warhead_type` across accepted records.

**`linkage_quality`** 鈥?dict with:

- `bond_type_distribution` 鈥?`{bond_type: count}` from `core_labels.bond_type`
- `linkage_count_distribution` 鈥?always `{"1": accepted_count}` for monodentate-only v1

**`geometry_quality`** 鈥?dict with:

- `bond_length` 鈥?`{min, max, mean, count}` stats from `metadata.geometry.bond_length.value`
- `protein_side_angle` 鈥?`{min, max, mean, count}` stats from `metadata.geometry.protein_side_angle.value`
- `ligand_side_angle` 鈥?`{min, max, mean, count}` stats from `metadata.geometry.ligand_side_angle.value`
- `records_missing_geometry` 鈥?count of accepted records with no geometry values

Each stat is `{"min": null, "max": null, "mean": null, "count": 0}` when no values are available.

**`protein_chemical_state_quality`** 鈥?dict with:

- `explicit_state_count` 鈥?records with `metadata.protein_chemical_state == "explicit"`
- `inferred_state_count` 鈥?records with `metadata.protein_chemical_state == "inferred"`
- `records_with_inferred_state` 鈥?list of `record_id` strings for inferred-state records

**`candidate_stats`** 鈥?dict aggregated from `edge_candidates.json` artifacts:

- `total_candidates` 鈥?sum of `denominators.candidate_count` across all records
- `total_natural_candidates` 鈥?sum of `denominators.natural_candidate_count`
- `total_forced_positives` 鈥?sum of `denominators.forced_positive_count`
- `empty_radius_window_count` 鈥?count of records where `empty_radius_window: true`
- `record_count` 鈥?number of records that have a readable `edge_candidates.json`

**`split_stats`** (present when `--splits-root` is provided) 鈥?dict with:

- `train_count`, `val_count`, `test_count`, `excluded_count` 鈥?per-split assignment counts from `split_index.json`
- `fallback_count` 鈥?number of assignments with a `fallback_reason`

**`visual_check_summary`** (present when `--visual-checks-root` is provided) 鈥?dict with:

- `sampled_count` 鈥?number of records in `visual_check_index.json`
- `total_accepted` 鈥?from `sample_policy.total_accepted`
- `status_counts` 鈥?`{pending, pass, fail, needs_rule_review}` counts
- `blocking_counts` 鈥?`{blocking_first_core, non_blocking}` counts

If `rejected_index.jsonl`, `conflict_index.jsonl`, or a provided `visual_check_index.json` exists but cannot be parsed, Task 16 returns a structured data error (`REJECTED_INDEX_UNREADABLE`, `CONFLICT_INDEX_UNREADABLE`, or `VISUAL_CHECK_INDEX_UNREADABLE`) instead of silently treating the corresponding counts as zero.

**`quality_tier_distribution`** 鈥?`{quality_tier: count}` from `metadata.quality.quality_tier` across accepted records.

### Count Reconciliation Equations

```text
total_accounted = accepted_count + rejected_count + conflict_count
all_sources_complete_for_v1 = all(complete_for_v1 for every provided source)
visual_blocked_count = blocking_counts.blocking_first_core
candidate_coverage_ok = candidate_stats.record_count == accepted_count
split_counts_match = train_count + val_count + test_count + excluded_count == accepted_count  # when splits_root is provided
visual_counts_match = visual_total_accepted == accepted_count and status_total == sampled_count and blocking_total + non_blocking_total == sampled_count
reconciled = candidate_coverage_ok and split_counts_match and visual_counts_match
```

`visual_blocked_count` counts records that are blocked from first-core release by visual check status. It is derived from `visual_check_index.json` 鈫?`blocking_counts.blocking_first_core`, which is the number of sampled records whose `blocking_first_core` is `true` (status is `pending`, `fail`, or `needs_rule_review`).

Incomplete source coverage gates the all-source ETL release through `all_sources_complete_for_v1`; when it is `false`, the receipt includes a `SOURCE_COVERAGE_INCOMPLETE` structured error (`owner: "data"`). Count reconciliation failures are represented by `reconciled: false` and produce `COUNT_RECONCILIATION_FAILED`.

### Task 16 Reconciliation Clarification

`complete_for_v1` is a per-source coverage signal. It is reported as `all_sources_complete_for_v1` in the reconciliation section and may produce `SOURCE_COVERAGE_INCOMPLETE`, but it is not the count reconciliation equation itself.

Task 16 count reconciliation is explicit:

```text
total_accounted = accepted_count + rejected_count + conflict_count
candidate_coverage_ok = candidate_stats.record_count == accepted_count
split_counts_match = train_count + val_count + test_count + excluded_count == accepted_count  # when splits_root is provided
visual_counts_match = visual_total_accepted == accepted_count and status_total == sampled_count and blocking_total + non_blocking_total == sampled_count
reconciled = candidate_coverage_ok and split_counts_match and visual_counts_match
```

If any count equation fails, the receipt includes `COUNT_RECONCILIATION_FAILED`.

### Data Release Gate Relationship

The ETL quality report is the **Data Release Gate** artifact (Checkpoint A). It aggregates every ETL task output (Tasks 1鈥?6) into a single auditable JSON envelope. Before model training begins:

- All sources must report `complete_for_v1: true` 鈫?`all_sources_complete_for_v1: true`.
- `visual_blocked_count` must be zero (no sampled records blocked by `pending`, `fail`, or `needs_rule_review` status).
- `total_accounted` must be non-zero.
- The report JSON must be byte-deterministic across repeated runs with identical inputs.
- `complete_for_v1` coverage and `reconciled` count equations must both pass; neither one substitutes for the other.

The report is consumed by downstream governance checks and manual review; it does not produce model, training, or inference artifacts.

### Misuse Guards

- The report writes a single JSON file; it does not modify `records.jsonl`, `artifact_manifest.json`, `split_index.json`, or `visual_check_index.json`.
- Missing `records.jsonl` returns `receipt.ok=False` with `RECORDS_FILE_NOT_FOUND`.
- Unreadable `records.jsonl` returns `receipt.ok=False` with `RECORDS_UNREADABLE`.
- Missing `edge_candidates.json` for a record is silently skipped in `candidate_stats` (the record count reflects only records with readable artifacts).
- No model, training, or inference artifacts are generated.

## Model Interfaces

### Input Bundle

Task 17 consumes a single `records.jsonl` — the finalized Task 13 output with five artifact roles per record (`protein_atom_table`, `ligand_atom_table`, `ligand_bond_table`, `coordinates`, `edge_candidates`). The input is a plain JSONL file, not a Data Release Gate bundle. The Data Release Gate (Checkpoint A) is a governance precondition checked before Task 17 is invoked; it is not embedded in the batch constructor as a runtime check.

### Python API

```python
def make_model_batch(
    records_path: object,
    batch_spec: "BatchSpec | None" = None,
) -> ContractEnvelope["ModelBatch"]: ...
    """Convert accepted records into a typed ModelBatch.

    Reads a finalized Task 13 ``records.jsonl`` (accepted records with
    five artifact roles).  Validates every artifact for existence,
    checksum, and readability.  Builds ``BatchRecordHeader`` per record
    (with ``target_atom_identity`` resolved from ``protein_atom_table``
    artifact), aggregates ``BatchTensors`` (shapes/dtypes only — no
    tensor data), collects ``static_edge_candidates_refs`` (record_id →
    Task 12 ``edge_candidates`` ``ArtifactRef``), aggregates per-record
    ``EdgeDenominators``, and discovers ``bond_type_vocabulary`` from
    ``core_labels.bond_type`` values.

    Fails before tensor construction with structured ``ContractError`` on
    any of the 6 ``MODEL_BATCH_*`` error codes:
    - ``MODEL_BATCH_ARTIFACT_MISSING`` / ``_UNREADABLE`` / ``_CHECKSUM_MISMATCH``
    - ``MODEL_BATCH_ARTIFACT_ROLE_MISSING``
    - ``MODEL_BATCH_CONTRACT_VERSION_UNSUPPORTED``
    - ``MODEL_BATCH_REQUIRED_STATE_UNAVAILABLE``

    Task 17 does not read the rule table. Finalized records must already
    include ``metadata.chemical_state.status``; missing chemical-state
    metadata and explicit ``unavailable`` status both fail conservatively
    with ``MODEL_BATCH_REQUIRED_STATE_UNAVAILABLE``.

    Does NOT check Data Release Gate, split assignment, quality-tier
    eligibility, or visual check status — those are governance / Task 22
    concerns.  Creates no artifacts on disk (no side effects).
    """

def build_covalent_model(
    config: "ModelConfig",
    registry: "ContractRegistry",
) -> "CovalentDiffusionModel": ...

def forward_pmdm(
    *,
    batch: "ModelBatch",
    config: "ModelConfig",
    timestep: float = 0.5,
) -> "ModelForwardOutput": ...
    """Run the PMDM backbone forward pass and produce ModelForwardOutput.

    In Task 19 the fake backbone generates deterministic pure-Python
    nested-list outputs (no real PMDM, PocketFlow, torch, or RDKit).
    Task 20 fields (``edge_logits``, ``bond_type_logits``,
    ``family_logits``, ``edge_prob_message_weights``) are explicit
    ``SMOKE_PLACEHOLDER`` sentinels — not real logits, not detached
    sigmoid message weights, not covalent heads, not message passing.

    ``message_weight_source`` is set to
    ``"detached_edge_probability"`` to satisfy the public anti-leakage
    guard; Task 19 does NOT prove Task 20 message-weight provenance.
    """

def decode_final_edge(
    final_state: "FinalLigandState",
    gate: Any,
) -> "FinalDecodeResult": ...
    """Select the highest-scoring candidate that passes all gate checks.

    ``final_state`` is a dict with key ``"candidates"`` mapping to a
    list of candidate record dicts. Each candidate has ``"score"``
    (float), ``"ligand_atom"``, ``"target_atom"``, ``"bond_type"``,
    and other fields consumed by the gate.

    ``gate`` is any object with an ``evaluate(int, dict, Any) ->
    tuple[EdgeValidityCheck, ...]`` method matching the ``ValidityGate``
    protocol.

    Candidates are sorted by score descending with deterministic
    tie-breaking (original list index).  The first candidate whose
    every gate check has status ``"pass"`` becomes the selected edge,
    provided no candidate has a ``REQUIRED_GATE_STATE_UNAVAILABLE``
    blocking condition.

    Returns ``FinalDecodeResult`` with full failure diagnostics (see
    Failure Reason Priority section).
    """

def forward_covalent(
    *,
    pmdm_output: "ModelForwardOutput",
    batch: "ModelBatch",
    config: "ModelConfig",
    num_families: int | None = None,
    stepwise_candidate_batch: "StepwiseCandidateBatch | None" = None,
) -> "ModelForwardOutput": ...
    """Produce edge, bond-type, and family logits with detached message weights.

    Consumes a Task 19 ``ModelForwardOutput`` (which carries
    ``SMOKE_PLACEHOLDER`` sentinels in its covalent fields) and a
    ``ModelBatch``.  Returns a new ``ModelForwardOutput`` with real
    pure-Python tensor-like objects replacing the smoke placeholders.

    Task 20 does **not** wrap or reimplement ``forward_pmdm()`` — it is
    a separate composition step that fills in the covalent head logits
    and detached message weights after the PMDM backbone runs.

    Output tensor shapes:
    - ``edge_logits``: (B, N_candidates)
    - ``bond_type_logits``: (B, N_candidates, N_bond_types)
    - ``family_logits``: (B, N_families)
    - ``edge_prob_message_weights``: (B, N_candidates) — detached

    ``N_candidates`` comes from ``stepwise_candidate_batch.padded_shape``
    when the dynamic batch is supplied.  ``None`` remains a Task 19 static
    smoke-compatibility path only.  Task 24 must pass the dynamic batch.
    ``N_bond_types`` is read from ``BatchSpec.bond_type_vocabulary``;
    ``N_families`` is auto-detected from ``batch.records`` when
    ``num_families=None``.  v1 always includes the family auxiliary head
    (``family_logits`` is a required output).
    """

def apply_edge_message_weights(
    *,
    message_weights: object,
    source: str,
) -> object: ...
    """Validate the Task 20 message-weight boundary.

    Task 20 only accepts detached prediction probabilities as message
    weights.  It rejects label, ground-truth, target-edge, unknown
    provenance sources, and trainable message weights.  This function is
    a no-op passthrough after validation; final decode and loss behavior
    remain later-task scope.

    Allowed source: only ``"detached_edge_probability"``.
    Forbidden sources: ``"label"``, ``"ground_truth"``, ``"target_edge"``
    — rejected even when ``requires_grad == False``.
    """

class ValidityGate(abc.ABC):
    """Abstract gate that evaluates all 9 covalent edge validity checks."""

    @abc.abstractmethod
    def evaluate(
        self,
        candidate_index: int,
        candidate: dict,
        state: Any,
    ) -> tuple[EdgeValidityCheck, ...]:
        """Evaluate every gate check for one candidate.

        Returns one ``EdgeValidityCheck`` per gate check, ordered
        according to the spec gate evaluation sequence (see Failure
        Reason Priority). The first non-pass check in that sequence
        is the primary failure for this candidate.
        """
        ...

def inspect_batch(
    records_path: Path,
    record_id: str | None = None,
) -> dict: ...
    """Inspect one record (--record-id) or all records in a batch.

    Returns a deterministic JSON dict with ``schema_version``,
    ``contract_version``, ``batch_spec`` (aggregated), ``records`` (list of
    per-record reports), ``passed``, ``errors``, and ``warnings``.

    Each per-record report contains ``record_id``, ``line``, ``error``
    (null when ok), ``error_code``, ``provenance`` (nested dict with
    ``record_id``, ``residue_reaction_family``, ``quality_tier``,
    ``visual_check_status``, ``chemical_state_status``,
    ``target_atom_identity``, ``target_atom_index``,
    ``target_atom_artifact_role``, ``artifact_refs``, ``batch_index``),
    ``tensor_shapes`` (nested dict with all 9 shape fields plus dtype,
    index_dtype, coordinate_frame), ``denominators_expected`` (nested
    dict with all 10 denominator fields), ``batch_spec`` (per-record
    nested dict), and ``warnings``.

    If a record would fail batch construction, the report includes the
    error reason rather than silently skipping it.
    """
```

```python
def build_stepwise_candidates(
    *,
    protein_atoms: list[dict],
    ligand_atoms: list[dict],
    edge_candidates_artifact: dict,
    timestep_index: int,
    timestep_value: float,
    candidate_radius_angstrom: float = 4.0,
) -> "StepwiseCandidateSet": ...
    """Rebuild covalent edge candidates at one denoising timestep.

    Consumes the Task 12 static ``edge_candidates`` artifact for
    positive-label identity (``ligand_atom_index``, ``target_atom``,
    ``bond_type``) and uses current noisy/generated ligand coordinates
    from ``ligand_atoms`` to determine which ligand atoms fall within
    the candidate radius of the fixed target atom.

    The positive ligand atom is always included as a candidate:

    * When within the candidate radius it is a *natural* candidate
      (``is_forced_positive=False``).
    * When outside it is *force-included* with
      ``is_forced_positive=True``.

    Key behaviors:

    * Target atom coordinates are resolved by the shared protein-atom
      resolver: explicit ``target_atom.atom_index`` plus full identity
      cross-check first; unique-name fallback only for legacy artifacts.
      Ambiguous name-only fallback is a hard failure.
    * Natural candidates use strict distance
      ``< candidate_radius_angstrom``.
    * Forced positives increment
      ``EdgeDenominators.forced_positive_count`` and are excluded
      from ``bond_type_loss_denominator``, ``geometry_loss_denominator``,
      and ``message_passing_candidate_count``.
    * ``empty_radius_window`` is ``True`` when zero natural negative
      candidates exist (``natural_negative_count == 0``).
    * ``local_index`` is a contiguous per-timestep index starting
      from 0; it restarts on every call and has NO cross-timestep
      meaning.
    * ``ligand_atom_index`` is the stable cross-timestep identity
      used for force-inclusion checks and loss alignment.
    * Candidates are sorted positive-first, then negatives by
      distance (ascending).
    * The function is a pure in-memory computation; it creates no
      artifacts on disk.

    Task 18 does **not** implement PMDM adapter, covalent heads,
    message passing, loss masks, final decode, training, inference,
    or evaluation.
    """
```

### Task 25: Run Manifest And Checkpoint Metadata

Hash functions (``covalent_design.training.reports``):

```python
def canonical_json(value) -> str:
    """Produce deterministic sorted-key JSON with no trailing whitespace."""

def sha256_bytes(value: bytes) -> str:
    """Return ``sha256:<64 lowercase hex>`` for the given bytes."""

def sha256_file(path) -> str:
    """Return ``sha256:<64 lowercase hex>`` for the exact bytes of the file at ``path``."""

def hash_resolved_config(resolved_config) -> str:
    """Resolved config → canonical JSON (sorted keys) → SHA-256."""

def hash_rule_table(path) -> str:
    """Parse YAML at ``path`` → canonical JSON (sorted keys) → SHA-256."""

def build_training_input_hashes(
    *,
    records_path,
    split_index_path,
    rule_table_path,
    quality_report_path,
    visual_check_index_path,
    release_gate_path=None,
) -> dict:
    """Build the ``input_hashes`` dict for a training run manifest.

    Required keys: ``records_jsonl``, ``split_index``, ``rule_table``,
    ``quality_report``, ``visual_check_index``.
    Optional key: ``release_gate`` (present only when ``release_gate_path``
    is given).

    ``records_jsonl`` and ``split_index``: exact-byte SHA-256.
    ``rule_table``: parsed YAML → canonical JSON → SHA-256.
    ``quality_report``, ``visual_check_index``, ``release_gate``:
    exact-byte SHA-256.
    """

def build_training_run_manifest(
    *,
    run_id,
    resolved_config,
    records_path,
    split_index_path,
    rule_table_path,
    quality_report_path,
    visual_check_index_path,
    checkpoint_dir,
    train_metrics_uri,
    validation_metrics_uri,
    denominator_report_uri,
    release_gate_path=None,
    train_completed=False,
    epochs_completed=0,
    steps_completed=0,
    crash_recovery=None,
) -> TrainingRunManifest:
    """Build a fully-populated ``TrainingRunManifest``.

    ``training_config_resolved_hash`` is computed from ``resolved_config``
    and stored separately from ``input_hashes``.
    ``train_completed`` defaults to ``False``; ``epochs_completed`` and
    ``steps_completed`` default to ``0``; ``crash_recovery`` defaults to
    ``None``.
    """

def training_run_manifest_to_dict(manifest: TrainingRunManifest) -> dict:
    """Serialize a ``TrainingRunManifest`` to a JSON-compatible dict."""
```

Checkpoint functions (``covalent_design.training.checkpoints``):

```python
@dataclass(frozen=True)
class CheckpointMetadata:
    """Immutable checkpoint provenance with 11 fields.

    Fields: schema_version, contract_version, role, run_id, step,
    model_contract_version, rule_table_version, input_hashes,
    model_weights_uri, optimizer_state_uri, bond_type_vocabulary.
    """
    schema_version: str
    contract_version: str
    role: str
    run_id: str
    step: int
    model_contract_version: str
    rule_table_version: str
    input_hashes: dict
        # required keys: records_jsonl, split_index, rule_table,
        #   training_config_resolved, quality_report, visual_check_index
        # optional key: release_gate
    model_weights_uri: str
    optimizer_state_uri: str
    bond_type_vocabulary: tuple   # no_edge must be index 0

def checkpoint_metadata_to_dict(metadata: CheckpointMetadata) -> dict:
    """Serialize to JSON-compatible dict.
    ``bond_type_vocabulary`` is stored as a list in the dict output.
    """

def write_checkpoint_metadata(path, metadata: CheckpointMetadata) -> Path:
    """Validate metadata, write deterministic YAML, return output path.

    YAML is written using a project-owned pure-Python subset with
    sorted keys — no PyYAML dependency for writing.  Output is
    byte-deterministic across repeated calls with identical metadata.
    """

def read_checkpoint_metadata(
    path, *, expected_contract_version=CONTRACT_VERSION
) -> tuple[CheckpointMetadata, tuple[str, ...]]:
    """Read and validate checkpoint metadata from a YAML file.

    Returns ``(metadata, warnings)`` where warnings is a tuple of
    human-readable strings.

    Version compatibility:
    - Exact version match → no warnings.
    - Major version mismatch → ``ContractError`` (hard reject).
    - Minor version mismatch → loads with warning.
    - Patch version difference → silent (no warning).

    URI targets (``model_weights_uri``, ``optimizer_state_uri``) need
    not exist on disk during metadata validation.
    """

def validate_checkpoint_metadata(
    metadata: CheckpointMetadata, *,
    expected_contract_version=CONTRACT_VERSION,
) -> tuple[str, ...]:
    """Return deterministic warning/error strings (empty = valid).

    Checks: schema_version == ``"1"``, role == ``"checkpoint_manifest"``,
    non-empty run_id, non-negative step, non-empty bond_type_vocabulary
    with no duplicates, ``no_edge`` at vocabulary index 0, all 6 required
    ``input_hashes`` keys present in ``sha256:<64 lowercase hex>`` format,
    ``release_gate`` optional.

    URI targets are not checked for existence.  A major contract-version
    mismatch raises ``ContractError``; a minor mismatch returns a warning.
    """
```

**Task 25 scope:** writes metadata only — no real ``.pt`` weight contents,
optimizer state, resume logic, torch, RDKit, PMDM, PocketFlow, or Task 26
inference.  Task 24 smoke training is unchanged; Task 25 builders are
explicit public APIs and do not silently add artifact writes to
``run_smoke_train()``.

### Public Types

All types below live in `covalent_design.contracts.types` (shared across packages) or in their respective package modules. See ADR 0035 for placement rationale.

```python
@dataclass(frozen=True)
class BatchRecordHeader:
    """Provenance layer for one record in a ModelBatch."""
    record_id: str
    residue_reaction_family: str
    quality_tier: str                # "Q0" | "Q1" | "Q2"
    visual_check_status: str         # "pending" | "pass" | "fail" | "needs_rule_review"
    chemical_state_status: str       # "explicit" | "inferred" | "unavailable"
    target_atom_identity: ProteinAtomIdentity  # resolved from protein_atom_table artifact
    target_atom_index: int            # from core_labels.target_atom_index
    target_atom_artifact_role: str    # constant "protein_atom_table"
    split_assignment: str | None     # populated by Task 22, not Task 17
    fallback_reason: str | None
    artifact_refs: Mapping[str, ArtifactRef]
    batch_index: int

@dataclass(frozen=True)
class BatchTensors:
    """Computational layer — shapes and dtype metadata."""
    protein_coords_shape: tuple[int, ...]      # (B, N_prot, 3)
    ligand_coords_shape: tuple[int, ...]       # (B, N_lig, 3)
    protein_atom_types_shape: tuple[int, ...]  # (B, N_prot)
    ligand_atom_types_shape: tuple[int, ...]   # (B, N_lig)
    ligand_bonds_shape: tuple[int, ...]        # (B, N_lig, N_lig)
    edge_candidates_shape: tuple[int, ...]     # (B, N_candidates)
    positive_label_mask_shape: tuple[int, ...] # (B, N_candidates)
    candidate_to_ligand_map_shape: tuple[int, ...]
    candidate_to_protein_map_shape: tuple[int, ...]
    dtype: str = "float32"
    index_dtype: str = "int64"
    coordinate_frame: str = "original_pdb"

@dataclass(frozen=True)
class ModelBatch:
    """Typed batch — provenance + tensor metadata."""
    records: tuple[BatchRecordHeader, ...]
    tensors: BatchTensors
    static_edge_candidates_refs: Mapping[str, ArtifactRef]
    denominators_expected: EdgeDenominators
    batch_spec: BatchSpec | None = None

@dataclass(frozen=True)
class BatchSpec:
    """Configuration carried alongside every ModelBatch."""
    bond_type_vocabulary: tuple[str, ...]  # discovered from records
    max_protein_atoms: int
    max_ligand_atoms: int
    max_candidates: int
    candidate_radius_angstrom: float = 4.0
    coordinate_frame: str = "original_pdb"
    records_jsonl_hash: str | None = None

@dataclass(frozen=True)
class BatchInspectionReport:
    """Output schema for a single record from inspect_batch.

    inspect_batch() returns a batch-level dict; this type describes
    the fields present in each per-record entry of the ``records`` list.
    """
    schema_version: str
    contract_version: str
    record_id: str
    batch_index: int
    provenance: BatchRecordHeader | None
    tensor_shapes: dict[str, tuple[int, ...]] | None
    denominators_expected: EdgeDenominators | None
    batch_spec: BatchSpec | None
    warnings: tuple[str, ...]

@dataclass(frozen=True)
class ModelForwardOutput:
    """Output of one model forward pass.

    Task 19: pmdm_outputs, denominators_observed, and message_weight_source are
    populated. edge_logits, bond_type_logits, family_logits, and
    edge_prob_message_weights are SMOKE_PLACEHOLDER sentinels — not real logits,
    not detached sigmoid message weights.

    Task 20: replaces smoke placeholders with real tensors.
    """
    pmdm_outputs: Mapping[str, object]
    edge_logits: object             # SMOKE_PLACEHOLDER in Task 19; Tensor (B, N_candidates) in Task 20
    bond_type_logits: object        # SMOKE_PLACEHOLDER in Task 19; Tensor (B, N_candidates, N_bond_types) in Task 20
    family_logits: object           # SMOKE_PLACEHOLDER in Task 19; Tensor (B, N_families) in Task 20
    edge_prob_message_weights: object  # SMOKE_PLACEHOLDER in Task 19; detached Tensor (B, N_candidates) in Task 20
    message_weight_source: str      # "detached_edge_probability" — public anti-leakage guard
    denominators_observed: EdgeDenominators

@dataclass(frozen=True)
class StepwiseCandidate:
    """One edge candidate at a single denoising timestep."""
    local_index: int              # temporary, per-timestep
    ligand_atom_index: int        # stable across timesteps
    target_atom: ProteinAtomIdentity
    is_positive_label: bool
    is_forced_positive: bool      # forced-in when noise moved it outside radius
    within_radius: bool
    distance: float               # angstroms

@dataclass(frozen=True)
class StepwiseCandidateSet:
    """All edge candidates rebuilt at one denoising timestep."""
    timestep_index: int
    timestep_value: float
    candidates: tuple[StepwiseCandidate, ...]
    positive_label_ligand_atom_index: int  # from Task 12 static edge_candidates
    positive_label_target_atom: ProteinAtomIdentity
    positive_label_bond_type: str
    denominators: EdgeDenominators
    empty_radius_window: bool

@dataclass(frozen=True)
class StepwiseCandidateBatch:
    """Package-specific deterministic padded dynamic view."""
    candidate_sets: tuple[StepwiseCandidateSet, ...]
    candidate_counts: tuple[int, ...]
    padded_shape: tuple[int, int]
    denominators_observed: EdgeDenominators
```

### Tensor Shape Conventions

| Data | Shape | Dtype |
| --- | --- | --- |
| Protein coords | `(B, N_prot, 3)` | float32 |
| Ligand coords | `(B, N_lig, 3)` | float32 |
| Protein atom types | `(B, N_prot)` | int64 |
| Ligand atom types | `(B, N_lig)` | int64 |
| Ligand bonds | `(B, N_lig, N_lig)` | int64 |
| Edge logits | `(B, N_candidates)` | float32 |
| Bond type logits | `(B, N_candidates, N_bond_types)` | float32 |
| Family logits | `(B, N_families)` | float32 |
| Positive label mask | `(B, N_candidates)` | bool |

Coordinates are in angstroms in the `original_pdb` frame by default.
`N_prot`, `N_lig`, and `N_candidates` are per-batch maxima; shorter entries are padded.

### Bond-Type Vocabulary

Discovered dynamically by ``make_model_batch()`` from all ``core_labels.bond_type`` values in the input records, excluding ``"no_edge"``.  The vocabulary always has ``"no_edge"`` at index 0 followed by alphabetically sorted discovered bond types.  Stored in ``BatchSpec.bond_type_vocabulary`` as a tuple of strings.  Expected v1 vocabulary: ``("no_edge", "carbon-nitrogen", "carbon-oxygen", "carbon-sulfur", "disulfide", "phosphorus-oxygen")``.

### Static vs Dynamic Edge Candidates

- **Static edge candidates** (Task 12, artifact role `"edge_candidates"`): built once from ground-truth coordinates. Local artifact schema v2 adds ``positive_edge.ligand_atom_index``, full ``positive_edge.target_atom`` identity with ``atom_index``, and ``positive_edge.bond_type`` while retaining legacy flat fields. Task 17 validates existence and checksum and records refs in ``ModelBatch.static_edge_candidates_refs``. Task 18 later consumes per-edge contents.
- **Stepwise candidates** (Task 18, type `StepwiseCandidateSet`): rebuilt at every denoising timestep from current noisy/generated ligand coordinates. Positive label is force-included when noise moves it outside the candidate radius.
- **Stepwise candidate batches** (Task 18 package-specific type `StepwiseCandidateBatch`): deterministic padded views used by Task 20 and future Task 24 integration.

These are distinct entities and MUST NOT share an unqualified type or variable name.

### ModelConfig

```python
@dataclass(frozen=True)
class ModelConfig:
    """Frozen configuration for the PMDM adapter and covalent model.

    All fields have defaults; ``contract_version`` and ``rule_table_hash``
    are required for checkpoint provenance.  ``to_dict()`` is deterministic
    across repeated calls with identical field values.
    """
    contract_version: str = "1.0.0"
    rule_table_hash: str = ""
    fake_backbone: bool = True
    hidden_dim: int = 256
    ligand_feature_dim: int = 128
    protein_feature_dim: int = 128
    ligand_pair_feature_dim: int = 0      # 0 disables optional pair key
    protein_ligand_pair_feature_dim: int = 0  # 0 disables optional cross key
    seed: int = 42
    candidate_radius_angstrom: float = 4.0

    def to_dict(self) -> dict[str, object]: ...
```

### PMDM Adapter Output Keys

`ModelForwardOutput.pmdm_outputs` MUST contain 7 required keys and 2 optional keys.
Optional pair keys are present **only** when the corresponding config dimension is
positive (``ligand_pair_feature_dim > 0`` enables ``ligand_pair_features``;
``protein_ligand_pair_feature_dim > 0`` enables ``protein_ligand_pair_features``).
When dimensions are zero, optional keys must be absent — they must not appear as
empty tensors.

| Key | Shape | Required | Enabled by |
| --- | --- | --- | --- |
| `ligand_atom_features` | `(B, N_lig, D_lig)` | yes | always |
| `protein_atom_features` | `(B, N_prot, D_prot)` | yes | always |
| `ligand_coords_denoised` | `(B, N_lig, 3)` | yes | always |
| `ligand_pair_features` | `(B, N_lig, N_lig, D_pair)` | no | `ligand_pair_feature_dim > 0` |
| `protein_ligand_pair_features` | `(B, N_prot, N_lig, D_cross)` | no | `protein_ligand_pair_feature_dim > 0` |
| `position_loss` | scalar | yes | always |
| `atom_type_loss` | scalar | yes | always |
| `timestep` | scalar float | yes | always |
| `num_atom` | `(B,)` | yes | always |

Shape validation raises ``ContractError`` with owner ``"model"`` on:

- **Missing required key** — ``PMDM_MISSING_REQUIRED_KEY`` when a required key is absent.
- **Unknown key** — ``PMDM_UNKNOWN_KEY`` when a key not in the 9-key vocabulary is present.
- **Wrong shape** — ``PMDM_SHAPE_MISMATCH`` when a key has an unexpected shape.
- **Missing optional key** — ``PMDM_MISSING_OPTIONAL_KEY`` when optional pair features are enabled but absent.
- **Unexpected optional key** — ``PMDM_UNEXPECTED_OPTIONAL_KEY`` when optional pair features are disabled but present.

Fake backbone for smoke testing must output all required keys with correct shapes
and deterministic random values (fixed seed). It is pure Python nested lists — no
real PMDM, PocketFlow, torch, or RDKit import in Task 19.

### ModelForwardOutput (Task 19 boundary)

```python
@dataclass(frozen=True)
class ModelForwardOutput:
    pmdm_outputs: Mapping[str, object]     # validated PMDM adapter output dict
    edge_logits: object                    # SMOKE_PLACEHOLDER (Task 20)
    bond_type_logits: object               # SMOKE_PLACEHOLDER (Task 20)
    family_logits: object                  # SMOKE_PLACEHOLDER (Task 20)
    edge_prob_message_weights: object      # SMOKE_PLACEHOLDER (Task 20)
    message_weight_source: str             # "detached_edge_probability"
    denominators_observed: EdgeDenominators
```

Task 19 fields ``edge_logits``, ``bond_type_logits``, ``family_logits``, and
``edge_prob_message_weights`` are explicit ``SMOKE_PLACEHOLDER`` sentinels — not
real logits, not detached sigmoid message weights, not covalent heads, not message
passing.  Task 19 does **not** implement covalent heads, message passing, real
logits, or detached sigmoid message weights.

``message_weight_source`` is set to ``"detached_edge_probability"`` to satisfy
the public anti-leakage guard contract.  Docs must not claim Task 19 proves
Task 20 message-weight provenance.

``__post_init__`` validates ``requires_grad == False`` and
``message_weight_source`` membership in ``ALLOWED_MESSAGE_WEIGHT_SOURCES``
(see Message-Weight Anti-Leakage Guard below).

### Failure Reason Priority (Task 21)

Gate checks execute in this order for each candidate:

```
1. target_atom → 2. ligand_atom_class → 3. bond_type →
4. single_edge_representability → 5. warhead_smarts → 6. forbidden_smarts →
7. valence → 8. protonation → 9. geometry
```

The first failing check is that candidate's primary failure.

**`REQUIRED_GATE_STATE_UNAVAILABLE` is a global blocking condition.** If any evaluated candidate has a `not_evaluable` check (status `"not_evaluable"` or `failure_code == "REQUIRED_GATE_STATE_UNAVAILABLE"`), no candidate can be selected — the entire generation is invalid regardless of whether a lower-ranked candidate passes all other checks. The blocking code is `"REQUIRED_GATE_STATE_UNAVAILABLE:{check_name}"`.

`primary_failure_reason` priority chain when all candidates fail:
1. `blocking_required_state_failure` — if any candidate is not-evaluable
2. `best_candidate_first_failure` — first failure of the highest-scoring candidate
3. `"NO_COVALENT_EDGE_PREDICTED"` — sentinel when zero candidates exist

**Valid/invalid semantics:**
- **valid:** a candidate passes every applicable gate check (`pass` and `not_applicable` are non-blocking) and no candidate has `REQUIRED_GATE_STATE_UNAVAILABLE`. `primary_failure_reason` is `None`. If the top-scoring candidate fails and a lower-ranked candidate passes, `secondary_failure_reasons` preserves deduplicated first-failure codes from each skipped higher-scoring candidate.
- **invalid:** every candidate fails (or zero candidates). `primary_failure_reason` follows the priority chain above. `selected_edge` is `None`.

### FinalDecodeResult Fields

`FinalDecodeResult` is returned by `decode_final_edge()`:

| Field | Type | Description |
| --- | --- | --- |
| `generation_validity_status` | `str` | `"valid"` when a candidate passed every gate check, `"invalid"` otherwise |
| `selected_edge` | `CovalentEdge \| None` | The covalent edge of the selected candidate, or `None` |
| `primary_failure_reason` | `str \| None` | `None` for valid results; the primary failure code for invalid |
| `secondary_failure_reasons` | `tuple[str, ...]` | Deduplicated first-failure codes from skipped higher-scoring candidates; empty when none |
| `edge_validity_checks` | `tuple[EdgeValidityCheck, ...]` | One `EdgeValidityCheck` per check per evaluated candidate |
| `selected_score` | `float \| None` | The score of the selected candidate, or `None`

### Message-Weight Anti-Leakage Guard (Task 20)

`ModelForwardOutput.edge_prob_message_weights` MUST be a detached tensor (`requires_grad == False`) and `ModelForwardOutput.message_weight_source` MUST be `"detached_edge_probability"`. The source value is part of the public contract: label, ground-truth, target-edge, empty, or unknown sources are invalid even when `requires_grad == False`. The `ModelForwardOutput.__post_init__` validates this at construction time without importing PyTorch:

```python
def __post_init__(self):
    if getattr(self.edge_prob_message_weights, "requires_grad", False):
        raise ValueError("message_weights must be detached predicted probabilities")
    if self.message_weight_source != "detached_edge_probability":
        raise ValueError("message weights must come from the detached prediction path")
```

Ground-truth labels MUST NOT be assigned to `edge_prob_message_weights`. The runtime check rejects direct use of trainable logits or any tensor-like object with `requires_grad=True`; it also rejects explicit label/ground-truth provenance through `message_weight_source`. Task 20 tests must therefore include both guards: detached prediction source accepted, `requires_grad=True` rejected, and label/ground-truth/target-edge source rejected even when detached.

### MISSING GUARDS

- `make_model_batch()` fails before tensor construction on any of the 6 `MODEL_BATCH_*` errors.
- `make_model_batch()` does NOT check Data Release Gate, split assignment, quality-tier eligibility, or visual check status — those are governance / Task 22 concerns.
- `make_model_batch()` does NOT exclude Q2/visual-blocked/fallback records — that is Task 22 responsibility.
- `make_model_batch()` creates no artifacts on disk (no side effects); only builds and returns an in-memory ``ContractEnvelope[ModelBatch]``.
- Static edge candidate refs are validated for existence and checksum; their contents (positive edge identity, bond type, per-candidate metadata) are consumed later by Task 18 (stepwise candidate builder) and Task 23 (loss masks), not by the batch constructor itself.
- `decode_final_edge()` returns `FinalDecodeResult` with either a selected valid edge or full failure metadata; it never returns a best-failed-edge as valid.
- ``inspect_batch()`` returns a deterministic JSON dict: same ``records_path`` always produces byte-identical JSON output.

### CLI

```bash
python -m covalent_design.model.inspect_batch --records data/processed/covalent_complex_records/records.jsonl --record-id <record_id>
```

Task 19 ``forward_pmdm`` has no standalone CLI; it is called from tests and from
``forward_smoke`` (Task 24). Task 24 implements both smoke CLIs:

```bash
python -m covalent_design.model.forward_smoke --config configs/covalent_model_smoke.yml
python -m covalent_design.training.train --config configs/covalent_train_smoke.yml
```

### Misuse Guards

- Use `candidate_radius_angstrom`, not `radius` or `pocket_radius`, for covalent edge candidates.
- Forced positives are represented explicitly and excluded from v1 message passing and geometry regression.
- Message weights are detached predicted probabilities with `message_weight_source = "detached_edge_probability"`, never ground-truth labels.
- `decode_final_edge()` returns valid or invalid; it never returns a best failed edge as a valid result.
- Task 19 does NOT implement covalent heads, message passing, real logits, or detached sigmoid message weights — those are Task 20 scope.
- Fake backbone is pure Python deterministic smoke path; no real PMDM/PocketFlow/torch/RDKit import in Task 19.
- Shape validation covers missing required key, unknown key, and wrong shape; optional pair keys are present only when config dimensions are positive.

## Training Interfaces

### Python API

```python
def prepare_dataset(
    records_path: Path,
    split_index_path: Path,
    split_name: str,                     # "train" | "val" | "test"
    policy: "TrainingDataPolicy | None" = None,
) -> ContractEnvelope["TrainingDatasetIndex"]: ...
    """Build the training dataset index for exactly one split.

    Reads ``records.jsonl`` and ``split_index.json``, applies the exclusion
    priority chain, and returns a ``ContractEnvelope[TrainingDatasetIndex]``.

    Valid ``split_name`` values: ``"train"``, ``"val"``, ``"test"``.

    Exclusion priority chain (first matching reason wins):

    1. assigned split is another core split (``train``/``val``/``test``)
       and differs from requested split → ``not_in_this_split``
    2. assigned split is ``"excluded"`` → ``hard_excluded_by_split``
    3. ``visual_check_status != "pass"`` and
       ``policy.exclude_visual_blocked=True`` → ``excluded_visual_blocked``
    4. ``quality_tier`` outside accepted set → ``excluded_quality_tier``
    5. ``policy.first_core_only=True`` and record is multi-linkage →
       ``excluded_multi_linkage``
    6. ``policy.exclude_q2=True`` and ``quality_tier == "Q2"`` → ``excluded_q2``
    7. missing split assignment → ``missing_split_assignment``
    """

def load_training_batch(
    dataset: "TrainingDatasetIndex",
    batch_id: "BatchId",
    *,
    batch_spec: "BatchSpec | None" = None,
) -> "ContractEnvelope[ModelBatch]": ...
    """Load one deterministic singleton batch through Task 17.

    ``batch_id`` is ``"batch-<zero-based-index>"`` over the sorted
    ``TrainingDatasetIndex.records`` tuple.  The loader extracts the selected
    finalized JSONL row into a temporary same-directory JSONL file, delegates
    checksum/schema/artifact validation to Task 17 ``make_model_batch()``, and
    removes the temporary file before returning.
    """

def resolve_mask_flags(
    *,
    pending_smarts: bool = False,
    pending_geometry: bool = False,
    missing_required_chemical_state: bool = False,
    quality_tier: str = "Q1",
    exclude_q2: bool = False,
) -> "NormalizedMaskFlags": ...
    """Own the explicit normalized rule/policy flags consumed by Task 23."""

def compute_mask_audit(
    candidate_set: "StepwiseCandidateSet",
    *,
    pending_smarts: bool = False,
    pending_geometry: bool = False,
    missing_required_chemical_state: bool = False,
    quality_tier: str = "Q1",
    exclude_q2: bool = False,
) -> "MaskAudit": ...
    """Decompose a per-timestep candidate set into mask counts and eligible counts.

    ``missing_required_chemical_state`` is an explicit normalized boolean.
    This function does NOT resolve rule-table rows. Call ``resolve_mask_flags``
    at the integration boundary before projecting the flags.
    """

def build_edge_denominators(mask_audit: "MaskAudit") -> "EdgeDenominators": ...
    """Project a MaskAudit into the 10-field EdgeDenominators used by losses.

    Calls ``EdgeDenominators.validate()`` before returning; raises
    ``ContractError`` on negative counts or invalid forced-positive/message-
    passing combinations.
    """

def classify_timestep_bucket(timestep_value: float) -> str: ...
    """Classify a continuous timestep value into ``"early"``, ``"mid"``, or ``"late"``.

    Raises ``ValueError`` for out-of-range or non-finite values.
    """

def aggregate_denominator_strata(
    entries: Iterable["DenominatorStratumEntry"],
) -> tuple["DenominatorsStratum", ...]: ...
    """Sum per-timestep MaskAudit fields within each (family, bucket) group,
    derive the corresponding EdgeDenominators projection, and return tuples
    sorted by family name alphabetically, then early/mid/late within each family.
    """

def compute_losses(
    output: "ModelForwardOutput",
    *,
    model_batch: "ModelBatch",
    stepwise_candidate_batch: "StepwiseCandidateBatch",
    mask_flags: "tuple[NormalizedMaskFlags, ...]",
    weights: "LossWeights" = LossWeights(),
) -> "LossReport": ...
    """Compute all six required loss components from one forward output.

    Keyword-only parameters after ``output``:

    * ``model_batch`` — provides per-record provenance and bond-type vocabulary.
    * ``stepwise_candidate_batch`` — dynamic per-timestep candidate sets with labels.
    * ``mask_flags`` — resolved rule/policy flags that determine eligible counts.
    * ``weights`` — six-component ``LossWeights``; smoke defaults to all 1.0.

    Implements pure-Python pseudo BCE/CE losses (``_bce_with_logits``,
    ``_cross_entropy``).  ``covalent_geometry_loss`` is wired as an explicit
    ``0.0`` sentinel — not a real geometry regression implementation.
    PMDM losses are read directly from ``output.pmdm_outputs``
    (``position_loss``, ``atom_type_loss``) as produced by the fake backbone.

    Returns a ``LossReport`` with all six components, weighted total,
    aggregated ``EdgeDenominators``, ``MaskAudit``, and per-family/timestep
    strata.  Per-record denominator building and mask audit computation
    delegate to Task 23 ``build_edge_denominators()`` and
    ``compute_mask_audit()``.
    """

def train(config: "TrainConfig") -> ContractEnvelope["TrainingRunManifest"]: ...

def validate_epoch(
    checkpoint: "CheckpointRef",
    split: str,
) -> ContractEnvelope["ValidationReport"]: ...

def report_denominators(
    run: "TrainingRunManifest",
) -> "DenominatorReport": ...
```

### Public Types

```python
@dataclass(frozen=True)
class TrainingDataPolicy:
    """Per-split inclusion/exclusion policy for training dataset construction.

    Implemented in ``covalent_design.training.dataset`` and exported from
    ``covalent_design.training``.
    """
    first_core_only: bool = True
    exclude_visual_blocked: bool = True
    exclude_q2: bool = False
    accepted_quality_tiers: tuple[str, ...] = ("Q0", "Q1", "Q2")

@dataclass(frozen=True)
class TrainingRecordEntry:
    record_id: str
    residue_reaction_family: str
    quality_tier: str
    visual_check_status: str
    fallback_reason: str | None
    manual_review_status: str | None
    artifact_refs: Mapping[str, ArtifactRef]

@dataclass(frozen=True)
class ExclusionSummary:
    """Count breakdown for one split-specific dataset.

    Equations:

    - ``total_accepted == len(records.jsonl rows)``
    - ``records_in_split == len(TrainingDatasetIndex.records)``
    - ``excluded_by_policy == total_accepted - records_in_split``
    - ``sum(exclusion_reasons.values()) == excluded_by_policy``
    """
    total_accepted: int
    records_in_split: int
    excluded_by_policy: int
    exclusion_reasons: Mapping[str, int]  # reason → count

@dataclass(frozen=True)
class TrainingDatasetIndex:
    policy: Mapping[str, object]
    split_name: str
    records: tuple[TrainingRecordEntry, ...]
    excluded_summary: ExclusionSummary
    records_path: str

@dataclass(frozen=True)
class NormalizedMaskFlags:
    pending_smarts: bool = False
    pending_geometry: bool = False
    missing_required_chemical_state: bool = False
    quality_tier: str = "Q1"
    exclude_q2: bool = False

@dataclass(frozen=True)
class MaskAudit:
    """Per-timestep mask decomposition."""
    candidate_count: int
    natural_positive_count: int
    forced_positive_count: int
    natural_negative_count: int
    zero_negative_count: int
    masked_by_pending_smarts: int
    masked_by_pending_geometry: int
    masked_by_missing_chemical_state: int
    masked_by_q2_exclusion: int
    masked_by_forced_positive_exclusion: int
    edge_loss_eligible_count: int
    bond_type_loss_eligible_count: int
    geometry_loss_eligible_count: int
    message_passing_candidate_count: int
    gate_evaluated_count: int

@dataclass(frozen=True)
class DenominatorsStratum:
    residue_reaction_family: str
    timestep_bucket: str  # "early" | "mid" | "late"
    denominators: EdgeDenominators
    mask_audit: MaskAudit

@dataclass(frozen=True)
class DenominatorStratumEntry:
    """Single-timestep input for strata aggregation.

    Defined in ``covalent_design.training.denominators``, not in contracts.
    This is a package-specific frozen dataclass, not a cross-package contract type.
    """
    residue_reaction_family: str
    timestep_value: float
    mask_audit: MaskAudit

@dataclass(frozen=True)
class LossReport:
    schema_version: str
    contract_version: str
    step: int
    total_loss: float
    components: Mapping[str, float]
    denominators: EdgeDenominators | None
    mask_audit: MaskAudit | None
    strata: tuple[DenominatorsStratum, ...]

@dataclass(frozen=True)
class LossWeights:
    """Task 24 smoke defaults only; calibration is later workflow scope."""
    pmdm_position_loss: float = 1.0
    pmdm_atom_loss: float = 1.0
    covalent_edge_loss: float = 1.0
    covalent_bond_type_loss: float = 1.0
    covalent_geometry_loss: float = 1.0
    family_aux_loss: float = 1.0
```

Required `components` keys (v1, all required):

- `pmdm_position_loss`
- `pmdm_atom_loss`
- `covalent_edge_loss`
- `covalent_bond_type_loss`
- `covalent_geometry_loss`
- `family_aux_loss`

### Forced-Positive Loss Participation

| Loss | Forced positive included? |
| --- | --- |
| edge_existence_loss | yes — model must recognise positive edge even outside radius |
| bond_type_loss | no — insufficient context for bond-type classification |
| geometry_loss | no — geometry is undefined outside radius |
| message_passing | no — only radius-in candidates participate |
| gate_evaluated | yes — gate evaluates all candidates including forced |

### Pending SMARTS + Pending Geometry Interaction

When both are pending for a candidate:
- `edge_existence_loss` — NOT masked (neither SMARTS nor geometry affect it)
- `bond_type_loss` — masked by `pending_smarts`
- `geometry_loss` — masked by `pending_geometry`
- Gate `warhead_smarts` / `forbidden_smarts` — not_evaluable
- Gate `geometry` — not_evaluable

### Timestep Buckets

- `early`: t ∈ [0.8, 1.0] (high noise)
- `mid`: t ∈ [0.3, 0.8)
- `late`: t ∈ [0.0, 0.3) (low noise)

`classify_timestep_bucket()` raises `ValueError` for out-of-range values (t < 0.0 or t > 1.0) and non-finite values (NaN, inf).

### Mask Audit Field Semantics

`resolve_mask_flags()` owns the explicit normalized rule/policy input object.
`compute_mask_audit()` decomposes one `StepwiseCandidateSet` into the 15-field
`MaskAudit`; it does NOT resolve rule-table rows.

**Base counts:**

```text
TC = candidate_count
NP = natural_positive_count
FP = forced_positive_count
NN = natural_negative_count
TC == NP + FP + NN                    # conservation invariant
zero_negative_count = 1 iff NN == 0  # valid state, not an error
```

**Mask reason counts** (independent and may overlap):

```text
masked_by_pending_smarts              = NP  if pending_smarts else 0
masked_by_pending_geometry            = NP  if pending_geometry else 0
masked_by_missing_chemical_state      = NP  if missing_required_chemical_state else 0
masked_by_q2_exclusion                = TC  if exclude_q2 and quality_tier == "Q2" else 0
masked_by_forced_positive_exclusion   = FP  (always — forced positives excluded from bond/geometry/message)
```

**Eligible counts** when Q2 is not excluded:

```text
edge_loss_eligible_count         = TC
bond_type_loss_eligible_count    = 0   if pending_smarts else NP
geometry_loss_eligible_count     = 0   if pending_geometry or missing_required_chemical_state else NP
message_passing_candidate_count  = NP + NN
gate_evaluated_count             = TC
```

When `exclude_q2=True` and `quality_tier == "Q2"`:

```text
edge_loss_eligible_count = bond_type_loss_eligible_count = geometry_loss_eligible_count
  = message_passing_candidate_count = gate_evaluated_count = 0
```

**Participation rules:**

| Candidate type | edge existence | bond type | geometry | message passing | gate |
| --- | --- | --- | --- | --- | --- |
| natural positive (NP) | yes | yes (unless pending SMARTS) | yes (unless pending geometry or missing chemical state) | yes | yes |
| forced positive (FP) | yes | no | no | no | yes |
| natural negative (NN) | yes (edge existence only) | no | no | yes | yes |

**Pending SMARTS + pending geometry interaction:**

| Condition | edge_loss | bond_type_loss | geometry_loss |
| --- | --- | --- | --- |
| neither pending | included | included | included |
| pending SMARTS only | included | masked | included |
| pending geometry only | included | included | masked |
| both pending | included | masked | masked |

### Denominator Projection

`build_edge_denominators()` converts a `MaskAudit` into the 10-field `EdgeDenominators`:

```text
candidate_count               = TC
natural_candidate_count       = NP + NN
forced_positive_count         = FP
eligible_edge_count           = edge_loss_eligible_count
masked_candidate_count        = TC - edge_loss_eligible_count
edge_loss_denominator         = edge_loss_eligible_count
bond_type_loss_denominator    = bond_type_loss_eligible_count
geometry_loss_denominator     = geometry_loss_eligible_count
message_passing_candidate_count = message_passing_candidate_count (from MaskAudit)
gate_evaluated_count          = gate_evaluated_count (from MaskAudit)
```

The function calls `EdgeDenominators.validate()` before returning. The loss/message/gate denominator fields copy the matching eligible counts from the `MaskAudit`.

### Strata Aggregation

`aggregate_denominator_strata()` consumes `DenominatorStratumEntry` values and produces sorted `DenominatorsStratum` tuples:

1. Sort entries by `(residue_reaction_family, timestep_bucket)` where `timestep_bucket` is derived via `classify_timestep_bucket()`.
2. Within each `(family, bucket)` group, sum all 15 `MaskAudit` fields element-wise.
3. Derive each group's 10-field `EdgeDenominators` via `build_edge_denominators()`.
4. Sort strata: family name alphabetical ascending, then `"early"`, `"mid"`, `"late"` within each family.

`DenominatorStratumEntry` is a package-specific frozen dataclass in `covalent_design.training.denominators`, not a cross-package contract type.

### Task 23 Scope Boundaries

Task 23 implements masks and denominator reports. It does **not**:
- Compute numeric losses, run model forward, or run a training loop.
- Generate checkpoints, run manifests, or training/inference/evaluation artifacts.
- Resolve rule-table rows — all boolean flags must be resolved upstream.
- Introduce RDKit or torch dependencies.

### TrainingRunManifest

```python
@dataclass(frozen=True)
class TrainingRunManifest:
    schema_version: str
    contract_version: str
    role: str = "training_run_manifest"
    run_id: str
    training_config_resolved_hash: str          # canonical JSON → SHA-256
    input_hashes: Mapping[str, str]
        # required keys: records_jsonl, split_index, rule_table,
        #   quality_report, visual_check_index
        # optional key: release_gate
        # quality_report and visual_check_index are required exact-byte
        #   audit hashes; release_gate is an optional exact-byte audit
        #   hash.  These hashes bind provenance only; training metadata
        #   code does not re-run the Data Release Gate.
    checkpoint_dir: str
    train_metrics_uri: str
    validation_metrics_uri: str
    denominator_report_uri: str
    train_completed: bool
    epochs_completed: int
    steps_completed: int
    crash_recovery: Mapping[str, object] | None
```

### Hash Computation

Every hash uses the uniform format ``sha256:<64 lowercase hex>``.

- **Config hash**: resolved config → canonical JSON (sorted keys) → SHA-256
- **Record bundle hash**: SHA-256 of `records.jsonl` exact bytes
- **Split hash**: SHA-256 of `split_index.json` exact bytes
- **Rule table hash**: parse YAML → canonical JSON (sorted keys) → SHA-256
- **quality_report and visual_check_index**: required exact-byte audit hashes
- **release_gate**: optional exact-byte audit hash
- Audit hashes bind provenance only; training metadata code does **not** re-run the Data Release Gate

### Checkpoint Manifest

```yaml
schema_version: "1"
contract_version: "1.0.0"
role: "checkpoint_manifest"
run_id: "..."
step: 5000
model_contract_version: "1.0.0"
rule_table_version: "1.0.0"
input_hashes:
  records_jsonl: "sha256:..."
  split_index: "sha256:..."
  rule_table: "sha256:..."
  training_config_resolved: "sha256:..."
  quality_report: "sha256:..."
  visual_check_index: "sha256:..."
  release_gate: "sha256:..."          # optional
model_weights_uri: "step_5000_model.pt"
optimizer_state_uri: "step_5000_optimizer.pt"
bond_type_vocabulary: ["no_edge", "carbon-sulfur", ...]
```

``bond_type_vocabulary[0]`` must be ``"no_edge"``.  ``release_gate`` is
optional in ``input_hashes``.  The 6 required keys are:
``records_jsonl``, ``split_index``, ``rule_table``,
``training_config_resolved``, ``quality_report``, ``visual_check_index``.

Checkpoint YAML is written using a project-owned pure-Python subset
(sorted keys, no PyYAML dependency for writing); output is
byte-deterministic across repeated calls with identical metadata.
URI targets (``model_weights_uri``, ``optimizer_state_uri``) need not
exist on disk during metadata validation.

Cross-version compatibility:
- Exact version match → no warnings.
- Major version mismatch → hard reject (``ContractError``).
- Minor version mismatch → warn, but load.
- Patch version difference → silent (no warning).

### Training CLI

Task 24 smoke CLIs (implemented):

```bash
python -m covalent_design.model.forward_smoke --config configs/covalent_model_smoke.yml
python -m covalent_design.training.train --config configs/covalent_train_smoke.yml
```

``forward_smoke`` runs the PMDM + covalent forward pipeline against the smoke
bundle and prints a deterministic JSON shape summary. ``train`` executes one
smoke training step: loads four deterministic singleton microbatches
(``batch_size=4``, one record each via Task 22 ``load_training_batch``), runs
``forward_pmdm`` + ``forward_covalent`` per microbatch, computes losses via
``compute_losses()``, aggregates into one step-level ``LossReport``, and
writes exactly one ``train_metrics.jsonl`` row.

Future training CLI (Task 25+):

```bash
python -m covalent_design.training.validate_epoch --checkpoint outputs/checkpoints/latest.pt --split val
python -m covalent_design.training.report_denominators --run outputs/runs/<run_id>
```

### Artifact Boundary

```text
outputs/runs/<run_id>/
  run_manifest.yml
  config.resolved.yml
  train_metrics.jsonl          # one LossReport.to_dict() per line
  validation_metrics.jsonl
  denominator_report.yml
  checkpoints/
    step_5000_checkpoint.yml
    step_5000_model.pt
    step_5000_optimizer.pt
```

### Misuse Guards

- `TrainingDataPolicy(first_core_only=True)` is the default. Rejected and
  conflict records must not appear in finalized accepted input; multi-linkage
  records are excluded with `excluded_multi_linkage`.
- Q2 keep-with-flag records are eligible only through accepted-core gates and must be stratified in reports.
- Pending geometry produces zero geometry denominator, not an unbounded geometry loss.
- Training reports distinguish debug random split from primary protein-cluster and scaffold splits.
- `LossReport` serialises via `.to_dict()` for JSONL output; `components` keys are validated at construction.

### Task 22 Scope Boundaries

Task 22 is the dataset preparation and batch-loader boundary. It does **not**:

- Compute Task 23 masks or denominators.
- Compute Task 24 losses.
- Run model forward or a training loop.
- Generate model, training, inference, or evaluation artifacts.

``load_training_batch()`` implements deterministic singleton loading and
delegates validation and construction to Task 17 ``make_model_batch()``. It
does not duplicate model-batch construction logic.

## Inference Interfaces

### Request File Format

YAML (`.yml` / `.yaml`) is the authoritative human-authored format.
JSON is accepted for programmatically-generated requests.  The CLI auto-detects
format from the file extension.  Unknown extensions and malformed content map to
`REQUEST_STRUCTURE_UNREADABLE`.

`write_normalized_request(validated, path)` produces deterministic UTF-8 YAML
from a `ValidatedRequest`.  It is a public API callable by Task 27, not an
implicit side effect of Task 26 validation.

### Request Validation Error Codes

Exactly 13 `REQUEST_*` error codes are defined in
`covalent_design.contracts.types.REQUEST_VALIDATION_ERROR_CODES`:

```text
REQUEST_STRUCTURE_UNREADABLE          — unknown extension, malformed file, structure I/O error, no ATOM/HETATM records
REQUEST_TARGET_RESIDUE_NOT_FOUND      — residue not found in structure
REQUEST_TARGET_RESIDUE_AMBIGUOUS      — multiple distinct chain+residue matches
REQUEST_TARGET_ATOM_NOT_FOUND         — target atom name not found; also used for nonexistent altloc override
REQUEST_RESIDUE_NAME_MISMATCH         — request residue name != structure residue name
REQUEST_FAMILY_UNSUPPORTED            — reaction family not in rule table
REQUEST_RESIDUE_FAMILY_CONFLICT       — family expects different residue
REQUEST_ATOM_FAMILY_CONFLICT          — family expects different target atom
REQUEST_SAMPLE_COUNT_INVALID          — non-positive or non-integer sample_count
REQUEST_LIGAND_SIZE_INVALID           — fixed size non-positive or non-integer
REQUEST_LIGAND_SIZE_RANGE_INVALID     — range bounds invalid (non-positive, non-integer, min > max)
REQUEST_LIGAND_SIZE_CONFLICT          — both fixed and range fields set
REQUEST_REQUIRED_CHEMICAL_STATE_UNAVAILABLE  — family requires chemical state, not provided
```

Each raises `ContractError(owner="request", code=...)`.  Request validation
failure is a request contract error, not an invalid generated sample.

### Python API

```python
# request_validation.py (Task 26)
def load_request_file(path: Path) -> ReactiveSiteGenerationRequest: ...
    """Parse YAML (authoritative) or JSON (accepted).  Raises
    ContractError(owner="request", code="REQUEST_STRUCTURE_UNREADABLE")
    on unknown extension or malformed content."""

def validate_request(
    request: ReactiveSiteGenerationRequest,
    rules: ReactionFamilyRuleTable,
    *,
    request_base_dir: str | None = None,
) -> ValidatedRequest: ...
    """Validate against rule table.  Returns ValidatedRequest on success.
    Raises ContractError(owner="request", code=...) on failure."""

def validate_request_file(
    path: Path,
    *,
    rules_path: Path | None = None,
) -> ValidatedRequest: ...
    """Load + validate in one call.  Default rule table:
    data/rules/reaction_family_rule_table.yml (auto-discovered from repo root)."""

def normalized_request_yaml(validated: ValidatedRequest) -> str: ...
    """Deterministic canonical YAML string (pure Python)."""

def write_normalized_request(validated: ValidatedRequest, path: Path) -> Path: ...
    """Write deterministic UTF-8 YAML file; creates parent directories."""

# --- Task 27 (implemented) ---

@dataclass(frozen=True)
class SamplingPolicy:
    """Retry policy for generation sampling.

    Both fields are required explicitly.  Retry defaults remain deliberately
    unfrozen.  ``retry_exhausted`` is an emitted terminal sentinel and cannot
    be configured as a retry trigger.
    """
    max_retries: int
    retry_on_categories: tuple[str, ...]

def generate(
    request: ValidatedRequest,
    policy: SamplingPolicy,
    *,
    output_dir: Path,
    job_id: str,
    sampler,
    result_sink,
    checkpoint_ref: ArtifactRef | None = None,
    checkpoint_loader = None,
    clock = None,
    traceback_normalizer = None,
) -> ContractEnvelope[GenerationRunManifest]: ...
    """Run generation for an accepted request.

    Writes ``request.normalized.yml`` before checkpoint loading, then
    samples each accepted sample_id.  ``sampler``, ``result_sink``,
    ``checkpoint_loader``, ``clock``, and ``traceback_normalizer`` are
    injectable boundaries — no real PMDM, PocketFlow, torch, RDKit,
    Task 29 export, or Task 30 evaluation implementation lives here.

    ``result_sink`` is the Task 28 ``ResultWriter.write()`` callable
    injected through ``generate(result_sink=writer.write)``.
    """

def export_complexes(
    results: "GenerationResultIndex",
    output_format: Literal["mmcif", "pdb_compat"] = "mmcif",
) -> "ExportReport": ...
```

### Request Schema Types

```python
@dataclass(frozen=True)
class ProteinAtomLocator:
    """Locator describing the target protein atom in structural terms."""
    chain_id: str | None
    residue_number: int | None
    residue_name: str
    atom_name: str
    insertion_code: str | None = None
    structure_model: int | None = None
    asym_id: str | None = None

@dataclass(frozen=True)
class LigandSizeControl:
    """Fixed or range ligand-size constraints.  Exactly one mode must be set."""
    num_ligand_heavy_atoms: int | None = None
    min_ligand_heavy_atoms: int | None = None
    max_ligand_heavy_atoms: int | None = None

@dataclass(frozen=True)
class ProteinChemicalStateRequest:
    """User-supplied or tool-inferred chemical state of the target atom."""
    target_atom_formal_charge: int | None = None
    target_atom_protonation_state: str | None = None
    target_atom_hydrogen_state: str | None = None
    protein_preparation_policy: str | None = None
    chemical_state_source: str | None = None
    chemical_state_tool_name: str | None = None
    chemical_state_tool_version: str | None = None
    chemical_state_confidence: str | None = None

@dataclass(frozen=True)
class ReactiveSiteGenerationRequest:
    """A complete reactive-site generation request."""
    request_id: str
    protein_structure_uri: str
    protein_structure_format: str               # "pdb" or "mmcif"
    target_atom_identity_request: ProteinAtomLocator
    residue_reaction_family: str
    sample_count: int
    size_control: LigandSizeControl | None = None
    protein_chemical_state_request: ProteinChemicalStateRequest | None = None
    target_altloc: str | None = None

@dataclass(frozen=True)
class ValidatedRequest:
    """A validated request with resolved atom identity and altloc."""
    request: ReactiveSiteGenerationRequest
    resolved_target_atom_identity: ProteinAtomIdentity
    resolved_target_altloc: str | None
    rule_table_version: int
```

`LigandSizeControl` must represent exactly one of:

- fixed (`num_ligand_heavy_atoms` set, min/max both None)
- inclusive range (`min_ligand_heavy_atoms` and `max_ligand_heavy_atoms` set, num None)
- absent (all fields None), meaning model size prior

Conflicting modes → `REQUEST_LIGAND_SIZE_CONFLICT`.  Non-integer values in
integer fields → deterministic error codes (`REQUEST_LIGAND_SIZE_INVALID` or
`REQUEST_LIGAND_SIZE_RANGE_INVALID`).

### Alternate-Location Atom Policy

When the target atom has multiple altloc conformations:
1. If `target_altloc` is specified in the request → use that altloc; fail with
   `REQUEST_TARGET_ATOM_NOT_FOUND` if not present.
2. If not specified → select highest occupancy altloc; if occupancy data
   unavailable or tied, select `altloc='A'`.
3. Single-conformer structures (blank altloc for all matching atoms) resolve
   `resolved_target_altloc` to `None`.
4. Resolved altloc recorded in `ValidatedRequest.resolved_target_altloc`.

### Result Type

The full `CovalentGenerationResult` is defined in `covalent_design.contracts.types`.
Key fields include the four lifecycle statuses, `primary_failure_reason`,
`secondary_failure_reasons`, `generated_ligand_status`, `predicted_ligand_attachment_atom`,
`predicted_covalent_edge`, `covalent_edge_score`, `geometry_metrics`,
`molecular_quality_metrics`, `matched_warhead_type`, `predicted_warhead_type`,
`covalent_docking_score`, `noncovalent_vina_score`, `edge_validity_checks`, and `artifacts`.

### SamplingSystemFailure

```python
@dataclass(frozen=True)
class SamplingSystemFailure:
    request_id: str
    sample_id: int
    failure_category: str    # crash | oom | timeout | retry_exhausted |
                             # checkpoint_load_failed | sampler_invariant_violation
    failure_timestamp: str   # ISO 8601
    traceback_hash: str      # SHA-256 of normalised traceback
    log_uri: str
    retry_count: int
    resource_snapshot: Mapping[str, object] | None
    message: str
```

### GenerationRunManifest

```python
@dataclass(frozen=True)
class GenerationRunManifest:
    schema_version: str
    contract_version: str
    role: str = "generation_run_manifest"
    job_id: str
    request_id: str
    checkpoint_ref: ArtifactRef | None
    accepted_request_sample_count: int
    attempted_sample_count: int
    sampling_system_failure_count: int  # deduplicated by sample_id
    result_count: int
    artifacts: Mapping[str, ArtifactRef]
        # keys: request, results, sampling_system_failures
```

``checkpoint_ref`` uses ``ArtifactRef | None`` (not a separate ``CheckpointRef``
type).  All artifact refs use relative URIs and exact-byte SHA-256 with
``format``, ``schema_version``, ``role``, and ``bytes`` fields.  Artifacts
mapping keys are ``request``, ``results``, and ``sampling_system_failures``.

### Sampling Policy And Accounting

``SamplingPolicy`` is a frozen dataclass with two required fields:

- ``max_retries: int`` — maximum retry attempts per sample_id.
- ``retry_on_categories: tuple[str, ...]`` — failure categories that trigger a
  retry.  ``retry_exhausted`` is an emitted terminal sentinel and cannot be
  configured as a retry trigger.

Retry defaults remain deliberately unfrozen.

Accounting is at sample_id granularity:

- ``accepted_request_sample_count = attempted_sample_count + sampling_system_failure_count``
- Retried attempts do not change the denominator.
- Every intermediate failure attempt row remains in
  ``sampling_system_failures.jsonl`` (with ``retry_count`` = 0, 1, ...).
- A fully exhausted sample adds an extra ``retry_exhausted`` terminal sentinel
  row, but ``sampling_system_failure_count`` counts that failed sample once.
- ``checkpoint_load_failed`` rows are emitted per accepted sample id.

### mmCIF Export (Task 29 - implemented)

Writer boundary: project-owned pure-Python mmCIF writer and immutable export adapters. RDKit may be used later as an optional backend only after the exact API is source-verified; default CI uses the project-owned writer and does not require RDKit. Source-verification status (2026-06-02): the official RDKit `rdkit.Chem.rdmolfiles` API reference (`https://rdkit.org/docs/source/rdkit.Chem.rdmolfiles.html`) was re-checked and no `MolToMMCIFBlock` symbol was found. RDKit remains an optional future backend requiring source verification.

```python
def write_covalent_complex(
    result: CovalentGenerationResult,
    protein_atom_table: ArtifactRef,
    ligand_coords: object,         # (N_lig, 3)
    ligand_atom_types: object,     # (N_lig,)
    ligand_bonds: object,          # (N_lig, N_lig)
    covalent_edge: CovalentEdge,
    out_path: Path,
    *,
    artifact_root: Path,
) -> ArtifactRef:
    """Export a valid covalent complex as deterministic mmCIF.

    Input protein table is ``ArtifactRef`` JSON with explicit
    keyword-only ``artifact_root``; no cwd guessing.  Input and output
    paths reject absolute, traversing, and root-escaping boundaries.

    Writes ``_entry.id``, ``_atom_site.*`` (protein ``ATOM`` + ligand
    ``HETATM``), and exactly one ``_struct_conn.*`` row with
    ``conn_type_id = covale``.

    Ligand identity is deterministic: element-local names (``C1``,
    ``C2``, ``N1``), ``label_asym_id=L``, ``label_seq_id=1``,
    ``label_comp_id=LIG``, entity id ``2``.

    Returns ``ArtifactRef`` with ``role=complex_mmcif``,
    ``format=mmcif``, root-relative URI, exact bytes, and sha256.

    Raises ``ContractError(code="COMPLEX_EXPORT_FAILED",
    owner="inference")`` on validation, read, or write failure.
    """

def export_covalent_complex_result(
    result: CovalentGenerationResult,
    protein_atom_table: ArtifactRef,
    ligand_coords: object,
    ligand_atom_types: object,
    ligand_bonds: object,
    covalent_edge: CovalentEdge,
    out_path: Path,
    *,
    artifact_root: Path,
) -> CovalentGenerationResult:
    """Write the mmCIF complex; return updated result with success statuses.

    Immutable ``dataclasses.replace()`` update:
    - ``complex_export_status`` = ``"exported"``
    - ``docking_eligibility_status`` = ``"eligible"``
    - ``docking_run_status`` = ``"not_run"``
    - ``complex_mmcif`` ArtifactRef merged into artifacts
    """

def adapt_complex_export_failure(
    result: CovalentGenerationResult,
) -> CovalentGenerationResult:
    """Return a new result reflecting failed complex export.

    Immutable ``dataclasses.replace()`` update:
    - ``complex_export_status`` = ``"failed"``
    - ``docking_eligibility_status`` = ``"not_applicable"``
    - ``docking_run_status`` = ``"not_applicable"``
    - ``primary_failure_reason`` = ``"COMPLEX_EXPORT_FAILED"``

    Preserves generation-valid diagnostics and existing artifacts.
    Export failure is not a sampling-system failure.
    """
```

Required mmCIF content: `_atom_site.*` for protein + ligand atoms,
`_struct_conn` with `covale` type, `_entry.id`.

PDB compatibility output (LINK/CONECT) is optional future compatibility
output only - not implemented.

### CLI

```bash
# Task 26
python -m covalent_design.inference.validate_request --request <path> [--rules <path>]
# --rules defaults to data/rules/reaction_family_rule_table.yml (auto-discovered from repo root)
# Output: deterministic JSON to stdout; exit 0 on success; exit 20 on ContractError

# Task 27 has no standalone CLI.  generate() is a Python API called from
# orchestration code.  Task 28 ResultWriter is a pure-Python API with
# no independent CLI and integrates via generate(result_sink=writer.write).
```

### Artifact Boundary

Generation writes ``request.normalized.yml`` first (before checkpoint loading),
then creates this sibling layout:

```text
outputs/generation/<job_id>/
  request.normalized.yml
  run_manifest.yml
  results.jsonl
  sampling_system_failures.jsonl
  logs/
```

### Result Writer (Task 28)

```python
from covalent_design.inference.result_writer import ResultWriter

writer = ResultWriter()
row = writer.write(result)  # dict[str, object]
```

Key semantics:

- ``write()`` validates ``result`` with ``from covalent_design.contracts import
  validate_generation_result`` and raises ``ContractError`` on contract corruption
  (the first receipt error's code, owner, message, location, and details are
  preserved).
- Contract-corrupt sampler output raises a structured ``ContractError`` and is
  not silently converted to an invalid sample or sampling-system failure.
- Internally consistent invalid generated samples are retained as rows with
  diagnostics preserved.
- Writer rows contain every ``CovalentGenerationResult`` domain field as
  deterministic JSON-compatible values.
- Nested dataclasses become dictionaries, tuples become lists, and artifact
  mapping keys are stable.
- Top-level ``schema_version`` and ``contract_version`` are intentionally excluded
  from writer output — Task 27 ``write_jsonl()`` injects them in ``results.jsonl``.
- Task 27 integration is ``generate(..., result_sink=writer.write)``.
- ``ResultWriter()`` is stateless and reusable across multiple ``write()`` calls.
- Task 28 does not implement Task 29 mmCIF writer/export, real docking, Task 30
  evaluation, or heavy dependencies.
- Pure Python API — no standalone CLI.

### Misuse Guards

- Request validation failure returns `REQUEST_*` and does not create a sample result row.
- Sampling crash, OOM, timeout, retry exhaustion, checkpoint load failure, or
  sampler invariant violation creates `SamplingSystemFailure`, not an invalid
  generated sample.
- `predicted_warhead_type` is diagnostic only; validity gates use matched structural evidence and rule checks.
- Ligand size is decided before denoising; size mismatch is not a successful sample filter.
- `result_writer` validates lifecycle constraints (e.g., invalid → export = not_applicable) at write time.
- Protein structure reader (`structure_reader.py`) is pure Python with PDB/mmCIF atom-level boundary only; no RDKit, no torch.
- `write_normalized_request()` is a deterministic UTF-8 YAML writer callable by Task 27; Task 26 validation does not write generation, checkpoint, sampling, or normalized artifacts.
- Request validation failure is a request contract error (`owner="request"`), not an invalid generated sample (`CovalentGenerationResult`).
- ``SamplingPolicy`` requires ``max_retries`` and ``retry_on_categories`` explicitly; defaults are deliberately unfrozen.
- ``retry_exhausted`` is an emitted terminal sentinel row and cannot be configured as a retry trigger.
- ``result_sink`` is wired to ``ResultWriter.write()`` through ``generate(result_sink=writer.write)``.
- ``sampler``, ``checkpoint_loader``, ``clock``, and ``traceback_normalizer`` are injectable boundaries. No real PMDM, PocketFlow, torch, RDKit, Task 29 export, or Task 30 evaluation implementation.
- ``checkpoint_ref`` uses ``ArtifactRef | None`` — no separate ``CheckpointRef`` type.
- ``accepted_request_sample_count = attempted_sample_count + sampling_system_failure_count``; retries do not change the denominator. Every intermediate failure attempt row remains in ``sampling_system_failures.jsonl``.
- ``checkpoint_load_failed`` rows are emitted per accepted sample id.

## Evaluation Interfaces

### Manifest-First CLI

Evaluation uses a single entry point — the generation run manifest:

```bash
python -m covalent_design.evaluation.summarize_results \
    --manifest outputs/generation/<job_id>/run_manifest.yml
python -m covalent_design.evaluation.check_denominators \
    --manifest outputs/generation/<job_id>/run_manifest.yml
```

`summarize_results` reads `results.jsonl` and `sampling_system_failures.jsonl`
paths from the manifest, validates their checksums, and computes the
`EvaluationSummary`.  It writes `evaluation_summary.json` beside the manifest.
`check_denominators` recomputes the summary and prints the validation receipt
without writing files.

`summarize_results()` the Python function MUST NOT infer counts from files on
disk.  It has no write side effect — the CLI layers `write_evaluation_summary()`
on top.

### Python API

```python
def load_generation_run(
    manifest: Path,
) -> ContractEnvelope["GenerationRunManifest"]: ...
    """Parse and validate a generation-run manifest YAML.

    Validates schema_version, contract_version, and role.  Builds
    checksum-validated ArtifactRef entries for the three mandatory
    artifact keys: request, results, sampling_system_failures.
    Only relative URIs are accepted — absolute paths and traversal
    outside the manifest parent directory are rejected.

    Returns a ContractEnvelope with a GenerationRunManifest payload.
    """

def summarize_results(
    manifest: Path,
) -> "EvaluationSummary": ...
    """Manifest-first: reads manifest, loads referenced artifacts, computes summary.

    This API has no write side effect. Use write_evaluation_summary to
    persist the result. The CLI composes the two operations.

    Every result row is decoded through decode_result_row() and validated
    through validate_generation_result().  Corrupt rows produce structured
    ContractError, not silent skips.

    sampling_system_failure_count is read from the manifest and is
    authoritative; the row count of sampling_system_failures.jsonl is not
    used as a denominator.
    """

def check_denominators(
    summary: "EvaluationSummary",
) -> ValidationReceipt: ...
    """Validate the six EvaluationSummary conservation equations.

    Delegates to validate_evaluation_summary() in contracts.denominators.
    """

def evaluation_summary_to_dict(
    summary: "EvaluationSummary",
) -> dict[str, object]: ...
    """Serialize an EvaluationSummary to a deterministic JSON-compatible dict."""

def write_evaluation_summary(
    summary: "EvaluationSummary",
    path: Path,
) -> "ArtifactRef": ...
    """Write an EvaluationSummary to *path* atomically.

    Uses a same-directory temp file that is renamed into place.
    Returns an ArtifactRef for the written file with role=evaluation_summary,
    format=json.
    """
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

Required equations (six, implemented in `validate_evaluation_summary()`):

```text
requested = request_validation_error + accepted_request
accepted_request = attempted + sampling_system_failure
attempted = valid_internal + invalid_sample
valid_internal = exported_valid_complex + valid_export_failure
exported_valid_complex = docking_evaluable_valid + valid_but_not_docking_evaluable
docking_evaluable_valid = successfully_docked + docking_failed + docking_not_run
```

For one manifest, `request_validation_error_sample_count = 0` and
`requested_sample_count = accepted_request_sample_count`.

### Task 30 vs Task 33 Scope Split

| Task | Scope | Output |
| --- | --- | --- |
| Task 30 | Global denominator equations (no strata) | `evaluation_summary.json` |
| Task 33 | Per-split, per-family stratified reports | `stratified_evaluation_summary.json` |

Task 30 alone does NOT need to produce split-aware or family-stratified reports.
Checkpoint C requires Task 33 for full stratification.

### Task 33: Split-Aware Evaluation Reports

Task 33 is a Python API and atomic writer for stratified evaluation reports. It
does not add a CLI and does not run Checkpoint C.

#### Public APIs

```python
def load_split_index(path: Path) -> dict[str, object]: ...
def validate_split_index_for_evaluation(data: dict[str, object]) -> ValidationReceipt: ...
def load_leakage_report(path: Path) -> dict[str, object]: ...
def validate_leakage_report_for_evaluation(
    leakage: dict[str, object],
    split_index: dict[str, object],
) -> ValidationReceipt: ...
def join_results_to_split_assignments(
    results: tuple[CovalentGenerationResult, ...],
    split_index: dict[str, object],
) -> tuple[JoinedAssignment, ...]: ...
def summarize_split_results(
    results: tuple[CovalentGenerationResult, ...],
    split_index: dict[str, object],
) -> dict[str, object]: ...
def build_stratified_evaluation_summary(
    results: tuple[CovalentGenerationResult, ...],
    split_index: dict[str, object],
    leakage: dict[str, object],
    *,
    docking_index: dict[str, object] | None = None,
) -> StratifiedEvaluationSummary: ...
def stratified_evaluation_summary_to_dict(
    summary: StratifiedEvaluationSummary,
) -> dict[str, object]: ...
def write_stratified_evaluation_summary(
    summary: StratifiedEvaluationSummary,
    path: Path,
) -> ArtifactRef: ...
```

`JoinedAssignment` and `StratifiedEvaluationSummary` are evaluation-package
dataclasses, not shared `contracts/types.py` types.

#### Join And Input Contracts

The frozen join key is:

```text
CovalentGenerationResult.request_id == split_index.assignments[].record_id
```

Task 33 does not support external request-record maps, `(request_id, sample_id)`
matching, sample_id fallback, fuzzy matching, or directory scanning.

Split index input must carry current `schema_version`, current
`contract_version`, `role="split_index"`, `assignment_count`, and assignments
with `record_id`, `split`, `scaffold_key`, `protein_cluster_id`,
`residue_reaction_family`, `fallback_reason`, and `manual_review_status`.

Leakage report input must carry current `schema_version`, current
`contract_version`, `role="leakage_report"`, split counts, fallback/manual-review
counts, scaffold and protein-cluster overlap lists, and boolean
`zero_overlap.scaffold` / `zero_overlap.protein_cluster`. Split counts are
cross-validated against the split index.

#### Report Shape

`stratified_evaluation_summary_to_dict()` emits deterministic JSON-compatible
data with:

- `role="stratified_evaluation_summary"`.
- `per_split` train/val/test summaries whose `summary` value is
  `EvaluationSummary`-compatible.
- `per_family` summaries keyed by canonical `residue_reaction_family`.
- `scaffold_primary_metrics.per_split` and
  `protein_cluster_primary_metrics.per_split`, each with deterministic
  `unique_count` and `values` from the split index.
- `leakage_report.zero_overlap` and `leakage_report.blocking_primary_leakage`
  for scaffold and protein-cluster leakage risk.
- `excluded_summary`, `fallback_exclusions.by_reason` with counts and
  `record_ids`, and `manual_review_accounting`.
- `docking_score_eligible_counts` when a docking index is supplied, otherwise
  `null`.

Every result row is validated with `validate_generation_result()` before
aggregation. Corrupt rows raise `ContractError` before any output. Per-split
sampling-system failures are not attributed in Task 33 because the input is a
result-row list plus split index, not a split-aware run manifest.

#### Task 33 Boundaries

- Does not regenerate or mutate Task 14 splits.
- Does not infer joins from directories, sample ids, or sample order.
- Does not implement Task 30 global manifest accounting or duplicate its CLI.
- Does not implement Task 31 failure-mode reports or Task 32 docking protocol
  validation.
- Does not import RDKit, torch, PMDM, PocketFlow, or docking engines.
- Does not generate Checkpoint C artifacts beyond the explicit
  `stratified_evaluation_summary.json` writer output.

### CLI

```bash
# Task 30 — global summary and denominator check
python -m covalent_design.evaluation.summarize_results \
    --manifest outputs/generation/<job_id>/run_manifest.yml
python -m covalent_design.evaluation.check_denominators \
    --manifest outputs/generation/<job_id>/run_manifest.yml

# Task 32 — pure Python docking-protocol API only (no CLI)
# Task 33 — pure Python split-aware report API only (no CLI)
```

`summarize_results` CLI writes `evaluation_summary.json` to the manifest parent
directory and prints the summary as deterministic JSON to stdout.
`check_denominators` CLI prints the validation receipt to stdout and does not
write files.

### Misuse Guards

- `summarize_results()` uses generation run manifest counts, result rows, and sampling failure artifacts. It must not infer requested or attempted counts from files present on disk.
- `sampling_system_failures.jsonl` rows are schema-validated `SamplingSystemFailure` audit evidence. Their row count is not a denominator; the manifest `sampling_system_failure_count` is authoritative.
- The three mandatory checksum-validated artifact refs are `request`, `results`, and `sampling_system_failures`. Missing any is a hard error.
- Only relative artifact URIs are accepted. Absolute paths and traversal outside the manifest parent are rejected.
- Invalid samples remain in validity denominators.
- Docking protocol manifest validation, lifecycle reports, and stratified reports are Task 31-33 scope and are not documented as Task 30 APIs.

### Task 31: Lifecycle Validation And Failure Mode Reports

Task 31 exposes Python APIs and an explicit atomic writer only — no standalone CLI.
It consumes `CovalentGenerationResult` lists (validated by Task 30) and produces
`FailureModeReport` artifacts.

**`FailureModeReport` is an evaluation-package dataclass** (`covalent_design.evaluation.failure_modes`),
not a shared `contracts/types.py` type.

#### Public APIs

```python
# validity_metrics.py
def validate_results_before_aggregation(
    results: list[CovalentGenerationResult],
) -> ValidationReceipt: ...
    """Validate every result row before any lifecycle aggregation.

    Calls validate_generation_result() on every row.  Any corrupt lifecycle
    row fails the WHOLE report — no survivor aggregation, no partial output,
    no corrupt_lifecycle_count partial report, no partial artifact.
    """

def summarize_lifecycle_statuses(
    results: list[CovalentGenerationResult],
) -> dict[str, int]: ...
    """Validate and count all lifecycle statuses across a result list.

    Calls validate_results_before_aggregation internally and raises
    ContractError on corrupt rows.  Returns a dict with all 12 status keys:
    valid_generated, invalid_generated, and each lifecycle-stage status
    prefixed by complex_export_, docking_eligibility_, docking_run_.
    """

# failure_modes.py
def build_failure_mode_report(
    results: list[CovalentGenerationResult],
) -> FailureModeReport: ...
    """Validate all rows, then aggregate failure mode statistics.

    Calls validate_results_before_aggregation internally.  If any row is
    corrupt the whole report is rejected — no survivor aggregation.
    """

def build_failure_mode_report_from_manifest(
    manifest: Path,
) -> FailureModeReport: ...
    """Load validated results via Task 30 load_validated_results(manifest),
    then build a failure mode report."""

def failure_mode_report_to_dict(
    report: FailureModeReport,
) -> dict[str, object]: ...
    """Serialize a FailureModeReport to a deterministic JSON-compatible dict."""

def write_failure_mode_report(
    report: FailureModeReport,
    path: Path,
) -> ArtifactRef: ...
    """Write *report* to *path* atomically with same-directory tempfile,
    fsync, and os.replace.  Returns an ArtifactRef with role=failure_mode_report,
    format=json."""

# Task 30 helper (denominator_accounting.py) — reused by Task 31
def load_validated_results(
    manifest: Path,
) -> list[CovalentGenerationResult]: ...
    """Load a generation-run manifest and return fully validated results.

    Preserves all Task 30 validation: manifest parsing, artifact ref checks,
    checksum checks, JSONL schema checks, failures JSONL validation, manifest
    count checks, decode_result_row(), and validate_generation_result().
    Never exposes raw rows.  Does not produce denominator equations.
    """
```

#### Validate-All-Before-Aggregate

`validate_results_before_aggregation` calls `validate_generation_result` on every row.
If any single row is corrupt (e.g. `generation_validity_status = "invalid"` but
`docking_run_status = "succeeded"`), the entire receipt fails.  No survivor
aggregation, no `corrupt_lifecycle_count` partial report, no partial artifact on disk.

Both `summarize_lifecycle_statuses` and `build_failure_mode_report` call
`validate_results_before_aggregation` internally and propagate the failure as a
`ContractError`.

#### FROZEN_REASON_STAGE_MAP

```python
FROZEN_REASON_STAGE_MAP: Mapping[str, str] = {
    # generation (4)
    "LIGAND_RECONSTRUCTION_FAILED": "generation",
    "LIGAND_CHEMISTRY_INVALID": "generation",
    "NO_COVALENT_EDGE_PREDICTED": "generation",
    "COVALENT_EDGE_BELOW_THRESHOLD": "generation",
    # generation_gate (6)
    "REACTION_FAMILY_RULE_FAIL": "generation_gate",
    "WARHEAD_MATCH_FAIL": "generation_gate",
    "VALENCE_CHECK_FAIL": "generation_gate",
    "GEOMETRY_CHECK_FAIL": "generation_gate",
    "REQUIRED_GATE_STATE_UNAVAILABLE": "generation_gate",
    "UNSUPPORTED_GENERATED_CHEMISTRY": "generation_gate",
    # export (1)
    "COMPLEX_EXPORT_FAILED": "export",
    # docking_eligibility (1)
    "DOCKING_NOT_EVALUABLE": "docking_eligibility",
    # docking_run (1)
    "DOCKING_RUN_FAILED": "docking_run",
}
```

Five lifecycle stages: `generation`, `generation_gate`, `export`, `docking_eligibility`,
`docking_run`.  Every `FAILURE_REASON_CODES` value maps to exactly one stage.  Unknown
reasons raise `ContractError(code="FAILURE_REPORT_REASON_NOT_MAPPED")` — no silent
mapping.

#### FailureModeReport Fields

| Field | Type | Description |
| --- | --- | --- |
| `primary_reason_counts` | `Mapping[str, int]` | Global primary failure reason counts |
| `secondary_reason_counts` | `Mapping[str, int]` | Global secondary failure reason counts |
| `primary_reason_counts_by_family` | `Mapping[str, Mapping[str, int]]` | Primary counts grouped by `residue_reaction_family` |
| `secondary_reason_counts_by_family` | `Mapping[str, Mapping[str, int]]` | Secondary counts grouped by `residue_reaction_family` |
| `primary_reason_counts_by_stage` | `Mapping[str, Mapping[str, int]]` | Primary counts grouped by lifecycle stage |
| `secondary_reason_counts_by_stage` | `Mapping[str, Mapping[str, int]]` | Secondary counts grouped by lifecycle stage |
| `primary_reason_counts_by_family_and_stage` | `Mapping[str, Mapping[str, Mapping[str, int]]]` | Primary counts by family and stage |
| `secondary_reason_counts_by_family_and_stage` | `Mapping[str, Mapping[str, Mapping[str, int]]]` | Secondary counts by family and stage |
| `lifecycle_statuses` | `Mapping[str, int]` | From `summarize_lifecycle_statuses` |
| `evidence` | `tuple[Mapping[str, object], ...]` | Per-failure-row evidence with family, sample_id, primary/secondary reason, and lifecycle stage |

#### Key Design Rules

- **Canonical `residue_reaction_family` grouping only.** No protein-cluster, scaffold,
  or split-aware strata in Task 31.
- **Primary and secondary counts are separate** — globally and per-family.
- **Lifecycle stage is preserved** globally (`primary_reason_counts_by_stage`),
  by family (`primary_reason_counts_by_family_and_stage`), and in every evidence entry
  (`primary_failure_stage`, `secondary_failure_stages`).
- **`primary_failure_reason=None` (success) does not contribute** to any reason count.
- **Invalid but lifecycle-consistent results** remain in statistics — they are counted
  in `lifecycle_statuses` and their failure reasons appear in the report.
- **Deterministic ordering:** families sorted alphabetically, reasons sorted
  alphabetically within each group, evidence sorted by (family, reason, sample_id).
- **Atomic UTF-8 JSON writer:** same-directory tempfile → fsync → os.replace.
  Returns `ArtifactRef` with `role="failure_mode_report"`, `format="json"`.
- **`build_failure_mode_report_from_manifest`** delegates to
  `load_validated_results(manifest)` from Task 30 (denominator_accounting).  Raw rows
  are never exposed.  Manifest/artifact/checksum/JSONL validation is preserved without
  duplicating Task 30 denominator equations.
- **No Task 31 CLI.**  Task 31 is a pure Python API.
- **Task 32 docking protocol and Task 33 split-aware reports are outside Task 31.**
  Task 31 does not import or reference Task 32/33 modules.

#### CLI

No standalone Task 31 CLI.  Task 31 is called programmatically from Task 30-based
orchestration.

### Task 32: Docking Protocol Manifest Validation And Score Index

Task 32 implements protocol-manifest validation and a flat `DockingScoreEligibleResultIndex`
Python API. It does **not** execute docking, has **no** CLI, and does **not** choose an
authoritative docking engine for v1. ADR 0032 and `docs/covalent_generation_io_contract.md`
(lines 331-390) govern the authoritative nested YAML manifest schema.

#### Shared Contract Types

All six types below are frozen dataclasses in `covalent_design.contracts.types`:

```python
@dataclass(frozen=True)
class ReceptorPreparation:
    tool_name: str = ""
    tool_version: str = ""
    input_structure_uri: str = ""
    input_structure_sha256: str = ""
    output_receptor_uri: str = ""
    output_receptor_sha256: str = ""
    pH_or_protonation_policy: str = ""
    water_policy: str = "keep"        # "keep" | "remove" | "selected"
    cofactor_policy: str = "keep"     # "keep" | "remove" | "selected"
    metal_policy: str = "keep"        # "keep" | "remove" | "selected"

@dataclass(frozen=True)
class LigandPreparation:
    tool_name: str = ""
    tool_version: str = ""
    input_ligand_uri: str = ""
    input_ligand_sha256: str = ""
    charge_model: str = ""
    protonation_policy: str = ""

@dataclass(frozen=True)
class CovalentConstraint:
    representation: str = "other"     # "explicit_linkage" | "distance_constraint" | "reaction_constraint" | "other"
    target_atom_identity: str = ""
    ligand_atom_identity: str = ""
    constraint_parameters: Mapping[str, object] = field(default_factory=dict)  # may be empty

@dataclass(frozen=True)
class DockingSearchRegion:
    center: tuple[float, ...] = (0.0, 0.0, 0.0)  # numeric triple, no sign restriction on center
    size: tuple[float, ...] = (0.0, 0.0, 0.0)    # numeric triple, components must be positive
    unit: str = "angstrom"                         # "angstrom" only

@dataclass(frozen=True)
class PoseSelection:
    ranking_rule: str = "best_score"  # "best_score" | "first_valid" | "other"
    score_unit: str = ""

@dataclass(frozen=True)
class DockingProtocolManifest:
    docking_protocol_id: str = ""
    engine_name: str = ""
    engine_version: str = ""
    engine_build_hash: str = ""
    full_config_uri: str = ""
    full_config_sha256: str = ""
    random_seed: Optional[int] = None
    receptor_preparation: ReceptorPreparation = field(default_factory=ReceptorPreparation)
    ligand_preparation: LigandPreparation = field(default_factory=LigandPreparation)
    covalent_constraint: CovalentConstraint = field(default_factory=CovalentConstraint)
    search_region: DockingSearchRegion = field(default_factory=DockingSearchRegion)
    pose_selection: PoseSelection = field(default_factory=PoseSelection)
    failure_log_uri: str = ""
    failure_log_sha256: str = ""
```

#### Public API (6 Functions, No CLI)

```python
# All in covalent_design.evaluation.docking_protocol

def load_docking_protocol_manifest(path: Path) -> DockingProtocolManifest: ...
    """Decode a docking protocol manifest YAML file.

    Decodes inline JSON-compatible values left as strings by the minimal YAML loader
    (e.g. ``[10.0, 20.0, 30.0]``, ``{}``).  Missing nested required fields decode to
    invalid placeholder values so the validator reports failure instead of the loader
    crashing.  Unreadable or non-mapping YAML raises structured ``ContractError``.
    """

def validate_docking_protocol_manifest(
    manifest: DockingProtocolManifest,
    artifact_root: Path,
) -> ValidationReceipt: ...
    """Validate a docking protocol manifest against the frozen IO contract.

    Returns a ``ValidationReceipt``.  The receipt is failed when any required field
    is missing, empty, out-of-enum, or when a referenced artifact URI is unsafe,
    missing, or has a checksum mismatch.

    Validation rules:
    - All required string fields must be non-empty.
    - SHA-256 fields must be 64 lowercase hex characters.
    - engine_build_hash is required and non-empty but may be ``unknown``; it is
      provenance text, not a ``*_sha256`` field.
    - Enum fields must use allowed values (see contract types above).
    - search_region.center and size must be numeric triples; size components positive.
    - random_seed must be int or None; bool is rejected.
    - constraint_parameters must be a mapping (may be empty).
    - All artifact URIs must be root-relative: absolute paths, traversal (../), and
      backslash traversal are rejected.
    - Referenced artifact files (full_config, receptor_input, receptor_output,
      ligand_input, failure_log) must exist with matching SHA-256.
    - failure_log_uri and failure_log_sha256 are required; the file may be zero-byte.
    """

def docking_protocol_manifest_to_dict(
    manifest: DockingProtocolManifest,
) -> dict[str, object]: ...
    """Serialize a DockingProtocolManifest to a deterministic JSON-compatible dict
    preserving every field (including nested sub-structs and constraint_parameters)."""

def build_docking_score_eligible_result_index(
    results: list[CovalentGenerationResult],
    protocol_manifests: Mapping[str, object],
    artifact_root: Path,
) -> DockingScoreEligibleResultIndex: ...
    """Build a DockingScoreEligibleResultIndex from validated generation results.

    * Validates every input result via ``validate_generation_result`` first.
      Corrupt lifecycle rows raise ``ContractError`` before any output.
    * Filters to valid/exported/eligible/succeeded rows with
      ``covalent_docking_score is not None``.
    * Requires every surviving row to have an ``artifacts["docking_protocol_manifest"]``
      ``ArtifactRef`` whose URI maps to a supplied manifest in ``protocol_manifests``.
    * Validates the manifest ``ArtifactRef`` itself against ``artifact_root``,
      reloads the referenced YAML, requires it to match the supplied manifest
      object, then validates all internal protocol artifacts.
    * Missing association, missing supplied manifest, manifest ref mismatch,
      incomplete manifest, bad URI, or checksum mismatch raises
      ``ContractError`` — succeeded rows are never silently omitted.
    * QuickVina2-only baseline rows (no covalent docking score) are excluded normally.
    * Does not mutate input results.
    """

def docking_score_eligible_result_index_to_dict(
    index: DockingScoreEligibleResultIndex,
) -> dict[str, object]: ...
    """Serialize a DockingScoreEligibleResultIndex to a JSON-compatible dict.

    Output includes ``role`` (``"docking_score_eligible_result_index"``),
    ``format`` (``"json"``), ``counts.total_eligible_entries``, and a flat
    ``entries`` list.  Entries are sorted deterministically by
    (request_id, sample_id, docking_protocol_id)."""

def write_docking_score_eligible_result_index(
    index: DockingScoreEligibleResultIndex,
    path: Path,
) -> ArtifactRef: ...
    """Write *index* to *path* atomically.

    Uses a same-directory tempfile that is fsync'd and os.replace'd into place.
    Returns an ``ArtifactRef`` with ``role=docking_score_eligible_result_index``,
    ``format=json``.  No temp artifacts remain after a successful write.
    """
```

#### Index Entry Structure

```python
@dataclass(frozen=True)
class DockingScoreEligibleResult:
    """One flat entry in a DockingScoreEligibleResultIndex."""
    request_id: str
    sample_id: int
    docking_protocol_id: str
    covalent_docking_score: float
    noncovalent_vina_score: Optional[float]
    engine_name: str
    engine_version: str

@dataclass(frozen=True)
class DockingScoreEligibleResultIndex:
    """Index of all docking-score-eligible succeeded results."""
    entries: tuple[DockingScoreEligibleResult, ...]
```

Both types live in `covalent_design.evaluation.docking_protocol`, not in
shared `contracts/types.py`.

#### Key Design Rules

- **Manifest-first.** Index entries link explicitly through `ArtifactRef` in
  `result.artifacts["docking_protocol_manifest"]`. `protocol_manifests` is keyed
  by that `ArtifactRef.uri`. No directory scanning inference.
- **Hard ContractError on incomplete manifest association.** A succeeded row with
  missing, incomplete, or corrupt manifest association fails the whole index build.
  No survivor index; no partial output.
- **QuickVina2-only rows excluded.** Noncovalent scores stay in `noncovalent_vina_score`;
  `covalent_docking_score` stays null. A future documented covalent-linkage wrapper
  is not prohibited by engine-name string alone.
- **Deterministic flat ordering.** `(request_id, sample_id, docking_protocol_id)`.
  The flat sort is non-stochastic.
- **Atomic writer.** Same-directory tempfile → fsync → os.replace.
  Returns `ArtifactRef` with `role=docking_score_eligible_result_index`, `format=json`.
- **No docking engine selection.** Task 32 does not choose an authoritative covalent
  docking engine. The unresolved question remains for v1.
- **No Task 33 implementation.** Task 32 does not implement split/family stratified
  reports. No Task 33 imports or behavior.
- **No CLI.** Task 32 is a pure Python API.

#### Misuse Guards

- Artifact URIs must be root-relative. Absolute paths and traversal (including
  backslash traversal) are rejected.
- SHA-256 must be 64 lowercase hex. Uppercase and non-hex characters are rejected.
- Only size components of the search region must be positive; center components
  have no sign restriction.
- Boolean values are not valid `random_seed` values (must be int or None).
- `constraint_parameters` must be a mapping, never a list or scalar.

## Boundary Validation Points

| Boundary | Validation |
| --- | --- |
| Raw data to ETL | manifest schema, checksum, license/access notes |
| Source records to normalized records | canonical identity, atom mapping, monodentate filter |
| Records to training core | Q0/Q1/Q2, visual gate, conflict exclusion, non-edge artifact checksums for the 4 required roles |
| Rule table to gates | `family_id`, SMARTS status, geometry status, required chemical state |
| Records to model batch | tensor shapes, family key, edge candidate artifact, quality flags |
| Model to training loss | denominator validity, forced-positive masks, detached message weights |
| Request to inference | all 13 `REQUEST_*` validation errors via `ContractError(owner="request")` before sampling; `write_normalized_request()` callable by Task 27; `generate()` injects sampler/result_sink/checkpoint_loader/clock/traceback_normalizer boundaries; ``SamplingPolicy`` requires ``max_retries`` and ``retry_on_categories``; ``retry_exhausted`` is terminal sentinel, not a retry trigger |
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
- Misuse guards cover `residue_reaction_family`, pending SMARTS/geometry, forced positives, invalid samples, sampling failures, manifest-first evaluation with checksum-validated artifact refs, only relative URIs, and `sampling_system_failure_count` as the authoritative failure count.
