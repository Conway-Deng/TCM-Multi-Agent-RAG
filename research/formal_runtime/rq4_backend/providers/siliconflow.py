from __future__ import annotations

import httpx
import math

from .openai_compatible import ProviderUnavailable


class SiliconFlowEmbeddingProvider:
    name = "siliconflow"

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        timeout: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.transport = transport

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not self.api_key:
            raise ProviderUnavailable("Embedding API key is missing")
        try:
            async with httpx.AsyncClient(timeout=self.timeout, transport=self.transport) as client:
                response = await client.post(
                    f"{self.base_url}/embeddings",
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json={"model": self.model, "input": texts},
                )
                response.raise_for_status()
                data = response.json()
            if not isinstance(data, dict):
                raise TypeError("response root is not an object")
            returned_model = data.get("model")
            if returned_model is not None and returned_model != self.model:
                raise ValueError(f"model mismatch: expected {self.model}, returned {returned_model}")
            items = data["data"]
            if not isinstance(items, list) or len(items) != len(texts):
                raise ValueError(f"item count mismatch: expected {len(texts)}, returned {len(items) if isinstance(items, list) else 'non-list'}")
            by_index: dict[int, list[float]] = {}
            for item in items:
                if not isinstance(item, dict) or not isinstance(item.get("index"), int):
                    raise TypeError("embedding item is missing an integer index")
                index = item["index"]
                if index in by_index or not 0 <= index < len(texts):
                    raise ValueError(f"invalid or duplicate embedding index: {index}")
                vector = item.get("embedding")
                if not isinstance(vector, list) or not vector:
                    raise TypeError(f"embedding index {index} has no vector")
                values = [float(value) for value in vector]
                if any(not math.isfinite(value) for value in values):
                    raise ValueError(f"embedding index {index} contains non-finite values")
                by_index[index] = values
            expected_indices = set(range(len(texts)))
            if set(by_index) != expected_indices:
                raise ValueError("embedding response has missing or unverified ordering indices")
            dimensions = {len(vector) for vector in by_index.values()}
            if len(dimensions) != 1:
                raise ValueError("embedding dimensions are inconsistent")
            return [by_index[index] for index in range(len(texts))]
        except ProviderUnavailable:
            raise
        except httpx.TimeoutException as exc:
            raise ProviderUnavailable("SiliconFlow embedding request timed out", error_type="timeout") from exc
        except httpx.HTTPStatusError as exc:
            raise ProviderUnavailable(
                f"SiliconFlow embedding HTTP {exc.response.status_code}",
                error_type="http_4xx" if exc.response.status_code < 500 else "http_5xx",
                http_status=exc.response.status_code,
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderUnavailable("SiliconFlow embedding connectivity failure", error_type="connectivity") from exc
        except (KeyError, TypeError, ValueError) as exc:
            raise ProviderUnavailable(f"SiliconFlow embedding malformed response: {exc}", error_type="malformed_response") from exc


class SiliconFlowRerankProvider:
    name = "siliconflow"

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        timeout: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.transport = transport

    async def rerank(self, query: str, documents: list[str]) -> list[float]:
        if not self.api_key:
            raise ProviderUnavailable("Rerank API key is missing")
        try:
            async with httpx.AsyncClient(timeout=self.timeout, transport=self.transport) as client:
                response = await client.post(
                    f"{self.base_url}/rerank",
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json={"model": self.model, "query": query, "documents": documents, "top_n": len(documents)},
                )
                response.raise_for_status()
                data = response.json()
            if not isinstance(data, dict):
                raise TypeError("response root is not an object")
            returned_model = data.get("model")
            if returned_model is not None and returned_model != self.model:
                raise ValueError(f"model mismatch: expected {self.model}, returned {returned_model}")
            items = data["results"]
            if not isinstance(items, list) or len(items) != len(documents):
                raise ValueError(f"item count mismatch: expected {len(documents)}, returned {len(items) if isinstance(items, list) else 'non-list'}")
            by_index: dict[int, float] = {}
            for item in items:
                if not isinstance(item, dict):
                    raise TypeError("rerank item is not an object")
                index = item.get("index")
                if not isinstance(index, int) or index in by_index or not 0 <= index < len(documents):
                    raise ValueError(f"invalid or duplicate rerank index: {index}")
                score = float(item["relevance_score"])
                if not math.isfinite(score):
                    raise ValueError(f"rerank index {index} contains a non-finite score")
                by_index[index] = score
            if set(by_index) != set(range(len(documents))):
                raise ValueError("rerank response has missing or unverified ordering indices")
            return [by_index[index] for index in range(len(documents))]
        except ProviderUnavailable:
            raise
        except httpx.TimeoutException as exc:
            raise ProviderUnavailable("SiliconFlow rerank request timed out", error_type="timeout") from exc
        except httpx.HTTPStatusError as exc:
            raise ProviderUnavailable(
                f"SiliconFlow rerank HTTP {exc.response.status_code}",
                error_type="http_4xx" if exc.response.status_code < 500 else "http_5xx",
                http_status=exc.response.status_code,
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderUnavailable("SiliconFlow rerank connectivity failure", error_type="connectivity") from exc
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ProviderUnavailable(f"SiliconFlow rerank malformed response: {exc}", error_type="malformed_response") from exc
