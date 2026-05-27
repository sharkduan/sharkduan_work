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
    ``record_id``, ``role`` (``"edge_candidates"``), ``lineage``,
    ``positive_edge``, ``negative_edges``, ``denominators`` (10 fields),
    ``artifact_refs``, and ``empty_radius_window``.  Zero negatives is a valid
    ``empty_radius_window``, not a failure.  Missing ``coordinates``,
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

def forward_covalent(
    model: "CovalentDiffusionModel",
    batch: "ModelBatch",
) -> "ModelForwardOutput": ...

def decode_final_edge(
    final_state: "FinalLigandState",
    gate: "ValidityGate",
) -> "FinalDecodeResult": ...

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
    """Output of one model forward pass."""
    pmdm_outputs: Mapping[str, object]
    edge_logits: object             # Tensor: (B, N_candidates)
    bond_type_logits: object        # Tensor: (B, N_candidates, N_bond_types)
    family_logits: object           # Tensor: (B, N_families) — v1 required
    edge_prob_message_weights: object  # detached Tensor: (B, N_candidates)
    message_weight_source: str      # "detached_edge_probability"
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

- **Static edge candidates** (Task 12, artifact role `"edge_candidates"`): built once from ground-truth coordinates. Provide positive-edge labels, negative-edge labels, and denominator statistics for supervision. Task 17 validates their existence and checksum and records them in ``ModelBatch.static_edge_candidates_refs`` (a ``record_id → ArtifactRef`` mapping). Task 18 later consumes their per-edge contents (positive label identity, bond type, per-candidate metadata).
- **Stepwise candidates** (Task 18, type `StepwiseCandidateSet`): rebuilt at every denoising timestep from current noisy/generated ligand coordinates. Positive label is force-included when noise moves it outside the candidate radius.

These are distinct entities and MUST NOT share an unqualified type or variable name.

### PMDM Adapter Output Keys

`ModelForwardOutput.pmdm_outputs` MUST contain 7 required keys and 2 optional keys:

| Key | Shape | Required |
| --- | --- | --- |
| `ligand_atom_features` | `(B, N_lig, D_lig)` | yes |
| `protein_atom_features` | `(B, N_prot, D_prot)` | yes |
| `ligand_coords_denoised` | `(B, N_lig, 3)` | yes |
| `ligand_pair_features` | `(B, N_lig, N_lig, D_pair)` | no |
| `protein_ligand_pair_features` | `(B, N_prot, N_lig, D_cross)` | no |
| `position_loss` | scalar | yes |
| `atom_type_loss` | scalar | yes |
| `timestep` | scalar float | yes |
| `num_atom` | `(B,)` | yes |

Fake backbone for smoke testing must output all `required` keys with correct shapes
and deterministic random values (fixed seed).

### Failure Reason Priority (Task 21)

Gate checks execute in this order for each candidate:

```
1. target_atom → 2. ligand_atom_class → 3. bond_type →
4. single_edge_representability → 5. warhead_smarts → 6. forbidden_smarts →
7. valence → 8. protonation → 9. geometry
```

The first failing check is that candidate's primary failure. `REQUIRED_GATE_STATE_UNAVAILABLE` outranks all other failures (the gate cannot be evaluated).

If the top-scoring candidate fails and a lower-ranked candidate passes all checks, the sample is **valid** — `secondary_failure_reasons` preserves skipped-candidate failures for diagnostic review.

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
python -m covalent_design.model.forward_smoke --config configs/covalent_model_smoke.yml
python -m covalent_design.model.export_arch_summary --config configs/covalent_model_smoke.yml --out data/reports/model_arch_summary.md
```

### Misuse Guards

- Use `candidate_radius_angstrom`, not `radius` or `pocket_radius`, for covalent edge candidates.
- Forced positives are represented explicitly and excluded from v1 message passing and geometry regression.
- Message weights are detached predicted probabilities with `message_weight_source = "detached_edge_probability"`, never ground-truth labels.
- `decode_final_edge()` returns valid or invalid; it never returns a best failed edge as a valid result.

## Training Interfaces

### Python API

```python
def prepare_dataset(
    records_path: Path,
    split_index_path: Path,
    split_name: str,                     # "train" | "val" | "test"
    policy: "TrainingDataPolicy | None",
) -> ContractEnvelope["TrainingDatasetIndex"]: ...
    """Build the training dataset index for one split.

    Excludes records according to policy:
    1. split != split_name → not in this dataset
    2. split == "excluded" → hard exclude
    3. visual_check_status != "pass" && policy.exclude_visual_blocked → exclude
    4. quality_tier not in accepted set → exclude
    5. policy.first_core_only && multi-linkage → exclude
    6. policy.exclude_q2 && quality_tier == "Q2" → exclude
    """

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
    split: str,
) -> ContractEnvelope["ValidationReport"]: ...

def report_denominators(
    run: "TrainingRunManifest",
) -> "DenominatorReport": ...
```

### Public Types

```python
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
class LossReport:
    schema_version: str
    contract_version: str
    step: int
    total_loss: float
    components: Mapping[str, float]
    denominators: EdgeDenominators | None
    mask_audit: MaskAudit | None
    strata: tuple[DenominatorsStratum, ...]
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
        # required keys: records_jsonl, split_index, rule_table
        # release-gate provenance keys: quality_report, visual_check_index, release_gate
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

- **Config hash**: resolve config → canonical JSON (sorted keys) → SHA-256
- **Record bundle hash**: SHA-256 of `records.jsonl`
- **Split hash**: SHA-256 of `split_index.json`
- **Rule table hash**: canonical JSON of parsed rule table → SHA-256
- **Release-gate provenance hashes**: SHA-256 of the Task 16 quality report, Task 15 visual check index, and optional release approval manifest. These hashes are audit provenance only; training runtime does not re-run the Data Release Gate.

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
  release_gate: "sha256:..."
model_weights_uri: "step_5000_model.pt"
optimizer_state_uri: "step_5000_optimizer.pt"
bond_type_vocabulary: ["no_edge", "carbon-sulfur", ...]
```

Cross-version compatibility: major version mismatch → hard reject; minor version mismatch → warn but allow.

### CLI

```bash
python -m covalent_design.training.prepare_dataset --records data/processed/covalent_complex_records/records.jsonl --splits <split_index.json> --split train
python -m covalent_design.training.train --config configs/covalent_train_smoke.yml
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

- `TrainingDataPolicy(first_core_only=True)` is the default. Including rejected, conflict, or multi-linkage records raises `DATASET_CONTRACT_VIOLATION`.
- Q2 keep-with-flag records are eligible only through accepted-core gates and must be stratified in reports.
- Pending geometry produces zero geometry denominator, not an unbounded geometry loss.
- Training reports distinguish debug random split from primary protein-cluster and scaffold splits.
- `LossReport` serialises via `.to_dict()` for JSONL output; `components` keys are validated at construction.

## Inference Interfaces

### Request File Format

YAML (`.yml` / `.yaml`) is the authoritative human-authored format.
JSON is accepted for programmatically-generated requests.  The CLI auto-detects
format from the file extension.  Validated requests are normalised to YAML
(`request.normalized.yml`) at the start of `generate()`.

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
    # Optional altloc specification:
    target_altloc: str | None = None  # "A", "B", etc.
```

`LigandSizeControl` must represent exactly one of:

- fixed `num_ligand_heavy_atoms`
- inclusive range `min_ligand_heavy_atoms` and `max_ligand_heavy_atoms`
- absent, meaning model size prior

### Alternate-Location Atom Policy

When the target atom has multiple altloc conformations:
1. If `target_altloc` is specified in the request → use that altloc; fail with
   `REQUEST_TARGET_ATOM_NOT_FOUND` if not present.
2. If not specified → select highest occupancy altloc; if occupancy data
   unavailable or equal, select `altloc='A'`.
3. Resolved altloc recorded in `ValidatedRequest.resolved_target_altloc`.

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

### Retry Policy

- `attempted_sample_count` is per sample_id, not per attempt.
- Retries are internal strategy details and do NOT change denominator equations.
- `accepted_request_sample_count = attempted_sample_count + sampling_system_failure_count`
- `sampling_system_failure_count` is deduplicated by sample_id (only samples
  that failed ALL retries).

### mmCIF Export (Task 29)

Writer boundary: project-owned mmCIF writer or adapter boundary. RDKit may be used later as an optional backend only after the exact API is source-verified; default CI must use fixture/project-owned writer tests and must not require RDKit. Source-verification status (2026-05-27): the official RDKit `rdkit.Chem.rdmolfiles` API reference (`https://rdkit.org/docs/source/rdkit.Chem.rdmolfiles.html`) was checked for an mmCIF writer and no v1 backend API is frozen from that source.

```python
def write_covalent_complex(
    result: CovalentGenerationResult,
    protein_atom_table: ArtifactRef,
    ligand_coords: object,         # Tensor (N_lig, 3)
    ligand_atom_types: object,     # Tensor (N_lig,)
    ligand_bonds: object,          # Tensor (N_lig, N_lig)
    covalent_edge: CovalentEdge,
    out_path: Path,
) -> ArtifactRef:
    """Export a valid covalent complex as mmCIF.

    Returns ArtifactRef with sha256 of the written file.
    Raises ContractError(code="COMPLEX_EXPORT_FAILED") on failure.
    """
```

Required mmCIF content: `_atom_site.*` for protein + ligand atoms,
`_struct_conn` with `covale` type, `_entry.id`.

### CLI

```bash
python -m covalent_design.inference.validate_request --request request.yml
python -m covalent_design.inference.generate --request request.yml --checkpoint outputs/checkpoints/model.pt --out outputs/generation/<job_id>
python -m covalent_design.inference.export_complexes --results outputs/generation/<job_id>/results.jsonl
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

### Result Writer (Task 28)

Pure Python API — no independent CLI.  `result_writer.write(result)` is called
inside `generate()` for each attempted sample.  The writer validates lifecycle
constraints before writing.

### Misuse Guards

- Request validation failure returns `REQUEST_*` and does not create a sample result row.
- Sampling crash, OOM, timeout, or retry exhaustion creates `SamplingSystemFailure`, not an invalid generated sample.
- `predicted_warhead_type` is diagnostic only; validity gates use matched structural evidence and rule checks.
- Ligand size is decided before denoising; size mismatch is not a successful sample filter.
- `result_writer` validates lifecycle constraints (e.g., invalid → export = not_applicable) at write time.

## Evaluation Interfaces

### Manifest-First CLI

Evaluation uses a single entry point — the generation run manifest:

```bash
python -m covalent_design.evaluation.summarize_results \
    --manifest outputs/generation/<job_id>/run_manifest.yml
```

`summarize_results()` reads `results.jsonl` and `sampling_system_failures.jsonl`
paths from the manifest, validates their checksums, and computes the
`EvaluationSummary`.  It MUST NOT infer counts from files on disk.

### Python API

```python
def load_generation_run(
    manifest: Path,
) -> ContractEnvelope["GenerationRunManifest"]: ...

def summarize_results(
    manifest: Path,
) -> "EvaluationSummary": ...
    """Manifest-first: reads manifest, loads referenced artifacts, computes summary."""

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
    split: str,
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

### Task 30 vs Task 33 Scope Split

| Task | Scope | Output |
| --- | --- | --- |
| Task 30 | Global denominator equations (no strata) | `evaluation_summary.json` |
| Task 33 | Per-split, per-family stratified reports | `stratified_evaluation_summary.json` |

Task 30 alone does NOT need to produce split-aware or family-stratified reports.
Checkpoint C requires Task 33 for full stratification.

### CLI

```bash
# Task 30 — global denominator check
python -m covalent_design.evaluation.summarize_results \
    --manifest outputs/generation/<job_id>/run_manifest.yml
python -m covalent_design.evaluation.check_denominators \
    --manifest outputs/generation/<job_id>/run_manifest.yml

# Task 32 — docking protocol
python -m covalent_design.evaluation.run_covalent_docking \
    --manifest configs/docking_protocol.yml \
    --results outputs/generation/<job_id>/results.jsonl

# Task 33 — stratified report
python -m covalent_design.evaluation.report \
    --manifest outputs/generation/<job_id>/run_manifest.yml \
    --split scaffold --out outputs/eval/report.md
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
