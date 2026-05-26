"""CLI entry-point for export_visual_checks.

Usage:
  python -m covalent_design.viz.cli.export_visual_checks \
    --records <records.jsonl> \
    --out-root <out_root> \
    [--sample-count N] \
    [--seed 42]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from covalent_design.contracts import CONTRACT_VERSION, exit_code_for_error
from covalent_design.viz.visual_checks import export_visual_checks


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m covalent_design.viz.cli.export_visual_checks",
        description="Export visual check artifacts for sampled records.",
    )
    parser.add_argument(
        "--records",
        required=True,
        type=Path,
        help="Path to records JSONL file.",
    )
    parser.add_argument(
        "--out-root",
        required=True,
        type=Path,
        help="Directory to write visual check artifacts.",
    )
    parser.add_argument(
        "--sample-count",
        type=int,
        default=None,
        help="Number of records to sample (default: all).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for deterministic sampling (default: 42).",
    )
    return parser


def _run(argv: Optional[list[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    envelope = export_visual_checks(
        records_path=args.records,
        out_root=args.out_root,
        sample_count=args.sample_count,
        seed=args.seed,
    )

    summary = {
        "schema_version": "1",
        "contract_version": CONTRACT_VERSION,
        "role": "export_visual_checks_summary",
        "ok": envelope.receipt.ok,
        "sampled_count": envelope.payload.get("sampled_count", 0),
        "errors": [
            {"code": e.code, "message": e.message}
            for e in envelope.receipt.errors
        ],
    }
    json.dump(summary, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")

    if not envelope.receipt.ok:
        for error in envelope.receipt.errors:
            return exit_code_for_error(error)
        return 10
    return 0


if __name__ == "__main__":
    sys.exit(_run())
