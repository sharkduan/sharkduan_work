import unittest
from dataclasses import replace

from covalent_design.contracts import (
    ArtifactRef,
    CovalentEdge,
    CovalentGenerationResult,
    EdgeValidityCheck,
    FAILURE_REASON_CODES,
    GenerationValidityStatus,
    GeometryMetrics,
    LigandAtomIdentity,
    MoleculeQuality,
    ProteinAtomIdentity,
    validate_generation_result,
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


def ligand_atom() -> LigandAtomIdentity:
    return LigandAtomIdentity(
        ligand_id="LIG",
        atom_name="C1",
        atom_index=4,
        chain_id="A",
        residue_number=301,
    )


def covalent_edge() -> CovalentEdge:
    return CovalentEdge(
        protein_atom=target_atom(),
        ligand_atom=ligand_atom(),
        bond_type="carbon-sulfur",
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


def exported_artifact() -> ArtifactRef:
    return ArtifactRef(
        uri="complexes/req-1-3.cif",
        sha256="d" * 64,
        format="mmcif",
        schema_version="1",
        role="complex_mmcif",
    )


def valid_generation_result(**overrides: object) -> CovalentGenerationResult:
    result = CovalentGenerationResult(
        request_id="req-1",
        sample_id=3,
        residue_reaction_family="CYS_MICHAEL_ACCEPTOR",
        target_atom_identity=target_atom(),
        generation_validity_status="valid",
        complex_export_status="exported",
        docking_eligibility_status="eligible",
        docking_run_status="not_run",
        primary_failure_reason=None,
        secondary_failure_reasons=(),
        generated_ligand_status="present",
        predicted_ligand_attachment_atom=ligand_atom(),
        predicted_covalent_edge=covalent_edge(),
        covalent_edge_score=0.93,
        geometry_metrics=GeometryMetrics(
            bond_length=1.82,
            protein_side_angle=108.0,
            ligand_side_angle=112.0,
        ),
        molecular_quality_metrics=MoleculeQuality(qed=0.6, molecular_weight=350.0),
        matched_warhead_type="michael_acceptor",
        predicted_warhead_type="michael_acceptor",
        covalent_docking_score=None,
        noncovalent_vina_score=-6.7,
        edge_validity_checks=(validity_check(),),
        artifacts={"complex_mmcif": exported_artifact()},
    )
    if not overrides:
        return result
    return replace(result, **overrides)


class LifecycleContractTests(unittest.TestCase):
    def test_lifecycle_enum_and_failure_codes_are_exported(self) -> None:
        self.assertEqual(GenerationValidityStatus, ("valid", "invalid"))
        self.assertIn("COMPLEX_EXPORT_FAILED", FAILURE_REASON_CODES)
        self.assertIn("DOCKING_RUN_FAILED", FAILURE_REASON_CODES)

    def test_generation_result_diagnostic_fields_have_safe_defaults(self) -> None:
        result = CovalentGenerationResult(
            request_id="req-legacy",
            sample_id=0,
            residue_reaction_family="CYS_MICHAEL_ACCEPTOR",
            target_atom_identity=target_atom(),
            generation_validity_status="invalid",
            complex_export_status="not_applicable",
            docking_eligibility_status="not_applicable",
            docking_run_status="not_applicable",
            primary_failure_reason="NO_COVALENT_EDGE_PREDICTED",
            secondary_failure_reasons=(),
        )

        self.assertEqual(result.generated_ligand_status, "absent")
        self.assertIsNone(result.predicted_ligand_attachment_atom)
        self.assertIsNone(result.predicted_covalent_edge)
        self.assertIsNone(result.covalent_docking_score)
        self.assertEqual(result.edge_validity_checks, ())

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

    def test_generation_result_validator_requires_valid_generation_diagnostics(self) -> None:
        result = valid_generation_result(predicted_covalent_edge=None)

        receipt = validate_generation_result(result)

        self.assertFalse(receipt.passed)
        self.assertEqual(
            receipt.errors[0].code,
            "GENERATION_RESULT_VALID_DIAGNOSTICS_MISSING",
        )

    def test_generation_result_validator_requires_covalent_score_on_docking_success(self) -> None:
        result = valid_generation_result(
            docking_run_status="succeeded",
            covalent_docking_score=None,
            noncovalent_vina_score=-7.1,
        )

        receipt = validate_generation_result(result)

        self.assertFalse(receipt.passed)
        self.assertEqual(
            receipt.errors[0].code,
            "GENERATION_RESULT_COVALENT_DOCKING_SCORE_MISSING",
        )

    def test_generation_result_validator_rejects_covalent_score_on_docking_failure(self) -> None:
        result = valid_generation_result(
            docking_run_status="failed",
            primary_failure_reason="DOCKING_RUN_FAILED",
            covalent_docking_score=-8.2,
        )

        receipt = validate_generation_result(result)

        self.assertFalse(receipt.passed)
        self.assertEqual(
            receipt.errors[0].code,
            "GENERATION_RESULT_COVALENT_DOCKING_SCORE_NOT_ALLOWED",
        )

    def test_generation_result_validator_keeps_noncovalent_score_separate(self) -> None:
        result = valid_generation_result(
            docking_run_status="not_run",
            covalent_docking_score=None,
            noncovalent_vina_score=-6.5,
        )

        receipt = validate_generation_result(result)

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
