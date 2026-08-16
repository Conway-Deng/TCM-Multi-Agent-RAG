from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import sys


BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from corpus.v1_models import NormalizedRecord, ResearchChunk
from ingestion.contamination import check_contamination
from ingestion.tabular import read_tabular
from ingestion.tcm_v1 import (
    deduplicate_and_flag,
    deterministic_chunk_id,
    import_symmap_herbs,
    normalize_text,
    record_to_chunk,
)


def _record(source_id: str = "source-a", record_id: str = "1", properties: str = "warm") -> NormalizedRecord:
    return NormalizedRecord(
        source_id=source_id,
        source_name="Audited source",
        source_record_id=record_id,
        source_version="1",
        source_url="https://example.org/source",
        source_title="Source title",
        source_citation="Citation",
        source_license_status="restricted",
        source_access_date="2026-08-16",
        category="herbal_medicine",
        subcategory="herb",
        entity_type="herb",
        entity_name="Test Herb",
        aliases=[" test  herb "],
        language="en",
        structured_facts={"properties": properties},
        transformation_history=["Deterministic test import."],
        ingestion_timestamp="2026-08-16T00:00:00Z",
        corpus_version="test-v1",
        original_record={"name": "Test Herb", "properties": properties},
    )


def test_unicode_normalization_and_deterministic_chunk_ids() -> None:
    assert normalize_text("  Ｔｅｓｔ\n Herb ") == "Test Herb"
    record = _record()
    chunk = record_to_chunk(record)
    assert chunk.chunk_id == deterministic_chunk_id(record, chunk.text)
    assert chunk == record_to_chunk(record)
    assert chunk.source_record_id == "1"
    assert chunk.transformation_history == ["Deterministic test import."]


def test_exact_duplicates_removed_but_cross_source_conflicts_preserved() -> None:
    duplicate = _record(record_id="2")
    first = _record()
    conflicting = _record(source_id="source-b", record_id="3", properties="cold")
    records, report = deduplicate_and_flag([first, duplicate, conflicting])
    assert len(records) == 2
    assert report["exact_duplicates_removed"] == 1
    assert report["conflicts_preserved"] == 1
    assert all(item.conflict_group_ids for item in records)


def test_supported_plain_formats_and_sqlite(tmp_path: Path) -> None:
    (tmp_path / "rows.csv").write_text("id,name\n1,CSV\n", encoding="utf-8")
    (tmp_path / "rows.tsv").write_text("id\tname\n2\tTSV\n", encoding="utf-8")
    (tmp_path / "rows.json").write_text(json.dumps([{"id": 3, "name": "JSON"}]), encoding="utf-8")
    (tmp_path / "rows.jsonl").write_text('{"id": 4, "name": "JSONL"}\n', encoding="utf-8")
    database = tmp_path / "rows.sqlite"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE records (id INTEGER, name TEXT)")
        connection.execute("INSERT INTO records VALUES (5, 'SQLite')")
    assert [next(read_tabular(tmp_path / name))["name"] for name in ["rows.csv", "rows.tsv", "rows.json", "rows.jsonl", "rows.sqlite"]] == [
        "CSV", "TSV", "JSON", "JSONL", "SQLite"
    ]


def test_source_importer_retains_original_and_provenance(tmp_path: Path) -> None:
    source_file = tmp_path / "symmap.csv"
    source_file.write_text(
        "Herb_id,English_name,Pinyin_name,Properties_English,Suppress\n1,Test Herb,Ce Shi,Warm,0\n",
        encoding="utf-8",
    )
    config = {
        "ingestion_timestamp": "2026-08-16T00:00:00Z",
        "corpus_version": "test-v1",
        "sources": [{
            "source_id": "symmap_v2",
            "source_name": "SymMap v2",
            "source_version": "v2.0",
            "official_url": "https://example.org/symmap",
            "source_title": "SymMap test export",
            "source_citation": "Test citation",
            "license_status": "restricted",
            "access_date": "2026-08-16",
            "expert_review_claimed": True,
        }],
    }
    records = import_symmap_herbs(source_file, config, "symmap_v2")
    assert len(records) == 1
    assert records[0].source_record_id == "SMHB00001"
    assert records[0].structured_facts["properties_english"] == "Warm"
    assert records[0].original_record["Pinyin_name"] == "Ce Shi"
    assert records[0].expert_review_claimed_by_source is True


def test_contamination_checker_finds_exact_text_and_source_leakage(tmp_path: Path) -> None:
    chunk = record_to_chunk(_record())
    benchmark = tmp_path / "benchmark.jsonl"
    benchmark.write_text(json.dumps({"question": chunk.text, "source_id": chunk.source_id}) + "\n", encoding="utf-8")
    report = check_contamination([ResearchChunk.model_validate(chunk)], [benchmark])
    assert report["exact_text_overlap_count"] == 1
    assert report["source_record_leakage_count"] == 1
    assert report["zero_leakage_claimed"] is False
