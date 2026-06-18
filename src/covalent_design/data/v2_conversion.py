"""Task 42: V2 data conversion — convert Task 41 staging evidence to SourceIngestRecord records.

Converts checked-in, checksum-verified manual staged source data into
v1-compatible ``SourceIngestRecord`` records, preserving provenance and
license audit references for downstream tasks (43+).
"""

from __future__ import annotations

import csv
import hashlib
import re
from pathlib import Path
from typing import Mapping, Optional

from covalent_design.contracts.errors import ContractErrorInfo
from covalent_design.contracts.types import (
    ContractEnvelope,
    LigandAtomIdentity,
    ProteinAtomIdentity,
    Provenance,
    SourceIngestRecord,
    SourceRecordLineage,
    ValidationReceipt,
)
from covalent_design.data.v2_intake import (
    STATUS_CHECKSUM_VERIFIED,
    STATUS_PENDING_DOWNLOAD,
    VALIDATOR_NAME as V2_STAGING_VALIDATOR,
    V2StagingSummary,
    serialize_v2_staging_summary,
    stage_source_manifest,
)
from covalent_design.data.v2_manifests import (
    CONTRACT_VERSION as V2_CONTRACT_VERSION,
)

VALIDATOR_NAME = "covalent_design.data.v2_convert_staged_source"

# Task 42 supports only covalentin_db parser target.
_SUPPORTED_PARSER_TARGETS = frozenset({"covalentin_db"})

_V2_REQUIRED_COLUMNS = (
    "pdb_id",
    "uniprot_id",
    "residue",
    "residue_number",
    "ligand",
    "ligand_name",
    "bond_type",
    "warhead_type",
)

_RESIDUE_RE = re.compile(r"^([A-Za-z]+)(\d+)$")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def convert_staged_source(
    staging_envelope: ContractEnvelope[V2StagingSummary],
    *,
    reverify_checksum: bool = True,
) -> ContractEnvelope[tuple[SourceIngestRecord, ...]]:
    """Convert Task 41 staging evidence to SourceIngestRecord records.

    Only ``status == checksum_verified`` (manual local file) is convertible.
    ``pending_download`` returns a structured failure — no placeholder records.
    """
    errors: list[ContractErrorInfo] = []

    if not staging_envelope.receipt.ok:
        errors.append(
            _error(
                "V2_CONVERSION_STAGING_FAILED",
                "Staging envelope receipt not ok; cannot convert failed staging",
                details={
                    "staging_errors": [e.code for e in staging_envelope.receipt.errors]
                },
            )
        )
        return _fail_envelope(tuple(errors))

    if staging_envelope.receipt.validator != V2_STAGING_VALIDATOR:
        errors.append(
            _error(
                "V2_CONVERSION_INVALID_STAGING_EVIDENCE",
                "Conversion requires a Task 41 stage_source_manifest envelope",
                details={
                    "expected_validator": V2_STAGING_VALIDATOR,
                    "actual_validator": staging_envelope.receipt.validator,
                },
            )
        )
        return _fail_envelope(tuple(errors))

    summary = staging_envelope.payload
    if summary is None:
        errors.append(
            _error(
                "V2_CONVERSION_PAYLOAD_MISSING",
                "Staging envelope payload is None",
            )
        )
        return _fail_envelope(tuple(errors))

    input_sha256 = hashlib.sha256(
        serialize_v2_staging_summary(summary).encode("utf-8")
    ).hexdigest()

    if summary.status == STATUS_PENDING_DOWNLOAD:
        errors.append(
            _error(
                "V2_CONVERSION_PENDING_DOWNLOAD",
                "Source is pending download; not convertible in Task 42. "
                "Download the source first, then re-stage with manual intake mode.",
                details={"status": summary.status},
            )
        )
        return _fail_envelope(tuple(errors), input_sha256=input_sha256)

    if summary.status != STATUS_CHECKSUM_VERIFIED:
        errors.append(
            _error(
                "V2_CONVERSION_UNEXPECTED_STATUS",
                f"Unexpected staging status: {summary.status!r}",
                details={
                    "status": summary.status,
                    "expected": STATUS_CHECKSUM_VERIFIED,
                },
            )
        )
        return _fail_envelope(tuple(errors), input_sha256=input_sha256)

    if not summary.manual_path:
        errors.append(
            _error(
                "V2_CONVERSION_MANUAL_PATH_MISSING",
                "No manual_path in staging summary; cannot locate source data file",
            )
        )
        return _fail_envelope(tuple(errors), input_sha256=input_sha256)

    manual_path = Path(summary.manual_path)

    if not manual_path.is_file():
        errors.append(
            _error(
                "V2_CONVERSION_FILE_NOT_FOUND",
                f"Source data file not found: {manual_path}",
                location=str(manual_path),
            )
        )
        return _fail_envelope(tuple(errors), input_sha256=input_sha256)

    parser_target = summary.parser_target or ""
    if parser_target not in _SUPPORTED_PARSER_TARGETS:
        errors.append(
            _error(
                "V2_CONVERSION_UNSUPPORTED_PARSER",
                f"Parser target {parser_target!r} is not supported in Task 42",
                details={
                    "parser_target": parser_target,
                    "supported": sorted(_SUPPORTED_PARSER_TARGETS),
                },
            )
        )
        return _fail_envelope(tuple(errors), input_sha256=input_sha256)

    if reverify_checksum and summary.checksum:
        actual_sha256 = hashlib.sha256(manual_path.read_bytes()).hexdigest()
        if actual_sha256 != summary.checksum:
            errors.append(
                _error(
                    "V2_CONVERSION_CHECKSUM_MISMATCH",
                    f"Checksum reverification failed: "
                    f"expected {summary.checksum}, computed {actual_sha256}",
                    location=str(manual_path),
                    details={
                        "expected": summary.checksum,
                        "actual": actual_sha256,
                    },
                )
            )
            return _fail_envelope(tuple(errors), input_sha256=input_sha256)

    records, parse_errors = _parse_v2_source(
        path=manual_path,
        source_name=summary.source_name,
        checksum=summary.checksum or "",
        source_url=summary.source_url,
        license_audit_ref=summary.license_audit_ref,
    )

    all_errors = tuple(errors) + parse_errors
    return _result_envelope(records, all_errors, input_sha256)


def convert_staged_manifest(
    manifest_path: Path,
    *,
    reverify_checksum: bool = True,
) -> ContractEnvelope[tuple[SourceIngestRecord, ...]]:
    """Convenience: stage a manifest, then convert the resulting staging evidence."""
    staging_envelope = stage_source_manifest(manifest_path)
    if not staging_envelope.receipt.ok:
        return _fail_envelope(
            staging_envelope.receipt.errors,
            input_sha256=staging_envelope.receipt.input_sha256,
        )
    return convert_staged_source(staging_envelope, reverify_checksum=reverify_checksum)


# ---------------------------------------------------------------------------
# V2 TSV parser
# ---------------------------------------------------------------------------


def _parse_v2_source(
    *,
    path: Path,
    source_name: str,
    checksum: str,
    source_url: Optional[str],
    license_audit_ref: Optional[str],
) -> tuple[list[SourceIngestRecord], tuple[ContractErrorInfo, ...]]:
    """Parse a v2-format TSV source file into SourceIngestRecord objects."""
    records: list[SourceIngestRecord] = []
    errors: list[ContractErrorInfo] = []

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        error = _error(
            "V2_CONVERSION_FILE_UNREADABLE",
            f"Unable to read source file: {exc}",
            location=str(path),
        )
        return [], (error,)

    if not text.strip():
        return [], ()

    reader = csv.DictReader(text.splitlines(), delimiter="\t")
    if reader.fieldnames is None:
        return [], ()

    missing_columns = [
        col for col in _V2_REQUIRED_COLUMNS if col not in reader.fieldnames
    ]
    if missing_columns:
        error = _error(
            "V2_CONVERSION_MISSING_COLUMNS",
            f"Missing required columns: {', '.join(missing_columns)}",
            location=str(path),
            details={
                "missing": missing_columns,
                "present": list(reader.fieldnames),
            },
        )
        return [], (error,)

    raw_manifest_file = str(path.parent / "manifest.json")
    raw_file_path = str(path)

    for row_index, row in enumerate(reader, start=1):
        missing = [
            col for col in _V2_REQUIRED_COLUMNS if not _text(row, col)
        ]
        if missing:
            errors.append(
                _error(
                    "V2_CONVERSION_ROW_PARSE_ERROR",
                    f"Row {row_index}: missing required fields: "
                    f"{', '.join(missing)}",
                    location=f"{path}:row:{row_index}",
                    details={
                        "row_index": row_index,
                        "missing_fields": missing,
                    },
                )
            )
            continue

        try:
            residue_name, _residue_num = _parse_residue(_text(row, "residue"))
        except ValueError:
            errors.append(
                _error(
                    "V2_CONVERSION_ROW_PARSE_ERROR",
                    f"Row {row_index}: unable to parse residue field: "
                    f"{_text(row, 'residue')!r}",
                    location=f"{path}:row:{row_index}",
                    details={
                        "row_index": row_index,
                        "residue": _text(row, "residue"),
                    },
                )
            )
            continue

        source_record_id = f"{source_name}:{raw_file_path}:row:{row_index}"

        lineage: dict[str, object] = {
            "source_database": source_name,
            "source_version": "v2",
            "source_record_id": source_record_id,
            "raw_manifest_file": raw_manifest_file,
            "raw_file_path": raw_file_path,
            "raw_file_sha256": checksum,
            "row_index": row_index,
        }
        if license_audit_ref is not None:
            lineage["license_audit_ref"] = license_audit_ref
        if source_url is not None:
            lineage["source_url"] = source_url

        try:
            residue_number = int(_text(row, "residue_number"))
        except ValueError:
            errors.append(
                _error(
                    "V2_CONVERSION_ROW_PARSE_ERROR",
                    f"Row {row_index}: residue_number must be an integer: "
                    f"{_text(row, 'residue_number')!r}",
                    location=f"{path}:row:{row_index}",
                    details={
                        "row_index": row_index,
                        "residue_number": _text(row, "residue_number"),
                    },
                )
            )
            continue

        pdb_id = _text(row, "pdb_id")
        uniprot_id = _text(row, "uniprot_id")
        residue_text = _text(row, "residue")
        ligand_id = _text(row, "ligand")
        ligand_name = _text(row, "ligand_name")
        bond_type = _text(row, "bond_type")
        warhead_type = _text(row, "warhead_type")

        protein: dict[str, object] = {
            "pdb_id": pdb_id,
            "uniprot_id": uniprot_id,
            "chain_id": "A",
            "residue": residue_text,
            "residue_name": residue_name,
            "residue_number": residue_number,
            "atom_name": "SG",
        }

        ligand: dict[str, object] = {
            "ligand_id": ligand_id,
            "compound_id": ligand_id,
            "ligand_name": ligand_name,
            "attachment_atom": "C1",
            "warhead_type": warhead_type,
        }

        linkage: dict[str, object] = {
            "bond_type": bond_type,
            "residue_reaction_family": f"{residue_name}_{warhead_type}".lower(),
        }

        metadata: dict[str, object] = {"pdb_id": pdb_id}
        if license_audit_ref is not None:
            metadata["license_audit_ref"] = license_audit_ref
        if source_url is not None:
            metadata["source_url"] = source_url

        source_lineage = SourceRecordLineage(
            source_database=source_name,
            source_version="v2",
            source_record_id=source_record_id,
            raw_manifest_file=raw_manifest_file,
            raw_file_path=raw_file_path,
            raw_file_sha256=checksum,
            row_index=row_index,
        )

        target_atom_identity = ProteinAtomIdentity(
            chain_id="A",
            residue_name=residue_name,
            residue_number=residue_number,
            atom_name="SG",
        )

        ligand_atom_identity = LigandAtomIdentity(
            ligand_id=ligand_id,
            atom_name="C1",
        )

        records.append(
            SourceIngestRecord(
                source_database=source_name,
                source_version="v2",
                source_record_id=source_record_id,
                raw_manifest_file=raw_manifest_file,
                raw_file_path=raw_file_path,
                raw_file_sha256=checksum,
                row_index=row_index,
                lineage=lineage,
                protein=protein,
                ligand=ligand,
                linkage=linkage,
                metadata=metadata,
                source_lineage=source_lineage,
                target_atom_identity=target_atom_identity,
                ligand_atom_identity=ligand_atom_identity,
            )
        )

    return records, tuple(errors)


def _parse_residue(residue: str) -> tuple[str, int]:
    """Parse 'CYS145' → ('CYS', 145)."""
    m = _RESIDUE_RE.match(residue.strip())
    if not m:
        raise ValueError(f"Unable to parse residue field: {residue!r}")
    return m.group(1).upper(), int(m.group(2))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _text(row: Mapping[str, Optional[str]], column: str) -> str:
    value = row.get(column)
    if value is None:
        return ""
    return value.strip()


def _result_envelope(
    records: list[SourceIngestRecord],
    errors: tuple[ContractErrorInfo, ...],
    input_sha256: str,
) -> ContractEnvelope[tuple[SourceIngestRecord, ...]]:
    return ContractEnvelope(
        payload=tuple(records),
        artifacts=(),
        receipt=ValidationReceipt(
            validator=VALIDATOR_NAME,
            contract_version=V2_CONTRACT_VERSION,
            input_sha256=input_sha256,
            ok=not errors,
            errors=errors,
        ),
        provenance=Provenance(),
    )


def _fail_envelope(
    errors: tuple[ContractErrorInfo, ...],
    *,
    input_sha256: str = "",
) -> ContractEnvelope[tuple[SourceIngestRecord, ...]]:
    return ContractEnvelope(
        payload=(),
        artifacts=(),
        receipt=ValidationReceipt(
            validator=VALIDATOR_NAME,
            contract_version=V2_CONTRACT_VERSION,
            input_sha256=input_sha256,
            ok=False,
            errors=errors,
        ),
        provenance=Provenance(),
    )


def _error(
    code: str,
    message: str,
    *,
    location: Optional[str] = None,
    details: Optional[Mapping[str, object]] = None,
) -> ContractErrorInfo:
    return ContractErrorInfo(
        code=code,
        owner="data",
        message=message,
        location=location,
        details=dict(details or {}),
    )


__all__ = [
    "convert_staged_manifest",
    "convert_staged_source",
]
