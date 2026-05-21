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
    "warhead_smarts",
    "forbidden_smarts",
    "valence",
    "protonation",
    "geometry",
    "single_edge_representability",
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


@dataclass(frozen=True)
class CovalentGenerationResult:
    request_id: str
    sample_id: int
    residue_reaction_family: str
    target_atom_identity: ProteinAtomIdentity
    generation_validity_status: str
    complex_export_status: str
    docking_eligibility_status: str
    docking_run_status: str
    primary_failure_reason: Optional[str]
    secondary_failure_reasons: tuple[str, ...]
    edge_validity_checks: tuple[EdgeValidityCheck, ...]
    artifacts: Mapping[str, ArtifactRef] = field(default_factory=dict)


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
