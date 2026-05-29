"""Tests for Task 20 covalent heads contracts.

Covers shape-validation, message-weight provenance, anti-leakage, import
isolation, and absence-of-decode requirements from the Task 20 spec and
verification matrix.

Public API under test:
    covalent_design.model.covalent_heads.forward_covalent(
        *, pmdm_output, batch, config, num_families=None
    )

These are Task 20 contract tests.
Do not lower assertions.
"""

from __future__ import annotations

import copy
import math
import os
import sys
import tempfile
import unittest

# ===================================================================
# production imports
# ===================================================================

from covalent_design.model.covalent_heads import (
    forward_covalent as _forward_covalent,
)
from covalent_design.model.edge_message_passing import (
    apply_edge_message_weights as _apply_edge_message_weights,
)
from covalent_design.model.pmdm_adapter import SMOKE_PLACEHOLDER

# contract types (exist from Task 17/19)
from covalent_design.contracts import (
    ContractError,
    EdgeDenominators,
    ModelForwardOutput,
)
from covalent_design.contracts.types import (
    ALLOWED_MESSAGE_WEIGHT_SOURCES,
    MESSAGE_WEIGHT_SOURCE_DETACHED_EDGE_PROBABILITY,
    BatchRecordHeader,
    BatchTensors,
    ModelBatch,
)

from tests.fixtures.model.covalent_heads._builder import (
    CovalentHeadsFixtureBuilder,
    FakeTensor,
    sigmoid,
)

# ===================================================================
# helpers
# ===================================================================


def _scalar_sigmoid(x: float) -> float:
    """Element-wise sigmoid for a scalar."""
    return 1.0 / (1.0 + math.exp(-x))


def _tensor_sigmoid_values(data: list) -> list:
    """Recursively apply sigmoid to every leaf in a nested list."""
    if isinstance(data, list):
        return [_tensor_sigmoid_values(item) for item in data]
    if isinstance(data, (int, float)):
        return _scalar_sigmoid(float(data))
    raise TypeError(f"Unsupported data type: {type(data)}")


def _get_shape(obj: object) -> tuple:
    """Return nested-list shape."""
    if isinstance(obj, (int, float, type(None))):
        return ()
    if isinstance(obj, list):
        if len(obj) == 0:
            return (0,)
        inner = _get_shape(obj[0])
        return (len(obj),) + inner
    if hasattr(obj, "shape"):
        return obj.shape
    return ()


def _shapes_equal(a: tuple, b: tuple) -> bool:
    """Compare two shape tuples."""
    if len(a) != len(b):
        return False
    for x, y in zip(a, b):
        if not isinstance(x, int) or not isinstance(y, int):
            return False
        if x != y:
            return False
    return True


def _is_fake_tensor_like(obj: object) -> bool:
    """Return True if *obj* is a FakeTensor (or compatible tensor-like object)."""
    return hasattr(obj, "requires_grad") and hasattr(obj, "detach")


# ===================================================================
# Requirement 1-3: API contract -forward_covalent exists and accepts
# Task 19 handoff plus ModelBatch
# ===================================================================


class CovalentHeadsAPITests(unittest.TestCase):
    """Requirements 1-3: API existence, keyword-only signature, return contract."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = CovalentHeadsFixtureBuilder(seed=42)
        cls.batch = cls.builder.build_model_batch()
        cls.config = cls.builder.build_config()
        cls.task19_handoff = cls.builder.build_task19_handoff(cls.batch)

    # Requirement 1 -forward_covalent is callable

    def test_01_forward_covalent_is_callable(self) -> None:
        """forward_covalent must be a callable accepting keyword-only args."""
        self.assertTrue(
            callable(_forward_covalent),
            "forward_covalent must be importable and callable",
        )

    # Requirement 2 -accepts Task 19 ModelForwardOutput handoff

    def test_02_accepts_task19_handoff_as_pmdm_output(self) -> None:
        """forward_covalent must accept a ModelForwardOutput (from Task 19)
        as the pmdm_output argument."""
        self.assertIsInstance(self.task19_handoff, ModelForwardOutput)
        self.assertIsInstance(self.task19_handoff.pmdm_outputs, dict)
        self.assertIsInstance(self.batch, ModelBatch)

        result = _forward_covalent(
            pmdm_output=self.task19_handoff,
            batch=self.batch,
            config=self.config,
        )
        self.assertIsNotNone(result)

    # Requirement 3 -returns output with non-smoke-placeholder covalent fields

    def test_03_returns_output_with_non_smoke_covalent_fields(self) -> None:
        """forward_covalent must replace SMOKE_PLACEHOLDER sentinels with
        real edge_logits, bond_type_logits, family_logits, and
        edge_prob_message_weights."""
        result = _forward_covalent(
            pmdm_output=self.task19_handoff,
            batch=self.batch,
            config=self.config,
        )

        self.assertIsNotNone(result.edge_logits)
        self.assertTrue(
            hasattr(result.edge_logits, "shape") or isinstance(result.edge_logits, list),
            "edge_logits must be tensor-like",
        )
        self.assertTrue(
            hasattr(result.bond_type_logits, "shape") or isinstance(result.bond_type_logits, list),
            "bond_type_logits must be tensor-like",
        )


# ===================================================================
# Requirements 4-6: tensor shapes
# ===================================================================


class CovalentHeadsShapeTests(unittest.TestCase):
    """Requirements 4-6: edge_logits, bond_type_logits, family_logits shapes."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = CovalentHeadsFixtureBuilder(seed=42)
        cls.batch = cls.builder.build_model_batch()
        cls.config = cls.builder.build_config()
        cls.task19_handoff = cls.builder.build_task19_handoff(cls.batch)

    @property
    def B(self) -> int:
        return self.batch.tensors.protein_coords_shape[0]

    @property
    def N_candidates(self) -> int:
        return self.batch.tensors.edge_candidates_shape[1]

    @property
    def N_bond_types(self) -> int:
        vocab = self.batch.batch_spec.bond_type_vocabulary
        return len(vocab) if vocab is not None else 2

    @property
    def N_families(self) -> int:
        families = {rec.residue_reaction_family for rec in self.batch.records}
        return len(families)

    # Requirement 4 -edge_logits shape (B, N_candidates)

    def test_04_edge_logits_shape(self) -> None:
        """edge_logits must have shape (B, N_candidates)."""
        result = _forward_covalent(
            pmdm_output=self.task19_handoff,
            batch=self.batch,
            config=self.config,
        )

        shape = _get_shape(result.edge_logits)
        expected = (self.B, self.N_candidates)
        self.assertTrue(
            _shapes_equal(shape, expected),
            f"edge_logits shape {shape} != expected {expected}",
        )

    # Requirement 5 -bond_type_logits shape (B, N_candidates, N_bond_types)

    def test_05_bond_type_logits_shape(self) -> None:
        """bond_type_logits must have shape (B, N_candidates, N_bond_types)."""
        result = _forward_covalent(
            pmdm_output=self.task19_handoff,
            batch=self.batch,
            config=self.config,
        )

        shape = _get_shape(result.bond_type_logits)
        expected = (self.B, self.N_candidates, self.N_bond_types)
        self.assertTrue(
            _shapes_equal(shape, expected),
            f"bond_type_logits shape {shape} != expected {expected}",
        )

    # Requirement 6 -family_logits shape (B, N_families)

    def test_06_family_logits_shape(self) -> None:
        """family_logits must have shape (B, N_families)."""
        result = _forward_covalent(
            pmdm_output=self.task19_handoff,
            batch=self.batch,
            config=self.config,
        )

        shape = _get_shape(result.family_logits)
        expected = (self.B, self.N_families)
        self.assertTrue(
            _shapes_equal(shape, expected),
            f"family_logits shape {shape} != expected {expected}",
        )

    def test_06b_family_logits_num_families_override(self) -> None:
        """When num_families is explicit, family_logits must use that count."""
        explicit_num = 3
        result = _forward_covalent(
            pmdm_output=self.task19_handoff,
            batch=self.batch,
            config=self.config,
            num_families=explicit_num,
        )

        shape = _get_shape(result.family_logits)
        expected = (self.B, explicit_num)
        self.assertTrue(
            _shapes_equal(shape, expected),
            f"family_logits shape {shape} != expected {expected} "
            f"with num_families={explicit_num}",
        )


# ===================================================================
# Requirements 7-9: message-weight provenance
# ===================================================================


class CovalentHeadsMessageWeightProvenanceTests(unittest.TestCase):
    """Requirements 7-9: edge_prob_message_weights must equal
    sigmoid(edge_logits).detach()."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = CovalentHeadsFixtureBuilder(seed=42)
        cls.batch = cls.builder.build_model_batch()
        cls.config = cls.builder.build_config()
        cls.task19_handoff = cls.builder.build_task19_handoff(cls.batch)

    # Requirement 7 -values match sigmoid of edge_logits

    def test_07_message_weights_equal_sigmoid_detach_of_edge_logits(self) -> None:
        """edge_prob_message_weights values must equal sigmoid(edge_logits)
        followed by detach()."""
        result = _forward_covalent(
            pmdm_output=self.task19_handoff,
            batch=self.batch,
            config=self.config,
        )

        edge_logits = result.edge_logits
        message_weights = result.edge_prob_message_weights

        # Compute expected: sigmoid(edge_logits).detach()
        if _is_fake_tensor_like(edge_logits):
            expected = edge_logits.sigmoid().detach()
        else:
            sigmoid_data = _tensor_sigmoid_values(edge_logits)
            expected = FakeTensor(sigmoid_data, requires_grad=False)

        # Verify values match
        if _is_fake_tensor_like(message_weights) and _is_fake_tensor_like(expected):
            self.assertEqual(
                message_weights.data,
                expected.data,
                "edge_prob_message_weights values must equal sigmoid(edge_logits)",
            )
        else:
            self.assertEqual(
                message_weights,
                expected,
                "edge_prob_message_weights must equal sigmoid(edge_logits).detach()",
            )

    # Requirement 8 -message_weight_source is the correct constant

    def test_08_message_weight_source_is_detached_edge_probability(self) -> None:
        """message_weight_source must be 'detached_edge_probability'."""
        result = _forward_covalent(
            pmdm_output=self.task19_handoff,
            batch=self.batch,
            config=self.config,
        )

        self.assertEqual(
            result.message_weight_source,
            MESSAGE_WEIGHT_SOURCE_DETACHED_EDGE_PROBABILITY,
            "message_weight_source must prove the weights came from "
            "model predictions, not labels or ground truth",
        )

    # Requirement 9 -message weights must be detached

    def test_09_message_weights_requires_grad_is_false(self) -> None:
        """edge_prob_message_weights must have requires_grad=False."""
        result = _forward_covalent(
            pmdm_output=self.task19_handoff,
            batch=self.batch,
            config=self.config,
        )

        message_weights = result.edge_prob_message_weights

        if _is_fake_tensor_like(message_weights):
            self.assertFalse(
                message_weights.requires_grad,
                "edge_prob_message_weights must be detached "
                "(requires_grad=False)",
            )
        else:
            # For non-tensor-like objects (e.g. lists), the check is that
            # they don't expose requires_grad at all, meaning no gradient tracking
            self.assertFalse(
                hasattr(message_weights, "requires_grad")
                and message_weights.requires_grad,
                "edge_prob_message_weights must not carry gradient state",
            )


# ===================================================================
# Requirements 10-13: anti-leakage -requires_grad=False alone isn't enough
# ===================================================================


class CovalentHeadsAntiLeakageTests(unittest.TestCase):
    """Requirements 10-13: provenance beyond requires_grad=False.

    A tensor with requires_grad=False is NOT sufficient proof that
    message weights came from model predictions. Values must equal
    sigmoid(edge_logits). Label/ground_truth/target_edge sources
    must be rejected.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = CovalentHeadsFixtureBuilder(seed=42)
        cls.batch = cls.builder.build_model_batch()
        cls.config = cls.builder.build_config()

    # Requirement 10 -SMOKE_PLACEHOLDER fields are replaced with real tensors

    def test_10_smoke_placeholder_fields_are_replaced(self) -> None:
        """forward_covalent must replace SMOKE_PLACEHOLDER sentinels in the
        Task 19 handoff with real tensor outputs. It must not return
        SMOKE_PLACEHOLDER as edge_logits, bond_type_logits, family_logits,
        or edge_prob_message_weights."""
        from covalent_design.model.pmdm_adapter import SMOKE_PLACEHOLDER

        # Verify the Task 19 handoff still has smoke placeholders
        # (this is pre-condition -Task 19 provides smoke)
        pmdm_output = self.builder.build_task19_handoff(self.batch)
        self.assertIs(pmdm_output.edge_logits, SMOKE_PLACEHOLDER,
                       "Pre-condition: Task 19 handoff must have SMOKE_PLACEHOLDER edge_logits")

        result = _forward_covalent(
            pmdm_output=pmdm_output,
            batch=self.batch,
            config=self.config,
        )

        # After Task 20, none of the covalent fields may be smoke placeholders
        self.assertIsNot(result.edge_logits, SMOKE_PLACEHOLDER,
                          "edge_logits must not be SMOKE_PLACEHOLDER after Task 20")
        self.assertIsNot(result.bond_type_logits, SMOKE_PLACEHOLDER,
                          "bond_type_logits must not be SMOKE_PLACEHOLDER after Task 20")
        self.assertIsNot(result.family_logits, SMOKE_PLACEHOLDER,
                          "family_logits must not be SMOKE_PLACEHOLDER after Task 20")
        self.assertIsNot(result.edge_prob_message_weights, SMOKE_PLACEHOLDER,
                          "edge_prob_message_weights must not be SMOKE_PLACEHOLDER after Task 20")

    # Requirement 11 -requires_grad=False alone is insufficient

    def test_11_requires_grad_false_alone_is_insufficient(self) -> None:
        """A tensor with requires_grad=False but values != sigmoid(edge_logits)
        must be rejected by provenance tests.

        This test creates message weights where requires_grad=False but the
        values are all 1.0 -not derivable from sigmoid of any reasonable
        edge_logits tensor. The forward_covalent function must either
        compute message weights from edge_logits itself or validate that
        provided weights match sigmoid(edge_logits).detach().
        """
        pmdm_output = self.builder.build_model_forward_output(self.batch)

        # Compute the true message weights (sigmoid of edge_logits)
        edge_logits = self.builder.build_edge_logits(self.batch, requires_grad=True)
        true_weights = edge_logits.sigmoid().detach()

        # forged_weights has requires_grad=False but wrong values (all ones)
        B = self.batch.tensors.protein_coords_shape[0]
        N = self.batch.tensors.edge_candidates_shape[1]
        forged_weights = FakeTensor(
            [[1.0 for _ in range(N)] for _ in range(B)],
            requires_grad=False,
        )

        # The forged weights have requires_grad=False ... that alone is not enough
        self.assertFalse(forged_weights.requires_grad)
        self.assertNotEqual(
            forged_weights.data,
            true_weights.data,
            "Forged weights must differ from true sigmoid values "
            "for this test to be meaningful",
        )

        # If forward_covalent accepts externally-provided message weights,
        # it must reject those that don't match sigmoid(edge_logits).
        # If it computes them internally, this test passes automatically
        # because the forged weights are never used.
        #
        # The key assertion: the output's edge_prob_message_weights
        # MUST NOT equal the forged values.
        result = _forward_covalent(
            pmdm_output=pmdm_output,
            batch=self.batch,
            config=self.config,
        )

        msg_weights = result.edge_prob_message_weights
        if _is_fake_tensor_like(msg_weights):
            actual_data = msg_weights.data
        else:
            actual_data = msg_weights

        self.assertNotEqual(
            actual_data,
            forged_weights.data,
            "Output message weights must not equal forged label values; "
            "requires_grad=False alone is insufficient provenance",
        )

    # Requirement 12 -label/ground_truth/target_edge source values rejected

    def test_12_label_ground_truth_target_edge_source_rejected(self) -> None:
        """ModelForwardOutput construction must reject message_weight_source
        values 'label', 'ground_truth', and 'target_edge' even when the
        tensor carries requires_grad=False."""
        invalid_sources = ("label", "ground_truth", "target_edge")

        from covalent_design.contracts.types import EdgeDenominators

        for source in invalid_sources:
            with self.subTest(source=source):
                with self.assertRaises(
                    ValueError,
                    msg=f"message_weight_source '{source}' must be rejected",
                ):
                    ModelForwardOutput(
                        pmdm_outputs={"ligand_atom_features": []},
                        edge_logits=FakeTensor([[0.0]], requires_grad=True),
                        bond_type_logits=FakeTensor([[[0.0]]], requires_grad=True),
                        family_logits=FakeTensor([[0.0]], requires_grad=True),
                        edge_prob_message_weights=FakeTensor(
                            [[0.5]], requires_grad=False
                        ),
                        message_weight_source=source,
                        denominators_observed=EdgeDenominators(
                            candidate_count=1,
                            natural_candidate_count=1,
                            forced_positive_count=0,
                            eligible_edge_count=1,
                            masked_candidate_count=0,
                            edge_loss_denominator=1,
                            bond_type_loss_denominator=1,
                            geometry_loss_denominator=1,
                            message_passing_candidate_count=1,
                            gate_evaluated_count=1,
                        ),
                    )

    # Requirement 13 -requires_grad=True message weights rejected

    def test_13_requires_grad_true_message_weights_rejected(self) -> None:
        """edge_prob_message_weights with requires_grad=True must be
        rejected by ModelForwardOutput.__post_init__."""
        grad_tensor = FakeTensor([[0.5]], requires_grad=True)
        self.assertTrue(grad_tensor.requires_grad)

        from covalent_design.contracts.types import EdgeDenominators

        with self.assertRaises(
            ValueError,
            msg="edge_prob_message_weights with requires_grad=True must be rejected",
        ):
            ModelForwardOutput(
                pmdm_outputs={"ligand_atom_features": []},
                edge_logits=FakeTensor([[0.0]], requires_grad=True),
                bond_type_logits=FakeTensor([[[0.0]]], requires_grad=True),
                family_logits=FakeTensor([[0.0]], requires_grad=True),
                edge_prob_message_weights=grad_tensor,
                message_weight_source=MESSAGE_WEIGHT_SOURCE_DETACHED_EDGE_PROBABILITY,
                denominators_observed=EdgeDenominators(
                    candidate_count=1,
                    natural_candidate_count=1,
                    forced_positive_count=0,
                    eligible_edge_count=1,
                    masked_candidate_count=0,
                    edge_loss_denominator=1,
                    bond_type_loss_denominator=1,
                    geometry_loss_denominator=1,
                    message_passing_candidate_count=1,
                    gate_evaluated_count=1,
                ),
            )


# ===================================================================
# Requirements 14-16: import isolation -no torch, PMDM, PocketFlow
# ===================================================================


class CovalentHeadsImportIsolationTests(unittest.TestCase):
    """Requirements 14-16: covalent_heads module must not import torch,
    PMDM, PocketFlow, or Task 21 decode modules."""

    # Requirement 14 -no torch import

    def test_14_no_torch_import(self) -> None:
        """Importing covalent_heads must not pull in torch."""
        pre_modules = set(sys.modules.keys())

        mod_to_reload = "covalent_design.model.covalent_heads"
        for mod_name in list(sys.modules.keys()):
            if mod_name == mod_to_reload or mod_name.startswith(mod_to_reload + "."):
                del sys.modules[mod_name]

        from covalent_design.model import covalent_heads  # noqa: F401

        post_modules = set(sys.modules.keys())
        new_modules = post_modules - pre_modules

        torch_variants = {"torch", "torch.nn", "torch.nn.functional"}
        violations = [m for m in new_modules if m in torch_variants
                      or m.startswith("torch.")]
        self.assertEqual(
            violations,
            [],
            f"covalent_heads imported torch: {violations}",
        )

    # Requirement 15 -no PMDM / PocketFlow

    def test_15_no_pmdm_or_pocketflow_import(self) -> None:
        """Importing covalent_heads must not pull in PMDM or PocketFlow."""
        pre_modules = set(sys.modules.keys())

        mod_to_reload = "covalent_design.model.covalent_heads"
        for mod_name in list(sys.modules.keys()):
            if mod_name == mod_to_reload or mod_name.startswith(mod_to_reload + "."):
                del sys.modules[mod_name]

        from covalent_design.model import covalent_heads  # noqa: F401

        post_modules = set(sys.modules.keys())
        new_modules = post_modules - pre_modules

        forbidden = {"pmdm", "pocketflow"}
        violations = []
        for mod in new_modules:
            lower = mod.lower()
            for prefix in forbidden:
                if lower.startswith(prefix) or f".{prefix}" in lower:
                    violations.append(mod)
                    break

        self.assertEqual(
            violations,
            [],
            f"covalent_heads imported PMDM/PocketFlow: {violations}",
        )

    # Requirement 16 -no Task 21 decode or loss modules

    def test_16_no_task21_decode_or_training_modules_imported(self) -> None:
        """Importing covalent_heads must not pull in Task 21 decode or
        training modules (final_decode, validity_gate, loss, train step)."""
        pre_modules = set(sys.modules.keys())

        mod_to_reload = "covalent_design.model.covalent_heads"
        for mod_name in list(sys.modules.keys()):
            if mod_name == mod_to_reload or mod_name.startswith(mod_to_reload + "."):
                del sys.modules[mod_name]

        from covalent_design.model import covalent_heads  # noqa: F401

        post_modules = set(sys.modules.keys())
        new_modules = post_modules - pre_modules

        task21_and_beyond = {
            "covalent_design.model.final_decode",
            "covalent_design.model.validity_gate",
            "covalent_design.model.geometry_features",
            "covalent_design.training",
        }

        violations = [m for m in new_modules
                      if m in task21_and_beyond
                      or m.startswith("covalent_design.training.")]
        self.assertEqual(
            violations,
            [],
            f"covalent_heads must not import Task 21+ modules: {violations}",
        )


# ===================================================================
# Requirements 17-18: no decode, no loss computation
# ===================================================================


class CovalentHeadsNoDecodeOrLossTests(unittest.TestCase):
    """Requirements 17-18: covalent_heads must not expose decode, loss
    computation, or training artifacts."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = CovalentHeadsFixtureBuilder(seed=42)
        cls.batch = cls.builder.build_model_batch()
        cls.config = cls.builder.build_config()
        cls.task19_handoff = cls.builder.build_task19_handoff(cls.batch)

    # Requirement 17 -no decode symbols in covalent_heads

    def test_17_no_decode_symbols_exported(self) -> None:
        """covalent_design.model.covalent_heads must not export decode,
        validity-gate, or hard-edge-selection symbols."""
        import covalent_design.model.covalent_heads as ch

        forbidden_attrs = {
            "decode",
            "final_decode",
            "select_final_edge",
            "apply_validity_gate",
            "hard_edge_selection",
            "FinalDecodeResult",
            "EdgeValidityCheck",
            "select_covalent_edge",
            "reject_all_candidates",
        }
        exported = set(dir(ch))
        overlap = forbidden_attrs & exported
        self.assertEqual(
            overlap,
            set(),
            f"covalent_heads must not export decode symbols: {overlap}",
        )

    # Requirement 18 -no loss computation symbols

    def test_18_no_loss_computation_symbols_exported(self) -> None:
        """covalent_design.model.covalent_heads must not export loss
        computation symbols."""
        import covalent_design.model.covalent_heads as ch

        forbidden_attrs = {
            "compute_loss",
            "compute_edge_loss",
            "compute_bond_type_loss",
            "compute_geometry_loss",
            "compute_family_loss",
            "LossReport",
            "MaskAudit",
            "total_loss",
            "loss_components",
            "backward",
            "loss_fn",
            "criterion",
        }
        exported = set(dir(ch))
        overlap = forbidden_attrs & exported
        self.assertEqual(
            overlap,
            set(),
            f"covalent_heads must not export loss symbols: {overlap}",
        )


# ===================================================================
# Requirement 19: no artifacts generated by forward_covalent
# ===================================================================


class CovalentHeadsSideEffectTests(unittest.TestCase):
    """Requirement 19: forward_covalent must not create model/training/
    inference/evaluation artifacts on disk."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = CovalentHeadsFixtureBuilder(seed=42)
        cls.batch = cls.builder.build_model_batch()
        cls.config = cls.builder.build_config()
        cls.task19_handoff = cls.builder.build_task19_handoff(cls.batch)

    def test_19_no_artifacts_generated_by_forward_covalent(self) -> None:
        """forward_covalent must not create files on disk."""
        with tempfile.TemporaryDirectory() as tmpdir:
            before = set(os.listdir(tmpdir))

            old_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                _forward_covalent(
                    pmdm_output=self.task19_handoff,
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
                f"forward_covalent must not create files; found {new_files}",
            )


class CovalentHeadsDeterminismTests(unittest.TestCase):
    """Forward outputs are deterministic for a fixed config seed."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = CovalentHeadsFixtureBuilder(seed=42)
        cls.batch = cls.builder.build_model_batch()
        cls.config = cls.builder.build_config()
        cls.task19_handoff = cls.builder.build_task19_handoff(cls.batch)

    def test_19b_same_seed_produces_identical_logits(self) -> None:
        first = _forward_covalent(
            pmdm_output=self.task19_handoff,
            batch=self.batch,
            config=self.config,
        )
        second = _forward_covalent(
            pmdm_output=self.task19_handoff,
            batch=self.batch,
            config=self.config,
        )

        self.assertEqual(first.edge_logits.data, second.edge_logits.data)
        self.assertEqual(first.bond_type_logits.data, second.bond_type_logits.data)
        self.assertEqual(first.family_logits.data, second.family_logits.data)
        self.assertEqual(
            first.edge_prob_message_weights.data,
            second.edge_prob_message_weights.data,
        )

    def test_19c_different_seed_changes_logits(self) -> None:
        other_config = CovalentHeadsFixtureBuilder(seed=99).build_config()
        first = _forward_covalent(
            pmdm_output=self.task19_handoff,
            batch=self.batch,
            config=self.config,
        )
        second = _forward_covalent(
            pmdm_output=self.task19_handoff,
            batch=self.batch,
            config=other_config,
        )

        self.assertNotEqual(first.edge_logits.data, second.edge_logits.data)

    def test_19d_pmdm_outputs_are_not_mutated(self) -> None:
        before = copy.deepcopy(self.task19_handoff.pmdm_outputs)
        _forward_covalent(
            pmdm_output=self.task19_handoff,
            batch=self.batch,
            config=self.config,
        )
        self.assertEqual(before, self.task19_handoff.pmdm_outputs)


# ===================================================================
# Requirements 20-21: sigmoid utility correctness
# ===================================================================


class SigmoidUtilityTests(unittest.TestCase):
    """Requirements 20-21: the sigmoid helper computes correct values."""

    def test_20_sigmoid_of_zero_is_half(self) -> None:
        """sigmoid(0.0) must equal 0.5."""
        result = _scalar_sigmoid(0.0)
        self.assertAlmostEqual(result, 0.5, places=10)

    def test_20b_sigmoid_is_monotonic(self) -> None:
        """sigmoid must be monotonically increasing."""
        values = [-5.0, -2.0, -1.0, 0.0, 1.0, 2.0, 5.0]
        sig_values = [_scalar_sigmoid(v) for v in values]
        for i in range(len(sig_values) - 1):
            self.assertLess(
                sig_values[i], sig_values[i + 1],
                f"sigmoid({values[i]}) = {sig_values[i]} >= "
                f"sigmoid({values[i+1]}) = {sig_values[i+1]}",
            )

    def test_20c_sigmoid_approaches_zero_and_one(self) -> None:
        """sigmoid(-large) ~ 0, sigmoid(+large) ~ 1."""
        self.assertLess(_scalar_sigmoid(-20.0), 1e-8)
        self.assertGreater(_scalar_sigmoid(20.0), 0.99999999)

    def test_21_fake_tensor_sigmoid_preserves_requires_grad(self) -> None:
        """FakeTensor.sigmoid() preserves requires_grad."""
        t = FakeTensor([[0.0, 1.0], [-1.0, 2.0]], requires_grad=True)
        self.assertTrue(t.requires_grad)
        st = t.sigmoid()
        self.assertTrue(st.requires_grad)
        self.assertNotEqual(st.data, t.data)

    def test_21b_fake_tensor_detach_strips_requires_grad(self) -> None:
        """FakeTensor.detach() sets requires_grad=False."""
        t = FakeTensor([[0.0]], requires_grad=True)
        dt = t.detach()
        self.assertFalse(dt.requires_grad)
        self.assertEqual(dt.data, t.data)

    def test_21c_sigmoid_detach_pipeline(self) -> None:
        """Full sigmoid.detach pipeline on FakeTensor."""
        t = FakeTensor([[0.0, 1.0], [-1.0, 2.0]], requires_grad=True)
        weights = t.sigmoid().detach()
        self.assertFalse(weights.requires_grad)

        expected = [
            [_scalar_sigmoid(v) for v in row]
            for row in [[0.0, 1.0], [-1.0, 2.0]]
        ]
        for i in range(len(expected)):
            for j in range(len(expected[i])):
                self.assertAlmostEqual(
                    weights.data[i][j], expected[i][j], places=10,
                )


# ===================================================================
# Requirement 22: ALLOWED_MESSAGE_WEIGHT_SOURCES contract
# ===================================================================


class MessageWeightSourcesContractTests(unittest.TestCase):
    """Requirement 22: only 'detached_edge_probability' is allowed."""

    def test_22_only_detached_edge_probability_is_allowed(self) -> None:
        """ALLOWED_MESSAGE_WEIGHT_SOURCES must contain exactly one value."""
        self.assertEqual(
            ALLOWED_MESSAGE_WEIGHT_SOURCES,
            (MESSAGE_WEIGHT_SOURCE_DETACHED_EDGE_PROBABILITY,),
        )

    def test_22b_label_not_allowed(self) -> None:
        self.assertNotIn("label", ALLOWED_MESSAGE_WEIGHT_SOURCES)

    def test_22c_ground_truth_not_allowed(self) -> None:
        self.assertNotIn("ground_truth", ALLOWED_MESSAGE_WEIGHT_SOURCES)

    def test_22d_target_edge_not_allowed(self) -> None:
        self.assertNotIn("target_edge", ALLOWED_MESSAGE_WEIGHT_SOURCES)

    def test_22e_empty_not_allowed(self) -> None:
        self.assertNotIn("", ALLOWED_MESSAGE_WEIGHT_SOURCES)


class EdgeMessagePassingBoundaryTests(unittest.TestCase):
    """Edge message passing accepts only detached prediction weights."""

    def test_25_accepts_detached_prediction_weights(self) -> None:
        weights = FakeTensor([[0.25, 0.75]], requires_grad=False)
        result = _apply_edge_message_weights(
            message_weights=weights,
            source=MESSAGE_WEIGHT_SOURCE_DETACHED_EDGE_PROBABILITY,
        )
        self.assertIs(result, weights)

    def test_26_rejects_requires_grad_true_weights(self) -> None:
        weights = FakeTensor([[0.25, 0.75]], requires_grad=True)
        with self.assertRaises(ValueError):
            _apply_edge_message_weights(
                message_weights=weights,
                source=MESSAGE_WEIGHT_SOURCE_DETACHED_EDGE_PROBABILITY,
            )

    def test_27_rejects_label_ground_truth_and_target_edge_sources(self) -> None:
        weights = FakeTensor([[0.25, 0.75]], requires_grad=False)
        for source in ("label", "ground_truth", "target_edge", "", "unknown"):
            with self.subTest(source=source):
                with self.assertRaises(ValueError):
                    _apply_edge_message_weights(
                        message_weights=weights,
                        source=source,
                    )

    def test_28_rejects_smoke_placeholder_as_message_weights(self) -> None:
        with self.assertRaises(ValueError):
            _apply_edge_message_weights(
                message_weights=SMOKE_PLACEHOLDER,
                source=MESSAGE_WEIGHT_SOURCE_DETACHED_EDGE_PROBABILITY,
            )


# ===================================================================
# Requirement 23: forward_covalent accepts num_families=None
# ===================================================================


class CovalentHeadsNumFamiliesTests(unittest.TestCase):
    """Requirement 23: num_families=None auto-detects from batch records."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = CovalentHeadsFixtureBuilder(seed=42)
        cls.batch = cls.builder.build_model_batch()
        cls.config = cls.builder.build_config()
        cls.task19_handoff = cls.builder.build_task19_handoff(cls.batch)

    def test_23_num_families_none_uses_default_from_batch(self) -> None:
        """When num_families is None, the family count must come from the
        batch records' residue_reaction_family values."""
        result = _forward_covalent(
            pmdm_output=self.task19_handoff,
            batch=self.batch,
            config=self.config,
            num_families=None,
        )

        families_in_batch = {
            rec.residue_reaction_family for rec in self.batch.records
        }
        shape = _get_shape(result.family_logits)
        self.assertEqual(
            shape[1],
            len(families_in_batch),
            f"family_logits must have {len(families_in_batch)} families "
            f"from batch records, got shape {shape}",
        )

    def test_23b_num_families_explicit_overrides_batch(self) -> None:
        """Explicit num_families must override auto-detection."""
        explicit = 5
        result = _forward_covalent(
            pmdm_output=self.task19_handoff,
            batch=self.batch,
            config=self.config,
            num_families=explicit,
        )
        shape = _get_shape(result.family_logits)
        self.assertEqual(
            shape[1],
            explicit,
            f"family_logits shape[1] {shape[1]} != explicit {explicit}",
        )


# ===================================================================
# Requirement 24: ModelBatch records retained in output
# ===================================================================


class CovalentHeadsBatchPreservationTests(unittest.TestCase):
    """Requirement 24: output must carry batch record metadata for provenance."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = CovalentHeadsFixtureBuilder(seed=42)
        cls.batch = cls.builder.build_model_batch()
        cls.config = cls.builder.build_config()
        cls.task19_handoff = cls.builder.build_task19_handoff(cls.batch)

    def test_24_denominators_observed_is_present(self) -> None:
        """Output must include denominators_observed."""
        result = _forward_covalent(
            pmdm_output=self.task19_handoff,
            batch=self.batch,
            config=self.config,
        )

        self.assertIsNotNone(result.denominators_observed)
        self.assertIsInstance(result.denominators_observed, EdgeDenominators)

    def test_24b_pmdm_outputs_propagated(self) -> None:
        """pmdm_outputs dict must be present in the output."""
        result = _forward_covalent(
            pmdm_output=self.task19_handoff,
            batch=self.batch,
            config=self.config,
        )

        self.assertIsNotNone(result.pmdm_outputs)
        self.assertIsInstance(result.pmdm_outputs, dict)


if __name__ == "__main__":
    unittest.main()
