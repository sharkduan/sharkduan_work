# Task 17 Model Batch Contract: Data Release Gate to ModelBatch Boundary

## Status

Accepted

## Date

2026-05-26

## Context

Task 17 is the first model boundary after the ETL pipeline (Tasks 1–16). It must convert accepted `records.jsonl` into typed `ModelBatch` instances without ambiguity. The upstream Data Release Gate (Checkpoint A) and the downstream model/training tasks depend on clear contracts for:

- What exactly Task 17 consumes as input
- Which records are eligible for batch construction
- How artifact references are validated before tensor construction
- What error codes signal upstream problems
- How static (Task 12) and dynamic (Task 18) edge candidates relate
- Where types live in the package hierarchy
- What tensor shape/dtype/convention guarantees exist

This ADR freezes the answers so that Tasks 17–25 can be implemented in parallel without conflicting assumptions.

## Decision

### 1. Input bundle

Task 17 consumes a single `records.jsonl` — the finalized Task 13 output containing accepted records with five artifact roles (`protein_atom_table`, `ligand_atom_table`, `ligand_bond_table`, `coordinates`, `edge_candidates`). The Data Release Gate (Checkpoint A: quality report confirms `all_sources_complete_for_v1`, `reconciled == true`, `visual_blocked_count == 0`) is a **governance precondition** checked before Task 17 is invoked. It is not embedded in the batch constructor as a runtime check.

Rationale: If Task 17 depended on Task 16 (quality report), ETL changes would block model development. Separating governance from runtime allows parallel iteration.

### 2. ModelBatch structure — provenance + computation layers

`ModelBatch` is split into two layers:

- **Provenance layer** (`BatchRecordHeader`): per-record metadata (`record_id`, `residue_reaction_family`, `quality_tier`, `visual_check_status`, `chemical_state_status`, `target_atom_identity`, `target_atom_index`, `target_atom_artifact_role`, `split_assignment`, `fallback_reason`, `artifact_refs`). Consumed by `inspect_batch`, `TrainingRunManifest`, and audit tooling.
- **Computational layer** (`BatchTensors`): expected tensor shapes, dtypes, and coordinate frame. Actual tensor data is loaded by the consumer (PMDM adapter) from the referenced artifact files.

Rationale: `inspect_batch` requires artifact-level provenance for debugging, but model forward should not carry per-record provenance in its hot path. Separation avoids both problems.

### 2a. Reactive-site / target-atom contract

Task 17 must not leave the reactive site implicit inside atom-table artifacts. `BatchRecordHeader` carries:

- `target_atom_identity`: the shared `ProteinAtomIdentity` locator, resolved from the `protein_atom_table` artifact (chain_id, residue_number, residue_name) during Phase 2 artifact metadata reading.
- `target_atom_index`: the row/index into the `protein_atom_table` artifact, sourced from `core_labels.target_atom_index`.
- `target_atom_artifact_role`: constant `"protein_atom_table"`, naming the authoritative source artifact.

Missing identity or index is a constructor/validator error before tensor construction. If rule-required chemical state is unavailable, the record still exposes the target atom fields and reports `chemical_state_status = "unavailable"` before raising `MODEL_BATCH_REQUIRED_STATE_UNAVAILABLE` at batch construction.

### 3. Record eligibility in Task 17 vs Task 22

Task 17 does NOT exclude records based on quality tier (Q0/Q1/Q2), visual check status, split assignment, or fallback reason. All accepted records with valid artifacts are eligible for batch construction.

Exclusion rules (first_core_only, exclude_visual_blocked, exclude_q2, split filtering) are Task 22 (training dataset) responsibility via `TrainingDataPolicy`.

Rationale: A batch constructor should convert records to tensors. A dataset builder should filter for training suitability. Conflating them prevents downstream flexibility (e.g., using the same batch for inference, or comparing Q2-included vs Q2-excluded training).

### 4. Chemical state handling

Task 17 does not read the rule table and therefore does not decide per family whether chemical state is optional. The finalized Task 13 `records.jsonl` input must already carry `metadata.chemical_state.status` for every accepted record. Missing `metadata.chemical_state` or explicit `status = "unavailable"` is treated conservatively as `MODEL_BATCH_REQUIRED_STATE_UNAVAILABLE` (fail-before-tensor).

Records with `inferred` chemical state (with recorded tool/version/confidence) enter the batch with `chemical_state_status = "inferred"` in `BatchRecordHeader`. Downstream gates (Task 20/21) make per-check decisions based on confidence.

Rationale: ADR 0033 already established that missing required state must not pass by default. The batch constructor is the correct enforcement point because it validates artifact presence and completeness, while family-specific optionality remains an upstream normalization/rule-table responsibility.

### 5. Static vs dynamic edge candidates

- **Static edge candidates** (Task 12, artifact role `"edge_candidates"`): built once from ground-truth coordinates. Provide positive-edge labels, negative-edge labels, and denominator statistics for supervision. Task 17 validates their existence and checksum and records them in ``ModelBatch.static_edge_candidates_refs: Mapping[str, ArtifactRef]`` (a ``record_id → ArtifactRef`` mapping). Per-edge contents (positive label identity, bond type, per-candidate metadata) are consumed later by Task 18, not by ``make_model_batch()`` itself.
- **Stepwise candidates** (Task 18, types `StepwiseCandidate` / `StepwiseCandidateSet`): rebuilt at every denoising timestep from current noisy/generated ligand coordinates. Positive label is force-included when noise moves it outside the candidate radius.

These entities MUST NOT share an unqualified type or variable name. Task 12's artifact role name `"edge_candidates"` is unchanged (backward compatible with Tasks 1–16).

Rationale: Using static candidates directly as model-forward candidates would create a train/inference skew — training would use ground-truth-coordinate candidates while inference would use generated-coordinate candidates.

### 6. MODEL_BATCH error codes

Six error codes, all owner `"model"`:

| Code | Meaning |
|---|---|
| `MODEL_BATCH_ARTIFACT_MISSING` | A required artifact ref points to a non-existent file |
| `MODEL_BATCH_ARTIFACT_UNREADABLE` | An artifact file exists but cannot be parsed |
| `MODEL_BATCH_ARTIFACT_CHECKSUM_MISMATCH` | Artifact sha256 does not match the ref |
| `MODEL_BATCH_ARTIFACT_ROLE_MISSING` | A record lacks a required artifact role (e.g., `coordinates`) |
| `MODEL_BATCH_CONTRACT_VERSION_UNSUPPORTED` | An artifact's `contract_version` is incompatible |
| `MODEL_BATCH_REQUIRED_STATE_UNAVAILABLE` | Rule-required chemical state is missing |

`MODEL_BATCH_RELEASE_GATE_FAILED` is intentionally excluded — release gate is governance, not runtime.

### 7. Type placement

Types referenced by two or more packages live in `covalent_design.contracts.types`. Package-specific types live in their respective modules.

| Type | Location | Cross-package? |
|---|---|---|
| `ArtifactRef`, `ValidationReceipt`, `ContractEnvelope` | `contracts/types.py` | infrastructure |
| `ProteinAtomIdentity`, `LigandAtomIdentity` | `contracts/types.py` | data/model/inference |
| `EdgeDenominators` | `contracts/types.py` | candidates/model/training/evaluation |
| `CovalentGenerationResult` | `contracts/types.py` | model/inference/evaluation |
| `EvaluationSummary` | `contracts/types.py` | evaluation |
| `ModelBatch`, `BatchRecordHeader`, `BatchTensors` | `contracts/types.py` | model/training |
| `BatchSpec`, `BatchInspectionReport` | `contracts/types.py` | model/training |
| `ModelForwardOutput` | `contracts/types.py` | model/training |
| `StepwiseCandidate`, `StepwiseCandidateSet` | `contracts/types.py` | model/training |
| `MaskAudit`, `DenominatorsStratum`, `LossReport` | `contracts/types.py` | training |
| `TrainingDatasetIndex`, `TrainingRecordEntry` | `contracts/types.py` | training |
| `TrainingRunManifest` | `contracts/types.py` | training/evaluation |
| `GenerationRunManifest` | `contracts/types.py` | inference/evaluation |
| `SamplingSystemFailure` | `contracts/types.py` | inference/evaluation |

### 8. Tensor shape conventions

| Data | Shape | Dtype |
|---|---|---|
| Protein coords | `(B, N_prot, 3)` | float32 |
| Ligand coords | `(B, N_lig, 3)` | float32 |
| Protein atom types | `(B, N_prot)` | int64 |
| Ligand atom types | `(B, N_lig)` | int64 |
| Ligand bonds | `(B, N_lig, N_lig)` | int64 |
| Edge logits | `(B, N_candidates)` | float32 |
| Bond type logits | `(B, N_candidates, N_bond_types)` | float32 |
| Family logits | `(B, N_families)` | float32 |
| Positive label mask | `(B, N_candidates)` | bool |

Coordinate frame is `original_pdb` by default (angstroms). `N_prot`, `N_lig`, `N_candidates` are per-batch maxima; shorter entries are padded. `BatchSpec` carries `max_protein_atoms`, `max_ligand_atoms`, `max_candidates`.

### 9. Bond-type vocabulary

Discovered dynamically from all `positive_edge.bond_type` values in the input records, plus a `"no_edge"` class at index 0. Sorted alphabetically. Stored in `BatchSpec.bond_type_vocabulary`. Expected v1 vocabulary: `["no_edge", "carbon-nitrogen", "carbon-oxygen", "carbon-sulfur", "disulfide", "phosphorus-oxygen"]`.

### 10. PMDM adapter output keys

`ModelForwardOutput.pmdm_outputs` must contain these 7 required keys: `ligand_atom_features`, `protein_atom_features`, `ligand_coords_denoised`, `position_loss`, `atom_type_loss`, `timestep`, `num_atom`. Two optional keys: `ligand_pair_features`, `protein_ligand_pair_features`.

### 11. Family auxiliary head

v1 includes the family auxiliary head. `family_logits` (B, N_families) is a required field in `ModelForwardOutput`. `family_aux_loss` is a required component in `LossReport`. Not deferred to v2.

### 12. Training provenance for release-gate artifacts

The Data Release Gate remains governance rather than a runtime precondition inside Task 17. Training manifests and checkpoint manifests still carry audit provenance for that gate: `input_hashes` include `quality_report`, `visual_check_index`, and an optional `release_gate` approval-manifest hash in addition to `records_jsonl`, `split_index`, and `rule_table`. These hashes do not cause training to re-run ETL validation; they bind a training/checkpoint run to the data-release context that approved the records.

### 13. inspect_batch API contract

`inspect_batch(records_path, record_id=None)` returns a deterministic `dict` (not a ``BatchInspectionReport`` dataclass instance). The CLI entry point is ``python -m covalent_design.model.inspect_batch --records <records.jsonl> [--record-id <id>]``.

The returned dict has these top-level keys: ``schema_version``, ``contract_version``, ``batch_spec`` (aggregated dict or null), ``records`` (list of per-record dicts), ``passed`` (bool), ``errors`` (list), ``warnings`` (list).

Each per-record entry contains: ``record_id``, ``line``, ``error`` (null when ok), ``error_code``, ``provenance`` (nested dict with ``record_id``, ``residue_reaction_family``, ``quality_tier``, ``visual_check_status``, ``chemical_state_status``, ``target_atom_identity`` as nested dict, ``target_atom_index``, ``target_atom_artifact_role``, ``artifact_refs``, ``batch_index``), ``tensor_shapes`` (nested dict with all 9 shape fields plus ``dtype``, ``index_dtype``, ``coordinate_frame``), ``denominators_expected`` (nested dict with all 10 denominator fields), ``batch_spec`` (per-record nested dict), and ``warnings``.

Output is deterministic: same ``records_path`` always produces byte-identical JSON.

The ``BatchInspectionReport`` dataclass in ``contracts/types.py`` describes the per-record field schema; ``inspect_batch()`` returns a batch-level aggregation dict rather than a ``BatchInspectionReport`` instance directly.

### 14. make_model_batch return type

`make_model_batch(records_path, batch_spec=None)` returns a ``ContractEnvelope[ModelBatch]``. The ``ModelBatch`` carries ``batch_spec`` (either the caller-supplied ``BatchSpec`` or an auto-discovered one). The function creates no artifacts on disk (no side effects). Output is deterministic across repeated runs with identical inputs.

## Consequences

- Task 17 can be implemented and tested independently of Tasks 14–16.
- Task 18/19 can obtain target atom identity and tensor index from `BatchRecordHeader` without parsing artifact internals for the reactive site.
- Task 18 (stepwise candidate builder) can be implemented with clear static-vs-dynamic naming. Task 17 validates static edge candidate artifacts; Task 18 consumes their per-edge contents.
- Task 19 (PMDM adapter) has explicit output key vocabulary for both real and fake backbones.
- Task 20 (covalent heads) knows the exact output fields including family_logits.
- Task 22 (training dataset) owns record eligibility filtering, not Task 17.
- The 6 MODEL_BATCH error codes provide a complete, testable fail-before-tensor contract.
- Tensor conventions enable parallel implementation of model, training, and inference without shape/dtype negotiations.
- `inspect_batch` provides deterministic per-record audit output for debugging and CI verification.
