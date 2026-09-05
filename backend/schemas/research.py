from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from tcm.schemas import UserContext


class ConditionId(str, Enum):
    C0 = "C0"
    C1 = "C1"
    C2 = "C2"
    C3 = "C3"
    C4 = "C4"
    C5 = "C5"
    C6 = "C6"


class RetrievalStrategy(str, Enum):
    R0 = "R0"
    R1 = "R1"
    R2 = "R2"
    R3 = "R3"


class ResearchMode(str, Enum):
    SINGLE_RAG = "tcm_single_rag"
    MULTI_AGENT = "tcm_multi_agent"
    COMPARE = "research_compare"


class RunState(str, Enum):
    SUPPORTED = "supported"
    INSUFFICIENT_INFORMATION = "insufficient_information"
    OUT_OF_SCOPE = "out_of_scope"
    SAFETY_CRITICAL = "safety_critical"
    EVIDENCE_INSUFFICIENT = "evidence_insufficient"


class StructuredClaim(BaseModel):
    claim_id: str
    text: str
    claim_type: str = "educational"
    evidence_ids: list[str] = Field(default_factory=list)
    reasoning_summary: str = ""
    confidence: float = Field(default=0.0, ge=0, le=1)


class ResearchCitation(BaseModel):
    evidence_id: str
    source_id: str
    title: str
    locator: str = ""
    provenance_valid: bool = False


class RetrievalItem(BaseModel):
    chunk_id: str
    source_id: str
    rank: int = Field(ge=1)
    lexical_score: float | None = None
    semantic_score: float | None = None
    fusion_score: float | None = None
    rerank_score: float | None = None
    retrieval_method: str
    chunk_text: str
    topics: list[str] = Field(default_factory=list)
    source_metadata: dict[str, Any] = Field(default_factory=dict)


class PlannerOutput(BaseModel):
    normalized_question: str
    language: Literal["en", "zh", "ko"]
    intent: str
    subdomains: list[str] = Field(default_factory=list)
    required_agents: list[str] = Field(default_factory=list)
    missing_context: list[str] = Field(default_factory=list)
    retrieval_filters: dict[str, list[str]] = Field(default_factory=dict)
    safety_critical: bool = False
    scope_state: RunState = RunState.SUPPORTED
    reasoning_summary: str = ""


class ResearchAgentOutput(BaseModel):
    agent_id: str
    agent_name: str
    agent_version: str
    question: str
    language: Literal["en", "zh", "ko"]
    subdomain: str
    claims: list[StructuredClaim] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    citations: list[ResearchCitation] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    safety_flags: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0, le=1)
    confidence_basis: str = "retrieval evidence support: mean(min(0.62, 0.30 + signal * 0.40)); signal is first nonzero rerank, semantic, then lexical score; zero when no scoped evidence matches"
    abstained: bool = False
    abstention_reason: str | None = None
    latency_ms: int = Field(default=0, ge=0)
    provider: str = "mock"
    model: str = "deterministic-mock-v1"
    generation_mode: str = "deterministic"
    prompt_version: str = "v1"
    reasoning_summary: str = ""
    token_usage: dict[str, int] = Field(default_factory=dict)


class JudgeResult(BaseModel):
    judge_id: str
    judge_name: str
    judge_version: str = "1.0.0"
    score: float = Field(default=0.0, ge=0, le=1)
    passed: bool = False
    findings: list[str] = Field(default_factory=list)
    affected_claim_ids: list[str] = Field(default_factory=list)
    unsupported_claim_ids: list[str] = Field(default_factory=list)
    reasoning_summary: str = ""
    provider: str = "local"
    model: str = "deterministic-evaluator-v1"
    latency_ms: int = Field(default=0, ge=0)


class EvidenceSupportSummary(BaseModel):
    judge_version: str = "safejudge-evidence-adapter-v0.1"
    eligible_claim_count: int = Field(default=0, ge=0)
    supported_claim_ids: list[str] = Field(default_factory=list)
    partially_supported_claim_ids: list[str] = Field(default_factory=list)
    unsupported_claim_ids: list[str] = Field(default_factory=list)
    missing_citation_ids: list[str] = Field(default_factory=list)
    evidence_coverage: float = Field(default=0.0, ge=0, le=1)
    citation_coverage: float = Field(default=0.0, ge=0, le=1)
    retrieval_sufficiency: float = Field(default=0.0, ge=0, le=1)
    verified_evidence_ratio: float = Field(default=0.0, ge=0, le=1)
    interpretation: str = "Evidence support derived from structured claims, supplied evidence, citations, and retrieval metadata."


class SourceGroundedSafetyFinding(BaseModel):
    code: Literal[
        "unsupported_treatment_certainty",
        "absolute_medical_claim",
        "unsupported_dosage_or_use",
        "source_caution_not_preserved",
        "conflict_overresolution",
        "unsupported_diagnostic_certainty",
    ]
    severity: Literal["low", "medium", "high"]
    claim_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    explanation: str
    rule_id: Literal["SJ-01", "SJ-02", "SJ-03", "SJ-04", "SJ-05", "SJ-06"]


class EvidenceSupportedCautionAssessment(BaseModel):
    judge_version: str = "safejudge-deterministic-v0.1"
    assessment: Literal["no_flags_detected", "flags_detected", "insufficient_input"] = "insufficient_input"
    source_grounded_safety_score: float = Field(default=0.0, ge=0, le=1)
    findings: list[SourceGroundedSafetyFinding] = Field(default_factory=list)
    deterministic: bool = True
    interpretation: str = "Source-grounded safety flags and an evidence-supported caution assessment only."


class ConflictStatus(BaseModel):
    has_unresolved_conflict: bool = False
    conflict_score: float = Field(default=0.0, ge=0, le=1)
    agreements: list[str] = Field(default_factory=list)
    disagreements: list[str] = Field(default_factory=list)
    unresolved_conflicts: list[str] = Field(default_factory=list)


class ConfidenceSignalContribution(BaseModel):
    signal: str
    observed_value: float = Field(ge=0, le=1)
    weight: float = Field(ge=0, le=1)
    contribution: float = Field(ge=0, le=1)


class ConfidenceSignalPenalty(BaseModel):
    signal: str
    observed_value: float = Field(ge=0, le=1)
    maximum_penalty: float = Field(ge=0, le=1)
    applied_penalty: float = Field(ge=0, le=1)


class EvidenceConfidenceSummary(BaseModel):
    judge_version: str = "confidence-deterministic-v0.1"
    score: float = Field(default=0.0, ge=0, le=1)
    band: Literal["insufficient", "limited", "moderate", "strong"] = "insufficient"
    signal_contributions: list[ConfidenceSignalContribution] = Field(default_factory=list)
    penalties: list[ConfidenceSignalPenalty] = Field(default_factory=list)
    caps_applied: list[str] = Field(default_factory=list)
    missing_or_weak_signals: list[str] = Field(default_factory=list)
    deterministic: bool = True
    interpretation: str = "Evidence confidence expressed as a response reliability indicator derived from observable evidence signals."


class DebateTrace(BaseModel):
    enabled: bool = False
    rounds: int = 0
    architecture: str = "none"
    selected_agents: list[str] = Field(default_factory=list)
    critic_invoked: bool = False
    initial_outputs: list[dict[str, Any]] = Field(default_factory=list)
    critiques: list[dict[str, Any]] = Field(default_factory=list)
    revisions: list[dict[str, Any]] = Field(default_factory=list)
    final_consensus: dict[str, Any] = Field(default_factory=dict)
    stage_statuses: list[dict[str, Any]] = Field(default_factory=list)
    provider_attempts: list[dict[str, Any]] = Field(default_factory=list)
    agreements: list[str] = Field(default_factory=list)
    disagreements: list[str] = Field(default_factory=list)
    unresolved_conflicts: list[str] = Field(default_factory=list)


class StageTiming(BaseModel):
    stage: str
    latency_ms: int = Field(ge=0)


class ProviderAttempt(BaseModel):
    stage: str | None = None
    attempt: int = Field(ge=1)
    provider: str = "unknown"
    model: str = "unknown"
    elapsed_ms: int = Field(default=0, ge=0)
    success: bool = False
    http_status: int | None = Field(default=None, ge=100, le=599)
    error_type: Literal["timeout", "rate_limit", "http_4xx", "http_5xx", "connectivity", "output_quality_rejection", "malformed_response", "unknown"] | None = None
    error: str | None = None
    retry_performed: bool = False


class RunTrace(BaseModel):
    run_id: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    git_commit: str = "unknown"
    corpus_version: str = "unknown"
    corpus_name: str = "unknown"
    corpus_chunk_count: int = 0
    corpus_source_count: int = 0
    corpus_mode: str = "legacy"
    dataset_version: str = "ad-hoc"
    condition_id: ConditionId
    experiment_config: dict[str, Any] = Field(default_factory=dict)
    provider: str = "mock"
    model: str = "deterministic-mock-v1"
    provider_configured: str = "mock"
    llm_execution_enabled: bool = False
    generation_mode: str = "deterministic"
    termination_stage: str = "completed"
    system_abstention_reason: str | None = None
    support_score_formula: str = "mean selected-agent evidence-support scores including abstentions as zero; cap at 0.65 and at the minimum deterministic judge score when judges run"
    successful_provider_calls: int = 0
    failed_provider_calls: int = 0
    participating_agents: list[str] = Field(default_factory=list)
    abstaining_agents: list[str] = Field(default_factory=list)
    debate_enabled: bool = False
    judges_enabled: bool = False
    retrieved_source_names: list[str] = Field(default_factory=list)
    embedding_provider: str = "none"
    embedding_model: str = "local-hash-embedding-v1"
    reranker_provider: str = "none"
    reranker: str = "none"
    prompt_versions: dict[str, str] = Field(default_factory=dict)
    prompt_hashes: dict[str, str] = Field(default_factory=dict)
    temperature: float = 0.0
    top_k: int = 4
    random_seed: int = 20260815
    active_agents: list[str] = Field(default_factory=list)
    active_judges: list[str] = Field(default_factory=list)
    retrieval_strategy: RetrievalStrategy = RetrievalStrategy.R2
    retrieved_evidence_ids: list[str] = Field(default_factory=list)
    agent_outputs: list[dict[str, Any]] = Field(default_factory=list)
    judge_outputs: list[dict[str, Any]] = Field(default_factory=list)
    final_answer: str = ""
    confidence: float = Field(default=0.0, ge=0, le=1)
    abstention: bool = False
    latency_ms: int = Field(default=0, ge=0)
    stage_timings: list[StageTiming] = Field(default_factory=list)
    token_usage: dict[str, int] = Field(default_factory=dict)
    provider_calls: int = 0
    provider_errors: list[str] = Field(default_factory=list)
    provider_attempts: list[ProviderAttempt] = Field(default_factory=list)
    fallback_usage: bool = False
    iterative_retrieval_used: bool = False
    raw_query_stored: bool = False


class ResearchRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    context: UserContext = Field(default_factory=UserContext)
    condition_id: ConditionId = ConditionId.C6
    retrieval_strategy: RetrievalStrategy = RetrievalStrategy.R2
    active_agents: list[str] = Field(default_factory=list)
    active_judges: list[str] = Field(default_factory=list)
    top_k: int = Field(default=4, ge=1, le=20)
    debate_rounds: int = Field(default=1, ge=0, le=3)
    iterative_retrieval: bool = False
    include_trace: bool = True
    store_raw_query: bool = False
    random_seed: int = 20260815

    @field_validator("question")
    @classmethod
    def clean_question(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 3:
            raise ValueError("Please enter a health question of at least 3 characters.")
        return value


class ResearchRunResult(BaseModel):
    run_id: str
    mode: ResearchMode
    condition_id: ConditionId
    condition_name: str
    scope_state: RunState
    planner: PlannerOutput
    retrieval: list[RetrievalItem] = Field(default_factory=list)
    agent_outputs: list[ResearchAgentOutput] = Field(default_factory=list)
    debate: DebateTrace = Field(default_factory=DebateTrace)
    judge_outputs: list[JudgeResult] = Field(default_factory=list)
    evidence_support: EvidenceSupportSummary | None = None
    conflict_status: ConflictStatus | None = None
    safety_assessment: EvidenceSupportedCautionAssessment | None = None
    evidence_confidence: EvidenceConfidenceSummary | None = None
    final_answer: str
    citations: list[ResearchCitation] = Field(default_factory=list)
    agreements: list[str] = Field(default_factory=list)
    disagreements: list[str] = Field(default_factory=list)
    unresolved_conflicts: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    safety_flags: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0, le=1)
    abstained: bool = False
    abstention_reason: str | None = None
    trace: RunTrace | None = None
    metrics: dict[str, float | int | None] = Field(default_factory=dict)
    experimental: bool = True
    mock_mode: bool = True
    generation_mode: str = "deterministic"


class CompareRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    context: UserContext = Field(default_factory=UserContext)
    conditions: list[ConditionId] = Field(default_factory=lambda: [ConditionId.C1, ConditionId.C2, ConditionId.C6])
    retrieval_strategy: RetrievalStrategy = RetrievalStrategy.R2
    active_agents: list[str] = Field(default_factory=list)
    active_judges: list[str] = Field(default_factory=list)
    top_k: int = Field(default=4, ge=1, le=20)
    iterative_retrieval: bool = False
    random_seed: int = 20260815


class CompareResponse(BaseModel):
    comparison_id: str
    question: str
    results: list[ResearchRunResult]
    metric_comparison: dict[str, dict[str, float | int | None]]
    limitations: list[str]


class DatasetItem(BaseModel):
    question_id: str
    question: str
    language: Literal["en", "zh", "ko"]
    category: str
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    tcm_subdomains: list[str] = Field(default_factory=list)
    expected_scope: RunState = RunState.SUPPORTED
    safety_label: str = "routine"
    gold_evidence_ids: list[str] = Field(default_factory=list)
    required_concepts: list[str] = Field(default_factory=list)
    forbidden_claims: list[str] = Field(default_factory=list)
    reference_notes: str = ""
    expert_review_status: str = "synthetic_provisional_not_expert_validated"


class HumanReview(BaseModel):
    run_id: str
    question_id: str
    reviewer_id_anonymous: str
    reviewer_role: str
    evidence_support_score: int = Field(ge=1, le=5)
    completeness_score: int = Field(ge=1, le=5)
    explainability_score: int = Field(ge=1, le=5)
    safety_score: int = Field(ge=1, le=5)
    uncertainty_communication_score: int = Field(ge=1, le=5)
    trustworthiness_score: int = Field(ge=1, le=5)
    system_preference: str = ""
    notes: str = ""
