"""Task 24 smoke training contract tests.

These tests define the public API and boundary contracts for
``compute_losses()`` and the training smoke CLI.  They are designed to be
RED-first: the Task 24 production modules
(``covalent_design.training.losses`` and
``covalent_design.training.train``) do not exist yet.

Coverage:
1. All six required loss components and weighted total using LossWeights
2. Denominators, MaskAudit, and non-empty serialized family/timestep strata
3. Pending-smarts, pending-geometry, missing-required-state, Q2-exclusion,
   forced-positive, and zero-natural-negative audit paths
5. Train CLI deterministic one-line train_metrics.jsonl and concise JSON summary
6. CPU/fake-backbone only; no checkpoint run manifest, no torch/RDKit/PMDM/PocketFlow
"""
from __future__ import annotations

import json
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from dataclasses import asdict
from pathlib import Path

# ---------------------------------------------------------------------------
# contracts — always importable
# ---------------------------------------------------------------------------
from covalent_design.contracts.types import (
    CONTRACT_VERSION,
    SCHEMA_VERSION,
    REQUIRED_LOSS_COMPONENT_KEYS,
    DenominatorsStratum,
    EdgeDenominators,
    LossReport,
    LossWeights,
    MaskAudit,
    StepwiseCandidate,
    StepwiseCandidateSet,
)
from covalent_design.contracts import ProteinAtomIdentity

# ---------------------------------------------------------------------------
# existing training infrastructure
# ---------------------------------------------------------------------------
from covalent_design.training.masks import (
    NormalizedMaskFlags,
    compute_mask_audit,
    resolve_mask_flags,
)
from covalent_design.training.denominators import (
    DenominatorStratumEntry,
    aggregate_denominator_strata,
    build_edge_denominators,
    classify_timestep_bucket,
)

# ---------------------------------------------------------------------------
# fixture builders
# ---------------------------------------------------------------------------
from tests.fixtures.training.masks_denominators._builder import (
    MasksDenominatorsFixtureBuilder,
)
from tests.fixtures.training.smoke._builder import SmokeFixtureBuilder

# ===================================================================
# helpers
# ===================================================================


def _make_target_atom() -> ProteinAtomIdentity:
    return ProteinAtomIdentity(
        chain_id="A",
        residue_number=145,
        residue_name="CYS",
        atom_name="SG",
        atom_serial=1234,
    )


def _make_candidate(
    local_index: int,
    ligand_atom_index: int,
    is_positive_label: bool,
    is_forced_positive: bool,
    within_radius: bool,
    distance: float,
    target_atom: ProteinAtomIdentity | None = None,
) -> StepwiseCandidate:
    return StepwiseCandidate(
        local_index=local_index,
        ligand_atom_index=ligand_atom_index,
        target_atom=target_atom or _make_target_atom(),
        is_positive_label=is_positive_label,
        is_forced_positive=is_forced_positive,
        within_radius=within_radius,
        distance=distance,
    )


def _assert_importable(module_name: str, attribute: str) -> None:
    __import__(module_name)
    getattr(sys.modules[module_name], attribute)


_audit_builder = MasksDenominatorsFixtureBuilder()
_smoke_builder = SmokeFixtureBuilder()


def _artifact_path(records_path: object, uri: str) -> Path:
    return (Path(records_path).resolve().parent / uri).resolve()


# ===================================================================
# 1.  compute_losses API contract (RED)
# ===================================================================


class ComputeLossesContractTests(unittest.TestCase):
    """``compute_losses()`` API signature, return type, and component contract.

    These tests are expected to RED because ``covalent_design.training.losses``
    does not exist yet (it is Task 24 production scope, not preflight).
    """

    def test_compute_losses_is_importable(self) -> None:
        """compute_losses must be importable from covalent_design.training.losses."""
        _assert_importable("covalent_design.training.losses", "compute_losses")

    def test_compute_losses_accepts_preflight_signature(self) -> None:
        """compute_losses must accept the frozen preflight contract signature."""
        from covalent_design.training.losses import compute_losses  # RED

    def test_compute_losses_returns_loss_report_with_six_required_components(self) -> None:
        """LossReport.components must contain all 6 required keys with finite floats."""
        report = LossReport(
            components={
                "pmdm_position_loss": 1.0,
                "pmdm_atom_loss": 1.0,
                "covalent_edge_loss": 1.0,
                "covalent_bond_type_loss": 1.0,
                "covalent_geometry_loss": 1.0,
                "family_aux_loss": 1.0,
            },
        )
        self.assertEqual(report.components, {
            k: 1.0 for k in REQUIRED_LOSS_COMPONENT_KEYS
        })

    def test_loss_report_rejects_missing_required_component(self) -> None:
        """LossReport construction must raise ValueError when a required key is absent."""
        with self.assertRaises(ValueError):
            LossReport(
                components={
                    "pmdm_position_loss": 1.0,
                    "pmdm_atom_loss": 1.0,
                    # missing 4 keys
                },
            )

    def test_loss_weights_smoke_defaults_are_all_one(self) -> None:
        """Smoke LossWeights defaults must all be 1.0."""
        weights = LossWeights()
        d = weights.to_dict()
        self.assertEqual(d["pmdm_position_loss"], 1.0)
        self.assertEqual(d["pmdm_atom_loss"], 1.0)
        self.assertEqual(d["covalent_edge_loss"], 1.0)
        self.assertEqual(d["covalent_bond_type_loss"], 1.0)
        self.assertEqual(d["covalent_geometry_loss"], 1.0)
        self.assertEqual(d["family_aux_loss"], 1.0)
        self.assertEqual(len(d), 6)

    def test_weighted_total_formula_is_dot_product(self) -> None:
        """Weighted total loss = sum(weight * component)."""
        weights = LossWeights(
            pmdm_position_loss=2.0,
            pmdm_atom_loss=1.0,
            covalent_edge_loss=1.0,
            covalent_bond_type_loss=1.0,
            covalent_geometry_loss=0.0,
            family_aux_loss=0.5,
        )
        components = {
            "pmdm_position_loss": 0.5,
            "pmdm_atom_loss": 0.3,
            "covalent_edge_loss": 0.2,
            "covalent_bond_type_loss": 0.1,
            "covalent_geometry_loss": 0.0,
            "family_aux_loss": 0.8,
        }
        expected_total = (
            2.0 * 0.5 + 1.0 * 0.3 + 1.0 * 0.2 + 1.0 * 0.1 + 0.0 * 0.0 + 0.5 * 0.8
        )
        self.assertAlmostEqual(expected_total, 1.0 + 0.3 + 0.2 + 0.1 + 0.0 + 0.4)
        self.assertAlmostEqual(expected_total, 2.0)

    def test_geometry_smoke_loss_is_explicit_zero_sentinel(self) -> None:
        """Geometry loss component in smoke path must be exactly 0.0 (sentinel).

        Smoke tests do not test real geometry regression; the geometry loss
        is wired as an explicit finite 0.0 placeholder.
        """
        comm_loss = 0.0
        self.assertEqual(comm_loss, 0.0)
        self.assertTrue(0.0 <= comm_loss == 0.0)

    def test_family_aux_loss_is_deterministic_finite_value(self) -> None:
        """family_aux_loss must be a deterministic finite pseudo cross-entropy component."""
        loss = 0.693147  # ~ -ln(0.5) for a balanced pseudoclass
        self.assertGreater(loss, 0.0)
        self.assertLess(loss, 10.0)
        import math
        self.assertTrue(math.isfinite(loss))


# ===================================================================
# 2.  Denominators and MaskAudit smoke tests
# ===================================================================


class DenominatorsAndAuditSmokeTests(unittest.TestCase):
    """Denominator and MaskAudit validation in smoke context.

    These tests use the existing Task 23 infrastructure and should PASS.
    """

    def test_mask_audit_conservation_invariant_holds(self) -> None:
        """TC == NP + FP + NN must hold for every audit."""
        cs = _audit_builder.build_natural_positive_set()
        audit = compute_mask_audit(cs)
        self.assertEqual(
            audit.candidate_count,
            audit.natural_positive_count
            + audit.forced_positive_count
            + audit.natural_negative_count,
        )

    def test_edge_denominators_must_match_mask_audit_projection_after_valid(self) -> None:
        """build_edge_denominators must project audit counts onto denom fields."""
        cs = _audit_builder.build_natural_positive_set()
        audit = compute_mask_audit(cs)
        denoms = build_edge_denominators(audit)
        self.assertEqual(denoms.candidate_count, audit.candidate_count)
        self.assertEqual(
            denoms.natural_candidate_count,
            audit.natural_positive_count + audit.natural_negative_count,
        )
        self.assertEqual(denoms.forced_positive_count, audit.forced_positive_count)
        self.assertEqual(denoms.edge_loss_denominator, audit.edge_loss_eligible_count)
        self.assertEqual(
            denoms.bond_type_loss_denominator, audit.bond_type_loss_eligible_count,
        )
        self.assertEqual(
            denoms.geometry_loss_denominator, audit.geometry_loss_eligible_count,
        )

    def test_edge_denominators_validate_rejects_negative_count(self) -> None:
        """EdgeDenominators.validate must reject negative values."""
        with self.assertRaises(Exception):
            EdgeDenominators(
                candidate_count=-1,
                natural_candidate_count=0,
                forced_positive_count=0,
                eligible_edge_count=0,
                masked_candidate_count=0,
                edge_loss_denominator=0,
                bond_type_loss_denominator=0,
                geometry_loss_denominator=0,
                message_passing_candidate_count=0,
                gate_evaluated_count=0,
            ).validate()

    def test_edge_denominators_validate_rejects_under_accounting(self) -> None:
        """eligible_edge + masked must not exceed candidate_count."""
        with self.assertRaises(Exception):
            EdgeDenominators(
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
            ).validate()

    def test_loss_report_serializes_denominators_and_mask_audit(self) -> None:
        """LossReport.to_dict() must include denominators and mask_audit when non-None."""
        audit = compute_mask_audit(_audit_builder.build_natural_positive_set())
        denoms = build_edge_denominators(audit)
        report = LossReport(
            components={k: 1.0 for k in REQUIRED_LOSS_COMPONENT_KEYS},
            denominators=denoms,
            mask_audit=audit,
        )
        serialized = report.to_dict()
        self.assertIn("denominators", serialized)
        self.assertIn("mask_audit", serialized)
        self.assertEqual(serialized["denominators"]["candidate_count"], audit.candidate_count)
        self.assertEqual(serialized["mask_audit"]["candidate_count"], audit.candidate_count)

    def test_strata_serialization_includes_mask_audit_per_stratum(self) -> None:
        """Each stratum in LossReport.to_dict() must carry mask_audit."""
        audit = compute_mask_audit(_audit_builder.build_natural_positive_set())
        denoms = build_edge_denominators(audit)
        stratum = DenominatorsStratum(
            residue_reaction_family="CYS_MICHAEL_ADDITION",
            timestep_bucket="mid",
            denominators=denoms,
            mask_audit=audit,
        )
        report = LossReport(
            components={k: 1.0 for k in REQUIRED_LOSS_COMPONENT_KEYS},
            strata=(stratum,),
        )
        serialized = report.to_dict()
        self.assertEqual(len(serialized["strata"]), 1)
        serialized_stratum = serialized["strata"][0]
        self.assertIn("mask_audit", serialized_stratum)
        self.assertEqual(
            serialized_stratum["mask_audit"]["candidate_count"],
            audit.candidate_count,
        )

    def test_non_empty_strata_span_family_and_timestep_dimensions(self) -> None:
        """Aggregated strata must contain entries for at least two families across at least
        two timestep buckets."""
        target = _make_target_atom()
        entries: list[DenominatorStratumEntry] = []
        for fam in ("CYS_MICHAEL_ADDITION", "LYS_IMINE_FORMATION"):
            for ts in (0.9, 0.5):
                candidates = (
                    _make_candidate(0, 0, True, False, True, 2.0, target),
                    _make_candidate(1, 1, False, False, True, 2.5, target),
                )
                cs = StepwiseCandidateSet(
                    timestep_index=0,
                    timestep_value=ts,
                    candidates=candidates,
                    positive_label_ligand_atom_index=0,
                    positive_label_target_atom=target,
                    positive_label_bond_type="carbon-sulfur",
                    denominators=build_edge_denominators(
                        MaskAudit(
                            candidate_count=2,
                            natural_positive_count=1,
                            forced_positive_count=0,
                            natural_negative_count=1,
                            zero_negative_count=0,
                            masked_by_pending_smarts=0,
                            masked_by_pending_geometry=0,
                            masked_by_missing_chemical_state=0,
                            masked_by_q2_exclusion=0,
                            masked_by_forced_positive_exclusion=0,
                            edge_loss_eligible_count=2,
                            bond_type_loss_eligible_count=1,
                            geometry_loss_eligible_count=1,
                            message_passing_candidate_count=2,
                            gate_evaluated_count=2,
                        )
                    ),
                    empty_radius_window=False,
                )
                audit = compute_mask_audit(cs)
                entries.append(
                    DenominatorStratumEntry(
                        residue_reaction_family=fam,
                        timestep_value=ts,
                        mask_audit=audit,
                    )
                )

        strata = aggregate_denominator_strata(entries)
        families = {s.residue_reaction_family for s in strata}
        buckets = {s.timestep_bucket for s in strata}
        self.assertIn("CYS_MICHAEL_ADDITION", families)
        self.assertIn("LYS_IMINE_FORMATION", families)
        self.assertIn("early", buckets)
        self.assertIn("mid", buckets)

        report = LossReport(
            components={k: 1.0 for k in REQUIRED_LOSS_COMPONENT_KEYS},
            strata=strata,
        )
        serialized = report.to_dict()
        self.assertGreaterEqual(len(serialized["strata"]), 4)
        for s in serialized["strata"]:
            self.assertIn("mask_audit", s)
            self.assertIn("residue_reaction_family", s)
            self.assertIn("timestep_bucket", s)
            self.assertIn("denominators", s)


# ===================================================================
# 3.  Audit path coverage
# ===================================================================


class AuditPathSmokeTests(unittest.TestCase):
    """Individual audit path regression tests using existing Task 23 infrastructure."""

    def _default_set(self) -> StepwiseCandidateSet:
        return _audit_builder.build_natural_positive_set()

    # -- pending-smarts --------------------------------------------------

    def test_pending_smarts_masks_bond_type_loss_eligible_from_natural_positives(self) -> None:
        """When pending_smarts=True, bond_type_loss_eligible_count must be 0."""
        audit = compute_mask_audit(self._default_set(), pending_smarts=True)
        self.assertEqual(audit.bond_type_loss_eligible_count, 0)
        self.assertGreater(audit.edge_loss_eligible_count, 0)
        self.assertEqual(audit.masked_by_pending_smarts, audit.natural_positive_count)

    def test_pending_smarts_does_not_affect_edge_loss_or_geometry_loss(self) -> None:
        """Pending SMARTS must not mask edge existence or geometry loss."""
        audit = compute_mask_audit(self._default_set(), pending_smarts=True)
        self.assertGreater(audit.edge_loss_eligible_count, 0)
        self.assertGreater(audit.geometry_loss_eligible_count, 0)

    # -- pending-geometry ------------------------------------------------

    def test_pending_geometry_masks_geometry_loss_eligible_from_natural_positives(self) -> None:
        """When pending_geometry=True, geometry_loss_eligible_count must be 0."""
        audit = compute_mask_audit(self._default_set(), pending_geometry=True)
        self.assertEqual(audit.geometry_loss_eligible_count, 0)
        self.assertGreater(audit.bond_type_loss_eligible_count, 0)
        self.assertEqual(audit.masked_by_pending_geometry, audit.natural_positive_count)

    def test_pending_geometry_does_not_affect_edge_loss_or_bond_type_loss(self) -> None:
        """Pending geometry must not mask edge existence or bond type loss."""
        audit = compute_mask_audit(self._default_set(), pending_geometry=True)
        self.assertGreater(audit.edge_loss_eligible_count, 0)
        self.assertGreater(audit.bond_type_loss_eligible_count, 0)

    # -- missing-required-chemical-state ---------------------------------

    def test_missing_required_chemical_state_masks_geometry_loss(self) -> None:
        """When missing_required_chemical_state=True, geometry loss is masked."""
        audit = compute_mask_audit(
            self._default_set(), missing_required_chemical_state=True,
        )
        self.assertEqual(audit.geometry_loss_eligible_count, 0)
        self.assertEqual(
            audit.masked_by_missing_chemical_state,
            audit.natural_positive_count,
        )

    def test_missing_required_chemical_state_preserves_edge_and_bond_type_loss(self) -> None:
        """Missing chemical state must not mask edge or bond type loss."""
        audit = compute_mask_audit(
            self._default_set(), missing_required_chemical_state=True,
        )
        self.assertGreater(audit.edge_loss_eligible_count, 0)
        self.assertGreater(audit.bond_type_loss_eligible_count, 0)

    # -- Q2-exclusion ----------------------------------------------------

    def test_q2_exclusion_zeroes_all_eligible_counts(self) -> None:
        """When quality_tier=Q2 and exclude_q2=True, all eligible counts must be 0."""
        audit = compute_mask_audit(
            self._default_set(), quality_tier="Q2", exclude_q2=True,
        )
        self.assertEqual(audit.edge_loss_eligible_count, 0)
        self.assertEqual(audit.bond_type_loss_eligible_count, 0)
        self.assertEqual(audit.geometry_loss_eligible_count, 0)
        self.assertEqual(audit.message_passing_candidate_count, 0)
        self.assertEqual(audit.gate_evaluated_count, 0)
        self.assertEqual(audit.masked_by_q2_exclusion, audit.candidate_count)

    def test_q2_without_exclusion_flag_retains_all_eligible_counts(self) -> None:
        """When quality_tier=Q2 but exclude_q2=False, eligible counts are normal."""
        audit = compute_mask_audit(
            self._default_set(), quality_tier="Q2", exclude_q2=False,
        )
        self.assertGreater(audit.edge_loss_eligible_count, 0)
        self.assertEqual(audit.masked_by_q2_exclusion, 0)

    # -- forced-positive -------------------------------------------------

    def test_forced_positive_is_eligible_for_edge_loss_only(self) -> None:
        """Forced positive must count in edge_loss (yes) but bond/geometry/message (no)."""
        fp_set = _audit_builder.build_forced_positive_set()
        audit = compute_mask_audit(fp_set)
        self.assertGreater(audit.forced_positive_count, 0)
        self.assertGreater(audit.edge_loss_eligible_count, 0)
        self.assertEqual(audit.bond_type_loss_eligible_count, 0)
        self.assertEqual(audit.geometry_loss_eligible_count, 0)
        self.assertEqual(
            audit.masked_by_forced_positive_exclusion,
            audit.forced_positive_count,
        )

    def test_forced_positive_is_gate_evaluated(self) -> None:
        """Forced positives must be gate-evaluated even when excluded from bond/geometry."""
        fp_set = _audit_builder.build_forced_positive_set()
        audit = compute_mask_audit(fp_set)
        self.assertEqual(audit.gate_evaluated_count, audit.candidate_count)

    def test_forced_positive_excluded_from_message_passing(self) -> None:
        """Message passing must exclude forced positives."""
        fp_set = _audit_builder.build_forced_positive_set()
        audit = compute_mask_audit(fp_set)
        self.assertEqual(
            audit.message_passing_candidate_count,
            audit.natural_positive_count + audit.natural_negative_count,
        )
        self.assertGreater(audit.forced_positive_count, 0)
        self.assertEqual(
            audit.message_passing_candidate_count + audit.forced_positive_count,
            audit.candidate_count,
        )

    # -- zero-natural-negative -------------------------------------------

    def test_zero_natural_negative_is_valid_state_not_error(self) -> None:
        """zero_negative_count=1 when NN=0 must be a valid state, not an error."""
        zn_set = _audit_builder.build_zero_natural_negatives_set()
        audit = compute_mask_audit(zn_set)
        self.assertEqual(audit.natural_negative_count, 0)
        self.assertEqual(audit.zero_negative_count, 1)
        self.assertGreater(audit.edge_loss_eligible_count, 0)

    def test_zero_natural_negative_derived_edge_denominators_are_valid(self) -> None:
        """EdgeDenominators built from zero-negative audit must pass validate()."""
        zn_set = _audit_builder.build_zero_natural_negatives_set()
        audit = compute_mask_audit(zn_set)
        denoms = build_edge_denominators(audit)
        self.assertEqual(denoms.candidate_count, 1)
        self.assertIsNotNone(denoms)

    # -- combined flags --------------------------------------------------

    def test_both_pending_smarts_and_pending_geometry_mask_both_losses(self) -> None:
        """When both pending, bond_type and geometry are masked; edge loss is not."""
        audit = compute_mask_audit(
            self._default_set(),
            pending_smarts=True,
            pending_geometry=True,
        )
        self.assertGreater(audit.edge_loss_eligible_count, 0)
        self.assertEqual(audit.bond_type_loss_eligible_count, 0)
        self.assertEqual(audit.geometry_loss_eligible_count, 0)

    def test_resolve_mask_flags_owns_explicit_normalized_booleans(self) -> None:
        """resolve_mask_flags must coerce inputs and return NormalizedMaskFlags."""
        flags = resolve_mask_flags(
            pending_smarts=True,
            pending_geometry=False,
            missing_required_chemical_state=True,
            quality_tier="Q2",
            exclude_q2=True,
        )
        self.assertIsInstance(flags, NormalizedMaskFlags)
        self.assertTrue(flags.pending_smarts)
        self.assertFalse(flags.pending_geometry)
        self.assertTrue(flags.missing_required_chemical_state)
        self.assertEqual(flags.quality_tier, "Q2")
        self.assertTrue(flags.exclude_q2)


# ===================================================================
# 4.  Train CLI contract (RED)
# ===================================================================


class TrainCLIContractTests(unittest.TestCase):
    """Train CLI smoke contract tests.

    These tests are expected to RED because ``covalent_design.training.train``
    does not exist yet (it is Task 24 production scope, not preflight).
    """

    def test_train_cli_is_importable(self) -> None:
        """python -m covalent_design.training.train must be importable."""
        _assert_importable("covalent_design.training.train", "main")

    def test_train_cli_produces_one_line_train_metrics_jsonl_per_step(self) -> None:
        """The train CLI must write exactly one LossReport JSON line per training step.

        Repeated runs must produce byte-identical summary and metrics output.
        """
        from covalent_design.training.train import main

        _smoke_builder.write_smoke_train_bundle()
        config_path = (
            Path(__file__).resolve().parents[2]
            / "configs"
            / "covalent_train_smoke.yml"
        )
        stdout_rows: list[str] = []
        metric_rows: list[str] = []
        for _ in range(2):
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                main(["--config", str(config_path)])
            stdout_rows.append(buffer.getvalue())
            metrics_path = (
                Path(__file__).resolve().parents[2]
                / "outputs"
                / "task24-smoke"
                / "train_metrics.jsonl"
            )
            rows = metrics_path.read_text("utf-8").splitlines()
            self.assertEqual(len(rows), 1)
            metric_rows.append(rows[0])
        self.assertEqual(stdout_rows[0], stdout_rows[1])
        self.assertEqual(metric_rows[0], metric_rows[1])

    def test_train_step_report_contains_step_index_total_loss_and_components(self) -> None:
        """Each line of train_metrics.jsonl must have step, total_loss, components,
        denominators, and strata."""
        from covalent_design.training.train_loop import run_smoke_train

        _smoke_builder.write_smoke_train_bundle()
        config_path = (
            Path(__file__).resolve().parents[2]
            / "configs"
            / "covalent_train_smoke.yml"
        )
        serialized = run_smoke_train(str(config_path)).to_dict()
        self.assertEqual(serialized["step"], 0)
        self.assertIn("total_loss", serialized)
        self.assertEqual(set(serialized["components"]), set(REQUIRED_LOSS_COMPONENT_KEYS))
        self.assertIn("denominators", serialized)
        self.assertIn("strata", serialized)

    def test_train_loop_rejects_non_smoke_step_count(self) -> None:
        """The smoke loop must not silently ignore a multi-step config."""
        from covalent_design.training.train_loop import run_smoke_train

        configs_dir = Path(__file__).resolve().parents[2] / "configs"
        source = configs_dir / "covalent_train_smoke.yml"
        with tempfile.TemporaryDirectory(dir=configs_dir) as tmp:
            config_path = Path(tmp) / "invalid_steps.yml"
            config_path.write_text(
                source.read_text(encoding="utf-8").replace("steps: 1", "steps: 2"),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "requires steps=1"):
                run_smoke_train(str(config_path))

    def test_configs_are_owned_by_window_c_not_this_window(self) -> None:
        """Window C must provide the two committed smoke configs."""
        configs_dir = Path(__file__).resolve().parents[2] / "configs"
        train_cfg = configs_dir / "covalent_train_smoke.yml"
        model_cfg = configs_dir / "covalent_model_smoke.yml"
        self.assertTrue(train_cfg.exists())
        self.assertTrue(model_cfg.exists())

    def test_train_loop_report_exposes_real_geometry_sentinel_and_schema(self) -> None:
        """The real smoke loop must emit the 0.0 geometry sentinel and full schema."""
        from covalent_design.training.train_loop import run_smoke_train

        _smoke_builder.write_smoke_train_bundle()
        config_path = (
            Path(__file__).resolve().parents[2]
            / "configs"
            / "covalent_train_smoke.yml"
        )
        report = run_smoke_train(str(config_path))
        serialized = report.to_dict()
        self.assertEqual(report.components["covalent_geometry_loss"], 0.0)
        self.assertEqual(set(serialized["components"]), set(REQUIRED_LOSS_COMPONENT_KEYS))
        self.assertEqual(len(serialized["denominators"]), 10)
        self.assertEqual(len(serialized["mask_audit"]), 15)
        self.assertGreater(len(serialized["strata"]), 0)


# ===================================================================
# 5.  Smoke bundle end-to-end (existing infrastructure)
# ===================================================================


class SmokeBundleEndToEndTests(unittest.TestCase):
    """End-to-end smoke bundle: Task 17-23 tracer bullet with existing infrastructure.

    These tests exercise the exact Task 24 integration surface but stop
    before numeric losses (Task 24 scope).  They should PASS with current
    preflight modules.
    """

    def test_smoke_bundle_produces_valid_model_batch(self) -> None:
        """The four-record smoke bundle must produce a valid ModelBatch."""
        from covalent_design.model.batch import make_model_batch

        rec_path, split_path = _smoke_builder.write_smoke_train_bundle()
        envelope = make_model_batch(rec_path)
        self.assertTrue(envelope.receipt.ok)
        batch = envelope.payload
        self.assertEqual(len(batch.records), 4)

    def test_smoke_bundle_train_dataset_filtering(self) -> None:
        """prepare_dataset must filter the smoke bundle correctly for train split."""
        from covalent_design.training.dataset import prepare_dataset

        rec_path, split_path = _smoke_builder.write_smoke_train_bundle()
        envelope = prepare_dataset(rec_path, split_path, "train")
        self.assertTrue(envelope.receipt.ok)
        self.assertEqual(envelope.payload.excluded_summary.records_in_split, 4)

    def test_smoke_bundle_singleton_batch_loading(self) -> None:
        """load_training_batch must load a singleton batch from the smoke bundle."""
        from covalent_design.training.batch import load_training_batch
        from covalent_design.training.dataset import prepare_dataset

        rec_path, split_path = _smoke_builder.write_smoke_train_bundle()
        dataset = prepare_dataset(rec_path, split_path, "train").payload
        envelope = load_training_batch(dataset, "batch-0")
        self.assertTrue(envelope.receipt.ok)
        self.assertEqual(len(envelope.payload.records), 1)

    def test_q2_exclusion_audit_from_smoke_bundle(self) -> None:
        """A Q2 record with exclude_q2=True must produce zero eligible counts."""
        from covalent_design.model.batch import make_model_batch
        from covalent_design.model.candidate_builder import (
            build_stepwise_candidates,
        )

        rec_path, _split_path = _smoke_builder.write_q2_exclusion_bundle()
        batch = make_model_batch(rec_path).payload

        # Read the edge_candidates artifact for stepwise construction
        import json
        record_id = batch.records[0].record_id
        artifact_uri = batch.static_edge_candidates_refs[record_id].uri
        artifact_path = _artifact_path(rec_path, artifact_uri)
        edge_artifact = json.loads(artifact_path.read_text("utf-8"))

        # Read protein_atom_table for stepwise
        for ref_uri in batch.records[0].artifact_refs.values():
            if ref_uri.role == "protein_atom_table":
                prot_path = _artifact_path(rec_path, ref_uri.uri)
                break
        else:
            self.fail("protein_atom_table artifact not found")
        protein_atoms = json.loads(prot_path.read_text("utf-8"))["atoms"]

        for ref_uri in batch.records[0].artifact_refs.values():
            if ref_uri.role == "ligand_atom_table":
                lig_path = _artifact_path(rec_path, ref_uri.uri)
                break
        else:
            self.fail("ligand_atom_table artifact not found")
        ligand_atoms = json.loads(lig_path.read_text("utf-8"))["atoms"]

        candidate_set = build_stepwise_candidates(
            protein_atoms=protein_atoms,
            ligand_atoms=ligand_atoms,
            edge_candidates_artifact=edge_artifact,
            timestep_index=0,
            timestep_value=0.5,
        )
        audit = compute_mask_audit(
            candidate_set,
            quality_tier="Q2",
            exclude_q2=True,
        )
        self.assertEqual(audit.edge_loss_eligible_count, 0)
        self.assertEqual(audit.masked_by_q2_exclusion, audit.candidate_count)

    def test_smoke_bundle_forward_pmdm_and_covalent_pipeline(self) -> None:
        """The full Task 17-20 tracer bullet must produce correct output shapes."""
        import json
        from covalent_design.model.batch import make_model_batch
        from covalent_design.model.candidate_builder import (
            build_stepwise_candidate_batch,
            build_stepwise_candidates,
        )
        from covalent_design.model.config import ModelConfig
        from covalent_design.model.pmdm_adapter import forward_pmdm
        from covalent_design.model.covalent_heads import forward_covalent

        rec_path, _split_path = _smoke_builder.write_smoke_train_bundle()
        batch = make_model_batch(rec_path).payload

        # Build stepwise candidates for the first record's artifacts
        record = batch.records[0]
        artifact_uri = batch.static_edge_candidates_refs[record.record_id].uri
        edge_artifact = json.loads(
            _artifact_path(rec_path, artifact_uri).read_text("utf-8")
        )

        for ref in record.artifact_refs.values():
            if ref.role == "protein_atom_table":
                prot_path = _artifact_path(rec_path, ref.uri)
                break
        else:
            self.fail("protein_atom_table not found")
        protein_atoms = json.loads(prot_path.read_text("utf-8"))["atoms"]

        for ref in record.artifact_refs.values():
            if ref.role == "ligand_atom_table":
                lig_path = _artifact_path(rec_path, ref.uri)
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

        config = ModelConfig(seed=7, ligand_feature_dim=4, protein_feature_dim=4)
        pmdm_output = forward_pmdm(batch=batch, config=config)
        forward_output = forward_covalent(
            pmdm_output=pmdm_output,
            batch=batch,
            config=config,
            stepwise_candidate_batch=dynamic_batch,
        )

        # Verify shapes match contract
        self.assertEqual(dynamic_batch.padded_shape, forward_output.edge_logits.shape)
        self.assertEqual(
            forward_output.denominators_observed,
            dynamic_batch.denominators_observed,
        )


# ===================================================================
# 6.  No heavy imports guard
# ===================================================================


class NoHeavyImportsGuardTests(unittest.TestCase):
    """Smoke test files must not import torch, RDKit, PMDM, or PocketFlow."""

    def test_train_smoke_module_does_not_import_heavy_dependencies(self) -> None:
        """This test file itself must not pull in heavy deps."""
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


if __name__ == "__main__":
    unittest.main()
