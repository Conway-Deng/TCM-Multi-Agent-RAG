from __future__ import annotations

from typing import Any


class QdrantVectorStoreAdapter:
    """Optional future-ready adapter boundary; local execution never requires Qdrant."""

    name = "qdrant"

    def __init__(self, *, url: str, api_key: str, collection: str) -> None:
        self.url = url
        self.api_key = api_key
        self.collection = collection

    async def upsert(self, ids: list[str], vectors: list[list[float]], metadata: list[dict[str, Any]]) -> None:
        raise RuntimeError("Qdrant adapter is not enabled; install a reviewed integration before use.")

    async def search(self, vector: list[float], top_k: int) -> list[tuple[str, float]]:
        raise RuntimeError("Qdrant adapter is not enabled; local vector search remains the default.")
