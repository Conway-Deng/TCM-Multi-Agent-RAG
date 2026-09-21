from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


PerspectiveName = Literal["tcm", "western", "nutrition"]
ActivePerspectiveName = Literal["tcm", "western"]
SupportStatus = Literal["supported", "partially_supported", "insufficient"]
ExecutionStatus = Literal["available", "degraded", "abstained", "unavailable", "not_selected"]
RouterMode = Literal["auto", "forced"]

NUTRITION_UNAVAILABLE_MESSAGE = (
    "Nutrition perspective unavailable until a dedicated provenance-preserving "
    "nutrition evidence corpus is constructed."
)
TCM_NO_CLAIM_SUMMARY = "No provenance-linked TCM claim is available for synthesis."
WESTERN_NO_CLAIM_SUMMARY = "No provenance-linked Western claim is available for synthesis."
TCM_UNAVAILABLE_SUMMARY = "TCM perspective unavailable for synthesis."
WESTERN_UNAVAILABLE_SUMMARY = "Western perspective unavailable for synthesis."
OVERALL_NO_CLAIM_SUMMARY = "No provenance-linked evidence is available for an overall cross-perspective summary."


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvidenceReference(StrictModel):
    source_id: str = Field(min_length=1)
    chunk_id: str = Field(min_length=1)
    title: str | None = None


class PerspectiveClaim(StrictModel):
    claim_id: str = Field(min_length=1)
    claim_text: str = Field(min_length=1)
    evidence_refs: list[EvidenceReference] = Field(default_factory=list)
    support_status: SupportStatus
    claim_kind: Literal["source_excerpt", "derived_claim"] = "derived_claim"


class ProvenanceRecord(StrictModel):
    source_id: str = Field(min_length=1)
    chunk_id: str = Field(min_length=1)
    title: str | None = None
    source_url: str = ""
    source_type: str = ""
    section: str = ""
    excerpt: str = ""
    identifier: str = ""
    license: str = ""


class PerspectiveFailure(StrictModel):
    role: ActivePerspectiveName
    failure_type: Literal["configuration", "provider", "http", "timeout", "semantic", "unexpected"]
    error_summary: str
    http_status: int | None = None
    retry_count: int = Field(default=0, ge=0, le=1)


class PerspectiveEvidencePacket(StrictModel):
    perspective: ActivePerspectiveName
    available: bool = True
    execution_status: ExecutionStatus = "available"
    interpretation: str
    claims: list[PerspectiveClaim] = Field(default_factory=list)
    uncertainty: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    provenance: list[ProvenanceRecord] = Field(default_factory=list)
    failure: PerspectiveFailure | None = None

    @model_validator(mode="after")
    def validate_packet_links(self) -> "PerspectiveEvidencePacket":
        provenance_pairs = {(item.source_id, item.chunk_id) for item in self.provenance}
        for claim in self.claims:
            for ref in claim.evidence_refs:
                if (ref.source_id, ref.chunk_id) not in provenance_pairs:
                    raise ValueError(
                        f"claim {claim.claim_id!r} references evidence absent from packet provenance"
                    )
            if claim.support_status == "supported" and not claim.evidence_refs:
                raise ValueError(f"supported claim {claim.claim_id!r} must include evidence references")
        if not self.available and self.execution_status not in {"unavailable", "not_selected"}:
            raise ValueError("an unavailable packet must be unavailable or not_selected")
        if self.failure is not None and self.failure.role != self.perspective:
            raise ValueError("packet failure role must match packet perspective")
        return self


class RoutingDecision(StrictModel):
    use_tcm: bool
    use_western: bool
    reason_summary: str = Field(min_length=1)
    requested_perspectives: list[ActivePerspectiveName]

    @model_validator(mode="after")
    def validate_selection(self) -> "RoutingDecision":
        expected = []
        if self.use_tcm:
            expected.append("tcm")
        if self.use_western:
            expected.append("western")
        if not expected:
            raise ValueError("router must select at least one available perspective")
        if set(expected) != set(self.requested_perspectives):
            raise ValueError("routing booleans and requested_perspectives disagree")
        return self


class PerspectiveSummary(StrictModel):
    available: bool
    summary: str
    supported_claim_ids: list[str] = Field(default_factory=list)


class PerspectiveSummaries(StrictModel):
    western: PerspectiveSummary
    tcm: PerspectiveSummary


class Agreement(StrictModel):
    statement: str = Field(min_length=1)
    supporting_claim_ids: list[str] = Field(min_length=1)


class DifferenceOrConflict(StrictModel):
    statement: str = Field(min_length=1)
    tcm_claim_ids: list[str] = Field(min_length=1)
    western_claim_ids: list[str] = Field(min_length=1)


class SourceMapEntry(StrictModel):
    final_claim_or_statement: str = Field(min_length=1)
    perspective: ActivePerspectiveName
    claim_ids: list[str] = Field(min_length=1)
    evidence_refs: list[EvidenceReference] = Field(min_length=1)


class CrossPerspectiveAnswer(StrictModel):
    overall_summary: str = Field(min_length=1)
    overall_supporting_claim_ids: list[str] = Field(default_factory=list)
    perspectives: PerspectiveSummaries
    agreements: list[Agreement] = Field(default_factory=list)
    differences_or_conflicts: list[DifferenceOrConflict] = Field(default_factory=list)
    evidence_gaps: list[str] = Field(default_factory=list)
    uncertainty: list[str] = Field(default_factory=list)
    source_map: list[SourceMapEntry] = Field(default_factory=list)


class ModelCallEvent(StrictModel):
    role: Literal["router", "tcm", "western", "governance"]
    attempt: int = Field(ge=1, le=2)
    provider: str
    requested_model: str
    reported_model: str | None = None
    success: bool
    latency_ms: float = Field(ge=0)
    http_status: int | None = None
    failure_class: Literal["provider", "http", "timeout", "semantic", "configuration", "unexpected"] | None = None
    error_summary: str | None = None
    retry_performed: bool = False
    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)


class CrossPerspectiveTrace(StrictModel):
    run_id: str
    timestamp: datetime
    question_id: str | None = None
    question_hash: str
    router_output: RoutingDecision | None = None
    selected_perspectives: list[ActivePerspectiveName] = Field(default_factory=list)
    retrieval_source_ids: dict[ActivePerspectiveName, list[str]] = Field(default_factory=dict)
    retrieval_chunk_ids: dict[ActivePerspectiveName, list[str]] = Field(default_factory=dict)
    perspective_packets: dict[ActivePerspectiveName, PerspectiveEvidencePacket] = Field(default_factory=dict)
    governance_input: dict[str, Any] = Field(default_factory=dict)
    governance_output: CrossPerspectiveAnswer | None = None
    model_ids: dict[str, str] = Field(default_factory=dict)
    model_calls: int = Field(default=0, ge=0)
    latency_by_stage_ms: dict[str, float] = Field(default_factory=dict)
    total_latency_ms: float = Field(default=0, ge=0)
    provider_events: list[ModelCallEvent] = Field(default_factory=list)
    retry_count: int = Field(default=0, ge=0)
    failed_roles: list[str] = Field(default_factory=list)


class CrossPerspectiveConsultRequest(StrictModel):
    question: str = Field(min_length=3, max_length=2000)
    perspectives: list[PerspectiveName] = Field(default_factory=lambda: ["tcm", "western"])
    router_mode: RouterMode = "forced"
    question_id: str | None = Field(default=None, max_length=200)

    @field_validator("question")
    @classmethod
    def clean_question(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 3:
            raise ValueError("Please enter a health question of at least 3 characters.")
        return value

    @field_validator("perspectives")
    @classmethod
    def unique_perspectives(cls, value: list[PerspectiveName]) -> list[PerspectiveName]:
        if len(set(value)) != len(value):
            raise ValueError("perspectives must not contain duplicates")
        return value

    @model_validator(mode="after")
    def validate_forced_mode(self) -> "CrossPerspectiveConsultRequest":
        if self.router_mode == "forced" and not self.perspectives:
            raise ValueError("forced router mode requires at least one perspective")
        return self


class CrossPerspectiveConsultResponse(StrictModel):
    development_label: Literal["DEVELOPMENT PROTOTYPE — NOT FORMAL EXPERIMENT"] = (
        "DEVELOPMENT PROTOTYPE — NOT FORMAL EXPERIMENT"
    )
    run_id: str
    status: Literal["completed", "partial_failure", "failed"]
    routing: RoutingDecision
    perspective_packets: dict[ActivePerspectiveName, PerspectiveEvidencePacket]
    answer: CrossPerspectiveAnswer | None = None
    failed_roles: list[str] = Field(default_factory=list)
    trace: CrossPerspectiveTrace
