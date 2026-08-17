from __future__ import annotations

from dataclasses import dataclass

from config import get_settings

from .base import EmbeddingProvider, LLMProvider, RerankProvider, VectorStoreProvider
from .local import DeterministicMockLLM, LocalHashEmbeddingProvider, LocalOverlapReranker, LocalVectorStore
from .openai_compatible import OpenAICompatibleLLMProvider
from .qdrant import QdrantVectorStoreAdapter
from .siliconflow import SiliconFlowEmbeddingProvider, SiliconFlowRerankProvider


@dataclass(frozen=True)
class ProviderBundle:
    llm: LLMProvider
    embedding: EmbeddingProvider
    rerank: RerankProvider
    vector_store: VectorStoreProvider
    evaluator: LLMProvider
    mock_mode: bool


def get_provider_bundle(*, force_mock: bool = False) -> ProviderBundle:
    settings = get_settings()
    mock = DeterministicMockLLM()
    if force_mock or settings.provider_mode == "mock":
        llm: LLMProvider = mock
        mock_mode = True
    else:
        llm = OpenAICompatibleLLMProvider(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            model=settings.llm_model,
            timeout=settings.llm_timeout_seconds,
            max_tokens=settings.llm_max_tokens,
            provider_name=settings.llm_provider,
        )
        mock_mode = False
    embedding: EmbeddingProvider = LocalHashEmbeddingProvider()
    if settings.embedding_provider == "siliconflow" and settings.embedding_api_key:
        embedding = SiliconFlowEmbeddingProvider(api_key=settings.embedding_api_key, base_url=settings.embedding_base_url, model=settings.embedding_model)
    rerank: RerankProvider = LocalOverlapReranker()
    if settings.rerank_provider == "siliconflow" and settings.rerank_api_key:
        rerank = SiliconFlowRerankProvider(api_key=settings.rerank_api_key, base_url=settings.rerank_base_url, model=settings.rerank_model)
    vector_store: VectorStoreProvider = LocalVectorStore()
    if settings.vector_store_provider == "qdrant" and settings.qdrant_url:
        vector_store = QdrantVectorStoreAdapter(url=settings.qdrant_url, api_key=settings.qdrant_api_key, collection=settings.qdrant_collection)
    return ProviderBundle(
        llm=llm,
        embedding=embedding,
        rerank=rerank,
        vector_store=vector_store,
        evaluator=llm,
        mock_mode=mock_mode,
    )
