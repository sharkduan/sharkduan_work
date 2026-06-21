from __future__ import annotations

import json
import socket
import urllib.request
from pathlib import Path

import pytest

from covalent_design.contracts.types import ContractEnvelope
from covalent_design.data.v2_manifests import (
    ALLOWED_CHECKSUM_ALGORITHMS,
    ALLOWED_INTAKE_MODES,
    ALLOWED_PARSER_TARGETS,
    ALLOWED_SOURCE_NAMES,
    V2DataIntakeManifest,
    serialize_v2_data_intake_manifest,
    v2_data_intake_manifest_from_dict,
    validate_v2_data_intake_manifest,
)


FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "v2" / "data_manifests"
VALID_SHA256 = "a" * 64


def manifest_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": "1.0.0",
        "contract_version": "v2-beta",
        "source_name": "CovPDB",
        "intake_mode": "download",
        "source_url": "https://example.invalid/covpdb.zip",
        "checksum": VALID_SHA256,
        "checksum_algorithm": "sha256",
        "parser_target": "covpdb",
        "retrieval_date": "2026-06-16",
        "license_audit_ref": "license-audit/covpdb.json",
        "access_notes": "fixture metadata only; no download is performed",
    }
    payload.update(overrides)
    return payload


def validate_payload(payload: dict[str, object]) -> ContractEnvelope[V2DataIntakeManifest | None]:
    return v2_data_intake_manifest_from_dict(payload)


def error_codes(envelope: ContractEnvelope[object]) -> set[str]:
    return {error.code for error in envelope.receipt.errors}


def test_valid_manual_manifest() -> None:
    envelope = validate_payload(
        manifest_payload(
            source_name="CovalentInDB",
            intake_mode="manual",
            manual_path="manual/covalentindb.tsv",
            source_url=None,
            parser_target="covalentin_db",
        )
    )

    assert envelope.receipt.ok
    assert isinstance(envelope.payload, V2DataIntakeManifest)
    assert envelope.payload.source_name == "CovalentInDB"
    assert envelope.payload.intake_mode == "manual"
    assert envelope.payload.manual_path == "manual/covalentindb.tsv"


def test_valid_download_manifest() -> None:
    envelope = validate_payload(manifest_payload())

    assert envelope.receipt.ok
    assert envelope.payload is not None
    assert envelope.payload.intake_mode == "download"
    assert envelope.payload.source_url == "https://example.invalid/covpdb.zip"


@pytest.mark.parametrize(
    ("source_name", "parser_target"),
    [
        ("CovalentInDB", "covalentin_db"),
        ("CovPDB", "covpdb"),
        ("CovBinderInPDB", "covbinder_in_pdb"),
    ],
)
def test_allowed_source_names(source_name: str, parser_target: str) -> None:
    envelope = validate_payload(
        manifest_payload(source_name=source_name, parser_target=parser_target)
    )

    assert envelope.receipt.ok


def test_unknown_source_name_fails() -> None:
    envelope = validate_payload(manifest_payload(source_name="CovalentInDB 2.0"))

    assert not envelope.receipt.ok
    assert "V2_MANIFEST_UNKNOWN_SOURCE_NAME" in error_codes(envelope)


@pytest.mark.parametrize("mode", sorted(ALLOWED_INTAKE_MODES))
def test_allowed_intake_modes(mode: str) -> None:
    payload = manifest_payload(intake_mode=mode)
    if mode == "manual":
        payload.pop("source_url", None)
        payload["manual_path"] = "manual/source.dat"
    envelope = validate_payload(payload)

    assert envelope.receipt.ok


def test_unknown_intake_mode_fails() -> None:
    envelope = validate_payload(manifest_payload(intake_mode="automatic"))

    assert not envelope.receipt.ok
    assert "V2_MANIFEST_UNKNOWN_INTAKE_MODE" in error_codes(envelope)


def test_missing_checksum_fails() -> None:
    payload = manifest_payload()
    payload.pop("checksum")
    envelope = validate_payload(payload)

    assert not envelope.receipt.ok
    assert "V2_MANIFEST_MISSING_REQUIRED_FIELD" in error_codes(envelope)


def test_unsupported_checksum_algorithm_fails() -> None:
    envelope = validate_payload(
        manifest_payload(
            checksum_algorithm="md5",
            checksum="d41d8cd98f00b204e9800998ecf8427e",
        )
    )

    assert not envelope.receipt.ok
    assert "V2_MANIFEST_UNSUPPORTED_CHECKSUM_ALGORITHM" in error_codes(envelope)


def test_invalid_sha256_checksum_format_fails() -> None:
    envelope = validate_payload(manifest_payload(checksum="sha256:" + "a" * 64))

    assert not envelope.receipt.ok
    assert "V2_MANIFEST_CHECKSUM_INVALID" in error_codes(envelope)


def test_missing_parser_target_fails() -> None:
    payload = manifest_payload()
    payload.pop("parser_target")
    envelope = validate_payload(payload)

    assert not envelope.receipt.ok
    assert "V2_MANIFEST_MISSING_REQUIRED_FIELD" in error_codes(envelope)


def test_unknown_parser_target_fails() -> None:
    envelope = validate_payload(manifest_payload(parser_target="generic_parser"))

    assert not envelope.receipt.ok
    assert "V2_MANIFEST_UNKNOWN_PARSER_TARGET" in error_codes(envelope)


def test_source_parser_mismatch_fails() -> None:
    envelope = validate_payload(
        manifest_payload(source_name="CovPDB", parser_target="covalentin_db")
    )

    assert not envelope.receipt.ok
    assert "V2_MANIFEST_SOURCE_PARSER_MISMATCH" in error_codes(envelope)


def test_manual_mode_requires_manual_path() -> None:
    payload = manifest_payload(intake_mode="manual")
    payload.pop("source_url", None)
    envelope = validate_payload(payload)

    assert not envelope.receipt.ok
    assert "V2_MANIFEST_MANUAL_PATH_REQUIRED" in error_codes(envelope)


def test_download_mode_requires_source_url() -> None:
    payload = manifest_payload()
    payload.pop("source_url")
    envelope = validate_payload(payload)

    assert not envelope.receipt.ok
    assert "V2_MANIFEST_SOURCE_URL_REQUIRED" in error_codes(envelope)


def test_download_mode_does_not_perform_network_access(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_network(*args: object, **kwargs: object) -> object:
        raise AssertionError("manifest validation must not use network access")

    monkeypatch.setattr(socket, "create_connection", fail_network)
    monkeypatch.setattr(urllib.request, "urlopen", fail_network)

    envelope = validate_payload(
        manifest_payload(source_url="https://does-not-exist.invalid/source.zip")
    )

    assert envelope.receipt.ok


def test_license_audit_ref_is_required() -> None:
    payload = manifest_payload()
    payload.pop("license_audit_ref")
    envelope = validate_payload(payload)

    assert not envelope.receipt.ok
    assert "V2_MANIFEST_MISSING_REQUIRED_FIELD" in error_codes(envelope)


def test_empty_license_audit_ref_fails() -> None:
    envelope = validate_payload(manifest_payload(license_audit_ref=""))

    assert not envelope.receipt.ok
    assert "V2_MANIFEST_MISSING_REQUIRED_FIELD" in error_codes(envelope)


def test_serialization_is_deterministic() -> None:
    envelope = validate_payload(manifest_payload())
    assert envelope.payload is not None

    first = serialize_v2_data_intake_manifest(envelope.payload)
    second = serialize_v2_data_intake_manifest(envelope.payload)

    assert first == second
    assert first == json.dumps(json.loads(first), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def test_validation_errors_are_structured_and_machine_readable() -> None:
    envelope = validate_payload(
        manifest_payload(
            source_name="Unknown",
            intake_mode="bad",
            checksum_algorithm="md5",
            parser_target="bad",
        )
    )

    assert not envelope.receipt.ok
    assert len(envelope.receipt.errors) >= 4
    for error in envelope.receipt.errors:
        assert error.code.startswith("V2_MANIFEST_")
        assert error.owner == "data"
        assert error.message
        assert error.location


def test_manifest_rejects_later_task_fields() -> None:
    envelope = validate_payload(
        manifest_payload(
            staging_status="done",
            conversion_status="done",
            license_eligibility="allowed",
            training_eligible=True,
        )
    )

    assert not envelope.receipt.ok
    assert "V2_MANIFEST_FORBIDDEN_FIELD" in error_codes(envelope)


def test_validation_does_not_create_artifacts(tmp_path: Path) -> None:
    before = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))

    envelope = validate_payload(manifest_payload())

    after = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))
    assert envelope.receipt.ok
    assert after == before


def test_invalid_json_file_fails_with_structured_error(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    path.write_text("{not-json", encoding="utf-8")

    envelope = validate_v2_data_intake_manifest(path)

    assert not envelope.receipt.ok
    assert envelope.payload is None
    assert "V2_MANIFEST_INVALID_JSON" in error_codes(envelope)


def test_utf8_bom_manifest_file_is_accepted(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps(manifest_payload(), sort_keys=True, separators=(",", ":")),
        encoding="utf-8-sig",
    )

    envelope = validate_v2_data_intake_manifest(path)

    assert envelope.receipt.ok
    assert envelope.payload is not None
    assert envelope.payload.source_name == "CovPDB"


def test_json_root_must_be_object() -> None:
    envelope = v2_data_intake_manifest_from_dict([])  # type: ignore[arg-type]

    assert not envelope.receipt.ok
    assert "V2_MANIFEST_ROOT_NOT_OBJECT" in error_codes(envelope)


def test_committed_fixture_valid_download_covpdb() -> None:
    path = FIXTURE_ROOT / "valid" / "download_covpdb" / "manifest.json"
    envelope = validate_v2_data_intake_manifest(path)

    assert envelope.receipt.ok
    assert envelope.payload is not None
    assert envelope.payload.source_name == "CovPDB"


def test_committed_fixture_unknown_source_fails() -> None:
    path = FIXTURE_ROOT / "invalid" / "unknown_source_name" / "manifest.json"
    envelope = validate_v2_data_intake_manifest(path)

    assert not envelope.receipt.ok
    assert "V2_MANIFEST_UNKNOWN_SOURCE_NAME" in error_codes(envelope)


def test_constants_are_closed_to_task40_scope() -> None:
    assert ALLOWED_SOURCE_NAMES == ("CovalentInDB", "CovPDB", "CovBinderInPDB")
    assert ALLOWED_INTAKE_MODES == ("download", "manual")
    assert ALLOWED_PARSER_TARGETS == ("covalentin_db", "covpdb", "covbinder_in_pdb")
    assert ALLOWED_CHECKSUM_ALGORITHMS == ("sha256",)
