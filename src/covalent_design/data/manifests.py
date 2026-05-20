from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from covalent_design.contracts import (
    CONTRACT_VERSION,
    ArtifactRef,
    ContractEnvelope,
    ContractErrorInfo,
    ValidationReceipt,
)
from covalent_design.io.artifacts import artifact_ref_from_file, sha256_file


VALIDATOR_NAME = "covalent_design.data.validate_raw_manifests"
MANIFEST_NAME = "manifest.json"


@dataclass(frozen=True)
class RawManifestFile:
    source_database: str
    path: str
    role: str
    bytes: int
    sha256: str


@dataclass(frozen=True)
class RawSourceManifest:
    source_database: str
    source_version: str
    retrieval_date: str
    license: str
    access_notes: str
    complete_for_v1: bool
    manifest_path: str
    files: tuple[RawManifestFile, ...]


@dataclass(frozen=True)
class RawSourceInventory:
    raw_root: str
    manifests: tuple[RawSourceManifest, ...]
    extra_files: tuple[str, ...]

    @property
    def source_count(self) -> int:
        return len(self.manifests)

    @property
    def file_count(self) -> int:
        return sum(len(manifest.files) for manifest in self.manifests)


def validate_raw_manifests(raw_root: Path) -> ContractEnvelope[RawSourceInventory]:
    raw_root = raw_root.resolve()
    errors: list[ContractErrorInfo] = []
    artifacts: list[ArtifactRef] = []
    manifests: list[RawSourceManifest] = []
    manifest_declared_files: set[Path] = set()
    manifest_paths: set[Path] = set()

    if not raw_root.exists():
        errors.append(
            ContractErrorInfo(
                code="RAW_ROOT_NOT_FOUND",
                owner="data",
                message=f"Raw root does not exist: {raw_root}",
                location=str(raw_root),
            )
        )
        inventory = RawSourceInventory(str(raw_root), (), ())
        return _envelope(raw_root, inventory, artifacts, errors)

    for manifest_path in sorted(raw_root.glob(f"*/{MANIFEST_NAME}")):
        manifest_paths.add(manifest_path.resolve())
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(
                ContractErrorInfo(
                    code="RAW_MANIFEST_INVALID_JSON",
                    owner="data",
                    message=str(exc),
                    location=_display_path(manifest_path, raw_root),
                )
            )
            continue
        if not isinstance(payload, dict):
            errors.append(
                ContractErrorInfo(
                    code="RAW_MANIFEST_ROOT_NOT_OBJECT",
                    owner="data",
                    message="Raw manifest root must be a JSON object",
                    location=_display_path(manifest_path, raw_root),
                )
            )
            continue

        source_manifest = _parse_manifest(manifest_path, raw_root, payload, errors)
        if source_manifest is None:
            continue

        artifacts.append(artifact_ref_from_file(manifest_path, role="raw_manifest", root=raw_root))
        manifests.append(source_manifest)
        for file_entry in source_manifest.files:
            declared_path = (manifest_path.parent / file_entry.path).resolve()
            manifest_declared_files.add(declared_path)
            _validate_declared_file(declared_path, raw_root, file_entry, errors)

    all_raw_files = {
        path.resolve()
        for path in raw_root.rglob("*")
        if path.is_file() and ".git" not in path.parts
    }
    extra_files = tuple(
        sorted(
            _display_path(path, raw_root)
            for path in all_raw_files
            if path not in manifest_declared_files and path not in manifest_paths
        )
    )

    inventory = RawSourceInventory(
        raw_root=str(raw_root),
        manifests=tuple(manifests),
        extra_files=extra_files,
    )
    return _envelope(raw_root, inventory, artifacts, errors)


def _parse_manifest(
    manifest_path: Path,
    raw_root: Path,
    payload: dict[str, Any],
    errors: list[ContractErrorInfo],
) -> RawSourceManifest | None:
    required = (
        "source_database",
        "source_version",
        "retrieval_date",
        "license",
        "access_notes",
        "complete_for_v1",
        "files",
    )
    missing = [field for field in required if payload.get(field) in (None, "")]
    if missing:
        errors.append(
            ContractErrorInfo(
                code="RAW_MANIFEST_MISSING_REQUIRED_FIELD",
                owner="data",
                message=f"Missing required manifest fields: {', '.join(missing)}",
                location=_display_path(manifest_path, raw_root),
            )
        )
        return None

    if not isinstance(payload["complete_for_v1"], bool):
        errors.append(
            ContractErrorInfo(
                code="RAW_MANIFEST_COMPLETE_FOR_V1_INVALID",
                owner="data",
                message="complete_for_v1 must be a JSON boolean",
                location=_display_path(manifest_path, raw_root),
            )
        )
        return None

    file_entries = payload["files"]
    if not isinstance(file_entries, list):
        errors.append(
            ContractErrorInfo(
                code="RAW_MANIFEST_FILES_NOT_LIST",
                owner="data",
                message="Manifest files field must be a list",
                location=_display_path(manifest_path, raw_root),
            )
        )
        return None

    files: list[RawManifestFile] = []
    for index, entry in enumerate(file_entries):
        if not isinstance(entry, dict):
            errors.append(
                ContractErrorInfo(
                    code="RAW_MANIFEST_FILE_ENTRY_INVALID",
                    owner="data",
                    message="Manifest file entry must be an object",
                    location=f"{_display_path(manifest_path, raw_root)}:files[{index}]",
                )
            )
            continue
        parsed = _parse_file_entry(str(payload["source_database"]), manifest_path, raw_root, index, entry, errors)
        if parsed is not None:
            files.append(parsed)

    return RawSourceManifest(
        source_database=str(payload["source_database"]),
        source_version=str(payload["source_version"]),
        retrieval_date=str(payload["retrieval_date"]),
        license=str(payload["license"]),
        access_notes=str(payload["access_notes"]),
        complete_for_v1=bool(payload["complete_for_v1"]),
        manifest_path=_display_path(manifest_path, raw_root),
        files=tuple(files),
    )


def _parse_file_entry(
    source_database: str,
    manifest_path: Path,
    raw_root: Path,
    index: int,
    entry: dict[str, Any],
    errors: list[ContractErrorInfo],
) -> RawManifestFile | None:
    required = ("path", "role", "bytes", "sha256")
    missing = [field for field in required if entry.get(field) in (None, "")]
    location = f"{_display_path(manifest_path, raw_root)}:files[{index}]"
    if missing:
        errors.append(
            ContractErrorInfo(
                code="RAW_MANIFEST_FILE_MISSING_REQUIRED_FIELD",
                owner="data",
                message=f"Missing required file fields: {', '.join(missing)}",
                location=location,
            )
        )
        return None

    path = str(entry["path"])
    if Path(path).is_absolute() or ".." in Path(path).parts:
        errors.append(
            ContractErrorInfo(
                code="RAW_MANIFEST_FILE_PATH_UNSAFE",
                owner="data",
                message="Manifest file paths must be relative and stay inside the source root",
                location=location,
            )
        )
        return None

    byte_count = entry["bytes"]
    if not isinstance(byte_count, int) or isinstance(byte_count, bool) or byte_count < 0:
        errors.append(
            ContractErrorInfo(
                code="RAW_MANIFEST_FILE_BYTES_INVALID",
                owner="data",
                message="Manifest file bytes must be a non-negative integer",
                location=location,
            )
        )
        return None

    return RawManifestFile(
        source_database=source_database,
        path=path,
        role=str(entry["role"]),
        bytes=byte_count,
        sha256=str(entry["sha256"]),
    )


def _validate_declared_file(
    path: Path,
    raw_root: Path,
    entry: RawManifestFile,
    errors: list[ContractErrorInfo],
) -> None:
    display = _display_path(path, raw_root)
    if not path.exists():
        errors.append(
            ContractErrorInfo(
                code="RAW_MANIFEST_FILE_NOT_FOUND",
                owner="data",
                message=f"Manifested file does not exist: {display}",
                location=display,
            )
        )
        return

    actual_bytes = path.stat().st_size
    if actual_bytes != entry.bytes:
        errors.append(
            ContractErrorInfo(
                code="RAW_MANIFEST_BYTE_COUNT_MISMATCH",
                owner="data",
                message=f"Expected {entry.bytes} bytes but found {actual_bytes}",
                location=display,
            )
        )

    actual_sha256 = sha256_file(path)
    if actual_sha256 != entry.sha256:
        errors.append(
            ContractErrorInfo(
                code="RAW_MANIFEST_CHECKSUM_MISMATCH",
                owner="data",
                message=f"Expected sha256 {entry.sha256} but found {actual_sha256}",
                location=display,
            )
        )


def _envelope(
    raw_root: Path,
    inventory: RawSourceInventory,
    artifacts: list[ArtifactRef],
    errors: list[ContractErrorInfo],
) -> ContractEnvelope[RawSourceInventory]:
    return ContractEnvelope(
        payload=inventory,
        artifacts=tuple(artifacts),
        receipt=ValidationReceipt(
            validator=VALIDATOR_NAME,
            contract_version=CONTRACT_VERSION,
            input_sha256=_inventory_hash(inventory),
            ok=not errors,
            errors=tuple(errors),
        ),
    )


def _inventory_hash(inventory: RawSourceInventory) -> str:
    payload = json.dumps(inventory, default=lambda value: value.__dict__, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _display_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)
