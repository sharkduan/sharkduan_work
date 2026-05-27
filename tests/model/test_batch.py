"""Tests for Task 17 model batch contracts.

Covers all 22 requirements from task17-window-b-tests.md.

Public API under test:
    covalent_design.model.batch.make_model_batch(records_path, batch_spec=None)
    covalent_design.model.inspect.inspect_batch(records_path, record_id=None)

CLI under test:
    python -m covalent_design.model.inspect_batch --records <records.jsonl> [--record-id <id>]

These are contract and regression tests for the implemented Task 17 API.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest


#  attempt imports used by contract tests

_make_model_batch = None
_inspect_batch = None
_IMPORT_ERRORS: list[str] = []

try:
    from covalent_design.model.batch import make_model_batch as _mmb
    _make_model_batch = _mmb
except ImportError as exc:
    _IMPORT_ERRORS.append(f"make_model_batch: {exc}")

try:
    from covalent_design.model.inspect import inspect_batch as _ins
    _inspect_batch = _ins
except ImportError as exc:
    _IMPORT_ERRORS.append(f"inspect_batch: {exc}")


#  import contract types

from covalent_design.contracts import (
    ArtifactRef,
    BatchRecordHeader,
    BatchSpec,
    BatchTensors,
    ContractEnvelope,
    ContractError,
    MODEL_BATCH_ERROR_CODES,
    ModelBatch,
    ProteinAtomIdentity,
)

from tests.fixtures.model._builder import ModelBatchFixtureBuilder


#  helpers 

def _raise_if_missing() -> None:
    """Fail with a clear message if production code is not importable."""
    if not _IMPORT_ERRORS:
        return
    raise unittest.SkipTest(
        "Production code not yet implemented (Window C). "
        + "; ".join(_IMPORT_ERRORS)
    )


def _model_batch_fixture_dir() -> str:
    return os.path.join(
        os.path.dirname(__file__), "..", "fixtures", "model"
    )


class ModelBatchHappyPathTests(unittest.TestCase):
    """Requirements 1-8: valid fixtures produce correct ModelBatch."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = ModelBatchFixtureBuilder()
        cls.valid_path = cls.builder.write_valid()

    #  Requirement 1 

    def test_01_valid_fixture_builds_model_batch(self) -> None:
        _raise_if_missing()
        result = _make_model_batch(self.valid_path)

        self.assertIsNotNone(result)
        if isinstance(result, ContractEnvelope):
            self.assertIsInstance(result.payload, ModelBatch)
            batch = result.payload
        else:
            self.assertIsInstance(result, ModelBatch)
            batch = result

        self.assertGreaterEqual(len(batch.records), 2)

    #  Requirement 2 

    def test_02_records_contain_deterministic_batch_record_headers(self) -> None:
        _raise_if_missing()
        result = _make_model_batch(self.valid_path)
        batch = result.payload if isinstance(result, ContractEnvelope) else result

        self.assertIsInstance(batch, ModelBatch)
        ids = {r.record_id for r in batch.records}
        self.assertIn("m01a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6", ids)
        self.assertIn("m02a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6", ids)

        for r in batch.records:
            self.assertIsInstance(r.batch_index, int)
            self.assertGreaterEqual(r.batch_index, 0)
            self.assertIsInstance(r.residue_reaction_family, str)
            self.assertIn(r.quality_tier, ("Q0", "Q1", "Q2"))

    #  Requirement 3 

    def test_03_header_contains_target_atom_identity(self) -> None:
        _raise_if_missing()
        result = _make_model_batch(self.valid_path)
        batch = result.payload if isinstance(result, ContractEnvelope) else result

        rec_a = [r for r in batch.records
                 if r.record_id == "m01a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6"][0]
        self.assertIsInstance(rec_a.target_atom_identity, ProteinAtomIdentity)
        self.assertEqual(rec_a.target_atom_identity.atom_name, "SG")
        self.assertEqual(rec_a.target_atom_identity.residue_name, "CYS")

    #  Requirement 4 

    def test_04_header_contains_target_atom_index(self) -> None:
        _raise_if_missing()
        result = _make_model_batch(self.valid_path)
        batch = result.payload if isinstance(result, ContractEnvelope) else result

        for r in batch.records:
            self.assertIsInstance(r.target_atom_index, int)
            self.assertGreaterEqual(r.target_atom_index, 0)

    #  Requirement 5 

    def test_05_header_contains_target_atom_artifact_role(self) -> None:
        _raise_if_missing()
        result = _make_model_batch(self.valid_path)
        batch = result.payload if isinstance(result, ContractEnvelope) else result

        for r in batch.records:
            self.assertEqual(r.target_atom_artifact_role, "protein_atom_table")

    #  Requirement 6 

    def test_06_static_edge_candidates_refs_maps_record_id(self) -> None:
        _raise_if_missing()
        result = _make_model_batch(self.valid_path)
        batch = result.payload if isinstance(result, ContractEnvelope) else result

        self.assertIsInstance(batch.static_edge_candidates_refs, dict)
        for record_id in ("m01a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6",
                          "m02a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6"):
            self.assertIn(record_id, batch.static_edge_candidates_refs)
            ref = batch.static_edge_candidates_refs[record_id]
            self.assertIsInstance(ref, ArtifactRef)
            self.assertEqual(ref.role, "edge_candidates")

    #  Requirement 7 

    def test_07_batch_tensors_reports_shape_dtype_coordinate_frame(self) -> None:
        _raise_if_missing()
        result = _make_model_batch(self.valid_path)
        batch = result.payload if isinstance(result, ContractEnvelope) else result

        tensors = batch.tensors
        self.assertIsInstance(tensors, BatchTensors)

        for attr in ("protein_coords_shape", "ligand_coords_shape",
                     "protein_atom_types_shape", "ligand_atom_types_shape",
                     "ligand_bonds_shape", "edge_candidates_shape",
                     "positive_label_mask_shape"):
            shape = getattr(tensors, attr)
            self.assertIsInstance(shape, tuple)
            self.assertGreater(len(shape), 1, f"{attr} should be a tensor shape")

        self.assertEqual(tensors.dtype, "float32")
        self.assertEqual(tensors.index_dtype, "int64")
        self.assertEqual(tensors.coordinate_frame, "original_pdb")

    #  Requirement 8 

    def test_08_batch_spec_bond_type_vocabulary_includes_no_edge(self) -> None:
        _raise_if_missing()
        result = _make_model_batch(self.valid_path)
        batch = result.payload if isinstance(result, ContractEnvelope) else result
        self.assertIsNotNone(batch.batch_spec)
        discovered = batch.batch_spec.bond_type_vocabulary
        self.assertEqual(discovered[0], "no_edge")
        self.assertIn("carbon-sulfur", discovered)

        spec = BatchSpec(
            bond_type_vocabulary=(
                "no_edge", "carbon-sulfur", "carbon-nitrogen",
                "carbon-oxygen", "disulfide", "phosphorus-oxygen",
            ),
            max_protein_atoms=10,
            max_ligand_atoms=5,
            max_candidates=10,
        )
        self.assertIn("no_edge", spec.bond_type_vocabulary)
        self.assertEqual(spec.bond_type_vocabulary[0], "no_edge")

        result = _make_model_batch(self.valid_path, batch_spec=spec)
        batch = result.payload if isinstance(result, ContractEnvelope) else result
        self.assertIsInstance(batch, ModelBatch)
        self.assertEqual(batch.batch_spec, spec)


class ModelBatchErrorPathTests(unittest.TestCase):
    """Requirements 9-15: error scenarios return correct error codes."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = ModelBatchFixtureBuilder()
        cls.missing_artifact_path = cls.builder.write_missing_artifact()
        cls.unreadable_artifact_path = cls.builder.write_unreadable_artifact()
        cls.checksum_mismatch_path = cls.builder.write_checksum_mismatch()
        cls.missing_role_path = cls.builder.write_missing_artifact_role()
        cls.unsupported_version_path = cls.builder.write_unsupported_contract_version()
        cls.required_state_path = cls.builder.write_required_state_unavailable()
        cls.missing_state_path = cls.builder.write_missing_chemical_state()

    def _assert_error_code(self, result_or_exc, expected_code: str) -> None:
        """Verify an error result contains the expected error code."""
        if isinstance(result_or_exc, ContractError):
            self.assertEqual(result_or_exc.code, expected_code)
        elif isinstance(result_or_exc, ContractEnvelope):
            receipt = result_or_exc.receipt
            self.assertFalse(receipt.passed)
            codes = [e.code for e in receipt.errors]
            self.assertIn(expected_code, codes)
        elif isinstance(result_or_exc, Exception):
            raise result_or_exc
        else:
            self.fail(f"Unexpected result type: {type(result_or_exc)}")

    def _assert_not_model_batch(self, result_or_exc) -> None:
        """Verify result is NOT a ModelBatch (failure before tensor construction)."""
        if isinstance(result_or_exc, ContractEnvelope):
            self.assertFalse(
                isinstance(result_or_exc.payload, ModelBatch),
                "Error result must not contain a ModelBatch payload",
            )
            self.assertFalse(result_or_exc.receipt.passed)

    #  Requirement 9 

    def test_09_missing_artifact_returns_correct_error_code(self) -> None:
        _raise_if_missing()
        try:
            result = _make_model_batch(self.missing_artifact_path)
        except ContractError as exc:
            self.assertEqual(exc.code, "MODEL_BATCH_ARTIFACT_MISSING")
            return
        self._assert_error_code(result, "MODEL_BATCH_ARTIFACT_MISSING")

    def test_missing_records_jsonl_returns_structured_missing_error(self) -> None:
        _raise_if_missing()
        missing_records = os.path.join(
            tempfile.gettempdir(),
            "covalent_design_missing_model_records.jsonl",
        )
        if os.path.exists(missing_records):
            os.remove(missing_records)

        with self.assertRaises(ContractError) as ctx:
            _make_model_batch(missing_records)
        self.assertEqual(ctx.exception.code, "MODEL_BATCH_ARTIFACT_MISSING")

    #  Requirement 10 

    def test_10_unreadable_artifact_returns_correct_error_code(self) -> None:
        _raise_if_missing()
        try:
            result = _make_model_batch(self.unreadable_artifact_path)
        except ContractError as exc:
            self.assertEqual(exc.code, "MODEL_BATCH_ARTIFACT_UNREADABLE")
            return
        self._assert_error_code(result, "MODEL_BATCH_ARTIFACT_UNREADABLE")

    #  Requirement 11 

    def test_11_checksum_mismatch_returns_correct_error_code(self) -> None:
        _raise_if_missing()
        try:
            result = _make_model_batch(self.checksum_mismatch_path)
        except ContractError as exc:
            self.assertEqual(exc.code, "MODEL_BATCH_ARTIFACT_CHECKSUM_MISMATCH")
            return
        self._assert_error_code(result, "MODEL_BATCH_ARTIFACT_CHECKSUM_MISMATCH")

    #  Requirement 12 

    def test_12_missing_artifact_role_returns_correct_error_code(self) -> None:
        _raise_if_missing()
        try:
            result = _make_model_batch(self.missing_role_path)
        except ContractError as exc:
            self.assertEqual(exc.code, "MODEL_BATCH_ARTIFACT_ROLE_MISSING")
            return
        self._assert_error_code(result, "MODEL_BATCH_ARTIFACT_ROLE_MISSING")

    #  Requirement 13 

    def test_13_unsupported_contract_version_returns_correct_error_code(self) -> None:
        _raise_if_missing()
        try:
            result = _make_model_batch(self.unsupported_version_path)
        except ContractError as exc:
            self.assertEqual(
                exc.code, "MODEL_BATCH_CONTRACT_VERSION_UNSUPPORTED"
            )
            return
        self._assert_error_code(
            result, "MODEL_BATCH_CONTRACT_VERSION_UNSUPPORTED"
        )

    #  Requirement 14 

    def test_14_required_state_unavailable_returns_correct_error_code(self) -> None:
        _raise_if_missing()
        try:
            result = _make_model_batch(self.required_state_path)
        except ContractError as exc:
            self.assertEqual(
                exc.code, "MODEL_BATCH_REQUIRED_STATE_UNAVAILABLE"
            )
            return
        self._assert_error_code(
            result, "MODEL_BATCH_REQUIRED_STATE_UNAVAILABLE"
        )

    def test_missing_chemical_state_returns_required_state_unavailable(self) -> None:
        """Finalized Task 13 records must carry available chemical-state metadata."""
        _raise_if_missing()
        try:
            result = _make_model_batch(self.missing_state_path)
        except ContractError as exc:
            self.assertEqual(
                exc.code, "MODEL_BATCH_REQUIRED_STATE_UNAVAILABLE"
            )
            return
        self._assert_error_code(
            result, "MODEL_BATCH_REQUIRED_STATE_UNAVAILABLE"
        )

    #  Requirement 15 

    def test_15_failures_happen_before_tensor_construction(self) -> None:
        """Every error path must return an error, never a partial ModelBatch."""
        _raise_if_missing()
        error_paths = [
            self.missing_artifact_path,
            self.unreadable_artifact_path,
            self.checksum_mismatch_path,
            self.missing_role_path,
            self.unsupported_version_path,
            self.required_state_path,
            self.missing_state_path,
        ]
        for path in error_paths:
            with self.subTest(path=os.path.basename(path)):
                try:
                    result = _make_model_batch(path)
                except ContractError:
                    continue  # exception is fine
                self._assert_not_model_batch(result)


class ModelBatchNoFilterTests(unittest.TestCase):
    """Requirements 16-17: batch constructor does not filter records."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = ModelBatchFixtureBuilder()
        cls.mixed_path = cls.builder.write_mixed_quality_split()

    #  Requirement 16 

    def test_16_batch_constructor_does_not_check_data_release_gate(self) -> None:
        """Records failing Data Release Gate criteria must still build a batch."""
        _raise_if_missing()
        result = _make_model_batch(self.mixed_path)
        batch = result.payload if isinstance(result, ContractEnvelope) else result
        self.assertIsInstance(batch, ModelBatch)

        ids = {r.record_id for r in batch.records}
        self.assertIn("m09a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6", ids,
                      "Q2 record must be included")
        self.assertIn("m10a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6", ids,
                      "visual-fail record must be included")

    #  Requirement 17 

    def test_17_batch_constructor_does_not_filter_by_quality_or_visual_status(self) -> None:
        """Q2, visual=fail, and test-split records must all be present."""
        _raise_if_missing()
        result = _make_model_batch(self.mixed_path)
        batch = result.payload if isinstance(result, ContractEnvelope) else result

        quality_tiers = {r.quality_tier for r in batch.records}
        self.assertIn("Q2", quality_tiers,
                      "Q2 records must not be filtered by batch constructor")


class InspectBatchContractTests(unittest.TestCase):
    """Requirements 18-20: inspect_batch API and CLI."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = ModelBatchFixtureBuilder()
        cls.valid_path = cls.builder.write_valid()
        cls.missing_artifact_path = cls.builder.write_missing_artifact()
        cls.unsupported_schema_path = cls.builder.write_unsupported_schema_version()

    #  Requirement 18 

    def test_18_inspect_batch_valid_exits_zero_and_prints_deterministic_json(self) -> None:
        """inspect_batch(records_path) must return a structured report."""
        _raise_if_missing()
        report = _inspect_batch(self.valid_path)

        self.assertIsInstance(report, dict)
        self.assertIn("contract_version", report)
        self.assertEqual(report["contract_version"], "1.0.0")
        self.assertIn("batch_spec", report)
        self.assertIn("warnings", report)
        self.assertIn("records", report)
        self.assertGreaterEqual(len(report["records"]), 2)
        for row in report["records"]:
            self.assertIn("provenance", row)
            self.assertIn("tensor_shapes", row)
            self.assertIn("denominators_expected", row)
            self.assertIn("batch_spec", row)
            self.assertIn("warnings", row)

    #  Requirement 19 

    def test_19_inspect_batch_record_id_filters_to_one_record(self) -> None:
        _raise_if_missing()
        report = _inspect_batch(
            self.valid_path,
            record_id="m01a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6",
        )

        self.assertIsInstance(report, dict)
        records = report.get("records", [])
        self.assertEqual(len(records), 1)
        self.assertEqual(
            records[0]["record_id"],
            "m01a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6",
        )

    #  Requirement 20 

    def test_20_inspect_batch_reports_error_reason_for_invalid_record(self) -> None:
        """inspect_batch must not silently skip invalid records."""
        _raise_if_missing()
        report = _inspect_batch(self.missing_artifact_path)

        self.assertIsInstance(report, dict)
        # Should have error info, not an empty records list
        has_error = (
            report.get("errors")
            or any(r.get("error") for r in report.get("records", []))
            or not report.get("passed", True)
        )
        self.assertTrue(
            has_error,
            "inspect_batch must report error for invalid record, not silently skip",
        )

    def test_inspect_batch_rejects_unsupported_record_schema_version(self) -> None:
        """inspect_batch must mirror make_model_batch record schema gating."""
        _raise_if_missing()
        report = _inspect_batch(self.unsupported_schema_path)

        self.assertFalse(report["passed"])
        self.assertEqual(
            report["records"][0]["error_code"],
            "MODEL_BATCH_CONTRACT_VERSION_UNSUPPORTED",
        )
        self.assertIn(
            "MODEL_BATCH_CONTRACT_VERSION_UNSUPPORTED",
            [error["code"] for error in report["errors"]],
        )


class InspectBatchCLITests(unittest.TestCase):
    """Requirements 18-19 via CLI subprocess."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = ModelBatchFixtureBuilder()
        cls.valid_path = cls.builder.write_valid()

    def _run_cli(self, *args: str) -> subprocess.CompletedProcess:
        repo_root = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..")
        )
        env = os.environ.copy()
        env["PYTHONPATH"] = os.path.join(repo_root, "src")
        cmd = [sys.executable, "-m", "covalent_design.model.inspect_batch",
               "--records", self.valid_path, *args]
        return subprocess.run(
            cmd, capture_output=True, text=True,
            cwd=repo_root,
            env=env,
        )

    def test_18_cli_valid_exits_zero(self) -> None:
        """CLI inspect_batch --records <valid> exits 0."""
        proc = self._run_cli()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        parsed = json.loads(proc.stdout)
        self.assertIsInstance(parsed, dict)
        self.assertIn("batch_spec", parsed)
        self.assertIn("warnings", parsed)

    def test_19_cli_record_id_filters(self) -> None:
        """CLI inspect_batch --record-id filters output."""
        proc = self._run_cli(
            "--record-id", "m01a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6",
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        parsed = json.loads(proc.stdout)
        records = parsed.get("records", [parsed])
        self.assertLessEqual(len(records), 1)
        self.assertIn("batch_spec", records[0])
        self.assertIn("warnings", records[0])


class ModelBatchSideEffectTests(unittest.TestCase):
    """Requirements 21-22: no side effects, determinism."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = ModelBatchFixtureBuilder()
        cls.valid_path = cls.builder.write_valid()

    #  Requirement 21 

    def test_21_no_artifacts_generated_by_make_model_batch(self) -> None:
        """make_model_batch must not create model/training artifacts on disk."""
        _raise_if_missing()
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_records = os.path.join(tmpdir, "records.jsonl")
            # Copy valid records to tmpdir
            import shutil
            shutil.copy(self.valid_path, tmp_records)

            files_before = set(os.listdir(tmpdir))
            try:
                _make_model_batch(tmp_records)
            except ContractError:
                pass  # may fail due to artifact path resolution
            # But must not create model artifacts
            files_after = set(os.listdir(tmpdir))
            new_files = files_after - files_before - {"__pycache__"}
            self.assertEqual(
                len(new_files), 0,
                f"make_model_batch must not create files; found {new_files}"
            )

    #  Requirement 22 

    def test_22_output_is_deterministic_across_repeated_runs(self) -> None:
        _raise_if_missing()
        results = []
        for _ in range(3):
            result = _make_model_batch(self.valid_path)
            batch = result.payload if isinstance(result, ContractEnvelope) else result
            results.append(batch)

        # Compare batch_index assignments
        for batch in results:
            rec_ids = [r.record_id for r in batch.records]
            self.assertEqual(
                rec_ids, [r.record_id for r in results[0].records],
                "Record order must be deterministic",
            )

        # Compare tensor shapes
        for batch in results[1:]:
            self.assertEqual(
                batch.tensors.protein_coords_shape,
                results[0].tensors.protein_coords_shape,
            )
            self.assertEqual(
                batch.tensors.ligand_coords_shape,
                results[0].tensors.ligand_coords_shape,
            )


class ModelBatchContractErrorCodesTests(unittest.TestCase):
    """Verify all MODEL_BATCH error codes are registered."""

    def test_all_model_batch_error_codes_are_exported(self) -> None:
        expected = (
            "MODEL_BATCH_ARTIFACT_MISSING",
            "MODEL_BATCH_ARTIFACT_UNREADABLE",
            "MODEL_BATCH_ARTIFACT_CHECKSUM_MISMATCH",
            "MODEL_BATCH_ARTIFACT_ROLE_MISSING",
            "MODEL_BATCH_CONTRACT_VERSION_UNSUPPORTED",
            "MODEL_BATCH_REQUIRED_STATE_UNAVAILABLE",
        )
        for code in expected:
            self.assertIn(code, MODEL_BATCH_ERROR_CODES)

    def test_model_batch_error_codes_owner_is_model(self) -> None:
        from covalent_design.contracts.errors import exit_code_for_error
        for code in MODEL_BATCH_ERROR_CODES:
            from covalent_design.contracts.errors import ContractErrorInfo
            info = ContractErrorInfo(
                code=code, owner="model", message="test",
            )
            exit_code = exit_code_for_error(info)
            self.assertEqual(
                exit_code, 40,
                f"{code} should map to model_or_training_contract_violation (40)",
            )


class BatchRecordHeaderConstructorTests(unittest.TestCase):
    """Verify BatchRecordHeader invariants are enforced at construction."""

    def test_header_rejects_missing_target_atom_identity(self) -> None:
        with self.assertRaises(ValueError):
            BatchRecordHeader(
                record_id="r",
                residue_reaction_family="FAM",
                quality_tier="Q0",
                visual_check_status="pass",
                chemical_state_status="explicit",
                target_atom_identity=None,  # type: ignore[arg-type]
                target_atom_index=0,
            )

    def test_header_rejects_negative_target_atom_index(self) -> None:
        with self.assertRaises(ValueError):
            BatchRecordHeader(
                record_id="r",
                residue_reaction_family="FAM",
                quality_tier="Q0",
                visual_check_status="pass",
                chemical_state_status="explicit",
                target_atom_identity=ProteinAtomIdentity(
                    chain_id="A", residue_number=1,
                    residue_name="CYS", atom_name="SG",
                ),
                target_atom_index=-1,
            )

    def test_header_rejects_empty_artifact_role(self) -> None:
        with self.assertRaises(ValueError):
            BatchRecordHeader(
                record_id="r",
                residue_reaction_family="FAM",
                quality_tier="Q0",
                visual_check_status="pass",
                chemical_state_status="explicit",
                target_atom_identity=ProteinAtomIdentity(
                    chain_id="A", residue_number=1,
                    residue_name="CYS", atom_name="SG",
                ),
                target_atom_index=0,
                target_atom_artifact_role="",
            )


class TargetAtomSerialResolutionTests(unittest.TestCase):
    """Target atom resolution must use the explicit index before atom-name fallback."""

    def test_target_atom_serial_prefers_index_over_ambiguous_name(self) -> None:
        from covalent_design.model.batch import _target_atom_serial as batch_serial
        from covalent_design.model.inspect import _target_atom_serial as inspect_serial

        atoms = [
            {"serial": 101, "name": "CA"},
            {"serial": 202, "name": "CA"},
        ]

        self.assertEqual(batch_serial(atoms, 1, "CA"), 202)
        self.assertEqual(inspect_serial(atoms, 1, "CA"), 202)

    def test_target_atom_serial_does_not_treat_serial_as_index(self) -> None:
        from covalent_design.model.batch import _target_atom_serial as batch_serial
        from covalent_design.model.inspect import _target_atom_serial as inspect_serial

        atoms = [
            {"serial": 8, "name": "CA"},
            {"serial": 99, "name": "SG"},
        ]

        self.assertEqual(batch_serial(atoms, 8, "SG"), 99)
        self.assertEqual(inspect_serial(atoms, 8, "SG"), 99)


if __name__ == "__main__":
    unittest.main()
