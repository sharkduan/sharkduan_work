"""CI workflow policy tests.

Validate the .github/workflows/ci.yml file against required policy:
lightweight smoke checks, no heavy dependency default-runs, no heavy installs.
"""
import pathlib
import re
import unittest

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_CI_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "ci.yml"


def _ci_text():
    return _CI_WORKFLOW.read_text(encoding="utf-8")


def _run_blocks(text):
    """Yield each run block's text from the CI workflow."""
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        if "run:" not in lines[i]:
            i += 1
            continue
        # Determine if this is run: | (multiline) or run: one-liner
        stripped = lines[i].strip()
        if stripped.startswith("run: |"):
            indent = len(lines[i]) - len(lines[i].lstrip())
            i += 1
            block_lines = []
            while i < len(lines):
                line = lines[i]
                if line.strip() == "":
                    block_lines.append(line)
                    i += 1
                    continue
                cur_indent = len(line) - len(line.lstrip())
                if cur_indent <= indent and line.strip():
                    break
                block_lines.append(line)
                i += 1
            if block_lines:
                min_indent = min(
                    (len(l) - len(l.lstrip())) for l in block_lines if l.strip()
                )
                dedented = []
                for bl in block_lines:
                    if bl.strip():
                        dedented.append(bl[min_indent:])
                    else:
                        dedented.append("")
                yield "\n".join(dedented)
        else:
            # Single-line run
            yield stripped.split(":", 1)[1].strip()
            i += 1


def _all_run_text():
    return "\n".join(_run_blocks(_ci_text()))


class CIWorkflowSmokeTests(unittest.TestCase):
    """Lightweight smoke: CI must compile and test core modules."""

    def test_workflow_file_exists(self):
        self.assertTrue(_CI_WORKFLOW.exists(),
                        f"CI workflow not found at {_CI_WORKFLOW}")

    def test_compileall_scripts_src(self):
        """CI compiles project-owned Python with compileall."""
        text = _all_run_text()
        self.assertIn("python -m compileall -q scripts src", text)

    def test_runs_pytest_on_contract_io_data_rules(self):
        """CI runs contract, io, data, and rules tests via pytest."""
        text = _all_run_text()
        self.assertIn(
            "python -m pytest tests/contracts tests/io tests/data tests/rules -q",
            text,
        )

    def test_runs_ci_policy_tests(self):
        """CI self-checks workflow and repository governance policy."""
        text = _all_run_text()
        self.assertIn("python -m pytest tests/ci -q", text)

    def test_runs_cli_exit_code_tests(self):
        """CLI structured-exit tests stay in the lightweight CI gate."""
        text = _all_run_text()
        self.assertIn("python -m pytest tests/cli -q", text)


class CIWorkflowNoHeavyDefaults(unittest.TestCase):
    """CI must not default-run heavy dependency commands."""

    def test_no_rdkit_in_run(self):
        text = _all_run_text().lower()
        self.assertNotIn("rdkit", text)

    def test_no_cuda_in_run(self):
        text = _all_run_text().lower()
        self.assertNotIn("cuda", text)

    def test_no_torch_in_run(self):
        text = _all_run_text().lower()
        self.assertNotIn("torch", text)

    def test_no_pmdm_or_pocketflow_in_run(self):
        text = _all_run_text().lower()
        for term in ("pmdm", "pocketflow"):
            self.assertNotIn(term, text,
                             f"CI run text contains heavy term: {term!r}")

    def test_no_training_inference_evaluation_modules_in_run(self):
        """CI must not invoke training, inference, or evaluation CLI modules."""
        text = _all_run_text()
        prohibited = [
            "python -m covalent_design.training",
            "python -m covalent_design.inference",
            "python -m covalent_design.evaluation",
        ]
        for cmd in prohibited:
            self.assertNotIn(cmd, text,
                             f"CI runs heavy module: {cmd!r}")

    def test_no_docking_engine_run(self):
        text = _all_run_text().lower()
        docking_terms = ("autodock", "quickvina", "vina", "smina", "glide")
        for term in docking_terms:
            self.assertNotIn(term, text,
                             f"CI run text contains docking engine: {term!r}")


class CIWorkflowNoHeavyInstalls(unittest.TestCase):
    """CI must not install heavy dependencies."""

    def test_no_heavy_pip_installs(self):
        text = _all_run_text().lower()
        heavy = ("rdkit", "torch", "cuda", "cudnn", "autodock", "vina",
                 "meeko", "openbabel", "pytorch", "tensorflow", "jax")
        for pkg in heavy:
            pip_cmd = f"pip install {pkg}"
            self.assertNotIn(pip_cmd, text,
                             f"CI installs heavy package: {pip_cmd!r}")

    def test_no_heavy_conda_installs(self):
        text = _all_run_text().lower()
        heavy = ("rdkit", "pytorch", "cudatoolkit", "cuda")
        for pkg in heavy:
            conda_cmd = f"conda install {pkg}"
            self.assertNotIn(conda_cmd, text,
                             f"CI installs heavy package: {conda_cmd!r}")


if __name__ == "__main__":
    unittest.main()
