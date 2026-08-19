from __future__ import annotations

from collections import Counter
import math
import os
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


TOPIC_ALIASES = {
    "syndrome": {"syndrome", "syndrome_differentiation", "tcm_symptom", "tcm_symptoms"},
    "herbal": {"herbal", "herb", "herbal_medicine", "herbal_knowledge"},
    "acupuncture": {"acupuncture", "acupuncture_meridian", "meridian_theory"},
    "constitution": {"constitution", "constitution_analysis"},
    "dietary": {"dietary", "dietary_therapy"},
    "lifestyle": {"lifestyle", "lifestyle_yangsheng"},
}


def _expanded_topics(topics: list[str] | None) -> set[str]:
    return {alias for topic in topics or [] for alias in TOPIC_ALIASES.get(topic, {topic})}


class RetrievalEngine:
    def __init__(self) -> None:
        self.chunks = load_chunks()
        self.sources = load_sources()
        self.providers = get_provider_bundle()
        self._doc_counts = [Counter(_tokens(chunk.text + " " + " ".join(chunk.keywords))) for chunk in self.chunks]
        self._average_doc_length = sum(sum(doc.values()) for doc in self._doc_counts) / max(1, len(self._doc_counts))
        self._document_frequency = Counter(token for doc in self._doc_counts for token in doc)
        self._document_vectors: list[list[float]] | None = None
        self.actual_embedding_provider = "none"
        self.actual_embedding_model = "none"
        self.actual_reranker_provider = "none"
        self.actual_reranker_model = "none"

    def _lexical(self, query: str) -> dict[str, float]:
        query_counts = Counter(_tokens(query))
        scores: dict[str, float] = {}
        for chunk, doc in zip(self.chunks, self._doc_counts):
            score = 0.0
            length = sum(doc.values())
            for token, query_frequency in query_counts.items():
                frequency = doc[token]
                if frequency == 0:
                    continue
                idf = math.log(1 + (len(self._doc_counts) - self._document_frequency[token] + 0.5) / (self._document_frequency[token] + 0.5))
                denominator = frequency + 1.5 * (1 - 0.75 + 0.75 * length / max(1.0, self._average_doc_length))
                score += query_frequency * idf * (frequency * 2.5) / denominator
            scores[chunk.chunk_id] = score
        maximum = max(scores.values(), default=0.0) or 1.0
        return {key: round(value / maximum, 6) for key, value in scores.items()}

    async def _semantic(self, query: str) -> dict[str, float]:
        provider = self.providers.embedding
        bulk_approved = os.getenv("ALLOW_BULK_REMOTE_EMBEDDING", "false").strip().casefold() in {"1", "true", "yes", "on"}
        if provider.name != "local" and not bulk_approved:
            provider = LocalHashEmbeddingProvider()
        try:
            if self._document_vectors is None:
                self._document_vectors = await provider.embed([chunk.text for chunk in self.chunks])
            query_vector = (await provider.embed([query]))[0]
            self.actual_embedding_provider = provider.name
            self.actual_embedding_model = provider.model
        except ProviderUnavailable:
            local = LocalHashEmbeddingProvider()
            if self._document_vectors is None or provider.name != "local":
                self._document_vectors = await local.embed([chunk.text for chunk in self.chunks])
            query_vector = (await local.embed([query]))[0]
            self.actual_embedding_provider = local.name
            self.actual_embedding_model = local.model
        return {chunk.chunk_id: round(_cosine(query_vector, vector), 6) for chunk, vector in zip(self.chunks, self._document_vectors)}

    async def search(
        self,
        query: str,
        *,
        strategy: RetrievalStrategy = RetrievalStrategy.R2,
        top_k: int = 4,
        topics: list[str] | None = None,
    ) -> list[RetrievalItem]:
        self.actual_embedding_provider = "none"
        self.actual_embedding_model = "none"
        self.actual_reranker_provider = "none"
        self.actual_reranker_model = "none"
        lexical = self._lexical(query) if strategy != RetrievalStrategy.R1 else {chunk.chunk_id: 0.0 for chunk in self.chunks}
        semantic = await self._semantic(query) if strategy != RetrievalStrategy.R0 else {chunk.chunk_id: 0.0 for chunk in self.chunks}
        topic_filter = _expanded_topics(topics)
        allowed = [chunk for chunk in self.chunks if not topic_filter or topic_filter & set(chunk.topics)] or list(self.chunks)
        lexical_rank = {item_id: rank for rank, (item_id, _) in enumerate(sorted(lexical.items(), key=lambda item: item[1], reverse=True), 1)}
        semantic_rank = {item_id: rank for rank, (item_id, _) in enumerate(sorted(semantic.items(), key=lambda item: item[1], reverse=True), 1)}
        fusion = {chunk.chunk_id: 1 / (60 + lexical_rank[chunk.chunk_id]) + 1 / (60 + semantic_rank[chunk.chunk_id]) for chunk in allowed}
        rerank_scores: dict[str, float] = {}
        if strategy == RetrievalStrategy.R3:
            candidates = sorted(allowed, key=lambda chunk: fusion[chunk.chunk_id], reverse=True)[: max(top_k * 3, 10)]
            try:
                reranker = self.providers.rerank
                values = await reranker.rerank(query, [chunk.text for chunk in candidates])
            except ProviderUnavailable:
                reranker = LocalOverlapReranker()
                values = await reranker.rerank(query, [chunk.text for chunk in candidates])
            self.actual_reranker_provider = reranker.name
            self.actual_reranker_model = reranker.model
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
                    topics=chunk.topics,
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
        anchors = self.query_anchors(query)
        searches = list(dict.fromkeys([query, *anchors]))
        anchor_results = [await self.search(item, strategy=strategy, top_k=top_k, topics=topics) for item in searches]
        initial = self._merge_anchor_results(anchor_results, top_k=top_k, strategy=strategy)
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

    def query_anchors(self, query: str) -> list[str]:
        """Return explicit active-corpus entity/alias anchors mentioned in a query."""
        return [target["label"] for target in self.query_anchor_targets(query)]

    def query_anchor_targets(self, query: str) -> list[dict[str, str]]:
        """Return deduplicated corpus targets and their source domain."""
        normalized = query.casefold()
        candidates: list[tuple[str, str]] = []
        for chunk in self.chunks:
            typed_values = [
                *[(value, "herbal") for value in getattr(chunk, "herbs", [])],
                *[(value, "syndrome") for value in getattr(chunk, "syndromes", [])],
            ]
            entity_name = getattr(chunk, "entity_name", "")
            if entity_name:
                domain = "herbal" if "herbal_medicine" in getattr(chunk, "topics", []) else "syndrome" if "syndrome" in getattr(chunk, "topics", []) else "general"
                typed_values.append((entity_name, domain))
            typed_values.extend((value, "general") for value in getattr(chunk, "aliases", []))
            for value, domain in typed_values:
                value = value.strip()
                if len(value) >= 4 and value.casefold() in normalized:
                    candidates.append((value, domain))
        targets: list[dict[str, str]] = []
        seen: set[str] = set()
        for label, domain in sorted(candidates, key=lambda item: len(item[0]), reverse=True):
            key = label.casefold()
            nested_alias = any(key in target["label"].casefold() and domain == target["domain"] for target in targets)
            if key not in seen and not nested_alias:
                targets.append({"label": label, "domain": domain})
                seen.add(key)
        return targets

    def multi_target_evidence_plan(self, query: str, evidence: list[RetrievalItem]) -> dict[str, object] | None:
        """Partition shared evidence by requested corpus target without inventing relationships."""
        targets = self.query_anchor_targets(query)
        if len(targets) < 2:
            return None
        grouped: list[dict[str, object]] = []
        for target in targets:
            variants = self._anchor_variants(target["label"])
            ids = [item.chunk_id for item in evidence if any(value in item.chunk_text.casefold() for value in variants)]
            grouped.append({**target, "supporting_evidence_ids": ids})
        relationship_ids = [
            item.chunk_id
            for item in evidence
            if all(any(value in item.chunk_text.casefold() for value in self._anchor_variants(target["label"])) for target in targets)
        ]
        return {"requested_targets": grouped, "relationship_evidence_ids": relationship_ids}

    @staticmethod
    def _anchor_variants(anchor: str) -> set[str]:
        normalized = anchor.casefold()
        return {normalized, normalized.replace("deficiency of the ", ""), normalized.replace("deficiency of ", "")}

    def unsupported_multi_entity_claim(self, query: str, text: str, evidence: list[RetrievalItem]) -> str | None:
        """Reject a sentence that links multiple named corpus entities without co-occurring evidence."""
        anchors = self.query_anchors(query)
        if len(anchors) < 2:
            return None
        evidence_text = [item.chunk_text.casefold() for item in evidence]
        variants = {anchor: self._anchor_variants(anchor) for anchor in anchors}
        for sentence in re.split(r"(?<=[.!?])\s+", text):
            mentioned = [anchor for anchor in anchors if any(value in sentence.casefold() for value in variants[anchor])]
            if len(mentioned) >= 2 and not any(all(any(value in source for value in variants[anchor]) for anchor in mentioned) for source in evidence_text):
                return "sentence links multiple requested entities without co-occurring supporting evidence"
        return None

    @staticmethod
    def _merge_anchor_results(groups: list[list[RetrievalItem]], *, top_k: int, strategy: RetrievalStrategy) -> list[RetrievalItem]:
        by_id: dict[str, RetrievalItem] = {}
        for group in groups:
            for item in group:
                by_id.setdefault(item.chunk_id, item)
        if not by_id:
            return []
        score_name = {RetrievalStrategy.R0: "lexical_score", RetrievalStrategy.R1: "semantic_score", RetrievalStrategy.R2: "fusion_score", RetrievalStrategy.R3: "rerank_score"}[strategy]
        ordered = sorted(by_id.values(), key=lambda item: (getattr(item, score_name) or 0.0), reverse=True)
        selected: list[RetrievalItem] = []
        # Preserve at least one result from each anchor query before filling the shared top-k.
        for group in groups[1:]:
            if group and len(selected) < top_k and group[0].chunk_id not in {item.chunk_id for item in selected}:
                selected.append(group[0])
        for item in ordered:
            if len(selected) >= top_k:
                break
            if item.chunk_id not in {entry.chunk_id for entry in selected}:
                selected.append(item)
        for rank, item in enumerate(selected, 1):
            item.rank = rank
        return selected
