"""Window B: Real ETL CLI tests for the V2 conversion pipeline.

Tests cover the ``convert_staged_manifest`` ETL entrypoint and the
``v2_stage_source`` CLI ``main()`` function, verifying that the pipeline
rejects invalid inputs with structured errors and converts supported
sources to ``SourceIngestRecord`` records.
"""

from __future__ import annotations

import hashlib
import json
import socket
import urllib.request
from pathlib import Path

import pytest

from covalent_design.contracts.types import (
    ContractEnvelope,
    Provenance,
    SourceIngestRecord,
    SourceRecordLineage,
    ValidationReceipt,
)
from covalent_design.contracts.errors import ContractErrorInfo
from covalent_design.data.cli.v2_run_real_etl import main as v2_run_real_etl_main
from covalent_design.data.cli.v2_stage_source import main as v2_stage_source_main
from covalent_design.data.v2_conversion import convert_staged_manifest
from covalent_design.data.v2_intake import stage_source_manifest

# ---------------------------------------------------------------------------
# Fixture roots
# ---------------------------------------------------------------------------
FIXTURE_ROOT = (
    Path(__file__).resolve().parents[1] / "fixtures" / "v2" / "data_conversion"
)
INTAKE_FIXTURE_ROOT = (
    Path(__file__).resolve().parents[1] / "fixtures" / "v2" / "data_intake"
)

MANUAL_VALID_DATA = FIXTURE_ROOT / "manual_valid" / "data" / "covalentindb_sample.tsv"
MISSING_LICENSE_AUDIT_MANIFEST = (
    FIXTURE_ROOT / "missing_license_audit" / "manifest.json"
)
FORBIDDEN_TRAINING_MANIFEST = (
    FIXTURE_ROOT / "forbidden_training_eligible" / "manifest.json"
)
CHECKSUM_MISMATCH_MANIFEST = (
    INTAKE_FIXTURE_ROOT / "manual_checksum_mismatch" / "manifest.json"
)
DOWNLOAD_MANIFEST = INTAKE_FIXTURE_ROOT / "download" / "source_manifest.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _error_codes(envelope: ContractEnvelope[object]) -> set[str]:
    return {error.code for error in envelope.receipt.errors}


def _write_manual_manifest(
    directory: Path,
    *,
    data_file: Path,
    **overrides: object,
) -> Path:
    """Write a valid covalentin_db manual manifest JSON and return its path."""
    checksum = _sha256_file(data_file)
    payload: dict[str, object] = {
        "schema_version": "1.0.0",
        "contract_version": "v2-beta",
        "source_name": "CovalentInDB",
        "intake_mode": "manual",
        "manual_path": str(data_file),
        "source_url": None,
        "checksum": checksum,
        "checksum_algorithm": "sha256",
        "parser_target": "covalentin_db",
        "retrieval_date": "2026-06-16",
        "license_audit_ref": "audit/covalentindb/license.json",
        "access_notes": "generated test fixture",
    }
    for key in ("manual_path", "source_url"):
        if key in overrides:
            payload[key] = overrides.pop(key)
    payload.update(overrides)
    path = directory / "manifest.json"
    path.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False),
        encoding="utf-8",
    )
    return path


# ---------------------------------------------------------------------------
# Real ETL CLI entrypoint
# ---------------------------------------------------------------------------


class TestRealEtlCliEntrypoint:
    """Tests for the real-data CLI wrapper using synthetic empty roots."""

    def test_missing_manifests_write_per_source_report(
        self, tmp_path: Path
    ) -> None:
        raw_root = tmp_path / "raw"
        staging_root = tmp_path / "staging"
        out_root = tmp_path / "processed"
        report_root = tmp_path / "reports"
        raw_root.mkdir()

        exit_code = v2_run_real_etl_main(
            [
                "--raw-root",
                str(raw_root),
                "--staging-root",
                str(staging_root),
                "--out-root",
                str(out_root),
                "--report-root",
                str(report_root),
                "--source",
                "all",
            ]
        )

        assert exit_code == 30
        report_path = report_root / "window_c_real_etl_report.json"
        assert report_path.is_file()
        report = json.loads(report_path.read_text(encoding="utf-8"))
        assert report["report_path"] == str(report_path)
        assert report["total_sources"] == 3
        assert report["sources_failed"] == 3
        assert report["sources_converted"] == 0
        assert report["sources_unsupported"] == 0
        codes = {
            error["code"]
            for source in report["sources"]
            for error in source["conversion_errors"]
        }
        assert codes == {"V2_ETL_SOURCE_MANIFEST_MISSING"}

    def test_source_filter_limits_missing_manifest_report(
        self, tmp_path: Path
    ) -> None:
        raw_root = tmp_path / "raw"
        raw_root.mkdir()
        report_root = tmp_path / "reports"

        exit_code = v2_run_real_etl_main(
            [
                "--raw-root",
                str(raw_root),
                "--staging-root",
                str(tmp_path / "staging"),
                "--out-root",
                str(tmp_path / "processed"),
                "--report-root",
                str(report_root),
                "--source",
                "covalentin_db",
            ]
        )

        assert exit_code == 30
        report = json.loads(
            (report_root / "window_c_real_etl_report.json").read_text(
                encoding="utf-8"
            )
        )
        assert report["total_sources"] == 1
        assert report["sources"][0]["parser_target"] == "covalentin_db"

    def test_existing_invalid_manifest_is_not_reported_as_missing(
        self, tmp_path: Path
    ) -> None:
        raw_root = tmp_path / "raw"
        source_dir = raw_root / "CovalentInDB"
        source_dir.mkdir(parents=True)
        manifest = source_dir / "source_manifest.json"
        manifest.write_text("{not-json", encoding="utf-8")
        report_root = tmp_path / "reports"

        exit_code = v2_run_real_etl_main(
            [
                "--raw-root",
                str(raw_root),
                "--staging-root",
                str(tmp_path / "staging"),
                "--out-root",
                str(tmp_path / "processed"),
                "--report-root",
                str(report_root),
                "--source",
                "covalentin_db",
            ]
        )

        assert exit_code == 30
        report = json.loads(
            (report_root / "window_c_real_etl_report.json").read_text(
                encoding="utf-8"
            )
        )
        source = report["sources"][0]
        assert source["manifest_path"] == str(manifest)
        assert source["conversion_errors"][0]["code"] == "V2_MANIFEST_INVALID_JSON"
        assert source["conversion_errors"][0]["code"] != "V2_ETL_SOURCE_MANIFEST_MISSING"

    def test_cli_writes_processed_artifact_for_successful_source(
        self, tmp_path: Path
    ) -> None:
        raw_root = tmp_path / "raw"
        source_dir = raw_root / "CovalentInDB"
        source_dir.mkdir(parents=True)
        data_file = source_dir / "data.tsv"
        data_file.write_text(
            "pdb_id\tuniprot_id\tresidue\tresidue_number\tligand\t"
            "ligand_name\tbond_type\twarhead_type\n"
            "1abc\tP00001\tCYS145\t145\tLIG\tligand\tsingle\tacrylamide\n",
            encoding="utf-8",
        )
        (source_dir / "license.json").write_text(
            json.dumps(
                {
                    "source_name": "CovalentInDB",
                    "intake_mode": "manual",
                    "license_status": "manual_exempt",
                    "license_evidence_ref": "manual fixture",
                },
                sort_keys=True,
                separators=(",", ":"),
            ),
            encoding="utf-8",
        )
        _write_manual_manifest(
            source_dir,
            data_file=data_file,
            license_audit_ref="license.json",
        )
        out_root = tmp_path / "processed"

        exit_code = v2_run_real_etl_main(
            [
                "--raw-root",
                str(raw_root),
                "--staging-root",
                str(tmp_path / "staging"),
                "--out-root",
                str(out_root),
                "--report-root",
                str(tmp_path / "reports"),
                "--source",
                "covalentin_db",
            ]
        )

        assert exit_code == 0
        manifest_path = out_root / "v2_real_etl_manifest.json"
        records_path = out_root / "covalentin_db.records.jsonl"
        assert manifest_path.is_file()
        assert records_path.is_file()
        processed_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert processed_manifest["etl_complete"] is True
        assert processed_manifest["sources"][0]["parser_target"] == "covalentin_db"
        assert processed_manifest["sources"][0]["record_count"] == 1
        assert processed_manifest["sources"][0]["records_path"] == str(records_path)
        lines = records_path.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 1
        assert json.loads(lines[0])["source_database"] == "CovalentInDB"

    def test_failed_conversion_partial_payload_does_not_feed_downstream(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        raw_root = tmp_path / "raw"
        source_dir = raw_root / "CovalentInDB"
        source_dir.mkdir(parents=True)
        data_file = source_dir / "data.tsv"
        data_file.write_text(
            "pdb_id\tuniprot_id\tresidue\tresidue_number\tligand\t"
            "ligand_name\tbond_type\twarhead_type\n"
            "1abc\tP00001\tCYS145\t145\tLIG\tligand\tsingle\tacrylamide\n",
            encoding="utf-8",
        )
        (source_dir / "license.json").write_text(
            json.dumps(
                {
                    "source_name": "CovalentInDB",
                    "intake_mode": "manual",
                    "license_status": "manual_exempt",
                    "license_evidence_ref": "manual fixture",
                },
                sort_keys=True,
                separators=(",", ":"),
            ),
            encoding="utf-8",
        )
        _write_manual_manifest(
            source_dir,
            data_file=data_file,
            license_audit_ref="license.json",
        )
        partial_record = SourceIngestRecord(
            source_database="CovalentInDB",
            source_version="v2",
            source_record_id="partial",
            raw_manifest_file=str(source_dir / "source_manifest.json"),
            raw_file_path=str(data_file),
            raw_file_sha256=_sha256_file(data_file),
            row_index=1,
            lineage={"license_audit_ref": "license.json"},
            protein={},
            ligand={},
            linkage={},
            metadata={"license_audit_ref": "license.json"},
            source_lineage=SourceRecordLineage(
                source_database="CovalentInDB",
                source_version="v2",
                source_record_id="partial",
                raw_manifest_file=str(source_dir / "source_manifest.json"),
                raw_file_path=str(data_file),
                raw_file_sha256=_sha256_file(data_file),
                row_index=1,
            ),
        )

        def _failed_conversion(_: object) -> ContractEnvelope[tuple[SourceIngestRecord, ...]]:
            return ContractEnvelope(
                payload=(partial_record,),
                artifacts=(),
                receipt=ValidationReceipt(
                    validator="covalent_design.data.v2_convert_staged_source",
                    contract_version="v2-beta",
                    input_sha256="partial",
                    ok=False,
                    errors=(
                        ContractErrorInfo(
                            code="V2_CONVERSION_ROW_PARSE_ERROR",
                            owner="data",
                            message="partial conversion fixture",
                        ),
                    ),
                ),
                provenance=Provenance(),
            )

        monkeypatch.setattr(
            "covalent_design.data.cli.v2_run_real_etl.convert_staged_source",
            _failed_conversion,
        )
        out_root = tmp_path / "processed"
        report_root = tmp_path / "reports"

        exit_code = v2_run_real_etl_main(
            [
                "--raw-root",
                str(raw_root),
                "--staging-root",
                str(tmp_path / "staging"),
                "--out-root",
                str(out_root),
                "--report-root",
                str(report_root),
                "--source",
                "covalentin_db",
            ]
        )

        assert exit_code == 30
        report = json.loads(
            (report_root / "window_c_real_etl_report.json").read_text(
                encoding="utf-8"
            )
        )
        source = report["sources"][0]
        assert source["conversion_ok"] is False
        assert source["conversion_record_count"] == 1
        assert source["license_eligible"] is None
        assert not (out_root / "covalentin_db.records.jsonl").exists()


# ---------------------------------------------------------------------------
# Test 1: Rejects missing raw root
# ---------------------------------------------------------------------------


class TestRejectsMissingRawRoot:
    """ETL CLI rejects a manifest whose raw data file does not exist."""

    def test_staging_fails_when_raw_file_missing(self, tmp_path: Path) -> None:
        """convert_staged_manifest returns staging error when data file is absent."""
        manifest = tmp_path / "manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "schema_version": "1.0.0",
                    "contract_version": "v2-beta",
                    "source_name": "CovalentInDB",
                    "intake_mode": "manual",
                    "manual_path": "nonexistent_data.tsv",
                    "checksum": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                    "checksum_algorithm": "sha256",
                    "parser_target": "covalentin_db",
                    "retrieval_date": "2026-06-16",
                    "license_audit_ref": "audit/covalentindb/license.json",
                    "access_notes": "test: no raw root",
                },
                sort_keys=True,
                separators=(",", ":"),
            ),
            encoding="utf-8",
        )

        result = convert_staged_manifest(manifest)

        assert not result.receipt.ok
        codes = _error_codes(result)
        assert "V2_INTAKE_MANUAL_PATH_FILE_NOT_FOUND" in codes

    def test_cli_main_rejects_missing_raw_file(self, tmp_path: Path) -> None:
        """CLI main() also rejects missing raw root via staging."""
        manifest = tmp_path / "manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "schema_version": "1.0.0",
                    "contract_version": "v2-beta",
                    "source_name": "CovalentInDB",
                    "intake_mode": "manual",
                    "manual_path": "nonexistent_data.tsv",
                    "checksum": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                    "checksum_algorithm": "sha256",
                    "parser_target": "covalentin_db",
                    "retrieval_date": "2026-06-16",
                    "license_audit_ref": "audit/covalentindb/license.json",
                    "access_notes": "test: no raw root",
                },
                sort_keys=True,
                separators=(",", ":"),
            ),
            encoding="utf-8",
        )

        exit_code = v2_stage_source_main(["--manifest", str(manifest)])
        assert exit_code != 0

    def test_missing_raw_root_dir(self, tmp_path: Path) -> None:
        """Manifest points into a missing subdirectory."""
        data_dir = tmp_path / "missing_dir"
        # directory does not exist
        manifest = tmp_path / "manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "schema_version": "1.0.0",
                    "contract_version": "v2-beta",
                    "source_name": "CovalentInDB",
                    "intake_mode": "manual",
                    "manual_path": "missing_dir/data.tsv",
                    "checksum": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                    "checksum_algorithm": "sha256",
                    "parser_target": "covalentin_db",
                    "retrieval_date": "2026-06-16",
                    "license_audit_ref": "audit/covalentindb/license.json",
                    "access_notes": "test: missing raw root directory",
                },
                sort_keys=True,
                separators=(",", ":"),
            ),
            encoding="utf-8",
        )

        result = convert_staged_manifest(manifest)
        assert not result.receipt.ok
        assert any(
            "FILE_NOT_FOUND" in c for c in _error_codes(result)
        )


# ---------------------------------------------------------------------------
# Test 2: Rejects missing source manifest
# ---------------------------------------------------------------------------


class TestRejectsMissingSourceManifest:
    """ETL CLI rejects a nonexistent manifest path with structured error."""

    def test_convert_staged_manifest_rejects_nonexistent_file(
        self, tmp_path: Path
    ) -> None:
        manifest = tmp_path / "does_not_exist.json"
        assert not manifest.exists()

        result = convert_staged_manifest(manifest)
        assert not result.receipt.ok
        codes = _error_codes(result)
        assert any(
            "MANIFEST_UNREADABLE" in c or "INTAKE_MANIFEST_UNREADABLE" in c
            for c in codes
        ), f"expected unreadable error, got {codes}"

    def test_cli_main_rejects_nonexistent_manifest(self, tmp_path: Path) -> None:
        manifest = tmp_path / "does_not_exist.json"
        assert not manifest.exists()

        exit_code = v2_stage_source_main(["--manifest", str(manifest)])
        assert exit_code != 0

    def test_staging_rejects_unreadable_manifest_directly(
        self, tmp_path: Path
    ) -> None:
        manifest = tmp_path / "ghost.json"
        assert not manifest.exists()

        envelope = stage_source_manifest(manifest)
        assert not envelope.receipt.ok
        assert "V2_INTAKE_MANIFEST_UNREADABLE" in _error_codes(envelope)


# ---------------------------------------------------------------------------
# Test 3: Stages manifest before conversion
# ---------------------------------------------------------------------------


class TestStagesManifestBeforeConversion:
    """ETL CLI must stage (validate + checksum) before attempting conversion."""

    def test_staging_failure_produces_staging_error_code_not_conversion(
        self, tmp_path: Path
    ) -> None:
        """When staging fails, error codes are V2_INTAKE_* not V2_CONVERSION_*."""
        # Use a manifest that fails at staging: manual_path points to nonexistent file
        manifest = tmp_path / "manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "schema_version": "1.0.0",
                    "contract_version": "v2-beta",
                    "source_name": "CovalentInDB",
                    "intake_mode": "manual",
                    "manual_path": "nonexistent_file.tsv",
                    "checksum": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                    "checksum_algorithm": "sha256",
                    "parser_target": "covalentin_db",
                    "retrieval_date": "2026-06-16",
                    "license_audit_ref": "audit/covalentindb/license.json",
                    "access_notes": "test: staging fails before conversion",
                },
                sort_keys=True,
                separators=(",", ":"),
            ),
            encoding="utf-8",
        )

        result = convert_staged_manifest(manifest)
        assert not result.receipt.ok

        codes = _error_codes(result)
        # Must be staging-level errors, not conversion errors
        assert any(c.startswith("V2_INTAKE_") for c in codes), (
            f"expected V2_INTAKE_* error, got {codes}"
        )
        assert not any(c.startswith("V2_CONVERSION_") for c in codes), (
            f"must not contain V2_CONVERSION_* when staging fails, got {codes}"
        )

    def test_staging_passes_then_conversion_runs(self, tmp_path: Path) -> None:
        """When staging passes, conversion runs and uses V2_CONVERSION validator."""
        data_file = tmp_path / "data.tsv"
        data_file.write_text(
            "pdb_id\tuniprot_id\tresidue\tresidue_number\tligand\t"
            "ligand_name\tbond_type\twarhead_type\n"
            "1abc\tP00001\tCYS145\t145\tLIG\tligand\tcovalent\tacrylamide\n",
            encoding="utf-8",
        )
        manifest = _write_manual_manifest(tmp_path, data_file=data_file)

        result = convert_staged_manifest(manifest)
        assert result.receipt.ok
        assert "convert" in result.receipt.validator.lower()


# ---------------------------------------------------------------------------
# Test 4: Refuses pending_download sources
# ---------------------------------------------------------------------------


class TestRefusesPendingDownload:
    """ETL CLI refuses to convert sources still in pending_download status."""

    def test_convert_staged_manifest_rejects_download_manifest(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _block_network(*args: object, **kwargs: object) -> object:
            raise AssertionError("network access detected")

        monkeypatch.setattr(socket, "create_connection", _block_network)
        monkeypatch.setattr(urllib.request, "urlopen", _block_network)

        result = convert_staged_manifest(DOWNLOAD_MANIFEST)
        assert not result.receipt.ok
        codes = _error_codes(result)
        assert "V2_CONVERSION_PENDING_DOWNLOAD" in codes

    def test_pending_download_no_network_attempted(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _fail_everything(*args: object, **kwargs: object) -> object:
            raise AssertionError("network access detected")

        monkeypatch.setattr(socket, "create_connection", _fail_everything)
        monkeypatch.setattr(socket, "socket", _fail_everything)
        monkeypatch.setattr(urllib.request, "urlopen", _fail_everything)
        monkeypatch.setattr(urllib.request, "urlretrieve", _fail_everything)

        result = convert_staged_manifest(DOWNLOAD_MANIFEST)
        assert not result.receipt.ok
        assert any(
            "PENDING_DOWNLOAD" in c for c in _error_codes(result)
        )

    def test_cli_staging_download_without_allow_flag_is_pending(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _block_network(*args: object, **kwargs: object) -> object:
            raise AssertionError("network access detected")

        monkeypatch.setattr(socket, "create_connection", _block_network)
        monkeypatch.setattr(urllib.request, "urlopen", _block_network)

        # CLI staging without --allow-download produces pending_download status
        exit_code = v2_stage_source_main(["--manifest", str(DOWNLOAD_MANIFEST)])
        assert exit_code == 0  # staging itself succeeds, status is pending_download


# ---------------------------------------------------------------------------
# Test 5: Rejects checksum mismatch
# ---------------------------------------------------------------------------


class TestRejectsChecksumMismatch:
    """ETL CLI rejects a manifest whose checksum does not match the data file."""

    def test_convert_staged_manifest_rejects_checksum_mismatch(self) -> None:
        result = convert_staged_manifest(CHECKSUM_MISMATCH_MANIFEST)
        assert not result.receipt.ok
        codes = _error_codes(result)
        assert any(
            "CHECKSUM_MISMATCH" in c for c in codes
        ), f"expected CHECKSUM_MISMATCH error, got {codes}"

    def test_checksum_error_is_from_staging(self) -> None:
        """Checksum mismatch is caught during staging, before conversion."""
        result = convert_staged_manifest(CHECKSUM_MISMATCH_MANIFEST)
        assert not result.receipt.ok
        codes = _error_codes(result)
        assert "V2_INTAKE_CHECKSUM_MISMATCH" in codes

    def test_cli_main_rejects_checksum_mismatch(self) -> None:
        exit_code = v2_stage_source_main(
            ["--manifest", str(CHECKSUM_MISMATCH_MANIFEST)]
        )
        assert exit_code != 0


# ---------------------------------------------------------------------------
# Test 6: Rejects missing license audit ref
# ---------------------------------------------------------------------------


class TestRejectsMissingLicenseAuditRef:
    """ETL CLI rejects a manifest with missing or empty license_audit_ref."""

    def test_convert_staged_manifest_rejects_empty_license_audit_ref(self) -> None:
        result = convert_staged_manifest(MISSING_LICENSE_AUDIT_MANIFEST)
        assert not result.receipt.ok
        codes = _error_codes(result)
        assert any(
            "MISSING_REQUIRED_FIELD" in c for c in codes
        ), f"expected MISSING_REQUIRED_FIELD error, got {codes}"

    def test_error_references_license_audit_ref_field(self) -> None:
        result = convert_staged_manifest(MISSING_LICENSE_AUDIT_MANIFEST)
        assert not result.receipt.ok
        error_msgs = " ".join(e.message for e in result.receipt.errors).lower()
        assert any(
            word in error_msgs for word in ("license", "audit")
        ), f"error must reference license_audit_ref: {error_msgs}"

    def test_cli_main_rejects_missing_license_audit_ref(self) -> None:
        exit_code = v2_stage_source_main(
            ["--manifest", str(MISSING_LICENSE_AUDIT_MANIFEST)]
        )
        assert exit_code != 0


# ---------------------------------------------------------------------------
# Test 7: Rejects unknown/blocked training eligibility
# ---------------------------------------------------------------------------


class TestRejectsBlockedTrainingEligibility:
    """ETL CLI rejects a manifest containing forbidden task-43+ fields."""

    def test_convert_staged_manifest_rejects_training_eligible_field(self) -> None:
        result = convert_staged_manifest(FORBIDDEN_TRAINING_MANIFEST)
        assert not result.receipt.ok
        codes = _error_codes(result)
        assert "V2_MANIFEST_FORBIDDEN_FIELD" in codes

    def test_error_references_training_eligible(self) -> None:
        result = convert_staged_manifest(FORBIDDEN_TRAINING_MANIFEST)
        assert not result.receipt.ok
        error_msgs = " ".join(e.message for e in result.receipt.errors).lower()
        assert any(
            word in error_msgs for word in ("training_eligible", "forbidden", "later task")
        ), f"error must reference training_eligible: {error_msgs}"

    def test_other_forbidden_fields_also_rejected(self, tmp_path: Path) -> None:
        """Manifest with training_split field is rejected."""
        manifest = tmp_path / "manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "schema_version": "1.0.0",
                    "contract_version": "v2-beta",
                    "source_name": "CovalentInDB",
                    "intake_mode": "manual",
                    "manual_path": "data.tsv",
                    "checksum": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                    "checksum_algorithm": "sha256",
                    "parser_target": "covalentin_db",
                    "retrieval_date": "2026-06-16",
                    "license_audit_ref": "audit/covalentindb/license.json",
                    "access_notes": "test: forbidden training_split",
                    "training_split": "train",
                },
                sort_keys=True,
                separators=(",", ":"),
            ),
            encoding="utf-8",
        )

        result = convert_staged_manifest(manifest)
        assert not result.receipt.ok
        assert "V2_MANIFEST_FORBIDDEN_FIELD" in _error_codes(result)

    def test_cli_main_rejects_training_eligible(self) -> None:
        exit_code = v2_stage_source_main(
            ["--manifest", str(FORBIDDEN_TRAINING_MANIFEST)]
        )
        assert exit_code != 0


# ---------------------------------------------------------------------------
# Test 8: Converts supported source to SourceIngestRecord
# ---------------------------------------------------------------------------


class TestConvertsSupportedSourceToSourceIngestRecord:
    """ETL CLI successfully converts a supported source to SourceIngestRecord records."""

    def test_convert_staged_manifest_produces_records(self, tmp_path: Path) -> None:
        data_file = tmp_path / "data.tsv"
        data_file.write_text(
            "pdb_id\tuniprot_id\tresidue\tresidue_number\tligand\t"
            "ligand_name\tbond_type\twarhead_type\n"
            "1abc\tP00001\tCYS145\t145\tLIG\tligand\tcovalent\tacrylamide\n"
            "2xyz\tQ00002\tSER200\t200\tLIG2\tligand2\tnoncovalent\tnone\n"
            "3def\tR00003\tLYS55\t55\tLIG3\tligand3\tcovalent\tvinyl_sulfone\n",
            encoding="utf-8",
        )
        manifest = _write_manual_manifest(tmp_path, data_file=data_file)

        result = convert_staged_manifest(manifest)

        assert result.receipt.ok
        assert result.payload is not None
        assert len(result.payload) == 3

        for record in result.payload:
            assert isinstance(record, SourceIngestRecord)
            assert record.source_database == "CovalentInDB"
            assert record.source_version == "v2"
            assert record.source_record_id
            assert record.row_index >= 1
            assert record.raw_file_path
            assert record.raw_file_sha256

    def test_output_preserves_provenance_fields(self, tmp_path: Path) -> None:
        data_file = tmp_path / "data.tsv"
        data_file.write_text(
            "pdb_id\tuniprot_id\tresidue\tresidue_number\tligand\t"
            "ligand_name\tbond_type\twarhead_type\n"
            "1abc\tP00001\tCYS145\t145\tLIG\tligand\tcovalent\tacrylamide\n",
            encoding="utf-8",
        )
        url = "https://example.invalid/provenance/test.tsv"
        license_ref = "audit/test/license.json"
        manifest = _write_manual_manifest(
            tmp_path,
            data_file=data_file,
            source_url=url,
            license_audit_ref=license_ref,
        )

        result = convert_staged_manifest(manifest)
        assert result.receipt.ok

        for record in result.payload:
            # Checksum preserved
            assert record.raw_file_sha256 == _sha256_file(data_file)
            # Source URL preserved
            url_ref = record.lineage.get("source_url") or record.metadata.get(
                "source_url"
            )
            assert url_ref == url
            # License audit ref preserved
            license_ref_found = record.lineage.get(
                "license_audit_ref"
            ) or record.metadata.get("license_audit_ref")
            assert license_ref_found == license_ref
            # Local path preserved
            assert str(data_file) in str(record.raw_file_path)

    def test_convert_staged_manifest_with_existing_conversion_fixture(
        self, tmp_path: Path
    ) -> None:
        """End-to-end: convert the valid covalentin_db conversion fixture."""
        from covalent_design.data.v2_conversion import convert_staged_source

        manifest = _write_manual_manifest(tmp_path, data_file=MANUAL_VALID_DATA)
        staging_envelope = stage_source_manifest(manifest)
        assert staging_envelope.receipt.ok

        result = convert_staged_source(staging_envelope)
        assert result.receipt.ok
        assert len(result.payload) == 3
        for record in result.payload:
            assert isinstance(record, SourceIngestRecord)

    def test_output_is_deterministic(self, tmp_path: Path) -> None:
        data_file = tmp_path / "data.tsv"
        data_file.write_text(
            "pdb_id\tuniprot_id\tresidue\tresidue_number\tligand\t"
            "ligand_name\tbond_type\twarhead_type\n"
            "1abc\tP00001\tCYS145\t145\tLIG\tligand\tcovalent\tacrylamide\n",
            encoding="utf-8",
        )
        manifest1 = _write_manual_manifest(tmp_path, data_file=data_file)
        manifest2 = _write_manual_manifest(tmp_path, data_file=data_file)

        result1 = convert_staged_manifest(manifest1)
        result2 = convert_staged_manifest(manifest2)

        assert len(result1.payload) == len(result2.payload)
        for r1, r2 in zip(result1.payload, result2.payload):
            assert r1 == r2

    def test_no_files_written_during_etl(self, tmp_path: Path) -> None:
        data_file = tmp_path / "data.tsv"
        data_file.write_text(
            "pdb_id\tuniprot_id\tresidue\tresidue_number\tligand\t"
            "ligand_name\tbond_type\twarhead_type\n"
            "1abc\tP00001\tCYS145\t145\tLIG\tligand\tcovalent\tacrylamide\n",
            encoding="utf-8",
        )
        manifest = _write_manual_manifest(tmp_path, data_file=data_file)

        before = set(p.relative_to(tmp_path) for p in tmp_path.rglob("*"))

        result = convert_staged_manifest(manifest)

        after = set(p.relative_to(tmp_path) for p in tmp_path.rglob("*"))
        # Only manifest.json and data.tsv existed before
        new_files = after - before
        assert not new_files, f"unexpected files written during ETL: {new_files}"
        assert result.receipt.ok


# ---------------------------------------------------------------------------
# No network during ETL CLI
# ---------------------------------------------------------------------------


class TestNoNetworkDuringEtlCli:
    """The ETL CLI must never attempt network access during staging or conversion."""

    def test_no_network_attempted_with_manual_manifest(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        def _fail_everything(*args: object, **kwargs: object) -> object:
            raise AssertionError("network access detected")

        monkeypatch.setattr(socket, "create_connection", _fail_everything)
        monkeypatch.setattr(socket, "socket", _fail_everything)
        monkeypatch.setattr(urllib.request, "urlopen", _fail_everything)
        monkeypatch.setattr(urllib.request, "urlretrieve", _fail_everything)

        data_file = tmp_path / "data.tsv"
        data_file.write_text(
            "pdb_id\tuniprot_id\tresidue\tresidue_number\tligand\t"
            "ligand_name\tbond_type\twarhead_type\n"
            "1abc\tP00001\tCYS145\t145\tLIG\tligand\tcovalent\tacrylamide\n",
            encoding="utf-8",
        )
        manifest = _write_manual_manifest(tmp_path, data_file=data_file)

        result = convert_staged_manifest(manifest)
        assert result.receipt.ok

    def test_no_network_attempted_cli_main(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _fail_everything(*args: object, **kwargs: object) -> object:
            raise AssertionError("network access detected")

        monkeypatch.setattr(socket, "create_connection", _fail_everything)
        monkeypatch.setattr(urllib.request, "urlopen", _fail_everything)

        exit_code = v2_stage_source_main(["--manifest", str(DOWNLOAD_MANIFEST)])
        # Download manifest without --allow-download succeeds (pending_download)
        assert exit_code == 0


# ---------------------------------------------------------------------------
# No training artifacts in ETL output
# ---------------------------------------------------------------------------


class TestNoTrainingArtifactsFromEtl:
    """ETL output records must not contain training eligibility or model fields."""

    def test_etl_output_free_of_training_attributes(self, tmp_path: Path) -> None:
        data_file = tmp_path / "data.tsv"
        data_file.write_text(
            "pdb_id\tuniprot_id\tresidue\tresidue_number\tligand\t"
            "ligand_name\tbond_type\twarhead_type\n"
            "1abc\tP00001\tCYS145\t145\tLIG\tligand\tcovalent\tacrylamide\n",
            encoding="utf-8",
        )
        manifest = _write_manual_manifest(tmp_path, data_file=data_file)

        result = convert_staged_manifest(manifest)
        assert result.receipt.ok

        forbidden_attrs = {
            "training_eligible",
            "training_split",
            "license_eligibility",
            "license_status",
            "split_assignment",
            "model_artifacts",
            "inference_artifacts",
        }
        for record in result.payload:
            record_attrs = set(dir(record))
            assert forbidden_attrs.isdisjoint(record_attrs), (
                f"record must not contain forbidden attributes: "
                f"{forbidden_attrs & record_attrs}"
            )
            for field in forbidden_attrs:
                assert field not in record.metadata
                assert field not in record.lineage


# ---------------------------------------------------------------------------
# Structured error contract (CLI level)
# ---------------------------------------------------------------------------


class TestStructuredErrorsFromEtl:
    """All errors from the ETL pipeline use structured error codes."""

    def test_errors_have_owner_data(self, tmp_path: Path) -> None:
        manifest = tmp_path / "manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "schema_version": "1.0.0",
                    "contract_version": "v2-beta",
                    "source_name": "CovalentInDB",
                    "intake_mode": "manual",
                    "manual_path": "nonexistent_file.tsv",
                    "checksum": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                    "checksum_algorithm": "sha256",
                    "parser_target": "covalentin_db",
                    "retrieval_date": "2026-06-16",
                    "license_audit_ref": "audit/covalentindb/license.json",
                    "access_notes": "test: structured errors",
                },
                sort_keys=True,
                separators=(",", ":"),
            ),
            encoding="utf-8",
        )

        result = convert_staged_manifest(manifest)
        assert not result.receipt.ok
        for error in result.receipt.errors:
            assert error.owner == "data"
            assert error.code
            assert error.message

    def test_errors_use_staging_or_conversion_prefix(self, tmp_path: Path) -> None:
        manifest = tmp_path / "manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "schema_version": "1.0.0",
                    "contract_version": "v2-beta",
                    "source_name": "CovalentInDB",
                    "intake_mode": "manual",
                    "manual_path": "nonexistent_file.tsv",
                    "checksum": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                    "checksum_algorithm": "sha256",
                    "parser_target": "covalentin_db",
                    "retrieval_date": "2026-06-16",
                    "license_audit_ref": "audit/covalentindb/license.json",
                    "access_notes": "test: error prefix",
                },
                sort_keys=True,
                separators=(",", ":"),
            ),
            encoding="utf-8",
        )

        result = convert_staged_manifest(manifest)
        assert not result.receipt.ok
        for error in result.receipt.errors:
            assert error.code.startswith("V2_"), (
                f"error code must start with V2_: {error.code}"
            )
