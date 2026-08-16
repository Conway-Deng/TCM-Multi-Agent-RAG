from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from corpus.v1_models import NormalizedRecord, ResearchChunk
from ingestion.contamination import check_contamination
from ingestion.tcm_v1 import ALLOWED_CATEGORIES, load_config


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REQUIRED_PROVENANCE = [
    "source_id", "source_name", "source_record_id", "source_url", "source_title", "source_citation",
    "source_license_status", "source_access_date", "transformation_history", "ingestion_timestamp", "corpus_version",
]


def _load_jsonl(path: Path, model: type[NormalizedRecord] | type[ResearchChunk]) -> list[Any]:
    return [model.model_validate_json(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _missing_rate(values: list[ResearchChunk], field: str) -> float:
    missing = sum(getattr(item, field, None) in (None, "", [], {}) for item in values)
    return round(missing / len(values), 6) if values else 0.0


def validate(config_path: Path) -> tuple[dict[str, Any], bool]:
    config = load_config(config_path)
    normalized_path = PROJECT_ROOT / config["outputs"]["normalized_records"]
    chunks_path = PROJECT_ROOT / config["outputs"]["chunks"]
    manifest_path = PROJECT_ROOT / config["outputs"]["manifest"]
    dedup_path = PROJECT_ROOT / config["outputs"]["dedup_report"]
    errors: list[str] = []
    warnings: list[str] = []
    for path in [normalized_path, chunks_path, manifest_path, dedup_path]:
        if not path.exists():
            errors.append(f"missing build artifact: {path}")
    if errors:
        return {"report_name": "TCM Corpus v1 Validation Report", "valid": False, "errors": errors}, False
    records = _load_jsonl(normalized_path, NormalizedRecord)
    chunks = _load_jsonl(chunks_path, ResearchChunk)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    dedup = json.loads(dedup_path.read_text(encoding="utf-8"))

    chunk_ids = Counter(item.chunk_id for item in chunks)
    duplicate_ids = sorted(item for item, count in chunk_ids.items() if count > 1)
    if duplicate_ids:
        errors.append(f"duplicate chunk IDs: {len(duplicate_ids)}")
    record_keys = {(item.source_id, item.source_record_id) for item in records}
    for chunk in chunks:
        if not chunk.text.strip():
            errors.append(f"{chunk.chunk_id}: empty text")
        if chunk.category not in ALLOWED_CATEGORIES:
            errors.append(f"{chunk.chunk_id}: invalid category {chunk.category}")
        if (chunk.source_id, chunk.source_record_id) not in record_keys:
            errors.append(f"{chunk.chunk_id}: source record not found")
        for field in REQUIRED_PROVENANCE:
            if getattr(chunk, field, None) in (None, "", [], {}):
                errors.append(f"{chunk.chunk_id}: missing provenance field {field}")
        parsed = urlparse(chunk.source_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            errors.append(f"{chunk.chunk_id}: malformed source URL")
        if any(marker in " ".join(chunk.transformation_history).casefold() for marker in ["llm_generated_fact", "ai_generated_fact"]):
            errors.append(f"{chunk.chunk_id}: unsupported generated fact marker")
    if any("\ufffd" in chunk.text or "���" in chunk.text for chunk in chunks):
        errors.append("retrieval text contains corrupted upstream characters")

    benchmark_paths = [*sorted((PROJECT_ROOT / "research/datasets").glob("*.json*")), *sorted((PROJECT_ROOT / "research/benchmarks/external").rglob("*.json*"))]
    contamination = check_contamination(chunks, benchmark_paths)
    if contamination["exact_text_overlap_count"] or contamination["source_record_leakage_count"]:
        errors.append("benchmark contamination detected")
    if contamination["high_similarity_overlap_count"]:
        warnings.append("Highly similar corpus/benchmark text requires manual inspection.")
    if not list((PROJECT_ROOT / "research/benchmarks/external").rglob("*.json*")):
        warnings.append("No external ZhongJing benchmark files are present; external contamination testing is deferred.")

    source_count = len({item.source_id for item in chunks})
    conflicts = {group for item in chunks for group in item.conflict_group_ids}
    reviewed = sum(item.expert_review_claimed_by_source is True for item in chunks)
    report = {
        "report_name": "TCM Corpus v1 Validation Report", "corpus_name": manifest["corpus_name"],
        "corpus_version": manifest["corpus_version"], "valid": not errors, "errors": errors, "warnings": warnings,
        "number_of_sources": source_count, "raw_record_count": manifest["raw_record_count"],
        "normalized_entity_count": len(records), "relation_count": manifest["relation_count"], "chunk_count": len(chunks),
        "chunks_per_category": dict(Counter(item.category for item in chunks)),
        "chunks_per_source": dict(Counter(item.source_id for item in chunks)),
        "missing_field_rates": {field: _missing_rate(chunks, field) for field in [
            "source_version", "subcategory", "aliases", "relation_type", "related_entities", "conflict_group_ids",
        ]},
        "duplicate_statistics": {
            "duplicate_chunk_ids": len(duplicate_ids), "exact_duplicates_removed": dedup["exact_duplicates_removed"],
            "alias_equivalent_groups": dedup["alias_equivalent_groups"], "near_duplicates_flagged": dedup["near_duplicates_flagged"],
        },
        "conflict_statistics": {"conflict_groups_preserved": len(conflicts)},
        "language_distribution": dict(Counter(item.language for item in chunks)),
        "provenance_completeness": round(sum(all(getattr(item, field, None) not in (None, "", [], {}) for field in REQUIRED_PROVENANCE) for item in chunks) / len(chunks), 6) if chunks else 0.0,
        "expert_reviewed_source_coverage": round(reviewed / len(chunks), 6) if chunks else 0.0,
        "benchmark_contamination": contamination,
        "known_coverage_gaps": [
            "No reliable prescription/formula source was available under verified database terms.",
            "No dedicated acupuncture source was accepted.", "No dedicated meridian-theory source was accepted.",
            "No dedicated constitution-analysis source was accepted.", "No source-level safety/contraindication corpus beyond herb toxicity fields was accepted.",
            "No bulk relationship files were accepted; relation_count is zero.",
        ],
    }
    return report, not errors


def _markdown(report: dict[str, Any]) -> str:
    lines = ["# TCM Corpus v1 Validation Report", "", f"Valid: **{report['valid']}**", "",
             f"- Sources: {report.get('number_of_sources', 0)}", f"- Raw records: {report.get('raw_record_count', 0)}",
             f"- Normalized entities: {report.get('normalized_entity_count', 0)}", f"- Relations: {report.get('relation_count', 0)}",
             f"- Chunks: {report.get('chunk_count', 0)}", f"- Provenance completeness: {report.get('provenance_completeness', 0):.1%}",
             f"- Expert-reviewed-source claim coverage: {report.get('expert_reviewed_source_coverage', 0):.1%}", "",
             "## Chunks per category", ""]
    lines.extend(f"- {key}: {value}" for key, value in report.get("chunks_per_category", {}).items())
    lines.extend(["", "## Errors", ""] + ([f"- {item}" for item in report.get("errors", [])] or ["- None"]))
    lines.extend(["", "## Warnings", ""] + ([f"- {item}" for item in report.get("warnings", [])] or ["- None"]))
    lines.extend(["", "## Known coverage gaps", ""] + [f"- {item}" for item in report.get("known_coverage_gaps", [])])
    lines.extend(["", "This validates structure, provenance, separation, and reproducibility. It does not establish clinical authority or correctness.", ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate TCM Research Corpus v1 and benchmark isolation.")
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "research/corpus/configs/tcm_v1.yaml")
    args = parser.parse_args()
    config = load_config(args.config.resolve())
    report, valid = validate(args.config.resolve())
    json_path = PROJECT_ROOT / config["outputs"]["validation_json"]
    markdown_path = PROJECT_ROOT / config["outputs"]["validation_markdown"]
    contamination_path = PROJECT_ROOT / config["outputs"]["contamination_json"]
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(_markdown(report), encoding="utf-8")
    contamination_path.write_text(json.dumps(report.get("benchmark_contamination", {}), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
