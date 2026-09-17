from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any

from dotenv import load_dotenv

from retrieval import RetrievalEngine
from schemas.research import RetrievalStrategy

from .corpus import DEFAULT_CORPUS_ROOT, sha256_file, write_chunks, write_sources
from .ingestion.pmc import CHUNKING_VERSION, NCBIClient, ParsedPMCArticle, chunk_article, parse_pmc_articles
from .models import WesternKnowledgeChunk, WesternSourceRecord
from .validation import validate_records


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TCM_CHUNKS = PROJECT_ROOT / "research" / "corpus" / "tcm_v1" / "chunks.jsonl"
CORPUS_VERSION = "medirag-west-v0.1-pilot"
SOURCES_PER_TOPIC = 4
EXCLUDED_WESTERN_BASELINE_TITLE_TERMS = (
    "acupuncture", "auricular", "chinese medicine", "decoction", "herbal medicine", "massage",
)

TOPIC_SPECS: dict[str, dict[str, Any]] = {
    "insomnia_sleep": {
        "label": "insomnia / sleep",
        "patterns": [r"\binsomnia\b", r"\bsleep\b", r"\bsleepless(?:ness)?\b", r"poor sleep"],
    },
    "hypertension": {
        "label": "hypertension",
        "patterns": [r"\bhypertension\b", r"high blood pressure"],
    },
    "low_back_pain": {
        "label": "low back pain",
        "patterns": [r"low(?:er)? back pain", r"\blumbago\b", r"\blumbar (?:pain|ache)\b"],
    },
    "dyspepsia_digestive_symptoms": {
        "label": "dyspepsia / digestive symptoms",
        "patterns": [
            r"\bdyspepsia\b", r"\bindigestion\b", r"\bdigestive\b", r"\bdigestion\b",
            r"\bepigastric\b", r"\bstomach pain\b", r"\babdominal (?:pain|distention|distension)\b",
        ],
        "pmc_query": '(dyspepsia[Title/Abstract] OR "functional dyspepsia"[Title/Abstract])',
        "retrieval_query": "dyspepsia digestive symptoms diagnosis treatment",
    },
    "headache": {
        "label": "headache",
        "patterns": [r"\bheadache\b", r"\bhead pain\b"],
        "pmc_query": "(headache[Title/Abstract] OR migraine[Title/Abstract])",
        "retrieval_query": "headache migraine diagnosis treatment",
    },
    "cough": {
        "label": "cough",
        "patterns": [r"\bcough(?:ing)?\b"],
        "pmc_query": "cough[Title/Abstract]",
        "retrieval_query": "cough causes diagnosis treatment",
    },
    "constipation": {
        "label": "constipation",
        "patterns": [r"\bconstipat(?:ion|ed)\b"],
        "pmc_query": "constipation[Title/Abstract]",
        "retrieval_query": "constipation diagnosis treatment",
    },
    "fatigue": {
        "label": "fatigue",
        "patterns": [r"\bfatigue\b", r"\btiredness\b", r"\blassitude\b", r"\bweariness\b"],
    },
    "anxiety_stress": {
        "label": "anxiety / stress",
        "patterns": [r"\banxiety\b", r"\banxious\b", r"\bstress\b", r"\bnervousness\b", r"\bworry\b"],
    },
}

SELECTED_TOPICS = ("cough", "dyspepsia_digestive_symptoms", "headache", "constipation")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _tcm_search_text(item: dict[str, Any]) -> str:
    return " ".join([
        str(item.get("entity_name", "")),
        " ".join(map(str, item.get("aliases", []))),
        str(item.get("text", "")),
        str(item.get("category", "")),
        str(item.get("entity_type", "")),
        str(item.get("subcategory", "")),
        " ".join(map(str, item.get("topics", []))) if isinstance(item.get("topics"), list) else "",
        json.dumps(item.get("structured_facts", {}), ensure_ascii=False),
    ]).casefold()


def topic_overlap_audit() -> dict[str, Any]:
    tcm_rows = [json.loads(line) for line in TCM_CHUNKS.read_text(encoding="utf-8").splitlines() if line.strip()]
    candidates: list[dict[str, Any]] = []
    for topic, spec in TOPIC_SPECS.items():
        matches = [
            item["chunk_id"] for item in tcm_rows
            if any(re.search(pattern, _tcm_search_text(item)) for pattern in spec["patterns"])
        ]
        candidates.append({
            "topic": topic,
            "label": spec["label"],
            "direct_support_count": len(matches),
            "patterns": spec["patterns"],
            "sample_chunk_ids": matches[:10],
            "selected": topic in SELECTED_TOPICS,
        })
    candidates.sort(key=lambda item: (-item["direct_support_count"], item["topic"]))
    observed_top_four = tuple(item["topic"] for item in candidates[:4])
    if set(observed_top_four) != set(SELECTED_TOPICS):
        raise RuntimeError(f"Configured pilot topics do not match observed top four: {observed_top_four}")
    return {
        "report_name": "TCM-Western Candidate Topic Overlap Audit",
        "development_evidence_only": True,
        "corpus_path": "research/corpus/tcm_v1/chunks.jsonl",
        "corpus_chunk_count": len(tcm_rows),
        "method": "Case-insensitive deterministic regular-expression matching over entity name, aliases, retrieval text, category/entity/topic metadata, and structured facts; one count per matching TCM chunk.",
        "candidates": candidates,
        "selected_topics": list(SELECTED_TOPICS),
        "selection_rule": "Exactly the four candidates with the highest observed direct-support counts.",
    }


def _git_commit() -> str:
    completed = subprocess.run(
        ["git", "-c", f"safe.directory={PROJECT_ROOT.as_posix()}", "rev-parse", "HEAD"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _search_query(topic: str) -> str:
    return (
        f"{TOPIC_SPECS[topic]['pmc_query']} AND "
        "(review[Publication Type] OR systematic review[Title/Abstract] OR meta-analysis[Publication Type]) "
        "AND pmc open access[filter] AND english[Language]"
    )


def _select_articles(client: NCBIClient, *, build_timestamp: str) -> tuple[list[ParsedPMCArticle], dict[str, Any]]:
    selected: list[ParsedPMCArticle] = []
    selected_pmcids: set[str] = set()
    discovery: dict[str, Any] = {}
    type_priority = {"systematic_review": 0, "review_article": 1, "peer_reviewed_article": 2}

    for topic in SELECTED_TOPICS:
        query = _search_query(topic)
        identifiers = client.search_pmcs(query, retmax=16)
        xml_data = client.fetch_pmcs(identifiers)
        candidates = [
            item for item in parse_pmc_articles(xml_data, topic=topic, retrieved_at=build_timestamp)
            if "protocol" not in item.source.title.casefold()
            and not any(term in item.source.title.casefold() for term in EXCLUDED_WESTERN_BASELINE_TITLE_TERMS)
        ]
        candidates.sort(key=lambda item: type_priority[item.source.source_type])
        topic_selected: list[ParsedPMCArticle] = []
        for article in candidates:
            if article.source.pmcid in selected_pmcids:
                continue
            topic_selected.append(article)
            selected_pmcids.add(article.source.pmcid)
            if len(topic_selected) == SOURCES_PER_TOPIC:
                break
        if len(topic_selected) < SOURCES_PER_TOPIC:
            raise RuntimeError(
                f"PMC OA discovery produced only {len(topic_selected)} reusable unique sources for {topic}; "
                f"{SOURCES_PER_TOPIC} are required"
            )
        selected.extend(topic_selected)
        discovery[topic] = {
            "query_without_contact_parameters": query,
            "search_result_count_retrieved": len(identifiers),
            "reusable_articles_parsed": len(candidates),
            "selected_pmcids": [item.source.pmcid for item in topic_selected],
        }
    return selected, discovery


async def _retrieval_smoke_tests(
    sources: list[WesternSourceRecord], chunks: list[WesternKnowledgeChunk],
) -> list[dict[str, Any]]:
    source_map = {item.source_id: item for item in sources}
    engine = RetrievalEngine(chunks=tuple(chunks), sources=source_map)
    reports: list[dict[str, Any]] = []
    for topic in SELECTED_TOPICS:
        query = str(TOPIC_SPECS[topic]["retrieval_query"])
        results = await engine.search(query, strategy=RetrievalStrategy.R0, top_k=4, topics=[topic])
        if len(results) != 4 or any(item.source_id not in source_map for item in results):
            raise RuntimeError(f"Western retrieval smoke test failed for {topic}")
        reports.append({
            "topic": topic,
            "query": query,
            "strategy": "R0 lexical",
            "results": [
                {
                    "rank": item.rank,
                    "chunk_id": item.chunk_id,
                    "source_id": item.source_id,
                    "article_title": item.source_metadata.get("title", ""),
                    "lexical_score": item.lexical_score,
                }
                for item in results
            ],
            "all_results_from_western_pilot": all(item.chunk_id.startswith("west-pmc-") for item in results),
        })
    return reports


def build(root: Path = DEFAULT_CORPUS_ROOT) -> dict[str, Any]:
    load_dotenv(PROJECT_ROOT / "backend" / ".env", override=False)
    email = os.getenv("NCBI_EMAIL", "").strip()
    tool = os.getenv("NCBI_TOOL", "").strip()
    api_key = os.getenv("NCBI_API_KEY", "").strip()
    if not email:
        raise RuntimeError("NCBI_EMAIL is required for live PMC ingestion")
    if not tool:
        raise RuntimeError("NCBI_TOOL is required for live PMC ingestion")

    build_timestamp = datetime.now(timezone.utc).isoformat()
    reports_dir = root / "reports"
    audit = topic_overlap_audit()
    _write_json(reports_dir / "topic_overlap_audit.json", audit)

    client = NCBIClient(email=email, tool=tool, api_key=api_key, min_interval_seconds=0.55)
    articles, discovery = _select_articles(client, build_timestamp=build_timestamp)

    raw_dir = root / "raw"
    normalized_dir = root / "normalized"
    for directory, pattern in [(raw_dir, "*.xml"), (normalized_dir, "*.json")]:
        if directory.exists():
            for stale_path in directory.glob(pattern):
                if stale_path.is_file():
                    stale_path.unlink()
    sources: list[WesternSourceRecord] = []
    chunks: list[WesternKnowledgeChunk] = []
    for article in articles:
        raw_path = raw_dir / f"{article.source.pmcid}.xml"
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_bytes(article.raw_xml)
        _write_json(normalized_dir / f"{article.source.pmcid}.json", {
            "source": article.source.model_dump(mode="json"),
            "sections": [{"section": section, "text": text} for section, text in article.paragraphs],
            "transformation": "Whitespace normalization and deterministic JATS structural paragraph extraction; no summarization or LLM use.",
        })
        sources.append(article.source)
        chunks.extend(chunk_article(article, max_chunks=18))

    source_registry_path = root / "source_registry.json"
    chunks_path = root / "chunks.jsonl"
    write_sources(source_registry_path, sources)
    write_chunks(chunks_path, chunks)

    validation = validate_records(sources, chunks)
    _write_json(reports_dir / "validation_report.json", validation)
    if not validation["valid"]:
        raise RuntimeError(f"Western corpus validation failed with {len(validation['errors'])} hard errors")
    if not 100 <= len(chunks) <= 300:
        raise RuntimeError(f"Western pilot chunk count {len(chunks)} is outside the required approximate 100-300 range")

    smoke_tests = asyncio.run(_retrieval_smoke_tests(sources, chunks))
    source_type_counts = dict(sorted(Counter(item.source_type for item in sources).items()))
    license_counts = dict(sorted(Counter(item.license for item in sources).items()))
    manifest = {
        "corpus_name": "MediRAG-West PMC Open Access Pilot Corpus",
        "corpus_version": CORPUS_VERSION,
        "build_timestamp": build_timestamp,
        "selected_topics": list(SELECTED_TOPICS),
        "source_count": len(sources),
        "chunk_count": len(chunks),
        "source_type_counts": source_type_counts,
        "license_counts": license_counts,
        "ingestion_method": "NCBI E-utilities ESearch plus EFetch full-text JATS XML, restricted to PMC Open Access results with explicit reusable licenses",
        "ncbi_tool": tool,
        "ncbi_api_key_used": bool(api_key),
        "request_rate_limit": "maximum 2 requests/second; implementation interval 0.55 seconds",
        "chunking_version": CHUNKING_VERSION,
        "source_registry_sha256": sha256_file(source_registry_path),
        "chunks_sha256": sha256_file(chunks_path),
        "build_base_git_commit": _git_commit(),
        "scientific_status": "small retrieval-development pilot; not clinically validated",
    }
    _write_json(root / "manifest.json", manifest)
    build_report = {
        "report_name": "MediRAG-West v0.1 Pilot Build Report",
        "status": "built",
        "discovery": discovery,
        "source_count": len(sources),
        "chunk_count": len(chunks),
        "source_type_counts": source_type_counts,
        "license_counts": license_counts,
        "retrieval_smoke_tests": smoke_tests,
        "validation_errors": validation["errors"],
        "validation_warnings": validation["warnings"],
        "llm_used": False,
        "notes": [
            "Article text and bibliographic/license metadata are source-derived.",
            "Topic assignments, deterministic identifiers, timestamps, hashes, and retrieval scores are implementation metadata.",
            "Search-query relevance is a pilot selection assumption and is not a claim of clinical authority or comprehensive coverage.",
        ],
    }
    _write_json(reports_dir / "build_report.json", build_report)
    return {"manifest": manifest, "validation": validation, "build_report": build_report}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the small MediRAG-West v0.1 PMC Open Access pilot corpus.")
    parser.add_argument("--output", type=Path, default=DEFAULT_CORPUS_ROOT)
    args = parser.parse_args()
    result = build(args.output.resolve())
    summary = {
        "status": "built",
        "corpus_version": result["manifest"]["corpus_version"],
        "selected_topics": result["manifest"]["selected_topics"],
        "source_count": result["manifest"]["source_count"],
        "chunk_count": result["manifest"]["chunk_count"],
        "validation_valid": result["validation"]["valid"],
        "llm_used": False,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
