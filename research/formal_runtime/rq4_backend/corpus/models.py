from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


SourceType = Literal[
    "classical_tcm_text",
    "modern_tcm_textbook",
    "professional_standard",
    "guideline",
    "peer_reviewed_study",
    "systematic_review",
    "educational_reference",
    "researcher_added_source",
]


class SourceRecord(BaseModel):
    source_id: str
    title: str
    author_or_organization: str
    source_type: SourceType
    edition: str = ""
    publication_year: int | None = None
    language: str = "multilingual"
    url_or_reference: str = ""
    license_or_access_note: str = ""
    evidence_category: str = "traditional_educational"
    review_status: str = "needs_human_review"
    reviewer: str = ""
    date_added: str = "2026-08-15"
    notes: str = ""


class KnowledgeChunk(BaseModel):
    chunk_id: str
    source_id: str
    section: str
    text: str
    language: str = "multilingual"
    topics: list[str] = Field(default_factory=list)
    syndromes: list[str] = Field(default_factory=list)
    herbs: list[str] = Field(default_factory=list)
    meridians: list[str] = Field(default_factory=list)
    constitution_tags: list[str] = Field(default_factory=list)
    dietary_tags: list[str] = Field(default_factory=list)
    lifestyle_tags: list[str] = Field(default_factory=list)
    safety_tags: list[str] = Field(default_factory=list)
    human_review_status: str = "needs_human_review"
    source_ids: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
