"""Task 33 reports - thin compatibility facade.

Re-exports split-aware evaluation report construction from split_metrics.
"""

from covalent_design.evaluation.split_metrics import (
    JoinedAssignment,
    StratifiedEvaluationSummary,
    build_stratified_evaluation_summary,
    join_results_to_split_assignments,
    load_leakage_report,
    load_split_index,
    stratified_evaluation_summary_to_dict,
    summarize_split_results,
    validate_leakage_report_for_evaluation,
    validate_split_index_for_evaluation,
    write_stratified_evaluation_summary,
)

__all__ = [
    "JoinedAssignment",
    "StratifiedEvaluationSummary",
    "build_stratified_evaluation_summary",
    "join_results_to_split_assignments",
    "load_leakage_report",
    "load_split_index",
    "stratified_evaluation_summary_to_dict",
    "summarize_split_results",
    "validate_leakage_report_for_evaluation",
    "validate_split_index_for_evaluation",
    "write_stratified_evaluation_summary",
]
