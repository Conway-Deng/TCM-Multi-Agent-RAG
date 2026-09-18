"""Additive Western-medicine corpus and Phase 1B RAG support."""

from .agent import WesternEvidenceAgent
from .corpus import (
    WesternCorpusError,
    load_chunks,
    load_runtime_corpus,
    load_sources,
    western_corpus_stats,
)
from .models import WesternKnowledgeChunk, WesternSourceRecord
from .routing import route_western_scope
from .schemas import WesternConsultRequest, WesternConsultResponse
from .validation import validate_corpus_files, validate_records

__all__ = [
    "WesternConsultRequest",
    "WesternConsultResponse",
    "WesternCorpusError",
    "WesternEvidenceAgent",
    "WesternKnowledgeChunk",
    "WesternSourceRecord",
    "load_chunks",
    "load_runtime_corpus",
    "load_sources",
    "route_western_scope",
    "validate_corpus_files",
    "validate_records",
    "western_corpus_stats",
]
