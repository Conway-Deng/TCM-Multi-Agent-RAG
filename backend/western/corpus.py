from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from .models import WesternKnowledgeChunk, WesternSourceRecord
from .validation import validate_corpus_files


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CORPUS_ROOT = PROJECT_ROOT / "research" / "corpus" / "west_v0_1"


class WesternCorpusError(RuntimeError):
    pass


@dataclass(frozen=True)
class WesternRuntimeCorpus:
    root: Path
    sources: dict[str, WesternSourceRecord]
    chunks: tuple[WesternKnowledgeChunk, ...]
    manifest: dict[str, Any]
    validation: dict[str, Any]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def active_corpus_root(configured_path: str | Path | None = None) -> Path:
    configured = str(configured_path or os.getenv("WESTERN_CORPUS_PATH", "")).strip()
    if not configured:
        return DEFAULT_CORPUS_ROOT
    path = Path(configured)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.parent if path.name == "chunks.jsonl" else path


def load_sources(root: Path = DEFAULT_CORPUS_ROOT) -> dict[str, WesternSourceRecord]:
    payload = json.loads((root / "source_registry.json").read_text(encoding="utf-8"))
    records = [WesternSourceRecord.model_validate(item) for item in payload]
    return {item.source_id: item for item in records}


def load_chunks(root: Path = DEFAULT_CORPUS_ROOT) -> tuple[WesternKnowledgeChunk, ...]:
    path = root / "chunks.jsonl"
    return tuple(
        WesternKnowledgeChunk.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )


@lru_cache(maxsize=4)
def _load_runtime_cached(
    root_string: str,
    source_size: int,
    source_modified_ns: int,
    chunks_size: int,
    chunks_modified_ns: int,
    manifest_size: int,
    manifest_modified_ns: int,
) -> WesternRuntimeCorpus:
    del source_size, source_modified_ns, chunks_size, chunks_modified_ns, manifest_size, manifest_modified_ns
    root = Path(root_string)
    validation = validate_corpus_files(root)
    if not validation["valid"]:
        details = "; ".join(validation["errors"][:5])
        raise WesternCorpusError(f"Western pilot corpus validation failed: {details}")
    try:
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        sources = load_sources(root)
        chunks = load_chunks(root)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise WesternCorpusError(f"Western pilot corpus could not be loaded: {type(exc).__name__}") from None
    if manifest.get("corpus_version") != "medirag-west-v0.1-pilot":
        raise WesternCorpusError("Western pilot manifest has an unsupported corpus version")
    if manifest.get("source_registry_sha256") != sha256_file(root / "source_registry.json"):
        raise WesternCorpusError("Western pilot source registry hash does not match its manifest")
    if manifest.get("chunks_sha256") != sha256_file(root / "chunks.jsonl"):
        raise WesternCorpusError("Western pilot chunks hash does not match its manifest")
    if manifest.get("source_count") != len(sources) or manifest.get("chunk_count") != len(chunks):
        raise WesternCorpusError("Western pilot manifest counts do not match loaded artifacts")
    return WesternRuntimeCorpus(root=root, sources=sources, chunks=chunks, manifest=manifest, validation=validation)


def load_runtime_corpus(configured_path: str | Path | None = None) -> WesternRuntimeCorpus:
    root = active_corpus_root(configured_path).resolve()
    required = [root / "source_registry.json", root / "chunks.jsonl", root / "manifest.json"]
    missing = [path.name for path in required if not path.is_file()]
    if missing:
        raise WesternCorpusError(f"Western pilot corpus is missing required artifact(s): {', '.join(missing)}")
    source_stat, chunks_stat, manifest_stat = (path.stat() for path in required)
    return _load_runtime_cached(
        str(root),
        source_stat.st_size, source_stat.st_mtime_ns,
        chunks_stat.st_size, chunks_stat.st_mtime_ns,
        manifest_stat.st_size, manifest_stat.st_mtime_ns,
    )


def clear_runtime_cache() -> None:
    _load_runtime_cached.cache_clear()


def western_corpus_stats(configured_path: str | Path | None = None) -> dict[str, Any]:
    corpus = load_runtime_corpus(configured_path)
    topics = sorted({topic for chunk in corpus.chunks for topic in chunk.topics})
    return {
        "corpus_name": "MediRAG-West v0.1 pilot",
        "corpus_version": corpus.manifest["corpus_version"],
        "source_count": len(corpus.sources),
        "chunk_count": len(corpus.chunks),
        "topics": topics,
        "topic_count": len(topics),
        "validation_errors": list(corpus.validation["errors"]),
        "validation_warnings": list(corpus.validation["warnings"]),
        "retrieval_strategy": "R0 lexical",
        "scientific_status": "limited four-topic research pilot; not clinically comprehensive or medical advice",
    }


def write_sources(path: Path, sources: list[WesternSourceRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [item.model_dump(mode="json") for item in sorted(sources, key=lambda item: item.source_id)]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_chunks(path: Path, chunks: list[WesternKnowledgeChunk]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(chunks, key=lambda item: item.chunk_id)
    path.write_text(
        "".join(json.dumps(item.model_dump(mode="json"), ensure_ascii=False, sort_keys=True) + "\n" for item in ordered),
        encoding="utf-8",
    )
