from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
STUDY_ROOT = Path(__file__).resolve().parent
BACKEND_ROOT = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from config import get_settings
from corpus import load_chunks
from providers.openai_compatible import ProviderUnavailable
from providers.siliconflow import SiliconFlowEmbeddingProvider
from retrieval.engine import RetrievalEngine


CONFIG_PATH = STUDY_ROOT / "retrieval_ablation_config.json"
PROTECTED_PATH = STUDY_ROOT / "protected_artifacts.json"
DEFAULT_CACHE_DIR = STUDY_ROOT / "cache"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def load_config() -> dict[str, Any]:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def preflight(config: dict[str, Any]) -> tuple[tuple[Any, ...], dict[str, Any]]:
    benchmark = PROJECT_ROOT / config["benchmark"]["path"]
    corpus = PROJECT_ROOT / config["corpus"]["path"]
    if not benchmark.exists() or sha256(benchmark) != config["benchmark"]["sha256"]:
        raise RuntimeError("frozen benchmark is missing or has the wrong hash")
    if not corpus.exists() or sha256(corpus) != config["corpus"]["sha256"]:
        raise RuntimeError("Corpus v1 is missing or has the wrong hash")
    chunks = load_chunks()
    if len(chunks) != 4461 or len({chunk.chunk_id for chunk in chunks}) != 4461:
        raise RuntimeError("Corpus v1 must contain exactly 4,461 unique chunks")
    stage1_dir = STUDY_ROOT / "formal_stage1"
    if stage1_dir.exists() and any(stage1_dir.iterdir()):
        raise RuntimeError("formal Stage 1 appears to have started")
    for item in json.loads(PROTECTED_PATH.read_text(encoding="utf-8"))["artifacts"]:
        path = PROJECT_ROOT / item["path"]
        if not path.exists() or sha256(path) != item["sha256"]:
            raise RuntimeError(f"protected Research A/B/C artifact changed: {item['path']}")
    strict = config["formal_strict"]
    if strict["embedding_model"] != "BAAI/bge-m3" or int(strict["embedding_batch_size"]) != 64:
        raise RuntimeError("formal embedding model or batch size does not match preregistration")
    if strict["preprocessing_version"] != "chunk-text-v1" or strict["embedding_config_version"] != "retrieval-ablation-v1":
        raise RuntimeError("formal cache identity configuration does not match preregistration")
    return chunks, {"benchmark_sha256": config["benchmark"]["sha256"], "corpus_sha256": config["corpus"]["sha256"]}


def _batch_path(batch_dir: Path, batch_index: int) -> Path:
    return batch_dir / f"batch-{batch_index:05d}.json"


def _validate_batch(path: Path, *, batch_index: int, expected_ids: list[str], identity: dict[str, str]) -> list[list[float]] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("identity") != identity or data.get("batch_index") != batch_index or data.get("chunk_ids") != expected_ids:
            return None
        vectors = [[float(value) for value in vector] for vector in data["vectors"]]
        RetrievalEngine._validate_vectors(vectors, len(expected_ids), expected_dimension=1024)
        return vectors
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None


async def _embed_with_retry(provider: SiliconFlowEmbeddingProvider, texts: list[str], *, max_attempts: int = 3) -> tuple[list[list[float]], int, int]:
    retries = 0
    failed_calls = 0
    for attempt in range(1, max_attempts + 1):
        try:
            vectors = await provider.embed(texts)
            RetrievalEngine._validate_vectors(vectors, len(texts), expected_dimension=1024)
            return vectors, retries, failed_calls
        except ProviderUnavailable as exc:
            failed_calls += 1
            transient = exc.error_type in {"timeout", "connectivity", "rate_limit", "http_5xx"}
            if not transient or attempt >= max_attempts:
                raise
            retries += 1
            await asyncio.sleep(float(2 ** (attempt - 1)))
    raise RuntimeError("unreachable")


async def warm(cache_dir: Path) -> dict[str, Any]:
    os.environ["TCM_CORPUS_MODE"] = "required"
    os.environ["ALLOW_BULK_REMOTE_EMBEDDING"] = "true"
    config = load_config()
    chunks, hashes = preflight(config)
    strict = config["formal_strict"]
    settings = get_settings()
    api_key = settings.embedding_api_key or settings.llm_api_key
    if not api_key:
        raise RuntimeError("No configured embedding/LLM API key is available")
    provider = SiliconFlowEmbeddingProvider(
        api_key=api_key,
        base_url=settings.embedding_base_url or settings.llm_base_url,
        model=strict["embedding_model"],
        timeout=120.0,
    )
    identity = {
        "corpus_sha256": hashes["corpus_sha256"],
        "embedding_provider": "siliconflow",
        "embedding_model": strict["embedding_model"],
        "preprocessing_version": strict["preprocessing_version"],
        "embedding_config_version": strict["embedding_config_version"],
    }
    cache_dir.mkdir(parents=True, exist_ok=True)
    batch_dir = cache_dir / "warmup_batches"
    batch_dir.mkdir(parents=True, exist_ok=True)
    batch_size = int(strict["embedding_batch_size"])
    total_batches = (len(chunks) + batch_size - 1) // batch_size
    vectors_by_batch: dict[int, list[list[float]]] = {}
    reused = 0
    newly_embedded = 0
    retries = 0
    failed_calls = 0
    embedding_calls = 0
    for batch_index, start in enumerate(range(0, len(chunks), batch_size)):
        batch_chunks = list(chunks[start : start + batch_size])
        ids = [chunk.chunk_id for chunk in batch_chunks]
        path = _batch_path(batch_dir, batch_index)
        existing = _validate_batch(path, batch_index=batch_index, expected_ids=ids, identity=identity) if path.exists() else None
        if existing is not None:
            vectors_by_batch[batch_index] = existing
            reused += len(existing)
            continue
        if path.exists():
            path.unlink()
        vectors, batch_retries, batch_failures = await _embed_with_retry(provider, [chunk.text for chunk in batch_chunks])
        embedding_calls += 1 + batch_retries
        retries += batch_retries
        failed_calls += batch_failures
        payload = {"identity": identity, "batch_index": batch_index, "start": start, "chunk_ids": ids, "vectors": vectors}
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
        temporary.replace(path)
        vectors_by_batch[batch_index] = vectors
        newly_embedded += len(vectors)
        print(json.dumps({"batch": batch_index + 1, "batches": total_batches, "chunks_embedded": newly_embedded, "reused": reused}), flush=True)

    ordered_vectors = [vector for index in range(total_batches) for vector in vectors_by_batch[index]]
    ordered_ids = [chunk.chunk_id for chunk in chunks]
    RetrievalEngine._validate_vectors(ordered_vectors, len(chunks), expected_dimension=1024)
    if ordered_ids != [chunk.chunk_id for chunk in chunks] or len(set(ordered_ids)) != len(ordered_ids):
        raise RuntimeError("final cache ordering or chunk identity invariant failed")
    cache_identity_hash = canonical_hash(identity)
    final_path = cache_dir / f"embeddings-{cache_identity_hash}.json"
    payload = {"identity": identity, "document_ids": ordered_ids, "document_vectors": ordered_vectors, "query_vectors": {}}
    temporary = final_path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    temporary.replace(final_path)
    report = {
        "status": "PASS",
        "scope": "formal_corpus_embedding_cache_warmup_only",
        "model": strict["embedding_model"],
        "corpus_sha256": hashes["corpus_sha256"],
        "corpus_chunks": len(chunks),
        "batch_size": batch_size,
        "batches": total_batches,
        "newly_embedded": newly_embedded,
        "reused": reused,
        "missing": 0,
        "duplicates": 0,
        "dimension": 1024,
        "all_finite": True,
        "ordering_valid": True,
        "cache_path": str(final_path),
        "cache_identity": identity,
        "cache_identity_sha256": cache_identity_hash,
        "embedding_provider_calls": embedding_calls,
        "retries": retries,
        "failed_calls": failed_calls,
        "reranker_calls": 0,
        "qwen_generation_calls": 0,
        "fallback": False,
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    (cache_dir / "cache_warmup_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    args = parser.parse_args()
    asyncio.run(warm(args.cache_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
