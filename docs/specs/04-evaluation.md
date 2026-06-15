# Spec: Evaluation

## Objective

Evaluate generated covalent inhibitors with denominator conservation, explicit lifecycle states, split-aware reporting, rule/gate failure modes, mmCIF export status, docking eligibility, and covalent docking scores only where the covalent docking protocol succeeds.

Evaluation must make invalid generated samples visible instead of deleting them or assigning artificial docking scores.

## Tech Stack

- Python 3.9-compatible project-owned evaluation code.
- JSONL/YAML result and summary artifacts.
- Optional docking tools only behind explicit protocol manifests.
- QuickVina2 may be reported only as a noncovalent baseline or compatibility metric unless wrapped in a reviewed covalent protocol.

## Commands

```bash
python -m covalent_design.evaluation.summarize_results --manifest <run_manifest.yml>
python -m covalent_design.evaluation.check_denominators --manifest <run_manifest.yml>
python -m compileall -q scripts src
```

## Project Structure

```text
src/covalent_design/evaluation/
  __init__.py
  result_schema.py
  summarize_results.py          # CLI entry point
  check_denominators.py         # CLI entry point
  denominator_accounting.py     # core API functions
```

## Python API

```python
def load_generation_run(manifest: Path) -> ContractEnvelope[GenerationRunManifest]: ...
    """Parse and validate a generation-run manifest YAML.

    Returns a ContractEnvelope with the GenerationRunManifest payload and
    checksum-validated artifact references for request, results, and
    sampling_system_failures.
    """

def summarize_results(manifest: Path) -> EvaluationSummary: ...
    """Load a generation run and compute its EvaluationSummary.

    This API has no write side effect.  Use write_evaluation_summary to
    persist the result.  The CLI composes the two operations.
    """

def check_denominators(summary: EvaluationSummary) -> ValidationReceipt: ...
    """Validate the six EvaluationSummary conservation equations."""

def evaluation_summary_to_dict(summary: EvaluationSummary) -> dict[str, object]: ...
    """Serialize an EvaluationSummary to a deterministic JSON-compatible dict."""

def write_evaluation_summary(summary: EvaluationSummary, path: Path) -> ArtifactRef: ...
    """Write an EvaluationSummary to *path* atomically.

    Uses a same-directory temp file that is renamed into place.
    Returns an ArtifactRef for the written file.
    """
```

## CLI

```bash
# Compute and write evaluation_summary.json beside the manifest; print summary to stdout
python -m covalent_design.evaluation.summarize_results --manifest <run_manifest.yml>

# Validate conservation equations, print receipt to stdout (no file write)
python -m covalent_design.evaluation.check_denominators --manifest <run_manifest.yml>
```

`summarize_results` writes `evaluation_summary.json` to the manifest parent directory.
`check_denominators` recomputes the summary from the manifest and prints the validation receipt without writing files.

## Counting Rules

Manifest-first: every count comes from the manifest and the checksum-validated result/failure artifacts it references. Counts must not be inferred from files present on disk.

### Manifest Fields Used

| Manifest field | Role |
| --- | --- |
| `accepted_request_sample_count` | Becomes `requested_sample_count` and `accepted_request_sample_count` in the summary |
| `attempted_sample_count` | Number of attempted samples (one per sample_id) |
| `sampling_system_failure_count` | Authoritative count of fully-failed samples |
| `result_count` | Must equal the number of rows in `results.jsonl` |

### Result Row Processing

Every row in `results.jsonl` is decoded through `decode_result_row()` and validated
through `validate_generation_result()`.  Invalid rows (decode or lifecycle failures)
produce structured `ContractError`, not silent skips.

### Sampling System Failures

`sampling_system_failures.jsonl` rows are schema-validated as `SamplingSystemFailure`
audit evidence.  The row count in the file is not used as a denominator; the
manifest's `sampling_system_failure_count` is authoritative.

### Lifecycle Counting

Results are counted by lifecycle status:

```
attempted = valid_generated_internal + invalid_generated
valid_generated_internal = exported_valid_complex + valid_export_failure
exported_valid_complex = docking_evaluable_valid + valid_but_not_docking_evaluable
docking_evaluable_valid = successfully_docked + docking_failed + docking_not_run
```

Valid samples proceed through the lifecycle: generation validity -> export status ->
docking eligibility -> docking run status.  Invalid samples do not advance past
the validity check.

## Testing Strategy

Golden fixtures must cover:

- Request validation errors excluded from generation denominators.
- Invalid generated samples retained with failure reasons.
- Valid internal result with mmCIF export failure.
- Valid exported result that is not docking-evaluable.
- Docking-eligible sample with `not_run`, `failed`, and `succeeded` run statuses.
- Corrupt lifecycle rows rejected before aggregation.
- Sampling system failure artifact rows validated as audit evidence, with row count not used as a denominator.
- Manifest `sampling_system_failure_count` used as the authoritative count.

Conservation equations from the IO contract must be tested exactly (see `validate_evaluation_summary`).

## Boundaries

Always:

- Read counts from the manifest, not from files on disk.
- Mandatory checksum-validated artifact refs are `request`, `results`, and `sampling_system_failures`.
- Use relative artifact URIs only; no absolute paths or traversal outside the manifest parent.
- Treat `sampling_system_failure_count` in the manifest as authoritative.
- Schema-validate every `sampling_system_failures.jsonl` row as audit evidence.
- Decode and validate every result row through `validate_generation_result()`.
- Separate generation validity, export status, docking eligibility, and docking run status as lifecycle fields.
- Task 30 is global unstratified summary only.

Ask first:

- Changing the six conservation equations.
- Changing Task 31 failure-mode semantics, Task 32 docking-protocol indexing rules, or Task 33 stratification.

Never:

- Collapse generation validity, export status, docking eligibility, and docking run into a single flag.
- Infer counts from directory scanning, sibling artifact presence, or `--results`/`--summary` file paths.
- Use the row count of `sampling_system_failures.jsonl` as a denominator.

## Success Criteria

- All six conservation equations pass for generated summaries.
- Manifest-first: `summarize_results(manifest)` loads artifacts by checksum-validated paths with no disk scanning.
- Python `summarize_results()` has no write side effect; `write_evaluation_summary()` and the CLI handle persistence.
- `evaluation_summary.json` written atomically beside the manifest by the CLI.
- For one manifest, `request_validation_error_sample_count = 0` and `requested_sample_count = accepted_request_sample_count`.
- `sampling_system_failure_count` comes from the manifest, not from row counts in `sampling_system_failures.jsonl`.
- Every result row decoded and validated; corrupt rows produce structured errors, not silent skips.

## Open Questions

Resolved (2026-06-02 Task 30 freeze):

- **Evaluation CLI:** manifest-first (`--manifest <run_manifest.yml>`). Counts from manifest, not from disk. See `interface-design.md`.
- **Python API:** Five public functions: `load_generation_run`, `summarize_results`, `check_denominators`, `evaluation_summary_to_dict`, `write_evaluation_summary`. Summarize has no write side effect.
- **Task 30 vs Task 33 scope:** Task 30 = global unstratified summary only. Task 33 = per-split, per-family stratified reports. See `implementation-plan.md`.
- **Failure reason priority:** Gate execution order determines primary failure. `REQUIRED_GATE_STATE_UNAVAILABLE` outranks all. See `interface-design.md` Failure Reason Priority.
- **Retry counting:** sample_id granularity; retries internal; denominator not affected. See ADR 0035.
- **Sampling system failures:** `sampling_system_failures.jsonl` rows are schema-validated audit evidence. Row count is not a denominator; `sampling_system_failure_count` in the manifest is authoritative.

Still open for v1:

- Which covalent docking engine and representation are authoritative for v1?
- Is docking required for all valid samples or a reviewed subset?
- What score unit and pose ranking convention should be standardized?
- How should multi-label failure reasons be summarized without hiding the primary lifecycle failure?
- Is manual structural review part of the release gate or a separate analysis artifact?

## Task 31: Lifecycle Validation And Failure Mode Reports

Task 31 builds on Task 30's validated results to produce failure mode reports
with lifecycle stage preserved at every level of aggregation.

### Python API (no CLI)

```python
# validity_metrics.py
def validate_results_before_aggregation(
    results: list[CovalentGenerationResult],
) -> ValidationReceipt: ...

def summarize_lifecycle_statuses(
    results: list[CovalentGenerationResult],
) -> dict[str, int]: ...

# failure_modes.py
def build_failure_mode_report(
    results: list[CovalentGenerationResult],
) -> FailureModeReport: ...

def build_failure_mode_report_from_manifest(
    manifest: Path,
) -> FailureModeReport: ...

def failure_mode_report_to_dict(
    report: FailureModeReport,
) -> dict[str, object]: ...

def write_failure_mode_report(
    report: FailureModeReport,
    path: Path,
) -> ArtifactRef: ...
```

`load_validated_results(manifest)` from Task 30 (denominator_accounting) is the
reusable bridge: it preserves all manifest/artifact/checksum/JSONL validation
without exposing raw rows.  Task 31 does not duplicate denominator equations.

### Validate-All-Before-Aggregate

`validate_results_before_aggregation` calls `validate_generation_result` on every
result row.  Any corrupt lifecycle row (e.g. `generation_validity_status = "invalid"`
but `docking_run_status = "succeeded"`) fails the WHOLE report.  There is no survivor
aggregation, no `corrupt_lifecycle_count` partial report, and no partial artifact on
disk.  Both `summarize_lifecycle_statuses` and `build_failure_mode_report` call
`validate_results_before_aggregation` internally and raise `ContractError` on failure.

### FROZEN_REASON_STAGE_MAP

Every `FAILURE_REASON_CODES` value maps to exactly one of five lifecycle stages:

| Stage | Reasons |
| --- | --- |
| `generation` | `LIGAND_RECONSTRUCTION_FAILED`, `LIGAND_CHEMISTRY_INVALID`, `NO_COVALENT_EDGE_PREDICTED`, `COVALENT_EDGE_BELOW_THRESHOLD` |
| `generation_gate` | `REACTION_FAMILY_RULE_FAIL`, `WARHEAD_MATCH_FAIL`, `VALENCE_CHECK_FAIL`, `GEOMETRY_CHECK_FAIL`, `REQUIRED_GATE_STATE_UNAVAILABLE`, `UNSUPPORTED_GENERATED_CHEMISTRY` |
| `export` | `COMPLEX_EXPORT_FAILED` |
| `docking_eligibility` | `DOCKING_NOT_EVALUABLE` |
| `docking_run` | `DOCKING_RUN_FAILED` |

Unknown reasons raise `ContractError(code="FAILURE_REPORT_REASON_NOT_MAPPED")`.

### FailureModeReport

`FailureModeReport` is an evaluation-package dataclass (`covalent_design.evaluation.failure_modes`),
not a shared `contracts/types.py` type.  It contains:

- **Primary and secondary reason counts** — separate globally (`primary_reason_counts`,
  `secondary_reason_counts`) and by `residue_reaction_family` (canonical grouping only).
- **Lifecycle stage preserved** globally (`primary_reason_counts_by_stage`),
  by family (`primary_reason_counts_by_family_and_stage`), and in every evidence
  entry (`primary_failure_stage`, `secondary_failure_stages`).
- **`lifecycle_statuses`** from `summarize_lifecycle_statuses` (all 12 status keys).
- **Evidence** entries sorted deterministically by (family, reason, sample_id).
  Each entry includes `residue_reaction_family`, `sample_id`, `primary_failure_reason`,
  `primary_failure_stage`, `secondary_failure_reasons`, and `secondary_failure_stages`.
- **`primary_failure_reason=None` (success) does not contribute** to any reason count.
- **Invalid but lifecycle-consistent results** remain in the report.

### Atomic Writer

`write_failure_mode_report` writes deterministically ordered UTF-8 JSON via a
same-directory tempfile that is fsync'd and os.replace'd into place.  It returns
an `ArtifactRef` with `role="failure_mode_report"`, `format="json"`.  No temp
artifacts remain after a successful write.

### Testing Strategy

Golden fixtures must cover:

- Corrupt lifecycle rows (invalid gen + succeeded docking, invalid gen + exported,
  invalid gen + None failure reason) → whole report rejected.
- Primary and secondary reason counts separated globally and per-family.
- `primary_failure_reason=None` (success) excluded from reason counts.
- Lifecycle stage preserved in global, per-family, and evidence views.
- All `FAILURE_REASON_CODES` values mapped; unknown reason → ContractError.
- Deterministic ordering: families, reasons, evidence.
- Atomic writer: no temp artifacts, deterministic bytes, correct ArtifactRef role.
- `build_failure_mode_report_from_manifest` uses `load_validated_results` from
  Task 30 — manifest validation, checksum checks, and `decode_result_row()` are
  all preserved.
- No Task 32/33 imports or behavior.

### Boundaries

Always:

- Validate all rows before any aggregation.  One corrupt row → whole report rejected.
- Group by canonical `residue_reaction_family` only.
- Separate primary and secondary failure counts globally, by family, by stage, and
  by family+stage.
- Preserve lifecycle stage in every evidence entry.
- Use deterministic ordering and atomic UTF-8 JSON writes.

Never:

- Produce partial reports with `corrupt_lifecycle_count`.
- Expose raw JSONL rows through the Task 31 API.
- Duplicate Task 30 denominator conservation equations.
- Implement a standalone Task 31 CLI.
- Import or reference Task 32 (docking protocol) or Task 33 (split-aware reports).

## Task 32: Docking Protocol Manifest Validation And Score Index

Task 32 implements protocol-manifest validation and a flat `DockingScoreEligibleResultIndex`
Python API. It does not execute docking and has no Task 32 CLI.

### Shared Frozen Contract Types (covalent_design.contracts.types)

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
    water_policy: str = "keep"        # keep | remove | selected
    cofactor_policy: str = "keep"     # keep | remove | selected
    metal_policy: str = "keep"        # keep | remove | selected

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
    representation: str = "other"     # explicit_linkage | distance_constraint | reaction_constraint | other
    target_atom_identity: str = ""
    ligand_atom_identity: str = ""
    constraint_parameters: Mapping[str, object] = field(default_factory=dict)

@dataclass(frozen=True)
class DockingSearchRegion:
    center: tuple[float, ...] = (0.0, 0.0, 0.0)
    size: tuple[float, ...] = (0.0, 0.0, 0.0)
    unit: str = "angstrom"            # angstrom only

@dataclass(frozen=True)
class PoseSelection:
    ranking_rule: str = "best_score"  # best_score | first_valid | other
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

### Python API (No CLI)

```python
# docking_protocol.py

def load_docking_protocol_manifest(path: Path) -> DockingProtocolManifest: ...
    """Decode a docking protocol manifest YAML file.

    Missing nested required fields decode to invalid placeholder values so
    the validator reports failure instead of the loader crashing.
    Unreadable or non-mapping YAML raises structured ContractError.
    """

def validate_docking_protocol_manifest(
    manifest: DockingProtocolManifest,
    artifact_root: Path,
) -> ValidationReceipt: ...
    """Validate a docking protocol manifest against the frozen IO contract.

    Returns a ValidationReceipt.  The receipt is failed when any required
    field is missing, empty, out-of-enum, or when a referenced artifact URI
    is unsafe, missing, or has a checksum mismatch.
    """

def docking_protocol_manifest_to_dict(
    manifest: DockingProtocolManifest,
) -> dict[str, object]: ...
    """Serialize a DockingProtocolManifest to a deterministic JSON-compatible dict
    preserving every field."""

def build_docking_score_eligible_result_index(
    results: list[CovalentGenerationResult],
    protocol_manifests: Mapping[str, object],
    artifact_root: Path,
) -> DockingScoreEligibleResultIndex: ...
    """Build a DockingScoreEligibleResultIndex from validated generation results.

    Validates every input result via validate_generation_result first.
    Corrupt lifecycle rows raise ContractError before any output.
    Filters to valid/exported/eligible/succeeded rows with covalent_docking_score.
    Requires every surviving row to have an artifacts[docking_protocol_manifest]
    ArtifactRef whose URI maps to a supplied manifest in protocol_manifests.
    Validates the manifest ArtifactRef itself against artifact_root, reloads
    the referenced YAML, requires it to match the supplied manifest object,
    then validates all internal protocol artifacts.
    Missing association, missing supplied manifest, manifest ref mismatch,
    incomplete manifest, bad URI, or checksum mismatch raises ContractError.
    QuickVina2-only baseline rows are omitted normally.
    Does not mutate input results.
    """

def docking_score_eligible_result_index_to_dict(
    index: DockingScoreEligibleResultIndex,
) -> dict[str, object]: ...
    """Serialize a DockingScoreEligibleResultIndex to a JSON-compatible dict.
    Includes role=docking_score_eligible_result_index, format=json, counts,
    and a flat entries list sorted by (request_id, sample_id, docking_protocol_id)."""

def write_docking_score_eligible_result_index(
    index: DockingScoreEligibleResultIndex,
    path: Path,
) -> ArtifactRef: ...
    """Write index to path atomically via same-directory tempfile, fsync, and
    os.replace. Returns an ArtifactRef with role=docking_score_eligible_result_index,
    format=json."""
```

### Manifest Validation Rules

Required manifest strings must be non-empty. SHA-256 fields must be 64 lowercase hex
characters. Artifact URIs must be root-relative only: absolute paths and traversal
(including Windows backslash traversal) are rejected.

`engine_build_hash` is a required non-empty provenance string, not a `*_sha256` field.
It may be `unknown` when a reproducible engine build hash is unavailable.

The validator checks the full config, receptor input structure, receptor output receptor,
ligand input ligand, and failure log artifacts for existence and checksum, not existence
alone. Checksum-mismatched artifacts fail validation.

`failure_log_uri` and `failure_log_sha256` are required. The referenced file may be
zero-byte as long as the SHA-256 matches.

`constraint_parameters` may be an empty mapping. `random_seed` may be null. Bool values
for random_seed are rejected (must be int or None).

Search region `center` and `size` must be numeric triples. Only `size` components must
be positive; `center` components have no sign restriction.

Enum-restricted fields must use allowed values:

| Field | Allowed values |
| --- | --- |
| water_policy, cofactor_policy, metal_policy | keep, remove, selected |
| constraint representation | explicit_linkage, distance_constraint, reaction_constraint, other |
| search_region.unit | angstrom |
| pose_selection.ranking_rule | best_score, first_valid, other |

### DockingScoreEligibleResultIndex Building

`build_docking_score_eligible_result_index` is the single index builder. Index inclusion
requires all of: generation_validity_status == "valid", complex_export_status == "exported",
docking_eligibility_status == "eligible", docking_run_status == "succeeded",
covalent_docking_score is not None, and a complete validated linked manifest.

Successful covalent-score rows link explicitly through `result.artifacts["docking_protocol_manifest"]`.
`protocol_manifests` is keyed by that `ArtifactRef.uri`. The builder validates the
manifest ArtifactRef (existence + checksum against artifact_root), reloads the linked
YAML and requires it to match the supplied manifest object, and validates the manifest's
internal artifacts.

A succeeded row with missing, incomplete, or corrupt manifest association is a hard
`ContractError` — no survivor index. Ordinary non-success rows (invalid, export-failed,
not-evaluable, not-run, docking-failed) are excluded silently.

### QuickVina2-Only Baseline

QuickVina2-only rows (`docking_run_status = "not_run"`, `covalent_docking_score = null`)
are excluded from the index. Their `noncovalent_vina_score` remains populated.
QuickVina2 alone is not a covalent docking protocol; it may be reported as a
noncovalent baseline or compatibility metric unless wrapped in a documented
covalent-linkage or constrained protocol. A future documented covalent-linkage wrapper
is not prohibited by engine-name string alone.

### Deterministic Ordering And Atomic Writer

Index entries sort deterministically by `(request_id, sample_id, docking_protocol_id)`.
The flat sort is non-stochastic and does not infer or reshape the input ordering.

`write_docking_score_eligible_result_index` writes via same-directory tempfile, fsync,
and os.replace. It returns an `ArtifactRef` with `role=docking_score_eligible_result_index`,
`format=json`.

### Boundaries

Always:

- Manifest-first: count index entries from validated manifests, not from files on disk.
- Reject absolute artifact URIs and traversal (including backslash traversal).
- Require checksum match for every referenced artifact, not existence alone.
- Accept zero-byte failure log when SHA-256 matches.
- Accept empty constraint_parameters and null random_seed.
- Filter to valid + exported + eligible + succeeded + covalent score + complete validated manifest.
- Raise ContractError (not write partial index) for corrupt manifest association.
- Sort deterministically by (request_id, sample_id, docking_protocol_id).
- Write index atomically.

Ask first:

- Changing the YAML manifest schema (governed by IO contract and ADR 0032).
- Choosing an authoritative covalent docking engine (remain unresolved for v1).
- Implementing Task 33 split/family stratified reports.
- Adding a Task 32 CLI.

Never:

- Execute docking or import a docking engine.
- Create a Task 32 CLI.
- Implement directory-scanning manifest inference.
- Implement Task 33 split/family reports.
- Import or reference Task 33 (split-aware reports).
- Import RDKit, torch, PMDM, or PocketFlow.
- State that search region center must be positive (only size components are positive).
- Claim Task 32 imports or executes QuickVina2.

### Testing Strategy

Golden fixtures must cover:

- Valid complete manifest loads without error and passes validate_docking_protocol_manifest.
- null random_seed accepted.
- Empty constraint_parameters mapping accepted.
- Zero-byte failure log with correct SHA accepted.
- Every required string field (docking_protocol_id, engine_name, engine_version, engine_build_hash, full_config_uri, full_config_sha256, failure_log_uri, failure_log_sha256, receptor_preparation.*, ligand_preparation.*, covalent_constraint.*, pose_selection.score_unit) non-empty → rejected when empty.
- SHA-256 fields rejected when too short, uppercase, or non-hex.
- Enum fields rejected for out-of-enum values (water/cofactor/metal policy, constraint representation, search unit, pose ranking rule).
- Search region center non-triple and wrong-size triples rejected; size negative/zero rejected.
- URI safety: absolute, traversal (forward-slash), and backslash traversal rejected.
- Missing artifact files and checksum mismatches rejected for full_config, receptor_input, receptor_output, ligand_input, and failure_log.
- Valid succeeded result with manifest link included in index.
- Multiple results sorted deterministically by (request_id, sample_id, docking_protocol_id).
- Ordinary excluded lifecycle states (invalid, export-failed, not-evaluable, not-run, docking-failed) omitted.
- Succeeded row without manifest association → ContractError.
- Succeeded row pointing to manifest not in protocol_manifests → ContractError.
- Succeeded row manifest ref checksum mismatch → ContractError.
- Succeeded row nested artifact checksum mismatch → ContractError.
- Corrupt lifecycle row (e.g. invalid + succeeded) → ContractError before any output.
- QuickVina2-only baseline rows excluded from index.
- Input result objects not mutated.
- Empty results list produces empty index.
- Index dict includes role, format, and counts metadata.
- Writer is atomic (no temp residue), deterministic, returns correct ArtifactRef role.
- No heavy dependencies loaded (torch, RDKit, PMDM, PocketFlow).
- No Task 33 imports.
- No docking engine imports.

## Task 33: Split-Aware Evaluation Reports

Task 33 produces stratified evaluation reports from generation results, the Task
14 split index, and the Task 14 leakage report. It is a Python API plus atomic
JSON writer; there is no Task 33 CLI.

### Python API

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

`reports.py` is a thin compatibility facade over `split_metrics.py`.

### Join Rule

The frozen join key is:

```text
CovalentGenerationResult.request_id == split_index.assignments[].record_id
```

Task 33 must not use external request-record maps, `(request_id, sample_id)`
matching, sample id fallback, fuzzy matching, sibling files, or directory scans.
If a result has no split assignment, report construction raises structured
`ContractError(code="SPLIT_REPORT_ASSIGNMENT_MISSING")`.

### Validation

`load_split_index()` validates the split index. Direct API calls validate the
same contract before joining:

- current `schema_version` and `contract_version`;
- `role="split_index"`;
- `assignment_count == len(assignments)`;
- unique `record_id`;
- `split` in train/val/test/excluded;
- assignment fields `record_id`, `split`, `scaffold_key`,
  `protein_cluster_id`, `residue_reaction_family`, `fallback_reason`, and
  `manual_review_status`.

`validate_leakage_report_for_evaluation()` requires current versions,
`role="leakage_report"`, split counts, fallback/manual-review counts, overlap
lists, and boolean `zero_overlap.scaffold` and `zero_overlap.protein_cluster`.
Split counts are cross-validated against the split index.

Every `CovalentGenerationResult` is validated with `validate_generation_result`
before aggregation. Corrupt lifecycle rows fail the whole report before output.

### Report Shape

`stratified_evaluation_summary.json` contains:

- `schema_version`, `contract_version`, and
  `role="stratified_evaluation_summary"`;
- `per_split` train/val/test summaries with `EvaluationSummary`-compatible
  `summary` dicts;
- `per_family` lifecycle summaries keyed by canonical
  `residue_reaction_family`;
- `scaffold_primary_metrics` and `protein_cluster_primary_metrics`, each with
  per-split `unique_count` and deterministic `values` from the split index;
- `leakage_report.zero_overlap` and
  `leakage_report.blocking_primary_leakage`;
- `excluded_summary`, `fallback_exclusions.by_reason` with count and
  `record_ids`, and `manual_review_accounting`;
- optional `docking_score_eligible_counts`, or `null` when no docking index is
  supplied.

The writer uses deterministic UTF-8 JSON, same-directory tempfile, fsync, and
`os.replace`, then returns an `ArtifactRef` with
`role="stratified_evaluation_summary"`.

### Boundaries

Always:

- Report train/val/test splits separately.
- Use canonical `residue_reaction_family`.
- Treat scaffold and protein cluster as primary generalization metrics.
- Report scaffold and protein-cluster leakage risks from the leakage report.
- Preserve excluded/fallback/manual-review accounting.

Never:

- Regenerate or mutate splits.
- Run Checkpoint C.
- Import RDKit, torch, PMDM, PocketFlow, or docking engines.
- Implement result writing, mmCIF export, docking execution, or evaluation
  workflows outside the split-aware report.
- Treat optional docking input as required.

### Testing Strategy

Golden fixtures cover valid split/leakage reports, schema/version/role failures,
assignment count mismatch, duplicate record ids, invalid splits, missing
assignment fields, scaffold and protein-cluster leakage risks, request-id-only
join behavior, per-split `EvaluationSummary` compatibility, per-family canonical
grouping, primary scaffold/protein-cluster metrics, fallback/manual-review
evidence, optional docking counts, deterministic writer output, and no heavy
dependency imports.
