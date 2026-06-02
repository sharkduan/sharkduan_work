"""Task 24: Smoke training loop.

Orchestrates one smoke training step: load singleton microbatches,
build dynamic candidates, run PMDM + covalent forward passes, compute
task 23 audits/denominators/strata, and compute losses.  Aggregates
four deterministic singleton microbatches into one step ``LossReport``
and emits exactly one ``train_metrics.jsonl`` row.
"""

from __future__ import annotations

import json
from pathlib import Path

from covalent_design._yaml_loader import load_yaml_config
from covalent_design.contracts.types import LossReport, LossWeights
from covalent_design.model.candidate_builder import (
    build_stepwise_candidate_batch,
    build_stepwise_candidates,
)
from covalent_design.model.config import ModelConfig
from covalent_design.model.covalent_heads import forward_covalent
from covalent_design.model.pmdm_adapter import forward_pmdm
from covalent_design.training.batch import load_training_batch
from covalent_design.training.dataset import prepare_dataset
from covalent_design.training.losses import compute_losses
from covalent_design.training.masks import (
    NormalizedMaskFlags,
    resolve_mask_flags,
)


def _resolve_path(raw: str, config_dir: Path) -> Path:
    """Resolve a config path relative to the config file directory."""
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


def _build_mask_flags(cfg: dict) -> NormalizedMaskFlags:
    mf = cfg.get("mask_flags", {})
    return resolve_mask_flags(
        pending_smarts=mf.get("pending_smarts", False),
        pending_geometry=mf.get("pending_geometry", False),
        missing_required_chemical_state=mf.get("missing_required_chemical_state", False),
        quality_tier=mf.get("quality_tier", "Q1"),
        exclude_q2=mf.get("exclude_q2", False),
    )


def _build_weights(cfg: dict) -> LossWeights:
    w = cfg.get("loss_weights", {})
    return LossWeights(
        pmdm_position_loss=w.get("pmdm_position_loss", 1.0),
        pmdm_atom_loss=w.get("pmdm_atom_loss", 1.0),
        covalent_edge_loss=w.get("covalent_edge_loss", 1.0),
        covalent_bond_type_loss=w.get("covalent_bond_type_loss", 1.0),
        covalent_geometry_loss=w.get("covalent_geometry_loss", 1.0),
        family_aux_loss=w.get("family_aux_loss", 1.0),
    )


def _load_artifacts_for_record(batch, record, records_root: Path):
    """Read protein_atom_table, ligand_atom_table, and edge_candidates for one record."""
    import json as _json

    edge_uri = batch.static_edge_candidates_refs[record.record_id].uri
    edge_path = records_root / edge_uri
    edge_artifact = _json.loads(edge_path.read_text("utf-8"))

    for ref in record.artifact_refs.values():
        if ref.role == "protein_atom_table":
            prot_path = records_root / ref.uri
            break
    else:
        raise ValueError("protein_atom_table artifact not found")
    protein_atoms = _json.loads(prot_path.read_text("utf-8"))["atoms"]

    for ref in record.artifact_refs.values():
        if ref.role == "ligand_atom_table":
            lig_path = records_root / ref.uri
            break
    else:
        raise ValueError("ligand_atom_table artifact not found")
    ligand_atoms = _json.loads(lig_path.read_text("utf-8"))["atoms"]

    return protein_atoms, ligand_atoms, edge_artifact


def _aggregate_microbatch_losses(
    reports: list[LossReport], weights: LossWeights, step: int
) -> LossReport:
    """Aggregate multiple LossReports into one by averaging components and summing audits."""
    n = len(reports)
    if n == 0:
        raise ValueError("no microbatch reports to aggregate")

    avg_components: dict[str, float] = {}
    for key in reports[0].components:
        avg_components[key] = sum(r.components[key] for r in reports) / n

    total_loss = sum(
        getattr(weights, key) * avg_components[key] for key in avg_components
    )

    # Rebuild DenominatorStratumEntry objects from each report's strata and
    # re-aggregate so that microbatches sharing the same (family, bucket) are
    # merged with summed mask audits.
    from covalent_design.training.denominators import (
        DenominatorStratumEntry,
        aggregate_denominator_strata,
    )

    _BUCKET_MIDPOINTS = {"early": 0.9, "mid": 0.5, "late": 0.1}

    raw_entries: list[DenominatorStratumEntry] = []
    for r in reports:
        for s in r.strata:
            raw_entries.append(
                DenominatorStratumEntry(
                    residue_reaction_family=s.residue_reaction_family,
                    timestep_value=_BUCKET_MIDPOINTS.get(s.timestep_bucket, 0.5),
                    mask_audit=s.mask_audit,
                )
            )
    agg_strata = aggregate_denominator_strata(raw_entries)

    # Sum denominators and audits across all microbatches
    from covalent_design.training.losses import _sum_denominators, _sum_mask_audits

    agg_denoms = _sum_denominators(
        [r.denominators for r in reports if r.denominators is not None]
    )
    agg_audit = _sum_mask_audits(
        [r.mask_audit for r in reports if r.mask_audit is not None]
    )

    return LossReport(
        step=step,
        total_loss=total_loss,
        components=avg_components,
        denominators=agg_denoms,
        mask_audit=agg_audit,
        strata=agg_strata,
    )


def run_smoke_train(config_path: str) -> LossReport:
    """Execute one smoke training step and write ``train_metrics.jsonl``.

    Parameters
    ----------
    config_path : str
        Path to a ``covalent_train_smoke.yml`` config file.

    Returns
    -------
    LossReport
        The aggregated step-level loss report that was also written to disk.
    """
    cfg = load_yaml_config(config_path)
    config_dir = Path(config_path).resolve().parent
    repo_root = config_dir.parent

    records_path = _resolve_path(cfg["records_path"], repo_root)
    split_index_path = _resolve_path(cfg["split_index_path"], repo_root)
    split_name = cfg.get("split_name", "train")
    output_dir = _resolve_path(cfg.get("output_dir", "."), repo_root)
    steps = cfg.get("steps", 1)
    batch_size = cfg.get("batch_size", 4)
    timestep_value = cfg.get("timestep", 0.5)
    if isinstance(steps, bool) or not isinstance(steps, int) or steps != 1:
        raise ValueError("smoke training requires steps=1")

    model_config = _build_model_config(cfg)
    mask_flags = _build_mask_flags(cfg)
    weights = _build_weights(cfg)

    # -- prepare dataset -----------------------------------------------------
    dataset = prepare_dataset(records_path, split_index_path, split_name).payload

    microbatch_reports: list[LossReport] = []

    config_seed = model_config.seed

    for mb_idx in range(batch_size):
        batch_id = f"batch-{mb_idx}"

        # Load singleton batch through Task 22 -> Task 17
        envelope = load_training_batch(dataset, batch_id)
        singleton_batch = envelope.payload

        record = singleton_batch.records[0]
        records_root = records_path.parent

        protein_atoms, ligand_atoms, edge_artifact = _load_artifacts_for_record(
            singleton_batch, record, records_root
        )

        # Build stepwise candidates for the singleton record
        candidate_set = build_stepwise_candidates(
            protein_atoms=protein_atoms,
            ligand_atoms=ligand_atoms,
            edge_candidates_artifact=edge_artifact,
            timestep_index=0,
            timestep_value=timestep_value,
            candidate_radius_angstrom=model_config.candidate_radius_angstrom,
        )
        dynamic_batch = build_stepwise_candidate_batch((candidate_set,))

        # Per-microbatch config with deterministic seed
        mb_config = ModelConfig(
            seed=config_seed + mb_idx,
            fake_backbone=model_config.fake_backbone,
            ligand_feature_dim=model_config.ligand_feature_dim,
            protein_feature_dim=model_config.protein_feature_dim,
            ligand_pair_feature_dim=model_config.ligand_pair_feature_dim,
            protein_ligand_pair_feature_dim=model_config.protein_ligand_pair_feature_dim,
            hidden_dim=model_config.hidden_dim,
            candidate_radius_angstrom=model_config.candidate_radius_angstrom,
        )

        # Forward passes
        pmdm_output = forward_pmdm(batch=singleton_batch, config=mb_config, timestep=timestep_value)
        forward_output = forward_covalent(
            pmdm_output=pmdm_output,
            batch=singleton_batch,
            config=mb_config,
            stepwise_candidate_batch=dynamic_batch,
        )

        # Compute losses per microbatch
        report = compute_losses(
            forward_output,
            model_batch=singleton_batch,
            stepwise_candidate_batch=dynamic_batch,
            mask_flags=(mask_flags,),
            weights=weights,
        )

        microbatch_reports.append(report)

    # -- aggregate into one step report --------------------------------------
    step_report = _aggregate_microbatch_losses(microbatch_reports, weights, step=0)

    # -- write train_metrics.jsonl -------------------------------------------
    output_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = output_dir / "train_metrics.jsonl"
    with open(metrics_path, "w", encoding="utf-8") as fh:
        json.dump(step_report.to_dict(), fh, sort_keys=True)
        fh.write("\n")

    return step_report
