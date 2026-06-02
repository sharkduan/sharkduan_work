"""Task 26 request validation.

Load, validate, and normalise reactive-site generation requests.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from covalent_design.contracts.errors import ContractError
from covalent_design.contracts.types import ProteinAtomIdentity
from covalent_design.inference.request_schema import (
    LigandSizeControl,
    ProteinAtomLocator,
    ProteinChemicalStateRequest,
    ReactiveSiteGenerationRequest,
    ValidatedRequest,
)
from covalent_design.io.structure_reader import AtomRecord, read_structure
from covalent_design.rules.schema import ReactionFamilyRuleRow, ReactionFamilyRuleTable
from covalent_design.rules.validate import load_rule_table


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def load_request_file(path: Path) -> ReactiveSiteGenerationRequest:
    """Parse a YAML (authoritative) or JSON (accepted) request file.

    Raises ContractError(owner="request", code="REQUEST_STRUCTURE_UNREADABLE")
    for unknown extension, malformed content, or unreadable files.
    """
    path = Path(path)
    suffix = path.suffix.lower()

    if suffix in (".yml", ".yaml"):
        raw = _load_yaml(str(path))
    elif suffix == ".json":
        raw = _load_json(str(path))
    else:
        raise ContractError(
            code="REQUEST_STRUCTURE_UNREADABLE",
            owner="request",
            message=f"Unknown request file extension: {suffix}",
            location=str(path),
        )

    try:
        return _dict_to_request(raw)
    except (KeyError, TypeError, ValueError) as exc:
        raise ContractError(
            code="REQUEST_STRUCTURE_UNREADABLE",
            owner="request",
            message=f"Malformed request content: {exc}",
            location=str(path),
        ) from exc


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_request(
    request: ReactiveSiteGenerationRequest,
    rules: ReactionFamilyRuleTable,
    *,
    request_base_dir: Optional[str] = None,
) -> ValidatedRequest:
    """Validate a loaded request against a rule table.

    Returns ValidatedRequest on success.
    Raises ContractError(owner="request", code=...) on semantic failure.

    Validation order avoids cascading errors:
      1. sample_count
      2. ligand size control coherence
      3. structure readable & parsed
      4. target residue resolve (not found / ambiguous)
      5. residue name mismatch
      6. target atom + altloc resolve
      7. family supported
      8. residue-family conflict
      9. atom-family conflict
      10. required chemical state
    """
    # 1. sample_count must be a positive int (not bool)
    if not isinstance(request.sample_count, int) or isinstance(request.sample_count, bool):
        raise ContractError(
            code="REQUEST_SAMPLE_COUNT_INVALID",
            owner="request",
            message=f"sample_count must be an integer, got {type(request.sample_count).__name__}: {request.sample_count!r}",
            location=request.request_id,
        )
    if request.sample_count <= 0:
        raise ContractError(
            code="REQUEST_SAMPLE_COUNT_INVALID",
            owner="request",
            message=f"sample_count must be positive, got {request.sample_count}",
            location=request.request_id,
        )

    # 2. ligand size control coherence
    _validate_size_control(request.size_control, request.request_id)

    # 3. structure readable & parsed
    structure_path = _resolve_structure_path(
        request.protein_structure_uri,
        request_base_dir,
        request.request_id,
    )
    atoms = _read_structure(structure_path, request.protein_structure_format, request.request_id)

    # 4. target residue resolve
    loc = request.target_atom_identity_request
    candidate_atoms = _filter_by_residue(atoms, loc)

    if not candidate_atoms:
        raise ContractError(
            code="REQUEST_TARGET_RESIDUE_NOT_FOUND",
            owner="request",
            message=f"Residue {loc.residue_name} "
            f"chain={loc.chain_id} res_num={loc.residue_number} not found",
            location=request.request_id,
        )

    # Check for ambiguity: multiple distinct chain+residue combos
    unique_residues = set(
        (a.chain_id, a.residue_number, a.insertion_code)
        for a in candidate_atoms
    )
    if len(unique_residues) > 1:
        raise ContractError(
            code="REQUEST_TARGET_RESIDUE_AMBIGUOUS",
            owner="request",
            message=(
                f"Multiple residues match chain={loc.chain_id} "
                f"res_num={loc.residue_number} res_name={loc.residue_name}"
            ),
            location=request.request_id,
        )

    # 5. residue name mismatch
    resolved_res_name = candidate_atoms[0].residue_name
    if resolved_res_name.upper() != loc.residue_name.upper():
        raise ContractError(
            code="REQUEST_RESIDUE_NAME_MISMATCH",
            owner="request",
            message=(
                f"Request specified residue {loc.residue_name} "
                f"but structure has {resolved_res_name}"
            ),
            location=request.request_id,
        )

    # 6. target atom + altloc resolve
    atom_identity, resolved_altloc = _resolve_atom_with_altloc(
        candidate_atoms, loc, request.target_altloc, request.request_id
    )

    # 7. family supported
    family = _find_family(rules, request.residue_reaction_family)
    if family is None:
        raise ContractError(
            code="REQUEST_FAMILY_UNSUPPORTED",
            owner="request",
            message=f"Reaction family not in rule table: {request.residue_reaction_family}",
            location=request.request_id,
        )

    # 8. residue-family conflict
    if family.target_residue_name.upper() != resolved_res_name.upper():
        raise ContractError(
            code="REQUEST_RESIDUE_FAMILY_CONFLICT",
            owner="request",
            message=(
                f"Family {family.family_id} expects residue {family.target_residue_name} "
                f"but target is {resolved_res_name}"
            ),
            location=request.request_id,
        )

    # 9. atom-family conflict
    if family.target_atom_name.upper() != loc.atom_name.upper():
        raise ContractError(
            code="REQUEST_ATOM_FAMILY_CONFLICT",
            owner="request",
            message=(
                f"Family {family.family_id} expects atom {family.target_atom_name} "
                f"but request targets {loc.atom_name}"
            ),
            location=request.request_id,
        )

    # 10. required chemical state
    _validate_chemical_state(
        request.protein_chemical_state_request,
        family,
        request.request_id,
    )

    return ValidatedRequest(
        request=request,
        resolved_target_atom_identity=atom_identity,
        resolved_target_altloc=resolved_altloc,
        rule_table_version=rules.version,
    )


def validate_request_file(
    path: Path,
    *,
    rules_path: Optional[Path] = None,
) -> ValidatedRequest:
    """Load and validate a request file in one call.

    Returns ValidatedRequest on success.
    Raises ContractError(owner="request", code=...) on failure.
    """
    request = load_request_file(path)

    if rules_path is None:
        rules_path = _default_rules_path()

    rules = load_rule_table(rules_path)

    return validate_request(
        request,
        rules,
        request_base_dir=str(path.parent),
    )


# ---------------------------------------------------------------------------
# Normalised YAML output
# ---------------------------------------------------------------------------


def normalized_request_yaml(validated: ValidatedRequest) -> str:
    """Produce deterministic canonical YAML for a validated request.

    Pure Python; sorted keys; no external YAML dependency.
    """
    lines: list[str] = []
    _emit_request_yaml(validated, lines, indent=0)
    return "\n".join(lines) + "\n"


def write_normalized_request(validated: ValidatedRequest, path: Path) -> Path:
    """Write deterministic canonical YAML to a file.  Returns the path."""
    yaml_str = normalized_request_yaml(validated)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(yaml_str)
    return p


# ---------------------------------------------------------------------------
# Size control helpers
# ---------------------------------------------------------------------------


def _validate_size_control(
    sc: Optional[LigandSizeControl],
    request_id: str,
) -> None:
    """Validate ligand size control coherence (step 2).

    Rules:
      - Can be absent (None) — valid.
      - Fixed mode: num_ligand_heavy_atoms set, min/max both None.
      - Range mode: min and max set, num_ligand_heavy_atoms None.
      - No mixed mode.
      - Fixed must be positive.
      - Range: 0 < min <= max.
    """
    if sc is None:
        return

    has_fixed = sc.num_ligand_heavy_atoms is not None
    has_min = sc.min_ligand_heavy_atoms is not None
    has_max = sc.max_ligand_heavy_atoms is not None

    # Conflict: both fixed and range fields set
    if has_fixed and (has_min or has_max):
        raise ContractError(
            code="REQUEST_LIGAND_SIZE_CONFLICT",
            owner="request",
            message="Cannot specify both fixed size and range size simultaneously",
            location=request_id,
        )

    if has_fixed:
        if not isinstance(sc.num_ligand_heavy_atoms, int) or isinstance(sc.num_ligand_heavy_atoms, bool):
            raise ContractError(
                code="REQUEST_LIGAND_SIZE_INVALID",
                owner="request",
                message=f"num_ligand_heavy_atoms must be an integer, got {type(sc.num_ligand_heavy_atoms).__name__}: {sc.num_ligand_heavy_atoms!r}",
                location=request_id,
            )
        if sc.num_ligand_heavy_atoms <= 0:
            raise ContractError(
                code="REQUEST_LIGAND_SIZE_INVALID",
                owner="request",
                message=f"num_ligand_heavy_atoms must be positive, got {sc.num_ligand_heavy_atoms}",
                location=request_id,
            )
    elif has_min or has_max:
        min_val = sc.min_ligand_heavy_atoms
        max_val = sc.max_ligand_heavy_atoms
        if min_val is None or max_val is None:
            raise ContractError(
                code="REQUEST_LIGAND_SIZE_RANGE_INVALID",
                owner="request",
                message="Range mode requires both min_ligand_heavy_atoms and max_ligand_heavy_atoms",
                location=request_id,
            )
        if (not isinstance(min_val, int) or isinstance(min_val, bool)
                or not isinstance(max_val, int) or isinstance(max_val, bool)):
            raise ContractError(
                code="REQUEST_LIGAND_SIZE_RANGE_INVALID",
                owner="request",
                message=f"Range bounds must be integers, got min={type(min_val).__name__}: {min_val!r}, max={type(max_val).__name__}: {max_val!r}",
                location=request_id,
            )
        if min_val <= 0 or max_val <= 0:
            raise ContractError(
                code="REQUEST_LIGAND_SIZE_RANGE_INVALID",
                owner="request",
                message=f"Range bounds must be positive, got [{min_val}, {max_val}]",
                location=request_id,
            )
        if min_val > max_val:
            raise ContractError(
                code="REQUEST_LIGAND_SIZE_RANGE_INVALID",
                owner="request",
                message=f"min_ligand_heavy_atoms ({min_val}) > max_ligand_heavy_atoms ({max_val})",
                location=request_id,
            )


# ---------------------------------------------------------------------------
# Structure helpers
# ---------------------------------------------------------------------------


def _resolve_structure_path(
    uri: str,
    base_dir: Optional[str],
    request_id: str,
) -> Path:
    """Resolve a structure URI relative to request_base_dir."""
    path = Path(uri)
    if not path.is_absolute() and base_dir is not None:
        path = Path(base_dir) / path
    return path


def _read_structure(
    path: Path,
    format: str,
    request_id: str,
) -> list[AtomRecord]:
    """Read a PDB or mmCIF structure file.

    Raises REQUEST_STRUCTURE_UNREADABLE on any I/O or parse failure.
    """
    if not path.exists():
        raise ContractError(
            code="REQUEST_STRUCTURE_UNREADABLE",
            owner="request",
            message=f"Structure file not found: {path}",
            location=request_id,
        )
    try:
        atoms = read_structure(path, format)
        if not atoms:
            raise ContractError(
                code="REQUEST_STRUCTURE_UNREADABLE",
                owner="request",
                message=f"No ATOM/HETATM records found in structure file: {path}",
                location=request_id,
            )
        return atoms
    except ContractError:
        raise
    except Exception as exc:
        raise ContractError(
            code="REQUEST_STRUCTURE_UNREADABLE",
            owner="request",
            message=f"Failed to read structure {path}: {exc}",
            location=request_id,
        ) from exc


# ---------------------------------------------------------------------------
# Residue / atom resolution
# ---------------------------------------------------------------------------


def _filter_by_residue(
    atoms: list[AtomRecord],
    loc: ProteinAtomLocator,
) -> list[AtomRecord]:
    """Return atoms matching the locator's residue criteria.

    Filtering by chain_id, residue_number, and optionally residue_name,
    insertion_code, structure_model, asym_id.
    """
    result: list[AtomRecord] = []
    for a in atoms:
        if loc.chain_id is not None and a.chain_id != loc.chain_id:
            continue
        if loc.residue_number is not None and a.residue_number != loc.residue_number:
            continue
        if loc.insertion_code is not None and a.insertion_code != loc.insertion_code:
            continue
        if loc.structure_model is not None and a.structure_model != loc.structure_model:
            continue
        if loc.asym_id is not None and a.asym_id != loc.asym_id:
            continue
        result.append(a)
    return result


def _resolve_atom_with_altloc(
    candidate_atoms: list[AtomRecord],
    loc: ProteinAtomLocator,
    target_altloc: str | None,
    request_id: str,
) -> tuple[ProteinAtomIdentity, str | None]:
    """Resolve the target atom identity and altloc.

    Steps:
      1. Filter candidate atoms by atom_name.
      2. If no atoms match → REQUEST_TARGET_ATOM_NOT_FOUND.
      3. Determine altloc:
         a. All atoms have blank altloc → resolved_altloc = None.
         b. explicit altloc override → use it; if not found → error.
         c. No override: pick highest occupancy; tie or missing → "A".
    """
    matching = [a for a in candidate_atoms if a.atom_name == loc.atom_name]

    if not matching:
        raise ContractError(
            code="REQUEST_TARGET_ATOM_NOT_FOUND",
            owner="request",
            message=(
                f"Atom {loc.atom_name} not found in residue "
                f"chain={loc.chain_id} res_num={loc.residue_number}"
            ),
            location=request_id,
        )

    # Determine if there are real altlocs (non-blank)
    altloc_groups: dict[str, list[AtomRecord]] = {}
    for a in matching:
        key = a.altloc if a.altloc else ""
        altloc_groups.setdefault(key, []).append(a)

    has_multi_altloc = any(k != "" for k in altloc_groups)

    if not has_multi_altloc:
        # Single conformer (blank altloc)
        resolved_altloc: str | None = None
        chosen = matching[0]
    elif target_altloc is not None:
        # Explicit override
        chosen_list = [a for a in matching if a.altloc == target_altloc]
        if not chosen_list:
            raise ContractError(
                code="REQUEST_TARGET_ATOM_NOT_FOUND",
                owner="request",
                message=(
                    f"Requested altloc {target_altloc!r} does not exist "
                    f"for atom {loc.atom_name}"
                ),
                location=request_id,
            )
        chosen = chosen_list[0]
        resolved_altloc = target_altloc
    else:
        # Pick highest occupancy
        altloc_entries = [(a.altloc, a.occupancy or 0.0) for a in matching]
        # Group by altloc, sum occupancy or take first entry
        best_altloc = _pick_best_altloc(altloc_entries)
        chosen = next(a for a in matching if a.altloc == best_altloc)
        resolved_altloc = best_altloc

    identity = ProteinAtomIdentity(
        chain_id=chosen.chain_id,
        residue_number=chosen.residue_number,
        residue_name=chosen.residue_name,
        atom_name=chosen.atom_name,
        altloc=resolved_altloc,
        insertion_code=chosen.insertion_code,
        structure_model=chosen.structure_model,
        asym_id=chosen.asym_id,
        atom_serial=chosen.atom_serial,
    )

    return identity, resolved_altloc


def _pick_best_altloc(
    entries: list[tuple[str | None, float]],
) -> str:
    """Pick the altloc with the highest occupancy.

    Ties → "A".  Missing occupancy (0.0) → fall back to alphabetical "A".
    """
    # Map altloc → max occupancy for that altloc
    best: dict[str, float] = {}
    for altloc, occ in entries:
        key = altloc if altloc else ""
        best[key] = max(best.get(key, 0.0), occ)

    if not best:
        return "A"

    max_occ = max(best.values())
    # If all occupancies are 0, choose "A"
    if max_occ == 0.0:
        return "A" if "A" in best else sorted(best.keys())[0]

    candidates = [k for k, v in best.items() if v == max_occ]
    return "A" if "A" in candidates else sorted(candidates)[0]


# ---------------------------------------------------------------------------
# Family lookups
# ---------------------------------------------------------------------------


def _find_family(
    table: ReactionFamilyRuleTable,
    family_id: str,
) -> Optional[ReactionFamilyRuleRow]:
    for family in table.families:
        if family.family_id == family_id:
            return family
    return None


# ---------------------------------------------------------------------------
# Chemical state validation
# ---------------------------------------------------------------------------


def _validate_chemical_state(
    cs: Optional[ProteinChemicalStateRequest],
    family: ReactionFamilyRuleRow,
    request_id: str,
) -> None:
    """Validate that required chemical state fields are present (step 10).

    The family's protein_state_requirements maps each field to one of:
      "required", "optional", "not_applicable", "required_or_inferred".

    If a field is "required" or "required_or_inferred", the corresponding
    chemical state request field must be non-None.
    """
    psr = family.protein_state_requirements
    if psr is None:
        return  # No requirements → nothing to check

    # Build mapping: request field name → requirement string
    requirement_map = {
        "target_atom_formal_charge": psr.target_atom_formal_charge,
        "target_atom_protonation_state": psr.target_atom_protonation_state,
        "target_atom_hydrogen_state": psr.explicit_hydrogen_state,
    }

    for field_name, requirement in requirement_map.items():
        if requirement in ("required", "required_or_inferred"):
            if cs is None:
                raise ContractError(
                    code="REQUEST_REQUIRED_CHEMICAL_STATE_UNAVAILABLE",
                    owner="request",
                    message=(
                        f"Family {family.family_id} requires chemical state "
                        f"({field_name} is {requirement}) but no "
                        f"protein_chemical_state_request was provided"
                    ),
                    location=request_id,
                )
            value = getattr(cs, field_name, None)
            if value is None:
                raise ContractError(
                    code="REQUEST_REQUIRED_CHEMICAL_STATE_UNAVAILABLE",
                    owner="request",
                    message=(
                        f"Family {family.family_id} requires {field_name} "
                        f"({requirement}) but it is missing or None"
                    ),
                    location=request_id,
                )


# ---------------------------------------------------------------------------
# YAML / JSON loading helpers
# ---------------------------------------------------------------------------


def _load_yaml(path_str: str) -> dict:
    """Load YAML using PyYAML if available; else minimal fallback parser."""
    try:
        import yaml as _yaml

        with open(path_str, "r", encoding="utf-8") as fh:
            return _yaml.safe_load(fh)
    except ImportError:
        pass
    except Exception as exc:
        raise ContractError(
            code="REQUEST_STRUCTURE_UNREADABLE",
            owner="request",
            message=f"YAML parse error: {exc}",
            location=path_str,
        ) from exc

    try:
        from covalent_design.rules.validate import _parse_minimal_yaml

        with open(path_str, "r", encoding="utf-8") as fh:
            data = _parse_minimal_yaml(fh.read())
        if not isinstance(data, dict):
            raise ContractError(
                code="REQUEST_STRUCTURE_UNREADABLE",
                owner="request",
                message="Request file must contain a top-level YAML mapping",
                location=path_str,
            )
        return data
    except ContractError:
        raise
    except Exception as exc:
        raise ContractError(
            code="REQUEST_STRUCTURE_UNREADABLE",
            owner="request",
            message=f"YAML parse error: {exc}",
            location=path_str,
        ) from exc


def _load_json(path_str: str) -> dict:
    """Load JSON request file."""
    try:
        with open(path_str, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            raise ContractError(
                code="REQUEST_STRUCTURE_UNREADABLE",
                owner="request",
                message="Request file must contain a top-level JSON object",
                location=path_str,
            )
        return data
    except json.JSONDecodeError as exc:
        raise ContractError(
            code="REQUEST_STRUCTURE_UNREADABLE",
            owner="request",
            message=f"JSON parse error: {exc}",
            location=path_str,
        ) from exc
    except ContractError:
        raise
    except Exception as exc:
        raise ContractError(
            code="REQUEST_STRUCTURE_UNREADABLE",
            owner="request",
            message=f"Failed to read JSON: {exc}",
            location=path_str,
        ) from exc


# ---------------------------------------------------------------------------
# Dict → typed request conversion
# ---------------------------------------------------------------------------


def _dict_to_request(raw: dict) -> ReactiveSiteGenerationRequest:
    """Convert a parsed dict into a ReactiveSiteGenerationRequest."""
    loc_dict = raw.get("target_atom_identity_request")
    if not isinstance(loc_dict, dict):
        raise ValueError("target_atom_identity_request must be a mapping")

    locator = ProteinAtomLocator(
        chain_id=loc_dict.get("chain_id"),
        residue_number=loc_dict.get("residue_number"),
        residue_name=str(loc_dict["residue_name"]),
        atom_name=str(loc_dict["atom_name"]),
        insertion_code=loc_dict.get("insertion_code"),
        structure_model=loc_dict.get("structure_model"),
        asym_id=loc_dict.get("asym_id"),
    )

    size_control = None
    sc_dict = raw.get("size_control")
    if isinstance(sc_dict, dict):
        size_control = LigandSizeControl(
            num_ligand_heavy_atoms=sc_dict.get("num_ligand_heavy_atoms"),
            min_ligand_heavy_atoms=sc_dict.get("min_ligand_heavy_atoms"),
            max_ligand_heavy_atoms=sc_dict.get("max_ligand_heavy_atoms"),
        )

    chemical_state = None
    cs_dict = raw.get("protein_chemical_state_request")
    if isinstance(cs_dict, dict):
        chemical_state = ProteinChemicalStateRequest(
            target_atom_formal_charge=cs_dict.get("target_atom_formal_charge"),
            target_atom_protonation_state=cs_dict.get("target_atom_protonation_state"),
            target_atom_hydrogen_state=cs_dict.get("target_atom_hydrogen_state"),
            protein_preparation_policy=cs_dict.get("protein_preparation_policy"),
            chemical_state_source=cs_dict.get("chemical_state_source"),
            chemical_state_tool_name=cs_dict.get("chemical_state_tool_name"),
            chemical_state_tool_version=cs_dict.get("chemical_state_tool_version"),
            chemical_state_confidence=cs_dict.get("chemical_state_confidence"),
        )

    target_altloc = raw.get("target_altloc")
    if target_altloc is not None and not isinstance(target_altloc, str):
        target_altloc = str(target_altloc)

    return ReactiveSiteGenerationRequest(
        request_id=str(raw["request_id"]),
        protein_structure_uri=str(raw["protein_structure_uri"]),
        protein_structure_format=str(raw["protein_structure_format"]),
        target_atom_identity_request=locator,
        residue_reaction_family=str(raw["residue_reaction_family"]),
        sample_count=raw["sample_count"],
        size_control=size_control,
        protein_chemical_state_request=chemical_state,
        target_altloc=target_altloc,
    )


# ---------------------------------------------------------------------------
# Normalised YAML emission (pure Python, deterministic)
# ---------------------------------------------------------------------------


def _emit_request_yaml(
    validated: ValidatedRequest,
    lines: list[str],
    indent: int,
) -> None:
    prefix = "  " * indent
    req = validated.request
    identity = validated.resolved_target_atom_identity

    _emit_str(prefix, "request_id", req.request_id, lines)
    _emit_str(prefix, "protein_structure_uri", req.protein_structure_uri, lines)
    _emit_str(prefix, "protein_structure_format", req.protein_structure_format, lines)

    # target_atom_identity_request
    lines.append(f"{prefix}target_atom_identity_request:")
    loc = req.target_atom_identity_request
    _emit_optional_str(prefix + "  ", "chain_id", loc.chain_id, lines)
    _emit_optional_int(prefix + "  ", "residue_number", loc.residue_number, lines)
    _emit_str(prefix + "  ", "residue_name", loc.residue_name, lines)
    _emit_str(prefix + "  ", "atom_name", loc.atom_name, lines)
    _emit_optional_str(prefix + "  ", "insertion_code", loc.insertion_code, lines)
    _emit_optional_int(prefix + "  ", "structure_model", loc.structure_model, lines)
    _emit_optional_str(prefix + "  ", "asym_id", loc.asym_id, lines)

    _emit_str(prefix, "residue_reaction_family", req.residue_reaction_family, lines)
    _emit_int(prefix, "sample_count", req.sample_count, lines)

    # size_control
    if req.size_control is not None:
        lines.append(f"{prefix}size_control:")
        sc = req.size_control
        _emit_optional_int(prefix + "  ", "num_ligand_heavy_atoms", sc.num_ligand_heavy_atoms, lines)
        _emit_optional_int(prefix + "  ", "min_ligand_heavy_atoms", sc.min_ligand_heavy_atoms, lines)
        _emit_optional_int(prefix + "  ", "max_ligand_heavy_atoms", sc.max_ligand_heavy_atoms, lines)

    # protein_chemical_state_request
    if req.protein_chemical_state_request is not None:
        lines.append(f"{prefix}protein_chemical_state_request:")
        cs = req.protein_chemical_state_request
        _emit_optional_int(prefix + "  ", "target_atom_formal_charge", cs.target_atom_formal_charge, lines)
        _emit_optional_str(prefix + "  ", "target_atom_protonation_state", cs.target_atom_protonation_state, lines)
        _emit_optional_str(prefix + "  ", "target_atom_hydrogen_state", cs.target_atom_hydrogen_state, lines)
        _emit_optional_str(prefix + "  ", "protein_preparation_policy", cs.protein_preparation_policy, lines)
        _emit_optional_str(prefix + "  ", "chemical_state_source", cs.chemical_state_source, lines)
        _emit_optional_str(prefix + "  ", "chemical_state_tool_name", cs.chemical_state_tool_name, lines)
        _emit_optional_str(prefix + "  ", "chemical_state_tool_version", cs.chemical_state_tool_version, lines)
        _emit_optional_str(prefix + "  ", "chemical_state_confidence", cs.chemical_state_confidence, lines)

    _emit_optional_str(prefix, "target_altloc", req.target_altloc, lines)

    # resolved fields
    lines.append(f"{prefix}resolved_target_atom_identity:")
    _emit_optional_str(prefix + "  ", "chain_id", identity.chain_id, lines)
    _emit_optional_int(prefix + "  ", "residue_number", identity.residue_number, lines)
    _emit_str(prefix + "  ", "residue_name", identity.residue_name, lines)
    _emit_str(prefix + "  ", "atom_name", identity.atom_name, lines)
    _emit_optional_str(prefix + "  ", "altloc", identity.altloc, lines)
    _emit_optional_str(prefix + "  ", "insertion_code", identity.insertion_code, lines)
    _emit_optional_int(prefix + "  ", "structure_model", identity.structure_model, lines)
    _emit_optional_str(prefix + "  ", "asym_id", identity.asym_id, lines)

    _emit_optional_str(prefix, "resolved_target_altloc", validated.resolved_target_altloc, lines)
    _emit_int(prefix, "rule_table_version", validated.rule_table_version, lines)


def _emit_str(prefix: str, key: str, value: str, lines: list[str]) -> None:
    lines.append(f"{prefix}{key}: {_yaml_quote(value)}")


def _emit_int(prefix: str, key: str, value: int, lines: list[str]) -> None:
    lines.append(f"{prefix}{key}: {value}")


def _emit_optional_str(prefix: str, key: str, value: str | None, lines: list[str]) -> None:
    if value is None:
        lines.append(f"{prefix}{key}: null")
    else:
        lines.append(f"{prefix}{key}: {_yaml_quote(value)}")


def _emit_optional_int(prefix: str, key: str, value: int | None, lines: list[str]) -> None:
    if value is None:
        lines.append(f"{prefix}{key}: null")
    else:
        lines.append(f"{prefix}{key}: {value}")


def _yaml_quote(value: str) -> str:
    """Produce a deterministic YAML-compatible double-quoted scalar string."""
    return json.dumps(value, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Default rule table path
# ---------------------------------------------------------------------------


def _default_rules_path() -> Path:
    """Return the repository default rule table path.

    Uses data/rules/reaction_family_rule_table.yml relative to the repo root.
    """
    # Walk up from this module to find the repo root (where data/ lives)
    this_dir = Path(__file__).resolve().parent
    for ancestor in this_dir.parents:
        candidate = ancestor / "data" / "rules" / "reaction_family_rule_table.yml"
        if candidate.exists():
            return candidate
    # Fallback: repo root is 3 levels up from src/covalent_design/inference/
    repo_root = this_dir.parents[2]
    return repo_root / "data" / "rules" / "reaction_family_rule_table.yml"
