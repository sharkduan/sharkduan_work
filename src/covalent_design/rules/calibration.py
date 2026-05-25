"""Build a reviewable calibration sheet CSV from records and rule tables."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Optional

from covalent_design.contracts.types import (
    CONTRACT_VERSION,
    ArtifactRef,
    ContractEnvelope,
    ValidationReceipt,
)
from covalent_design.io.artifacts import artifact_ref_from_file, sha256_file
from covalent_design.io.jsonl import read_jsonl
from covalent_design.rules.validate import load_rule_table


VALIDATOR_NAME = "covalent_design.rules.calibration"

REQUIRED_CSV_COLUMNS = [
    "family_id",
    "sample_count",
    "representative_record_ids",
    "target_atom_distribution",
    "ligand_attachment_element_distribution",
    "warhead_distribution",
    "bond_length_summary",
    "protein_side_angle_summary",
    "ligand_side_angle_summary",
    "outlier_record_ids",
    "manual_decision",
    "notes",
    "pending_smarts_marker",
    "pending_geometry_marker",
]


def build_calibration_sheet(
    records_path: Path,
    rule_table_path: Path,
    out_csv: Optional[Path] = None,
    out_json: Optional[Path] = None,
) -> ContractEnvelope[dict]:
    records_path = Path(records_path)
    rule_table_path = Path(rule_table_path)

    records = read_jsonl(records_path, require_versions=False)
    rule_table = load_rule_table(rule_table_path)

    family_records: dict[str, list[dict]] = {}
    for rec in records:
        core = rec.get("core_labels", {})
        if isinstance(core, dict):
            family_id = str(core.get("residue_reaction_family", ""))
            if family_id:
                family_records.setdefault(family_id, []).append(rec)

    rows: list[dict] = []
    artifacts: list[ArtifactRef] = []

    for family in rule_table.families:
        fam_records = family_records.get(family.family_id, [])
        row = _build_family_row(family, fam_records)
        rows.append(row)

    if out_csv is not None:
        out_csv = Path(out_csv)
        out_csv.parent.mkdir(parents=True, exist_ok=True)
        _write_csv(out_csv, rows)
        csv_ref = artifact_ref_from_file(out_csv, role="calibration_sheet", format="csv")
        artifacts.append(csv_ref)

    if out_json is not None:
        out_json = Path(out_json)
        out_json.parent.mkdir(parents=True, exist_ok=True)
        summary = _build_json_summary(rows)
        out_json.write_text(
            json.dumps(summary, sort_keys=True, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        json_ref = artifact_ref_from_file(out_json, role="calibration_summary", format="json")
        artifacts.append(json_ref)

    payload = _build_json_summary(rows)
    input_sha256 = _compute_input_sha256(records_path, rule_table_path)

    receipt = ValidationReceipt(
        validator=VALIDATOR_NAME,
        contract_version=CONTRACT_VERSION,
        input_sha256=input_sha256,
        passed=True,
    )

    return ContractEnvelope(
        payload=payload,
        artifacts=tuple(artifacts),
        receipt=receipt,
    )


def _build_family_row(family, fam_records: list[dict]) -> dict:
    sample_count = len(fam_records)

    if sample_count == 0:
        return _empty_family_row(family)

    target_atoms: dict[str, int] = {}
    ligand_elements: dict[str, int] = {}
    warheads: dict[str, int] = {}
    bond_lengths: list[float] = []
    protein_angles: list[float] = []
    ligand_angles: list[float] = []
    record_ids: list[str] = []

    for rec in fam_records:
        rid = str(rec.get("record_id", ""))
        if rid:
            record_ids.append(rid)

        core = rec.get("core_labels", {})
        if isinstance(core, dict):
            target_atom = str(core.get("target_atom_name", ""))
            if target_atom:
                target_atoms[target_atom] = target_atoms.get(target_atom, 0) + 1

            ligand_elem = str(core.get("ligand_atom_element", ""))
            if ligand_elem:
                ligand_elements[ligand_elem] = ligand_elements.get(ligand_elem, 0) + 1

            warhead = str(core.get("warhead_type", ""))
            if warhead:
                warheads[warhead] = warheads.get(warhead, 0) + 1

        metadata = rec.get("metadata", {})
        if isinstance(metadata, dict):
            geometry = metadata.get("geometry", {})
            if isinstance(geometry, dict):
                bl = geometry.get("bond_length", {})
                if isinstance(bl, dict) and "value" in bl:
                    bond_lengths.append(float(bl["value"]))
                psa = geometry.get("protein_side_angle", {})
                if isinstance(psa, dict) and "value" in psa:
                    protein_angles.append(float(psa["value"]))
                lsa = geometry.get("ligand_side_angle", {})
                if isinstance(lsa, dict) and "value" in lsa:
                    ligand_angles.append(float(lsa["value"]))

    record_ids.sort()

    return {
        "family_id": family.family_id,
        "sample_count": str(sample_count),
        "representative_record_ids": json.dumps(record_ids, sort_keys=True),
        "target_atom_distribution": json.dumps(target_atoms, sort_keys=True),
        "ligand_attachment_element_distribution": json.dumps(ligand_elements, sort_keys=True),
        "warhead_distribution": json.dumps(warheads, sort_keys=True),
        "bond_length_summary": _geom_summary(bond_lengths, "A"),
        "protein_side_angle_summary": _geom_summary(protein_angles, "deg"),
        "ligand_side_angle_summary": _geom_summary(ligand_angles, "deg"),
        "outlier_record_ids": "[]",
        "manual_decision": "",
        "notes": family.notes,
        "pending_smarts_marker": _smarts_marker(family),
        "pending_geometry_marker": _geometry_marker(family),
    }


def _empty_family_row(family) -> dict:
    return {
        "family_id": family.family_id,
        "sample_count": "0",
        "representative_record_ids": "[]",
        "target_atom_distribution": "{}",
        "ligand_attachment_element_distribution": "{}",
        "warhead_distribution": "{}",
        "bond_length_summary": "None",
        "protein_side_angle_summary": "None",
        "ligand_side_angle_summary": "None",
        "outlier_record_ids": "[]",
        "manual_decision": "",
        "notes": family.notes or "No accepted samples in current dataset.",
        "pending_smarts_marker": _smarts_marker(family),
        "pending_geometry_marker": _geometry_marker(family),
    }


def _geom_summary(values: list[float], unit: str) -> str:
    if not values:
        return "None"
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    min_val = sorted_vals[0]
    max_val = sorted_vals[-1]
    mean_val = sum(sorted_vals) / n
    return f"min={min_val:.2f} max={max_val:.2f} mean={mean_val:.2f} n={n} {unit}"


def _smarts_marker(family) -> str:
    if family.warhead_rule_status == "pending":
        return "pending"
    if family.warhead_rule_status == "calibrated" and family.allowed_warhead_smarts:
        return "calibrated"
    return "pending"


def _geometry_marker(family) -> str:
    gs = family.geometry_status
    all_calibrated = (
        gs.bond_length == "calibrated"
        and gs.protein_side_angle == "calibrated"
        and gs.ligand_side_angle == "calibrated"
    )
    if all_calibrated:
        return "calibrated"
    return "pending"


def _write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=REQUIRED_CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _build_json_summary(rows: list[dict]) -> dict:
    families = []
    for row in rows:
        families.append({
            "family_id": row["family_id"],
            "sample_count": int(row["sample_count"]),
            "pending_smarts_marker": row["pending_smarts_marker"],
            "pending_geometry_marker": row["pending_geometry_marker"],
        })
    return {
        "ok": True,
        "families": families,
        "family_count": len(families),
    }


def _compute_input_sha256(records_path: Path, rule_table_path: Path) -> str:
    input_parts = json.dumps(
        {
            "records_sha256": sha256_file(records_path),
            "rules_sha256": sha256_file(rule_table_path),
        },
        sort_keys=True,
    )
    return hashlib.sha256(input_parts.encode()).hexdigest()
