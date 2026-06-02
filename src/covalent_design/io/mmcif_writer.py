"""Task 29 mmCIF complex-export writer — pure stdlib, no heavy deps."""

from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

from covalent_design.contracts.errors import ContractError
from covalent_design.contracts.types import (
    ArtifactRef,
    CovalentEdge,
    CovalentGenerationResult,
)

_ENTRY_ID_SANITIZE_RE = re.compile(r"[^A-Za-z0-9_]")


def write_covalent_complex(
    result: CovalentGenerationResult,
    protein_atom_table: ArtifactRef,
    ligand_coords: object,
    ligand_atom_types: object,
    ligand_bonds: object,
    covalent_edge: CovalentEdge,
    out_path: Path,
    *,
    artifact_root: Path,
) -> ArtifactRef:
    """Write a protein—ligand covalent complex as a deterministic mmCIF file."""

    # -- 1. type guard --
    if not isinstance(result, CovalentGenerationResult):
        raise TypeError(
            f"result must be a CovalentGenerationResult, "
            f"got {type(result).__name__}"
        )

    # -- 2. generation-valid export precondition --
    if result.generation_validity_status != "valid":
        _raise_export_error(
            "Cannot export a generation-invalid result",
            location="result.generation_validity_status",
        )
    if not isinstance(covalent_edge, CovalentEdge):
        _raise_export_error(
            "covalent_edge must be a CovalentEdge",
            location="covalent_edge",
        )
    if result.target_atom_identity != covalent_edge.protein_atom:
        _raise_export_error(
            "Covalent edge protein atom must match result target_atom_identity",
            location="covalent_edge.protein_atom",
        )
    if (
        result.predicted_covalent_edge is not None
        and result.predicted_covalent_edge != covalent_edge
    ):
        _raise_export_error(
            "Covalent edge must match result predicted_covalent_edge",
            location="covalent_edge",
        )

    # -- 3. resolve & validate artifact_root, out_path, protein table --
    artifact_root = _validate_artifact_root(artifact_root)
    out_path = _resolve_out_path(out_path, artifact_root)
    protein_atoms = _load_protein_table(protein_atom_table, artifact_root)

    # -- 4. validate ligand inputs --
    _validate_ligand_inputs(ligand_coords, ligand_atom_types, ligand_bonds)

    coords: list[list[float]] = ligand_coords  # type: ignore[assignment]
    atom_types: list[str] = ligand_atom_types  # type: ignore[assignment]
    bonds: list[list[int]] = ligand_bonds  # type: ignore[assignment]

    # -- 5. resolve edge: protein atom must exist; ligand index must exist & name must match --
    protein_idx = _find_protein_atom_index(protein_atoms, covalent_edge.protein_atom)
    if protein_idx is None:
        _raise_export_error(
            "Covalent edge protein atom not found in protein_atom_table",
            location="covalent_edge.protein_atom",
        )

    lig_atom_idx = covalent_edge.ligand_atom.atom_index
    if lig_atom_idx is None or not (0 <= lig_atom_idx < len(coords)):
        _raise_export_error(
            "Covalent edge ligand attachment atom index out of range",
            location="covalent_edge.ligand_atom.atom_index",
        )

    lig_atom_names = _assign_ligand_atom_names(atom_types)
    expected_name = lig_atom_names[lig_atom_idx]
    if covalent_edge.ligand_atom.atom_name != expected_name:
        _raise_export_error(
            f"Ligand attachment atom name mismatch: "
            f"edge says {covalent_edge.ligand_atom.atom_name!r}, "
            f"expected {expected_name!r} for atom index {lig_atom_idx}",
            location="covalent_edge.ligand_atom.atom_name",
        )

    # -- 6. generate mmCIF content --
    entry_id = _sanitize_entry_id(f"{result.request_id}_{result.sample_id}")
    mmcif_text = _build_mmcif(
        entry_id=entry_id,
        protein_atoms=protein_atoms,
        ligand_coords=coords,
        ligand_atom_types=atom_types,
        ligand_atom_names=lig_atom_names,
        ligand_bonds=bonds,
        covalent_edge=covalent_edge,
        protein_edge_idx=protein_idx,
    )

    # -- 7. write output --
    tmp_path = out_path.with_name(f".{out_path.name}.tmp")
    try:
        data = mmcif_text.encode("utf-8")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path.write_bytes(data)
        tmp_path.replace(out_path)
    except OSError as exc:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        _raise_export_error(
            f"Failed to write mmCIF output: {exc}",
            location=str(out_path),
        )

    # -- 8. return ArtifactRef --
    sha256 = hashlib.sha256(data).hexdigest()
    uri = out_path.relative_to(artifact_root).as_posix()
    return ArtifactRef(
        uri=uri,
        sha256=sha256,
        format="mmcif",
        role="complex_mmcif",
        bytes=len(data),
    )


# ===================================================================
# Private helpers
# ===================================================================


def _sanitize_entry_id(raw: str) -> str:
    return _ENTRY_ID_SANITIZE_RE.sub("_", raw)


def _raise_export_error(message: str, *, location: str | None = None) -> None:
    raise ContractError(
        code="COMPLEX_EXPORT_FAILED",
        owner="inference",
        message=message,
        location=location,
    )


# -- path validation --------------------------------------------------


def _validate_artifact_root(root: Path) -> Path:
    root = root.resolve()
    if not root.is_dir():
        _raise_export_error(
            f"artifact_root is not a directory: {root}",
            location="artifact_root",
        )
    return root


def _resolve_out_path(out_path: Path, artifact_root: Path) -> Path:
    resolved = (artifact_root / out_path).resolve() if not out_path.is_absolute() else out_path.resolve()
    try:
        resolved.relative_to(artifact_root.resolve())
    except ValueError:
        _raise_export_error(
            f"out_path escapes artifact_root: {out_path}",
            location="out_path",
        )
    if ".." in out_path.as_posix().split("/"):
        _raise_export_error(
            f"out_path contains parent traversal: {out_path}",
            location="out_path",
        )
    return resolved


def _resolve_protein_path(ref: ArtifactRef, artifact_root: Path) -> Path:
    uri_path = Path(ref.uri)
    if uri_path.is_absolute():
        _raise_export_error(
            f"Protein table URI must be relative: {ref.uri}",
            location="protein_atom_table.uri",
        )
    if ".." in uri_path.parts:
        _raise_export_error(
            f"Protein table URI must not escape artifact root: {ref.uri}",
            location="protein_atom_table.uri",
        )
    resolved = (artifact_root.resolve() / uri_path).resolve()
    try:
        resolved.relative_to(artifact_root.resolve())
    except ValueError:
        _raise_export_error(
            f"Protein table URI escapes artifact root: {ref.uri}",
            location="protein_atom_table.uri",
        )
    return resolved


# -- protein table loading --------------------------------------------


def _load_protein_table(ref: ArtifactRef, artifact_root: Path) -> list[dict[str, Any]]:
    if not isinstance(ref, ArtifactRef):
        _raise_export_error(
            "protein_atom_table must be an ArtifactRef",
            location="protein_atom_table",
        )
    if ref.role not in ("", "protein_atom_table"):
        _raise_export_error(
            f"Unexpected protein atom table role: {ref.role!r}",
            location="protein_atom_table.role",
        )
    path = _resolve_protein_path(ref, artifact_root)

    if not path.is_file():
        _raise_export_error(
            f"Protein table file not found: {ref.uri}",
            location="protein_atom_table",
        )

    if ref.bytes > 0:
        actual_bytes = path.stat().st_size
        if actual_bytes != ref.bytes:
            _raise_export_error(
                f"Protein table byte count mismatch: "
                f"expected {ref.bytes}, got {actual_bytes}",
                location="protein_atom_table.bytes",
            )

    try:
        raw = path.read_bytes()
    except OSError as exc:
        _raise_export_error(
            f"Protein table unreadable: {exc}",
            location="protein_atom_table",
        )

    actual_sha256 = hashlib.sha256(raw).hexdigest()
    if actual_sha256 != ref.sha256:
        _raise_export_error(
            f"Protein table sha256 mismatch: "
            f"expected {ref.sha256}, got {actual_sha256}",
            location="protein_atom_table.sha256",
        )

    try:
        doc = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        _raise_export_error(
            f"Protein table JSON unparseable: {exc}",
            location="protein_atom_table",
        )

    if not isinstance(doc, dict) or "atoms" not in doc:
        _raise_export_error(
            "Protein table must be a JSON object with an 'atoms' key",
            location="protein_atom_table",
        )

    atoms: list[Any] = doc["atoms"]
    if not isinstance(atoms, list):
        _raise_export_error(
            "Protein table 'atoms' must be a JSON array",
            location="protein_atom_table.atoms",
        )

    if len(atoms) == 0:
        _raise_export_error(
            "Protein table 'atoms' array must not be empty",
            location="protein_atom_table.atoms",
        )

    required_fields = ("chain_id", "residue_number", "residue_name", "atom_name", "element", "x", "y", "z")
    for i, atom in enumerate(atoms):
        if not isinstance(atom, dict):
            _raise_export_error(
                f"Protein atom {i} is not a JSON object",
                location=f"protein_atom_table.atoms[{i}]",
            )
        for field in required_fields:
            if field not in atom:
                _raise_export_error(
                    f"Protein atom {i} missing required field {field!r}",
                    location=f"protein_atom_table.atoms[{i}].{field}",
                )
        for field in ("chain_id", "residue_name", "atom_name", "element"):
            _validate_token(atom[field], f"protein_atom_table.atoms[{i}].{field}")
        if isinstance(atom["residue_number"], bool) or not isinstance(atom["residue_number"], int):
            _raise_export_error(
                f"Protein atom {i} residue_number must be an integer",
                location=f"protein_atom_table.atoms[{i}].residue_number",
            )
        for field in ("x", "y", "z"):
            value = atom[field]
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                _raise_export_error(
                    f"Protein atom {i} {field} must be numeric",
                    location=f"protein_atom_table.atoms[{i}].{field}",
                )
            if not math.isfinite(float(value)):
                _raise_export_error(
                    f"Protein atom {i} {field} must be finite",
                    location=f"protein_atom_table.atoms[{i}].{field}",
                )

    return atoms  # type: ignore[return-value]


# -- ligand input validation ------------------------------------------


def _validate_ligand_inputs(coords: object, atom_types: object, bonds: object) -> None:
    if not isinstance(coords, list):
        _raise_export_error("ligand_coords must be a list", location="ligand_coords")

    coord_rows: list[Any] = coords  # type: ignore[assignment]
    if not coord_rows:
        _raise_export_error("ligand_coords must not be empty", location="ligand_coords")
    for i, row in enumerate(coord_rows):
        if not isinstance(row, list) or len(row) != 3:
            _raise_export_error(
                f"ligand_coords[{i}] must be [x, y, z]",
                location=f"ligand_coords[{i}]",
            )
        for j, v in enumerate(row):
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                _raise_export_error(
                    f"ligand_coords[{i}][{j}] must be numeric",
                    location=f"ligand_coords[{i}][{j}]",
                )
            if not math.isfinite(float(v)):
                _raise_export_error(
                    f"ligand_coords[{i}][{j}] must be finite",
                    location=f"ligand_coords[{i}][{j}]",
                )

    if not isinstance(atom_types, list):
        _raise_export_error("ligand_atom_types must be a list", location="ligand_atom_types")

    types: list[Any] = atom_types  # type: ignore[assignment]
    for i, t in enumerate(types):
        if not isinstance(t, str):
            _raise_export_error(
                f"ligand_atom_types[{i}] must be a string (element symbol)",
                location=f"ligand_atom_types[{i}]",
            )
        _validate_token(t, f"ligand_atom_types[{i}]")

    if len(types) != len(coord_rows):
        _raise_export_error(
            f"ligand_atom_types length ({len(types)}) must match "
            f"ligand_coords length ({len(coord_rows)})",
            location="ligand_atom_types",
        )

    _validate_bonds(bonds, len(coord_rows))


def _validate_bonds(bonds: object, num_atoms: int) -> None:
    if not isinstance(bonds, list):
        _raise_export_error("ligand_bonds must be a list", location="ligand_bonds")

    bond_list: list[Any] = bonds  # type: ignore[assignment]
    seen: set[tuple[int, int]] = set()
    for i, bond in enumerate(bond_list):
        if not isinstance(bond, list) or len(bond) != 2:
            _raise_export_error(
                f"ligand_bonds[{i}] must be [index_a, index_b]",
                location=f"ligand_bonds[{i}]",
            )
        a, b = bond
        if isinstance(a, bool) or isinstance(b, bool) or not isinstance(a, int) or not isinstance(b, int):
            _raise_export_error(
                f"ligand_bonds[{i}] indices must be integers",
                location=f"ligand_bonds[{i}]",
            )
        if a < 0 or a >= num_atoms or b < 0 or b >= num_atoms:
            _raise_export_error(
                f"ligand_bonds[{i}] index out of range [0, {num_atoms})",
                location=f"ligand_bonds[{i}]",
            )
        if a == b:
            _raise_export_error(
                f"ligand_bonds[{i}] cannot be a self-bond",
                location=f"ligand_bonds[{i}]",
            )
        pair = (min(a, b), max(a, b))
        if pair in seen:
            _raise_export_error(
                f"ligand_bonds[{i}] is a duplicate bond",
                location=f"ligand_bonds[{i}]",
            )
        seen.add(pair)


# -- edge helpers -----------------------------------------------------


def _find_protein_atom_index(
    protein_atoms: list[dict[str, Any]],
    edge_pa: Any,
) -> int | None:
    """Return the index in *protein_atoms* matching the edge's ProteinAtomIdentity."""
    matches: list[int] = []
    for i, atom in enumerate(protein_atoms):
        if (
            str(atom.get("chain_id", "")) == (edge_pa.chain_id or "")
            and atom.get("residue_number") == edge_pa.residue_number
            and str(atom.get("residue_name", "")) == edge_pa.residue_name
            and str(atom.get("atom_name", "")) == edge_pa.atom_name
            and _optional_identity_fields_match(atom, edge_pa)
        ):
            matches.append(i)
    if len(matches) > 1:
        _raise_export_error(
            "Covalent edge protein atom identity is ambiguous in protein_atom_table",
            location="covalent_edge.protein_atom",
        )
    return matches[0] if matches else None


def _optional_identity_fields_match(atom: dict[str, Any], edge_pa: Any) -> bool:
    """Match every optional identity field supplied by the resolved edge."""
    for field in (
        "altloc",
        "insertion_code",
        "structure_model",
        "asym_id",
        "atom_serial",
    ):
        expected = getattr(edge_pa, field, None)
        if expected is not None and atom.get(field) != expected:
            return False
    return True


# -- ligand atom naming ------------------------------------------------


def _assign_ligand_atom_names(atom_types: list[str]) -> list[str]:
    counts: dict[str, int] = {}
    names: list[str] = []
    for elem in atom_types:
        counts[elem] = counts.get(elem, 0) + 1
        names.append(f"{elem}{counts[elem]}")
    return names


def _validate_token(value: object, location: str) -> None:
    if not isinstance(value, str) or not value or any(ch.isspace() for ch in value):
        _raise_export_error(
            f"{location} must be a non-empty mmCIF token without whitespace",
            location=location,
        )


# -- mmCIF generation --------------------------------------------------


def _build_mmcif(
    *,
    entry_id: str,
    protein_atoms: list[dict[str, Any]],
    ligand_coords: list[list[float]],
    ligand_atom_types: list[str],
    ligand_atom_names: list[str],
    ligand_bonds: list[list[int]],
    covalent_edge: CovalentEdge,
    protein_edge_idx: int,
) -> str:
    lines: list[str] = []

    # -- data block header --
    lines.append(f"data_{entry_id}")
    lines.append("#")

    # -- entry id --
    lines.append(f"_entry.id  {entry_id}")
    lines.append("#")

    # -- atom_site loop header --
    lines.append("loop_")
    lines.append("_atom_site.group_PDB")
    lines.append("_atom_site.id")
    lines.append("_atom_site.type_symbol")
    lines.append("_atom_site.label_atom_id")
    lines.append("_atom_site.label_alt_id")
    lines.append("_atom_site.label_comp_id")
    lines.append("_atom_site.label_asym_id")
    lines.append("_atom_site.label_entity_id")
    lines.append("_atom_site.label_seq_id")
    lines.append("_atom_site.Cartn_x")
    lines.append("_atom_site.Cartn_y")
    lines.append("_atom_site.Cartn_z")
    lines.append("_atom_site.occupancy")
    lines.append("_atom_site.B_iso_or_equiv")
    lines.append("_atom_site.pdbx_formal_charge")
    lines.append("_atom_site.auth_seq_id")
    lines.append("_atom_site.auth_comp_id")
    lines.append("_atom_site.auth_asym_id")
    lines.append("_atom_site.auth_atom_id")
    lines.append("_atom_site.pdbx_PDB_model_num")

    # -- protein atom rows --
    atom_id = 0
    for i, atom in enumerate(protein_atoms):
        atom_id += 1
        lines.append(
            _format_atom_line(
                group_pdb="ATOM",
                atom_id=atom_id,
                element=_val_str(atom, "element"),
                atom_name=_val_str(atom, "atom_name"),
                altloc=_val_str(atom, "altloc", default="."),
                comp_id=_val_str(atom, "residue_name"),
                asym_id=_val_str(atom, "asym_id", default=_val_str(atom, "chain_id")),
                entity_id=1,
                seq_id=_val_int(atom, "residue_number"),
                x=float(atom["x"]),
                y=float(atom["y"]),
                z=float(atom["z"]),
                occupancy=float(atom.get("occupancy", 1.0)),
                b_factor=float(atom.get("b_factor", 0.0)),
                formal_charge=int(atom.get("formal_charge", 0)),
                auth_seq_id=_val_int(atom, "residue_number"),
                auth_comp_id=_val_str(atom, "residue_name"),
                auth_asym_id=_val_str(atom, "asym_id", default=_val_str(atom, "chain_id")),
                auth_atom_id=_val_str(atom, "atom_name"),
                model_num=1,
            )
        )

    # -- ligand atom rows --
    for i, (coord, elem, name) in enumerate(zip(ligand_coords, ligand_atom_types, ligand_atom_names)):
        atom_id += 1
        lines.append(
            _format_atom_line(
                group_pdb="HETATM",
                atom_id=atom_id,
                element=elem,
                atom_name=name,
                altloc=".",
                comp_id="LIG",
                asym_id="L",
                entity_id=2,
                seq_id=1,
                x=coord[0],
                y=coord[1],
                z=coord[2],
                occupancy=1.0,
                b_factor=0.0,
                formal_charge=0,
                auth_seq_id=1,
                auth_comp_id="LIG",
                auth_asym_id="L",
                auth_atom_id=name,
                model_num=1,
            )
        )

    # -- struct_conn loop --
    lines.append("#")
    lines.append("loop_")
    lines.append("_struct_conn.conn_type_id")
    lines.append("_struct_conn.ptnr1_label_asym_id")
    lines.append("_struct_conn.ptnr1_label_comp_id")
    lines.append("_struct_conn.ptnr1_label_seq_id")
    lines.append("_struct_conn.ptnr1_label_atom_id")
    lines.append("_struct_conn.ptnr2_label_asym_id")
    lines.append("_struct_conn.ptnr2_label_comp_id")
    lines.append("_struct_conn.ptnr2_label_seq_id")
    lines.append("_struct_conn.ptnr2_label_atom_id")
    lines.append("_struct_conn.pdbx_dist_value")
    lines.append("_struct_conn.details")

    # protein edge atom info
    prot_atom = protein_atoms[protein_edge_idx]
    prot_asym = _val_str(prot_atom, "asym_id", default=_val_str(prot_atom, "chain_id"))
    prot_comp = _val_str(prot_atom, "residue_name")
    prot_seq = str(_val_int(prot_atom, "residue_number"))
    prot_name = _val_str(prot_atom, "atom_name")

    lines.append(
        f"covale  {prot_asym}  {prot_comp}  {prot_seq}  {prot_name}  "
        f"L  LIG  1  {covalent_edge.ligand_atom.atom_name}  ?  ?"
    )

    lines.append("#")
    return "\n".join(lines) + "\n"


def _format_atom_line(
    *,
    group_pdb: str,
    atom_id: int,
    element: str,
    atom_name: str,
    altloc: str,
    comp_id: str,
    asym_id: str,
    entity_id: int,
    seq_id: int,
    x: float,
    y: float,
    z: float,
    occupancy: float,
    b_factor: float,
    formal_charge: int,
    auth_seq_id: int,
    auth_comp_id: str,
    auth_asym_id: str,
    auth_atom_id: str,
    model_num: int,
) -> str:
    """Format one _atom_site data row, matching the golden fixture column widths."""

    return (
        f"{group_pdb:<6s}{atom_id:>2d}  {element:>2s}  "
        f"{atom_name}  {altloc}  {comp_id:<3s}  "
        f"{asym_id}  {entity_id}  {seq_id}  "
        f"{x:.3f}  {y:.3f}  {z:.3f}  "
        f"{occupancy:.3f}  {b_factor:.3f}  "
        f"{formal_charge}  {auth_seq_id}  {auth_comp_id}  "
        f"{auth_asym_id}  {auth_atom_id}  {model_num}"
    )


def _val_str(atom: dict[str, Any], key: str, *, default: str = "") -> str:
    v = atom.get(key)
    if v is None:
        return default
    return str(v)


def _val_int(atom: dict[str, Any], key: str, *, default: int = 0) -> int:
    v = atom.get(key)
    if v is None:
        return default
    return int(v)
