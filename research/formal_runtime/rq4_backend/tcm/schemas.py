from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


ResponseLanguage = Literal["en", "zh", "ko"]
ScopeStatus = Literal[
    "supported",
    "insufficient_information",
    "out_of_scope",
    "safety_critical",
    "evidence_insufficient",
]
GenerationMode = Literal["mock", "llm", "safety", "rule", "abstention"]
GenerationSource = Literal[
    "siliconflow_llm",
    "mock_fallback",
    "safety_rule",
    "scope_rule",
    "evidence_gate",
]
RetrievalMethod = Literal["not_run", "lexical", "semantic", "hybrid", "hybrid_reranked"]


class UserContext(BaseModel):
    age: str = Field(default="", max_length=40)
    gender: str = Field(default="", max_length=80)
    duration: str = Field(default="", max_length=160)
    medications: str = Field(default="", max_length=500)
    pregnancy: str = Field(default="", max_length=80)
    allergies: str = Field(default="", max_length=500)


class TCMConsultRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    context: UserContext = Field(default_factory=UserContext)

    @field_validator("question")
    @classmethod
    def question_must_contain_text(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 3:
            raise ValueError("Please enter a health question of at least 3 characters.")
        return value


class QueryAnalysis(BaseModel):
    keywords: list[str] = Field(default_factory=list)
    possible_domains: list[str] = Field(default_factory=list)


class PatternDisplay(BaseModel):
    pattern: str
    rationale: str


class PossiblePattern(BaseModel):
    pattern: str
    rationale: str
    matching_symptoms: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    localized: dict[ResponseLanguage, PatternDisplay] = Field(default_factory=dict)


class FormulaDisplay(BaseModel):
    name: str
    purpose: str
    safety_warning: str


class RelatedHerbOrFormula(BaseModel):
    name: str
    type: Literal["herb", "formula"]
    purpose: str
    safety_warning: str
    evidence_ids: list[str] = Field(default_factory=list)
    localized: dict[ResponseLanguage, FormulaDisplay] = Field(default_factory=dict)


class EvidenceDisplay(BaseModel):
    title: str
    source_type: str
    snippet: str


class EvidenceChunk(BaseModel):
    evidence_id: str
    source: str
    source_ids: list[str] = Field(default_factory=list)
    title: str
    source_type: str
    snippet: str
    relevance_score: float = Field(ge=0, le=1)
    matched_terms: list[str] = Field(default_factory=list)
    evidence_category: str = "terminology_or_educational"
    review_status: str = "needs_human_review"
    localized: dict[ResponseLanguage, EvidenceDisplay] = Field(default_factory=dict)


class Citation(BaseModel):
    source_id: str
    title: str
    organization: str
    year: int | None = None
    url_or_identifier: str = ""
    section: str = ""
    source_type: str
    verification_status: Literal["verified", "needs_review"] = "needs_review"


class Claim(BaseModel):
    claim_id: str
    text: str
    evidence_ids: list[str] = Field(default_factory=list)
    claim_type: Literal[
        "pattern_hypothesis",
        "evidence_limitation",
        "safety_guidance",
        "abstention_reason",
    ]


class Confidence(BaseModel):
    level: Literal["low", "medium", "high"]
    score: float = Field(ge=0, le=1)
    reason: str


class RetrievalMetadata(BaseModel):
    retrieval_method: RetrievalMethod = "not_run"
    candidate_count: int = Field(default=0, ge=0)
    meaningful_match_count: int = Field(default=0, ge=0)
    top_relevance_score: float = Field(default=0, ge=0, le=1)
    min_relevance_score: float = Field(default=0, ge=0, le=1)
    retrieval_notes: list[str] = Field(default_factory=list)


class LocalizedResultPattern(BaseModel):
    name: str
    rationale: str
    matched_symptoms: list[str] = Field(default_factory=list)


class LocalizedResultFormula(BaseModel):
    name: str
    description: str
    warning: str


class LocalizedResultContent(BaseModel):
    status_label: str
    summary_title: str
    grounding: str
    summary: str
    state_title: str = ""
    state_body: str = ""
    patterns_title: str
    patterns: list[LocalizedResultPattern] = Field(default_factory=list)
    examples_title: str
    formulas: list[LocalizedResultFormula] = Field(default_factory=list)
    safety_title: str
    safety_notes: list[str] = Field(default_factory=list)
    evidence_summary: str
    evidence_title: str


class RequestTimings(BaseModel):
    preprocessing_ms: float = Field(default=0, ge=0)
    retrieval_ms: float = Field(default=0, ge=0)
    embedding_ms: float = Field(default=0, ge=0)
    reranking_ms: float = Field(default=0, ge=0)
    llm_ms: float = Field(default=0, ge=0)
    post_processing_ms: float = Field(default=0, ge=0)
    total_ms: float = Field(default=0, ge=0)


class TCMConsultResponse(BaseModel):
    mode: Literal["TCM-RAG"] = "TCM-RAG"
    agent: Literal["tcm"] = "tcm"
    scope_status: ScopeStatus
    abstained: bool
    generation_mode: GenerationMode
    generation_source: GenerationSource
    response_language: ResponseLanguage
    llm_model: str
    llm_error: str | None = None
    urgent: bool = False
    query_analysis: QueryAnalysis
    summary: str
    tcm_perspective: str
    claims: list[Claim] = Field(default_factory=list)
    patterns: list[PossiblePattern] = Field(default_factory=list)
    educational_examples: list[RelatedHerbOrFormula] = Field(default_factory=list)
    possible_patterns: list[PossiblePattern]
    related_herbs_or_formulas: list[RelatedHerbOrFormula]
    evidence: list[EvidenceChunk]
    citations: list[Citation] = Field(default_factory=list)
    safety_notes: list[str]
    localized_safety_notes: dict[ResponseLanguage, list[str]] = Field(default_factory=dict)
    localized_result: dict[ResponseLanguage, LocalizedResultContent] = Field(default_factory=dict)
    confidence: Confidence
    limitations: list[str] = Field(default_factory=list)
    retrieval_metadata: RetrievalMetadata = Field(default_factory=RetrievalMetadata)
    retrieval_method: RetrievalMethod = "not_run"
    candidate_count: int = 0
    meaningful_match_count: int = 0
    top_relevance_score: float = 0
    timings: RequestTimings = Field(default_factory=RequestTimings)
    disclaimer: str
