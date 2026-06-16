"""Repository hygiene policy tests.

Validate the CI workflow's inline repository-hygiene script covers required
blocked patterns, size threshold, and narrow fixture exceptions.

The hygiene policy is enforced by the inline Python script in the
repository-hygiene job of .github/workflows/ci.yml, supplemented by
.gitignore patterns. Tests check both sources.
"""
import pathlib
import re
import unittest

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_CI_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "ci.yml"
_GITIGNORE = _REPO_ROOT / ".gitignore"


# ---------------------------------------------------------------------------
# helpers: extract CI hygiene script and parse its policy data
# ---------------------------------------------------------------------------

def _ci_text():
    return _CI_WORKFLOW.read_text(encoding="utf-8")


def _extract_hygiene_script():
    """Return the dedented inline Python script from the hygiene job."""
    lines = _ci_text().splitlines()

    # Locate the step that contains "Block generated caches and large binaries"
    step_idx = None
    for idx, line in enumerate(lines):
        if "Block generated caches and large binaries" in line:
            step_idx = idx
            break
    if step_idx is None:
        raise ValueError("Could not locate repository-hygiene step in CI workflow")

    # Find the run: | line within that step (within ~5 lines after step name)
    run_idx = None
    for idx in range(step_idx, min(step_idx + 6, len(lines))):
        if "run: |" in lines[idx]:
            run_idx = idx
            break
    if run_idx is None:
        raise ValueError("Could not find run: | in repository-hygiene step")

    run_indent = len(lines[run_idx]) - len(lines[run_idx].lstrip())
    block_lines = []
    for idx in range(run_idx + 1, len(lines)):
        line = lines[idx]
        if line.strip() == "":
            block_lines.append(line)
            continue
        cur_indent = len(line) - len(line.lstrip())
        if cur_indent <= run_indent and line.strip():
            break
        block_lines.append(line)

    if not block_lines:
        raise ValueError("Empty run block in repository-hygiene step")

    non_empty = [l for l in block_lines if l.strip()]
    if not non_empty:
        raise ValueError("Run block has no non-empty lines")
    min_indent = min(len(l) - len(l.lstrip()) for l in non_empty)

    dedented = []
    for line in block_lines:
        if line.strip():
            dedented.append(line[min_indent:])
        else:
            dedented.append("")

    return "\n".join(dedented)


def _parse_set_literal(source, var_name):
    """Extract a Python set literal assigned to *var_name* from source text.

    Returns a set of strings, or None if not found.
    """
    # Match: var_name = {"...", "...", ...}
    pattern = rf'{re.escape(var_name)}\s*=\s*\{{([^}}]+)\}}'
    match = re.search(pattern, source)
    if not match:
        return None
    content = match.group(1)
    items = re.findall(r"""["']([^"']+)["']""", content)
    return set(items)


def _parse_size_threshold(source):
    """Extract the file-size threshold (in bytes) from the hygiene script.

    Looks for pattern: st_size > N * M * K  or  st_size > N.
    """
    # Try multiplicative first: e.g. 95 * 1024 * 1024
    m = re.search(r'st_size\s*>\s*(\d+(?:_?\d+)*)\s*\*\s*(\d+(?:_?\d+)*)\s*\*\s*(\d+(?:_?\d+)*)', source)
    if m:
        return int(m.group(1)) * int(m.group(2)) * int(m.group(3))
    # Try two-term: e.g. 50 * 1024
    m = re.search(r'st_size\s*>\s*(\d+(?:_?\d+)*)\s*\*\s*(\d+(?:_?\d+)*)', source)
    if m:
        return int(m.group(1)) * int(m.group(2))
    # Try single value
    m = re.search(r'st_size\s*>\s*(\d+(?:_?\d+)*)', source)
    if m:
        return int(m.group(1))
    return None


# ---------------------------------------------------------------------------
# helpers: .gitignore pattern analysis
# ---------------------------------------------------------------------------

def _gitignore_lines():
    return _GITIGNORE.read_text(encoding="utf-8").splitlines()


def _gitignore_blocked_suffixes():
    """Extract file suffixes blocked by .gitignore."""
    suffixes = set()
    for raw in _gitignore_lines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        # Bracket patterns: *.py[cod] -> .pyc, .pyo, .pyd
        m = re.match(r'\*\.(\w+)\[([^\]]+)\]', line)
        if m:
            base = "." + m.group(1)
            for ch in m.group(2):
                suffixes.add(base + ch)
            continue
        # Simple patterns: *.ckpt -> .ckpt
        m = re.match(r'\*\.(\w+)$', line)
        if m:
            suffixes.add("." + m.group(1))
    return suffixes


def _gitignore_blocked_dirs():
    """Extract directory names blocked by .gitignore."""
    dirs = set()
    for raw in _gitignore_lines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("!"):
            continue
        # Patterns like name/ (a directory)
        if line.endswith("/") and not line.startswith("*"):
            name = line.rstrip("/")
            if "/" not in name:  # simple name, not a path
                dirs.add(name)
    return dirs


# ---------------------------------------------------------------------------
# helpers: combined policy simulation
# ---------------------------------------------------------------------------

def _path_would_be_blocked(rel_path, blocked_parts, blocked_suffixes):
    """Simulate the CI script's blocking logic for a single path.

    Returns (blocked: bool, reason: str).
    """
    path = pathlib.PurePosixPath(rel_path)
    if any(part in blocked_parts for part in path.parts):
        return True, "part-match"
    if path.suffix.lower() in blocked_suffixes:
        return True, "suffix-match"
    return False, ""


def _path_allowed_or_unblocked(rel_path, allowlist, blocked_parts, blocked_suffixes):
    if rel_path in allowlist:
        return False, "allowlist"
    return _path_would_be_blocked(rel_path, blocked_parts, blocked_suffixes)


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------

class HygieneScriptExtractionTests(unittest.TestCase):
    """Verify the CI hygiene script can be extracted and parsed."""

    @classmethod
    def setUpClass(cls):
        cls.script = _extract_hygiene_script()
        cls.blocked_suffixes = _parse_set_literal(cls.script, "blocked_suffixes")
        cls.blocked_parts = _parse_set_literal(cls.script, "blocked_parts")
        cls.size_threshold = _parse_size_threshold(cls.script)

    def test_script_extracted(self):
        self.assertIn("import subprocess", self.script)
        self.assertIn("blocked_suffixes", self.script)
        self.assertIn("blocked_parts", self.script)

    def test_blocked_suffixes_parsed(self):
        self.assertIsNotNone(self.blocked_suffixes)
        self.assertIsInstance(self.blocked_suffixes, set)
        self.assertGreater(len(self.blocked_suffixes), 0)

    def test_blocked_parts_parsed(self):
        self.assertIsNotNone(self.blocked_parts)
        self.assertIsInstance(self.blocked_parts, set)
        self.assertGreater(len(self.blocked_parts), 0)

    def test_size_threshold_parsed(self):
        self.assertIsNotNone(self.size_threshold)
        self.assertGreater(self.size_threshold, 0)


class HygienePolicyCacheBlockingTests(unittest.TestCase):
    """Verify the combined policy blocks generated cache artifacts."""

    @classmethod
    def setUpClass(cls):
        cls.script = _extract_hygiene_script()
        cls.ci_suffixes = _parse_set_literal(cls.script, "blocked_suffixes") or set()
        cls.ci_parts = _parse_set_literal(cls.script, "blocked_parts") or set()
        cls.gi_suffixes = _gitignore_blocked_suffixes()
        cls.gi_dirs = _gitignore_blocked_dirs()

    def _blocked_by_either(self, name, is_dir=True):
        """Check if *name* is blocked by CI script or .gitignore."""
        if is_dir:
            return name in self.ci_parts or name in self.gi_dirs
        else:
            return name in self.ci_suffixes or name in self.gi_suffixes

    def test_blocks_pycache(self):
        self.assertTrue(self._blocked_by_either("__pycache__", is_dir=True),
                        "__pycache__ must be blocked")

    def test_blocks_pytest_cache(self):
        self.assertTrue(self._blocked_by_either(".pytest_cache", is_dir=True),
                        ".pytest_cache must be blocked")

    def test_blocks_mypy_cache(self):
        self.assertTrue(self._blocked_by_either(".mypy_cache", is_dir=True),
                        ".mypy_cache must be blocked")

    def test_blocks_ruff_cache(self):
        self.assertTrue(self._blocked_by_either(".ruff_cache", is_dir=True),
                        ".ruff_cache must be blocked")

    def test_blocks_pyc_suffix(self):
        self.assertTrue(self._blocked_by_either(".pyc", is_dir=False),
                        ".pyc must be blocked")

    def test_blocks_pyo_suffix(self):
        self.assertTrue(self._blocked_by_either(".pyo", is_dir=False),
                        ".pyo must be blocked")


class HygienePolicySizeThresholdTests(unittest.TestCase):
    """Verify the policy has a size threshold for large binary artifacts."""

    def test_size_threshold_exists(self):
        script = _extract_hygiene_script()
        threshold = _parse_size_threshold(script)
        self.assertIsNotNone(threshold, "Size threshold not found in hygiene script")
        # Must be a reasonable size limit (< 200 MiB, > 0)
        self.assertGreater(threshold, 0)
        self.assertLess(threshold, 200 * 1024 * 1024,
                        "Size threshold should be under 200 MiB")


class HygienePolicyCheckpointBlockingTests(unittest.TestCase):
    """Verify the combined policy blocks checkpoint / model-weight suffixes."""

    REQUIRED_BLOCKED = {".ckpt", ".pt", ".pth", ".pkl", ".npy", ".npz", ".safetensors"}

    @classmethod
    def setUpClass(cls):
        cls.script = _extract_hygiene_script()
        cls.ci_suffixes = _parse_set_literal(cls.script, "blocked_suffixes") or set()
        cls.gi_suffixes = _gitignore_blocked_suffixes()

    def _blocked_by_either(self, suffix):
        return suffix in self.ci_suffixes or suffix in self.gi_suffixes

    def test_blocks_all_checkpoint_weight_suffixes(self):
        for suffix in sorted(self.REQUIRED_BLOCKED):
            with self.subTest(suffix=suffix):
                self.assertTrue(
                    self._blocked_by_either(suffix),
                    f"{suffix} must be blocked by CI script or .gitignore",
                )

    def test_gitignore_blocks_all_checkpoint_weight_suffixes(self):
        for suffix in sorted(self.REQUIRED_BLOCKED):
            with self.subTest(suffix=suffix):
                self.assertIn(
                    suffix,
                    self.gi_suffixes,
                    f"{suffix} must be blocked by .gitignore before CI",
                )


class HygienePolicyDockingLogBlockingTests(unittest.TestCase):
    """Verify the combined policy blocks broad docking / log artifacts."""

    @classmethod
    def setUpClass(cls):
        cls.script = _extract_hygiene_script()
        cls.ci_suffixes = _parse_set_literal(cls.script, "blocked_suffixes") or set()
        cls.gi_suffixes = _gitignore_blocked_suffixes()

    def test_blocks_pdbqt(self):
        combined = self.ci_suffixes | self.gi_suffixes
        self.assertIn(".pdbqt", combined, ".pdbqt must be blocked")

    def test_blocks_log(self):
        combined = self.ci_suffixes | self.gi_suffixes
        self.assertIn(".log", combined, ".log must be blocked")


class HygienePolicyFixtureExceptionTests(unittest.TestCase):
    """Verify the 6 narrow fixture exceptions are allowed by the combined policy.

    These paths are explicitly un-ignored in .gitignore and must not be
    blocked by the CI hygiene script's suffix/part checks.
    """

    EXCEPTION_PATHS = [
        "tests/fixtures/evaluation/docking_protocol/valid_manifest/output/receptor.pdbqt",
        "tests/fixtures/evaluation/docking_protocol/valid_manifest/logs/docking_failure.log",
        "tests/fixtures/training/checkpoints/valid_checkpoint.yml",
        "tests/fixtures/training/checkpoints/minor_version_checkpoint.yml",
        "tests/fixtures/training/checkpoints/major_version_checkpoint.yml",
        "tests/fixtures/training/checkpoints/no_release_gate_checkpoint.yml",
    ]

    @classmethod
    def setUpClass(cls):
        cls.script = _extract_hygiene_script()
        cls.ci_suffixes = _parse_set_literal(cls.script, "blocked_suffixes") or set()
        cls.ci_parts = _parse_set_literal(cls.script, "blocked_parts") or set()
        cls.allowlist = _parse_set_literal(cls.script, "allowlist") or set()

    def test_exception_fixtures_not_blocked_by_ci_script(self):
        for path in self.EXCEPTION_PATHS:
            with self.subTest(path=path):
                blocked, reason = _path_allowed_or_unblocked(
                    path, self.allowlist, self.ci_parts, self.ci_suffixes
                )
                self.assertFalse(
                    blocked,
                    f"{path} is blocked by CI script ({reason}); "
                    f"blocked_parts={self.ci_parts}, blocked_suffixes={self.ci_suffixes}",
                )

    def test_exception_fixture_allowlist_is_exact(self):
        self.assertEqual(set(self.EXCEPTION_PATHS), self.allowlist)

    def test_exception_fixture_files_exist(self):
        for path in self.EXCEPTION_PATHS:
            full = _REPO_ROOT / path
            with self.subTest(path=path):
                self.assertTrue(
                    full.exists(),
                    f"Exception fixture {path} does not exist on disk",
                )


if __name__ == "__main__":
    unittest.main()
