from __future__ import annotations

import hashlib
from pathlib import Path

from covalent_design.contracts import ArtifactRef


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def artifact_ref_from_file(path: Path, *, role: str, root: Path | None = None) -> ArtifactRef:
    base = root if root is not None else path.parent
    uri = path.relative_to(base).as_posix()
    return ArtifactRef(
        uri=uri,
        sha256=sha256_file(path),
        format=path.suffix.lstrip(".") or "binary",
        bytes=path.stat().st_size,
        role=role,
    )

