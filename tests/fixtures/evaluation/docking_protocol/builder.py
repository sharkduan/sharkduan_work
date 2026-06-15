"""Build committed Task 32 docking_protocol fixtures.

Run from repo root:
    python tests\\fixtures\\evaluation\\docking_protocol\\builder.py

Generates:
    valid_manifest/
        docking_protocol_manifest.yml
        configs/docking_config.txt
        input/receptor.pdb
        output/receptor.pdbqt
        input/ligand.sdf
        logs/docking_failure.log
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
TARGET = ROOT / "tests" / "fixtures" / "evaluation" / "docking_protocol" / "valid_manifest"

_YAML_QUOTE = json.dumps


def build() -> None:
    TARGET.mkdir(parents=True, exist_ok=True)

    # --- artifact files ---
    artifacts: dict[str, tuple[Path, bytes]] = {}

    full_config = b"# docking config\nengine=vina_covalent\n"
    artifacts["full_config"] = (TARGET / "configs" / "docking_config.txt", full_config)

    receptor_input = (
        b"ATOM      1  N   MET A   1      23.456  12.345   8.901  1.00  0.00           N\n"
        b"ATOM      2  CA  MET A   1      24.123  13.567   9.234  1.00  0.00           C\n"
        b"ATOM      3  C   MET A   1      25.456  13.678   8.567  1.00  0.00           C\n"
        b"ATOM      4  O   MET A   1      25.890  12.901   7.789  1.00  0.00           O\n"
        b"ATOM      5  CB  MET A   1      23.345  14.789   8.901  1.00  0.00           C\n"
        b"ATOM      6  CG  MET A   1      23.123  15.012  10.234  1.00  0.00           C\n"
        b"ATOM      7  SD  MET A   1      22.456  13.567  10.901  1.00  0.00           S\n"
        b"ATOM      8  CE  MET A   1      21.234  13.123   9.789  1.00  0.00           C\n"
        b"ATOM      9  N   CYS A 145      26.123  14.789   8.901  1.00  0.00           N\n"
        b"ATOM     10  CA  CYS A 145      27.456  14.901   8.234  1.00  0.00           C\n"
        b"ATOM     11  C   CYS A 145      28.123  13.678   8.567  1.00  0.00           C\n"
        b"ATOM     12  O   CYS A 145      27.890  12.901   9.456  1.00  0.00           O\n"
        b"ATOM     13  CB  CYS A 145      27.345  15.234   6.789  1.00  0.00           C\n"
        b"ATOM     14  SG  CYS A 145      28.901  15.567   5.901  1.00  0.00           S\n"
    )
    artifacts["receptor_input"] = (TARGET / "input" / "receptor.pdb", receptor_input)

    receptor_output = (
        b"REMARK   4 receptor.pdbqt - pdb2pqr 3.0.0 output\n"
        b"REMARK   5 MODEL 1\n"
        b"REMARK   6 TOTAL CHARGE: -2.0\n"
    )
    artifacts["receptor_output"] = (TARGET / "output" / "receptor.pdbqt", receptor_output)

    ligand_input = (
        b"ligand sdf content\n"
        b"  -OEChem-04282612342D\n"
        b"\n"
        b"  1  0     0  0  0  0  0  0999 V2000\n"
        b"    0.0000    0.0000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0\n"
        b"M  END\n"
    )
    artifacts["ligand_input"] = (TARGET / "input" / "ligand.sdf", ligand_input)

    failure_log = b""
    artifacts["failure_log"] = (TARGET / "logs" / "docking_failure.log", failure_log)

    # Write all artifact files
    shas: dict[str, str] = {}
    for key, (path, content) in artifacts.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        shas[key] = hashlib.sha256(content).hexdigest()

    # --- manifest YAML ---
    lines: list[str] = []
    _a = lines.append

    _a(f"docking_protocol_id: {_YAML_QUOTE('prot-valid-001')}")
    _a(f"engine_name: {_YAML_QUOTE('vina_covalent')}")
    _a(f"engine_version: {_YAML_QUOTE('1.2.3')}")
    _a(f"engine_build_hash: {_YAML_QUOTE('b' * 64)}")
    _a(f"full_config_uri: {_YAML_QUOTE('configs/docking_config.txt')}")
    _a(f"full_config_sha256: {_YAML_QUOTE(shas['full_config'])}")
    _a("random_seed: 42")

    _a("receptor_preparation:")
    _a(f"  tool_name: {_YAML_QUOTE('pdb2pqr')}")
    _a(f"  tool_version: {_YAML_QUOTE('3.0.0')}")
    _a(f"  input_structure_uri: {_YAML_QUOTE('input/receptor.pdb')}")
    _a(f"  input_structure_sha256: {_YAML_QUOTE(shas['receptor_input'])}")
    _a(f"  output_receptor_uri: {_YAML_QUOTE('output/receptor.pdbqt')}")
    _a(f"  output_receptor_sha256: {_YAML_QUOTE(shas['receptor_output'])}")
    _a(f"  pH_or_protonation_policy: {_YAML_QUOTE('pH 7.4')}")
    _a("  water_policy: remove")
    _a("  cofactor_policy: keep")
    _a("  metal_policy: keep")

    _a("ligand_preparation:")
    _a(f"  tool_name: {_YAML_QUOTE('obabel')}")
    _a(f"  tool_version: {_YAML_QUOTE('3.0.0')}")
    _a(f"  input_ligand_uri: {_YAML_QUOTE('input/ligand.sdf')}")
    _a(f"  input_ligand_sha256: {_YAML_QUOTE(shas['ligand_input'])}")
    _a(f"  charge_model: {_YAML_QUOTE('gasteiger')}")
    _a(f"  protonation_policy: {_YAML_QUOTE('pH 7.4')}")

    _a("covalent_constraint:")
    _a("  representation: distance_constraint")
    _a(f"  target_atom_identity: {_YAML_QUOTE('A:145:CYS:SG')}")
    _a(f"  ligand_atom_identity: {_YAML_QUOTE('C1')}")
    _a("  constraint_parameters: {}")

    _a("search_region:")
    _a("  center: [10.0, 20.0, 30.0]")
    _a("  size: [15.0, 15.0, 15.0]")
    _a("  unit: angstrom")

    _a("pose_selection:")
    _a("  ranking_rule: best_score")
    _a(f"  score_unit: {_YAML_QUOTE('kcal/mol')}")

    _a(f"failure_log_uri: {_YAML_QUOTE('logs/docking_failure.log')}")
    _a(f"failure_log_sha256: {_YAML_QUOTE(shas['failure_log'])}")

    manifest_path = TARGET / "docking_protocol_manifest.yml"
    manifest_path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    print("Built docking_protocol/valid_manifest fixture:")
    for key, (path, _) in artifacts.items():
        print(f"  {path.relative_to(TARGET)}  sha256={shas[key][:16]}...")
    print(f"  docking_protocol_manifest.yml")


if __name__ == "__main__":
    build()
