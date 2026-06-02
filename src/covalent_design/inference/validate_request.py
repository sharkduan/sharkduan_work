"""CLI entry point for request validation.

Usage:
  python -m covalent_design.inference.validate_request --request <path>
  python -m covalent_design.inference.validate_request --request <path> --rules <path>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from covalent_design.contracts.errors import ContractError, exit_code_for_error
from covalent_design.inference.request_validation import validate_request_file


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Validate a reactive-site generation request."
    )
    parser.add_argument(
        "--request",
        required=True,
        type=Path,
        help="Path to request YAML or JSON file.",
    )
    parser.add_argument(
        "--rules",
        type=Path,
        default=None,
        help="Path to reaction family rule table YAML (default: repo default).",
    )
    args = parser.parse_args(argv)

    try:
        validated = validate_request_file(args.request, rules_path=args.rules)

        result = {
            "status": "ok",
            "request_id": validated.request.request_id,
            "rule_table_version": validated.rule_table_version,
            "resolved_target_atom_identity": {
                "chain_id": validated.resolved_target_atom_identity.chain_id,
                "residue_number": validated.resolved_target_atom_identity.residue_number,
                "residue_name": validated.resolved_target_atom_identity.residue_name,
                "atom_name": validated.resolved_target_atom_identity.atom_name,
                "altloc": validated.resolved_target_atom_identity.altloc,
                "insertion_code": validated.resolved_target_atom_identity.insertion_code,
                "structure_model": validated.resolved_target_atom_identity.structure_model,
                "asym_id": validated.resolved_target_atom_identity.asym_id,
            },
            "resolved_target_altloc": validated.resolved_target_altloc,
        }
        json.dump(result, sys.stdout, indent=2, sort_keys=True, default=str)
        sys.stdout.write("\n")
        sys.exit(0)

    except ContractError as exc:
        error_output = {
            "status": "error",
            "errors": [
                {
                    "code": exc.code,
                    "owner": exc.owner,
                    "message": exc.message,
                    "location": exc.location,
                }
            ],
        }
        json.dump(error_output, sys.stdout, indent=2, sort_keys=True, default=str)
        sys.stdout.write("\n")
        sys.exit(exit_code_for_error(exc))


if __name__ == "__main__":
    main()
