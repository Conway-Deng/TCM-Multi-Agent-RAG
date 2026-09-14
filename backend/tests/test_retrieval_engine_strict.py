from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import inspect
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


def _warmup_module():
    path = BACKEND.parent / "research/retrieval_ablation/warm_formal_cache.py"
    spec = importlib.util.spec_from_file_location("retrieval_warmup_memory_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _configure_mock_warmup(
    monkeypatch: pytest.MonkeyPatch,
    warmer,
    chunks: tuple[SimpleNamespace, ...],
    *,
    batch_size: int = 2,
) -> dict[str, str]:
    config = {
        "formal_strict": {
            "embedding_provider": "siliconflow",
            "embedding_model": "BAAI/bge-m3",
            "embedding_batch_size": batch_size,
            "preprocessing_version": "chunk-text-v1",
            "embedding_config_version": "retrieval-ablation-v1",
        },
    }
    identity = {
        "corpus_sha256": "corpus-sha",
        "embedding_provider": "siliconflow",
        "embedding_model": "BAAI/bge-m3",
        "preprocessing_version": "chunk-text-v1",
        "embedding_config_version": "retrieval-ablation-v1",
    }
    settings = SimpleNamespace(
        embedding_api_key="offline-key",
        llm_api_key="",
        embedding_base_url="https://offline.invalid",
        llm_base_url="",
    )
    provider = object()
    next_vector = 0

    async def embed_batch(actual_provider, texts: list[str], *, max_attempts: int = 3):
        nonlocal next_vector
        assert actual_provider is provider
        assert max_attempts == 3
        vectors = []
        for _ in texts:
            vectors.append([float(next_vector)] + [0.0] * 1023)
            next_vector += 1
        return vectors, 0, 0

    monkeypatch.setenv("TCM_CORPUS_MODE", "offline-test-placeholder")
    monkeypatch.setenv("ALLOW_BULK_REMOTE_EMBEDDING", "offline-test-placeholder")
    monkeypatch.setattr(warmer, "load_config", lambda: config)
    monkeypatch.setattr(warmer, "preflight", lambda _config: (chunks, {
        "benchmark_sha256": "benchmark-sha", "corpus_sha256": "corpus-sha",
    }))
    monkeypatch.setattr(warmer, "get_settings", lambda: settings)
    monkeypatch.setattr(warmer, "SiliconFlowEmbeddingProvider", lambda **_kwargs: provider)
    monkeypatch.setattr(warmer, "_embed_with_retry", embed_batch)
    return identity


def _write_warmup_batches(
    engine: RetrievalEngine,
    identity: dict[str, str],
    *,
    vectors: list[list[float]] | None = None,
) -> list[list[float]]:
    batch_dir = engine.cache_dir / "warmup_batches"
    batch_dir.mkdir(parents=True)
    document_vectors = vectors or [
        [float(index)] + [0.0] * 1023
        for index in range(len(engine.chunks))
    ]
    for batch_index, start in enumerate(range(0, len(engine.chunks), engine.embedding_batch_size)):
        batch_chunks = engine.chunks[start : start + engine.embedding_batch_size]
        (batch_dir / f"batch-{batch_index:05d}.json").write_text(
            json.dumps({
                "identity": identity,
                "batch_index": batch_index,
                "start": start,
                "chunk_ids": [chunk.chunk_id for chunk in batch_chunks],
                "vectors": document_vectors[start : start + len(batch_chunks)],
            }, separators=(",", ":")),
            encoding="utf-8",
        )
    return document_vectors


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
    assert engine._query_cache_path(identity) == tmp_path / f"query-vectors-{digest}.json"


def test_warmup_streams_batches_into_the_unchanged_cache_schema(tmp_path: Path) -> None:
    warmer = _warmup_module()
    chunks = _chunks(6)
    identity = {
        "corpus_sha256": "corpus-sha",
        "embedding_provider": "siliconflow",
        "embedding_model": "BAAI/bge-m3",
        "preprocessing_version": "chunk-text-v1",
        "embedding_config_version": "retrieval-ablation-v1",
    }
    batch_dir = tmp_path / "batches"
    batch_dir.mkdir()
    expected_vectors: list[list[float]] = []
    batch_size = 2
    for batch_index, start in enumerate(range(0, len(chunks), batch_size)):
        batch_chunks = chunks[start : start + batch_size]
        vectors = [[float(start + offset)] * 1024 for offset in range(len(batch_chunks))]
        expected_vectors.extend(vectors)
        warmer._batch_path(batch_dir, batch_index).write_text(
            json.dumps({
                "identity": identity,
                "batch_index": batch_index,
                "start": start,
                "chunk_ids": [chunk.chunk_id for chunk in batch_chunks],
                "vectors": vectors,
            }, separators=(",", ":")),
            encoding="utf-8",
        )

    final_path = tmp_path / "embeddings.json"
    warmer._stream_final_cache(
        final_path,
        batch_dir=batch_dir,
        chunks=chunks,
        identity=identity,
        batch_size=batch_size,
        total_batches=3,
    )

    data = json.loads(final_path.read_text(encoding="utf-8"))
    assert list(data) == ["identity", "document_ids", "document_vectors", "query_vectors"]
    assert data["identity"] == identity
    assert data["document_ids"] == [chunk.chunk_id for chunk in chunks]
    assert data["document_vectors"] == expected_vectors
    assert data["query_vectors"] == {}
    source = inspect.getsource(warmer.warm)
    assert "vectors_by_batch" not in source
    assert "ordered_vectors" not in source


def test_sharded_warmup_skips_legacy_final_cache_and_reports_authoritative_batches(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    warmer = _warmup_module()
    chunks = _chunks(5)
    identity = _configure_mock_warmup(monkeypatch, warmer, chunks)
    monkeypatch.setattr(
        warmer,
        "_stream_final_cache",
        lambda *_args, **_kwargs: pytest.fail("sharded warmup must not build the legacy final cache"),
    )

    report = asyncio.run(warmer.warm(tmp_path, build_legacy_final_cache=False))

    batch_dir = tmp_path / "warmup_batches"
    assert report["status"] == "PASS"
    assert report["storage"] == "sharded_batches"
    assert report["cache_path"] == str(batch_dir)
    assert report["cache_identity"] == identity
    assert report["corpus_chunks"] == len(chunks)
    assert report["batch_size"] == 2
    assert report["batches"] == 3
    assert report["dimension"] == 1024
    assert report["all_finite"] is True
    assert report["ordering_valid"] is True
    assert report["missing"] == report["duplicates"] == 0
    assert report["model"] == "BAAI/bge-m3"
    assert report["embedding_provider"] == "siliconflow"
    assert report["embedding_model"] == "BAAI/bge-m3"
    assert report["embedding_provider_calls"] == 3
    assert not list(tmp_path.glob("embeddings-*.json"))
    assert [path.name for path in sorted(batch_dir.glob("batch-*.json"))] == [
        "batch-00000.json", "batch-00001.json", "batch-00002.json",
    ]
    first_values: list[float] = []
    for batch_index, start in enumerate(range(0, len(chunks), 2)):
        expected_ids = [chunk.chunk_id for chunk in chunks[start : start + 2]]
        vectors = warmer._validate_batch(
            warmer._batch_path(batch_dir, batch_index),
            batch_index=batch_index,
            expected_ids=expected_ids,
            identity=identity,
        )
        assert vectors is not None
        first_values.extend(vector[0] for vector in vectors)
    assert first_values == list(map(float, range(len(chunks))))


def test_warmup_default_still_builds_legacy_monolithic_cache(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    warmer = _warmup_module()
    chunks = _chunks(3)
    identity = _configure_mock_warmup(monkeypatch, warmer, chunks)
    calls: list[dict[str, object]] = []

    def stream_final_cache(final_path: Path, **kwargs) -> None:
        calls.append({"final_path": final_path, **kwargs})
        final_path.write_text("legacy-cache", encoding="utf-8")

    monkeypatch.setattr(warmer, "_stream_final_cache", stream_final_cache)

    report = asyncio.run(warmer.warm(tmp_path))

    expected_path = tmp_path / f"embeddings-{warmer.canonical_hash(identity)}.json"
    assert len(calls) == 1
    assert calls[0]["final_path"] == expected_path
    assert calls[0]["batch_dir"] == tmp_path / "warmup_batches"
    assert expected_path.read_text(encoding="utf-8") == "legacy-cache"
    assert report["cache_path"] == str(expected_path)
    assert "storage" not in report


def test_warmup_finalization_holds_only_one_validated_batch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    warmer = _warmup_module()
    chunks = _chunks(40)

    class TrackedBatch(list):
        live = 0
        maximum_live = 0

        def __init__(self) -> None:
            super().__init__([[1.0, 0.0]])
            type(self).live += 1
            type(self).maximum_live = max(type(self).maximum_live, type(self).live)

        def __del__(self) -> None:
            type(self).live -= 1

    def validated_batch(_path: Path, *, batch_index: int, expected_ids: list[str], identity: dict[str, str]):
        assert expected_ids == [f"chunk-{batch_index}"]
        assert identity == {"cache": "identity"}
        return TrackedBatch()

    monkeypatch.setattr(warmer, "_validate_batch", validated_batch)
    final_path = tmp_path / "bounded.json"
    warmer._stream_final_cache(
        final_path,
        batch_dir=tmp_path,
        chunks=chunks,
        identity={"cache": "identity"},
        batch_size=1,
        total_batches=len(chunks),
    )

    assert TrackedBatch.maximum_live == 1
    assert TrackedBatch.live == 0


def test_warmup_streaming_rejects_invalid_batch_without_replacing_final_cache(tmp_path: Path) -> None:
    warmer = _warmup_module()
    chunks = _chunks(1)
    identity = {"cache": "identity"}
    batch_dir = tmp_path / "batches"
    batch_dir.mkdir()
    warmer._batch_path(batch_dir, 0).write_text(
        json.dumps({
            "identity": identity,
            "batch_index": 0,
            "start": 0,
            "chunk_ids": [chunks[0].chunk_id],
            "vectors": [[0.0] * 1023],
        }, separators=(",", ":")),
        encoding="utf-8",
    )
    final_path = tmp_path / "embeddings.json"
    final_path.write_text("previous-valid-cache", encoding="utf-8")

    with pytest.raises(ProviderUnavailable, match="dimension mismatch"):
        warmer._stream_final_cache(
            final_path,
            batch_dir=batch_dir,
            chunks=chunks,
            identity=identity,
            batch_size=1,
            total_batches=1,
        )

    assert final_path.read_text(encoding="utf-8") == "previous-valid-cache"
    assert not final_path.with_suffix(".tmp").exists()


def test_strict_loader_reconstructs_batches_in_order_and_loads_query_sidecar(tmp_path: Path) -> None:
    chunks = _chunks(5)
    engine = _engine(tmp_path, formal_strict=True, chunks=chunks)
    identity = engine.embedding_cache_identity()
    expected_vectors = _write_warmup_batches(engine, identity)
    query_vector = [1.0] + [0.0] * 1023
    engine._query_cache_path(identity).write_text(json.dumps({
        "identity": identity,
        "query_vectors": {"cached-query": query_vector},
    }, separators=(",", ":")), encoding="utf-8")

    engine._load_embedding_cache(identity)

    assert not engine._cache_path(identity).exists()
    assert len(engine._document_vectors or []) == len(chunks)
    assert engine._document_vectors == expected_vectors
    assert [vector[0] for vector in engine._document_vectors or []] == list(map(float, range(len(chunks))))
    assert engine._query_vectors == {"cached-query": query_vector}


@pytest.mark.parametrize(
    ("field", "value", "message"),
    (
        ("identity", {"wrong": "identity"}, "identity mismatch"),
        ("batch_index", 99, "index mismatch"),
        ("chunk_ids", ["wrong-chunk"], "document ordering mismatch"),
    ),
)
def test_strict_loader_rejects_wrong_batch_metadata(
    tmp_path: Path, field: str, value: object, message: str,
) -> None:
    engine = _engine(tmp_path, formal_strict=True, chunks=_chunks(1))
    identity = engine.embedding_cache_identity()
    _write_warmup_batches(engine, identity)
    path = engine.cache_dir / "warmup_batches/batch-00000.json"
    batch = json.loads(path.read_text(encoding="utf-8"))
    batch[field] = value
    path.write_text(json.dumps(batch, separators=(",", ":")), encoding="utf-8")

    with pytest.raises(ProviderUnavailable, match=message):
        engine._load_embedding_cache(identity)


@pytest.mark.parametrize(
    ("vector", "message"),
    (
        ([0.0] * 1023, "dimension mismatch"),
        ([math.nan] + [0.0] * 1023, "non-finite"),
    ),
)
def test_strict_loader_rejects_invalid_batch_vectors(
    tmp_path: Path, vector: list[float], message: str,
) -> None:
    engine = _engine(tmp_path, formal_strict=True, chunks=_chunks(1))
    identity = engine.embedding_cache_identity()
    _write_warmup_batches(engine, identity, vectors=[vector])

    with pytest.raises(ProviderUnavailable, match=message):
        engine._load_embedding_cache(identity)


def test_strict_loader_decodes_only_one_batch_at_a_time(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    chunks = _chunks(8)
    engine = _engine(tmp_path, formal_strict=True, chunks=chunks)
    identity = engine.embedding_cache_identity()
    expected_vectors = [[float(index)] + [0.0] * 1023 for index in range(len(chunks))]
    _write_warmup_batches(engine, identity, vectors=expected_vectors)
    original_loads = engine_module.json.loads

    class TrackedBatch(list):
        live = 0
        maximum_live = 0

        def __init__(self, values: list[list[float]]) -> None:
            super().__init__(values)
            type(self).live += 1
            type(self).maximum_live = max(type(self).maximum_live, type(self).live)

        def __del__(self) -> None:
            type(self).live -= 1

    def tracked_loads(value: str):
        data = original_loads(value)
        if "vectors" in data:
            data["vectors"] = TrackedBatch(data["vectors"])
        return data

    monkeypatch.setattr(engine_module.json, "loads", tracked_loads)
    engine._load_embedding_cache(identity)

    assert len(engine._document_vectors or []) == len(chunks)
    assert TrackedBatch.maximum_live == 1
    assert TrackedBatch.live == 0


def test_legacy_final_cache_reuses_parsed_document_matrix_without_copy(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    engine = _engine(tmp_path, formal_strict=True, chunks=_chunks(2))
    identity = engine.embedding_cache_identity()
    document_vectors = [[1.0, 0.0], [0.0, 1.0]]
    payload = {
        "identity": identity,
        "document_ids": [chunk.chunk_id for chunk in engine.chunks],
        "document_vectors": document_vectors,
        "query_vectors": {},
    }
    engine._cache_path(identity).write_text("legacy-cache", encoding="utf-8")
    monkeypatch.setattr(engine_module.json, "loads", lambda _value: payload)

    engine._load_embedding_cache(identity)

    assert engine._document_vectors is document_vectors


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


def test_formal_query_vector_uses_identity_sidecar_without_rewriting_document_cache(
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
    original_document_cache = cache_path.read_bytes()
    monkeypatch.setenv("ALLOW_BULK_REMOTE_EMBEDDING", "true")

    asyncio.run(engine.search(query, strategy=RetrievalStrategy.R1, top_k=2))

    query_key = hashlib.sha256(query.encode("utf-8")).hexdigest()
    sidecar_path = engine._query_cache_path(identity)
    saved = json.loads(sidecar_path.read_text(encoding="utf-8"))
    assert embedding.calls == [[query]]
    assert cache_path.read_bytes() == original_document_cache
    assert saved == {"identity": identity, "query_vectors": {query_key: [1.0, 0.0]}}
    assert not sidecar_path.with_suffix(".tmp").exists()

    reloaded_embedding = FakeEmbedding(fail=True)
    reloaded = _engine(tmp_path, formal_strict=True, chunks=chunks, embedding=reloaded_embedding)
    reloaded._load_embedding_cache(identity)
    results = asyncio.run(reloaded.search(query, strategy=RetrievalStrategy.R1, top_k=2))
    assert len(results) == 2
    assert reloaded_embedding.calls == []


def test_formal_query_sidecar_ignores_mismatched_identity(tmp_path: Path) -> None:
    chunks = _chunks(2)
    engine = _engine(tmp_path, formal_strict=True, chunks=chunks)
    identity = engine.embedding_cache_identity()
    engine._cache_path(identity).write_text(json.dumps({
        "identity": identity,
        "document_ids": [chunk.chunk_id for chunk in chunks],
        "document_vectors": [[1.0, 0.0], [0.0, 1.0]],
        "query_vectors": {},
    }, separators=(",", ":")), encoding="utf-8")
    engine._query_cache_path(identity).write_text(json.dumps({
        "identity": {**identity, "corpus_sha256": "wrong-corpus"},
        "query_vectors": {"not-compatible": [1.0, 0.0]},
    }, separators=(",", ":")), encoding="utf-8")

    engine._load_embedding_cache(identity)

    assert engine._query_vectors == {}


def test_formal_query_sidecar_validates_document_dimension(tmp_path: Path) -> None:
    chunks = _chunks(2)
    engine = _engine(tmp_path, formal_strict=True, chunks=chunks)
    identity = engine.embedding_cache_identity()
    engine._cache_path(identity).write_text(json.dumps({
        "identity": identity,
        "document_ids": [chunk.chunk_id for chunk in chunks],
        "document_vectors": [[1.0, 0.0], [0.0, 1.0]],
        "query_vectors": {},
    }, separators=(",", ":")), encoding="utf-8")
    engine._query_cache_path(identity).write_text(json.dumps({
        "identity": identity,
        "query_vectors": {"wrong-dimension": [1.0, 0.0, 0.0]},
    }, separators=(",", ":")), encoding="utf-8")

    with pytest.raises(ProviderUnavailable, match="dimension mismatch"):
        engine._load_embedding_cache(identity)


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
