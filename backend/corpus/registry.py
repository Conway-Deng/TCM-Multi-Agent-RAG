from __future__ import annotations

from functools import lru_cache
import hashlib
import json
from pathlib import Path

from tcm.knowledge_base import KNOWLEDGE_BASE, SOURCE_REGISTRY

from .models import KnowledgeChunk, SourceRecord


DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def _source_type(raw: str) -> str:
    mapping = {
        "terminology_standard": "professional_standard",
        "educational_textbook_summary": "educational_reference",
        "safety_information": "researcher_added_source",
    }
    return mapping.get(raw, "researcher_added_source")


@lru_cache(maxsize=1)
def load_sources() -> dict[str, SourceRecord]:
    return {
        item.source_id: SourceRecord(
            source_id=item.source_id,
            title=item.title,
            author_or_organization=item.organization,
            source_type=_source_type(item.source_type),
            publication_year=item.year,
            url_or_reference=item.url_or_identifier,
            license_or_access_note=item.license_or_usage_note,
            evidence_category="terminology_standard" if "terminology" in item.source_type else "traditional_educational",
            review_status="needs_human_review" if item.verification_status != "verified" else "verified",
            notes=item.section,
        )
        for item in SOURCE_REGISTRY.values()
    }


@lru_cache(maxsize=1)
def load_chunks() -> tuple[KnowledgeChunk, ...]:
    chunks: list[KnowledgeChunk] = []
    for entry in KNOWLEDGE_BASE:
        examples = [str(example.get("name", {}).get("en", "")) for example in entry.educational_examples]
        example_text = "\n".join(
            " ".join(
                filter(None, [
                    str(example.get("name", {}).get("en", "")),
                    str(example.get("description", {}).get("en", "")),
                    str(example.get("warning", {}).get("en", "")),
                ])
            )
            for example in entry.educational_examples
        )
        text = "\n".join(
            [
                entry.title("en"), entry.pattern["en"], entry.rationale["en"],
                entry.title("zh"), entry.pattern["zh"], entry.rationale["zh"],
                entry.title("ko"), entry.pattern["ko"], entry.rationale["ko"],
                example_text,
            ]
        )
        chunks.append(
            KnowledgeChunk(
                chunk_id=entry.entry_id,
                source_id=entry.source_ids[0],
                source_ids=list(entry.source_ids),
                section=entry.subtopic,
                text=text,
                topics=list(dict.fromkeys([entry.topic, *entry.tags])),
                syndromes=[entry.pattern["en"], entry.pattern["zh"], entry.pattern["ko"]],
                herbs=examples,
                meridians=[tag for tag in entry.tags if "meridian" in tag],
                constitution_tags=[tag for tag in entry.tags if "constitution" in tag or "deficiency" in tag],
                dietary_tags=[tag for tag in entry.tags if tag in {"digestion", "food_stagnation"}],
                lifestyle_tags=[tag for tag in entry.tags if tag in {"sleep", "stress", "fatigue"}],
                safety_tags=list(entry.safety_notes["en"]),
                human_review_status=entry.review_status,
                keywords=list(dict.fromkeys([*entry.keywords["en"], *entry.keywords["zh"], *entry.keywords["ko"]])),
            )
        )
    return tuple(chunks)


def corpus_version() -> str:
    digest = hashlib.sha256()
    for path in sorted(DATA_DIR.glob("tcm_*.json")):
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
    return f"tcm-{digest.hexdigest()[:12]}"


def validate_corpus() -> list[str]:
    issues: list[str] = []
    sources = load_sources()
    seen: set[str] = set()
    for chunk in load_chunks():
        if chunk.chunk_id in seen:
            issues.append(f"duplicate chunk_id: {chunk.chunk_id}")
        seen.add(chunk.chunk_id)
        for source_id in chunk.source_ids:
            if source_id not in sources:
                issues.append(f"{chunk.chunk_id}: unknown source_id {source_id}")
        if not chunk.text.strip():
            issues.append(f"{chunk.chunk_id}: empty text")
    return issues


def corpus_stats() -> dict[str, object]:
    chunks = load_chunks()
    sources = load_sources()
    return {
        "corpus_version": corpus_version(),
        "source_count": len(sources),
        "chunk_count": len(chunks),
        "reviewed_source_count": sum(item.review_status == "verified" for item in sources.values()),
        "reviewed_chunk_count": sum(item.human_review_status == "verified" for item in chunks),
        "languages": ["en", "zh", "ko"],
        "validation_issues": validate_corpus(),
        "scientific_status": "small provisional educational corpus; not clinically validated",
    }
