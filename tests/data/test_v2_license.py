from __future__ import annotations

import json
import socket
import urllib.request
from pathlib import Path

import pytest

from covalent_design.contracts.errors import ContractErrorInfo
from covalent_design.contracts.types import (
    ContractEnvelope,
    Provenance,
    SourceIngestRecord,
    SourceRecordLineage,
    ValidationReceipt,
)
from covalent_design.data.v2_intake import V2StagingSummary
from covalent_design.data.v2_license import (
    LICENSE_STATUS_ALLOWED,
    LICENSE_STATUS_BLOCKED,
    LICENSE_STATUS_MANUAL_EXEMPT,
    LICENSE_STATUS_RESTRICTED,
    LICENSE_STATUS_UNKNOWN,
    SourceLicenseAudit,
    audit_v2_training_eligibility,
    license_gate_report_to_dict,
    load_source_license_audit,
)


FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "v2" / "license"
VALID_SHA256 = "b" * 64
APPROVED_ROOT = Path(__file__).resolve().parents[1] / "fixtures"
_DEFAULT_MANUAL_PATH = object()


def _staging(
    *,
    source_name: str = "CovalentInDB",
    intake_mode: str = "manual",
    status: str = "checksum_verified",
    checksum: str | None = VALID_SHA256,
    manual_path: str | None | object = _DEFAULT_MANUAL_PATH,
    source_url: str | None = "https://example.invalid/covalentindb.tsv",
    license_audit_ref: str | None = "audit/covalentindb/license.json",
) -> ContractEnvelope[V2StagingSummary]:
    summary = V2StagingSummary(
        source_name=source_name,
        intake_mode=intake_mode,
        status=status,
        source_url=source_url,
        manual_path=(
            str(APPROVED_ROOT / "v2" / "license" / "fixture.tsv")
            if manual_path is _DEFAULT_MANUAL_PATH
            else manual_path  # type: ignore[arg-type]
        ),
        checksum=checksum,
        checksum_algorithm="sha256" if checksum else None,
        parser_target="covalentin_db",
        license_audit_ref=license_audit_ref,
    )
    return ContractEnvelope(
        payload=summary,
        artifacts=(),
        receipt=ValidationReceipt(
            validator="covalent_design.data.stage_source_manifest",
            contract_version="v2-beta",
            input_sha256="staging",
            ok=True,
        ),
        provenance=Provenance(),
    )


def _failed_staging(code: str) -> ContractEnvelope[V2StagingSummary]:
    return ContractEnvelope(  # type: ignore[arg-type]
        payload=None,
        artifacts=(),
        receipt=ValidationReceipt(
            validator="covalent_design.data.stage_source_manifest",
            contract_version="v2-beta",
            input_sha256="staging",
            ok=False,
            errors=(
                ContractErrorInfo(
                    code=code,
                    owner="data",
                    message="fixture staging failure",
                ),
            ),
        ),
        provenance=Provenance(),
    )


def _audit(
    status: str,
    *,
    intake_mode: str = "manual",
    conditions: tuple[str, ...] = (),
    conditions_satisfied: bool = False,
) -> SourceLicenseAudit:
    return SourceLicenseAudit(
        source_name="CovalentInDB",
        intake_mode=intake_mode,
        license_status=status,
        license_evidence_ref="audit/ref.json",
        restriction_conditions=conditions,
        restriction_conditions_satisfied=conditions_satisfied,
    )


def _record(
    *,
    license_audit_ref: str = "audit/covalentindb/license.json",
    checksum: str = VALID_SHA256,
    raw_file_path: str | None = None,
    source_url: str | None = "https://example.invalid/covalentindb.tsv",
) -> SourceIngestRecord:
    path = raw_file_path or str(APPROVED_ROOT / "v2" / "license" / "fixture.tsv")
    lineage: dict[str, object] = {
        "source_database": "CovalentInDB",
        "source_version": "v2",
        "source_record_id": "CovalentInDB:test:row:1",
        "raw_manifest_file": "manifest.json",
        "raw_file_path": path,
        "raw_file_sha256": checksum,
        "row_index": 1,
        "license_audit_ref": license_audit_ref,
    }
    if source_url is not None:
        lineage["source_url"] = source_url
    return SourceIngestRecord(
        source_database="CovalentInDB",
        source_version="v2",
        source_record_id="CovalentInDB:test:row:1",
        raw_manifest_file="manifest.json",
        raw_file_path=path,
        raw_file_sha256=checksum,
        row_index=1,
        lineage=lineage,
        protein={},
        ligand={},
        linkage={},
        metadata={"license_audit_ref": license_audit_ref},
        source_lineage=SourceRecordLineage(
            source_database="CovalentInDB",
            source_version="v2",
            source_record_id="CovalentInDB:test:row:1",
            raw_manifest_file="manifest.json",
            raw_file_path=path,
            raw_file_sha256=checksum,
            row_index=1,
        ),
    )


def _codes(envelope: ContractEnvelope[object]) -> set[str]:
    return {error.code for error in envelope.receipt.errors}


def _run(status: str, **kwargs: object) -> ContractEnvelope[object]:
    return audit_v2_training_eligibility(
        [_staging()],
        {"audit/covalentindb/license.json": _audit(status, **kwargs)},
        approved_local_data_roots=(APPROVED_ROOT,),
    )


def test_license_status_constants_are_exact_five_state_model() -> None:
    assert {
        LICENSE_STATUS_ALLOWED,
        LICENSE_STATUS_RESTRICTED,
        LICENSE_STATUS_BLOCKED,
        LICENSE_STATUS_UNKNOWN,
        LICENSE_STATUS_MANUAL_EXEMPT,
    } == {"allowed", "restricted", "blocked", "unknown", "manual_exempt"}


def test_allowed_fixture_passes_training_eligibility() -> None:
    envelope = _run("allowed")

    assert envelope.receipt.ok
    assert envelope.payload is not None
    assert envelope.payload.sources[0].training_eligible is True


def test_restricted_with_recorded_satisfied_conditions_passes_and_preserves_conditions() -> None:
    envelope = _run(
        "restricted",
        conditions=("internal research only",),
        conditions_satisfied=True,
    )

    assert envelope.receipt.ok
    report = envelope.payload
    assert report is not None
    assert report.sources[0].training_eligible is True
    assert report.sources[0].restriction_conditions == ("internal research only",)
    assert license_gate_report_to_dict(report)["sources"][0]["restriction_conditions"] == [
        "internal research only"
    ]


def test_restricted_without_satisfied_conditions_fails() -> None:
    envelope = _run(
        "restricted",
        conditions=("no redistribution",),
        conditions_satisfied=False,
    )

    assert not envelope.receipt.ok
    assert "V2_LICENSE_RESTRICTED_CONDITIONS_UNSATISFIED" in _codes(envelope)


@pytest.mark.parametrize(
    ("status", "expected_code"),
    [
        ("unknown", "V2_LICENSE_STATUS_UNKNOWN_BLOCKED"),
        ("blocked", "V2_LICENSE_STATUS_BLOCKED"),
    ],
)
def test_unknown_and_blocked_fixtures_block_training_eligibility(
    status: str,
    expected_code: str,
) -> None:
    envelope = _run(status)

    assert not envelope.receipt.ok
    assert expected_code in _codes(envelope)
    assert envelope.payload is not None
    assert envelope.payload.sources[0].training_eligible is False


def test_manual_exempt_manual_passes_as_distinct_report_category_with_notice() -> None:
    envelope = _run("manual_exempt")

    assert envelope.receipt.ok
    report = envelope.payload
    assert report is not None
    assert report.status_counts["manual_exempt"] == 1
    assert report.status_counts["allowed"] == 0
    assert report.sources[0].training_eligible is True
    assert "third-party license verification" in report.sources[0].notice


def test_manual_exempt_download_mode_structured_failure() -> None:
    envelope = audit_v2_training_eligibility(
        [_staging(intake_mode="download", manual_path=None)],
        {"audit/covalentindb/license.json": _audit("manual_exempt", intake_mode="download")},
        approved_local_data_roots=(APPROVED_ROOT,),
    )

    assert not envelope.receipt.ok
    assert "V2_LICENSE_MANUAL_EXEMPT_DOWNLOAD" in _codes(envelope)


def test_load_source_license_audit_reads_fixture_json() -> None:
    audit = load_source_license_audit(FIXTURE_ROOT / "manual_exempt_audit.json")

    assert audit.license_status == "manual_exempt"
    assert audit.intake_mode == "manual"


@pytest.mark.parametrize(
    ("fixture_name", "expected_status"),
    [
        ("allowed_audit.json", "allowed"),
        ("restricted_satisfied_audit.json", "restricted"),
        ("restricted_unsatisfied_audit.json", "restricted"),
        ("blocked_audit.json", "blocked"),
        ("unknown_audit.json", "unknown"),
        ("manual_exempt_audit.json", "manual_exempt"),
    ],
)
def test_all_license_fixture_json_files_load(
    fixture_name: str,
    expected_status: str,
) -> None:
    audit = load_source_license_audit(FIXTURE_ROOT / fixture_name)

    assert audit.license_status == expected_status


def test_unsupported_license_status_structured_failure() -> None:
    envelope = _run("allowed_but_misspelled")

    assert not envelope.receipt.ok
    assert "V2_LICENSE_STATUS_UNSUPPORTED" in _codes(envelope)


def test_multiple_staged_sources_aggregate_status_counts() -> None:
    envelope = audit_v2_training_eligibility(
        [
            _staging(license_audit_ref="audit/allowed.json"),
            _staging(
                source_name="CovPDB",
                intake_mode="manual",
                source_url="https://example.invalid/covpdb.tsv",
                license_audit_ref="audit/blocked.json",
            ),
            _staging(
                source_name="CovBinderInPDB",
                intake_mode="manual",
                source_url="https://example.invalid/covbinder.tsv",
                license_audit_ref="audit/manual-exempt.json",
            ),
        ],
        {
            "audit/allowed.json": _audit("allowed"),
            "audit/blocked.json": SourceLicenseAudit(
                source_name="CovPDB",
                intake_mode="manual",
                license_status="blocked",
                license_evidence_ref="audit/blocked.json",
            ),
            "audit/manual-exempt.json": SourceLicenseAudit(
                source_name="CovBinderInPDB",
                intake_mode="manual",
                license_status="manual_exempt",
                license_evidence_ref="audit/manual-exempt.json",
            ),
        },
        approved_local_data_roots=(APPROVED_ROOT,),
    )

    assert not envelope.receipt.ok
    assert envelope.payload is not None
    assert envelope.payload.status_counts["allowed"] == 1
    assert envelope.payload.status_counts["blocked"] == 1
    assert envelope.payload.status_counts["manual_exempt"] == 1
    assert envelope.payload.training_eligible_count == 2
    assert envelope.payload.blocked_count == 1


@pytest.mark.parametrize(
    ("staging_kwargs", "expected_code"),
    [
        ({"checksum": None}, "V2_LICENSE_CHECKSUM_MISSING"),
        ({"manual_path": None, "source_url": None}, "V2_LICENSE_PROVENANCE_MISSING"),
    ],
)
def test_manual_exempt_does_not_bypass_prerequisite_checks(
    staging_kwargs: dict[str, object],
    expected_code: str,
) -> None:
    envelope = audit_v2_training_eligibility(
        [_staging(**staging_kwargs)],
        {"audit/covalentindb/license.json": _audit("manual_exempt")},
        approved_local_data_roots=(APPROVED_ROOT,),
    )

    assert not envelope.receipt.ok
    assert expected_code in _codes(envelope)


def test_missing_manifest_structured_failure() -> None:
    envelope = audit_v2_training_eligibility(
        [_failed_staging("V2_INTAKE_MANIFEST_UNREADABLE")],
        {},
        approved_local_data_roots=(APPROVED_ROOT,),
    )

    assert not envelope.receipt.ok
    assert "V2_LICENSE_STAGING_EVIDENCE_INVALID" in _codes(envelope)


def test_missing_checksum_structured_failure() -> None:
    envelope = audit_v2_training_eligibility(
        [_staging(checksum=None)],
        {"audit/covalentindb/license.json": _audit("allowed")},
        approved_local_data_roots=(APPROVED_ROOT,),
    )

    assert not envelope.receipt.ok
    assert "V2_LICENSE_CHECKSUM_MISSING" in _codes(envelope)


def test_missing_provenance_structured_failure() -> None:
    envelope = audit_v2_training_eligibility(
        [_staging(manual_path=None, source_url=None)],
        {"audit/covalentindb/license.json": _audit("allowed")},
        approved_local_data_roots=(APPROVED_ROOT,),
    )

    assert not envelope.receipt.ok
    assert "V2_LICENSE_PROVENANCE_MISSING" in _codes(envelope)


def test_missing_license_audit_reference_structured_failure() -> None:
    envelope = audit_v2_training_eligibility(
        [_staging(license_audit_ref=None)],
        {},
        approved_local_data_roots=(APPROVED_ROOT,),
    )

    assert not envelope.receipt.ok
    assert "V2_LICENSE_AUDIT_REF_MISSING" in _codes(envelope)


def test_path_outside_approved_local_data_root_structured_failure(tmp_path: Path) -> None:
    outside = tmp_path / "outside.tsv"
    envelope = audit_v2_training_eligibility(
        [_staging(manual_path=str(outside))],
        {"audit/covalentindb/license.json": _audit("allowed")},
        approved_local_data_roots=(APPROVED_ROOT,),
    )

    assert not envelope.receipt.ok
    assert "V2_LICENSE_PATH_OUTSIDE_APPROVED_ROOT" in _codes(envelope)


@pytest.mark.parametrize(
    ("record_kwargs", "expected_code"),
    [
        (
            {"license_audit_ref": "audit/other/license.json"},
            "V2_LICENSE_CROSS_VALIDATION_LICENSE_AUDIT_REF_MISMATCH",
        ),
        (
            {"checksum": "c" * 64},
            "V2_LICENSE_CROSS_VALIDATION_CHECKSUM_MISMATCH",
        ),
        (
            {"raw_file_path": "different/path.tsv"},
            "V2_LICENSE_CROSS_VALIDATION_LOCAL_PATH_MISMATCH",
        ),
        (
            {"source_url": "https://example.invalid/other.tsv"},
            "V2_LICENSE_CROSS_VALIDATION_SOURCE_PROVENANCE_MISMATCH",
        ),
    ],
)
def test_staged_evidence_vs_converted_output_reference_mismatches_fail(
    record_kwargs: dict[str, object],
    expected_code: str,
) -> None:
    envelope = audit_v2_training_eligibility(
        [_staging()],
        {"audit/covalentindb/license.json": _audit("allowed")},
        converted_records=(_record(**record_kwargs),),
        approved_local_data_roots=(APPROVED_ROOT,),
    )

    assert not envelope.receipt.ok
    assert expected_code in _codes(envelope)


def test_cross_validation_success_preserves_audit_reference() -> None:
    envelope = audit_v2_training_eligibility(
        [_staging()],
        {"audit/covalentindb/license.json": _audit("allowed")},
        converted_records=(_record(),),
        approved_local_data_roots=(APPROVED_ROOT,),
    )

    assert envelope.receipt.ok
    assert envelope.payload is not None
    assert envelope.payload.sources[0].license_audit_ref == "audit/covalentindb/license.json"


def test_every_staged_source_has_audit_evidence_or_explicit_blocked_status() -> None:
    envelope = audit_v2_training_eligibility(
        [_staging()],
        {},
        approved_local_data_roots=(APPROVED_ROOT,),
    )

    assert not envelope.receipt.ok
    assert "V2_LICENSE_AUDIT_EVIDENCE_MISSING" in _codes(envelope)


def test_output_is_deterministic() -> None:
    first = _run("manual_exempt").payload
    second = _run("manual_exempt").payload

    assert first is not None and second is not None
    assert license_gate_report_to_dict(first) == license_gate_report_to_dict(second)
    assert json.dumps(license_gate_report_to_dict(first), sort_keys=True) == json.dumps(
        license_gate_report_to_dict(second),
        sort_keys=True,
    )


def test_no_network_conversion_raw_parser_or_artifacts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def _fail_network(*args: object, **kwargs: object) -> object:
        raise AssertionError("network access detected")

    def _fail_conversion(*args: object, **kwargs: object) -> object:
        raise AssertionError("conversion execution detected")

    monkeypatch.setattr(socket, "create_connection", _fail_network)
    monkeypatch.setattr(socket, "socket", _fail_network)
    monkeypatch.setattr(urllib.request, "urlopen", _fail_network)
    monkeypatch.setattr(urllib.request, "urlretrieve", _fail_network)
    monkeypatch.setattr(
        "covalent_design.data.v2_conversion.convert_staged_source",
        _fail_conversion,
    )
    before = set(tmp_path.rglob("*"))

    envelope = _run("allowed")

    after = set(tmp_path.rglob("*"))
    assert envelope.receipt.ok
    assert after == before
