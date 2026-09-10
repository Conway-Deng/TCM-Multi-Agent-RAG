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
    qwen: LLMProvider | None = None
    glm: LLMProvider | None = None
    deepseek: LLMProvider | None = None
    consensus: LLMProvider | None = None


M2_SPECIALIST_ROTATIONS: dict[int, tuple[str, str, str]] = {
    1: ("qwen", "glm", "deepseek"),
    2: ("glm", "deepseek", "qwen"),
    3: ("deepseek", "qwen", "glm"),
}


def build_llm_provider(model_id: str) -> LLMProvider:
    """Build every configured remote model through the verified Qwen path."""
    settings = get_settings()
    return OpenAICompatibleLLMProvider(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        model=model_id,
        timeout=settings.llm_timeout_seconds,
        max_tokens=settings.llm_max_tokens,
        provider_name=settings.llm_provider,
    )


def configured_model_provider(providers: ProviderBundle, model_key: str) -> LLMProvider:
    provider = getattr(providers, model_key, None)
    if provider is None:
        return providers.llm
    return provider


def specialist_provider_for(
    providers: ProviderBundle,
    model_profile: str | None,
    *,
    seat_index: int,
    rotation_id: int,
    model_target: str | None = None,
) -> LLMProvider:
    target = getattr(model_target, "value", model_target)
    if target is not None:
        if target not in {"qwen", "glm", "deepseek"}:
            raise ValueError(f"Unsupported model target: {target}")
        return configured_model_provider(providers, target)
    profile = getattr(model_profile, "value", model_profile)
    if profile is None:
        return providers.llm
    if profile == "M1":
        return configured_model_provider(providers, "qwen")
    if profile != "M2":
        raise ValueError(f"Unsupported model profile: {profile}")
    try:
        rotation = M2_SPECIALIST_ROTATIONS[rotation_id]
    except KeyError as exc:
        raise ValueError(f"Unsupported M2 rotation: {rotation_id}") from exc
    return configured_model_provider(providers, rotation[seat_index % len(rotation)])


def consensus_provider_for(providers: ProviderBundle) -> LLMProvider:
    return configured_model_provider(providers, "consensus")


def get_provider_bundle(*, force_mock: bool = False) -> ProviderBundle:
    settings = get_settings()
    mock = DeterministicMockLLM()
    if force_mock or settings.provider_mode == "mock":
        llm: LLMProvider = mock
        qwen: LLMProvider = mock
        glm: LLMProvider = mock
        deepseek: LLMProvider = mock
        consensus: LLMProvider = mock
        mock_mode = True
    else:
        llm = build_llm_provider(settings.llm_model)
        qwen = build_llm_provider(settings.qwen_model)
        glm = build_llm_provider(settings.glm_model)
        deepseek = build_llm_provider(settings.deepseek_model)
        consensus = build_llm_provider(settings.consensus_model)
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
        qwen=qwen,
        glm=glm,
        deepseek=deepseek,
        consensus=consensus,
    )
