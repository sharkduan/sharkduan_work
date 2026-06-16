"""V2 environment smoke check.

Task 37 requires this script to stay stdlib-only and lightweight-safe.
"""

from __future__ import annotations

import importlib
import json
import platform
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
ENVIRONMENT_NAME = "covalent-design-v2"
SCHEMA_VERSION = "1.0.0"
CONTRACT_VERSION = "v2-beta"
SUPPORTED_PROFILES = ("lightweight", "heavy")
GENERATED_AT = "1970-01-01T00:00:00Z"


def _json_print(payload: Dict[str, Any]) -> None:
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))


def _base_report(profile: str) -> Dict[str, Any]:
    return {
        "checks": {},
        "contract_version": CONTRACT_VERSION,
        "dependency_statuses": {},
        "environment_name": ENVIRONMENT_NAME,
        "errors": [],
        "generated_at": GENERATED_AT,
        "overall_status": "unknown",
        "platform": {
            "machine": platform.machine(),
            "python_implementation": platform.python_implementation(),
            "release": platform.release(),
            "system": platform.system(),
        },
        "profile": profile,
        "python_version": platform.python_version(),
        "role": "v2_environment_manifest",
        "schema_version": SCHEMA_VERSION,
        "warnings": [],
    }


def _unsupported_profile(profile: str) -> int:
    payload = _base_report(profile)
    payload["overall_status"] = "failed"
    payload["errors"].append(
        {
            "code": "V2_ENV_PROFILE_UNSUPPORTED",
            "message": "Unsupported v2 smoke profile. Use lightweight or heavy.",
            "profile": profile,
            "supported_profiles": list(SUPPORTED_PROFILES),
        }
    )
    _json_print(payload)
    return 3


def _parse_profile(argv: List[str]) -> Tuple[str, int]:
    if len(argv) != 3 or argv[1] != "--profile":
        return "<missing>", 3
    profile = argv[2]
    if profile not in SUPPORTED_PROFILES:
        return profile, 3
    return profile, 0


def _ensure_project_path() -> None:
    src = str(SRC_ROOT)
    if src not in sys.path:
        sys.path.insert(0, src)


def _project_import_check() -> Dict[str, Any]:
    _ensure_project_path()
    try:
        module = importlib.import_module("covalent_design")
    except Exception as exc:  # pragma: no cover - environment dependent
        return {
            "message": f"{type(exc).__name__}: {exc}",
            "module": "covalent_design",
            "status": "failed",
        }
    return {
        "module": "covalent_design",
        "module_file": str(getattr(module, "__file__", "")),
        "status": "pass",
    }


def _dependency_not_required(name: str, message: str) -> Dict[str, Any]:
    return {
        "message": message,
        "name": name,
        "required_for_profile": False,
        "status": "not_required",
    }


def _guarded_import(name: str, module_name: str) -> Dict[str, Any]:
    try:
        module = importlib.import_module(module_name)
    except ImportError as exc:
        return {
            "message": str(exc),
            "module": module_name,
            "name": name,
            "required_for_profile": True,
            "status": "unavailable",
        }
    except Exception as exc:  # pragma: no cover - depends on optional packages
        return {
            "message": f"{type(exc).__name__}: {exc}",
            "module": module_name,
            "name": name,
            "required_for_profile": True,
            "status": "failed",
        }

    return {
        "message": "import succeeded; API/version source verification remains Task 38 scope",
        "module": module_name,
        "name": name,
        "required_for_profile": True,
        "status": "available",
        "version": getattr(module, "__version__", None),
    }


def _cuda_status(torch_status: Dict[str, Any]) -> Dict[str, Any]:
    if torch_status["status"] != "available":
        return {
            "message": "PyTorch unavailable, so CUDA runtime was not checked",
            "name": "cuda",
            "required_for_profile": True,
            "status": "unavailable",
        }
    try:
        torch_module = importlib.import_module("torch")
        cuda = getattr(torch_module, "cuda", None)
        is_available = bool(cuda and cuda.is_available())
    except Exception as exc:  # pragma: no cover - depends on optional package
        return {
            "message": f"{type(exc).__name__}: {exc}",
            "name": "cuda",
            "required_for_profile": True,
            "status": "failed",
        }
    return {
        "available": is_available,
        "message": "CUDA availability reported by torch.cuda.is_available()",
        "name": "cuda",
        "required_for_profile": True,
        "status": "available" if is_available else "unavailable",
    }


def _docking_status() -> Dict[str, Any]:
    binaries = {
        name: shutil.which(name)
        for name in ("vina", "smina", "gnina")
    }
    available = any(path is not None for path in binaries.values())
    return {
        "binaries": binaries,
        "message": "docking binary found on PATH" if available else "no supported docking binary found on PATH",
        "name": "docking",
        "required_for_profile": True,
        "status": "available" if available else "unavailable",
    }


def _lightweight_dependency_statuses() -> Dict[str, Dict[str, Any]]:
    message = "heavy dependency is not required for lightweight profile"
    return {
        "cuda": _dependency_not_required("cuda", message),
        "docking": _dependency_not_required("docking", message),
        "pmdm": _dependency_not_required("pmdm", message),
        "pocketflow": _dependency_not_required("pocketflow", message),
        "pytorch": _dependency_not_required("pytorch", message),
        "rdkit": _dependency_not_required("rdkit", message),
    }


def _heavy_dependency_statuses() -> Dict[str, Dict[str, Any]]:
    statuses = {
        "pytorch": _guarded_import("pytorch", "torch"),
        "rdkit": _guarded_import("rdkit", "rdkit"),
        "pmdm": _guarded_import("pmdm", "PMDM"),
        "pocketflow": _guarded_import("pocketflow", "PocketFlow"),
        "docking": _docking_status(),
    }
    statuses["cuda"] = _cuda_status(statuses["pytorch"])
    return dict(sorted(statuses.items()))


def _build_report(profile: str) -> Tuple[Dict[str, Any], int]:
    report = _base_report(profile)
    project_check = _project_import_check()
    report["checks"]["project_import"] = project_check

    if profile == "lightweight":
        report["dependency_statuses"] = _lightweight_dependency_statuses()
    else:
        report["dependency_statuses"] = _heavy_dependency_statuses()

    if project_check["status"] != "pass":
        report["errors"].append(
            {
                "code": "V2_ENV_PROJECT_IMPORT_FAILED",
                "message": project_check.get("message", "project import failed"),
            }
        )

    heavy_failures = []
    if profile == "heavy":
        heavy_failures = [
            item
            for item in report["dependency_statuses"].values()
            if item["required_for_profile"] and item["status"] != "available"
        ]
        for item in heavy_failures:
            report["warnings"].append(
                {
                    "code": "V2_ENV_DEPENDENCY_UNAVAILABLE",
                    "dependency": item["name"],
                    "message": item["message"],
                    "status": item["status"],
                }
            )

    if report["errors"]:
        report["overall_status"] = "failed"
        return report, 1
    if heavy_failures:
        report["overall_status"] = "unavailable"
        return report, 2

    report["overall_status"] = "pass"
    return report, 0


def main(argv: List[str]) -> int:
    profile, parse_status = _parse_profile(argv)
    if parse_status != 0:
        return _unsupported_profile(profile)

    report, exit_code = _build_report(profile)
    _json_print(report)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
