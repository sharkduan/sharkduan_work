from __future__ import annotations

from covalent_design.contracts.types import (
    MESSAGE_WEIGHT_SOURCE_DETACHED_EDGE_PROBABILITY,
)

ALLOWED_SOURCES = (MESSAGE_WEIGHT_SOURCE_DETACHED_EDGE_PROBABILITY,)
FORBIDDEN_SOURCES = ("label", "ground_truth", "target_edge")


def apply_edge_message_weights(
    *,
    message_weights: object,
    source: str,
) -> object:
    """Validate the Task 20 message-weight boundary.

    Task 20 only accepts detached prediction probabilities as message weights.
    It rejects label, ground-truth, target-edge, unknown provenance sources, and
    trainable message weights. This function is a no-op passthrough after
    validation; final decode and loss behavior remain later-task scope.
    """
    if source in FORBIDDEN_SOURCES or source not in ALLOWED_SOURCES:
        raise ValueError(
            "edge_message_passing requires message_weight_source="
            f"{MESSAGE_WEIGHT_SOURCE_DETACHED_EDGE_PROBABILITY!r}, got {source!r}"
        )
    if not hasattr(message_weights, "requires_grad"):
        raise ValueError(
            "edge_message_passing requires tensor-like detached prediction "
            "weights with a requires_grad attribute"
        )
    if getattr(message_weights, "requires_grad", False):
        raise ValueError(
            "edge_message_passing requires detached prediction weights; "
            "message_weights.requires_grad must be False"
        )
    return message_weights
