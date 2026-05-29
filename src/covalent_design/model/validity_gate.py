"""Hard-gate validity checks for covalent edge candidates (Task 21).

Defines the ``ValidityGate`` abstract interface. Production
implementations evaluate the 9 gate checks in spec order and return
one ``EdgeValidityCheck`` record per check.
"""

from __future__ import annotations

import abc
from typing import Any

from covalent_design.contracts.types import EdgeValidityCheck


class ValidityGate(abc.ABC):
    """Abstract gate that evaluates all 9 covalent edge validity checks.

    Production implementations check target atom identity, ligand atom
    class, bond type, single-edge representability, warhead SMARTS,
    forbidden SMARTS, valence, protonation, and geometry in the
    spec-defined order from interface-design.md Failure Reason Priority.
    """

    @abc.abstractmethod
    def evaluate(
        self,
        candidate_index: int,
        candidate: dict,
        state: Any,
    ) -> tuple[EdgeValidityCheck, ...]:
        """Evaluate every gate check for one candidate.

        Returns one ``EdgeValidityCheck`` per gate check, ordered
        according to the spec gate evaluation sequence. The first
        non-pass check in that sequence is the primary failure for
        this candidate.
        """
        ...
