"""CLI for build_calibration_sheet.

Usage:
    python -m covalent_design.rules.cli.build_calibration_sheet
        --records <records.jsonl> --rules <rule_table.yml>
        [--out-csv <csv>] [--out-json <json>]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from covalent_design.rules.calibration import build_calibration_sheet


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a calibration review sheet from records and rule table."
    )
    parser.add_argument(
        "--records", type=Path, required=True, help="Path to records.jsonl"
    )
    parser.add_argument(
        "--rules", type=Path, required=True, help="Path to rule table YAML"
    )
    parser.add_argument(
        "--out-csv", type=Path, default=None, help="Output CSV path"
    )
    parser.add_argument(
        "--out-json", type=Path, default=None, help="Output JSON summary path"
    )
    args = parser.parse_args(argv)

    envelope = build_calibration_sheet(
        records_path=args.records,
        rule_table_path=args.rules,
        out_csv=args.out_csv,
        out_json=args.out_json,
    )

    summary = {
        "ok": envelope.receipt.ok,
        "validator": envelope.receipt.validator,
        "contract_version": envelope.receipt.contract_version,
        "family_count": envelope.payload.get("family_count", 0),
        "families": envelope.payload.get("families", []),
    }
    json.dump(summary, sys.stdout, sort_keys=True, indent=2)
    sys.stdout.write("\n")

    return 0 if envelope.receipt.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
