"""Build record indexes from normalized linkage data."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from covalent_design.contracts.errors import ContractErrorInfo
from covalent_design.contracts.types import (
    CONTRACT_VERSION,
    SCHEMA_VERSION,
    ContractEnvelope,
    ValidationReceipt,
)
from covalent_design.data.artifact_manifests import (
    artifact_ref_to_dict,
    build_artifact_manifest,
    discover_required_artifacts,
)
from covalent_design.io.artifacts import artifact_ref_from_file
from covalent_design.io.jsonl import write_jsonl


RECORDS_VALIDATOR = "covalent_design.data.build_record_index"


def build_record_index(processed_root: Path) -> ContractEnvelope[dict[str, object]]:
    """Build accepted, rejected, and conflict indexes from Task 9 output."""
    processed_root = processed_root.resolve()
    accepted_rows = _read_lines(processed_root / "accepted.jsonl")
    rejected_rows = _read_lines(processed_root / "rejected.jsonl")
    conflict_rows = _read_lines(processed_root / "conflicts.jsonl")
    input_sha256 = _digest_rows(accepted_rows, rejected_rows, conflict_rows)

    errors = _artifact_errors(accepted_rows, processed_root=processed_root)
    if errors:
        return ContractEnvelope(
            payload={},
            artifacts=(),
            receipt=ValidationReceipt(
                validator=RECORDS_VALIDATOR,
                contract_version=CONTRACT_VERSION,
                input_sha256=input_sha256,
                passed=False,
                errors=tuple(errors),
            ),
        )

    records = _accepted_records(accepted_rows, processed_root=processed_root)
    rejected_index = _rejected_index(rejected_rows)
    conflict_index = _conflict_index(conflict_rows)

    records_ref = write_jsonl(processed_root / "records.jsonl", records, role="record_index")
    rejected_ref = write_jsonl(
        processed_root / "rejected_index.jsonl",
        rejected_index,
        role="rejected_index",
    )
    conflict_ref = write_jsonl(
        processed_root / "conflict_index.jsonl",
        conflict_index,
        role="conflict_index",
    )

    manifest_path = processed_root / "artifact_manifest.json"
    manifest = build_artifact_manifest(tuple(records))
    manifest_path.write_text(
        json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False),
        encoding="utf-8",
    )
    manifest_ref = artifact_ref_from_file(
        manifest_path,
        role="artifact_manifest",
        root=processed_root,
        format="json",
    )

    return ContractEnvelope(
        payload={
            "record_count": len(records),
            "rejected_count": len(rejected_index),
            "conflict_count": len(conflict_index),
        },
        artifacts=(records_ref, rejected_ref, conflict_ref, manifest_ref),
        receipt=ValidationReceipt(
            validator=RECORDS_VALIDATOR,
            contract_version=CONTRACT_VERSION,
            input_sha256=input_sha256,
            passed=True,
        ),
    )


def _artifact_errors(
    accepted_rows: list[dict[str, object]],
    *,
    processed_root: Path,
) -> list[ContractErrorInfo]:
    errors: list[ContractErrorInfo] = []
    for row in accepted_rows:
        record_id = _record_id(row)
        if not record_id:
            errors.append(
                ContractErrorInfo(
                    code="RECORD_ID_MISSING",
                    owner="data",
                    message="Accepted record missing record_id",
                )
            )
            continue
        _, artifact_errors = discover_required_artifacts(record_id, processed_root=processed_root)
        errors.extend(artifact_errors)
    return errors


def _accepted_records(
    accepted_rows: list[dict[str, object]],
    *,
    processed_root: Path,
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for row in accepted_rows:
        record_id = _record_id(row)
        if not record_id:
            continue
        refs, _ = discover_required_artifacts(record_id, processed_root=processed_root)
        records.append(
            {
                "schema_version": SCHEMA_VERSION,
                "contract_version": CONTRACT_VERSION,
                "record_id": record_id,
                "core_labels": _core_labels(row),
                "lineage": _lineage(row),
                "metadata": _metadata(row),
                "artifacts": [artifact_ref_to_dict(ref) for ref in refs],
            }
        )
    return sorted(records, key=lambda record: str(record["record_id"]))


def _rejected_index(rejected_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for row in rejected_rows:
        rows.append(
            {
                "schema_version": SCHEMA_VERSION,
                "contract_version": CONTRACT_VERSION,
                "record_id": _record_id(row),
                "reason": row.get("reason", ""),
                "lineage": _lineage(row),
            }
        )
    return sorted(rows, key=lambda row: str(row["record_id"]))


def _conflict_index(conflict_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for row in conflict_rows:
        rows.append(
            {
                "schema_version": SCHEMA_VERSION,
                "contract_version": CONTRACT_VERSION,
                "conflict_group_id": str(row.get("conflict_group_id", "")),
                "anchor": row.get("anchor", {}),
                "conflicting_identities": row.get("conflicting_identities", []),
                "lineage": row.get("lineage", []),
                "reason": row.get("reason", ""),
            }
        )
    return sorted(rows, key=lambda row: str(row.get("conflict_group_id", "")))


def _read_lines(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    rows: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped:
            rows.append(json.loads(stripped))
    return rows


def _record_id(row: dict[str, object]) -> str:
    normalized = row.get("normalized", {})
    if isinstance(normalized, dict):
        return str(normalized.get("record_id", ""))
    return ""


def _core_labels(row: dict[str, object]) -> dict[str, object]:
    normalized = row.get("normalized", {})
    labels: dict[str, object] = {}
    if isinstance(normalized, dict):
        labels["pdb_id"] = normalized.get("pdb_id", "")
        labels["residue_reaction_family"] = normalized.get("residue_reaction_family", "")
        atom_mapping = normalized.get("atom_mapping", {})
        if isinstance(atom_mapping, dict):
            labels["target_atom_name"] = atom_mapping.get("target_atom_name", "")
            labels["target_atom_index"] = atom_mapping.get("target_atom_index", -1)
            labels["ligand_atom_name"] = atom_mapping.get("ligand_atom_name", "")
            labels["ligand_atom_index"] = atom_mapping.get("ligand_atom_index", -1)
            labels["ligand_atom_element"] = _ligand_atom_element(atom_mapping)
        labels["bond_type"] = normalized.get("bond_type", "")
        labels["warhead_type"] = normalized.get("warhead_type", "")
    return labels


def _ligand_atom_element(atom_mapping: dict[str, object]) -> str:
    explicit = atom_mapping.get("ligand_atom_element")
    if explicit:
        return str(explicit).strip().upper()

    atom_name = str(atom_mapping.get("ligand_atom_name", "")).strip()
    letters = []
    seen_letter = False
    for char in atom_name:
        if char.isalpha():
            letters.append(char)
            seen_letter = True
            continue
        if seen_letter:
            break
    return "".join(letters).upper()


def _metadata(row: dict[str, object]) -> dict[str, object]:
    normalized = row.get("normalized", {})
    if not isinstance(normalized, dict):
        return {}
    gate = row.get("gate_result", {})
    captured = {
        "pdb_id",
        "residue_reaction_family",
        "atom_mapping",
        "record_id",
        "source_lineage",
        "source_lineages",
        "bond_type",
        "warhead_type",
    }
    metadata = {key: value for key, value in normalized.items() if key not in captured}
    if isinstance(gate, dict):
        metadata["quality"] = {
            "quality_tier": gate.get("quality_tier", ""),
            "quality_flags": gate.get("flags", []),
            "quality_reasons": gate.get("reasons", []),
            "first_core_eligible": gate.get("first_core_eligible", False),
        }
    return metadata


def _lineage(row: dict[str, object]) -> list[object]:
    normalized = row.get("normalized", {})
    if not isinstance(normalized, dict):
        return []
    lineages = normalized.get("source_lineages")
    if isinstance(lineages, list) and lineages:
        return list(lineages)
    lineage = normalized.get("source_lineage")
    if isinstance(lineage, dict):
        return [lineage]
    return []


def _digest_rows(*row_groups: list[dict[str, object]]) -> str:
    payload = json.dumps(
        row_groups,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
