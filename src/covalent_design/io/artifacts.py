from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Optional

from covalent_design.contracts.errors import ContractErrorInfo
from covalent_design.contracts.types import (
    CONTRACT_VERSION,
    SCHEMA_VERSION,
    ArtifactRef,
    ValidationReceipt,
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


ARTIFACT_VALIDATOR = "covalent_design.io.validate_artifact_ref"


def artifact_ref_from_file(
    path: Path,
    *,
    role: str,
    root: Optional[Path] = None,
    schema_version: str = SCHEMA_VERSION,
    format: Optional[str] = None,
) -> ArtifactRef:
    base = root if root is not None else path.parent
    uri = path.relative_to(base).as_posix()
    return ArtifactRef(
        uri=uri,
        sha256=sha256_file(path),
        format=format or path.suffix.lstrip(".") or "binary",
        schema_version=schema_version,
        bytes=path.stat().st_size,
        role=role,
    )


def validate_artifact_ref(ref: ArtifactRef, *, root: Optional[Path] = None) -> ValidationReceipt:
    errors: list[ContractErrorInfo] = []
    try:
        path = resolve_artifact_path(ref, root=root)
    except ValueError as exc:
        errors.append(
            ContractErrorInfo(
                code="ARTIFACT_URI_INVALID",
                owner="data",
                message=str(exc),
                location=ref.uri,
            )
        )
        return _receipt(ref, errors)

    if not path.exists():
        errors.append(
            ContractErrorInfo(
                code="ARTIFACT_NOT_FOUND",
                owner="data",
                message=f"Artifact does not exist: {ref.uri}",
                location=ref.uri,
            )
        )
        return _receipt(ref, errors)

    actual_bytes = path.stat().st_size
    if ref.bytes is not None and actual_bytes != ref.bytes:
        errors.append(
            ContractErrorInfo(
                code="ARTIFACT_BYTE_COUNT_MISMATCH",
                owner="data",
                message=f"Expected {ref.bytes} bytes but found {actual_bytes}",
                location=ref.uri,
            )
        )

    actual_sha256 = sha256_file(path)
    if actual_sha256 != ref.sha256:
        errors.append(
            ContractErrorInfo(
                code="ARTIFACT_CHECKSUM_MISMATCH",
                owner="data",
                message=f"Expected sha256 {ref.sha256} but found {actual_sha256}",
                location=ref.uri,
            )
        )

    return _receipt(ref, errors)


def resolve_artifact_path(ref: ArtifactRef, *, root: Optional[Path] = None) -> Path:
    uri_path = Path(ref.uri)
    if uri_path.is_absolute():
        raise ValueError("Artifact URI must be relative to the artifact root")
    if ".." in uri_path.parts:
        raise ValueError("Artifact URI must not escape the artifact root")
    if root is None:
        return uri_path
    resolved_root = root.resolve()
    resolved_path = (resolved_root / uri_path).resolve()
    try:
        resolved_path.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError("Artifact URI must stay inside the artifact root") from exc
    return resolved_path


def _receipt(ref: ArtifactRef, errors: list[ContractErrorInfo]) -> ValidationReceipt:
    return ValidationReceipt(
        validator=ARTIFACT_VALIDATOR,
        contract_version=CONTRACT_VERSION,
        input_sha256=ref.sha256,
        passed=not errors,
        errors=tuple(errors),
    )
