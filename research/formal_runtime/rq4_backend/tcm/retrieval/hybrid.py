from __future__ import annotations

import os
import time

from ..knowledge_base import KNOWLEDGE_BASE, KnowledgeEntry
from .lexical import retrieve_lexical
from .reranker import RerankerUnavailable, rerank
from .scoring import RetrievalDiagnostics, RetrievalResult, dedupe_results
from .semantic import SemanticRetrievalUnavailable, retrieve_semantic, semantic_enabled


def _config_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _config_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def retrieval_config() -> dict[str, int | float | str | bool]:
    return {
        "mode": os.getenv("RETRIEVAL_MODE", "hybrid").strip().casefold() or "hybrid",
        "top_k_candidates": _config_int("TOP_K_CANDIDATES", 10),
        "top_k_evidence": _config_int("TOP_K_EVIDENCE", 4),
        "min_relevance_score": _config_float("MIN_RELEVANCE_SCORE", 0.18),
        "enable_semantic": semantic_enabled(),
        "enable_rerank": os.getenv("ENABLE_RERANK", "true").strip().casefold() in {"1", "true", "yes", "on"},
    }


async def retrieve(
    query: str,
    context_text: str = "",
    *,
    entries: tuple[KnowledgeEntry, ...] = KNOWLEDGE_BASE,
) -> tuple[list[RetrievalResult], RetrievalDiagnostics]:
    retrieval_started = time.perf_counter()
    config = retrieval_config()
    mode = str(config["mode"])
    top_k_candidates = int(config["top_k_candidates"])
    top_k_evidence = int(config["top_k_evidence"])
    threshold = float(config["min_relevance_score"])
    retrieval_query = f"{query} {context_text}".strip()
    notes: list[str] = []

    lexical_started = time.perf_counter()
    lexical = retrieve_lexical(retrieval_query, entries=entries, top_k=top_k_candidates)
    lexical_ms = (time.perf_counter() - lexical_started) * 1000
    semantic_ms = 0.0
    reranking_ms = 0.0
    method = "lexical"
    candidates = lexical

    if mode in {"semantic", "hybrid", "hybrid_reranked"} and bool(config["enable_semantic"]):
      semantic_started = time.perf_counter()
      try:
          semantic = await retrieve_semantic(retrieval_query, entries, top_k=top_k_candidates)
      except SemanticRetrievalUnavailable as exc:
          notes.append(str(exc))
          if mode == "semantic":
              candidates = []
              method = "semantic"
      else:
          method = "semantic" if mode == "semantic" else "hybrid"
          by_id: dict[str, RetrievalResult] = {item.entry.entry_id: item for item in lexical}
          for semantic_item in semantic:
              old = by_id.get(semantic_item.entry.entry_id)
              if old:
                  combined = round(min(1.0, old.score * 0.58 + semantic_item.score * 0.42), 3)
                  matched = old.matched_terms
                  breakdown = {**old.score_breakdown, **semantic_item.score_breakdown, "combined_score": combined}
              else:
                  combined = round(semantic_item.score * 0.75, 3)
                  matched = semantic_item.matched_terms
                  breakdown = {**semantic_item.score_breakdown, "combined_score": combined}
              by_id[semantic_item.entry.entry_id] = RetrievalResult(
                  entry=semantic_item.entry,
                  score=combined,
                  matched_terms=matched,
                  score_breakdown=breakdown,
              )
          candidates = dedupe_results(list(by_id.values()))[:top_k_candidates]
      semantic_ms = (time.perf_counter() - semantic_started) * 1000

    if method == "hybrid" and bool(config["enable_rerank"]):
        reranking_started = time.perf_counter()
        try:
            candidates = await rerank(retrieval_query, candidates)
        except RerankerUnavailable as exc:
            notes.append(str(exc))
        else:
            method = "hybrid_reranked"
        reranking_ms = (time.perf_counter() - reranking_started) * 1000

    meaningful = [item for item in candidates if item.score >= threshold]
    meaningful.sort(key=lambda item: item.score, reverse=True)
    evidence = meaningful[:top_k_evidence]
    diagnostics = RetrievalDiagnostics(
        retrieval_method=method,
        candidate_count=len(candidates),
        meaningful_match_count=len(meaningful),
        top_relevance_score=round(evidence[0].score if evidence else 0.0, 3),
        min_relevance_score=threshold,
        notes=tuple(notes),
        lexical_ms=round(lexical_ms, 3),
        semantic_ms=round(semantic_ms, 3),
        reranking_ms=round(reranking_ms, 3),
        total_ms=round((time.perf_counter() - retrieval_started) * 1000, 3),
    )
    return evidence, diagnostics
