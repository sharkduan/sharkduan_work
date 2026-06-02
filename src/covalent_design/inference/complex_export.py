"""Task 29 public API — complex export adapter and writer re-export."""

from __future__ import annotations

import dataclasses
from pathlib import Path

from covalent_design.contracts.errors import ContractError
from covalent_design.contracts.types import (
    ArtifactRef,
    CovalentEdge,
    CovalentGenerationResult,
)
from covalent_design.io.mmcif_writer import write_covalent_complex as _write

write_covalent_complex = _write


def export_covalent_complex_result(
    result: CovalentGenerationResult,
    protein_atom_table: ArtifactRef,
    ligand_coords: object,
    ligand_atom_types: object,
    ligand_bonds: object,
    covalent_edge: CovalentEdge,
    out_path: Path,
    *,
    artifact_root: Path,
) -> CovalentGenerationResult:
    """Write the mmCIF complex and return an updated *result* with success statuses.

    On success, uses ``dataclasses.replace`` to return a new result with:
    - ``complex_mmcif`` ArtifactRef merged into artifacts
    - ``complex_export_status`` = ``"exported"``
    - ``docking_eligibility_status`` = ``"eligible"``
    - ``docking_run_status`` = ``"not_run"``
    - ``primary_failure_reason`` cleared to ``None``
    """
    try:
        ref = _write(
            result=result,
            protein_atom_table=protein_atom_table,
            ligand_coords=ligand_coords,
            ligand_atom_types=ligand_atom_types,
            ligand_bonds=ligand_bonds,
            covalent_edge=covalent_edge,
            out_path=out_path,
            artifact_root=artifact_root,
        )
    except ContractError:
        raise
    except Exception as exc:
        raise ContractError(
            code="COMPLEX_EXPORT_FAILED",
            owner="inference",
            message=f"Unexpected export error: {exc}",
        ) from exc

    new_artifacts = dict(result.artifacts)
    new_artifacts["complex_mmcif"] = ref

    return dataclasses.replace(
        result,
        artifacts=new_artifacts,
        complex_export_status="exported",
        docking_eligibility_status="eligible",
        docking_run_status="not_run",
        primary_failure_reason=None,
    )


def adapt_complex_export_failure(
    result: CovalentGenerationResult,
) -> CovalentGenerationResult:
    """Return a new *result* reflecting a failed complex export.

    Uses ``dataclasses.replace`` to return a new result with:
    - ``complex_export_status`` = ``"failed"``
    - ``docking_eligibility_status`` = ``"not_applicable"``
    - ``docking_run_status`` = ``"not_applicable"``
    - ``primary_failure_reason`` = ``"COMPLEX_EXPORT_FAILED"``

    Preserves generation-valid diagnostics and existing artifacts.
    """
    return dataclasses.replace(
        result,
        complex_export_status="failed",
        docking_eligibility_status="not_applicable",
        docking_run_status="not_applicable",
        primary_failure_reason="COMPLEX_EXPORT_FAILED",
    )
