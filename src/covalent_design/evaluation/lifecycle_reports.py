"""Task 31 lifecycle reports - thin compatibility facade.

Re-exports everything from validity_metrics and failure_modes.
Must not duplicate denominator equations or lifecycle logic.
"""

from covalent_design.evaluation.failure_modes import (
    FROZEN_REASON_STAGE_MAP,
    FailureModeReport,
    build_failure_mode_report,
    build_failure_mode_report_from_manifest,
    failure_mode_report_to_dict,
    write_failure_mode_report,
)
from covalent_design.evaluation.validity_metrics import (
    summarize_lifecycle_statuses,
    validate_results_before_aggregation,
)

__all__ = [
    "FROZEN_REASON_STAGE_MAP",
    "FailureModeReport",
    "build_failure_mode_report",
    "build_failure_mode_report_from_manifest",
    "failure_mode_report_to_dict",
    "summarize_lifecycle_statuses",
    "validate_results_before_aggregation",
    "write_failure_mode_report",
]
