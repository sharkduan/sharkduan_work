from __future__ import annotations

import hashlib
import json
from pathlib import Path

from covalent_design.contracts.types import (
    CONTRACT_VERSION,
    SCHEMA_VERSION,
    TrainingRunManifest,
)


def canonical_json(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_bytes(value: bytes) -> str:
    return f"sha256:{hashlib.sha256(value).hexdigest()}"


def sha256_file(path) -> str:
    return sha256_bytes(Path(path).read_bytes())


def hash_resolved_config(resolved_config) -> str:
    return sha256_bytes(canonical_json(resolved_config).encode("utf-8"))


def hash_rule_table(path) -> str:
    from covalent_design.rules.validate import _parse_minimal_yaml

    data = _parse_minimal_yaml(Path(path).read_text("utf-8"))
    return sha256_bytes(canonical_json(data).encode("utf-8"))


def build_training_input_hashes(
    *,
    records_path,
    split_index_path,
    rule_table_path,
    quality_report_path,
    visual_check_index_path,
    release_gate_path=None,
) -> dict:
    hashes = {
        "records_jsonl": sha256_file(records_path),
        "split_index": sha256_file(split_index_path),
        "rule_table": hash_rule_table(rule_table_path),
        "quality_report": sha256_file(quality_report_path),
        "visual_check_index": sha256_file(visual_check_index_path),
    }
    if release_gate_path is not None:
        hashes["release_gate"] = sha256_file(release_gate_path)
    return hashes


def build_training_run_manifest(
    *,
    run_id,
    resolved_config,
    records_path,
    split_index_path,
    rule_table_path,
    quality_report_path,
    visual_check_index_path,
    checkpoint_dir,
    train_metrics_uri,
    validation_metrics_uri,
    denominator_report_uri,
    release_gate_path=None,
    train_completed=False,
    epochs_completed=0,
    steps_completed=0,
    crash_recovery=None,
) -> TrainingRunManifest:
    if not run_id:
        raise ValueError("run_id must not be empty")
    if epochs_completed < 0 or steps_completed < 0:
        raise ValueError("completion counters must be non-negative")
    input_hashes = build_training_input_hashes(
        records_path=records_path,
        split_index_path=split_index_path,
        rule_table_path=rule_table_path,
        quality_report_path=quality_report_path,
        visual_check_index_path=visual_check_index_path,
        release_gate_path=release_gate_path,
    )
    return TrainingRunManifest(
        schema_version=SCHEMA_VERSION,
        contract_version=CONTRACT_VERSION,
        role="training_run_manifest",
        run_id=run_id,
        training_config_resolved_hash=hash_resolved_config(resolved_config),
        input_hashes=input_hashes,
        checkpoint_dir=checkpoint_dir,
        train_metrics_uri=train_metrics_uri,
        validation_metrics_uri=validation_metrics_uri,
        denominator_report_uri=denominator_report_uri,
        train_completed=train_completed,
        epochs_completed=epochs_completed,
        steps_completed=steps_completed,
        crash_recovery=crash_recovery,
    )


def training_run_manifest_to_dict(manifest: TrainingRunManifest) -> dict:
    return {
        "schema_version": manifest.schema_version,
        "contract_version": manifest.contract_version,
        "role": manifest.role,
        "run_id": manifest.run_id,
        "training_config_resolved_hash": manifest.training_config_resolved_hash,
        "input_hashes": {
            key: manifest.input_hashes[key] for key in sorted(manifest.input_hashes)
        },
        "checkpoint_dir": manifest.checkpoint_dir,
        "train_metrics_uri": manifest.train_metrics_uri,
        "validation_metrics_uri": manifest.validation_metrics_uri,
        "denominator_report_uri": manifest.denominator_report_uri,
        "train_completed": manifest.train_completed,
        "epochs_completed": manifest.epochs_completed,
        "steps_completed": manifest.steps_completed,
        "crash_recovery": manifest.crash_recovery,
    }
