from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from typing import Any, Final, Literal, Sequence
from pydantic import BaseModel, ConfigDict, Field

_REPO_ROOT = Path(__file__).resolve().parents[3]
_BACKEND_DIR = _REPO_ROOT / "backend"
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from .manifest import canonical_json_dumps, sha256_canonical_obj, sha256_text
from .schemas import (
    RawRetrievalItem,
    RawRetrievalRecord,
    RetrievalRunManifest,
    StrictResearchModel,
)


STUDY_ID: Final[str] = "cross-perspective-advisory-ablation-v1"
ALGORITHM_ID: Final[str] = "CPAA1-R0-LEXICAL-V1"
RETRIEVAL_STRATEGY: Final[str] = "R0"
REQUESTED_TOP_K: Final[int] = 4

QUESTION_MANIFEST_RELPATH: Final[str] = (
    "research/experiments/cross_perspective_advisory_ablation_v1/question_manifest.jsonl"
)
EXPECTED_QUESTION_MANIFEST_SHA256: Final[str] = (
    "a7daead783134ef6c2d4e5632153c19a8aa4a826a3c172838de90172796f9bbf"
)
EXPECTED_QUESTION_COUNT: Final[int] = 48

TCM_CORPUS_RELPATH: Final[str] = "research/corpus/tcm_v1/chunks.jsonl"
EXPECTED_TCM_CORPUS_SHA256: Final[str] = (
    "316eade86599c4d59a640020b59a3e153719c962fe20e4953ce36f8ddf8988c9"
)
TCM_CORPUS_ID: Final[str] = "tcm_v1"
TCM_CORPUS_VERSION: Final[str] = "tcm-research-corpus-v1"

WESTERN_CORPUS_RELPATH: Final[str] = "research/corpus/west_v0_1/chunks.jsonl"
EXPECTED_WESTERN_CORPUS_SHA256: Final[str] = (
    "8c53511e6193ebccea70c59f121fd456b5749b1e40a16eaeda3a4e53515a752b"
)
WESTERN_CORPUS_ID: Final[str] = "west_v0_1"
WESTERN_CORPUS_VERSION: Final[str] = "medirag-west-v0.1-pilot"
WESTERN_SOURCE_REGISTRY_RELPATH: Final[str] = "research/corpus/west_v0_1/source_registry.json"

ALLOW_QUERY_REWRITING: Final[bool] = False
ALLOW_TOPIC_FILTERING: Final[bool] = False
ALLOW_ROUTED_FILTER: Final[bool] = False
ALLOW_ANCHOR_SEARCH: Final[bool] = False
ALLOW_REFLECTION: Final[bool] = False
SCORE_THRESHOLD: Final[None] = None
ALLOW_SOURCE_DIVERSIFICATION: Final[bool] = False
ALLOW_POST_RANKING_DEDUPLICATION: Final[bool] = False
ALLOW_FALLBACK_CORPUS: Final[bool] = False

TCM_SEARCHABLE_REPRESENTATION_RULE: Final[str] = (
    "chunk.text + ' ' + ' '.join(ordered_unique_keywords_from_entity_name_aliases)"
)
WESTERN_SEARCHABLE_REPRESENTATION_RULE: Final[str] = (
    "validated_chunk.text.strip() + ' ' + ' '.join(stored_keywords)"
)

TOKEN_REGEX_PATTERN: Final[str] = r"[a-z][a-z-]{1,}|[\u3400-\u9fff]|[\uac00-\ud7af]"
CASEFOLD: Final[bool] = True
BM25_K1: Final[float] = 1.5
BM25_B: Final[float] = 0.75
SCORE_ROUNDING_DIGITS: Final[int] = 6
TIE_BREAKER: Final[str] = "corpus_ordinal_ascending"
RETAIN_ZERO_SCORES: Final[bool] = True
CORPUS_ORDINAL_RULE: Final[str] = "source_file_nonblank_record_order"


def tcm_searchable_representation(text: str, entity_name: str, aliases: Sequence[str]) -> str:
    """TCM searchable text: chunk.text + " " + ordered unique keywords from entity_name, aliases."""
    keywords = list(dict.fromkeys([entity_name, *aliases]))
    return f"{text} {' '.join(keywords)}".strip()


def western_searchable_representation(text: str, keywords: Sequence[str]) -> str:
    """Western searchable text: validated chunk.text + " " + stored keywords in stored order."""
    return f"{text.strip()} {' '.join(keywords)}".strip()


def compute_chunk_text_sha256(text: str) -> str:
    """Compute SHA256 hash of UTF-8 encoded chunk text."""
    return sha256_text(text)


def compute_record_canonical_sha256(data: dict[str, Any]) -> str:
    """Compute SHA256 of canonical JSON representation excluding record_canonical_sha256."""
    cleaned = {k: v for k, v in data.items() if k != "record_canonical_sha256"}
    return sha256_canonical_obj(cleaned)


class RetrievalContract(StrictResearchModel):
    """Immutable contract specification for Phase 1 advisory-ablation retrieval."""

    study_id: str = STUDY_ID
    algorithm_id: str = ALGORITHM_ID
    retrieval_strategy: str = RETRIEVAL_STRATEGY
    requested_top_k: int = REQUESTED_TOP_K
    question_manifest_relpath: str = QUESTION_MANIFEST_RELPATH
    expected_question_manifest_sha256: str = EXPECTED_QUESTION_MANIFEST_SHA256
    expected_question_count: int = EXPECTED_QUESTION_COUNT
    tcm_corpus_relpath: str = TCM_CORPUS_RELPATH
    expected_tcm_corpus_sha256: str = EXPECTED_TCM_CORPUS_SHA256
    tcm_corpus_id: str = TCM_CORPUS_ID
    tcm_corpus_version: str = TCM_CORPUS_VERSION
    western_corpus_relpath: str = WESTERN_CORPUS_RELPATH
    expected_western_corpus_sha256: str = EXPECTED_WESTERN_CORPUS_SHA256
    western_corpus_id: str = WESTERN_CORPUS_ID
    western_corpus_version: str = WESTERN_CORPUS_VERSION
    western_source_registry_relpath: str = WESTERN_SOURCE_REGISTRY_RELPATH
    allow_query_rewriting: bool = ALLOW_QUERY_REWRITING
    allow_topic_filtering: bool = ALLOW_TOPIC_FILTERING
    allow_routed_filter: bool = ALLOW_ROUTED_FILTER
    allow_anchor_search: bool = ALLOW_ANCHOR_SEARCH
    allow_reflection: bool = ALLOW_REFLECTION
    score_threshold: str | None = None
    allow_source_diversification: bool = ALLOW_SOURCE_DIVERSIFICATION
    allow_post_ranking_deduplication: bool = ALLOW_POST_RANKING_DEDUPLICATION
    allow_fallback_corpus: bool = ALLOW_FALLBACK_CORPUS
    tcm_searchable_representation_rule: str = TCM_SEARCHABLE_REPRESENTATION_RULE
    western_searchable_representation_rule: str = WESTERN_SEARCHABLE_REPRESENTATION_RULE
    token_regex_pattern: str = TOKEN_REGEX_PATTERN
    casefold: bool = CASEFOLD
    bm25_k1: float = BM25_K1
    bm25_b: float = BM25_B
    score_rounding_digits: int = SCORE_ROUNDING_DIGITS
    tie_breaker: str = TIE_BREAKER
    retain_zero_scores: bool = RETAIN_ZERO_SCORES
    corpus_ordinal_rule: str = CORPUS_ORDINAL_RULE

    def as_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


LOCKED_RETRIEVAL_CONTRACT: Final[RetrievalContract] = RetrievalContract()
