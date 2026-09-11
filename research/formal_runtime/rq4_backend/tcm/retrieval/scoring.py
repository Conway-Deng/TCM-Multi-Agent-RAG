from __future__ import annotations

from dataclasses import dataclass, field
import math
import re

from ..knowledge_base import KnowledgeEntry


@dataclass(frozen=True)
class RetrievalResult:
    entry: KnowledgeEntry
    score: float
    matched_terms: tuple[str, ...] = field(default_factory=tuple)
    score_breakdown: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class RetrievalDiagnostics:
    retrieval_method: str
    candidate_count: int
    meaningful_match_count: int
    top_relevance_score: float
    min_relevance_score: float
    notes: tuple[str, ...] = field(default_factory=tuple)
    lexical_ms: float = 0.0
    semantic_ms: float = 0.0
    reranking_ms: float = 0.0
    total_ms: float = 0.0


def normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text.casefold()).strip()


def english_tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z][a-z-]{2,}", text.casefold()))


def character_ngrams(text: str, *, n: int = 2) -> set[str]:
    chars = re.findall(r"[\u3400-\u9fff\uac00-\ud7af]", text)
    return {"".join(chars[index : index + n]) for index in range(max(0, len(chars) - n + 1))}


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return max(0.0, min(1.0, dot / (left_norm * right_norm)))


def dedupe_results(results: list[RetrievalResult]) -> list[RetrievalResult]:
    seen: set[str] = set()
    deduped: list[RetrievalResult] = []
    for result in sorted(results, key=lambda item: item.score, reverse=True):
        if result.entry.entry_id in seen:
            continue
        seen.add(result.entry.entry_id)
        deduped.append(result)
    return deduped
