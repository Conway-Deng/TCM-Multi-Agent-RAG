from __future__ import annotations

from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path

from tcm.knowledge_base import KNOWLEDGE_BASE, SOURCE_REGISTRY

from .models import KnowledgeChunk, SourceRecord
from .v1_models import ResearchChunk


DATA_DIR = Path(__file__).resolve().parents[1] / "data"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_V1_PATH = PROJECT_ROOT / "research" / "corpus" / "tcm_v1" / "chunks.jsonl"
DEFAULT_V1_MANIFEST = PROJECT_ROOT / "research" / "corpus" / "manifests" / "tcm_v1_manifest.json"


def active_v1_path() -> Path | None:
    mode = os.getenv("TCM_CORPUS_MODE", "v1_if_available").strip().casefold()
    if mode in {"legacy", "fixture", "provisional"}:
        return None
    configured = os.getenv("TCM_CORPUS_PATH", "").strip()
    path = Path(configured) if configured else DEFAULT_V1_PATH
    if path.exists():
        return path
    if mode in {"v1", "required"}:
        raise FileNotFoundError(f"TCM Corpus v1 is required but not built: {path}")
    return None


@lru_cache(maxsize=1)
def _v1_chunks() -> tuple[ResearchChunk, ...]:
    path = active_v1_path()
    if path is None:
        return ()
    return tuple(ResearchChunk.model_validate_json(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def _source_type(raw: str) -> str:
    mapping = {
        "terminology_standard": "professional_standard",
        "educational_textbook_summary": "educational_reference",
        "safety_information": "researcher_added_source",
    }
    return mapping.get(raw, "researcher_added_source")


@lru_cache(maxsize=1)
def load_sources() -> dict[str, SourceRecord]:
    v1 = _v1_chunks()
    if v1:
        sources: dict[str, SourceRecord] = {}
        for item in v1:
            if item.source_id in sources:
                continue
            sources[item.source_id] = SourceRecord(
                source_id=item.source_id,
                title=item.source_title,
                author_or_organization=item.source_name,
                source_type="researcher_added_source",
                edition=item.source_version or "",
                language=item.language,
                url_or_reference=item.source_url,
                license_or_access_note=f"{item.source_license_status}; see research/corpus/reports/source_audit.md",
                evidence_category="source_derived_structured_data",
                review_status=item.review_status,
                date_added=item.source_access_date,
                notes=item.source_citation,
            )
        return sources
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
    v1 = _v1_chunks()
    if v1:
        return tuple(
            KnowledgeChunk(
                chunk_id=item.chunk_id,
                source_id=item.source_id,
                source_ids=[item.source_id],
                section=item.subcategory or item.category,
                text=item.text,
                language=item.language,
                topics=[value for value in dict.fromkeys([item.category, item.entity_type, item.subcategory or ""]) if value],
                syndromes=[item.entity_name, *item.aliases] if item.entity_type == "syndrome" else [],
                herbs=[item.entity_name, *item.aliases] if item.entity_type == "herb" else [],
                meridians=[value for value in [str(item.structured_facts.get("meridians") or item.structured_facts.get("meridians_english") or "")] if value],
                safety_tags=[value for value in [str(item.structured_facts.get("toxicity") or "")] if value],
                human_review_status=item.review_status,
                keywords=list(dict.fromkeys([item.entity_name, *item.aliases])),
            )
            for item in v1
        )
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
    path = active_v1_path()
    if path is not None:
        if path.resolve() == DEFAULT_V1_PATH.resolve() and DEFAULT_V1_MANIFEST.exists():
            manifest = json.loads(DEFAULT_V1_MANIFEST.read_text(encoding="utf-8"))
            return str(manifest.get("corpus_version", "tcm-research-corpus-v1"))
        return f"tcm-v1-{hashlib.sha256(path.read_bytes()).hexdigest()[:12]}"
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
        "languages": sorted({item.language for item in chunks}),
        "validation_issues": validate_corpus(),
        "active_corpus": "tcm_research_corpus_v1" if active_v1_path() is not None else "legacy_provisional_fixture",
        "scientific_status": "provenance-aware research corpus; not clinically authoritative or validated" if active_v1_path() is not None else "small provisional educational fixture; not clinically validated",
    }
