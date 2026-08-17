from __future__ import annotations

from schemas.research import ConditionId


COMMON = {
    "planner": "deterministic",
    "specialist_generation": "one LLM call per evidence-participating specialist when RESEARCH_REAL_LLM_ENABLED=true; otherwise deterministic",
    "final_synthesis": "deterministic evidence-linked aggregation",
}

CONDITION_REGISTRY = [
    {**COMMON, "id": "C0", "name": "direct_llm", "retrieval": False, "multi_agent": False, "specialist_generation": "none", "final_synthesis": "direct LLM response when enabled; otherwise an explicit deterministic control message", "aggregation": "direct", "debate": False, "judges": False, "expected_provider_calls": "1 when real LLM execution is enabled; otherwise 0", "purpose": "No-retrieval control baseline."},
    {**COMMON, "id": "C1", "name": "single_rag", "retrieval": True, "multi_agent": False, "aggregation": "single", "debate": False, "judges": False, "expected_provider_calls": "1 for an evidence-backed run when real LLM execution is enabled; otherwise 0", "purpose": "Conventional TCM RAG baseline."},
    {**COMMON, "id": "C2", "name": "multi_agent_rag", "retrieval": True, "multi_agent": True, "aggregation": "independent", "debate": False, "judges": False, "expected_provider_calls": "one per non-abstaining specialist when real LLM execution is enabled; otherwise 0", "purpose": "Independent TCM specialists."},
    {**COMMON, "id": "C3", "name": "multi_agent_weighted", "retrieval": True, "multi_agent": True, "aggregation": "deterministic_weighted", "debate": False, "judges": False, "expected_provider_calls": "one per non-abstaining specialist when real LLM execution is enabled; otherwise 0", "purpose": "Deterministic evidence/support weighting."},
    {**COMMON, "id": "C4", "name": "multi_agent_debate", "retrieval": True, "multi_agent": True, "aggregation": "critique_revision", "debate": "deterministic", "judges": False, "expected_provider_calls": "one per non-abstaining specialist when real LLM execution is enabled; debate adds 0", "purpose": "Structured deterministic TCM within-paradigm critique/revision."},
    {**COMMON, "id": "C5", "name": "multi_agent_judge", "retrieval": True, "multi_agent": True, "aggregation": "judge_arbitration", "debate": False, "judges": "deterministic", "expected_provider_calls": "one per non-abstaining specialist when real LLM execution is enabled; judges add 0", "purpose": "Deterministic rubric-judge arbitration."},
    {**COMMON, "id": "C6", "name": "multi_agent_debate_judge", "retrieval": True, "multi_agent": True, "aggregation": "debate_judge", "debate": "deterministic", "judges": "deterministic", "expected_provider_calls": "one per non-abstaining specialist when real LLM execution is enabled; debate/judges add 0", "purpose": "Specialist generation plus deterministic debate and judge baselines."},
]

CONDITIONS = {ConditionId(item["id"]): item for item in CONDITION_REGISTRY}
