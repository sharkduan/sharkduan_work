from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from covalent_design._yaml_loader import load_yaml_config
from covalent_design.contracts.types import (
    ArtifactRef,
    FAILURE_REASON_CODES,
    SAMPLING_SYSTEM_FAILURE_CATEGORIES,
)

FIXTURE_DIR = Path("tests/fixtures/v2/sampling")
CONFIG_PATH = Path("configs/v2_sampling_smoke.yml")
SHA = "sha256:" + "c" * 64


def artifact(role: str) -> ArtifactRef:
    return ArtifactRef(
        uri=f"manifest-ref://v2/sampling-smoke/{role}",
        sha256=SHA,
        format="manifest_ref",
        role=role,
        bytes=123,
    )


def request_kwargs(**overrides):
    data = {
        "request_id": "v2-sampling-smoke-001",
        "checkpoint_ref": artifact("checkpoint"),
        "checkpoint_manifest_ref": artifact("checkpoint_manifest"),
        "environment_manifest_ref": artifact("environment_manifest"),
        "split_name": "test",
        "record_ids": (),
        "family_filter": (),
        "random_seed": 42,
        "sample_count": 6,
        "output_root": "local-only-v2-sampling-smoke-output",
        "max_retries": 1,
        "retry_on_categories": ("crash", "timeout"),
        "baseline_mode": "non_pmdm_baseline",
        "generation_mode": "reactive_site",
    }
    data.update(overrides)
    return data


def load_records() -> tuple[dict[str, object], ...]:
    records = []
    for line in (FIXTURE_DIR / "records.jsonl").read_text(encoding="utf-8-sig").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return tuple(records)


def load_split_index() -> dict[str, object]:
    return json.loads((FIXTURE_DIR / "split_index.json").read_text(encoding="utf-8-sig"))


def run_request(**overrides):
    from covalent_design.inference.v2_sampling import (
        V2SamplingRequest,
        run_deterministic_fixture_sampling,
    )

    request = V2SamplingRequest(**request_kwargs(**overrides))
    return run_deterministic_fixture_sampling(
        request,
        load_records(),
        fixture_split_index=load_split_index(),
    )


class TestV2SamplingSmokeDeterminism:
    def test_same_seed_produces_identical_outputs(self):
        from covalent_design.inference.v2_sampling import (
            hash_v2_sampling_result,
            serialize_v2_sampling_result,
        )

        first = run_request(random_seed=42)
        second = run_request(random_seed=42)

        assert serialize_v2_sampling_result(first) == serialize_v2_sampling_result(second)
        assert hash_v2_sampling_result(first) == hash_v2_sampling_result(second)

    def test_different_seed_changes_deterministic_output(self):
        from covalent_design.inference.v2_sampling import hash_v2_sampling_result

        first = run_request(random_seed=42)
        second = run_request(random_seed=43)

        assert hash_v2_sampling_result(first) != hash_v2_sampling_result(second)

    def test_output_serialization_has_sorted_keys(self):
        from covalent_design.inference.v2_sampling import serialize_v2_sampling_result

        decoded = json.loads(serialize_v2_sampling_result(run_request(random_seed=42)))

        assert list(decoded) == sorted(decoded)


class TestV2SamplingSmokeSelectors:
    def test_held_out_selector_uses_test_split(self):
        result = run_request(split_name="test", sample_count=4)

        assert result.split_name == "test"
        assert result.requested_sample_count == 4
        assert all("TEST" in item.message for item in result.invalid_decode_diagnostics)
        assert all("TEST" in item.message for item in result.sampling_system_failures)

    def test_train_selector_uses_train_split(self):
        result = run_request(split_name="train", sample_count=4)

        assert result.split_name == "train"
        assert all("TRAIN" in item.message for item in result.invalid_decode_diagnostics)
        assert all("TRAIN" in item.message for item in result.sampling_system_failures)

    def test_val_selector_uses_val_split(self):
        result = run_request(split_name="val", sample_count=4)

        assert result.split_name == "val"
        assert all("VAL" in item.message for item in result.invalid_decode_diagnostics)
        assert all("VAL" in item.message for item in result.sampling_system_failures)

    def test_per_family_selector_filters_records(self):
        result = run_request(
            split_name="test",
            family_filter=("CYS_MICHAEL_ADDITION",),
            sample_count=4,
        )

        assert result.family_filter == ("CYS_MICHAEL_ADDITION",)
        assert all("CYS" in item.message for item in result.invalid_decode_diagnostics)
        assert all("CYS" in item.message for item in result.sampling_system_failures)

    def test_record_id_selector_bypasses_split_selector(self):
        result = run_request(
            split_name=None,
            record_ids=("SMOKE-TRAIN-CYS", "SMOKE-TEST-LYS"),
            sample_count=4,
        )

        assert result.split_name is None
        messages = [item.message for item in result.invalid_decode_diagnostics]
        messages += [item.message for item in result.sampling_system_failures]
        assert messages
        assert any("SMOKE-TRAIN-CYS" in item for item in messages)
        assert any("SMOKE-TEST-LYS" in item for item in messages)


class TestV2SamplingSmokeAccounting:
    def test_count_conservation_is_preserved(self):
        result = run_request(sample_count=8)

        assert result.valid_sample_count + result.invalid_sample_count == result.attempted_sample_count
        assert result.attempted_sample_count + result.sampling_system_failure_count == result.requested_sample_count

    def test_invalid_decode_and_system_failures_are_separate(self):
        result = run_request(random_seed=42, sample_count=12)

        assert result.invalid_decode_diagnostics
        assert result.sampling_system_failures
        assert result.invalid_sample_count == len(result.invalid_decode_diagnostics)
        assert result.sampling_system_failure_count == len(result.sampling_system_failures)
        assert all(item.failure_reason in FAILURE_REASON_CODES for item in result.invalid_decode_diagnostics)
        assert all(item.failure_category in SAMPLING_SYSTEM_FAILURE_CATEGORIES for item in result.sampling_system_failures)

    def test_failed_sample_does_not_become_valid_sample(self):
        result = run_request(random_seed=42, sample_count=12)

        assert result.valid_sample_count == result.attempted_sample_count - result.invalid_sample_count
        assert result.valid_sample_count < result.requested_sample_count

    def test_empty_selection_preserves_failure_accounting(self):
        result = run_request(
            split_name="test",
            family_filter=("ABSENT_FAMILY",),
            sample_count=3,
        )

        assert result.attempted_sample_count == 0
        assert result.valid_sample_count == 0
        assert result.invalid_sample_count == 0
        assert result.sampling_system_failure_count == 3
        assert len(result.sampling_system_failures) == 3


class TestV2SamplingSmokeRequestAndConfig:
    def test_task53_request_validation_is_reused(self):
        from covalent_design.inference.v2_sampling import V2SamplingRequest

        with pytest.raises(ValueError, match="reactive_site"):
            V2SamplingRequest(**request_kwargs(generation_mode="reference_ligand"))

    def test_smoke_config_loads_from_config_file(self):
        config = load_yaml_config(str(CONFIG_PATH))

        assert config["profile"] == "v2_sampling_smoke"
        assert config["execution_mode"] == "fixture"
        assert config["records_path"] == "tests/fixtures/v2/sampling/records.jsonl"
        assert config["split_index_path"] == "tests/fixtures/v2/sampling/split_index.json"
        assert config["sample_count"] == 6
        assert config["baseline_mode"] == "non_pmdm_baseline"

    def test_fixture_files_exist_and_are_relative(self):
        config = load_yaml_config(str(CONFIG_PATH))

        for key in ("records_path", "split_index_path"):
            path = Path(config[key])
            assert not path.is_absolute()
            assert path.exists()


class TestV2SamplingSmokeBoundary:
    def test_smoke_does_not_create_output_root_or_artifacts(self, tmp_path):
        output_root = tmp_path / "smoke-output"
        result = run_request(output_root=str(output_root), sample_count=5)

        assert result.export_status == "not_implemented"
        assert result.docking_status == "not_run"
        assert result.evaluation_status == "not_implemented"
        assert not output_root.exists()
        assert not list(tmp_path.rglob("*.cif"))
        assert not list(tmp_path.rglob("*.pdb"))
        assert not list(tmp_path.rglob("*.sdf"))

    def test_no_heavy_dependencies_are_imported(self):
        import covalent_design.inference.v2_sampling  # noqa: F401

        for name in ("torch", "rdkit", "PMDM", "PocketFlow", "pmdm", "pocketflow"):
            assert name not in sys.modules

    def test_source_and_config_have_no_forbidden_boundaries(self):
        import covalent_design.inference.v2_sampling as module

        source = Path(module.__file__).read_text(encoding="utf-8").lower()
        test_source = Path(__file__).read_text(encoding="utf-8").lower()
        config_source = CONFIG_PATH.read_text(encoding="utf-8").lower()
        combined = "\n".join((source, test_source, config_source))
        forbidden = (
            "import " + "torch",
            "from " + "torch",
            "import " + "rdkit",
            "from " + "rdkit",
            "import " + "pmdm",
            "from " + "pmdm",
            "import " + "pocketflow",
            "from " + "pocketflow",
            "v2_" + "metrics",
            "v2_" + "evaluate",
            "write_" + "mmcif",
            "run_" + "docking",
            "d:" + "\\\\codex_work" + "\\\\data",
            "data" + "/v2",
        )
        for token in forbidden:
            assert token not in combined
