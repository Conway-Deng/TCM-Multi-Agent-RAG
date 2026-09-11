from __future__ import annotations

from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import re
from typing import Any

from corpus import corpus_stats, load_chunks, load_sources
from providers import ProviderBundle, get_provider_bundle
from providers.local import LocalHashEmbeddingProvider, LocalOverlapReranker
from providers.openai_compatible import ProviderUnavailable
from schemas.research import RetrievalItem, RetrievalStrategy


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z][a-z-]{1,}|[\u3400-\u9fff]|[\uac00-\ud7af]", text.casefold())


def _cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        raise ProviderUnavailable("Embedding dimensions are inconsistent", error_type="malformed_response")
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


FORMAL_EMBEDDING_PROVIDER = "siliconflow"
FORMAL_EMBEDDING_MODEL = "BAAI/bge-m3"
FORMAL_RERANK_PROVIDER = "siliconflow"
FORMAL_RERANK_MODEL = "BAAI/bge-reranker-v2-m3"
DEFAULT_PREPROCESSING_VERSION = "chunk-text-v1"
DEFAULT_EMBEDDING_CONFIG_VERSION = "retrieval-ablation-v1"


class RetrievalEngine:
    def __init__(
        self,
        *,
        formal_strict: bool = False,
        persistent_cache: bool | None = None,
        cache_dir: Path | None = None,
        embedding_batch_size: int = 64,
        candidate_depth: int = 12,
        preprocessing_version: str = DEFAULT_PREPROCESSING_VERSION,
        embedding_config_version: str = DEFAULT_EMBEDDING_CONFIG_VERSION,
        chunks: tuple[Any, ...] | None = None,
        sources: dict[str, Any] | None = None,
        providers: ProviderBundle | None = None,
        corpus_sha256: str | None = None,
    ) -> None:
        self.chunks = chunks if chunks is not None else load_chunks()
        self.sources = sources if sources is not None else load_sources()
        self.providers = providers if providers is not None else get_provider_bundle()
        self.formal_strict = formal_strict
        self.persistent_cache = formal_strict if persistent_cache is None else persistent_cache
        self.cache_dir = cache_dir or Path(__file__).resolve().parents[2] / "research" / "retrieval_ablation" / "cache"
        self.embedding_batch_size = max(1, embedding_batch_size)
        self.candidate_depth = max(1, candidate_depth)
        self.preprocessing_version = preprocessing_version
        self.embedding_config_version = embedding_config_version
        runtime_sha = corpus_stats().get("corpus_sha256") if chunks is None else None
        self.corpus_sha256 = corpus_sha256 or str(runtime_sha or self._content_sha256())
        self._doc_counts = [Counter(_tokens(chunk.text + " " + " ".join(chunk.keywords))) for chunk in self.chunks]
        self._average_doc_length = sum(sum(doc.values()) for doc in self._doc_counts) / max(1, len(self._doc_counts))
        self._document_frequency = Counter(token for doc in self._doc_counts for token in doc)
        self._document_vectors: list[list[float]] | None = None
        self._query_vectors: dict[str, list[float]] = {}
        self._active_cache_identity: dict[str, str] | None = None
        self.actual_embedding_provider = "none"
        self.actual_embedding_model = "none"
        self.actual_reranker_provider = "none"
        self.actual_reranker_model = "none"

    def _content_sha256(self) -> str:
        digest = hashlib.sha256()
        for chunk in self.chunks:
            digest.update(chunk.chunk_id.encode("utf-8"))
            digest.update(b"\0")
            digest.update(chunk.text.encode("utf-8"))
            digest.update(b"\0")
        return digest.hexdigest()

    def embedding_cache_identity(self, provider: Any | None = None) -> dict[str, str]:
        provider = provider or self.providers.embedding
        return {
            "corpus_sha256": self.corpus_sha256,
            "embedding_provider": str(provider.name),
            "embedding_model": str(provider.model),
            "preprocessing_version": self.preprocessing_version,
            "embedding_config_version": self.embedding_config_version,
        }

    @staticmethod
    def _identity_hash(identity: dict[str, str]) -> str:
        payload = json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def _cache_path(self, identity: dict[str, str]) -> Path:
        return self.cache_dir / f"embeddings-{self._identity_hash(identity)}.json"

    @staticmethod
    def _validate_vectors(vectors: list[list[float]], expected_count: int, *, expected_dimension: int | None = None) -> int:
        if len(vectors) != expected_count:
            raise ProviderUnavailable(
                f"Embedding count mismatch: expected {expected_count}, returned {len(vectors)}",
                error_type="malformed_response",
            )
        dimensions = {len(vector) for vector in vectors}
        if not vectors or len(dimensions) != 1 or 0 in dimensions:
            raise ProviderUnavailable("Embedding dimensions are missing or inconsistent", error_type="malformed_response")
        dimension = next(iter(dimensions))
        if expected_dimension is not None and dimension != expected_dimension:
            raise ProviderUnavailable(
                f"Embedding dimension mismatch: expected {expected_dimension}, returned {dimension}",
                error_type="malformed_response",
            )
        if any(not math.isfinite(value) for vector in vectors for value in vector):
            raise ProviderUnavailable("Embedding response contains non-finite values", error_type="malformed_response")
        return dimension

    def _load_embedding_cache(self, identity: dict[str, str]) -> None:
        if self._active_cache_identity == identity:
            return
        self._document_vectors = None
        self._query_vectors = {}
        self._active_cache_identity = identity
        path = self._cache_path(identity)
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("identity") != identity:
                raise ValueError("cache identity mismatch")
            expected_ids = [chunk.chunk_id for chunk in self.chunks]
            if data.get("document_ids") != expected_ids:
                raise ValueError("cache document ordering mismatch")
            document_vectors = [[float(value) for value in vector] for vector in data["document_vectors"]]
            dimension = self._validate_vectors(document_vectors, len(expected_ids))
            query_vectors = {
                str(key): [float(value) for value in vector]
                for key, vector in dict(data.get("query_vectors", {})).items()
            }
            for vector in query_vectors.values():
                self._validate_vectors([vector], 1, expected_dimension=dimension)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ProviderUnavailable(f"Embedding cache validation failed: {exc}", error_type="malformed_response") from exc
        self._document_vectors = document_vectors
        self._query_vectors = query_vectors

    def _save_embedding_cache(self, identity: dict[str, str]) -> None:
        if self._document_vectors is None:
            return
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        path = self._cache_path(identity)
        temporary = path.with_suffix(".tmp")
        payload = {
            "identity": identity,
            "document_ids": [chunk.chunk_id for chunk in self.chunks],
            "document_vectors": self._document_vectors,
            "query_vectors": self._query_vectors,
        }
        temporary.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        temporary.replace(path)

    async def _embed_batched(self, provider: Any, texts: list[str], *, expected_dimension: int | None = None) -> list[list[float]]:
        vectors: list[list[float]] = []
        dimension = expected_dimension
        for offset in range(0, len(texts), self.embedding_batch_size):
            batch = texts[offset : offset + self.embedding_batch_size]
            returned = await provider.embed(batch)
            batch_dimension = self._validate_vectors(returned, len(batch), expected_dimension=dimension)
            dimension = dimension or batch_dimension
            vectors.extend(returned)
        self._validate_vectors(vectors, len(texts), expected_dimension=dimension)
        return vectors

    def _validate_formal_embedding_provider(self, provider: Any) -> None:
        if not self.formal_strict:
            return
        if provider.name != FORMAL_EMBEDDING_PROVIDER or provider.model != FORMAL_EMBEDDING_MODEL:
            raise ProviderUnavailable(
                f"Formal R1/R2/R3 requires {FORMAL_EMBEDDING_PROVIDER}/{FORMAL_EMBEDDING_MODEL}; "
                f"got {provider.name}/{provider.model}",
                error_type="configuration",
            )

    def _validate_formal_reranker(self, provider: Any) -> None:
        if not self.formal_strict:
            return
        if provider.name != FORMAL_RERANK_PROVIDER or provider.model != FORMAL_RERANK_MODEL:
            raise ProviderUnavailable(
                f"Formal R3 requires {FORMAL_RERANK_PROVIDER}/{FORMAL_RERANK_MODEL}; got {provider.name}/{provider.model}",
                error_type="configuration",
            )

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
        self._validate_formal_embedding_provider(provider)
        bulk_approved = os.getenv("ALLOW_BULK_REMOTE_EMBEDDING", "false").strip().casefold() in {"1", "true", "yes", "on"}
        if provider.name != "local" and not bulk_approved and not self.formal_strict:
            provider = LocalHashEmbeddingProvider()
        if self.formal_strict and not bulk_approved:
            raise ProviderUnavailable("Formal remote embedding requires ALLOW_BULK_REMOTE_EMBEDDING=true", error_type="configuration")
        try:
            identity = self.embedding_cache_identity(provider)
            if self.persistent_cache:
                self._load_embedding_cache(identity)
            if self._document_vectors is None:
                self._document_vectors = await self._embed_batched(provider, [chunk.text for chunk in self.chunks])
            dimension = self._validate_vectors(self._document_vectors, len(self.chunks))
            query_key = hashlib.sha256(query.encode("utf-8")).hexdigest()
            query_vector = self._query_vectors.get(query_key)
            if query_vector is None:
                query_vector = (await self._embed_batched(provider, [query], expected_dimension=dimension))[0]
                self._query_vectors[query_key] = query_vector
                if self.persistent_cache:
                    self._save_embedding_cache(identity)
            self.actual_embedding_provider = provider.name
            self.actual_embedding_model = provider.model
        except ProviderUnavailable:
            if self.formal_strict:
                raise
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
            if self.formal_strict and top_k > self.candidate_depth:
                raise ProviderUnavailable("Final top-k exceeds the fixed candidate depth", error_type="configuration")
            candidate_limit = self.candidate_depth if self.formal_strict else max(top_k * 3, 10)
            candidates = sorted(allowed, key=lambda chunk: fusion[chunk.chunk_id], reverse=True)[:candidate_limit]
            try:
                reranker = self.providers.rerank
                self._validate_formal_reranker(reranker)
                values = await reranker.rerank(query, [chunk.text for chunk in candidates])
                if len(values) != len(candidates) or any(not math.isfinite(value) for value in values):
                    raise ProviderUnavailable("Reranker returned malformed or partial scores", error_type="malformed_response")
            except ProviderUnavailable:
                if self.formal_strict:
                    raise
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
