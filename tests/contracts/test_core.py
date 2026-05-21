import unittest

from covalent_design.contracts import (
    ArtifactRef,
    CLI_EXIT_CODES,
    CONTRACT_VERSION,
    ContractEnvelope,
    ContractError,
    ContractErrorInfo,
    Provenance,
    QualitySeverity,
    REQUEST_VALIDATION_ERROR_CODES,
    ValidationReceipt,
    VisualCheckStatus,
    exit_code_for_error,
)


class CoreContractTests(unittest.TestCase):
    def test_artifact_ref_and_receipt_carry_contract_version_fields(self) -> None:
        artifact = ArtifactRef(
            uri="records.jsonl",
            sha256="a" * 64,
            format="jsonl",
            schema_version="1",
            role="record_index",
            bytes=123,
        )
        receipt = ValidationReceipt(
            validator="tests.contracts",
            contract_version=CONTRACT_VERSION,
            input_sha256="b" * 64,
            passed=True,
        )
        envelope = ContractEnvelope(
            payload={"records": 1},
            artifacts=(artifact,),
            receipt=receipt,
            provenance=Provenance(producer_name="covalent_design"),
        )

        self.assertEqual(artifact.schema_version, "1")
        self.assertEqual(artifact.bytes, 123)
        self.assertTrue(receipt.passed)
        self.assertTrue(receipt.ok)
        self.assertEqual(envelope.provenance.producer_name, "covalent_design")

    def test_validation_receipt_accepts_legacy_ok_keyword(self) -> None:
        receipt = ValidationReceipt(
            validator="tests.contracts",
            contract_version=CONTRACT_VERSION,
            input_sha256="c" * 64,
            ok=False,
            errors=(
                ContractErrorInfo(
                    code="TEST_ERROR",
                    owner="data",
                    message="fixture failure",
                ),
            ),
        )

        self.assertFalse(receipt.passed)
        self.assertFalse(receipt.ok)
        self.assertEqual(receipt.errors[0].code, "TEST_ERROR")

    def test_shared_enum_values_are_centralized(self) -> None:
        self.assertEqual(QualitySeverity, ("Q0", "Q1", "Q2"))
        self.assertIn("needs_rule_review", VisualCheckStatus)
        self.assertIn(
            "REQUEST_REQUIRED_CHEMICAL_STATE_UNAVAILABLE",
            REQUEST_VALIDATION_ERROR_CODES,
        )

    def test_contract_error_maps_to_documented_exit_codes(self) -> None:
        request_error = ContractError(
            code="REQUEST_SAMPLE_COUNT_INVALID",
            owner="request",
            message="bad sample count",
            details={"field": "sample_count"},
        )
        denominator_error = ContractError(
            code="EVALUATION_DENOMINATOR_MISMATCH",
            owner="evaluation",
            message="bad denominator equation",
        )

        self.assertEqual(CLI_EXIT_CODES["request_validation_failed"], 20)
        self.assertEqual(exit_code_for_error(request_error), 20)
        self.assertEqual(exit_code_for_error(denominator_error), 12)


if __name__ == "__main__":
    unittest.main()
