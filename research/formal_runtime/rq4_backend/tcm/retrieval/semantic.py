from __future__ import annotations

import os
from typing import Any

import httpx

from ..knowledge_base import KnowledgeEntry
from .scoring import RetrievalResult, cosine_similarity


class SemanticRetrievalUnavailable(Exception):
    """Raised when semantic retrieval cannot be used safely."""


def semantic_enabled() -> bool:
    return os.getenv("ENABLE_SEMANTIC_RETRIEVAL", "false").strip().casefold() in {"1", "true", "yes", "on"}


def _entry_text(entry: KnowledgeEntry) -> str:
    parts = [
        entry.topic,
        entry.subtopic,
        " ".join(entry.tags),
        entry.pattern["en"],
        entry.pattern["zh"],
        entry.pattern["ko"],
        entry.rationale["en"],
        entry.rationale["zh"],
        entry.rationale["ko"],
        " ".join(entry.keywords["en"] + entry.keywords["zh"] + entry.keywords["ko"]),
    ]
    return "\n".join(parts)


async def _embed(texts: list[str]) -> list[list[float]]:
    api_key = os.getenv("EMBEDDING_API_KEY", "").strip() or os.getenv("LLM_API_KEY", "").strip()
    base_url = os.getenv("EMBEDDING_BASE_URL", "").strip().rstrip("/") or os.getenv("LLM_BASE_URL", "https://api.siliconflow.cn/v1").rstrip("/")
    model = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3").strip()
    timeout = float(os.getenv("RETRIEVAL_TIMEOUT_SECONDS", "20"))
    if not api_key:
        raise SemanticRetrievalUnavailable("embedding API key is missing")
    payload = {"model": model, "input": texts}
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(f"{base_url}/embeddings", headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise SemanticRetrievalUnavailable("embedding provider unavailable") from exc
    vectors: list[list[float]] = []
    try:
        for item in data["data"]:
            vector = item["embedding"]
            if not isinstance(vector, list):
                raise TypeError
            vectors.append([float(value) for value in vector])
    except (KeyError, TypeError, ValueError) as exc:
        raise SemanticRetrievalUnavailable("embedding provider returned an unexpected response") from exc
    if len(vectors) != len(texts):
        raise SemanticRetrievalUnavailable("embedding provider returned an incomplete response")
    return vectors


async def retrieve_semantic(query: str, entries: tuple[KnowledgeEntry, ...], *, top_k: int = 10) -> list[RetrievalResult]:
    if not semantic_enabled():
        raise SemanticRetrievalUnavailable("semantic retrieval is disabled")
    vectors = await _embed([query, *[_entry_text(entry) for entry in entries]])
    query_vector = vectors[0]
    entry_vectors = vectors[1:]
    results = [
        RetrievalResult(
            entry=entry,
            score=round(cosine_similarity(query_vector, vector), 3),
            matched_terms=(),
            score_breakdown={"semantic_score": round(cosine_similarity(query_vector, vector), 3)},
        )
        for entry, vector in zip(entries, entry_vectors)
    ]
    results.sort(key=lambda item: item.score, reverse=True)
    return results[: max(1, top_k)]
