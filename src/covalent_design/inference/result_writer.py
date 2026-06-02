"""Task 28 ResultWriter — validates and serializes CovalentGenerationResult rows."""

from __future__ import annotations

from covalent_design.contracts import ContractError, validate_generation_result
from covalent_design.contracts.types import CovalentGenerationResult
from covalent_design.inference.result_schema import _result_to_dict


class ResultWriter:
    """Stateless, reusable writer that validates then serializes generation results.

    Usage::

        writer = ResultWriter()
        row = writer.write(result)
    """

    def write(self, result: CovalentGenerationResult) -> dict[str, object]:
        """Validate *result* and return a JSON-compatible row dict.

        Raises ``ContractError`` if generation-result contract validation
        fails, preserving the first receipt error's code, owner, message,
        location, and details.
        """
        if not isinstance(result, CovalentGenerationResult):
            raise TypeError(
                f"result must be a CovalentGenerationResult, "
                f"got {type(result).__name__}"
            )
        receipt = validate_generation_result(result)
        if not receipt.passed:
            err = receipt.errors[0]
            raise ContractError(
                code=err.code,
                owner=err.owner,
                message=err.message,
                location=err.location,
                details=err.details,
            )
        return _result_to_dict(result)
