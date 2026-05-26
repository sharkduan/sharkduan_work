"""Visual check artifact exporter."""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Optional

from covalent_design.contracts.errors import ContractErrorInfo
from covalent_design.contracts.types import (
    CONTRACT_VERSION,
    SCHEMA_VERSION,
    ContractEnvelope,
    ValidationReceipt,
)
from covalent_design.io.artifacts import sha256_file
from covalent_design.io.jsonl import read_jsonl

VISUAL_CHECKS_VALIDATOR = "covalent_design.viz.export_visual_checks"

BLOCKING_STATUSES = frozenset({"pending", "fail", "needs_rule_review"})
VALID_VISUAL_STATUSES = frozenset({"pending", "pass", "fail", "needs_rule_review"})


def export_visual_checks(
    records_path: Path,
    out_root: Path,
    sample_count: Optional[int] = None,
    seed: int = 42,
) -> ContractEnvelope[dict[str, object]]:
    records_path = records_path.resolve()
    records = list(read_jsonl(records_path))
    input_sha256 = sha256_file(records_path)
    artifact_root = records_path.parent

    records.sort(key=lambda r: str(r.get("record_id", "")))

    rng = random.Random(seed)
    if sample_count is not None and sample_count < len(records):
        sampled = rng.sample(records, sample_count)
    else:
        sampled = list(records)

    sampled.sort(key=lambda r: str(r.get("record_id", "")))

    errors = _validate_sampled_records(sampled, artifact_root)

    if errors:
        return ContractEnvelope(
            payload={},
            artifacts=(),
            receipt=ValidationReceipt(
                validator=VISUAL_CHECKS_VALIDATOR,
                contract_version=CONTRACT_VERSION,
                input_sha256=input_sha256,
                passed=False,
                errors=tuple(errors),
            ),
        )

    out_root = Path(out_root)
    index_records: list[dict[str, object]] = []
    status_counts: dict[str, int] = {
        "pending": 0,
        "pass": 0,
        "fail": 0,
        "needs_rule_review": 0,
    }

    for record in sampled:
        record_id = str(record.get("record_id", ""))
        core_labels = record.get("core_labels")
        if not isinstance(core_labels, dict):
            core_labels = {}
        metadata = record.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}

        visual_status = metadata.get("visual_check_status", "pending")
        if visual_status not in VALID_VISUAL_STATUSES:
            visual_status = "pending"
        blocking = visual_status in BLOCKING_STATUSES

        artifact = _build_visual_artifact(record, artifact_root, visual_status, blocking)

        artifact_dir = out_root / "artifacts" / record_id
        artifact_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = artifact_dir / "visual_check.json"
        artifact_path.write_text(
            json.dumps(artifact, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        artifact_ref = {
            "role": "visual_check",
            "uri": f"artifacts/{record_id}/visual_check.json",
            "sha256": sha256_file(artifact_path),
            "format": "json",
            "schema_version": SCHEMA_VERSION,
            "bytes": artifact_path.stat().st_size,
        }

        index_records.append({
            "record_id": record_id,
            "status": visual_status,
            "blocking_first_core": blocking,
            "artifact_ref": artifact_ref,
        })
        status_counts[visual_status] = status_counts.get(visual_status, 0) + 1

    blocking_count = sum(1 for r in index_records if r["blocking_first_core"])
    non_blocking_count = len(index_records) - blocking_count

    index = {
        "schema_version": SCHEMA_VERSION,
        "contract_version": CONTRACT_VERSION,
        "role": "visual_check_index",
        "sample_policy": {
            "sample_count": sample_count,
            "seed": seed,
            "total_accepted": len(records),
        },
        "blocking_counts": {
            "blocking_first_core": blocking_count,
            "non_blocking": non_blocking_count,
        },
        "status_counts": status_counts,
        "records": index_records,
    }

    out_root.mkdir(parents=True, exist_ok=True)
    index_path = out_root / "visual_check_index.json"
    index_path.write_text(
        json.dumps(index, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    return ContractEnvelope(
        payload={"sampled_count": len(sampled)},
        artifacts=(),
        receipt=ValidationReceipt(
            validator=VISUAL_CHECKS_VALIDATOR,
            contract_version=CONTRACT_VERSION,
            input_sha256=input_sha256,
            passed=True,
        ),
    )


def _validate_sampled_records(
    sampled: list[dict[str, object]],
    artifact_root: Path,
) -> list[ContractErrorInfo]:
    errors: list[ContractErrorInfo] = []
    for record in sampled:
        record_id = str(record.get("record_id", ""))

        artifacts = record.get("artifacts")
        if not isinstance(artifacts, list):
            errors.append(
                ContractErrorInfo(
                    code="ARTIFACT_LIST_MISSING",
                    owner="data",
                    message=f"Record {record_id}: artifacts list missing or invalid",
                    location=f"records/{record_id}",
                )
            )
            continue

        edge_artifact = None
        for art in artifacts:
            if isinstance(art, dict) and art.get("role") == "edge_candidates":
                edge_artifact = art
                break

        if edge_artifact is None:
            errors.append(
                ContractErrorInfo(
                    code="ARTIFACT_EDGE_CANDIDATE_MISSING",
                    owner="data",
                    message=f"Record {record_id}: missing edge_candidates artifact",
                    location=f"records/{record_id}",
                )
            )
            continue

        edge_uri = edge_artifact.get("uri", "")
        edge_path = artifact_root / edge_uri
        if not edge_path.exists():
            errors.append(
                ContractErrorInfo(
                    code="ARTIFACT_EDGE_CANDIDATE_MISSING",
                    owner="data",
                    message=f"Record {record_id}: edge_candidates artifact file not found: {edge_uri}",
                    location=f"records/{record_id}",
                )
            )
            continue

        for required_role in ("protein_atom_table", "ligand_atom_table"):
            required = _artifact_by_role(record, required_role)
            if required is None:
                errors.append(
                    ContractErrorInfo(
                        code=f"ARTIFACT_{required_role.upper()}_MISSING",
                        owner="data",
                        message=f"Record {record_id}: missing {required_role} artifact",
                        location=f"records/{record_id}",
                    )
                )
                continue
            required_path = artifact_root / str(required.get("uri", ""))
            if not required_path.exists():
                errors.append(
                    ContractErrorInfo(
                        code=f"ARTIFACT_{required_role.upper()}_MISSING",
                        owner="data",
                        message=f"Record {record_id}: {required_role} artifact file not found",
                        location=f"records/{record_id}",
                    )
                )
                continue

        core_labels = record.get("core_labels")
        if not isinstance(core_labels, dict):
            errors.append(
                ContractErrorInfo(
                    code="ARTIFACT_CORE_LABELS_MISSING",
                    owner="data",
                    message=f"Record {record_id}: core_labels missing or invalid",
                    location=f"records/{record_id}",
                )
            )
            continue

    return errors


def _build_visual_artifact(
    record: dict[str, object],
    artifact_root: Path,
    visual_status: object,
    blocking_first_core: bool,
) -> dict[str, object]:
    record_id = str(record.get("record_id", ""))
    core_labels = record.get("core_labels")
    if not isinstance(core_labels, dict):
        core_labels = {}
    metadata = record.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}

    target_atom_name = str(core_labels.get("target_atom_name", ""))
    ligand_atom_name = str(core_labels.get("ligand_atom_name", ""))

    edge = _load_edge_candidate(record, artifact_root)
    protein_atom = _find_atom(
        _load_artifact_json(record, artifact_root, "protein_atom_table"),
        target_atom_name,
    )
    ligand_atom = _find_atom(
        _load_artifact_json(record, artifact_root, "ligand_atom_table"),
        ligand_atom_name,
    )

    geometry = metadata.get("geometry")
    if isinstance(geometry, dict):
        bond_length = geometry.get("bond_length")
        protein_side_angle = geometry.get("protein_side_angle")
        ligand_side_angle = geometry.get("ligand_side_angle")
    else:
        bond_length = None
        protein_side_angle = None
        ligand_side_angle = None

    if isinstance(bond_length, dict):
        distance_value = bond_length.get("value")
    else:
        distance_value = None

    psa_value = protein_side_angle.get("value") if isinstance(protein_side_angle, dict) else None
    lsa_value = ligand_side_angle.get("value") if isinstance(ligand_side_angle, dict) else None
    local_angles = None
    if psa_value is not None or lsa_value is not None:
        local_angles = {
            "protein_side": psa_value,
            "ligand_side": lsa_value,
        }

    family = str(core_labels.get("residue_reaction_family", ""))

    target_atom = _atom_summary(
        protein_atom,
        target_atom_name,
        "protein_atom_table",
    )
    ligand_attachment_atom = _atom_summary(
        ligand_atom,
        ligand_atom_name,
        "ligand_atom_table",
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "contract_version": CONTRACT_VERSION,
        "role": "visual_check",
        "record_id": record_id,
        "status": visual_status,
        "blocking_first_core": blocking_first_core,
        "target_atom": target_atom,
        "ligand_attachment_atom": ligand_attachment_atom,
        "covalent_edge": {
            "target_atom": {
                "name": edge.get("target_atom_name", target_atom["name"]),
                "element": edge.get("target_atom_element", target_atom["element"]),
            },
            "ligand_atom": {
                "name": edge.get("ligand_atom_name", ligand_attachment_atom["name"]),
                "element": edge.get(
                    "ligand_atom_element",
                    ligand_attachment_atom["element"],
                ),
            },
            "bond_length": edge.get("distance_angstrom"),
            "bond_type": str(core_labels.get("bond_type", "")),
        },
        "residue_reaction_family": family,
        "warhead_annotation": {
            "warhead_type": str(core_labels.get("warhead_type", "")),
            "warhead_smarts": None,
        },
        "distance": distance_value,
        "local_angles": local_angles,
    }


def _artifact_by_role(
    record: dict[str, object],
    role: str,
) -> Optional[dict[str, object]]:
    artifacts = record.get("artifacts")
    if not isinstance(artifacts, list):
        return None
    for artifact in artifacts:
        if isinstance(artifact, dict) and artifact.get("role") == role:
            return artifact
    return None


def _load_artifact_json(
    record: dict[str, object],
    artifact_root: Path,
    role: str,
) -> dict[str, object]:
    artifact = _artifact_by_role(record, role)
    if artifact is None:
        return {}
    uri = str(artifact.get("uri", ""))
    path = artifact_root / uri
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _load_edge_candidate(
    record: dict[str, object],
    artifact_root: Path,
) -> dict[str, object]:
    artifact = _load_artifact_json(record, artifact_root, "edge_candidates")
    positive_edge = artifact.get("positive_edge")
    if isinstance(positive_edge, dict):
        return positive_edge
    return {}


def _find_atom(atom_table: dict[str, object], atom_name: str) -> dict[str, object]:
    atoms = atom_table.get("atoms")
    if isinstance(atoms, list):
        for atom in atoms:
            if isinstance(atom, dict) and str(atom.get("name", "")) == atom_name:
                result = dict(atom)
                for table_key in ("chain_id", "residue_name", "residue_number", "ligand_id"):
                    if table_key in atom_table and table_key not in result:
                        result[table_key] = atom_table[table_key]
                return result
    return {}


def _atom_summary(atom: dict[str, object], atom_name: str, source_role: str) -> dict[str, object]:
    return {
        "name": str(atom.get("name", atom_name)),
        "element": str(atom.get("element", _element_from_atom_name(atom_name))),
        "serial": atom.get("serial"),
        "chain_id": atom.get("chain_id"),
        "residue_name": atom.get("residue_name"),
        "residue_number": atom.get("residue_number"),
        "ligand_id": atom.get("ligand_id"),
        "x": atom.get("x"),
        "y": atom.get("y"),
        "z": atom.get("z"),
        "source_role": source_role,
    }


def _element_from_atom_name(atom_name: str) -> str:
    letters: list[str] = []
    seen_letter = False
    for char in atom_name:
        if char.isalpha():
            letters.append(char)
            seen_letter = True
        elif seen_letter:
            break
    return "".join(letters).upper()
