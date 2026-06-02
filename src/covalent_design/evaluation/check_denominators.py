"""check_denominators CLI - validate EvaluationSummary conservation equations.

Usage::

    python -m covalent_design.evaluation.check_denominators --manifest <run_manifest.yml>

Recomputes the EvaluationSummary from the manifest and prints the
validation receipt as deterministic JSON.  Does not write any files.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> None:
    manifest_path = _parse_manifest_arg(sys.argv[1:])
    try:
        from covalent_design.evaluation.denominator_accounting import (
            check_denominators as _impl,
            summarize_results,
        )

        receipt = _impl(summarize_results(manifest_path))
        print(_receipt_json(receipt))
    except Exception as exc:
        _handle_error(exc)


def _receipt_json(receipt) -> str:
    from covalent_design.contracts.receipts import receipt_to_dict

    return json.dumps(
        receipt_to_dict(receipt), indent=2, sort_keys=True, ensure_ascii=False
    )


def _parse_manifest_arg(argv: list[str]) -> Path:
    parser = argparse.ArgumentParser(
        description="Validate EvaluationSummary conservation equations for a generation run."
    )
    parser.add_argument("--manifest", required=True, type=Path)
    return parser.parse_args(argv).manifest


def _handle_error(exc: Exception) -> None:
    from covalent_design.contracts.errors import ContractError, exit_code_for_error

    if isinstance(exc, ContractError):
        payload = {
            "error": exc.code,
            "owner": exc.owner,
            "message": exc.message,
        }
        if exc.location:
            payload["location"] = exc.location
        if exc.details:
            payload["details"] = dict(exc.details)
        print(json.dumps(payload, sort_keys=True), file=sys.stderr)
        sys.exit(exit_code_for_error(exc))

    print(
        json.dumps(
            {"error": "RUNTIME_ERROR", "message": str(exc)}, sort_keys=True
        ),
        file=sys.stderr,
    )
    sys.exit(1)


if __name__ == "__main__":
    main()
