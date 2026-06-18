"""CLI entry point for ``python -m covalent_design.data.cli.v2_stage_source``."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List, Optional

from covalent_design.contracts.errors import exit_code_for_error
from covalent_design.data.v2_intake import (
    stage_source_manifest,
    v2_staging_summary_to_dict,
)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="covalent_design.data.cli.v2_stage_source",
        description="Stage a V2 data intake source manifest.",
    )
    parser.add_argument(
        "--manifest",
        required=True,
        type=Path,
        help="Path to the V2 data intake manifest JSON file",
    )
    parser.add_argument(
        "--allow-download",
        action="store_true",
        default=False,
        help="Request network download (not available in Task 41)",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=None,
        help="Optional output root directory for staged files",
    )
    args = parser.parse_args(argv)

    envelope = stage_source_manifest(
        args.manifest,
        allow_download=args.allow_download,
        output_root=args.output_root,
    )

    if envelope.receipt.ok and envelope.payload is not None:
        output = v2_staging_summary_to_dict(envelope.payload)
        output["ok"] = True
        print(json.dumps(output, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
        return 0
    else:
        errors = [
            {
                "code": e.code,
                "owner": e.owner,
                "message": e.message,
                "location": e.location,
                "details": e.details,
            }
            for e in envelope.receipt.errors
        ]
        output: dict[str, object] = {
            "ok": False,
            "errors": errors,
        }
        print(json.dumps(output, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
        if envelope.receipt.errors:
            return exit_code_for_error(envelope.receipt.errors[0])
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
