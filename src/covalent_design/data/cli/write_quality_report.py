"""CLI entry point: python -m covalent_design.data.cli.write_quality_report

Writes an ETL quality report that reconciles sources, records, candidates,
splits, and visual checks into a single JSON envelope.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from covalent_design.contracts.errors import exit_code_for_error
from covalent_design.data.quality_report import write_quality_report


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Write ETL quality report reconciling sources, records, candidates, splits, and visual checks.",
    )
    parser.add_argument(
        "--processed-root",
        required=True,
        type=Path,
        help="Path to the processed root containing records.jsonl, rejected_index.jsonl, conflict_index.jsonl, and artifacts/.",
    )
    parser.add_argument(
        "--ingest-roots",
        action="append",
        type=Path,
        default=None,
        help="Path to an ingest source root containing ingest_index.json. May be repeated.",
    )
    parser.add_argument(
        "--splits-root",
        type=Path,
        default=None,
        help="Path to the splits root containing split_index.json.",
    )
    parser.add_argument(
        "--visual-checks-root",
        type=Path,
        default=None,
        help="Path to the visual checks root containing visual_check_index.json.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        dest="out_path",
        help="Path to write the quality report JSON file.",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)

    envelope = write_quality_report(
        processed_root=args.processed_root,
        ingest_roots=args.ingest_roots,
        splits_root=args.splits_root,
        visual_checks_root=args.visual_checks_root,
        out_path=args.out_path,
    )

    summary = {
        "ok": envelope.receipt.ok,
        "errors": [{"code": e.code, "message": e.message} for e in envelope.receipt.errors],
    }
    print(json.dumps(summary, sort_keys=True, separators=(",", ":")))

    if not envelope.receipt.ok:
        sys.exit(exit_code_for_error(envelope.receipt.errors[0]))
    sys.exit(0)


if __name__ == "__main__":
    main()
