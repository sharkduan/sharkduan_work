"""Task 28 internal result serializer — deterministic, JSON-compatible only."""

from __future__ import annotations

import dataclasses

from covalent_design.contracts.types import CovalentGenerationResult


def _result_to_dict(result: CovalentGenerationResult) -> dict[str, object]:
    """Serialize a CovalentGenerationResult to a JSON-compatible dict.

    Does NOT include ``schema_version`` or ``contract_version`` — those
    are injected by Task 27's ``write_jsonl()`` via ``setdefault``.
    """
    return {
        "request_id": result.request_id,
        "sample_id": result.sample_id,
        "residue_reaction_family": result.residue_reaction_family,
        "target_atom_identity": _json_compatible(result.target_atom_identity),
        "generation_validity_status": result.generation_validity_status,
        "complex_export_status": result.complex_export_status,
        "docking_eligibility_status": result.docking_eligibility_status,
        "docking_run_status": result.docking_run_status,
        "primary_failure_reason": result.primary_failure_reason,
        "secondary_failure_reasons": _json_compatible(result.secondary_failure_reasons),
        "generated_ligand_status": result.generated_ligand_status,
        "predicted_ligand_attachment_atom": _json_compatible(
            result.predicted_ligand_attachment_atom
        ),
        "predicted_covalent_edge": _json_compatible(result.predicted_covalent_edge),
        "covalent_edge_score": result.covalent_edge_score,
        "geometry_metrics": _json_compatible(result.geometry_metrics),
        "molecular_quality_metrics": _json_compatible(
            result.molecular_quality_metrics
        ),
        "matched_warhead_type": result.matched_warhead_type,
        "predicted_warhead_type": result.predicted_warhead_type,
        "covalent_docking_score": result.covalent_docking_score,
        "noncovalent_vina_score": result.noncovalent_vina_score,
        "edge_validity_checks": _json_compatible(result.edge_validity_checks),
        "artifacts": {
            key: _json_compatible(value)
            for key, value in sorted(result.artifacts.items())
        },
    }


def _json_compatible(value: object) -> object:
    """Recursively convert to JSON-compatible Python values.

    Dataclasses become dicts, tuples become lists, and mapping keys
    are sorted for deterministic serialization order.
    """
    if value is None:
        return None
    if isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, tuple):
        return [_json_compatible(item) for item in value]
    if isinstance(value, list):
        return [_json_compatible(item) for item in value]
    if isinstance(value, dict):
        return {
            _json_compatible(k): _json_compatible(v)
            for k, v in sorted(value.items())
        }
    if dataclasses.is_dataclass(value):
        result: dict[str, object] = {}
        for f in dataclasses.fields(value):
            result[f.name] = _json_compatible(getattr(value, f.name))
        return result
    raise TypeError(
        f"Unsupported type {type(value).__name__} for JSON-compatible conversion"
    )
