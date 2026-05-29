from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generic, Mapping, Optional, TypeVar

from covalent_design.contracts.errors import ContractError, ContractErrorInfo


CONTRACT_VERSION = "1.0.0"
SCHEMA_VERSION = "1"

QualitySeverity = ("Q0", "Q1", "Q2")
RuleWarheadStatus = ("calibrated", "pending", "not_applicable")
RuleGeometryStatus = ("calibrated", "pending", "disabled")
VisualCheckStatus = ("pending", "pass", "fail", "needs_rule_review")

REQUEST_VALIDATION_ERROR_CODES = (
    "REQUEST_STRUCTURE_UNREADABLE",
    "REQUEST_TARGET_RESIDUE_NOT_FOUND",
    "REQUEST_TARGET_RESIDUE_AMBIGUOUS",
    "REQUEST_TARGET_ATOM_NOT_FOUND",
    "REQUEST_RESIDUE_NAME_MISMATCH",
    "REQUEST_FAMILY_UNSUPPORTED",
    "REQUEST_RESIDUE_FAMILY_CONFLICT",
    "REQUEST_ATOM_FAMILY_CONFLICT",
    "REQUEST_SAMPLE_COUNT_INVALID",
    "REQUEST_LIGAND_SIZE_INVALID",
    "REQUEST_LIGAND_SIZE_RANGE_INVALID",
    "REQUEST_LIGAND_SIZE_CONFLICT",
    "REQUEST_REQUIRED_CHEMICAL_STATE_UNAVAILABLE",
)

GenerationValidityStatus = ("valid", "invalid")
ComplexExportStatus = ("not_applicable", "exported", "failed")
DockingEligibilityStatus = ("not_applicable", "eligible", "not_evaluable")
DockingRunStatus = ("not_applicable", "not_run", "succeeded", "failed")

FAILURE_REASON_CODES = (
    "LIGAND_RECONSTRUCTION_FAILED",
    "LIGAND_CHEMISTRY_INVALID",
    "NO_COVALENT_EDGE_PREDICTED",
    "COVALENT_EDGE_BELOW_THRESHOLD",
    "REACTION_FAMILY_RULE_FAIL",
    "WARHEAD_MATCH_FAIL",
    "VALENCE_CHECK_FAIL",
    "GEOMETRY_CHECK_FAIL",
    "REQUIRED_GATE_STATE_UNAVAILABLE",
    "UNSUPPORTED_GENERATED_CHEMISTRY",
    "COMPLEX_EXPORT_FAILED",
    "DOCKING_NOT_EVALUABLE",
    "DOCKING_RUN_FAILED",
)

EdgeValidityCheckName = (
    "target_atom",
    "ligand_atom_class",
    "bond_type",
    "single_edge_representability",
    "warhead_smarts",
    "forbidden_smarts",
    "valence",
    "protonation",
    "geometry",
)
EdgeValidityCheckStatus = ("pass", "fail", "not_applicable", "not_evaluable")


@dataclass(frozen=True)
class ArtifactRef:
    uri: str
    sha256: str
    format: str
    schema_version: str = SCHEMA_VERSION
    role: str = ""
    bytes: int = 0

    def __post_init__(self) -> None:
        # Compatibility with the pre-1.0 positional order:
        # ArtifactRef(uri, sha256, format, bytes, role).
        if isinstance(self.schema_version, int):
            object.__setattr__(self, "bytes", self.schema_version)
            object.__setattr__(self, "schema_version", SCHEMA_VERSION)


@dataclass(frozen=True, init=False)
class ValidationReceipt:
    validator: str
    contract_version: str
    input_sha256: str
    passed: bool
    warnings: tuple[ContractErrorInfo, ...]
    errors: tuple[ContractErrorInfo, ...]

    def __init__(
        self,
        validator: str,
        contract_version: str,
        input_sha256: str,
        passed: Optional[bool] = None,
        *,
        ok: Optional[bool] = None,
        warnings: tuple[ContractErrorInfo, ...] = (),
        errors: tuple[ContractErrorInfo, ...] = (),
    ) -> None:
        if passed is None and ok is None:
            raise TypeError("ValidationReceipt requires passed or ok")
        if passed is not None and ok is not None and passed != ok:
            raise ValueError("ValidationReceipt passed and ok disagree")
        object.__setattr__(self, "validator", validator)
        object.__setattr__(self, "contract_version", contract_version)
        object.__setattr__(self, "input_sha256", input_sha256)
        object.__setattr__(self, "passed", bool(passed if passed is not None else ok))
        object.__setattr__(self, "warnings", tuple(warnings))
        object.__setattr__(self, "errors", tuple(errors))

    @property
    def ok(self) -> bool:
        return self.passed


@dataclass(frozen=True)
class Provenance:
    producer_name: str = "covalent_design"
    producer_version: str = ""
    git_commit: str = ""
    inputs: Mapping[str, ArtifactRef] = field(default_factory=dict)


T = TypeVar("T")


@dataclass(frozen=True)
class ContractEnvelope(Generic[T]):
    payload: T
    artifacts: tuple[ArtifactRef, ...]
    receipt: ValidationReceipt
    provenance: Provenance = field(default_factory=Provenance)


@dataclass(frozen=True)
class ProteinAtomIdentity:
    chain_id: Optional[str]
    residue_number: Optional[int]
    residue_name: str
    atom_name: str
    altloc: Optional[str] = None
    insertion_code: Optional[str] = None
    structure_model: Optional[int] = None
    asym_id: Optional[str] = None
    atom_serial: Optional[int] = None


@dataclass(frozen=True)
class LigandAtomIdentity:
    ligand_id: str
    atom_name: str
    atom_index: Optional[int] = None
    chain_id: Optional[str] = None
    asym_id: Optional[str] = None
    residue_number: Optional[int] = None
    altloc: Optional[str] = None


@dataclass(frozen=True)
class SourceRecordLineage:
    source_database: str
    source_version: str
    source_record_id: str
    raw_manifest_file: str
    raw_file_path: str
    raw_file_sha256: str
    row_index: int


@dataclass(frozen=True)
class SourceIngestRecord:
    source_database: str
    source_version: str
    source_record_id: str
    raw_manifest_file: str
    raw_file_path: str
    raw_file_sha256: str
    row_index: int
    lineage: Mapping[str, object]
    protein: Mapping[str, object]
    ligand: Mapping[str, object]
    linkage: Mapping[str, object]
    metadata: Mapping[str, object]
    source_lineage: Optional[SourceRecordLineage] = None
    target_atom_identity: Optional[ProteinAtomIdentity] = None
    ligand_atom_identity: Optional[LigandAtomIdentity] = None


@dataclass(frozen=True)
class EdgeValidityCheck:
    check_name: str
    status: str
    observed_value: str
    threshold_or_rule: str
    rule_table_version: str
    failure_code: Optional[str] = None


# Task 17+ model batch error codes

MODEL_BATCH_ERROR_CODES = (
    "MODEL_BATCH_ARTIFACT_MISSING",
    "MODEL_BATCH_ARTIFACT_UNREADABLE",
    "MODEL_BATCH_ARTIFACT_CHECKSUM_MISMATCH",
    "MODEL_BATCH_ARTIFACT_ROLE_MISSING",
    "MODEL_BATCH_CONTRACT_VERSION_UNSUPPORTED",
    "MODEL_BATCH_REQUIRED_STATE_UNAVAILABLE",
)

# sampling system failure categories

SAMPLING_SYSTEM_FAILURE_CATEGORIES = (
    "crash",
    "oom",
    "timeout",
    "retry_exhausted",
    "checkpoint_load_failed",
    "sampler_invariant_violation",
)

LigandStatus = ("present", "absent", "unparseable")

# helper types


@dataclass(frozen=True)
class CovalentEdge:
    """A predicted or labelled protein-ligand covalent cross edge."""

    protein_atom: ProteinAtomIdentity
    ligand_atom: LigandAtomIdentity
    bond_type: str  # from bond_type_vocabulary


@dataclass(frozen=True)
class GeometryMetrics:
    """Local covalent geometry measurements for a single candidate edge."""

    bond_length: Optional[float]  # angstroms
    protein_side_angle: Optional[float]  # degrees
    ligand_side_angle: Optional[float]  # degrees


@dataclass(frozen=True)
class MoleculeQuality:
    """Placeholder molecular-quality metrics for a generated ligand.

    Fields are nullable - populated only when a parseable ligand exists.
    """

    qed: Optional[float] = None
    sa_score: Optional[float] = None
    log_p: Optional[float] = None
    molecular_weight: Optional[float] = None


@dataclass(frozen=True)
class CovalentGenerationResult:
    """Per-sample generation result with full lifecycle and diagnostic fields.

    This is the authoritative result schema consumed by result_writer (Task 28),
    evaluation (Task 30), and export (Task 29).  Every attempted sample produces
    exactly one result row.
    """

    # ---- identity ----
    request_id: str
    sample_id: int
    residue_reaction_family: str
    target_atom_identity: ProteinAtomIdentity

    # ---- lifecycle statuses (four separated states) ----
    generation_validity_status: str  # "valid" | "invalid"
    complex_export_status: str  # "not_applicable" | "exported" | "failed"
    docking_eligibility_status: str  # "not_applicable" | "eligible" | "not_evaluable"
    docking_run_status: str  # "not_applicable" | "not_run" | "succeeded" | "failed"

    # ---- failure information ----
    primary_failure_reason: Optional[str]  # None only for fully successful path
    secondary_failure_reasons: tuple[str, ...]  # deduplicated; empty when none

    # ---- ligand state ----
    generated_ligand_status: str = "absent"  # "present" | "absent" | "unparseable"
    predicted_ligand_attachment_atom: Optional[LigandAtomIdentity] = None
    predicted_covalent_edge: Optional["CovalentEdge"] = None

    # ---- scores and metrics ----
    covalent_edge_score: Optional[float] = None
    geometry_metrics: Optional["GeometryMetrics"] = None
    molecular_quality_metrics: Optional["MoleculeQuality"] = None

    # ---- warhead evidence (matched is structural; predicted is model diagnostic) ----
    matched_warhead_type: Optional[str] = None
    predicted_warhead_type: Optional[str] = None

    # ---- docking scores ----
    covalent_docking_score: Optional[float] = None  # only when docking_run_status == "succeeded"
    noncovalent_vina_score: Optional[float] = None  # baseline / compatibility metric

    # ---- gate check detail ----
    edge_validity_checks: tuple[EdgeValidityCheck, ...] = ()  # empty only when no edge was scored

    # ---- file references ----
    artifacts: Mapping[str, ArtifactRef] = field(default_factory=dict)
    # Expected keys: "ligand_sdf", "complex_mmcif", "complex_pdb" (optional compatibility)


@dataclass(frozen=True)
class EdgeDenominators:
    candidate_count: int
    natural_candidate_count: int
    forced_positive_count: int
    eligible_edge_count: int
    masked_candidate_count: int
    edge_loss_denominator: int
    bond_type_loss_denominator: int
    geometry_loss_denominator: int
    message_passing_candidate_count: int
    gate_evaluated_count: int

    def validate(self) -> None:
        from covalent_design.contracts.denominators import validate_edge_denominators

        receipt = validate_edge_denominators(self)
        if not receipt.passed:
            raise ContractError(
                code=receipt.errors[0].code,
                owner=receipt.errors[0].owner,
                message=receipt.errors[0].message,
                location=receipt.errors[0].location,
                details=receipt.errors[0].details,
            )


@dataclass(frozen=True)
class EvaluationSummary:
    requested_sample_count: int
    request_validation_error_sample_count: int
    accepted_request_sample_count: int
    attempted_sample_count: int
    sampling_system_failure_count: int
    valid_generated_internal_count: int
    invalid_generated_sample_count: int
    exported_valid_complex_count: int
    valid_export_failure_count: int
    docking_evaluable_valid_sample_count: int
    valid_but_not_docking_evaluable_sample_count: int
    docking_not_run_valid_sample_count: int
    docking_failed_valid_sample_count: int
    successfully_docked_valid_sample_count: int

    def validate(self) -> None:
        from covalent_design.contracts.denominators import validate_evaluation_summary

        receipt = validate_evaluation_summary(self)
        if not receipt.passed:
            raise ContractError(
                code=receipt.errors[0].code,
                owner=receipt.errors[0].owner,
                message=receipt.errors[0].message,
                location=receipt.errors[0].location,
                details=receipt.errors[0].details,
            )


# Task 17+ model / training / inference / evaluation types


# -- Model batch (Task 17) --


@dataclass(frozen=True)
class BatchRecordHeader:
    """Provenance layer for one record in a ModelBatch."""

    record_id: str
    residue_reaction_family: str
    quality_tier: str  # "Q0" | "Q1" | "Q2"
    visual_check_status: str  # "pending" | "pass" | "fail" | "needs_rule_review"
    chemical_state_status: str  # "explicit" | "inferred" | "unavailable"
    target_atom_identity: ProteinAtomIdentity
    target_atom_index: int
    target_atom_artifact_role: str = "protein_atom_table"
    split_assignment: Optional[str] = None  # "train" | "val" | "test" | "excluded"
    fallback_reason: Optional[str] = None
    artifact_refs: Mapping[str, ArtifactRef] = field(default_factory=dict)
    batch_index: int = -1  # set by make_model_batch()

    def __post_init__(self) -> None:
        if self.target_atom_identity is None:
            raise ValueError("BatchRecordHeader.target_atom_identity is required")
        if self.target_atom_index is None:
            raise ValueError("BatchRecordHeader.target_atom_index is required")
        if self.target_atom_index < 0:
            raise ValueError("BatchRecordHeader.target_atom_index must be non-negative")
        if not self.target_atom_artifact_role:
            raise ValueError("BatchRecordHeader.target_atom_artifact_role is required")


@dataclass(frozen=True)
class BatchTensors:
    """Computational layer for a ModelBatch - shapes and type metadata only.

    Actual tensor data is loaded by the consumer (PMDM adapter) from
    the referenced artifact files.  This dataclass records expected shapes
    and dtypes so that implementers and inspect_batch can verify correctness
    before expensive tensor construction.
    """

    protein_coords_shape: tuple[int, ...]  # (B, N_prot, 3)
    ligand_coords_shape: tuple[int, ...]  # (B, N_lig, 3)
    protein_atom_types_shape: tuple[int, ...]  # (B, N_prot)
    ligand_atom_types_shape: tuple[int, ...]  # (B, N_lig)
    ligand_bonds_shape: tuple[int, ...]  # (B, N_lig, N_lig)
    edge_candidates_shape: tuple[int, ...]  # (B, N_candidates)
    positive_label_mask_shape: tuple[int, ...]  # (B, N_candidates)
    candidate_to_ligand_map_shape: tuple[int, ...]  # (B, N_candidates)
    candidate_to_protein_map_shape: tuple[int, ...]  # (B, N_candidates)
    dtype: str = "float32"  # coordinate / logit dtype
    index_dtype: str = "int64"
    coordinate_frame: str = "original_pdb"


@dataclass(frozen=True)
class ModelBatch:
    """Typed batch carrying both provenance and tensor metadata.

    Consumed by model forward (Task 19) and training (Task 22).
    """

    records: tuple[BatchRecordHeader, ...]
    tensors: BatchTensors
    static_edge_candidates_refs: Mapping[str, ArtifactRef]
    denominators_expected: EdgeDenominators
    batch_spec: Optional["BatchSpec"] = None


@dataclass(frozen=True)
class BatchSpec:
    """Static configuration carried alongside every ModelBatch.

    Defines vocabulary, size constraints, and source-hash binding
    so downstream consumers can validate compatibility.
    """

    bond_type_vocabulary: tuple[str, ...]  # e.g. ("no_edge", "carbon-sulfur", ...)
    max_protein_atoms: int
    max_ligand_atoms: int
    max_candidates: int
    candidate_radius_angstrom: float = 4.0
    coordinate_frame: str = "original_pdb"
    records_jsonl_hash: Optional[str] = None


@dataclass(frozen=True)
class BatchInspectionReport:
    """Output of inspect_batch CLI for a single record."""

    schema_version: str = SCHEMA_VERSION
    contract_version: str = CONTRACT_VERSION
    record_id: str = ""
    batch_index: int = -1
    provenance: Optional[BatchRecordHeader] = None
    tensor_shapes: Optional[dict[str, tuple[int, ...]]] = None
    denominators_expected: Optional[EdgeDenominators] = None
    batch_spec: Optional[BatchSpec] = None
    warnings: tuple[str, ...] = ()


# -- Model forward (Task 19-20) --


MESSAGE_WEIGHT_SOURCE_DETACHED_EDGE_PROBABILITY = "detached_edge_probability"
ALLOWED_MESSAGE_WEIGHT_SOURCES = (
    MESSAGE_WEIGHT_SOURCE_DETACHED_EDGE_PROBABILITY,
)


@dataclass(frozen=True)
class ModelForwardOutput:
    """Output of one model forward pass, combining PMDM backbone and covalent heads."""

    pmdm_outputs: Mapping[str, object]  # PMDM-adapter output dict
    edge_logits: object  # Tensor: (B, N_candidates)
    bond_type_logits: object  # Tensor: (B, N_candidates, N_bond_types)
    family_logits: object  # Tensor: (B, N_families)
    edge_prob_message_weights: object  # detached Tensor: (B, N_candidates)
    message_weight_source: str  # "detached_edge_probability"
    denominators_observed: EdgeDenominators

    def __post_init__(self) -> None:
        if getattr(self.edge_prob_message_weights, "requires_grad", False):
            raise ValueError(
                "edge_prob_message_weights must be detached predicted probabilities; "
                "provenance tests must also verify that this tensor comes from the "
                "model prediction path, not labels or ground truth."
            )
        if self.message_weight_source not in ALLOWED_MESSAGE_WEIGHT_SOURCES:
            raise ValueError(
                "message_weight_source must prove the detached prediction path; "
                f"expected {MESSAGE_WEIGHT_SOURCE_DETACHED_EDGE_PROBABILITY!r}, "
                f"got {self.message_weight_source!r}"
            )


# -- Stepwise candidates (Task 18) --


@dataclass(frozen=True)
class StepwiseCandidate:
    """One covalent edge candidate at a single denoising timestep."""

    local_index: int  # temporary index within this timestep
    ligand_atom_index: int  # stable across timesteps
    target_atom: ProteinAtomIdentity
    is_positive_label: bool
    is_forced_positive: bool  # forced-in when noise moved it outside radius
    within_radius: bool
    distance: float  # angstroms, current noisy coords


@dataclass(frozen=True)
class StepwiseCandidateSet:
    """All covalent edge candidates rebuilt at one denoising timestep."""

    timestep_index: int
    timestep_value: float  # t in [0, 1]
    candidates: tuple[StepwiseCandidate, ...]
    positive_label_ligand_atom_index: int  # from Task 12 static edge_candidates
    positive_label_target_atom: ProteinAtomIdentity
    positive_label_bond_type: str
    denominators: EdgeDenominators
    empty_radius_window: bool


# -- Training dataset (Task 22) --


@dataclass(frozen=True)
class TrainingRecordEntry:
    """Metadata for one record eligible for a training split."""

    record_id: str
    residue_reaction_family: str
    quality_tier: str
    visual_check_status: str
    fallback_reason: Optional[str]
    manual_review_status: Optional[str]
    artifact_refs: Mapping[str, ArtifactRef]


@dataclass(frozen=True)
class ExclusionSummary:
    """Why records were excluded from a training split."""

    total_accepted: int
    records_in_split: int
    excluded_by_policy: int
    exclusion_reasons: Mapping[str, int]


@dataclass(frozen=True)
class TrainingDatasetIndex:
    """Index of records allocated to one training split."""

    policy: Mapping[str, object]  # TrainingDataPolicy serialised
    split_name: str  # "train" | "val" | "test"
    records: tuple[TrainingRecordEntry, ...]
    excluded_summary: ExclusionSummary


# -- Loss masks & reports (Task 23-24) --


@dataclass(frozen=True)
class MaskAudit:
    """Per-timestep decomposition of which candidates were masked and why."""

    candidate_count: int
    natural_positive_count: int
    forced_positive_count: int
    natural_negative_count: int
    zero_negative_count: int

    masked_by_pending_smarts: int
    masked_by_pending_geometry: int
    masked_by_missing_chemical_state: int
    masked_by_q2_exclusion: int
    masked_by_forced_positive_exclusion: int

    edge_loss_eligible_count: int
    bond_type_loss_eligible_count: int
    geometry_loss_eligible_count: int
    message_passing_candidate_count: int
    gate_evaluated_count: int


@dataclass(frozen=True)
class DenominatorsStratum:
    """Denominator and mask audit for one (family, timestep_bucket) stratum."""

    residue_reaction_family: str
    timestep_bucket: str  # "early" | "mid" | "late"
    denominators: EdgeDenominators
    mask_audit: MaskAudit


@dataclass(frozen=True)
class LossReport:
    """Structured loss report emitted by one training step."""

    schema_version: str = SCHEMA_VERSION
    contract_version: str = CONTRACT_VERSION
    step: int = 0
    total_loss: float = 0.0
    components: Mapping[str, float] = field(default_factory=dict)
    denominators: Optional[EdgeDenominators] = None
    mask_audit: Optional[MaskAudit] = None
    strata: tuple[DenominatorsStratum, ...] = ()

    def __post_init__(self) -> None:
        missing = [
            key
            for key in REQUIRED_LOSS_COMPONENT_KEYS
            if key not in self.components
        ]
        if missing:
            raise ValueError(
                "LossReport.components missing required keys: "
                + ", ".join(missing)
            )

    def to_dict(self) -> dict[str, object]:
        """Serialise to JSON-compatible dict (one row in train_metrics.jsonl)."""
        result: dict[str, object] = {
            "schema_version": self.schema_version,
            "contract_version": self.contract_version,
            "step": self.step,
            "total_loss": self.total_loss,
            "components": dict(self.components),
        }
        if self.denominators is not None:
            result["denominators"] = _denominators_dict(self.denominators)
        if self.mask_audit is not None:
            result["mask_audit"] = _mask_audit_dict(self.mask_audit)
        if self.strata:
            result["strata"] = [
                {
                    "residue_reaction_family": s.residue_reaction_family,
                    "timestep_bucket": s.timestep_bucket,
                    "denominators": _denominators_dict(s.denominators),
                }
                for s in self.strata
            ]
        return result


def _denominators_dict(d: EdgeDenominators) -> dict[str, int]:
    return {
        "candidate_count": d.candidate_count,
        "natural_candidate_count": d.natural_candidate_count,
        "forced_positive_count": d.forced_positive_count,
        "eligible_edge_count": d.eligible_edge_count,
        "masked_candidate_count": d.masked_candidate_count,
        "edge_loss_denominator": d.edge_loss_denominator,
        "bond_type_loss_denominator": d.bond_type_loss_denominator,
        "geometry_loss_denominator": d.geometry_loss_denominator,
        "message_passing_candidate_count": d.message_passing_candidate_count,
        "gate_evaluated_count": d.gate_evaluated_count,
    }


def _mask_audit_dict(m: MaskAudit) -> dict[str, int]:
    return {
        "candidate_count": m.candidate_count,
        "natural_positive_count": m.natural_positive_count,
        "forced_positive_count": m.forced_positive_count,
        "natural_negative_count": m.natural_negative_count,
        "zero_negative_count": m.zero_negative_count,
        "masked_by_pending_smarts": m.masked_by_pending_smarts,
        "masked_by_pending_geometry": m.masked_by_pending_geometry,
        "masked_by_missing_chemical_state": m.masked_by_missing_chemical_state,
        "masked_by_q2_exclusion": m.masked_by_q2_exclusion,
        "masked_by_forced_positive_exclusion": m.masked_by_forced_positive_exclusion,
        "edge_loss_eligible_count": m.edge_loss_eligible_count,
        "bond_type_loss_eligible_count": m.bond_type_loss_eligible_count,
        "geometry_loss_eligible_count": m.geometry_loss_eligible_count,
        "message_passing_candidate_count": m.message_passing_candidate_count,
        "gate_evaluated_count": m.gate_evaluated_count,
    }


# -- Training run manifest (Task 25) --


REQUIRED_LOSS_COMPONENT_KEYS = (
    "pmdm_position_loss",
    "pmdm_atom_loss",
    "covalent_edge_loss",
    "covalent_bond_type_loss",
    "covalent_geometry_loss",
    "family_aux_loss",
)

TRAINING_REQUIRED_INPUT_HASH_KEYS = (
    "records_jsonl",
    "split_index",
    "rule_table",
)

TRAINING_RELEASE_GATE_INPUT_HASH_KEYS = (
    "quality_report",
    "visual_check_index",
    "release_gate",
)


@dataclass(frozen=True)
class TrainingRunManifest:
    """Provenance manifest for one training run."""

    schema_version: str = SCHEMA_VERSION
    contract_version: str = CONTRACT_VERSION
    role: str = "training_run_manifest"
    run_id: str = ""
    training_config_resolved_hash: str = ""
    input_hashes: Mapping[str, str] = field(default_factory=dict)
    checkpoint_dir: str = ""
    train_metrics_uri: str = ""
    validation_metrics_uri: str = ""
    denominator_report_uri: str = ""
    train_completed: bool = False
    epochs_completed: int = 0
    steps_completed: int = 0
    crash_recovery: Optional[Mapping[str, object]] = None


# -- Inference run manifest (Task 27) --


@dataclass(frozen=True)
class SamplingSystemFailure:
    """One run-level sampling failure event (not a generated sample)."""

    request_id: str
    sample_id: int
    failure_category: str  # one of SAMPLING_SYSTEM_FAILURE_CATEGORIES
    failure_timestamp: str  # ISO 8601
    traceback_hash: str  # SHA-256 of normalised traceback
    log_uri: str
    retry_count: int
    resource_snapshot: Optional[Mapping[str, object]] = None
    message: str = ""


@dataclass(frozen=True)
class GenerationRunManifest:
    """Manifest for one generation run, returned by generate()."""

    schema_version: str = SCHEMA_VERSION
    contract_version: str = CONTRACT_VERSION
    role: str = "generation_run_manifest"
    job_id: str = ""
    request_id: str = ""
    checkpoint_ref: Optional[ArtifactRef] = None
    accepted_request_sample_count: int = 0
    attempted_sample_count: int = 0
    sampling_system_failure_count: int = 0
    result_count: int = 0
    artifacts: Mapping[str, ArtifactRef] = field(default_factory=dict)
