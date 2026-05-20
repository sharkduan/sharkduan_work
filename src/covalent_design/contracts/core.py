from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Literal, TypeVar


CONTRACT_VERSION = "0.1.0"

ContractOwner = Literal[
    "request",
    "data",
    "rules",
    "model",
    "training",
    "inference",
    "evaluation",
    "io",
]


@dataclass(frozen=True)
class ContractErrorInfo:
    code: str
    owner: ContractOwner
    message: str
    location: str | None = None


@dataclass(frozen=True)
class ContractError(Exception):
    code: str
    owner: ContractOwner
    message: str
    location: str | None = None

    def to_info(self) -> ContractErrorInfo:
        return ContractErrorInfo(
            code=self.code,
            owner=self.owner,
            message=self.message,
            location=self.location,
        )


@dataclass(frozen=True)
class ArtifactRef:
    uri: str
    sha256: str
    format: str
    bytes: int
    role: str


@dataclass(frozen=True)
class ValidationReceipt:
    validator: str
    contract_version: str
    input_sha256: str
    ok: bool
    errors: tuple[ContractErrorInfo, ...] = ()
    warnings: tuple[ContractErrorInfo, ...] = ()


T = TypeVar("T")


@dataclass(frozen=True)
class ContractEnvelope(Generic[T]):
    payload: T
    artifacts: tuple[ArtifactRef, ...]
    receipt: ValidationReceipt

