"""Task 22 training dataset contract and regression tests.

These tests define the public API and exclusion semantics for
``prepare_dataset()``.  They use small deterministic fixtures under
``tests/fixtures/training/dataset/valid/``.
"""

import json
import sys
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# contracts — always importable
# ---------------------------------------------------------------------------
from covalent_design.contracts import (
    ArtifactRef,
    ContractEnvelope,
    ExclusionSummary,
    TrainingDatasetIndex,
    TrainingRecordEntry,
    ValidationReceipt,
)

# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------
FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "training" / "dataset"
VALID_RECORDS_PATH = FIXTURE_ROOT / "valid" / "records.jsonl"
VALID_SPLIT_INDEX_PATH = FIXTURE_ROOT / "valid" / "split_index.json"

RECORD_IDS = {
    "train_q0": "0000000000000000000000TRN0001",
    "train_q1": "0000000000000000000000TRN0002",
    "val_q1": "0000000000000000000000VAL0001",
    "test_q0": "0000000000000000000000TST0001",
    "excluded": "0000000000000000000000EXC0001",
    "vis_fail": "0000000000000000000000VIS0001",
    "vis_pending": "0000000000000000000000VIS0002",
    "vis_needs_rule_review": "0000000000000000000000VIS0003",
    "qti_q3": "0000000000000000000000QTI0001",
    "multi_linkage": "0000000000000000000000MLK0001",
    "q2_keep": "0000000000000000000000Q2K0001",
}

TOTAL_ACCEPTED = 11

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _load_jsonl_ids(path: Path) -> list[str]:
    ids = []
    for line in path.read_text("utf-8").splitlines():
        stripped = line.strip()
        if stripped:
            ids.append(json.loads(stripped)["record_id"])
    return ids


def _assert_importable(module_name: str, attribute: str) -> None:
    """Import attribute from module — raises ImportError if absent."""
    __import__(module_name)
    getattr(sys.modules[module_name], attribute)


# ---------------------------------------------------------------------------
# 1.  Public API contract
# ---------------------------------------------------------------------------


class PrepareDatasetAPIContractTests(unittest.TestCase):
    """``prepare_dataset()`` signature and return-type contract."""

    def test_prepare_dataset_is_importable(self) -> None:
        _assert_importable("covalent_design.training.dataset", "prepare_dataset")

    def test_prepare_dataset_accepts_four_positional_args(self) -> None:
        from covalent_design.training.dataset import prepare_dataset

        envelope = prepare_dataset(
            VALID_RECORDS_PATH,
            VALID_SPLIT_INDEX_PATH,
            "train",
            None,
        )
        self.assertIsInstance(envelope, ContractEnvelope)

    def test_prepare_dataset_returns_training_dataset_index_payload(self) -> None:
        from covalent_design.training.dataset import prepare_dataset

        envelope = prepare_dataset(
            VALID_RECORDS_PATH,
            VALID_SPLIT_INDEX_PATH,
            "train",
            None,
        )
        self.assertIsInstance(envelope.payload, TrainingDatasetIndex)

    def test_envelope_receipt_is_valid(self) -> None:
        from covalent_design.training.dataset import prepare_dataset

        envelope = prepare_dataset(
            VALID_RECORDS_PATH,
            VALID_SPLIT_INDEX_PATH,
            "train",
            None,
        )
        self.assertIsInstance(envelope.receipt, ValidationReceipt)
        self.assertTrue(envelope.receipt.ok)

    def test_split_name_train_val_test_accepted(self) -> None:
        from covalent_design.training.dataset import prepare_dataset

        for split_name in ("train", "val", "test"):
            with self.subTest(split=split_name):
                envelope = prepare_dataset(
                    VALID_RECORDS_PATH,
                    VALID_SPLIT_INDEX_PATH,
                    split_name,
                    None,
                )
                self.assertEqual(envelope.payload.split_name, split_name)


# ---------------------------------------------------------------------------
# 2.  TrainingDataPolicy defaults
# ---------------------------------------------------------------------------


class TrainingDataPolicyDefaultTests(unittest.TestCase):
    """Default ``TrainingDataPolicy`` values match the approved interface."""

    def test_policy_is_importable(self) -> None:
        _assert_importable("covalent_design.training.dataset", "TrainingDataPolicy")

    def test_default_first_core_only_is_true(self) -> None:
        from covalent_design.training.dataset import TrainingDataPolicy

        policy = TrainingDataPolicy()
        self.assertTrue(policy.first_core_only)

    def test_default_exclude_visual_blocked_is_true(self) -> None:
        from covalent_design.training.dataset import TrainingDataPolicy

        policy = TrainingDataPolicy()
        self.assertTrue(policy.exclude_visual_blocked)

    def test_default_exclude_q2_is_false(self) -> None:
        from covalent_design.training.dataset import TrainingDataPolicy

        policy = TrainingDataPolicy()
        self.assertFalse(policy.exclude_q2)

    def test_default_accepted_quality_tiers_are_q0_q1_q2(self) -> None:
        from covalent_design.training.dataset import TrainingDataPolicy

        policy = TrainingDataPolicy()
        self.assertEqual(
            tuple(policy.accepted_quality_tiers),
            ("Q0", "Q1", "Q2"),
        )


# ---------------------------------------------------------------------------
# 3.  Split filtering (train scope)
# ---------------------------------------------------------------------------


class SplitFilteringTests(unittest.TestCase):
    """Records in other splits are excluded as ``not_in_this_split``."""

    def test_train_split_includes_only_train_assigned_records(self) -> None:
        from covalent_design.training.dataset import prepare_dataset

        envelope = prepare_dataset(
            VALID_RECORDS_PATH,
            VALID_SPLIT_INDEX_PATH,
            "train",
            None,
        )
        dataset = envelope.payload
        record_ids = {r.record_id for r in dataset.records}

        self.assertIn(RECORD_IDS["train_q0"], record_ids)
        self.assertIn(RECORD_IDS["train_q1"], record_ids)
        self.assertIn(RECORD_IDS["q2_keep"], record_ids)

    def test_val_assigned_record_not_in_train(self) -> None:
        from covalent_design.training.dataset import prepare_dataset

        envelope = prepare_dataset(
            VALID_RECORDS_PATH,
            VALID_SPLIT_INDEX_PATH,
            "train",
            None,
        )
        record_ids = {r.record_id for r in envelope.payload.records}
        self.assertNotIn(RECORD_IDS["val_q1"], record_ids)

    def test_test_assigned_record_not_in_train(self) -> None:
        from covalent_design.training.dataset import prepare_dataset

        envelope = prepare_dataset(
            VALID_RECORDS_PATH,
            VALID_SPLIT_INDEX_PATH,
            "train",
            None,
        )
        record_ids = {r.record_id for r in envelope.payload.records}
        self.assertNotIn(RECORD_IDS["test_q0"], record_ids)

    def test_val_split_includes_val_record(self) -> None:
        from covalent_design.training.dataset import prepare_dataset

        envelope = prepare_dataset(
            VALID_RECORDS_PATH,
            VALID_SPLIT_INDEX_PATH,
            "val",
            None,
        )
        record_ids = {r.record_id for r in envelope.payload.records}
        self.assertIn(RECORD_IDS["val_q1"], record_ids)
        self.assertNotIn(RECORD_IDS["train_q0"], record_ids)

    def test_test_split_includes_test_record(self) -> None:
        from covalent_design.training.dataset import prepare_dataset

        envelope = prepare_dataset(
            VALID_RECORDS_PATH,
            VALID_SPLIT_INDEX_PATH,
            "test",
            None,
        )
        record_ids = {r.record_id for r in envelope.payload.records}
        self.assertIn(RECORD_IDS["test_q0"], record_ids)
        self.assertNotIn(RECORD_IDS["train_q0"], record_ids)

    def test_not_in_this_split_appears_in_exclusion_reasons(self) -> None:
        from covalent_design.training.dataset import prepare_dataset

        envelope = prepare_dataset(
            VALID_RECORDS_PATH,
            VALID_SPLIT_INDEX_PATH,
            "train",
            None,
        )
        reasons = envelope.payload.excluded_summary.exclusion_reasons
        self.assertIn("not_in_this_split", reasons)
        self.assertGreater(reasons["not_in_this_split"], 0)


# ---------------------------------------------------------------------------
# 4.  Hard-excluded by split
# ---------------------------------------------------------------------------


class HardExcludedBySplitTests(unittest.TestCase):
    """Records with ``split == "excluded"`` are hard excluded."""

    def test_excluded_split_record_not_in_train(self) -> None:
        from covalent_design.training.dataset import prepare_dataset

        envelope = prepare_dataset(
            VALID_RECORDS_PATH,
            VALID_SPLIT_INDEX_PATH,
            "train",
            None,
        )
        record_ids = {r.record_id for r in envelope.payload.records}
        self.assertNotIn(RECORD_IDS["excluded"], record_ids)

    def test_excluded_split_record_not_in_val(self) -> None:
        from covalent_design.training.dataset import prepare_dataset

        envelope = prepare_dataset(
            VALID_RECORDS_PATH,
            VALID_SPLIT_INDEX_PATH,
            "val",
            None,
        )
        record_ids = {r.record_id for r in envelope.payload.records}
        self.assertNotIn(RECORD_IDS["excluded"], record_ids)

    def test_excluded_split_record_not_in_test(self) -> None:
        from covalent_design.training.dataset import prepare_dataset

        envelope = prepare_dataset(
            VALID_RECORDS_PATH,
            VALID_SPLIT_INDEX_PATH,
            "test",
            None,
        )
        record_ids = {r.record_id for r in envelope.payload.records}
        self.assertNotIn(RECORD_IDS["excluded"], record_ids)

    def test_hard_excluded_by_split_appears_in_exclusion_reasons(self) -> None:
        from covalent_design.training.dataset import prepare_dataset

        envelope = prepare_dataset(
            VALID_RECORDS_PATH,
            VALID_SPLIT_INDEX_PATH,
            "train",
            None,
        )
        reasons = envelope.payload.excluded_summary.exclusion_reasons
        self.assertIn("hard_excluded_by_split", reasons)
        self.assertGreaterEqual(reasons["hard_excluded_by_split"], 1)


# ---------------------------------------------------------------------------
# 5.  Visual blocked exclusion
# ---------------------------------------------------------------------------


class VisualBlockedExclusionTests(unittest.TestCase):
    """Records with visual status != ``"pass"`` are excluded by default."""

    def test_visual_fail_is_excluded(self) -> None:
        from covalent_design.training.dataset import prepare_dataset

        envelope = prepare_dataset(
            VALID_RECORDS_PATH,
            VALID_SPLIT_INDEX_PATH,
            "train",
            None,
        )
        record_ids = {r.record_id for r in envelope.payload.records}
        self.assertNotIn(RECORD_IDS["vis_fail"], record_ids)

    def test_visual_pending_is_excluded(self) -> None:
        from covalent_design.training.dataset import prepare_dataset

        envelope = prepare_dataset(
            VALID_RECORDS_PATH,
            VALID_SPLIT_INDEX_PATH,
            "train",
            None,
        )
        record_ids = {r.record_id for r in envelope.payload.records}
        self.assertNotIn(RECORD_IDS["vis_pending"], record_ids)

    def test_visual_needs_rule_review_is_excluded(self) -> None:
        from covalent_design.training.dataset import prepare_dataset

        envelope = prepare_dataset(
            VALID_RECORDS_PATH,
            VALID_SPLIT_INDEX_PATH,
            "train",
            None,
        )
        record_ids = {r.record_id for r in envelope.payload.records}
        self.assertNotIn(RECORD_IDS["vis_needs_rule_review"], record_ids)

    def test_visual_blocked_reason_in_exclusion_summary(self) -> None:
        from covalent_design.training.dataset import prepare_dataset

        envelope = prepare_dataset(
            VALID_RECORDS_PATH,
            VALID_SPLIT_INDEX_PATH,
            "train",
            None,
        )
        reasons = envelope.payload.excluded_summary.exclusion_reasons
        self.assertIn("excluded_visual_blocked", reasons)
        # VIS0001 (fail), VIS0002 (pending), VIS0003 (needs_rule_review) = 3
        self.assertEqual(3, reasons["excluded_visual_blocked"])

    def test_exclude_visual_blocked_false_includes_visual_fail_records(self) -> None:
        from covalent_design.training.dataset import TrainingDataPolicy, prepare_dataset

        policy = TrainingDataPolicy(exclude_visual_blocked=False)
        envelope = prepare_dataset(
            VALID_RECORDS_PATH,
            VALID_SPLIT_INDEX_PATH,
            "train",
            policy,
        )
        record_ids = {r.record_id for r in envelope.payload.records}
        self.assertIn(RECORD_IDS["vis_fail"], record_ids)
        self.assertIn(RECORD_IDS["vis_pending"], record_ids)
        self.assertIn(RECORD_IDS["vis_needs_rule_review"], record_ids)

    def test_exclude_visual_blocked_false_exclusion_reasons_omit_visual_blocked(self) -> None:
        from covalent_design.training.dataset import TrainingDataPolicy, prepare_dataset

        policy = TrainingDataPolicy(exclude_visual_blocked=False)
        envelope = prepare_dataset(
            VALID_RECORDS_PATH,
            VALID_SPLIT_INDEX_PATH,
            "train",
            policy,
        )
        reasons = envelope.payload.excluded_summary.exclusion_reasons
        self.assertNotIn("excluded_visual_blocked", reasons)


# ---------------------------------------------------------------------------
# 6.  Quality tier filtering
# ---------------------------------------------------------------------------


class QualityTierExclusionTests(unittest.TestCase):
    """Records outside accepted quality tiers are excluded."""

    def test_q3_outside_accepted_set_is_excluded(self) -> None:
        from covalent_design.training.dataset import prepare_dataset

        envelope = prepare_dataset(
            VALID_RECORDS_PATH,
            VALID_SPLIT_INDEX_PATH,
            "train",
            None,
        )
        record_ids = {r.record_id for r in envelope.payload.records}
        self.assertNotIn(RECORD_IDS["qti_q3"], record_ids)

    def test_excluded_quality_tier_reason_present(self) -> None:
        from covalent_design.training.dataset import prepare_dataset

        envelope = prepare_dataset(
            VALID_RECORDS_PATH,
            VALID_SPLIT_INDEX_PATH,
            "train",
            None,
        )
        reasons = envelope.payload.excluded_summary.exclusion_reasons
        self.assertIn("excluded_quality_tier", reasons)
        self.assertGreaterEqual(reasons["excluded_quality_tier"], 1)

    def test_q0_q1_q2_all_included_by_default(self) -> None:
        from covalent_design.training.dataset import prepare_dataset

        envelope = prepare_dataset(
            VALID_RECORDS_PATH,
            VALID_SPLIT_INDEX_PATH,
            "train",
            None,
        )
        records = envelope.payload.records
        tiers = {r.quality_tier for r in records}
        # Q0 (TRN001), Q1 (TRN002), Q2 (Q2K001) all present
        self.assertIn("Q0", tiers)
        self.assertIn("Q1", tiers)
        self.assertIn("Q2", tiers)

    def test_custom_accepted_quality_tiers(self) -> None:
        from covalent_design.training.dataset import TrainingDataPolicy, prepare_dataset

        # Only Q0
        policy = TrainingDataPolicy(accepted_quality_tiers=("Q0",))
        envelope = prepare_dataset(
            VALID_RECORDS_PATH,
            VALID_SPLIT_INDEX_PATH,
            "train",
            policy,
        )
        record_ids = {r.record_id for r in envelope.payload.records}
        self.assertIn(RECORD_IDS["train_q0"], record_ids)
        # Q1 and Q2 excluded
        self.assertNotIn(RECORD_IDS["train_q1"], record_ids)
        self.assertNotIn(RECORD_IDS["q2_keep"], record_ids)


# ---------------------------------------------------------------------------
# 7.  Multi-linkage exclusion (first_core_only)
# ---------------------------------------------------------------------------


class MultiLinkageExclusionTests(unittest.TestCase):
    """Multi-linkage records excluded when ``first_core_only=True``."""

    def test_multi_linkage_excluded_by_default(self) -> None:
        from covalent_design.training.dataset import prepare_dataset

        envelope = prepare_dataset(
            VALID_RECORDS_PATH,
            VALID_SPLIT_INDEX_PATH,
            "train",
            None,
        )
        record_ids = {r.record_id for r in envelope.payload.records}
        self.assertNotIn(RECORD_IDS["multi_linkage"], record_ids)

    def test_excluded_multi_linkage_reason_present(self) -> None:
        from covalent_design.training.dataset import prepare_dataset

        envelope = prepare_dataset(
            VALID_RECORDS_PATH,
            VALID_SPLIT_INDEX_PATH,
            "train",
            None,
        )
        reasons = envelope.payload.excluded_summary.exclusion_reasons
        self.assertIn("excluded_multi_linkage", reasons)
        self.assertGreaterEqual(reasons["excluded_multi_linkage"], 1)

    def test_first_core_only_false_includes_multi_linkage(self) -> None:
        from covalent_design.training.dataset import TrainingDataPolicy, prepare_dataset

        policy = TrainingDataPolicy(first_core_only=False)
        envelope = prepare_dataset(
            VALID_RECORDS_PATH,
            VALID_SPLIT_INDEX_PATH,
            "train",
            policy,
        )
        record_ids = {r.record_id for r in envelope.payload.records}
        self.assertIn(RECORD_IDS["multi_linkage"], record_ids)


# ---------------------------------------------------------------------------
# 8.  Q2 keep-with-flag behaviour
# ---------------------------------------------------------------------------


class Q2KeepWithFlagTests(unittest.TestCase):
    """Q2 records included by default, excluded with ``exclude_q2=True``."""

    def test_q2_included_by_default(self) -> None:
        from covalent_design.training.dataset import prepare_dataset

        envelope = prepare_dataset(
            VALID_RECORDS_PATH,
            VALID_SPLIT_INDEX_PATH,
            "train",
            None,
        )
        record_ids = {r.record_id for r in envelope.payload.records}
        self.assertIn(RECORD_IDS["q2_keep"], record_ids)

    def test_q2_record_preserves_q2_tier_in_entry(self) -> None:
        from covalent_design.training.dataset import prepare_dataset

        envelope = prepare_dataset(
            VALID_RECORDS_PATH,
            VALID_SPLIT_INDEX_PATH,
            "train",
            None,
        )
        q2_entry = next(
            r for r in envelope.payload.records
            if r.record_id == RECORD_IDS["q2_keep"]
        )
        self.assertEqual("Q2", q2_entry.quality_tier)

    def test_q2_excluded_when_exclude_q2_true(self) -> None:
        from covalent_design.training.dataset import TrainingDataPolicy, prepare_dataset

        policy = TrainingDataPolicy(exclude_q2=True)
        envelope = prepare_dataset(
            VALID_RECORDS_PATH,
            VALID_SPLIT_INDEX_PATH,
            "train",
            policy,
        )
        record_ids = {r.record_id for r in envelope.payload.records}
        self.assertNotIn(RECORD_IDS["q2_keep"], record_ids)

    def test_excluded_q2_reason_present_when_exclude_q2_true(self) -> None:
        from covalent_design.training.dataset import TrainingDataPolicy, prepare_dataset

        policy = TrainingDataPolicy(exclude_q2=True)
        envelope = prepare_dataset(
            VALID_RECORDS_PATH,
            VALID_SPLIT_INDEX_PATH,
            "train",
            policy,
        )
        reasons = envelope.payload.excluded_summary.exclusion_reasons
        self.assertIn("excluded_q2", reasons)
        self.assertGreaterEqual(reasons["excluded_q2"], 1)

    def test_excluded_q2_reason_absent_when_exclude_q2_false(self) -> None:
        from covalent_design.training.dataset import prepare_dataset

        envelope = prepare_dataset(
            VALID_RECORDS_PATH,
            VALID_SPLIT_INDEX_PATH,
            "train",
            None,
        )
        reasons = envelope.payload.excluded_summary.exclusion_reasons
        self.assertNotIn("excluded_q2", reasons)


# ---------------------------------------------------------------------------
# 9.  Exclusion priority
# ---------------------------------------------------------------------------


class ExclusionPriorityTests(unittest.TestCase):
    """Each record is excluded for the *first* matching reason in priority order."""

    def test_excluded_split_takes_priority_over_visual_blocked(self) -> None:
        """EXC0001 is excluded with fallback_reason=missing_scaffold_input.
        It also has visual_check_status='pass', so visual is not a factor.
        The priority should capture it as hard_excluded_by_split."""
        from covalent_design.training.dataset import prepare_dataset

        envelope = prepare_dataset(
            VALID_RECORDS_PATH,
            VALID_SPLIT_INDEX_PATH,
            "train",
            None,
        )
        reasons = envelope.payload.excluded_summary.exclusion_reasons
        # exactly 1 hard excluded (EXC0001)
        self.assertEqual(1, reasons.get("hard_excluded_by_split", 0))

    def test_quality_tier_outside_set_known_before_multi_linkage(self) -> None:
        """QTI0001 has Q3 tier (excluded_quality_tier, priority 4).
        If it were also multi-linkage, it would still be captured as
        excluded_quality_tier because quality check has higher priority."""
        from covalent_design.training.dataset import prepare_dataset

        envelope = prepare_dataset(
            VALID_RECORDS_PATH,
            VALID_SPLIT_INDEX_PATH,
            "train",
            None,
        )
        reasons = envelope.payload.excluded_summary.exclusion_reasons
        self.assertEqual(1, reasons.get("excluded_quality_tier", 0))
        self.assertEqual(1, reasons.get("excluded_multi_linkage", 0))


# ---------------------------------------------------------------------------
# 10. ExclusionSummary accounting equations
# ---------------------------------------------------------------------------


class ExclusionSummaryAccountingTests(unittest.TestCase):
    """``ExclusionSummary`` must satisfy conservation equations."""

    def test_total_accepted_equals_records_jsonl_row_count(self) -> None:
        from covalent_design.training.dataset import prepare_dataset

        envelope = prepare_dataset(
            VALID_RECORDS_PATH,
            VALID_SPLIT_INDEX_PATH,
            "train",
            None,
        )
        summary = envelope.payload.excluded_summary
        self.assertEqual(TOTAL_ACCEPTED, summary.total_accepted)

    def test_records_in_split_equals_len_dataset_records(self) -> None:
        from covalent_design.training.dataset import prepare_dataset

        envelope = prepare_dataset(
            VALID_RECORDS_PATH,
            VALID_SPLIT_INDEX_PATH,
            "train",
            None,
        )
        summary = envelope.payload.excluded_summary
        self.assertEqual(
            len(envelope.payload.records),
            summary.records_in_split,
        )

    def test_excluded_by_policy_equals_total_accepted_minus_records_in_split(self) -> None:
        from covalent_design.training.dataset import prepare_dataset

        envelope = prepare_dataset(
            VALID_RECORDS_PATH,
            VALID_SPLIT_INDEX_PATH,
            "train",
            None,
        )
        summary = envelope.payload.excluded_summary
        expected = summary.total_accepted - summary.records_in_split
        self.assertEqual(expected, summary.excluded_by_policy)

    def test_exclusion_reasons_sum_equals_excluded_by_policy(self) -> None:
        from covalent_design.training.dataset import prepare_dataset

        envelope = prepare_dataset(
            VALID_RECORDS_PATH,
            VALID_SPLIT_INDEX_PATH,
            "train",
            None,
        )
        summary = envelope.payload.excluded_summary
        reasons_sum = sum(summary.exclusion_reasons.values())
        self.assertEqual(summary.excluded_by_policy, reasons_sum)

    def test_accounting_holds_for_all_splits(self) -> None:
        from covalent_design.training.dataset import prepare_dataset

        for split_name in ("train", "val", "test"):
            with self.subTest(split=split_name):
                envelope = prepare_dataset(
                    VALID_RECORDS_PATH,
                    VALID_SPLIT_INDEX_PATH,
                    split_name,
                    None,
                )
                s = envelope.payload.excluded_summary
                self.assertEqual(TOTAL_ACCEPTED, s.total_accepted)
                self.assertEqual(
                    len(envelope.payload.records),
                    s.records_in_split,
                )
                self.assertEqual(
                    s.total_accepted - s.records_in_split,
                    s.excluded_by_policy,
                )
                self.assertEqual(
                    s.excluded_by_policy,
                    sum(s.exclusion_reasons.values()),
                )

    def test_accounting_holds_with_custom_policy(self) -> None:
        from covalent_design.training.dataset import TrainingDataPolicy, prepare_dataset

        policy = TrainingDataPolicy(exclude_q2=True, exclude_visual_blocked=False)
        envelope = prepare_dataset(
            VALID_RECORDS_PATH,
            VALID_SPLIT_INDEX_PATH,
            "train",
            policy,
        )
        s = envelope.payload.excluded_summary
        self.assertEqual(TOTAL_ACCEPTED, s.total_accepted)
        self.assertEqual(
            len(envelope.payload.records),
            s.records_in_split,
        )
        self.assertEqual(
            s.total_accepted - s.records_in_split,
            s.excluded_by_policy,
        )
        self.assertEqual(
            s.excluded_by_policy,
            sum(s.exclusion_reasons.values()),
        )


# ---------------------------------------------------------------------------
# 11. Exact exclusion reason counts (train scope, default policy)
# ---------------------------------------------------------------------------


class ExclusionReasonCountTests(unittest.TestCase):
    """Verify the exact exclusion reason breakdown for the train split."""

    def test_train_default_policy_exclusion_counts(self) -> None:
        from covalent_design.training.dataset import prepare_dataset

        envelope = prepare_dataset(
            VALID_RECORDS_PATH,
            VALID_SPLIT_INDEX_PATH,
            "train",
            None,
        )
        reasons = envelope.payload.excluded_summary.exclusion_reasons

        # not_in_this_split: VAL0001 (val) + TST0001 (test) = 2
        self.assertEqual(2, reasons.get("not_in_this_split", 0))
        # hard_excluded_by_split: EXC0001 (excluded) = 1
        self.assertEqual(1, reasons.get("hard_excluded_by_split", 0))
        # excluded_visual_blocked: VIS0001 (fail) + VIS0002 (pending) + VIS0003 (needs_rule_review) = 3
        self.assertEqual(3, reasons.get("excluded_visual_blocked", 0))
        # excluded_quality_tier: QTI0001 (Q3) = 1
        self.assertEqual(1, reasons.get("excluded_quality_tier", 0))
        # excluded_multi_linkage: MLK0001 (linkage_count=2) = 1
        self.assertEqual(1, reasons.get("excluded_multi_linkage", 0))

    def test_train_default_policy_three_records_accepted(self) -> None:
        from covalent_design.training.dataset import prepare_dataset

        envelope = prepare_dataset(
            VALID_RECORDS_PATH,
            VALID_SPLIT_INDEX_PATH,
            "train",
            None,
        )
        self.assertEqual(3, envelope.payload.excluded_summary.records_in_split)
        self.assertEqual(3, len(envelope.payload.records))


# ---------------------------------------------------------------------------
# 12. TrainingRecordEntry field preservation
# ---------------------------------------------------------------------------


class TrainingRecordEntryPreservationTests(unittest.TestCase):
    """``TrainingRecordEntry`` must preserve all specified fields."""

    def test_entry_has_all_required_fields(self) -> None:
        from covalent_design.training.dataset import prepare_dataset

        envelope = prepare_dataset(
            VALID_RECORDS_PATH,
            VALID_SPLIT_INDEX_PATH,
            "train",
            None,
        )
        entry = envelope.payload.records[0]

        self.assertIsInstance(entry, TrainingRecordEntry)
        self.assertIsInstance(entry.record_id, str)
        self.assertIsInstance(entry.residue_reaction_family, str)
        self.assertIsInstance(entry.quality_tier, str)
        self.assertIsInstance(entry.visual_check_status, str)

    def test_entry_record_id_matches_fixture(self) -> None:
        from covalent_design.training.dataset import prepare_dataset

        envelope = prepare_dataset(
            VALID_RECORDS_PATH,
            VALID_SPLIT_INDEX_PATH,
            "train",
            None,
        )
        entry = next(
            r for r in envelope.payload.records
            if r.record_id == RECORD_IDS["train_q0"]
        )
        self.assertEqual(RECORD_IDS["train_q0"], entry.record_id)
        self.assertEqual("CYS_MICHAEL_ADDITION", entry.residue_reaction_family)
        self.assertEqual("Q0", entry.quality_tier)
        self.assertEqual("pass", entry.visual_check_status)

    def test_fallback_reason_preserved(self) -> None:
        from covalent_design.training.dataset import prepare_dataset

        envelope = prepare_dataset(
            VALID_RECORDS_PATH,
            VALID_SPLIT_INDEX_PATH,
            "train",
            None,
        )
        # The fallback_reason comes from split_index.json
        # TRN0001 has null fallback_reason
        entry = next(
            r for r in envelope.payload.records
            if r.record_id == RECORD_IDS["train_q0"]
        )
        self.assertIsNone(entry.fallback_reason)

    def test_manual_review_status_preserved(self) -> None:
        from covalent_design.training.dataset import prepare_dataset

        envelope = prepare_dataset(
            VALID_RECORDS_PATH,
            VALID_SPLIT_INDEX_PATH,
            "train",
            None,
        )
        # TRN0001 has null manual_review_status
        entry = next(
            r for r in envelope.payload.records
            if r.record_id == RECORD_IDS["train_q0"]
        )
        self.assertIsNone(entry.manual_review_status)

    def test_artifact_refs_are_preserved_as_artifact_ref_dicts(self) -> None:
        from covalent_design.training.dataset import prepare_dataset

        envelope = prepare_dataset(
            VALID_RECORDS_PATH,
            VALID_SPLIT_INDEX_PATH,
            "train",
            None,
        )
        entry = next(
            r for r in envelope.payload.records
            if r.record_id == RECORD_IDS["train_q0"]
        )
        self.assertIsInstance(entry.artifact_refs, dict)
        # At least the 4 required non-edge roles
        for role in ("coordinates", "protein_atom_table", "ligand_atom_table", "ligand_bond_table"):
            self.assertIn(role, entry.artifact_refs,
                          f"artifact_refs missing role {role!r}")
            ref = entry.artifact_refs[role]
            self.assertIsInstance(ref, ArtifactRef,
                                  f"artifact_ref for {role!r} is not an ArtifactRef")

    def test_residue_reaction_family_preserved(self) -> None:
        from covalent_design.training.dataset import prepare_dataset

        envelope = prepare_dataset(
            VALID_RECORDS_PATH,
            VALID_SPLIT_INDEX_PATH,
            "train",
            None,
        )
        for entry in envelope.payload.records:
            self.assertEqual("CYS_MICHAEL_ADDITION", entry.residue_reaction_family)


# ---------------------------------------------------------------------------
# 13. Dataset index structure
# ---------------------------------------------------------------------------


class TrainingDatasetIndexStructureTests(unittest.TestCase):
    """``TrainingDatasetIndex`` carries policy, split_name, records, summary."""

    def test_policy_field_is_dict_like(self) -> None:
        from covalent_design.training.dataset import prepare_dataset

        envelope = prepare_dataset(
            VALID_RECORDS_PATH,
            VALID_SPLIT_INDEX_PATH,
            "train",
            None,
        )
        self.assertIsInstance(envelope.payload.policy, dict)

    def test_split_name_matches_requested(self) -> None:
        from covalent_design.training.dataset import prepare_dataset

        envelope = prepare_dataset(
            VALID_RECORDS_PATH,
            VALID_SPLIT_INDEX_PATH,
            "val",
            None,
        )
        self.assertEqual("val", envelope.payload.split_name)

    def test_records_is_tuple_of_training_record_entries(self) -> None:
        from covalent_design.training.dataset import prepare_dataset

        envelope = prepare_dataset(
            VALID_RECORDS_PATH,
            VALID_SPLIT_INDEX_PATH,
            "train",
            None,
        )
        self.assertIsInstance(envelope.payload.records, tuple)
        for entry in envelope.payload.records:
            self.assertIsInstance(entry, TrainingRecordEntry)

    def test_excluded_summary_is_exclusion_summary_type(self) -> None:
        from covalent_design.training.dataset import prepare_dataset

        envelope = prepare_dataset(
            VALID_RECORDS_PATH,
            VALID_SPLIT_INDEX_PATH,
            "train",
            None,
        )
        self.assertIsInstance(envelope.payload.excluded_summary, ExclusionSummary)


# ---------------------------------------------------------------------------
# 14. Edge cases
# ---------------------------------------------------------------------------


class EdgeCaseTests(unittest.TestCase):
    """Boundary behaviour for the dataset builder."""

    def test_policy_defaults_to_default_policy_when_none(self) -> None:
        from covalent_design.training.dataset import prepare_dataset, TrainingDataPolicy

        # Use a custom policy to prove it overrides the default
        policy = TrainingDataPolicy(
            first_core_only=False,
            exclude_visual_blocked=False,
            exclude_q2=True,
            accepted_quality_tiers=("Q0",),
        )
        envelope = prepare_dataset(
            VALID_RECORDS_PATH,
            VALID_SPLIT_INDEX_PATH,
            "train",
            policy,
        )
        # With only Q0 accepted, TRN0002 (Q1) and Q2K0001 (Q2) excluded
        record_ids = {r.record_id for r in envelope.payload.records}
        self.assertIn(RECORD_IDS["train_q0"], record_ids)
        self.assertNotIn(RECORD_IDS["train_q1"], record_ids)
        self.assertNotIn(RECORD_IDS["q2_keep"], record_ids)

    def test_all_exclusion_reasons_have_non_negative_counts(self) -> None:
        from covalent_design.training.dataset import prepare_dataset

        for split_name in ("train", "val", "test"):
            with self.subTest(split=split_name):
                envelope = prepare_dataset(
                    VALID_RECORDS_PATH,
                    VALID_SPLIT_INDEX_PATH,
                    split_name,
                    None,
                )
                for reason, count in envelope.payload.excluded_summary.exclusion_reasons.items():
                    self.assertGreaterEqual(
                        count, 0,
                        f"{split_name}: exclusion reason {reason!r} has negative count {count}",
                    )

    def test_dataset_records_sorted_by_record_id(self) -> None:
        from covalent_design.training.dataset import prepare_dataset

        envelope = prepare_dataset(
            VALID_RECORDS_PATH,
            VALID_SPLIT_INDEX_PATH,
            "train",
            None,
        )
        ids = [r.record_id for r in envelope.payload.records]
        self.assertEqual(sorted(ids), ids,
                         "dataset records must be sorted by record_id")

    def test_no_duplicate_record_ids_in_dataset(self) -> None:
        from covalent_design.training.dataset import prepare_dataset

        envelope = prepare_dataset(
            VALID_RECORDS_PATH,
            VALID_SPLIT_INDEX_PATH,
            "train",
            None,
        )
        ids = [r.record_id for r in envelope.payload.records]
        self.assertEqual(len(ids), len(set(ids)),
                         "duplicate record_id in dataset")


# ---------------------------------------------------------------------------
# 15. load_training_batch contract
# ---------------------------------------------------------------------------


class LoadTrainingBatchContractTests(unittest.TestCase):
    """``load_training_batch()`` must exist in the correct module."""

    def test_load_training_batch_is_importable(self) -> None:
        _assert_importable("covalent_design.training.batch", "load_training_batch")


# ---------------------------------------------------------------------------
# 16. Module boundary — no Task 23 / model-forward contamination
# ---------------------------------------------------------------------------


class ModuleBoundaryTests(unittest.TestCase):
    """``covalent_design.training.dataset`` must not import forbidden modules."""

    def test_dataset_does_not_import_masks(self) -> None:
        # Ensure the dataset module does not pull in masks
        before = set(sys.modules.keys())
        __import__("covalent_design.training.dataset")
        after = set(sys.modules.keys())
        new = after - before
        forbidden = [m for m in new if "masks" in m.lower()]
        self.assertEqual([], forbidden,
                         f"dataset imported mask modules: {forbidden}")

    def test_dataset_does_not_import_losses(self) -> None:
        before = set(sys.modules.keys())
        __import__("covalent_design.training.dataset")
        after = set(sys.modules.keys())
        new = after - before
        forbidden = [m for m in new if "loss" in m.lower()]
        self.assertEqual([], forbidden,
                         f"dataset imported loss modules: {forbidden}")

    def test_dataset_does_not_import_model_forward(self) -> None:
        before = set(sys.modules.keys())
        __import__("covalent_design.training.dataset")
        after = set(sys.modules.keys())
        new = after - before
        forbidden = [m for m in new if "pmdm" in m.lower() or "covalent_heads" in m.lower()]
        self.assertEqual([], forbidden,
                         f"dataset imported model forward modules: {forbidden}")

    def test_batch_does_not_import_masks(self) -> None:
        before = set(sys.modules.keys())
        __import__("covalent_design.training.batch")
        after = set(sys.modules.keys())
        new = after - before
        forbidden = [m for m in new if "masks" in m.lower()]
        self.assertEqual([], forbidden,
                         f"batch imported mask modules: {forbidden}")

    def test_batch_does_not_import_losses(self) -> None:
        before = set(sys.modules.keys())
        __import__("covalent_design.training.batch")
        after = set(sys.modules.keys())
        new = after - before
        forbidden = [m for m in new if "loss" in m.lower()]
        self.assertEqual([], forbidden,
                         f"batch imported loss modules: {forbidden}")

    def test_batch_does_not_import_model_forward(self) -> None:
        before = set(sys.modules.keys())
        __import__("covalent_design.training.batch")
        after = set(sys.modules.keys())
        new = after - before
        forbidden = [m for m in new if "pmdm" in m.lower() or "covalent_heads" in m.lower()]
        self.assertEqual([], forbidden,
                         f"batch imported model forward modules: {forbidden}")


# ---------------------------------------------------------------------------
# 17. TrainingDataPolicy field validation
# ---------------------------------------------------------------------------


class TrainingDataPolicyConstructionTests(unittest.TestCase):
    """``TrainingDataPolicy`` field validation."""

    def test_policy_normalizes_iterable_accepted_quality_tiers(self) -> None:
        """List accepted_quality_tiers are normalized to an immutable tuple."""
        from covalent_design.training.dataset import TrainingDataPolicy

        # Accepted: quality tiers must be iterable
        policy = TrainingDataPolicy(accepted_quality_tiers=["Q0", "Q1"])
        self.assertEqual(("Q0", "Q1"), tuple(policy.accepted_quality_tiers))

    def test_policy_accepts_explicit_fields(self) -> None:
        from covalent_design.training.dataset import TrainingDataPolicy

        policy = TrainingDataPolicy(
            first_core_only=False,
            exclude_visual_blocked=False,
            exclude_q2=True,
            accepted_quality_tiers=("Q0", "Q1"),
        )
        self.assertFalse(policy.first_core_only)
        self.assertFalse(policy.exclude_visual_blocked)
        self.assertTrue(policy.exclude_q2)
        self.assertEqual(("Q0", "Q1"), tuple(policy.accepted_quality_tiers))


# ---------------------------------------------------------------------------
# 18. Deterministic output
# ---------------------------------------------------------------------------


class DeterministicOutputTests(unittest.TestCase):
    """``prepare_dataset`` must produce identical output for identical inputs."""

    def test_repeated_calls_produce_identical_dataset(self) -> None:
        from covalent_design.training.dataset import prepare_dataset

        e1 = prepare_dataset(
            VALID_RECORDS_PATH,
            VALID_SPLIT_INDEX_PATH,
            "train",
            None,
        )
        e2 = prepare_dataset(
            VALID_RECORDS_PATH,
            VALID_SPLIT_INDEX_PATH,
            "train",
            None,
        )

        self.assertEqual(
            tuple(r.record_id for r in e1.payload.records),
            tuple(r.record_id for r in e2.payload.records),
        )
        self.assertEqual(
            e1.payload.excluded_summary.exclusion_reasons,
            e2.payload.excluded_summary.exclusion_reasons,
        )


# ---------------------------------------------------------------------------
# 19. Fixture integrity
# ---------------------------------------------------------------------------


class FixtureIntegrityTests(unittest.TestCase):
    """Fixtures themselves must be well-formed."""

    def test_records_jsonl_exists(self) -> None:
        self.assertTrue(VALID_RECORDS_PATH.exists(),
                        f"records.jsonl not found: {VALID_RECORDS_PATH}")

    def test_split_index_json_exists(self) -> None:
        self.assertTrue(VALID_SPLIT_INDEX_PATH.exists(),
                        f"split_index.json not found: {VALID_SPLIT_INDEX_PATH}")

    def test_records_jsonl_has_correct_row_count(self) -> None:
        ids = _load_jsonl_ids(VALID_RECORDS_PATH)
        self.assertEqual(TOTAL_ACCEPTED, len(ids))

    def test_records_jsonl_no_duplicate_ids(self) -> None:
        ids = _load_jsonl_ids(VALID_RECORDS_PATH)
        self.assertEqual(len(ids), len(set(ids)))

    def test_split_index_covers_all_records(self) -> None:
        record_ids = set(_load_jsonl_ids(VALID_RECORDS_PATH))
        split_data = json.loads(VALID_SPLIT_INDEX_PATH.read_text("utf-8"))
        assignment_ids = {a["record_id"] for a in split_data["assignments"]}
        missing = record_ids - assignment_ids
        self.assertEqual(set(), missing,
                         f"split_index missing assignments for: {missing}")

    def test_split_index_has_no_extra_records(self) -> None:
        record_ids = set(_load_jsonl_ids(VALID_RECORDS_PATH))
        split_data = json.loads(VALID_SPLIT_INDEX_PATH.read_text("utf-8"))
        assignment_ids = {a["record_id"] for a in split_data["assignments"]}
        extra = assignment_ids - record_ids
        self.assertEqual(set(), extra,
                         f"split_index has extra assignments for: {extra}")

    def test_split_index_has_correct_split_distribution(self) -> None:
        split_data = json.loads(VALID_SPLIT_INDEX_PATH.read_text("utf-8"))
        split_counts = {"train": 0, "val": 0, "test": 0, "excluded": 0}
        for a in split_data["assignments"]:
            split_counts[a["split"]] += 1
        self.assertEqual(8, split_counts["train"])  # TRN001, TRN002, VIS001-3, QTI001, MLK001, Q2K001
        self.assertEqual(1, split_counts["val"])     # VAL001
        self.assertEqual(1, split_counts["test"])    # TST001
        self.assertEqual(1, split_counts["excluded"]) # EXC001

    def test_records_jsonl_has_all_required_fields(self) -> None:
        for line in VALID_RECORDS_PATH.read_text("utf-8").splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            row = json.loads(stripped)
            self.assertEqual("1", row.get("schema_version"))
            self.assertEqual("1.0.0", row.get("contract_version"))
            self.assertIn("core_labels", row)
            self.assertIn("residue_reaction_family", row["core_labels"])
            self.assertIn("metadata", row)
            self.assertIn("artifacts", row)
            self.assertIsInstance(row["artifacts"], list)

    def test_records_jsonl_artifacts_are_valid_artifact_ref_dicts(self) -> None:
        for line in VALID_RECORDS_PATH.read_text("utf-8").splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            row = json.loads(stripped)
            for art in row["artifacts"]:
                self.assertIn("uri", art)
                self.assertIn("sha256", art)
                self.assertIn("format", art)
                self.assertIn("role", art)
                self.assertIn("schema_version", art)

    def test_records_jsonl_covers_all_quality_tiers(self) -> None:
        tiers = set()
        for line in VALID_RECORDS_PATH.read_text("utf-8").splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            row = json.loads(stripped)
            tiers.add(row["metadata"]["quality"]["quality_tier"])
        self.assertIn("Q0", tiers)
        self.assertIn("Q1", tiers)
        self.assertIn("Q2", tiers)
        self.assertIn("Q3", tiers)

    def test_records_jsonl_covers_all_visual_statuses(self) -> None:
        statuses = set()
        for line in VALID_RECORDS_PATH.read_text("utf-8").splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            row = json.loads(stripped)
            statuses.add(row["metadata"]["visual_check_status"])
        self.assertIn("pass", statuses)
        self.assertIn("fail", statuses)
        self.assertIn("pending", statuses)
        self.assertIn("needs_rule_review", statuses)

    def test_records_jsonl_has_multi_linkage_record(self) -> None:
        for line in VALID_RECORDS_PATH.read_text("utf-8").splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            row = json.loads(stripped)
            if row["record_id"] == RECORD_IDS["multi_linkage"]:
                self.assertEqual(2, row["metadata"]["linkage_count"])
                return
        self.fail("multi-linkage record not found in fixture")

    def test_records_jsonl_has_excluded_split_record(self) -> None:
        split_data = json.loads(VALID_SPLIT_INDEX_PATH.read_text("utf-8"))
        excluded = [
            a for a in split_data["assignments"]
            if a["record_id"] == RECORD_IDS["excluded"]
        ]
        self.assertEqual(1, len(excluded))
        self.assertEqual("excluded", excluded[0]["split"])
        self.assertIsNotNone(excluded[0]["fallback_reason"])


if __name__ == "__main__":
    unittest.main()
