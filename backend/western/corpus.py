from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .models import WesternKnowledgeChunk, WesternSourceRecord


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CORPUS_ROOT = PROJECT_ROOT / "research" / "corpus" / "west_v0_1"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
