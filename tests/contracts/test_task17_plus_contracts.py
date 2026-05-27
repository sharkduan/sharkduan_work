import unittest

from covalent_design.contracts import (
    ArtifactRef,
    ALLOWED_MESSAGE_WEIGHT_SOURCES,
    BatchRecordHeader,
    BatchSpec,
    BatchTensors,
    EdgeDenominators,
    GenerationRunManifest,
    LossReport,
    MaskAudit,
    ModelBatch,
    ModelForwardOutput,
    MESSAGE_WEIGHT_SOURCE_DETACHED_EDGE_PROBABILITY,
    ProteinAtomIdentity,
    TrainingRunManifest,
)


class FakeTensor:
    def __init__(self, requires_grad: bool) -> None:
        self.requires_grad = requires_grad


def target_atom() -> ProteinAtomIdentity:
    return ProteinAtomIdentity(
        chain_id="A",
        residue_number=145,
        residue_name="CYS",
        atom_name="SG",
        atom_serial=1234,
    )


def denominators() -> EdgeDenominators:
    return EdgeDenominators(
        candidate_count=3,
        natural_candidate_count=3,
        forced_positive_count=0,
        eligible_edge_count=3,
        masked_candidate_count=0,
        edge_loss_denominator=3,
        bond_type_loss_denominator=1,
        geometry_loss_denominator=1,
        message_passing_candidate_count=3,
        gate_evaluated_count=3,
    )


def tensors() -> BatchTensors:
    return BatchTensors(
        protein_coords_shape=(1, 10, 3),
        ligand_coords_shape=(1, 5, 3),
        protein_atom_types_shape=(1, 10),
        ligand_atom_types_shape=(1, 5),
        ligand_bonds_shape=(1, 5, 5),
        edge_candidates_shape=(1, 3),
        positive_label_mask_shape=(1, 3),
        candidate_to_ligand_map_shape=(1, 3),
        candidate_to_protein_map_shape=(1, 3),
    )


def loss_components() -> dict[str, float]:
    return {
        "pmdm_position_loss": 0.1,
        "pmdm_atom_loss": 0.2,
        "covalent_edge_loss": 0.3,
        "covalent_bond_type_loss": 0.4,
        "covalent_geometry_loss": 0.5,
        "family_aux_loss": 0.6,
    }


def mask_audit() -> MaskAudit:
    return MaskAudit(
        candidate_count=3,
        natural_positive_count=1,
        forced_positive_count=0,
        natural_negative_count=2,
        zero_negative_count=0,
        masked_by_pending_smarts=0,
        masked_by_pending_geometry=1,
        masked_by_missing_chemical_state=0,
        masked_by_q2_exclusion=0,
        masked_by_forced_positive_exclusion=0,
        edge_loss_eligible_count=3,
        bond_type_loss_eligible_count=1,
        geometry_loss_eligible_count=0,
        message_passing_candidate_count=3,
        gate_evaluated_count=3,
    )


class PublicTask17PlusContractExportsTests(unittest.TestCase):
    def test_task17_plus_types_are_importable_from_contracts_facade(self) -> None:
        self.assertEqual(ModelBatch.__name__, "ModelBatch")
        self.assertEqual(BatchSpec.__name__, "BatchSpec")
        self.assertEqual(ModelForwardOutput.__name__, "ModelForwardOutput")
        self.assertEqual(LossReport.__name__, "LossReport")
        self.assertEqual(GenerationRunManifest.__name__, "GenerationRunManifest")
        self.assertEqual(
            MESSAGE_WEIGHT_SOURCE_DETACHED_EDGE_PROBABILITY,
            "detached_edge_probability",
        )
        self.assertEqual(
            ALLOWED_MESSAGE_WEIGHT_SOURCES,
            ("detached_edge_probability",),
        )


class ModelForwardOutputGuardTests(unittest.TestCase):
    def test_accepts_detached_message_weights_without_torch_dependency(self) -> None:
        output = ModelForwardOutput(
            pmdm_outputs={},
            edge_logits=FakeTensor(requires_grad=True),
            bond_type_logits=object(),
            family_logits=object(),
            edge_prob_message_weights=FakeTensor(requires_grad=False),
            message_weight_source=MESSAGE_WEIGHT_SOURCE_DETACHED_EDGE_PROBABILITY,
            denominators_observed=denominators(),
        )

        self.assertFalse(output.edge_prob_message_weights.requires_grad)
        self.assertEqual(
            output.message_weight_source,
            MESSAGE_WEIGHT_SOURCE_DETACHED_EDGE_PROBABILITY,
        )

    def test_rejects_message_weights_that_require_grad(self) -> None:
        with self.assertRaisesRegex(ValueError, "edge_prob_message_weights"):
            ModelForwardOutput(
                pmdm_outputs={},
                edge_logits=FakeTensor(requires_grad=True),
                bond_type_logits=object(),
                family_logits=object(),
                edge_prob_message_weights=FakeTensor(requires_grad=True),
                message_weight_source=MESSAGE_WEIGHT_SOURCE_DETACHED_EDGE_PROBABILITY,
                denominators_observed=denominators(),
            )

    def test_rejects_label_source_even_when_detached(self) -> None:
        for source in ("label", "ground_truth", "target_edge"):
            with self.subTest(source=source):
                with self.assertRaisesRegex(ValueError, "detached prediction path"):
                    ModelForwardOutput(
                        pmdm_outputs={},
                        edge_logits=FakeTensor(requires_grad=True),
                        bond_type_logits=object(),
                        family_logits=object(),
                        edge_prob_message_weights=FakeTensor(requires_grad=False),
                        message_weight_source=source,
                        denominators_observed=denominators(),
                    )

    def test_rejects_missing_message_weight_source(self) -> None:
        with self.assertRaisesRegex(ValueError, "message_weight_source"):
            ModelForwardOutput(
                pmdm_outputs={},
                edge_logits=FakeTensor(requires_grad=True),
                bond_type_logits=object(),
                family_logits=object(),
                edge_prob_message_weights=FakeTensor(requires_grad=False),
                message_weight_source="",
                denominators_observed=denominators(),
            )


class ModelBatchReactiveSiteContractTests(unittest.TestCase):
    def test_batch_record_header_exposes_target_atom_identity_and_index(self) -> None:
        header = BatchRecordHeader(
            record_id="rec-1",
            residue_reaction_family="CYS_MICHAEL_ACCEPTOR",
            quality_tier="Q1",
            visual_check_status="pass",
            chemical_state_status="explicit",
            target_atom_identity=target_atom(),
            target_atom_index=7,
            target_atom_artifact_role="protein_atom_table",
        )
        batch = ModelBatch(
            records=(header,),
            tensors=tensors(),
            static_edge_candidates_refs={
                "rec-1": ArtifactRef(
                    uri="artifacts/rec-1/edge_candidates.json",
                    sha256="a" * 64,
                    format="json",
                    role="edge_candidates",
                )
            },
            denominators_expected=denominators(),
        )

        self.assertEqual(batch.records[0].target_atom_identity.atom_name, "SG")
        self.assertEqual(batch.records[0].target_atom_index, 7)
        self.assertEqual(batch.records[0].target_atom_artifact_role, "protein_atom_table")

    def test_batch_record_header_rejects_missing_required_target_atom_info(self) -> None:
        with self.assertRaises(TypeError):
            BatchRecordHeader(
                record_id="rec-1",
                residue_reaction_family="CYS_MICHAEL_ACCEPTOR",
                quality_tier="Q1",
                visual_check_status="pass",
                chemical_state_status="explicit",
                target_atom_index=7,
            )

        with self.assertRaises(TypeError):
            BatchRecordHeader(
                record_id="rec-1",
                residue_reaction_family="CYS_MICHAEL_ACCEPTOR",
                quality_tier="Q1",
                visual_check_status="pass",
                chemical_state_status="explicit",
                target_atom_identity=target_atom(),
            )


class LossReportContractTests(unittest.TestCase):
    def test_loss_report_rejects_missing_required_component(self) -> None:
        components = loss_components()
        components.pop("family_aux_loss")

        with self.assertRaisesRegex(ValueError, "family_aux_loss"):
            LossReport(components=components)

    def test_loss_report_accepts_complete_required_components(self) -> None:
        report = LossReport(
            step=1,
            total_loss=2.1,
            components=loss_components(),
            denominators=denominators(),
            mask_audit=mask_audit(),
        )

        self.assertEqual(report.components["family_aux_loss"], 0.6)

    def test_loss_report_to_dict_serializes_full_mask_audit(self) -> None:
        report = LossReport(
            components=loss_components(),
            mask_audit=mask_audit(),
        )

        serialized = report.to_dict()["mask_audit"]

        self.assertEqual(
            set(serialized.keys()),
            {
                "candidate_count",
                "natural_positive_count",
                "forced_positive_count",
                "natural_negative_count",
                "zero_negative_count",
                "masked_by_pending_smarts",
                "masked_by_pending_geometry",
                "masked_by_missing_chemical_state",
                "masked_by_q2_exclusion",
                "masked_by_forced_positive_exclusion",
                "edge_loss_eligible_count",
                "bond_type_loss_eligible_count",
                "geometry_loss_eligible_count",
                "message_passing_candidate_count",
                "gate_evaluated_count",
            },
        )


class TrainingRunManifestProvenanceTests(unittest.TestCase):
    def test_manifest_can_carry_release_gate_provenance_hashes(self) -> None:
        manifest = TrainingRunManifest(
            run_id="run-1",
            training_config_resolved_hash="sha256:config",
            input_hashes={
                "records_jsonl": "sha256:records",
                "split_index": "sha256:split",
                "rule_table": "sha256:rules",
                "quality_report": "sha256:quality",
                "visual_check_index": "sha256:visual",
                "release_gate": "sha256:approval",
            },
        )

        self.assertEqual(manifest.input_hashes["quality_report"], "sha256:quality")
        self.assertEqual(manifest.input_hashes["visual_check_index"], "sha256:visual")
        self.assertEqual(manifest.input_hashes["release_gate"], "sha256:approval")


if __name__ == "__main__":
    unittest.main()
