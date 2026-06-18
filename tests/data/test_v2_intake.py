"""Task 41: V2 data intake staging tests."""

from __future__ import annotations

import hashlib
import json
import os
import socket
import subprocess
import sys
import urllib.request
from pathlib import Path

import pytest

from covalent_design.contracts.types import ContractEnvelope
from covalent_design.data.v2_intake import (
    V2StagingSummary,
    stage_source_manifest,
)

# ---------------------------------------------------------------------------
# Fixture roots
# ---------------------------------------------------------------------------
FIXTURE_ROOT = (
    Path(__file__).resolve().parents[1] / "fixtures" / "v2" / "data_intake"
)
REPO_ROOT = Path(__file__).resolve().parents[2]
VALID_MANUAL_DATA = (
    FIXTURE_ROOT / "manual" / "data" / "covalentindb_sample.tsv"
)
VALID_DOWNLOAD_MANIFEST = FIXTURE_ROOT / "download" / "source_manifest.json"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _write_manifest(
    directory: Path,
    **overrides: object,
) -> Path:
    """Write a valid manifest JSON and return its path."""
    payload: dict[str, object] = {
        "schema_version": "1.0.0",
        "contract_version": "v2-beta",
        "source_name": "CovalentInDB",
        "intake_mode": "download",
        "source_url": "https://example.invalid/covalentindb/sample.tsv",
        "checksum": _sha256_text("fixture"),
        "checksum_algorithm": "sha256",
        "parser_target": "covalentin_db",
        "retrieval_date": "2026-06-16",
        "license_audit_ref": "audit/covalentindb/license.json",
        "access_notes": "generated test fixture",
    }
    payload.update(overrides)
    path = directory / "manifest.json"
    path.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    return path


def _error_codes(envelope: ContractEnvelope[object]) -> set[str]:
    return {error.code for error in envelope.receipt.errors}


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = "src"
    return subprocess.run(
        [sys.executable, "-m", "covalent_design.data.cli.v2_stage_source", *args],
        cwd=str(REPO_ROOT),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


# ===================================================================
# Manual staging tests
# ===================================================================


class TestManualStaging:
    """Tests for manual intake mode staging with file existence and
    checksum verification."""

    def test_valid_manual_verifies_file_and_checksum(self, tmp_path: Path) -> None:
        checksum = _sha256_file(VALID_MANUAL_DATA)
        manifest_path = _write_manifest(
            tmp_path,
            source_name="CovalentInDB",
            intake_mode="manual",
            manual_path=str(VALID_MANUAL_DATA),
            source_url=None,
            checksum=checksum,
            parser_target="covalentin_db",
        )

        envelope = stage_source_manifest(manifest_path)

        assert envelope.receipt.ok
        assert envelope.receipt.input_sha256 == hashlib.sha256(
            manifest_path.read_text(encoding="utf-8").encode("utf-8")
        ).hexdigest()
        assert isinstance(envelope.payload, V2StagingSummary)
        assert envelope.payload.source_name == "CovalentInDB"
        assert envelope.payload.intake_mode == "manual"
        assert envelope.payload.status == "checksum_verified"

    def test_missing_manual_path_fails(self, tmp_path: Path) -> None:
        manifest_path = FIXTURE_ROOT / "manual_missing_file" / "manifest.json"

        envelope = stage_source_manifest(manifest_path)

        assert not envelope.receipt.ok
        assert "V2_INTAKE_MANUAL_PATH_FILE_NOT_FOUND" in _error_codes(envelope)

    def test_checksum_mismatch_fails(self, tmp_path: Path) -> None:
        manifest_path = (
            FIXTURE_ROOT / "manual_checksum_mismatch" / "manifest.json"
        )

        envelope = stage_source_manifest(manifest_path)

        assert not envelope.receipt.ok
        assert "V2_INTAKE_CHECKSUM_MISMATCH" in _error_codes(envelope)


# ===================================================================
# Download staging tests
# ===================================================================


class TestDownloadStaging:
    """Tests for download intake mode staging without network access."""

    def test_valid_download_passes_without_network(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _block_network(*args: object, **kwargs: object) -> object:
            raise AssertionError("stage_source_manifest must not use network")

        monkeypatch.setattr(socket, "create_connection", _block_network)
        monkeypatch.setattr(urllib.request, "urlopen", _block_network)

        manifest_path = VALID_DOWNLOAD_MANIFEST
        envelope = stage_source_manifest(manifest_path)

        assert envelope.receipt.ok
        assert envelope.payload is not None
        assert envelope.payload.intake_mode == "download"
        assert envelope.payload.status in ("pending_download", "ok")
        assert envelope.payload.download_request is not None
        assert envelope.payload.download_request.source_url.startswith("https://")
        assert envelope.payload.download_request.intended_output_name
        assert envelope.payload.download_request.source_artifact_id
        assert envelope.payload.download_request.expected_checksum == envelope.payload.checksum
        assert envelope.payload.download_request.checksum_algorithm == "sha256"
        assert envelope.payload.download_request.license_audit_ref
        assert (
            envelope.payload.download_request.retrieval_metadata_placeholder[
                "network_access"
            ]
            == "not_performed_task41"
        )

    def test_allow_download_fails_structured_no_network(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _block_network(*args: object, **kwargs: object) -> object:
            raise AssertionError("must not attempt network download in Task 41")

        monkeypatch.setattr(socket, "create_connection", _block_network)
        monkeypatch.setattr(urllib.request, "urlopen", _block_network)

        manifest_path = VALID_DOWNLOAD_MANIFEST
        envelope = stage_source_manifest(
            manifest_path, allow_download=True
        )

        assert not envelope.receipt.ok
        assert "V2_INTAKE_DOWNLOAD_NOT_AVAILABLE" in _error_codes(envelope)

    def test_missing_source_url_fails(self) -> None:
        manifest_path = FIXTURE_ROOT / "download_missing_url" / "manifest.json"

        envelope = stage_source_manifest(manifest_path)

        assert not envelope.receipt.ok
        assert "V2_MANIFEST_SOURCE_URL_REQUIRED" in _error_codes(envelope)

    def test_no_network_access_whatsoever(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Prove that download validation never touches the network."""
        def _fail_everything(*args: object, **kwargs: object) -> object:
            raise AssertionError("network access detected")

        # Block every conceivable network path
        monkeypatch.setattr(socket, "create_connection", _fail_everything)
        monkeypatch.setattr(socket, "socket", _fail_everything)
        monkeypatch.setattr(urllib.request, "urlopen", _fail_everything)
        monkeypatch.setattr(urllib.request, "urlretrieve", _fail_everything)

        manifest_path = VALID_DOWNLOAD_MANIFEST
        envelope = stage_source_manifest(manifest_path)

        assert envelope.receipt.ok
        assert envelope.payload is not None
        assert envelope.payload.status in ("pending_download", "ok")


# ===================================================================
# Validation / error tests
# ===================================================================


class TestValidationErrors:
    """Tests that manifest-level validation errors propagate correctly."""

    def test_unknown_source_fails(self) -> None:
        manifest_path = FIXTURE_ROOT / "unknown_source" / "manifest.json"

        envelope = stage_source_manifest(manifest_path)

        assert not envelope.receipt.ok
        assert "V2_MANIFEST_UNKNOWN_SOURCE_NAME" in _error_codes(envelope)

    def test_unknown_intake_mode_fails(self) -> None:
        manifest_path = FIXTURE_ROOT / "unknown_intake_mode" / "manifest.json"

        envelope = stage_source_manifest(manifest_path)

        assert not envelope.receipt.ok
        assert "V2_MANIFEST_UNKNOWN_INTAKE_MODE" in _error_codes(envelope)


# ===================================================================
# Deterministic summary
# ===================================================================


class TestDeterministicSummary:
    """Tests that staging summaries are deterministic and machine-readable."""

    def test_summary_status_names_are_deterministic(
        self, tmp_path: Path
    ) -> None:
        checksum = _sha256_file(VALID_MANUAL_DATA)
        manifest_path = _write_manifest(
            tmp_path,
            source_name="CovalentInDB",
            intake_mode="manual",
            manual_path=str(VALID_MANUAL_DATA),
            source_url=None,
            checksum=checksum,
            parser_target="covalentin_db",
        )

        first = stage_source_manifest(manifest_path)
        second = stage_source_manifest(manifest_path)

        assert first.receipt.ok and second.receipt.ok
        assert first.payload is not None and second.payload is not None
        assert first.payload.status == second.payload.status
        assert first.payload.source_name == second.payload.source_name
        assert first.payload.intake_mode == second.payload.intake_mode

    def test_summary_serialization_is_stable(self, tmp_path: Path) -> None:
        checksum = _sha256_file(VALID_MANUAL_DATA)
        manifest_path = _write_manifest(
            tmp_path,
            source_name="CovalentInDB",
            intake_mode="manual",
            manual_path=str(VALID_MANUAL_DATA),
            source_url=None,
            checksum=checksum,
            parser_target="covalentin_db",
        )

        envelope = stage_source_manifest(manifest_path)
        summary = envelope.payload

        assert summary is not None
        d1 = {
            "source_name": summary.source_name,
            "intake_mode": summary.intake_mode,
            "status": summary.status,
        }
        d2 = {
            "source_name": summary.source_name,
            "intake_mode": summary.intake_mode,
            "status": summary.status,
        }
        assert d1 == d2
        assert json.dumps(d1, sort_keys=True) == json.dumps(
            d2, sort_keys=True
        )

    def test_status_names_are_machine_readable(
        self, tmp_path: Path
    ) -> None:
        """Status strings should be snake_case identifiers, not prose."""
        checksum = _sha256_file(VALID_MANUAL_DATA)
        manifest_path = _write_manifest(
            tmp_path,
            source_name="CovalentInDB",
            intake_mode="manual",
            manual_path=str(VALID_MANUAL_DATA),
            source_url=None,
            checksum=checksum,
            parser_target="covalentin_db",
        )

        envelope = stage_source_manifest(manifest_path)

        assert envelope.payload is not None
        status = envelope.payload.status
        assert status.islower() or "_" in status
        assert " " not in status


# ===================================================================
# No artifact generation
# ===================================================================


class TestNoArtifacts:
    """Task 41 must not generate conversion, license, or training artifacts."""

    def test_no_files_created_during_staging(self, tmp_path: Path) -> None:
        checksum = _sha256_file(VALID_MANUAL_DATA)
        manifest_path = _write_manifest(
            tmp_path,
            source_name="CovalentInDB",
            intake_mode="manual",
            manual_path=str(VALID_MANUAL_DATA),
            source_url=None,
            checksum=checksum,
            parser_target="covalentin_db",
        )

        before = set(p.relative_to(tmp_path) for p in tmp_path.rglob("*"))

        envelope = stage_source_manifest(manifest_path)

        after = set(p.relative_to(tmp_path) for p in tmp_path.rglob("*"))
        assert envelope.receipt.ok
        # Only the manifest file itself should exist; no new artifacts
        assert after == before

    def test_no_conversion_license_or_training_fields_in_summary(
        self, tmp_path: Path
    ) -> None:
        checksum = _sha256_file(VALID_MANUAL_DATA)
        manifest_path = _write_manifest(
            tmp_path,
            source_name="CovalentInDB",
            intake_mode="manual",
            manual_path=str(VALID_MANUAL_DATA),
            source_url=None,
            checksum=checksum,
            parser_target="covalentin_db",
        )

        envelope = stage_source_manifest(manifest_path)

        assert envelope.payload is not None
        forbidden_attrs = {
            "conversion_status",
            "license_eligibility",
            "license_status",
            "training_artifacts",
            "training_eligible",
            "training_split",
        }
        summary_attrs = set(
            attr
            for attr in dir(envelope.payload)
            if not attr.startswith("_")
        )
        assert forbidden_attrs.isdisjoint(summary_attrs)


# ===================================================================
# CLI tests
# ===================================================================


class TestCLI:
    """Integration tests for the v2_stage_source CLI."""

    def test_manual_exits_0_json(self, tmp_path: Path) -> None:
        checksum = _sha256_file(VALID_MANUAL_DATA)
        manifest_path = _write_manifest(
            tmp_path,
            source_name="CovalentInDB",
            intake_mode="manual",
            manual_path=str(VALID_MANUAL_DATA),
            source_url=None,
            checksum=checksum,
            parser_target="covalentin_db",
        )

        result = _run_cli("--manifest", str(manifest_path))

        assert result.returncode == 0, result.stderr
        summary = json.loads(result.stdout)
        assert summary["ok"] is True
        assert "status" in summary

    def test_download_exits_0_json(self, tmp_path: Path) -> None:
        manifest_path = VALID_DOWNLOAD_MANIFEST

        result = _run_cli("--manifest", str(manifest_path))

        assert result.returncode == 0, result.stderr
        summary = json.loads(result.stdout)
        assert summary["ok"] is True

    def test_invalid_exits_nonzero_json(self) -> None:
        manifest_path = FIXTURE_ROOT / "unknown_source" / "manifest.json"

        result = _run_cli("--manifest", str(manifest_path))

        assert result.returncode != 0
        summary = json.loads(result.stdout)
        assert summary["ok"] is False
        assert isinstance(summary.get("errors"), list)

    def test_cli_manual_with_output_root(self, tmp_path: Path) -> None:
        checksum = _sha256_file(VALID_MANUAL_DATA)
        manifest_path = _write_manifest(
            tmp_path,
            source_name="CovalentInDB",
            intake_mode="manual",
            manual_path=str(VALID_MANUAL_DATA),
            source_url=None,
            checksum=checksum,
            parser_target="covalentin_db",
        )
        output_root = tmp_path / "staging_output"

        result = _run_cli(
            "--manifest", str(manifest_path),
            "--output-root", str(output_root),
        )

        assert result.returncode == 0, result.stderr
        summary = json.loads(result.stdout)
        assert summary["ok"] is True

    def test_cli_allow_download_fails_structured(self, tmp_path: Path) -> None:
        manifest_path = VALID_DOWNLOAD_MANIFEST

        result = _run_cli(
            "--manifest", str(manifest_path),
            "--allow-download",
        )

        assert result.returncode != 0
        summary = json.loads(result.stdout)
        assert summary["ok"] is False
        errors = summary.get("errors", [])
        assert any(
            "DOWNLOAD" in err.get("code", "") for err in errors
        )
