"""CLI wrapper for Task 10 record index construction."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from covalent_design.contracts.errors import exit_code_for_error
from covalent_design.data.records import RECORDS_VALIDATOR, build_record_index


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build covalent record indexes.")
    parser.add_argument("--processed-root", type=Path, required=True)
    args = parser.parse_args(argv)

    envelope = build_record_index(args.processed_root)
    summary = {
        "ok": envelope.receipt.ok,
        "validator": RECORDS_VALIDATOR,
        "contract_version": envelope.receipt.contract_version,
        "record_count": envelope.payload.get("record_count", 0)
        if isinstance(envelope.payload, dict)
        else 0,
        "rejected_count": envelope.payload.get("rejected_count", 0)
        if isinstance(envelope.payload, dict)
        else 0,
        "conflict_count": envelope.payload.get("conflict_count", 0)
        if isinstance(envelope.payload, dict)
        else 0,
        "artifacts": [asdict(ref) for ref in envelope.artifacts],
        "errors": [asdict(error) for error in envelope.receipt.errors],
        "warnings": [asdict(warning) for warning in envelope.receipt.warnings],
    }
    print(json.dumps(summary, sort_keys=True))
    if envelope.receipt.ok:
        return 0
    if envelope.receipt.errors:
        return exit_code_for_error(envelope.receipt.errors[0])
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
