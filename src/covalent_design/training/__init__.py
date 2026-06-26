"""Public training package facade with lazy exports.

The facade keeps historical import names available while avoiding import-time
side effects from optional training, checkpoint, and model-adapter modules.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS: dict[str, tuple[str, str]] = {
    "CHECKPOINT_REQUIRED_INPUT_HASH_KEYS": ("covalent_design.training.checkpoints", "CHECKPOINT_REQUIRED_INPUT_HASH_KEYS"),
    "CheckpointMetadata": ("covalent_design.training.checkpoints", "CheckpointMetadata"),
    "DenominatorStratumEntry": ("covalent_design.training.denominators", "DenominatorStratumEntry"),
    "NormalizedMaskFlags": ("covalent_design.training.masks", "NormalizedMaskFlags"),
    "TrainingDataPolicy": ("covalent_design.training.dataset", "TrainingDataPolicy"),
    "V2TrainLoopConfig": ("covalent_design.training.v2_train_loop", "V2TrainLoopConfig"),
    "V2ExcludedRecord": ("covalent_design.training.v2_dataset", "V2ExcludedRecord"),
    "V2ExclusionSummary": ("covalent_design.training.v2_dataset", "V2ExclusionSummary"),
    "V2TrainingDataPolicy": ("covalent_design.training.v2_dataset", "V2TrainingDataPolicy"),
    "V2TrainingDatasetIndex": ("covalent_design.training.v2_dataset", "V2TrainingDatasetIndex"),
    "V2TrainingRecordEntry": ("covalent_design.training.v2_dataset", "V2TrainingRecordEntry"),
    "V2TrainingSummary": ("covalent_design.training.v2_train_loop", "V2TrainingSummary"),
    "V2TinySweepConfig": ("covalent_design.training.v2_tuning", "V2TinySweepConfig"),
    "V2TrialResult": ("covalent_design.training.v2_tuning", "V2TrialResult"),
    "V2TuningSummary": ("covalent_design.training.v2_tuning", "V2TuningSummary"),
    "V2CheckpointExperimentManifest": ("covalent_design.training.v2_manifests", "V2CheckpointExperimentManifest"),
    "V2CheckpointRef": ("covalent_design.training.v2_manifests", "V2CheckpointRef"),
    "V2DependencyLockProvenance": ("covalent_design.training.v2_manifests", "V2DependencyLockProvenance"),
    "V2FullBetaConfig": ("covalent_design.training.v2_full_beta", "V2FullBetaConfig"),
    "V2FullBetaSummary": ("covalent_design.training.v2_full_beta", "V2FullBetaSummary"),
    "aggregate_denominator_strata": ("covalent_design.training.denominators", "aggregate_denominator_strata"),
    "build_edge_denominators": ("covalent_design.training.denominators", "build_edge_denominators"),
    "build_training_input_hashes": ("covalent_design.training.reports", "build_training_input_hashes"),
    "build_training_run_manifest": ("covalent_design.training.reports", "build_training_run_manifest"),
    "build_v2_checkpoint_experiment_manifest": ("covalent_design.training.v2_manifests", "build_v2_checkpoint_experiment_manifest"),
    "canonical_json": ("covalent_design.training.reports", "canonical_json"),
    "checkpoint_metadata_to_dict": ("covalent_design.training.checkpoints", "checkpoint_metadata_to_dict"),
    "classify_timestep_bucket": ("covalent_design.training.denominators", "classify_timestep_bucket"),
    "compute_losses": ("covalent_design.training.losses", "compute_losses"),
    "compute_mask_audit": ("covalent_design.training.masks", "compute_mask_audit"),
    "hash_resolved_config": ("covalent_design.training.reports", "hash_resolved_config"),
    "hash_rule_table": ("covalent_design.training.reports", "hash_rule_table"),
    "load_training_batch": ("covalent_design.training.batch", "load_training_batch"),
    "prepare_dataset": ("covalent_design.training.dataset", "prepare_dataset"),
    "prepare_v2_dataset": ("covalent_design.training.v2_dataset", "prepare_v2_dataset"),
    "read_checkpoint_metadata": ("covalent_design.training.checkpoints", "read_checkpoint_metadata"),
    "resolve_mask_flags": ("covalent_design.training.masks", "resolve_mask_flags"),
    "run_smoke_train": ("covalent_design.training.train_loop", "run_smoke_train"),
    "run_v2_full_beta_train": ("covalent_design.training.v2_full_beta", "run_v2_full_beta_train"),
    "run_v2_tune": ("covalent_design.training.v2_tuning", "run_v2_tune"),
    "run_v2_train": ("covalent_design.training.v2_train_loop", "run_v2_train"),
    "sha256_bytes": ("covalent_design.training.reports", "sha256_bytes"),
    "sha256_file": ("covalent_design.training.reports", "sha256_file"),
    "training_run_manifest_to_dict": ("covalent_design.training.reports", "training_run_manifest_to_dict"),
    "hash_v2_checkpoint_experiment_manifest": ("covalent_design.training.v2_manifests", "hash_v2_checkpoint_experiment_manifest"),
    "serialize_v2_checkpoint_experiment_manifest": ("covalent_design.training.v2_manifests", "serialize_v2_checkpoint_experiment_manifest"),
    "v2_checkpoint_experiment_manifest_to_dict": ("covalent_design.training.v2_manifests", "v2_checkpoint_experiment_manifest_to_dict"),
    "v2_full_beta_summary_to_dict": ("covalent_design.training.v2_full_beta", "v2_full_beta_summary_to_dict"),
    "v2_hash_bytes": ("covalent_design.training.v2_manifests", "v2_hash_bytes"),
    "v2_hash_file": ("covalent_design.training.v2_manifests", "v2_hash_file"),
    "v2_hash_object": ("covalent_design.training.v2_manifests", "v2_hash_object"),
    "v2_trial_result_to_dict": ("covalent_design.training.v2_tuning", "v2_trial_result_to_dict"),
    "v2_training_dataset_index_to_dict": ("covalent_design.training.v2_dataset", "v2_training_dataset_index_to_dict"),
    "v2_training_summary_to_dict": ("covalent_design.training.v2_train_loop", "v2_training_summary_to_dict"),
    "v2_tuning_summary_to_dict": ("covalent_design.training.v2_tuning", "v2_tuning_summary_to_dict"),
    "validate_checkpoint_metadata": ("covalent_design.training.checkpoints", "validate_checkpoint_metadata"),
    "validate_v2_checkpoint_experiment_manifest": ("covalent_design.training.v2_manifests", "validate_v2_checkpoint_experiment_manifest"),
    "write_checkpoint_metadata": ("covalent_design.training.checkpoints", "write_checkpoint_metadata"),
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    try:
        module_name, attr_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc
    value = getattr(import_module(module_name), attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
