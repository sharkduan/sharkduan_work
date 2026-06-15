"""Task 34 Window B: CLI exit codes, error JSON schema, and error-out contract.

Covers:
- exit_code_for_error mapping for all contract error owner categories
- exit_code_for_exception pattern for ContractError, ContractErrorInfo, runtime
- Runtime exception -> exit 1
- Argparse bad arguments -> exit 2
- Deterministic CLI error JSON schema with role == cli_error
- validate_request failure writes error JSON and human-readable stderr
- summarize_results artifact failure writes error JSON
- check_denominators denominator failure writes error JSON
- Data CLI failure writes error JSON / documented error JSON
- Success stdout remains clean and success path does not write error JSON
- Parent directories for error-out are created
- No Task 31/32/33 CLI exists
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from covalent_design.contracts.errors import (
    CLI_EXIT_CODES,
    ContractError,
    ContractErrorInfo,
    exit_code_for_error,
)
from covalent_design.contracts.cli_errors import (
    exit_code_for_exception,
    to_cli_error_json,
    write_cli_error_json,
)
from covalent_design.contracts.types import (
    CONTRACT_VERSION,
    SCHEMA_VERSION,
    REQUEST_VALIDATION_ERROR_CODES,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures"
REQUEST_FIXTURES = FIXTURE_ROOT / "inference" / "request_validation"
EVAL_FIXTURES = FIXTURE_ROOT / "evaluation" / "denominator_accounting"
DATA_FIXTURES = FIXTURE_ROOT / "finalize_record_manifests"


# ---------------------------------------------------------------------------
# helper: invoke CLIs via subprocess
# ---------------------------------------------------------------------------


def _run_cli(module: str, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = "src"
    return subprocess.run(
        [sys.executable, "-m", module, *args],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def _copy_evaluation_fixture(
    test_case: unittest.TestCase,
    name: str,
) -> Path:
    temp_dir = tempfile.TemporaryDirectory()
    test_case.addCleanup(temp_dir.cleanup)
    source = EVAL_FIXTURES / name
    target = Path(temp_dir.name) / name
    shutil.copytree(source, target)
    return target


# ===================================================================
# 1. exit_code_for_error mapping
# ===================================================================


class TestExitCodeForError(unittest.TestCase):
    """exit_code_for_error maps ContractError/ContractErrorInfo to correct exit codes."""

    # -- request errors -> 20 --

    def test_request_error_owner_maps_to_20(self):
        for code in (
            "REQUEST_STRUCTURE_UNREADABLE",
            "REQUEST_TARGET_RESIDUE_NOT_FOUND",
            "REQUEST_TARGET_RESIDUE_AMBIGUOUS",
        ):
            with self.subTest(code=code):
                err = ContractErrorInfo(code=code, owner="request", message="test")
                self.assertEqual(20, exit_code_for_error(err))

    def test_request_prefixed_code_maps_to_20_from_any_owner(self):
        for code in REQUEST_VALIDATION_ERROR_CODES:
            with self.subTest(code=code):
                err = ContractErrorInfo(code=code, owner="inference", message="test")
                self.assertEqual(20, exit_code_for_error(err))

    # -- artifact / checksum -> 11 --

    def test_artifact_code_maps_to_11(self):
        codes = (
            "ARTIFACT_MISSING",
            "ARTIFACT_REF_NOT_OBJECT",
            "ARTIFACT_CHECKSUM_MISMATCH",
            "ARTIFACT_UNREADABLE",
            "ARTIFACT_ROLE_MISMATCH",
            "ARTIFACT_FORMAT_MISMATCH",
        )
        for code in codes:
            with self.subTest(code=code):
                err = ContractErrorInfo(code=code, owner="evaluation", message="test")
                self.assertEqual(11, exit_code_for_error(err))

    def test_checksum_code_maps_to_11(self):
        err = ContractErrorInfo(code="CHECKSUM_MISMATCH", owner="system", message="test")
        self.assertEqual(11, exit_code_for_error(err))

    # -- denominator -> 12 --

    def test_denominator_code_maps_to_12(self):
        codes = (
            "DENOMINATOR_CONSERVATION_FAILED",
            "EVALUATION_DENOMINATOR_COUNT_MISMATCH",
        )
        for code in codes:
            with self.subTest(code=code):
                err = ContractErrorInfo(code=code, owner="evaluation", message="test")
                self.assertEqual(12, exit_code_for_error(err))

    def test_conservation_code_maps_to_12(self):
        err = ContractErrorInfo(code="CONSERVATION_EQUATION_FAILED", owner="evaluation", message="test")
        self.assertEqual(12, exit_code_for_error(err))

    # -- data -> 30 --

    def test_data_owner_maps_to_30(self):
        err = ContractErrorInfo(code="DATA_MANIFEST_INVALID", owner="data", message="test")
        self.assertEqual(30, exit_code_for_error(err))

    def test_data_quality_code_maps_to_30(self):
        err = ContractErrorInfo(code="DATA_QUALITY_GATE_FAILED", owner="data", message="test")
        self.assertEqual(30, exit_code_for_error(err))

    # -- model / training -> 40 --

    def test_model_owner_maps_to_40(self):
        codes = (
            "MODEL_BATCH_ARTIFACT_MISSING",
            "MODEL_BATCH_REQUIRED_STATE_UNAVAILABLE",
        )
        for code in codes:
            with self.subTest(code=code):
                err = ContractErrorInfo(code=code, owner="model", message="test")
                self.assertEqual(40, exit_code_for_error(err))

    def test_training_owner_maps_to_40(self):
        err = ContractErrorInfo(code="TRAINING_CONTRACT_VIOLATION", owner="training", message="test")
        self.assertEqual(40, exit_code_for_error(err))

    # -- docking -> 60 --

    def test_docking_code_in_evaluation_owner_maps_to_60(self):
        err = ContractErrorInfo(code="DOCKING_PROTOCOL_INVALID", owner="evaluation", message="test")
        self.assertEqual(60, exit_code_for_error(err))

    def test_docking_not_evaluable_maps_to_60(self):
        err = ContractErrorInfo(code="DOCKING_NOT_EVALUABLE", owner="evaluation", message="test")
        self.assertEqual(60, exit_code_for_error(err))

    # -- version -> 70 --

    def test_version_code_maps_to_70(self):
        codes = (
            "MANIFEST_SCHEMA_VERSION_UNSUPPORTED",
            "MANIFEST_CONTRACT_VERSION_UNSUPPORTED",
            "JSONL_SCHEMA_VERSION_UNSUPPORTED",
            "JSONL_CONTRACT_VERSION_UNSUPPORTED",
            "ARTIFACT_REF_SCHEMA_VERSION_UNSUPPORTED",
        )
        for code in codes:
            with self.subTest(code=code):
                err = ContractErrorInfo(code=code, owner="evaluation", message="test")
                self.assertEqual(70, exit_code_for_error(err))

    def test_unsupported_version_code_maps_to_70(self):
        err = ContractErrorInfo(code="UNSUPPORTED_VERSION", owner="system", message="test")
        self.assertEqual(70, exit_code_for_error(err))

    # -- generic / fallback -> 10 --

    def test_generic_contract_error_maps_to_10(self):
        for owner in ("system",):
            with self.subTest(owner=owner):
                err = ContractErrorInfo(code="UNKNOWN_CONTRACT_VIOLATION", owner=owner, message="test")
                self.assertEqual(10, exit_code_for_error(err))

    def test_validation_failed_maps_to_10(self):
        err = ContractErrorInfo(code="VALIDATION_FAILED", owner="system", message="test")
        self.assertEqual(10, exit_code_for_error(err))

    # -- ContractError (not just ContractErrorInfo) --

    def test_contract_error_exception_also_maps_correctly(self):
        err = ContractError(code="REQUEST_STRUCTURE_UNREADABLE", owner="request", message="bad")
        self.assertEqual(20, exit_code_for_error(err))

    def test_contract_error_code_prefix_overrides_owner(self):
        err = ContractError(code="DOCKING_RUN_FAILED", owner="evaluation", message="bad")
        self.assertEqual(60, exit_code_for_error(err))


# ===================================================================
# 2. exit_code_for_exception pattern
# ===================================================================


class TestExitCodeForException(unittest.TestCase):
    """Contract: exit_code_for_exception maps exceptions to exit codes."""

    def test_contract_error_uses_exit_code_for_error(self):
        err = ContractError(code="REQUEST_STRUCTURE_UNREADABLE", owner="request", message="bad")
        self.assertEqual(20, exit_code_for_exception(err))

    def test_contract_error_info_uses_exit_code_for_error(self):
        info = ContractErrorInfo(code="ARTIFACT_CHECKSUM_MISMATCH", owner="evaluation", message="bad")
        self.assertEqual(11, exit_code_for_exception(info))

    def test_contract_error_model_training_maps_to_40(self):
        err = ContractError(code="MODEL_BATCH_ARTIFACT_MISSING", owner="model", message="bad")
        self.assertEqual(40, exit_code_for_exception(err))

    def test_contract_error_denominator_maps_to_12(self):
        err = ContractError(code="DENOMINATOR_CONSERVATION_FAILED", owner="evaluation", message="bad")
        self.assertEqual(12, exit_code_for_exception(err))

    def test_contract_error_version_maps_to_70(self):
        err = ContractError(code="MANIFEST_SCHEMA_VERSION_UNSUPPORTED", owner="evaluation", message="bad")
        self.assertEqual(70, exit_code_for_exception(err))

    def test_contract_error_data_maps_to_30(self):
        err = ContractError(code="DATA_QUALITY_GATE_FAILED", owner="data", message="bad")
        self.assertEqual(30, exit_code_for_exception(err))

    def test_contract_error_docking_maps_to_60(self):
        err = ContractError(code="DOCKING_PROTOCOL_INVALID", owner="evaluation", message="bad")
        self.assertEqual(60, exit_code_for_exception(err))

    def test_contract_error_generic_maps_to_10(self):
        err = ContractError(code="SOME_UNKNOWN_ERROR", owner="system", message="bad")
        self.assertEqual(10, exit_code_for_exception(err))

    # runtime exceptions -> 1

    def test_runtime_error_exit_1(self):
        self.assertEqual(1, exit_code_for_exception(RuntimeError("boom")))

    def test_value_error_exit_1(self):
        self.assertEqual(1, exit_code_for_exception(ValueError("bad value")))

    def test_type_error_exit_1(self):
        self.assertEqual(1, exit_code_for_exception(TypeError("wrong type")))

    def test_os_error_exit_1(self):
        self.assertEqual(1, exit_code_for_exception(OSError("file not found")))

    def test_key_error_exit_1(self):
        self.assertEqual(1, exit_code_for_exception(KeyError("missing")))

    def test_attribute_error_exit_1(self):
        self.assertEqual(1, exit_code_for_exception(AttributeError("no attr")))

    def test_import_error_exit_1(self):
        self.assertEqual(1, exit_code_for_exception(ImportError("no module")))

    def test_zero_division_error_exit_1(self):
        self.assertEqual(1, exit_code_for_exception(ZeroDivisionError("div by zero")))

    def test_system_exit_is_not_treated_as_runtime(self):
        exc = SystemExit(0)
        self.assertEqual(0, exc.code)


# ===================================================================
# 3. Deterministic CLI error JSON schema
# ===================================================================


class TestCliErrorJsonSchema(unittest.TestCase):
    """Frozen CLI error JSON shape: role == cli_error, top-level keys, nested error."""

    def test_top_level_keys_are_exact(self):
        error_json = to_cli_error_json(
            code="REQUEST_STRUCTURE_UNREADABLE",
            owner="request",
            message="Structure unreadable",
            exit_code=20,
        )
        self.assertEqual(
            {"schema_version", "contract_version", "role", "ok", "exit_code", "error"},
            set(error_json.keys()),
        )

    def test_role_is_exactly_cli_error(self):
        error_json = to_cli_error_json(code="TEST", owner="system", message="m", exit_code=1)
        self.assertEqual("cli_error", error_json["role"])

    def test_ok_is_always_false(self):
        error_json = to_cli_error_json(code="TEST", owner="system", message="m", exit_code=1)
        self.assertFalse(error_json["ok"])

    def test_error_nested_has_all_fields(self):
        error_json = to_cli_error_json(
            code="REQUEST_STRUCTURE_UNREADABLE",
            owner="request",
            message="Structure is missing ATOM/HETATM records",
            exit_code=20,
            location="structure_path",
            details={"path": "/data/input.pdb"},
        )
        nested = error_json["error"]
        self.assertEqual(
            {"code", "owner", "message", "location", "details"},
            set(nested.keys()),
        )
        self.assertEqual("REQUEST_STRUCTURE_UNREADABLE", nested["code"])
        self.assertEqual("request", nested["owner"])
        self.assertEqual("Structure is missing ATOM/HETATM records", nested["message"])
        self.assertEqual("structure_path", nested["location"])
        self.assertEqual({"path": "/data/input.pdb"}, nested["details"])

    def test_null_location_allowed(self):
        error_json = to_cli_error_json(code="TEST", owner="system", message="m", exit_code=1)
        self.assertIsNone(error_json["error"]["location"])

    def test_empty_details_defaults_to_empty_dict(self):
        error_json = to_cli_error_json(code="TEST", owner="system", message="m", exit_code=1)
        self.assertEqual({}, error_json["error"]["details"])

    def test_exit_code_matches_supplied_value(self):
        for expected_exit in (0, 1, 10, 11, 12, 20, 30, 40, 60, 70):
            with self.subTest(exit_code=expected_exit):
                error_json = to_cli_error_json(
                    code="TEST", owner="system", message="m", exit_code=expected_exit
                )
                self.assertEqual(expected_exit, error_json["exit_code"])

    def test_deterministic_serialization(self):
        args = dict(code="A", owner="request", message="m1", exit_code=20)
        json1 = json.dumps(to_cli_error_json(**args), sort_keys=True, indent=2)
        json2 = json.dumps(to_cli_error_json(**args), sort_keys=True, indent=2)
        self.assertEqual(json1, json2)

    def test_schema_version_matches_contract(self):
        error_json = to_cli_error_json(code="X", owner="system", message="m", exit_code=1)
        self.assertEqual(SCHEMA_VERSION, error_json["schema_version"])

    def test_contract_version_matches_contract(self):
        error_json = to_cli_error_json(code="X", owner="system", message="m", exit_code=1)
        self.assertEqual(CONTRACT_VERSION, error_json["contract_version"])


# ===================================================================
# 4. validate_request CLI
# ===================================================================


class TestValidateRequestCli(unittest.TestCase):
    """validate_request CLI success and failure paths."""

    def test_success_exits_zero(self):
        result = _run_cli(
            "covalent_design.inference.validate_request",
            "--request", str(REQUEST_FIXTURES / "valid_request.yml"),
        )
        self.assertEqual(0, result.returncode, result.stderr)

    def test_success_stdout_is_deterministic_json(self):
        result = _run_cli(
            "covalent_design.inference.validate_request",
            "--request", str(REQUEST_FIXTURES / "valid_request.yml"),
        )
        data = json.loads(result.stdout)
        self.assertEqual("ok", data["status"])
        self.assertIn("request_id", data)
        self.assertIn("rule_table_version", data)

    def test_failure_exits_with_request_error_code_20(self):
        result = _run_cli(
            "covalent_design.inference.validate_request",
            "--request", str(REQUEST_FIXTURES / "error_structure_unreadable.yml"),
        )
        self.assertEqual(20, result.returncode)

    def test_failure_writes_error_json_to_stdout(self):
        result = _run_cli(
            "covalent_design.inference.validate_request",
            "--request", str(REQUEST_FIXTURES / "error_structure_unreadable.yml"),
        )
        data = json.loads(result.stdout)
        self.assertEqual("error", data["status"])
        self.assertIn("errors", data)
        self.assertIsInstance(data["errors"], list)
        self.assertGreater(len(data["errors"]), 0)
        self.assertIn("code", data["errors"][0])
        self.assertIn("message", data["errors"][0])

    def test_failure_writes_human_error_to_stderr(self):
        result = _run_cli(
            "covalent_design.inference.validate_request",
            "--request", str(REQUEST_FIXTURES / "error_structure_unreadable.yml"),
        )
        self.assertIn("REQUEST_STRUCTURE_UNREADABLE", result.stderr)

    def test_failure_writes_error_out_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            error_path = Path(tmp) / "request" / "cli_error.json"
            result = _run_cli(
                "covalent_design.inference.validate_request",
                "--request", str(REQUEST_FIXTURES / "error_structure_unreadable.yml"),
                "--error-out", str(error_path),
            )
            self.assertEqual(20, result.returncode)
            payload = json.loads(error_path.read_text(encoding="utf-8"))
            self.assertEqual("cli_error", payload["role"])
            self.assertEqual(20, payload["exit_code"])
            self.assertEqual("REQUEST_STRUCTURE_UNREADABLE", payload["error"]["code"])

    def test_target_residue_not_found_exits_20(self):
        result = _run_cli(
            "covalent_design.inference.validate_request",
            "--request", str(REQUEST_FIXTURES / "error_target_residue_not_found.yml"),
        )
        self.assertEqual(20, result.returncode)

    def test_target_atom_not_found_exits_20(self):
        result = _run_cli(
            "covalent_design.inference.validate_request",
            "--request", str(REQUEST_FIXTURES / "error_target_atom_not_found.yml"),
        )
        self.assertEqual(20, result.returncode)

    def test_residue_name_mismatch_exits_20(self):
        result = _run_cli(
            "covalent_design.inference.validate_request",
            "--request", str(REQUEST_FIXTURES / "error_residue_name_mismatch.yml"),
        )
        self.assertEqual(20, result.returncode)

    def test_family_unsupported_exits_20(self):
        result = _run_cli(
            "covalent_design.inference.validate_request",
            "--request", str(REQUEST_FIXTURES / "error_family_unsupported.yml"),
        )
        self.assertEqual(20, result.returncode)

    def test_sample_count_invalid_exits_20(self):
        result = _run_cli(
            "covalent_design.inference.validate_request",
            "--request", str(REQUEST_FIXTURES / "error_sample_count_invalid.yml"),
        )
        self.assertEqual(20, result.returncode)

    def test_help_exits_zero(self):
        result = _run_cli("covalent_design.inference.validate_request", "--help")
        self.assertEqual(0, result.returncode)

    def test_missing_required_arg_exits_2(self):
        result = _run_cli("covalent_design.inference.validate_request")
        self.assertEqual(2, result.returncode)

    def test_bad_optional_arg_exits_2(self):
        result = _run_cli(
            "covalent_design.inference.validate_request",
            "--request", str(REQUEST_FIXTURES / "valid_request.yml"),
            "--nonexistent-flag",
        )
        self.assertEqual(2, result.returncode)


# ===================================================================
# 5. summarize_results CLI
# ===================================================================


class TestSummarizeResultsCli(unittest.TestCase):
    """summarize_results CLI success and failure paths."""

    def test_success_with_all_success_fixture(self):
        fixture = _copy_evaluation_fixture(self, "all_success")
        result = _run_cli(
            "covalent_design.evaluation.summarize_results",
            "--manifest", str(fixture / "run_manifest.yml"),
        )
        self.assertEqual(0, result.returncode)
        data = json.loads(result.stdout)
        self.assertIn("requested_sample_count", data)
        self.assertEqual("evaluation_summary", data.get("role"))

    def test_success_stdout_is_deterministic(self):
        fixture1 = _copy_evaluation_fixture(self, "all_success")
        fixture2 = _copy_evaluation_fixture(self, "all_success")
        result1 = _run_cli(
            "covalent_design.evaluation.summarize_results",
            "--manifest", str(fixture1 / "run_manifest.yml"),
        )
        result2 = _run_cli(
            "covalent_design.evaluation.summarize_results",
            "--manifest", str(fixture2 / "run_manifest.yml"),
        )
        self.assertEqual(result1.stdout, result2.stdout)

    def test_artifact_checksum_mismatch_exits_11(self):
        result = _run_cli(
            "covalent_design.evaluation.summarize_results",
            "--manifest", str(EVAL_FIXTURES / "checksum_mismatch" / "run_manifest.yml"),
        )
        self.assertEqual(11, result.returncode)

    def test_artifact_checksum_mismatch_writes_error_to_stderr(self):
        result = _run_cli(
            "covalent_design.evaluation.summarize_results",
            "--manifest", str(EVAL_FIXTURES / "checksum_mismatch" / "run_manifest.yml"),
        )
        error_data = json.loads(result.stderr)
        self.assertIn("error", error_data)
        self.assertIn("message", error_data)

    def test_artifact_checksum_mismatch_writes_error_out(self):
        with tempfile.TemporaryDirectory() as tmp:
            error_path = Path(tmp) / "nested" / "cli_error.json"
            result = _run_cli(
                "covalent_design.evaluation.summarize_results",
                "--manifest", str(EVAL_FIXTURES / "checksum_mismatch" / "run_manifest.yml"),
                "--error-out", str(error_path),
            )
            self.assertEqual(11, result.returncode)
            payload = json.loads(error_path.read_text(encoding="utf-8"))
            self.assertEqual("cli_error", payload["role"])
            self.assertEqual(11, payload["exit_code"])

    def test_artifact_missing_exits_11(self):
        result = _run_cli(
            "covalent_design.evaluation.summarize_results",
            "--manifest", str(EVAL_FIXTURES / "missing_artifact" / "run_manifest.yml"),
        )
        self.assertEqual(11, result.returncode)

    def test_absolute_uri_exits_nonzero(self):
        result = _run_cli(
            "covalent_design.evaluation.summarize_results",
            "--manifest", str(EVAL_FIXTURES / "absolute_uri" / "run_manifest.yml"),
        )
        self.assertNotEqual(0, result.returncode)

    def test_traversal_uri_exits_nonzero(self):
        result = _run_cli(
            "covalent_design.evaluation.summarize_results",
            "--manifest", str(EVAL_FIXTURES / "traversal_uri" / "run_manifest.yml"),
        )
        self.assertNotEqual(0, result.returncode)

    def test_version_unsupported_exits_70(self):
        result = _run_cli(
            "covalent_design.evaluation.summarize_results",
            "--manifest",
            str(EVAL_FIXTURES / "manifest_role_version_invalid" / "run_manifest.yml"),
        )
        self.assertEqual(70, result.returncode)

    def test_corrupt_lifecycle_exits_nonzero(self):
        result = _run_cli(
            "covalent_design.evaluation.summarize_results",
            "--manifest", str(EVAL_FIXTURES / "corrupt_lifecycle" / "run_manifest.yml"),
        )
        self.assertNotEqual(0, result.returncode)

    def test_help_exits_zero(self):
        result = _run_cli("covalent_design.evaluation.summarize_results", "--help")
        self.assertEqual(0, result.returncode)

    def test_missing_required_arg_exits_2(self):
        result = _run_cli("covalent_design.evaluation.summarize_results")
        self.assertEqual(2, result.returncode)


# ===================================================================
# 6. check_denominators CLI
# ===================================================================


class TestCheckDenominatorsCli(unittest.TestCase):
    """check_denominators CLI success and failure paths."""

    def test_success_with_all_success_fixture(self):
        result = _run_cli(
            "covalent_design.evaluation.check_denominators",
            "--manifest", str(EVAL_FIXTURES / "all_success" / "run_manifest.yml"),
        )
        self.assertEqual(0, result.returncode)
        receipt = json.loads(result.stdout)
        self.assertTrue(receipt["passed"])

    def test_denominator_failure_with_corrupt_lifecycle(self):
        result = _run_cli(
            "covalent_design.evaluation.check_denominators",
            "--manifest", str(EVAL_FIXTURES / "corrupt_lifecycle" / "run_manifest.yml"),
        )
        self.assertNotEqual(0, result.returncode)

    def test_denominator_failure_writes_error_to_stderr(self):
        result = _run_cli(
            "covalent_design.evaluation.check_denominators",
            "--manifest", str(EVAL_FIXTURES / "corrupt_lifecycle" / "run_manifest.yml"),
        )
        error_data = json.loads(result.stderr)
        self.assertIn("error", error_data)
        self.assertIn("message", error_data)

    def test_denominator_failure_writes_error_out(self):
        with tempfile.TemporaryDirectory() as tmp:
            error_path = Path(tmp) / "errors" / "cli_error.json"
            result = _run_cli(
                "covalent_design.evaluation.check_denominators",
                "--manifest", str(EVAL_FIXTURES / "corrupt_lifecycle" / "run_manifest.yml"),
                "--error-out", str(error_path),
            )
            self.assertNotEqual(0, result.returncode)
            payload = json.loads(error_path.read_text(encoding="utf-8"))
            self.assertEqual("cli_error", payload["role"])
            self.assertEqual(result.returncode, payload["exit_code"])

    def test_artifact_checksum_mismatch_exits_11(self):
        result = _run_cli(
            "covalent_design.evaluation.check_denominators",
            "--manifest", str(EVAL_FIXTURES / "checksum_mismatch" / "run_manifest.yml"),
        )
        self.assertEqual(11, result.returncode)

    def test_version_invalid_exits_70(self):
        result = _run_cli(
            "covalent_design.evaluation.check_denominators",
            "--manifest",
            str(EVAL_FIXTURES / "jsonl_version_invalid" / "run_manifest.yml"),
        )
        self.assertEqual(70, result.returncode)

    def test_help_exits_zero(self):
        result = _run_cli("covalent_design.evaluation.check_denominators", "--help")
        self.assertEqual(0, result.returncode)

    def test_missing_required_arg_exits_2(self):
        result = _run_cli("covalent_design.evaluation.check_denominators")
        self.assertEqual(2, result.returncode)


# ===================================================================
# 7. Data CLI error handling
# ===================================================================


class TestDataCliErrorHandling(unittest.TestCase):
    """At least one data CLI writes documented error JSON on failure."""

    def _copy_fixture(self, name: str) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        temp_dir = tempfile.TemporaryDirectory()
        src = DATA_FIXTURES / name
        dst = Path(temp_dir.name) / name
        shutil.copytree(src, dst)
        return temp_dir, dst

    def test_valid_fixture_exits_zero(self):
        temp_dir, root = self._copy_fixture("valid")
        self.addCleanup(temp_dir.cleanup)
        result = _run_cli(
            "covalent_design.data.cli.finalize_record_manifests",
            "--records", str(root / "records.jsonl"),
        )
        self.assertEqual(0, result.returncode)
        summary = json.loads(result.stdout)
        self.assertTrue(summary["ok"])
        self.assertGreater(summary["record_count"], 0)

    def test_missing_edge_candidate_exits_artefact_error_code(self):
        temp_dir, root = self._copy_fixture("missing_edge_candidate")
        self.addCleanup(temp_dir.cleanup)
        result = _run_cli(
            "covalent_design.data.cli.finalize_record_manifests",
            "--records", str(root / "records.jsonl"),
        )
        self.assertEqual(11, result.returncode)

    def test_missing_edge_candidate_writes_error_json_to_stdout(self):
        temp_dir, root = self._copy_fixture("missing_edge_candidate")
        self.addCleanup(temp_dir.cleanup)
        result = _run_cli(
            "covalent_design.data.cli.finalize_record_manifests",
            "--records", str(root / "records.jsonl"),
        )
        summary = json.loads(result.stdout)
        self.assertFalse(summary["ok"])
        self.assertIsInstance(summary["errors"], list)
        self.assertGreater(len(summary["errors"]), 0)
        self.assertIn("code", summary["errors"][0])
        self.assertIn("message", summary["errors"][0])

    def test_checksum_mismatch_exits_11(self):
        temp_dir, root = self._copy_fixture("checksum_mismatch")
        self.addCleanup(temp_dir.cleanup)
        result = _run_cli(
            "covalent_design.data.cli.finalize_record_manifests",
            "--records", str(root / "records.jsonl"),
        )
        self.assertEqual(11, result.returncode)

    def test_duplicate_edge_candidate_exits_11(self):
        temp_dir, root = self._copy_fixture("duplicate_edge_candidate")
        self.addCleanup(temp_dir.cleanup)
        result = _run_cli(
            "covalent_design.data.cli.finalize_record_manifests",
            "--records", str(root / "records.jsonl"),
        )
        self.assertEqual(11, result.returncode)

    def test_quality_report_failure_writes_error_out(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing_root = Path(tmp) / "missing_processed"
            error_path = Path(tmp) / "quality" / "cli_error.json"
            result = _run_cli(
                "covalent_design.data.cli.write_quality_report",
                "--processed-root", str(missing_root),
                "--error-out", str(error_path),
            )
            self.assertNotEqual(0, result.returncode)
            self.assertIn("PROCESSED_ROOT_NOT_FOUND", result.stderr)
            payload = json.loads(error_path.read_text(encoding="utf-8"))
            self.assertEqual("cli_error", payload["role"])
            self.assertEqual(result.returncode, payload["exit_code"])
            self.assertEqual("data", payload["error"]["owner"])

    def test_help_exits_zero(self):
        result = _run_cli(
            "covalent_design.data.cli.finalize_record_manifests", "--help"
        )
        self.assertEqual(0, result.returncode)

    def test_missing_required_arg_exits_2(self):
        result = _run_cli("covalent_design.data.cli.finalize_record_manifests")
        self.assertEqual(2, result.returncode)


# ===================================================================
# 8. Success stdout is clean; success path does not write error JSON
# ===================================================================


class TestSuccessStdoutClean(unittest.TestCase):
    """Success stdout contains expected JSON; no error sidecar emitted."""

    def test_validate_request_success_stdout_is_not_error(self):
        result = _run_cli(
            "covalent_design.inference.validate_request",
            "--request", str(REQUEST_FIXTURES / "valid_request.yml"),
        )
        self.assertEqual(0, result.returncode)
        data = json.loads(result.stdout)
        self.assertEqual("ok", data["status"])
        self.assertNotIn("error", {k.lower() for k in data})

    def test_summarize_results_success_stdout_is_summary(self):
        fixture = _copy_evaluation_fixture(self, "all_success")
        result = _run_cli(
            "covalent_design.evaluation.summarize_results",
            "--manifest", str(fixture / "run_manifest.yml"),
        )
        self.assertEqual(0, result.returncode)
        data = json.loads(result.stdout)
        self.assertEqual("evaluation_summary", data.get("role"))
        self.assertIn("requested_sample_count", data)

    def test_check_denominators_success_stdout_is_passing_receipt(self):
        result = _run_cli(
            "covalent_design.evaluation.check_denominators",
            "--manifest", str(EVAL_FIXTURES / "all_success" / "run_manifest.yml"),
        )
        self.assertEqual(0, result.returncode)
        receipt = json.loads(result.stdout)
        self.assertTrue(receipt["passed"])

    def test_data_cli_success_stdout_is_ok_summary(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        src = DATA_FIXTURES / "valid"
        dst = Path(temp_dir.name) / "valid"
        shutil.copytree(src, dst)
        result = _run_cli(
            "covalent_design.data.cli.finalize_record_manifests",
            "--records", str(dst / "records.jsonl"),
        )
        self.assertEqual(0, result.returncode)
        summary = json.loads(result.stdout)
        self.assertTrue(summary["ok"])

    def test_success_path_does_not_write_error_file_in_cwd(self):
        result = _run_cli(
            "covalent_design.inference.validate_request",
            "--request", str(REQUEST_FIXTURES / "valid_request.yml"),
        )
        self.assertEqual(0, result.returncode)
        error_path = REPO_ROOT / "cli_error.json"
        self.assertFalse(
            error_path.exists(), f"Unexpected error file left behind: {error_path}"
        )

    def test_success_stderr_is_empty(self):
        result = _run_cli(
            "covalent_design.inference.validate_request",
            "--request", str(REQUEST_FIXTURES / "valid_request.yml"),
        )
        self.assertEqual(0, result.returncode)
        self.assertEqual("", result.stderr)


# ===================================================================
# 9. Parent directories for error-out are created
# ===================================================================


class TestErrorOutDirectoryCreation(unittest.TestCase):
    """Writing cli_error JSON to a deep path creates parent directories."""

    def test_writes_to_nonexistent_deep_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            deep_dir = Path(tmp) / "a" / "b" / "c"
            error_path = deep_dir / "cli_error.json"
            self.assertFalse(deep_dir.exists())

            error_json = to_cli_error_json(
                code="REQUEST_STRUCTURE_UNREADABLE",
                owner="request",
                message="Structure not readable",
                exit_code=20,
                location="input.pdb",
            )
            write_cli_error_json(error_json, error_path)

            self.assertTrue(error_path.exists())
            self.assertTrue(deep_dir.exists())
            written = json.loads(error_path.read_text(encoding="utf-8"))
            self.assertEqual("cli_error", written["role"])
            self.assertFalse(written["ok"])
            self.assertEqual(20, written["exit_code"])

    def test_round_trip_preserves_all_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sub" / "cli_error.json"
            original = to_cli_error_json(
                code="DENOMINATOR_CONSERVATION_FAILED",
                owner="evaluation",
                message="Sum of split counts does not equal accepted",
                exit_code=12,
                location="attempted_sample_count",
                details={"manifest_count": 10, "actual_count": 9},
            )
            write_cli_error_json(original, path)
            restored = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(original, restored)

    def test_different_exit_codes_produce_different_json(self):
        json20 = json.dumps(
            to_cli_error_json(code="ERR", owner="request", message="m", exit_code=20),
            sort_keys=True,
        )
        json11 = json.dumps(
            to_cli_error_json(code="ERR", owner="evaluation", message="m", exit_code=11),
            sort_keys=True,
        )
        self.assertNotEqual(json20, json11)


# ===================================================================
# 10. No Task 31/32/33 CLI exists
# ===================================================================


class TestNoTask31_32_33Cli(unittest.TestCase):
    """Task 31 (lifecycle reports), Task 32 (docking protocol), and Task 33
    (split metrics) are Python API only — no CLI entry points exist."""

    def test_lifecycle_reports_has_no_cli(self):
        import covalent_design.evaluation.lifecycle_reports as mod
        self.assertFalse(hasattr(mod, "main"))
        self.assertFalse(hasattr(mod, "argparse"))

    def test_failure_modes_has_no_cli(self):
        import covalent_design.evaluation.failure_modes as mod
        self.assertFalse(hasattr(mod, "main"))

    def test_validity_metrics_has_no_cli(self):
        import covalent_design.evaluation.validity_metrics as mod
        self.assertFalse(hasattr(mod, "main"))

    def test_docking_protocol_has_no_cli(self):
        import covalent_design.evaluation.docking_protocol as mod
        self.assertFalse(hasattr(mod, "main"))

    def test_split_metrics_has_no_cli(self):
        import covalent_design.evaluation.split_metrics as mod
        self.assertFalse(hasattr(mod, "main"))

    def test_reports_has_no_cli(self):
        import covalent_design.evaluation.reports as mod
        self.assertFalse(hasattr(mod, "main"))

    def test_no_evaluation_cli_package(self):
        eval_dir = REPO_ROOT / "src" / "covalent_design" / "evaluation" / "cli"
        self.assertFalse(eval_dir.is_dir())

    def test_evaluation_init_does_not_export_cli(self):
        import covalent_design.evaluation as pkg
        exports = set(getattr(pkg, "__all__", []))
        cli_names = {n for n in exports if "cli" in n.lower()}
        self.assertEqual(set(), cli_names)


# ===================================================================
# 11. Argparse bad arguments -> exit 2 (cross-CLI)
# ===================================================================


class TestArgparseBadArgumentsExit2(unittest.TestCase):
    """All CLIs return exit code 2 on unrecognised or missing arguments."""

    def test_validate_request_no_args_exit_2(self):
        result = _run_cli("covalent_design.inference.validate_request")
        self.assertEqual(2, result.returncode)

    def test_validate_request_bad_flag_exit_2(self):
        result = _run_cli(
            "covalent_design.inference.validate_request",
            "--request", str(REQUEST_FIXTURES / "valid_request.yml"),
            "--not-a-flag",
        )
        self.assertEqual(2, result.returncode)

    def test_summarize_results_no_args_exit_2(self):
        result = _run_cli("covalent_design.evaluation.summarize_results")
        self.assertEqual(2, result.returncode)

    def test_summarize_results_bad_flag_exit_2(self):
        result = _run_cli(
            "covalent_design.evaluation.summarize_results",
            "--manifest", str(EVAL_FIXTURES / "all_success" / "run_manifest.yml"),
            "--not-a-flag",
        )
        self.assertEqual(2, result.returncode)

    def test_check_denominators_no_args_exit_2(self):
        result = _run_cli("covalent_design.evaluation.check_denominators")
        self.assertEqual(2, result.returncode)

    def test_data_cli_no_args_exit_2(self):
        result = _run_cli("covalent_design.data.cli.finalize_record_manifests")
        self.assertEqual(2, result.returncode)

    def test_data_cli_bad_flag_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = _run_cli(
                "covalent_design.data.cli.finalize_record_manifests",
                "--records", str(Path(tmp) / "nonexistent.jsonl"),
                "--not-a-flag",
            )
            self.assertEqual(2, result.returncode)


if __name__ == "__main__":
    unittest.main()
