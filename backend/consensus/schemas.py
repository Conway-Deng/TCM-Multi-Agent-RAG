from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from tcm.schemas import UserContext


class Domain(str, Enum):
    TCM = "tcm"
    WESTERN = "western"
    NUTRITION = "nutrition"
    LIFESTYLE = "lifestyle"


class SourceType(str, Enum):
    LIVE_API = "live_api"
    LOCAL_RAG = "local_rag"
    FIXTURE = "fixture"
    PROVIDED = "provided"


class ConsensusStrategy(str, Enum):
    CONCATENATE = "concatenate"
    WEIGHTED = "weighted"
    DEBATE = "debate"
    DEBATE_JUDGE = "debate_judge"


DomainInput = Literal["tcm", "western_fixture", "western_api"]


class AgentClaim(BaseModel):
    claim_id: str
    text: str
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0, le=1)
    claim_type: str = "informational"


class AgentEvidence(BaseModel):
    evidence_id: str
    title: str
    source: str
    snippet: str
    relevance_score: float = Field(default=0.0, ge=0, le=1)
    source_type: str = ""
    verification_status: str = "needs_review"


class AgentOutput(BaseModel):
    agent_id: str
    domain: Domain
    source_type: SourceType
    experimental: bool = True
    summary: str
    claims: list[AgentClaim] = Field(default_factory=list)
    evidence: list[AgentEvidence] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0, le=1)
    limitations: list[str] = Field(default_factory=list)
    safety_flags: list[str] = Field(default_factory=list)
    urgent: bool = False
    abstained: bool = False
    scope_status: str = "supported"
    generation_source: str = ""
    model: str = ""
    latency_ms: int = Field(default=0, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def fixture_is_unambiguous(self) -> "AgentOutput":
        if self.source_type == SourceType.FIXTURE:
            self.experimental = True
            if not any("fixture" in item.casefold() for item in self.limitations):
                raise ValueError("fixture output must include an explicit fixture limitation")
        return self


class ConsensusConsultRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    context: UserContext = Field(default_factory=UserContext)
    strategy: ConsensusStrategy = ConsensusStrategy.DEBATE_JUDGE
    domains: list[DomainInput] = Field(default_factory=lambda: ["tcm"])
    include_trace: bool = False

    @field_validator("question")
    @classmethod
    def question_must_contain_text(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 3:
            raise ValueError("Please enter a health question of at least 3 characters.")
        return value

    @field_validator("domains")
    @classmethod
    def domains_are_unique_and_nonempty(cls, value: list[DomainInput]) -> list[DomainInput]:
        if not value:
            raise ValueError("At least one domain is required.")
        return list(dict.fromkeys(value))


class DebateResult(BaseModel):
    agreements: list[str] = Field(default_factory=list)
    disagreements: list[str] = Field(default_factory=list)
    complementary_points: list[str] = Field(default_factory=list)
    unsupported_assertions: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    unresolved_conflicts: list[str] = Field(default_factory=list)
    recommendations_not_to_merge: list[str] = Field(default_factory=list)
    confidence_reductions: list[str] = Field(default_factory=list)
    reasoning_summary: str = ""
    generation_source: str = "deterministic_fallback"


class EvidenceJudgeResult(BaseModel):
    supported_claim_ids: list[str] = Field(default_factory=list)
    partially_supported_claim_ids: list[str] = Field(default_factory=list)
    unsupported_claim_ids: list[str] = Field(default_factory=list)
    citation_issues: list[str] = Field(default_factory=list)
    evidence_coverage_score: float = Field(default=0.0, ge=0, le=1)
    reasoning_summary: str = ""


class SafetyJudgeResult(BaseModel):
    urgent: bool = False
    safety_flags: list[str] = Field(default_factory=list)
    unsafe_claim_ids: list[str] = Field(default_factory=list)
    missing_safety_warnings: list[str] = Field(default_factory=list)
    over_reassurance_detected: bool = False
    safety_score: float = Field(default=0.0, ge=0, le=1)
    reasoning_summary: str = ""


class ConflictItem(BaseModel):
    claim_ids: list[str] = Field(default_factory=list)
    type: Literal["direct", "conditional", "evidence_strength", "paradigm_difference"]
    description: str
    resolvable: bool = False


class ConflictJudgeResult(BaseModel):
    conflicts: list[ConflictItem] = Field(default_factory=list)
    agreements: list[str] = Field(default_factory=list)
    complementary_points: list[str] = Field(default_factory=list)
    conflict_score: float = Field(default=0.0, ge=0, le=1)


class ConfidenceJudgeResult(BaseModel):
    score: float = Field(default=0.0, ge=0, le=1)
    level: Literal["low", "medium", "high"] = "low"
    reason: str
    penalties: list[str] = Field(default_factory=list)


class JudgeResults(BaseModel):
    evidence: EvidenceJudgeResult | None = None
    safety: SafetyJudgeResult | None = None
    conflict: ConflictJudgeResult | None = None
    confidence: ConfidenceJudgeResult | None = None


class ConfidenceSummary(BaseModel):
    score: float = Field(default=0.0, ge=0, le=1)
    level: Literal["low", "medium", "high"] = "low"
    reason: str


class IntegratedResponse(BaseModel):
    summary: str
    agreements: list[str] = Field(default_factory=list)
    disagreements: list[str] = Field(default_factory=list)
    safety_notes: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)
    confidence: ConfidenceSummary


class AgentWeight(BaseModel):
    agent_id: str
    weight: float = Field(ge=0, le=1)
    rationale: list[str] = Field(default_factory=list)


class ModelTraceEntry(BaseModel):
    role: str
    model: str
    status: Literal["success", "fallback", "skipped"]
    latency_ms: int = Field(default=0, ge=0)
    evidence_ids_received: list[str] = Field(default_factory=list)
    error: str | None = None


class ConsensusResponse(BaseModel):
    strategy: ConsensusStrategy
    question: str
    agents: list[AgentOutput]
    debate: DebateResult | None = None
    judges: JudgeResults = Field(default_factory=JudgeResults)
    integrated_response: IntegratedResponse
    agent_weights: list[AgentWeight] = Field(default_factory=list)
    selected_claim_ids: list[str] = Field(default_factory=list)
    excluded_claim_ids: list[str] = Field(default_factory=list)
    fixture_used: bool = False
    experimental: bool = True
    latency_ms: int = Field(default=0, ge=0)
    api_call_count: int = Field(default=0, ge=0)
    model_call_failure_count: int = Field(default=0, ge=0)
    model_trace: list[ModelTraceEntry] = Field(default_factory=list)


class ConsensusErrorDetail(BaseModel):
    code: str
    message: str


class ConsensusError(BaseModel):
    detail: ConsensusErrorDetail
