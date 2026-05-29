# Spec: Model

## Objective

Build a PMDM-compatible fixed-protein ligand diffusion extension for de novo covalent inhibitor generation. The model keeps PMDM's pocket-conditioned ligand diffusion backbone and adds explicit reactive-site conditioning, residue-reaction-family conditioning, stepwise soft covalent cross-edge scoring, bond-type scoring, optional family auxiliary diagnostics, and a final hard covalent edge decode interface.

The model must support a single covalent attachment event and must not rewrite the project as a PocketFlow backbone.

## Tech Stack

- Python 3.9-compatible project-owned wrappers and adapters.
- PyTorch model components.
- PMDM as the baseline diffusion backbone.
- PocketFlow only as design inspiration for candidate-edge and local context supervision.

## Commands

```bash
python -m covalent_design.model.inspect_batch --records data/processed/covalent_complex_records/records.jsonl --record-id <record_id>
pytest tests/model/test_pmdm_adapter.py -q
pytest tests/model/test_stepwise_candidates.py -q
pytest tests/model/test_batch.py -q
python -m compileall -q scripts src
```

`forward_smoke` and `export_arch_summary` CLIs are deferred to Task 24; Task 19 `forward_pmdm` has no standalone CLI — it is called from tests.

## Project Structure

```text
src/covalent_design/model/
  pmdm_adapter.py
  batch.py
  conditioning.py
  reactive_site_features.py
  family_conditioning.py
  candidate_builder.py
  covalent_heads.py
  edge_message_passing.py
  geometry_features.py
  final_decode.py
  validity_gate.py
  size_prior.py

configs/
  covalent_model_smoke.yml
  covalent_model_v1.yml
```

## Code Style

Separate learnable behavior from non-learnable constraints. Model code may expose rule masks and gate features, but it must not describe masked feasibility as learned chemistry.

```python
edge_logits = edge_head(candidate_features)
edge_prob = edge_logits.sigmoid()
message_weight = edge_prob.detach()
message_weight_source = "detached_edge_probability"
context = apply_soft_cross_edge_messages(context, candidates, message_weight)
```

Rules:

- Stepwise candidates are rebuilt from fixed protein coordinates and current noisy or generated ligand coordinates.
- The positive training edge is force-included when diffusion noise moves it outside the candidate radius.
- Force-included positives are counted separately and excluded from v1 soft edge message passing and geometry regression.
- Ground-truth edge labels are not used as training-time message weights, and any `ModelForwardOutput` using label/ground_truth/target_edge as `message_weight_source` is invalid.
- Final hard decoding can reject all candidates and return an invalid sample path.

### PMDM Adapter (Task 19)

```python
def forward_pmdm(
    *,
    batch: ModelBatch,
    config: ModelConfig,
    timestep: float = 0.5,
) -> ModelForwardOutput:
```

Task 19 fake backbone is pure Python deterministic smoke — no real PMDM, PocketFlow, torch, or RDKit import. `ModelForwardOutput.edge_logits`, `.bond_type_logits`, `.family_logits`, and `.edge_prob_message_weights` are explicit `SMOKE_PLACEHOLDER` sentinels. Task 19 does **not** implement covalent heads, message passing, real logits, or detached sigmoid message weights.

`message_weight_source` is `"detached_edge_probability"` to satisfy the public anti-leakage guard. Task 19 does NOT prove Task 20 message-weight provenance.

### ModelConfig

```python
@dataclass(frozen=True)
class ModelConfig:
    contract_version: str = "1.0.0"
    rule_table_hash: str = ""
    fake_backbone: bool = True
    hidden_dim: int = 256
    ligand_feature_dim: int = 128
    protein_feature_dim: int = 128
    ligand_pair_feature_dim: int = 0       # 0 → optional pair key absent
    protein_ligand_pair_feature_dim: int = 0  # 0 → optional cross key absent
    seed: int = 42
    candidate_radius_angstrom: float = 4.0
```

Frozen dataclass; `to_dict()` is deterministic across repeated calls. `contract_version` and `rule_table_hash` are required for checkpoint provenance.

### PMDM Output Key Vocabulary

9 keys: 7 required, 2 optional. Optional pair keys (`ligand_pair_features`, `protein_ligand_pair_features`) are present only when the corresponding config dimension is positive. When dimensions are zero, optional keys must be absent — not present as empty arrays.

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

Shape validation raises `ContractError` with owner `"model"` on missing required key, unknown key, wrong shape, missing optional when enabled, and unexpected optional when disabled.

### Covalent Heads (Task 20)

```python
def forward_covalent(
    *,
    pmdm_output: ModelForwardOutput,
    batch: ModelBatch,
    config: ModelConfig,
    num_families: Optional[int] = None,
) -> ModelForwardOutput:
```

Consumes a Task 19 `ModelForwardOutput` (which carries `SMOKE_PLACEHOLDER` sentinels in its covalent fields) and a `ModelBatch`. Returns a new `ModelForwardOutput` with real pure-Python tensor-like objects replacing the smoke placeholders.

Task 20 does **not** wrap or reimplement `forward_pmdm()`. It is a separate step: `forward_pmdm()` produces the PMDM backbone output with smoke placeholders; `forward_covalent()` consumes that output and fills in the covalent head logits and detached message weights.

**Output tensor shapes:**

| Field | Shape |
| --- | --- |
| `edge_logits` | `(B, N_candidates)` |
| `bond_type_logits` | `(B, N_candidates, N_bond_types)` |
| `family_logits` | `(B, N_families)` |
| `edge_prob_message_weights` | `(B, N_candidates)` |

`N_bond_types` is read from `BatchSpec.bond_type_vocabulary`; `N_families` is auto-detected from `batch.records` `residue_reaction_family` values when `num_families=None`.

**v1 family auxiliary head:** `family_logits` is always populated (not optional). `family_aux_loss` is a required `LossReport` component.

**Detached message-weight rule:** `edge_prob_message_weights = edge_logits.sigmoid().detach()` — predicted probabilities detached from the computation graph. `message_weight_source` is `"detached_edge_probability"`. `ModelForwardOutput.__post_init__` validates:
- `edge_prob_message_weights.requires_grad == False` (rejects trainable weights)
- `message_weight_source == "detached_edge_probability"` (rejects `"label"`, `"ground_truth"`, `"target_edge"`, empty, and unknown sources, even when `requires_grad == False`)

### Edge Message Passing Boundary (Task 20)

```python
def apply_edge_message_weights(
    *,
    message_weights: object,
    source: str,
) -> object:
```

Validates the Task 20 message-weight boundary. Accepts only `message_weight_source = "detached_edge_probability"` with detached prediction weights. Rejects label, ground-truth, target-edge, unknown provenance sources, and trainable message weights. This function is a no-op passthrough after validation.

`apply_edge_message_weights` is a Task 20 guard, not Task 21 final decode or Task 24 loss. Final decode and loss behavior remain later-task scope.

**Allowed sources:** only `"detached_edge_probability"`.

**Forbidden sources:** `"label"`, `"ground_truth"`, `"target_edge"` — rejected with `ValueError` even when `message_weights.requires_grad == False`. Unknown sources are also rejected.

### Final Decode And Validity Gate (Task 21)

```python
class ValidityGate(abc.ABC):
    @abc.abstractmethod
    def evaluate(
        self,
        candidate_index: int,
        candidate: dict,
        state: Any,
    ) -> tuple[EdgeValidityCheck, ...]: ...

FinalLigandState = Dict[str, Any]  # dict with key "candidates"

def decode_final_edge(
    final_state: FinalLigandState,
    gate: Any,  # ValidityGate protocol
) -> FinalDecodeResult:
```

Selects the highest-scoring candidate that passes all 9 validity gate checks. Candidates are sorted by score descending with deterministic tie-breaking (original list index). `decode_final_edge` calls `gate.evaluate()` for each candidate in rank order.

**Gate evaluation order** (`_SPEC_GATE_ORDER` constant):

```
1. target_atom → 2. ligand_atom_class → 3. bond_type →
4. single_edge_representability → 5. warhead_smarts → 6. forbidden_smarts →
7. valence → 8. protonation → 9. geometry
```

**`FinalDecodeResult` fields:**

| Field | Type | Description |
| --- | --- | --- |
| `generation_validity_status` | `str` | `"valid"` \| `"invalid"` |
| `selected_edge` | `CovalentEdge \| None` | The selected candidate edge, or `None` |
| `primary_failure_reason` | `str \| None` | `None` for valid; failure code for invalid |
| `secondary_failure_reasons` | `tuple[str, ...]` | Deduplicated first-failure codes from skipped higher-scoring candidates |
| `edge_validity_checks` | `tuple[EdgeValidityCheck, ...]` | One entry per check per evaluated candidate |
| `selected_score` | `float \| None` | Score of the selected candidate, or `None` |

**`REQUIRED_GATE_STATE_UNAVAILABLE` is a global blocking condition.** The constant `_REQUIRED_GATE_STATE_UNAVAILABLE = "REQUIRED_GATE_STATE_UNAVAILABLE"` identifies checks where required gate state is absent (`not_evaluable` or `failure_code == "REQUIRED_GATE_STATE_UNAVAILABLE"`). If any evaluated candidate has such a check, no candidate can be selected — the entire generation is invalid. The blocking code format is `"REQUIRED_GATE_STATE_UNAVAILABLE:{check_name}"`.

**`primary_failure_reason` priority chain** when all candidates fail:
1. A blocking required-state failure (if any candidate was not-evaluable)
2. The first failure of the highest-scoring candidate
3. `"NO_COVALENT_EDGE_PREDICTED"` (sentinel for zero candidates)

**Valid:** a candidate passes every applicable gate check (`pass` and `not_applicable` are non-blocking) and no blocking required-state failure exists. `primary_failure_reason` is `None`. `secondary_failure_reasons` records deduplicated first-failure codes from skipped higher-scoring candidates.

**Invalid:** all candidates fail or zero candidates exist. `selected_edge` is `None`. `primary_failure_reason` is non-`None`.

`_failure_reason(check)` constructs the failure code string: for `not_evaluable` / `REQUIRED_GATE_STATE_UNAVAILABLE` checks, the format is `"REQUIRED_GATE_STATE_UNAVAILABLE:{check_name}"`; otherwise the check's `failure_code` is used, falling back to `"GATE_{CHECK_NAME}_FAIL"`.

### Stepwise Candidate Builder API

```python
def build_stepwise_candidates(
    *,
    protein_atoms: list[dict],
    ligand_atoms: list[dict],
    edge_candidates_artifact: dict,
    timestep_index: int,
    timestep_value: float,
    candidate_radius_angstrom: float = 4.0,
) -> StepwiseCandidateSet:
```

Rebuilds covalent edge candidates at a single denoising timestep. The function is a pure in-memory computation that creates no disk artifacts.

**Input sources and their roles:**

| Input | Role | Constraint |
| --- | --- | --- |
| `protein_atoms` | Fixed protein structure | Dicts with `"name"`, `"x"`, `"y"`, `"z"`; target atom coords resolved by matching `"name"` to artifact |
| `ligand_atoms` | Current-timestep noisy/generated ligand coords | Dicts with `"x"`, `"y"`, `"z"`; `"index"` key used when present |
| `edge_candidates_artifact` | Task 12 static artifact | `positive_edge` → `ligand_atom_index`, `target_atom`, `bond_type` |
| `timestep_index` | Metadata passthrough | Stored in `StepwiseCandidateSet.timestep_index` |
| `timestep_value` | Metadata passthrough | Stored in `StepwiseCandidateSet.timestep_value` |
| `candidate_radius_angstrom` | Natural-candidate cutoff | Default 4.0 A; strict `<` (not `<=`) |

**Candidate sorting and indexing:**

- Positive candidate always appears first in the output tuple.
- Negative candidates follow, sorted by distance ascending then by `ligand_atom_index`.
- `local_index` is a contiguous per-call index (0, 1, 2, ...) assigned in sort order. It restarts at 0 on every call and has no cross-timestep meaning.
- `ligand_atom_index` is the stable identity carried across timesteps for force-inclusion checks and loss alignment.

**Forced-positive semantics:**

A positive is *natural* when `distance < candidate_radius_angstrom` (`is_forced_positive=False`). It is *force-included* when outside the radius (`is_forced_positive=True`). Forced positives:

- Increment `EdgeDenominators.forced_positive_count`.
- Are excluded from `bond_type_loss_denominator`, `geometry_loss_denominator`, and `message_passing_candidate_count` (v1).
- Participate in edge-existence loss and gate evaluation but not bond-type loss, geometry loss, or message passing.

**Denominator equations for the per-timestep set:**

```text
candidate_count = natural_candidate_count + forced_positive_count
natural_candidate_count = count of candidates with within_radius=True
forced_positive_count = count of candidates with is_forced_positive=True
empty_radius_window = (natural_negative_count == 0)
bond_type_loss_denominator = natural_candidate_count       # forced positives excluded
geometry_loss_denominator = natural_candidate_count        # forced positives excluded
message_passing_candidate_count = natural_candidate_count  # forced positives excluded
```

**Boundary:** Task 18 does NOT implement PMDM adapter, covalent heads, message passing, loss masks, final decode, training, inference, or evaluation. Those are Task 19–33 scope.

## Testing Strategy

Unit tests should cover:

- Candidate construction at noisy timestep `t`.
- Forced-positive inclusion and denominator counts.
- No-edge negative labels and loss eligibility.
- Detached predicted probabilities for message passing.
- Covalent head tensor shapes for edge existence and bond type.
- Family conditioning uses `residue_reaction_family`.
- Ligand heavy-atom controls map to PMDM-style `num_atom`.
- Final validity gate can reject every candidate.
- Task 19 fake backbone: all 7 required pmdm_outputs keys with correct shapes; optional keys present/absent per config dims; shape validation (missing required, unknown, wrong shape); determinism (same seed = identical, different seed = different); import isolation (no PMDM/PocketFlow/torch/RDKit, no Task 20 modules); no artifacts generated.
- Task 19 Task-20 fields are explicit smoke placeholders; `message_weight_source = "detached_edge_probability"` satisfies anti-leakage guard.
- Task 20 `forward_covalent`: consumes Task 19 `ModelForwardOutput` (with smoke placeholders) + `ModelBatch` + `ModelConfig`; returns `ModelForwardOutput` with real `_CovalentTensor` objects; does NOT wrap/reimplement `forward_pmdm()`; output shapes `edge_logits (B,N_candidates)`, `bond_type_logits (B,N_candidates,N_bond_types)`, `family_logits (B,N_families)`, `edge_prob_message_weights (B,N_candidates)`; v1 family auxiliary head always present; detached message-weight rule (`sigmoid().detach()`); `message_weight_source = "detached_edge_probability"`; `__post_init__` rejects trainable weights and label/ground_truth/target_edge/empty/unknown sources even when `requires_grad == False`.
- Task 20 `apply_edge_message_weights`: Task 20 boundary guard (not Task 21/24); validates source + requires_grad; no-op passthrough; rejects `"label"`, `"ground_truth"`, `"target_edge"`, unknown sources; rejects trainable weights.
- Task 21 gate order contract: `_SPEC_GATE_ORDER` has exactly 9 checks in the correct sequence, matching `EdgeValidityCheckName` values, no duplicates, `single_edge_representability` at index 3.
- Task 21 `InjectableGate` and `OrderRecordingGate` test doubles: evaluate checks in spec order, per-candidate status independence, not_evaluable produces REQUIRED_GATE_STATE_UNAVAILABLE failure code.
- Task 21 `decode_final_edge`: deterministic score sorting (descending + tie-breaking by list index), all-pass returns valid with selected_edge, top-fail+second-pass returns valid with secondary_failure_reasons, all-fail returns invalid with primary_failure_reason from best candidate first failure, single-candidate-fail returns invalid, REQUIRED_GATE_STATE_UNAVAILABLE blocks all candidates globally, zero candidates returns invalid with NO_COVALENT_EDGE_PREDICTED, primary_failure_reason None for valid / non-None for invalid, edge_validity_checks covers all evaluated candidates, selected_edge None for invalid / non-None for valid, non-mutation of input state, same-input determinism.

Tests should use tiny fixture records, not full raw corpora.

## Boundaries

Always:

- Keep protein coordinates fixed.
- Use `residue_reaction_family` as the primary condition.
- Emit at most one final covalent cross edge.
- Preserve distinction between matched warhead evidence and predicted warhead diagnostics.

Ask first:

- Editing upstream PMDM files directly.
- Adding scheduled sampling, non-detached edge-message gradients, or a new backbone.
- Enabling chemistry families outside the first-pass vocabulary.

Never:

- Predict the reactive residue as a model target in v1.
- Use a fixed ligand attachment slot.
- Do full complex diffusion.
- Repair an invalid generated ligand by post-hoc adding, deleting, or switching the covalent edge.
- Treat PocketFlow flow likelihood as part of the v1 model objective.

## Success Criteria

- A model smoke forward pass consumes a batch derived from accepted `CovalentComplexRecord` artifacts.
- Forward outputs include PMDM-compatible predictions plus covalent edge logits, bond-type logits, and denominator metadata.
- Stepwise candidates use current coordinate state and the 4.0 Angstrom candidate radius.
- Forced positives, natural candidates, message-passing candidates, and gate-evaluated candidates are counted separately.
- Final decode selects the highest-scoring candidate that passes the rule gate or records a valid invalid-sample failure path.

## Open Questions

Resolved (2026-05-26 contract freeze, see ADR 0035):

- **Bond-type vocabulary:** Dynamically discovered from `core_labels.bond_type` across records + `"no_edge"` at index 0. Stored in `BatchSpec.bond_type_vocabulary`. ~6 positive classes + no_edge for v1.
- **Family auxiliary head:** Included in v1. `family_logits` is a required `ModelForwardOutput` field; `family_aux_loss` is a required `LossReport` component.
- **PMDM integration:** Adapter pattern with explicit output key vocabulary (9 keys: 7 required + 2 optional). Fake backbone for smoke tests. Task 19 ``forward_pmdm(*, batch, config, timestep=0.5) -> ModelForwardOutput`` uses pure Python nested lists with deterministic ``random.Random(seed)`` — no real PMDM, PocketFlow, torch, or RDKit import. Optional pair keys present only when config dimensions > 0. Task 20 fields (``edge_logits``, ``bond_type_logits``, ``family_logits``, ``edge_prob_message_weights``) are explicit ``SMOKE_PLACEHOLDER`` sentinels. Shape validation covers missing required key, unknown key, and wrong shape. See `interface-design.md` ModelConfig and PMDM Adapter Output Keys.
- **Task 17 input bundle:** Consumes a single finalized Task 13 `records.jsonl` (five artifact roles per record). Task 17 does NOT check Data Release Gate, split assignment, quality-tier eligibility, or visual check status. ``make_model_batch()`` creates no artifacts on disk (no side effects).
- **Target atom sourcing:** ``BatchRecordHeader.target_atom_identity`` is resolved from ``protein_atom_table`` artifact (chain_id, residue_number, residue_name); ``target_atom_index`` comes from ``core_labels.target_atom_index``; ``target_atom_artifact_role`` is constant ``"protein_atom_table"``.
- **Static edge candidates:** Task 17 validates existence and checksum and records them in ``static_edge_candidates_refs`` (``record_id → ArtifactRef`` mapping). Per-edge contents (positive label identity, bond type) are consumed later by Task 18, not by ``make_model_batch()`` itself.

Still open for v1:

- How should final edge-score thresholds be calibrated?
- Does size prior remain PMDM-style, or become family-conditioned in v1?
