from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Optional

from covalent_design.contracts.errors import ContractErrorInfo
from covalent_design.contracts.types import (
    CONTRACT_VERSION,
    SCHEMA_VERSION,
    ArtifactRef,
    ContractEnvelope,
    ValidationReceipt,
)
from covalent_design.io import read_jsonl
from covalent_design.io.artifacts import artifact_ref_from_file, sha256_file


def _distance(ax: float, ay: float, az: float, bx: float, by: float, bz: float) -> float:
    return math.sqrt((ax - bx) ** 2 + (ay - by) ** 2 + (az - bz) ** 2)


def _find_artifact_ref(artifacts: list[dict[str, Any]], role: str) -> Optional[dict[str, Any]]:
    for ref in artifacts:
        if ref.get("role") == role:
            return ref
    return None


def _build_denominators(
    candidate_count: int,
    natural_candidate_count: int,
    forced_positive_count: int,
) -> dict[str, int]:
    eligible = candidate_count
    masked = 0
    return {
        "candidate_count": candidate_count,
        "natural_candidate_count": natural_candidate_count,
        "forced_positive_count": forced_positive_count,
        "eligible_edge_count": eligible,
        "masked_candidate_count": masked,
        "edge_loss_denominator": eligible,
        "bond_type_loss_denominator": eligible,
        "geometry_loss_denominator": eligible,
        "message_passing_candidate_count": natural_candidate_count,
        "gate_evaluated_count": candidate_count,
    }


def _process_record(
    record: dict[str, Any],
    records_dir: Path,
    radius: float,
    errors: list[ContractErrorInfo],
) -> Optional[dict[str, Any]]:
    record_id: str = record["record_id"]
    core_labels: dict[str, Any] = record["core_labels"]
    artifact_list: list[dict[str, Any]] = record.get("artifacts", [])

    target_atom_name = core_labels["target_atom_name"]
    positive_ligand_atom_name = core_labels["ligand_atom_name"]
    positive_ligand_element = core_labels.get("ligand_atom_element", "")

    # --- resolve protein_atom_table ---
    protein_ref = _find_artifact_ref(artifact_list, "protein_atom_table")
    if protein_ref is None:
        errors.append(
            ContractErrorInfo(
                code="PROTEIN_ATOM_TABLE_MISSING",
                owner="data",
                message=f"Record {record_id}: protein_atom_table artifact not found",
                location=record_id,
            )
        )
        return None

    protein_path = records_dir / protein_ref["uri"]
    if not protein_path.exists():
        errors.append(
            ContractErrorInfo(
                code="ARTIFACT_MISSING_PROTEIN_ATOM_TABLE",
                owner="data",
                message=f"Record {record_id}: protein_atom_table file not found at {protein_path}",
                location=record_id,
            )
        )
        return None

    try:
        protein_data = json.loads(protein_path.read_text("utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        errors.append(
            ContractErrorInfo(
                code="PROTEIN_ATOM_TABLE_UNREADABLE",
                owner="data",
                message=f"Record {record_id}: cannot read protein_atom_table: {exc}",
                location=record_id,
            )
        )
        return None

    protein_atoms: list[dict[str, Any]] = protein_data.get("atoms", [])
    target_atom = None
    for atom in protein_atoms:
        if atom.get("name") == target_atom_name:
            target_atom = atom
            break

    if target_atom is None:
        errors.append(
            ContractErrorInfo(
                code="PROTEIN_TARGET_ATOM_NOT_FOUND",
                owner="data",
                message=f"Record {record_id}: target atom {target_atom_name} not found in protein_atom_table",
                location=record_id,
            )
        )
        return None

    tx = target_atom["x"]
    ty = target_atom["y"]
    tz = target_atom["z"]
    target_atom_element = target_atom.get("element", "")

    # --- resolve ligand_atom_table ---
    ligand_ref = _find_artifact_ref(artifact_list, "ligand_atom_table")
    if ligand_ref is None:
        errors.append(
            ContractErrorInfo(
                code="LIGAND_ATOM_TABLE_MISSING",
                owner="data",
                message=f"Record {record_id}: ligand_atom_table artifact not found",
                location=record_id,
            )
        )
        return None

    ligand_path = records_dir / ligand_ref["uri"]
    if not ligand_path.exists():
        errors.append(
            ContractErrorInfo(
                code="ARTIFACT_MISSING_LIGAND_ATOM_TABLE",
                owner="data",
                message=f"Record {record_id}: ligand_atom_table file not found at {ligand_path}",
                location=record_id,
            )
        )
        return None

    try:
        ligand_data = json.loads(ligand_path.read_text("utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        errors.append(
            ContractErrorInfo(
                code="LIGAND_ATOM_TABLE_UNREADABLE",
                owner="data",
                message=f"Record {record_id}: cannot read ligand_atom_table: {exc}",
                location=record_id,
            )
        )
        return None

    ligand_atoms: list[dict[str, Any]] = ligand_data.get("atoms", [])

    # --- compute distances from target atom to all ligand atoms ---
    ligand_distances: list[tuple[dict[str, Any], float]] = []
    positive_atom: Optional[dict[str, Any]] = None
    positive_distance: Optional[float] = None

    for atom in ligand_atoms:
        lx = atom["x"]
        ly = atom["y"]
        lz = atom["z"]
        dist = _distance(tx, ty, tz, lx, ly, lz)
        if atom["name"] == positive_ligand_atom_name:
            positive_atom = atom
            positive_distance = dist
        else:
            ligand_distances.append((atom, dist))

    if positive_atom is None:
        errors.append(
            ContractErrorInfo(
                code="LIGAND_POSITIVE_ATOM_NOT_FOUND",
                owner="data",
                message=f"Record {record_id}: positive ligand atom {positive_ligand_atom_name} not found",
                location=record_id,
            )
        )
        return None

    # --- build positive edge ---
    positive_edge = {
        "target_atom_name": target_atom_name,
        "target_atom_element": target_atom_element,
        "ligand_atom_name": positive_ligand_atom_name,
        "ligand_atom_element": positive_ligand_element,
        "distance_angstrom": round(positive_distance, 4),
    }

    # --- build negative edges (non-positive ligand atoms within radius) ---
    negative_edges: list[dict[str, Any]] = []
    natural_candidate_count = 1 if positive_distance < radius else 0

    for atom, dist in ligand_distances:
        if dist < radius:
            negative_edges.append(
                {
                    "ligand_atom_name": atom["name"],
                    "ligand_atom_element": atom.get("element", ""),
                    "distance_angstrom": round(dist, 4),
                }
            )
            natural_candidate_count += 1

    negative_edges.sort(key=lambda n: (n["distance_angstrom"], n["ligand_atom_name"]))

    empty_radius_window = len(negative_edges) == 0
    forced_positive_count = 0 if positive_distance < radius else 1
    candidate_count = 1 + len(negative_edges)

    denominators = _build_denominators(
        candidate_count=candidate_count,
        natural_candidate_count=natural_candidate_count,
        forced_positive_count=forced_positive_count,
    )

    # --- build artifact_refs for input artifacts ---
    artifact_refs: list[dict[str, Any]] = []
    for role in ("coordinates", "protein_atom_table", "ligand_atom_table"):
        ref = _find_artifact_ref(artifact_list, role)
        if ref is not None:
            artifact_refs.append(
                {
                    "role": role,
                    "uri": ref["uri"],
                    "sha256": ref["sha256"],
                    "format": ref.get("format", "json"),
                    "schema_version": ref.get("schema_version", SCHEMA_VERSION),
                    "bytes": ref.get("bytes", 0),
                }
            )

    return {
        "schema_version": SCHEMA_VERSION,
        "contract_version": CONTRACT_VERSION,
        "record_id": record_id,
        "role": "edge_candidates",
        "lineage": record.get("lineage", []),
        "positive_edge": positive_edge,
        "negative_edges": negative_edges,
        "denominators": denominators,
        "artifact_refs": artifact_refs,
        "empty_radius_window": empty_radius_window,
    }


def build_edge_candidates(
    records_path: Path,
    candidate_radius_angstrom: float = 4.0,
) -> ContractEnvelope[dict[str, Any]]:
    records_dir = records_path.resolve().parent
    records = read_jsonl(records_path, require_versions=False)

    errors: list[ContractErrorInfo] = []
    edge_candidates: list[dict[str, Any]] = []

    for record in records:
        record_id = record.get("record_id", "")
        artifact_list = record.get("artifacts", [])

        # --- check for missing protein/ligand before processing ---
        coordinates_ref = _find_artifact_ref(artifact_list, "coordinates")
        has_protein = _find_artifact_ref(artifact_list, "protein_atom_table") is not None
        has_ligand = _find_artifact_ref(artifact_list, "ligand_atom_table") is not None

        if coordinates_ref is None:
            errors.append(
                ContractErrorInfo(
                    code="COORDINATES_ARTIFACT_MISSING",
                    owner="data",
                    message=f"Record {record_id}: coordinates artifact not in records",
                    location=record_id,
                )
            )
            continue
        coordinates_path = records_dir / coordinates_ref["uri"]
        if not coordinates_path.exists():
            errors.append(
                ContractErrorInfo(
                    code="COORDINATES_FILE_MISSING",
                    owner="data",
                    message=f"Record {record_id}: coordinates file not found at {coordinates_path}",
                    location=record_id,
                )
            )
            continue
        if not has_protein:
            errors.append(
                ContractErrorInfo(
                    code="PROTEIN_ATOM_TABLE_MISSING",
                    owner="data",
                    message=f"Record {record_id}: protein_atom_table artifact not in records",
                    location=record_id,
                )
            )
            continue
        if not has_ligand:
            errors.append(
                ContractErrorInfo(
                    code="LIGAND_ATOM_TABLE_MISSING",
                    owner="data",
                    message=f"Record {record_id}: ligand_atom_table artifact not in records",
                    location=record_id,
                )
            )
            continue

        result = _process_record(record, records_dir, candidate_radius_angstrom, errors)
        if result is not None:
            edge_candidates.append(result)

    # --- write per-record edge_candidates.json artifacts ---
    artifact_refs: list[ArtifactRef] = []
    for ec in edge_candidates:
        rid = ec["record_id"]
        out_path = records_dir / "artifacts" / rid / "edge_candidates.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(ec, indent=2, sort_keys=True), encoding="utf-8")
        ref = artifact_ref_from_file(out_path, role="edge_candidates", root=records_dir)
        artifact_refs.append(ref)

    # --- build receipt ---
    sha_input = sha256_file(records_path)
    passed = len(errors) == 0
    receipt = ValidationReceipt(
        validator="covalent_design.candidates.edge_candidates.build_edge_candidates",
        contract_version=CONTRACT_VERSION,
        input_sha256=sha_input,
        ok=passed,
        errors=tuple(errors),
    )

    payload: dict[str, Any] = {
        "edge_candidate_count": len(edge_candidates),
        "record_count": len(records),
        "radius_angstrom": candidate_radius_angstrom,
    }

    return ContractEnvelope(
        payload=payload,
        artifacts=tuple(artifact_refs),
        receipt=receipt,
    )
