from __future__ import annotations

import os

from .scoring import RetrievalResult


class RerankerUnavailable(Exception):
    """Raised when remote reranking cannot be used safely."""


def rerank_enabled() -> bool:
    return os.getenv("ENABLE_RERANK", "true").strip().casefold() in {"1", "true", "yes", "on"} and os.getenv(
        "ENABLE_REMOTE_RERANK", "false"
    ).strip().casefold() in {"1", "true", "yes", "on"}


async def rerank(query: str, results: list[RetrievalResult]) -> list[RetrievalResult]:
    # SiliconFlow-compatible reranker APIs are provider-specific. The hook is kept explicit
    # so the system never pretends reranking happened when no verified endpoint is enabled.
    if not rerank_enabled():
        raise RerankerUnavailable("remote reranker is disabled")
    raise RerankerUnavailable("remote reranker endpoint is not configured for this prototype")
