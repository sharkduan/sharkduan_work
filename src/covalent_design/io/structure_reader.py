"""Pure-Python PDB and mmCIF structure reader.

Reads atom-level fields needed for Task 26 request validation:
chain_id, residue_number, residue_name, atom_name, altloc, occupancy,
insertion_code, structure_model, asym_id.

PDB fixed columns are per wwPDB v3.3:
  https://www.wwpdb.org/documentation/file-format-content/format33/sect9.html

mmCIF _atom_site items per wwPDB dictionary v5:
  https://mmcif.wwpdb.org/dictionaries/mmcif_pdbx_v50.dic/Categories/atom_site.html
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class AtomRecord:
    chain_id: Optional[str]
    residue_number: Optional[int]
    residue_name: str
    atom_name: str
    altloc: Optional[str]  # None for blank/no-altloc single conformer
    occupancy: Optional[float]
    insertion_code: Optional[str]
    structure_model: Optional[int]
    asym_id: Optional[str]
    atom_serial: Optional[int]


def read_structure(path: Path, format: str) -> list[AtomRecord]:
    """Read a PDB or mmCIF structure file and return atom records."""
    text = path.read_text(encoding="utf-8")
    fmt = format.lower()
    if fmt in ("pdb",):
        return _parse_pdb(text)
    if fmt in ("mmcif", "cif"):
        return _parse_mmcif(text)
    raise ValueError(f"Unsupported structure format: {format}")


# ---------------------------------------------------------------------------
# PDB parser
# ---------------------------------------------------------------------------


def _parse_pdb(text: str) -> list[AtomRecord]:
    atoms: list[AtomRecord] = []
    current_model: Optional[int] = None
    for line in text.splitlines():
        record = line[0:6].strip()
        if record == "MODEL":
            model_str = line[10:14].strip()
            current_model = int(model_str) if model_str else None
            continue
        if record == "ENDMDL":
            current_model = None
            continue
        if record not in ("ATOM", "HETATM"):
            continue
        if len(line) < 54:
            continue

        serial_str = line[6:11].strip()
        atom_name = line[12:16].strip()
        altloc = line[16:17].strip()
        residue_name = line[17:20].strip()
        chain_id = line[21:22].strip()
        res_seq_str = line[22:26].strip()
        i_code = line[26:27].strip()
        occ_str = line[54:60].strip()

        atom_serial = int(serial_str) if serial_str else None
        residue_number = int(res_seq_str) if res_seq_str else None
        occupancy = float(occ_str) if occ_str else None
        insertion_code = i_code if i_code else None
        chain = chain_id if chain_id else None
        altloc_val = altloc if altloc else None

        atoms.append(
            AtomRecord(
                chain_id=chain,
                residue_number=residue_number,
                residue_name=residue_name,
                atom_name=atom_name,
                altloc=altloc_val,
                occupancy=occupancy,
                insertion_code=insertion_code,
                structure_model=current_model,
                asym_id=None,
                atom_serial=atom_serial,
            )
        )
    return atoms


# ---------------------------------------------------------------------------
# mmCIF parser
# ---------------------------------------------------------------------------


def _parse_mmcif(text: str) -> list[AtomRecord]:
    atoms: list[AtomRecord] = []
    lines = text.splitlines()

    atom_site_columns: list[str] = []
    in_atom_site = False

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("data_") or stripped.startswith("loop_"):
            continue
        if stripped.startswith("_"):
            if stripped.startswith("_atom_site."):
                atom_site_columns.append(stripped)
                in_atom_site = True
            else:
                # A different category started; stop collecting data for atom_site
                in_atom_site = False
            continue

        if in_atom_site:
            tokens = stripped.split()
            if len(tokens) == len(atom_site_columns):
                atom = _build_mmcif_atom(atom_site_columns, tokens)
                if atom is not None:
                    atoms.append(atom)

    return atoms


def _build_mmcif_atom(
    columns: list[str], tokens: list[str]
) -> Optional[AtomRecord]:
    col_map = {col: val for col, val in zip(columns, tokens)}

    label_comp_id = col_map.get("_atom_site.label_comp_id", "")
    label_atom_id = col_map.get("_atom_site.label_atom_id", "")
    if not label_comp_id or not label_atom_id:
        return None

    def _str_or_none(col: str) -> Optional[str]:
        val = col_map.get(col, ".")
        val = val.strip()
        if val in (".", "?", ""):
            return None
        return val

    def _int_or_none(col: str) -> Optional[int]:
        try:
            return int(col_map.get(col, ""))
        except (ValueError, KeyError):
            return None

    def _float_or_none(col: str) -> Optional[float]:
        try:
            return float(col_map.get(col, ""))
        except (ValueError, KeyError):
            return None

    return AtomRecord(
        chain_id=_str_or_none("_atom_site.label_asym_id"),
        residue_number=_int_or_none("_atom_site.label_seq_id"),
        residue_name=label_comp_id,
        atom_name=label_atom_id,
        altloc=_str_or_none("_atom_site.label_alt_id"),
        occupancy=_float_or_none("_atom_site.occupancy"),
        insertion_code=_str_or_none("_atom_site.pdbx_PDB_ins_code"),
        structure_model=_int_or_none("_atom_site.pdbx_PDB_model_num"),
        asym_id=_str_or_none("_atom_site.label_asym_id"),
        atom_serial=_int_or_none("_atom_site.id"),
    )
