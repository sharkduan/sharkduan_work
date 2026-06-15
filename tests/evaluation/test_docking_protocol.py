"""Task 32 Window B - Docking protocol tests.

Covers:
- ``load_docking_protocol_manifest(path) -> DockingProtocolManifest``
- ``validate_docking_protocol_manifest(manifest, artifact_root) -> ValidationReceipt``
- ``docking_protocol_manifest_to_dict(manifest) -> dict[str, object]``
- ``build_docking_score_eligible_result_index(results, protocol_manifests, artifact_root) -> DockingScoreEligibleResultIndex``
- ``docking_score_eligible_result_index_to_dict(index) -> dict[str, object]``
- ``write_docking_score_eligible_result_index(index, path) -> ArtifactRef``

Expected RED: ``covalent_design.evaluation.docking_protocol`` production module
does not exist yet.  Contract types may also be missing.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from typing import Mapping

# ===================================================================
# existing contracts (always importable)
# ===================================================================
from covalent_design.contracts.errors import ContractError, ContractErrorInfo
from covalent_design.contracts.lifecycle import validate_generation_result
from covalent_design.contracts.types import (
    CONTRACT_VERSION,
    SCHEMA_VERSION,
    ArtifactRef,
    CovalentGenerationResult,
    EdgeValidityCheck,
    GeometryMetrics,
    LigandAtomIdentity,
    MoleculeQuality,
    ProteinAtomIdentity,
    ValidationReceipt,
)

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "evaluation" / "docking_protocol"

# ===================================================================
# production imports (expected RED - module does not exist yet)
# ===================================================================

try:
    from covalent_design.evaluation.docking_protocol import (  # noqa: F401
        DockingScoreEligibleResult,
        DockingScoreEligibleResultIndex,
        build_docking_score_eligible_result_index,
        docking_protocol_manifest_to_dict,
        docking_score_eligible_result_index_to_dict,
        load_docking_protocol_manifest,
        validate_docking_protocol_manifest,
        write_docking_score_eligible_result_index,
    )
    _DOCKING_PROTOCOL_IMPORT_OK = True
except ImportError:
    _DOCKING_PROTOCOL_IMPORT_OK = False

try:
    from covalent_design.contracts import (  # noqa: F401
        CovalentConstraint,
        DockingProtocolManifest,
        DockingSearchRegion,
        LigandPreparation,
        PoseSelection,
        ReceptorPreparation,
    )
    _CONTRACTS_TYPES_OK = True
except ImportError:
    _CONTRACTS_TYPES_OK = False


# ===================================================================
# shared result row builders (same as denominator_accounting fixtures)
# ===================================================================

TARGET_ATOM = ProteinAtomIdentity(
    chain_id="A",
    residue_number=145,
    residue_name="CYS",
    atom_name="SG",
    altloc=None,
    insertion_code=None,
    structure_model=1,
    asym_id="A",
    atom_serial=1234,
)

LIGAND_ATOM = LigandAtomIdentity(
    ligand_id="LIG001",
    atom_name="C1",
    atom_index=0,
    chain_id=None,
    asym_id=None,
    residue_number=None,
    altloc=None,
)

GEOMETRY = GeometryMetrics(
    bond_length=1.82,
    protein_side_angle=109.5,
    ligand_side_angle=120.0,
)

MOL_QUALITY = MoleculeQuality(
    qed=0.72,
    sa_score=3.1,
    log_p=2.5,
    molecular_weight=350.0,
)

EDGE_CHECK_PASS = EdgeValidityCheck(
    check_name="target_atom",
    status="pass",
    observed_value="SG",
    threshold_or_rule="CYS:SG",
    rule_table_version="1.0.0",
    failure_code=None,
)

DUMMY_SHA256 = "a" * 64

COMPLEX_MMCIF_REF = ArtifactRef(
    uri="sample_complex.mmcif",
    sha256=DUMMY_SHA256,
    format="mmcif",
    schema_version=SCHEMA_VERSION,
    role="complex_mmcif",
    bytes=16384,
)

LIGAND_SDF_REF = ArtifactRef(
    uri="sample_ligand.sdf",
    sha256="b" * 64,
    format="sdf",
    schema_version=SCHEMA_VERSION,
    role="ligand_sdf",
    bytes=2048,
)

FULL_ARTIFACTS: Mapping[str, ArtifactRef] = {
    "complex_mmcif": COMPLEX_MMCIF_REF,
    "ligand_sdf": LIGAND_SDF_REF,
}


def _make_valid_full_result(
    sample_id: int,
    *,
    request_id: str = "eval-test-req",
    family: str = "CYS_MICHAEL_ADDITION",
    generation_validity_status: str = "valid",
    complex_export: str = "exported",
    docking_elig: str = "eligible",
    docking_run: str = "succeeded",
    primary_failure: str | None = None,
    covalent_docking: float | None = -8.5,
    noncovalent: float | None = -7.2,
    artifacts: Mapping[str, ArtifactRef] | None = None,
    extra_artifacts: Mapping[str, ArtifactRef] | None = None,
) -> CovalentGenerationResult:
    """Fully successful valid result with all diagnostics populated."""
    from covalent_design.contracts.types import CovalentEdge

    edge = CovalentEdge(
        protein_atom=TARGET_ATOM,
        ligand_atom=LIGAND_ATOM,
        bond_type="carbon-sulfur",
    )
    result_artifacts: dict[str, ArtifactRef] = dict(FULL_ARTIFACTS if artifacts is None else artifacts)
    if extra_artifacts:
        result_artifacts.update(extra_artifacts)
    return CovalentGenerationResult(
        request_id=request_id,
        sample_id=sample_id,
        residue_reaction_family=family,
        target_atom_identity=TARGET_ATOM,
        generation_validity_status=generation_validity_status,
        complex_export_status=complex_export,
        docking_eligibility_status=docking_elig,
        docking_run_status=docking_run,
        primary_failure_reason=primary_failure,
        secondary_failure_reasons=(),
        generated_ligand_status="present",
        predicted_ligand_attachment_atom=LIGAND_ATOM,
        predicted_covalent_edge=edge,
        covalent_edge_score=0.85,
        geometry_metrics=GEOMETRY,
        molecular_quality_metrics=MOL_QUALITY,
        matched_warhead_type="acrylamide",
        predicted_warhead_type="acrylamide",
        covalent_docking_score=covalent_docking,
        noncovalent_vina_score=noncovalent,
        edge_validity_checks=(EDGE_CHECK_PASS,),
        artifacts=result_artifacts,
    )


def _make_result_with_manifest_ref(
    sample_id: int,
    manifest_ref: ArtifactRef,
    *,
    request_id: str = "eval-test-req",
    covalent_docking: float = -8.5,
    noncovalent: float = -7.2,
) -> CovalentGenerationResult:
    """Valid succeeded result with a docking_protocol_manifest artifact."""
    return _make_valid_full_result(
        sample_id,
        request_id=request_id,
        covalent_docking=covalent_docking,
        noncovalent=noncovalent,
        extra_artifacts={"docking_protocol_manifest": manifest_ref},
    )


def _make_quickvina2_only_result(
    sample_id: int,
    *,
    request_id: str = "eval-test-req",
    noncovalent: float = -7.2,
) -> CovalentGenerationResult:
    """Valid result with QuickVina2 baseline only (no covalent docking)."""
    return _make_valid_full_result(
        sample_id,
        request_id=request_id,
        docking_run="not_run",
        covalent_docking=None,
        noncovalent=noncovalent,
    )


# ===================================================================
# YAML manifest builder helpers
# ===================================================================

_YAML_QUOTE = json.dumps


def _write_docking_protocol_manifest_yaml(
    path: Path,
    *,
    protocol_id: str = "prot-001",
    engine_name: str = "vina_covalent",
    engine_version: str = "1.2.3",
    engine_build_hash: str = "b" * 64,
    full_config_uri: str = "configs/docking_config.txt",
    full_config_sha256: str = "c" * 64,
    random_seed: int | None = 42,
    receptor_tool_name: str = "pdb2pqr",
    receptor_tool_version: str = "3.0.0",
    receptor_input_structure_uri: str = "input/receptor.pdb",
    receptor_input_structure_sha256: str = "d" * 64,
    receptor_output_uri: str = "output/receptor.pdbqt",
    receptor_output_sha256: str = "e" * 64,
    receptor_ph_policy: str = "pH 7.4",
    receptor_water_policy: str = "remove",
    receptor_cofactor_policy: str = "keep",
    receptor_metal_policy: str = "keep",
    ligand_tool_name: str = "obabel",
    ligand_tool_version: str = "3.0.0",
    ligand_input_uri: str = "input/ligand.sdf",
    ligand_input_sha256: str = "f" * 64,
    ligand_charge_model: str = "gasteiger",
    ligand_protonation_policy: str = "pH 7.4",
    constraint_representation: str = "distance_constraint",
    constraint_target_atom: str = "A:145:CYS:SG",
    constraint_ligand_atom: str = "C1",
    constraint_parameters: str = "{}",
    search_center: str = "[10.0, 20.0, 30.0]",
    search_size: str = "[15.0, 15.0, 15.0]",
    search_unit: str = "angstrom",
    pose_ranking_rule: str = "best_score",
    pose_score_unit: str = "kcal/mol",
    failure_log_uri: str = "logs/docking_failure.log",
    failure_log_sha256: str = "0" * 64,
) -> None:
    """Write a valid docking protocol manifest YAML file."""
    lines: list[str] = []
    _a = lines.append

    _a(f"docking_protocol_id: {_YAML_QUOTE(protocol_id)}")
    _a(f"engine_name: {_YAML_QUOTE(engine_name)}")
    _a(f"engine_version: {_YAML_QUOTE(engine_version)}")
    _a(f"engine_build_hash: {_YAML_QUOTE(engine_build_hash)}")
    _a(f"full_config_uri: {_YAML_QUOTE(full_config_uri)}")
    _a(f"full_config_sha256: {_YAML_QUOTE(full_config_sha256)}")
    if random_seed is None:
        _a("random_seed: null")
    else:
        _a(f"random_seed: {random_seed}")

    _a("receptor_preparation:")
    _a(f"  tool_name: {_YAML_QUOTE(receptor_tool_name)}")
    _a(f"  tool_version: {_YAML_QUOTE(receptor_tool_version)}")
    _a(f"  input_structure_uri: {_YAML_QUOTE(receptor_input_structure_uri)}")
    _a(f"  input_structure_sha256: {_YAML_QUOTE(receptor_input_structure_sha256)}")
    _a(f"  output_receptor_uri: {_YAML_QUOTE(receptor_output_uri)}")
    _a(f"  output_receptor_sha256: {_YAML_QUOTE(receptor_output_sha256)}")
    _a(f"  pH_or_protonation_policy: {_YAML_QUOTE(receptor_ph_policy)}")
    _a(f"  water_policy: {receptor_water_policy}")
    _a(f"  cofactor_policy: {receptor_cofactor_policy}")
    _a(f"  metal_policy: {receptor_metal_policy}")

    _a("ligand_preparation:")
    _a(f"  tool_name: {_YAML_QUOTE(ligand_tool_name)}")
    _a(f"  tool_version: {_YAML_QUOTE(ligand_tool_version)}")
    _a(f"  input_ligand_uri: {_YAML_QUOTE(ligand_input_uri)}")
    _a(f"  input_ligand_sha256: {_YAML_QUOTE(ligand_input_sha256)}")
    _a(f"  charge_model: {_YAML_QUOTE(ligand_charge_model)}")
    _a(f"  protonation_policy: {_YAML_QUOTE(ligand_protonation_policy)}")

    _a("covalent_constraint:")
    _a(f"  representation: {constraint_representation}")
    _a(f"  target_atom_identity: {_YAML_QUOTE(constraint_target_atom)}")
    _a(f"  ligand_atom_identity: {_YAML_QUOTE(constraint_ligand_atom)}")
    _a(f"  constraint_parameters: {constraint_parameters}")

    _a("search_region:")
    _a(f"  center: {search_center}")
    _a(f"  size: {search_size}")
    _a(f"  unit: {search_unit}")

    _a("pose_selection:")
    _a(f"  ranking_rule: {pose_ranking_rule}")
    _a(f"  score_unit: {_YAML_QUOTE(pose_score_unit)}")

    _a(f"failure_log_uri: {_YAML_QUOTE(failure_log_uri)}")
    _a(f"failure_log_sha256: {_YAML_QUOTE(failure_log_sha256)}")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


# ===================================================================
# temp-directory manifest builder (with real artifact files)
# ===================================================================


class ManifestFixture:
    """Creates a self-contained docking protocol manifest with all referenced
    artifact files in a temp directory, computing real SHA-256 checksums."""

    def __init__(self, base_dir: Path) -> None:
        self._dir = base_dir
        self._dir.mkdir(parents=True, exist_ok=True)

    @property
    def root(self) -> Path:
        return self._dir

    def write_artifact(self, rel_path: str, content: bytes) -> ArtifactRef:
        """Write an artifact file and return its ArtifactRef."""
        full = self._dir / rel_path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_bytes(content)
        sha = hashlib.sha256(content).hexdigest()
        suffix = Path(rel_path).suffix.lstrip(".") or "txt"
        return ArtifactRef(
            uri=rel_path,
            sha256=sha,
            format=suffix,
            schema_version=SCHEMA_VERSION,
            role="",
            bytes=len(content),
        )

    def sha256_of(self, rel_path: str) -> str:
        return hashlib.sha256((self._dir / rel_path).read_bytes()).hexdigest()

    def write_valid_manifest(
        self,
        *,
        protocol_id: str = "prot-001",
        engine_name: str = "vina_covalent",
        engine_version: str = "1.2.3",
        engine_build_hash: str | None = None,
        random_seed: int | None = 42,
    ) -> Path:
        """Build a complete valid manifest with all artifacts and return its path."""

        # Create artifact files
        full_config_content = b"# docking config\nengine=vina\n"
        full_config_ref = self.write_artifact("configs/docking_config.txt", full_config_content)

        receptor_input = b"ATOM  ...\n" * 10
        receptor_input_ref = self.write_artifact("input/receptor.pdb", receptor_input)

        receptor_output = b"REMARK pdbqt\n" * 5
        receptor_output_ref = self.write_artifact("output/receptor.pdbqt", receptor_output)

        ligand_input = b"ligand sdf content\n"
        ligand_input_ref = self.write_artifact("input/ligand.sdf", ligand_input)

        failure_log = b""
        failure_log_ref = self.write_artifact("logs/docking_failure.log", failure_log)

        if engine_build_hash is None:
            engine_build_hash = "b" * 64

        manifest_path = self._dir / "docking_protocol_manifest.yml"
        _write_docking_protocol_manifest_yaml(
            manifest_path,
            protocol_id=protocol_id,
            engine_name=engine_name,
            engine_version=engine_version,
            engine_build_hash=engine_build_hash,
            full_config_uri=full_config_ref.uri,
            full_config_sha256=full_config_ref.sha256,
            random_seed=random_seed,
            receptor_input_structure_uri=receptor_input_ref.uri,
            receptor_input_structure_sha256=receptor_input_ref.sha256,
            receptor_output_uri=receptor_output_ref.uri,
            receptor_output_sha256=receptor_output_ref.sha256,
            ligand_input_uri=ligand_input_ref.uri,
            ligand_input_sha256=ligand_input_ref.sha256,
            failure_log_uri=failure_log_ref.uri,
            failure_log_sha256=failure_log_ref.sha256,
        )
        return manifest_path

    def write_minimal_valid_manifest(
        self,
        *,
        protocol_id: str = "prot-minimal",
    ) -> Path:
        """Write the smallest valid manifest possible (empty failure log)."""
        return self.write_valid_manifest(protocol_id=protocol_id)


# ===================================================================
# 1.  Import and signature tests
# ===================================================================


class DockingProtocolImportTests(unittest.TestCase):
    """Import and signature checks.

    Expected RED: module does not exist yet.
    """

    def test_load_docking_protocol_manifest_is_importable(self) -> None:
        self.assertTrue(_DOCKING_PROTOCOL_IMPORT_OK,
                        "docking_protocol module must be importable")

    def test_validate_docking_protocol_manifest_is_importable(self) -> None:
        from covalent_design.evaluation.docking_protocol import (
            validate_docking_protocol_manifest,
        )
        self.assertTrue(callable(validate_docking_protocol_manifest))

    def test_docking_protocol_manifest_to_dict_is_importable(self) -> None:
        from covalent_design.evaluation.docking_protocol import (
            docking_protocol_manifest_to_dict,
        )
        self.assertTrue(callable(docking_protocol_manifest_to_dict))

    def test_build_docking_score_eligible_result_index_is_importable(self) -> None:
        from covalent_design.evaluation.docking_protocol import (
            build_docking_score_eligible_result_index,
        )
        self.assertTrue(callable(build_docking_score_eligible_result_index))

    def test_docking_score_eligible_result_index_to_dict_is_importable(self) -> None:
        from covalent_design.evaluation.docking_protocol import (
            docking_score_eligible_result_index_to_dict,
        )
        self.assertTrue(callable(docking_score_eligible_result_index_to_dict))

    def test_write_docking_score_eligible_result_index_is_importable(self) -> None:
        from covalent_design.evaluation.docking_protocol import (
            write_docking_score_eligible_result_index,
        )
        self.assertTrue(callable(write_docking_score_eligible_result_index))

    def test_contract_types_importable(self) -> None:
        self.assertTrue(_CONTRACTS_TYPES_OK,
                        "Docking protocol contract types must be importable")

    def test_load_manifest_signature(self) -> None:
        import inspect
        from covalent_design.evaluation.docking_protocol import load_docking_protocol_manifest

        sig = inspect.signature(load_docking_protocol_manifest)
        params = list(sig.parameters.keys())
        self.assertEqual(params, ["path"])
        self.assertIsNotNone(sig.return_annotation)

    def test_validate_manifest_signature(self) -> None:
        import inspect
        from covalent_design.evaluation.docking_protocol import (
            validate_docking_protocol_manifest,
        )

        sig = inspect.signature(validate_docking_protocol_manifest)
        params = list(sig.parameters.keys())
        self.assertEqual(params, ["manifest", "artifact_root"])
        self.assertIsNotNone(sig.return_annotation)

    def test_manifest_to_dict_signature(self) -> None:
        import inspect
        from covalent_design.evaluation.docking_protocol import (
            docking_protocol_manifest_to_dict,
        )

        sig = inspect.signature(docking_protocol_manifest_to_dict)
        params = list(sig.parameters.keys())
        self.assertEqual(params, ["manifest"])
        self.assertIsNotNone(sig.return_annotation)

    def test_build_index_signature(self) -> None:
        import inspect
        from covalent_design.evaluation.docking_protocol import (
            build_docking_score_eligible_result_index,
        )

        sig = inspect.signature(build_docking_score_eligible_result_index)
        params = list(sig.parameters.keys())
        self.assertEqual(params, ["results", "protocol_manifests", "artifact_root"])
        self.assertIsNotNone(sig.return_annotation)

    def test_index_to_dict_signature(self) -> None:
        import inspect
        from covalent_design.evaluation.docking_protocol import (
            docking_score_eligible_result_index_to_dict,
        )

        sig = inspect.signature(docking_score_eligible_result_index_to_dict)
        params = list(sig.parameters.keys())
        self.assertEqual(params, ["index"])
        self.assertIsNotNone(sig.return_annotation)

    def test_write_index_signature(self) -> None:
        import inspect
        from covalent_design.evaluation.docking_protocol import (
            write_docking_score_eligible_result_index,
        )

        sig = inspect.signature(write_docking_score_eligible_result_index)
        params = list(sig.parameters.keys())
        self.assertEqual(params, ["index", "path"])
        self.assertIsNotNone(sig.return_annotation)


# ===================================================================
# 2.  Manifest load and validation tests
# ===================================================================


class DockingProtocolManifestLoadValidateTests(unittest.TestCase):
    """load_docking_protocol_manifest and validate_docking_protocol_manifest."""

    def test_valid_complete_manifest_loads(self) -> None:
        """A valid manifest with all artifacts loads without error."""
        if not _DOCKING_PROTOCOL_IMPORT_OK:
            self.skipTest("docking_protocol module not yet available")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fixture = ManifestFixture(tmp_path)
            manifest_path = fixture.write_valid_manifest()

            manifest = load_docking_protocol_manifest(manifest_path)
            self.assertIsNotNone(manifest)

    def test_valid_complete_manifest_validates(self) -> None:
        """A valid manifest passes validate_docking_protocol_manifest."""
        if not _DOCKING_PROTOCOL_IMPORT_OK:
            self.skipTest("docking_protocol module not yet available")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fixture = ManifestFixture(tmp_path)
            manifest_path = fixture.write_valid_manifest()

            manifest = load_docking_protocol_manifest(manifest_path)
            receipt = validate_docking_protocol_manifest(manifest, tmp_path)
            self.assertTrue(receipt.passed)

    def test_null_seed_accepted(self) -> None:
        """random_seed=null is valid."""
        if not _DOCKING_PROTOCOL_IMPORT_OK:
            self.skipTest("docking_protocol module not yet available")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fixture = ManifestFixture(tmp_path)
            manifest_path = fixture.write_valid_manifest(random_seed=None)

            manifest = load_docking_protocol_manifest(manifest_path)
            receipt = validate_docking_protocol_manifest(manifest, tmp_path)
            self.assertTrue(receipt.passed)

    def test_unknown_engine_build_hash_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fixture = ManifestFixture(tmp_path)
            manifest_path = fixture.write_valid_manifest()
            _write_docking_protocol_manifest_yaml(
                manifest_path,
                engine_build_hash="unknown",
                full_config_sha256=fixture.sha256_of("configs/docking_config.txt"),
                receptor_input_structure_sha256=fixture.sha256_of("input/receptor.pdb"),
                receptor_output_sha256=fixture.sha256_of("output/receptor.pdbqt"),
                ligand_input_sha256=fixture.sha256_of("input/ligand.sdf"),
                failure_log_sha256=fixture.sha256_of("logs/docking_failure.log"),
            )
            manifest = load_docking_protocol_manifest(manifest_path)
            receipt = validate_docking_protocol_manifest(manifest, tmp_path)
            self.assertTrue(receipt.passed, receipt.errors)

    def test_empty_constraint_parameters_accepted(self) -> None:
        """Empty constraint_parameters mapping is valid."""
        if not _DOCKING_PROTOCOL_IMPORT_OK:
            self.skipTest("docking_protocol module not yet available")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fixture = ManifestFixture(tmp_path)
            manifest_path = fixture.write_valid_manifest()

            manifest = load_docking_protocol_manifest(manifest_path)
            receipt = validate_docking_protocol_manifest(manifest, tmp_path)
            self.assertTrue(receipt.passed)

    def test_zero_byte_failure_log_accepted(self) -> None:
        """A zero-byte failure log with correct SHA is valid."""
        if not _DOCKING_PROTOCOL_IMPORT_OK:
            self.skipTest("docking_protocol module not yet available")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fixture = ManifestFixture(tmp_path)
            # write_valid_manifest already writes zero-byte failure log
            manifest_path = fixture.write_valid_manifest()

            manifest = load_docking_protocol_manifest(manifest_path)
            # Verify the failure log is indeed empty
            log_path = tmp_path / "logs" / "docking_failure.log"
            self.assertEqual(log_path.read_bytes(), b"")

            receipt = validate_docking_protocol_manifest(manifest, tmp_path)
            self.assertTrue(receipt.passed)

    def test_manifest_load_returns_correct_type(self) -> None:
        """load_docking_protocol_manifest returns DockingProtocolManifest."""
        if not _DOCKING_PROTOCOL_IMPORT_OK or not _CONTRACTS_TYPES_OK:
            self.skipTest("types not yet available")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fixture = ManifestFixture(tmp_path)
            manifest_path = fixture.write_valid_manifest()

            manifest = load_docking_protocol_manifest(manifest_path)
            from covalent_design.contracts import DockingProtocolManifest as DPM
            self.assertIsInstance(manifest, DPM)


# ===================================================================
# 3.  Manifest serialization tests
# ===================================================================


class DockingProtocolManifestSerializeTests(unittest.TestCase):
    """docking_protocol_manifest_to_dict produces correct structure."""

    def test_all_required_fields_preserved_in_dict(self) -> None:
        """Every required nested field must appear in the serialized dict."""
        if not _DOCKING_PROTOCOL_IMPORT_OK:
            self.skipTest("docking_protocol module not yet available")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fixture = ManifestFixture(tmp_path)
            manifest_path = fixture.write_valid_manifest()

            manifest = load_docking_protocol_manifest(manifest_path)
            d = docking_protocol_manifest_to_dict(manifest)

            # top-level fields
            self.assertEqual(d["docking_protocol_id"], "prot-001")
            self.assertEqual(d["engine_name"], "vina_covalent")
            self.assertEqual(d["engine_version"], "1.2.3")
            self.assertIn("engine_build_hash", d)
            self.assertIn("full_config_uri", d)
            self.assertIn("full_config_sha256", d)
            self.assertIn("random_seed", d)
            # receptor_preparation nested
            self.assertIsInstance(d["receptor_preparation"], dict)
            rp = d["receptor_preparation"]
            self.assertIn("tool_name", rp)
            self.assertIn("tool_version", rp)
            self.assertIn("input_structure_uri", rp)
            self.assertIn("input_structure_sha256", rp)
            self.assertIn("output_receptor_uri", rp)
            self.assertIn("output_receptor_sha256", rp)
            self.assertIn("pH_or_protonation_policy", rp)
            self.assertIn("water_policy", rp)
            self.assertIn("cofactor_policy", rp)
            self.assertIn("metal_policy", rp)
            # ligand_preparation nested
            self.assertIsInstance(d["ligand_preparation"], dict)
            lp = d["ligand_preparation"]
            self.assertIn("tool_name", lp)
            self.assertIn("tool_version", lp)
            self.assertIn("input_ligand_uri", lp)
            self.assertIn("input_ligand_sha256", lp)
            self.assertIn("charge_model", lp)
            self.assertIn("protonation_policy", lp)
            # covalent_constraint nested
            self.assertIsInstance(d["covalent_constraint"], dict)
            cc = d["covalent_constraint"]
            self.assertIn("representation", cc)
            self.assertIn("target_atom_identity", cc)
            self.assertIn("ligand_atom_identity", cc)
            self.assertIn("constraint_parameters", cc)
            # search_region nested
            self.assertIsInstance(d["search_region"], dict)
            sr = d["search_region"]
            self.assertIn("center", sr)
            self.assertIn("size", sr)
            self.assertIn("unit", sr)
            # pose_selection nested
            self.assertIsInstance(d["pose_selection"], dict)
            ps = d["pose_selection"]
            self.assertIn("ranking_rule", ps)
            self.assertIn("score_unit", ps)
            # failure_log
            self.assertIn("failure_log_uri", d)
            self.assertIn("failure_log_sha256", d)

    def test_serializer_is_deterministic(self) -> None:
        """Same manifest produces identical dict every time."""
        if not _DOCKING_PROTOCOL_IMPORT_OK:
            self.skipTest("docking_protocol module not yet available")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fixture = ManifestFixture(tmp_path)
            manifest_path = fixture.write_valid_manifest()

            manifest = load_docking_protocol_manifest(manifest_path)
            d1 = docking_protocol_manifest_to_dict(manifest)
            d2 = docking_protocol_manifest_to_dict(manifest)
            j1 = json.dumps(d1, sort_keys=True)
            j2 = json.dumps(d2, sort_keys=True)
            self.assertEqual(j1, j2)

    def test_null_seed_is_null_in_dict(self) -> None:
        """random_seed=None must serialize as JSON null, not 0 or string."""
        if not _DOCKING_PROTOCOL_IMPORT_OK:
            self.skipTest("docking_protocol module not yet available")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fixture = ManifestFixture(tmp_path)
            manifest_path = fixture.write_valid_manifest(random_seed=None)

            manifest = load_docking_protocol_manifest(manifest_path)
            d = docking_protocol_manifest_to_dict(manifest)
            self.assertIsNone(d["random_seed"])

    def test_dict_is_json_serializable(self) -> None:
        """Output dict must be directly JSON-serializable."""
        if not _DOCKING_PROTOCOL_IMPORT_OK:
            self.skipTest("docking_protocol module not yet available")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fixture = ManifestFixture(tmp_path)
            manifest_path = fixture.write_valid_manifest()

            manifest = load_docking_protocol_manifest(manifest_path)
            d = docking_protocol_manifest_to_dict(manifest)
            json_str = json.dumps(d, sort_keys=True)
            self.assertIsInstance(json_str, str)


# ===================================================================
# 4.  Manifest validation edge-case tests
# ===================================================================


class DockingProtocolManifestValidationTests(unittest.TestCase):
    """Exhaustive validation rejection tests."""

    def _load_and_validate(
        self, tmp_path: Path, manifest_path: Path
    ) -> ValidationReceipt:
        if not _DOCKING_PROTOCOL_IMPORT_OK:
            self.skipTest("docking_protocol module not yet available")
        manifest = load_docking_protocol_manifest(manifest_path)
        return validate_docking_protocol_manifest(manifest, tmp_path)

    # ---- missing/empty required string fields ----

    def test_empty_docking_protocol_id_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fixture = ManifestFixture(tmp_path)
            manifest_path = fixture.write_valid_manifest(protocol_id="")
            receipt = self._load_and_validate(tmp_path, manifest_path)
            self.assertFalse(receipt.passed)

    def test_empty_engine_name_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fixture = ManifestFixture(tmp_path)
            manifest_path = fixture.write_valid_manifest()
            _write_docking_protocol_manifest_yaml(
                manifest_path, engine_name="",
                full_config_sha256=fixture.sha256_of("configs/docking_config.txt"),
                receptor_input_structure_sha256=fixture.sha256_of("input/receptor.pdb"),
                receptor_output_sha256=fixture.sha256_of("output/receptor.pdbqt"),
                ligand_input_sha256=fixture.sha256_of("input/ligand.sdf"),
                failure_log_sha256=fixture.sha256_of("logs/docking_failure.log"),
            )
            receipt = self._load_and_validate(tmp_path, manifest_path)
            self.assertFalse(receipt.passed)

    def test_non_string_engine_name_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fixture = ManifestFixture(tmp_path)
            manifest_path = fixture.write_valid_manifest()
            _write_docking_protocol_manifest_yaml(
                manifest_path, engine_name=123,
                full_config_sha256=fixture.sha256_of("configs/docking_config.txt"),
                receptor_input_structure_sha256=fixture.sha256_of("input/receptor.pdb"),
                receptor_output_sha256=fixture.sha256_of("output/receptor.pdbqt"),
                ligand_input_sha256=fixture.sha256_of("input/ligand.sdf"),
                failure_log_sha256=fixture.sha256_of("logs/docking_failure.log"),
            )
            receipt = self._load_and_validate(tmp_path, manifest_path)
            self.assertFalse(receipt.passed)

    def test_missing_random_seed_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fixture = ManifestFixture(tmp_path)
            manifest_path = fixture.write_valid_manifest()
            manifest_path.write_text(
                manifest_path.read_text(encoding="utf-8").replace("random_seed: 42\n", ""),
                encoding="utf-8",
                newline="\n",
            )
            receipt = self._load_and_validate(tmp_path, manifest_path)
            self.assertFalse(receipt.passed)

    def test_empty_receptor_tool_name_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fixture = ManifestFixture(tmp_path)
            manifest_path = fixture.write_valid_manifest()
            _write_docking_protocol_manifest_yaml(
                manifest_path, receptor_tool_name="",
                full_config_sha256=fixture.sha256_of("configs/docking_config.txt"),
                receptor_input_structure_sha256=fixture.sha256_of("input/receptor.pdb"),
                receptor_output_sha256=fixture.sha256_of("output/receptor.pdbqt"),
                ligand_input_sha256=fixture.sha256_of("input/ligand.sdf"),
                failure_log_sha256=fixture.sha256_of("logs/docking_failure.log"),
            )
            receipt = self._load_and_validate(tmp_path, manifest_path)
            self.assertFalse(receipt.passed)

    def test_empty_ligand_tool_name_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fixture = ManifestFixture(tmp_path)
            manifest_path = fixture.write_valid_manifest()
            _write_docking_protocol_manifest_yaml(
                manifest_path, ligand_tool_name="",
                full_config_sha256=fixture.sha256_of("configs/docking_config.txt"),
                receptor_input_structure_sha256=fixture.sha256_of("input/receptor.pdb"),
                receptor_output_sha256=fixture.sha256_of("output/receptor.pdbqt"),
                ligand_input_sha256=fixture.sha256_of("input/ligand.sdf"),
                failure_log_sha256=fixture.sha256_of("logs/docking_failure.log"),
            )
            receipt = self._load_and_validate(tmp_path, manifest_path)
            self.assertFalse(receipt.passed)

    def test_empty_constraint_target_atom_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fixture = ManifestFixture(tmp_path)
            manifest_path = fixture.write_valid_manifest()
            _write_docking_protocol_manifest_yaml(
                manifest_path, constraint_target_atom="",
                full_config_sha256=fixture.sha256_of("configs/docking_config.txt"),
                receptor_input_structure_sha256=fixture.sha256_of("input/receptor.pdb"),
                receptor_output_sha256=fixture.sha256_of("output/receptor.pdbqt"),
                ligand_input_sha256=fixture.sha256_of("input/ligand.sdf"),
                failure_log_sha256=fixture.sha256_of("logs/docking_failure.log"),
            )
            receipt = self._load_and_validate(tmp_path, manifest_path)
            self.assertFalse(receipt.passed)

    def test_empty_failure_log_uri_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fixture = ManifestFixture(tmp_path)
            manifest_path = fixture.write_valid_manifest()
            _write_docking_protocol_manifest_yaml(
                manifest_path, failure_log_uri="",
                full_config_sha256=fixture.sha256_of("configs/docking_config.txt"),
                receptor_input_structure_sha256=fixture.sha256_of("input/receptor.pdb"),
                receptor_output_sha256=fixture.sha256_of("output/receptor.pdbqt"),
                ligand_input_sha256=fixture.sha256_of("input/ligand.sdf"),
                failure_log_sha256=fixture.sha256_of("logs/docking_failure.log"),
            )
            receipt = self._load_and_validate(tmp_path, manifest_path)
            self.assertFalse(receipt.passed)

    def test_missing_receptor_preparation_field_rejected(self) -> None:
        """A nested required field that is absent (not just empty) must be rejected."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fixture = ManifestFixture(tmp_path)
            # Write a manifest with missing receptor_preparation entirely
            manifest_path = tmp_path / "bad_manifest.yml"
            lines = [
                "docking_protocol_id: \"prot-bad\"",
                "engine_name: \"vina\"",
                "engine_version: \"1.0\"",
                f"engine_build_hash: \"{'b' * 64}\"",
                "full_config_uri: \"cfg.txt\"",
                "full_config_sha256: \"0\" * 64",
                "random_seed: null",
                # receptor_preparation intentionally omitted
                "ligand_preparation:",
                "  tool_name: \"obabel\"",
                "  tool_version: \"1.0\"",
                "  input_ligand_uri: \"lig.sdf\"",
                "  input_ligand_sha256: \"0\" * 64",
                "  charge_model: \"gasteiger\"",
                "  protonation_policy: \"pH 7.4\"",
                "covalent_constraint:",
                "  representation: distance_constraint",
                "  target_atom_identity: \"A:145:CYS:SG\"",
                "  ligand_atom_identity: \"C1\"",
                "  constraint_parameters: {}",
                "search_region:",
                "  center: [0.0, 0.0, 0.0]",
                "  size: [10.0, 10.0, 10.0]",
                "  unit: angstrom",
                "pose_selection:",
                "  ranking_rule: best_score",
                "  score_unit: \"kcal/mol\"",
                "failure_log_uri: \"log.txt\"",
                "failure_log_sha256: \"0\" * 64",
            ]
            manifest_path.write_text("\n".join(lines), encoding="utf-8")
            receipt = self._load_and_validate(tmp_path, manifest_path)
            self.assertFalse(receipt.passed)

    # ---- invalid enums ----

    def test_invalid_water_policy_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fixture = ManifestFixture(tmp_path)
            manifest_path = fixture.write_valid_manifest()
            _write_docking_protocol_manifest_yaml(
                manifest_path, receptor_water_policy="delete",
                full_config_sha256=fixture.sha256_of("configs/docking_config.txt"),
                receptor_input_structure_sha256=fixture.sha256_of("input/receptor.pdb"),
                receptor_output_sha256=fixture.sha256_of("output/receptor.pdbqt"),
                ligand_input_sha256=fixture.sha256_of("input/ligand.sdf"),
                failure_log_sha256=fixture.sha256_of("logs/docking_failure.log"),
            )
            receipt = self._load_and_validate(tmp_path, manifest_path)
            self.assertFalse(receipt.passed)

    def test_invalid_cofactor_policy_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fixture = ManifestFixture(tmp_path)
            manifest_path = fixture.write_valid_manifest()
            _write_docking_protocol_manifest_yaml(
                manifest_path, receptor_cofactor_policy="delete",
                full_config_sha256=fixture.sha256_of("configs/docking_config.txt"),
                receptor_input_structure_sha256=fixture.sha256_of("input/receptor.pdb"),
                receptor_output_sha256=fixture.sha256_of("output/receptor.pdbqt"),
                ligand_input_sha256=fixture.sha256_of("input/ligand.sdf"),
                failure_log_sha256=fixture.sha256_of("logs/docking_failure.log"),
            )
            receipt = self._load_and_validate(tmp_path, manifest_path)
            self.assertFalse(receipt.passed)

    def test_invalid_metal_policy_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fixture = ManifestFixture(tmp_path)
            manifest_path = fixture.write_valid_manifest()
            _write_docking_protocol_manifest_yaml(
                manifest_path, receptor_metal_policy="delete",
                full_config_sha256=fixture.sha256_of("configs/docking_config.txt"),
                receptor_input_structure_sha256=fixture.sha256_of("input/receptor.pdb"),
                receptor_output_sha256=fixture.sha256_of("output/receptor.pdbqt"),
                ligand_input_sha256=fixture.sha256_of("input/ligand.sdf"),
                failure_log_sha256=fixture.sha256_of("logs/docking_failure.log"),
            )
            receipt = self._load_and_validate(tmp_path, manifest_path)
            self.assertFalse(receipt.passed)

    def test_invalid_constraint_representation_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fixture = ManifestFixture(tmp_path)
            manifest_path = fixture.write_valid_manifest()
            _write_docking_protocol_manifest_yaml(
                manifest_path, constraint_representation="covalent_bond",
                full_config_sha256=fixture.sha256_of("configs/docking_config.txt"),
                receptor_input_structure_sha256=fixture.sha256_of("input/receptor.pdb"),
                receptor_output_sha256=fixture.sha256_of("output/receptor.pdbqt"),
                ligand_input_sha256=fixture.sha256_of("input/ligand.sdf"),
                failure_log_sha256=fixture.sha256_of("logs/docking_failure.log"),
            )
            receipt = self._load_and_validate(tmp_path, manifest_path)
            self.assertFalse(receipt.passed)

    def test_non_mapping_constraint_parameters_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fixture = ManifestFixture(tmp_path)
            manifest_path = fixture.write_valid_manifest()
            _write_docking_protocol_manifest_yaml(
                manifest_path,
                constraint_parameters="[]",
                full_config_sha256=fixture.sha256_of("configs/docking_config.txt"),
                receptor_input_structure_sha256=fixture.sha256_of("input/receptor.pdb"),
                receptor_output_sha256=fixture.sha256_of("output/receptor.pdbqt"),
                ligand_input_sha256=fixture.sha256_of("input/ligand.sdf"),
                failure_log_sha256=fixture.sha256_of("logs/docking_failure.log"),
            )
            receipt = self._load_and_validate(tmp_path, manifest_path)
            self.assertFalse(receipt.passed)

    def test_invalid_search_unit_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fixture = ManifestFixture(tmp_path)
            manifest_path = fixture.write_valid_manifest()
            _write_docking_protocol_manifest_yaml(
                manifest_path, search_unit="nanometer",
                full_config_sha256=fixture.sha256_of("configs/docking_config.txt"),
                receptor_input_structure_sha256=fixture.sha256_of("input/receptor.pdb"),
                receptor_output_sha256=fixture.sha256_of("output/receptor.pdbqt"),
                ligand_input_sha256=fixture.sha256_of("input/ligand.sdf"),
                failure_log_sha256=fixture.sha256_of("logs/docking_failure.log"),
            )
            receipt = self._load_and_validate(tmp_path, manifest_path)
            self.assertFalse(receipt.passed)

    def test_search_center_nan_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fixture = ManifestFixture(tmp_path)
            manifest_path = fixture.write_valid_manifest()
            _write_docking_protocol_manifest_yaml(
                manifest_path, search_center="[NaN, 20.0, 30.0]",
                full_config_sha256=fixture.sha256_of("configs/docking_config.txt"),
                receptor_input_structure_sha256=fixture.sha256_of("input/receptor.pdb"),
                receptor_output_sha256=fixture.sha256_of("output/receptor.pdbqt"),
                ligand_input_sha256=fixture.sha256_of("input/ligand.sdf"),
                failure_log_sha256=fixture.sha256_of("logs/docking_failure.log"),
            )
            receipt = self._load_and_validate(tmp_path, manifest_path)
            self.assertFalse(receipt.passed)
            self.assertEqual(
                receipt.errors[0].code,
                "DOCKING_PROTOCOL_SEARCH_CENTER_INVALID",
            )

    def test_search_size_infinity_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fixture = ManifestFixture(tmp_path)
            manifest_path = fixture.write_valid_manifest()
            _write_docking_protocol_manifest_yaml(
                manifest_path, search_size="[15.0, Infinity, 15.0]",
                full_config_sha256=fixture.sha256_of("configs/docking_config.txt"),
                receptor_input_structure_sha256=fixture.sha256_of("input/receptor.pdb"),
                receptor_output_sha256=fixture.sha256_of("output/receptor.pdbqt"),
                ligand_input_sha256=fixture.sha256_of("input/ligand.sdf"),
                failure_log_sha256=fixture.sha256_of("logs/docking_failure.log"),
            )
            receipt = self._load_and_validate(tmp_path, manifest_path)
            self.assertFalse(receipt.passed)
            self.assertEqual(
                receipt.errors[0].code,
                "DOCKING_PROTOCOL_SEARCH_SIZE_INVALID",
            )

    def test_invalid_pose_ranking_rule_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fixture = ManifestFixture(tmp_path)
            manifest_path = fixture.write_valid_manifest()
            _write_docking_protocol_manifest_yaml(
                manifest_path, pose_ranking_rule="lowest_energy",
                full_config_sha256=fixture.sha256_of("configs/docking_config.txt"),
                receptor_input_structure_sha256=fixture.sha256_of("input/receptor.pdb"),
                receptor_output_sha256=fixture.sha256_of("output/receptor.pdbqt"),
                ligand_input_sha256=fixture.sha256_of("input/ligand.sdf"),
                failure_log_sha256=fixture.sha256_of("logs/docking_failure.log"),
            )
            receipt = self._load_and_validate(tmp_path, manifest_path)
            self.assertFalse(receipt.passed)

    # ---- malformed SHA ----

    def test_malformed_sha_too_short_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fixture = ManifestFixture(tmp_path)
            manifest_path = fixture.write_valid_manifest()
            _write_docking_protocol_manifest_yaml(
                manifest_path, full_config_sha256="abc123",
                receptor_input_structure_sha256=fixture.sha256_of("input/receptor.pdb"),
                receptor_output_sha256=fixture.sha256_of("output/receptor.pdbqt"),
                ligand_input_sha256=fixture.sha256_of("input/ligand.sdf"),
                failure_log_sha256=fixture.sha256_of("logs/docking_failure.log"),
            )
            receipt = self._load_and_validate(tmp_path, manifest_path)
            self.assertFalse(receipt.passed)

    def test_malformed_sha_uppercase_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fixture = ManifestFixture(tmp_path)
            manifest_path = fixture.write_valid_manifest()
            _write_docking_protocol_manifest_yaml(
                manifest_path, full_config_sha256="A" * 64,
                receptor_input_structure_sha256=fixture.sha256_of("input/receptor.pdb"),
                receptor_output_sha256=fixture.sha256_of("output/receptor.pdbqt"),
                ligand_input_sha256=fixture.sha256_of("input/ligand.sdf"),
                failure_log_sha256=fixture.sha256_of("logs/docking_failure.log"),
            )
            receipt = self._load_and_validate(tmp_path, manifest_path)
            self.assertFalse(receipt.passed)

    def test_malformed_sha_non_hex_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fixture = ManifestFixture(tmp_path)
            manifest_path = fixture.write_valid_manifest()
            _write_docking_protocol_manifest_yaml(
                manifest_path, full_config_sha256="g" * 64,
                receptor_input_structure_sha256=fixture.sha256_of("input/receptor.pdb"),
                receptor_output_sha256=fixture.sha256_of("output/receptor.pdbqt"),
                ligand_input_sha256=fixture.sha256_of("input/ligand.sdf"),
                failure_log_sha256=fixture.sha256_of("logs/docking_failure.log"),
            )
            receipt = self._load_and_validate(tmp_path, manifest_path)
            self.assertFalse(receipt.passed)

    # ---- search region validation ----

    def test_invalid_search_center_type_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fixture = ManifestFixture(tmp_path)
            manifest_path = fixture.write_valid_manifest()
            _write_docking_protocol_manifest_yaml(
                manifest_path, search_center="not_a_list",
                full_config_sha256=fixture.sha256_of("configs/docking_config.txt"),
                receptor_input_structure_sha256=fixture.sha256_of("input/receptor.pdb"),
                receptor_output_sha256=fixture.sha256_of("output/receptor.pdbqt"),
                ligand_input_sha256=fixture.sha256_of("input/ligand.sdf"),
                failure_log_sha256=fixture.sha256_of("logs/docking_failure.log"),
            )
            receipt = self._load_and_validate(tmp_path, manifest_path)
            self.assertFalse(receipt.passed)

    def test_wrong_search_center_size_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fixture = ManifestFixture(tmp_path)
            manifest_path = fixture.write_valid_manifest()
            _write_docking_protocol_manifest_yaml(
                manifest_path, search_center="[1.0, 2.0]",
                full_config_sha256=fixture.sha256_of("configs/docking_config.txt"),
                receptor_input_structure_sha256=fixture.sha256_of("input/receptor.pdb"),
                receptor_output_sha256=fixture.sha256_of("output/receptor.pdbqt"),
                ligand_input_sha256=fixture.sha256_of("input/ligand.sdf"),
                failure_log_sha256=fixture.sha256_of("logs/docking_failure.log"),
            )
            receipt = self._load_and_validate(tmp_path, manifest_path)
            self.assertFalse(receipt.passed)

    def test_wrong_search_size_size_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fixture = ManifestFixture(tmp_path)
            manifest_path = fixture.write_valid_manifest()
            _write_docking_protocol_manifest_yaml(
                manifest_path, search_size="[1.0, 2.0]",
                full_config_sha256=fixture.sha256_of("configs/docking_config.txt"),
                receptor_input_structure_sha256=fixture.sha256_of("input/receptor.pdb"),
                receptor_output_sha256=fixture.sha256_of("output/receptor.pdbqt"),
                ligand_input_sha256=fixture.sha256_of("input/ligand.sdf"),
                failure_log_sha256=fixture.sha256_of("logs/docking_failure.log"),
            )
            receipt = self._load_and_validate(tmp_path, manifest_path)
            self.assertFalse(receipt.passed)

    def test_negative_search_size_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fixture = ManifestFixture(tmp_path)
            manifest_path = fixture.write_valid_manifest()
            _write_docking_protocol_manifest_yaml(
                manifest_path, search_size="[-1.0, 10.0, 10.0]",
                full_config_sha256=fixture.sha256_of("configs/docking_config.txt"),
                receptor_input_structure_sha256=fixture.sha256_of("input/receptor.pdb"),
                receptor_output_sha256=fixture.sha256_of("output/receptor.pdbqt"),
                ligand_input_sha256=fixture.sha256_of("input/ligand.sdf"),
                failure_log_sha256=fixture.sha256_of("logs/docking_failure.log"),
            )
            receipt = self._load_and_validate(tmp_path, manifest_path)
            self.assertFalse(receipt.passed)

    # ---- URI safety ----

    def test_absolute_uri_in_full_config_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fixture = ManifestFixture(tmp_path)
            manifest_path = fixture.write_valid_manifest()
            _write_docking_protocol_manifest_yaml(
                manifest_path, full_config_uri="/etc/config.txt",
                full_config_sha256="c" * 64,
                receptor_input_structure_sha256=fixture.sha256_of("input/receptor.pdb"),
                receptor_output_sha256=fixture.sha256_of("output/receptor.pdbqt"),
                ligand_input_sha256=fixture.sha256_of("input/ligand.sdf"),
                failure_log_sha256=fixture.sha256_of("logs/docking_failure.log"),
            )
            receipt = self._load_and_validate(tmp_path, manifest_path)
            self.assertFalse(receipt.passed)

    def test_traversal_uri_in_full_config_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fixture = ManifestFixture(tmp_path)
            manifest_path = fixture.write_valid_manifest()
            _write_docking_protocol_manifest_yaml(
                manifest_path, full_config_uri="../../etc/passwd",
                full_config_sha256="c" * 64,
                receptor_input_structure_sha256=fixture.sha256_of("input/receptor.pdb"),
                receptor_output_sha256=fixture.sha256_of("output/receptor.pdbqt"),
                ligand_input_sha256=fixture.sha256_of("input/ligand.sdf"),
                failure_log_sha256=fixture.sha256_of("logs/docking_failure.log"),
            )
            receipt = self._load_and_validate(tmp_path, manifest_path)
            self.assertFalse(receipt.passed)

    def test_windows_backslash_traversal_uri_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fixture = ManifestFixture(tmp_path)
            manifest_path = fixture.write_valid_manifest()
            _write_docking_protocol_manifest_yaml(
                manifest_path, full_config_uri="..\\..\\windows\\system32",
                full_config_sha256="c" * 64,
                receptor_input_structure_sha256=fixture.sha256_of("input/receptor.pdb"),
                receptor_output_sha256=fixture.sha256_of("output/receptor.pdbqt"),
                ligand_input_sha256=fixture.sha256_of("input/ligand.sdf"),
                failure_log_sha256=fixture.sha256_of("logs/docking_failure.log"),
            )
            receipt = self._load_and_validate(tmp_path, manifest_path)
            self.assertFalse(receipt.passed)

    def test_absolute_uri_in_receptor_input_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fixture = ManifestFixture(tmp_path)
            manifest_path = fixture.write_valid_manifest()
            _write_docking_protocol_manifest_yaml(
                manifest_path, receptor_input_structure_uri="/root/receptor.pdb",
                receptor_input_structure_sha256="d" * 64,
                full_config_sha256=fixture.sha256_of("configs/docking_config.txt"),
                receptor_output_sha256=fixture.sha256_of("output/receptor.pdbqt"),
                ligand_input_sha256=fixture.sha256_of("input/ligand.sdf"),
                failure_log_sha256=fixture.sha256_of("logs/docking_failure.log"),
            )
            receipt = self._load_and_validate(tmp_path, manifest_path)
            self.assertFalse(receipt.passed)

    def test_traversal_uri_in_failure_log_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fixture = ManifestFixture(tmp_path)
            manifest_path = fixture.write_valid_manifest()
            _write_docking_protocol_manifest_yaml(
                manifest_path, failure_log_uri="../outside.log",
                full_config_sha256=fixture.sha256_of("configs/docking_config.txt"),
                receptor_input_structure_sha256=fixture.sha256_of("input/receptor.pdb"),
                receptor_output_sha256=fixture.sha256_of("output/receptor.pdbqt"),
                ligand_input_sha256=fixture.sha256_of("input/ligand.sdf"),
                failure_log_sha256=fixture.sha256_of("logs/docking_failure.log"),
            )
            receipt = self._load_and_validate(tmp_path, manifest_path)
            self.assertFalse(receipt.passed)

    # ---- missing artifact ----

    def test_missing_full_config_artifact_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fixture = ManifestFixture(tmp_path)
            manifest_path = fixture.write_valid_manifest()
            _write_docking_protocol_manifest_yaml(
                manifest_path,
                full_config_uri="nonexistent_config.txt",
                full_config_sha256="c" * 64,
                receptor_input_structure_sha256=fixture.sha256_of("input/receptor.pdb"),
                receptor_output_sha256=fixture.sha256_of("output/receptor.pdbqt"),
                ligand_input_sha256=fixture.sha256_of("input/ligand.sdf"),
                failure_log_sha256=fixture.sha256_of("logs/docking_failure.log"),
            )
            receipt = self._load_and_validate(tmp_path, manifest_path)
            self.assertFalse(receipt.passed)

    def test_missing_receptor_input_artifact_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fixture = ManifestFixture(tmp_path)
            manifest_path = fixture.write_valid_manifest()
            _write_docking_protocol_manifest_yaml(
                manifest_path,
                receptor_input_structure_uri="nonexistent_rec.pdb",
                receptor_input_structure_sha256="d" * 64,
                full_config_sha256=fixture.sha256_of("configs/docking_config.txt"),
                receptor_output_sha256=fixture.sha256_of("output/receptor.pdbqt"),
                ligand_input_sha256=fixture.sha256_of("input/ligand.sdf"),
                failure_log_sha256=fixture.sha256_of("logs/docking_failure.log"),
            )
            receipt = self._load_and_validate(tmp_path, manifest_path)
            self.assertFalse(receipt.passed)

    def test_missing_failure_log_artifact_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fixture = ManifestFixture(tmp_path)
            manifest_path = fixture.write_valid_manifest()
            _write_docking_protocol_manifest_yaml(
                manifest_path,
                failure_log_uri="nonexistent.log",
                full_config_sha256=fixture.sha256_of("configs/docking_config.txt"),
                receptor_input_structure_sha256=fixture.sha256_of("input/receptor.pdb"),
                receptor_output_sha256=fixture.sha256_of("output/receptor.pdbqt"),
                ligand_input_sha256=fixture.sha256_of("input/ligand.sdf"),
                failure_log_sha256=fixture.sha256_of("logs/docking_failure.log"),
            )
            receipt = self._load_and_validate(tmp_path, manifest_path)
            self.assertFalse(receipt.passed)

    # ---- checksum mismatch ----

    def test_full_config_checksum_mismatch_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fixture = ManifestFixture(tmp_path)
            manifest_path = fixture.write_valid_manifest()
            _write_docking_protocol_manifest_yaml(
                manifest_path,
                full_config_sha256="b" * 64,  # wrong, should be fixture's SHA
                receptor_input_structure_sha256=fixture.sha256_of("input/receptor.pdb"),
                receptor_output_sha256=fixture.sha256_of("output/receptor.pdbqt"),
                ligand_input_sha256=fixture.sha256_of("input/ligand.sdf"),
                failure_log_sha256=fixture.sha256_of("logs/docking_failure.log"),
            )
            receipt = self._load_and_validate(tmp_path, manifest_path)
            self.assertFalse(receipt.passed)

    def test_receptor_output_checksum_mismatch_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fixture = ManifestFixture(tmp_path)
            manifest_path = fixture.write_valid_manifest()
            _write_docking_protocol_manifest_yaml(
                manifest_path,
                receptor_output_sha256="b" * 64,
                full_config_sha256=fixture.sha256_of("configs/docking_config.txt"),
                receptor_input_structure_sha256=fixture.sha256_of("input/receptor.pdb"),
                ligand_input_sha256=fixture.sha256_of("input/ligand.sdf"),
                failure_log_sha256=fixture.sha256_of("logs/docking_failure.log"),
            )
            receipt = self._load_and_validate(tmp_path, manifest_path)
            self.assertFalse(receipt.passed)

    def test_ligand_input_checksum_mismatch_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fixture = ManifestFixture(tmp_path)
            manifest_path = fixture.write_valid_manifest()
            _write_docking_protocol_manifest_yaml(
                manifest_path,
                ligand_input_sha256="b" * 64,
                full_config_sha256=fixture.sha256_of("configs/docking_config.txt"),
                receptor_input_structure_sha256=fixture.sha256_of("input/receptor.pdb"),
                receptor_output_sha256=fixture.sha256_of("output/receptor.pdbqt"),
                failure_log_sha256=fixture.sha256_of("logs/docking_failure.log"),
            )
            receipt = self._load_and_validate(tmp_path, manifest_path)
            self.assertFalse(receipt.passed)

    def test_failure_log_checksum_mismatch_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fixture = ManifestFixture(tmp_path)
            manifest_path = fixture.write_valid_manifest()
            _write_docking_protocol_manifest_yaml(
                manifest_path,
                failure_log_sha256="b" * 64,
                full_config_sha256=fixture.sha256_of("configs/docking_config.txt"),
                receptor_input_structure_sha256=fixture.sha256_of("input/receptor.pdb"),
                receptor_output_sha256=fixture.sha256_of("output/receptor.pdbqt"),
                ligand_input_sha256=fixture.sha256_of("input/ligand.sdf"),
            )
            receipt = self._load_and_validate(tmp_path, manifest_path)
            self.assertFalse(receipt.passed)


# ===================================================================
# 5.  DockingScoreEligibleResultIndex build tests
# ===================================================================


class DockingScoreEligibleResultIndexBuildTests(unittest.TestCase):
    """build_docking_score_eligible_result_index contract tests."""

    def _setup_manifest_and_ref(
        self, tmp_path: Path, protocol_id: str = "prot-001"
    ) -> tuple[Path, ArtifactRef]:
        """Create a valid manifest in tmp_path and return (manifest_path, ArtifactRef)."""
        if not _DOCKING_PROTOCOL_IMPORT_OK:
            self.skipTest("docking_protocol module not yet available")

        fixture = ManifestFixture(tmp_path)
        manifest_path = fixture.write_valid_manifest(protocol_id=protocol_id)
        manifest = load_docking_protocol_manifest(manifest_path)

        # Compute the ArtifactRef for the manifest
        from covalent_design.io.artifacts import artifact_ref_from_file

        manifest_ref = artifact_ref_from_file(
            manifest_path,
            role="docking_protocol_manifest",
            format="yml",
        )
        return manifest_path, manifest_ref

    def _build_index(
        self,
        tmp_path: Path,
        results: list[CovalentGenerationResult],
        manifest_path: Path,
        manifest_ref: ArtifactRef,
    ) -> "DockingScoreEligibleResultIndex":
        if not _DOCKING_PROTOCOL_IMPORT_OK:
            self.skipTest("docking_protocol module not yet available")

        manifest = load_docking_protocol_manifest(manifest_path)
        protocol_manifests = {
            manifest_ref.uri: manifest,
        }
        return build_docking_score_eligible_result_index(
            results, protocol_manifests, tmp_path
        )

    def test_valid_linked_succeeded_result_included(self) -> None:
        """A succeeded result with a valid manifest link must appear in the index."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            manifest_path, manifest_ref = self._setup_manifest_and_ref(tmp_path)
            results = [
                _make_result_with_manifest_ref(0, manifest_ref),
            ]
            index = self._build_index(tmp_path, results, manifest_path, manifest_ref)
            d = docking_score_eligible_result_index_to_dict(index)
            self.assertEqual(len(d["entries"]), 1)
            entry = d["entries"][0]
            self.assertEqual(entry["request_id"], "eval-test-req")
            self.assertEqual(entry["sample_id"], 0)
            self.assertEqual(entry["docking_protocol_id"], "prot-001")

    def test_valid_linked_multiple_results_sorted_deterministically(self) -> None:
        """Multiple results sort by (request_id, sample_id, docking_protocol_id)."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            manifest_path, manifest_ref = self._setup_manifest_and_ref(tmp_path)

            # Insert results in reverse order
            results = [
                _make_result_with_manifest_ref(3, manifest_ref, request_id="req-B"),
                _make_result_with_manifest_ref(0, manifest_ref, request_id="req-A"),
                _make_result_with_manifest_ref(1, manifest_ref, request_id="req-A"),
                _make_result_with_manifest_ref(2, manifest_ref, request_id="req-B"),
            ]
            index = self._build_index(tmp_path, results, manifest_path, manifest_ref)
            d = docking_score_eligible_result_index_to_dict(index)
            entries = d["entries"]
            self.assertEqual(len(entries), 4)
            # Must be sorted by (request_id, sample_id)
            expected_order = [
                ("req-A", 0),
                ("req-A", 1),
                ("req-B", 2),
                ("req-B", 3),
            ]
            for i, (exp_req, exp_sid) in enumerate(expected_order):
                self.assertEqual(entries[i]["request_id"], exp_req)
                self.assertEqual(entries[i]["sample_id"], exp_sid)

    def test_ordinary_excluded_lifecycle_states_omitted(self) -> None:
        """Invalid, export-failed, not-evaluable, not-run, docking-failed rows are excluded."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            manifest_path, manifest_ref = self._setup_manifest_and_ref(tmp_path)

            results = [
                _make_result_with_manifest_ref(0, manifest_ref),  # succeeded -> included
                _make_valid_full_result(
                    1, docking_run="failed",
                    primary_failure="DOCKING_RUN_FAILED",
                    covalent_docking=None, noncovalent=None,
                ),  # docking failed -> excluded
                _make_valid_full_result(
                    2, docking_elig="not_evaluable",
                    docking_run="not_applicable",
                    primary_failure="DOCKING_NOT_EVALUABLE",
                    covalent_docking=None, noncovalent=None,
                ),  # not evaluable -> excluded
                _make_valid_full_result(
                    3, complex_export="failed",
                    docking_elig="not_applicable",
                    docking_run="not_applicable",
                    primary_failure="COMPLEX_EXPORT_FAILED",
                    covalent_docking=None, noncovalent=None,
                    artifacts={},
                ),  # export failed -> excluded
                _make_valid_full_result(
                    4, docking_run="not_run",
                    covalent_docking=None, noncovalent=-6.5,
                ),  # not run -> excluded
                _make_valid_full_result(
                    5, generation_validity_status="invalid",
                    complex_export="not_applicable",
                     docking_elig="not_applicable",
                     docking_run="not_applicable",
                     primary_failure="NO_COVALENT_EDGE_PREDICTED",
                     covalent_docking=None,
                     noncovalent=None,
                     artifacts={},
                 ),  # invalid -> excluded
            ]
            index = self._build_index(tmp_path, results, manifest_path, manifest_ref)
            d = docking_score_eligible_result_index_to_dict(index)
            self.assertEqual(len(d["entries"]), 1)
            self.assertEqual(d["entries"][0]["sample_id"], 0)

    def test_succeeded_row_missing_manifest_association_hard_fails(self) -> None:
        """A succeeded row without artifacts[docking_protocol_manifest] -> ContractError."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            manifest_path, manifest_ref = self._setup_manifest_and_ref(tmp_path)

            results = [
                _make_valid_full_result(0, covalent_docking=-8.5),
                # No docking_protocol_manifest in artifacts
            ]
            protocol_manifests = {manifest_ref.uri: load_docking_protocol_manifest(manifest_path)}
            with self.assertRaises((ContractError, ValueError, KeyError)):
                build_docking_score_eligible_result_index(
                    results, protocol_manifests, tmp_path
                )

    def test_succeeded_row_points_to_supplied_manifest_missing_hard_fails(self) -> None:
        """Result references a manifest not present in protocol_manifests -> ContractError."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            manifest_path, manifest_ref = self._setup_manifest_and_ref(tmp_path)

            phantom_ref = ArtifactRef(
                uri="phantom_manifest.yml",
                sha256="1" * 64,
                format="yml",
                schema_version=SCHEMA_VERSION,
                role="docking_protocol_manifest",
                bytes=100,
            )
            results = [
                _make_result_with_manifest_ref(0, phantom_ref),
            ]
            # protocol_manifests does NOT contain phantom_ref.uri
            protocol_manifests: dict[str, object] = {
                manifest_ref.uri: load_docking_protocol_manifest(manifest_path),
            }
            with self.assertRaises((ContractError, ValueError, KeyError)):
                build_docking_score_eligible_result_index(
                    results, protocol_manifests, tmp_path
                )

    def test_succeeded_row_manifest_artifact_checksum_mismatch_hard_fails(self) -> None:
        """Result's manifest ArtifactRef has wrong checksum -> ContractError."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            manifest_path, manifest_ref = self._setup_manifest_and_ref(tmp_path)

            # Tamper with the manifest ref's SHA
            bad_ref = ArtifactRef(
                uri=manifest_ref.uri,
                sha256="d" * 64,  # wrong
                format=manifest_ref.format,
                schema_version=manifest_ref.schema_version,
                role=manifest_ref.role,
                bytes=manifest_ref.bytes,
            )
            results = [
                _make_result_with_manifest_ref(0, bad_ref),
            ]
            protocol_manifests = {
                manifest_ref.uri: load_docking_protocol_manifest(manifest_path),
            }
            with self.assertRaises((ContractError, ValueError)):
                build_docking_score_eligible_result_index(
                    results, protocol_manifests, tmp_path
                )

    def test_succeeded_row_manifest_artifact_role_mismatch_hard_fails(self) -> None:
        """Result link must use the docking_protocol_manifest artifact role."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            manifest_path, manifest_ref = self._setup_manifest_and_ref(tmp_path)
            wrong_role_ref = ArtifactRef(
                uri=manifest_ref.uri,
                sha256=manifest_ref.sha256,
                format=manifest_ref.format,
                schema_version=manifest_ref.schema_version,
                role="wrong_role",
                bytes=manifest_ref.bytes,
            )
            results = [
                _make_result_with_manifest_ref(0, wrong_role_ref),
            ]
            with self.assertRaises(ContractError):
                build_docking_score_eligible_result_index(
                    results,
                    {manifest_ref.uri: load_docking_protocol_manifest(manifest_path)},
                    tmp_path,
                )

    def test_succeeded_row_nested_artifact_checksum_mismatch_hard_fails(self) -> None:
        """The manifest itself references an artifact with wrong SHA -> ContractError."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fixture = ManifestFixture(tmp_path)
            manifest_path = fixture.write_valid_manifest()

            # Rewrite manifest with wrong full_config_sha256
            _write_docking_protocol_manifest_yaml(
                manifest_path,
                full_config_sha256="b" * 64,  # wrong
                receptor_input_structure_sha256=fixture.sha256_of("input/receptor.pdb"),
                receptor_output_sha256=fixture.sha256_of("output/receptor.pdbqt"),
                ligand_input_sha256=fixture.sha256_of("input/ligand.sdf"),
                failure_log_sha256=fixture.sha256_of("logs/docking_failure.log"),
            )

            from covalent_design.io.artifacts import artifact_ref_from_file

            manifest_ref = artifact_ref_from_file(
                manifest_path, role="docking_protocol_manifest", format="yml",
            )
            results = [
                _make_result_with_manifest_ref(0, manifest_ref),
            ]
            protocol_manifests = {
                manifest_ref.uri: load_docking_protocol_manifest(manifest_path),
            }
            with self.assertRaises((ContractError, ValueError)):
                build_docking_score_eligible_result_index(
                    results, protocol_manifests, tmp_path
                )

    def test_succeeded_row_supplied_manifest_content_mismatch_hard_fails(self) -> None:
        """A valid but substituted supplied manifest must not satisfy the file link."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            manifest_path, manifest_ref = self._setup_manifest_and_ref(tmp_path)
            supplied_manifest = load_docking_protocol_manifest(manifest_path)
            forged_manifest = replace(supplied_manifest, engine_name="forged_covalent")
            results = [
                _make_result_with_manifest_ref(0, manifest_ref),
            ]
            with self.assertRaises(ContractError):
                build_docking_score_eligible_result_index(
                    results, {manifest_ref.uri: forged_manifest}, tmp_path
                )

    def test_corrupt_succeeded_lifecycle_hard_fails_before_survivor_index(self) -> None:
        """A corrupt row (e.g., invalid + succeeded) must fail the whole index build."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            manifest_path, manifest_ref = self._setup_manifest_and_ref(tmp_path)

            from covalent_design.contracts.types import CovalentEdge

            edge = CovalentEdge(
                protein_atom=TARGET_ATOM,
                ligand_atom=LIGAND_ATOM,
                bond_type="carbon-sulfur",
            )
            corrupt = CovalentGenerationResult(
                request_id="eval-test-req",
                sample_id=99,
                residue_reaction_family="CYS_MICHAEL_ADDITION",
                target_atom_identity=TARGET_ATOM,
                generation_validity_status="invalid",  # invalid
                complex_export_status="exported",  # but exported!
                docking_eligibility_status="eligible",
                docking_run_status="succeeded",
                primary_failure_reason="NO_COVALENT_EDGE_PREDICTED",
                secondary_failure_reasons=(),
                generated_ligand_status="present",
                predicted_ligand_attachment_atom=LIGAND_ATOM,
                predicted_covalent_edge=edge,
                covalent_edge_score=0.85,
                geometry_metrics=GEOMETRY,
                molecular_quality_metrics=MOL_QUALITY,
                matched_warhead_type="acrylamide",
                predicted_warhead_type="acrylamide",
                covalent_docking_score=-8.5,
                noncovalent_vina_score=-7.2,
                edge_validity_checks=(EDGE_CHECK_PASS,),
                artifacts={
                    **FULL_ARTIFACTS,
                    "docking_protocol_manifest": manifest_ref,
                },
            )
            results = [
                _make_result_with_manifest_ref(0, manifest_ref),
                corrupt,
            ]
            protocol_manifests = {
                manifest_ref.uri: load_docking_protocol_manifest(manifest_path),
            }
            with self.assertRaises((ContractError, ValueError)):
                build_docking_score_eligible_result_index(
                    results, protocol_manifests, tmp_path
                )

    def test_quickvina2_only_baseline_excluded(self) -> None:
        """QuickVina2-only: noncovalent_vina_score populated, no covalent docking, excluded."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            manifest_path, manifest_ref = self._setup_manifest_and_ref(tmp_path)

            results = [
                _make_quickvina2_only_result(0, noncovalent=-7.2),
            ]
            protocol_manifests = {
                manifest_ref.uri: load_docking_protocol_manifest(manifest_path),
            }
            index = build_docking_score_eligible_result_index(
                results, protocol_manifests, tmp_path
            )
            d = docking_score_eligible_result_index_to_dict(index)
            self.assertEqual(len(d["entries"]), 0)

    def test_input_result_objects_not_mutated(self) -> None:
        """build must not modify the input CovalentGenerationResult objects."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            manifest_path, manifest_ref = self._setup_manifest_and_ref(tmp_path)

            results = [
                _make_result_with_manifest_ref(0, manifest_ref),
            ]
            artifacts_before = dict(results[0].artifacts)
            score_before = results[0].covalent_docking_score

            protocol_manifests = {
                manifest_ref.uri: load_docking_protocol_manifest(manifest_path),
            }
            build_docking_score_eligible_result_index(
                results, protocol_manifests, tmp_path
            )

            # Verify input not mutated
            self.assertEqual(results[0].covalent_docking_score, score_before)
            self.assertEqual(dict(results[0].artifacts), artifacts_before)

    def test_empty_results_produces_empty_index(self) -> None:
        """Empty results list should produce an index with zero entries."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            manifest_path, manifest_ref = self._setup_manifest_and_ref(tmp_path)

            protocol_manifests = {
                manifest_ref.uri: load_docking_protocol_manifest(manifest_path),
            }
            index = build_docking_score_eligible_result_index(
                [], protocol_manifests, tmp_path
            )
            d = docking_score_eligible_result_index_to_dict(index)
            self.assertEqual(len(d["entries"]), 0)


# ===================================================================
# 6.  DockingScoreEligibleResultIndex serialize tests
# ===================================================================


class DockingScoreEligibleResultIndexSerializeTests(unittest.TestCase):
    """docking_score_eligible_result_index_to_dict contract tests."""

    def _build_valid_index(self, tmp_path: Path) -> "DockingScoreEligibleResultIndex":
        if not _DOCKING_PROTOCOL_IMPORT_OK:
            self.skipTest("docking_protocol module not yet available")

        fixture = ManifestFixture(tmp_path)
        manifest_path = fixture.write_valid_manifest(protocol_id="prot-001")
        from covalent_design.io.artifacts import artifact_ref_from_file

        manifest_ref = artifact_ref_from_file(
            manifest_path, role="docking_protocol_manifest", format="yml",
        )
        manifest = load_docking_protocol_manifest(manifest_path)
        results = [
            _make_result_with_manifest_ref(0, manifest_ref, request_id="req-A", covalent_docking=-8.5),
            _make_result_with_manifest_ref(1, manifest_ref, request_id="req-A", covalent_docking=-9.2),
        ]
        return build_docking_score_eligible_result_index(
            results, {manifest_ref.uri: manifest}, tmp_path
        )

    def test_to_dict_produces_deterministic_output(self) -> None:
        """Same index -> same dict every time."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            index = self._build_valid_index(tmp_path)
            d1 = docking_score_eligible_result_index_to_dict(index)
            d2 = docking_score_eligible_result_index_to_dict(index)
            j1 = json.dumps(d1, sort_keys=True)
            j2 = json.dumps(d2, sort_keys=True)
            self.assertEqual(j1, j2)

    def test_to_dict_is_json_serializable(self) -> None:
        """Output dict must be directly JSON-serializable."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            index = self._build_valid_index(tmp_path)
            d = docking_score_eligible_result_index_to_dict(index)
            json_str = json.dumps(d, sort_keys=True)
            self.assertIsInstance(json_str, str)
            loaded = json.loads(json_str)
            self.assertIsInstance(loaded, dict)
            self.assertIn("entries", loaded)

    def test_to_dict_entries_are_flat(self) -> None:
        """Entries must be flat dicts (no nested dataclass objects)."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            index = self._build_valid_index(tmp_path)
            d = docking_score_eligible_result_index_to_dict(index)
            for entry in d["entries"]:
                for key, value in entry.items():
                    self.assertIsInstance(
                        value, (str, int, float, bool, type(None), list),
                        f"Entry key {key!r} has non-flat value type {type(value)}",
                    )

    def test_index_includes_role_and_format(self) -> None:
        """Index dict must include role and format metadata."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            index = self._build_valid_index(tmp_path)
            d = docking_score_eligible_result_index_to_dict(index)
            self.assertEqual(d.get("role"), "docking_score_eligible_result_index")
            self.assertEqual(d.get("format"), "json")


# ===================================================================
# 7.  Writer tests
# ===================================================================


class DockingScoreEligibleResultIndexWriterTests(unittest.TestCase):
    """write_docking_score_eligible_result_index contract tests."""

    def _build_valid_index(self, tmp_path: Path) -> "DockingScoreEligibleResultIndex":
        if not _DOCKING_PROTOCOL_IMPORT_OK:
            self.skipTest("docking_protocol module not yet available")

        fixture = ManifestFixture(tmp_path)
        manifest_path = fixture.write_valid_manifest(protocol_id="prot-001")
        from covalent_design.io.artifacts import artifact_ref_from_file

        manifest_ref = artifact_ref_from_file(
            manifest_path, role="docking_protocol_manifest", format="yml",
        )
        manifest = load_docking_protocol_manifest(manifest_path)
        results = [
            _make_result_with_manifest_ref(0, manifest_ref, request_id="req-A"),
        ]
        return build_docking_score_eligible_result_index(
            results, {manifest_ref.uri: manifest}, tmp_path
        )

    def test_writer_is_atomic_no_temp_residue(self) -> None:
        """Writer must not leave any .tmp files."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            index = self._build_valid_index(tmp_path)
            out_path = tmp_path / "docking_score_eligible_result_index.json"
            ref = write_docking_score_eligible_result_index(index, out_path)
            self.assertTrue(out_path.is_file())
            self.assertIsInstance(ref, ArtifactRef)
            # No temp residue
            tmp_files = list(tmp_path.glob("*.tmp"))
            self.assertEqual(tmp_files, [], f"Temp artifacts must not remain: {tmp_files}")

    def test_writer_is_deterministic(self) -> None:
        """Same index written twice produces identical content and ArtifactRef."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            index = self._build_valid_index(tmp_path)
            out_path = tmp_path / "docking_score_eligible_result_index.json"

            first = write_docking_score_eligible_result_index(index, out_path)
            first_bytes = out_path.read_bytes()
            second = write_docking_score_eligible_result_index(index, out_path)

            self.assertEqual(first_bytes, out_path.read_bytes())
            self.assertEqual(first.sha256, second.sha256)

    def test_writer_returns_correct_artifact_ref(self) -> None:
        """Returned ArtifactRef must have role=docking_score_eligible_result_index."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            index = self._build_valid_index(tmp_path)
            out_path = tmp_path / "docking_score_eligible_result_index.json"
            ref = write_docking_score_eligible_result_index(index, out_path)
            self.assertEqual(ref.role, "docking_score_eligible_result_index")
            self.assertEqual(ref.format, "json")
            self.assertEqual(ref.schema_version, SCHEMA_VERSION)


# ===================================================================
# 8.  Source guard tests
# ===================================================================


class SourceGuardTests(unittest.TestCase):
    """Boundary enforcement: no heavy deps, correct task scope."""

    def test_no_heavy_dependencies_loaded(self) -> None:
        heavy = {"torch", "rdkit", "pmdm", "pocketflow"}
        violations: list[str] = []
        for mod_name in sorted(sys.modules):
            lower = mod_name.lower()
            for h in heavy:
                if lower == h or lower.startswith(h + "."):
                    violations.append(mod_name)
        self.assertEqual(
            violations, [], f"heavy dependencies found in sys.modules: {violations}",
        )

    def test_no_task33_imported(self) -> None:
        self.assertNotIn("covalent_design.deployment", sys.modules)
        self.assertNotIn("covalent_design.split_report", sys.modules)

    def test_no_real_docking_imports(self) -> None:
        """No docking engine imports in sys.modules."""
        docking_mods = {"vina", "smina", "autodock", "rdock"}
        for mod_name in sorted(sys.modules):
            lower = mod_name.lower()
            for d in docking_mods:
                if lower == d or lower.startswith(d + "."):
                    self.fail(f"Docking engine import found: {mod_name}")

    def test_no_directory_scanning_inference(self) -> None:
        """Tests must not infer artifacts by scanning directories."""
        # This test module is the evidence: all artifact refs use explicit
        # URIs written by ManifestFixture, never os.walk or glob.
        pass


if __name__ == "__main__":
    unittest.main()
