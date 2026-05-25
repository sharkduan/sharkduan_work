"""CLI entry point for build_edge_candidates.

Usage:
    python -m covalent_design.candidates.cli.build_edge_candidates
        --records <records.jsonl> [--radius 4.0]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from covalent_design.candidates.edge_candidates import build_edge_candidates


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="build_edge_candidates",
        description="Build edge candidates from records with positive/negative edge enumeration.",
    )
    parser.add_argument(
        "--records",
        required=True,
        type=Path,
        help="Path to records.jsonl",
    )
    parser.add_argument(
        "--radius",
        type=float,
        default=4.0,
        help="Candidate radius in angstroms (default: 4.0)",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    records_path: Path = args.records
    if not records_path.exists():
        result = {
            "ok": False,
            "errors": [
                {
                    "code": "CLI_RECORDS_FILE_NOT_FOUND",
                    "message": f"Records file not found: {records_path}",
                }
            ],
            "edge_candidate_count": 0,
        }
        json.dump(result, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return 2

    envelope = build_edge_candidates(records_path, candidate_radius_angstrom=args.radius)

    if envelope.receipt.ok:
        result: dict = {
            "ok": True,
            "edge_candidate_count": envelope.payload.get("edge_candidate_count", 0),
            "record_count": envelope.payload.get("record_count", 0),
            "radius_angstrom": envelope.payload.get("radius_angstrom", args.radius),
        }
    else:
        errors_list = [
            {
                "code": e.code,
                "owner": e.owner,
                "message": e.message,
                "location": e.location,
                "details": dict(e.details),
            }
            for e in envelope.receipt.errors
        ]
        result = {
            "ok": False,
            "errors": errors_list,
            "edge_candidate_count": envelope.payload.get("edge_candidate_count", 0),
        }

    json.dump(result, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0 if envelope.receipt.ok else 10


if __name__ == "__main__":
    sys.exit(main())
