from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional, Sequence

from covalent_design.evaluation.v2_metrics import (
    build_v2_evaluation_report,
    errors_to_dict,
    load_json_mapping_file,
    load_records_jsonl,
    load_v2_sampling_result_file,
    v2_evaluation_report_to_dict,
)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Write a deterministic V2 evaluation metrics summary.")
    parser.add_argument("--sampling-result", required=True, help="Path to V2SamplingResult JSON.")
    parser.add_argument("--fixture-records", help="Optional fixture records JSONL for family metrics.")
    parser.add_argument("--fixture-split-index", help="Optional fixture split index JSON.")
    parser.add_argument("--geometry-evidence", help="Optional explicit geometry-evidence JSON.")
    parser.add_argument("--uniqueness-evidence", help="Optional explicit uniqueness/novelty evidence JSON.")
    parser.add_argument("--rdkit-evidence", help="Optional explicit RDKit-validity evidence JSON.")
    args = parser.parse_args(argv)

    sampling = load_v2_sampling_result_file(Path(args.sampling_result))
    if not sampling.receipt.passed or sampling.payload is None:
        _print_errors(sampling.receipt.errors)
        return 1

    records = ()
    if args.fixture_records:
        loaded = load_records_jsonl(Path(args.fixture_records))
        if not loaded.receipt.passed or loaded.payload is None:
            _print_errors(loaded.receipt.errors)
            return 1
        records = loaded.payload

    split_index = None
    if args.fixture_split_index:
        loaded = load_json_mapping_file(Path(args.fixture_split_index))
        if not loaded.receipt.passed or loaded.payload is None:
            _print_errors(loaded.receipt.errors)
            return 1
        split_index = loaded.payload

    geometry = _load_optional_mapping(args.geometry_evidence)
    if isinstance(geometry, int):
        return geometry
    uniqueness = _load_optional_mapping(args.uniqueness_evidence)
    if isinstance(uniqueness, int):
        return uniqueness
    rdkit = _load_optional_mapping(args.rdkit_evidence)
    if isinstance(rdkit, int):
        return rdkit

    envelope = build_v2_evaluation_report(
        sampling.payload,
        fixture_records=records,
        fixture_split_index=split_index,
        geometry_evidence=geometry,
        uniqueness_evidence=uniqueness,
        rdkit_evidence=rdkit,
    )
    if not envelope.receipt.passed:
        _print_errors(envelope.receipt.errors)
        return 1

    sys.stdout.write(
        json.dumps(
            v2_evaluation_report_to_dict(envelope.payload),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )
    return 0


def _load_optional_mapping(path: Optional[str]) -> Optional[dict[str, object]] | int:
    if path is None:
        return None
    loaded = load_json_mapping_file(Path(path))
    if not loaded.receipt.passed or loaded.payload is None:
        _print_errors(loaded.receipt.errors)
        return 1
    return dict(loaded.payload)


def _print_errors(errors) -> None:
    sys.stderr.write(
        json.dumps(errors_to_dict(errors), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    )


if __name__ == "__main__":
    raise SystemExit(main())
