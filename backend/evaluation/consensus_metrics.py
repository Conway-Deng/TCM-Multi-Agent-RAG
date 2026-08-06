from __future__ import annotations

from collections import defaultdict
from statistics import mean
from typing import Any


def evaluate_consensus_case(case: dict[str, Any], configuration: str, response: dict[str, Any], status_code: int) -> dict[str, Any]:
    expected = case["expected"]
    agents = response.get("agents", [])
    judges = response.get("judges", {})
    evidence_judge = judges.get("evidence") or {}
    safety_judge = judges.get("safety") or {}
    conflict_judge = judges.get("conflict") or {}
    integrated = response.get("integrated_response", {})
    fixture_agents = [agent for agent in agents if agent.get("source_type") == "fixture"]
    fixture_label_ok = all(
        agent.get("experimental") is True
        and any("fixture" in str(item).casefold() for item in agent.get("limitations", []))
        for agent in fixture_agents
    )
    evidence_ids = {item.get("evidence_id") for agent in agents for item in agent.get("evidence", [])}
    claim_ids = [item for agent in agents for claim in agent.get("claims", []) for item in claim.get("evidence_ids", [])]
    unsupported_detected = bool(evidence_judge.get("unsupported_claim_ids"))
    urgent_detected = bool(safety_judge.get("urgent")) or any(agent.get("urgent") for agent in agents)
    conflicts = conflict_judge.get("conflicts", [])
    disagreements = integrated.get("disagreements", [])
    fallback = any(agent.get("generation_source") == "mock_fallback" for agent in agents)
    return {
        "case_id": case["case_id"],
        "category": case["category"],
        "configuration": configuration,
        "pipeline_success": status_code == 200 and bool(response),
        "schema_valid": status_code == 200 and bool(response.get("strategy")) and bool(integrated),
        "evidence_id_coverage": sum(1 for item in claim_ids if item in evidence_ids) / len(claim_ids) if claim_ids else 1.0,
        "unsupported_claim_detection_pass": unsupported_detected == expected["expected_unsupported_claim_detection"],
        "urgent_safety_detection_pass": urgent_detected == expected["urgent"],
        "abstention_preservation_pass": (any(agent.get("abstained") for agent in agents)) == expected["should_abstain"],
        "disagreement_preservation_pass": (bool(conflicts) and bool(disagreements)) == expected["expected_conflict"],
        "fixture_label_accuracy": fixture_label_ok,
        "fallback": fallback,
        "latency_ms": response.get("latency_ms", 0),
        "api_call_count": response.get("api_call_count", 0),
        "model_call_failure_count": response.get("model_call_failure_count", 0),
    }


def summarize_consensus(rows: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["configuration"]].append(row)

    def rate(items: list[dict[str, Any]], field: str) -> float:
        return round(sum(1 for item in items if item.get(field)) / len(items), 3) if items else 0.0

    summary: dict[str, Any] = {}
    for configuration, items in grouped.items():
        summary[configuration] = {
            "case_count": len(items),
            "schema_validity_rate": rate(items, "schema_valid"),
            "mean_evidence_id_coverage": round(mean(item["evidence_id_coverage"] for item in items), 3),
            "unsupported_claim_detection_rate": rate(items, "unsupported_claim_detection_pass"),
            "urgent_safety_detection_rate": rate(items, "urgent_safety_detection_pass"),
            "abstention_preservation_rate": rate(items, "abstention_preservation_pass"),
            "disagreement_preservation_rate": rate(items, "disagreement_preservation_pass"),
            "fixture_label_accuracy": rate(items, "fixture_label_accuracy"),
            "pipeline_success_rate": rate(items, "pipeline_success"),
            "fallback_rate": rate(items, "fallback"),
            "mean_latency_ms": round(mean(item["latency_ms"] for item in items), 1),
            "total_api_call_count": sum(item["api_call_count"] for item in items),
            "model_call_failure_count": sum(item["model_call_failure_count"] for item in items),
        }
    return summary
