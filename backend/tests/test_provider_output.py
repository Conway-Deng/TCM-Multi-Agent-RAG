from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys

import pytest


BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from agents import build_agents
from orchestration.workbench import _agent_prompt, _claim_with_citations, _synthesis
from providers.openai_compatible import (
    OpenAICompatibleLLMProvider,
    ProviderUnavailable,
    _chat_payload,
    _extract_chat_content,
    _extract_finish_reason,
    _extract_response_model,
)
from providers.output_quality import runaway_output_reason
from schemas.research import DebateTrace, ResearchAgentOutput, StructuredClaim


def test_non_streaming_payload_and_response_content_are_extracted_once() -> None:
    payload = _chat_payload(
        model="test-model",
        system="system",
        prompt="prompt",
        temperature=0.0,
        max_tokens=384,
        frequency_penalty=0.5,
    )
    assert payload["stream"] is False
    assert "enable_thinking" not in payload
    assert payload["max_tokens"] == 384
    assert payload["frequency_penalty"] == 0.5
    assert _extract_chat_content({"choices": [{"message": {"content": "one complete response"}}]}) == "one complete response"
    assert _extract_finish_reason({"choices": [{"message": {"content": "one complete response"}, "finish_reason": "stop"}]}) == "stop"
    assert _extract_finish_reason({"choices": [{"message": {"content": "one complete response"}}]}) is None
    with pytest.raises(TypeError):
        _extract_chat_content({"choices": [{"message": {"content": {"text": "not a string"}}}]})

    qwen3_payload = _chat_payload(
        model="Qwen/Qwen3-8B",
        system="system",
        prompt="prompt",
        temperature=0.0,
        max_tokens=384,
        frequency_penalty=0.5,
    )
    assert qwen3_payload["enable_thinking"] is False


def test_extract_response_model_validation() -> None:
    assert _extract_response_model({"model": "deepseek-ai/DeepSeek-V3.2"}) == "deepseek-ai/DeepSeek-V3.2"
    assert _extract_response_model({"model": "Qwen/Qwen3-8B"}) == "Qwen/Qwen3-8B"

    with pytest.raises(KeyError, match="missing 'model'"):
        _extract_response_model({})

    with pytest.raises(TypeError, match="must be a string"):
        _extract_response_model({"model": None})

    with pytest.raises(TypeError, match="must be a string"):
        _extract_response_model({"model": 12345})

    with pytest.raises(TypeError, match="must be a string"):
        _extract_response_model({"model": ["deepseek-ai/DeepSeek-V3.2"]})

    with pytest.raises(ValueError, match="non-empty string"):
        _extract_response_model({"model": ""})

    with pytest.raises(ValueError, match="non-empty string"):
        _extract_response_model({"model": "   "})


def test_provider_generation_captures_finish_reason_and_model_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    OpenAICompatibleLLMProvider._shared_http_client = None

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "model": "Qwen/Qwen3-8B",
                "choices": [{"message": {"content": "A complete provider response."}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 4, "completion_tokens": 5},
            }

    class FakeClient:
        def __init__(self, *, timeout: float) -> None:
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        async def post(self, *_, **__) -> FakeResponse:
            return FakeResponse()

    monkeypatch.setattr("providers.openai_compatible.httpx.AsyncClient", FakeClient)
    provider = OpenAICompatibleLLMProvider(
        api_key="unit-test-placeholder",
        base_url="https://api.siliconflow.cn/v1",
        model="Qwen/Qwen3-8B",
        timeout=45,
        max_tokens=1400,
        provider_name="siliconflow",
    )
    result = asyncio.run(provider.generate(system="system", prompt="prompt"))
    assert result.finish_reason == "stop"
    assert result.model == "Qwen/Qwen3-8B"
    assert result.metadata["finish_reason"] == "stop"
    assert result.metadata["requested_model"] == "Qwen/Qwen3-8B"
    assert result.metadata["provider_reported_model"] == "Qwen/Qwen3-8B"
    OpenAICompatibleLLMProvider._shared_http_client = None


def test_provider_reported_model_and_provenance_handling() -> None:
    OpenAICompatibleLLMProvider._shared_http_client = None
    captured_payload: dict | None = None

    class MockResponse:
        def __init__(self, data: dict) -> None:
            self._data = data

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return self._data

    class MockClient:
        def __init__(self, response_data: dict) -> None:
            self.response_data = response_data

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        async def post(self, url: str, headers: dict, json: dict, timeout: float) -> MockResponse:
            nonlocal captured_payload
            captured_payload = json
            return MockResponse(self.response_data)

    # 1. Outgoing request contains requested model; valid response model returned
    response_data = {
        "model": "deepseek-ai/DeepSeek-V3.2",
        "choices": [{"message": {"content": "response content"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20},
    }
    mock_client = MockClient(response_data)
    OpenAICompatibleLLMProvider._shared_http_client = mock_client

    try:
        provider = OpenAICompatibleLLMProvider(
            api_key="test-key",
            base_url="https://api.siliconflow.cn/v1",
            model="deepseek-ai/DeepSeek-V3.2",
            timeout=120.0,
            max_tokens=1200,
            provider_name="siliconflow",
        )
        result = asyncio.run(provider.generate(system="sys", prompt="user"))

        # Outgoing request contains exact requested model ID
        assert captured_payload is not None
        assert captured_payload["model"] == "deepseek-ai/DeepSeek-V3.2"

        # GenerationResult.model is provider-reported model
        assert result.model == "deepseek-ai/DeepSeek-V3.2"
        # Metadata contains both requested_model and provider_reported_model
        assert result.metadata["requested_model"] == "deepseek-ai/DeepSeek-V3.2"
        assert result.metadata["provider_reported_model"] == "deepseek-ai/DeepSeek-V3.2"

        # 2. Provider response model differing from requested model is preserved
        mock_client.response_data = {
            "model": "some/aliased-model-or-wrong-model",
            "choices": [{"message": {"content": "response content"}, "finish_reason": "stop"}],
        }
        result_divergent = asyncio.run(provider.generate(system="sys", prompt="user"))
        assert result_divergent.model == "some/aliased-model-or-wrong-model"
        assert result_divergent.metadata["requested_model"] == "deepseek-ai/DeepSeek-V3.2"
        assert result_divergent.metadata["provider_reported_model"] == "some/aliased-model-or-wrong-model"

        # 3. Missing response model raises ProviderUnavailable(error_type="malformed_response")
        mock_client.response_data = {
            "choices": [{"message": {"content": "response content"}, "finish_reason": "stop"}],
        }
        with pytest.raises(ProviderUnavailable) as exc_info:
            asyncio.run(provider.generate(system="sys", prompt="user"))
        assert exc_info.value.error_type == "malformed_response"

        # 4. Null response model raises ProviderUnavailable(error_type="malformed_response")
        mock_client.response_data = {
            "model": None,
            "choices": [{"message": {"content": "response content"}, "finish_reason": "stop"}],
        }
        with pytest.raises(ProviderUnavailable) as exc_info:
            asyncio.run(provider.generate(system="sys", prompt="user"))
        assert exc_info.value.error_type == "malformed_response"

        # 5. Empty string response model raises ProviderUnavailable(error_type="malformed_response")
        mock_client.response_data = {
            "model": "",
            "choices": [{"message": {"content": "response content"}, "finish_reason": "stop"}],
        }
        with pytest.raises(ProviderUnavailable) as exc_info:
            asyncio.run(provider.generate(system="sys", prompt="user"))
        assert exc_info.value.error_type == "malformed_response"

        # 6. Non-string response model raises ProviderUnavailable(error_type="malformed_response")
        mock_client.response_data = {
            "model": 99999,
            "choices": [{"message": {"content": "response content"}, "finish_reason": "stop"}],
        }
        with pytest.raises(ProviderUnavailable) as exc_info:
            asyncio.run(provider.generate(system="sys", prompt="user"))
        assert exc_info.value.error_type == "malformed_response"
    finally:
        OpenAICompatibleLLMProvider._shared_http_client = None


def test_evidence_prompt_is_clean_and_leaves_provenance_to_backend() -> None:
    agent = build_agents(["herbal"])[0]
    baseline = ResearchAgentOutput(
        agent_id="herbal",
        agent_name="Herbal Knowledge Agent",
        agent_version="test",
        question="What is Red Ginseng?",
        language="en",
        subdomain="herbal medicine",
        evidence_ids=["tcmv1-example"],
    )
    evidence = [type("Evidence", (), {
        "chunk_id": "tcmv1-example",
        "source_id": "symmap_v2",
        "chunk_text": "Red Ginseng is source-reported as sweet and slightly bitter.",
    })()]
    system, prompt, prompt_evidence_ids = _agent_prompt(agent, "What is Red Ginseng?", "en", baseline, evidence, None)
    decoded = json.loads(prompt)
    assert decoded["evidence"] == [{"label": "Evidence 1", "text": evidence[0].chunk_text}]
    assert "tcmv1-example" not in prompt
    assert prompt_evidence_ids == ["tcmv1-example"]
    assert "symmap_v2" not in prompt
    assert "do not emit citations" in system


def test_citations_are_added_exactly_once() -> None:
    text = "Source-constrained specialist summary."
    assert _claim_with_citations(text, ["chunk-a", "chunk-b"]) == f"{text} [chunk-a] [chunk-b]"
    assert _claim_with_citations(f"{text} [chunk-a]", ["chunk-a", "chunk-b"]) == f"{text} [chunk-a] [chunk-b]"


def test_runaway_output_is_rejected_without_rewriting_content() -> None:
    assert runaway_output_reason("Red Ginseng is traditionally described as sweet and slightly bitter.") is None
    assert runaway_output_reason("Red Ginseng is traditionally slightly slightly bitter and used to reinforce qi.") == "consecutive repeated token"
    repeated = " ".join(["spleen lung kidney"] * 5)
    assert runaway_output_reason(repeated + ".") == "repeated phrase pattern"
    assert runaway_output_reason("Red Ginseng is used classified as reinforcing qi") == "incomplete paragraph"
    assert runaway_output_reason("Red Ginseng is knownR. ginseng and is traditionally described as warm.") == "malformed token spacing"
    assert runaway_output_reason("Red Ginseng is traditionally described as warm,, sweet, and slightly bitter.") == "malformed repeated punctuation"
    assert runaway_output_reason("Red Ginseng is traditionally described as warm sweet and slightly bitter", finish_reason="stop") is None
    assert runaway_output_reason("Red Ginseng is traditionally described as warm sweet and slightly bitter", finish_reason="length") == "truncated output (finish_reason=length)"
    assert runaway_output_reason("Red Ginseng is traditionally slightly slightly bitter and used to reinforce qi", finish_reason="stop") == "consecutive repeated token"
    assert runaway_output_reason("Red Ginseng is knownR ginseng and is traditionally described as warm", finish_reason="stop") == "malformed token spacing"


def test_normal_c1_c2_synthesis_serializes_cleanly() -> None:
    claim = StructuredClaim(
        claim_id="claim-a",
        text="Red Ginseng is traditionally described as warm, sweet, and slightly bitter.",
        confidence=0.6,
        evidence_ids=["chunk-a"],
    )
    output = ResearchAgentOutput(
        agent_id="herbal",
        agent_name="Herbal Knowledge Agent",
        agent_version="test",
        question="What is Red Ginseng?",
        language="en",
        subdomain="herbal medicine",
        claims=[claim],
        evidence_ids=["chunk-a"],
        confidence=0.6,
    )
    independent = {"aggregation": "independent"}
    direct = {"aggregation": "direct"}
    c2, _, _, _ = _synthesis([output], independent, DebateTrace(), [])
    c1, _, _, _ = _synthesis([output], direct, DebateTrace(), [])
    assert c2.count("[chunk-a]") == 1
    assert c1.count("[chunk-a]") == 1
    assert runaway_output_reason(claim.text) is None
    assert "slightly slightly" not in c1
    assert "slightly slightly" not in c2
