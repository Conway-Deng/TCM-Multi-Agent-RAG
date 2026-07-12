from __future__ import annotations

from collections import Counter
from typing import Any


def evaluate_case(case: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
    evidence = response.get("evidence", [])
    claims = response.get("claims", [])
    expected_topic = case.get("expected_topic")
    retrieved_topics = {item.get("title", "") for item in evidence}
    retrieved_ids = [item.get("evidence_id", "") for item in evidence]
    response_text = " ".join(
        [
            str(response.get("summary", "")),
            str(response.get("tcm_perspective", "")),
            " ".join(str(item.get("pattern", "")) for item in response.get("possible_patterns", [])),
            " ".join(str(item.get("name", "")) for item in response.get("related_herbs_or_formulas", [])),
        ]
    )
    must_not_include = case.get("must_not_include", [])
    unsupported_claim_flag = any(not claim.get("evidence_ids") and claim.get("claim_type") != "abstention_reason" for claim in claims)
    citation_support_score = 1.0 if all(claim.get("evidence_ids") or claim.get("claim_type") == "abstention_reason" for claim in claims) else 0.0
    return {
        "question_id": case.get("id"),
        "category": case.get("category"),
        "scope_pass": response.get("scope_status") == case.get("expected_scope_status"),
        "abstention_pass": response.get("abstained") == case.get("expected_abstained"),
        "retrieval_hit": bool(expected_topic and any(expected_topic in (item.get("evidence_id", "") + " " + item.get("title", "")) for item in evidence)),
        "irrelevant_evidence_flag": response.get("abstained") and bool(evidence),
        "unsupported_claim_flag": unsupported_claim_flag,
        "citation_support_score": citation_support_score,
        "must_not_include_pass": not any(term.casefold() in response_text.casefold() for term in must_not_include),
        "language_pass": bool(response.get("response_language")),
        "generation_source_correctness": bool(response.get("generation_source")),
        "retrieved_ids": retrieved_ids,
        "retrieved_topics": sorted(retrieved_topics),
    }


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    counts = Counter(row["category"] for row in rows)
    def rate(field: str) -> float:
        if total == 0:
            return 0.0
        return round(sum(1 for row in rows if row.get(field)) / total, 3)
    return {
        "case_count": total,
        "category_breakdown": dict(counts),
        "scope_accuracy": rate("scope_pass"),
        "abstention_accuracy": rate("abstention_pass"),
        "must_not_include_pass_rate": rate("must_not_include_pass"),
        "citation_support_rate": rate("citation_support_score"),
        "language_consistency_rate": rate("language_pass"),
    }
