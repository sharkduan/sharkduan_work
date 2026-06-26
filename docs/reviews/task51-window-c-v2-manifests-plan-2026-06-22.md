# Task 51 Window C Implementation Plan — V2 Manifests & Lazy Facade

**Date:** 2026-06-22
**Status:** Planning pass (no files modified)
**Mode:** Plan-only — `src/covalent_design/training/v2_manifests.py` + lazy public facade exports
**Dependencies:** Task 50 (verified), v1 `reports.py` / `checkpoints.py`, contracts types

---

## 1. Reference Architecture (source-driven)

### 1.1 What already exists

| Artifact | Location | Role in Task 51 |
|---|---|---|
| `TrainingRunManifest` (v1) | `contracts.types:824` | Dataclass shape to extend, not replace |
| `build_training_input_hashes()` | `training/reports.py:37` | Reused for records/split/rule/quality/visual hashes |
| `build_training_run_manifest()` | `training/reports.py:58` | V1 builder kept untouched; V2 builder wraps + extends |
| `training_run_manifest_to_dict()` | `training/reports.py:107` | Deterministic serialisation reference |
| `hash_resolved_config()` | `training/reports.py:26` | Reused for config hash |
| `sha256_file / sha256_bytes` | `training/reports.py:22-23` | Reused for all file hashes |
| `canonical_json` | `training/reports.py:14` | Reused for deterministic JSON encoding |
| `CheckpointMetadata` | `training/checkpoints.py:38` | Defines `CHECKPOINT_REQUIRED_INPUT_HASH_KEYS` — reused |
| `ContractEnvelope[T]` | `contracts.types:140` | Return type for all builders |
| `ValidationReceipt` | `contracts.types:93` | Receipt for envelope returns |
| `ContractErrorInfo` | `contracts.errors:20` | Structured error reporting |
| `BASELINE_MODE_NON_PMDM` / `BASELINE_MODE_PMDM` | `model/non_pmdm_baseline.py:30-31` | Frozen mode constants |
| `BASELINE_NOT_PMDM_WARNING` / `_CODE` | `model/non_pmdm_baseline.py:39,46` | Baseline warning for manifest |
| `check_pmdm_available()` | `model/pmdm_real_adapter.py` | PMDM status for manifest |
| `pmdm_backend_status_to_dict()` | `model/pmdm_real_adapter.py` | PMDM status serialisation |
| `V2TrainingDatasetIndex` | `training/v2_dataset.py:104` | Source of `records_path`, `split_name` for hashing key material |
| Lazy facade pattern | `training/__init__.py:12-62` | `_EXPORTS` dict + `__getattr__`, `__dir__` |
| `CONTRACT_VERSION` / `SCHEMA_VERSION` | `contracts.types:16-17` | Frozen version constants |

### 1.2 What does NOT exist yet (Task 51 scope)

- `V2TrainingRunManifest` dataclass
- `DependencyLockProvenance` dataclass
- `build_v2_training_input_hashes()` — V2 input hash builder
- `build_v2_training_run_manifest()` — V2 manifest builder
- `validate_v2_training_run_manifest()` — structural validation
- `v2_training_run_manifest_to_dict()` — deterministic JSON serialisation
- `v2_training_run_manifest_digest()` — manifest integrity SHA-256
- `hash_dependency_lock()` — lock file byte hash
- All public exports registered in `training/__init__.py` `_EXPORTS`

---

## 2. Module: `src/covalent_design/training/v2_manifests.py`

### 2.1 Design principles

1. **Additive, not replacement.** V1 `TrainingRunManifest` in `contracts.types` and v1 `reports.py` / `checkpoints.py` are untouched. V2 manifest is a new dataclass in `v2_manifests.py` with all v1-equivalent fields plus V2-specific extensions.

2. **Dependency lock provenance, not hash.** The dependency lock file's SHA-256 is recorded as a `DependencyLockProvenance` metadata object. It is NOT folded into the manifest's `input_hashes` dict or its integrity digest. Reason: the lock is environment-specific and may be regenerated; baking it into the manifest hash would break cross-machine reproducibility. The provenance *records which lock was used* without making the manifest hash depend on it.

3. **Envelope style.** All builder functions return `ContractEnvelope[V2TrainingRunManifest]` with a `ValidationReceipt` — same pattern as Task 49 `prepare_v2_dataset()` and Task 50 `run_v2_train()`.

4. **Deterministic.** All JSON output uses `canonical_json()` (sorted keys, compact separators, `ensure_ascii=False`). Manifest digest is `sha256:<64 lowercase hex>`.

5. **No checkpoint/weight artifacts.** Task 51 defines schemas and builders only. It must not create, read, or reference `.pt`, `.pth`, `.ckpt`, or any model weight files. Checkpoint refs in the manifest are URI strings only.

6. **No heavy deps.** Module import must not trigger `torch`, `rdkit`, `pmdm`, or `pocketflow` imports. Baseline mode constants and PMDM status functions are imported lazily or from lightweight contracts.

7. **Schema/contract version constants.** Reuse `SCHEMA_VERSION` and `CONTRACT_VERSION` from `contracts.types`.

---

### 2.2 Dataclasses

#### 2.2.1 `DependencyLockProvenance`

```python
@dataclass(frozen=True)
class DependencyLockProvenance:
    """Metadata about the dependency lock file used for this run.

    The lock hash is recorded as provenance metadata but is NOT folded into
    the manifest's input_hashes or digest.  This keeps manifests reproducible
    across environments that may regenerate their lock files independently.
    """

    lock_file_path: str = ""          # path or URI to the lock file
    lock_file_sha256: str = ""         # sha256:<64 hex> of raw lock file bytes
    lock_format: str = ""              # e.g. "conda-lock", "pip-freeze", "poetry-lock"
    generated_by: str = ""             # tool name (e.g. "conda-lock", "pip-tools")
    generated_at: str = ""             # ISO 8601 timestamp or empty
    schema_version: str = SCHEMA_VERSION
    contract_version: str = CONTRACT_VERSION
```

Fields rationale:
- `lock_file_path` — where the lock lives; required for audit trail
- `lock_file_sha256` — `sha256:<hex>` of file bytes, computed by `hash_dependency_lock()`
- `lock_format` — distinguishes conda-lock.yml from requirements.txt etc.
- `generated_by` / `generated_at` — provenance metadata from the tool itself

Validation rules:
- If `lock_file_path` is non-empty, `lock_file_sha256` must be present (non-empty)
- `lock_file_sha256` if present must match `sha256:<64 lowercase hex>` regex
- `lock_format` must be one of known values or empty

#### 2.2.2 `V2TrainingRunManifest`

```python
@dataclass(frozen=True)
class V2TrainingRunManifest:
    """Provenance manifest for one V2-beta training run.

    Extends v1 TrainingRunManifest semantics with V2-specific fields:
    baseline_mode, PMDM status, dependency lock provenance, and V2 gate
    report hashes (family_readiness_report, license_gate_report).
    """

    # -- identity & versioning --
    schema_version: str = SCHEMA_VERSION
    contract_version: str = CONTRACT_VERSION
    role: str = "v2_training_run_manifest"
    run_id: str = ""

    # -- hashes --
    training_config_resolved_hash: str = ""   # canonical JSON -> sha256
    input_hashes: Mapping[str, str] = field(default_factory=dict)
    # Required keys: records_jsonl, split_index, rule_table,
    #                quality_report, visual_check_index
    # V2-required keys: family_readiness_report, license_gate_report

    # -- model path --
    baseline_mode: str = ""             # "pmdm" | "non_pmdm_baseline"
    pmdm_status: Optional[Mapping[str, object]] = None
    # pmdm_status serialised from pmdm_backend_status_to_dict() when pmdm
    # mode was selected; None when baseline_mode != "pmdm"

    # -- dependency provenance (NOT hashed into manifest digest) --
    dependency_lock: Optional[DependencyLockProvenance] = None

    # -- output refs (URI strings only, no weight artifacts) --
    checkpoint_dir: str = ""
    train_metrics_uri: str = ""
    validation_metrics_uri: str = ""
    denominator_report_uri: str = ""

    # -- completion state --
    train_completed: bool = False
    epochs_completed: int = 0
    steps_completed: int = 0
    crash_recovery: Optional[Mapping[str, object]] = None

    # -- diagnostics --
    warnings: tuple[str, ...] = ()
    diagnostics: tuple[Mapping[str, object], ...] = ()
```

Key design decisions:
- **`baseline_mode`**: exactly `"pmdm"` or `"non_pmdm_baseline"`. Must be set explicitly; never auto-derived.
- **`pmdm_status`**: stored as a serialised dict (from `pmdm_backend_status_to_dict()`). Present only when `baseline_mode == "pmdm"`. When PMDM was unavailable, this captures `status: "unavailable"`, `reason: "license_unknown"`, `import_attempted: false`.
- **`input_hashes` V2 additions**: `family_readiness_report` and `license_gate_report` are V2-required keys on top of the v1 set.
- **`dependency_lock`**: a `DependencyLockProvenance` object or `None`. Stored as provenance metadata. Excluded from the manifest digest (see §2.4).
- **Checkpoint refs**: stored as URI strings (`checkpoint_dir`, `train_metrics_uri`, etc.). Task 51 does not validate that these paths exist — that is a Task 50 responsibility at smoke time.
- No `model_weights_uri`, `optimizer_state_uri`, or `bond_type_vocabulary` fields — those belong to `CheckpointMetadata` (v1), not the training run manifest. If a future consumer needs them, it reads the checkpoint YAML separately.

---

### 2.3 Constants

```python
V2_TRAINING_REQUIRED_INPUT_HASH_KEYS: tuple[str, ...] = (
    "records_jsonl",
    "split_index",
    "rule_table",
    "quality_report",
    "visual_check_index",
    "family_readiness_report",
    "license_gate_report",
)

V2_TRAINING_OPTIONAL_INPUT_HASH_KEYS: tuple[str, ...] = (
    "release_gate",
)

VALID_BASELINE_MODES: tuple[str, ...] = ("pmdm", "non_pmdm_baseline")
```

The V2 set adds `family_readiness_report` and `license_gate_report` as required. `release_gate` remains optional (same as v1).

---

### 2.4 Manifest digest design (dependency lock NOT forged in)

The manifest digest is computed as:

```python
def v2_training_run_manifest_digest(manifest: V2TrainingRunManifest) -> str:
    data = v2_training_run_manifest_to_dict(manifest)
    # Remove dependency_lock before hashing — it's provenance metadata only
    data.pop("dependency_lock", None)
    return sha256_bytes(canonical_json(data).encode("utf-8"))
```

This means:
- Two runs with identical config, data, model mode, and outputs produce the **same digest** even if run on different machines with different lock files.
- The `dependency_lock` is still in the manifest record (stored, serialised, auditable) — it's just not part of the integrity hash.
- If you change the lock file and re-run, you get a new provenance record but the same digest (assuming nothing else changed).

---

### 2.5 Public functions

#### 2.5.1 `hash_dependency_lock(path) -> str`

Reads a dependency lock file from `path`, computes `sha256:<hex>` of raw bytes. Returns empty string if path is empty/None. Raises `OSError` on unreadable files (caught by the caller, not swallowed).

```python
def hash_dependency_lock(path: object) -> str:
    """Return sha256:<hex> of a dependency lock file's raw bytes.

    Returns "" if path is empty or None.
    Raises OSError if the file exists but is unreadable.
    """
```

#### 2.5.2 `build_v2_training_input_hashes(**kwargs) -> dict[str, str]`

Extends v1 `build_training_input_hashes()` with V2 gate reports.

```python
def build_v2_training_input_hashes(
    *,
    records_path: object,
    split_index_path: object,
    rule_table_path: object,
    quality_report_path: object,
    visual_check_index_path: object,
    family_readiness_report_path: object,
    license_gate_report_path: object,
    release_gate_path: object = None,
) -> dict[str, str]:
```

Delegates to the v1 builder for the five shared keys, then adds:
- `family_readiness_report`: `sha256_file(family_readiness_report_path)`
- `license_gate_report`: `sha256_file(license_gate_report_path)`
- `release_gate`: optional, same as v1

#### 2.5.3 `build_v2_training_run_manifest(**kwargs) -> ContractEnvelope[V2TrainingRunManifest]`

The main builder. Returns an envelope — failed envelope on validation errors, success envelope otherwise.

```python
def build_v2_training_run_manifest(
    *,
    run_id: str,
    resolved_config: object,
    records_path: object,
    split_index_path: object,
    rule_table_path: object,
    quality_report_path: object,
    visual_check_index_path: object,
    family_readiness_report_path: object,
    license_gate_report_path: object,
    baseline_mode: str,
    checkpoint_dir: str = "",
    train_metrics_uri: str = "",
    validation_metrics_uri: str = "",
    denominator_report_uri: str = "",
    release_gate_path: object = None,
    dependency_lock_path: object = None,
    dependency_lock_format: str = "",
    dependency_lock_generated_by: str = "",
    dependency_lock_generated_at: str = "",
    pmdm_status: Optional[Mapping[str, object]] = None,
    train_completed: bool = False,
    epochs_completed: int = 0,
    steps_completed: int = 0,
    crash_recovery: Optional[Mapping[str, object]] = None,
    warnings: tuple[str, ...] = (),
    diagnostics: tuple[Mapping[str, object], ...] = (),
) -> ContractEnvelope[V2TrainingRunManifest]:
```

**Validation gates (fail closed):**

1. `run_id` must not be empty → `V2_MANIFEST_EMPTY_RUN_ID`
2. `baseline_mode` must be in `VALID_BASELINE_MODES` → `V2_MANIFEST_BASELINE_MODE_INVALID`
3. If `baseline_mode == "pmdm"`, `pmdm_status` must be provided → `V2_MANIFEST_PMDM_STATUS_MISSING`
4. If `baseline_mode == "non_pmdm_baseline"`, `pmdm_status` must be absent or `None` → `V2_MANIFEST_PMDM_STATUS_UNEXPECTED`
5. `epochs_completed` and `steps_completed` must be non-negative
6. File-not-found on any required input path → `V2_MANIFEST_INPUT_FILE_MISSING`
7. File-unreadable on any required input path → `V2_MANIFEST_INPUT_FILE_UNREADABLE`

**Dependency lock handling:**
- If `dependency_lock_path` is provided and non-empty:
  - Attempt `hash_dependency_lock(dependency_lock_path)`
  - Success → create `DependencyLockProvenance` with the computed hash
  - `OSError` → return failed envelope with `V2_MANIFEST_DEPENDENCY_LOCK_UNREADABLE`
  - The `DependencyLockProvenance` is stored in `manifest.dependency_lock` but excluded from the manifest digest

**PMDM status handling:**
- When `baseline_mode == "pmdm"`, the caller should pass `pmdm_backend_status_to_dict(check_pmdm_available())`
- When PMDM is unavailable, `pmdm_status` captures `{"status": "unavailable", "reason": "license_unknown", "import_attempted": false}`
- The manifest does NOT import `pmdm_real_adapter` at module level — the caller resolves PMDM status before passing it in

#### 2.5.4 `validate_v2_training_run_manifest(manifest) -> ValidationReceipt`

Structural validation of an already-constructed manifest. Used when loading a manifest from storage (future read path). Checks:

- `run_id` non-empty
- `baseline_mode` in `VALID_BASELINE_MODES`
- `input_hashes` contains all `V2_TRAINING_REQUIRED_INPUT_HASH_KEYS`
- Each hash value matches `sha256:<64 lowercase hex>`
- `baseline_mode == "pmdm"` → `pmdm_status` is not None
- `baseline_mode == "non_pmdm_baseline"` → `pmdm_status` is None
- `training_config_resolved_hash` is `sha256:<hex>` or empty
- Non-negative counters
- `dependency_lock.lock_file_sha256` format valid if present

Returns `ValidationReceipt(passed=True/False, errors=(...), warnings=(...))`.

#### 2.5.5 `v2_training_run_manifest_to_dict(manifest) -> dict[str, object]`

Deterministic JSON-compatible serialisation. Uses `canonical_json`-style key ordering. Includes `dependency_lock` serialised as a nested dict. Maps `pmdm_status` as-is (already a dict).

Output shape:
```json
{
  "schema_version": "1",
  "contract_version": "1.0.0",
  "role": "v2_training_run_manifest",
  "run_id": "...",
  "training_config_resolved_hash": "sha256:...",
  "input_hashes": { "family_readiness_report": "sha256:...", ... },
  "baseline_mode": "non_pmdm_baseline",
  "pmdm_status": null,
  "dependency_lock": {
    "lock_file_path": "...",
    "lock_file_sha256": "sha256:...",
    "lock_format": "conda-lock",
    "generated_by": "conda-lock",
    "generated_at": "2026-06-22T...",
    "schema_version": "1",
    "contract_version": "1.0.0"
  },
  "checkpoint_dir": "...",
  "train_metrics_uri": "...",
  "validation_metrics_uri": "...",
  "denominator_report_uri": "...",
  "train_completed": false,
  "epochs_completed": 0,
  "steps_completed": 0,
  "crash_recovery": null,
  "warnings": [],
  "diagnostics": []
}
```

#### 2.5.6 `v2_training_run_manifest_digest(manifest) -> str`

SHA-256 of the canonical JSON of `to_dict()` output, **with `dependency_lock` removed** before hashing.

Returns `"sha256:<64 lowercase hex>"`.

#### 2.5.7 `v2_training_run_manifest_from_dict(data) -> V2TrainingRunManifest`

Deserialisation helper for reading manifests back from JSON. Reconstructs the frozen dataclass including nested `DependencyLockProvenance`.

---

### 2.6 Error codes (all `owner = "training"`)

| Code | Meaning |
|---|---|
| `V2_MANIFEST_EMPTY_RUN_ID` | `run_id` is empty or whitespace-only |
| `V2_MANIFEST_BASELINE_MODE_INVALID` | `baseline_mode` not in `("pmdm", "non_pmdm_baseline")` |
| `V2_MANIFEST_PMDM_STATUS_MISSING` | PMDM mode selected but no `pmdm_status` provided |
| `V2_MANIFEST_PMDM_STATUS_UNEXPECTED` | `non_pmdm_baseline` mode but `pmdm_status` provided |
| `V2_MANIFEST_INPUT_FILE_MISSING` | Required input file not found at path |
| `V2_MANIFEST_INPUT_FILE_UNREADABLE` | Required input file exists but cannot be read |
| `V2_MANIFEST_DEPENDENCY_LOCK_UNREADABLE` | Lock file path provided but file is unreadable |
| `V2_MANIFEST_MISSING_REQUIRED_HASH_KEY` | `input_hashes` missing a V2-required key |
| `V2_MANIFEST_INVALID_HASH_FORMAT` | A hash value does not match `sha256:<64 hex>` |
| `V2_MANIFEST_NEGATIVE_COUNTER` | `epochs_completed` or `steps_completed` is negative |

---

## 3. Lazy public facade: `src/covalent_design/training/__init__.py`

### 3.1 New entries in `_EXPORTS` dict

```python
"DependencyLockProvenance": ("covalent_design.training.v2_manifests", "DependencyLockProvenance"),
"V2TrainingRunManifest": ("covalent_design.training.v2_manifests", "V2TrainingRunManifest"),
"build_v2_training_input_hashes": ("covalent_design.training.v2_manifests", "build_v2_training_input_hashes"),
"build_v2_training_run_manifest": ("covalent_design.training.v2_manifests", "build_v2_training_run_manifest"),
"hash_dependency_lock": ("covalent_design.training.v2_manifests", "hash_dependency_lock"),
"validate_v2_training_run_manifest": ("covalent_design.training.v2_manifests", "validate_v2_training_run_manifest"),
"v2_training_run_manifest_digest": ("covalent_design.training.v2_manifests", "v2_training_run_manifest_digest"),
"v2_training_run_manifest_from_dict": ("covalent_design.training.v2_manifests", "v2_training_run_manifest_from_dict"),
"v2_training_run_manifest_to_dict": ("covalent_design.training.v2_manifests", "v2_training_run_manifest_to_dict"),
```

`__all__` is auto-sorted from `_EXPORTS` keys — no manual update needed.

### 3.2 No change to existing exports

The v1 `build_training_input_hashes`, `build_training_run_manifest`, and `training_run_manifest_to_dict` remain in `_EXPORTS` pointing at `reports.py`. The V2 functions are separate names in `v2_manifests.py`.

---

## 4. `__all__` for `v2_manifests.py`

```python
__all__ = [
    "DependencyLockProvenance",
    "V2TrainingRunManifest",
    "V2_TRAINING_REQUIRED_INPUT_HASH_KEYS",
    "V2_TRAINING_OPTIONAL_INPUT_HASH_KEYS",
    "VALID_BASELINE_MODES",
    "build_v2_training_input_hashes",
    "build_v2_training_run_manifest",
    "hash_dependency_lock",
    "validate_v2_training_run_manifest",
    "v2_training_run_manifest_digest",
    "v2_training_run_manifest_from_dict",
    "v2_training_run_manifest_to_dict",
]
```

---

## 5. Test plan: `tests/training/test_v2_manifests.py`

### 5.1 Test categories

1. **Import existence** — every public name in `__all__` is importable from `covalent_design.training.v2_manifests`
2. **Facade lazy loading** — importing `covalent_design.training` does NOT import `v2_manifests` until an attribute is accessed
3. **`DependencyLockProvenance` construction** — valid construction, empty defaults, immutability
4. **`V2TrainingRunManifest` construction** — valid minimal manifest, immutability, field types
5. **`build_v2_training_input_hashes`** — returns dict with all V2-required keys, hash prefix format, deterministic, matches `sha256_file` for file-based hashes
6. **`build_v2_training_run_manifest` success** — valid `non_pmdm_baseline` manifest, valid `pmdm` manifest with `pmdm_status`, envelope shape
7. **`build_v2_training_run_manifest` failures**:
   - Empty `run_id` → `V2_MANIFEST_EMPTY_RUN_ID`
   - Invalid `baseline_mode` → `V2_MANIFEST_BASELINE_MODE_INVALID`
   - PMDM mode without `pmdm_status` → `V2_MANIFEST_PMDM_STATUS_MISSING`
   - `non_pmdm_baseline` with `pmdm_status` → `V2_MANIFEST_PMDM_STATUS_UNEXPECTED`
   - Missing input file → `V2_MANIFEST_INPUT_FILE_MISSING`
   - Unreadable input file → `V2_MANIFEST_INPUT_FILE_UNREADABLE`
   - Unreadable dependency lock → `V2_MANIFEST_DEPENDENCY_LOCK_UNREADABLE`
   - Negative epoch/step → validation failure
8. **Dependency lock provenance** — lock hash appears in manifest dict, lock hash is NOT in manifest digest, `DependencyLockProvenance` round-trips through JSON
9. **Manifest digest stability** — same inputs → same digest; different `dependency_lock` → same digest (proves lock is excluded); different `baseline_mode` → different digest
10. **`validate_v2_training_run_manifest`** — valid manifest passes (empty errors), missing required hash fails, invalid hash format fails, PMDM/baseline consistency checks
11. **`v2_training_run_manifest_to_dict`** — all keys present, JSON-serializable, deterministic key order, `pmdm_status` null for baseline mode
12. **`v2_training_run_manifest_from_dict`** — round-trips dict → manifest → dict, handles missing optional fields (dependency_lock, pmdm_status, crash_recovery)
13. **No heavy imports** — importing `v2_manifests` does not pull in `torch`, `rdkit`, `pmdm`, or `pocketflow`
14. **No checkpoint/weight artifacts** — `v2_manifests.py` source contains no references to `.pt`, `.pth`, `.ckpt`, `model_weights`, `checkpoint_manifest_path`, `checkpoint_output`, or `real data root`
15. **Baseline mode constants** — `non_pmdm_baseline` manifest records `is_pmdm: false` context, warning text present in diagnostics when baseline selected; `pmdm` manifest records PMDM status dict
16. **Deterministic JSON** — multiple calls to `to_dict()` produce identical output

### 5.2 Fixture directory

`tests/fixtures/training/v2_manifests/` containing:
- `records.jsonl` — 1-record JSONL (shared or copied)
- `split_index.json` — role: `split_index`
- `rule_table.yml` — families block
- `quality_report.json` — role: `quality_report`
- `visual_check_index.json` — role: `visual_check_index`
- `family_readiness_report.json` — role: `family_readiness_report`
- `license_gate_report.json` — role: `license_gate_report`
- `release_gate.json` — role: `release_gate`
- `environment.lock.yml` — placeholder lock file for `hash_dependency_lock` tests

---

## 6. Key boundary rules (what Task 51 must NOT do)

1. No checkpoint weight files (`.pt`, `.pth`, `.ckpt`) referenced, read, or written
2. No checkpoints module import at module level (lazy import only if needed)
3. No `D:\codex_work\data` references
4. No training loop execution, model forward, sampling, inference, evaluation
5. No publication claims
6. No heavy dependency imports (torch, rdkit, pmdm, pocketflow)
7. No modification to v1 `reports.py`, `checkpoints.py`, or `contracts/types.py`
8. No dependency lock hash folded into manifest digest
9. No auto-derivation of `baseline_mode` from PMDM status
10. No writing of manifest files to disk (JSON serialisation is in-memory; file I/O is future scope)

---

## 7. Verification command (planned)

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/training/test_v2_manifests.py -q
```

---

## 8. Implementation order (incremental)

| Step | What | Delivers |
|---|---|---|
| 1 | `DependencyLockProvenance` dataclass | Immutable, defaults, `to_dict()` |
| 2 | `V2TrainingRunManifest` dataclass | All fields, defaults, frozen |
| 3 | Constants (`V2_TRAINING_REQUIRED_INPUT_HASH_KEYS`, etc.) | Frozen tuples |
| 4 | `hash_dependency_lock(path)` | File byte hash |
| 5 | `build_v2_training_input_hashes()` | Delegates to v1 + adds V2 keys |
| 6 | `build_v2_training_run_manifest()` | Envelope return, all validation gates |
| 7 | `validate_v2_training_run_manifest()` | Structural validation |
| 8 | `v2_training_run_manifest_to_dict()` | Deterministic JSON dict |
| 9 | `v2_training_run_manifest_from_dict()` | Deserialisation |
| 10 | `v2_training_run_manifest_digest()` | SHA-256 excluding dependency_lock |
| 11 | `__all__` and module docstring | Module boundary |
| 12 | Lazy facade entries in `training/__init__.py` | 9 new `_EXPORTS` entries |
| 13 | Test fixtures + all test categories | `test_v2_manifests.py` |
| 14 | Full verification: `pytest tests/training/test_v2_manifests.py -q` | All pass |
