from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from schemas.research import ProviderAttempt


class WesternTopic(str, Enum):
    COUGH = "cough"
    DYSPEPSIA = "dyspepsia_digestive_symptoms"
    HEADACHE = "headache"
    CONSTIPATION = "constipation"


class WesternConsultRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    top_k: int = Field(default=4, ge=1, le=8)

    @field_validator("question")
    @classmethod
    def clean_question(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 3:
            raise ValueError("Please enter an educational question of at least 3 characters.")
        return value


class WesternRetrievalEvidence(BaseModel):
    chunk_id: str
    source_id: str
    rank: int = Field(ge=1)
    lexical_score: float = Field(ge=0.0)
    article_title: str
    section: str
    pmcid: str
    doi: str = ""
    source_url: str
    license: str
    topic: WesternTopic
    text: str
    provenance: dict[str, Any] = Field(default_factory=dict)


class WesternClaim(BaseModel):
    claim_id: str
    text: str
    evidence_ids: list[str] = Field(default_factory=list)
    support_status: Literal["not_individually_verified"] = "not_individually_verified"
    reasoning_summary: str = "Answer generated from retrieved Western pilot evidence."


class WesternCitation(BaseModel):
    evidence_id: str
    source_id: str
    article_title: str
    section: str
    pmcid: str
    doi: str = ""
    source_url: str
    license: str
    provenance_valid: bool = True


class WesternTrace(BaseModel):
    corpus_name: str
    corpus_version: str
    corpus_chunk_count: int
    corpus_source_count: int
    retrieval_strategy: str = "R0"
    retrieved_evidence_ids: list[str] = Field(default_factory=list)
    provider_attempts: list[ProviderAttempt] = Field(default_factory=list)
    fallback_usage: bool = False
    reasoning_summary: str = "Answer generated from retrieved Western pilot evidence."
    token_usage: dict[str, int] = Field(default_factory=dict)


class WesternConsultResponse(BaseModel):
    question: str
    topic: WesternTopic | None = None
    answer: str = ""
    retrieval: list[WesternRetrievalEvidence] = Field(default_factory=list)
    claims: list[WesternClaim] = Field(default_factory=list)
    citations: list[WesternCitation] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    safety_flags: list[str] = Field(default_factory=list)
    evidence_support_signal: float = Field(default=0.0, ge=0.0, le=1.0)
    support_signal_definition: str = (
        "Phase 1B does not independently verify sentence-level claim support; "
        "citations expose retrieval provenance only."
    )
    support_status: Literal["not_individually_verified"] = "not_individually_verified"
    abstained: bool = False
    abstention_reason: str | None = None
    provider: str = "none"
    model: str = "none"
    generation_mode: str = "none"
    latency_ms: int = Field(default=0, ge=0)
    trace: WesternTrace | None = None
