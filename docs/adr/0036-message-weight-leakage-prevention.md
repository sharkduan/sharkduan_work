# Message-Weight Leakage-Prevention Design

## Status

Accepted

## Date

2026-05-26

## Context

The covalent model uses soft stepwise cross-edge message passing (ADR 0003, ADR 0031)
in which covalent cross-edge probabilities serve as soft weights during protein-ligand
message passing. If ground-truth edge labels leak into these message weights, the model
can learn to copy labels rather than predict edges from structure, producing a model
that appears performant during training but fails at inference when labels are absent.

The review identified a risk: tests could verify one happy-path output is detached
while public APIs still allow label leakage in another call path. A concrete API guard
and a provenance test are required.

## Decision

### Two-layer defense: runtime assertion plus provenance tests

**Layer 1 - field convention**

`ModelForwardOutput` carries segregated fields:

```python
@dataclass(frozen=True)
class ModelForwardOutput:
    edge_logits: object
    bond_type_logits: object
    family_logits: object
    edge_prob_message_weights: object  # sigmoid(logits).detach()
    message_weight_source: str          # "detached_edge_probability"
    ...
```

The field name `edge_prob_message_weights` is self-documenting: "prob" means sigmoid
output, and "message_weights" means these are used as soft weights. The
`message_weight_source` field is the explicit provenance marker for the public
contract. The only v1 accepted value is `"detached_edge_probability"`.

**Layer 2 - runtime assertion**

`ModelForwardOutput.__post_init__` validates:

```python
def __post_init__(self):
    if getattr(self.edge_prob_message_weights, "requires_grad", False):
        raise ValueError(
            "edge_prob_message_weights must be detached predicted probabilities; "
            "provenance tests must also verify that this tensor comes from the "
            "model prediction path, not labels or ground truth."
        )
    if self.message_weight_source != "detached_edge_probability":
        raise ValueError(
            "message_weight_source must prove the detached prediction path"
        )
```

This catches:

- Accidentally passing `edge_logits` or another trainable tensor as message weights.
- Any future code path that constructs `ModelForwardOutput` with trainable message weights.
- Any path that explicitly marks message weights as `label`, `ground_truth`, `target_edge`,
  empty, or unknown provenance.

This does not prove by itself that the value did not originate from labels, because
label tensors commonly have `requires_grad=False`. The source marker makes that
case invalid at the contract boundary; Task 20 still needs a provenance test for the
full forward path, because the field value must be produced by code rather than
hand-written incorrectly.

**Layer 3 - provenance/test guard**

Task 20 tests must prove that `edge_prob_message_weights` is computed from the
detached model prediction path (`edge_logits.sigmoid().detach()` or equivalent), not
from label or ground-truth tensors. This is a provenance requirement on the
covalent-head forward path, separate from the dataclass construction-time check.
The contract-level proof is executable today: detached prediction source is accepted,
`requires_grad=True` is rejected, and label/ground-truth source is rejected even when
`requires_grad=False`.

**What we do NOT do**

- We do not introduce a separate `MessageWeightTensor` wrapper type. PyTorch
  ecosystems use `torch.Tensor` universally; a wrapper would require unwrapping at
  every call site with little additional safety.
- We do not add a compile-time static check. The project has no mypy strict-mode
  commitment.

### Test coverage

Required tests in `tests/model/test_covalent_heads.py`:

1. `test_message_weights_are_detached`: construct `ModelForwardOutput` with a
   detached tensor and `message_weight_source="detached_edge_probability"`; no error,
   `requires_grad == False`.
2. `test_message_weights_with_grad_raises`: construct with `requires_grad=True`;
   raises `ValueError`.
3. `test_label_source_raises`: construct with `message_weight_source` equal to
   `label`, `ground_truth`, or `target_edge`; raises `ValueError` even when detached.
4. `test_forward_output_message_weights_detached`: run the full `forward_covalent()`
   path and verify the returned `edge_prob_message_weights` is detached.
5. Label provenance test: verify the full `forward_covalent()` path sources
   `edge_prob_message_weights` from detached predictions, not from labels or ground
   truth.

## Consequences

- Every construction of `ModelForwardOutput` incurs one `requires_grad` check.
- If a future code path constructs `ModelForwardOutput` without going through
  `forward_covalent()`, the guard still catches trainable message weights.
- Tests prove both layers: the public API rejects trainable message weights and
  explicit label/ground-truth sources, and the model forward path sources message
  weights from detached predictions rather than labels.
- ADR 0031 and ADR 0033 remain the governing authorities for stepwise edge
  supervision and mask/gate boundaries.
