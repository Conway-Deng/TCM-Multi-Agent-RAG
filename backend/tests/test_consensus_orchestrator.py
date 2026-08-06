from __future__ import annotations

import asyncio
import os

os.environ["LLM_API_KEY"] = ""
os.environ["ALLOW_WEST_FIXTURE"] = "true"
os.environ["ENABLE_SEMANTIC_RETRIEVAL"] = "false"
os.environ["ENABLE_REMOTE_RERANK"] = "false"

from consensus.client import ConsensusLLMError, LLMRoleResult
from consensus.orchestrator import ConsensusOrchestrator
from consensus.schemas import ConsensusConsultRequest, ModelTraceEntry


def test_no_llm_orchestration_completes_without_api_calls() -> None:
    response = asyncio.run(ConsensusOrchestrator(allow_fixture=True).run(
        ConsensusConsultRequest(question="I have trouble sleeping and lower back soreness", domains=["tcm", "western_fixture"], strategy="debate_judge", include_trace=True)
    ))
    assert response.api_call_count == 0
    assert response.fixture_used is True
    assert response.integrated_response.limitations


class FakeLLM:
    configured = True
    call_count = 0
    failure_count = 0
    trace: list[ModelTraceEntry]

    def __init__(self, fail_role: str = "") -> None:
        self.fail_role = fail_role
        self.roles: list[str] = []
        self.trace = []

    async def call_json(self, role, payload, *, evidence_ids):
        del payload
        self.call_count += 1
        self.roles.append(role)
        if role == self.fail_role:
            self.failure_count += 1
            self.trace.append(ModelTraceEntry(role=role, model="same-model", status="fallback", evidence_ids_received=evidence_ids, error="LLM role returned malformed JSON"))
            raise ConsensusLLMError("LLM role returned malformed JSON")
        data = {
            "debate": {"agreements": [], "disagreements": [], "complementary_points": [], "unsupported_assertions": [], "missing_information": [], "unresolved_conflicts": [], "recommendations_not_to_merge": [], "confidence_reductions": [], "reasoning_summary": "debate"},
            "evidence_judge": {"supported_claim_ids": [], "partially_supported_claim_ids": [], "unsupported_claim_ids": [], "citation_issues": [], "evidence_coverage_score": 0.7, "reasoning_summary": "evidence"},
            "safety_judge": {"urgent": False, "safety_flags": [], "unsafe_claim_ids": [], "missing_safety_warnings": [], "over_reassurance_detected": False, "safety_score": 0.9, "reasoning_summary": "safety"},
            "conflict_judge": {"conflicts": [], "agreements": [], "complementary_points": [], "conflict_score": 0.0},
            "confidence_judge": {"score": 0.6, "level": "medium", "reason": "controlled", "penalties": []},
            "synthesis": {"summary": "Integrated research summary.", "agreements": [], "disagreements": [], "safety_notes": [], "limitations": [], "unresolved_questions": [], "confidence": {"score": 0.6, "level": "medium", "reason": "controlled"}},
        }[role]
        self.trace.append(ModelTraceEntry(role=role, model="same-model", status="success", evidence_ids_received=evidence_ids))
        return LLMRoleResult(data=data, model="same-model", latency_ms=1)


def test_debate_judge_uses_six_independent_role_calls() -> None:
    fake = FakeLLM()
    response = asyncio.run(ConsensusOrchestrator(llm_client=fake, allow_fixture=True).run(
        ConsensusConsultRequest(question="I have trouble sleeping and lower back soreness", domains=["tcm", "western_fixture"], strategy="debate_judge", include_trace=True)
    ))
    assert fake.roles == ["debate", "evidence_judge", "safety_judge", "conflict_judge", "confidence_judge", "synthesis"]
    assert response.api_call_count == 6
    assert all(item.evidence_ids_received for item in response.model_trace)


def test_malformed_llm_json_fails_safely_to_structured_fallback() -> None:
    fake = FakeLLM(fail_role="debate")
    response = asyncio.run(ConsensusOrchestrator(llm_client=fake, allow_fixture=True).run(
        ConsensusConsultRequest(question="I have trouble sleeping and lower back soreness", domains=["tcm", "western_fixture"], strategy="debate_judge", include_trace=True)
    ))
    assert response.debate is not None
    assert response.debate.generation_source == "deterministic_fallback"
    assert response.model_call_failure_count == 1


def test_urgent_tcm_rule_cannot_be_downgraded_by_llm_judge() -> None:
    fake = FakeLLM()
    response = asyncio.run(ConsensusOrchestrator(llm_client=fake, allow_fixture=True).run(
        ConsensusConsultRequest(question="我胸口剧痛而且呼吸困难", domains=["tcm", "western_fixture"], strategy="debate_judge")
    ))
    assert response.judges.safety is not None
    assert response.judges.safety.urgent is True
    assert response.integrated_response.safety_notes
