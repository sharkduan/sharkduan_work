"""Fixture builder for lifecycle reports tests.

Run this script to regenerate committed fixtures under
tests/fixtures/evaluation/lifecycle_reports/.

Usage:
    cd tests/fixtures/evaluation/lifecycle_reports
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
# file I/O (same pattern as denominator_accounting/builder.py)
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
    family: str = "CYS_MICHAEL_ADDITION",
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
        "residue_reaction_family": family,
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
    family = overrides.pop("family", "CYS_MICHAEL_ADDITION")
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
    kwargs.update(overrides)
    return _result_row(
        sample_id,
        "valid",
        complex_export,
        docking_elig,
        docking_run,
        family=family,
        **kwargs,
    )


def _invalid_row(
    sample_id: int,
    primary_failure: str,
    *,
    family: str = "CYS_MICHAEL_ADDITION",
    secondary: list[str] | None = None,
) -> dict:
    """Invalid result - not_applicable downstream, no diagnostics."""
    return _result_row(
        sample_id,
        "invalid",
        "not_applicable",
        "not_applicable",
        "not_applicable",
        family=family,
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


def _build_scenario(
    scenario_dir: Path,
    *,
    results: list[dict],
    failures: list[dict],
    accepted: int,
    attempted: int,
    failure_count: int,
    result_count: int | None = None,
) -> None:
    """Write a complete scenario directory with manifest."""
    if scenario_dir.exists():
        shutil.rmtree(scenario_dir)
    scenario_dir.mkdir(parents=True, exist_ok=True)

    write_request_placeholder(scenario_dir / "request.normalized.yml", REQUEST_ID)
    write_jsonl(scenario_dir / "results.jsonl", results)
    write_jsonl(scenario_dir / "sampling_system_failures.jsonl", failures)

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


def build_valid_mixed_families() -> None:
    """Multi-family mixed lifecycle scenario.

    CYS_MICHAEL_ADDITION: 4 results (1 succeeded, 1 docking-failed,
      1 export-failed, 1 invalid)
    SER_MICHAEL_ADDITION: 3 results (1 succeeded, 1 invalid,
      1 not-evaluable)
    """
    results = [
        # CYS family - sample 0: fully successful
        _valid_full(0, family="CYS_MICHAEL_ADDITION", covalent_docking=-8.5, noncovalent=-7.2),
        # CYS family - sample 1: docking failed
        _valid_full(
            1,
            family="CYS_MICHAEL_ADDITION",
            docking_elig="eligible",
            docking_run="failed",
            primary_failure="DOCKING_RUN_FAILED",
            covalent_docking=None,
            noncovalent=None,
        ),
        # CYS family - sample 2: export failed
        _valid_full(
            2,
            family="CYS_MICHAEL_ADDITION",
            complex_export="failed",
            docking_elig="not_applicable",
            docking_run="not_applicable",
            primary_failure="COMPLEX_EXPORT_FAILED",
            covalent_docking=None,
            noncovalent=None,
            artifacts={},
        ),
        # CYS family - sample 3: invalid (no edge)
        _invalid_row(3, "NO_COVALENT_EDGE_PREDICTED", family="CYS_MICHAEL_ADDITION"),
        # SER family - sample 4: fully successful
        _valid_full(4, family="SER_MICHAEL_ADDITION", covalent_docking=-9.1, noncovalent=-6.8),
        # SER family - sample 5: invalid (gate fail with secondaries)
        _invalid_row(
            5,
            "WARHEAD_MATCH_FAIL",
            family="SER_MICHAEL_ADDITION",
            secondary=["VALENCE_CHECK_FAIL", "GEOMETRY_CHECK_FAIL"],
        ),
        # SER family - sample 6: not docking evaluable
        _valid_full(
            6,
            family="SER_MICHAEL_ADDITION",
            docking_elig="not_evaluable",
            docking_run="not_applicable",
            primary_failure="DOCKING_NOT_EVALUABLE",
            covalent_docking=None,
            noncovalent=None,
        ),
    ]

    failures = [
        _failure_row(7, "oom"),
    ]

    _build_scenario(
        ROOT / "valid_mixed_families",
        results=results,
        failures=failures,
        accepted=8,
        attempted=7,
        failure_count=1,
    )


def build_corrupt_lifecycle_mixed() -> None:
    """Contains a corrupt lifecycle row (invalid gen + succeeded docking).

    Sample 1 has generation_validity_status="invalid" but
    docking_run_status="succeeded" which is a lifecycle violation.
    The entire report must be rejected; no partial output.
    """
    results = [
        # sample 0: valid success
        _valid_full(0, family="CYS_MICHAEL_ADDITION", covalent_docking=-8.5, noncovalent=-7.2),
        # sample 1: CORRUPT - invalid gen but succeeded docking
        _result_row(
            1,
            "invalid",
            "exported",
            "eligible",
            "succeeded",
            family="CYS_MICHAEL_ADDITION",
            primary_failure="NO_COVALENT_EDGE_PREDICTED",
            ligand_atom=dict(_LIGAND_ATOM),
            covalent_edge=dict(_COVALENT_EDGE),
            edge_score=0.85,
            geometry=dict(_GEOMETRY),
            mol_quality=dict(_MOL_QUALITY),
            matched_warhead="acrylamide",
            predicted_warhead="acrylamide",
            covalent_docking=-8.5,
            noncovalent=-7.2,
            edge_checks=[dict(_EDGE_CHECK)],
            artifacts=dict(_ARTIFACTS_FULL),
        ),
        # sample 2: valid success
        _valid_full(2, family="SER_MICHAEL_ADDITION", covalent_docking=-7.5, noncovalent=-7.3),
    ]

    _build_scenario(
        ROOT / "corrupt_lifecycle_mixed",
        results=results,
        failures=[],
        accepted=3,
        attempted=3,
        failure_count=0,
    )


def build_all_success_single_family() -> None:
    """Single-family all-success scenario for deterministic ordering tests."""
    results = [
        _valid_full(0, family="CYS_MICHAEL_ADDITION", covalent_docking=-8.5),
        _valid_full(1, family="CYS_MICHAEL_ADDITION", covalent_docking=-9.1),
        _valid_full(2, family="CYS_MICHAEL_ADDITION", covalent_docking=-7.5),
    ]

    _build_scenario(
        ROOT / "all_success_single_family",
        results=results,
        failures=[],
        accepted=3,
        attempted=3,
        failure_count=0,
    )


# ===================================================================
# main
# ===================================================================


ALL_BUILDERS = [
    build_valid_mixed_families,
    build_corrupt_lifecycle_mixed,
    build_all_success_single_family,
]


def build_all() -> None:
    for builder in ALL_BUILDERS:
        builder()
        print(f"  built: {builder.__name__}")


if __name__ == "__main__":
    build_all()
    print(f"\n{len(ALL_BUILDERS)} fixtures built under {ROOT}")
