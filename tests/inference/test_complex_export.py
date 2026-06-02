"""Task 29 mmCIF complex export contract tests.

These tests define the public API and boundary contracts for
``write_covalent_complex()``, ``export_covalent_complex_result()``, and
``adapt_complex_export_failure()``.

Coverage:
1.  Writer API: importable, returns ArtifactRef, rejects non-result.
2.  Valid export: byte-deterministic golden mmCIF, protein-then-ligand atom
    order, one covale struct_conn, coordinate precision, ligand atom naming,
    ligand mmCIF identity, ArtifactRef receipt fields.
3.  Protein table validation: missing, checksum mismatch, unreadable, empty
    atoms, target atom not found, absolute/traversal URI rejection.
4.  Ligand input validation: coord shape, atom types, bond shape, bond index
    out of range, self-bond rejection.
5.  Edge mismatch: protein atom not in table, ligand attachment atom out of
    range.
6.  Adapters: immutable success (adds complex_mmcif, sets statuses),
    immutable failure (preserves diagnostics, sets failure statuses).
7.  Task 28 ResultWriter compatibility for success and failure results.
8.  Source guards: no RDKit, torch, docking, evaluation, Task 30 imports.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from covalent_design.contracts.errors import ContractError
from covalent_design.contracts.types import (
    ArtifactRef,
    CovalentEdge,
    CovalentGenerationResult,
    GeometryMetrics,
    LigandAtomIdentity,
    MoleculeQuality,
    ProteinAtomIdentity,
)

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "inference" / "complex_export"


# ===================================================================
# Shared helpers
# ===================================================================


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_hex(path.read_bytes())


def _make_valid_result(
    request_id: str = "task29-test-001",
    sample_id: int = 0,
) -> CovalentGenerationResult:
    """Build a minimal valid CovalentGenerationResult for export testing."""
    return CovalentGenerationResult(
        request_id=request_id,
        sample_id=sample_id,
        residue_reaction_family="CYS_MICHAEL_ADDITION",
        target_atom_identity=ProteinAtomIdentity(
            chain_id="A",
            residue_number=145,
            residue_name="CYS",
            atom_name="SG",
            asym_id="A",
            atom_serial=1234,
        ),
        generation_validity_status="valid",
        complex_export_status="not_applicable",
        docking_eligibility_status="not_applicable",
        docking_run_status="not_applicable",
        primary_failure_reason=None,
        secondary_failure_reasons=(),
        generated_ligand_status="present",
        predicted_ligand_attachment_atom=LigandAtomIdentity(
            ligand_id="LIG",
            atom_name="C1",
            atom_index=0,
        ),
        predicted_covalent_edge=CovalentEdge(
            protein_atom=ProteinAtomIdentity(
                chain_id="A",
                residue_number=145,
                residue_name="CYS",
                atom_name="SG",
                asym_id="A",
                atom_serial=1234,
            ),
            ligand_atom=LigandAtomIdentity(
                ligand_id="LIG",
                atom_name="C1",
                atom_index=0,
            ),
            bond_type="carbon-sulfur",
        ),
        covalent_edge_score=0.95,
        geometry_metrics=GeometryMetrics(
            bond_length=1.82,
            protein_side_angle=109.5,
            ligand_side_angle=120.0,
        ),
        molecular_quality_metrics=MoleculeQuality(
            qed=0.7,
            sa_score=2.5,
            log_p=1.2,
            molecular_weight=320.0,
        ),
        matched_warhead_type="acrylamide",
    )


_COORDS: list[list[float]] = [[1.0, 2.0, 3.0], [1.5, 2.5, 3.5], [0.5, 1.8, 3.2]]
_TYPES: list[str] = ["C", "C", "O"]
_BONDS: list[list[int]] = [[0, 1], [0, 2]]

_EDGE = CovalentEdge(
    protein_atom=ProteinAtomIdentity(
        chain_id="A", residue_number=145, residue_name="CYS",
        atom_name="SG", asym_id="A", atom_serial=1234,
    ),
    ligand_atom=LigandAtomIdentity(
        ligand_id="LIG", atom_name="C1", atom_index=0,
    ),
    bond_type="carbon-sulfur",
)


def _tmp_root() -> Path:
    """Create a temp directory with fixture protein tables copied in."""
    tmp = Path(tempfile.mkdtemp(prefix="task29_"))
    for name in [
        "protein_atom_table.json",
        "protein_atom_table_no_target.json",
        "protein_atom_table_empty.json",
        "protein_atom_table_unreadable.json",
    ]:
        src = FIXTURES / name
        if src.is_file():
            shutil.copy2(src, tmp / name)
    return tmp


def _prot_ref(root: Path, *, uri: str = "protein_atom_table.json",
              sha256: str | None = None) -> ArtifactRef:
    if sha256 is None:
        sha256 = _sha256_file(root / uri)
    return ArtifactRef(uri=uri, sha256=sha256, format="json",
                       role="protein_atom_table")


# ===================================================================
# 1.  Writer API contract (3 tests)
# ===================================================================


class WriterAPITests(unittest.TestCase):
    """write_covalent_complex import, signature, and type-guard tests."""

    @staticmethod
    def _fn():
        from covalent_design.inference.complex_export import write_covalent_complex
        return write_covalent_complex

    def test_writer_is_importable_and_callable(self) -> None:
        fn = self._fn()
        self.assertTrue(callable(fn))

    def test_writer_returns_artifact_ref(self) -> None:
        fn = self._fn()
        root = _tmp_root()
        try:
            ref = fn(
                result=_make_valid_result(),
                protein_atom_table=_prot_ref(root),
                ligand_coords=_COORDS,
                ligand_atom_types=_TYPES,
                ligand_bonds=_BONDS,
                covalent_edge=_EDGE,
                out_path=root / "out.mmcif",
                artifact_root=root,
            )
            self.assertIsInstance(ref, ArtifactRef)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_writer_rejects_non_result(self) -> None:
        fn = self._fn()
        root = _tmp_root()
        try:
            with self.assertRaises(TypeError):
                fn(
                    result={"not": "a result"},
                    protein_atom_table=_prot_ref(root),
                    ligand_coords=_COORDS,
                    ligand_atom_types=_TYPES,
                    ligand_bonds=_BONDS,
                    covalent_edge=_EDGE,
                    out_path=root / "out.mmcif",
                    artifact_root=root,
                )
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_writer_rejects_generation_invalid_result(self) -> None:
        fn = self._fn()
        root = _tmp_root()
        try:
            with self.assertRaises(ContractError) as ctx:
                fn(
                    result=replace(
                        _make_valid_result(),
                        generation_validity_status="invalid",
                    ),
                    protein_atom_table=_prot_ref(root),
                    ligand_coords=_COORDS,
                    ligand_atom_types=_TYPES,
                    ligand_bonds=_BONDS,
                    covalent_edge=_EDGE,
                    out_path=root / "out.mmcif",
                    artifact_root=root,
                )
            self.assertEqual(ctx.exception.code, "COMPLEX_EXPORT_FAILED")
            self.assertEqual(ctx.exception.owner, "inference")
        finally:
            shutil.rmtree(root, ignore_errors=True)


# ===================================================================
# 2.  Valid export (10 tests)
# ===================================================================


class ValidExportTests(unittest.TestCase):
    """Byte-deterministic golden output and mmCIF content verification."""

    @staticmethod
    def _fn():
        from covalent_design.inference.complex_export import write_covalent_complex
        return write_covalent_complex

    def _write(self, root: Path, name: str = "out.mmcif") -> tuple[Path, ArtifactRef]:
        fn = self._fn()
        out = root / name
        ref = fn(
            result=_make_valid_result(),
            protein_atom_table=_prot_ref(root),
            ligand_coords=_COORDS,
            ligand_atom_types=_TYPES,
            ligand_bonds=_BONDS,
            covalent_edge=_EDGE,
            out_path=out,
            artifact_root=root,
        )
        return out, ref

    # -- golden fixture --

    def test_golden_output_byte_deterministic(self) -> None:
        root = _tmp_root()
        try:
            out, _ = self._write(root)
            actual = out.read_bytes()
            expected = (FIXTURES / "golden_complex.mmcif").read_bytes()
            self.assertEqual(actual, expected,
                             "mmCIF output does not match golden fixture byte-for-byte")
        finally:
            shutil.rmtree(root, ignore_errors=True)

    # -- entry id --

    def test_entry_id_contains_request_id_and_sample_id(self) -> None:
        root = _tmp_root()
        try:
            out, _ = self._write(root)
            text = out.read_text(encoding="utf-8")
            self.assertIn("_entry.id", text)
            # entry value should reference both identifiers
            entry_match = re.search(r"_entry\.id\s+(\S+)", text)
            self.assertIsNotNone(entry_match, "_entry.id not found")
            self.assertIn("task29", entry_match.group(1).lower())
        finally:
            shutil.rmtree(root, ignore_errors=True)

    # -- atom ordering --

    def test_protein_atoms_before_ligand_atoms(self) -> None:
        root = _tmp_root()
        try:
            out, _ = self._write(root)
            atom_lines = [ln for ln in out.read_text(encoding="utf-8").splitlines()
                          if ln.startswith("ATOM") or ln.startswith("HETATM")]
            lig_start = next((i for i, ln in enumerate(atom_lines)
                              if "LIG" in ln.split()), None)
            prot_end = max(i for i, ln in enumerate(atom_lines)
                           if "LIG" not in ln.split())
            if lig_start is not None:
                self.assertLess(prot_end, lig_start,
                                "protein atoms must precede ligand atoms")
        finally:
            shutil.rmtree(root, ignore_errors=True)

    # -- struct_conn --

    def test_exactly_one_covale_link(self) -> None:
        root = _tmp_root()
        try:
            out, _ = self._write(root)
            covale_count = sum(
                1 for ln in out.read_text(encoding="utf-8").splitlines()
                if ln.strip().startswith("covale")
            )
            self.assertEqual(covale_count, 1,
                             f"expected 1 covale line, got {covale_count}")
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_covale_link_connects_sg_to_c1(self) -> None:
        root = _tmp_root()
        try:
            out, _ = self._write(root)
            text = out.read_text(encoding="utf-8")
            covale = next(ln for ln in text.splitlines()
                          if ln.strip().startswith("covale"))
            self.assertIn("SG", covale)
            self.assertIn("C1", covale)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    # -- coordinate precision --

    def test_coordinates_three_decimal_places(self) -> None:
        root = _tmp_root()
        try:
            out, _ = self._write(root)
            atom_lines = [ln for ln in out.read_text(encoding="utf-8").splitlines()
                          if ln.startswith("ATOM") or ln.startswith("HETATM")]
            self.assertGreater(len(atom_lines), 0)
            for line in atom_lines:
                coords = [f for f in line.split()
                          if re.match(r"^-?\d+\.\d{3}$", f)]
                self.assertGreaterEqual(len(coords), 3,
                                        f"need 3 three-decimal coords in: {line}")
        finally:
            shutil.rmtree(root, ignore_errors=True)

    # -- ligand naming and identity --

    def test_ligand_atom_names_element_local_one_based(self) -> None:
        root = _tmp_root()
        try:
            out, _ = self._write(root)
            lig_lines = [ln for ln in out.read_text(encoding="utf-8").splitlines()
                         if (ln.startswith("ATOM") or ln.startswith("HETATM"))
                         and "LIG" in ln.split()]
            names = [ln.split()[3] for ln in lig_lines]
            self.assertIn("C1", names)
            self.assertIn("C2", names)
            self.assertIn("O1", names)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_ligand_mmcif_identity(self) -> None:
        root = _tmp_root()
        try:
            out, _ = self._write(root)
            lig_lines = [ln for ln in out.read_text(encoding="utf-8").splitlines()
                         if (ln.startswith("ATOM") or ln.startswith("HETATM"))
                         and "LIG" in ln.split()]
            self.assertGreater(len(lig_lines), 0)
            for line in lig_lines:
                parts = line.split()
                self.assertEqual(parts[6], "L", f"asym_id: {line}")
                self.assertEqual(parts[5], "LIG", f"comp_id: {line}")
                self.assertEqual(parts[8], "1", f"seq_id: {line}")
        finally:
            shutil.rmtree(root, ignore_errors=True)

    # -- ArtifactRef receipt --

    def test_artifact_ref_role_format(self) -> None:
        root = _tmp_root()
        try:
            _, ref = self._write(root)
            self.assertEqual(ref.role, "complex_mmcif")
            self.assertEqual(ref.format, "mmcif")
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_artifact_ref_uri_bytes_sha256(self) -> None:
        root = _tmp_root()
        try:
            out, ref = self._write(root)
            self.assertFalse(os.path.isabs(ref.uri),
                             f"URI must be relative: {ref.uri!r}")
            self.assertNotIn("..", ref.uri)
            self.assertEqual(ref.bytes, out.stat().st_size)
            self.assertEqual(ref.sha256, _sha256_file(out))
        finally:
            shutil.rmtree(root, ignore_errors=True)


# ===================================================================
# 3.  Protein table validation (5 tests)
# ===================================================================


class ProteinTableValidationTests(unittest.TestCase):
    """Validation of the protein atom table artifact."""

    @staticmethod
    def _fn():
        from covalent_design.inference.complex_export import write_covalent_complex
        return write_covalent_complex

    def _assert_export_error(self, prot_ref: ArtifactRef, root: Path) -> ContractError:
        fn = self._fn()
        with self.assertRaises(ContractError) as ctx:
            fn(
                result=_make_valid_result(),
                protein_atom_table=prot_ref,
                ligand_coords=_COORDS,
                ligand_atom_types=_TYPES,
                ligand_bonds=_BONDS,
                covalent_edge=_EDGE,
                out_path=root / "out.mmcif",
                artifact_root=root,
            )
        err = ctx.exception
        self.assertEqual(err.code, "COMPLEX_EXPORT_FAILED")
        self.assertEqual(err.owner, "inference")
        return err

    def test_missing_protein_table(self) -> None:
        root = _tmp_root()
        try:
            ref = ArtifactRef(uri="nonexistent.json", sha256="0" * 64,
                              format="json", role="protein_atom_table")
            self._assert_export_error(ref, root)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_checksum_mismatch(self) -> None:
        root = _tmp_root()
        try:
            ref = _prot_ref(root, sha256="a" * 64)
            self._assert_export_error(ref, root)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_unreadable_protein_table(self) -> None:
        root = _tmp_root()
        try:
            uri = "protein_atom_table_unreadable.json"
            ref = ArtifactRef(uri=uri, sha256=_sha256_file(root / uri),
                              format="json", role="protein_atom_table")
            self._assert_export_error(ref, root)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_empty_atoms_array(self) -> None:
        root = _tmp_root()
        try:
            uri = "protein_atom_table_empty.json"
            ref = ArtifactRef(uri=uri, sha256=_sha256_file(root / uri),
                              format="json", role="protein_atom_table")
            self._assert_export_error(ref, root)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_target_atom_not_in_table(self) -> None:
        root = _tmp_root()
        try:
            uri = "protein_atom_table_no_target.json"
            ref = ArtifactRef(uri=uri, sha256=_sha256_file(root / uri),
                              format="json", role="protein_atom_table")
            self._assert_export_error(ref, root)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_full_identity_disambiguates_matching_atom_names(self) -> None:
        root = _tmp_root()
        try:
            path = root / "protein_atom_table.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            alternate = dict(payload["atoms"][0])
            alternate["altloc"] = "B"
            alternate["atom_serial"] = 9999
            payload["atoms"].insert(0, alternate)
            path.write_text(json.dumps(payload), encoding="utf-8")

            self._fn()(
                result=_make_valid_result(),
                protein_atom_table=_prot_ref(root),
                ligand_coords=_COORDS,
                ligand_atom_types=_TYPES,
                ligand_bonds=_BONDS,
                covalent_edge=_EDGE,
                out_path=root / "out.mmcif",
                artifact_root=root,
            )
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_ambiguous_protein_atom_identity_rejected(self) -> None:
        root = _tmp_root()
        try:
            path = root / "protein_atom_table.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["atoms"].append(dict(payload["atoms"][0]))
            path.write_text(json.dumps(payload), encoding="utf-8")

            err = self._assert_export_error(_prot_ref(root), root)
            self.assertIn("ambiguous", err.message)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_non_artifact_ref_rejected(self) -> None:
        root = _tmp_root()
        try:
            fn = self._fn()
            with self.assertRaises(ContractError) as ctx:
                fn(
                    result=_make_valid_result(),
                    protein_atom_table={"uri": "protein_atom_table.json"},
                    ligand_coords=_COORDS,
                    ligand_atom_types=_TYPES,
                    ligand_bonds=_BONDS,
                    covalent_edge=_EDGE,
                    out_path=root / "out.mmcif",
                    artifact_root=root,
                )
            self.assertEqual(ctx.exception.code, "COMPLEX_EXPORT_FAILED")
            self.assertEqual(ctx.exception.owner, "inference")
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_non_finite_protein_coordinate_rejected(self) -> None:
        root = _tmp_root()
        try:
            path = root / "protein_atom_table.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["atoms"][0]["x"] = float("inf")
            path.write_text(json.dumps(payload), encoding="utf-8")
            self._assert_export_error(_prot_ref(root), root)
        finally:
            shutil.rmtree(root, ignore_errors=True)


# ===================================================================
# 4.  URI rejection (1 test)
# ===================================================================


class URIRejectionTests(unittest.TestCase):
    """Absolute URI, root-traversal, and out_path boundary rejection."""

    @staticmethod
    def _fn():
        from covalent_design.inference.complex_export import write_covalent_complex
        return write_covalent_complex

    def test_absolute_and_traversal_uris_rejected(self) -> None:
        root = _tmp_root()
        try:
            fn = self._fn()
            sha = _sha256_file(root / "protein_atom_table.json")

            for bad_uri in [str(root / "protein_atom_table.json"),  # absolute
                            "../protein_atom_table.json"]:            # traversal
                with self.subTest(uri=bad_uri):
                    ref = ArtifactRef(uri=bad_uri, sha256=sha,
                                      format="json", role="protein_atom_table")
                    with self.assertRaises(ContractError) as ctx:
                        fn(
                            result=_make_valid_result(),
                            protein_atom_table=ref,
                            ligand_coords=_COORDS,
                            ligand_atom_types=_TYPES,
                            ligand_bonds=_BONDS,
                            covalent_edge=_EDGE,
                            out_path=root / "out.mmcif",
                            artifact_root=root,
                        )
                    self.assertEqual(ctx.exception.code, "COMPLEX_EXPORT_FAILED")
                    self.assertEqual(ctx.exception.owner, "inference")
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_out_path_outside_artifact_root_rejected(self) -> None:
        root = _tmp_root()
        try:
            fn = self._fn()
            # out_path must reside under artifact_root
            outside = root / ".." / "escape_outside_root.mmcif"
            with self.assertRaises(ContractError) as ctx:
                fn(
                    result=_make_valid_result(),
                    protein_atom_table=_prot_ref(root),
                    ligand_coords=_COORDS,
                    ligand_atom_types=_TYPES,
                    ligand_bonds=_BONDS,
                    covalent_edge=_EDGE,
                    out_path=outside,
                    artifact_root=root,
                )
            self.assertEqual(ctx.exception.code, "COMPLEX_EXPORT_FAILED")
            self.assertEqual(ctx.exception.owner, "inference")
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_artifact_root_must_be_directory(self) -> None:
        root = _tmp_root()
        try:
            bad_root = root / "not-a-directory"
            bad_root.write_text("not a directory", encoding="utf-8")
            fn = self._fn()
            with self.assertRaises(ContractError) as ctx:
                fn(
                    result=_make_valid_result(),
                    protein_atom_table=_prot_ref(root),
                    ligand_coords=_COORDS,
                    ligand_atom_types=_TYPES,
                    ligand_bonds=_BONDS,
                    covalent_edge=_EDGE,
                    out_path=root / "out.mmcif",
                    artifact_root=bad_root,
                )
            self.assertEqual(ctx.exception.code, "COMPLEX_EXPORT_FAILED")
            self.assertEqual(ctx.exception.owner, "inference")
        finally:
            shutil.rmtree(root, ignore_errors=True)


# ===================================================================
# 5.  Ligand input validation (5 tests)
# ===================================================================


class LigandInputValidationTests(unittest.TestCase):
    """Validation of ligand coords, atom types, and bonds."""

    @staticmethod
    def _fn():
        from covalent_design.inference.complex_export import write_covalent_complex
        return write_covalent_complex

    def _write_with_ligand(self, root: Path, coords: object,
                           atom_types: object, bonds: object) -> None:
        fn = self._fn()
        fn(
            result=_make_valid_result(),
            protein_atom_table=_prot_ref(root),
            ligand_coords=coords,
            ligand_atom_types=atom_types,
            ligand_bonds=bonds,
            covalent_edge=_EDGE,
            out_path=root / "out.mmcif",
            artifact_root=root,
        )

    def test_coords_not_list_of_triples_rejected(self) -> None:
        root = _tmp_root()
        try:
            with self.assertRaises((ContractError, ValueError, TypeError)):
                self._write_with_ligand(root, coords=[[1.0, 2.0]],
                                        atom_types=_TYPES, bonds=_BONDS)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_atom_types_not_strings_rejected(self) -> None:
        root = _tmp_root()
        try:
            with self.assertRaises((ContractError, ValueError, TypeError)):
                self._write_with_ligand(root, coords=_COORDS,
                                        atom_types=[1, 2, 3], bonds=_BONDS)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_coords_types_length_mismatch_rejected(self) -> None:
        root = _tmp_root()
        try:
            with self.assertRaises((ContractError, ValueError)):
                self._write_with_ligand(
                    root,
                    coords=[[1.0, 2.0, 3.0], [4.0, 5.0, 6.0], [7.0, 8.0, 9.0]],
                    atom_types=["C", "C"],  # shorter
                    bonds=_BONDS,
                )
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_bond_index_out_of_range_rejected(self) -> None:
        root = _tmp_root()
        try:
            for bad_bonds in [[[0, 99]], [[-1, 0]]]:
                with self.subTest(bonds=bad_bonds):
                    with self.assertRaises((ContractError, ValueError)):
                        self._write_with_ligand(root, coords=_COORDS,
                                                atom_types=_TYPES,
                                                bonds=bad_bonds)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_self_bond_rejected(self) -> None:
        root = _tmp_root()
        try:
            with self.assertRaises((ContractError, ValueError)):
                self._write_with_ligand(root, coords=_COORDS,
                                        atom_types=_TYPES, bonds=[[0, 0]])
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_duplicate_bond_rejected(self) -> None:
        root = _tmp_root()
        try:
            with self.assertRaises(ContractError):
                self._write_with_ligand(
                    root,
                    coords=_COORDS,
                    atom_types=_TYPES,
                    bonds=[[0, 1], [1, 0]],
                )
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_non_finite_coordinate_rejected(self) -> None:
        root = _tmp_root()
        try:
            for value in (float("nan"), float("inf")):
                with self.subTest(value=value):
                    with self.assertRaises(ContractError):
                        self._write_with_ligand(
                            root,
                            coords=[[value, 2.0, 3.0], [1.5, 2.5, 3.5], [0.5, 1.8, 3.2]],
                            atom_types=_TYPES,
                            bonds=_BONDS,
                        )
        finally:
            shutil.rmtree(root, ignore_errors=True)


# ===================================================================
# 6.  Edge mismatch (1 test)
# ===================================================================


class EdgeMismatchTests(unittest.TestCase):
    """Covalent edge referencing atoms not in the protein/ligand tables,
    and attachment atom name mismatches."""

    @staticmethod
    def _fn():
        from covalent_design.inference.complex_export import write_covalent_complex
        return write_covalent_complex

    def test_protein_or_ligand_atom_not_found_rejected(self) -> None:
        root = _tmp_root()
        try:
            fn = self._fn()

            # protein atom not in table
            bad_prot_edge = CovalentEdge(
                protein_atom=ProteinAtomIdentity(
                    chain_id="A", residue_number=999, residue_name="CYS",
                    atom_name="SG",
                ),
                ligand_atom=LigandAtomIdentity(
                    ligand_id="LIG", atom_name="C1", atom_index=0,
                ),
                bond_type="carbon-sulfur",
            )
            with self.assertRaises(ContractError) as ctx:
                fn(result=_make_valid_result(), protein_atom_table=_prot_ref(root),
                   ligand_coords=_COORDS, ligand_atom_types=_TYPES,
                   ligand_bonds=_BONDS, covalent_edge=bad_prot_edge,
                   out_path=root / "out.mmcif", artifact_root=root)
            self.assertEqual(ctx.exception.code, "COMPLEX_EXPORT_FAILED")

            # ligand attachment atom index out of range
            bad_lig_edge = CovalentEdge(
                protein_atom=ProteinAtomIdentity(
                    chain_id="A", residue_number=145, residue_name="CYS",
                    atom_name="SG",
                ),
                ligand_atom=LigandAtomIdentity(
                    ligand_id="LIG", atom_name="C99", atom_index=99,
                ),
                bond_type="carbon-sulfur",
            )
            with self.assertRaises(ContractError) as ctx:
                fn(result=_make_valid_result(), protein_atom_table=_prot_ref(root),
                   ligand_coords=_COORDS, ligand_atom_types=_TYPES,
                   ligand_bonds=_BONDS, covalent_edge=bad_lig_edge,
                   out_path=root / "out.mmcif", artifact_root=root)
            self.assertEqual(ctx.exception.code, "COMPLEX_EXPORT_FAILED")
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_ligand_attachment_atom_name_mismatch_rejected(self) -> None:
        root = _tmp_root()
        try:
            fn = self._fn()
            # atom_index == 0 implies deterministic name "C1"
            # a mismatch (e.g. "O1") must be rejected
            bad_name_edge = CovalentEdge(
                protein_atom=ProteinAtomIdentity(
                    chain_id="A", residue_number=145, residue_name="CYS",
                    atom_name="SG",
                ),
                ligand_atom=LigandAtomIdentity(
                    ligand_id="LIG", atom_name="O1", atom_index=0,
                ),
                bond_type="carbon-sulfur",
            )
            with self.assertRaises(ContractError) as ctx:
                fn(result=_make_valid_result(), protein_atom_table=_prot_ref(root),
                   ligand_coords=_COORDS, ligand_atom_types=_TYPES,
                   ligand_bonds=_BONDS, covalent_edge=bad_name_edge,
                   out_path=root / "out.mmcif", artifact_root=root)
            self.assertEqual(ctx.exception.code, "COMPLEX_EXPORT_FAILED")
            self.assertEqual(ctx.exception.owner, "inference")
        finally:
            shutil.rmtree(root, ignore_errors=True)


# ===================================================================
# 7.  Adapter tests (7 tests)
# ===================================================================


class SuccessAdapterTests(unittest.TestCase):
    """export_covalent_complex_result adapter behaviour."""

    @staticmethod
    def _adapter():
        from covalent_design.inference.complex_export import export_covalent_complex_result
        return export_covalent_complex_result

    def _call(self, root: Path):
        return self._adapter()(
            result=_make_valid_result(),
            protein_atom_table=_prot_ref(root),
            ligand_coords=_COORDS,
            ligand_atom_types=_TYPES,
            ligand_bonds=_BONDS,
            covalent_edge=_EDGE,
            out_path=root / "out.mmcif",
            artifact_root=root,
        )

    def test_immutable_replacement(self) -> None:
        root = _tmp_root()
        try:
            result = _make_valid_result()
            original = dict(result.artifacts)
            new_result = self._adapter()(
                result=result,
                protein_atom_table=_prot_ref(root),
                ligand_coords=_COORDS,
                ligand_atom_types=_TYPES,
                ligand_bonds=_BONDS,
                covalent_edge=_EDGE,
                out_path=root / "out.mmcif",
                artifact_root=root,
            )
            self.assertIsNot(new_result, result)
            self.assertEqual(dict(result.artifacts), original)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_adds_complex_mmcif_artifact(self) -> None:
        root = _tmp_root()
        try:
            new_result = self._call(root)
            self.assertIn("complex_mmcif", new_result.artifacts)
            ref = new_result.artifacts["complex_mmcif"]
            self.assertEqual(ref.role, "complex_mmcif")
            self.assertEqual(ref.format, "mmcif")
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_sets_lifecycle_statuses(self) -> None:
        root = _tmp_root()
        try:
            new_result = self._call(root)
            self.assertEqual(new_result.complex_export_status, "exported")
            self.assertEqual(new_result.docking_eligibility_status, "eligible")
            self.assertEqual(new_result.docking_run_status, "not_run")
        finally:
            shutil.rmtree(root, ignore_errors=True)


class FailureAdapterTests(unittest.TestCase):
    """adapt_complex_export_failure adapter behaviour."""

    @staticmethod
    def _adapter():
        from covalent_design.inference.complex_export import adapt_complex_export_failure
        return adapt_complex_export_failure

    def test_immutable_replacement(self) -> None:
        adapter = self._adapter()
        result = _make_valid_result()
        original_artifacts = dict(result.artifacts)
        new_result = adapter(result)
        self.assertIsNot(new_result, result)
        self.assertEqual(dict(result.artifacts), original_artifacts)

    def test_preserves_generation_valid_diagnostics(self) -> None:
        adapter = self._adapter()
        result = _make_valid_result()
        new_result = adapter(result)
        self.assertEqual(new_result.generation_validity_status, "valid")
        self.assertEqual(new_result.generated_ligand_status, "present")
        self.assertIsNotNone(new_result.predicted_covalent_edge)
        self.assertEqual(new_result.covalent_edge_score, 0.95)

    def test_preserves_existing_artifacts(self) -> None:
        adapter = self._adapter()
        ligand_ref = ArtifactRef(uri="sample_0_ligand.sdf", sha256="a" * 64,
                                 format="sdf", role="ligand_sdf", bytes=2048)
        result = CovalentGenerationResult(
            request_id="test", sample_id=0,
            residue_reaction_family="CYS_MICHAEL_ADDITION",
            target_atom_identity=ProteinAtomIdentity(
                chain_id="A", residue_number=145, residue_name="CYS", atom_name="SG"),
            generation_validity_status="valid",
            complex_export_status="not_applicable",
            docking_eligibility_status="not_applicable",
            docking_run_status="not_applicable",
            primary_failure_reason=None,
            secondary_failure_reasons=(),
            generated_ligand_status="present",
            artifacts={"ligand_sdf": ligand_ref},
        )
        new_result = adapter(result)
        self.assertIn("ligand_sdf", new_result.artifacts)
        self.assertEqual(new_result.artifacts["ligand_sdf"], ligand_ref)

    def test_sets_failure_statuses_and_reason(self) -> None:
        adapter = self._adapter()
        result = _make_valid_result()
        new_result = adapter(result)
        self.assertEqual(new_result.complex_export_status, "failed")
        self.assertEqual(new_result.docking_eligibility_status, "not_applicable")
        self.assertEqual(new_result.docking_run_status, "not_applicable")
        self.assertEqual(new_result.primary_failure_reason, "COMPLEX_EXPORT_FAILED")


# ===================================================================
# 8.  Task 28 ResultWriter compatibility (2 tests)
# ===================================================================


class Task28ResultWriterCompatibilityTests(unittest.TestCase):
    """Ensure ResultWriter.write() accepts results from both adapters."""

    def test_result_writer_accepts_success_adapter_output(self) -> None:
        from covalent_design.inference.complex_export import export_covalent_complex_result
        from covalent_design.inference.result_writer import ResultWriter

        root = _tmp_root()
        try:
            new_result = export_covalent_complex_result(
                result=_make_valid_result(),
                protein_atom_table=_prot_ref(root),
                ligand_coords=_COORDS,
                ligand_atom_types=_TYPES,
                ligand_bonds=_BONDS,
                covalent_edge=_EDGE,
                out_path=root / "out.mmcif",
                artifact_root=root,
            )
            row = ResultWriter().write(new_result)
            self.assertEqual(row["complex_export_status"], "exported")
            self.assertEqual(row["docking_eligibility_status"], "eligible")
            self.assertIn("complex_mmcif", row["artifacts"])
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_result_writer_accepts_failure_adapter_output(self) -> None:
        from covalent_design.inference.complex_export import adapt_complex_export_failure
        from covalent_design.inference.result_writer import ResultWriter

        result = adapt_complex_export_failure(_make_valid_result())
        row = ResultWriter().write(result)
        self.assertEqual(row["complex_export_status"], "failed")
        self.assertEqual(row["docking_run_status"], "not_applicable")
        self.assertEqual(row["primary_failure_reason"], "COMPLEX_EXPORT_FAILED")


# ===================================================================
# 9.  Source guards (3 tests)
# ===================================================================


class SourceGuardTests(unittest.TestCase):
    """Scope guard: no heavy deps, no wrong task imports, clean fixture dir."""

    def test_no_heavy_imports(self) -> None:
        heavy = {"torch", "rdkit", "pmdm", "pocketflow"}
        violations = [m for m in sys.modules
                      for h in heavy
                      if m.lower() == h or m.lower().startswith(h + ".")]
        self.assertEqual(violations, [],
                         f"heavy dependencies in sys.modules: {violations}")

    def test_no_task30_or_docking_imports(self) -> None:
        sources = (
            ROOT / "src" / "covalent_design" / "inference" / "complex_export.py",
            ROOT / "src" / "covalent_design" / "io" / "mmcif_writer.py",
        )
        for source_path in sources:
            with self.subTest(source=source_path.name):
                source = source_path.read_text(encoding="utf-8")
                self.assertNotIn("covalent_design.evaluation", source)
                self.assertNotIn("docking_protocol", source)

    def test_fixture_dir_contains_only_expected_files(self) -> None:
        allowed = {
            "protein_atom_table.json",
            "protein_atom_table_no_target.json",
            "protein_atom_table_empty.json",
            "protein_atom_table_unreadable.json",
            "golden_complex.mmcif",
        }
        actual = {p.name for p in FIXTURES.iterdir() if p.is_file()}
        self.assertEqual(actual - allowed, set(),
                         f"unexpected fixtures: {actual - allowed}")


if __name__ == "__main__":
    unittest.main()
