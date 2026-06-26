# V2 Training And Tuning Spec

Date: 2026-06-16
Status: hardened planning spec

## Dataset Input

Training consumes v1-compatible finalized records plus split index, visual checks, quality report, family readiness report, and license audit references. It must not train on records blocked by license, family readiness, visual status, quality policy, or split policy.

### V2 Dataset Eligibility Index (Task 49)

Task 49 provides `prepare_v2_dataset(records_path, split_index_path, split_name, *, visual_check_index_path, quality_report_path, family_readiness_report_path, license_gate_report_path, policy=None) -> ContractEnvelope[V2TrainingDatasetIndex]`.

The API builds one split-specific index per call for `train`, `val`, or `test`. It reads only explicit artifact paths supplied by the caller and does not read `D:\codex_work\data`, raw source roots, model outputs, or training manifests.

The default `V2TrainingDataPolicy` is conservative:

- `first_core_only=True`
- `exclude_visual_blocked=True`
- `exclude_q2=False`
- `accepted_quality_tiers=("Q0", "Q1", "Q2")`
- `allow_manual_exempt=True`

Eligibility gates execute in a deterministic priority chain:

1. Split assignment: mismatched split, `excluded`, or missing split assignment excludes the record.
2. License audit: missing, `blocked`, `unknown`, unsatisfied `restricted`, failed audit, invalid manual exemption, and `manual_exempt` with `training_eligible=false` exclude the record.
3. Family readiness: `blocked`, `deferred`, `partial`, and missing family readiness exclude the record.
4. Visual status: non-`pass` visual status excludes the record when `exclude_visual_blocked=True`.
5. Quality tier: tiers outside `accepted_quality_tiers` exclude the record.
6. Linkage policy: multi-linkage records are excluded when `first_core_only=True`.
7. Q2 policy: Q2 is included by default and excluded only when `exclude_q2=True`.

`manual_exempt` remains a distinct license status. It is not normalized to `allowed`; it is eligible only when both the record metadata and license gate report identify manual intake and the license gate report records `training_eligible=true`. Manual exemptions with download intake are excluded as `excluded_manual_exempt_non_manual`; manual exemptions with failed audit eligibility are excluded as `excluded_manual_exempt_audit_failed`.

`V2TrainingDatasetIndex` preserves eligible `V2TrainingRecordEntry` fields needed by downstream training: `record_id`, residue-reaction family, quality tier, visual status, license status, family readiness status, fallback/manual review metadata, source/intake mode, and artifact references. Excluded records carry a deterministic primary reason plus all applicable reasons, source/intake provenance, and source license `reason_codes` as `license_reason_codes`.

Task 49 performs only minimum artifact role presence validation. If a record has no usable artifact roles, it is excluded as `excluded_missing_artifact_roles`. Artifact path existence, readability, byte size, and checksum validation remain Task 50 fail-before-tensor responsibilities.

`V2ExclusionSummary` is a count-conservation report: `eligible_count + excluded_count == input_count`, and `excluded_count == sum(primary_reason_counts.values())`. Task 49 does not compute Task 23 masks, losses, model forward passes, checkpoints, or training artifacts.

## Model Input

Training reuses:

- `ModelBatch`
- stepwise candidates
- PMDM adapter output vocabulary
- covalent heads
- final decode diagnostics

PyTorch tensor adapters may sit behind these contracts, but public contract objects stay serializable.

### PMDM Adapter Output Vocabulary

Task 47 freezes the real-PMDM adapter smoke vocabulary without executing PMDM while its license remains unknown. The seven required keys are:

- `ligand_atom_features`
- `protein_atom_features`
- `ligand_coords_denoised`
- `position_loss`
- `atom_type_loss`
- `timestep`
- `num_atom`

The two optional keys are `ligand_pair_features` and `protein_ligand_pair_features`. They are present only when the corresponding `ModelConfig` feature dimensions are positive, and absent when those dimensions are zero.

When PMDM is blocked by `license_unknown`, PMDM-mode execution records structured unavailability with `status: unavailable`, `reason: license_unknown`, and `import_attempted: false`. It must not silently switch to `non_pmdm_baseline`.

### Baseline Mode Contract (Task 48)

Task 48 provides an explicit non-PMDM baseline forward path. It must not self-activate: the consumer must explicitly set `baseline_mode = "non_pmdm_baseline"` before invoking `forward_non_pmdm_baseline()`.

The baseline output matches the PMDM-compatible vocabulary shape, but it carries persistent machine-readable diagnostics: `baseline_mode: "non_pmdm_baseline"`, `is_pmdm: false`, and warning text `baseline is not PMDM; this is a smoke-only path`. Training manifests, checkpoint metadata, and evaluation reports that consume baseline output must preserve this distinction.

Task 47 PMDM mode and Task 48 baseline mode are mutually exclusive at the call site. PMDM blocked/unavailable status does not automatically activate the baseline path.

## Training Objective

V2-beta objective remains aligned with v1:

- PMDM position loss,
- PMDM atom loss,
- covalent edge loss,
- covalent bond type loss,
- covalent geometry loss,
- family auxiliary loss.

Real numerical loss implementation may replace smoke pseudo-losses only after Task 46-50 validate tensor and PMDM seams.

## Loss Functions

The first real loss implementation must:

- preserve v1 `LossReport` required components,
- preserve mask and denominator accounting,
- keep forced-positive behavior auditable,
- reject denominator drift.

## Checkpoint Policy

Checkpoint metadata must include:

- environment manifest hash,
- dependency lock hash or explicit dependency-lock provenance,
- source/data manifest hashes,
- Task 49 dataset/index eligibility hash,
- family readiness hash,
- training config hash,
- training summary hash/ref,
- checkpoint refs,
- rule table hash,
- model contract version,
- baseline mode (`pmdm` or `non_pmdm_baseline`).

### V2 Checkpoint And Experiment Manifest (Task 51)

Task 51 implements `src/covalent_design/training/v2_manifests.py` as a schema-only manifest boundary. The public builder is `build_v2_checkpoint_experiment_manifest(...) -> ContractEnvelope[V2CheckpointExperimentManifest]`. It does not start training, write checkpoint payloads, read `D:\codex_work\data`, or implement later search/sampling behavior.

`V2CheckpointExperimentManifest` records deterministic JSON fields for `manifest_id`, `run_id`, `environment_hash`, `dependency_lock`, `data_hashes`, `dataset_index_hash`, `family_readiness_hash`, `training_config_hash`, `training_summary_hash`, `training_summary_ref`, `checkpoint_refs`, `baseline_mode`, `is_pmdm`, `pmdm_status`, warnings, and diagnostics. Hash values use `sha256:<64 lowercase hex>`.

Dependency lock handling is explicit: when no verified lock file exists, the manifest records `dependency_lock.status = "not_available"`, `lock_hash = null`, and a reason. This is not a verified lock hash and must not be treated as one. PMDM-mode manifests require `dependency_lock.status = "available"` with a valid lock hash.

Baseline manifests preserve `baseline_mode="non_pmdm_baseline"` and `is_pmdm=false`. A manifest with `baseline_mode="pmdm"` and `pmdm_status` of unavailable, blocked, or license unknown is invalid. Missing environment, dependency lock provenance, data, dataset, family readiness, config, training summary, or checkpoint-ref provenance fails with structured `V2_MANIFEST_*` errors.
## Hyperparameter Search

The first search is tiny and budget-controlled:

- fixed `trial_count`,
- fixed random `seeds`,
- fixed split and Task 49 gate input references,
- explicit `runtime_budget_seconds`,
- deterministic per-trial config and result hashes,
- selected checkpoint justification from one frozen metric,
- failed-trial reporting without silent promotion.

Task 52 implements the lightweight entrypoint:

```powershell
$env:PYTHONPATH='src'
python -m covalent_design.training.cli.v2_tune --config configs/v2_tiny_sweep.yml
python -m covalent_design.training.cli.v2_full_beta_train --config configs/v2_full_beta_train.yml
```

The tiny sweep config is intentionally explicit. It records `trial_count`,
`runtime_budget_seconds`, comma-separated `seeds`, `selection_metric`,
`selection_mode`, `device`, `model_mode`, and the same Task 49 gate inputs used
by Task 50 (`records_path`, `split_index_path`, `visual_check_index_path`,
`quality_report_path`, `family_readiness_report_path`, and
`license_gate_report_path`). Each trial reuses the Task 50 training boundary
rather than rebuilding dataset or tensor validation logic. In the lightweight smoke
implementation, `runtime_budget_seconds` is a required recorded budget contract, not a
wall-clock interrupter; hard timeout enforcement belongs to a later heavy/full run if
needed. Seeds provide deterministic trial identity and hashes in the smoke loop; Task
50 currently has no random training path to consume them as stochastic state.

`V2TuningSummary` is deterministic JSON-compatible data. It records trial
ordering, selected-trial metadata, `sweep_config_hash`, `sweep_result_hash`,
per-trial `config_hash`, per-trial `result_hash`, `failed_trial_count`, and
`selection_justification`. Failed trials are represented as trial results with
`status="failed"` and structured error fields; they remain visible in the
report and are never eligible for selection. The selected checkpoint reference
is manifest-style metadata for downstream binding and does not create a model
payload.

## Full Beta Training Harness (Task 52.5)

Task 52.5 adds the numbered full-beta harness after tiny tuning and before Checkpoint V2-E. The public API is `run_v2_full_beta_train(config) -> ContractEnvelope[V2FullBetaSummary>` and the package CLI is:

```powershell
$env:PYTHONPATH='src'
python -m covalent_design.training.cli.v2_full_beta_train --config configs/v2_full_beta_train.yml
```

The harness composes existing boundaries instead of rebuilding them:

- Task 49 provides split-specific eligibility and license/family/visual/quality gates.
- Task 50 validates eligible artifact references and emits the deterministic training summary.
- Task 51 provides the checkpoint/experiment manifest schema.
- Task 52 provides selected-trial and frozen-metric tuning evidence.

`V2FullBetaSummary` records `execution_mode`, `device`, `model_mode`, `checkpoint_policy`, `checkpoint_selection_metric`, selected checkpoint reference, selection justification, nested training/tuning summaries, manifest validation status, `outputs_written`, `real_data_accessed`, structured errors, and `summary_hash`.

The default fixture config uses `execution_mode="fixture"` and must not read raw local data roots or write checkpoint payloads. `execution_mode="heavy_manual"` requires explicit controller authorization before real local data paths are used. If CUDA, PMDM, a verified dependency lock, or real-data authorization is unavailable, the harness returns structured failure and leaves `selected_checkpoint_ref=null`.

Task 52.5 does not implement later pipeline stages, evaluation metrics, or model-payload publication. Heavy checkpoint payloads remain local/manual evidence and are not tracked by default.
## Training Manifest

Every run records:

- run id,
- start/end time,
- environment hash,
- data hash,
- checkpoint refs,
- metrics,
- failure diagnostics,
- whether PMDM or fallback was used,
- PMDM status details when PMDM is unavailable (`status`, `reason`, and `import_attempted`),
- explicit `baseline_mode` when the Task 48 baseline is selected, set to exactly `non_pmdm_baseline` and never auto-derived or defaulted from PMDM unavailability.

## Runtime Budget

The beta budget is intentionally small. Exact limits are set in Task 52, but the plan must support CPU smoke, single-GPU smoke, and small full run modes.

## Smoke And Full Modes

- CPU smoke: Task 50 implemented package CLI smoke path. It consumes Task 49 V2 eligibility inputs, validates artifact existence/readability/bytes/checksum before tensor construction, selects the explicit non-PMDM baseline mode, preserves a smoke `LossReport` and denominators, and emits deterministic JSON without requiring CUDA.
- GPU smoke: Task 50 config explicitly requires CUDA. If CUDA is unavailable, the CLI/API returns structured `V2_TRAIN_CUDA_UNAVAILABLE` without traceback; successful heavy GPU execution remains manual-profile evidence.
- Full beta run: Task 52.5 provides the numbered harness over ready families. Fixture mode succeeds deterministically; heavy/manual mode may return structured unavailable or unauthorized status. Task 50 still does not write checkpoint manifests, model payloads, or publication-performance claims.

## Verification Commands

Planned commands:

```bash
python -m covalent_design.training.cli.v2_train --config configs/v2_train_cpu_smoke.yml
python -m covalent_design.training.cli.v2_train --config configs/v2_train_gpu_smoke.yml
python -m covalent_design.training.cli.v2_tune --config configs/v2_tiny_sweep.yml
python -m covalent_design.training.cli.v2_full_beta_train --config configs/v2_full_beta_train.yml
```

Task 50 finalizes `python -m covalent_design.training.cli.v2_train --config configs/v2_train_cpu_smoke.yml` as the lightweight CPU smoke entrypoint. The GPU command is manual-profile because it requires CUDA. Developer scripts may wrap these commands only as local helpers.
