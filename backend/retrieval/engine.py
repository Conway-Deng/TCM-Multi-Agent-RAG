from __future__ import annotations

from collections import Counter
import math
import re

from corpus import load_chunks, load_sources
from providers import get_provider_bundle
from providers.local import LocalHashEmbeddingProvider, LocalOverlapReranker
from providers.openai_compatible import ProviderUnavailable
from schemas.research import RetrievalItem, RetrievalStrategy


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z][a-z-]{1,}|[\u3400-\u9fff]|[\uac00-\ud7af]", text.casefold())


def _cosine(left: list[float], right: list[float]) -> float:
    return max(0.0, min(1.0, sum(a * b for a, b in zip(left, right))))


class RetrievalEngine:
    def __init__(self) -> None:
        self.chunks = load_chunks()
        self.sources = load_sources()
        self.providers = get_provider_bundle()

    def _lexical(self, query: str) -> dict[str, float]:
        query_counts = Counter(_tokens(query))
        docs = [Counter(_tokens(chunk.text + " " + " ".join(chunk.keywords))) for chunk in self.chunks]
        avg_len = sum(sum(doc.values()) for doc in docs) / max(1, len(docs))
        document_frequency = Counter(token for doc in docs for token in doc)
        scores: dict[str, float] = {}
        for chunk, doc in zip(self.chunks, docs):
            score = 0.0
            length = sum(doc.values())
            for token, query_frequency in query_counts.items():
                frequency = doc[token]
                if frequency == 0:
                    continue
                idf = math.log(1 + (len(docs) - document_frequency[token] + 0.5) / (document_frequency[token] + 0.5))
                denominator = frequency + 1.5 * (1 - 0.75 + 0.75 * length / max(1.0, avg_len))
                score += query_frequency * idf * (frequency * 2.5) / denominator
            scores[chunk.chunk_id] = score
        maximum = max(scores.values(), default=0.0) or 1.0
        return {key: round(value / maximum, 6) for key, value in scores.items()}

    async def _semantic(self, query: str) -> dict[str, float]:
        try:
            vectors = await self.providers.embedding.embed([query, *[chunk.text for chunk in self.chunks]])
        except ProviderUnavailable:
            vectors = await LocalHashEmbeddingProvider().embed([query, *[chunk.text for chunk in self.chunks]])
        return {chunk.chunk_id: round(_cosine(vectors[0], vector), 6) for chunk, vector in zip(self.chunks, vectors[1:])}

    async def search(
        self,
        query: str,
        *,
        strategy: RetrievalStrategy = RetrievalStrategy.R2,
        top_k: int = 4,
        topics: list[str] | None = None,
    ) -> list[RetrievalItem]:
        lexical = self._lexical(query)
        semantic = await self._semantic(query)
        allowed = [chunk for chunk in self.chunks if not topics or set(topics) & set(chunk.topics)] or list(self.chunks)
        lexical_rank = {item_id: rank for rank, (item_id, _) in enumerate(sorted(lexical.items(), key=lambda item: item[1], reverse=True), 1)}
        semantic_rank = {item_id: rank for rank, (item_id, _) in enumerate(sorted(semantic.items(), key=lambda item: item[1], reverse=True), 1)}
        fusion = {chunk.chunk_id: 1 / (60 + lexical_rank[chunk.chunk_id]) + 1 / (60 + semantic_rank[chunk.chunk_id]) for chunk in allowed}
        rerank_scores: dict[str, float] = {}
        if strategy == RetrievalStrategy.R3:
            candidates = sorted(allowed, key=lambda chunk: fusion[chunk.chunk_id], reverse=True)[: max(top_k * 3, 10)]
            try:
                values = await self.providers.rerank.rerank(query, [chunk.text for chunk in candidates])
            except ProviderUnavailable:
                values = await LocalOverlapReranker().rerank(query, [chunk.text for chunk in candidates])
            rerank_scores = {chunk.chunk_id: value for chunk, value in zip(candidates, values)}
        if strategy == RetrievalStrategy.R0:
            ranked = sorted(allowed, key=lambda chunk: lexical[chunk.chunk_id], reverse=True)
        elif strategy == RetrievalStrategy.R1:
            ranked = sorted(allowed, key=lambda chunk: semantic[chunk.chunk_id], reverse=True)
        elif strategy == RetrievalStrategy.R3:
            ranked = sorted(allowed, key=lambda chunk: (rerank_scores.get(chunk.chunk_id, -1), fusion[chunk.chunk_id]), reverse=True)
        else:
            ranked = sorted(allowed, key=lambda chunk: fusion[chunk.chunk_id], reverse=True)
        method = {"R0": "lexical", "R1": "dense", "R2": "hybrid", "R3": "hybrid_reranked"}[strategy.value]
        results: list[RetrievalItem] = []
        for rank, chunk in enumerate(ranked[:top_k], 1):
            source = self.sources.get(chunk.source_id)
            results.append(
                RetrievalItem(
                    chunk_id=chunk.chunk_id,
                    source_id=chunk.source_id,
                    rank=rank,
                    lexical_score=lexical[chunk.chunk_id] if strategy != RetrievalStrategy.R1 else None,
                    semantic_score=semantic[chunk.chunk_id] if strategy != RetrievalStrategy.R0 else None,
                    fusion_score=round(fusion[chunk.chunk_id], 6) if strategy in {RetrievalStrategy.R2, RetrievalStrategy.R3} else None,
                    rerank_score=rerank_scores.get(chunk.chunk_id) if strategy == RetrievalStrategy.R3 else None,
                    retrieval_method=method,
                    chunk_text=chunk.text,
                    source_metadata=source.model_dump() if source else {},
                )
            )
        return results

    async def search_with_reflection(
        self,
        query: str,
        *,
        strategy: RetrievalStrategy,
        top_k: int,
        topics: list[str],
        enabled: bool,
    ) -> tuple[list[RetrievalItem], bool]:
        initial = await self.search(query, strategy=strategy, top_k=top_k, topics=topics)
        if not enabled:
            return initial, False
        top_signal = max((item.rerank_score or item.semantic_score or item.lexical_score or 0.0) for item in initial) if initial else 0.0
        if initial and top_signal >= 0.18:
            return initial, False
        reformulated = f"{query} Traditional Chinese Medicine {' '.join(topics)} syndrome constitution meridian educational evidence"
        second = await self.search(reformulated, strategy=strategy, top_k=top_k, topics=topics)
        merged = {item.chunk_id: item for item in [*initial, *second]}
        ranked = sorted(merged.values(), key=lambda item: item.rerank_score or item.fusion_score or item.semantic_score or item.lexical_score or 0.0, reverse=True)[:top_k]
        for rank, item in enumerate(ranked, 1):
            item.rank = rank
        return ranked, True
