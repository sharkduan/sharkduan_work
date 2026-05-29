from __future__ import annotations

import random

from covalent_design.contracts.errors import ContractError
from covalent_design.contracts.types import (
    MESSAGE_WEIGHT_SOURCE_DETACHED_EDGE_PROBABILITY,
    ModelForwardOutput,
)

# ---------------------------------------------------------------------------
# PMDM output key vocabulary
# ---------------------------------------------------------------------------

REQUIRED_PMDM_OUTPUT_KEYS = (
    "ligand_atom_features",
    "protein_atom_features",
    "ligand_coords_denoised",
    "position_loss",
    "atom_type_loss",
    "timestep",
    "num_atom",
)

OPTIONAL_PMDM_OUTPUT_KEYS = (
    "ligand_pair_features",
    "protein_ligand_pair_features",
)

ALL_PMDM_OUTPUT_KEYS = REQUIRED_PMDM_OUTPUT_KEYS + OPTIONAL_PMDM_OUTPUT_KEYS

# ---------------------------------------------------------------------------
# Smoke placeholder for Task 20 fields
# ---------------------------------------------------------------------------


class _SmokePlaceholder:
    """Marker for ModelForwardOutput fields owned by Task 20."""

    def __repr__(self) -> str:
        return "<SmokePlaceholder>"


SMOKE_PLACEHOLDER = _SmokePlaceholder()

# ---------------------------------------------------------------------------
# internal helpers
# ---------------------------------------------------------------------------


def _scalar(rng: random.Random) -> float:
    return rng.random()


def _get_shape(obj: object) -> tuple:
    if isinstance(obj, (int, float, type(None))):
        return ()
    if isinstance(obj, list):
        if len(obj) == 0:
            return (0,)
        inner = _get_shape(obj[0])
        return (len(obj),) + inner
    return ()


def _shapes_equal(a: tuple, b: tuple) -> bool:
    if len(a) != len(b):
        return False
    for x, y in zip(a, b):
        if not isinstance(x, int) or not isinstance(y, int):
            return False
        if x != y:
            return False
    return True


def _normalize_config(config: object) -> dict:
    """Accept either a ModelConfig instance or a flat dict."""
    if hasattr(config, "ligand_feature_dim"):
        pair_dim = getattr(config, "ligand_pair_feature_dim", 0)
        cross_dim = getattr(config, "protein_ligand_pair_feature_dim", 0)
        return {
            "ligand_feature_dim": config.ligand_feature_dim,
            "protein_feature_dim": config.protein_feature_dim,
            "pair_feature_dim": pair_dim,
            "cross_feature_dim": cross_dim,
            "seed": getattr(config, "seed", 42),
            "enable_ligand_pair": pair_dim > 0,
            "enable_cross_pair": cross_dim > 0,
        }
    cfg = config  # type: ignore[assignment]
    if "enable_optional_pair_features" in cfg:
        enable_ligand_pair = bool(cfg["enable_optional_pair_features"])
        enable_cross_pair = bool(cfg["enable_optional_pair_features"])
    else:
        enable_ligand_pair = cfg.get("pair_feature_dim", 0) > 0
        enable_cross_pair = cfg.get("cross_feature_dim", 0) > 0
    return {
        "ligand_feature_dim": cfg.get("ligand_feature_dim", 128),
        "protein_feature_dim": cfg.get("protein_feature_dim", 128),
        "pair_feature_dim": cfg.get("pair_feature_dim", 0),
        "cross_feature_dim": cfg.get("cross_feature_dim", 0),
        "seed": cfg.get("seed", 42),
        "enable_ligand_pair": enable_ligand_pair,
        "enable_cross_pair": enable_cross_pair,
    }


def _build_fake_pmdm_outputs(
    tensors: object,
    *,
    seed: int,
    timestep: float,
    cfg: dict,
) -> dict:
    rng = random.Random(seed)
    B = tensors.protein_coords_shape[0]
    N_lig = tensors.ligand_coords_shape[1]
    N_prot = tensors.protein_coords_shape[1]

    D_lig = cfg["ligand_feature_dim"]
    D_prot = cfg["protein_feature_dim"]

    outputs: dict = {}

    outputs["ligand_atom_features"] = [
        [[_scalar(rng) for _ in range(D_lig)] for _ in range(N_lig)]
        for _ in range(B)
    ]

    outputs["protein_atom_features"] = [
        [[_scalar(rng) for _ in range(D_prot)] for _ in range(N_prot)]
        for _ in range(B)
    ]

    outputs["ligand_coords_denoised"] = [
        [[_scalar(rng) for _ in range(3)] for _ in range(N_lig)]
        for _ in range(B)
    ]

    outputs["position_loss"] = _scalar(rng)
    outputs["atom_type_loss"] = _scalar(rng)
    outputs["timestep"] = float(timestep)
    outputs["num_atom"] = [N_lig for _ in range(B)]

    if cfg["enable_ligand_pair"]:
        D_pair = cfg["pair_feature_dim"]
        outputs["ligand_pair_features"] = [
            [
                [[_scalar(rng) for _ in range(D_pair)] for _ in range(N_lig)]
                for _ in range(N_lig)
            ]
            for _ in range(B)
        ]

    if cfg["enable_cross_pair"]:
        D_cross = cfg["cross_feature_dim"]
        outputs["protein_ligand_pair_features"] = [
            [
                [[_scalar(rng) for _ in range(D_cross)] for _ in range(N_lig)]
                for _ in range(N_prot)
            ]
            for _ in range(B)
        ]

    return outputs


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------


def validate_pmdm_outputs(
    pmdm_outputs: dict,
    *,
    batch: object,
    config: object,
) -> None:
    cfg = _normalize_config(config)
    B = batch.tensors.protein_coords_shape[0]
    N_lig = batch.tensors.ligand_coords_shape[1]
    N_prot = batch.tensors.protein_coords_shape[1]

    for key in REQUIRED_PMDM_OUTPUT_KEYS:
        if key not in pmdm_outputs:
            raise ContractError(
                code="PMDM_MISSING_REQUIRED_KEY",
                owner="model",
                message=f"pmdm_outputs missing required key {key!r}",
            )

    allowed = set(ALL_PMDM_OUTPUT_KEYS)
    for key in pmdm_outputs:
        if key not in allowed:
            raise ContractError(
                code="PMDM_UNKNOWN_KEY",
                owner="model",
                message=f"pmdm_outputs contains unknown key {key!r}",
            )

    optional_expectations = {
        "ligand_pair_features": cfg["enable_ligand_pair"],
        "protein_ligand_pair_features": cfg["enable_cross_pair"],
    }
    for key, expected_present in optional_expectations.items():
        is_present = key in pmdm_outputs
        if expected_present and not is_present:
            raise ContractError(
                code="PMDM_MISSING_OPTIONAL_KEY",
                owner="model",
                message=(
                    f"pmdm_outputs missing optional key {key!r} "
                    "when its feature dimension is enabled"
                ),
            )
        if not expected_present and is_present:
            raise ContractError(
                code="PMDM_UNEXPECTED_OPTIONAL_KEY",
                owner="model",
                message=(
                    f"pmdm_outputs contains optional key {key!r} "
                    "when its feature dimension is disabled"
                ),
            )

    D_lig = cfg["ligand_feature_dim"]
    D_prot = cfg["protein_feature_dim"]

    expected_shapes = {
        "ligand_atom_features": (B, N_lig, D_lig),
        "protein_atom_features": (B, N_prot, D_prot),
        "ligand_coords_denoised": (B, N_lig, 3),
        "position_loss": (),
        "atom_type_loss": (),
        "timestep": (),
        "num_atom": (B,),
    }

    for key, exp_shape in expected_shapes.items():
        actual = _get_shape(pmdm_outputs[key])
        if not _shapes_equal(actual, exp_shape):
            raise ContractError(
                code="PMDM_SHAPE_MISMATCH",
                owner="model",
                message=(
                    f"pmdm_outputs[{key!r}] shape {actual} != expected {exp_shape}"
                ),
            )

    opt_expected = {}
    if cfg["enable_ligand_pair"]:
        opt_expected["ligand_pair_features"] = (
            B, N_lig, N_lig, cfg["pair_feature_dim"]
        )
    if cfg["enable_cross_pair"]:
        opt_expected["protein_ligand_pair_features"] = (
            B, N_prot, N_lig, cfg["cross_feature_dim"]
        )
    for key, exp_shape in opt_expected.items():
        actual = _get_shape(pmdm_outputs[key])
        if not _shapes_equal(actual, exp_shape):
            raise ContractError(
                code="PMDM_SHAPE_MISMATCH",
                owner="model",
                message=(
                    f"pmdm_outputs[{key!r}] shape {actual} != expected {exp_shape}"
                ),
            )


def forward_pmdm(
    *,
    batch: object,
    config: object,
    timestep: float = 0.5,
) -> ModelForwardOutput:
    cfg = _normalize_config(config)

    pmdm_outputs = _build_fake_pmdm_outputs(
        batch.tensors,
        seed=cfg["seed"],
        timestep=timestep,
        cfg=cfg,
    )

    validate_pmdm_outputs(pmdm_outputs, batch=batch, config=config)

    return ModelForwardOutput(
        pmdm_outputs=pmdm_outputs,
        edge_logits=SMOKE_PLACEHOLDER,
        bond_type_logits=SMOKE_PLACEHOLDER,
        family_logits=SMOKE_PLACEHOLDER,
        edge_prob_message_weights=SMOKE_PLACEHOLDER,
        message_weight_source=MESSAGE_WEIGHT_SOURCE_DETACHED_EDGE_PROBABILITY,
        denominators_observed=batch.denominators_expected,
    )
