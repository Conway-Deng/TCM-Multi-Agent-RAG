from __future__ import annotations

from schemas.research import ConditionId


CONDITION_REGISTRY = [
    {"id": "C0", "name": "direct_llm", "retrieval": False, "multi_agent": False, "aggregation": "direct", "debate": False, "judges": False, "purpose": "No-retrieval control baseline."},
    {"id": "C1", "name": "single_rag", "retrieval": True, "multi_agent": False, "aggregation": "single", "debate": False, "judges": False, "purpose": "Conventional TCM RAG baseline."},
    {"id": "C2", "name": "multi_agent_rag", "retrieval": True, "multi_agent": True, "aggregation": "independent", "debate": False, "judges": False, "purpose": "Independent TCM specialists."},
    {"id": "C3", "name": "multi_agent_weighted", "retrieval": True, "multi_agent": True, "aggregation": "deterministic_weighted", "debate": False, "judges": False, "purpose": "Deterministic evidence/confidence weighting."},
    {"id": "C4", "name": "multi_agent_debate", "retrieval": True, "multi_agent": True, "aggregation": "critique_revision", "debate": True, "judges": False, "purpose": "Structured TCM within-paradigm debate."},
    {"id": "C5", "name": "multi_agent_judge", "retrieval": True, "multi_agent": True, "aggregation": "judge_arbitration", "debate": False, "judges": True, "purpose": "Judge-mediated arbitration."},
    {"id": "C6", "name": "multi_agent_debate_judge", "retrieval": True, "multi_agent": True, "aggregation": "debate_judge", "debate": True, "judges": True, "purpose": "Full TCM research pipeline."},
]

CONDITIONS = {ConditionId(item["id"]): item for item in CONDITION_REGISTRY}
