from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

from covalent_design.candidates.edge_candidates import build_edge_candidates
from covalent_design.contracts import (
    EdgeDenominators,
    ExclusionSummary,
    LossReport,
    LossWeights,
    MaskAudit,
    TrainingDatasetIndex,
    TrainingRecordEntry,
)
from covalent_design.data.artifact_manifests import finalize_record_manifests
from covalent_design.io.artifacts import artifact_ref_from_file
from covalent_design.io.jsonl import write_jsonl
from covalent_design.model.candidate_builder import build_stepwise_candidates
from covalent_design.model.covalent_heads import forward_covalent
from tests.fixtures.model._builder import ModelBatchFixtureBuilder
from tests.fixtures.model.covalent_heads._builder import CovalentHeadsFixtureBuilder
from tests.fixtures.model.stepwise_candidates._builder import (
    StepwiseCandidateFixtureBuilder,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
EDGE_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "edge_candidates" / "valid"


class Task12To18ArtifactIntegrationTests(unittest.TestCase):
    def test_task12_artifact_is_consumed_by_task18_without_manual_rewrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp) / "valid"
            shutil.copytree(EDGE_FIXTURE, work)
            records_path = work / "records.jsonl"

            envelope = build_edge_candidates(records_path)
            self.assertTrue(envelope.receipt.ok)

            record = json.loads(records_path.read_text("utf-8").splitlines()[0])
            record_id = record["record_id"]
            artifact_root = work / "artifacts" / record_id
            edge_artifact = json.loads(
                (artifact_root / "edge_candidates.json").read_text("utf-8")
            )
            protein_atoms = json.loads(
                (artifact_root / "protein_atom_table.json").read_text("utf-8")
            )["atoms"]
            ligand_atoms = json.loads(
                (artifact_root / "ligand_atom_table.json").read_text("utf-8")
            )["atoms"]

            result = build_stepwise_candidates(
                protein_atoms=protein_atoms,
                ligand_atoms=ligand_atoms,
                edge_candidates_artifact=edge_artifact,
                timestep_index=0,
                timestep_value=0.5,
            )

            self.assertEqual("2", edge_artifact["edge_candidates_schema_version"])
            self.assertEqual(0, result.positive_label_ligand_atom_index)
            self.assertEqual("SG", result.positive_label_target_atom.atom_name)
            self.assertEqual("single", result.positive_label_bond_type)


class TargetAtomResolutionTests(unittest.TestCase):
    def test_explicit_index_selects_correct_duplicate_name(self) -> None:
        from covalent_design.contracts.atom_resolution import resolve_protein_atom

        atoms = [
            {"index": 0, "name": "SG", "serial": 10, "x": 1.0, "y": 0.0, "z": 0.0},
            {"index": 1, "name": "SG", "serial": 20, "x": 2.0, "y": 0.0, "z": 0.0},
        ]

        atom = resolve_protein_atom(
            atoms,
            target_atom_index=1,
            target_atom_name="SG",
        )

        self.assertEqual(20, atom["serial"])

    def test_ambiguous_name_only_fallback_fails(self) -> None:
        from covalent_design.contracts.atom_resolution import resolve_protein_atom

        atoms = [
            {"name": "SG", "serial": 10},
            {"name": "SG", "serial": 20},
        ]

        with self.assertRaisesRegex(ValueError, "ambiguous"):
            resolve_protein_atom(atoms, target_atom_name="SG")


class DenominatorFreezeTests(unittest.TestCase):
    def test_shared_validator_rejects_under_accounted_eligible_candidates(self) -> None:
        denominators = EdgeDenominators(
            candidate_count=3,
            natural_candidate_count=3,
            forced_positive_count=0,
            eligible_edge_count=1,
            masked_candidate_count=1,
            edge_loss_denominator=1,
            bond_type_loss_denominator=1,
            geometry_loss_denominator=1,
            message_passing_candidate_count=3,
            gate_evaluated_count=3,
        )

        with self.assertRaisesRegex(Exception, "candidate_count"):
            denominators.validate()

    def test_task18_bond_and_geometry_denominators_count_natural_positives_only(self) -> None:
        fixture = StepwiseCandidateFixtureBuilder()
        protein_atoms, ligand_atoms, edge_artifact = fixture.load("within_radius")

        result = build_stepwise_candidates(
            protein_atoms=protein_atoms,
            ligand_atoms=ligand_atoms,
            edge_candidates_artifact=edge_artifact,
            timestep_index=0,
            timestep_value=0.5,
        )

        self.assertEqual(1, result.denominators.bond_type_loss_denominator)
        self.assertEqual(1, result.denominators.geometry_loss_denominator)


class TrainingBatchLoaderTests(unittest.TestCase):
    def test_loader_delegates_singleton_batch_to_task17_boundary(self) -> None:
        from covalent_design.training.batch import load_training_batch

        records_path = ModelBatchFixtureBuilder().write_valid()
        rows = [
            json.loads(line)
            for line in Path(records_path).read_text("utf-8").splitlines()
            if line.strip()
        ]
        entries = tuple(
            TrainingRecordEntry(
                record_id=row["record_id"],
                residue_reaction_family=row["core_labels"]["residue_reaction_family"],
                quality_tier=row["metadata"]["quality"]["quality_tier"],
                visual_check_status="pass",
                fallback_reason=None,
                manual_review_status=None,
                artifact_refs={},
            )
            for row in rows
        )
        dataset = TrainingDatasetIndex(
            policy={},
            split_name="train",
            records=entries,
            excluded_summary=ExclusionSummary(
                total_accepted=2,
                records_in_split=2,
                excluded_by_policy=0,
                exclusion_reasons={},
            ),
            records_path=records_path,
        )

        envelope = load_training_batch(dataset, "batch-0")

        self.assertEqual(1, len(envelope.payload.records))
        self.assertEqual(entries[0].record_id, envelope.payload.records[0].record_id)


class ModelBatchProvenanceTests(unittest.TestCase):
    def test_visual_status_is_preserved_without_filtering(self) -> None:
        from covalent_design.model.batch import make_model_batch

        batch = make_model_batch(ModelBatchFixtureBuilder().write_mixed_quality_split()).payload
        visual_fail = next(
            record
            for record in batch.records
            if record.record_id == "m10a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6"
        )

        self.assertEqual("fail", visual_fail.visual_check_status)


class DynamicCandidateForwardTests(unittest.TestCase):
    def test_forward_consumes_dynamic_candidate_batch_and_calls_message_guard(self) -> None:
        from covalent_design.model.candidate_builder import (
            build_stepwise_candidate_batch,
        )

        stepwise_fixture = StepwiseCandidateFixtureBuilder()
        protein_atoms, ligand_atoms, edge_artifact = stepwise_fixture.load("within_radius")
        candidate_set = build_stepwise_candidates(
            protein_atoms=protein_atoms,
            ligand_atoms=ligand_atoms,
            edge_candidates_artifact=edge_artifact,
            timestep_index=0,
            timestep_value=0.5,
        )
        dynamic_batch = build_stepwise_candidate_batch((candidate_set, candidate_set))

        heads_fixture = CovalentHeadsFixtureBuilder(seed=42)
        batch = heads_fixture.build_model_batch()
        config = heads_fixture.build_config()
        pmdm_output = heads_fixture.build_task19_handoff(batch)

        with patch(
            "covalent_design.model.covalent_heads.apply_edge_message_weights",
            wraps=__import__(
                "covalent_design.model.edge_message_passing",
                fromlist=["apply_edge_message_weights"],
            ).apply_edge_message_weights,
        ) as guard:
            output = forward_covalent(
                pmdm_output=pmdm_output,
                batch=batch,
                config=config,
                stepwise_candidate_batch=dynamic_batch,
            )

        self.assertEqual(dynamic_batch.padded_shape, output.edge_logits.shape)
        self.assertEqual(dynamic_batch.denominators_observed, output.denominators_observed)
        guard.assert_called_once()

    def test_forward_rejects_dynamic_candidate_batch_with_wrong_batch_size(self) -> None:
        from covalent_design.model.candidate_builder import (
            build_stepwise_candidate_batch,
        )

        stepwise_fixture = StepwiseCandidateFixtureBuilder()
        protein_atoms, ligand_atoms, edge_artifact = stepwise_fixture.load("within_radius")
        candidate_set = build_stepwise_candidates(
            protein_atoms=protein_atoms,
            ligand_atoms=ligand_atoms,
            edge_candidates_artifact=edge_artifact,
            timestep_index=0,
            timestep_value=0.5,
        )
        dynamic_batch = build_stepwise_candidate_batch((candidate_set,))

        heads_fixture = CovalentHeadsFixtureBuilder(seed=42)
        batch = heads_fixture.build_model_batch()
        config = heads_fixture.build_config()
        pmdm_output = heads_fixture.build_task19_handoff(batch)

        with self.assertRaisesRegex(ValueError, "match the model batch size"):
            forward_covalent(
                pmdm_output=pmdm_output,
                batch=batch,
                config=config,
                stepwise_candidate_batch=dynamic_batch,
            )


class Task23FlagsAndLossReportTests(unittest.TestCase):
    def test_normalized_mask_flags_are_resolved_by_training_masks(self) -> None:
        from covalent_design.training.masks import resolve_mask_flags

        flags = resolve_mask_flags(
            pending_smarts=True,
            pending_geometry=False,
            missing_required_chemical_state=True,
            quality_tier="Q2",
            exclude_q2=True,
        )

        self.assertEqual("Q2", flags.quality_tier)
        self.assertTrue(flags.pending_smarts)
        self.assertTrue(flags.missing_required_chemical_state)
        self.assertTrue(flags.exclude_q2)

    def test_loss_report_serializes_mask_audit_inside_each_stratum(self) -> None:
        from covalent_design.contracts import DenominatorsStratum

        audit = MaskAudit(
            candidate_count=1,
            natural_positive_count=1,
            forced_positive_count=0,
            natural_negative_count=0,
            zero_negative_count=1,
            masked_by_pending_smarts=0,
            masked_by_pending_geometry=0,
            masked_by_missing_chemical_state=0,
            masked_by_q2_exclusion=0,
            masked_by_forced_positive_exclusion=0,
            edge_loss_eligible_count=1,
            bond_type_loss_eligible_count=1,
            geometry_loss_eligible_count=1,
            message_passing_candidate_count=1,
            gate_evaluated_count=1,
        )
        denominators = EdgeDenominators(
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
        )
        report = LossReport(
            components={
                "pmdm_position_loss": 1.0,
                "pmdm_atom_loss": 1.0,
                "covalent_edge_loss": 1.0,
                "covalent_bond_type_loss": 1.0,
                "covalent_geometry_loss": 1.0,
                "family_aux_loss": 1.0,
            },
            strata=(
                DenominatorsStratum(
                    residue_reaction_family="CYS_MICHAEL_ADDITION",
                    timestep_bucket="mid",
                    denominators=denominators,
                    mask_audit=audit,
                ),
            ),
        )

        serialized = report.to_dict()

        self.assertEqual(asdict(audit), serialized["strata"][0]["mask_audit"])

    def test_loss_weights_smoke_contract_defaults_are_deterministic(self) -> None:
        weights = LossWeights()

        self.assertEqual(
            {
                "pmdm_position_loss": 1.0,
                "pmdm_atom_loss": 1.0,
                "covalent_edge_loss": 1.0,
                "covalent_bond_type_loss": 1.0,
                "covalent_geometry_loss": 1.0,
                "family_aux_loss": 1.0,
            },
            weights.to_dict(),
        )


class TrainingDatasetMalformedInputTests(unittest.TestCase):
    def test_malformed_split_assignment_returns_structured_failure(self) -> None:
        from covalent_design.training.dataset import prepare_dataset

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            records_path = root / "records.jsonl"
            split_path = root / "split_index.json"
            write_jsonl(
                records_path,
                [{"record_id": "REC-1", "artifacts": []}],
                role="record_index",
            )
            split_path.write_text('{"assignments":[42]}', encoding="utf-8")

            envelope = prepare_dataset(records_path, split_path, "train")

        self.assertFalse(envelope.receipt.ok)
        self.assertEqual(
            "TRAINING_SPLIT_ASSIGNMENT_INVALID",
            envelope.receipt.errors[0].code,
        )

    def test_malformed_nested_artifact_returns_structured_failure(self) -> None:
        from covalent_design.training.dataset import prepare_dataset

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            records_path = root / "records.jsonl"
            split_path = root / "split_index.json"
            write_jsonl(
                records_path,
                [{"record_id": "REC-1", "artifacts": [42]}],
                role="record_index",
            )
            split_path.write_text(
                '{"assignments":[{"record_id":"REC-1","split":"train"}]}',
                encoding="utf-8",
            )

            envelope = prepare_dataset(records_path, split_path, "train")

        self.assertFalse(envelope.receipt.ok)
        self.assertEqual(
            "TRAINING_ARTIFACT_REF_INVALID",
            envelope.receipt.errors[0].code,
        )

    def test_malformed_core_labels_returns_structured_failure(self) -> None:
        from covalent_design.training.dataset import prepare_dataset

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            records_path = root / "records.jsonl"
            split_path = root / "split_index.json"
            write_jsonl(
                records_path,
                [{"record_id": "REC-1", "core_labels": [], "artifacts": []}],
                role="record_index",
            )
            split_path.write_text(
                '{"assignments":[{"record_id":"REC-1","split":"train"}]}',
                encoding="utf-8",
            )

            envelope = prepare_dataset(records_path, split_path, "train")

        self.assertFalse(envelope.receipt.ok)
        self.assertEqual("TRAINING_RECORD_INVALID", envelope.receipt.errors[0].code)


class Task24TracerBulletTests(unittest.TestCase):
    def test_task12_through_task23_seam_without_task24_loss(self) -> None:
        from covalent_design.model.batch import make_model_batch
        from covalent_design.model.candidate_builder import build_stepwise_candidate_batch
        from covalent_design.model.config import ModelConfig
        from covalent_design.model.pmdm_adapter import forward_pmdm
        from covalent_design.training.denominators import build_edge_denominators
        from covalent_design.training.masks import compute_mask_audit, resolve_mask_flags

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            record_id = "TRACE-001"
            artifact_root = root / "artifacts" / record_id
            artifact_root.mkdir(parents=True)
            (artifact_root / "coordinates.pdb").write_text(
                '{"format":"pdb","data":"ATOM\\n"}',
                encoding="utf-8",
            )
            (artifact_root / "protein_atom_table.json").write_text(
                json.dumps(
                    {
                        "atoms": [
                            {"serial": 1, "name": "N", "x": 0.0, "y": 1.0, "z": 0.0},
                            {"serial": 2, "name": "SG", "element": "S", "x": 0.0, "y": 0.0, "z": 0.0},
                        ],
                        "chain_id": "A",
                        "residue_number": 42,
                        "residue_name": "CYS",
                    }
                ),
                encoding="utf-8",
            )
            (artifact_root / "ligand_atom_table.json").write_text(
                json.dumps(
                    {
                        "atoms": [
                            {"index": 0, "name": "C1", "element": "C", "x": 1.0, "y": 0.0, "z": 0.0},
                            {"index": 1, "name": "C2", "element": "C", "x": 2.0, "y": 0.0, "z": 0.0},
                        ],
                        "ligand_id": "LIG",
                    }
                ),
                encoding="utf-8",
            )
            (artifact_root / "ligand_bond_table.json").write_text(
                '{"bonds":[]}',
                encoding="utf-8",
            )
            refs = [
                artifact_ref_from_file(path, role=role, root=root)
                for role, path in (
                    ("coordinates", artifact_root / "coordinates.pdb"),
                    ("protein_atom_table", artifact_root / "protein_atom_table.json"),
                    ("ligand_atom_table", artifact_root / "ligand_atom_table.json"),
                    ("ligand_bond_table", artifact_root / "ligand_bond_table.json"),
                )
            ]
            row = {
                "record_id": record_id,
                "core_labels": {
                    "bond_type": "carbon-sulfur",
                    "ligand_atom_element": "C",
                    "ligand_atom_index": 0,
                    "ligand_atom_name": "C1",
                    "pdb_id": "trace",
                    "residue_reaction_family": "CYS_MICHAEL_ADDITION",
                    "target_atom_index": 1,
                    "target_atom_name": "SG",
                    "warhead_type": "acrylamide",
                },
                "lineage": [],
                "metadata": {
                    "chemical_state": {"status": "explicit"},
                    "quality": {"quality_tier": "Q0"},
                    "visual_check_status": "pass",
                },
                "artifacts": [asdict(ref) for ref in refs],
            }
            records_path = root / "records.jsonl"
            write_jsonl(records_path, [row], role="record_index")
            (root / "artifact_manifest.json").write_text(
                json.dumps({record_id: [asdict(ref) for ref in refs]}),
                encoding="utf-8",
            )

            self.assertTrue(build_edge_candidates(records_path).receipt.ok)
            self.assertTrue(finalize_record_manifests(records_path).receipt.ok)
            batch = make_model_batch(records_path).payload
            edge_artifact = json.loads(
                (artifact_root / "edge_candidates.json").read_text("utf-8")
            )
            protein_atoms = json.loads(
                (artifact_root / "protein_atom_table.json").read_text("utf-8")
            )["atoms"]
            ligand_atoms = json.loads(
                (artifact_root / "ligand_atom_table.json").read_text("utf-8")
            )["atoms"]
            candidate_set = build_stepwise_candidates(
                protein_atoms=protein_atoms,
                ligand_atoms=ligand_atoms,
                edge_candidates_artifact=edge_artifact,
                timestep_index=0,
                timestep_value=0.5,
            )
            dynamic_batch = build_stepwise_candidate_batch((candidate_set,))
            config = ModelConfig(seed=7, ligand_feature_dim=4, protein_feature_dim=4)
            pmdm_output = forward_pmdm(batch=batch, config=config)
            forward_output = forward_covalent(
                pmdm_output=pmdm_output,
                batch=batch,
                config=config,
                stepwise_candidate_batch=dynamic_batch,
            )
            flags = resolve_mask_flags(quality_tier=batch.records[0].quality_tier)
            audit = compute_mask_audit(candidate_set, **asdict(flags))
            projected = build_edge_denominators(audit)

        self.assertEqual(dynamic_batch.padded_shape, forward_output.edge_logits.shape)
        self.assertEqual(projected, forward_output.denominators_observed)


if __name__ == "__main__":
    unittest.main()
