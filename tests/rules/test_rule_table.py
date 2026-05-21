"""
Tests for rule table schema and validation (Task 8 Window B).

Expected production API (to be implemented in Window C):

  from covalent_design.rules.schema import (
      ReactionFamilyRuleTable,
      ReactionFamilyRuleRow,
  )
  from covalent_design.rules.validate import (
      load_rule_table,
      validate_rule_table,
  )

  load_rule_table(path: Path) -> ReactionFamilyRuleTable
      Parse a YAML rule table file into a typed object.

  validate_rule_table(table: ReactionFamilyRuleTable)
      -> ContractEnvelope[RuleValidationReport]
      Validate a loaded rule table and return an envelope whose payload
      carries per-family pass/fail/pending details.  The receipt uses
      the standard ValidationReceipt shape (passed/ok, errors, warnings).

CLI (subprocess):

  python -m covalent_design.rules.cli.validate_rule_table --rules <path>
      Writes a JSON summary to stdout.
      Exit code 0 on success; exit code 10 on contract validation failure.

These tests are expected to FAIL until Window C delivers the production modules.
"""

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path


FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "rules"
REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _validate_fixture(name: str):
    """Load *name* from FIXTURE_ROOT and return validate_rule_table's envelope."""
    from covalent_design.rules.validate import load_rule_table, validate_rule_table

    table = load_rule_table(FIXTURE_ROOT / name)
    return validate_rule_table(table)


def _assert_family_error(envelope, error_code: str):
    """Assert that *envelope* contains at least one error whose code matches."""
    codes = {e.code for e in envelope.receipt.errors}
    self = unittest.TestCase()
    self.assertIn(
        error_code,
        codes,
        f"expected error {error_code!r} not found in {sorted(codes)}",
    )


# ---------------------------------------------------------------------------
# Python API tests - structural validation
# ---------------------------------------------------------------------------

class RuleTableValidationTests(unittest.TestCase):
    """Schema and structural validation of loaded rule tables."""

    # -- 1. valid fixture passes -------------------------------------------

    def test_valid_rule_table_passes_validation(self):
        envelope = _validate_fixture("valid_rule_table.yml")
        self.assertTrue(envelope.receipt.ok)
        self.assertEqual(len(envelope.receipt.errors), 0)

    # -- 2. family / residue_reaction_family mismatch ----------------------

    def test_family_id_mismatch_with_residue_reaction_family_fails(self):
        envelope = _validate_fixture("family_mismatch.yml")
        self.assertFalse(envelope.receipt.ok)
        _assert_family_error(envelope, "RULE_FAMILY_ID_REACTION_CLASS_MISMATCH")

    # -- 3. empty SMARTS is NOT permissive ---------------------------------

    def test_empty_smarts_with_calibrated_status_fails_validation(self):
        envelope = _validate_fixture("empty_smarts.yml")
        self.assertFalse(envelope.receipt.ok)
        _assert_family_error(envelope, "RULE_EMPTY_SMARTS_NOT_PERMISSIVE")

    # -- 4. null geometry is NOT permissive --------------------------------

    def test_null_geometry_with_calibrated_status_fails_validation(self):
        envelope = _validate_fixture("null_geometry.yml")
        self.assertFalse(envelope.receipt.ok)
        _assert_family_error(envelope, "RULE_NULL_GEOMETRY_NOT_PERMISSIVE")

    # -- 5. pending rules do not present as permissive/enabled -------------

    def test_pending_smarts_not_reported_as_calibrated_and_permissive(self):
        """A rule table whose family has pending warheads must be reported
        as pending, not as if the SMARTS gate had passed."""
        envelope = _validate_fixture("valid_rule_table.yml")
        self.assertTrue(envelope.receipt.ok)

        report = envelope.payload
        family = report.families[0]

        self.assertEqual(family["family_id"], "CYS_MICHAEL_ADDITION")
        self.assertEqual(family["warhead_rule_status"], "pending")
        # Pending SMARTS must NOT be listed as calibrated or passed.
        self.assertNotEqual(family.get("warhead_gate"), "calibrated")
        self.assertNotEqual(family.get("warhead_gate"), "pass")

    def test_pending_geometry_not_reported_as_calibrated_and_permissive(self):
        """A rule table family with pending geometry must be reported as
        pending, not as if the geometry gate had passed."""
        envelope = _validate_fixture("valid_rule_table.yml")
        self.assertTrue(envelope.receipt.ok)

        report = envelope.payload
        family = report.families[0]

        self.assertEqual(family["geometry_status"]["bond_length"], "pending")
        self.assertEqual(family["geometry_status"]["protein_side_angle"], "pending")
        self.assertEqual(family["geometry_status"]["ligand_side_angle"], "pending")
        # Pending geometry must NOT be listed as calibrated.
        for key in ("bond_length", "protein_side_angle", "ligand_side_angle"):
            self.assertNotEqual(family.get(f"geometry_gate_{key}"), "calibrated")
            self.assertNotEqual(family.get(f"geometry_gate_{key}"), "pass")

    # -- 6. missing anchor atom --------------------------------------------

    def test_missing_anchor_atom_fails_validation(self):
        envelope = _validate_fixture("missing_required.yml")
        self.assertFalse(envelope.receipt.ok)
        _assert_family_error(envelope, "RULE_MISSING_ANCHOR_ATOM")

    # -- 7. missing ligand neighbor policy ---------------------------------

    def test_missing_ligand_neighbor_policy_fails_validation(self):
        envelope = _validate_fixture("missing_required.yml")
        self.assertFalse(envelope.receipt.ok)
        _assert_family_error(envelope, "RULE_MISSING_LIGAND_NEIGHBOR_POLICY")

    # -- 8. missing protein state requirements -----------------------------

    def test_missing_protein_state_requirements_fails_validation(self):
        envelope = _validate_fixture("missing_required.yml")
        self.assertFalse(envelope.receipt.ok)
        _assert_family_error(envelope, "RULE_MISSING_PROTEIN_STATE_REQUIREMENTS")

    # -- 9. missing valence delta ------------------------------------------

    def test_missing_valence_delta_fails_validation(self):
        envelope = _validate_fixture("missing_required.yml")
        self.assertFalse(envelope.receipt.ok)
        _assert_family_error(envelope, "RULE_MISSING_VALENCE_DELTA")


# ---------------------------------------------------------------------------
# CLI tests - exit codes and JSON summary
# ---------------------------------------------------------------------------

class RuleTableCliTests(unittest.TestCase):
    def _run_cli(self, fixture_name: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = "src"
        rules_path = FIXTURE_ROOT / fixture_name
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "covalent_design.rules.cli.validate_rule_table",
                "--rules",
                str(rules_path),
            ],
            cwd=str(REPO_ROOT),
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    # -- 10. valid fixture - exit 0 and JSON ok:true -----------------------

    def test_cli_valid_fixture_returns_exit_0_and_ok_true(self):
        result = self._run_cli("valid_rule_table.yml")
        self.assertEqual(result.returncode, 0, f"stderr:\n{result.stderr}")
        summary = json.loads(result.stdout)
        self.assertTrue(summary["ok"])

    # -- 11. invalid fixture - non-zero exit and JSON errors ---------------

    def test_cli_invalid_fixture_returns_nonzero_and_error_summary(self):
        result = self._run_cli("family_mismatch.yml")
        self.assertEqual(result.returncode, 10, f"stderr:\n{result.stderr}")
        summary = json.loads(result.stdout)
        self.assertFalse(summary["ok"])
        self.assertIn("errors", summary)
        self.assertGreater(len(summary["errors"]), 0)


if __name__ == "__main__":
    unittest.main()
