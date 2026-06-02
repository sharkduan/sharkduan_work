"""Task 24: Forward smoke CLI.

Usage::

    python -m covalent_design.model.forward_smoke

Produces a deterministic JSON shape summary of the PMDM + covalent forward
pipeline against the smoke bundle.
"""

from __future__ import annotations

import argparse
import json as _json
from pathlib import Path

from covalent_design._yaml_loader import load_yaml_config
from covalent_design.model.batch import make_model_batch
from covalent_design.model.candidate_builder import (
    build_stepwise_candidate_batch,
    build_stepwise_candidates,
)
from covalent_design.model.config import ModelConfig
from covalent_design.model.covalent_heads import forward_covalent
from covalent_design.model.pmdm_adapter import forward_pmdm


def _resolve_path(raw: str, config_dir: Path) -> Path:
    p = Path(raw)
    if p.is_absolute():
        return p
    return (config_dir / p).resolve()


def _build_model_config(cfg: dict) -> ModelConfig:
    mc = cfg.get("model_config", {})
    return ModelConfig(
        seed=mc.get("seed", 42),
        fake_backbone=mc.get("fake_backbone", True),
        ligand_feature_dim=mc.get("ligand_feature_dim", 128),
        protein_feature_dim=mc.get("protein_feature_dim", 128),
        ligand_pair_feature_dim=mc.get("ligand_pair_feature_dim", 0),
        protein_ligand_pair_feature_dim=mc.get("protein_ligand_pair_feature_dim", 0),
        hidden_dim=mc.get("hidden_dim", 256),
        candidate_radius_angstrom=mc.get("candidate_radius_angstrom", 4.0),
    )


def main(argv: list[str] | None = None) -> None:
    """Run the forward smoke pipeline and print a deterministic shape summary."""
    parser = argparse.ArgumentParser(description="Run the Task 24 forward smoke path.")
    parser.add_argument("--config", default=None, help="Path to smoke YAML config.")
    args = parser.parse_args(argv)

    repo_root = Path(__file__).resolve().parents[3]
    config_path = (
        Path(args.config).resolve()
        if args.config
        else repo_root / "configs" / "covalent_model_smoke.yml"
    )

    if not config_path.exists():
        raise FileNotFoundError(f"config not found: {config_path}")

    cfg = load_yaml_config(str(config_path))
    config_dir = config_path.parent
    repo_root = config_dir.parent

    records_path = _resolve_path(cfg["records_path"], repo_root)
    timestep_value = cfg.get("timestep", 0.5)
    model_config = _build_model_config(cfg)

    # Build model batch from the smoke records
    envelope = make_model_batch(records_path)
    batch = envelope.payload

    # Build stepwise candidates for each record
    records_root = records_path.parent
    candidate_sets = []
    for record in batch.records:
        edge_uri = batch.static_edge_candidates_refs[record.record_id].uri
        edge_path = records_root / edge_uri
        edge_artifact = _json.loads(edge_path.read_text("utf-8"))

        for ref in record.artifact_refs.values():
            if ref.role == "protein_atom_table":
                prot_path = records_root / ref.uri
                break
        else:
            raise ValueError("protein_atom_table not found")
        protein_atoms = _json.loads(prot_path.read_text("utf-8"))["atoms"]

        for ref in record.artifact_refs.values():
            if ref.role == "ligand_atom_table":
                lig_path = records_root / ref.uri
                break
        else:
            raise ValueError("ligand_atom_table not found")
        ligand_atoms = _json.loads(lig_path.read_text("utf-8"))["atoms"]

        candidate_set = build_stepwise_candidates(
            protein_atoms=protein_atoms,
            ligand_atoms=ligand_atoms,
            edge_candidates_artifact=edge_artifact,
            timestep_index=0,
            timestep_value=timestep_value,
            candidate_radius_angstrom=model_config.candidate_radius_angstrom,
        )
        candidate_sets.append(candidate_set)

    dynamic_batch = build_stepwise_candidate_batch(tuple(candidate_sets))

    # PMDM forward
    pmdm_output = forward_pmdm(
        batch=batch, config=model_config, timestep=timestep_value
    )

    # Covalent forward
    forward_output = forward_covalent(
        pmdm_output=pmdm_output,
        batch=batch,
        config=model_config,
        stepwise_candidate_batch=dynamic_batch,
    )

    # Build deterministic shape summary
    summary = {
        "contract_version": "1.0.0",
        "schema_version": "1",
        "batch_size": len(batch.records),
        "pmdm_shapes": {
            "ligand_atom_features": _shape_desc(pmdm_output.pmdm_outputs["ligand_atom_features"]),
            "protein_atom_features": _shape_desc(pmdm_output.pmdm_outputs["protein_atom_features"]),
            "ligand_coords_denoised": _shape_desc(pmdm_output.pmdm_outputs["ligand_coords_denoised"]),
            "timestep": pmdm_output.pmdm_outputs["timestep"],
        },
        "covalent_shapes": {
            "edge_logits": list(forward_output.edge_logits.shape),
            "bond_type_logits": list(forward_output.bond_type_logits.shape),
            "family_logits": list(forward_output.family_logits.shape),
            "edge_prob_message_weights": list(forward_output.edge_prob_message_weights.shape),
        },
        "denominators_observed": _denom_dict(forward_output.denominators_observed),
    }
    print(_json.dumps(summary, sort_keys=True))


def _shape_desc(data: object) -> list[int]:
    """Return a nested-list shape for pure-Python tensor data."""
    if isinstance(data, list):
        inner = _shape_desc(data[0]) if data else []
        return [len(data)] + inner
    return []


def _denom_dict(d: object) -> dict:
    """Serialize EdgeDenominators to a JSON-safe dict."""
    return {
        "candidate_count": d.candidate_count,
        "natural_candidate_count": d.natural_candidate_count,
        "forced_positive_count": d.forced_positive_count,
        "eligible_edge_count": d.eligible_edge_count,
        "masked_candidate_count": d.masked_candidate_count,
        "edge_loss_denominator": d.edge_loss_denominator,
        "bond_type_loss_denominator": d.bond_type_loss_denominator,
        "geometry_loss_denominator": d.geometry_loss_denominator,
        "message_passing_candidate_count": d.message_passing_candidate_count,
        "gate_evaluated_count": d.gate_evaluated_count,
    }


if __name__ == "__main__":
    main()
