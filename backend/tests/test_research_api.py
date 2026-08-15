from __future__ import annotations

import os
from pathlib import Path
import sys

from fastapi.testclient import TestClient


BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
os.environ["LLM_API_KEY"] = ""
os.environ["LLM_PROVIDER"] = "mock"

from main import app


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
    assert {item["id"] for item in client.get("/api/research/conditions").json()} == {f"C{i}" for i in range(7)}
    assert {item["id"] for item in client.get("/api/research/retrievers").json()} == {f"R{i}" for i in range(4)}
    assert {item["id"] for item in client.get("/api/research/judges").json()} == {"evidence", "hallucination", "safety", "conflict", "confidence", "provenance"}
    assert len(client.get("/api/research/agents").json()) >= 7


def test_full_c6_pipeline_runs_without_key() -> None:
    response = client.post("/api/tcm/multi-agent/consult", json=research_payload())
    assert response.status_code == 200
    data = response.json()
    assert data["condition_id"] == "C6"
    assert data["mock_mode"] is True
    assert len(data["agent_outputs"]) >= 2
    assert data["debate"]["enabled"] is True
    assert len(data["judge_outputs"]) == 6
    assert data["retrieval"]
    assert data["trace"]["git_commit"]
    assert data["trace"]["corpus_version"].startswith("tcm-")
    assert data["trace"]["prompt_hashes"]
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


def test_old_consensus_and_western_runtime_are_absent() -> None:
    assert client.post("/api/consensus/consult", json={"question": "test"}).status_code == 404
    env_text = (BACKEND / ".env.example").read_text(encoding="utf-8")
    for obsolete in ("ALLOW_WEST_FIXTURE", "WEST_API_BASE_URL", "WEST_API_TIMEOUT_SECONDS", "WEST_API_IMPLEMENTED"):
        assert obsolete not in env_text
