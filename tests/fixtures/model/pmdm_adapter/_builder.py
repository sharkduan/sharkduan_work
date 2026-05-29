"""Build fixtures for PMDM adapter contract tests (Task 19).

Provides deterministic fake PMDM output generation and ModelConfig-like
dict construction without requiring PMDM, PocketFlow, torch, or RDKit.

Usage from tests::

    from tests.fixtures.model.pmdm_adapter._builder import (
        PMDMAdapterFixtureBuilder,
    )

    builder = PMDMAdapterFixtureBuilder(seed=42)
    batch = builder.build_model_batch()
    config = builder.build_config()
    pmdm_outputs = builder.build_fake_pmdm_outputs(batch.tensors)
"""

from __future__ import annotations

import random
from typing import Optional

from covalent_design.contracts.types import BatchTensors, ModelBatch

from tests.fixtures.model._builder import ModelBatchFixtureBuilder

# ---------------------------------------------------------------------------
# PMDM output key vocabulary (from interface-design.md)
# ---------------------------------------------------------------------------

REQUIRED_PMDM_KEYS = (
    "ligand_atom_features",
    "protein_atom_features",
    "ligand_coords_denoised",
    "position_loss",
    "atom_type_loss",
    "timestep",
    "num_atom",
)

OPTIONAL_PMDM_KEYS = (
    "ligand_pair_features",
    "protein_ligand_pair_features",
)

ALL_PMDM_KEYS = REQUIRED_PMDM_KEYS + OPTIONAL_PMDM_KEYS

# ---------------------------------------------------------------------------
# Default feature dimensions (PMDM-compatible)
# ---------------------------------------------------------------------------

DEFAULT_LIGAND_FEATURE_DIM = 128
DEFAULT_PROTEIN_FEATURE_DIM = 128
DEFAULT_PAIR_FEATURE_DIM = 64
DEFAULT_CROSS_FEATURE_DIM = 64


# ===================================================================
# fixture builder
# ===================================================================


class PMDMAdapterFixtureBuilder:
    """Builds fixtures for PMDM adapter contract tests.

    All fake outputs are pure-Python nested lists or scalars - no
    torch, PMDM, PocketFlow, or RDKit required.
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

    def build_config_dict(
        self,
        *,
        contract_version: str = "1.0.0",
        rule_table_hash: str = "sha256:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
        ligand_feature_dim: int = DEFAULT_LIGAND_FEATURE_DIM,
        protein_feature_dim: int = DEFAULT_PROTEIN_FEATURE_DIM,
        pair_feature_dim: int = DEFAULT_PAIR_FEATURE_DIM,
        cross_feature_dim: int = DEFAULT_CROSS_FEATURE_DIM,
        enable_optional_pair_features: bool = False,
        seed: Optional[int] = None,
    ) -> dict:
        """Build a ModelConfig-like dict for contract tests.

        Returns a plain dict so tests can pass it to forward_pmdm
        without requiring the ModelConfig class to be implemented.
        """
        return {
            "contract_version": contract_version,
            "rule_table_hash": rule_table_hash,
            "ligand_feature_dim": ligand_feature_dim,
            "protein_feature_dim": protein_feature_dim,
            "pair_feature_dim": pair_feature_dim,
            "cross_feature_dim": cross_feature_dim,
            "enable_optional_pair_features": enable_optional_pair_features,
            "seed": seed if seed is not None else self._seed,
        }

    # -- fake PMDM outputs ----------------------------------------------

    @staticmethod
    def build_fake_pmdm_outputs(
        tensors: BatchTensors,
        *,
        seed: int = 42,
        timestep: float = 0.5,
        enable_optional: bool = False,
        ligand_feature_dim: int = DEFAULT_LIGAND_FEATURE_DIM,
        protein_feature_dim: int = DEFAULT_PROTEIN_FEATURE_DIM,
        pair_feature_dim: int = DEFAULT_PAIR_FEATURE_DIM,
        cross_feature_dim: int = DEFAULT_CROSS_FEATURE_DIM,
    ) -> dict:
        """Build a deterministic fake PMDM output dict.

        All values are pure-Python nested lists or scalars.  The same
        (tensor shapes, seed) pair always produces byte-identical output.
        """
        rng = random.Random(seed)

        B = tensors.protein_coords_shape[0]
        N_lig = tensors.ligand_coords_shape[1]
        N_prot = tensors.protein_coords_shape[1]

        D_lig = ligand_feature_dim
        D_prot = protein_feature_dim
        D_pair = pair_feature_dim
        D_cross = cross_feature_dim

        outputs: dict = {}

        # ligand_atom_features  (B, N_lig, D_lig)
        outputs["ligand_atom_features"] = [
            [[_scalar(rng) for _ in range(D_lig)] for _ in range(N_lig)]
            for _ in range(B)
        ]

        # protein_atom_features  (B, N_prot, D_prot)
        outputs["protein_atom_features"] = [
            [[_scalar(rng) for _ in range(D_prot)] for _ in range(N_prot)]
            for _ in range(B)
        ]

        # ligand_coords_denoised  (B, N_lig, 3)
        outputs["ligand_coords_denoised"] = [
            [[_scalar(rng) for _ in range(3)] for _ in range(N_lig)]
            for _ in range(B)
        ]

        # position_loss  scalar
        outputs["position_loss"] = _scalar(rng)

        # atom_type_loss  scalar
        outputs["atom_type_loss"] = _scalar(rng)

        # timestep  scalar float
        outputs["timestep"] = float(timestep)

        # num_atom  (B,)
        outputs["num_atom"] = [N_lig for _ in range(B)]

        # optional pair features
        if enable_optional:
            # ligand_pair_features  (B, N_lig, N_lig, D_pair)
            outputs["ligand_pair_features"] = [
                [
                    [[_scalar(rng) for _ in range(D_pair)] for _ in range(N_lig)]
                    for _ in range(N_lig)
                ]
                for _ in range(B)
            ]

            # protein_ligand_pair_features  (B, N_prot, N_lig, D_cross)
            outputs["protein_ligand_pair_features"] = [
                [
                    [[_scalar(rng) for _ in range(D_cross)] for _ in range(N_lig)]
                    for _ in range(N_prot)
                ]
                for _ in range(B)
            ]

        return outputs

    # -- shape helpers --------------------------------------------------

    @staticmethod
    def get_shape(obj: object) -> tuple:
        """Return the nested-list shape of *obj*.

        Scalars (int, float, None) return ().  Lists return
        (len, *get_shape(first_element)).
        """
        if isinstance(obj, (int, float, type(None))):
            return ()
        if isinstance(obj, list):
            if len(obj) == 0:
                return (0,)
            inner = PMDMAdapterFixtureBuilder.get_shape(obj[0])
            return (len(obj),) + inner
        return ()

    @staticmethod
    def shapes_equal(a: tuple, b: tuple) -> bool:
        """Compare two shape tuples element-wise.

        Returns False when dimensions differ or when either contains a
        non-integer element (indicating a malformed value).
        """
        if len(a) != len(b):
            return False
        for x, y in zip(a, b):
            if not isinstance(x, int) or not isinstance(y, int):
                return False
            if x != y:
                return False
        return True


# ===================================================================
# internal helpers
# ===================================================================


def _scalar(rng: random.Random) -> float:
    """Return a deterministic float in [0, 1) from *rng*."""
    return rng.random()
