from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional, Sequence

from covalent_design.data.manifests import RawManifestFile, RawSourceManifest


MISSING_REQUIRED_FIELD = "INGEST_MISSING_REQUIRED_FIELD"
INVALID_VALUE = "INGEST_INVALID_VALUE"

REQUIRED_COLUMNS = (
    "compound_id",
    "target_name",
    "uniprot_id",
    "residue",
    "residue_name",
    "atom_name",
    "attachment_atom",
    "warhead_class",
    "bond_type",
    "reaction_family",
)


@dataclass(frozen=True)
class ParsedCovalentInDBRow:
    source_database: str
    source_version: str
    source_record_id: str
    raw_manifest_file: str
    raw_file_path: str
    raw_file_sha256: str
    row_index: int
    lineage: Mapping[str, object]
    protein: Mapping[str, object]
    ligand: Mapping[str, object]
    linkage: Mapping[str, object]
    metadata: Mapping[str, object]


@dataclass(frozen=True)
class CovalentInDBRowFailure:
    source_database: str
    raw_file_path: str
    row_index: int
    reason: str
    message: str
    raw_line_preview: str


def parse_covalentin_db_records(
    path: Path,
    *,
    manifest: RawSourceManifest,
    file_entry: RawManifestFile,
) -> tuple[tuple[ParsedCovalentInDBRow, ...], tuple[CovalentInDBRowFailure, ...]]:
    records: list[ParsedCovalentInDBRow] = []
    failures: list[CovalentInDBRowFailure] = []

    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row_index, row in enumerate(reader, start=1):
            missing = _missing_required_fields(row, REQUIRED_COLUMNS)
            if missing:
                failures.append(
                    _failure(
                        manifest.source_database,
                        file_entry.path,
                        row_index,
                        MISSING_REQUIRED_FIELD,
                        "Missing required CovalentInDB P0 fields: " + ", ".join(missing),
                        row,
                    )
                )
                continue

            try:
                metadata = _metadata(row)
            except ValueError as exc:
                failures.append(
                    _failure(
                        manifest.source_database,
                        file_entry.path,
                        row_index,
                        INVALID_VALUE,
                        str(exc),
                        row,
                    )
                )
                continue

            raw_file_path = f"{manifest.source_database}/{file_entry.path}"
            source_record_id = f"{manifest.source_database}:{raw_file_path}:row:{row_index}"
            lineage = _lineage(manifest, file_entry, raw_file_path, source_record_id, row_index)

            records.append(
                ParsedCovalentInDBRow(
                    source_database=manifest.source_database,
                    source_version=manifest.source_version,
                    source_record_id=source_record_id,
                    raw_manifest_file=manifest.manifest_path,
                    raw_file_path=raw_file_path,
                    raw_file_sha256=file_entry.sha256,
                    row_index=row_index,
                    lineage=lineage,
                    protein={
                        "target_name": _text(row, "target_name"),
                        "uniprot_id": _text(row, "uniprot_id"),
                        "residue": _text(row, "residue"),
                        "residue_name": _text(row, "residue_name"),
                        "atom_name": _text(row, "atom_name"),
                    },
                    ligand={
                        "compound_id": _text(row, "compound_id"),
                        "attachment_atom": _text(row, "attachment_atom"),
                        "warhead_class": _text(row, "warhead_class"),
                    },
                    linkage={
                        "bond_type": _text(row, "bond_type"),
                        "residue_reaction_family": _text(row, "reaction_family"),
                    },
                    metadata=metadata,
                )
            )

    return tuple(records), tuple(failures)


def _metadata(row: Mapping[str, Optional[str]]) -> Mapping[str, object]:
    return {
        "pdb_id": _text(row, "pdb_id"),
        "chain": _text(row, "chain"),
        "resolution": _parse_optional_float(row, "resolution"),
        "ic50_nm": _parse_optional_float(row, "ic50_nm"),
        "ki_nm": _parse_optional_float(row, "ki_nm"),
        "assay_type": _text(row, "assay_type"),
        "reference": _text(row, "reference"),
        "doi": _text(row, "doi"),
        "year": _parse_optional_int(row, "year"),
        "p1_confidence": _text(row, "p1_confidence"),
        "p2_notes": _text(row, "p2_notes"),
    }


def _lineage(
    manifest: RawSourceManifest,
    file_entry: RawManifestFile,
    raw_file_path: str,
    source_record_id: str,
    row_index: int,
) -> Mapping[str, object]:
    return {
        "source_database": manifest.source_database,
        "source_version": manifest.source_version,
        "source_record_id": source_record_id,
        "raw_manifest_file": manifest.manifest_path,
        "raw_file_path": raw_file_path,
        "raw_file_sha256": file_entry.sha256,
        "row_index": row_index,
        "license": manifest.license,
        "access_notes": manifest.access_notes,
    }


def _missing_required_fields(row: Mapping[str, Optional[str]], columns: Sequence[str]) -> list[str]:
    return [column for column in columns if not _text(row, column)]


def _text(row: Mapping[str, Optional[str]], column: str) -> str:
    value = row.get(column)
    if value is None:
        return ""
    return value.strip()


def _parse_optional_float(row: Mapping[str, Optional[str]], column: str) -> Optional[float]:
    value = _text(row, column)
    if not value:
        return None
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"Invalid float for {column}: {value!r}") from exc


def _parse_optional_int(row: Mapping[str, Optional[str]], column: str) -> Optional[int]:
    value = _text(row, column)
    if not value:
        return None
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"Invalid integer for {column}: {value!r}") from exc


def _failure(
    source_database: str,
    raw_file_path: str,
    row_index: int,
    reason: str,
    message: str,
    row: Mapping[str, Optional[str]],
) -> CovalentInDBRowFailure:
    return CovalentInDBRowFailure(
        source_database=source_database,
        raw_file_path=raw_file_path,
        row_index=row_index,
        reason=reason,
        message=message,
        raw_line_preview=str(dict(row))[:200],
    )
