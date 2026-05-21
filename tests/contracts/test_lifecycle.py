import unittest

from covalent_design.contracts import (
    ArtifactRef,
    CovalentGenerationResult,
    EdgeValidityCheck,
    FAILURE_REASON_CODES,
    GenerationValidityStatus,
    ProteinAtomIdentity,
    validate_lifecycle,
)


def target_atom() -> ProteinAtomIdentity:
    return ProteinAtomIdentity(
        chain_id="A",
        residue_number=145,
        residue_name="CYS",
        atom_name="SG",
        altloc=None,
        insertion_code=None,
    )


def validity_check(status: str = "pass") -> EdgeValidityCheck:
    return EdgeValidityCheck(
        check_name="target_atom",
        status=status,
        observed_value="CYS:SG",
        threshold_or_rule="CYS_MICHAEL_ACCEPTOR",
        rule_table_version="fixture",
        failure_code=None,
    )


class LifecycleContractTests(unittest.TestCase):
    def test_lifecycle_enum_and_failure_codes_are_exported(self) -> None:
        self.assertEqual(GenerationValidityStatus, ("valid", "invalid"))
        self.assertIn("COMPLEX_EXPORT_FAILED", FAILURE_REASON_CODES)
        self.assertIn("DOCKING_RUN_FAILED", FAILURE_REASON_CODES)

    def test_invalid_generation_requires_not_applicable_downstream_statuses(self) -> None:
        result = CovalentGenerationResult(
            request_id="req-1",
            sample_id=0,
            residue_reaction_family="CYS_MICHAEL_ACCEPTOR",
            target_atom_identity=target_atom(),
            generation_validity_status="invalid",
            complex_export_status="not_applicable",
            docking_eligibility_status="not_applicable",
            docking_run_status="not_applicable",
            primary_failure_reason="NO_COVALENT_EDGE_PREDICTED",
            secondary_failure_reasons=(),
            edge_validity_checks=(validity_check("fail"),),
            artifacts={},
        )

        receipt = validate_lifecycle(result)

        self.assertTrue(receipt.passed)

    def test_invalid_generation_rejects_exported_complex_status(self) -> None:
        result = CovalentGenerationResult(
            request_id="req-1",
            sample_id=1,
            residue_reaction_family="CYS_MICHAEL_ACCEPTOR",
            target_atom_identity=target_atom(),
            generation_validity_status="invalid",
            complex_export_status="exported",
            docking_eligibility_status="not_applicable",
            docking_run_status="not_applicable",
            primary_failure_reason="NO_COVALENT_EDGE_PREDICTED",
            secondary_failure_reasons=(),
            edge_validity_checks=(validity_check("fail"),),
            artifacts={},
        )

        receipt = validate_lifecycle(result)

        self.assertFalse(receipt.passed)
        self.assertEqual(receipt.errors[0].code, "LIFECYCLE_INVALID_EXPORT_STATUS")

    def test_export_failure_requires_complex_export_failure_reason(self) -> None:
        result = CovalentGenerationResult(
            request_id="req-1",
            sample_id=2,
            residue_reaction_family="CYS_MICHAEL_ACCEPTOR",
            target_atom_identity=target_atom(),
            generation_validity_status="valid",
            complex_export_status="failed",
            docking_eligibility_status="not_applicable",
            docking_run_status="not_applicable",
            primary_failure_reason="LIGAND_CHEMISTRY_INVALID",
            secondary_failure_reasons=(),
            edge_validity_checks=(validity_check(),),
            artifacts={},
        )

        receipt = validate_lifecycle(result)

        self.assertFalse(receipt.passed)
        self.assertEqual(
            receipt.errors[0].code,
            "LIFECYCLE_EXPORT_FAILURE_REASON_MISMATCH",
        )

    def test_docking_success_requires_exported_artifact(self) -> None:
        result = CovalentGenerationResult(
            request_id="req-1",
            sample_id=3,
            residue_reaction_family="CYS_MICHAEL_ACCEPTOR",
            target_atom_identity=target_atom(),
            generation_validity_status="valid",
            complex_export_status="exported",
            docking_eligibility_status="eligible",
            docking_run_status="succeeded",
            primary_failure_reason=None,
            secondary_failure_reasons=(),
            edge_validity_checks=(validity_check(),),
            artifacts={
                "complex_mmcif": ArtifactRef(
                    uri="complexes/req-1-3.cif",
                    sha256="d" * 64,
                    format="mmcif",
                    schema_version="1",
                    role="complex_mmcif",
                )
            },
        )

        receipt = validate_lifecycle(result)

        self.assertTrue(receipt.passed)


if __name__ == "__main__":
    unittest.main()
