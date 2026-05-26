import json
import unittest
from pathlib import Path

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "splits"
EXPECTED_CLI_PATH = "python -m covalent_design.data.cli.build_splits"

VALID_SPLITS = ("train", "val", "test", "excluded")
VALID_FALLBACK_REASONS = (
    "warhead_unmatched",
    "missing_scaffold_input",
    "missing_protein_cluster_input",
    "manual_review_override",
)
VALID_REVIEW_STATUSES = ("pending", "approved", "rejected")

REQUIRED_SPLIT_INDEX_KEYS = {
    "schema_version",
    "contract_version",
    "role",
    "split_policy",
    "assignment_count",
    "assignments",
}
REQUIRED_SPLIT_POLICY_KEYS = {
    "algorithm",
    "algorithm_version",
    "random_seed",
    "split_ratios",
}
REQUIRED_SPLIT_RATIOS = {"train", "val", "test"}
REQUIRED_ASSIGNMENT_KEYS = {
    "record_id",
    "split",
    "scaffold_key",
    "protein_cluster_id",
    "residue_reaction_family",
    "fallback_reason",
    "manual_review_status",
}
REQUIRED_LEAKAGE_REPORT_KEYS = {
    "schema_version",
    "contract_version",
    "role",
    "record_count",
    "train_count",
    "val_count",
    "test_count",
    "excluded_count",
    "fallback_count",
    "fallback_by_reason",
    "manual_review_count",
    "scaffold_overlaps",
    "protein_cluster_overlaps",
    "zero_overlap",
}
REQUIRED_RECORD_KEYS = {"record_id", "core_labels", "lineage", "artifacts"}
REQUIRED_CORE_LABELS_KEYS = {
    "residue_reaction_family",
    "bond_type",
    "warhead_type",
    "pdb_id",
}


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _validate_split_index(split_index: dict, expected_assignments: int) -> None:
    missing = REQUIRED_SPLIT_INDEX_KEYS - set(split_index)
    assert not missing, f"split_index missing keys: {missing}"

    assert split_index["schema_version"] == "1", "schema_version must be '1'"
    assert split_index["contract_version"] == "1.0.0", "contract_version must be '1.0.0'"
    assert split_index["role"] == "split_index", "role must be 'split_index'"

    policy = split_index["split_policy"]
    missing_policy = REQUIRED_SPLIT_POLICY_KEYS - set(policy)
    assert not missing_policy, f"split_policy missing keys: {missing_policy}"
    assert policy["algorithm"] == "leakage_aware_covalent_splits"
    assert isinstance(policy["random_seed"], int)
    missing_ratios = REQUIRED_SPLIT_RATIOS - set(policy["split_ratios"])
    assert not missing_ratios, f"split_ratios missing keys: {missing_ratios}"
    ratio_sum = sum(policy["split_ratios"].values())
    assert 0.99 <= ratio_sum <= 1.01, f"split ratios must sum to ~1.0, got {ratio_sum}"

    assert split_index["assignment_count"] == expected_assignments
    assert len(split_index["assignments"]) == expected_assignments

    assigned_ids: set[str] = set()
    for assignment in split_index["assignments"]:
        missing_assign = REQUIRED_ASSIGNMENT_KEYS - set(assignment)
        assert not missing_assign, f"assignment missing keys: {missing_assign}"
        assert assignment["split"] in VALID_SPLITS, f"invalid split: {assignment['split']}"
        if assignment["fallback_reason"] is not None:
            assert assignment["fallback_reason"] in VALID_FALLBACK_REASONS, (
                f"invalid fallback_reason: {assignment['fallback_reason']}"
            )
        if assignment["manual_review_status"] is not None:
            assert assignment["manual_review_status"] in VALID_REVIEW_STATUSES, (
                f"invalid review_status: {assignment['manual_review_status']}"
            )
        assigned_ids.add(assignment["record_id"])

    assert len(assigned_ids) == expected_assignments, "duplicate record_id in assignments"


def _validate_leakage_report(report: dict, split_index: dict) -> None:
    missing = REQUIRED_LEAKAGE_REPORT_KEYS - set(report)
    assert not missing, f"leakage_report missing keys: {missing}"

    assert report["schema_version"] == "1"
    assert report["contract_version"] == "1.0.0"
    assert report["role"] == "leakage_report"

    splits = {"train": 0, "val": 0, "test": 0, "excluded": 0}
    fallback_count = 0
    fallback_reasons: dict[str, int] = {}
    review_count = 0

    for a in split_index["assignments"]:
        splits[a["split"]] += 1
        if a["fallback_reason"] is not None:
            fallback_count += 1
            fallback_reasons[a["fallback_reason"]] = (
                fallback_reasons.get(a["fallback_reason"], 0) + 1
            )
        if a["manual_review_status"] is not None:
            review_count += 1

    total = sum(splits.values())
    assert report["record_count"] == total
    assert report["train_count"] == splits["train"]
    assert report["val_count"] == splits["val"]
    assert report["test_count"] == splits["test"]
    assert report["excluded_count"] == splits["excluded"]
    assert report["fallback_count"] == fallback_count
    assert report["fallback_by_reason"] == fallback_reasons
    assert report["manual_review_count"] == review_count

    assert isinstance(report["zero_overlap"], dict)
    assert isinstance(report["zero_overlap"]["scaffold"], bool)
    assert isinstance(report["zero_overlap"]["protein_cluster"], bool)

    for overlap in report["scaffold_overlaps"]:
        assert "scaffold_key" in overlap
        assert "overlapping_splits" in overlap
        assert "record_ids" in overlap
        assert len(set(overlap["overlapping_splits"])) >= 2

    for overlap in report["protein_cluster_overlaps"]:
        assert "protein_cluster_id" in overlap
        assert "overlapping_splits" in overlap
        assert "record_ids" in overlap
        assert len(set(overlap["overlapping_splits"])) >= 2


def _validate_records_fixture(records: list[dict], min_count: int) -> list[str]:
    assert len(records) >= min_count
    record_ids: list[str] = []
    for record in records:
        missing = REQUIRED_RECORD_KEYS - set(record)
        assert not missing, f"record missing keys: {missing}"
        missing_cl = REQUIRED_CORE_LABELS_KEYS - set(record["core_labels"])
        assert not missing_cl, f"core_labels missing keys: {missing_cl}"
        assert isinstance(record["lineage"], list) and len(record["lineage"]) > 0
        assert isinstance(record["artifacts"], list) and len(record["artifacts"]) > 0
        record_ids.append(record["record_id"])
    return record_ids


class SplitIndexSchemaContractTests(unittest.TestCase):
    def test_scaffold_leakage_split_index_shape(self) -> None:
        split_index = _load_json(FIXTURE_ROOT / "scaffold_leakage" / "split_index.json")
        _validate_split_index(split_index, expected_assignments=4)
        scaffolds = {a["scaffold_key"] for a in split_index["assignments"]}
        self.assertEqual(3, len(scaffolds), "expected 3 distinct scaffolds for 4 records")

    def test_scaffold_no_leakage_split_index_shape(self) -> None:
        split_index = _load_json(FIXTURE_ROOT / "scaffold_no_leakage" / "split_index.json")
        _validate_split_index(split_index, expected_assignments=4)
        scaffolds = {a["scaffold_key"] for a in split_index["assignments"]}
        self.assertEqual(4, len(scaffolds), "all 4 scaffolds should be distinct")

    def test_protein_cluster_leakage_split_index_shape(self) -> None:
        split_index = _load_json(FIXTURE_ROOT / "protein_cluster_leakage" / "split_index.json")
        _validate_split_index(split_index, expected_assignments=4)
        clusters = {a["protein_cluster_id"] for a in split_index["assignments"]}
        self.assertEqual(3, len(clusters), "expected 3 distinct protein clusters for 4 records")

    def test_warhead_unmatched_split_index_shape(self) -> None:
        split_index = _load_json(FIXTURE_ROOT / "warhead_unmatched" / "split_index.json")
        _validate_split_index(split_index, expected_assignments=4)
        fallback_assignments = [
            a for a in split_index["assignments"] if a["fallback_reason"] == "warhead_unmatched"
        ]
        self.assertEqual(1, len(fallback_assignments))
        self.assertEqual("excluded", fallback_assignments[0]["split"])

    def test_manual_review_override_split_index_shape(self) -> None:
        split_index = _load_json(FIXTURE_ROOT / "manual_review_override" / "split_index.json")
        _validate_split_index(split_index, expected_assignments=4)
        approved = [
            a for a in split_index["assignments"]
            if a["manual_review_status"] == "approved"
        ]
        self.assertEqual(1, len(approved))
        self.assertEqual("train", approved[0]["split"])
        self.assertEqual("warhead_unmatched", approved[0]["fallback_reason"])

    def test_missing_scaffold_inputs_split_index_shape(self) -> None:
        split_index = _load_json(FIXTURE_ROOT / "missing_scaffold_inputs" / "split_index.json")
        _validate_split_index(split_index, expected_assignments=4)
        missing = [
            a for a in split_index["assignments"]
            if a["fallback_reason"] == "missing_scaffold_input"
        ]
        self.assertEqual(2, len(missing))
        for m in missing:
            self.assertEqual("excluded", m["split"])

    def test_excluded_records_not_counted_in_train_val_test(self) -> None:
        for scenario in (
            "scaffold_leakage",
            "scaffold_no_leakage",
            "protein_cluster_leakage",
            "warhead_unmatched",
            "manual_review_override",
            "missing_scaffold_inputs",
        ):
            with self.subTest(scenario=scenario):
                split_index = _load_json(FIXTURE_ROOT / scenario / "split_index.json")
                train_val_test = sum(
                    1 for a in split_index["assignments"] if a["split"] in ("train", "val", "test")
                )
                excluded = sum(
                    1 for a in split_index["assignments"] if a["split"] == "excluded"
                )
                self.assertEqual(
                    len(split_index["assignments"]),
                    train_val_test + excluded,
                    f"{scenario}: assignments must partition into train+val+test+excluded",
                )


class LeakageReportSchemaContractTests(unittest.TestCase):
    def test_scaffold_leakage_report_shape(self) -> None:
        split_index = _load_json(FIXTURE_ROOT / "scaffold_leakage" / "split_index.json")
        report = _load_json(FIXTURE_ROOT / "scaffold_leakage" / "leakage_report.json")
        _validate_leakage_report(report, split_index)
        self.assertGreater(len(report["scaffold_overlaps"]), 0, "must detect scaffold overlap")
        self.assertFalse(report["zero_overlap"]["scaffold"])

    def test_scaffold_no_leakage_report_shape(self) -> None:
        split_index = _load_json(FIXTURE_ROOT / "scaffold_no_leakage" / "split_index.json")
        report = _load_json(FIXTURE_ROOT / "scaffold_no_leakage" / "leakage_report.json")
        _validate_leakage_report(report, split_index)
        self.assertEqual([], report["scaffold_overlaps"])
        self.assertTrue(report["zero_overlap"]["scaffold"])

    def test_protein_cluster_leakage_report_shape(self) -> None:
        split_index = _load_json(FIXTURE_ROOT / "protein_cluster_leakage" / "split_index.json")
        report = _load_json(FIXTURE_ROOT / "protein_cluster_leakage" / "leakage_report.json")
        _validate_leakage_report(report, split_index)
        self.assertGreater(len(report["protein_cluster_overlaps"]), 0)
        self.assertFalse(report["zero_overlap"]["protein_cluster"])

    def test_warhead_unmatched_report_shape(self) -> None:
        split_index = _load_json(FIXTURE_ROOT / "warhead_unmatched" / "split_index.json")
        report = _load_json(FIXTURE_ROOT / "warhead_unmatched" / "leakage_report.json")
        _validate_leakage_report(report, split_index)
        self.assertEqual(1, report["fallback_by_reason"].get("warhead_unmatched", 0))

    def test_manual_review_override_report_shape(self) -> None:
        split_index = _load_json(FIXTURE_ROOT / "manual_review_override" / "split_index.json")
        report = _load_json(FIXTURE_ROOT / "manual_review_override" / "leakage_report.json")
        _validate_leakage_report(report, split_index)
        self.assertEqual(2, report["manual_review_count"])
        self.assertEqual(2, report["fallback_by_reason"].get("warhead_unmatched", 0))

    def test_missing_scaffold_inputs_report_shape(self) -> None:
        split_index = _load_json(FIXTURE_ROOT / "missing_scaffold_inputs" / "split_index.json")
        report = _load_json(FIXTURE_ROOT / "missing_scaffold_inputs" / "leakage_report.json")
        _validate_leakage_report(report, split_index)
        self.assertEqual(2, report["fallback_by_reason"].get("missing_scaffold_input", 0))

    def test_missing_protein_cluster_inputs_report_shape(self) -> None:
        split_index = _load_json(FIXTURE_ROOT / "missing_protein_cluster_inputs" / "split_index.json")
        report = _load_json(FIXTURE_ROOT / "missing_protein_cluster_inputs" / "leakage_report.json")
        _validate_leakage_report(report, split_index)
        self.assertEqual(2, report["fallback_by_reason"].get("missing_protein_cluster_input", 0))

    def test_all_reports_conserve_record_count(self) -> None:
        for scenario in (
            "scaffold_leakage",
            "scaffold_no_leakage",
            "protein_cluster_leakage",
            "warhead_unmatched",
            "manual_review_override",
            "missing_scaffold_inputs",
            "missing_protein_cluster_inputs",
        ):
            with self.subTest(scenario=scenario):
                split_index = _load_json(FIXTURE_ROOT / scenario / "split_index.json")
                report = _load_json(FIXTURE_ROOT / scenario / "leakage_report.json")
                train = report["train_count"]
                val = report["val_count"]
                test = report["test_count"]
                excluded = report["excluded_count"]
                self.assertEqual(report["record_count"], train + val + test + excluded)


class RecordInputFixtureTests(unittest.TestCase):
    def test_scaffold_leakage_records_have_minimum_split_inputs(self) -> None:
        records = _load_jsonl(FIXTURE_ROOT / "records" / "scaffold_leakage_records.jsonl")
        record_ids = _validate_records_fixture(records, min_count=4)
        self.assertEqual(4, len(record_ids))
        self.assertEqual(len(set(record_ids)), 4, "record_ids must be unique")

    def test_scaffold_no_leakage_records_have_minimum_split_inputs(self) -> None:
        records = _load_jsonl(FIXTURE_ROOT / "records" / "scaffold_no_leakage_records.jsonl")
        record_ids = _validate_records_fixture(records, min_count=4)
        self.assertEqual(4, len(record_ids))
        self.assertEqual(len(set(record_ids)), 4)

    def test_protein_cluster_leakage_records_have_minimum_split_inputs(self) -> None:
        records = _load_jsonl(FIXTURE_ROOT / "records" / "protein_cluster_leakage_records.jsonl")
        record_ids = _validate_records_fixture(records, min_count=4)
        self.assertEqual(4, len(record_ids))
        cluster_ids = [
            r.get("metadata", {}).get("protein_cluster_id") for r in records
        ]
        self.assertIsNotNone(cluster_ids[0])
        self.assertEqual(cluster_ids[0], cluster_ids[1], "first two records share cluster")

    def test_warhead_unmatched_records_have_minimum_split_inputs(self) -> None:
        records = _load_jsonl(FIXTURE_ROOT / "records" / "warhead_unmatched_records.jsonl")
        record_ids = _validate_records_fixture(records, min_count=4)
        self.assertEqual(4, len(record_ids))

    def test_manual_review_override_records_have_minimum_split_inputs(self) -> None:
        records = _load_jsonl(FIXTURE_ROOT / "records" / "manual_review_override_records.jsonl")
        record_ids = _validate_records_fixture(records, min_count=4)
        self.assertEqual(4, len(record_ids))

    def test_missing_scaffold_inputs_records_have_minimum_split_inputs(self) -> None:
        records = _load_jsonl(FIXTURE_ROOT / "records" / "missing_scaffold_inputs_records.jsonl")
        record_ids = _validate_records_fixture(records, min_count=4)
        self.assertEqual(4, len(record_ids))
        missing_ligand_bond = any(
            not any(
                str(ref.get("role", "")) == "ligand_bond_table"
                for ref in r.get("artifacts", [])
            )
            for r in records
        )
        self.assertTrue(missing_ligand_bond, "at least one record must lack ligand_bond_table")

    def test_missing_protein_cluster_inputs_records_have_minimum_split_inputs(self) -> None:
        records = _load_jsonl(FIXTURE_ROOT / "records" / "missing_protein_cluster_inputs_records.jsonl")
        record_ids = _validate_records_fixture(records, min_count=4)
        self.assertEqual(4, len(record_ids))
        missing_cluster = any(
            not r.get("metadata", {}).get("protein_cluster_id")
            for r in records
        )
        self.assertTrue(missing_cluster, "at least one record must lack protein_cluster_id")

    def test_record_ids_match_between_records_and_split_index(self) -> None:
        scenarios = [
            ("scaffold_leakage", "scaffold_leakage_records.jsonl"),
            ("scaffold_no_leakage", "scaffold_no_leakage_records.jsonl"),
            ("protein_cluster_leakage", "protein_cluster_leakage_records.jsonl"),
            ("warhead_unmatched", "warhead_unmatched_records.jsonl"),
            ("manual_review_override", "manual_review_override_records.jsonl"),
            ("missing_scaffold_inputs", "missing_scaffold_inputs_records.jsonl"),
            ("missing_protein_cluster_inputs", "missing_protein_cluster_inputs_records.jsonl"),
        ]
        for scenario, records_file in scenarios:
            with self.subTest(scenario=scenario):
                split_index = _load_json(FIXTURE_ROOT / scenario / "split_index.json")
                records = _load_jsonl(FIXTURE_ROOT / "records" / records_file)
                index_ids = {a["record_id"] for a in split_index["assignments"]}
                record_ids = {r["record_id"] for r in records}
                self.assertEqual(index_ids, record_ids)


class CLIPathContractTests(unittest.TestCase):
    def test_frozen_cli_path_is_python_m_covalent_design_data_cli_build_splits(self) -> None:
        self.assertEqual(
            "python -m covalent_design.data.cli.build_splits",
            EXPECTED_CLI_PATH,
        )

    def test_cli_path_consistent_with_existing_task_13_pattern(self) -> None:
        self.assertTrue(EXPECTED_CLI_PATH.startswith("python -m covalent_design.data.cli."))

    def test_cli_module_path_resolves_to_package_layout(self) -> None:
        rel = EXPECTED_CLI_PATH.replace("python -m ", "").replace(".", "/")
        expected_file = (
            Path(__file__).resolve().parents[2]
            / "src"
            / (rel + ".py")
        )
        self.assertTrue(
            expected_file.parent.exists(),
            f"CLI package directory must exist: {expected_file.parent}",
        )


class ScaffoldKeyArtifactContractTests(unittest.TestCase):
    def test_scaffold_key_artifact_schema_is_defined(self) -> None:
        scaffold_key_schema_path = FIXTURE_ROOT / "scaffold_key_artifact_schema.json"
        schema = _load_json(scaffold_key_schema_path)

        self.assertEqual("1", schema["schema_version"])
        self.assertEqual("1.0.0", schema["contract_version"])
        self.assertEqual("scaffold_key", schema["role"])
        self.assertIn("algorithm", schema)
        self.assertIn("algorithm_version", schema)
        self.assertIn("warhead_match", schema)
        self.assertIn("matched", schema["warhead_match"])
        self.assertIn("scaffold_key", schema)
        self.assertIn("fallback_reason", schema)
        allowed = tuple(schema["fallback_reason"]["allowed"])
        for reason in (None, *VALID_FALLBACK_REASONS):
            self.assertIn(reason, allowed)

    def test_scaffold_key_example_is_valid(self) -> None:
        example = _load_json(FIXTURE_ROOT / "scaffold_key_artifact_example.json")
        self.assertEqual("scaffold_key", example["role"])
        self.assertTrue(example["warhead_match"]["matched"])
        self.assertGreater(len(example["warhead_match"]["removed_atom_indices"]), 0)
        self.assertGreater(len(example["scaffold_key"]), 0)
        self.assertIsNone(example["fallback_reason"])

    def test_scaffold_key_fallback_example_is_valid(self) -> None:
        example = _load_json(FIXTURE_ROOT / "scaffold_key_artifact_fallback_example.json")
        self.assertEqual("scaffold_key", example["role"])
        self.assertFalse(example["warhead_match"]["matched"])
        self.assertEqual("warhead_unmatched", example["fallback_reason"])
        self.assertIsNone(example["scaffold_key"])


if __name__ == "__main__":
    unittest.main()
