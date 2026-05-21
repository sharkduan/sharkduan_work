"""Rule table loading and validation."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Optional, Union

from covalent_design.contracts.errors import ContractErrorInfo
from covalent_design.contracts.types import (
    CONTRACT_VERSION,
    ValidationReceipt,
    ContractEnvelope,
    Provenance,
)
from covalent_design.rules.schema import (
    RESIDUE_ATOM_CONTRACT,
    VALID_ANCHOR_ATOMS,
    VALID_GEOMETRY_STATUSES,
    VALID_LIGAND_NEIGHBOR_POLICIES,
    VALID_PROTEIN_STATE_VALUES,
    VALID_REACTION_CLASSES,
    VALID_RESIDUE_NAMES,
    VALID_WARHEAD_STATUSES,
    GeometryRange,
    GeometryStatus,
    ProteinStateRequirements,
    ReactionFamilyRuleRow,
    ReactionFamilyRuleTable,
    RuleValidationReport,
    ValenceDelta,
)


VALIDATOR_NAME = "covalent_design.rules.validate"


# ======================================================================
# public API
# ======================================================================

def load_rule_table(path: Path) -> ReactionFamilyRuleTable:
    """Parse a YAML rule table file into a typed object.

    Uses PyYAML if available; otherwise falls back to a minimal parser
    that handles the committed fixture format (JSON-compatible YAML subset).
    """
    path = Path(path)
    input_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    raw = _load_yaml(str(path))
    return _dict_to_table(raw, input_sha256=input_sha256)


def validate_rule_table(
    table: ReactionFamilyRuleTable,
) -> ContractEnvelope[RuleValidationReport]:
    """Validate a loaded rule table and return an envelope.

    The envelope payload carries per-family pass/fail/pending details.
    The receipt uses the standard ValidationReceipt shape.
    """
    errors: list[ContractErrorInfo] = []
    warnings: list[ContractErrorInfo] = []
    families_report: list[dict] = []

    # -- duplicate family_id check --
    seen_ids: set[str] = set()
    for family in table.families:
        if family.family_id in seen_ids:
            errors.append(_err(
                "RULE_DUPLICATE_FAMILY_ID",
                f"Duplicate family_id: {family.family_id}",
                family.family_id,
            ))
        seen_ids.add(family.family_id)

    for family in table.families:
        report, family_errors, family_warnings = _validate_one_family(family)
        families_report.append(report)
        errors.extend(family_errors)
        warnings.extend(family_warnings)

    ok = len(errors) == 0
    report = RuleValidationReport(
        families=families_report,
        ok=ok,
        error_codes=[e.code for e in errors],
    )

    input_bytes = table.input_sha256 or _table_fingerprint(table)
    receipt = ValidationReceipt(
        validator=VALIDATOR_NAME,
        contract_version=CONTRACT_VERSION,
        input_sha256=input_bytes,
        passed=ok,
        warnings=tuple(warnings),
        errors=tuple(errors),
    )

    return ContractEnvelope(
        payload=report,
        artifacts=(),
        receipt=receipt,
        provenance=Provenance(),
    )


# ======================================================================
# per-family validation
# ======================================================================

def _validate_one_family(
    family: ReactionFamilyRuleRow,
) -> tuple[dict, list[ContractErrorInfo], list[ContractErrorInfo]]:
    errors: list[ContractErrorInfo] = []
    warnings: list[ContractErrorInfo] = []
    loc = family.family_id

    # -- family_id decomposition and consistency --
    parts = family.family_id.split("_", 1)
    residue_token = parts[0] if parts else ""
    reaction_suffix = parts[1] if len(parts) > 1 else ""

    # family_id residue token must match target_residue_name
    if residue_token != family.target_residue_name:
        errors.append(_err(
            "RULE_FAMILY_ID_RESIDUE_MISMATCH",
            f"family_id residue token '{residue_token}' != target_residue_name '{family.target_residue_name}'",
            loc,
        ))

    # family_id reaction suffix must match residue_reaction_class
    if reaction_suffix != family.residue_reaction_class:
        errors.append(_err(
            "RULE_FAMILY_ID_REACTION_CLASS_MISMATCH",
            f"family_id reaction suffix '{reaction_suffix}' != residue_reaction_class '{family.residue_reaction_class}'",
            loc,
        ))

    # -- residue name in first-pass vocabulary --
    if family.target_residue_name not in VALID_RESIDUE_NAMES:
        errors.append(_err(
            "RULE_UNSUPPORTED_RESIDUE",
            f"target_residue_name '{family.target_residue_name}' not in first-pass vocabulary",
            loc,
        ))

    # -- target atom matches residue contract --
    expected_atom = RESIDUE_ATOM_CONTRACT.get(family.target_residue_name)
    if expected_atom is not None and family.target_atom_name != expected_atom:
        errors.append(_err(
            "RULE_TARGET_ATOM_CONTRACT_VIOLATION",
            f"target_atom_name '{family.target_atom_name}' != expected '{expected_atom}' for {family.target_residue_name}",
            loc,
        ))

    # -- reaction class validity --
    if family.residue_reaction_class not in VALID_REACTION_CLASSES:
        errors.append(_err(
            "RULE_UNSUPPORTED_REACTION_CLASS",
            f"residue_reaction_class '{family.residue_reaction_class}' not in first-pass vocabulary",
            loc,
        ))

    # -- at least one ligand attachment element --
    if len(family.allowed_ligand_attachment_elements) == 0:
        errors.append(_err(
            "RULE_NO_LIGAND_ATTACHMENT_ELEMENT",
            "allowed_ligand_attachment_elements must not be empty",
            loc,
        ))

    # -- at least one covalent bond type --
    if len(family.allowed_covalent_bond_types) == 0:
        errors.append(_err(
            "RULE_NO_COVALENT_BOND_TYPE",
            "allowed_covalent_bond_types must not be empty",
            loc,
        ))

    # -- warhead_rule_status validity --
    if family.warhead_rule_status not in VALID_WARHEAD_STATUSES:
        errors.append(_err(
            "RULE_INVALID_WARHEAD_STATUS",
            f"warhead_rule_status '{family.warhead_rule_status}' not in {sorted(VALID_WARHEAD_STATUSES)}",
            loc,
        ))

    # -- empty SMARTS is NOT permissive --
    if len(family.allowed_warhead_smarts) == 0:
        if family.warhead_rule_status == "calibrated":
            errors.append(_err(
                "RULE_EMPTY_SMARTS_NOT_PERMISSIVE",
                "allowed_warhead_smarts is empty but warhead_rule_status is 'calibrated'",
                loc,
            ))
        elif family.warhead_rule_status == "not_applicable":
            if "SMARTS gate intentionally disabled" not in family.notes:
                warnings.append(_err(
                    "RULE_SMARTS_NOT_APPLICABLE_UNEXPLAINED",
                    "warhead_rule_status is 'not_applicable' but notes lack explanation",
                    loc,
                ))
    elif family.warhead_rule_status in ("pending", "not_applicable"):
        errors.append(_err(
            "RULE_WARHEAD_STATUS_SMARTS_MISMATCH",
            f"allowed_warhead_smarts must be empty when warhead_rule_status is '{family.warhead_rule_status}'",
            loc,
        ))

    # -- calibrated SMARTS requires at least one pattern --
    if family.warhead_rule_status == "calibrated" and len(family.allowed_warhead_smarts) == 0:
        pass  # caught above as RULE_EMPTY_SMARTS_NOT_PERMISSIVE

    # -- geometry_status validity --
    for geom_key in ("bond_length", "protein_side_angle", "ligand_side_angle"):
        status = getattr(family.geometry_status, geom_key)
        if status not in VALID_GEOMETRY_STATUSES:
            errors.append(_err(
                "RULE_INVALID_GEOMETRY_STATUS",
                f"geometry_status.{geom_key} = '{status}' not in {sorted(VALID_GEOMETRY_STATUSES)}",
                loc,
            ))

    # -- geometry range consistency with status --
    geom_map = {
        "bond_length": family.bond_length_range,
        "protein_side_angle": family.protein_side_angle_range,
        "ligand_side_angle": family.ligand_side_angle_range,
    }
    for geom_key, geom_range in geom_map.items():
        status = getattr(family.geometry_status, geom_key)
        has_nulls = geom_range.min is None or geom_range.max is None
        has_values = geom_range.min is not None and geom_range.max is not None

        if status == "calibrated" and has_nulls:
            errors.append(_err(
                "RULE_NULL_GEOMETRY_NOT_PERMISSIVE",
                f"geometry_status.{geom_key} is 'calibrated' but range has null bounds",
                loc,
            ))
        elif status in ("pending", "disabled") and has_values:
            errors.append(_err(
                "RULE_GEOMETRY_STATUS_RANGE_MISMATCH",
                f"geometry_status.{geom_key} is '{status}' but range has numeric bounds",
                loc,
            ))

    # -- anchor_atom_name required --
    if family.anchor_atom_name is None:
        errors.append(_err(
            "RULE_MISSING_ANCHOR_ATOM",
            "anchor_atom_name is missing",
            loc,
        ))
    elif family.anchor_atom_name and family.target_residue_name in VALID_ANCHOR_ATOMS:
        expected_anchor = VALID_ANCHOR_ATOMS[family.target_residue_name]
        if family.anchor_atom_name != expected_anchor:
            warnings.append(_err(
                "RULE_UNEXPECTED_ANCHOR_ATOM",
                f"anchor_atom_name '{family.anchor_atom_name}' differs from default '{expected_anchor}' for {family.target_residue_name}",
                loc,
            ))

    # -- ligand_neighbor_policy required --
    if family.ligand_neighbor_policy is None:
        errors.append(_err(
            "RULE_MISSING_LIGAND_NEIGHBOR_POLICY",
            "ligand_neighbor_policy is missing",
            loc,
        ))
    elif family.ligand_neighbor_policy not in VALID_LIGAND_NEIGHBOR_POLICIES:
        errors.append(_err(
            "RULE_INVALID_LIGAND_NEIGHBOR_POLICY",
            f"ligand_neighbor_policy '{family.ligand_neighbor_policy}' not in {sorted(VALID_LIGAND_NEIGHBOR_POLICIES)}",
            loc,
        ))

    # -- protein_state_requirements required --
    if family.protein_state_requirements is None:
        errors.append(_err(
            "RULE_MISSING_PROTEIN_STATE_REQUIREMENTS",
            "protein_state_requirements is missing",
            loc,
        ))
    else:
        psr = family.protein_state_requirements
        for psr_key in ("target_atom_formal_charge", "target_atom_protonation_state", "explicit_hydrogen_state"):
            val = getattr(psr, psr_key, None)
            if val is None:
                errors.append(_err(
                    "RULE_MISSING_PROTEIN_STATE_FIELD",
                    f"protein_state_requirements.{psr_key} is missing",
                    loc,
                ))
            elif val not in VALID_PROTEIN_STATE_VALUES:
                errors.append(_err(
                    "RULE_INVALID_PROTEIN_STATE_VALUE",
                    f"protein_state_requirements.{psr_key} = '{val}' not in {sorted(VALID_PROTEIN_STATE_VALUES)}",
                    loc,
                ))

    # -- valence_delta required --
    if family.valence_delta is None:
        errors.append(_err(
            "RULE_MISSING_VALENCE_DELTA",
            "valence_delta is missing",
            loc,
        ))
    else:
        vd = family.valence_delta
        if vd.target_atom is None:
            errors.append(_err(
                "RULE_MISSING_VALENCE_DELTA_TARGET",
                "valence_delta.target_atom is missing",
                loc,
            ))
        if vd.ligand_attachment_atom is None:
            errors.append(_err(
                "RULE_MISSING_VALENCE_DELTA_LIGAND",
                "valence_delta.ligand_attachment_atom is missing",
                loc,
            ))

    # -- build per-family report dict --
    report = _family_report_dict(family, errors, warnings)

    return report, errors, warnings


def _family_report_dict(
    family: ReactionFamilyRuleRow,
    errors: list[ContractErrorInfo],
    warnings: list[ContractErrorInfo],
) -> dict:
    """Build an enriched dict representation for the validation report."""
    geom = family.geometry_status
    # Compute gate statuses: 'calibrated', 'pending', or 'disabled'.
    warhead_gate = family.warhead_rule_status

    return {
        "family_id": family.family_id,
        "target_residue_name": family.target_residue_name,
        "target_atom_name": family.target_atom_name,
        "residue_reaction_class": family.residue_reaction_class,
        "warhead_rule_status": family.warhead_rule_status,
        "warhead_gate": warhead_gate,
        "geometry_status": {
            "bond_length": geom.bond_length,
            "protein_side_angle": geom.protein_side_angle,
            "ligand_side_angle": geom.ligand_side_angle,
        },
        "geometry_gate_bond_length": geom.bond_length,
        "geometry_gate_protein_side_angle": geom.protein_side_angle,
        "geometry_gate_ligand_side_angle": geom.ligand_side_angle,
        "anchor_atom_name": family.anchor_atom_name,
        "ligand_neighbor_policy": family.ligand_neighbor_policy,
        "has_protein_state_requirements": family.protein_state_requirements is not None,
        "has_valence_delta": family.valence_delta is not None,
        "notes": family.notes,
    }


# ======================================================================
# dict → typed conversion
# ======================================================================

def _dict_to_table(raw: dict, input_sha256: str = "") -> ReactionFamilyRuleTable:
    version = int(raw.get("version", 1))
    families_raw = raw.get("families", [])
    if not isinstance(families_raw, list):
        raise ValueError("Rule table 'families' must be a list")

    families: list[ReactionFamilyRuleRow] = []
    for item in families_raw:
        if not isinstance(item, dict):
            raise ValueError(f"Rule table family entry must be a dict, got {type(item)}")
        families.append(_dict_to_row(item))

    return ReactionFamilyRuleTable(
        version=version,
        families=tuple(families),
        input_sha256=input_sha256,
    )


def _dict_to_row(d: dict) -> ReactionFamilyRuleRow:
    def _str_list(key: str) -> tuple[str, ...]:
        val = d.get(key, [])
        if isinstance(val, list):
            return tuple(str(v) for v in val)
        return ()

    def _geom_range(key: str, default_unit: str = "angstrom") -> GeometryRange:
        val = d.get(key)
        if isinstance(val, dict):
            return GeometryRange(
                min=_optional_float(val.get("min")),
                max=_optional_float(val.get("max")),
                unit=str(val.get("unit", default_unit)),
            )
        return GeometryRange(None, None, default_unit)

    def _geom_status() -> GeometryStatus:
        val = d.get("geometry_status")
        if isinstance(val, dict):
            return GeometryStatus(
                bond_length=str(val.get("bond_length", "pending")),
                protein_side_angle=str(val.get("protein_side_angle", "pending")),
                ligand_side_angle=str(val.get("ligand_side_angle", "pending")),
            )
        return GeometryStatus("pending", "pending", "pending")

    def _protein_state() -> Optional[ProteinStateRequirements]:
        val = d.get("protein_state_requirements")
        if isinstance(val, dict):
            return ProteinStateRequirements(
                target_atom_formal_charge=str(val.get("target_atom_formal_charge", "")),
                target_atom_protonation_state=str(val.get("target_atom_protonation_state", "")),
                explicit_hydrogen_state=str(val.get("explicit_hydrogen_state", "")),
            )
        return None

    def _valence_delta() -> Optional[ValenceDelta]:
        val = d.get("valence_delta")
        if isinstance(val, dict):
            ta = val.get("target_atom")
            la = val.get("ligand_attachment_atom")
            # Both must be present and numeric; partial is treated as missing.
            if ta is not None and la is not None:
                return ValenceDelta(
                    target_atom=int(ta),
                    ligand_attachment_atom=int(la),
                )
        return None

    return ReactionFamilyRuleRow(
        family_id=str(d.get("family_id", "")),
        target_residue_name=str(d.get("target_residue_name", "")),
        target_atom_name=str(d.get("target_atom_name", "")),
        residue_reaction_class=str(d.get("residue_reaction_class", "")),
        allowed_ligand_attachment_elements=_str_list("allowed_ligand_attachment_elements"),
        allowed_covalent_bond_types=_str_list("allowed_covalent_bond_types"),
        allowed_warhead_smarts=_str_list("allowed_warhead_smarts"),
        warhead_rule_status=str(d.get("warhead_rule_status", "pending")),
        forbidden_warhead_smarts=_str_list("forbidden_warhead_smarts"),
        bond_length_range=_geom_range("bond_length_range"),
        protein_side_angle_range=_geom_range("protein_side_angle_range", "degree"),
        ligand_side_angle_range=_geom_range("ligand_side_angle_range", "degree"),
        geometry_status=_geom_status(),
        anchor_atom_name=_optional_str(d.get("anchor_atom_name")),
        ligand_neighbor_policy=_optional_str(d.get("ligand_neighbor_policy")),
        protein_state_requirements=_protein_state(),
        valence_delta=_valence_delta(),
        notes=str(d.get("notes", "")),
    )


# ======================================================================
# helpers
# ======================================================================

def _optional_float(val: object) -> Optional[float]:
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _optional_str(val: object) -> Optional[str]:
    if val is None:
        return None
    if isinstance(val, (dict, list)):
        return None
    if isinstance(val, str) and val.strip() == "":
        return None
    return str(val)


def _err(code: str, message: str, location: str = "") -> ContractErrorInfo:
    return ContractErrorInfo(
        code=code,
        owner="rules",
        message=message,
        location=location,
    )


def _table_fingerprint(table: ReactionFamilyRuleTable) -> str:
    """Deterministic fingerprint for validation receipt."""
    parts: list[str] = [str(table.version)]
    for f in table.families:
        parts.append(f.family_id)
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


# ======================================================================
# YAML loading (minimal fallback when PyYAML is unavailable)
# ======================================================================

def _load_yaml(path_str: str) -> dict:
    """Load YAML using PyYAML if available; else use a minimal fallback parser.

    The fallback handles the committed fixture format: a JSON-compatible
    YAML subset with flow-style lists, flow-style inline dicts, null,
    integers, quoted strings, comments, and indentation-based nesting.
    """
    try:
        import yaml
        with open(path_str, "r", encoding="utf-8") as fh:
            return yaml.safe_load(fh)
    except ImportError:
        pass

    with open(path_str, "r", encoding="utf-8") as fh:
        return _parse_minimal_yaml(fh.read())


def _parse_minimal_yaml(text: str) -> dict:
    """Parse a minimal YAML subset sufficient for rule table fixtures.

    Handles:
      - Comments (lines starting with #)
      - key: value  (scalar values)
      - key:        (nested block follows on indented lines)
      - - list items with optional inline key: value
      - [a, b, c]   (flow-style sequences)
      - {k: v, ...} (flow-style mappings)
      - null, integers, double-quoted strings, unquoted strings
      - Indentation-based nesting
    """
    lines: list[tuple[int, str]] = []
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        lines.append((indent, stripped))

    root: dict[str, object] = {}
    # stack: (container, indent, key_or_index or None)
    stack: list[
        tuple[
            Union[dict[str, object], list[object]],
            int,
            Optional[Union[str, int]],
        ]
    ] = [
        (root, -1, None)
    ]

    i = 0
    while i < len(lines):
        indent, stripped = lines[i]

        # pop stack until we find a container at a lower indent level
        while len(stack) > 1 and indent <= stack[-1][1]:
            stack.pop()

        container, _, _ = stack[-1]

        if stripped.startswith("- "):
            inner = stripped[2:].strip()

            if inner and ":" in inner and not _is_flow_mapping(inner):
                # - key: value  (mapping list item)
                k, v = _split_kv(inner)
                item: dict[str, object] = {}
                if k:
                    item[k] = _parse_yaml_value(v.strip())
                if isinstance(container, list):
                    container.append(item)
                else:
                    # Container is a dict; the last key pushed needs this list.
                    # We'll create a list and put the item in it
                    _append_to_dict_list(container, item)
                stack.append((item, indent, k))
            else:
                # - value  (scalar or flow-mapping list item)
                val = _parse_yaml_value(inner)
                if isinstance(container, list):
                    container.append(val)
                else:
                    _append_to_dict_list(container, val)
            i += 1

        elif ":" in stripped:
            key, value_text = _split_kv(stripped)
            value_text = value_text.strip()
            if value_text:
                # inline value
                parsed = _parse_yaml_value(value_text)
                if isinstance(container, dict):
                    container[key] = parsed
                elif isinstance(container, list) and len(container) > 0:
                    if isinstance(container[-1], dict):
                        container[-1][key] = parsed
            else:
                # Block value: peek ahead to decide list vs dict.
                peek_i = i + 1
                is_list = False
                while peek_i < len(lines):
                    p_indent, p_stripped = lines[peek_i]
                    if p_indent > indent:
                        is_list = p_stripped.startswith("- ")
                        break
                    peek_i += 1

                if is_list:
                    new_list: list[object] = []
                    if isinstance(container, dict):
                        container[key] = new_list
                    stack.append((new_list, indent, key))
                else:
                    new_dict: dict[str, object] = {}
                    if isinstance(container, dict):
                        container[key] = new_dict
                    stack.append((new_dict, indent, key))
            i += 1

        else:
            i += 1

    return root


def _append_to_dict_list(container: dict[str, object], value: object) -> None:
    """Find or create the list key in a dict container and append."""
    # Walk the stack backwards to find the key that owns the next list
    # This is a heuristic: the last key added to a dict is the list owner.
    # In practice the YAML 'families:' key creates a list.
    for k in reversed(list(container.keys())):
        existing = container[k]
        if isinstance(existing, list):
            existing.append(value)
            return
    # No existing list found; this should not happen with well-formed input.
    raise ValueError("Cannot determine which dict key owns the list item")


def _is_flow_mapping(text: str) -> bool:
    return text.startswith("{") and text.endswith("}")


def _split_kv(text: str) -> tuple[str, str]:
    """Split 'key: value' at the first colon not inside quotes or brackets."""
    depth_brace = 0
    depth_bracket = 0
    in_quote = False
    quote_char = ""
    for idx, ch in enumerate(text):
        if in_quote:
            if ch == quote_char:
                in_quote = False
            continue
        if ch == '"' or ch == "'":
            in_quote = True
            quote_char = ch
            continue
        if ch == "[":
            depth_bracket += 1
        elif ch == "]":
            depth_bracket -= 1
        elif ch == "{":
            depth_brace += 1
        elif ch == "}":
            depth_brace -= 1
        elif ch == ":" and depth_brace == 0 and depth_bracket == 0:
            return text[:idx].strip(), text[idx + 1:].strip()
    return text.strip(), ""


def _parse_yaml_value(text: str) -> object:
    """Parse a scalar, flow-sequence, or flow-mapping YAML value."""
    text = text.strip()
    if text == "null" or text == "~":
        return None
    if text == "true":
        return True
    if text == "false":
        return False
    if _is_flow_mapping(text):
        return _parse_flow_mapping(text)
    if text.startswith("[") and text.endswith("]"):
        return _parse_flow_sequence(text)
    if (text.startswith('"') and text.endswith('"')) or \
       (text.startswith("'") and text.endswith("'")):
        return text[1:-1]
    try:
        if "." in text or "e" in text.lower():
            return float(text)
        return int(text)
    except ValueError:
        return text


def _parse_flow_sequence(text: str) -> list[object]:
    """Parse a flow-style YAML sequence: [a, b, c]."""
    inner = text[1:-1].strip()
    if not inner:
        return []
    items = _split_flow_items(inner)
    return [_parse_yaml_value(item) for item in items]


def _parse_flow_mapping(text: str) -> dict[str, object]:
    """Parse a flow-style YAML mapping: {k: v, k2: v2}."""
    inner = text[1:-1].strip()
    if not inner:
        return {}
    result: dict[str, object] = {}
    items = _split_flow_items(inner)
    for item in items:
        k, v = _split_kv(item)
        result[k.strip()] = _parse_yaml_value(v.strip())
    return result


def _split_flow_items(text: str) -> list[str]:
    """Split comma-separated items respecting nested brackets."""
    items: list[str] = []
    depth_brace = 0
    depth_bracket = 0
    current: list[str] = []
    for ch in text:
        if ch == "[":
            depth_bracket += 1
        elif ch == "]":
            depth_bracket -= 1
        elif ch == "{":
            depth_brace += 1
        elif ch == "}":
            depth_brace -= 1
        elif ch == "," and depth_brace == 0 and depth_bracket == 0:
            items.append("".join(current).strip())
            current = []
            continue
        current.append(ch)
    if current:
        items.append("".join(current).strip())
    return items
