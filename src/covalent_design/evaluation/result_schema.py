"""Evaluation result row decoder - reconstructs CovalentGenerationResult from JSONL rows."""
from __future__ import annotations

from typing import Callable, Mapping

from covalent_design.contracts.types import (
    ArtifactRef,
    CovalentEdge,
    CovalentGenerationResult,
    EdgeValidityCheck,
    GeometryMetrics,
    LigandAtomIdentity,
    MoleculeQuality,
    ProteinAtomIdentity,
)


def decode_result_row(row: Mapping[str, object]) -> CovalentGenerationResult:
    """Decode a JSONL row dict into a CovalentGenerationResult."""
    return CovalentGenerationResult(
        request_id=_require_str(row, "request_id"),
        sample_id=_require_int(row, "sample_id"),
        residue_reaction_family=_require_str(row, "residue_reaction_family"),
        target_atom_identity=_decode_protein_atom(_require_dict(row, "target_atom_identity")),
        generation_validity_status=_require_str(row, "generation_validity_status"),
        complex_export_status=_require_str(row, "complex_export_status"),
        docking_eligibility_status=_require_str(row, "docking_eligibility_status"),
        docking_run_status=_require_str(row, "docking_run_status"),
        primary_failure_reason=_optional_str(row, "primary_failure_reason"),
        secondary_failure_reasons=_decode_string_tuple(row, "secondary_failure_reasons"),
        generated_ligand_status=_str(row.get("generated_ligand_status"), default="absent"),
        predicted_ligand_attachment_atom=_optional_nested(
            row, "predicted_ligand_attachment_atom", _decode_ligand_atom
        ),
        predicted_covalent_edge=_optional_nested(
            row, "predicted_covalent_edge", _decode_covalent_edge
        ),
        covalent_edge_score=_optional_float(row, "covalent_edge_score"),
        geometry_metrics=_optional_nested(
            row, "geometry_metrics", _decode_geometry_metrics
        ),
        molecular_quality_metrics=_optional_nested(
            row, "molecular_quality_metrics", _decode_molecule_quality
        ),
        matched_warhead_type=_optional_str(row, "matched_warhead_type"),
        predicted_warhead_type=_optional_str(row, "predicted_warhead_type"),
        covalent_docking_score=_optional_float(row, "covalent_docking_score"),
        noncovalent_vina_score=_optional_float(row, "noncovalent_vina_score"),
        edge_validity_checks=_decode_edge_checks(row),
        artifacts=_decode_artifacts(row),
    )


# ---------------------------------------------------------------------------
# nested dataclass decoders
# ---------------------------------------------------------------------------


def _decode_protein_atom(d: dict[str, object]) -> ProteinAtomIdentity:
    return ProteinAtomIdentity(
        chain_id=_optional_str(d, "chain_id"),
        residue_number=_optional_int(d, "residue_number"),
        residue_name=_require_str(d, "residue_name"),
        atom_name=_require_str(d, "atom_name"),
        altloc=_optional_str(d, "altloc"),
        insertion_code=_optional_str(d, "insertion_code"),
        structure_model=_optional_int(d, "structure_model"),
        asym_id=_optional_str(d, "asym_id"),
        atom_serial=_optional_int(d, "atom_serial"),
    )


def _decode_ligand_atom(d: dict[str, object]) -> LigandAtomIdentity:
    return LigandAtomIdentity(
        ligand_id=_require_str(d, "ligand_id"),
        atom_name=_require_str(d, "atom_name"),
        atom_index=_optional_int(d, "atom_index"),
        chain_id=_optional_str(d, "chain_id"),
        asym_id=_optional_str(d, "asym_id"),
        residue_number=_optional_int(d, "residue_number"),
        altloc=_optional_str(d, "altloc"),
    )


def _decode_covalent_edge(d: dict[str, object]) -> CovalentEdge:
    return CovalentEdge(
        protein_atom=_decode_protein_atom(_require_dict(d, "protein_atom")),
        ligand_atom=_decode_ligand_atom(_require_dict(d, "ligand_atom")),
        bond_type=_require_str(d, "bond_type"),
    )


def _decode_geometry_metrics(d: dict[str, object]) -> GeometryMetrics:
    return GeometryMetrics(
        bond_length=_optional_float(d, "bond_length"),
        protein_side_angle=_optional_float(d, "protein_side_angle"),
        ligand_side_angle=_optional_float(d, "ligand_side_angle"),
    )


def _decode_molecule_quality(d: dict[str, object]) -> MoleculeQuality:
    return MoleculeQuality(
        qed=_optional_float(d, "qed"),
        sa_score=_optional_float(d, "sa_score"),
        log_p=_optional_float(d, "log_p"),
        molecular_weight=_optional_float(d, "molecular_weight"),
    )


def _decode_edge_check(d: dict[str, object]) -> EdgeValidityCheck:
    return EdgeValidityCheck(
        check_name=_require_str(d, "check_name"),
        status=_require_str(d, "status"),
        observed_value=_require_str(d, "observed_value"),
        threshold_or_rule=_require_str(d, "threshold_or_rule"),
        rule_table_version=_require_str(d, "rule_table_version"),
        failure_code=_optional_str(d, "failure_code"),
    )


def _decode_artifact_ref(d: dict[str, object]) -> ArtifactRef:
    return ArtifactRef(
        uri=_require_str(d, "uri"),
        sha256=_require_str(d, "sha256"),
        format=_require_str(d, "format"),
        schema_version=_str(d.get("schema_version"), default="1"),
        role=_str(d.get("role"), default=""),
        bytes=_optional_int(d, "bytes", default=0),
    )


def _decode_string_tuple(d: Mapping[str, object], key: str) -> tuple[str, ...]:
    values = _optional_list(d, key)
    if any(not isinstance(value, str) for value in values):
        raise ValueError(f"Expected list of strings for {key!r}")
    return tuple(values)  # type: ignore[arg-type]


def _decode_edge_checks(d: Mapping[str, object]) -> tuple[EdgeValidityCheck, ...]:
    values = _optional_list(d, "edge_validity_checks")
    if any(not isinstance(value, dict) for value in values):
        raise ValueError("Expected list of dicts for 'edge_validity_checks'")
    return tuple(_decode_edge_check(value) for value in values)  # type: ignore[arg-type]


def _decode_artifacts(d: Mapping[str, object]) -> dict[str, ArtifactRef]:
    values = _optional_dict(d, "artifacts")
    if any(not isinstance(value, dict) for value in values.values()):
        raise ValueError("Expected artifact refs to be dicts")
    return {
        key: _decode_artifact_ref(value)  # type: ignore[arg-type]
        for key, value in values.items()
    }


# ---------------------------------------------------------------------------
# helpers - safe extractors from JSON-compatible dicts
# ---------------------------------------------------------------------------


def _require_str(d: Mapping[str, object], key: str) -> str:
    v = d[key]
    if not isinstance(v, str):
        raise ValueError(
            f"Expected string for {key!r}, got {type(v).__name__}"
        )
    return v


def _optional_str(d: Mapping[str, object], key: str) -> str | None:
    v = d.get(key)
    if v is None:
        return None
    if not isinstance(v, str):
        raise ValueError(
            f"Expected string or null for {key!r}, got {type(v).__name__}"
        )
    return v


def _str(v: object, *, default: str) -> str:
    if v is None:
        return default
    if not isinstance(v, str):
        raise ValueError(f"Expected string, got {type(v).__name__}")
    return v


def _require_int(d: Mapping[str, object], key: str) -> int:
    v = d[key]
    if isinstance(v, bool) or not isinstance(v, int):
        raise ValueError(
            f"Expected integer for {key!r}, got {type(v).__name__}"
        )
    return v


def _optional_int(
    d: Mapping[str, object],
    key: str,
    *,
    default: int | None = None,
) -> int | None:
    v = d.get(key)
    if v is None:
        return default
    if isinstance(v, bool) or not isinstance(v, int):
        raise ValueError(
            f"Expected integer or null for {key!r}, got {type(v).__name__}"
        )
    return v


def _optional_float(d: Mapping[str, object], key: str) -> float | None:
    v = d.get(key)
    if v is None:
        return None
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise ValueError(
            f"Expected float or null for {key!r}, got {type(v).__name__}"
        )
    return float(v)


def _require_dict(d: Mapping[str, object], key: str) -> dict[str, object]:
    v = d[key]
    if not isinstance(v, dict):
        raise ValueError(
            f"Expected dict for {key!r}, got {type(v).__name__}"
        )
    return v


def _optional_dict(d: Mapping[str, object], key: str) -> dict[str, object]:
    v = d.get(key)
    if v is None:
        return {}
    if not isinstance(v, dict):
        raise ValueError(f"Expected dict or null for {key!r}, got {type(v).__name__}")
    return v


def _optional_list(d: Mapping[str, object], key: str) -> list[object]:
    v = d.get(key)
    if v is None:
        return []
    if not isinstance(v, list):
        raise ValueError(f"Expected list or null for {key!r}, got {type(v).__name__}")
    return v


def _optional_nested(
    d: Mapping[str, object],
    key: str,
    decoder: Callable[[dict[str, object]], object],
) -> object:
    v = d.get(key)
    if v is None:
        return None
    if not isinstance(v, dict):
        raise ValueError(
            f"Expected dict or null for {key!r}, got {type(v).__name__}"
        )
    return decoder(v)
