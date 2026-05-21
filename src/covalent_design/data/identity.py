from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Mapping, Optional

from covalent_design.contracts import (
    LigandAtomIdentity,
    ProteinAtomIdentity,
    SourceIngestRecord,
    SourceRecordLineage,
)
from covalent_design.data.conflicts import ConflictAnchor, ConflictGroup


SOURCE_PRIORITY = ("covbinder_in_pdb", "covpdb", "covalentin_db")
_SOURCE_RANK = {source: index for index, source in enumerate(SOURCE_PRIORITY)}


@dataclass(frozen=True)
class CanonicalLinkageIdentity:
    structure_id: str
    structure_model: Optional[int]
    protein_chain_id: Optional[str]
    protein_asym_id: Optional[str]
    protein_residue_name: str
    protein_residue_number: int
    protein_insertion_code: Optional[str]
    protein_altloc: Optional[str]
    protein_atom_name: str
    protein_atom_serial: Optional[int]
    ligand_id: str
    ligand_chain_id: Optional[str]
    ligand_asym_id: Optional[str]
    ligand_residue_number: Optional[int]
    ligand_altloc: Optional[str]
    ligand_atom_name: str
    ligand_atom_index: Optional[int]
    residue_reaction_family: str
    bond_type: str


class IdentityInputError(ValueError):
    def __init__(self, message: str, missing_fields: tuple[str, ...]) -> None:
        super().__init__(message)
        self.missing_fields = missing_fields


@dataclass(frozen=True)
class RejectedIdentityInput:
    source_lineage: SourceRecordLineage
    reason: str
    message: str
    missing_fields: tuple[str, ...]


@dataclass(frozen=True)
class AnnotationValue:
    source_database: str
    source_record_id: str
    value: object


@dataclass(frozen=True)
class MergedIdentityRecord:
    record_id: str
    identity: CanonicalLinkageIdentity
    lineage: tuple[SourceRecordLineage, ...]
    preferred_annotations: Mapping[str, object]
    annotation_alternatives: Mapping[str, tuple[AnnotationValue, ...]]


@dataclass(frozen=True)
class IdentityResolutionResult:
    merged_records: tuple[MergedIdentityRecord, ...]
    conflict_groups: tuple[ConflictGroup, ...]
    rejected_inputs: tuple[RejectedIdentityInput, ...]


def canonical_identity_from_record(record: SourceIngestRecord) -> CanonicalLinkageIdentity:
    target = record.target_atom_identity
    ligand = record.ligand_atom_identity
    structure_id = _text(record.protein.get("pdb_id") or record.metadata.get("pdb_id"))
    residue_reaction_family = _text(record.linkage.get("residue_reaction_family"))
    bond_type = _text(record.linkage.get("bond_type"))

    missing: list[str] = []
    if not structure_id:
        missing.append("structure_id")
    if target is None:
        missing.append("target_atom_identity")
    if ligand is None:
        missing.append("ligand_atom_identity")
    if target is not None:
        _require_text(target.residue_name, "protein_residue_name", missing)
        _require_int(target.residue_number, "protein_residue_number", missing)
        _require_text(target.atom_name, "protein_atom_name", missing)
        if not _text(target.chain_id) and not _text(target.asym_id):
            missing.append("protein_chain_or_asym_id")
    if ligand is not None:
        _require_text(ligand.ligand_id, "ligand_id", missing)
        _require_text(ligand.atom_name, "ligand_atom_name", missing)
    if not residue_reaction_family:
        missing.append("residue_reaction_family")
    if not bond_type:
        missing.append("bond_type")
    if missing:
        raise IdentityInputError(
            "Missing identity-critical fields: " + ", ".join(missing),
            tuple(missing),
        )

    assert target is not None
    assert ligand is not None
    assert target.residue_number is not None
    return CanonicalLinkageIdentity(
        structure_id=structure_id.lower(),
        structure_model=target.structure_model,
        protein_chain_id=_normalized_optional(target.chain_id),
        protein_asym_id=_normalized_optional(target.asym_id),
        protein_residue_name=target.residue_name.upper(),
        protein_residue_number=target.residue_number,
        protein_insertion_code=_normalized_optional(target.insertion_code),
        protein_altloc=_normalized_optional(target.altloc),
        protein_atom_name=target.atom_name.upper(),
        protein_atom_serial=target.atom_serial,
        ligand_id=ligand.ligand_id.upper(),
        ligand_chain_id=_normalized_optional(ligand.chain_id),
        ligand_asym_id=_normalized_optional(ligand.asym_id),
        ligand_residue_number=ligand.residue_number,
        ligand_altloc=_normalized_optional(ligand.altloc),
        ligand_atom_name=ligand.atom_name.upper(),
        ligand_atom_index=ligand.atom_index,
        residue_reaction_family=residue_reaction_family,
        bond_type=bond_type,
    )


def normalize_identity_json(identity: CanonicalLinkageIdentity) -> str:
    return json.dumps(asdict(identity), sort_keys=True, separators=(",", ":"))


def build_record_id(identity: CanonicalLinkageIdentity) -> str:
    return hashlib.sha256(normalize_identity_json(identity).encode("utf-8")).hexdigest()[:32]


def resolve_identities(records: tuple[SourceIngestRecord, ...]) -> IdentityResolutionResult:
    rejected: list[RejectedIdentityInput] = []
    accepted: list[tuple[SourceIngestRecord, CanonicalLinkageIdentity]] = []

    for record in records:
        try:
            accepted.append((record, canonical_identity_from_record(record)))
        except IdentityInputError as exc:
            rejected.append(
                RejectedIdentityInput(
                    source_lineage=_lineage(record),
                    reason="IDENTITY_CRITICAL_FIELD_MISSING",
                    message=str(exc),
                    missing_fields=exc.missing_fields,
                )
            )

    records_by_anchor: dict[ConflictAnchor, list[tuple[SourceIngestRecord, CanonicalLinkageIdentity]]] = {}
    for record, identity in accepted:
        records_by_anchor.setdefault(_conflict_anchor(identity), []).append((record, identity))

    merged: list[MergedIdentityRecord] = []
    conflicts: list[ConflictGroup] = []
    for anchor, group in sorted(records_by_anchor.items(), key=lambda item: _anchor_json(item[0])):
        identities = {_identity_key(identity) for _, identity in group}
        if len(identities) > 1:
            conflicts.append(_conflict_group(anchor, group))
            continue
        merged.append(_merge_identity_records(group))

    return IdentityResolutionResult(
        merged_records=tuple(sorted(merged, key=lambda record: record.record_id)),
        conflict_groups=tuple(sorted(conflicts, key=lambda group: group.conflict_group_id)),
        rejected_inputs=tuple(rejected),
    )


def _merge_identity_records(group: list[tuple[SourceIngestRecord, CanonicalLinkageIdentity]]) -> MergedIdentityRecord:
    identity = group[0][1]
    records = [record for record, _ in group]
    lineage = tuple(sorted((_lineage(record) for record in records), key=_lineage_sort_key))
    alternatives = _annotation_alternatives(records)
    preferred = {
        key: values[0].value
        for key, values in alternatives.items()
        if values
    }
    return MergedIdentityRecord(
        record_id=build_record_id(identity),
        identity=identity,
        lineage=lineage,
        preferred_annotations=preferred,
        annotation_alternatives=alternatives,
    )


def _annotation_alternatives(records: list[SourceIngestRecord]) -> Mapping[str, tuple[AnnotationValue, ...]]:
    by_key: dict[str, list[AnnotationValue]] = {}
    for record in records:
        for key, value in record.metadata.items():
            if value in (None, ""):
                continue
            by_key.setdefault(key, []).append(
                AnnotationValue(
                    source_database=record.source_database,
                    source_record_id=record.source_record_id,
                    value=value,
                )
            )
    return {
        key: tuple(sorted(values, key=lambda value: (_source_rank(value.source_database), str(value.value))))
        for key, values in sorted(by_key.items())
    }


def _conflict_group(
    anchor: ConflictAnchor,
    group: list[tuple[SourceIngestRecord, CanonicalLinkageIdentity]],
) -> ConflictGroup:
    identities_by_json = {
        normalize_identity_json(identity): identity
        for _, identity in group
    }
    identities = tuple(identities_by_json[key] for key in sorted(identities_by_json))
    lineage = tuple(sorted((_lineage(record) for record, _ in group), key=_lineage_sort_key))
    payload = {
        "anchor": asdict(anchor),
        "identities": [json.loads(normalize_identity_json(identity)) for identity in identities],
    }
    conflict_group_id = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:32]
    return ConflictGroup(
        conflict_group_id=conflict_group_id,
        anchor=anchor,
        lineage=lineage,
        conflicting_identities=identities,
        reason="LINKAGE_IDENTITY_CONFLICT",
    )


def _conflict_anchor(identity: CanonicalLinkageIdentity) -> ConflictAnchor:
    return ConflictAnchor(
        structure_id=identity.structure_id,
        ligand_id=identity.ligand_id,
        ligand_chain_id=identity.ligand_chain_id,
        ligand_asym_id=identity.ligand_asym_id,
        ligand_residue_number=identity.ligand_residue_number,
    )


def _lineage(record: SourceIngestRecord) -> SourceRecordLineage:
    if record.source_lineage is not None:
        return record.source_lineage
    return SourceRecordLineage(
        source_database=record.source_database,
        source_version=record.source_version,
        source_record_id=record.source_record_id,
        raw_manifest_file=record.raw_manifest_file,
        raw_file_path=record.raw_file_path,
        raw_file_sha256=record.raw_file_sha256,
        row_index=record.row_index,
    )


def _lineage_sort_key(lineage: SourceRecordLineage) -> tuple[int, str, str]:
    return (_source_rank(lineage.source_database), lineage.source_database, lineage.source_record_id)


def _source_rank(source_database: str) -> int:
    return _SOURCE_RANK.get(source_database, len(SOURCE_PRIORITY))


def _identity_key(identity: CanonicalLinkageIdentity) -> str:
    return normalize_identity_json(identity)


def _anchor_json(anchor: ConflictAnchor) -> str:
    return json.dumps(asdict(anchor), sort_keys=True, separators=(",", ":"))


def _text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalized_optional(value: Optional[str]) -> Optional[str]:
    text = _text(value)
    return text or None


def _require_text(value: object, field: str, missing: list[str]) -> None:
    if not _text(value):
        missing.append(field)


def _require_int(value: object, field: str, missing: list[str]) -> None:
    if value is None or isinstance(value, bool):
        missing.append(field)
