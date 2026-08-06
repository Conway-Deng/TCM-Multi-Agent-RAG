from __future__ import annotations

import os

from fastapi.testclient import TestClient

os.environ["LLM_API_KEY"] = ""
os.environ["ENABLE_SEMANTIC_RETRIEVAL"] = "false"
os.environ["ENABLE_REMOTE_RERANK"] = "false"

from main import app


client = TestClient(app)


def request(domains=None, strategy="debate_judge"):
    return client.post(
        "/api/consensus/consult",
        json={"question": "I have trouble sleeping and lower back soreness", "context": {}, "strategy": strategy, "domains": domains or ["tcm"]},
    )


def test_consensus_request_validation() -> None:
    response = client.post("/api/consensus/consult", json={"question": "x", "domains": ["tcm"]})
    assert response.status_code == 422


def test_fixture_use_blocked_by_default(monkeypatch) -> None:
    monkeypatch.setenv("ALLOW_WEST_FIXTURE", "false")
    response = request(["tcm", "western_fixture"])
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "fixture_disabled"


def test_consensus_endpoint_with_explicit_fixture_enable(monkeypatch) -> None:
    monkeypatch.setenv("ALLOW_WEST_FIXTURE", "true")
    response = request(["tcm", "western_fixture"], "weighted")
    assert response.status_code == 200
    data = response.json()
    assert data["fixture_used"] is True
    fixture = next(agent for agent in data["agents"] if agent["source_type"] == "fixture")
    assert fixture["experimental"] is True
    assert any("fixture" in item.casefold() for item in fixture["limitations"])


def test_future_west_api_returns_structured_unavailable_error(monkeypatch) -> None:
    monkeypatch.delenv("WEST_API_BASE_URL", raising=False)
    response = request(["western_api"])
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "service_unavailable"


def test_existing_tcm_endpoint_remains_functional() -> None:
    response = client.post("/api/tcm/consult", json={"question": "我有点失眠，最近腰酸", "context": {}})
    assert response.status_code == 200
    assert response.json()["agent"] == "tcm"


def test_health_exposes_flags_without_secrets(monkeypatch) -> None:
    monkeypatch.setenv("LLM_API_KEY", "obvious-test-value")
    response = client.get("/health")
    assert response.status_code == 200
    assert "consensus_enabled" in response.json()
    assert "obvious-test-value" not in response.text


def test_no_secret_appears_in_consensus_response(monkeypatch) -> None:
    secret = "obvious-non-production-test-secret"
    monkeypatch.setenv("LLM_API_KEY", "")
    response = request(["tcm"])
    assert response.status_code == 200
    assert secret not in response.text
