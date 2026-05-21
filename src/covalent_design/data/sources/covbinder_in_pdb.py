from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional, Sequence

from covalent_design.data.manifests import RawManifestFile, RawSourceManifest


MISSING_REQUIRED_FIELD = "INGEST_MISSING_REQUIRED_FIELD"
INVALID_VALUE = "INGEST_INVALID_VALUE"

REQUIRED_COLUMNS = (
    "pdb_id",
    "chain",
    "residue_number",
    "residue_name",
    "target_atom_name",
    "ligand_id",
    "ligand_chain",
    "ligand_residue",
    "ligand_attachment_atom",
    "bond_type",
    "reaction_family",
)


@dataclass(frozen=True)
class ParsedCovBinderRow:
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
class CovBinderRowFailure:
    source_database: str
    raw_file_path: str
    row_index: int
    reason: str
    message: str
    raw_line_preview: str


def parse_covbinder_records(
    path: Path,
    *,
    manifest: RawSourceManifest,
    file_entry: RawManifestFile,
) -> tuple[tuple[ParsedCovBinderRow, ...], tuple[CovBinderRowFailure, ...]]:
    records: list[ParsedCovBinderRow] = []
    failures: list[CovBinderRowFailure] = []

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
                        "Missing required CovBinder fields: " + ", ".join(missing),
                        row,
                    )
                )
                continue

            try:
                protein_residue_number = _parse_int(row, "residue_number")
                ligand_residue_number = _parse_int(row, "ligand_residue")
                resolution = _parse_optional_float(row, "resolution")
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
            lineage = {
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

            records.append(
                ParsedCovBinderRow(
                    source_database=manifest.source_database,
                    source_version=manifest.source_version,
                    source_record_id=source_record_id,
                    raw_manifest_file=manifest.manifest_path,
                    raw_file_path=raw_file_path,
                    raw_file_sha256=file_entry.sha256,
                    row_index=row_index,
                    lineage=lineage,
                    protein={
                        "pdb_id": _text(row, "pdb_id"),
                        "chain_id": _text(row, "chain"),
                        "residue_number": protein_residue_number,
                        "residue_name": _text(row, "residue_name"),
                        "atom_name": _text(row, "target_atom_name"),
                    },
                    ligand={
                        "ligand_id": _text(row, "ligand_id"),
                        "chain_id": _text(row, "ligand_chain"),
                        "residue_number": ligand_residue_number,
                        "attachment_atom": _text(row, "ligand_attachment_atom"),
                    },
                    linkage={
                        "bond_type": _text(row, "bond_type"),
                        "residue_reaction_family": _text(row, "reaction_family"),
                    },
                    metadata={
                        "resolution": resolution,
                    },
                )
            )

    return tuple(records), tuple(failures)


def _missing_required_fields(row: Mapping[str, Optional[str]], columns: Sequence[str]) -> list[str]:
    return [column for column in columns if not _text(row, column)]


def _text(row: Mapping[str, Optional[str]], column: str) -> str:
    value = row.get(column)
    if value is None:
        return ""
    return value.strip()


def _parse_int(row: Mapping[str, Optional[str]], column: str) -> int:
    value = _text(row, column)
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"Invalid integer for {column}: {value!r}") from exc


def _parse_optional_float(row: Mapping[str, Optional[str]], column: str) -> Optional[float]:
    value = _text(row, column)
    if not value:
        return None
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"Invalid float for {column}: {value!r}") from exc


def _failure(
    source_database: str,
    raw_file_path: str,
    row_index: int,
    reason: str,
    message: str,
    row: Mapping[str, Optional[str]],
) -> CovBinderRowFailure:
    return CovBinderRowFailure(
        source_database=source_database,
        raw_file_path=raw_file_path,
        row_index=row_index,
        reason=reason,
        message=message,
        raw_line_preview=str(dict(row))[:200],
    )
