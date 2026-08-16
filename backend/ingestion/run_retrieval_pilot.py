from __future__ import annotations

import argparse
import asyncio
from collections import Counter
import json
from pathlib import Path
from time import perf_counter
from typing import Any

from corpus import corpus_version
from ingestion.tcm_v1 import load_config, normalized_key
from retrieval.engine import RetrievalEngine
from schemas.research import RetrievalStrategy


PROJECT_ROOT = Path(__file__).resolve().parents[2]
STRATEGIES = {
    "lexical": RetrievalStrategy.R0,
    "dense_local_hash": RetrievalStrategy.R1,
    "hybrid": RetrievalStrategy.R2,
    "hybrid_local_reranked": RetrievalStrategy.R3,
}


def _expected_ids(engine: RetrievalEngine, entity: str) -> set[str]:
    target = normalized_key(entity)
    return {
        chunk.chunk_id for chunk in engine.chunks
        if target in {normalized_key(item) for item in [*chunk.keywords, *chunk.herbs, *chunk.syndromes]}
    }


async def run(config_path: Path, questions_path: Path, top_k: int) -> dict[str, Any]:
    config = load_config(config_path)
    questions = json.loads(questions_path.read_text(encoding="utf-8"))
    engine = RetrievalEngine()
    rows: list[dict[str, Any]] = []
    for method, strategy in STRATEGIES.items():
        for question in questions:
            expected = _expected_ids(engine, question["expected_entity"])
            started = perf_counter()
            results = await engine.search(question["question"], strategy=strategy, top_k=top_k, topics=[question["category"]])
            latency_ms = round((perf_counter() - started) * 1000, 3)
            ranks = [item.rank for item in results if item.chunk_id in expected]
            source_ids = [item.source_id for item in results]
            duplicate_rate = 1 - len({item.chunk_id for item in results}) / max(1, len(results))
            provenance_complete = sum(bool(item.source_id and item.source_metadata.get("url_or_reference")) for item in results) / max(1, len(results))
            rows.append({
                "method": method, "existing_registry_id": strategy.value, "question_id": question["question_id"],
                "category": question["category"], "expected_entity": question["expected_entity"],
                "expected_chunk_count": len(expected), "hit_at_k": int(bool(ranks)),
                "reciprocal_rank": round(1 / min(ranks), 6) if ranks else 0.0,
                "provenance_completeness": round(provenance_complete, 6),
                "top_k_source_diversity": len(set(source_ids)), "duplicate_result_rate": round(duplicate_rate, 6),
                "latency_ms": latency_ms, "top_chunk_ids": [item.chunk_id for item in results],
                "top_source_ids": source_ids,
            })
    summaries: dict[str, Any] = {}
    for method in STRATEGIES:
        values = [item for item in rows if item["method"] == method]
        summaries[method] = {
            "existing_registry_id": STRATEGIES[method].value,
            "questions": len(values), "hit_rate_at_k": round(sum(item["hit_at_k"] for item in values) / len(values), 6),
            "mean_reciprocal_rank": round(sum(item["reciprocal_rank"] for item in values) / len(values), 6),
            "mean_provenance_completeness": round(sum(item["provenance_completeness"] for item in values) / len(values), 6),
            "mean_top_k_source_diversity": round(sum(item["top_k_source_diversity"] for item in values) / len(values), 6),
            "mean_duplicate_result_rate": round(sum(item["duplicate_result_rate"] for item in values) / len(values), 6),
            "mean_latency_ms": round(sum(item["latency_ms"] for item in values) / len(values), 3),
        }
    return {
        "pilot_name": "TCM Corpus v1 retrieval-only pilot", "corpus_version": corpus_version(),
        "chunk_count": len(engine.chunks), "top_k": top_k,
        "strategy_mapping_note": "The existing repository registry is preserved: R0=lexical, R1=dense, R2=hybrid, R3=hybrid+rerank.",
        "embedding_note": "Dense/hybrid pilot used deterministic local hash embeddings. No remote or paid embedding call was made.",
        "remote_embedding_estimate": {"document_inputs": len(engine.chunks), "query_inputs": len(questions), "approval_required_before_remote_bulk_run": True},
        "summaries": summaries, "per_question": rows,
        "manual_inspection": {
            "sample_size": len(rows), "method": "Expected source entity and top-k chunk/source IDs were inspected; no generation was run.",
            "top_source_frequency": dict(Counter(source for row in rows for source in row["top_source_ids"])),
            "limitation": "This small entity-lookup pilot is a pipeline check, not a final retrieval-quality conclusion or clinical evaluation.",
        },
    }


def _markdown(report: dict[str, Any]) -> str:
    lines = ["# TCM Corpus v1 retrieval-only pilot", "", report["strategy_mapping_note"], "", report["embedding_note"], "",
             "| Method | Registry ID | Hit@K | MRR | Provenance | Source diversity | Duplicate rate | Mean latency (ms) |",
             "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for method, item in report["summaries"].items():
        lines.append(f"| {method} | {item['existing_registry_id']} | {item['hit_rate_at_k']:.3f} | {item['mean_reciprocal_rank']:.3f} | {item['mean_provenance_completeness']:.3f} | {item['mean_top_k_source_diversity']:.3f} | {item['mean_duplicate_result_rate']:.3f} | {item['mean_latency_ms']:.3f} |")
    lines.extend(["", "This is a small retrieval-only pipeline pilot. It is not a final research conclusion and does not establish clinical correctness.", ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the local retrieval-only pilot for TCM Corpus v1.")
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "research/corpus/configs/tcm_v1.yaml")
    parser.add_argument("--questions", type=Path, default=PROJECT_ROOT / "research/corpus/configs/retrieval_pilot_questions.json")
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()
    config = load_config(args.config.resolve())
    report = asyncio.run(run(args.config.resolve(), args.questions.resolve(), args.top_k))
    json_path = PROJECT_ROOT / config["outputs"]["retrieval_pilot_json"]
    markdown_path = PROJECT_ROOT / config["outputs"]["retrieval_pilot_markdown"]
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(_markdown(report), encoding="utf-8")
    print(json.dumps({"status": "complete", "summaries": report["summaries"], "output": str(json_path)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
