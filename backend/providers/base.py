from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class GenerationResult:
    text: str
    provider: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    finish_reason: str | None = None
    fallback: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


class LLMProvider(Protocol):
    name: str
    model: str

    async def generate(
        self,
        *,
        system: str,
        prompt: str,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        frequency_penalty: float = 0.0,
    ) -> GenerationResult: ...


class EmbeddingProvider(Protocol):
    name: str
    model: str

    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class RerankProvider(Protocol):
    name: str
    model: str

    async def rerank(self, query: str, documents: list[str]) -> list[float]: ...


class VectorStoreProvider(Protocol):
    name: str

    async def upsert(self, ids: list[str], vectors: list[list[float]], metadata: list[dict[str, Any]]) -> None: ...
    async def search(self, vector: list[float], top_k: int) -> list[tuple[str, float]]: ...


class EvaluatorProvider(LLMProvider, Protocol):
    pass
