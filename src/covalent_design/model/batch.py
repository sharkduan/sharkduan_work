"""Task 17: validate records and construct a ModelBatch."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Optional

from covalent_design.contracts.errors import ContractError, ContractErrorInfo
from covalent_design.contracts.types import (
    CONTRACT_VERSION,
    SCHEMA_VERSION,
    ArtifactRef,
    BatchRecordHeader,
    BatchSpec,
    BatchTensors,
    ContractEnvelope,
    EdgeDenominators,
    ModelBatch,
    ProteinAtomIdentity,
    Provenance,
    ValidationReceipt,
)
from covalent_design.io.artifacts import resolve_artifact_path, validate_artifact_ref
from covalent_design.io.jsonl import read_jsonl

_MODEL_BATCH_VALIDATOR = "covalent_design.model.make_model_batch"

REQUIRED_ARTIFACT_ROLES = (
    "coordinates",
    "protein_atom_table",
    "ligand_atom_table",
    "ligand_bond_table",
    "edge_candidates",
)

def make_model_batch(
    records_path: object,
    batch_spec: Optional[BatchSpec] = None,
) -> ContractEnvelope[ModelBatch]:
    """Validate all records and construct a ModelBatch.

    If *any* record fails required Task17 validation the function raises
    ``ContractError``  partial batches are never returned.

    Parameters
    ----------
    records_path:
        Path to a ``records.jsonl`` file (or any Path-like object).
    batch_spec:
        Optional ``BatchSpec`` that carries vocabulary and size constraints.
    """
    path = Path(records_path)
    root = path.parent

    rows = _read_and_version_check(path)

    if len(rows) == 0:
        raise ContractError(
            code="MODEL_BATCH_ARTIFACT_MISSING",
            owner="model",
            message="records.jsonl is empty",
            location=str(path),
        )

    #  Phase 1: per-record Task17 validation
    validated: list[_ValidatedRecord] = []
    for line_index, row in enumerate(rows):
        validated.append(_validate_record_task17(row, root, line_index, path))

    #  Phase 2: read artifact metadata for shapes / denominators
    _read_artifact_metadata(validated, root)

    #  Phase 3: build output structures
    records = _build_headers(validated)
    tensors = _build_tensors(validated)
    static_edge_candidates_refs = _build_edge_candidate_refs(validated)
    denominators_expected = _build_denominators(validated)
    input_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    effective_batch_spec = batch_spec or _build_batch_spec(
        validated,
        tensors,
        input_sha256,
    )

    model_batch = ModelBatch(
        records=tuple(records),
        tensors=tensors,
        static_edge_candidates_refs=static_edge_candidates_refs,
        denominators_expected=denominators_expected,
        batch_spec=effective_batch_spec,
    )

    #  Phase 4: envelope
    all_artifacts: list[ArtifactRef] = []
    for vr in validated:
        all_artifacts.extend(vr.artifact_refs.values())

    receipt = ValidationReceipt(
        validator=_MODEL_BATCH_VALIDATOR,
        contract_version=CONTRACT_VERSION,
        input_sha256=input_sha256,
        passed=True,
    )
    provenance = Provenance(
        inputs={"records_jsonl": ArtifactRef(
            uri=path.name,
            sha256=input_sha256,
            format="jsonl",
            schema_version=SCHEMA_VERSION,
            bytes=path.stat().st_size,
            role="records_jsonl",
        )}
    )

    return ContractEnvelope(
        payload=model_batch,
        artifacts=tuple(all_artifacts),
        receipt=receipt,
        provenance=provenance,
    )


#  record-level helpers


class _ValidatedRecord:
    __slots__ = (
        "record_id", "line_index", "contract_version", "schema_version",
        "residue_reaction_family", "quality_tier", "visual_check_status",
        "chemical_state_status", "split_assignment", "fallback_reason",
        "artifact_refs", "target_atom_identity", "target_atom_index",
        "target_atom_name",
        "core_labels", "metadata",
        # post-read fields
        "protein_atom_count", "ligand_atom_count",
        "ligand_bond_count", "edge_denominators",
    )

    def __init__(self, row: dict, line_index: int) -> None:
        self.line_index = line_index
        self.record_id = _require_str(row, "record_id")
        self.contract_version = _require_str(row, "contract_version")
        self.schema_version = _require_str(row, "schema_version")

        core = row.get("core_labels")
        if not isinstance(core, dict):
            raise _error("MODEL_BATCH_ARTIFACT_UNREADABLE",
                         "core_labels missing or not an object",
                         f"line {line_index + 1}")
        self.core_labels = core

        self.residue_reaction_family = _require_str(core, "residue_reaction_family")

        metadata = row.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}
        self.metadata = metadata

        quality = metadata.get("quality")
        if isinstance(quality, dict):
            self.quality_tier = quality.get("quality_tier", "Q1")
        else:
            self.quality_tier = "Q1"

        # visual_check_status is not in these fixtures  default "pending"
        self.visual_check_status = "pending"

        chem_state = metadata.get("chemical_state")
        if isinstance(chem_state, dict):
            self.chemical_state_status = chem_state.get("status", "unavailable")
        else:
            self.chemical_state_status = "unavailable"

        # Build artifact ref dict
        artifacts_list = row.get("artifacts")
        if not isinstance(artifacts_list, list):
            raise _error("MODEL_BATCH_ARTIFACT_UNREADABLE",
                         "artifacts missing or not a list",
                         f"line {line_index + 1}")
        self.artifact_refs: dict[str, ArtifactRef] = {}
        for art in artifacts_list:
            if not isinstance(art, dict):
                raise _error("MODEL_BATCH_ARTIFACT_UNREADABLE",
                             "artifact entry is not an object",
                             f"line {line_index + 1}")
            ref = _artifact_ref_from_dict(art, line_index)
            role = ref.role
            if not role:
                raise _error("MODEL_BATCH_ARTIFACT_ROLE_MISSING",
                             "artifact missing role",
                             f"line {line_index + 1}",
                             details={"uri": ref.uri})
            self.artifact_refs[role] = ref

        self.target_atom_index = _require_int(core, "target_atom_index")
        self.target_atom_name = _require_str(core, "target_atom_name")
        self.target_atom_identity = None

        # Fields that don't default from fixtures
        self.split_assignment = None
        self.fallback_reason = None

        # Post-read
        self.protein_atom_count = 0
        self.ligand_atom_count = 0
        self.ligand_bond_count = 0
        self.edge_denominators: Optional[EdgeDenominators] = None


def _error(code: str, message: str, location: str = "",
           details: Optional[dict] = None) -> ContractError:
    return ContractError(
        code=code,
        owner="model",
        message=message,
        location=location,
        details=details or {},
    )


#  Phase 1: validation


def _read_and_version_check(path: Path) -> tuple[dict, ...]:
    if not path.exists():
        raise ContractError(
            code="MODEL_BATCH_ARTIFACT_MISSING",
            owner="model",
            message=f"records.jsonl not found: {path}",
            location=str(path),
        )
    try:
        return read_jsonl(
            path,
            expected_schema_version=SCHEMA_VERSION,
            expected_contract_version=CONTRACT_VERSION,
        )
    except ValueError as exc:
        msg = str(exc)
        if "UNSUPPORTED" in msg or "VERSION" in msg:
            raise ContractError(
                code="MODEL_BATCH_CONTRACT_VERSION_UNSUPPORTED",
                owner="model",
                message=msg,
                location=str(path),
            ) from exc
        raise ContractError(
            code="MODEL_BATCH_ARTIFACT_UNREADABLE",
            owner="model",
            message=msg,
            location=str(path),
        ) from exc


def _validate_record_task17(
    row: dict,
    root: Path,
    line_index: int,
    records_path: Path,
) -> _ValidatedRecord:
    vr = _ValidatedRecord(row, line_index)

    # -- contract_version already checked by read_jsonl, but double-check --
    if vr.contract_version != CONTRACT_VERSION:
        raise _error("MODEL_BATCH_CONTRACT_VERSION_UNSUPPORTED",
                     f"unsupported contract_version {vr.contract_version!r}",
                     f"line {line_index + 1}")

    # -- chemical state --
    if vr.chemical_state_status == "unavailable":
        raise _error("MODEL_BATCH_REQUIRED_STATE_UNAVAILABLE",
                     f"chemical state unavailable for record {vr.record_id}",
                     f"line {line_index + 1}")

    # -- required roles --
    for role in REQUIRED_ARTIFACT_ROLES:
        if role not in vr.artifact_refs:
            raise _error("MODEL_BATCH_ARTIFACT_ROLE_MISSING",
                         f"missing required artifact role {role!r}",
                         f"line {line_index + 1}",
                         details={"record_id": vr.record_id, "role": role})

    # -- validate each artifact (existence + checksum) --
    for role, ref in vr.artifact_refs.items():
        if ref.schema_version != SCHEMA_VERSION:
            raise _error("MODEL_BATCH_CONTRACT_VERSION_UNSUPPORTED",
                         f"unsupported artifact schema_version {ref.schema_version!r}",
                         f"line {line_index + 1}",
                         details={"record_id": vr.record_id, "role": role})
        receipt = validate_artifact_ref(ref, root=root)
        if not receipt.passed:
            _map_artifact_error(receipt.errors, line_index, vr.record_id)

    # -- validate artifact readability (content parsing) --
    for role, ref in vr.artifact_refs.items():
        _validate_artifact_readable(ref, root, line_index, vr.record_id)

    return vr


def _map_artifact_error(errors: tuple[ContractErrorInfo, ...],
                        line_index: int, record_id: str) -> None:
    for err_info in errors:
        code = err_info.code
        if code == "ARTIFACT_NOT_FOUND":
            raise _error("MODEL_BATCH_ARTIFACT_MISSING",
                         err_info.message,
                         f"line {line_index + 1}",
                         details={"record_id": record_id})
        if code == "ARTIFACT_CHECKSUM_MISMATCH":
            raise _error("MODEL_BATCH_ARTIFACT_CHECKSUM_MISMATCH",
                         err_info.message,
                         f"line {line_index + 1}",
                         details={"record_id": record_id})
        if code == "ARTIFACT_BYTE_COUNT_MISMATCH":
            raise _error("MODEL_BATCH_ARTIFACT_CHECKSUM_MISMATCH",
                         err_info.message,
                         f"line {line_index + 1}",
                         details={"record_id": record_id})
        # fallback
        raise _error("MODEL_BATCH_ARTIFACT_MISSING",
                     err_info.message,
                     f"line {line_index + 1}",
                     details={"record_id": record_id})


def _validate_artifact_readable(ref: ArtifactRef, root: Path,
                                line_index: int, record_id: str) -> None:
    try:
        file_path = resolve_artifact_path(ref, root=root)
    except ValueError as exc:
        raise _error("MODEL_BATCH_ARTIFACT_MISSING",
                     str(exc),
                     f"line {line_index + 1}",
                     details={"record_id": record_id, "uri": ref.uri}) from exc

    fmt = ref.format
    try:
        with file_path.open("r", encoding="utf-8") as fh:
            raw = fh.read()
    except (OSError, UnicodeDecodeError) as exc:
        raise _error("MODEL_BATCH_ARTIFACT_UNREADABLE",
                     f"cannot read {ref.uri}: {exc}",
                     f"line {line_index + 1}",
                     details={"record_id": record_id, "uri": ref.uri}) from exc

    if fmt == "json":
        try:
            json.loads(raw)
        except json.JSONDecodeError as exc:
            raise _error("MODEL_BATCH_ARTIFACT_UNREADABLE",
                         f"invalid JSON in {ref.uri}: {exc}",
                         f"line {line_index + 1}",
                         details={"record_id": record_id, "uri": ref.uri}) from exc
    elif fmt == "pdb":
        # PDB artifacts in this project are JSON-wrapped:
        # {"format":"pdb","data":"ATOM ...\\n"}
        try:
            wrapper = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise _error("MODEL_BATCH_ARTIFACT_UNREADABLE",
                         f"PDB artifact {ref.uri} is not valid JSON: {exc}",
                         f"line {line_index + 1}",
                         details={"record_id": record_id, "uri": ref.uri}) from exc
        if not isinstance(wrapper, dict) or "data" not in wrapper:
            raise _error("MODEL_BATCH_ARTIFACT_UNREADABLE",
                         f"PDB wrapper missing 'data' key in {ref.uri}",
                         f"line {line_index + 1}",
                         details={"record_id": record_id, "uri": ref.uri})


#  Phase 2: read artifact metadata


def _read_artifact_metadata(validated: list[_ValidatedRecord],
                            root: Path) -> None:
    for vr in validated:
        # protein atom count
        prot_ref = vr.artifact_refs["protein_atom_table"]
        prot_path = resolve_artifact_path(prot_ref, root=root)
        prot_data = json.loads(prot_path.read_text(encoding="utf-8"))
        atoms = prot_data.get("atoms")
        if not isinstance(atoms, list):
            raise _error("MODEL_BATCH_ARTIFACT_UNREADABLE",
                         "protein_atom_table missing 'atoms' array",
                         f"line {vr.line_index + 1}",
                         details={"record_id": vr.record_id})
        vr.protein_atom_count = len(atoms)

        # Resolve target_atom_identity only after the protein atom table is readable.
        vr.target_atom_identity = ProteinAtomIdentity(
            chain_id=prot_data.get("chain_id"),
            residue_number=prot_data.get("residue_number"),
            residue_name=prot_data.get("residue_name", ""),
            atom_name=vr.target_atom_name,
            atom_serial=_target_atom_serial(
                atoms,
                vr.target_atom_index,
                vr.target_atom_name,
            ),
        )

        # ligand atom count
        lig_ref = vr.artifact_refs["ligand_atom_table"]
        lig_path = resolve_artifact_path(lig_ref, root=root)
        lig_data = json.loads(lig_path.read_text(encoding="utf-8"))
        lig_atoms = lig_data.get("atoms")
        if not isinstance(lig_atoms, list):
            raise _error("MODEL_BATCH_ARTIFACT_UNREADABLE",
                         "ligand_atom_table missing 'atoms' array",
                         f"line {vr.line_index + 1}",
                         details={"record_id": vr.record_id})
        vr.ligand_atom_count = len(lig_atoms)

        # ligand bond count (for bond matrix shape context)
        bond_ref = vr.artifact_refs["ligand_bond_table"]
        bond_path = resolve_artifact_path(bond_ref, root=root)
        bond_data = json.loads(bond_path.read_text(encoding="utf-8"))
        bonds = bond_data.get("bonds")
        if not isinstance(bonds, list):
            raise _error("MODEL_BATCH_ARTIFACT_UNREADABLE",
                         "ligand_bond_table missing 'bonds' array",
                         f"line {vr.line_index + 1}",
                         details={"record_id": vr.record_id})
        vr.ligand_bond_count = len(bonds)

        # edge denominators (only boundary metadata, not per-edge contents)
        edge_ref = vr.artifact_refs["edge_candidates"]
        edge_path = resolve_artifact_path(edge_ref, root=root)
        edge_data = json.loads(edge_path.read_text(encoding="utf-8"))
        denom_dict = edge_data.get("denominators")
        if not isinstance(denom_dict, dict):
            raise _error("MODEL_BATCH_ARTIFACT_UNREADABLE",
                         "edge_candidates missing 'denominators'",
                         f"line {vr.line_index + 1}",
                         details={"record_id": vr.record_id})

        try:
            vr.edge_denominators = EdgeDenominators(**denom_dict)
        except TypeError as exc:
            raise _error("MODEL_BATCH_ARTIFACT_UNREADABLE",
                         f"invalid edge denominators: {exc}",
                         f"line {vr.line_index + 1}",
                         details={"record_id": vr.record_id}) from exc


#  Phase 3: build output structures


def _build_headers(
    validated: list[_ValidatedRecord],
) -> list[BatchRecordHeader]:
    records: list[BatchRecordHeader] = []
    for batch_index, vr in enumerate(validated):
        if vr.target_atom_identity is None:
            raise _error("MODEL_BATCH_ARTIFACT_UNREADABLE",
                         "target atom identity was not resolved",
                         f"line {vr.line_index + 1}",
                         details={"record_id": vr.record_id})
        artifact_refs_mapping: dict[str, ArtifactRef] = dict(vr.artifact_refs)
        header = BatchRecordHeader(
            record_id=vr.record_id,
            residue_reaction_family=vr.residue_reaction_family,
            quality_tier=vr.quality_tier,
            visual_check_status=vr.visual_check_status,
            chemical_state_status=vr.chemical_state_status,
            target_atom_identity=vr.target_atom_identity,
            target_atom_index=vr.target_atom_index,
            target_atom_artifact_role="protein_atom_table",
            artifact_refs=artifact_refs_mapping,
            batch_index=batch_index,
        )
        records.append(header)
    return records


def _build_tensors(validated: list[_ValidatedRecord]) -> BatchTensors:
    B = len(validated)
    max_prot = max(vr.protein_atom_count for vr in validated)
    max_lig = max(vr.ligand_atom_count for vr in validated)
    max_candidates = max(
        vr.edge_denominators.candidate_count if vr.edge_denominators else 0
        for vr in validated
    )

    return BatchTensors(
        protein_coords_shape=(B, max_prot, 3),
        ligand_coords_shape=(B, max_lig, 3),
        protein_atom_types_shape=(B, max_prot),
        ligand_atom_types_shape=(B, max_lig),
        ligand_bonds_shape=(B, max_lig, max_lig),
        edge_candidates_shape=(B, max_candidates),
        positive_label_mask_shape=(B, max_candidates),
        candidate_to_ligand_map_shape=(B, max_candidates),
        candidate_to_protein_map_shape=(B, max_candidates),
        dtype="float32",
        index_dtype="int64",
        coordinate_frame="original_pdb",
    )


def _build_edge_candidate_refs(
    validated: list[_ValidatedRecord],
) -> dict[str, ArtifactRef]:
    mapping: dict[str, ArtifactRef] = {}
    for vr in validated:
        mapping[vr.record_id] = vr.artifact_refs["edge_candidates"]
    return mapping


def _build_denominators(validated: list[_ValidatedRecord]) -> EdgeDenominators:
    """Aggregate per-record denominators into batch-level expected totals."""
    total = EdgeDenominators(
        candidate_count=0,
        natural_candidate_count=0,
        forced_positive_count=0,
        eligible_edge_count=0,
        masked_candidate_count=0,
        edge_loss_denominator=0,
        bond_type_loss_denominator=0,
        geometry_loss_denominator=0,
        message_passing_candidate_count=0,
        gate_evaluated_count=0,
    )
    for vr in validated:
        d = vr.edge_denominators
        if d is None:
            continue
        total = EdgeDenominators(
            candidate_count=total.candidate_count + d.candidate_count,
            natural_candidate_count=total.natural_candidate_count + d.natural_candidate_count,
            forced_positive_count=total.forced_positive_count + d.forced_positive_count,
            eligible_edge_count=total.eligible_edge_count + d.eligible_edge_count,
            masked_candidate_count=total.masked_candidate_count + d.masked_candidate_count,
            edge_loss_denominator=total.edge_loss_denominator + d.edge_loss_denominator,
            bond_type_loss_denominator=total.bond_type_loss_denominator + d.bond_type_loss_denominator,
            geometry_loss_denominator=total.geometry_loss_denominator + d.geometry_loss_denominator,
            message_passing_candidate_count=total.message_passing_candidate_count + d.message_passing_candidate_count,
            gate_evaluated_count=total.gate_evaluated_count + d.gate_evaluated_count,
        )

    # validate aggregated denominators
    total.validate()
    return total


#  helpers


def _target_atom_serial(
    atoms: list,
    target_atom_index: int,
    target_atom_name: str,
) -> Optional[int]:
    if 0 <= target_atom_index < len(atoms):
        atom = atoms[target_atom_index]
        if isinstance(atom, dict):
            serial = atom.get("serial")
            if isinstance(serial, int):
                return serial

    for atom in atoms:
        if not isinstance(atom, dict):
            continue
        name = atom.get("name")
        serial = atom.get("serial")
        if name == target_atom_name and isinstance(serial, int):
            return serial
    return None


def _build_batch_spec(
    validated: list[_ValidatedRecord],
    tensors: BatchTensors,
    records_jsonl_hash: str,
) -> BatchSpec:
    bond_types = set()
    for vr in validated:
        bond_type = vr.core_labels.get("bond_type")
        if isinstance(bond_type, str) and bond_type and bond_type != "no_edge":
            bond_types.add(bond_type)

    return BatchSpec(
        bond_type_vocabulary=("no_edge",) + tuple(sorted(bond_types)),
        max_protein_atoms=tensors.protein_coords_shape[1],
        max_ligand_atoms=tensors.ligand_coords_shape[1],
        max_candidates=tensors.edge_candidates_shape[1],
        candidate_radius_angstrom=4.0,
        coordinate_frame=tensors.coordinate_frame,
        records_jsonl_hash=records_jsonl_hash,
    )


def _require_str(d: dict, key: str) -> str:
    v = d.get(key)
    if not isinstance(v, str):
        raise _error("MODEL_BATCH_ARTIFACT_UNREADABLE",
                     f"'{key}' missing or not a string",
                     details={"key": key})
    return v


def _require_int(d: dict, key: str) -> int:
    v = d.get(key)
    if not isinstance(v, int):
        raise _error("MODEL_BATCH_ARTIFACT_UNREADABLE",
                     f"'{key}' missing or not an int",
                     details={"key": key})
    return v


def _artifact_ref_from_dict(d: dict, line_index: int) -> ArtifactRef:
    try:
        return ArtifactRef(
            uri=_require_str(d, "uri"),
            sha256=_require_str(d, "sha256"),
            format=_require_str(d, "format"),
            schema_version=d.get("schema_version", SCHEMA_VERSION),
            role=d.get("role", ""),
            bytes=int(d.get("bytes", 0)),
        )
    except (TypeError, ValueError) as exc:
        raise _error("MODEL_BATCH_ARTIFACT_UNREADABLE",
                     f"invalid artifact ref: {exc}",
                     f"line {line_index + 1}") from exc
