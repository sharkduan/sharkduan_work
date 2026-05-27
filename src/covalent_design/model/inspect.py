"""Task 17 per-record ModelBatch inspection with inline errors."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Optional

from covalent_design.contracts.errors import ContractError, ContractErrorInfo
from covalent_design.contracts.types import (
    CONTRACT_VERSION,
    SCHEMA_VERSION,
    ArtifactRef,
    EdgeDenominators,
    ProteinAtomIdentity,
)
from covalent_design.io.artifacts import resolve_artifact_path, validate_artifact_ref
from covalent_design.io.jsonl import read_jsonl


REQUIRED_ROLES = (
    "coordinates",
    "protein_atom_table",
    "ligand_atom_table",
    "ligand_bond_table",
    "edge_candidates",
)


def inspect_batch(
    records_path: object,
    record_id: Optional[str] = None,
) -> dict:
    """Inspect records and report per-record Task 17 batch readiness."""
    path = Path(records_path)
    root = path.parent

    report = {
        "schema_version": SCHEMA_VERSION,
        "contract_version": CONTRACT_VERSION,
        "batch_spec": None,
        "records": [],
        "passed": True,
        "errors": [],
        "warnings": [],
    }

    try:
        rows = read_jsonl(path, require_versions=True)
    except OSError as exc:
        report["passed"] = False
        report["errors"].append(
            {
                "code": "MODEL_BATCH_ARTIFACT_MISSING",
                "message": str(exc),
                "location": str(path),
            }
        )
        return report
    except ValueError as exc:
        report["passed"] = False
        report["errors"].append(
            {
                "code": "MODEL_BATCH_CONTRACT_VERSION_UNSUPPORTED",
                "message": str(exc),
                "location": str(path),
            }
        )
        return report

    if len(rows) == 0:
        report["passed"] = False
        report["errors"].append(
            {
                "code": "MODEL_BATCH_ARTIFACT_MISSING",
                "message": "records.jsonl is empty",
                "location": str(path),
            }
        )
        return report

    seen_any = False
    for line_index, row in enumerate(rows):
        row_record_id = row.get("record_id", "")
        if not isinstance(row_record_id, str):
            continue
        if record_id is not None and row_record_id != record_id:
            continue

        seen_any = True
        record_report = _inspect_one_record(row, line_index, root)
        report["records"].append(record_report)

        if record_report.get("error"):
            report["passed"] = False
            report["errors"].append(
                {
                    "code": record_report.get("error_code", "UNKNOWN"),
                    "message": record_report["error"],
                    "record_id": row_record_id,
                    "line": line_index + 1,
                }
            )

    if record_id is not None and not seen_any:
        report["passed"] = False
        report["errors"].append(
            {
                "code": "RECORD_NOT_FOUND",
                "message": f"record_id {record_id!r} not found",
                "record_id": record_id,
            }
        )

    records_hash = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
    report["batch_spec"] = _aggregate_batch_spec(report["records"], records_hash)
    return report


def _inspect_one_record(row: dict, line_index: int, root: Path) -> dict:
    row_record_id = row.get("record_id", f"line_{line_index + 1}")
    if not isinstance(row_record_id, str):
        row_record_id = f"line_{line_index + 1}"

    record_report = {
        "record_id": row_record_id,
        "line": line_index + 1,
        "error": None,
        "error_code": None,
        "provenance": None,
        "tensor_shapes": None,
        "denominators_expected": None,
        "batch_spec": None,
        "warnings": [],
    }

    try:
        _inspect_impl(row, line_index, root, record_report)
    except ContractError as exc:
        record_report["error"] = exc.message
        record_report["error_code"] = exc.code
        record_report["warnings"] = [f"{exc.code}: {exc.message}"]
    except Exception as exc:
        record_report["error"] = str(exc)
        record_report["error_code"] = "MODEL_BATCH_ARTIFACT_UNREADABLE"
        record_report["warnings"] = [f"MODEL_BATCH_ARTIFACT_UNREADABLE: {exc}"]

    return record_report


def _inspect_impl(row: dict, line_index: int, root: Path, record_report: dict) -> None:
    row_record_id = record_report["record_id"]

    schema_version = row.get("schema_version")
    if schema_version != SCHEMA_VERSION:
        raise ContractError(
            code="MODEL_BATCH_CONTRACT_VERSION_UNSUPPORTED",
            owner="model",
            message=f"unsupported schema_version {schema_version!r}",
            location=f"line {line_index + 1}",
        )

    contract_version = row.get("contract_version")
    if contract_version != CONTRACT_VERSION:
        raise ContractError(
            code="MODEL_BATCH_CONTRACT_VERSION_UNSUPPORTED",
            owner="model",
            message=f"unsupported contract_version {contract_version!r}",
            location=f"line {line_index + 1}",
        )

    metadata = row.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    chemical_state = metadata.get("chemical_state")
    chemical_state_status = "unavailable"
    if isinstance(chemical_state, dict):
        chemical_state_status = chemical_state.get("status", "unavailable")
    if chemical_state_status == "unavailable":
        raise ContractError(
            code="MODEL_BATCH_REQUIRED_STATE_UNAVAILABLE",
            owner="model",
            message=f"chemical state unavailable for record {row_record_id}",
            location=f"line {line_index + 1}",
        )

    quality = metadata.get("quality")
    quality_tier = "Q1"
    if isinstance(quality, dict):
        quality_tier = quality.get("quality_tier", "Q1")

    core_labels = row.get("core_labels")
    if not isinstance(core_labels, dict):
        raise ContractError(
            code="MODEL_BATCH_ARTIFACT_UNREADABLE",
            owner="model",
            message="core_labels missing",
            location=f"line {line_index + 1}",
        )

    artifacts = _artifact_refs_by_role(row, line_index)
    _validate_required_roles(artifacts, line_index)
    _validate_artifacts(artifacts, root, line_index, row_record_id)

    protein_data = _read_json_artifact(artifacts["protein_atom_table"], root)
    protein_atoms = protein_data.get("atoms", [])
    protein_count = len(protein_atoms) if isinstance(protein_atoms, list) else 0
    target_atom_index = core_labels.get("target_atom_index", 0)
    target_atom_name = core_labels.get("target_atom_name", "")
    target_identity = ProteinAtomIdentity(
        chain_id=protein_data.get("chain_id"),
        residue_number=protein_data.get("residue_number"),
        residue_name=protein_data.get("residue_name", ""),
        atom_name=target_atom_name,
        atom_serial=_target_atom_serial(
            protein_atoms,
            target_atom_index if isinstance(target_atom_index, int) else -1,
            target_atom_name if isinstance(target_atom_name, str) else "",
        ),
    )

    ligand_data = _read_json_artifact(artifacts["ligand_atom_table"], root)
    ligand_atoms = ligand_data.get("atoms", [])
    ligand_count = len(ligand_atoms) if isinstance(ligand_atoms, list) else 0

    edge_data = _read_json_artifact(artifacts["edge_candidates"], root)
    denominators_raw = edge_data.get("denominators", {})
    denominators = EdgeDenominators(**denominators_raw) if denominators_raw else None
    candidate_count = denominators.candidate_count if denominators else 0

    record_report["provenance"] = {
        "record_id": row_record_id,
        "residue_reaction_family": core_labels.get("residue_reaction_family", ""),
        "quality_tier": quality_tier,
        "visual_check_status": "pending",
        "chemical_state_status": chemical_state_status,
        "target_atom_identity": {
            "chain_id": target_identity.chain_id,
            "residue_number": target_identity.residue_number,
            "residue_name": target_identity.residue_name,
            "atom_name": target_identity.atom_name,
            "atom_serial": target_identity.atom_serial,
        },
        "target_atom_index": target_atom_index,
        "target_atom_artifact_role": "protein_atom_table",
        "artifact_refs": {
            role: ref.uri for role, ref in sorted(artifacts.items())
        },
        "batch_index": -1,
    }
    record_report["tensor_shapes"] = {
        "protein_coords_shape": [1, protein_count, 3],
        "ligand_coords_shape": [1, ligand_count, 3],
        "protein_atom_types_shape": [1, protein_count],
        "ligand_atom_types_shape": [1, ligand_count],
        "ligand_bonds_shape": [1, ligand_count, ligand_count],
        "edge_candidates_shape": [1, candidate_count],
        "positive_label_mask_shape": [1, candidate_count],
        "candidate_to_ligand_map_shape": [1, candidate_count],
        "candidate_to_protein_map_shape": [1, candidate_count],
        "dtype": "float32",
        "index_dtype": "int64",
        "coordinate_frame": "original_pdb",
    }
    record_report["denominators_expected"] = (
        _denominators_to_dict(denominators) if denominators else None
    )
    record_report["batch_spec"] = _record_batch_spec(
        core_labels,
        protein_count,
        ligand_count,
        candidate_count,
    )


def _artifact_refs_by_role(row: dict, line_index: int) -> dict[str, ArtifactRef]:
    artifacts_list = row.get("artifacts")
    if not isinstance(artifacts_list, list):
        raise ContractError(
            code="MODEL_BATCH_ARTIFACT_UNREADABLE",
            owner="model",
            message="artifacts missing",
            location=f"line {line_index + 1}",
        )

    artifacts = {}
    for item in artifacts_list:
        if not isinstance(item, dict):
            continue
        ref = ArtifactRef(
            uri=str(item.get("uri", "")),
            sha256=str(item.get("sha256", "")),
            format=str(item.get("format", "")),
            schema_version=str(item.get("schema_version", SCHEMA_VERSION)),
            role=str(item.get("role", "")),
            bytes=int(item.get("bytes", 0)),
        )
        if ref.role:
            artifacts[ref.role] = ref
    return artifacts


def _validate_required_roles(artifacts: dict[str, ArtifactRef], line_index: int) -> None:
    for role in REQUIRED_ROLES:
        if role not in artifacts:
            raise ContractError(
                code="MODEL_BATCH_ARTIFACT_ROLE_MISSING",
                owner="model",
                message=f"missing required artifact role {role!r}",
                location=f"line {line_index + 1}",
            )


def _validate_artifacts(
    artifacts: dict[str, ArtifactRef],
    root: Path,
    line_index: int,
    record_id: str,
) -> None:
    for role, ref in artifacts.items():
        if ref.schema_version != SCHEMA_VERSION:
            raise ContractError(
                code="MODEL_BATCH_CONTRACT_VERSION_UNSUPPORTED",
                owner="model",
                message=f"unsupported artifact schema_version {ref.schema_version!r}",
                location=f"line {line_index + 1}",
                details={"record_id": record_id, "role": role},
            )
        receipt = validate_artifact_ref(ref, root=root)
        if not receipt.passed:
            _raise_model_artifact_error(receipt.errors, line_index, record_id)
        _read_artifact(ref, root, line_index)


def _read_artifact(ref: ArtifactRef, root: Path, line_index: int) -> str:
    path = resolve_artifact_path(ref, root=root)
    try:
        raw = path.read_text(encoding="utf-8")
        if ref.format == "json":
            json.loads(raw)
        elif ref.format == "pdb":
            wrapper = json.loads(raw)
            if not isinstance(wrapper, dict) or "data" not in wrapper:
                raise ContractError(
                    code="MODEL_BATCH_ARTIFACT_UNREADABLE",
                    owner="model",
                    message=f"invalid PDB wrapper in {ref.uri}",
                    location=f"line {line_index + 1}",
                )
        return raw
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(
            code="MODEL_BATCH_ARTIFACT_UNREADABLE",
            owner="model",
            message=f"cannot read {ref.uri}: {exc}",
            location=f"line {line_index + 1}",
        ) from exc


def _read_json_artifact(ref: ArtifactRef, root: Path) -> dict:
    path = resolve_artifact_path(ref, root=root)
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _raise_model_artifact_error(
    errors: tuple[ContractErrorInfo, ...],
    line_index: int,
    record_id: str,
) -> None:
    for error in errors:
        if error.code == "ARTIFACT_NOT_FOUND":
            raise ContractError(
                code="MODEL_BATCH_ARTIFACT_MISSING",
                owner="model",
                message=error.message,
                location=f"line {line_index + 1}",
                details={"record_id": record_id},
            )
        if error.code in (
            "ARTIFACT_CHECKSUM_MISMATCH",
            "ARTIFACT_BYTE_COUNT_MISMATCH",
        ):
            raise ContractError(
                code="MODEL_BATCH_ARTIFACT_CHECKSUM_MISMATCH",
                owner="model",
                message=error.message,
                location=f"line {line_index + 1}",
                details={"record_id": record_id},
            )
        raise ContractError(
            code="MODEL_BATCH_ARTIFACT_MISSING",
            owner="model",
            message=error.message,
            location=f"line {line_index + 1}",
            details={"record_id": record_id},
        )


def _denominators_to_dict(denominators: EdgeDenominators) -> dict:
    return {
        "candidate_count": denominators.candidate_count,
        "natural_candidate_count": denominators.natural_candidate_count,
        "forced_positive_count": denominators.forced_positive_count,
        "eligible_edge_count": denominators.eligible_edge_count,
        "masked_candidate_count": denominators.masked_candidate_count,
        "edge_loss_denominator": denominators.edge_loss_denominator,
        "bond_type_loss_denominator": denominators.bond_type_loss_denominator,
        "geometry_loss_denominator": denominators.geometry_loss_denominator,
        "message_passing_candidate_count": denominators.message_passing_candidate_count,
        "gate_evaluated_count": denominators.gate_evaluated_count,
    }


def _target_atom_serial(
    atoms: list,
    target_atom_index: int,
    target_atom_name: str,
) -> Optional[int]:
    if 0 <= target_atom_index < len(atoms):
        atom = atoms[target_atom_index]
        if isinstance(atom, dict):
            serial = atom.get("serial")
            if isinstance(serial, int):
                return serial

    for atom in atoms:
        if not isinstance(atom, dict):
            continue
        name = atom.get("name")
        serial = atom.get("serial")
        if name == target_atom_name and isinstance(serial, int):
            return serial
    return None


def _record_batch_spec(
    core_labels: dict,
    protein_count: int,
    ligand_count: int,
    candidate_count: int,
) -> dict:
    vocabulary = ["no_edge"]
    bond_type = core_labels.get("bond_type")
    if isinstance(bond_type, str) and bond_type and bond_type != "no_edge":
        vocabulary.append(bond_type)
    return {
        "bond_type_vocabulary": vocabulary,
        "max_protein_atoms": protein_count,
        "max_ligand_atoms": ligand_count,
        "max_candidates": candidate_count,
        "candidate_radius_angstrom": 4.0,
        "coordinate_frame": "original_pdb",
        "records_jsonl_hash": None,
    }


def _aggregate_batch_spec(records: list[dict], records_jsonl_hash: Optional[str]) -> Optional[dict]:
    specs = [row.get("batch_spec") for row in records if row.get("batch_spec")]
    if not specs:
        return None

    bond_types = set()
    for spec in specs:
        for value in spec.get("bond_type_vocabulary", []):
            if value != "no_edge":
                bond_types.add(value)

    return {
        "bond_type_vocabulary": ["no_edge"] + sorted(bond_types),
        "max_protein_atoms": max(spec["max_protein_atoms"] for spec in specs),
        "max_ligand_atoms": max(spec["max_ligand_atoms"] for spec in specs),
        "max_candidates": max(spec["max_candidates"] for spec in specs),
        "candidate_radius_angstrom": 4.0,
        "coordinate_frame": "original_pdb",
        "records_jsonl_hash": records_jsonl_hash,
    }
