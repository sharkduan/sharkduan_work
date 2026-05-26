"""CLI entry-point for build_splits.

Usage:
  python -m covalent_design.data.cli.build_splits \
    --records <records.jsonl> \
    --policy <policy.json> \
    --out-root <out_root>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from covalent_design.contracts import CONTRACT_VERSION
from covalent_design.data.splits import SplitPolicy, build_splits


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m covalent_design.data.cli.build_splits",
        description="Build leakage-aware covalent train/val/test splits.",
    )
    parser.add_argument(
        "--records",
        required=True,
        type=Path,
        help="Path to accepted records JSONL file.",
    )
    parser.add_argument(
        "--policy",
        type=Path,
        default=None,
        help="Optional path to split policy JSON.",
    )
    parser.add_argument(
        "--out-root",
        required=True,
        type=Path,
        help="Directory to write split artifacts.",
    )
    return parser


def _run(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    policy = None
    if args.policy:
        policy = SplitPolicy.from_json_path(args.policy)

    envelope = build_splits(
        records_path=args.records,
        out_root=args.out_root,
        policy=policy,
    )

    # JSON summary to stdout.
    summary = {
        "schema_version": "1",
        "contract_version": CONTRACT_VERSION,
        "role": "build_splits_summary",
        "ok": envelope.receipt.ok,
        "assignment_count": len(envelope.payload) if envelope.payload else 0,
        "errors": [
            {"code": e.code, "message": e.message}
            for e in envelope.receipt.errors
        ],
    }
    json.dump(summary, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")

    if not envelope.receipt.ok:
        return 10  # contract_validation_failed
    return 0


if __name__ == "__main__":
    sys.exit(_run())
