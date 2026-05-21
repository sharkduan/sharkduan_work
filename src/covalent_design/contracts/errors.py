from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Mapping, Optional, Union


ContractOwner = Literal[
    "request",
    "data",
    "rules",
    "model",
    "training",
    "inference",
    "evaluation",
    "system",
]


@dataclass(frozen=True)
class ContractErrorInfo:
    code: str
    owner: ContractOwner
    message: str
    location: Optional[str] = None
    details: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ContractError(Exception):
    code: str
    owner: ContractOwner
    message: str
    location: Optional[str] = None
    details: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        Exception.__init__(self, f"{self.code}: {self.message}")

    def to_info(self) -> ContractErrorInfo:
        return ContractErrorInfo(
            code=self.code,
            owner=self.owner,
            message=self.message,
            location=self.location,
            details=self.details,
        )


CLI_EXIT_CODES: Mapping[str, int] = {
    "success": 0,
    "runtime_error": 1,
    "cli_argument_error": 2,
    "contract_validation_failed": 10,
    "artifact_missing_or_checksum_mismatch": 11,
    "denominator_conservation_failed": 12,
    "request_validation_failed": 20,
    "data_quality_gate_failed": 30,
    "model_or_training_contract_violation": 40,
    "sampling_system_failure_exceeded_policy": 50,
    "docking_protocol_invalid_or_not_evaluable": 60,
    "unsupported_version_or_incompatible_artifact": 70,
}


def exit_code_for_error(error: Union[ContractError, ContractErrorInfo]) -> int:
    if error.owner == "request" or error.code.startswith("REQUEST_"):
        return CLI_EXIT_CODES["request_validation_failed"]
    if "DENOMINATOR" in error.code or "CONSERVATION" in error.code:
        return CLI_EXIT_CODES["denominator_conservation_failed"]
    if "ARTIFACT" in error.code or "CHECKSUM" in error.code:
        return CLI_EXIT_CODES["artifact_missing_or_checksum_mismatch"]
    if error.owner == "data":
        return CLI_EXIT_CODES["data_quality_gate_failed"]
    if error.owner in ("model", "training"):
        return CLI_EXIT_CODES["model_or_training_contract_violation"]
    if error.owner == "evaluation" and "DOCKING" in error.code:
        return CLI_EXIT_CODES["docking_protocol_invalid_or_not_evaluable"]
    if "VERSION" in error.code:
        return CLI_EXIT_CODES["unsupported_version_or_incompatible_artifact"]
    return CLI_EXIT_CODES["contract_validation_failed"]
