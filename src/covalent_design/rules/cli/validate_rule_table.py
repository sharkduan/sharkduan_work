"""CLI for validating a reaction family rule table file.

Usage:
    python -m covalent_design.rules.cli.validate_rule_table --rules <path>

Exit codes:
    0  - validation passed
    10 - contract/validation failure
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from covalent_design.contracts.errors import CLI_EXIT_CODES
from covalent_design.rules.validate import load_rule_table, validate_rule_table


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate a reaction family rule table YAML file."
    )
    parser.add_argument("--rules", type=Path, required=True, help="Path to rule table YAML")
    args = parser.parse_args(argv)

    table = load_rule_table(args.rules)
    envelope = validate_rule_table(table)

    summary = {
        "ok": envelope.receipt.ok,
        "validator": envelope.receipt.validator,
        "contract_version": envelope.receipt.contract_version,
        "family_count": len(envelope.payload.families),
        "families": envelope.payload.families,
        "errors": [_error_summary(e) for e in envelope.receipt.errors],
        "warnings": [_error_summary(w) for w in envelope.receipt.warnings],
    }
    json.dump(summary, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")

    if not envelope.receipt.ok:
        return CLI_EXIT_CODES["contract_validation_failed"]
    return 0


def _error_summary(error) -> dict:
    return {
        "code": error.code,
        "owner": error.owner,
        "message": error.message,
        "location": error.location,
        "details": dict(error.details),
    }


if __name__ == "__main__":
    raise SystemExit(main())
