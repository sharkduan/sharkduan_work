"""CLI entry point for ``python -m covalent_design.data.cli.v2_run_real_etl``.

Window C: Real ETL pipeline.  Discovers v2 data intake manifests under a raw
root, validates (Task 40), stages (Task 41), converts (Task 42), and runs the
license/provenance gate (Task 43).  Writes a deterministic report and exits with
a contract-aware exit code.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List, Optional, Sequence

from covalent_design.contracts.errors import ContractErrorInfo
from covalent_design.contracts.types import (
    ContractEnvelope,
    SourceIngestRecord,
)
from covalent_design.data.v2_conversion import (
    SUPPORTED_PARSER_TARGETS,
    UNSUPPORTED_PARSER_TARGETS,
    convert_staged_source,
)
from covalent_design.data.v2_intake import (
    STATUS_PENDING_DOWNLOAD,
    V2StagingSummary,
    stage_source_manifest,
)
from covalent_design.data.v2_license import (
    audit_v2_training_eligibility,
    license_gate_report_to_dict,
    load_source_license_audit,
)
from covalent_design.data.v2_manifests import (
    validate_v2_data_intake_manifest,
)

_ALLOWED_SOURCE_FILTERS = frozenset(
    {"all", "covalentin_db", "covpdb", "covbinder_in_pdb"}
)
_EXPECTED_SOURCES = (
    ("CovalentInDB", "covalentin_db"),
    ("CovPDB", "covpdb"),
    ("CovBinderInPDB", "covbinder_in_pdb"),
)

# ---------------------------------------------------------------------------
# Report dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SourceEtlResult:
    """Deterministic per-source ETL pipeline result."""

    source_name: str
    parser_target: str
    manifest_path: str
    manifest_ok: bool
    staging_ok: bool
    staging_status: str
    conversion_ok: bool
    conversion_record_count: int
    conversion_errors: tuple[dict[str, object], ...]
    unsupported_notice: str
    license_eligible: Optional[bool]
    license_status: str
    license_errors: tuple[dict[str, object], ...]


def _source_result_to_dict(result: SourceEtlResult) -> dict[str, object]:
    return {
        "source_name": result.source_name,
        "parser_target": result.parser_target,
        "manifest_path": result.manifest_path,
        "manifest_ok": result.manifest_ok,
        "staging_ok": result.staging_ok,
        "staging_status": result.staging_status,
        "conversion_ok": result.conversion_ok,
        "conversion_record_count": result.conversion_record_count,
        "conversion_errors": list(result.conversion_errors),
        "unsupported_notice": result.unsupported_notice,
        "license_eligible": result.license_eligible,
        "license_status": result.license_status,
        "license_errors": list(result.license_errors),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="covalent_design.data.cli.v2_run_real_etl",
        description="Window C: Real ETL pipeline — validate, stage, convert, "
        "license gate.",
    )
    parser.add_argument(
        "--raw-root",
        required=True,
        type=Path,
        help="Root directory containing source manifest files",
    )
    parser.add_argument(
        "--staging-root",
        required=True,
        type=Path,
        help="Root directory for staging evidence",
    )
    parser.add_argument(
        "--out-root",
        required=True,
        type=Path,
        help="Root directory for output records",
    )
    parser.add_argument(
        "--report-root",
        required=True,
        type=Path,
        help="Root directory for ETL reports",
    )
    parser.add_argument(
        "--source",
        type=str,
        default="all",
        help="Source filter: covalentin_db|covpdb|covbinder_in_pdb|all",
    )
    args = parser.parse_args(argv)

    raw_root = Path(args.raw_root).resolve()
    out_root = Path(args.out_root).resolve()
    report_root = Path(args.report_root).resolve()
    source_filter = args.source.lower()

    if source_filter not in _ALLOWED_SOURCE_FILTERS:
        _print_error(
            f"Unknown --source filter: {source_filter!r}. "
            f"Allowed: {sorted(_ALLOWED_SOURCE_FILTERS)}"
        )
        return 2

    # Ensure output directories exist
    for root_arg in (args.staging_root, args.out_root, args.report_root):
        Path(root_arg).mkdir(parents=True, exist_ok=True)

    # Discover manifests. Missing expected manifests are represented in the
    # report instead of causing an early exit, so incomplete real-data roots
    # still produce auditable evidence.
    manifest_paths: list[Path] = []
    source_results: list[SourceEtlResult] = []
    discovered_targets: set[str] = set()

    for manifest_candidate in _candidate_manifest_paths(raw_root):
        parser_target = _manifest_parser_target(manifest_candidate)
        if not parser_target:
            parser_target = _expected_parser_from_path(manifest_candidate)
        if source_filter != "all" and parser_target != source_filter:
            continue

        manifest_envelope = validate_v2_data_intake_manifest(manifest_candidate)
        if manifest_envelope.receipt.ok and manifest_envelope.payload is not None:
            manifest_paths.append(manifest_candidate)
            discovered_targets.add(manifest_envelope.payload.parser_target)
            continue

        source_name = _manifest_source_name(manifest_candidate)
        if not source_name and parser_target:
            source_name = _source_name_for_parser(parser_target)
        source_results.append(
            _invalid_manifest_result(
                source_name=source_name,
                parser_target=parser_target,
                manifest_path=manifest_candidate,
                errors=manifest_envelope.receipt.errors,
            )
        )
        if parser_target:
            discovered_targets.add(parser_target)

    # ------------------------------------------------------------------
    # Per-source: Task 40 → Task 41 → Task 42
    # ------------------------------------------------------------------
    staging_envelopes: list[ContractEnvelope[V2StagingSummary]] = []
    converted_records: list[SourceIngestRecord] = []
    converted_records_by_parser: dict[str, list[SourceIngestRecord]] = {}
    for source_name, parser_target in _expected_sources(source_filter):
        if parser_target not in discovered_targets:
            source_results.append(
                _missing_manifest_result(source_name, parser_target, raw_root)
            )

    for manifest_path in manifest_paths:
        result, staging_env, records = _process_source(manifest_path)
        source_results.append(result)
        if staging_env is not None and result.conversion_ok:
            staging_envelopes.append(staging_env)
            converted_records.extend(records)
            converted_records_by_parser[result.parser_target] = records

    # ------------------------------------------------------------------
    # Task 43: License / provenance gate
    # ------------------------------------------------------------------
    if staging_envelopes:
        license_audits = _load_license_audits(source_results, raw_root)
        approved_roots = (raw_root,)
        license_envelope = audit_v2_training_eligibility(
            staged_evidence=tuple(staging_envelopes),
            license_audits=license_audits,
            converted_records=tuple(converted_records),
            approved_local_data_roots=approved_roots,
        )

        # Merge license results into per-source results
        source_results = _merge_license_results(
            source_results, license_envelope
        )

    # ------------------------------------------------------------------
    # Build and write report
    # ------------------------------------------------------------------
    report = _build_report(source_results)
    processed_manifest_path = _write_processed_artifacts(
        source_results,
        converted_records_by_parser,
        out_root,
        etl_complete=bool(report["etl_complete"]),
    )
    report["processed_manifest_path"] = processed_manifest_path
    _write_report(report, report_root)

    # ------------------------------------------------------------------
    # Print summary
    # ------------------------------------------------------------------
    print(
        json.dumps(
            {
                "total_sources": report["total_sources"],
                "sources_converted": report["sources_converted"],
                "sources_unsupported": report["sources_unsupported"],
                "sources_failed": report["sources_failed"],
                "etl_complete": report["etl_complete"],
                "report_written": report["report_path"],
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
    )

    if not report["etl_complete"]:
        return 30  # data quality gate failed / incomplete
    return 0


# ---------------------------------------------------------------------------
# Discovery helpers
# ---------------------------------------------------------------------------


def _expected_sources(source_filter: str) -> tuple[tuple[str, str], ...]:
    if source_filter == "all":
        return _EXPECTED_SOURCES
    return tuple(
        (source_name, parser_target)
        for source_name, parser_target in _EXPECTED_SOURCES
        if parser_target == source_filter
    )


def _missing_manifest_result(
    source_name: str,
    parser_target: str,
    raw_root: Path,
) -> SourceEtlResult:
    return SourceEtlResult(
        source_name=source_name,
        parser_target=parser_target,
        manifest_path=str(raw_root / parser_target / "manifest.json"),
        manifest_ok=False,
        staging_ok=False,
        staging_status="",
        conversion_ok=False,
        conversion_record_count=0,
        conversion_errors=(
            {
                "code": "V2_ETL_SOURCE_MANIFEST_MISSING",
                "message": (
                    "No v2 data intake manifest was discovered for "
                    f"parser target {parser_target!r} under raw root"
                ),
            },
        ),
        unsupported_notice="",
        license_eligible=None,
        license_status="",
        license_errors=(),
    )


def _invalid_manifest_result(
    *,
    source_name: str,
    parser_target: str,
    manifest_path: Path,
    errors: tuple[ContractErrorInfo, ...],
) -> SourceEtlResult:
    return SourceEtlResult(
        source_name=source_name,
        parser_target=parser_target,
        manifest_path=str(manifest_path),
        manifest_ok=False,
        staging_ok=False,
        staging_status="",
        conversion_ok=False,
        conversion_record_count=0,
        conversion_errors=_errors_dicts(errors),
        unsupported_notice="",
        license_eligible=None,
        license_status="",
        license_errors=(),
    )


def _candidate_manifest_paths(raw_root: Path) -> list[Path]:
    if not raw_root.is_dir():
        return []
    return sorted(
        path
        for path in raw_root.rglob("*.json")
        if path.name in {"manifest.json", "source_manifest.json"}
    )


def _is_v2_manifest(path: Path) -> bool:
    """Return True if *path* looks like a v2 data intake manifest."""
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return False
    return (
        isinstance(data, dict)
        and data.get("contract_version") == "v2-beta"
        and data.get("schema_version") == "1.0.0"
    )


def _manifest_parser_target(path: Path) -> str:
    """Extract parser_target from a manifest without full validation."""
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return ""
    return str(data.get("parser_target", ""))


def _manifest_source_name(path: Path) -> str:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return _source_name_from_dir(path.parent.name)
    return str(data.get("source_name", "")) or _source_name_from_dir(path.parent.name)


def _expected_parser_from_path(path: Path) -> str:
    source_name = _source_name_from_dir(path.parent.name)
    for expected_source, parser_target in _EXPECTED_SOURCES:
        if expected_source == source_name:
            return parser_target
    return ""


def _source_name_from_dir(name: str) -> str:
    normalized = name.lower()
    for source_name, parser_target in _EXPECTED_SOURCES:
        if normalized in {source_name.lower(), parser_target.lower()}:
            return source_name
    return ""


def _source_name_for_parser(parser_target: str) -> str:
    for source_name, expected_parser in _EXPECTED_SOURCES:
        if expected_parser == parser_target:
            return source_name
    return ""


# ---------------------------------------------------------------------------
# Per-source pipeline
# ---------------------------------------------------------------------------


def _process_source(
    manifest_path: Path,
) -> tuple[
    SourceEtlResult,
    Optional[ContractEnvelope[V2StagingSummary]],
    list[SourceIngestRecord],
]:
    """Run Task 40 → Task 41 → Task 42 for a single manifest.

    Returns the per-source result, the staging envelope (if staging
    succeeded), and any successfully converted records.
    """
    manifest_str = str(manifest_path)
    parser_target = _manifest_parser_target(manifest_path)

    # --- Task 40: validate manifest ---
    manifest_envelope = validate_v2_data_intake_manifest(manifest_path)
    manifest_ok = manifest_envelope.receipt.ok
    if not manifest_ok:
        result = SourceEtlResult(
            source_name="",
            parser_target=parser_target,
            manifest_path=manifest_str,
            manifest_ok=False,
            staging_ok=False,
            staging_status="",
            conversion_ok=False,
            conversion_record_count=0,
            conversion_errors=_errors_dicts(manifest_envelope.receipt.errors),
            unsupported_notice="",
            license_eligible=None,
            license_status="",
            license_errors=(),
        )
        return result, None, []

    manifest = manifest_envelope.payload
    source_name = str(manifest.source_name) if manifest else ""

    # --- Task 41: stage ---
    staging_envelope = stage_source_manifest(manifest_path)
    staging_ok = staging_envelope.receipt.ok
    staging_status = (
        staging_envelope.payload.status
        if staging_envelope.payload
        else ""
    )
    staging_errors = _errors_dicts(staging_envelope.receipt.errors)

    if not staging_ok:
        result = SourceEtlResult(
            source_name=source_name,
            parser_target=parser_target,
            manifest_path=manifest_str,
            manifest_ok=True,
            staging_ok=False,
            staging_status=staging_status,
            conversion_ok=False,
            conversion_record_count=0,
            conversion_errors=staging_errors,
            unsupported_notice="",
            license_eligible=None,
            license_status="",
            license_errors=(),
        )
        return result, None, []

    if staging_status == STATUS_PENDING_DOWNLOAD:
        result = SourceEtlResult(
            source_name=source_name,
            parser_target=parser_target,
            manifest_path=manifest_str,
            manifest_ok=True,
            staging_ok=True,
            staging_status=staging_status,
            conversion_ok=False,
            conversion_record_count=0,
            conversion_errors=(
                {
                    "code": "V2_ETL_PENDING_DOWNLOAD",
                    "message": (
                        f"Source {source_name} is pending download; "
                        "not convertible in Task 42"
                    ),
                },
            ),
            unsupported_notice="",
            license_eligible=None,
            license_status="",
            license_errors=(),
        )
        return result, staging_envelope, []

    # --- Task 42: convert ---
    conversion_envelope = convert_staged_source(staging_envelope)
    conversion_ok = conversion_envelope.receipt.ok
    conversion_errors = _errors_dicts(conversion_envelope.receipt.errors)
    records = list(conversion_envelope.payload) if conversion_envelope.payload else []

    # Detect unsupported parser for explicit reporting
    unsupported_notice = ""
    if not conversion_ok and parser_target in UNSUPPORTED_PARSER_TARGETS:
        unsupported_notice = (
            f"Parser target {parser_target!r} is explicitly known but "
            f"conversion is not implemented in Task 42. "
            f"Supported: {sorted(SUPPORTED_PARSER_TARGETS)}. "
            "This source was NOT silently skipped."
        )

    result = SourceEtlResult(
        source_name=source_name,
        parser_target=parser_target,
        manifest_path=manifest_str,
        manifest_ok=True,
        staging_ok=True,
        staging_status=staging_status,
        conversion_ok=conversion_ok,
        conversion_record_count=len(records),
        conversion_errors=conversion_errors,
        unsupported_notice=unsupported_notice,
        license_eligible=None,
        license_status="",
        license_errors=(),
    )
    return result, staging_envelope, records


# ---------------------------------------------------------------------------
# License gate
# ---------------------------------------------------------------------------


def _load_license_audits(
    results: Sequence[SourceEtlResult],
    raw_root: Path,
) -> dict[str, object]:
    """Load license audit files referenced by staged manifests."""
    audits: dict[str, object] = {}
    for result in results:
        if not result.staging_ok:
            continue
        manifest_path = Path(result.manifest_path)
        manifest_dir = manifest_path.parent
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            continue
        audit_ref = str(data.get("license_audit_ref", ""))
        if not audit_ref:
            continue
        # Resolve relative to manifest directory
        audit_path = Path(audit_ref)
        if not audit_path.is_absolute():
            audit_path = manifest_dir / audit_path
        if audit_path.is_file():
            try:
                audits[audit_ref] = load_source_license_audit(audit_path)
            except (OSError, json.JSONDecodeError, KeyError, TypeError):
                audits[audit_ref] = _unknown_audit_dict(result.source_name)
        else:
            audits[audit_ref] = _unknown_audit_dict(result.source_name)
    return audits


def _unknown_audit_dict(source_name: str) -> dict[str, object]:
    return {
        "source_name": source_name,
        "intake_mode": "",
        "license_status": "unknown",
        "license_evidence_ref": "audit_not_found",
        "block_reason": "License audit file not found at referenced path",
    }


def _merge_license_results(
    results: list[SourceEtlResult],
    license_envelope: ContractEnvelope[object],
) -> list[SourceEtlResult]:
    """Attach license gate results to each per-source result."""
    if license_envelope.payload is None:
        return results

    gate_report = license_envelope.payload
    gate_data = license_gate_report_to_dict(gate_report)

    # Build lookup: source_name → license source report
    license_lookup: dict[str, dict[str, object]] = {}
    for src in gate_data.get("sources", []):
        name = str(src.get("source_name", ""))
        if name:
            license_lookup[name] = src

    merged: list[SourceEtlResult] = []
    for result in results:
        source_report = license_lookup.get(result.source_name)
        if source_report is not None:
            merged.append(
                SourceEtlResult(
                    source_name=result.source_name,
                    parser_target=result.parser_target,
                    manifest_path=result.manifest_path,
                    manifest_ok=result.manifest_ok,
                    staging_ok=result.staging_ok,
                    staging_status=result.staging_status,
                    conversion_ok=result.conversion_ok,
                    conversion_record_count=result.conversion_record_count,
                    conversion_errors=result.conversion_errors,
                    unsupported_notice=result.unsupported_notice,
                    license_eligible=bool(
                        source_report.get("training_eligible", False)
                    ),
                    license_status=str(
                        source_report.get("license_status", "")
                    ),
                    license_errors=tuple(
                        {
                            "code": str(rc),
                            "message": str(rc),
                        }
                        for rc in source_report.get("reason_codes", [])
                    ),
                )
            )
        else:
            # License gate did not produce a report for this source
            merged.append(
                SourceEtlResult(
                    source_name=result.source_name,
                    parser_target=result.parser_target,
                    manifest_path=result.manifest_path,
                    manifest_ok=result.manifest_ok,
                    staging_ok=result.staging_ok,
                    staging_status=result.staging_status,
                    conversion_ok=result.conversion_ok,
                    conversion_record_count=result.conversion_record_count,
                    conversion_errors=result.conversion_errors,
                    unsupported_notice=result.unsupported_notice,
                    license_eligible=None,
                    license_status="",
                    license_errors=(
                        {
                            "code": "V2_LICENSE_NO_REPORT",
                            "message": "License gate produced no report for "
                            f"source {result.source_name}",
                        },
                    ),
                )
            )
    return merged


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def _build_report(results: list[SourceEtlResult]) -> dict[str, object]:
    """Build a deterministic ETL report dictionary."""
    sources = [_source_result_to_dict(r) for r in results]
    sources.sort(
        key=lambda s: (s["source_name"], s["parser_target"])
    )

    total = len(sources)
    converted = sum(1 for s in sources if s["conversion_ok"])
    unsupported = sum(
        1 for s in sources
        if not s["conversion_ok"] and s["unsupported_notice"]
    )
    ready = sum(
        1
        for s in sources
        if s["conversion_ok"] and s["license_eligible"] is True
    )
    failed = total - ready - unsupported

    # ETL is complete only when every requested source converted and passed
    # the license/provenance gate, or is explicitly unsupported.
    etl_complete = failed == 0

    return {
        "contract_version": "v2-beta",
        "pipeline": "window_c_real_etl",
        "total_sources": total,
        "sources_converted": converted,
        "sources_unsupported": unsupported,
        "sources_failed": failed,
        "etl_complete": etl_complete,
        "sources": sources,
        "report_path": "",
    }


def _write_report(report: dict[str, object], report_root: Path) -> None:
    """Write the ETL report as deterministic JSON under report_root."""
    report_root.mkdir(parents=True, exist_ok=True)

    report_path = report_root / "window_c_real_etl_report.json"
    report["report_path"] = str(report_path)
    text = json.dumps(
        report, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    report_path.write_text(text, encoding="utf-8")


def _write_processed_artifacts(
    results: Sequence[SourceEtlResult],
    records_by_parser: dict[str, list[SourceIngestRecord]],
    out_root: Path,
    *,
    etl_complete: bool,
) -> str:
    """Write deterministic processed records for sources that passed all gates."""
    out_root.mkdir(parents=True, exist_ok=True)
    source_entries: list[dict[str, object]] = []

    for result in sorted(results, key=lambda item: (item.source_name, item.parser_target)):
        if not result.conversion_ok or result.license_eligible is not True:
            continue
        records = records_by_parser.get(result.parser_target, [])
        if not records:
            continue

        records_path = out_root / f"{result.parser_target}.records.jsonl"
        text = "\n".join(_record_json(record) for record in records)
        records_path.write_text(text + "\n", encoding="utf-8")

        first_record = records[0]
        license_ref = str(
            first_record.metadata.get("license_audit_ref")
            or first_record.lineage.get("license_audit_ref")
            or ""
        )
        source_url = str(
            first_record.metadata.get("source_url")
            or first_record.lineage.get("source_url")
            or ""
        )
        source_entries.append(
            {
                "checksum": first_record.raw_file_sha256,
                "gate_status": "passed",
                "license_audit_ref": license_ref,
                "license_status": result.license_status,
                "local_path": first_record.raw_file_path,
                "parser_target": result.parser_target,
                "record_count": len(records),
                "records_path": str(records_path),
                "source_name": result.source_name,
                "source_provenance": source_url,
            }
        )

    manifest = {
        "contract_version": "v2-beta",
        "etl_complete": etl_complete,
        "pipeline": "window_c_real_etl_processed",
        "sources": source_entries,
        "total_records": sum(int(source["record_count"]) for source in source_entries),
    }
    manifest_path = out_root / "v2_real_etl_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False),
        encoding="utf-8",
    )
    return str(manifest_path)


def _record_json(record: SourceIngestRecord) -> str:
    return json.dumps(
        asdict(record),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _errors_dicts(
    errors: tuple[ContractErrorInfo, ...],
) -> tuple[dict[str, object], ...]:
    return tuple(
        {
            "code": e.code,
            "owner": e.owner,
            "message": e.message,
            "location": e.location,
            "details": dict(e.details),
        }
        for e in errors
    )


def _print_error(message: str) -> None:
    print(
        json.dumps(
            {"ok": False, "error": message},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
