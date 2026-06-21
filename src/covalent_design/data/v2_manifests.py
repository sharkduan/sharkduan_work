"""V2 raw data intake manifest contracts.

Task 40 defines schema and validation only.  This module must not download
data, inspect raw-data contents, stage files, convert records, or decide
license eligibility.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Optional

from covalent_design.contracts.errors import ContractErrorInfo
from covalent_design.contracts.types import (
    ContractEnvelope,
    Provenance,
    ValidationReceipt,
)


SCHEMA_VERSION = "1.0.0"
CONTRACT_VERSION = "v2-beta"
VALIDATOR_NAME = "covalent_design.data.validate_v2_data_intake_manifest"
MANIFEST_ROLE = "v2_data_intake_manifest"

ALLOWED_SOURCE_NAMES = ("CovalentInDB", "CovPDB", "CovBinderInPDB")
ALLOWED_INTAKE_MODES = ("download", "manual")
ALLOWED_PARSER_TARGETS = ("covalentin_db", "covpdb", "covbinder_in_pdb")
ALLOWED_CHECKSUM_ALGORITHMS = ("sha256",)

SOURCE_TO_PARSER_TARGET = {
    "CovalentInDB": "covalentin_db",
    "CovPDB": "covpdb",
    "CovBinderInPDB": "covbinder_in_pdb",
}

REQUIRED_FIELDS = (
    "schema_version",
    "contract_version",
    "source_name",
    "intake_mode",
    "checksum",
    "checksum_algorithm",
    "parser_target",
    "retrieval_date",
    "license_audit_ref",
    "access_notes",
)

FORBIDDEN_TASK40_FIELDS = (
    "conversion_status",
    "license_eligibility",
    "license_status",
    "staging_status",
    "training_artifacts",
    "training_eligible",
    "training_split",
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class V2DataIntakeManifest:
    schema_version: str
    contract_version: str
    source_name: str
    intake_mode: str
    checksum: str
    checksum_algorithm: str
    parser_target: str
    retrieval_date: str
    license_audit_ref: str
    access_notes: str
    source_url: Optional[str] = None
    manual_path: Optional[str] = None


def validate_v2_data_intake_manifest(
    manifest_path: Path,
) -> ContractEnvelope[Optional[V2DataIntakeManifest]]:
    """Validate a manifest JSON file without touching raw data or network."""
    path = Path(manifest_path)
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        error = _error(
            "V2_MANIFEST_UNREADABLE",
            f"Unable to read V2 data intake manifest: {exc}",
            location=str(path),
        )
        return _envelope(None, (error,), input_text="")

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        error = _error(
            "V2_MANIFEST_INVALID_JSON",
            f"Invalid JSON in V2 data intake manifest: {exc}",
            location=str(path),
        )
        return _envelope(None, (error,), input_text=text)

    return v2_data_intake_manifest_from_dict(data, location=str(path), input_text=text)


def v2_data_intake_manifest_from_dict(
    data: Mapping[str, object],
    *,
    location: str = "<dict>",
    input_text: Optional[str] = None,
) -> ContractEnvelope[Optional[V2DataIntakeManifest]]:
    """Validate an in-memory manifest mapping and return a contract envelope."""
    if not isinstance(data, Mapping):
        error = _error(
            "V2_MANIFEST_ROOT_NOT_OBJECT",
            "V2 data intake manifest root must be a JSON object",
            location=location,
        )
        return _envelope(None, (error,), input_text=input_text or "")

    errors = list(_validate_mapping(data, location=location))
    if errors:
        return _envelope(None, tuple(errors), input_text=input_text or _canonical_json(data))

    manifest = V2DataIntakeManifest(
        schema_version=str(data["schema_version"]),
        contract_version=str(data["contract_version"]),
        source_name=str(data["source_name"]),
        intake_mode=str(data["intake_mode"]),
        checksum=str(data["checksum"]),
        checksum_algorithm=str(data["checksum_algorithm"]),
        parser_target=str(data["parser_target"]),
        retrieval_date=str(data["retrieval_date"]),
        license_audit_ref=str(data["license_audit_ref"]),
        access_notes=str(data["access_notes"]),
        source_url=_optional_string(data.get("source_url")),
        manual_path=_optional_string(data.get("manual_path")),
    )
    return _envelope(manifest, (), input_text=input_text or serialize_v2_data_intake_manifest(manifest))


def serialize_v2_data_intake_manifest(manifest: V2DataIntakeManifest) -> str:
    """Return deterministic compact JSON for a manifest."""
    return _canonical_json(asdict(manifest))


def v2_data_intake_manifest_to_dict(
    manifest: V2DataIntakeManifest,
) -> dict[str, object]:
    """Return a deterministic JSON-compatible manifest dict."""
    return dict(sorted(asdict(manifest).items(), key=lambda item: item[0]))


def _validate_mapping(
    data: Mapping[str, object],
    *,
    location: str,
) -> tuple[ContractErrorInfo, ...]:
    errors: list[ContractErrorInfo] = []

    for field in REQUIRED_FIELDS:
        if _is_missing(data.get(field)):
            errors.append(
                _error(
                    "V2_MANIFEST_MISSING_REQUIRED_FIELD",
                    f"Missing required field: {field}",
                    location=f"{location}:{field}",
                    details={"field": field},
                )
            )

    for field in FORBIDDEN_TASK40_FIELDS:
        if field in data:
            errors.append(
                _error(
                    "V2_MANIFEST_FORBIDDEN_FIELD",
                    f"Field {field!r} belongs to a later task and is not part of Task 40",
                    location=f"{location}:{field}",
                    details={"field": field},
                )
            )

    source_name = data.get("source_name")
    if not _is_missing(source_name) and source_name not in ALLOWED_SOURCE_NAMES:
        errors.append(
            _error(
                "V2_MANIFEST_UNKNOWN_SOURCE_NAME",
                f"Unknown source_name {source_name!r}",
                location=f"{location}:source_name",
                details={"allowed": ALLOWED_SOURCE_NAMES, "got": source_name},
            )
        )

    intake_mode = data.get("intake_mode")
    if not _is_missing(intake_mode) and intake_mode not in ALLOWED_INTAKE_MODES:
        errors.append(
            _error(
                "V2_MANIFEST_UNKNOWN_INTAKE_MODE",
                f"Unknown intake_mode {intake_mode!r}",
                location=f"{location}:intake_mode",
                details={"allowed": ALLOWED_INTAKE_MODES, "got": intake_mode},
            )
        )

    if intake_mode == "manual" and _is_missing(data.get("manual_path")):
        errors.append(
            _error(
                "V2_MANIFEST_MANUAL_PATH_REQUIRED",
                "manual intake mode requires manual_path",
                location=f"{location}:manual_path",
            )
        )
    if intake_mode == "download" and _is_missing(data.get("source_url")):
        errors.append(
            _error(
                "V2_MANIFEST_SOURCE_URL_REQUIRED",
                "download intake mode requires source_url",
                location=f"{location}:source_url",
            )
        )

    checksum_algorithm = data.get("checksum_algorithm")
    if (
        not _is_missing(checksum_algorithm)
        and checksum_algorithm not in ALLOWED_CHECKSUM_ALGORITHMS
    ):
        errors.append(
            _error(
                "V2_MANIFEST_UNSUPPORTED_CHECKSUM_ALGORITHM",
                f"Unsupported checksum_algorithm {checksum_algorithm!r}",
                location=f"{location}:checksum_algorithm",
                details={"allowed": ALLOWED_CHECKSUM_ALGORITHMS, "got": checksum_algorithm},
            )
        )

    checksum = data.get("checksum")
    if not _is_missing(checksum) and (
        not isinstance(checksum, str) or not _SHA256_RE.fullmatch(checksum)
    ):
        errors.append(
            _error(
                "V2_MANIFEST_CHECKSUM_INVALID",
                "checksum must be a 64-character lowercase SHA-256 hex digest",
                location=f"{location}:checksum",
            )
        )

    parser_target = data.get("parser_target")
    if not _is_missing(parser_target) and parser_target not in ALLOWED_PARSER_TARGETS:
        errors.append(
            _error(
                "V2_MANIFEST_UNKNOWN_PARSER_TARGET",
                f"Unknown parser_target {parser_target!r}",
                location=f"{location}:parser_target",
                details={"allowed": ALLOWED_PARSER_TARGETS, "got": parser_target},
            )
        )

    expected_parser = SOURCE_TO_PARSER_TARGET.get(str(source_name))
    if (
        expected_parser is not None
        and parser_target in ALLOWED_PARSER_TARGETS
        and parser_target != expected_parser
    ):
        errors.append(
            _error(
                "V2_MANIFEST_SOURCE_PARSER_MISMATCH",
                f"source_name {source_name!r} must use parser_target {expected_parser!r}",
                location=f"{location}:parser_target",
                details={
                    "source_name": source_name,
                    "expected_parser_target": expected_parser,
                    "got": parser_target,
                },
            )
        )

    return tuple(errors)


def _is_missing(value: object) -> bool:
    return value is None or value == ""


def _optional_string(value: object) -> Optional[str]:
    if value is None:
        return None
    return str(value)


def _canonical_json(data: Mapping[str, object]) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


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


def _envelope(
    payload: Optional[V2DataIntakeManifest],
    errors: tuple[ContractErrorInfo, ...],
    *,
    input_text: str,
) -> ContractEnvelope[Optional[V2DataIntakeManifest]]:
    return ContractEnvelope(
        payload=payload,
        artifacts=(),
        receipt=ValidationReceipt(
            validator=VALIDATOR_NAME,
            contract_version=CONTRACT_VERSION,
            input_sha256=_sha256_text(input_text),
            ok=not errors,
            errors=errors,
        ),
        provenance=Provenance(),
    )


def _sha256_text(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()


__all__ = [
    "ALLOWED_CHECKSUM_ALGORITHMS",
    "ALLOWED_INTAKE_MODES",
    "ALLOWED_PARSER_TARGETS",
    "ALLOWED_SOURCE_NAMES",
    "CONTRACT_VERSION",
    "MANIFEST_ROLE",
    "SCHEMA_VERSION",
    "SOURCE_TO_PARSER_TARGET",
    "V2DataIntakeManifest",
    "serialize_v2_data_intake_manifest",
    "v2_data_intake_manifest_from_dict",
    "v2_data_intake_manifest_to_dict",
    "validate_v2_data_intake_manifest",
]
