"""Normalize linkage records and route them through quality gates."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Mapping, Optional

from covalent_design.contracts.types import (
    CONTRACT_VERSION,
    ContractEnvelope,
    LigandAtomIdentity,
    ProteinAtomIdentity,
    Provenance,
    SourceIngestRecord,
    SourceRecordLineage,
    ValidationReceipt,
)
from covalent_design.data.conflicts import ConflictGroup
from covalent_design.data.identity import (
    MergedIdentityRecord,
    RejectedIdentityInput,
    build_record_id,
    canonical_identity_from_record,
    resolve_identities,
)
from covalent_design.data.quality import QualityGateResult, evaluate_quality_gates


NORMALIZE_VALIDATOR = "covalent_design.data.normalize_linkages"


@dataclass(frozen=True)
class AtomMapping:
    target_atom_index: int
    ligand_atom_index: int
    target_atom_name: str
    ligand_atom_name: str
    mapping_verified: bool


@dataclass(frozen=True)
class NormalizedLinkageRecord:
    pdb_id: str
    residue_reaction_family: str
    record_id: str
    source_lineage: SourceRecordLineage
    source_lineages: tuple[SourceRecordLineage, ...]
    atom_mapping: AtomMapping


@dataclass(frozen=True)
class AcceptedRecord:
    normalized: NormalizedLinkageRecord
    gate_result: QualityGateResult


@dataclass(frozen=True)
class RejectedRecord:
    normalized: NormalizedLinkageRecord
    gate_result: QualityGateResult
    reason: str


@dataclass(frozen=True)
class NormalizationPayload:
    counts: dict[str, int]
    accepted: tuple[AcceptedRecord, ...]
    rejected: tuple[RejectedRecord, ...]
    conflicts: tuple[ConflictGroup, ...] = ()
    rejected_identity_inputs: tuple[RejectedIdentityInput, ...] = ()


def normalize_linkages(
    records: tuple[SourceIngestRecord, ...],
) -> ContractEnvelope[NormalizationPayload]:
    """Normalize already-selected source records without identity reconciliation.

    This remains the small in-memory API used by unit tests and future callers
    that have already resolved duplicates/conflicts. Use
    ``normalize_with_identity_resolution`` at the pipeline seam before writing
    downstream indexes.
    """
    accepted: list[AcceptedRecord] = []
    rejected: list[RejectedRecord] = []

    for record in records:
        normalized = _build_normalized_record(record)
        _route_record(record, normalized, accepted, rejected)

    return _envelope(
        NormalizationPayload(
            counts=_counts(accepted, rejected, (), ()),
            accepted=tuple(accepted),
            rejected=tuple(rejected),
        )
    )


def normalize_with_identity_resolution(
    records: tuple[SourceIngestRecord, ...],
) -> ContractEnvelope[NormalizationPayload]:
    """Resolve canonical identities before normalization.

    Duplicate source records merge into one normalized output with combined
    lineage. Linkage conflicts stay in ``payload.conflicts`` and never enter
    accepted normalized records.
    """
    identity_result = resolve_identities(records)
    record_by_lineage = {_lineage_key(_source_lineage(record)): record for record in records}
    accepted: list[AcceptedRecord] = []
    rejected: list[RejectedRecord] = []

    for merged in identity_result.merged_records:
        representative = _representative_record(merged, record_by_lineage)
        if representative is None:
            continue
        normalized = _build_normalized_record(
            representative,
            record_id=merged.record_id,
            source_lineages=merged.lineage,
        )
        _route_record(representative, normalized, accepted, rejected)

    payload = NormalizationPayload(
        counts=_counts(
            accepted,
            rejected,
            identity_result.conflict_groups,
            identity_result.rejected_inputs,
        ),
        accepted=tuple(accepted),
        rejected=tuple(rejected),
        conflicts=identity_result.conflict_groups,
        rejected_identity_inputs=identity_result.rejected_inputs,
    )
    return _envelope(payload)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Normalize linkage records with identity resolution and quality gates."
    )
    parser.add_argument("--source", help="Optional source filter for --raw-root JSON fixtures.")
    parser.add_argument("--raw-root", type=Path, help="Directory containing JSON source-record fixtures.")
    parser.add_argument("--ingest-index", type=Path, help="JSON ingest index with a records array.")
    parser.add_argument("--interim-root", type=Path, help="Directory containing source_records.jsonl or ingest_index.json.")
    parser.add_argument("--out", type=Path, help="Optional path for a JSON summary.")
    parser.add_argument("--out-root", type=Path, help="Optional directory for accepted/rejected/conflict JSONL output.")
    args = parser.parse_args(argv)

    try:
        records = _load_cli_records(args)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    envelope = normalize_with_identity_resolution(records)
    summary = _summary(envelope, input_record_count=len(records))

    if args.out_root is not None:
        _write_outputs(args.out_root, envelope.payload)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")

    print(json.dumps(summary, sort_keys=True))
    return 0


def _route_record(
    record: SourceIngestRecord,
    normalized: NormalizedLinkageRecord,
    accepted: list[AcceptedRecord],
    rejected: list[RejectedRecord],
) -> None:
    gate_result = evaluate_quality_gates(
        protein=record.protein,
        linkage=record.linkage,
        metadata=record.metadata,
    )
    if gate_result.quality_tier in ("Q0", "Q1"):
        rejected.append(
            RejectedRecord(
                normalized=normalized,
                gate_result=gate_result,
                reason=gate_result.reasons[0] if gate_result.reasons else "UNKNOWN",
            )
        )
        return
    accepted.append(AcceptedRecord(normalized=normalized, gate_result=gate_result))


def _build_normalized_record(
    record: SourceIngestRecord,
    *,
    record_id: Optional[str] = None,
    source_lineages: Optional[tuple[SourceRecordLineage, ...]] = None,
) -> NormalizedLinkageRecord:
    if record_id is None:
        record_id = build_record_id(canonical_identity_from_record(record))
    lineage = _source_lineage(record)
    lineages = source_lineages if source_lineages is not None else (lineage,)
    return NormalizedLinkageRecord(
        pdb_id=str(record.protein.get("pdb_id") or record.metadata.get("pdb_id") or ""),
        residue_reaction_family=str(record.linkage.get("residue_reaction_family", "")),
        record_id=record_id,
        source_lineage=lineages[0] if lineages else lineage,
        source_lineages=tuple(lineages),
        atom_mapping=_atom_mapping(record.metadata.get("atom_mapping")),
    )


def _atom_mapping(value: object) -> AtomMapping:
    if isinstance(value, Mapping):
        return AtomMapping(
            target_atom_index=int(value.get("target_atom_index", -1)),
            ligand_atom_index=int(value.get("ligand_atom_index", -1)),
            target_atom_name=str(value.get("target_atom_name", "")),
            ligand_atom_name=str(value.get("ligand_atom_name", "")),
            mapping_verified=value.get("mapping_verified") is True,
        )
    return AtomMapping(
        target_atom_index=-1,
        ligand_atom_index=-1,
        target_atom_name="",
        ligand_atom_name="",
        mapping_verified=False,
    )


def _representative_record(
    merged: MergedIdentityRecord,
    record_by_lineage: Mapping[tuple[str, str, int], SourceIngestRecord],
) -> Optional[SourceIngestRecord]:
    for lineage in merged.lineage:
        record = record_by_lineage.get(_lineage_key(lineage))
        if record is not None:
            return record
    return None


def _source_lineage(record: SourceIngestRecord) -> SourceRecordLineage:
    if record.source_lineage is not None:
        return record.source_lineage
    return SourceRecordLineage(
        source_database=record.source_database,
        source_version=record.source_version,
        source_record_id=record.source_record_id,
        raw_manifest_file=record.raw_manifest_file,
        raw_file_path=record.raw_file_path,
        raw_file_sha256=record.raw_file_sha256,
        row_index=record.row_index,
    )


def _lineage_key(lineage: SourceRecordLineage) -> tuple[str, str, int]:
    return (lineage.source_database, lineage.source_record_id, lineage.row_index)


def _counts(
    accepted: Iterable[AcceptedRecord],
    rejected: Iterable[RejectedRecord],
    conflicts: Iterable[ConflictGroup],
    rejected_identity_inputs: Iterable[RejectedIdentityInput],
) -> dict[str, int]:
    accepted_tuple = tuple(accepted)
    rejected_tuple = tuple(rejected)
    conflict_tuple = tuple(conflicts)
    rejected_identity_tuple = tuple(rejected_identity_inputs)
    return {
        "accepted": len(accepted_tuple),
        "rejected": len(rejected_tuple),
        "conflicts": len(conflict_tuple),
        "rejected_identity_inputs": len(rejected_identity_tuple),
    }


def _envelope(payload: NormalizationPayload) -> ContractEnvelope[NormalizationPayload]:
    digest = hashlib.sha256(
        json.dumps(asdict(payload), sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()
    return ContractEnvelope(
        payload=payload,
        artifacts=(),
        receipt=ValidationReceipt(
            validator=NORMALIZE_VALIDATOR,
            contract_version=CONTRACT_VERSION,
            input_sha256=digest,
            ok=True,
        ),
        provenance=Provenance(),
    )


def _summary(
    envelope: ContractEnvelope[NormalizationPayload],
    *,
    input_record_count: int,
) -> dict[str, object]:
    payload = envelope.payload
    rejected_reason_counts = Counter(
        reason for record in payload.rejected for reason in record.gate_result.reasons
    )
    quality_flag_counts = Counter(
        flag for record in payload.accepted for flag in record.gate_result.flags
    )
    quality_tier_counts = Counter()
    for record in payload.accepted:
        quality_tier_counts[record.gate_result.quality_tier or "Q_clean"] += 1
    for record in payload.rejected:
        quality_tier_counts[record.gate_result.quality_tier] += 1
    return {
        "ok": envelope.receipt.ok,
        "validator": envelope.receipt.validator,
        "contract_version": envelope.receipt.contract_version,
        "input_record_count": input_record_count,
        "identity_merged_record_count": payload.counts["accepted"] + payload.counts["rejected"],
        "accepted_record_count": payload.counts["accepted"],
        "rejected_record_count": payload.counts["rejected"],
        "conflict_group_count": payload.counts["conflicts"],
        "rejected_identity_input_count": payload.counts["rejected_identity_inputs"],
        "quality_tier_counts": dict(sorted(quality_tier_counts.items())),
        "rejected_reason_counts": dict(sorted(rejected_reason_counts.items())),
        "quality_flag_counts": dict(sorted(quality_flag_counts.items())),
        "errors": [asdict(error) for error in envelope.receipt.errors],
        "warnings": [asdict(warning) for warning in envelope.receipt.warnings],
    }


def _load_cli_records(args: argparse.Namespace) -> tuple[SourceIngestRecord, ...]:
    if args.ingest_index is not None:
        return _load_ingest_index(args.ingest_index)
    if args.interim_root is not None:
        records_path = args.interim_root / "source_records.jsonl"
        if records_path.exists():
            return _load_records_jsonl(records_path)
        ingest_path = args.interim_root / "ingest_index.json"
        return _load_ingest_index(ingest_path)
    if args.raw_root is not None:
        records = _load_raw_root(args.raw_root, source=args.source)
        if not records:
            raise ValueError(f"No records found in {args.raw_root}")
        return records
    raise ValueError("Provide --interim-root, --ingest-index, or --raw-root.")


def _load_raw_root(root: Path, *, source: Optional[str]) -> tuple[SourceIngestRecord, ...]:
    if not root.is_dir():
        raise ValueError(f"Raw root does not exist: {root}")
    records: list[SourceIngestRecord] = []
    for path in sorted(root.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if source is not None and payload.get("source_database") != source:
            continue
        records.append(_record_from_payload(payload, path))
    return tuple(records)


def _load_records_jsonl(path: Path) -> tuple[SourceIngestRecord, ...]:
    records: list[SourceIngestRecord] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        records.append(_record_from_payload(payload, path, default_row_index=line_number))
    return tuple(records)


def _load_ingest_index(path: Path) -> tuple[SourceIngestRecord, ...]:
    if not path.is_file():
        raise ValueError(f"Ingest index not found: {path}")
    index = json.loads(path.read_text(encoding="utf-8"))
    return tuple(
        _record_from_payload(payload, path, default_row_index=index)
        for index, payload in enumerate(index.get("records", ()), start=1)
    )


def _record_from_payload(
    payload: Mapping[str, object],
    path: Path,
    *,
    default_row_index: int = 0,
) -> SourceIngestRecord:
    source_database = str(payload.get("source_database", ""))
    source_version = str(payload.get("source_version", ""))
    source_record_id = str(payload.get("source_record_id", ""))
    row_index = int(payload.get("row_index", default_row_index))
    quality = _mapping(payload.get("quality"))
    protein = _mapping(payload.get("protein"))
    ligand = _mapping(payload.get("ligand"))
    metadata = _mapping(payload.get("metadata"))
    target_raw = _mapping(payload.get("target_atom") or payload.get("target_atom_identity"))
    ligand_raw = _mapping(payload.get("ligand_atom") or payload.get("ligand_atom_identity"))
    linkage = dict(_mapping(payload.get("linkage")))

    lineage = SourceRecordLineage(
        source_database=source_database,
        source_version=source_version,
        source_record_id=source_record_id,
        raw_manifest_file=str(payload.get("raw_manifest_file", "manifest.json")),
        raw_file_path=str(payload.get("raw_file_path", path)),
        raw_file_sha256=str(payload.get("raw_file_sha256", "fixture-sha256")),
        row_index=row_index,
    )
    protein_payload = dict(protein)
    if "pdb_id" not in protein_payload:
        protein_payload["pdb_id"] = payload.get("pdb_id") or metadata.get("pdb_id", "")
    if "resolution_angstrom" not in protein_payload:
        protein_payload["resolution_angstrom"] = (
            quality.get("resolution_angstrom")
            if "resolution_angstrom" in quality
            else metadata.get("resolution")
        )
    ligand_payload = dict(ligand)
    if "ligand_id" not in ligand_payload:
        ligand_payload["ligand_id"] = ligand_raw.get("ligand_id", "")
    metadata_payload = dict(metadata)
    if "atom_mapping" not in metadata_payload:
        metadata_payload["atom_mapping"] = payload.get("atom_mapping")
    if "quality_flags" not in metadata_payload:
        metadata_payload["quality_flags"] = tuple(quality.get("flags", ()))

    return SourceIngestRecord(
        source_database=source_database,
        source_version=source_version,
        source_record_id=source_record_id,
        raw_manifest_file=lineage.raw_manifest_file,
        raw_file_path=lineage.raw_file_path,
        raw_file_sha256=lineage.raw_file_sha256,
        row_index=lineage.row_index,
        lineage=_mapping(payload.get("lineage")),
        protein=protein_payload,
        ligand=ligand_payload,
        linkage=linkage,
        metadata=metadata_payload,
        source_lineage=lineage,
        target_atom_identity=ProteinAtomIdentity(**target_raw) if target_raw else None,
        ligand_atom_identity=LigandAtomIdentity(**ligand_raw) if ligand_raw else None,
    )


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _write_outputs(out_root: Path, payload: NormalizationPayload) -> None:
    out_root.mkdir(parents=True, exist_ok=True)
    _write_jsonl(out_root / "accepted.jsonl", payload.accepted)
    _write_jsonl(out_root / "rejected.jsonl", payload.rejected)
    _write_jsonl(out_root / "conflicts.jsonl", payload.conflicts)
    _write_jsonl(out_root / "rejected_identity_inputs.jsonl", payload.rejected_identity_inputs)


def _write_jsonl(path: Path, rows: Iterable[object]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(asdict(row), sort_keys=True, default=str))
            handle.write("\n")


if __name__ == "__main__":
    raise SystemExit(main())
