"""CLI entry point for Task 17 model batch inspection.

Usage::

    python -m covalent_design.model.inspect_batch --records <records.jsonl> [--record-id <id>]
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Optional


def main(argv: Optional[list[str]] = None) -> None:
    parser = argparse.ArgumentParser(
        prog="python -m covalent_design.model.inspect_batch",
        description="Inspect model batch records with per-record error reporting.",
    )
    parser.add_argument(
        "--records", required=True,
        help="Path to records.jsonl",
    )
    parser.add_argument(
        "--record-id", default=None,
        help="Optional record ID to filter output to a single record",
    )
    args = parser.parse_args(argv)

    from covalent_design.model.inspect import inspect_batch

    report = inspect_batch(args.records, record_id=args.record_id)

    json.dump(report, sys.stdout, sort_keys=True, default=str)
    sys.stdout.write("\n")

    # Exit non-zero if any error was detected
    if not report.get("passed", True):
        sys.exit(1)


if __name__ == "__main__":
    main()
