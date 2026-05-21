from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Optional

from covalent_design.contracts import (
    CONTRACT_VERSION,
    ArtifactRef,
    ContractEnvelope,
    ContractErrorInfo,
    LigandAtomIdentity,
    ProteinAtomIdentity,
    Provenance,
    SourceIngestRecord,
    SourceRecordLineage,
    ValidationReceipt,
    exit_code_for_error,
)
from covalent_design.data.manifests import RawManifestFile, RawSourceManifest, validate_raw_manifests
from covalent_design.data.sources.covbinder_in_pdb import (
    parse_covbinder_records,
)
from covalent_design.data.sources.covalentin_db import parse_covalentin_db_records
from covalent_design.data.sources.covpdb import parse_covpdb_records


INGEST_VALIDATOR = "covalent_design.data.ingest_source"
SUPPORTED_SOURCES = ("covbinder_in_pdb", "covpdb", "covalentin_db")


@dataclass(frozen=True)
class SourceIngestFailure:
    source_database: str
    raw_file_path: str
    row_index: int
    reason: str
    message: str
    raw_line_preview: str


@dataclass(frozen=True)
class SourceIngestIndex:
    """Single-source raw ingestion summary.

    complete_for_v1 mirrors the staged raw manifest for this one source. It is
    not the ETL release gate, which is decided later by the all-source quality
    report after normalization, conflicts, records, candidates, and visual
    gates reconcile.
    """

    source_database: str
    source_version: str
    complete_for_v1: bool
    raw_root: str
    manifest_path: str
    raw_record_count: int
    record_count: int
    failure_count: int
    failure_reason_counts: Mapping[str, int]
    records: tuple[SourceIngestRecord, ...]
    failures: tuple[SourceIngestFailure, ...]


def ingest_source(source: str, raw_root: Path, out: Optional[Path] = None) -> ContractEnvelope[SourceIngestIndex]:
    del out  # Task 5 defines the ingestion contract; downstream artifact writing starts later.

    if source not in SUPPORTED_SOURCES:
        index = _empty_index(source, raw_root)
        return _envelope(
            index,
            artifacts=(),
            errors=(
                ContractErrorInfo(
                    code="SOURCE_UNSUPPORTED",
                    owner="data",
                    message=f"Unsupported source: {source}",
                    location=source,
                ),
            ),
        )

    manifest_envelope = validate_raw_manifests(raw_root)
    if not manifest_envelope.receipt.passed:
        index = _empty_index(source, raw_root)
        return _envelope(index, artifacts=manifest_envelope.artifacts, errors=manifest_envelope.receipt.errors)

    source_manifest = _find_source_manifest(manifest_envelope.payload.manifests, source)
    if source_manifest is None:
        index = _empty_index(source, raw_root)
        return _envelope(
            index,
            artifacts=manifest_envelope.artifacts,
            errors=(
                ContractErrorInfo(
                    code="SOURCE_NOT_FOUND",
                    owner="data",
                    message=f"Source manifest not found: {source}",
                    location=str(raw_root),
                ),
            ),
        )

    records: list[SourceIngestRecord] = []
    failures: list[SourceIngestFailure] = []
    raw_root = raw_root.resolve()

    record_files = tuple(file_entry for file_entry in source_manifest.files if file_entry.role == "records")
    if not record_files:
        index = _empty_index(source, raw_root, source_manifest=source_manifest)
        return _envelope(
            index,
            artifacts=manifest_envelope.artifacts,
            errors=(
                ContractErrorInfo(
                    code="SOURCE_RECORD_FILE_NOT_DECLARED",
                    owner="data",
                    message=f"No records file declared for source: {source}",
                    location=source_manifest.manifest_path,
                ),
            ),
        )

    for file_entry in record_files:
        path = raw_root / source / file_entry.path
        parsed_records, parsed_failures = _parse_source_records(source, path, source_manifest, file_entry)
        records.extend(_to_ingest_record(row) for row in parsed_records)
        failures.extend(_to_ingest_failure(row) for row in parsed_failures)

    reason_counts = Counter(failure.reason for failure in failures)
    index = SourceIngestIndex(
        source_database=source_manifest.source_database,
        source_version=source_manifest.source_version,
        complete_for_v1=source_manifest.complete_for_v1,
        raw_root=str(raw_root),
        manifest_path=source_manifest.manifest_path,
        raw_record_count=len(records) + len(failures),
        record_count=len(records),
        failure_count=len(failures),
        failure_reason_counts=dict(sorted(reason_counts.items())),
        records=tuple(records),
        failures=tuple(failures),
    )
    return _envelope(index, artifacts=manifest_envelope.artifacts, errors=())


def _parse_source_records(
    source: str,
    path: Path,
    source_manifest: RawSourceManifest,
    file_entry: RawManifestFile,
) -> tuple[tuple[Any, ...], tuple[Any, ...]]:
    if source == "covbinder_in_pdb":
        return parse_covbinder_records(path, manifest=source_manifest, file_entry=file_entry)
    if source == "covpdb":
        return parse_covpdb_records(path, manifest=source_manifest, file_entry=file_entry)
    if source == "covalentin_db":
        return parse_covalentin_db_records(path, manifest=source_manifest, file_entry=file_entry)
    raise AssertionError(f"Unsupported source dispatched: {source}")


def _find_source_manifest(
    manifests: tuple[RawSourceManifest, ...],
    source: str,
) -> Optional[RawSourceManifest]:
    for manifest in manifests:
        if manifest.source_database == source:
            return manifest
    return None


def _to_ingest_record(row: Any) -> SourceIngestRecord:
    source_lineage = SourceRecordLineage(
        source_database=row.source_database,
        source_version=row.source_version,
        source_record_id=row.source_record_id,
        raw_manifest_file=row.raw_manifest_file,
        raw_file_path=row.raw_file_path,
        raw_file_sha256=row.raw_file_sha256,
        row_index=row.row_index,
    )
    return SourceIngestRecord(
        source_database=row.source_database,
        source_version=row.source_version,
        source_record_id=row.source_record_id,
        raw_manifest_file=row.raw_manifest_file,
        raw_file_path=row.raw_file_path,
        raw_file_sha256=row.raw_file_sha256,
        row_index=row.row_index,
        lineage=row.lineage,
        protein=row.protein,
        ligand=row.ligand,
        linkage=row.linkage,
        metadata=row.metadata,
        source_lineage=source_lineage,
        target_atom_identity=_target_atom_identity(row.protein, row.metadata),
        ligand_atom_identity=_ligand_atom_identity(row.ligand),
    )


def _to_ingest_failure(row: Any) -> SourceIngestFailure:
    return SourceIngestFailure(
        source_database=row.source_database,
        raw_file_path=row.raw_file_path,
        row_index=row.row_index,
        reason=row.reason,
        message=row.message,
        raw_line_preview=row.raw_line_preview,
    )


def _empty_index(
    source: str,
    raw_root: Path,
    *,
    source_manifest: Optional[RawSourceManifest] = None,
) -> SourceIngestIndex:
    return SourceIngestIndex(
        source_database=source,
        source_version=source_manifest.source_version if source_manifest is not None else "",
        complete_for_v1=source_manifest.complete_for_v1 if source_manifest is not None else False,
        raw_root=str(raw_root),
        manifest_path=source_manifest.manifest_path if source_manifest is not None else "",
        raw_record_count=0,
        record_count=0,
        failure_count=0,
        failure_reason_counts={},
        records=(),
        failures=(),
    )


def _envelope(
    index: SourceIngestIndex,
    *,
    artifacts: tuple[ArtifactRef, ...],
    errors: tuple[ContractErrorInfo, ...],
) -> ContractEnvelope[SourceIngestIndex]:
    return ContractEnvelope(
        payload=index,
        artifacts=artifacts,
        receipt=ValidationReceipt(
            validator=INGEST_VALIDATOR,
            contract_version=CONTRACT_VERSION,
            input_sha256=_index_hash(index),
            ok=not errors,
            errors=errors,
        ),
        provenance=Provenance(inputs={artifact.role: artifact for artifact in artifacts}),
    )


def _index_hash(index: SourceIngestIndex) -> str:
    payload = json.dumps(asdict(index), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _target_atom_identity(protein: Mapping[str, object], metadata: Mapping[str, object]) -> ProteinAtomIdentity:
    return ProteinAtomIdentity(
        structure_model=_optional_int(protein.get("structure_model") or metadata.get("structure_model")),
        chain_id=_optional_str(protein.get("chain_id") or metadata.get("chain")),
        asym_id=_optional_str(protein.get("asym_id")),
        residue_name=_optional_str(protein.get("residue_name") or protein.get("residue")) or "",
        residue_number=_optional_int(protein.get("residue_number")),
        insertion_code=_optional_str(protein.get("insertion_code")),
        altloc=_optional_str(protein.get("altloc")),
        atom_name=_optional_str(protein.get("atom_name")) or "",
        atom_serial=_optional_int(protein.get("atom_serial")),
    )


def _ligand_atom_identity(ligand: Mapping[str, object]) -> LigandAtomIdentity:
    return LigandAtomIdentity(
        ligand_id=_optional_str(ligand.get("ligand_id") or ligand.get("compound_id")) or "",
        chain_id=_optional_str(ligand.get("chain_id")),
        asym_id=_optional_str(ligand.get("asym_id")),
        residue_number=_optional_int(ligand.get("residue_number")),
        atom_name=_optional_str(ligand.get("attachment_atom") or ligand.get("atom_name")) or "",
        atom_index=_optional_int(ligand.get("atom_index")),
        altloc=_optional_str(ligand.get("altloc")),
    )


def _optional_str(value: object) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_int(value: object) -> Optional[int]:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest a staged covalent data source.")
    parser.add_argument("--source", required=True)
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)

    envelope = ingest_source(args.source, args.raw_root, out=args.out)
    print(json.dumps(_summary(envelope), indent=2, sort_keys=True))
    if envelope.receipt.ok:
        return 0
    return exit_code_for_error(envelope.receipt.errors[0])


def _summary(envelope: ContractEnvelope[SourceIngestIndex]) -> dict[str, object]:
    payload = envelope.payload
    return {
        "ok": envelope.receipt.ok,
        "validator": envelope.receipt.validator,
        "contract_version": envelope.receipt.contract_version,
        "source": payload.source_database,
        "source_database": payload.source_database,
        "source_version": payload.source_version,
        "complete_for_v1": payload.complete_for_v1,
        "complete_for_v1_scope": "single_source_raw_manifest",
        "raw_record_count": payload.raw_record_count,
        "record_count": payload.record_count,
        "failure_count": payload.failure_count,
        "failure_counts": dict(payload.failure_reason_counts),
        "failure_reason_counts": dict(payload.failure_reason_counts),
        "errors": [asdict(error) for error in envelope.receipt.errors],
        "warnings": [asdict(warning) for warning in envelope.receipt.warnings],
    }


if __name__ == "__main__":
    raise SystemExit(main())
