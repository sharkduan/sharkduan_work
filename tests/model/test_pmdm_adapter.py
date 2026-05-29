"""Tests for Task 19 PMDM adapter contracts.

Covers all 16 requirements from the Task 19 spec.

Public APIs under test:
    covalent_design.model.config.ModelConfig
    covalent_design.model.pmdm_adapter.forward_pmdm(*, batch, config, timestep=0.5)
    covalent_design.model.pmdm_adapter.validate_pmdm_outputs(pmdm_outputs, *, batch, config)

These are contract and regression tests for the implemented Task 19 API.
"""

from __future__ import annotations

import copy
import os
import subprocess
import sys
import tempfile
import unittest


# ===================================================================
# production imports
# ===================================================================

from covalent_design.model.pmdm_adapter import forward_pmdm as _forward_pmdm
from covalent_design.model.pmdm_adapter import validate_pmdm_outputs as _validate_pmdm_outputs
from covalent_design.model.config import ModelConfig as _ModelConfig

# contract types (exist from Task 17)
from covalent_design.contracts import (
    ContractError,
    EdgeDenominators,
    ModelForwardOutput,
)
from covalent_design.contracts.types import (
    ALLOWED_MESSAGE_WEIGHT_SOURCES,
    MESSAGE_WEIGHT_SOURCE_DETACHED_EDGE_PROBABILITY,
    BatchTensors,
    ModelBatch,
)

from covalent_design.model.pmdm_adapter import SMOKE_PLACEHOLDER
from tests.fixtures.model.pmdm_adapter._builder import (
    ALL_PMDM_KEYS,
    DEFAULT_CROSS_FEATURE_DIM,
    DEFAULT_LIGAND_FEATURE_DIM,
    DEFAULT_PAIR_FEATURE_DIM,
    DEFAULT_PROTEIN_FEATURE_DIM,
    OPTIONAL_PMDM_KEYS,
    REQUIRED_PMDM_KEYS,
    PMDMAdapterFixtureBuilder,
)


def _raise_if_missing() -> None:
    """Compatibility no-op retained for earlier helper calls."""
    return


# ===================================================================
# helpers
# ===================================================================


def _assert_is_smoke_placeholder(test: unittest.TestCase, obj: object) -> None:
    """Assert *obj* is a Task-20 smoke placeholder, not real covalent heads."""
    test.assertIs(
        obj,
        SMOKE_PLACEHOLDER,
        "Task 20 field must be a smoke placeholder (SMOKE_PLACEHOLDER), "
        f"not {type(obj).__name__}",
    )


# ===================================================================
# Requirements 1-3: smoke fixture, batch acceptance, output type
# ===================================================================


class PMDMAdapterSmokeTests(unittest.TestCase):
    """Requirements 1-3: fake backbone smoke, batch acceptance, return type."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = PMDMAdapterFixtureBuilder(seed=42)
        cls.batch = cls.builder.build_model_batch()
        cls.config = cls.builder.build_config_dict()

    # Requirement 1 - fake backbone smoke fixture

    def test_01_fake_backbone_smoke_fixture_produces_outputs(self) -> None:
        """The fake backbone generates valid PMDM outputs with correct shapes."""
        _raise_if_missing()

        outputs = self.builder.build_fake_pmdm_outputs(
            self.batch.tensors, seed=42
        )

        self.assertIsInstance(outputs, dict)
        # All 7 required keys must be present
        for key in REQUIRED_PMDM_KEYS:
            self.assertIn(key, outputs, f"missing required key {key!r}")

        # Shapes must be non-trivial
        lig_shape = self.builder.get_shape(outputs["ligand_atom_features"])
        self.assertEqual(len(lig_shape), 3)
        prot_shape = self.builder.get_shape(outputs["protein_atom_features"])
        self.assertEqual(len(prot_shape), 3)
        coords_shape = self.builder.get_shape(outputs["ligand_coords_denoised"])
        self.assertEqual(len(coords_shape), 3)
        self.assertEqual(coords_shape[-1], 3)

    # Requirement 2 - adapter accepts ModelBatch from Task 17 fixtures

    def test_02_adapter_accepts_model_batch_from_task17_fixture(self) -> None:
        """forward_pmdm must accept a ModelBatch constructed by Task 17."""
        _raise_if_missing()

        # The batch must be a ModelBatch instance
        self.assertIsInstance(self.batch, ModelBatch)
        self.assertIsInstance(self.batch.tensors, BatchTensors)

        result = _forward_pmdm(
            batch=self.batch, config=self.config, timestep=0.5
        )
        self.assertIsNotNone(result)

    # Requirement 3 - adapter returns ModelForwardOutput

    def test_03_adapter_returns_model_forward_output(self) -> None:
        """forward_pmdm must return a ModelForwardOutput instance."""
        _raise_if_missing()

        result = _forward_pmdm(
            batch=self.batch, config=self.config, timestep=0.5
        )
        self.assertIsInstance(result, ModelForwardOutput)
        self.assertIsInstance(result.pmdm_outputs, dict)


# ===================================================================
# Requirements 4-6: required keys, optional disabled, optional enabled
# ===================================================================


class PMDMOutputKeysTests(unittest.TestCase):
    """Requirements 4-6: key vocabulary in pmdm_outputs."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = PMDMAdapterFixtureBuilder(seed=42)
        cls.batch = cls.builder.build_model_batch()

    # Requirement 4 - pmdm_outputs contains all 7 required keys

    def test_04_pmdm_outputs_contains_all_seven_required_keys(self) -> None:
        """Default forward_pmdm must include all 7 required keys."""
        _raise_if_missing()

        config = self.builder.build_config_dict(enable_optional_pair_features=False)
        result = _forward_pmdm(batch=self.batch, config=config, timestep=0.5)

        for key in REQUIRED_PMDM_KEYS:
            self.assertIn(
                key,
                result.pmdm_outputs,
                f"pmdm_outputs missing required key {key!r}",
            )

    # Requirement 5 - optional keys disabled by default

    def test_05_optional_keys_disabled_by_default(self) -> None:
        """When config does not enable optional features, optional keys must be
        absent from pmdm_outputs."""
        _raise_if_missing()

        config = self.builder.build_config_dict(enable_optional_pair_features=False)
        result = _forward_pmdm(batch=self.batch, config=config, timestep=0.5)

        for key in OPTIONAL_PMDM_KEYS:
            self.assertNotIn(
                key,
                result.pmdm_outputs,
                f"optional key {key!r} must be absent when disabled",
            )

    # Requirement 6 - optional keys enabled by config

    def test_06_optional_keys_enabled_by_config(self) -> None:
        """When config enables optional features, optional keys must be present
        in pmdm_outputs."""
        _raise_if_missing()

        config = self.builder.build_config_dict(enable_optional_pair_features=True)
        result = _forward_pmdm(batch=self.batch, config=config, timestep=0.5)

        for key in OPTIONAL_PMDM_KEYS:
            self.assertIn(
                key,
                result.pmdm_outputs,
                f"optional key {key!r} must be present when enabled",
            )

    def test_06b_optional_keys_are_enabled_independently(self) -> None:
        """Each optional PMDM key follows its own feature dimension gate."""
        _raise_if_missing()

        config = _ModelConfig(
            rule_table_hash="sha256:fixture",
            ligand_pair_feature_dim=DEFAULT_PAIR_FEATURE_DIM,
            protein_ligand_pair_feature_dim=0,
        )
        result = _forward_pmdm(batch=self.batch, config=config, timestep=0.5)

        self.assertIn("ligand_pair_features", result.pmdm_outputs)
        self.assertNotIn("protein_ligand_pair_features", result.pmdm_outputs)

        config = _ModelConfig(
            rule_table_hash="sha256:fixture",
            ligand_pair_feature_dim=0,
            protein_ligand_pair_feature_dim=DEFAULT_CROSS_FEATURE_DIM,
        )
        result = _forward_pmdm(batch=self.batch, config=config, timestep=0.5)

        self.assertNotIn("ligand_pair_features", result.pmdm_outputs)
        self.assertIn("protein_ligand_pair_features", result.pmdm_outputs)


# ===================================================================
# Requirement 7: required shapes
# ===================================================================


class PMDMOutputShapesTests(unittest.TestCase):
    """Requirement 7: shape validation for each required key."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = PMDMAdapterFixtureBuilder(seed=42)
        cls.batch = cls.builder.build_model_batch()
        cls.config = cls.builder.build_config_dict()

    def _forward_and_get_outputs(self) -> dict:
        _raise_if_missing()
        result = _forward_pmdm(batch=self.batch, config=self.config, timestep=0.5)
        return result.pmdm_outputs

    # 7a

    def test_07a_ligand_atom_features_shape(self) -> None:
        outputs = self._forward_and_get_outputs()
        shape = self.builder.get_shape(outputs["ligand_atom_features"])

        B = self.batch.tensors.protein_coords_shape[0]
        N_lig = self.batch.tensors.ligand_coords_shape[1]
        D_lig = DEFAULT_LIGAND_FEATURE_DIM
        expected = (B, N_lig, D_lig)

        self.assertTrue(
            self.builder.shapes_equal(shape, expected),
            f"ligand_atom_features shape {shape} != expected {expected}",
        )

    # 7b

    def test_07b_protein_atom_features_shape(self) -> None:
        outputs = self._forward_and_get_outputs()
        shape = self.builder.get_shape(outputs["protein_atom_features"])

        B = self.batch.tensors.protein_coords_shape[0]
        N_prot = self.batch.tensors.protein_coords_shape[1]
        D_prot = DEFAULT_PROTEIN_FEATURE_DIM
        expected = (B, N_prot, D_prot)

        self.assertTrue(
            self.builder.shapes_equal(shape, expected),
            f"protein_atom_features shape {shape} != expected {expected}",
        )

    # 7c

    def test_07c_ligand_coords_denoised_shape(self) -> None:
        outputs = self._forward_and_get_outputs()
        shape = self.builder.get_shape(outputs["ligand_coords_denoised"])

        B = self.batch.tensors.protein_coords_shape[0]
        N_lig = self.batch.tensors.ligand_coords_shape[1]
        expected = (B, N_lig, 3)

        self.assertTrue(
            self.builder.shapes_equal(shape, expected),
            f"ligand_coords_denoised shape {shape} != expected {expected}",
        )

    # 7d

    def test_07d_position_loss_is_scalar(self) -> None:
        outputs = self._forward_and_get_outputs()
        shape = self.builder.get_shape(outputs["position_loss"])
        self.assertEqual(shape, (), "position_loss must be scalar")

    # 7e

    def test_07e_atom_type_loss_is_scalar(self) -> None:
        outputs = self._forward_and_get_outputs()
        shape = self.builder.get_shape(outputs["atom_type_loss"])
        self.assertEqual(shape, (), "atom_type_loss must be scalar")

    # 7f

    def test_07f_timestep_is_scalar_float(self) -> None:
        outputs = self._forward_and_get_outputs()
        ts = outputs["timestep"]
        shape = self.builder.get_shape(ts)
        self.assertEqual(shape, (), "timestep must be scalar")
        self.assertIsInstance(ts, float, "timestep must be a float")

    # 7g

    def test_07g_num_atom_shape(self) -> None:
        outputs = self._forward_and_get_outputs()
        shape = self.builder.get_shape(outputs["num_atom"])

        B = self.batch.tensors.protein_coords_shape[0]
        expected = (B,)

        self.assertTrue(
            self.builder.shapes_equal(shape, expected),
            f"num_atom shape {shape} != expected {expected}",
        )


# ===================================================================
# Requirements 8-9: validation error paths
# ===================================================================


class PMDMValidationErrorTests(unittest.TestCase):
    """Requirements 8-9: validation raises structured errors on bad outputs."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = PMDMAdapterFixtureBuilder(seed=42)
        cls.batch = cls.builder.build_model_batch()
        cls.config = cls.builder.build_config_dict()

    def _good_outputs(self) -> dict:
        return self.builder.build_fake_pmdm_outputs(self.batch.tensors, seed=42)

    # Requirement 8 - missing required key

    def test_08_missing_required_key_raises_structured_model_error(self) -> None:
        """validate_pmdm_outputs must raise ContractError when a required key
        is missing."""
        _raise_if_missing()

        outputs = self._good_outputs()
        del outputs["position_loss"]

        with self.assertRaises(ContractError) as ctx:
            _validate_pmdm_outputs(
                pmdm_outputs=outputs, batch=self.batch, config=self.config,
            )
        self.assertEqual(ctx.exception.owner, "model")
        self.assertIn("position_loss", ctx.exception.message.lower())

    # Requirement 9 - wrong shape

    def test_09_wrong_shape_raises_structured_model_error(self) -> None:
        """validate_pmdm_outputs must raise ContractError when a value has
        the wrong shape."""
        _raise_if_missing()

        outputs = self._good_outputs()
        # Corrupt ligand_coords_denoised: last dim should be 3, make it 4
        B = self.batch.tensors.protein_coords_shape[0]
        N_lig = self.batch.tensors.ligand_coords_shape[1]
        outputs["ligand_coords_denoised"] = [
            [[0.0, 0.0, 0.0, 0.0] for _ in range(N_lig)] for _ in range(B)
        ]

        with self.assertRaises(ContractError) as ctx:
            _validate_pmdm_outputs(
                pmdm_outputs=outputs, batch=self.batch, config=self.config,
            )
        self.assertEqual(ctx.exception.owner, "model")
        self.assertEqual(ctx.exception.code, "PMDM_SHAPE_MISMATCH")

    def test_unknown_key_raises_structured_model_error(self) -> None:
        """validate_pmdm_outputs must reject keys outside the PMDM vocabulary."""
        _raise_if_missing()

        outputs = self._good_outputs()
        outputs["fake_features"] = []

        with self.assertRaises(ContractError) as ctx:
            _validate_pmdm_outputs(
                pmdm_outputs=outputs, batch=self.batch, config=self.config,
            )
        self.assertEqual(ctx.exception.owner, "model")
        self.assertEqual(ctx.exception.code, "PMDM_UNKNOWN_KEY")

    def test_missing_enabled_optional_key_raises_structured_model_error(self) -> None:
        """Enabled optional pair features must be present when requested."""
        _raise_if_missing()

        config = self.builder.build_config_dict(enable_optional_pair_features=True)
        outputs = self.builder.build_fake_pmdm_outputs(
            self.batch.tensors, seed=42, enable_optional=True,
        )
        del outputs["ligand_pair_features"]

        with self.assertRaises(ContractError) as ctx:
            _validate_pmdm_outputs(
                pmdm_outputs=outputs, batch=self.batch, config=config,
            )
        self.assertEqual(ctx.exception.owner, "model")
        self.assertEqual(ctx.exception.code, "PMDM_MISSING_OPTIONAL_KEY")

    def test_unexpected_disabled_optional_key_raises_structured_model_error(self) -> None:
        """Disabled optional pair features must not be silently accepted."""
        _raise_if_missing()

        outputs = self.builder.build_fake_pmdm_outputs(
            self.batch.tensors, seed=42, enable_optional=True,
        )

        with self.assertRaises(ContractError) as ctx:
            _validate_pmdm_outputs(
                pmdm_outputs=outputs, batch=self.batch, config=self.config,
            )
        self.assertEqual(ctx.exception.owner, "model")
        self.assertEqual(ctx.exception.code, "PMDM_UNEXPECTED_OPTIONAL_KEY")


# ===================================================================
# Requirements 10-11: determinism
# ===================================================================


class PMDMDeterminismTests(unittest.TestCase):
    """Requirements 10-11: deterministic output with fixed seed."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = PMDMAdapterFixtureBuilder(seed=42)
        cls.batch = cls.builder.build_model_batch()
        cls.config = cls.builder.build_config_dict()

    # Requirement 10 - deterministic with same seed

    def test_10_deterministic_output_with_same_seed(self) -> None:
        """Two forward_pmdm calls with the same seed produce identical
        pmdm_outputs."""
        _raise_if_missing()

        config_a = self.builder.build_config_dict(seed=42)
        config_b = self.builder.build_config_dict(seed=42)

        result_a = _forward_pmdm(
            batch=self.batch, config=config_a, timestep=0.5
        )
        result_b = _forward_pmdm(
            batch=self.batch, config=config_b, timestep=0.5
        )

        self.assertEqual(
            result_a.pmdm_outputs,
            result_b.pmdm_outputs,
            "Same seed must produce identical pmdm_outputs",
        )

    # Requirement 11 - different seed changes output

    def test_11_different_seed_changes_deterministic_fake_outputs(self) -> None:
        """Two forward_pmdm calls with different seeds produce different
        pmdm_outputs (non-scalar values differ)."""
        _raise_if_missing()

        config_a = self.builder.build_config_dict(seed=42)
        config_b = self.builder.build_config_dict(seed=99)

        result_a = _forward_pmdm(
            batch=self.batch, config=config_a, timestep=0.5
        )
        result_b = _forward_pmdm(
            batch=self.batch, config=config_b, timestep=0.5
        )

        # At least one non-scalar output must differ
        differing_keys = []
        for key in REQUIRED_PMDM_KEYS:
            va = result_a.pmdm_outputs[key]
            vb = result_b.pmdm_outputs[key]
            shape = self.builder.get_shape(va)
            if shape == ():
                # Scalars may differ or not - skip
                continue
            if va != vb:
                differing_keys.append(key)

        self.assertGreater(
            len(differing_keys),
            0,
            "Different seeds must produce different non-scalar outputs; "
            "all non-scalar keys were identical",
        )


# ===================================================================
# Requirements 12-13: ModelConfig contracts
# ===================================================================


class ModelConfigContractTests(unittest.TestCase):
    """Requirements 12-13: ModelConfig metadata and serialisation."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = PMDMAdapterFixtureBuilder(seed=42)

    # Requirement 12 - contract_version and rule_table_hash

    def test_12_model_config_contains_contract_version_and_rule_table_hash(self) -> None:
        """ModelConfig must carry contract_version and rule_table_hash."""
        _raise_if_missing()

        config = _ModelConfig(
            contract_version="1.0.0",
            rule_table_hash="sha256:feedface",
        )
        self.assertEqual(config.contract_version, "1.0.0")
        self.assertEqual(config.rule_table_hash, "sha256:feedface")

    # Requirement 13 - deterministic to_dict()

    def test_13_model_config_has_deterministic_to_dict(self) -> None:
        """ModelConfig.to_dict() must be deterministic across repeated calls."""
        _raise_if_missing()

        config = _ModelConfig(
            contract_version="1.0.0",
            rule_table_hash="sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
        )

        d1 = config.to_dict()
        d2 = config.to_dict()

        self.assertEqual(d1, d2)
        self.assertIn("contract_version", d1)
        self.assertIn("rule_table_hash", d1)
        self.assertEqual(d1["contract_version"], "1.0.0")

    def test_13b_to_dict_is_stable_across_instances(self) -> None:
        """Two ModelConfig instances with identical fields produce identical
        to_dict() output."""
        _raise_if_missing()

        kwargs = {
            "contract_version": "1.0.0",
            "rule_table_hash": "sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
        }
        d1 = _ModelConfig(**kwargs).to_dict()
        d2 = _ModelConfig(**kwargs).to_dict()
        self.assertEqual(d1, d2)

    def test_13c_to_dict_output_is_json_serializable(self) -> None:
        """to_dict() output must be JSON-serializable."""
        _raise_if_missing()

        import json

        config = _ModelConfig(
            contract_version="1.0.0",
            rule_table_hash="sha256:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
        )
        d = config.to_dict()
        # Must not raise
        encoded = json.dumps(d, sort_keys=True)
        self.assertIsInstance(encoded, str)


# ===================================================================
# Requirements 14-15: import isolation
# ===================================================================


class PMDMImportIsolationTests(unittest.TestCase):
    """Requirements 14-15: no heavy imports or Task-20 modules."""

    # Requirement 14 - no PMDM/PocketFlow/torch/RDKit

    def test_14_importing_adapter_does_not_import_heavy_libs(self) -> None:
        """Importing covalent_design.model.pmdm_adapter must not pull in
        PMDM, PocketFlow, torch, or RDKit."""
        # Take snapshot before forced import
        pre_modules = set(sys.modules.keys())

        mods_to_check = ["covalent_design.model.pmdm_adapter",
                         "covalent_design.model.config"]
        for mod_name in mods_to_check:
            if mod_name in sys.modules:
                del sys.modules[mod_name]

        from covalent_design.model import pmdm_adapter  # noqa: F401

        from covalent_design.model import config  # noqa: F401

        post_modules = set(sys.modules.keys())
        new_modules = post_modules - pre_modules

        forbidden_prefixes = ("pmdm", "pocketflow", "torch", "rdkit")
        violations: list[str] = []
        for mod in new_modules:
            lower = mod.lower()
            for prefix in forbidden_prefixes:
                if lower.startswith(prefix) or f".{prefix}" in lower:
                    violations.append(mod)
                    break

        self.assertEqual(
            violations,
            [],
            f"adapter/config imported forbidden modules: {violations}",
        )

    # Requirement 15 - no Task 20 modules

    def test_15_no_task20_covalent_heads_or_message_passing_imported(self) -> None:
        """Importing the adapter or config must not import Task 20 modules
        (covalent_heads, edge_message_passing, etc.)."""
        pre_modules = set(sys.modules.keys())

        mods_to_check = ["covalent_design.model.pmdm_adapter",
                         "covalent_design.model.config"]
        for mod_name in mods_to_check:
            if mod_name in sys.modules:
                del sys.modules[mod_name]

        from covalent_design.model import pmdm_adapter  # noqa: F401

        from covalent_design.model import config  # noqa: F401

        post_modules = set(sys.modules.keys())
        new_modules = post_modules - pre_modules

        task20_modules = {
            "covalent_design.model.covalent_heads",
            "covalent_design.model.edge_message_passing",
            "covalent_design.model.final_decode",
            "covalent_design.model.validity_gate",
            "covalent_design.model.geometry_features",
            "covalent_design.model.conditioning",
            "covalent_design.model.reactive_site_features",
            "covalent_design.model.family_conditioning",
            "covalent_design.model.size_prior",
        }

        violations = [m for m in new_modules if m in task20_modules]
        self.assertEqual(
            violations,
            [],
            f"Task 19 imports must not pull in Task 20 modules: {violations}",
        )

    def test_15e_fresh_pmdm_import_does_not_import_later_task_modules(self) -> None:
        """A fresh interpreter import of the Task 19 module must not eager-load
        Task 20/21 modules through covalent_design.model.__init__."""
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        env = os.environ.copy()
        env["PYTHONPATH"] = os.path.join(repo_root, "src")
        code = (
            "import sys; "
            "import covalent_design.model.pmdm_adapter; "
            "loaded = [name for name in ("
            "'covalent_design.model.covalent_heads',"
            "'covalent_design.model.edge_message_passing',"
            "'covalent_design.model.final_decode',"
            "'covalent_design.model.validity_gate'"
            ") if name in sys.modules]; "
            "assert not loaded, loaded"
        )
        proc = subprocess.run(
            [sys.executable, "-c", code],
            cwd=repo_root,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_15b_model_forward_output_message_weight_source_is_valid(self) -> None:
        """ModelForwardOutput constructed with smoke placeholders must pass the
        message_weight_source contract check."""
        _raise_if_missing()

        config = self.builder.build_config_dict() if hasattr(self, "builder") else {}
        # _raise_if_missing will skip if imports failed, so we're safe here

        # Construct a ModelForwardOutput with smoke placeholders
        try:
            output = ModelForwardOutput(
                pmdm_outputs={"ligand_atom_features": []},
                edge_logits=SMOKE_PLACEHOLDER,
                bond_type_logits=SMOKE_PLACEHOLDER,
                family_logits=SMOKE_PLACEHOLDER,
                edge_prob_message_weights=SMOKE_PLACEHOLDER,
                message_weight_source=MESSAGE_WEIGHT_SOURCE_DETACHED_EDGE_PROBABILITY,
                denominators_observed=EdgeDenominators(
                    candidate_count=0,
                    natural_candidate_count=0,
                    forced_positive_count=0,
                    eligible_edge_count=0,
                    masked_candidate_count=0,
                    edge_loss_denominator=0,
                    bond_type_loss_denominator=0,
                    geometry_loss_denominator=0,
                    message_passing_candidate_count=0,
                    gate_evaluated_count=0,
                ),
            )
        except ValueError as exc:
            self.fail(f"ModelForwardOutput smoke construction failed: {exc}")

        self.assertEqual(
            output.message_weight_source,
            MESSAGE_WEIGHT_SOURCE_DETACHED_EDGE_PROBABILITY,
        )

    def test_15c_label_ground_truth_target_edge_sources_rejected(self) -> None:
        """ModelForwardOutput construction must reject invalid message_weight_source
        values (label, ground_truth, target_edge)."""
        invalid_sources = ("label", "ground_truth", "target_edge")

        for source in invalid_sources:
            with self.subTest(source=source):
                with self.assertRaises(ValueError):
                    ModelForwardOutput(
                        pmdm_outputs={"ligand_atom_features": []},
                        edge_logits=SMOKE_PLACEHOLDER,
                        bond_type_logits=SMOKE_PLACEHOLDER,
                        family_logits=SMOKE_PLACEHOLDER,
                        edge_prob_message_weights=SMOKE_PLACEHOLDER,
                        message_weight_source=source,
                        denominators_observed=EdgeDenominators(
                            candidate_count=0,
                            natural_candidate_count=0,
                            forced_positive_count=0,
                            eligible_edge_count=0,
                            masked_candidate_count=0,
                            edge_loss_denominator=0,
                            bond_type_loss_denominator=0,
                            geometry_loss_denominator=0,
                            message_passing_candidate_count=0,
                            gate_evaluated_count=0,
                        ),
                    )

    def test_15d_unknown_source_is_rejected(self) -> None:
        """Any message_weight_source not in ALLOWED_MESSAGE_WEIGHT_SOURCES
        must be rejected at construction."""
        with self.assertRaises(ValueError):
            ModelForwardOutput(
                pmdm_outputs={"ligand_atom_features": []},
                edge_logits=SMOKE_PLACEHOLDER,
                bond_type_logits=SMOKE_PLACEHOLDER,
                family_logits=SMOKE_PLACEHOLDER,
                edge_prob_message_weights=SMOKE_PLACEHOLDER,
                message_weight_source="unknown_provenance",
                denominators_observed=EdgeDenominators(
                    candidate_count=0,
                    natural_candidate_count=0,
                    forced_positive_count=0,
                    eligible_edge_count=0,
                    masked_candidate_count=0,
                    edge_loss_denominator=0,
                    bond_type_loss_denominator=0,
                    geometry_loss_denominator=0,
                    message_passing_candidate_count=0,
                    gate_evaluated_count=0,
                ),
            )

    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = PMDMAdapterFixtureBuilder(seed=42)


# ===================================================================
# Requirement 16: no artifacts generated
# ===================================================================


class PMDMSideEffectTests(unittest.TestCase):
    """Requirement 16: no model/training/inference/evaluation artifacts."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = PMDMAdapterFixtureBuilder(seed=42)
        cls.batch = cls.builder.build_model_batch()
        cls.config = cls.builder.build_config_dict()

    # Requirement 16

    def test_16_no_artifacts_generated_by_forward_pmdm(self) -> None:
        """forward_pmdm must not create model/training/inference/evaluation
        artifacts on disk."""
        _raise_if_missing()

        with tempfile.TemporaryDirectory() as tmpdir:
            before = set(os.listdir(tmpdir))

            old_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                _forward_pmdm(
                    batch=self.batch, config=self.config, timestep=0.5
                )
            finally:
                os.chdir(old_cwd)

            after = set(os.listdir(tmpdir))
            new_files = after - before - {"__pycache__"}

            self.assertEqual(
                len(new_files),
                0,
                f"forward_pmdm must not create files; found {new_files}",
            )

    def test_16b_validate_pmdm_outputs_creates_no_artifacts(self) -> None:
        """validate_pmdm_outputs must not create artifacts on disk."""
        _raise_if_missing()

        good_outputs = self.builder.build_fake_pmdm_outputs(
            self.batch.tensors, seed=42
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            before = set(os.listdir(tmpdir))

            old_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                _validate_pmdm_outputs(
                    pmdm_outputs=good_outputs,
                    batch=self.batch,
                    config=self.config,
                )
            finally:
                os.chdir(old_cwd)

            after = set(os.listdir(tmpdir))
            new_files = after - before - {"__pycache__"}

            self.assertEqual(
                len(new_files),
                0,
                f"validate_pmdm_outputs must not create files; found {new_files}",
            )

    def test_16c_model_config_construction_creates_no_artifacts(self) -> None:
        """ModelConfig construction must not create artifacts on disk."""
        _raise_if_missing()

        with tempfile.TemporaryDirectory() as tmpdir:
            before = set(os.listdir(tmpdir))

            old_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                _ModelConfig(
                    contract_version="1.0.0",
                    rule_table_hash="sha256:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
                )
            finally:
                os.chdir(old_cwd)

            after = set(os.listdir(tmpdir))
            new_files = after - before - {"__pycache__"}

            self.assertEqual(
                len(new_files),
                0,
                f"ModelConfig construction must not create files; found {new_files}",
            )


# ===================================================================
# Additional: Task-20 placeholder verification
# ===================================================================


class Task20SmokePlaceholderTests(unittest.TestCase):
    """Verify that Task-20 fields in ModelForwardOutput are smoke placeholders,
    not real covalent head implementations."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = PMDMAdapterFixtureBuilder(seed=42)
        cls.batch = cls.builder.build_model_batch()
        cls.config = cls.builder.build_config_dict()

    def test_edge_logits_is_smoke_placeholder(self) -> None:
        _raise_if_missing()
        result = _forward_pmdm(
            batch=self.batch, config=self.config, timestep=0.5
        )
        _assert_is_smoke_placeholder(self, result.edge_logits)

    def test_bond_type_logits_is_smoke_placeholder(self) -> None:
        _raise_if_missing()
        result = _forward_pmdm(
            batch=self.batch, config=self.config, timestep=0.5
        )
        _assert_is_smoke_placeholder(self, result.bond_type_logits)

    def test_family_logits_is_smoke_placeholder(self) -> None:
        _raise_if_missing()
        result = _forward_pmdm(
            batch=self.batch, config=self.config, timestep=0.5
        )
        _assert_is_smoke_placeholder(self, result.family_logits)

    def test_edge_prob_message_weights_is_smoke_placeholder(self) -> None:
        _raise_if_missing()
        result = _forward_pmdm(
            batch=self.batch, config=self.config, timestep=0.5
        )
        _assert_is_smoke_placeholder(self, result.edge_prob_message_weights)

    def test_message_weight_source_is_detached_edge_probability(self) -> None:
        _raise_if_missing()
        result = _forward_pmdm(
            batch=self.batch, config=self.config, timestep=0.5
        )
        self.assertEqual(
            result.message_weight_source,
            MESSAGE_WEIGHT_SOURCE_DETACHED_EDGE_PROBABILITY,
        )


# ===================================================================
# Additional: validate_pmdm_outputs accepts correct outputs
# ===================================================================


class PMDMValidationSuccessTests(unittest.TestCase):
    """validate_pmdm_outputs must not raise on correct outputs."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = PMDMAdapterFixtureBuilder(seed=42)
        cls.batch = cls.builder.build_model_batch()
        cls.config = cls.builder.build_config_dict()

    def test_validate_accepts_correct_outputs(self) -> None:
        _raise_if_missing()
        outputs = self.builder.build_fake_pmdm_outputs(
            self.batch.tensors, seed=42
        )
        # Must not raise
        _validate_pmdm_outputs(
            pmdm_outputs=outputs, batch=self.batch, config=self.config,
        )

    def test_validate_accepts_outputs_with_optional_keys(self) -> None:
        _raise_if_missing()
        config = self.builder.build_config_dict(enable_optional_pair_features=True)
        outputs = self.builder.build_fake_pmdm_outputs(
            self.batch.tensors, seed=42, enable_optional=True
        )
        _validate_pmdm_outputs(
            pmdm_outputs=outputs, batch=self.batch, config=config,
        )


# ===================================================================
# Additional: ALLOWED_MESSAGE_WEIGHT_SOURCES contract
# ===================================================================


class MessageWeightSourceContractTests(unittest.TestCase):
    """Verify the message_weight_source contract constants."""

    def test_only_detached_edge_probability_is_allowed(self) -> None:
        self.assertEqual(
            ALLOWED_MESSAGE_WEIGHT_SOURCES,
            (MESSAGE_WEIGHT_SOURCE_DETACHED_EDGE_PROBABILITY,),
        )

    def test_label_not_in_allowed_sources(self) -> None:
        self.assertNotIn("label", ALLOWED_MESSAGE_WEIGHT_SOURCES)

    def test_ground_truth_not_in_allowed_sources(self) -> None:
        self.assertNotIn("ground_truth", ALLOWED_MESSAGE_WEIGHT_SOURCES)

    def test_target_edge_not_in_allowed_sources(self) -> None:
        self.assertNotIn("target_edge", ALLOWED_MESSAGE_WEIGHT_SOURCES)

    def test_empty_not_in_allowed_sources(self) -> None:
        self.assertNotIn("", ALLOWED_MESSAGE_WEIGHT_SOURCES)


# ===================================================================
# Additional: ModelForwardOutput requires_grad guard
# ===================================================================


class ModelForwardOutputDetachGuardTests(unittest.TestCase):
    """Task 19 must not subvert the anti-leakage guard in ModelForwardOutput."""

    def test_requires_grad_true_rejected(self) -> None:
        """Any tensor-like object reporting requires_grad=True must be rejected."""
        class _FakeGradTensor:
            requires_grad = True

        with self.assertRaises(ValueError):
            ModelForwardOutput(
                pmdm_outputs={"ligand_atom_features": []},
                edge_logits=SMOKE_PLACEHOLDER,
                bond_type_logits=SMOKE_PLACEHOLDER,
                family_logits=SMOKE_PLACEHOLDER,
                edge_prob_message_weights=_FakeGradTensor(),
                message_weight_source=MESSAGE_WEIGHT_SOURCE_DETACHED_EDGE_PROBABILITY,
                denominators_observed=EdgeDenominators(
                    candidate_count=0,
                    natural_candidate_count=0,
                    forced_positive_count=0,
                    eligible_edge_count=0,
                    masked_candidate_count=0,
                    edge_loss_denominator=0,
                    bond_type_loss_denominator=0,
                    geometry_loss_denominator=0,
                    message_passing_candidate_count=0,
                    gate_evaluated_count=0,
                ),
            )

    def test_requires_grad_false_accepted(self) -> None:
        """A tensor-like object with requires_grad=False is accepted."""
        class _FakeDetachedTensor:
            requires_grad = False

        output = ModelForwardOutput(
            pmdm_outputs={"ligand_atom_features": []},
            edge_logits=SMOKE_PLACEHOLDER,
            bond_type_logits=SMOKE_PLACEHOLDER,
            family_logits=SMOKE_PLACEHOLDER,
            edge_prob_message_weights=_FakeDetachedTensor(),
            message_weight_source=MESSAGE_WEIGHT_SOURCE_DETACHED_EDGE_PROBABILITY,
            denominators_observed=EdgeDenominators(
                candidate_count=0,
                natural_candidate_count=0,
                forced_positive_count=0,
                eligible_edge_count=0,
                masked_candidate_count=0,
                edge_loss_denominator=0,
                bond_type_loss_denominator=0,
                geometry_loss_denominator=0,
                message_passing_candidate_count=0,
                gate_evaluated_count=0,
            ),
        )
        self.assertIsInstance(output, ModelForwardOutput)


if __name__ == "__main__":
    unittest.main()
