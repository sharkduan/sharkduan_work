"""Fixture builder for denominator accounting tests.

Run this script to regenerate all committed fixtures under
tests/fixtures/evaluation/denominator_accounting/.

Usage:
    cd tests/fixtures/evaluation/denominator_accounting
    python builder.py
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent

SCHEMA_VERSION = "1"
CONTRACT_VERSION = "1.0.0"
REQUEST_ID = "eval-test-req"

# ===================================================================
# file I/O helpers
# ===================================================================


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True, separators=(",", ":")))
            f.write("\n")


def _ys(value: str) -> str:
    """YAML-safe string: JSON-quoted."""
    return json.dumps(value, ensure_ascii=False)


def write_manifest(path: Path, data: dict) -> None:
    lines: list[str] = []

    def _i(key: str, val: int, indent: int = 0) -> None:
        lines.append(f"{'  ' * indent}{key}: {val}")

    def _s(key: str, val: str, indent: int = 0) -> None:
        lines.append(f"{'  ' * indent}{key}: {_ys(val)}")

    def _n(key: str, indent: int = 0) -> None:
        lines.append(f"{'  ' * indent}{key}: null")

    _s("schema_version", data["schema_version"])
    _s("contract_version", data["contract_version"])
    _s("role", data["role"])
    _s("job_id", data["job_id"])
    _s("request_id", data["request_id"])
    _n("checkpoint_ref")
    _i("accepted_request_sample_count", data["accepted_request_sample_count"])
    _i("attempted_sample_count", data["attempted_sample_count"])
    _i("sampling_system_failure_count", data["sampling_system_failure_count"])
    _i("result_count", data["result_count"])
    lines.append("artifacts:")
    for key in sorted(data["artifacts"]):
        ref = data["artifacts"][key]
        lines.append(f"  {key}:")
        _s("uri", ref["uri"], indent=2)
        _s("sha256", ref["sha256"], indent=2)
        _s("format", ref["format"], indent=2)
        _s("schema_version", ref["schema_version"], indent=2)
        _s("role", ref["role"], indent=2)
        _i("bytes", ref["bytes"], indent=2)
    lines.append("")

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))


def write_request_placeholder(path: Path, request_id: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = (
        f"schema_version: {_ys(SCHEMA_VERSION)}\n"
        f"contract_version: {_ys(CONTRACT_VERSION)}\n"
        f"request_id: {_ys(request_id)}\n"
        "sample_count: 9\n"
    )
    with path.open("w", encoding="utf-8", newline="\n") as f:
        f.write(content)


def make_ref(path: Path, role: str, fmt: str) -> dict:
    return {
        "uri": path.name,
        "sha256": sha256_file(path),
        "format": fmt,
        "schema_version": SCHEMA_VERSION,
        "role": role,
        "bytes": path.stat().st_size,
    }


# ===================================================================
# shared data templates
# ===================================================================

_TARGET_ATOM: dict = {
    "chain_id": "A",
    "residue_number": 145,
    "residue_name": "CYS",
    "atom_name": "SG",
    "altloc": None,
    "insertion_code": None,
    "structure_model": 1,
    "asym_id": "A",
    "atom_serial": 1234,
}

_LIGAND_ATOM: dict = {
    "ligand_id": "LIG001",
    "atom_name": "C1",
    "atom_index": 0,
    "chain_id": None,
    "asym_id": None,
    "residue_number": None,
    "altloc": None,
}

_COVALENT_EDGE: dict = {
    "protein_atom": dict(_TARGET_ATOM),
    "ligand_atom": dict(_LIGAND_ATOM),
    "bond_type": "carbon-sulfur",
}

_GEOMETRY: dict = {
    "bond_length": 1.82,
    "protein_side_angle": 109.5,
    "ligand_side_angle": 120.0,
}

_MOL_QUALITY: dict = {
    "qed": 0.72,
    "sa_score": 3.1,
    "log_p": 2.5,
    "molecular_weight": 350.0,
}

_EDGE_CHECK: dict = {
    "check_name": "target_atom",
    "status": "pass",
    "observed_value": "SG",
    "threshold_or_rule": "CYS:SG",
    "rule_table_version": "1.0.0",
    "failure_code": None,
}

_EDGE_CHECK_FAIL: dict = {
    "check_name": "target_atom",
    "status": "fail",
    "observed_value": "OG",
    "threshold_or_rule": "CYS:SG",
    "rule_table_version": "1.0.0",
    "failure_code": None,
}

_ARTIFACTS_FULL: dict = {
    "complex_mmcif": {
        "uri": "sample_complex.mmcif",
        "sha256": "a" * 64,
        "format": "mmcif",
        "schema_version": SCHEMA_VERSION,
        "role": "complex_mmcif",
        "bytes": 16384,
    },
    "ligand_sdf": {
        "uri": "sample_ligand.sdf",
        "sha256": "b" * 64,
        "format": "sdf",
        "schema_version": SCHEMA_VERSION,
        "role": "ligand_sdf",
        "bytes": 2048,
    },
}


def _result_row(
    sample_id: int,
    gen_validity: str,
    complex_export: str,
    docking_elig: str,
    docking_run: str,
    *,
    primary_failure: str | None = None,
    secondary: list[str] | None = None,
    ligand_status: str = "present",
    ligand_atom: dict | None = None,
    covalent_edge: dict | None = None,
    edge_score: float | None = None,
    geometry: dict | None = None,
    mol_quality: dict | None = None,
    matched_warhead: str | None = None,
    predicted_warhead: str | None = None,
    covalent_docking: float | None = None,
    noncovalent: float | None = None,
    edge_checks: list[dict] | None = None,
    artifacts: dict | None = None,
) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "contract_version": CONTRACT_VERSION,
        "request_id": REQUEST_ID,
        "sample_id": sample_id,
        "residue_reaction_family": "CYS_MICHAEL_ADDITION",
        "target_atom_identity": dict(_TARGET_ATOM),
        "generation_validity_status": gen_validity,
        "complex_export_status": complex_export,
        "docking_eligibility_status": docking_elig,
        "docking_run_status": docking_run,
        "primary_failure_reason": primary_failure,
        "secondary_failure_reasons": secondary or [],
        "generated_ligand_status": ligand_status,
        "predicted_ligand_attachment_atom": ligand_atom,
        "predicted_covalent_edge": covalent_edge,
        "covalent_edge_score": edge_score,
        "geometry_metrics": geometry,
        "molecular_quality_metrics": mol_quality,
        "matched_warhead_type": matched_warhead,
        "predicted_warhead_type": predicted_warhead,
        "covalent_docking_score": covalent_docking,
        "noncovalent_vina_score": noncovalent,
        "edge_validity_checks": edge_checks or [],
        "artifacts": artifacts or {},
    }


def _valid_full(sample_id: int, **overrides: object) -> dict:
    """Fully successful valid result with all diagnostics populated."""
    complex_export = overrides.pop("complex_export", "exported")
    docking_elig = overrides.pop("docking_elig", "eligible")
    docking_run = overrides.pop("docking_run", "succeeded")
    kwargs: dict = {
        "ligand_atom": dict(_LIGAND_ATOM),
        "covalent_edge": dict(_COVALENT_EDGE),
        "edge_score": 0.85,
        "geometry": dict(_GEOMETRY),
        "mol_quality": dict(_MOL_QUALITY),
        "matched_warhead": "acrylamide",
        "predicted_warhead": "acrylamide",
        "edge_checks": [dict(_EDGE_CHECK)],
        "artifacts": dict(_ARTIFACTS_FULL),
    }
    kwargs.update(overrides)  # type: ignore[arg-type]
    return _result_row(
        sample_id,
        "valid",
        complex_export,
        docking_elig,
        docking_run,
        **kwargs,
    )


def _invalid_row(
    sample_id: int, primary_failure: str, *, secondary: list[str] | None = None
) -> dict:
    """Invalid result - not_applicable downstream, no diagnostics."""
    return _result_row(
        sample_id,
        "invalid",
        "not_applicable",
        "not_applicable",
        "not_applicable",
        primary_failure=primary_failure,
        secondary=secondary or [],
        ligand_status="absent",
        ligand_atom=None,
        covalent_edge=None,
        edge_score=None,
        geometry=None,
        mol_quality=None,
        matched_warhead=None,
        predicted_warhead=None,
        covalent_docking=None,
        noncovalent=None,
        edge_checks=[dict(_EDGE_CHECK_FAIL)],
        artifacts={},
    )


def _failure_row(
    sample_id: int,
    category: str,
    retry_count: int = 0,
    message: str | None = None,
) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "contract_version": CONTRACT_VERSION,
        "request_id": REQUEST_ID,
        "sample_id": sample_id,
        "failure_category": category,
        "failure_timestamp": "2026-06-02T00:00:00Z",
        "traceback_hash": "d" * 64,
        "log_uri": f"logs/{category}_sample_{sample_id}.log",
        "retry_count": retry_count,
        "message": message or f"{category} for sample {sample_id}",
        "resource_snapshot": None,
    }


def _retry_row(
    sample_id: int,
    category: str,
    retry_count: int,
) -> dict:
    """A non-terminal retry entry (audit-only, not counted in denominator)."""
    return {
        "schema_version": SCHEMA_VERSION,
        "contract_version": CONTRACT_VERSION,
        "request_id": REQUEST_ID,
        "sample_id": sample_id,
        "failure_category": category,
        "failure_timestamp": "2026-06-02T00:00:00Z",
        "traceback_hash": "e" * 64,
        "log_uri": f"logs/{category}_sample_{sample_id}_attempt_{retry_count}.log",
        "retry_count": retry_count,
        "message": f"retry {retry_count}: {category} for sample {sample_id}",
        "resource_snapshot": None,
    }


def _build_scenario(scenario_dir: Path, *, results: list[dict], failures: list[dict],
                    accepted: int, attempted: int, failure_count: int,
                    result_count: int | None = None,
                    extra_files: dict[str, str] | None = None) -> None:
    """Write a complete scenario directory with manifest."""
    if scenario_dir.exists():
        shutil.rmtree(scenario_dir)
    scenario_dir.mkdir(parents=True, exist_ok=True)

    write_request_placeholder(scenario_dir / "request.normalized.yml", REQUEST_ID)
    write_jsonl(scenario_dir / "results.jsonl", results)
    write_jsonl(scenario_dir / "sampling_system_failures.jsonl", failures)

    if extra_files:
        for rel_path, content in extra_files.items():
            dest = scenario_dir / rel_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")

    manifest_data = {
        "schema_version": SCHEMA_VERSION,
        "contract_version": CONTRACT_VERSION,
        "role": "generation_run_manifest",
        "job_id": scenario_dir.name,
        "request_id": REQUEST_ID,
        "accepted_request_sample_count": accepted,
        "attempted_sample_count": attempted,
        "sampling_system_failure_count": failure_count,
        "result_count": result_count if result_count is not None else len(results),
        "artifacts": {
            "request": make_ref(scenario_dir / "request.normalized.yml", "request", "yml"),
            "results": make_ref(scenario_dir / "results.jsonl", "results", "jsonl"),
            "sampling_system_failures": make_ref(
                scenario_dir / "sampling_system_failures.jsonl",
                "sampling_system_failures",
                "jsonl",
            ),
        },
    }

    write_manifest(scenario_dir / "run_manifest.yml", manifest_data)


# ===================================================================
# scenario definitions
# ===================================================================


def build_valid_mixed() -> None:
    """Mixed scenario with all lifecycle states."""
    results = [
        # sample 0: fully successful (valid -> exported -> eligible -> succeeded)
        _valid_full(0, covalent_docking=-8.5, noncovalent=-7.2),
        # sample 1: docking failed
        _valid_full(
            1,
            docking_elig="eligible",
            docking_run="failed",
            primary_failure="DOCKING_RUN_FAILED",
            covalent_docking=None,
            noncovalent=None,
        ),
        # sample 2: docking not evaluable
        _valid_full(
            2,
            docking_elig="not_evaluable",
            docking_run="not_applicable",
            primary_failure="DOCKING_NOT_EVALUABLE",
            covalent_docking=None,
            noncovalent=None,
        ),
        # sample 3: export failed
        _valid_full(
            3,
            complex_export="failed",
            docking_elig="not_applicable",
            docking_run="not_applicable",
            primary_failure="COMPLEX_EXPORT_FAILED",
            covalent_docking=None,
            noncovalent=None,
            artifacts={},
        ),
        # sample 4: invalid - no edge
        _invalid_row(4, "NO_COVALENT_EDGE_PREDICTED"),
        # sample 5: invalid - below threshold
        _invalid_row(5, "COVALENT_EDGE_BELOW_THRESHOLD"),
        # sample 6: invalid - chemistry invalid with secondaries
        _invalid_row(
            6,
            "LIGAND_CHEMISTRY_INVALID",
            secondary=["WARHEAD_MATCH_FAIL", "VALENCE_CHECK_FAIL"],
        ),
    ]

    failures = [
        _failure_row(7, "oom"),
        _failure_row(8, "crash"),
    ]

    _build_scenario(
        ROOT / "valid_mixed",
        results=results,
        failures=failures,
        accepted=9,
        attempted=7,
        failure_count=2,
    )


def build_all_success() -> None:
    """All 3 samples succeed through docking."""
    results = [
        _valid_full(0, covalent_docking=-8.1, noncovalent=-7.0),
        _valid_full(1, covalent_docking=-9.2, noncovalent=-6.8),
        _valid_full(2, covalent_docking=-7.5, noncovalent=-7.3),
    ]
    _build_scenario(
        ROOT / "all_success",
        results=results,
        failures=[],
        accepted=3,
        attempted=3,
        failure_count=0,
    )


def build_all_system_failure() -> None:
    """All 3 samples produce system failures, no results."""
    _build_scenario(
        ROOT / "all_system_failure",
        results=[],
        failures=[
            _failure_row(0, "oom"),
            _failure_row(1, "crash"),
            _failure_row(2, "timeout"),
        ],
        accepted=3,
        attempted=0,
        failure_count=3,
        result_count=0,
    )


def build_retry_diagnostics() -> None:
    """Mixed scenario where sample 2 had retries before succeeding."""
    results = [
        _valid_full(0, covalent_docking=-8.5, noncovalent=-7.2),
        # sample 1 succeeded after retries (retry entries are audit-only)
        _valid_full(1, covalent_docking=-8.1, noncovalent=-7.1),
        # sample 2 failed after exhausting retries
        _valid_full(2, docking_run="failed", primary_failure="DOCKING_RUN_FAILED",
                    covalent_docking=None, noncovalent=None),
    ]

    failures = [
        # retry attempts for sample 1 (audit-only)
        _retry_row(1, "oom", 0),
        _retry_row(1, "oom", 1),
        # final exhausted sentinel for sample 1 (succeeded on retry, so no exhausted)
        # sample 3 retries then exhausts without producing a result
        _retry_row(3, "crash", 0),
        _failure_row(3, "retry_exhausted", retry_count=2,
                     message="All 3 retry attempts exhausted for sample 3"),
    ]

    _build_scenario(
        ROOT / "retry_diagnostics",
        results=results,
        failures=failures,
        accepted=4,
        attempted=3,
        failure_count=1,  # only retry_exhausted counts as a failure
    )


def build_checksum_mismatch() -> None:
    """Manifest with a wrong checksum for results.jsonl."""
    scenario_dir = ROOT / "checksum_mismatch"
    if scenario_dir.exists():
        shutil.rmtree(scenario_dir)
    scenario_dir.mkdir(parents=True, exist_ok=True)

    results = [_valid_full(0, covalent_docking=-8.5)]
    failures: list[dict] = []

    write_request_placeholder(scenario_dir / "request.normalized.yml", REQUEST_ID)
    write_jsonl(scenario_dir / "results.jsonl", results)
    write_jsonl(scenario_dir / "sampling_system_failures.jsonl", failures)

    manifest_data = {
        "schema_version": SCHEMA_VERSION,
        "contract_version": CONTRACT_VERSION,
        "role": "generation_run_manifest",
        "job_id": "checksum_mismatch",
        "request_id": REQUEST_ID,
        "accepted_request_sample_count": 1,
        "attempted_sample_count": 1,
        "sampling_system_failure_count": 0,
        "result_count": 1,
        "artifacts": {
            "request": make_ref(scenario_dir / "request.normalized.yml", "request", "yml"),
            "results": {
                "uri": "results.jsonl",
                "sha256": "f" * 64,  # deliberately wrong
                "format": "jsonl",
                "schema_version": SCHEMA_VERSION,
                "role": "results",
                "bytes": (scenario_dir / "results.jsonl").stat().st_size,
            },
            "sampling_system_failures": make_ref(
                scenario_dir / "sampling_system_failures.jsonl",
                "sampling_system_failures",
                "jsonl",
            ),
        },
    }
    write_manifest(scenario_dir / "run_manifest.yml", manifest_data)


def build_missing_artifact() -> None:
    """Manifest references a non-existent results file."""
    scenario_dir = ROOT / "missing_artifact"
    if scenario_dir.exists():
        shutil.rmtree(scenario_dir)
    scenario_dir.mkdir(parents=True, exist_ok=True)

    failures: list[dict] = []
    write_request_placeholder(scenario_dir / "request.normalized.yml", REQUEST_ID)
    write_jsonl(scenario_dir / "sampling_system_failures.jsonl", failures)

    manifest_data = {
        "schema_version": SCHEMA_VERSION,
        "contract_version": CONTRACT_VERSION,
        "role": "generation_run_manifest",
        "job_id": "missing_artifact",
        "request_id": REQUEST_ID,
        "accepted_request_sample_count": 1,
        "attempted_sample_count": 1,
        "sampling_system_failure_count": 0,
        "result_count": 1,
        "artifacts": {
            "request": make_ref(scenario_dir / "request.normalized.yml", "request", "yml"),
            "results": {
                "uri": "nonexistent_results.jsonl",
                "sha256": "f" * 64,
                "format": "jsonl",
                "schema_version": SCHEMA_VERSION,
                "role": "results",
                "bytes": 100,
            },
            "sampling_system_failures": make_ref(
                scenario_dir / "sampling_system_failures.jsonl",
                "sampling_system_failures",
                "jsonl",
            ),
        },
    }
    write_manifest(scenario_dir / "run_manifest.yml", manifest_data)


def build_absolute_uri() -> None:
    """Artifact ref with an absolute URI path."""
    scenario_dir = ROOT / "absolute_uri"
    if scenario_dir.exists():
        shutil.rmtree(scenario_dir)
    scenario_dir.mkdir(parents=True, exist_ok=True)

    results = [_valid_full(0)]
    failures: list[dict] = []

    write_request_placeholder(scenario_dir / "request.normalized.yml", REQUEST_ID)
    write_jsonl(scenario_dir / "results.jsonl", results)
    write_jsonl(scenario_dir / "sampling_system_failures.jsonl", failures)

    results_ref = make_ref(scenario_dir / "results.jsonl", "results", "jsonl")
    manifest_data = {
        "schema_version": SCHEMA_VERSION,
        "contract_version": CONTRACT_VERSION,
        "role": "generation_run_manifest",
        "job_id": "absolute_uri",
        "request_id": REQUEST_ID,
        "accepted_request_sample_count": 1,
        "attempted_sample_count": 1,
        "sampling_system_failure_count": 0,
        "result_count": 1,
        "artifacts": {
            "request": make_ref(scenario_dir / "request.normalized.yml", "request", "yml"),
            "results": {
                **results_ref,
                "uri": "/etc/passwd",
            },
            "sampling_system_failures": make_ref(
                scenario_dir / "sampling_system_failures.jsonl",
                "sampling_system_failures",
                "jsonl",
            ),
        },
    }
    write_manifest(scenario_dir / "run_manifest.yml", manifest_data)


def build_traversal_uri() -> None:
    """Artifact ref with path traversal."""
    scenario_dir = ROOT / "traversal_uri"
    if scenario_dir.exists():
        shutil.rmtree(scenario_dir)
    scenario_dir.mkdir(parents=True, exist_ok=True)

    results = [_valid_full(0)]
    failures: list[dict] = []

    write_request_placeholder(scenario_dir / "request.normalized.yml", REQUEST_ID)
    write_jsonl(scenario_dir / "results.jsonl", results)
    write_jsonl(scenario_dir / "sampling_system_failures.jsonl", failures)

    results_ref = make_ref(scenario_dir / "results.jsonl", "results", "jsonl")
    manifest_data = {
        "schema_version": SCHEMA_VERSION,
        "contract_version": CONTRACT_VERSION,
        "role": "generation_run_manifest",
        "job_id": "traversal_uri",
        "request_id": REQUEST_ID,
        "accepted_request_sample_count": 1,
        "attempted_sample_count": 1,
        "sampling_system_failure_count": 0,
        "result_count": 1,
        "artifacts": {
            "request": make_ref(scenario_dir / "request.normalized.yml", "request", "yml"),
            "results": {
                **results_ref,
                "uri": "../../../etc/passwd",
            },
            "sampling_system_failures": make_ref(
                scenario_dir / "sampling_system_failures.jsonl",
                "sampling_system_failures",
                "jsonl",
            ),
        },
    }
    write_manifest(scenario_dir / "run_manifest.yml", manifest_data)


def build_result_count_mismatch() -> None:
    """manifest.result_count != actual JSONL row count."""
    results = [
        _valid_full(0, covalent_docking=-8.5),
        _valid_full(1, covalent_docking=-9.1),
        _valid_full(2, covalent_docking=-7.8),
    ]
    _build_scenario(
        ROOT / "result_count_mismatch",
        results=results,
        failures=[],
        accepted=3,
        attempted=3,
        failure_count=0,
        result_count=5,  # wrong: actual JSONL has 3 rows
    )


def build_extra_siblings() -> None:
    """Manifest with extra unrecognized sibling keys in artifact refs (tolerated)."""
    scenario_dir = ROOT / "extra_siblings"
    if scenario_dir.exists():
        shutil.rmtree(scenario_dir)
    scenario_dir.mkdir(parents=True, exist_ok=True)

    results = [_valid_full(0, covalent_docking=-8.5)]
    failures: list[dict] = []

    write_request_placeholder(scenario_dir / "request.normalized.yml", REQUEST_ID)
    write_jsonl(scenario_dir / "results.jsonl", results)
    write_jsonl(scenario_dir / "sampling_system_failures.jsonl", failures)

    results_ref = make_ref(scenario_dir / "results.jsonl", "results", "jsonl")
    request_ref = make_ref(scenario_dir / "request.normalized.yml", "request", "yml")
    failures_ref = make_ref(
        scenario_dir / "sampling_system_failures.jsonl",
        "sampling_system_failures",
        "jsonl",
    )

    manifest_data = {
        "schema_version": SCHEMA_VERSION,
        "contract_version": CONTRACT_VERSION,
        "role": "generation_run_manifest",
        "job_id": "extra_siblings",
        "request_id": REQUEST_ID,
        "accepted_request_sample_count": 1,
        "attempted_sample_count": 1,
        "sampling_system_failure_count": 0,
        "result_count": 1,
        "artifacts": {
            "request": request_ref,
            "results": results_ref,
            "sampling_system_failures": failures_ref,
        },
    }
    write_manifest(scenario_dir / "run_manifest.yml", manifest_data)


def build_corrupt_lifecycle() -> None:
    """Results contain a lifecycle violation (invalid sample with 'exported' status)."""
    results = [
        _valid_full(0, covalent_docking=-8.5),
        # corrupt: invalid generation but complex_export_status is "exported"
        _result_row(
            1,
            "invalid",
            "exported",  # violation: invalid samples must be not_applicable
            "not_applicable",
            "not_applicable",
            primary_failure="NO_COVALENT_EDGE_PREDICTED",
            ligand_atom=None,
            covalent_edge=None,
            edge_score=None,
            geometry=None,
            mol_quality=None,
            matched_warhead=None,
            predicted_warhead=None,
            covalent_docking=None,
            noncovalent=None,
        ),
    ]
    _build_scenario(
        ROOT / "corrupt_lifecycle",
        results=results,
        failures=[],
        accepted=2,
        attempted=2,
        failure_count=0,
    )


def build_corrupt_diagnostics() -> None:
    """Results contain a valid sample with missing required diagnostics."""
    results = [
        _valid_full(0, covalent_docking=-8.5),
        # corrupt: valid but missing predicted_covalent_edge
        _valid_full(
            1,
            covalent_edge=None,
            docking_run="not_run",
            docking_elig="eligible",
            complex_export="exported",
            primary_failure=None,
            covalent_docking=None,
            noncovalent=-6.5,
        ),
    ]
    _build_scenario(
        ROOT / "corrupt_diagnostics",
        results=results,
        failures=[],
        accepted=2,
        attempted=2,
        failure_count=0,
    )


def build_empty_failures_jsonl() -> None:
    """Empty failures JSONL is valid - only 0 bytes."""
    scenario_dir = ROOT / "empty_failures_jsonl"
    if scenario_dir.exists():
        shutil.rmtree(scenario_dir)
    scenario_dir.mkdir(parents=True, exist_ok=True)

    results = [_valid_full(0, covalent_docking=-8.5)]

    write_request_placeholder(scenario_dir / "request.normalized.yml", REQUEST_ID)
    write_jsonl(scenario_dir / "results.jsonl", results)

    # empty failures file (0 bytes, no newline)
    failures_path = scenario_dir / "sampling_system_failures.jsonl"
    failures_path.write_text("", encoding="utf-8")

    manifest_data = {
        "schema_version": SCHEMA_VERSION,
        "contract_version": CONTRACT_VERSION,
        "role": "generation_run_manifest",
        "job_id": "empty_failures_jsonl",
        "request_id": REQUEST_ID,
        "accepted_request_sample_count": 1,
        "attempted_sample_count": 1,
        "sampling_system_failure_count": 0,
        "result_count": 1,
        "artifacts": {
            "request": make_ref(scenario_dir / "request.normalized.yml", "request", "yml"),
            "results": make_ref(scenario_dir / "results.jsonl", "results", "jsonl"),
            "sampling_system_failures": make_ref(
                failures_path, "sampling_system_failures", "jsonl"
            ),
        },
    }
    write_manifest(scenario_dir / "run_manifest.yml", manifest_data)


def build_jsonl_version_invalid() -> None:
    """Results JSONL with incorrect schema_version."""
    scenario_dir = ROOT / "jsonl_version_invalid"
    if scenario_dir.exists():
        shutil.rmtree(scenario_dir)
    scenario_dir.mkdir(parents=True, exist_ok=True)

    write_request_placeholder(scenario_dir / "request.normalized.yml", REQUEST_ID)

    # results with wrong schema_version
    bad_row = _valid_full(0, covalent_docking=-8.5)
    bad_row["schema_version"] = "99"
    write_jsonl(scenario_dir / "results.jsonl", [bad_row])

    failures: list[dict] = []
    failures_path = scenario_dir / "sampling_system_failures.jsonl"
    failures_path.write_text("", encoding="utf-8")

    manifest_data = {
        "schema_version": SCHEMA_VERSION,
        "contract_version": CONTRACT_VERSION,
        "role": "generation_run_manifest",
        "job_id": "jsonl_version_invalid",
        "request_id": REQUEST_ID,
        "accepted_request_sample_count": 1,
        "attempted_sample_count": 1,
        "sampling_system_failure_count": 0,
        "result_count": 1,
        "artifacts": {
            "request": make_ref(scenario_dir / "request.normalized.yml", "request", "yml"),
            "results": make_ref(scenario_dir / "results.jsonl", "results", "jsonl"),
            "sampling_system_failures": make_ref(
                failures_path, "sampling_system_failures", "jsonl"
            ),
        },
    }
    write_manifest(scenario_dir / "run_manifest.yml", manifest_data)


def build_manifest_role_version_invalid() -> None:
    """Manifest with wrong role and wrong contract_version."""
    scenario_dir = ROOT / "manifest_role_version_invalid"
    if scenario_dir.exists():
        shutil.rmtree(scenario_dir)
    scenario_dir.mkdir(parents=True, exist_ok=True)

    results = [_valid_full(0, covalent_docking=-8.5)]
    failures: list[dict] = []

    write_request_placeholder(scenario_dir / "request.normalized.yml", REQUEST_ID)
    write_jsonl(scenario_dir / "results.jsonl", results)
    write_jsonl(scenario_dir / "sampling_system_failures.jsonl", failures)

    results_ref = make_ref(scenario_dir / "results.jsonl", "results", "jsonl")
    request_ref = make_ref(scenario_dir / "request.normalized.yml", "request", "yml")
    failures_ref = make_ref(
        scenario_dir / "sampling_system_failures.jsonl",
        "sampling_system_failures",
        "jsonl",
    )

    manifest_data = {
        "schema_version": SCHEMA_VERSION,
        "contract_version": "99.0.0",  # wrong
        "role": "wrong_role",  # wrong
        "job_id": "manifest_role_version_invalid",
        "request_id": REQUEST_ID,
        "accepted_request_sample_count": 1,
        "attempted_sample_count": 1,
        "sampling_system_failure_count": 0,
        "result_count": 1,
        "artifacts": {
            "request": request_ref,
            "results": results_ref,
            "sampling_system_failures": failures_ref,
        },
    }
    write_manifest(scenario_dir / "run_manifest.yml", manifest_data)


def build_artifact_role_format_invalid() -> None:
    """Manifest with artifact refs having wrong role/format values."""
    scenario_dir = ROOT / "artifact_role_format_invalid"
    if scenario_dir.exists():
        shutil.rmtree(scenario_dir)
    scenario_dir.mkdir(parents=True, exist_ok=True)

    results = [_valid_full(0, covalent_docking=-8.5)]
    failures: list[dict] = []

    write_request_placeholder(scenario_dir / "request.normalized.yml", REQUEST_ID)
    write_jsonl(scenario_dir / "results.jsonl", results)
    write_jsonl(scenario_dir / "sampling_system_failures.jsonl", failures)

    results_ref = make_ref(scenario_dir / "results.jsonl", "results", "jsonl")
    request_ref = make_ref(scenario_dir / "request.normalized.yml", "request", "yml")
    failures_ref = make_ref(
        scenario_dir / "sampling_system_failures.jsonl",
        "sampling_system_failures",
        "jsonl",
    )

    manifest_data = {
        "schema_version": SCHEMA_VERSION,
        "contract_version": CONTRACT_VERSION,
        "role": "generation_run_manifest",
        "job_id": "artifact_role_format_invalid",
        "request_id": REQUEST_ID,
        "accepted_request_sample_count": 1,
        "attempted_sample_count": 1,
        "sampling_system_failure_count": 0,
        "result_count": 1,
        "artifacts": {
            "request": request_ref,
            # results with wrong role
            "results": {**results_ref, "role": "wrong_results_role"},
            # sampling_system_failures with wrong format
            "sampling_system_failures": {**failures_ref, "format": "wrong_format"},
        },
    }
    write_manifest(scenario_dir / "run_manifest.yml", manifest_data)


# ===================================================================
# main
# ===================================================================


ALL_BUILDERS = [
    build_valid_mixed,
    build_all_success,
    build_all_system_failure,
    build_retry_diagnostics,
    build_checksum_mismatch,
    build_missing_artifact,
    build_absolute_uri,
    build_traversal_uri,
    build_result_count_mismatch,
    build_extra_siblings,
    build_corrupt_lifecycle,
    build_corrupt_diagnostics,
    build_empty_failures_jsonl,
    build_jsonl_version_invalid,
    build_manifest_role_version_invalid,
    build_artifact_role_format_invalid,
]


def build_all() -> None:
    for builder in ALL_BUILDERS:
        builder()
        print(f"  built: {builder.__name__}")


if __name__ == "__main__":
    build_all()
    print(f"\n{len(ALL_BUILDERS)} fixtures built under {ROOT}")
