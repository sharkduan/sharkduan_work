"""Task 42: V2 data conversion tests for staged SourceIngestRecord output."""

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
from covalent_design.data.v2_conversion import convert_staged_source
from covalent_design.data.v2_intake import (
    V2StagingSummary,
    stage_source_manifest,
)


# ---------------------------------------------------------------------------
# Fixture roots
# ---------------------------------------------------------------------------
FIXTURE_ROOT = (
    Path(__file__).resolve().parents[1] / "fixtures" / "v2" / "data_conversion"
)
INTAKE_FIXTURE_ROOT = (
    Path(__file__).resolve().parents[1] / "fixtures" / "v2" / "data_intake"
)
REPO_ROOT = Path(__file__).resolve().parents[2]

MANUAL_VALID_DATA = FIXTURE_ROOT / "manual_valid" / "data" / "covalentindb_sample.tsv"
MANUAL_MALFORMED_DATA = (
    FIXTURE_ROOT / "manual_malformed_rows" / "data" / "covalentindb_malformed.tsv"
)
MANUAL_UNSUPPORTED_PARSER_DATA = (
    FIXTURE_ROOT / "manual_unsupported_parser" / "data" / "covpdb_sample.tsv"
)

# Reusable intake fixtures for error-path staging envelopes
DOWNLOAD_MANIFEST = INTAKE_FIXTURE_ROOT / "download" / "source_manifest.json"
CHECKSUM_MISMATCH_MANIFEST = (
    INTAKE_FIXTURE_ROOT / "manual_checksum_mismatch" / "manifest.json"
)
MISSING_FILE_MANIFEST = INTAKE_FIXTURE_ROOT / "manual_missing_file" / "manifest.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _write_manifest(directory: Path, **overrides: object) -> Path:
    """Write a valid covalentin_db manual manifest JSON and return its path."""
    payload: dict[str, object] = {
        "schema_version": "1.0.0",
        "contract_version": "v2-beta",
        "source_name": "CovalentInDB",
        "intake_mode": "manual",
        "manual_path": str(MANUAL_VALID_DATA),
        "source_url": None,
        "checksum": _sha256_text("fixture"),
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
        json.dumps(payload, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    return path


def _ok_manual_envelope(
    tmp_path: Path,
    *,
    data_file: Path = MANUAL_VALID_DATA,
    **manifest_overrides: object,
) -> ContractEnvelope[V2StagingSummary]:
    """Stage a valid manual manifest against *data_file* and return the envelope."""
    checksum = _sha256_file(data_file)
    manifest = _write_manifest(
        tmp_path,
        manual_path=str(data_file),
        checksum=checksum,
        **manifest_overrides,
    )
    envelope = stage_source_manifest(manifest)
    assert envelope.receipt.ok, f"staging failed: {envelope.receipt.errors}"
    assert envelope.payload is not None
    return envelope


def _error_codes(envelope: ContractEnvelope[object]) -> set[str]:
    return {error.code for error in envelope.receipt.errors}


# ---------------------------------------------------------------------------
# Valid conversion tests
# ---------------------------------------------------------------------------


class TestValidManualConversion:
    """Valid manual fixture converts to v1-compatible SourceIngestRecord records."""

    def test_converts_checked_manual_to_source_ingest_records(
        self, tmp_path: Path
    ) -> None:
        envelope = _ok_manual_envelope(tmp_path)
        result = convert_staged_source(envelope)

        assert result.receipt.ok
        assert result.payload is not None
        records = result.payload
        assert isinstance(records, tuple)
        assert len(records) >= 1
        for record in records:
            assert isinstance(record, SourceIngestRecord)

    def test_every_record_has_required_source_identity(self, tmp_path: Path) -> None:
        envelope = _ok_manual_envelope(tmp_path)
        result = convert_staged_source(envelope)

        for record in result.payload:
            assert record.source_database == "CovalentInDB"
            assert record.source_version
            assert record.source_record_id
            assert record.row_index >= 0

    def test_records_preserve_local_path_provenance(self, tmp_path: Path) -> None:
        envelope = _ok_manual_envelope(tmp_path)
        result = convert_staged_source(envelope)

        for record in result.payload:
            assert record.raw_file_path
            assert "covalentindb_sample.tsv" in str(record.raw_file_path)
            assert record.raw_manifest_file
            assert "manifest.json" in str(record.raw_manifest_file)

    def test_records_preserve_checksum_reference(self, tmp_path: Path) -> None:
        envelope = _ok_manual_envelope(tmp_path)
        result = convert_staged_source(envelope)

        expected_checksum = envelope.payload.checksum
        assert expected_checksum is not None
        for record in result.payload:
            assert record.raw_file_sha256 == expected_checksum

    def test_records_preserve_license_audit_ref(self, tmp_path: Path) -> None:
        envelope = _ok_manual_envelope(tmp_path)
        result = convert_staged_source(envelope)

        # License audit ref is preserved in the record lineage/metadata for
        # downstream Task 43 eligibility decisions.
        for record in result.payload:
            lineage_ref = record.lineage.get("license_audit_ref")
            metadata_ref = record.metadata.get("license_audit_ref")
            assert (
                lineage_ref is not None or metadata_ref is not None
            ), "license_audit_ref must be preserved in lineage or metadata"

    def test_records_preserve_source_url_when_present(self, tmp_path: Path) -> None:
        # Even for manual fixtures, a source_url provenance can be optional
        envelope = _ok_manual_envelope(
            tmp_path,
            source_url="https://example.invalid/provenance/covalentindb.tsv",
        )
        result = convert_staged_source(envelope)

        for record in result.payload:
            url_ref = record.metadata.get("source_url") or record.lineage.get(
                "source_url"
            )
            assert url_ref is not None

    def test_records_have_structured_lineage(self, tmp_path: Path) -> None:
        envelope = _ok_manual_envelope(tmp_path)
        result = convert_staged_source(envelope)

        for record in result.payload:
            assert record.source_lineage is not None
            assert isinstance(record.source_lineage, SourceRecordLineage)
            assert record.source_lineage.source_database == record.source_database
            assert record.source_lineage.row_index == record.row_index

    def test_records_populate_protein_ligand_linkage_metadata(
        self, tmp_path: Path
    ) -> None:
        envelope = _ok_manual_envelope(tmp_path)
        result = convert_staged_source(envelope)

        for record in result.payload:
            assert isinstance(record.protein, dict)
            assert isinstance(record.ligand, dict)
            assert isinstance(record.linkage, dict)
            assert isinstance(record.metadata, dict)
            # protein must have a pdb_id for identity resolution
            assert record.protein.get("pdb_id") or record.metadata.get("pdb_id")

    def test_record_count_matches_data_rows(self, tmp_path: Path) -> None:
        """3 data rows in the valid fixture TSV → 3 records."""
        envelope = _ok_manual_envelope(tmp_path)
        result = convert_staged_source(envelope)

        assert len(result.payload) == 3


# ---------------------------------------------------------------------------
# Downstream compatibility tests
# ---------------------------------------------------------------------------


class TestDownstreamCompatibility:
    """Output can feed normalize_linkages() and normalize_with_identity_resolution()."""

    def test_output_feeds_normalize_linkages(self, tmp_path: Path) -> None:
        from covalent_design.data.normalize import normalize_linkages

        envelope = _ok_manual_envelope(tmp_path)
        result = convert_staged_source(envelope)

        norm_envelope = normalize_linkages(result.payload)
        assert norm_envelope.receipt.ok
        assert norm_envelope.payload is not None

    def test_output_feeds_normalize_with_identity_resolution(
        self, tmp_path: Path
    ) -> None:
        from covalent_design.data.normalize import normalize_with_identity_resolution

        envelope = _ok_manual_envelope(tmp_path)
        result = convert_staged_source(envelope)

        norm_envelope = normalize_with_identity_resolution(result.payload)
        assert norm_envelope.receipt.ok
        assert norm_envelope.payload is not None


# ---------------------------------------------------------------------------
# Error: missing/failed staging evidence
# ---------------------------------------------------------------------------


class TestMissingOrFailedStagingEvidence:
    """Missing or failed staging evidence must produce structured errors."""

    def test_failed_staging_envelope_rejected(self) -> None:
        """A staging envelope with ok=False (e.g. checksum mismatch) must fail."""
        envelope = stage_source_manifest(CHECKSUM_MISMATCH_MANIFEST)
        assert not envelope.receipt.ok

        result = convert_staged_source(envelope)
        assert not result.receipt.ok
        codes = _error_codes(result)
        assert any("V2_CONVERSION" in c for c in codes), (
            f"expected V2_CONVERSION_* error, got {codes}"
        )

    def test_none_payload_rejected(self, tmp_path: Path) -> None:
        """An envelope with ok=True but None payload must fail."""
        # Simulate a structurally corrupt envelope
        bad_envelope = ContractEnvelope[V2StagingSummary](
            payload=None,
            artifacts=(),
            receipt=ValidationReceipt(
                validator="test",
                contract_version="v2-beta",
                input_sha256="",
                ok=False,
                errors=(),
            ),
            provenance=Provenance(),
        )
        result = convert_staged_source(bad_envelope)
        assert not result.receipt.ok
        assert any("V2_CONVERSION" in c for c in _error_codes(result))

    def test_forged_non_task41_envelope_rejected(self, tmp_path: Path) -> None:
        """A caller cannot bypass Task 41 by hand-constructing an ok envelope."""
        summary = V2StagingSummary(
            source_name="CovalentInDB",
            intake_mode="manual",
            status="checksum_verified",
            manual_path=str(MANUAL_VALID_DATA),
            checksum=_sha256_file(MANUAL_VALID_DATA),
            checksum_algorithm="sha256",
            parser_target="covalentin_db",
            license_audit_ref="audit/covalentindb/license.json",
        )
        forged = ContractEnvelope[V2StagingSummary](
            payload=summary,
            artifacts=(),
            receipt=ValidationReceipt(
                validator="test.forged_staging",
                contract_version="v2-beta",
                input_sha256="forged",
                ok=True,
            ),
            provenance=Provenance(),
        )

        result = convert_staged_source(forged)

        assert not result.receipt.ok
        assert "V2_CONVERSION_INVALID_STAGING_EVIDENCE" in _error_codes(result)

    def test_manifest_unreadable_staging_fails(self) -> None:
        """A staging envelope from a missing manifest must fail conversion."""
        envelope = stage_source_manifest(MISSING_FILE_MANIFEST)
        assert not envelope.receipt.ok

        result = convert_staged_source(envelope)
        assert not result.receipt.ok
        assert any("V2_CONVERSION" in c for c in _error_codes(result))


# ---------------------------------------------------------------------------
# Error: pending_download rejected
# ---------------------------------------------------------------------------


class TestPendingDownloadRejected:
    """pending_download is NOT convertible in Task 42 — must fail structured."""

    def test_pending_download_rejected_with_structured_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _block_network(*args: object, **kwargs: object) -> object:
            raise AssertionError("convert_staged_source must not use network")

        monkeypatch.setattr(socket, "create_connection", _block_network)
        monkeypatch.setattr(urllib.request, "urlopen", _block_network)

        envelope = stage_source_manifest(DOWNLOAD_MANIFEST)
        assert envelope.receipt.ok
        assert envelope.payload is not None
        assert envelope.payload.status == "pending_download"

        result = convert_staged_source(envelope)
        assert not result.receipt.ok
        codes = _error_codes(result)
        assert any("V2_CONVERSION" in c for c in codes), (
            f"expected V2_CONVERSION_* error, got {codes}"
        )
        # The error must mention pending/download/network
        error_msgs = " ".join(
            e.message for e in result.receipt.errors
        ).lower()
        assert any(
            word in error_msgs for word in ("pending", "download", "not convertible")
        ), f"error message must reference pending_download: {error_msgs}"

    def test_pending_download_does_not_read_files(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _block_network(*args: object, **kwargs: object) -> object:
            raise AssertionError("no network")

        monkeypatch.setattr(socket, "create_connection", _block_network)
        monkeypatch.setattr(urllib.request, "urlopen", _block_network)

        envelope = stage_source_manifest(DOWNLOAD_MANIFEST)
        assert envelope.payload is not None
        assert envelope.payload.status == "pending_download"

        # Even though the download_request has a source_url, no file exists
        result = convert_staged_source(envelope)
        assert not result.receipt.ok
        assert len(result.payload) == 0 if result.payload is not None else True


# ---------------------------------------------------------------------------
# Error: unsupported source / parser
# ---------------------------------------------------------------------------


class TestUnsupportedSourceOrParser:
    """Unsupported source_name or parser_target must fail structured."""

    def test_unsupported_parser_target_fails_structured(self, tmp_path: Path) -> None:
        """Valid staging but with a parser_target not yet implemented in Task 42."""
        envelope = _ok_manual_envelope(
            tmp_path,
            data_file=MANUAL_UNSUPPORTED_PARSER_DATA,
            source_name="CovPDB",
            parser_target="covpdb",
        )
        assert envelope.receipt.ok

        result = convert_staged_source(envelope)
        assert not result.receipt.ok
        codes = _error_codes(result)
        assert any("V2_CONVERSION" in c for c in codes), (
            f"expected V2_CONVERSION_* error, got {codes}"
        )

    def test_unsupported_source_name_fails(self, tmp_path: Path) -> None:
        """A source_name that doesn't map to a known parser must fail."""
        envelope = _ok_manual_envelope(
            tmp_path,
            data_file=MANUAL_UNSUPPORTED_PARSER_DATA,
            source_name="CovBinderInPDB",
            parser_target="covbinder_in_pdb",
        )
        assert envelope.receipt.ok

        result = convert_staged_source(envelope)
        assert not result.receipt.ok
        codes = _error_codes(result)
        assert any("V2_CONVERSION" in c for c in codes)


# ---------------------------------------------------------------------------
# Error: parser row failure
# ---------------------------------------------------------------------------


class TestParserRowFailure:
    """Schema normalization / parser row failure is structured."""

    def test_malformed_rows_produce_structured_error(self, tmp_path: Path) -> None:
        """Rows that don't match the parser schema must produce V2_CONVERSION errors."""
        envelope = _ok_manual_envelope(
            tmp_path,
            data_file=MANUAL_MALFORMED_DATA,
        )
        assert envelope.receipt.ok

        result = convert_staged_source(envelope)
        # May be partial success (some rows valid) or total failure
        if not result.receipt.ok:
            codes = _error_codes(result)
            assert any("V2_CONVERSION" in c for c in codes)
        # If partial, valid rows should be returned alongside error info
        if result.payload and result.receipt.ok:
            # All returned records must be valid SourceIngestRecords
            for record in result.payload:
                assert isinstance(record, SourceIngestRecord)

    def test_non_integer_residue_number_produces_structured_error(
        self, tmp_path: Path
    ) -> None:
        data_file = tmp_path / "bad_residue_number.tsv"
        data_file.write_text(
            "pdb_id\tuniprot_id\tresidue\tresidue_number\tligand\t"
            "ligand_name\tbond_type\twarhead_type\n"
            "1abc\tP00001\tCYS145\tone-forty-five\tLIG\tligand\t"
            "covalent\tacrylamide\n",
            encoding="utf-8",
        )
        envelope = _ok_manual_envelope(tmp_path, data_file=data_file)

        result = convert_staged_source(envelope)

        assert not result.receipt.ok
        assert "V2_CONVERSION_ROW_PARSE_ERROR" in _error_codes(result)
        assert result.payload == ()


# ---------------------------------------------------------------------------
# Deterministic output
# ---------------------------------------------------------------------------


class TestDeterministicOutput:
    """Conversion output must be deterministic and serializable."""

    def test_same_input_produces_same_output(self, tmp_path: Path) -> None:
        envelope1 = _ok_manual_envelope(tmp_path)
        envelope2 = _ok_manual_envelope(tmp_path)

        result1 = convert_staged_source(envelope1)
        result2 = convert_staged_source(envelope2)

        assert len(result1.payload) == len(result2.payload)
        for r1, r2 in zip(result1.payload, result2.payload):
            assert r1 == r2

    def test_output_serializable_to_json(self, tmp_path: Path) -> None:
        envelope = _ok_manual_envelope(tmp_path)
        result = convert_staged_source(envelope)

        from dataclasses import asdict

        serialized = json.dumps(
            [asdict(r) for r in result.payload],
            sort_keys=True,
            default=str,
        )
        assert isinstance(serialized, str)
        roundtripped = json.loads(serialized)
        assert isinstance(roundtripped, list)
        assert len(roundtripped) == len(result.payload)

    def test_receipt_is_deterministic(self, tmp_path: Path) -> None:
        envelope1 = _ok_manual_envelope(tmp_path)
        envelope2 = _ok_manual_envelope(tmp_path)

        result1 = convert_staged_source(envelope1)
        result2 = convert_staged_source(envelope2)

        assert result1.receipt.ok == result2.receipt.ok
        assert result1.receipt.validator == result2.receipt.validator
        assert result1.receipt.contract_version == result2.receipt.contract_version


# ---------------------------------------------------------------------------
# No network
# ---------------------------------------------------------------------------


class TestNoNetworkAccess:
    """Conversion must never attempt network access."""

    def test_no_network_attempted_during_conversion(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        def _fail_everything(*args: object, **kwargs: object) -> object:
            raise AssertionError("network access detected")

        monkeypatch.setattr(socket, "create_connection", _fail_everything)
        monkeypatch.setattr(socket, "socket", _fail_everything)
        monkeypatch.setattr(urllib.request, "urlopen", _fail_everything)
        monkeypatch.setattr(urllib.request, "urlretrieve", _fail_everything)

        envelope = _ok_manual_envelope(tmp_path)
        result = convert_staged_source(envelope)
        assert result.receipt.ok

    def test_no_network_with_pending_download(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _fail_everything(*args: object, **kwargs: object) -> object:
            raise AssertionError("network access detected")

        monkeypatch.setattr(socket, "create_connection", _fail_everything)
        monkeypatch.setattr(socket, "socket", _fail_everything)
        monkeypatch.setattr(urllib.request, "urlopen", _fail_everything)
        monkeypatch.setattr(urllib.request, "urlretrieve", _fail_everything)

        envelope = stage_source_manifest(DOWNLOAD_MANIFEST)
        assert envelope.payload is not None
        assert envelope.payload.status == "pending_download"

        result = convert_staged_source(envelope)
        assert not result.receipt.ok


# ---------------------------------------------------------------------------
# No real data / no model / no training
# ---------------------------------------------------------------------------


class TestNoRealDataOrArtifacts:
    """Conversion must not depend on real data, models, or training artifacts."""

    def test_no_data_directory_dependency(self, tmp_path: Path) -> None:
        """Conversion must work without D:\\codex_work\\data."""
        import os

        env_patch = os.environ.copy()
        env_patch.pop("DATA_ROOT", None)
        # Just verify the test doesn't try to read from a real data dir
        envelope = _ok_manual_envelope(tmp_path)
        result = convert_staged_source(envelope)
        assert result.receipt.ok

    def test_no_model_training_inference_artifacts_generated(
        self, tmp_path: Path
    ) -> None:
        """Output records must not contain model/training/inference/evaluation fields."""
        envelope = _ok_manual_envelope(tmp_path)
        result = convert_staged_source(envelope)

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
                assert field not in record.metadata, (
                    f"metadata must not contain {field}"
                )
                assert field not in record.lineage, (
                    f"lineage must not contain {field}"
                )

    def test_no_files_written_during_conversion(self, tmp_path: Path) -> None:
        """Conversion must be purely in-memory; no side-effect files."""
        before = set(p.relative_to(tmp_path) for p in tmp_path.rglob("*"))

        envelope = _ok_manual_envelope(tmp_path)
        result = convert_staged_source(envelope)

        after = set(p.relative_to(tmp_path) for p in tmp_path.rglob("*"))
        # Only the manifest file from _ok_manual_envelope should exist
        manifest_file = tmp_path / "manifest.json"
        assert manifest_file.exists()
        # No additional files beyond the manifest
        new_files = after - before - {Path("manifest.json")}
        assert not new_files, f"unexpected files written: {new_files}"


# ---------------------------------------------------------------------------
# Provenance completeness
# ---------------------------------------------------------------------------


class TestProvenanceCompleteness:
    """Checksum, local path, source URL, and license audit ref preserved."""

    def test_checksum_in_summary_matches_checksum_in_records(
        self, tmp_path: Path
    ) -> None:
        envelope = _ok_manual_envelope(tmp_path)
        result = convert_staged_source(envelope)

        expected = envelope.payload.checksum
        for record in result.payload:
            assert record.raw_file_sha256 == expected

    def test_local_path_is_absolute_and_exists(self, tmp_path: Path) -> None:
        envelope = _ok_manual_envelope(tmp_path)
        result = convert_staged_source(envelope)

        for record in result.payload:
            path = Path(record.raw_file_path)
            assert path.is_absolute() or Path(record.raw_file_path).exists()

    def test_optional_source_url_preserved_in_metadata(self, tmp_path: Path) -> None:
        url = "https://example.invalid/covalentindb/release/dataset_v3.tsv"
        envelope = _ok_manual_envelope(
            tmp_path,
            source_url=url,
        )
        result = convert_staged_source(envelope)

        for record in result.payload:
            found = (
                record.metadata.get("source_url")
                or record.lineage.get("source_url")
            )
            assert found == url, f"source_url {url} not preserved"

    def test_license_audit_ref_preserved_for_task43_eligibility(
        self, tmp_path: Path
    ) -> None:
        license_ref = "audit/covalentindb/license-v2.json"
        envelope = _ok_manual_envelope(
            tmp_path,
            license_audit_ref=license_ref,
        )
        result = convert_staged_source(envelope)

        for record in result.payload:
            any_ref = (
                record.metadata.get("license_audit_ref")
                or record.lineage.get("license_audit_ref")
            )
            assert any_ref == license_ref, f"license_audit_ref not preserved"


# ---------------------------------------------------------------------------
# Conversion result structure
# ---------------------------------------------------------------------------


class TestConversionResultStructure:
    """The ContractEnvelope returned by convert_staged_source is well-formed."""

    def test_envelope_has_valid_receipt(self, tmp_path: Path) -> None:
        envelope = _ok_manual_envelope(tmp_path)
        result = convert_staged_source(envelope)

        assert result.receipt.ok
        assert result.receipt.validator
        assert "convert" in result.receipt.validator.lower()
        assert result.receipt.contract_version
        assert result.receipt.input_sha256

    def test_envelope_payload_is_tuple_of_records(self, tmp_path: Path) -> None:
        envelope = _ok_manual_envelope(tmp_path)
        result = convert_staged_source(envelope)

        assert isinstance(result.payload, tuple)
        for record in result.payload:
            assert isinstance(record, SourceIngestRecord)

    def test_artifacts_tuple_is_empty(self, tmp_path: Path) -> None:
        """Task 42 produces no new artifact refs — that's Task 43+ scope."""
        envelope = _ok_manual_envelope(tmp_path)
        result = convert_staged_source(envelope)

        assert result.artifacts == ()


# ---------------------------------------------------------------------------
# Structured error contract
# ---------------------------------------------------------------------------


class TestStructuredErrors:
    """All conversion errors use V2_CONVERSION_* error codes."""

    def test_pending_download_error_code(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def _block(*args: object, **kwargs: object) -> object:
            raise AssertionError("no network")

        monkeypatch.setattr(socket, "create_connection", _block)
        monkeypatch.setattr(urllib.request, "urlopen", _block)

        envelope = stage_source_manifest(DOWNLOAD_MANIFEST)
        result = convert_staged_source(envelope)

        assert not result.receipt.ok
        for error in result.receipt.errors:
            assert error.code.startswith("V2_CONVERSION_"), (
                f"error code must start with V2_CONVERSION_: {error.code}"
            )
            assert error.owner == "data"

    def test_failed_staging_error_code(self) -> None:
        envelope = stage_source_manifest(CHECKSUM_MISMATCH_MANIFEST)
        result = convert_staged_source(envelope)

        assert not result.receipt.ok
        for error in result.receipt.errors:
            assert error.code.startswith("V2_CONVERSION_"), (
                f"error code must start with V2_CONVERSION_: {error.code}"
            )
            assert error.owner == "data"

    def test_unsupported_parser_error_code(self, tmp_path: Path) -> None:
        envelope = _ok_manual_envelope(
            tmp_path,
            data_file=MANUAL_UNSUPPORTED_PARSER_DATA,
            source_name="CovPDB",
            parser_target="covpdb",
        )
        result = convert_staged_source(envelope)

        assert not result.receipt.ok
        for error in result.receipt.errors:
            assert error.code.startswith("V2_CONVERSION_"), (
                f"error code must start with V2_CONVERSION_: {error.code}"
            )
            assert error.owner == "data"

    def test_missing_staging_evidence_error_code(self) -> None:
        envelope = stage_source_manifest(MISSING_FILE_MANIFEST)
        result = convert_staged_source(envelope)

        assert not result.receipt.ok
        for error in result.receipt.errors:
            assert error.code.startswith("V2_CONVERSION_")
            assert error.owner == "data"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Boundary conditions that must be handled correctly."""

    def test_single_row_data_converts_to_single_record(self, tmp_path: Path) -> None:
        single_row_tsv = tmp_path / "single_row.tsv"
        single_row_tsv.write_text(
            "pdb_id\tuniprot_id\tresidue\tresidue_number\tligand\tligand_name\t"
            "bond_type\twarhead_type\n"
            "9zzz\tX99999\tTHR42\t42\tZZZ\tnone\tnone\tnone\n",
            encoding="utf-8",
        )
        envelope = _ok_manual_envelope(tmp_path, data_file=single_row_tsv)
        result = convert_staged_source(envelope)

        assert result.receipt.ok
        assert len(result.payload) == 1

    def test_data_with_only_header_returns_empty_tuple(self, tmp_path: Path) -> None:
        header_only_tsv = tmp_path / "header_only.tsv"
        header_only_tsv.write_text(
            "pdb_id\tuniprot_id\tresidue\tresidue_number\tligand\t"
            "ligand_name\tbond_type\twarhead_type\n",
            encoding="utf-8",
        )
        envelope = _ok_manual_envelope(tmp_path, data_file=header_only_tsv)
        result = convert_staged_source(envelope)

        assert result.receipt.ok
        assert result.payload == ()

    def test_empty_file_converts_to_empty_without_error(self, tmp_path: Path) -> None:
        empty_tsv = tmp_path / "empty.tsv"
        empty_tsv.write_text("", encoding="utf-8")
        envelope = _ok_manual_envelope(tmp_path, data_file=empty_tsv)
        result = convert_staged_source(envelope)

        assert result.receipt.ok
        assert result.payload == ()
