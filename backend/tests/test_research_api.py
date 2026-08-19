from __future__ import annotations

import os
from pathlib import Path
import asyncio
import sys

from fastapi.testclient import TestClient


BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
os.environ["LLM_API_KEY"] = ""
os.environ["LLM_PROVIDER"] = "mock"

from main import app
from orchestration import ResearchWorkbench
from providers.base import GenerationResult
from providers.factory import ProviderBundle
from providers.openai_compatible import ProviderUnavailable
from schemas.research import ConditionId, ResearchRequest, RetrievalStrategy


client = TestClient(app)


def research_payload(condition: str = "C6") -> dict:
    return {
        "question": "I have trouble sleeping, palpitations, and forgetfulness. How are these discussed in TCM teaching?",
        "condition_id": condition,
        "retrieval_strategy": "R2",
        "active_agents": ["syndrome", "herbal", "constitution", "lifestyle_yangsheng"],
        "active_judges": ["evidence", "hallucination", "safety", "conflict", "confidence", "provenance"],
        "top_k": 4,
        "debate_rounds": 1,
        "include_trace": True,
    }


def test_research_registries_are_complete() -> None:
    conditions = client.get("/api/research/conditions").json()
    assert {item["id"] for item in conditions} == {f"C{i}" for i in range(7)}
    assert next(item for item in conditions if item["id"] == "C4")["debate"] == "deterministic"
    assert next(item for item in conditions if item["id"] == "C5")["judges"] == "deterministic"
    assert {item["id"] for item in client.get("/api/research/retrievers").json()} == {f"R{i}" for i in range(4)}
    assert {item["id"] for item in client.get("/api/research/judges").json()} == {"evidence", "hallucination", "safety", "conflict", "confidence", "provenance"}
    assert len(client.get("/api/research/agents").json()) >= 7


def test_full_c6_pipeline_runs_without_key() -> None:
    response = client.post("/api/tcm/multi-agent/consult", json=research_payload())
    assert response.status_code == 200
    data = response.json()
    assert data["condition_id"] == "C6"
    assert data["mock_mode"] is False
    assert len(data["agent_outputs"]) >= 2
    assert data["debate"]["enabled"] is True
    assert len(data["judge_outputs"]) == 6
    assert data["retrieval"]
    assert data["trace"]["git_commit"]
    assert data["trace"]["corpus_version"].startswith("tcm-")
    assert data["trace"]["prompt_hashes"]
    assert data["trace"]["provider_calls"] == 0
    assert data["trace"]["successful_provider_calls"] == 0
    assert data["trace"]["generation_mode"] == "deterministic"
    assert data["trace"]["fallback_usage"] is False
    assert all(item["provider"] == "local" for item in data["agent_outputs"])
    assert "question" not in data["trace"]["experiment_config"]


def test_claim_and_citation_ids_resolve() -> None:
    data = client.post("/api/research/run", json=research_payload("C5")).json()
    evidence_ids = {item["chunk_id"] for item in data["retrieval"]}
    assert evidence_ids
    for output in data["agent_outputs"]:
        for claim in output["claims"]:
            assert set(claim["evidence_ids"]) <= evidence_ids
        for citation in output["citations"]:
            assert citation["evidence_id"] in evidence_ids
            assert citation["provenance_valid"] is True


def test_research_compare_returns_compatible_results() -> None:
    response = client.post("/api/research/compare", json={
        "question": research_payload()["question"],
        "conditions": ["C1", "C2", "C6"],
        "retrieval_strategy": "R0",
        "top_k": 3,
    })
    assert response.status_code == 200
    data = response.json()
    assert [item["condition_id"] for item in data["results"]] == ["C1", "C2", "C6"]
    assert set(data["metric_comparison"]) == {"C1", "C2", "C6"}


def test_run_lookup_and_metrics() -> None:
    result = client.post("/api/research/run", json=research_payload("C3")).json()
    assert client.get(f"/api/research/runs/{result['run_id']}").status_code == 200
    metrics = client.get(f"/api/research/runs/{result['run_id']}/metrics")
    assert metrics.status_code == 200
    assert "citation_coverage" in metrics.json()


def test_retrieval_search_exposes_strategy_scores() -> None:
    response = client.post("/api/retrieval/search", json={"query": "insomnia palpitations", "retrieval_strategy": "R3", "top_k": 3})
    assert response.status_code == 200
    data = response.json()
    assert data
    assert all(item["retrieval_method"] == "hybrid_reranked" for item in data)
    assert all(item["rerank_score"] is not None for item in data)


def test_emergency_abstains_before_retrieval() -> None:
    payload = research_payload()
    payload["question"] = "I have severe chest pain and cannot breathe. Which herb should I take?"
    data = client.post("/api/research/run", json=payload).json()
    assert data["scope_state"] == "safety_critical"
    assert data["abstained"] is True
    assert data["retrieval"] == []
    assert data["agent_outputs"] == []
    assert data["trace"]["termination_stage"] == "planner_scope_gate"
    assert data["trace"]["system_abstention_reason"] == "safety_critical"
    assert data["trace"]["participating_agents"] == []
    assert data["trace"]["abstaining_agents"] == []


def test_old_consensus_and_western_runtime_are_absent() -> None:
    assert client.post("/api/consensus/consult", json={"question": "test"}).status_code == 404
    env_text = (BACKEND / ".env.example").read_text(encoding="utf-8")
    for obsolete in ("ALLOW_WEST_FIXTURE", "WEST_API_BASE_URL", "WEST_API_TIMEOUT_SECONDS", "WEST_API_IMPLEMENTED"):
        assert obsolete not in env_text


def test_public_health_and_corpus_stats_disclose_legacy_fixture() -> None:
    health = client.get("/health").json()
    stats = client.get("/api/corpus/stats").json()
    assert health["runtime_profile"] == "public_demo"
    assert health["corpus_chunk_count"] == 16
    assert health["active_corpus"] == "legacy_provisional_fixture"
    assert health["llm_execution_enabled"] is False
    assert stats["corpus_mode"] == "legacy"
    assert stats["chunk_count"] == 16


class _FakeSiliconFlowLLM:
    name = "siliconflow"
    model = "Qwen/Qwen3-8B"

    def __init__(self) -> None:
        self.calls = 0

    async def generate(
        self,
        *,
        system: str,
        prompt: str,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        frequency_penalty: float = 0.0,
    ) -> GenerationResult:
        self.calls += 1
        return GenerationResult(
            text="This source-constrained educational specialist summary reports only the supplied evidence.",
            provider=self.name,
            model=self.model,
            prompt_tokens=20,
            completion_tokens=6,
        )


def test_c1_and_c2_track_actual_llm_calls_with_same_retrieval_and_model() -> None:
    async def run_pair():
        workbench = ResearchWorkbench(force_mock=True)
        fake = _FakeSiliconFlowLLM()
        current = workbench.providers
        workbench.providers = ProviderBundle(
            llm=fake,
            embedding=current.embedding,
            rerank=current.rerank,
            vector_store=current.vector_store,
            evaluator=fake,
            mock_mode=False,
        )
        workbench.settings = workbench.settings.model_copy(update={
            "llm_provider": "siliconflow",
            "llm_api_key": "unit-test-placeholder",
            "research_real_llm_enabled": True,
        })
        common = {
            "question": "Explain herbal formula concepts for insomnia in TCM teaching.",
            "retrieval_strategy": RetrievalStrategy.R2,
            "active_agents": ["syndrome", "herbal"],
            "top_k": 4,
        }
        c1 = await workbench.run(ResearchRequest(condition_id=ConditionId.C1, **common))
        c2 = await workbench.run(ResearchRequest(condition_id=ConditionId.C2, **common))
        return fake, c1, c2

    fake, c1, c2 = asyncio.run(run_pair())
    assert c1.trace is not None and c2.trace is not None
    assert c1.trace.retrieved_evidence_ids == c2.trace.retrieved_evidence_ids
    assert c1.trace.provider_calls == c1.trace.successful_provider_calls == 1
    assert c2.trace.provider_calls == c2.trace.successful_provider_calls == 2
    assert c1.trace.model == c2.trace.model == "Qwen/Qwen3-8B"
    assert c1.generation_mode == c2.generation_mode == "llm"
    assert c1.mock_mode is False and c2.mock_mode is False
    assert fake.calls == 3


def test_provider_retry_telemetry_is_redacted_and_explains_retry() -> None:
    class RetryLLM(_FakeSiliconFlowLLM):
        async def generate(self, **kwargs) -> GenerationResult:
            self.calls += 1
            if self.calls == 1:
                raise ProviderUnavailable("LLM request timed out", error_type="timeout")
            return GenerationResult(text="This source-constrained educational specialist summary reports only the supplied evidence.", provider=self.name, model=self.model)

    async def run_once():
        workbench = ResearchWorkbench(force_mock=True)
        fake = RetryLLM(); current = workbench.providers
        workbench.providers = ProviderBundle(llm=fake, embedding=current.embedding, rerank=current.rerank, vector_store=current.vector_store, evaluator=fake, mock_mode=False)
        workbench.settings = workbench.settings.model_copy(update={"llm_provider": "siliconflow", "llm_api_key": "unit-test-placeholder", "research_real_llm_enabled": True})
        return await workbench.run(ResearchRequest(question="Explain herbal formula concepts for insomnia in TCM teaching.", condition_id=ConditionId.C1, retrieval_strategy=RetrievalStrategy.R2, top_k=4))

    result = asyncio.run(run_once())
    assert result.trace is not None
    assert result.trace.provider_attempts[0].error_type == "timeout"
    assert result.trace.provider_attempts[0].retry_performed is True
    assert result.trace.provider_attempts[1].success is True
    assert all("Authorization" not in str(item) and "unit-test-placeholder" not in str(item) for item in result.trace.provider_attempts)
