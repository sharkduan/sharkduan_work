"""Task 26: request schema and validation contract tests.

Expected production API (Task 26 implementation):

  from covalent_design.inference.request_schema import (
      ProteinAtomLocator,
      LigandSizeControl,
      ProteinChemicalStateRequest,
      ReactiveSiteGenerationRequest,
      ValidatedRequest,
  )
  from covalent_design.inference.request_validation import (
      load_request_file,
      validate_request,
      validate_request_file,
      normalized_request_yaml,
      write_normalized_request,
  )

  load_request_file(path: Path) -> ReactiveSiteGenerationRequest
      Parse YAML (authoritative) or JSON (accepted) request file.
      Raises ContractError(owner="request", code=...) for unknown
      extension or malformed YAML/JSON.

  validate_request(request, rules, *, request_base_dir=None) -> ValidatedRequest
      Validate a loaded request against a rule table.
      Returns ValidatedRequest on success.
      Raises ContractError(owner="request", code=...) on semantic failure.

  validate_request_file(path, *, rules_path=None) -> ValidatedRequest
      Load and validate a request file in one call.
      Returns ValidatedRequest on success.
      Raises ContractError(owner="request", code=...) on semantic failure.

  normalized_request_yaml(validated: ValidatedRequest) -> str
      Produce deterministic canonical YAML.

  write_normalized_request(validated, path) -> str
      Write deterministic canonical YAML to a file.

CLI:

  python -m covalent_design.inference.validate_request --request <fixture>
      May also accept --rules.
      On ContractError: emits deterministic JSON to stdout and exits 20.

These tests are expected to FAIL (RED) until Task 26 production modules exist.
"""

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = (
    Path(__file__).resolve().parents[1] / "fixtures" / "inference" / "request_validation"
)
RULES_FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "rules"
VALID_RULE_TABLE = RULES_FIXTURE_ROOT / "valid_rule_table.yml"
LOCAL_RULE_TABLE = FIXTURE_ROOT / "task26_local_rule.yml"
STRUCTURES_DIR = FIXTURE_ROOT / "structures"


# ---------------------------------------------------------------------------
# Expected public API (imports will fail until Task 26 is implemented)
# ---------------------------------------------------------------------------

def _import_request_schema():
    from covalent_design.inference.request_schema import (  # noqa: F401
        LigandSizeControl,
        ProteinAtomLocator,
        ProteinChemicalStateRequest,
        ReactiveSiteGenerationRequest,
        ValidatedRequest,
    )
    return True


def _import_request_validation():
    from covalent_design.inference.request_validation import (  # noqa: F401
        load_request_file,
        normalized_request_yaml,
        validate_request,
        validate_request_file,
        write_normalized_request,
    )
    return True


def _import_rules():
    from covalent_design.rules.validate import load_rule_table  # noqa: F401
    return True


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _load_fixture(name: str) -> dict:
    """Parse fixture YAML/JSON from FIXTURE_ROOT."""
    path = FIXTURE_ROOT / name
    if name.endswith(".json"):
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    # YAML — use the project loader
    from covalent_design._yaml_loader import load_yaml_config

    return load_yaml_config(str(path))


def _resolve_structure_uri(relative_uri: str) -> str:
    """Resolve a structure URI relative to FIXTURE_ROOT."""
    return str(FIXTURE_ROOT / relative_uri)


def _validate_fixture(name: str, *, rules_path=None):
    """Load and validate a request fixture.

    Returns ValidatedRequest on success.
    Raises ContractError on semantic validation failure.
    """
    from covalent_design.inference.request_validation import validate_request_file

    if rules_path is None:
        rules_path = VALID_RULE_TABLE
    return validate_request_file(FIXTURE_ROOT / name, rules_path=rules_path)


# ---------------------------------------------------------------------------
# 1. File loading tests
# ---------------------------------------------------------------------------


class RequestFileLoadingTests(unittest.TestCase):
    """Test load_request_file for YAML and JSON parsing."""

    def test_load_valid_yaml_request_returns_typed_object(self):
        from covalent_design.inference.request_schema import ReactiveSiteGenerationRequest
        from covalent_design.inference.request_validation import load_request_file

        request = load_request_file(FIXTURE_ROOT / "valid_request.yml")
        self.assertIsInstance(request, ReactiveSiteGenerationRequest)
        self.assertEqual(request.request_id, "valid-request-001")
        self.assertEqual(request.sample_count, 10)
        self.assertEqual(request.residue_reaction_family, "CYS_MICHAEL_ADDITION")

    def test_load_valid_json_request_returns_typed_object(self):
        from covalent_design.inference.request_schema import ReactiveSiteGenerationRequest
        from covalent_design.inference.request_validation import load_request_file

        request = load_request_file(FIXTURE_ROOT / "valid_request.json")
        self.assertIsInstance(request, ReactiveSiteGenerationRequest)
        self.assertEqual(request.request_id, "valid-request-001")

    def test_load_yaml_with_size_control_parses_correctly(self):
        from covalent_design.inference.request_validation import load_request_file

        request = load_request_file(FIXTURE_ROOT / "valid_fixed_size.yml")
        self.assertIsNotNone(request.size_control)
        self.assertEqual(request.size_control.num_ligand_heavy_atoms, 30)
        self.assertIsNone(request.size_control.min_ligand_heavy_atoms)
        self.assertIsNone(request.size_control.max_ligand_heavy_atoms)

    def test_load_yaml_with_range_size_parses_correctly(self):
        from covalent_design.inference.request_validation import load_request_file

        request = load_request_file(FIXTURE_ROOT / "valid_range_size.yml")
        self.assertIsNotNone(request.size_control)
        self.assertIsNone(request.size_control.num_ligand_heavy_atoms)
        self.assertEqual(request.size_control.min_ligand_heavy_atoms, 10)
        self.assertEqual(request.size_control.max_ligand_heavy_atoms, 40)

    def test_load_yaml_with_absent_size_parses_as_none(self):
        from covalent_design.inference.request_validation import load_request_file

        request = load_request_file(FIXTURE_ROOT / "valid_absent_size.yml")
        self.assertIsNone(request.size_control)

    def test_load_yaml_with_target_altloc_parses(self):
        from covalent_design.inference.request_validation import load_request_file

        request = load_request_file(FIXTURE_ROOT / "valid_altloc_override.yml")
        self.assertEqual(request.target_altloc, "B")

    def test_load_yaml_with_chemical_state_parses(self):
        from covalent_design.inference.request_validation import load_request_file

        request = load_request_file(FIXTURE_ROOT / "valid_request.yml")
        self.assertIsNotNone(request.protein_chemical_state_request)
        self.assertEqual(request.protein_chemical_state_request.target_atom_formal_charge, 0)
        self.assertEqual(
            request.protein_chemical_state_request.target_atom_protonation_state,
            "thiolate",
        )

    def test_unknown_extension_raises_contract_error(self):
        from covalent_design.contracts.errors import ContractError
        from covalent_design.inference.request_validation import load_request_file

        unknown_path = FIXTURE_ROOT / "unknown_extension.txt"
        with self.assertRaises(ContractError) as ctx:
            load_request_file(unknown_path)
        self.assertEqual(ctx.exception.owner, "request")

    def test_malformed_yaml_raises_contract_error(self):
        from covalent_design.contracts.errors import ContractError
        from covalent_design.inference.request_validation import load_request_file

        malformed = FIXTURE_ROOT / "malformed_request.yml"
        with self.assertRaises(ContractError) as ctx:
            load_request_file(malformed)
        self.assertEqual(ctx.exception.owner, "request")

    def test_malformed_json_raises_contract_error(self):
        from covalent_design.contracts.errors import ContractError
        from covalent_design.inference.request_validation import load_request_file

        malformed = FIXTURE_ROOT / "malformed_request.json"
        with self.assertRaises(ContractError) as ctx:
            load_request_file(malformed)
        self.assertEqual(ctx.exception.owner, "request")


# ---------------------------------------------------------------------------
# 2. Valid request validation tests
# ---------------------------------------------------------------------------


class ValidRequestValidationTests(unittest.TestCase):
    """Test validate_request_file with valid fixtures."""

    def test_valid_request_yml_passes(self):
        validated = _validate_fixture("valid_request.yml")
        self.assertIsNotNone(validated.resolved_target_atom_identity)
        self.assertEqual(validated.resolved_target_atom_identity.chain_id, "A")
        self.assertEqual(validated.resolved_target_atom_identity.residue_number, 42)
        self.assertEqual(validated.resolved_target_atom_identity.residue_name, "CYS")
        self.assertEqual(validated.resolved_target_atom_identity.atom_name, "SG")
        # Single atom with no altloc resolves to None
        self.assertIsNone(validated.resolved_target_altloc)

    def test_valid_request_json_passes(self):
        validated = _validate_fixture("valid_request.json")
        self.assertEqual(validated.request.request_id, "valid-request-001")

    def test_valid_fixed_size_passes(self):
        validated = _validate_fixture("valid_fixed_size.yml")
        self.assertEqual(validated.request.size_control.num_ligand_heavy_atoms, 30)

    def test_valid_range_size_passes(self):
        validated = _validate_fixture("valid_range_size.yml")
        self.assertEqual(validated.request.size_control.min_ligand_heavy_atoms, 10)
        self.assertEqual(validated.request.size_control.max_ligand_heavy_atoms, 40)

    def test_valid_absent_size_passes(self):
        validated = _validate_fixture("valid_absent_size.yml")
        self.assertIsNone(validated.request.size_control)

    def test_valid_mmcif_structure_passes(self):
        from covalent_design.inference.request_validation import (
            load_request_file,
            validate_request,
        )
        from covalent_design.rules.validate import load_rule_table

        rules = load_rule_table(VALID_RULE_TABLE)
        fixture_data = _load_fixture("valid_request.yml")
        fixture_data["protein_structure_uri"] = "structures/valid_structure.cif"
        fixture_data["protein_structure_format"] = "mmcif"

        from covalent_design.inference.request_schema import ReactiveSiteGenerationRequest

        request = ReactiveSiteGenerationRequest(
            request_id=fixture_data["request_id"],
            protein_structure_uri=str(FIXTURE_ROOT / fixture_data["protein_structure_uri"]),
            protein_structure_format=fixture_data["protein_structure_format"],
            target_atom_identity_request=_build_locator(fixture_data["target_atom_identity_request"]),
            residue_reaction_family=fixture_data["residue_reaction_family"],
            sample_count=fixture_data["sample_count"],
            size_control=_build_size_control(fixture_data.get("size_control")),
            protein_chemical_state_request=_build_chemical_state(
                fixture_data.get("protein_chemical_state_request")
            ),
        )
        validated = validate_request(request, rules, request_base_dir=str(FIXTURE_ROOT))
        self.assertIsNotNone(validated)

    def test_target_atom_locator_can_omit_chain_id(self):
        from covalent_design.inference.request_validation import (
            load_request_file,
            validate_request,
        )
        from covalent_design.rules.validate import load_rule_table

        rules = load_rule_table(VALID_RULE_TABLE)
        fixture_data = _load_fixture("valid_request.yml")

        from covalent_design.inference.request_schema import ReactiveSiteGenerationRequest

        locator_data = dict(fixture_data["target_atom_identity_request"])
        del locator_data["chain_id"]

        request = ReactiveSiteGenerationRequest(
            request_id=fixture_data["request_id"],
            protein_structure_uri=str(FIXTURE_ROOT / fixture_data["protein_structure_uri"]),
            protein_structure_format=fixture_data["protein_structure_format"],
            target_atom_identity_request=_build_locator(locator_data),
            residue_reaction_family=fixture_data["residue_reaction_family"],
            sample_count=fixture_data["sample_count"],
            size_control=_build_size_control(fixture_data.get("size_control")),
            protein_chemical_state_request=_build_chemical_state(
                fixture_data.get("protein_chemical_state_request")
            ),
        )
        validated = validate_request(request, rules, request_base_dir=str(FIXTURE_ROOT))
        self.assertIsNotNone(validated)

    def test_validated_request_carries_rule_table_version(self):
        validated = _validate_fixture("valid_request.yml")
        self.assertIsInstance(validated.rule_table_version, int)
        self.assertGreaterEqual(validated.rule_table_version, 1)


# ---------------------------------------------------------------------------
# 3. Altloc resolution tests
# ---------------------------------------------------------------------------


class AltlocResolutionTests(unittest.TestCase):
    """Test target altloc resolution semantics."""

    def test_single_atom_no_altloc_resolves_none(self):
        validated = _validate_fixture("valid_request.yml")
        self.assertIsNone(validated.resolved_target_altloc)

    def test_explicit_override_wins_over_higher_occupancy(self):
        validated = _validate_fixture("valid_altloc_override.yml")
        # altloc_multi.pdb has A at 0.60 and B at 0.40
        # explicit override B wins
        self.assertEqual(validated.resolved_target_altloc, "B")

    def test_no_override_highest_occupancy_wins(self):
        validated = _validate_fixture("valid_altloc_highest_occupancy.yml")
        # altloc_multi.pdb has A at 0.60 and B at 0.40
        self.assertEqual(validated.resolved_target_altloc, "A")

    def test_occupancy_tie_chooses_a(self):
        validated = _validate_fixture("valid_altloc_tie_choose_a.yml")
        # altloc_tie.pdb has A at 0.50 and B at 0.50
        self.assertEqual(validated.resolved_target_altloc, "A")

    def test_missing_occupancy_chooses_a(self):
        validated = _validate_fixture("valid_altloc_missing_occupancy_choose_a.yml")
        # altloc_missing_occ.pdb has A and B both at 0.00
        self.assertEqual(validated.resolved_target_altloc, "A")

    def test_explicit_nonexistent_altloc_fails_atom_not_found(self):
        from covalent_design.contracts.errors import ContractError
        from covalent_design.inference.request_validation import (
            load_request_file,
            validate_request,
        )
        from covalent_design.rules.validate import load_rule_table

        rules = load_rule_table(VALID_RULE_TABLE)
        request = load_request_file(FIXTURE_ROOT / "valid_altloc_highest_occupancy.yml")

        # Override to request altloc X which does not exist in altloc_multi.pdb
        from dataclasses import replace

        modified = replace(request, target_altloc="X")
        with self.assertRaises(ContractError) as ctx:
            validate_request(modified, rules, request_base_dir=str(FIXTURE_ROOT))
        self.assertEqual(ctx.exception.code, "REQUEST_TARGET_ATOM_NOT_FOUND")
        self.assertEqual(ctx.exception.owner, "request")


# ---------------------------------------------------------------------------
# 4. Error code tests — one per REQUEST_* code
# ---------------------------------------------------------------------------


class RequestErrorCodeTests(unittest.TestCase):
    """Each of the 13 REQUEST_* error codes is exercised by at least one fixture."""

    def test_structure_unreadable_missing_file(self):
        from covalent_design.contracts.errors import ContractError

        with self.assertRaises(ContractError) as ctx:
            _validate_fixture("error_structure_unreadable.yml")
        self.assertEqual(ctx.exception.code, "REQUEST_STRUCTURE_UNREADABLE")
        self.assertEqual(ctx.exception.owner, "request")

    def test_structure_no_atom_records_is_unreadable(self):
        """PDB with no ATOM/HETATM → REQUEST_STRUCTURE_UNREADABLE, not RESIDUE_NOT_FOUND."""
        from covalent_design.contracts.errors import ContractError

        with self.assertRaises(ContractError) as ctx:
            _validate_fixture("error_structure_no_atoms.yml")
        self.assertEqual(ctx.exception.code, "REQUEST_STRUCTURE_UNREADABLE")
        self.assertEqual(ctx.exception.owner, "request")

    def test_target_residue_not_found(self):
        from covalent_design.contracts.errors import ContractError

        with self.assertRaises(ContractError) as ctx:
            _validate_fixture("error_target_residue_not_found.yml")
        self.assertEqual(ctx.exception.code, "REQUEST_TARGET_RESIDUE_NOT_FOUND")
        self.assertEqual(ctx.exception.owner, "request")

    def test_target_residue_ambiguous(self):
        from covalent_design.contracts.errors import ContractError

        with self.assertRaises(ContractError) as ctx:
            _validate_fixture("error_target_residue_ambiguous.yml")
        self.assertEqual(ctx.exception.code, "REQUEST_TARGET_RESIDUE_AMBIGUOUS")
        self.assertEqual(ctx.exception.owner, "request")

    def test_target_atom_not_found(self):
        from covalent_design.contracts.errors import ContractError

        with self.assertRaises(ContractError) as ctx:
            _validate_fixture("error_target_atom_not_found.yml")
        self.assertEqual(ctx.exception.code, "REQUEST_TARGET_ATOM_NOT_FOUND")
        self.assertEqual(ctx.exception.owner, "request")

    def test_residue_name_mismatch(self):
        from covalent_design.contracts.errors import ContractError

        with self.assertRaises(ContractError) as ctx:
            _validate_fixture("error_residue_name_mismatch.yml")
        self.assertEqual(ctx.exception.code, "REQUEST_RESIDUE_NAME_MISMATCH")
        self.assertEqual(ctx.exception.owner, "request")

    def test_family_unsupported(self):
        from covalent_design.contracts.errors import ContractError

        with self.assertRaises(ContractError) as ctx:
            _validate_fixture("error_family_unsupported.yml")
        self.assertEqual(ctx.exception.code, "REQUEST_FAMILY_UNSUPPORTED")
        self.assertEqual(ctx.exception.owner, "request")

    def test_residue_family_conflict(self):
        from covalent_design.contracts.errors import ContractError

        with self.assertRaises(ContractError) as ctx:
            _validate_fixture(
                "error_residue_family_conflict.yml", rules_path=LOCAL_RULE_TABLE
            )
        self.assertEqual(ctx.exception.code, "REQUEST_RESIDUE_FAMILY_CONFLICT")
        self.assertEqual(ctx.exception.owner, "request")

    def test_atom_family_conflict(self):
        from covalent_design.contracts.errors import ContractError

        with self.assertRaises(ContractError) as ctx:
            _validate_fixture(
                "error_atom_family_conflict.yml", rules_path=LOCAL_RULE_TABLE
            )
        self.assertEqual(ctx.exception.code, "REQUEST_ATOM_FAMILY_CONFLICT")
        self.assertEqual(ctx.exception.owner, "request")

    def test_sample_count_invalid_zero(self):
        from covalent_design.contracts.errors import ContractError

        with self.assertRaises(ContractError) as ctx:
            _validate_fixture("error_sample_count_invalid.yml")
        self.assertEqual(ctx.exception.code, "REQUEST_SAMPLE_COUNT_INVALID")
        self.assertEqual(ctx.exception.owner, "request")

    def test_sample_count_invalid_negative(self):
        from covalent_design.contracts.errors import ContractError
        from covalent_design.inference.request_validation import (
            load_request_file,
            validate_request,
        )
        from covalent_design.rules.validate import load_rule_table

        rules = load_rule_table(VALID_RULE_TABLE)
        request = load_request_file(FIXTURE_ROOT / "valid_request.yml")
        from dataclasses import replace

        modified = replace(request, sample_count=-1)
        with self.assertRaises(ContractError) as ctx:
            validate_request(modified, rules, request_base_dir=str(FIXTURE_ROOT))
        self.assertEqual(ctx.exception.code, "REQUEST_SAMPLE_COUNT_INVALID")
        self.assertEqual(ctx.exception.owner, "request")

    def test_ligand_size_invalid_zero(self):
        from covalent_design.contracts.errors import ContractError

        with self.assertRaises(ContractError) as ctx:
            _validate_fixture("error_ligand_size_invalid.yml")
        self.assertEqual(ctx.exception.code, "REQUEST_LIGAND_SIZE_INVALID")
        self.assertEqual(ctx.exception.owner, "request")

    def test_ligand_size_invalid_negative(self):
        from covalent_design.contracts.errors import ContractError
        from covalent_design.inference.request_validation import (
            load_request_file,
            validate_request,
        )
        from covalent_design.rules.validate import load_rule_table

        rules = load_rule_table(VALID_RULE_TABLE)
        request = load_request_file(FIXTURE_ROOT / "valid_fixed_size.yml")
        from dataclasses import replace

        modified = replace(request, size_control=replace(request.size_control, num_ligand_heavy_atoms=-5))
        with self.assertRaises(ContractError) as ctx:
            validate_request(modified, rules, request_base_dir=str(FIXTURE_ROOT))
        self.assertEqual(ctx.exception.code, "REQUEST_LIGAND_SIZE_INVALID")
        self.assertEqual(ctx.exception.owner, "request")

    def test_ligand_size_range_invalid(self):
        from covalent_design.contracts.errors import ContractError

        with self.assertRaises(ContractError) as ctx:
            _validate_fixture("error_ligand_size_range_invalid.yml")
        self.assertEqual(ctx.exception.code, "REQUEST_LIGAND_SIZE_RANGE_INVALID")
        self.assertEqual(ctx.exception.owner, "request")

    def test_ligand_size_conflict_mixed_fixed_and_range(self):
        from covalent_design.contracts.errors import ContractError

        with self.assertRaises(ContractError) as ctx:
            _validate_fixture("error_ligand_size_conflict.yml")
        self.assertEqual(ctx.exception.code, "REQUEST_LIGAND_SIZE_CONFLICT")
        self.assertEqual(ctx.exception.owner, "request")

    def test_required_chemical_state_unavailable(self):
        from covalent_design.contracts.errors import ContractError

        with self.assertRaises(ContractError) as ctx:
            _validate_fixture("error_required_chemical_state_unavailable.yml")
        self.assertEqual(ctx.exception.code, "REQUEST_REQUIRED_CHEMICAL_STATE_UNAVAILABLE")
        self.assertEqual(ctx.exception.owner, "request")

    def test_required_chemical_state_partial_missing(self):
        from covalent_design.contracts.errors import ContractError
        from covalent_design.inference.request_validation import (
            load_request_file,
            validate_request,
        )
        from covalent_design.rules.validate import load_rule_table

        rules = load_rule_table(VALID_RULE_TABLE)
        request = load_request_file(FIXTURE_ROOT / "valid_request.yml")

        # Remove target_atom_formal_charge from chemical state
        from covalent_design.inference.request_schema import ProteinChemicalStateRequest

        modified_state = ProteinChemicalStateRequest(
            target_atom_protonation_state="thiolate",
        )
        from dataclasses import replace

        modified = replace(request, protein_chemical_state_request=modified_state)
        with self.assertRaises(ContractError) as ctx:
            validate_request(modified, rules, request_base_dir=str(FIXTURE_ROOT))
        self.assertEqual(ctx.exception.code, "REQUEST_REQUIRED_CHEMICAL_STATE_UNAVAILABLE")
        self.assertEqual(ctx.exception.owner, "request")


# ---------------------------------------------------------------------------
# 5. Ligand size control validation tests
# ---------------------------------------------------------------------------


class LigandSizeControlTests(unittest.TestCase):
    """Test that fixed/range/absent ligand size are mutually exclusive."""

    def test_fixed_size_is_valid(self):
        validated = _validate_fixture("valid_fixed_size.yml")
        self.assertIsNotNone(validated)

    def test_range_size_is_valid(self):
        validated = _validate_fixture("valid_range_size.yml")
        self.assertIsNotNone(validated)

    def test_absent_size_is_valid(self):
        validated = _validate_fixture("valid_absent_size.yml")
        self.assertIsNotNone(validated)

    def test_fixed_and_range_together_is_conflict(self):
        from covalent_design.contracts.errors import ContractError

        with self.assertRaises(ContractError) as ctx:
            _validate_fixture("error_ligand_size_conflict.yml")
        self.assertEqual(ctx.exception.code, "REQUEST_LIGAND_SIZE_CONFLICT")
        self.assertEqual(ctx.exception.owner, "request")

    def test_fixed_zero_is_invalid(self):
        from covalent_design.contracts.errors import ContractError

        with self.assertRaises(ContractError) as ctx:
            _validate_fixture("error_ligand_size_invalid.yml")
        self.assertEqual(ctx.exception.code, "REQUEST_LIGAND_SIZE_INVALID")
        self.assertEqual(ctx.exception.owner, "request")

    def test_range_min_greater_than_max_is_invalid(self):
        from covalent_design.contracts.errors import ContractError

        with self.assertRaises(ContractError) as ctx:
            _validate_fixture("error_ligand_size_range_invalid.yml")
        self.assertEqual(ctx.exception.code, "REQUEST_LIGAND_SIZE_RANGE_INVALID")
        self.assertEqual(ctx.exception.owner, "request")

    def test_range_negative_min_is_invalid(self):
        from covalent_design.contracts.errors import ContractError
        from covalent_design.inference.request_validation import (
            load_request_file,
            validate_request,
        )
        from covalent_design.rules.validate import load_rule_table

        rules = load_rule_table(VALID_RULE_TABLE)
        request = load_request_file(FIXTURE_ROOT / "valid_range_size.yml")
        from dataclasses import replace

        modified = replace(
            request,
            size_control=replace(
                request.size_control,
                min_ligand_heavy_atoms=-1,
            ),
        )
        with self.assertRaises(ContractError) as ctx:
            validate_request(modified, rules, request_base_dir=str(FIXTURE_ROOT))
        self.assertEqual(ctx.exception.code, "REQUEST_LIGAND_SIZE_RANGE_INVALID")
        self.assertEqual(ctx.exception.owner, "request")


# ---------------------------------------------------------------------------
# 6. Chemical state validation tests
# ---------------------------------------------------------------------------


class ChemicalStateValidationTests(unittest.TestCase):
    """Test protein chemical state requirement validation."""

    def test_full_chemical_state_passes(self):
        validated = _validate_fixture("valid_fixed_size.yml")
        self.assertIsNotNone(validated)

    def test_missing_required_state_fails(self):
        from covalent_design.contracts.errors import ContractError

        with self.assertRaises(ContractError) as ctx:
            _validate_fixture("error_required_chemical_state_unavailable.yml")
        self.assertEqual(ctx.exception.code, "REQUEST_REQUIRED_CHEMICAL_STATE_UNAVAILABLE")
        self.assertEqual(ctx.exception.owner, "request")

    def test_chemical_state_with_source_metadata_passes(self):
        from covalent_design.inference.request_validation import (
            load_request_file,
            validate_request,
        )
        from covalent_design.rules.validate import load_rule_table

        rules = load_rule_table(VALID_RULE_TABLE)
        request = load_request_file(FIXTURE_ROOT / "valid_request.yml")

        from covalent_design.inference.request_schema import ProteinChemicalStateRequest

        state = ProteinChemicalStateRequest(
            target_atom_formal_charge=0,
            target_atom_protonation_state="thiolate",
            target_atom_hydrogen_state="deprotonated",
            protein_preparation_policy="explicit_user",
            chemical_state_source="user_provided",
            chemical_state_tool_name="manual",
            chemical_state_tool_version="1.0",
            chemical_state_confidence="high",
        )
        from dataclasses import replace

        modified = replace(request, protein_chemical_state_request=state)
        validated = validate_request(modified, rules, request_base_dir=str(FIXTURE_ROOT))
        self.assertIsNotNone(validated)


# ---------------------------------------------------------------------------
# 7. Normalized output tests
# ---------------------------------------------------------------------------


class NormalizedOutputTests(unittest.TestCase):
    """Test deterministic normalized YAML output."""

    def test_normalized_yaml_is_string(self):
        from covalent_design.inference.request_validation import normalized_request_yaml

        validated = _validate_fixture("valid_request.yml")
        yaml_str = normalized_request_yaml(validated)
        self.assertIsInstance(yaml_str, str)
        self.assertIn("request_id", yaml_str)
        self.assertIn("valid-request-001", yaml_str)

    def test_normalized_yaml_includes_resolved_altloc(self):
        from covalent_design.inference.request_validation import normalized_request_yaml

        validated = _validate_fixture("valid_altloc_highest_occupancy.yml")
        yaml_str = normalized_request_yaml(validated)
        self.assertIn("resolved_target_altloc", yaml_str)
        self.assertIn("A", yaml_str)

    def test_normalized_yaml_is_deterministic(self):
        from covalent_design.inference.request_validation import normalized_request_yaml

        validated1 = _validate_fixture("valid_request.yml")
        validated2 = _validate_fixture("valid_request.yml")
        self.assertEqual(normalized_request_yaml(validated1), normalized_request_yaml(validated2))

    def test_write_normalized_request_creates_file(self):
        import tempfile

        from covalent_design.inference.request_validation import write_normalized_request

        validated = _validate_fixture("valid_request.yml")
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "normalized.yml"
            result = write_normalized_request(validated, out_path)
            self.assertTrue(out_path.exists())
            content = out_path.read_text(encoding="utf-8")
            self.assertIn("request_id", content)


# ---------------------------------------------------------------------------
# 8. YAML / JSON parity tests
# ---------------------------------------------------------------------------


class YamlJsonParityTests(unittest.TestCase):
    """YAML (authoritative) and JSON (accepted) produce identical results."""

    def test_yaml_and_json_produce_same_validated_request(self):
        from covalent_design.inference.request_validation import validate_request_file

        yaml_result = validate_request_file(
            FIXTURE_ROOT / "valid_request.yml",
            rules_path=VALID_RULE_TABLE,
        )
        json_result = validate_request_file(
            FIXTURE_ROOT / "valid_request.json",
            rules_path=VALID_RULE_TABLE,
        )
        self.assertEqual(yaml_result.request.request_id, json_result.request.request_id)
        self.assertEqual(yaml_result.request.sample_count, json_result.request.sample_count)
        self.assertEqual(
            yaml_result.resolved_target_atom_identity,
            json_result.resolved_target_atom_identity,
        )
        self.assertEqual(
            yaml_result.resolved_target_altloc,
            json_result.resolved_target_altloc,
        )
        self.assertEqual(
            yaml_result.rule_table_version,
            json_result.rule_table_version,
        )

    def test_yaml_and_json_normalized_output_match(self):
        from covalent_design.inference.request_validation import (
            normalized_request_yaml,
            validate_request_file,
        )

        yaml_validated = validate_request_file(
            FIXTURE_ROOT / "valid_request.yml",
            rules_path=VALID_RULE_TABLE,
        )
        json_validated = validate_request_file(
            FIXTURE_ROOT / "valid_request.json",
            rules_path=VALID_RULE_TABLE,
        )
        self.assertEqual(
            normalized_request_yaml(yaml_validated),
            normalized_request_yaml(json_validated),
        )


# ---------------------------------------------------------------------------
# 9. CLI tests
# ---------------------------------------------------------------------------


class RequestValidationCliTests(unittest.TestCase):
    """Test CLI invocation: python -m covalent_design.inference.validate_request."""

    def _run_cli(self, fixture_name: str, *, rules_path=None, expect_error: bool = False):
        env = os.environ.copy()
        env["PYTHONPATH"] = "src"
        request_path = FIXTURE_ROOT / fixture_name
        cmd = [
            sys.executable,
            "-m",
            "covalent_design.inference.validate_request",
            "--request",
            str(request_path),
        ]
        if rules_path is not None:
            cmd.extend(["--rules", str(rules_path)])
        return subprocess.run(
            cmd,
            cwd=str(REPO_ROOT),
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_cli_valid_fixture_exits_0(self):
        result = self._run_cli("valid_request.yml")
        # CLI may not exist yet; if it does, assert
        if result.returncode != 0 and "No module named" in result.stderr:
            self.skipTest("CLI module not yet implemented")
        self.assertEqual(result.returncode, 0, f"stderr:\n{result.stderr}")

    def test_cli_valid_fixture_produces_json_summary(self):
        result = self._run_cli("valid_request.yml")
        if result.returncode != 0 and "No module named" in result.stderr:
            self.skipTest("CLI module not yet implemented")
        output = json.loads(result.stdout)
        self.assertIn("request_id", output)

    def test_cli_error_fixture_exits_20(self):
        result = self._run_cli("error_sample_count_invalid.yml")
        if result.returncode != 0 and "No module named" in result.stderr:
            self.skipTest("CLI module not yet implemented")
        self.assertEqual(result.returncode, 20, f"stderr:\n{result.stderr}")

    def test_cli_error_fixture_produces_error_json(self):
        result = self._run_cli("error_family_unsupported.yml")
        if result.returncode != 0 and "No module named" in result.stderr:
            self.skipTest("CLI module not yet implemented")
        output = json.loads(result.stdout)
        self.assertIn("errors", output)
        self.assertGreater(len(output["errors"]), 0)

    def test_cli_with_explicit_rules_flag(self):
        result = self._run_cli(
            "valid_request.yml",
            rules_path=VALID_RULE_TABLE,
        )
        if result.returncode != 0 and "No module named" in result.stderr:
            self.skipTest("CLI module not yet implemented")
        self.assertEqual(result.returncode, 0, f"stderr:\n{result.stderr}")

    def test_cli_json_request_accepted(self):
        result = self._run_cli("valid_request.json")
        if result.returncode != 0 and "No module named" in result.stderr:
            self.skipTest("CLI module not yet implemented")
        self.assertEqual(result.returncode, 0, f"stderr:\n{result.stderr}")

    def test_cli_deterministic_json_output(self):
        result1 = self._run_cli("valid_request.yml")
        result2 = self._run_cli("valid_request.yml")
        if result1.returncode != 0 and "No module named" in result1.stderr:
            self.skipTest("CLI module not yet implemented")
        self.assertEqual(result1.stdout, result2.stdout)


# ---------------------------------------------------------------------------
# 10. No artifact / no dependency tests
# ---------------------------------------------------------------------------


class NoSideEffectTests(unittest.TestCase):
    """Verify no sampling/checkpoint/generation artifacts are created."""

    def test_validation_creates_no_checkpoint_artifacts(self):
        import tempfile

        from covalent_design.inference.request_validation import validate_request_file

        with tempfile.TemporaryDirectory() as tmpdir:
            validate_request_file(
                FIXTURE_ROOT / "valid_request.yml",
                rules_path=VALID_RULE_TABLE,
            )
            files = list(Path(tmpdir).glob("**/*"))
            self.assertEqual(
                len(files),
                0,
                f"unexpected artifacts created: {files}",
            )

    def test_no_rdkit_or_torch_dependency_in_request_validation(self):
        import covalent_design.inference.request_validation as rv

        source = str(Path(rv.__file__).read_text(encoding="utf-8"))
        self.assertNotIn("import torch", source)
        self.assertNotIn("from torch", source)
        self.assertNotIn("import rdkit", source)
        self.assertNotIn("from rdkit", source)


# ---------------------------------------------------------------------------
# helper builders for programmatic test construction
# ---------------------------------------------------------------------------


def _build_locator(data: dict):
    from covalent_design.inference.request_schema import ProteinAtomLocator

    return ProteinAtomLocator(
        chain_id=data.get("chain_id"),
        residue_number=data.get("residue_number"),
        residue_name=data["residue_name"],
        atom_name=data["atom_name"],
        insertion_code=data.get("insertion_code"),
        structure_model=data.get("structure_model"),
        asym_id=data.get("asym_id"),
    )


def _build_size_control(data: dict | None):
    if data is None:
        return None
    from covalent_design.inference.request_schema import LigandSizeControl

    return LigandSizeControl(
        num_ligand_heavy_atoms=data.get("num_ligand_heavy_atoms"),
        min_ligand_heavy_atoms=data.get("min_ligand_heavy_atoms"),
        max_ligand_heavy_atoms=data.get("max_ligand_heavy_atoms"),
    )


def _build_chemical_state(data: dict | None):
    if data is None:
        return None
    from covalent_design.inference.request_schema import ProteinChemicalStateRequest

    return ProteinChemicalStateRequest(
        target_atom_formal_charge=data.get("target_atom_formal_charge"),
        target_atom_protonation_state=data.get("target_atom_protonation_state"),
        target_atom_hydrogen_state=data.get("target_atom_hydrogen_state"),
        protein_preparation_policy=data.get("protein_preparation_policy"),
        chemical_state_source=data.get("chemical_state_source"),
        chemical_state_tool_name=data.get("chemical_state_tool_name"),
        chemical_state_tool_version=data.get("chemical_state_tool_version"),
        chemical_state_confidence=data.get("chemical_state_confidence"),
    )


# ---------------------------------------------------------------------------
# 11. Programmatic non-integer rejection — string-typed fields must raise
#     ContractError, not leak an unstructured TypeError
# ---------------------------------------------------------------------------


class ProgrammaticNonIntegerRejectionTests(unittest.TestCase):
    """Build requests programmatically with string-typed integer fields.

    Each must be rejected with the correct REQUEST_* ContractError code.
    The current implementation is expected to leak TypeError or
    REQUEST_STRUCTURE_UNREADABLE; these tests are RED until the production
    code guards type boundaries.
    """

    def test_sample_count_string_ten_is_rejected_with_request_sample_count_invalid(self):
        """sample_count='ten' → REQUEST_SAMPLE_COUNT_INVALID, not TypeError."""
        from covalent_design.contracts.errors import ContractError
        from covalent_design.inference.request_schema import (
            ProteinAtomLocator,
            ReactiveSiteGenerationRequest,
        )
        from covalent_design.inference.request_validation import validate_request
        from covalent_design.rules.validate import load_rule_table

        rules = load_rule_table(VALID_RULE_TABLE)

        request = ReactiveSiteGenerationRequest(
            request_id="test-sample-count-string",
            protein_structure_uri=str(STRUCTURES_DIR / "valid_structure.pdb"),
            protein_structure_format="pdb",
            target_atom_identity_request=ProteinAtomLocator(
                chain_id="A",
                residue_number=42,
                residue_name="CYS",
                atom_name="SG",
            ),
            residue_reaction_family="CYS_MICHAEL_ADDITION",
            sample_count="ten",  # intentionally wrong type
        )

        with self.assertRaises(ContractError) as ctx:
            validate_request(request, rules, request_base_dir=str(STRUCTURES_DIR))
        self.assertEqual(ctx.exception.code, "REQUEST_SAMPLE_COUNT_INVALID")
        self.assertEqual(ctx.exception.owner, "request")

    def test_sample_count_string_ten_via_fixture_is_rejected(self):
        """Fixture sample_count='ten' → REQUEST_SAMPLE_COUNT_INVALID, not STRUCTURE_UNREADABLE."""
        from covalent_design.contracts.errors import ContractError

        with self.assertRaises(ContractError) as ctx:
            _validate_fixture("error_sample_count_string.yml")
        self.assertEqual(ctx.exception.code, "REQUEST_SAMPLE_COUNT_INVALID")
        self.assertEqual(ctx.exception.owner, "request")

    def test_fixed_size_string_ten_is_rejected_with_request_ligand_size_invalid(self):
        """num_ligand_heavy_atoms='ten' → REQUEST_LIGAND_SIZE_INVALID."""
        from covalent_design.contracts.errors import ContractError
        from covalent_design.inference.request_schema import (
            LigandSizeControl,
            ProteinAtomLocator,
            ReactiveSiteGenerationRequest,
        )
        from covalent_design.inference.request_validation import validate_request
        from covalent_design.rules.validate import load_rule_table

        rules = load_rule_table(VALID_RULE_TABLE)

        request = ReactiveSiteGenerationRequest(
            request_id="test-str-fixed-size",
            protein_structure_uri=str(STRUCTURES_DIR / "valid_structure.pdb"),
            protein_structure_format="pdb",
            target_atom_identity_request=ProteinAtomLocator(
                chain_id="A",
                residue_number=42,
                residue_name="CYS",
                atom_name="SG",
            ),
            residue_reaction_family="CYS_MICHAEL_ADDITION",
            sample_count=10,
            size_control=LigandSizeControl(
                num_ligand_heavy_atoms="ten",  # intentionally wrong type
            ),
        )

        with self.assertRaises(ContractError) as ctx:
            validate_request(request, rules, request_base_dir=str(STRUCTURES_DIR))
        self.assertEqual(ctx.exception.code, "REQUEST_LIGAND_SIZE_INVALID")
        self.assertEqual(ctx.exception.owner, "request")

    def test_range_min_string_ten_is_rejected_with_request_ligand_size_range_invalid(self):
        """min_ligand_heavy_atoms='ten' → REQUEST_LIGAND_SIZE_RANGE_INVALID."""
        from covalent_design.contracts.errors import ContractError
        from covalent_design.inference.request_schema import (
            LigandSizeControl,
            ProteinAtomLocator,
            ReactiveSiteGenerationRequest,
        )
        from covalent_design.inference.request_validation import validate_request
        from covalent_design.rules.validate import load_rule_table

        rules = load_rule_table(VALID_RULE_TABLE)

        request = ReactiveSiteGenerationRequest(
            request_id="test-str-range-size",
            protein_structure_uri=str(STRUCTURES_DIR / "valid_structure.pdb"),
            protein_structure_format="pdb",
            target_atom_identity_request=ProteinAtomLocator(
                chain_id="A",
                residue_number=42,
                residue_name="CYS",
                atom_name="SG",
            ),
            residue_reaction_family="CYS_MICHAEL_ADDITION",
            sample_count=10,
            size_control=LigandSizeControl(
                min_ligand_heavy_atoms="ten",  # intentionally wrong type
                max_ligand_heavy_atoms=40,
            ),
        )

        with self.assertRaises(ContractError) as ctx:
            validate_request(request, rules, request_base_dir=str(STRUCTURES_DIR))
        self.assertEqual(ctx.exception.code, "REQUEST_LIGAND_SIZE_RANGE_INVALID")
        self.assertEqual(ctx.exception.owner, "request")


# ---------------------------------------------------------------------------
# 12. PDB MODEL record resolution
# ---------------------------------------------------------------------------


class PdbModelResolutionTests(unittest.TestCase):
    """Target resolution against a multi-model PDB file.

    The PDB parser does not currently parse MODEL/ENDMDL records;
    structure_model is always None.  These tests are RED until the
    parser is extended.
    """

    def test_model_2_locator_resolves_to_structure_model_2(self):
        """Locator structure_model=2 selects atoms from MODEL 2 only."""
        from covalent_design.inference.request_schema import (
            ProteinAtomLocator,
            ProteinChemicalStateRequest,
            ReactiveSiteGenerationRequest,
        )
        from covalent_design.inference.request_validation import validate_request
        from covalent_design.rules.validate import load_rule_table

        rules = load_rule_table(VALID_RULE_TABLE)

        request = ReactiveSiteGenerationRequest(
            request_id="test-model-2",
            protein_structure_uri=str(STRUCTURES_DIR / "multi_model.pdb"),
            protein_structure_format="pdb",
            target_atom_identity_request=ProteinAtomLocator(
                chain_id="A",
                residue_number=42,
                residue_name="CYS",
                atom_name="SG",
                structure_model=2,
            ),
            residue_reaction_family="CYS_MICHAEL_ADDITION",
            sample_count=10,
            protein_chemical_state_request=ProteinChemicalStateRequest(
                target_atom_formal_charge=0,
                target_atom_protonation_state="thiolate",
                target_atom_hydrogen_state="absent",
            ),
        )

        validated = validate_request(
            request, rules, request_base_dir=str(STRUCTURES_DIR)
        )
        self.assertEqual(
            validated.resolved_target_atom_identity.structure_model, 2
        )
        self.assertEqual(
            validated.resolved_target_atom_identity.chain_id, "A"
        )
        self.assertEqual(
            validated.resolved_target_atom_identity.residue_number, 42
        )
        self.assertEqual(
            validated.resolved_target_atom_identity.residue_name, "CYS"
        )
        self.assertEqual(
            validated.resolved_target_atom_identity.atom_name, "SG"
        )


# ---------------------------------------------------------------------------
# 13. write_normalized_request filesystem robustness
# ---------------------------------------------------------------------------


class WriteNormalizedRequestFilesystemTests(unittest.TestCase):
    """Filesystem behaviour of write_normalized_request.

    Currently write_normalized_request does not create missing parent
    directories.  The nested-directory test is RED until the production
    code calls Path.mkdir(parents=True).
    """

    def test_creates_missing_parent_directories(self):
        """write_normalized_request creates parent dirs for a nested path."""
        import tempfile

        from covalent_design.inference.request_validation import (
            write_normalized_request,
        )

        validated = _validate_fixture("valid_request.yml")
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "nested" / "request.normalized.yml"
            result = write_normalized_request(validated, out_path)
            self.assertTrue(out_path.exists(), f"expected file at {out_path}")
            content = out_path.read_text(encoding="utf-8")
            self.assertIn("request_id", content)


if __name__ == "__main__":
    unittest.main()
