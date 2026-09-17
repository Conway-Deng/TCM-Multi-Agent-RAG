from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from pydantic import ValidationError

from .models import WesternKnowledgeChunk, WesternSourceRecord


def _valid_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc)


def validate_records(
    sources: list[WesternSourceRecord],
    chunks: list[WesternKnowledgeChunk],
    *,
    parse_errors: list[str] | None = None,
) -> dict[str, Any]:
    errors = list(parse_errors or [])
    warnings: list[str] = []

    source_counts = Counter(item.source_id for item in sources)
    chunk_counts = Counter(item.chunk_id for item in chunks)
    errors.extend(f"duplicate source_id: {key}" for key, count in source_counts.items() if count > 1)
    errors.extend(f"duplicate chunk_id: {key}" for key, count in chunk_counts.items() if count > 1)
    known_sources = set(source_counts)

    for source in sources:
        if not _valid_url(source.source_url):
            errors.append(f"{source.source_id}: missing or invalid source URL")
        if not source.pmcid:
            errors.append(f"{source.source_id}: missing PMCID")
        if not source.license.strip():
            errors.append(f"{source.source_id}: missing license information")
        if not source.topics:
            errors.append(f"{source.source_id}: missing topic assignment")
        if not source.doi:
            warnings.append(f"{source.source_id}: DOI unavailable in PMC metadata")
        if not source.license_url:
            warnings.append(f"{source.source_id}: license URL unavailable in PMC metadata")

    for chunk in chunks:
        if chunk.source_id not in known_sources:
            errors.append(f"{chunk.chunk_id}: unknown source_id {chunk.source_id}")
        if not chunk.text.strip():
            errors.append(f"{chunk.chunk_id}: empty chunk text")
        if not chunk.topics:
            errors.append(f"{chunk.chunk_id}: missing topic assignment")
        if chunk.domain != "western":
            errors.append(f"{chunk.chunk_id}: invalid domain {chunk.domain!r}")
        if not _valid_url(chunk.source_url):
            errors.append(f"{chunk.chunk_id}: missing or invalid source URL")

    return {
        "report_name": "MediRAG-West v0.1 Pilot Validation Report",
        "valid": not errors,
        "errors": sorted(set(errors)),
        "warnings": sorted(set(warnings)),
        "source_count": len(sources),
        "chunk_count": len(chunks),
        "source_type_counts": dict(sorted(Counter(item.source_type for item in sources).items())),
        "license_counts": dict(sorted(Counter(item.license for item in sources).items())),
        "topic_chunk_counts": dict(sorted(Counter(topic for item in chunks for topic in item.topics).items())),
        "scientific_status": "pilot retrieval corpus; not clinically validated",
    }


def validate_corpus_files(root: Path) -> dict[str, Any]:
    parse_errors: list[str] = []
    sources: list[WesternSourceRecord] = []
    chunks: list[WesternKnowledgeChunk] = []

    try:
        payload = json.loads((root / "source_registry.json").read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError("source_registry.json must contain a list")
        for index, item in enumerate(payload, 1):
            try:
                sources.append(WesternSourceRecord.model_validate(item))
            except ValidationError as exc:
                parse_errors.append(f"source_registry.json record {index}: {exc.errors()[0]['msg']}")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parse_errors.append(f"source_registry.json malformed: {type(exc).__name__}")

    try:
        for line_number, line in enumerate((root / "chunks.jsonl").read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                chunks.append(WesternKnowledgeChunk.model_validate_json(line))
            except (ValidationError, ValueError, json.JSONDecodeError) as exc:
                parse_errors.append(f"chunks.jsonl line {line_number}: malformed {type(exc).__name__}")
    except OSError as exc:
        parse_errors.append(f"chunks.jsonl unreadable: {type(exc).__name__}")

    return validate_records(sources, chunks, parse_errors=parse_errors)
