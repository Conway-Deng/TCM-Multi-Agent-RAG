from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


LicenseStatus = Literal["approved", "restricted", "uncertain", "rejected"]
ReviewStatus = Literal["source_claimed_review", "unreviewed", "needs_human_review"]


class CanonicalSourceRecord(BaseModel):
    source_id: str
    source_name: str
    official_url: str
    repository_url: str | None = None
    institution_or_authors: str
    publication_citation: str
    access_method: str
    available_files: list[str] = Field(default_factory=list)
    license_status: LicenseStatus
    license_or_terms: str
    redistribution_permitted: bool | None = None
    academic_use_permitted: bool | None = None
    attribution_required: bool | None = None
    expert_review_claimed: bool | None = None
    limitations: list[str] = Field(default_factory=list)
    proposed_use: str
    status: LicenseStatus


class NormalizedRecord(BaseModel):
    source_id: str
    source_name: str
    source_record_id: str
    source_version: str | None = None
    source_url: str
    source_title: str
    source_citation: str
    source_license_status: LicenseStatus
    source_access_date: str
    category: str
    subcategory: str | None = None
    entity_type: str
    entity_name: str
    aliases: list[str] = Field(default_factory=list)
    language: str
    source_text: str | None = None
    structured_facts: dict[str, Any] = Field(default_factory=dict)
    relation_type: str | None = None
    related_entities: list[dict[str, str]] = Field(default_factory=list)
    review_status: ReviewStatus = "needs_human_review"
    expert_review_claimed_by_source: bool | None = None
    transformation_history: list[str] = Field(default_factory=list)
    ingestion_timestamp: str
    corpus_version: str
    original_record: dict[str, Any] = Field(default_factory=dict)
    conflict_group_ids: list[str] = Field(default_factory=list)

class ResearchChunk(BaseModel):
    chunk_id: str
    source_id: str
    source_name: str
    source_record_id: str
    source_version: str | None = None
    source_url: str
    source_title: str
    source_citation: str
    source_license_status: LicenseStatus
    source_access_date: str
    category: str
    subcategory: str | None = None
    entity_type: str
    entity_name: str
    aliases: list[str] = Field(default_factory=list)
    language: str
    text: str
    structured_facts: dict[str, Any] = Field(default_factory=dict)
    relation_type: str | None = None
    related_entities: list[dict[str, str]] = Field(default_factory=list)
    review_status: ReviewStatus = "needs_human_review"
    expert_review_claimed_by_source: bool | None = None
    transformation_history: list[str] = Field(default_factory=list)
    ingestion_timestamp: str
    corpus_version: str
    conflict_group_ids: list[str] = Field(default_factory=list)
