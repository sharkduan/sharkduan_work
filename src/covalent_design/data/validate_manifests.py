from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from covalent_design.data.manifests import validate_raw_manifests


DATA_QUALITY_EXIT_CODE = 30


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate staged raw source manifests.")
    parser.add_argument("--raw-root", type=Path, required=True)
    args = parser.parse_args(argv)

    envelope = validate_raw_manifests(args.raw_root)
    summary = {
        "ok": envelope.receipt.ok,
        "validator": envelope.receipt.validator,
        "contract_version": envelope.receipt.contract_version,
        "source_count": envelope.payload.source_count,
        "file_count": envelope.payload.file_count,
        "extra_files": list(envelope.payload.extra_files),
        "errors": [asdict(error) for error in envelope.receipt.errors],
        "warnings": [asdict(warning) for warning in envelope.receipt.warnings],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if envelope.receipt.ok else DATA_QUALITY_EXIT_CODE


if __name__ == "__main__":
    raise SystemExit(main())
