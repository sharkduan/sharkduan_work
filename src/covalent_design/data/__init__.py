"""Data processing APIs."""

from covalent_design.data.conflicts import ConflictAnchor, ConflictGroup
from covalent_design.data.identity import (
    AnnotationValue,
    CanonicalLinkageIdentity,
    IdentityInputError,
    IdentityResolutionResult,
    MergedIdentityRecord,
    RejectedIdentityInput,
    build_record_id,
    canonical_identity_from_record,
    normalize_identity_json,
    resolve_identities,
)
from covalent_design.data.records import build_record_index
from covalent_design.data.artifact_manifests import finalize_record_manifests
from covalent_design.data.splits import SplitPolicy, build_splits
from covalent_design.data.quality_report import write_quality_report
from covalent_design.data.v2_conversion import (
    convert_staged_manifest,
    convert_staged_source,
)
from covalent_design.data.v2_intake import (
    V2DownloadRequest,
    V2StagingSummary,
    serialize_v2_staging_summary,
    stage_source_manifest,
    v2_staging_summary_to_dict,
)
from covalent_design.data.v2_license import (
    LICENSE_STATUS_ALLOWED,
    LICENSE_STATUS_BLOCKED,
    LICENSE_STATUS_MANUAL_EXEMPT,
    LICENSE_STATUS_RESTRICTED,
    LICENSE_STATUS_UNKNOWN,
    LICENSE_STATUSES,
    LicenseGateReport,
    LicenseGateSourceReport,
    SourceLicenseAudit,
    audit_v2_training_eligibility,
    license_gate_report_to_dict,
    load_source_license_audit,
    source_license_audit_from_dict,
)
from covalent_design.data.v2_manifests import (
    ALLOWED_CHECKSUM_ALGORITHMS,
    ALLOWED_INTAKE_MODES,
    ALLOWED_PARSER_TARGETS,
    ALLOWED_SOURCE_NAMES,
    V2DataIntakeManifest,
    serialize_v2_data_intake_manifest,
    v2_data_intake_manifest_from_dict,
    validate_v2_data_intake_manifest,
)

_NORMALIZE_EXPORTS = {
    "AcceptedRecord",
    "AtomMapping",
    "NormalizationPayload",
    "NormalizedLinkageRecord",
    "RejectedRecord",
    "normalize_linkages",
    "normalize_with_identity_resolution",
}


def __getattr__(name: str):
    if name in _NORMALIZE_EXPORTS:
        from covalent_design.data import normalize as _normalize

        return getattr(_normalize, name)
    if name == "QualityGateResult":
        from covalent_design.data.quality import QualityGateResult

        return QualityGateResult
    raise AttributeError(name)

__all__ = [
    "AcceptedRecord",
    "AnnotationValue",
    "AtomMapping",
    "ALLOWED_CHECKSUM_ALGORITHMS",
    "ALLOWED_INTAKE_MODES",
    "ALLOWED_PARSER_TARGETS",
    "ALLOWED_SOURCE_NAMES",
    "CanonicalLinkageIdentity",
    "ConflictAnchor",
    "ConflictGroup",
    "IdentityInputError",
    "IdentityResolutionResult",
    "MergedIdentityRecord",
    "NormalizationPayload",
    "NormalizedLinkageRecord",
    "QualityGateResult",
    "RejectedIdentityInput",
    "RejectedRecord",
    "SplitPolicy",
    "LICENSE_STATUS_ALLOWED",
    "LICENSE_STATUS_BLOCKED",
    "LICENSE_STATUS_MANUAL_EXEMPT",
    "LICENSE_STATUS_RESTRICTED",
    "LICENSE_STATUS_UNKNOWN",
    "LICENSE_STATUSES",
    "LicenseGateReport",
    "LicenseGateSourceReport",
    "SourceLicenseAudit",
    "V2DataIntakeManifest",
    "V2DownloadRequest",
    "V2StagingSummary",
    "audit_v2_training_eligibility",
    "build_record_id",
    "build_record_index",
    "build_splits",
    "canonical_identity_from_record",
    "convert_staged_manifest",
    "convert_staged_source",
    "finalize_record_manifests",
    "normalize_identity_json",
    "normalize_linkages",
    "normalize_with_identity_resolution",
    "resolve_identities",
    "serialize_v2_data_intake_manifest",
    "serialize_v2_staging_summary",
    "stage_source_manifest",
    "license_gate_report_to_dict",
    "load_source_license_audit",
    "source_license_audit_from_dict",
    "v2_data_intake_manifest_from_dict",
    "v2_staging_summary_to_dict",
    "validate_v2_data_intake_manifest",
    "write_quality_report",
]
