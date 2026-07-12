from __future__ import annotations

from ..knowledge_base import KNOWLEDGE_BASE, KnowledgeEntry
from .scoring import RetrievalResult, character_ngrams, english_tokens, normalise


def _score_entry(query: str, query_tokens: set[str], query_ngrams: set[str], entry: KnowledgeEntry) -> RetrievalResult:
    query_norm = normalise(query)
    matched_terms: list[str] = []
    phrase_score = 0.0

    for language, terms in entry.all_search_terms().items():
        for term in terms:
            term_norm = normalise(term)
            if not term_norm or len(term_norm) < 2:
                continue
            if term_norm in query_norm:
                if term not in matched_terms:
                    matched_terms.append(term)
                phrase_score += 2.4 if language != "en" else 2.0

    entry_tokens = english_tokens(
        " ".join(
            [
                entry.topic,
                entry.subtopic,
                *entry.tags,
                *entry.keywords["en"],
                *entry.symptoms["en"],
                entry.pattern["en"],
            ]
        )
    )
    token_overlap = len(query_tokens & entry_tokens)

    entry_ngrams = character_ngrams(
        " ".join(
            [
                *entry.keywords["zh"],
                *entry.symptoms["zh"],
                entry.pattern["zh"],
                *entry.keywords["ko"],
                *entry.symptoms["ko"],
                entry.pattern["ko"],
            ]
        )
    )
    ngram_overlap = len(query_ngrams & entry_ngrams)

    raw = phrase_score + token_overlap * 0.45 + min(ngram_overlap, 8) * 0.18
    denominator = max(5.0, min(14.0, len(query_tokens) * 0.75 + len(query_ngrams) * 0.12 + 5.0))
    score = min(1.0, raw / denominator)
    if not matched_terms and token_overlap == 0 and ngram_overlap < 2:
        score = 0.0

    return RetrievalResult(
        entry=entry,
        score=round(score, 3),
        matched_terms=tuple(matched_terms[:10]),
        score_breakdown={
            "phrase_score": round(phrase_score, 3),
            "token_overlap": float(token_overlap),
            "ngram_overlap": float(ngram_overlap),
        },
    )


def retrieve_lexical(query: str, *, entries: tuple[KnowledgeEntry, ...] = KNOWLEDGE_BASE, top_k: int = 10) -> list[RetrievalResult]:
    query_tokens = english_tokens(query)
    query_ngrams = character_ngrams(query)
    ranked = [_score_entry(query, query_tokens, query_ngrams, entry) for entry in entries]
    ranked.sort(key=lambda item: (item.score, len(item.matched_terms)), reverse=True)
    return ranked[: max(1, top_k)]
