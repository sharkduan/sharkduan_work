"""Fixtures for covalent heads contract tests (Task 20).

Provides pure-Python tensor-like objects and fixture builders for testing
the ``forward_covalent`` API without torch, PMDM, PocketFlow, or RDKit.

Usage from tests::

    from tests.fixtures.model.covalent_heads._builder import (
        CovalentHeadsFixtureBuilder,
        FakeTensor,
        sigmoid,
    )

    builder = CovalentHeadsFixtureBuilder()
    batch = builder.build_model_batch()
    config = builder.build_config()
    pmdm_output = builder.build_model_forward_output(batch)
"""
from __future__ import annotations

import math
import random
from typing import Any, Optional

from covalent_design.contracts.types import BatchTensors, ModelBatch

from tests.fixtures.model._builder import ModelBatchFixtureBuilder


# ===================================================================
# Pure-Python tensor helpers
# ===================================================================


def _scalar_sigmoid(x: float) -> float:
    """Element-wise sigmoid for a scalar."""
    return 1.0 / (1.0 + math.exp(-x))


def _recursive_sigmoid(data: object) -> object:
    """Recursively apply sigmoid to every leaf in a nested list structure."""
    if isinstance(data, list):
        return [_recursive_sigmoid(item) for item in data]
    if isinstance(data, (int, float)):
        return _scalar_sigmoid(float(data))
    raise TypeError(f"Unsupported data type for sigmoid: {type(data)}")


def _get_shape(obj: object) -> tuple:
    """Return the nested-list shape of *obj*."""
    if isinstance(obj, (int, float, type(None))):
        return ()
    if isinstance(obj, list):
        if len(obj) == 0:
            return (0,)
        inner = _get_shape(obj[0])
        return (len(obj),) + inner
    # Fallback for FakeTensor-like objects
    if hasattr(obj, "shape"):
        return obj.shape
    return ()


def _shapes_equal(a: tuple, b: tuple) -> bool:
    """Compare two shape tuples element-wise."""
    if len(a) != len(b):
        return False
    for x, y in zip(a, b):
        if not isinstance(x, int) or not isinstance(y, int):
            return False
        if x != y:
            return False
    return True


class FakeTensor:
    """Pure-Python tensor-like object for testing without torch.

    Supports ``requires_grad``, ``detach()``, and ``sigmoid()`` with
    nested-list data so tests can verify provenance without torch import.
    """

    def __init__(self, data: list, *, requires_grad: bool = True) -> None:
        self._data = data
        self.requires_grad = requires_grad

    @property
    def shape(self) -> tuple:
        return _get_shape(self._data)

    @property
    def data(self) -> list:
        """Raw nested-list values (read-only accessor)."""
        return self._data

    def detach(self) -> FakeTensor:
        """Return a copy with ``requires_grad=False``, data unchanged."""
        return FakeTensor(self._data, requires_grad=False)

    def sigmoid(self) -> FakeTensor:
        """Element-wise sigmoid, preserving ``requires_grad``."""
        sigmoid_data = _recursive_sigmoid(self._data)
        return FakeTensor(sigmoid_data, requires_grad=self.requires_grad)

    def to_list(self) -> list:
        """Return a deep-copy of the underlying nested list."""
        import copy
        return copy.deepcopy(self._data)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, FakeTensor):
            return NotImplemented
        return self._data == other._data and self.requires_grad == other.requires_grad

    def __repr__(self) -> str:
        shape_str = "x".join(str(d) for d in self.shape)
        grad_str = "grad" if self.requires_grad else "detached"
        return f"FakeTensor(shape=({shape_str}), {grad_str})"


def sigmoid(tensor: object) -> object:
    """Public sigmoid helper -works with FakeTensor or nested lists.

    Returns a FakeTensor when given a FakeTensor; returns nested lists
    when given nested lists.
    """
    if isinstance(tensor, FakeTensor):
        return tensor.sigmoid()
    sigmoid_data = _recursive_sigmoid(tensor)
    return sigmoid_data


# ===================================================================
# Label-source tensor (for anti-leakage tests)
# ===================================================================


class _LabelSourceTensor(FakeTensor):
    """A detached tensor whose values came from labels, not model predictions.

    This simulates a tensor that has ``requires_grad=False`` but whose data
    was sourced from ground-truth edge labels rather than sigmoid(detach(edge_logits)).
    Providers of edge_prob_message_weights must not simply set
    ``requires_grad=False`` on label data -the values must be derivable from
    sigmoid(edge_logits).
    """

    def __init__(self, data: list) -> None:
        super().__init__(data, requires_grad=False)

    @property
    def source(self) -> str:
        return "ground_truth_label"


class _GradFalseButWrongValuesTensor(FakeTensor):
    """A detached tensor with ``requires_grad=False`` but values that do NOT
    equal sigmoid(edge_logits) -e.g. a hand-crafted array of ones or label values.
    """

    def __init__(self, data: list) -> None:
        super().__init__(data, requires_grad=False)


# ===================================================================
# Covalent heads fixture builder
# ===================================================================


DEFAULT_HIDDEN_DIM = 256
DEFAULT_LIGAND_FEATURE_DIM = 128
DEFAULT_PROTEIN_FEATURE_DIM = 128


class CovalentHeadsFixtureBuilder:
    """Builds fixtures for covalent heads contract tests (Task 20).

    All fake outputs are pure-Python nested lists or FakeTensor objects -    no torch, PMDM, PocketFlow, or RDKit required.
    """

    def __init__(self, seed: int = 42) -> None:
        self._seed = seed
        self._batch_builder = ModelBatchFixtureBuilder()

    # -- batch ----------------------------------------------------------

    def build_model_batch(self) -> ModelBatch:
        """Build a ModelBatch from the existing valid Task-17 fixture."""
        from covalent_design.model.batch import make_model_batch

        valid_path = self._batch_builder.write_valid()
        result = make_model_batch(valid_path)
        if hasattr(result, "payload"):
            return result.payload
        return result  # type: ignore[return-value]

    # -- config ---------------------------------------------------------

    def build_config(self) -> object:
        """Build a ModelConfig for covalent heads tests."""
        from covalent_design.model.config import ModelConfig

        return ModelConfig(
            contract_version="1.0.0",
            rule_table_hash=(
                "sha256:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
            ),
            fake_backbone=True,
            hidden_dim=DEFAULT_HIDDEN_DIM,
            ligand_feature_dim=DEFAULT_LIGAND_FEATURE_DIM,
            protein_feature_dim=DEFAULT_PROTEIN_FEATURE_DIM,
            ligand_pair_feature_dim=0,
            protein_ligand_pair_feature_dim=0,
            seed=self._seed,
            candidate_radius_angstrom=4.0,
        )

    def build_config_dict(self) -> dict:
        """Build a config dict for covalent heads tests."""
        return {
            "contract_version": "1.0.0",
            "rule_table_hash": (
                "sha256:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
            ),
            "fake_backbone": True,
            "hidden_dim": DEFAULT_HIDDEN_DIM,
            "ligand_feature_dim": DEFAULT_LIGAND_FEATURE_DIM,
            "protein_feature_dim": DEFAULT_PROTEIN_FEATURE_DIM,
            "pair_feature_dim": 0,
            "cross_feature_dim": 0,
            "enable_optional_pair_features": False,
            "seed": self._seed,
        }

    # -- fake PMDM outputs (Task 19 handoff) ----------------------------

    def build_fake_pmdm_outputs(
        self,
        tensors: BatchTensors,
        *,
        timestep: float = 0.5,
    ) -> dict:
        """Build a fake PMDM outputs dict matching the Task 19 contract."""
        rng = random.Random(self._seed)

        B = tensors.protein_coords_shape[0]
        N_lig = tensors.ligand_coords_shape[1]
        N_prot = tensors.protein_coords_shape[1]

        D_lig = DEFAULT_LIGAND_FEATURE_DIM
        D_prot = DEFAULT_PROTEIN_FEATURE_DIM

        outputs: dict = {}

        outputs["ligand_atom_features"] = [
            [[rng.random() for _ in range(D_lig)] for _ in range(N_lig)]
            for _ in range(B)
        ]

        outputs["protein_atom_features"] = [
            [[rng.random() for _ in range(D_prot)] for _ in range(N_prot)]
            for _ in range(B)
        ]

        outputs["ligand_coords_denoised"] = [
            [[rng.random() for _ in range(3)] for _ in range(N_lig)]
            for _ in range(B)
        ]

        outputs["position_loss"] = rng.random()
        outputs["atom_type_loss"] = rng.random()
        outputs["timestep"] = float(timestep)
        outputs["num_atom"] = [N_lig for _ in range(B)]

        return outputs

    # -- Task 19 handoff: ModelForwardOutput with SMOKE_PLACEHOLDER ------

    def build_task19_handoff(
        self,
        batch: ModelBatch,
        *,
        timestep: float = 0.5,
    ) -> object:
        """Build a Task-19-style ModelForwardOutput with SMOKE_PLACEHOLDER
        sentinels in the covalent-head fields.

        This is the exact shape that Task 19 ``forward_pmdm()`` produces.
        Task 20 ``forward_covalent()`` must replace the smoke placeholders
        with real tensor outputs.
        """
        from covalent_design.model.pmdm_adapter import SMOKE_PLACEHOLDER
        from covalent_design.contracts.types import (
            MESSAGE_WEIGHT_SOURCE_DETACHED_EDGE_PROBABILITY,
            ModelForwardOutput,
        )

        pmdm_outputs = self.build_fake_pmdm_outputs(
            batch.tensors, timestep=timestep
        )

        return ModelForwardOutput(
            pmdm_outputs=pmdm_outputs,
            edge_logits=SMOKE_PLACEHOLDER,
            bond_type_logits=SMOKE_PLACEHOLDER,
            family_logits=SMOKE_PLACEHOLDER,
            edge_prob_message_weights=SMOKE_PLACEHOLDER,
            message_weight_source=MESSAGE_WEIGHT_SOURCE_DETACHED_EDGE_PROBABILITY,
            denominators_observed=batch.denominators_expected,
        )

    # -- Task 20 expected output: ModelForwardOutput with real logits ----

    def build_model_forward_output(
        self,
        batch: ModelBatch,
        *,
        timestep: float = 0.5,
    ) -> object:
        """Build a Task-20-style ModelForwardOutput with real FakeTensor
        edge_logits, bond_type_logits, and family_logits.

        The edge_prob_message_weights equal sigmoid(edge_logits).detach().
        Used as a reference for verifying forward_covalent output.
        """
        from covalent_design.contracts.types import (
            MESSAGE_WEIGHT_SOURCE_DETACHED_EDGE_PROBABILITY,
            ModelForwardOutput,
        )

        pmdm_outputs = self.build_fake_pmdm_outputs(
            batch.tensors, timestep=timestep
        )

        edge_logits = self.build_edge_logits(batch, requires_grad=True)
        bond_type_logits = self.build_bond_type_logits(batch)
        family_logits = self.build_family_logits(batch)
        edge_prob_message_weights = edge_logits.sigmoid().detach()

        return ModelForwardOutput(
            pmdm_outputs=pmdm_outputs,
            edge_logits=edge_logits,
            bond_type_logits=bond_type_logits,
            family_logits=family_logits,
            edge_prob_message_weights=edge_prob_message_weights,
            message_weight_source=MESSAGE_WEIGHT_SOURCE_DETACHED_EDGE_PROBABILITY,
            denominators_observed=batch.denominators_expected,
        )

    # -- individual logit tensor builders --------------------------------

    def build_edge_logits(
        self,
        batch: ModelBatch,
        *,
        requires_grad: bool = True,
    ) -> FakeTensor:
        """Build edge_logits FakeTensor with known values.

        Shape: (B, N_candidates).
        Uses deterministic values so sigmoid comparisons are exact.
        """
        B = batch.tensors.protein_coords_shape[0]
        N_candidates = batch.tensors.edge_candidates_shape[1]
        rng = random.Random(self._seed)
        data = [
            [rng.uniform(-2.0, 2.0) for _ in range(N_candidates)]
            for _ in range(B)
        ]
        return FakeTensor(data, requires_grad=requires_grad)

    def build_bond_type_logits(
        self,
        batch: ModelBatch,
    ) -> FakeTensor:
        """Build bond_type_logits FakeTensor.

        Shape: (B, N_candidates, N_bond_types).
        """
        B = batch.tensors.protein_coords_shape[0]
        N_candidates = batch.tensors.edge_candidates_shape[1]
        vocab = (
            batch.batch_spec.bond_type_vocabulary
            if batch.batch_spec is not None
            else ("no_edge", "carbon-sulfur")
        )
        N_bond_types = len(vocab)
        rng = random.Random(self._seed + 1)
        data = [
            [
                [rng.uniform(-2.0, 2.0) for _ in range(N_bond_types)]
                for _ in range(N_candidates)
            ]
            for _ in range(B)
        ]
        return FakeTensor(data, requires_grad=True)

    def build_family_logits(
        self,
        batch: ModelBatch,
        *,
        num_families: Optional[int] = None,
    ) -> FakeTensor:
        """Build family_logits FakeTensor.

        Shape: (B, N_families).
        """
        B = batch.tensors.protein_coords_shape[0]
        if num_families is None:
            families = set()
            for rec in batch.records:
                families.add(rec.residue_reaction_family)
            num_families = len(families)
        N_families = num_families
        rng = random.Random(self._seed + 2)
        data = [
            [rng.uniform(-2.0, 2.0) for _ in range(N_families)]
            for _ in range(B)
        ]
        return FakeTensor(data, requires_grad=True)

    # -- anti-leakage: edge_prob_message_weights from labels ------------

    @staticmethod
    def build_label_sourced_message_weights(
        batch: ModelBatch,
    ) -> _LabelSourceTensor:
        """Build a detached tensor whose values come from label data.

        The tensor has ``requires_grad=False`` but the values are not
        derivable from sigmoid(edge_logits) -they are label values.
        """
        B = batch.tensors.protein_coords_shape[0]
        N_candidates = batch.tensors.edge_candidates_shape[1]
        # Simulate one-hot label data (first candidate is positive)
        data = [
            [float(i == 0) for i in range(N_candidates)]
            for _ in range(B)
        ]
        return _LabelSourceTensor(data)

    @staticmethod
    def build_wrong_value_message_weights(
        batch: ModelBatch,
    ) -> _GradFalseButWrongValuesTensor:
        """Build a detached tensor whose values do not match sigmoid(edge_logits)."""
        B = batch.tensors.protein_coords_shape[0]
        N_candidates = batch.tensors.edge_candidates_shape[1]
        # All ones -does not match any sigmoid output
        data = [
            [1.0 for _ in range(N_candidates)]
            for _ in range(B)
        ]
        return _GradFalseButWrongValuesTensor(data)

    # -- shape helpers --------------------------------------------------

    @staticmethod
    def get_shape(obj: object) -> tuple:
        """Return the nested-list shape of *obj*."""
        return _get_shape(obj)

    @staticmethod
    def shapes_equal(a: tuple, b: tuple) -> bool:
        """Compare two shape tuples element-wise."""
        return _shapes_equal(a, b)
