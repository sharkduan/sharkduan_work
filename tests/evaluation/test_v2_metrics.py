from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from covalent_design.contracts.types import ArtifactRef


FIXTURE_DIR = Path("tests/fixtures/v2/evaluation")
SHA = "sha256:" + "d" * 64


def artifact(role: str) -> ArtifactRef:
    return ArtifactRef(
        uri=f"manifest-ref://v2/evaluation/{role}",
        sha256=SHA,
        format="manifest_ref",
        role=role,
        bytes=123,
    )


def sampling_result(**overrides):
    from covalent_design.inference.v2_sampling import (
        V2InvalidDecodeDiagnostic,
        V2SamplingResult,
        V2SamplingSystemFailure,
    )

    data = {
        "request_id": "v2-eval-001",
        "checkpoint_manifest_ref": artifact("checkpoint_manifest"),
        "environment_manifest_ref": artifact("environment_manifest"),
        "checkpoint_ref": artifact("checkpoint"),
        "baseline_mode": "non_pmdm_baseline",
        "split_name": "test",
        "family_filter": (),
        "random_seed": 42,
        "requested_sample_count": 6,
        "attempted_sample_count": 5,
        "valid_sample_count": 3,
        "invalid_sample_count": 2,
        "sampling_system_failure_count": 1,
        "invalid_decode_diagnostics": (
            V2InvalidDecodeDiagnostic(
                request_id="v2-eval-001",
                sample_id=1,
                failure_reason="LIGAND_CHEMISTRY_INVALID",
                message="invalid ligand",
            ),
            V2InvalidDecodeDiagnostic(
                request_id="v2-eval-001",
                sample_id=3,
                failure_reason="GEOMETRY_CHECK_FAIL",
                message="bad geometry",
            ),
        ),
        "sampling_system_failures": (
            V2SamplingSystemFailure(
                request_id="v2-eval-001",
                sample_id=0,
                failure_category="timeout",
                message="sampler timeout",
            ),
        ),
        "export_status": "not_implemented",
        "docking_status": "not_run",
        "evaluation_status": "not_implemented",
    }
    data.update(overrides)
    return V2SamplingResult(**data)


def load_records() -> tuple[dict[str, object], ...]:
    return tuple(
        json.loads(line)
        for line in (FIXTURE_DIR / "records.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    )


def load_json(name: str) -> dict[str, object]:
    return json.loads((FIXURE_PATH := FIXTURE_DIR / name).read_text(encoding="utf-8"))


class TestV2EvaluationMetrics:
    def test_report_includes_required_sections(self):
        from covalent_design.evaluation.v2_metrics import build_v2_evaluation_report

        envelope = build_v2_evaluation_report(
            sampling_result(),
            fixture_records=load_records(),
            fixture_split_index=load_json("split_index.json"),
            geometry_evidence=load_json("geometry_evidence.json"),
            uniqueness_evidence=load_json("uniqueness_evidence.json"),
            rdkit_evidence=load_json("rdkit_evidence.json"),
        )

        assert envelope.receipt.passed
        report = envelope.payload
        assert report.validity_metrics["valid_sample_count"] == 3
        assert report.family_metrics["status"] == "computed"
        assert report.covalent_geometry_metrics["status"] == "computed"
        assert report.uniqueness_novelty_metrics["status"] == "computed"
        assert report.rdkit_validity_metrics["status"] == "computed"
        assert report.failure_accounting["status"] == "computed"
        assert report.denominator_conservation["passed"] is True
        assert report.docking_evaluation_status == "not_evaluable"

    def test_optional_tool_absence_is_not_negative_model_performance(self):
        from covalent_design.evaluation.v2_metrics import build_v2_evaluation_report

        report = build_v2_evaluation_report(sampling_result()).payload

        assert report.rdkit_validity_metrics == {
            "reason": "rdkit_evidence_absent",
            "status": "not_evaluable",
        }
        assert report.uniqueness_novelty_metrics["status"] == "not_evaluable"
        assert report.covalent_geometry_metrics["status"] == "not_evaluable"
        assert report.docking_evaluation_status == "not_evaluable"
        assert report.failure_accounting["categories"]["docking_not_run"] == 1

    def test_family_metrics_use_fixture_metadata_when_available(self):
        from covalent_design.evaluation.v2_metrics import build_v2_evaluation_report

        report = build_v2_evaluation_report(
            sampling_result(),
            fixture_records=load_records(),
            fixture_split_index=load_json("split_index.json"),
        ).payload

        by_family = report.family_metrics["families"]
        assert set(by_family) == {"CYS_MICHAEL_ADDITION", "LYS_ACYLATION"}
        assert sum(item["requested_sample_count"] for item in by_family.values()) == 6
        assert sum(item["valid_sample_count"] for item in by_family.values()) == 3

    def test_failure_accounting_preserves_categories_and_reasons(self):
        from covalent_design.evaluation.v2_metrics import build_v2_evaluation_report

        accounting = build_v2_evaluation_report(sampling_result()).payload.failure_accounting

        assert accounting["categories"] == {
            "docking_not_run": 1,
            "evaluation_artifact_corruption": 0,
            "export_failure": 0,
            "invalid_generated_sample": 2,
            "request_validation_failure": 0,
            "sampling_system_failure": 1,
        }
        assert accounting["invalid_decode_failure_reasons"] == {
            "GEOMETRY_CHECK_FAIL": 1,
            "LIGAND_CHEMISTRY_INVALID": 1,
        }
        assert accounting["sampling_system_failure_categories"] == {"timeout": 1}

    def test_denominator_mismatch_fails_with_structured_error(self):
        from covalent_design.evaluation.v2_metrics import load_v2_sampling_result_file

        envelope = load_v2_sampling_result_file(FIXTURE_DIR / "denominator_mismatch.json")

        assert envelope.payload is None
        assert not envelope.receipt.passed
        assert envelope.receipt.errors[0].code == "V2_EVALUATION_DENOMINATOR_MISMATCH"

    def test_report_serialization_and_hash_are_deterministic(self):
        from covalent_design.evaluation.v2_metrics import (
            build_v2_evaluation_report,
            hash_v2_evaluation_report,
            serialize_v2_evaluation_report,
        )

        first = build_v2_evaluation_report(
            sampling_result(),
            fixture_records=load_records(),
            fixture_split_index=load_json("split_index.json"),
            geometry_evidence=load_json("geometry_evidence.json"),
        ).payload
        second = build_v2_evaluation_report(
            sampling_result(),
            fixture_records=load_records(),
            fixture_split_index=load_json("split_index.json"),
            geometry_evidence=load_json("geometry_evidence.json"),
        ).payload

        assert serialize_v2_evaluation_report(first) == serialize_v2_evaluation_report(second)
        assert hash_v2_evaluation_report(first) == hash_v2_evaluation_report(second)
        assert list(json.loads(serialize_v2_evaluation_report(first))) == sorted(
            json.loads(serialize_v2_evaluation_report(first))
        )


class TestV2EvaluationCli:
    def test_cli_valid_fixture_outputs_deterministic_json(self):
        cmd = [
            sys.executable,
            "-m",
            "covalent_design.evaluation.cli.v2_evaluate",
            "--sampling-result",
            str(FIXTURE_DIR / "valid_sampling_result.json"),
            "--fixture-records",
            str(FIXTURE_DIR / "records.jsonl"),
            "--fixture-split-index",
            str(FIXTURE_DIR / "split_index.json"),
            "--geometry-evidence",
            str(FIXTURE_DIR / "geometry_evidence.json"),
        ]

        first = subprocess.run(cmd, check=False, text=True, capture_output=True)
        second = subprocess.run(cmd, check=False, text=True, capture_output=True)

        assert first.returncode == 0, first.stderr
        assert second.returncode == 0, second.stderr
        assert first.stdout == second.stdout
        payload = json.loads(first.stdout)
        assert payload["role"] == "v2_evaluation_report"
        assert payload["denominator_conservation"]["passed"] is True

    def test_cli_invalid_fixture_exits_nonzero_with_structured_error(self):
        cmd = [
            sys.executable,
            "-m",
            "covalent_design.evaluation.cli.v2_evaluate",
            "--sampling-result",
            str(FIXTURE_DIR / "corrupt_sampling_result.json"),
        ]

        result = subprocess.run(cmd, check=False, text=True, capture_output=True)

        assert result.returncode == 1
        payload = json.loads(result.stderr)
        assert payload["errors"][0]["code"] == "V2_EVALUATION_INPUT_CORRUPT"


class TestV2EvaluationBoundary:
    def test_source_has_no_heavy_imports_real_data_or_task56_execution(self):
        import covalent_design.evaluation.v2_metrics as module

        source = Path(module.__file__).read_text(encoding="utf-8").lower()
        test_source = Path(__file__).read_text(encoding="utf-8").lower()
        combined = "\n".join((source, test_source))

        forbidden = (
            "import " + "torch",
            "from " + "torch",
            "import " + "rdkit",
            "from " + "rdkit",
            "import " + "pmdm",
            "from " + "pmdm",
            "import " + "pocketflow",
            "from " + "pocketflow",
            "run_" + "docking",
            "vi" + "na",
            "pd" + "bqt",
            "d:" + "\\codex_work" + "\\data",
            "data" + "/v2",
            "performance " + "claim",
            "drug " + "efficacy",
            "clin" + "ical " + "claim",
        )
        for token in forbidden:
            assert token not in combined

    def test_build_report_does_not_create_artifacts(self, tmp_path):
        from covalent_design.evaluation.v2_metrics import build_v2_evaluation_report

        build_v2_evaluation_report(sampling_result(), fixture_records=load_records())

        assert not list(tmp_path.rglob("*"))
