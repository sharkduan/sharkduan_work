"""CLI entry point for ``finalize_record_manifests``."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List, Optional

from covalent_design.contracts.errors import exit_code_for_error
from covalent_design.data.artifact_manifests import finalize_record_manifests


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="covalent_design.data.cli.finalize_record_manifests",
        description="Append edge-candidate artifact refs to accepted records.",
    )
    parser.add_argument(
        "--records",
        required=True,
        type=Path,
        help="Path to records.jsonl",
    )
    args = parser.parse_args(argv)

    envelope = finalize_record_manifests(args.records)

    summary = {
        "ok": envelope.receipt.ok,
        "record_count": envelope.payload.get("record_count", 0),
        "edge_candidate_count": envelope.payload.get("edge_candidate_count", 0),
        "errors": [
            {"code": e.code, "message": e.message, "location": e.location}
            for e in envelope.receipt.errors
        ],
    }
    print(json.dumps(summary, sort_keys=True, separators=(",", ":")))

    if not envelope.receipt.ok:
        if envelope.receipt.errors:
            return exit_code_for_error(envelope.receipt.errors[0])
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
