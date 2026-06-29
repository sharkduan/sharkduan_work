from __future__ import annotations

import json
import sys
from pathlib import Path


FIXTURE_DIR = Path("tests/fixtures/v2/docking_feasibility")


def load_evidence(name: str) -> dict[str, object]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


class TestV2DockingFeasibilityReport:
    def test_missing_engine_reports_not_evaluable(self):
        from covalent_design.evaluation.v2_docking_feasibility import (
            build_v2_docking_feasibility_report,
        )

        envelope = build_v2_docking_feasibility_report(load_evidence("missing_engine.json"))

        assert envelope.receipt.passed
        report = envelope.payload
        assert report.feasibility_status == "not_evaluable"
        assert report.missing_install_reason == "engine_not_installed"
        assert report.non_blocking is True
        assert report.beta_release_impact == "none"
        assert report.model_performance_impact == "none"

    def test_unknown_license_reports_license_unknown_non_blocking(self):
        from covalent_design.evaluation.v2_docking_feasibility import (
            build_v2_docking_feasibility_report,
        )

        report = build_v2_docking_feasibility_report(
            load_evidence("license_unknown.json")
        ).payload

        assert report.feasibility_status == "license_unknown"
        assert report.license_status == "unknown"
        assert report.non_blocking is True
        assert report.not_evaluable_reason == "license_unknown"

    def test_unsupported_formats_report_not_evaluable(self):
        from covalent_design.evaluation.v2_docking_feasibility import (
            build_v2_docking_feasibility_report,
        )

        report = build_v2_docking_feasibility_report(
            load_evidence("unsupported_formats.json")
        ).payload

        assert report.feasibility_status == "not_evaluable"
        assert report.input_format_support["status"] == "unsupported"
        assert report.output_format_support["status"] == "unsupported"
        assert report.not_evaluable_reason == "unsupported_format"

    def test_probe_failure_is_reported_as_non_blocking(self):
        from covalent_design.evaluation.v2_docking_feasibility import (
            build_v2_docking_feasibility_report,
        )

        report = build_v2_docking_feasibility_report(
            load_evidence("failed_probe.json")
        ).payload

        assert report.feasibility_status == "failed_probe"
        assert report.cli_probe_status == "failed"
        assert report.api_probe_status == "not_attempted"
        assert report.non_blocking is True
        assert report.beta_release_impact == "none"

    def test_feasible_evidence_records_path_version_formats_and_runtime(self):
        from covalent_design.evaluation.v2_docking_feasibility import (
            build_v2_docking_feasibility_report,
        )

        report = build_v2_docking_feasibility_report(load_evidence("feasible.json")).payload

        assert report.feasibility_status == "feasible"
        assert report.engine_candidate == "fixture_engine"
        assert report.engine_version == "fixture-1.0"
        assert report.install_path == "fixtures/bin/fixture_engine"
        assert report.license_status == "allowed"
        assert report.cli_probe_status == "passed"
        assert report.probe_duration_seconds == 0.012
        assert report.input_format_support["supported_formats"] == ["fixture_receptor"]
        assert report.output_format_support["supported_formats"] == ["fixture_pose"]

    def test_invalid_feasible_claim_fails_structured(self):
        from covalent_design.evaluation.v2_docking_feasibility import (
            build_v2_docking_feasibility_report,
        )

        envelope = build_v2_docking_feasibility_report(
            load_evidence("invalid_feasible_claim.json")
        )

        assert envelope.payload is None
        assert not envelope.receipt.passed
        assert envelope.receipt.errors[0].code == "V2_DOCKING_FEASIBILITY_CLAIM_INVALID"
        assert envelope.receipt.errors[0].owner == "evaluation"

    def test_serialization_and_hash_are_deterministic(self):
        from covalent_design.evaluation.v2_docking_feasibility import (
            build_v2_docking_feasibility_report,
            hash_v2_docking_feasibility_report,
            serialize_v2_docking_feasibility_report,
        )

        first = build_v2_docking_feasibility_report(load_evidence("feasible.json")).payload
        second = build_v2_docking_feasibility_report(load_evidence("feasible.json")).payload

        assert serialize_v2_docking_feasibility_report(first) == serialize_v2_docking_feasibility_report(second)
        assert hash_v2_docking_feasibility_report(first) == hash_v2_docking_feasibility_report(second)
        decoded = json.loads(serialize_v2_docking_feasibility_report(first))
        assert list(decoded) == sorted(decoded)
        assert first.report_id.startswith("sha256:")


class TestV2DockingFeasibilityBoundary:
    def test_no_output_artifact_is_required_or_written(self, tmp_path):
        from covalent_design.evaluation.v2_docking_feasibility import (
            build_v2_docking_feasibility_report,
        )

        report = build_v2_docking_feasibility_report(load_evidence("missing_engine.json")).payload

        assert report.output_artifact_required is False
        assert not list(tmp_path.rglob("*"))

    def test_no_heavy_dependencies_are_imported(self):
        import covalent_design.evaluation.v2_docking_feasibility  # noqa: F401

        for name in ("to" + "rch", "rd" + "kit", "PM" + "DM", "Pocket" + "Flow", "pm" + "dm", "pocket" + "flow"):
            assert name not in sys.modules

    def test_source_has_no_real_execution_or_data_root_boundary(self):
        import covalent_design.evaluation.v2_docking_feasibility as module

        source = Path(module.__file__).read_text(encoding="utf-8").lower()
        test_source = Path(__file__).read_text(encoding="utf-8").lower()
        combined = "\n".join((source, test_source))

        forbidden = (
            "sub" + "process",
            "os." + "system",
            "start-" + "process",
            "vi" + "na",
            "sm" + "ina",
            "gni" + "na",
            "auto" + "dock",
            "qvi" + "na",
            "quick" + "vi" + "na",
            "import " + "to" + "rch",
            "from " + "to" + "rch",
            "import " + "rd" + "kit",
            "from " + "rd" + "kit",
            "import " + "pm" + "dm",
            "from " + "pm" + "dm",
            "import " + "pocket" + "flow",
            "from " + "pocket" + "flow",
            "d:" + "\\codex_work" + "\\data",
            "data" + "/v2",
            "binding " + "affinity",
            "drug " + "efficacy",
            "clin" + "ical",
            "pot" + "ency",
        )
        for token in forbidden:
            assert token not in combined
