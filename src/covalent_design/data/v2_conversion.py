"""Task 42: V2 data conversion — convert Task 41 staging evidence to SourceIngestRecord records.

Converts checked-in, checksum-verified manual staged source data into
v1-compatible ``SourceIngestRecord`` records, preserving provenance and
license audit references for downstream tasks (43+).
"""

from __future__ import annotations

import csv
import hashlib
import re
from dataclasses import dataclass
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

from covalent_design.data.manifests import RawManifestFile, RawSourceManifest
from covalent_design.data.sources.covalentin_db import parse_covalentin_db_records
from covalent_design.data.sources.covpdb import parse_covpdb_records
from covalent_design.data.sources.covbinder_in_pdb import parse_covbinder_records

VALIDATOR_NAME = "covalent_design.data.v2_convert_staged_source"

# Supported parser targets for Task 42 conversion.
SUPPORTED_PARSER_TARGETS = frozenset({"covalentin_db", "covpdb", "covbinder_in_pdb"})
UNSUPPORTED_PARSER_TARGETS: frozenset[str] = frozenset()


def is_parser_target_supported(parser_target: str) -> bool:
    """Return True if *parser_target* is implemented in Task 42 conversion."""
    return parser_target in SUPPORTED_PARSER_TARGETS


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
_COVPDB_LINK_RE = re.compile(
    r"^LINK\s+(.{4})\s+(.{3})\s+(.{1})\s*(\d+)([A-Za-z]?)\s+"
    r"(.{4})\s+(.{3})\s+(.{1})\s*(\d+)([A-Za-z]?)\s+"
    r"(\d+)\s+(\d+)\s+([\d.]+)"
)
_COVPDB_RESOLUTION_RE = re.compile(r"REMARK\s+2\s+RESOLUTION.\s*([\d.]+)")

_RESIDUE_ATOM = {
    "CYS": "SG",
    "SER": "OG",
    "LYS": "NZ",
    "HIS": "NE2",
    "THR": "OG1",
    "TYR": "OH",
    "ASP": "OD1",
    "GLU": "OE1",
    "MET": "SD",
    "SEC": "SE",
    "ASN": "ND2",
    "GLN": "NE2",
}
_COVALENTIN_REACTION_TO_FAMILY = {
    "Michael Addition": "MICHAEL_ADDITION",
    "Nucleophilic Substitution": "NUCLEOPHILIC_SUBSTITUTION",
    "Disulfide Exchange": "DISULFIDE_EXCHANGE",
    "Acylation": "ACYLATION",
    "Phosphonate Addition": "PHOSPHONYLATION",
    "Schiff Base": "SCHIFF_BASE",
}
_COVALENTIN_BOND_TYPE = {
    "Michael Addition": "single",
    "Nucleophilic Substitution": "single",
    "Disulfide Exchange": "single",
    "Acylation": "single",
    "Phosphonate Addition": "single",
    "Schiff Base": "double",
}
_FULL_RESIDUE_TO_THREE_LETTER = {
    "cysteine": "CYS",
    "serine": "SER",
    "lysine": "LYS",
    "histidine": "HIS",
    "threonine": "THR",
    "tyrosine": "TYR",
    "aspartic acid": "ASP",
    "aspartate": "ASP",
    "glutamic acid": "GLU",
    "glutamate": "GLU",
    "methionine": "MET",
    "asparagine": "ASN",
    "glutamine": "GLN",
    "tryptophan": "TRP",
    "phenylalanine": "PHE",
    "arginine": "ARG",
    "proline": "PRO",
    "selenocysteine": "SEC",
    "glycine": "GLY",
    "alanine": "ALA",
    "valine": "VAL",
    "leucine": "LEU",
    "isoleucine": "ILE",
}
_WARHEAD_FAMILY = {
    "haloacetamide": ("NUCLEOPHILIC_SUBSTITUTION", "single"),
    "α-ketoamide": ("MICHAEL_ADDITION", "single"),
    "acrylamide": ("MICHAEL_ADDITION", "single"),
    "vinyl sulfone": ("MICHAEL_ADDITION", "single"),
    "michael acceptor": ("MICHAEL_ADDITION", "single"),
    "disulfide": ("DISULFIDE_EXCHANGE", "single"),
    "phosphonate": ("PHOSPHONYLATION", "single"),
    "β-lactam": ("ACYLATION", "single"),
    "sulfonyl fluoride": ("ACYLATION", "single"),
    "aldehyde": ("SCHIFF_BASE", "double"),
}
_STD_AMINO = frozenset(
    {
        "ALA",
        "ARG",
        "ASN",
        "ASP",
        "CYS",
        "GLN",
        "GLU",
        "GLY",
        "HIS",
        "ILE",
        "LEU",
        "LYS",
        "MET",
        "PHE",
        "PRO",
        "SER",
        "THR",
        "TRP",
        "TYR",
        "VAL",
        "SEC",
        "PYL",
    }
)
_REACTION_FROM_RESIDUE = {
    "CYS": "MICHAEL_ADDITION",
    "SER": "ACYLATION",
    "LYS": "SCHIFF_BASE",
    "HIS": "MICHAEL_ADDITION",
    "THR": "ACYLATION",
    "TYR": "MICHAEL_ADDITION",
}


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
    if parser_target not in SUPPORTED_PARSER_TARGETS:
        errors.append(
            _error(
                "V2_CONVERSION_UNSUPPORTED_PARSER",
                f"Parser target {parser_target!r} is not supported in Task 42",
                details={
                    "parser_target": parser_target,
                    "supported": sorted(SUPPORTED_PARSER_TARGETS),
                    "known_unsupported": sorted(UNSUPPORTED_PARSER_TARGETS),
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

    if parser_target == "covalentin_db" and _has_simplified_v2_columns(manual_path):
        records, simplified_errors = _parse_v2_source(
            path=manual_path,
            source_name=summary.source_name,
            checksum=summary.checksum or "",
            source_url=summary.source_url,
            license_audit_ref=summary.license_audit_ref,
        )
        return _result_envelope(records, tuple(errors) + tuple(simplified_errors), input_sha256)

    raw_rows: list[dict[str, str]]
    raw_failures: tuple[_TSVRowFailure, ...]
    if parser_target == "covalentin_db" and _has_columns(manual_path, ("ID", "Resi_name")):
        raw_rows, raw_failures = _parse_covalentin_raw_source(
            path=manual_path,
            source_name=summary.source_name,
            checksum=summary.checksum or "",
            source_url=summary.source_url,
            license_audit_ref=summary.license_audit_ref,
        )
        records = [
            _tsv_row_to_source_ingest_record(row, checksum=summary.checksum or "")
            for row in raw_rows
        ]
        return _result_envelope(
            records,
            tuple(errors) + _row_failures_to_errors(raw_failures, manual_path),
            input_sha256,
        )

    if parser_target == "covbinder_in_pdb" and _has_columns(
        manual_path, ("full_residue_name", "warhead_name")
    ):
        raw_rows, raw_failures = _parse_covbinder_raw_source(
            path=manual_path,
            source_name=summary.source_name,
            checksum=summary.checksum or "",
            source_url=summary.source_url,
            license_audit_ref=summary.license_audit_ref,
        )
        records = [
            _tsv_row_to_source_ingest_record(row, checksum=summary.checksum or "")
            for row in raw_rows
        ]
        return _result_envelope(
            records,
            tuple(errors) + _row_failures_to_errors(raw_failures, manual_path),
            input_sha256,
        )

    if parser_target == "covpdb":
        covpdb_root = _resolve_covpdb_complex_root(manual_path)
        if covpdb_root is not None:
            raw_rows, raw_failures = _parse_covpdb_raw_source(
                pdb_root=covpdb_root,
                lineage_path=manual_path,
                source_name=summary.source_name,
                checksum=summary.checksum or "",
                source_url=summary.source_url,
                license_audit_ref=summary.license_audit_ref,
            )
            records = [
                _tsv_row_to_source_ingest_record(row, checksum=summary.checksum or "")
                for row in raw_rows
            ]
            return _result_envelope(
                records,
                tuple(errors) + _row_failures_to_errors(raw_failures, manual_path),
                input_sha256,
            )

    # Build minimal manifest for v1 parsers
    file_bytes = manual_path.stat().st_size
    minimal_file_entry = RawManifestFile(
        source_database=summary.source_name,
        path=str(manual_path),
        role="source_data",
        bytes=file_bytes,
        sha256=summary.checksum or "",
    )
    minimal_manifest = RawSourceManifest(
        source_database=summary.source_name,
        source_version="v2",
        retrieval_date="2026-06-18",
        license="manual_exempt",
        access_notes=summary.source_name,
        complete_for_v1=True,
        manifest_path=str(manual_path.parent / "manifest.json"),
        files=(minimal_file_entry,),
    )

    # Read TSV rows directly (v1 parsers expect comma-delimited CSV,
    # but our transformed files are tab-delimited TSV)
    tsv_rows, parse_errors_tuple = _parse_tsv_source(
        path=manual_path,
        source_name=summary.source_name,
        checksum=summary.checksum or "",
        source_url=summary.source_url,
        license_audit_ref=summary.license_audit_ref,
        parser_target=parser_target,
    )

    # Convert typed TSV rows to SourceIngestRecord objects
    records: list[SourceIngestRecord] = []
    for tr in tsv_rows:
        record = _tsv_row_to_source_ingest_record(tr, checksum=summary.checksum or "")
        records.append(record)

    parse_errors: list[ContractErrorInfo] = []
    for pf in parse_errors_tuple:
        parse_errors.append(_error(
            "V2_CONVERSION_ROW_PARSE_ERROR",
            pf.message,
            location=f"{manual_path}:row:{pf.row_index}",
            details={"row_index": pf.row_index, "reason": pf.reason},
        ))

    all_errors = tuple(errors) + tuple(parse_errors)
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


def _has_simplified_v2_columns(path: Path) -> bool:
    """Return True for the legacy 8-column synthetic covalentin_db fixture TSV."""
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError:
        return False
    if not text.strip():
        return False
    reader = csv.DictReader(text.splitlines(), delimiter="\t")
    if reader.fieldnames is None:
        return False
    return all(column in reader.fieldnames for column in _V2_REQUIRED_COLUMNS)


def _has_columns(path: Path, required: tuple[str, ...]) -> bool:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            fieldnames = reader.fieldnames or ()
    except OSError:
        return False
    return all(column in fieldnames for column in required)


def _parse_covalentin_raw_source(
    *,
    path: Path,
    source_name: str,
    checksum: str,
    source_url: Optional[str],
    license_audit_ref: Optional[str],
) -> tuple[list[dict[str, str]], tuple["_TSVRowFailure", ...]]:
    rows: list[dict[str, str]] = []
    failures: list[_TSVRowFailure] = []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row_index, row in enumerate(reader, start=1):
                residue_name = _text(row, "Resi_name").upper()
                if not residue_name:
                    continue
                reaction = _text(row, "Reaction")
                residue = f"{residue_name}{_text(row, 'Resi_posi')}"
                out_row = {
                    "compound_id": _text(row, "ID"),
                    "target_name": _text(row, "Protein_name"),
                    "uniprot_id": _text(row, "Proteins"),
                    "residue": residue,
                    "residue_name": residue_name,
                    "atom_name": _RESIDUE_ATOM.get(residue_name, "SG"),
                    "attachment_atom": "C1",
                    "warhead_class": _text(row, "Warhead"),
                    "bond_type": _COVALENTIN_BOND_TYPE.get(reaction, "single"),
                    "reaction_family": (
                        f"{residue_name}_"
                        f"{_COVALENTIN_REACTION_TO_FAMILY.get(reaction, 'UNKNOWN')}"
                    ),
                    "pdb_id": _text(row, "PDB"),
                    "chain": _text(row, "Resi_chain") or "_",
                    "resolution": _float_text(row.get("Resolution")) or "unknown",
                    "smiles": _text(row, "SMILES"),
                    "year": _int_text(row.get("Year")),
                }
                _add_lineage_fields(
                    out_row,
                    path=path,
                    source_name=source_name,
                    checksum=checksum,
                    source_url=source_url,
                    license_audit_ref=license_audit_ref,
                    parser_target="covalentin_db",
                    row_index=row_index,
                )
                rows.append(out_row)
    except OSError as exc:
        failures.append(
            _TSVRowFailure(source_name, str(path), 0, "FILE_UNREADABLE", str(exc), "")
        )
    return rows, tuple(failures)


def _parse_covbinder_raw_source(
    *,
    path: Path,
    source_name: str,
    checksum: str,
    source_url: Optional[str],
    license_audit_ref: Optional[str],
) -> tuple[list[dict[str, str]], tuple["_TSVRowFailure", ...]]:
    rows: list[dict[str, str]] = []
    failures: list[_TSVRowFailure] = []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row_index, row in enumerate(reader, start=1):
                full_name = _text(row, "full_residue_name")
                residue_name = _FULL_RESIDUE_TO_THREE_LETTER.get(full_name.lower())
                if residue_name is None:
                    continue
                family_suffix, bond_type = _WARHEAD_FAMILY.get(
                    _text(row, "warhead_name").lower(), ("UNKNOWN", "single")
                )
                out_row = {
                    "pdb_id": _text(row, "pdb_id"),
                    "chain": _text(row, "chain_id") or "_",
                    "residue_number": _text(row, "res_num") or "0",
                    "residue_name": residue_name,
                    "target_atom_name": _RESIDUE_ATOM.get(residue_name, "SG"),
                    "ligand_id": _text(row, "binder_id"),
                    "ligand_chain": _text(row, "binder_chain_id") or "_",
                    "ligand_residue": _text(row, "binder_num") or "0",
                    "ligand_attachment_atom": "C1",
                    "bond_type": bond_type,
                    "reaction_family": f"{residue_name}_{family_suffix}",
                    "resolution": "unknown",
                    "smiles": _text(row, "binder_smiles"),
                    "doi": _text(row, "doi"),
                }
                _add_lineage_fields(
                    out_row,
                    path=path,
                    source_name=source_name,
                    checksum=checksum,
                    source_url=source_url,
                    license_audit_ref=license_audit_ref,
                    parser_target="covbinder_in_pdb",
                    row_index=row_index,
                )
                rows.append(out_row)
    except OSError as exc:
        failures.append(
            _TSVRowFailure(source_name, str(path), 0, "FILE_UNREADABLE", str(exc), "")
        )
    return rows, tuple(failures)


def _resolve_covpdb_complex_root(manual_path: Path) -> Optional[Path]:
    candidates = [
        manual_path.with_suffix(""),
        manual_path.parent / manual_path.stem,
        manual_path.parent / "CovPDB" / "raw" / manual_path.stem,
    ]
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return None


def _parse_covpdb_raw_source(
    *,
    pdb_root: Path,
    lineage_path: Path,
    source_name: str,
    checksum: str,
    source_url: Optional[str],
    license_audit_ref: Optional[str],
) -> tuple[list[dict[str, str]], tuple["_TSVRowFailure", ...]]:
    rows: list[dict[str, str]] = []
    failures: list[_TSVRowFailure] = []
    row_index = 0
    for subdir in sorted(pdb_root.iterdir()):
        if not subdir.is_dir():
            continue
        pdb_id = subdir.name
        pdb_file = subdir / f"{pdb_id}.pdb"
        if not pdb_file.is_file():
            pdbs = sorted(subdir.glob("*.pdb"))
            if not pdbs:
                continue
            pdb_file = pdbs[0]
        for parsed in _parse_covpdb_pdb_file(pdb_file, pdb_id):
            row_index += 1
            _add_lineage_fields(
                parsed,
                path=lineage_path,
                source_name=source_name,
                checksum=checksum,
                source_url=source_url,
                license_audit_ref=license_audit_ref,
                parser_target="covpdb",
                row_index=row_index,
            )
            rows.append(parsed)
    return rows, tuple(failures)


def _parse_covpdb_pdb_file(pdb_file: Path, pdb_id: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    resolution = "unknown"
    try:
        with pdb_file.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if (
                    "REMARK   2 RESOLUTION" in line[:24]
                    or "REMARK   2  RESOLUTION" in line[:25]
                ):
                    match = _COVPDB_RESOLUTION_RE.search(line)
                    if match:
                        resolution = match.group(1)
                elif line.startswith("LINK "):
                    row = _parse_covpdb_link(line, pdb_id)
                    if row is not None:
                        rows.append(row)
    except OSError:
        return []
    for row in rows:
        row["resolution"] = resolution
    return rows


def _parse_covpdb_link(line: str, pdb_id: str) -> Optional[dict[str, str]]:
    match = _COVPDB_LINK_RE.match(line)
    if not match:
        return None

    atom1 = match.group(1).strip()
    res1 = match.group(2).strip()
    chain1 = match.group(3).strip() or "_"
    resnum1 = match.group(4).strip() or "0"
    atom2 = match.group(6).strip()
    res2 = match.group(7).strip()
    chain2 = match.group(8).strip() or "_"
    resnum2 = match.group(9).strip() or "0"
    try:
        distance = float(match.group(13))
    except ValueError:
        distance = 0.0

    if res1 in _STD_AMINO and res2 not in _STD_AMINO:
        protein_chain, protein_res, protein_atom, protein_num = (
            chain1,
            res1,
            atom1,
            resnum1,
        )
        ligand_id, ligand_chain, ligand_num, ligand_atom = (
            res2,
            chain2,
            resnum2,
            atom2,
        )
    elif res2 in _STD_AMINO and res1 not in _STD_AMINO:
        protein_chain, protein_res, protein_atom, protein_num = (
            chain2,
            res2,
            atom2,
            resnum2,
        )
        ligand_id, ligand_chain, ligand_num, ligand_atom = (
            res1,
            chain1,
            resnum1,
            atom1,
        )
    else:
        return None

    family_suffix = _REACTION_FROM_RESIDUE.get(protein_res, "MICHAEL_ADDITION")
    return {
        "pdb_id": pdb_id,
        "chain": protein_chain,
        "residue_number": protein_num,
        "residue_name": protein_res,
        "target_atom_name": protein_atom,
        "ligand_id": ligand_id,
        "ligand_chain": ligand_chain,
        "ligand_residue": ligand_num,
        "ligand_attachment_atom": ligand_atom,
        "bond_type": "double" if distance < 1.5 else "single",
        "reaction_family": f"{protein_res}_{family_suffix}",
    }


def _add_lineage_fields(
    row: dict[str, str],
    *,
    path: Path,
    source_name: str,
    checksum: str,
    source_url: Optional[str],
    license_audit_ref: Optional[str],
    parser_target: str,
    row_index: int,
) -> None:
    row["_source_database"] = source_name
    row["_source_version"] = "v2"
    row["_raw_manifest_file"] = str(path.parent / "manifest.json")
    row["_raw_file_path"] = str(path)
    row["_raw_file_sha256"] = checksum
    row["_row_index"] = str(row_index)
    row["_license_audit_ref"] = license_audit_ref or ""
    row["_source_url"] = source_url or ""
    row["_parser_target"] = parser_target


def _row_failures_to_errors(
    failures: tuple["_TSVRowFailure", ...],
    path: Path,
) -> tuple[ContractErrorInfo, ...]:
    return tuple(
        _error(
            "V2_CONVERSION_ROW_PARSE_ERROR",
            failure.message,
            location=f"{path}:row:{failure.row_index}",
            details={"row_index": failure.row_index, "reason": failure.reason},
        )
        for failure in failures
    )


def _float_text(value: object) -> str:
    text = "" if value is None else str(value).strip()
    if not text:
        return ""
    try:
        return str(float(text))
    except (TypeError, ValueError):
        return text


def _int_text(value: object) -> str:
    text = "" if value is None else str(value).strip()
    if not text:
        return ""
    try:
        return str(int(float(text)))
    except (TypeError, ValueError):
        return text


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


def _safe_int(value: object) -> int:
    """Safely convert a value to int, returning 0 for None or unparseable."""
    if value is None:
        return 0
    try:
        return int(value)
    except (ValueError, TypeError):
        return 0


# ---------------------------------------------------------------------------
# TSV row parsers — one per parser_target column schema
# ---------------------------------------------------------------------------
#
# Each parser_target has its own REQUIRED_COLUMNS definition in the
# corresponding v1 parser under src/covalent_design/data/sources/.
# We replicate the column lists + mapping logic here so the conversion
# path is self-contained and does not depend on the v1 parser modules
# (which expect comma-delimited CSV, not tab-delimited TSV).

_COLUMN_SCHEMAS: dict[str, tuple[tuple[str, ...], dict[str, str]]] = {
    # covalentin_db: 10 required + 7 optional
    "covalentin_db": (
        (
            "compound_id", "target_name", "uniprot_id", "residue",
            "residue_name", "atom_name", "attachment_atom",
            "warhead_class", "bond_type", "reaction_family",
        ),
        {
            "compound_id": "compound_id",
            "target_name": "target_name",
            "uniprot_id": "uniprot_id",
            "residue": "residue",
            "residue_name": "residue_name",
            "atom_name": "atom_name",
            "attachment_atom": "attachment_atom",
            "warhead_class": "warhead_class",
            "bond_type": "bond_type",
            "reaction_family": "reaction_family",
        },
    ),
    # covbinder_in_pdb: 11 required + 5 optional
    "covbinder_in_pdb": (
        (
            "pdb_id", "chain", "residue_number", "residue_name",
            "target_atom_name", "ligand_id", "ligand_chain",
            "ligand_residue", "ligand_attachment_atom",
            "bond_type", "reaction_family",
        ),
        {
            "pdb_id": "pdb_id",
            "chain": "chain",
            "residue_number": "residue_number",
            "residue_name": "residue_name",
            "target_atom_name": "target_atom_name",
            "ligand_id": "ligand_id",
            "ligand_chain": "ligand_chain",
            "ligand_residue": "ligand_residue",
            "ligand_attachment_atom": "ligand_attachment_atom",
            "bond_type": "bond_type",
            "reaction_family": "reaction_family",
        },
    ),
    # covpdb: 12 required + 3 optional
    "covpdb": (
        (
            "pdb_id", "chain", "residue_number", "residue_name",
            "target_atom_name", "ligand_id", "ligand_chain",
            "ligand_residue", "ligand_attachment_atom",
            "bond_type", "reaction_family", "resolution",
        ),
        {
            "pdb_id": "pdb_id",
            "chain": "chain",
            "residue_number": "residue_number",
            "residue_name": "residue_name",
            "target_atom_name": "target_atom_name",
            "ligand_id": "ligand_id",
            "ligand_chain": "ligand_chain",
            "ligand_residue": "ligand_residue",
            "ligand_attachment_atom": "ligand_attachment_atom",
            "bond_type": "bond_type",
            "reaction_family": "reaction_family",
            "resolution": "resolution",
        },
    ),
}


@dataclass(frozen=True)
class _TSVRowFailure:
    source_database: str
    raw_file_path: str
    row_index: int
    reason: str
    message: str
    raw_line_preview: str


def _parse_tsv_source(
    *,
    path: Path,
    source_name: str,
    checksum: str,
    source_url: Optional[str],
    license_audit_ref: Optional[str],
    parser_target: str,
) -> tuple[list[dict[str, str]], tuple[_TSVRowFailure, ...]]:
    """Parse a tab-delimited TSV source file into intermediate dict rows."""
    rows: list[dict[str, str]] = []
    failures: list[_TSVRowFailure] = []

    schema = _COLUMN_SCHEMAS.get(parser_target)
    if schema is None:
        return rows, (
            _TSVRowFailure(source_name, str(path), 0, "UNSUPPORTED_PARSER",
                           f"Unknown parser_target: {parser_target}", ""),
        )

    required_cols, _col_map = schema

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return rows, (
            _TSVRowFailure(source_name, str(path), 0, "FILE_UNREADABLE",
                           f"Unable to read: {exc}", ""),
        )

    if not text.strip():
        return rows, ()

    reader = csv.DictReader(text.splitlines(), delimiter="\t")
    if reader.fieldnames is None:
        return rows, ()

    missing = [c for c in required_cols if c not in reader.fieldnames]
    if missing:
        return rows, (
            _TSVRowFailure(source_name, str(path), 0, "MISSING_COLUMNS",
                           f"Missing required columns: {', '.join(missing)}", ""),
        )

    raw_manifest_file = str(path.parent / "manifest.json")
    raw_file_path = str(path)

    for row_index, row in enumerate(reader, start=1):
        missing_fields = [c for c in required_cols if not _text(row, c)]
        if missing_fields:
            failures.append(_TSVRowFailure(
                source_name, raw_file_path, row_index,
                "MISSING_REQUIRED_FIELD",
                f"Missing required fields: {', '.join(missing_fields)}",
                str(dict(row))[:200],
            ))
            continue

        # Enrich row with lineage metadata
        out_row: dict[str, str] = dict(row)
        out_row["_source_database"] = source_name
        out_row["_source_version"] = "v2"
        out_row["_raw_manifest_file"] = raw_manifest_file
        out_row["_raw_file_path"] = raw_file_path
        out_row["_raw_file_sha256"] = checksum
        out_row["_row_index"] = str(row_index)
        out_row["_license_audit_ref"] = license_audit_ref or ""
        out_row["_source_url"] = source_url or ""
        out_row["_parser_target"] = parser_target
        rows.append(out_row)

    return rows, tuple(failures)


def _tsv_row_to_source_ingest_record(
    row: dict[str, str],
    *,
    checksum: str = "",
) -> SourceIngestRecord:
    """Convert a parsed TSV row dict to a SourceIngestRecord."""
    source_name = row.get("_source_database", "")
    raw_file_path = row.get("_raw_file_path", "")
    row_index = int(row.get("_row_index", "0"))
    source_record_id = f"{source_name}:{raw_file_path}:row:{row_index}"

    lineage: dict[str, object] = {
        "source_database": source_name,
        "source_version": row.get("_source_version", "v2"),
        "source_record_id": source_record_id,
        "raw_manifest_file": row.get("_raw_manifest_file", ""),
        "raw_file_path": raw_file_path,
        "raw_file_sha256": checksum,
        "row_index": row_index,
    }
    license_ref = row.get("_license_audit_ref", "")
    source_url = row.get("_source_url", "")
    if license_ref:
        lineage["license_audit_ref"] = license_ref
    if source_url:
        lineage["source_url"] = source_url

    parser_target = row.get("_parser_target", "")

    if parser_target == "covalentin_db":
        chain_id = row.get("chain", "A")
        residue_name_val = row.get("residue_name", "")
        residue_number_val = _parse_residue_num_from_residue(row.get("residue", ""))
        atom_name_val = row.get("atom_name", "SG")
        target_name = row.get("target_name", "")
        uniprot_id = row.get("uniprot_id", "")
        ligand_id_val = row.get("compound_id", "")
        attachment_atom = row.get("attachment_atom", "C1")
        warhead_class = row.get("warhead_class", "")
        bond_type = row.get("bond_type", "single")
        family = row.get("reaction_family", "")
        protein = {
            "target_name": target_name, "uniprot_id": uniprot_id,
            "chain_id": chain_id, "residue_name": residue_name_val,
            "residue_number": residue_number_val, "atom_name": atom_name_val,
        }
        ligand = {
            "compound_id": ligand_id_val, "ligand_id": ligand_id_val,
            "attachment_atom": attachment_atom, "warhead_class": warhead_class,
        }
        linkage = {"bond_type": bond_type, "residue_reaction_family": family}
        metadata: dict[str, object] = {
            "pdb_id": row.get("pdb_id", ""),
            "resolution": row.get("resolution", ""),
            "smiles": row.get("smiles", ""),
            "year": row.get("year", ""),
        }
        target_atom = ProteinAtomIdentity(
            chain_id=chain_id, residue_name=residue_name_val,
            residue_number=residue_number_val, atom_name=atom_name_val,
        )
        ligand_atom = LigandAtomIdentity(
            ligand_id=ligand_id_val, atom_name=attachment_atom,
        )
    elif parser_target in ("covpdb", "covbinder_in_pdb"):
        chain_id = row.get("chain", "A")
        residue_name_val = row.get("residue_name", "")
        residue_number_val = _safe_int(row.get("residue_number"))
        atom_name_val = row.get("target_atom_name", "SG")
        pdb_id = row.get("pdb_id", "")
        ligand_id_val = row.get("ligand_id", "")
        ligand_chain = row.get("ligand_chain", "A")
        ligand_residue = _safe_int(row.get("ligand_residue"))
        attachment_atom = row.get("ligand_attachment_atom", "C1")
        bond_type = row.get("bond_type", "single")
        family = row.get("reaction_family", "")
        protein = {
            "pdb_id": pdb_id, "target_name": pdb_id,
            "uniprot_id": "", "chain_id": chain_id,
            "residue_name": residue_name_val, "residue_number": residue_number_val,
            "atom_name": atom_name_val,
        }
        ligand = {
            "ligand_id": ligand_id_val, "compound_id": ligand_id_val,
            "attachment_atom": attachment_atom,
            "chain_id": ligand_chain, "residue_number": ligand_residue,
            "warhead_class": "",
        }
        linkage = {"bond_type": bond_type, "residue_reaction_family": family}
        metadata = {
            "pdb_id": pdb_id,
            "resolution": row.get("resolution", ""),
            "smiles": row.get("smiles", ""),
            "doi": row.get("doi", ""),
        }
        target_atom = ProteinAtomIdentity(
            chain_id=chain_id, residue_name=residue_name_val,
            residue_number=residue_number_val, atom_name=atom_name_val,
        )
        ligand_atom = LigandAtomIdentity(
            ligand_id=ligand_id_val, atom_name=attachment_atom,
        )
    else:
        raise ValueError(f"Unknown parser_target: {parser_target}")

    source_lineage = SourceRecordLineage(
        source_database=source_name, source_version="v2",
        source_record_id=source_record_id,
        raw_manifest_file=row.get("_raw_manifest_file", ""),
        raw_file_path=raw_file_path,
        raw_file_sha256=checksum,
        row_index=row_index,
    )
    if license_ref:
        metadata["license_audit_ref"] = license_ref
    if source_url:
        metadata["source_url"] = source_url

    return SourceIngestRecord(
        source_database=source_name,
        source_version="v2",
        source_record_id=source_record_id,
        raw_manifest_file=row.get("_raw_manifest_file", ""),
        raw_file_path=raw_file_path,
        raw_file_sha256=checksum,
        row_index=row_index,
        lineage=lineage,
        protein=protein,
        ligand=ligand,
        linkage=linkage,
        metadata=metadata,
        source_lineage=source_lineage,
        target_atom_identity=target_atom,
        ligand_atom_identity=ligand_atom,
    )


def _parse_residue_num_from_residue(residue: str) -> int:
    """Extract residue number from 'CYS145' -> 145."""
    m = re.match(r"^[A-Za-z]+(\d+)$", residue.strip())
    if m:
        return int(m.group(1))
    return 0


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
    "SUPPORTED_PARSER_TARGETS",
    "UNSUPPORTED_PARSER_TARGETS",
    "convert_staged_manifest",
    "convert_staged_source",
    "is_parser_target_supported",
]
