"""Task 27 generation run manifest and sampling failure accounting tests."""

from __future__ import annotations

import inspect
import json
import tempfile
import unittest
from dataclasses import fields, replace
from pathlib import Path
from typing import get_type_hints

from covalent_design.contracts.types import (
    SAMPLING_SYSTEM_FAILURE_CATEGORIES,
    ArtifactRef,
    ContractEnvelope,
    GenerationRunManifest,
    ProteinAtomIdentity,
    SamplingSystemFailure,
)
from covalent_design.inference.request_schema import (
    ProteinAtomLocator,
    ProteinChemicalStateRequest,
    ReactiveSiteGenerationRequest,
    ValidatedRequest,
)
from covalent_design.inference.request_validation import (
    validate_request,
    validate_request_file,
)
from covalent_design.io.artifacts import validate_artifact_ref
from covalent_design.io.jsonl import read_jsonl
from covalent_design.rules.validate import load_rule_table


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "inference" / "sampling_failures"
REQUEST_FIXTURES = ROOT / "tests" / "fixtures" / "inference" / "request_validation"
FIXED_TIMESTAMP = "2026-06-02T00:00:00Z"


class ScriptedSampler:
    """Deterministic sampler fake. Strings are failure categories."""

    def __init__(self, scripts: dict[int, list[object]] | None = None):
        self.scripts = {key: list(values) for key, values in (scripts or {}).items()}
        self.calls: list[int] = []

    def sample_one(self, request: ValidatedRequest, checkpoint: object, sample_id: int):
        from covalent_design.inference.sampler import SamplingFailureSignal

        self.calls.append(sample_id)
        outcomes = self.scripts.get(sample_id, [])
        outcome = outcomes.pop(0) if outcomes else {"sample_id": sample_id, "status": "ok"}
        if isinstance(outcome, str):
            raise SamplingFailureSignal(
                failure_category=outcome,
                message=f"{outcome} for sample {sample_id}",
                log_uri=f"logs/{outcome}-sample-{sample_id}.log",
                resource_snapshot={"sample_id": sample_id},
                traceback_text=f"Traceback: {outcome} sample={sample_id}",
            )
        return outcome


def _policy(max_retries: int = 0, retry_on: tuple[str, ...] = ()):
    from covalent_design.inference.run_manifest import SamplingPolicy

    return SamplingPolicy(max_retries=max_retries, retry_on_categories=retry_on)


def _generate(
    request: ValidatedRequest,
    output_dir: Path,
    sampler: ScriptedSampler,
    *,
    policy=None,
    checkpoint_ref: ArtifactRef | None = None,
    checkpoint_loader=None,
):
    from covalent_design.inference.run_manifest import generate

    return generate(
        request,
        policy if policy is not None else _policy(),
        output_dir=output_dir,
        job_id="task27-test-job",
        sampler=sampler,
        result_sink=lambda result: dict(result),
        checkpoint_ref=checkpoint_ref,
        checkpoint_loader=checkpoint_loader,
        clock=lambda: FIXED_TIMESTAMP,
    )


def _validated(sample_count: int = 3, request_id: str = "task27-request") -> ValidatedRequest:
    raw = ReactiveSiteGenerationRequest(
        request_id=request_id,
        protein_structure_uri=str(REQUEST_FIXTURES / "structures" / "valid_structure.pdb"),
        protein_structure_format="pdb",
        target_atom_identity_request=ProteinAtomLocator(
            chain_id="A",
            residue_number=42,
            residue_name="CYS",
            atom_name="SG",
        ),
        residue_reaction_family="CYS_MICHAEL_ADDITION",
        sample_count=sample_count,
        protein_chemical_state_request=ProteinChemicalStateRequest(
            target_atom_formal_charge=0,
            target_atom_protonation_state="thiolate",
            target_atom_hydrogen_state="absent",
        ),
    )
    rules = load_rule_table(REQUEST_FIXTURES / "task26_local_rule.yml")
    return validate_request(raw, rules)


def _validated_fixture(sample_count: int = 3) -> ValidatedRequest:
    validated = validate_request_file(
        FIXTURES / "valid_request.yml",
        rules_path=REQUEST_FIXTURES / "task26_local_rule.yml",
    )
    return replace(
        validated,
        request=replace(validated.request, sample_count=sample_count),
    )


def _checkpoint_fixture() -> ArtifactRef:
    return ArtifactRef(
        **json.loads((FIXTURES / "checkpoint_ref.json").read_text(encoding="utf-8"))
    )


def _failure_rows(output_dir: Path) -> tuple[dict[str, object], ...]:
    return read_jsonl(output_dir / "sampling_system_failures.jsonl")


class SamplingFailureContractTests(unittest.TestCase):
    def test_sampling_system_failure_has_frozen_nine_field_schema(self):
        self.assertEqual(
            tuple(field.name for field in fields(SamplingSystemFailure)),
            (
                "request_id",
                "sample_id",
                "failure_category",
                "failure_timestamp",
                "traceback_hash",
                "log_uri",
                "retry_count",
                "resource_snapshot",
                "message",
            ),
        )
        hints = get_type_hints(SamplingSystemFailure)
        self.assertIs(hints["request_id"], str)
        self.assertIs(hints["sample_id"], int)

    def test_all_six_categories_are_frozen(self):
        self.assertEqual(
            SAMPLING_SYSTEM_FAILURE_CATEGORIES,
            (
                "crash",
                "oom",
                "timeout",
                "retry_exhausted",
                "checkpoint_load_failed",
                "sampler_invariant_violation",
            ),
        )

    def test_each_failure_category_constructs(self):
        for category in SAMPLING_SYSTEM_FAILURE_CATEGORIES:
            failure = _failure(category=category)
            self.assertEqual(failure.failure_category, category)

    def test_invalid_category_rejected(self):
        with self.assertRaises(ValueError):
            _failure(category="disk_full")

    def test_negative_retry_count_rejected(self):
        with self.assertRaises(ValueError):
            _failure(retry_count=-1)

    def test_negative_sample_id_rejected(self):
        with self.assertRaises(ValueError):
            SamplingSystemFailure(
                request_id="request-001",
                sample_id=-1,
                failure_category="checkpoint_load_failed",
                failure_timestamp=FIXED_TIMESTAMP,
                traceback_hash="a" * 64,
                log_uri="logs/failure.log",
                retry_count=0,
            )

    def test_non_iso_timestamp_rejected(self):
        with self.assertRaises(ValueError):
            _failure(timestamp="yesterday")

    def test_non_iso_timestamp_separator_rejected(self):
        with self.assertRaises(ValueError):
            _failure(timestamp="2026-06-02X00:00:00Z")

    def test_non_iso_timestamp_trailing_text_rejected(self):
        with self.assertRaises(ValueError):
            _failure(timestamp="2026-06-02T00:00:00Z trailing")

    def test_invalid_traceback_hash_rejected(self):
        with self.assertRaises(ValueError):
            _failure(traceback_hash="not-a-sha256")


class SamplingPolicyTests(unittest.TestCase):
    def test_policy_requires_explicit_fields(self):
        from covalent_design.inference.run_manifest import SamplingPolicy

        with self.assertRaises(TypeError):
            SamplingPolicy()  # type: ignore[call-arg]

    def test_policy_rejects_negative_retry_count(self):
        with self.assertRaises(ValueError):
            _policy(max_retries=-1)

    def test_policy_rejects_unknown_retry_category(self):
        with self.assertRaises(ValueError):
            _policy(retry_on=("disk_full",))

    def test_policy_rejects_retry_exhausted_as_retry_input(self):
        with self.assertRaises(ValueError):
            _policy(retry_on=("retry_exhausted",))


class GenerateArtifactTests(unittest.TestCase):
    def test_generate_signature_accepts_validated_request(self):
        from covalent_design.inference.run_manifest import generate

        params = inspect.signature(generate).parameters
        self.assertEqual(params["request"].annotation, "ValidatedRequest")

    def test_generate_writes_deterministic_artifacts_and_refs(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            first_out = Path(first)
            second_out = Path(second)
            envelope = _generate(_validated(2), first_out, ScriptedSampler())
            _generate(_validated(2), second_out, ScriptedSampler())

            self.assertIsInstance(envelope, ContractEnvelope)
            self.assertIsInstance(envelope.payload, GenerationRunManifest)
            self.assertEqual(envelope.payload.role, "generation_run_manifest")
            self.assertEqual(
                set(envelope.payload.artifacts),
                {"request", "results", "sampling_system_failures"},
            )
            for filename in (
                "request.normalized.yml",
                "results.jsonl",
                "sampling_system_failures.jsonl",
                "run_manifest.yml",
            ):
                self.assertTrue((first_out / filename).is_file(), filename)
                self.assertEqual(
                    (first_out / filename).read_bytes(),
                    (second_out / filename).read_bytes(),
                    filename,
                )
            for ref in envelope.payload.artifacts.values():
                self.assertFalse(Path(ref.uri).is_absolute())
                self.assertNotIn("..", Path(ref.uri).parts)
                self.assertTrue(validate_artifact_ref(ref, root=first_out).passed)
            self.assertEqual(
                {ref.role for ref in envelope.artifacts},
                {"request", "results", "sampling_system_failures", "generation_run_manifest"},
            )
            self.assertTrue((first_out / "logs").is_dir())

    def test_raw_request_rejected_before_output_directory_created(self):
        raw = _validated(1).request
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "not-created"
            with self.assertRaises(TypeError):
                _generate(raw, out, ScriptedSampler())  # type: ignore[arg-type]
            self.assertFalse(out.exists())

    def test_normalized_request_written_before_checkpoint_loader(self):
        checkpoint_ref = ArtifactRef(uri="model.pt", sha256="a" * 64, format="pt")
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            observed: list[bool] = []

            def loader(ref: ArtifactRef):
                observed.append((out / "request.normalized.yml").is_file())
                raise RuntimeError(ref.uri)

            _generate(
                _validated(1),
                out,
                ScriptedSampler(),
                checkpoint_ref=checkpoint_ref,
                checkpoint_loader=loader,
            )
            self.assertEqual(observed, [True])

    def test_generation_root_contains_logs_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            _generate(_validated(1), out, ScriptedSampler())
            self.assertTrue((out / "logs").is_dir())

    def test_envelope_provenance_names_written_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            envelope = _generate(_validated(1), Path(tmp), ScriptedSampler())
            self.assertEqual(
                set(envelope.provenance.inputs),
                {"request", "results", "sampling_system_failures"},
            )

    def test_injected_traceback_normalizer_controls_failure_hash(self):
        from covalent_design.inference.run_manifest import generate

        sampler = ScriptedSampler({0: ["timeout"]})
        with tempfile.TemporaryDirectory() as tmp:
            generate(
                _validated(1),
                _policy(),
                output_dir=Path(tmp),
                job_id="normalizer-test",
                sampler=sampler,
                result_sink=lambda result: dict(result),
                clock=lambda: FIXED_TIMESTAMP,
                traceback_normalizer=lambda text: "normalized",
            )
            rows = _failure_rows(Path(tmp))
            import hashlib

            self.assertEqual(
                rows[0]["traceback_hash"],
                hashlib.sha256(b"normalized").hexdigest(),
            )


class SamplingAccountingTests(unittest.TestCase):
    def test_all_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            envelope = _generate(_validated(3), Path(tmp), ScriptedSampler())
            manifest = envelope.payload
            self.assertEqual(
                (
                    manifest.accepted_request_sample_count,
                    manifest.attempted_sample_count,
                    manifest.sampling_system_failure_count,
                    manifest.result_count,
                ),
                (3, 3, 0, 3),
            )
            self.assertEqual(len(read_jsonl(Path(tmp) / "results.jsonl")), 3)
            self.assertEqual(_failure_rows(Path(tmp)), ())

    def test_mixed_success_and_final_failure(self):
        sampler = ScriptedSampler({1: ["timeout"]})
        with tempfile.TemporaryDirectory() as tmp:
            manifest = _generate(_validated(3), Path(tmp), sampler).payload
            self.assertEqual(manifest.accepted_request_sample_count, 3)
            self.assertEqual(manifest.attempted_sample_count, 2)
            self.assertEqual(manifest.sampling_system_failure_count, 1)
            self.assertEqual(manifest.result_count, 2)
            self.assertEqual([row["failure_category"] for row in _failure_rows(Path(tmp))], ["timeout"])

    def test_retry_success_preserves_diagnostic_without_increasing_denominator(self):
        sampler = ScriptedSampler({0: ["crash", {"sample_id": 0, "status": "ok"}]})
        with tempfile.TemporaryDirectory() as tmp:
            manifest = _generate(
                _validated(1),
                Path(tmp),
                sampler,
                policy=_policy(max_retries=1, retry_on=("crash",)),
            ).payload
            self.assertEqual((manifest.attempted_sample_count, manifest.sampling_system_failure_count), (1, 0))
            self.assertEqual([row["failure_category"] for row in _failure_rows(Path(tmp))], ["crash"])
            self.assertEqual(sampler.calls, [0, 0])

    def test_retry_exhausted_writes_attempt_rows_and_final_sentinel(self):
        sampler = ScriptedSampler({0: ["crash", "crash", "crash"]})
        with tempfile.TemporaryDirectory() as tmp:
            manifest = _generate(
                _validated(1),
                Path(tmp),
                sampler,
                policy=_policy(max_retries=2, retry_on=("crash",)),
            ).payload
            rows = _failure_rows(Path(tmp))
            self.assertEqual(manifest.sampling_system_failure_count, 1)
            self.assertEqual(manifest.attempted_sample_count, 0)
            self.assertEqual([row["failure_category"] for row in rows], ["crash", "crash", "crash", "retry_exhausted"])
            self.assertEqual([row["retry_count"] for row in rows], [0, 1, 2, 2])

    def test_non_retryable_invariant_violation_is_final(self):
        sampler = ScriptedSampler({0: ["sampler_invariant_violation"]})
        with tempfile.TemporaryDirectory() as tmp:
            manifest = _generate(_validated(1), Path(tmp), sampler, policy=_policy(max_retries=3, retry_on=("crash",))).payload
            self.assertEqual(manifest.sampling_system_failure_count, 1)
            self.assertEqual(sampler.calls, [0])
            self.assertEqual(_failure_rows(Path(tmp))[0]["failure_category"], "sampler_invariant_violation")

    def test_multi_category_retry_policy_retries_configured_categories(self):
        sampler = ScriptedSampler(
            {0: ["oom", "crash", {"sample_id": 0, "status": "ok"}]}
        )
        with tempfile.TemporaryDirectory() as tmp:
            manifest = _generate(
                _validated(1),
                Path(tmp),
                sampler,
                policy=_policy(max_retries=2, retry_on=("crash", "oom")),
            ).payload
            self.assertEqual(
                (manifest.attempted_sample_count, manifest.sampling_system_failure_count),
                (1, 0),
            )
            self.assertEqual(
                [row["failure_category"] for row in _failure_rows(Path(tmp))],
                ["oom", "crash"],
            )

    def test_zero_retry_count_never_emits_retry_exhausted(self):
        sampler = ScriptedSampler({0: ["crash"]})
        with tempfile.TemporaryDirectory() as tmp:
            manifest = _generate(
                _validated(1),
                Path(tmp),
                sampler,
                policy=_policy(max_retries=0, retry_on=("crash",)),
            ).payload
            self.assertEqual(
                (manifest.attempted_sample_count, manifest.sampling_system_failure_count),
                (0, 1),
            )
            self.assertEqual(
                [row["failure_category"] for row in _failure_rows(Path(tmp))],
                ["crash"],
            )

    def test_sampling_failure_signal_fields_propagate_to_jsonl(self):
        import hashlib

        sampler = ScriptedSampler({0: ["timeout"]})
        with tempfile.TemporaryDirectory() as tmp:
            _generate(_validated(1), Path(tmp), sampler)
            row = _failure_rows(Path(tmp))[0]
            self.assertEqual(row["log_uri"], "logs/timeout-sample-0.log")
            self.assertEqual(row["resource_snapshot"], {"sample_id": 0})
            self.assertEqual(row["message"], "timeout for sample 0")
            self.assertEqual(
                row["traceback_hash"],
                hashlib.sha256(b"Traceback: timeout sample=0").hexdigest(),
            )

    def test_result_sink_called_only_for_success(self):
        from covalent_design.inference.run_manifest import generate

        calls: list[int] = []
        sampler = ScriptedSampler({1: ["oom"]})
        with tempfile.TemporaryDirectory() as tmp:
            envelope = generate(
                _validated(3),
                _policy(),
                output_dir=Path(tmp),
                job_id="sink-test",
                sampler=sampler,
                result_sink=lambda result: calls.append(result["sample_id"]) or dict(result),
                clock=lambda: FIXED_TIMESTAMP,
            )
            self.assertEqual(calls, [0, 2])
            self.assertEqual(envelope.payload.result_count, len(calls))


class CheckpointFailureTests(unittest.TestCase):
    def test_checkpoint_failure_accounts_each_accepted_sample_id(self):
        checkpoint_ref = ArtifactRef(uri="model.pt", sha256="a" * 64, format="pt", role="checkpoint")

        def fail_loader(ref: ArtifactRef):
            raise RuntimeError(f"cannot load {ref.uri}")

        with tempfile.TemporaryDirectory() as tmp:
            manifest = _generate(
                _validated(3),
                Path(tmp),
                ScriptedSampler(),
                checkpoint_ref=checkpoint_ref,
                checkpoint_loader=fail_loader,
            ).payload
            rows = _failure_rows(Path(tmp))
            self.assertEqual((manifest.accepted_request_sample_count, manifest.attempted_sample_count, manifest.sampling_system_failure_count), (3, 0, 3))
            self.assertEqual([row["sample_id"] for row in rows], [0, 1, 2])
            self.assertEqual({row["failure_category"] for row in rows}, {"checkpoint_load_failed"})


class FixtureAndScopeTests(unittest.TestCase):
    def test_required_committed_fixtures_exist(self):
        for name in (
            "valid_request.yml",
            "checkpoint_ref.json",
            "failure_crash.json",
            "failure_oom.json",
            "failure_timeout.json",
            "failure_retry_exhausted.json",
            "failure_checkpoint_load_failed.json",
            "failure_sampler_invariant_violation.json",
            "expected_all_failure_run_manifest.yml",
            "expected_retry_success_run_manifest.yml",
            "expected_mixed_run_manifest.yml",
        ):
            self.assertTrue((FIXTURES / name).is_file(), name)

    def test_fixture_failure_categories_cover_contract(self):
        found = {
            json.loads(path.read_text(encoding="utf-8"))["failure_category"]
            for path in FIXTURES.glob("failure_*.json")
        }
        self.assertEqual(found, set(SAMPLING_SYSTEM_FAILURE_CATEGORIES))

    def test_committed_run_manifest_golden_fixtures(self):
        scenarios = (
            (
                "expected_all_failure_run_manifest.yml",
                _validated_fixture(),
                "test-job-all-failure",
                ScriptedSampler({0: ["crash"], 1: ["oom"], 2: ["timeout"]}),
                _policy(),
                None,
            ),
            (
                "expected_mixed_run_manifest.yml",
                _validated_fixture(),
                "test-job-mixed",
                ScriptedSampler({1: ["timeout"]}),
                _policy(),
                _checkpoint_fixture(),
            ),
            (
                "expected_retry_success_run_manifest.yml",
                _validated_fixture(sample_count=1),
                "test-job-retry-success",
                ScriptedSampler({0: ["crash", {"sample_id": 0, "status": "ok"}]}),
                _policy(max_retries=1, retry_on=("crash",)),
                _checkpoint_fixture(),
            ),
        )
        for expected_name, request, job_id, sampler, policy, checkpoint_ref in scenarios:
            with self.subTest(expected_name), tempfile.TemporaryDirectory() as tmp:
                from covalent_design.inference.run_manifest import generate

                generate(
                    request,
                    policy,
                    output_dir=Path(tmp),
                    job_id=job_id,
                    sampler=sampler,
                    result_sink=lambda result: dict(result),
                    checkpoint_ref=checkpoint_ref,
                    clock=lambda: FIXED_TIMESTAMP,
                )
                self.assertEqual(
                    (Path(tmp) / "run_manifest.yml").read_bytes(),
                    (FIXTURES / expected_name).read_bytes(),
                )

    def test_task27_source_has_no_heavy_dependency_or_task28_writer(self):
        source = (ROOT / "src" / "covalent_design" / "inference" / "run_manifest.py").read_text(encoding="utf-8")
        lowered = source.lower()
        self.assertNotIn("import torch", lowered)
        self.assertNotIn("import rdkit", lowered)
        self.assertNotIn("result_writer", lowered)
        self.assertNotIn(".glob(", lowered)
        self.assertNotIn(".rglob(", lowered)


def _failure(
    *,
    category: str = "crash",
    retry_count: int = 0,
    timestamp: str = FIXED_TIMESTAMP,
    traceback_hash: str = "a" * 64,
) -> SamplingSystemFailure:
    return SamplingSystemFailure(
        request_id="request-001",
        sample_id=0,
        failure_category=category,
        failure_timestamp=timestamp,
        traceback_hash=traceback_hash,
        log_uri="logs/failure.log",
        retry_count=retry_count,
        resource_snapshot=None,
        message="failure",
    )


if __name__ == "__main__":
    unittest.main()
