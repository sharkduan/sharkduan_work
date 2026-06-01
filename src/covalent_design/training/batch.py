"""Task 22: Training batch loading boundary."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Optional

from covalent_design.contracts.errors import ContractError
from covalent_design.contracts.types import BatchSpec, TrainingDatasetIndex
from covalent_design.io.jsonl import read_jsonl
from covalent_design.model.batch import make_model_batch


def load_training_batch(
    dataset: TrainingDatasetIndex,
    batch_id: object,
    *,
    batch_spec: Optional[BatchSpec] = None,
):
    """Load one deterministic singleton training batch through Task 17.

    ``batch_id`` uses the stable ``batch-<zero-based-index>`` vocabulary over
    the dataset's sorted entries. Singleton batching is the v1 preflight
    contract; later batching strategies remain additive.
    """
    index = _parse_batch_id(batch_id)
    entries = tuple(sorted(dataset.records, key=lambda entry: entry.record_id))
    if index >= len(entries):
        raise ContractError(
            code="TRAINING_BATCH_ID_NOT_FOUND",
            owner="training",
            message=f"batch_id {batch_id!r} is outside dataset range",
        )
    if not dataset.records_path:
        raise ContractError(
            code="TRAINING_BATCH_RECORDS_PATH_MISSING",
            owner="training",
            message="TrainingDatasetIndex.records_path is required for batch loading",
        )

    records_path = Path(dataset.records_path)
    try:
        rows = read_jsonl(records_path)
    except (OSError, ValueError) as exc:
        raise ContractError(
            code="TRAINING_BATCH_RECORDS_UNREADABLE",
            owner="training",
            message=str(exc),
            location=str(records_path),
        ) from exc

    record_id = entries[index].record_id
    selected = [row for row in rows if row.get("record_id") == record_id]
    if len(selected) != 1:
        raise ContractError(
            code="TRAINING_BATCH_RECORD_NOT_FOUND",
            owner="training",
            message=f"expected one finalized record for {record_id!r}",
            location=str(records_path),
        )

    temp_path: Optional[Path] = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            suffix=".jsonl",
            prefix=".training-batch-",
            dir=records_path.parent,
            delete=False,
        ) as handle:
            handle.write(json.dumps(selected[0], sort_keys=True, separators=(",", ":")))
            handle.write("\n")
            temp_path = Path(handle.name)
        return make_model_batch(temp_path, batch_spec=batch_spec)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def _parse_batch_id(batch_id: object) -> int:
    if not isinstance(batch_id, str) or not batch_id.startswith("batch-"):
        raise ContractError(
            code="TRAINING_BATCH_ID_INVALID",
            owner="training",
            message="batch_id must use the form 'batch-<zero-based-index>'",
        )
    suffix = batch_id[len("batch-"):]
    if not suffix.isdigit():
        raise ContractError(
            code="TRAINING_BATCH_ID_INVALID",
            owner="training",
            message="batch_id must use the form 'batch-<zero-based-index>'",
        )
    return int(suffix)
