"""Task 25 training run manifest and checkpoint metadata contract tests.

These tests define the public API and boundary contracts for
``covalent_design.training.reports`` and
``covalent_design.training.checkpoints``.  The production modules do
not exist yet -every test that imports from those modules is
expected to **RED**.

Coverage:

*Reports (covalent_design.training.reports):*
- ``canonical_json(value) -> str``
- ``sha256_bytes(value: bytes) -> str``
- ``sha256_file(path) -> str``
- ``hash_resolved_config(resolved_config) -> str``
- ``hash_rule_table(path) -> str``
- ``build_training_input_hashes(...) -> dict[str, str]``
- ``build_training_run_manifest(...) -> TrainingRunManifest``
- ``training_run_manifest_to_dict(manifest) -> dict``

*Checkpoints (covalent_design.training.checkpoints):*
- ``CheckpointMetadata`` frozen dataclass
- ``checkpoint_metadata_to_dict(metadata) -> dict``
- ``write_checkpoint_metadata(path, metadata) -> Path``
- ``read_checkpoint_metadata(path, *, expected_contract_version=...) -> tuple[...]``
- ``validate_checkpoint_metadata(metadata, *, expected_contract_version=...) -> tuple[str, ...]``

*Cross-cutting frozen decisions:*
- Every hash is ``sha256:<64 lowercase hex>``.
- records, split, quality_report, visual_check_index, and optional
  release_gate use exact file bytes.
- rule_table uses parsed YAML -> canonical JSON sorted keys -> SHA-256.
- quality_report and visual_check_index are required audit provenance
  hashes.
- release_gate is optional.
- TrainingRunManifest.training_config_resolved_hash stores canonical
  resolved config hash separately from input_hashes.
- checkpoint input_hashes require records_jsonl, split_index, rule_table,
  training_config_resolved, quality_report, and visual_check_index.
- release_gate remains optional in checkpoint metadata.
- release-gate artifacts are hash-bound only; metadata code does not
  rerun governance.
- no_edge must be vocabulary index 0.
- exact version loads without warning; major mismatch rejects; minor
  mismatch loads with warning.
- URI targets need not exist for metadata validation.
- deterministic YAML output, pure Python, no heavy imports, no real .pt
  files.
"""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# contracts -always importable
# ---------------------------------------------------------------------------
from covalent_design.contracts.types import (
    CONTRACT_VERSION,
    SCHEMA_VERSION,
    TRAINING_RELEASE_GATE_INPUT_HASH_KEYS,
    TRAINING_REQUIRED_INPUT_HASH_KEYS,
    TrainingRunManifest,
)

# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------
_FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "training"
_RUN_MANIFEST_FIXTURES = _FIXTURE_ROOT / "run_manifest"
_CHECKPOINT_FIXTURES = _FIXTURE_ROOT / "checkpoints"

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _assert_importable(module_name: str, attribute: str) -> None:
    """Import attribute from module -- raises ImportError if absent."""
    __import__(module_name)
    getattr(sys.modules[module_name], attribute)


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hash_prefix(hex_digest: str) -> str:
    return f"sha256:{hex_digest}"


# ===================================================================
# 1.  Reports module -import existence (RED)
# ===================================================================


class ReportsImportExistenceTests(unittest.TestCase):
    """Every public function must be importable from its declared module."""

    def test_canonical_json_is_importable(self) -> None:
        _assert_importable("covalent_design.training.reports", "canonical_json")

    def test_sha256_bytes_is_importable(self) -> None:
        _assert_importable("covalent_design.training.reports", "sha256_bytes")

    def test_sha256_file_is_importable(self) -> None:
        _assert_importable("covalent_design.training.reports", "sha256_file")

    def test_hash_resolved_config_is_importable(self) -> None:
        _assert_importable("covalent_design.training.reports", "hash_resolved_config")

    def test_hash_rule_table_is_importable(self) -> None:
        _assert_importable("covalent_design.training.reports", "hash_rule_table")

    def test_build_training_input_hashes_is_importable(self) -> None:
        _assert_importable(
            "covalent_design.training.reports", "build_training_input_hashes"
        )

    def test_build_training_run_manifest_is_importable(self) -> None:
        _assert_importable(
            "covalent_design.training.reports", "build_training_run_manifest"
        )

    def test_training_run_manifest_to_dict_is_importable(self) -> None:
        _assert_importable(
            "covalent_design.training.reports", "training_run_manifest_to_dict"
        )


# ===================================================================
# 2.  canonical_json
# ===================================================================


class CanonicalJsonTests(unittest.TestCase):
    """``canonical_json(value) -> str`` produces deterministic sorted-key JSON."""

    def test_canonical_json_returns_string(self) -> None:
        from covalent_design.training.reports import canonical_json  # RED

        result = canonical_json({"b": 2, "a": 1})
        self.assertIsInstance(result, str)

    def test_canonical_json_sorts_keys(self) -> None:
        from covalent_design.training.reports import canonical_json  # RED

        result = canonical_json({"b": 2, "a": 1, "c": 3})
        # "a" must appear before "b" in the output
        self.assertLess(result.index('"a"'), result.index('"b"'))
        self.assertLess(result.index('"b"'), result.index('"c"'))

    def test_canonical_json_nested_keys_sorted(self) -> None:
        from covalent_design.training.reports import canonical_json  # RED

        value = {"z": {"y": 1, "x": 2}, "a": 1}
        result = canonical_json(value)
        # inner object keys sorted too
        inner_start = result.index('"x"')
        inner_end = result.index('"y"')
        self.assertLess(inner_start, inner_end)

    def test_canonical_json_deterministic_across_calls(self) -> None:
        from covalent_design.training.reports import canonical_json  # RED

        value = {"b": [3, 2, 1], "a": {"d": 4, "c": 3}}
        r1 = canonical_json(value)
        r2 = canonical_json(value)
        self.assertEqual(r1, r2)

    def test_canonical_json_no_trailing_whitespace(self) -> None:
        from covalent_design.training.reports import canonical_json  # RED

        result = canonical_json({"k": "v"})
        self.assertEqual(result, result.rstrip())

    def test_canonical_json_handles_lists_primitives_and_nulls(self) -> None:
        from covalent_design.training.reports import canonical_json  # RED

        value = {
            "strings": ["b", "a"],
            "numbers": [3, 1, 2],
            "nulls": None,
            "bools": [True, False],
            "floats": [1.5, -2.0],
        }
        result = canonical_json(value)
        # Must be valid JSON
        parsed = json.loads(result)
        self.assertEqual(parsed["strings"], ["b", "a"])
        self.assertEqual(parsed["numbers"], [3, 1, 2])
        self.assertIsNone(parsed["nulls"])

    def test_canonical_json_empty_object_and_array(self) -> None:
        from covalent_design.training.reports import canonical_json  # RED

        self.assertEqual(canonical_json({}), "{}")
        self.assertEqual(canonical_json([]), "[]")


# ===================================================================
# 3.  sha256_bytes
# ===================================================================


class Sha256BytesTests(unittest.TestCase):
    """``sha256_bytes(value: bytes) -> str`` returns ``sha256:<64 hex>``."""

    def test_sha256_bytes_returns_hash_prefix_format(self) -> None:
        from covalent_design.training.reports import sha256_bytes  # RED

        result = sha256_bytes(b"hello")
        self.assertTrue(result.startswith("sha256:"))
        self.assertEqual(len(result), 7 + 64)  # "sha256:" + 64 hex chars

    def test_sha256_bytes_only_lowercase_hex(self) -> None:
        from covalent_design.training.reports import sha256_bytes  # RED

        result = sha256_bytes(b"test data")
        hex_part = result[len("sha256:"):]
        self.assertEqual(hex_part, hex_part.lower())
        self.assertTrue(all(c in "0123456789abcdef" for c in hex_part))

    def test_sha256_bytes_matches_known_hash(self) -> None:
        from covalent_design.training.reports import sha256_bytes  # RED

        expected_hex = _sha256_hex(b"predictable input")
        result = sha256_bytes(b"predictable input")
        self.assertEqual(result, _hash_prefix(expected_hex))

    def test_sha256_bytes_empty_bytes(self) -> None:
        from covalent_design.training.reports import sha256_bytes  # RED

        result = sha256_bytes(b"")
        expected_hex = _sha256_hex(b"")
        self.assertEqual(result, _hash_prefix(expected_hex))

    def test_sha256_bytes_deterministic(self) -> None:
        from covalent_design.training.reports import sha256_bytes  # RED

        data = b"deterministic test data"
        self.assertEqual(sha256_bytes(data), sha256_bytes(data))

    def test_sha256_bytes_different_input_different_hash(self) -> None:
        from covalent_design.training.reports import sha256_bytes  # RED

        h1 = sha256_bytes(b"input one")
        h2 = sha256_bytes(b"input two")
        self.assertNotEqual(h1, h2)

    def test_sha256_bytes_large_input(self) -> None:
        from covalent_design.training.reports import sha256_bytes  # RED

        data = b"x" * 100000
        result = sha256_bytes(data)
        expected_hex = _sha256_hex(data)
        self.assertEqual(result, _hash_prefix(expected_hex))


# ===================================================================
# 4.  sha256_file
# ===================================================================


class Sha256FileTests(unittest.TestCase):
    """``sha256_file(path) -> str`` returns SHA-256 of file bytes."""

    def test_sha256_file_returns_hash_prefix_format(self) -> None:
        from covalent_design.training.reports import sha256_file  # RED

        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tf:
            tf.write(b"file content for hashing")
            tmp_path = Path(tf.name)

        try:
            result = sha256_file(tmp_path)
            self.assertTrue(result.startswith("sha256:"))
            self.assertEqual(len(result), 7 + 64)
        finally:
            tmp_path.unlink()

    def test_sha256_file_matches_sha256_bytes_of_file_content(self) -> None:
        from covalent_design.training.reports import sha256_bytes, sha256_file  # RED

        content = b"exact file bytes for hash comparison"
        with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as tf:
            tf.write(content)
            tmp_path = Path(tf.name)

        try:
            file_hash = sha256_file(tmp_path)
            bytes_hash = sha256_bytes(content)
            self.assertEqual(file_hash, bytes_hash)
        finally:
            tmp_path.unlink()

    def test_sha256_file_deterministic_across_calls(self) -> None:
        from covalent_design.training.reports import sha256_file  # RED

        content = b"deterministic file content"
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tf:
            tf.write(content)
            tmp_path = Path(tf.name)

        try:
            h1 = sha256_file(tmp_path)
            h2 = sha256_file(tmp_path)
            self.assertEqual(h1, h2)
        finally:
            tmp_path.unlink()

    def test_sha256_file_empty_file(self) -> None:
        from covalent_design.training.reports import sha256_file  # RED

        with tempfile.NamedTemporaryFile(delete=False, suffix=".empty") as tf:
            tmp_path = Path(tf.name)

        try:
            result = sha256_file(tmp_path)
            expected = _hash_prefix(_sha256_hex(b""))
            self.assertEqual(result, expected)
        finally:
            tmp_path.unlink()


# ===================================================================
# 5.  hash_resolved_config
# ===================================================================


class HashResolvedConfigTests(unittest.TestCase):
    """``hash_resolved_config(resolved_config) -> str`` uses canonical JSON 鈫?SHA-256."""

    def test_hash_resolved_config_returns_hash_prefix_format(self) -> None:
        from covalent_design.training.reports import hash_resolved_config  # RED

        config = {"learning_rate": 0.001, "batch_size": 32}
        result = hash_resolved_config(config)
        self.assertTrue(result.startswith("sha256:"))
        self.assertEqual(len(result), 7 + 64)

    def test_hash_resolved_config_deterministic(self) -> None:
        from covalent_design.training.reports import hash_resolved_config  # RED

        config = {"a": 1, "b": 2}
        self.assertEqual(
            hash_resolved_config(config),
            hash_resolved_config(config),
        )

    def test_hash_resolved_config_key_order_independent(self) -> None:
        """Hashes must match regardless of key insertion order."""
        from covalent_design.training.reports import hash_resolved_config  # RED

        # In Python 3.7+, dicts preserve insertion order.
        # sorted-key canonical JSON makes the hash order-independent.
        d1 = {"a": 1, "b": 2}
        d2 = {"b": 2, "a": 1}
        self.assertEqual(hash_resolved_config(d1), hash_resolved_config(d2))

    def test_hash_resolved_config_nested_key_order_independent(self) -> None:
        from covalent_design.training.reports import hash_resolved_config  # RED

        c1 = {"outer": {"inner_b": 2, "inner_a": 1}}
        c2 = {"outer": {"inner_a": 1, "inner_b": 2}}
        self.assertEqual(hash_resolved_config(c1), hash_resolved_config(c2))

    def test_hash_resolved_config_different_configs_different_hash(self) -> None:
        from covalent_design.training.reports import hash_resolved_config  # RED

        h1 = hash_resolved_config({"k": "v1"})
        h2 = hash_resolved_config({"k": "v2"})
        self.assertNotEqual(h1, h2)

    def test_hash_resolved_config_empty_config(self) -> None:
        from covalent_design.training.reports import hash_resolved_config  # RED

        result = hash_resolved_config({})
        self.assertTrue(result.startswith("sha256:"))


# ===================================================================
# 6.  hash_rule_table
# ===================================================================


class HashRuleTableTests(unittest.TestCase):
    """``hash_rule_table(path) -> str``: parsed YAML 鈫?canonical JSON 鈫?SHA-256."""

    def test_hash_rule_table_returns_hash_prefix_format(self) -> None:
        from covalent_design.training.reports import hash_rule_table  # RED

        rule_path = _RUN_MANIFEST_FIXTURES / "rule_table.yml"
        result = hash_rule_table(rule_path)
        self.assertTrue(result.startswith("sha256:"))
        self.assertEqual(len(result), 7 + 64)

    def test_hash_rule_table_deterministic(self) -> None:
        from covalent_design.training.reports import hash_rule_table  # RED

        rule_path = _RUN_MANIFEST_FIXTURES / "rule_table.yml"
        h1 = hash_rule_table(rule_path)
        h2 = hash_rule_table(rule_path)
        self.assertEqual(h1, h2)

    def test_hash_rule_table_pure_python_no_heavy_imports(self) -> None:
        """hash_rule_table must not pull in torch, RDKit, PMDM, or PocketFlow."""
        pre = set(sys.modules.keys())
        _assert_importable("covalent_design.training.reports", "hash_rule_table")
        post = set(sys.modules.keys())
        new = post - pre
        heavy = {"torch", "rdkit", "pmdm", "pocketflow"}
        violations = [
            m for m in new
            for h in heavy
            if m.lower() == h or m.lower().startswith(h + ".")
        ]
        self.assertEqual(
            violations, [],
            f"hash_rule_table pulled in heavy deps: {violations}",
        )


# ===================================================================
# 7.  build_training_input_hashes
# ===================================================================


class BuildTrainingInputHashesTests(unittest.TestCase):
    """``build_training_input_hashes(...) -> dict[str, str]``."""

    def test_build_training_input_hashes_returns_dict(self) -> None:
        from covalent_design.training.reports import build_training_input_hashes  # RED

        hashes = build_training_input_hashes(
            records_path=_RUN_MANIFEST_FIXTURES / "records.jsonl",
            split_index_path=_RUN_MANIFEST_FIXTURES / "split_index.json",
            rule_table_path=_RUN_MANIFEST_FIXTURES / "rule_table.yml",
            quality_report_path=_RUN_MANIFEST_FIXTURES / "quality_report.json",
            visual_check_index_path=_RUN_MANIFEST_FIXTURES / "visual_check_index.json",
        )
        self.assertIsInstance(hashes, dict)

    def test_required_hash_key_constant_matches_builder_contract(self) -> None:
        self.assertEqual(
            (
                "records_jsonl",
                "split_index",
                "rule_table",
                "quality_report",
                "visual_check_index",
            ),
            TRAINING_REQUIRED_INPUT_HASH_KEYS,
        )
        self.assertEqual(
            ("quality_report", "visual_check_index", "release_gate"),
            TRAINING_RELEASE_GATE_INPUT_HASH_KEYS,
        )

    def test_build_training_input_hashes_required_keys_present(self) -> None:
        from covalent_design.training.reports import build_training_input_hashes  # RED

        hashes = build_training_input_hashes(
            records_path=_RUN_MANIFEST_FIXTURES / "records.jsonl",
            split_index_path=_RUN_MANIFEST_FIXTURES / "split_index.json",
            rule_table_path=_RUN_MANIFEST_FIXTURES / "rule_table.yml",
            quality_report_path=_RUN_MANIFEST_FIXTURES / "quality_report.json",
            visual_check_index_path=_RUN_MANIFEST_FIXTURES / "visual_check_index.json",
        )

        required = {"records_jsonl", "split_index", "rule_table",
                     "quality_report", "visual_check_index"}
        for key in required:
            self.assertIn(key, hashes, f"missing required key: {key!r}")
            self.assertTrue(hashes[key].startswith("sha256:"),
                            f"{key} hash does not start with sha256:")

    def test_build_training_input_hashes_all_hash_prefix_format(self) -> None:
        from covalent_design.training.reports import build_training_input_hashes  # RED

        hashes = build_training_input_hashes(
            records_path=_RUN_MANIFEST_FIXTURES / "records.jsonl",
            split_index_path=_RUN_MANIFEST_FIXTURES / "split_index.json",
            rule_table_path=_RUN_MANIFEST_FIXTURES / "rule_table.yml",
            quality_report_path=_RUN_MANIFEST_FIXTURES / "quality_report.json",
            visual_check_index_path=_RUN_MANIFEST_FIXTURES / "visual_check_index.json",
        )

        for key, value in hashes.items():
            with self.subTest(key=key):
                self.assertEqual(len(value), 7 + 64,
                                 f"{key} hash has wrong length: {len(value)}")
                hex_part = value[len("sha256:"):]
                self.assertTrue(
                    all(c in "0123456789abcdef" for c in hex_part),
                    f"{key} hex part has non-lowercase/hex chars",
                )

    def test_build_training_input_hashes_records_is_file_bytes_hash(self) -> None:
        from covalent_design.training.reports import (
            build_training_input_hashes,  # RED
            sha256_file,  # RED
        )

        records_path = _RUN_MANIFEST_FIXTURES / "records.jsonl"
        hashes = build_training_input_hashes(
            records_path=records_path,
            split_index_path=_RUN_MANIFEST_FIXTURES / "split_index.json",
            rule_table_path=_RUN_MANIFEST_FIXTURES / "rule_table.yml",
            quality_report_path=_RUN_MANIFEST_FIXTURES / "quality_report.json",
            visual_check_index_path=_RUN_MANIFEST_FIXTURES / "visual_check_index.json",
        )

        expected = sha256_file(records_path)
        self.assertEqual(hashes["records_jsonl"], expected)

    def test_build_training_input_hashes_split_is_file_bytes_hash(self) -> None:
        from covalent_design.training.reports import (
            build_training_input_hashes,  # RED
            sha256_file,  # RED
        )

        split_path = _RUN_MANIFEST_FIXTURES / "split_index.json"
        hashes = build_training_input_hashes(
            records_path=_RUN_MANIFEST_FIXTURES / "records.jsonl",
            split_index_path=split_path,
            rule_table_path=_RUN_MANIFEST_FIXTURES / "rule_table.yml",
            quality_report_path=_RUN_MANIFEST_FIXTURES / "quality_report.json",
            visual_check_index_path=_RUN_MANIFEST_FIXTURES / "visual_check_index.json",
        )

        expected = sha256_file(split_path)
        self.assertEqual(hashes["split_index"], expected)

    def test_build_training_input_hashes_rule_table_is_canonical_yaml_hash(self) -> None:
        from covalent_design.training.reports import (
            build_training_input_hashes,  # RED
            hash_rule_table,  # RED
        )

        rule_path = _RUN_MANIFEST_FIXTURES / "rule_table.yml"
        hashes = build_training_input_hashes(
            records_path=_RUN_MANIFEST_FIXTURES / "records.jsonl",
            split_index_path=_RUN_MANIFEST_FIXTURES / "split_index.json",
            rule_table_path=rule_path,
            quality_report_path=_RUN_MANIFEST_FIXTURES / "quality_report.json",
            visual_check_index_path=_RUN_MANIFEST_FIXTURES / "visual_check_index.json",
        )

        expected = hash_rule_table(rule_path)
        self.assertEqual(hashes["rule_table"], expected)

    def test_build_training_input_hashes_quality_report_is_file_bytes_hash(self) -> None:
        from covalent_design.training.reports import (
            build_training_input_hashes,  # RED
            sha256_file,  # RED
        )

        qr_path = _RUN_MANIFEST_FIXTURES / "quality_report.json"
        hashes = build_training_input_hashes(
            records_path=_RUN_MANIFEST_FIXTURES / "records.jsonl",
            split_index_path=_RUN_MANIFEST_FIXTURES / "split_index.json",
            rule_table_path=_RUN_MANIFEST_FIXTURES / "rule_table.yml",
            quality_report_path=qr_path,
            visual_check_index_path=_RUN_MANIFEST_FIXTURES / "visual_check_index.json",
        )

        expected = sha256_file(qr_path)
        self.assertEqual(hashes["quality_report"], expected)

    def test_build_training_input_hashes_visual_check_is_file_bytes_hash(self) -> None:
        from covalent_design.training.reports import (
            build_training_input_hashes,  # RED
            sha256_file,  # RED
        )

        vc_path = _RUN_MANIFEST_FIXTURES / "visual_check_index.json"
        hashes = build_training_input_hashes(
            records_path=_RUN_MANIFEST_FIXTURES / "records.jsonl",
            split_index_path=_RUN_MANIFEST_FIXTURES / "split_index.json",
            rule_table_path=_RUN_MANIFEST_FIXTURES / "rule_table.yml",
            quality_report_path=_RUN_MANIFEST_FIXTURES / "quality_report.json",
            visual_check_index_path=vc_path,
        )

        expected = sha256_file(vc_path)
        self.assertEqual(hashes["visual_check_index"], expected)

    def test_build_training_input_hashes_without_release_gate(self) -> None:
        from covalent_design.training.reports import build_training_input_hashes  # RED

        hashes = build_training_input_hashes(
            records_path=_RUN_MANIFEST_FIXTURES / "records.jsonl",
            split_index_path=_RUN_MANIFEST_FIXTURES / "split_index.json",
            rule_table_path=_RUN_MANIFEST_FIXTURES / "rule_table.yml",
            quality_report_path=_RUN_MANIFEST_FIXTURES / "quality_report.json",
            visual_check_index_path=_RUN_MANIFEST_FIXTURES / "visual_check_index.json",
        )
        # release_gate must NOT be present when not provided
        self.assertNotIn("release_gate", hashes)

    def test_build_training_input_hashes_with_release_gate(self) -> None:
        from covalent_design.training.reports import (
            build_training_input_hashes,  # RED
            sha256_file,  # RED
        )

        rg_path = _RUN_MANIFEST_FIXTURES / "release_gate.json"
        hashes = build_training_input_hashes(
            records_path=_RUN_MANIFEST_FIXTURES / "records.jsonl",
            split_index_path=_RUN_MANIFEST_FIXTURES / "split_index.json",
            rule_table_path=_RUN_MANIFEST_FIXTURES / "rule_table.yml",
            quality_report_path=_RUN_MANIFEST_FIXTURES / "quality_report.json",
            visual_check_index_path=_RUN_MANIFEST_FIXTURES / "visual_check_index.json",
            release_gate_path=rg_path,
        )
        self.assertIn("release_gate", hashes)
        expected = sha256_file(rg_path)
        self.assertEqual(hashes["release_gate"], expected)

    def test_build_training_input_hashes_deterministic(self) -> None:
        from covalent_design.training.reports import build_training_input_hashes  # RED

        kwargs = {
            "records_path": _RUN_MANIFEST_FIXTURES / "records.jsonl",
            "split_index_path": _RUN_MANIFEST_FIXTURES / "split_index.json",
            "rule_table_path": _RUN_MANIFEST_FIXTURES / "rule_table.yml",
            "quality_report_path": _RUN_MANIFEST_FIXTURES / "quality_report.json",
            "visual_check_index_path": _RUN_MANIFEST_FIXTURES / "visual_check_index.json",
        }
        h1 = build_training_input_hashes(**kwargs)
        h2 = build_training_input_hashes(**kwargs)
        self.assertEqual(h1, h2)

    def test_build_training_input_hashes_is_keyword_only(self) -> None:
        """The function must use keyword-only arguments after ``*``."""
        from covalent_design.training.reports import build_training_input_hashes  # RED
        import inspect

        sig = inspect.signature(build_training_input_hashes)
        params = list(sig.parameters.values())
        # First param should be * (or have kind VAR_POSITIONAL for keyword-only after)
        # Actually keyword-only args come after * or *args
        has_keyword_only_separator = any(
            p.kind == inspect.Parameter.VAR_POSITIONAL for p in params
        )
        # All parameters after the first positional-or-keyword should be keyword-only
        # The key check is that params after * must be KEYWORD_ONLY
        kw_only = [p for p in params if p.kind == inspect.Parameter.KEYWORD_ONLY]
        self.assertGreater(
            len(kw_only), 0,
            "build_training_input_hashes must have keyword-only parameters",
        )


# ===================================================================
# 8.  build_training_run_manifest
# ===================================================================


class BuildTrainingRunManifestTests(unittest.TestCase):
    """``build_training_run_manifest(...) -> TrainingRunManifest``."""

    def test_build_training_run_manifest_returns_training_run_manifest(self) -> None:
        from covalent_design.training.reports import (
            build_training_input_hashes,  # RED
            build_training_run_manifest,  # RED
        )

        input_hashes = build_training_input_hashes(
            records_path=_RUN_MANIFEST_FIXTURES / "records.jsonl",
            split_index_path=_RUN_MANIFEST_FIXTURES / "split_index.json",
            rule_table_path=_RUN_MANIFEST_FIXTURES / "rule_table.yml",
            quality_report_path=_RUN_MANIFEST_FIXTURES / "quality_report.json",
            visual_check_index_path=_RUN_MANIFEST_FIXTURES / "visual_check_index.json",
        )

        manifest = build_training_run_manifest(
            run_id="test-run-001",
            resolved_config={"model": "smoke", "seed": 42},
            records_path=_RUN_MANIFEST_FIXTURES / "records.jsonl",
            split_index_path=_RUN_MANIFEST_FIXTURES / "split_index.json",
            rule_table_path=_RUN_MANIFEST_FIXTURES / "rule_table.yml",
            quality_report_path=_RUN_MANIFEST_FIXTURES / "quality_report.json",
            visual_check_index_path=_RUN_MANIFEST_FIXTURES / "visual_check_index.json",
            checkpoint_dir="outputs/checkpoints",
            train_metrics_uri="outputs/train_metrics.jsonl",
            validation_metrics_uri="outputs/val_metrics.jsonl",
            denominator_report_uri="outputs/denominator_report.json",
        )
        self.assertIsInstance(manifest, TrainingRunManifest)

    def test_build_training_run_manifest_sets_run_id(self) -> None:
        from covalent_design.training.reports import build_training_run_manifest  # RED

        manifest = build_training_run_manifest(
            run_id="my-unique-run",
            resolved_config={"model": "smoke"},
            records_path=_RUN_MANIFEST_FIXTURES / "records.jsonl",
            split_index_path=_RUN_MANIFEST_FIXTURES / "split_index.json",
            rule_table_path=_RUN_MANIFEST_FIXTURES / "rule_table.yml",
            quality_report_path=_RUN_MANIFEST_FIXTURES / "quality_report.json",
            visual_check_index_path=_RUN_MANIFEST_FIXTURES / "visual_check_index.json",
            checkpoint_dir="outputs/ckpt",
            train_metrics_uri="outputs/train.jsonl",
            validation_metrics_uri="outputs/val.jsonl",
            denominator_report_uri="outputs/denom.json",
        )
        self.assertEqual(manifest.run_id, "my-unique-run")

    def test_build_training_run_manifest_stores_config_hash_separately(self) -> None:
        from covalent_design.training.reports import (
            build_training_run_manifest,  # RED
            hash_resolved_config,  # RED
        )

        config = {"model": "smoke", "seed": 42}
        manifest = build_training_run_manifest(
            run_id="test-run-config",
            resolved_config=config,
            records_path=_RUN_MANIFEST_FIXTURES / "records.jsonl",
            split_index_path=_RUN_MANIFEST_FIXTURES / "split_index.json",
            rule_table_path=_RUN_MANIFEST_FIXTURES / "rule_table.yml",
            quality_report_path=_RUN_MANIFEST_FIXTURES / "quality_report.json",
            visual_check_index_path=_RUN_MANIFEST_FIXTURES / "visual_check_index.json",
            checkpoint_dir="outputs/ckpt",
            train_metrics_uri="outputs/train.jsonl",
            validation_metrics_uri="outputs/val.jsonl",
            denominator_report_uri="outputs/denom.json",
        )

        expected_config_hash = hash_resolved_config(config)
        self.assertEqual(
            manifest.training_config_resolved_hash, expected_config_hash,
        )
        # config hash must not appear inside input_hashes
        self.assertNotIn("training_config_resolved", manifest.input_hashes)

    def test_build_training_run_manifest_stores_input_hashes(self) -> None:
        from covalent_design.training.reports import build_training_run_manifest  # RED

        manifest = build_training_run_manifest(
            run_id="test-run-hashes",
            resolved_config={"model": "smoke"},
            records_path=_RUN_MANIFEST_FIXTURES / "records.jsonl",
            split_index_path=_RUN_MANIFEST_FIXTURES / "split_index.json",
            rule_table_path=_RUN_MANIFEST_FIXTURES / "rule_table.yml",
            quality_report_path=_RUN_MANIFEST_FIXTURES / "quality_report.json",
            visual_check_index_path=_RUN_MANIFEST_FIXTURES / "visual_check_index.json",
            checkpoint_dir="outputs/ckpt",
            train_metrics_uri="outputs/train.jsonl",
            validation_metrics_uri="outputs/val.jsonl",
            denominator_report_uri="outputs/denom.json",
        )

        required = {"records_jsonl", "split_index", "rule_table",
                     "quality_report", "visual_check_index"}
        for key in required:
            self.assertIn(key, manifest.input_hashes,
                          f"input_hashes missing {key!r}")

    def test_build_training_run_manifest_stores_uri_fields(self) -> None:
        from covalent_design.training.reports import build_training_run_manifest  # RED

        manifest = build_training_run_manifest(
            run_id="test-run-uris",
            resolved_config={"model": "smoke"},
            records_path=_RUN_MANIFEST_FIXTURES / "records.jsonl",
            split_index_path=_RUN_MANIFEST_FIXTURES / "split_index.json",
            rule_table_path=_RUN_MANIFEST_FIXTURES / "rule_table.yml",
            quality_report_path=_RUN_MANIFEST_FIXTURES / "quality_report.json",
            visual_check_index_path=_RUN_MANIFEST_FIXTURES / "visual_check_index.json",
            checkpoint_dir="/tmp/ckpt",
            train_metrics_uri="/tmp/train.jsonl",
            validation_metrics_uri="/tmp/val.jsonl",
            denominator_report_uri="/tmp/denom.json",
        )

        self.assertEqual(manifest.checkpoint_dir, "/tmp/ckpt")
        self.assertEqual(manifest.train_metrics_uri, "/tmp/train.jsonl")
        self.assertEqual(manifest.validation_metrics_uri, "/tmp/val.jsonl")
        self.assertEqual(manifest.denominator_report_uri, "/tmp/denom.json")

    def test_build_training_run_manifest_defaults_for_completion_fields(self) -> None:
        from covalent_design.training.reports import build_training_run_manifest  # RED

        manifest = build_training_run_manifest(
            run_id="test-run-defaults",
            resolved_config={"model": "smoke"},
            records_path=_RUN_MANIFEST_FIXTURES / "records.jsonl",
            split_index_path=_RUN_MANIFEST_FIXTURES / "split_index.json",
            rule_table_path=_RUN_MANIFEST_FIXTURES / "rule_table.yml",
            quality_report_path=_RUN_MANIFEST_FIXTURES / "quality_report.json",
            visual_check_index_path=_RUN_MANIFEST_FIXTURES / "visual_check_index.json",
            checkpoint_dir="outputs/ckpt",
            train_metrics_uri="outputs/train.jsonl",
            validation_metrics_uri="outputs/val.jsonl",
            denominator_report_uri="outputs/denom.json",
        )

        self.assertFalse(manifest.train_completed)
        self.assertEqual(manifest.epochs_completed, 0)
        self.assertEqual(manifest.steps_completed, 0)
        self.assertIsNone(manifest.crash_recovery)

    def test_build_training_run_manifest_with_crash_recovery(self) -> None:
        from covalent_design.training.reports import build_training_run_manifest  # RED

        crash_info = {"last_step": 42, "error": "OOM"}
        manifest = build_training_run_manifest(
            run_id="test-run-crash",
            resolved_config={"model": "smoke"},
            records_path=_RUN_MANIFEST_FIXTURES / "records.jsonl",
            split_index_path=_RUN_MANIFEST_FIXTURES / "split_index.json",
            rule_table_path=_RUN_MANIFEST_FIXTURES / "rule_table.yml",
            quality_report_path=_RUN_MANIFEST_FIXTURES / "quality_report.json",
            visual_check_index_path=_RUN_MANIFEST_FIXTURES / "visual_check_index.json",
            checkpoint_dir="outputs/ckpt",
            train_metrics_uri="outputs/train.jsonl",
            validation_metrics_uri="outputs/val.jsonl",
            denominator_report_uri="outputs/denom.json",
            crash_recovery=crash_info,
        )

        self.assertEqual(manifest.crash_recovery, crash_info)

    def test_build_training_run_manifest_with_completion_state(self) -> None:
        from covalent_design.training.reports import build_training_run_manifest  # RED

        manifest = build_training_run_manifest(
            run_id="test-run-completed",
            resolved_config={"model": "smoke"},
            records_path=_RUN_MANIFEST_FIXTURES / "records.jsonl",
            split_index_path=_RUN_MANIFEST_FIXTURES / "split_index.json",
            rule_table_path=_RUN_MANIFEST_FIXTURES / "rule_table.yml",
            quality_report_path=_RUN_MANIFEST_FIXTURES / "quality_report.json",
            visual_check_index_path=_RUN_MANIFEST_FIXTURES / "visual_check_index.json",
            checkpoint_dir="outputs/ckpt",
            train_metrics_uri="outputs/train.jsonl",
            validation_metrics_uri="outputs/val.jsonl",
            denominator_report_uri="outputs/denom.json",
            train_completed=True,
            epochs_completed=10,
            steps_completed=5000,
        )

        self.assertTrue(manifest.train_completed)
        self.assertEqual(manifest.epochs_completed, 10)
        self.assertEqual(manifest.steps_completed, 5000)
        self.assertIsNone(manifest.crash_recovery)

    def test_build_training_run_manifest_optional_release_gate_stored(self) -> None:
        from covalent_design.training.reports import build_training_run_manifest  # RED

        manifest = build_training_run_manifest(
            run_id="test-run-rg",
            resolved_config={"model": "smoke"},
            records_path=_RUN_MANIFEST_FIXTURES / "records.jsonl",
            split_index_path=_RUN_MANIFEST_FIXTURES / "split_index.json",
            rule_table_path=_RUN_MANIFEST_FIXTURES / "rule_table.yml",
            quality_report_path=_RUN_MANIFEST_FIXTURES / "quality_report.json",
            visual_check_index_path=_RUN_MANIFEST_FIXTURES / "visual_check_index.json",
            release_gate_path=_RUN_MANIFEST_FIXTURES / "release_gate.json",
            checkpoint_dir="outputs/ckpt",
            train_metrics_uri="outputs/train.jsonl",
            validation_metrics_uri="outputs/val.jsonl",
            denominator_report_uri="outputs/denom.json",
        )

        self.assertIn("release_gate", manifest.input_hashes)

    def test_build_training_run_manifest_is_keyword_only(self) -> None:
        from covalent_design.training.reports import build_training_run_manifest  # RED
        import inspect

        sig = inspect.signature(build_training_run_manifest)
        kw_only = [
            p for p in sig.parameters.values()
            if p.kind == inspect.Parameter.KEYWORD_ONLY
        ]
        self.assertGreater(
            len(kw_only), 0,
            "build_training_run_manifest must have keyword-only parameters",
        )

    def test_build_training_run_manifest_sets_schema_and_contract_version(self) -> None:
        from covalent_design.training.reports import build_training_run_manifest  # RED

        manifest = build_training_run_manifest(
            run_id="test-run-versions",
            resolved_config={"model": "smoke"},
            records_path=_RUN_MANIFEST_FIXTURES / "records.jsonl",
            split_index_path=_RUN_MANIFEST_FIXTURES / "split_index.json",
            rule_table_path=_RUN_MANIFEST_FIXTURES / "rule_table.yml",
            quality_report_path=_RUN_MANIFEST_FIXTURES / "quality_report.json",
            visual_check_index_path=_RUN_MANIFEST_FIXTURES / "visual_check_index.json",
            checkpoint_dir="outputs/ckpt",
            train_metrics_uri="outputs/train.jsonl",
            validation_metrics_uri="outputs/val.jsonl",
            denominator_report_uri="outputs/denom.json",
        )

        self.assertEqual(manifest.schema_version, SCHEMA_VERSION)
        self.assertEqual(manifest.contract_version, CONTRACT_VERSION)
        self.assertEqual(manifest.role, "training_run_manifest")


# ===================================================================
# 9.  training_run_manifest_to_dict
# ===================================================================


class TrainingRunManifestToDictTests(unittest.TestCase):
    """``training_run_manifest_to_dict(manifest) -> dict``."""

    def test_training_run_manifest_to_dict_returns_dict(self) -> None:
        from covalent_design.training.reports import (
            build_training_run_manifest,  # RED
            training_run_manifest_to_dict,  # RED
        )

        manifest = build_training_run_manifest(
            run_id="test-dict",
            resolved_config={"model": "smoke"},
            records_path=_RUN_MANIFEST_FIXTURES / "records.jsonl",
            split_index_path=_RUN_MANIFEST_FIXTURES / "split_index.json",
            rule_table_path=_RUN_MANIFEST_FIXTURES / "rule_table.yml",
            quality_report_path=_RUN_MANIFEST_FIXTURES / "quality_report.json",
            visual_check_index_path=_RUN_MANIFEST_FIXTURES / "visual_check_index.json",
            checkpoint_dir="outputs/ckpt",
            train_metrics_uri="outputs/train.jsonl",
            validation_metrics_uri="outputs/val.jsonl",
            denominator_report_uri="outputs/denom.json",
        )

        result = training_run_manifest_to_dict(manifest)
        self.assertIsInstance(result, dict)

    def test_training_run_manifest_to_dict_contains_all_keys(self) -> None:
        from covalent_design.training.reports import (
            build_training_run_manifest,  # RED
            training_run_manifest_to_dict,  # RED
        )

        manifest = build_training_run_manifest(
            run_id="test-dict-keys",
            resolved_config={"model": "smoke"},
            records_path=_RUN_MANIFEST_FIXTURES / "records.jsonl",
            split_index_path=_RUN_MANIFEST_FIXTURES / "split_index.json",
            rule_table_path=_RUN_MANIFEST_FIXTURES / "rule_table.yml",
            quality_report_path=_RUN_MANIFEST_FIXTURES / "quality_report.json",
            visual_check_index_path=_RUN_MANIFEST_FIXTURES / "visual_check_index.json",
            checkpoint_dir="outputs/ckpt",
            train_metrics_uri="outputs/train.jsonl",
            validation_metrics_uri="outputs/val.jsonl",
            denominator_report_uri="outputs/denom.json",
        )

        result = training_run_manifest_to_dict(manifest)

        expected_keys = {
            "schema_version", "contract_version", "role",
            "run_id", "training_config_resolved_hash", "input_hashes",
            "checkpoint_dir", "train_metrics_uri", "validation_metrics_uri",
            "denominator_report_uri", "train_completed",
            "epochs_completed", "steps_completed", "crash_recovery",
        }
        self.assertEqual(expected_keys, set(result.keys()))

    def test_training_run_manifest_to_dict_is_json_serializable(self) -> None:
        from covalent_design.training.reports import (
            build_training_run_manifest,  # RED
            training_run_manifest_to_dict,  # RED
        )

        manifest = build_training_run_manifest(
            run_id="test-dict-json",
            resolved_config={"model": "smoke"},
            records_path=_RUN_MANIFEST_FIXTURES / "records.jsonl",
            split_index_path=_RUN_MANIFEST_FIXTURES / "split_index.json",
            rule_table_path=_RUN_MANIFEST_FIXTURES / "rule_table.yml",
            quality_report_path=_RUN_MANIFEST_FIXTURES / "quality_report.json",
            visual_check_index_path=_RUN_MANIFEST_FIXTURES / "visual_check_index.json",
            checkpoint_dir="outputs/ckpt",
            train_metrics_uri="outputs/train.jsonl",
            validation_metrics_uri="outputs/val.jsonl",
            denominator_report_uri="outputs/denom.json",
        )

        result = training_run_manifest_to_dict(manifest)
        serialized = json.dumps(result, sort_keys=True)
        self.assertIsInstance(serialized, str)

        # Round-trip
        parsed = json.loads(serialized)
        self.assertEqual(parsed["run_id"], "test-dict-json")

    def test_training_run_manifest_to_dict_crash_recovery_null_when_none(self) -> None:
        from covalent_design.training.reports import (
            build_training_run_manifest,  # RED
            training_run_manifest_to_dict,  # RED
        )

        manifest = build_training_run_manifest(
            run_id="test-dict-null",
            resolved_config={"model": "smoke"},
            records_path=_RUN_MANIFEST_FIXTURES / "records.jsonl",
            split_index_path=_RUN_MANIFEST_FIXTURES / "split_index.json",
            rule_table_path=_RUN_MANIFEST_FIXTURES / "rule_table.yml",
            quality_report_path=_RUN_MANIFEST_FIXTURES / "quality_report.json",
            visual_check_index_path=_RUN_MANIFEST_FIXTURES / "visual_check_index.json",
            checkpoint_dir="outputs/ckpt",
            train_metrics_uri="outputs/train.jsonl",
            validation_metrics_uri="outputs/val.jsonl",
            denominator_report_uri="outputs/denom.json",
        )

        result = training_run_manifest_to_dict(manifest)
        self.assertIsNone(result["crash_recovery"])


# ===================================================================
# 10. Checkpoints module -import existence (RED)
# ===================================================================


class CheckpointsImportExistenceTests(unittest.TestCase):
    """Every public type/function must be importable from its declared module."""

    def test_checkpoint_metadata_is_importable(self) -> None:
        _assert_importable("covalent_design.training.checkpoints", "CheckpointMetadata")

    def test_checkpoint_metadata_to_dict_is_importable(self) -> None:
        _assert_importable(
            "covalent_design.training.checkpoints", "checkpoint_metadata_to_dict"
        )

    def test_write_checkpoint_metadata_is_importable(self) -> None:
        _assert_importable(
            "covalent_design.training.checkpoints", "write_checkpoint_metadata"
        )

    def test_read_checkpoint_metadata_is_importable(self) -> None:
        _assert_importable(
            "covalent_design.training.checkpoints", "read_checkpoint_metadata"
        )

    def test_validate_checkpoint_metadata_is_importable(self) -> None:
        _assert_importable(
            "covalent_design.training.checkpoints", "validate_checkpoint_metadata"
        )


# ===================================================================
# 11. CheckpointMetadata frozen dataclass
# ===================================================================


class CheckpointMetadataContractTests(unittest.TestCase):
    """``CheckpointMetadata`` is a frozen dataclass with the specified fields."""

    def test_checkpoint_metadata_is_frozen_dataclass(self) -> None:
        from covalent_design.training.checkpoints import CheckpointMetadata  # RED
        import dataclasses

        self.assertTrue(dataclasses.is_dataclass(CheckpointMetadata))

        # Must be frozen
        self.assertTrue(
            getattr(CheckpointMetadata, "__dataclass_params__").frozen,
            "CheckpointMetadata must be frozen",
        )

    def test_checkpoint_metadata_constructs_with_required_fields(self) -> None:
        from covalent_design.training.checkpoints import CheckpointMetadata  # RED

        meta = CheckpointMetadata(
            schema_version="1",
            contract_version="1.0.0",
            role="checkpoint_manifest",
            run_id="run-001",
            step=5000,
            model_contract_version="1.0.0",
            rule_table_version="1.0.0",
            input_hashes={
                "records_jsonl": "sha256:aaaa",
                "split_index": "sha256:bbbb",
                "rule_table": "sha256:cccc",
                "training_config_resolved": "sha256:dddd",
                "quality_report": "sha256:eeee",
                "visual_check_index": "sha256:ffff",
            },
            model_weights_uri="model.pt",
            optimizer_state_uri="optim.pt",
            bond_type_vocabulary=("no_edge", "carbon-sulfur"),
        )
        self.assertIsInstance(meta, CheckpointMetadata)

    def test_checkpoint_metadata_fields_have_correct_types(self) -> None:
        from covalent_design.training.checkpoints import CheckpointMetadata  # RED

        meta = CheckpointMetadata(
            schema_version="1",
            contract_version="1.0.0",
            role="checkpoint_manifest",
            run_id="run-types",
            step=100,
            model_contract_version="1.0.0",
            rule_table_version="1.0.0",
            input_hashes={
                "records_jsonl": "sha256:" + "a" * 64,
                "split_index": "sha256:" + "b" * 64,
                "rule_table": "sha256:" + "c" * 64,
                "training_config_resolved": "sha256:" + "d" * 64,
                "quality_report": "sha256:" + "e" * 64,
                "visual_check_index": "sha256:" + "f" * 64,
            },
            model_weights_uri="model.pt",
            optimizer_state_uri="optim.pt",
            bond_type_vocabulary=("no_edge", "carbon-sulfur"),
        )

        self.assertIsInstance(meta.schema_version, str)
        self.assertIsInstance(meta.contract_version, str)
        self.assertIsInstance(meta.role, str)
        self.assertIsInstance(meta.run_id, str)
        self.assertIsInstance(meta.step, int)
        self.assertIsInstance(meta.model_contract_version, str)
        self.assertIsInstance(meta.rule_table_version, str)
        self.assertIsInstance(meta.input_hashes, dict)
        self.assertIsInstance(meta.model_weights_uri, str)
        self.assertIsInstance(meta.optimizer_state_uri, str)
        self.assertIsInstance(meta.bond_type_vocabulary, tuple)

    def test_checkpoint_metadata_is_immutable(self) -> None:
        from covalent_design.training.checkpoints import CheckpointMetadata  # RED

        meta = CheckpointMetadata(
            schema_version="1",
            contract_version="1.0.0",
            role="checkpoint_manifest",
            run_id="run-frozen",
            step=5000,
            model_contract_version="1.0.0",
            rule_table_version="1.0.0",
            input_hashes={
                "records_jsonl": "sha256:" + "a" * 64,
                "split_index": "sha256:" + "b" * 64,
                "rule_table": "sha256:" + "c" * 64,
                "training_config_resolved": "sha256:" + "d" * 64,
                "quality_report": "sha256:" + "e" * 64,
                "visual_check_index": "sha256:" + "f" * 64,
            },
            model_weights_uri="model.pt",
            optimizer_state_uri="optim.pt",
            bond_type_vocabulary=("no_edge", "carbon-sulfur"),
        )

        with self.assertRaises(Exception):
            meta.step = 6000  # type: ignore[misc]

    def test_checkpoint_metadata_no_edge_is_vocabulary_index_zero(self) -> None:
        from covalent_design.training.checkpoints import CheckpointMetadata  # RED

        meta = CheckpointMetadata(
            schema_version="1",
            contract_version="1.0.0",
            role="checkpoint_manifest",
            run_id="run-no-edge",
            step=0,
            model_contract_version="1.0.0",
            rule_table_version="1.0.0",
            input_hashes={
                "records_jsonl": "sha256:" + "0" * 64,
                "split_index": "sha256:" + "0" * 64,
                "rule_table": "sha256:" + "0" * 64,
                "training_config_resolved": "sha256:" + "0" * 64,
                "quality_report": "sha256:" + "0" * 64,
                "visual_check_index": "sha256:" + "0" * 64,
            },
            model_weights_uri="model.pt",
            optimizer_state_uri="optim.pt",
            bond_type_vocabulary=("no_edge", "carbon-sulfur"),
        )

        self.assertEqual(meta.bond_type_vocabulary[0], "no_edge")

    def test_checkpoint_metadata_optional_release_gate(self) -> None:
        from covalent_design.training.checkpoints import CheckpointMetadata  # RED

        # release_gate may be absent from input_hashes
        meta = CheckpointMetadata(
            schema_version="1",
            contract_version="1.0.0",
            role="checkpoint_manifest",
            run_id="run-no-rg",
            step=2000,
            model_contract_version="1.0.0",
            rule_table_version="1.0.0",
            input_hashes={
                "records_jsonl": "sha256:" + "a" * 64,
                "split_index": "sha256:" + "b" * 64,
                "rule_table": "sha256:" + "c" * 64,
                "training_config_resolved": "sha256:" + "d" * 64,
                "quality_report": "sha256:" + "e" * 64,
                "visual_check_index": "sha256:" + "f" * 64,
            },
            model_weights_uri="model.pt",
            optimizer_state_uri="optim.pt",
            bond_type_vocabulary=("no_edge",),
        )
        self.assertNotIn("release_gate", meta.input_hashes)

    def test_checkpoint_metadata_with_release_gate(self) -> None:
        from covalent_design.training.checkpoints import CheckpointMetadata  # RED

        meta = CheckpointMetadata(
            schema_version="1",
            contract_version="1.0.0",
            role="checkpoint_manifest",
            run_id="run-with-rg",
            step=5000,
            model_contract_version="1.0.0",
            rule_table_version="1.0.0",
            input_hashes={
                "records_jsonl": "sha256:" + "a" * 64,
                "split_index": "sha256:" + "b" * 64,
                "rule_table": "sha256:" + "c" * 64,
                "training_config_resolved": "sha256:" + "d" * 64,
                "quality_report": "sha256:" + "e" * 64,
                "visual_check_index": "sha256:" + "f" * 64,
                "release_gate": "sha256:" + "0" * 64,
            },
            model_weights_uri="model.pt",
            optimizer_state_uri="optim.pt",
            bond_type_vocabulary=("no_edge", "carbon-sulfur"),
        )
        self.assertIn("release_gate", meta.input_hashes)

    def test_checkpoint_metadata_positional_args(self) -> None:
        """All fields are positional-or-keyword but frozen after construction."""
        from covalent_design.training.checkpoints import CheckpointMetadata  # RED

        meta = CheckpointMetadata(
            "1", "1.0.0", "checkpoint_manifest", "run-pos",
            100, "1.0.0", "1.0.0",
            {"records_jsonl": "sha256:" + "0" * 64,
             "split_index": "sha256:" + "0" * 64,
             "rule_table": "sha256:" + "0" * 64,
             "training_config_resolved": "sha256:" + "0" * 64,
             "quality_report": "sha256:" + "0" * 64,
             "visual_check_index": "sha256:" + "0" * 64},
            "model.pt", "optim.pt",
            ("no_edge",),
        )
        self.assertEqual(meta.run_id, "run-pos")
        self.assertEqual(meta.step, 100)


# ===================================================================
# 12. checkpoint_metadata_to_dict
# ===================================================================


class CheckpointMetadataToDictTests(unittest.TestCase):
    """``checkpoint_metadata_to_dict(metadata) -> dict``."""

    def test_checkpoint_metadata_to_dict_returns_dict(self) -> None:
        from covalent_design.training.checkpoints import (
            CheckpointMetadata,  # RED
            checkpoint_metadata_to_dict,  # RED
        )

        meta = CheckpointMetadata(
            schema_version="1",
            contract_version="1.0.0",
            role="checkpoint_manifest",
            run_id="run-dict",
            step=5000,
            model_contract_version="1.0.0",
            rule_table_version="1.0.0",
            input_hashes={
                "records_jsonl": "sha256:" + "a" * 64,
                "split_index": "sha256:" + "b" * 64,
                "rule_table": "sha256:" + "c" * 64,
                "training_config_resolved": "sha256:" + "d" * 64,
                "quality_report": "sha256:" + "e" * 64,
                "visual_check_index": "sha256:" + "f" * 64,
            },
            model_weights_uri="model.pt",
            optimizer_state_uri="optim.pt",
            bond_type_vocabulary=("no_edge", "carbon-sulfur"),
        )

        result = checkpoint_metadata_to_dict(meta)
        self.assertIsInstance(result, dict)

    def test_checkpoint_metadata_to_dict_contains_all_keys(self) -> None:
        from covalent_design.training.checkpoints import (
            CheckpointMetadata,  # RED
            checkpoint_metadata_to_dict,  # RED
        )

        meta = CheckpointMetadata(
            schema_version="1",
            contract_version="1.0.0",
            role="checkpoint_manifest",
            run_id="run-dict-keys",
            step=5000,
            model_contract_version="1.0.0",
            rule_table_version="1.0.0",
            input_hashes={
                "records_jsonl": "sha256:" + "a" * 64,
                "split_index": "sha256:" + "b" * 64,
                "rule_table": "sha256:" + "c" * 64,
                "training_config_resolved": "sha256:" + "d" * 64,
                "quality_report": "sha256:" + "e" * 64,
                "visual_check_index": "sha256:" + "f" * 64,
            },
            model_weights_uri="model.pt",
            optimizer_state_uri="optim.pt",
            bond_type_vocabulary=("no_edge", "carbon-sulfur"),
        )

        result = checkpoint_metadata_to_dict(meta)

        expected_keys = {
            "schema_version", "contract_version", "role",
            "run_id", "step", "model_contract_version", "rule_table_version",
            "input_hashes", "model_weights_uri", "optimizer_state_uri",
            "bond_type_vocabulary",
        }
        self.assertEqual(expected_keys, set(result.keys()))

    def test_checkpoint_metadata_to_dict_is_json_serializable(self) -> None:
        from covalent_design.training.checkpoints import (
            CheckpointMetadata,  # RED
            checkpoint_metadata_to_dict,  # RED
        )

        meta = CheckpointMetadata(
            schema_version="1",
            contract_version="1.0.0",
            role="checkpoint_manifest",
            run_id="run-dict-json",
            step=5000,
            model_contract_version="1.0.0",
            rule_table_version="1.0.0",
            input_hashes={
                "records_jsonl": "sha256:" + "a" * 64,
                "split_index": "sha256:" + "b" * 64,
                "rule_table": "sha256:" + "c" * 64,
                "training_config_resolved": "sha256:" + "d" * 64,
                "quality_report": "sha256:" + "e" * 64,
                "visual_check_index": "sha256:" + "f" * 64,
            },
            model_weights_uri="model.pt",
            optimizer_state_uri="optim.pt",
            bond_type_vocabulary=("no_edge", "carbon-sulfur"),
        )

        result = checkpoint_metadata_to_dict(meta)
        serialized = json.dumps(result, sort_keys=True)
        parsed = json.loads(serialized)
        self.assertEqual(parsed["run_id"], "run-dict-json")
        self.assertEqual(parsed["step"], 5000)
        self.assertEqual(parsed["bond_type_vocabulary"], ["no_edge", "carbon-sulfur"])

    def test_checkpoint_metadata_to_dict_bond_type_vocabulary_is_list(self) -> None:
        from covalent_design.training.checkpoints import (
            CheckpointMetadata,  # RED
            checkpoint_metadata_to_dict,  # RED
        )

        meta = CheckpointMetadata(
            schema_version="1",
            contract_version="1.0.0",
            role="checkpoint_manifest",
            run_id="run-dict-vocab",
            step=0,
            model_contract_version="1.0.0",
            rule_table_version="1.0.0",
            input_hashes={
                "records_jsonl": "sha256:" + "0" * 64,
                "split_index": "sha256:" + "0" * 64,
                "rule_table": "sha256:" + "0" * 64,
                "training_config_resolved": "sha256:" + "0" * 64,
                "quality_report": "sha256:" + "0" * 64,
                "visual_check_index": "sha256:" + "0" * 64,
            },
            model_weights_uri="model.pt",
            optimizer_state_uri="optim.pt",
            bond_type_vocabulary=("no_edge", "carbon-nitrogen", "carbon-oxygen",
                                   "carbon-sulfur", "disulfide", "phosphorus-oxygen"),
        )

        result = checkpoint_metadata_to_dict(meta)
        self.assertIsInstance(result["bond_type_vocabulary"], list)
        self.assertEqual(result["bond_type_vocabulary"][0], "no_edge")


# ===================================================================
# 13. write_checkpoint_metadata
# ===================================================================


class WriteCheckpointMetadataTests(unittest.TestCase):
    """``write_checkpoint_metadata(path, metadata) -> Path``."""

    def test_write_checkpoint_metadata_returns_path(self) -> None:
        from covalent_design.training.checkpoints import (
            CheckpointMetadata,  # RED
            write_checkpoint_metadata,  # RED
        )

        meta = CheckpointMetadata(
            schema_version="1",
            contract_version="1.0.0",
            role="checkpoint_manifest",
            run_id="run-write",
            step=5000,
            model_contract_version="1.0.0",
            rule_table_version="1.0.0",
            input_hashes={
                "records_jsonl": "sha256:" + "a" * 64,
                "split_index": "sha256:" + "b" * 64,
                "rule_table": "sha256:" + "c" * 64,
                "training_config_resolved": "sha256:" + "d" * 64,
                "quality_report": "sha256:" + "e" * 64,
                "visual_check_index": "sha256:" + "f" * 64,
            },
            model_weights_uri="model.pt",
            optimizer_state_uri="optim.pt",
            bond_type_vocabulary=("no_edge", "carbon-sulfur"),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "checkpoint.yml"
            result = write_checkpoint_metadata(out_path, meta)
            self.assertIsInstance(result, Path)
            self.assertTrue(out_path.exists())

    def test_write_checkpoint_metadata_writes_valid_yaml(self) -> None:
        from covalent_design.training.checkpoints import (
            CheckpointMetadata,  # RED
            write_checkpoint_metadata,  # RED
        )

        meta = CheckpointMetadata(
            schema_version="1",
            contract_version="1.0.0",
            role="checkpoint_manifest",
            run_id="run-write-yaml",
            step=5000,
            model_contract_version="1.0.0",
            rule_table_version="1.0.0",
            input_hashes={
                "records_jsonl": "sha256:" + "a" * 64,
                "split_index": "sha256:" + "b" * 64,
                "rule_table": "sha256:" + "c" * 64,
                "training_config_resolved": "sha256:" + "d" * 64,
                "quality_report": "sha256:" + "e" * 64,
                "visual_check_index": "sha256:" + "f" * 64,
            },
            model_weights_uri="model.pt",
            optimizer_state_uri="optim.pt",
            bond_type_vocabulary=("no_edge", "carbon-sulfur"),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "checkpoint.yml"
            write_checkpoint_metadata(out_path, meta)

            # Must be parseable YAML
            import yaml

            content = out_path.read_text("utf-8")
            parsed = yaml.safe_load(content)
            self.assertIsInstance(parsed, dict)
            self.assertEqual(parsed["run_id"], "run-write-yaml")
            self.assertEqual(parsed["step"], 5000)

    def test_write_checkpoint_metadata_deterministic(self) -> None:
        from covalent_design.training.checkpoints import (
            CheckpointMetadata,  # RED
            write_checkpoint_metadata,  # RED
        )

        meta = CheckpointMetadata(
            schema_version="1",
            contract_version="1.0.0",
            role="checkpoint_manifest",
            run_id="run-det",
            step=5000,
            model_contract_version="1.0.0",
            rule_table_version="1.0.0",
            input_hashes={
                "records_jsonl": "sha256:" + "a" * 64,
                "split_index": "sha256:" + "b" * 64,
                "rule_table": "sha256:" + "c" * 64,
                "training_config_resolved": "sha256:" + "d" * 64,
                "quality_report": "sha256:" + "e" * 64,
                "visual_check_index": "sha256:" + "f" * 64,
            },
            model_weights_uri="model.pt",
            optimizer_state_uri="optim.pt",
            bond_type_vocabulary=("no_edge", "carbon-sulfur"),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            p1 = Path(tmpdir) / "a.yml"
            p2 = Path(tmpdir) / "b.yml"
            write_checkpoint_metadata(p1, meta)
            write_checkpoint_metadata(p2, meta)
            self.assertEqual(p1.read_text("utf-8"), p2.read_text("utf-8"))

    def test_write_checkpoint_metadata_no_edge_is_first_in_yaml(self) -> None:
        from covalent_design.training.checkpoints import (
            CheckpointMetadata,  # RED
            write_checkpoint_metadata,  # RED
        )

        meta = CheckpointMetadata(
            schema_version="1",
            contract_version="1.0.0",
            role="checkpoint_manifest",
            run_id="run-no-edge-yaml",
            step=0,
            model_contract_version="1.0.0",
            rule_table_version="1.0.0",
            input_hashes={
                "records_jsonl": "sha256:" + "0" * 64,
                "split_index": "sha256:" + "0" * 64,
                "rule_table": "sha256:" + "0" * 64,
                "training_config_resolved": "sha256:" + "0" * 64,
                "quality_report": "sha256:" + "0" * 64,
                "visual_check_index": "sha256:" + "0" * 64,
            },
            model_weights_uri="model.pt",
            optimizer_state_uri="optim.pt",
            bond_type_vocabulary=("no_edge", "carbon-sulfur", "disulfide"),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "checkpoint.yml"
            write_checkpoint_metadata(out_path, meta)

            import yaml

            parsed = yaml.safe_load(out_path.read_text("utf-8"))
            self.assertEqual(parsed["bond_type_vocabulary"][0], "no_edge")


# ===================================================================
# 14. read_checkpoint_metadata
# ===================================================================


class ReadCheckpointMetadataTests(unittest.TestCase):
    """``read_checkpoint_metadata(path, *, expected_contract_version=...)``."""

    def test_read_valid_checkpoint_returns_metadata_and_warnings(self) -> None:
        from covalent_design.training.checkpoints import read_checkpoint_metadata  # RED

        path = _CHECKPOINT_FIXTURES / "valid_checkpoint.yml"
        metadata, warnings = read_checkpoint_metadata(path)

        from covalent_design.training.checkpoints import CheckpointMetadata  # RED
        self.assertIsInstance(metadata, CheckpointMetadata)
        self.assertIsInstance(warnings, tuple)

    def test_read_valid_checkpoint_has_zero_warnings(self) -> None:
        from covalent_design.training.checkpoints import read_checkpoint_metadata  # RED

        path = _CHECKPOINT_FIXTURES / "valid_checkpoint.yml"
        _metadata, warnings = read_checkpoint_metadata(path)
        self.assertEqual(len(warnings), 0)

    def test_read_valid_checkpoint_parses_all_fields(self) -> None:
        from covalent_design.training.checkpoints import read_checkpoint_metadata  # RED

        path = _CHECKPOINT_FIXTURES / "valid_checkpoint.yml"
        metadata, _warnings = read_checkpoint_metadata(path)

        self.assertEqual(metadata.schema_version, "1")
        self.assertEqual(metadata.contract_version, "1.0.0")
        self.assertEqual(metadata.role, "checkpoint_manifest")
        self.assertEqual(metadata.run_id, "run-20260601-rm-test")
        self.assertEqual(metadata.step, 5000)
        self.assertEqual(metadata.model_contract_version, "1.0.0")
        self.assertEqual(metadata.rule_table_version, "1.0.0")
        self.assertEqual(metadata.model_weights_uri, "step_5000_model.pt")
        self.assertEqual(metadata.optimizer_state_uri, "step_5000_optimizer.pt")
        self.assertEqual(
            metadata.bond_type_vocabulary,
            ("no_edge", "carbon-nitrogen", "carbon-oxygen", "carbon-sulfur",
             "disulfide", "phosphorus-oxygen"),
        )

    def test_read_valid_checkpoint_input_hashes_parsed(self) -> None:
        from covalent_design.training.checkpoints import read_checkpoint_metadata  # RED

        path = _CHECKPOINT_FIXTURES / "valid_checkpoint.yml"
        metadata, _warnings = read_checkpoint_metadata(path)

        self.assertIsInstance(metadata.input_hashes, dict)
        self.assertIn("records_jsonl", metadata.input_hashes)
        self.assertIn("split_index", metadata.input_hashes)
        self.assertIn("rule_table", metadata.input_hashes)
        self.assertIn("training_config_resolved", metadata.input_hashes)
        self.assertIn("quality_report", metadata.input_hashes)
        self.assertIn("visual_check_index", metadata.input_hashes)
        self.assertIn("release_gate", metadata.input_hashes)

    def test_read_checkpoint_without_release_gate(self) -> None:
        from covalent_design.training.checkpoints import read_checkpoint_metadata  # RED

        path = _CHECKPOINT_FIXTURES / "no_release_gate_checkpoint.yml"
        metadata, _warnings = read_checkpoint_metadata(path)

        self.assertNotIn("release_gate", metadata.input_hashes)

    def test_read_checkpoint_minor_version_warns(self) -> None:
        from covalent_design.training.checkpoints import read_checkpoint_metadata  # RED

        path = _CHECKPOINT_FIXTURES / "minor_version_checkpoint.yml"
        metadata, warnings = read_checkpoint_metadata(path)

        # minor mismatch (1.1 != 1.0) must load successfully with warnings
        self.assertIsNotNone(metadata)
        self.assertGreater(len(warnings), 0)

    def test_read_checkpoint_major_version_rejects(self) -> None:
        from covalent_design.training.checkpoints import read_checkpoint_metadata  # RED

        path = _CHECKPOINT_FIXTURES / "major_version_checkpoint.yml"
        with self.assertRaises(Exception):
            read_checkpoint_metadata(path)

    def test_read_checkpoint_exact_version_no_warning(self) -> None:
        from covalent_design.training.checkpoints import read_checkpoint_metadata  # RED

        path = _CHECKPOINT_FIXTURES / "valid_checkpoint.yml"
        _metadata, warnings = read_checkpoint_metadata(path)
        self.assertEqual(len(warnings), 0,
                         "exact version match must produce zero warnings")

    def test_read_checkpoint_patch_version_difference_has_no_warning(self) -> None:
        from covalent_design.training.checkpoints import read_checkpoint_metadata

        source = (_CHECKPOINT_FIXTURES / "valid_checkpoint.yml").read_text("utf-8")
        source = source.replace(
            'contract_version: "1.0.0"',
            'contract_version: "1.0.1"',
            1,
        ).replace(
            'model_contract_version: "1.0.0"',
            'model_contract_version: "1.0.1"',
            1,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "patch-version.yml"
            path.write_text(source, encoding="utf-8")
            _metadata, warnings = read_checkpoint_metadata(path)

        self.assertEqual((), warnings)

    def test_read_checkpoint_missing_top_level_field_hard_rejects(self) -> None:
        from covalent_design.contracts import ContractError
        from covalent_design.training.checkpoints import read_checkpoint_metadata

        source = (_CHECKPOINT_FIXTURES / "valid_checkpoint.yml").read_text("utf-8")
        source = source.replace('run_id: "run-20260601-rm-test"\n', "", 1)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "missing-field.yml"
            path.write_text(source, encoding="utf-8")
            with self.assertRaises(ContractError) as ctx:
                read_checkpoint_metadata(path)

        self.assertEqual("CHECKPOINT_METADATA_MISSING_FIELD", ctx.exception.code)

    def test_read_checkpoint_invalid_hash_format_hard_rejects(self) -> None:
        from covalent_design.contracts import ContractError
        from covalent_design.training.checkpoints import read_checkpoint_metadata

        source = (_CHECKPOINT_FIXTURES / "valid_checkpoint.yml").read_text("utf-8")
        source = source.replace(
            '"sha256:a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"',
            '"not-a-sha256"',
            1,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "bad-hash.yml"
            path.write_text(source, encoding="utf-8")
            with self.assertRaises(ContractError) as ctx:
                read_checkpoint_metadata(path)

        self.assertEqual("CHECKPOINT_METADATA_INVALID", ctx.exception.code)


# ===================================================================
# 15. validate_checkpoint_metadata
# ===================================================================


class ValidateCheckpointMetadataTests(unittest.TestCase):
    """``validate_checkpoint_metadata(metadata, *, expected_contract_version=...)``."""

    def test_validate_valid_metadata_returns_empty_tuple(self) -> None:
        from covalent_design.training.checkpoints import (
            CheckpointMetadata,  # RED
            validate_checkpoint_metadata,  # RED
        )

        meta = CheckpointMetadata(
            schema_version="1",
            contract_version="1.0.0",
            role="checkpoint_manifest",
            run_id="run-validate",
            step=100,
            model_contract_version="1.0.0",
            rule_table_version="1.0.0",
            input_hashes={
                "records_jsonl": "sha256:" + "a" * 64,
                "split_index": "sha256:" + "b" * 64,
                "rule_table": "sha256:" + "c" * 64,
                "training_config_resolved": "sha256:" + "d" * 64,
                "quality_report": "sha256:" + "e" * 64,
                "visual_check_index": "sha256:" + "f" * 64,
            },
            model_weights_uri="model.pt",
            optimizer_state_uri="optim.pt",
            bond_type_vocabulary=("no_edge", "carbon-sulfur"),
        )

        errors = validate_checkpoint_metadata(meta)
        self.assertIsInstance(errors, tuple)
        self.assertEqual(len(errors), 0)

    def test_validate_minor_version_mismatch_warns(self) -> None:
        from covalent_design.training.checkpoints import (
            CheckpointMetadata,
            validate_checkpoint_metadata,
        )

        meta = CheckpointMetadata(
            schema_version="1",
            contract_version="1.1.0",
            role="checkpoint_manifest",
            run_id="run-minor",
            step=100,
            model_contract_version="1.1.0",
            rule_table_version="1.0.0",
            input_hashes={
                "records_jsonl": "sha256:" + "a" * 64,
                "split_index": "sha256:" + "b" * 64,
                "rule_table": "sha256:" + "c" * 64,
                "training_config_resolved": "sha256:" + "d" * 64,
                "quality_report": "sha256:" + "e" * 64,
                "visual_check_index": "sha256:" + "f" * 64,
            },
            model_weights_uri="model.pt",
            optimizer_state_uri="optim.pt",
            bond_type_vocabulary=("no_edge",),
        )

        warnings = validate_checkpoint_metadata(meta)
        self.assertGreater(len(warnings), 0)
        self.assertTrue(all("minor version mismatch" in item for item in warnings))

    def test_validate_major_version_mismatch_hard_rejects(self) -> None:
        from covalent_design.contracts import ContractError
        from covalent_design.training.checkpoints import (
            CheckpointMetadata,
            validate_checkpoint_metadata,
        )

        meta = CheckpointMetadata(
            schema_version="1",
            contract_version="2.0.0",
            role="checkpoint_manifest",
            run_id="run-major",
            step=100,
            model_contract_version="2.0.0",
            rule_table_version="1.0.0",
            input_hashes={
                "records_jsonl": "sha256:" + "a" * 64,
                "split_index": "sha256:" + "b" * 64,
                "rule_table": "sha256:" + "c" * 64,
                "training_config_resolved": "sha256:" + "d" * 64,
                "quality_report": "sha256:" + "e" * 64,
                "visual_check_index": "sha256:" + "f" * 64,
            },
            model_weights_uri="model.pt",
            optimizer_state_uri="optim.pt",
            bond_type_vocabulary=("no_edge",),
        )

        with self.assertRaises(ContractError) as ctx:
            validate_checkpoint_metadata(meta)

        self.assertEqual(
            "CHECKPOINT_CONTRACT_MAJOR_VERSION_MISMATCH",
            ctx.exception.code,
        )

    def test_validate_wrong_schema_version_returns_issue(self) -> None:
        from covalent_design.training.checkpoints import (
            CheckpointMetadata,
            validate_checkpoint_metadata,
        )

        meta = CheckpointMetadata(
            schema_version="2",
            contract_version="1.0.0",
            role="checkpoint_manifest",
            run_id="run-schema",
            step=100,
            model_contract_version="1.0.0",
            rule_table_version="1.0.0",
            input_hashes={
                "records_jsonl": "sha256:" + "a" * 64,
                "split_index": "sha256:" + "b" * 64,
                "rule_table": "sha256:" + "c" * 64,
                "training_config_resolved": "sha256:" + "d" * 64,
                "quality_report": "sha256:" + "e" * 64,
                "visual_check_index": "sha256:" + "f" * 64,
            },
            model_weights_uri="model.pt",
            optimizer_state_uri="optim.pt",
            bond_type_vocabulary=("no_edge",),
        )

        self.assertTrue(validate_checkpoint_metadata(meta))

    def test_validate_wrong_role_returns_issue(self) -> None:
        from covalent_design.training.checkpoints import (
            CheckpointMetadata,
            validate_checkpoint_metadata,
        )

        meta = CheckpointMetadata(
            schema_version="1",
            contract_version="1.0.0",
            role="wrong_role",
            run_id="run-role",
            step=100,
            model_contract_version="1.0.0",
            rule_table_version="1.0.0",
            input_hashes={
                "records_jsonl": "sha256:" + "a" * 64,
                "split_index": "sha256:" + "b" * 64,
                "rule_table": "sha256:" + "c" * 64,
                "training_config_resolved": "sha256:" + "d" * 64,
                "quality_report": "sha256:" + "e" * 64,
                "visual_check_index": "sha256:" + "f" * 64,
            },
            model_weights_uri="model.pt",
            optimizer_state_uri="optim.pt",
            bond_type_vocabulary=("no_edge",),
        )

        self.assertTrue(validate_checkpoint_metadata(meta))

    def test_validate_rejects_negative_step(self) -> None:
        from covalent_design.training.checkpoints import (
            CheckpointMetadata,  # RED
            validate_checkpoint_metadata,  # RED
        )

        meta = CheckpointMetadata(
            schema_version="1",
            contract_version="1.0.0",
            role="checkpoint_manifest",
            run_id="run-neg",
            step=-1,
            model_contract_version="1.0.0",
            rule_table_version="1.0.0",
            input_hashes={
                "records_jsonl": "sha256:" + "a" * 64,
                "split_index": "sha256:" + "b" * 64,
                "rule_table": "sha256:" + "c" * 64,
                "training_config_resolved": "sha256:" + "d" * 64,
                "quality_report": "sha256:" + "e" * 64,
                "visual_check_index": "sha256:" + "f" * 64,
            },
            model_weights_uri="model.pt",
            optimizer_state_uri="optim.pt",
            bond_type_vocabulary=("no_edge",),
        )

        errors = validate_checkpoint_metadata(meta)
        self.assertGreater(len(errors), 0)

    def test_validate_no_edge_not_index_zero(self) -> None:
        from covalent_design.training.checkpoints import (
            CheckpointMetadata,  # RED
            validate_checkpoint_metadata,  # RED
        )

        meta = CheckpointMetadata(
            schema_version="1",
            contract_version="1.0.0",
            role="checkpoint_manifest",
            run_id="run-wrong-vocab",
            step=100,
            model_contract_version="1.0.0",
            rule_table_version="1.0.0",
            input_hashes={
                "records_jsonl": "sha256:" + "a" * 64,
                "split_index": "sha256:" + "b" * 64,
                "rule_table": "sha256:" + "c" * 64,
                "training_config_resolved": "sha256:" + "d" * 64,
                "quality_report": "sha256:" + "e" * 64,
                "visual_check_index": "sha256:" + "f" * 64,
            },
            model_weights_uri="model.pt",
            optimizer_state_uri="optim.pt",
            bond_type_vocabulary=("carbon-sulfur", "no_edge"),
        )

        errors = validate_checkpoint_metadata(meta)
        self.assertGreater(len(errors), 0)

    def test_validate_missing_required_input_hash(self) -> None:
        from covalent_design.training.checkpoints import (
            CheckpointMetadata,  # RED
            validate_checkpoint_metadata,  # RED
        )

        meta = CheckpointMetadata(
            schema_version="1",
            contract_version="1.0.0",
            role="checkpoint_manifest",
            run_id="run-missing-hash",
            step=100,
            model_contract_version="1.0.0",
            rule_table_version="1.0.0",
            input_hashes={
                "records_jsonl": "sha256:" + "a" * 64,
                # missing split_index
                "rule_table": "sha256:" + "c" * 64,
                "training_config_resolved": "sha256:" + "d" * 64,
                "quality_report": "sha256:" + "e" * 64,
                "visual_check_index": "sha256:" + "f" * 64,
            },
            model_weights_uri="model.pt",
            optimizer_state_uri="optim.pt",
            bond_type_vocabulary=("no_edge",),
        )

        errors = validate_checkpoint_metadata(meta)
        self.assertGreater(len(errors), 0)

    def test_validate_missing_quality_report_hash(self) -> None:
        from covalent_design.training.checkpoints import (
            CheckpointMetadata,  # RED
            validate_checkpoint_metadata,  # RED
        )

        meta = CheckpointMetadata(
            schema_version="1",
            contract_version="1.0.0",
            role="checkpoint_manifest",
            run_id="run-no-qr",
            step=100,
            model_contract_version="1.0.0",
            rule_table_version="1.0.0",
            input_hashes={
                "records_jsonl": "sha256:" + "a" * 64,
                "split_index": "sha256:" + "b" * 64,
                "rule_table": "sha256:" + "c" * 64,
                "training_config_resolved": "sha256:" + "d" * 64,
                # missing quality_report
                "visual_check_index": "sha256:" + "f" * 64,
            },
            model_weights_uri="model.pt",
            optimizer_state_uri="optim.pt",
            bond_type_vocabulary=("no_edge",),
        )

        errors = validate_checkpoint_metadata(meta)
        self.assertGreater(len(errors), 0)

    def test_validate_missing_visual_check_hash(self) -> None:
        from covalent_design.training.checkpoints import (
            CheckpointMetadata,  # RED
            validate_checkpoint_metadata,  # RED
        )

        meta = CheckpointMetadata(
            schema_version="1",
            contract_version="1.0.0",
            role="checkpoint_manifest",
            run_id="run-no-vc",
            step=100,
            model_contract_version="1.0.0",
            rule_table_version="1.0.0",
            input_hashes={
                "records_jsonl": "sha256:" + "a" * 64,
                "split_index": "sha256:" + "b" * 64,
                "rule_table": "sha256:" + "c" * 64,
                "training_config_resolved": "sha256:" + "d" * 64,
                "quality_report": "sha256:" + "e" * 64,
                # missing visual_check_index
            },
            model_weights_uri="model.pt",
            optimizer_state_uri="optim.pt",
            bond_type_vocabulary=("no_edge",),
        )

        errors = validate_checkpoint_metadata(meta)
        self.assertGreater(len(errors), 0)

    def test_validate_uris_need_not_exist(self) -> None:
        """URI targets are not checked for existence during validation."""
        from covalent_design.training.checkpoints import (
            CheckpointMetadata,  # RED
            validate_checkpoint_metadata,  # RED
        )

        meta = CheckpointMetadata(
            schema_version="1",
            contract_version="1.0.0",
            role="checkpoint_manifest",
            run_id="run-fake-uris",
            step=100,
            model_contract_version="1.0.0",
            rule_table_version="1.0.0",
            input_hashes={
                "records_jsonl": "sha256:" + "a" * 64,
                "split_index": "sha256:" + "b" * 64,
                "rule_table": "sha256:" + "c" * 64,
                "training_config_resolved": "sha256:" + "d" * 64,
                "quality_report": "sha256:" + "e" * 64,
                "visual_check_index": "sha256:" + "f" * 64,
            },
            model_weights_uri="nonexistent/model.pt",
            optimizer_state_uri="nonexistent/optim.pt",
            bond_type_vocabulary=("no_edge", "carbon-sulfur"),
        )

        errors = validate_checkpoint_metadata(meta)
        self.assertEqual(len(errors), 0,
                         "nonexistent URIs must not cause validation errors")

    def test_validate_rejects_empty_vocabulary(self) -> None:
        from covalent_design.training.checkpoints import (
            CheckpointMetadata,  # RED
            validate_checkpoint_metadata,  # RED
        )

        meta = CheckpointMetadata(
            schema_version="1",
            contract_version="1.0.0",
            role="checkpoint_manifest",
            run_id="run-empty-vocab",
            step=100,
            model_contract_version="1.0.0",
            rule_table_version="1.0.0",
            input_hashes={
                "records_jsonl": "sha256:" + "a" * 64,
                "split_index": "sha256:" + "b" * 64,
                "rule_table": "sha256:" + "c" * 64,
                "training_config_resolved": "sha256:" + "d" * 64,
                "quality_report": "sha256:" + "e" * 64,
                "visual_check_index": "sha256:" + "f" * 64,
            },
            model_weights_uri="model.pt",
            optimizer_state_uri="optim.pt",
            bond_type_vocabulary=(),
        )

        errors = validate_checkpoint_metadata(meta)
        self.assertGreater(len(errors), 0)

    def test_validate_empty_run_id_rejected(self) -> None:
        from covalent_design.training.checkpoints import (
            CheckpointMetadata,  # RED
            validate_checkpoint_metadata,  # RED
        )

        meta = CheckpointMetadata(
            schema_version="1",
            contract_version="1.0.0",
            role="checkpoint_manifest",
            run_id="",
            step=100,
            model_contract_version="1.0.0",
            rule_table_version="1.0.0",
            input_hashes={
                "records_jsonl": "sha256:" + "a" * 64,
                "split_index": "sha256:" + "b" * 64,
                "rule_table": "sha256:" + "c" * 64,
                "training_config_resolved": "sha256:" + "d" * 64,
                "quality_report": "sha256:" + "e" * 64,
                "visual_check_index": "sha256:" + "f" * 64,
            },
            model_weights_uri="model.pt",
            optimizer_state_uri="optim.pt",
            bond_type_vocabulary=("no_edge",),
        )

        errors = validate_checkpoint_metadata(meta)
        self.assertGreater(len(errors), 0)

    def test_validate_rejects_duplicate_bond_types(self) -> None:
        from covalent_design.training.checkpoints import (
            CheckpointMetadata,  # RED
            validate_checkpoint_metadata,  # RED
        )

        meta = CheckpointMetadata(
            schema_version="1",
            contract_version="1.0.0",
            role="checkpoint_manifest",
            run_id="run-dup-vocab",
            step=100,
            model_contract_version="1.0.0",
            rule_table_version="1.0.0",
            input_hashes={
                "records_jsonl": "sha256:" + "a" * 64,
                "split_index": "sha256:" + "b" * 64,
                "rule_table": "sha256:" + "c" * 64,
                "training_config_resolved": "sha256:" + "d" * 64,
                "quality_report": "sha256:" + "e" * 64,
                "visual_check_index": "sha256:" + "f" * 64,
            },
            model_weights_uri="model.pt",
            optimizer_state_uri="optim.pt",
            bond_type_vocabulary=("no_edge", "carbon-sulfur", "carbon-sulfur"),
        )

        errors = validate_checkpoint_metadata(meta)
        self.assertGreater(len(errors), 0)


# ===================================================================
# 16. No-heavy-imports boundary
# ===================================================================


class NoHeavyImportsGuardTests(unittest.TestCase):
    """The reports and checkpoints modules must not import torch, RDKit, etc."""

    def test_reports_module_no_heavy_imports(self) -> None:
        pre = set(sys.modules.keys())

        mod_name = "covalent_design.training.reports"
        if mod_name in sys.modules:
            del sys.modules[mod_name]

        try:
            __import__(mod_name)
        except ImportError:
            # RED -production module does not exist yet
            pass

        post = set(sys.modules.keys())
        new = post - pre
        heavy = {"torch", "rdkit", "pmdm", "pocketflow"}
        violations = [
            m for m in new
            for h in heavy
            if m.lower() == h or m.lower().startswith(h + ".")
        ]
        self.assertEqual(violations, [],
                         f"reports module imported heavy deps: {violations}")

    def test_checkpoints_module_no_heavy_imports(self) -> None:
        pre = set(sys.modules.keys())

        mod_name = "covalent_design.training.checkpoints"
        if mod_name in sys.modules:
            del sys.modules[mod_name]

        try:
            __import__(mod_name)
        except ImportError:
            # RED -production module does not exist yet
            pass

        post = set(sys.modules.keys())
        new = post - pre
        heavy = {"torch", "rdkit", "pmdm", "pocketflow"}
        violations = [
            m for m in new
            for h in heavy
            if m.lower() == h or m.lower().startswith(h + ".")
        ]
        self.assertEqual(violations, [],
                         f"checkpoints module imported heavy deps: {violations}")


# ===================================================================
# 17. Fixture integrity
# ===================================================================


class FixtureIntegrityTests(unittest.TestCase):
    """All fixture files must be well-formed."""

    def test_rule_table_yml_exists_and_is_valid_yaml(self) -> None:
        path = _RUN_MANIFEST_FIXTURES / "rule_table.yml"
        self.assertTrue(path.exists(), f"missing: {path}")

        import yaml

        parsed = yaml.safe_load(path.read_text("utf-8"))
        self.assertIsInstance(parsed, dict)
        self.assertIn("families", parsed)
        self.assertEqual(len(parsed["families"]), 2)

    def test_split_index_json_exists_and_is_valid_json(self) -> None:
        path = _RUN_MANIFEST_FIXTURES / "split_index.json"
        self.assertTrue(path.exists(), f"missing: {path}")

        parsed = json.loads(path.read_text("utf-8"))
        self.assertEqual(parsed["role"], "split_index")

    def test_records_jsonl_exists(self) -> None:
        path = _RUN_MANIFEST_FIXTURES / "records.jsonl"
        self.assertTrue(path.exists(), f"missing: {path}")

        lines = path.read_text("utf-8").strip().splitlines()
        self.assertGreater(len(lines), 0)
        parsed = json.loads(lines[0])
        self.assertIn("record_id", parsed)

    def test_quality_report_json_exists(self) -> None:
        path = _RUN_MANIFEST_FIXTURES / "quality_report.json"
        self.assertTrue(path.exists(), f"missing: {path}")

        parsed = json.loads(path.read_text("utf-8"))
        self.assertEqual(parsed["role"], "quality_report")

    def test_visual_check_index_json_exists(self) -> None:
        path = _RUN_MANIFEST_FIXTURES / "visual_check_index.json"
        self.assertTrue(path.exists(), f"missing: {path}")

        parsed = json.loads(path.read_text("utf-8"))
        self.assertEqual(parsed["role"], "visual_check_index")

    def test_release_gate_json_exists(self) -> None:
        path = _RUN_MANIFEST_FIXTURES / "release_gate.json"
        self.assertTrue(path.exists(), f"missing: {path}")

        parsed = json.loads(path.read_text("utf-8"))
        self.assertEqual(parsed["role"], "release_gate")

    def test_valid_checkpoint_yml_exists_and_has_required_keys(self) -> None:
        path = _CHECKPOINT_FIXTURES / "valid_checkpoint.yml"
        self.assertTrue(path.exists(), f"missing: {path}")

        import yaml

        parsed = yaml.safe_load(path.read_text("utf-8"))
        for key in ("schema_version", "contract_version", "role", "run_id",
                     "step", "model_contract_version", "rule_table_version",
                     "input_hashes", "model_weights_uri", "optimizer_state_uri",
                     "bond_type_vocabulary"):
            self.assertIn(key, parsed, f"checkpoint yaml missing key: {key!r}")

    def test_minor_version_checkpoint_yml_exists(self) -> None:
        path = _CHECKPOINT_FIXTURES / "minor_version_checkpoint.yml"
        self.assertTrue(path.exists(), f"missing: {path}")

    def test_major_version_checkpoint_yml_exists(self) -> None:
        path = _CHECKPOINT_FIXTURES / "major_version_checkpoint.yml"
        self.assertTrue(path.exists(), f"missing: {path}")

    def test_no_release_gate_checkpoint_yml_exists(self) -> None:
        path = _CHECKPOINT_FIXTURES / "no_release_gate_checkpoint.yml"
        self.assertTrue(path.exists(), f"missing: {path}")

    def test_no_release_gate_checkpoint_lacks_release_gate_hash(self) -> None:
        path = _CHECKPOINT_FIXTURES / "no_release_gate_checkpoint.yml"

        import yaml

        parsed = yaml.safe_load(path.read_text("utf-8"))
        self.assertNotIn("release_gate", parsed["input_hashes"])


if __name__ == "__main__":
    unittest.main()
