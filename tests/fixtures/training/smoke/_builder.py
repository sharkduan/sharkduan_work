"""Smoke fixture builder for Task 24 train and forward smoke tests.

Builds complete records.jsonl with valid artifact refs that work through the
Task 17-23 tracer-bullet path.  Reuses static model-batch artifact files.

Usage from tests::

    from tests.fixtures.training.smoke._builder import SmokeFixtureBuilder

    builder = SmokeFixtureBuilder()
    records_path, split_path = builder.write_train_smoke_bundle()
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any

_FIXTURE_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
_REPO_ROOT = _FIXTURE_DIR.parents[3]
_MODEL_VALID = _REPO_ROOT / "tests" / "fixtures" / "model" / "valid"
_MODEL_ARTIFACT_A = _MODEL_VALID / "artifacts" / "m01a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6"
_MODEL_ARTIFACT_B = _MODEL_VALID / "artifacts" / "m02a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6"

SMOKE_RECORD_IDS = {
    "s_cys_q0": "S01a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6",
    "s_cys_q1": "S02a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6",
    "s_lys_q0": "S03a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6",
    "s_ser_q1": "S04a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6",
}

REQUIRED_ROLES = (
    "coordinates",
    "protein_atom_table",
    "ligand_atom_table",
    "ligand_bond_table",
    "edge_candidates",
)


def _sha256_file(path: Path) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _artifact_ref_via(source_dir: Path, role: str, fmt: str) -> dict[str, Any]:
    filenames: dict[str, str] = {
        "coordinates": "coordinates.pdb",
        "protein_atom_table": "protein_atom_table.json",
        "ligand_atom_table": "ligand_atom_table.json",
        "ligand_bond_table": "ligand_bond_table.json",
        "edge_candidates": "edge_candidates.json",
    }
    filename = filenames[role]
    source_path = source_dir / filename
    destination_dir = _FIXTURE_DIR / "artifacts" / source_dir.name
    destination_dir.mkdir(parents=True, exist_ok=True)
    path = destination_dir / filename
    if role == "edge_candidates":
        edge_data = json.loads(source_path.read_text("utf-8"))
        protein_data = json.loads(
            (source_dir / "protein_atom_table.json").read_text("utf-8")
        )
        atoms = protein_data["atoms"]
        target_index, target = next(
            (index, atom)
            for index, atom in enumerate(atoms)
            if atom.get("name") == "SG"
        )
        edge_data["positive_edge"].update(
            {
                "ligand_atom_index": 1,
                "bond_type": "carbon-sulfur",
                "target_atom": {
                    "atom_index": target_index,
                    "atom_name": target["name"],
                    "atom_serial": target.get("serial"),
                    "chain_id": protein_data.get("chain_id"),
                    "residue_number": protein_data.get("residue_number"),
                    "residue_name": protein_data.get("residue_name", "CYS"),
                },
            }
        )
        path.write_text(json.dumps(edge_data, sort_keys=True), "utf-8")
    else:
        shutil.copy2(source_path, path)
    return {
        "bytes": int(os.path.getsize(str(path))),
        "format": fmt,
        "role": role,
        "schema_version": "1",
        "sha256": _sha256_file(path),
        "uri": str(path.relative_to(_FIXTURE_DIR)).replace("\\", "/"),
    }


def _core_labels(
    record_id: str,
    family: str,
    target_idx: int,
    target_name: str,
    ligand_idx: int,
    ligand_name: str,
    ligand_el: str = "C",
    bond_type: str = "carbon-sulfur",
    warhead_type: str = "acrylamide",
    pdb_id: str = "1abc",
) -> dict[str, Any]:
    return {
        "bond_type": bond_type,
        "ligand_atom_element": ligand_el,
        "ligand_atom_index": ligand_idx,
        "ligand_atom_name": ligand_name,
        "pdb_id": pdb_id,
        "residue_reaction_family": family,
        "target_atom_index": target_idx,
        "target_atom_name": target_name,
        "warhead_type": warhead_type,
    }


def _lineage_entry(
    source_db: str, source_id: str, version: str, row: int
) -> dict[str, Any]:
    return {
        "raw_file_path": f"/fixture/smoke/{source_id}.json",
        "raw_file_sha256": f"fixture-lineage-{source_id}",
        "raw_manifest_file": "smoke-fixture-manifest.json",
        "row_index": row,
        "source_database": source_db,
        "source_record_id": source_id,
        "source_version": version,
    }


def _record(
    record_id: str,
    family: str,
    quality_tier: str,
    visual_check_status: str,
    chemical_state_status: str,
    artifact_source: Path,
    *,
    bond_type: str = "carbon-sulfur",
    warhead_type: str = "acrylamide",
    ligand_el: str = "C",
    pdb_id: str = "1abc",
    row_index: int = 0,
    linkage_count: int = 1,
) -> dict[str, Any]:
    formats: dict[str, str] = {
        "coordinates": "pdb",
        "protein_atom_table": "json",
        "ligand_atom_table": "json",
        "ligand_bond_table": "json",
        "edge_candidates": "json",
    }
    target_atom_indices = {
        "S01a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6": 6,
        "S02a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6": 12,
        "S03a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6": 10,
        "S04a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6": 8,
    }
    target_idx = target_atom_indices.get(record_id, 6)

    artifacts = [
        _artifact_ref_via(artifact_source, role, formats[role])
        for role in REQUIRED_ROLES
    ]

    return {
        "schema_version": "1",
        "contract_version": "1.0.0",
        "record_id": record_id,
        "artifacts": artifacts,
        "core_labels": _core_labels(
            record_id,
            family,
            target_idx,
            "SG",
            1,
            "C1",
            ligand_el=ligand_el,
            bond_type=bond_type,
            warhead_type=warhead_type,
            pdb_id=pdb_id,
        ),
        "lineage": [
            _lineage_entry("covbinder_in_pdb", f"smoke-{record_id[:6]}", "2026-06-01", row_index),
        ],
        "metadata": {
            "quality": {
                "quality_tier": quality_tier,
                "first_core_eligible": quality_tier in ("Q0", "Q1"),
                "quality_flags": [],
                "quality_reasons": [],
            },
            "chemical_state": {"status": chemical_state_status}
            | (
                {"protonation": "SG_minus1"}
                if chemical_state_status in ("explicit", "inferred")
                else {}
            ),
            "visual_check_status": visual_check_status,
            "linkage_count": linkage_count,
        },
    }


class SmokeFixtureBuilder:
    """Builds complete train-smoke fixture bundles.

    Produces valid ``records.jsonl`` and ``split_index.json`` files that
    pass through the Task 17-23 tracer-bullet path: make_model_batch,
    build_stepwise_candidates, forward_pmdm, forward_covalent, mask audit,
    and denominator projection.
    """

    def __init__(self) -> None:
        self._paths: dict[str, str] = {}

    def _write_jsonl(self, records: list[dict], stem: str) -> str:
        path_obj = _FIXTURE_DIR / f"{stem}.jsonl"
        with open(path_obj, "w", encoding="utf-8") as fh:
            for rec in records:
                json.dump(rec, fh, sort_keys=True)
                fh.write("\n")
        path_str = str(path_obj)
        self._paths[stem] = path_str
        return path_str

    def _write_json(self, data: dict, stem: str) -> str:
        path_obj = _FIXTURE_DIR / f"{stem}.json"
        with open(path_obj, "w", encoding="utf-8") as f:
            json.dump(data, f, sort_keys=True, indent=2)
        path_str = str(path_obj)
        self._paths[stem] = path_str
        return path_str

    def path_for(self, key: str) -> str:
        return self._paths[key]

    # --- four-record smoke bundle ----------------------------------------

    def write_smoke_train_bundle(self) -> tuple[str, str]:
        """Write records.jsonl + split_index.json and return (rec_path, split_path).

        Four records across two families:

        - S01: CYS_MICHAEL_ADDITION, Q0, explicit, visual=pass
        - S02: CYS_MICHAEL_ADDITION, Q1, inferred, visual=pass
        - S03: LYS_IMINE_FORMATION, Q0, explicit, visual=pass
        - S04: SER_ESTER_FORMATION, Q1, explicit, visual=pass

        All assigned split='train'.
        """
        rid_cys_q0 = SMOKE_RECORD_IDS["s_cys_q0"]
        rid_cys_q1 = SMOKE_RECORD_IDS["s_cys_q1"]
        rid_lys_q0 = SMOKE_RECORD_IDS["s_lys_q0"]
        rid_ser_q1 = SMOKE_RECORD_IDS["s_ser_q1"]

        records = [
            _record(
                rid_cys_q0, "CYS_MICHAEL_ADDITION", "Q0", "pass", "explicit",
                _MODEL_ARTIFACT_A, row_index=0,
            ),
            _record(
                rid_cys_q1, "CYS_MICHAEL_ADDITION", "Q1", "pass", "inferred",
                _MODEL_ARTIFACT_B, row_index=1, pdb_id="2xyz",
            ),
            _record(
                rid_lys_q0, "LYS_IMINE_FORMATION", "Q0", "pass", "explicit",
                _MODEL_ARTIFACT_A, row_index=2,
            ),
            _record(
                rid_ser_q1, "SER_ESTER_FORMATION", "Q1", "pass", "explicit",
                _MODEL_ARTIFACT_B, row_index=3, pdb_id="4ser",
            ),
        ]
        rec_path = self._write_jsonl(records, "smoke_records")

        assignments = [
            {"record_id": rid, "split": "train",
             "scaffold_key": None, "protein_cluster_id": None,
             "residue_reaction_family": fam, "fallback_reason": None,
             "manual_review_status": None}
            for rid, fam in [
                (rid_cys_q0, "CYS_MICHAEL_ADDITION"),
                (rid_cys_q1, "CYS_MICHAEL_ADDITION"),
                (rid_lys_q0, "LYS_IMINE_FORMATION"),
                (rid_ser_q1, "SER_ESTER_FORMATION"),
            ]
        ]
        split = {
            "schema_version": "1",
            "contract_version": "1.0.0",
            "role": "split_index",
            "split_policy": {
                "algorithm": "leakage_aware_covalent_splits",
                "algorithm_version": "1.0.0",
                "random_seed": 42,
                "split_ratios": {"train": 0.80, "val": 0.10, "test": 0.10},
            },
            "assignment_count": 4,
            "assignments": assignments,
        }
        split_path = self._write_json(split, "smoke_split_index")
        return rec_path, split_path

    # --- Q2-exclusion smoke record ---------------------------------------

    def write_q2_exclusion_bundle(self) -> tuple[str, str]:
        """Single Q2 record with explicit state for Q2-exclusion audit."""
        rid = SMOKE_RECORD_IDS["s_cys_q0"]
        rec = _record(
            rid, "CYS_MICHAEL_ADDITION", "Q2", "pass", "explicit",
            _MODEL_ARTIFACT_A, row_index=0,
        )
        rec_path = self._write_jsonl([rec], "smoke_q2_records")
        assignments = [{
            "record_id": rid, "split": "train",
            "scaffold_key": None, "protein_cluster_id": None,
            "residue_reaction_family": "CYS_MICHAEL_ADDITION",
            "fallback_reason": None, "manual_review_status": None,
        }]
        split = {
            "schema_version": "1", "contract_version": "1.0.0",
            "role": "split_index",
            "split_policy": {
                "algorithm": "leakage_aware_covalent_splits",
                "algorithm_version": "1.0.0",
                "random_seed": 42,
                "split_ratios": {"train": 0.80, "val": 0.10, "test": 0.10},
            },
            "assignment_count": 1, "assignments": assignments,
        }
        split_path = self._write_json(split, "smoke_q2_split_index")
        return rec_path, split_path
