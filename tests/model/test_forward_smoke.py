"""Task 24 forward smoke contract tests.

These tests define the public API and boundary contracts for the forward
smoke CLI (``covalent_design.model.forward_smoke``) and validate that the
Task 17-20 forward pipeline produces deterministic, contract-conformant shapes.

Coverage:
4. Forward smoke deterministic PMDM+covalent shape summary
6. CPU/fake-backbone only; no torch/RDKit/PMDM/PocketFlow imports
"""
from __future__ import annotations

import json
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

# ---------------------------------------------------------------------------
# contracts — always importable
# ---------------------------------------------------------------------------
from covalent_design.contracts.types import (
    BatchTensors,
    LossWeights,
    ModelBatch,
    ModelForwardOutput,
)

# ---------------------------------------------------------------------------
# existing model infrastructure
# ---------------------------------------------------------------------------
from covalent_design.model.config import ModelConfig
from covalent_design.model.pmdm_adapter import forward_pmdm, SMOKE_PLACEHOLDER
from covalent_design.model.covalent_heads import forward_covalent
from covalent_design.model.candidate_builder import (
    build_stepwise_candidate_batch,
    build_stepwise_candidates,
)
from covalent_design.model.batch import make_model_batch

# ---------------------------------------------------------------------------
# fixture builders
# ---------------------------------------------------------------------------
from tests.fixtures.model._builder import ModelBatchFixtureBuilder
from tests.fixtures.model.covalent_heads._builder import CovalentHeadsFixtureBuilder
from tests.fixtures.model.stepwise_candidates._builder import (
    StepwiseCandidateFixtureBuilder,
)
from tests.fixtures.training.smoke._builder import SmokeFixtureBuilder


# ===================================================================
# helpers
# ===================================================================


def _assert_importable(module_name: str, attribute: str) -> None:
    __import__(module_name)
    getattr(sys.modules[module_name], attribute)


_batch_builder = ModelBatchFixtureBuilder()
_heads_builder = CovalentHeadsFixtureBuilder(seed=42)
_stepwise_builder = StepwiseCandidateFixtureBuilder()
_smoke_builder = SmokeFixtureBuilder()


def _artifact_path(uri: str) -> Path:
    roots = (
        Path(__file__).resolve().parents[1] / "fixtures" / "model",
        Path(__file__).resolve().parents[1] / "fixtures" / "training" / "smoke",
        Path(__file__).resolve().parents[2],
    )
    for root in roots:
        candidate = (root / uri).resolve()
        if candidate.exists():
            return candidate
    return (roots[0] / uri).resolve()


def _edge_artifact(uri: str) -> dict:
    artifact = json.loads(_artifact_path(uri).read_text("utf-8"))
    positive = artifact["positive_edge"]
    positive.setdefault("ligand_atom_index", 1)
    positive.setdefault("bond_type", "carbon-sulfur")
    positive.setdefault(
        "target_atom",
        {
            "atom_index": 5,
            "atom_name": "SG",
            "atom_serial": 6,
            "chain_id": "A",
            "residue_number": 42,
            "residue_name": "CYS",
        },
    )
    return artifact


# ===================================================================
# 1.  Forward smoke CLI contract (RED)
# ===================================================================


class ForwardSmokeCLIContractTests(unittest.TestCase):
    """Forward smoke CLI boundary tests.

    These tests are expected to RED because
    ``covalent_design.model.forward_smoke`` does not exist yet.
    """

    def test_forward_smoke_cli_is_importable(self) -> None:
        """python -m covalent_design.model.forward_smoke must be importable."""
        _assert_importable("covalent_design.model.forward_smoke", "main")

    def test_forward_smoke_cli_produces_deterministic_json_summary(self) -> None:
        """The forward smoke CLI must produce a deterministic JSON shape summary.

        Repeated runs must produce byte-identical JSON.
        """
        from covalent_design.model.forward_smoke import main

        _smoke_builder.write_smoke_train_bundle()
        config_path = (
            Path(__file__).resolve().parents[2]
            / "configs"
            / "covalent_model_smoke.yml"
        )
        rows: list[str] = []
        for _ in range(2):
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                main(["--config", str(config_path)])
            rows.append(buffer.getvalue())
        self.assertEqual(rows[0], rows[1])
        summary = json.loads(rows[0])
        self.assertIn("pmdm_shapes", summary)
        self.assertIn("covalent_shapes", summary)


# ===================================================================
# 2.  Forward pipeline shape summary (existing infrastructure)
# ===================================================================


class ForwardPipelineShapeSummaryTests(unittest.TestCase):
    """Verify deterministic shapes through the Task 17-20 forward pipeline.

    These tests use existing infrastructure and should PASS.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.batch = _heads_builder.build_model_batch()
        cls.config = _heads_builder.build_config()
        cls.stepwise = _stepwise_builder

    def _build_dynamic_batch_for_record0(self):
        """Build a singleton dynamic candidate batch from the first batch record."""
        record = self.batch.records[0]
        edge_uri = self.batch.static_edge_candidates_refs[record.record_id].uri
        edge_artifact = _edge_artifact(edge_uri)

        for ref in record.artifact_refs.values():
            if ref.role == "protein_atom_table":
                prot_path = _artifact_path(ref.uri)
                break
        else:
            self.fail("protein_atom_table not found")
        protein_atoms = json.loads(prot_path.read_text("utf-8"))["atoms"]

        for ref in record.artifact_refs.values():
            if ref.role == "ligand_atom_table":
                lig_path = _artifact_path(ref.uri)
                break
        else:
            self.fail("ligand_atom_table not found")
        ligand_atoms = json.loads(lig_path.read_text("utf-8"))["atoms"]

        candidate_set = build_stepwise_candidates(
            protein_atoms=protein_atoms,
            ligand_atoms=ligand_atoms,
            edge_candidates_artifact=edge_artifact,
            timestep_index=0,
            timestep_value=0.5,
        )
        return build_stepwise_candidate_batch(
            tuple(candidate_set for _ in self.batch.records)
        )

    # -- shape contract tests --------------------------------------------

    def test_edge_logits_shape_is_b_by_n_candidates(self) -> None:
        """edge_logits must have shape (B, N_candidates)."""
        dynamic_batch = self._build_dynamic_batch_for_record0()
        pmdm_output = forward_pmdm(batch=self.batch, config=self.config)
        output = forward_covalent(
            pmdm_output=pmdm_output,
            batch=self.batch,
            config=self.config,
            stepwise_candidate_batch=dynamic_batch,
        )
        self.assertEqual(len(output.edge_logits.shape), 2)
        self.assertEqual(
            output.edge_logits.shape,
            dynamic_batch.padded_shape,
        )

    def test_bond_type_logits_shape_is_b_by_n_candidates_by_n_bond_types(self) -> None:
        """bond_type_logits must have shape (B, N_candidates, N_bond_types)."""
        dynamic_batch = self._build_dynamic_batch_for_record0()
        pmdm_output = forward_pmdm(batch=self.batch, config=self.config)
        output = forward_covalent(
            pmdm_output=pmdm_output,
            batch=self.batch,
            config=self.config,
            stepwise_candidate_batch=dynamic_batch,
        )
        self.assertEqual(len(output.bond_type_logits.shape), 3)
        B = output.bond_type_logits.shape[0]
        N_cand = output.bond_type_logits.shape[1]
        self.assertEqual(B, len(self.batch.records))
        self.assertEqual(N_cand, dynamic_batch.padded_shape[1])

    def test_family_logits_shape_is_b_by_n_families(self) -> None:
        """family_logits must have shape (B, N_families)."""
        dynamic_batch = self._build_dynamic_batch_for_record0()
        pmdm_output = forward_pmdm(batch=self.batch, config=self.config)
        output = forward_covalent(
            pmdm_output=pmdm_output,
            batch=self.batch,
            config=self.config,
            stepwise_candidate_batch=dynamic_batch,
        )
        self.assertEqual(len(output.family_logits.shape), 2)
        self.assertEqual(output.family_logits.shape[0], len(self.batch.records))
        self.assertGreater(output.family_logits.shape[1], 0)

    def test_edge_prob_message_weights_shape_matches_edge_logits(self) -> None:
        """Message weights must match edge_logits shape: (B, N_candidates)."""
        dynamic_batch = self._build_dynamic_batch_for_record0()
        pmdm_output = forward_pmdm(batch=self.batch, config=self.config)
        output = forward_covalent(
            pmdm_output=pmdm_output,
            batch=self.batch,
            config=self.config,
            stepwise_candidate_batch=dynamic_batch,
        )
        self.assertEqual(
            output.edge_prob_message_weights.shape,
            output.edge_logits.shape,
        )

    def test_message_weights_are_detached(self) -> None:
        """edge_prob_message_weights must have requires_grad=False."""
        dynamic_batch = self._build_dynamic_batch_for_record0()
        pmdm_output = forward_pmdm(batch=self.batch, config=self.config)
        output = forward_covalent(
            pmdm_output=pmdm_output,
            batch=self.batch,
            config=self.config,
            stepwise_candidate_batch=dynamic_batch,
        )
        self.assertFalse(
            output.edge_prob_message_weights.requires_grad,
            "message weights must be detached",
        )

    def test_message_weight_source_is_detached_edge_probability(self) -> None:
        """message_weight_source must be 'detached_edge_probability'."""
        dynamic_batch = self._build_dynamic_batch_for_record0()
        pmdm_output = forward_pmdm(batch=self.batch, config=self.config)
        output = forward_covalent(
            pmdm_output=pmdm_output,
            batch=self.batch,
            config=self.config,
            stepwise_candidate_batch=dynamic_batch,
        )
        self.assertEqual(
            output.message_weight_source,
            "detached_edge_probability",
        )

    def test_denominators_observed_matches_dynamic_batch_denominators(self) -> None:
        """denominators_observed must equal the dynamic batch's denominator projection."""
        dynamic_batch = self._build_dynamic_batch_for_record0()
        pmdm_output = forward_pmdm(batch=self.batch, config=self.config)
        output = forward_covalent(
            pmdm_output=pmdm_output,
            batch=self.batch,
            config=self.config,
            stepwise_candidate_batch=dynamic_batch,
        )
        self.assertEqual(
            output.denominators_observed,
            dynamic_batch.denominators_observed,
        )

    def test_pmdm_outputs_contain_all_seven_required_keys(self) -> None:
        """pmdm_outputs must include all 7 required keys."""
        result = forward_pmdm(batch=self.batch, config=self.config)
        required_keys = {
            "ligand_atom_features",
            "protein_atom_features",
            "ligand_coords_denoised",
            "position_loss",
            "atom_type_loss",
            "timestep",
            "num_atom",
        }
        for key in required_keys:
            self.assertIn(key, result.pmdm_outputs)

    def test_pmdm_output_ligand_coords_denoised_shape_is_b_by_n_lig_by_3(self) -> None:
        """ligand_coords_denoised must be (B, N_lig, 3)."""
        result = forward_pmdm(batch=self.batch, config=self.config)
        coords = result.pmdm_outputs["ligand_coords_denoised"]
        B = self.batch.tensors.protein_coords_shape[0]
        N_lig = self.batch.tensors.ligand_coords_shape[1]
        self.assertEqual(len(coords), B)
        self.assertEqual(len(coords[0]), N_lig)
        self.assertEqual(len(coords[0][0]), 3)

    def test_timestep_is_preserved_in_pmdm_outputs(self) -> None:
        """pmdm_outputs['timestep'] must match the requested value."""
        for ts in (0.1, 0.5, 0.9):
            with self.subTest(timestep=ts):
                result = forward_pmdm(batch=self.batch, config=self.config, timestep=ts)
                self.assertEqual(result.pmdm_outputs["timestep"], ts)


# ===================================================================
# 3.  Forward determinism tests
# ===================================================================


class ForwardDeterminismTests(unittest.TestCase):
    """Task 19-20 forward pass must produce deterministic outputs with fixed seed."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._batch = _heads_builder.build_model_batch()
        cls._stepwise = _stepwise_builder

    def _run_forward(self, seed: int = 42):
        """Run full forward pipeline with a given seed."""
        config = ModelConfig(
            seed=seed,
            ligand_feature_dim=4,
            protein_feature_dim=4,
            rule_table_hash="sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
        )
        record = self._batch.records[0]
        edge_uri = self._batch.static_edge_candidates_refs[record.record_id].uri
        edge_artifact = _edge_artifact(edge_uri)

        for ref in record.artifact_refs.values():
            if ref.role == "protein_atom_table":
                prot_path = _artifact_path(ref.uri)
                break
        else:
            self.fail("protein_atom_table not found")
        protein_atoms = json.loads(prot_path.read_text("utf-8"))["atoms"]

        for ref in record.artifact_refs.values():
            if ref.role == "ligand_atom_table":
                lig_path = _artifact_path(ref.uri)
                break
        else:
            self.fail("ligand_atom_table not found")
        ligand_atoms = json.loads(lig_path.read_text("utf-8"))["atoms"]

        candidate_set = build_stepwise_candidates(
            protein_atoms=protein_atoms,
            ligand_atoms=ligand_atoms,
            edge_candidates_artifact=edge_artifact,
            timestep_index=0,
            timestep_value=0.5,
        )
        dynamic_batch = build_stepwise_candidate_batch(
            tuple(candidate_set for _ in self._batch.records)
        )

        pmdm_output = forward_pmdm(batch=self._batch, config=config)
        return forward_covalent(
            pmdm_output=pmdm_output,
            batch=self._batch,
            config=config,
            stepwise_candidate_batch=dynamic_batch,
        )

    def test_same_seed_produces_identical_edge_logits(self) -> None:
        """Two forward passes with same seed must produce identical edge_logits."""
        out_a = self._run_forward(seed=42)
        out_b = self._run_forward(seed=42)
        self.assertEqual(out_a.edge_logits.data, out_b.edge_logits.data)

    def test_same_seed_produces_identical_bond_type_logits(self) -> None:
        """Two forward passes with same seed must produce identical bond_type_logits."""
        out_a = self._run_forward(seed=42)
        out_b = self._run_forward(seed=42)
        self.assertEqual(out_a.bond_type_logits.data, out_b.bond_type_logits.data)

    def test_same_seed_produces_identical_family_logits(self) -> None:
        """Two forward passes with same seed must produce identical family_logits."""
        out_a = self._run_forward(seed=42)
        out_b = self._run_forward(seed=42)
        self.assertEqual(out_a.family_logits.data, out_b.family_logits.data)

    def test_same_seed_produces_identical_pmdm_outputs(self) -> None:
        """Two forward_pmdm calls with same seed produce identical pmdm_outputs."""
        config = ModelConfig(
            seed=42,
            ligand_feature_dim=4,
            protein_feature_dim=4,
            rule_table_hash="sha256:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
        )
        out_a = forward_pmdm(batch=self._batch, config=config)
        config_b = ModelConfig(
            seed=42,
            ligand_feature_dim=4,
            protein_feature_dim=4,
            rule_table_hash="sha256:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
        )
        out_b = forward_pmdm(batch=self._batch, config=config_b)
        self.assertEqual(out_a.pmdm_outputs, out_b.pmdm_outputs)

    def test_different_seed_changes_non_scalar_outputs(self) -> None:
        """Different seeds must produce different non-scalar pmdm_outputs."""
        config_a = ModelConfig(
            seed=42,
            ligand_feature_dim=4,
            protein_feature_dim=4,
            rule_table_hash="sha256:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
        )
        config_b = ModelConfig(
            seed=99,
            ligand_feature_dim=4,
            protein_feature_dim=4,
            rule_table_hash="sha256:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
        )
        out_a = forward_pmdm(batch=self._batch, config=config_a)
        out_b = forward_pmdm(batch=self._batch, config=config_b)

        differing = []
        for key in ("ligand_atom_features", "protein_atom_features", "ligand_coords_denoised"):
            if out_a.pmdm_outputs[key] != out_b.pmdm_outputs[key]:
                differing.append(key)
        self.assertGreater(len(differing), 0)

    def test_covalent_forward_deterministic_with_same_dynamic_batch(self) -> None:
        """Two forward_covalent calls with identical dynamic batch produce identical output."""
        out_a = self._run_forward(seed=42)
        out_b = self._run_forward(seed=42)
        self.assertEqual(out_a.edge_logits.data, out_b.edge_logits.data)
        self.assertEqual(out_a.bond_type_logits.data, out_b.bond_type_logits.data)
        self.assertEqual(out_a.family_logits.data, out_b.family_logits.data)


# ===================================================================
# 4.  Forward smoke from smoke bundle (existing infrastructure)
# ===================================================================


class ForwardSmokeFromBundleTests(unittest.TestCase):
    """Forward pipeline exercised against the four-record smoke bundle."""

    def test_smoke_bundle_forward_produces_valid_output_for_all_four_records(self) -> None:
        """Each record in the smoke bundle must produce a valid forward output."""
        import json

        rec_path, _split_path = _smoke_builder.write_smoke_train_bundle()
        batch = make_model_batch(rec_path).payload
        config = ModelConfig(
            seed=7,
            ligand_feature_dim=4,
            protein_feature_dim=4,
            rule_table_hash="sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
        )
        for record in batch.records:
            with self.subTest(record_id=record.record_id):
                edge_uri = batch.static_edge_candidates_refs[record.record_id].uri
                edge_artifact = _edge_artifact(edge_uri)

                for ref in record.artifact_refs.values():
                    if ref.role == "protein_atom_table":
                        prot_path = _artifact_path(ref.uri)
                        break
                else:
                    self.fail("protein_atom_table not found")
                protein_atoms = json.loads(prot_path.read_text("utf-8"))["atoms"]

                for ref in record.artifact_refs.values():
                    if ref.role == "ligand_atom_table":
                        lig_path = _artifact_path(ref.uri)
                        break
                else:
                    self.fail("ligand_atom_table not found")
                ligand_atoms = json.loads(lig_path.read_text("utf-8"))["atoms"]

                candidate_set = build_stepwise_candidates(
                    protein_atoms=protein_atoms,
                    ligand_atoms=ligand_atoms,
                    edge_candidates_artifact=edge_artifact,
                    timestep_index=0,
                    timestep_value=0.5,
                )
                dynamic_batch = build_stepwise_candidate_batch(
                    tuple(candidate_set for _ in batch.records)
                )

                pmdm_output = forward_pmdm(batch=batch, config=config)
                output = forward_covalent(
                    pmdm_output=pmdm_output,
                    batch=batch,
                    config=config,
                    stepwise_candidate_batch=dynamic_batch,
                )
                self.assertIsInstance(output, ModelForwardOutput)
                self.assertEqual(output.edge_logits.shape, dynamic_batch.padded_shape)
                self.assertEqual(
                    output.denominators_observed,
                    dynamic_batch.denominators_observed,
                )


# ===================================================================
# 5.  No heavy imports guard
# ===================================================================


class NoHeavyImportsGuardTests(unittest.TestCase):
    """Forward smoke test file must not import torch, RDKit, PMDM, or PocketFlow."""

    def test_forward_smoke_module_does_not_import_heavy_dependencies(self) -> None:
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

    def test_forward_pipeline_shape_summary_is_pure_python(self) -> None:
        """The full forward pipeline (PMDM + covalent) must use only pure Python."""
        import os
        repo_root = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..")
        )
        env = os.environ.copy()
        env["PYTHONPATH"] = os.path.join(repo_root, "src")
        code = (
            "import sys; "
            "from covalent_design.model.config import ModelConfig; "
            "from covalent_design.model.batch import make_model_batch; "
            "from covalent_design.model.pmdm_adapter import forward_pmdm; "
            "from covalent_design.model.covalent_heads import forward_covalent; "
            "heavy = {'torch', 'rdkit', 'pmdm', 'pocketflow'}; "
            "violations = [m for m in sys.modules "
            "if any(m.lower() == h or m.lower().startswith(h + '.') for h in heavy)]; "
            "assert not violations, f'heavy modules loaded: {violations}'"
        )
        import subprocess
        proc = subprocess.run(
            [sys.executable, "-c", code],
            cwd=repo_root,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)


if __name__ == "__main__":
    unittest.main()
