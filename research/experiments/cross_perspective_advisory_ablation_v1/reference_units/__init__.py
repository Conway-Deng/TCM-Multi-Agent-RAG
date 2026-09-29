"""Research Reference-Unit Infrastructure.

Protocol ID: CPAA1-REFERENCE-UNIT-PROTOCOL-V1
Study: cross-perspective-advisory-ablation-v1
"""

from .reference_unit_schema import (
    ALLOWED_ANCHOR_PERSPECTIVES,
    ALLOWED_ANCHOR_ROLES,
    ALLOWED_PERSPECTIVE_SCOPES,
    ALLOWED_REVIEW_STATUSES,
    ALLOWED_SUPPORT_SCOPES,
    ALLOWED_UNIT_TYPES,
    FINAL_REFERENCE_UNIT_ID_PATTERN,
    FROZEN_PROTOCOL_BYTE_SHA256,
    PROTOCOL_ID,
    SCHEMA_VERSION,
    STUDY_ID,
    AnchorPerspective,
    AnchorRole,
    EvidenceAnchor,
    EvidenceSpan,
    PerspectiveScope,
    ReferenceUnitRecord,
    ReviewStatus,
    SupportScope,
    UnitType,
    format_final_reference_unit_id,
    parse_final_reference_unit_id,
)
from .reference_unit_validation import (
    EvidenceItemMetadata,
    FrozenPacketAnchorIndex,
    PacketMetadata,
    validate_evidence_anchor,
    validate_reference_unit_record,
)

__all__ = [
    "ALLOWED_ANCHOR_PERSPECTIVES",
    "ALLOWED_ANCHOR_ROLES",
    "ALLOWED_PERSPECTIVE_SCOPES",
    "ALLOWED_REVIEW_STATUSES",
    "ALLOWED_SUPPORT_SCOPES",
    "ALLOWED_UNIT_TYPES",
    "AnchorPerspective",
    "AnchorRole",
    "EvidenceAnchor",
    "EvidenceItemMetadata",
    "EvidenceSpan",
    "FINAL_REFERENCE_UNIT_ID_PATTERN",
    "FROZEN_PROTOCOL_BYTE_SHA256",
    "FrozenPacketAnchorIndex",
    "PacketMetadata",
    "PerspectiveScope",
    "PROTOCOL_ID",
    "ReferenceUnitRecord",
    "ReviewStatus",
    "SCHEMA_VERSION",
    "STUDY_ID",
    "SupportScope",
    "UnitType",
    "format_final_reference_unit_id",
    "parse_final_reference_unit_id",
    "validate_evidence_anchor",
    "validate_reference_unit_record",
]
