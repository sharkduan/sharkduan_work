"""CLI for the Task 52 V2 tiny sweep tuning protocol."""

from __future__ import annotations

import argparse
import json

from covalent_design.contracts.errors import exit_code_for_error
from covalent_design.training.v2_tuning import run_v2_tune, v2_tuning_summary_to_dict


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the V2 tiny sweep tuning protocol.")
    parser.add_argument("--config", required=True, help="Path to a V2 tiny sweep YAML config.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    envelope = run_v2_tune(args.config)
    print(
        json.dumps(
            v2_tuning_summary_to_dict(envelope.payload),
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    if envelope.receipt.passed:
        return 0
    if envelope.receipt.errors:
        return exit_code_for_error(envelope.receipt.errors[0])
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
