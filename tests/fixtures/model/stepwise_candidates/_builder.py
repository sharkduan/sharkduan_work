"""Load static stepwise_candidates fixtures for tests.

Usage from tests::

    from tests.fixtures.model.stepwise_candidates._builder import (
        StepwiseCandidateFixtureBuilder,
    )

    builder = StepwiseCandidateFixtureBuilder()
    protein_atoms, ligand_atoms, edge_candidates = builder.load("within_radius")
"""

from __future__ import annotations

import json
import os
from typing import Any

_FIXTURE_DIR = os.path.dirname(os.path.abspath(__file__))

SCENARIOS = ("within_radius", "outside_radius", "zero_natural_negatives")


def _load_json(scenario: str, filename: str) -> dict[str, Any]:
    path = os.path.join(_FIXTURE_DIR, scenario, filename)
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


class StepwiseCandidateFixtureBuilder:
    """Loads static stepwise_candidates fixture data for tests."""

    def load(
        self, scenario: str
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
        """Return (protein_atoms, ligand_atoms, edge_candidates_artifact)."""
        if scenario not in SCENARIOS:
            raise ValueError(
                f"Unknown scenario {scenario!r}, expected one of {SCENARIOS}"
            )
        protein_data = _load_json(scenario, "protein_atom_table.json")
        ligand_data = _load_json(scenario, "ligand_atom_table.json")
        edge_data = _load_json(scenario, "edge_candidates.json")
        return (
            protein_data["atoms"],
            ligand_data["atoms"],
            edge_data,
        )

    def load_protein_atoms(self, scenario: str) -> list[dict[str, Any]]:
        protein_data = _load_json(scenario, "protein_atom_table.json")
        return protein_data["atoms"]

    def load_ligand_atoms(self, scenario: str) -> list[dict[str, Any]]:
        ligand_data = _load_json(scenario, "ligand_atom_table.json")
        return ligand_data["atoms"]

    def load_edge_candidates_artifact(self, scenario: str) -> dict[str, Any]:
        return _load_json(scenario, "edge_candidates.json")

    def load_protein_metadata(self, scenario: str) -> dict[str, Any]:
        return _load_json(scenario, "protein_atom_table.json")
