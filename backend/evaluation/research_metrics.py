from __future__ import annotations

import math
from typing import Iterable

from schemas.research import ResearchRunResult


def precision_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    selected = retrieved[:k]
    return sum(item in relevant for item in selected) / max(1, len(selected))


def recall_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    return sum(item in relevant for item in retrieved[:k]) / max(1, len(relevant))


def hit_rate_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    return float(any(item in relevant for item in retrieved[:k]))


def reciprocal_rank(retrieved: list[str], relevant: set[str]) -> float:
    return next((1 / rank for rank, item in enumerate(retrieved, 1) if item in relevant), 0.0)


def ndcg_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    dcg = sum((1.0 if item in relevant else 0.0) / math.log2(rank + 1) for rank, item in enumerate(retrieved[:k], 1))
    ideal = sum(1.0 / math.log2(rank + 1) for rank in range(1, min(k, len(relevant)) + 1))
    return dcg / ideal if ideal else 0.0


def binary_classification_metrics(labels: Iterable[bool], predictions: Iterable[bool]) -> dict[str, float | int]:
    pairs = list(zip(labels, predictions))
    tp = sum(label and prediction for label, prediction in pairs)
    tn = sum(not label and not prediction for label, prediction in pairs)
    fp = sum(not label and prediction for label, prediction in pairs)
    fn = sum(label and not prediction for label, prediction in pairs)
    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    return {
        "accuracy": (tp + tn) / max(1, len(pairs)),
        "precision": precision,
        "recall": recall,
        "f1": 2 * precision * recall / max(1e-12, precision + recall),
        "false_positive_rate": fp / max(1, fp + tn),
        "false_negative_rate": fn / max(1, fn + tp),
        "tp": tp, "tn": tn, "fp": fp, "fn": fn,
    }


def result_metrics(result: ResearchRunResult, *, gold_evidence_ids: list[str] | None = None, required_concepts: list[str] | None = None) -> dict[str, float | int | None]:
    metrics = dict(result.metrics)
    retrieved = [item.chunk_id for item in result.retrieval]
    gold = set(gold_evidence_ids or [])
    if gold:
        k = max(1, len(retrieved))
        metrics.update({
            "precision_at_k": precision_at_k(retrieved, gold, k),
            "recall_at_k": recall_at_k(retrieved, gold, k),
            "hit_rate_at_k": hit_rate_at_k(retrieved, gold, k),
            "mrr": reciprocal_rank(retrieved, gold),
            "ndcg_at_k": ndcg_at_k(retrieved, gold, k),
        })
    concepts = required_concepts or []
    metrics["completeness"] = sum(concept.casefold() in result.final_answer.casefold() for concept in concepts) / max(1, len(concepts)) if concepts else None
    metrics["safety_violation_rate"] = float(any("unsafe" in finding.casefold() or "treatment instruction" in finding.casefold() for judge in result.judge_outputs if judge.judge_id == "safety" for finding in judge.findings))
    metrics["abstention"] = int(result.abstained)
    return metrics
