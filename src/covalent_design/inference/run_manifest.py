"""Task 27 generation run manifest, SamplingPolicy, and generate() entry point."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping

from covalent_design.contracts.types import (
    CONTRACT_VERSION,
    SCHEMA_VERSION,
    SAMPLING_SYSTEM_FAILURE_CATEGORIES,
    ArtifactRef,
    ContractEnvelope,
    GenerationRunManifest,
    Provenance,
    SamplingSystemFailure,
    ValidationReceipt,
)
from covalent_design.inference.request_schema import ValidatedRequest
from covalent_design.inference.request_validation import write_normalized_request
from covalent_design.inference.sampler import SamplingFailureSignal
from covalent_design.io.artifacts import artifact_ref_from_file
from covalent_design.io.jsonl import write_jsonl


@dataclass(frozen=True)
class SamplingPolicy:
    """Retry policy controlling per-sample failure handling.

    max_retries: maximum number of retry attempts per sample.
    retry_on_categories: failure categories eligible for retry.
    """

    max_retries: int
    retry_on_categories: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.max_retries < 0:
            raise ValueError(
                f"max_retries must be non-negative, got {self.max_retries}"
            )
        if "retry_exhausted" in self.retry_on_categories:
            raise ValueError(
                "retry_exhausted is a terminal sentinel emitted by the run loop; "
                "it must not appear in retry_on_categories"
            )
        invalid = set(self.retry_on_categories) - set(SAMPLING_SYSTEM_FAILURE_CATEGORIES)
        if invalid:
            raise ValueError(
                f"Unknown retry categories: {sorted(invalid)}. "
                f"Allowed: {SAMPLING_SYSTEM_FAILURE_CATEGORIES}"
            )


def generate(
    request: ValidatedRequest,
    policy: SamplingPolicy,
    *,
    output_dir: Path,
    job_id: str,
    sampler,
    result_sink: Callable[[object], Mapping[str, object]],
    checkpoint_ref: ArtifactRef | None = None,
    checkpoint_loader: Callable[[ArtifactRef], object] | None = None,
    clock: Callable[[], str] | None = None,
    traceback_normalizer: Callable[[str], str] | None = None,
) -> ContractEnvelope[GenerationRunManifest]:
    """Run generation for every accepted request sample.

    Returns ContractEnvelope[GenerationRunManifest] with the complete
    run manifest as payload and output artifact references.
    """
    if not isinstance(request, ValidatedRequest):
        raise TypeError(
            f"request must be a ValidatedRequest, got {type(request).__name__}"
        )

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "logs").mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # normalized request artifact (before checkpoint loading)
    # ------------------------------------------------------------------
    write_normalized_request(
        request, output_dir / "request.normalized.yml"
    )
    request_ref = artifact_ref_from_file(
        output_dir / "request.normalized.yml",
        role="request",
        format="yml",
    )

    if clock is None:
        from datetime import datetime, timezone

        def _clock() -> str:
            return datetime.now(timezone.utc).isoformat()

        clock = _clock

    # ------------------------------------------------------------------
    # checkpoint loading (once per run)
    # ------------------------------------------------------------------
    checkpoint: object = None
    checkpoint_load_failed = False
    if checkpoint_ref is not None and checkpoint_loader is not None:
        try:
            checkpoint = checkpoint_loader(checkpoint_ref)
        except Exception:
            checkpoint_load_failed = True

    # ------------------------------------------------------------------
    # per-sample generation loop with retry
    # ------------------------------------------------------------------
    accepted_count = request.request.sample_count
    attempted_count = 0
    failure_count = 0
    results: list[dict[str, object]] = []
    failure_rows: list[dict[str, object]] = []

    for sample_id in range(accepted_count):
        if checkpoint_load_failed:
            _record_checkpoint_failure(
                request.request.request_id,
                sample_id,
                checkpoint_ref,
                clock,
                failure_rows,
                traceback_normalizer,
            )
            failure_count += 1
            continue

        retry_count = 0

        while True:
            try:
                result = sampler.sample_one(request, checkpoint, sample_id)
            except SamplingFailureSignal as signal:
                _record_failure(
                    request.request.request_id,
                    sample_id,
                    signal,
                    retry_count,
                    clock,
                    failure_rows,
                    traceback_normalizer,
                )
                if _should_retry(signal.failure_category, retry_count, policy):
                    retry_count += 1
                    continue
                # Final failure: write retry_exhausted sentinel if retries were used
                if retry_count > 0:
                    _record_exhausted(
                        request.request.request_id,
                        sample_id,
                        signal,
                        retry_count,
                        clock,
                        failure_rows,
                        traceback_normalizer,
                    )
                failure_count += 1
                break
            else:
                row = result_sink(result)
                results.append(dict(row))
                attempted_count += 1
                break

    # ------------------------------------------------------------------
    # write results.jsonl
    # ------------------------------------------------------------------
    results_ref = write_jsonl(
        output_dir / "results.jsonl",
        results,
        role="results",
    )

    # ------------------------------------------------------------------
    # write sampling_system_failures.jsonl
    # ------------------------------------------------------------------
    failures_ref = write_jsonl(
        output_dir / "sampling_system_failures.jsonl",
        failure_rows,
        role="sampling_system_failures",
    )

    # ------------------------------------------------------------------
    # build and write run manifest
    # ------------------------------------------------------------------
    manifest = GenerationRunManifest(
        job_id=job_id,
        request_id=request.request.request_id,
        checkpoint_ref=checkpoint_ref,
        accepted_request_sample_count=accepted_count,
        attempted_sample_count=attempted_count,
        sampling_system_failure_count=failure_count,
        result_count=len(results),
        artifacts={
            "request": request_ref,
            "results": results_ref,
            "sampling_system_failures": failures_ref,
        },
    )
    _write_run_manifest(manifest, output_dir / "run_manifest.yml")

    # ------------------------------------------------------------------
    # envelope
    # ------------------------------------------------------------------
    manifest_ref = artifact_ref_from_file(
        output_dir / "run_manifest.yml",
        role="generation_run_manifest",
        format="yml",
    )
    receipt = ValidationReceipt(
        validator="covalent_design.inference.generate",
        contract_version=CONTRACT_VERSION,
        input_sha256=request_ref.sha256,
        passed=True,
    )
    envelope = ContractEnvelope[GenerationRunManifest](
        payload=manifest,
        artifacts=(request_ref, results_ref, failures_ref, manifest_ref),
        receipt=receipt,
        provenance=Provenance(
            inputs={
                "request": request_ref,
                "results": results_ref,
                "sampling_system_failures": failures_ref,
            },
        ),
    )
    return envelope


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _should_retry(category: str, retry_count: int, policy: SamplingPolicy) -> bool:
    return category in policy.retry_on_categories and retry_count < policy.max_retries


def _normalise_traceback(tb_text: str) -> str:
    return tb_text.strip().replace("\r\n", "\n").replace("\r", "\n")


def _traceback_hash(tb_text: str, traceback_normalizer: Callable[[str], str] | None = None) -> str:
    if traceback_normalizer is not None:
        normalised = traceback_normalizer(tb_text)
    else:
        normalised = _normalise_traceback(tb_text)
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()


def _record_failure(
    request_id: str,
    sample_id: int,
    signal: SamplingFailureSignal,
    retry_count: int,
    clock: Callable[[], str],
    rows: list[dict[str, object]],
    traceback_normalizer: Callable[[str], str] | None = None,
) -> None:
    tb_hash = _traceback_hash(signal.traceback_text, traceback_normalizer)
    failure = SamplingSystemFailure(
        request_id=request_id,
        sample_id=sample_id,
        failure_category=signal.failure_category,
        failure_timestamp=clock(),
        traceback_hash=tb_hash,
        log_uri=signal.log_uri,
        retry_count=retry_count,
        resource_snapshot=signal.resource_snapshot,
        message=signal.message,
    )
    rows.append(_failure_to_dict(failure))


def _record_exhausted(
    request_id: str,
    sample_id: int,
    signal: SamplingFailureSignal,
    retry_count: int,
    clock: Callable[[], str],
    rows: list[dict[str, object]],
    traceback_normalizer: Callable[[str], str] | None = None,
) -> None:
    tb_hash = _traceback_hash(signal.traceback_text, traceback_normalizer)
    failure = SamplingSystemFailure(
        request_id=request_id,
        sample_id=sample_id,
        failure_category="retry_exhausted",
        failure_timestamp=clock(),
        traceback_hash=tb_hash,
        log_uri=signal.log_uri,
        retry_count=retry_count,
        resource_snapshot=signal.resource_snapshot,
        message=f"All {retry_count + 1} retry attempts exhausted for sample {sample_id}",
    )
    rows.append(_failure_to_dict(failure))


def _record_checkpoint_failure(
    request_id: str,
    sample_id: int,
    checkpoint_ref: ArtifactRef | None,
    clock: Callable[[], str],
    rows: list[dict[str, object]],
    traceback_normalizer: Callable[[str], str] | None = None,
) -> None:
    uri = checkpoint_ref.uri if checkpoint_ref else "checkpoint"
    failure = SamplingSystemFailure(
        request_id=request_id,
        sample_id=sample_id,
        failure_category="checkpoint_load_failed",
        failure_timestamp=clock(),
        traceback_hash=_traceback_hash(f"Checkpoint load failed: {uri}", traceback_normalizer),
        log_uri=f"logs/checkpoint_load_failed.log",
        retry_count=0,
        resource_snapshot=None,
        message=f"Checkpoint {uri} failed to load",
    )
    rows.append(_failure_to_dict(failure))


def _failure_to_dict(f: SamplingSystemFailure) -> dict[str, object]:
    result: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "contract_version": CONTRACT_VERSION,
        "request_id": f.request_id,
        "sample_id": f.sample_id,
        "failure_category": f.failure_category,
        "failure_timestamp": f.failure_timestamp,
        "traceback_hash": f.traceback_hash,
        "log_uri": f.log_uri,
        "retry_count": f.retry_count,
        "message": f.message,
    }
    if f.resource_snapshot is not None:
        result["resource_snapshot"] = dict(f.resource_snapshot)
    else:
        result["resource_snapshot"] = None
    return result


# ---------------------------------------------------------------------------
# deterministic YAML writer for GenerationRunManifest
# ---------------------------------------------------------------------------


def _write_run_manifest(manifest: GenerationRunManifest, path: Path) -> None:
    lines: list[str] = []
    _emit(lines, 0, "schema_version", manifest.schema_version)
    _emit(lines, 0, "contract_version", manifest.contract_version)
    _emit(lines, 0, "role", manifest.role)
    _emit(lines, 0, "job_id", manifest.job_id)
    _emit(lines, 0, "request_id", manifest.request_id)
    if manifest.checkpoint_ref is None:
        _emit_null(lines, 0, "checkpoint_ref")
    else:
        _emit_artifact(lines, 0, "checkpoint_ref", manifest.checkpoint_ref)
    _emit_int(lines, 0, "accepted_request_sample_count", manifest.accepted_request_sample_count)
    _emit_int(lines, 0, "attempted_sample_count", manifest.attempted_sample_count)
    _emit_int(lines, 0, "sampling_system_failure_count", manifest.sampling_system_failure_count)
    _emit_int(lines, 0, "result_count", manifest.result_count)
    if not manifest.artifacts:
        _emit_null(lines, 0, "artifacts")
    else:
        lines.append("artifacts:")
        for key in sorted(manifest.artifacts):
            ref = manifest.artifacts[key]
            lines.append(f"  {key}:")
            _emit_str(lines, 2, "uri", ref.uri)
            _emit_str(lines, 2, "sha256", ref.sha256)
            _emit_str(lines, 2, "format", ref.format)
            _emit_str(lines, 2, "schema_version", ref.schema_version)
            _emit_str(lines, 2, "role", ref.role)
            _emit_int(lines, 2, "bytes", ref.bytes)
    lines.append("")
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines))


def _emit(lines: list[str], indent: int, key: str, value: str) -> None:
    prefix = "  " * indent
    lines.append(f"{prefix}{key}: {_yaml_str(value)}")


def _emit_str(lines: list[str], indent: int, key: str, value: str) -> None:
    prefix = "  " * indent
    lines.append(f"{prefix}{key}: {_yaml_str(value)}")


def _emit_int(lines: list[str], indent: int, key: str, value: int) -> None:
    prefix = "  " * indent
    lines.append(f"{prefix}{key}: {value}")


def _emit_null(lines: list[str], indent: int, key: str) -> None:
    prefix = "  " * indent
    lines.append(f"{prefix}{key}: null")


def _emit_artifact(lines: list[str], indent: int, key: str, ref: ArtifactRef) -> None:
    prefix = "  " * indent
    lines.append(f"{prefix}{key}:")
    _emit_str(lines, indent + 1, "uri", ref.uri)
    _emit_str(lines, indent + 1, "sha256", ref.sha256)
    _emit_str(lines, indent + 1, "format", ref.format)
    _emit_str(lines, indent + 1, "schema_version", ref.schema_version)
    _emit_str(lines, indent + 1, "role", ref.role)
    _emit_int(lines, indent + 1, "bytes", ref.bytes)


def _yaml_str(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)
