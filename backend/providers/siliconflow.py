from __future__ import annotations

import httpx

from .openai_compatible import ProviderUnavailable


class SiliconFlowEmbeddingProvider:
    name = "siliconflow"

    def __init__(self, *, api_key: str, base_url: str, model: str, timeout: float = 30.0) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not self.api_key:
            raise ProviderUnavailable("Embedding API key is missing")
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/embeddings",
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json={"model": self.model, "input": texts},
                )
                response.raise_for_status()
                data = response.json()
            return [[float(value) for value in item["embedding"]] for item in data["data"]]
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            raise ProviderUnavailable("SiliconFlow embedding provider unavailable") from exc


class SiliconFlowRerankProvider:
    name = "siliconflow"

    def __init__(self, *, api_key: str, base_url: str, model: str, timeout: float = 30.0) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    async def rerank(self, query: str, documents: list[str]) -> list[float]:
        if not self.api_key:
            raise ProviderUnavailable("Rerank API key is missing")
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/rerank",
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json={"model": self.model, "query": query, "documents": documents, "top_n": len(documents)},
                )
                response.raise_for_status()
                data = response.json()
            scores = [0.0] * len(documents)
            for item in data["results"]:
                scores[int(item["index"])] = float(item["relevance_score"])
            return scores
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
            raise ProviderUnavailable("SiliconFlow rerank provider unavailable") from exc
