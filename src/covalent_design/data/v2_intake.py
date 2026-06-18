"""Task 41: V2 data intake staging — validate, checksum, and stage source manifests.

This module must not download data, convert records, inspect raw-data contents
beyond checksums, or decide license eligibility.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional
from urllib.parse import urlparse

from covalent_design.contracts.errors import ContractErrorInfo
from covalent_design.contracts.types import (
    ContractEnvelope,
    Provenance,
    ValidationReceipt,
)
from covalent_design.data.v2_manifests import (
    CONTRACT_VERSION as V2_MANIFEST_CONTRACT_VERSION,
    V2DataIntakeManifest,
    validate_v2_data_intake_manifest,
)

VALIDATOR_NAME = "covalent_design.data.stage_source_manifest"
STAGING_ROLE = "v2_source_staging"

STATUS_CHECKSUM_VERIFIED = "checksum_verified"
STATUS_PENDING_DOWNLOAD = "pending_download"
STATUS_OK = "ok"

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class V2DownloadRequest:
    """Pending download request for a source that needs network retrieval."""

    source_url: str
    intended_output_name: str
    source_artifact_id: str
    expected_checksum: str
    checksum_algorithm: str
    retrieval_metadata_placeholder: Mapping[str, str]
    license_audit_ref: str
    retrieval_date: str


@dataclass(frozen=True)
class V2StagingSummary:
    """Deterministic summary of a source staging operation."""

    source_name: str
    intake_mode: str
    status: str
    source_url: Optional[str] = None
    manual_path: Optional[str] = None
    output_root: Optional[str] = None
    checksum: Optional[str] = None
    checksum_algorithm: Optional[str] = None
    parser_target: Optional[str] = None
    license_audit_ref: Optional[str] = None
    download_request: Optional[V2DownloadRequest] = None


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def v2_staging_summary_to_dict(summary: V2StagingSummary) -> dict[str, object]:
    """Return a deterministic JSON-compatible dict for a staging summary."""
    result: dict[str, object] = {
        "source_name": summary.source_name,
        "intake_mode": summary.intake_mode,
        "status": summary.status,
    }
    if summary.source_url is not None:
        result["source_url"] = summary.source_url
    if summary.manual_path is not None:
        result["manual_path"] = summary.manual_path
    if summary.output_root is not None:
        result["output_root"] = summary.output_root
    if summary.checksum is not None:
        result["checksum"] = summary.checksum
    if summary.checksum_algorithm is not None:
        result["checksum_algorithm"] = summary.checksum_algorithm
    if summary.parser_target is not None:
        result["parser_target"] = summary.parser_target
    if summary.license_audit_ref is not None:
        result["license_audit_ref"] = summary.license_audit_ref
    if summary.download_request is not None:
        result["download_request"] = {
            "checksum_algorithm": summary.download_request.checksum_algorithm,
            "expected_checksum": summary.download_request.expected_checksum,
            "intended_output_name": summary.download_request.intended_output_name,
            "license_audit_ref": summary.download_request.license_audit_ref,
            "retrieval_date": summary.download_request.retrieval_date,
            "retrieval_metadata_placeholder": dict(
                summary.download_request.retrieval_metadata_placeholder
            ),
            "source_artifact_id": summary.download_request.source_artifact_id,
            "source_url": summary.download_request.source_url,
        }
    return dict(sorted(result.items(), key=lambda item: item[0]))


def serialize_v2_staging_summary(summary: V2StagingSummary) -> str:
    """Return deterministic compact JSON for a staging summary."""
    return json.dumps(
        v2_staging_summary_to_dict(summary),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


# ---------------------------------------------------------------------------
# Core staging logic
# ---------------------------------------------------------------------------


def stage_source_manifest(
    manifest_path: Path,
    *,
    allow_download: bool = False,
    output_root: Optional[Path] = None,
) -> ContractEnvelope[V2StagingSummary]:
    """Stage a v2 data intake manifest.

    Manual mode: resolves ``manual_path`` relative to the manifest directory,
    verifies the file exists, and checks its SHA-256 against the manifest.

    Download mode without ``allow_download``: validates the manifest and returns
    a pending-download summary without touching the network.

    Download mode with ``allow_download=True``: returns a structured error
    because Task 41 has no real downloader.
    """
    path = Path(manifest_path).resolve()
    manifest_dir = path.parent

    try:
        manifest_text = path.read_text(encoding="utf-8")
    except OSError as exc:
        error = _error(
            "V2_INTAKE_MANIFEST_UNREADABLE",
            f"Unable to read manifest: {exc}",
            location=str(path),
        )
        return _fail_envelope((error,))

    manifest_sha256 = _sha256_text(manifest_text)

    envelope = validate_v2_data_intake_manifest(path)

    if not envelope.receipt.ok or envelope.payload is None:
        return _fail_envelope(envelope.receipt.errors, input_sha256=manifest_sha256)

    manifest: V2DataIntakeManifest = envelope.payload

    if manifest.intake_mode == "manual":
        return _stage_manual(manifest, manifest_dir, output_root, manifest_sha256)
    return _stage_download(manifest, allow_download, output_root, manifest_sha256)


def _stage_manual(
    manifest: V2DataIntakeManifest,
    manifest_dir: Path,
    output_root: Optional[Path],
    manifest_sha256: str,
) -> ContractEnvelope[V2StagingSummary]:
    if not manifest.manual_path:
        error = _error(
            "V2_INTAKE_MANUAL_PATH_MISSING",
            "manual_path is required for manual intake mode",
        )
        return _fail_envelope((error,))

    manual_path = Path(manifest.manual_path)
    if not manual_path.is_absolute():
        manual_path = manifest_dir / manual_path
    manual_path = manual_path.resolve()

    if not manual_path.is_file():
        error = _error(
            "V2_INTAKE_MANUAL_PATH_FILE_NOT_FOUND",
            f"Manual file not found: {manual_path}",
            location=str(manual_path),
        )
        return _fail_envelope((error,))

    actual_sha256 = hashlib.sha256(manual_path.read_bytes()).hexdigest()
    if actual_sha256 != manifest.checksum:
        error = _error(
            "V2_INTAKE_CHECKSUM_MISMATCH",
            f"Checksum mismatch for manual file: "
            f"expected {manifest.checksum}, computed {actual_sha256}",
            location=str(manual_path),
            details={"expected": manifest.checksum, "actual": actual_sha256},
        )
        return _fail_envelope((error,))

    summary = V2StagingSummary(
        source_name=manifest.source_name,
        intake_mode=manifest.intake_mode,
        status=STATUS_CHECKSUM_VERIFIED,
        source_url=manifest.source_url,
        manual_path=str(manual_path),
        output_root=str(output_root) if output_root else None,
        checksum=manifest.checksum,
        checksum_algorithm=manifest.checksum_algorithm,
        parser_target=manifest.parser_target,
        license_audit_ref=manifest.license_audit_ref,
    )
    return _ok_envelope(summary, input_sha256=manifest_sha256)


def _stage_download(
    manifest: V2DataIntakeManifest,
    allow_download: bool,
    output_root: Optional[Path],
    manifest_sha256: str,
) -> ContractEnvelope[V2StagingSummary]:
    if allow_download:
        error = _error(
            "V2_INTAKE_DOWNLOAD_NOT_AVAILABLE",
            "Network download is not available in Task 41; "
            "the downloader belongs to a later task",
        )
        return _fail_envelope((error,))

    download_request = None
    if manifest.source_url:
        intended_output_name = _intended_output_name(manifest)
        download_request = V2DownloadRequest(
            source_url=manifest.source_url,
            intended_output_name=intended_output_name,
            source_artifact_id=(
                f"{manifest.source_name}:{manifest.parser_target}:download_request"
            ),
            expected_checksum=manifest.checksum,
            checksum_algorithm=manifest.checksum_algorithm,
            retrieval_metadata_placeholder={
                "network_access": "not_performed_task41",
                "retrieval_status": "pending_approved_download",
            },
            license_audit_ref=manifest.license_audit_ref,
            retrieval_date=manifest.retrieval_date,
        )

    summary = V2StagingSummary(
        source_name=manifest.source_name,
        intake_mode=manifest.intake_mode,
        status=STATUS_PENDING_DOWNLOAD,
        source_url=manifest.source_url,
        output_root=str(output_root) if output_root else None,
        checksum=manifest.checksum,
        checksum_algorithm=manifest.checksum_algorithm,
        parser_target=manifest.parser_target,
        license_audit_ref=manifest.license_audit_ref,
        download_request=download_request,
    )
    return _ok_envelope(summary, input_sha256=manifest_sha256)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


def _ok_envelope(
    summary: V2StagingSummary,
    *,
    input_sha256: str,
) -> ContractEnvelope[V2StagingSummary]:
    return ContractEnvelope(
        payload=summary,
        artifacts=(),
        receipt=ValidationReceipt(
            validator=VALIDATOR_NAME,
            contract_version=V2_MANIFEST_CONTRACT_VERSION,
            input_sha256=input_sha256,
            ok=True,
        ),
        provenance=Provenance(),
    )


def _fail_envelope(
    errors: tuple[ContractErrorInfo, ...],
    *,
    input_sha256: str = "",
) -> ContractEnvelope[V2StagingSummary]:
    return ContractEnvelope(  # type: ignore[return-value]
        payload=None,
        artifacts=(),
        receipt=ValidationReceipt(
            validator=VALIDATOR_NAME,
            contract_version=V2_MANIFEST_CONTRACT_VERSION,
            input_sha256=input_sha256,
            ok=False,
            errors=errors,
        ),
        provenance=Provenance(),
    )


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _intended_output_name(manifest: V2DataIntakeManifest) -> str:
    if manifest.source_url:
        name = Path(urlparse(manifest.source_url).path).name
        if name:
            return name
    return f"{manifest.parser_target}_download_request.raw"


__all__ = [
    "STAGING_ROLE",
    "STATUS_CHECKSUM_VERIFIED",
    "STATUS_OK",
    "STATUS_PENDING_DOWNLOAD",
    "V2DownloadRequest",
    "V2StagingSummary",
    "serialize_v2_staging_summary",
    "stage_source_manifest",
    "v2_staging_summary_to_dict",
]
