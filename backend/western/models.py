from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


WesternSourceType = Literal[
    "peer_reviewed_article",
    "systematic_review",
    "review_article",
]


class WesternSourceRecord(BaseModel):
    source_id: str
    title: str
    source_type: WesternSourceType
    organization_or_journal: str
    publication_year: int | None = None
    source_url: str
    pmcid: str
    doi: str = ""
    license: str
    license_url: str = ""
    license_text: str = ""
    retrieved_at: str
    evidence_category: str = "peer_reviewed_literature"
    review_status: str = "not_human_clinically_validated"
    topics: list[str] = Field(default_factory=list)
    notes: str = ""

    @field_validator("source_id", "title", "organization_or_journal", "source_url", "pmcid", "license", "retrieved_at")
    @classmethod
    def require_nonempty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("field must not be empty")
        return value
    @field_validator("pmcid")
    @classmethod
    def normalize_pmcid(cls, value: str) -> str:
        value = value.upper()
        if not value.startswith("PMC") or not value[3:].isdigit():
            raise ValueError("pmcid must use the PMC123456 form")
        return value


class WesternKnowledgeChunk(BaseModel):
    chunk_id: str
    source_id: str
    domain: Literal["western"] = "western"
    section: str
    text: str
    language: str = "en"
    topics: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    evidence_category: str = "peer_reviewed_literature"
    human_review_status: str = "not_human_clinically_validated"
    pmcid: str
    doi: str = ""
    source_url: str

    @field_validator("chunk_id", "source_id", "section", "text", "pmcid", "source_url")
    @classmethod
    def require_nonempty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("field must not be empty")
        return value
