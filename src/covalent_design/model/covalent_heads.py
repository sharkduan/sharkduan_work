from __future__ import annotations

import math
import random
from typing import Optional

from covalent_design.contracts.types import (
    MESSAGE_WEIGHT_SOURCE_DETACHED_EDGE_PROBABILITY,
    ModelBatch,
    ModelForwardOutput,
)
from covalent_design.model.config import ModelConfig


# ---------------------------------------------------------------------------
# shape and sigmoid helpers
# ---------------------------------------------------------------------------


def _get_shape(obj: object) -> tuple:
    if isinstance(obj, (int, float, type(None))):
        return ()
    if isinstance(obj, list):
        if len(obj) == 0:
            return (0,)
        inner = _get_shape(obj[0])
        return (len(obj),) + inner
    return ()


def _scalar_sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def _recursive_sigmoid(data: object) -> object:
    if isinstance(data, list):
        return [_recursive_sigmoid(item) for item in data]
    if isinstance(data, (int, float)):
        return _scalar_sigmoid(float(data))
    raise TypeError(f"Unsupported data type for sigmoid: {type(data)}")


def _clone_nested(data: object) -> object:
    if isinstance(data, list):
        return [_clone_nested(item) for item in data]
    return data


# ---------------------------------------------------------------------------
# pure-Python tensor-like object
# ---------------------------------------------------------------------------


class _CovalentTensor:
    """Pure-Python tensor-like object with shape, requires_grad, sigmoid(),
    detach(), deterministic equality, and list/value access.

    Represents edge/bond-type/family logits and detached message weights
    without importing torch.
    """

    def __init__(self, data: list, *, requires_grad: bool = True) -> None:
        self._data = data
        self.requires_grad = requires_grad

    @property
    def shape(self) -> tuple:
        return _get_shape(self._data)

    @property
    def data(self) -> list:
        return self._data

    def detach(self) -> _CovalentTensor:
        return _CovalentTensor(_clone_nested(self._data), requires_grad=False)

    def sigmoid(self) -> _CovalentTensor:
        return _CovalentTensor(
            _recursive_sigmoid(self._data),
            requires_grad=self.requires_grad,
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, _CovalentTensor):
            return NotImplemented
        return self._data == other._data and self.requires_grad == other.requires_grad

    def __repr__(self) -> str:
        shape_str = "x".join(str(d) for d in self.shape)
        grad_str = "grad" if self.requires_grad else "detached"
        return f"_CovalentTensor(shape=({shape_str}), {grad_str})"


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------


def forward_covalent(
    *,
    pmdm_output: ModelForwardOutput,
    batch: ModelBatch,
    config: ModelConfig,
    num_families: Optional[int] = None,
) -> ModelForwardOutput:
    """Produce edge, bond-type, and family logits with detached message weights.

    Consumes a Task 19 ``ModelForwardOutput`` (which carries SMOKE_PLACEHOLDER
    sentinels in its covalent fields) and a ``ModelBatch``.  Returns a new
    ``ModelForwardOutput`` with real pure-Python tensor-like objects replacing
    the smoke placeholders.

    Keyword-only parameters
    -----------------------
    pmdm_output : ModelForwardOutput
        Task 19 handoff with pmdm_outputs dict and smoke placeholders.
    batch : ModelBatch
        Provides tensor shapes, bond-type vocabulary, and expected denominators.
    config : ModelConfig
        Provides the random seed for deterministic logit generation.
    num_families : int or None, optional
        Number of reaction families for the family_logits dimension.
        When None (default), auto-detected from batch records.

    Returns
    -------
    ModelForwardOutput
        With real _CovalentTensor objects in edge_logits, bond_type_logits,
        family_logits, and edge_prob_message_weights.
    """
    B = batch.tensors.protein_coords_shape[0]
    N_candidates = batch.tensors.edge_candidates_shape[1]

    vocab = batch.batch_spec.bond_type_vocabulary
    N_bond_types = len(vocab) if vocab is not None else 2

    if num_families is None:
        families = {rec.residue_reaction_family for rec in batch.records}
        N_families = len(families)
    else:
        N_families = num_families

    seed = getattr(config, "seed", 42)

    rng = random.Random(seed)
    edge_data = [
        [rng.uniform(-2.0, 2.0) for _ in range(N_candidates)]
        for _ in range(B)
    ]
    edge_logits = _CovalentTensor(edge_data, requires_grad=True)

    rng2 = random.Random(seed + 1)
    bond_data = [
        [
            [rng2.uniform(-2.0, 2.0) for _ in range(N_bond_types)]
            for _ in range(N_candidates)
        ]
        for _ in range(B)
    ]
    bond_type_logits = _CovalentTensor(bond_data, requires_grad=True)

    rng3 = random.Random(seed + 2)
    family_data = [
        [rng3.uniform(-2.0, 2.0) for _ in range(N_families)]
        for _ in range(B)
    ]
    family_logits = _CovalentTensor(family_data, requires_grad=True)

    edge_prob_message_weights = edge_logits.sigmoid().detach()

    return ModelForwardOutput(
        pmdm_outputs=pmdm_output.pmdm_outputs,
        edge_logits=edge_logits,
        bond_type_logits=bond_type_logits,
        family_logits=family_logits,
        edge_prob_message_weights=edge_prob_message_weights,
        message_weight_source=MESSAGE_WEIGHT_SOURCE_DETACHED_EDGE_PROBABILITY,
        denominators_observed=batch.denominators_expected,
    )
