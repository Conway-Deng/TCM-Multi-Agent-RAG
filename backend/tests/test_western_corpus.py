from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from retrieval import RetrievalEngine
from schemas.research import RetrievalStrategy
from western.build import SELECTED_TOPICS, topic_overlap_audit
from western.ingestion.pmc import NCBIClient, chunk_article, parse_pmc_articles
from western.models import WesternKnowledgeChunk, WesternSourceRecord
from western.validation import validate_corpus_files, validate_records


SAMPLE_JATS = b"""<?xml version="1.0" encoding="UTF-8"?>
<pmc-articleset xmlns:xlink="http://www.w3.org/1999/xlink">
  <article article-type="review-article">
    <front>
      <journal-meta><journal-title-group><journal-title>Example Medical Reviews</journal-title></journal-title-group></journal-meta>
      <article-meta>
        <article-id pub-id-type="pmcid">PMC123456</article-id>
        <article-id pub-id-type="doi">10.1000/example.1</article-id>
        <title-group><article-title>A systematic review of cough assessment</article-title></title-group>
        <pub-date><year>2024</year></pub-date>
        <permissions><license>
          <license-p>This is an open access article distributed under the Creative Commons Attribution 4.0 license at https://creativecommons.org/licenses/by/4.0/.</license-p>
        </license></permissions>
      </article-meta>
    </front>
    <body>
      <sec><title>Background</title>
        <p>Chronic cough is a common clinical symptom. This paragraph supplies enough source text to exercise deterministic structural extraction while preserving the original wording and section context for retrieval testing.</p>
        <p>Assessment considers duration, associated symptoms, medication exposure, and warning features. Management depends on the identified cause and the clinical setting rather than on a single universal intervention.</p>
      </sec>
      <sec><title>Methods</title>
        <p>The review searched multiple bibliographic databases using a predefined protocol. Eligible studies were assessed with explicit criteria and findings were organized by diagnostic and treatment questions.</p>
      </sec>
      <sec><title>Acknowledgments</title>
        <p>This acknowledgment paragraph is deliberately long enough to be extracted if exclusion fails, but it must never appear in the normalized article paragraphs or generated chunks.</p>
      </sec>
      <sec><title>References</title>
        <p>This reference paragraph is deliberately long enough to be extracted if exclusion fails, but it must never appear in the normalized article paragraphs or generated chunks.</p>
      </sec>
    </body>
  </article>
</pmc-articleset>"""


def source(source_id: str = "west-pmc-123456") -> WesternSourceRecord:
    return WesternSourceRecord(
        source_id=source_id,
        title="A systematic review of cough assessment",
        source_type="systematic_review",
        organization_or_journal="Example Medical Reviews",
        publication_year=2024,
        source_url="https://pmc.ncbi.nlm.nih.gov/articles/PMC123456/",
        pmcid="PMC123456",
        doi="10.1000/example.1",
        license="CC BY 4.0",
        license_url="https://creativecommons.org/licenses/by/4.0/",
        retrieved_at="2026-09-17T00:00:00+00:00",
        topics=["cough"],
    )


def chunk(chunk_id: str = "west-pmc-123456-abc", source_id: str = "west-pmc-123456") -> WesternKnowledgeChunk:
    return WesternKnowledgeChunk(
        chunk_id=chunk_id,
        source_id=source_id,
        section="Background",
        text="Cough assessment includes duration, associated symptoms, diagnostic evaluation, and treatment based on cause.",
        topics=["cough"],
        keywords=["cough", "assessment", "treatment"],
        pmcid="PMC123456",
        doi="10.1000/example.1",
        source_url="https://pmc.ncbi.nlm.nih.gov/articles/PMC123456/",
    )


def test_western_schema_requires_valid_pmcid_and_domain() -> None:
    with pytest.raises(ValidationError):
        WesternSourceRecord.model_validate({**source().model_dump(), "pmcid": "123456"})
    with pytest.raises(ValidationError):
        WesternKnowledgeChunk.model_validate({**chunk().model_dump(), "domain": "tcm"})


def test_pmc_parser_preserves_license_doi_and_excludes_noncontent_sections() -> None:
    articles = parse_pmc_articles(SAMPLE_JATS, topic="cough", retrieved_at="2026-09-17T00:00:00+00:00")
    assert len(articles) == 1
    item = articles[0]
    assert item.source.pmcid == "PMC123456"
    assert item.source.doi == "10.1000/example.1"
    assert item.source.license == "CC BY 4.0"
    assert item.source.license_url == "https://creativecommons.org/licenses/by/4.0/"
    assert item.source.source_type == "systematic_review"
    combined = " ".join(text for _, text in item.paragraphs)
    assert "acknowledgment paragraph" not in combined
    assert "reference paragraph" not in combined


def test_chunk_ids_and_chunking_are_deterministic() -> None:
    article = parse_pmc_articles(SAMPLE_JATS, topic="cough", retrieved_at="2026-09-17T00:00:00+00:00")[0]
    first = chunk_article(article)
    second = chunk_article(article)
    assert [item.model_dump() for item in first] == [item.model_dump() for item in second]
    assert all(item.chunk_id.startswith("west-pmc-123456-") for item in first)
    assert all(item.section and item.text for item in first)


def test_validation_detects_duplicates_and_unknown_source_references() -> None:
    report = validate_records(
        [source(), source()],
        [chunk(), chunk(), chunk("west-pmc-123456-other", "west-pmc-missing")],
    )
    assert report["valid"] is False
    assert "duplicate source_id: west-pmc-123456" in report["errors"]
    assert "duplicate chunk_id: west-pmc-123456-abc" in report["errors"]
    assert "west-pmc-123456-other: unknown source_id west-pmc-missing" in report["errors"]


def test_validation_reports_malformed_jsonl(tmp_path: Path) -> None:
    (tmp_path / "source_registry.json").write_text(json.dumps([source().model_dump(mode="json")]), encoding="utf-8")
    (tmp_path / "chunks.jsonl").write_text("{not-json}\n", encoding="utf-8")
    report = validate_corpus_files(tmp_path)
    assert report["valid"] is False
    assert any("chunks.jsonl line 1: malformed" in item for item in report["errors"])


def test_ncbi_client_enforces_two_requests_per_second_ceiling() -> None:
    with pytest.raises(ValueError, match="at most 2 per second"):
        NCBIClient(email="configured@example.org", tool="medirag_test", min_interval_seconds=0.49)


def test_retrieval_engine_accepts_injected_western_models() -> None:
    sources = {"west-pmc-123456": source()}
    chunks = tuple(
        chunk(f"west-pmc-123456-{index}").model_copy(update={
            "text": f"Cough diagnostic assessment and treatment evidence section {index}.",
        })
        for index in range(1, 6)
    )
    engine = RetrievalEngine(chunks=chunks, sources=sources)
    results = asyncio.run(engine.search(
        "cough diagnosis treatment",
        strategy=RetrievalStrategy.R0,
        top_k=4,
        topics=["cough"],
    ))
    assert len(results) == 4
    assert all(item.chunk_id.startswith("west-pmc-") for item in results)
    assert all(item.source_metadata["pmcid"] == "PMC123456" for item in results)
    assert all(item.source_metadata["license"] == "CC BY 4.0" for item in results)


def test_default_review_status_does_not_claim_clinical_validation() -> None:
    assert source().review_status == "not_human_clinically_validated"
    assert chunk().human_review_status == "not_human_clinically_validated"


def test_topic_overlap_audit_selects_observed_top_four() -> None:
    report = topic_overlap_audit()
    selected = [item for item in report["candidates"] if item["selected"]]
    assert {item["topic"] for item in selected} == set(SELECTED_TOPICS)
    assert [(item["topic"], item["direct_support_count"]) for item in selected] == [
        ("cough", 671),
        ("dyspepsia_digestive_symptoms", 397),
        ("headache", 232),
        ("constipation", 120),
    ]
