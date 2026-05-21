import unittest

from covalent_design.contracts import EdgeDenominators, EvaluationSummary
from covalent_design.contracts.denominators import (
    validate_edge_denominators,
    validate_evaluation_summary,
)


class EdgeDenominatorContractTests(unittest.TestCase):
    def test_valid_edge_denominators_pass(self) -> None:
        denominators = EdgeDenominators(
            candidate_count=5,
            natural_candidate_count=4,
            forced_positive_count=1,
            eligible_edge_count=4,
            masked_candidate_count=1,
            edge_loss_denominator=4,
            bond_type_loss_denominator=1,
            geometry_loss_denominator=1,
            message_passing_candidate_count=3,
            gate_evaluated_count=2,
        )

        receipt = validate_edge_denominators(denominators)

        self.assertTrue(receipt.passed)
        denominators.validate()

    def test_edge_denominators_reject_negative_counts(self) -> None:
        denominators = EdgeDenominators(
            candidate_count=-1,
            natural_candidate_count=0,
            forced_positive_count=0,
            eligible_edge_count=0,
            masked_candidate_count=0,
            edge_loss_denominator=0,
            bond_type_loss_denominator=0,
            geometry_loss_denominator=0,
            message_passing_candidate_count=0,
            gate_evaluated_count=0,
        )

        receipt = validate_edge_denominators(denominators)

        self.assertFalse(receipt.passed)
        self.assertEqual(receipt.errors[0].code, "EDGE_DENOMINATOR_NEGATIVE")

    def test_edge_denominators_reject_forced_positive_message_passing_leak(self) -> None:
        denominators = EdgeDenominators(
            candidate_count=3,
            natural_candidate_count=1,
            forced_positive_count=2,
            eligible_edge_count=3,
            masked_candidate_count=0,
            edge_loss_denominator=3,
            bond_type_loss_denominator=1,
            geometry_loss_denominator=1,
            message_passing_candidate_count=2,
            gate_evaluated_count=0,
        )

        receipt = validate_edge_denominators(denominators)

        self.assertFalse(receipt.passed)
        self.assertEqual(
            receipt.errors[0].code,
            "EDGE_DENOMINATOR_FORCED_POSITIVE_MESSAGE_PASSING",
        )


class EvaluationSummaryContractTests(unittest.TestCase):
    def test_valid_evaluation_summary_conserves_all_counts(self) -> None:
        summary = EvaluationSummary(
            requested_sample_count=10,
            request_validation_error_sample_count=1,
            accepted_request_sample_count=9,
            attempted_sample_count=7,
            sampling_system_failure_count=2,
            valid_generated_internal_count=5,
            invalid_generated_sample_count=2,
            exported_valid_complex_count=4,
            valid_export_failure_count=1,
            docking_evaluable_valid_sample_count=3,
            valid_but_not_docking_evaluable_sample_count=1,
            docking_not_run_valid_sample_count=1,
            docking_failed_valid_sample_count=1,
            successfully_docked_valid_sample_count=1,
        )

        receipt = validate_evaluation_summary(summary)

        self.assertTrue(receipt.passed)
        summary.validate()

    def test_evaluation_summary_rejects_sampling_failure_mismatch(self) -> None:
        summary = EvaluationSummary(
            requested_sample_count=10,
            request_validation_error_sample_count=1,
            accepted_request_sample_count=9,
            attempted_sample_count=8,
            sampling_system_failure_count=2,
            valid_generated_internal_count=6,
            invalid_generated_sample_count=2,
            exported_valid_complex_count=5,
            valid_export_failure_count=1,
            docking_evaluable_valid_sample_count=3,
            valid_but_not_docking_evaluable_sample_count=2,
            docking_not_run_valid_sample_count=1,
            docking_failed_valid_sample_count=1,
            successfully_docked_valid_sample_count=1,
        )

        receipt = validate_evaluation_summary(summary)

        self.assertFalse(receipt.passed)
        self.assertEqual(
            receipt.errors[0].code,
            "EVALUATION_DENOMINATOR_ACCEPTED_REQUEST_MISMATCH",
        )


if __name__ == "__main__":
    unittest.main()
