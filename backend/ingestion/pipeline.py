from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import re
from typing import Iterable

from corpus.models import KnowledgeChunk, SourceRecord


SUPPORTED_SUFFIXES = {".txt", ".md", ".json", ".jsonl", ".csv"}


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\x00", " ")).strip()


def deterministic_chunk_id(source_id: str, section: str, text: str) -> str:
    digest = hashlib.sha256(f"{source_id}\n{section}\n{normalize_text(text)}".encode("utf-8")).hexdigest()[:20]
    return f"tcm-chunk-{digest}"


def chunk_text(text: str, *, words_per_chunk: int = 180, overlap: int = 30) -> list[str]:
    words = normalize_text(text).split()
    if not words:
        return []
    step = max(1, words_per_chunk - overlap)
    return [" ".join(words[index:index + words_per_chunk]) for index in range(0, len(words), step) if words[index:index + words_per_chunk]]


def _records(path: Path) -> Iterable[tuple[str, str]]:
    if path.suffix.casefold() in {".txt", ".md"}:
        yield path.stem, path.read_text(encoding="utf-8")
    elif path.suffix.casefold() == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        values = data if isinstance(data, list) else [data]
        for index, item in enumerate(values):
            yield str(item.get("section", index)), str(item.get("text", item.get("content", "")))
    elif path.suffix.casefold() == ".jsonl":
        for index, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
            item = json.loads(line)
            yield str(item.get("section", index)), str(item.get("text", item.get("content", "")))
    elif path.suffix.casefold() == ".csv":
        with path.open(newline="", encoding="utf-8-sig") as handle:
            for index, item in enumerate(csv.DictReader(handle)):
                yield str(item.get("section", index)), str(item.get("text", item.get("content", "")))


def build_corpus_from_directory(input_dir: Path, source_registry: dict[str, SourceRecord]) -> tuple[list[KnowledgeChunk], list[str]]:
    chunks: list[KnowledgeChunk] = []
    issues: list[str] = []
    seen_hashes: set[str] = set()
    for path in sorted(input_dir.rglob("*")):
        if not path.is_file() or path.suffix.casefold() not in SUPPORTED_SUFFIXES:
            continue
        source_id = path.stem.split("__", 1)[0]
        if source_id not in source_registry:
            issues.append(f"{path.name}: source_id {source_id!r} is not registered")
            continue
        for section, raw in _records(path):
            for part in chunk_text(raw):
                content_hash = hashlib.sha256(normalize_text(part).encode("utf-8")).hexdigest()
                if content_hash in seen_hashes:
                    issues.append(f"{path.name}: duplicate content skipped")
                    continue
                seen_hashes.add(content_hash)
                chunks.append(KnowledgeChunk(
                    chunk_id=deterministic_chunk_id(source_id, section, part),
                    source_id=source_id,
                    source_ids=[source_id],
                    section=section,
                    text=part,
                    human_review_status="needs_human_review",
                ))
    return chunks, issues


def corpus_manifest(sources: dict[str, SourceRecord], chunks: list[KnowledgeChunk]) -> dict[str, object]:
    canonical = json.dumps([chunk.model_dump(mode="json") for chunk in chunks], ensure_ascii=False, sort_keys=True)
    return {
        "schema_version": "1.0.0",
        "corpus_version": f"researcher-{hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:12]}",
        "source_count": len(sources),
        "chunk_count": len(chunks),
        "reviewed_chunk_count": sum(chunk.human_review_status == "verified" for chunk in chunks),
        "source_type_warning": "Source-type labels do not imply equal scientific strength.",
    }
