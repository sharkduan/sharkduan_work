"""Task 28 ResultWriter contract tests.

These tests define the public API and boundary contracts for
``ResultWriter.write()``.

Coverage:
1.  ResultWriter import, type guard, write valid/invalid results,
    JSON-compatible mapping, deterministic output, input non-mutation.
2.  Nested ProteinAtomIdentity, LigandAtomIdentity, CovalentEdge,
    GeometryMetrics, MoleculeQuality, EdgeValidityCheck, and ArtifactRef
    serialization.
3.  Tuple fields become lists; mapping keys deterministic.
4.  All valid diagnostic missing cases reject through structured ContractError.
5.  Invalid diagnostics and secondary reasons preserved.
6.  Unknown failure reason, lifecycle, ligand status, edge check name/status
    reject through ContractError.
7.  Docking succeeded requires covalent score; non-succeeded rejects covalent
    score; noncovalent score independently allowed.
8.  Task 27 integration with result_sink=writer.write.
9.  Source guards: no heavy dependencies.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

# ---------------------------------------------------------------------------
# contracts — always importable
# ---------------------------------------------------------------------------
from covalent_design.contracts.errors import ContractError
from covalent_design.contracts.types import (
    ArtifactRef,
    CovalentEdge,
    CovalentGenerationResult,
    EdgeValidityCheck,
    GeometryMetrics,
    LigandAtomIdentity,
    MoleculeQuality,
    ProteinAtomIdentity,
)

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "inference" / "result_writer"
FIXED_TIMESTAMP = "2026-06-02T00:00:00Z"


# ===================================================================
# Fixture loading helpers
# ===================================================================


def _load_json(name: str) -> dict[str, object]:
    path = FIXTURES / name
    if not path.is_file():
        raise FileNotFoundError(f"Fixture not found: {path}")
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)  # type: ignore[no-any-return]


def _decode_protein_atom_identity(d: dict[str, object]) -> ProteinAtomIdentity:
    return ProteinAtomIdentity(
        chain_id=_optional_str(d.get("chain_id")),
        residue_number=_optional_int(d.get("residue_number")),
        residue_name=str(d.get("residue_name", "")),
        atom_name=str(d.get("atom_name", "")),
        altloc=_optional_str(d.get("altloc")),
        insertion_code=_optional_str(d.get("insertion_code")),
        structure_model=_optional_int(d.get("structure_model")),
        asym_id=_optional_str(d.get("asym_id")),
        atom_serial=_optional_int(d.get("atom_serial")),
    )


def _decode_ligand_atom_identity(d: dict[str, object]) -> LigandAtomIdentity:
    return LigandAtomIdentity(
        ligand_id=str(d.get("ligand_id", "")),
        atom_name=str(d.get("atom_name", "")),
        atom_index=_optional_int(d.get("atom_index")),
        chain_id=_optional_str(d.get("chain_id")),
        asym_id=_optional_str(d.get("asym_id")),
        residue_number=_optional_int(d.get("residue_number")),
        altloc=_optional_str(d.get("altloc")),
    )


def _decode_covalent_edge(d: dict[str, object]) -> CovalentEdge:
    return CovalentEdge(
        protein_atom=_decode_protein_atom_identity(_require_dict(d, "protein_atom")),
        ligand_atom=_decode_ligand_atom_identity(_require_dict(d, "ligand_atom")),
        bond_type=_require_str(d, "bond_type"),
    )


def _decode_geometry_metrics(d: dict[str, object]) -> GeometryMetrics:
    return GeometryMetrics(
        bond_length=_optional_float(d.get("bond_length")),
        protein_side_angle=_optional_float(d.get("protein_side_angle")),
        ligand_side_angle=_optional_float(d.get("ligand_side_angle")),
    )


def _decode_molecule_quality(d: dict[str, object]) -> MoleculeQuality:
    return MoleculeQuality(
        qed=_optional_float(d.get("qed")),
        sa_score=_optional_float(d.get("sa_score")),
        log_p=_optional_float(d.get("log_p")),
        molecular_weight=_optional_float(d.get("molecular_weight")),
    )


def _decode_edge_validity_check(d: dict[str, object]) -> EdgeValidityCheck:
    return EdgeValidityCheck(
        check_name=_require_str(d, "check_name"),
        status=_require_str(d, "status"),
        observed_value=_require_str(d, "observed_value"),
        threshold_or_rule=_require_str(d, "threshold_or_rule"),
        rule_table_version=_require_str(d, "rule_table_version"),
        failure_code=_optional_str(d.get("failure_code")),
    )


def _decode_artifact_ref(d: dict[str, object]) -> ArtifactRef:
    return ArtifactRef(
        uri=_require_str(d, "uri"),
        sha256=_require_str(d, "sha256"),
        format=_require_str(d, "format"),
        schema_version=_require_str(d, "schema_version"),
        role=_require_str(d, "role"),
        bytes=int(d.get("bytes", 0)),
    )


def _decode_result(d: dict[str, object]) -> CovalentGenerationResult:
    return CovalentGenerationResult(
        request_id=_require_str(d, "request_id"),
        sample_id=_require_int(d, "sample_id"),
        residue_reaction_family=_require_str(d, "residue_reaction_family"),
        target_atom_identity=_decode_protein_atom_identity(
            _require_dict(d, "target_atom_identity")
        ),
        generation_validity_status=_require_str(d, "generation_validity_status"),
        complex_export_status=_require_str(d, "complex_export_status"),
        docking_eligibility_status=_require_str(d, "docking_eligibility_status"),
        docking_run_status=_require_str(d, "docking_run_status"),
        primary_failure_reason=_optional_str(d.get("primary_failure_reason")),
        secondary_failure_reasons=tuple(
            str(r) for r in _require_list(d, "secondary_failure_reasons")
        ),
        generated_ligand_status=_require_str(d, "generated_ligand_status"),
        predicted_ligand_attachment_atom=(
            _decode_ligand_atom_identity(_require_dict(d, "predicted_ligand_attachment_atom"))
            if d.get("predicted_ligand_attachment_atom") is not None
            else None
        ),
        predicted_covalent_edge=(
            _decode_covalent_edge(_require_dict(d, "predicted_covalent_edge"))
            if d.get("predicted_covalent_edge") is not None
            else None
        ),
        covalent_edge_score=_optional_float(d.get("covalent_edge_score")),
        geometry_metrics=(
            _decode_geometry_metrics(_require_dict(d, "geometry_metrics"))
            if d.get("geometry_metrics") is not None
            else None
        ),
        molecular_quality_metrics=(
            _decode_molecule_quality(_require_dict(d, "molecular_quality_metrics"))
            if d.get("molecular_quality_metrics") is not None
            else None
        ),
        matched_warhead_type=_optional_str(d.get("matched_warhead_type")),
        predicted_warhead_type=_optional_str(d.get("predicted_warhead_type")),
        covalent_docking_score=_optional_float(d.get("covalent_docking_score")),
        noncovalent_vina_score=_optional_float(d.get("noncovalent_vina_score")),
        edge_validity_checks=tuple(
            _decode_edge_validity_check(c)
            for c in _require_list(d, "edge_validity_checks")
        ),
        artifacts={
            str(k): _decode_artifact_ref(v)
            for k, v in _require_dict(d, "artifacts").items()
        },
    )


# -- primitive helpers --


def _require_str(d: dict[str, object], key: str) -> str:
    v = d[key]
    if not isinstance(v, str):
        raise TypeError(f"{key} must be str, got {type(v).__name__}")
    return v


def _require_int(d: dict[str, object], key: str) -> int:
    v = d[key]
    if isinstance(v, bool) or not isinstance(v, int):
        raise TypeError(f"{key} must be int, got {type(v).__name__}")
    return v


def _require_dict(d: dict[str, object], key: str) -> dict[str, object]:
    v = d[key]
    if not isinstance(v, dict):
        raise TypeError(f"{key} must be dict, got {type(v).__name__}")
    return v  # type: ignore[return-value]


def _require_list(d: dict[str, object], key: str) -> list[object]:
    v = d[key]
    if not isinstance(v, list):
        raise TypeError(f"{key} must be list, got {type(v).__name__}")
    return v  # type: ignore[return-value]


def _optional_str(v: object) -> str | None:
    if v is None:
        return None
    return str(v)


def _optional_int(v: object) -> int | None:
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return int(v)
    return None


def _optional_float(v: object) -> float | None:
    if v is None:
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    return None


# ===================================================================
# 1.  ResultWriter API contract (RED)
# ===================================================================


class ResultWriterAPITests(unittest.TestCase):
    """ResultWriter import, type guard, and signature tests.

    The writer rejects values outside the generation-result contract.
    """

    def test_result_writer_is_importable(self) -> None:
        """ResultWriter must be importable from covalent_design.inference.result_writer."""
        from covalent_design.inference.result_writer import ResultWriter  # noqa: F811

    def test_result_writer_instantiates_without_args(self) -> None:
        """ResultWriter() must construct with no arguments."""
        from covalent_design.inference.result_writer import ResultWriter

        writer = ResultWriter()
        self.assertIsNotNone(writer)

    def test_result_writer_has_callable_write_method(self) -> None:
        """ResultWriter must expose a callable write method."""
        from covalent_design.inference.result_writer import ResultWriter

        writer = ResultWriter()
        self.assertTrue(callable(getattr(writer, "write", None)))

    def test_write_accepts_covalent_generation_result(self) -> None:
        """write() must accept a CovalentGenerationResult and return dict[str, object]."""
        from covalent_design.inference.result_writer import ResultWriter

        result = _decode_result(_load_json("valid_exported_result.json"))
        writer = ResultWriter()
        row = writer.write(result)
        self.assertIsInstance(row, dict)

    def test_write_rejects_non_generation_result(self) -> None:
        """write() must reject values outside the CovalentGenerationResult contract."""
        from covalent_design.inference.result_writer import ResultWriter

        with self.assertRaises(TypeError):
            ResultWriter().write({"request_id": "not-a-result"})

    def test_write_returns_json_compatible_types(self) -> None:
        """write() output must be JSON-serializable."""
        from covalent_design.inference.result_writer import ResultWriter

        result = _decode_result(_load_json("valid_exported_result.json"))
        writer = ResultWriter()
        row = writer.write(result)
        serialized = json.dumps(row, sort_keys=True)
        self.assertIsInstance(serialized, str)
        round_tripped = json.loads(serialized)
        self.assertEqual(round_tripped, row)

    def test_writer_instance_is_reusable(self) -> None:
        """A single ResultWriter instance must be reusable across multiple write calls."""
        from covalent_design.inference.result_writer import ResultWriter

        r1 = _decode_result(_load_json("valid_exported_result.json"))
        r2 = _decode_result(_load_json("valid_docking_not_run_result.json"))
        writer = ResultWriter()
        row1 = writer.write(r1)
        row2 = writer.write(r2)
        self.assertIsInstance(row1, dict)
        self.assertIsInstance(row2, dict)
        self.assertNotEqual(row1["sample_id"], row2["sample_id"])


# ===================================================================
# 2.  Valid result write tests
# ===================================================================


class ResultWriterValidWriteTests(unittest.TestCase):
    """Write tests for valid CovalentGenerationResult fixtures.

    Valid results must serialize without losing lifecycle diagnostics.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls._fixtures: dict[str, CovalentGenerationResult] = {}

    def _writer(self):
        from covalent_design.inference.result_writer import ResultWriter
        return ResultWriter()

    def _get_result(self, name: str) -> CovalentGenerationResult:
        if name not in self._fixtures:
            self._fixtures[name] = _decode_result(_load_json(name))
        return self._fixtures[name]

    def test_write_valid_exported_docking_succeeded_result(self) -> None:
        """Valid exported docking-succeeded result must produce a complete row."""
        result = self._get_result("valid_exported_result.json")
        row = self._writer().write(result)
        self.assertEqual(row["request_id"], "task28-valid-exported")
        self.assertEqual(row["sample_id"], 0)
        self.assertEqual(row["generation_validity_status"], "valid")
        self.assertEqual(row["complex_export_status"], "exported")
        self.assertEqual(row["docking_run_status"], "succeeded")
        self.assertEqual(row["covalent_docking_score"], -8.5)
        self.assertIn("ligand_sdf", row["artifacts"])
        self.assertIn("complex_mmcif", row["artifacts"])
        self.assertIn("complex_pdb", row["artifacts"])

    def test_write_valid_docking_not_run_result(self) -> None:
        """Valid docking-not-run result must produce a row with null covalent score."""
        result = self._get_result("valid_docking_not_run_result.json")
        row = self._writer().write(result)
        self.assertEqual(row["request_id"], "task28-valid-docking-not-run")
        self.assertEqual(row["docking_run_status"], "not_run")
        self.assertIsNone(row["covalent_docking_score"])
        self.assertIsNotNone(row["noncovalent_vina_score"])

    def test_write_valid_docking_succeeded_with_null_non_covalent(self) -> None:
        """Noncovalent score may be null independently of covalent score presence."""
        result = self._get_result("valid_docking_succeeded_result.json")
        row = self._writer().write(result)
        self.assertEqual(row["docking_run_status"], "succeeded")
        self.assertEqual(row["covalent_docking_score"], -9.2)
        self.assertIsNone(row["noncovalent_vina_score"])

    def test_write_valid_export_failure_result(self) -> None:
        """Valid export-failure result must preserve failure reason."""
        result = self._get_result("valid_export_failure_result.json")
        row = self._writer().write(result)
        self.assertEqual(row["generation_validity_status"], "valid")
        self.assertEqual(row["complex_export_status"], "failed")
        self.assertEqual(row["primary_failure_reason"], "COMPLEX_EXPORT_FAILED")
        self.assertEqual(row["docking_run_status"], "not_applicable")
        self.assertIsNone(row["covalent_docking_score"])


# ===================================================================
# 3.  Invalid result write tests
# ===================================================================


class ResultWriterInvalidWriteTests(unittest.TestCase):
    """Write tests for invalid CovalentGenerationResult fixtures.

    Invalid results must still be writable — the writer serializes, not
    gatekeeps validity.  The primary_failure_reason and secondary_reasons
    must be preserved exactly.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls._fixtures: dict[str, CovalentGenerationResult] = {}

    def _writer(self):
        from covalent_design.inference.result_writer import ResultWriter
        return ResultWriter()

    def _get_result(self, name: str) -> CovalentGenerationResult:
        if name not in self._fixtures:
            self._fixtures[name] = _decode_result(_load_json(name))
        return self._fixtures[name]

    def test_write_invalid_no_edge_result(self) -> None:
        result = self._get_result("invalid_no_edge_result.json")
        row = self._writer().write(result)
        self.assertEqual(row["generation_validity_status"], "invalid")
        self.assertEqual(row["primary_failure_reason"], "NO_COVALENT_EDGE_PREDICTED")
        self.assertEqual(row["generated_ligand_status"], "absent")
        self.assertIsNone(row["predicted_covalent_edge"])

    def test_write_invalid_below_threshold_result(self) -> None:
        result = self._get_result("invalid_below_threshold_result.json")
        row = self._writer().write(result)
        self.assertEqual(row["primary_failure_reason"], "COVALENT_EDGE_BELOW_THRESHOLD")
        self.assertLess(row["covalent_edge_score"], 0.5)

    def test_write_invalid_rule_failure_result(self) -> None:
        result = self._get_result("invalid_rule_failure_result.json")
        row = self._writer().write(result)
        self.assertEqual(row["primary_failure_reason"], "REACTION_FAMILY_RULE_FAIL")
        self.assertEqual(row["secondary_failure_reasons"], ["WARHEAD_MATCH_FAIL"])

    def test_write_invalid_warhead_match_failure_result(self) -> None:
        result = self._get_result("invalid_warhead_match_failure_result.json")
        row = self._writer().write(result)
        self.assertEqual(row["primary_failure_reason"], "WARHEAD_MATCH_FAIL")
        self.assertEqual(row["secondary_failure_reasons"], ["VALENCE_CHECK_FAIL"])

    def test_write_invalid_valence_failure_result(self) -> None:
        result = self._get_result("invalid_valence_failure_result.json")
        row = self._writer().write(result)
        self.assertEqual(row["primary_failure_reason"], "VALENCE_CHECK_FAIL")

    def test_write_invalid_geometry_failure_result(self) -> None:
        result = self._get_result("invalid_geometry_failure_result.json")
        row = self._writer().write(result)
        self.assertEqual(row["primary_failure_reason"], "GEOMETRY_CHECK_FAIL")
        self.assertEqual(row["secondary_failure_reasons"], ["VALENCE_CHECK_FAIL"])

    def test_write_invalid_required_state_unavailable_result(self) -> None:
        result = self._get_result("invalid_required_state_unavailable_result.json")
        row = self._writer().write(result)
        self.assertEqual(
            row["primary_failure_reason"], "REQUIRED_GATE_STATE_UNAVAILABLE"
        )
        self.assertEqual(len(row["edge_validity_checks"]), 1)
        self.assertEqual(
            row["edge_validity_checks"][0]["status"], "not_evaluable"
        )

    def test_write_invalid_with_parseable_ligand_diagnostics(self) -> None:
        """Invalid result with parseable ligand must preserve all diagnostics."""
        result = self._get_result(
            "invalid_with_parseable_ligand_diagnostics.json"
        )
        row = self._writer().write(result)
        self.assertEqual(row["primary_failure_reason"], "LIGAND_CHEMISTRY_INVALID")
        self.assertEqual(
            row["secondary_failure_reasons"],
            ["WARHEAD_MATCH_FAIL", "VALENCE_CHECK_FAIL"],
        )
        self.assertEqual(row["generated_ligand_status"], "present")
        self.assertIsNotNone(row["predicted_ligand_attachment_atom"])
        self.assertIsNotNone(row["predicted_covalent_edge"])
        self.assertIsNotNone(row["covalent_edge_score"])
        self.assertIsNotNone(row["geometry_metrics"])
        self.assertIsNotNone(row["molecular_quality_metrics"])
        self.assertEqual(len(row["edge_validity_checks"]), 3)
        self.assertIn("ligand_sdf", row["artifacts"])


# ===================================================================
# 4.  Contract rejection tests (corrupt fixtures)
# ===================================================================


class ResultWriterContractRejectionTests(unittest.TestCase):
    """Corrupt fixtures must raise structured ContractError from validate_generation_result.

    These are expected to be GREEN-once-implemented.  Until the writer exists,
    the import inside test methods will fail with ImportError — acceptable RED.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls._fixtures: dict[str, CovalentGenerationResult] = {}

    def _writer(self):
        from covalent_design.inference.result_writer import ResultWriter
        return ResultWriter()

    def _get_result(self, name: str) -> CovalentGenerationResult:
        if name not in self._fixtures:
            self._fixtures[name] = _decode_result(_load_json(name))
        return self._fixtures[name]

    def _assert_contract_error(
        self, name: str, expected_code: str, expected_owner: str = "evaluation",
    ) -> None:
        result = self._get_result(name)
        with self.assertRaises(ContractError) as ctx:
            self._writer().write(result)
        err = ctx.exception
        self.assertEqual(err.code, expected_code, f"code mismatch in {name}")
        self.assertEqual(err.owner, expected_owner, f"owner mismatch in {name}")
        self.assertIsNotNone(err.message, f"message missing in {name}")

    # -- invalid lifecycle corruptions --

    def test_corrupt_invalid_missing_primary_reason_rejected(self) -> None:
        self._assert_contract_error(
            "corrupt_invalid_missing_primary_reason.json",
            "LIFECYCLE_INVALID_MISSING_FAILURE_REASON",
        )

    def test_corrupt_invalid_exported_status_rejected(self) -> None:
        self._assert_contract_error(
            "corrupt_invalid_exported_status.json",
            "LIFECYCLE_INVALID_EXPORT_STATUS",
        )

    # -- valid diagnostic missing corruptions --

    def test_corrupt_valid_missing_attachment_atom_rejected(self) -> None:
        self._assert_contract_error(
            "corrupt_valid_missing_attachment_atom.json",
            "GENERATION_RESULT_VALID_DIAGNOSTICS_MISSING",
        )

    def test_corrupt_valid_missing_predicted_edge_rejected(self) -> None:
        self._assert_contract_error(
            "corrupt_valid_missing_predicted_edge.json",
            "GENERATION_RESULT_VALID_DIAGNOSTICS_MISSING",
        )

    def test_corrupt_valid_missing_geometry_rejected(self) -> None:
        self._assert_contract_error(
            "corrupt_valid_missing_geometry.json",
            "GENERATION_RESULT_VALID_DIAGNOSTICS_MISSING",
        )

    def test_corrupt_valid_missing_matched_warhead_rejected(self) -> None:
        self._assert_contract_error(
            "corrupt_valid_missing_matched_warhead.json",
            "GENERATION_RESULT_VALID_DIAGNOSTICS_MISSING",
        )

    # -- docking score corruptions --

    def test_corrupt_docking_success_missing_score_rejected(self) -> None:
        self._assert_contract_error(
            "corrupt_docking_success_missing_score.json",
            "GENERATION_RESULT_COVALENT_DOCKING_SCORE_MISSING",
        )

    def test_corrupt_docking_failure_with_covalent_score_rejected(self) -> None:
        self._assert_contract_error(
            "corrupt_docking_failure_with_covalent_score.json",
            "GENERATION_RESULT_COVALENT_DOCKING_SCORE_NOT_ALLOWED",
        )

    # -- unknown value corruptions --

    def test_corrupt_unknown_failure_reason_rejected(self) -> None:
        self._assert_contract_error(
            "corrupt_unknown_failure_reason.json",
            "FAILURE_REASON_CODE_INVALID",
        )

    def test_corrupt_unknown_edge_check_name_rejected(self) -> None:
        self._assert_contract_error(
            "corrupt_unknown_edge_check_name.json",
            "EDGE_VALIDITY_CHECK_NAME_INVALID",
        )

    def test_corrupt_unknown_edge_check_status_rejected(self) -> None:
        self._assert_contract_error(
            "corrupt_unknown_edge_check_status.json",
            "EDGE_VALIDITY_CHECK_STATUS_INVALID",
        )

    # -- error detail propagation --

    def test_missing_diagnostics_includes_missing_fields_in_details(self) -> None:
        """ContractError details must enumerate missing_fields for missing diagnostics."""
        result = self._get_result("corrupt_valid_missing_attachment_atom.json")
        with self.assertRaises(ContractError) as ctx:
            self._writer().write(result)
        err = ctx.exception
        self.assertIn("missing_fields", err.details)
        missing = err.details["missing_fields"]
        self.assertIn("predicted_ligand_attachment_atom", missing)

    def test_corrupt_error_preserves_location(self) -> None:
        """ContractError must carry a location field pinpointing the violation."""
        result = self._get_result("corrupt_invalid_missing_primary_reason.json")
        with self.assertRaises(ContractError) as ctx:
            self._writer().write(result)
        err = ctx.exception
        self.assertEqual(err.location, "primary_failure_reason")


# ===================================================================
# 5.  Serialization format and determinism tests
# ===================================================================


class ResultWriterSerializationTests(unittest.TestCase):
    """Output format, determinism, and non-mutation tests."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._fixtures: dict[str, CovalentGenerationResult] = {}

    def _writer(self):
        from covalent_design.inference.result_writer import ResultWriter
        return ResultWriter()

    def _get_result(self, name: str) -> CovalentGenerationResult:
        if name not in self._fixtures:
            self._fixtures[name] = _decode_result(_load_json(name))
        return self._fixtures[name]

    # -- tuple-to-list --

    def test_secondary_failure_reasons_serialized_as_list(self) -> None:
        result = self._get_result("invalid_rule_failure_result.json")
        row = self._writer().write(result)
        self.assertIsInstance(row["secondary_failure_reasons"], list)
        self.assertNotIsInstance(row["secondary_failure_reasons"], tuple)

    def test_edge_validity_checks_serialized_as_list(self) -> None:
        result = self._get_result("valid_exported_result.json")
        row = self._writer().write(result)
        self.assertIsInstance(row["edge_validity_checks"], list)
        self.assertNotIsInstance(row["edge_validity_checks"], tuple)

    # -- nested type serialization --

    def test_target_atom_identity_serialized_as_dict(self) -> None:
        result = self._get_result("valid_exported_result.json")
        row = self._writer().write(result)
        self.assertIsInstance(row["target_atom_identity"], dict)
        self.assertEqual(row["target_atom_identity"]["chain_id"], "A")
        self.assertEqual(row["target_atom_identity"]["residue_number"], 145)
        self.assertEqual(row["target_atom_identity"]["residue_name"], "CYS")
        self.assertEqual(row["target_atom_identity"]["atom_name"], "SG")
        self.assertEqual(row["target_atom_identity"]["atom_serial"], 1234)

    def test_predicted_ligand_attachment_atom_serialized_as_dict(self) -> None:
        result = self._get_result("valid_exported_result.json")
        row = self._writer().write(result)
        attach = row["predicted_ligand_attachment_atom"]
        self.assertIsInstance(attach, dict)
        self.assertEqual(attach["ligand_id"], "LIG001")
        self.assertEqual(attach["atom_name"], "C1")
        self.assertEqual(attach["atom_index"], 0)

    def test_predicted_covalent_edge_serialized_with_nested_atoms(self) -> None:
        result = self._get_result("valid_exported_result.json")
        row = self._writer().write(result)
        edge = row["predicted_covalent_edge"]
        self.assertIsInstance(edge, dict)
        self.assertIn("protein_atom", edge)
        self.assertIn("ligand_atom", edge)
        self.assertEqual(edge["bond_type"], "carbon-sulfur")
        self.assertEqual(edge["protein_atom"]["atom_name"], "SG")
        self.assertEqual(edge["ligand_atom"]["atom_name"], "C1")

    def test_geometry_metrics_serialized_as_dict(self) -> None:
        result = self._get_result("valid_exported_result.json")
        row = self._writer().write(result)
        gm = row["geometry_metrics"]
        self.assertIsInstance(gm, dict)
        self.assertAlmostEqual(gm["bond_length"], 1.82)
        self.assertAlmostEqual(gm["protein_side_angle"], 109.5)
        self.assertAlmostEqual(gm["ligand_side_angle"], 120.0)

    def test_molecular_quality_metrics_serialized_as_dict(self) -> None:
        result = self._get_result("valid_exported_result.json")
        row = self._writer().write(result)
        mq = row["molecular_quality_metrics"]
        self.assertIsInstance(mq, dict)
        self.assertAlmostEqual(mq["qed"], 0.72)
        self.assertAlmostEqual(mq["sa_score"], 3.1)
        self.assertAlmostEqual(mq["log_p"], 2.5)
        self.assertAlmostEqual(mq["molecular_weight"], 350.0)

    def test_edge_validity_check_serialized_as_dict(self) -> None:
        result = self._get_result("valid_exported_result.json")
        row = self._writer().write(result)
        check = row["edge_validity_checks"][0]
        self.assertIsInstance(check, dict)
        self.assertEqual(check["check_name"], "target_atom")
        self.assertEqual(check["status"], "pass")
        self.assertEqual(check["observed_value"], "SG")

    def test_artifact_ref_serialized_as_dict(self) -> None:
        result = self._get_result("valid_exported_result.json")
        row = self._writer().write(result)
        aref = row["artifacts"]["ligand_sdf"]
        self.assertIsInstance(aref, dict)
        self.assertEqual(aref["role"], "ligand_sdf")
        self.assertEqual(aref["format"], "sdf")
        self.assertIsInstance(aref["bytes"], int)

    # -- stable artifact key ordering --

    def test_artifacts_keys_are_deterministic(self) -> None:
        """Multiple artifact keys must have stable serialization order."""
        result = self._get_result("valid_exported_result.json")
        self.assertGreaterEqual(
            len(result.artifacts), 3,
            "fixture must have at least 3 artifact keys for ordering test",
        )
        rows = [self._writer().write(result) for _ in range(5)]
        key_orders = [list(r["artifacts"].keys()) for r in rows]
        first = key_orders[0]
        for keys in key_orders[1:]:
            self.assertEqual(keys, first)

    # -- deterministic output --

    def test_write_deterministic_for_same_input(self) -> None:
        result = self._get_result("valid_exported_result.json")
        writer = self._writer()
        row1 = writer.write(result)
        row2 = writer.write(result)
        self.assertEqual(row1, row2)

    def test_write_deterministic_across_writer_instances(self) -> None:
        result = self._get_result("valid_exported_result.json")
        row1 = self._writer().write(result)
        row2 = self._writer().write(result)
        self.assertEqual(row1, row2)

    # -- input non-mutation --

    def test_write_does_not_mutate_input_dataclass(self) -> None:
        result = self._get_result("valid_exported_result.json")
        original = deepcopy(
            {
                "sample_id": result.sample_id,
                "request_id": result.request_id,
                "covalent_edge_score": result.covalent_edge_score,
                "primary_failure_reason": result.primary_failure_reason,
                "secondary_failure_reasons": result.secondary_failure_reasons,
                "edge_validity_checks": result.edge_validity_checks,
                "artifacts_keys": tuple(result.artifacts.keys()),
            }
        )
        self._writer().write(result)
        self.assertEqual(result.request_id, original["request_id"])
        self.assertEqual(result.sample_id, original["sample_id"])
        self.assertEqual(result.covalent_edge_score, original["covalent_edge_score"])
        self.assertEqual(result.primary_failure_reason, original["primary_failure_reason"])
        self.assertEqual(result.secondary_failure_reasons, original["secondary_failure_reasons"])
        self.assertEqual(result.edge_validity_checks, original["edge_validity_checks"])
        self.assertEqual(tuple(result.artifacts.keys()), original["artifacts_keys"])

    # -- JSON-compatible mapping --

    def test_all_fields_present_in_serialized_row(self) -> None:
        """Every CovalentGenerationResult field must have a corresponding key in output."""
        result = self._get_result("valid_exported_result.json")
        row = self._writer().write(result)
        expected_fields = {
            "request_id", "sample_id", "residue_reaction_family",
            "target_atom_identity", "generation_validity_status",
            "complex_export_status", "docking_eligibility_status",
            "docking_run_status", "primary_failure_reason",
            "secondary_failure_reasons", "generated_ligand_status",
            "predicted_ligand_attachment_atom", "predicted_covalent_edge",
            "covalent_edge_score", "geometry_metrics",
            "molecular_quality_metrics", "matched_warhead_type",
            "predicted_warhead_type", "covalent_docking_score",
            "noncovalent_vina_score", "edge_validity_checks", "artifacts",
        }
        self.assertEqual(set(row.keys()), expected_fields)

    def test_null_optional_fields_serialized_as_none(self) -> None:
        """Optional fields with None value must be serialized as JSON null."""
        result = self._get_result("valid_docking_not_run_result.json")
        row = self._writer().write(result)
        self.assertIsNone(row["covalent_docking_score"])
        self.assertIsNone(row["primary_failure_reason"])

    # -- schema_version / contract_version absent from writer output --

    def test_writer_output_excludes_schema_version(self) -> None:
        """writer.write() must NOT inject schema_version (Task 27 does that)."""
        result = self._get_result("valid_exported_result.json")
        row = self._writer().write(result)
        self.assertNotIn("schema_version", row)

    def test_writer_output_excludes_contract_version(self) -> None:
        """writer.write() must NOT inject contract_version (Task 27 does that)."""
        result = self._get_result("valid_exported_result.json")
        row = self._writer().write(result)
        self.assertNotIn("contract_version", row)


# ===================================================================
# 6.  Integration tests with Task 27 generate()
# ===================================================================


class _ResultSampler:
    """Fake sampler that returns CovalentGenerationResult instances."""

    def __init__(self, results_by_sample_id, default_factory):
        self._results = {k: list(v) for k, v in (results_by_sample_id or {}).items()}
        self._factory = default_factory
        self.calls: list[int] = []

    def sample_one(self, request, checkpoint, sample_id):
        from covalent_design.inference.sampler import SamplingFailureSignal

        self.calls.append(sample_id)
        outcomes = self._results.get(sample_id, [])
        if not outcomes:
            return self._factory(request.request.request_id, sample_id)
        outcome = outcomes.pop(0)
        if isinstance(outcome, str):
            raise SamplingFailureSignal(
                failure_category=outcome,
                message=f"{outcome} for sample {sample_id}",
                log_uri=f"logs/{outcome}-{sample_id}.log",
                resource_snapshot=None,
                traceback_text=f"Traceback: {outcome} sample={sample_id}",
            )
        return outcome


REQUEST_FIXTURES = ROOT / "tests" / "fixtures" / "inference" / "request_validation"


class ResultWriterIntegrationTests(unittest.TestCase):
    """Integration tests with Task 27 generate(..., result_sink=writer.write)."""

    @staticmethod
    def _make_result(request_id: str, sample_id: int) -> CovalentGenerationResult:
        d = _load_json("valid_exported_result.json")
        d2 = dict(d)
        d2["request_id"] = request_id
        d2["sample_id"] = sample_id
        return _decode_result(d2)

    @staticmethod
    def _make_docking_not_run_result(request_id: str, sample_id: int) -> CovalentGenerationResult:
        d = _load_json("valid_docking_not_run_result.json")
        d2 = dict(d)
        d2["request_id"] = request_id
        d2["sample_id"] = sample_id
        return _decode_result(d2)

    @classmethod
    def setUpClass(cls) -> None:
        from covalent_design.inference.request_schema import (
            ProteinAtomLocator,
            ProteinChemicalStateRequest,
            ReactiveSiteGenerationRequest,
        )
        from covalent_design.rules.validate import load_rule_table
        from covalent_design.inference.request_validation import validate_request

        cls._raw_request = ReactiveSiteGenerationRequest(
            request_id="task28-integration",
            protein_structure_uri=str(
                REQUEST_FIXTURES / "structures" / "valid_structure.pdb"
            ),
            protein_structure_format="pdb",
            target_atom_identity_request=ProteinAtomLocator(
                chain_id="A",
                residue_number=42,
                residue_name="CYS",
                atom_name="SG",
            ),
            residue_reaction_family="CYS_MICHAEL_ADDITION",
            sample_count=3,
            protein_chemical_state_request=ProteinChemicalStateRequest(
                target_atom_formal_charge=0,
                target_atom_protonation_state="thiolate",
                target_atom_hydrogen_state="absent",
            ),
        )
        rules = load_rule_table(REQUEST_FIXTURES / "task26_local_rule.yml")
        cls._validated = validate_request(cls._raw_request, rules)

    def _policy(self, max_retries: int = 0, retry_on: tuple[str, ...] = ()):
        from covalent_design.inference.run_manifest import SamplingPolicy

        return SamplingPolicy(max_retries=max_retries, retry_on_categories=retry_on)

    def _generate(self, output_dir: Path, sampler, *, policy=None):
        from covalent_design.inference.run_manifest import generate
        from covalent_design.inference.result_writer import ResultWriter

        writer = ResultWriter()
        return generate(
            self._validated,
            policy if policy is not None else self._policy(),
            output_dir=output_dir,
            job_id="task28-integration-job",
            sampler=sampler,
            result_sink=writer.write,
            clock=lambda: FIXED_TIMESTAMP,
        )

    def test_all_success_integration(self) -> None:
        """All-success generate() with writer.write sink must produce correct rows."""
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            sampler = _ResultSampler(
                results_by_sample_id={},
                default_factory=self._make_result,
            )
            envelope = self._generate(out, sampler)
            manifest = envelope.payload

            self.assertEqual(manifest.accepted_request_sample_count, 3)
            self.assertEqual(manifest.attempted_sample_count, 3)
            self.assertEqual(manifest.sampling_system_failure_count, 0)
            self.assertEqual(manifest.result_count, 3)
            self.assertEqual(sampler.calls, [0, 1, 2])

            # Read results.jsonl
            from covalent_design.io.jsonl import read_jsonl

            rows = read_jsonl(out / "results.jsonl")
            self.assertEqual(len(rows), 3)
            for i, row in enumerate(rows):
                self.assertEqual(row["sample_id"], i)
                self.assertEqual(row["request_id"], "task28-integration")
                self.assertEqual(row["generation_validity_status"], "valid")

    def test_rows_contain_schema_version_and_contract_version(self) -> None:
        """Task 27 write_jsonl must inject schema_version and contract_version per row."""
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            sampler = _ResultSampler(
                results_by_sample_id={},
                default_factory=self._make_result,
            )
            self._generate(out, sampler)

            from covalent_design.io.jsonl import read_jsonl

            rows = read_jsonl(out / "results.jsonl")
            for row in rows:
                self.assertIn("schema_version", row)
                self.assertIn("contract_version", row)
                self.assertEqual(row["schema_version"], "1")

    def test_mixed_system_failure_integration(self) -> None:
        """Mixed success/failure: system failures do not produce result rows."""
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            # sample_id 1 fails with timeout (system failure)
            sampler = _ResultSampler(
                results_by_sample_id={1: ["timeout"]},
                default_factory=self._make_docking_not_run_result,
            )
            envelope = self._generate(out, sampler)
            manifest = envelope.payload

            self.assertEqual(manifest.accepted_request_sample_count, 3)
            self.assertEqual(manifest.attempted_sample_count, 2)
            self.assertEqual(manifest.sampling_system_failure_count, 1)
            self.assertEqual(manifest.result_count, 2)

            from covalent_design.io.jsonl import read_jsonl

            rows = read_jsonl(out / "results.jsonl")
            self.assertEqual(len(rows), 2)
            sample_ids = [row["sample_id"] for row in rows]
            self.assertIn(0, sample_ids)
            self.assertIn(2, sample_ids)
            self.assertNotIn(1, sample_ids)

    def test_result_count_equals_actual_jsonl_rows(self) -> None:
        """manifest.result_count must equal the number of lines in results.jsonl."""
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            sampler = _ResultSampler(
                results_by_sample_id={0: ["oom"], 2: ["crash"]},
                default_factory=self._make_result,
            )
            envelope = self._generate(out, sampler)
            manifest = envelope.payload

            from covalent_design.io.jsonl import read_jsonl

            rows = read_jsonl(out / "results.jsonl")
            self.assertEqual(manifest.result_count, len(rows))
            self.assertEqual(len(rows), 1)  # only sample 1 succeeded

    def test_attempted_samples_one_row_each(self) -> None:
        """Every attempted (non-failure) sample must write exactly one row."""
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            sampler = _ResultSampler(
                results_by_sample_id={},
                default_factory=self._make_result,
            )
            envelope = self._generate(out, sampler)

            from covalent_design.io.jsonl import read_jsonl

            rows = read_jsonl(out / "results.jsonl")
            # Each sample produces exactly one row, no duplicates
            sample_ids = [row["sample_id"] for row in rows]
            self.assertEqual(sorted(sample_ids), [0, 1, 2])

    def test_request_validation_failure_does_not_produce_rows(self) -> None:
        """If request validation fails, no results.jsonl or empty rows must be produced.

        Task 27 validate_request_file rejects malformed requests before
        generate() runs.  This test verifies that the request-level validation
        failure path never reaches result_sink.
        """
        from covalent_design.inference.request_validation import validate_request_file

        try:
            validated = validate_request_file(
                REQUEST_FIXTURES / "malformed_request.yml",
                rules_path=REQUEST_FIXTURES / "task26_local_rule.yml",
            )
        except Exception:
            # Request validation failure — no generate() call, no rows.
            # This is the expected path; the test confirms no results are produced.
            return
        # If validation unexpectedly passed (should not happen with malformed request),
        # verify no rows are produced.
        self.fail(
            "malformed_request.yml unexpectedly passed request validation"
        )

    def test_corrupt_sampler_result_propagates_contract_error(self) -> None:
        """Contract-corrupt sampler output is fatal, not a sampling-system failure."""
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            data = dict(_load_json("corrupt_valid_missing_predicted_edge.json"))
            data["request_id"] = "task28-integration"
            data["sample_id"] = 0
            sampler = _ResultSampler(
                results_by_sample_id={0: [_decode_result(data)]},
                default_factory=self._make_result,
            )

            with self.assertRaises(ContractError) as ctx:
                self._generate(out, sampler)

            self.assertEqual(
                ctx.exception.code, "GENERATION_RESULT_VALID_DIAGNOSTICS_MISSING"
            )
            self.assertFalse((out / "results.jsonl").exists())
            self.assertFalse((out / "sampling_system_failures.jsonl").exists())


# ===================================================================
# 7.  Source guard tests
# ===================================================================


class ResultWriterSourceGuardTests(unittest.TestCase):
    """ResultWriter scope guard: no heavy deps, no wrong task imports."""

    def test_this_test_module_has_no_heavy_imports(self) -> None:
        heavy = {"torch", "rdkit", "pmdm", "pocketflow"}
        violations: list[str] = []
        for mod_name in sorted(sys.modules):
            lower = mod_name.lower()
            for h in heavy:
                if lower == h or lower.startswith(h + "."):
                    violations.append(mod_name)
        self.assertEqual(
            violations,
            [],
            f"heavy dependencies found in sys.modules: {violations}",
        )

    def test_this_test_module_does_not_import_task29_export(self) -> None:
        self.assertNotIn("covalent_design.export", sys.modules)

    def test_this_test_module_does_not_import_task30_evaluation(self) -> None:
        source_path = ROOT / "src" / "covalent_design" / "inference" / "result_writer.py"
        source = source_path.read_text(encoding="utf-8")
        self.assertNotIn("covalent_design.evaluation", source)

    def test_fixture_files_do_not_contain_schema_version_or_contract_version_as_top_level_keys(self) -> None:
        """Fixtures represent raw domain results; schema/contract version is Task 27 scope."""
        for fixture_name in (
            "valid_exported_result.json",
            "valid_docking_not_run_result.json",
        ):
            data = _load_json(fixture_name)
            self.assertNotIn(
                "schema_version", data,
                f"{fixture_name} must not contain top-level schema_version",
            )
            self.assertNotIn(
                "contract_version", data,
                f"{fixture_name} must not contain top-level contract_version",
            )


# ===================================================================
# 8.  Fixture load and content verification tests
# ===================================================================


class ResultWriterFixtureLoadTests(unittest.TestCase):
    """Committed fixtures are loadable and structurally correct, not merely existing."""

    def test_all_23_committed_fixtures_exist(self) -> None:
        expected = [
            "valid_exported_result.json",
            "valid_docking_not_run_result.json",
            "valid_docking_succeeded_result.json",
            "valid_export_failure_result.json",
            "invalid_no_edge_result.json",
            "invalid_below_threshold_result.json",
            "invalid_rule_failure_result.json",
            "invalid_warhead_match_failure_result.json",
            "invalid_valence_failure_result.json",
            "invalid_geometry_failure_result.json",
            "invalid_required_state_unavailable_result.json",
            "invalid_with_parseable_ligand_diagnostics.json",
            "corrupt_invalid_missing_primary_reason.json",
            "corrupt_invalid_exported_status.json",
            "corrupt_valid_missing_attachment_atom.json",
            "corrupt_valid_missing_predicted_edge.json",
            "corrupt_valid_missing_geometry.json",
            "corrupt_valid_missing_matched_warhead.json",
            "corrupt_docking_success_missing_score.json",
            "corrupt_docking_failure_with_covalent_score.json",
            "corrupt_unknown_failure_reason.json",
            "corrupt_unknown_edge_check_name.json",
            "corrupt_unknown_edge_check_status.json",
        ]
        for name in expected:
            path = FIXTURES / name
            self.assertTrue(path.is_file(), f"missing fixture: {name}")

    def test_each_fixture_decodes_to_covalent_generation_result(self) -> None:
        """Every fixture must produce a valid CovalentGenerationResult dataclass."""
        for path in sorted(FIXTURES.glob("*.json")):
            with self.subTest(fixture=path.name):
                d = _load_json(path.name)
                result = _decode_result(d)
                self.assertIsInstance(result, CovalentGenerationResult)
                self.assertIsInstance(result.request_id, str)
                self.assertIsInstance(result.sample_id, int)

    def test_valid_fixtures_have_required_fields_non_null(self) -> None:
        """Valid fixtures must have all diagnostic fields populated."""
        for name in (
            "valid_exported_result.json",
            "valid_docking_not_run_result.json",
            "valid_docking_succeeded_result.json",
            "valid_export_failure_result.json",
        ):
            with self.subTest(fixture=name):
                result = _decode_result(_load_json(name))
                self.assertEqual(result.generation_validity_status, "valid")
                self.assertIsNotNone(result.predicted_covalent_edge)

    def test_invalid_fixtures_have_correct_status_and_reason(self) -> None:
        """Invalid fixtures must have invalid status and a valid failure reason."""
        for path in sorted(FIXTURES.glob("invalid_*.json")):
            with self.subTest(fixture=path.name):
                result = _decode_result(_load_json(path.name))
                self.assertEqual(
                    result.generation_validity_status, "invalid",
                    f"{path.name}: generation_validity_status must be 'invalid'"
                )
                self.assertIsNotNone(
                    result.primary_failure_reason,
                    f"{path.name}: primary_failure_reason must not be None"
                )

    def test_corrupt_fixtures_have_identifying_violation(self) -> None:
        """Each corrupt fixture must contain a specific identifiable violation."""
        # missing primary reason
        r = _decode_result(_load_json("corrupt_invalid_missing_primary_reason.json"))
        self.assertEqual(r.generation_validity_status, "invalid")
        self.assertIsNone(r.primary_failure_reason)

        # invalid exported status
        r = _decode_result(_load_json("corrupt_invalid_exported_status.json"))
        self.assertEqual(r.generation_validity_status, "invalid")
        self.assertEqual(r.complex_export_status, "exported")

        # missing attachment atom
        r = _decode_result(_load_json("corrupt_valid_missing_attachment_atom.json"))
        self.assertEqual(r.generation_validity_status, "valid")
        self.assertIsNone(r.predicted_ligand_attachment_atom)

        # missing predicted edge
        r = _decode_result(_load_json("corrupt_valid_missing_predicted_edge.json"))
        self.assertEqual(r.generation_validity_status, "valid")
        self.assertIsNone(r.predicted_covalent_edge)

        # missing geometry
        r = _decode_result(_load_json("corrupt_valid_missing_geometry.json"))
        self.assertEqual(r.generation_validity_status, "valid")
        self.assertIsNone(r.geometry_metrics)

        # missing matched warhead
        r = _decode_result(_load_json("corrupt_valid_missing_matched_warhead.json"))
        self.assertEqual(r.generation_validity_status, "valid")
        self.assertIsNone(r.matched_warhead_type)

        # docking success missing score
        r = _decode_result(_load_json("corrupt_docking_success_missing_score.json"))
        self.assertEqual(r.docking_run_status, "succeeded")
        self.assertIsNone(r.covalent_docking_score)

        # docking failure with covalent score
        r = _decode_result(_load_json("corrupt_docking_failure_with_covalent_score.json"))
        self.assertNotEqual(r.docking_run_status, "succeeded")
        self.assertIsNotNone(r.covalent_docking_score)

        # unknown failure reason
        r = _decode_result(_load_json("corrupt_unknown_failure_reason.json"))
        self.assertEqual(r.primary_failure_reason, "MYSTERY_CRASH_CODE")

        # unknown edge check name
        r = _decode_result(_load_json("corrupt_unknown_edge_check_name.json"))
        names = [c.check_name for c in r.edge_validity_checks]
        self.assertIn("quantum_tunneling_effect", names)

        # unknown edge check status
        r = _decode_result(_load_json("corrupt_unknown_edge_check_status.json"))
        statuses = [c.status for c in r.edge_validity_checks]
        self.assertIn("maybe_later", statuses)

    def test_artifact_ref_mapping_preserves_all_keys(self) -> None:
        """Fixture artifacts Mapping must include all declared keys after decoding."""
        result = _decode_result(_load_json("valid_exported_result.json"))
        self.assertIn("ligand_sdf", result.artifacts)
        self.assertIn("complex_mmcif", result.artifacts)
        self.assertIn("complex_pdb", result.artifacts)
        self.assertEqual(result.artifacts["ligand_sdf"].role, "ligand_sdf")

    def test_predicted_covalent_edge_round_trips_through_decoder(self) -> None:
        """CovalentEdge nested ProteinAtomIdentity and LigandAtomIdentity decode correctly."""
        result = _decode_result(_load_json("valid_docking_succeeded_result.json"))
        edge = result.predicted_covalent_edge
        self.assertIsNotNone(edge)
        self.assertEqual(edge.bond_type, "carbon-nitrogen")
        self.assertEqual(edge.protein_atom.residue_name, "LYS")
        self.assertEqual(edge.protein_atom.atom_name, "NZ")
        self.assertEqual(edge.ligand_atom.ligand_id, "LIG003")


if __name__ == "__main__":
    unittest.main()
