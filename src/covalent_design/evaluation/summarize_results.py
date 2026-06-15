"""summarize_results CLI - compute and write EvaluationSummary from a run manifest.

Usage::

    python -m covalent_design.evaluation.summarize_results --manifest <run_manifest.yml>
    python -m covalent_design.evaluation.summarize_results --manifest <run_manifest.yml> --error-out <path>

Writes ``evaluation_summary.json`` to the manifest parent directory
and prints the summary as deterministic JSON to stdout.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional


def main() -> None:
    args = _parse_args(sys.argv[1:])
    try:
        from covalent_design.evaluation.denominator_accounting import (
            summarize_results as _impl,
            write_evaluation_summary,
        )

        summary = _impl(args.manifest)
        write_evaluation_summary(summary, args.manifest.parent / "evaluation_summary.json")
        payload = _summary_to_dict(summary)
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
    except Exception as exc:
        _handle_error(exc, args.error_out)


def _summary_to_dict(summary) -> dict[str, object]:
    from covalent_design.evaluation.denominator_accounting import evaluation_summary_to_dict

    return evaluation_summary_to_dict(summary)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compute and write an EvaluationSummary from a generation run manifest."
    )
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument(
        "--error-out",
        type=Path,
        default=None,
        dest="error_out",
        help="Path to write cli_error JSON on failure.",
    )
    return parser.parse_args(argv)


def _handle_error(exc: Exception, error_out: Optional[Path] = None) -> None:
    from covalent_design.contracts.cli_errors import (
        contract_error_to_cli_json,
        exception_to_cli_json,
        write_cli_error_json,
    )
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

        if error_out is not None:
            write_cli_error_json(contract_error_to_cli_json(exc), error_out)

        sys.exit(exit_code_for_error(exc))

    # unexpected errors
    print(
        json.dumps(
            {"error": "RUNTIME_ERROR", "message": str(exc)}, sort_keys=True
        ),
        file=sys.stderr,
    )

    if error_out is not None:
        write_cli_error_json(exception_to_cli_json(exc), error_out)

    sys.exit(1)


if __name__ == "__main__":
    main()
