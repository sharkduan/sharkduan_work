from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Union

from covalent_design.contracts.errors import (
    CLI_EXIT_CODES,
    ContractError,
    ContractErrorInfo,
    exit_code_for_error,
)
from covalent_design.contracts.types import CONTRACT_VERSION, SCHEMA_VERSION


def exit_code_for_exception(exc: BaseException) -> int:
    if isinstance(exc, (ContractError, ContractErrorInfo)):
        return exit_code_for_error(exc)
    return CLI_EXIT_CODES["runtime_error"]


def to_cli_error_json(
    *,
    code: str,
    owner: str,
    message: str,
    exit_code: int,
    location: Optional[str] = None,
    details: Optional[dict[str, object]] = None,
) -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "contract_version": CONTRACT_VERSION,
        "role": "cli_error",
        "ok": False,
        "exit_code": exit_code,
        "error": {
            "code": code,
            "owner": owner,
            "message": message,
            "location": location,
            "details": details or {},
        },
    }


def contract_error_to_cli_json(
    error: Union[ContractError, ContractErrorInfo],
) -> dict[str, object]:
    return to_cli_error_json(
        code=error.code,
        owner=error.owner,
        message=error.message,
        exit_code=exit_code_for_error(error),
        location=error.location,
        details=error.details,
    )


def exception_to_cli_json(exc: BaseException) -> dict[str, object]:
    if isinstance(exc, (ContractError, ContractErrorInfo)):
        return contract_error_to_cli_json(exc)
    return to_cli_error_json(
        code="RUNTIME_ERROR",
        owner="system",
        message=str(exc) or type(exc).__name__,
        exit_code=CLI_EXIT_CODES["runtime_error"],
    )


def write_cli_error_json(
    error_json: dict[str, object],
    path: Union[str, Path],
) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(error_json, indent=2, sort_keys=True, ensure_ascii=False),
        encoding="utf-8",
    )
