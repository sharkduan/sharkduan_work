"""Task 27 typed exception for per-sample sampling system failures."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class SamplingFailureSignal(Exception):
    """Signal raised when a sampler encounters a non-recoverable system failure.

    Per-sample failures (crash, OOM, timeout, invariant violation) are
    run-level events tracked in sampling_system_failures.jsonl, not
    invalid generated samples.
    """

    failure_category: str
    message: str
    log_uri: str
    resource_snapshot: Mapping[str, object] | None = None
    traceback_text: str = ""
