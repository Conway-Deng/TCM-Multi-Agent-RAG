from __future__ import annotations

import asyncio
import hashlib
import json
import math
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest


BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from providers.openai_compatible import ProviderUnavailable
from retrieval import engine as engine_module
from retrieval.engine import RetrievalEngine
from schemas.research import RetrievalStrategy


def _chunks(count: int = 3) -> tuple[SimpleNamespace, ...]:
    return tuple(
        SimpleNamespace(
            chunk_id=f"chunk-{index}",
            source_id="source",
            text=f"alpha evidence {index}",
            keywords=["alpha"],
            topics=["herbal"],
        )
        for index in range(count)
    )


class FakeEmbedding:
    def __init__(
        self,
        *,
        name: str = "siliconflow",
        model: str = "BAAI/bge-m3",
        fail: bool = False,
    ) -> None:
        self.name = name
        self.model = model
        self.fail = fail
        self.calls: list[list[str]] = []

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        if self.fail:
            raise ProviderUnavailable("embedding unavailable", error_type="connectivity")
        return [[1.0, 0.0] for _ in texts]


class FakeReranker:
    def __init__(
        self,
        *,
        name: str = "siliconflow",
        model: str = "BAAI/bge-reranker-v2-m3",
        fail: bool = False,
        malformed: bool = False,
    ) -> None:
        self.name = name
        self.model = model
        self.fail = fail
        self.malformed = malformed
        self.document_counts: list[int] = []

    async def rerank(self, _query: str, documents: list[str]) -> list[float]:
        self.document_counts.append(len(documents))
        if self.fail:
            raise ProviderUnavailable("reranker unavailable", error_type="connectivity")
        if self.malformed:
            return [1.0]
        return [float(len(documents) - index) for index, _ in enumerate(documents)]


def _providers(embedding: FakeEmbedding | None = None, reranker: FakeReranker | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        embedding=embedding or FakeEmbedding(),
        rerank=reranker or FakeReranker(),
    )


def _engine(
    tmp_path: Path,
    *,
    formal_strict: bool,
    chunks: tuple[SimpleNamespace, ...] | None = None,
    embedding: FakeEmbedding | None = None,
    reranker: FakeReranker | None = None,
    candidate_depth: int = 12,
    persistent_cache: bool | None = None,
) -> RetrievalEngine:
    return RetrievalEngine(
        formal_strict=formal_strict,
        persistent_cache=persistent_cache,
        cache_dir=tmp_path,
        embedding_batch_size=2,
        candidate_depth=candidate_depth,
        preprocessing_version="chunk-text-v1",
        embedding_config_version="retrieval-ablation-v1",
        chunks=chunks or _chunks(),
        sources={},
        providers=_providers(embedding, reranker),
        corpus_sha256="corpus-sha",
    )


def test_ordinary_constructor_defaults_preserve_nonformal_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    chunks = _chunks()
    monkeypatch.setattr(engine_module, "load_chunks", lambda: chunks)
    monkeypatch.setattr(engine_module, "load_sources", lambda: {})
    monkeypatch.setattr(engine_module, "get_provider_bundle", _providers)
    monkeypatch.setattr(engine_module, "corpus_stats", lambda: pytest.fail("ordinary construction must not require formal corpus identity"))

    engine = RetrievalEngine()

    assert engine.formal_strict is False
    assert engine.persistent_cache is False
    assert engine.chunks == chunks


def test_strict_constructor_accepts_frozen_runner_configuration(tmp_path: Path) -> None:
    engine = _engine(tmp_path, formal_strict=True, candidate_depth=9)

    assert engine.formal_strict is True
    assert engine.persistent_cache is True
    assert engine.cache_dir == tmp_path
    assert engine.embedding_batch_size == 2
    assert engine.candidate_depth == 9
    assert engine.preprocessing_version == "chunk-text-v1"
    assert engine.embedding_config_version == "retrieval-ablation-v1"
    assert engine._query_vectors == {}
    assert engine._active_cache_identity is None


def test_strict_constructor_uses_active_corpus_sha_for_warmup_identity(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    chunks = _chunks()
    providers = _providers()
    monkeypatch.setattr(engine_module, "load_chunks", lambda: chunks)
    monkeypatch.setattr(engine_module, "load_sources", lambda: {})
    monkeypatch.setattr(engine_module, "get_provider_bundle", lambda: providers)
    monkeypatch.setattr(engine_module, "corpus_stats", lambda: {"corpus_sha256": "frozen-corpus-sha"})

    engine = RetrievalEngine(formal_strict=True, cache_dir=tmp_path)

    assert engine.embedding_cache_identity() == {
        "corpus_sha256": "frozen-corpus-sha",
        "embedding_provider": "siliconflow",
        "embedding_model": "BAAI/bge-m3",
        "preprocessing_version": "chunk-text-v1",
        "embedding_config_version": "retrieval-ablation-v1",
    }


def test_vector_validation_accepts_only_complete_consistent_finite_vectors() -> None:
    assert RetrievalEngine._validate_vectors([[1.0, 0.0], [0.0, 1.0]], 2, expected_dimension=2) == 2

    invalid = (
        ([[1.0, 0.0]], 2, None),
        ([[1.0, 0.0], [1.0]], 2, None),
        ([[1.0, 0.0]], 1, 3),
        ([[1.0, math.nan]], 1, 2),
        ([[1.0, math.inf]], 1, 2),
    )
    for vectors, count, dimension in invalid:
        with pytest.raises(ProviderUnavailable):
            RetrievalEngine._validate_vectors(vectors, count, expected_dimension=dimension)


def test_cache_identity_and_filename_match_frozen_warmup_schema(tmp_path: Path) -> None:
    provider = FakeEmbedding()
    engine = _engine(tmp_path, formal_strict=True, embedding=provider)
    expected = {
        "corpus_sha256": "corpus-sha",
        "embedding_provider": "siliconflow",
        "embedding_model": "BAAI/bge-m3",
        "preprocessing_version": "chunk-text-v1",
        "embedding_config_version": "retrieval-ablation-v1",
    }

    identity = engine.embedding_cache_identity(provider)
    digest = hashlib.sha256(json.dumps(expected, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()

    assert identity == expected
    assert engine.embedding_cache_identity(provider) == identity
    assert engine._cache_path(identity) == tmp_path / f"embeddings-{digest}.json"


def test_formal_engine_loads_warmup_cache_document_and_query_vectors(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    query = "alpha"
    chunks = _chunks(2)
    embedding = FakeEmbedding(fail=True)
    engine = _engine(tmp_path, formal_strict=True, chunks=chunks, embedding=embedding)
    identity = engine.embedding_cache_identity(embedding)
    query_key = hashlib.sha256(query.encode("utf-8")).hexdigest()
    payload = {
        "identity": identity,
        "document_ids": [chunk.chunk_id for chunk in chunks],
        "document_vectors": [[1.0, 0.0], [0.0, 1.0]],
        "query_vectors": {query_key: [1.0, 0.0]},
    }
    engine._cache_path(identity).write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    monkeypatch.setenv("ALLOW_BULK_REMOTE_EMBEDDING", "true")

    engine._load_embedding_cache(identity)
    results = asyncio.run(engine.search(query, strategy=RetrievalStrategy.R1, top_k=2))

    assert engine._document_vectors == payload["document_vectors"]
    assert engine._query_vectors == payload["query_vectors"]
    assert embedding.calls == []
    assert [item.chunk_id for item in results] == ["chunk-0", "chunk-1"]


def test_formal_cache_rejects_document_ordering_mismatch(tmp_path: Path) -> None:
    chunks = _chunks(2)
    engine = _engine(tmp_path, formal_strict=True, chunks=chunks)
    identity = engine.embedding_cache_identity()
    payload = {
        "identity": identity,
        "document_ids": ["chunk-1", "chunk-0"],
        "document_vectors": [[1.0, 0.0], [0.0, 1.0]],
        "query_vectors": {},
    }
    engine._cache_path(identity).write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")

    with pytest.raises(ProviderUnavailable, match="document ordering"):
        engine._load_embedding_cache(identity)


def test_formal_query_vector_is_saved_back_to_warmup_cache(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    query = "new formal query"
    chunks = _chunks(2)
    embedding = FakeEmbedding()
    engine = _engine(tmp_path, formal_strict=True, chunks=chunks, embedding=embedding)
    identity = engine.embedding_cache_identity(embedding)
    payload = {
        "identity": identity,
        "document_ids": [chunk.chunk_id for chunk in chunks],
        "document_vectors": [[1.0, 0.0], [0.0, 1.0]],
        "query_vectors": {},
    }
    cache_path = engine._cache_path(identity)
    cache_path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    monkeypatch.setenv("ALLOW_BULK_REMOTE_EMBEDDING", "true")

    asyncio.run(engine.search(query, strategy=RetrievalStrategy.R1, top_k=2))

    saved = json.loads(cache_path.read_text(encoding="utf-8"))
    query_key = hashlib.sha256(query.encode("utf-8")).hexdigest()
    assert embedding.calls == [[query]]
    assert saved["identity"] == identity
    assert saved["document_ids"] == [chunk.chunk_id for chunk in chunks]
    assert saved["document_vectors"] == payload["document_vectors"]
    assert saved["query_vectors"] == {query_key: [1.0, 0.0]}


def test_strict_provider_and_model_validation_precedes_provider_calls(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.setenv("ALLOW_BULK_REMOTE_EMBEDDING", "true")
    wrong_embedding = FakeEmbedding(name="local", model="other-embedding")
    embedding_engine = _engine(tmp_path / "embedding", formal_strict=True, embedding=wrong_embedding, persistent_cache=False)

    with pytest.raises(ProviderUnavailable, match="Formal R1/R2/R3 requires"):
        asyncio.run(embedding_engine.search("alpha", strategy=RetrievalStrategy.R1, top_k=2))
    assert wrong_embedding.calls == []

    wrong_reranker = FakeReranker(name="local", model="other-reranker")
    rerank_engine = _engine(tmp_path / "rerank", formal_strict=True, reranker=wrong_reranker, persistent_cache=False)
    with pytest.raises(ProviderUnavailable, match="Formal R3 requires"):
        asyncio.run(rerank_engine.search("alpha", strategy=RetrievalStrategy.R3, top_k=2))
    assert wrong_reranker.document_counts == []


def test_strict_embedding_uses_configured_batch_size(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.setenv("ALLOW_BULK_REMOTE_EMBEDDING", "true")
    embedding = FakeEmbedding()
    engine = _engine(
        tmp_path,
        formal_strict=True,
        persistent_cache=False,
        chunks=_chunks(5),
        embedding=embedding,
    )

    asyncio.run(engine.search("alpha", strategy=RetrievalStrategy.R1, top_k=2))

    assert [len(call) for call in embedding.calls] == [2, 2, 1, 1]


def test_strict_embedding_failure_propagates_while_ordinary_mode_falls_back(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.setenv("ALLOW_BULK_REMOTE_EMBEDDING", "true")
    strict = _engine(tmp_path / "strict", formal_strict=True, embedding=FakeEmbedding(fail=True), persistent_cache=False)
    ordinary = _engine(tmp_path / "ordinary", formal_strict=False, embedding=FakeEmbedding(fail=True))

    with pytest.raises(ProviderUnavailable, match="embedding unavailable"):
        asyncio.run(strict.search("alpha", strategy=RetrievalStrategy.R1, top_k=2))

    results = asyncio.run(ordinary.search("alpha", strategy=RetrievalStrategy.R1, top_k=2))
    assert len(results) == 2
    assert ordinary.actual_embedding_provider == "local"


def test_strict_reranker_failure_propagates_while_ordinary_mode_falls_back(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.setenv("ALLOW_BULK_REMOTE_EMBEDDING", "true")
    strict = _engine(tmp_path / "strict", formal_strict=True, reranker=FakeReranker(fail=True), persistent_cache=False)
    ordinary = _engine(tmp_path / "ordinary", formal_strict=False, reranker=FakeReranker(fail=True))

    with pytest.raises(ProviderUnavailable, match="reranker unavailable"):
        asyncio.run(strict.search("alpha", strategy=RetrievalStrategy.R3, top_k=2))

    results = asyncio.run(ordinary.search("alpha", strategy=RetrievalStrategy.R3, top_k=2))
    assert len(results) == 2
    assert ordinary.actual_reranker_provider == "local"


def test_strict_reranker_rejects_partial_scores(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ALLOW_BULK_REMOTE_EMBEDDING", "true")
    strict = _engine(
        tmp_path,
        formal_strict=True,
        reranker=FakeReranker(malformed=True),
        persistent_cache=False,
    )

    with pytest.raises(ProviderUnavailable, match="malformed or partial"):
        asyncio.run(strict.search("alpha", strategy=RetrievalStrategy.R3, top_k=2))


def test_formal_r3_uses_fixed_candidate_depth_and_ordinary_mode_remains_dynamic(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.setenv("ALLOW_BULK_REMOTE_EMBEDDING", "true")
    chunks = _chunks(20)
    strict_reranker = FakeReranker()
    ordinary_reranker = FakeReranker()
    strict = _engine(
        tmp_path / "strict",
        formal_strict=True,
        persistent_cache=False,
        chunks=chunks,
        reranker=strict_reranker,
        candidate_depth=5,
    )
    ordinary = _engine(
        tmp_path / "ordinary",
        formal_strict=False,
        chunks=chunks,
        reranker=ordinary_reranker,
        candidate_depth=5,
    )

    asyncio.run(strict.search("alpha", strategy=RetrievalStrategy.R3, top_k=4))
    asyncio.run(ordinary.search("alpha", strategy=RetrievalStrategy.R3, top_k=4))

    assert strict_reranker.document_counts == [5]
    assert ordinary_reranker.document_counts == [12]
    with pytest.raises(ProviderUnavailable, match="exceeds the fixed candidate depth"):
        asyncio.run(strict.search("alpha", strategy=RetrievalStrategy.R3, top_k=6))
