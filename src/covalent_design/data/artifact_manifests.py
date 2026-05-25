"""Artifact manifest helpers for Task 10 record indexes and Task 13 finalization."""

from __future__ import annotations

import json
from pathlib import Path

from covalent_design.contracts.errors import ContractErrorInfo
from covalent_design.contracts.types import (
    CONTRACT_VERSION,
    SCHEMA_VERSION,
    ArtifactRef,
    ContractEnvelope,
    ValidationReceipt,
)
from covalent_design.io.artifacts import (
    artifact_ref_from_file,
    sha256_file,
    validate_artifact_ref,
)
from covalent_design.io.jsonl import read_jsonl, write_jsonl


FINALIZE_VALIDATOR = "covalent_design.data.finalize_record_manifests"

REQUIRED_ARTIFACT_ROLES = (
    "protein_atom_table",
    "ligand_atom_table",
    "ligand_bond_table",
    "coordinates",
)


def artifact_ref_to_dict(ref: ArtifactRef) -> dict[str, object]:
    return {
        "uri": ref.uri,
        "sha256": ref.sha256,
        "format": ref.format,
        "schema_version": ref.schema_version,
        "bytes": ref.bytes,
        "role": ref.role,
    }


def discover_required_artifacts(
    record_id: str,
    *,
    processed_root: Path,
) -> tuple[tuple[ArtifactRef, ...], tuple[ContractErrorInfo, ...]]:
    """Return required non-edge artifacts for one accepted record."""
    record_dir = processed_root / "artifacts" / record_id
    refs: list[ArtifactRef] = []
    errors: list[ContractErrorInfo] = []
    for role in REQUIRED_ARTIFACT_ROLES:
        candidates = sorted(record_dir.glob(f"{role}.*"))
        if not candidates:
            errors.append(
                ContractErrorInfo(
                    code="ARTIFACT_MISSING_REQUIRED",
                    owner="data",
                    message=f"Record {record_id}: missing required artifact role '{role}'",
                    location=f"artifacts/{record_id}/{role}.*",
                )
            )
            continue
        refs.append(artifact_ref_from_file(candidates[0], role=role, root=processed_root))
    return tuple(sorted(refs, key=lambda ref: ref.role)), tuple(errors)


def build_artifact_manifest(
    records: tuple[dict[str, object], ...],
) -> dict[str, list[dict[str, object]]]:
    """Build the deterministic Task 10 manifest shape."""
    manifest: dict[str, list[dict[str, object]]] = {}
    for record in sorted(records, key=lambda row: str(row["record_id"])):
        artifacts = record.get("artifacts", [])
        if not isinstance(artifacts, list):
            artifacts = []
        manifest[str(record["record_id"])] = sorted(
            (dict(ref) for ref in artifacts if isinstance(ref, dict)),
            key=lambda ref: str(ref.get("role", "")),
        )
    return manifest


def finalize_record_manifests(
    records_path: Path,
) -> ContractEnvelope[dict[str, object]]:
    """Append edge-candidate artifact refs to every accepted record and update the manifest.

    Public API: ``finalize_record_manifests(records_path: Path) -> ContractEnvelope[dict[str, object]]``.
    """
    records_path = records_path.resolve()
    root = records_path.parent
    input_sha256 = sha256_file(records_path)

    errors: list[ContractErrorInfo] = []

    # -- read records --
    try:
        raw_records = list(read_jsonl(records_path, require_versions=False))
    except (OSError, ValueError) as exc:
        errors.append(
            ContractErrorInfo(
                code="RECORDS_UNREADABLE",
                owner="data",
                message=str(exc),
                location=str(records_path),
            )
        )
        return _finalize_envelope(0, 0, input_sha256, errors)

    record_ids = {str(r["record_id"]) for r in raw_records}

    # -- read artifact manifest --
    manifest_path = root / "artifact_manifest.json"
    try:
        manifest: dict[str, object] = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(
            ContractErrorInfo(
                code="ARTIFACT_MANIFEST_UNREADABLE",
                owner="data",
                message=str(exc),
                location=str(manifest_path),
            )
        )
        return _finalize_envelope(len(raw_records), 0, input_sha256, errors)

    # -- detect obsolete unlinked manifest entries --
    manifest_ids = set(manifest.keys())
    unlinked = manifest_ids - record_ids
    for uid in sorted(unlinked):
        entry = manifest.get(uid)
        if _is_explicitly_obsolete_or_rejected(entry):
            continue
        errors.append(
            ContractErrorInfo(
                code="ARTIFACT_MANIFEST_OBSOLETE_UNLINKED",
                owner="data",
                message=f"Manifest entry for {uid} is not linked to any accepted record",
                location=str(manifest_path),
                details={"unlinked_record_id": uid},
            )
        )

    # -- process each accepted record --
    records = [dict(r) for r in raw_records]
    edge_candidate_count = 0

    for record in records:
        rid = str(record["record_id"])
        artifacts: list[dict[str, object]] = [
            dict(a) for a in record.get("artifacts", []) if isinstance(a, dict)
        ]

        # -- reject pre-existing edge_candidate ref --
        if any(a.get("role") == "edge_candidates" for a in artifacts):
            errors.append(
                ContractErrorInfo(
                    code="EDGE_CANDIDATE_ARTIFACT_DUPLICATE",
                    owner="data",
                    message=f"Record {rid}: edge_candidates artifact ref already present",
                    location=rid,
                )
            )
            continue

        manifest_entries: list[dict[str, object]] = [
            dict(e) for e in manifest.get(rid, []) if isinstance(e, dict)
        ]
        if any(e.get("role") == "edge_candidates" for e in manifest_entries):
            errors.append(
                ContractErrorInfo(
                    code="EDGE_CANDIDATE_ARTIFACT_DUPLICATE",
                    owner="data",
                    message=f"Record {rid}: edge_candidates artifact ref already present in manifest",
                    location=rid,
                )
            )
            continue

        # -- discover edge-candidate artifact --
        edge_path = root / "artifacts" / rid / "edge_candidates.json"
        if not edge_path.exists():
            errors.append(
                ContractErrorInfo(
                    code="EDGE_CANDIDATE_ARTIFACT_MISSING",
                    owner="data",
                    message=f"Record {rid}: edge_candidates.json not found",
                    location=rid,
                )
            )
            continue

        # -- validate embedded artifact_refs inside edge_candidates.json --
        try:
            edge_data = json.loads(edge_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(
                ContractErrorInfo(
                    code="EDGE_CANDIDATE_UNREADABLE",
                    owner="data",
                    message=f"Record {rid}: {exc}",
                    location=rid,
                )
            )
            continue

        if edge_data.get("record_id") != rid:
            errors.append(
                ContractErrorInfo(
                    code="EDGE_CANDIDATE_RECORD_ID_MISMATCH",
                    owner="data",
                    message=f"Record {rid}: edge_candidates.json record_id mismatch",
                    location=rid,
                )
            )
            continue

        if edge_data.get("role") != "edge_candidates":
            errors.append(
                ContractErrorInfo(
                    code="EDGE_CANDIDATE_ROLE_INVALID",
                    owner="data",
                    message=f"Record {rid}: edge_candidates.json role is not edge_candidates",
                    location=rid,
                )
            )
            continue

        for embedded in edge_data.get("artifact_refs", []):
            art_ref = ArtifactRef(
                uri=str(embedded["uri"]),
                sha256=str(embedded["sha256"]),
                format=str(embedded.get("format", "json")),
                schema_version=str(embedded.get("schema_version", SCHEMA_VERSION)),
                bytes=int(embedded.get("bytes", 0)),
                role=str(embedded.get("role", "")),
            )
            receipt = validate_artifact_ref(art_ref, root=root)
            if not receipt.ok:
                errors.extend(receipt.errors)

        # -- build ref for edge_candidates.json --
        edge_ref = artifact_ref_from_file(edge_path, role="edge_candidates", root=root)
        edge_ref_dict = artifact_ref_to_dict(edge_ref)

        # -- append edge_candidate ref to record artifacts --
        artifacts.append(edge_ref_dict)
        artifacts.sort(key=lambda a: str(a.get("role", "")))
        record["artifacts"] = artifacts

        # -- update manifest --
        manifest_entries.append(edge_ref_dict)
        manifest_entries.sort(key=lambda e: str(e.get("role", "")))
        manifest[rid] = manifest_entries

        edge_candidate_count += 1

    # -- return early on errors without modifying files --
    if errors:
        return _finalize_envelope(len(records), edge_candidate_count, input_sha256, errors)

    # -- write updated records.jsonl --
    records.sort(key=lambda r: str(r["record_id"]))
    write_jsonl(records_path, records, role="record_index")

    # -- write updated artifact_manifest.json --
    sorted_manifest = dict(sorted(manifest.items(), key=lambda x: x[0]))
    manifest_path.write_text(
        json.dumps(sorted_manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False),
        encoding="utf-8",
    )

    return _finalize_envelope(len(records), edge_candidate_count, input_sha256, errors)


def _finalize_envelope(
    record_count: int,
    edge_candidate_count: int,
    input_sha256: str,
    errors: list[ContractErrorInfo],
) -> ContractEnvelope[dict[str, object]]:
    passed = len(errors) == 0
    return ContractEnvelope(
        payload={
            "record_count": record_count,
            "edge_candidate_count": edge_candidate_count,
        },
        artifacts=(),
        receipt=ValidationReceipt(
            validator=FINALIZE_VALIDATOR,
            contract_version=CONTRACT_VERSION,
            input_sha256=input_sha256,
            ok=passed,
            errors=tuple(errors),
        ),
    )


def _is_explicitly_obsolete_or_rejected(entry: object) -> bool:
    if isinstance(entry, dict):
        return entry.get("obsolete") is True or entry.get("status") == "rejected"
    if isinstance(entry, list):
        return any(_is_explicitly_obsolete_or_rejected(item) for item in entry)
    return False
