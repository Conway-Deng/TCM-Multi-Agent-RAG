from __future__ import annotations

import hashlib
import math
import re

from .base import GenerationResult


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z][a-z-]{1,}|[\u3400-\u9fff]|[\uac00-\ud7af]", text.casefold())


class DeterministicMockLLM:
    name = "mock"
    model = "deterministic-mock-v1"

    async def generate(self, *, system: str, prompt: str, temperature: float = 0.0) -> GenerationResult:
        digest = hashlib.sha256((system + "\n" + prompt).encode("utf-8")).hexdigest()[:10]
        text = (
            "Mock research output derived from the supplied local evidence. "
            "It is deterministic, educational only, and must not be interpreted as clinical validation. "
            f"[mock:{digest}]"
        )
        return GenerationResult(text=text, provider=self.name, model=self.model, completion_tokens=len(text.split()), fallback=True)


class LocalHashEmbeddingProvider:
    name = "local"
    model = "local-hash-embedding-v1"

    def __init__(self, dimensions: int = 256) -> None:
        self.dimensions = dimensions

    async def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            vector = [0.0] * self.dimensions
            for token in _tokens(text):
                raw = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
                index = int.from_bytes(raw[:4], "big") % self.dimensions
                sign = 1.0 if raw[4] % 2 == 0 else -1.0
                vector[index] += sign
            norm = math.sqrt(sum(value * value for value in vector)) or 1.0
            vectors.append([value / norm for value in vector])
        return vectors


class LocalOverlapReranker:
    name = "local"
    model = "local-overlap-reranker-v1"

    async def rerank(self, query: str, documents: list[str]) -> list[float]:
        query_tokens = set(_tokens(query))
        scores: list[float] = []
        for document in documents:
            doc_tokens = set(_tokens(document))
            overlap = len(query_tokens & doc_tokens)
            scores.append(round(overlap / max(1, len(query_tokens)), 6))
        return scores


class LocalVectorStore:
    name = "local"

    def __init__(self) -> None:
        self._vectors: dict[str, tuple[list[float], dict]] = {}

    async def upsert(self, ids: list[str], vectors: list[list[float]], metadata: list[dict]) -> None:
        self._vectors.update({item_id: (vector, meta) for item_id, vector, meta in zip(ids, vectors, metadata)})

    async def search(self, vector: list[float], top_k: int) -> list[tuple[str, float]]:
        ranked = [(item_id, sum(a * b for a, b in zip(vector, stored))) for item_id, (stored, _) in self._vectors.items()]
        return sorted(ranked, key=lambda item: item[1], reverse=True)[:top_k]
