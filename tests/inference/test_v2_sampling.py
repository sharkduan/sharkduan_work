from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from covalent_design.contracts.types import (
    ArtifactRef,
    SAMPLING_SYSTEM_FAILURE_CATEGORIES,
)


SHA = "sha256:" + "a" * 64
SHA_B = "sha256:" + "b" * 64


def artifact(role: str = "checkpoint") -> ArtifactRef:
    return ArtifactRef(
        uri=f"manifest-ref://v2/{role}",
        sha256=SHA,
        format="manifest_ref",
        role=role,
        bytes=123,
    )


def valid_request_kwargs(**overrides):
    data = {
        "request_id": "v2-sampling-request-001",
        "checkpoint_ref": artifact("checkpoint"),
        "checkpoint_manifest_ref": artifact("checkpoint_manifest"),
        "environment_manifest_ref": artifact("environment_manifest"),
        "split_name": "test",
        "record_ids": (),
        "family_filter": ("CYS_MICHAEL_ADDITION",),
        "random_seed": 42,
        "sample_count": 3,
        "output_root": "local-only-v2-sampling-output",
        "max_retries": 2,
        "retry_on_categories": ("crash", "oom"),
        "baseline_mode": "non_pmdm_baseline",
        "generation_mode": "reactive_site",
    }
    data.update(overrides)
    return data


def valid_result_kwargs(**overrides):
    data = {
        "request_id": "v2-sampling-request-001",
        "checkpoint_manifest_ref": artifact("checkpoint_manifest"),
        "environment_manifest_ref": artifact("environment_manifest"),
        "checkpoint_ref": artifact("checkpoint"),
        "baseline_mode": "non_pmdm_baseline",
        "split_name": "test",
        "family_filter": ("CYS_MICHAEL_ADDITION",),
        "random_seed": 42,
        "requested_sample_count": 3,
        "attempted_sample_count": 2,
        "valid_sample_count": 1,
        "invalid_sample_count": 1,
        "sampling_system_failure_count": 1,
        "invalid_decode_diagnostics": (),
        "sampling_system_failures": (),
        "export_status": "not_implemented",
        "docking_status": "not_run",
        "evaluation_status": "not_implemented",
    }
    data.update(overrides)
    return data


class TestV2SamplingRequestContract:
    def test_valid_request_contains_required_task53_fields(self):
        from covalent_design.inference.v2_sampling import V2SamplingRequest

        request = V2SamplingRequest(**valid_request_kwargs())

        assert request.checkpoint_ref.role == "checkpoint"
        assert request.checkpoint_manifest_ref.role == "checkpoint_manifest"
        assert request.environment_manifest_ref.role == "environment_manifest"
        assert request.split_name == "test"
        assert request.family_filter == ("CYS_MICHAEL_ADDITION",)
        assert request.random_seed == 42
        assert request.sample_count == 3
        assert request.output_root == "local-only-v2-sampling-output"
        assert request.max_retries == 2
        assert request.baseline_mode == "non_pmdm_baseline"
        assert request.generation_mode == "reactive_site"

    def test_request_supports_record_selector_instead_of_split_selector(self):
        from covalent_design.inference.v2_sampling import V2SamplingRequest

        request = V2SamplingRequest(
            **valid_request_kwargs(split_name=None, record_ids=("REC-001", "REC-002"))
        )

        assert request.split_name is None
        assert request.record_ids == ("REC-001", "REC-002")

    @pytest.mark.parametrize(
        "overrides, code",
        [
            ({"checkpoint_ref": None}, "V2_SAMPLING_CHECKPOINT_REF_MISSING"),
            ({"split_name": None, "record_ids": ()}, "V2_SAMPLING_SELECTOR_MISSING"),
            ({"split_name": "test", "record_ids": ("REC-001",)}, "V2_SAMPLING_SELECTOR_CONFLICT"),
            ({"family_filter": ("",)}, "V2_SAMPLING_FAMILY_FILTER_INVALID"),
            ({"random_seed": "42"}, "V2_SAMPLING_RANDOM_SEED_INVALID"),
            ({"sample_count": 0}, "V2_SAMPLING_SAMPLE_COUNT_INVALID"),
            ({"output_root": ""}, "V2_SAMPLING_OUTPUT_ROOT_MISSING"),
            ({"max_retries": -1}, "V2_SAMPLING_MAX_RETRIES_INVALID"),
            ({"retry_on_categories": ("retry_exhausted",)}, "V2_SAMPLING_RETRY_POLICY_INVALID"),
            ({"baseline_mode": "unknown"}, "V2_SAMPLING_BASELINE_MODE_UNSUPPORTED"),
            ({"generation_mode": "reference_ligand"}, "V2_SAMPLING_GENERATION_MODE_UNSUPPORTED"),
        ],
    )
    def test_invalid_request_data_returns_structured_error(self, overrides, code):
        from covalent_design.inference.v2_sampling import build_v2_sampling_request

        payload = valid_request_kwargs(**overrides)
        envelope = build_v2_sampling_request(payload)

        assert envelope.payload is None
        assert not envelope.receipt.passed
        assert envelope.receipt.errors[0].code == code
        assert envelope.receipt.errors[0].owner == "inference"

    def test_request_dataclass_rejects_reference_ligand_generation_mode(self):
        from covalent_design.inference.v2_sampling import V2SamplingRequest

        with pytest.raises(ValueError, match="reactive_site"):
            V2SamplingRequest(**valid_request_kwargs(generation_mode="reference_ligand"))


class TestV2SamplingResultContract:
    def test_result_links_checkpoint_and_environment_manifests(self):
        from covalent_design.inference.v2_sampling import V2SamplingResult

        result = V2SamplingResult(**valid_result_kwargs())

        assert result.checkpoint_ref.role == "checkpoint"
        assert result.checkpoint_manifest_ref.role == "checkpoint_manifest"
        assert result.environment_manifest_ref.role == "environment_manifest"
        assert result.requested_sample_count == 3
        assert result.attempted_sample_count == 2
        assert result.valid_sample_count == 1
        assert result.invalid_sample_count == 1
        assert result.sampling_system_failure_count == 1

    def test_result_reconciles_counts(self):
        from covalent_design.inference.v2_sampling import V2SamplingResult

        with pytest.raises(ValueError, match="valid_sample_count"):
            V2SamplingResult(**valid_result_kwargs(valid_sample_count=2))
        with pytest.raises(ValueError, match="requested_sample_count"):
            V2SamplingResult(**valid_result_kwargs(sampling_system_failure_count=0))

    def test_invalid_decode_diagnostics_separate_from_system_failures(self):
        from covalent_design.inference.v2_sampling import (
            V2InvalidDecodeDiagnostic,
            V2SamplingResult,
            V2SamplingSystemFailure,
        )

        diagnostic = V2InvalidDecodeDiagnostic(
            request_id="v2-sampling-request-001",
            sample_id=1,
            failure_reason="LIGAND_CHEMISTRY_INVALID",
            message="invalid generated ligand",
        )
        failure = V2SamplingSystemFailure(
            request_id="v2-sampling-request-001",
            sample_id=2,
            failure_category="timeout",
            message="sampler timed out",
        )
        result = V2SamplingResult(
            **valid_result_kwargs(
                invalid_decode_diagnostics=(diagnostic,),
                sampling_system_failures=(failure,),
            )
        )

        assert result.invalid_decode_diagnostics[0].failure_reason == "LIGAND_CHEMISTRY_INVALID"
        assert result.sampling_system_failures[0].failure_category == "timeout"

    def test_failure_concepts_are_distinct_and_do_not_implement_later_tasks(self):
        from covalent_design.inference.v2_sampling import V2_SAMPLING_FAILURE_CONCEPTS

        assert V2_SAMPLING_FAILURE_CONCEPTS == (
            "request_validation_failure",
            "sampling_system_failure",
            "invalid_generated_sample",
            "export_failure",
            "docking_not_run",
            "evaluation_artifact_corruption",
        )

    def test_result_defaults_do_not_write_export_docking_or_evaluation(self):
        from covalent_design.inference.v2_sampling import V2SamplingResult

        result = V2SamplingResult(**valid_result_kwargs())

        assert result.export_status == "not_implemented"
        assert result.docking_status == "not_run"
        assert result.evaluation_status == "not_implemented"


class TestV2SamplingSerialization:
    def test_request_serialization_and_hash_are_deterministic(self):
        from covalent_design.inference.v2_sampling import (
            V2SamplingRequest,
            hash_v2_sampling_request,
            serialize_v2_sampling_request,
        )

        request_a = V2SamplingRequest(**valid_request_kwargs())
        request_b = V2SamplingRequest(**valid_request_kwargs())

        assert serialize_v2_sampling_request(request_a) == serialize_v2_sampling_request(request_b)
        assert hash_v2_sampling_request(request_a) == hash_v2_sampling_request(request_b)
        decoded = json.loads(serialize_v2_sampling_request(request_a))
        assert list(decoded) == sorted(decoded)

    def test_result_serialization_and_hash_are_deterministic(self):
        from covalent_design.inference.v2_sampling import (
            V2SamplingResult,
            hash_v2_sampling_result,
            serialize_v2_sampling_result,
        )

        result_a = V2SamplingResult(**valid_result_kwargs())
        result_b = V2SamplingResult(**valid_result_kwargs())

        assert serialize_v2_sampling_result(result_a) == serialize_v2_sampling_result(result_b)
        assert hash_v2_sampling_result(result_a) == hash_v2_sampling_result(result_b)
        assert hash_v2_sampling_result(result_a).startswith("sha256:")

    def test_different_seed_changes_request_hash(self):
        from covalent_design.inference.v2_sampling import V2SamplingRequest, hash_v2_sampling_request

        first = V2SamplingRequest(**valid_request_kwargs(random_seed=1))
        second = V2SamplingRequest(**valid_request_kwargs(random_seed=2))

        assert hash_v2_sampling_request(first) != hash_v2_sampling_request(second)


class TestV2SamplingBoundary:
    def test_no_heavy_dependencies_are_imported_by_v2_sampling(self):
        import covalent_design.inference.v2_sampling  # noqa: F401

        for name in ("torch", "rdkit", "PMDM", "PocketFlow", "pmdm", "pocketflow"):
            assert name not in sys.modules

    def test_source_has_no_task54_55_56_or_heavy_boundary_imports(self):
        import covalent_design.inference.v2_sampling as module

        source = Path(module.__file__).read_text(encoding="utf-8")
        lowered = source.lower()

        forbidden = (
            "import " + "torch",
            "from " + "torch",
            "import " + "rdkit",
            "from " + "rdkit",
            "import " + "pmdm",
            "from " + "pmdm",
            "import " + "pocketflow",
            "from " + "pocketflow",
            "covalent_design." + "evaluation",
            "v2_sampling" + "_smoke",
            "write_" + "mmcif",
            "run_" + "docking",
            "d:" + "\\codex_work" + "\\data",
            "data" + "/v2",
        )
        for token in forbidden:
            assert token not in lowered

    def test_constructing_request_does_not_create_output_root(self, tmp_path):
        from covalent_design.inference.v2_sampling import V2SamplingRequest

        output_root = tmp_path / "not-created"
        V2SamplingRequest(**valid_request_kwargs(output_root=str(output_root)))

        assert not output_root.exists()

    def test_sampling_system_failure_categories_remain_v1_frozen(self):
        assert SAMPLING_SYSTEM_FAILURE_CATEGORIES == (
            "crash",
            "oom",
            "timeout",
            "retry_exhausted",
            "checkpoint_load_failed",
            "sampler_invariant_violation",
        )