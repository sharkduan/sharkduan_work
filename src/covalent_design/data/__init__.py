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
    "build_record_id",
    "canonical_identity_from_record",
    "normalize_identity_json",
    "normalize_linkages",
    "normalize_with_identity_resolution",
    "resolve_identities",
]
