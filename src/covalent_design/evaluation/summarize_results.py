"""summarize_results CLI - compute and write EvaluationSummary from a run manifest.

Usage::

    python -m covalent_design.evaluation.summarize_results --manifest <run_manifest.yml>

Writes ``evaluation_summary.json`` to the manifest parent directory
and prints the summary as deterministic JSON to stdout.
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
            summarize_results as _impl,
            write_evaluation_summary,
        )

        summary = _impl(manifest_path)
        write_evaluation_summary(summary, manifest_path.parent / "evaluation_summary.json")
        payload = _summary_to_dict(summary)
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
    except Exception as exc:
        _handle_error(exc)


def _summary_to_dict(summary) -> dict[str, object]:
    from covalent_design.evaluation.denominator_accounting import evaluation_summary_to_dict

    return evaluation_summary_to_dict(summary)


def _parse_manifest_arg(argv: list[str]) -> Path:
    parser = argparse.ArgumentParser(
        description="Compute and write an EvaluationSummary from a generation run manifest."
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

    # unexpected errors
    print(
        json.dumps(
            {"error": "RUNTIME_ERROR", "message": str(exc)}, sort_keys=True
        ),
        file=sys.stderr,
    )
    sys.exit(1)


if __name__ == "__main__":
    main()
