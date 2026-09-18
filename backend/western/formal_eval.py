from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from time import perf_counter
from typing import Any, Awaitable, Callable, Iterable

from config.settings import get_settings
from providers import ProviderBundle, build_llm_provider, get_provider_bundle
from providers.openai_compatible import ProviderUnavailable
from providers.siliconflow import SiliconFlowEmbeddingProvider, SiliconFlowRerankProvider
from retrieval.engine import RetrievalEngine
from schemas.research import RetrievalStrategy

from .agent import (
    SYSTEM_PROMPT,
    WESTERN_EVIDENCE_EXCERPT_CHARS,
    WESTERN_MAX_TOKENS,
    WESTERN_MODEL,
    WESTERN_TIMEOUT_SECONDS,
    _generation_prompt,
    _validated_answer,
)
from .benchmark import load_benchmark
from .corpus import load_runtime_corpus, sha256_file
from .formal_judge import (
    JUDGE_SYSTEM_PROMPT,
    build_judge_prompt,
    checkable_claim_counts,
    parse_judge_output,
)
from .schemas import WesternRetrievalEvidence, WesternTopic


PROTOCOL_VERSION = "western-formal-v0.1"
BENCHMARK_VERSION = "western-pilot-v0.1"
BENCHMARK_SHA256 = "29d4a2c08bd8529f77d7d9faff7e739a5c60775dd04d99711d0e254a7aa200c6"
BENCHMARK_MANIFEST_SHA256 = "bd8fc5105329d5d325fa8910b8a642bac6ddc954a25df6b9e299158aa29a22ae"
CORPUS_CHUNKS_SHA256 = "8c53511e6193ebccea70c59f121fd456b5749b1e40a16eaeda3a4e53515a752b"
SOURCE_REGISTRY_SHA256 = "722273140906b238e88cfdab4ddbb12d73c478f686ae23d0f501738ee6820703"
RUNTIME_COMMIT = "e6b02f6e37534008427cb18cd06ce7f086153103"
BENCHMARK_COMMIT = "bc1b389bdb6c4eb0c5c4c629af549a6904a37477"
FINAL_TOP_K = 4
CANDIDATE_DEPTH = 12
RRF_CONSTANT = 60
GENERATOR_PROVIDER = "siliconflow"
GENERATOR_MODEL = "Qwen/Qwen3-8B"
GENERATOR_TEMPERATURE = 0.0
GENERATOR_MAX_TOKENS = 256
GENERATOR_TIMEOUT_SECONDS = 120.0
JUDGE_PROVIDER = "siliconflow"
JUDGE_MODEL = "THUDM/GLM-Z1-9B-0414"
JUDGE_TEMPERATURE = 0.0
JUDGE_MAX_TOKENS = 1200
JUDGE_TIMEOUT_SECONDS = 120.0
INTENDED_CASES = 48
INTENDED_CELLS = 192
RETRYABLE_ERROR_TYPES = frozenset({"connectivity", "http_5xx", "timeout", "malformed_response"})
CONDITIONS = ("R0", "R1", "R2", "R3")


RETRIEVAL_CONDITIONS: dict[str, dict[str, Any]] = {
    "R0": {
        "implementation": "RetrievalEngine BM25-like lexical scoring",
        "provider": "local deterministic",
        "model": "BM25-like lexical baseline",
        "candidate_depth": None,
        "fusion_method": None,
        "rerank_depth": None,
        "final_top_k": FINAL_TOP_K,
    },
    "R1": {
        "implementation": "RetrievalEngine dense cosine similarity",
        "provider": "siliconflow",
        "model": "BAAI/bge-m3",
        "candidate_depth": "all topic-filtered corpus chunks",
        "fusion_method": None,
        "rerank_depth": None,
        "final_top_k": FINAL_TOP_K,
    },
    "R2": {
        "implementation": "RetrievalEngine reciprocal-rank fusion of lexical and dense rankings",
        "provider": "local lexical + siliconflow dense",
        "model": "BM25-like lexical + BAAI/bge-m3",
        "candidate_depth": "all topic-filtered corpus chunks",
        "fusion_method": f"RRF: 1/({RRF_CONSTANT}+lexical_rank) + 1/({RRF_CONSTANT}+dense_rank)",
        "rerank_depth": None,
        "final_top_k": FINAL_TOP_K,
    },
    "R3": {
        "implementation": "RetrievalEngine hybrid RRF candidates followed by remote reranking",
        "provider": "siliconflow",
        "model": "BAAI/bge-m3 + BAAI/bge-reranker-v2-m3",
        "candidate_depth": CANDIDATE_DEPTH,
        "fusion_method": f"RRF with constant {RRF_CONSTANT}",
        "rerank_depth": CANDIDATE_DEPTH,
        "final_top_k": FINAL_TOP_K,
    },
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_frozen_inputs(repository_root: Path) -> dict[str, str]:
    benchmark_root = repository_root / "research/benchmarks/western_pilot_v0_1"
    corpus_root = repository_root / "research/corpus/west_v0_1"
    actual = {
        "benchmark_sha256": _sha256(benchmark_root / "benchmark.jsonl"),
        "manifest_sha256": _sha256(benchmark_root / "benchmark_manifest.json"),
        "corpus_chunks_sha256": _sha256(corpus_root / "chunks.jsonl"),
        "source_registry_sha256": _sha256(corpus_root / "source_registry.json"),
    }
    expected = {
        "benchmark_sha256": BENCHMARK_SHA256,
        "manifest_sha256": BENCHMARK_MANIFEST_SHA256,
        "corpus_chunks_sha256": CORPUS_CHUNKS_SHA256,
        "source_registry_sha256": SOURCE_REGISTRY_SHA256,
    }
    mismatches = {key: {"expected": expected[key], "actual": value} for key, value in actual.items() if value != expected[key]}
    if mismatches:
        raise RuntimeError(f"Frozen input mismatch: {json.dumps(mismatches, sort_keys=True)}")
    return actual


def load_frozen_cases(repository_root: Path) -> list[dict[str, Any]]:
    cases, errors = load_benchmark(repository_root / "research/benchmarks/western_pilot_v0_1/benchmark.jsonl")
    if errors:
        raise RuntimeError(f"Frozen benchmark parse failure: {errors}")
    if len(cases) != INTENDED_CASES:
        raise RuntimeError(f"Expected {INTENDED_CASES} frozen cases, found {len(cases)}")
    return cases


def experiment_id(case_id: str, retrieval_condition: str) -> str:
    if retrieval_condition not in CONDITIONS:
        raise ValueError(f"Unknown retrieval condition: {retrieval_condition}")
    return f"{PROTOCOL_VERSION}:{case_id}:{retrieval_condition}"


def balanced_execution_order(cases: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    order: list[dict[str, Any]] = []
    for case_index, case in enumerate(cases):
        rotation = CONDITIONS[case_index % len(CONDITIONS):] + CONDITIONS[:case_index % len(CONDITIONS)]
        for within_case_index, condition in enumerate(rotation):
            order.append({
                "sequence": len(order) + 1,
                "case_index": case_index + 1,
                "within_case_index": within_case_index + 1,
                "case_id": case["case_id"],
                "retrieval_condition": condition,
                "experiment_id": experiment_id(case["case_id"], condition),
            })
    if len(order) != INTENDED_CELLS or len({row["experiment_id"] for row in order}) != INTENDED_CELLS:
        raise RuntimeError("Balanced execution order did not produce 192 unique cells")
    return order


def headline_retrieval_case_ids(cases: Iterable[dict[str, Any]]) -> set[str]:
    return {
        case["case_id"]
        for case in cases
        if case["answerability"] in {"supported", "partially_supported"} and case["gold_chunk_ids"]
    }


def insufficient_case_ids(cases: Iterable[dict[str, Any]]) -> set[str]:
    return {case["case_id"] for case in cases if case["answerability"] == "insufficient"}


def build_formal_provider_bundle() -> ProviderBundle:
    settings = get_settings()
    shared_key = settings.embedding_api_key or settings.rerank_api_key or settings.llm_api_key
    if not shared_key:
        raise ProviderUnavailable("SiliconFlow credential is missing", error_type="configuration")
    base = get_provider_bundle()
    embedding = SiliconFlowEmbeddingProvider(
        api_key=shared_key,
        base_url=settings.embedding_base_url or settings.llm_base_url,
        model="BAAI/bge-m3",
    )
    reranker = SiliconFlowRerankProvider(
        api_key=shared_key,
        base_url=settings.rerank_base_url or settings.llm_base_url,
        model="BAAI/bge-reranker-v2-m3",
    )
    return replace(base, embedding=embedding, rerank=reranker)


def build_formal_retrieval_engine(repository_root: Path) -> RetrievalEngine:
    verify_frozen_inputs(repository_root)
    corpus = load_runtime_corpus(repository_root / "research/corpus/west_v0_1")
    return RetrievalEngine(
        formal_strict=True,
        persistent_cache=True,
        cache_dir=repository_root / "research/experiments/western_formal_v0_1/cache",
        embedding_batch_size=64,
        candidate_depth=CANDIDATE_DEPTH,
        chunks=corpus.chunks,
        sources=corpus.sources,
        providers=build_formal_provider_bundle(),
        corpus_sha256=CORPUS_CHUNKS_SHA256,
    )


def _error_type(exc: Exception) -> str:
    return str(getattr(exc, "error_type", "content_or_schema_failure"))


@dataclass(frozen=True)
class RetryOutcome:
    value: Any | None
    first_attempt_success: bool
    attempt_count: int
    technical_retry_used: bool
    first_error_type: str | None
    final_success: bool
    errors: list[dict[str, Any]]
    elapsed_ms: float


async def invoke_with_technical_retry(operation: Callable[[], Awaitable[Any]]) -> RetryOutcome:
    started = perf_counter()
    errors: list[dict[str, Any]] = []
    first_error_type: str | None = None
    for attempt in (1, 2):
        try:
            value = await operation()
            return RetryOutcome(
                value=value,
                first_attempt_success=attempt == 1,
                attempt_count=attempt,
                technical_retry_used=attempt == 2,
                first_error_type=first_error_type,
                final_success=True,
                errors=errors,
                elapsed_ms=round((perf_counter() - started) * 1000, 3),
            )
        except Exception as exc:
            kind = _error_type(exc)
            if first_error_type is None:
                first_error_type = kind
            errors.append({"attempt": attempt, "error_type": kind, "message": str(exc)})
            if attempt == 2 or kind not in RETRYABLE_ERROR_TYPES:
                return RetryOutcome(
                    value=None,
                    first_attempt_success=False,
                    attempt_count=attempt,
                    technical_retry_used=attempt == 2,
                    first_error_type=first_error_type,
                    final_success=False,
                    errors=errors,
                    elapsed_ms=round((perf_counter() - started) * 1000, 3),
                )
    raise AssertionError("unreachable")


def _assert_no_secret_fields(value: Any, path: str = "root") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = str(key).casefold()
            if normalized in {"authorization", "password", "secret", "api_key", "access_token", "refresh_token"} or normalized.endswith("_api_key"):
                raise ValueError(f"Secret-bearing field is forbidden in formal output: {path}.{key}")
            _assert_no_secret_fields(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _assert_no_secret_fields(item, f"{path}[{index}]")


def _atomic_new_json(path: Path, payload: dict[str, Any]) -> None:
    _assert_no_secret_fields(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    if path.exists() or temporary.exists():
        raise FileExistsError(f"Immutable output already exists: {path}")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


class RunDirectory:
    STAGE_FILES = {"A": "stage_a_retrieval.jsonl", "B": "stage_b_generation.jsonl", "C": "stage_c_judge.jsonl"}

    def __init__(self, path: Path) -> None:
        self.path = path

    @classmethod
    def create(cls, runs_root: Path, run_id: str) -> "RunDirectory":
        path = runs_root / run_id
        path.mkdir(parents=True, exist_ok=False)
        instance = cls(path)
        _atomic_new_json(path / "run_manifest.json", {
            "run_id": run_id,
            "protocol_version": PROTOCOL_VERSION,
            "benchmark_version": BENCHMARK_VERSION,
            "benchmark_sha256": BENCHMARK_SHA256,
            "created_at": _utc_now(),
            "status": "in_progress",
        })
        return instance

    @classmethod
    def resume(cls, path: Path) -> "RunDirectory":
        if not (path / "run_manifest.json").is_file():
            raise FileNotFoundError("Run manifest is missing")
        return cls(path)

    def stage_path(self, stage: str) -> Path:
        return self.path / self.STAGE_FILES[stage]

    def stage_manifest_path(self, stage: str) -> Path:
        return self.path / f"stage_{stage.casefold()}_manifest.json"

    def completed_ids(self, stage: str) -> set[str]:
        path = self.stage_path(stage)
        if not path.exists():
            return set()
        return {
            json.loads(line)["experiment_id"]
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        }

    def append(self, stage: str, record: dict[str, Any]) -> None:
        if self.stage_manifest_path(stage).exists():
            raise RuntimeError(f"Stage {stage} is sealed and immutable")
        predecessor = {"B": "A", "C": "B"}.get(stage)
        if predecessor is not None:
            if not self.stage_manifest_path(predecessor).exists():
                raise RuntimeError(f"Stage {predecessor} must be sealed before Stage {stage}")
            self.verify_sealed(predecessor)
        _assert_no_secret_fields(record)
        completed = self.completed_ids(stage)
        if record["experiment_id"] in completed:
            raise ValueError(f"Duplicate experiment cell: {record['experiment_id']}")
        path = self.stage_path(stage)
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def seal(self, stage: str, *, expected_cells: int = INTENDED_CELLS) -> dict[str, Any]:
        path = self.stage_path(stage)
        records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        ids = [item["experiment_id"] for item in records]
        if len(records) != expected_cells or len(set(ids)) != expected_cells:
            raise RuntimeError(f"Stage {stage} requires {expected_cells} unique cells before sealing")
        payload = {
            "stage": stage,
            "cell_count": len(records),
            "sha256": _sha256(path),
            "sealed_at": _utc_now(),
            "immutable_input_for": {"A": "B", "B": "C", "C": "final analysis"}[stage],
        }
        _atomic_new_json(self.stage_manifest_path(stage), payload)
        return payload

    def verify_sealed(self, stage: str) -> None:
        manifest = json.loads(self.stage_manifest_path(stage).read_text(encoding="utf-8"))
        if manifest["sha256"] != _sha256(self.stage_path(stage)):
            raise RuntimeError(f"Sealed Stage {stage} hash mismatch")


def _base_record(case: dict[str, Any], condition: str) -> dict[str, Any]:
    return {
        "experiment_id": experiment_id(case["case_id"], condition),
        "protocol_version": PROTOCOL_VERSION,
        "benchmark_version": BENCHMARK_VERSION,
        "benchmark_sha256": BENCHMARK_SHA256,
        "case_id": case["case_id"],
        "question": case["question"],
        "topic": case["topic"],
        "question_type": case["question_type"],
        "answerability": case["answerability"],
        "retrieval_condition": condition,
        "retrieval_config": RETRIEVAL_CONDITIONS[condition],
        "gold_primary_chunk_ids": case["gold_chunk_ids"],
        "gold_primary_source_ids": case["gold_source_ids"],
        "gold_secondary_chunk_ids": case["optional_secondary_chunk_ids"],
        "expected_evidence_points": case["expected_evidence_points"],
        "generator_provider": GENERATOR_PROVIDER,
        "generator_model": GENERATOR_MODEL,
        "temperature": GENERATOR_TEMPERATURE,
        "max_tokens": GENERATOR_MAX_TOKENS,
        "judge_provider": JUDGE_PROVIDER,
        "judge_model": JUDGE_MODEL,
    }


async def run_stage_a(repository_root: Path, run: RunDirectory, *, engine: RetrievalEngine | None = None) -> None:
    verify_frozen_inputs(repository_root)
    cases = load_frozen_cases(repository_root)
    cases_by_id = {case["case_id"]: case for case in cases}
    engine = engine or build_formal_retrieval_engine(repository_root)
    chunk_lookup = {chunk.chunk_id: chunk for chunk in engine.chunks}
    completed = run.completed_ids("A")
    for cell in balanced_execution_order(cases):
        if cell["experiment_id"] in completed:
            continue
        case = cases_by_id[cell["case_id"]]
        condition = cell["retrieval_condition"]
        started = perf_counter()
        results = await engine.search(
            case["question"],
            strategy=RetrievalStrategy(condition),
            top_k=FINAL_TOP_K,
            topics=[case["topic"]],
        )
        latency = round((perf_counter() - started) * 1000, 3)
        retrieved_items = []
        for item in results:
            chunk = chunk_lookup[item.chunk_id]
            source = item.source_metadata
            retrieved_items.append({
                "chunk_id": item.chunk_id,
                "source_id": item.source_id,
                "rank": item.rank,
                "article_title": source.get("title", ""),
                "section": chunk.section,
                "source_url": source.get("source_url", ""),
                "pmcid": source.get("pmcid", ""),
                "doi": source.get("doi", ""),
                "license": source.get("license", ""),
                "domain": "western",
                "evidence_excerpt": item.chunk_text[:WESTERN_EVIDENCE_EXCERPT_CHARS],
                "lexical_score": item.lexical_score,
                "semantic_score": item.semantic_score,
                "fusion_score": item.fusion_score,
                "rerank_score": item.rerank_score,
            })
        record = {
            **_base_record(case, condition),
            "retrieval_latency_ms": latency,
            "retrieved_items": retrieved_items,
            "errors": [],
            "timestamps": {"retrieval_completed_at": _utc_now()},
        }
        run.append("A", record)
    run.seal("A")


def _retrieval_evidence(items: list[dict[str, Any]], topic: str) -> list[WesternRetrievalEvidence]:
    return [
        WesternRetrievalEvidence(
            chunk_id=item["chunk_id"], source_id=item["source_id"], rank=item["rank"],
            lexical_score=float(item.get("lexical_score") or 0.0), article_title=item["article_title"],
            section=item["section"], pmcid=item["pmcid"], doi=item["doi"], source_url=item["source_url"],
            license=item["license"], topic=WesternTopic(topic), text=item["evidence_excerpt"], provenance={},
        )
        for item in items
    ]


async def run_stage_b(repository_root: Path, run: RunDirectory, *, generator: Any | None = None) -> None:
    verify_frozen_inputs(repository_root)
    run.verify_sealed("A")
    generator = generator or build_llm_provider(GENERATOR_MODEL, timeout_override=GENERATOR_TIMEOUT_SECONDS)
    stage_a = [json.loads(line) for line in run.stage_path("A").read_text(encoding="utf-8").splitlines() if line.strip()]
    completed = run.completed_ids("B")
    for retrieval in stage_a:
        if retrieval["experiment_id"] in completed:
            continue
        evidence = _retrieval_evidence(retrieval["retrieved_items"], retrieval["topic"])
        prompt = _generation_prompt(retrieval["question"] if "question" in retrieval else "", retrieval["topic"], evidence)

        async def operation() -> Any:
            result = await generator.generate(
                system=SYSTEM_PROMPT,
                prompt=prompt,
                temperature=GENERATOR_TEMPERATURE,
                max_tokens=GENERATOR_MAX_TOKENS,
            )
            return result, _validated_answer(result.text)

        outcome = await invoke_with_technical_retry(operation)
        generated, answer = outcome.value if outcome.final_success else (None, "")
        provenance = [
            {key: item[key] for key in ("chunk_id", "source_id", "article_title", "section", "source_url", "pmcid", "doi", "license")}
            for item in retrieval["retrieved_items"]
        ]
        record = {
            "experiment_id": retrieval["experiment_id"],
            "first_attempt_success": outcome.first_attempt_success,
            "attempt_count": outcome.attempt_count,
            "technical_retry_used": outcome.technical_retry_used,
            "first_error_type": outcome.first_error_type,
            "generation_success": outcome.final_success,
            "final_generation_success": outcome.final_success,
            "generation_outcome": "completed" if outcome.final_success else "technical_failure_or_nonretryable_failure",
            "generation_latency_ms": outcome.elapsed_ms,
            "answer": answer,
            "provenance": provenance,
            "provider_reported_model": generated.model if generated else GENERATOR_MODEL,
            "errors": outcome.errors,
            "timestamps": {"generation_completed_at": _utc_now()},
        }
        run.append("B", record)
    run.seal("B")


async def run_stage_c(repository_root: Path, run: RunDirectory, *, judge: Any | None = None) -> None:
    verify_frozen_inputs(repository_root)
    run.verify_sealed("A")
    run.verify_sealed("B")
    judge = judge or build_llm_provider(JUDGE_MODEL, timeout_override=JUDGE_TIMEOUT_SECONDS)
    stage_a = {item["experiment_id"]: item for item in _read_jsonl(run.stage_path("A"))}
    stage_b = _read_jsonl(run.stage_path("B"))
    completed = run.completed_ids("C")
    for generation in stage_b:
        cell_id = generation["experiment_id"]
        if cell_id in completed:
            continue
        retrieval = stage_a[cell_id]
        if not generation["generation_success"]:
            run.append("C", {
                "experiment_id": cell_id,
                "judge_success": False,
                "judge_latency_ms": 0.0,
                "claim_labels": [],
                "evidence_point_labels": [],
                "insufficiency_label": "not_applicable",
                "errors": [{"error_type": "generation_missing", "message": "Judge excluded after generation failure"}],
                "timestamps": {"judge_completed_at": _utc_now()},
            })
            continue
        prompt = build_judge_prompt(
            question=retrieval.get("question", ""),
            answer=generation["answer"],
            retrieved_evidence=retrieval["retrieved_items"],
            expected_evidence_points=retrieval["expected_evidence_points"],
            answerability=retrieval["answerability"],
        )

        async def operation() -> Any:
            result = await judge.generate(
                system=JUDGE_SYSTEM_PROMPT,
                prompt=prompt,
                temperature=JUDGE_TEMPERATURE,
                max_tokens=JUDGE_MAX_TOKENS,
            )
            try:
                parsed = parse_judge_output(result.text)
            except ValueError as exc:
                raise RuntimeError(str(exc)) from exc
            return result, parsed

        outcome = await invoke_with_technical_retry(operation)
        provider_result, parsed = outcome.value if outcome.final_success else (None, None)
        record = {
            "experiment_id": cell_id,
            "judge_success": outcome.final_success,
            "judge_latency_ms": outcome.elapsed_ms,
            "judge_attempt_count": outcome.attempt_count,
            "judge_technical_retry_used": outcome.technical_retry_used,
            "judge_provider_reported_model": provider_result.model if provider_result else JUDGE_MODEL,
            "claim_labels": [item.model_dump(mode="json") for item in parsed.claim_labels] if parsed else [],
            "evidence_point_labels": [item.model_dump(mode="json") for item in parsed.evidence_point_labels] if parsed else [],
            "insufficiency_label": parsed.insufficiency_label if parsed else "not_applicable",
            "observable_safety_flags": {
                "diagnosis_like_personalized_statement": parsed.diagnosis_like_personalized_statement,
                "individualized_dosing": parsed.individualized_dosing,
                "prescription_like_recommendation": parsed.prescription_like_recommendation,
                "research_or_educational_limitation_preserved": parsed.research_or_educational_limitation_preserved,
            } if parsed else {},
            "errors": outcome.errors,
            "timestamps": {"judge_completed_at": _utc_now()},
        }
        run.append("C", record)
    run.seal("C")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def retrieval_metrics(records: list[dict[str, Any]], cases: list[dict[str, Any]]) -> dict[str, Any]:
    eligible = headline_retrieval_case_ids(cases)
    output: dict[str, Any] = {"eligible_case_count": len(eligible), "insufficient_case_count": len(insufficient_case_ids(cases)), "by_condition": {}}
    for condition in CONDITIONS:
        rows = [row for row in records if row["retrieval_condition"] == condition and row["case_id"] in eligible]
        chunk_recalls: list[float] = []
        source_recalls: list[float] = []
        reciprocal_ranks: list[float] = []
        hits = total_chunks = source_hits = total_sources = hit_cases = 0
        secondary_hit_cases = 0
        for row in rows:
            retrieved = [item["chunk_id"] for item in row["retrieved_items"]]
            retrieved_sources = {item["source_id"] for item in row["retrieved_items"]}
            primary = row["gold_primary_chunk_ids"]
            primary_sources = row["gold_primary_source_ids"]
            row_hits = sum(1 for item in primary if item in retrieved)
            row_source_hits = sum(1 for item in primary_sources if item in retrieved_sources)
            hits += row_hits
            total_chunks += len(primary)
            source_hits += row_source_hits
            total_sources += len(primary_sources)
            chunk_recalls.append(row_hits / len(primary))
            source_recalls.append(row_source_hits / len(primary_sources))
            ranks = [retrieved.index(item) + 1 for item in primary if item in retrieved]
            reciprocal_ranks.append(1 / min(ranks) if ranks else 0.0)
            hit_cases += bool(ranks)
            primary_or_secondary = set(primary) | set(row.get("gold_secondary_chunk_ids", []))
            secondary_hit_cases += any(item in primary_or_secondary for item in retrieved)
        output["by_condition"][condition] = {
            "case_count": len(rows),
            "macro_primary_gold_chunk_recall_at_4": sum(chunk_recalls) / len(rows),
            "aggregate_primary_gold_chunk_recall_at_4": hits / total_chunks,
            "macro_primary_source_recall_at_4": sum(source_recalls) / len(rows),
            "aggregate_primary_source_recall_at_4": source_hits / total_sources,
            "mrr": sum(reciprocal_ranks) / len(rows),
            "hit_at_4": hit_cases / len(rows),
            "primary_or_secondary_hit_at_4": secondary_hit_cases / len(rows),
            "aggregate_primary_hits": hits,
            "aggregate_primary_total": total_chunks,
            "aggregate_source_hits": source_hits,
            "aggregate_source_total": total_sources,
        }
    return output


def judge_metrics(completed_records: list[dict[str, Any]]) -> dict[str, Any]:
    successful = [row for row in completed_records if row.get("judge_success")]
    totals = {"supported": 0, "partially_supported": 0, "unsupported": 0, "not_checkable": 0, "checkable": 0}
    point_totals = {"covered": 0, "partially_covered": 0, "not_covered": 0, "contradicted": 0}
    answers_with_unsupported = 0
    for row in successful:
        labels = parse_judge_output(json.dumps({
            "claim_labels": row["claim_labels"],
            "evidence_point_labels": row["evidence_point_labels"],
            "insufficiency_label": row["insufficiency_label"],
            **row.get("observable_safety_flags", {}),
            "stays_within_supported_evidence": None,
            "preserves_uncertainty": None,
            "invented_unsupported_information": None,
        }))
        counts = checkable_claim_counts(labels)
        for key in totals:
            totals[key] += counts[key]
        answers_with_unsupported += counts["unsupported"] > 0
        for item in labels.evidence_point_labels:
            point_totals[item.label] += 1
    checkable = totals["checkable"]
    total_points = sum(point_totals.values())
    return {
        "completed_judgments": len(successful),
        "claim_support_rate": totals["supported"] / checkable if checkable else None,
        "partially_supported_claim_rate": totals["partially_supported"] / checkable if checkable else None,
        "unsupported_claim_rate": totals["unsupported"] / checkable if checkable else None,
        "answers_with_any_unsupported_claim": answers_with_unsupported,
        "mean_unsupported_claims_per_completed_answer": totals["unsupported"] / len(successful) if successful else None,
        "evidence_point_coverage_rate": point_totals["covered"] / total_points if total_points else None,
        "evidence_point_partial_coverage_rate": point_totals["partially_covered"] / total_points if total_points else None,
        "claim_counts": totals,
        "evidence_point_counts": point_totals,
    }


def provenance_integrity(
    retrieved_items: list[dict[str, Any]],
    provenance: list[dict[str, Any]],
    known_source_ids: set[str],
) -> tuple[bool, list[str]]:
    errors: list[str] = []
    retrieved_by_chunk = {item["chunk_id"]: item for item in retrieved_items}
    if len(provenance) != len(retrieved_items):
        errors.append("provenance count differs from retrieved item count")
    for item in provenance:
        retrieved = retrieved_by_chunk.get(item.get("chunk_id"))
        if retrieved is None:
            errors.append("provenance chunk is outside actual top_k")
            continue
        if item.get("source_id") not in known_source_ids:
            errors.append("provenance source does not resolve")
        if not item.get("source_url"):
            errors.append("provenance source URL is missing")
        if not str(item.get("chunk_id", "")).startswith("west-") or retrieved.get("domain") != "western":
            errors.append("non-Western or TCM evidence detected")
        for field in ("source_id", "article_title", "section", "source_url", "pmcid", "doi", "license"):
            if item.get(field) != retrieved.get(field):
                errors.append(f"application provenance mismatch for {field}")
    return not errors, errors


def generation_metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(records)
    first_successes = sum(bool(row["first_attempt_success"]) for row in records)
    completions = sum(bool(row["generation_success"]) for row in records)
    retries = sum(bool(row["technical_retry_used"]) for row in records)
    return {
        "cell_count": total,
        "first_attempt_success_rate": first_successes / total if total else None,
        "final_completion_rate": completions / total if total else None,
        "technical_failure_count": total - completions,
        "retry_count": retries,
        "completed_answer_count": completions,
        "semantic_answer_quality_denominator": completions,
    }


def finalize_run(repository_root: Path, run: RunDirectory) -> None:
    verify_frozen_inputs(repository_root)
    for stage in ("A", "B", "C"):
        run.verify_sealed(stage)
    stage_a = {row["experiment_id"]: row for row in _read_jsonl(run.stage_path("A"))}
    stage_b = {row["experiment_id"]: row for row in _read_jsonl(run.stage_path("B"))}
    stage_c = {row["experiment_id"]: row for row in _read_jsonl(run.stage_path("C"))}
    if set(stage_a) != set(stage_b) or set(stage_a) != set(stage_c):
        raise RuntimeError("Stage cell identities differ")
    raw_path = run.path / "raw_results.jsonl"
    temporary = raw_path.with_suffix(".jsonl.tmp")
    if raw_path.exists() or temporary.exists():
        raise FileExistsError("Immutable raw formal results already exist")
    with temporary.open("x", encoding="utf-8", newline="\n") as handle:
        for cell_id in stage_a:
            retrieval = stage_a[cell_id]
            generation = stage_b[cell_id]
            judgment = stage_c[cell_id]
            record = {**retrieval, **generation, **judgment}
            record["errors"] = retrieval.get("errors", []) + generation.get("errors", []) + judgment.get("errors", [])
            record["timestamps"] = {
                **retrieval.get("timestamps", {}),
                **generation.get("timestamps", {}),
                **judgment.get("timestamps", {}),
            }
            _assert_no_secret_fields(record)
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(raw_path)
    cases = load_frozen_cases(repository_root)
    _atomic_new_json(run.path / "retrieval_metrics.json", retrieval_metrics(list(stage_a.values()), cases))
    _atomic_new_json(run.path / "generation_metrics.json", generation_metrics(list(stage_b.values())))
    _atomic_new_json(run.path / "judge_metrics.json", judge_metrics(list(stage_c.values())))
    _atomic_new_json(run.path / "provider_metrics.json", {
        **generation_metrics(list(stage_b.values())),
        "judge_completion_rate": sum(bool(row["judge_success"]) for row in stage_c.values()) / len(stage_c),
        "generation_latency_ms_total": sum(float(row["generation_latency_ms"]) for row in stage_b.values()),
        "judge_latency_ms_total": sum(float(row["judge_latency_ms"]) for row in stage_c.values()),
        "retrieval_latency_ms_total": sum(float(row["retrieval_latency_ms"]) for row in stage_a.values()),
    })
    _atomic_new_json(run.path / "completion_manifest.json", {
        "protocol_version": PROTOCOL_VERSION,
        "cell_count": len(stage_a),
        "raw_results_sha256": _sha256(raw_path),
        "stage_a_sha256": _sha256(run.stage_path("A")),
        "stage_b_sha256": _sha256(run.stage_path("B")),
        "stage_c_sha256": _sha256(run.stage_path("C")),
        "completed_at": _utc_now(),
        "total_experiment_elapsed_time_source": "sum of separately recorded retrieval, generation, and judge latency fields",
    })
