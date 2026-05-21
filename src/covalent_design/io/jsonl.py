from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Mapping

from covalent_design.contracts.types import CONTRACT_VERSION, SCHEMA_VERSION, ArtifactRef
from covalent_design.io.artifacts import artifact_ref_from_file


def write_jsonl(
    path: Path,
    rows: Iterable[Mapping[str, object]],
    *,
    role: str,
    schema_version: str = SCHEMA_VERSION,
    contract_version: str = CONTRACT_VERSION,
) -> ArtifactRef:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            payload = dict(row)
            payload.setdefault("schema_version", schema_version)
            payload.setdefault("contract_version", contract_version)
            handle.write(json.dumps(payload, sort_keys=True, separators=(",", ":")))
            handle.write("\n")
    return artifact_ref_from_file(path, role=role, schema_version=schema_version, format="jsonl")


def read_jsonl(
    path: Path,
    *,
    require_versions: bool = True,
    expected_schema_version: str | None = None,
    expected_contract_version: str | None = None,
) -> tuple[dict[str, object], ...]:
    rows: list[dict[str, object]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"JSONL_INVALID_JSON at line {line_number}: {exc}") from exc
            if not isinstance(payload, dict):
                raise ValueError(f"JSONL_ROW_NOT_OBJECT at line {line_number}")
            if require_versions:
                if "schema_version" not in payload:
                    raise ValueError(f"JSONL_SCHEMA_VERSION_MISSING at line {line_number}")
                if "contract_version" not in payload:
                    raise ValueError(f"JSONL_CONTRACT_VERSION_MISSING at line {line_number}")
            if expected_schema_version is not None:
                if "schema_version" not in payload:
                    raise ValueError(f"JSONL_SCHEMA_VERSION_MISSING at line {line_number}")
                if payload["schema_version"] != expected_schema_version:
                    raise ValueError(
                        "JSONL_SCHEMA_VERSION_UNSUPPORTED "
                        f"at line {line_number}: expected {expected_schema_version!r}, "
                        f"found {payload['schema_version']!r}"
                    )
            if expected_contract_version is not None:
                if "contract_version" not in payload:
                    raise ValueError(f"JSONL_CONTRACT_VERSION_MISSING at line {line_number}")
                if payload["contract_version"] != expected_contract_version:
                    raise ValueError(
                        "JSONL_CONTRACT_VERSION_UNSUPPORTED "
                        f"at line {line_number}: expected {expected_contract_version!r}, "
                        f"found {payload['contract_version']!r}"
                    )
            rows.append(payload)
    return tuple(rows)
