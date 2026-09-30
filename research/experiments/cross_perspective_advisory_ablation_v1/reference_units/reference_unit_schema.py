"""Reference-Unit Record and Evidence-Anchor Schema.

Protocol Anchor: CPAA1-REFERENCE-UNIT-PROTOCOL-V1
Schema Version: cpaa1_reference_unit_v1
Study ID: cross-perspective-advisory-ablation-v1

This module implements the mechanical structural Pydantic models and field constants
for human reference units and their paired evidence anchors according to
REFERENCE_UNIT_PROTOCOL_V1.md Section G and Section H.

CRITICAL BOUNDARY NOTICE:
This module defines syntactic and structural schemas only. It does NOT perform
semantic validation, relevance evaluation, or clinical/grounding verification.
"""

from __future__ import annotations

import re
from typing import Final, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


SCHEMA_VERSION: Final[str] = "cpaa1_reference_unit_v1"
STUDY_ID: Final[str] = "cross-perspective-advisory-ablation-v1"
PROTOCOL_ID: Final[str] = "CPAA1-REFERENCE-UNIT-PROTOCOL-V1"
FROZEN_PROTOCOL_BYTE_SHA256: Final[str] = (
    "5ab2f681e605f3bc75ef6e91fa8d864a102aa60e6b14efdda132448845dcb46b"
)

# Deterministic final reference-unit ID regex per Section H:
# cpaa1:ru:<question_id>:<three-digit ordinal>
FINAL_REFERENCE_UNIT_ID_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^cpaa1:ru:(?P<qid>[a-zA-Z0-9_-]+):(?P<ordinal>\d{3})$"
)

# Field Literals / Enums
UnitType = Literal["content", "relationship", "limitation", "evidence_gap"]
PerspectiveScope = Literal["tcm", "western", "both"]
AnchorPerspective = Literal["tcm", "western"]
AnchorRole = Literal["supporting_span", "contrasting_span", "scope_audit"]
SupportScope = Literal["source_explicit", "cross_span_synthesis", "packet_bounded_absence"]
ReviewStatus = Literal["draft", "disputed", "reconciled"]
ValidationMode = Literal["draft", "final_candidate"]

ALLOWED_UNIT_TYPES: Final[set[str]] = {"content", "relationship", "limitation", "evidence_gap"}
ALLOWED_PERSPECTIVE_SCOPES: Final[set[str]] = {"tcm", "western", "both"}
ALLOWED_ANCHOR_PERSPECTIVES: Final[set[str]] = {"tcm", "western"}
ALLOWED_ANCHOR_ROLES: Final[set[str]] = {"supporting_span", "contrasting_span", "scope_audit"}
ALLOWED_SUPPORT_SCOPES: Final[set[str]] = {
    "source_explicit",
    "cross_span_synthesis",
    "packet_bounded_absence",
}
ALLOWED_REVIEW_STATUSES: Final[set[str]] = {"draft", "disputed", "reconciled"}
ALLOWED_VALIDATION_MODES: Final[set[str]] = {"draft", "final_candidate"}


class EvidenceSpan(BaseModel):
    """Zero-based, half-open Unicode code-point offset interval within exact_chunk_text.

    Coordinates are neither UTF-8 byte offsets nor UTF-16 code units.
    """
    model_config = ConfigDict(extra="forbid")

    start: int = Field(..., description="Zero-based, inclusive Unicode code-point offset")
    end: int = Field(..., description="Zero-based, exclusive Unicode code-point offset")

    @model_validator(mode="after")
    def validate_bounds(self) -> EvidenceSpan:
        if self.start < 0:
            raise ValueError(f"Span start offset must be non-negative, got {self.start}")
        if self.start >= self.end:
            raise ValueError(
                f"Span start offset must be strictly less than end offset, got start={self.start}, end={self.end}"
            )
        return self


class EvidenceAnchor(BaseModel):
    """Evidence anchor linking a reference unit to a frozen packet evidence item.

    Adheres strictly to REFERENCE_UNIT_PROTOCOL_V1.md Section G.
    """
    model_config = ConfigDict(extra="forbid")

    packet_id: str = Field(..., min_length=1, description="Exact frozen packet ID")
    packet_canonical_sha256: str = Field(
        ..., min_length=64, max_length=64, description="Frozen packet self-hash (64-character lowercase hex)"
    )
    perspective: AnchorPerspective = Field(..., description="Perspective of the anchored packet: tcm or western")
    evidence_id: str = Field(..., min_length=1, description="Exact evidence occurrence ID")
    chunk_text_sha256: str = Field(
        ..., min_length=64, max_length=64, description="SHA256 of the anchored frozen chunk text"
    )
    anchor_role: AnchorRole = Field(
        ..., description="Role of this anchor: supporting_span, contrasting_span, or scope_audit"
    )
    spans: list[EvidenceSpan] = Field(
        default_factory=list, description="Array of non-overlapping start/end offsets"
    )

    @field_validator("packet_canonical_sha256", "chunk_text_sha256")
    @classmethod
    def validate_hex_hash(cls, v: str) -> str:
        if not re.match(r"^[0-9a-f]{64}$", v):
            raise ValueError(f"Hash must be a 64-character lowercase hex string, got {v!r}")
        return v

    @model_validator(mode="after")
    def validate_role_and_spans(self) -> EvidenceAnchor:
        if self.anchor_role in ("supporting_span", "contrasting_span"):
            if not self.spans:
                raise ValueError(
                    f"Anchor role {self.anchor_role!r} must have at least one span coordinate (cannot be empty)"
                )
        elif self.anchor_role == "scope_audit":
            # Section G: scope_audit anchors MAY have an empty spans array
            pass
        return self


class ReferenceUnitRecord(BaseModel):
    """Human Reference-Unit record adhering to REFERENCE_UNIT_PROTOCOL_V1.md Section H.

    Contains semantic reference content and evidence anchors without model-generated
    fields or condition identifiers.
    """
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["cpaa1_reference_unit_v1"] = SCHEMA_VERSION
    study_id: Literal["cross-perspective-advisory-ablation-v1"] = STUDY_ID
    question_id: str = Field(..., min_length=1, description="Exact frozen question ID")
    reference_unit_id: str | None = Field(
        default=None,
        description="Deterministic final ID (cpaa1:ru:<question_id>:<ordinal>) or None for draft",
    )
    unit_text: str = Field(..., description="Human-authored substantive information target")
    unit_type: UnitType = Field(..., description="Classification: content, relationship, limitation, or evidence_gap")
    perspective_scope: PerspectiveScope = Field(..., description="Substantive scope: tcm, western, or both")
    evidence_anchors: list[EvidenceAnchor] = Field(default_factory=list, description="List of evidence anchors")
    support_scope: SupportScope = Field(
        ..., description="Basis: source_explicit, cross_span_synthesis, or packet_bounded_absence"
    )
    required_qualifiers: list[str] = Field(
        default_factory=list, description="Indispensable semantic qualifications (empty if none required)"
    )
    support_rationale: str = Field(..., description="Human justification for support, comparison, or absence")
    review_status: ReviewStatus = Field(
        default="draft", description="Review state: draft, disputed, or reconciled"
    )


def format_final_reference_unit_id(question_id: str, ordinal: int) -> str:
    """Format a deterministic final reference unit ID according to CPAA1-REFERENCE-UNIT-PROTOCOL-V1 Section H."""
    if not (1 <= ordinal <= 999):
        raise ValueError(f"Ordinal must be an integer between 1 and 999, got {ordinal}")
    return f"cpaa1:ru:{question_id}:{ordinal:03d}"


def parse_final_reference_unit_id(ref_id: str) -> tuple[str, int] | None:
    """Parse final reference unit ID into (question_id, ordinal) or return None if invalid format."""
    m = FINAL_REFERENCE_UNIT_ID_PATTERN.match(ref_id)
    if not m:
        return None
    return m.group("qid"), int(m.group("ordinal"))
