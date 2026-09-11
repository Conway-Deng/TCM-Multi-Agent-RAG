from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
from time import perf_counter
from typing import Any
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
STUDY_ROOT = Path(__file__).resolve().parent
BACKEND_ROOT = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from providers.openai_compatible import ProviderUnavailable
from retrieval import RetrievalEngine
from schemas.research import RetrievalStrategy


CONFIG_PATH = STUDY_ROOT / "retrieval_ablation_config.json"
SPLIT_PATH = STUDY_ROOT / "selection_manifest.json"
STAGE = "stage1_retrieval_only"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def load_inputs() -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], str]:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    split = json.loads(SPLIT_PATH.read_text(encoding="utf-8"))
    benchmark_path = PROJECT_ROOT / config["benchmark"]["path"]
    if sha256(benchmark_path) != config["benchmark"]["sha256"]:
        raise ValueError("Frozen benchmark hash mismatch")
    if sha256(PROJECT_ROOT / config["corpus"]["path"]) != config["corpus"]["sha256"]:
        raise ValueError("Frozen corpus hash mismatch")
    benchmark = [json.loads(line) for line in benchmark_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return config, split, benchmark, canonical_hash(config)


def resume_identity(*, question_id: str, retrieval_condition: str, stage: str, benchmark_hash: str, config_hash: str) -> str:
    return canonical_hash({
        "question_id": question_id,
        "retrieval_condition": retrieval_condition,
        "stage": stage,
        "benchmark_hash": benchmark_hash,
        "retrieval_config_hash": config_hash,
    })


def build_stage1_plan() -> list[dict[str, Any]]:
    config, split, benchmark, config_hash = load_inputs()
    by_id = {item["question_id"]: item for item in benchmark}
    ordered_ids = [item["question_id"] for item in sorted(split["assignments"], key=lambda item: item["overall_sequence"])]
    plan = []
    for question_id in ordered_ids:
        item = by_id[question_id]
        for condition in ("R0", "R1", "R2", "R3"):
            plan.append({
                "question_id": question_id,
                "retrieval_condition": condition,
                "stage": STAGE,
                "benchmark_sha256": config["benchmark"]["sha256"],
                "retrieval_config_sha256": config_hash,
                "resume_identity": resume_identity(
                    question_id=question_id,
                    retrieval_condition=condition,
                    stage=STAGE,
                    benchmark_hash=config["benchmark"]["sha256"],
                    config_hash=config_hash,
                ),
                "question": item["question"],
            })
    if len(plan) != 400 or len({item["resume_identity"] for item in plan}) != 400:
        raise ValueError("Stage 1 plan identity invariant failed")
    return plan


def _topics(item: dict[str, Any]) -> list[str]:
    if "+" in item["domain"]:
        return ["herbal", "syndrome"]
    return ["herbal"] if item["domain"] == "herbal_medicine" else ["syndrome"]


def _metric_row(retrieved_ids: list[str], gold_ids: set[str], retrieved_sources: list[str], gold_sources: set[str]) -> dict[str, float]:
    def recall(k: int) -> float:
        return len(set(retrieved_ids[:k]) & gold_ids) / max(1, len(gold_ids))

    def hit(k: int) -> float:
        return float(bool(set(retrieved_ids[:k]) & gold_ids))

    return {
        "chunk_recall_at_1": recall(1),
        "chunk_recall_at_4": recall(4),
        "chunk_recall_at_8": recall(8),
        "gold_evidence_recall": recall(4),
        "hit_at_1": hit(1),
        "hit_at_4": hit(4),
        "hit_at_8": hit(8),
        "source_recall": len(set(retrieved_sources[:4]) & gold_sources) / max(1, len(gold_sources)),
    }


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _formal_environment() -> None:
    """Select the already-authorized SiliconFlow providers without persisting secrets."""
    from config import get_settings
    configured = get_settings()
    os.environ["TCM_CORPUS_MODE"] = "required"
    os.environ["ALLOW_BULK_REMOTE_EMBEDDING"] = "true"
    llm_key = os.getenv("LLM_API_KEY", "") or configured.llm_api_key
    if not os.getenv("EMBEDDING_PROVIDER"):
        os.environ["EMBEDDING_PROVIDER"] = "siliconflow"
    if not os.getenv("EMBEDDING_API_KEY"):
        os.environ["EMBEDDING_API_KEY"] = llm_key
    if not os.getenv("EMBEDDING_MODEL"):
        os.environ["EMBEDDING_MODEL"] = "BAAI/bge-m3"
    if not os.getenv("RERANK_PROVIDER"):
        os.environ["RERANK_PROVIDER"] = "siliconflow"
    if not os.getenv("RERANK_API_KEY"):
        os.environ["RERANK_API_KEY"] = llm_key
    if not os.getenv("RERANK_MODEL"):
        os.environ["RERANK_MODEL"] = "BAAI/bge-reranker-v2-m3"
    get_settings.cache_clear()


def _validate_cache(engine: RetrievalEngine, config: dict[str, Any]) -> dict[str, Any]:
    strict = config["formal_strict"]
    provider = engine.providers.embedding
    if provider.name != strict["embedding_provider"] or provider.model != strict["embedding_model"]:
        raise RuntimeError("strict embedding provider/model configuration mismatch")
    identity = engine.embedding_cache_identity(provider)
    cache_path = engine._cache_path(identity)
    if not cache_path.exists():
        raise RuntimeError(f"completed BGE cache is missing: {cache_path}")
    data = json.loads(cache_path.read_text(encoding="utf-8"))
    expected_ids = [chunk.chunk_id for chunk in engine.chunks]
    if data.get("identity") != identity or data.get("document_ids") != expected_ids:
        raise RuntimeError("completed BGE cache identity or document ordering mismatch")
    vectors = data.get("document_vectors")
    dimension = engine._validate_vectors(vectors, len(expected_ids), expected_dimension=1024)
    return {"path": str(cache_path), "identity": identity, "chunks": len(expected_ids), "dimension": dimension, "query_cache_entries": len(data.get("query_vectors", {}))}


def _formal_manifest(config: dict[str, Any], split: dict[str, Any], benchmark: list[dict[str, Any]], config_hash: str, plan: list[dict[str, Any]], engine: RetrievalEngine, cache: dict[str, Any]) -> dict[str, Any]:
    condition_configs = {
        condition: canonical_hash({"condition": condition, **config["retrieval_conditions"][condition], "strict": config["formal_strict"], "candidate_depth": config["fixed_variables"]["candidate_depth"], "top_k": config["fixed_variables"]["final_top_k"]})
        for condition in ("R0", "R1", "R2", "R3")
    }
    return {
        "study_id": config["study_id"],
        "stage": STAGE,
        "status": "LOCKED_BEFORE_FIRST_EVALUATION",
        "benchmark_sha256": config["benchmark"]["sha256"],
        "corpus_sha256": config["corpus"]["sha256"],
        "split_sha256": sha256(SPLIT_PATH),
        "retrieval_config_sha256": config_hash,
        "runner_implementation_sha256": sha256(Path(__file__)),
        "condition_config_sha256": condition_configs,
        "embedding_model": config["formal_strict"]["embedding_model"],
        "reranker_model": config["formal_strict"]["rerank_model"],
        "embedding_cache": cache,
        "top_k": {"stage1_metric_depth": 8, "final_generation_evidence": config["fixed_variables"]["final_top_k"]},
        "candidate_depth": config["fixed_variables"]["candidate_depth"],
        "random_seed": split["seed"],
        "question_ordering": "selection_manifest overall_sequence, condition order R0,R1,R2,R3",
        "retry_policy": config["fixed_variables"]["retrieval_retry_failure_policy"],
        "planned_stage1_executions": 400,
        "planned_questions": len(benchmark),
        "execution_order_sha256": hashlib.sha256(json.dumps(plan, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest(),
        "gold_labels_exposed_to_retriever": False,
        "provider_calls": {"embedding": 0, "reranker": 0, "qwen": 0},
    }


async def execute_stage1(output: Path) -> dict[str, Any]:
    if os.getenv("RETRIEVAL_ABLATION_EXECUTION") != "FORMAL_STAGE1_APPROVED":
        raise RuntimeError("Stage 1 is locked; set RETRIEVAL_ABLATION_EXECUTION=FORMAL_STAGE1_APPROVED only after authorization")
    _formal_environment()
    config, split, benchmark, config_hash = load_inputs()
    by_id = {item["question_id"]: item for item in benchmark}
    strict = config["formal_strict"]
    engine = RetrievalEngine(
        formal_strict=True,
        cache_dir=STUDY_ROOT / "cache",
        embedding_batch_size=int(strict["embedding_batch_size"]),
        candidate_depth=int(config["fixed_variables"]["candidate_depth"]),
        preprocessing_version=str(strict["preprocessing_version"]),
        embedding_config_version=str(strict["embedding_config_version"]),
    )
    output.mkdir(parents=True, exist_ok=True)
    cache_info = _validate_cache(engine, config)
    plan = build_stage1_plan()
    manifest_path = output / "formal_run_manifest.json"
    execution_order_path = output / "execution_order.json"
    if manifest_path.exists():
        existing_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if existing_manifest.get("benchmark_sha256") != config["benchmark"]["sha256"] or existing_manifest.get("split_sha256") != sha256(SPLIT_PATH) or existing_manifest.get("planned_stage1_executions") != 400:
            raise RuntimeError("existing formal manifest does not match preregistration")
    else:
        manifest = _formal_manifest(config, split, benchmark, config_hash, plan, engine, cache_info)
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    if not execution_order_path.exists():
        execution_order_path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    raw_path = output / "results.jsonl"
    attempts_path = output / "provider_attempts.jsonl"
    completed = set()
    if raw_path.exists():
        existing_rows = [json.loads(line) for line in raw_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        completed = {row["resume_identity"] for row in existing_rows}
        if len(completed) != len(existing_rows) or not completed <= {entry["resume_identity"] for entry in plan}:
            raise RuntimeError("formal results contain duplicate or invalid canonical identities")
    chunk_source = {chunk.chunk_id: chunk.source_id for chunk in engine.chunks}
    engine._load_embedding_cache(cache_info["identity"])
    records = 0
    embedding_calls = 0
    reranker_calls = 0
    failed_provider_calls = 0
    cache_hits = {"corpus_cache_loads": 1, "query_cache_hits": 0}
    query_cache_seen = set(engine._query_vectors)
    with raw_path.open("a", encoding="utf-8") as handle:
        attempts_handle = attempts_path.open("a", encoding="utf-8")
        for entry in build_stage1_plan():
            if entry["resume_identity"] in completed:
                continue
            item = by_id[entry["question_id"]]
            gold_ids = set(item["preferred_evidence_ids"])
            gold_sources = {chunk_source[item_id] for item_id in gold_ids}
            started = perf_counter()
            query_key = hashlib.sha256(item["question"].encode("utf-8")).hexdigest()
            query_cached = query_key in query_cache_seen
            try:
                results = await engine.search(
                    item["question"],
                    strategy=RetrievalStrategy(entry["retrieval_condition"]),
                    top_k=8,
                    topics=_topics(item),
                )
                retrieved_ids = [result.chunk_id for result in results]
                row = {
                    **entry,
                    **_metric_row(retrieved_ids, gold_ids, [result.source_id for result in results], gold_sources),
                    "retrieved_ids": retrieved_ids,
                    "retrieval_latency_ms": round((perf_counter() - started) * 1000, 3),
                    "usable": True,
                    "fallback": False,
                    "embedding_provider": engine.actual_embedding_provider,
                    "embedding_model": engine.actual_embedding_model,
                    "reranker_provider": engine.actual_reranker_provider,
                    "reranker_model": engine.actual_reranker_model,
                    "error_type": None,
                    "error": None,
                }
                if entry["retrieval_condition"] != "R0":
                    if query_cached:
                        cache_hits["query_cache_hits"] += 1
                    else:
                        embedding_calls += 1
                        query_cache_seen.add(query_key)
                        attempts_handle.write(json.dumps({"resume_identity": entry["resume_identity"], "provider_stage": "query_embedding", "attempt": 1, "provider": row["embedding_provider"], "model": row["embedding_model"], "success": True}, ensure_ascii=False) + "\n")
                    attempts_handle.flush()
                if entry["retrieval_condition"] == "R3":
                    reranker_calls += 1
                    attempts_handle.write(json.dumps({"resume_identity": entry["resume_identity"], "provider_stage": "reranker", "attempt": 1, "provider": row["reranker_provider"], "model": row["reranker_model"], "success": True}, ensure_ascii=False) + "\n")
                    attempts_handle.flush()
            except ProviderUnavailable as exc:
                failed_provider_calls += 1
                row = {
                    **entry,
                    "chunk_recall_at_1": 0.0,
                    "chunk_recall_at_4": 0.0,
                    "chunk_recall_at_8": 0.0,
                    "gold_evidence_recall": 0.0,
                    "hit_at_1": 0.0,
                    "hit_at_4": 0.0,
                    "hit_at_8": 0.0,
                    "source_recall": 0.0,
                    "retrieved_ids": [],
                    "retrieval_latency_ms": round((perf_counter() - started) * 1000, 3),
                    "usable": False,
                    "fallback": False,
                    "error_type": exc.error_type,
                    "error": str(exc),
                }
                attempts_handle.write(json.dumps({"resume_identity": entry["resume_identity"], "provider_stage": "retrieval", "attempt": 1, "success": False, "error_type": exc.error_type, "error": str(exc)}, ensure_ascii=False) + "\n")
                attempts_handle.flush()
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            handle.flush()
            records += 1
        attempts_handle.close()
    all_rows = [json.loads(line) for line in raw_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(all_rows) != 400 or len({row["resume_identity"] for row in all_rows}) != 400:
        raise RuntimeError(f"Stage 1 did not produce exactly 400 unique rows (found {len(all_rows)})")
    from analysis import select_advanced_method, selection_statistics, stage1_summary
    selection = select_advanced_method(all_rows, split)
    statistics = selection_statistics(all_rows, split)
    summary = stage1_summary(all_rows, split)
    (output / "selection_analysis.json").write_text(json.dumps(selection, indent=2) + "\n", encoding="utf-8")
    (output / "selection_statistics.json").write_text(json.dumps(statistics, indent=2) + "\n", encoding="utf-8")
    (output / "stage1_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    _write_csv(output / "stage1_metrics.csv", all_rows)
    final_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    final_manifest.update({
        "status": "STAGE_1_COMPLETE",
        "completed_stage1_executions": len(all_rows),
        "new_records_this_invocation": records,
        "provider_calls": {"embedding": embedding_calls, "reranker": reranker_calls, "qwen": 0},
        "failed_provider_calls_this_invocation": failed_provider_calls,
        "cache_hits": cache_hits,
        "failed_formal_rows": sum(not bool(row["usable"]) for row in all_rows),
        "fallback_events": sum(bool(row.get("fallback")) for row in all_rows),
        "selected_advanced_method": selection["selected_advanced_method"],
        "stage2_authorized_by_gate": selection["stage2_authorized_by_gate"],
    })
    manifest_path.write_text(json.dumps(final_manifest, indent=2) + "\n", encoding="utf-8")
    (output / "stage1_manifest.json").write_text(json.dumps(final_manifest, indent=2) + "\n", encoding="utf-8")
    return final_manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", action="store_true")
    parser.add_argument("--execute-stage1", action="store_true")
    parser.add_argument("--output", type=Path, default=STUDY_ROOT / "formal_stage1")
    args = parser.parse_args()
    if args.execute_stage1:
        print(json.dumps(asyncio.run(execute_stage1(args.output)), indent=2))
        return 0
    plan = build_stage1_plan()
    print(json.dumps({"stage": STAGE, "planned_retrieval_evaluations": len(plan), "unique_resume_identities": len({item['resume_identity'] for item in plan}), "llm_generation_calls": 0}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
