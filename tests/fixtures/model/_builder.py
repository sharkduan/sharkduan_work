"""Build records.jsonl fixtures with correct checksums for model batch tests.

Usage from tests::

    from tests.fixtures.model._builder import ModelBatchFixtureBuilder

    builder = ModelBatchFixtureBuilder()
    valid_path = builder.write_valid()
    missing_path = builder.write_missing_artifact()
    ...
"""

from __future__ import annotations

import hashlib
import json
import os

_FIXTURE_DIR = os.path.dirname(os.path.abspath(__file__))

#  artifact file paths relative to _FIXTURE_DIR

_VALID_A = "valid/artifacts/m01a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6"
_VALID_B = "valid/artifacts/m02a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6"
_MISSING_ARTIFACT_DIR = "missing_artifact/artifacts/m03deadbeefdeadbeefdeadbeefdead"
_UNREADABLE_DIR = "unreadable_artifact/artifacts/m04a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6"

REQUIRED_ROLES = (
    "coordinates",
    "protein_atom_table",
    "ligand_atom_table",
    "ligand_bond_table",
    "edge_candidates",
)


def _sha256_file(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _artifact_ref(role: str, uri: str, fmt: str) -> dict:
    full = os.path.join(_FIXTURE_DIR, uri)
    return {
        "bytes": os.path.getsize(full),
        "format": fmt,
        "role": role,
        "schema_version": "1",
        "sha256": _sha256_file(full),
        "uri": uri,
    }


def _artifacts_for(artifact_dir: str) -> list[dict]:
    """Build ArtifactRef dicts for all 5 required roles under *artifact_dir*."""
    formats = {
        "coordinates": "pdb",
        "protein_atom_table": "json",
        "ligand_atom_table": "json",
        "ligand_bond_table": "json",
        "edge_candidates": "json",
    }
    filenames = {
        "coordinates": "coordinates.pdb",
        "protein_atom_table": "protein_atom_table.json",
        "ligand_atom_table": "ligand_atom_table.json",
        "ligand_bond_table": "ligand_bond_table.json",
        "edge_candidates": "edge_candidates.json",
    }
    refs = []
    for role in REQUIRED_ROLES:
        uri = f"{artifact_dir}/{filenames[role]}"
        full = os.path.join(_FIXTURE_DIR, uri)
        if not os.path.isfile(full):
            continue  # caller handles missing
        refs.append(_artifact_ref(role, uri, formats[role]))
    return refs


def _core_labels(record_id: str, family: str, target_idx: int, target_name: str,
                 ligand_idx: int, ligand_name: str, ligand_el: str = "C",
                 bond_type: str = "", warhead_type: str = "", pdb_id: str = "1abc") -> dict:
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


def _lineage_entry(source_db: str, source_id: str, version: str, row: int,
                   path: str = "/fixture/model.json") -> dict:
    return {
        "raw_file_path": path,
        "raw_file_sha256": f"fixture-lineage-{source_id}",
        "raw_manifest_file": "model-fixture-manifest.json",
        "row_index": row,
        "source_database": source_db,
        "source_record_id": source_id,
        "source_version": version,
    }


class ModelBatchFixtureBuilder:
    """Generates records.jsonl files with correct SHA-256 checksums."""

    def __init__(self) -> None:
        self._paths: dict[str, str] = {}

    def _write_jsonl(self, key: str, records: list[dict]) -> str:
        path = os.path.join(_FIXTURE_DIR, f"{key}.jsonl")
        with open(path, "w", encoding="utf-8") as fh:
            for rec in records:
                json.dump(rec, fh, sort_keys=True)
                fh.write("\n")
        self._paths[key] = path
        return path

    def path_for(self, key: str) -> str:
        return self._paths[key]

    #  valid (2 records)

    def write_valid(self) -> str:
        rec_a = {
            "schema_version": "1",
            "contract_version": "1.0.0",
            "record_id": "m01a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6",
            "artifacts": _artifacts_for(_VALID_A),
            "core_labels": _core_labels(
                "m01a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6",
                "CYS_MICHAEL_ADDITION", 6, "SG", 1, "C1",
                bond_type="carbon-sulfur", warhead_type="acrylamide",
            ),
            "lineage": [
                _lineage_entry("covbinder_in_pdb", "model-valid-a", "2026-05-21", 0),
            ],
            "metadata": {
                "quality": {
                    "first_core_eligible": True,
                    "quality_flags": [],
                    "quality_reasons": [],
                    "quality_tier": "Q0",
                },
                "chemical_state": {
                    "status": "explicit",
                    "protonation": "SG_minus1",
                },
            },
        }
        rec_b = {
            "schema_version": "1",
            "contract_version": "1.0.0",
            "record_id": "m02a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6",
            "artifacts": _artifacts_for(_VALID_B),
            "core_labels": _core_labels(
                "m02a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6",
                "CYS_MICHAEL_ADDITION", 12, "SG", 1, "C4",
                bond_type="carbon-sulfur", warhead_type="vinyl_sulfonamide",
                pdb_id="2xyz",
            ),
            "lineage": [
                _lineage_entry("covpdb", "model-valid-b", "2026-03-15", 1),
            ],
            "metadata": {
                "quality": {
                    "first_core_eligible": True,
                    "quality_flags": [],
                    "quality_reasons": [],
                    "quality_tier": "Q1",
                },
                "chemical_state": {
                    "status": "inferred",
                    "protonation": "SG_minus1",
                    "tool": "propka",
                    "version": "3.4",
                    "confidence": "medium",
                },
            },
        }
        return self._write_jsonl("valid", [rec_a, rec_b])

    #  missing artifact

    def write_missing_artifact(self) -> str:
        """records.jsonl references a coordinates.pdb that does not exist."""
        roles_present = [
            "protein_atom_table", "ligand_atom_table", "ligand_bond_table", "edge_candidates"
        ]
        artifacts = []
        for role in roles_present:
            uri = f"{_MISSING_ARTIFACT_DIR}/{_filenames()[role]}"
            fmt = _formats()[role]
            artifacts.append(_artifact_ref(role, uri, fmt))
        # Add a reference to a coordinates file that does NOT exist
        fake_coords_uri = f"{_MISSING_ARTIFACT_DIR}/coordinates.pdb"
        artifacts.append({
            "bytes": 500,
            "format": "pdb",
            "role": "coordinates",
            "schema_version": "1",
            "sha256": "0" * 64,
            "uri": fake_coords_uri,
        })
        rec = {
            "schema_version": "1",
            "contract_version": "1.0.0",
            "record_id": "m03deadbeefdeadbeefdeadbeefdead",
            "artifacts": artifacts,
            "core_labels": _core_labels(
                "m03deadbeefdeadbeefdeadbeefdead",
                "CYS_MICHAEL_ADDITION", 6, "SG", 1, "C1",
            ),
            "lineage": [
                _lineage_entry("covbinder_in_pdb", "model-missing", "2026-05-21", 0),
            ],
            "metadata": {
                "quality": {
                    "first_core_eligible": True,
                    "quality_flags": [],
                    "quality_reasons": [],
                    "quality_tier": "Q0",
                },
                "chemical_state": {"status": "explicit", "protonation": "SG_minus1"},
            },
        }
        return self._write_jsonl("missing_artifact", [rec])

    #  unreadable artifact

    def write_unreadable_artifact(self) -> str:
        """coordinates.pdb exists but is not valid JSON/PDB."""
        rec = {
            "schema_version": "1",
            "contract_version": "1.0.0",
            "record_id": "m04a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6",
            "artifacts": _artifacts_for(_UNREADABLE_DIR),
            "core_labels": _core_labels(
                "m04a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6",
                "CYS_MICHAEL_ADDITION", 6, "SG", 1, "C1",
            ),
            "lineage": [
                _lineage_entry("covbinder_in_pdb", "model-unreadable", "2026-05-21", 0),
            ],
            "metadata": {
                "quality": {
                    "first_core_eligible": True,
                    "quality_flags": [],
                    "quality_reasons": [],
                    "quality_tier": "Q0",
                },
                "chemical_state": {"status": "explicit", "protonation": "SG_minus1"},
            },
        }
        return self._write_jsonl("unreadable_artifact", [rec])

    #  checksum mismatch

    def write_checksum_mismatch(self) -> str:
        """All artifact files exist but one sha256 is wrong."""
        artifacts = _artifacts_for(_VALID_A)
        # Corrupt the coordinates sha256
        for a in artifacts:
            if a["role"] == "coordinates":
                a["sha256"] = "b" * 64
                break
        rec = {
            "schema_version": "1",
            "contract_version": "1.0.0",
            "record_id": "m05a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6",
            "artifacts": artifacts,
            "core_labels": _core_labels(
                "m05a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6",
                "CYS_MICHAEL_ADDITION", 6, "SG", 1, "C1",
            ),
            "lineage": [
                _lineage_entry("covbinder_in_pdb", "model-checksum", "2026-05-21", 0),
            ],
            "metadata": {
                "quality": {
                    "first_core_eligible": True,
                    "quality_flags": [],
                    "quality_reasons": [],
                    "quality_tier": "Q0",
                },
                "chemical_state": {"status": "explicit", "protonation": "SG_minus1"},
            },
        }
        return self._write_jsonl("checksum_mismatch", [rec])

    #  missing artifact role

    def write_missing_artifact_role(self) -> str:
        """Record lacks a 'coordinates' role in its artifacts array."""
        # Only include 4 of 5 roles  omit coordinates
        roles = [
            "protein_atom_table", "ligand_atom_table",
            "ligand_bond_table", "edge_candidates",
        ]
        artifacts = []
        for role in roles:
            uri = f"{_VALID_A}/{_filenames()[role]}"
            artifacts.append(_artifact_ref(role, uri, _formats()[role]))
        rec = {
            "schema_version": "1",
            "contract_version": "1.0.0",
            "record_id": "m06a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6",
            "artifacts": artifacts,
            "core_labels": _core_labels(
                "m06a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6",
                "CYS_MICHAEL_ADDITION", 6, "SG", 1, "C1",
            ),
            "lineage": [
                _lineage_entry("covbinder_in_pdb", "model-no-role", "2026-05-21", 0),
            ],
            "metadata": {
                "quality": {
                    "first_core_eligible": True,
                    "quality_flags": [],
                    "quality_reasons": [],
                    "quality_tier": "Q0",
                },
                "chemical_state": {"status": "explicit", "protonation": "SG_minus1"},
            },
        }
        return self._write_jsonl("missing_artifact_role", [rec])

    #  unsupported contract version

    def write_unsupported_contract_version(self) -> str:
        """Record has contract_version '99.0.0' instead of '1.0.0'."""
        rec = {
            "schema_version": "1",
            "contract_version": "99.0.0",
            "record_id": "m07a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6",
            "artifacts": _artifacts_for(_VALID_A),
            "core_labels": _core_labels(
                "m07a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6",
                "CYS_MICHAEL_ADDITION", 6, "SG", 1, "C1",
            ),
            "lineage": [
                _lineage_entry("covbinder_in_pdb", "model-version", "2026-05-21", 0),
            ],
            "metadata": {
                "quality": {
                    "first_core_eligible": True,
                    "quality_flags": [],
                    "quality_reasons": [],
                    "quality_tier": "Q0",
                },
                "chemical_state": {"status": "explicit", "protonation": "SG_minus1"},
            },
        }
        return self._write_jsonl("unsupported_contract_version", [rec])

    def write_unsupported_schema_version(self) -> str:
        """Record has schema_version '99' instead of the Task 17 supported schema."""
        rec = {
            "schema_version": "99",
            "contract_version": "1.0.0",
            "record_id": "m12a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6",
            "artifacts": _artifacts_for(_VALID_A),
            "core_labels": _core_labels(
                "m12a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6",
                "CYS_MICHAEL_ADDITION", 6, "SG", 1, "C1",
            ),
            "lineage": [
                _lineage_entry("covbinder_in_pdb", "model-schema", "2026-05-21", 0),
            ],
            "metadata": {
                "quality": {
                    "first_core_eligible": True,
                    "quality_flags": [],
                    "quality_reasons": [],
                    "quality_tier": "Q0",
                },
                "chemical_state": {"status": "explicit", "protonation": "SG_minus1"},
            },
        }
        return self._write_jsonl("unsupported_schema_version", [rec])

    #  required chemical state unavailable

    def write_required_state_unavailable(self) -> str:
        """Record has chemical_state.status == 'unavailable'."""
        rec = {
            "schema_version": "1",
            "contract_version": "1.0.0",
            "record_id": "m08a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6",
            "artifacts": _artifacts_for(_VALID_A),
            "core_labels": _core_labels(
                "m08a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6",
                "CYS_MICHAEL_ADDITION", 6, "SG", 1, "C1",
            ),
            "lineage": [
                _lineage_entry("covbinder_in_pdb", "model-state", "2026-05-21", 0),
            ],
            "metadata": {
                "quality": {
                    "first_core_eligible": True,
                    "quality_flags": [],
                    "quality_reasons": [],
                    "quality_tier": "Q0",
                },
                "chemical_state": {"status": "unavailable"},
            },
        }
        return self._write_jsonl("required_state_unavailable", [rec])

    def write_missing_chemical_state(self) -> str:
        """Record lacks metadata.chemical_state and must fail conservatively."""
        rec = {
            "schema_version": "1",
            "contract_version": "1.0.0",
            "record_id": "m11a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6",
            "artifacts": _artifacts_for(_VALID_A),
            "core_labels": _core_labels(
                "m11a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6",
                "CYS_MICHAEL_ADDITION", 6, "SG", 1, "C1",
            ),
            "lineage": [
                _lineage_entry("covbinder_in_pdb", "model-missing-state", "2026-05-21", 0),
            ],
            "metadata": {
                "quality": {
                    "first_core_eligible": True,
                    "quality_flags": [],
                    "quality_reasons": [],
                    "quality_tier": "Q0",
                },
            },
        }
        return self._write_jsonl("missing_chemical_state", [rec])

    #  mixed quality / split (tests 16-17: no filtering)

    def write_mixed_quality_split(self) -> str:
        """Records with Q2, visual=fail, split=test  must still be accepted."""
        rec_q2 = {
            "schema_version": "1",
            "contract_version": "1.0.0",
            "record_id": "m09a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6",
            "artifacts": _artifacts_for(_VALID_A),
            "core_labels": _core_labels(
                "m09a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6",
                "CYS_MICHAEL_ADDITION", 6, "SG", 1, "C1",
                pdb_id="3q2x",
            ),
            "lineage": [
                _lineage_entry("covbinder_in_pdb", "model-q2", "2026-05-21", 0),
            ],
            "metadata": {
                "quality": {
                    "first_core_eligible": False,
                    "quality_flags": ["non_human_protein"],
                    "quality_reasons": [],
                    "quality_tier": "Q2",
                },
                "chemical_state": {"status": "explicit", "protonation": "SG_minus1"},
            },
        }
        rec_visual_fail = {
            "schema_version": "1",
            "contract_version": "1.0.0",
            "record_id": "m10a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6",
            "artifacts": _artifacts_for(_VALID_B),
            "core_labels": _core_labels(
                "m10a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6",
                "CYS_MICHAEL_ADDITION", 12, "SG", 1, "C4",
                pdb_id="4vfx",
            ),
            "lineage": [
                _lineage_entry("covpdb", "model-visual-fail", "2026-03-15", 1),
            ],
            "metadata": {
                "quality": {
                    "first_core_eligible": True,
                    "quality_flags": [],
                    "quality_reasons": [],
                    "quality_tier": "Q1",
                },
                "chemical_state": {"status": "explicit", "protonation": "SG_minus1"},
            },
        }
        return self._write_jsonl("mixed_quality_split", [rec_q2, rec_visual_fail])


def _filenames() -> dict[str, str]:
    return {
        "coordinates": "coordinates.pdb",
        "protein_atom_table": "protein_atom_table.json",
        "ligand_atom_table": "ligand_atom_table.json",
        "ligand_bond_table": "ligand_bond_table.json",
        "edge_candidates": "edge_candidates.json",
    }


def _formats() -> dict[str, str]:
    return {
        "coordinates": "pdb",
        "protein_atom_table": "json",
        "ligand_atom_table": "json",
        "ligand_bond_table": "json",
        "edge_candidates": "json",
    }
