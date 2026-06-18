"""Tests for the v2 environment smoke check probe."""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "v2_smoke_check.py"
HEAVY_DEPS = frozenset({"cuda", "docking", "pmdm", "pocketflow", "pytorch", "rdkit"})
HEAVY_MODULES = frozenset({"PMDM", "PocketFlow", "rdkit", "torch"})
DEPENDENCY_STATUSES = frozenset({"available", "unavailable", "not_checked", "failed"})


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        cwd=str(REPO_ROOT),
        text=True,
    )


def _payload(proc: subprocess.CompletedProcess) -> dict:
    return json.loads(proc.stdout)


def _module():
    scripts_path = str(REPO_ROOT / "scripts")
    if scripts_path not in sys.path:
        sys.path.insert(0, scripts_path)
    return importlib.import_module("v2_smoke_check")


def test_lightweight_exits_zero_and_has_required_json_fields():
    proc = _run("--profile", "lightweight")
    assert proc.returncode == 0, proc.stderr
    data = _payload(proc)
    assert data["profile"] == "lightweight"
    assert data["status"] == "pass"
    assert data["overall_status"] == "pass"
    assert data["exit_reason"] == "ok"
    for key in ("python_version", "platform", "checks", "dependency_statuses"):
        assert key in data
    assert data["checks"]["project_import"]["status"] == "pass"
    assert data["errors"] == []


def test_lightweight_output_is_deterministic():
    first = _run("--profile", "lightweight")
    second = _run("--profile", "lightweight")
    assert first.returncode == 0
    assert second.returncode == 0
    assert first.stdout == second.stdout


def test_lightweight_marks_heavy_dependencies_not_checked():
    data = _payload(_run("--profile", "lightweight"))
    assert set(data["dependency_statuses"]) == HEAVY_DEPS
    for name, status in data["dependency_statuses"].items():
        assert status["name"] == name
        assert status["required_for_profile"] is False
        assert status["status"] == "not_checked"
        assert status["status"] in DEPENDENCY_STATUSES


def test_lightweight_does_not_import_heavy_modules(monkeypatch):
    original_import_module = importlib.import_module
    heavy_calls = []

    def tracking_import(name, package=None):
        if name in HEAVY_MODULES:
            heavy_calls.append(name)
            raise AssertionError(f"lightweight imported heavy module {name}")
        return original_import_module(name, package=package)

    monkeypatch.setattr(importlib, "import_module", tracking_import)
    report, exit_code = _module()._build_report("lightweight")
    assert exit_code == 0
    assert report["status"] == "pass"
    assert heavy_calls == []


def test_heavy_reports_structured_dependency_statuses_without_traceback():
    proc = _run("--profile", "heavy")
    data = _payload(proc)
    assert proc.returncode in {0, 1, 2}
    assert "Traceback" not in proc.stdout
    assert "Traceback" not in proc.stderr
    assert data["profile"] == "heavy"
    assert set(data["dependency_statuses"]) == HEAVY_DEPS
    for name, status in data["dependency_statuses"].items():
        assert status["name"] == name
        assert status["status"] in DEPENDENCY_STATUSES
        assert isinstance(status["message"], str)
        assert "Traceback" not in status["message"]


def test_heavy_missing_dependency_is_nonzero_but_structured(monkeypatch):
    mod = _module()

    def unavailable(name, module_name):
        return {
            "message": f"No module named {module_name!r}",
            "module": module_name,
            "name": name,
            "required_for_profile": True,
            "status": "unavailable",
        }

    monkeypatch.setattr(mod, "_guarded_import", unavailable)
    monkeypatch.setattr(mod, "_docking_status", lambda: {
        "message": "no supported docking binary found on PATH",
        "name": "docking",
        "required_for_profile": True,
        "status": "unavailable",
    })
    report, exit_code = mod._build_report("heavy")
    assert exit_code == 2
    assert report["status"] == "unavailable"
    assert report["exit_reason"] == "heavy_dependency_unavailable"
    assert report["warnings"]


def test_cuda_is_not_checked_when_pytorch_is_unavailable():
    status = _module()._cuda_status({"status": "unavailable"})
    assert status["name"] == "cuda"
    assert status["required_for_profile"] is True
    assert status["status"] == "not_checked"
    assert "not checked" in status["message"]


def test_heavy_pmdm_is_unavailable_without_importing_pmdm(monkeypatch):
    original_import_module = importlib.import_module
    pmdm_calls = []

    def tracking_import(name, package=None):
        if name == "PMDM":
            pmdm_calls.append(name)
            raise AssertionError("PMDM must not be imported while license is unknown")
        return original_import_module(name, package=package)

    monkeypatch.setattr(importlib, "import_module", tracking_import)
    report, exit_code = _module()._build_report("heavy")
    pmdm = report["dependency_statuses"]["pmdm"]
    assert pmdm_calls == []
    assert pmdm["status"] == "unavailable"
    assert pmdm["reason"] == "license_unknown"
    assert pmdm["import_attempted"] is False
    assert exit_code in {0, 2}


def test_invalid_cpu_profile_is_rejected_with_structured_json():
    proc = _run("--profile", "cpu")
    assert proc.returncode == 3
    data = _payload(proc)
    assert data["profile"] == "cpu"
    assert data["status"] == "failed"
    assert data["overall_status"] == "failed"
    assert data["exit_reason"] == "unsupported_profile"
    assert data["errors"][0]["code"] == "V2_ENV_PROFILE_UNSUPPORTED"
    assert data["errors"][0]["supported_profiles"] == ["lightweight", "heavy"]
    assert "Traceback" not in proc.stdout
    assert "Traceback" not in proc.stderr


def test_missing_profile_arg_is_rejected_with_structured_json():
    proc = _run()
    assert proc.returncode == 3
    data = _payload(proc)
    assert data["profile"] == "<missing>"
    assert data["status"] == "failed"
    assert data["exit_reason"] == "unsupported_profile"


def test_dependency_status_vocabulary_is_constrained():
    mod = _module()
    for profile in ("lightweight", "heavy"):
        report, _ = mod._build_report(profile)
        for status in report["dependency_statuses"].values():
            assert status["status"] in DEPENDENCY_STATUSES
