"""Docking protocol manifest loader, validator, and score index builder.

Task 32: No real docking execution.  No directory scanning inference.
No RDKit, torch, PMDM, PocketFlow, or heavy dependency.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional

from covalent_design._yaml_loader import load_yaml_config
from covalent_design.contracts.errors import ContractError, ContractErrorInfo
from covalent_design.contracts.lifecycle import validate_generation_result
from covalent_design.contracts.types import (
    CONTRACT_VERSION,
    SCHEMA_VERSION,
    ArtifactRef,
    CovalentConstraint,
    CovalentGenerationResult,
    DockingProtocolManifest,
    DockingSearchRegion,
    LigandPreparation,
    PoseSelection,
    ReceptorPreparation,
    ValidationReceipt,
)
from covalent_design.io.artifacts import (
    resolve_artifact_path,
    sha256_file,
    validate_artifact_ref,
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

_WATER_COFACTOR_METAL_POLICY = ("keep", "remove", "selected")
_CONSTRAINT_REPRESENTATION = (
    "explicit_linkage",
    "distance_constraint",
    "reaction_constraint",
    "other",
)
_SEARCH_UNIT = ("angstrom",)
_POSE_RANKING = ("best_score", "first_valid", "other")

_VALIDATOR = "covalent_design.evaluation.validate_docking_protocol_manifest"


# ---------------------------------------------------------------------------
# evaluation-owned dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DockingScoreEligibleResult:
    """One flat entry in a DockingScoreEligibleResultIndex."""

    request_id: str
    sample_id: int
    docking_protocol_id: str
    covalent_docking_score: float
    noncovalent_vina_score: Optional[float]
    engine_name: str
    engine_version: str


@dataclass(frozen=True)
class DockingScoreEligibleResultIndex:
    """Index of all docking-score-eligible succeeded results."""

    entries: tuple[DockingScoreEligibleResult, ...]


# ---------------------------------------------------------------------------
# inline YAML / JSON decode
# ---------------------------------------------------------------------------


def _decode_inline(val: object) -> object:
    """Decode JSON-compatible inline YAML values that the minimal YAML
    loader leaves as bare strings (e.g. ``[10.0, 20.0, 30.0]``, ``{}``)."""
    if isinstance(val, str):
        stripped = val.strip()
        if (stripped.startswith("[") and stripped.endswith("]")) or (
            stripped.startswith("{") and stripped.endswith("}")
        ):
            try:
                return json.loads(stripped)
            except (json.JSONDecodeError, ValueError):
                pass
    elif isinstance(val, dict):
        return {k: _decode_inline(v) for k, v in val.items()}
    elif isinstance(val, list):
        return [_decode_inline(v) for v in val]
    return val


# ---------------------------------------------------------------------------
# numeric triple helper
# ---------------------------------------------------------------------------


def _parse_numeric_triple(val: object) -> tuple:
    """Parse a value into a numeric triple tuple.  Returns an empty tuple or a
    shorter-than-3 tuple for invalid input so the validator can reject it."""
    if isinstance(val, (list, tuple)):
        return tuple(
            float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else v
            for v in val
        )
    if isinstance(val, str):
        decoded = _decode_inline(val)
        if isinstance(decoded, list):
            return _parse_numeric_triple(decoded)
    return ()


# ---------------------------------------------------------------------------
# manifest loader
# ---------------------------------------------------------------------------


def load_docking_protocol_manifest(path: Path) -> DockingProtocolManifest:
    """Decode a docking protocol manifest YAML file.

    * Decodes inline JSON-compatible values left as strings by the minimal
      YAML loader (e.g. ``[10.0, 20.0, 30.0]``, ``{}``).
    * Missing nested required fields decode to invalid placeholder values so
      the validator reports failure instead of the loader crashing.
    * Truly unreadable or non-mapping YAML raises a structured ``ContractError``.
    """
    path = Path(path)
    try:
        raw = load_yaml_config(str(path))
    except Exception as exc:
        raise ContractError(
            code="DOCKING_PROTOCOL_MANIFEST_UNREADABLE",
            owner="evaluation",
            message=f"Cannot parse docking protocol manifest: {exc}",
            location=str(path),
        ) from exc

    if not isinstance(raw, dict):
        raise ContractError(
            code="DOCKING_PROTOCOL_MANIFEST_NOT_MAPPING",
            owner="evaluation",
            message="Docking protocol manifest root must be a mapping",
            location=str(path),
        )

    decoded = {k: _decode_inline(v) for k, v in raw.items()}

    # extract nested sections, defaulting to empty dicts for missing sections
    rp_raw = decoded.get("receptor_preparation")
    if not isinstance(rp_raw, dict):
        rp_raw = {}

    lp_raw = decoded.get("ligand_preparation")
    if not isinstance(lp_raw, dict):
        lp_raw = {}

    cc_raw = decoded.get("covalent_constraint")
    if not isinstance(cc_raw, dict):
        cc_raw = {}

    sr_raw = decoded.get("search_region")
    if not isinstance(sr_raw, dict):
        sr_raw = {}

    ps_raw = decoded.get("pose_selection")
    if not isinstance(ps_raw, dict):
        ps_raw = {}

    # constraint_parameters may arrive as inline-YAML string "{}"
    cp = cc_raw.get("constraint_parameters")
    if isinstance(cp, str):
        decoded_cp = _decode_inline(cp)
        if isinstance(decoded_cp, dict):
            cp = decoded_cp
        else:
            cp = cp  # keep the original string so validator can reject it

    random_seed = decoded.get("random_seed", "")

    return DockingProtocolManifest(
        docking_protocol_id=_as_str(decoded.get("docking_protocol_id")),
        engine_name=_as_str(decoded.get("engine_name")),
        engine_version=_as_str(decoded.get("engine_version")),
        engine_build_hash=_as_str(decoded.get("engine_build_hash")),
        full_config_uri=_as_str(decoded.get("full_config_uri")),
        full_config_sha256=_as_str(decoded.get("full_config_sha256")),
        random_seed=random_seed,  # None / int / bool preserved; validator rejects bool
        receptor_preparation=ReceptorPreparation(
            tool_name=_as_str(rp_raw.get("tool_name")),
            tool_version=_as_str(rp_raw.get("tool_version")),
            input_structure_uri=_as_str(rp_raw.get("input_structure_uri")),
            input_structure_sha256=_as_str(rp_raw.get("input_structure_sha256")),
            output_receptor_uri=_as_str(rp_raw.get("output_receptor_uri")),
            output_receptor_sha256=_as_str(rp_raw.get("output_receptor_sha256")),
            pH_or_protonation_policy=_as_str(rp_raw.get("pH_or_protonation_policy")),
            water_policy=_as_str(rp_raw.get("water_policy")),
            cofactor_policy=_as_str(rp_raw.get("cofactor_policy")),
            metal_policy=_as_str(rp_raw.get("metal_policy")),
        ),
        ligand_preparation=LigandPreparation(
            tool_name=_as_str(lp_raw.get("tool_name")),
            tool_version=_as_str(lp_raw.get("tool_version")),
            input_ligand_uri=_as_str(lp_raw.get("input_ligand_uri")),
            input_ligand_sha256=_as_str(lp_raw.get("input_ligand_sha256")),
            charge_model=_as_str(lp_raw.get("charge_model")),
            protonation_policy=_as_str(lp_raw.get("protonation_policy")),
        ),
        covalent_constraint=CovalentConstraint(
            representation=_as_str(cc_raw.get("representation")),
            target_atom_identity=_as_str(cc_raw.get("target_atom_identity")),
            ligand_atom_identity=_as_str(cc_raw.get("ligand_atom_identity")),
            constraint_parameters=cp,
        ),
        search_region=DockingSearchRegion(
            center=_parse_numeric_triple(sr_raw.get("center")),
            size=_parse_numeric_triple(sr_raw.get("size")),
            unit=_as_str(sr_raw.get("unit")),
        ),
        pose_selection=PoseSelection(
            ranking_rule=_as_str(ps_raw.get("ranking_rule")),
            score_unit=_as_str(ps_raw.get("score_unit")),
        ),
        failure_log_uri=_as_str(decoded.get("failure_log_uri")),
        failure_log_sha256=_as_str(decoded.get("failure_log_sha256")),
    )


def _as_str(val: object, default: str = "") -> str:
    """Preserve source values so the validator can reject wrong types."""
    if val is None:
        return default
    return val  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# manifest validator
# ---------------------------------------------------------------------------


def validate_docking_protocol_manifest(
    manifest: DockingProtocolManifest,
    artifact_root: Path,
) -> ValidationReceipt:
    """Validate a docking protocol manifest against the frozen IO contract.

    Returns a ``ValidationReceipt``.  The receipt is failed when any
    required field is missing, empty, out-of-enum, or when a referenced
    artifact URI is unsafe, missing, or has a checksum mismatch.
    """
    errors: list[ContractErrorInfo] = []

    _validate_non_empty_strings(manifest, errors)
    _validate_sha256_fields(manifest, errors)
    _validate_enums(manifest, errors)
    _validate_search_region(manifest, errors)
    _validate_random_seed(manifest, errors)
    _validate_constraint_parameters(manifest, errors)
    _validate_uri_safety(manifest, errors)
    if not errors:
        _validate_artifact_files(manifest, artifact_root, errors)

    return ValidationReceipt(
        validator=_VALIDATOR,
        contract_version=CONTRACT_VERSION,
        input_sha256=_manifest_sha256(manifest),
        passed=not errors,
        errors=tuple(errors),
    )


# -- field-level validators --


def _validate_non_empty_strings(
    manifest: DockingProtocolManifest, errors: list[ContractErrorInfo]
) -> None:
    """All required string fields must be non-empty."""
    rp = manifest.receptor_preparation
    lp = manifest.ligand_preparation
    cc = manifest.covalent_constraint
    ps = manifest.pose_selection

    checks: list[tuple[str, str]] = [
        ("docking_protocol_id", manifest.docking_protocol_id),
        ("engine_name", manifest.engine_name),
        ("engine_version", manifest.engine_version),
        ("engine_build_hash", manifest.engine_build_hash),
        ("full_config_uri", manifest.full_config_uri),
        ("full_config_sha256", manifest.full_config_sha256),
        ("failure_log_uri", manifest.failure_log_uri),
        ("failure_log_sha256", manifest.failure_log_sha256),
        ("receptor_preparation.tool_name", rp.tool_name),
        ("receptor_preparation.tool_version", rp.tool_version),
        ("receptor_preparation.input_structure_uri", rp.input_structure_uri),
        ("receptor_preparation.input_structure_sha256", rp.input_structure_sha256),
        ("receptor_preparation.output_receptor_uri", rp.output_receptor_uri),
        ("receptor_preparation.output_receptor_sha256", rp.output_receptor_sha256),
        ("receptor_preparation.pH_or_protonation_policy", rp.pH_or_protonation_policy),
        ("ligand_preparation.tool_name", lp.tool_name),
        ("ligand_preparation.tool_version", lp.tool_version),
        ("ligand_preparation.input_ligand_uri", lp.input_ligand_uri),
        ("ligand_preparation.input_ligand_sha256", lp.input_ligand_sha256),
        ("ligand_preparation.charge_model", lp.charge_model),
        ("ligand_preparation.protonation_policy", lp.protonation_policy),
        ("covalent_constraint.target_atom_identity", cc.target_atom_identity),
        ("covalent_constraint.ligand_atom_identity", cc.ligand_atom_identity),
        ("pose_selection.score_unit", ps.score_unit),
    ]
    for location, value in checks:
        if not value or not isinstance(value, str):
            errors.append(
                _err(
                    "DOCKING_PROTOCOL_REQUIRED_FIELD_EMPTY",
                    f"Required field {location!r} must be non-empty",
                    location,
                )
            )
            return  # one error per field family to avoid flooding


def _validate_sha256_fields(
    manifest: DockingProtocolManifest, errors: list[ContractErrorInfo]
) -> None:
    """SHA-256 fields must be 64 lowercase hex characters."""
    rp = manifest.receptor_preparation
    lp = manifest.ligand_preparation

    checks: list[tuple[str, str]] = [
        ("full_config_sha256", manifest.full_config_sha256),
        ("receptor_preparation.input_structure_sha256", rp.input_structure_sha256),
        ("receptor_preparation.output_receptor_sha256", rp.output_receptor_sha256),
        ("ligand_preparation.input_ligand_sha256", lp.input_ligand_sha256),
        ("failure_log_sha256", manifest.failure_log_sha256),
    ]
    for location, value in checks:
        if not isinstance(value, str) or not _SHA256_RE.match(value):
            errors.append(
                _err(
                    "DOCKING_PROTOCOL_SHA256_INVALID",
                    f"SHA-256 field {location!r} must be 64 lowercase hex characters",
                    location,
                )
            )


def _validate_enums(
    manifest: DockingProtocolManifest, errors: list[ContractErrorInfo]
) -> None:
    """Enum-restricted fields must use allowed values."""
    rp = manifest.receptor_preparation
    cc = manifest.covalent_constraint
    sr = manifest.search_region
    ps = manifest.pose_selection

    enum_checks: list[tuple[str, str, tuple[str, ...]]] = [
        ("receptor_preparation.water_policy", rp.water_policy, _WATER_COFACTOR_METAL_POLICY),
        ("receptor_preparation.cofactor_policy", rp.cofactor_policy, _WATER_COFACTOR_METAL_POLICY),
        ("receptor_preparation.metal_policy", rp.metal_policy, _WATER_COFACTOR_METAL_POLICY),
        ("covalent_constraint.representation", cc.representation, _CONSTRAINT_REPRESENTATION),
        ("search_region.unit", sr.unit, _SEARCH_UNIT),
        ("pose_selection.ranking_rule", ps.ranking_rule, _POSE_RANKING),
    ]
    for location, value, allowed in enum_checks:
        if value not in allowed:
            errors.append(
                _err(
                    "DOCKING_PROTOCOL_ENUM_INVALID",
                    f"{location!r} must be one of {allowed}, got {value!r}",
                    location,
                )
            )


def _validate_search_region(
    manifest: DockingProtocolManifest, errors: list[ContractErrorInfo]
) -> None:
    """center and size must be numeric triples; size components must be positive."""
    center = manifest.search_region.center
    size = manifest.search_region.size

    if not isinstance(center, tuple) or len(center) != 3:
        errors.append(
            _err(
                "DOCKING_PROTOCOL_SEARCH_CENTER_INVALID",
                "search_region.center must be a numeric triple [x, y, z]",
                "search_region.center",
            )
        )
    else:
        for i, v in enumerate(center):
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                errors.append(
                    _err(
                        "DOCKING_PROTOCOL_SEARCH_CENTER_INVALID",
                        f"search_region.center[{i}] must be numeric, got {type(v).__name__}",
                        f"search_region.center[{i}]",
                    )
                )
                break
            if not math.isfinite(float(v)):
                errors.append(
                    _err(
                        "DOCKING_PROTOCOL_SEARCH_CENTER_INVALID",
                        f"search_region.center[{i}] must be finite, got {v}",
                        f"search_region.center[{i}]",
                    )
                )
                break

    if not isinstance(size, tuple) or len(size) != 3:
        errors.append(
            _err(
                "DOCKING_PROTOCOL_SEARCH_SIZE_INVALID",
                "search_region.size must be a numeric triple [x, y, z]",
                "search_region.size",
            )
        )
    else:
        for i, v in enumerate(size):
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                errors.append(
                    _err(
                        "DOCKING_PROTOCOL_SEARCH_SIZE_INVALID",
                        f"search_region.size[{i}] must be numeric, got {type(v).__name__}",
                        f"search_region.size[{i}]",
                    )
                )
                break
            if not math.isfinite(float(v)):
                errors.append(
                    _err(
                        "DOCKING_PROTOCOL_SEARCH_SIZE_INVALID",
                        f"search_region.size[{i}] must be finite, got {v}",
                        f"search_region.size[{i}]",
                    )
                )
                break
            if v <= 0:
                errors.append(
                    _err(
                        "DOCKING_PROTOCOL_SEARCH_SIZE_NON_POSITIVE",
                        f"search_region.size[{i}] must be positive, got {v}",
                        f"search_region.size[{i}]",
                    )
                )
                break


def _validate_random_seed(
    manifest: DockingProtocolManifest, errors: list[ContractErrorInfo]
) -> None:
    """random_seed must be int or None, but not bool."""
    seed = manifest.random_seed
    if seed is None:
        return
    if isinstance(seed, bool):
        errors.append(
            _err(
                "DOCKING_PROTOCOL_RANDOM_SEED_BOOL",
                "random_seed must be int or None, not bool",
                "random_seed",
            )
        )
        return
    if not isinstance(seed, int):
        errors.append(
            _err(
                "DOCKING_PROTOCOL_RANDOM_SEED_TYPE",
                "random_seed must be int or None",
                "random_seed",
            )
        )


def _validate_constraint_parameters(
    manifest: DockingProtocolManifest, errors: list[ContractErrorInfo]
) -> None:
    """constraint_parameters must be a mapping (may be empty)."""
    cp = manifest.covalent_constraint.constraint_parameters
    if not isinstance(cp, Mapping):
        errors.append(
            _err(
                "DOCKING_PROTOCOL_CONSTRAINT_PARAMETERS_NOT_MAPPING",
                "constraint_parameters must be a mapping",
                "covalent_constraint.constraint_parameters",
            )
        )


def _validate_uri_safety(
    manifest: DockingProtocolManifest, errors: list[ContractErrorInfo]
) -> None:
    """All artifact URIs must be non-empty, root-relative, no traversal, no backslash."""
    rp = manifest.receptor_preparation
    lp = manifest.ligand_preparation

    uri_checks: list[tuple[str, str]] = [
        ("full_config_uri", manifest.full_config_uri),
        ("failure_log_uri", manifest.failure_log_uri),
        ("receptor_preparation.input_structure_uri", rp.input_structure_uri),
        ("receptor_preparation.output_receptor_uri", rp.output_receptor_uri),
        ("ligand_preparation.input_ligand_uri", lp.input_ligand_uri),
    ]
    for location, uri in uri_checks:
        if not uri:
            continue  # empty-string error already reported by _validate_non_empty_strings
        if not isinstance(uri, str):
            continue  # wrong-type error already reported by _validate_non_empty_strings
        if "\\" in uri:
            errors.append(
                _err(
                    "DOCKING_PROTOCOL_URI_BACKSLASH",
                    f"Artifact URI {location!r} contains backslash (Windows traversal)",
                    location,
                )
            )
            continue
        uri_path = Path(uri)
        if uri_path.is_absolute():
            errors.append(
                _err(
                    "DOCKING_PROTOCOL_URI_ABSOLUTE",
                    f"Artifact URI {location!r} must be root-relative",
                    location,
                )
            )
            continue
        if ".." in uri_path.parts:
            errors.append(
                _err(
                    "DOCKING_PROTOCOL_URI_TRAVERSAL",
                    f"Artifact URI {location!r} must not escape the artifact root",
                    location,
                )
            )


def _validate_artifact_files(
    manifest: DockingProtocolManifest,
    artifact_root: Path,
    errors: list[ContractErrorInfo],
) -> None:
    """Validate file existence and checksum for all referenced artifacts."""
    rp = manifest.receptor_preparation
    lp = manifest.ligand_preparation

    file_checks: list[tuple[str, str, str]] = [
        ("full_config_uri", manifest.full_config_uri, manifest.full_config_sha256),
        (
            "receptor_preparation.input_structure_uri",
            rp.input_structure_uri,
            rp.input_structure_sha256,
        ),
        (
            "receptor_preparation.output_receptor_uri",
            rp.output_receptor_uri,
            rp.output_receptor_sha256,
        ),
        (
            "ligand_preparation.input_ligand_uri",
            lp.input_ligand_uri,
            lp.input_ligand_sha256,
        ),
        ("failure_log_uri", manifest.failure_log_uri, manifest.failure_log_sha256),
    ]

    for uri_loc, uri, expected_sha in file_checks:
        if not uri:
            continue  # empty URI already rejected
        try:
            file_path = resolve_artifact_path(
                ArtifactRef(uri=uri, sha256="0" * 64, format="", role=""),
                root=artifact_root,
            )
        except ValueError:
            errors.append(
                _err(
                    "DOCKING_PROTOCOL_ARTIFACT_URI_UNSAFE",
                    f"Cannot resolve artifact URI {uri_loc}: {uri!r}",
                    uri_loc,
                )
            )
            continue

        if not file_path.exists():
            errors.append(
                _err(
                    "DOCKING_PROTOCOL_ARTIFACT_NOT_FOUND",
                    f"Artifact file not found for {uri_loc}: {uri!r}",
                    uri_loc,
                )
            )
            continue

        actual_sha = sha256_file(file_path)
        if actual_sha != expected_sha:
            errors.append(
                _err(
                    "DOCKING_PROTOCOL_ARTIFACT_CHECKSUM_MISMATCH",
                    f"Checksum mismatch for {uri_loc}: expected {expected_sha}, actual {actual_sha}",
                    uri_loc,
                )
            )


# ---------------------------------------------------------------------------
# manifest serializer
# ---------------------------------------------------------------------------


def docking_protocol_manifest_to_dict(manifest: DockingProtocolManifest) -> dict[str, object]:
    """Serialize a DockingProtocolManifest to a deterministic JSON-compatible dict
    preserving every field."""
    rp = manifest.receptor_preparation
    lp = manifest.ligand_preparation
    cc = manifest.covalent_constraint
    sr = manifest.search_region
    ps = manifest.pose_selection

    return {
        "docking_protocol_id": manifest.docking_protocol_id,
        "engine_name": manifest.engine_name,
        "engine_version": manifest.engine_version,
        "engine_build_hash": manifest.engine_build_hash,
        "full_config_uri": manifest.full_config_uri,
        "full_config_sha256": manifest.full_config_sha256,
        "random_seed": manifest.random_seed,
        "receptor_preparation": {
            "tool_name": rp.tool_name,
            "tool_version": rp.tool_version,
            "input_structure_uri": rp.input_structure_uri,
            "input_structure_sha256": rp.input_structure_sha256,
            "output_receptor_uri": rp.output_receptor_uri,
            "output_receptor_sha256": rp.output_receptor_sha256,
            "pH_or_protonation_policy": rp.pH_or_protonation_policy,
            "water_policy": rp.water_policy,
            "cofactor_policy": rp.cofactor_policy,
            "metal_policy": rp.metal_policy,
        },
        "ligand_preparation": {
            "tool_name": lp.tool_name,
            "tool_version": lp.tool_version,
            "input_ligand_uri": lp.input_ligand_uri,
            "input_ligand_sha256": lp.input_ligand_sha256,
            "charge_model": lp.charge_model,
            "protonation_policy": lp.protonation_policy,
        },
        "covalent_constraint": {
            "representation": cc.representation,
            "target_atom_identity": cc.target_atom_identity,
            "ligand_atom_identity": cc.ligand_atom_identity,
            "constraint_parameters": (
                dict(cc.constraint_parameters)
                if isinstance(cc.constraint_parameters, Mapping)
                else cc.constraint_parameters
            ),
        },
        "search_region": {
            "center": list(sr.center),
            "size": list(sr.size),
            "unit": sr.unit,
        },
        "pose_selection": {
            "ranking_rule": ps.ranking_rule,
            "score_unit": ps.score_unit,
        },
        "failure_log_uri": manifest.failure_log_uri,
        "failure_log_sha256": manifest.failure_log_sha256,
    }


# ---------------------------------------------------------------------------
# index builder
# ---------------------------------------------------------------------------


def build_docking_score_eligible_result_index(
    results: list[CovalentGenerationResult],
    protocol_manifests: Mapping[str, object],
    artifact_root: Path,
) -> DockingScoreEligibleResultIndex:
    """Build a DockingScoreEligibleResultIndex from validated generation results.

    * Validates every input result via ``validate_generation_result`` first.
      Corrupt lifecycle rows raise ``ContractError`` before any output.
    * Filters to valid/exported/eligible/succeeded rows with
      ``covalent_docking_score``.
    * Requires every surviving row to have an ``artifacts["docking_protocol_manifest"]``
      ``ArtifactRef`` whose URI maps to a supplied manifest in
      ``protocol_manifests``.
    * Validates the manifest ``ArtifactRef`` itself against ``artifact_root``,
      then validates all internal protocol artifacts.
    * Missing association, missing supplied manifest, manifest ref mismatch,
      incomplete manifest, bad URI, or checksum mismatch raises
      ``ContractError`` — succeeded rows are never silently omitted.
    * QuickVina2-only baseline rows (no covalent docking score) are omitted
      normally.
    * Does not mutate input results.
    """
    artifact_root = Path(artifact_root)

    # 1. Validate every result first
    _validate_all_results(results)

    # 2. Build eligible entries
    entries: list[DockingScoreEligibleResult] = []

    for result in results:
        # Filter: valid + exported + eligible + succeeded + has covalent_docking_score
        if not (
            result.generation_validity_status == "valid"
            and result.complex_export_status == "exported"
            and result.docking_eligibility_status == "eligible"
            and result.docking_run_status == "succeeded"
            and result.covalent_docking_score is not None
        ):
            continue

        # Require docking_protocol_manifest artifact ref
        manifest_ref = result.artifacts.get("docking_protocol_manifest")
        if manifest_ref is None:
            raise ContractError(
                code="DOCKING_PROTOCOL_INDEX_MANIFEST_ASSOCIATION_MISSING",
                owner="evaluation",
                message=(
                    f"Succeeded result {result.request_id!r}/{result.sample_id} "
                    "has no artifacts[docking_protocol_manifest]"
                ),
                location=f"results[{result.request_id!r}/{result.sample_id}].artifacts",
            )
        if manifest_ref.role != "docking_protocol_manifest":
            raise ContractError(
                code="DOCKING_PROTOCOL_INDEX_MANIFEST_ROLE_INVALID",
                owner="evaluation",
                message=(
                    f"Succeeded result {result.request_id!r}/{result.sample_id} "
                    "must link an ArtifactRef with role='docking_protocol_manifest'"
                ),
                location=f"results[{result.request_id!r}/{result.sample_id}].artifacts",
            )

        # Validate the manifest ArtifactRef against artifact_root
        v_receipt = validate_artifact_ref(manifest_ref, root=artifact_root)
        if not v_receipt.passed:
            err = v_receipt.errors[0]
            raise ContractError(
                code=err.code,
                owner="evaluation",
                message=err.message,
                location=err.location,
                details=err.details,
            )

        # Require the manifest in the supplied protocol_manifests
        manifest = protocol_manifests.get(manifest_ref.uri)
        if manifest is None:
            raise ContractError(
                code="DOCKING_PROTOCOL_INDEX_MANIFEST_NOT_SUPPLIED",
                owner="evaluation",
                message=(
                    f"Result {result.request_id!r}/{result.sample_id} references "
                    f"manifest {manifest_ref.uri!r} not present in protocol_manifests"
                ),
                location=f"results[{result.request_id!r}/{result.sample_id}]",
            )
        if not isinstance(manifest, DockingProtocolManifest):
            raise ContractError(
                code="DOCKING_PROTOCOL_INDEX_MANIFEST_WRONG_TYPE",
                owner="evaluation",
                message=(
                    f"protocol_manifests[{manifest_ref.uri!r}] must be "
                    f"DockingProtocolManifest, got {type(manifest).__name__}"
                ),
                location=f"protocol_manifests[{manifest_ref.uri!r}]",
            )

        # Bind the supplied manifest object to the exact file referenced by the
        # result row. Validating both independently is insufficient: without
        # this comparison a caller could substitute a different valid manifest.
        linked_manifest_path = resolve_artifact_path(manifest_ref, root=artifact_root)
        linked_manifest = load_docking_protocol_manifest(linked_manifest_path)
        if docking_protocol_manifest_to_dict(linked_manifest) != docking_protocol_manifest_to_dict(
            manifest
        ):
            raise ContractError(
                code="DOCKING_PROTOCOL_INDEX_MANIFEST_CONTENT_MISMATCH",
                owner="evaluation",
                message=(
                    f"protocol_manifests[{manifest_ref.uri!r}] does not match "
                    "the manifest file referenced by the result"
                ),
                location=f"protocol_manifests[{manifest_ref.uri!r}]",
            )

        # Validate the manifest's internal artifacts
        v_receipt = validate_docking_protocol_manifest(manifest, artifact_root)
        if not v_receipt.passed:
            err = v_receipt.errors[0]
            raise ContractError(
                code=err.code,
                owner="evaluation",
                message=err.message,
                location=f"protocol_manifests[{manifest_ref.uri!r}].{err.location}"
                if err.location
                else f"protocol_manifests[{manifest_ref.uri!r}]",
                details=err.details,
            )

        entries.append(
            DockingScoreEligibleResult(
                request_id=result.request_id,
                sample_id=result.sample_id,
                docking_protocol_id=manifest.docking_protocol_id,
                covalent_docking_score=result.covalent_docking_score,
                noncovalent_vina_score=result.noncovalent_vina_score,
                engine_name=manifest.engine_name,
                engine_version=manifest.engine_version,
            )
        )

    # Sort by (request_id, sample_id, docking_protocol_id)
    entries.sort(key=lambda e: (e.request_id, e.sample_id, e.docking_protocol_id))

    return DockingScoreEligibleResultIndex(entries=tuple(entries))


def _validate_all_results(results: list[CovalentGenerationResult]) -> None:
    """Validate every result row.  Corrupt lifecycle -> ContractError."""
    for i, result in enumerate(results):
        receipt = validate_generation_result(result)
        if not receipt.passed:
            err = receipt.errors[0]
            raise ContractError(
                code=err.code,
                owner=err.owner,
                message=err.message,
                location=f"results[{i}].{err.location}" if err.location else f"results[{i}]",
                details=err.details,
            )


# ---------------------------------------------------------------------------
# index serializer
# ---------------------------------------------------------------------------


def docking_score_eligible_result_index_to_dict(
    index: DockingScoreEligibleResultIndex,
) -> dict[str, object]:
    """Serialize a DockingScoreEligibleResultIndex to a JSON-compatible dict."""
    entries: list[dict[str, object]] = []
    for e in index.entries:
        entries.append(
            {
                "request_id": e.request_id,
                "sample_id": e.sample_id,
                "docking_protocol_id": e.docking_protocol_id,
                "covalent_docking_score": e.covalent_docking_score,
                "noncovalent_vina_score": e.noncovalent_vina_score,
                "engine_name": e.engine_name,
                "engine_version": e.engine_version,
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "contract_version": CONTRACT_VERSION,
        "role": "docking_score_eligible_result_index",
        "format": "json",
        "counts": {"total_eligible_entries": len(entries)},
        "entries": entries,
    }


# ---------------------------------------------------------------------------
# index writer
# ---------------------------------------------------------------------------


def write_docking_score_eligible_result_index(
    index: DockingScoreEligibleResultIndex,
    path: Path,
) -> ArtifactRef:
    """Write *index* to *path* atomically.

    Uses a same-directory tempfile that is fsync'd and os.replace'd into
    place.  Returns an ``ArtifactRef`` for the written file.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    payload = docking_score_eligible_result_index_to_dict(index)
    json_text = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)

    fd, tmp_path_str = tempfile.mkstemp(
        suffix=".tmp",
        prefix=".docking_score_eligible_result_index",
        dir=str(path.parent),
    )
    tmp_path = Path(tmp_path_str)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(json_text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    except BaseException:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        raise

    return ArtifactRef(
        uri=path.name,
        sha256=sha256_file(path),
        format="json",
        schema_version=SCHEMA_VERSION,
        role="docking_score_eligible_result_index",
        bytes=path.stat().st_size,
    )


# ---------------------------------------------------------------------------
# internal helpers
# ---------------------------------------------------------------------------


def _manifest_sha256(manifest: DockingProtocolManifest) -> str:
    d = docking_protocol_manifest_to_dict(manifest)
    return hashlib.sha256(
        json.dumps(d, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _err(
    code: str,
    message: str,
    location: str | None = None,
) -> ContractErrorInfo:
    return ContractErrorInfo(
        code=code,
        owner="evaluation",
        message=message,
        location=location,
    )
